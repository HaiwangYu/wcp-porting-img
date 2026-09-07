#!/usr/bin/env bash
# doc pdhd/09 -- stage a 029107 event into a fresh tag by SYMLINK and re-run clus+Q/L
# under the pinned binary, so the 28084 comparison is same-binary AND same-chain.
# The imaging is reused as-is (identical DNN-ROI product); only clus+Q/L re-runs.
# Nothing under the original work dir is written -- M13.
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
RUN=29107; RUN6=029107; TAG=${TAG:-d09ref}
PIN=${PIN:-/home/xqian/tmp/d09_libpin/pin}
JOBS=${JOBS:-6}
LOGD=${LOGD:-/home/xqian/tmp/d09/reflogs}; mkdir -p "$LOGD"
[ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

one() {
    local idx=$1
    local src="$PDHD/work/${RUN6}_${idx}"
    local dst="$PDHD/work/${RUN6}_${idx}_${TAG}"
    local log="$LOGD/evt${idx}.log"
    [ -d "$src" ] || { echo "[d09ref] idx=$idx NO SOURCE"; return; }
    mkdir -p "$dst"
    (
      cd "$PDHD" || exit 1
      for f in "$src"/clusters-apa-apa*-ms-*.tar.gz; do ln -sfn "../${RUN6}_${idx}/$(basename "$f")" "$dst/$(basename "$f")"; done
      # opflash: follow the source's own symlink to the all-PD product
      op="$src/opflash_pdhd-wct.tar.gz"
      [ -e "$op" ] && ln -sfn "$(readlink -f "$op")" "$dst/opflash_pdhd-wct.tar.gz"
      ./run_clus_evt.sh -s "$TAG" -calib -save-pctree -save-assoc $RUN "$idx" || exit 14
      touch "$dst/.d09-ref-done"
    ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$dst/.d09-ref-done" ]; then echo "[d09ref] idx=$idx OK"
    else echo "[d09ref] idx=$idx FAILED rc=$rc -- $log"; fi
}
n=0
for idx in $(seq 0 29); do
    one "$idx" & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait
done
wait
echo "[d09ref] done"
