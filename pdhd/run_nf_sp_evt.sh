#!/bin/bash
# Run standalone NF+SP for one event (no art/LArSoft).
# Usage: ./run_nf_sp_evt.sh [-a anode] [-g elecGain] [-r reality] [-d dump_root] <run> <evt|all>
#        ./run_nf_sp_evt.sh                # list available runs
#
# EVT may be 'all' to run every discovered event in parallel (capped at nproc,
# override with PDHD_MAX_JOBS=N).  Events with missing inputs are skipped.
#
#   -g elecGain   FE amplifier gain in mV/fC (default: 14).
#                 Use 7.8 for low-gain data.  Selects the matching noise
#                 spectrum file automatically (params.jsonnet:165-166).
#   -r reality    'data' (default) inserts the 512->500 ns Resampler before NF.
#                 'sim' skips it (input already at 500 ns).
#   -d dump_root  Enable PDHDCoherentNoiseSub debug dump (default: OFF).
#                 Per-group .npz files are written to
#                 <dump_root>/<RUN_PADDED>_<EVT>/apa<N>/.
#
# Input:  input_data/<run_dir>/<evt_dir>/protodunehd-orig-frames-anode{0..3}.tar.bz2
# Output: work/<RUN_PADDED>_<EVT>/protodunehd-sp-frames{,-raw}-anode{N}.tar.bz2

set -e

PDHD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$PDHD_DIR/_runlib.sh"

ANODE=""
ELEC_GAIN="14"
REALITY="data"
DUMP_ROOT=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        -g) ELEC_GAIN="$2"; shift 2 ;;
        -g*) ELEC_GAIN="${1#-g}"; shift ;;
        -r) REALITY="$2"; shift 2 ;;
        -r*) REALITY="${1#-r}"; shift ;;
        -d) DUMP_ROOT="$2"; shift 2 ;;
        -d*) DUMP_ROOT="${1#-d}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -eq 0 ]; then
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] [-g elecGain] [-r reality] <run> <evt|all>" >&2
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

process_event() {
    local RUN=$1 EVT=$2
    local RUN_STRIPPED RUN_PADDED EVTDIR WORKDIR ANODE_CODE TAG_SUFFIX LOG
    RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
    [ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
    RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

    EVTDIR=$(find_evtdir) || EVTDIR=""
    if [ -z "$EVTDIR" ]; then
        echo "[skip] run=$RUN evt=$EVT: no event dir found under input_data/" >&2
        return 2
    fi
    echo "Event dir: $EVTDIR"

    if ! ls "$EVTDIR/protodunehd-orig-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
        echo "[skip] run=$RUN evt=$EVT: no protodunehd-orig-frames-anode*.tar.bz2 in $EVTDIR" >&2
        return 2
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
    echo "Work dir:  $WORKDIR"
    echo "elecGain:  ${ELEC_GAIN} mV/fC"
    echo "reality:   ${REALITY}"
    echo "Log:       $LOG"

    cd "$PDHD_DIR"
    rm -f "$LOG"

    local DUMP_TLA=()
    if [ -n "$DUMP_ROOT" ]; then
        local DUMP_DIR_ABS
        case "$DUMP_ROOT" in
            /*) DUMP_DIR_ABS="$DUMP_ROOT" ;;
            *)  DUMP_DIR_ABS="$PDHD_DIR/$DUMP_ROOT" ;;
        esac
        DUMP_DIR_ABS="${DUMP_DIR_ABS}/${RUN_PADDED}_${EVT}"
        mkdir -p "$DUMP_DIR_ABS"
        DUMP_TLA=(--tla-str debug_dump_path="$DUMP_DIR_ABS")
        echo "Dump dir:  $DUMP_DIR_ABS"
    fi

    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        -V "elecGain=${ELEC_GAIN}" \
        --tla-str orig_prefix="${EVTDIR}/protodunehd-orig-frames" \
        --tla-str raw_prefix="${WORKDIR}/protodunehd-sp-frames-raw" \
        --tla-str sp_prefix="${WORKDIR}/protodunehd-sp-frames" \
        --tla-str reality="${REALITY}" \
        --tla-code anode_indices="${ANODE_CODE}" \
        "${DUMP_TLA[@]}" \
        -c wct-nf-sp.jsonnet

    echo "NF+SP done -> $WORKDIR"
}

mkdir -p "$PDHD_DIR/work"
if [ "$EVT" = "all" ]; then
    batch_init
    mapfile -t _events < <(discover_events "$RUN" "$RUN_PADDED")
    if [ ${#_events[@]} -eq 0 ]; then
        echo "no events found for run=$RUN under input_data/ or work/" >&2; exit 1
    fi
    echo "Found ${#_events[@]} event(s) for run=$RUN: ${_events[*]}"
    echo "Parallel jobs: $BATCH_MAX"
    for _e in "${_events[@]}"; do
        _blogfile="$PDHD_DIR/work/.batch_nfsp_${RUN_PADDED}_${_e}.log"
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
