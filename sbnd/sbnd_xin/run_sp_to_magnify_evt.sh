#!/bin/bash
# Convert SBND SP frames for one event to per-anode Magnify ROOT files.
# Usage: ./run_sp_to_magnify_evt.sh [-s sel_tag] <idx> [run] [subrun]
#   idx:     1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   run:     run number stored in ROOT Trun tree (default 0 for MC)
#   subrun:  subrun number (default 0)
#   -s:      use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2 (from run_select_evt.sh)
# Input:   input_files/2025f-mc-sp-frames.tar.bz2  (extracted to work/evt<ID>/ on first use)
# Output:  work/evt<ID>[_<SEL_TAG>]/magnify-evt<ID>-anode{0,1}.root

set -e

SBND_DIR=$(cd "$(dirname "$0")" && pwd)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

SBND_EVENTS=(2 9 11 12 14 18 31 35 41 42)

lookup_evt_id() {
    local idx="$1"
    if ! echo "$idx" | grep -qE '^[0-9]+$' || [ "$idx" -lt 1 ] || [ "$idx" -gt 10 ]; then
        echo "ERROR: invalid event index '$idx' — must be 1..10" >&2
        echo "  Index → Event ID mapping:" >&2
        for i in "${!SBND_EVENTS[@]}"; do
            echo "    $((i+1)) → ${SBND_EVENTS[$i]}" >&2
        done
        exit 1
    fi
    echo "${SBND_EVENTS[$((idx-1))]}"
}

SEL_TAG=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-s sel_tag] <idx> [run] [subrun]" >&2
    exit 1
fi

IDX=$1
RUN=${2:-0}
SUBRUN=${3:-0}

EVT_ID=$(lookup_evt_id "$IDX")

if [ -n "$SEL_TAG" ]; then
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
    SP_ARCHIVE="$WORKDIR/input/sp-frames.tar.bz2"
    if [ ! -s "$SP_ARCHIVE" ]; then
        echo "ERROR: selection archive not found: $SP_ARCHIVE" >&2
        echo "  Run: ./run_select_evt.sh $IDX $SEL_TAG" >&2
        exit 1
    fi
else
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
    SP_ARCHIVE="$WORKDIR/sp-frames.tar.bz2"
    # Extract per-event subset from shared input tarball on first use.
    if [ ! -s "$SP_ARCHIVE" ]; then
        SOURCE_TAR="$SBND_DIR/input_files/2025f-mc-sp-frames.tar.bz2"
        if [ ! -s "$SOURCE_TAR" ]; then
            echo "ERROR: source tarball not found: $SOURCE_TAR" >&2
            exit 1
        fi
        echo "Extracting event $EVT_ID from $SOURCE_TAR ..."
        mkdir -p "$WORKDIR"
        TMPDIR_EXTRACT=$(mktemp -d /home/xqian/tmp/sbnd_extract_XXXXXX)
        tar -xjf "$SOURCE_TAR" -C "$TMPDIR_EXTRACT" --wildcards "*_${EVT_ID}.npy"
        (cd "$TMPDIR_EXTRACT" && tar -cjf "$SP_ARCHIVE" *.npy)
        rm -rf "$TMPDIR_EXTRACT"
        echo "  → $SP_ARCHIVE"
    else
        echo "SP archive already exists: $SP_ARCHIVE"
    fi
fi

mkdir -p "$WORKDIR"

OUTPUT_PREFIX="$WORKDIR/magnify-evt${EVT_ID}"
LOG="$WORKDIR/wct_magnify_evt${EVT_ID}.log"

echo "Event index:  $IDX → EVT_ID=$EVT_ID"
echo "Work dir:     $WORKDIR"
echo "Input:        $SP_ARCHIVE"
echo "Output:       ${OUTPUT_PREFIX}-anode{0,1}.root"
echo "Log:          $LOG"

cd "$SBND_DIR"
rm -f "$LOG"
wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str  "input=${SP_ARCHIVE}" \
    --tla-code "anode_indices=[0,1]" \
    --tla-str  "output_file_prefix=${OUTPUT_PREFIX}" \
    --tla-code "run=${RUN}" \
    --tla-code "subrun=${SUBRUN}" \
    --tla-code "event=${EVT_ID}" \
    -c wct-sp-to-magnify.jsonnet

echo "Magnify done:"
echo "  ${OUTPUT_PREFIX}-anode0.root"
echo "  ${OUTPUT_PREFIX}-anode1.root"
