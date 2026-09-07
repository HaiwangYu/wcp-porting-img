#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 sec 11 -- build the SECOND blind scan set, 12 objects.

READ-ONLY apart from the two files named by --sheet and --key.

Forked by duplication from pr148_pidset.py (M10), which produced the committed
scan0 sheet and stays byte-untouched: its strata, its 24-object size and its
`nseg` column are part of a finished record.

WHY A SECOND SCAN.  Scan 0 (docs/pr/pr148-pidscan-verdicts.tsv) inverted the
round: the suspects came back EM and the defect turned out to be A5 re-typing
real EM cascades.  The guard designed in sec 8 -- decline the re-type when the
shower has more than `shower_hadronic_max_nseg` segments at evaluation time --
rests on FOUR labels.  This sheet measures it properly.

THREE STRATA, and each answers a different question:

  A  all 3 remaining objects ABOVE the bar (census nseg > 10).  With scan 0's
     four, this labels the guard's ENTIRE cut set, so its PRECISION stops
     being an estimate.
  B  all 4 remaining STEM-branch fires.  The stem branch has never been
     tested: it fired 5 times in the population, its single label (98294) came
     back EM, and only that one sits above the bar.  0 of 1 is not a
     measurement.  This makes it 5 of 5.
  C  5 growth-branch fires BELOW the bar, sampled at kine_best QUANTILES
     (min / p25 / median / p75 / max) of the 45 unlabelled.  This measures the
     guard's RECALL -- if these come back HADRONIC the guard is safe, and if
     some come back EM then A5 mis-fires below the bar too and `nseg` is not
     the whole answer.  Quantiles, not top-N: scan 0's S4 was the top six by
     energy out of sixty whose median was 58 MeV, and doc sec 6.1.3 had to
     spend a paragraph discounting its own headline because of it.

  Not covered, and said so rather than quietly dropped: the bragg branch, 2
  fires in the whole population (25.2 and 173.7 MeV).  Two of twelve slots is
  a poor trade against 45 unlabelled growth fires; it stays open.

THE BLIND MOVED, because the proxy moved.  Scan 0 hid growth / bragg / stem /
f_heavy.  Sec 8's discriminant is the SEGMENT COUNT, so this sheet also hides
`nseg` -- and so does the display, which no longer prints "segments drawn".
Printing a count next to a bar of 10 is printing the verdict
(feedback_blind_the_scan_sheet).  Length and energy stay: they are what the
object is, not what the guard thinks of it.

Repro:
  ./pr148_pidset2.py --census ../docs/pr/pr148-a5-census.tsv \
      --labelled ../docs/pr/pr148-pidscan.KEY.tsv \
      --sheet ../docs/pr/pr148-pidscan2-manifest.tsv \
      --key   ../docs/pr/pr148-pidscan2.KEY.tsv
"""
import argparse, csv, json, os, random, sys
from collections import Counter

SEED = 2148          # arbitrary but FIXED, so the row order is reproducible
MAX_NSEG = 10        # the sec 8 bar
DRAWABLE_MIN = 0.90  # sec 6 -- never put a partly-drawable object on a sheet
SHEET_COLS = ["idx", "sample", "run", "subrun", "event", "obj", "shower_id",
              "kine_charge_mev", "kine_best_mev", "total_len_cm",
              "verdict", "weak", "note"]
KEY_COLS = ["idx", "sample", "event", "shower_id", "stratum", "branch",
            "nseg_census", "nseg_final", "growth", "bragg", "stem_mip",
            "kine_dQdx_mev", "nue_score", "enu_mev"]


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
    """Which of A5's three disjuncts fired, at the SBND operating point."""
    g, b, s = F(r, "growth"), F(r, "bragg"), F(r, "stem_mip")
    if g < 0.7: return "growth"
    if b >= 3.0 and g < 1.2: return "bragg"
    if s >= 2.8 and g < 1.2: return "stem"
    return "?"


def drawable_frac(sample, event, shower_id):
    p = os.path.join("work-%s-d145np" % sample, "pr_evt%s" % event,
                     "calib-pr-evt%s.json" % event)
    if not os.path.exists(p):
        return 0.0
    with open(p) as fh:
        d = json.load(fh)
    sh = {s["shower_id"]: s for s in d["showers"]}.get(shower_id)
    if not sh or sh["total_length"] <= 0:
        return 0.0
    have = sum(s["length"] for s in d["segments"] if s.get("shower_id") == sh["id"])
    return have / sh["total_length"]


