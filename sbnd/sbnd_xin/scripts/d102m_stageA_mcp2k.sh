#!/bin/bash
# doc 102 stage A for mcp2k: TWO 1000-entry reco1 files into ONE out_root.
# The second invocation offsets the group NAMES by 63 (doc 81) so its g0 does
# not land on the first file's g0 and get skipped as already-present.
# Usage: [JOBS=N] d102m_stageA_mcp2k.sh <part1|part2>
set -u
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
D=/nfs/data/1/yuhw/production-prep/add-frameshift-data-2nd-2k-2026-08-15
export LD_LIBRARY_PATH=$HOME/tmp/d102m-libsnap:${LD_LIBRARY_PATH:-}   # doc 102: pinned binary
P=$1
case "$P" in
  part1) IN=$D/data_MCP2025C_reco1_frameshift_2nd1k_part1.root; GB=0 ;;
  part2) IN=$D/data_MCP2025C_reco1_frameshift_2nd1k_part2.root; GB=63 ;;
  *) echo "usage: $0 part1|part2" >&2; exit 1 ;;
esac
cd "$SX"
echo "=== stage A mcp2k $P : jobs=${JOBS:-8} gbase=$GB in=$IN"
echo "=== toolkit HEAD before: $(git -C /nfs/data/1/xqian/toolkit-dev/toolkit rev-parse HEAD)"
SBND_MAX_JOBS=${JOBS:-8} ./run_chain_group.sh "$IN" work-mcp2k-d102m data \
    --size 16 --layout perevt --gbase $GB
rc=$?
echo "=== run_chain_group rc=$rc ($P)"
echo "=== toolkit HEAD after : $(git -C /nfs/data/1/xqian/toolkit-dev/toolkit rev-parse HEAD)"
echo "=== ql_evt dirs: $(ls -d work-mcp2k-d102m/ql_evt* 2>/dev/null | wc -l)"
exit $rc
