#!/usr/bin/env bash
# doc 30 round 3: extend two existing scan tags to the full PDHD busy set of 6.
# Usage: busy6.sh <padtag> <padfile>     (the OFF tag d30r3off is always extended)
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
S=$PDHD/stm/perf/d30_stage.sh
PIN=/home/xqian/tmp/d30_libpin_r3
OUT=/home/xqian/tmp/d30r3
PADTAG=$1; PADFILE=$2
REST="029107:12:d09ctl2 029107:15:d09ctl2 029107:9:d09ctl2 028084:18:d09"

run_arm () {   # $1 tag, $2 TLA
  local tag=$1 tla=$2
  for e in $REST; do
    IFS=: read -r r i src <<< "$e"
    [ -d "$PDHD/work/${r}_${i}_${tag}" ] || $S "$r" "$i" "$src" "$tag" >/dev/null
  done
  ( cd "$PDHD" || exit 1
    for e in $REST; do
      IFS=: read -r r i src <<< "$e"
      LD_LIBRARY_PATH=$PIN PDHD_MAX_JOBS=1 WCT_D30_FILL_CENSUS=1 \
        PDHD_PR_TLA="$tla" ./run_pr_evt.sh -s "$tag" -stm-fit $((10#$r)) "$i" \
        > "$OUT/busy_${tag}_${r}_${i}.log" 2>&1
      echo "  $tag $r/$i rc=$?"
    done )
}
echo "=== OFF, remaining 4 ==="
run_arm d30r3off ""
echo "=== $PADTAG, remaining 4 ==="
run_arm "$PADTAG" "-A trackfitting_config=$PADFILE"
echo "BUSY6 DONE"
