#!/usr/bin/env bash
# doc pdhd/09 -- stage one PR arm and run it over both runs.  PDHD's counterpart of
# pdvd/scripts/stage_pr_tag.sh, which has no PDHD equivalent.
#
# Each arm gets its own work dir with the pctree SYMLINKED from the Q/L source tag,
# so all arms consume byte-identical input and no arm can overwrite another's
# mabc-pr.zip / wct_pr log.  The source tags are the Phase 1/2 products:
#   028084 -> _d09      (31 events, imaged + Q/L'd today under the pin)
#   029107 -> _d09ctl2  (30 events: imaging AND light AND Q/L all under the SAME pin)
#
# Usage:
#   ARM=d09fvoff ./d09_run_pr_arm.sh
#   ARM=d09p90c5 PR_TLA="-S curved_fv=true -A curved_fv_profile=p90 -S curved_fv_margin_y=5 -S curved_fv_margin_z=5" ./d09_run_pr_arm.sh
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
ARM=${ARM:?set ARM}
PR_TLA=${PR_TLA:-}
PIN=${PIN:-/home/xqian/tmp/d09_libpin/pin}
JOBS=${JOBS:-6}
LOGD=${LOGD:-/home/xqian/tmp/d09/pr_$ARM}; mkdir -p "$LOGD"
[ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# binary fingerprint before AND after: doc pdvd/43 lost a round to a rebuild between arms
fp() { md5sum "$PIN/libWireCellClus.so" "$PIN/libWireCellAux.so" 2>/dev/null | cut -c1-12 | paste -sd,; }
echo "[$ARM] pin fingerprint BEFORE: $(fp)"
echo "[$ARM] PDHD_PR_TLA: ${PR_TLA:-<none>}"

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
      PDHD_PR_TLA="$PR_TLA" ./run_pr_evt.sh -s "$ARM" "$run" "$idx" || exit 15
      grep -q "TaggerCheckTGM: cluster" "$dst"/wct_pr_*.log || { echo "NO TGM VERDICT LINES"; exit 16; }
      touch "$dst/.d09-pr-done"
    ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$dst/.d09-pr-done" ]; then echo "[$ARM] $run6/$idx OK"
    else echo "[$ARM] $run6/$idx FAILED rc=$rc -- $log"; fi
}

n=0
for idx in $(seq 0 30); do one 028084 28084 "$idx" d09    & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait; done
for idx in $(seq 0 29); do one 029107 29107 "$idx" d09ctl2 & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait; done
wait
echo "[$ARM] pin fingerprint AFTER:  $(fp)"
echo "[$ARM] done"
