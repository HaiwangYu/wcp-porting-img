#!/usr/bin/env python3
"""doc pdhd/07 -- offline census of the retiler's anti-ghost filter.

Parses the three log lines that `retile_bad_blob_report=true` emits from
ImproveCluster_1/2 and answers the doc-06 sec 8.7 R0 question: how did a 26.8 cm
fabricated Steiner stretch get past a 20 cm run bound?

  BADBLOB     cid= ident= apa= face= nnew= norig= ncomp= ncomp_ss= nsup=
              legacy_rm= run_rm= nruns= maxrun_cm=   [| run i: nb= nslices=
              span_cm= craw=(x,y,z) bb=(x0,x1,y0,y1,z0,z1)]*
  BADBLOBRM   ident= apa= face= removed= npts A -> B nblobs N
  BADBLOBSKIP ident= apa= face= cached_nnew= children_on_face=

`cid` is get_cluster_id() -- the Bee / calib-dump cluster id, the key to join on
(a retile ident is NOT the Bee cluster id).  Run centres/boxes are in the RAW
drift frame (blob center_pos), not x_t0cor.

Usage:
  d07_badblob_census.py <log> [<log> ...] [--cid N] [--near y,z[,r]] [--tsv out.tsv]
"""
import re, sys, os, argparse, statistics

RE_HEAD = re.compile(
    r"BADBLOB cid=(?P<cid>-?\d+) ident=(?P<ident>-?\d+) apa=(?P<apa>\d+) face=(?P<face>\d+) "
    r"nnew=(?P<nnew>\d+) norig=(?P<norig>\d+) ncomp=(?P<ncomp>\d+) ncomp_ss=(?P<ncomp_ss>\d+) "
    r"nsup=(?P<nsup>\d+) legacy_rm=(?P<legacy_rm>\d+) run_rm=(?P<run_rm>\d+) "
    r"nruns=(?P<nruns>\d+) maxrun_cm=(?P<maxrun>-?[\d.]+)")
RE_RUN = re.compile(
    r"run (?P<i>\d+): nb=(?P<nb>\d+) nslices=(?P<nslices>\d+) span_cm=(?P<span>-?[\d.]+) "
    r"craw=\((?P<cx>-?[\d.]+),(?P<cy>-?[\d.]+),(?P<cz>-?[\d.]+)\) "
    r"bb=\((?P<x0>-?[\d.]+),(?P<x1>-?[\d.]+),(?P<y0>-?[\d.]+),(?P<y1>-?[\d.]+),(?P<z0>-?[\d.]+),(?P<z1>-?[\d.]+)\)")
RE_RM = re.compile(r"BADBLOBRM ident=(?P<ident>-?\d+) apa=(?P<apa>\d+) face=(?P<face>\d+) "
                   r"removed=(?P<removed>\d+) npts (?P<before>\d+) -> (?P<after>\d+) nblobs (?P<nblobs>\d+)")
RE_SKIP = re.compile(r"BADBLOBSKIP ident=(?P<ident>-?\d+) apa=(?P<apa>\d+) face=(?P<face>\d+) "
                     r"cached_nnew=(?P<nnew>\d+) children_on_face=(?P<nchild>\d+)")


