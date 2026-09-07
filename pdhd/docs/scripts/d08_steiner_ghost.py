#!/usr/bin/env python3
"""doc pdhd/08 -- the owner-facing metric: Steiner graph points with no live charge.

doc pdhd/07 counted retiled BLOBS.  The owner asked about ghost Steiner graph
EDGES.  This closes that gap: for each arm it reads the Bee zip's `steiner_graph`
layer and measures each point's distance to the nearest `clustering` (live) point,
the doc pdvd/40 statistic, reproduced for PDHD.

Two controls, both printed, both must pass before any number here is read:
  FRAME  `steiner_terminals` is a charge-selected SUBSET of the Steiner cloud, so
         by construction it sits ON live charge.  Median distance ~0 proves the
         two layers share a coordinate frame.  A systematic offset would mean a
         display bug, not a fabricated point (doc pdvd/40 sec 1).
  SANE   QLMatching stamps unmatched clusters with t0 = -1e12, which puts their
         x at ~1.5e8 cm.  Points beyond |x| > 1e4 cm are dropped and counted; a
         kd-tree built over them is meaningless.

**The confound this script must control.** The Bee `steiner_graph` layer carries
only the STM-FITTED clusters, and the doc-08 knobs change which clusters get a
fit (evt 991: 20 fitted with the knobs off, 18 with them on).  A raw arm-vs-arm
ghost count therefore mixes "less fabrication" with "two fewer clusters drawn".
--pair fixes this: it matches layer clusters between the two arms by centroid
(the layer's own cluster_id is a per-drawing index, not the tagger's id) and
reports the ghost counts over the MATCHED set only, listing what did not match.
Unpaired mode prints raw per-arm numbers and must not be used to compare arms.

The centroid tolerance is a matching parameter, not a physics one, and the
conclusion must not depend on it -- but it is NOT neutral between arms.  A
cluster fails to match when its centroid moved, and the centroid moves precisely
when its Steiner cloud changed shape, so a tight tolerance drops the
most-affected clusters and UNDERSTATES the arms with the largest effect.  On
d08cap10 the measured improvement in "> 3 cm" rises monotonically as the
exclusion shrinks: -66 % (tol 2, 233 unmatched/arm), -74 % (5, 114), -78 %
(20, 20), -79 % (50, 7).  Default is therefore 50 cm, the loosest, and the
matched-cluster count is printed so the denominator is visible.  On d08goff -> d08cap10 over 30 events,
points > 10 cm from live charge go 263 -> 4 (tol 2), 876 -> 6 (5),
1205 -> 6 (20), 1419 -> 6 (50), while the unmatched count falls 233 -> 7 per
arm.  Default 20 cm: it pairs all but ~20 of ~700 drawn clusters, and the
unmatched counts stay EQUAL on the two sides at every tolerance, which is the
check that the matcher is pairing symmetrically rather than dropping one arm.

Usage: d08_steiner_ghost.py <armdir> [<armdir> ...] [--tsv out.tsv]
       d08_steiner_ghost.py --pair <base_tag> <arm_tag> [--run6 029107] [--tol 5]
"""
import json, sys, os, zipfile, argparse
import numpy as np
from scipy.spatial import cKDTree

XMAX = 1e4   # cm; beyond this is the t0 = -1e12 sentinel leak


def layer(z, name):
    for n in z.namelist():
        if n.endswith("-%s-global.json" % name):
            return json.loads(z.read(n))
    return None


def pts(d):
    if d is None:
        return np.empty((0, 3)), 0
    a = np.array([d["x"], d["y"], d["z"]], dtype=float).T
    bad = int(np.sum(np.abs(a[:, 0]) > XMAX))
    return a[np.abs(a[:, 0]) <= XMAX], bad


