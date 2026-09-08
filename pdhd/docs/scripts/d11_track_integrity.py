#!/usr/bin/env python3
"""doc pdhd/11 sec 11 -- does `unmerge_assoc` break long tracks?

The owner's constraint (2026-09-07): "we do not want to break a long track into
pieces, so it is not just about ghost track."  `unmerge_assoc` is supposed to undo
only what `clustering_isolated` merged, so by construction it should detach
clumps and never cut a continuous track.  This tests that claim on the output
instead of trusting it.

Method.  Both arms read the SAME pctree, so the two `clustering` Bee layers hold
the same 3-D points; only the cluster LABELLING differs.  Points are matched by
exact (x, y, z) key, so no tolerance is involved.  For every cluster of the base
arm we then ask where its points went in the other arm:

    kept   = largest share of the base cluster's points landing in one arm cluster
    pieces = number of arm clusters holding >= `--min-frac` of the base cluster

A detached ghost shows up as kept ~ 1.0 with a small tail (the clump leaves).
A BROKEN TRACK shows up as kept well below 1 with two or more substantial pieces
-- and that is what the owner is asking about, so it is reported per cluster with
the base cluster's 3-D extent, longest first.

Usage:
  d11_track_integrity.py <base.zip> <arm.zip> [--min-len 100] [--min-frac 0.10]
"""
import argparse, collections, json, math, sys, zipfile


def load(path):
    z = zipfile.ZipFile(path)
    name = [n for n in z.namelist() if n.endswith("-clustering-global.json")]
    if not name:
        sys.exit("no clustering layer in %s" % path)
    d = json.loads(z.read(name[0]))
    pts = {}
    for x, y, zz, c in zip(d["x"], d["y"], d["z"], d["cluster_id"]):
        pts[(round(x, 3), round(y, 3), round(zz, 3))] = int(c)
    return pts


def extent(keys):
    xs = [k[0] for k in keys]; ys = [k[1] for k in keys]; zs = [k[2] for k in keys]
    dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
    return dx, dy, dz, math.sqrt(dx * dx + dy * dy + dz * dz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("arm")
    ap.add_argument("--min-len", type=float, default=100.0,
                    help="only report base clusters with diagonal extent above this (cm)")
    ap.add_argument("--min-frac", type=float, default=0.10,
                    help="a destination holding this share of the base cluster counts as a piece")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    A, B = load(args.base), load(args.arm)
    shared = set(A) & set(B)
    print("# base=%s" % args.base)
    print("# arm =%s" % args.arm)
    print("# points: base %d, arm %d, exactly shared %d (%.1f%%)"
          % (len(A), len(B), len(shared), 100.0 * len(shared) / max(len(A), 1)))
    if len(shared) < 0.99 * len(A):
        print("# WARNING: the two arms do not carry the same point cloud; "
              "cluster-to-cluster shares below are computed on the intersection only")

    groups = collections.defaultdict(list)
    for k in shared:
        groups[A[k]].append(k)

    rows = []
    for cid, keys in groups.items():
        dx, dy, dz, L = extent(keys)
        if L < args.min_len or len(keys) < 20:
            continue
        dest = collections.Counter(B[k] for k in keys)
        n = len(keys)
        kept = dest.most_common(1)[0][1] / n
        pieces = sum(1 for _, v in dest.items() if v >= args.min_frac * n)
        rows.append((L, cid, n, kept, pieces, dx, dy, dz, dest))

    rows.sort(reverse=True)
    print()
    print("# base clusters with diagonal extent > %.0f cm, longest first" % args.min_len)
    print("%8s %6s %7s %8s %7s %7s   %s"
          % ("extent", "clus", "npts", "pts/cm", "kept", "pieces", "dx,dy,dz"))
    broken = 0
    for L, cid, n, kept, pieces, dx, dy, dz, dest in rows[:args.top]:
        flag = ""
        if pieces > 1:
            flag = "  <== SPLIT into %d pieces: %s" % (
                pieces, ", ".join("%d:%d" % (c, v) for c, v in dest.most_common(4)))
        print("%8.1f %6d %7d %8.2f %7.3f %7d   %.0f,%.0f,%.0f%s"
              % (L, cid, n, n / L, kept, pieces, dx, dy, dz, flag))
    for L, cid, n, kept, pieces, dx, dy, dz, dest in rows:
        if pieces > 1:
            broken += 1
    print()
    print("# summary over %d base clusters longer than %.0f cm:" % (len(rows), args.min_len))
    print("#   split into >1 substantial piece (>=%.0f%% each): %d" % (100 * args.min_frac, broken))
    if rows:
        ks = sorted(r[3] for r in rows)
        print("#   kept-fraction: min %.3f  median %.3f  mean %.3f"
              % (ks[0], ks[len(ks) // 2], sum(ks) / len(ks)))
        print("#   clusters keeping < 90%% of their points: %d"
              % sum(1 for k in ks if k < 0.90))
        # A real track is dense; a noise dot-group is not.  Report the two
        # populations apart, because "do not break a long track" is a statement
        # about the dense one only.
        DENSE = 3.0   # points per cm of diagonal extent
        for label, sel in (("dense (>= %.0f pts/cm, i.e. real tracks)" % DENSE,
                            lambda r: r[2] / r[0] >= DENSE),
                           ("sparse (<  %.0f pts/cm, dot groups)" % DENSE,
                            lambda r: r[2] / r[0] < DENSE)):
            sub = [r for r in rows if sel(r)]
            if not sub:
                continue
            kk = sorted(r[3] for r in sub)
            print("#   %-42s n=%3d  median kept %.3f  min %.3f  split %d"
                  % (label, len(sub), kk[len(kk) // 2], kk[0],
                     sum(1 for r in sub if r[4] > 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
