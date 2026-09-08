#!/bin/bash
# doc 102: stage-A completeness straight off the PRODUCTS, not off the runner's
# own verdict.
#
# Why this exists: run_chain_group.sh writes its per-group runner log as
# "$OUTROOT/.g$K.log" using the INTERNAL group index K, not the --gbase-offset
# name it gives the group DIRECTORY (g$((K+GBASE))).  Its final success check is
# `grep -q "^\[g$K\] ok" "$OUTROOT/.g$K.log"`.  So two concurrent invocations
# into one out_root -- which is exactly how a two-file sample like mcp2k is run
# -- share .g0.log .. .g62.log and can each read the OTHER's success line.  The
# products never collide (the group DIRS are offset), only the verdict does.
# This gate ignores logs entirely.
#
# Usage: d102m_stageA_complete.sh <sample> <expected_events>
set -u
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
S=$1; WANT=$2
A=$SX/work-$S-d102m
bad=0
ngrp=$(ls -d "$A"/g* 2>/dev/null | wc -l)
# every group's events.txt must be non-empty and every event must have products
short_grp=0; miss=0; empty=0; nev=0
for g in "$A"/g*; do
    [ -f "$g/events.txt" ] || { short_grp=$((short_grp+1)); continue; }
    n=$(wc -l < "$g/events.txt"); [ "$n" -gt 0 ] || short_grp=$((short_grp+1))
    while read -r e; do
        [ -n "$e" ] || continue
        nev=$((nev+1))
        f="$A/ql_evt$e/pctree-evt$e.tar.gz"
        if [ ! -e "$f" ]; then miss=$((miss+1)); echo "  MISSING pctree evt=$e (group $(basename $g))"
        elif [ ! -s "$f" ]; then empty=$((empty+1)); echo "  EMPTY   pctree evt=$e (group $(basename $g))"; fi
    done < "$g/events.txt"
done
nql=$(ls -d "$A"/ql_evt* 2>/dev/null | wc -l)
npc=$(find "$A"/ql_evt* -maxdepth 1 -name 'pctree-evt*.tar.gz' -size +0 2>/dev/null | wc -l)
echo "$S: groups=$ngrp events_in_groups=$nev ql_evt_dirs=$nql nonempty_pctree=$npc  want=$WANT"
echo "$S: short_groups=$short_grp missing=$miss empty=$empty"
[ "$nev" -eq "$WANT" ] && [ "$nql" -eq "$WANT" ] && [ "$npc" -eq "$WANT" ] \
    && [ "$short_grp" -eq 0 ] && [ "$miss" -eq 0 ] && [ "$empty" -eq 0 ] \
    && { echo "$S: STAGE-A COMPLETE"; exit 0; }
echo "$S: STAGE-A INCOMPLETE"; exit 1
