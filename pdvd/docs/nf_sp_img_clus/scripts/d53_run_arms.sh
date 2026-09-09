#!/usr/bin/env bash
# doc pdvd/53 -- stage and run the d53 PR arms (the SURVEY: fit every
# same-bundle cluster within survey_radius_cm of the STM stop, and give every
# fitted-but-unclaimed companion segment a role-6 row naming the gate that
# dropped it) on both ProtoDUNEs.
#
# Fork by duplication (CLAUDE.md M10) of this directory's d51g_run_arms.sh.
# The ONLY differences are the arm names, the log dir and the legacy key.
#
# Fork by duplication (CLAUDE.md M10) of pdhd/docs/scripts/d16_run_arms.sh: each
# arm gets its own work dir with the pctree SYMLINKED from the source arm, so
# every arm consumes byte-identical input and the branch-by-branch comparison in
# doc pdvd/51 sec 6 is a comparison of the CODE, not of the input.
#
# RUN NO WAF TARGET WHILE THIS IS LIVE -- not `install`, not a plain
# `./wcb build`: the runner's plugin search reaches build/<pkg>/ as well as
# local/lib, so relinking build/ truncates the .so the live jobs are dlopening.
# It cost doc pdhd/15 20 of 31 PDHD events.
#
# The legacy arm passes ONE key.  stm_michel_extra (doc pdvd/51, added to both
# wct-pr-perevt.jsonnet) merges on top of the driver's default bag, so
# `-S stm_michel_extra={survey_enable:false}` is provably a one-key change --
# unlike -S stm_michel_knobs={...}, which replaces the bag and makes the arm's
# correctness depend on re-transcribing every other knob.
#
# Usage:
#   ARM=d53v    DET=pdvd SRC=d16vnu JOBS=8 ./d53_run_arms.sh
#   ARM=d53vleg DET=pdvd SRC=d16vnu JOBS=8 \
#       PR_TLA='-S stm_michel_extra={survey_enable:false}' ./d53_run_arms.sh
#   ARM=d53h    DET=pdhd SRC=d16hnu JOBS=8 ./d53_run_arms.sh
#   ARM=d53hleg DET=pdhd SRC=d16hnu JOBS=8 \
#       PR_TLA='-S stm_michel_extra={survey_enable:false}' ./d53_run_arms.sh
set -uo pipefail
IMG=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img
DET=${DET:?set DET to pdvd or pdhd}
ARM=${ARM:?set ARM}
SRC=${SRC:?set SRC (the source arm whose pctree symlinks are reused)}
JOBS=${JOBS:-8}
PR_TLA=${PR_TLA:-}
LOGD=${LOGD:-/home/xqian/tmp/d53/arm_$ARM}; mkdir -p "$LOGD"
D=$IMG/$DET
# PIN: a private snapshot of local/lib, prepended to LD_LIBRARY_PATH.  This is
# not optional in this tree.  The doc pdvd/51 arms were run once WITHOUT it and
# had to be thrown away: a peer session ran a waf target mid-campaign, local/lib
# went 75465affecfb -> ca225ad952e8 -> 9ee23d287d57 under three live arms, and
# 14 PDHD events died with `file too short` (4 logs, 10 wall_s=0 rows -- the
# tell from feedback_shared_tree_binary_pin).  wire-cell dlopens its plugins
# once per job at job start, so a mid-campaign rebuild silently splits an arm
# across binaries and NOTHING in the output says so.
PIN=${PIN:-}
if [ -n "$PIN" ]; then
    export LD_LIBRARY_PATH="$PIN:${LD_LIBRARY_PATH:-}"
    LIB=$PIN/libWireCellClus.so
else
    LIB=/nfs/data/1/xqian/toolkit-dev/local/lib/libWireCellClus.so
    echo "[$ARM] *** NO PIN -- a peer rebuild will silently void this arm ***"
fi

case "$DET" in
  pdvd) JOBVAR=PDVD_MAX_JOBS; TLAVAR=PDVD_PR_TLA; EXTRA_ENV="PDVD_LIGHT_SUFFIX=_keep" ;;
  pdhd) JOBVAR=PDHD_MAX_JOBS; TLAVAR=PDHD_PR_TLA; EXTRA_ENV="" ;;
  *) echo "DET must be pdvd or pdhd" >&2; exit 2 ;;
