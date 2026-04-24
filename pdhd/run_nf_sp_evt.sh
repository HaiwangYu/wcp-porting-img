#!/bin/bash
# Run standalone NF+SP for one event (no art/LArSoft).
# Usage: ./run_nf_sp_evt.sh [-a anode] <run> <evt>
# Input:  input_data/<run_dir>/<evt_dir>/protodunehd-orig-frames-anode{0..3}.tar.bz2
# Output: work/<RUN_PADDED>_<EVT>/protodunehd-sp-frames{,-raw}-anode{N}.tar.bz2

set -e

PDHD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

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
    echo "Usage: $0 [-a anode] <run> <evt>" >&2
    exit 1
fi
RUN=$1
EVT=$2

RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
[ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

find_evtdir() {
    local base="$PDHD_DIR/input_data"
    for rname in "run${RUN}" "run${RUN_PADDED}" "run${RUN_STRIPPED}"; do
        local rdir="$base/$rname"
        [ -d "$rdir" ] || continue
        for ename in "evt${EVT}" "evt_${EVT}"; do
            local cand="$rdir/$ename"
            if [ -d "$cand" ] && [ -n "$(ls -A "$cand" 2>/dev/null)" ]; then
                echo "$cand"; return 0
            fi
        done
        if ls "$rdir/protodunehd-orig-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

EVTDIR=$(find_evtdir)
if [ -z "$EVTDIR" ]; then
    echo "ERROR: cannot find event dir for run=$RUN evt=$EVT under $PDHD_DIR/input_data/" >&2
    exit 1
fi
echo "Event dir: $EVTDIR"

if ! ls "$EVTDIR/protodunehd-orig-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
    echo "ERROR: no protodunehd-orig-frames-anode*.tar.bz2 found in $EVTDIR" >&2
    exit 1
fi

WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}"

if [ -n "$ANODE" ]; then
    ANODE_CODE="[$ANODE]"
    TAG_SUFFIX="_a${ANODE}"
else
    ANODE_CODE="[0,1,2,3]"
    TAG_SUFFIX=""
fi

mkdir -p "$WORKDIR"
LOG="$WORKDIR/wct_nfsp_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.log"
echo "Work dir: $WORKDIR"
echo "Log:      $LOG"

cd "$PDHD_DIR"
rm -f "$LOG"

wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str orig_prefix="${EVTDIR}/protodunehd-orig-frames" \
    --tla-str raw_prefix="${WORKDIR}/protodunehd-sp-frames-raw" \
    --tla-str sp_prefix="${WORKDIR}/protodunehd-sp-frames" \
    --tla-code anode_indices="${ANODE_CODE}" \
    -c wct-nf-sp.jsonnet

echo "NF+SP done -> $WORKDIR"
