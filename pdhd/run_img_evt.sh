#!/bin/bash
# Run imaging for one event.
# Usage: ./run_img_evt.sh [-I] [-a anode] [-S] [-s sel_tag] <run> <evt|all>
#        ./run_img_evt.sh                # list available runs
#
# EVT may be 'all' to run every discovered event in parallel (capped at nproc,
# override with PDHD_MAX_JOBS=N).  Events with missing inputs are skipped.
#
# Input:  work/<RUN_PADDED>_<EVT>/protodunehd-sp-frames-anode{0..3}.tar.bz2  (preferred)
#         input_data/<run_dir>/<evt_dir>/protodunehd-sp-frames-anode{0..3}.tar.bz2  (fallback)
#   -I:  force loading SP frames from input_data even if work dir has them
#   By default the dense archive is used.  If the dense archive for an anode is
#   missing and a sparse variant (*-sparseon.tar.bz2) exists, the sparse variant
#   is used automatically as a fallback.
#   -S:  force-prefer the sparse variant for every anode that has one.
#   -s:  work/<RUN_PADDED>_<EVT>_sel<TAG>/input/ (from run_select_evt.sh)
# Output: work/<run>_<evt>[_sel<TAG>]/clusters-apa-apa{N}-ms-{active,masked}.tar.gz

set -e

PDHD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

. "$PDHD_DIR/_runlib.sh"

ANODE=""
SEL_TAG=""
FORCE_SPARSE=false
FORCE_INPUT_DATA=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -I) FORCE_INPUT_DATA=1; shift ;;
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        -S) FORCE_SPARSE=true; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -eq 0 ]; then
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-I] [-a anode] [-S] [-s sel_tag] <run> <evt|all>" >&2
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
        if ls "$rdir/protodunehd-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

process_event() {
    local RUN=$1 EVT=$2
    local RUN_STRIPPED RUN_PADDED EVTDIR WORKDIR
    local ANODE_CODE TAG_SUFFIX LOG INPUT_PREFIX NEED_STAGE STAGE_DIR ai dense sparse
    local -a ANODE_INDICES
    RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
    [ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
    RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}"
        EVTDIR="$WORKDIR/input"
        if [ ! -d "$EVTDIR" ]; then
            echo "[skip] run=$RUN evt=$EVT: selection dir not found: $EVTDIR" >&2
            return 2
        fi
    else
        EVTDIR=$(find_evtdir) || EVTDIR=""
        if [ -z "$EVTDIR" ]; then
            echo "[skip] run=$RUN evt=$EVT: no event dir under input_data/" >&2
            return 2
        fi
        WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}"
    fi
    echo "Event dir: $EVTDIR"

    if [ -n "$ANODE" ]; then
        ANODE_CODE="[$ANODE]"
        ANODE_INDICES=("$ANODE")
        TAG_SUFFIX="_a${ANODE}"
    else
        ANODE_CODE="[0,1,2,3]"
        ANODE_INDICES=(0 1 2 3)
        TAG_SUFFIX=""
    fi

    mkdir -p "$WORKDIR"

    # Prefer SP frames produced locally in work dir; -I forces input_data.
    if [ -z "$SEL_TAG" ] && [ -z "$FORCE_INPUT_DATA" ] && \
       ls "$WORKDIR/protodunehd-sp-frames-anode"*.tar.bz2 >/dev/null 2>&1; then
        INPUT_PREFIX="${WORKDIR}/protodunehd-sp-frames"
        echo "SP prefix: $INPUT_PREFIX"
    else
        # Determine per-anode archive: dense by default; sparse if forced (-S) or
        # dense is missing.  Stage symlinks only when at least one anode uses sparse
        # (sparse archive name differs from FrameFileSource's expected pattern).
        NEED_STAGE=false
        for ai in "${ANODE_INDICES[@]}"; do
            dense="${EVTDIR}/protodunehd-sp-frames-anode${ai}.tar.bz2"
            sparse="${EVTDIR}/protodunehd-sp-frames-anode${ai}-sparseon.tar.bz2"
            if $FORCE_SPARSE && [ -f "$sparse" ]; then
                NEED_STAGE=true; break
            elif [ ! -f "$dense" ] && [ -f "$sparse" ]; then
                NEED_STAGE=true; break
            fi
        done

        if $NEED_STAGE; then
            STAGE_DIR="${WORKDIR}/sp_stage"
            mkdir -p "$STAGE_DIR"
            for ai in "${ANODE_INDICES[@]}"; do
                dense="${EVTDIR}/protodunehd-sp-frames-anode${ai}.tar.bz2"
                sparse="${EVTDIR}/protodunehd-sp-frames-anode${ai}-sparseon.tar.bz2"
                if $FORCE_SPARSE && [ -f "$sparse" ]; then
                    ln -sf "$sparse" "${STAGE_DIR}/protodunehd-sp-frames-anode${ai}.tar.bz2"
                    echo "  anode${ai}: sparse (forced)"
                elif [ -f "$dense" ]; then
                    ln -sf "$dense" "${STAGE_DIR}/protodunehd-sp-frames-anode${ai}.tar.bz2"
                    echo "  anode${ai}: dense"
                elif [ -f "$sparse" ]; then
                    ln -sf "$sparse" "${STAGE_DIR}/protodunehd-sp-frames-anode${ai}.tar.bz2"
                    echo "  anode${ai}: sparse (dense not found)"
                else
                    echo "[skip] run=$RUN evt=$EVT: no archive for anode${ai} in $EVTDIR" >&2
                    return 2
                fi
            done
            INPUT_PREFIX="${STAGE_DIR}/protodunehd-sp-frames"
        else
            INPUT_PREFIX="${EVTDIR}/protodunehd-sp-frames"
        fi
    fi

    LOG="$WORKDIR/wct_img_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.log"
    echo "Work dir:  $WORKDIR"
    echo "Log:       $LOG"

    cd "$PDHD_DIR"
    rm -f "$LOG"
    wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        --tla-str "input_prefix=${INPUT_PREFIX}" \
        --tla-code "anode_indices=${ANODE_CODE}" \
        --tla-str "output_dir=${WORKDIR}" \
        -c wct-img-all.jsonnet

    echo "Imaging done -> $WORKDIR"
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
        _blogfile="$PDHD_DIR/work/.batch_img_${RUN_PADDED}_${_e}.log"
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
