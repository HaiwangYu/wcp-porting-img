#!/bin/bash
# Convert SBND imaging results to Bee JSON and upload.
# Usage: ./run_bee_img_evt.sh [-a anode] [-s sel_tag] <idx> [run] [subrun]
#   idx:   1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   run:   run number for bee RSE metadata (default 0)
#   subrun: subrun number (default 0)
#   -a:    restrict to one anode (0 or 1); default processes both
#   -s:    use work/evt<ID>_<SEL_TAG>/ as working directory
# Input:  work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-active.npz (from run_img_evt.sh)
# Output: upload_evt<ID>[_<SEL_TAG>][_a<N>].zip  (Bee upload created and submitted)

set -e

SBND_DIR=$(cd "$(dirname "$0")" && pwd)

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
    SEL_SUFFIX="_${SEL_TAG}"
else
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
    SEL_SUFFIX=""
fi

# Build list of anode_idx:path pairs
if [ -n "$ANODE" ]; then
    TAG_SUFFIX="_a${ANODE}"
    ANODE_PAIRS="${ANODE}:${WORKDIR}/icluster-apa${ANODE}-active.npz"
else
    TAG_SUFFIX=""
    ANODE_PAIRS=""
    for i in 0 1; do
        npz="$WORKDIR/icluster-apa${i}-active.npz"
        if [ -s "$npz" ]; then
            ANODE_PAIRS="$ANODE_PAIRS ${i}:${npz}"
        fi
    done
fi

if [ -z "$ANODE_PAIRS" ]; then
    echo "ERROR: no icluster-apa*-active.npz files found in $WORKDIR" >&2
    echo "  Run: ./run_img_evt.sh $IDX" >&2
    exit 1
fi

ZIPNAME="upload_evt${EVT_ID}${SEL_SUFFIX}${TAG_SUFFIX}.zip"

echo "Event index:  $IDX → EVT_ID=$EVT_ID"
echo "Work dir:     $WORKDIR"
echo "RSE:          run=$RUN subrun=$SUBRUN event=$EVT_ID"
echo "Anode pairs:  $ANODE_PAIRS"
echo "Output zip:   $SBND_DIR/$ZIPNAME"

cd "$SBND_DIR"
# shellcheck disable=SC2086
python wct-img-2-bee.py "$RUN" "$SUBRUN" "$EVT_ID" $ANODE_PAIRS

mv -f upload.zip "$ZIPNAME"
echo "Uploading $ZIPNAME ..."
./upload-to-bee.sh "$ZIPNAME"
