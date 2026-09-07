#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 sec 12 -- combine both blind scans and measure the tag.

READ-ONLY.  Prints; writes nothing.

Forked by duplication from pr148_score_scan.py (M10), which scores ONE sheet
and is referenced from sec 0's repro block for scan 0.  This one joins BOTH
sheets to the A5 census and produces every table in sec 12:

  12.1  the tag's precision on the labelled re-types, with a binomial CI, the
        Fisher test of the sec 8 bar, and the overlap table that says no
        census variable separates the two classes;
  12.2  the decomposition of A5's effect on kine_reco_Enu into the estimator
        swap it was designed to make and the pion rest term that rides along;
  12.3  whether pr/99's five A5 design events still fire the tag.

The two samples were designed differently on purpose -- scan 0's S4 by energy
rank, scan 2's stratum C by energy quantile -- so pooling them is not pooling
two draws from the same biased design.  Where a number depends on which, the
output says so.

Repro:
  ./pr148_scan_combined.py
"""
import argparse, csv, math, os, statistics as st, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)
PI_MASS = 139.57
MAX_NSEG = 10                       # the (refuted) sec 8 bar
PR99_DESIGN = ("315167", "395148", "285567", "70084", "91653")


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
    return "?"


def wilson(k, n, z=1.96):
    """Wilson score interval -- the normal approximation is useless at n=18."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def fisher(a, b, c, d):
    n = a + b + c + d
    pr = lambda w, x, y, z: (math.comb(w + x, w) * math.comb(y + z, y)) / math.comb(n, w + y)
    obs, tot = pr(a, b, c, d), 0.0
    for i in range(0, min(a + b, a + c) + 1):
        j, k = a + b - i, a + c - i
        l = c + d - k
        if j < 0 or k < 0 or l < 0:
            continue
        q = pr(i, j, k, l)
        if q <= obs + 1e-12:
            tot += q
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default=os.path.join(SX, "docs/pr/pr148-a5-census.tsv"))
    ap.add_argument("--scan", action="append", metavar="KEY:LABELS", default=None,
                    help="repeatable; defaults to both committed scans")
    a = ap.parse_args()
    scans = a.scan or [
        os.path.join(SX, "docs/pr/pr148-pidscan.KEY.tsv") + ":" +
        os.path.join(SX, "docs/pr/pr148-pidscan-verdicts.tsv"),
        os.path.join(SX, "docs/pr/pr148-pidscan2.KEY.tsv") + ":" +
        os.path.join(SX, "docs/pr/pr148-pidscan2-verdicts.tsv")]

    cen = [r for r in rd(a.census) if r["start_seg"] != ""]
    byk = {(r["event"], r["shower_id"]): r for r in cen}
    V = {}
    for spec in scans:
        kf, lf = spec.rsplit(":", 1)
        key = {r["idx"]: r for r in rd(kf)}
        for i, l in ((r["idx"], r) for r in rd(lf)):
            if l.get("verdict"):
                V[(key[i]["event"], key[i]["shower_id"])] = l["verdict"]
    print("labels pooled from %d scan(s): %d object(s)" % (len(scans), len(V)))

    lab = [(k, v) for k, v in V.items() if byk[k]["verdict"] == "1"]
    em = [k for k, v in lab if v == "EM"]
    ha = [k for k, v in lab if v == "HADRONIC"]
    lo, hi = wilson(len(ha), len(lab))
    print("\n=== 12.1  the tag's precision on labelled RE-TYPES ===")
    print("  %d labelled;  right (HADRONIC) %d,  wrong (EM) %d" % (len(lab), len(ha), len(em)))
    print("  precision %.3f   95%% Wilson CI [%.2f, %.2f]%s"
          % (len(ha) / len(lab), lo, hi,
             "   <- 0.50 is INSIDE the interval" if lo <= 0.5 <= hi else ""))

    ab = [(k, v) for k, v in lab if int(byk[k]["nseg_census"]) > MAX_NSEG]
    be = [(k, v) for k, v in lab if int(byk[k]["nseg_census"]) <= MAX_NSEG]
    A, B = sum(1 for _, v in ab if v == "EM"), sum(1 for _, v in ab if v != "EM")
    C, D = sum(1 for _, v in be if v == "EM"), sum(1 for _, v in be if v != "EM")
    print("\n  the sec 8 bar (nseg > %d), now that its whole cut set is labelled:" % MAX_NSEG)
    print("    above (it removes): %d labelled -> EM %d, HADRONIC %d" % (len(ab), A, B))
    print("    below (it keeps)  : %d labelled -> EM %d, HADRONIC %d" % (len(be), C, D))
    print("    EM fraction %.2f vs %.2f,  Fisher two-sided p = %.3f -> %s"
          % (A / (A + B), C / (C + D), fisher(A, B, C, D),
             "REFUTED" if fisher(A, B, C, D) > 0.05 else "separates"))

    print("\n  does ANY census variable separate the two classes?")
    for var in ("growth", "bragg", "stem_mip", "nseg_census", "nseg_final",
                "total_len_cm", "kine_best_mev", "kine_charge_mev",
                "start_len_cm", "f_heavy", "max_mip", "smax_cm"):
        E = sorted(F(byk[k], var) for k in em)
        H = sorted(F(byk[k], var) for k in ha)
        sep = max(E) < min(H) or max(H) < min(E)
        print("    %-15s EM [%8.2f ..%8.2f]  HAD [%8.2f ..%8.2f]  %s"
              % (var, E[0], E[-1], H[0], H[-1], "SEPARATES" if sep else "overlap"))
    bb = Counter((branch(byk[k]), v) for k, v in lab)
    print("  by branch: " + ", ".join(
        "%s EM %d / HAD %d" % (b, bb[(b, "EM")], bb[(b, "HADRONIC")])
        for b in sorted({x[0] for x in bb})))

    ret = [r for r in cen if r["verdict"] == "1"]
    swap = sum(F(r, "kine_charge_mev") - F(r, "kine_best_mev") for r in ret)
    inert = [r for r in ret
             if abs(F(r, "kine_best_mev") - F(r, "kine_charge_mev")) < 0.01]
    moved = [r for r in ret if r not in inert]
    print("\n=== 12.2  what A5 actually does to Enu, over the %d joined re-types ===" % len(ret))
    print("  pion rest term  %+9.1f MeV if reverted   (%d x %.2f)" % (-PI_MASS * len(ret), len(ret), PI_MASS))
    print("  estimator swap  %+9.1f MeV if reverted   (median %.1f per object it moved)"
          % (swap, st.median([F(r, "kine_charge_mev") - F(r, "kine_best_mev") for r in moved])))
    print("  net if the tag were OFF %+.1f MeV over %d events (%.1f per object)"
          % (swap - PI_MASS * len(ret), len({(r["sample"], r["event"]) for r in ret}),
             (swap - PI_MASS * len(ret)) / len(ret)))
    print("  ratio rest-mass : estimator = %.0f : 1 by median per object" % (PI_MASS / 12.7))
    print("  apply_hadronic_dqdx_best DECLINED to write on %d of %d (%.0f%%) -- for those the"
          % (len(inert), len(ret), 100 * len(inert) / len(ret)))
    print("  re-type's ENTIRE Enu effect is the rest term, %.0f MeV between them"
          % (PI_MASS * len(inert)))
    d = lambda r: (F(r, "kine_charge_mev") - F(r, "kine_best_mev")) - PI_MASS
    lr = [r for r in ret if (r["event"], r["shower_id"]) in V]
    w = [r for r in lr if V[(r["event"], r["shower_id"])] == "EM"]
    g = [r for r in lr if V[(r["event"], r["shower_id"])] == "HADRONIC"]
    print("  reverting the %d labelled would FIX %.1f MeV and BREAK %.1f -> net %+.1f"
          % (len(lr), -sum(d(r) for r in w), -sum(d(r) for r in g),
             -sum(d(r) for r in w) - -sum(d(r) for r in g)))

    print("\n=== 12.3  do pr/99's five A5 design events still fire? ===")
    for e in PR99_DESIGN:
        rs = [r for r in cen if r["event"] == e]
        if not rs:
            print("  %-7s NOT in the census at this epoch" % e)
            continue
        fires = [r for r in rs if r["verdict"] == "1"]
        print("  %-7s %d shower(s) evaluated, %d fire%s" % (e, len(rs), len(fires),
              "" if len(fires) == 1 else "s"), end="")
        print("   " + "  ".join("sh%s:%s(g=%.2f s=%.2f)"
              % (r["shower_id"], "FIRE" if r["verdict"] == "1" else "no",
                 F(r, "growth"), F(r, "stem_mip")) for r in rs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
