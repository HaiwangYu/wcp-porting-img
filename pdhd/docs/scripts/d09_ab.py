#!/usr/bin/env python3
"""doc pdhd/09 Phase 6 -- per-(event, cluster) tagger A/B between two arms.

PDHD port of pdvd/docs/nf_sp_img_clus/scripts/fv_curved_ab.py.

Verdicts come from the taggers' OWN per-cluster log lines, never a line count:
TaggerCheckSTM emits a second shape ("already TGM; skipping") for clusters it
never evaluates, so counting lines conflates "not a stopping muon" with "never
asked".  The two arms are asserted to expose identical cluster-id sets per event
before anything is differenced -- if they do not, the arms are not comparable and
the run is aborted rather than silently reported.

Decomposition is mandatory, not optional: doc pdvd/35 and doc pdvd/41 both show a
single TGM number hiding a trade between axes and drift halves.  With --geom the
flips are also split by track length, since doc pdvd/43's adjudicating metric was
TGM on tracks over 2 m, not the raw count.

Repro:
  python3 docs/scripts/d09_ab.py d09fvoff d09p90c5 --geom --out /home/xqian/tmp/d09/ab_p90c5
"""
import argparse, glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d09_fv_pdhd import read_arm, event_points, HALF_X


def cluster_geom(pdhd, tag, keys):
    """PCA length / ends / drift half for the clusters we need, from the arm's Bee layer."""
    out = {}
    want = {}
    for (run, idx, cid) in keys:
        want.setdefault((run, idx), set()).add(cid)
    for (run, idx), cids in sorted(want.items()):
        wd = os.path.join(pdhd, "work", f"{run}_{idx}_{tag}")
        try:
            E = event_points(wd)
        except Exception:
            continue
        P, C, ph = E["P"], E["cid"], E["phys"]
        for cid in cids:
            m = (C == cid) & ph
            if m.sum() < 5:
                continue
            Q = P[m]; c = Q - Q.mean(0)
            ax = np.linalg.svd(c, full_matrices=False)[2][0]
            t = c @ ax
            e1, e2 = Q[int(np.argmax(t))], Q[int(np.argmin(t))]
            out[(run, idx, cid)] = dict(len_cm=float(t.max()-t.min()), npts=int(m.sum()),
                                        e1=[round(float(v), 2) for v in e1],
                                        e2=[round(float(v), 2) for v in e2],
                                        half=("cathode" if min(abs(e1[0]), abs(e2[0])) < HALF_X else "anode"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("off"); ap.add_argument("on")
    ap.add_argument("--pdhd", default="/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd")
    ap.add_argument("--geom", action="store_true")
    ap.add_argument("--out", default="/home/xqian/tmp/d09/ab")
    a = ap.parse_args()

    A = read_arm(a.pdhd, a.off); B = read_arm(a.pdhd, a.on)
    ev = sorted(set(A) & set(B))
    print(f"{a.off}: {len(A)} events   {a.on}: {len(B)} events   common: {len(ev)}")
    bad = [e for e in ev if set(A[e]) != set(B[e])]
    if bad:
        print(f"ABORT: {len(bad)} events expose different cluster-id sets, e.g. {bad[:3]}")
        print("  the arms are not comparable -- same pctree must give the same clusters")
        sys.exit(2)

    res = {"off": a.off, "on": a.on, "events": len(ev)}
    flips = {}
    for key in ("tgm", "stm", "fc"):
        n_off = n_on = 0; gained = []; lost = []
        for e in ev:
            for cid, v in A[e].items():
                o = bool(v.get(key)); n = bool(B[e][cid].get(key))
                n_off += o; n_on += n
                if o and not n: lost.append((e[0], e[1], cid))
                elif n and not o: gained.append((e[0], e[1], cid))
        d = n_on - n_off
        print(f"  {key.upper():4s} {n_off:6d} -> {n_on:6d}  ({d:+5d}, {100*d/max(n_off,1):+6.1f} %)   "
              f"gained {len(gained):5d}  lost {len(lost):5d}")
        res[key] = dict(off=n_off, on=n_on, delta=d, n_gained=len(gained), n_lost=len(lost))
        flips[key] = dict(gained=gained, lost=lost)

    if a.geom:
        for key in ("tgm",):
            for direction in ("lost", "gained"):
                keys = flips[key][direction]
                if not keys:
                    continue
                G = cluster_geom(a.pdhd, a.off, keys)
                L = np.array([G[k]["len_cm"] for k in keys if k in G])
                if not len(L):
                    continue
                halves = [G[k]["half"] for k in keys if k in G]
                print(f"\n  {key.upper()} {direction}: n={len(L)}  median length {np.median(L):.0f} cm  "
                      f">2 m: {100*np.mean(L>200):.0f} %  cathode half: {100*np.mean([h=='cathode' for h in halves]):.0f} %")
                for lo, hi in ((0,50),(50,100),(100,200),(200,1e9)):
                    n = int(((L>=lo)&(L<hi)).sum())
                    print(f"     {lo:4.0f}-{hi if hi<1e9 else 9999:4.0f} cm: {n:5d}")
                res.setdefault("geom", {})[f"{key}_{direction}"] = [
                    dict(run=k[0], idx=k[1], cid=k[2], **G[k]) for k in keys if k in G]
        # long-track TGM, the doc pdvd/43 adjudicator
        for arm, R in ((a.off, A), (a.on, B)):
            keys = [(e[0], e[1], cid) for e in ev for cid, v in R[e].items() if v.get("tgm")]
            G = cluster_geom(a.pdhd, a.off, keys)
            nlong = sum(1 for k in keys if k in G and G[k]["len_cm"] > 200)
            print(f"  TGM on tracks > 2 m, {arm}: {nlong}")
            res.setdefault("long_tgm", {})[arm] = nlong

    json.dump(res, open(a.out + "_verdicts.json", "w"), indent=1)
    print(f"\n-> {a.out}_verdicts.json")


if __name__ == "__main__":
    main()
