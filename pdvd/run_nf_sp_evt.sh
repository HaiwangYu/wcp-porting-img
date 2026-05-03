#!/bin/bash
# Run standalone NF+SP for one event (no art/LArSoft).
# Usage: ./run_nf_sp_evt.sh [-a anode] [-r reality] [-d dump_root] [-c calib_root] [-w wf_root] [-x] <run> <evt|all>
#        ./run_nf_sp_evt.sh              # list available runs
#
# EVT may be 'all' to run every discovered event in parallel (capped at nproc,
# override with PDVD_MAX_JOBS=N).  Events with missing inputs are skipped.
#
#   -r reality    'data' (default) inserts the 512->500 ns Resampler on the
#                 bottom anodes (n<4) before NF. 'sim' skips it.
#   -d dump_root  Enable PDVDCoherentNoiseSub debug dump (default: OFF).
#                 Per-group .npz files are written to
#                 <dump_root>/<RUN_PADDED>_<EVT>/apa<N>/.
#   L1SP defaults to dump (tagger-only) mode with calib NPZs under
#   work/<RUN>_<EVT>/l1sp_calib/.  -c overrides the dump dir; -w switches to
#   process mode + per-ROI waveform dump; -x disables L1SP entirely.
#   -c calib_root Override the L1SP calibration dump directory (still dump mode).
#                 Per-event NPZ files with per-ROI asymmetry quantities are
#                 written to <calib_root>/<RUN_PADDED>_<EVT>/.
#   -w wf_root    Switch L1SP to process mode and write per-triggered-ROI
#                 waveform NPZ files (raw/decon/lasso/smeared) to
#                 <wf_root>/<RUN_PADDED>_<EVT>/.  Requires kernels_file in
#                 cfg/pgrapher/experiment/protodunevd/sp.jsonnet to be populated.
#   -x            Disable L1SPFilterPD entirely (no node instantiated).
#
# Input:  input_data/<run_dir>/<evt_dir>/protodune-orig-frames-anode{0..7}.tar.bz2
# Output: work/<RUN_PADDED>_<EVT>/protodune-sp-frames{,-raw}-anode{N}.tar.bz2

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$PDVD_DIR/_runlib.sh"

usage() {
    cat <<'EOF'
Usage: ./run_nf_sp_evt.sh [options] <run> <evt|all>
       ./run_nf_sp_evt.sh          # list available runs

Options:
  -a <anode>      Anode index to process (default: all, i.e. 0-7).
                  Bottom CRP: 0-3; top CRP: 4-7.
  -r <reality>    'data' (default): inserts 512->500 ns Resampler on bottom
                  anodes (n<4) before NF. 'sim': skips Resampler.
  -d <dump_dir>   Enable PDVDCoherentNoiseSub debug dump (default: OFF).
                  Per-group .npz files are written to
                  <dump_dir>/<RUN_PADDED>_<EVT>/apa<N>/.
                  View with: cd nf_plot && ./serve_coherent_viewer.sh <dump_dir>

  L1SP defaults to dump (tagger-only) mode; calib NPZs land under
  work/<RUN>_<EVT>/l1sp_calib/.  Use the flags below to redirect or change
  the L1SP variant.  Precedence: -x > -w > -c > default.
  -c <calib_dir>  Override the L1SP calibration dump dir (still dump mode).
                  Per-event NPZ files with per-ROI asymmetry quantities are
                  written to <calib_dir>/<RUN_PADDED>_<EVT>/.
                  Load with: np.load('<calib_dir>/.../apa<N>_NNNN_IIII.npz')
  -w <wf_dir>     Switch L1SP to process mode and write per-triggered-ROI
                  waveform NPZ files (raw/decon/lasso/smeared) to
                  <wf_dir>/<RUN_PADDED>_<EVT>/.  Requires kernels_file
                  populated in cfg/pgrapher/experiment/protodunevd/sp.jsonnet.
                  View with: cd nf_plot && ./serve_l1sp_roi_viewer.sh <wf_dir>
  -x              Disable L1SPFilterPD entirely (no node instantiated).
  -h              Show this help message and exit.

EVT may be 'all' to run every discovered event in parallel
(capped at nproc; override with PDVD_MAX_JOBS=N).

Input:  input_data/<run_dir>/<evt_dir>/protodune-orig-frames-anode{0..7}.tar.bz2
Output: work/<RUN_PADDED>_<EVT>/protodune-sp-frames{,-raw}-anode{N}.tar.bz2
EOF
}

