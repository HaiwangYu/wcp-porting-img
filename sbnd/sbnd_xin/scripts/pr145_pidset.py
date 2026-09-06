#!/usr/bin/env python3
"""doc sbnd_xin/pr/145 sec 5 -- the ON-EPOCH mu-typed PID set, and the blind
scan sheet for it.

READ-ONLY.  Writes only its --tsv / --manifest.

FORK of pr141_pidset.py (M10 -- that script produced doc 141 sec 16/22's census
and stays byte-untouched).  Two things change, and only two:

  1. the arm is work-*-d144fixprod (current production, 1435 dumps) instead of
     work-pr140r2-off-* (retired, and therefore unreadable);
  2. the pre-registered predictor is kine_charge / kine_range, NOT
     cm_per_seg < 40.  doc 141 sec 22 scored that one at precision 0.500 and
     sec 22.2 declared every per-object scalar "overlaps".

WHY THE THRESHOLD IS 1.0, AND WHY THAT IS NOT FITTED.  The pr141 labels give
the mechanism (charge- and range-derived energies agree for a real track and
diverge for an EM shower typed as a muon) but they CANNOT set an on-epoch
threshold: only 2 of the 6 confident-EM labels survive a clean join onto this
arm (doc 145 sec 5.7).  So the threshold comes from the unlabelled population's
own structure instead, which uses no labels at all and so cannot be post-hoc on
them: the 222 mu-typed objects are bimodal with an EMPTY bin at 1.0-1.2, and
every threshold in [1.0, 1.2] selects exactly the same 23 objects.  1.0 is the
low edge of that stability plateau.

The served sheet is BLIND -- the predicted class is not printed on it, and the
rows are ordered by energy at stake only (feedback_blind_the_scan_sheet).

    ./scripts/pr145_pidset.py --tsv docs/pr/pr145-pidset.tsv \
        --manifest docs/pr/pr145-pidscan-manifest.tsv
"""
import argparse, glob, json, os, sys

SX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HYP = 1.657          # shower-hypothesis / track-hypothesis energy, exact global (doc 141)
E_FLOOR = 50.0       # MeV, track hypothesis
RATIO_CUT = 1.0      # kine_charge/kine_range; > cut => predicted EM
RANGE_FLOOR = 10.0   # MeV; below this the ratio is a division artifact, not a
                     # measurement -- doc 145 sec 5.8.1.  Three objects in the
                     # 222 sit here, the worst a 364.9 cm shower whose
                     # kine_range is 1e-4 MeV, which the ratio turns into 5.6e6
                     # and which would otherwise TOP the blind sheet.  They are
                     # classed DEGENERATE, never EM: the predictor did not
                     # select them, a failed range computation did.
