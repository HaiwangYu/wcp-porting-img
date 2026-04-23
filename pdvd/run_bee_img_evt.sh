#!/bin/bash
# Bee conversion + upload for one event.
# Usage: ./run_bee_img_evt.sh [-a anode] [-s sel_tag] <run> <evt> [subrun]
# Input:  work/<run>_<evt>[_sel<TAG>]/ (from imaging) or input_data event dir as fallback
# Output: upload_<run>_<evt>[_sel<TAG>].zip  (Bee URL printed to stdout)

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

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

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] [-s sel_tag] <run> <evt> [subrun]" >&2
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

if [ -n "$SEL_TAG" ]; then
    WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}"
else
    WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}"
fi

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
    TAG_SUFFIX="_a${ANODE}"
    ANODE_PAIRS="${ANODE}:${CLUS_INPUT}/clusters-apa-anode${ANODE}-ms-active.tar.gz"
else
    TAG_SUFFIX=""
    ANODE_PAIRS=""
    for i in 0 1 2 3 4 5 6 7; do
        ANODE_PAIRS="$ANODE_PAIRS ${i}:${CLUS_INPUT}/clusters-apa-anode${i}-ms-active.tar.gz"
    done
fi

SEL_SUFFIX="${SEL_TAG:+_${SEL_TAG}}"
ZIPNAME="upload_${RUN_PADDED}_${EVT}${SEL_SUFFIX}${TAG_SUFFIX}.zip"

cd "$PDVD_DIR"
# shellcheck disable=SC2086
python wct-img-2-bee.py "$RUN_STRIPPED" "$SUBRUN" "$EVENT_NO" $ANODE_PAIRS

# wct-img-2-bee.py writes upload.zip; rename to per-event name
mv -f upload.zip "$ZIPNAME"
echo "Uploading $ZIPNAME ..."
./upload-to-bee.sh "$ZIPNAME"
