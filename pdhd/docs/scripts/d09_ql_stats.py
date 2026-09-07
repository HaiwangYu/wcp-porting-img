#!/usr/bin/env python3
"""doc pdhd/09 Phase 2 -- Q/L quality per event, for the 28084-vs-029107 comparison.

Metrics per event (and per drift group 02 / 13):
  input     len(clusters)   -- QLMatching.cxx:4145 dumps run.clusters, i.e. the
                               matching INPUT set, NOT the matched set.  Normalising
                               by it is the whole point: a high absolute matched
                               count is usually event busyness, not better matching.
  matched   distinct main_cluster over auto_selected bundles
  rate      matched / input
  chi2/ndf, ks_dis   medians over auto_selected bundles
  two_boundary       auto_selected bundles flagged -- the anode-cathode crossers
                     the fiducial instrument consumes
  pred/meas          median total_pred_light / total_PE over auto_selected

Repro:
  python3 docs/scripts/d09_ql_stats.py --tag d09     --run 028084 --out /home/xqian/tmp/d09/ql_28084.json
  python3 docs/scripts/d09_ql_stats.py --tag d09ref  --run 029107 --out /home/xqian/tmp/d09/ql_29107.json
"""
import argparse, glob, json, os
import numpy as np

def med(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else float("nan")

def stats_for(bundles, clusters, flashes, group=None):
    if group is not None:
        # The dump's `apa` is the per-drift-side ApaRun index, NOT the WCT APA
        # number: verified on the dump's own geometry -- apa 0 holds x in
        # [-353.2, 119.0] (group02, APA0/2) and apa 1 holds [-119.5, 353.0]
        # (group13, APA1/3), and its opdets sit at x = -356.4 / +356.2.
        want = 0 if group == "02" else 1
        bundles = [b for b in bundles if b.get("apa") == want]
        clusters = [c for c in clusters if c.get("apa") == want]
        flashes = [f for f in flashes if f.get("apa") == want]
    sel = [b for b in bundles if b.get("auto_selected")]
    # main_cluster keys on `uid`, NOT `ident`: ident is not unique across drift
    # sides (91 distinct for 101 clusters in 028084/74408) and keying on it
    # silently produced a matched/input ratio above 1.
    mc = {b["main_cluster"] for b in sel if b.get("main_cluster") is not None}
    matched = len(mc)
    ninput = len({c["uid"] for c in clusters})
    npts = sum(c.get("npoints", 0) for c in clusters if c["uid"] in mc)
    c2 = [b["chi2"]/b["ndf"] for b in sel if b.get("ndf")]
    pm = [b["total_pred_light"]/b["total_PE"] for b in sel
          if b.get("total_PE") and b.get("total_pred_light") is not None]
    return dict(input=ninput, matched=matched,
                rate=(matched/ninput if ninput else float("nan")),
                chi2ndf=med(c2), ks=med([b.get("ks_dis") for b in sel]),
                two_boundary=sum(1 for b in sel if b.get("two_boundary")),
                nbundles=len(bundles), nsel=len(sel), flashes=len(flashes),
                points_matched=int(npts), pred_over_meas=med(pm))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdhd", default="/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rows = []
    for wd in sorted(glob.glob(os.path.join(a.pdhd, "work", f"{a.run}_*_{a.tag}"))):
        cal = glob.glob(os.path.join(wd, "calib-evt*.json"))
        cal = [c for c in cal if "-group" not in os.path.basename(c)]
        if not cal:
            continue
        d = json.load(open(cal[0]))
        r = dict(dir=os.path.basename(wd), ident=d.get("charge_ident"),
                 nticks=d.get("readout_nticks"))
        r.update(stats_for(d["bundles"], d["clusters"], d["flashes"]))
        for gname in ("02", "13"):
            g = stats_for(d["bundles"], d["clusters"], d["flashes"], gname)
            for k, v in g.items():
                r[f"g{gname}_{k}"] = v
        rows.append(r)
    json.dump(rows, open(a.out, "w"), indent=1)
    keys = ["input", "matched", "rate", "chi2ndf", "ks", "two_boundary", "flashes", "points_matched", "pred_over_meas"]
    print(f"{a.run} tag={a.tag}: {len(rows)} events -> {a.out}")
    print(f"{'metric':16s} {'min':>10s} {'p25':>10s} {'median':>10s} {'p75':>10s} {'max':>10s}")
    for k in keys:
        v = np.array([r[k] for r in rows], float); v = v[np.isfinite(v)]
        if not len(v): continue
        q = np.percentile(v, [0, 25, 50, 75, 100])
        print(f"{k:16s} " + " ".join(f"{x:10.3f}" for x in q))

if __name__ == "__main__":
    main()
