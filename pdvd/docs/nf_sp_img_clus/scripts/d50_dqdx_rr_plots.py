#!/usr/bin/env python3
"""doc pdvd/50 -- figures: dQ/dx vs residual range, PDHD and PDVD, against BOTH
detectors' own expectation curves, plus the proton hypothesis and the
charge-completeness diagnosis.

Consumes only the TSVs written by d50_dqdx_rr_cross.py and
d50_pr_proton_segments.py, so every figure is regenerable from committed
products.

Usage:
  python3 d50_dqdx_rr_plots.py --ana ANA --figs pdvd/docs/nf_sp_img_clus/figs
"""
import argparse, json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BINS = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 60)]
SYS_FLOOR = 0.03
REF = {"pdhd": "/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd/stm/pdhd_ref_dqdx.json",
       "pdvd": "/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd/stm/pdvd_ref_dqdx_045.json"}
FIELD = {"pdhd": "0.4959 kV/cm", "pdvd": "0.45 kV/cm"}
ANODE = {"pdhd": 352.1, "pdvd": 339.91}
COL = {"pdhd": "#c1272d", "pdvd": "#0b6fa4"}


def table(det, key):
    t = json.load(open(REF[det]))[key]
    x = t["start"] + t["step"] * np.arange(len(t["values"]))
    return x, np.asarray(t["values"], float)


def interp(det, key):
    x, y = table(det, key)
    return lambda rr: np.interp(rr, x, y)


def load_tracks(p):
    hdr, rows = None, []
    for l in open(p):
        if l.startswith("#"):
            continue
        if hdr is None:
            hdr = l.rstrip("\n").split("\t"); continue
        rows.append(l.rstrip("\n").split("\t"))
    return {c: j for j, c in enumerate(hdr)}, rows


def sample(ana, det, tier):
    """Return (rr, dqdx, ntracks) for one tier, pooling the status-0 and status-5 files."""
    RR, VV, nt = [], [], 0
    for st in ("s0", "s5"):
        tf = "%s/d50_%s_%s_tracks.tsv" % (ana, det, st)
        pf = "%s/d50_%s_%s_points.tsv" % (ana, det, st)
        if not os.path.exists(tf):
            continue
        i, rows = load_tracks(tf)
        def f(r, c):
            try: return float(r[i[c]])
            except Exception: return float("nan")
        if tier == "complete_bragg":
            sel = [r for r in rows if r[i["complete"]] == "1" and f(r, "contrast") >= 2 and r[i["status"]] == "0"]
        elif tier == "complete":
            sel = [r for r in rows if r[i["complete"]] == "1" and r[i["status"]] == "0"]
        elif tier == "doc55_muon":
            sel = [r for r in rows if r[i["doc55"]] == "1" and 0.85 <= f(r, "k_muon") <= 1.25 and r[i["status"]] == "0"]
        else:
            sel = [r for r in rows if r[i["status"]] == "0"]
        keys = {r[i["event"]] + "#" + r[i["block"]] for r in sel}
        nt += len(sel)
        if not keys:
            continue
        d = np.genfromtxt(pf, delimiter="\t", names=True, dtype=None, encoding="utf-8")
        k = np.array([e + "#" + str(b) for e, b in zip(d["event"], d["block"])])
        m = np.isin(k, list(keys)) & (d["past_kink"] == 0) & np.isfinite(d["dqdx"]) & (d["dqdx"] > 0)
        RR.append(d["rr_kink"][m]); VV.append(d["dqdx"][m])
    if not RR:
        return np.array([]), np.array([]), 0
    return np.concatenate(RR), np.concatenate(VV), nt