def one(armdir):
    zp = os.path.join(armdir, "mabc-pr.zip")
    if not os.path.exists(zp):
        return None
    z = zipfile.ZipFile(zp)
    live, live_bad = pts(layer(z, "clustering"))
    st, st_bad = pts(layer(z, "steiner_graph"))
    term, _ = pts(layer(z, "steiner_terminals"))
    if len(live) == 0 or len(st) == 0:
        return dict(arm=armdir, nlive=len(live), nst=len(st), skip=True)
    kt = cKDTree(live)
    d, _ = kt.query(st, k=1)
    dt = kt.query(term, k=1)[0] if len(term) else np.array([np.nan])
    return dict(arm=armdir, nlive=len(live), nst=len(st),
                bad=live_bad + st_bad,
                frame_med=float(np.nanmedian(dt)), nterm=len(term),
                g3=int((d > 3).sum()), g10=int((d > 10).sum()), g30=int((d > 30).sum()),
                dmax=float(d.max()), dmed=float(np.median(d)))


def by_cluster(armdir):
    """{layer cluster_id: (centroid, distances-to-live)} plus the live count."""
    zp = os.path.join(armdir, "mabc-pr.zip")
    if not os.path.exists(zp):
        return None, 0
    z = zipfile.ZipFile(zp)
    ld = layer(z, "clustering")
    sd = layer(z, "steiner_graph")
    if ld is None or sd is None:
        return None, 0
    live, _ = pts(ld)
    if len(live) == 0:
        return None, 0
    kt = cKDTree(live)
    sx = np.array([sd["x"], sd["y"], sd["z"]], dtype=float).T
    cid = np.array(sd["cluster_id"])
    keep = np.abs(sx[:, 0]) <= XMAX
    sx, cid = sx[keep], cid[keep]
    if len(sx) == 0:
        return {}, len(live)
    d, _ = kt.query(sx, k=1)
    out = {}
    for c in np.unique(cid):
        m = cid == c
        out[int(c)] = (sx[m].mean(axis=0), d[m])
    return out, len(live)


