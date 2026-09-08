#!/bin/bash
# Wait for mcp1k stage A, gate it on PRODUCTS, then start stage B.
set -u
SCR=$(cd "$(dirname "$0")" && pwd)
until grep -q 'run_chain_group rc=' "$HOME/tmp/d102m-A-mcp1k.log" 2>/dev/null; do sleep 30; done
echo "stage A finished: $(grep 'run_chain_group rc=' $HOME/tmp/d102m-A-mcp1k.log)"
"$SCR/d102m_stageA_complete.sh" mcp1k 1000 || { echo "REFUSE: mcp1k stage A incomplete -- not starting stage B"; exit 1; }
PR_JOBS=16 "$SCR/d102m_stageB.sh" mcp1k
