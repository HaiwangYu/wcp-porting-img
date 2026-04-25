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

# True if the .npz exists, is nonempty on disk, AND contains at least one
# array. A "no clusters" run produces a 22-byte zip header (no .npy inside),
# which makes ClusterFileSource hit EOS at call=0 and stalls the all-apa
# PointTreeMerging fan-in (multiplicity expects every branch to deliver).
npz_has_content() {
    [ -s "$1" ] || return 1
    python3 -c "import numpy as np,sys; sys.exit(0 if len(np.load(sys.argv[1]).files)>0 else 1)" "$1" 2>/dev/null
}

if [ -n "$ANODE" ]; then
    candidates=("$ANODE")
else
    candidates=(0 1)
fi

KEEP=()
for a in "${candidates[@]}"; do
    npz="$WORKDIR/icluster-apa${a}-active.npz"
    if npz_has_content "$npz"; then
        KEEP+=("$a")
    else
        echo "WARNING: skipping anode $a — $npz is missing or has no active clusters" >&2
    fi
done

if [ ${#KEEP[@]} -eq 0 ]; then
    echo "ERROR: no non-empty icluster-apa*-active.npz files found in $WORKDIR" >&2
    echo "  Run: ./run_img_evt.sh $IDX" >&2
    exit 1
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
