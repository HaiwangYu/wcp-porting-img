#!/usr/bin/env bash
# doc pdhd/09 Phase 1 -- full chain for run 28084 into the _d09 tag.
#
#   NF/SP + DNN-ROI + L1SP  ->  imaging  ->  all-PD light  ->  clus + Q/L + calib
#
# Run 28084 is a 14 mV/fC run (measured: median per-channel MAD 13 ADC vs 7 for
# 029107/027980, ratio 1.86 ~ 14/7.8).  Both NF/SP runners auto-derive 7.8 from
# the directory name input_data_7p8_new_coh_grouping -- which names the
# COHERENT-NOISE GROUPING epoch, not the gain -- so -g 14 is mandatory.
#
# DAQ ident = 74408 + 8*idx, verified from the tar members of all 31 events.
#
# Usage:  EVENTS="0 1 2" JOBS=6 PIN=/home/xqian/tmp/d09_libpin/pin ./d09_run_chain.sh
#         EVENTS=all
set -uo pipefail

PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
S="$PDHD/docs/scripts"
RUN=28084; RUN6=028084; TAG=d09; GAIN=14
JOBS=${JOBS:-6}
PIN=${PIN:-/home/xqian/tmp/d09_libpin/pin}
LOGD=${LOGD:-/home/xqian/tmp/d09/chainlogs}
mkdir -p "$LOGD"

[ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

EV=${EVENTS:-all}
if [ "$EV" = "all" ]; then EV=$(seq 0 30); fi

one_event() {
    local idx=$1
    local ident=$((74408 + 8*idx))
    local wd="$PDHD/work/${RUN6}_${idx}_${TAG}"
    local log="$LOGD/evt${idx}.log"
    local t0=$SECONDS
    (
      echo "=== d09 chain run=$RUN idx=$idx ident=$ident tag=$TAG gain=$GAIN ==="
      cd "$PDHD" || exit 1

      if [ ! -f "$wd/protodunehd-sp-dnnroi-frames-anode3.tar.bz2" ]; then
        echo "--- [1/4] NF/SP + DNN-ROI + L1SP ---"
        ./run_nf_sp_dnnroi_evt.sh -g $GAIN -L on -N dnn -O "_${TAG}" $RUN $idx || { echo "FAIL nfsp"; exit 11; }
      else echo "--- [1/4] NF/SP already present, skip ---"; fi

      if [ ! -f "$wd/.d09-img-done" ]; then
        echo "--- [2/4] imaging ---"
        "$S/d09_img_tagged.sh" $RUN $idx $TAG || { echo "FAIL img"; exit 12; }
      else echo "--- [2/4] imaging already done, skip ---"; fi

      if [ ! -f "$PDHD/work/${RUN6}_allpd${ident}/opflash_pdhd-allpd-wct.tar.gz" ]; then
        echo "--- [3/4] all-PD light (ident=$ident, run UNPADDED) ---"
        ./run_light_allpd_evt.sh $RUN $ident || { echo "FAIL light"; exit 13; }
      else echo "--- [3/4] light already present, skip ---"; fi
      ln -sfn "../${RUN6}_allpd${ident}/opflash_pdhd-allpd-wct.tar.gz" "$wd/opflash_pdhd-wct.tar.gz"

      if [ ! -f "$wd/calib-evt${ident}.json" ]; then
        echo "--- [4/4] clus + Q/L + calib (+pctree +assoc) ---"
        ./run_clus_evt.sh -s "$TAG" -calib -save-pctree -save-assoc $RUN "$idx" \
          || { echo "FAIL clus"; exit 14; }
      else echo "--- [4/4] clus already done, skip ---"; fi

      echo "=== OK idx=$idx in $((SECONDS-t0)) s ==="
      touch "$wd/.d09-chain-done"
    ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$wd/.d09-chain-done" ]; then
        echo "[d09] idx=$idx OK  ($((SECONDS-t0)) s)"
    else
        echo "[d09] idx=$idx FAILED rc=$rc -- $(grep -m1 '^FAIL' "$log" 2>/dev/null || echo 'see') $log"
    fi
}

n=0
for idx in $EV; do
    one_event "$idx" &
    n=$((n+1))
    if [ $((n % JOBS)) -eq 0 ]; then wait; fi
done
wait
echo "[d09] all requested events finished"
