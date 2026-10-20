#!/usr/bin/env python3
"""
mutate_img.py — structure-aware image mutator for Atril's decoder paths.

radamsa is good at blind damage, but on an image container it usually destroys
the framing (a PNG chunk length, a JPEG segment marker, a GIF sub-block chain)
and the decoder rejects the file at the header. This mutator parses the
container and corrupts the *values the decoder trusts*, while keeping the
framing valid so control reaches the interesting code.

Checksums are recomputed where the format has them (PNG CRC, QOI has none,
WebP/RIFF sizes), because libpng and friends reject a bad critical-chunk CRC
before decoding anything.

Sections, one per container
  png    chunk tree, IHDR fields, palette, recompressed IDAT (filters)
  jpeg   marker segments, SOF/SOS/DQT/DHT/RST, entropy data
  gif    LSD, GCT, image descriptors, LZW minimum code size, sub-blocks
  tiff   IFD entries, strip offsets/byte counts, tags
  bmp    file/DIB header fields, palette, row padding
  webp   RIFF chunk tree, VP8/VP8L/VP8X/ANMF headers
  ico    directory entries (ICO and CUR)
  pnm    header tokens (P1..P6)
  tga    header fields
  qoi    header and op stream
  dds    header and surface descriptors
  wmf    placeable header and record sizes
  svg    XML tree (text)
  xpm    C string table (text)

Usage:
    mutate_img.py [-s SEED] [--rounds N] [--format FMT] [-l] FILE > mutant
    mutate_img.py --suggest FILE     # radamsa mutation set for this format

Every mutator is best-effort: if a file does not parse as its claimed format,
the caller gets the input unchanged (and the fuzz driver will see no crash).
"""

import argparse
import binascii
import random
import re
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _u32be(b, o):
    return struct.unpack_from(">I", b, o)[0]


def _u32le(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _u16be(b, o):
    return struct.unpack_from(">H", b, o)[0]


def _u16le(b, o):
    return struct.unpack_from("<H", b, o)[0]


MAX_DIMS = [0, 1, 2, 0xFFFF, 0x10000, 0x7FFFFFFF, 0xFFFFFFFF]


def _splice(data, off, width, payload):
    """Replace width bytes at off with payload, keeping width if possible.

    Length-preserving replacements keep every offset after the splice valid,
    which matters for formats whose tables point at absolute positions
    (TIFF IFDs, ICO directories). When the payload is shorter it is padded;
    when longer it is truncated.
    """
    if len(payload) > width:
        payload = payload[:width]
    payload = payload + b"\x00" * (width - len(payload))
    return data[:off] + payload + data[off + width:]


def _insert(data, off, payload):
    return data[:off] + payload + data[off:]


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_CRITICAL = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}


def png_chunks(data):
    """Return [(type, chunk_off, data_off, data_len, crc_off)]."""
    if not data.startswith(PNG_SIG):
        return []
    out = []
    off = len(PNG_SIG)
    while off + 8 <= len(data):
        ln = _u32be(data, off)
        typ = data[off + 4:off + 8]
        data_off = off + 8
        crc_off = data_off + ln
        if crc_off + 4 > len(data):
            out.append((typ, off, data_off, len(data) - data_off, None))
            break
        out.append((typ, off, data_off, ln, crc_off))
        off = crc_off + 4
        if typ == b"IEND":
            break
    return out


def png_rebuild(data, chunks, replacements):
    """Rebuild a PNG, substituting chunk data by chunk offset.

    replacements: {chunk_off: (new_type, new_data)}
    CRC is recomputed for every chunk.
    """
    out = bytearray(PNG_SIG)
    for typ, off, data_off, ln, crc_off in chunks:
        if crc_off is None:
            break  # truncated tail: drop it
        if off in replacements:
            typ, body = replacements[off]
        else:
            body = data[data_off:data_off + ln]
        out += struct.pack(">I", len(body))
        out += typ
        out += body
        out += struct.pack(">I", binascii.crc32(typ + body) & 0xFFFFFFFF)
        if typ == b"IEND":
            break
    return bytes(out)


def png_ihdr(data):
    for typ, off, d_off, ln, crc in png_chunks(data):
        if typ == b"IHDR" and ln >= 13:
            w, h, depth, ctype, comp, filt, inter = struct.unpack_from(
                ">IIBBBBB", data, d_off)
            return (off, d_off, w, h, depth, ctype)
    return None


def png_mutate_ihdr(data, rng):
    info = png_ihdr(data)
    if not info:
        return data
    off, d_off, w, h, depth, ctype = info
    chunks = png_chunks(data)
    field = rng.choice(["w", "h", "depth", "ctype", "comp", "filt", "inter"])
    body = bytearray(data[d_off:d_off + 13])
    if field == "w":
        struct.pack_into(">I", body, 0, rng.choice(MAX_DIMS))
    elif field == "h":
        struct.pack_into(">I", body, 4, rng.choice(MAX_DIMS))
    elif field == "depth":
        body[8] = rng.choice([0, 1, 2, 3, 4, 8, 16, 32, 64, 255])
    elif field == "ctype":
        body[9] = rng.choice([0, 2, 3, 4, 6, 7, 255])
    elif field == "comp":
        body[10] = rng.choice([0, 1, 255])
    elif field == "filt":
        body[11] = rng.choice([0, 1, 255])
    else:
        body[12] = rng.choice([0, 1, 2, 255])
    return png_rebuild(data, chunks, {off: (b"IHDR", bytes(body))})


def png_mutate_chunk_len(data, rng):
    """Lie about a chunk length, leaving the stream misaligned on purpose."""
    chunks = png_chunks(data)
    if not chunks:
        return data
    cand = [c for c in chunks if c[0] not in (b"IEND",)]
    if not cand:
        return data
    typ, off, d_off, ln, crc = rng.choice(cand)
    new = rng.choice([0, 1, ln + 1, ln - 1 if ln else 0, 0x7FFFFFFF,
                      0xFFFFFFFF, rng.randrange(0, 4096)])
    out = bytearray(data)
    struct.pack_into(">I", out, off, new & 0xFFFFFFFF)
    return bytes(out)


