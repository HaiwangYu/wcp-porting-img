#!/bin/bash
# Wait for BOTH mcp2k stage-A invocations, gate on PRODUCTS (the runner's own
# per-group verdict is unreliable for a two-invocation sample -- see
# d102m_stageA_complete.sh), then start stage B.
set -u
SCR=$(cd "$(dirname "$0")" && pwd)
for p in part1 part2; do
    until grep -q 'run_chain_group rc=' "$HOME/tmp/d102m-A-mcp2k-$p.log" 2>/dev/null; do sleep 30; done
    echo "mcp2k $p: $(grep 'run_chain_group rc=' $HOME/tmp/d102m-A-mcp2k-$p.log)"
done
"$SCR/d102m_stageA_complete.sh" mcp2k 2000 || { echo "REFUSE: mcp2k stage A incomplete -- not starting stage B"; exit 1; }
PR_JOBS=${PR_JOBS:-16} "$SCR/d102m_stageB.sh" mcp2k
