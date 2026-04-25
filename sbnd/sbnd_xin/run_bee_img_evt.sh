#!/bin/bash
# Convert SBND imaging results to Bee JSON and upload.
# Usage: ./run_bee_img_evt.sh [-a anode] [-s sel_tag] <idx|all> [run] [subrun]
#        ./run_bee_img_evt.sh       # list available events
#   idx:   1-based event index (1..10) — maps to event IDs: 2 9 11 12 14 18 31 35 41 42
#   all:   combine all events into one upload zip and do a single Bee upload
#   run:   run number for bee RSE metadata (default 0)
#   subrun: subrun number (default 0)
#   -a:    restrict to one anode (0 or 1); default processes both
#   -s:    use work/evt<ID>_<SEL_TAG>/ as working directory
# Input:  work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-active.npz (from run_img_evt.sh)
# Output (single-event): upload_evt<ID>[_<SEL_TAG>][_a<N>].zip  (Bee URL printed)
# Output (all):          upload-batch.zip  (one zip for all events, Bee URL printed)

set -e

SBND_DIR=$(cd "$(dirname "$0")" && pwd)

. "$SBND_DIR/_runlib.sh"

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

if [ $# -eq 0 ]; then
    list_events; exit 0
fi

IDX=$1
RUN=${2:-0}
SUBRUN=${3:-0}

# True if the .npz exists, is nonempty on disk, AND contains at least one array.
npz_has_content() {
    [ -s "$1" ] || return 1
    python3 -c "import numpy as np,sys; sys.exit(0 if len(np.load(sys.argv[1]).files)>0 else 1)" "$1" 2>/dev/null
}

# Geometry args for wirecell-img bee-blobs (must match wct-img-2-bee.py:anode_args).
bee_anode_args() {
    local idx=$1
    if [ "$idx" -eq 0 ]; then
        echo '--speed "-1.563*mm/us" --t0 "200*us" --x0 "-201.45*cm"'
    else
        echo '--speed "1.563*mm/us" --t0 "200*us" --x0 "201.45*cm"'
    fi
}

# ── Single-event path ─────────────────────────────────────────────────────────

if [ "$IDX" != "all" ]; then
    EVT_ID=$(lookup_evt_id "$IDX")

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}_${SEL_TAG}"
        SEL_SUFFIX="_${SEL_TAG}"
    else
        WORKDIR="$SBND_DIR/work/evt${EVT_ID}"
        SEL_SUFFIX=""
    fi

    # Build list of anode_idx:path pairs
    if [ -n "$ANODE" ]; then
        TAG_SUFFIX="_a${ANODE}"
        npz="$WORKDIR/icluster-apa${ANODE}-active.npz"
        if ! npz_has_content "$npz"; then
            echo "ERROR: $npz is missing or has no clusters" >&2
            echo "  Try widening the selection in run_select_evt.sh or the other anode." >&2
            exit 1
        fi
        ANODE_PAIRS="${ANODE}:${npz}"
    else
        TAG_SUFFIX=""
        ANODE_PAIRS=""
        for i in 0 1; do
            npz="$WORKDIR/icluster-apa${i}-active.npz"
            if npz_has_content "$npz"; then
                ANODE_PAIRS="$ANODE_PAIRS ${i}:${npz}"
            else
                echo "WARNING: skipping empty/missing $npz (no active clusters)"
            fi
        done
    fi

    if [ -z "$ANODE_PAIRS" ]; then
        echo "ERROR: no non-empty icluster-apa*-active.npz files found in $WORKDIR" >&2
        echo "  Run: ./run_img_evt.sh $IDX" >&2
        exit 1
    fi

    ZIPNAME="upload_evt${EVT_ID}${SEL_SUFFIX}${TAG_SUFFIX}.zip"

    echo "Event index:  $IDX → EVT_ID=$EVT_ID"
    echo "Work dir:     $WORKDIR"
    echo "RSE:          run=$RUN subrun=$SUBRUN event=$EVT_ID"
    echo "Anode pairs:  $ANODE_PAIRS"
    echo "Output zip:   $SBND_DIR/$ZIPNAME"

    cd "$SBND_DIR"
    # shellcheck disable=SC2086
    python wct-img-2-bee.py "$RUN" "$SUBRUN" "$EVT_ID" $ANODE_PAIRS
    mv -f upload.zip "$ZIPNAME"
    echo "Uploading $ZIPNAME ..."
    ./upload-to-bee.sh "$ZIPNAME"
    exit 0
