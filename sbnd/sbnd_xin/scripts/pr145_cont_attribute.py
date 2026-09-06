#!/usr/bin/env python3
"""doc sbnd_xin/pr/145 item 3b -- attribute each rest-term charge to the site
that admitted it, and say why flag_reduce did or did not fire.

READ-ONLY.  Writes only its --tsv.

THE QUESTION.  NeutrinoKinematics.cxx:331-347 already carries a
particle-continuation detector, `flag_reduce`, and :375-388 already undoes the
rest term the previous segment was charged when it fires.  doc 144 sec 14.2.1
found 21 split-muon candidates of which 6 pay a spurious rest mass.  So this is
not a missing rule -- it is an existing mechanism failing on 6 cases, and the
job is to NAME the escape rather than guess it.

THE FOUR CANDIDATE ESCAPES, all separable from the kine_cont log lines:
  sign      -- `curr_pdg == prev_pdg` is SIGNED, so 13 vs -13 never matches and
               the mu<->pi clause covers only +211/+13
  pool      -- the rest term is charged at FOUR independent sites but the
               reduction exists at only ONE (the BFS).  push_shower_kine (:230),
               kine_count_orphan_tracks (:615), kine_count_guard_freed (:784)
               and kine_count_near_cross_cluster (:894) have no reduction at all
  visited   -- the `used_vertices.count(curr_vtx)` early-continue at :329 skips
               the whole reduction block
  genuine   -- two real particles; no defect

A fill_kine_tree call is one block ending at its kine_excluded_census line; an
event can host several, so we keep the block whose Enu matches the calib dump --
the one that actually produced the output (feedback_same_source_dump_fields:
match the layer you are grading, do not assume there is only one).

Repro:
    ./scripts/pr145_cont_attribute.py --tag d145cont2 \
        --census docs/pr/pr145-splitcensus.tsv --tsv docs/pr/pr145-contattr.tsv
"""
import argparse, glob, json, os, re, sys

RE_CHARGE = re.compile(r"kine_cont: CHARGE seg=(-?\d+) pdg=(-?\d+) rest_mev=(-?[\d.]+) ke_mev=(-?[\d.]+)")
RE_CHARGE_S = re.compile(r"kine_cont: CHARGE_SHOWER start_seg=(-?\d+) pdg=(-?\d+) rest_mev=(-?[\d.]+) ke_mev=(-?[\d.]+)")
RE_TEST = re.compile(r"kine_cont: TEST vtx=(-?\d+) prev_seg=(-?\d+) prev_pdg=(-?\d+) curr_seg=(-?\d+) curr_pdg=(-?\d+) is_shower=(\d) already_used=(\d) -> (\w+)")
RE_RED = re.compile(r"kine_cont: REDUCE vtx=(-?\d+) prev_seg=(-?\d+) prev_pdg=(-?\d+) rest_mev=(-?[\d.]+)")
RE_SKIP = re.compile(r"kine_cont: SKIP_VISITED vtx=(-?\d+) prev_seg=(-?\d+) prev_pdg=(-?\d+)")
RE_POOL = re.compile(r"(kine_count_orphan_tracks|kine_count_guard_freed|kine_count_near_cross_cluster): COUNT seg idx=(-?\d+)")
RE_CENSUS = re.compile(r"kine_excluded_census: Enu=([\d.]+)")

POOL_SHORT = {"kine_count_orphan_tracks": "orphan",
              "kine_count_guard_freed": "guard_freed",
              "kine_count_near_cross_cluster": "near_cross"}

def blocks(log):
    """Split the log into fill_kine_tree blocks, each ending at its census line."""
    cur, out = [], []
    with open(log, errors="replace") as fh:
        for ln in fh:
            if "kine_cont:" in ln or "COUNT seg idx=" in ln or "kine_excluded_census:" in ln:
                cur.append(ln)
                m = RE_CENSUS.search(ln)
                if m:
                    out.append((float(m.group(1)), cur))
                    cur = []
    return out

def analyse(lines):
    """Return per-charge rows with the admitting site, plus the reduce/test facts."""
    pool_of = {}
    for ln in lines:
        m = RE_POOL.search(ln)
        if m:
            pool_of[int(m.group(2))] = POOL_SHORT[m.group(1)]
    charges, tests, reduces, skips = [], [], [], []
    for ln in lines:
        m = RE_CHARGE.search(ln)
        if m:
            seg = int(m.group(1))
            charges.append(dict(kind="track", seg=seg, pdg=int(m.group(2)),
                                rest=float(m.group(3)), ke=float(m.group(4)),
                                site=pool_of.get(seg, "bfs_or_mainvtx")))
            continue
        m = RE_CHARGE_S.search(ln)
        if m:
            charges.append(dict(kind="shower", seg=int(m.group(1)), pdg=int(m.group(2)),
                                rest=float(m.group(3)), ke=float(m.group(4)),
                                site="shower"))
            continue
        m = RE_TEST.search(ln)
        if m:
            tests.append(dict(vtx=int(m.group(1)), prev_seg=int(m.group(2)), prev_pdg=int(m.group(3)),
                              curr_seg=int(m.group(4)), curr_pdg=int(m.group(5)),
                              is_shower=int(m.group(6)), used=int(m.group(7)), hit=m.group(8)))
            continue
        m = RE_RED.search(ln)
        if m:
            reduces.append(dict(vtx=int(m.group(1)), prev_seg=int(m.group(2)),
                                prev_pdg=int(m.group(3)), rest=float(m.group(4))))
            continue
        m = RE_SKIP.search(ln)
        if m:
            skips.append(dict(vtx=int(m.group(1)), prev_seg=int(m.group(2)), prev_pdg=int(m.group(3))))
    return charges, tests, reduces, skips

