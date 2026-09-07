#!/usr/bin/env bash
# doc pdhd/09 Phase 2 -- the FULL same-binary 029107 control.
#
# d09ref reuses 029107's June-2026 imaging and re-runs only clus+Q/L under the pin.
# That is not enough: libWireCellImg.so is 2026-09-05 while those cluster tarballs are
# 2026-06-17, so the 28084 side (imaged today) and the 029107 side would differ by ~3
# months of imaging-binary drift as well as by run.  This arm re-images 029107 from its
# own DNN-ROI frames under the SAME pin, so d09ctl vs d09 is run-only, and
# d09ref vs d09ctl isolates the imaging drift.
#
# Nothing under work/029107_<idx>/ is written -- frames are symlinked in.  M13.
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
S="$PDHD/docs/scripts"
RUN=29107; RUN6=029107; TAG=${TAG:-d09ctl}
PIN=${PIN:-/home/xqian/tmp/d09_libpin/pin}
JOBS=${JOBS:-6}
LOGD=${LOGD:-/home/xqian/tmp/d09/ctllogs}; mkdir -p "$LOGD"
[ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

one() {
    local idx=$1
    local src="$PDHD/work/${RUN6}_${idx}"
    local dst="$PDHD/work/${RUN6}_${idx}_${TAG}"
    local log="$LOGD/evt${idx}.log"
    [ -d "$src" ] || { echo "[d09ctl] idx=$idx NO SOURCE"; return; }
    mkdir -p "$dst"
    (
      cd "$PDHD" || exit 1
      for f in "$src"/protodunehd-sp-dnnroi-frames-anode*.tar.bz2; do
          ln -sfn "../${RUN6}_${idx}/$(basename "$f")" "$dst/$(basename "$f")"
      done
      op="$src/opflash_pdhd-wct.tar.gz"
      [ -e "$op" ] && ln -sfn "$(readlink -f "$op")" "$dst/opflash_pdhd-wct.tar.gz"
      [ -f "$dst/.d09-img-done" ] || "$S/d09_img_tagged.sh" $RUN "$idx" "$TAG" || exit 12
      ./run_clus_evt.sh -s "$TAG" -calib -save-pctree -save-assoc $RUN "$idx" || exit 14
      touch "$dst/.d09-ctl-done"
    ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$dst/.d09-ctl-done" ]; then echo "[d09ctl] idx=$idx OK"
    else echo "[d09ctl] idx=$idx FAILED rc=$rc -- $log"; fi
}
n=0
for idx in $(seq 0 29); do
    one "$idx" & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait
done
wait
echo "[d09ctl] done"
