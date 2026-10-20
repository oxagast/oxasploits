#!/usr/bin/env bash
#
# fuzz_images.sh — radamsa-driven mutation fuzzing of the image decoders that
# Atril reaches through gdk-pixbuf.
#
# Atril decodes document-supplied images in three places:
#   * comics backend: archive entry bytes -> GdkPixbufLoader (streamed)
#   * pixbuf backend: an image file opened as a document (image/*)
#   * thumbnails/sidebar icons: gdk_pixbuf_new_from_file_at_size
#
# A PDF can carry the same compressed bitstreams inside image XObjects
# (DCTDecode = JPEG, JPXDecode = JPEG 2000, JBIG2Decode, CCITT, Flate), so a
# decoder bug found here is reachable from a document even when the PDF
# syntax around it is valid.
#
# For each iteration:
#   1. pick a seed from seeds_images/
#   2. radamsa it
#   3. run the ASan/UBSan image harness on the mutant
#   4. on a sanitizer report or a signal, save input + report, dedupe by the
#      first frame that belongs to a decoder/library
#
# Usage:
#   ./fuzz_images.sh [-n ITERATIONS] [-s SEED] [-j JOBS] [-t TIMEOUT]
#                    [-o OUTDIR] [-M structural|radamsa|both]
#                    [--unsafe] [--keep-going]
#
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="${BUILD:-$HERE/build}"
OUT="${OUT:-$HERE/out_images}"
ITER=200
SEED=0
JOBS=1
TIMEOUT=20
KEEPGOING=0
# Image-friendly: keep byte flips and block ops, drop text-only mutators that
# do nothing useful on a binary container.
RADAMSA_MUTATIONS="${RADAMSA_MUTATIONS:-num=2,ab,bd,bf,bi,br,bp,bei,bed,ber,uw,ui=2,sr,sd,ft,fn,fo}"
# structural: mutate_img.py (container-aware), radamsa: raw radamsa, both: mix
MODE="${MODE:-both}"
SAFE_FLAG="${SAFE_FLAG:---safe}"

usage() {
    sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        -n) ITER="$2"; shift 2 ;;
        -s) SEED="$2"; shift 2 ;;
        -j) JOBS="$2"; shift 2 ;;
        -t) TIMEOUT="$2"; shift 2 ;;
        -o) OUT="$2"; shift 2 ;;
        -m) RADAMSA_MUTATIONS="$2"; shift 2 ;;
        -M) MODE="$2"; shift 2 ;;
        --unsafe) SAFE_FLAG=""; shift ;;
        --keep-going) KEEPGOING=1; shift ;;
        -h|--help) usage ;;
        *) echo "unknown arg: $1" >&2; usage ;;
    esac
done

[ -x "$BUILD/atril_image_harness" ] || {
    echo "harness not built; run ./build_harness.sh" >&2; exit 1; }
command -v radamsa >/dev/null || { echo "radamsa not found" >&2; exit 1; }

SEED_DIR="$HERE/seeds_images"
[ -d "$SEED_DIR" ] || { echo "no seeds; run ./gen_image_seeds.py" >&2; exit 1; }
mapfile -t SEEDS < <(find "$SEED_DIR" -maxdepth 1 -type f | sort)
[ "${#SEEDS[@]}" -gt 0 ] || { echo "empty seed dir" >&2; exit 1; }

mkdir -p "$OUT"/{mutants,crashes,logs}

# Bash arrays cannot be exported, and run_one runs in an xargs subshell, so
# hand the list over as a file and pick from it there.
SEED_LIST="$OUT/seeds.list"
printf '%s\n' "${SEEDS[@]}" > "$SEED_LIST"
export SEED_DIR SEED_COUNT="${#SEEDS[@]}" SEED_LIST

export LD_LIBRARY_PATH="/home/marshall/Projects/atril-hack/deps/usr/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ASAN_OPTIONS="detect_leaks=0:abort_on_error=1:print_stacktrace=1:symbolize=1:handle_abort=1:log_path=$OUT/logs/asan"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"

# ---------------------------------------------------------------- triage ----
# Signature: sanitizer class + the first frame that is not libasan/libc
# startup. That groups by the decoder (libjpeg, libtiff, libwebp, ...) rather
# than by the harness, which is always the same.
signature() {
    local log="$1"
    local cls lib frame

    cls=$(grep -oE "(AddressSanitizer|UndefinedBehaviorSanitizer|LeakSanitizer): [A-Za-z0-9_-]+" "$log" |
          head -1 | sed 's/.*: //')
    [ -n "$cls" ] || cls="signal"

    # UBSan names the exact source location without a stack trace.
    local ub
    ub=$(grep -oE "^[^ :]+:[0-9]+:[0-9]+: runtime error" "$log" | head -1 |
         sed -E 's/^([^ :]+):([0-9]+):[0-9]+:.*/\1:\2/')
    if [ -n "$ub" ]; then
        echo "$cls-$(basename "$ub" | sed 's/[^A-Za-z0-9_.]/_/g')"
        return
    fi

    # First interesting frame: prefer anything that is not the harness.
    frame=$(grep -E "^ +#[0-9]+ 0x[0-9a-f]+ in " "$log" |
            grep -v "atril_image_harness" |
            head -1 |
            sed -E 's/^ +#([0-9]+) 0x[0-9a-f]+ in ([^ ]+).*/\2/')
    [ -n "$frame" ] || frame="unknown"

    lib=$(grep -oE "/(libjpeg|libtiff|libwebp|libavif|libheif|libjxl|libopenjp2|libjbig|libpng[0-9]*|libgexiv2|libraw|OpenEXR|libgdk_pixbuf|libglib|libpixman|libcairo)[^ ]*\.so[^ ]*" "$log" |
          head -1 | xargs -r basename 2>/dev/null)
    [ -n "$lib" ] || lib=""

    echo "$cls-${lib:+$lib-}$frame" | sed 's/[^A-Za-z0-9_.@:-]/_/g' | cut -c1-110
}

