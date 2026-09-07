#!/bin/bash
# doc sbnd_xin/pr/146 -- the gate arm for kine_sat_cont_keep_deg, the arm-C
# waiver in the stray-satellite classifier.
#
# Forked from pr145_prodarm.sh (M10 fork-by-duplication; that script is the
# published source of doc 145 sec 8's gate and stays byte-identical).
#
# WHY 41 EVENTS AND NOT 3067.  The waiver can only change an event whose
# classifier reaches arm C, and arm C's verdicts are already fully enumerated:
# NeutrinoKinematics.cxx:467-570 logs EVERY drop, and the finished 3067-event
# arm work-*-d145np carries those lines.  scripts/pr146_sat_census.py over the
# 3000 numu events finds 70 drops, of which exactly 8 are arm C.  The waiver
# reads only `ang_mv`, which is computed from state fixed long before the
# classifier runs, so no event outside those 8 can move.  The manifest is
#     the 8 arm-C events  U  the pr127 sentinel registry (30 ids)
# = every event whose output CAN move, plus every event the suite asserts on.
#
# Two arms, same pin, same manifest:
#   TAG=d146sv0   (no TLA)     -- must be byte-identical to work-*-d145prod
#   TAG=d146sv25  (waiver 25)  -- PR_EXTRA_TLA=docs/pr/pr146-satkeep25.tla
#
# (d146satoff / d146sat are the SAME manifest run at an earlier, REFUTED
#  operating point -- the waiver keyed on ang_mv at 45 deg.  The owner's scan
#  moved it to ang_sv at 25; see doc pr/146 sec 7.  Those arms are kept as the
#  record of that step, not as the gate.)
#
# Usage: [JOBS=16] [PIN=/home/xqian/tmp/d146_libpin] TAG=... [TLA=...] \
#        ./scripts/pr146_satarm.sh
set -u
JOBS=${JOBS:-16}
PIN=${PIN:-/home/xqian/tmp/d146_libpin}
TAG=${TAG:-d146sv0}
SX=$(cd "$(dirname "$0")/.." && pwd)
cd "$SX" || exit 2

export LD_LIBRARY_PATH="$PIN:${LD_LIBRARY_PATH:-}"
export PR_EXTRA_STAGES=pr_display
unset PR_GROUP_SIZE
if [ -n "${TLA:-}" ]; then export PR_EXTRA_TLA="$TLA"; else unset PR_EXTRA_TLA; fi

# The 8 arm-C events first in each list, then the sentinel ids in that sample.
# arm-C movers: mcp1k 408534 321371 320667 54341 ; mcp2k 74336 170098 94392 392009
EV_ncpi0="37112"
EV_nuecc48="69314 137238"
EV_mcp1k="408534 321371 320667 54341 395610 350935 172794 175896 281595 292643 313847 315167 348471"
EV_mcp2k="74336 170098 392009 94392 101828 393505 47212 52693 53793 55740 66366 67026 69314 72786 77328 77978 100222 105074 171572 173819 177536 179369 347890 406125 497311"

echo "=== pr146 arm $TAG  TLA=${TLA:-none}  jobs=$JOBS  pin=$PIN  $(date +%F_%H:%M:%S)"
md5sum "$PIN/libWireCellClus.so"

for s in ncpi0 nuecc48 mcp1k mcp2k; do
  eval "EVTS=\$EV_$s"
  OUT="work-$s-$TAG"
  echo "--- $s -> $OUT  ($(echo $EVTS | wc -w) events)  $(date +%H:%M:%S)"
  PR_JOBS=$JOBS ./run_pr_chain_batch.sh "work-$s-d97fv" "$OUT" data $EVTS
  echo "--- $s rc=$? events=$(ls -d $OUT/pr_evt*/ 2>/dev/null | wc -l)  $(date +%H:%M:%S) loadavg=$(cut -d' ' -f1 /proc/loadavg)"
done
echo "=== pr146 arm $TAG DONE $(date +%F_%H:%M:%S)"