def verdict(charges, tests, reduces, skips):
    """Name the escape for the muon/pion rest terms this event paid."""
    mu = [c for c in charges if abs(c["pdg"]) in (13, 211)]
    if len(mu) < 2:
        return "single", "only one mu/pi rest term charged"
    non_bfs = [c for c in mu if c["site"] != "bfs_or_mainvtx"]
    # doc pr/145: a fifth escape the first taxonomy missed, found by hand-reading
    # mcp1k 407280 -- the PARENT segment carries pdg == 0 (no particle_info), so
    # the continuation test compares 0 against 13 and can never match.  Both
    # children then pay a full rest mass.
    for t in tests:
        if t["prev_pdg"] == 0 and abs(t["curr_pdg"]) in (13, 211) and t["hit"] != "CONT":
            return "untyped", ("parent seg=%d has pdg=0, so the chain breaks and "
                               "curr_pdg=%d pays unreduced" % (t["prev_seg"], t["curr_pdg"]))
    # a TEST between two mu/pi that did not fire because the pdgs are signed differently
    for t in tests:
        if abs(t["prev_pdg"]) in (13, 211) and abs(t["curr_pdg"]) in (13, 211) and t["hit"] != "CONT":
            if t["prev_pdg"] != t["curr_pdg"]:
                return "sign", ("BFS saw prev_pdg=%d curr_pdg=%d and the signed test missed"
                                % (t["prev_pdg"], t["curr_pdg"]))
    if len(non_bfs) >= 1 and len(mu) - len(non_bfs) <= 1:
        sites = ",".join(sorted({c["site"] for c in mu}))
        return "pool", ("%d mu/pi rest terms charged at sites {%s}; the reduction "
                        "exists only in the BFS" % (len(mu), sites))
    if tests and all(t["hit"] == "CONT" for t in tests
                     if abs(t["prev_pdg"]) in (13, 211) and abs(t["curr_pdg"]) in (13, 211)) \
            and len(reduces) >= 1:
        return "reduced_ok", ("every mu/pi continuation fired and %d reduction(s) "
                              "were applied; no escape" % len(reduces))
    for s in skips:
        if abs(s["prev_pdg"]) in (13, 211):
            return "visited", ("vtx=%d already visited, so the reduction block was "
                               "skipped for prev_seg=%d" % (s["vtx"], s["prev_seg"]))
    return "unattributed", "no escape matched -- read the block by hand"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="d145cont2")
    ap.add_argument("--census", default="docs/pr/pr145-splitcensus.tsv")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    cens = {}
    for ln in open(a.census):
        if ln.startswith("#"): continue
        f = ln.rstrip("\n").split("\t")
        if f[0] == "sample": continue
        cens[(f[0], f[1])] = float(f[6])          # d_add

    rows = []
    for (sample, evt), d_add in sorted(cens.items(), key=lambda kv: -kv[1]):
        log = f"work-{sample}-{a.tag}/pr_evt{evt}/wct_pr_evt{evt}.log"
        cal = f"work-{sample}-{a.tag}/pr_evt{evt}/calib-pr-evt{evt}.json"
        if not os.path.exists(log) or not os.path.exists(cal):
            print(f"MISSING {sample} {evt}"); continue
        enu = json.load(open(cal))["kine"]["kine_reco_Enu"]
        bl = blocks(log)
        best = min(bl, key=lambda b: abs(b[0] - enu)) if bl else None
        if best is None or abs(best[0] - enu) > 0.5:
            print(f"NO MATCHING BLOCK {sample} {evt} (dump Enu={enu:.1f})"); continue
        ch, te, rd, sk = analyse(best[1])
        esc, why = verdict(ch, te, rd, sk)
        rows.append(dict(sample=sample, event=evt, d_add=d_add, escape=esc, why=why,
                         n_charge=len(ch), n_test=len(te), n_reduce=len(rd),
                         n_skipvisited=len(sk),
                         sites=";".join(f"{c['site']}:{c['pdg']}:{c['rest']:.1f}" for c in ch)))

    print("%-9s %-8s %9s %-13s %3s %3s %3s  %s" %
          ("sample", "event", "d_add", "escape", "chg", "tst", "red", "why"))
    for r in rows:
        print("%-9s %-8s %+9.1f %-13s %3d %3d %3d  %s" %
              (r["sample"], r["event"], r["d_add"], r["escape"],
               r["n_charge"], r["n_test"], r["n_reduce"], r["why"][:76]))

    print("\n==== ESCAPE TALLY (payers only, d_add > +1 MeV) ====")
    from collections import Counter
    c = Counter(r["escape"] for r in rows if r["d_add"] > 1.0)
    for k, v in c.most_common(): print("  %-14s %d" % (k, v))
    print("\n==== ESCAPE TALLY (all 21) ====")
    c = Counter(r["escape"] for r in rows)
    for k, v in c.most_common(): print("  %-14s %d" % (k, v))

    if a.tsv:
        cols = ["sample","event","d_add","escape","n_charge","n_test","n_reduce",
                "n_skipvisited","sites","why"]
        with open(a.tsv,"w") as fh:
            fh.write("# doc pr/145 item 3b -- rest-term admission sites and the flag_reduce escape\n")
            fh.write("\t".join(cols)+"\n")
            for r in rows:
                fh.write("\t".join(str(r[c]) for c in cols)+"\n")
        print("\nwrote %s (%d rows)" % (a.tsv, len(rows)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
