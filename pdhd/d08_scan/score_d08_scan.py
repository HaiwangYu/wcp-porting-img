#!/usr/bin/env python3
"""Score the doc-08 STM-flip hand scan.  Forked BY DUPLICATION from
pdhd/stm_scan/score_stm_scan.py, which is untouched.

THIS script reads the answer key; the viewer reads it only when you press REVEAL,
and records that it did.

WHAT IS BEING DECIDED
  retile_hack_max_bridge = 10 cm removes every Steiner ghost beyond 30 cm and
  leaves the TGM tagged set untouched, but moves 45 of 174 STM tags (doc pdhd/08
  sec 6, 8).  For each moved object the human says what the object actually is;
  an arm is right on that object when its tag agrees with the human:

      arm correct  <=>  (human verdict is STM)  ==  (arm tagged the cluster)

  MESSY and UNCLEAR are unscored and reported as a rate -- a high rate is itself a
  result, because it means the sample cannot decide.

THE ACCEPTANCE BAR, fixed here BEFORE any label exists, and yours to overrule:

  1. The cap arm must agree with the human on STRICTLY MORE scored items than the
     baseline.  A tie is not a reason to change production.
  2. Of the 6 objects that lose their tag under EVERY cap value (the sec 8 core),
     a MAJORITY must be THRU / FRAG -> THRU -- i.e. the cap is removing tags that
     were wrong.  If most of those 6 are real stoppers, the cap is destroying
     genuine support and the value must come down even if clause 1 passes.
  3. Blind and REVEALED labels are reported separately.  If they disagree in
     direction, the BLIND set governs; revealed labels are diagnostic only.
  4. partition_moved items (2 of 45) are reported separately and excluded from
     clause 1: for those two the two arms do not even agree on which points the
     cluster owns, so "the same object" is not well defined.

Usage: python3 score_d08_scan.py [--tag d08flip0]
"""
import argparse, csv, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PDHD = os.path.dirname(HERE)
WORK = os.path.join(PDHD, "work")
KEY = os.path.join(PDHD, "docs", "scan", "d08_stm_flip_key.tsv")
RUN6 = "029107"
BASE, KNOB = "d08goff", "d08cap10"
KNOWN = {"STM", "THRU", "MESSY", "UNCLEAR"}


def load_key():
    with open(KEY) as fh:
        rows = list(csv.DictReader([l for l in fh if not l.startswith("#")], delimiter="\t"))
    return {(r["event"], int(r["cluster"])): r for r in rows}


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="d08flip0")
    a = ap.parse_args()
    lf = os.path.join(WORK, "d08_scan_labels", a.tag, "labels.json")
    if not os.path.isfile(lf):
        sys.exit("no labels yet: %s" % lf)
    labels = json.load(open(lf))["labels"]
    key = load_key()
    A, B = stm_tagged(BASE), stm_tagged(KNOB)

    scored = dict(base=0, knob=0, n=0)
    unscored = 0
    blind = dict(base=0, knob=0, n=0)
    revealed = dict(base=0, knob=0, n=0)
    core = []
    moved = []
    bydir = {"gained": dict(base=0, knob=0, n=0), "lost": dict(base=0, knob=0, n=0)}
    partial_n = 0

    for k, rec in sorted(labels.items()):
        e, cl = k.split("/")[0], int(k.split("/")[1])
        kr = key.get((e, cl))
        if kr is None:
            sys.exit("label %s is not in the key -- wrong --tag, or a stale sheet?" % k)
        lab = rec.get("label")
        if lab not in KNOWN:
            sys.exit("unrecognised label %r on %s -- refusing to fold it into THRU" % (lab, k))
        if rec.get("partial"):
            partial_n += 1
        if kr["core_all_caps"] == "1":
            core.append((e, cl, rec.get("choice"), kr["direction"]))
        if lab in ("MESSY", "UNCLEAR"):
            unscored += 1
            continue
        truth = (lab == "STM")
        ok_base = ((e, cl) in A) == truth
        ok_knob = ((e, cl) in B) == truth
        tgt = revealed if rec.get("revealed_before_label") else blind
        for d in (tgt,):
            d["n"] += 1; d["base"] += ok_base; d["knob"] += ok_knob
        if kr["partition_moved"] == "1":
            moved.append((e, cl, rec.get("choice"), ok_base, ok_knob))
            continue                       # clause 4: excluded from the headline
        scored["n"] += 1
        scored["base"] += ok_base
        scored["knob"] += ok_knob
        d = bydir[kr["direction"]]
        d["n"] += 1; d["base"] += ok_base; d["knob"] += ok_knob

    n_items = len(key)
    print("== doc pdhd/08 STM-flip scan, tag=%s ==" % a.tag)
    print("labelled %d of %d;  unscored (MESSY+UNCLEAR) %d;  fragments (partial) %d"
          % (len(labels), n_items, unscored, partial_n))
    if scored["n"] == 0:
        print("nothing scored yet."); return
    n_moved_sheet = sum(1 for r in key.values() if r["partition_moved"] == "1")
    print("\n-- clause 1: agreement with the human, excluding moved-partition items "
          "(%d scored of %d in the sheet) --" % (len(moved), n_moved_sheet))
    print("   %-28s %s" % ("baseline (knobs off)", "%d / %d" % (scored["base"], scored["n"])))
    print("   %-28s %s" % ("cap 10 cm", "%d / %d" % (scored["knob"], scored["n"])))
    d = scored["knob"] - scored["base"]
    print("   net %+d  ->  %s" % (d, "PASSES clause 1" if d > 0 else
                                  "does NOT pass clause 1 (needs strictly > 0)"))
    for k2 in ("gained", "lost"):
        s = bydir[k2]
        if s["n"]:
            print("     tags the cap %-7s : base %d/%d, cap %d/%d"
                  % (k2, s["base"], s["n"], s["knob"], s["n"]))

    print("\n-- clause 2: the 6 objects that lose their tag under EVERY cap value --")
    if not core:
        print("   none labelled yet")
    else:
        thru = sum(1 for c in core if c[2] in ("THRU", "FRAG_THRU"))
        stm = sum(1 for c in core if c[2] in ("STM", "FRAG_STM"))
        for e, cl, ch, dr in core:
            print("     evt %-3s cl %-4d  %-10s (%s)" % (e, cl, ch, dr))
        print("   THRU-like %d, STM-like %d of %d labelled  ->  %s"
              % (thru, stm, len(core),
                 "PASSES clause 2" if thru > stm else
                 "does NOT pass clause 2 -- the cap is removing real stoppers"
                 if stm > thru else "tied; not decided"))

    print("\n-- clause 3: blind vs revealed --")
    for nm, s in (("blind", blind), ("revealed", revealed)):
        if s["n"]:
            print("   %-9s n=%-3d base %d, cap %d  (net %+d)"
                  % (nm, s["n"], s["base"], s["knob"], s["knob"] - s["base"]))
    if blind["n"] and revealed["n"]:
        db = blind["knob"] - blind["base"]
        dr = revealed["knob"] - revealed["base"]
        if (db > 0) != (dr > 0):
            print("   *** blind and revealed DISAGREE in direction -- the blind set governs ***")

    print("\n-- clause 4: the 2 items whose cluster partition moved between arms --")
    for e, cl, ch, ob, ok in moved:
        print("   evt %-3s cl %-4d %-10s base_ok=%s cap_ok=%s" % (e, cl, ch, ob, ok))
    if not moved:
        print("   none labelled yet")


if __name__ == "__main__":
    main()
