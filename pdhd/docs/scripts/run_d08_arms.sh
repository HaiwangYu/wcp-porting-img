#!/bin/bash
# doc pdhd/08 -- PDHD retiler-fabrication arms (fork BY DUPLICATION of
# docs/scripts/run_d03_arms.sh; that script is untouched).  One binary per pin,
# fresh tags only (M13).  Every event reads its pctree from
# work/029107_<evt>_<SRC> (default stm0), symlinked into the new tag dir.
#
# There is deliberately NO CFG= option.  run_pr_evt.sh:61 does
#     export WIRECELL_PATH="$WCT_BASE/toolkit/cfg:...:${WIRECELL_PATH}"
# i.e. it PREPENDS the live tree, so an alternative cfg/ tree passed in from
# outside is shadowed and silently ignored (this bit doc pdhd/08 once).  An arm
# here always compiles the working tree's cfg/.  The config side of the
# byte-identity claim is proven separately, by diffing the COMPILED config
# against a pristine `git archive HEAD cfg` tree (doc pdhd/08 sec 5); the arm
# gate is the binary-only half and the two compose.
#
# Usage:
#   ARM=d08goff PIN=/home/xqian/tmp/d08_libpin/new2 [MODE=-stm] [JOBS=10] \
#       [EVENTS="0 6"] [EXTRA="-S retile_hack_max_bridge=20"] [CFG=<cfgdir>] \
#       ./docs/scripts/run_d08_arms.sh
set -u
ARM=${ARM:?ARM=<tag>}
PIN=${PIN:?PIN=<libpin dir>}
MODE=${MODE:--stm}
JOBS=${JOBS:-10}
EXTRA=${EXTRA:-}
EVENTS=${EVENTS:-all}
SRC=${SRC:-stm0}
cd "$(dirname "$0")/../.." || exit 9      # pdhd/
[ -d "$PIN" ] || { echo "no pin $PIN" >&2; exit 2; }
export LD_LIBRARY_PATH=$PIN
WC=/home/xqian/toolkit-dev/local/bin/wire-cell
if ldd $WC | grep -i wirecell | grep -qv "$PIN"; then echo "REFUSING: wire-cell libs not resolved from $PIN" >&2; exit 2; fi
case " $EXTRA" in *"trackfitting_config="|*"trackfitting_config= "*)
    echo "REFUSING $ARM: empty trackfitting_config would drop the PDHD fitting parameters" >&2; exit 2;; esac
for d in work/029107_*_$SRC; do
    e=${d#work/029107_}; e=${e%_$SRC}
    if [ "$EVENTS" != all ]; then case " $EVENTS " in *" $e "*) ;; *) continue ;; esac; fi
    n=work/029107_${e}_$ARM
    if [ -s "$n/mabc-pr.zip" ]; then echo "REFUSING $ARM: $n already has outputs (M13: new run => new tag)" >&2; exit 3; fi
    mkdir -p "$n"; ln -sfn "$PWD/$d"/pctree-evt*.tar.gz "$n/"; ln -sfn "$PWD/$d"/pctree-evt*.tlas "$n/"
done
{
  echo "arm=$ARM pin=$PIN mode=$MODE extra='$EXTRA' events=$EVENTS date=$(date -Is)"
  md5sum "$PIN"/libWireCellClus.so "$PIN"/libWireCellRoot.so
  echo "toolkit=$(git -C /home/xqian/toolkit-dev/toolkit rev-parse --short HEAD) wcp=$(git -C /home/xqian/toolkit-dev/wcp-porting-img rev-parse --short HEAD)"
} > "work/.d08_$ARM.info"
if [ "$EVENTS" = all ]; then
    PDHD_MAX_JOBS=$JOBS PDHD_PR_TLA="$EXTRA" ./run_pr_evt.sh -s "$ARM" $MODE -stm-fit 029107 all
    rc=$?
else
    rc=0
    for e in $EVENTS; do
        PDHD_PR_TLA="$EXTRA" ./run_pr_evt.sh -s "$ARM" $MODE -stm-fit 029107 "$e" || rc=$?
    done
fi
echo "arm=$ARM rc=$rc markers=$(ls work/029107_*_$ARM/pr_resource_029107_*.txt 2>/dev/null | wc -l)" | tee -a "work/.d08_$ARM.info"
echo "$rc" > "work/.d08_$ARM.rc"
exit $rc
