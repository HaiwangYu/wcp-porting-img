#!/bin/bash
# Run the PDHD pattern-recognition (PR) tail for one event.
# Usage: ./run_pr_evt.sh [-s sel_tag] [-stm-fit] [-unmerge] [-stm|-nu|-nu-legacy|-empty] [-pipe a,b,c] <run> <evt|all> [subrun]
#
# Forked BY DUPLICATION from pdvd/run_pr_evt.sh; the PDVD script is untouched.
# See pdhd/docs/stm-tagger-chain.md and pdhd/docs/03_check-stm-michel-pdhd.md.
#
# DEFAULT MODE IS -stm: the chain stops after the cosmic taggers (PDHD
# production).  -nu appends the PR tail, which since doc pdhd/03 (owner
# 2026-09-05, counterpart of doc pdvd/48) is the STM + MICHEL stage
# (check_stm_michel): every STM-tagged main is re-fitted from its ENTRY point,
# walked to the Bragg stop, searched for a Michel e- (+ nearby dots), the
# particle flow is rooted at the entry, and a reject verdict is persisted
# (T_stm_michel in tracking-pr.root; 'CheckSTM_Michel: cluster' in the log).
# -nu-legacy runs the pre-doc-03 neutrino PR tail (tagger_check_neutrino +
# tagger_output), which was never graded on PDHD.
#
# Input : work/<RUN6>_<EVT>[_<TAG>]/pctree-evt<ID>.tar.gz + pctree-evt<ID>.tlas
#         (both written by run_clus_evt.sh -save-pctree; the .tlas sidecar carries
#         the trigger offset / readout window / wires file the Q/L job used, so
#         the PR job rebuilds DetectorVolumes identically).
# Output: work/<RUN6>_<EVT>[_<TAG>]/mabc-pr.zip            Bee: clustering + dead + stm_fit
#                                                          + stm/steiner_graph/steiner_terminals
#                                                          + stm_tagged (the STM verdict)
#                                                          + track_fit/shower_track/vertices/mc with -nu / -nu-legacy
#         work/<RUN6>_<EVT>[_<TAG>]/tracking-pr.root       PR fits (T_rec_charge) + T_stm_michel/T_stm_michel_pts (-nu);
#                                                          + T_tagger/T_kine with -nu-legacy
#         work/<RUN6>_<EVT>[_<TAG>]/calib-pr-evt<ID>.json  PrDisplayDump -- ONLY with -nu / -nu-legacy.
#           pr_display is in the -stm pipeline for PDVD parity but is INERT there:
#           it warns "no TrackFitting in grouping 'live'" and writes no file,
#           because the dump reads the fit TaggerCheckNeutrino builds.
#         work/<RUN6>_<EVT>[_<TAG>]/tracking-stm.root      STM fits (T_rec_charge/T_proj_data/
#                                                          T_stm_pass/T_stm_eval), with -stm-fit
#         work/<RUN6>_<EVT>[_<TAG>]/wct_pr_<RUN6>_<EVT>.log
# Verdicts: grep 'TaggerCheckSTM: cluster' / 'TaggerCheckTGM: cluster' in the log.
#
#   -stm     (default) switch_scope, flag_mains, steiner, fiducialutils,
#            tagger_check_tgm, tagger_check_stm, tagger_check_fc, protect_bundle,
#            steiner_refresh, pr_display
#   -nu      the above plus check_stm_michel, tracking_visitor (doc pdhd/03)
#   -nu-legacy  the above plus tagger_check_neutrino, tracking_visitor, tagger_output
#            (the pre-doc-03 tail; UNGRADED on PDHD; needs libpython only if
#            dl_weights is set, which it is not by default here)
#   -empty   pipeline_names=[] : the round-trip identity gate
#   -pipe    explicit comma-separated pipeline list
#   -stm-fit append stm_magnify (tracking-stm.root); save_stm_fit is ON by default
#            in wct-pr-perevt.jsonnet, this only adds the ROOT writer
#   PDHD_PR_TLA="-S key=val ..."   extra wcsonnet args (knob overrides)
#   PDHD_PR_COMPILE_ONLY=1         write the compiled JSON and stop
#   PDHD_KEEP_CFG=1                keep .wct-pr<TAG>.json
#   PDHD_MAX_JOBS=N                parallel cap for 'evt all' (default 6)
#   PDHD_PR_SKIP_DONE=1            resume a batch: skip events whose PR outputs exist
#   PDHD_ALLOW_STALE_GEOMETRY=1    downgrade the wires-file mismatch guard to a warning
#   PDHD_LOG_LEVEL=trace           file-sink level (default debug)
#   PDHD_RESMON=off                disable the RSS sampler
#   WCT_TCMALLOC=off               drop the tcmalloc preload
#   WCT_PYLIB=on                   preload libpython (only needed with dl_weights set)
set -o pipefail
PDHD_DIR=$(cd "$(dirname "$0")" && pwd)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH="$WCT_BASE/toolkit/cfg:$WCT_BASE/wire-cell-data${WIRECELL_PATH:+:$WIRECELL_PATH}"
_PRELOADS=""
if [ "${WCT_TCMALLOC:-on}" != "off" ] && [ -f /usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4 ]; then
    _PRELOADS="/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4"
