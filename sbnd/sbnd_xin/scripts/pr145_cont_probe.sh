#!/bin/bash
# doc sbnd_xin/pr/145 item 3b -- run the 21-candidate split-muon working set
# (docs/pr/pr145-splitcensus.tsv) with kine_continuation_debug armed, so every
# flag_reduce decision is on the record.
#
# Runs on the INSTRUMENTED pin, which is a different binary from Round A's arm
# pin -- the two rounds run concurrently and must not read each other's libs.
#
# Usage: [JOBS=8] [TAG=d145cont2] [PIN=...] ./scripts/pr145_cont_probe.sh
#
# M13: a re-run gets a FRESH tag, never the previous one.
set -u
JOBS=${JOBS:-8}
PIN=${PIN:-/home/xqian/tmp/d145_libpin_cont2}
TAG=${TAG:-d145cont2}
SX=$(cd "$(dirname "$0")/.." && pwd)
cd "$SX" || exit 2
CENSUS=${CENSUS:-$SX/docs/pr/pr145-splitcensus.tsv}

export LD_LIBRARY_PATH="$PIN:${LD_LIBRARY_PATH:-}"
export PR_EXTRA_STAGES=pr_display
export PR_EXTRA_TLA="$SX/docs/pr/pr145-cont.tla"
unset PR_GROUP_SIZE

echo "=== pr145 continuation probe  jobs=$JOBS  pin=$PIN  $(date +%F_%H:%M:%S)"
md5sum "$PIN/libWireCellClus.so"
grep -v '^#' "$PR_EXTRA_TLA"

for s in mcp1k mcp2k nuecc48 ncpi0; do
  EVTS=$(awk -F'\t' -v s="$s" 'NR>2 && $1==s {printf "%s ", $2}' "$CENSUS")
  [ -z "$EVTS" ] && { echo "--- $s: none in census"; continue; }
  OUT="work-$s-$TAG"
  echo "--- $s -> $OUT  events: $EVTS"
  PR_JOBS=$JOBS ./run_pr_chain_batch.sh "work-$s-d97fv" "$OUT" data $EVTS
  echo "--- $s rc=$? events=$(ls -d $OUT/pr_evt*/ 2>/dev/null | wc -l)  loadavg=$(cut -d' ' -f1 /proc/loadavg)"
done
echo "=== pr145 continuation probe DONE $(date +%F_%H:%M:%S)"
