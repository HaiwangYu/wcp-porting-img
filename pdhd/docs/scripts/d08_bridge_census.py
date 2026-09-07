#!/usr/bin/env python3
"""doc pdhd/08 stage 1a -- the bridge census.

Parses the BRIDGE lines emitted by ImproveCluster_1::hack_activity_improved under
`-S retile_bad_blob_report=true` and answers ONE question:

    when hack_activity_improved invents a bridge across a gap in the cluster's
    shortest path, does that bridge actually FABRICATE activity, or is it riding
    on activity that already existed?

It matters because the paint at improvecluster_1.cxx:591 only writes into cells
that are still empty, and get_activity_improved has already admitted dead
channels within 20 cm of the cluster's own 2-D points.  If long bridges mostly
land on already-admitted cells, a length cap on the gap would sever legitimate
dead-region bridging and buy nothing, and the knob belongs elsewhere.

Per bridge the C++ reports four cell counts:
  new     cells this bridge painted (nothing was there) -- the FOOTPRINT it
          added to the activity map, and the honest measure of fabrication
  sprior  cells already painted by a bridge.  CAVEAT: this counts a bridge
          re-covering ITSELF as well as the `temp` call retracing the `orig`
          call's ghost -- consecutive interpolated points are 0.3 cm apart and
          each paints a 7x7 disc, so the discs overlap heavily.  Read it as
          re-paint effort, NOT as extra footprint.
  sreal   cells that already held charge            -> bridge was redundant
  sdead   cells that already held the dead sentinel -> dead admission covered it

The question "is a length cap right" is answered by `new` against `sreal+sdead`:
a bridge whose cells were already covered by charge or by an admitted dead
channel was doing no harm, and capping it would only lose legitimate bridging.

Per-segment detail is the 12 LONGEST bridges of each call, so the cap simulation
below is exact for any cap at or above the 12th-longest gap of every call -- i.e.
exact where a cap would act.

Usage: d08_bridge_census.py <log> [<log> ...] [--tsv out.tsv]
"""
import re, sys, argparse, statistics

RE_HEAD = re.compile(
    r"BRIDGE cid=(?P<cid>-?\d+) ident=(?P<ident>-?\d+) apa=(?P<apa>\d+) face=(?P<face>\d+) "
    r"which=(?P<which>\w*) npath=(?P<npath>\d+) npath_face=(?P<npf>\d+) nbridge=(?P<nbridge>\d+) "
    r"capped=(?P<capped>\d+) new_cells=(?P<new>\d+) skip_real=(?P<sreal>\d+) "
    r"skip_dead=(?P<sdead>\d+) skip_prior=(?P<sprior>\d+)")
RE_SEG = re.compile(
    r"seg (?P<k>\d+): gap_cm=(?P<gap>-?[\d.]+) ncount=(?P<ncount>\d+) new=(?P<new>\d+) "
    r"sprior=(?P<sprior>\d+) sreal=(?P<sreal>\d+) sdead=(?P<sdead>\d+) new_frac=(?P<frac>-?[\d.]+)")


def parse(path):
    calls, segs = [], []
    for line in open(path, errors="replace"):
        m = RE_HEAD.search(line)
        if not m:
            continue
        c = {k: (v if k == "which" else int(v)) for k, v in m.groupdict().items()}
        c["log"] = path
        calls.append(c)
        for s in RE_SEG.finditer(line):
            d = s.groupdict()
            segs.append(dict(cid=c["cid"], ident=c["ident"], apa=c["apa"], face=c["face"],
                             which=c["which"], k=int(d["k"]), gap=float(d["gap"]),
                             ncount=int(d["ncount"]), new=int(d["new"]),
                             sprior=int(d["sprior"]), sreal=int(d["sreal"]),
                             sdead=int(d["sdead"]), log=path))
    return calls, segs


