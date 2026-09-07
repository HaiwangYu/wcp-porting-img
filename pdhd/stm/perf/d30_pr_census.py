#!/usr/bin/env python3
"""doc 30 -- per-event CPU + memory census of a PDHD or PDVD PR arm, from what
run_pr_evt.sh already leaves on disk (no rerun).

Why a new tool and not a fork of pdvd/stm/perf/pr_perf_profile.py: that script
answers doc 28's question (stage shares of node_core_s across a 120-event PDVD
arm) and carries a PDVD-only stage list and a PNG path.  This one answers doc
30's: where the RESIDENT bytes go, per stage, on either detector, plus the
per-fit variables that set the STM stage's size.  The PDVD script is untouched.

Two instrument notes, both load-bearing:

  * `peak_rss_gb` in pr_resource_*.txt is the max over 2 s samples of VmHWM taken
    by a loop that dies with the job, so the last ~2 s (writers + teardown) can
    be unobserved: 19 % of PDHD and 55 % of PDVD jobs report LESS than the max
    `res=` in their own MEM ladder (deficits to 0.66 GB).  This tool publishes
    peak_gb = max(sampled VmHWM, max ladder res) and reports the gap.
  * `res=` in the MEM ladder is /proc/self/statm resident in KB and agrees with
    VmHWM exactly on jobs whose sampler covered the tail -- checked on the doc-30
    arms (5.99/5.99, 7.35/7.35, 1.91/1.92 GB).

Usage:
  d30_pr_census.py <work_root> <tag> [<tag> ...]        # one row per event
  d30_pr_census.py --tsv out.tsv <work_root> <tag> ...
"""
import glob
import os
import re
import sys
from collections import OrderedDict

RE_TIMING = re.compile(r"MABC timing: (.+?) took ([0-9.]+) ms \(cumulative")
RE_MEM = re.compile(r"MEM: total: size=[0-9.e+]+K, res=([0-9.e+]+)K increment: "
                    r"size=[-0-9.e+]+K, res=([-0-9.e+]+)K (.*)$")
RE_RES = re.compile(r"run=(\d+) evt=(\d+) wall_s=(\d+) peak_rss_gb=([0-9.]+) mode=(\S+) stmfit=(\d)")
RE_TIMER = re.compile(r'Timer: ([0-9.]+) wall-sec, ([0-9.]+) core-sec:\s+\((\S+)\) "(\S+)"')
RE_KEPT = re.compile(r"CreateSteinerGraph: .*kept (\d+) of (\d+) cluster")
RE_STM = re.compile(r"TaggerCheckSTM: cluster (\d+) . STM=(\d)")
# doc 30: the per-fit variables.  One line per persisted STM fit pass.
RE_PERSIST = re.compile(r"persist_stm_fit: cluster (\d+) stmfit pass=(\d+) status=(-?\d+) "
                        r"kink=(-?\d+) exit_L=([-0-9.]+) left_L=([-0-9.]+) npts=(\d+)")
RE_SAVED = re.compile(r"save_stm_fit stored (\d+) segment\(s\)")

# Stages worth a column, in pipeline order.  PDHD and PDVD differ: PDHD has no
# ClusteringUnmergeBundle by default and no TaggerCheckNeutrino (doc pdhd/03
# replaced it with CheckSTM_Michel); PDVD carries both.  Absent stages simply
# stay 0 -- but see the coverage assertion at the end, which names any stage
# that was never seen in ANY log of the arm, so a wrong list cannot pass
# silently as a column of zeros.
STAGES = [
    "loaded live", "ClusteringSwitchScope:pr", "ClusteringFlagMatchedMains:pr",
    "ClusteringUnmergeBundle:prassoc", "CreateSteinerGraph:pr", "MakeFiducialUtils:pr",
    "TaggerCheckTGM:pr", "TaggerCheckSTM:pr", "TaggerCheckFC:pr",
    "ClusteringProtectBundle:pr", "CreateSteinerGraph:prrefresh",
    "CheckSTM_Michel:pr", "TaggerCheckNeutrino:pr",
    "PdvdPrMagnifyTrackingVisitor:pr", "PrDisplayDump:pr",
    "PdvdMagnifyTrackingVisitor:pr", "done",
]
SHORT = {
    "loaded live": "load", "ClusteringSwitchScope:pr": "scope",
    "ClusteringFlagMatchedMains:pr": "flag", "ClusteringUnmergeBundle:prassoc": "unmerge",
    "CreateSteinerGraph:pr": "steiner", "MakeFiducialUtils:pr": "fv",
    "TaggerCheckTGM:pr": "tgm", "TaggerCheckSTM:pr": "stm", "TaggerCheckFC:pr": "fc",
    "ClusteringProtectBundle:pr": "protect", "CreateSteinerGraph:prrefresh": "refresh",
    "CheckSTM_Michel:pr": "michel", "TaggerCheckNeutrino:pr": "nu",
    "PdvdPrMagnifyTrackingVisitor:pr": "w_pr", "PrDisplayDump:pr": "w_disp",
    "PdvdMagnifyTrackingVisitor:pr": "w_stm", "done": "done",
}


