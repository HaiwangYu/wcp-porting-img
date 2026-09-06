#!/bin/bash
# doc sbnd_xin/pr/145 -- the arms that price the pr/129 pointing test on the
# near-cross-cluster kine pool (toolkit 7c4bf46a, kine_near_pointing_impact).
#
# Fork of pr144_arms.sh (M10: that script produced doc 144's census and stays
# byte-untouched).  Two arms:
#
#   bridge -> work-<s>-d145bridge   knob OFF, only the 13 events of the
#             d144np2 manifest.  THE EPOCH BRIDGE: work-*-d144fixprod was
#             produced by the library built at 25baa8aa; this round runs
#             7c4bf46a.  7c4bf46a's committed T0 proof covers the compiled
#             CONFIG, not the two LIBRARIES.  This arm is what licenses
#             d144fixprod as a zero-cost negative control -- without it the
#             control is an unproven cross-epoch comparison (doc 92's trap,
#             and feedback_check_the_cfg_epoch_between_arms).
#
#   np     -> work-<s>-d145np       armed via docs/pr/pr144-nearpoint.tla
#             (impact = 20 cm, miss_deg = 30 deg, pr/129's SBND production
#             values), all four samples = 3067 events.
#
# The armed arm emits one INFO line per candidate reaching the test, COUNT and
# SKIP alike (NeutrinoKinematics.cxx:883-890).  There is NO persisted counter --
# n_near is function-local and KineInfo has no member for it -- so THE LOG IS
# THE ONLY RECORD.  Do not prune work-*-d145np/pr_evt*/wct_pr_evt*.log; that is
# what pr145_pointing_census.py reads.
#
# Usage: [JOBS=16] [PIN=/home/xqian/tmp/d145_libpin] ./scripts/pr145_arms.sh bridge|np
set -u
ARM=${1:?usage: pr145_arms.sh bridge|np}
JOBS=${JOBS:-16}
PIN=${PIN:-/home/xqian/tmp/d145_libpin}
SX=$(cd "$(dirname "$0")/.." && pwd)
cd "$SX" || exit 2

export LD_LIBRARY_PATH="$PIN:${LD_LIBRARY_PATH:-}"
export PR_EXTRA_STAGES=pr_display          # calib-pr-evt<ID>.json, which the census scripts read
unset PR_GROUP_SIZE                        # per-event mode => per-event wall_s / maxrss_kb

# The d144np2 manifest, per sample.  13 events, and it is not an arbitrary
# subset: it carries 494297 (the doc 144 crash), 393505 (item 4), 177536 and
# 98844 (item 3b's two rest-mass payers), 347890 (item 3a) and 137238 (item 5).
BRIDGE_mcp1k="175896"
BRIDGE_mcp2k="100135 171572 177536 179369 347890 393505 47212 494297 94392 98844"
BRIDGE_nuecc48="111412 137238"
BRIDGE_ncpi0=""

case "$ARM" in
  bridge) unset PR_EXTRA_TLA; TAG=d145bridge ;;
  np)     export PR_EXTRA_TLA="$SX/docs/pr/pr144-nearpoint.tla"; TAG=d145np ;;
  *)      echo "arm must be bridge|np" >&2; exit 2 ;;
esac

echo "=== pr145 arm $TAG  jobs=$JOBS  pin=$PIN  $(date +%F_%H:%M:%S)"
md5sum "$PIN/libWireCellClus.so"
[ -n "${PR_EXTRA_TLA:-}" ] && { echo "--- PR_EXTRA_TLA ---"; grep -v '^#' "$PR_EXTRA_TLA"; }

for s in ncpi0 nuecc48 mcp1k mcp2k; do          # small samples first: fail fast
  if [ "$ARM" = bridge ]; then
    eval "EVTS=\$BRIDGE_$s"
    [ -z "$EVTS" ] && { echo "--- $s: no bridge events, skipped"; continue; }
  else
    EVTS=""
  fi
  OUT="work-$s-$TAG"
  echo "--- $s -> $OUT  $(date +%H:%M:%S)"
  PR_JOBS=$JOBS ./run_pr_chain_batch.sh "work-$s-d97fv" "$OUT" data $EVTS
  echo "--- $s rc=$? events=$(ls -d $OUT/pr_evt*/ 2>/dev/null | wc -l)  $(date +%H:%M:%S) loadavg=$(cut -d' ' -f1 /proc/loadavg)"
done
echo "=== pr145 arm $TAG DONE $(date +%F_%H:%M:%S)"