def binned(rr, v, ref=None, k=1.0):
    cen, med, err, n = [], [], [], []
    for lo, hi in BINS:
        m = (rr >= lo) & (rr < hi)
        if m.sum() < 5:
            continue
        r = v[m] / (k * ref(rr[m])) if ref is not None else v[m]
        mm = float(np.median(r))
        e = float(1.2533 * 1.4826 * np.median(np.abs(r - mm)) / np.sqrt(m.sum()))
        if ref is not None:
            e = float(np.hypot(e, SYS_FLOOR * mm))
        cen.append(0.5 * (lo + hi)); med.append(mm); err.append(e); n.append(int(m.sum()))
    return map(np.array, (cen, med, err, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ana", required=True)
    ap.add_argument("--figs", required=True)
    ap.add_argument("--tier", default="complete_bragg")
    a = ap.parse_args()
    os.makedirs(a.figs, exist_ok=True)
    dets = ["pdhd", "pdvd"]
    S = {d: sample(a.ana, d, a.tier) for d in dets}
    KP = {}
    for d in dets:
        rr, v, nt = S[d]
        KP[d] = float(np.exp(np.median(np.log(v / interp(d, "MuonDeDx")(rr))))) if len(v) else np.nan

    # ================= FIGURE 1: the overlay + the ratio =================
    fig, ax = plt.subplots(1, 2, figsize=(14.5, 6.0))
    A = ax[0]
    for d in dets:
        x, mu = table(d, "MuonDeDx"); _, pr = table(d, "ProtonDeDx")
        A.plot(x, mu * KP[d], "-", color=COL[d], lw=2,
               label="%s muon expectation @ %s (x k=%.2f)" % (d.upper(), FIELD[d], KP[d]))
        A.plot(x, pr * KP[d], "--", color=COL[d], lw=1.6, alpha=.75,
               label="%s proton expectation (same k)" % d.upper())
    for d in dets:
        rr, v, nt = S[d]
        if not len(v):
            continue
        cen, med, err, n = binned(rr, v)
        A.errorbar(cen, med, yerr=err, fmt="o", ms=7, color=COL[d], mfc="w", mew=2, capsize=3, zorder=5,
                   label="%s measured, %d tracks / %d pts" % (d.upper(), nt, len(v)))
    # the PR chain's own proton-tagged segments
    mk = {"pdhd": "^", "pdvd": "s"}
    for d in dets:
        p = "%s/d50_%s_prp_points.tsv" % (a.ana, d)
        if not os.path.exists(p):
            continue
        q = np.genfromtxt(p, delimiter="\t", names=True, dtype=None, encoding="utf-8")
        if q.size == 0:
            continue
        A.plot(np.atleast_1d(q["rr"]), np.atleast_1d(q["dqdx"]), mk[d], ms=4, color=COL[d], alpha=.55, zorder=4,
               label="%s PR particle_id=2212 segments (n=%d)" % (d.upper(), len(set(np.atleast_1d(q["seg"]).tolist()))))
    A.set_xscale("log"); A.set_xlim(0.4, 65); A.set_ylim(0, 2.1e5)
    A.set_xlabel("residual range  [cm]"); A.set_ylabel("dQ/dx  [e/cm]")
    A.set_title("Stopping-muon dQ/dx vs residual range\nboth detectors' own Modified-Box expectation overlaid")
    A.grid(alpha=.25); A.legend(fontsize=7.4, loc="upper right")

    B = ax[1]
    for d in dets:
        rr, v, nt = S[d]
        if not len(v):
            continue
        cen, med, err, n = binned(rr, v, interp(d, "MuonDeDx"), KP[d])
        B.errorbar(cen, med, yerr=err, fmt="o-", ms=6, lw=1.4, color=COL[d], capsize=3,
                   label="%s  (k=%.3f, %d tracks)" % (d.upper(), KP[d], nt))
    B.axhline(1, color="k", lw=1)
    B.fill_between([0.4, 65], 1 - SYS_FLOOR, 1 + SYS_FLOOR, color="k", alpha=.08, lw=0,
                   label="3 % systematic floor")
    B.set_xscale("log"); B.set_xlim(0.4, 65); B.set_ylim(0.6, 1.45)
    B.set_xlabel("residual range  [cm]")
    B.set_ylabel("measured / (k x own muon table)")
    B.set_title("Shape comparison: each detector against its OWN table\n(one free scale removed per detector)")
    B.grid(alpha=.25); B.legend(fontsize=8.5, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(a.figs, "50_dqdx_rr_overlay.png"), dpi=145)
    print("wrote", os.path.join(a.figs, "50_dqdx_rr_overlay.png"))

    # ================= FIGURE 2: why the two samples differ =================
    fig2, bx = plt.subplots(2, 2, figsize=(13.5, 9.2))
    # (a) f_low distribution
    P = bx[0][0]
    for d in dets:
        fl = []
        for st in ("s0", "s5"):
            tf = "%s/d50_%s_%s_tracks.tsv" % (a.ana, d, st)
            if not os.path.exists(tf):
                continue
            i, rows = load_tracks(tf)
            fl += [float(r[i["f_low"]]) for r in rows if r[i["status"]] == "0" and int(r[i["npts"]]) >= 40
                   and r[i["f_low"]] != "nan"]
        fl = np.array(fl)
        P.hist(fl, bins=np.linspace(0, 1, 41), histtype="step", lw=2, color=COL[d], density=True,
               label="%s  median %.3f  (n=%d)" % (d.upper(), np.median(fl), len(fl)))
    P.axvline(0.05, color="k", ls=":", lw=1.5)
    P.text(0.055, P.get_ylim()[1] * .85, "charge-complete\ncut (f_low < 0.05)", fontsize=8)
    P.set_xlabel("f_low  =  fraction of live fit points below 0.4 x plateau")
    P.set_ylabel("tracks (normalised)"); P.set_title("(a) Charge completeness of the fitted trajectories")
    P.grid(alpha=.25); P.legend(fontsize=8.5)
    # (b) k vs f_low
    P = bx[0][1]
    for d in dets:
        xs, ks = [], []
        for st in ("s0", "s5"):
            tf = "%s/d50_%s_%s_tracks.tsv" % (a.ana, d, st)
            if not os.path.exists(tf):
                continue
            i, rows = load_tracks(tf)
            for r in rows:
                if r[i["status"]] != "0" or int(r[i["npts"]]) < 40:
                    continue
                try:
                    xs.append(float(r[i["f_low"]])); ks.append(float(r[i["k_muon"]]))
                except Exception:
                    pass
        xs = np.array(xs); ks = np.array(ks); m = np.isfinite(xs) & np.isfinite(ks)
        xs, ks = xs[m], ks[m]
        edges = [0, .05, .10, .15, .25, .40, 1.01]
        c, y, e = [], [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            s = (xs >= lo) & (xs < hi)
            if s.sum() >= 3:
                c.append(.5 * (lo + hi)); y.append(np.median(ks[s]))
                e.append(1.2533 * np.std(ks[s]) / np.sqrt(s.sum()))
        P.plot(xs, ks, ".", ms=2.5, color=COL[d], alpha=.28)
        P.errorbar(c, y, yerr=e, fmt="o-", color=COL[d], lw=2, ms=7, capsize=3, label=d.upper())
    P.axvline(0.05, color="k", ls=":", lw=1.5); P.axhline(1, color="k", lw=.8)
    P.set_xlim(0, .8); P.set_ylim(0, 1.5)
    P.set_xlabel("f_low"); P.set_ylabel("per-track scale k vs the muon table")
    P.set_title("(b) The SAME relation on both detectors\nthey differ in f_low, not in charge")
    P.grid(alpha=.25); P.legend(fontsize=9)
    # (c) plateau dQ/dx vs drift distance
    P = bx[1][0]
    for d in dets:
        rr, v, _ = S[d]
        # need x: reload the complete tier points with x
        XS, VS = [], []
        for st in ("s0", "s5"):
            tf = "%s/d50_%s_%s_tracks.tsv" % (a.ana, d, st); pf = "%s/d50_%s_%s_points.tsv" % (a.ana, d, st)
            if not os.path.exists(tf):
                continue
            i, rows = load_tracks(tf)
            keys = {r[i["event"]] + "#" + r[i["block"]] for r in rows if r[i["complete"]] == "1" and r[i["status"]] == "0"}
            if not keys:
                continue
            q = np.genfromtxt(pf, delimiter="\t", names=True, dtype=None, encoding="utf-8")
            k = np.array([e + "#" + str(b) for e, b in zip(q["event"], q["block"])])
            m = (np.isin(k, list(keys)) & (q["past_kink"] == 0) & np.isfinite(q["dqdx"]) & (q["dqdx"] > 0)
                 & (q["rr_kink"] >= 20) & (q["rr_kink"] < 80))
            XS.append(np.abs(q["x"][m])); VS.append(q["dqdx"][m])
        X = np.concatenate(XS); V = np.concatenate(VS); D = ANODE[d] - X
        base = np.median(V)
        c, y, e = [], [], []
        for lo in range(0, 360, 40):
            s = (D >= lo) & (D < lo + 40)
            if s.sum() >= 30:
                c.append(lo + 20); y.append(np.median(V[s]) / base)
                e.append(1.2533 * np.std(V[s]) / np.sqrt(s.sum()) / base)
        P.errorbar(c, y, yerr=e, fmt="o-", color=COL[d], lw=1.8, ms=6, capsize=3,
                   label="%s (anode |x|=%.1f cm)" % (d.upper(), ANODE[d]))
    P.axhline(1, color="k", lw=.8)
    P.set_xlabel("drift distance = anode |x| - |x|   [cm]")
    P.set_ylabel("plateau dQ/dx / sample median")
    P.set_title("(c) No attenuation with drift on either detector\n(a lifetime effect would FALL toward large drift; neither does)")
    P.grid(alpha=.25); P.legend(fontsize=9)
    # (d) plateau dQ/dx vs |x| -- the max_abs_x derivation
    P = bx[1][1]
    for d in dets:
        XS, VS = [], []
        for st in ("s0", "s5"):
            tf = "%s/d50_%s_%s_tracks.tsv" % (a.ana, d, st); pf = "%s/d50_%s_%s_points.tsv" % (a.ana, d, st)
            if not os.path.exists(tf):
                continue
            i, rows = load_tracks(tf)
            keys = {r[i["event"]] + "#" + r[i["block"]] for r in rows if r[i["complete"]] == "1" and r[i["status"]] == "0"}
            if not keys:
                continue
            q = np.genfromtxt(pf, delimiter="\t", names=True, dtype=None, encoding="utf-8")
            k = np.array([e + "#" + str(b) for e, b in zip(q["event"], q["block"])])
            m = (np.isin(k, list(keys)) & (q["past_kink"] == 0) & np.isfinite(q["dqdx"]) & (q["dqdx"] > 0)
                 & (q["rr_kink"] >= 20) & (q["rr_kink"] < 80))
            XS.append(np.abs(q["x"][m])); VS.append(q["dqdx"][m])
        X = np.concatenate(XS); V = np.concatenate(VS)
        base = np.median(V[X < 250])
        c, y, e = [], [], []
        for lo in range(0, 360, 20):
            s = (X >= lo) & (X < lo + 20)
            if s.sum() >= 25:
                c.append(lo + 10); y.append(np.median(V[s]) / base)
                e.append(1.2533 * np.std(V[s]) / np.sqrt(s.sum()) / base)
        P.errorbar(c, y, yerr=e, fmt="o-", color=COL[d], lw=1.8, ms=6, capsize=3, label=d.upper())
    P.axhline(1, color="k", lw=.8)
    P.axvline(305, color="grey", ls="--", lw=1.5)
    P.text(307, 1.18, "the inherited\n--max-abs-x 305", fontsize=8, color="grey")
    P.fill_between([0, 360], 0.97, 1.03, color="k", alpha=.08, lw=0)
    P.set_xlim(0, 360); P.set_ylim(0.75, 1.30)
    P.set_xlabel("|x|   [cm]"); P.set_ylabel("plateau dQ/dx / (|x| < 250 cm median)")
    P.set_title("(d) PDVD RISES near its CRP, PDHD FALLS near its anodes\nthe 305 cut does not transfer")
    P.grid(alpha=.25); P.legend(fontsize=9)
    fig2.tight_layout(); fig2.savefig(os.path.join(a.figs, "50_dqdx_rr_diagnosis.png"), dpi=145)
    print("wrote", os.path.join(a.figs, "50_dqdx_rr_diagnosis.png"))


if __name__ == "__main__":
    raise SystemExit(main())
