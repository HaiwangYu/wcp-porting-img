#!/usr/bin/env python3
"""doc pdhd/08 -- tag flips between two PDHD PR arms, as a SET census.

A count census hides the interesting case: doc pdvd/100 saw TGM move by +2 on the
count while 27.5 % of events changed which clusters were tagged.  This reports the
SET of (event, cluster) tagged in each arm and the symmetric difference, so a
"no change" verdict means the same objects, not the same number of them.

Cluster ids are the tagger's own, stable across arms here because the doc-08 knobs
change only the retiled SHADOW cloud, never the live clustering the pctree carries.

Usage: d08_tag_flips.py <base_tag> <arm_tag> [run6=029107] [work_dir]

`work_dir` lets the same census run on PDVD (doc pdhd/08 sec 9.2):
  d08_tag_flips.py d08pv30off d08pv30on 039349 ../pdvd/work
PDVD's stage logs `CheckSTM: cluster N -> STM= TGM=` where PDHD's logs
`TaggerCheckSTM: ...`, so the regex takes an optional `Tagger` prefix.  It cannot
swallow TaggerCheckTGM/FC: those spell a different component and carry their own
STM-free lines.
"""
import sys, os, re, glob

RE_STM = re.compile(r"(?:Tagger)?CheckSTM: cluster (\d+) . STM=(\d) TGM=(\d)")
RE_TGM = re.compile(r"TaggerCheckTGM: cluster (\d+) . TGM=([tf])")
RE_FC  = re.compile(r"TaggerCheckFC: cluster (\d+) . FC=([tf01])")

PDHD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.path.join(PDHD, "work")


def read(tag, run6):
    global W
    out = {"STM": set(), "TGM": set(), "FC": set()}
    evts = set()
    for d in sorted(glob.glob(os.path.join(W, "%s_*_%s" % (run6, tag)))):
        e = os.path.basename(d).split("_")[1]
        logs = glob.glob(os.path.join(d, "wct_pr_*.log"))
        if not logs:
            continue
        evts.add(e)
        for line in open(logs[0], errors="replace"):
            m = RE_STM.search(line)
            if m:
                if m.group(2) == "1": out["STM"].add((e, int(m.group(1))))
                if m.group(3) == "1": out["TGM"].add((e, int(m.group(1))))
                continue
            m = RE_TGM.search(line)
            if m and m.group(2) == "t":
                out["TGM"].add((e, int(m.group(1)))); continue
            m = RE_FC.search(line)
            if m and m.group(2) in ("t", "1"):
                out["FC"].add((e, int(m.group(1))))
    return out, evts


def main():
    base, arm = sys.argv[1], sys.argv[2]
    run6 = sys.argv[3] if len(sys.argv) > 3 else "029107"
    if len(sys.argv) > 4:
        globals()["W"] = os.path.abspath(sys.argv[4])
    print("work root: %s" % W)
    A, ea = read(base, run6)
    B, eb = read(arm, run6)
    common = ea & eb
    if ea != eb:
        print("WARNING: event sets differ -- base %d, arm %d, comparing the %d in common"
              % (len(ea), len(eb), len(common)))
    print("%-5s %8s %8s %8s %8s %8s   %s" %
          ("tag", "base", "arm", "gained", "lost", "same", "events with any flip"))
    for k in ("TGM", "STM", "FC"):
        a = {x for x in A[k] if x[0] in common}
        b = {x for x in B[k] if x[0] in common}
        gained, lost = b - a, a - b
        flipev = sorted({x[0] for x in gained | lost}, key=int)
        print("%-5s %8d %8d %8d %8d %8d   %s" %
              (k, len(a), len(b), len(gained), len(lost), len(a & b),
               ("%d/%d: %s" % (len(flipev), len(common), ",".join(flipev[:12]))) if flipev else "none"))
        # NOT truncated: a printed subset invites set arithmetic over a
        # truncated list, which silently gives the wrong answer (this bit doc
        # pdhd/08 once, on an "objects lost in every arm" intersection).
        for lab, s in (("+", gained), ("-", lost)):
            for e, c in sorted(s, key=lambda x: (int(x[0]), x[1])):
                print("        %s evt %s cluster %d" % (lab, e, c))


if __name__ == "__main__":
    main()