def parse(path):
    """Return (records, skips).

    Each record is one BADBLOB census line.  ImproveCluster_2::mutate retiles a
    face TWICE -- ImproveCluster_1::mutate first (an intermediate cluster used
    only to derive the retiled path for the second activity hack), then its own
    (the cloud the Steiner build actually sees).  Both emit a census line; only
    the second is followed by BADBLOBRM.  Binding each RM line to the most
    recent census line with the same (ident, apa, face) is what separates them,
    and r["final"] marks the pass that survives.  Summing over both passes
    double-counts, so every number below is taken over final passes only.
    """
    recs, skips = [], []
    last = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            m = RE_HEAD.search(line)
            if m:
                d = {k: (float(v) if k == "maxrun" else int(v)) for k, v in m.groupdict().items()}
                d["runs"] = [{k: (int(v) if k in ("i", "nb", "nslices") else float(v))
                              for k, v in r.groupdict().items()} for r in RE_RUN.finditer(line)]
                d["final"] = False
                d["removed"] = d["npts_before"] = d["npts_after"] = d["nblobs_after"] = None
                recs.append(d)
                last[(d["ident"], d["apa"], d["face"])] = d
                continue
            m = RE_RM.search(line)
            if m:
                v = {k: int(x) for k, x in m.groupdict().items()}
                d = last.get((v["ident"], v["apa"], v["face"]))
                if d is not None and not d["final"]:
                    d["final"] = True
                    d["removed"] = v["removed"]
                    d["npts_before"], d["npts_after"] = v["before"], v["after"]
                    d["nblobs_after"] = v["nblobs"]
                continue
            m = RE_SKIP.search(line)
            if m:
                skips.append({k: int(v) for k, v in m.groupdict().items()})
    return recs, skips


def summarize(tag, recs, skips):
    fin = [r for r in recs if r["final"]]
    print(f"\n=== {tag} ===")
    if not recs:
        print("  no BADBLOB lines -- was retile_bad_blob_report=true set?")
        return
    print(f"  census lines {len(recs)}  ({len(fin)} final passes, {len(recs)-len(fin)} intermediate)"
          f"   distinct cid: {len({r['cid'] for r in fin})}")
    nnew = sum(r["nnew"] for r in fin)
    nsup = sum(r["nsup"] for r in fin)
    norig = sum(r["norig"] for r in fin)
    print(f"  original blobs -> retiled   : {norig} -> {nnew}   (x{nnew/max(1,norig):.1f})")
    print(f"  retiled blobs supported     : {nsup} ({100.0*nsup/max(1,nnew):.1f} %)"
          f"   unsupported: {nnew-nsup} ({100.0*(nnew-nsup)/max(1,nnew):.1f} %)")
    print(f"  removed  legacy vote {sum(r['legacy_rm'] for r in fin)}"
          f"   run bound {sum(r['run_rm'] for r in fin)}"
          f"   union {sum(r['removed'] for r in fin)}")
    pb, pa = sum(r["npts_before"] for r in fin), sum(r["npts_after"] for r in fin)
    print(f"  points in the retiled cloud : {pb} -> {pa}  ({100.0*(pb-pa)/max(1,pb):.1f} % removed)")
    print(f"  ncomp>1 (legacy vote fires) : {len([r for r in fin if r['ncomp']>1])}/{len(fin)}"
          f"   ncomp_ss>1: {len([r for r in fin if r['ncomp_ss']>1])}/{len(fin)}")
    runs = [rr for r in fin for rr in r["runs"]]
    if runs:
        spans = sorted((rr["span"] for rr in runs), reverse=True)
        over = [x for x in spans if x > 20]
        near = [x for x in spans if 15 <= x <= 20]
        print(f"  unsupported runs >=3 cm     : {len(runs)}   longest {spans[0]:.1f} cm"
              f"   median {statistics.median(spans):.1f} cm")
        print(f"     over the 20 cm bound     : {len(over)} (removed)"
              f"     15-20 cm, just under     : {len(near)} (KEPT)")
    kept = sum(r["nnew"] - r["removed"] for r in fin)
    kept_uns = sum(max(0, (r["nnew"] - r["removed"]) - r["nsup"]) for r in fin)
    print(f"  SURVIVING blobs             : {kept}, of which {kept_uns} "
          f"({100.0*kept_uns/max(1,kept):.1f} %) have NO support in the original cluster")
    worst = sorted(((max(0, (r["nnew"]-r["removed"])-r["nsup"]) / max(1, r["nnew"]-r["removed"]),
                     max(0, (r["nnew"]-r["removed"])-r["nsup"]), r["nnew"]-r["removed"],
                     r["cid"], r["apa"], r["face"]) for r in fin), reverse=True)
    for f, u, k, cid, apa, face in worst[:5]:
        print(f"      cid={cid:<5d} apa={apa} face={face}  kept={k:5d}  unsupported={u:5d}  ({100*f:.1f} %)")
    if skips:
        hidden = [x for x in skips if x["nchild"] > x["nnew"]]
        print(f"  BADBLOBSKIP: {len(skips)} (cached_nnew<=1); {len(hidden)} with children on the "
              f"face -> stale-cache blind spot")


