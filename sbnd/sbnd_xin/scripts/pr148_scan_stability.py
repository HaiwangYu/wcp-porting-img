#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 sec 15 -- the two passes over the SAME 36 objects.

READ-ONLY.  Prints; writes nothing.

Pass 1 (scans 0 + 2) drew the best-fit trajectory only.  Pass 2 (the rescan,
sec 14) drew the same trajectory with the 3-D imaged charge underneath it.  The
sheets were reshuffled and the first-pass verdict was kept in the KEY, so the
comparison is a real measurement of two things at once:

  15.1  how stable a hand EM/hadronic label is  -- raw agreement, the chance
        agreement implied by the marginals, and Cohen's kappa;
  15.2  which objects moved, and in which direction;
  15.3  the CONFIDENT CORE -- the re-types both passes agree on -- re-tested
        for a separator, which is the strongest negative this round can make;
  15.4  what distinguishes an object that flipped from one that did not.

The pass-1 verdict is read from the RESCAN KEY (prev_verdict), which is where
pr148_pidset3.py recorded it; the pass-2 verdict from the returned sheet.  Both
files are committed, so every number here is re-derivable from the repo alone
(feedback_rederive_from_primary_source).

The Wilson interval, the branch predicate and the overlap loop are duplicated
from pr148_scan_combined.py rather than imported (M10): that script is the
sec 12 record and must not acquire a new consumer.

Repro:
  ./pr148_scan_stability.py
