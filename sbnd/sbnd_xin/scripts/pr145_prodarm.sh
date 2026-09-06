#!/bin/bash
# doc sbnd_xin/pr/145 sec 8 -- the TARGETED arm that gates the SBND production
# flip of kine_near_pointing_impact / _miss_deg to 200 cm / 30 deg.
#
# NO PR_EXTRA_TLA, on purpose.  An arm that forces the keys cannot show that the
# COMMITTED DEFAULT carries them (doc 144's `prod` arm makes the same point).
# This arm runs the driver exactly as production now compiles it.
#
# WHY 35 EVENTS AND NOT 3067.  The pointing test can only change an event that
# reaches it, and the pool it tests is built BEFORE the test runs:
# NeutrinoKinematics.cxx:892-915 fills near_cands from kine_near_gap,
# kine_near_end_tol, kine_near_kink_deg and kine_near_min_len only -- no
# pointing threshold is read there.  So no threshold can enlarge the pool, and
# the already-complete 3067-event armed arm work-*-d145np enumerated it:
# exactly 5 candidates in 5 events across the whole population.  Every other
# event runs identical code on identical data and cannot move.  The manifest is
# therefore
#     the 5 candidate events  U  the pr127 sentinel registry (30 ids)
# which is the complete set of events whose output CAN move, plus every event
# the sentinel suite asserts on.
#
# Usage: [JOBS=16] [PIN=/home/xqian/tmp/d145_libpin] ./scripts/pr145_prodarm.sh
set -u
JOBS=${JOBS:-16}
PIN=${PIN:-/home/xqian/tmp/d145_libpin}
TAG=${TAG:-d145prod}
SX=$(cd "$(dirname "$0")/.." && pwd)
cd "$SX" || exit 2

export LD_LIBRARY_PATH="$PIN:${LD_LIBRARY_PATH:-}"
export PR_EXTRA_STAGES=pr_display
unset PR_GROUP_SIZE
unset PR_EXTRA_TLA

# The 5 movers first in each list, then the sentinel ids present in that sample.
EV_ncpi0="37112"
EV_nuecc48="69314 137238"
EV_mcp1k="395610 350935 172794 175896 281595 292643 313847 315167 348471"
EV_mcp2k="392009 101828 393505 47212 52693 53793 55740 66366 67026 69314 72786 77328 77978 94392 100222 105074 171572 173819 177536 179369 347890 406125 497311"

echo "=== pr145 arm $TAG (no TLA -- the committed default)  jobs=$JOBS  pin=$PIN  $(date +%F_%H:%M:%S)"
md5sum "$PIN/libWireCellClus.so"

for s in ncpi0 nuecc48 mcp1k mcp2k; do
  eval "EVTS=\$EV_$s"
  OUT="work-$s-$TAG"
  echo "--- $s -> $OUT  ($(echo $EVTS | wc -w) events)  $(date +%H:%M:%S)"
  PR_JOBS=$JOBS ./run_pr_chain_batch.sh "work-$s-d97fv" "$OUT" data $EVTS
  echo "--- $s rc=$? events=$(ls -d $OUT/pr_evt*/ 2>/dev/null | wc -l)  $(date +%H:%M:%S) loadavg=$(cut -d' ' -f1 /proc/loadavg)"
done
echo "=== pr145 arm $TAG DONE $(date +%F_%H:%M:%S)"
