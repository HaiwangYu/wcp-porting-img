#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 -- build the BLIND 24-object EM/HADRONIC scan set.

READ-ONLY apart from the two files named by --sheet and --key.

Input is docs/pr/pr148-a5-census.tsv (scripts/pr148_a5_census.py), the 313
conn-1 |11| showers the A5 tag evaluated over the 3067-event production set.

FOUR STRATA of six.  The strata are a SAMPLING design, not a proposed cut --
doc pr/148 sec 5 records that all three offline candidate discriminants died
against the control, so nothing here claims to separate anything:

  S1  highest kine_best, not re-typed, in events the nue BDT rejects
      (nue_score < 3).  Where a mis-type costs Enu accuracy with no
      selection consequence.  Contains 137238 and does not mark it.
  S2  not re-typed, in BDT-rejected events, carrying a STAR: >= 2 short
      heavily-ionising prongs sharing a graph vertex away from the shower
      start.  This is what a hadronic interaction looks like; whether it
      separates is the question, not the premise.
  S3  CONTROL -- highest kine_best, not re-typed, in nue-SELECTED events
      (nue_score >= 3).  Expected to come back EM.  A rule that eats these
      is the pr/93 sec 6 regression class (23/48 nueCC48) and is dead on
      arrival.
  S4  CONTROL -- objects A5 ALREADY re-typed to 211.  Expected HADRONIC.
      If these come back EM the current production tag is over-firing and
      that is a finding in its own right.

The sheet carries NO growth / bragg / stem / f_heavy / n_heavy / star /
nue_score / verdict / stratum -- printing the proxy's answer on the sheet you
then judge makes the agreement circular (feedback_blind_the_scan_sheet).
Everything withheld is written to the KEY file, which the viewer and its
self-test never open; the self-test asserts that.

The order is shuffled with a FIXED seed so the sheet is reproducible and the
strata are not readable off the row order.

Repro:
  ./pr148_pidset.py --census ../docs/pr/pr148-a5-census.tsv \
      --sheet ../docs/pr/pr148-pidscan-manifest.tsv \
      --key   ../docs/pr/pr148-pidscan.KEY.tsv
