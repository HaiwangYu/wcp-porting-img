#!/usr/bin/env python3
"""doc pdhd/08 sec 8 -- score the hand labels against EVERY arm, not just cap 10.

The scan sheet was built from `d08cap10`'s flips, so the item population is
cap10-selected: an arm that flips fewer of these items automatically looks more
like the baseline, and an arm's score here is NOT its score on a population
chosen for it.  What this DOES answer is the question the scan was for -- on the
objects the owner could actually judge, is a given arm's verdict right? -- and
whether a larger cap keeps the correct flips while dropping the wrong ones.

Label -> truth mapping is copied from score_d08_scan.py (pre-registered):
`STM` and `FRAG -> STM` mean the object stops, everything else means it does not;
MESSY / UNCLEAR are unscorable.

Repro:
  python3 docs/scripts/d08_score_arms.py --tag d08flip0
"""
import argparse, csv, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PDHD = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(PDHD, "work")
KEY = os.path.join(PDHD, "docs", "scan", "d08_stm_flip_key.tsv")
RUN6 = "029107"
ARMS = ["d08goff", "d08cap10", "d08cap20b", "d08cap40", "d08mrg1", "d08mrg3",
        "d08mrg5", "d08both"]


def stm_tagged(tag):
    s, evts = set(), set()
    for d in sorted(glob.glob(os.path.join(WORK, "%s_*_%s" % (RUN6, tag)))):
        e = os.path.basename(d).split("_")[1]
        lg = glob.glob(os.path.join(d, "wct_pr_*.log"))
        if not lg:
            continue
        evts.add(e)
        for line in open(lg[0], errors="replace"):
            m = re.search(r"TaggerCheckSTM: cluster (\d+) . STM=(\d) TGM=(\d)", line)
            if m and m.group(2) == "1":
                s.add((e, int(m.group(1))))
    return s, evts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="d08flip0")
    a = ap.parse_args()
    labels = json.load(open(os.path.join(WORK, "d08_scan_labels", a.tag,
                                         "labels.json")))["labels"]
    with open(KEY) as fh:
        key = {(r["event"], int(r["cluster"])): r
               for r in csv.DictReader([l for l in fh if not l.startswith("#")],
                                       delimiter="\t")}
    tagged, nev = {}, {}
    for arm in ARMS:
        tagged[arm], ev = stm_tagged(arm)
        nev[arm] = len(ev)
        if len(ev) != 30:
            print("  ! %s has %d events, not 30 -- excluded" % (arm, len(ev)))
    arms = [x for x in ARMS if nev[x] == 30]

    items = []
    for k, rec in sorted(labels.items()):
        e, cl = k.split("/")[0], int(k.split("/")[1])
        if rec["label"] in ("MESSY", "UNCLEAR"):
            continue
        if key[(e, cl)]["partition_moved"] == "1":
            continue
        items.append((e, cl, rec["label"] == "STM", rec["choice"],
                      key[(e, cl)]["direction"], key[(e, cl)]["core_all_caps"] == "1"))
    print("scorable items: %d (of %d labelled, %d in the sheet)\n"
          % (len(items), len(labels), len(key)))

    print("%-11s %7s   %-28s %s" % ("arm", "correct", "gained-tag items", "lost-tag items"))
    for arm in arms:
        ok = [((e, cl) in tagged[arm]) == truth for e, cl, truth, _, _, _ in items]
        g = [((e, cl) in tagged[arm]) == truth
             for e, cl, truth, _, d, _ in items if d == "gained"]
        l = [((e, cl) in tagged[arm]) == truth
             for e, cl, truth, _, d, _ in items if d == "lost"]
        print("%-11s %3d/%-3d   %d/%-26d %d/%d"
              % (arm, sum(ok), len(ok), sum(g), len(g), sum(l), len(l)))

    print("\nper item (T = the arm's verdict matches the owner's label):")
    print("  %-4s %-4s %-10s %-7s %-5s %s"
          % ("evt", "cl", "label", "dir", "core", "  ".join("%-9s" % x for x in arms)))
    for e, cl, truth, choice, d, core in items:
        cells = ["T" if (((e, cl) in tagged[arm]) == truth) else "." for arm in arms]
        print("  %-4s %-4d %-10s %-7s %-5s %s"
              % (e, cl, choice, d, "CORE" if core else "", 
                 "  ".join("%-9s" % c for c in cells)))


if __name__ == "__main__":
    main()
