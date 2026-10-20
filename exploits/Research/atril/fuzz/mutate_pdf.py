#!/usr/bin/env python3
"""
mutate_pdf.py — structure-aware PDF mutator.

radamsa is excellent at byte/line-level damage, but it usually destroys the
xref table, so poppler rejects the file before Atril ever sees interesting
data. This mutator keeps the document loadable while corrupting exactly the
values Atril reads:

  * numeric tokens in dictionaries  (/Count, /Length, /Rect, /MediaBox,
    /D, /St, /Rotate, /UserUnit ...)  -> 0, -1, INT_MIN/MAX, huge
  * PDF strings in ()              -> markup, format specifiers, path
    traversal, quotes, NULs, very long runs
  * PDF names (/Foo)               -> traversal-ish names, quotes
  * dictionary keys                -> duplicate/unknown keys
  * stream bodies                  -> truncate/extend without fixing /Length

It never rewrites the xref table, and it leaves object/stream framing alone.

Usage:
    mutate_pdf.py -s SEED [--rounds N] input.pdf  > mutant.pdf
"""

import argparse
import random
import re
import sys

NUM = re.compile(rb"(?<![\w/<>\[\]])(-?\d+(?:\.\d+)?)(?![\w.])")
STR = re.compile(rb"\((?:\\.|[^()\\]|\((?:\\.|[^()\\])*\))*\)")
NAME = re.compile(rb"/([A-Za-z0-9_.#+-]{1,64})")

NASTY_NUMBERS = [
    b"0", b"-1", b"-2147483648", b"2147483647", b"4294967295",
    b"99999999999999999999", b"-99999999999999999999", b"1e309",
    b"0.0000001", b"-0", b"2147483648",
]

NASTY_STRINGS = [
    b"()",
    b"(<%s>)" % (b"A" * 8192),
    b"(\\<b\\>bold\\</b\\>)",
    b"(%n%n%n%n)",
    b"(%s%n%x%p)",
    b"(../../../../../../etc/passwd)",
    b"(/etc/cron.d/atril)",
    b"(..\\..\\..\\windows\\system32\\cmd.exe)",
    b"(\"quoted\" and 'single')",
    b"(\x00\x00\x00)",
    b"(\\377\\376\\000A)",
    b"(%s)" % (b"B" * 65536),
    b"(\\()",
    b"(\\))",
    b"(\\\\\\\\)",
]

NASTY_NAMES = [
    b"/../../etc/passwd",
    b"/%2e%2e%2f%2e%2e%2fetc",
    b"/a'b\"c",
    b"/\x00x",
    b"/%s" % (b"N" * 1024),
    b"/Launch",
    b"/JavaScript",
]


# Numbers whose corruption makes poppler reject the file outright, rather
# than reach Atril's code with hostile values.
PROTECTED_KEYS = (
    b"/Length", b"/Size", b"/Root", b"/Prev", b"/W", b"/Index",
    b"/Type", b"/Subtype", b"/Filter", b"/DecodeParms", b"/N", b"/First",
)


REF_TAIL = re.compile(rb"\s+\d+\s+R\b")


def _stream_spans(data: bytes):
    """Byte ranges occupied by stream payloads."""
    spans = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end > start:
            spans.append((start, end))
    return spans


def _protected_spans(data: bytes):
    """Byte ranges of numeric values we must not touch:
      - the cross-reference table and trailer (framing)
      - values of framing keys (/Length, /Size, /Root, ...)
      - object references ("3 0 R"): corrupting either half makes poppler
        drop the object and reject the file
      - stream payloads (mutated separately, in place)
    """
    spans = []
    # xref table: the "xref" keyword up to "trailer"
    m = re.search(rb"(?m)^xref\s*$", data)
    if m:
        trailer = data.find(b"trailer", m.end())
        spans.append((m.start(), trailer if trailer != -1 else len(data)))
    # startxref offset + trailer /Size /Root /Prev
    m = re.search(rb"startxref\s+\d+", data)
    if m:
        spans.append((m.start(), m.end()))

    for key in PROTECTED_KEYS:
        for km in re.finditer(re.escape(key) + rb"\s*", data):
            mm = NUM.match(data, km.end())
            if mm:
                spans.append((mm.start(), mm.end()))

    for nm in NUM.finditer(data):
        if REF_TAIL.match(data, nm.end()):
            spans.append((nm.start(), nm.end()))

    # object headers: "<num> <gen> obj" — both numbers are framing
    for om in re.finditer(rb"(?m)^[ \t]*(\d+)[ \t]+(\d+)[ \t]+obj\b", data):
        spans.append((om.start(1), om.end(1)))
        spans.append((om.start(2), om.end(2)))

    spans.extend(_stream_spans(data))
    return spans


