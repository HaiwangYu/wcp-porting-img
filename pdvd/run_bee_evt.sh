#!/bin/bash
# Bee conversion + upload for one event.
# Usage: ./run_bee_evt.sh <run> <evt>
# Input:  work/<run>_<evt>/ (from imaging) or input_data event dir as fallback
# Output: upload_<run>_<evt>.zip  (Bee URL printed to stdout)

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

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

# prefer work dir (post-imaging), fall back to input_data
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
    exit 1
fi
echo "Cluster input: $CLUS_INPUT"

ZIPNAME="upload_${RUN_PADDED}_${EVT}.zip"

cd "$PDVD_DIR"
python wct-img-2-bee.py \
    "$CLUS_INPUT/clusters-apa-anode0-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode1-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode2-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode3-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode4-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode5-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode6-ms-active.tar.gz" \
    "$CLUS_INPUT/clusters-apa-anode7-ms-active.tar.gz"

# wct-img-2-bee.py writes upload.zip; rename to per-event name
mv -f upload.zip "$ZIPNAME"
echo "Uploading $ZIPNAME ..."
./upload-to-bee.sh "$ZIPNAME"
