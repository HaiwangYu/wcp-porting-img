#!/usr/bin/env bash
# doc pdhd/09 -- regenerate 029107's all-PD light under the PIN.
# work/029107_allpd<ident>/ dates from 2026-07-08 while libWireCellFlash.so is
# 2026-09-05 and libWireCellRoot.so 2026-09-06.  Measured PE enters chi2 directly,
# so a stale light product confounds the 28084 comparison exactly as stale imaging
# does.  -s _d09 writes to work/029107_allpd<ident>_d09/, leaving the July record
# untouched (M13).  ident = 983 + 8*idx.
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
PIN=${PIN:-/home/xqian/tmp/d09_libpin/pin}
JOBS=${JOBS:-6}
LOGD=/home/xqian/tmp/d09/lightlogs; mkdir -p "$LOGD"
[ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cd "$PDHD" || exit 1
n=0
for idx in $(seq 0 29); do
  ident=$((983 + 8*idx))
  (
    if [ ! -f "work/029107_allpd${ident}_d09/opflash_pdhd-allpd-wct.tar.gz" ]; then
      ./run_light_allpd_evt.sh -s _d09 29107 "$ident" || exit 13
    fi
  ) > "$LOGD/${ident}.log" 2>&1
  rc=$?
  [ $rc -eq 0 ] && echo "[d09light] ident=$ident OK" || echo "[d09light] ident=$ident FAILED rc=$rc"
  n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait
done
wait
echo "[d09light] done"
