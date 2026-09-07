#!/usr/bin/env python3
"""doc pdvd/50 sec 4.2 -- anatomy of the per-point charge deficit, PDHD and PDVD
through one code path (the doc-42 --det convention).

Consumes only d50_dqdx_rr_cross.py's <out>_points.tsv, so every panel is
regenerable from the doc's Repro block.

Readout-unit assignment is GEOMETRIC, from the production wire files:

  PDHD  (protodunehd-wires-larsoft-v1.json.bz2)   4 APAs
      APA0: x<0, z< 231      APA1: x>0, z< 231
      APA2: x<0, z>=231      APA3: x>0, z>=231
    and cfg/pgrapher/experiment/pdhd/clus.jsonnet groups them
      APA0+APA2 = face 0 (drift -x),  APA1+APA3 = face 1 (drift +x),
    i.e. on PDHD the sign of x IS the drift volume.

  PDVD  (protodunevd-wires-larsoft-v7-uvwfit.json.bz2)   8 anodes x 2 faces
      x = +-341.6 ; y split at -168.5, 0, +168.5 ; z split at ~150
    = 16 CRP quadrants, 2 drift volumes x 4 y bands x 2 z bands.

Usage:
  python3 d50_deficit_plots.py --det pdhd --ana ANA --figs .../figs
  python3 d50_deficit_plots.py --det pdvd --ana ANA --figs .../figs
"""
import argparse, json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CNEG, CPOS = "#c1272d", "#0b6fa4"

DET = {
    "pdhd": dict(
        plateau=54609.2,
        ref="/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd/stm/pdhd_ref_dqdx.json",
        ylim=(0, 607), zlim=(0, 463), ylines=[], zlines=[231.0],
        unit_name="APA",
        volume_label={-1: "x < 0   (APA0 | APA2, face 0)", 1: "x > 0   (APA1 | APA3, face 1)"},
    ),
    "pdvd": dict(
        plateau=53965.5,
        ref="/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd/stm/pdvd_ref_dqdx_045.json",
        ylim=(-337, 337), zlim=(0, 299), ylines=[-168.5, 0.0, 168.5], zlines=[149.7],
        unit_name="CRP",
        volume_label={-1: "x < 0   (8 CRP quadrants)", 1: "x > 0   (8 CRP quadrants)"},
    ),
}


def units(det, x, y, z):
    """Return (index, label list). Index enumerates the detector's readout units."""
    d = DET[det]
    zb = np.digitize(z, d["zlines"])
    yb = np.digitize(y, d["ylines"]) if d["ylines"] else np.zeros_like(z, int)
    nz, ny = len(d["zlines"]) + 1, (len(d["ylines"]) + 1 if d["ylines"] else 1)
    if det == "pdhd":                       # keep the physical APA numbering
        idx = np.where(z < 231, np.where(x < 0, 0, 1), np.where(x < 0, 2, 3))
        return idx, ["APA0\nx<0", "APA1\nx>0", "APA2\nx<0", "APA3\nx>0"], [0, 1, 0, 1]
    vb = (x > 0).astype(int)
    idx = vb * (nz * ny) + zb * ny + yb
    labs, vols = [], []
    for v in range(2):
        for iz in range(nz):
            for iy in range(ny):
                labs.append("%s\nz%d y%d" % ("x>0" if v else "x<0", iz, iy))
                vols.append(v)
    return idx, labs, vols


