#!/usr/bin/env python3
"""doc pdhd/08 -- build the STM-flip hand-scan sheet and its answer key.

The SHEET is what the viewer reads: it carries no verdict from either arm, and
in particular not the DIRECTION of the flip.  Direction is the thing most likely
to bias a scanner ("this one lost its tag, so the knob must be wrong"), and it is
recoverable from nothing on the sheet.

The KEY carries every verdict and is read only by score_d08_scan.py.

Ordering is a fixed-seed shuffle, so tranche 1 is a random subset rather than
"the interesting ones first" -- putting the 6 objects that lose their tag under
every cap value at the top would announce their direction.

Usage: python3 d08_scan/make_d08_scan_sheet.py [--base d08goff] [--arm d08cap10]
"""
import argparse, glob, json, os, random, re, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PDHD = os.path.dirname(HERE)
WORK = os.path.join(PDHD, "work")
OUT = os.path.join(PDHD, "docs", "scan")
RUN6 = "029107"
SEED = 20260906


def stm_tagged(tag):
    s = set()
    for d in sorted(glob.glob(os.path.join(WORK, "%s_*_%s" % (RUN6, tag)))):
        e = os.path.basename(d).split("_")[1]
        lg = glob.glob(os.path.join(d, "wct_pr_*.log"))
        if not lg:
            continue
        for line in open(lg[0], errors="replace"):
            m = re.search(r"TaggerCheckSTM: cluster (\d+) . STM=(\d) TGM=(\d)", line)
            if m and m.group(2) == "1":
                s.add((e, int(m.group(1))))
    return s


_lay = {}


def clustering(e, tag):
    k = (e, tag)
    if k not in _lay:
        with zipfile.ZipFile(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, tag), "mabc-pr.zip")) as z:
            n = [x for x in z.namelist() if "clustering-global" in x][0]
            d = json.loads(z.read(n))
        _lay[k] = (np.asarray(d["x"], float), np.asarray(d["y"], float),
                   np.asarray(d["z"], float), np.asarray(d["cluster_id"], int))
    return _lay[k]


def cluster_pts(e, tag, cl):
    X, Y, Z, C = clustering(e, tag)
    m = C == cl
    return np.c_[X[m], Y[m], Z[m]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="d08goff")
    ap.add_argument("--arm", default="d08cap10")
    ap.add_argument("--extra", nargs="*", default=["d08cap20b", "d08cap40", "d08mrg3"],
                    help="arms whose flip sets go in the KEY only, for the core column")
    a = ap.parse_args()

    A, B = stm_tagged(a.base), stm_tagged(a.arm)
    gained, lost = B - A, A - B
    items = sorted(gained | lost, key=lambda x: (int(x[0]), x[1]))
    extra = {t: stm_tagged(t) for t in a.extra}

    rows = []
    for e, cl in items:
        p0 = cluster_pts(e, a.base, cl)
        p1 = cluster_pts(e, a.arm, cl)
        s0 = set(map(tuple, np.round(p0, 5)))
        s1 = set(map(tuple, np.round(p1, 5)))
        jac = len(s0 & s1) / max(1, len(s0 | s1))
        length = float(np.linalg.norm(p0.max(0) - p0.min(0))) if len(p0) else 0.0
        # "core": loses the tag under EVERY cap arm -- key only, never the sheet
        core = all((e, cl) in A and (e, cl) not in extra[t]
                   for t in a.extra if t.startswith("d08cap"))
        rows.append(dict(event=e, cluster=cl, npts=len(p0), length_cm=length,
                         partition_moved=int(jac < 0.99),
                         direction="gained" if (e, cl) in gained else "lost",
                         core_all_caps=int(core),
                         also_flips_mrg3=int(((e, cl) in A) != ((e, cl) in extra.get("d08mrg3", A)))))

    rnd = random.Random(SEED)
    rnd.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["scan_id"] = i
        r["tranche"] = 1 if i <= 20 else 2

    os.makedirs(OUT, exist_ok=True)
    sheet = os.path.join(OUT, "d08_stm_flip_sheet.tsv")
    key = os.path.join(OUT, "d08_stm_flip_key.tsv")
    with open(sheet, "w") as fh:
        fh.write("# doc pdhd/08 STM-flip hand scan -- ITEM LIST, no verdicts.\n")
        fh.write("# base=%s arm=%s seed=%d.  DIRECTION IS DELIBERATELY ABSENT.\n" % (a.base, a.arm, SEED))
        fh.write("# partition_moved=1: the two arms do not agree on this cluster's point set\n")
        fh.write("#   (2 of %d items); the display shows the %s partition.\n" % (len(rows), a.base))
        fh.write("scan_id\ttranche\tevent\tcluster\tnpts\tlength_cm\tpartition_moved\n")
        for r in sorted(rows, key=lambda r: r["scan_id"]):
            fh.write("%d\t%d\t%s\t%d\t%d\t%.1f\t%d\n" % (r["scan_id"], r["tranche"], r["event"],
                     r["cluster"], r["npts"], r["length_cm"], r["partition_moved"]))
    with open(key, "w") as fh:
        fh.write("# doc pdhd/08 STM-flip hand scan -- ANSWER KEY.  Read by score_d08_scan.py only.\n")
        fh.write("scan_id\tevent\tcluster\tdirection\tcore_all_caps\talso_flips_mrg3\tpartition_moved\n")
        for r in sorted(rows, key=lambda r: r["scan_id"]):
            fh.write("%d\t%s\t%d\t%s\t%d\t%d\t%d\n" % (r["scan_id"], r["event"], r["cluster"],
                     r["direction"], r["core_all_caps"], r["also_flips_mrg3"], r["partition_moved"]))
    ng = sum(1 for r in rows if r["direction"] == "gained")
    print("wrote %s (%d items: %d gained, %d lost; %d with a moved partition)"
          % (os.path.relpath(sheet, PDHD), len(rows), ng, len(rows) - ng,
             sum(r["partition_moved"] for r in rows)))
    print("wrote %s (core_all_caps=%d)" % (os.path.relpath(key, PDHD),
                                           sum(r["core_all_caps"] for r in rows)))


if __name__ == "__main__":
    main()
