#!/bin/bash
# doc pdhd/08 stage 4 -- one grade row per arm against the d08goff baseline.
# Primary (owner-facing): Steiner points far from live charge, on cluster-MATCHED
# populations only.  Cost: TGM/STM/FC tag flips as a SET census.
# Usage: ./docs/scripts/d08_grade.sh [base_tag] [arm_tag ...]
set -u
cd "$(dirname "$0")/../.." || exit 9
BASE=${1:-d08goff}; shift || true
D=docs/scripts
printf "%-9s %7s %13s %10s %8s %11s %6s | %s\n" arm "matched" ">3cm" ">10cm" ">30cm" "worst" "unmat" "TGM +/-   STM +/-   FC +/-"
for a in "$@"; do
  # Completion is the runner's own rc marker, NOT a count of zips: a zip exists
  # before its log is finalised, and grading a still-writing arm silently
  # produced a wrong FC column once (feedback_gate_against_a_running_arm).
  rcf="work/.d08_$a.rc"
  n=$(ls work/029107_*_$a/mabc-pr.zip 2>/dev/null | wc -l)
  if [ ! -s "$rcf" ]; then printf "%-9s NOT FINISHED (no %s; %s/30 zips)\n" "$a" "$rcf" "$n"; continue; fi
  rc=$(cat "$rcf")
  if [ "$rc" != 0 ] || [ "$n" -ne 30 ]; then
      printf "%-9s UNUSABLE rc=%s zips=%s/30\n" "$a" "$rc" "$n"; continue; fi
  g=$(python3 $D/d08_steiner_ghost.py --pair "$BASE" "$a" 2>/dev/null | grep -E "matched clusters|cm from live|> 10 cm|> 30 cm|worst distance|unmatched: base")
  t=$(python3 $D/d08_tag_flips.py "$BASE" "$a" 2>/dev/null | awk '$1=="TGM"||$1=="STM"||$1=="FC"{printf "%s %s/%s  ",$1,$4,$5}')
  printf "%-9s %7s %13s %10s %8s %11s %6s | %s\n" "$a" \
    "$(echo "$g" | sed -n 's/.*matched clusters \([0-9]*\).*/\1/p')" \
    "$(echo "$g" | sed -n 's/.*> 3 cm from live \([0-9]*\) -> \([0-9]*\).*/\1->\2/p')" \
    "$(echo "$g" | sed -n 's/.*> 10 cm  *\([0-9]*\) -> \([0-9]*\).*/\1->\2/p')" \
    "$(echo "$g" | sed -n 's/.*> 30 cm  *\([0-9]*\) -> \([0-9]*\).*/\1->\2/p')" \
    "$(echo "$g" | sed -n 's/.*worst distance  *\([0-9.]*\) -> \([0-9.]*\).*/\1->\2/p')" \
    "$(echo "$g" | sed -n 's/.*unmatched: base \([0-9]*\), arm \([0-9]*\).*/\1\/\2/p')" "$t"
done
