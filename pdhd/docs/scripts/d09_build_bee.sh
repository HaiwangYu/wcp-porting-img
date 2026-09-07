#!/usr/bin/env bash
# doc pdhd/09 Phase 6 -- build the owner's Bee spot-check set for contested TGM verdicts.
#
# Recipe from doc pdvd/41 sec 12.1, which is worth following exactly: each index is the
# full clustering-global layer PLUS a `target-global` layer containing ONLY the cluster to
# scan, with the same schema.  Building the one-object layer costs nothing and saves the
# scanner from hunting the track in a cosmic-dense event -- do this for every scan set.
#
# This script only ASSEMBLES data/ and zips it.  It deliberately does NOT upload:
# upload-to-bee.sh is outward-facing and needs the owner's explicit go-ahead.
set -uo pipefail
PDHD=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
SHEET=${1:?usage: d09_build_bee.sh <panels/sheet.json> [arm] [outzip]}
ARM=${2:-d09fvoff}
OUT=${3:-$PDHD/bee-pr-d09-scan.zip}
STAGE=$(mktemp -d /home/xqian/tmp/d09bee.XXXXXX)
mkdir -p "$STAGE/data"

python3 - "$SHEET" "$ARM" "$STAGE" <<'PY'
import json, os, sys, zipfile
import numpy as np
sys.path.insert(0, "/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd/docs/scripts")
from d09_fv_pdhd import bee_points

sheet, arm, stage = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
P = "/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd/work"
idxmap = []
for i, row in enumerate(sheet):
    wd = os.path.join(P, f"{row['run']}_{row['idx']}_{arm}")
    z = zipfile.ZipFile(os.path.join(wd, "mabc-pr.zip"))
    d = os.path.join(stage, "data", str(i)); os.makedirs(d, exist_ok=True)
    # copy every layer of the event through unchanged
    for n in z.namelist():
        base = os.path.basename(n)
        if not base.endswith(".json"):
            continue
        tail = base.split("-", 1)[1] if "-" in base else base
        open(os.path.join(d, f"{i}-{tail}"), "wb").write(z.read(n))
    # add the one-cluster target layer, same schema as clustering-global
    P3, Q, C, run, evt = bee_points(wd)
    m = (C == row["cid"])
    tgt = dict(runNo=str(run), subRunNo="0", eventNo=str(evt), geom="protodunehd",
               type="target", x=[round(float(v), 2) for v in P3[m, 0]],
               y=[round(float(v), 2) for v in P3[m, 1]],
               z=[round(float(v), 2) for v in P3[m, 2]],
               q=[round(float(v), 2) for v in Q[m]],
               cluster_id=[int(row["cid"])]*int(m.sum()),
               real_cluster_id=[int(row["cid"])]*int(m.sum()))
    json.dump(tgt, open(os.path.join(d, f"{i}-target-global.json"), "w"))
    idxmap.append(f"{i}\t{row['run']}/{row['idx']}\tcluster {row['cid']}\t"
                  f"{row['len_cm']:.0f} cm\t{row['half']} half\t{int(m.sum())} pts")
    print(f"  [{i}] {row['run']}/{row['idx']} cluster {row['cid']}: {int(m.sum())} points in target layer")
open(os.path.join(stage, "INDEX.tsv"), "w").write("\n".join(idxmap) + "\n")
PY

( cd "$STAGE" && zip -qr "$OUT" data ) && cp "$STAGE/INDEX.tsv" "${OUT%.zip}.index.tsv"
echo "built $OUT  ($(du -h "$OUT" | cut -f1))  index: ${OUT%.zip}.index.tsv"
echo "NOT uploaded -- upload-to-bee.sh is outward-facing and needs the owner's go-ahead."
