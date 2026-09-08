#!/usr/bin/env python3
"""doc pdvd/50 round 2 -- the before/after ladder across chain arms.

Consumes only d51_dqdx_rr_apa.py's <out>_{tracks,apa}.tsv, so every published
number is regenerable from the doc's Repro block.

Two things this exists to keep honest:

  * R3 (traj_final_fill_charge_test) DELETES charge-free fit points, so f_low
    falls whether or not charge was recovered.  Every f_low row is printed with
    pts_per_cm beside it (feedback_matched_population_metric_bias).
  * Arms taken across a CLUSTERING change cannot be matched on (event, block) --
    block = cluster*10 + pass and cluster ids do not survive re-clustering.
    Everything here is a POPULATION comparison over the same event set; the
    event sets are printed and their intersection size is asserted.

Usage:
  python3 d51_arm_ladder.py --out LADDER --label-tier complete_bragg \
      old=ANA/gate_pdhd_d30hpost newclus=ANA/d51_pdhd_fit0 new=ANA/d51_pdhd_stm
Writes <out>_tiers.tsv, <out>_attrition.tsv, <out>_apa.tsv and prints them.
"""
import argparse, json, os, sys
import numpy as np

BINS = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 60)]
TIERS = ["all_kept", "contrast_ge2", "doc55_cuts", "doc55_muon",
         "complete", "complete_bragg"]
SHOW = ["ntracks", "npoints", "k_pop", "chi2", "k_med", "contrast_med",
        "f_low_med", "pts_per_cm_med", "reach_frac"]


def read_tsv(path):
    """Header-commented TSV -> (list of dicts, header list)."""
    rows, hdr = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f; continue
            if len(f) < 2:
                continue
            rows.append(dict(zip(hdr, f)))
    return rows, hdr


def fnum(d, k, default=float("nan")):
    try:
        return float(d[k])
    except (KeyError, ValueError, TypeError):
        return default


def attrition(tracks):
    """doc 50 sec 4.1's cumulative doc-55 ladder, plus the completeness route."""
    def n(pred):
        return sum(1 for t in tracks if pred(t))
    c = []
    c.append(("accepted STM passes (status 0)", len(tracks)))
    s1 = [t for t in tracks if fnum(t, "npts") >= 40]
    c.append(("+ npts >= 40", len(s1)))
    s2 = [t for t in s1 if fnum(t, "nbins") >= 6]
    c.append(("+ >= 6 populated rr bins", len(s2)))
    s3 = [t for t in s2 if fnum(t, "rrmin") < 2.0 and fnum(t, "rrmax") >= 22.0]
    c.append(("+ reaches rr < 2 and rr >= 22 cm", len(s3)))
    s4 = [t for t in s3 if fnum(t, "contrast") >= 2.0]
    c.append(("+ Bragg contrast >= 2", len(s4)))
    s5 = [t for t in s4 if fnum(t, "med_chi2") <= 2.5]
    c.append(("+ median reduced chi2 <= 2.5", len(s5)))
    s6 = [t for t in s5 if fnum(t, "shape_muon") <= 0.10]
    c.append(("+ muon shape rms <= 0.10", len(s6)))
    c.append(("(instead) npts >= 40 and f_low < 0.05",
              n(lambda t: fnum(t, "npts") >= 40 and fnum(t, "f_low") < 0.05)))
    c.append(("(instead) ... and Bragg contrast >= 2",
              n(lambda t: fnum(t, "npts") >= 40 and fnum(t, "f_low") < 0.05
                and fnum(t, "contrast") >= 2.0)))
    return c


