#!/bin/bash
# Convert SBND SP frames for one event to per-anode Magnify ROOT files.
# Usage: ./run_sp_to_magnify_evt.sh [-s sel_tag] <idx|all> [run] [subrun]
#        ./run_sp_to_magnify_evt.sh       # list available events
#   idx:     1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   all:     process all 10 events in parallel (up to nproc jobs; override with SBND_MAX_JOBS=N)
#   run:     run number stored in ROOT Trun tree (default 0 for MC)
#   subrun:  subrun number (default 0)
#   -s:      use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2 (from run_select_evt.sh)
# Input:   input_files/2025f-mc-sp-frames.tar.bz2  (extracted to work/evt<ID>/ on first use)
# Output:  work/evt<ID>[_<SEL_TAG>]/magnify-evt<ID>-anode{0,1}.root
#           work/evt<ID>[_<SEL_TAG>]/sbnd-sp-frames-anode{0,1}.tar.bz2  (for run_select_evt.sh)

set -e

SBND_DIR=$(cd "$(dirname "$0")" && pwd)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$SBND_DIR/_runlib.sh"

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

if [ $# -eq 0 ]; then
    list_events; exit 0
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-s sel_tag] <idx|all> [run] [subrun]" >&2
    exit 1
fi

IDX=$1
RUN=${2:-0}
SUBRUN=${3:-0}

process_event() {
    local IDX=$1
    local EVT_ID RUN_L SUBRUN_L WORKDIR SP_ARCHIVE
    local SOURCE_TAR TMPDIR_EXTRACT OUTPUT_PREFIX LOG SP_FRAME_PREFIX
    EVT_ID=$(lookup_evt_id "$IDX") || return 1
    RUN_L=${RUN:-0}
    SUBRUN_L=${SUBRUN:-0}

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
        SP_ARCHIVE="$WORKDIR/input/sp-frames.tar.bz2"
        if [ ! -s "$SP_ARCHIVE" ]; then
            echo "[skip] idx=$IDX evt=$EVT_ID: selection archive not found: $SP_ARCHIVE" >&2
            echo "  Run: ./run_select_evt.sh $IDX $SEL_TAG" >&2
            return 2
        fi
    else
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
        SP_ARCHIVE="$WORKDIR/sp-frames.tar.bz2"
        # Extract per-event subset from shared input tarball on first use.
        if [ ! -s "$SP_ARCHIVE" ]; then
            SOURCE_TAR="$SBND_DIR/input_files/2025f-mc-sp-frames.tar.bz2"
            if [ ! -s "$SOURCE_TAR" ]; then
                echo "[skip] idx=$IDX evt=$EVT_ID: source tarball not found: $SOURCE_TAR" >&2
                return 2
            fi
            echo "Extracting event $EVT_ID from $SOURCE_TAR ..."
            mkdir -p "$WORKDIR"
            TMPDIR_EXTRACT=$(mktemp -d /home/xqian/tmp/sbnd_extract_XXXXXX)
            trap 'rm -rf "$TMPDIR_EXTRACT"' RETURN
            tar -xjf "$SOURCE_TAR" -C "$TMPDIR_EXTRACT" --wildcards "*_${EVT_ID}.npy"
            (cd "$TMPDIR_EXTRACT" && tar -cjf "$SP_ARCHIVE" *.npy)
            echo "  → $SP_ARCHIVE"
        else
            echo "SP archive already exists: $SP_ARCHIVE"
        fi
    fi

    mkdir -p "$WORKDIR"

    OUTPUT_PREFIX="$WORKDIR/magnify-evt${EVT_ID}"
    LOG="$WORKDIR/wct_magnify_evt${EVT_ID}.log"
    SP_FRAME_PREFIX="$WORKDIR/sbnd-sp-frames"

    echo "Event index:  $IDX → EVT_ID=$EVT_ID"
    echo "Work dir:     $WORKDIR"
    echo "Input:        $SP_ARCHIVE"
    echo "Output:       ${OUTPUT_PREFIX}-anode{0,1}.root"
    echo "              ${SP_FRAME_PREFIX}-anode{0,1}.tar.bz2"
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
        --tla-str  "sp_frame_prefix=${SP_FRAME_PREFIX}" \
        --tla-code "run=${RUN_L}" \
        --tla-code "subrun=${SUBRUN_L}" \
        --tla-code "event=${EVT_ID}" \
        -c wct-sp-to-magnify.jsonnet

    echo "Magnify done:"
    echo "  ${OUTPUT_PREFIX}-anode0.root"
    echo "  ${OUTPUT_PREFIX}-anode1.root"
    echo "SP frame archives (for woodpecker):"
    echo "  ${SP_FRAME_PREFIX}-anode0.tar.bz2"
    echo "  ${SP_FRAME_PREFIX}-anode1.tar.bz2"
}

mkdir -p "$SBND_DIR/work"
if [ "$IDX" = "all" ]; then
    batch_init
    echo "Found ${#SBND_EVENTS[@]} event(s). Parallel jobs: $BATCH_MAX"
    for _i in $(discover_event_indices); do
        _evtid="${SBND_EVENTS[$((_i-1))]}"
        _blogfile="$SBND_DIR/work/.batch_magnify_evt${_evtid}.log"
        batch_wait_slot
        ( process_event "$_i" ) > "$_blogfile" 2>&1 &
        BATCH_PIDS[$!]=$_i
        echo "  [start] idx=$_i evt=$_evtid  log: $_blogfile"
    done
    batch_drain
    batch_summary
    exit $?
else
    process_event "$IDX"
    exit $?
fi
