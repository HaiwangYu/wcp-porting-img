#!/bin/bash
# Select a region of interest from SBND SP frames using the Woodpecker GUI.
# Usage: ./run_select_evt.sh [-a anode] <idx> <sel_tag>
#   idx:     1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   sel_tag: short label for this selection (e.g. sel1, tight, track5)
#   -a:      restrict to one anode (0 or 1)
#
# Requires run_sp_to_magnify_evt.sh to have been run first (creates the per-event
# sp-frames.tar.bz2 in work/evt<ID>/).
#
# Output: work/evt<ID>_<SEL_TAG>/input/
#             sp-frames.tar.bz2   (masked, zeros outside selection)
#             selection.json      (tick/channel sidecar)
#
# After selection, pass -s <SEL_TAG> to the pipeline scripts:
#   ./run_sp_to_magnify_evt.sh <idx> -s <SEL_TAG>
#   ./run_img_evt.sh           <idx> -s <SEL_TAG>
#   ./run_clus_evt.sh          <idx> -s <SEL_TAG>
#   ./run_bee_img_evt.sh       <idx> -s <SEL_TAG>

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
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] <idx> <sel_tag>" >&2
    echo "  sel_tag: short label for this selection (e.g. sel1, tight, track5)" >&2
    exit 1
fi

IDX=$1
SEL_TAG=$2

EVT_ID=$(lookup_evt_id "$IDX")
WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
SP_ARCHIVE="$WORKDIR/sp-frames.tar.bz2"

if [ ! -s "$SP_ARCHIVE" ]; then
    echo "ERROR: SP archive not found: $SP_ARCHIVE" >&2
    echo "  Run: ./run_sp_to_magnify_evt.sh $IDX" >&2
    exit 1
fi

SELDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}/input"
mkdir -p "$SELDIR"

echo "Event index:     $IDX → EVT_ID=$EVT_ID"
echo "Source archive:  $SP_ARCHIVE"
echo "Selection output: $SELDIR"

export MPLBACKEND=WebAgg
echo ""
echo "Using browser-based GUI (WebAgg)."
echo "Once woodpecker prints its URL (e.g. http://127.0.0.1:8988),"
echo "forward the port from your local machine:"
echo "  ssh -L 8988:localhost:8988 $USER@$(hostname)"
echo "then open http://127.0.0.1:8988 in your browser."
echo ""
echo "GUI instructions:"
echo "  1. Drag vertically on any plane → tick range, press ENTER"
echo "  2. Drag horizontally on U plane → U channel range, press ENTER"
echo "  3. Drag horizontally on V plane → V channel range, press ENTER"
echo "  4. Drag horizontally on W plane → W channel range, press ENTER"
echo "  5. Click 'Save selection'"
echo ""

woodpecker select "$SP_ARCHIVE" \
    --outdir "$SELDIR" \
    --prefix "sp-frames"

echo ""
echo "Selection complete -> $SELDIR"
echo ""
echo "Next steps:"
echo "  ./run_sp_to_magnify_evt.sh $IDX -s $SEL_TAG"
echo "  ./run_img_evt.sh           $IDX -s $SEL_TAG"
echo "  ./run_clus_evt.sh          $IDX -s $SEL_TAG"
echo "  ./run_bee_img_evt.sh       $IDX -s $SEL_TAG"