def png_mutate_extra_chunk(data, rng):
    """Insert a duplicate/unknown chunk: decoders must skip it safely."""
    chunks = png_chunks(data)
    if not chunks:
        return data
    typ, off, d_off, ln, crc = chunks[-1] if len(chunks) > 1 else chunks[0]
    names = [b"tEXt", b"zTXt", b"iTXt", b"tIME", b"pHYs", b"sPLT",
             b"PLTE", b"tRNS", b"gAMA", b"IDAT", b"IHDR", b"ZZZZ",
             b"\x00\x00\x00\x00"]
    name = rng.choice(names)
    n = rng.choice([0, 1, 2, 5, 13, 64, 1024, 0xFFFF])
    body = bytes(rng.getrandbits(8) for _ in range(min(n, 4096)))
    new = (struct.pack(">I", len(body)) + name + body +
           struct.pack(">I", binascii.crc32(name + body) & 0xFFFFFFFF))
    return _insert(data, off, new)


def png_mutate_plte(data, rng):
    chunks = png_chunks(data)
    for typ, off, d_off, ln, crc in chunks:
        if typ == b"PLTE":
            body = bytearray(data[d_off:d_off + ln])
            if not body:
                return data
            for _ in range(rng.randrange(1, 6)):
                body[rng.randrange(len(body))] = rng.getrandbits(8)
            # lie about the entry count by truncating or padding
            if rng.random() < 0.5:
                body = body[:rng.randrange(1, len(body) + 1)]
            else:
                body += bytes(rng.getrandbits(8)
                              for _ in range(rng.randrange(1, 16)))
            return png_rebuild(data, chunks, {off: (b"PLTE", bytes(body))})
    return data


