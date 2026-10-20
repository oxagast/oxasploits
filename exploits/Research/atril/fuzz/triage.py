#!/usr/bin/env python3
"""
triage.py — turn a sanitizer report into a stable crash signature.

The signature is "<class>-<atril-frame>" where class is the sanitizer error
kind and atril-frame is the first stack frame that lives in the Atril source
tree. That keeps distinct bugs in distinct buckets even when the failing
allocation site is in glib/poppler.

Usage: triage.py <logfile>
Exit status 0 always; prints signature (empty if the log has no report).
"""

import re
import sys

ATRIL_ROOT_HINTS = (
    "/atril/",
    "/libdocument/",
    "/libview/",
    "/backend/",
    "/shell/",
)

CLASS_PATTERNS = [
    (r"AddressSanitizer: (\w[\w-]*)", 1),
    (r"runtime error: ([^\n]*)", 2),
    (r"LeakSanitizer: detected memory leaks", None),
]

FRAME_RE = re.compile(r"^\s*#\d+\s+0x[0-9a-fA-F]+\s+in\s+(\S+)\s+(.+)$")


def sanitize(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^A-Za-z0-9_.]+", "_", s)
    return s[:90].strip("_")


def signature(text: str) -> str:
    cls = None
    for pat, grp in CLASS_PATTERNS:
        m = re.search(pat, text)
        if m:
            cls = sanitize(m.group(1)) if grp else "leak"
            break

    frame = None

    # UBSan without a stack trace still names the exact source location:
    #   /path/to/atril/backend/pdf/ev-poppler.cc:1907:9: runtime error: ...
    m = re.search(r"(/[^\s:]*/atril-hack/atril/[^\s:]+):(\d+):(\d+): runtime error",
                  text)
    if m:
        loc = m.group(1).split("/atril-hack/atril/")[-1]
        frame = sanitize("%s@%s:%s" % (loc.replace("/", "_"), m.group(2),
                                       m.group(3)))
        return "%s-%s" % (cls or "report", frame)

    for line in text.splitlines():
        m = FRAME_RE.match(line)
        if not m:
            continue
        fn, loc = m.group(1), m.group(2)
        if any(h in loc for h in ATRIL_ROOT_HINTS) and "atril-hack/fuzz" not in loc:
            loc = loc.split("/atril-hack/atril/")[-1]
            frame = sanitize(f"{fn}@{loc.rsplit(':', 1)[0].rsplit('/', 1)[-1]}")
            break

    if not cls and not frame:
        return ""

    return "%s-%s" % (cls or "report", frame or "unknownframe")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: triage.py <logfile>", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], "rb") as f:
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return 0
    sig = signature(text)
    if sig:
        print(sig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
