#!/usr/bin/env python3
"""doc pdhd/12 -- score the STM + Michel hand-scan labels against the chain.

Run:  ./score_stm_michel_scan.py --det pdhd [--tag smx1]

This script reads the ANSWER KEY.  stm_michel_viewer.py never does.

THE BAR, fixed here BEFORE any label exists so it cannot be fitted afterwards,
and the owner's to overrule.  Two numbers decide whether the chain's
"stopping muon WITH a Michel" flag is usable as a sample definition:

  purity     of the objects the chain calls STM + Michel, the fraction the
             scanner also calls STM + MICHEL.
  efficiency of the objects the scanner calls STM + MICHEL, the fraction the
             chain also flags.

The scan is stratified, so BOTH have to be re-weighted back to the parent
population before they mean anything: tranche 1 takes every reco-positive item
it can and only a floor from the other three strata, so a raw purity computed
over the labelled set would be a purity of the SHEET, not of the detector.  The
re-weighting is per stratum, n_parent / n_labelled, and it is printed alongside
the raw numbers so the two can never be confused.

MESSY and UNCLEAR are UNSCORED, and their rate is reported per stratum rather
than folded into a class -- an unjudgeable rate that climbs with stratum is a
statement about the sample, not about the chain
(feedback_fragment_label_carries_object_verdict item 2).

A FRAG label scores exactly as its plain counterpart: `label` already carries
the FULL object's verdict, and `partial` is tallied separately as the
under-clustering rate.

REVEALED LABELS ARE SCORED SEPARATELY, never merged.  A label taken with the
reconstruction on screen cannot measure agreement with the reconstruction.
"""
import argparse, collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.dirname(os.path.dirname(HERE))

# The whitelist.  A bare `else` folding an unrecognised label into a class is
# exactly the silent failure this table exists to prevent -- so an unknown label
# is a hard error, not a default.
TRUTH = {
    "STM_MICHEL": dict(stm=True, michel=True),
    "STM_ONLY":   dict(stm=True, michel=False),
    "THRU":       dict(stm=False, michel=False),
    "MESSY":      None,          # ill-posed for the object
    "UNCLEAR":    None,          # the scanner's confidence
}