"""
import argparse, csv, math, os, statistics as st
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)


def rd(p):
    with open(p) as fh:
        return list(csv.DictReader((l for l in fh if not l.startswith("#")),
                                   delimiter="\t"))


def F(r, k, d=0.0):
    try:
        return float(r[k])
    except (TypeError, ValueError, KeyError):
        return d


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


VARS = ("growth", "bragg", "stem_mip", "nseg_census", "nseg_final",
        "total_len_cm", "kine_best_mev", "kine_charge_mev", "start_len_cm",
        "f_heavy", "max_mip", "smax_cm", "stem_run_cm", "star_dist_cm")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default=os.path.join(SX, "docs/pr/pr148-a5-census.tsv"))
    ap.add_argument("--key", default=os.path.join(SX, "docs/pr/pr148-pidscan3.KEY.tsv"))
    ap.add_argument("--labels", default=os.path.join(SX, "docs/pr/pr148-pidscan3-verdicts.tsv"))
    a = ap.parse_args()

    cen = {(r["event"], r["shower_id"]): r
           for r in rd(a.census) if r["start_seg"] != ""}
    key = {r["idx"]: r for r in rd(a.key)}
    rows = []
    for l in rd(a.labels):
        k = key[l["idx"]]
        if not l.get("verdict"):
            continue
        rows.append({"event": k["event"], "sh": k["shower_id"],
                     "p1": k["prev_verdict"], "p2": l["verdict"],
                     "retyped": k["a5_retyped"] == "1",
                     "prev_scan": k["prev_scan"],
                     "c": cen[(k["event"], k["shower_id"])]})

    n = len(rows)
    print("=== 15.1  are the labels stable?  %d object(s) labelled in BOTH passes ===" % n)
    cats = ("EM", "HADRONIC", "MIXED")
    m1, m2 = Counter(r["p1"] for r in rows), Counter(r["p2"] for r in rows)
    agree = sum(1 for r in rows if r["p1"] == r["p2"])
    pe = sum(m1[c] * m2[c] for c in cats) / (n * n)
    po = agree / n
    print("  pass 1 (fit only)      " + "  ".join("%s %d" % (c, m1[c]) for c in cats))
    print("  pass 2 (fit + image)   " + "  ".join("%s %d" % (c, m2[c]) for c in cats)
          + ("     <- IDENTICAL marginals" if m1 == m2 else ""))
    print("  raw agreement %.3f (%d/%d)   chance %.3f   Cohen's kappa %.3f"
          % (po, agree, n, pe, (po - pe) / (1 - pe)))
    print("  confusion (rows = pass 1, cols = pass 2):")
    print("      " + "".join("%10s" % c for c in cats))
    for c1 in cats:
        print("   %-8s" % c1 + "".join(
            "%10d" % sum(1 for r in rows if r["p1"] == c1 and r["p2"] == c2)
            for c2 in cats))
    rt = [r for r in rows if r["retyped"]]
    print("  on the %d A5 re-types alone: %d agree (%.0f%%)"
          % (len(rt), sum(1 for r in rt if r["p1"] == r["p2"]),
             100 * sum(1 for r in rt if r["p1"] == r["p2"]) / len(rt)))
    print("  => the label noise floor is ~%.0f%%; any effect smaller than that"
          % (100 * (1 - po)))
    print("     cannot be measured with hand labels at this scale.")

    fl = [r for r in rows if r["p1"] != r["p2"]]
    print("\n=== 15.2  what moved (%d of %d) ===" % (len(fl), n))
    for r in sorted(fl, key=lambda r: r["event"]):
        c = r["c"]
        print("  evt %-7s sh %-3s %-8s -> %-8s  re-typed=%-3s nseg=%-3s len=%6.1f cm  E=%6.0f MeV"
              % (r["event"], r["sh"], r["p1"], r["p2"], "yes" if r["retyped"] else "no",
                 c["nseg_final"], F(c, "total_len_cm"), F(c, "kine_best_mev")))
    print("  of the flips, %d are A5 re-types" % sum(1 for r in fl if r["retyped"]))
    mx = [r for r in rows if "MIXED" in (r["p1"], r["p2"])]
    print("\n  every object either pass called MIXED:")
    for r in sorted(mx, key=lambda r: r["event"]):
        c = r["c"]
        print("  evt %-7s sh %-3s %-8s -> %-8s  nseg=%-3s len=%6.1f cm  E=%6.0f MeV"
              % (r["event"], r["sh"], r["p1"], r["p2"], c["nseg_final"],
                 F(c, "total_len_cm"), F(c, "kine_best_mev")))

    core = [r for r in rt if r["p1"] == r["p2"]]
    ha = [r for r in core if r["p2"] == "HADRONIC"]
    em = [r for r in core if r["p2"] == "EM"]
    print("\n=== 15.3  the CONFIDENT CORE -- %d re-types both passes agree on ===" % len(core))
    if ha and em:
        lo, hi = wilson(len(ha), len(ha) + len(em))
        print("  HADRONIC (tag right) %d,  EM (tag wrong) %d" % (len(ha), len(em)))
        print("  precision %.3f   95%% Wilson CI [%.2f, %.2f]%s"
              % (len(ha) / (len(ha) + len(em)), lo, hi,
                 "   <- 0.50 still INSIDE" if lo <= 0.5 <= hi else ""))
        print("  does ANY census variable separate them, now that the noisiest")
        print("  labels have been removed by agreement?")
        nsep = 0
        for var in VARS:
            E = sorted(F(r["c"], var) for r in em)
            H = sorted(F(r["c"], var) for r in ha)
            sep = max(E) < min(H) or max(H) < min(E)
            nsep += sep
            print("    %-15s EM [%8.2f ..%8.2f]  HAD [%8.2f ..%8.2f]  %s"
                  % (var, E[0], E[-1], H[0], H[-1], "SEPARATES" if sep else "overlap"))
        print("  %d of %d variables separate." % (nsep, len(VARS)))

    print("\n=== 15.4  a flipped object versus a stable one ===")
    st_ = [r for r in rows if r["p1"] == r["p2"]]
    for var in ("kine_best_mev", "total_len_cm", "nseg_final", "growth", "stem_mip"):
        print("  %-15s flipped median %8.2f (n=%d)   stable median %8.2f (n=%d)"
              % (var, st.median([F(r["c"], var) for r in fl]), len(fl),
                 st.median([F(r["c"], var) for r in st_]), len(st_)))

    print("\n=== 15.5  the sec 8 cut set (nseg_census > 10 re-types) across both passes ===")
    cs = [r for r in rt if int(r["c"]["nseg_census"]) > 10]
    for r in sorted(cs, key=lambda r: r["event"]):
        print("  evt %-7s sh %-3s nseg=%-3s  pass1 %-8s  pass2 %-8s%s"
              % (r["event"], r["sh"], r["c"]["nseg_census"], r["p1"], r["p2"],
                 "" if r["p1"] == r["p2"] else "   <-- FLIPPED"))
    print("  flips inside the cut set: %d of %d;  below the bar: %d of %d"
          % (sum(1 for r in cs if r["p1"] != r["p2"]), len(cs),
             sum(1 for r in rt if int(r["c"]["nseg_census"]) <= 10 and r["p1"] != r["p2"]),
             sum(1 for r in rt if int(r["c"]["nseg_census"]) <= 10)))


if __name__ == "__main__":
    main()
