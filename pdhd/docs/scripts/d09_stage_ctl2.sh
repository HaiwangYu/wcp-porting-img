#!/usr/bin/env bash
# doc pdhd/09 Phase 2 -- the DEFINITIVE 029107 control: every stage under the pin.
#
# Three arms, each removing one epoch difference, so any residual is attributable:
#   d09ref   June-2026 imaging + July-2026 light + pinned Q/L
#   d09ctl   PINNED imaging    + July-2026 light + pinned Q/L   (isolates imaging drift)
#   d09ctl2  PINNED imaging    + PINNED light    + pinned Q/L   (isolates light drift)
# d09ctl2 vs the 028084 _d09 arm is then run-only.
#
# Imaging is symlinked from d09ctl rather than re-run: same pin, so the product is
# identical and re-running would only burn CPU.
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
RUN=29107; RUN6=029107; TAG=d09ctl2; SRC=d09ctl
PIN=${PIN:-/home/xqian/tmp/d09_libpin/pin}
JOBS=${JOBS:-6}
LOGD=/home/xqian/tmp/d09/ctl2logs; mkdir -p "$LOGD"
[ -d "$PIN" ] && export LD_LIBRARY_PATH="$PIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

one() {
    local idx=$1
    local ident=$((983 + 8*idx))
    local src="$PDHD/work/${RUN6}_${idx}_${SRC}"
    local dst="$PDHD/work/${RUN6}_${idx}_${TAG}"
    local lig="$PDHD/work/${RUN6}_allpd${ident}_d09/opflash_pdhd-allpd-wct.tar.gz"
    local log="$LOGD/evt${idx}.log"
    ls "$src"/clusters-apa-apa*-ms-active.tar.gz >/dev/null 2>&1 || { echo "[$TAG] idx=$idx NO CLUSTERS"; return; }
    [ -f "$lig" ] || { echo "[$TAG] idx=$idx NO PINNED LIGHT"; return; }
    mkdir -p "$dst"
    (
      cd "$PDHD" || exit 1
      for f in "$src"/clusters-apa-apa*-ms-*.tar.gz; do
          ln -sfn "../${RUN6}_${idx}_${SRC}/$(basename "$f")" "$dst/$(basename "$f")"
      done
      ln -sfn "../${RUN6}_allpd${ident}_d09/opflash_pdhd-allpd-wct.tar.gz" "$dst/opflash_pdhd-wct.tar.gz"
      ./run_clus_evt.sh -s "$TAG" -calib -save-pctree -save-assoc $RUN "$idx" || exit 14
      touch "$dst/.d09-ctl2-done"
    ) > "$log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ] && [ -f "$dst/.d09-ctl2-done" ]; then echo "[$TAG] idx=$idx OK"
    else echo "[$TAG] idx=$idx FAILED rc=$rc -- $log"; fi
}
n=0
for idx in $(seq 0 29); do one "$idx" & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait; done
wait
echo "[$TAG] done"