def scan(logpath, respath):
    r = dict(ms={}, dres={}, ladder_max=0.0, node_core_s=0.0,
             nclus=0, nstm=0, nstm1=0, nfit=0, sum_npts=0, max_npts=0, nseg=0,
             load_gb=0.0, stm_gb=0.0, steiner_gb=0.0)
    with open(logpath, errors="replace") as fp:
        for line in fp:
            m = RE_TIMING.search(line)
            if m:
                r["ms"][m.group(1)] = r["ms"].get(m.group(1), 0.0) + float(m.group(2))
                continue
            m = RE_MEM.search(line)
            if m:
                res = float(m.group(1)) / 1048576.0
                r["dres"][m.group(3).strip()] = float(m.group(2)) / 1048576.0
                r["ladder_max"] = max(r["ladder_max"], res)
                continue
            m = RE_TIMER.search(line)
            if m and m.group(3).endswith("MultiAlgBlobClustering"):
                r["node_core_s"] = float(m.group(2))
                continue
            m = RE_KEPT.search(line)
            if m and not r["nclus"]:
                r["nclus"] = int(m.group(2))
                continue
            m = RE_STM.search(line)
            if m:
                r["nstm"] += 1
                r["nstm1"] += m.group(2) == "1"
                continue
            m = RE_PERSIST.search(line)
            if m:
                n = int(m.group(7))
                r["nfit"] += 1
                r["sum_npts"] += n
                r["max_npts"] = max(r["max_npts"], n)
                continue
            m = RE_SAVED.search(line)
            if m:
                r["nseg"] = int(m.group(1))
    r["load_gb"] = r["dres"].get("loaded live", 0.0)
    r["stm_gb"] = r["dres"].get("TaggerCheckSTM:pr", 0.0)
    r["steiner_gb"] = r["dres"].get("CreateSteinerGraph:pr", 0.0)
    r["vmhwm_gb"] = r["wall_s"] = -1
    r["mode"], r["stmfit"] = "?", "?"
    if respath and os.path.exists(respath):
        m = RE_RES.search(open(respath).read())
        if m:
            r["wall_s"] = int(m.group(3))
            r["vmhwm_gb"] = float(m.group(4))
            r["mode"], r["stmfit"] = m.group(5), m.group(6)
    # doc 30: the published peak is the larger of the two instruments
    r["peak_gb"] = max(r["vmhwm_gb"], r["ladder_max"])
    r["hwm_gap"] = r["peak_gb"] - r["vmhwm_gb"] if r["vmhwm_gb"] > 0 else 0.0
    return r


def main():
    argv = sys.argv[1:]
    tsv = None
    if argv and argv[0] == "--tsv":
        tsv, argv = argv[1], argv[2:]
    if len(argv) < 2:
        sys.exit(__doc__)
    root, tags = argv[0], argv[1:]
    rows = []
    seen_stages = set()
    for tag in tags:
        for d in sorted(glob.glob(os.path.join(root, "*_" + tag))):
            logs = glob.glob(os.path.join(d, "wct_pr_*.log"))
            if not logs:
                continue
            res = glob.glob(os.path.join(d, "pr_resource_*.txt"))
            r = scan(logs[0], res[0] if res else None)
            seen_stages |= set(r["ms"]) | set(r["dres"])
            r["tag"], r["event"] = tag, os.path.basename(d)[:-len(tag) - 1]
            rows.append(r)
    if not rows:
        sys.exit("no logs under %s for tags %s" % (root, tags))

    cols = (["tag", "event", "mode", "stmfit", "wall_s", "node_core_s", "vmhwm_gb",
             "peak_gb", "hwm_gap", "nclus", "nstm", "nstm1", "nfit", "nseg",
             "sum_npts", "max_npts", "load_gb", "steiner_gb", "stm_gb"]
            + ["ms_" + SHORT[s] for s in STAGES] + ["d_" + SHORT[s] for s in STAGES])
    out = [cols]
    for r in rows:
        out.append([r.get(c, "") for c in cols[:19]]
                   + ["%.1f" % r["ms"].get(s, 0.0) for s in STAGES]
                   + ["%.3f" % r["dres"].get(s, 0.0) for s in STAGES])
    if tsv:
        with open(tsv, "w") as fp:
            for row in out:
                fp.write("\t".join(str(x) for x in row) + "\n")
        print("wrote %s (%d events)" % (tsv, len(rows)))

    # per-tag summary
    print("%-12s %4s  %-6s %8s %8s %8s   %5s %5s %5s  %7s" %
          ("tag", "n", "mode", "peak_p50", "peak_max", "core_s50", "nclus", "nfit", "npts", "stm_gb50"))
    for tag in tags:
        rr = [r for r in rows if r["tag"] == tag]
        if not rr:
            continue
        def pct(key, q=0.5):
            v = sorted(x[key] for x in rr)
            return v[min(len(v) - 1, int(len(v) * q))]
        print("%-12s %4d  %-6s %8.2f %8.2f %8.1f   %5d %5d %5d  %7.2f" %
              (tag, len(rr), rr[0]["mode"], pct("peak_gb"), max(x["peak_gb"] for x in rr),
               pct("node_core_s"), pct("nclus"), pct("nfit"), pct("sum_npts"), pct("stm_gb")))

    missing = [s for s in STAGES if s not in seen_stages]
    if missing:
        print("\nNOTE: stages never seen in any log of these tags (expected for the "
              "other detector / the other mode): %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
