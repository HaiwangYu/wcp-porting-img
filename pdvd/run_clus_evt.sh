#!/bin/bash
# Run clustering for one event.
# Usage: ./run_clus_evt.sh [-a anode] <run> <evt> [subrun]
# Input:  work/<run>_<evt>/ (from imaging) or input_data event dir as fallback
# Output: work/<run>_<evt>/mabc-anode{N}.zip, mabc-all-apa.zip

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

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
    echo "Usage: $0 [-a anode] <run> <evt> [subrun]" >&2
    exit 1
fi
RUN=$1
EVT=$2
SUBRUN=${3:-0}

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
        if ls "$rdir/clusters-apa-anode"*"-ms-active.tar.gz" >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}"
mkdir -p "$WORKDIR"

# prefer work dir (post-imaging output), fall back to input_data
CLUS_INPUT=""
if ls "$WORKDIR/clusters-apa-anode"*"-ms-active.tar.gz" >/dev/null 2>&1; then
    CLUS_INPUT="$WORKDIR"
else
    EVTDIR=$(find_evtdir)
    if [ -n "$EVTDIR" ] && ls "$EVTDIR/clusters-apa-anode"*"-ms-active.tar.gz" >/dev/null 2>&1; then
        CLUS_INPUT="$EVTDIR"
    fi
fi

if [ -z "$CLUS_INPUT" ]; then
    echo "ERROR: no cluster tarballs found for run=$RUN evt=$EVT" >&2
    echo "  Tried: $WORKDIR and input_data/ event dirs" >&2
    exit 1
fi
echo "Cluster input: $CLUS_INPUT"
echo "Work dir:      $WORKDIR"

# Extract the art event number from the first available cluster tarball.
# e.g. cluster_339870_graph.json  →  339870
ANODE0_CLUS=$(ls "$CLUS_INPUT/clusters-apa-anode"*"-ms-active.tar.gz" 2>/dev/null | head -1)
EVENT_NO=$(tar tzf "$ANODE0_CLUS" | head -1 | sed -E 's/.*cluster_([0-9]+)_.*/\1/')
if ! echo "$EVENT_NO" | grep -qE '^[0-9]+$'; then
    echo "ERROR: could not parse event number from $ANODE0_CLUS (got: '$EVENT_NO')" >&2
    exit 1
fi
echo "Art event number: $EVENT_NO"

if [ -n "$ANODE" ]; then
    ANODE_CODE="[$ANODE]"
    TAG_SUFFIX="_a${ANODE}"
else
    ANODE_CODE="[0,1,2,3,4,5,6,7]"
    TAG_SUFFIX=""
fi

LOG="$WORKDIR/wct_clus_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.log"
echo "Log:           $LOG"

cd "$PDVD_DIR"
rm -f "$LOG"
wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str "input=${CLUS_INPUT}" \
    --tla-code "anode_indices=${ANODE_CODE}" \
    --tla-str "output_dir=${WORKDIR}" \
    --tla-code "run=${RUN_STRIPPED}" \
    --tla-code "subrun=${SUBRUN}" \
    --tla-code "event=${EVENT_NO}" \
    -c wct-clustering.jsonnet

echo "Clustering done -> $WORKDIR"
