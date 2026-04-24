#!/bin/bash
# Convert SP frame archives for one event to per-anode Magnify ROOT files.
# Usage: ./run_sp_to_magnify_evt.sh [-I] [-s sel_tag] <run> <evt> [subrun]
# Input:  work/<RUN_PADDED>_<EVT>/protodune-sp-frames-anode{0..7}.tar.bz2  (preferred)
#         input_data/<run_dir>/<evt_dir>/protodune-sp-frames-anode{0..7}.tar.bz2  (fallback)
#   -I:  force loading SP/raw frames from input_data even if work dir has them
#   -s:  work/<RUN_PADDED>_<EVT>_sel<TAG>/input/ (from run_select_evt.sh)
# Output: work/<run>_<evt>[_sel<TAG>]/magnify-run<RUN>-evt<EVT>-anode<N>.root  (one per anode)

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

SEL_TAG=""
FORCE_INPUT_DATA=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -I) FORCE_INPUT_DATA=1; shift ;;
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-I] [-s sel_tag] <run> <evt> [subrun]" >&2
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

# Prefer SP/raw frames produced locally in work dir; -I forces input_data.
if [ -z "$SEL_TAG" ] && [ -z "$FORCE_INPUT_DATA" ] && \
   ls "$WORKDIR/protodune-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
    SP_DIR="$WORKDIR"
else
    SP_DIR="$EVTDIR"
fi
echo "SP frames from: $SP_DIR"

# Extract the art event number from the anode0 archive filename suffix.
# e.g. frame_gauss0_339870.npy  →  339870
ANODE0_ARCHIVE="$SP_DIR/protodune-sp-frames-anode0.tar.bz2"
if [ ! -s "$ANODE0_ARCHIVE" ]; then
    echo "ERROR: missing or empty $ANODE0_ARCHIVE" >&2
    exit 1
fi
EVENT_NO=$(tar tjf "$ANODE0_ARCHIVE" | head -1 | sed -E 's/.*_([0-9]+)\.npy.*/\1/')
if ! echo "$EVENT_NO" | grep -qE '^[0-9]+$'; then
    echo "ERROR: could not parse event number from $ANODE0_ARCHIVE (got: '$EVENT_NO')" >&2
    exit 1
fi
echo "Art event number: $EVENT_NO"

mkdir -p "$WORKDIR"
echo "Work dir: $WORKDIR"

cd "$PDVD_DIR"

# Process each anode independently → one ROOT file per anode.
PROCESSED=0
for N in 0 1 2 3 4 5 6 7; do
    f="$SP_DIR/protodune-sp-frames-anode${N}.tar.bz2"
    if [ ! -s "$f" ]; then
        echo "Skipping anode ${N} (missing or empty $f)"
        continue
    fi

    OUTPUT="$WORKDIR/magnify-run${RUN_PADDED}-evt${EVT}-anode${N}.root"
    LOG="$WORKDIR/wct_magnify_${RUN_PADDED}_${EVT}_anode${N}.log"
    echo "--- Anode ${N}: $OUTPUT"
    rm -f "$LOG"

    if [ -z "$SEL_TAG" ] && [ -z "$FORCE_INPUT_DATA" ] && \
       [ -s "$WORKDIR/protodune-sp-frames-raw-anode${N}.tar.bz2" ]; then
        RAW_ARCHIVE="$WORKDIR/protodune-sp-frames-raw-anode${N}.tar.bz2"
    else
        RAW_ARCHIVE="$EVTDIR/protodune-sp-frames-raw-anode${N}.tar.bz2"
    fi
    if [ -s "$RAW_ARCHIVE" ]; then
        RAW_DIR=$(dirname "$RAW_ARCHIVE")
        echo "    + raw: $RAW_ARCHIVE"
        RAW_ARGS="--tla-code include_raw=true --tla-str raw_input_prefix=${RAW_DIR}/protodune-sp-frames-raw"
    else
        RAW_ARGS="--tla-code include_raw=false"
    fi

    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        --tla-str  "input_prefix=${SP_DIR}/protodune-sp-frames" \
        --tla-code "anode_indices=[${N}]" \
        --tla-str  "output_file=${OUTPUT}" \
        --tla-code "run=${RUN_STRIPPED}" \
        --tla-code "subrun=${SUBRUN}" \
        --tla-code "event=${EVENT_NO}" \
        ${RAW_ARGS} \
        -c wct-sp-to-magnify.jsonnet

    echo "    done -> $OUTPUT"
    PROCESSED=$((PROCESSED + 1))
done

if [ "$PROCESSED" -eq 0 ]; then
    echo "ERROR: no anode archives found in $EVTDIR" >&2
    exit 1
fi

echo "Magnify done: $PROCESSED anode(s) written to $WORKDIR/"
