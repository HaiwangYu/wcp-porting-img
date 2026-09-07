#!/usr/bin/env bash
# doc 30 round 3: pad scan on the two census events.  Sequential, JOBS=1.
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
S=$PDHD/stm/perf/d30_stage.sh
PIN=/home/xqian/tmp/d30_libpin_r3
OUT=/home/xqian/tmp/d30r3
EVENTS="029107:18:d09ctl2 028084:2:d09"

run_arm () {   # $1 tag, $2 TLA (may be empty)
  local tag=$1 tla=$2
  for e in $EVENTS; do
    IFS=: read -r r i src <<< "$e"
    [ -d "$PDHD/work/${r}_${i}_${tag}" ] || $S "$r" "$i" "$src" "$tag" >/dev/null
  done
  ( cd "$PDHD" || exit 1
    for e in $EVENTS; do
      IFS=: read -r r i src <<< "$e"
      LD_LIBRARY_PATH=$PIN PDHD_MAX_JOBS=1 WCT_D30_FILL_CENSUS=1 \
        PDHD_PR_TLA="$tla" ./run_pr_evt.sh -s "$tag" -stm-fit $((10#$r)) "$i" \
        > "$OUT/scan_${tag}_${r}_${i}.log" 2>&1
      echo "  $tag $r/$i rc=$?"
    done )
}

echo "=== OFF (knob absent, production JSON) ==="
run_arm d30r3off ""
for p in 0 1 2 3 5; do
  echo "=== pad $p ==="
  run_arm "d30r3p${p}" "-A trackfitting_config=/home/xqian/tmp/d30r3/pdhd_tf_pad${p}.json"
done
echo "SCAN DONE"
