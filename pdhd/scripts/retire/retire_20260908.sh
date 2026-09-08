#!/bin/bash
# Cleanup round 2026-09-08 -- deletion driver.  DRY RUN unless CONFIRM=yes.
#
#   ./retire_20260908.sh <tier> [tree ...]        tier = 1 | 2
#   CONFIRM=yes ./retire_20260908.sh 2 sbnd
#
# THIS ROUND HAS ONE TIER WITH ANYTHING IN IT.  Tier 2 is the superseded
# prod-2026-09-04 chain in sbnd_xin -- grp0825 (imaging) -> d97fv (stage A Q/L)
# -> d144fixprod (stage B) -- 12 dirs, 35.85 GiB, every one of them named in
# sbnd_xin/scripts/retire/PROTECTED.txt today.  So this is not a mechanical
# sweep: it is one owner decision with three grounds and three stated costs, all
# written out in plan_20260908.py and doc 103.  Tier 1 is empty by measurement,
# and pdvd/pdhd release nothing at all -- see doc 103 sec 4 for why that is the
# honest answer rather than a missing tier.
#
# ORDER MATTERS AND IS ENFORCED.  grp0825 is still borrowed by five PROTECTED
# arms when this runs, so the sequence is:
#     1. archive_records_20260908.py 2        freeze the record layer  (M13)
#     2. materialise_20260908.py              copy the 119 borrowed dirs in
#     3. this driver, CONFIRM=yes             delete
# Step 2 must have left ZERO links into the substrate, and this driver re-checks
# that itself rather than trusting that it ran -- see INTERLOCK M below.  A
# CONFIRM-only path that nothing exercised is how 09-06 shipped three defects
# past five clean dry runs; materialise_20260908.py carries a STUB= mode that
# runs its writing branch end-to-end, and it was run before this driver existed.
#
# THE TRAP THIS GUARDS (doc 100 catch 2): the 08-31 driver built its tier
# filename by interpolation, a literal rename missed it, and the first dry run
# silently targeted the PREVIOUS round's already-deleted list and reported
# dirs=0.  So this refuses unless the tier file exists, is non-empty, and EVERY
# line still exists on disk.  Always compare its counts against what
# plan_20260908.py printed before typing CONFIRM=yes.
set -u
D="$(cd "$(dirname "$0")" && pwd)"
STAMP=20260908

TIER=${1:?tier (1-2)}; shift || true
case "$TIER" in 1|2) ;; *) echo "tier must be 1 or 2"; exit 1;; esac
TREES=${*:-sbnd pdvd pdhd}
CONFIRM=${CONFIRM:-no}

# ---- INTERLOCK A: RE-PLAN AT CONFIRM TIME -------------------------------
# On 09-06 a peer session started 11 minutes into planning and wrote two new
# arms; on 09-04 a live round created SEVEN new families between plan and
# confirm.  A tier file frozen at plan time cannot see them.  Scoped to the tier
# being run: comparing every tier file means tier 1 having executed makes
# tier 2 refuse -- the round's own first pass raising a peer alarm.
# NOTE the 09-06 bug this avoids: ${TIER} must be assigned ABOVE this block.
if [ "${CONFIRM:-no}" = yes ] && [ "${REPLAN:-yes}" = yes ]; then
  echo "== INTERLOCK A: re-planning before deleting (peer-session guard)"
  mkdir -p "$D/.preplan-$STAMP"
  cp "$D"/tier${TIER}_*_${STAMP}.txt "$D/.preplan-$STAMP/" 2>/dev/null || true
  if ! python3 "$D/plan_${STAMP}.py" > "$D/plan_${STAMP}.confirm.out" 2>&1; then
    echo "   REFUSING: the plan no longer passes its interlocks. See"
    echo "   $D/plan_${STAMP}.confirm.out"; exit 10
  fi
  changed=0
  for f in "$D"/tier${TIER}_*_${STAMP}.txt; do
    b=$(basename "$f")
    cmp -s "$f" "$D/.preplan-$STAMP/$b" || { echo "   CHANGED since plan time: $b"; changed=1; }
  done
  if [ "$changed" != 0 ]; then
    echo "   REFUSING: the tier files moved between plan and confirm -- that is"
    echo "   what a live peer looks like.  Review the diff, then re-confirm."
    exit 11
  fi
  echo "   OK: all interlocks still PASS and every tier file is unchanged."