def load(ana, det):
    d = np.genfromtxt("%s/d50_%s_s0_points.tsv" % (ana, det), delimiter="\t",
                      names=True, dtype=None, encoding="utf-8")
    m = (d["past_kink"] == 0) & np.isfinite(d["dqdx"]) & (d["dqdx"] > 0)
    return {k: d[k][m] for k in d.dtype.names}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=sorted(DET))
    ap.add_argument("--ana", required=True)
    ap.add_argument("--figs", required=True)
    a = ap.parse_args()
    D = DET[a.det]
    PLAT = D["plateau"]; LOW = 0.40 * PLAT
    t = json.load(open(D["ref"]))["MuonDeDx"]
    xg = t["start"] + t["step"] * np.arange(len(t["values"]))
    yg = np.asarray(t["values"], float)
    table = lambda rr: np.interp(rr, xg, yg)

    p = load(a.ana, a.det)
    x, y, z, v, rr = p["x"], p["y"], p["z"], p["dqdx"], p["rr_kink"]
    uidx, ulab, uvol = units(a.det, x, y, z)
    neg = x < 0
    plat = (rr >= 40) & (rr < 60)
    key = np.array([e + "#" + str(b) for e, b in zip(p["event"], p["block"])])
    other = "pdvd" if a.det == "pdhd" else "pdhd"
    q = load(a.ana, other)
    mq = (q["rr_kink"] >= 40) & (q["rr_kink"] < 60)

    fig, ax = plt.subplots(2, 3, figsize=(19.5, 10.6))

    # (a) plateau dQ/dx split by drift volume, with the other detector as control
    P = ax[0][0]
    bins = np.arange(0, 120001, 4000)
    for msk, c, lab in [(neg, CNEG, D["volume_label"][-1]), (~neg, CPOS, D["volume_label"][1])]:
        s = plat & msk
        P.hist(v[s], bins=bins, histtype="step", lw=2.2, color=c, density=True,
               label="%s\n   n=%d, median %.1f ke/cm" % (lab, s.sum(), np.median(v[s]) / 1e3))
    P.hist(q["dqdx"][mq], bins=bins, histtype="step", lw=1.6, color="grey", ls="--", density=True,
           label="%s control (both volumes)\n   median %.1f ke/cm" % (other.upper(), np.median(q["dqdx"][mq]) / 1e3))
    tv = float(np.median(table(rr[plat])))
    P.axvline(tv, color="k", lw=2, ls=":")
    P.text(tv * 1.03, P.get_ylim()[1] * 0.86, "expected\n%.1f ke/cm" % (tv / 1e3), fontsize=8.5)
    P.set_xlabel("dQ/dx  [e/cm]   (plateau points, rr 40-60 cm)")
    P.set_ylabel("points (normalised)")
    P.set_title("(a) %s plateau charge, split by drift volume" % a.det.upper())
    P.grid(alpha=.25); P.legend(fontsize=7.4, loc="upper right")

    # (b) per readout unit: all points vs the surviving points
    P = ax[0][1]
    n_u = len(ulab)
    vals, errs, surv, dead, ns, cols = [], [], [], [], [], []
    for U in range(n_u):
        s = plat & (uidx == U)
        if s.sum() < 40:
            vals.append(np.nan); errs.append(0); surv.append(np.nan); dead.append(np.nan)
            ns.append(int(s.sum())); cols.append(CPOS if uvol[U] else CNEG); continue
        r = v[s] / table(rr[s])
        vals.append(float(np.median(r)))
        errs.append(float(1.2533 * 1.4826 * np.median(np.abs(r - np.median(r))) / np.sqrt(s.sum())))
        surv.append(float(np.median(r[r > 0.5])))
        dead.append(float((r < 0.5).mean()))
        ns.append(int(s.sum())); cols.append(CPOS if uvol[U] else CNEG)
    w = 0.38
    P.bar(np.arange(n_u) - w / 2, vals, yerr=errs, color=cols, capsize=3, width=w, label="all plateau points")
    P.bar(np.arange(n_u) + w / 2, surv, color=cols, width=w, alpha=.42, hatch="///",
          edgecolor="k", label="only points above 0.5 x plateau")
    fs = 9 if n_u <= 6 else 6.5
    for i in range(n_u):
        if not np.isfinite(vals[i]): continue
        P.text(i - w / 2, vals[i] + .03, "%.2f" % vals[i], ha="center", fontweight="bold", fontsize=fs)
        P.text(i, .05, "%.0f%%" % (100 * dead[i]), ha="center", fontsize=fs)
    P.axhline(1, color="k", lw=1.5)
    P.set_xticks(range(n_u)); P.set_xticklabels(ulab, fontsize=7 if n_u > 6 else 9)
    P.set_ylim(0, 1.42); P.set_ylabel("plateau dQ/dx / expectation  (no free scale)")
    P.legend(fontsize=8, loc="upper center")
    P.set_title("(b) per %s: all points (solid) vs surviving points (hatched)\n"
                "the %% is the share killed below 0.5 x plateau" % D["unit_name"])
    P.grid(alpha=.25, axis="y")

    # (c,d) deficient-fraction maps, one per drift volume
    for col, (msk, sgn) in enumerate([(neg, -1), (~neg, 1)]):
        P = ax[0][2] if col == 0 else ax[1][0]
        zb = np.linspace(D["zlim"][0], D["zlim"][1], 24)
        yb = np.linspace(D["ylim"][0], D["ylim"][1], 20)
        lo = np.histogram2d(z[msk & (v < LOW)], y[msk & (v < LOW)], bins=[zb, yb])[0]
        al = np.histogram2d(z[msk], y[msk], bins=[zb, yb])[0]
        with np.errstate(invalid="ignore", divide="ignore"):
            f = np.where(al >= 25, lo / al, np.nan)
        im = P.pcolormesh(zb, yb, f.T, cmap="Reds" if sgn < 0 else "Blues", vmin=0, vmax=1, shading="flat")
        plt.colorbar(im, ax=P, label="fraction below 0.4 x plateau")
        for zl in D["zlines"]: P.axvline(zl, color="k", lw=2)
        for yl in D["ylines"]: P.axhline(yl, color="k", lw=1.4)
        P.set_xlabel("z  [cm]"); P.set_ylabel("y  [cm]")
        P.set_title("(%s) charge-deficient fraction, %s" % ("c" if col == 0 else "d", D["volume_label"][sgn]))

    # (e) one typical track from each drift volume
    P = ax[1][1]
    tgt = {}
    for U in range(n_u):
        pass
    for want_neg, cc, lab in [(True, CNEG, "x < 0"), (False, CPOS, "x > 0")]:
        s_all = plat & (neg if want_neg else ~neg)
        aim = float(np.median(v[s_all])) if s_all.sum() else PLAT
        best = None
        for k in sorted(set(key.tolist())):
            m2 = key == k
            if m2.sum() < 120: continue
            share = neg[m2].mean()
            if want_neg and share < 0.9: continue
            if (not want_neg) and share > 0.1: continue
            dd = abs(float(np.median(v[m2])) - aim)
            if best is None or dd < best[0]: best = (dd, k)
        if best:
            m2 = key == best[1]
            o = np.argsort(p["i"][m2]); vv = v[m2][o]
            P.plot(np.arange(len(vv)) * 0.6, vv / 1e3, "-", lw=1.4, color=cc,
                   label="%s  %s\n   median %.1f ke/cm, %d pts"
                         % (lab, best[1].split("_d")[0], np.median(vv) / 1e3, len(vv)))
    P.axhline(PLAT / 1e3, color="k", ls=":", lw=1.8)
    P.text(2, PLAT / 1e3 + 4, "muon plateau expectation", fontsize=8.5)
    P.axhline(LOW / 1e3, color="grey", ls="--", lw=1.2)
    P.text(2, LOW / 1e3 + 3, "deficient threshold (0.4 x plateau)", fontsize=7.5, color="grey")
    P.set_ylim(0, 150); P.set_xlabel("distance along the fitted trajectory  [cm]")
    P.set_ylabel("dQ/dx  [ke/cm]")
    P.set_title("(e) %s: one typical track from each drift volume" % a.det.upper())
    P.grid(alpha=.25); P.legend(fontsize=7.8, loc="upper right")

    # (f) per-event ratio between the two drift volumes
    P = ax[1][2]
    rows = []
    for e in sorted(set(p["event"].tolist())):
        A = plat & (p["event"] == e) & neg
        B = plat & (p["event"] == e) & (~neg)
        if A.sum() >= 40 and B.sum() >= 40:
            rows.append(float(np.median(v[A]) / np.median(v[B])))
    rows = np.array(rows)
    if len(rows):
        P.hist(rows, bins=np.linspace(0, 2.0, 21), color="#7b3294", alpha=.8, edgecolor="k")
        P.axvline(1, color="k", lw=2)
        P.axvline(np.median(rows), color="#c1272d", lw=2.4, ls="--", label="median %.2f" % np.median(rows))
        P.legend(fontsize=9)
        P.set_title("(f) %s: per-event volume ratio\n%d/%d events below 0.8"
                    % (a.det.upper(), (rows < 0.8).sum(), len(rows)))
    P.set_xlabel("plateau dQ/dx :  median(x<0) / median(x>0),  per event")
    P.set_ylabel("events"); P.grid(alpha=.25, axis="y")

    fig.tight_layout()
    out = os.path.join(a.figs, "50_%s_deficit_anatomy.png" % a.det)
    fig.savefig(out, dpi=140); print("wrote", out)
    print("  plateau medians: x<0 %.0f   x>0 %.0f   ratio %.3f"
          % (np.median(v[plat & neg]), np.median(v[plat & ~neg]),
             np.median(v[plat & neg]) / np.median(v[plat & ~neg])))
    for U in range(n_u):
        if np.isfinite(vals[U]):
            print("   %-12s all %.3f   surviving %.3f   killed %.0f %%   (%d pts)"
                  % (ulab[U].replace("\n", " "), vals[U], surv[U], 100 * dead[U], ns[U]))


if __name__ == "__main__":
    raise SystemExit(main())
