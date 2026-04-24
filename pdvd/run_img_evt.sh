#!/bin/bash
# Run imaging for one event.
# Usage: ./run_img_evt.sh [-I] [-a anode] [-s sel_tag] <run> <evt>
# Input:  work/<RUN_PADDED>_<EVT>/protodune-sp-frames-anode{0..7}.tar.bz2  (preferred)
#         input_data/<run_dir>/<evt_dir>/protodune-sp-frames-anode{0..7}.tar.bz2  (fallback)
#   -I:  force loading SP frames from input_data even if work dir has them
#   -s:  work/<RUN_PADDED>_<EVT>_sel<TAG>/input/ (from run_select_evt.sh)
# Output: work/<run>_<evt>[_sel<TAG>]/clusters-apa-anode{N}-ms-{active,masked}.tar.gz

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

ANODE=""
SEL_TAG=""
FORCE_INPUT_DATA=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -I) FORCE_INPUT_DATA=1; shift ;;
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-I] [-a anode] [-s sel_tag] <run> <evt>" >&2
    exit 1
fi
RUN=$1
EVT=$2

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
        # flat layout: SP frame files live directly in run root
        if ls "$rdir/protodune-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

if [ -n "$SEL_TAG" ]; then
    WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}"
    EVTDIR="$WORKDIR/input"
    if [ ! -d "$EVTDIR" ]; then
        echo "ERROR: selection dir not found: $EVTDIR" >&2
        echo "  Run: ./run_select_evt.sh $RUN $EVT $SEL_TAG" >&2
        exit 1
    fi
else
    EVTDIR=$(find_evtdir)
    if [ -z "$EVTDIR" ]; then
        echo "ERROR: cannot find event dir for run=$RUN evt=$EVT under $PDVD_DIR/input_data/" >&2
        exit 1
    fi
    WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}"
fi
echo "Event dir: $EVTDIR"

# Prefer SP frames produced locally in work dir; -I forces input_data.
if [ -z "$SEL_TAG" ] && [ -z "$FORCE_INPUT_DATA" ] && \
   ls "$WORKDIR/protodune-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
    SP_PREFIX="$WORKDIR/protodune-sp-frames"
else
    SP_PREFIX="$EVTDIR/protodune-sp-frames"
fi
echo "SP prefix: $SP_PREFIX"

if [ -n "$ANODE" ]; then
    ANODE_CODE="[$ANODE]"
    TAG_SUFFIX="_a${ANODE}"
else
    ANODE_CODE="[0,1,2,3,4,5,6,7]"
    TAG_SUFFIX=""
fi

mkdir -p "$WORKDIR"
LOG="$WORKDIR/wct_img_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.log"
echo "Work dir:  $WORKDIR"
echo "Log:       $LOG"

cd "$PDVD_DIR"
rm -f "$LOG"
wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str "input_prefix=${SP_PREFIX}" \
    --tla-code "anode_indices=${ANODE_CODE}" \
    --tla-str "output_dir=${WORKDIR}" \
    -c wct-img-all.jsonnet

echo "Imaging done -> $WORKDIR"
