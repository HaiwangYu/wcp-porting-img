#!/usr/bin/env python3
"""doc pdhd/08 stage 1d -- which form of R2b closes the fragmentation escape?

doc pdhd/07 found that the retiler's 20 cm run bound leaks because one fabricated
column is cut into several runs, each shorter than the bound.  Two repairs are
possible and they are NOT interchangeable:

  A  per-component union   -- bound the union bbox of ALL unsupported blobs in a
                              connected component.  Works only if the pieces of a
                              fragmented ghost sit in the SAME component.
  B  proximity merge       -- merge runs whose bounding boxes are within d cm of
                              each other, component-independent, then bound the
                              merged group.  Works either way, more code.
  D  co-location with a    -- remove a surviving run whose bbox lies within d cm of
     PROVEN ghost             a run in the SAME component that the per-run bound
                              already removed.  The most conservative of the three:
                              it never condemns a run on its own, only one sharing
                              space with a fabrication the existing rule has already
                              judged.  Requires max_run > 0 by construction.

This script decides between them offline from the untruncated BADBLOBRUN lines
(-S retile_bad_blob_report=true), before any decision logic is written.

Only the FINAL retile pass of each (cluster, apa, face) is counted:
ImproveCluster_2::mutate retiles twice and both passes report (doc 07 sec 2).

Usage: d08_run_merge_sim.py <log> [...] [--cid N] [--bounds 20,30,40] [--tsv f]
"""
import re, sys, argparse, math

RE_HEAD = re.compile(
    r"BADBLOB cid=(?P<cid>-?\d+) ident=(?P<ident>-?\d+) apa=(?P<apa>\d+) face=(?P<face>\d+) ")
RE_RUN = re.compile(
    r"BADBLOBRUN cid=(?P<cid>-?\d+) ident=(?P<ident>-?\d+) apa=(?P<apa>\d+) face=(?P<face>\d+) "
    r"k=(?P<k>\d+) comp=(?P<comp>-?\d+) nb=(?P<nb>\d+) nslices=(?P<nslices>\d+) "
    r"span_cm=(?P<span>-?[\d.]+) "
    r"bb=\((?P<x0>-?[\d.]+),(?P<x1>-?[\d.]+),(?P<y0>-?[\d.]+),(?P<y1>-?[\d.]+),"
    r"(?P<z0>-?[\d.]+),(?P<z1>-?[\d.]+)\)")


def parse(path, which="last"):
    """Return {key: [runs]} for the FINAL (or FIRST) retile pass of each key.

    ImproveCluster_2::mutate retiles twice and both passes report (doc 07 sec 2).
    "last" is the pass that produces the cloud the Steiner build sees, and is what
    every census table uses.  "first" is the pass whose INPUT is the untouched
    original cluster, which makes it the only pass comparable between a knob-off
    and a knob-on arm: once the first pass removes different blobs, the second
    pass is retiling a different intermediate cluster.  Use "first" to validate
    the C++ against this model.
    """
    passes, seen, skip = {}, set(), set()
    for line in open(path, errors="replace"):
        m = RE_HEAD.search(line)
        if m:
            k = tuple(int(m.group(x)) for x in ("cid", "ident", "apa", "face"))
            if which == "first" and k in seen:
                skip.add(k)              # keep pass 1, ignore every later pass
            else:
                passes[k] = []           # "last": a new pass supersedes the previous
            seen.add(k)
            continue
        m = RE_RUN.search(line)
        if m:
            d = m.groupdict()
            k = tuple(int(d[x]) for x in ("cid", "ident", "apa", "face"))
            if k in skip:
                continue                     # a later pass in --pass first mode
            passes.setdefault(k, []).append(dict(
                k=int(d["k"]), comp=int(d["comp"]), nb=int(d["nb"]),
                nslices=int(d["nslices"]), span=float(d["span"]),
                bb=[float(d[x]) for x in ("x0", "x1", "y0", "y1", "z0", "z1")]))
    return passes


def diag(bb):
    return math.sqrt((bb[1]-bb[0])**2 + (bb[3]-bb[2])**2 + (bb[5]-bb[4])**2)


def union(a, b):
    return [min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]),
            max(a[3], b[3]), min(a[4], b[4]), max(a[5], b[5])]


