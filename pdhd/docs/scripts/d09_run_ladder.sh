#!/usr/bin/env bash
# doc pdhd/09 Phase 6 -- the five-arm ladder, one pinned binary, 61 events each.
#
# PDVD's p90+5 is NOT inherited as the answer.  Its ladder graded against a baseline
# that already carried a 17.5/18 cm shell and scored 7.5 % per-end miss; PDHD's flat
# baseline is the same construction but a different detector, so the winning operating
# point has to come from PDHD's own numbers.  The owner picks from the graded table.
#
# Arm switches (the PDHD counterpart of doc pdvd/43 sec 8's table):
#   flat / production   (no TLA)
#   p80 + 3             -S curved_fv=true -A curved_fv_profile=p80
#   p80 + 5             ... -S curved_fv_margin_y=5 -S curved_fv_margin_z=5
#   p90 + 3             -S curved_fv=true -A curved_fv_profile=p90
#   p90 + 5             ... -S curved_fv_margin_y=5 -S curved_fv_margin_z=5
set -uo pipefail
S=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd/docs/scripts
C5="-S curved_fv_margin_y=5 -S curved_fv_margin_z=5"
run_arm() { echo "=========== $1 ==========="; ARM=$1 PR_TLA="$2" JOBS=${JOBS:-6} "$S/d09_run_pr_arm.sh"; }

run_arm d09fvoff ""
run_arm d09p80c3 "-S curved_fv=true -A curved_fv_profile=p80"
run_arm d09p80c5 "-S curved_fv=true -A curved_fv_profile=p80 $C5"
run_arm d09p90c3 "-S curved_fv=true -A curved_fv_profile=p90"
run_arm d09p90c5 "-S curved_fv=true -A curved_fv_profile=p90 $C5"
echo "[ladder] all arms done"