def png_mutate_idat(data, rng):
    """Decompress, damage the scanline/filter structure, recompress.

    This is the structural path that reaches libpng's filter and
    interlace handling rather than bouncing off the zlib stream.
    """
    info = png_ihdr(data)
    if not info:
        return data
    _, _, w, h, depth, ctype = info
    chunks = png_chunks(data)
    idat = [c for c in chunks if c[0] == b"IDAT"]
    if not idat:
        return data
    raw = b"".join(data[c[2]:c[2] + c[3]] for c in idat)
    try:
        plain = zlib.decompress(raw)
    except zlib.error:
        return data
    if not plain:
        return data

    # Size-preserving modes keep the image decodable and reach libpng's
    # filter/unfilter code; truncate/extend only exercise the size check.
    mode = rng.weighted_choice if False else rng.choice(
        ["filters", "filters", "shuffle", "shuffle", "zeros",
         "truncate", "extend"])
    if mode == "filters":
        # Every row in a non-interlaced image starts with a filter byte.
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype, 3)
        bits = depth * channels
        stride = (w * bits + 7) // 8 + 1
        out = bytearray(plain)
        for row in range(min(h, len(out) // max(stride, 1))):
            o = row * stride
            if o < len(out):
                out[o] = rng.choice([0, 1, 2, 3, 4, 5, 6, 7, 255])
        plain = bytes(out)
    elif mode == "truncate":
        plain = plain[:rng.randrange(0, len(plain) + 1)]
    elif mode == "extend":
        plain += bytes(rng.getrandbits(8)
                       for _ in range(rng.randrange(1, 512)))
    elif mode == "zeros":
        plain = bytes(len(plain))
    else:
        b = bytearray(plain)
        for _ in range(rng.randrange(1, 64)):
            b[rng.randrange(len(b))] = rng.getrandbits(8)
        plain = bytes(b)

    comp = zlib.compress(plain, rng.choice([0, 1, 6, 9]))

    # Replace the first IDAT and drop the rest.
    repl = {idat[0][1]: (b"IDAT", comp)}
    out = bytearray(PNG_SIG)
    for typ, off, d_off, ln, crc_off in chunks:
        if crc_off is None:
            break
        if off in repl:
            typ, body = repl[off]
        elif typ == b"IDAT":
            continue
        else:
            body = data[d_off:d_off + ln]
        out += struct.pack(">I", len(body)) + typ + body
        out += struct.pack(">I", binascii.crc32(typ + body) & 0xFFFFFFFF)
        if typ == b"IEND":
            break
    return bytes(out)


def png_mutate_truncate(data, rng):
    return data[:rng.randrange(len(PNG_SIG), max(len(PNG_SIG) + 1, len(data)))]


PNG_MUTATORS = [png_mutate_ihdr, png_mutate_idat, png_mutate_plte,
                png_mutate_chunk_len, png_mutate_extra_chunk,
                png_mutate_truncate]


# ---------------------------------------------------------------------------
# JPEG
# ---------------------------------------------------------------------------

SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def jpeg_segments(data):
    """Return [(marker, seg_off, payload_off, seg_end)] for header segments.

    SOS is returned with seg_end at the start of the entropy data; the caller
    treats the tail as entropy-coded bytes.
    """
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return []
    out = []
    off = 2
    while off + 3 < len(data):
        if data[off] != 0xFF:
            # resynchronise on the next marker
            nxt = data.find(b"\xff", off)
            if nxt < 0:
                break
            off = nxt
            continue
        marker = data[off + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            off += 2
            continue
        if marker == 0xD9:
            out.append((marker, off, off + 2, off + 2))
            break
        if off + 4 > len(data):
            break
        ln = _u16be(data, off + 2)
        payload = off + 4
        end = off + 2 + ln
        out.append((marker, off, payload, min(end, len(data))))
        if marker == 0xDA:
            break
        if end <= off:
            break
        off = end
    return out


def jpeg_sof_offsets(data):
    for marker, off, payload, end in jpeg_segments(data):
        if marker in SOF_MARKERS and end - payload >= 6:
            return (marker, payload, end)
    return None


def jpeg_mutate_sof(data, rng):
    """Corrupt the frame header: dimensions, precision, component count and
    per-component sampling factors. These size the decoder's buffers."""
    sof = jpeg_sof_offsets(data)
    if not sof:
        return data
    marker, payload, end = sof
    width_off = payload + 3
    height_off = payload + 1
    field = rng.choice(["w", "h", "prec", "ncomp", "sampling", "qtbl"])
    if field == "w":
        return _splice(data, width_off, 2,
                       struct.pack(">H", rng.choice(
                           [1, 2, 64, 4096, 0x7FFF, rng.randrange(1, 65536)])))
    if field == "h":
        return _splice(data, height_off, 2,
                       struct.pack(">H", rng.choice(
                           [1, 2, 64, 4096, 0x7FFF, rng.randrange(1, 65536)])))
    if field == "prec":
        return _splice(data, payload, 1,
                       bytes([rng.choice([0, 1, 8, 12, 16, 255])]))
    if field == "ncomp":
        return _splice(data, payload + 5, 1,
                       bytes([rng.choice([1, 2, 3, 3, 4])]))
    if field == "sampling":
        # Component records: id, hv, quant table
        n = data[payload + 5] if payload + 5 < len(data) else 0
        if n == 0 or payload + 6 + n * 3 > len(data):
            return data
        idx = rng.randrange(n)
        return _splice(data, payload + 7 + idx * 3, 1,
                       bytes([rng.getrandbits(8)]))
    if field == "qtbl":
        n = data[payload + 5] if payload + 5 < len(data) else 0
        if n == 0 or payload + 8 + n * 3 > len(data):
            return data
        idx = rng.randrange(n)
        return _splice(data, payload + 8 + idx * 3, 1,
                       bytes([rng.choice([0, 1, 2, 3, 4, 255])]))
    return data


def jpeg_mutate_segment_len(data, rng):
    segs = jpeg_segments(data)
    cand = [s for s in segs if s[0] not in (0xD9, 0xDA)]
    if not cand:
        return data
    marker, off, payload, end = rng.choice(cand)
    old = _u16be(data, off + 2)
    new = rng.choice([0, 1, 2, old + 1, max(0, old - 1), 0xFFFF,
                      rng.randrange(0, 65536)])
    return _splice(data, off + 2, 2, struct.pack(">H", new))


def jpeg_mutate_dqt(data, rng):
    """Corrupt quantisation tables: values drive the IDCT and can make the
    decoder do very different work."""
    for marker, off, payload, end in jpeg_segments(data):
        if marker == 0xDB and end - payload > 1:
            body = bytearray(data[payload:end])
            for _ in range(rng.randrange(1, 10)):
                i = rng.randrange(len(body))
                body[i] = rng.choice([0, 1, 2, 0x7F, 0xFF, rng.getrandbits(8)])
            return _splice(data, payload, end - payload, bytes(body))
    return data


def jpeg_mutate_dht(data, rng):
    """Corrupt Huffman table code lengths/symbols with values that are still
    structurally legal, so the scan decode runs into the damaged table rather
    than the parser rejecting the segment outright."""
    for marker, off, payload, end in jpeg_segments(data):
        if marker != 0xC4 or end - payload < 18:
            continue
        body = bytearray(data[payload:end])
        # Each table starts with a 16-byte code-count array followed by
        # symbols. Only the symbol area is safe to randomise.
        n = sum(body[1:17])
        sym_start = 17
        if sym_start + n > len(body) or n == 0:
            continue
        for _ in range(rng.randrange(1, min(n, 8) + 1)):
            body[sym_start + rng.randrange(n)] = rng.getrandbits(8)
        return _splice(data, payload, end - payload, bytes(body))
    return data


def jpeg_mutate_sos(data, rng):
    """Corrupt the scan header component count / table selectors."""
    for marker, off, payload, end in jpeg_segments(data):
        if marker != 0xDA or end - payload < 3:
            continue
        field = rng.choice(["ncomp", "tables", "ss", "se", "ahal"])
        if field == "ncomp":
            return _splice(data, payload, 1,
                           bytes([rng.choice([1, 2, 3, 4])]))
        if field == "tables":
            n = data[payload]
            if n and payload + 2 + n * 2 <= end:
                idx = rng.randrange(n)
                return _splice(data, payload + 2 + idx * 2, 1,
                               bytes([rng.getrandbits(8)]))
            return data
        if field == "ss":
            return _splice(data, payload + 1, 1,
                           bytes([rng.choice([0, 0, 1, 5, 63])]))
        if field == "se":
            return _splice(data, payload + 2, 1,
                           bytes([rng.choice([0, 63, 63, 1, 5])]))
        return _splice(data, payload + 3, 1,
                       bytes([rng.choice([0x00, 0x11, 0x22, 0x00])]))
    return data


def jpeg_mutate_entropy(data, rng):
    """Damage the entropy-coded scan data, including fake markers."""
    for marker, off, payload, end in jpeg_segments(data):
        if marker != 0xDA:
            continue
        start = end
        stop = data.rfind(b"\xff\xd9")
        if stop <= start:
            stop = len(data)
        if stop - start < 8:
            return data
        out = bytearray(data)
        mode = rng.choice(["flip", "inject_marker", "drop", "repeat"])
        if mode == "flip":
            for _ in range(rng.randrange(1, 40)):
                out[rng.randrange(start, stop)] = rng.getrandbits(8)
        elif mode == "inject_marker":
            # A stray marker inside the scan desynchronises the parser.
            p = rng.randrange(start, stop)
            mk = bytes([0xFF, rng.choice([0x00, 0xD0, 0xD7, 0xC0, 0xDA,
                                          0xDB, 0xE0, 0xFE])])
            out[p:p] = mk
        elif mode == "drop":
            a = rng.randrange(start, stop)
            b = min(stop, a + rng.randrange(1, 256))
            del out[a:b]
        else:
            a = rng.randrange(start, stop)
            b = min(stop, a + rng.randrange(1, 64))
            out[a:a] = bytes(out[a:b])
        return bytes(out)
    return data


def jpeg_mutate_app(data, rng):
    for marker, off, payload, end in jpeg_segments(data):
        if 0xE0 <= marker <= 0xEF and end - payload > 2:
            body = bytearray(data[payload:end])
            for _ in range(rng.randrange(1, 6)):
                body[rng.randrange(len(body))] = rng.getrandbits(8)
            return _splice(data, payload, end - payload, bytes(body))
    return data


JPEG_MUTATORS = [jpeg_mutate_sof, jpeg_mutate_sos, jpeg_mutate_dqt,
                 jpeg_mutate_dht, jpeg_mutate_entropy, jpeg_mutate_segment_len,
                 jpeg_mutate_app]


# ---------------------------------------------------------------------------
# GIF
# ---------------------------------------------------------------------------


def gif_mutate_lsd(data, rng):
    """Logical screen descriptor: dimensions and global colour table size.
    The GCT size field also changes how many bytes the decoder expects."""
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return data
    field = rng.choice(["w", "h", "gct_size", "bg", "aspect", "packed"])
    if field == "w":
        return _splice(data, 6, 2, struct.pack("<H", rng.choice(
            [0, 1, 0x7FFF, 0xFFFF])))
    if field == "h":
        return _splice(data, 8, 2, struct.pack("<H", rng.choice(
            [0, 1, 0x7FFF, 0xFFFF])))
    if field == "gct_size":
        packed = data[10]
        return _splice(data, 10, 1,
                       bytes([(packed & 0x78) | rng.choice([0, 1, 7]) |
                              (packed & 0x80)]))
    if field == "bg":
        return _splice(data, 11, 1, bytes([rng.getrandbits(8)]))
    if field == "aspect":
        return _splice(data, 12, 1, bytes([rng.getrandbits(8)]))
    return _splice(data, 10, 1, bytes([rng.getrandbits(8)]))


def gif_blocks(data):
    """Yield (kind, off, len) for image descriptors and extension blocks."""
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return []
    packed = data[10]
    off = 13
    if packed & 0x80:
        off += 3 * (2 ** ((packed & 0x07) + 1))
    out = []
    while off < len(data):
        b = data[off]
        if b == 0x3B:                       # trailer
            out.append(("trailer", off, 1))
            break
        if b == 0x21:                       # extension
            if off + 2 > len(data):
                break
            label = data[off + 1]
            p = off + 2
            while p < len(data) and data[p]:
                p += data[p] + 1
            out.append(("ext_%02x" % label, off, min(p + 1, len(data)) - off))
            off = p + 1
            continue
        if b == 0x2C:                       # image descriptor
            if off + 10 > len(data):
                break
            lp = data[off + 9]
            p = off + 10
            if lp & 0x80:
                p += 3 * (2 ** ((lp & 0x07) + 1))
            if p >= len(data):
                break
            p += 1                          # LZW minimum code size
            while p < len(data) and data[p]:
                p += data[p] + 1
            out.append(("image", off, min(p + 1, len(data)) - off))
            off = p + 1
            continue
        break
    return out


def gif_mutate_image_descriptor(data, rng):
    blocks = [b for b in gif_blocks(data) if b[0] == "image"]
    if not blocks:
        return data
    kind, off, ln = rng.choice(blocks)
    field = rng.choice(["x", "y", "w", "h", "packed", "lzw_min"])
    if field == "x":
        return _splice(data, off + 1, 2, struct.pack("<H", rng.getrandbits(16)))
    if field == "y":
        return _splice(data, off + 3, 2, struct.pack("<H", rng.getrandbits(16)))
    if field == "w":
        return _splice(data, off + 5, 2, struct.pack("<H", rng.choice(
            [1, 2, 0x7FFF, rng.randrange(1, 65536)])))
    if field == "h":
        return _splice(data, off + 7, 2, struct.pack("<H", rng.choice(
            [1, 2, 0x7FFF, rng.randrange(1, 65536)])))
    if field == "packed":
        # Keep the local-colour-table flag/size consistent with the bytes
        # that follow; only perturb the interlace bit and the reserved bits.
        packed = data[off + 9]
        return _splice(data, off + 9, 1, bytes([(packed & 0x87) |
                                                (rng.getrandbits(1) << 6) |
                                                (rng.getrandbits(1) << 5)]))
    # LZW minimum code size sits after the optional local colour table.
    packed = data[off + 9]
    p = off + 10 + (3 * (2 ** ((packed & 0x07) + 1)) if packed & 0x80 else 0)
    if p >= len(data):
        return data
    return _splice(data, p, 1, bytes([rng.choice([2, 3, 4, 5, 6, 7, 8, 8, 8])]))


def gif_mutate_subblocks(data, rng):
    """Corrupt the sub-block length chain: a classic GIF parser stress."""
    blocks = gif_blocks(data)
    if not blocks:
        return data
    kind, off, ln = rng.choice(blocks)
    if ln < 4:
        return data
    p = off + rng.randrange(1, ln)
    if p >= len(data):
        return data
    return _splice(data, p, 1,
                   bytes([rng.choice([0, 1, 2, 0x7F, 0xFE, 0xFF])]))


GIF_MUTATORS = [gif_mutate_lsd, gif_mutate_image_descriptor,
                gif_mutate_subblocks]


# ---------------------------------------------------------------------------
# TIFF
# ---------------------------------------------------------------------------

TIFF_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2,
                  9: 4, 10: 8, 11: 4, 12: 8}


def tiff_ifds(data):
    """Return (endian, ifd_offset, entries) for the first IFD.

    entries: [(tag, type, count, value_off, entry_off)]
    """
    if len(data) < 8:
        return None
    if data[:2] == b"II":
        e = "<"
    elif data[:2] == b"MM":
        e = ">"
    else:
        return None
    magic = struct.unpack_from(e + "H", data, 2)[0]
    if magic != 42:
        return None
    ifd = struct.unpack_from(e + "I", data, 4)[0]
    if ifd + 2 > len(data):
        return None
    n = struct.unpack_from(e + "H", data, ifd)[0]
    entries = []
    for i in range(n):
        o = ifd + 2 + i * 12
        if o + 12 > len(data):
            break
        tag, typ, count = struct.unpack_from(e + "HHI", data, o)
        entries.append((tag, typ, count, o + 8, o))
    return (e, ifd, entries)


def tiff_mutate_entry(data, rng):
    """Mutate a tag's count or inline value. Offsets that point outside the
    file are the classic TIFF out-of-bounds read."""
    info = tiff_ifds(data)
    if not info or not info[2]:
        return data
    e, ifd, entries = info
    tag, typ, count, voff, eoff = rng.choice(entries)
    choice = rng.choice(["count", "type", "value", "value", "value", "tag"])
    if choice == "count":
        new = rng.choice([0, 1, 2, 3, 0x7FFFFFFF, 0xFFFFFFFF,
                          rng.randrange(0, 1 << 16)])
        return _splice(data, eoff + 4, 4, struct.pack(e + "I", new & 0xFFFFFFFF))
    if choice == "type":
        return _splice(data, eoff + 2, 2,
                       struct.pack(e + "H", rng.choice(
                           [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
                            13, 0xFFFF])))
    if choice == "tag":
        return _splice(data, eoff, 2,
                       struct.pack(e + "H", rng.choice(
                           [256, 257, 258, 259, 262, 273, 277, 278, 279,
                            282, 283, 284, 0xFFFF])))
    size = TIFF_TYPE_SIZE.get(typ, 4)
    if count * size <= 4:
        # Value is stored inline in the entry: corrupt it in place.
        return _splice(data, voff, 4, struct.pack(
            e + "I", rng.choice([0, 1, 2, 8, 16, 0x7FFFFFFF, 0xFFFFFFFF,
                                 rng.randrange(0, 1 << 24)])))
    return _splice(data, voff, 4, struct.pack(e + "I", rng.choice(
        [8, 16, 32, len(data) - 8, 0x7FFFFFFF, 0xFFFFFFFF]) & 0xFFFFFFFF))


def tiff_mutate_strips(data, rng):
    """Point strip offsets / byte counts at hostile values."""
    info = tiff_ifds(data)
    if not info:
        return data
    e, ifd, entries = info
    for tag, typ, count, voff, eoff in entries:
        if tag not in (273, 279):           # StripOffsets, StripByteCounts
            continue
        if count == 1:
            new = rng.choice([0, 1, len(data), 0x7FFFFFFF, 0xFFFFFFFF,
                              rng.randrange(0, 1 << 24)])
            return _splice(data, voff, 4,
                           struct.pack(e + "I", new & 0xFFFFFFFF))
        arr = struct.unpack_from(e + "I", data, voff)[0]
        if arr + 4 > len(data):
            return data
        return _splice(data, arr, 4, struct.pack(
            e + "I", rng.choice([0, 1, 0x7FFFFFFF, 0xFFFFFFFF]) & 0xFFFFFFFF))
    return data


def tiff_mutate_tags(data, rng):
    """Dimensions, rows-per-strip, bits-per-sample, compression."""
    info = tiff_ifds(data)
    if not info:
        return data
    e, ifd, entries = info
    for tag, typ, count, voff, eoff in entries:
        if tag == 256 or tag == 257:        # ImageWidth / ImageLength
            new = rng.choice([0, 1, 2, 0x7FFF, 0xFFFF, 0x7FFFFFFF])
            if typ == 3:
                return _splice(data, voff, 2, struct.pack(e + "H", new & 0xFFFF))
            return _splice(data, voff, 4, struct.pack(e + "I", new & 0xFFFFFFFF))
        if tag == 278:                      # RowsPerStrip
            return _splice(data, voff, 4, struct.pack(
                e + "I", rng.choice([0, 1, 0xFFFFFFFF])))
        if tag == 259:                      # Compression
            return _splice(data, voff, 2, struct.pack(
                e + "H", rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 32773, 0xFFFF])))
        if tag == 258:                      # BitsPerSample
            return _splice(data, voff, 2, struct.pack(
                e + "H", rng.choice([0, 1, 2, 4, 8, 16, 32, 64, 0xFFFF])))
        if tag == 262:                      # PhotometricInterpretation
            return _splice(data, voff, 2, struct.pack(
                e + "H", rng.choice([0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 0xFFFF])))
    return data


