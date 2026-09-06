#!/usr/bin/env python3
"""doc sbnd_xin/pr/145 -- the refusal census for the pr/129 pointing test on the
near-cross-cluster kine pool (kine_near_pointing_impact, toolkit 7c4bf46a).

READ-ONLY.  Writes only its --tsv (and its report to stdout).

Why a log parser and not a table reader: the pool's admissions reach no output
column.  `n_near` is a function-local in NeutrinoKinematics.cxx:862 and KineInfo
has no member counting it, so the INFO line is the ONLY record of what the test
examined.  It is emitted only inside the `m_kine_near_pointing_impact > 0`
branch, so a production (knob-off) arm has zero of these lines by construction --
this script needs an ARMED arm.

    kine_near_pointing_impact: seg idx=14 cluster=15 ke_mev=177.78 \
        d_vtx_cm=68.91 impact_cm=69.10 miss_deg=112.2 -> SKIP

ONE FILE PER EVENT.  Each pr_evt<ID>/ holds both wct_pr_evt<ID>.log and
stdout.log, and both carry every INFO line.  Globbing '*.log' double-counts
every candidate (feedback_log_line_count_is_not_object_count).  We read
wct_pr_evt<ID>.log only, and assert stdout.log is not also consumed.

Repro:
    ./scripts/pr145_pointing_census.py --arms work-mcp1k-d145np work-mcp2k-d145np \
        work-nuecc48-d145np work-ncpi0-d145np --tsv docs/pr/pr145-pointing-census.tsv
"""
import argparse, os, re, sys, glob
from collections import Counter

LINE = re.compile(
    r"kine_near_pointing_impact:\s+seg\s+idx=(-?\d+)\s+cluster=(-?\d+)\s+"
    r"ke_mev=(-?[\d.]+)\s+d_vtx_cm=(-?[\d.]+)\s+impact_cm=(-?[\d.]+)\s+"
    r"miss_deg=(-?[\d.]+)\s+->\s+(COUNT|SKIP)")

def rows_for_arm(arm):
    sample = os.path.basename(arm.rstrip("/")).split("-")[1]
    out, n_evt, n_missing = [], 0, 0
    for d in sorted(glob.glob(os.path.join(arm, "pr_evt*"))):
        evt = os.path.basename(d)[len("pr_evt"):]
        log = os.path.join(d, "wct_pr_evt%s.log" % evt)
        if not os.path.exists(log):
            n_missing += 1
            continue
        n_evt += 1
        with open(log, errors="replace") as fh:
            for ln in fh:
                if "kine_near_pointing_impact:" not in ln:
                    continue
                m = LINE.search(ln)
                if not m:
                    print("UNPARSED %s: %s" % (log, ln.rstrip()), file=sys.stderr)
                    continue
                idx, cl, ke, dv, imp, miss, verdict = m.groups()
                out.append(dict(sample=sample, event=evt, seg_idx=int(idx),
                                cluster=int(cl), ke_mev=float(ke),
                                d_vtx_cm=float(dv), impact_cm=float(imp),
                                miss_deg=float(miss), verdict=verdict))
    return out, n_evt, n_missing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--tsv")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()

    rows, tot_evt, tot_missing = [], 0, 0
    for arm in a.arms:
        r, n, miss = rows_for_arm(arm)
        rows += r
        tot_evt += n
        tot_missing += miss
        print("%-32s events=%-5d candidates=%-5d missing_log=%d"
              % (os.path.basename(arm.rstrip("/")), n, len(r), miss))

    if tot_missing:
        print("\nWARNING: %d event dirs had no wct_pr_evt<ID>.log" % tot_missing)
    if not rows:
        print("\nNO CANDIDATES FOUND.  Is this arm actually armed?  The line is "
              "emitted only when kine_near_pointing_impact > 0.")
        return 1

    skip = [r for r in rows if r["verdict"] == "SKIP"]
    cnt  = [r for r in rows if r["verdict"] == "COUNT"]
    evts_touched = len({(r["sample"], r["event"]) for r in rows})
    evts_refused = len({(r["sample"], r["event"]) for r in skip})

    print("\n==== EXPOSURE ====")
    print("events in arms                 %d" % tot_evt)
    print("events reaching the test       %d  (%.2f%% of the arm)"
          % (evts_touched, 100.0 * evts_touched / max(tot_evt, 1)))
    print("candidates examined            %d" % len(rows))
    print("  -> COUNT (admitted)          %d" % len(cnt))
    print("  -> SKIP  (refused)           %d" % len(skip))
    print("events losing >=1 candidate    %d  (%.2f%% of the arm)"
          % (evts_refused, 100.0 * evts_refused / max(tot_evt, 1)))
    print("\nrefused KE   sum   %10.1f MeV" % sum(r["ke_mev"] for r in skip))
    print("admitted KE  sum   %10.1f MeV" % sum(r["ke_mev"] for r in cnt))

    if skip:
        ke = sorted(r["ke_mev"] for r in skip)
        def q(p):
            return ke[min(len(ke) - 1, int(p * len(ke)))]
        print("refused KE   median %8.1f   p90 %8.1f   max %8.1f MeV"
              % (q(0.50), q(0.90), ke[-1]))
        bands = Counter()
        for r in skip:
            k = r["ke_mev"]
            bands["  <  50" if k < 50 else "  50-100" if k < 100 else
                  " 100-200" if k < 200 else " 200-500" if k < 500 else
                  " >= 500"] += 1
        print("\nrefused KE distribution:")
        for b in ["  <  50", "  50-100", " 100-200", " 200-500", " >= 500"]:
            if bands[b]:
                print("   %s MeV  %5d" % (b, bands[b]))

        print("\n==== TOP %d REFUSALS BY REFUSED KE (the blind-scan set) ====" % a.top)
        print("%-9s %-8s %6s %8s %9s %9s %9s" %
              ("sample", "event", "seg", "ke_mev", "d_vtx_cm", "impact_cm", "miss_deg"))
        for r in sorted(skip, key=lambda r: -r["ke_mev"])[:a.top]:
            print("%-9s %-8s %6d %8.1f %9.2f %9.2f %9.1f" %
                  (r["sample"], r["event"], r["seg_idx"], r["ke_mev"],
                   r["d_vtx_cm"], r["impact_cm"], r["miss_deg"]))

    if a.tsv:
        cols = ["sample", "event", "seg_idx", "cluster", "ke_mev",
                "d_vtx_cm", "impact_cm", "miss_deg", "verdict"]
        with open(a.tsv, "w") as fh:
            fh.write("# doc pr/145 -- kine_near_pointing_impact refusal census\n")
            fh.write("\t".join(cols) + "\n")
            for r in sorted(rows, key=lambda r: (r["sample"], r["event"], r["seg_idx"])):
                fh.write("\t".join(str(r[c]) for c in cols) + "\n")
        print("\nwrote %s (%d rows)" % (a.tsv, len(rows)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
