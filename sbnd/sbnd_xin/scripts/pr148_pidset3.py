#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 sec 14 -- the RESCAN sheet: both scans' objects, redone
with the 3-D image overlaid.

READ-ONLY apart from --sheet and --key.

Owner, 2026-09-06: *"I would like to rescan these events, in addition to the
best-fit trajectory can you also overlay the 3D image on them?"*

The first two scans drew only FIT points -- the reconstruction's trajectory
samples.  EM-vs-hadronic is a judgement about CHARGE (a cone that opens, or a
track that ends in a star), so the scanner was being asked the right question
with the wrong picture.  The display now overlays the imaged charge from
mabc-pr.zip; this sheet puts all 36 previously-labelled objects back in front
of it.

WHAT MAKES THE RESCAN WORTH ANYTHING: it must be blind to the first pass.
The previous verdict is in the KEY, never on the sheet, and the row order is
RESHUFFLED under a different seed, so position carries no memory of scan 0 or
scan 2 either.  Comparing the two passes is then a real measurement -- of the
labels' stability, and of how much the image changed the answer.

Everything the earlier sheets withheld stays withheld: the A5 discriminants,
which branch fired, the nue BDT score, the stratum, and the segment count.

Repro:
  ./pr148_pidset3.py --sheet ../docs/pr/pr148-pidscan3-manifest.tsv \
      --key ../docs/pr/pr148-pidscan3.KEY.tsv
"""
import argparse, csv, os, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)
SEED = 3148                     # different from scan 0 (147) and scan 2 (2148)
SHEET_COLS = ["idx", "sample", "run", "subrun", "event", "obj", "shower_id",
              "kine_charge_mev", "kine_best_mev", "total_len_cm",
              "verdict", "weak", "note"]
KEY_COLS = ["idx", "sample", "event", "shower_id", "prev_scan", "prev_verdict",
            "prev_stratum", "a5_retyped", "branch", "nseg_census", "growth",
            "bragg", "stem_mip", "nue_score"]
PRIOR = [("scan0", "pr148-pidscan.KEY.tsv", "pr148-pidscan-verdicts.tsv"),
         ("scan2", "pr148-pidscan2.KEY.tsv", "pr148-pidscan2-verdicts.tsv")]


def rd(p):
    with open(p) as fh:
        return list(csv.DictReader((l for l in fh if not l.startswith("#")),
                                   delimiter="\t"))


def F(r, k, d=0.0):
    try:
        return float(r[k])
    except (TypeError, ValueError, KeyError):
        return d


def branch(r):
    g, b, s = F(r, "growth"), F(r, "bragg"), F(r, "stem_mip")
    if g < 0.7: return "growth"
    if b >= 3.0 and g < 1.2: return "bragg"
    if s >= 2.8 and g < 1.2: return "stem"
    return "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default=os.path.join(SX, "docs/pr/pr148-a5-census.tsv"))
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--key", required=True)
    a = ap.parse_args()

    cen = {(r["event"], r["shower_id"]): r
           for r in rd(a.census) if r["start_seg"] != ""}
    items = []
    for tag, kf, lf in PRIOR:
        key = {r["idx"]: r for r in rd(os.path.join(SX, "docs/pr", kf))}
        lab = {r["idx"]: r for r in rd(os.path.join(SX, "docs/pr", lf))}
        for i, k in key.items():
            items.append(dict(tag=tag, k=k, v=lab.get(i, {}).get("verdict", "")))

    random.Random(SEED).shuffle(items)
    with open(a.sheet, "w") as sh, open(a.key, "w") as kf:
        sh.write("# doc pr/148 sec 14 -- RESCAN, %d objects, now with the 3-D\n"
                 "# imaged charge overlaid on the best-fit trajectory.\n"
                 "#\n"
                 "# These are the same objects you labelled on 2026-09-06, in a\n"
                 "# DIFFERENT order, and your earlier verdict is deliberately not\n"
                 "# on this sheet: a rescan that shows you your own previous\n"
                 "# answer measures nothing.  Judge each one fresh.\n"
                 "#\n"
                 "# Still withheld, as before: the A5 discriminants (growth,\n"
                 "# bragg, stem), which branch fired, the nue BDT score, the\n"
                 "# stratum, and the segment count.\n"
                 "#\n"
                 "# verdict: EM | HADRONIC | MIXED      weak: 1 if not confident\n"
                 "#   EM       -- an electron or photon shower\n"
                 "#   HADRONIC -- a pion/proton/neutron interaction\n"
                 "#   MIXED    -- both, clustered into one object\n"
                 "#\n"
                 "# The display fills this in for you:\n"
                 "#   ./pr148_scan/serve_pr148_scan.sh 5017 --scan-tag scan2 \\\n"
                 "#       --sheet docs/pr/pr148-pidscan3-manifest.tsv\n" % len(items))
        sh.write("\t".join(SHEET_COLS) + "\n")
        kf.write("# doc pr/148 sec 14 -- the KEY for pr148-pidscan3-manifest.tsv,\n"
                 "# carrying each object's FIRST-PASS verdict so the two passes can\n"
                 "# be compared.  The display and its self-test never open it.\n")
        kf.write("\t".join(KEY_COLS) + "\n")
        for i, it in enumerate(items):
            k = it["k"]
            c = cen[(k["event"], k["shower_id"])]
            sh.write("\t".join(str(x) for x in [
                i, c["sample"], "", "", k["event"], c["start_seg"],
                k["shower_id"], c["kine_charge_mev"], c["kine_best_mev"],
                c["total_len_cm"], "", "", ""]) + "\n")
            kf.write("\t".join(str(x) for x in [
                i, c["sample"], k["event"], k["shower_id"], it["tag"], it["v"],
                k.get("stratum", ""), c["verdict"], branch(c),
                c["nseg_census"], c["growth"], c["bragg"], c["stem_mip"],
                c["nue_score"]]) + "\n")

    print("rescan sheet: %d object(s)  %s" % (len(items),
          dict(Counter(i["tag"] for i in items))))
    print("  of which A5 re-typed: %d" % sum(
        1 for i in items if cen[(i["k"]["event"], i["k"]["shower_id"])]["verdict"] == "1"))
    print("  first-pass verdicts: %s" % dict(Counter(i["v"] for i in items)))
    print("wrote %s and %s" % (a.sheet, a.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