def pct(xs, q):
    if not xs:
        return 0.0
    xs = sorted(xs)
    i = min(len(xs) - 1, int(q * len(xs)))
    return xs[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--tsv")
    ap.add_argument("--cid", type=int, help="detail for one cluster id")
    a = ap.parse_args()

    calls, segs = [], []
    for p in a.logs:
        c, s = parse(p)
        calls += c
        segs += s
    if not calls:
        sys.exit("no BRIDGE lines found -- was -S retile_bad_blob_report=true set?")

    tot = lambda k: sum(c[k] for c in calls)
    fab = tot("new") + tot("sprior")
    ride = tot("sreal") + tot("sdead")
    print("== whole-arm totals over %d BRIDGE calls (%d with a bridge) ==" %
          (len(calls), sum(1 for c in calls if c["nbridge"])))
    print("  bridges                    %d" % tot("nbridge"))
    print("  cells NEWLY PAINTED        %d   <-- the fabricated footprint" % tot("new"))
    print("  cells re-painted (sprior)  %d   (effort, NOT footprint: a bridge re-covers itself)"
          % tot("sprior"))
    print("  cells already charged      %d" % tot("sreal"))
    print("  cells already dead-flagged %d" % tot("sdead"))
    d2 = tot("new") + tot("sreal") + tot("sdead")
    if d2:
        print("  new_frac (new / touched)   %.3f" % (tot("new") / d2))
    for w in ("orig", "temp"):
        sub = [c for c in calls if c["which"] == w]
        if not sub:
            continue
        r = sum(c["sreal"] for c in sub) + sum(c["sdead"] for c in sub)
        print("    which=%-5s bridges %6d  new %8d  re-paint %8d  already-covered %8d"
              % (w, sum(c["nbridge"] for c in sub), sum(c["new"] for c in sub),
                 sum(c["sprior"] for c in sub), r))

    gaps = [s["gap"] for s in segs]
    print("\n== gap length of the reported (longest-12-per-call) bridges: n=%d ==" % len(gaps))
    if gaps:
        print("  p50 %.2f  p90 %.2f  p95 %.2f  p99 %.2f  max %.2f cm"
              % (pct(gaps, .5), pct(gaps, .9), pct(gaps, .95), pct(gaps, .99), max(gaps)))

    print("\n== is a LENGTH cap the right knob?  cells by gap band ==")
    print("  new_frac = new / (new + sreal + sdead): the share of the cells a bridge")
    print("  touched that did not already exist.  sprior excluded (self-overlap).")
    print("  %-14s %6s %10s %10s %10s %10s %9s" %
          ("gap band (cm)", "nseg", "new", "sprior", "sreal", "sdead", "new_frac"))
    bands = [(0, 1), (1, 3), (3, 5), (5, 10), (10, 20), (20, 30), (30, 60), (60, 1e9)]
    for lo, hi in bands:
        sub = [s for s in segs if lo <= s["gap"] < hi]
        if not sub:
            continue
        n = sum(s["new"] for s in sub); sp = sum(s["sprior"] for s in sub)
        sr = sum(s["sreal"] for s in sub); sd = sum(s["sdead"] for s in sub)
        d = n + sp + sr + sd
        d2 = n + sr + sd
        print("  %-14s %6d %10d %10d %10d %10d %9.3f" %
              ("%g-%g" % (lo, hi if hi < 1e9 else 999), len(sub), n, sp, sr, sd,
               n / d2 if d2 else 0.0))

    print("\n== what a cap on the gap would prevent ==")
    print("  A capped bridge stops painting: the arm loses exactly its `new` cells.")
    print("  Its sreal/sdead cells already held charge or a dead sentinel, so the")
    print("  bridge's write there was already a no-op and the cap costs nothing on")
    print("  them.  The real cost of a cap is downstream connectivity, not cells.")
    print("  %-8s %9s %8s %18s %14s" %
          ("cap_cm", "nseg_cut", "%bridges", "new_cells_cut", "already_covered"))
    tot_new_arm = tot("new")
    nbr = tot("nbridge")
    for cap in (3, 5, 10, 15, 20, 30, 40, 60):
        sub = [s for s in segs if s["gap"] > cap]
        f = sum(s["new"] for s in sub)
        r = sum(s["sreal"] + s["sdead"] for s in sub)
        print("  %-8g %9d %8.2f %18s %14d" %
              (cap, len(sub), 100.0 * len(sub) / nbr if nbr else 0,
               "%d (%.0f%% of arm)" % (f, 100.0 * f / tot_new_arm if tot_new_arm else 0), r))

    if a.cid is not None:
        print("\n== cluster cid=%d ==" % a.cid)
        for c in [c for c in calls if c["cid"] == a.cid]:
            print("  apa=%d face=%d which=%-4s npath=%d nbridge=%d new=%d sprior=%d sreal=%d sdead=%d"
                  % (c["apa"], c["face"], c["which"], c["npath"], c["nbridge"],
                     c["new"], c["sprior"], c["sreal"], c["sdead"]))
        for s in sorted([s for s in segs if s["cid"] == a.cid], key=lambda s: -s["gap"])[:20]:
            d = s["new"] + s["sprior"] + s["sreal"] + s["sdead"]
            print("    apa=%d face=%d %-4s gap=%7.2f ncount=%6d new=%7d sprior=%7d sreal=%7d sdead=%7d fab_frac=%.3f"
                  % (s["apa"], s["face"], s["which"], s["gap"], s["ncount"], s["new"],
                     s["sprior"], s["sreal"], s["sdead"],
                     (s["new"] + s["sprior"]) / d if d else 0.0))

    if a.tsv:
        with open(a.tsv, "w") as fh:
            fh.write("log\tcid\tident\tapa\tface\twhich\tk\tgap_cm\tncount\tnew\tsprior\tsreal\tsdead\n")
            for s in segs:
                fh.write("%s\t%d\t%d\t%d\t%d\t%s\t%d\t%.3f\t%d\t%d\t%d\t%d\t%d\n" %
                         (s["log"], s["cid"], s["ident"], s["apa"], s["face"], s["which"],
                          s["k"], s["gap"], s["ncount"], s["new"], s["sprior"], s["sreal"], s["sdead"]))
        print("\nwrote %s (%d segments)" % (a.tsv, len(segs)))


if __name__ == "__main__":
    main()
