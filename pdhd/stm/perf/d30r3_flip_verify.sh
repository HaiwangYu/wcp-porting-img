#!/usr/bin/env bash
# doc 30 round 3 flip: run BOTH detectors' busy sets with the PRODUCTION config
# (no TLA -- the knob now lives in cfg/.../_track_fitting.json) so the shipped
# path can be gated against the measured TLA arms.
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
PDVD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd
S=$PDHD/stm/perf/d30_stage.sh
PIN=/home/xqian/tmp/d30_libpin_r3g
OUT=/home/xqian/tmp/d30r3
HTAG=d30r3hon
VTAG=d30r3von
HEV="029107:18:d09ctl2 029107:12:d09ctl2 029107:15:d09ctl2 029107:9:d09ctl2 028084:2:d09 028084:18:d09"
VEV="039252:5 039252:8 039252:15 039253:11 039253:15 039349:6 039349:7"

echo "=== PDHD -stm, production config ==="
for e in $HEV; do IFS=: read -r r i src <<< "$e"
  [ -d "$PDHD/work/${r}_${i}_${HTAG}" ] || $S "$r" "$i" "$src" "$HTAG" >/dev/null
done
( cd "$PDHD" || exit 1
  for e in $HEV; do IFS=: read -r r i src <<< "$e"
    LD_LIBRARY_PATH=$PIN PDHD_MAX_JOBS=1 ./run_pr_evt.sh -s "$HTAG" -stm-fit $((10#$r)) "$i" \
      > "$OUT/flip_${HTAG}_${r}_${i}.log" 2>&1
    echo "  $HTAG $r/$i rc=$?"
  done )

echo "=== PDVD -nu, production config ==="
( cd "$PDVD" || exit 1
  for e in $VEV; do IFS=: read -r r i <<< "$e"
    [ -d "$PDVD/work/${r}_${i}_${VTAG}" ] || ./scripts/stage_pr_tag.sh $((10#$r)) "$i" "$VTAG" d48nu7 >/dev/null
    LD_LIBRARY_PATH=$PIN PDVD_MAX_JOBS=1 ./run_pr_evt.sh -s "$VTAG" -nu -stm-fit $((10#$r)) "$i" \
      > "$OUT/flip_${VTAG}_${r}_${i}.log" 2>&1
    echo "  $VTAG $r/$i rc=$?"
  done )
echo "FLIP VERIFY DONE"
