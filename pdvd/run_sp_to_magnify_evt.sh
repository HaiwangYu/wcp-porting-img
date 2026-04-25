#!/bin/bash
# Convert SP frame archives for one event to per-anode Magnify ROOT files.
# Usage: ./run_sp_to_magnify_evt.sh [-I] [-s sel_tag] <run> <evt|all> [subrun]
#        ./run_sp_to_magnify_evt.sh      # list available runs
#
# EVT may be 'all' to run every discovered event in parallel (capped at nproc,
# override with PDVD_MAX_JOBS=N).  Events with missing inputs are skipped.
#
# Input:  work/<RUN_PADDED>_<EVT>/protodune-sp-frames-anode{0..7}.tar.bz2  (preferred)
#         input_data/<run_dir>/<evt_dir>/protodune-sp-frames-anode{0..7}.tar.bz2  (fallback)
#   -I:  force loading SP/raw frames from input_data even if work dir has them
#   -s:  work/<RUN_PADDED>_<EVT>_sel<TAG>/input/ (from run_select_evt.sh)
# Orig frames (protodune-orig-frames-anode{N}.tar.bz2) are always sourced from
# input_data when present, producing hu/hv/hw_orig<N> histograms in Magnify.
# Output: work/<run>_<evt>[_sel<TAG>]/magnify-run<RUN>-evt<EVT>-anode<N>.root  (one per anode)

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$PDVD_DIR/_runlib.sh"

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

if [ $# -eq 0 ]; then
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-I] [-s sel_tag] <run> <evt|all> [subrun]" >&2
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

process_event() {
    local RUN=$1 EVT=$2
    local RUN_STRIPPED RUN_PADDED WORKDIR EVTDIR SP_DIR LOG
    local ANODE0_ARCHIVE EVENT_NO RAW_ARCHIVE RAW_DIR RAW_ARGS ORIG_ARCHIVE ORIG_ARGS
    RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
    [ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
    RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}"
        EVTDIR="$WORKDIR/input"
        if [ ! -d "$EVTDIR" ]; then
            echo "[skip] run=$RUN evt=$EVT: selection dir not found: $EVTDIR" >&2
            return 2
        fi
    else
        EVTDIR=$(find_evtdir) || EVTDIR=""
        if [ -z "$EVTDIR" ]; then
            echo "[skip] run=$RUN evt=$EVT: no event dir found under input_data/" >&2
            return 2
        fi
        WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}"
    fi
    echo "Event dir: $EVTDIR"

    if [ -z "$SEL_TAG" ] && [ -z "$FORCE_INPUT_DATA" ] && \
       ls "$WORKDIR/protodune-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
        SP_DIR="$WORKDIR"
    else
        SP_DIR="$EVTDIR"
    fi
    echo "SP frames from: $SP_DIR"

    ANODE0_ARCHIVE="$SP_DIR/protodune-sp-frames-anode0.tar.bz2"
    if [ ! -s "$ANODE0_ARCHIVE" ]; then
        echo "[skip] run=$RUN evt=$EVT: missing or empty $ANODE0_ARCHIVE" >&2
        return 2
    fi
    EVENT_NO=$(tar tjf "$ANODE0_ARCHIVE" | head -1 | sed -E 's/.*_([0-9]+)\.npy.*/\1/')
    if ! echo "$EVENT_NO" | grep -qE '^[0-9]+$'; then
        echo "ERROR: could not parse event number from $ANODE0_ARCHIVE (got: '$EVENT_NO')" >&2
        return 1
    fi
    echo "Art event number: $EVENT_NO"

    mkdir -p "$WORKDIR"
    echo "Work dir: $WORKDIR"

    cd "$PDVD_DIR"

    local PROCESSED=0 N OUTPUT
    for N in 0 1 2 3 4 5 6 7; do
        local f="$SP_DIR/protodune-sp-frames-anode${N}.tar.bz2"
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

        ORIG_ARCHIVE="$EVTDIR/protodune-orig-frames-anode${N}.tar.bz2"
        if [ -s "$ORIG_ARCHIVE" ]; then
            echo "    + orig: $ORIG_ARCHIVE"
            ORIG_ARGS="--tla-code include_orig=true --tla-str orig_input_prefix=${EVTDIR}/protodune-orig-frames"
        else
            ORIG_ARGS="--tla-code include_orig=false"
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
            ${ORIG_ARGS} \
            -c wct-sp-to-magnify.jsonnet

        echo "    done -> $OUTPUT"
        PROCESSED=$((PROCESSED + 1))
    done

    if [ "$PROCESSED" -eq 0 ]; then
        echo "[skip] run=$RUN evt=$EVT: no anode archives found in $EVTDIR" >&2
        return 2
    fi

    echo "Magnify done: $PROCESSED anode(s) written to $WORKDIR/"
}

mkdir -p "$PDVD_DIR/work"
if [ "$EVT" = "all" ]; then
    batch_init
    mapfile -t _events < <(discover_events "$RUN" "$RUN_PADDED")
    if [ ${#_events[@]} -eq 0 ]; then
        echo "no events found for run=$RUN under input_data/ or work/" >&2; exit 1
    fi
    echo "Found ${#_events[@]} event(s) for run=$RUN: ${_events[*]}"
    echo "Parallel jobs: $BATCH_MAX"
    for _e in "${_events[@]}"; do
        _blogfile="$PDVD_DIR/work/.batch_magnify_${RUN_PADDED}_${_e}.log"
        batch_wait_slot
        ( process_event "$RUN" "$_e" ) > "$_blogfile" 2>&1 &
        BATCH_PIDS[$!]=$_e
        echo "  [start] evt=$_e  log: $_blogfile"
    done
    batch_drain
    batch_summary
    exit $?
else
    ( process_event "$RUN" "$EVT" )
    exit $?
fi
