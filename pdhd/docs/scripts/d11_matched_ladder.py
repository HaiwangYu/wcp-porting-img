#!/usr/bin/env python3
"""doc pdhd/11 sec 10 -- the unmerge ladder on a MATCHED block population.

`d11_fit_image.py` reports "blocks with median fit->charge > 3 cm" as a fraction
of whatever blocks an arm produced.  That is biased when an arm CHANGES the
population: `unmerge_assoc` splits clusters into dots, dots fall below the
>=20-point cut, and the object leaves the census entirely.  Part of "2 bad of 17"
vs "7 bad of 22" is then objects leaving, not trajectories being repaired
(`feedback_matched_population_metric_bias`, `feedback_cleanup_step_masks_upstream_defect`).

This reads d11_fit_image.py's _blocks.tsv and reports, in addition to the raw
per-arm numbers:

  * blocks and fitted POINTS next to every count, so attrition is visible;
  * the intersection census -- only (event, cluster) pairs present in EVERY arm,
    so the same objects are compared;
  * absolute bad-POINT counts (npts * f10), which do not rescale when the
    denominator moves.

Cluster ids are the tagger's own.  They are comparable only WITHIN one pctree, so
every arm passed here must read the same clustering output.  Passing arms from
different pctrees is a silent error and the --pctree label is required to make
that explicit.

Usage:
  d11_matched_ladder.py <blocks.tsv> --pctree d11seponA [--order A,B,C,D]
"""
import argparse, collections, sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--pctree", required=True,
                    help="the clustering arm every listed PR arm read (asserted, not checked)")
    ap.add_argument("--order", default="", help="comma-separated arm order")
    args = ap.parse_args()

    rows = []
    with open(args.tsv) as fh:
        hdr = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            rows.append(dict(zip(hdr, f)))

    for r in rows:
        r["npts"] = int(r["npts"]); r["status"] = int(r["status"])
        r["med"] = float(r["med"]); r["f10"] = float(r["f10"]); r["negq"] = float(r["negq"])
        # the event field is the work dir; strip the arm tag to get run_evt
        ev = r["event"]
        r["key"] = ("_".join(ev.split("_")[:2]), r["cluster"])

    arms = args.order.split(",") if args.order else sorted({r["arm"] for r in rows})
    by = {a: {r["key"]: r for r in rows if r["arm"] == a} for a in arms}
    for a in arms:
        if not by[a]:
            sys.exit("no rows for arm %r; have %s" % (a, sorted({r['arm'] for r in rows})))

    common = set(by[arms[0]])
    for a in arms[1:]:
        common &= set(by[a])

    print("# doc pdhd/11 -- all arms read the pctree of clustering arm %s" % args.pctree)
    print("# raw census: every block the arm produced")
    print("%-10s %7s %8s %8s %8s %10s %8s" %
          ("arm", "blocks", "points", "bad>3cm", "bad%", "badpoints", "med-med"))
    for a in arms:
        rs = list(by[a].values())
        n = len(rs); p = sum(r["npts"] for r in rs)
        bad = sum(1 for r in rs if r["med"] > 3)
        bp = sum(r["npts"] * r["f10"] for r in rs)
        med = sorted(r["med"] for r in rs)[n // 2] if n else float("nan")
        print("%-10s %7d %8d %8d %7.1f%% %10.0f %8.2f" % (a, n, p, bad, 100.0 * bad / max(n, 1), bp, med))

    print()
    print("# matched census: only the %d (event, cluster) blocks present in ALL %d arms"
          % (len(common), len(arms)))
    print("%-10s %7s %8s %8s %8s %10s %8s %14s" %
          ("arm", "blocks", "points", "bad>3cm", "bad%", "badpoints", "med-med", "accepted st=0"))
    for a in arms:
        rs = [by[a][k] for k in common]
        n = len(rs); p = sum(r["npts"] for r in rs)
        bad = sum(1 for r in rs if r["med"] > 3)
        bp = sum(r["npts"] * r["f10"] for r in rs)
        med = sorted(r["med"] for r in rs)[n // 2] if n else float("nan")
        acc = [r for r in rs if r["status"] == 0]
        amed = sorted(r["med"] for r in acc)[len(acc) // 2] if acc else float("nan")
        print("%-10s %7d %8d %8d %7.1f%% %10.0f %8.2f %7d %6.2f" %
              (a, n, p, bad, 100.0 * bad / max(n, 1), bp, med, len(acc), amed))

    print()
    print("# blocks each arm DROPPED relative to %s (attrition, not repair)" % arms[0])
    base = set(by[arms[0]])
    for a in arms[1:]:
        gone = base - set(by[a])
        newb = set(by[a]) - base
        gbad = sum(1 for k in gone if by[arms[0]][k]["med"] > 3)
        print("  %-10s dropped %3d blocks (%d of them were bad), gained %3d"
              % (a, len(gone), gbad, len(newb)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
