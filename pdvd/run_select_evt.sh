#!/bin/bash
# Select a region of interest from raw SP frame archives using the Woodpecker GUI.
# One GUI window opens per anode file found in the source event directory.
#
# Usage: ./run_select_evt.sh [-a anode] <run> <evt> <sel_tag>
#
# Input:  input_data/<run_dir>/<evt_dir>/protodune-sp-frames-anode<N>.tar.bz2
# Output: work/<RUN_PADDED>_<EVT>_sel<TAG>/input/
#             protodune-sp-frames-anode<N>.tar.bz2   (masked, zeros outside selection)
#             selection-anode<N>.json                (tick/channel sidecar)
#
# After selection, pass -s <TAG> to the pipeline scripts:
#   ./run_sp_to_magnify_evt.sh <run> <evt> -s <TAG>
#   ./run_img_evt.sh           <run> <evt> -s <TAG>
#   ./run_clus_evt.sh          <run> <evt> -s <TAG>
#   ./run_bee_img_evt.sh       <run> <evt> -s <TAG>

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

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

if [ $# -lt 3 ]; then
    echo "Usage: $0 [-a anode] <run> <evt> <sel_tag>" >&2
    echo "  sel_tag: short label for this selection (e.g. sel1, tight, track5)" >&2
    exit 1
fi
RUN=$1
EVT=$2
SEL_TAG=$3

RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
[ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

find_evtdir() {
    local base="$PDVD_DIR/input_data"
    for rname in "run${RUN}" "run${RUN_PADDED}" "run${RUN_STRIPPED}"; do
        local rdir="$base/$rname"
        [ -d "$rdir" ] || continue
        for ename in "evt${EVT}" "evt_${EVT}"; do
            local cand="$rdir/$ename"
            if [ -d "$cand" ] && [ -n "$(ls -A "$cand" 2>/dev/null)" ]; then
                echo "$cand"; return 0
            fi
        done
        if ls "$rdir/protodune-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

EVTDIR=$(find_evtdir)
if [ -z "$EVTDIR" ]; then
    echo "ERROR: cannot find event dir for run=$RUN evt=$EVT under $PDVD_DIR/input_data/" >&2
    exit 1
fi
echo "Source event dir: $EVTDIR"

SELDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}/input"
mkdir -p "$SELDIR"
echo "Selection output: $SELDIR"

# Find archives to select from; optionally restrict to one anode
if [ -n "$ANODE" ]; then
    ARCHIVES=("$EVTDIR/protodune-sp-frames-anode${ANODE}.tar.bz2")
else
    mapfile -t ARCHIVES < <(ls "$EVTDIR/protodune-sp-frames-anode"*.tar.bz2 2>/dev/null)
fi

if [ ${#ARCHIVES[@]} -eq 0 ]; then
    echo "ERROR: no protodune-sp-frames-anode*.tar.bz2 found in $EVTDIR" >&2
    exit 1
fi

echo "Found ${#ARCHIVES[@]} anode archive(s)."

# Use WebAgg backend (browser-based) when no working X display is available.
if ! xdpyinfo >/dev/null 2>&1; then
    export MPLBACKEND=WebAgg
    echo ""
    echo "No X display detected — using browser-based GUI (WebAgg)."
    echo "Once woodpecker prints its URL (e.g. http://127.0.0.1:8988),"
    echo "forward the port from your local machine:"
    echo "  ssh -L 8988:localhost:8988 $USER@$(hostname)"
    echo "then open http://127.0.0.1:8988 in your browser."
fi

echo ""
echo "GUI instructions (repeated for each anode):"
echo "  1. Drag vertically on any plane → tick range, press ENTER"
echo "  2. Drag horizontally on U plane → U channel range, press ENTER"
echo "  3. Drag horizontally on V plane → V channel range, press ENTER"
echo "  4. Drag horizontally on W plane → W channel range, press ENTER"
echo "  5. Click 'Save selection'"
echo ""

for archive in "${ARCHIVES[@]}"; do
    [ -s "$archive" ] || { echo "Skipping missing/empty: $archive"; continue; }
    echo "--- Opening GUI: $archive"
    woodpecker select "$archive" \
        --outdir "$SELDIR" \
        --prefix "protodune-sp-frames"
done

echo ""
echo "Selection complete -> $SELDIR"
echo ""
echo "Next steps:"
echo "  ./run_sp_to_magnify_evt.sh $RUN $EVT -s $SEL_TAG"
echo "  ./run_img_evt.sh           $RUN $EVT -s $SEL_TAG"
echo "  ./run_clus_evt.sh          $RUN $EVT -s $SEL_TAG"
echo "  ./run_bee_img_evt.sh       $RUN $EVT -s $SEL_TAG"
