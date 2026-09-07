#!/usr/bin/env bash
# doc 30 round 3: PDVD -nu busy-set scan (the -nu path also exercises the MAP
# flavour of fill_fitted_charge_2d, via do_multi_tracking).  Sequential, JOBS=1.
PDVD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd
PIN=/home/xqian/tmp/d30_libpin_r3
OUT=/home/xqian/tmp/d30r3
SRC=d48nu7
EVENTS="039252:5 039252:8 039252:15 039253:11 039253:15 039349:6 039349:7"

run_arm () {   # $1 tag, $2 TLA
  local tag=$1 tla=$2
  ( cd "$PDVD" || exit 1
    for e in $EVENTS; do
      IFS=: read -r r i <<< "$e"
      [ -d "$PDVD/work/${r}_${i}_${tag}" ] || ./scripts/stage_pr_tag.sh $((10#$r)) "$i" "$tag" "$SRC" >/dev/null
      LD_LIBRARY_PATH=$PIN PDVD_MAX_JOBS=1 WCT_D30_FILL_CENSUS=1 \
        PDVD_PR_TLA="$tla" ./run_pr_evt.sh -s "$tag" -nu -stm-fit $((10#$r)) "$i" \
        > "$OUT/pdvd_${tag}_${r}_${i}.log" 2>&1
      echo "  $tag $r/$i rc=$?"
    done )
}

echo "=== PDVD OFF ==="
run_arm d30r3voff ""
for p in 0 3; do
  echo "=== PDVD pad $p ==="
  run_arm "d30r3vp${p}" "-A trackfitting_config=/home/xqian/tmp/d30r3/pdvd_tf_pad${p}.json"
done
echo "PDVD SCAN DONE"
