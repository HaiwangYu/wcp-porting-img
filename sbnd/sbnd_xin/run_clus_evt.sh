#!/bin/bash
# Run SBND per-APA and all-APA blob clustering — standalone (no LArSoft).
# Usage: ./run_clus_evt.sh [-a anode] [-s sel_tag] <idx> [run] [subrun]
#   idx:   1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
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

SBND_EVENTS=(2 9 11 12 14 18 31 35 41 42)

lookup_evt_id() {
    local idx="$1"
    if ! echo "$idx" | grep -qE '^[0-9]+$' || [ "$idx" -lt 1 ] || [ "$idx" -gt 10 ]; then
        echo "ERROR: invalid event index '$idx' — must be 1..10" >&2
        for i in "${!SBND_EVENTS[@]}"; do echo "    $((i+1)) → ${SBND_EVENTS[$i]}" >&2; done
        exit 1
    fi
    echo "${SBND_EVENTS[$((idx-1))]}"
}

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

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-a anode] [-s sel_tag] <idx> [run] [subrun]" >&2
    exit 1
fi

IDX=$1
RUN=${2:-0}
SUBRUN=${3:-0}

EVT_ID=$(lookup_evt_id "$IDX")

if [ -n "$SEL_TAG" ]; then
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
else
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
fi

# Check that at least one input cluster file exists
if ! ls "$WORKDIR/icluster-apa"*"-active.npz" >/dev/null 2>&1; then
    echo "ERROR: no icluster-apa*-active.npz found in $WORKDIR" >&2
    echo "  Run: ./run_img_evt.sh $IDX" >&2
    exit 1
fi

if [ -n "$ANODE" ]; then
    ANODE_CODE="[$ANODE]"
    TAG_SUFFIX="_a${ANODE}"
else
    ANODE_CODE="[0,1]"
    TAG_SUFFIX=""
fi

mkdir -p "$WORKDIR"
LOG="$WORKDIR/wct_clus_evt${EVT_ID}${TAG_SUFFIX}.log"

echo "Event index:  $IDX → EVT_ID=$EVT_ID"
echo "Work dir:     $WORKDIR"
echo "Anodes:       $ANODE_CODE"
echo "RSE:          run=$RUN subrun=$SUBRUN event=$EVT_ID"
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
    --tla-code "run=${RUN}" \
    --tla-code "subrun=${SUBRUN}" \
    --tla-code "event=${EVT_ID}" \
    --tla-str  "reality=sim" \
    --tla-code "DL=6.2" \
    --tla-code "DT=9.8" \
    --tla-code "lifetime=10" \
    --tla-code "driftSpeed=1.565" \
    -c wct-clustering.jsonnet

echo "Clustering done -> $WORKDIR"
