#!/bin/bash
# doc pr/11: batch driver for the FULL 13-stage SBND PR chain -- the one that
# is missing today.  Every existing runner (run_nusel_evt.sh, run_pr_evt.sh,
# run_full1k_nusel.sh) stops at tagger_check_fc; this one appends
# tagger_check_neutrino -> numu_bdt_scorer -> nue_bdt_scorer -> tracking_visitor
# -> tagger_output, so it is the first driver that can produce numu_score /
# nue_score / T_kine at population scale.
#
# Runs on an EXISTING Q/L pctree root (never re-runs Q/L or imaging -- CLAUDE.md
# M11): fork-by-duplication of run_nusel_evt.sh's process_event() (M10 -- that
# production script stays byte-untouched), with:
#   - the DL (SCN) neutrino vertex ON (the production default since e3d46c91;
#     no dl_weights override, unlike run_nusel_evt.sh which always forces
#     geometric).  Needs libpython RTLD_GLOBAL preloaded or the SCN import
#     fails and the DL vertex SILENTLY falls back to geometric (a WARN
#     "DL vertex failed: ..." is the only sign -- checked per event, see below).
#   - OMP_NUM_THREADS=MKL_NUM_THREADS=1: the DL inference is multithreaded: a
#     30-event probe showed 5.7s wall / 5.6s core pinned vs 5.3s wall / 9.5s
#     core unpinned on the same event.  Pinned so wall time is a comparable
#     single-thread latency number across every event and arm.
#   - -stm-fit (stm_magnify / tracking-stm.root) is OMITTED: doc pr/3 confirms
#     save_stm_fit only gates a diagnostic dump, never the STM verdict itself,
#     and skipping it avoids a second UPDATE-mode ROOT writer per event.
#   - RSE (run/subrun/event) is read from the Q/L job's own opflash metadata
#     (opflash_tensorset_<EVT>_metadata.json), exactly like run_nusel_evt.sh --
#     no external per-sample RSE file needed, and it is correct even for
#     samples spanning multiple runs (nueCC48) or reusing event numbers across
#     samples (MC evt 12 appears in both round1-qlmatch and round2-patrec).
#
# Usage:
#   ./run_pr_chain_batch.sh <ql_root> <out_root> <data|sim> [evt ...]
#     ql_root   dir containing ql_evt<ID>/{pctree-evt<ID>.tar.gz,
#               opflash_apa0.tar.gz, mabc-all-apa.zip} -- e.g. work-mcp1kall-d59k
#     out_root  FRESH dir for pr_evt<ID>/ outputs (refuses to reuse a non-empty
#               one that was not created by a prior run of this script -- M13)
#     data|sim  reality TLA
#     evt ...   optional explicit event-id subset; default = every ql_evt<ID>
#               found under ql_root
#
# Env: PR_JOBS (default 6, M5), SBND_WCT_LOGLEVEL (default debug -- needed for
#      the MABC timing / TaggerCheckNeutrino timing substage lines, doc pr/11
#      sec 3/5; perf=true is already on for SBND).
#
# Per-event output: out_root/pr_evt<ID>/{wct_pr_evt<ID>.log, stdout.log, rc.txt,
#   .time.meta (timecmd.py), mabc-pr.zip, tracking-pr.root,
#   pctree-pr-evt<ID>.tar.gz, nusel-evt<ID>.tsv}.
# Arm: out_root/nusel-table.tsv + nusel-events.tsv -- merged over EVERY pr_evt*/
#   in out_root, not just this invocation's events (doc 99; it used to be the
#   batch, so a one-event re-run truncated the arm's tables).  Same shape as
#   run_nusel_evt.sh all.  Read the SCORES with pr_scores_table.py.
set -u; {   # doc pr/141 sec 19 -- brace + trailing exit: see the note at EOF

SX=$(cd "$(dirname "$0")" && pwd -P)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
TK=$WCT_BASE/toolkit
export WIRECELL_PATH=${PR_CFG_TREE:-$TK/cfg}:$WCT_BASE/wire-cell-data:$WCT_BASE/wire-cell-data/sbnd/photodet:${WIRECELL_PATH:-}  # doc pr/142: PR_CFG_TREE swaps in an older cfg tree (an A/B reference); EMPTY = $TK/cfg = byte-identical.  Same line on purpose: no line number moves.
export PYTHONPATH=$TK/pyutil/python:$WCT_BASE/local/python:$WCT_BASE/wire-cell-python:${PYTHONPATH:-}
AB=$SX/../../abtest

SBND_DIR=$SX  # required by _runlib.sh (unused otherwise here: QLROOT/OUTROOT
              # are explicit args, not SBND_WORK_ROOT-derived).
# _runlib.sh (2026-08-05) refuses to source when SBND_WORK_ROOT is unset AND
# the default work/ is absent (M13 guard, doc 71) -- a false positive for
# THIS script, which never reads $SBND_WORK_ROOT.  Give it a harmless
# placeholder rather than weakening the guard for scripts that do use the
# default (run_img_evt.sh, run_ql_evt.sh, run_nusel_evt.sh, run_pr_evt.sh).
SBND_WORK_ROOT=${SBND_WORK_ROOT:-unused-see-QLROOT-OUTROOT-args}
. "$SX/_runlib.sh"

usage() {
    cat <<EOF
Usage: $0 <ql_root> <out_root> <data|sim> [evt ...]
  ql_root   dir with ql_evt<ID>/{pctree,opflash,mabc-all-apa.zip}
  out_root  fresh output dir (pr_evt<ID>/ per event)
  data|sim  reality TLA
  evt ...   optional event-id subset (default: every ql_evt<ID> in ql_root)
Env: PR_JOBS (default 6), SBND_WCT_LOGLEVEL (default debug)
EOF
}

[ $# -ge 3 ] || { usage; exit 1; }
QLROOT=$(cd "$1" 2>/dev/null && pwd -P) || { echo "ERROR: no such ql_root: $1" >&2; exit 1; }
OUTROOT=$2
REALITY=$3
shift 3

case "$REALITY" in
    data|sim) ;;
    *) echo "ERROR: reality must be data|sim, got '$REALITY'" >&2; exit 1 ;;
esac

mkdir -p "$OUTROOT"
OUTROOT=$(cd "$OUTROOT" && pwd -P)

# doc pr/38 round 3: the PR job re-applies switch_scope's pos_offset
# correction, gated on reality -- so the PR reality MUST match the lineage of
# the ql_root that produced the input pctree, or borderline scope / in-window
# / PID decisions flip wholesale (234638 red-chord track, 55715 whole-event
# EM-shower absorb).  Every run stamps its out_root; the check reads the
# ql_root's stamp, falling back to the reality= field of its .batch_* markers
# (rounds that predate the stamp).  Mismatch is fatal unless
# SBND_ALLOW_REALITY_MISMATCH=1 (deliberate cross-lineage A/B only).
echo "$REALITY" > "$OUTROOT/.lineage_reality"
QL_REALITY=""
if [ -f "$QLROOT/.lineage_reality" ]; then
    QL_REALITY=$(cat "$QLROOT/.lineage_reality")
else
    mapfile -t _QLR < <(grep -sho 'reality=[a-z]*' "$QLROOT"/.batch_*.log 2>/dev/null | sort -u | sed 's/reality=//')
    if [ "${#_QLR[@]}" -gt 1 ]; then
        echo "WARN: ql_root has MIXED reality markers (${_QLR[*]}) -- lineage check skipped, verify by hand" >&2
    elif [ "${#_QLR[@]}" -eq 1 ]; then
        QL_REALITY="${_QLR[0]}"
    fi
fi
if [ -n "$QL_REALITY" ] && [ "$QL_REALITY" != "$REALITY" ]; then
    echo "ERROR: reality mismatch: ql_root lineage is '$QL_REALITY' but this run was given '$REALITY'." >&2
    echo "       (doc pr/38 round 3; set SBND_ALLOW_REALITY_MISMATCH=1 only for a deliberate cross-lineage A/B)" >&2
    [ "${SBND_ALLOW_REALITY_MISMATCH:-0}" = "1" ] || exit 1
fi

if [ $# -ge 1 ]; then
    EVENT_IDS=("$@")
else
    mapfile -t EVENT_IDS < <(ls -d "$QLROOT"/ql_evt*/ 2>/dev/null | sed -E 's#.*/ql_evt([0-9]+)/?$#\1#' | sort -n)
fi
[ "${#EVENT_IDS[@]}" -gt 0 ] || { echo "ERROR: no events found under $QLROOT" >&2; exit 1; }

JSONNET="$SX/wct-pr-perevt.jsonnet"
[ -f "$JSONNET" ] || { echo "ERROR: missing jsonnet: $JSONNET" >&2; exit 1; }

# doc 68: the LAr set and the TrackFitting parameter file come from the job's
# own defaults (cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet); only an
# SBND_TRACKFIT_JSON override is named, for the doc-66 diffusion A/B.
TFJSON="${SBND_TRACKFIT_JSON:-}"
TFJSON_TLA=()
[ -n "$TFJSON" ] && TFJSON_TLA=(--tla-str "trackfitting_config=$TFJSON")

# Production NUF pipeline + the 5 neutrino-PR stages (doc pr/2-3; ordering
# matters -- BDTs after tagger_check_neutrino, nue after numu, tagger_output
# after tracking_visitor because it opens tracking-pr.root in UPDATE mode).
# protect_bundle + steiner_refresh (doc pr/23): uboone's second graph
# examination (Protect_Over_Clustering) -- split each beam-bundle cluster at
# graph component boundaries, cathode re-join per the cfg operating point.
# Position (doc pr/23 ordering decision): AFTER the cosmic taggers and BEFORE
# tagger_check_neutrino, with steiner_refresh (replace=false) right after so
# the split clusters' steiner products are rebuilt -- the prototype-faithful
# order (cosmic verdicts on unsplit clusters, wire-cell-prod-stm.cxx:806;
# protect only in the nue executable, wire-cell-prod-nue.cxx:1322).
# PR_PIPELINE: replace the whole stage list.  EMPTY BY DEFAULT => the string
# below, so every existing invocation compiles and outputs exactly as before.
# Its reason for existing (doc 76 round 2): stage A of the two-stage chain runs
# only the cosmic-rejection half to produce the selection table, and the P0.1
# probe that proved the chain cannot be SPLIT there needed to run each half on
# its own.  Do not use it to ship a different production pipeline -- the
# production list is the default below.
PIPELINE="${PR_PIPELINE:-switch_scope,unmerge_bundle,unmerge_assoc,steiner,fiducialutils,tagger_check_tgm,tagger_check_stm,tagger_check_fc,protect_bundle,steiner_refresh,tagger_check_neutrino,numu_bdt_scorer,nue_bdt_scorer,tracking_visitor,tagger_output}"

# PR_EXTRA_STAGES: comma-separated cm_by_name stages APPENDED to the pipeline
# above.  EMPTY BY DEFAULT => the pipeline string, and therefore every compiled
# config and every output of this driver, is unchanged.  Names resolve in
# clus_pr's cm_by_name (cfg/pgrapher/experiment/sbnd/clus.jsonnet).
#
# Its reason for existing is the PR event display (doc pr/26):
#   PR_EXTRA_STAGES=pr_display ./run_pr_chain_batch.sh <ql_root> <out> sim 388
# appends PrDisplayDump, which writes pr_evt<ID>/calib-pr-evt<ID>.json next to
# the usual outputs.  That stage is read-only, so an arm run with it must hash
# identically to one run without -- which is the doc's gate.
# The beam window, in us, that this driver runs the job at.  ONE variable so
# the per-event and the group path cannot drift: nusel_extract.py takes it
# twice -- as --beam-window (labelling) and, in group mode, as --bw-gate (which
# mains the taggers evaluated at all).  It must match the job's own
# beam_window_us default in wct-pr-perevt.jsonnet; this driver passes no
# beam-window TLA, so the default is what runs.
PR_BEAM_WINDOW_US="0.2,2.2"

if [ -n "${PR_EXTRA_STAGES:-}" ]; then
    PIPELINE="$PIPELINE,$PR_EXTRA_STAGES"
fi

# doc 87: normalize the master switch HERE, before anything reads SBND_PR_CALIB.
# Ordering is load-bearing: the pipeline strip below and the scoreboard auto-set
# further down both read it, so defaulting it later would leave
# `PR_MINIMAL_OUTPUT=1 PR_EXTRA_STAGES=pr_display` writing the calib dump it was
# asked to drop.
: "${PR_MINIMAL_OUTPUT:=}"
case "$PR_MINIMAL_OUTPUT" in
    1|true|yes) PR_MINIMAL_OUTPUT=1; : "${SBND_PR_CALIB:=0}" ;;
    *)          PR_MINIMAL_OUTPUT=0 ;;
esac

# doc 87: SBND_PR_CALIB=0 drops the calib dump even when PR_EXTRA_STAGES asked
# for it, so the three output knobs have one uniform surface.  PrDisplayDump is
# opt-in already, so with the stage absent nothing is instantiated -- this is a
# pipeline_names edit, not a component knob.
if [ "${SBND_PR_CALIB:-1}" = 0 ]; then
    PIPELINE=$(echo "$PIPELINE" | tr ',' '\n' | grep -vx 'pr_display' | paste -sd, -)
fi

# doc sbnd_xin/docs/pr/75: the neutrino-vertex hand scan needs the per-event
# vertex scoreboard (compare_main_vertices scores, DL top-K voxels, the seven
# rerank composite terms, the accept route) beside the pr_display dump.  That
# recording lives in TaggerCheckNeutrino -- PrDisplayDump runs after it and
# cannot see its locals -- so it is a separate C++ knob, DEFAULT OFF.
#
# Turned on automatically whenever pr_display is requested, so producing a
# scannable dump stays the one command doc pr/26 documents.  It is pure
# recording (no decision reads it), which is what keeps the doc pr/26 sec 6
# claim -- a pr_display arm hashes identically to a plain one -- intact.
# SBND_VERTEX_SCOREBOARD set explicitly always wins, including =0/false to
# reproduce a pre-pr/75 dump.
# doc 87: gate this on SBND_PR_CALIB too.  The board is consumed ONLY by
# PrDisplayDump, so with SBND_PR_CALIB=0 stripping that stage the auto-set would
# compute a scoreboard nothing writes out AND leave a vertex_scoreboard TLA in
# the compiled config that a plain default run does not have -- i.e. the knob
# would not be config-neutral.  Measured: without this, arm B (pr_display +
# SBND_PR_CALIB=0) carried "vertex_scoreboard" : true while the default arm
# carried no such key.
case ",${PR_EXTRA_STAGES:-}," in
    *,pr_display,*) [ "${SBND_PR_CALIB:-1}" = 0 ] || : "${SBND_VERTEX_SCOREBOARD:=true}" ;;
esac

# ---------------------------------------------------------------------------
# doc 87 -- PRODUCTION OUTPUT KNOBS.  ALL DEFAULT TO TODAY'S BEHAVIOUR: unset or
# empty => no TLA, no change, byte-identical.  Only the literal value 0 turns an
# output off, so a typo'd value fails safe (keeps writing) rather than silently
# discarding a product.
#
#   SBND_PR_BEE=0      no pr_evt<ID>/mabc-pr.zip            (~0.24 GB/1000 evt)
#   SBND_PR_PCTREE=0   no pr_evt<ID>/pctree-pr-evt<ID>.tar.gz (~2.24 GB/1000)
#   SBND_PR_CALIB=0    no calib-pr-evt<ID>.json even if PR_EXTRA_STAGES asks
#   PR_MINIMAL_OUTPUT=1  the master switch -- see below
#
# PR_MINIMAL_OUTPUT does NOT suppress at source.  It lets the job write the Bee
# zip and the pctree, runs the per-event nusel extraction that needs them, and
# THEN deletes them.  Residual disk is the same as suppressing, the per-event
# peak is one event's worth, and -- unlike suppression -- nusel-evt<ID>.tsv keeps
# its AUTHORITATIVE pctree-derived flags instead of the tear-prone log fallback,
# and the group-mode per-event verdict below keeps working unchanged.

# Suppressing the Bee zip at source costs the in-scope cluster set, which
# nusel_extract.py needs -- unless save_in_scope has put it in T_cluster.  So
# SBND_PR_BEE=0 defaults save_in_scope ON; an explicit SBND_PR_SAVE_IN_SCOPE
# still wins, the same idiom PR_EXTRA_STAGES=pr_display uses for the scoreboard.
if [ "${SBND_PR_BEE:-1}" = 0 ]; then : "${SBND_PR_SAVE_IN_SCOPE:=1}"; fi

# doc sbnd_xin/docs/pr/79 sec 10: harvest requires the scoreboard, so a
# truthy SBND_DL_VTX_HARVEST defaults the board on too (explicit
# SBND_VERTEX_SCOREBOARD still wins).  pr_display alone does NOT enable
# harvest -- it is opt-in, so the pr/26 sec 6 hash-identity claim for
# scoreboard-only dumps keeps holding.
case "${SBND_DL_VTX_HARVEST:-}" in
    true|1) : "${SBND_VERTEX_SCOREBOARD:=true}" ;;
esac

# SBND PRODUCTION DEFAULT ON since the doc pr/23 sec 9 flip (owner 2026-08-02,
# after the sec 8 fresh-tree gate: 0 event_label / nu_evaluated flips in 572
# valfast events).  SBND_PROTECT_BUNDLE=0 removes both stages = the pre-pr/23
# chain (the arm every pre-flip comparison uses).
if [ "${SBND_PROTECT_BUNDLE:-1}" = 0 ]; then
    PIPELINE="${PIPELINE/protect_bundle,steiner_refresh,/}"
fi

# Cathode kink veto (doc pr/20 Part II B0), cm.  EMPTY = emit no TLA = the job
# default null = C++ 0 = OFF = the legacy kink search, so a bare run of this
# script is byte-identical to before the knob existed.
# Env: SBND_CATHODE_KINK_XCUT=<cm> SBND_CATHODE_X=<cm>.
CATH_TLA=()
# SBND_NO_DL=1: force the GEOMETRIC neutrino vertex by passing an empty
# dl_weights, the same thing run_nusel_evt.sh always does.  UNSET BY DEFAULT so
# this driver keeps running the DL (SCN) vertex, which is the production
# default.  Its reason for existing is diagnosis, not production: the DL vertex
# is a python/torch inference and CLAUDE.md M4 already records that it is not
# bit-stable, so when a group run and a per-event run disagree this is the knob
# that says whether the DL vertex is the reason.
if [ "${SBND_NO_DL:-0}" = 1 ]; then
    CATH_TLA+=(--tla-str "dl_weights=")
