#!/bin/bash
# doc 102 stage B: the 15-stage tagger + PR chain on a doc-102 stage-A arm.
# Usage: [PR_JOBS=N] d102m_stageB.sh <ncpi0|nuecc48|mcp1k>
set -u
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
export LD_LIBRARY_PATH=$HOME/tmp/d102m-libsnap:${LD_LIBRARY_PATH:-}   # doc 102: pinned binary
export PR_EXTRA_STAGES=pr_display     # calib dump; no physics effect (doc pr/3)
S=$1
cd "$SX"
echo "=== stage B $S : PR_JOBS=${PR_JOBS:-6}"
echo "=== toolkit HEAD before: $(git -C /nfs/data/1/xqian/toolkit-dev/toolkit rev-parse HEAD)"
./run_pr_chain_batch.sh "work-$S-d102m" "work-$S-d102mpr" data
rc=$?
echo "=== run_pr_chain_batch rc=$rc"
echo "=== toolkit HEAD after : $(git -C /nfs/data/1/xqian/toolkit-dev/toolkit rev-parse HEAD)"
echo "=== pr_evt dirs : $(ls -d work-$S-d102mpr/pr_evt* 2>/dev/null | wc -l)"
echo "=== rc!=0 events: $(grep -L 'rc=0' work-$S-d102mpr/pr_evt*/rc.txt 2>/dev/null | wc -l)"
echo "=== nusel-events rows: $(wc -l < work-$S-d102mpr/nusel-events.tsv 2>/dev/null)"
exit $rc