TIFF_MUTATORS = [tiff_mutate_entry, tiff_mutate_strips, tiff_mutate_tags]


# ---------------------------------------------------------------------------
# BMP
# ---------------------------------------------------------------------------


def bmp_mutate_header(data, rng):
    if len(data) < 54 or data[:2] != b"BM":
        return data
    dib = _u32le(data, 14)
    field = rng.choice(["w", "h", "bpp", "compression", "planes",
                        "imgsize", "clrused", "dib"])
    if field == "w":
        return _splice(data, 18, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFF, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "h":
        return _splice(data, 22, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFF, 0x7FFFFFFF, 0xFFFFFFFF, 0x80000000])))
    if field == "bpp":
        return _splice(data, 28, 2, struct.pack("<H", rng.choice(
            [1, 2, 4, 8, 16, 24, 32, 32])))
    if field == "compression":
        return _splice(data, 30, 4, struct.pack("<I", rng.choice(
            [0, 1, 2, 3, 4, 5, 6, 11, 12, 13])))
    if field == "planes":
        return _splice(data, 26, 2, struct.pack("<H", rng.choice([1, 1, 1])))
    if field == "imgsize":
        return _splice(data, 34, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "clrused":
        return _splice(data, 46, 4, struct.pack("<I", rng.choice(
            [0, 1, 2, 256, 0xFFFFFFFF])))
    return _splice(data, 14, 4, struct.pack("<I", rng.choice(
        [12, 40, 52, 56, 108, 124, 0xFFFFFFFF])))


def bmp_mutate_palette(data, rng):
    if len(data) < 54 or data[:2] != b"BM":
        return data
    off = _u32le(data, 10)
    dib = _u32le(data, 14)
    pal_start = 14 + dib
    if pal_start >= len(data) or off > len(data):
        return data
    p = rng.randrange(pal_start, max(pal_start + 1, min(off, len(data))))
    return _splice(data, p, 1, bytes([rng.getrandbits(8)]))


BMP_MUTATORS = [bmp_mutate_header, bmp_mutate_palette]


# ---------------------------------------------------------------------------
# WEBP (RIFF)
# ---------------------------------------------------------------------------


def webp_chunks(data):
    """Return [(fourcc, off, size_off, payload_off, size, padded_end)]."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return []
    out = []
    off = 12
    while off + 8 <= len(data):
        cc = data[off:off + 4]
        size = _u32le(data, off + 4)
        payload = off + 8
        end = payload + size + (size & 1)
        out.append((cc, off, off + 4, payload, size, min(end, len(data))))
        if end <= off or end > len(data):
            break
        off = end
    return out


def webp_mutate_chunk_size(data, rng):
    chunks = webp_chunks(data)
    if not chunks:
        return data
    cc, off, size_off, payload, size, end = rng.choice(chunks)
    new = rng.choice([0, 1, size + 1, max(0, size - 1), 0x7FFFFFFF,
                      0xFFFFFFFF, rng.randrange(0, 1 << 20)])
    out = _splice(data, size_off, 4, struct.pack("<I", new & 0xFFFFFFFF))
    if rng.random() < 0.5:                  # keep RIFF size consistent
        riff = _u32le(out, 4)
        out = _splice(out, 4, 4, struct.pack("<I", (riff + 4) & 0xFFFFFFFF))
    return out


def webp_mutate_vp8(data, rng):
    """VP8 keyframe header: the 3-byte start code, dimensions, scaling."""
    for cc, off, size_off, payload, size, end in webp_chunks(data):
        if cc != b"VP8 " or size < 10:
            continue
        # frame tag (3 bytes) then 0x9d 0x01 0x2a then 14-bit dimensions
        if data[payload + 3:payload + 6] != b"\x9d\x01\x2a":
            return data
        p = payload + 6
        field = rng.choice(["w", "h", "scale", "scale"])
        if field == "w":
            return _splice(data, p, 2,
                           struct.pack("<H", rng.choice(
                               [1, 63, 64, 16383, rng.randrange(1, 16384)])))
        if field == "h":
            return _splice(data, p + 2, 2,
                           struct.pack("<H", rng.choice(
                               [1, 63, 64, 16383, rng.randrange(1, 16384)])))
        v = _u16le(data, p + 4) if p + 6 <= len(data) else 0
        return _splice(data, p + 4, 2, struct.pack("<H", v ^ 0xC000))
    return data


def webp_mutate_vp8l(data, rng):
    """VP8L signature, 14-bit dimensions, alpha flag, version."""
    for cc, off, size_off, payload, size, end in webp_chunks(data):
        if cc != b"VP8L" or size < 5:
            continue
        if data[payload] != 0x2F:
            return data
        if rng.random() < 0.6:
            v = _u32le(data, payload + 1)
            return _splice(data, payload + 1, 4,
                           struct.pack("<I", v ^ rng.getrandbits(32)))
        return _splice(data, payload, 1, bytes([rng.getrandbits(8)]))
    return data


WEBP_MUTATORS = [webp_mutate_vp8, webp_mutate_vp8l,
                 webp_mutate_chunk_size]


# ---------------------------------------------------------------------------
# ICO / CUR
# ---------------------------------------------------------------------------


def ico_mutate_dir(data, rng):
    if len(data) < 6:
        return data
    n = _u16le(data, 4)
    if n == 0 or 6 + n * 16 > len(data):
        return data
    i = rng.randrange(n)
    base = 6 + i * 16
    field = rng.choice(["w", "h", "colors", "planes", "bpp", "size", "offset"])
    if field == "w":
        return _splice(data, base, 1, bytes([rng.choice([0, 1, 0x7F, 0xFF])]))
    if field == "h":
        return _splice(data, base + 1, 1, bytes([rng.choice([0, 1, 0x7F, 0xFF])]))
    if field == "colors":
        return _splice(data, base + 2, 1, bytes([rng.getrandbits(8)]))
    if field == "planes":
        return _splice(data, base + 4, 2, struct.pack("<H", rng.getrandbits(16)))
    if field == "bpp":
        return _splice(data, base + 6, 2, struct.pack("<H", rng.choice(
            [0, 1, 4, 8, 16, 24, 32, 0xFFFF])))
    if field == "size":
        return _splice(data, base + 8, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF, rng.randrange(0, 1 << 24)])))
    return _splice(data, base + 12, 4, struct.pack("<I", rng.choice(
        [0, 1, 22, 0x7FFFFFFF, 0xFFFFFFFF, rng.randrange(0, len(data) + 64)])))


ICO_MUTATORS = [ico_mutate_dir]


# ---------------------------------------------------------------------------
# PNM
# ---------------------------------------------------------------------------


def pnm_tokens(data):
    out = []
    i = 0
    while i < len(data):
        if data[i:i + 1] == b"#":
            j = data.find(b"\n", i)
            i = len(data) if j < 0 else j + 1
            continue
        if data[i:i + 1].isspace():
            i += 1
            continue
        j = i
        while j < len(data) and not data[j:j + 1].isspace():
            j += 1
        out.append((i, j))
        i = j
        if len(out) >= 4:
            break
    return out


def pnm_mutate_header(data, rng):
    toks = pnm_tokens(data)
    if len(toks) < 3 or data[:2] not in (b"P1", b"P2", b"P3", b"P4",
                                         b"P5", b"P6"):
        return data
    which = rng.randrange(1, min(4, len(toks)))
    a, b = toks[which]
    value = rng.choice([b"0", b"1", b"-1", b"2147483647", b"4294967295",
                        b"99999999999999999999", b"65536"])
    return data[:a] + value + data[b:]


PNM_MUTATORS = [pnm_mutate_header]


# ---------------------------------------------------------------------------
# TGA
# ---------------------------------------------------------------------------


def tga_mutate_header(data, rng):
    if len(data) < 18:
        return data
    field = rng.choice(["idlen", "cmap", "type", "cmap_len", "cmap_depth",
                        "x", "y", "w", "h", "bpp", "descriptor"])
    offs = {"idlen": (0, 1), "cmap": (1, 1), "type": (2, 1),
            "cmap_len": (5, 2), "cmap_depth": (7, 1), "x": (8, 2),
            "y": (10, 2), "w": (12, 2), "h": (14, 2), "bpp": (16, 1),
            "descriptor": (17, 1)}
    off, width = offs[field]
    if width == 1:
        return _splice(data, off, 1, bytes([rng.getrandbits(8)]))
    return _splice(data, off, 2, struct.pack("<H", rng.choice(
        [0, 1, 2, 0x7FFF, 0xFFFF])))


TGA_MUTATORS = [tga_mutate_header]


# ---------------------------------------------------------------------------
# QOI
# ---------------------------------------------------------------------------


def qoi_mutate(data, rng):
    if len(data) < 14 or data[:4] != b"qoif":
        return data
    field = rng.choice(["w", "h", "channels", "colorspace", "ops"])
    if field == "w":
        return _splice(data, 4, 4, struct.pack(">I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "h":
        return _splice(data, 8, 4, struct.pack(">I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "channels":
        return _splice(data, 12, 1, bytes([rng.choice([0, 3, 4, 255])]))
    if field == "colorspace":
        return _splice(data, 13, 1, bytes([rng.choice([0, 1, 255])]))
    if len(data) <= 22:
        return data
    p = rng.randrange(14, len(data) - 8)
    if rng.random() < 0.5:
        return _splice(data, p, 1, bytes([rng.getrandbits(8)]))
    # Insert an opcode run that claims far more pixels than exist.
    return _insert(data, p, bytes([0xFE, rng.getrandbits(8),
                                   rng.getrandbits(8), rng.getrandbits(8)]))


QOI_MUTATORS = [qoi_mutate]


# ---------------------------------------------------------------------------
# DDS
# ---------------------------------------------------------------------------


def dds_mutate(data, rng):
    if len(data) < 128 or data[:4] != b"DDS ":
        return data
    field = rng.choice(["h", "w", "pitch", "mips", "pf_flags", "fourcc",
                        "rgb_bits", "masks", "caps"])
    if field == "h":
        return _splice(data, 12, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "w":
        return _splice(data, 16, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "pitch":
        return _splice(data, 20, 4, struct.pack("<I", rng.getrandbits(32)))
    if field == "mips":
        return _splice(data, 28, 4, struct.pack("<I", rng.choice(
            [0, 1, 2, 255, 0xFFFFFFFF])))
    if field == "pf_flags":
        return _splice(data, 80, 4, struct.pack("<I", rng.getrandbits(32)))
    if field == "fourcc":
        return _splice(data, 84, 4, bytes(rng.getrandbits(8) for _ in range(4)))
    if field == "rgb_bits":
        return _splice(data, 88, 4, struct.pack("<I", rng.choice(
            [0, 8, 16, 24, 32, 64, 0xFFFFFFFF])))
    if field == "masks":
        return _splice(data, 92 + rng.randrange(4) * 4, 4,
                       struct.pack("<I", rng.getrandbits(32)))
    return _splice(data, 108, 4, struct.pack("<I", rng.getrandbits(32)))


DDS_MUTATORS = [dds_mutate]


# ---------------------------------------------------------------------------
# WMF
# ---------------------------------------------------------------------------


def wmf_mutate(data, rng):
    if len(data) < 22:
        return data
    placeable = data[:4] == b"\xd7\xcd\xc6\x9a"
    base = 22 if placeable else 0
    if len(data) < base + 18:
        return data
    field = rng.choice(["type", "headersize", "version", "size",
                        "objects", "maxrec", "params", "record"])
    hdr = base
    if field == "type":
        return _splice(data, hdr, 2, struct.pack("<H", rng.getrandbits(16)))
    if field == "headersize":
        return _splice(data, hdr + 2, 2, struct.pack("<H", rng.choice(
            [0, 9, 0xFFFF])))
    if field == "version":
        return _splice(data, hdr + 4, 2, struct.pack("<H", rng.choice(
            [0x0100, 0x0300, 0xFFFF])))
    if field == "size":
        return _splice(data, hdr + 6, 4, struct.pack("<I", rng.choice(
            [0, 1, 0x7FFFFFFF, 0xFFFFFFFF])))
    if field == "objects":
        return _splice(data, hdr + 12, 4, struct.pack("<I", rng.getrandbits(32)))
    if field == "maxrec":
        return _splice(data, hdr + 16, 2, struct.pack("<H", rng.getrandbits(16)))
    if field == "params":
        return _splice(data, hdr + 18, 2, struct.pack("<H", rng.getrandbits(16)))
    if len(data) > hdr + 24:
        p = rng.randrange(hdr + 18, len(data) - 6)
        return _splice(data, p, 4, struct.pack("<I", rng.choice(
            [0, 1, 3, 0x7FFFFFFF, 0xFFFFFFFF])))
    return data


WMF_MUTATORS = [wmf_mutate]


# ---------------------------------------------------------------------------
# SVG / XPM (text)
# ---------------------------------------------------------------------------

NUM_RE = re.compile(rb"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


def svg_mutate(data, rng):
    """Numeric attributes drive the renderer's size and path arithmetic."""
    mode = rng.choice(["num", "tag", "attr", "entity", "nest", "huge"])
    if mode == "num":
        return NUM_RE.sub(
            lambda m: rng.choice([b"0", b"-1", b"2147483647", b"1e309",
                                  b"-2147483648", b"99999999999999999999"]),
            data, count=rng.randrange(1, 5))
    if mode == "attr":
        return data.replace(b'width="64"', b'width="2147483647"', 1) \
                   .replace(b'height="64"', b'height="999999999999"', 1)
    if mode == "tag":
        return data.replace(b"<rect", b"<rectFoo", 1)
    if mode == "entity":
        return data.replace(b"<svg", b'<!DOCTYPE x [<!ENTITY e "&e;&e;&e;">]><svg', 1)
    if mode == "huge":
        return data.replace(b"</svg>", b"<rect width='99999' height='99999'/>" * 200 + b"</svg>", 1)
    return data + b"<g>" * 5000 + b"</g>" * 5000


def xpm_mutate(data, rng):
    lines = data.split(b"\n")
    if not lines:
        return data
    idx = rng.randrange(len(lines))
    mode = rng.choice(["num", "quote", "counts", "long"])
    if mode == "num":
        lines[idx] = NUM_RE.sub(
            lambda m: rng.choice([b"0", b"-1", b"65535", b"2147483647"]),
            lines[idx], count=1)
    elif mode == "counts":
        # The "W H N C" header line controls the colour table size.
        for i, ln in enumerate(lines):
            if re.match(rb'^\s*"\d+\s+\d+\s+\d+\s+\d+"', ln):
                lines[i] = b'"1 1 65535 1"'
                break
    elif mode == "quote":
        lines[idx] = lines[idx].replace(b'"', b"", 1)
    else:
        lines[idx] = lines[idx] + b"A" * 4096
    return b"\n".join(lines)


SVG_MUTATORS = [svg_mutate]
XPM_MUTATORS = [xpm_mutate]


# ---------------------------------------------------------------------------
# Format detection and registry
# ---------------------------------------------------------------------------


EXT_HINTS = {
    ".tga": "tga", ".targa": "tga", ".ico": "ico", ".cur": "ico",
    ".wmf": "wmf", ".apm": "wmf", ".qoi": "qoi", ".dds": "dds",
    ".svg": "svg", ".svgz": "svg", ".xpm": "xpm", ".pnm": "pnm",
    ".pbm": "pnm", ".pgm": "pnm", ".ppm": "pnm", ".jxl": "jpeg",
    ".heic": "jpeg", ".avif": "jpeg",
}


def detect(data, path=None):
    if path:
        import os
        ext = os.path.splitext(path)[1].lower()
        if ext in EXT_HINTS and ext not in (".jxl", ".heic", ".avif"):
            return EXT_HINTS[ext]
    if data.startswith(PNG_SIG):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] in (b"II", b"MM") and len(data) > 4:
        if data[:4] in (b"II*\x00", b"MM\x00*"):
            return "tiff"
    if data.startswith(b"BM") and len(data) > 14:
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:4] in (b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"):
        # A real ICO directory has 1..255 entries and fits inside the file.
        n = struct.unpack_from("<H", data, 4)[0] if len(data) >= 6 else 0
        if 0 < n <= 255 and 6 + n * 16 <= len(data):
            return "ico"
    if data[:2] in (b"P1", b"P2", b"P3", b"P4", b"P5", b"P6"):
        return "pnm"
    if data[:4] == b"qoif":
        return "qoi"
    if data[:4] == b"DDS ":
        return "dds"
    if data[:4] == b"\xd7\xcd\xc6\x9a":
        return "wmf"
    head = data[:4096]
    if b"<svg" in head or (head.lstrip().startswith(b"<?xml") and b"svg" in head):
        return "svg"
    if head.lstrip().startswith(b"/* XPM */"):
        return "xpm"
    return None


REGISTRY = {
    "png": PNG_MUTATORS,
    "jpeg": JPEG_MUTATORS,
    "gif": GIF_MUTATORS,
    "tiff": TIFF_MUTATORS,
    "bmp": BMP_MUTATORS,
    "webp": WEBP_MUTATORS,
    "ico": ICO_MUTATORS,
    "pnm": PNM_MUTATORS,
    "tga": TGA_MUTATORS,
    "qoi": QOI_MUTATORS,
    "dds": DDS_MUTATORS,
    "wmf": WMF_MUTATORS,
    "svg": SVG_MUTATORS,
    "xpm": XPM_MUTATORS,
}

# Mutators that keep the container framing intact, so the decoder parses the
# damaged values instead of rejecting the file at the header. Everything else
# is "framing-breaking" (useful for parser robustness, useless for reaching
# the decode path). fuzz_images.sh uses these two tiers separately.
FRAMING_SAFE = {
    "png":  [png_mutate_ihdr, png_mutate_plte, png_mutate_extra_chunk,
             png_mutate_idat],
    "jpeg": [jpeg_mutate_sof, jpeg_mutate_sos, jpeg_mutate_dqt,
             jpeg_mutate_dht, jpeg_mutate_entropy, jpeg_mutate_app],
    "gif":  [gif_mutate_lsd, gif_mutate_image_descriptor],
    "tiff": [tiff_mutate_entry, tiff_mutate_strips, tiff_mutate_tags],
    "bmp":  [bmp_mutate_header, bmp_mutate_palette],
    "webp": [webp_mutate_vp8, webp_mutate_vp8l],
    "ico":  [ico_mutate_dir],
    "pnm":  [pnm_mutate_header],
    "tga":  [tga_mutate_header],
    "qoi":  [qoi_mutate],
    "dds":  [dds_mutate],
    "wmf":  [wmf_mutate],
    "svg":  [svg_mutate],
    "xpm":  [xpm_mutate],
}


# A radamsa mutation set that suits each container. Line-oriented mutators
# (ld/ls/lr/...) are useless on binary framing; block/position-aware ones
# (ft/fn/fo) and the XML tree parser (xp) are what actually reach the decoder.
RADAMSA_HINTS = {
    "png":   "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo,num=1",
    "jpeg":  "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo,sr,sd",
    "gif":   "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo,sr,sd",
    "tiff":  "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo,sr,sd",
    "bmp":   "bd,bf,bi,br,bp,bei,bed,ber,uw,sr,sd",
    "webp":  "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo,sr,sd",
    "ico":   "bd,bf,bi,br,bp,bei,bed,ber,uw,sr,sd",
    "pnm":   "num=6,ab,bd,bf,bi,br,bp,uw",
    "tga":   "bd,bf,bi,br,bp,bei,bed,ber,uw",
    "qoi":   "bd,bf,bi,br,bp,bei,bed,ber,uw,sr,sd",
    "dds":   "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo",
    "wmf":   "bd,bf,bi,br,bp,bei,bed,ber,uw,ft,fn,fo,sr,sd",
    "svg":   "xp=9,num=6,ab,uw,ui,sr",
    "xpm":   "num=6,ab,uw,ui,sr",
}


def main():
    ap = argparse.ArgumentParser(
        description="Structure-aware image mutator for Atril's decoders.")
    ap.add_argument("file", nargs="?")
    ap.add_argument("-s", "--seed", type=int, default=0)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--format", dest="fmt", default=None)
    ap.add_argument("--safe", action="store_true",
                    help="use only mutators that keep container framing valid "
                         "(reaches decoder internals instead of failing early)")
    ap.add_argument("-l", "--list", action="store_true",
                    help="list formats and mutators and exit")
    ap.add_argument("--suggest", action="store_true",
                    help="print the radamsa mutation set for this file")
    args = ap.parse_args()

    if args.list:
        for fmt, muts in sorted(REGISTRY.items()):
            print("%-6s %2d mutators: %s" %
                  (fmt, len(muts), ", ".join(m.__name__ for m in muts)))
        return 0

    if not args.file:
        ap.error("a file is required unless --list is used")

    with open(args.file, "rb") as f:
        data = f.read()

    fmt = args.fmt or detect(data, args.file)
    if args.suggest:
        if not fmt:
            print("bd,bf,bi,br,bp,uw")
        else:
            print(RADAMSA_HINTS.get(fmt, "bd,bf,bi,br,bp,uw"))
        return 0

    if not fmt or fmt not in REGISTRY:
        sys.stdout.buffer.write(data)
        return 0

    rng = random.Random(args.seed)
    muts = FRAMING_SAFE[fmt] if args.safe and fmt in FRAMING_SAFE else REGISTRY[fmt]
    for _ in range(args.rounds):
        fn = rng.choice(muts)
        try:
            new = fn(data, rng)
        except Exception:
            continue
        if new:
            data = new

    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
