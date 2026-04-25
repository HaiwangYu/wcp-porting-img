#!/bin/bash
# Run standalone NF+SP for one event (no art/LArSoft).
# Usage: ./run_nf_sp_evt.sh [-a anode] <run> <evt|all>
#        ./run_nf_sp_evt.sh              # list available runs
#
# EVT may be 'all' to run every discovered event in parallel (capped at nproc,
# override with PDVD_MAX_JOBS=N).  Events with missing inputs are skipped.
#
# Input:  input_data/<run_dir>/<evt_dir>/protodune-orig-frames-anode{0..7}.tar.bz2
# Output: work/<RUN_PADDED>_<EVT>/protodune-sp-frames{,-raw}-anode{N}.tar.bz2

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$PDVD_DIR/_runlib.sh"

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

if [ $# -eq 0 ]; then
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] <run> <evt|all>" >&2
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
        if ls "$rdir/protodune-orig-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

process_event() {
    local RUN=$1 EVT=$2
    local RUN_STRIPPED RUN_PADDED WORKDIR EVTDIR ANODE_CODE TAG_SUFFIX LOG
    RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
    [ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
    RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

    EVTDIR=$(find_evtdir) || EVTDIR=""
    if [ -z "$EVTDIR" ]; then
        echo "[skip] run=$RUN evt=$EVT: no event dir found under input_data/" >&2
        return 2
    fi
    echo "Event dir: $EVTDIR"

    if ! ls "$EVTDIR/protodune-orig-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
        echo "[skip] run=$RUN evt=$EVT: no protodune-orig-frames-anode*.tar.bz2 in $EVTDIR" >&2
        return 2
    fi

    WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}"

    if [ -n "$ANODE" ]; then
        ANODE_CODE="[$ANODE]"
        TAG_SUFFIX="_a${ANODE}"
    else
        ANODE_CODE="[0,1,2,3,4,5,6,7]"
        TAG_SUFFIX=""
    fi

    mkdir -p "$WORKDIR"
    LOG="$WORKDIR/wct_nfsp_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.log"
    echo "Work dir: $WORKDIR"
    echo "Log:      $LOG"

    cd "$PDVD_DIR"
    rm -f "$LOG"
    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        --tla-str orig_prefix="${EVTDIR}/protodune-orig-frames" \
        --tla-str raw_prefix="${WORKDIR}/protodune-sp-frames-raw" \
        --tla-str sp_prefix="${WORKDIR}/protodune-sp-frames" \
        --tla-str use_resampler="true" \
        --tla-code anode_indices="${ANODE_CODE}" \
        -c wct-nf-sp.jsonnet

    echo "NF+SP done -> $WORKDIR"
}

mkdir -p "$PDVD_DIR/work"
if [ "$EVT" = "all" ]; then
    batch_init
    mapfile -t _events < <(discover_events "$RUN" "$RUN_PADDED")
    if [ ${#_events[@]} -eq 0 ]; then
        echo "no events found for run=$RUN under input_data/" >&2; exit 1
    fi
    echo "Found ${#_events[@]} event(s) for run=$RUN: ${_events[*]}"
    echo "Parallel jobs: $BATCH_MAX"
    for _e in "${_events[@]}"; do
        _blogfile="$PDVD_DIR/work/.batch_nfsp_${RUN_PADDED}_${_e}.log"
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