fi
[ -n "${SBND_CATHODE_KINK_XCUT:-}" ] && CATH_TLA+=(--tla-code "cathode_kink_xcut=${SBND_CATHODE_KINK_XCUT}")
[ -n "${SBND_CATHODE_X:-}" ]         && CATH_TLA+=(--tla-code "cathode_x=${SBND_CATHODE_X}")
# doc pr/94 Phase 2: per-bundle neutrino candidates.  One T_tagger/T_kine row
# per in-beam-window flash bundle instead of one per event, each carrying its
# own vertex/kinematics/BDT scores plus a vectorised per-activity cosmic block
# (act_*).  **SBND PRODUCTION DEFAULT ON since the 2026-08-19 owner flip (doc
# pr/94 sec 9.13)** -- EMPTY now inherits that.  Set 0 for the PRE-FLIP arm
# (one event-wide candidate, the pre-pr/94 behaviour).
# Env: SBND_NU_PER_BUNDLE=<0|1>.
[ -n "${SBND_NU_PER_BUNDLE:-}" ] && CATH_TLA+=(--tla-code "nu_per_bundle=$([ "${SBND_NU_PER_BUNDLE}" = 0 ] && echo false || echo true)")
# doc 80: MCS muon momentum (kine_mcs_* T_kine branches + the computation,
# both derived from ONE mcs_enable TLA).  EMPTY = no TLA = job default false
# = byte-identical pre-MCS config AND schema.  Env: SBND_MCS=<0|1>.
[ -n "${SBND_MCS:-}" ] && CATH_TLA+=(--tla-code "mcs_enable=$([ "${SBND_MCS}" = 0 ] && echo false || echo true)")
# doc 80 sec 7.5: cathode excised half-band (cm); 0 = excision off (the
# sign-check arm).  EMPTY = no TLA = the job default 5.
[ -n "${SBND_MCS_CATHODE_XCUT:-}" ] && CATH_TLA+=(--tla-code "mcs_cathode_xcut=${SBND_MCS_CATHODE_XCUT}")
# doc pr/94 Phase 5b round 2: the dot guard.  Length floor (cm) for a
# per-bundle candidate, exempting the legacy event-wide winner.  EMPTY = no
# TLA = the job default 15 cm.  Set to 0 to reproduce the pre-5b behavior (no
# floor), which is what promoted sub-cm blobs to neutrino candidates.
# Env: SBND_NU_PER_BUNDLE_MIN_LENGTH=<cm>.
[ -n "${SBND_NU_PER_BUNDLE_MIN_LENGTH:-}" ] && CATH_TLA+=(--tla-code "nu_per_bundle_min_length=${SBND_NU_PER_BUNDLE_MIN_LENGTH}")
# doc pr/94 Phase 3: stop ClusteringProtectBundle withholding cosmic-convicted
# bundles from the PR ensemble, so every in-beam bundle is actually openable by
# Phase 2's per-bundle loop.  EMPTY = no TLA = the job default null = the C++
# default true = legacy = byte-identical.  Set to 0 to open them.
# Env: SBND_PROTECT_SKIP_CONVICTED=<0|1>.
[ -n "${SBND_PROTECT_SKIP_CONVICTED:-}" ] && CATH_TLA+=(--tla-code "protect_skip_convicted=$([ "${SBND_PROTECT_SKIP_CONVICTED}" = 0 ] && echo false || echo true)")
# doc pr/94 round 3: let a cosmic-convicted main OPEN its bundle so the
# bundle's unconvicted members get ClusteringProtectBundle's graph examination
# (the convicted cluster itself is still never split).  Narrower than
# SBND_PROTECT_SKIP_CONVICTED=0 above, which also splits the cosmic tree.
# **SBND PRODUCTION DEFAULT ON since the 2026-08-19 owner flip (doc pr/94 sec
# 9.13)** -- EMPTY inherits that; set 0 for the pre-flip arm.
# Env: SBND_OPEN_CONVICTED_BUNDLES=<0|1>.
[ -n "${SBND_OPEN_CONVICTED_BUNDLES:-}" ] && CATH_TLA+=(--tla-code "protect_open_convicted_bundles=$([ "${SBND_OPEN_CONVICTED_BUNDLES}" = 0 ] && echo false || echo true)")
# doc pr/94 round 3: give the SELECTED neutrino candidate the main-cluster PR
# treatment for its own pass even when it is a demoted main (examine_vertices_3,
# improve_vertex, main_cluster_initial_pair_vertices, break_two_end_dqdx, the
# main-branch endpoint ordering).  EMPTY = no TLA = the job default false =
# **SBND PRODUCTION DEFAULT ON since the 2026-08-19 owner flip (doc pr/94 sec
# 9.13)** -- EMPTY inherits that; set 0 for the pre-flip arm.
# Env: SBND_NU_SELECTED_AS_MAIN=<0|1>.
[ -n "${SBND_NU_SELECTED_AS_MAIN:-}" ] && CATH_TLA+=(--tla-code "nu_selected_as_main=$([ "${SBND_NU_SELECTED_AS_MAIN}" = 0 ] && echo false || echo true)")
# doc pr/89 Arm D2: post-DL adjustment reach, cm.  EMPTY = no TLA = the cfg
# default null = the C++ defaults (vks 5.0 / mvga 15.0) = byte-identical.
# The TLAs already exist and are fully threaded (wct-pr-perevt.jsonnet:1977,
# :1989); these envs only expose them to a batch A/B.
# Env: SBND_VKS_RADIUS=<cm> SBND_MVGA_RADIUS=<cm>.
[ -n "${SBND_VKS_RADIUS:-}" ]  && CATH_TLA+=(--tla-code "vks_radius=${SBND_VKS_RADIUS}")
[ -n "${SBND_MVGA_RADIUS:-}" ] && CATH_TLA+=(--tla-code "mvga_radius=${SBND_MVGA_RADIUS}")
# doc pr/99 round 2 -- op3.5 approach-collapse guards + op1-post charge
# second-opinion + shower ghost-member drop.  Numeric knobs: unset/empty
# omits the TLA (jsonnet default null => C++ default 0 = legacy =>
# byte-identical).  Bool knobs: tri-state (unset = cfg default, 1 = force
# on, 0 = force off).
# doc 77 round 4 (2026-09-01): mvga_ac_veto_radius removed -- 0.2 cm measured
# ADVERSE.  SBND_MVGA_AC_VETO_RADIUS no longer wired.
[ -n "${SBND_MVGA_AC_CHORD_MAX:-}" ]   && CATH_TLA+=(--tla-code "mvga_ac_chord_max=${SBND_MVGA_AC_CHORD_MAX}")
# doc pr/103: mvga op0 pass-through split radius (cm) + miss tolerance (cm).  EMPTY = no TLA = the job default (off).
[ -n "${SBND_MVGA_PASSTHRU:-}" ]       && CATH_TLA+=(--tla-code "mvga_passthru=${SBND_MVGA_PASSTHRU}")
[ -n "${SBND_MVGA_PASSTHRU_TOL:-}" ]   && CATH_TLA+=(--tla-code "mvga_passthru_tol=${SBND_MVGA_PASSTHRU_TOL}")
[ -n "${SBND_MVGA_INTERPOSED_FALLBACK_MIN_ANGLE:-}" ] && CATH_TLA+=(--tla-code "mvga_interposed_fallback_min_angle=${SBND_MVGA_INTERPOSED_FALLBACK_MIN_ANGLE}")
[ -n "${SBND_MVGA_DUP_STARVED_ASYM:-}" ] && CATH_TLA+=(--tla-code "mvga_dup_starved_asym=${SBND_MVGA_DUP_STARVED_ASYM}")
[ -n "${SBND_MVGA_DUP_STARVED_MIP:-}" ] && CATH_TLA+=(--tla-code "mvga_dup_starved_mip=${SBND_MVGA_DUP_STARVED_MIP}")
[ -n "${SBND_MVGA_DUP_STARVED_SPAN:-}" ] && CATH_TLA+=(--tla-code "mvga_dup_starved_span=${SBND_MVGA_DUP_STARVED_SPAN}")
[ -n "${SBND_SHOWER_GHOST_OVERLAP_FRAC:-}" ] && CATH_TLA+=(--tla-code "shower_ghost_overlap_frac=${SBND_SHOWER_GHOST_OVERLAP_FRAC}")
[ -n "${SBND_SHOWER_GHOST_DQDX_RATIO:-}" ] && CATH_TLA+=(--tla-code "shower_ghost_dqdx_ratio=${SBND_SHOWER_GHOST_DQDX_RATIO}")
[ -n "${SBND_SHOWER_GHOST_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_ghost_min_len=${SBND_SHOWER_GHOST_MIN_LEN}")
for _pr99 in \
    "SBND_MVGA_AC_NO_CASCADE:mvga_ac_no_cascade" \
    "SBND_MVGA_INTERPOSED_FALLBACK:mvga_interposed_fallback" \
    "SBND_SHOWER_GHOST_MEMBER_DROP:shower_ghost_member_drop" ; do
    _env=${_pr99%%:*}; _key=${_pr99#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr99 _env _key _val
# doc pr/99 round 3 -- same convention: numerics pass through when set,
# bool knobs tri-state (unset = cfg default, 1 = force on, 0 = force off).
[ -n "${SBND_SHOWER_HADRONIC_MIN_LEN:-}" ]      && CATH_TLA+=(--tla-code "shower_hadronic_min_len=${SBND_SHOWER_HADRONIC_MIN_LEN}")
[ -n "${SBND_SHOWER_HADRONIC_SCAN_LEN:-}" ]     && CATH_TLA+=(--tla-code "shower_hadronic_scan_len=${SBND_SHOWER_HADRONIC_SCAN_LEN}")
[ -n "${SBND_SHOWER_HADRONIC_BIN:-}" ]          && CATH_TLA+=(--tla-code "shower_hadronic_bin=${SBND_SHOWER_HADRONIC_BIN}")
[ -n "${SBND_SHOWER_HADRONIC_R_CYL:-}" ]        && CATH_TLA+=(--tla-code "shower_hadronic_r_cyl=${SBND_SHOWER_HADRONIC_R_CYL}")
[ -n "${SBND_SHOWER_HADRONIC_R_CORE:-}" ]       && CATH_TLA+=(--tla-code "shower_hadronic_r_core=${SBND_SHOWER_HADRONIC_R_CORE}")
[ -n "${SBND_SHOWER_HADRONIC_GROWTH_MAX:-}" ]   && CATH_TLA+=(--tla-code "shower_hadronic_growth_max=${SBND_SHOWER_HADRONIC_GROWTH_MAX}")
[ -n "${SBND_SHOWER_HADRONIC_GROWTH_BRAGG:-}" ] && CATH_TLA+=(--tla-code "shower_hadronic_growth_bragg=${SBND_SHOWER_HADRONIC_GROWTH_BRAGG}")
[ -n "${SBND_SHOWER_HADRONIC_BRAGG_RATIO:-}" ]  && CATH_TLA+=(--tla-code "shower_hadronic_bragg_ratio=${SBND_SHOWER_HADRONIC_BRAGG_RATIO}")
[ -n "${SBND_SHOWER_HADRONIC_STEM_RATIO:-}" ]   && CATH_TLA+=(--tla-code "shower_hadronic_stem_ratio=${SBND_SHOWER_HADRONIC_STEM_RATIO}")
for _pr99r3 in \
    "SBND_KINE_CHARGE_DEDUP:kine_charge_dedup" \
    "SBND_KINE_CHARGE_REBUILD:kine_charge_rebuild" \
    "SBND_SHOWER_HADRONIC_TAG:shower_hadronic_tag" ; do
    _env=${_pr99r3%%:*}; _key=${_pr99r3#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr99r3 _env _key _val
# doc pr/101 Enu accounting round.  Bools tri-state as above; numerics
# pass-through (EMPTY = no TLA = C++ default).
for _pr101 in \
    "SBND_KINE_CHARGE_TRACK_CTX:kine_charge_track_ctx" \
    "SBND_KINE_MASS_RULES:kine_mass_rules" \
    "SBND_KINE_HADRONIC_DQDX:kine_hadronic_dqdx" \
    "SBND_KINE_MAINVTX_USED_GUARD:kine_mainvtx_used_guard" ; do
    _env=${_pr101%%:*}; _key=${_pr101#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr101 _env _key _val
# doc pr/117 round 1 -- EM clustering knobs (pass-4 best-owner arbitration,
# late fragment consolidation).  Bools tri-state
# (unset = cfg default, 1 = force on, 0 = force off); numerics pass-through
# in cm/deg (EMPTY = no TLA = C++ default 6cm/15deg/5cm =
# byte-identical).
[ -n "${SBND_SHOWER_MERGE_RELAX_DIS:-}" ]      && CATH_TLA+=(--tla-code "shower_merge_relax_dis=${SBND_SHOWER_MERGE_RELAX_DIS}")
[ -n "${SBND_SHOWER_MERGE_RELAX_ANGLE:-}" ]    && CATH_TLA+=(--tla-code "shower_merge_relax_angle=${SBND_SHOWER_MERGE_RELAX_ANGLE}")
[ -n "${SBND_SHOWER_MERGE_RELAX_MIN_LEN:-}" ]  && CATH_TLA+=(--tla-code "shower_merge_relax_min_len=${SBND_SHOWER_MERGE_RELAX_MIN_LEN}")
for _pr117 in \
    "SBND_SHOWER_PASS4_BEST_OWNER:shower_pass4_best_owner" \
    "SBND_SHOWER_MERGE_RELAX:shower_merge_relax" ; do
    _env=${_pr117%%:*}; _key=${_pr117#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr117 _env _key _val
# doc pr/118 round 1 -- the two-tier axis+charge merge path.  Bool
# tri-state (unset = cfg default, 1 = force on, 0 = force off); numerics
# pass-through (EMPTY = no TLA = C++ default
# 1.0/8cm/5000/7.5deg/120cm/1cm/30deg = byte-identical).
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_FRAC:-}" ]    && CATH_TLA+=(--tla-code "shower_merge_relax_cont_frac=${SBND_SHOWER_MERGE_RELAX_CONT_FRAC}")
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_GAP:-}" ]     && CATH_TLA+=(--tla-code "shower_merge_relax_cont_gap=${SBND_SHOWER_MERGE_RELAX_CONT_GAP}")
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_QMED:-}" ]    && CATH_TLA+=(--tla-code "shower_merge_relax_cont_qmed=${SBND_SHOWER_MERGE_RELAX_CONT_QMED}")
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_AXIS:-}" ]    && CATH_TLA+=(--tla-code "shower_merge_relax_cont_axis=${SBND_SHOWER_MERGE_RELAX_CONT_AXIS}")
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_DMAX:-}" ]    && CATH_TLA+=(--tla-code "shower_merge_relax_cont_dmax=${SBND_SHOWER_MERGE_RELAX_CONT_DMAX}")
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_T1_GAP:-}" ]  && CATH_TLA+=(--tla-code "shower_merge_relax_cont_t1_gap=${SBND_SHOWER_MERGE_RELAX_CONT_T1_GAP}")
[ -n "${SBND_SHOWER_MERGE_RELAX_CONT_T1_FOLD:-}" ] && CATH_TLA+=(--tla-code "shower_merge_relax_cont_t1_fold=${SBND_SHOWER_MERGE_RELAX_CONT_T1_FOLD}")
for _pr118 in \
    "SBND_SHOWER_MERGE_RELAX_CONTINUITY:shower_merge_relax_continuity" ; do
    _env=${_pr118%%:*}; _key=${_pr118#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr118 _env _key _val
# doc pr/120 round 1 -- backward-stem admission guard.
# Bools tri-state (unset = cfg default, 1 = force on, 0 = force off);
# numerics pass-through (EMPTY = no TLA = C++ default 110deg).
[ -n "${SBND_STEM_BACKFILL_BACK_ANG:-}" ]          && CATH_TLA+=(--tla-code "stem_backfill_back_ang=${SBND_STEM_BACKFILL_BACK_ANG}")
for _pr120 in \
    "SBND_STEM_BACKFILL_BACK_GUARD:stem_backfill_back_guard" ; do
    _env=${_pr120%%:*}; _key=${_pr120#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr120 _env _key _val
# doc pr/121 round 1 -- examine_shower_1 dedup re-home (348471 orphaning).
# Bool tri-state (unset = cfg default, 1 = force on, 0 = force off).
_val=${SBND_SHOWER_EX1_DEDUP_REHOME:-}
[ "$_val" = 1 ] && CATH_TLA+=(--tla-code "shower_ex1_dedup_rehome=true")
[ "$_val" = 0 ] && CATH_TLA+=(--tla-code "shower_ex1_dedup_rehome=false")

# doc pr/123 round 1 -- pass4_angle over-reach (owner line 2026-08-28).
# Prune: bool tri-state (unset = cfg default, 1 = on, 0 = off); gap in cm
# (EMPTY = cfg default 40).  Track guard: length in cm (EMPTY = cfg default
# 0 = off).
_val=${SBND_SHOWER_PASS4_PRUNE:-}
[ "$_val" = 1 ] && CATH_TLA+=(--tla-code "shower_pass4_prune_detached=true")
[ "$_val" = 0 ] && CATH_TLA+=(--tla-code "shower_pass4_prune_detached=false")
[ -n "${SBND_SHOWER_PASS4_PRUNE_GAP:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prune_gap=${SBND_SHOWER_PASS4_PRUNE_GAP}")
[ -n "${SBND_SHOWER_PASS4_TRACK_GUARD_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_track_guard_len=${SBND_SHOWER_PASS4_TRACK_GUARD_LEN}")
[ -n "${SBND_SHOWER_PASS4_PROX_GUARD_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prox_guard_len=${SBND_SHOWER_PASS4_PROX_GUARD_LEN}")          # doc pr/130 item 1b
[ -n "${SBND_SHOWER_PASS3_BACKFILL_GUARD_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_pass3_backfill_guard_len=${SBND_SHOWER_PASS3_BACKFILL_GUARD_LEN}")  # doc pr/130 item 1b
[ -n "${SBND_STEM_BACKFILL_BACK_DVTX:-}" ] && CATH_TLA+=(--tla-code "stem_backfill_back_dvtx=${SBND_STEM_BACKFILL_BACK_DVTX}")                    # doc pr/130 item B

# doc pr/124 front A -- gap-band tier-2 prune.  gap2 in cm (EMPTY = cfg
# default 0 = off); ang in deg / mdqdx in MIP (EMPTY = cfg defaults 40/2.5).
[ -n "${SBND_SHOWER_PASS4_PRUNE_GAP2:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prune_gap2=${SBND_SHOWER_PASS4_PRUNE_GAP2}")
[ -n "${SBND_SHOWER_PASS4_PRUNE2_ANG:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prune2_ang=${SBND_SHOWER_PASS4_PRUNE2_ANG}")
[ -n "${SBND_SHOWER_PASS4_PRUNE2_MDQDX:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prune2_mdqdx=${SBND_SHOWER_PASS4_PRUNE2_MDQDX}")
# doc pr/124 front C -- pass3_cone track-pdg decline; len in cm (EMPTY = cfg
# default 0 = off).
[ -n "${SBND_SHOWER_PASS3_CONE_GUARD_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_pass3_cone_guard_len=${SBND_SHOWER_PASS3_CONE_GUARD_LEN}")

# doc pr/125 -- same-vertex track-frag absorb (37112) + vertex-connected
# satellite absorb (69314).  Bools tri-state (unset = cfg default, 1 = on,
# 0 = off); gap/len in cm, kine caps in MeV (EMPTY = cfg defaults 6/50/10/20).
_val=${SBND_SHOWER_SAMEVTX_TRACK_ABSORB:-}
[ -n "$_val" ] && CATH_TLA+=(--tla-code "shower_samevtx_track_absorb=$([ "$_val" = 0 ] && echo false || echo true)")
[ -n "${SBND_SHOWER_SAMEVTX_ABSORB_GAP:-}" ] && CATH_TLA+=(--tla-code "shower_samevtx_absorb_gap=${SBND_SHOWER_SAMEVTX_ABSORB_GAP}")
[ -n "${SBND_SHOWER_SAMEVTX_ABSORB_MAX_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_samevtx_absorb_max_len=${SBND_SHOWER_SAMEVTX_ABSORB_MAX_LEN}")
[ -n "${SBND_SHOWER_SAMEVTX_ABSORB_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_samevtx_absorb_min_len=${SBND_SHOWER_SAMEVTX_ABSORB_MIN_LEN}")
_val=${SBND_SHOWER_SATELLITE_ABSORB:-}
[ -n "$_val" ] && CATH_TLA+=(--tla-code "shower_satellite_absorb=$([ "$_val" = 0 ] && echo false || echo true)")
[ -n "${SBND_SHOWER_SATELLITE_ABSORB_MAX_MEV:-}" ] && CATH_TLA+=(--tla-code "shower_satellite_absorb_max_mev=${SBND_SHOWER_SATELLITE_ABSORB_MAX_MEV}")
[ -n "${SBND_SHOWER_SATELLITE_ABSORB_HOST_MEV:-}" ] && CATH_TLA+=(--tla-code "shower_satellite_absorb_host_mev=${SBND_SHOWER_SATELLITE_ABSORB_HOST_MEV}")

# doc pr/123 round 2 -- guard-freed track pickup (PF root node + kine count).
# Bool tri-states (unset = cfg default, 1 = on, 0 = off).
_val=${SBND_PF_ORPHAN_GUARD_FREED:-}
[ "$_val" = 1 ] && CATH_TLA+=(--tla-code "pf_orphan_guard_freed=true")
[ "$_val" = 0 ] && CATH_TLA+=(--tla-code "pf_orphan_guard_freed=false")
_val=${SBND_KINE_COUNT_GUARD_FREED:-}
[ "$_val" = 1 ] && CATH_TLA+=(--tla-code "kine_count_guard_freed=true")
[ "$_val" = 0 ] && CATH_TLA+=(--tla-code "kine_count_guard_freed=false")
unset _val
# doc 74 -- cosmic_tagger() consistent-FV knob (G1/G2).  Bool tri-state as
# above: EMPTY = no TLA = the job default, 1 = force on, 0 = force off.
for _d74 in \
    "SBND_COSMIC_CONSISTENT_FV:cosmic_consistent_fv" ; do
    _env=${_d74%%:*}; _key=${_d74#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _d74 _env _key _val
# doc 75 -- nue/single-photon consistent-FV knob + the flag-leak snapshot
# guard.  Same tri-state idiom: EMPTY = no TLA = the job default, 1 = force
# on, 0 = force off.
for _d75 in \
    "SBND_NUE_SP_CONSISTENT_FV:nue_sp_consistent_fv" \
    "SBND_NU_SELECTED_AS_MAIN_SNAPSHOT_ALL:nu_selected_as_main_snapshot_all" ; do
    _env=${_d75%%:*}; _key=${_d75#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _d75 _env _key _val
# docs/76 round 2 -- fast_xgb_forest: book the numu/nue XGB BDT combiners
# with TmvaGradForest (compact exact re-evaluation of the same XML) instead of
# TMVA::Reader.  **SBND PRODUCTION DEFAULT ON since 2026-08-23 (docs/76 sec
# 6)** -- EMPTY inherits that.  Same tri-state idiom: EMPTY = no TLA = the job
# default, 1 = force on, 0 = force off (= the pre-docs/76 TMVA::Reader path,
# byte-identical outputs, ~3 s and ~0.3-0.8 GB more per event).
for _d76 in \
    "SBND_FAST_XGB_FOREST:fast_xgb_forest" ; do
    _env=${_d76%%:*}; _key=${_d76#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _d76 _env _key _val
[ -n "${SBND_KINE_LONG_MUON_MODE:-}" ]     && CATH_TLA+=(--tla-code "kine_long_muon_mode=${SBND_KINE_LONG_MUON_MODE}")
[ -n "${SBND_KINE_LONG_MUON_RATIO_LO:-}" ] && CATH_TLA+=(--tla-code "kine_long_muon_ratio_lo=${SBND_KINE_LONG_MUON_RATIO_LO}")
[ -n "${SBND_KINE_LONG_MUON_RATIO_HI:-}" ] && CATH_TLA+=(--tla-code "kine_long_muon_ratio_hi=${SBND_KINE_LONG_MUON_RATIO_HI}")
# doc 77 round 1 (2026-08-24): dl_vtx_topo_weight/_center (pr/89 Arm C2)
# removed -- live A/B -8/1014.  SBND_DL_VTX_TOPO_WEIGHT/_CENTER no longer wired.
# doc pr/47 sec 8 (O1): wide-baseline cathode kink accept, degrees.  EMPTY =
# no TLA = the job default (SBND ON at 25 deg since 2026-08-07).  0 = force
# the C++ OFF path (legacy kink search, byte-identical); "null" also works
# (omits the key entirely).  Skirt/baseline ride the C++ defaults 3/15 cm.
# Env: SBND_CATHODE_WIDE_KINK_ANGLE=<deg|0|null>.
[ -n "${SBND_CATHODE_WIDE_KINK_ANGLE:-}" ] && CATH_TLA+=(--tla-code "cathode_wide_kink_angle=${SBND_CATHODE_WIDE_KINK_ANGLE}")
# doc pr/25 sec 3: long shower-topology demote length, cm.  EMPTY = no TLA =
# the cfg default (null = OFF = byte-identical).  50 is the scan-supported
# operating point; the guard measures segment_track_length(seg,0).
[ -n "${SBND_SHOWER_TOPO_DEMOTE_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_topo_demote_len=${SBND_SHOWER_TOPO_DEMOTE_LEN}")
# doc pr/31 sec 11 (F2, was P2): skip the stage-3
# segment_determine_shower_direction call so a kShowerTopology segment keeps
# the direction segment_is_shower_topology set -- the prototype's state.
# EMPTY = no TLA = the cfg default (false = OFF = byte-identical).  Set to 1
# for the arm that measures it.
[ "${SBND_SHOWER_TOPO_PROTO_DIR:-}" = 1 ] && CATH_TLA+=(--tla-code "shower_topo_proto_dir=true")
# doc pr/32 sec 11: the four stage-4 (neutrino vertex ID) port fixes.  These
# are TRI-STATE on purpose -- unset = no TLA = whatever the cfg says, 1 = force
# on, 0 = force off -- because once the SBND operating point flips them on, the
# gate arm still has to be able to turn them back off without editing cfg/.
#   F1 SBND_VERTEX_DIR_USE_FIT_POINT   conflict + all-showers geometry from the
#                                      continuous fit, not the Steiner snap
#   F2 SBND_SHOWER_TRAJ_RECHECK_PARITY improve_vertex shower-traj recheck:
#                                      stored-flag gates, 10 cm inner test, and
#                                      a clearable kShowerTrajectory
#   F3 SBND_MAIN_VERTEX_REQUIRE_DESC   drop invalid-descriptor candidates
#                                      before compare_main_vertices scores
#   F4 SBND_MAIN_VERTEX_CANDIDATE_FLAG set kMainCandidate (diagnostic only)
for _pr32 in \
    "SBND_VERTEX_DIR_USE_FIT_POINT:vertex_dir_use_fit_point" \
    "SBND_SHOWER_TRAJ_RECHECK_PARITY:shower_traj_recheck_parity" \
    "SBND_MAIN_VERTEX_REQUIRE_DESC:main_vertex_require_descriptor" \
    "SBND_MAIN_VERTEX_CANDIDATE_FLAG:main_vertex_candidate_flag" ; do
    _env=${_pr32%%:*}; _key=${_pr32#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr32 _env _key _val
# doc pr/31 sec 12: the sec 10.12 topology/PID/direction port fixes.  Same
# tri-state contract as the pr/32 loop above (unset = cfg default, 1 = force
# on, 0 = force off).
#   F5 SBND_CONT_MUON_DIR3_30CM       cont-muon dir3 always at 30 cm
#   F6 SBND_TRACK_COMP_EMPTY_ABSTAIN  empty comparison window abstains
#   F3 SBND_SHOWER_TOPO_RESET         clear kShowerTopology/dirsign at entry
#   F1 SBND_RECLASS_PRESERVE_4MOM     preserve 4-momentum at reclassification
#   F4 SBND_DIR_TRACK_MEDIAN_LOCAL    median over the PID's own dQ/dx vector
#   F7 SBND_EXAMINE_SHOWERS_VTX_BY_INDEX  order the examine_all_showers pair
#                                     by graph index (dormant pending pr/30 F4)
for _pr31 in \
    "SBND_CONT_MUON_DIR3_30CM:cont_muon_dir3_30cm" \
    "SBND_TRACK_COMP_EMPTY_ABSTAIN:track_comp_empty_abstain" \
    "SBND_SHOWER_TOPO_RESET:shower_topo_reset" \
    "SBND_RECLASS_PRESERVE_4MOM:reclass_preserve_4mom" \
    "SBND_DIR_TRACK_MEDIAN_LOCAL:dir_track_median_local" \
    "SBND_EXAMINE_SHOWERS_VTX_BY_INDEX:examine_showers_vertex_by_index" ; do
    _env=${_pr31%%:*}; _key=${_pr31#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr31 _env _key _val
# doc pr/34 sec 11: the sec 10 particle-flow (Bee mc tree) port fixes.  Same
# tri-state contract (unset = cfg default, 1 = force on, 0 = force off).
# DISPLAY-ONLY stage: these move mabc-pr.zip::data/0/0-mc.json and nothing
# else -- gate with pr34_cmp.py, NOT pr32_cmp.py (pctree gate is vacuous).
#   F1 SBND_PF_TRACK_MAIN_CLUSTER_ONLY  track BFS keeps main-cluster idents only
#   F2 SBND_PF_SHOWER_VERTEX_BARRIER    BFS never expands through a shower vtx
#   F3 SBND_PF_SHOWER_PARENT_PRECEDENCE parent shower resolves before track seg
#   F4 SBND_PF_PI0_NODE_PER_ID          one pi0 node per id (home = highest-E
#                                       daughter's parent, owner 2026-08-04)
#   F5 SBND_PF_PDG_NAME_PROTOTYPE_FALLBACK  pi0/nuclei/number PDG-name fallback
for _pr34 in \
    "SBND_PF_TRACK_MAIN_CLUSTER_ONLY:pf_track_main_cluster_only" \
    "SBND_PF_SHOWER_VERTEX_BARRIER:pf_shower_vertex_barrier" \
    "SBND_PF_SHOWER_PARENT_PRECEDENCE:pf_shower_parent_precedence" \
    "SBND_PF_PI0_NODE_PER_ID:pf_pi0_node_per_id" \
    "SBND_PF_PDG_NAME_PROTOTYPE_FALLBACK:pf_pdg_name_prototype_fallback" ; do
    _env=${_pr34%%:*}; _key=${_pr34#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr34 _env _key _val
# doc pr/38 (2026-08-05 owner round 2): the two short-lived pr/38 knobs were
# REMOVED -- their corrected behavior (barrier minus shower start vertices +
# orphan root-leaf safety net) now lives under the existing
# SBND_PF_SHOWER_VERTEX_BARRIER / pf_shower_vertex_barrier knob above.
# doc pr/35 sec 11: the sec 10 energy-reconstruction port fix.  Same tri-state
# contract (unset = cfg default, 1 = force on, 0 = force off).  NOT display-
# only: kine_reco_Enu is numu-BDT var 69 and in the nue reader.  Gate with
# pr35_cmp.py on calib-pr-evt<ID>.json (PR_EXTRA_STAGES=pr_display) + the
# nusel TSVs -- pctree does NOT carry KineInfo, pr32/pr34_cmp gate nothing.
#   F1 SBND_KINE_SHOWER_PDG_LIVE  live start-segment PDG at the four
#                                 fill_kine_tree sites (prototype parity)
_val=${SBND_KINE_SHOWER_PDG_LIVE:-}
[ "$_val" = 1 ] && CATH_TLA+=(--tla-code "kine_shower_pdg_live=true")
[ "$_val" = 0 ] && CATH_TLA+=(--tla-code "kine_shower_pdg_live=false")
unset _val
# doc pr/36 sec 11: the sec 10 tagger-stage port fixes.  Same tri-state
# contract (unset = cfg default, 1 = force on, 0 = force off).  The gate is
# TWO artifacts (doc pr/36 sec 10.9), neither alone sufficient: T_tagger in
# tracking-pr.root (leaf compare, covers F3-F6 fields + scores) PLUS the
# tagger block of calib-pr-evt<ID>.json (PR_EXTRA_STAGES=pr_display; the ONLY
# outlet for F1's match_isFC -- it is NOT booked in T_tagger).  Gate with
# pr36_cmp.py; pctree/mabc must never move.
#   F1 SBND_NEUTRINO_CONSISTENT_FV     match_isFC on the STM/TGM/FC fiducial
#   F3 SBND_SP_SCE_CORRECTION          single-photon SCE gate (OFF on SBND,
#                                      owner 2026-08-04; vacuous, no helper)
#   F4 SBND_TAGGER_ORDERED_SEGSETS     index-ordered accumulation sets (M4)
#   F5 SBND_STEM_ENDPOINT_WCPT_PARITY  prototype wcpt stem-endpoint rule
#   F6 SBND_BROKEN_MUON_CLUSTER_ID_COUNT  distinct cluster IDs, not pointers
#   F7 SBND_NEUTRINO_TYPE_BITMASK      verdict bitmask + neutrino_type/I branch
for _pr36 in \
    "SBND_NEUTRINO_CONSISTENT_FV:neutrino_consistent_fv" \
    "SBND_SP_SCE_CORRECTION:sp_sce_correction" \
    "SBND_TAGGER_ORDERED_SEGSETS:tagger_ordered_segment_sets" \
    "SBND_STEM_ENDPOINT_WCPT_PARITY:stem_endpoint_wcpt_parity" \
    "SBND_BROKEN_MUON_CLUSTER_ID_COUNT:broken_muon_cluster_id_count" \
    "SBND_NEUTRINO_TYPE_BITMASK:neutrino_type_bitmask" ; do
    _env=${_pr36%%:*}; _key=${_pr36#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr36 _env _key _val
# doc pr/33 sec 11: the sec 10 EM-shower-clustering port fixes.  Same
# tri-state contract (unset = cfg default, 1 = force on, 0 = force off).
# The stage is upstream of T_kine, the nue tagger pi0 block, and the Bee
# PR layers (mc.json pi0 grouping + shower_track membership), so gate with
# pr33_cmp.py (all trees + calib + per-member mabc + pctree + TSVs;
# PR_EXTRA_STAGES=pr_display for the calib dump).  pctree and the
# imaging-derived mabc members must never move; ssmsp_* movement in
# T_tagger is the F3 scoping tripwire.
#   F1a SBND_DAUGHTER_COUNT_PROTO_MAIN_VERTEX     _tracks callee, proton skip
#   F1b SBND_DAUGHTER_COUNT_PROTO_EXAMINE_SHOWERS _tracks callee, daughter_length
#   F2a SBND_SHOWER_PDG_FROM_START_SEGMENT  start-segment PDG at 4 sites
#   F2b SBND_SHOWER_PDG_FROM_SHOWER_TYPE    shower type at the inverted site
#   F2c SBND_SHOWER_PDG_EXACT_MUON_TEST     exact ==13 muon test at 2 sites
#   F3  SBND_PI0_ID_SHARED_ALLOCATOR        shared pi0-id stream, no collision
#   F4  SBND_SHOWER_FLAG_PDG_ELECTRON       is_shower gains abs(pdg)==11
#   F5  SBND_SHOWER_LESS_ID_TIEBREAK        shower_less id tie-break (house rule)
for _pr33 in \
    "SBND_DAUGHTER_COUNT_PROTO_MAIN_VERTEX:daughter_count_proto_main_vertex" \
    "SBND_DAUGHTER_COUNT_PROTO_EXAMINE_SHOWERS:daughter_count_proto_examine_showers" \
    "SBND_SHOWER_PDG_FROM_START_SEGMENT:shower_pdg_from_start_segment" \
    "SBND_SHOWER_PDG_FROM_SHOWER_TYPE:shower_pdg_from_shower_type" \
    "SBND_SHOWER_PDG_EXACT_MUON_TEST:shower_pdg_exact_muon_test" \
    "SBND_PI0_ID_SHARED_ALLOCATOR:pi0_id_shared_allocator" \
    "SBND_SHOWER_FLAG_PDG_ELECTRON:shower_flag_pdg_electron" \
    "SBND_SHOWER_LESS_ID_TIEBREAK:shower_less_id_tiebreak" ; do
    _env=${_pr33%%:*}; _key=${_pr33#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr33 _env _key _val
# doc pr/24: isochronous first-segment endpoint finding.  SBND PRODUCTION
# DEFAULT ON since the round-3 flip (owner 2026-08-03) -- EMPTY = no TLA = the
# cfg default = ON at the C++ sizing defaults (40 cm min length, 25 cm max
# drift extent, 0.35 frac, 0.02 quantile, 4 cm diagnostic tube radius, 0.12 min
# sheet aspect).  SBND_ISO_ENDPOINT=0 restores the legacy wire-footprint
# boundary endpoints for an A/B; =1 is now a no-op kept so older runner
# invocations still mean what they said.
if [ "${SBND_ISO_ENDPOINT:-1}" = 0 ]; then
    CATH_TLA+=(--tla-code "iso_endpoint=false")
else
    [ "${SBND_ISO_ENDPOINT:-}" = 1 ] && CATH_TLA+=(--tla-code "iso_endpoint=true")
fi
# doc pr/24 round 3 overrides, validation only (both inert unless
# SBND_ISO_ENDPOINT=1).  SBND_ISO_MIN_ASPECT=0 disables the sheet-aspect gate,
# which is how the aspect distribution is harvested from the DEBUG log without
# a rebuild; SBND_ISO_TUBE_R sets the axis-tube radius in cm.
[ -n "${SBND_ISO_MIN_ASPECT:-}" ] && CATH_TLA+=(--tla-code "iso_endpoint_min_aspect=${SBND_ISO_MIN_ASPECT}")
[ -n "${SBND_ISO_TUBE_R:-}" ] && CATH_TLA+=(--tla-code "iso_endpoint_tube_radius=${SBND_ISO_TUBE_R}")
# doc pr/24 round 5 (sec 18): examine_vertices_3's get_local_extension
# recovery step has no check that it actually extends the vertex (rather than
# retracting it toward the far endpoint) -- worst on an iso_endpoint-picked
# isochronous seed.  DEFAULT ON since the round-6 flip (owner 2026-08-06,
# doc pr/24 sec 19.1) -- EMPTY = no TLA = the cfg default = ON.
# SBND_V3_EXT_GUARD=0 restores the legacy (unguarded) get_local_extension for
# an A/B; =1 is now a no-op kept so older runner invocations still mean what
# they said.
if [ "${SBND_V3_EXT_GUARD:-1}" = 0 ]; then
    CATH_TLA+=(--tla-code "v3_extension_guard=false")
else
    [ "${SBND_V3_EXT_GUARD:-}" = 1 ] && CATH_TLA+=(--tla-code "v3_extension_guard=true")
fi
[ -n "${SBND_V3_EXT_MIN_GAIN:-}" ] && CATH_TLA+=(--tla-code "v3_extension_min_gain=${SBND_V3_EXT_MIN_GAIN}")
# doc pr/67: LOG-ONLY trajectory-coverage probe (why the fitted trajectory does
# not cover the image, worst in isochronous topologies).  Default OFF; the key
# is suppressed in the compiled config unless set, so an unset run is
# byte-identical.  SBND_TRAJ_COVER_PROBE=1 turns the diagnostic lines on.
[ "${SBND_TRAJ_COVER_PROBE:-}" = 1 ] && CATH_TLA+=(--tla-code "traj_cover_probe=true")
# doc pr/96: MEASUREMENT hook for pr/30's P1 port-fidelity gap.  fit_exclusion
# is the SBND config default FALSE and pr/30 sec 12.8 DECLINED flipping it (net
# regression at that operating point, and still blocked on the sec 3.1
# transverse-coordinate unit question inside update_association).  This hook
# exists only so a diagnostic arm can measure it on named events; it is NOT a
# step toward a flip.  EMPTY = no TLA = the job default false = byte-identical.
[ -n "${SBND_FIT_EXCLUSION:-}" ] && CATH_TLA+=(--tla-code "fit_exclusion=${SBND_FIT_EXCLUSION}")
# doc pr/97 D1: deterministic main_pi sentinel in
# shower_clustering_with_nv_from_vertices.  The legacy path compares
# INDETERMINATE stack bytes, so which vertex an other-cluster shower attaches
# to depends on the address-space layout (ASLR, or just the size of the
# environment).  SBND config default FALSE; unset => no TLA => byte-identical.
# SBND_MAIN_PI_INIT=true is the knob-on arm.
[ -n "${SBND_MAIN_PI_INIT:-}" ] && CATH_TLA+=(--tla-code "shower_nv_main_pi_init=${SBND_MAIN_PI_INIT}")
# docs/73 sec 12 (round 3).  Both SBND config default FALSE; unset inherits
# that, =1/=0 forces for an A/B arm.
#   SBND_NU_FALLBACK_DEMOTED   when NO candidate survives TaggerCheckNeutrino's
#                              primary loop, consider demoted mains (evt 65289)
#   SBND_ESVA_IGNORE_EMPTY_2D  eliminate_short_vertex_activities case 5: the
#                              empty-2D-index sentinel is "no information", not
#                              "covered" (evt 78242 cross-cathode junction)
case "${SBND_NU_FALLBACK_DEMOTED:-}" in
    1) CATH_TLA+=(--tla-code "nu_fallback_demoted_mains=true") ;;
    0) CATH_TLA+=(--tla-code "nu_fallback_demoted_mains=false") ;;
esac
case "${SBND_ESVA_IGNORE_EMPTY_2D:-}" in
    1) CATH_TLA+=(--tla-code "esva_ignore_empty_2d=true") ;;
    0) CATH_TLA+=(--tla-code "esva_ignore_empty_2d=false") ;;
esac
# doc pr/67 counterfactual: override find_proto_vertex's HARDCODED main-cluster
# branch-search round budget (2).  DIAGNOSTIC ONLY -- a value > 0 changes
# reconstruction output by design.  Unset = the hardcoded budget stands.
[ -n "${SBND_PR_FIND_OTHER_ROUNDS:-}" ] && CATH_TLA+=(--tla-code "pr_find_other_rounds=${SBND_PR_FIND_OTHER_ROUNDS}")
# doc pr/39: exclude a shower's own start vertex from the end_point
# farthest-vertex search (prototype map_vtx_segs parity, same rule as
# fill_sets's exclude_start_vertex, extended to calculate_kinematics{,_long_muon}).
# SBND production default since 2026-08-06 (owner: "turn it on for SBND"),
# exactly the v3_extension_guard idiom -- EMPTY = no TLA = the cfg default
# (ON).  SBND_SHOWER_ENDPOINT_EXCLUDE_START_VERTEX=0 restores the legacy
# (unguarded) end_point search for an A/B; =1 is now a no-op kept so older
# runner invocations still mean what they said.
if [ "${SBND_SHOWER_ENDPOINT_EXCLUDE_START_VERTEX:-1}" = 0 ]; then
    CATH_TLA+=(--tla-code "shower_endpoint_exclude_start_vertex=false")
else
    [ "${SBND_SHOWER_ENDPOINT_EXCLUDE_START_VERTEX:-}" = 1 ] && CATH_TLA+=(--tla-code "shower_endpoint_exclude_start_vertex=true")
fi
# Steiner TERMINAL filter fidelity (doc pr/29 D1 + D12).
# **SBND PRODUCTION DEFAULT ON since the owner flip 2026-08-04** -- these are
# port bugs, not tuning: the toolkit terminal filter was tighter than the WCP
# prototype in two independent ways and was discarding 47.7% of all Steiner
# terminals on evt 388.  EMPTY = emit no TLA = the cfg default = BOTH ON, so a
# bare run is production (doc 68).  Set them to 0 for the pre-fix arm:
#   SBND_STEINER_WIRE_TOL=0    drop the prototype's one wire of slack.
#   SBND_STEINER_ADJ_SLICE=0   go back to stepping the adjacent-slice lookup by
#                              1, which (the map key being in ticks, 4 per
#                              slice on SBND) never resolves -- the dead branch.
# Both together = the legacy arm every pre-flip comparison needs.
[ -n "${SBND_STEINER_WIRE_TOL:-}" ] && \
    CATH_TLA+=(--tla-code "steiner_terminal_wire_tol=${SBND_STEINER_WIRE_TOL}")
case "${SBND_STEINER_ADJ_SLICE:-}" in
    1) CATH_TLA+=(--tla-code "steiner_terminal_adjacent_slice=true") ;;
    0) CATH_TLA+=(--tla-code "steiner_terminal_adjacent_slice=false") ;;
esac
# Steiner EDGE-WEIGHT charge fidelity (doc pr/29 D2).  **SBND PRODUCTION
# DEFAULT ON since the owner flip 2026-08-04**, same reasoning as the two
# above: create_steiner_tree is called with disable_dead_mix_cell=false and the
# toolkit dropped the argument before the edge-weight charge calculation, so
# create_enhanced_steiner_graph's `= true` default won.  EMPTY = no TLA = the
# cfg default = ON.  SBND_STEINER_EDGE_DEAD_MIX=0 restores the dropped
# argument's effect for the pre-fix arm.
case "${SBND_STEINER_EDGE_DEAD_MIX:-}" in
    1) CATH_TLA+=(--tla-code "steiner_edge_charge_forward_dead_mix=true") ;;
    0) CATH_TLA+=(--tla-code "steiner_edge_charge_forward_dead_mix=false") ;;
esac
# protect_bundle knob overrides (doc pr/23, validation only).  EMPTY = no TLA
# = the cfg default = the SBND operating point.  The _XCUT/_DYZ/_DIS values
# are in CM, converted via wirecell.jsonnet because the C++ takes INTERNAL
# units (the cathode_kink_xcut cm-vs-internal trap, doc pr/20).  0 disables
# the cathode re-join pass (prototype-faithful).
[ -n "${SBND_PROTECT_GRAPH:-}" ] && \
    CATH_TLA+=(--tla-str "protect_graph_name=${SBND_PROTECT_GRAPH}")
[ -n "${SBND_PROTECT_REJOIN_XCUT:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_xcut=(import 'wirecell.jsonnet').cm*${SBND_PROTECT_REJOIN_XCUT}")
[ -n "${SBND_PROTECT_REJOIN_DYZ:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_dyz=(import 'wirecell.jsonnet').cm*${SBND_PROTECT_REJOIN_DYZ}")
[ -n "${SBND_PROTECT_REJOIN_DIS:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_dis=(import 'wirecell.jsonnet').cm*${SBND_PROTECT_REJOIN_DIS}")
# Direction-agreement fallback for a dyz-only re-join failure (doc pr/25,
# SBND evt 489327): DESIGNED, NOT YET the SBND default (cfg default = 0 =
# disabled).  SBND_PROTECT_REJOIN_PERP in CM (0/unset = fallback off);
# SBND_PROTECT_REJOIN_ANGLE in DEGREES (no cm conversion);
# SBND_PROTECT_REJOIN_DIR_RADIUS in CM; SBND_PROTECT_REJOIN_DIR_NPTS a bare
# point-count integer.
[ -n "${SBND_PROTECT_REJOIN_PERP:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_perp=(import 'wirecell.jsonnet').cm*${SBND_PROTECT_REJOIN_PERP}")
[ -n "${SBND_PROTECT_REJOIN_ANGLE:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_angle=${SBND_PROTECT_REJOIN_ANGLE}")
[ -n "${SBND_PROTECT_REJOIN_DIR_RADIUS:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_dir_radius=(import 'wirecell.jsonnet').cm*${SBND_PROTECT_REJOIN_DIR_RADIUS}")
[ -n "${SBND_PROTECT_REJOIN_DIR_NPTS:-}" ] && \
    CATH_TLA+=(--tla-code "protect_cathode_rejoin_dir_npts=${SBND_PROTECT_REJOIN_DIR_NPTS}")
# Demoted-main flag on the outer un-merge (doc pr/20 Part I P2).  EMPTY = emit
# no TLA = the job default null = C++ false = OFF.  Needs the Q/L stage to have
# run with SBND_SAVE_WASMAIN=1, else the visitor warns and flags nothing.
# Env: SBND_RESTORE_DEMOTED_MAINS=1|0.
case "${SBND_RESTORE_DEMOTED_MAINS:-}" in
    1) CATH_TLA+=(--tla-code "restore_demoted_mains=true") ;;
    0) CATH_TLA+=(--tla-code "restore_demoted_mains=false") ;;
