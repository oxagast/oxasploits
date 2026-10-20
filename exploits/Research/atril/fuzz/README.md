# Fuzzing Atril's document and image paths

Two harnesses and three drivers. Everything runs under ASan+UBSan.

```
build_harness.sh     builds ../fuzzbuild/atril_pdf_harness
                            ../fuzzbuild/atril_image_harness
gen_pdf_seeds.py     PDF seeds (document surfaces + image XObjects)
gen_image_seeds.py   image seeds (every format gdk-pixbuf reports)
mutate_pdf.py        structure-aware, length-preserving PDF mutator
fuzz_pdf.sh          radamsa/structural fuzzing of the PDF harness
fuzz_images.sh       radamsa fuzzing of the image decoder harness
triage.py            crash signature from a sanitizer report
```

## Quick start

```sh
./build_harness.sh
./gen_pdf_seeds.py seeds
./gen_image_seeds.py                    # -> seeds_images/

./fuzz_images.sh -n 6000 -j 8 -s 1      # image decoders
./fuzz_pdf.sh -n 4000 -j 6 -s 1 --no-selection
```

Crashes land in `out*/crashes/<signature>/{input,report.txt,meta.txt}`,
deduped by sanitizer class plus the first non-harness stack frame.

## Why images matter for a PDF viewer

Atril decodes document bytes in three places:

* **comics backend** — archive entry bytes streamed into `GdkPixbufLoader`
* **pixbuf backend** — an image file opened as a document (`image/*`)
* **thumbnails / sidebar icons** — `gdk_pixbuf_new_from_file_at_size`

A PDF can carry the same bitstreams inside image XObjects, where poppler hands
them to its own decoders:

| PDF filter | Decoder |
|---|---|
| `DCTDecode` | libjpeg |
| `JPXDecode` | libopenjp2 |
| `JBIG2Decode` | libjbig |
| `CCITTFaxDecode` | libtiff CCITT |
| `FlateDecode` + predictor | zlib + predictor |

So a decoder bug is reachable from a *syntactically valid* document.

`gen_pdf_seeds.py` emits `image_dct`, `image_jpx`, `image_jbig2`,
`image_ccitt`, `image_flate_predict` and `image_smask` for exactly this path.

## The `--no-selection` flag

`pdf_selection_render_selection()` reports a UBSan "null pointer passed as
argument 1" on essentially every page (the V4 finding in `poc/poc.md`). Left
on, it fires within the first few hundred iterations of any run and buries
every other crash under one signature. Pass `--no-selection` when you want to
see anything else; leave it off when you are specifically fuzzing V4.

## Harness surface

`atril_pdf_harness` walks, in the order the UI/daemon/thumbnailer would:
document info, security, links model, attachments, fonts, layers, find,
export, then per page: render at several scales/rotations, thumbnails, text
and layout, selection, images, annotations, forms, transitions, print.

`atril_image_harness` exercises one image file through every gdk-pixbuf entry
point: streamed in 512-byte chunks (the comics feed), streamed with a
size-prepared thumbnail request, `new_from_file_at_size`, `at_file_at_scale`,
and plain `new_from_file`.

## mutate_img.py — structural mutation

`mutate_img.py` parses each container and corrupts the values the decoder
trusts, instead of blindly damaging framing. Sections per format, with the
container kept intact so control reaches decode code:

| Format | What is mutated |
|---|---|
| PNG | IHDR fields, chunk lengths, duplicate/unknown chunks, PLTE, decompressed IDAT (filter bytes) with CRC recomputed |
| JPEG | SOF/SOS/DQT/DHT/APP segments, entropy data, inter-marker bytes |
| GIF | logical screen descriptor, image descriptors, LZW minimum code size, sub-block chain |
| TIFF | IFD entry types/counts/inline values, strip offsets and byte counts, dimensions, compression |
| BMP | file/DIB headers, palette |
| WEBP | RIFF chunk sizes, VP8 frame dimensions/scaling, VP8L header |
| ICO | directory entries (size/offset/bpp) |
| PNM | header tokens |
| TGA | header fields |
| QOI | header and op stream |
| DDS | header and surface masks |
| WMF | placeable header and record sizes |
| SVG | numeric attributes, element nesting, entities |
| XPM | C string table, colour-table counts |

