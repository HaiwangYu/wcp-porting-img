#!/usr/bin/env python3
"""doc pdhd/16 -- the figure: three energy scales for one stopping muon,
before and after the recombination normalization.

Reads T_stm_michel from a BEFORE arm (uncalibrated inverse, e.g. d15vnu) and an
AFTER arm (calibrated, d16vnu) of the same events, and draws:

  1. dQ/dx energy over range energy vs muon length -- before and after.  The
     before curve is FLAT and low: that flatness is the whole argument that the
     deficit is a normalization and not a shape, so it is the first panel.
  2. the same ratio vs drift distance -- what the flat constant does NOT fix,
     reported as an open calibration item.
  3. MCS energy vs range energy, split on the ambiguity cut, with the
     dQ/dx-vs-range cloud behind it.
  4. the Michel object energy before and after against the 52.8 MeV endpoint --
     an absolute scale the calibration never saw.

Repro:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
  python3 pdhd/docs/scripts/d16_energy_plots.py --det pdvd \
      --before 'pdvd/work/*_d15vnu' --after 'pdvd/work/*_d16vnu' \
      -o pdhd/docs/figs/d16_energy_scales_pdvd.png
"""
import argparse
import glob
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import uproot

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
ANODE_ABS_X = {"pdvd": 339.91, "pdhd": 357.985}
MICHEL_ENDPOINT = 52.8      # MeV, (m_mu^2 + m_e^2)/(2 m_mu) - m_e

COLS = ["cluster_id", "is_stm", "muon_len", "muon_ke_range", "muon_ke_dqdx",
        "michel_found", "michel_ke_dqdx", "michel_ke_best", "has_pass",
        "entry_x", "stop_x"]
OPT = ["muon_ke_mcs", "muon_mcs_amb", "muon_mcs_nsegs", "muon_mcs_bad_path"]


def load(g):
    out = {c: [] for c in COLS + OPT}
    for d in sorted(glob.glob(g if os.path.isabs(g) else os.path.join(IMG, g))):
        rf = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        f = uproot.open(rf)
        if "T_stm_michel" not in [k.split(";")[0] for k in f.keys()]:
            continue
        t = f["T_stm_michel"]
        have = set(t.keys())
        a = t.arrays([c for c in COLS + OPT if c in have], library="np")
        n = len(a["cluster_id"])
        for c in COLS + OPT:
            out[c].append(a[c] if c in a else np.full(n, np.nan))
    return {c: (np.concatenate(v) if v else np.array([])) for c, v in out.items()}