"""
import argparse, csv, json, os, random, sys

SEED = 147          # arbitrary but FIXED, so the sheet order is reproducible; not a doc number
PER_STRATUM = 6
SHEET_COLS = ["idx", "sample", "run", "subrun", "event", "obj", "shower_id",
              "kine_charge_mev", "kine_best_mev", "total_len_cm", "nseg",
              "verdict", "weak", "note"]
KEY_COLS = ["idx", "sample", "event", "shower_id", "stratum", "a5_verdict",
            "growth", "bragg", "stem_mip", "n_heavy", "f_heavy", "max_mip",
            "star_n", "star_dist_cm", "stem_run_cm", "start_len_cm",
            "start_score", "kine_dQdx_mev", "nue_score", "enu_mev"]


def num(r, k, d=0.0):
    v = r.get(k, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def runsub(sample, event):
    """run/subrun from the per-event calib dump's meta (never guessed)."""
    p = os.path.join("work-%s-d145np" % sample, "pr_evt%s" % event,
                     "calib-pr-evt%s.json" % event)
    if not os.path.exists(p):
        return "", ""
    with open(p) as fh:
        m = json.load(fh).get("meta", {})
    return m.get("runNo", ""), m.get("subRunNo", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--key", required=True)
    a = ap.parse_args()

    rows = [r for r in csv.DictReader(open(a.census), delimiter="\t")
            if r["start_seg"] != ""]
    # one row per physical object: the same event can appear in two samples
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: (r["event"], r["shower_id"], r["sample"])):
        k = (r["event"], r["shower_id"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    kept = [r for r in uniq if r["verdict"] == "0"]
    rej = [r for r in kept if num(r, "nue_score", -99) < 3.0]
    sel = [r for r in kept if num(r, "nue_score", -99) >= 3.0]
    ret = [r for r in uniq if r["verdict"] == "1"]
    by_e = lambda g: sorted(g, key=lambda r: -num(r, "kine_best_mev"))

    picked, strata = [], {}

    def take(cands, name, n=PER_STRATUM):
        got = 0
        for r in cands:
            if got >= n:
                break
            k = (r["event"], r["shower_id"])
            if k in strata:
                continue
            strata[k] = name
            picked.append(r)
            got += 1
        return got

    # S1 -- 137238 first so it is guaranteed in, then by energy
    s1 = [r for r in rej if r["event"] == "137238"] + by_e(rej)
    take(s1, "S1_rejected_topE")
    # S2 backfills down a stated chain so it always reaches six: a star
    # away from the start vertex first, then any heavy prong, then any
    # remaining rejected object by energy.  Stated, because "we took the
    # next thing available" is part of how the sample was built.
    star = ([r for r in by_e(rej)
             if num(r, "star_n") >= 2 and num(r, "star_dist_cm") > 5.0]
            + [r for r in by_e(rej) if num(r, "n_heavy") >= 1]
            + by_e(rej))
    take(star, "S2_rejected_star")
    take(by_e(sel), "S3_control_nue_selected")
    take(by_e(ret), "S4_control_already_retyped")

    random.Random(SEED).shuffle(picked)

    with open(a.sheet, "w") as sh, open(a.key, "w") as kf:
        sh.write("# doc pr/148 -- BLIND EM/HADRONIC scan sheet, 24 objects.\n"
                 "# The A5 discriminants (growth, bragg, stem), the derived\n"
                 "# candidates (n_heavy, f_heavy, star), the nue BDT score, the\n"
                 "# tag's own verdict and the stratum are all DELIBERATELY\n"
                 "# ABSENT: printing the proxy's answer on the sheet you then\n"
                 "# judge makes the agreement circular.  They live in\n"
                 "# pr148-pidscan.KEY.tsv, which the scan display never opens.\n"
                 "#\n"
                 "# verdict: EM | HADRONIC | MIXED      weak: 1 if not confident\n"
                 "#   EM       -- an electron or photon shower\n"
                 "#   HADRONIC -- a pion/proton/neutron interaction; should not\n"
                 "#               be typed 11 and should not be valued as EM\n"
                 "#   MIXED    -- both, clustered into one object (this is the\n"
                 "#               splitter's problem, not the tag's)\n"
                 "#\n"
                 "# The display fills this in for you:\n"
                 "#   ./pr148_scan/serve_pr148_scan.sh 5017\n")
        sh.write("\t".join(SHEET_COLS) + "\n")
        kf.write("# doc pr/148 -- the KEY for pr148-pidscan-manifest.tsv.\n"
                 "# Written so the record exists.  The scan display and its\n"
                 "# self-test never open this file; the self-test asserts that.\n")
        kf.write("\t".join(KEY_COLS) + "\n")
        for i, r in enumerate(picked):
            run, sub = runsub(r["sample"], r["event"])
            sh.write("\t".join(str(x) for x in [
                i, r["sample"], run, sub, r["event"], r["start_seg"],
                r["shower_id"], r["kine_charge_mev"], r["kine_best_mev"],
                r["total_len_cm"], r["nseg_final"], "", "", ""]) + "\n")
            kf.write("\t".join(str(x) for x in [
                i, r["sample"], r["event"], r["shower_id"],
                strata[(r["event"], r["shower_id"])], r["verdict"],
                r["growth"], r["bragg"], r["stem_mip"], r["n_heavy"],
                r["f_heavy"], r["max_mip"], r["star_n"], r["star_dist_cm"],
                r["stem_run_cm"], r["start_len_cm"], r["start_score"],
                r["kine_dQdx_mev"], r["nue_score"], r["enu_mev"]]) + "\n")

    from collections import Counter
    print("picked %d object(s): %s" % (len(picked), dict(Counter(strata.values()))))
    print("137238 present: %s" % any(r["event"] == "137238" for r in picked))
    print("wrote %s and %s" % (a.sheet, a.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