fi
# The DL (SCN) vertex is OFF by default on PDHD (wct-pr-perevt.jsonnet
# dl_weights=''), so libpython is NOT preloaded by default.  Set WCT_PYLIB=on
# together with PDHD_PR_TLA="-A dl_weights=uboone/scn_vtx/...pth" to try it:
# without the preload the SCN import fails and TaggerCheckNeutrino silently
# falls back to the geometric vertex after one WARN ("DL vertex failed").
if [ "${WCT_PYLIB:-off}" != "off" ]; then
    PYLIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")/libpython3.11.so.1.0
    [ -r "$PYLIB" ] || { echo "ERROR: libpython not found: $PYLIB (WCT_PYLIB=off to skip)" >&2; exit 1; }
    _PRELOADS="${_PRELOADS:+$_PRELOADS:}$PYLIB"
fi
WC_PRELOAD="${_PRELOADS:+LD_PRELOAD=$_PRELOADS}"
# torch inside the SCN call would otherwise spawn a thread per core in every job
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1} MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
. "$PDHD_DIR/_runlib.sh"

SEL_TAG=""
MODE=stm    # cosmic taggers only, up to tagger_check_stm; -nu appends the PR tail
STM_FIT=0
UNMERGE=1   # doc pdhd/11 sec 11 (owner flip 2026-09-07): split back what
            # clustering_isolated merged.  PDVD has run this by default since
            # 2026-09-04 (doc pdvd/39 r2); -nounmerge restores the old chain.
PIPE_EXPLICIT=""
_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -stm-fit|--stm-fit) STM_FIT=1; shift ;;
        -unmerge|--unmerge) UNMERGE=1; shift ;;   # doc pdhd/06
        -nounmerge|--nounmerge) UNMERGE=0; shift ;;
        -stm) MODE=stm; shift ;;
        -nu) MODE=nu; shift ;;
        -nu-legacy) MODE=nulegacy; shift ;;   # doc pdhd/03: the pre-replacement neutrino PR tail
        -empty) MODE=empty; shift ;;
        -pipe) PIPE_EXPLICIT="$2"; shift 2 ;;
        -s) SEL_TAG="$2"; shift 2 ;;
        -s*) SEL_TAG="${1#-s}"; shift ;;
        *) _args+=("$1"); shift ;;
    esac
