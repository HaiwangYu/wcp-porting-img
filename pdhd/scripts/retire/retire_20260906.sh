#!/bin/bash
# Cleanup round 2026-09-06 -- deletion driver.  DRY RUN unless CONFIRM=yes.
#
#   ./retire_20260906.sh <tier> [tree ...]        tier = 1 | 2
#   CONFIRM=yes ./retire_20260906.sh 1 sbnd pdvd pdhd
#
# TIER 1 is what the owner's instruction plainly licenses: uncited, non-input,
# non-production, non-open-round arms.  TIER 2 is the named families that are
# cited only by their own CLOSED round's doc -- each carries a stated cost in
# plan_20260906.py and needs its own explicit yes.  They are separate runs on
# purpose: agreeing to tier 1 is not agreeing to tier 2.
#
# THE TRAP THIS GUARDS (doc 100 catch 2): the 08-31 driver built its tier
# filename by interpolation, a literal rename missed it, and the first dry run
# silently targeted the PREVIOUS round's already-deleted list and reported
# dirs=0.  So this refuses unless the tier file exists, is non-empty, and EVERY
# line still exists on disk.  Always compare its counts against what
# plan_20260906.py printed before typing CONFIRM=yes.
set -u
D="$(cd "$(dirname "$0")" && pwd)"

# ---- INTERLOCK A: RE-PLAN AT CONFIRM TIME -------------------------------
# A peer session started 11 minutes into this round's planning (PID 2727386,
# cwd toolkit/) and on 09-04 a live round created SEVEN new arm families
# between plan and confirm.  A tier file frozen at plan time cannot see them.
# So on CONFIRM=yes this re-runs the planner and refuses if any interlock now
# fails or if any tier file changed -- it refuses rather than deletes under a
# peer.  Set REPLAN=no only to re-confirm a plan you just re-ran by hand.
if [ "${CONFIRM:-no}" = yes ] && [ "${REPLAN:-yes}" = yes ]; then
  echo "== INTERLOCK A: re-planning before deleting (peer-session guard)"
  mkdir -p "$D/.preplan"; cp "$D"/tier?_*_20260906.txt "$D/.preplan/"
  if ! python3 "$D/plan_20260906.py" > "$D/plan_20260906.confirm.out" 2>&1; then
    echo "   REFUSING: the plan no longer passes its interlocks. See"
    echo "   $D/plan_20260906.confirm.out"; exit 10
  fi
  changed=0
  for f in "$D"/tier?_*_20260906.txt; do
    b=$(basename "$f")
    cmp -s "$f" "$D/.preplan/$b" || { echo "   CHANGED since plan time: $b"; changed=1; }
  done
  if [ "$changed" != 0 ]; then
    echo "   REFUSING: the tier files moved between plan and confirm -- that is"
    echo "   what a live peer looks like.  Review the diff, then re-confirm."
    exit 11
  fi
  echo "   OK: all interlocks still PASS and every tier file is unchanged."
fi
TIER=${1:?tier (1 or 2)}; shift || true
case "$TIER" in 1|2) ;; *) echo "tier must be 1 or 2"; exit 1;; esac
TREES=${*:-sbnd pdvd pdhd}
CONFIRM=${CONFIRM:-no}

for t in $TREES; do
  TF="$D/tier${TIER}_${t}_20260906.txt"
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
  # the record layer must be frozen BEFORE the bytes go (M13: the doc keeps the
  # summary, the archive keeps the record).
  REC="$D/../../archive/records/cleanup-20260906"
  if [ "$CONFIRM" = yes ] && [ ! -d "$REC" ] && [ "$t" = pdhd ]; then
    echo "   REFUSING: $REC missing -- run archive_records_20260906.py first."; exit 6
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
echo "count per tree; this number only means something compared against that."
for t in pdhd pdvd sbnd/sbnd_xin; do
  echo "   $t: $(find /home/xqian/toolkit-dev/wcp-porting-img/$t -xtype l 2>/dev/null | wc -l) broken symlinks"
done
[ "$CONFIRM" = yes ] || echo -e "\nDRY RUN.  Re-run with CONFIRM=yes to execute."
