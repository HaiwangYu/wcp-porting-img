#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 -- score the blind EM/HADRONIC scan, and price the guard.

READ-ONLY.  Prints; writes nothing.

Joins the owner's verdicts (the display's filled_sheet.tsv, or the committed
copy docs/pr/pr148-pidscan-verdicts.tsv) to the sheet's KEY and to the A5
census, and reproduces every table in doc pr/148 sec 6.1 and sec 8.

The guard being priced is sec 8: A5 declines to re-type a shower whose
segment count AT EVALUATION TIME exceeds --max-nseg.  Evaluation time, not
final: A5 runs mid-pipeline, and one labelled HADRONIC object (98844) was 26
segments when A5 judged it and 9 by the end.

dEnu per spared object = (kine_charge - kine_best_now) - 139.57, i.e. the
object reverts from the hadronic dQ/dx estimate to its EM charge estimate and
gives back the pion rest term that kine_mass_rules adds for pdg 211.  The
first half is an ASSUMPTION -- that a spared object's kine_best reverts to its
kine_charge -- and the script prints how well it holds over the census.

Repro:
  ./pr148_score_scan.py
  ./pr148_score_scan.py --labels ../work/pr148_scan_labels/scan1/filled_sheet.tsv
"""
import argparse, csv, os, statistics as st, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)
PI_MASS = 139.57


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
    """Which of A5's three disjuncts fired (NeutrinoShowerClustering.cxx:9942),
    at the SBND operating point growth_max 0.7 / bragg 3.0 / stem 2.8."""
    g, b, s = F(r, "growth"), F(r, "bragg"), F(r, "stem_mip")
    if g < 0.7: return "growth"
    if b >= 3.0 and g < 1.2: return "bragg"
    if s >= 2.8 and g < 1.2: return "stem"
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default=os.path.join(SX, "docs/pr/pr148-a5-census.tsv"))
    ap.add_argument("--key", default=os.path.join(SX, "docs/pr/pr148-pidscan.KEY.tsv"))
    ap.add_argument("--labels", default=os.path.join(SX, "docs/pr/pr148-pidscan-verdicts.tsv"))
    ap.add_argument("--max-nseg", type=int, default=10)
    a = ap.parse_args()

    cen = [r for r in rd(a.census) if r["start_seg"] != ""]
    by = {(r["event"], r["shower_id"]): r for r in cen}
    key = {r["idx"]: r for r in rd(a.key)}
    lab = {r["idx"]: r for r in rd(a.labels)}
    verdict_of = {(key[i]["event"], key[i]["shower_id"]): lab[i]["verdict"]
                  for i in lab if lab[i].get("verdict")}

    print("=== sec 6.1  verdicts by stratum ===")
    tab = defaultdict(Counter)
    for i in lab:
        tab[key[i]["stratum"]][lab[i]["verdict"] or "(blank)"] += 1
    for s in sorted(tab):
        c = tab[s]
        print("  %-28s EM %d  MIXED %d  HADRONIC %d"
              % (s, c["EM"], c["MIXED"], c["HADRONIC"]))
    tot = Counter(l["verdict"] for l in lab.values())
    print("  %-28s EM %d  MIXED %d  HADRONIC %d   (weak: %d, notes: %d)"
          % ("TOTAL", tot["EM"], tot["MIXED"], tot["HADRONIC"],
             sum(1 for l in lab.values() if l.get("weak")),
             sum(1 for l in lab.values() if l.get("note"))))

    print("\n=== sec 6.1  segment count vs verdict (FINAL nseg; clean, but not readable at the seat) ===")
    for v in ("HADRONIC", "MIXED", "EM"):
        n = sorted(int(by[k]["nseg_final"]) for k, vv in verdict_of.items() if vv == v)
        print("  %-9s %s" % (v, n))
    had = [int(by[k]["nseg_final"]) for k, v in verdict_of.items() if v == "HADRONIC"]
    oth = [int(by[k]["nseg_final"]) for k, v in verdict_of.items() if v != "HADRONIC"]
    print("  empty bins between: %s" % list(range(max(had) + 1, min(oth))))
    print("  ... and on the CENSUS-time nseg A5 can actually read:")
    for v in ("HADRONIC", "MIXED", "EM"):
        n = sorted(int(by[k]["nseg_census"]) for k, vv in verdict_of.items() if vv == v)
        print("  %-9s %s" % (v, n))

    ret = [r for r in cen if r["verdict"] == "1"]
    print("\n=== sec 8.1  the label-free argument: census-nseg histogram of the %d joined re-types ==="
          % len(ret))
    h = Counter(int(r["nseg_census"]) for r in ret)
    lo, hi = min(h), max(h)
    print("  nseg: " + " ".join("%3d" % n for n in range(lo, hi + 1)))
    print("     n: " + " ".join(("%3d" % h[n]) if h[n] else "  ." for n in range(lo, hi + 1)))
    print("  by branch: %s" % dict(Counter(branch(r) for r in ret)))

    print("\n=== sec 8.2  what a guard at nseg > %d declines ===" % a.max_nseg)
    sp = sorted([r for r in ret if int(r["nseg_census"]) > a.max_nseg],
                key=lambda r: -F(r, "kine_charge_mev"))
    print("  %7s %3s %5s %5s %7s %8s %8s %9s %9s" % (
        "evt", "sh", "nsegC", "nsegF", "branch", "best_now", "charge", "dEnu", "label"))
    tot_d = 0.0
    for r in sp:
        d = (F(r, "kine_charge_mev") - F(r, "kine_best_mev")) - PI_MASS
        tot_d += d
        print("  %7s %3s %5s %5s %7s %8.1f %8.1f %+9.1f %9s" % (
            r["event"], r["shower_id"], r["nseg_census"], r["nseg_final"], branch(r),
            F(r, "kine_best_mev"), F(r, "kine_charge_mev"), d,
            verdict_of.get((r["event"], r["shower_id"]), "-")))
    labelled = [r for r in sp if (r["event"], r["shower_id"]) in verdict_of]
    em = [r for r in labelled if verdict_of[(r["event"], r["shower_id"])] == "EM"]
    print("  TOTAL dEnu %+.1f MeV over %d object(s) in %d event(s)"
          % (tot_d, len(sp), len({(r["sample"], r["event"]) for r in sp})))
    print("  labelled: %d of %d; of those, EM (wrongly re-typed) %d"
          % (len(labelled), len(sp), len(em)))

    notret = [r for r in cen if r["verdict"] == "0"]
    same = [r for r in notret
            if abs(F(r, "kine_best_mev") - F(r, "kine_charge_mev")) < 0.01]
    diff = sorted(abs(F(r, "kine_best_mev") - F(r, "kine_charge_mev"))
                  for r in notret if r not in same)
    print("\n=== sec 8.2  how good is the counterfactual (kine_best reverts to kine_charge)? ===")
    print("  holds exactly for %d of %d EM-typed showers (%.0f%%); "
          "the other %d differ by a median %.1f MeV, max %.1f"
          % (len(same), len(notret), 100 * len(same) / len(notret), len(diff),
             diff[len(diff) // 2], diff[-1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
