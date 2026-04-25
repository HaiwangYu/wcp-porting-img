#!/bin/bash
# Bee conversion + upload for one event (or all events in a single combined zip).
# Usage: ./run_bee_img_evt.sh [-a anode] [-s sel_tag] <run> <evt|all> [subrun]
#        ./run_bee_img_evt.sh            # list available runs
#
# Single-event mode (EVT is a number):
#   Converts cluster tarballs to Bee JSON, zips, and uploads.
#   Output: upload_<run>_<evt>[_sel<TAG>].zip  (Bee URL printed to stdout)
#
# EVT='all' mode:
#   Finds every event for the run, converts each to data/<i>/ in parallel
#   (up to nproc jobs, override with PDVD_MAX_JOBS=N), then combines all
#   events into one upload zip and does a single Bee upload.
#   Output: upload-batch-run<RUN_PADDED>.zip
#   Note: --speed/--t0/--x0 constants below must match wct-img-2-bee.py.

set -e

PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

. "$PDVD_DIR/_runlib.sh"

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
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] [-s sel_tag] <run> <evt|all> [subrun]" >&2
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

# ── Single-event path (unchanged from original) ───────────────────────────────

if [ "$EVT" != "all" ]; then
    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}"
    else
        WORKDIR="$PDVD_DIR/work/${RUN_PADDED}_${EVT}"
    fi

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
    mv -f upload.zip "$ZIPNAME"
    echo "Uploading $ZIPNAME ..."
    ./upload-to-bee.sh "$ZIPNAME"
    exit 0
fi

# ── EVT=all path: combine events into data/0, data/1, ..., single upload ─────
#
# Each event occupies data/<i>/; anode tarballs within an event are processed
# in parallel (up to PDVD_MAX_JOBS).  After all events, zip and upload once.
#
# Speed/x0 geometry: anodes 0-3 bottom-drift, 4-7 top-drift.
# These values must stay in sync with wct-img-2-bee.py:anode_args().
bee_anode_args() {
    local idx=$1
    if [ "$idx" -le 3 ]; then
        echo '--speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm"'
    else
        echo '--speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm"'
    fi
}

batch_init
mapfile -t _all_events < <(discover_events "$RUN" "$RUN_PADDED")
if [ ${#_all_events[@]} -eq 0 ]; then
    echo "no events found for run=$RUN under input_data/ or work/" >&2; exit 1
fi
echo "Found ${#_all_events[@]} event(s) for run=$RUN: ${_all_events[*]}"
echo "Parallel jobs: $BATCH_MAX"

cd "$PDVD_DIR"
rm -rf data
mkdir -p data

_bee_idx=0
for _e in "${_all_events[@]}"; do
    # Locate cluster files for this event
    _workdir="$PDVD_DIR/work/${RUN_PADDED}_${_e}"
    _clus_input=""
    if ls "$_workdir/clusters-apa-anode"*"-ms-active.tar.gz" >/dev/null 2>&1; then
        _clus_input="$_workdir"
    else
        # Try input_data evt dirs
        for _rname in "run${RUN}" "run${RUN_PADDED}" "run${RUN_STRIPPED}"; do
            _rdir="$PDVD_DIR/input_data/$_rname"
            [ -d "$_rdir" ] || continue
            for _ename in "evt${_e}" "evt_${_e}"; do
                _cand="$_rdir/$_ename"
                if [ -d "$_cand" ] && \
                   ls "$_cand/clusters-apa-anode"*"-ms-active.tar.gz" >/dev/null 2>&1; then
                    _clus_input="$_cand"
                    break 2
                fi
            done
            if ls "$_rdir/clusters-apa-anode"*"-ms-active.tar.gz" >/dev/null 2>&1; then
                _clus_input="$_rdir"
                break
            fi
        done
    fi

    if [ -z "$_clus_input" ]; then
        echo "[skip] run=$RUN evt=$_e: no cluster tarballs found" >&2
        BATCH_FAIL=$((BATCH_FAIL + 1))
        BATCH_FAIL_LIST+=("$_e")
        continue
    fi

    _anode0_clus=$(ls "$_clus_input/clusters-apa-anode"*"-ms-active.tar.gz" 2>/dev/null | head -1)
    _event_no=$(tar tzf "$_anode0_clus" | head -1 | sed -E 's/.*cluster_([0-9]+)_.*/\1/')
    if ! echo "$_event_no" | grep -qE '^[0-9]+$'; then
        echo "[skip] run=$RUN evt=$_e: cannot parse event number from $_anode0_clus" >&2
        BATCH_FAIL=$((BATCH_FAIL + 1))
        BATCH_FAIL_LIST+=("$_e")
        continue
    fi

    echo "  [start] evt=$_e (bee index $_bee_idx)  art_event=$_event_no  clus: $_clus_input"
    mkdir -p "data/$_bee_idx"

    # Build bee-blobs for each anode in parallel.
    # Each anode writes to data/<bee_idx>/0-apa<j>.json — no filename collision.
    _anode_pids=()
    for _j in 0 1 2 3 4 5 6 7; do
        _f="$_clus_input/clusters-apa-anode${_j}-ms-active.tar.gz"
        [ -s "$_f" ] || continue
        batch_wait_slot
        (
            _geo_args=$(bee_anode_args "$_j")
            eval wirecell-img bee-blobs \
                -g protodunevd -s uniform -d 1 \
                --rse "$RUN_STRIPPED" "$SUBRUN" "$_event_no" \
                $_geo_args \
                -o "data/${_bee_idx}/0-apa${_j}.json" \
                "$_f"
        ) &
        BATCH_PIDS[$!]="evt${_e}_apa${_j}"
        _anode_pids+=($!)
    done
    # Wait for this event's anodes before moving to the next bee index.
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

_zipname="upload-batch-run${RUN_PADDED}.zip"
zip -r "$_zipname" data
echo "Uploading $_zipname ($_bee_idx event(s)) ..."
./upload-to-bee.sh "$_zipname"

echo
echo "===== batch summary ====="
echo "  events in zip: $_bee_idx"
echo "  skipped:       $BATCH_FAIL"
[ "$BATCH_FAIL" -gt 0 ] && echo "  skipped events: ${BATCH_FAIL_LIST[*]}"
