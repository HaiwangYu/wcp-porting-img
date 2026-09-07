#!/bin/bash
# doc pdhd/08 sec 9.1 follow-up: the PDVD 30-event grade the flip shipped without.
# ARM=<tag> TLA="<extra wcsonnet args>" JOBS=n bash run_pdvd30.sh
# Writes .d08_<ARM>.rc.<evt> markers -- gate on those, never on a file's existence.
set -u
PDVD=/home/xqian/toolkit-dev/wcp-porting-img/pdvd
RUN=039349
ARM=${ARM:?}
JOBS=${JOBS:-12}
TLA=${TLA:-}
cd "$PDVD" || exit 2
mkdir -p "$PDVD/.d08marks"

one() {
    e=$1
    src=$(ls "$PDVD"/work/${RUN}_${e}_*/pctree-evt*.tar.gz 2>/dev/null | grep -v "_${ARM}/" | head -1)
    [ -n "$src" ] || { echo "evt $e: NO INPUT" >&2; echo 90 > "$PDVD/.d08marks/${ARM}.$e"; return; }
    src=$(readlink -f "$src")
    d="$PDVD/work/${RUN}_${e}_${ARM}"
    mkdir -p "$d"
    ln -sf "$src" "$d/"
    ln -sf "${src%.tar.gz}.tlas" "$d/"
    PDVD_PR_TLA="$TLA" ./run_pr_evt.sh -s "$ARM" "$RUN" "$e" > "$d/run.log" 2>&1
    rc=$?
    echo "$rc" > "$PDVD/.d08marks/${ARM}.$e"
    echo "evt $e rc=$rc"
}
export -f one
export PDVD RUN ARM TLA

seq 0 29 | xargs -P "$JOBS" -I{} bash -c 'one {}'
echo "=== ${ARM}: $(grep -l . "$PDVD"/.d08marks/${ARM}.* 2>/dev/null | wc -l) markers, non-zero: $(cat "$PDVD"/.d08marks/${ARM}.* 2>/dev/null | grep -vc '^0$')"