def _fit(chunk: bytes, width: int, pad_byte: bytes = b" ") -> bytes:
    """Return a mutation of exactly `width` bytes.

    The xref table stores byte offsets, so every replacement MUST keep the
    original token length; otherwise poppler sees a damaged file and Atril
    never processes the hostile values."""
    if len(chunk) > width:
        chunk = chunk[:width]
    return chunk + pad_byte * (width - len(chunk))


def _fit_string(content: bytes, width: int) -> bytes:
    """Fit `content` into a PDF literal string of exactly `width` bytes
    (including the surrounding parentheses)."""
    inner = max(0, width - 2)
    if len(content) > inner:
        content = content[:inner]
    return b"(" + content + b" " * (inner - len(content)) + b")"


def _fit_name(name: bytes, width: int) -> bytes:
    """Fit a PDF name (/Foo) into exactly `width` bytes.  Trailing bytes are
    padded with #20 escapes, which are legal name characters."""
    if not name.startswith(b"/"):
        name = b"/" + name
    if len(name) > width:
        name = name[:width]
    tail = b"#20" * ((width - len(name)) // 3)
    name += tail
    return _fit(name, width, b"#20")


def mutate_numbers(data: bytes, rng: random.Random) -> bytes:
    spans = _protected_spans(data)

    def inside(a: int, b: int) -> bool:
        return any(s <= a and b <= e for s, e in spans)

    def repl(m):
        if inside(m.start(), m.end()):
            return m.group(0)
        if rng.random() < 0.55:
            return _fit(rng.choice(NASTY_NUMBERS), len(m.group(0)))
        return m.group(0)
    return NUM.sub(repl, data)


def mutate_strings(data: bytes, rng: random.Random) -> bytes:
    def repl(m):
        if rng.random() < 0.5:
            return _fit_string(rng.choice(NASTY_STRINGS)[1:-1], len(m.group(0)))
        return m.group(0)
    return STR.sub(repl, data)


def mutate_names(data: bytes, rng: random.Random) -> bytes:
    def repl(m):
        if rng.random() < 0.35:
            return _fit_name(rng.choice(NASTY_NAMES), len(m.group(0)))
        return m.group(0)
    return NAME.sub(repl, data)


def mutate_streams(data: bytes, rng: random.Random) -> bytes:
    """Damage stream payloads without touching /Length so poppler reads
    whatever bytes are there."""
    out = bytearray(data)
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end <= start:
            continue
        span = end - start
        choice = rng.random()
        if choice < 0.5:
            # overwrite in place with a recognisable payload; length preserved
            payload = (b"BT /F1 12 Tf 10 10 Td ("
                       + b"%n%s" * 500 + b") Tj ET")[:span]
            out[start:start + len(payload)] = payload
        else:
            junk = bytes(rng.getrandbits(8) for _ in range(min(span, 256)))
            out[start:start + len(junk)] = junk
        return bytes(out)
    return bytes(out)


MUTATORS = [
    (mutate_numbers, 4),
    (mutate_strings, 3),
    (mutate_names, 2),
    (mutate_streams, 1),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--seed", type=int, default=0)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("input")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    with open(args.input, "rb") as f:
        data = f.read()

    pool = []
    for fn, weight in MUTATORS:
        pool.extend([fn] * weight)

    for _ in range(args.rounds):
        fn = rng.choice(pool)
        try:
            data = fn(data, rng)
        except Exception:
            pass

    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