done
set -- "${_args[@]}"
if [ $# -lt 2 ]; then
    sed -n '2,32p' "$0"; echo; echo "Runs with pctree inputs:"; ls -d "$PDHD_DIR"/work/*/pctree-evt*.tar.gz 2>/dev/null | sed 's#.*/work/##' | head -20; exit 1
fi
RUN=$1; EVT=$2; SUBRUN_ARG=${3:-}

# PDHD pipelines.  unmerge_assoc is OFF BY DEFAULT and selected with -unmerge
# (doc pdhd/06).
#
# CORRECTION 2026-09-06: this comment used to read "unmerge_assoc is
# DELIBERATELY absent: PDHD's clustering runs no cm.isolated() merge ... so the
# stage would be inert".  The first clause is FALSE -- the compiled PDHD
# clustering config contains TWO live ClusteringIsolated instances (group02,
# group13), and cm.isolated() MERGES, not groups (clustering_isolated.cxx: the
# save_assoc_id knob gates only the RECORDING of what was merged, never the
# merge).  The conclusion "inert" happened to be right, for the other reason:
# PDHD never wrote the assoc_cluster_id/assoc_cluster_main provenance, so there
# was nothing for the visitor to undo.  That is now a knob:
# run_clus_evt.sh -save-assoc writes it, this -unmerge consumes it.
PIPE_STM="switch_scope,flag_mains,unmerge_assoc,steiner,fiducialutils,tagger_check_tgm,tagger_check_stm,tagger_check_fc,protect_bundle,steiner_refresh,pr_display"
# doc pdhd/03 (owner 2026-09-05): -nu runs the STM + Michel stage
# (check_stm_michel) in place of the neutrino PR tail; tagger_output is dropped
# with it (T_tagger/T_kine carried only neutrino BDT features).  pr_display is
# already in PIPE_STM (inert there; live here).  The legacy neutrino tail is
# preserved VERBATIM as PIPE_NU_LEGACY behind -nu-legacy for the A/B gates.
PIPE_NU="switch_scope,flag_mains,unmerge_assoc,steiner,fiducialutils,tagger_check_tgm,tagger_check_stm,tagger_check_fc,protect_bundle,steiner_refresh,check_stm_michel,tracking_visitor,pr_display"
PIPE_NU_LEGACY="$PIPE_STM,tagger_check_neutrino,tracking_visitor,tagger_output"
case "$MODE" in
    nu) PIPE="$PIPE_NU" ;;
    nulegacy) PIPE="$PIPE_NU_LEGACY" ;;
    stm) PIPE="$PIPE_STM" ;;
    empty) PIPE="" ;;
esac
[ -n "$PIPE_EXPLICIT" ] && PIPE="$PIPE_EXPLICIT"
# Position (PDVD parity, doc pdvd/39 sec 11): AFTER flag_mains and BEFORE
# steiner -- before steiner because separate() does not carry node-local PCs, so
# the split must precede steiner_pc creation; after flag_mains so the split-off
# fragments are removed from the main's Steiner build and STM fit WITHOUT being
# promoted to mains and given cosmic verdicts of their own.
if [ "$UNMERGE" = 1 ] && [ -n "$PIPE" ]; then
    case ",$PIPE," in
        *,unmerge_assoc,*) ;;
        *,flag_mains,*) PIPE="${PIPE/flag_mains,/flag_mains,unmerge_assoc,}" ;;
        *) echo "ERROR: -unmerge needs flag_mains in the pipeline (got '$PIPE')" >&2; exit 4 ;;
    esac
fi
if [ "$STM_FIT" = 1 ] && [ -n "$PIPE" ]; then PIPE="$PIPE,stm_magnify"; fi
PIPE_JSON="[$(echo "$PIPE" | sed -e 's/,/","/g' -e 's/^/"/' -e 's/$/"/' -e 's/^""$//')]"

