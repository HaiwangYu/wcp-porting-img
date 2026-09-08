#!/usr/bin/env bash
# doc pdhd/16 -- stage and run the d16 PR arms (MCS + the calibrated dQ/dx ->
# dE/dx inverse) on both ProtoDUNEs.
#
# Fork by duplication of d30_run_pr_arm.sh's staging idiom: each arm gets its
# own work dir with the pctree SYMLINKED from the doc-15 arm, so d15 and d16
# consume byte-identical input and the branch-by-branch comparison in doc 16
# sec 6 is a comparison of the code, not of the input.
#
# RUN NO WAF TARGET WHILE THIS IS LIVE -- not `install`, not a plain
# `./wcb build`: the runner's plugin search reaches build/<pkg>/ as well as
# local/lib, so relinking build/ truncates the .so the live jobs are dlopening.
#
# Usage:
#   ARM=d16vnu DET=pdvd SRC=d15vnu JOBS=6 ./d16_run_arms.sh
#   ARM=d16hnu DET=pdhd SRC=d15hnu JOBS=6 ./d16_run_arms.sh
set -uo pipefail
IMG=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img
DET=${DET:?set DET to pdvd or pdhd}
ARM=${ARM:?set ARM}
SRC=${SRC:?set SRC (the source arm whose pctree symlinks are reused)}
JOBS=${JOBS:-6}
PR_TLA=${PR_TLA:-}
LOGD=${LOGD:-/home/xqian/tmp/d16/arm_$ARM}; mkdir -p "$LOGD"
D=$IMG/$DET

case "$DET" in
  pdvd) JOBVAR=PDVD_MAX_JOBS; TLAVAR=PDVD_PR_TLA; EXTRA_ENV="PDVD_LIGHT_SUFFIX=_keep" ;;
  pdhd) JOBVAR=PDHD_MAX_JOBS; TLAVAR=PDHD_PR_TLA; EXTRA_ENV="" ;;
  *) echo "DET must be pdvd or pdhd" >&2; exit 2 ;;
esac

echo "[$ARM] det=$DET src=$SRC jobs=$JOBS tla=${PR_TLA:-<none>}"
md5sum /nfs/data/1/xqian/toolkit-dev/local/lib/libWireCellClus.so | cut -c1-12 | sed "s/^/[$ARM] libWireCellClus md5 /"

# ---- stage: one dir per source event, pctree symlinked -------------------
n=0
for s in "$D"/work/*_"$SRC"; do
    [ -d "$s" ] || continue
    b=$(basename "$s"); pre=${b%_$SRC}
    dst="$D/work/${pre}_${ARM}"
    ls "$s"/pctree-evt*.tar.gz >/dev/null 2>&1 || { echo "[$ARM] $pre NO PCTREE"; continue; }
    mkdir -p "$dst"
    for f in "$s"/pctree-evt*.tar.gz "$s"/pctree-evt*.tlas; do
        # follow the source's own symlink so d16 points at the same real file
        ln -sfn "$(readlink -f "$f")" "$dst/$(basename "$f")"
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
done

# ---- a completion check that is not the log file existing ---------------
ok=0; bad=0
for d in "$D"/work/*_"$ARM"; do
    if [ -s "$d/tracking-pr.root" ] && grep -q "CheckSTM_Michel: .* candidate(s)" "$d"/wct_pr_*.log 2>/dev/null
    then ok=$((ok+1)); else bad=$((bad+1)); echo "[$ARM] INCOMPLETE $(basename "$d")"; fi
done
echo "[$ARM] complete $ok, incomplete $bad, run rc=$rc_all"
md5sum /nfs/data/1/xqian/toolkit-dev/local/lib/libWireCellClus.so | cut -c1-12 | sed "s/^/[$ARM] libWireCellClus md5 AFTER /"
exit $(( bad > 0 ? 1 : rc_all ))
