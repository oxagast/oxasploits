#!/usr/bin/env bash
#
# fuzz_pdf.sh — radamsa-driven mutation fuzzing of Atril's PDF path.
#
# For each iteration:
#   1. pick a seed from seeds/
#   2. radamsa it (structure-aware-ish text mutation, PDF syntax survives often)
#   3. run the ASan/UBSan harness on the mutant
#   4. on a sanitizer report or a signal, save the input + report, dedupe by
#      the top Atril frame.
#
# Crashes are written to $OUT/crashes/<sig>/{input.pdf,report.txt}. The
# signature is derived from the first frame that belongs to atril sources,
# so distinct bugs land in distinct directories.
#
# Usage:
#   ./fuzz_pdf.sh [-n ITERATIONS] [-s SEED] [-j JOBS] [-t TIMEOUT] [-o OUTDIR]
#                 [-M radamsa|structural|both] [-m RADAMSA_MUTATIONS]
#                 [--all-pages] [--no-selection]
#
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="${BUILD:-$HERE/build}"
OUT="${OUT:-$HERE/out}"
ITER=200
MODE=both
SEED=0
JOBS=1
TIMEOUT=30
ALLPAGES=""
EXTRA_FLAGS=""
KEEPGOING=0
# PDF-friendly default: keep string/number mutations, drop XML-only ones
# that usually destroy the whole file.
RADAMSA_MUTATIONS="num=6,ld,lds,lr2,li,ls,lp,lr,lis,lrs,sr,sd,bd,bf,bi,br,bp,bei,bed,ber,uw,ui=2,ab"

usage() {
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
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
        --all-pages) ALLPAGES="--all-pages"; shift ;;
        --no-selection) EXTRA_FLAGS="$EXTRA_FLAGS --no-selection"; shift ;;
        --keep-going) KEEPGOING=1; shift ;;
        -h|--help) usage ;;
        *) echo "unknown arg: $1" >&2; usage ;;
    esac
done

[ -x "$BUILD/atril_pdf_harness" ] || { echo "harness not built; run ./build_harness.sh" >&2; exit 1; }
command -v radamsa >/dev/null || { echo "radamsa not found" >&2; exit 1; }

mkdir -p "$OUT"/{mutants,crashes,logs}
SEED_DIR="${SEED_DIR_IN:-$HERE/seeds}"
mapfile -t SEEDS < <(ls "$SEED_DIR"/*.pdf 2>/dev/null)
[ "${#SEEDS[@]}" -gt 0 ] || { echo "no seeds; run ./gen_pdf_seeds.py seeds" >&2; exit 1; }
export SEED_DIR SEED_COUNT="${#SEEDS[@]}"

export LD_LIBRARY_PATH="/home/marshall/Projects/atril-hack/deps/usr/lib64:$BUILD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ASAN_OPTIONS="detect_leaks=0:abort_on_error=1:print_stacktrace=1:symbolize=1:handle_abort=1:log_path=$OUT/logs/asan"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"

run_one() {
    local idx="$1"
    local rng=$((SEED + idx * 7919))
    local seedfile
    seedfile="$(ls "$SEED_DIR"/*.pdf | sed -n "$(( (idx % SEED_COUNT) + 1 ))p")"
    local mut="$OUT/mutants/m_${SEED}_${idx}.pdf"
    local log="$OUT/logs/run_${SEED}_${idx}.log"

    case "$MODE" in
        radamsa)  radamsa -s "$rng" -n 1 -m "$RADAMSA_MUTATIONS" \
                      "$seedfile" > "$mut" 2>/dev/null ;;
        structural) python3 "$HERE/mutate_pdf.py" -s "$rng" \
                      "$seedfile" > "$mut" 2>/dev/null ;;
        both) if [ $((rng % 2)) -eq 0 ]; then
                  radamsa -s "$rng" -n 1 -m "$RADAMSA_MUTATIONS" \
                      "$seedfile" > "$mut" 2>/dev/null
              else
                  python3 "$HERE/mutate_pdf.py" -s "$rng" \
                      "$seedfile" > "$mut" 2>/dev/null
              fi ;;
    esac
    [ -s "$mut" ] || { rm -f "$mut"; return 0; }

    timeout "$TIMEOUT" "$BUILD/atril_pdf_harness" "$mut" --quiet $ALLPAGES $EXTRA_FLAGS \
        > "$log" 2>&1
    local rc=$?

    # A sanitizer failure exits through the sanitizer runtime, which may be
    # exit 1 -- the same status a backend uses for "this file is invalid".
    # So decide from the report, not from the status code alone.
    if ! grep -qE "AddressSanitizer|LeakSanitizer|ThreadSanitizer|UndefinedBehaviorSanitizer|runtime error:" "$log" 2>/dev/null; then
        if [ $rc -eq 0 ] || [ $rc -eq 1 ] || [ $rc -eq 124 ] || [ $rc -eq 137 ]; then
            rm -f "$mut" "$log"
            return 0
        fi
    fi

    # sanitizer report, or a genuine signal (SIGSEGV/SIGABRT/...).
    local sig
    sig=$(python3 "$HERE/triage.py" "$log" 2>/dev/null)
    [ -n "$sig" ] || sig="unknown_rc${rc}"

    local dir="$OUT/crashes/$sig"
    mkdir -p "$dir"
    if [ ! -f "$dir/input.pdf" ]; then
        cp "$mut" "$dir/input.pdf"
        cp "$log" "$dir/report.txt"
        printf 'seed=%s iteration=%s rc=%s mutant=%s\n' \
            "$(basename "$seedfile")" "$idx" "$rc" "$(basename "$mut")" \
            > "$dir/meta.txt"
        echo "CRASH [$sig] -> $dir"
    else
        echo "dup   [$sig] ($(basename "$seedfile"))"
    fi
    echo "$mut" >> "$dir/duplicates.txt"
    rm -f "$log"
    return 0
}

export -f run_one
export SEED ITER TIMEOUT OUT BUILD ALLPAGES HERE SEED_DIR SEED_COUNT
export MODE RADAMSA_MUTATIONS EXTRA_FLAGS
export LD_LIBRARY_PATH ASAN_OPTIONS UBSAN_OPTIONS

echo "fuzzing $ITER iterations, seed base $SEED, $JOBS job(s), timeout ${TIMEOUT}s"
echo "crash dir: $OUT/crashes"

if [ "$JOBS" -gt 1 ] && command -v xargs >/dev/null; then
    seq 1 "$ITER" | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
else
    for i in $(seq 1 "$ITER"); do
        run_one "$i"
        if [ $KEEPGOING -eq 0 ]; then :; fi
    done
fi

echo
if [ -d "$OUT/crashes" ]; then
    for d in "$OUT"/crashes/*/; do
        [ -d "$d" ] || continue
        printf '%-40s %s\n' "$(basename "$d")" \
            "$(head -1 "$d/meta.txt" 2>/dev/null)"
    done
fi
