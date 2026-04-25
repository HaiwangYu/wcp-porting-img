#!/bin/bash
# Run 3D imaging for one SBND event — standalone (no LArSoft).
# Usage: ./run_img_evt.sh [-a anode] [-s sel_tag] <idx|all>
#        ./run_img_evt.sh       # list available events
#   idx:   1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   all:   process all 10 events in parallel (up to nproc jobs; override with SBND_MAX_JOBS=N)
#   -a:    restrict to one anode (0 or 1); default processes both
#   -s:    use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2 (from run_select_evt.sh)
# Input:  work/evt<ID>[_<SEL_TAG>]/sp-frames.tar.bz2 (created by run_sp_to_magnify_evt.sh)
# Output: work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-{active,masked}.npz

set -e

SBND_DIR=$(cd "$(dirname "$0")" && pwd)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$SBND_DIR/_runlib.sh"

ANODE=""
SEL_TAG=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -eq 0 ]; then
    list_events; exit 0
fi

IDX=$1

process_event() {
    local IDX=$1
    local EVT_ID WORKDIR SP_ARCHIVE ANODE_CODE TAG_SUFFIX LOG
    EVT_ID=$(lookup_evt_id "$IDX") || return 1

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
        SP_ARCHIVE="$WORKDIR/input/sp-frames.tar.bz2"
    else
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
        SP_ARCHIVE="$WORKDIR/sp-frames.tar.bz2"
    fi

    if [ ! -s "$SP_ARCHIVE" ]; then
        echo "[skip] idx=$IDX evt=$EVT_ID: SP archive not found: $SP_ARCHIVE" >&2
        echo "  Run: ./run_sp_to_magnify_evt.sh $IDX" >&2
        return 2
    fi

    if [ -n "$ANODE" ]; then
        ANODE_CODE="[$ANODE]"
        TAG_SUFFIX="_a${ANODE}"
    else
        ANODE_CODE="[0,1]"
        TAG_SUFFIX=""
    fi

    mkdir -p "$WORKDIR"
    LOG="$WORKDIR/wct_img_evt${EVT_ID}${TAG_SUFFIX}.log"

    echo "Event index:  $IDX → EVT_ID=$EVT_ID"
    echo "Work dir:     $WORKDIR"
    echo "Input:        $SP_ARCHIVE"
    echo "Anodes:       $ANODE_CODE"
    echo "Log:          $LOG"

    cd "$SBND_DIR"
    rm -f "$LOG"
    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        --tla-str  "input=${SP_ARCHIVE}" \
        --tla-code "anode_indices=${ANODE_CODE}" \
        --tla-str  "output_dir=${WORKDIR}" \
        -c wct-img-all.jsonnet

    echo "Imaging done -> $WORKDIR"
}

mkdir -p "$SBND_DIR/work"
if [ "$IDX" = "all" ]; then
    batch_init
    echo "Found ${#SBND_EVENTS[@]} event(s). Parallel jobs: $BATCH_MAX"
    for _i in $(discover_event_indices); do
        _evtid="${SBND_EVENTS[$((_i-1))]}"
        _blogfile="$SBND_DIR/work/.batch_img_evt${_evtid}.log"
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