fi

# ---- INTERLOCK M: the MATERIALISE step must have RUN, not merely exist ----
# Checked by looking at the tree, not at a marker file: zero symlinks anywhere
# in sbnd_xin may still resolve into a grp0825 arm.  If step 2 was skipped this
# fires and nothing is deleted.  Only meaningful for the sbnd tree.
if [ "$CONFIRM" = yes ] && [[ " $TREES " == *" sbnd "* ]] && [ "$TIER" = 2 ]; then
  echo "== INTERLOCK M: has materialise_20260908.py run?"
  left=$(CONFIRM=no python3 "$D/materialise_${STAMP}.py" 2>&1 | head -1)
  case "$left" in
    *"nothing borrows"*) echo "   OK: 0 links resolve into grp0825." ;;
    *) echo "   REFUSING: links still resolve into the substrate --"
       echo "   $left"
       echo "   Run:  CONFIRM=yes python3 $D/materialise_${STAMP}.py"
       exit 12 ;;
  esac
fi

for t in $TREES; do
  TF="$D/tier${TIER}_${t}_${STAMP}.txt"
  echo "=================================================================="
  echo "== $t   tier $TIER   file: $TF"
  if [ ! -s "$TF" ]; then
    echo "   (empty or missing tier file -- nothing planned for this tree/tier)"; continue
  fi
  n=$(wc -l < "$TF"); miss=0; kb=0
  while read -r p; do
    if [ -e "$p" ]; then kb=$((kb + $(du -sk "$p" | cut -f1))); else miss=$((miss+1)); fi
  done < "$TF"
  echo "   lines $n | present $((n-miss)) | already gone $miss | $(echo "scale=2; $kb/1048576" | bc) GiB"
  if [ "$miss" -gt 0 ]; then
    echo "   REFUSING: $miss of $n targets are already gone -- that is the"
    echo "   signature of pointing at a PREVIOUS round's tier list. Re-plan."
    exit 3
  fi
  bad=$(while read -r p; do [ -L "$p" ] && echo "$p"; done < "$TF")
  if [ -n "$bad" ]; then echo "   REFUSING: symlink in the target list:"; echo "$bad"; exit 4; fi
  out=$(grep -cv '^/home/xqian/toolkit-dev/wcp-porting-img/' "$TF" || true)
  if [ "$out" != 0 ]; then echo "   REFUSING: $out targets outside wcp-porting-img"; exit 5; fi
  # The record layer must be frozen BEFORE the bytes go (M13).  The 09-06 driver
  # had two CONFIRM-only bugs here -- a path that never existed, and a gate on
  # the LAST tree so the first two were already deleted when it refused.  This
  # is the corrected shape: real output path, per tree AND per tier, every tree.
  REC="$D/../../../sbnd/sbnd_xin/archive/records/cleanup-${STAMP}/${t}-tier${TIER}"
  if [ "$CONFIRM" = yes ] && [ ! -d "$REC" ]; then
    echo "   REFUSING: $REC missing -- run 'python3 archive_records_${STAMP}.py $TIER' first."
    exit 6
  fi

  if [ "$CONFIRM" = yes ]; then
    echo "   DELETING..."
    xargs -a "$TF" -d '\n' rm -rf
    echo "   done, rc=$?"
  else
    echo "   DRY RUN -- first 3 targets:"; head -3 "$TF" | sed 's/^/      /'
  fi
done

echo
echo "POST-STATE CHECK.  interlock 4 recorded the PRE-existing broken-symlink"
echo "count per tree (0 / 0 / 0 on 2026-09-08); this number only means"
echo "something compared against that."
for t in pdhd pdvd sbnd/sbnd_xin; do
  echo "   $t: $(find /home/xqian/toolkit-dev/wcp-porting-img/$t -xtype l 2>/dev/null | wc -l) broken symlinks"
done
[ "$CONFIRM" = yes ] || echo -e "\nDRY RUN.  Re-run with CONFIRM=yes to execute."