ANODE=""
REALITY="data"
DUMP_ROOT=""
CALIB_ROOT=""
WF_ROOT=""
L1SP_OFF=0
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        -r) REALITY="$2"; shift 2 ;;
        -r*) REALITY="${1#-r}"; shift ;;
        -d) DUMP_ROOT="$2"; shift 2 ;;
        -d*) DUMP_ROOT="${1#-d}"; shift ;;
        -c) CALIB_ROOT="$2"; shift 2 ;;
        -c*) CALIB_ROOT="${1#-c}"; shift ;;
        -w) WF_ROOT="$2"; shift 2 ;;
        -w*) WF_ROOT="${1#-w}"; shift ;;
        -x) L1SP_OFF=1; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -eq 0 ]; then
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] [-r reality] [-d dump_dir] [-c calib_dir] [-w wf_dir] [-x] <run> <evt|all>  (use -h for help)" >&2
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
    echo "reality:  $REALITY"
    echo "Log:      $LOG"

    cd "$PDVD_DIR"
    rm -f "$LOG"

    local DUMP_TLA=()
    if [ -n "$DUMP_ROOT" ]; then
        local DUMP_DIR_ABS
        case "$DUMP_ROOT" in
            /*) DUMP_DIR_ABS="$DUMP_ROOT" ;;
            *)  DUMP_DIR_ABS="$PDVD_DIR/$DUMP_ROOT" ;;
        esac
        DUMP_DIR_ABS="${DUMP_DIR_ABS}/${RUN_PADDED}_${EVT}"
        mkdir -p "$DUMP_DIR_ABS"
        DUMP_TLA=(--tla-str debug_dump_path="$DUMP_DIR_ABS")
        echo "Dump dir: $DUMP_DIR_ABS"
    fi

    # L1SP mode selection.  Precedence: -x > -w > -c > default (auto-dump).
    local L1SP_TLA=()
    if [ "$L1SP_OFF" -eq 1 ]; then
        L1SP_TLA=(--tla-str l1sp_pd_mode='')
        echo "L1SP:           OFF (no L1SPFilterPD node)"
    elif [ -n "$WF_ROOT" ]; then
        if [ -n "$CALIB_ROOT" ]; then
            echo "Note: -c (dump) and -w (process+wfdump) are mutually exclusive; -w wins." >&2
        fi
        local WF_DIR_ABS
        case "$WF_ROOT" in
            /*) WF_DIR_ABS="$WF_ROOT" ;;
            *)  WF_DIR_ABS="$PDVD_DIR/$WF_ROOT" ;;
        esac
        WF_DIR_ABS="${WF_DIR_ABS}/${RUN_PADDED}_${EVT}"
        mkdir -p "$WF_DIR_ABS"
        L1SP_TLA=(--tla-str l1sp_pd_mode=process
                  --tla-str l1sp_pd_wf_dump_path="$WF_DIR_ABS")
        echo "L1SP wf dir:    $WF_DIR_ABS  (mode=process)"
    else
        local CALIB_DIR_ABS
        if [ -n "$CALIB_ROOT" ]; then
            case "$CALIB_ROOT" in
                /*) CALIB_DIR_ABS="$CALIB_ROOT" ;;
                *)  CALIB_DIR_ABS="$PDVD_DIR/$CALIB_ROOT" ;;
            esac
            CALIB_DIR_ABS="${CALIB_DIR_ABS}/${RUN_PADDED}_${EVT}"
        else
            CALIB_DIR_ABS="${WORKDIR}/l1sp_calib"
        fi
        mkdir -p "$CALIB_DIR_ABS"
        L1SP_TLA=(--tla-str l1sp_pd_mode=dump
                  --tla-str l1sp_pd_dump_path="$CALIB_DIR_ABS")
        echo "L1SP calib dir: $CALIB_DIR_ABS  (mode=dump)"
    fi

    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        --tla-str orig_prefix="${EVTDIR}/protodune-orig-frames" \
        --tla-str raw_prefix="${WORKDIR}/protodune-sp-frames-raw" \
        --tla-str sp_prefix="${WORKDIR}/protodune-sp-frames" \
        --tla-str reality="${REALITY}" \
        --tla-code anode_indices="${ANODE_CODE}" \
        "${DUMP_TLA[@]}" \
        "${L1SP_TLA[@]}" \
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
