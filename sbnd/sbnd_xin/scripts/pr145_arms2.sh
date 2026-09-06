#!/bin/bash
# doc sbnd_xin/pr/145 sec 8 -- the arm that validates THE CORRECTED operating
# point (impact = 200 cm, miss_deg = 30 deg) before the SBND production flip.
#
# Fork of pr145_arms.sh (M10: that script produced sec 3's census and the epoch
# bridge and stays byte-untouched).  ONE arm:
#
#   np200 -> work-<s>-d145np200   armed via docs/pr/pr145-nearpoint200.tla,
#            all four samples = 3067 events, on the SAME pin d145_libpin
#            (toolkit 7c4bf46a) the sec-3 census ran on, so work-*-d144fixprod
#            stays licensed as the negative control by the sec-2 epoch bridge.
#
# WHY A NEW 3067-EVENT ARM AND NOT A RE-SCORE OF THE SEC-3 CENSUS.  The census
# enumerated every candidate that reached the test under a config that REFUSED
# ALL FIVE.  At 200/30 one candidate (392009 seg 58015) is ADMITTED, the counted
# set grows, and candidates that never reached the test before may now do so --
# with impacts nobody has observed.  So "200 cm places no effective bound" is a
# statement about the OLD pool.  This arm's own census is what tests it: if a
# sixth candidate appears, or any impact lands in (110.22, 200], sec 3.8.1's
# 5/5 was scored on an incomplete pool and the flip must be re-scored.
#
# The armed arm emits one INFO line per candidate reaching the test, COUNT and
# SKIP alike (NeutrinoKinematics.cxx:883-890).  There is NO persisted counter,
# so THE LOG IS THE ONLY RECORD.  Do not prune
# work-*-d145np200/pr_evt*/wct_pr_evt*.log.
#
# Usage: [JOBS=16] [PIN=/home/xqian/tmp/d145_libpin] ./scripts/pr145_arms2.sh np200
# DO NOT RUN.  This arm was ABORTED partway through mcp1k on 2026-09-06 and is
# kept only as the record of what was launched (doc 145 sec 8.1).  The gate that
# actually shipped the flip is scripts/pr145_prodarm.sh -- 35 events, no TLA.
# Running this would spend an hour re-deriving a result the pool argument above
# already proves, and would write into an out_root that carries an ABORTED.txt.
echo "pr145_arms2.sh: ABORTED ARM, do not run -- see doc 145 sec 8.1;" >&2
echo "                the shipped gate is scripts/pr145_prodarm.sh" >&2
exit 2

set -u
ARM=${1:?usage: pr145_arms2.sh np200}
JOBS=${JOBS:-16}
PIN=${PIN:-/home/xqian/tmp/d145_libpin}
SX=$(cd "$(dirname "$0")/.." && pwd)
cd "$SX" || exit 2

export LD_LIBRARY_PATH="$PIN:${LD_LIBRARY_PATH:-}"
export PR_EXTRA_STAGES=pr_display          # calib-pr-evt<ID>.json, which the census scripts read
unset PR_GROUP_SIZE                        # per-event mode => per-event wall_s / maxrss_kb

case "$ARM" in
  np200) export PR_EXTRA_TLA="$SX/docs/pr/pr145-nearpoint200.tla"; TAG=d145np200 ;;
  *)     echo "arm must be np200" >&2; exit 2 ;;
esac

echo "=== pr145 arm $TAG  jobs=$JOBS  pin=$PIN  $(date +%F_%H:%M:%S)"
md5sum "$PIN/libWireCellClus.so"
echo "--- PR_EXTRA_TLA ---"; grep -v '^#' "$PR_EXTRA_TLA"

for s in ncpi0 nuecc48 mcp1k mcp2k; do          # small samples first: fail fast
  OUT="work-$s-$TAG"
  echo "--- $s -> $OUT  $(date +%H:%M:%S)"
  PR_JOBS=$JOBS ./run_pr_chain_batch.sh "work-$s-d97fv" "$OUT" data
  echo "--- $s rc=$? events=$(ls -d $OUT/pr_evt*/ 2>/dev/null | wc -l)  $(date +%H:%M:%S) loadavg=$(cut -d' ' -f1 /proc/loadavg)"
done
echo "=== pr145 arm $TAG DONE $(date +%F_%H:%M:%S)"