def near(a, b, d):
    """True if the boxes are within d cm on every axis (inflated-box overlap)."""
    return (a[0]-d <= b[1] and b[0]-d <= a[1] and
            a[2]-d <= b[3] and b[2]-d <= a[3] and
            a[4]-d <= b[5] and b[4]-d <= a[5])


def merge_groups(runs, d, same_comp=False):
    """Transitively merge runs whose boxes are within d.  Returns list of index lists.
    same_comp: only merge runs that share a connected component."""
    n = len(runs)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i in range(n):
        for j in range(i+1, n):
            if same_comp and runs[i]["comp"] != runs[j]["comp"]:
                continue
            if near(runs[i]["bb"], runs[j]["bb"], d):
                ri, rj = find(i), find(j)
                if ri != rj: parent[max(ri, rj)] = min(ri, rj)
    g = {}
    for i in range(n):
        g.setdefault(find(i), []).append(i)
    return list(g.values())


def group_stats(runs, idxs):
    bb = runs[idxs[0]]["bb"]
    nb = 0
    for i in idxs:
        bb = union(bb, runs[i]["bb"]); nb += runs[i]["nb"]
    return diag(bb), nb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--cid", type=int)
    ap.add_argument("--maxrun", type=float, default=20.0,
                    help="the production per-run bound already in force (cm)")
    ap.add_argument("--bounds", default="20,30,40")
    ap.add_argument("--merge-d", default="0,1,3,5")
    ap.add_argument("--pass", dest="which", choices=("first", "last"), default="last")
    ap.add_argument("--predict", type=float,
                    help="print only the variant-E prediction at this merge_d (cm), for "
                         "cross-validating the C++ merge_rm= census field")
    a = ap.parse_args()
    bounds = [float(x) for x in a.bounds.split(",")]
    mds = [float(x) for x in a.merge_d.split(",")]

    passes = {}
    for p in a.logs:
        passes.update(parse(p, a.which))
    if a.predict is not None:
        extra = 0
        for v in passes.values():
            for idxs in merge_groups(v, a.predict, same_comp=True):
                dd, _ = group_stats(v, idxs)
                if dd > a.maxrun:
                    extra += sum(v[i]["nb"] for i in idxs if v[i]["span"] <= a.maxrun)
        print("variant-E prediction: merge_d=%g maxrun=%g pass=%s -> %d blobs "
              "removed by the merge over %d passes" % (a.predict, a.maxrun, a.which, extra, len(passes)))
        return
    if not passes:
        sys.exit("no BADBLOBRUN lines -- was -S retile_bad_blob_report=true set?")

    n_runs = sum(len(v) for v in passes.values())
    n_unsup = sum(r["nb"] for v in passes.values() for r in v)
    base_rm = sum(r["nb"] for v in passes.values() for r in v if r["span"] > a.maxrun)
    print("== %d final passes, %d runs, %d unsupported blobs in kept components ==" %
          (len(passes), n_runs, n_unsup))
    print("   production per-run bound %.0f cm already removes %d (%.1f%%); "
          "%d survive" % (a.maxrun, base_rm, 100.0*base_rm/n_unsup if n_unsup else 0,
                          n_unsup - base_rm))

    # --- how often is a ghost fragmented WITHIN one component? ---
    same_comp_pairs = 0; diff_comp_pairs = 0
    for v in passes.values():
        big = [r for r in v if r["span"] > 3.0]
        for i in range(len(big)):
            for j in range(i+1, len(big)):
                if near(big[i]["bb"], big[j]["bb"], 1.0):
                    if big[i]["comp"] == big[j]["comp"]: same_comp_pairs += 1
                    else: diff_comp_pairs += 1
    tot = same_comp_pairs + diff_comp_pairs
    print("\n== adjacent run pairs (>3 cm, boxes within 1 cm) -- where the cut happened ==")
    print("   same component %d   different components %d   (%s)" %
          (same_comp_pairs, diff_comp_pairs,
           "per-component union WOULD rejoin most" if same_comp_pairs >= diff_comp_pairs
           else "per-component union would MISS most -- use the proximity merge"))
    if tot:
        print("   same-component share %.1f%%" % (100.0*same_comp_pairs/tot))

    print("\n== variant A: per-component union bbox, on top of the %.0f cm per-run bound ==" % a.maxrun)
    print("   %-8s %14s %14s" % ("bound", "extra_removed", "%of survivors"))
    surv = n_unsup - base_rm
    for B in bounds:
        extra = 0
        for v in passes.values():
            bycomp = {}
            for i, r in enumerate(v):
                bycomp.setdefault(r["comp"], []).append(i)
            for idxs in bycomp.values():
                d, nb = group_stats(v, idxs)
                if d > B:
                    extra += sum(v[i]["nb"] for i in idxs if v[i]["span"] <= a.maxrun)
        print("   %-8.0f %14d %13.1f%%" % (B, extra, 100.0*extra/surv if surv else 0))

    print("\n== variant B: proximity merge (component-independent), on top of %.0f cm ==" % a.maxrun)
    print("   %-8s %-8s %14s %14s" % ("merge_d", "bound", "extra_removed", "%of survivors"))
    for d in mds:
        groups_cache = {k: merge_groups(v, d) for k, v in passes.items()}
        for B in bounds:
            extra = 0
            for k, v in passes.items():
                for idxs in groups_cache[k]:
                    dd, nb = group_stats(v, idxs)
                    if dd > B:
                        extra += sum(v[i]["nb"] for i in idxs if v[i]["span"] <= a.maxrun)
            print("   %-8g %-8.0f %14d %13.1f%%" % (d, B, extra, 100.0*extra/surv if surv else 0))

    print("\n== variant D: co-location with a run the %.0f cm bound already removed ==" % a.maxrun)
    print("   %-8s %14s %14s   %s" % ("merge_d", "extra_removed", "%of survivors", "passes touched"))
    for d in mds:
        extra = 0; touched = 0
        for v in passes.values():
            bad = [r for r in v if r["span"] > a.maxrun]
            if not bad: continue
            hit = 0
            for r in v:
                if r["span"] > a.maxrun: continue
                for b in bad:
                    if b["comp"] == r["comp"] and near(b["bb"], r["bb"], d):
                        extra += r["nb"]; hit += 1
                        break
            if hit: touched += 1
        print("   %-8g %14d %13.1f%%   %d" % (d, extra, 100.0*extra/surv if surv else 0, touched))

    print("\n== variant E: transitive merge WITHIN a component, then the SAME %.0f cm bound ==" % a.maxrun)
    print("   the recommended form: it adds no second threshold, it makes the existing")
    print("   bound see the whole ghost instead of one fragment of it.")
    print("   %-8s %14s %14s   %s" % ("merge_d", "extra_removed", "%of survivors", "groups_over_bound"))
    for d in (1.0, 3.0, 5.0, 8.0, 10.0, 15.0):
        extra = 0; ng = 0
        for v in passes.values():
            for idxs in merge_groups(v, d, same_comp=True):
                dd, nb = group_stats(v, idxs)
                if dd > a.maxrun:
                    add = sum(v[i]["nb"] for i in idxs if v[i]["span"] <= a.maxrun)
                    if add: ng += 1
                    extra += add
        print("   %-8g %14d %13.1f%%   %d" % (d, extra, 100.0*extra/surv if surv else 0, ng))

    if a.cid is not None:
        print("\n== cluster cid=%d, final pass runs (longest first) ==" % a.cid)
        for k, v in passes.items():
            if k[0] != a.cid:
                continue
            print("  apa=%d face=%d  (%d runs)" % (k[2], k[3], len(v)))
            print("   %-4s %-5s %-6s %-9s %-9s %s" % ("k", "comp", "nb", "span_cm", "verdict", "bb y / z"))
            for r in sorted(v, key=lambda r: -r["span"])[:15]:
                bb = r["bb"]
                print("   %-4d %-5d %-6d %-9.1f %-9s y %.1f-%.1f  z %.1f-%.1f" %
                      (r["k"], r["comp"], r["nb"], r["span"],
                       "REMOVED" if r["span"] > a.maxrun else "kept",
                       bb[2], bb[3], bb[4], bb[5]))


if __name__ == "__main__":
    main()