def shape_test(row_a, row_b, tier):
    """Is arm A's rr shape flat, or does it carry arm B's shape?

    Doc 50 sec 5 left PDVD's +10 % hump at 3-20 cm undecided on PDHD (Delta chi2
    = -2.5 on 6 tracks).  Both per-bin curves already have one free scale
    removed, so renormalise each to unit geometric mean over the bins BOTH
    populate and compare A against 1 (flat) and against B (the template).  The
    template carries its own error, which is added in quadrature -- without that
    the template is treated as exact and the comparison is unfair to 'flat'."""
    ra = np.array([fnum(row_a, "r_%d_%d" % b) for b in BINS])
    ea = np.array([fnum(row_a, "e_%d_%d" % b) for b in BINS])
    na = np.array([fnum(row_a, "n_%d_%d" % b) for b in BINS])
    rb = np.array([fnum(row_b, "r_%d_%d" % b) for b in BINS])
    eb = np.array([fnum(row_b, "e_%d_%d" % b) for b in BINS])
    nb = np.array([fnum(row_b, "n_%d_%d" % b) for b in BINS])
    m = np.isfinite(ra) & np.isfinite(rb) & (na >= 5) & (nb >= 5)
    if m.sum() < 3:
        return None
    ga = float(np.exp(np.mean(np.log(ra[m])))); gb = float(np.exp(np.mean(np.log(rb[m]))))
    A, EA = ra[m] / ga, ea[m] / ga
    B, EB = rb[m] / gb, eb[m] / gb
    chi_flat = float(np.sum(((A - 1.0) / EA) ** 2))
    chi_tmpl = float(np.sum(((A - B) / np.hypot(EA, EB)) ** 2))
    return dict(nbins=int(m.sum()), chi2_flat=chi_flat, chi2_template=chi_tmpl,
                dchi2=chi_tmpl - chi_flat, tier=tier)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+", help="label=<out prefix> (the prefix given to d51_dqdx_rr_apa.py)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--apa-tier", default="all_kept",
                    help="tier whose per-readout-unit table is tabulated (doc 50 sec 4.2 used all_kept)")
    ap.add_argument("--shape-test", default="",
                    help="LAB_A,LAB_B: test arm A's rr shape against flat and against arm B's shape")
    ap.add_argument("--shape-tier", default="complete_bragg")
    ap.add_argument("--drift-profile", default="",
                    help="LABEL:REF_JSON:ANODE_ABS_X -- plateau dQ/dx vs |x| for that arm, "
                         "the doc 50 sec 6 --max-abs-x check redone on the new arms")
    a = ap.parse_args()

    arms = []
    for spec in a.arms:
        lab, _, pre = spec.partition("=")
        if not pre:
            print("bad arm spec %r (want label=prefix)" % spec, file=sys.stderr); return 2
        tr, _ = read_tsv(pre + "_tracks.tsv")
        su, _ = read_tsv(pre + "_summary.tsv")
        ap_rows, _ = read_tsv(pre + "_apa.tsv")
        arms.append(dict(label=lab, prefix=pre, tracks=tr,
                         summary={r["tier"]: r for r in su},
                         apa=[r for r in ap_rows if r.get("tier") == a.apa_tier]))

    # --- event-set sanity: population comparisons need the same events -------
    evsets = [set(t["event"].rsplit("_", 1)[0] for t in arm["tracks"]) for arm in arms]
    common = set.intersection(*evsets) if evsets else set()
    print("event sets (by run_evt, tag stripped):")
    for arm, es in zip(arms, evsets):
        print("  %-12s %d events" % (arm["label"], len(es)))
    print("  intersection: %d events" % len(common))
    if any(len(es) != len(common) for es in evsets):
        print("  NOTE: not every arm contributes a track from every event.  An arm is absent"
              " from an event when that event yielded NO accepted (status 0) pass there --"
              " which is itself a chain effect, not a coverage gap.  Confirm the arms ran the"
              " same events by counting tracking-stm.root, not by this line, before reading"
              " the tables below as a delta.", file=sys.stderr)

    # --- tier table ---------------------------------------------------------
    with open(a.out + "_tiers.tsv", "w") as fh:
        fh.write("# doc pdvd/50 r2 d51_arm_ladder.py -- tier ladder per arm.\n"
                 "# Read f_low_med WITH pts_per_cm_med: R3 deletes charge-free fit points, so\n"
                 "# f_low falls mechanically.  f_low down + density HELD = recovery;\n"
                 "# f_low down + density DOWN = deletion.\n")
        fh.write("tier\tarm\t" + "\t".join(SHOW) + "\n")
        for tier in TIERS:
            for arm in arms:
                r = arm["summary"].get(tier)
                if r is None:
                    continue
                fh.write(tier + "\t" + arm["label"] + "\t"
                         + "\t".join(r.get(c, "") for c in SHOW) + "\n")

    # --- attrition table ----------------------------------------------------
    lads = [attrition(arm["tracks"]) for arm in arms]
    with open(a.out + "_attrition.tsv", "w") as fh:
        fh.write("# doc 50 sec 4.1's cumulative cuts, per arm.\n")
        fh.write("cut\t" + "\t".join(arm["label"] for arm in arms) + "\n")
        for i, (name, _) in enumerate(lads[0]):
            fh.write(name + "\t" + "\t".join(str(l[i][1]) for l in lads) + "\n")

    # --- per-readout-unit table --------------------------------------------
    BANDS = ["band_lt0.2", "band_0.2-0.5", "band_0.5-0.8", "band_0.8-1.2", "band_gt1.2"]
    with open(a.out + "_apa.tsv", "w") as fh:
        fh.write("# per readout-unit selection on tier '%s', per arm.  plateau_ratio has NO free\n"
                 "# scale.  band_* are ABSOLUTE point counts: deletion shrinks every band,\n"
                 "# recovery collapses band_lt0.2 while band_0.8-1.2 holds.\n" % a.apa_tier)
        fh.write("sel\tarm\tntracks\tnpoints\tplateau_ratio\tplateau_npts\tplateau_ratio_hi\t"
                 "killed_frac\t" + "\t".join(BANDS) + "\n")
        sels = []
        for arm in arms:
            for r in arm["apa"]:
                if r["sel"] not in sels:
                    sels.append(r["sel"])
        for sel in sels:
            for arm in arms:
                r = next((x for x in arm["apa"] if x["sel"] == sel), None)
                if r is None:
                    continue
                fh.write("\t".join([sel, arm["label"], r["ntracks"], r["npoints"],
                                    r["plateau_ratio"], r["plateau_npts"],
                                    r["plateau_ratio_hi"], r["killed_frac"]]
                                   + [r[b] for b in BANDS]) + "\n")

    # --- optional cross-arm shape test -------------------------------------
    if a.shape_test:
        la, _, lb = a.shape_test.partition(",")
        A = next((arm for arm in arms if arm["label"] == la), None)
        B = next((arm for arm in arms if arm["label"] == lb), None)
        if A is None or B is None:
            print("shape-test: unknown label(s) %r" % a.shape_test, file=sys.stderr)
        else:
            rows_a, _ = read_tsv(A["prefix"] + "_apa.tsv")
            rows_b, _ = read_tsv(B["prefix"] + "_apa.tsv")
            ra = next((r for r in rows_a if r["tier"] == a.shape_tier and r["sel"] == "all"), None)
            rb = next((r for r in rows_b if r["tier"] == a.shape_tier and r["sel"] == "all"), None)
            res = shape_test(ra, rb, a.shape_tier) if (ra and rb) else None
            if res is None:
                print("shape-test: too few shared populated bins")
            else:
                print("\nSHAPE TEST  %s vs flat, and %s vs %s's shape  (tier %s, %d bins)"
                      % (la, la, lb, res["tier"], res["nbins"]))
                print("  chi2 flat     = %7.2f" % res["chi2_flat"])
                print("  chi2 template = %7.2f" % res["chi2_template"])
                print("  Delta chi2    = %+7.2f  (negative favours the template)" % res["dchi2"])

    # --- optional drift profile (doc 50 sec 6's --max-abs-x derivation) ------
    if a.drift_profile:
        lab, refp, anode = a.drift_profile.split(":")
        arm = next((x for x in arms if x["label"] == lab), None)
        t = json.load(open(refp))["MuonDeDx"]
        xs = t["start"] + t["step"] * np.arange(len(t["values"]))
        ys = np.asarray(t["values"], float)
        ref = lambda rr: np.interp(rr, xs, ys)
        rows, _ = read_tsv(arm["prefix"] + "_points.tsv")
        rr, v, ax = [], [], []
        for r in rows:
            if r.get("past_kink") != "0":
                continue
            try:
                q = float(r["dqdx"]); s_rr = float(r["rr_kink"]); s_x = abs(float(r["x"]))
            except (ValueError, KeyError):
                continue
            if not np.isfinite(q) or q <= 0 or s_rr < 20 or s_rr >= 80:
                continue
            rr.append(s_rr); v.append(q); ax.append(s_x)
        rr = np.array(rr); v = np.array(v); ax = np.array(ax)
        print("\nDRIFT PROFILE  arm=%s  rr 20-80 cm, live points, ratio to the muon table "
              "(NO free scale).  |x| runs from the cathode toward the anode at %s cm."
              % (lab, anode))
        edges = list(np.arange(0, float(anode) + 20.0, 20.0))
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (ax >= lo) & (ax < hi)
            if m.sum() < 30:
                continue
            print("  |x| %5.0f-%-5.0f  n=%-7d ratio %.3f" % (lo, hi, m.sum(),
                  float(np.median(v[m] / ref(rr[m])))))
        for cut in (250.0, 280.0, 305.0):
            m = ax < cut
            if m.sum():
                print("  |x| < %-5.0f      n=%-7d ratio %.3f  (keeps %.0f %% of points)"
                      % (cut, m.sum(), float(np.median(v[m] / ref(rr[m]))), 100.0 * m.mean()))
        print("  no cut          n=%-7d ratio %.3f" % (len(v), float(np.median(v / ref(rr)))))

    for suffix in ("_tiers", "_attrition", "_apa"):
        print("\n==== %s%s.tsv" % (os.path.basename(a.out), suffix))
        for line in open(a.out + suffix + ".tsv"):
            if not line.startswith("#"):
                print("  " + line.rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
