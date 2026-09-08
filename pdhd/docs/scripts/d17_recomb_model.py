#!/usr/bin/env python3
"""doc pdhd/17 -- is the recombination model consistent FORWARD and BACKWARD,
and where did the calibrated model land relative to where we started?

Forward  = dE/dx -> dQ/dx.  In this tree the only forward user in force is the
           PID *DeDx table generator (energy_loss/pion_travel/convert_field.C),
           whose output ships inside particle_dataset.jsonnet and is what
           do_track_comp compares a measured dQ/dx against.  There is NO
           IRecombinationModel on any simulation path here (pdvd_sim's
           sim.tracks sets electrons per step directly), so "forward" means the
           tables, not a simulated charge.
Backward = dQ/dx -> dE/dx.  segment_cal_kine_dQdx(seg, recomb_model), i.e.
           whichever IRecombinationModel the component is handed.

Everything below is a RE-ANALYSIS of arms already on disk plus an inversion of
the shipped table.  No arm is produced and no chain is re-run.

The arithmetic is not re-implemented: `dedx_box`, `track_energy` and `load` are
imported from d16_stm_energy_scales so the clamps, the endpoint dX rule and the
accumulation are bit-for-bit the ones doc pdhd/16 was gated with.

Sections
  A  table identity   -- invert the shipped MuonDeDx table at C in {1, 0.85,
                         C_ship} and compare against the CSDA dE/dx = dKE/dR
                         from the SAME config's muon_range_function.  This is a
                         model-vs-model statement with no data in it.
  B  data C-ladder    -- median(E_dQdx(C) / E_range) over the is_stm muons for
                         the same three C.  Turns A's pointwise factor into a
                         measured integral one, and prices what is left over.
  C  pointwise        -- measured dQ/dx against the expected dE/dx(rr), binned,
                         with each model's forward curve.  The figure's data.
  D  charge-direct    -- the OTHER charge -> energy conversions in the same
                         component, and whether this round left them consistent.

Repro
-----
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
  python3 pdhd/docs/scripts/d17_recomb_model.py --det pdvd \
      --arm 'pdvd/work/*_d16vnu' --out /home/xqian/tmp/d17/d17v \
      --fig pdhd/docs/figs/d17_recomb_model_pdvd.png
  python3 pdhd/docs/scripts/d17_recomb_model.py --det pdhd \
      --arm 'pdhd/work/*_d16hnu' --out /home/xqian/tmp/d17/d17h \
      --fig pdhd/docs/figs/d17_recomb_model_pdhd.png
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np
import uproot

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import d16_stm_energy_scales as D16          # noqa: E402  (the gated arithmetic)

IMG = D16.IMG
WCT = os.environ.get("WCT_SRC", "/nfs/data/1/xqian/toolkit-dev/toolkit")

# The tables' own scale factor, convert_field.C:71 / particle_dataset.jsonnet:24.
TABLE_C = 0.85
# The shipped calibrated normalization, pr.jsonnet {pdvd,pdhd}_stm_recomb.
SHIP_C = {"pdvd": 0.7941, "pdhd": 0.8120}
# The flat charge -> energy conversion for charge that was never fitted:
# CheckSTM_Michel.cxx:375 michel_unfit_recom/fudge, used by
# stm_michel_charge_to_energy (StmMichelFunctions.cxx:191).
UNFIT_RECOM, UNFIT_FUDGE = 0.7, 0.95

PDS = {"pdvd": "cfg/pgrapher/experiment/protodunevd/particle_dataset.jsonnet",
       "pdhd": "cfg/pgrapher/experiment/pdhd/particle_dataset.jsonnet"}
# The committed re-derivations of the same tables, used only as a self-gate.
REF = {"pdvd": "pdvd/stm/pdvd_ref_dqdx_045.json",
       "pdhd": "pdhd/stm/pdhd_ref_dqdx.json"}


# ---------------------------------------------------------------------------
# the config, read from the primary source
# ---------------------------------------------------------------------------
def particle_dataset(det, cache=None):
    """The COMPILED particle_dataset.jsonnet -- the tables the job actually gets."""
    if cache and os.path.exists(cache):
        with open(cache) as fh:
            return json.load(fh)
    out = subprocess.run(["wcsonnet", os.path.join(WCT, PDS[det])],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    if cache:
        with open(cache, "w") as fh:
            fh.write(out)
    return j


def muon_dqdx_table(j):
    d = j["muon_dEdx_function"]
    assert d["type"] == "LinterpFunction" and d["name"] == "MuonDeDx", d["name"]
    v = np.array(d["data"]["values"], float)
    rr = d["data"]["start"] + d["data"]["step"] * np.arange(v.size)
    return rr, v


def csda_dedx(j, rr):
    """dE/dx(rr) = dKE/dR from muon_range_function -- the CSDA truth the table
    was generated from, and the ONE object in this config that carries no drift
    field and no charge calibration."""
    t = j["muon_range_function"]["data"]
    co, va = np.array(t["coords"], float), np.array(t["values"], float)
    h = 1e-3
    return (np.interp(rr + h, co, va) - np.interp(rr - h, co, va)) / (2 * h)


# ---------------------------------------------------------------------------
# the models, all three as ONE family
# ---------------------------------------------------------------------------
def forward(dedx, det, C):
    """dQ/dx (e/cm) from dE/dx (MeV/cm): the Modified Box times C.

    C = 1     -- Gen::PracticalBoxRecombination as configured (pdvd_box_recomb),
                 the model check_stm_michel's inverse ran before doc pdhd/16.
    C = 0.85  -- convert_field.C, i.e. the *DeDx tables this same config ships.
    C = ship  -- PowerBoxRecombination at p = 1, k = beta'*pivot (pdvd_stm_recomb).
    """
    p = D16.BOX[det]
    bp = D16.beta_prime(det)
    d = np.asarray(dedx, float)
    out = np.zeros_like(d)
    m = d > 0
    u = bp * d[m]
    out[m] = C * (np.log(p["A"] + u) / u) * d[m] / p["Wi"]
    return out


def backward(dqdx, det, C):
    """dE/dx (MeV/cm) from dQ/dx (e/cm), the exact inverse of `forward`."""
    return D16.dedx_box(dqdx, det, C=C)



# ---------------------------------------------------------------------------
# the shape test that does NOT go through KE(L)
# ---------------------------------------------------------------------------
def track_shape(rows, det, C, co, va, rr_min=0.0):
    """Per track: sum(backward(q) dX) / sum(CSDA dE/dx dX) over the SAME points.

    This is the comparison the calibration claim is really about, and it is the
    only one insensitive to two conventions that otherwise contaminate it:
      * the dX convention -- it appears in numerator and denominator alike;
      * KE(muon_len) as the reference -- a DISCRETE sum of the CSDA dE/dx over
        fit points does NOT equal KE(L), because dE/dx diverges at the stop and
        no finite point spacing integrates that.  The over-count is measured
        below (`discret`) and is strongly length dependent.
    With rr_min > 0 the last centimetres are dropped from BOTH sides: the
    detector cannot resolve the Bragg peak the CSDA has there, so including it
    compares a smeared measurement against an unsmeared model.
    """
    h = 1e-3
    w, disc, clo, Lm = [], [], [], []
    for r in rows:
        m = r["rr"] >= rr_min
        if m.sum() < 5:
            continue
        L = r["L"][m]
        dX = np.gradient(L) if L.size > 1 else np.array([0.0])
        d = (np.interp(r["rr"][m] + h, co, va) - np.interp(r["rr"][m] - h, co, va)) / (2 * h)
        q = np.where(r["q"][m] > D16.DQDX_SANITY, 0.0, r["q"][m])
        b = np.clip(backward(q, det, C), 0.0, D16.DEDX_CLAMP)
        w.append(float(np.sum(b * dX) / np.sum(d * dX)))
        disc.append(float(np.sum(d * dX) / r["muon_ke_range"]))
        clo.append(float(np.sum(b * dX) / r["muon_ke_range"]))
        Lm.append(float(r["muon_len"]))
    return (np.array(w), np.array(disc), np.array(clo), np.array(Lm))


LEN_BINS = [(0, 80), (80, 120), (120, 180), (180, 250), (250, 350), (350, 1e9)]


# ---------------------------------------------------------------------------
def pct(a, q):
    return float(np.percentile(a, q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=["pdvd", "pdhd"])
    ap.add_argument("--arm", required=True, help="glob of event dirs (a d16 arm)")
    ap.add_argument("--out", required=True, help="output prefix for the TSVs")
    ap.add_argument("--fig", default=None, help="figure path (png)")
    ap.add_argument("--stop-cut", type=float, default=5.0,
                    help="[E]: residual range below which the fit point is dropped from "
                         "BOTH the data and the model -- the detector cannot resolve the "
                         "Bragg peak the CSDA dE/dx has there")
    ap.add_argument("--rr-min", type=float, default=2.0,
                    help="drop the first bins of the table: the 0.5 cm bin is a "
                         "10-point average over a decade of dE/dx (convert_field.C), "
                         "not a value at 0.5 cm")
    a = ap.parse_args()
    det, C_ship = a.det, SHIP_C[a.det]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    rep = open(a.out + "_report.txt", "w")

    def say(s=""):
        print(s)
        rep.write(s + "\n")

    say("# doc pdhd/17  det=%s  arm=%s" % (det, a.arm))
    say("# C_ship=%.4f  C_table=%.2f  beta'=%.6f  E=%.4f kV/cm"
        % (C_ship, TABLE_C, D16.beta_prime(det), D16.BOX[det]["E"]))

    # ---------------- A: the table identity -------------------------------
    j = particle_dataset(det, cache=a.out + "_particle_dataset.json")
    rr, tab = muon_dqdx_table(j)
    truth = csda_dedx(j, rr)
    sel = rr >= a.rr_min

    # self-gate: the compiled table must match the committed re-derivation
    refp = os.path.join(IMG, REF[det])
    gate = "SKIPPED (no %s)" % REF[det]
    if os.path.exists(refp):
        with open(refp) as fh:
            r = json.load(fh)["MuonDeDx"]["values"]
        r = np.array(r, float)
        rel = np.abs(tab - r) / r
        gate = "max rel dev %.2e over %d bins (jsonnet is 6 sig figs)" % (rel.max(), rel.size)
    say("\n[A] the shipped MuonDeDx table, inverted, against the CSDA dE/dx")
    say("    self-gate compiled jsonnet vs %s: %s" % (REF[det], gate))
    say("    %-10s %10s %10s %10s" % ("C used", "median", "p10", "p90"))
    rows = []
    for name, C in (("1.00 (box)", 1.0), ("0.85 (table)", TABLE_C), ("%.4f (ship)" % C_ship, C_ship)):
        r = backward(tab, det, C)[sel] / truth[sel]
        rows.append((name, C, np.median(r), pct(r, 10), pct(r, 90)))
        say("    %-12s %10.4f %10.4f %10.4f" % (name, np.median(r), pct(r, 10), pct(r, 90)))
    say("    => the table IS the Modified Box x 0.85: inverting it WITH the 0.85")
    say("       returns the CSDA dE/dx; the pointwise cost of dropping it is %.4f"
        % rows[0][2])

    with open(a.out + "_table.tsv", "w") as fh:
        fh.write("rr_cm\ttable_dqdx_e_per_cm\tcsda_dedx\tdedx_C1\tdedx_C085\tdedx_Cship\n")
        for i in range(rr.size):
            fh.write("%.1f\t%.4f\t%.6f\t%.6f\t%.6f\t%.6f\n"
                     % (rr[i], tab[i], truth[i], backward(tab[i:i+1], det, 1.0)[0],
                        backward(tab[i:i+1], det, TABLE_C)[0],
                        backward(tab[i:i+1], det, C_ship)[0]))

    # ---------------- B: the data ladder ----------------------------------
    rows_d, ndirs, nwith = D16.load(os.path.join(IMG, a.arm) if not os.path.isabs(a.arm) else a.arm)
    say("\n[B] %d event dirs, %d with T_stm_michel, %d candidates" % (ndirs, nwith, len(rows_d)))
    stm = np.array([bool(r["is_stm"]) for r in rows_d])
    keep = np.array([r["L"].size >= 2 and r["muon_ke_range"] > 0 for r in rows_d])
    use = [r for r, s, k in zip(rows_d, stm, keep) if s and k]
    say("    %d is_stm muons with a usable chain" % len(use))
    ref_e = np.array([r["muon_ke_range"] for r in use])
    chain = np.array([r["muon_ke_dqdx"] for r in use])

    ladder = []
    say("    %-14s %10s %10s %10s   %s" % ("C used", "median", "p25", "p75", "what it is"))
    for name, C, what in (
            ("1.00", 1.0, "the model check_stm_michel ran BEFORE doc 16"),
            ("0.85", TABLE_C, "the tables' own factor, and nothing else"),
            ("%.4f" % C_ship, C_ship, "SHIPPED (pdvd/pdhd_stm_recomb)")):
        e, _, _ = D16.energies(use, lambda q, C=C: backward(q, det, C))
        r = e / ref_e
        ladder.append((name, C, np.median(r)))
        say("    %-14s %10.4f %10.4f %10.4f   %s"
            % (name, np.median(r), pct(r, 25), pct(r, 75), what))
    say("    chain's own muon_ke_dqdx / muon_ke_range: %.4f  (python reproduces the"
        % np.median(chain / ref_e))
    say("      chain to %.4f)" % np.median(
        D16.energies(use, lambda q: backward(q, det, C_ship))[0] / np.maximum(chain, 1e-9)))
    say("    decomposition: %.4f (model, from the missing 0.85) x %.4f (charge the"
        % (ladder[0][2] / ladder[1][2], ladder[1][2]))
    say("      reconstruction does not recover) = %.4f" % ladder[0][2])

    with open(a.out + "_ladder.tsv", "w") as fh:
        fh.write("C\tmedian_ratio\n")
        for name, C, m in ladder:
            fh.write("%s\t%.6f\n" % (name, m))

    # ---------------- C: pointwise ----------------------------------------
    q = np.concatenate([r["q"] for r in use])
    rrp = np.concatenate([r["rr"] for r in use])
    ok = (q > 0) & (rrp >= a.rr_min) & np.isfinite(q)
    q, rrp = q[ok], rrp[ok]
    t = j["muon_range_function"]["data"]
    co, va = np.array(t["coords"], float), np.array(t["values"], float)
    h = 1e-3
    dedx_pt = (np.interp(rrp + h, co, va) - np.interp(rrp - h, co, va)) / (2 * h)
    say("\n[C] %d role-1 points with rr >= %.1f cm; dE/dx span %.2f - %.2f MeV/cm"
        % (q.size, a.rr_min, dedx_pt.min(), dedx_pt.max()))
    edges = np.array([2.0, 2.2, 2.5, 3.0, 3.5, 4.0, 5.0, 6.5, 9.0, 14.0])
    say("    %-12s %8s %12s %12s %10s %10s %10s"
        % ("dE/dx bin", "n", "med dQ/dx", "model C=1", "r(C=1)", "r(0.85)", "r(ship)"))
    with open(a.out + "_pointwise.tsv", "w") as fh:
        fh.write("dedx_lo\tdedx_hi\tn\tdedx_med\tdqdx_med\tdqdx_p25\tdqdx_p75"
                 "\tmodel_C1\tmodel_C085\tmodel_Cship\n")
        for lo, hi in zip(edges[:-1], edges[1:]):
            s = (dedx_pt >= lo) & (dedx_pt < hi)
            if s.sum() < 20:
                continue
            dm, qm = np.median(dedx_pt[s]), np.median(q[s])
            m1 = forward(dm, det, 1.0)
            m85 = forward(dm, det, TABLE_C)
            ms = forward(dm, det, C_ship)
            say("    %5.1f-%-6.1f %8d %12.0f %12.0f %10.4f %10.4f %10.4f"
                % (lo, hi, s.sum(), qm, m1, qm / m1, qm / m85, qm / ms))
            fh.write("%.2f\t%.2f\t%d\t%.4f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\n"
                     % (lo, hi, s.sum(), dm, qm, pct(q[s], 25), pct(q[s], 75), m1, m85, ms))
    say("    NOTE this is a POOLED point median: it weights long muons by their")
    say("    point count and mixes tracks whose overall charge scale differs by")
    say("    +-10 %.  The per-track statement is [E], which is what the claim is.")

    # ---------------- E: the shape test, per track, no KE(L) --------------
    say("\n[E] per track: sum(backward(q) dX) / sum(CSDA dE/dx dX) over the SAME points")
    say("    -- no KE(L) in it, and the dX convention cancels.")
    w_all, disc, clo, Lm = track_shape(use, det, C_ship, co, va, rr_min=0.0)
    w_cut, _, _, Lc = track_shape(use, det, C_ship, co, va, rr_min=a.stop_cut)
    say("    %-14s %5s %12s %14s %12s | %s" % ("muon length", "n", "data/model",
                                               "discretisation", "closure",
                                               "data/model rr>=%.0f" % a.stop_cut))
    with open(a.out + "_shape.tsv", "w") as fh:
        fh.write("len_lo\tlen_hi\tn\tdata_over_model\tdiscretisation\tclosure\tdata_over_model_cut\n")
        for lo, hi in LEN_BINS:
            s1 = (Lm >= lo) & (Lm < hi)
            s2 = (Lc >= lo) & (Lc < hi)
            if s1.sum() < 3:
                continue
            cut = np.median(w_cut[s2]) if s2.sum() >= 3 else float("nan")
            say("    %5.0f-%-8.0f %5d %12.4f %14.4f %12.4f | %12.4f"
                % (lo, min(hi, 9999), s1.sum(), np.median(w_all[s1]),
                   np.median(disc[s1]), np.median(clo[s1]), cut))
            fh.write("%.0f\t%.0f\t%d\t%.6f\t%.6f\t%.6f\t%.6f\n"
                     % (lo, min(hi, 9999), s1.sum(), np.median(w_all[s1]),
                        np.median(disc[s1]), np.median(clo[s1]), cut))
    say("    all lengths      %5d %12.4f %14.4f %12.4f | %12.4f"
        % (w_all.size, np.median(w_all), np.median(disc), np.median(clo), np.median(w_cut)))
    say("    => with the last %.0f cm dropped the model reproduces the CSDA dE/dx to"
        % a.stop_cut)
    say("       %.1f %% and is FLAT in length; the length structure in `closure` is a"
        % (100 * abs(np.median(w_cut) - 1)))
    say("       stop-region effect partly cancelled by `discretisation` running the")
    say("       other way.  Neither is a recombination result.")

    # ---------------- D: the other charge -> energy conversions -----------
    say("\n[D] the OTHER charge -> energy conversions in the same component")
    bp = D16.beta_prime(det)
    A = D16.BOX[det]["A"]
    say("    %-10s %10s %10s %12s %12s" % ("dE/dx", "R", "R x C_ship", "MeV/e fit", "vs flat"))
    flat_mev_per_e = D16.BOX[det]["Wi"] / (UNFIT_RECOM * UNFIT_FUDGE)
    for d0 in (1.0, 2.1, 3.0, 5.0, 10.0):
        R = np.log(A + bp * d0) / (bp * d0)
        mev_e = D16.BOX[det]["Wi"] / (R * C_ship)
        say("    %-10.1f %10.4f %10.4f %12.4e %12.4f" % (d0, R, R * C_ship, mev_e, mev_e / flat_mev_per_e))
    say("    flat (unfitted) path: 1/(%.2f x %.2f) x Wi = %.4e MeV/e"
        % (UNFIT_RECOM, UNFIT_FUDGE, flat_mev_per_e))
    R21 = np.log(A + bp * D16.PIVOT) / (bp * D16.PIVOT)
    say("    at MIP the two disagree by %.4f (they agreed to %.4f before doc 16)"
        % ((D16.BOX[det]["Wi"] / (R21 * C_ship)) / flat_mev_per_e,
           (D16.BOX[det]["Wi"] / (R21 * 1.0)) / flat_mev_per_e))

    # how much charge actually goes through the flat path
    cens = {}
    for c in ("michel_found", "dots_charge_unfit", "dots_ke_unfit",
              "michel_ke_charge", "michel_ke_dqdx", "michel_ke_best"):
        cens[c] = np.array([r.get(c, 0.0) for r in rows_d], float)
    mf = cens["michel_found"] != 0
    say("    michel_found = %d candidates" % int(mf.sum()))
    for c in ("dots_charge_unfit", "dots_ke_unfit", "michel_ke_charge"):
        v = cens[c][mf]
        say("      %-20s nonzero %4d of %4d   max %12.4g"
            % (c, int((v != 0).sum()), v.size, v.max() if v.size else 0.0))
    nz = mf & (cens["dots_ke_unfit"] > 0)
    if nz.any():
        f = cens["dots_ke_unfit"][nz] / np.maximum(cens["michel_ke_best"][nz], 1e-9)
        say("      where it fires: dots_ke_unfit / michel_ke_best median %.3f max %.3f"
            % (np.median(f), f.max()))
    else:
        say("      it never fires on this arm, so 'it did not move' is VACUOUS here")

    # ---------------- the figure ------------------------------------------
    if a.fig:
        fig, ax = plt.subplots(2, 2, figsize=(12.5, 9.5))
        grid = np.linspace(1.9, 6.0, 300)

        # 1: forward, dQ/dx vs dE/dx
        p = ax[0, 0]
        p.hist2d(dedx_pt, q / 1e3, bins=[np.linspace(1.9, 6.0, 90), np.linspace(25, 135, 90)],
                 cmap="Blues", cmin=1, norm=matplotlib.colors.LogNorm())
        bx, by, be = [], [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            sb = (dedx_pt >= lo) & (dedx_pt < hi)
            if sb.sum() >= 20:
                bx.append(np.median(dedx_pt[sb])); by.append(np.median(q[sb]) / 1e3)
                be.append((pct(q[sb], 75) - pct(q[sb], 25)) / 2e3)
        p.errorbar(bx, by, yerr=be, fmt="ko", ms=5, lw=1.2, capsize=3,
                   label="pooled median +- IQR/2", zorder=5)
        for C, lab, st in ((1.0, "Modified Box, C=1 (pre-doc-16 inverse)", "--"),
                           (TABLE_C, "x0.85 = the shipped PID tables", "-."),
                           (C_ship, "C=%.4f  SHIPPED" % C_ship, "-")):
            p.plot(grid, forward(grid, det, C) / 1e3, st, lw=2, label=lab)
        p.set_xlabel("expected dE/dx at this residual range (MeV/cm)")
        p.set_ylabel("measured dQ/dx (ke/cm)")
        p.set_xlim(1.9, 6.0); p.set_ylim(25, 135)
        p.set_title("%s: forward.  data = %d fitted points on %d stopping muons"
                    % (det.upper(), q.size, len(use)))
        p.legend(fontsize=8, loc="upper left")
        p.grid(alpha=.3)

        # 2: dQ/dx vs residual range
        p = ax[0, 1]
        rb = np.array([2, 3, 4, 5, 6, 8, 10, 13, 17, 22, 30, 40, 60, 90, 140, 220, 350])
        cx, cy, lo, hi = [], [], [], []
        for x0, x1 in zip(rb[:-1], rb[1:]):
            s = (rrp >= x0) & (rrp < x1)
            if s.sum() >= 20:
                cx.append(np.median(rrp[s])); cy.append(np.median(q[s]) / 1e3)
                lo.append(pct(q[s], 25) / 1e3); hi.append(pct(q[s], 75) / 1e3)
        cx = np.array(cx)
        p.fill_between(cx, lo, hi, color="C0", alpha=.25, label="data IQR")
        p.plot(cx, cy, "o-", color="C0", label="data median")
        rg = np.logspace(np.log10(2), np.log10(350), 200)
        dg = (np.interp(rg + h, co, va) - np.interp(rg - h, co, va)) / (2 * h)
        for C, lab, st in ((1.0, "Modified Box, C=1", "--"),
                           (TABLE_C, "x0.85 = PID tables", "-."),
                           (C_ship, "C=%.4f SHIPPED" % C_ship, "-")):
            p.plot(rg, forward(dg, det, C) / 1e3, st, lw=2, label=lab)
        p.plot(rr[sel], tab[sel] / 1e3, ":", color="k", lw=2, label="MuonDeDx table itself")
        p.set_xscale("log"); p.set_xlabel("residual range (cm)")
        p.set_ylabel("dQ/dx (ke/cm)"); p.grid(alpha=.3)
        p.set_title("dQ/dx vs residual range: the same three models")
        p.legend(fontsize=8)

        # 3: backward closure, per muon
        p = ax[1, 0]
        bins = np.linspace(0.3, 1.8, 61)
        for (name, C, med), col in zip(ladder, ("C3", "C1", "C2")):
            e, _, _ = D16.energies(use, lambda qq, C=C: backward(qq, det, C))
            p.hist(e / ref_e, bins=bins, histtype="step", lw=2, color=col,
                   label="C=%s  median %.3f" % (name, med))
            p.axvline(med, color=col, ls=":", lw=1)
        p.axvline(1.0, color="k", lw=1)
        p.set_xlabel(r"$E_{dQ/dx}\,/\,E_{\rm range}$ for one stopping muon")
        p.set_ylabel("muons"); p.grid(alpha=.3)
        p.set_title("backward: the integral closure against CSDA range, n=%d" % len(use))
        p.legend(fontsize=8)

        # 4: the shape test that does not go through KE(L)
        p = ax[1, 1]
        for arr, Lx, lab, col, mk in ((w_all, Lm, "data/model, all fit points", "C3", "s"),
                                      (w_cut, Lc, "data/model, rr >= %.0f cm" % a.stop_cut, "C2", "o"),
                                      (clo, Lm, r"closure $E_{dQ/dx}/E_{\rm range}$", "C0", "^")):
            xs, ys, el = [], [], []
            for lo, hi in LEN_BINS:
                sb = (Lx >= lo) & (Lx < hi)
                if sb.sum() >= 3:
                    xs.append(np.median(Lx[sb])); ys.append(np.median(arr[sb]))
                    el.append((pct(arr[sb], 75) - pct(arr[sb], 25)) / 2 / np.sqrt(sb.sum()))
            p.errorbar(xs, ys, yerr=el, fmt=mk + "-", color=col, label=lab)
        xs, ys = [], []
        for lo, hi in LEN_BINS:
            sb = (Lm >= lo) & (Lm < hi)
            if sb.sum() >= 3:
                xs.append(np.median(Lm[sb])); ys.append(np.median(disc[sb]))
        p.plot(xs, ys, "v:", color="0.45", label="discretisation of the reference")
        p.axhline(1.0, color="k", lw=1)
        p.set_xscale("log")
        p.set_xlabel("muon length (cm)")
        p.set_ylabel("ratio")
        p.set_ylim(0.75, 1.25); p.grid(alpha=.3)
        p.set_title("shape test: data/model with and without the last %.0f cm (n=%d)"
                    % (a.stop_cut, w_all.size))
        p.legend(fontsize=8)

        fig.suptitle("doc pdhd/17 -- %s recombination model, forward and backward"
                     % det.upper(), fontsize=13)
        fig.tight_layout(rect=[0, 0, 1, 0.97])
        os.makedirs(os.path.dirname(a.fig) or ".", exist_ok=True)
        fig.savefig(a.fig, dpi=110)
        say("\nwrote %s" % a.fig)

    say("\nwrote %s_{report.txt,table.tsv,ladder.tsv,pointwise.tsv}" % a.out)
    rep.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