def runsub(sample, event):
    p = os.path.join("work-%s-d145np" % sample, "pr_evt%s" % event,
                     "calib-pr-evt%s.json" % event)
    if not os.path.exists(p):
        return "", ""
    with open(p) as fh:
        m = json.load(fh).get("meta", {})
    return m.get("runNo", ""), m.get("subRunNo", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True)
    ap.add_argument("--labelled", required=True,
                    help="scan 0's KEY -- its objects are excluded")
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--key", required=True)
    a = ap.parse_args()

    cen = [r for r in rd(a.census) if r["start_seg"] != ""]
    done = {(k["event"], k["shower_id"]) for k in rd(a.labelled)}
    ret = [r for r in cen if r["verdict"] == "1"
           and (r["event"], r["shower_id"]) not in done]

    picked, strata, skipped = [], {}, []

    def take(cands, name, n):
        got = 0
        for r in cands:
            if got >= n:
                break
            k = (r["event"], r["shower_id"])
            if k in strata:
                continue
            f = drawable_frac(r["sample"], r["event"], int(r["shower_id"]))
            if f < DRAWABLE_MIN:
                skipped.append((r["event"], r["shower_id"], round(f, 3)))
                continue
            strata[k] = name
            picked.append(r)
            got += 1
        return got

    by_e = lambda g: sorted(g, key=lambda r: -F(r, "kine_best_mev"))
    above = [r for r in ret if int(r["nseg_census"]) > MAX_NSEG]
    take(by_e(above), "A_above_bar_precision", len(above))

    stem = [r for r in ret if branch(r) == "stem"
            and int(r["nseg_census"]) <= MAX_NSEG]
    take(by_e(stem), "B_stem_branch_untested", len(stem))

    grow = sorted([r for r in ret if branch(r) == "growth"
                   and int(r["nseg_census"]) <= MAX_NSEG],
                  key=lambda r: F(r, "kine_best_mev"))
    n = len(grow)
    qidx = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})
    take([grow[i] for i in qidx], "C_below_bar_recall", len(qidx))

    random.Random(SEED).shuffle(picked)

    with open(a.sheet, "w") as sh, open(a.key, "w") as kf:
        sh.write("# doc pr/148 sec 11 -- BLIND scan 2, 12 objects.  Every one of\n"
                 "# these is an object the reconstruction ALREADY re-typed from\n"
                 "# electron to pion; the question is whether it was right to.\n"
                 "#\n"
                 "# Withheld, because printing the proxy's answer on the sheet you\n"
                 "# then judge makes the agreement circular: the A5 discriminants\n"
                 "# (growth, bragg, stem), which branch fired, the nue BDT score,\n"
                 "# the stratum -- and NEW this round, the SEGMENT COUNT, which is\n"
                 "# what sec 8's proposed guard keys on.  They are all in\n"
                 "# pr148-pidscan2.KEY.tsv, which the display never opens.\n"
                 "#\n"
                 "# verdict: EM | HADRONIC | MIXED      weak: 1 if not confident\n"
                 "#   EM       -- an electron or photon shower.  The re-type was\n"
                 "#               WRONG and production is mis-valuing this object.\n"
                 "#   HADRONIC -- a pion/proton/neutron interaction.  The re-type\n"
                 "#               was right.\n"
                 "#   MIXED    -- both, clustered into one object.\n"
                 "#\n"
                 "# The display fills this in for you:\n"
                 "#   ./pr148_scan/serve_pr148_scan.sh 5017 --scan-tag scan1 \\\n"
                 "#       --sheet docs/pr/pr148-pidscan2-manifest.tsv\n")
        sh.write("\t".join(SHEET_COLS) + "\n")
        kf.write("# doc pr/148 sec 11 -- the KEY for pr148-pidscan2-manifest.tsv.\n"
                 "# The display and its self-test never open this file.\n")
        kf.write("\t".join(KEY_COLS) + "\n")
        for i, r in enumerate(picked):
            run, sub = runsub(r["sample"], r["event"])
            sh.write("\t".join(str(x) for x in [
                i, r["sample"], run, sub, r["event"], r["start_seg"],
                r["shower_id"], r["kine_charge_mev"], r["kine_best_mev"],
                r["total_len_cm"], "", "", ""]) + "\n")
            kf.write("\t".join(str(x) for x in [
                i, r["sample"], r["event"], r["shower_id"],
                strata[(r["event"], r["shower_id"])], branch(r),
                r["nseg_census"], r["nseg_final"], r["growth"], r["bragg"],
                r["stem_mip"], r["kine_dQdx_mev"], r["nue_score"],
                r["enu_mev"]]) + "\n")

    print("picked %d object(s): %s" % (len(picked), dict(Counter(strata.values()))))
    if skipped:
        print("skipped, not fully drawable: %s" % skipped)
    print("wrote %s and %s" % (a.sheet, a.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
