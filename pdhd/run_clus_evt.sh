#!/bin/bash
# Run clustering for one event.
# Usage: ./run_clus_evt.sh [-a anode] [-s sel_tag] [-noq] <run> <evt|all> [subrun]
#        ./run_clus_evt.sh               # list available runs
#
# -save-pctree persists the post-Q/L point-cloud tree (pctree-evt<EVT>.tar.gz)
# that ./run_pr_evt.sh reloads for the PR / STM tagger tail.
#
# Q/L (charge-light) matching runs by DEFAULT; -noq (or PDHD_QLMATCH=0) disables it.
# An event with no converted light (opflash_pdhd-wct.tar.gz) auto-falls back to the
# no-matching chain, so 'evt all' never fails on a light-less event.
#
# EVT may be 'all' to run every discovered event in parallel (capped at nproc,
# override with PDHD_MAX_JOBS=N).  Events with missing inputs are skipped.
#   PDHD_CLUS_TLA="-S key=val ..."  extra wcsonnet args (knob overrides), e.g.
#     PDHD_CLUS_TLA="-S wrapped_channel_charge=true"  -- doc stm-tagger-chain
#     sec 12.  NOT production: it changes the pctree this job writes.
#
# Input:  work/<run>_<evt>[_sel<TAG>]/ (from imaging) or input_data event dir as fallback
# Output: work/<run>_<evt>[_sel<TAG>]/mabc-apa{N}.zip, mabc-all-apa.zip

set -e

PDHD_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

# Preload tcmalloc for the clustering wire-cell process (~20% faster on
# busy events).  Unlocked by the get_closest_blob pointer-order fix: with
# it, glibc and tcmalloc outputs are byte-identical on the A/B event set.
# Disable with WCT_TCMALLOC=off.
TCMALLOC_SO=/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4
WC_PRELOAD=""
if [ "${WCT_TCMALLOC:-on}" = "on" ] && [ -f "$TCMALLOC_SO" ]; then
    WC_PRELOAD="LD_PRELOAD=$TCMALLOC_SO"
fi

. "$PDHD_DIR/_runlib.sh"

ANODE=""
SEL_TAG=""
# Charge-light (Q/L) matching before the final all-TPC clustering: ON by default
# now that the PDHD light + matching chain is tuned (-noq or PDHD_QLMATCH=0 forces
# the historical no-matching chain).  Per-event, matching auto-disables when the
# converted light is absent (see QLMATCH_EVT below).
QLMATCH=${PDHD_QLMATCH:-1}
# -calib: also dump the per-drift-side Q/L hand-scan calibration JSONs
# (work/<run6>_<evt>/calib-evt<EVT>-group{02,13}.json) for the pdhd/ql_scan viewer.
# Implies Q/L matching; the matched mabc-*.zip output is byte-identical with/without it.
CALIB=0
OPDUMP=${PDHD_OPDUMP:-1}   # optical "op" bee instance (light + Q/L pred); default ON, -noop to disable
# -save-pctree: also persist the post-Q/L point-cloud tree
# (work/<run6>_<evt>/pctree-evt<EVT>.tar.gz) that run_pr_evt.sh reloads.  Off by
# default => the all-TPC TensorFileSink stays in dump_mode and the compiled
# config / mabc output are byte-identical.
SAVE_PCTREE=${PDHD_SAVE_PCTREE:-0}
# doc pdhd/06: record what clustering_isolated MERGED, so run_pr_evt.sh -unmerge
# can split it back.  Additive (three perblob arrays); cluster membership and
# every physics number are unchanged, but the PCTREE IS NOT BYTE-IDENTICAL --
# it gains the arrays -- so a -save-assoc pctree and a plain one are different
# files.  Default 0 => byte-identical compiled config and pctree.
# doc pdhd/11 sec 11 (owner flip 2026-09-07): default ON, because the PR chain now
# runs unmerge_assoc and that stage is SILENTLY INERT on a pctree written without
# the isolated-merge provenance.  PDVD flipped the same default 2026-09-04.
SAVE_ASSOC=${PDHD_SAVE_ASSOC:-1}
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -a) ANODE="$2"; shift 2 ;;
        -a*) ANODE="${1#-a}"; shift ;;
        # MUST precede the -s / -s* cases: '-save-pctree' starts with '-s' and the
        # -s* catch-all would swallow it as a selection tag "ave-pctree".
        -save-pctree|--save-pctree) SAVE_PCTREE=1; shift ;;
        # Also before -s / -s*: '-save-assoc' starts with '-s'.
        -save-assoc|--save-assoc) SAVE_ASSOC=1; shift ;;
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        -q) QLMATCH=1; shift ;;
        -noq|--no-qlmatch) QLMATCH=0; shift ;;
        -calib|--calib) CALIB=1; QLMATCH=1; shift ;;
        -op|--op) OPDUMP=1; QLMATCH=1; shift ;;
        -noop|--no-op) OPDUMP=0; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"