def detail(recs, cid=None, near=None):
    sel = [r for r in recs if r["final"]]
    if cid is not None:
        sel = [r for r in sel if r["cid"] == cid]
    for r in sel:
        kept = r["nnew"] - r["removed"]
        print(f"\n  cid={r['cid']} ident={r['ident']} apa={r['apa']} face={r['face']}: "
              f"nnew={r['nnew']} norig={r['norig']} nsup={r['nsup']} "
              f"({100.0*r['nsup']/r['nnew']:.1f} % supported) ncomp={r['ncomp']} ncomp_ss={r['ncomp_ss']} "
              f"legacy_rm={r['legacy_rm']} run_rm={r['run_rm']} nruns={r['nruns']} maxrun={r['maxrun']:.1f} cm\n"
              f"      removed {r['removed']} -> kept {kept} blobs, {max(0,kept-r['nsup'])} of them unsupported "
              f"({100.0*max(0,kept-r['nsup'])/max(1,kept):.1f} %); points {r['npts_before']} -> {r['npts_after']}")
        for rr in r["runs"]:
            hit = ""
            if near:
                y, z, rad = near
                if abs(rr["cy"] - y) < rad and abs(rr["cz"] - z) < rad:
                    hit = "   <== near the requested (y,z)"
            print(f"      run {rr['i']}: nb={rr['nb']:4d} nslices={rr['nslices']:4d} span={rr['span']:6.1f} cm "
                  f"craw=({rr['cx']:7.1f},{rr['cy']:6.1f},{rr['cz']:6.1f}) "
                  f"x[{rr['x0']:.1f},{rr['x1']:.1f}] y[{rr['y0']:.1f},{rr['y1']:.1f}] z[{rr['z0']:.1f},{rr['z1']:.1f}]{hit}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--cid", type=int, default=None, help="print every run of this Bee cluster id")
    ap.add_argument("--near", default=None, help="y,z[,radius_cm] -- flag runs whose centre is near this")
    ap.add_argument("--tsv", default=None)
    args = ap.parse_args()
    near = None
    if args.near:
        p = [float(x) for x in args.near.split(",")]
        near = (p[0], p[1], p[2] if len(p) > 2 else 20.0)
    rows = []
    for path in args.logs:
        recs, skips = parse(path)
        summarize(os.path.basename(os.path.dirname(path)) or path, recs, skips)
        if args.cid is not None or near:
            detail(recs, args.cid, near)
        for r in recs:
            if not r["final"]:
                continue
            rows.append((os.path.basename(os.path.dirname(path)), r))
    if args.tsv:
        with open(args.tsv, "w") as fh:
            fh.write("arm\tcid\tident\tapa\tface\tnnew\tnorig\tncomp\tncomp_ss\tnsup\tlegacy_rm\trun_rm\tnruns\tmaxrun_cm\n")
            for arm, r in rows:
                fh.write("\t".join(str(x) for x in [arm, r["cid"], r["ident"], r["apa"], r["face"],
                                                    r["nnew"], r["norig"], r["ncomp"], r["ncomp_ss"], r["nsup"],
                                                    r["legacy_rm"], r["run_rm"], r["nruns"], f"{r['maxrun']:.1f}"]) + "\n")
        print(f"\nwrote {args.tsv} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
