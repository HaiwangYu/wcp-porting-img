#!/usr/bin/env bash
# doc 30 step 3.0: the accumulator bracket on two PDHD events, sequential, pinned lib.
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
PIN=/home/xqian/tmp/d30_libpin
LOGD=/home/xqian/tmp/d30/a; mkdir -p "$LOGD"
export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cd "$PDHD"
echo "pin BEFORE: $(md5sum $PIN/libWireCellClus.so | cut -c1-12)"
for ev in "029107 18" "028084 2"; do
  set -- $ev; run=$1 idx=$2
  # a1: production (-stm -stm-fit), save_stm_fit=true (the jsonnet default)
  PDHD_MAX_JOBS=1 ./run_pr_evt.sh -s d30a1 -stm-fit $run $idx > "$LOGD/a1_${run}_${idx}.log" 2>&1; echo "a1 $run/$idx rc=$?"
  # a2: same but no ROOT writer (accumulators still built)
  PDHD_MAX_JOBS=1 ./run_pr_evt.sh -s d30a2            $run $idx > "$LOGD/a2_${run}_${idx}.log" 2>&1; echo "a2 $run/$idx rc=$?"
  # a3: save_stm_fit=false -> no accumulators, no local PCs, no WireCellRoot
  PDHD_PR_TLA="-S save_stm_fit=false" PDHD_MAX_JOBS=1 ./run_pr_evt.sh -s d30a3 $run $idx > "$LOGD/a3_${run}_${idx}.log" 2>&1; echo "a3 $run/$idx rc=$?"
done
echo "pin AFTER: $(md5sum $PIN/libWireCellClus.so | cut -c1-12)"
