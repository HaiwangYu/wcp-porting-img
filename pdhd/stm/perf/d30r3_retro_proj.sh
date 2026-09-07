#!/usr/bin/env bash
# doc 30 r3: retro-verify T_proj_data across the round-1 gate arms with the
# non-vacuous hasher (the round-1/2 gate could not see this tree).
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img || exit 1
H=pdhd/stm/perf/d30_hash_proj.py
for pair in "pdhd d30hpre d30hpost" "pdhd d30hnupre d30hnupost" "pdvd d30vpre d30vpost" "pdvd d30vnupre d30vnupost"; do
  set -- $pair; det=$1 a=$2 b=$3
  same=0; diff=0; miss=0
  for da in $det/work/*_$a; do
    e=$(basename "$da"); e=${e%_$a}
    db="$det/work/${e}_$b"
    fa="$da/tracking-stm.root"; fb="$db/tracking-stm.root"
    [ -f "$fa" ] || fa="$da/tracking-pr.root"
    [ -f "$fb" ] || fb="$db/tracking-pr.root"
    if [ ! -f "$fa" ] || [ ! -f "$fb" ]; then miss=$((miss+1)); continue; fi
    ha=$(nice -n 19 python3 $H "$fa" | awk '{print $1" "$3" "$4}')
    hb=$(nice -n 19 python3 $H "$fb" | awk '{print $1" "$3" "$4}')
    if [ "$ha" = "$hb" ]; then same=$((same+1)); else diff=$((diff+1)); echo "  DIFF $det $e"; echo "    A: $ha"; echo "    B: $hb"; fi
  done
  echo "$det $a vs $b : T_proj_data same=$same diff=$diff missing=$miss"
done
