#!/usr/bin/env python3
"""
gen_image_seeds.py — build a seed corpus for atril_image_harness.

Every format gdk-pixbuf reports is represented, because a PDF can carry the
same compressed bitstreams inside image XObjects (DCTDecode = JPEG,
JPXDecode = JPEG 2000, JBIG2Decode, CCITT, Flate + predictor). The harness
fuzzes the decoder, so a crash found here is reachable from a document even
when the PDF around it is perfectly valid.

Seeds are written small (64x64 unless noted) so radamsa mutates structure
rather than spending its budget on pixel noise.

Usage:
    ./gen_image_seeds.py [outdir]      # default: seeds_images/
"""

import io
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "seeds_images")


def _pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


# --------------------------------------------------------------------------
# Hand-rolled writers for formats PIL may not save
# --------------------------------------------------------------------------

def pnm():
    w = h = 32
    body = b"P6\n%d %d\n255\n" % (w, h)
    body += bytes([v for y in range(h) for x in range(w)
                   for v in (x * 8 % 256, y * 8 % 256, 128)])
    return body


def tga():
    # uncompressed 24-bit truecolour, bottom-left origin
    w = h = 32
    hdr = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, 24, 0)
    px = bytes([v for y in range(h) for x in range(w)
                for v in (x * 8 % 256, y * 8 % 256, 200)])
    return hdr + px


def bmp():
    w = h = 32
    row = (w * 3 + 3) & ~3
    pixels = bytearray()
    for y in range(h):
        line = bytearray()
        for x in range(w):
            line += bytes((x * 8 % 256, y * 8 % 256, 90))
        line += b"\0" * (row - len(line))
        pixels += line
    data = bytes(pixels)
    hdr = struct.pack("<2sIHHI", b"BM", 14 + 40 + len(data), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(data),
                      2835, 2835, 0, 0)
    return hdr + dib + data


def qoi():
    w = h = 32
    out = bytearray(b"qoif")
    out += struct.pack(">IIBB", w, h, 3, 0)
    prev = (0, 0, 0, 255)
    for y in range(h):
        for x in range(w):
            px = (x * 8 % 256, y * 8 % 256, 128, 255)
            if px[:3] == prev[:3]:
                out.append(0b11000000 | 0)          # INDEX-free run
            else:
                out.append(0b11111110)              # RGB
                out += bytes(px[:3])
            prev = px
    out += b"\0" * 7 + b"\1"
    return bytes(out)


def raw_rgb():
    w = h = 32
    return bytes([v for y in range(h) for x in range(w)
                  for v in (x * 8 % 256, y * 8 % 256, 64)])


def jbig2_like():
    """A JBIG2 segment header shape, not a decodable image.

    gdk-pixbuf has no JBIG2 decoder; this is here so the *PDF* side of the
    corpus can wrap it in a JBIG2Decode XObject, where poppler's libjbig
    is the decoder under test.
    """
    return bytes((0, 0, 0, 1)) + b"\0" * 12 + b"\x00\x01\x02\x03"


def ccitt_g4():
    """Minimal CCITT G4 (Group 4) fax bitstream: EOL + EOFB only.

    Same rationale as jbig2_like(): poppler hands CCITT to libtiff, so this
    seed exists to be wrapped in a PDF image XObject.
    """
    return bytes((0x00, 0x10, 0x01)) * 4 + b"\x00\x10\x01\x00" * 2


def jp2_minimal():
    """Minimal JPEG 2000 codestream header (SOC + SIZ + EOC)."""
    soc = b"\xff\x4f"
    siz = b"\xff\x51" + struct.pack(">H", 41)
    siz += struct.pack(">HIIIIIIII", 2, 32, 32, 0, 0, 0, 0, 0, 0)
    return soc + siz + b"\xff\xd9"


# --------------------------------------------------------------------------

def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else OUT
    os.makedirs(outdir, exist_ok=True)
    Image = _pil()
    n = 0

    def write(name, data):
        nonlocal n
        path = os.path.join(outdir, name)
        with open(path, "wb") as f:
            f.write(data)
        n += 1

    if Image is not None:
        from PIL import Image as I

        rgb = I.new("RGB", (64, 64))
        rgb.putdata([(x * 4 % 256, y * 4 % 256, 120)
                     for y in range(64) for x in range(64)])
        # 4-band with alpha, and an indexed image, exercise different paths
        rgba = rgb.convert("RGBA")
        pal = rgb.convert("P", palette=I.Palette.ADAPTIVE, colors=16)
        grey = rgb.convert("L")
        cmyk = rgb.convert("CMYK")

        for fmt, img, ext in (
                ("PNG", rgb, "png"),
                ("PNG", rgba, "rgba.png"),
                ("PNG", grey, "grey.png"),
                ("PNG", pal, "pal.png"),
                ("JPEG", rgb, "jpg"),
                ("JPEG", cmyk, "cmyk.jpg"),
                ("GIF", rgb, "gif"),
                ("GIF", pal, "pal.gif"),
                ("BMP", rgb, "bmp"),
                ("TIFF", rgb, "tif"),
                ("TIFF", rgba, "rgba.tif"),
                ("WEBP", rgb, "webp"),
                ("PPM", rgb, "ppm"),
        ):
            buf = io.BytesIO()
            try:
                img.save(buf, fmt)
                write("pil_%s.%s" % (fmt.lower(), ext), buf.getvalue())
            except Exception as exc:
                print("skip %s/%s: %s" % (fmt, ext, exc))

        # Progressive JPEG and a 16-bit PNG are distinct decoder paths.
        buf = io.BytesIO()
        try:
            rgb.save(buf, "JPEG", progressive=True, quality=85)
            write("pil_jpeg_progressive.jpg", buf.getvalue())
        except Exception as exc:
            print("skip progressive jpeg:", exc)

        buf = io.BytesIO()
        try:
            rgb.convert("I;16").save(buf, "PNG")
            write("pil_png_16bit.png", buf.getvalue())
        except Exception as exc:
            print("skip 16-bit png:", exc)

        for fmt, ext in (("AVIF", "avif"), ("HEIF", "heic"), ("JXL", "jxl"),
                         ("EXR", "exr"), ("DDS", "dds"), ("ICO", "ico")):
            buf = io.BytesIO()
            try:
                rgb.save(buf, fmt)
                write("pil_%s.%s" % (fmt.lower(), ext), buf.getvalue())
            except Exception as exc:
                print("skip %s: %s" % (fmt, exc))
    else:
        print("Pillow not available; only hand-rolled seeds")

    write("hand.pnm", pnm())
    write("hand.tga", tga())
    write("hand.bmp", bmp())
    write("hand.qoi", qoi())
    write("hand.raw", raw_rgb())
    write("hand.xpm", b"""/* XPM */
static char *s[] = {
"16 16 2 1",
"a c #ff0000",
"b c #0000ff",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa",
"abababababababab",
"babababababababa"};
""")
    write("hand.svg", b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">
  <rect x="0" y="0" width="64" height="64" fill="#0a78c8"/>
  <circle cx="32" cy="32" r="20" fill="#f0c000"/>
</svg>
""")

    # Wrapper-only seeds for the PDF-side decoders.
    write("wrap.jbig2", jbig2_like())
    write("wrap.ccitt", ccitt_g4())
    write("wrap.jp2", jp2_minimal())

    print("wrote %d seeds to %s" % (n, outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
