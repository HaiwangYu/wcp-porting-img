#!/bin/bash
# doc 102 stage A: reco1 -> imaging -> clustering + Q/L, one arm per sample.
# Usage: d102m_stageA.sh <ncpi0|nuecc48|mcp1k>
set -u
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
R1=$SX/input_files_reco1
export LD_LIBRARY_PATH=$HOME/tmp/d102m-libsnap:${LD_LIBRARY_PATH:-}   # doc 102: pinned binary
S=$1
case "$S" in
  ncpi0)   IN=$R1/nc-sideband_filtered_frameshift.root
           EXTRA=(--fsproduct 'sbnd::timing::FrameShiftInfo_frameshift__FILTERFRAMESHIFT.')
           JOBS=2 ;;
  nuecc48) IN=$R1/data_filtered_decoded_reco1-fe6033f3-07a0-4971-cea5-16ce59269fba_eventidfiltered_frameshift.root
           EXTRA=() ; JOBS=3 ;;
  mcp1k)   IN=$R1/data_MCP2025C_reco1_frameshift_first1000ev.root
           EXTRA=() ; JOBS=${MCP1K_JOBS:-8} ;;
  *) echo "unknown sample: $S" >&2; exit 1 ;;
esac
cd "$SX"
echo "=== stage A $S : jobs=$JOBS  in=$IN"
echo "=== toolkit HEAD before: $(git -C /nfs/data/1/xqian/toolkit-dev/toolkit rev-parse HEAD)"
SBND_MAX_JOBS=$JOBS ./run_chain_group.sh "$IN" "work-$S-d102m" data \
    --size 16 --layout perevt "${EXTRA[@]}"
rc=$?
echo "=== run_chain_group rc=$rc"
echo "=== toolkit HEAD after : $(git -C /nfs/data/1/xqian/toolkit-dev/toolkit rev-parse HEAD)"
echo "=== ql_evt dirs: $(ls -d work-$S-d102m/ql_evt* 2>/dev/null | wc -l)"
exit $rc
