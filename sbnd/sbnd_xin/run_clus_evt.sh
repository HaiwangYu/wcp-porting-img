#!/bin/bash
# Run SBND per-APA and all-APA blob clustering — standalone (no LArSoft).
# Usage: ./run_clus_evt.sh [-a anode] [-s sel_tag] <idx|all> [run] [subrun]
#        ./run_clus_evt.sh       # list available events
#   idx:   1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   all:   process all 10 events in parallel (up to nproc jobs; override with SBND_MAX_JOBS=N)
#   run:   run number stored in bee RSE metadata (default 0)
#   subrun: subrun number (default 0)
#   -a:    restrict to one anode (0 or 1)
#   -s:    use work/evt<ID>_<SEL_TAG>/ as working directory
# Input:  work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-{active,masked}.npz (from run_img_evt.sh)
# Output: work/evt<ID>[_<SEL_TAG>]/mabc-<anode>-face0.zip, mabc-all-apa.zip

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
RUN=${2:-0}
SUBRUN=${3:-0}

# True if the .npz exists, is nonempty on disk, AND contains at least one array.
# A "no clusters" run still produces a 22-byte zip header (no .npy inside),
# which makes ClusterFileSource hit EOS at call=0 and stalls the all-apa
# PointTreeMerging fan-in (multiplicity expects every branch to deliver).
npz_has_content() {
    [ -s "$1" ] || return 1
    python3 -c "import numpy as np,sys; sys.exit(0 if len(np.load(sys.argv[1]).files)>0 else 1)" "$1" 2>/dev/null
}

process_event() {
    local IDX=$1
    local EVT_ID RUN_L SUBRUN_L WORKDIR
    local candidates KEEP ANODE_CODE TAG_SUFFIX LOG
    EVT_ID=$(lookup_evt_id "$IDX") || return 1
    RUN_L=${RUN:-0}
    SUBRUN_L=${SUBRUN:-0}

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
    else
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
    fi

    if [ -n "$ANODE" ]; then
        candidates=("$ANODE")
    else
        candidates=(0 1)
    fi

    KEEP=()
    for a in "${candidates[@]}"; do
        local npz="$WORKDIR/icluster-apa${a}-active.npz"
        if npz_has_content "$npz"; then
            KEEP+=("$a")
        else
            echo "WARNING: skipping anode $a — $npz is missing or has no active clusters" >&2
        fi
    done

    if [ ${#KEEP[@]} -eq 0 ]; then
        echo "[skip] idx=$IDX evt=$EVT_ID: no non-empty icluster-apa*-active.npz found in $WORKDIR" >&2
        echo "  Run: ./run_img_evt.sh $IDX" >&2
        return 2
    fi

    ANODE_CODE="[$(IFS=,; echo "${KEEP[*]}")]"
    if [ ${#KEEP[@]} -eq 1 ]; then
        TAG_SUFFIX="_a${KEEP[0]}"
    else
        TAG_SUFFIX=""
    fi

    mkdir -p "$WORKDIR"
    LOG="$WORKDIR/wct_clus_evt${EVT_ID}${TAG_SUFFIX}.log"

    echo "Event index:  $IDX → EVT_ID=$EVT_ID"
    echo "Work dir:     $WORKDIR"
    echo "Anodes:       $ANODE_CODE"
    echo "RSE:          run=$RUN_L subrun=$SUBRUN_L event=$EVT_ID"
    echo "Log:          $LOG"

    cd "$SBND_DIR"
    rm -f "$LOG"
    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        --tla-str  "input=${WORKDIR}" \
        --tla-code "anode_indices=${ANODE_CODE}" \
        --tla-str  "output_dir=${WORKDIR}" \
        --tla-code "run=${RUN_L}" \
        --tla-code "subrun=${SUBRUN_L}" \
        --tla-code "event=${EVT_ID}" \
        --tla-str  "reality=sim" \
        --tla-code "DL=6.2" \
        --tla-code "DT=9.8" \
        --tla-code "lifetime=10" \
        --tla-code "driftSpeed=1.565" \
        -c wct-clustering.jsonnet

    echo "Clustering done -> $WORKDIR"
}

mkdir -p "$SBND_DIR/work"
if [ "$IDX" = "all" ]; then
    batch_init
    echo "Found ${#SBND_EVENTS[@]} event(s). Parallel jobs: $BATCH_MAX"
    for _i in $(discover_event_indices); do
        _evtid="${SBND_EVENTS[$((_i-1))]}"
        _blogfile="$SBND_DIR/work/.batch_clus_evt${_evtid}.log"
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
