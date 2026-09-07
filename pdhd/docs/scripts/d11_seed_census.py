#!/usr/bin/env python3
"""doc pdhd/11 -- read the WCT_STM_PATH_DEBUG trajectory trace.

`run_pr_evt.sh` with WCT_STM_PATH_DEBUG=1 in the environment makes
TrackFitting::do_single_tracking emit, per pass, one block per stage of the
fitting chain:

    seed   the segment's wcpts -- for round 1 the Steiner shortest path itself
    org1   after organize_orig_path (straight-line middle fill)
    map1   after form_map           (keeps a point iff qU+qV+qW > 0)
    fit1   after trajectory_fit(charge_div_method=1)
    org2   after organize_ps_path(low_dis_limit/2, end_point_limit/2)
    map2   after form_map
    fit2   after trajectory_fit(charge_div_method=2)
    org3   after the FINAL organize_ps_path(low_dis_limit, 0)
    org3f  after the doc pdhd/11 charge test, when traj_final_fill_charge_test > 0
    final  fine_tracking_path as handed to PR::Fit

Two derived quantities carry the whole diagnosis:

  max seed edge   the longest consecutive gap in the ROUND-1 seed.  The Steiner
                  edge weight prices charge only at the two edge endpoints, over
                  a bounded [0.8, 1.2] range, so a geometric chord between two
                  charged nodes can beat any route that follows the charge.  When
                  that happens the "shortest path" is one enormous edge.
  ins             (org3 - fit2) / org3, the fraction of the FINAL trajectory
                  inserted by the last organize_ps_path -- points created by
                  straight-line interpolation after the last fit and never
                  charge-tested, because no form_map runs between org3 and the
                  PR::Fit construction.

Repro:
    WCT_STM_PATH_DEBUG=1 ./run_pr_evt.sh -stm-fit -s d11trace 028084 9   # writes the log
    ./d11_seed_census.py --log <wct_pr log> --root ../../work/028084_9_d11trace/tracking-stm.root
"""
import argparse, collections, math, sys
import numpy as np


def parse(path):
    stages = collections.defaultdict(dict)
    seeds = collections.defaultdict(list)
    for line in open(path, errors="replace"):
        if line.startswith("STMPATHN "):
            f = line.split()
            if len(f) >= 4:
                stages[f[1]][f[2]] = int(f[3])
        elif line.startswith("STMPATH ") and " seed " in line:
            f = line.split()
            if len(f) >= 7:
                seeds[f[1]].append((float(f[4]), float(f[5]), float(f[6])))
    return stages, seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, nargs="+")
    ap.add_argument("--out")
    args = ap.parse_args()

    stages, seeds = {}, {}
    for p in args.log:
        s, d = parse(p)
        stages.update(s)
        seeds.update(d)

    rows = []
    for tag, st in stages.items():
        cid, direction, rnd = (tag.split("/") + ["", ""])[:3]
        S = seeds.get(tag, [])
        edges = [math.dist(S[i], S[i + 1]) for i in range(len(S) - 1)] or [0.0]
        o3 = st.get("org3f", st.get("org3", 0))
        f2 = st.get("fit2", 0)
        rows.append(dict(tag=tag, cluster=cid, dir=direction, round=rnd,
                         nseed=len(S), maxedge=max(edges), seedL=sum(edges),
                         org1=st.get("org1", 0), map1=st.get("map1", 0),
                         fit1=st.get("fit1", 0), org2=st.get("org2", 0),
                         map2=st.get("map2", 0), fit2=f2, org3=st.get("org3", 0),
                         org3f=st.get("org3f", -1), final=st.get("final", 0),
                         ins=(o3 - f2) / max(o3, 1)))
    rows.sort(key=lambda r: -r["maxedge"])
    cols = ["tag", "nseed", "maxedge", "seedL", "org1", "map1", "fit1",
            "org2", "map2", "fit2", "org3", "org3f", "final", "ins"]
    out = []
    out.append("\t".join(cols))
    for r in rows:
        out.append("\t".join(("%.4g" % r[c]) if isinstance(r[c], float) else str(r[c]) for c in cols))
    txt = "\n".join(out) + "\n"
    if args.out:
        open(args.out, "w").write("# doc pdhd/11 d11_seed_census.py\n" + txt)
    print(txt, end="")

    r1 = [r for r in rows if r["round"] == "r1"]
    if r1:
        me = np.array([r["maxedge"] for r in r1])
        ns = np.array([r["nseed"] for r in r1])
        print("\nround-1 seeds (the raw Steiner shortest path), n=%d" % len(r1), file=sys.stderr)
        print("  max edge cm: median %.1f  p90 %.1f  max %.1f | >20 cm: %d/%d"
              % (np.median(me), np.percentile(me, 90), me.max(), (me > 20).sum(), len(me)), file=sys.stderr)
        print("  nodes:       median %d  min %d  max %d | <=5 nodes: %d/%d"
              % (np.median(ns), ns.min(), ns.max(), (ns <= 5).sum(), len(ns)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
