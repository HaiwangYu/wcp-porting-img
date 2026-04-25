#!/bin/bash
# Shared helper library for pdhd/run_*.sh scripts.
# Source after setting PDHD_DIR:
#   . "$PDHD_DIR/_runlib.sh"

# List runs found under input_data/.  Called when the invoking script
# receives no positional arguments.
list_runs() {
    local base="$PDHD_DIR/input_data"
    [ -d "$base" ] || { echo "no input_data/ under $PDHD_DIR" >&2; return 1; }
    echo "Available runs under $base:"
    local found=0 d name evts
    for d in "$base"/run*/; do
        [ -d "$d" ] || continue
        found=1
        name=$(basename "$d")
        evts=$(ls -d "$d"/evt_* 2>/dev/null | sed 's|.*/evt_||' | tr '\n' ' ')
        if [ -n "$evts" ]; then
            printf '  %-12s  events: %s\n' "$name" "$evts"
        else
            printf '  %-12s  (flat layout — specify event number explicitly)\n' "$name"
        fi
    done
    [ "$found" -eq 0 ] && echo "  (none found)"
    return 0
}

# Discover numeric event ids for a given run.  Searches:
#   input_data/run<N>/evt_*  (structured layout)
#   work/<RUN_PADDED>_<EVT>  (from prior processing steps)
# Prints unique ids one per line, sorted numerically.
# Args: run_as_given  run_padded
discover_events() {
    local run=$1 run_padded=$2
    local run_stripped
    run_stripped=$(echo "$run" | sed 's/^0*//')
    [ -z "$run_stripped" ] && run_stripped=0
    {
        local rname rdir
        for rname in "run${run}" "run${run_padded}" "run${run_stripped}"; do
            rdir="$PDHD_DIR/input_data/$rname"
            [ -d "$rdir" ] || continue
            ls -d "$rdir"/evt_* 2>/dev/null | sed 's|.*/evt_||'
        done
        # work/<RUN_PADDED>_<EVT> and work/<RUN_PADDED>_<EVT>_<tag>
        ls -d "$PDHD_DIR/work/${run_padded}_"* 2>/dev/null \
            | sed -E "s|.*/${run_padded}_([0-9]+).*|\1|"
    } | grep -E '^[0-9]+$' | sort -n -u
}

# ── Batch parallel runner ─────────────────────────────────────────────────────
#
# Usage in each script:
#   batch_init
#   for e in "${events[@]}"; do
#       batch_wait_slot
#       ( process_event "$RUN" "$e" ) > "$logfile" 2>&1 &
#       BATCH_PIDS[$!]=$e
#   done
#   batch_drain
#   batch_summary; exit $?
#
# Concurrency cap: ${PDHD_MAX_JOBS:-$(nproc)}.

batch_init() {
    BATCH_OK=0
    BATCH_FAIL=0
    BATCH_FAIL_LIST=()
    BATCH_MAX=${PDHD_MAX_JOBS:-$(nproc)}
    declare -gA BATCH_PIDS=()
}

# Reap one finished background job; update BATCH_OK / BATCH_FAIL.
# Requires bash >= 5.1 for 'wait -n -p VARNAME'.
# The &&/|| chain suppresses set -e when the reaped job exits non-zero.
_batch_reap_one() {
    local _pid _st
    wait -n -p _pid 2>/dev/null && _st=0 || _st=$?
    if [ "$_st" -eq 0 ]; then
        BATCH_OK=$((BATCH_OK + 1))
    else
        BATCH_FAIL=$((BATCH_FAIL + 1))
        BATCH_FAIL_LIST+=("${BATCH_PIDS[$_pid]:-pid:$_pid}")
    fi
    unset "BATCH_PIDS[$_pid]"
}

batch_wait_slot() {
    while [ "${#BATCH_PIDS[@]}" -ge "$BATCH_MAX" ]; do _batch_reap_one; done
}

batch_drain() {
    while [ "${#BATCH_PIDS[@]}" -gt 0 ]; do _batch_reap_one; done
}

# Print summary; returns 0 if at least one event succeeded, 1 otherwise.
batch_summary() {
    echo
    echo "===== batch summary ====="
    echo "  ok:      $BATCH_OK"
    echo "  failed:  $BATCH_FAIL"
    [ "$BATCH_FAIL" -gt 0 ] && echo "  failed events: ${BATCH_FAIL_LIST[*]}"
    [ "$BATCH_OK" -gt 0 ] && return 0 || return 1
}