esac
# Legacy-tree guard (doc pr/23 sec 4.2).  cfg default TRUE: with the restore
# on, a pctree with no wasmain array ABORTS the job instead of silently
# running pre-pr/20 behaviour.  Pass 0 to DECLARE an intentional legacy-tree
# run (e.g. the pinned valfast PR-tail hubs).
# Env: SBND_REQUIRE_WASMAIN=1|0.
case "${SBND_REQUIRE_WASMAIN:-}" in
    1) CATH_TLA+=(--tla-code "require_provenance=true") ;;
    0) CATH_TLA+=(--tla-code "require_provenance=false") ;;
esac
# Let TGM/STM/FC evaluate those demoted mains (doc pr/20 Part I P3).  Inert
# unless SBND_RESTORE_DEMOTED_MAINS=1 above put the flag there.
# Env: SBND_EVAL_DEMOTED_MAINS=1|0.
case "${SBND_EVAL_DEMOTED_MAINS:-}" in
    1) CATH_TLA+=(--tla-code "evaluate_demoted_mains=true") ;;
    0) CATH_TLA+=(--tla-code "evaluate_demoted_mains=false") ;;
esac
# Exempt a flag_demoted_main cluster from TaggerCheckTGM's main_pair_rejects
# veto (doc pr/25, SBND evt 320029): with tgm_main_pair on, that guard reads a
# per-blob array that is all-zero on every demoted main by construction, so it
# vetoed every demoted-main pair unconditionally, before any CASE-A/CASE-B
# boundary geometry ran.  DESIGNED, NOT YET the SBND default -- changes cosmic
# verdicts, owner sign-off pending.  Only meaningful WITH
# SBND_EVAL_DEMOTED_MAINS=1 above.  Env: SBND_TGM_EXEMPT_DEMOTED_MAIN=1|0.
case "${SBND_TGM_EXEMPT_DEMOTED_MAIN:-}" in
    1) CATH_TLA+=(--tla-code "tgm_exempt_demoted_main=true") ;;
    0) CATH_TLA+=(--tla-code "tgm_exempt_demoted_main=false") ;;
esac
# Act on that verdict (doc pr/20 Part I P4): drop a TGM/STM-tagged companion
# from the neutrino's other_clusters, keeping any shorter than the floor.
# Env: SBND_SKIP_COSMIC_COMPANIONS=1|0  SBND_COSMIC_COMPANION_MIN_LEN=<cm>.
case "${SBND_SKIP_COSMIC_COMPANIONS:-}" in
    1) CATH_TLA+=(--tla-code "skip_cosmic_companions=true") ;;
    0) CATH_TLA+=(--tla-code "skip_cosmic_companions=false") ;;
