#!/usr/bin/env bash
# doc 30 -- stage and run one PDVD PR arm over the 120-event d48nu7 pctree set.
# Uses pdvd/scripts/stage_pr_tag.sh (untouched) for staging.
set -uo pipefail
PDVD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd
ARM=${ARM:?set ARM}; PR_TLA=${PR_TLA:-}; MODE=${MODE:--stm}; STMFIT=${STMFIT:-1}
PIN=${PIN:-}; JOBS=${JOBS:-6}; SRC=${SRC:-d48nu7}
LOGD=${LOGD:-/home/xqian/tmp/d30/arm_$ARM}; mkdir -p "$LOGD"
[ -n "$PIN" ] && [ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fp() { md5sum "$PIN/libWireCellClus.so" "$PIN/libWireCellRoot.so" 2>/dev/null | cut -c1-12 | paste -sd,; }
echo "[$ARM] pin=$PIN fingerprint BEFORE: $(fp)"
echo "[$ARM] MODE=$MODE STMFIT=$STMFIT JOBS=$JOBS SRC=$SRC TLA=${PR_TLA:-<none>}"
FITFLAG=""; [ "$STMFIT" = 1 ] && FITFLAG="-stm-fit"
one() {
    local run6=$1 idx=$2
    local run=$((10#$run6))
    local dst="$PDVD/work/${run6}_${idx}_${ARM}"
    local log="$LOGD/${run6}_${idx}.log"
    ( cd "$PDVD" || exit 1
      [ -d "$dst" ] || ./scripts/stage_pr_tag.sh "$run" "$idx" "$ARM" "$SRC" >/dev/null || exit 14
      PDVD_PR_TLA="$PR_TLA" PDVD_MAX_JOBS=1 ./run_pr_evt.sh -s "$ARM" $MODE $FITFLAG "$run" "$idx" || exit 15
      grep -q "TaggerCheckSTM: cluster" "$dst"/wct_pr_*.log || { echo "NO STM VERDICT LINES"; exit 16; }
      [ -s "$dst/mabc-pr.zip" ] || { echo "NO mabc-pr.zip"; exit 17; }
      touch "$dst/.d30-pr-done" ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$dst/.d30-pr-done" ]; then echo "[$ARM] $run6/$idx OK"
    else echo "[$ARM] $run6/$idx FAIL rc=$rc ($log)"; fi
}
for d in $(ls -d "$PDVD"/work/*_${SRC} 2>/dev/null); do
    b=$(basename "$d"); run6=${b%%_*}; rest=${b#*_}; idx=${rest%%_*}
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
    one "$run6" "$idx" &
done
wait
echo "[$ARM] pin fingerprint AFTER: $(fp)"
echo "[$ARM] DONE markers: $(ls -d "$PDVD"/work/*_${ARM}/.d30-pr-done 2>/dev/null | wc -l) of $(ls -d "$PDVD"/work/*_${ARM} 2>/dev/null | wc -l) dirs"