esac

echo "[$ARM] det=$DET src=$SRC jobs=$JOBS tla=${PR_TLA:-<none>}"
# The binary pin, printed BEFORE and AFTER: a concurrent session's wcbuild swaps
# local/lib under a running arm and every number becomes unattributable.
# A start marker, so the completion checks can tell THIS campaign's output from
# a previous run's leftovers in the same work dirs.
STAMP=$(mktemp /home/xqian/tmp/d53_stamp_XXXXXX); trap 'rm -f "$STAMP"' EXIT
MD5_BEFORE=$(md5sum "$LIB" | cut -c1-12)
echo "[$ARM] libWireCellClus md5 $MD5_BEFORE  (${PIN:-local/lib})"

# ---- stage: one dir per source event, pctree symlinked -------------------
n=0
for s in "$D"/work/*_"$SRC"; do
    [ -d "$s" ] || continue
    b=$(basename "$s"); pre=${b%_$SRC}
    dst="$D/work/${pre}_${ARM}"
    ls "$s"/pctree-evt*.tar.gz >/dev/null 2>&1 || { echo "[$ARM] $pre NO PCTREE"; continue; }
    mkdir -p "$dst"
    for f in "$s"/pctree-evt*.tar.gz "$s"/pctree-evt*.tlas; do
        ln -sfn "$(readlink -f "$f")" "$dst/$(basename "$f")"   # follow to the same real file
    done
    n=$((n+1))
done
echo "[$ARM] staged $n event dir(s)"

# ---- run, run by run -----------------------------------------------------
rc_all=0
for run6 in $(ls -d "$D"/work/*_"$ARM" | sed -E 's#.*/([0-9]+)_[0-9]+_.*#\1#' | sort -u); do
    run=$((10#$run6))
    echo "[$ARM] run $run6 ($run) ..."
    ( cd "$D" && env $EXTRA_ENV $JOBVAR="$JOBS" $TLAVAR="$PR_TLA" \
        ./run_pr_evt.sh -nu -stm-fit -s "$ARM" "$run" all ) \
        > "$LOGD/run_${run6}.log" 2>&1
    rc=$?; echo "[$ARM] run $run6 rc=$rc"
    [ $rc -ne 0 ] && rc_all=$rc
    echo "[$ARM] loadavg $(cut -d' ' -f1 /proc/loadavg) / $(nproc) cores"
    # Verify the pin took effect in a job that actually ran, not just in the
    # environment: the memory's rule is to grep a RUNNING process's maps, and
    # the next best evidence after the fact is that no job died in the loader.
    # Only logs written by THIS campaign may be judged: an arm re-run over a
    # previous one starts with the old logs still on disk, so globbing them all
    # reports the PREVIOUS run's loader deaths as if they were this run's.  That
    # false positive fired once here and cost a diagnosis.
    if [ -n "$PIN" ]; then
        bad=$(find "$D"/work -maxdepth 2 -name 'wct_pr_*.log' -path "*_$ARM/*" \
                   -newer "$STAMP" -exec grep -l "file too short" {} + 2>/dev/null | wc -l)
        [ "$bad" -gt 0 ] && echo "[$ARM] *** $bad job(s) died in the loader DESPITE the pin ***"
    fi
done

# ---- a completion check that is not the log file existing ---------------
# (feedback_completion_marker_not_the_log: a log exists from the moment a job
# starts; the summary line exists only when CheckSTM_Michel actually ran.)
ok=0; bad=0
for d in "$D"/work/*_"$ARM"; do
    if [ -s "$d/tracking-pr.root" ] && grep -q "CheckSTM_Michel: .* candidate(s)" "$d"/wct_pr_*.log 2>/dev/null
    then ok=$((ok+1)); else bad=$((bad+1)); echo "[$ARM] INCOMPLETE $(basename "$d")"; fi
done
MD5_AFTER=$(md5sum "$LIB" | cut -c1-12)
echo "[$ARM] complete $ok, incomplete $bad, run rc=$rc_all"
echo "[$ARM] libWireCellClus md5 AFTER $MD5_AFTER"
[ "$MD5_BEFORE" = "$MD5_AFTER" ] || echo "[$ARM] *** BINARY CHANGED MID-ARM -- every number in this arm is unattributable ***"
exit $(( bad > 0 ? 1 : rc_all ))
