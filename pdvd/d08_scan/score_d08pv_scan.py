#!/usr/bin/env python3
"""doc pdhd/08 sec 9.3 -- score the PDVD STM hand scan.

THE BAR IS FIXED HERE BEFORE ANY LABEL EXISTS, and it is deliberately different
from the PDHD one, because this sheet has only four flips and eight controls:

  C0  CALIBRATION (a gate on the rest).  Two parts, because a control the scanner
      calls MESSY/UNCLEAR is not evidence either way and must not silently count
      as a disagreement:
        C0a  at least 6 of the 8 controls are SCORED (labelled STM or THRU);
        C0b  the scanner agrees with the tagger on at least 80 % of those.
      Controls are the only thing that says whether a label set can carry a
      verdict at all.  If C0 fails, the flip columns below are reported but they
      decide NOTHING, and the honest report is "this scan cannot answer it".
  C1  On the 4 flips, the cap arm must be right at least as often as the
      baseline.  "At least" and not "strictly more": the round's criterion is
      that the ghost removal is bought without a tag loss the owner rejects,
      not that the cap improves the tagger.  Four items cannot show an
      improvement and are not being asked to.
  C2  If any flip is scored against the cap, it is named in full, with its
      persist_stm_fit line from both arms, because doc 08 sec 9.2 found all four
      have an essentially unchanged fit -- so a label against the cap is a
      statement about the tagger, not about the bridge.
  C3  Blind and revealed labels are reported apart, and MESSY/UNCLEAR are never
      folded into either verdict.

Usage: python3 score_d08pv_scan.py [--tag d08pvflip0]
"""
import argparse, csv, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PDVD = os.path.dirname(HERE)
WORK = os.path.join(PDVD, "work")
KEY = os.path.join(PDVD, "docs", "scan", "d08pv_stm_flip_key.tsv")
BASE, KNOB = "d08pv30off", "d08pv30on"
RUN6 = "039349"
KNOWN = {"STM", "THRU", "MESSY", "UNCLEAR"}
RE_STM = re.compile(r"(?:Tagger)?CheckSTM: cluster (\d+) . STM=(\d) TGM=(\d)")
RE_FIT = re.compile(r"persist_stm_fit: cluster (\d+) stmfit (pass=\d+ status=\S+ "
                    r"kink=\S+ exit_L=\S+ left_L=\S+ npts=\d+)")


def tagged(tag):
    s = set()
    for d in sorted(glob.glob(os.path.join(WORK, "%s_*_%s" % (RUN6, tag)))):
        e = os.path.basename(d).split("_")[1]
        lg = glob.glob(os.path.join(d, "wct_pr_*.log"))
        if not lg:
            continue
        for line in open(lg[0], errors="replace"):
            m = RE_STM.search(line)
            if m and m.group(2) == "1":
                s.add((e, int(m.group(1))))
    return s