```sh
./mutate_img.py -l                       # what each format gets
./mutate_img.py --suggest seed.jpg       # radamsa set that suits the format
./mutate_img.py --safe -s 7 x.png > out  # framing-preserving mutations only
```

### Decode rates matter

`--safe` restricts to the `FRAMING_SAFE` tier: mutators that keep the
container valid so the decoder actually runs. Measured over 10 mutations per
seed (fraction that still reached a decode):

```
webp 9/10   png 6/10   gif 6/10   bmp 5/10   jpeg 4/10   tiff 1/10
```

The framing-breaking tier (`chunk_len`, `truncate`, `tiff_mutate_entry` with
hostile types) is still available with `--unsafe`; it exercises parser
robustness rather than the decode path. `tiff 1/10` is honest: TIFF's IFD is
so position-dependent that almost any structural change is rejected early.

### radamsa, less blindly

`fuzz_images.sh` now asks `mutate_img.py --suggest` for a per-container radamsa
set: line-oriented mutators (`ld`, `ls`, `lr`, ...) are dropped for binary
containers, `xp` (XML tree) is used for SVG, and block/position-aware mutators
(`ft`, `fn`, `fo`) are added where they help. `-M structural|radamsa|both`
selects the strategy.

## Decoder sandboxing — read this before triaging

On this system gdk-pixbuf delegates to **glycin**, which runs each decoder in a
sandboxed child:

```
bwrap --unshare-all --die-with-parent ... --seccomp 27 \
      /usr/libexec/glycin-loaders/2+/glycin-image-rs --dbus-fd 23
```

Confirmed for JPEG/PNG/TIFF/ICO/WebP/SVG. Consequences:

* Every image decode error surfaced as
  `Remote error: org.gnome.glycin.Error.LoadingError: Format error decoding
  Jpeg: ... Bad Huffman Table`, i.e. the decode happened in another process.
* A memory-safety bug in those decoders is contained by the sandbox
  (no filesystem, seccomp filter, `--unshare-all`), so an image-decoder crash
  is a DoS at most and does **not** give a path to Atril's address space.
* ASan in the harness cannot observe those processes. The fuzzing still finds
  *inputs the decoders mishandle*, but instrumented detection needs
  `GLYCIN_*`/gdk-pixbuf fallback loaders, or fuzzing glycin's loaders
  directly.

**The PDF path is different.** `libpoppler.so.156` in `deps/` links
`libjpeg`, `libopenjp2`, `libwebp` and `libjbig` **in-process** and does not
spawn a loader. Measured: opening `image_dct/image_jpx/image_jbig2/
image_flate_predict.pdf` creates no bwrap/glycin children, while the same
harness linked against the system `libatrildocument` does. Poppler's image
decode is therefore the in-process, unsandboxed target — which is where a
zero-click primitive would have to come from.

## Results so far

| Run | Iterations | Strategy | Result |
|---|---|---|---|
| image decoders | 6000 | radamsa (blind) | no crashes |
| image decoders | 6000 | structural, framing-safe | no crashes |
| image decoders | 900 | both | no crashes |
| PDF image XObjects | 2500 | radamsa | no crashes |
| PDF (all seeds) | 349 hits | unfiltered | V4 only (masking) |

Mutants are verified to still reach the decoders (a mutated JPEG still sniffs
as `jpeg (64x64)` and yields 4 stream + 3 file decodes), so the clean results
are a statement about the decoders, not about mutants being rejected at
header parse.

These are not strong negative results. gdk-pixbuf's decoders run out-of-process
under glycin (below), so a crash would not be visible to ASan in this harness
anyway. The PDF-in-process poppler path is the one that matters, and it has
had far fewer iterations than the image path.

## Where the next bug most likely is

1. **Poppler's in-process image decode** (libjpeg/openjp2/jbig/webp). Unsandboxed
   and reachable with zero clicks via page render. `seeds/image_*.pdf` exist for
   this; run `fuzz_pdf.sh` against only those seeds with `--no-selection`.
2. **PDF structural surfaces** behind V4 — run with `--no-selection` and give it
   more than a few thousand iterations.
3. **glycin's loaders directly**, if you want the image decoders at all: fuzz
   `/usr/libexec/glycin-loaders/2+/glycin-image-rs` with its own corpus, since
   instrumenting it through gdk-pixbuf is not possible from this harness.