process_event() {
    local RUN=$1 EVT=$2
    local RUN_STRIPPED=$((10#$RUN))
    local RUN_PADDED
    RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")
    local WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}${SEL_TAG:+_$SEL_TAG}"
    local PCTREE TLAS EVENT_NO
    PCTREE=$(ls "$WORKDIR"/pctree-evt*.tar.gz 2>/dev/null | head -1)
    if [ -z "$PCTREE" ]; then
        echo "[skip] run=$RUN evt=$EVT: no pctree-evt*.tar.gz in $WORKDIR (run_clus_evt.sh -save-pctree first)" >&2
        return 2
    fi
    EVENT_NO=$(basename "$PCTREE" | sed -E 's/pctree-evt([0-9]+)\.tar\.gz/\1/')
    TLAS="$WORKDIR/pctree-evt${EVENT_NO}.tlas"
    # PDHD_PR_SKIP_DONE=1: resume a batch -- skip an event whose PR outputs exist
    if [ "${PDHD_PR_SKIP_DONE:-0}" = 1 ] && [ -s "$WORKDIR/calib-pr-evt${EVENT_NO}.json" ] && [ -s "$WORKDIR/tracking-stm.root" ] && [ -s "$WORKDIR/mabc-pr.zip" ]; then
        echo "[skip-done] run=$RUN evt=$EVT: PR outputs present"
        return 0
    fi
    if [ ! -f "$TLAS" ]; then
        echo "ERROR: missing $TLAS (the Q/L job's TLA sidecar) -- rerun run_clus_evt.sh -save-pctree" >&2
        return 1
    fi
    local TRIG NT QL DS
    TRIG=$(awk -F= '$1=="trigger_offset_us"{print $2}' "$TLAS")
    NT=$(awk -F= '$1=="readout_window_ticks"{print $2}' "$TLAS")
    QL=$(awk -F= '$1=="qlmatch"{print $2}' "$TLAS")
    DS=$(awk -F= '$1=="drift_speed_mmus"{print $2}' "$TLAS")
    # subrun: the value the Q/L job stamped (sidecar) unless given on the command line
    local SUBRUN=${SUBRUN_ARG:-$(awk -F= '$1=="subrun"{print $2}' "$TLAS")}
    SUBRUN=${SUBRUN:-0}
    if [ "$QL" != 1 ]; then
        echo "[skip] run=$RUN evt=$EVT: the pctree was written WITHOUT Q/L matching (qlmatch=$QL); no matched bundles to tag" >&2
        return 2
    fi
    # doc pdhd/06: unmerge_assoc reads the assoc_cluster_id/assoc_cluster_main
    # perblob arrays.  On a pctree written without -save-assoc they are absent
    # and the visitor is SILENTLY INERT -- it cannot invent what was never
    # recorded, and the run looks like a normal one.  That silence is exactly
    # the failure this feature exists to fix, so refuse instead.  Keyed on the
    # selected PIPELINE, not on the -unmerge flag: if unmerge_assoc ever becomes
    # a default the flag stops being the thing that selects it.
    case ",$PIPE," in
        *,unmerge_assoc,*)
            local SA
            SA=$(awk -F= '$1=="save_assoc_id"{print $2}' "$TLAS")
            if [ "$SA" != "true" ]; then
                echo "ERROR: run=$RUN evt=$EVT: the pipeline contains unmerge_assoc but this pctree carries no isolated-merge provenance (save_assoc_id=${SA:-absent})." >&2
                echo "       Re-run clustering with: ./run_clus_evt.sh -q -save-pctree -save-assoc -s <tag> $RUN $EVT" >&2
                echo "       (or drop -unmerge; the visitor would be silently inert on this input)" >&2
                return 4
            fi ;;
    esac
    local TAG_SUFFIX=""
    local LOG="$WORKDIR/wct_pr_${RUN_PADDED}_${EVT}.log"
    local CFG_JSON="$WORKDIR/.wct-pr${SEL_TAG:+_$SEL_TAG}.json"
    rm -f "$LOG"   # spdlog appends; one run = one log
    echo "PR: run=$RUN evt=$EVT art_event=$EVENT_NO work=$WORKDIR pipeline=[$PIPE]"
    echo "    tlas: v=$DS mm/us trig=$TRIG us nticks=$NT"
    # shellcheck disable=SC2086
    (cd "$PDHD_DIR" && wcsonnet \
        -A "input=${PCTREE}" \
        -A "output_dir=${WORKDIR}" \
        -S "run=${RUN_STRIPPED}" \
        -S "subrun=${SUBRUN}" \
        -S "event=${EVENT_NO}" \
        -S "trigger_offset_us=${TRIG:-0}" \
        -S "readout_window_ticks=${NT:-6000}" \
        -S "pipeline_names=${PIPE_JSON}" \
        ${PDHD_PR_TLA:-} \
        -o "$CFG_JSON" wct-pr-perevt.jsonnet)
    if [ ! -s "$CFG_JSON" ]; then
        echo "ERROR: wcsonnet failed to compile wct-pr-perevt.jsonnet" >&2
        return 1
    fi
    # Drift-speed provenance guard (PDHD's analogue of the wires guard below).
    # PDHD's drift speed is not a TLA -- it is fixed in params.jsonnet -- so a
    # pctree written before a params.jsonnet edit would be re-scoped by
    # switch_scope at a DIFFERENT speed than it was sampled at, silently.
    local PR_DS
    PR_DS=$(python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); print("%.6g" % (next(n["data"]["drift_speed"] for n in c if n.get("type")=="BlobSampler" and "drift_speed" in n.get("data",{}))*1e3))' "$CFG_JSON" 2>/dev/null)
    if [ -n "$DS" ] && [ -n "$PR_DS" ] && [ "$DS" != "$PR_DS" ]; then
        if [ "${PDHD_ALLOW_STALE_GEOMETRY:-0}" = 1 ]; then
            echo "WARNING: pctree drift_speed=$DS mm/us but this PR job compiles $PR_DS (allowed by PDHD_ALLOW_STALE_GEOMETRY=1)" >&2
        else
            echo "ERROR: run=$RUN evt=$EVT: pctree was built at drift_speed=$DS mm/us but this PR job compiles $PR_DS -- params.jsonnet changed since the Q/L job; re-run run_clus_evt.sh -save-pctree (and re-derive pdhd_track_fitting.json add_sigma_L and the field), or set PDHD_ALLOW_STALE_GEOMETRY=1" >&2
            rm -f "$CFG_JSON"; return 3
        fi
    fi
    # Geometry provenance guard (PDVD doc pdvd/27).  The pctree's 3D points and face
    # ids were sampled with the Q/L job's wires file; the PR retile re-samples
    # the same blobs with THIS job's anodes.  v6 -> v7-uvwfit swapped the face
    # idents of anodes 2,3,6,7, so a v6 pctree under a v7 PR job moved every
    # retile on those anodes one face height in y (039349/53's "isolated piece"
    # 75 cm from its own track).  Refuse the mix; PDHD_ALLOW_STALE_GEOMETRY=1
    # downgrades to a warning; a pre-doc-27 sidecar (no wires= line) warns.
    local PR_WIRES TLA_WIRES
    PR_WIRES=$(python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); print(sorted({n["data"]["filename"] for n in c if n.get("type")=="WireSchemaFile"})[0])' "$CFG_JSON" 2>/dev/null)
    TLA_WIRES=$(awk -F= '$1=="wires"{print $2}' "$TLAS")
    if [ -z "$TLA_WIRES" ]; then
        echo "WARNING: $TLAS has no wires= line (no sidecar provenance): cannot prove the pctree was sampled with ${PR_WIRES:-?}; regenerate imaging + clustering if the wires file changed since" >&2
    elif [ "$TLA_WIRES" != "$PR_WIRES" ]; then
        if [ "${PDHD_ALLOW_STALE_GEOMETRY:-0}" = 1 ]; then
            echo "WARNING: pctree wires=$TLA_WIRES but this PR job compiles wires=$PR_WIRES (allowed by PDHD_ALLOW_STALE_GEOMETRY=1)" >&2
        else
            echo "ERROR: run=$RUN evt=$EVT: pctree was sampled with wires=$TLA_WIRES but this PR job compiles wires=$PR_WIRES -- regenerate imaging + clustering (run_img_evt.sh, run_clus_evt.sh -save-pctree) before PR, or set PDHD_ALLOW_STALE_GEOMETRY=1" >&2
            rm -f "$CFG_JSON"; return 3
        fi
    fi
    if [ "${PDHD_PR_COMPILE_ONLY:-0}" = 1 ]; then
        echo "[compile-only] wrote $CFG_JSON"
        return 0
    fi
    local RES_TXT="$WORKDIR/pr_resource_${RUN_PADDED}_${EVT}.txt"
    local RES_CSV="$WORKDIR/pr_rss_${RUN_PADDED}_${EVT}.csv"
    local _t0=$SECONDS _smpid=""
    # PDHD_LOG_LEVEL: file-sink level (default debug; 'trace' exposes the
    # CreateSteinerGraph / ImproveCluster / NeutrinoPattern phase timers, doc
    # pdvd/28).  PDHD_LOG_LOGGERS: the -L argument (default = the sink level;
    # e.g. 'clus:trace' restricts trace to the clus logger).
    env $WC_PRELOAD GOGC=off wire-cell \
        -l stderr \
        -l "${LOG}:${PDHD_LOG_LEVEL:-debug}" \
        -L "${PDHD_LOG_LOGGERS:-${PDHD_LOG_LEVEL:-debug}}" \
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
    awk -v r="$RUN_PADDED" -v e="$EVT" -v w="$_wall" -v p="$_peak_kb" -v m="$MODE" -v f="$STM_FIT" 'BEGIN{
        printf "run=%s evt=%s wall_s=%d peak_rss_gb=%.2f mode=%s stmfit=%s\n", r,e,w,p/1048576,m,f}' | tee "$RES_TXT"
    [ "${PDHD_KEEP_CFG:-0}" = 1 ] || rm -f "$CFG_JSON"
    if [ "$_rc" -ne 0 ]; then
        echo "ERROR: wire-cell PR failed (rc=$_rc) for run=$RUN evt=$EVT; see $LOG" >&2
        return "$_rc"
    fi
    local NSTM NTGM
    NSTM=$(grep -c 'TaggerCheckSTM: cluster' "$LOG" 2>/dev/null || true)
    NTGM=$(grep -c 'TaggerCheckTGM: cluster' "$LOG" 2>/dev/null || true)
    echo "PR done -> $WORKDIR  (STM verdict lines: $NSTM, TGM verdict lines: $NTGM)"
}

if [ "$EVT" = "all" ]; then
    RUN_PADDED=$(printf '%06d' "$((10#$RUN))")
    mapfile -t _events < <(ls -d "$PDHD_DIR"/work/${RUN_PADDED}_*${SEL_TAG:+_$SEL_TAG} 2>/dev/null \
             | sed -E "s#.*/${RUN_PADDED}_([0-9]+)${SEL_TAG:+_$SEL_TAG}\$#\1#" | grep -E '^[0-9]+$' | sort -n)
    if [ ${#_events[@]} -eq 0 ]; then
        echo "no work/${RUN_PADDED}_<idx>${SEL_TAG:+_$SEL_TAG} dirs" >&2; exit 1
    fi
    export PDHD_MAX_JOBS=${PDHD_MAX_JOBS:-6}
    batch_init
    echo "Found ${#_events[@]} event(s) for run=$RUN${SEL_TAG:+ tag=$SEL_TAG}: ${_events[*]}"
    echo "Parallel jobs: $BATCH_MAX"
    for _e in "${_events[@]}"; do
        _blogfile="$PDHD_DIR/work/.batch_pr_${RUN_PADDED}_${_e}${SEL_TAG:+_$SEL_TAG}.log"
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