fi

# ── EVT=all path: combine events into data/0, data/1, ..., single upload ─────
#
# Bee identifies events by the filename prefix (parse_pathname in
# wirecell/bee/data.py splits the stem on '-'), so files MUST be named
# <bee_idx>-apa<j>.json so distinct events don't collide on the server.
#
# Anode jobs per event run in parallel up to SBND_MAX_JOBS slots total.

batch_init
mapfile -t _all_idxs < <(discover_event_indices)
echo "Found ${#SBND_EVENTS[@]} event(s). Parallel jobs: $BATCH_MAX"

cd "$SBND_DIR"
rm -rf data
mkdir -p data

_bee_idx=0
for _i in "${_all_idxs[@]}"; do
    _evtid="${SBND_EVENTS[$((_i-1))]}"
    if [ -n "$SEL_TAG" ]; then
        _workdir="$SBND_DIR/work/evt${_evtid}_${SEL_TAG}"
    else
        _workdir="$SBND_DIR/work/evt${_evtid}"
    fi

    # Collect anode files that have actual content
    _anode_files=()
    for _j in 0 1; do
        _f="$_workdir/icluster-apa${_j}-active.npz"
        if npz_has_content "$_f"; then
            _anode_files+=("$_j:$_f")
        fi
    done

    if [ ${#_anode_files[@]} -eq 0 ]; then
        echo "[skip] idx=$_i evt=$_evtid: no non-empty icluster-apa*-active.npz in $_workdir" >&2
        BATCH_FAIL=$((BATCH_FAIL + 1))
        BATCH_FAIL_LIST+=("idx${_i}")
        continue
    fi

    echo "  [start] idx=$_i evt=$_evtid (bee index $_bee_idx)"
    mkdir -p "data/$_bee_idx"

    _anode_pids=()
    for _apf in "${_anode_files[@]}"; do
        _j="${_apf%%:*}"
        _f="${_apf#*:}"
        batch_wait_slot
        (
            _geo=$(bee_anode_args "$_j")
            eval wirecell-img bee-blobs \
                -g sbnd -s center \
                --rse "$RUN" "$SUBRUN" "$_evtid" \
                $_geo \
                -o "data/${_bee_idx}/${_bee_idx}-apa${_j}.json" \
                "$_f"
        ) &
        BATCH_PIDS[$!]="idx${_i}_apa${_j}"
        _anode_pids+=($!)
    done

    # Wait for this event's anode jobs before advancing the bee index
    for _pid in "${_anode_pids[@]}"; do
        if [ -n "${BATCH_PIDS[$_pid]+x}" ]; then
            wait "$_pid" && {
                BATCH_OK=$((BATCH_OK + 1))
                unset "BATCH_PIDS[$_pid]"
            } || {
                BATCH_FAIL=$((BATCH_FAIL + 1))
                BATCH_FAIL_LIST+=("${BATCH_PIDS[$_pid]}")
                unset "BATCH_PIDS[$_pid]"
            }
        fi
    done

    _bee_idx=$((_bee_idx + 1))
done

if [ "$_bee_idx" -eq 0 ]; then
    echo "ERROR: no events produced Bee data" >&2
    exit 1
fi

_zipname="upload-batch.zip"
rm -f "$_zipname"
zip -r "$_zipname" data
echo "Uploading $_zipname ($_bee_idx event(s)) ..."
./upload-to-bee.sh "$_zipname"

echo
echo "===== batch summary ====="
echo "  events in zip: $_bee_idx"
echo "  skipped:       $BATCH_FAIL"
[ "$BATCH_FAIL" -gt 0 ] && echo "  skipped events: ${BATCH_FAIL_LIST[*]}"
