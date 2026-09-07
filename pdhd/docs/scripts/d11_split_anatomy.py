#!/usr/bin/env python3
"""doc pdhd/11 sec 11.2 -- when unmerge splits a DENSE long cluster, was that one
track cut in half, or two crossing tracks correctly separated?

The owner's constraint is "we do not want to break a long track into pieces".
A piece count alone cannot answer it: `clustering_isolated` merges both noise
clumps AND genuinely distinct tracks that pass near each other, and undoing the
second kind is exactly what unmerge is for.

Discriminator, per split cluster:

  angle  = angle between the two pieces' principal axes (PCA on the points)
  gap    = distance between the nearest ends of the two pieces
  overlap= fractional overlap of the two pieces' projections onto the BASE
           cluster's principal axis

  one track cut in half -> axes nearly parallel (small angle), projections do
                           NOT overlap (they sit end to end), gap small
  two crossing tracks   -> large angle, and/or projections overlap heavily
                           (both pieces span the same stretch of the base axis)

Neither is a proof, so the verdict column is a LEAN, and the cases it calls
"CUT?" are the hand-scan list, not a count to quote.

Usage: d11_split_anatomy.py <base.zip> <arm.zip> --clusters 90,103 [--min-frac 0.15]
"""
import argparse, collections, json, sys, zipfile
import numpy as np


def load(path):
    z = zipfile.ZipFile(path)
    n = [x for x in z.namelist() if x.endswith("-clustering-global.json")]
    d = json.loads(z.read(n[0]))
    return d


def axis(P):
    C = P - P.mean(0)
    w, V = np.linalg.eigh(np.cov(C.T))
    return V[:, -1] / np.linalg.norm(V[:, -1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("arm")
    ap.add_argument("--clusters", default="", help="comma-separated base cluster ids")
    ap.add_argument("--min-frac", type=float, default=0.15)
    args = ap.parse_args()

    A, B = load(args.base), load(args.arm)
    key = lambda d, i: (round(d["x"][i], 3), round(d["y"][i], 3), round(d["z"][i], 3))
    bmap = {key(B, i): int(B["cluster_id"][i]) for i in range(len(B["x"]))}

    want = {int(c) for c in args.clusters.split(",") if c.strip()}
    groups = collections.defaultdict(list)
    for i in range(len(A["x"])):
        c = int(A["cluster_id"][i])
        if want and c not in want:
            continue
        groups[c].append(i)

    print("%6s %8s %7s %8s %8s %8s %9s  %s"
          % ("clus", "npts", "pieces", "kept", "angle", "gap_cm", "overlap", "lean"))
    for cid, idx in sorted(groups.items()):
        P = np.array([[A["x"][i], A["y"][i], A["z"][i]] for i in idx])
        dest = collections.Counter(bmap.get(key(A, i)) for i in idx)
        big = [c for c, v in dest.most_common() if v >= args.min_frac * len(idx)]
        kept = dest.most_common(1)[0][1] / len(idx)
        if len(big) < 2:
            print("%6d %8d %7d %8.3f %8s %8s %9s  single piece"
                  % (cid, len(idx), len(big), kept, "-", "-", "-"))
            continue
        sel = [np.array([P[j] for j, i in enumerate(idx) if bmap.get(key(A, i)) == c])
               for c in big[:2]]
        a0, a1 = axis(sel[0]), axis(sel[1])
        ang = np.degrees(np.arccos(min(1.0, abs(float(np.dot(a0, a1))))))
        base_ax = axis(P); mid = P.mean(0)
        pr = [np.dot(s - mid, base_ax) for s in sel]
        lo0, hi0, lo1, hi1 = pr[0].min(), pr[0].max(), pr[1].min(), pr[1].max()
        inter = max(0.0, min(hi0, hi1) - max(lo0, lo1))
        ov = inter / max(1e-9, min(hi0 - lo0, hi1 - lo1))
        from scipy.spatial import cKDTree
        gap = float(cKDTree(sel[0]).query(sel[1])[0].min())
        lean = ("CUT?  one track split end-to-end" if (ang < 20 and ov < 0.25)
                else "OK    two objects (crossing / offset)")
        print("%6d %8d %7d %8.3f %7.1f%s %8.1f %8.2f  %s"
              % (cid, len(idx), len(big), kept, ang, "d", gap, ov, lean))
    return 0


if __name__ == "__main__":
    sys.exit(main())