def read_tsv(path):
    with open(path) as fh:
        lines = [l for l in fh if not l.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=["pdhd", "pdvd"])
    ap.add_argument("--tag", default="smx1")
    ap.add_argument("--key", default=None)
    ap.add_argument("--labels", default=None)
    a = ap.parse_args()
    root = os.path.join(IMG, a.det)
    keyf = a.key or os.path.join(root, "docs", "scan",
                                 "%s_stm_michel_scan_key.tsv" % a.det)
    labf = a.labels or os.path.join(root, "work", "stm_michel_labels", a.tag,
                                    "labels.json")
    if not os.path.exists(labf):
        raise SystemExit("no labels at %s" % labf)
    KEY = {(r["event"], int(r["cluster"])): r for r in read_tsv(keyf)}
    with open(labf) as fh:
        LAB = json.load(fh)["labels"]

    parent = collections.Counter(r["stratum"] for r in KEY.values())
    got = collections.Counter()
    unscored = collections.Counter()
    cells = collections.Counter()          # (stratum, revealed, human, chain)
    partial = collections.Counter()
    moved = []

    for k, rec in LAB.items():
        ev, cl = k.split("/")
        kk = (ev, int(cl))
        if kk not in KEY:
            raise SystemExit("label %s is not in the key -- wrong sheet or wrong tag" % k)
        lbl = rec["label"]
        if lbl not in TRUTH:
            raise SystemExit("unknown label %r on %s: refusing to guess a class" % (lbl, k))
        s = KEY[kk]["stratum"]
        got[s] += 1
        if TRUTH[lbl] is None:
            unscored[s] += 1
            continue
        rev = bool(rec.get("revealed_before_label"))
        chain = (int(KEY[kk]["is_stm"]), int(KEY[kk]["michel_found"]))
        human = (TRUTH[lbl]["stm"], TRUTH[lbl]["michel"])
        cells[(s, rev, human, chain)] += 1
        if rec.get("partial"):
            partial[s] += 1
        p = rec.get("pin") or {}
        if p.get("placed") and p.get("moved_cm") is not None:
            moved.append(p["moved_cm"])

    print("=== %s, tag %s: %d labels over %d key rows" % (a.det, a.tag, len(LAB), len(KEY)))
    print("\nstratum  parent  labelled  unscored(MESSY+UNCLEAR)  weight")
    for s in sorted(parent):
        w = parent[s] / got[s] if got[s] else float("nan")
        print("  %-4s   %5d   %6d   %6d (%5.1f %%)          %6.2f"
              % (s, parent[s], got[s], unscored[s],
                 100.0 * unscored[s] / max(got[s], 1), w))

    for rev in (False, True):
        sub = {k: v for k, v in cells.items() if k[1] is rev}
        n = sum(sub.values())
        if not n:
            continue
        print("\n--- labels taken with the reconstruction %s (%d scored) ---"
              % ("REVEALED" if rev else "hidden", n))
        # re-weight each stratum back to the parent population
        def w(s):
            return parent[s] / got[s] if got[s] else 0.0
        tp = sum(v * w(k[0]) for k, v in sub.items() if k[2] == (True, True) and k[3] == (1, 1))
        chain_pos = sum(v * w(k[0]) for k, v in sub.items() if k[3] == (1, 1))
        human_pos = sum(v * w(k[0]) for k, v in sub.items() if k[2] == (True, True))
        rtp = sum(v for k, v in sub.items() if k[2] == (True, True) and k[3] == (1, 1))
        rcp = sum(v for k, v in sub.items() if k[3] == (1, 1))
        rhp = sum(v for k, v in sub.items() if k[2] == (True, True))
        print("  STM + Michel   purity     raw %3d/%-3d = %s   reweighted = %s"
              % (rtp, rcp, "%.3f" % (rtp / rcp) if rcp else "  -  ",
                 "%.3f" % (tp / chain_pos) if chain_pos else "  -  "))
        print("  STM + Michel   efficiency raw %3d/%-3d = %s   reweighted = %s"
              % (rtp, rhp, "%.3f" % (rtp / rhp) if rhp else "  -  ",
                 "%.3f" % (tp / human_pos) if human_pos else "  -  "))
        # the stopping-muon flag on its own, Michel ignored
        stp = sum(v for k, v in sub.items() if k[2][0] and k[3][0])
        scp = sum(v for k, v in sub.items() if k[3][0])
        shp = sum(v for k, v in sub.items() if k[2][0])
        print("  is_stm alone   purity     raw %3d/%-3d = %s   efficiency raw %3d/%-3d = %s"
              % (stp, scp, "%.3f" % (stp / scp) if scp else "  -  ",
                 stp, shp, "%.3f" % (stp / shp) if shp else "  -  "))
        print("  confusion (human -> chain), raw counts:")
        print("      %-22s %s" % ("", "chain: STM+Mic  STM only  neither"))
        for hl, hv in (("STM + MICHEL", (True, True)), ("STM, no Michel", (True, False)),
                       ("THRU", (False, False))):
            r = [sum(v for k, v in sub.items() if k[2] == hv and k[3] == c)
                 for c in ((1, 1), (1, 0), (0, 0))]
            r.append(sum(v for k, v in sub.items() if k[2] == hv) - sum(r))
            print("      %-22s %8d %9d %8d   (other %d)" % (hl, r[0], r[1], r[2], r[3]))

    if partial:
        print("\nunder-clustering (FRAG) rate: " +
              "  ".join("%s %d/%d" % (s, partial[s], got[s] - unscored[s])
                        for s in sorted(partial)))
    if moved:
        moved.sort()
        print("pin moved off the drawn chain end on %d labels: median %.2f cm, "
              "p90 %.2f cm, max %.2f cm"
              % (len(moved), moved[len(moved) // 2],
                 moved[int(0.9 * (len(moved) - 1))], moved[-1]))
    else:
        print("\npin: no label moved it off the drawn chain end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