esac
[ -n "${SBND_COSMIC_COMPANION_MIN_LEN:-}" ] && \
    CATH_TLA+=(--tla-code "cosmic_companion_min_length=${SBND_COSMIC_COMPANION_MIN_LEN}")
# sp_photon_flag (doc pr/26 sec. 8.2): store singlephoton_tagger()'s verdict in
# TaggerInfo::photon_flag, the way prototype NeutrinoID.cxx:271 does.  The port
# ran that tagger and filled its ~90 shw_sp_* BDT features but discarded the
# return value, so the uBooNE tagger ntuple's photon_flag branch is a constant
# 0.  SBND DEFAULT ON (owner 2026-08-03): nothing in the chain reads the field,
# so it moves that one branch and nothing else -- 1215 of 1216 T_tagger
# branch-values are identical across the flip (doc pr/26 sec. 9.3).
# Env: SBND_SP_PHOTON_FLAG=1|0.  Unset = no TLA = the cfg default (now ON);
# pass 0 to reproduce the pre-fix gap.
case "${SBND_SP_PHOTON_FLAG:-}" in
    1) CATH_TLA+=(--tla-code "sp_photon_flag=true") ;;
    0) CATH_TLA+=(--tla-code "sp_photon_flag=false") ;;
esac
# DIAGNOSTIC ONLY.  SBND_NU_SKIP_COSMIC=0 clears both cosmic vetoes in
# TaggerCheckNeutrino (per-main and per-bundle), so neutrino PR runs on an
# in-window main that TGM/STM convicted.  This is how you get track_fit /
# shower_track / vertices layers for an event whose only in-window object is a
# cosmic (SBND evt 116962).  It is NOT an operating point -- production is
# BOTH ON (docs/pr/3 sec. 8, pr/16 sec. 7).  Unset = no TLA = cfg default.
case "${SBND_NU_SKIP_COSMIC:-}" in
    0) CATH_TLA+=(--tla-code "nu_skip_cosmic=false")
       CATH_TLA+=(--tla-code "nu_skip_cosmic_bundle=false") ;;
    1) CATH_TLA+=(--tla-code "nu_skip_cosmic=true")
       CATH_TLA+=(--tla-code "nu_skip_cosmic_bundle=true") ;;
