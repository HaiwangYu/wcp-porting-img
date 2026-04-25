#!/bin/bash
# Shared helper library for sbnd_xin/run_*.sh scripts.
# Source after setting SBND_DIR:
#   . "$SBND_DIR/_runlib.sh"

SBND_EVENTS=(2 9 11 12 14 18 31 35 41 42)

# Print the 10 idx→EVT_ID mappings.  Called when the invoking script
# receives no positional arguments.
list_events() {
    echo "Available SBND events (1-based index → event ID):"
    for i in "${!SBND_EVENTS[@]}"; do
        printf '  idx %-3d → evt %d\n' "$((i+1))" "${SBND_EVENTS[$i]}"
    done
}

# Resolve a 1-based event index (1..10) to the real event ID.
# Echoes the ID on stdout; on bad input writes the table to stderr and
# returns 1 (callers should check $? or let set -e handle it).
lookup_evt_id() {
    local idx="$1"
    if ! echo "$idx" | grep -qE '^[0-9]+$' || [ "$idx" -lt 1 ] || [ "$idx" -gt 10 ]; then
        echo "ERROR: invalid event index '$idx' — must be 1..10" >&2
        for i in "${!SBND_EVENTS[@]}"; do
            printf '    %d → %d\n' "$((i+1))" "${SBND_EVENTS[$i]}" >&2
        done
        return 1
    fi
    echo "${SBND_EVENTS[$((idx-1))]}"
}

# Prints the full sequence of valid event indices (1..N), one per line.
discover_event_indices() {
    seq 1 "${#SBND_EVENTS[@]}"
}

# ── Batch parallel runner ─────────────────────────────────────────────────────
#
# Usage in each script:
#   batch_init
#   for idx in $(discover_event_indices); do
#       batch_wait_slot
#       ( process_event "$idx" ) > "$logfile" 2>&1 &
#       BATCH_PIDS[$!]=$idx
#   done
#   batch_drain
#   batch_summary; exit $?
#
# Concurrency cap: ${SBND_MAX_JOBS:-$(nproc)}.

batch_init() {
    BATCH_OK=0
    BATCH_FAIL=0
    BATCH_FAIL_LIST=()
    BATCH_MAX=${SBND_MAX_JOBS:-$(nproc)}
    declare -gA BATCH_PIDS=()
}

# Reap one finished background job; update BATCH_OK / BATCH_FAIL.
# Requires bash >= 5.1 for 'wait -n -p VARNAME'.
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
