#!/usr/bin/env python3
"""doc pdhd/09 -- the EXIT census: where does a long track's end stop relative to
the wall its own direction is heading for?

The PDHD port of pdvd/docs/nf_sp_img_clus/scripts/fv_exit_census.py (doc pdvd/43).
The algorithm is unchanged; everything detector-specific is in d09_fv_pdhd.py.

Why an exit census and not a closest-approach one: doc pdvd/41 sec 13 built its
endpoint table from "the closest approach of a long cluster to a wall, within a
cap", which is contaminated by tracks that merely PASS a wall on the way out
through another -- and that contamination IS the tail a quantile reads (raising
the cap 25 -> 40 cm moved PDVD's anode-half p90 from 15 to 26 cm).  So every end
is assigned to exactly ONE surface: the first of six planes the ray from the end
along the track's outward local direction crosses.  The cathode is not a
boundary (the fiducial spans it), so a cathode crosser is not an exiter at x=0.

The anode faces are the CONTROL: imaged charge that reaches the collection plane
goes past it, so an instrument reading a large positive gap there is broken.
On PDHD the FV bound (357.985) and the collection plane (353.1) differ by 4.9 cm,
so the anode control carries that pedestal -- see d09_fv_pdhd.XCOLL.

Per end the record also carries the readout-window position in the RAW frame (an
end at the window edge is truncated by the READOUT, not by imaging, and must not
enter the surface) and, when a PR log is present, the arm's TGM/STM/FC verdicts
(a stopping muon's stop end is a legitimate non-exit).

Repro:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
  python3 docs/scripts/d09_exit_census.py --tag d09fvoff --out /home/xqian/tmp/d09/exits
"""
import argparse, glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d09_fv_pdhd import (XW, XCOLL, RAW_EARLY, RAW_LATE, WALLS, HALF_X, NORMAL,
                         wall_dist, vol_of, first_exit, event_points, read_arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdhd", default="/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd")
    ap.add_argument("--tag", default="d09fvoff")
    ap.add_argument("--runs", default="", help="comma-separated run prefixes to keep (e.g. 029107,028084)")
    ap.add_argument("--minlen", type=float, default=200.0)
    ap.add_argument("--minpts", type=int, default=40)
    ap.add_argument("--out", default="/home/xqian/tmp/d09/exits")
    a = ap.parse_args()

    arm = read_arm(a.pdhd, a.tag)
    if not arm:
        print("[note] no PR logs found for tag -- tagger verdicts will be null")
    keep = set(a.runs.split(",")) if a.runs else None

    rows, nev, nskip = [], 0, 0
    for wd in sorted(glob.glob(os.path.join(a.pdhd, "work", f"*_{a.tag}"))):
        base = os.path.basename(wd)
        parts = base.split("_")
        run, idx = parts[0], parts[1]
        if keep and run not in keep:
            continue
        try:
            E = event_points(wd)
        except Exception as ex:
            print("  skip", base, ex); nskip += 1; continue
        nev += 1
        P, cid_all, ph = E["P"], E["cid"], E["phys"]
        for cid in np.unique(cid_all[ph]):
            m = (cid_all == cid) & ph
            if m.sum() < a.minpts:
                continue
            Q = P[m]
            c = Q - Q.mean(0)
            axis = np.linalg.svd(c, full_matrices=False)[2][0]
            t = c @ axis
            length = float(t.max() - t.min())
            if length < a.minlen:
                continue
            v = arm.get((run, idx), {}).get(int(cid), {})
            gidx = np.flatnonzero(m)
            for iend, ii in enumerate((int(np.argmax(t)), int(np.argmin(t)))):
                e = Q[ii]; gi = int(gidx[ii])
                dd = np.linalg.norm(Q - e, axis=1)
                near = Q[np.argsort(dd)[:40]]
                lc = near - near.mean(0)
                u = np.linalg.svd(lc, full_matrices=False)[2][0]
                # orient OUTWARD by the cluster's global axis (end 0 = +axis end) and
                # fall back to it when the last 40 points do not follow it (a delta ray
                # or a kink): the local fit can point back INTO the detector and hand
                # the end to a wall hundreds of cm away.
                gax = axis if iend == 0 else -axis
                if np.dot(u, gax) < 0:
                    u = -u
                local_ok = bool(abs(np.dot(u, gax)) >= 0.7)
                if not local_ok:
                    u = gax
                hit = first_exit(e, u)
                if hit is None:
                    continue
                w, path, gap = hit
                xr = float(E["xraw"][gi]); sg = int(E["side"][gi])
                late = RAW_LATE if sg < 0 else -RAW_LATE
                early = -RAW_EARLY if sg < 0 else RAW_EARLY
                per = {ww: float(wall_dist(ww, e[1], e[2])) for ww in WALLS}
                per["anode"] = float(XW - abs(e[0]))
                cw = min(per, key=per.get)
                nrm = NORMAL[w] if w != "anode" else np.array([np.sign(e[0]), 0, 0])
                rows.append(dict(run=run, idx=idx, cid=int(cid), end=iend, wall=w,
                                 dmin=round(gap, 3), path=round(path, 2),
                                 # gap to the COLLECTION plane too: the anode control's
                                 # pedestal is XW - XCOLL and must not be argued away
                                 dmin_coll=round(gap - (XW - XCOLL), 3) if w == "anode" else None,
                                 x=round(float(e[0]), 3), y=round(float(e[1]), 3), z=round(float(e[2]), 3),
                                 half=("cathode" if abs(e[0]) < HALF_X else "anode"),
                                 vol=vol_of(sg) if sg else ("g02" if e[0] < 0 else "g13"),
                                 cos=round(float(abs(np.dot(u, nrm))), 4),
                                 ux=round(float(u[0]), 4), uy=round(float(u[1]), 4), uz=round(float(u[2]), 4),
                                 closest_wall=cw, closest_d=round(per[cw], 3),
                                 d_late=round(abs(xr - late), 2) if np.isfinite(xr) else None,
                                 d_early=round(abs(xr - early), 2) if np.isfinite(xr) else None,
                                 side=sg, npts=int(m.sum()), len_cm=round(length, 1),
                                 local_dir=local_ok,
                                 tgm=v.get("tgm"), stm=v.get("stm"), fc=v.get("fc")))
    json.dump(rows, open(a.out + "_rows.json", "w"), indent=0)
    print(f"{len(rows)} ends of long (>= {a.minlen:.0f} cm) clusters in {nev} events "
          f"({nskip} skipped) -> {a.out}_rows.json")

    print(f"\n{'wall':6s} {'n':>5s} {'med':>6s} {'p80':>6s} {'p90':>6s} {'>25cm':>6s} "
          f"{'rdout':>6s} {'locdir':>6s} {'wall==closest':>13s}")
    for w in WALLS + ["anode"]:
        R = [r for r in rows if r["wall"] == w]
        if not R:
            continue
        g = np.array([r["dmin"] for r in R])
        ro = np.array([min(r["d_late"], r["d_early"]) < 5
                       if r["d_late"] is not None else False for r in R])
        ld = np.array([r["local_dir"] for r in R])
        print(f"{w:6s} {len(R):5d} {np.median(g):6.1f} {np.percentile(g,80):6.1f} "
              f"{np.percentile(g,90):6.1f} {100*np.mean(g>25):5.1f}% {100*ro.mean():5.1f}% "
              f"{100*ld.mean():5.1f}% {100*np.mean([r['closest_wall']==w for r in R]):12.1f}%")
    A = [r for r in rows if r["wall"] == "anode"]
    if A:
        gc = np.array([r["dmin_coll"] for r in A])
        print(f"\nANODE CONTROL (gap to the COLLECTION plane, must be ~0 or negative): "
              f"median {np.median(gc):+.2f} cm  p25 {np.percentile(gc,25):+.2f}  n {len(A)}")


if __name__ == "__main__":
    main()