if [ $# -eq 0 ]; then
    list_runs; exit 0
fi

if [ $# -lt 2 ]; then
    echo "Usage: $0 [-a anode] [-s sel_tag] [-q] [-calib] [-noop] [-save-pctree] [-save-assoc] <run> <evt|all> [subrun]   (-q: Q/L matching; -calib: + hand-scan dumps; -save-pctree: persist the pctree for run_pr_evt.sh; -save-assoc: + the isolated-merge provenance run_pr_evt.sh -unmerge needs; optical bee instance ON by default, -noop to disable)" >&2
    exit 1
fi
RUN=$1
EVT=$2
SUBRUN=${3:-0}

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
        if ls "$rdir/clusters-apa-apa"*"-ms-active.tar.gz" >/dev/null 2>&1; then
            echo "$rdir"; return 0
        fi
    done
    return 1
}

process_event() {
    local RUN=$1 EVT=$2
    local RUN_STRIPPED RUN_PADDED WORKDIR EVTDIR CLUS_INPUT ANODE_CODE TAG_SUFFIX LOG
    local APA0_CLUS EVENT_NO
    RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//')
    [ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
    RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")

    if [ -n "$SEL_TAG" ]; then
        WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}_${SEL_TAG}"
    else
        WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}"
    fi
    mkdir -p "$WORKDIR"

    CLUS_INPUT=""
    if ls "$WORKDIR/clusters-apa-apa"*"-ms-active.tar.gz" >/dev/null 2>&1; then
        CLUS_INPUT="$WORKDIR"
    else
        EVTDIR=$(find_evtdir) || EVTDIR=""
        if [ -n "$EVTDIR" ] && ls "$EVTDIR/clusters-apa-apa"*"-ms-active.tar.gz" >/dev/null 2>&1; then
            CLUS_INPUT="$EVTDIR"
        fi
    fi

    if [ -z "$CLUS_INPUT" ]; then
        echo "[skip] run=$RUN evt=$EVT: no cluster tarballs found" >&2
        return 2
    fi
    echo "Cluster input: $CLUS_INPUT"
    echo "Work dir:      $WORKDIR"

    APA0_CLUS=$(ls "$CLUS_INPUT/clusters-apa-apa"*"-ms-active.tar.gz" 2>/dev/null | head -1)
    EVENT_NO=$(tar tzf "$APA0_CLUS" | head -1 | sed -E 's/.*cluster_([0-9]+)_.*/\1/')
    if ! echo "$EVENT_NO" | grep -qE '^[0-9]+$'; then
        echo "ERROR: could not parse event number from $APA0_CLUS (got: '$EVENT_NO')" >&2
        return 1
    fi
    echo "Art event number: $EVENT_NO"

    # Q/L matching is on by default but needs this event's converted light; if it
    # is absent fall back to the no-matching chain for THIS event only, so an
    # 'evt all' over a run with some light-less events doesn't fail.  Everything
    # below keys off the per-event QLMATCH_EVT rather than the global QLMATCH.
    local QLMATCH_EVT=$QLMATCH
    if [ "$QLMATCH_EVT" = 1 ] && [ ! -f "$CLUS_INPUT/opflash_pdhd-wct.tar.gz" ]; then
        echo "[note] no opflash_pdhd-wct.tar.gz in $CLUS_INPUT -> skipping Q/L matching for this event" >&2
        QLMATCH_EVT=0
    fi

    if [ -n "$ANODE" ]; then
        ANODE_CODE="[$ANODE]"
        TAG_SUFFIX="_a${ANODE}"
    else
        ANODE_CODE="[0,1,2,3]"
        TAG_SUFFIX=""
    fi

    LOG="$WORKDIR/wct_clus_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.log"
    echo "Log:           $LOG"

    cd "$PDHD_DIR"
    rm -f "$LOG"
    # Pre-compile the config with wcsonnet and feed wire-cell pure JSON,
    # with GOGC=off.  Rationale: an intermittent clustering SIGABRT was
    # identified as the embedded gojsonnet Go runtime GC crashing
    # ("traceback did not unwind completely").  libgojsonnet is hard-linked
    # so its runtime threads exist regardless of config format, but with a
    # pure-JSON config wire-cell never evaluates jsonnet (no Go heap) and
    # GOGC=off disables the Go collector entirely, including the 2-minute
    # periodic forced GC that is the crash vector.  Config is identical
    # (same pattern as imaging -P).
    # Per-event trigger offset for Q/L matching: read offset_us (~250) from the
    # converted opflash archive metadata and apply it DOWNSTREAM (matching geometry
    # + T0Correction x_t0cor).  Imaging stays offset-free (time_offset=0).  Stays 0
    # when not matching or when the archive/metadata is absent (bit-identical).
    TRIGGER_OFFSET_US=0
    if [ "$QLMATCH_EVT" = 1 ]; then
        OPFLASH_TAR="$CLUS_INPUT/opflash_pdhd-wct.tar.gz"
        if [ -f "$OPFLASH_TAR" ]; then
            TRIGGER_OFFSET_US=$(python3 - "$OPFLASH_TAR" <<'PY' || echo 0)
import sys, json, tarfile
off = 0.0
with tarfile.open(sys.argv[1]) as tf:
    for m in tf.getmembers():
        if m.name.endswith("_metadata.json"):
            md = json.loads(tf.extractfile(m).read())
            if "offset_us" in md:
                off = float(md["offset_us"])
                break
print(off)
PY
            echo "Trigger offset: ${TRIGGER_OFFSET_US} us (from $(basename "$OPFLASH_TAR"))"
            # Guard: charge and light are paired only by sharing this work dir,
            # nothing downstream checks it.  Both products independently carry the
            # DAQ/art event number (charge: cluster_<N>_ filename -> EVENT_NO;
            # light: opflash tensorset metadata 'event'), so assert they agree
            # before matching a flash to charge from a different event.
            OPFLASH_EVENT=$(python3 - "$OPFLASH_TAR" <<'PY' || echo "")
import sys, json, tarfile
with tarfile.open(sys.argv[1]) as tf:
    for m in tf.getmembers():
        if m.name.endswith("_metadata.json"):
            md = json.loads(tf.extractfile(m).read())
            if "event" in md:
                print(int(md["event"])); break
PY
            if [ -z "$OPFLASH_EVENT" ]; then
                echo "[warn] could not read event number from $(basename "$OPFLASH_TAR"); skipping charge/light event-number guard" >&2
            elif [ "$OPFLASH_EVENT" != "$EVENT_NO" ]; then
                echo "ERROR: charge/light event mismatch in $CLUS_INPUT: charge art_event=$EVENT_NO but opflash event=$OPFLASH_EVENT." >&2
                echo "       Refusing to Q/L-match charge and light from different events. Re-run light reco for this event (run_light_evt.sh -e $EVENT_NO ...)." >&2
                return 1
            fi
        else
            echo "[warn] $OPFLASH_TAR not found; trigger_offset_us=0" >&2
        fi
    fi

    # Post-resample readout-window length (ticks) for the Q/L window-truncation
    # flag.  Read the real SP frame length (~5999) from one SP frame archive so the
    # flag uses PDHD's true window rather than the C++ SBND default (3427, which
    # sits below the PDHD cathode and would falsely flag mid-drift clusters).
    # Falls back to 6000 (the jsonnet default) if no frame is found / unreadable.
    READOUT_NTICKS=6000
    if [ "$QLMATCH_EVT" = 1 ]; then
        _SPF=$(ls "$CLUS_INPUT"/protodunehd-sp-dnnroi-frames-anode*.tar.bz2 2>/dev/null | head -1)
        if [ -n "$_SPF" ]; then
            _NT=$(python3 - "$_SPF" <<'PY'
import sys, tarfile, io, numpy as np
with tarfile.open(sys.argv[1]) as tf:
    name = next(m.name for m in tf.getmembers() if m.name.startswith("frame_"))
    print(np.load(io.BytesIO(tf.extractfile(name).read())).shape[1])
PY
)
            READOUT_NTICKS=${_NT:-6000}
            echo "Readout window: ${READOUT_NTICKS} ticks (from $(basename "$_SPF"))"
        fi
    fi

    local PCTREE_OUT=""
    if [ "$SAVE_PCTREE" = 1 ]; then
        PCTREE_OUT="$WORKDIR/pctree-evt${EVENT_NO}.tar.gz"
        # TLA sidecar for run_pr_evt.sh: the PR job must rebuild DetectorVolumes
        # with EXACTLY the values this Q/L job used, or switch_scope re-derives
        # x_t0cor differently and the round-trip identity gate fails.  PDVD
        # parity (pdvd/run_clus_evt.sh), minus the per-crate drift speeds --
        # PDHD's single drift speed lives in params.jsonnet and is recorded here
        # only so a later change is visible in the sidecar diff.
        {
            echo "run=${RUN_STRIPPED}"
            echo "subrun=${SUBRUN}"
            echo "event=${EVENT_NO}"
            echo "trigger_offset_us=${TRIGGER_OFFSET_US:-0}"
            echo "time_offset=0"
            echo "readout_window_ticks=${READOUT_NTICKS:-6000}"
            echo "qlmatch=${QLMATCH_EVT}"
        } > "${WORKDIR}/pctree-evt${EVENT_NO}.tlas"
    fi

    local CFG_JSON="$WORKDIR/.wct-clus${TAG_SUFFIX}.json"
    wcsonnet \
        -A "input=${CLUS_INPUT}" \
        -S "anode_indices=${ANODE_CODE}" \
        -A "output_dir=${WORKDIR}" \
        -S "run=${RUN_STRIPPED}" \
        -S "subrun=${SUBRUN}" \
        -S "event=${EVENT_NO}" \
        -S "do_qlmatch=$([ "$QLMATCH_EVT" = 1 ] && echo true || echo false)" \
        -S "calib=$([ "$CALIB" = 1 ] && echo true || echo false)" \
        -S "save_opflash=$([ "$OPDUMP" = 1 ] && echo true || echo false)" \
        -S "trigger_offset_us=${TRIGGER_OFFSET_US}" \
        -S "readout_window_ticks=${READOUT_NTICKS}" \
        -A "save_tensors=${PCTREE_OUT}" \
        -S "clus_save_assoc_id=$([ "$SAVE_ASSOC" = 1 ] && echo true || echo false)" \
        ${PDHD_CLUS_TLA:-} \
        -o "$CFG_JSON" wct-clustering.jsonnet
    if [ ! -s "$CFG_JSON" ]; then
        echo "ERROR: wcsonnet failed to compile wct-clustering.jsonnet" >&2
        return 1
    fi
    # Geometry / drift provenance for the PR job's staleness guard, read out of
    # the COMPILED config so it can never disagree with what actually ran.
    if [ "$SAVE_PCTREE" = 1 ]; then
        python3 - "$CFG_JSON" >> "${WORKDIR}/pctree-evt${EVENT_NO}.tlas" <<'PYPROV'
import json, sys
cfg = json.load(open(sys.argv[1]))
wires = sorted({n["data"]["filename"] for n in cfg if n.get("type") == "WireSchemaFile"})
speeds = sorted({n["data"]["drift_speed"] for n in cfg
                 if n.get("type") == "BlobSampler" and "drift_speed" in n.get("data", {})})
print("wires=%s" % (wires[0] if wires else "unknown"))
# WCT internal units are mm and ns, so a speed is mm/ns: multiply by 1e3 for mm/us.
print("drift_speed_mmus=%s" % (("%.6g" % (speeds[0] * 1e3)) if speeds else "unknown"))
# doc pdhd/06: whether this pctree carries the isolated-merge provenance.  Read
# from the COMPILED config, so it cannot disagree with what actually ran, and
# read by run_pr_evt.sh -unmerge -- without it that visitor is silently inert.
print("save_assoc_id=%s" % ("true" if any(
    n.get("data", {}).get("save_assoc_cluster_id") for n in cfg
    if n.get("type") == "MultiAlgBlobClustering") else "false"))
PYPROV
    fi
    # Resource recording (additive; does not change reco output, disable with
    # PDHD_RESMON=off): run wire-cell in the background and sample its
    # /proc/<pid>/status every 2 s.  Writes a per-event summary
    # (clus_resource_<run>_<evt>.txt: wall_s + peak_rss_gb) and the full
    # RSS-vs-wallclock trace (clus_rss_<run>_<evt>.csv), whose timestamps align
    # with the debug-log stage markers so the peak can be attributed to a stage.
    local RES_TXT="$WORKDIR/clus_resource_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.txt"
    local RES_CSV="$WORKDIR/clus_rss_${RUN_PADDED}_${EVT}${TAG_SUFFIX}.csv"
    local _t0=$SECONDS _smpid=""
    env $WC_PRELOAD GOGC=off wire-cell \
        -l stderr \
        -l "${LOG}:debug" \
        -L debug \
        -c "$CFG_JSON" &
    local _wcpid=$!
    if [ "${PDHD_RESMON:-on}" != "off" ]; then
        echo "epoch_s,clock,vmrss_kb,vmhwm_kb" > "$RES_CSV"
        ( while kill -0 "$_wcpid" 2>/dev/null; do
            _line=$(awk '/^VmRSS:/{r=$2}/^VmHWM:/{h=$2}END{print r","h}' \
                    "/proc/$_wcpid/status" 2>/dev/null)
            [ -n "$_line" ] && echo "$(date +%s),$(date +%H:%M:%S.%2N),$_line" >> "$RES_CSV"
            sleep 2
          done ) &
        _smpid=$!
    fi
    local _rc=0
    wait "$_wcpid" || _rc=$?
    if [ -n "$_smpid" ]; then
        kill "$_smpid" 2>/dev/null || true
        wait "$_smpid" 2>/dev/null || true
    fi
    local _wall=$((SECONDS - _t0))
    local _peak_kb=0
    [ -f "$RES_CSV" ] && _peak_kb=$(awk -F, 'NR>1 && $4>m{m=$4}END{print m+0}' "$RES_CSV")
    awk -v r="$RUN_PADDED" -v e="$EVT" -v w="$_wall" -v p="$_peak_kb" \
        -v q="$QLMATCH_EVT" -v c="$CALIB" -v o="$OPDUMP" 'BEGIN{
        printf "run=%s evt=%s wall_s=%d peak_rss_gb=%.2f flags=q%s,calib%s,op%s\n",
               r,e,w,p/1048576,q,c,o}' | tee "$RES_TXT"
    if [ "$_rc" -ne 0 ]; then
        echo "ERROR: wire-cell exited with status $_rc" >&2
        return "$_rc"
    fi
    rm -f "$CFG_JSON"

    echo "Clustering done -> $WORKDIR"
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
        _blogfile="$PDHD_DIR/work/.batch_clus_${RUN_PADDED}_${_e}.log"
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