N_SERVE = 20         # blind sheet size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm-tag", default="d144fixprod")
    ap.add_argument("--tsv")
    ap.add_argument("--manifest")
    a = ap.parse_args()

    rows, nev = [], 0
    for f in sorted(glob.glob(os.path.join(SX, f"work-*-{a.arm_tag}", "pr_evt*",
                                           "calib-pr-evt*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        nev += 1
        m = d.get("meta") or {}
        ev = int(m.get("eventNo") or 0)
        samp = os.path.basename(os.path.dirname(os.path.dirname(f))).split("-")[1]
        for s in (d.get("showers") or ()):
            if abs(int(s.get("particle_id") or 0)) != 13:
                continue
            q = float(s.get("kine_charge") or 0.0)
            if q <= E_FLOOR:
                continue
            rng = float(s.get("kine_range") or 0.0)
            degenerate = (rng < RANGE_FLOOR)
            ratio = (q / rng) if rng > 0 else float("inf")
            nseg = int(s.get("num_segments") or 0)
            L = float(s.get("total_length") or 0.0)
            st, en = s.get("start") or {}, s.get("end") or {}
            rows.append(dict(
                sample=samp, run=int(m.get("runNo") or 0),
                subrun=int(m.get("subRunNo") or 0), event=ev, obj=int(s["id"]),
                kine_charge=round(q, 1), kine_range=round(rng, 1),
                ratio=round(ratio, 3) if ratio != float("inf") else -1.0,
                dE_if_EM=round((HYP - 1.0) * q, 1),
                nseg=nseg, length=round(L, 1),
                cm_per_seg=round(L / nseg, 1) if nseg else -1.0,
                conn=int(s.get("start_connection_type") or -1),
                # (y,z) so the object can be re-found after ANY reconstruction
                # change -- ids renumber (doc 145 sec 5.7: only 29% survived)
                sy=round(float(st.get("y", 0)), 2), sz=round(float(st.get("z", 0)), 2),
                ey=round(float(en.get("y", 0)), 2), ez=round(float(en.get("z", 0)), 2),
                predicted=("DEGENERATE" if degenerate else
                           "EM" if ratio > RATIO_CUT else "TRACK"),
                dump=os.path.relpath(f, SX)))

    em = [r for r in rows if r["predicted"] == "EM"]
    tr = [r for r in rows if r["predicted"] == "TRACK"]
    dg = [r for r in rows if r["predicted"] == "DEGENERATE"]
    print("events read                       : %d" % nev)
    print("mu-typed objects > %.0f MeV        : %d" % (E_FLOOR, len(rows)))
    print("  predicted EM  (q/range > %.1f)   : %d" % (RATIO_CUT, len(em)))
    print("  predicted TRACK                 : %d" % len(tr))
    print("  DEGENERATE (kine_range < %.0f MeV): %d  -- excluded from both classes"
          % (RANGE_FLOOR, len(dg)))
    for r in sorted(dg, key=lambda r: -r["kine_charge"]):
        print("      %-8s ev=%-8d obj=%-7d q=%7.1f rng=%8.4f len=%7.1f"
              % (r["sample"], r["event"], r["obj"], r["kine_charge"],
                 r["kine_range"], r["length"]))
    print("energy at stake if every predicted-EM object IS EM: %.0f MeV over %d objects"
          % (sum(0.657 * r["kine_charge"] for r in em), len(em)))

    # the blind sheet: the highest-stake predicted-EM objects plus TRACK controls,
    # interleaved by energy so the sheet order carries no class information.
    served = sorted(em, key=lambda r: -r["dE_if_EM"])[:N_SERVE - 6]
    ctrl = sorted(tr, key=lambda r: -r["kine_charge"])[:6]
    served = sorted(served + ctrl, key=lambda r: -r["kine_charge"])
    print("\nSERVED (blind): %d objects = %d predicted-EM + %d predicted-TRACK controls"
          % (len(served), len(served) - len(ctrl), len(ctrl)))

    if a.tsv:
        cols = ["sample", "run", "subrun", "event", "obj", "kine_charge", "kine_range",
                "ratio", "dE_if_EM", "nseg", "length", "cm_per_seg", "conn",
                "sy", "sz", "ey", "ez", "predicted", "dump"]
        with open(os.path.join(SX, a.tsv), "w") as fh:
            fh.write("# doc pr/145 sec 5 -- mu-typed PID set, arm work-*-%s\n" % a.arm_tag)
            fh.write("# predictor: kine_charge/kine_range > %.1f => EM.  Threshold from the\n" % RATIO_CUT)
            fh.write("# population's own empty 1.0-1.2 bin, NOT fitted on labels (sec 5.8).\n")
            fh.write("\t".join(cols) + "\n")
            for r in sorted(rows, key=lambda r: -r["kine_charge"]):
                fh.write("\t".join(str(r[c]) for c in cols) + "\n")
        print("wrote %s (%d rows, ALL mu-typed objects)" % (a.tsv, len(rows)))

    if a.manifest:
        # BLIND: no predicted class, no ratio, no ordering hint beyond energy.
        with open(os.path.join(SX, a.manifest), "w") as fh:
            fh.write("# doc pr/145 sec 5 -- BLIND mu-typed PID scan sheet.  The predicted\n")
            fh.write("# class and the discriminant are deliberately ABSENT: printing them on\n")
            fh.write("# the sheet you then judge makes the agreement circular\n")
            fh.write("# (feedback_blind_the_scan_sheet).  Verdict: EM or TRACK, plus weak=1\n")
            fh.write("# if you are not confident.\n")
            fh.write("sample\trun\tsubrun\tevent\tobj\tkine_charge\tlength\tnseg\tverdict\tweak\n")
            for r in served:
                fh.write("%s\t%d\t%d\t%d\t%d\t%.1f\t%.1f\t%d\t\t\n" %
                         (r["sample"], r["run"], r["subrun"], r["event"], r["obj"],
                          r["kine_charge"], r["length"], r["nseg"]))
        print("wrote %s (%d rows, BLIND)" % (a.manifest, len(served)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
