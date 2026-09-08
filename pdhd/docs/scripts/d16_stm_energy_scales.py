#!/usr/bin/env python3
"""doc pdhd/16 -- the STM muon's energy scales: dQ/dx vs range, and the
recombination normalization that makes them agree.

Owner ask 2026-09-08: "the range estimation of muon energy is the baseline ...
the inverse of [the 450 V/cm] recombination model should be what we can use to
do dQ/dx -> dE/dx conversion ... the key question is whether this dQ/dx -> dE/dx
energy estimation of muon agrees with the range estimation?  If not, we need to
iterate on the recombination model."

This script answers that from products already on disk.  It reads
`T_stm_michel` (muon_ke_range, muon_ke_dqdx, muon_len, is_stm, ...) and
`T_stm_michel_pts` (per-point dQ/dx along the muon chain, role 1) out of an
arm's tracking-pr.root, recomputes the dQ/dx energy under a family of
recombination hypotheses, and fits the one free normalization that puts the
median dQ/dx energy on the range energy.

Nothing here is a tuning of a verdict: `is_stm` and every reject bit are decided
from the dQ/dx PROFILE and the PID *tables* (`do_track_comp` never invokes a
recombination model), so a change of recombination model cannot move them.

The recombination hypotheses
----------------------------
`Gen::PracticalBoxRecombination` (the live PDVD/PDHD model,
cfg/.../pr.jsonnet:1230) implements

    dQ/dx = ln(A + b'*dE/dx) / (b' * Wi),   b' = B/(rho*E)

with A=0.93, B=0.212, rho=1.38 and E the detector field.  The PID tables the
same config carries are the SAME expression TIMES 0.85
(energy_loss/pion_travel/convert_field.C:42,71).  The model therefore has no
carrier for that factor, and `dE()` on a measured dQ/dx lands 1/0.85 away from
the scale its own tables were built on.

`Gen::PowerBoxRecombination` (gen/src/RecombinationModels.cxx:143) does have
one:

    u = k*(dE/dx / pivot)^p,  R = ln(A+u)/u,  dQ/dx = C * R * (dE/dx) / Wi

and at p = 1, k = b'*pivot it IS the Modified Box at field E with C exposed.
That is the vehicle this round ships; C is what is fitted here.

Quadrature note
---------------
`segment_cal_kine_dQdx` (PRSegmentFunctions.cxx:2483) accumulates
dE = dE/dx(dQ/dx_i) * dX_i over fit points, where dX_i is the per-point fitted
path length.  `T_stm_michel_pts` persists dQ/dx and the arc length L but NOT the
per-point dx, so dX is taken as np.gradient(L) (centred differences = trapezoid
weights on the true arc length).  Gate G1 measures what that costs against the
chain's own number; it is quoted, not assumed.

BOTH of segment_cal_kine_dQdx's clamps are functions of dQ/dx alone and are
reproduced exactly:
  * dQ/dx > 1000 * 43e3 e/cm  =>  the point's charge is zeroed  (:2523)
  * dE > 50 MeV/cm * dX       =>  i.e. dE/dx clipped into [0, 50]  (:2533)
Dividing dQ/dx by C ~ 0.79 raises every inferred dE/dx by ~1/C, so the second
clamp fires MORE often after calibration; the fire counts are reported at C=1
and at the fitted C (gate G0).

Repro
-----
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
  python3 pdhd/docs/scripts/d16_stm_energy_scales.py --det pdvd \
      --arm 'pdvd/work/*_d15vnu' --out /home/xqian/tmp/d16/d16v
  python3 pdhd/docs/scripts/d16_stm_energy_scales.py --det pdhd \
      --arm 'pdhd/work/*_d15hnu' --out /home/xqian/tmp/d16/d16h
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import uproot

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.normpath(os.path.join(HERE, "..", "..", ".."))   # wcp-porting-img

# ---------------------------------------------------------------------------
# the model constants, from the configs
# ---------------------------------------------------------------------------
# cfg/pgrapher/experiment/protodunevd/pr.jsonnet:1230-1234  (pdvd_box_recomb)
# cfg/pgrapher/experiment/pdhd/pr.jsonnet:1245-1249         (pdhd_box_recomb)
BOX = {
    "pdvd": dict(A=0.93, B=0.212, E=0.45,   rho=1.38, Wi=23.6e-6),
    "pdhd": dict(A=0.93, B=0.212, E=0.4959, rho=1.38, Wi=23.6e-6),
}
PIVOT = 2.1          # MeV/cm, PowerBoxRecombination's pivot (RecombinationModels.h:106)
DEDX_MAX = 77.0      # MeV/cm, end of PowerBox's monotone branch (:108)
DQDX_SANITY = 1000 * 43e3   # e/cm, segment_cal_kine_dQdx:2523
DEDX_CLAMP = 50.0           # MeV/cm, segment_cal_kine_dQdx:2533
MMU = 105.658        # MeV, mcs/src/MuonMCS.cxx:37

# anode |x| in cm; drift distance = ANODE_ABS_X - |x|
#   PDVD: protodunevd clus.jsonnet dvm a0f0pA/a4f0pA FV_x = +-3399.1 mm
#   PDHD: cfg/pgrapher/experiment/pdhd/clus.jsonnet:492
ANODE_ABS_X = {"pdvd": 339.91, "pdhd": 357.985}


def beta_prime(det):
    p = BOX[det]
    return p["B"] / (p["rho"] * p["E"])


def k_at_p1(det):
    """PowerBox k that makes p=1 identical to the Modified Box at this field."""
    return beta_prime(det) * PIVOT


# ---------------------------------------------------------------------------
# the two inverses
# ---------------------------------------------------------------------------
def dedx_box(dqdx, det, C=1.0):
    """Gen::PracticalBoxRecombination::dE / dX, with the measured dQ/dx first
    divided by the normalization C (C=1 is the model exactly as configured)."""
    p = BOX[det]
    c = beta_prime(det)
    q = np.asarray(dqdx, float) / C
    with np.errstate(over="ignore"):
        return (np.exp(q * c * p["Wi"]) - p["A"]) / c


def power_forward(dedx, A, k, p, C, Wi):
    """PowerBoxRecombination::forward_dqdx (RecombinationModels.cxx:152)."""
    d = np.asarray(dedx, float)
    out = np.zeros_like(d)
    m = d > 0
    u = k * np.power(d[m] / PIVOT, p)
    out[m] = C * (np.log(A + u) / u) * d[m] / Wi
    return out


def dedx_power(dqdx, A, k, p, C, Wi, dedx_max=DEDX_MAX, nbis=60):
    """PowerBoxRecombination::dE / dX (RecombinationModels.cxx:164), vectorised.

    Same fixed-count bisection, same saturation at dedx_max, same `dqdx <= 0
    -> 0` branch.  NOTE the two differences from dedx_box that the equivalence
    doctest range does not see: this one SATURATES above the monotone branch,
    and returns 0 rather than a negative dE/dx for dQ/dx <= 0.
    """
    q = np.asarray(dqdx, float)
    out = np.zeros_like(q)
    top = power_forward(np.array([dedx_max]), A, k, p, C, Wi)[0]
    sat = q >= top
    live = (q > 0) & ~sat
    out[sat] = dedx_max
    if live.any():
        lo = np.zeros(live.sum())
        hi = np.full(live.sum(), dedx_max)
        ql = q[live]
        for _ in range(nbis):
            mid = 0.5 * (lo + hi)
            f = power_forward(mid, A, k, p, C, Wi)
            take = f < ql
            lo = np.where(take, mid, lo)
            hi = np.where(take, hi, mid)
        out[live] = 0.5 * (lo + hi)
    return out


def track_energy(dqdx, L, dedx_fn):
    """segment_cal_kine_dQdx's accumulation, with both clamps.

    Returns (E_MeV, n_sanity_fired, n_ceiling_fired)."""
    q = np.where(dqdx > DQDX_SANITY, 0.0, dqdx)          # :2523
    n_san = int((dqdx > DQDX_SANITY).sum())
    d = dedx_fn(q)
    n_ceil = int((d > DEDX_CLAMP).sum())
    d = np.clip(d, 0.0, DEDX_CLAMP)                      # :2533
    dX = np.gradient(L) if L.size > 1 else np.array([0.0])
    return float(np.sum(d * dX)), n_san, n_ceil


def momentum(ke):
    """p = sqrt((KE + m)^2 - m^2), the segment_cal_4mom idiom."""
    ke = np.asarray(ke, float)
    return np.where(ke > 0, np.sqrt(np.maximum((ke + MMU) ** 2 - MMU ** 2, 0.0)), -1.0)


# ---------------------------------------------------------------------------
# geometry labels (verbatim conventions of d51_dqdx_rr_apa.py:105-137)
# ---------------------------------------------------------------------------
def unit_geometric(det, x, z):
    x = np.asarray(x, float); z = np.asarray(z, float)
    if det == "pdhd":
        return np.where(z < 231.0, np.where(x < 0, 0, 1), np.where(x < 0, 2, 3)).astype(np.int64)
    return (x > 0).astype(np.int64)


def unit_labels(det):
    if det == "pdhd":
        return {0: "APA0 (x<0,face0)", 1: "APA1 (x>0,face1)",
                2: "APA2 (x<0,face0)", 3: "APA3 (x>0,face1)"}
    return {0: "bottom (x<0, anodes 0-3)", 1: "top (x>0, anodes 4-7)"}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
SCALARS = ["cluster_id", "is_stm", "reject_bits", "muon_len", "muon_ke_range",
           "muon_ke_dqdx", "muon_ke_best", "michel_ke_dqdx", "michel_ke_best",
           "michel_found", "n_live_pts", "n_dead_pts", "dead_frac_cmp",
           "contrast", "plateau_med", "ks_mu", "entry_x", "entry_y", "entry_z",
           "stop_x", "stop_y", "stop_z", "n_chain_segs",
           "tagger_stop_x", "tagger_stop_y", "tagger_stop_z", "stop_dis"]
MCS = ["muon_ke_mcs", "muon_mcs_amb", "muon_mcs_tracklen", "muon_mcs_nsegs",
       "muon_mcs_range_ke", "muon_mcs_bad_path"]


def load(arm_glob):
    """One row per candidate; role-1 point arrays carried alongside."""
    rows = []
    ndirs = nwith = 0
    for d in sorted(glob.glob(arm_glob)):
        fp = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(fp):
            continue
        ndirs += 1
        f = uproot.open(fp)
        keys = {k.split(";")[0] for k in f.keys()}
        if "T_stm_michel" not in keys or "T_stm_michel_pts" not in keys:
            continue
        nwith += 1
        run = f["Trun"].arrays(["runNo", "eventNo"], library="np")
        rn, en = int(run["runNo"][0]), int(run["eventNo"][0])
        avail = set(f["T_stm_michel"].keys())
        cols = [c for c in SCALARS + MCS if c in avail]
        m = f["T_stm_michel"].arrays(cols, library="np")
        p = f["T_stm_michel_pts"].arrays(library="np")
        for i in range(len(m["cluster_id"])):
            cid = int(m["cluster_id"][i])
            s = (p["cluster_id"] == cid) & (p["role"] == 1) & (p["rr"] >= 0)
            o = np.argsort(p["L"][s])
            r = {c: m[c][i] for c in cols}
            r.update(run=rn, event=en, evtdir=d, cluster=cid,
                     q=p["q"][s][o], L=p["L"][s][o], rr=p["rr"][s][o],
                     px=p["x"][s][o], py=p["y"][s][o], pz=p["z"][s][o])
            rows.append(r)
    return rows, ndirs, nwith


# ---------------------------------------------------------------------------
# the fit
# ---------------------------------------------------------------------------
def energies(rows, dedx_fn):
    e = np.empty(len(rows)); san = 0; ceil = 0
    for i, r in enumerate(rows):
        if r["L"].size < 2:
            e[i] = 0.0
            continue
        v, a, b = track_energy(r["q"], r["L"], dedx_fn)
        e[i] = v; san += a; ceil += b
    return e, san, ceil


def fit_C(rows, ref, make_fn, lo=0.4, hi=1.5, nbis=50):
    """Solve for C with median(E_dQdx(C) / ref) == 1."""
    for _ in range(nbis):
        mid = 0.5 * (lo + hi)
        e, _, _ = energies(rows, make_fn(mid))
        if np.median(e / ref) < 1.0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def bin_report(fh, title, key, ratio, edges, fmt="%g"):
    lines = ["%-28s %5s %8s %8s %8s" % (title, "n", "median", "p25", "p75")]
    for a, b in zip(edges[:-1], edges[1:]):
        s = (key >= a) & (key < b)
        if s.sum() >= 5:
            lines.append("  %-26s %5d %8.4f %8.4f %8.4f"
                         % (("%s-%s" % (fmt % a, fmt % b)), s.sum(),
                            np.median(ratio[s]), *np.percentile(ratio[s], [25, 75])))
    out = "\n".join(lines)
    print(out); fh.write("# " + out.replace("\n", "\n# ") + "\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=["pdvd", "pdhd"])
    ap.add_argument("--arm", required=True, help="glob of event dirs, e.g. 'pdvd/work/*_d15vnu'")
    ap.add_argument("--out", required=True, help="output prefix")
    ap.add_argument("--exclude-apa0", action="store_true",
                    help="PDHD: drop candidates whose stop point sits in APA0")
    ap.add_argument("--chain-C", type=float, default=1.0,
                    help="the normalization C the ARM itself ran with (1.0 for an "
                         "uncalibrated arm, 0.7941 pdvd / 0.8120 pdhd for a d16 arm). "
                         "Gate G1 reproduces the chain at THIS C; the fit below is "
                         "always reported as an absolute C, not a correction to it.")
    ap.add_argument("--compare", default=None,
                    help="glob of a BEFORE arm; report the branch-by-branch move "
                         "(which branches are bit-identical, which are not) and the "
                         "Michel spectrum on both")
    a = ap.parse_args()

    det = a.det
    g = a.arm if os.path.isabs(a.arm) else os.path.join(IMG, a.arm)
    rows, ndirs, nwith = load(g)
    print("%s: %d event dirs, %d with T_stm_michel, %d candidates"
          % (det, ndirs, nwith, len(rows)))

    keep = [r for r in rows
            if int(r["is_stm"]) == 1 and float(r["muon_ke_range"]) > 0 and r["L"].size >= 5]
    if a.exclude_apa0 and det == "pdhd":
        keep = [r for r in keep
                if unit_geometric(det, np.array([r["stop_x"]]), np.array([r["stop_z"]]))[0] != 0]
    print("  is_stm with a usable chain: %d%s" % (len(keep), "  (APA0 excluded)" if a.exclude_apa0 else ""))
    if not keep:
        raise SystemExit("no candidates")

    ref = np.array([float(r["muon_ke_range"]) for r in keep])
    cpp = np.array([float(r["muon_ke_dqdx"]) for r in keep])

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    fh = open(a.out + "_summary.tsv", "w")
    fh.write("# doc pdhd/16 d16_stm_energy_scales.py det=%s arm=%s ndirs=%d ncand=%d nfit=%d\n"
             % (det, a.arm, ndirs, len(rows), len(keep)))
    fh.write("# model: Modified Box A=%.2f B=%.3f rho=%.2f E=%.4f kV/cm Wi=%.4g;"
             " b'=%.6f cm/MeV; PowerBox k(p=1)=%.6f pivot=%.1f\n"
             % (BOX[det]["A"], BOX[det]["B"], BOX[det]["rho"], BOX[det]["E"],
                BOX[det]["Wi"], beta_prime(det), k_at_p1(det), PIVOT))

    # ---- G0/G1: the two inverses agree, and the python reproduces the C++ ----
    A, Wi = BOX[det]["A"], BOX[det]["Wi"]
    k1 = k_at_p1(det)
    probe = np.linspace(0.5, 50.0, 400)
    fwd_pow = power_forward(probe, A, k1, 1.0, 1.0, Wi)
    fwd_box = np.exp(0)  # placeholder, computed below
    c = beta_prime(det)
    fwd_box = np.log(A + c * probe) / (c * Wi)
    rel_fwd = float(np.max(np.abs(fwd_pow / fwd_box - 1.0)))
    inv_pow = dedx_power(fwd_box, A, k1, 1.0, 1.0, Wi)
    rel_inv = float(np.max(np.abs(inv_pow / probe - 1.0)))
    print("G0 PowerBox(p=1,k=b'*pivot,C=1) vs PracticalBox(E=%.4f): forward max rel %.2e, inverse max rel %.2e"
          % (BOX[det]["E"], rel_fwd, rel_inv))
    fh.write("G0_powerbox_equiv_forward_maxrel\t%.3e\n" % rel_fwd)
    fh.write("G0_powerbox_equiv_inverse_maxrel\t%.3e\n" % rel_inv)

    e1, san1, ceil1 = energies(keep, lambda q: dedx_box(q, det, a.chain_C))
    r_self = np.median(cpp / np.where(e1 > 0, e1, np.nan))
    npts = sum(r["L"].size for r in keep)
    print("G1 python E_dQdx(C=%.4f) vs chain muon_ke_dqdx: median ratio %.5f  (IQR %.5f-%.5f) over %d tracks / %d points"
          % (a.chain_C, r_self, *np.percentile(cpp / e1, [25, 75]), len(keep), npts))
    print("   clamps at C=%.4f: sanity %d, ceiling %d of %d points" % (a.chain_C, san1, ceil1, npts))
    fh.write("G1_python_vs_cpp_median\t%.6f\n" % r_self)
    fh.write("G1_npoints\t%d\n" % npts)
    fh.write("G0b_clamp_sanity_C1\t%d\nG0b_clamp_ceiling_C1\t%d\n" % (san1, ceil1))

    # ---- 0b: saturation and non-positive charge census ---------------------
    qall = np.concatenate([r["q"] for r in keep])
    print("0b role-1 dQ/dx: max %.0f e/cm, n<=0 %d of %d" % (qall.max(), int((qall <= 0).sum()), qall.size))
    fh.write("0b_qmax_e_per_cm\t%.1f\n0b_n_nonpositive\t%d\n" % (qall.max(), int((qall <= 0).sum())))

    # ---- the headline ratio, uncalibrated ---------------------------------
    rat1 = cpp / ref
    print("\nHEADLINE  muon_ke_dqdx / muon_ke_range (as the arm ran): median %.4f  IQR %.4f-%.4f  n=%d"
          % (np.median(rat1), *np.percentile(rat1, [25, 75]), len(keep)))
    fh.write("ratio_C1_median\t%.4f\n" % np.median(rat1))

    # ---- the fit ----------------------------------------------------------
    C = fit_C(keep, ref, lambda cc: (lambda q: dedx_box(q, det, cc)))
    eC, sanC, ceilC = energies(keep, lambda q: dedx_box(q, det, C))
    ratC = eC / ref
    # bootstrap
    rng = np.random.default_rng(20260908)
    bs = []
    idx = np.arange(len(keep))
    for _ in range(200):
        j = rng.choice(idx, idx.size, replace=True)
        sub = [keep[t] for t in j]
        bs.append(fit_C(sub, ref[j], lambda cc: (lambda q: dedx_box(q, det, cc)), nbis=30))
    print("\nFIT  C = %.4f +- %.4f (bootstrap 200)   -> ratio median %.4f  IQR %.4f-%.4f  rms(log) %.3f"
          % (C, np.std(bs), np.median(ratC), *np.percentile(ratC, [25, 75]), np.std(np.log(ratC))))
    print("     clamps at C: sanity %d, ceiling %d of %d points" % (sanC, ceilC, npts))
    fh.write("fit_C\t%.5f\nfit_C_err\t%.5f\n" % (C, np.std(bs)))
    fh.write("G0b_clamp_sanity_Cfit\t%d\nG0b_clamp_ceiling_Cfit\t%d\n" % (sanC, ceilC))

    # what the tables' 0.85 alone would predict, and doc 50's k
    print("     for reference: the tables' fudge alone is 0.85; doc pdvd/50 sec 14.1 k_pop"
          " gives C ~ 0.85*k_pop")

    # ---- separation: is the residual a normalization or a shape? ----------
    L = np.array([float(r["muon_len"]) for r in keep])
    print()
    Lb = [0, 80, 120, 180, 250, 1e9]
    bin_report(fh, "ratio(C=%.4f) vs muon_len cm" % C, L, ratC, Lb, fmt="%.0f")
    xm = 0.5 * (np.abs([float(r["entry_x"]) for r in keep]) + np.abs([float(r["stop_x"]) for r in keep]))
    drift = ANODE_ABS_X[det] - xm
    print()
    bin_report(fh, "ratio vs mean drift cm", drift, ratC, [0, 60, 120, 180, 240, 400], fmt="%.0f")

    # a free power, and a free field, both against C-only
    def chi2_of(fn, nbin=5):
        e, _, _ = energies(keep, fn)
        r = e / ref
        tot = 0.0
        for lo, hi in zip(Lb[:-1], Lb[1:]):
            s = (L >= lo) & (L < hi)
            if s.sum() < 5:
                continue
            med = np.median(r[s])
            err = 1.2533 * np.std(np.log(r[s])) / np.sqrt(s.sum())
            tot += (np.log(med) / max(err, 0.01)) ** 2
        return tot

    chi_C = chi2_of(lambda q: dedx_box(q, det, C))
    best = (chi_C, 1.0, C)
    for p in (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2):
        Cp = fit_C(keep, ref, lambda cc, p=p: (lambda q: dedx_power(q, A, k1, p, cc, Wi)), nbis=32)
        ch = chi2_of(lambda q, p=p, Cp=Cp: dedx_power(q, A, k1, p, Cp, Wi))
        if ch < best[0]:
            best = (ch, p, Cp)
        print("  power p=%.2f -> C=%.4f  chi2(length bins)=%.2f" % (p, Cp, ch))
    print("  BOX  p=1.00 -> C=%.4f  chi2(length bins)=%.2f   [shipped unless dchi2 demands otherwise]"
          % (C, chi_C))
    fh.write("chi2_len_C_only\t%.3f\nbest_power_p\t%.2f\nbest_power_C\t%.4f\nbest_power_chi2\t%.3f\n"
             % (chi_C, best[1], best[2], best[0]))
    for E in (0.40, 0.45, 0.4959, 0.55, 0.60):
        sav = BOX[det]["E"]; BOX[det]["E"] = E
        CE = fit_C(keep, ref, lambda cc: (lambda q: dedx_box(q, det, cc)), nbis=32)
        eE, _, _ = energies(keep, lambda q: dedx_box(q, det, CE))
        print("  field E=%.4f kV/cm -> C=%.4f  rms(log ratio)=%.4f" % (E, CE, np.std(np.log(eE / ref))))
        fh.write("fieldscan_E%.4f_C\t%.4f\n" % (E, CE))
        BOX[det]["E"] = sav

    # ---- per readout unit -------------------------------------------------
    print()
    u = unit_geometric(det, np.array([float(r["stop_x"]) for r in keep]),
                       np.array([float(r["stop_z"]) for r in keep]))
    lab = unit_labels(det)
    for uu in sorted(lab):
        s = u == uu
        if s.sum() >= 3:
            print("  %-26s n=%3d ratio median %.4f" % (lab[uu], s.sum(), np.median(ratC[s])))
            fh.write("unit_%d_n\t%d\nunit_%d_ratio\t%.4f\n" % (uu, s.sum(), uu, np.median(ratC[s])))

    # ---- the length baseline control --------------------------------------
    # A chain that stops short of the true path biases E_range LOW, so it would
    # be absorbed into C.  Two probes, neither of them the vacuous
    # span-vs-muon_len identity (muon_len IS the profile's total length):
    #   (a) the ratio's flatness in muon_len above -- a missing constant end
    #       piece delta would show up as a length-dependent ratio, and does not;
    #   (b) the distance between the module's stop point and the STM tagger's
    #       own stop, which is an independent reconstruction of the same end.
    d_stop = np.array([float(np.hypot(np.hypot(r["stop_x"] - r["tagger_stop_x"],
                                               r["stop_y"] - r["tagger_stop_y"]),
                                      r["stop_z"] - r["tagger_stop_z"]))
                       for r in keep]) if "tagger_stop_x" in keep[0] else None
    if d_stop is not None:
        print("\nlength control: |stop - tagger_stop| median %.2f cm, p90 %.2f, >2 cm on %d/%d"
              % (np.median(d_stop), np.percentile(d_stop, 90), int((d_stop > 2).sum()), d_stop.size))
        fh.write("len_stop_mismatch_median_cm\t%.3f\nlen_stop_mismatch_gt2cm\t%d\n"
                 % (np.median(d_stop), int((d_stop > 2).sum())))
        bin_report(fh, "ratio vs |stop-tagger_stop| cm", d_stop, ratC,
                   [0, 1, 2, 5, 1e9], fmt="%.0f")

    # ---- MCS, when the arm has it ----------------------------------------
    if "muon_ke_mcs" in keep[0]:
        mk = np.array([float(r["muon_ke_mcs"]) for r in keep])
        am = np.array([float(r["muon_mcs_amb"]) for r in keep])
        ok = mk > 0
        print("\nMCS: computed on %d/%d (%.1f%%); amb<0.2 on %d (%.1f%%)"
              % (ok.sum(), ok.size, 100.0 * ok.sum() / ok.size,
                 int((ok & (am < 0.2)).sum()), 100.0 * (ok & (am < 0.2)).sum() / ok.size))
        for name, sel in (("all computed", ok), ("amb<0.2", ok & (am < 0.2))):
            if sel.sum() >= 5:
                print("  ke_MCS/ke_range %-12s n=%3d median %.4f IQR %.4f-%.4f"
                      % (name, sel.sum(), np.median(mk[sel] / ref[sel]),
                         *np.percentile(mk[sel] / ref[sel], [25, 75])))
                fh.write("mcs_%s_n\t%d\nmcs_%s_median\t%.4f\n"
                         % (name.replace(" ", "_"), sel.sum(),
                            name.replace(" ", "_"), np.median(mk[sel] / ref[sel])))

    # ---- before/after: WHICH branches move ---------------------------------
    # The recombination model is on no verdict path (do_track_comp reads the
    # PID *tables*, never a model), so `is_stm` matching is not evidence -- it
    # is my own reasoning restated.  The branches a RE-RUN can move are the ones
    # fed by preload_clusters -> prepare_data (doc pdhd/15 sec 7's companion
    # perturbation), which is why contrast/plateau_med/ks_mu/muon_len are
    # listed explicitly below: if THOSE are bit-identical, then is_stm being
    # identical means something.
    if a.compare:
        gb = a.compare if os.path.isabs(a.compare) else os.path.join(IMG, a.compare)
        rows_b, _, _ = load(gb)
        key = lambda r: (r["run"], r["event"], r["cluster"])
        Bm = {key(r): r for r in rows_b}
        Am = {key(r): r for r in rows}
        common = sorted(set(Am) & set(Bm))
        print("\nBEFORE/AFTER  %s -> %s : %d / %d candidates, %d common"
              % (a.compare, a.arm, len(rows_b), len(rows), len(common)))
        fh.write("cmp_before\t%s\ncmp_n_before\t%d\ncmp_n_after\t%d\ncmp_n_common\t%d\n"
                 % (a.compare, len(rows_b), len(rows), len(common)))
        shared = [c for c in SCALARS if c in rows_b[0] and c in rows[0]]
        ident, moved = [], []
        for c in shared:
            x = np.array([float(Bm[k][c]) for k in common])
            y = np.array([float(Am[k][c]) for k in common])
            (ident if np.array_equal(np.nan_to_num(x), np.nan_to_num(y)) else moved).append(c)
        print("  bit-identical (%d): %s" % (len(ident), " ".join(ident)))
        print("  MOVED (%d): %s" % (len(moved), " ".join(moved)))
        fh.write("cmp_identical\t%s\ncmp_moved\t%s\n"
                 % (",".join(ident), ",".join(moved)))
        for c in ("is_stm", "reject_bits", "contrast", "plateau_med", "ks_mu",
                  "muon_len", "n_live_pts", "michel_found"):
            if c in shared:
                same = c in ident
                print("    %-14s %s" % (c, "identical" if same else "*** MOVED ***"))
        for c in ("muon_ke_dqdx", "michel_ke_dqdx"):
            if c in shared:
                x = np.array([float(Bm[k][c]) for k in common])
                y = np.array([float(Am[k][c]) for k in common])
                nz = x > 0
                if nz.sum():
                    print("    %-14s after/before median %.4f on %d rows"
                          % (c, float(np.median(y[nz] / x[nz])), int(nz.sum())))
                    fh.write("cmp_ratio_%s\t%.4f\n" % (c, float(np.median(y[nz] / x[nz]))))
        # the Michel spectrum, before and after -- an absolute scale the fit never saw
        for tag, M in (("before", Bm), ("after", Am)):
            ke = np.array([float(M[k]["michel_ke_dqdx"]) for k in common
                           if int(M[k].get("michel_found") or 0) == 1
                           and float(M[k]["muon_len"]) >= 10])
            if ke.size:
                print("  Michel michel_ke_dqdx %-6s n=%3d med %.1f p90 %.1f max %.1f | >52.8 MeV: %d"
                      % (tag, ke.size, np.median(ke), np.percentile(ke, 90), ke.max(),
                         int((ke > 52.8).sum())))
                fh.write("michel_%s_n\t%d\nmichel_%s_p90\t%.2f\nmichel_%s_over528\t%d\n"
                         % (tag, ke.size, tag, float(np.percentile(ke, 90)), tag, int((ke > 52.8).sum())))

    # ---- per-track table --------------------------------------------------
    with open(a.out + "_tracks.tsv", "w") as tf:
        tf.write("run\tevent\tcluster\tmuon_len\tke_range\tke_dqdx_cpp\tke_dqdx_C\tratio_C1\tratio_C"
                 "\tdrift\tunit\tnpts\n")
        for i, r in enumerate(keep):
            tf.write("%d\t%d\t%d\t%.2f\t%.2f\t%.2f\t%.2f\t%.4f\t%.4f\t%.1f\t%d\t%d\n"
                     % (r["run"], r["event"], r["cluster"], L[i], ref[i], cpp[i], eC[i],
                        rat1[i], ratC[i], drift[i], u[i], r["L"].size))
    fh.close()
    print("\nwrote %s_{summary,tracks}.tsv" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