def binned(x, y, edges):
    cen, med, lo, hi, nn = [], [], [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        s = (x >= a) & (x < b) & np.isfinite(y)
        if s.sum() >= 5:
            cen.append(0.5 * (a + min(b, x.max()))); med.append(np.median(y[s]))
            q = np.percentile(y[s], [25, 75]); lo.append(q[0]); hi.append(q[1]); nn.append(int(s.sum()))
    return map(np.array, (cen, med, lo, hi, nn))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=["pdvd", "pdhd"])
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()

    B, A = load(a.before), load(a.after)
    fig, ax = plt.subplots(2, 2, figsize=(12.5, 9))
    fig.suptitle("doc pdhd/16 -- the STM muon's energy scales, %s "
                 "(before = %s, after = %s)" % (a.det.upper(), a.before, a.after),
                 fontsize=11)

    def sel(d):
        return (d["is_stm"] == 1) & (d["muon_ke_range"] > 0) & (d["muon_ke_dqdx"] > 0)

    # ---- 1. ratio vs muon length ----------------------------------------
    p = ax[0][0]
    Ledges = np.array([0, 60, 90, 130, 180, 250, 350, 900])
    for d, lab, col in ((B, "before (model as configured)", "#b00"),
                        (A, "after (C measured vs range)", "#06c")):
        s = sel(d)
        if not s.any():
            continue
        cen, med, lo, hi, nn = binned(d["muon_len"][s],
                                      d["muon_ke_dqdx"][s] / d["muon_ke_range"][s], Ledges)
        p.errorbar(cen, med, yerr=[med - lo, hi - med], fmt="o-", color=col,
                   capsize=3, label="%s  (n=%d)" % (lab, int(s.sum())))
    p.axhline(1.0, color="k", lw=0.8, ls="--")
    p.set_xlabel("muon length [cm]"); p.set_ylabel(r"$E_{dQ/dx}$ / $E_{range}$")
    p.set_title("1. flat in length  =>  a normalization, not a shape", fontsize=10)
    p.legend(fontsize=8); p.grid(alpha=0.3)

    # ---- 2. ratio vs drift ----------------------------------------------
    p = ax[0][1]
    for d, lab, col in ((B, "before", "#b00"), (A, "after", "#06c")):
        s = sel(d)
        if not s.any():
            continue
        drift = ANODE_ABS_X[a.det] - 0.5 * (np.abs(d["entry_x"][s]) + np.abs(d["stop_x"][s]))
        cen, med, lo, hi, nn = binned(drift, d["muon_ke_dqdx"][s] / d["muon_ke_range"][s],
                                      np.array([0, 60, 120, 180, 240, 400]))
        p.errorbar(cen, med, yerr=[med - lo, hi - med], fmt="o-", color=col, capsize=3, label=lab)
    p.axhline(1.0, color="k", lw=0.8, ls="--")
    p.set_xlabel("mean drift distance [cm]"); p.set_ylabel(r"$E_{dQ/dx}$ / $E_{range}$")
    p.set_title("2. what one flat constant does NOT fix (open item)", fontsize=10)
    p.legend(fontsize=8); p.grid(alpha=0.3)

    # ---- 3. the three scales --------------------------------------------
    p = ax[1][0]
    s = sel(A)
    if s.any():
        p.plot(A["muon_ke_range"][s], A["muon_ke_dqdx"][s], ".", ms=4, color="#06c",
               alpha=0.5, label="dQ/dx (calibrated)")
        m = s & (A["muon_ke_mcs"] > 0)
        good = m & (A["muon_mcs_amb"] < 0.2)
        p.plot(A["muon_ke_range"][m & ~good], A["muon_ke_mcs"][m & ~good], "^", ms=5,
               mfc="none", color="#a60", alpha=0.7, label="MCS, amb $\\geq$ 0.2 (n=%d)" % int((m & ~good).sum()))
        p.plot(A["muon_ke_range"][good], A["muon_ke_mcs"][good], "s", ms=5, color="#0a0",
               alpha=0.8, label="MCS, amb < 0.2 (n=%d)" % int(good.sum()))
        lim = [0, float(np.nanpercentile(A["muon_ke_range"][s], 99)) * 1.05]
        p.plot(lim, lim, "k--", lw=0.8)
        p.set_xlim(lim); p.set_ylim(lim)
    p.set_xlabel("range KE [MeV]  (the baseline)"); p.set_ylabel("estimator KE [MeV]")
    p.set_title("3. dQ/dx and MCS against the range baseline", fontsize=10)
    p.legend(fontsize=8); p.grid(alpha=0.3)

    # ---- 4. the Michel spectrum -----------------------------------------
    p = ax[1][1]
    bins = np.linspace(0, 90, 46)
    for d, lab, col in ((B, "before", "#b00"), (A, "after", "#06c")):
        m = (d["has_pass"] == 1) & (d["muon_len"] >= 10) & (d["michel_found"] == 1)
        if m.sum():
            p.hist(d["michel_ke_dqdx"][m], bins=bins, histtype="step", color=col, lw=1.6,
                   label="%s  (n=%d, p90 %.1f)" % (lab, int(m.sum()),
                                                   np.percentile(d["michel_ke_dqdx"][m], 90)))
    p.axvline(MICHEL_ENDPOINT, color="k", ls="--", lw=1.0)
    p.text(MICHEL_ENDPOINT + 1, p.get_ylim()[1] * 0.85, "52.8 MeV\nMichel endpoint", fontsize=8)
    p.set_xlabel(r"Michel object $E_{dQ/dx}$ [MeV]"); p.set_ylabel("objects")
    p.set_title("4. an absolute scale the calibration never saw", fontsize=10)
    p.legend(fontsize=8); p.grid(alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=120)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