def pair(base_tag, arm_tag, run6, tol, work=None):
    W = work or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "work")
    import glob, re
    evts = sorted({re.match(r".*/(%s)_(\d+)_%s$" % (run6, base_tag), d).group(2)
                   for d in glob.glob(os.path.join(W, "%s_*_%s" % (run6, base_tag)))}, key=int)
    tot = dict(nb=0, na=0, b3=0, a3=0, b10=0, a10=0, b30=0, a30=0,
               unb=0, una=0, mev=0, nev=0, mcl=0)
    worst_b = worst_a = 0.0
    print("%-6s %7s %7s   %7s %7s   %6s %6s   %6s %6s   %s" %
          ("evt", "cl_base", "cl_arm", "pts_base", "pts_arm",
           ">3 b", ">3 a", ">10 b", ">10 a", "unmatched b/a"))
    for e in evts:
        B, _ = by_cluster(os.path.join(W, "%s_%s_%s" % (run6, e, base_tag)))
        A, _ = by_cluster(os.path.join(W, "%s_%s_%s" % (run6, e, arm_tag)))
        if B is None or A is None:
            continue
        tot["nev"] += 1
        used, pairs = set(), []
        for cb, (kb, db) in sorted(B.items()):
            best, bd = None, 1e9
            for ca, (ka, da) in A.items():
                if ca in used:
                    continue
                dd = float(np.linalg.norm(kb - ka))
                if dd < bd:
                    best, bd = ca, dd
            if best is not None and bd <= tol:
                used.add(best); pairs.append((cb, best))
        unb, una = len(B) - len(pairs), len(A) - len(pairs)
        tot["mcl"] += len(pairs)
        if unb or una:
            tot["mev"] += 1
        nb = na = b3 = a3 = b10 = a10 = b30 = a30 = 0
        for cb, ca in pairs:
            db, da = B[cb][1], A[ca][1]
            nb += len(db); na += len(da)
            b3 += int((db > 3).sum()); a3 += int((da > 3).sum())
            b10 += int((db > 10).sum()); a10 += int((da > 10).sum())
            b30 += int((db > 30).sum()); a30 += int((da > 30).sum())
            worst_b = max(worst_b, float(db.max()) if len(db) else 0)
            worst_a = max(worst_a, float(da.max()) if len(da) else 0)
        for k, v in (("nb", nb), ("na", na), ("b3", b3), ("a3", a3), ("b10", b10),
                     ("a10", a10), ("b30", b30), ("a30", a30), ("unb", unb), ("una", una)):
            tot[k] += v
        print("%-6s %7d %7d   %7d %7d   %6d %6d   %6d %6d   %d/%d" %
              (e, len(B), len(A), nb, na, b3, a3, b10, a10, unb, una))
    print("-" * 96)
    print("MATCHED-CLUSTER TOTAL over %d events (%d had an unmatched cluster):" %
          (tot["nev"], tot["mev"]))
    print("  matched clusters %d   <-- the denominator; compare it across arms before"
          " comparing counts" % tot["mcl"])
    print("  steiner points   %d -> %d" % (tot["nb"], tot["na"]))
    print("  > 3 cm from live %d -> %d   (%+.1f%%)" %
          (tot["b3"], tot["a3"], 100.0 * (tot["a3"] - tot["b3"]) / tot["b3"] if tot["b3"] else 0))
    print("  > 10 cm          %d -> %d" % (tot["b10"], tot["a10"]))
    print("  > 30 cm          %d -> %d" % (tot["b30"], tot["a30"]))
    print("  worst distance   %.1f -> %.1f cm" % (worst_b, worst_a))
    print("  clusters drawn but unmatched: base %d, arm %d (tol %g cm) -- these are"
          % (tot["unb"], tot["una"], tol))
    print("  the population change the raw per-arm numbers would have hidden.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--tsv")
    ap.add_argument("--pair", action="store_true")
    ap.add_argument("--run6", default="029107")
    ap.add_argument("--tol", type=float, default=50.0)
    ap.add_argument("--work", default=None,
                    help="arm work root; defaults to this script's own detector "
                         "(pdhd/work).  Use ../pdvd/work to grade PDVD.")
    a = ap.parse_args()
    if a.pair:
        if len(a.arms) != 2:
            sys.exit("--pair takes exactly two TAGS (not dirs)")
        pair(a.arms[0], a.arms[1], a.run6, a.tol, a.work)
        return
    rows = [r for r in (one(x) for x in sorted(a.arms)) if r]
    ok = [r for r in rows if not r.get("skip")]
    print("%-34s %9s %9s %8s %8s %8s %8s %8s" %
          ("arm", "nlive", "nsteiner", ">3cm", ">10cm", ">30cm", "max_cm", "frame"))
    for r in ok:
        print("%-34s %9d %9d %8d %8d %8d %8.1f %8.3f" %
              (os.path.basename(r["arm"]), r["nlive"], r["nst"], r["g3"], r["g10"],
               r["g30"], r["dmax"], r["frame_med"]))
    for r in rows:
        if r.get("skip"):
            print("%-34s SKIPPED (nlive=%d nsteiner=%d)" % (os.path.basename(r["arm"]), r["nlive"], r["nst"]))
    if ok:
        tot = lambda k: sum(r[k] for r in ok)
        print("-" * 96)
        print("%-34s %9d %9d %8d %8d %8d" %
              ("TOTAL (%d arms)" % len(ok), tot("nlive"), tot("nst"), tot("g3"), tot("g10"), tot("g30")))
        fr = max(r["frame_med"] for r in ok)
        print("FRAME control: worst per-arm median terminal->live distance = %.3f cm  %s"
              % (fr, "PASS" if fr < 0.5 else "*** FAIL: the two layers do not share a frame ***"))
        nb = tot("bad")
        print("SANE control: %d points dropped beyond |x| > %g cm" % (nb, XMAX))
    if a.tsv:
        with open(a.tsv, "w") as fh:
            fh.write("arm\tnlive\tnsteiner\tg3\tg10\tg30\tdmax\tdmed\tframe_med\n")
            for r in ok:
                fh.write("%s\t%d\t%d\t%d\t%d\t%d\t%.2f\t%.3f\t%.4f\n" %
                         (os.path.basename(r["arm"]), r["nlive"], r["nst"], r["g3"], r["g10"],
                          r["g30"], r["dmax"], r["dmed"], r["frame_med"]))
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
