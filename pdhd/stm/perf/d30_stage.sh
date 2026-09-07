#!/usr/bin/env bash
# doc 30: stage one PR tag for one PDHD event by symlinking the source tag's pctree.
# Usage: d30_stage.sh <run6> <idx> <srctag> <newtag>
set -euo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
run6=$1 idx=$2 srctag=$3 newtag=$4
src="$PDHD/work/${run6}_${idx}_${srctag}"
dst="$PDHD/work/${run6}_${idx}_${newtag}"
[ -d "$dst" ] && { echo "REFUSE: $dst exists (M13)"; exit 3; }
ls "$src"/pctree-evt*.tar.gz >/dev/null 2>&1 || { echo "no pctree in $src"; exit 4; }
mkdir -p "$dst"
for f in "$src"/pctree-evt*.tar.gz "$src"/pctree-evt*.tlas; do
    ln -sfn "../${run6}_${idx}_${srctag}/$(basename "$f")" "$dst/$(basename "$f")"
done
echo "staged $dst"
