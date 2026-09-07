#!/usr/bin/env python3
"""doc pdhd/08 sec 9.3 -- build the PDVD STM-flip hand-scan sheet and its key.

Forked BY DUPLICATION from pdhd/d08_scan/make_d08_scan_sheet.py, which is
untouched.  Two differences that matter:

1. PDVD's stage logs `CheckSTM: cluster N -> STM= TGM=`, not `TaggerCheckSTM:`.
2. **Only four objects flip** (doc 08 sec 9.2).  A sheet of four items where
   every item is a flip tells the scanner, before they look, that something
   changed on every one -- and a scanner who knows that will hunt for a
   difference.  So the sheet carries EIGHT CONTROLS as well: four clusters
   tagged STM in BOTH arms and four tagged in NEITHER, drawn from the same
   events and the same size band.  The controls also measure the scanner's own
   baseline agreement, which four items alone cannot.

As on PDHD the sheet carries no verdict and no direction; the key carries both,
plus `is_flip`, and is read only by the scorer.

Usage: python3 d08_scan/make_d08pv_scan_sheet.py
"""
import glob, json, os, random, re, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PDVD = os.path.dirname(HERE)
WORK = os.path.join(PDVD, "work")
OUT = os.path.join(PDVD, "docs", "scan")
RUN6 = "039349"
BASE, KNOB = "d08pv30off", "d08pv30on"
SEED = 20260906
RE_STM = re.compile(r"(?:Tagger)?CheckSTM: cluster (\d+) . STM=(\d) TGM=(\d)")
RE_FIT = re.compile(r"persist_stm_fit: cluster (\d+) stmfit ")


def scan_log(tag):
    """(set of STM-tagged (evt,cid), set of (evt,cid) that got a fit at all)."""
    tagged, fitted = set(), set()
    for d in sorted(glob.glob(os.path.join(WORK, "%s_*_%s" % (RUN6, tag)))):
        e = os.path.basename(d).split("_")[1]
        lg = glob.glob(os.path.join(d, "wct_pr_*.log"))
        if not lg:
            continue
        for line in open(lg[0], errors="replace"):
            m = RE_STM.search(line)
            if m:
                if m.group(2) == "1":
                    tagged.add((e, int(m.group(1))))
                continue
            m = RE_FIT.search(line)
            if m:
                fitted.add((e, int(m.group(1))))
    return tagged, fitted


_cache = {}


def clustering(e, tag):
    k = (e, tag)
    if k in _cache:
        return _cache[k]
    p = os.path.join(WORK, "%s_%s_%s" % (RUN6, e, tag), "mabc-pr.zip")
    out = None
    if os.path.exists(p):
        with zipfile.ZipFile(p) as z:
            h = [n for n in z.namelist() if n.endswith("-clustering-global.json")]
            if h:
                d = json.loads(z.read(h[0]))
                out = (np.asarray(d["x"], float), np.asarray(d["y"], float),
                       np.asarray(d["z"], float), np.asarray(d["cluster_id"], int))
    _cache[k] = out
    return out


def geom(e, cid):
    """(npts, extent_cm) of one cluster in the BASE arm, sentinel x dropped."""
    c = clustering(e, BASE)
    if c is None:
        return None
    X, Y, Z, C = c
    m = (C == cid) & (np.abs(X) < 1000)     # |x| ~ 1.5e8 is the uncorrected-t0 sentinel
    if m.sum() < 2:
        return None
    P = np.c_[X[m], Y[m], Z[m]]
    return int(m.sum()), float(np.linalg.norm(P.max(axis=0) - P.min(axis=0)))


def moved_clusters(e):
    """cluster ids whose point set is not the same in both arms."""
    a, b = clustering(e, BASE), clustering(e, KNOB)
    if a is None or b is None:
        return set()
    da = {(x, y, z): c for x, y, z, c in zip(a[0], a[1], a[2], a[3])}
    db = {(x, y, z): c for x, y, z, c in zip(b[0], b[1], b[2], b[3])}
    return {da[k] for k in da if k in db and da[k] != db[k]}


def main():
    A, fitA = scan_log(BASE)
    B, fitB = scan_log(KNOB)
    evts = sorted({e for e, _ in A | B | fitA | fitB}, key=int)

    flips = [(e, c, "gained" if (e, c) in B else "lost") for (e, c) in sorted(A ^ B)]
    both = sorted((A & B))
    neither = sorted((fitA & fitB) - A - B)
    print("flips %d   STM in both %d   fitted but tagged in neither %d"
          % (len(flips), len(both), len(neither)))

    lo = min(geom(e, c)[0] for e, c, _ in flips)
    hi = max(geom(e, c)[0] for e, c, _ in flips)
    band = (max(1, int(lo * 0.4)), int(hi * 2.5))
    print("flip size band %d-%d points -> controls drawn from %d-%d" % (lo, hi, *band))

    rng = random.Random(SEED)

    def pick(pool, n, label):
        cand = []
        for e, c in pool:
            g = geom(e, c)
            if g and band[0] <= g[0] <= band[1] and c not in moved_clusters(e):
                cand.append((e, c, g))
        rng.shuffle(cand)
        seen, out = set(), []
        for e, c, g in cand:                 # at most one per event, spread them
            if e in seen:
                continue
            seen.add(e)
            out.append((e, c, label))
            if len(out) == n:
                break
        return out

    items = [(e, c, d) for e, c, d in flips]
    items += pick(both, 4, "control_stm")
    items += pick(neither, 4, "control_none")

    rows = []
    for e, c, d in items:
        g = geom(e, c)
        rows.append(dict(event=e, cluster=c, npts=g[0], length_cm=g[1], direction=d,
                         is_flip=int(d in ("gained", "lost")),
                         partition_moved=int(c in moved_clusters(e))))
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["scan_id"] = i
        r["tranche"] = 1 if i <= len(rows) // 2 else 2

    os.makedirs(OUT, exist_ok=True)
    sheet = os.path.join(OUT, "d08pv_stm_flip_sheet.tsv")
    with open(sheet, "w") as fh:
        fh.write("# doc pdhd/08 sec 9.3 PDVD STM hand scan -- ITEM LIST, no verdicts.\n")
        fh.write("# base=%s arm=%s run=%s seed=%d.  DIRECTION IS DELIBERATELY ABSENT,\n"
                 % (BASE, KNOB, RUN6, SEED))
        fh.write("# and so is whether an item flipped at all: 8 of these did not.\n")
        fh.write("scan_id\ttranche\tevent\tcluster\tnpts\tlength_cm\tpartition_moved\n")
        for r in sorted(rows, key=lambda x: x["scan_id"]):
            fh.write("%d\t%d\t%s\t%d\t%d\t%.1f\t%d\n"
                     % (r["scan_id"], r["tranche"], r["event"], r["cluster"],
                        r["npts"], r["length_cm"], r["partition_moved"]))
    key = os.path.join(OUT, "d08pv_stm_flip_key.tsv")
    with open(key, "w") as fh:
        fh.write("scan_id\tevent\tcluster\tdirection\tis_flip\tpartition_moved\n")
        for r in sorted(rows, key=lambda x: x["scan_id"]):
            fh.write("%d\t%s\t%d\t%s\t%d\t%d\n"
                     % (r["scan_id"], r["event"], r["cluster"], r["direction"],
                        r["is_flip"], r["partition_moved"]))
    print("wrote %s (%d items) and %s" % (sheet, len(rows), key))


if __name__ == "__main__":
    main()
