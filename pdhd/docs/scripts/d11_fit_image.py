#!/usr/bin/env python3
"""doc pdhd/11 -- how far the STM fit sits from the charge it was fitted to.

The owner's report is visual: on PDHD the `stm_fit` Bee layer disagrees with
`stm` and `steiner_graph`, on PDVD the three agree.  This turns that into one
number per fitted pass:

    for every point of a T_rec_charge block, the 3-D distance to the NEAREST
    charge point of the WHOLE event (the `clustering` Bee layer)

It is deliberately tolerance-free and 3-D.  A 2-D coverage measure (doc pdhd/10
sec 3) has to pick a slice tolerance, and +-2 slices is 0.63 cm on PDHD -- tighter
than the fit's own precision, so it scores a perfectly good fit as a miss and it
is not comparable across detectors whose slice is a different length in cm.

`clustering` is the whole event, not the block's own cluster, so a fit that has
merely wandered onto a NEIGHBOURING object still scores well: a large value here
means the trajectory is in genuinely empty space.

Repro:
    ./d11_fit_image.py --label OFF ../../work/028084_*_d11off \
                       --label ON  ../../work/028084_*_d11on  --out ../figs/11_fit_image
"""
import argparse, glob, json, os, sys, zipfile
import numpy as np
import uproot
from scipy.spatial import cKDTree


def arm_rows(dirs, min_points=20):
    rows = []
    for wd in dirs:
        ev = os.path.basename(wd)
        try:
            zf = zipfile.ZipFile(os.path.join(wd, "mabc-pr.zip"))
            names = [n for n in zf.namelist() if n.endswith("-clustering-global.json")]
            if not names:
                continue
            dj = json.loads(zf.read(names[0]))
            tall = cKDTree(np.stack([dj["x"], dj["y"], dj["z"]], 1))
            r = uproot.open(os.path.join(wd, "tracking-stm.root"))["T_rec_charge"].arrays(
                ["x", "y", "z", "q", "ndf", "status"], library="np")
        except Exception as e:
            print("# skip %s: %s" % (wd, e), file=sys.stderr)
            continue
        nd = r["ndf"].astype(np.int64)
        for blk in np.unique(nd):
            m = nd == blk
            if m.sum() < min_points:
                continue
            P = np.stack([r["x"][m], r["y"][m], r["z"][m]], 1)
            d, _ = tall.query(P)
            rows.append(dict(event=ev, block=int(blk), cluster=int(blk) // 10,
                             npts=int(m.sum()), status=int(r["status"][m][0]),
                             med=float(np.median(d)),
                             f3=float((d > 3).mean()), f10=float((d > 10).mean()),
                             negq=float((r["q"][m] < 0).mean())))
    return rows


def summarize(name, rows, fh):
    if not rows:
        fh.write("%-6s no blocks\n" % name)
        return
    med = np.array([r["med"] for r in rows])
    f10 = np.array([r["f10"] for r in rows])
    neg = np.array([r["negq"] for r in rows])
    npt = sum(r["npts"] for r in rows)
    st0 = [r for r in rows if r["status"] == 0]
    fh.write("%-6s blocks=%4d points=%7d | med-of-med=%.2f cm | med>3cm: %3d (%.1f%%) "
             "| mean frac>10cm=%.3f | mean negQ=%.3f | accepted(st=0): n=%d med-of-med=%.2f "
             "med>3cm=%.1f%%\n"
             % (name, len(rows), npt, np.median(med), (med > 3).sum(),
                100 * (med > 3).mean(), f10.mean(), neg.mean(), len(st0),
                np.median([r["med"] for r in st0]) if st0 else -1,
                100 * np.mean([r["med"] > 3 for r in st0]) if st0 else -1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--dirs", action="append", default=[], nargs="+")
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--out", required=True)
    args, rest = ap.parse_known_args()

    # allow "--label NAME dir dir ... --label NAME dir dir"
    arms, cur = [], None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--label":
            cur = (argv[i + 1], []); arms.append(cur); i += 2
        elif argv[i] in ("--out", "--min-points"):
            i += 2
        else:
            if cur is None:
                cur = ("ARM", []); arms.append(cur)
            for p in sorted(glob.glob(argv[i])) or [argv[i]]:
                if os.path.isdir(p):
                    cur[1].append(p)
            i += 1

    cols = ["arm", "event", "block", "cluster", "npts", "status", "med", "f3", "f10", "negq"]
    with open(args.out + "_blocks.tsv", "w") as fh:
        fh.write("# doc pdhd/11 d11_fit_image.py  fit point -> nearest charge in the event (cm)\n")
        fh.write("\t".join(cols) + "\n")
        allrows = {}
        for name, dirs in arms:
            rows = arm_rows(dirs, args.min_points)
            allrows[name] = rows
            for r in rows:
                fh.write("\t".join([name] + [("%.4g" % r[c]) if isinstance(r[c], float) else str(r[c])
                                             for c in cols[1:]]) + "\n")
    with open(args.out + "_summary.tsv", "w") as fh:
        for name, _ in arms:
            summarize(name, allrows[name], fh)
    print(open(args.out + "_summary.tsv").read(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