run_one() {
    local idx="$1"
    local rng=$((SEED + idx * 7919))
    local seedfile mut log rc sig dir

    local n=$(( (idx % SEED_COUNT) + 1 ))
    seedfile=$(sed -n "${n}p" "$SEED_LIST")
    mut="$OUT/mutants/m_${SEED}_${idx}"
    log="$OUT/logs/run_${SEED}_${idx}.log"

    # radamsa's set is chosen per container when the seed is recognised, so
    # it is not purely blind: no line-oriented mutators on binary framing,
    # and XML-tree mutation for SVG.
    local hint
    hint=$(python3 "$HERE/mutate_img.py" --suggest "$seedfile" 2>/dev/null)
    [ -n "$hint" ] || hint="$RADAMSA_MUTATIONS"

    case "$MODE" in
        structural) python3 "$HERE/mutate_img.py" -s "$rng" --rounds 2 \
                        $SAFE_FLAG "$seedfile" > "$mut" 2>/dev/null ;;
        radamsa)    radamsa -s "$rng" -n 1 -m "$hint" "$seedfile" \
                        > "$mut" 2>/dev/null ;;
        *)          if [ $((rng % 3)) -eq 0 ]; then
                        radamsa -s "$rng" -n 1 -m "$hint" "$seedfile" \
                            > "$mut" 2>/dev/null
                    else
                        python3 "$HERE/mutate_img.py" -s "$rng" --rounds 2 \
                            $SAFE_FLAG "$seedfile" > "$mut" 2>/dev/null
                    fi ;;
    esac
    [ -s "$mut" ] || { rm -f "$mut"; return 0; }

    timeout "$TIMEOUT" "$BUILD/atril_image_harness" "$mut" --quiet \
        > "$log" 2>&1
    rc=$?

    if ! grep -qE "AddressSanitizer|LeakSanitizer|ThreadSanitizer|UndefinedBehaviorSanitizer|runtime error:" "$log" 2>/dev/null; then
        if [ $rc -eq 0 ] || [ $rc -eq 1 ] || [ $rc -eq 124 ] || [ $rc -eq 137 ]; then
            rm -f "$mut" "$log"
            return 0
        fi
    fi

    sig=$(signature "$log")
    [ -n "$sig" ] || sig="unknown_rc${rc}"

    dir="$OUT/crashes/$sig"
    mkdir -p "$dir"
    if [ ! -f "$dir/input" ]; then
        cp "$mut" "$dir/input"
        cp "$log" "$dir/report.txt"
        printf 'seed=%s iteration=%s rc=%s mutant=%s\n' \
            "$(basename "$seedfile")" "$idx" "$rc" "$(basename "$mut")" \
            > "$dir/meta.txt"
        echo "CRASH [$sig] <- $(basename "$seedfile")"
    else
        echo "dup   [$sig] ($(basename "$seedfile"))"
    fi
    echo "$mut" >> "$dir/duplicates.txt"
    rm -f "$log"
    return 0
}

export -f run_one signature
export SEED ITER TIMEOUT OUT BUILD HERE SEED_DIR SEED_COUNT SEED_LIST RADAMSA_MUTATIONS
export LD_LIBRARY_PATH ASAN_OPTIONS UBSAN_OPTIONS

echo "fuzzing $ITER iterations over ${#SEEDS[@]} seeds, seed base $SEED, $JOBS job(s), timeout ${TIMEOUT}s, mode $MODE${SAFE_FLAG:+ (framing-safe)}"
echo "crash dir: $OUT/crashes"

if [ "$JOBS" -gt 1 ] && command -v xargs >/dev/null; then
    seq 1 "$ITER" | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
else
    for i in $(seq 1 "$ITER"); do
        run_one "$i"
    done
fi

echo
if [ -d "$OUT/crashes" ]; then
    found=0
    for d in "$OUT"/crashes/*/; do
        [ -d "$d" ] || continue
        found=$((found + 1))
        printf '%-52s %s\n' "$(basename "$d")" \
            "$(head -1 "$d/meta.txt" 2>/dev/null)"
    done
    [ "$found" -eq 0 ] && echo "no crashes"
fi