def fits(e, cid, tag):
    lg = glob.glob(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, tag), "wct_pr_*.log"))
    out = []
    if lg:
        for line in open(lg[0], errors="replace"):
            m = RE_FIT.search(line)
            if m and int(m.group(1)) == cid:
                out.append(m.group(2))
    return out or ["(no persist_stm_fit line)"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="d08pvflip0")
    a = ap.parse_args()
    lf = os.path.join(WORK, "d08pv_scan_labels", a.tag, "labels.json")
    if not os.path.isfile(lf):
        sys.exit("no labels yet: %s" % lf)
    labels = json.load(open(lf))["labels"]
    with open(KEY) as fh:
        key = {(r["event"], int(r["cluster"])): r
               for r in csv.DictReader([l for l in fh if not l.startswith("#")],
                                       delimiter="\t")}
    A, B = tagged(BASE), tagged(KNOB)

    print("== doc pdhd/08 sec 9.3 PDVD STM scan, tag=%s ==" % a.tag)
    print("labelled %d of %d" % (len(labels), len(key)))

    ctl = dict(n=0, ok=0)
    flip = dict(n=0, base=0, knob=0)
    unscored = []
    against = []
    blind = dict(n=0, base=0, knob=0)
    revealed = dict(n=0, base=0, knob=0)

    for k, rec in sorted(labels.items(), key=lambda kv: kv[1].get("scan_id", 0)):
        e, cl = k.split("/")[0], int(k.split("/")[1])
        kr = key.get((e, cl))
        if kr is None:
            sys.exit("label %s is not in the key -- wrong --tag, or a stale sheet?" % k)
        lab = rec.get("label")
        if lab not in KNOWN:
            sys.exit("unrecognised label %r on %s" % (lab, k))
        if lab in ("MESSY", "UNCLEAR"):
            unscored.append((kr["scan_id"], e, cl, kr["direction"], lab))
            continue
        truth = (lab == "STM")
        ok_base = ((e, cl) in A) == truth
        ok_knob = ((e, cl) in B) == truth
        tgt = revealed if rec.get("revealed_before_label") else blind
        tgt["n"] += 1; tgt["base"] += ok_base; tgt["knob"] += ok_knob
        if int(kr["is_flip"]):
            flip["n"] += 1; flip["base"] += ok_base; flip["knob"] += ok_knob
            if not ok_knob:
                against.append((kr["scan_id"], e, cl, kr["direction"], rec["choice"]))
        else:
            ctl["n"] += 1
            ctl["ok"] += ok_base          # both arms agree on a control by construction
            assert ok_base == ok_knob, "control %s disagrees between arms" % (k,)

    n_ctl_total = sum(1 for r in key.values() if not int(r["is_flip"]))
    print("\n-- C0 CALIBRATION: the %d control objects, which both arms agree about --"
          % n_ctl_total)
    print("   scored (STM or THRU)  %d of %d" % (ctl["n"], n_ctl_total))
    rate = (100.0 * ctl["ok"] / ctl["n"]) if ctl["n"] else 0.0
    print("   agrees with the tagger %d of %d  (%.0f %%)" % (ctl["ok"], ctl["n"], rate))
    c0a = ctl["n"] >= 6
    c0b = ctl["n"] > 0 and rate >= 80.0
    c0 = c0a and c0b
    print("   C0a %s (bar: >= 6 of %d scored)" % ("PASSES" if c0a else "FAILS", n_ctl_total))
    print("   C0b %s (bar: >= 80 %% agreement on those scored)" % ("PASSES" if c0b else "FAILS"))
    if not c0:
        print("   -> the flip columns below are REPORTED BUT DECIDE NOTHING.")

    print("\n-- C1: the 4 flips --")
    print("   baseline (knobs off)  %d / %d" % (flip["base"], flip["n"]))
    print("   cap 10 cm             %d / %d" % (flip["knob"], flip["n"]))
    c1 = flip["knob"] >= flip["base"]
    print("   %s (bar: cap >= baseline)" % ("PASSES" if c1 else "FAILS"))

    print("\n-- C2: flips scored AGAINST the cap --")
    if not against:
        print("   none")
    for sid, e, cl, d, choice in against:
        print("   item %s: evt %s cluster %d (%s), you said %s" % (sid, e, cl, d, choice))
        for arm in (BASE, KNOB):
            for line in fits(e, cl, arm):
                print("       %-12s %s" % (arm, line))
        print("       doc 08 sec 9.2: all four flips have an essentially unchanged fit,")
        print("       so a label against the cap here is a statement about the TAGGER.")

    print("\n-- C3: blind vs revealed, and the unscored --")
    print("   blind     n=%d  base %d, cap %d" % (blind["n"], blind["base"], blind["knob"]))
    print("   revealed  n=%d  base %d, cap %d" % (revealed["n"], revealed["base"], revealed["knob"]))
    if revealed["n"]:
        print("   -> blind labels govern where the two disagree.")
    for sid, e, cl, d, lab in unscored:
        print("   unscored: item %s evt %s cluster %d (%s) = %s" % (sid, e, cl, d, lab))

    print("\n== VERDICT: %s ==" % ("the scan supports keeping the cap on PDVD"
                                  if (c0 and c1) else
                                  "the scan does NOT clear the cap on PDVD -- see above"))


if __name__ == "__main__":
    main()
