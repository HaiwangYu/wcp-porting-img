#!/bin/bash
# Run 3D imaging for one SBND event — standalone (no LArSoft).
# Usage: ./run_img_evt.sh [-a anode] [-s sel_tag] <idx>
#   idx:   1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   -a:    restrict to one anode (0 or 1); default processes both
#   -s:    use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2 (from run_select_evt.sh)
# Input:  work/evt<ID>[_<SEL_TAG>]/sp-frames.tar.bz2 (created by run_sp_to_magnify_evt.sh)
# Output: work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-{active,masked}.npz

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
    echo "Usage: $0 [-a anode] [-s sel_tag] <idx>" >&2
    exit 1
fi

IDX=$1
EVT_ID=$(lookup_evt_id "$IDX")

if [ -n "$SEL_TAG" ]; then
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
    SP_ARCHIVE="$WORKDIR/input/sp-frames.tar.bz2"
else
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
    SP_ARCHIVE="$WORKDIR/sp-frames.tar.bz2"
fi

if [ ! -s "$SP_ARCHIVE" ]; then
    echo "ERROR: SP archive not found: $SP_ARCHIVE" >&2
    echo "  Run: ./run_sp_to_magnify_evt.sh $IDX" >&2
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
