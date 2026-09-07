#!/usr/bin/env python3
"""doc pdhd/09 Phase 2 -- place the 28084 Q/L events inside the 029107 envelope.

Both sides must come from the SAME pinned binary and the SAME chain (DNN-ROI +
L1SP): the 029107 side is re-run into the d09ref tag for exactly that reason, so
any difference here is run, not code and not reconstruction chain.

Reports, per metric: the 029107 min/median/max, the 28084 median, and the
PERCENTILE the 28084 median sits at within the 029107 distribution.  Per-event
outliers are listed rather than reduced to a pass/fail.

Repro:
  python3 docs/scripts/d09_ql_compare.py /home/xqian/tmp/d09/ql_29107.json \
                                          /home/xqian/tmp/d09/ql_28084.json
"""
import argparse, json
import numpy as np

KEYS = [("input", "input clusters"), ("matched", "matched clusters"),
        ("rate", "matched/input"), ("chi2ndf", "chi2/ndf (median)"),
        ("ks", "ks_dis (median)"), ("two_boundary", "two_boundary"),
        ("flashes", "flashes"), ("points_matched", "points in matched"),
        ("pred_over_meas", "pred/meas PE")]


def pct_of(v, ref):
    ref = np.sort(np.asarray(ref, float))
    return 100.0 * np.searchsorted(ref, v, side="right") / len(ref)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref"); ap.add_argument("test")
    ap.add_argument("--refname", default="029107"); ap.add_argument("--testname", default="028084")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    R = json.load(open(a.ref)); T = json.load(open(a.test))
    print(f"{a.refname}: {len(R)} events   {a.testname}: {len(T)} events "
          f"(same pinned binary, same DNN-ROI+L1SP chain)\n")
    print(f"{'metric':22s} {a.refname+' min':>11s} {'median':>10s} {'max':>10s} | "
          f"{a.testname+' med':>12s} {'pct':>6s}")
    out = {}
    for k, label in KEYS:
        r = np.array([x[k] for x in R], float); r = r[np.isfinite(r)]
        t = np.array([x[k] for x in T], float); t = t[np.isfinite(t)]
        if not len(r) or not len(t):
            continue
        tm = float(np.median(t)); p = pct_of(tm, r)
        print(f"{label:22s} {r.min():11.3f} {np.median(r):10.3f} {r.max():10.3f} | "
              f"{tm:12.3f} {p:5.0f}%")
        out[k] = dict(ref_min=float(r.min()), ref_med=float(np.median(r)), ref_max=float(r.max()),
                      test_med=tm, pct=float(p))

    # per drift group
    print(f"\n{'per-group':22s} {'g02 ref med':>12s} {'g02 test':>10s} | {'g13 ref med':>12s} {'g13 test':>10s}")
    for k, label in [("rate", "matched/input"), ("chi2ndf", "chi2/ndf"), ("ks", "ks_dis"),
                     ("pred_over_meas", "pred/meas PE")]:
        row = [label]
        for g in ("02", "13"):
            r = np.array([x[f"g{g}_{k}"] for x in R], float); r = r[np.isfinite(r)]
            t = np.array([x[f"g{g}_{k}"] for x in T], float); t = t[np.isfinite(t)]
            row += [np.median(r) if len(r) else np.nan, np.median(t) if len(t) else np.nan]
        print(f"{row[0]:22s} {row[1]:12.3f} {row[2]:10.3f} | {row[3]:12.3f} {row[4]:10.3f}")

    # outliers: a test event outside the reference min..max on any headline metric
    print(f"\noutliers ({a.testname} events outside the {a.refname} min..max):")
    nout = 0
    for k, label in KEYS:
        r = np.array([x[k] for x in R], float); r = r[np.isfinite(r)]
        if not len(r):
            continue
        for e in T:
            v = e.get(k)
            if v is None or not np.isfinite(v):
                continue
            if v < r.min() or v > r.max():
                print(f"  {e['dir']:24s} {label:22s} {v:10.3f}  (ref {r.min():.3f}..{r.max():.3f})")
                nout += 1
    if not nout:
        print("  none -- every event of every metric lies inside the reference range")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
