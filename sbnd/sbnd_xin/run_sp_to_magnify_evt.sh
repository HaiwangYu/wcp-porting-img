#!/bin/bash
# Convert SBND SP frames for one event to per-anode Magnify ROOT files.
# Usage: ./run_sp_to_magnify_evt.sh [-s sel_tag] <idx|all> [run] [subrun]
#   idx:     1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   all:     process all 10 events in parallel (up to 24 simultaneous jobs)
#   run:     run number stored in ROOT Trun tree (default 0 for MC)
#   subrun:  subrun number (default 0)
#   -s:      use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2 (from run_select_evt.sh)
# Input:   input_files/2025f-mc-sp-frames.tar.bz2  (extracted to work/evt<ID>/ on first use)
# Output:  work/evt<ID>[_<SEL_TAG>]/magnify-evt<ID>-anode{0,1}.root
#           work/evt<ID>[_<SEL_TAG>]/sbnd-sp-frames-anode{0,1}.tar.bz2  (for run_select_evt.sh)

set -e

SBND_DIR=$(cd "$(dirname "$0")" && pwd)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

SBND_EVENTS=(2 9 11 12 14 18 31 35 41 42)

lookup_evt_id() {
    local idx="$1"
    if ! echo "$idx" | grep -qE '^[0-9]+$' || [ "$idx" -lt 1 ] || [ "$idx" -gt 10 ]; then
        echo "ERROR: invalid event index '$idx' — must be 1..10" >&2
        echo "  Index → Event ID mapping:" >&2
        for i in "${!SBND_EVENTS[@]}"; do
            echo "    $((i+1)) → ${SBND_EVENTS[$i]}" >&2
        done
        exit 1
    fi
    echo "${SBND_EVENTS[$((idx-1))]}"
}

SEL_TAG=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-s sel_tag] <idx|all> [run] [subrun]" >&2
    exit 1
fi

IDX=$1
RUN=${2:-0}
SUBRUN=${3:-0}

# --- "all" mode: launch every event index in parallel ---
if [ "$IDX" = "all" ]; then
    MAX_PARALLEL=24
    N=${#SBND_EVENTS[@]}
    pids=()
    idx_arr=()
    failed_idxs=()

    for ((i=1; i<=N; i++)); do
        # Throttle: wait for a slot when at the parallel limit
        while [ "${#pids[@]}" -ge "$MAX_PARALLEL" ]; do
            new_pids=(); new_idxs=()
            for j in "${!pids[@]}"; do
                if kill -0 "${pids[$j]}" 2>/dev/null; then
                    new_pids+=("${pids[$j]}"); new_idxs+=("${idx_arr[$j]}")
                else
                    wait "${pids[$j]}" || failed_idxs+=("${idx_arr[$j]}")
                fi
            done
            pids=("${new_pids[@]}"); idx_arr=("${new_idxs[@]}")
            [ "${#pids[@]}" -ge "$MAX_PARALLEL" ] && sleep 0.3
        done

        EVTID="${SBND_EVENTS[$((i-1))]}"
        LOG_ALL="$SBND_DIR/work/evt${EVTID}${SEL_TAG:+_${SEL_TAG}}/run_all.log"
        mkdir -p "$(dirname "$LOG_ALL")"
        echo "[all] Launching index $i → EVT_ID=$EVTID"
        if [ -n "$SEL_TAG" ]; then
            "$0" -s "$SEL_TAG" "$i" "$RUN" "$SUBRUN" >"$LOG_ALL" 2>&1 &
        else
            "$0" "$i" "$RUN" "$SUBRUN" >"$LOG_ALL" 2>&1 &
        fi
        pids+=($!); idx_arr+=("$i")
    done

    # Wait for all remaining jobs
    for j in "${!pids[@]}"; do
        wait "${pids[$j]}" || failed_idxs+=("${idx_arr[$j]}")
    done

    if [ "${#failed_idxs[@]}" -gt 0 ]; then
        echo "ERROR: Failed event indices: ${failed_idxs[*]}" >&2
        echo "  Check logs under work/evt<ID>/run_all.log" >&2
        exit 1
    fi
    echo "All $N events completed successfully."
    exit 0
fi
# --------------------------------------------------------

EVT_ID=$(lookup_evt_id "$IDX")

if [ -n "$SEL_TAG" ]; then
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
    SP_ARCHIVE="$WORKDIR/input/sp-frames.tar.bz2"
    if [ ! -s "$SP_ARCHIVE" ]; then
        echo "ERROR: selection archive not found: $SP_ARCHIVE" >&2
        echo "  Run: ./run_select_evt.sh $IDX $SEL_TAG" >&2
        exit 1
    fi
else
    WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
    SP_ARCHIVE="$WORKDIR/sp-frames.tar.bz2"
    # Extract per-event subset from shared input tarball on first use.
    if [ ! -s "$SP_ARCHIVE" ]; then
        SOURCE_TAR="$SBND_DIR/input_files/2025f-mc-sp-frames.tar.bz2"
        if [ ! -s "$SOURCE_TAR" ]; then
            echo "ERROR: source tarball not found: $SOURCE_TAR" >&2
            exit 1
        fi
        echo "Extracting event $EVT_ID from $SOURCE_TAR ..."
        mkdir -p "$WORKDIR"
        TMPDIR_EXTRACT=$(mktemp -d /home/xqian/tmp/sbnd_extract_XXXXXX)
        tar -xjf "$SOURCE_TAR" -C "$TMPDIR_EXTRACT" --wildcards "*_${EVT_ID}.npy"
        (cd "$TMPDIR_EXTRACT" && tar -cjf "$SP_ARCHIVE" *.npy)
        rm -rf "$TMPDIR_EXTRACT"
        echo "  → $SP_ARCHIVE"
    else
        echo "SP archive already exists: $SP_ARCHIVE"
    fi
fi

mkdir -p "$WORKDIR"

OUTPUT_PREFIX="$WORKDIR/magnify-evt${EVT_ID}"
LOG="$WORKDIR/wct_magnify_evt${EVT_ID}.log"

SP_FRAME_PREFIX="$WORKDIR/sbnd-sp-frames"

echo "Event index:  $IDX → EVT_ID=$EVT_ID"
echo "Work dir:     $WORKDIR"
echo "Input:        $SP_ARCHIVE"
echo "Output:       ${OUTPUT_PREFIX}-anode{0,1}.root"
echo "              ${SP_FRAME_PREFIX}-anode{0,1}.tar.bz2"
echo "Log:          $LOG"

cd "$SBND_DIR"
rm -f "$LOG"
wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str  "input=${SP_ARCHIVE}" \
    --tla-code "anode_indices=[0,1]" \
    --tla-str  "output_file_prefix=${OUTPUT_PREFIX}" \
    --tla-str  "sp_frame_prefix=${SP_FRAME_PREFIX}" \
    --tla-code "run=${RUN}" \
    --tla-code "subrun=${SUBRUN}" \
    --tla-code "event=${EVT_ID}" \
    -c wct-sp-to-magnify.jsonnet

echo "Magnify done:"
echo "  ${OUTPUT_PREFIX}-anode0.root"
echo "  ${OUTPUT_PREFIX}-anode1.root"
echo "SP frame archives (for woodpecker):"
echo "  ${SP_FRAME_PREFIX}-anode0.tar.bz2"
echo "  ${SP_FRAME_PREFIX}-anode1.tar.bz2"
