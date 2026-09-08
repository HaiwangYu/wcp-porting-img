#!/usr/bin/env python3
"""doc pdhd/14 -- the two energy estimators CheckSTM_Michel itself uses.

The chain persists a Michel energy (`michel_ke_dqdx/_range/_best`, `dots_ke_dqdx`)
but NO muon energy: `set_pdg` (CheckSTM_Michel.cxx:658-665) builds a 4-momentum
with `segment_cal_4mom(seg, 13, ...)` and hangs it on the segment, and nothing
ever writes it out.  So the scan display has to recompute it, and this module
does that by reproducing the two toolkit functions exactly rather than inventing
a third estimator:

  ke_dqdx()   <- PRSegmentFunctions.cxx:2483  segment_cal_kine_dQdx
  ke_range()  <- PRSegmentFunctions.cxx:2673  cal_kine_range

Both are GATED against the production binary, not asserted -- see group L of
selftest_stm_michel_scan.py.  `dots_ke_dqdx` is the gate target for ke_dqdx
because CheckSTM_Michel.cxx:1262 fills it as a plain sum of
segment_cal_kine_dQdx over the dot segments, one segment at a time.
`michel_ke_dqdx` is NOT usable as a gate: `build_michel_shower` defaults true
(CheckSTM_Michel.cxx:312) and is not overridden by the job's stm_michel_knobs bag, so :1221-1222 fill
them from Shower::calculate_kinematics -- a MULTI-segment sum over the shower's
members, which is a different quantity.  Measured 2026-09-07 on the doc-13
census arms: PDHD 44/44 and PDVD 60/60 dot-carrying candidates agree to better
than 0.2 %.

Units in and out: dQ in electrons (the RAW fit.dQ, i.e. T_rec_charge's `q`
un-scaled by Trun's dQdx_scale/offset -- PdvdPrMagnifyTrackingVisitor.cxx:966),
dx and lengths in cm, energies in MeV.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RANGE_TABLES = os.path.join(HERE, "range_tables.json")

# Modified-Box recombination, the parameter sets the taggers actually receive.
# PDVD: cfg/pgrapher/experiment/protodunevd/pr.jsonnet:1231-1234 (pdvd_box_recomb)
# PDHD: cfg/pgrapher/experiment/pdhd/pr.jsonnet:1246-1248        (pdhd_box_recomb)
# Both are type 'PracticalBoxRecombination' -- PRACTICAL units (kV/cm,
# (kV/cm)(g/cm^2)/MeV, g/cm^3), NOT WCT units; doc 88 explains why the class
# exists.  `use_power_recomb` is false in production on both detectors, so the
# power-box branch is never the model in force and is deliberately not
# implemented here.
RECOMB = {
    "pdhd": dict(A=0.93, B=0.212, E=0.4959, rho=1.38, Wi=23.6e-6),
    "pdvd": dict(A=0.93, B=0.212, E=0.45,   rho=1.38, Wi=23.6e-6),
}

# The MIP operating point used only to label a raw-charge sum in MeV.  2.1
# MeV/cm is the same pivot the PowerBoxRecombination fit uses
# (RecombinationModels.h:104, `pivot`).
MIP_DEDX_MEV_PER_CM = 2.1

# segment_cal_kine_dQdx's two guards, kept as named constants so the self-test
# can assert them against the C++ rather than against a magic number.
DQDX_SANITY_MIP = 43e3     # :2525  dQ/dx / (43e3/cm) > 1000  => dQ := 0
DE_CLAMP_MEV_PER_CM = 50.0  # :2535  dE clamped into [0, 50 MeV/cm * dX]
ENDPOINT_DX_FACTOR = 1.5    # :2512, :2518  first/last dx > 1.5 * inter-point distance


def _coeff(p):
    """The Box model's quenching coefficient, B / (E * rho)."""
    return p["B"] / (p["E"] * p["rho"])


def dedx_from_dqdx(dqdx_e_per_cm, det):
    """MeV/cm from e/cm -- Gen::PracticalBoxRecombination::dE / dX.

    dE(dQ,dX) = (exp(dQ/dX * coeff * Wi) - A) * dX / coeff   (MeV),
    so dE/dx depends on dQ/dx alone.  The model is non-linear, which is why
    segment_cal_kine_dQdx is careful to evaluate it at the TRUE fitted dx even
    when it accumulates over a shortened one.
    """
    p = RECOMB[det]
    c = _coeff(p)
    return (np.exp(np.asarray(dqdx_e_per_cm, float) * c * p["Wi"]) - p["A"]) / c


def dqdx_at_mip(det):
    """e/cm that the Box model maps to MIP_DEDX_MEV_PER_CM -- the model inverted."""
    p = RECOMB[det]
    c = _coeff(p)
    return np.log(p["A"] + MIP_DEDX_MEV_PER_CM * c) / (c * p["Wi"])


def mev_per_electron_mip(det):
    """MeV per collected electron for charge deposited at MIP dE/dx.

    The ONLY honest way to put a MeV number on a cluster that was never fitted:
    with no dx there is no dQ/dx, so there is no recombination correction to
    make and the conversion has to assume one.  Everything quoted through this
    function must be labelled MIP-equivalent.  It is an over-estimate for
    denser deposits (more quenching than assumed) -- the SBND EM campaign
    measured an 0.84-0.86 charge-scale fudge on showers (doc pr/126), which is
    the size of the systematic being waved at here.
    """
    return MIP_DEDX_MEV_PER_CM / dqdx_at_mip(det)


