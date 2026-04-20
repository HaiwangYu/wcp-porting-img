#!/bin/bash
# Run clustering for one event.
# Usage: ./run_clus_evt.sh <run> <evt>
# Input:  work/<run>_<evt>/ (from imaging) or input_data event dir as fallback
# Output: work/<run>_<evt>/mabc-anode{N}.zip, mabc-all-apa.zip

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xning/wirecell-working
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/dunereco/dunereco/DUNEWireCell/protodunevd:${WIRECELL_PATH}

if [ $# -lt 2 ]; then
    echo "Usage: $0 <run> <evt>" >&2
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

LOG="$WORKDIR/wct_clus_${RUN_PADDED}_${EVT}.log"
echo "Log:           $LOG"

cd "$PDVD_DIR"
rm -f "$LOG"
wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str "input=${CLUS_INPUT}" \
    --tla-code 'anode_indices=[0,1,2,3,4,5,6,7]' \
    --tla-str "output_dir=${WORKDIR}" \
    -c wct-clustering.jsonnet

echo "Clustering done -> $WORKDIR"