esac
# doc pr/40: track (proton/pion/muon) mis-identified as electron.  Same
# tri-state contract (unset = cfg default, 1 = force on, 0 = force off).
#   F1 SBND_TRACK_PID_PERSIST_DQDX     persist type+mass whenever pdg_code!=0
#   F2 SBND_SHOWER_RECLASS_DQDX_GUARD  spare a decisively proton/muon-like
#                                      segment from wholesale reclassification
#   F3 SBND_SHOWER_TOPO_DQDX_GUARD     same guard inside the topology test
for _pr40 in \
    "SBND_TRACK_PID_PERSIST_DQDX:track_pid_persist_dqdx" \
    "SBND_SHOWER_RECLASS_DQDX_GUARD:shower_reclass_dqdx_guard" \
    "SBND_SHOWER_TOPO_DQDX_GUARD:shower_topo_dqdx_guard" ; do
    _env=${_pr40%%:*}; _key=${_pr40#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40 _env _key _val
# doc pr/40 round 2: two follow-on defects from the pr/40 fix round (zero-KE
# persistence stub, reclass_pinfo negative-KE stub) plus a proton-daughter
# guard.  Same tri-state contract.  F4/F6 are SBND production default ON;
# F5 is STILL default OFF (fires but reverted downstream -- see
# porting_dictionary.md and doc pr/40 round 2; blocked pending round 3).
#   F4 SBND_TRACK_PID_PERSIST_4MOM       segment_cal_4mom unconditionally
#                                        instead of a rest-mass-only stub
#   F5 SBND_SHOWER_PROTON_DAUGHTER_PION  electron -> pion when it fathers a
#                                        PID'd, charge-confirmed proton
#   F6 SBND_RECLASS_NEVER_COMPUTED_KE_FLOOR  never-computed reclass_pinfo
#                                        reads KE==0, not KE==-mass
for _pr40r2 in \
    "SBND_TRACK_PID_PERSIST_4MOM:track_pid_persist_4mom" \
    "SBND_SHOWER_PROTON_DAUGHTER_PION:shower_proton_daughter_pion" \
    "SBND_RECLASS_NEVER_COMPUTED_KE_FLOOR:reclass_never_computed_ke_floor" ; do
    _env=${_pr40r2%%:*}; _key=${_pr40r2#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40r2 _env _key _val
# doc pr/40 round 4: two follow-on defects from round 2/3's F5 fix (relabels
# pdg but not the shower flags; a muon fathering two protons is not
# physical).  Same tri-state contract.  Both default OFF pending gates.
#   F7 SBND_SHOWER_PROTON_DAUGHTER_PION_DISSOLVE  clear shower flags when F5
#                                                  relabels a segment to pion
#   F8 SBND_MUON_MULTI_PROTON_PION                muon -> pion when its far
#                                                  end is a multi-proton
#                                                  (>=2, charge-confirmed)
#                                                  hadronic vertex
for _pr40r4 in \
    "SBND_SHOWER_PROTON_DAUGHTER_PION_DISSOLVE:shower_proton_daughter_pion_dissolve" \
    "SBND_MUON_MULTI_PROTON_PION:muon_multi_proton_pion" ; do
    _env=${_pr40r4%%:*}; _key=${_pr40r4#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40r4 _env _key _val
# doc pr/40 round 5: muon mis-identified as electron, three owner-reported Bee
# cases (84229, 54341, 55715), three independent mechanisms.  Same tri-state
# contract.  All three default OFF pending gates.
#   F9  SBND_TRACK_PID_PERSIST_DQDX_ELECTRON_GUARD  narrows F1 -- no longer
#                                                    rescues an undirected
#                                                    electron guess
#   F10 SBND_SHOWER_CONNECT_MAIN_VERTEX_STRAIGHT_GUARD  excludes a long,
#                                                    straight candidate from
#                                                    the main-vertex EM-shower
#                                                    selection
#   F11 SBND_SHOWER_TRAJ_STRAIGHT_GUARD              same straightness veto
#                                                    on segment_is_shower_
#                                                    trajectory that F3 gave
#                                                    segment_is_shower_topology
for _pr40r5 in \
    "SBND_TRACK_PID_PERSIST_DQDX_ELECTRON_GUARD:track_pid_persist_dqdx_electron_guard" \
    "SBND_SHOWER_CONNECT_MAIN_VERTEX_STRAIGHT_GUARD:shower_connect_main_vertex_straight_guard" \
    "SBND_SHOWER_TRAJ_STRAIGHT_GUARD:shower_traj_straight_guard" ; do
    _env=${_pr40r5%%:*}; _key=${_pr40r5#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40r5 _env _key _val
# doc pr/40 round 6: the boundary-level fixes round 5's G2 measurement
# demanded.  Same tri-state contract.  Both default OFF pending gates.
# doc 77 round 1 (2026-08-24): F13 shower_connect_protected_pion_guard
# removed -- measured dead, never flipped (pr/40:1459).
#   F12 SBND_SHOWER_ABSORB_TRACK_GUARD           shower flood-fill no longer
#                                                 absorbs a confident straight
#                                                 non-electron track
#   F14 SBND_MICHEL_STEM_MUON_RESCUE             Michel stopping-muon rescue
#                                                 reaches a proton-called stem
#                                                 at a multi-prong vertex
for _pr40r6 in \
    "SBND_SHOWER_ABSORB_TRACK_GUARD:shower_absorb_track_guard" \
    "SBND_MICHEL_STEM_MUON_RESCUE:michel_stem_muon_rescue" ; do
    _env=${_pr40r6%%:*}; _key=${_pr40r6#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40r6 _env _key _val
# doc pr/38 Round 3 + doc pr/44 (2026-08-07): PF-tree/image consistency on
# 18255-142421.  Same tri-state contract (unset = cfg default, 1 = force on,
# 0 = force off).
#   SBND_PF_ORPHAN_TRACK_PARENTAGE   barrier-orphaned PF track nodes attach by
#                                    graph topology instead of flat roots
#                                    (DISPLAY-ONLY: moves mc.json only)
#   SBND_SHOWER_LONG_MUON_KEEP_TYPE  multi-segment long-muon pseudo-shower
#                                    keeps its muon start segment (NOT display-
#                                    only: PID/kine/pi0 pairing move)
for _pr44 in \
    "SBND_PF_ORPHAN_TRACK_PARENTAGE:pf_orphan_track_parentage" \
    "SBND_SHOWER_LONG_MUON_KEEP_TYPE:shower_long_muon_keep_type" ; do
    _env=${_pr44%%:*}; _key=${_pr44#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr44 _env _key _val
# doc pr/74 round 2: track/shower separation fixes for the four owner cases.
# Same tri-state contract (unset = cfg default, 1 = force on, 0 = force off).
#   SBND_SHOWER_IN_CASCADE_GUARD    P1: refuse examine_direction's cascade
#                                   e- relabel for a long AND MIP-like segment
#                                   (18345-53361)
#   SBND_MICHEL_STEM_MICHEL_CHECK   P2: F14 Michel rescue requires the far
#                                   subtree to be Michel-sized (18255-90055)
#   SBND_SHOWER_STEM_BACKFILL       K4: absorb the walked-past track stem
#                                   between main vertex and each substantial
#                                   EM shower (18255-90055, 18255-469665)
#   SBND_SHOWER_CONN3_UNREACHABLE   K5 = pr/65 rung 2: conn-3 pseudo-gamma
#                                   promotion of unreachable main-cluster
#                                   segments (18306-142421 seg 7013)
#   SBND_SHOWER_TRAJ_MICHEL_STEM    K6 (round 4): demote a main-vertex
#                                   shower-trajectory stem to a stopping muon
#                                   when its far end is a terminal, large-angle
#                                   Michel (18255-506746 seg 21048)
for _pr74 in \
    "SBND_SHOWER_IN_CASCADE_GUARD:shower_in_cascade_guard" \
    "SBND_MICHEL_STEM_MICHEL_CHECK:michel_stem_michel_check" \
    "SBND_SHOWER_STEM_BACKFILL:shower_stem_backfill" \
    "SBND_SHOWER_CONN3_UNREACHABLE:shower_conn3_unreachable" \
    "SBND_SHOWER_TRAJ_MICHEL_STEM:shower_traj_michel_stem" ; do
    _env=${_pr74%%:*}; _key=${_pr74#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr74 _env _key _val
# doc pr/74 round 2 scalar tunables.  EMPTY = no TLA = cfg default (null =
# the C++ default: 40 cm / 1.3 / 40 cm).  Only read when the owning bool is on.
[ -n "${SBND_SHOWER_IN_MAX_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_in_max_len=${SBND_SHOWER_IN_MAX_LEN}")
[ -n "${SBND_SHOWER_IN_MIP_HI:-}" ] && CATH_TLA+=(--tla-code "shower_in_mip_hi=${SBND_SHOWER_IN_MIP_HI}")
[ -n "${SBND_MICHEL_STEM_MAX_FAR_LEN:-}" ] && CATH_TLA+=(--tla-code "michel_stem_max_far_len=${SBND_MICHEL_STEM_MAX_FAR_LEN}")
[ -n "${SBND_STEM_BACKFILL_MAX_LEN:-}" ] && CATH_TLA+=(--tla-code "stem_backfill_max_len=${SBND_STEM_BACKFILL_MAX_LEN}")
[ -n "${SBND_STEM_BACKFILL_MIP_LO:-}" ] && CATH_TLA+=(--tla-code "stem_backfill_mip_lo=${SBND_STEM_BACKFILL_MIP_LO}")
[ -n "${SBND_STEM_BACKFILL_MIP_HI:-}" ] && CATH_TLA+=(--tla-code "stem_backfill_mip_hi=${SBND_STEM_BACKFILL_MIP_HI}")
[ -n "${SBND_STEM_BACKFILL_MIN_SHOWER_LEN:-}" ] && CATH_TLA+=(--tla-code "stem_backfill_min_shower_len=${SBND_STEM_BACKFILL_MIN_SHOWER_LEN}")
[ -n "${SBND_CONN3_UNREACHABLE_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "conn3_unreachable_min_len=${SBND_CONN3_UNREACHABLE_MIN_LEN}")
# doc pr/84 round 2.  Tri-state bools (unset = cfg default, 1 = on, 0 = off)
# + scalar radii in cm (EMPTY = no TLA = cfg default).  F1/F2 are
# display-only (move mc.json only); conn3_stitch_max moves fits + PF.
# SBND_SHOWER_WALK_VISITED_PARITY (doc pr/91 round 3) joins the same
# tri-state loop below -- unrelated to the pr/84 knobs above it but the
# contract is identical.
for _pr84 in \
    "SBND_PF_DIRECT_WHEN_TOUCHING:pf_direct_when_touching" \
    "SBND_PF_PSEUDO_GAP_FROM_MAIN:pf_pseudo_gap_from_main" \
    "SBND_SHOWER_DEDUP_START_SEG:shower_dedup_start_seg" \
    "SBND_SHOWER_ENDPOINT_SKIP_ORPHAN_VTX:shower_endpoint_skip_orphan_vtx" \
    "SBND_PF_UNIQUE_NODE_IDS:pf_unique_node_ids" \
    "SBND_SHOWER_WALK_VISITED_PARITY:shower_walk_visited_parity" ; do
    _env=${_pr84%%:*}; _key=${_pr84#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr84 _env _key _val
[ -n "${SBND_PF_TOUCH_MAX:-}" ] && CATH_TLA+=(--tla-code "pf_touch_max=${SBND_PF_TOUCH_MAX}")
[ -n "${SBND_CONN3_STITCH_MAX:-}" ] && CATH_TLA+=(--tla-code "conn3_stitch_max=${SBND_CONN3_STITCH_MAX}")
# doc pr/40 round 9 -- the rounds-7+8 straight-track PID guard family + the
# B2 cross-cluster bridge.  Tri-state bools (unset = cfg default, 1 = force
# on, 0 = force off) + two scalars (EMPTY = no TLA = cfg default: C++
# 25 deg / 1.8 cm).  pf_track_bridged_clusters is the PF-side gate widening
# that lets the track BFS traverse an nv-bridged cluster.
for _pr40r9 in \
    "SBND_SHOWER_CONNECT_FROM_VERTICES_STRAIGHT_GUARD:shower_connect_from_vertices_straight_guard" \
    "SBND_SHOWER_CONNECT_START_SEG_STRAIGHT_GUARD:shower_connect_start_seg_straight_guard" \
    "SBND_EXAMINE_DIRECTION_DIRSIGN_SHOWER_IN_GUARD:examine_direction_dirsign_shower_in_guard" \
    "SBND_DAUGHTER_SHOWER_ANGLE_RECLASS_STRAIGHT_GUARD:daughter_shower_angle_reclass_straight_guard" \
    "SBND_SHOWER_TOPO_REEXAM_STRAIGHT_GUARD:shower_topo_reexam_straight_guard" \
    "SBND_SHOWER_NV_BRIDGE_TRACK:shower_nv_bridge_track" \
    "SBND_PF_TRACK_BRIDGED_CLUSTERS:pf_track_bridged_clusters" ; do
    _env=${_pr40r9%%:*}; _key=${_pr40r9#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40r9 _env _key _val
[ -n "${SBND_SFV_KINK_MAX:-}" ] && CATH_TLA+=(--tla-code "sfv_kink_max=${SBND_SFV_KINK_MAX}")
[ -n "${SBND_SHOWER_NV_BRIDGE_MAX_GAP:-}" ] && CATH_TLA+=(--tla-code "shower_nv_bridge_max_gap=${SBND_SHOWER_NV_BRIDGE_MAX_GAP}")
# doc pr/92 -- drop stray satellite showers (overclustered cosmics / second
# neutrinos) from kine_reco_Enu + the Bee PF tree.  Same tri-state contract
# (unset = cfg default, 1 = force on, 0 = force off); scalars EMPTY = no TLA
# = cfg default (null = the C++ defaults: 20 MeV / 8 cm / 60 deg / 45 deg /
# 90 cm / 30 cm / 25 deg).  pf_drop_stray_satellites mirrors the kine-side
# drop in the PF tree; inert unless kine_drop_stray_satellites is also on.
for _pr92 in \
    "SBND_KINE_DROP_STRAY_SATELLITES:kine_drop_stray_satellites" \
    "SBND_PF_DROP_STRAY_SATELLITES:pf_drop_stray_satellites" ; do
    _env=${_pr92%%:*}; _key=${_pr92#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr92 _env _key _val
# doc pr/40 round 10 -- shower_bragg_protect_start_segment: a Shower start
# segment already typed muon/proton with a confident Bragg/dE-dx-template PID
# (particle_score < 1.0) keeps that type through update_particle_type's
# majority vote instead of being relabelled e-.  Same tri-state contract
# (unset = cfg default, 1 = force on, 0 = force off).
for _pr40r10 in \
    "SBND_SHOWER_BRAGG_PROTECT_START_SEGMENT:shower_bragg_protect_start_segment" ; do
    _env=${_pr40r10%%:*}; _key=${_pr40r10#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr40r10 _env _key _val
# doc pr/93 round 3 -- the "electron is really tracks / hadronic-pi0 shower"
# knob family (SBND 18255-55595/348471/69314/292643/315167).  Same tri-state
# contract (unset = cfg default, 1 = force on, 0 = force off).
for _pr93 in \
    "SBND_SHOWER_RECLASS_CASE_B_DQDX_GUARD:shower_reclass_case_b_dqdx_guard" \
    "SBND_SHOWER_ACCEPT_PID_GUARD:shower_accept_pid_guard" \
    "SBND_SHOWER_VOTE_TRACK_PID_COUNTS:shower_vote_track_pid_counts" \
    "SBND_SHOWER_CONE_ABSORB_GUARD:shower_cone_absorb_guard" ; do
    _env=${_pr93%%:*}; _key=${_pr93#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr93 _env _key _val
# doc pr/93 round 4 -- PF-hierarchy fine-tunes (detach track stem, orphan
# track PF/kine emission, cross-cluster straight continuation + bridge).
# Same tri-state contract.
for _pr93r4 in \
    "SBND_SHOWER_DETACH_TRACK_STEM:shower_detach_track_stem" \
    "SBND_KINE_COUNT_ORPHAN_TRACKS:kine_count_orphan_tracks" \
    "SBND_STRAIGHT_CONT_CROSS_CLUSTER:straight_cont_cross_cluster" \
    "SBND_SCCC_BRIDGE_BODY:sccc_bridge_body" \
    "SBND_PF_ORPHAN_CONFIDENT_TRACK:pf_orphan_confident_track" \
    "SBND_PF_TRACK_OWNS_LOOSE_VERTEX:pf_track_owns_loose_vertex" ; do
    _env=${_pr93r4%%:*}; _key=${_pr93r4#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr93r4 _env _key _val
[ -n "${SBND_KINE_ORPHAN_TRACK_MIN:-}" ] && CATH_TLA+=(--tla-code "kine_orphan_track_min=${SBND_KINE_ORPHAN_TRACK_MIN}")
[ -n "${SBND_SCCC_MAX_GAP:-}" ] && CATH_TLA+=(--tla-code "sccc_max_gap=${SBND_SCCC_MAX_GAP}")
[ -n "${SBND_SCCC_KINK_MAX:-}" ] && CATH_TLA+=(--tla-code "sccc_kink_max=${SBND_SCCC_KINK_MAX}")
[ -n "${SBND_SCCC_GAP_ALIGNED:-}" ] && CATH_TLA+=(--tla-code "sccc_gap_aligned=${SBND_SCCC_GAP_ALIGNED}")
[ -n "${SBND_SCCC_KINK_TIGHT:-}" ] && CATH_TLA+=(--tla-code "sccc_kink_tight=${SBND_SCCC_KINK_TIGHT}")
[ -n "${SBND_PF_ORPHAN_TRACK_MIN_CM:-}" ] && CATH_TLA+=(--tla-code "pf_orphan_track_min_cm=${SBND_PF_ORPHAN_TRACK_MIN_CM}")
[ -n "${SBND_SHOWER_PID_GUARD_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_pid_guard_min_len=${SBND_SHOWER_PID_GUARD_MIN_LEN}")
[ -n "${SBND_KINE_SAT_MIN_ENERGY:-}" ] && CATH_TLA+=(--tla-code "kine_sat_min_energy=${SBND_KINE_SAT_MIN_ENERGY}")
[ -n "${SBND_KINE_SAT_PROX_MAX:-}" ] && CATH_TLA+=(--tla-code "kine_sat_prox_max=${SBND_KINE_SAT_PROX_MAX}")
[ -n "${SBND_KINE_SAT_ANGLE_BAD:-}" ] && CATH_TLA+=(--tla-code "kine_sat_angle_bad=${SBND_KINE_SAT_ANGLE_BAD}")
[ -n "${SBND_KINE_SAT_ANGLE_MAIN:-}" ] && CATH_TLA+=(--tla-code "kine_sat_angle_main=${SBND_KINE_SAT_ANGLE_MAIN}")
[ -n "${SBND_KINE_SAT_FAR_DIS:-}" ] && CATH_TLA+=(--tla-code "kine_sat_far_dis=${SBND_KINE_SAT_FAR_DIS}")
[ -n "${SBND_KINE_SAT_AXIS_DIS_CUT:-}" ] && CATH_TLA+=(--tla-code "kine_sat_axis_dis_cut=${SBND_KINE_SAT_AXIS_DIS_CUT}")
[ -n "${SBND_KINE_SAT_CONT_KINK:-}" ] && CATH_TLA+=(--tla-code "kine_sat_cont_kink=${SBND_KINE_SAT_CONT_KINK}")
[ -n "${SBND_KINE_SAT_TRACK_MAX_NSEG:-}" ] && CATH_TLA+=(--tla-code "kine_sat_track_max_nseg=${SBND_KINE_SAT_TRACK_MAX_NSEG}")
[ -n "${SBND_KINE_SAT_EM_FAR_DIS:-}" ] && CATH_TLA+=(--tla-code "kine_sat_em_far_dis=${SBND_KINE_SAT_EM_FAR_DIS}")
# doc pr/74 round 4 K6 scalar tunables.  EMPTY = no TLA = cfg default (null =
# the C++ default: 15 cm / 45 cm / 1.3x / 40 cm / 40 deg).  Only read when
# shower_traj_michel_stem is on.
[ -n "${SBND_MICHEL_STEM_TRAJ_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "michel_stem_traj_min_len=${SBND_MICHEL_STEM_TRAJ_MIN_LEN}")
[ -n "${SBND_MICHEL_STEM_TRAJ_MAX_LEN:-}" ] && CATH_TLA+=(--tla-code "michel_stem_traj_max_len=${SBND_MICHEL_STEM_TRAJ_MAX_LEN}")
[ -n "${SBND_MICHEL_STEM_TRAJ_MIP_LO:-}" ] && CATH_TLA+=(--tla-code "michel_stem_traj_mip_lo=${SBND_MICHEL_STEM_TRAJ_MIP_LO}")
[ -n "${SBND_MICHEL_STEM_TRAJ_MAX_FAR_LEN:-}" ] && CATH_TLA+=(--tla-code "michel_stem_traj_max_far_len=${SBND_MICHEL_STEM_TRAJ_MAX_FAR_LEN}")
[ -n "${SBND_MICHEL_STEM_TRAJ_MIN_KINK_DEG:-}" ] && CATH_TLA+=(--tla-code "michel_stem_traj_min_kink_deg=${SBND_MICHEL_STEM_TRAJ_MIN_KINK_DEG}")
# doc pr/43 round 2 tri-state env overrides (unset = cfg default, 1 = force
# on, 0 = force off):
#   SBND_SINGLE_MUON_PROTON_CHAIN_VETO  vertex muon selection walks the
#                                       degree-2 chain for a disqualifying
#                                       proton (a muon cannot end in one)
#   SBND_SINGLE_MUON_LONG_MUON_CLAIM    long-muon chain claims the vertex
#                                       muon slot; second pdg-13 arm -> pion
#   SBND_PID_FLAG_RECONCILE             late reconciliation pass: forced-e-
#                                       terminal rescue + stale shower-flag/
#                                       wrapper cleanup on confirmed tracks
for _pr43r2 in \
    "SBND_SINGLE_MUON_PROTON_CHAIN_VETO:single_muon_proton_chain_veto" \
    "SBND_SINGLE_MUON_LONG_MUON_CLAIM:single_muon_long_muon_claim" \
    "SBND_PID_FLAG_RECONCILE:pid_flag_reconcile" ; do
    _env=${_pr43r2%%:*}; _key=${_pr43r2#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr43r2 _env _key _val
# doc pr/45 tri-state env overrides (unset = cfg default, 1 = force on,
# 0 = force off):
#   SBND_OTHER_SEG_EMPTY_2D_GUARD    find_other_segments: the -1.0 empty-2D-
#                                    tree sentinel counts as "no information"
#                                    instead of "distance zero" (isochronous
#                                    tail beyond a cathode-crossing cluster's
#                                    segment end can now seed a component)
#   SBND_PSEUDO_SHOWER_TRACK_PAINT   Bee shower_track layer + PrDisplayDump:
#                                    muon-typed (+-13) pseudo-showers paint
#                                    as track, matching the PF tree verdict
for _pr45 in \
    "SBND_OTHER_SEG_EMPTY_2D_GUARD:other_seg_empty_2d_guard" \
    "SBND_PSEUDO_SHOWER_TRACK_PAINT:pseudo_shower_track_paint" ; do
    _env=${_pr45%%:*}; _key=${_pr45#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr45 _env _key _val
# doc pr/46: long-muon stub bridge -- a short (< 6 cm) vertex stub's noisy
# fitted direction blocks the long-muon chain walk at the 15 deg junction
# test; the bridge accepts a > 35 cm MIP continuation up to 45 deg unless
# the junction has another substantial (> 10 cm) track-like arm.
#   SBND_LONG_MUON_STUB_BRIDGE       tri-state: unset = cfg default,
#                                    1 = force on, 0 = force off
for _pr46 in \
    "SBND_LONG_MUON_STUB_BRIDGE:long_muon_stub_bridge" ; do
    _env=${_pr46%%:*}; _key=${_pr46#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr46 _env _key _val
# doc pr/48: back-to-back track fixes (18255-51513/56211/57903/59335/57485;
# nu vertex mid-segment on one unbroken track, dQ/dx rising at BOTH ends).
# two_end_break = the two-end residual-range break pass;
# kink_walk_dqdx_stop / kink_break_protect = the 59335 walk-overshoot +
# EV4-absorption fixes.  Same tri-state contract: unset = cfg default,
# 1 = force on, 0 = force off.
#   SBND_TWO_END_BREAK / SBND_KINK_WALK_DQDX_STOP / SBND_KINK_BREAK_PROTECT
for _pr48 in \
    "SBND_TWO_END_BREAK:two_end_break" \
    "SBND_KINK_WALK_DQDX_STOP:kink_walk_dqdx_stop" \
    "SBND_KINK_BREAK_PROTECT:kink_break_protect" ; do
    _env=${_pr48%%:*}; _key=${_pr48#*:}; _val=${!_env:-}
    [ "$_val" = 1 ] && CATH_TLA+=(--tla-code "$_key=true")
    [ "$_val" = 0 ] && CATH_TLA+=(--tla-code "$_key=false")
done
unset _pr48 _env _key _val
# doc pr/90 round 2: two refinements of the two_end_break pass (mcp1k
# 320865/172832/61681 -- unbroken kink, wrong nu vertex).
# teb_turn_min_arm_frac: route R2's turn argmax only considers indices whose
# PCA arms can each span this fraction of teb_turn_baseline (dimensionless).
# doc 77 round 1 (2026-08-24): teb_second_max removed -- negative on its
# own motivating events (pr/90 sec 8.5).  SBND_TEB_SECOND_MAX no longer wired.
#   SBND_TEB_TURN_MIN_ARM_FRAC
if [ -n "${SBND_TEB_TURN_MIN_ARM_FRAC:-}" ]; then
    CATH_TLA+=(--tla-code "teb_turn_min_arm_frac=${SBND_TEB_TURN_MIN_ARM_FRAC}")
fi
# doc pr/90 round 4 (sec 9.5 D4): the R2 bragg-veto turn (deg).  Unset/empty
# omits (jsonnet default null => C++ default = legacy => byte-identical).
#   SBND_TEB_BRAGG_VETO_TURN
# doc 77 round 4 (2026-09-01): D1 (teb_chain_topology) and D3 (teb_r3_turn /
# teb_r3_hot) removed -- net NEGATIVE, 19 ADVERSE vs 6 toward (pr/90 sec 10.6).
# SBND_TEB_CHAIN_TOPOLOGY / SBND_TEB_R3_TURN / SBND_TEB_R3_HOT no longer wired.
if [ -n "${SBND_TEB_BRAGG_VETO_TURN:-}" ]; then
    CATH_TLA+=(--tla-code "teb_bragg_veto_turn=${SBND_TEB_BRAGG_VETO_TURN}")
fi
# doc pr/49: own-blob-coverage down-weighting in the trajectory fit's 2D
# charge association (18255-57441 V-plane projection ghost).  NUMERIC knob,
# not tri-state: unset = cfg default; any value is passed through verbatim
# (-1 = force off, 0 = force on strict, N > 0 = on with N cells tolerance).
#   SBND_FIT_BLOB_COVERAGE
if [ -n "${SBND_FIT_BLOB_COVERAGE:-}" ]; then
    CATH_TLA+=(--tla-code "fit_blob_coverage=${SBND_FIT_BLOB_COVERAGE}")
fi
# doc pr/50: suspend the pr/49 deweighting during find_proto_vertex (the
# partition-forming stage) -- 172230-class near-vertex robustness.  Boolean
# TLA: unset = cfg default (false = pr/49 behavior); true/false passed
# verbatim.
#   SBND_FIT_BLOB_COVERAGE_DEFER
if [ -n "${SBND_FIT_BLOB_COVERAGE_DEFER:-}" ]; then
    CATH_TLA+=(--tla-code "fit_blob_coverage_defer=${SBND_FIT_BLOB_COVERAGE_DEFER}")
fi
# doc pr/50: main-vertex kink-consistency snap (172230-class near-vertex
# robustness).  Boolean TLA, same contract as the defer knob above.
#   SBND_VERTEX_KINK_SNAP
if [ -n "${SBND_VERTEX_KINK_SNAP:-}" ]; then
    CATH_TLA+=(--tla-code "vertex_kink_snap=${SBND_VERTEX_KINK_SNAP}")
fi
# doc pr/104: main-vertex junction snap (405707/65289/66712/282072/345633
# class: main vertex 2-4 cm off the multi-prong junction).  Boolean TLA,
# same contract as the kink snap; numerics are bare cm/deg/count values,
# unset/empty omits the override (jsonnet default null => byte-identical).
#   SBND_VERTEX_JUNCTION_SNAP  SBND_VJS_RADIUS  SBND_VJS_MIN_ARM
#   SBND_VJS_MIN_PRONGS  SBND_VJS_COLLINEAR  SBND_VJS_FIT_MARGIN  SBND_VJS_FIT_RMS
if [ -n "${SBND_VERTEX_JUNCTION_SNAP:-}" ]; then
    CATH_TLA+=(--tla-code "vertex_junction_snap=${SBND_VERTEX_JUNCTION_SNAP}")
fi
[ -n "${SBND_VJS_RADIUS:-}" ]     && CATH_TLA+=(--tla-code "vjs_radius=${SBND_VJS_RADIUS}")
[ -n "${SBND_VJS_MIN_ARM:-}" ]    && CATH_TLA+=(--tla-code "vjs_min_arm=${SBND_VJS_MIN_ARM}")
[ -n "${SBND_VJS_MIN_PRONGS:-}" ] && CATH_TLA+=(--tla-code "vjs_min_prongs=${SBND_VJS_MIN_PRONGS}")
[ -n "${SBND_VJS_COLLINEAR:-}" ]  && CATH_TLA+=(--tla-code "vjs_collinear=${SBND_VJS_COLLINEAR}")
[ -n "${SBND_VJS_FIT_MARGIN:-}" ] && CATH_TLA+=(--tla-code "vjs_fit_margin=${SBND_VJS_FIT_MARGIN}")
[ -n "${SBND_VJS_FIT_RMS:-}" ]    && CATH_TLA+=(--tla-code "vjs_fit_rms=${SBND_VJS_FIT_RMS}")
#   SBND_VJS_OVERRIDE_KINK_SNAP (boolean TLA, same contract as the snap switch)
if [ -n "${SBND_VJS_OVERRIDE_KINK_SNAP:-}" ]; then
    CATH_TLA+=(--tla-code "vjs_override_kink_snap=${SBND_VJS_OVERRIDE_KINK_SNAP}")
fi
[ -n "${SBND_VJS_MIN_MOVE:-}" ]   && CATH_TLA+=(--tla-code "vjs_min_move=${SBND_VJS_MIN_MOVE}")
# doc pr/51: main-vertex graph audit (near-vertex graph-shape repair --
# duplicate-corridor merge / charge-less-bridge removal / micro-stub absorb
# + re-seat / one refit).  Boolean TLA, same contract as the snap knob.
#   SBND_MAIN_VERTEX_GRAPH_AUDIT
if [ -n "${SBND_MAIN_VERTEX_GRAPH_AUDIT:-}" ]; then
    CATH_TLA+=(--tla-code "main_vertex_graph_audit=${SBND_MAIN_VERTEX_GRAPH_AUDIT}")
fi
# doc pr/51 round 3: op3 satellite-anchor radius (cm), the mvga numeric
# knob that gets its own env (the rest ride the C++ defaults via
# main_vertex_graph_audit alone).  Numeric TLA -- pass a bare cm value, e.g.
# SBND_MVGA_SATELLITE=3.0.  Unset/empty omits the override (jsonnet default
# null => byte-identical).
#   SBND_MVGA_SATELLITE
if [ -n "${SBND_MVGA_SATELLITE:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_satellite=${SBND_MVGA_SATELLITE}")
fi
# doc pr/85: op3 stub-length ceiling (cm), for the Q4 sweep.  Numeric TLA,
# unset/empty omits (C++ default 2.0).
#   SBND_MVGA_STUB
if [ -n "${SBND_MVGA_STUB:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_stub=${SBND_MVGA_STUB}")
fi
# doc pr/85: op1/op3 overlap-fraction gate and op3 point-degeneracy ceiling.
# The pr/85 full-sample adjudication found every adverse >1 cm mover was a
# terminal absorb at overlap=0.75 nfit=4 (admitted by the degeneracy gate)
# while every clean absorb ran at overlap=1.00 -- 0.8/3 blocks exactly that
# class.  Numeric TLAs, unset/empty omits (C++ defaults 0.7 / 4).
#   SBND_MVGA_DUP_FRAC
#   SBND_MVGA_STUB_PTS
if [ -n "${SBND_MVGA_DUP_FRAC:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_dup_frac=${SBND_MVGA_DUP_FRAC}")
fi
if [ -n "${SBND_MVGA_STUB_PTS:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_stub_pts=${SBND_MVGA_STUB_PTS}")
fi
# doc pr/85: op3 re-seat collinearity threshold (deg).  0 DISABLES the
# re-seat sub-case (absorb-only op3) -- the pr/85 mover adjudication found
# both label-set re-seat firings moved the vertex OFF the owner's click
# (280017: 1.64 cm, 314838: 0.60 cm).  Numeric TLA, unset/empty omits.
#   SBND_MVGA_RESEAT_ANGLE
if [ -n "${SBND_MVGA_RESEAT_ANGLE:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_reseat_angle=${SBND_MVGA_RESEAT_ANGLE}")
fi
# doc pr/85: op3 interposed-stub absorb at the main-vertex anchor (boolean;
# inert unless main_vertex_graph_audit) + its far-end collinearity angle
# (deg, C++ default 150).  Same contracts as the mvga knobs above.
#   SBND_MVGA_INTERPOSED
#   SBND_MVGA_INTERPOSED_ANGLE
if [ -n "${SBND_MVGA_INTERPOSED:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_interposed=${SBND_MVGA_INTERPOSED}")
fi
if [ -n "${SBND_MVGA_INTERPOSED_ANGLE:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_interposed_angle=${SBND_MVGA_INTERPOSED_ANGLE}")
fi
# doc pr/86: interposed-splice candidate ceiling, cm (C++ default 0 = use
# mvga_stub; widens only the splice, never the terminal absorb).  Numeric
# TLA, unset/empty omits (jsonnet default null => byte-identical).
#   SBND_MVGA_INTERPOSED_LEN
if [ -n "${SBND_MVGA_INTERPOSED_LEN:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_interposed_len=${SBND_MVGA_INTERPOSED_LEN}")
fi
# doc pr/86 P4: satellite-anchor op3 overlap threshold (fraction; C++
# default 0 = use mvga_dup_frac everywhere).  Numeric TLA, unset/empty
# omits (jsonnet default null => byte-identical).
#   SBND_MVGA_SAT_DUP_FRAC
if [ -n "${SBND_MVGA_SAT_DUP_FRAC:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_sat_dup_frac=${SBND_MVGA_SAT_DUP_FRAC}")
fi
# doc pr/86 P1b: interposed splice at degree-1 main anchors (boolean; C++
# default false).  Boolean TLA, unset/empty omits (jsonnet default false
# => key suppressed => byte-identical).
#   SBND_MVGA_INTERPOSED_DEG1
if [ -n "${SBND_MVGA_INTERPOSED_DEG1:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_interposed_deg1=${SBND_MVGA_INTERPOSED_DEG1}")
fi
# doc pr/86 round 2 R1: op3 post-carry straighten reach past the junction
# (cm; C++ default 0 = concatenation verbatim).  Numeric TLA, unset/empty
# omits (jsonnet default null => byte-identical).
#   SBND_MVGA_SPLICE_STRAIGHTEN
if [ -n "${SBND_MVGA_SPLICE_STRAIGHTEN:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_splice_straighten=${SBND_MVGA_SPLICE_STRAIGHTEN}")
fi
# doc pr/86 round 2 R2: op3.5 junction-collapse radius around the main
# vertex (cm; C++ default 0 = pass skipped).  Numeric TLA, unset/empty
# omits (jsonnet default null => byte-identical).
#   SBND_MVGA_APPROACH_COLLAPSE
if [ -n "${SBND_MVGA_APPROACH_COLLAPSE:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_approach_collapse=${SBND_MVGA_APPROACH_COLLAPSE}")
fi
# doc pr/86 round 2: R1/R2 straight-chain charge-veto radius (cm; C++
# default 0 = the prototype 0.2 cm).  Numeric TLA, unset/empty omits
# (jsonnet default null => byte-identical).
#   SBND_MVGA_STRAIGHTEN_RADIUS
if [ -n "${SBND_MVGA_STRAIGHTEN_RADIUS:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_straighten_radius=${SBND_MVGA_STRAIGHTEN_RADIUS}")
fi
# doc pr/83 r3: the duplicate-corridor round.  op1-only scope radius (cm;
# C++ default 0 = use mvga_radius, -1 = unscoped) and overlap threshold
# (fraction; 0 = use mvga_dup_frac); post-op3 dup pass incl. created
# segments (boolean, class A); interposed-carry prong ceiling (count; 0 =
# unlimited); abandoned-main-cluster dup audit inside swap_main_cluster
# (boolean, Mechanism C).  Numeric/boolean TLAs, unset/empty omits
# (jsonnet defaults null/false => keys suppressed => byte-identical).
# doc 77 round 1 (2026-08-24): mvga_carry_max removed -- not needed, class A
# cleared 8/8 with it OFF (pr/83 r3 sec 8.5).
#   SBND_MVGA_OP1_RADIUS
#   SBND_MVGA_OP1_DUP_FRAC
#   SBND_MVGA_OP1_POST
#   SBND_SWAP_ORPHAN_DUP_AUDIT
if [ -n "${SBND_MVGA_OP1_RADIUS:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_op1_radius=${SBND_MVGA_OP1_RADIUS}")
fi
if [ -n "${SBND_MVGA_OP1_DUP_FRAC:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_op1_dup_frac=${SBND_MVGA_OP1_DUP_FRAC}")
fi
if [ -n "${SBND_MVGA_OP1_POST:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_op1_post=${SBND_MVGA_OP1_POST}")
fi
if [ -n "${SBND_SWAP_ORPHAN_DUP_AUDIT:-}" ]; then
    CATH_TLA+=(--tla-code "swap_orphan_dup_audit=${SBND_SWAP_ORPHAN_DUP_AUDIT}")
fi
# doc pr/83 r4 -- projective duplicate collapse (see wct-pr-perevt.jsonnet)
#   SBND_MVGA_PROJ_DUP_FRAC
#   SBND_MVGA_PROJ_DQDX_RATIO
if [ -n "${SBND_MVGA_PROJ_DUP_FRAC:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_proj_dup_frac=${SBND_MVGA_PROJ_DUP_FRAC}")
fi
if [ -n "${SBND_MVGA_PROJ_DQDX_RATIO:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_proj_dqdx_ratio=${SBND_MVGA_PROJ_DQDX_RATIO}")
fi
if [ -n "${SBND_MVGA_PROJ_ANGLE:-}" ]; then
    CATH_TLA+=(--tla-code "mvga_proj_angle=${SBND_MVGA_PROJ_ANGLE}")
fi
# doc pr/85: carry the old vertex's arms through the snap residual below
# this arc (cm).  Numeric TLA -- pass a bare cm value, e.g.
# SBND_VKS_CARRY_PRONG=1.5.  Unset/empty omits the override (jsonnet
# default null => byte-identical).
#   SBND_VKS_CARRY_PRONG
if [ -n "${SBND_VKS_CARRY_PRONG:-}" ]; then
    CATH_TLA+=(--tla-code "vks_carry_prong=${SBND_VKS_CARRY_PRONG}")
fi
# doc 77 round 1 (2026-08-24): dl_vtx_swap_guard removed -- live A/B
# -36/1014 (pr/89 round 5).  SBND_DL_VTX_SWAP_GUARD no longer wired.
# doc sbnd_xin/docs/pr/106 sec 10: exclusion-free charge cloud for the DL
# vertex net (one extra non-exclusion refit per cluster, fits restored).
# Boolean TLA, same contract.  EMPTY = no TLA = the job default false.
#   SBND_DL_VTX_CLOUD_NO_EXCLUSION
if [ -n "${SBND_DL_VTX_CLOUD_NO_EXCLUSION:-}" ]; then
    CATH_TLA+=(--tla-code "dl_vtx_cloud_no_exclusion=${SBND_DL_VTX_CLOUD_NO_EXCLUSION}")
fi
# doc sbnd_xin/docs/pr/107: dQ/dx fit keeps every trajectory point (prototype
# parity; the toolkit-only pre-dQ/dx form_map_graph pass no longer deletes the
# junction-adjacent points fit_exclusion stripped).  Boolean TLA, same
# contract.  EMPTY = no TLA = the job default false.
#   SBND_DQDX_FIT_KEEP_ALL_POINTS
if [ -n "${SBND_DQDX_FIT_KEEP_ALL_POINTS:-}" ]; then
    CATH_TLA+=(--tla-code "dqdx_fit_keep_all_points=${SBND_DQDX_FIT_KEEP_ALL_POINTS}")
fi
# doc sbnd_xin/docs/pr/75: per-event vertex scoreboard (recording only, read
# by PrDisplayDump for the neutrino-vertex hand scan).  Boolean TLA, same
# contract.  Defaulted to true above when PR_EXTRA_STAGES names pr_display.
#   SBND_VERTEX_SCOREBOARD
if [ -n "${SBND_VERTEX_SCOREBOARD:-}" ]; then
    CATH_TLA+=(--tla-code "vertex_scoreboard=${SBND_VERTEX_SCOREBOARD}")
fi
# doc sbnd_xin/docs/pr/79 sec 10: live-feature harvest (SCN input cloud +
# discarded traditional-path features into the scoreboard dump).  Boolean
# TLA, same contract.  Requires the scoreboard; a truthy value defaults
# SBND_VERTEX_SCOREBOARD=true near the PR_EXTRA_STAGES block above.
#   SBND_DL_VTX_HARVEST
if [ -n "${SBND_DL_VTX_HARVEST:-}" ]; then
    CATH_TLA+=(--tla-code "dl_vtx_harvest=${SBND_DL_VTX_HARVEST}")
fi
# doc pr/51 round 3: apply the traditional main-vertex path's cluster-swap
# decision instead of discarding it.  Boolean TLA, same contract.
#   SBND_MAIN_VERTEX_SWAP_APPLY
if [ -n "${SBND_MAIN_VERTEX_SWAP_APPLY:-}" ]; then
    CATH_TLA+=(--tla-code "main_vertex_swap_apply=${SBND_MAIN_VERTEX_SWAP_APPLY}")
fi
# doc pr/51 round 4: diagnostic-only rough-path probe (near-vertex short-cut
# investigation, path-COST not graph-shape).  Boolean TLA, same contract.
# No graph/fit/segment content is ever changed; every line is TRACE.
#   SBND_ROUGH_PATH_PROBE
if [ -n "${SBND_ROUGH_PATH_PROBE:-}" ]; then
    CATH_TLA+=(--tla-code "rough_path_probe=${SBND_ROUGH_PATH_PROBE}")
fi
# doc pr/51 round 5: steiner gap penalty (the H1 short-cut fix).  Numeric
# TLAs, bare values (scale is dimensionless; the four sub-knobs are cm /
# fractions and ride the C++ defaults 0.25 / 0.5 / 0.3 / 0.2 unless set).
#   SBND_STEINER_GAP_PENALTY  (0 = off; validation scales 1-5)
if [ -n "${SBND_STEINER_GAP_PENALTY:-}" ]; then
    CATH_TLA+=(--tla-code "steiner_gap_penalty=${SBND_STEINER_GAP_PENALTY}")
fi
if [ -n "${SBND_SGP_DEAD_ALPHA:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_dead_alpha=${SBND_SGP_DEAD_ALPHA}")
fi
if [ -n "${SBND_SGP_MIN_EDGE:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_min_edge=${SBND_SGP_MIN_EDGE}")
fi
if [ -n "${SBND_SGP_SAMPLE_STEP:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_sample_step=${SBND_SGP_SAMPLE_STEP}")
fi
if [ -n "${SBND_SGP_POINT_RADIUS:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_point_radius=${SBND_SGP_POINT_RADIUS}")
fi
# doc pr/51 round 6: weak-charge deficit term on the gap flavor.
#   SBND_SGP_WEAK_SCALE  (0 = off; grid scales 1-5)
#   SBND_SGP_WEAK_QREF   (charge units; C++ default 2000)
if [ -n "${SBND_SGP_WEAK_SCALE:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_weak_scale=${SBND_SGP_WEAK_SCALE}")
fi
if [ -n "${SBND_SGP_WEAK_QREF:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_weak_qref=${SBND_SGP_WEAK_QREF}")
fi
# doc pr/73: per-edge DEBUG sentinel for the steiner_graph_gap scan.
#   SBND_SGP_EDGE_PROBE  (literal jsonnet "true"/"false"; default off)
# Log-only; emits one "sgp edge:" line per SCANNED edge.  Diagnostic runs only
# -- it does not change reconstruction, but it does add ~1k lines per cluster.
if [ -n "${SBND_SGP_EDGE_PROBE:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_edge_probe=${SBND_SGP_EDGE_PROBE}")
fi
# doc pr/73 round 2, fix F3a: cap (cm) on how far the round-6 penalized route
# may stray from the unpenalized one in do_rough_path; over the cap the BASE
# route is kept.  C++ default -1 = off (unbounded, legacy).
#   SBND_SGP_MAX_SEP  (cm; -1 = off.  NB 0 is a real cap -- reject any
#                      excursion -- so "off" is a NEGATIVE value, not 0.)
if [ -n "${SBND_SGP_MAX_SEP:-}" ]; then
    CATH_TLA+=(--tla-code "sgp_max_sep=${SBND_SGP_MAX_SEP}")
fi
# doc pr/83: orient break_segment() splits to the wcpt path (find_vertices)
# instead of boost source/target; a reversed edge otherwise yields crossed
# children with vertex fits on the wrong track ends and stacked duplicate
# trajectories (mcp1k 283040/59899/72586).  C++ default false.
#   SBND_BREAK_SEG_ORIENT  (literal jsonnet "true"/"false")
if [ -n "${SBND_BREAK_SEG_ORIENT:-}" ]; then
    CATH_TLA+=(--tla-code "break_seg_orient=${SBND_BREAK_SEG_ORIENT}")
fi
# doc pr/51 round 7: robust vertex fit (mvfit_robust + satellites).
#   SBND_MVFIT_ROBUST      (true/false; escape for A/B: false)
#   SBND_MVFIT_MAIN_ONLY   (true/false; C++ default true)
#   SBND_MVFIT_MIN_LEN / RIN_MARGIN / ROUT_MIN / ROUT_MAX / PRIOR_RANGE (cm)
#   SBND_MVFIT_ROUT_FRAC / ANGLE (deg) / MIN_PTS / MIN_ANISO
for _pr51r7 in "SBND_MVFIT_ROBUST:mvfit_robust" \
               "SBND_MVFIT_MAIN_ONLY:mvfit_main_only" \
               "SBND_MVFIT_MIN_LEN:mvfit_min_len" \
               "SBND_MVFIT_RIN_MARGIN:mvfit_rin_margin" \
               "SBND_MVFIT_ROUT_FRAC:mvfit_rout_frac" \
               "SBND_MVFIT_ROUT_MIN:mvfit_rout_min" \
               "SBND_MVFIT_ROUT_MAX:mvfit_rout_max" \
               "SBND_MVFIT_ANGLE:mvfit_angle" \
               "SBND_MVFIT_MIN_PTS:mvfit_min_pts" \
               "SBND_MVFIT_MIN_ANISO:mvfit_min_aniso" \
               "SBND_MVFIT_PRIOR_RANGE:mvfit_prior_range"; do
    _env=${_pr51r7%%:*}; _key=${_pr51r7#*:}; _val=${!_env:-}
    if [ -n "$_val" ]; then
        CATH_TLA+=(--tla-code "$_key=$_val")
    fi
done
# doc pr/54: keep well-supported isolated residual segments in
# find_other_segments (18255-142421 separated EM shower with no fitted
# trajectory).  Boolean TLA, same contract; the two numeric floors ride the
# C++ defaults (25 points / 3 cm) unless their own envs are set (bare
# values: integer count, cm).
#   SBND_OTHER_SEG_KEEP_ISOLATED
if [ -n "${SBND_OTHER_SEG_KEEP_ISOLATED:-}" ]; then
    CATH_TLA+=(--tla-code "other_seg_keep_isolated=${SBND_OTHER_SEG_KEEP_ISOLATED}")
fi
if [ -n "${SBND_OTHER_SEG_KEEP_ISOLATED_MIN_POINTS:-}" ]; then
    CATH_TLA+=(--tla-code "other_seg_keep_isolated_min_points=${SBND_OTHER_SEG_KEEP_ISOLATED_MIN_POINTS}")
fi
if [ -n "${SBND_OTHER_SEG_KEEP_ISOLATED_MIN_LENGTH:-}" ]; then
    CATH_TLA+=(--tla-code "other_seg_keep_isolated_min_length=${SBND_OTHER_SEG_KEEP_ISOLATED_MIN_LENGTH}")
fi
# doc pr/102 P1: the OR-disjunct on the pr/54 keep -- len_admit (cm) admits
# any candidate at least that long.  EMPTY = no TLA = the C++ default 0 = off,
# byte-identical.
#   SBND_OSEG_LEN_ADMIT (cm)
# doc 77 round 4 (2026-09-01): P1's min_nnf disjunct removed -- validation
# FAILED at 4, named nue loss at 8.  SBND_OSEG_MIN_NNF no longer wired.
if [ -n "${SBND_OSEG_LEN_ADMIT:-}" ]; then
    CATH_TLA+=(--tla-code "other_seg_keep_isolated_len_admit=${SBND_OSEG_LEN_ADMIT}")
fi
# doc 77 round 1 (2026-08-24): other_seg_uncover_3d (pr/102 P2) removed --
# 23 ADVERSE movers, stays OFF.  SBND_OSEG_UNCOVER_3D no longer wired.
# doc pr/67 round 3 (S2): size gate on the isochronous snap in
# find_other_segments -- the machinery that ATTACHES a short isochronously
# displaced branch to its parent.  Bare value in cm; unset means the C++
# default 10.0 (legacy), which is byte-identical to pre-pr/67.  The doc pr/67
# branches sit at dir_mag 4.3-4.7 cm, so a value near 4 admits them.
#   SBND_ISO_SNAP_MIN_DIR_MAG (cm)
if [ -n "${SBND_ISO_SNAP_MIN_DIR_MAG:-}" ]; then
    CATH_TLA+=(--tla-code "iso_snap_min_dir_mag=${SBND_ISO_SNAP_MIN_DIR_MAG}")
fi
# doc pr/59 round 2 (18255-142421 seg 20; 116944-71372 segs
# 19052/19053/136199): per-cluster re-association rescue for a segment
# created after its cluster's clustering_points pass, left with a null
# associate_points cloud (zero shower_track-global points, energy fallback to
# the sparse fit polyline).  Boolean TLA, same contract.
#   SBND_ASSOC_FULL_RECLUSTER
if [ -n "${SBND_ASSOC_FULL_RECLUSTER:-}" ]; then
    CATH_TLA+=(--tla-code "assoc_full_recluster=${SBND_ASSOC_FULL_RECLUSTER}")
fi
# doc pr/64 round 7 (18259-18625: 12-18 pt blob at PF segment 126042's own
# fit endpoint, present in img charge but absent from
# shower_track/associate_points): reassign, instead of drop, a point that
# loses (or never enters) clustering_points_segments' Stage-C ghost removal
# to a SAME-cluster segment that actually wins the global 2D projection
# contest.  Boolean TLA, same contract.
#   SBND_ASSOC_REASSIGN_ORPHANS
if [ -n "${SBND_ASSOC_REASSIGN_ORPHANS:-}" ]; then
    CATH_TLA+=(--tla-code "assoc_reassign_orphans=${SBND_ASSOC_REASSIGN_ORPHANS}")
fi
# doc pr/64 round 8 (same 18259-18625 blob: examine_structure_final_1/_1p/_3,
# called unconditionally inside determine_main_vertex, merge a short/
# duplicate/degenerate segment into a surviving neighbor without carrying its
# associate_points forward).  When the deleted segment had non-empty
# associate_points, clears the survivor's too, so pr/59's
# reassociate_cluster_orphans any_orphan trigger correctly re-fires.  Boolean
# TLA, same contract.
#   SBND_ASSOC_CLEAR_ON_MERGE
if [ -n "${SBND_ASSOC_CLEAR_ON_MERGE:-}" ]; then
    CATH_TLA+=(--tla-code "assoc_clear_on_merge=${SBND_ASSOC_CLEAR_ON_MERGE}")
fi
# doc pr/72 round 2: examine_structure_3 stub guard (18255-196649).  Bool
# TLA, same contract as SBND_ASSOC_CLEAR_ON_MERGE (pass-through, must be the
# literal jsonnet string "true"/"false").  Numeric/bool sub-params are bare
# value pass-throughs -- unset means the component keeps its own C++
# default (fitted from a 117-event census, see doc pr/72 round 2).
#   SBND_ES3_STUB_GUARD
if [ -n "${SBND_ES3_STUB_GUARD:-}" ]; then
    CATH_TLA+=(--tla-code "es3_stub_guard=${SBND_ES3_STUB_GUARD}")
fi
#   SBND_ES3SG_STUB_MAX (cm)
[ -n "${SBND_ES3SG_STUB_MAX:-}" ] && \
    CATH_TLA+=(--tla-code "es3sg_stub_max=${SBND_ES3SG_STUB_MAX}")
#   SBND_ES3SG_LEN_RATIO
[ -n "${SBND_ES3SG_LEN_RATIO:-}" ] && \
    CATH_TLA+=(--tla-code "es3sg_len_ratio=${SBND_ES3SG_LEN_RATIO}")
#   SBND_ES3SG_ANG3_MIN (degrees)
[ -n "${SBND_ES3SG_ANG3_MIN:-}" ] && \
    CATH_TLA+=(--tla-code "es3sg_ang3_min=${SBND_ES3SG_ANG3_MIN}")
#   SBND_ES3SG_ANG_RATIO
[ -n "${SBND_ES3SG_ANG_RATIO:-}" ] && \
    CATH_TLA+=(--tla-code "es3sg_ang_ratio=${SBND_ES3SG_ANG_RATIO}")
#   SBND_ES3SG_REQUIRE_TERMINAL (literal jsonnet "true"/"false")
[ -n "${SBND_ES3SG_REQUIRE_TERMINAL:-}" ] && \
    CATH_TLA+=(--tla-code "es3sg_require_terminal=${SBND_ES3SG_REQUIRE_TERMINAL}")
# doc pr/65 round 3 (18259-54095 PF-root orphan mu-/e- fragments): rung 1
# relaxes the shower absorbers' cluster()==main_cluster guards to a
# main_vertex-reachability test so kept-isolated pr/54 residuals can be
# absorbed; rung 3 replaces the orphan net's fabricated root-level PF node
# with an audit log line (display-only, moves ONLY mc.json).  Boolean TLAs,
# value passed verbatim (true/false), same contract as the pr/54 hook above.
#   SBND_SHOWER_ABSORB_UNREACHABLE_MAIN
#   SBND_PF_ORPHAN_AUDIT_ONLY
if [ -n "${SBND_SHOWER_ABSORB_UNREACHABLE_MAIN:-}" ]; then
    CATH_TLA+=(--tla-code "shower_absorb_unreachable_main=${SBND_SHOWER_ABSORB_UNREACHABLE_MAIN}")
fi
if [ -n "${SBND_PF_ORPHAN_AUDIT_ONLY:-}" ]; then
    CATH_TLA+=(--tla-code "pf_orphan_audit_only=${SBND_PF_ORPHAN_AUDIT_ONLY}")
fi
# doc pr/43 round 1 (the F1 family: muon_chain_proton_veto,
# shower_type_cache_refresh, shower_traj_dqdx_guard, shower_traj_chain_pion,
# kine_shower_vertex_barrier) was ROLLED BACK on 2026-08-07 -- the owner asked
# for the five knobs to be pulled from the code entirely rather than left
# dead-OFF (toolkit 225d7e7e, revert of 4aabef3e).  The C++ and the cfg keys
# went with it; this env->TLA block did not, and was left emitting --tla-code
# for five top-level parameters that wct-pr-perevt.jsonnet no longer declares.
# That is a HARD jsonnet error (wcsonnet aborts, rc=134), not a silent no-op,
# so the vars were landmines rather than dead weight.  Removed 2026-08-22
# (doc pr/109 sec 9.8).  An audit of all 305 TLA names this runner can emit
# found these five and no others.  The three NARROWER round-2 knobs that
# replaced them are live and are handled by the _pr43r2 block above.
# DL (SCN) neutrino-vertex weights (doc pr/24 attribution arms).  UNSET = emit
# no TLA = the cfg default = the SBND operating point (DL vertex ON, doc pr/4).
# SBND_DL_WEIGHTS='' selects the geometric vertex -- the arm that isolates a
# DL-vertex effect from a PR-structure one.  Set-but-empty is honoured, hence
# the ${VAR+x} test rather than ${VAR:-}.
[ -n "${SBND_DL_WEIGHTS+x}" ] && CATH_TLA+=(--tla-str "dl_weights=${SBND_DL_WEIGHTS}")
# DL re-rank operating point (doc pr/79 deployment A/B).  UNSET = no TLA = the
# cfg defaults (min_accept 4.0, top_k 5, pinned in sbnd/clus.jsonnet since
# 2026-07-30).  Numeric values, passed as --tla-code.
[ -n "${SBND_DL_VTX_MIN_ACCEPT:-}" ] && CATH_TLA+=(--tla-code "dl_vtx_min_accept_score=${SBND_DL_VTX_MIN_ACCEPT}")
[ -n "${SBND_DL_VTX_TOP_K:-}" ] && CATH_TLA+=(--tla-code "dl_vtx_top_k=${SBND_DL_VTX_TOP_K}")
# doc pr/105: DL vertex WITHOUT the composite re-rank (legacy single-argmax
# branch: top voxel snapped, dl_vtx_cut 2.5 cm gate, else the traditional
# vertex).  EMPTY = no TLA = the job default true (production).  Strategy 3.1
# of the vertex-selection comparison; pass false for the no-rerank arm.
[ -n "${SBND_DL_VTX_RERANK:-}" ] && CATH_TLA+=(--tla-code "dl_vtx_rerank=${SBND_DL_VTX_RERANK}")
# doc pr/112 sec 11: the DUAL CHAIN -- a second, exclusion-free PR pass
# suggests the neutrino vertex; production decides.  EMPTY = no TLA = the job
# default (off, byte-identical).  SBND_DL_VTX_DUAL_CHAIN=true runs the pass;
# SBND_DUAL_CHAIN_TRANSFER=true lets it move the vertex (unset = PROBE: the
# agreement flag only).  MODE snap|voxels|union (string), TRANSFER_MAX in cm,
# ALLOW_CLUSTER_SWAP true|false, VTX_WEIGHT number (union only).
[ -n "${SBND_DL_VTX_DUAL_CHAIN:-}" ] && CATH_TLA+=(--tla-code "dl_vtx_dual_chain=${SBND_DL_VTX_DUAL_CHAIN}")
[ -n "${SBND_DUAL_CHAIN_MODE:-}" ] && CATH_TLA+=(--tla-str "dual_chain_mode=${SBND_DUAL_CHAIN_MODE}")
[ -n "${SBND_DUAL_CHAIN_TRANSFER:-}" ] && CATH_TLA+=(--tla-code "dual_chain_transfer=${SBND_DUAL_CHAIN_TRANSFER}")
[ -n "${SBND_DUAL_CHAIN_TRANSFER_MAX:-}" ] && CATH_TLA+=(--tla-code "dual_chain_transfer_max=${SBND_DUAL_CHAIN_TRANSFER_MAX}")
[ -n "${SBND_DUAL_CHAIN_ALLOW_CLUSTER_SWAP:-}" ] && CATH_TLA+=(--tla-code "dual_chain_allow_cluster_swap=${SBND_DUAL_CHAIN_ALLOW_CLUSTER_SWAP}")
[ -n "${SBND_DUAL_CHAIN_VTX_WEIGHT:-}" ] && CATH_TLA+=(--tla-code "dual_chain_vtx_weight=${SBND_DUAL_CHAIN_VTX_WEIGHT}")

# doc 84 round 1: long-muon chain + MCS knobs.  EMPTY = no TLA = job defaults
# (P1/P5 flip with the doc 84 round 1 production commit; P2/P3 HOLD OFF).
# Env: SBND_LONG_MUON_RANGE_FALLBACK=<0|1> SBND_LONG_MUON_ANGLE_RELAX=<0|1>
#      SBND_LONG_MUON_ANGLE_RELAX_DEG=<deg> SBND_LONG_MUON_STUB_BRIDGE_LEN=<cm>
#      SBND_MCS_MUON_SOURCE=<pf_muon|long_muon|longest_segment|long_muon_else_pf>
#      SBND_MCS_RANGE_COMPARATOR_CHAIN=<0|1>
#      SBND_MCS_BRIDGED_MEMBERS=<0|1>          (doc 84 round 3)
[ -n "${SBND_LONG_MUON_RANGE_FALLBACK:-}" ] && CATH_TLA+=(--tla-code "long_muon_range_empty_chain_fallback=$([ "${SBND_LONG_MUON_RANGE_FALLBACK}" = 0 ] && echo false || echo true)")
[ -n "${SBND_LONG_MUON_ANGLE_RELAX:-}" ] && CATH_TLA+=(--tla-code "long_muon_angle_relax_long=$([ "${SBND_LONG_MUON_ANGLE_RELAX}" = 0 ] && echo false || echo true)")
[ -n "${SBND_LONG_MUON_ANGLE_RELAX_DEG:-}" ] && CATH_TLA+=(--tla-code "long_muon_angle_relax_deg=${SBND_LONG_MUON_ANGLE_RELAX_DEG}")
[ -n "${SBND_LONG_MUON_STUB_BRIDGE_LEN:-}" ] && CATH_TLA+=(--tla-code "long_muon_stub_bridge_len=${SBND_LONG_MUON_STUB_BRIDGE_LEN}")
[ -n "${SBND_MCS_MUON_SOURCE:-}" ] && CATH_TLA+=(--tla-str "mcs_muon_source=${SBND_MCS_MUON_SOURCE}")
[ -n "${SBND_MCS_RANGE_COMPARATOR_CHAIN:-}" ] && CATH_TLA+=(--tla-code "mcs_range_comparator_chain=$([ "${SBND_MCS_RANGE_COMPARATOR_CHAIN}" = 0 ] && echo false || echo true)")
[ -n "${SBND_MCS_BRIDGED_MEMBERS:-}" ] && CATH_TLA+=(--tla-code "mcs_bridged_members=$([ "${SBND_MCS_BRIDGED_MEMBERS}" = 0 ] && echo false || echo true)")
# doc 84 round 2: members-geometry + cathode-bridge (value knobs in cm/deg)
[ -n "${SBND_LONG_MUON_MEMBERS_GEOMETRY:-}" ] && CATH_TLA+=(--tla-code "long_muon_members_geometry=$([ "${SBND_LONG_MUON_MEMBERS_GEOMETRY}" = 0 ] && echo false || echo true)")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge=$([ "${SBND_LONG_MUON_CATHODE_BRIDGE}" = 0 ] && echo false || echo true)")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_GAP:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_gap=${SBND_LONG_MUON_CATHODE_BRIDGE_GAP}")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_ANGLE:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_angle=${SBND_LONG_MUON_CATHODE_BRIDGE_ANGLE}")
# doc 84 round 4 -- the three admission misses (G1 lever / G2 track partner /
# G3 short-gap waiver).  EMPTY = cfg default = C++ legacy.
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_LEVER:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_lever=${SBND_LONG_MUON_CATHODE_BRIDGE_LEVER}")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_TRACK_PARTNER:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_track_partner=$([ "${SBND_LONG_MUON_CATHODE_BRIDGE_TRACK_PARTNER}" = 0 ] && echo false || echo true)")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_SHORT_GAP:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_short_gap=${SBND_LONG_MUON_CATHODE_BRIDGE_SHORT_GAP}")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_SHORT_GAP_ANGLE:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_short_gap_angle=${SBND_LONG_MUON_CATHODE_BRIDGE_SHORT_GAP_ANGLE}")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_SHORT_GAP_LEN:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_short_gap_len=${SBND_LONG_MUON_CATHODE_BRIDGE_SHORT_GAP_LEN}")
# doc pr/147: admit BOTH sides of the cathode bridge on track-likeness instead
# of PID.  EMPTY env = no TLA = the job default (false) = byte-identical.
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_TRACK_TYPES:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_track_types=$([ "${SBND_LONG_MUON_CATHODE_BRIDGE_TRACK_TYPES}" = 0 ] && echo false || echo true)")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_TRK_DQDX_LO:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_trk_dqdx_lo=${SBND_LONG_MUON_CATHODE_BRIDGE_TRK_DQDX_LO}")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_TRK_DQDX_HI:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_trk_dqdx_hi=${SBND_LONG_MUON_CATHODE_BRIDGE_TRK_DQDX_HI}")
[ -n "${SBND_LONG_MUON_CATHODE_BRIDGE_TRK_STRAIGHT:-}" ] && CATH_TLA+=(--tla-code "long_muon_cathode_bridge_trk_straight=${SBND_LONG_MUON_CATHODE_BRIDGE_TRK_STRAIGHT}")

# doc pr/128 -- PF/kine completeness.  EMPTY env = no TLA = the job default
# false = byte-identical.  PF knobs move only the picture; the KINE twins move
# kine_reco_Enu and are approved separately.
[ -n "${SBND_PF_ORPHAN_NEAR_CROSS_CLUSTER:-}" ] && CATH_TLA+=(--tla-code "pf_orphan_near_cross_cluster=$([ "${SBND_PF_ORPHAN_NEAR_CROSS_CLUSTER}" = 0 ] && echo false || echo true)")
[ -n "${SBND_PF_ORPHAN_NEAR_GAP:-}" ] && CATH_TLA+=(--tla-code "pf_orphan_near_gap_cm=${SBND_PF_ORPHAN_NEAR_GAP}")
[ -n "${SBND_PF_ORPHAN_NEAR_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "pf_orphan_near_min_len_cm=${SBND_PF_ORPHAN_NEAR_MIN_LEN}")
[ -n "${SBND_PF_ORPHAN_NEAR_END_TOL:-}" ] && CATH_TLA+=(--tla-code "pf_orphan_near_end_tol_cm=${SBND_PF_ORPHAN_NEAR_END_TOL}")
[ -n "${SBND_PF_ORPHAN_NEAR_KINK:-}" ] && CATH_TLA+=(--tla-code "pf_orphan_near_kink_deg=${SBND_PF_ORPHAN_NEAR_KINK}")
[ -n "${SBND_PF_CONN4_NEAR:-}" ] && CATH_TLA+=(--tla-code "pf_conn4_near_candidate=$([ "${SBND_PF_CONN4_NEAR}" = 0 ] && echo false || echo true)")
[ -n "${SBND_PF_CONN4_NEAR_GAP:-}" ] && CATH_TLA+=(--tla-code "pf_conn4_near_gap_cm=${SBND_PF_CONN4_NEAR_GAP}")
[ -n "${SBND_KINE_NEAR_CROSS_CLUSTER:-}" ] && CATH_TLA+=(--tla-code "kine_count_near_cross_cluster=$([ "${SBND_KINE_NEAR_CROSS_CLUSTER}" = 0 ] && echo false || echo true)")
[ -n "${SBND_KINE_NEAR_GAP:-}" ] && CATH_TLA+=(--tla-code "kine_near_gap_cm=${SBND_KINE_NEAR_GAP}")
[ -n "${SBND_KINE_NEAR_MIN_LEN:-}" ] && CATH_TLA+=(--tla-code "kine_near_min_len_cm=${SBND_KINE_NEAR_MIN_LEN}")
[ -n "${SBND_KINE_NEAR_END_TOL:-}" ] && CATH_TLA+=(--tla-code "kine_near_end_tol_cm=${SBND_KINE_NEAR_END_TOL}")
[ -n "${SBND_KINE_NEAR_KINK:-}" ] && CATH_TLA+=(--tla-code "kine_near_kink_deg=${SBND_KINE_NEAR_KINK}")
[ -n "${SBND_KINE_CONN4_NEAR:-}" ] && CATH_TLA+=(--tla-code "kine_count_conn4_near=$([ "${SBND_KINE_CONN4_NEAR}" = 0 ] && echo false || echo true)")
[ -n "${SBND_KINE_CONN4_NEAR_GAP:-}" ] && CATH_TLA+=(--tla-code "kine_conn4_near_gap_cm=${SBND_KINE_CONN4_NEAR_GAP}")
# doc pr/129: pointing test on the guard-freed kine pool.  EMPTY = no TLA = the
# job default 0 = no test = byte-identical.
[ -n "${SBND_KINE_GF_IMPACT:-}" ] && CATH_TLA+=(--tla-code "kine_guard_freed_impact=${SBND_KINE_GF_IMPACT}")
[ -n "${SBND_KINE_GF_MISS_DEG:-}" ] && CATH_TLA+=(--tla-code "kine_guard_freed_miss_deg=${SBND_KINE_GF_MISS_DEG}")
# doc pr/132: the pi0 round.  EMPTY = no TLA = the job default = byte-identical.
# _FUDGE overrides the EM charge scale (C++ default 0.8, jsonnet may flip it);
# the five finder knobs default to the legacy hard-coded constants.
[ -n "${SBND_KINE_SHOWER_FUDGE:-}" ] && CATH_TLA+=(--tla-code "kine_shower_fudge_factor=${SBND_KINE_SHOWER_FUDGE}")
[ -n "${SBND_PI0_MASS_OFFSET:-}" ] && CATH_TLA+=(--tla-code "pi0_mass_offset=${SBND_PI0_MASS_OFFSET}")
[ -n "${SBND_PI0_ASSOC_ANGLE:-}" ] && CATH_TLA+=(--tla-code "pi0_assoc_angle_deg=${SBND_PI0_ASSOC_ANGLE}")
[ -n "${SBND_PI0_ATTACH_MIN_MEV:-}" ] && CATH_TLA+=(--tla-code "pi0_attached_partner_min_mev=${SBND_PI0_ATTACH_MIN_MEV}")
[ -n "${SBND_PI0_NV_MAX_PRONGS:-}" ] && CATH_TLA+=(--tla-code "pi0_nv_max_prongs=${SBND_PI0_NV_MAX_PRONGS}")
# doc pr/132 round 2: the rescue family + path-2 quality gate.  EMPTY = no TLA = job default.
[ -n "${SBND_PI0_READMIT_RETYPED:-}" ] && CATH_TLA+=(--tla-code "pi0_readmit_retyped=$([ "${SBND_PI0_READMIT_RETYPED}" = 0 ] && echo false || echo true)")
[ -n "${SBND_PI0_ADMIT_TYPE3:-}" ] && CATH_TLA+=(--tla-code "pi0_admit_type3=$([ "${SBND_PI0_ADMIT_TYPE3}" = 0 ] && echo false || echo true)")
[ -n "${SBND_PI0_CRUMB_MEV:-}" ] && CATH_TLA+=(--tla-code "pi0_crumb_assoc_mev=${SBND_PI0_CRUMB_MEV}")
[ -n "${SBND_PI0_NV_VTX_SHIFT:-}" ] && CATH_TLA+=(--tla-code "pi0_nv_max_vtx_shift_cm=${SBND_PI0_NV_VTX_SHIFT}")
[ -n "${SBND_PI0_NV_MASS_WIN:-}" ] && CATH_TLA+=(--tla-code "pi0_nv_mass_window_mev=${SBND_PI0_NV_MASS_WIN}")
# doc pr/132 round 3: virtual collinear merge of detached fragments at pairing time.  EMPTY = no TLA = job default 0 = off.
[ -n "${SBND_PI0_COLLINEAR_DEG:-}" ] && CATH_TLA+=(--tla-code "pi0_collinear_merge_deg=${SBND_PI0_COLLINEAR_DEG}")
# doc pr/132 round 4: the NC vertex-in-shower partner floor.  EMPTY = no TLA = job default off.
# doc 77 round 4 (2026-09-01): K4 (pi0_nv_allow_type2), K14 (pi0_nv_retry_paired)
# and K15 (pi0_reseat_start_assoc) removed -- ZERO NC rescues over two rounds,
# K15 moved nothing.  Their SBND_PI0_* envs are no longer wired.
[ -n "${SBND_PI0_NV_PARTNER_MEV:-}" ] && CATH_TLA+=(--tla-code "pi0_nv_partner_min_mev=${SBND_PI0_NV_PARTNER_MEV}")
# doc pr/132 round 5: build-time EM collinear-fragment merge.  EMPTY = no TLA = job default off.
[ -n "${SBND_EM_COLLINEAR_DEG:-}" ] && CATH_TLA+=(--tla-code "shower_em_collinear_deg=${SBND_EM_COLLINEAR_DEG}")
[ -n "${SBND_EM_COLLINEAR_DIS:-}" ] && CATH_TLA+=(--tla-code "shower_em_collinear_dis_cm=${SBND_EM_COLLINEAR_DIS}")
[ -n "${SBND_EM_COLLINEAR_HOST:-}" ] && CATH_TLA+=(--tla-code "shower_em_collinear_host_mev=${SBND_EM_COLLINEAR_HOST}")
# doc pr/132 round 6: EM shower start back-extension.  EMPTY = no TLA = job default off.
[ -n "${SBND_EM_BACKEXT_PERP:-}" ] && CATH_TLA+=(--tla-code "shower_em_backext_perp_cm=${SBND_EM_BACKEXT_PERP}")
[ -n "${SBND_EM_BACKEXT_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_em_backext_len_cm=${SBND_EM_BACKEXT_LEN}")
# doc pr/132 round 7 (K18): acceptance-aware fragment merge reach, cm.  EMPTY = no TLA = the job default 0 (off).
[ -n "${SBND_PI0_ACCEPT_MERGE:-}" ] && CATH_TLA+=(--tla-code "pi0_accept_merge_dis_cm=${SBND_PI0_ACCEPT_MERGE}")
# doc pr/132 round 9 (K19): back-projection NC vertex proposer miss cap, cm.  EMPTY = no TLA = the job default 0 (off).
[ -n "${SBND_PI0_BP_VERTEX:-}" ] && CATH_TLA+=(--tla-code "pi0_bp_vertex_miss_cm=${SBND_PI0_BP_VERTEX}")
# doc pr/133: K20 admit mu-typed shower-topology objects into the pi0 pools.  EMPTY = no TLA = C++ default false.
[ -n "${SBND_PI0_ADMIT_MU:-}" ] && CATH_TLA+=(--tla-code "pi0_admit_muon_showers=$([ "${SBND_PI0_ADMIT_MU}" = 0 ] && echo false || echo true)")
# doc pr/141 M1: price mu-typed pi0 candidates under the SHOWER recom+fudge
# (ratio 1.657 at the production factors).  EMPTY = no TLA = the job default false.
[ -n "${SBND_PI0_MU_HYP:-}" ] && CATH_TLA+=(--tla-code "pi0_mu_shower_hypothesis=true")
# doc pr/141 M2: K20's shower-ish length bound in cm (shipped literal 40).
# EMPTY = no TLA = null = the C++ default 40 = byte-identical.
[ -n "${SBND_PI0_MU_LEN:-}" ] && CATH_TLA+=(--tla-code "pi0_mu_shower_max_len=${SBND_PI0_MU_LEN}")
# doc pr/141 M3: length floor (cm) for the M1 re-pricing.  EMPTY = no TLA = 0.
[ -n "${SBND_PI0_MU_HYP_MIN:-}" ] && CATH_TLA+=(--tla-code "pi0_mu_shower_hyp_min_len=${SBND_PI0_MU_HYP_MIN}")
# doc pr/133: K21 owner NC signature angle (deg) for the bp proposer.  EMPTY = no TLA = C++ default 0 (v3 gate).
[ -n "${SBND_PI0_NC_SIG_ANGLE:-}" ] && CATH_TLA+=(--tla-code "pi0_nc_sig_angle_deg=${SBND_PI0_NC_SIG_ANGLE}")
# doc pr/133: K21 v2 signature-mode partner floor (MeV).  EMPTY = no TLA = C++ default 0 (legacy 20).
[ -n "${SBND_PI0_NC_FLOOR:-}" ] && CATH_TLA+=(--tla-code "pi0_nc_floor_mev=${SBND_PI0_NC_FLOOR}")
# doc pr/133: K21 v2.2 post-fire PF association cone (deg).  EMPTY = no TLA = C++ default 0 = off.
[ -n "${SBND_PI0_NC_PF_ASSOC:-}" ] && CATH_TLA+=(--tla-code "pi0_nc_pf_assoc_deg=${SBND_PI0_NC_PF_ASSOC}")
# doc pr/134: K22 NC merged-complex bp pairing (bool).  EMPTY = no TLA = the job default false.
[ -n "${SBND_PI0_NC_FRAG_MERGE:-}" ] && CATH_TLA+=(--tla-code "pi0_nc_frag_merge=true")
# doc pr/134: K23 with-vertex post-accept PF satellite cone (deg).  EMPTY = no TLA = the job default off.
[ -n "${SBND_PI0_PF_ASSOC:-}" ] && CATH_TLA+=(--tla-code "pi0_pf_assoc_deg=${SBND_PI0_PF_ASSOC}")
# doc pr/134: K24 P1 nu-vertex preference (bool).  EMPTY = no TLA = the job default false.
[ -n "${SBND_PI0_PREFER_MAIN:-}" ] && CATH_TLA+=(--tla-code "pi0_prefer_main_vertex=true")
# doc pr/136 round 2: let the pass-4 cross-cluster pre-filter consult angle_v1
# before discarding on angle_v2 > 30 (bool).  EMPTY = no TLA = the job default false.
[ -n "${SBND_PASS4_V1_ESCAPE:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prefilter_v1_escape=true")
# doc pr/136 round 2: deg ceiling on angle_v2 for the escape above.  EMPTY = no
# TLA = the job default 0 = no ceiling (inert unless the escape is on).
[ -n "${SBND_PASS4_V1_MAXV2:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prefilter_v1_max_v2=${SBND_PASS4_V1_MAXV2}")
# doc pr/136 round 3: cm proximity bound on the escape.  EMPTY = no TLA = 0 = none.
[ -n "${SBND_PASS4_V1_MAXDIS:-}" ] && CATH_TLA+=(--tla-code "shower_pass4_prefilter_v1_max_dis=${SBND_PASS4_V1_MAXDIS}")
# doc pr/138 Phase B: the EM shower SPLITTER (bool).  The last shower-structure
# pass and the only one that cuts; runs before the pi0 finders.  EMPTY = no TLA
# = the job default false = no pass = byte-identical.
[ -n "${SBND_SHOWER_SPLIT:-}" ] && CATH_TLA+=(--tla-code "shower_split=true")
# doc pr/139 sec 24: turn the splitter OFF explicitly.  shower_split is now
# true by default in the job, so the only way to get a splitter-off arm is a
# TLA that sets it false.  EMPTY = no TLA = the job default (ON).
[ -n "${SBND_SHOWER_SPLIT_OFF:-}" ] && CATH_TLA+=(--tla-code "shower_split=false")
# doc pr/138 B3: how many parts one candidate may be cut into.  EMPTY = no TLA =
# the job default 2 = the kernel whose boundary Phase A measured exact.  >=3 is
# the k>=3 experiment (doc sec B3's 0.85 target MISSED at 0.772) -- not
# production-eligible; inert unless SBND_SHOWER_SPLIT is set.
[ -n "${SBND_SHOWER_SPLIT_PARTS:-}" ] && CATH_TLA+=(--tla-code "shower_split_max_parts=${SBND_SHOWER_SPLIT_PARTS}")
# doc pr/138 B2: the trigger's charge-valley ceiling.  EMPTY = no TLA = 0.95 =
# the Phase A knee, whose holdout is spent.  Present so the operating point is
# MOVABLE under review, not so it is searched again.
[ -n "${SBND_SHOWER_SPLIT_VALLEY:-}" ] && CATH_TLA+=(--tla-code "shower_split_max_valley=${SBND_SHOWER_SPLIT_VALLEY}")
# doc pr/139 phase 1: four independent follow-ups to the shipped splitter.  Each
# is EMPTY = no TLA = the job default = the shipped behaviour = byte-identical,
# and each is measured ALONE before any combination (doc pr/139 sec 1).
# P1.1 refuse a peel of segments another shower also owns (evt281485's 0.00 MeV
# daughter, evt165157's colliding seed).
[ -n "${SBND_SHOWER_SPLIT_SKIP_SHARED:-}" ] && CATH_TLA+=(--tla-code "shower_split_skip_shared=true")
# doc pr/139 sec 15: shed an ENTIRELY co-owned refused component instead of
# refusing it.  EMPTY = no TLA = the job default false.  Inert unless
# SBND_SHOWER_SPLIT_SKIP_SHARED is also set.
[ -n "${SBND_SHOWER_SPLIT_SHED_SHARED:-}" ] && CATH_TLA+=(--tla-code "shower_split_shed_shared=true")
# doc pr/139 sec 17: angular-maxima cap.  EMPTY = no TLA = the job default 4.
[ -n "${SBND_SHOWER_SPLIT_SEEDS:-}" ] && CATH_TLA+=(--tla-code "shower_split_max_seeds=${SBND_SHOWER_SPLIT_SEEDS}")
# doc pr/139 sec 25: cm; below this a daughter with no EM member peeled off an
# EM parent is typed 11.  EMPTY = no TLA = the job default 0 = off.
[ -n "${SBND_SHOWER_SPLIT_EM_TYPE_LEN:-}" ] && CATH_TLA+=(--tla-code "shower_split_em_type_max_len=${SBND_SHOWER_SPLIT_EM_TYPE_LEN}")
# P1.2 the impact-parameter veto, in CM.  EMPTY = no TLA = 0 = no bound.  The
# arm value is 12 (doc pr/139 sec 2.1: every census gain below 11 cm, every loss
# above 13 -- a bound chosen AFTER seeing 8 movers, and priced accordingly).
[ -n "${SBND_SHOWER_SPLIT_MAX_IMPACT:-}" ] && CATH_TLA+=(--tla-code "shower_split_max_impact=${SBND_SHOWER_SPLIT_MAX_IMPACT}")
# P1.3 seed the daughter on its nearest EM-typed member.  Fixes the 11-of-50
# mu-typed daughters, whose kine_charge is LOW BY A FACTOR 1.657.
[ -n "${SBND_SHOWER_SPLIT_EM_START:-}" ] && CATH_TLA+=(--tla-code "shower_split_em_start=true")
# P1.4 re-home an orphan daughter into the nearest larger EM shower that is NOT
# its parent.  _GAP is in CM; EMPTY = no TLA = 4 (the bundle scale).
[ -n "${SBND_SHOWER_SPLIT_REHOME:-}" ] && CATH_TLA+=(--tla-code "shower_split_rehome=true")
[ -n "${SBND_SHOWER_SPLIT_REHOME_GAP:-}" ] && CATH_TLA+=(--tla-code "shower_split_rehome_gap=${SBND_SHOWER_SPLIT_REHOME_GAP}")
# DL main-cluster swap guard (doc pr/24).  EMPTY = no TLA = the cfg default
# null = C++ 0/0 = OFF = the legacy DL vertex.  _MIN_LEN is in CM (the jsonnet
# multiplies wc.cm); _MIN_FRAC is a bare fraction of the incumbent main
# cluster's total track length.
# doc 87 output knobs -> TLAs.  Unset/empty => no TLA => byte-identical.
[ "${SBND_PR_BEE:-1}" = 0 ] && CATH_TLA+=(--tla-code "pr_bee=false")
[ -n "${SBND_PR_SAVE_IN_SCOPE:-}" ] && [ "${SBND_PR_SAVE_IN_SCOPE}" != 0 ] && \
    CATH_TLA+=(--tla-code "save_in_scope=true")
{ if [ -n "${PR_EXTRA_TLA:-}" ]; then [ -r "$PR_EXTRA_TLA" ] || { echo "ERROR: PR_EXTRA_TLA unreadable: $PR_EXTRA_TLA" >&2; exit 1; }; _n=0; while IFS= read -r _tl || [ -n "$_tl" ]; do case "$_tl" in ''|\#*) continue ;; esac; CATH_TLA+=(--tla-code "$_tl"); _n=$((_n+1)); done < "$PR_EXTRA_TLA"; echo "PR_EXTRA_TLA: appended $_n override(s) from $PR_EXTRA_TLA" >&2; fi; true; }  # doc pr/142: the LAST TLA block, so a file entry wins over any SBND_* env. EMPTY = no-op = byte-identical. On line 1800 on purpose: no line number moves.
true

# The embedded interpreter needs libpython loaded RTLD_GLOBAL for the SCN
# (DL vertex) import to succeed -- same idiom as run_pr3_evt_dl.sh / M4.
PYLIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")/libpython3.11.so.1.0
[ -r "$PYLIB" ] || { echo "ERROR: libpython not found: $PYLIB" >&2; exit 1; }

process_event() {
    local EVT_ID=$1
    local QLDIR="$QLROOT/ql_evt${EVT_ID}"
    local PCT="$QLDIR/pctree-evt${EVT_ID}.tar.gz"
    local PRDIR="$OUTROOT/pr_evt${EVT_ID}"
    local LOG="$PRDIR/wct_pr_evt${EVT_ID}.log"

    [ -s "$PCT" ] || { echo "ERROR: [evt $EVT_ID] no pctree: $PCT" >&2; return 1; }

    rm -rf "$PRDIR"; mkdir -p "$PRDIR"

    # RSE from the Q/L job's own opflash metadata (same source run_nusel_evt.sh
    # uses; correct across every sample this driver targets -- verified for
    # data/MCP2025C, nueCC48, and both MC roots, doc pr/11 sec 1).
    local RUN_NO=0 SUBRUN_NO=0 _md
    _md=$(tar xzOf "$QLDIR/opflash_apa0.tar.gz" "opflash_tensorset_${EVT_ID}_metadata.json" 2>/dev/null) || _md=''
    if [ -n "$_md" ]; then
        local _rse
        _rse=$(printf '%s' "$_md" | python3 -c \
            'import json,sys; d=json.load(sys.stdin); print(int(d.get("run",0)), int(d.get("subrun",0)))' \
            2>/dev/null) && [ -n "$_rse" ] && read -r RUN_NO SUBRUN_NO <<< "$_rse"
    fi

    echo "[evt $EVT_ID] rse=($RUN_NO, $SUBRUN_NO, $EVT_ID) pipeline=($PIPELINE) reality=$REALITY dl=on"

    (
        cd "$PRDIR" || exit 1
        export LD_PRELOAD="$PYLIB"
        export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
        # doc pr/57: env-gated per-edge JSONL dump feeding
        # overclustering_display (hand-scan of S6 2D-connectivity
        # removals). PR_OC56_SCAN_DUMP=1 => WCT_OC56_SCAN_DUMP points at a
        # per-event file under this event's own PRDIR; unset (default) =>
        # unset, so the C++ side's Oc56DumpWriter stays disabled and every
        # other batch invocation is unaffected -- same pattern as
        # PR_EXTRA_STAGES / SBND_PROTECT_GRAPH above. Exported only inside
        # this subshell, so parallel siblings each get their own event id.
        if [ "${PR_OC56_SCAN_DUMP:-}" = "1" ]; then
            export WCT_OC56_SCAN_DUMP="$PRDIR/oc56scan-evt${EVT_ID}.jsonl"
        fi
        # PR_TIMEOUT (seconds, default 3600) bounds a single event.  A pattern-
        # recognition hang is real: SBND MCP2025C evt 352365 spun at 100% CPU with
        # byte-flat RSS for 8h17m in shower_clustering_with_nv_from_vertices and
        # stalled the whole 1000-event batch on its last slot (doc pr/11 sec 6).
        # `timeout` sits INSIDE timecmd.py so .time.meta is still written (rc=124).
        # The full TLA list, collected once so the jsonnet compiler and
        # wire-cell see exactly the same arguments (doc pr/97 sec.5).
        # doc 87: keep the pctree unless SBND_PR_PCTREE=0.
        PCTREE_TLA=(--tla-str "save_tensors=$PRDIR/pctree-pr-evt${EVT_ID}.tar.gz")
        [ "${SBND_PR_PCTREE:-1}" = 0 ] && PCTREE_TLA=()
        _TLA=(
            --tla-str  "input=$PCT"
            --tla-code "anode_indices=[0,1]"
            --tla-str  "output_dir=$PRDIR"
            --tla-code "run=${RUN_NO}" --tla-code "subrun=${SUBRUN_NO}" --tla-code "event=${EVT_ID}"
            --tla-str  "reality=$REALITY"
            `# doc 68: the LAr set, the beam window and every tgm_*/stm_* knob`
            `# spelled out here were byte-for-byte the job's own defaults, so`
            `# they are gone.  PIPELINE stays explicit -- this chain adds the`
            `# neutrino taggers + BDT scorers on top of the default list.`
            --tla-code "pipeline_names=[$(echo "$PIPELINE" | sed "s/[^,]\+/'&'/g")]"
            "${TFJSON_TLA[@]}"
            "${CATH_TLA[@]}"
            `# doc 87: SBND_PR_PCTREE=0 => no save_tensors TLA => the job default`
            `# '' => TensorFileSink dump_mode => nothing written.  The sink NODE`
            `# stays in the graph; dropping it would break Pgrapher connectivity.`
            "${PCTREE_TLA[@]}"
        )
        # doc pr/97 sec.5: compile in a SEPARATE short-lived wcsonnet process
        # so this long job never hosts gojsonnet's Go runtime.  In-process, that
        # runtime keeps 64 threads alive for the whole job and one of them jumps
        # to PC 0x0 at ~120 s of process life (Go sysmon's forced-GC period),
        # killing the job with SIGSEGV while WireCell's own thread is provably
        # healthy.  The PR chain is the MOST exposed job here: it routinely runs
        # far past 120 s.  Costs 0.13 s; compiled config and output unchanged.
        # SBND_PRECOMPILE_CFG=0 restores the legacy in-process path (A/B only).
        _CFG=(-c "$JSONNET")
        if [ "${SBND_PRECOMPILE_CFG:-1}" = 1 ]; then
            _cfgjson="$PRDIR/.wct-cfg-evt${EVT_ID}.json"
            rm -f "$_cfgjson"
            if wcsonnet "${_TLA[@]}" -o "$_cfgjson" "$JSONNET"; then
                _CFG=(-c "$_cfgjson")
                _TLA=()
            else
                echo "[evt $EVT_ID] WARN: wcsonnet failed -- in-process jsonnet" >&2
            fi
        fi
        setarch x86_64 -R python3 "$AB/timecmd.py" "$PRDIR/.time.meta" \
        timeout --signal=TERM --kill-after=60 "${PR_TIMEOUT:-3600}" \
        wire-cell \
            -l stderr -l "${LOG}:${SBND_WCT_LOGLEVEL:-debug}" -L "${SBND_WCT_LOGLEVEL:-debug}" \
            "${_TLA[@]}" \
            "${_CFG[@]}"
        echo "rc=$?" > "$PRDIR/rc.txt"
    ) > "$PRDIR/stdout.log" 2>&1
    rm -f "$PRDIR/trash-pr.tar.gz"

    local rc; rc=$(sed -n 's/^rc=//p' "$PRDIR/rc.txt" 2>/dev/null); rc=${rc:-1}

    # DL-engagement proof (WARN visible at debug level -- doc pr/11 sec 1):
    # absent = DL ran without a hard failure this event (it may still have
    # legitimately deferred to the traditional vertex on a low rerank score).
    if grep -q "DL vertex failed" "$LOG" 2>/dev/null; then
        echo "[evt $EVT_ID] WARN: DL vertex failed this event (see $LOG)" >&2
    fi

    # Only extract when wire-cell actually succeeded.  On a crash the zip/prtree
    # are zero-byte and nusel_extract.py dies with a BadZipFile traceback that
    # buries the real cause at the tail of stdout.log -- exactly what happened to
    # the 73 doc-pr/11 failures, where SIGABRT/SIGTERM all read as "rc=250
    # BadZipFile".  rc here is wire-cell's own (timecmd.py encodes a fatal signal
    # N as 256-N: 250 = SIGABRT, 241 = SIGTERM, 124 = PR_TIMEOUT).
    if [ "$rc" != 0 ]; then
        echo "[evt $EVT_ID] wire-cell rc=$rc -- skipping nusel_extract (no usable outputs)" \
            >> "$PRDIR/stdout.log"
        echo "[evt $EVT_ID] rc=$rc  -> $PRDIR"
        return 1
    fi

    # Per-bundle label table -- same nusel_extract.py production call
    # (unmodified script; --prtree uses the save_tensors dump above, so labels
    # come from the authoritative flag_TGM/STM/FC, not the log fallback).
    # doc 87: pass whichever in-scope sources exist.  --prroot (T_cluster, needs
    # save_in_scope) is preferred inside nusel_extract.py and is what makes
    # SBND_PR_BEE=0 survivable; --prbee stays for every arm written before doc 87.
    # Proven interchangeable, byte-identical tsv on 308/308 events
    # (scripts/pr87_nusel_source_gate.sh).
    _NX=()
    [ -f "$PRDIR/mabc-pr.zip" ] && _NX+=(--prbee "$PRDIR/mabc-pr.zip")
    [ -f "$PRDIR/tracking-pr.root" ] && _NX+=(--prroot "$PRDIR/tracking-pr.root")
    [ -f "$PRDIR/pctree-pr-evt${EVT_ID}.tar.gz" ] && \
        _NX+=(--prtree "$PRDIR/pctree-pr-evt${EVT_ID}.tar.gz")
    [ -f "$QLDIR/mabc-all-apa.zip" ] && _NX+=(--qlbee "$QLDIR/mabc-all-apa.zip")
    python3 "$SX/nusel_extract.py" \
        --pctree "$PCT" --prlog "$LOG" "${_NX[@]}" \
        --beam-window "$PR_BEAM_WINDOW_US" \
        --run "$RUN_NO" --subrun "$SUBRUN_NO" \
        --out "$PRDIR/nusel-evt${EVT_ID}.tsv" 2>>"$PRDIR/stdout.log"

    # doc 87 master switch: the products were needed to BUILD the table above,
    # not to keep.  Delete after extraction, never before.
    if [ "$PR_MINIMAL_OUTPUT" = 1 ]; then
        rm -f "$PRDIR/mabc-pr.zip" "$PRDIR/pctree-pr-evt${EVT_ID}.tar.gz"
    fi

    echo "[evt $EVT_ID] rc=$rc  -> $PRDIR"
    [ "$rc" = 0 ]
}

# ---------------------------------------------------------------------------
# doc 76 round 2: GROUP mode -- run several events through ONE wire-cell
# process.  PR_GROUP_SIZE unset or 0 => the per-event path above, untouched and
# byte-identical.  Set it and the events are chunked; each chunk is one process.
#
# What makes this safe: the PR job's TLAs are IDENTICAL to the per-event ones
# except for four, so the operating point (all 300+ SBND_* knobs in CATH_TLA)
# cannot drift between the two modes:
#   input        one group archive instead of one event's pctree
#   output_dir   the batch root; evt_subdir puts each event back in pr_evt<ID>/
#   multi_event  event number from each tensor ident, not the constant `event`
#   rse_map      per-event run/subrun, because a group can span many runs
# Everything each event writes therefore lands on exactly the path the
# per-event driver writes, which is what lets pr85_hash_gate.py /
# pr94_root_gate.py / nusel_extract.py compare the two modes file for file.
process_group() {
    local GIDX=$1; shift
    local -a EVTS=("$@")
    local GDIR="$OUTROOT/.groups"
    local GTAR="$GDIR/g${GIDX}.tar.gz"
    local GRSE="$GDIR/g${GIDX}-rse.json"
    local GLOG="$OUTROOT/wct_pr_g${GIDX}.log"
    mkdir -p "$GDIR"

    # RSE for the *job* TLAs: the first event's, with rse_map correcting the
    # rest.  Same metadata source as process_event.
    local RUN_NO=0 SUBRUN_NO=0 _md
    _md=$(tar xzOf "$QLROOT/ql_evt${EVTS[0]}/opflash_apa0.tar.gz" \
            "opflash_tensorset_${EVTS[0]}_metadata.json" 2>/dev/null) || _md=''
    if [ -n "$_md" ]; then
        local _rse
        _rse=$(printf '%s' "$_md" | python3 -c \
            'import json,sys; d=json.load(sys.stdin); print(int(d.get("run",0)), int(d.get("subrun",0)))' \
            2>/dev/null) && [ -n "$_rse" ] && read -r RUN_NO SUBRUN_NO <<< "$_rse"
    fi

    # The sinks do not create directories -- the runner must.
    local evt
    for evt in "${EVTS[@]}"; do
        rm -rf "$OUTROOT/pr_evt${evt}"; mkdir -p "$OUTROOT/pr_evt${evt}"
    done

    if [ -s "$QLROOT/pctree-ql.tar.gz" ] && [ "${#EVTS[@]}" -eq "$(wc -l < "$QLROOT/events.txt" 2>/dev/null || echo -1)" ]; then
        # ql_root IS a stage-A group directory and we were asked for exactly its
        # events: its pctree-ql.tar.gz already holds them, in the right order,
        # so use it rather than take it apart and put it back together.
        GTAR="$QLROOT/pctree-ql.tar.gz"
        cp -f "$QLROOT/rse.json" "$GRSE" 2>/dev/null || echo '{}' > "$GRSE"
        echo "[group $GIDX] using stage-A archive $GTAR"
    elif ! python3 "$SX/scripts/multi/make_group_pctree.py" \
            --ql-root "$QLROOT" --out "$GTAR" --rse-map "$GRSE" "${EVTS[@]}" \
            > "$GDIR/g${GIDX}-build.log" 2>&1; then
        echo "ERROR: [group $GIDX] could not build $GTAR (see $GDIR/g${GIDX}-build.log)" >&2
        return 1
    fi

    echo "[group $GIDX] ${#EVTS[@]} events (${EVTS[0]}..${EVTS[-1]}) rse=($RUN_NO, $SUBRUN_NO) reality=$REALITY"

    (
        cd "$OUTROOT" || exit 1
        export LD_PRELOAD="$PYLIB"
        export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
        # doc 87: keep the pctree unless SBND_PR_PCTREE=0.
        GPCTREE_TLA=(--tla-str "save_tensors=$OUTROOT/pr_evt%1%/pctree-pr-evt%1%.tar.gz")
        [ "${SBND_PR_PCTREE:-1}" = 0 ] && GPCTREE_TLA=()
        _TLA=(
            --tla-str  "input=$GTAR"
            --tla-code "anode_indices=[0,1]"
            --tla-str  "output_dir=$OUTROOT"
            --tla-code "run=${RUN_NO}" --tla-code "subrun=${SUBRUN_NO}" --tla-code "event=${EVTS[0]}"
            --tla-str  "reality=$REALITY"
            --tla-code "pipeline_names=[$(echo "$PIPELINE" | sed "s/[^,]\+/'&'/g")]"
            "${TFJSON_TLA[@]}"
            "${CATH_TLA[@]}"
            --tla-code "multi_event=true"
            --tla-str  "evt_subdir=pr_evt%1%"
            --tla-code "rse_map=$(cat "$GRSE")"
            `# doc 87: SBND_PR_PCTREE=0 => no save_tensors TLA (see per-event path)`
            "${GPCTREE_TLA[@]}"
        )
        _CFG=(-c "$JSONNET")
        if [ "${SBND_PRECOMPILE_CFG:-1}" = 1 ]; then
            _cfgjson="$GDIR/.wct-cfg-g${GIDX}.json"
            rm -f "$_cfgjson"
            if wcsonnet "${_TLA[@]}" -o "$_cfgjson" "$JSONNET"; then
                _CFG=(-c "$_cfgjson")
                _TLA=()
            else
                echo "[group $GIDX] WARN: wcsonnet failed -- in-process jsonnet" >&2
            fi
        fi
        setarch x86_64 -R python3 "$AB/timecmd.py" "$GDIR/g${GIDX}.time.meta" \
        timeout --signal=TERM --kill-after=60 "${PR_GROUP_TIMEOUT:-${PR_TIMEOUT:-3600}}" \
        wire-cell \
            -l stderr -l "${GLOG}:${SBND_WCT_LOGLEVEL:-debug}" -L "${SBND_WCT_LOGLEVEL:-debug}" \
            "${_TLA[@]}" \
            "${_CFG[@]}"
        echo "rc=$?" > "$GDIR/g${GIDX}.rc"
    ) > "$OUTROOT/.batch_pr_g${GIDX}.stdout" 2>&1
    # doc 87: with SBND_PR_PCTREE=0 the TensorFileSink's outname falls back to the
    # job default 'trash-pr.tar.gz'.  dump_mode makes it write nothing, but
    # TensorFileSink::configure opens the stream regardless, so a near-empty file
    # appears in the process CWD -- which in group mode is $OUTROOT, shared by
    # every concurrent group.  The per-event path already removed its own copy;
    # this is the group-path counterpart.
    rm -f "$OUTROOT/trash-pr.tar.gz"

    local rc; rc=$(sed -n 's/^rc=//p' "$GDIR/g${GIDX}.rc" 2>/dev/null); rc=${rc:-1}
    if [ "$rc" != 0 ]; then
        echo "[group $GIDX] wire-cell rc=$rc -- see $GLOG" >&2
        for evt in "${EVTS[@]}"; do echo "rc=$rc" > "$OUTROOT/pr_evt${evt}/rc.txt"; done
        return 1
    fi

    # Per-event tables.  nusel_extract.py wants ONE event's log; the group log
    # is sequential, so slice it on the MABC load line that opens each event.
    # --bw-gate: the group log interleaves two logger sinks, so a per-event
    # slice of it can lose the beam_window_only line.  Pass the gate the job
    # actually ran with rather than let nusel_extract guess from a possibly
    # incomplete log -- without it an out-of-window main reads 0 "evaluated,
    # clean" instead of -1 "not evaluated" (seen on mcp1k 48367).
    local _NOK=0; local -a _MISSING=()
    for evt in "${EVTS[@]}"; do
        local PRDIR="$OUTROOT/pr_evt${evt}"
        local QLPCT="$QLROOT/ql_evt${evt}/pctree-evt${evt}.tar.gz"
        local QLBEE="$QLROOT/ql_evt${evt}/mabc-all-apa.zip"
        # doc 76 round 3.  RUN_NO/SUBRUN_NO are the JOB's TLAs -- the FIRST
        # event's run -- and rse_map corrects the rest inside wire-cell, so the
        # ROOT trees are right.  The table is written out here, though, and
        # stamping every row with the job's run gave every event in a group the
        # run of its group leader.  Silent on a single-run sample (mcp1k) and
        # wrong on 198 of 547 nueCC48 rows, which span 12 runs.  Take each
        # event's own pair from the same rse_map the job was given.
        local E_RUN=$RUN_NO E_SUBRUN=$SUBRUN_NO _erse
        _erse=$(python3 -c 'import json,sys
try:
    m = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit(1)
v = m.get(sys.argv[2])
if not v: raise SystemExit(1)
print(int(v[0]), int(v[1]))' "$GRSE" "$evt" 2>/dev/null)             && [ -n "$_erse" ] && read -r E_RUN E_SUBRUN <<< "$_erse"
        # A stage-A group dir keeps one archive for the whole group instead of a
        # tree per event; nusel_extract wants one event, so fall back to this
        # job's own re-saved per-event tree and skip the Q/L Bee cross-check.
        if [ ! -s "$QLPCT" ]; then
            QLPCT="$PRDIR/pctree-pr-evt${evt}.tar.gz"
            QLBEE=""
        fi
        # doc 82 round 2.  This used to be an unconditional `echo "rc=0"`.
        # The GROUP's own rc is checked above, and a non-zero group correctly
        # stamps every member -- but a group that exits 0 having produced
        # nothing for ONE member still reported that member as rc=0, so any
        # coverage count taken from rc.txt silently over-counted.  Take the
        # per-event verdict from the per-event product wire-cell was told to
        # write instead of asserting success.
        #
        # doc 87: that product used to be the pctree, "unconditional in the group
        # path" -- it no longer is (SBND_PR_PCTREE=0).  Ask for whichever product
        # this run was actually configured to write, else every event would
        # report rc=1 and the group would fail.  tracking-pr.root is the honest
        # fallback: SbndPrMagnifyTrackingVisitor runs on every event and the
        # runner has no knob to suppress it.
        _VERDICT_FILE="$PRDIR/pctree-pr-evt${evt}.tar.gz"
        [ "${SBND_PR_PCTREE:-1}" = 0 ] && _VERDICT_FILE="$PRDIR/tracking-pr.root"
        if [ -s "$_VERDICT_FILE" ]; then
            echo "rc=0" > "$PRDIR/rc.txt"
            _NOK=$((_NOK+1))
        else
            echo "rc=1" > "$PRDIR/rc.txt"
            _MISSING+=("$evt")
            echo "[group $GIDX] event $evt: NO per-event product though the group exited 0" >&2
        fi
        python3 "$SX/scripts/multi/slice_group_log.py" "$GLOG" "$evt" \
            > "$PRDIR/wct_pr_evt${evt}.log" 2>/dev/null
        # doc 87: same source handling as the per-event path.
        _NX=()
        [ -f "$PRDIR/mabc-pr.zip" ] && _NX+=(--prbee "$PRDIR/mabc-pr.zip")
        [ -f "$PRDIR/tracking-pr.root" ] && _NX+=(--prroot "$PRDIR/tracking-pr.root")
        [ -f "$PRDIR/pctree-pr-evt${evt}.tar.gz" ] && \
            _NX+=(--prtree "$PRDIR/pctree-pr-evt${evt}.tar.gz")
        python3 "$SX/nusel_extract.py" \
            --pctree "$QLPCT" --prlog "$PRDIR/wct_pr_evt${evt}.log" "${_NX[@]}" \
            ${QLBEE:+--qlbee "$QLBEE"} \
            --beam-window "$PR_BEAM_WINDOW_US" \
            --bw-gate "$PR_BEAM_WINDOW_US" \
            --run "$E_RUN" --subrun "$E_SUBRUN" \
            --out "$PRDIR/nusel-evt${evt}.tsv" 2>>"$PRDIR/stdout.log"
        if [ "$PR_MINIMAL_OUTPUT" = 1 ]; then
            rm -f "$PRDIR/mabc-pr.zip" "$PRDIR/pctree-pr-evt${evt}.tar.gz"
        fi
    done
    if [ "$_NOK" -ne "${#EVTS[@]}" ]; then
        echo "[group $GIDX] rc=0 from wire-cell but ${_NOK}/${#EVTS[@]} events have products; missing: ${_MISSING[*]}" >&2
        return 1
    fi
    echo "[group $GIDX] rc=0  -> $OUTROOT (${_NOK}/${#EVTS[@]} events)"
    return 0
}

batch_init
BATCH_MAX=${PR_JOBS:-6}
GROUP_SIZE=${PR_GROUP_SIZE:-0}
echo "ql_root=$QLROOT out_root=$OUTROOT reality=$REALITY events=${#EVENT_IDS[@]} jobs=$BATCH_MAX group_size=$GROUP_SIZE"
if [ "$GROUP_SIZE" -gt 0 ]; then
    _gi=0
    _n=${#EVENT_IDS[@]}
    for ((_i=0; _i<_n; _i+=GROUP_SIZE)); do
        _chunk=("${EVENT_IDS[@]:_i:GROUP_SIZE}")
        _blog="$OUTROOT/.batch_pr_g${_gi}.log"
        batch_wait_slot
        ( process_group "$_gi" "${_chunk[@]}" ) > "$_blog" 2>&1 &
        BATCH_PIDS[$!]="g$_gi"
        echo "  [start] group=$_gi n=${#_chunk[@]} log: $_blog"
        _gi=$((_gi+1))
    done
else
for evt in "${EVENT_IDS[@]}"; do
    _blog="$OUTROOT/.batch_pr_evt${evt}.log"
    batch_wait_slot
    ( process_event "$evt" ) > "$_blog" 2>&1 &
    BATCH_PIDS[$!]=$evt
    echo "  [start] evt=$evt  log: $_blog"
done
fi
batch_drain
batch_summary

# Merge the per-event nusel tables (label/TGM/STM/FC/LM census).
#
# ARM-SCOPED, NOT BATCH-SCOPED (doc 99).  These two files name the ARM, so they
# have to cover every event the arm holds -- not just this invocation's
# EVENT_IDS.  Merging the batch silently clobbered the arm: re-running ONE event
# of work-nuecc48-d97fvpr2 rewrote its nusel-events.tsv from 49 rows to 2 and
# nusel-table.tsv from 547 to 10, while all 48 per-event tables stayed intact and
# every published number stayed right -- so nothing failed and nothing warned.
# Enumerating pr_evt*/ instead makes the merge idempotent and monotone: a partial
# re-run can only refresh rows, never drop them.  Same ls/sed/sort -n idiom as
# the EVENT_IDS discovery above, so the row order is unchanged for a full run.
_tsvs=()
while IFS= read -r _t; do
    [ -s "$_t" ] && _tsvs+=("$_t")
done < <(ls -d "$OUTROOT"/pr_evt*/ 2>/dev/null \
             | sed -E 's#.*/pr_evt([0-9]+)/?$#\1#' | sort -n \
             | while read -r _e; do echo "$OUTROOT/pr_evt$_e/nusel-evt$_e.tsv"; done)
if [ "${#_tsvs[@]}" -gt 0 ]; then
    python3 "$SX/nusel_extract.py" --merge "${_tsvs[@]}" \
        --out "$OUTROOT/nusel-table.tsv" \
        --events-out "$OUTROOT/nusel-events.tsv"
    echo "merged ${#_tsvs[@]} per-event tables in the arm (this batch: ${#EVENT_IDS[@]})" \
         "-> $OUTROOT/nusel-table.tsv + nusel-events.tsv"
fi

echo "loadavg: $(cat /proc/loadavg)"

# doc pr/97 sec.5: batch_summary() returns 0 as long as ANY event succeeded, so
# one crashed event in 2000 exited 0 and read as a clean batch (doc pr/95, evt
# 178410).  Re-derive the failures from the per-event rc.txt and fail loudly.
_bad=""
for evt in "${EVENT_IDS[@]}"; do
    _r=$(sed -n 's/^rc=//p' "$OUTROOT/pr_evt${evt}/rc.txt" 2>/dev/null); _r=${_r:-missing}
    [ "$_r" = 0 ] || _bad="${_bad}evt=${evt} rc=${_r}
"
done
if [ -n "$_bad" ]; then
    echo
    echo "############################################################"
    echo "# FAILED EVENTS -- their mabc-pr.zip / pctree are MISSING or"
    echo "# TRUNCATED, and nusel_extract was skipped for them, so the"
    echo "# merged nusel table below is SHORT by these events."
    echo "#   rc=139 = SIGSEGV. On a job living past ~120 s this is very likely the"
    echo "#   doc pr/97 gojsonnet Go-runtime crash (~4 %/run): a libgojsonnet thread"
    echo "#   jumps to PC 0x0 while WireCell's own thread is healthy. Re-run the event;"
    echo "#   SBND_PRECOMPILE_CFG=1 (the default) is meant to prevent it."
    echo "#   rc=124 = PR_TIMEOUT, 250 = SIGABRT, 241 = SIGTERM."
    echo "#"
    printf '%s' "$_bad" | sed 's/^/# /'
    echo "############################################################"
    exit 1
fi
exit 0
}
# doc pr/141 sec 19 -- why the body is wrapped in one compound command.
#
# bash re-reads a RUNNING script from a saved byte offset, so editing this file
# while an arm is in flight makes the shell resume mid-token and execute a
# fragment.  That is the true cause of the intermittent
#     ./run_pr_chain_batch.sh: line NNNN: _r: unbound variable
# which has silently killed the doc pr/97 failure check since at least doc
# pr/139 (its sec 13.3 blamed the loop; the loop is correct and, fed a synthetic
# rc.txt set, fires and names the failing events).  Evidence: this script's mtime
# fell 18 s BEFORE the failing arm log's last write, and the reported line number
# tracked the edits, 2145 -> 2149 -> 2151.
#
# `{ ... }` forces bash to PARSE THE WHOLE BODY before executing anything, so a
# later edit cannot reach a run in progress.  The body always exits before the
# closing brace, which is required only to parse -- and that exit is
# LOAD-BEARING: with a bare brace bash resumes past `}` on the stale offset and
# dies rc=2.  The brace opens on the `set -u` line on purpose, so no existing
# line number in this file moves.