def ke_dqdx(dQ_e, dx_cm, xyz, det):
    """segment_cal_kine_dQdx (PRSegmentFunctions.cxx:2483), point for point.

    dQ_e     raw electrons per fit point (fit.dQ)
    dx_cm    the fitted path length per point, cm (fit.dx)
    xyz      (n, 3) fit points, cm -- only the first/last inter-point distances
             are used, for the endpoint shortening rule at :2509-2520
    """
    dQ = np.asarray(dQ_e, float)
    dx = np.asarray(dx_cm, float)
    P = np.asarray(xyz, float)
    n = dQ.size
    if n == 0:
        return 0.0

    # The accumulation path dX starts as the fitted dx and is shortened only at
    # the two endpoints, where the fit window reaches past the segment end.
    # dQ/dx is ALWAYS evaluated on the unshortened dx (:2508) -- shortening it
    # there would inflate dQ/dx and, the model being non-linear, bias the
    # energy upward.
    dX = dx.copy()
    if n > 1:
        for i, j in ((0, 1), (n - 1, n - 2)):
            dis = float(np.linalg.norm(P[i] - P[j]))
            if dis > 0 and dX[i] > dis * ENDPOINT_DX_FACTOR:
                dX[i] = dis

    good = (dx > 0) & (dX > 0)
    if not good.any():
        return 0.0
    with np.errstate(over="ignore"):
        dqdx = np.where(good, dQ / np.where(dx > 0, dx, 1.0), 0.0)
        dqdx = np.where(dqdx / DQDX_SANITY_MIP > 1000, 0.0, dqdx)  # :2523
        dE = dedx_from_dqdx(dqdx, det) * dX
    dE = np.clip(dE, 0.0, DE_CLAMP_MEV_PER_CM * dX)                # :2533
    return float(dE[good].sum())


# ---------------------------------------------------------------------------
# range -> kinetic energy
# ---------------------------------------------------------------------------
_TABLES = None

# cal_kine_range's pdg -> table name map (:2677-2690); anything else falls back
# to the muon table, exactly as the C++ does at :2694.
PDG_TABLE = {11: "electron", 13: "muon", 211: "pion", 321: "kaon", 2212: "proton"}


def tables(path=RANGE_TABLES):
    """The LinterpFunction tables, loaded once.

    Regenerate with `python3 smkine.py --dump`.  Group L does NOT re-derive
    them from the jsonnet -- it checks something stronger and cheaper: L1
    demands the CHAIN's own muon_ke_range equal np.interp on this table, over
    904 candidates at 0.0 MeV error, which fails the moment either side drifts.
    """
    global _TABLES
    if _TABLES is None:
        with open(path) as fh:
            _TABLES = json.load(fh)
    return _TABLES


def ke_range(L_cm, pdg, det):
    """cal_kine_range (PRSegmentFunctions.cxx:2673) -- MeV from a track length.

    Aux::LinterpFunction is plain linear interpolation on irregular points with
    END-POINT EXTRAPOLATION (LinterpFunction.cxx:9-11), which is what np.interp
    does by default, so this is exact and not an approximation.
    """
    t = tables()[det][PDG_TABLE.get(abs(int(pdg)), "muon")]
    return float(np.interp(float(L_cm), t["coords"], t["values"]))


def _dump(out=RANGE_TABLES):
    """Re-extract the range tables from each detector's particle_dataset.jsonnet."""
    import subprocess
    src = {
        "pdhd": "cfg/pgrapher/experiment/pdhd/particle_dataset.jsonnet",
        "pdvd": "cfg/pgrapher/experiment/protodunevd/particle_dataset.jsonnet",
    }
    root = os.environ.get("WCT_SRC", "/nfs/data/1/xqian/toolkit-dev/toolkit")
    doc = {"_source": {k: v for k, v in src.items()},
           "_note": "generated by smkine.py --dump; coords = range cm, values = KE MeV"}
    for det, rel in src.items():
        j = json.loads(subprocess.run(["wcsonnet", os.path.join(root, rel)],
                                      capture_output=True, text=True, check=True).stdout)
        doc[det] = {}
        for name in ("muon", "electron", "pion", "kaon", "proton"):
            d = j["%s_range_function" % name]
            assert d["type"] == "LinterpFunction", (det, name, d["type"])
            doc[det][name] = dict(coords=d["data"]["coords"], values=d["data"]["values"])
    with open(out, "w") as fh:
        json.dump(doc, fh, separators=(",", ":"), sort_keys=True)
    return out


if __name__ == "__main__":
    import sys
    if "--dump" in sys.argv:
        print("wrote", _dump())
    else:
        for det in sorted(RECOMB):
            print("%s: MIP dQ/dx %.0f e/cm, %.4e MeV/e (MIP-equivalent);"
                  " 100 cm muon = %.1f MeV"
                  % (det, dqdx_at_mip(det), mev_per_electron_mip(det),
                     ke_range(100.0, 13, det)))
