#!/usr/bin/env bash
#
# build_harness.sh — build the sanitized Atril PDF harness.
#
# The harness links Atril's *own* libdocument (compiled from this repo with
# ASan/UBSan) plus the repo's backend/pdf/ev-poppler.cc as a real
# .atril-backend module. Poppler is the system library; we are looking for
# bugs in Atril's handling of poppler output, not for poppler bugs.
#
# Requirements (all already present in this environment):
#   gcc/g++ with libasan+libubsan, gtk3-devel, libxml2-devel, poppler-glib-devel
#
# Usage:
#   ./build_harness.sh [--deps <dir>] [--srcdir <atril checkout>]
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRCDIR="${SRCDIR:-/home/marshall/Projects/atril-hack/atril}"
DEPS="${DEPS:-/home/marshall/Projects/atril-hack/deps}"
BUILD="${BUILD:-$(cd "$HERE/.." && pwd)/build}"

while [ $# -gt 0 ]; do
    case "$1" in
        --deps)   DEPS="$2"; shift 2 ;;
        --srcdir) SRCDIR="$2"; shift 2 ;;
        --build)  BUILD="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

INCDIR="$DEPS/usr/include"
LIBDIR="$DEPS/usr/lib64"
SAN="-fsanitize=address,undefined -fno-sanitize-recover=all"
CFLAGS="-g -O1 -fPIC -fno-omit-frame-pointer $SAN -DHAVE_CONFIG_H -DATRIL_COMPILATION"
GTK_CFLAGS="$(pkg-config --cflags gtk+-3.0 gio-2.0 libxml-2.0)"
GTK_LIBS="$(pkg-config --libs gtk+-3.0 gio-2.0 libxml-2.0)"

export LIBRARY_PATH="$LIBDIR${LIBRARY_PATH:+:$LIBRARY_PATH}"

mkdir -p "$BUILD"/{obj/libdocument,obj,lib,backends/gen}

# ---------------------------------------------------------------- config.h
cat > "$BUILD/obj/gen/config.h" <<EOF
#define GETTEXT_PACKAGE "atril"
#define PACKAGE "atril"
#define PACKAGE_NAME "atril"
#define PACKAGE_STRING "atril 1.28.7"
#define PACKAGE_VERSION "1.28.7"
#define VERSION "1.28.7"
#define MATELOCALEDIR "/usr/share/locale"
#define DATADIR "/usr/share"
#define MATEDATADIR "/usr/share"
#define LIBDIR "/usr/lib64"
#define BINDIR "/usr/bin"
#define ATRILDATADIR "/usr/share/atril"
#define ATRIL_LOCALE_DIR "/usr/share/locale"
#define EV_BACKENDSDIR "$BUILD/backends/gen"
#define ATRIL_COMPILATION 1
#define HAVE_CONFIG_H 1
EOF

sed -e 's/@EV_MAJOR_VERSION@/1/' -e 's/@EV_MINOR_VERSION@/28/' \
    -e 's/@EV_MICRO_VERSION@/7/' \
    "$SRCDIR/libdocument/ev-version.h.in" > "$BUILD/obj/gen/ev-version.h"

# Only the public, installed headers carry public enums (ev-debug.h would
# produce entries for private debug sections).
ENUMS_SRC=$(ls "$SRCDIR"/libdocument/*.h | grep -v template | grep -v '\.in$' \
            | grep -v ev-debug.h | grep -v ev-macros.h | grep -v ev-module.h \
            | grep -v ev-file-helpers.h | grep -v ev-backends-manager.h)
glib-mkenums --template "$SRCDIR/libdocument/ev-document-type-builtins.h.template" \
    $ENUMS_SRC > "$BUILD/obj/gen/ev-document-type-builtins.h"
glib-mkenums --template "$SRCDIR/libdocument/ev-document-type-builtins.c.template" \
    $ENUMS_SRC > "$BUILD/obj/gen/ev-document-type-builtins.c"

GEN_INC="-I$BUILD/obj/gen"

# ------------------------------------------------------------- libdocument
for f in "$SRCDIR"/libdocument/*.c; do
    b="$(basename "$f" .c)"
    gcc $CFLAGS $GEN_INC -I"$SRCDIR" -I"$SRCDIR/libdocument" $GTK_CFLAGS \
        -c "$f" -o "$BUILD/obj/libdocument/$b.o"
done
gcc $CFLAGS $GEN_INC -I"$SRCDIR" -I"$SRCDIR/libdocument" $GTK_CFLAGS \
    -c "$BUILD/obj/gen/ev-document-type-builtins.c" \
    -o "$BUILD/obj/libdocument/ev-document-type-builtins.o"

gcc -shared -o "$BUILD/lib/libatrildocument.so" \
    "$BUILD"/obj/libdocument/*.o \
    -Wl,-z,relro -Wl,-z,now $GTK_LIBS

# ---------------------------------------------------------------- backend
g++ $CFLAGS $GEN_INC -I"$SRCDIR" -I"$SRCDIR/libdocument" -I"$SRCDIR/libview" \
    -I"$INCDIR/poppler/glib" -I"$INCDIR/poppler" \
    $GTK_CFLAGS -c "$SRCDIR/backend/pdf/ev-poppler.cc" \
    -o "$BUILD/obj/ev-poppler.o"

g++ -shared -o "$BUILD/backends/gen/libpdfdocument.so" \
    "$BUILD/obj/ev-poppler.o" \
    -L"$BUILD/lib" -latrildocument \
    -Wl,-rpath,"$BUILD/lib" -Wl,-Bsymbolic -Wl,-z,relro -Wl,-z,now \
    $SAN -L"$LIBDIR" -lpoppler-glib $GTK_LIBS

sed -e 's/@[A-Za-z_]*@//g' \
    "$SRCDIR/backend/pdf/pdfdocument.atril-backend.desktop.in" \
    > "$BUILD/backends/gen/pdfdocument.atril-backend"

# ---------------------------------------------------------------- harness
gcc $CFLAGS $GEN_INC -I"$SRCDIR" -I"$SRCDIR/libdocument" \
    $GTK_CFLAGS -c "$HERE/harness/atril_pdf_harness.c" \
    -o "$BUILD/obj/atril_pdf_harness.o"

gcc -g -O1 $SAN -o "$BUILD/atril_pdf_harness" "$BUILD/obj/atril_pdf_harness.o" \
    -L"$BUILD/lib" -latrildocument \
    -Wl,-rpath,"$BUILD/lib" -L"$LIBDIR" -lpoppler-glib $GTK_LIBS

# ------------------------------------------------------------ image harness
# Decoder-only harness: no Atril code, just the gdk-pixbuf paths Atril uses.
PIXBUF_CFLAGS="$(pkg-config --cflags gdk-pixbuf-2.0 glib-2.0)"
PIXBUF_LIBS="$(pkg-config --libs gdk-pixbuf-2.0 glib-2.0)"

gcc $CFLAGS $PIXBUF_CFLAGS \
    -c "$HERE/harness/atril_image_harness.c" \
    -o "$BUILD/obj/atril_image_harness.o"

gcc -g -O1 $SAN -o "$BUILD/atril_image_harness" \
    "$BUILD/obj/atril_image_harness.o" -L"$LIBDIR" $PIXBUF_LIBS

echo "built: $BUILD/atril_pdf_harness"
echo "built: $BUILD/atril_image_harness"
echo "backends: $BUILD/backends/gen"
