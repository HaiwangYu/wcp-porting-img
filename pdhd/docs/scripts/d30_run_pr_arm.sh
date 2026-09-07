#!/usr/bin/env bash
# doc 30 -- stage and run one PDHD PR arm over both runs, for the memory/CPU study.
#
# Forked BY DUPLICATION from d09_run_pr_arm.sh (untouched).  What differs: MODE
# (-stm | -nu) and STMFIT are parameters, JOBS defaults to 1 so a timing arm is
# contention-free by default, and the pin fingerprint covers libWireCellRoot too
# (the T_proj_data writer lives there).
#
# Each arm gets its own work dir with the pctree SYMLINKED from the Q/L source
# tag, so all arms consume byte-identical input and no arm can overwrite
# another's outputs.  Source tags:
#   028084 -> _d09      (31 events)
#   029107 -> _d09ctl2  (30 events)
#
# Usage:
#   ARM=d30hpre PIN=/home/xqian/tmp/d30_libpin JOBS=6 ./d30_run_pr_arm.sh
#   ARM=d30hnu  MODE=-nu STMFIT=1 ./d30_run_pr_arm.sh
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
ARM=${ARM:?set ARM}
PR_TLA=${PR_TLA:-}
MODE=${MODE:--stm}
STMFIT=${STMFIT:-1}
PIN=${PIN:-}
JOBS=${JOBS:-1}
LOGD=${LOGD:-/home/xqian/tmp/d30/arm_$ARM}; mkdir -p "$LOGD"
[ -n "$PIN" ] && [ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# binary fingerprint before AND after: doc pdvd/43 lost a round to a rebuild between arms
fp() { md5sum "$PIN/libWireCellClus.so" "$PIN/libWireCellRoot.so" 2>/dev/null | cut -c1-12 | paste -sd,; }
echo "[$ARM] pin=$PIN fingerprint BEFORE: $(fp)"
echo "[$ARM] MODE=$MODE STMFIT=$STMFIT JOBS=$JOBS PDHD_PR_TLA: ${PR_TLA:-<none>}"

FITFLAG=""; [ "$STMFIT" = 1 ] && FITFLAG="-stm-fit"

one() {
    local run6=$1 run=$2 idx=$3 srctag=$4
    local src="$PDHD/work/${run6}_${idx}_${srctag}"
    local dst="$PDHD/work/${run6}_${idx}_${ARM}"
    local log="$LOGD/${run6}_${idx}.log"
    ls "$src"/pctree-evt*.tar.gz >/dev/null 2>&1 || { echo "[$ARM] $run6/$idx NO PCTREE"; return; }
    mkdir -p "$dst"
    (
      cd "$PDHD" || exit 1
      for f in "$src"/pctree-evt*.tar.gz "$src"/pctree-evt*.tlas; do
          ln -sfn "../${run6}_${idx}_${srctag}/$(basename "$f")" "$dst/$(basename "$f")"
      done
      PDHD_PR_TLA="$PR_TLA" PDHD_MAX_JOBS=1 ./run_pr_evt.sh -s "$ARM" $MODE $FITFLAG "$run" "$idx" || exit 15
      # a job that produced no verdict lines did not run the taggers: rc=0 is not enough
      grep -q "TaggerCheckSTM: cluster" "$dst"/wct_pr_*.log || { echo "NO STM VERDICT LINES"; exit 16; }
      [ -s "$dst/mabc-pr.zip" ] || { echo "NO mabc-pr.zip"; exit 17; }
      touch "$dst/.d30-pr-done"
    ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$dst/.d30-pr-done" ]; then echo "[$ARM] $run6/$idx OK"
    else echo "[$ARM] $run6/$idx FAIL rc=$rc ($log)"; fi
}

run_set() {
    local run6=$1 run=$2 srctag=$3
    for d in $(ls -d "$PDHD"/work/${run6}_*_${srctag} 2>/dev/null | sort -t_ -k2 -n); do
        local idx; idx=$(basename "$d" | sed -E "s/${run6}_([0-9]+)_${srctag}/\1/")
        while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
        one "$run6" "$run" "$idx" "$srctag" &
    done
}
run_set 028084 28084 d09
run_set 029107 29107 d09ctl2
wait
echo "[$ARM] pin fingerprint AFTER: $(fp)"
n_ok=$(ls -d "$PDHD"/work/*_${ARM}/.d30-pr-done 2>/dev/null | wc -l)
n_dir=$(ls -d "$PDHD"/work/*_${ARM} 2>/dev/null | wc -l)
echo "[$ARM] DONE markers: $n_ok of $n_dir dirs"
