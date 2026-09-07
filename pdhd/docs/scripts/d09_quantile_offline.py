#!/usr/bin/env python3
"""doc pdhd/09 -- per-exit-end miss rate for each candidate tagger boundary.

The PDHD port of pdvd/docs/nf_sp_img_clus/scripts/fv_quantile_offline.py.  This is
the PRIMARY grading number of the campaign: of the ends that genuinely EXIT through
a wall, what fraction would the boundary wrongly call CONTAINED?  A tagger that
calls an exiting end contained fails to tag a through-going muon, so this ranks the
ladder without running a single arm.

The flat baseline is PDHD PRODUCTION, read off the compiled config, not assumed:
wct-pr-perevt.jsonnet sets tgm_fv_y_margin=17.5 and tgm_fv_z{min,max}_margin=18, i.e.
TaggerCheckTGM's fv_tolerance = [-20,-20,-175,-175,-180,-180] WCT mm.  That 15 cm
(+ the dvm margins 2.5 / 3) is the flat space-charge allowance the surface replaces.

There is no d50 branch: PDHD never measured a charge-density median surface, because
doc pdvd/41 sec 13.3 withdrew that estimator for endpoint use before this port began.

Run-split cross-validation is free here in a way it was not on PDVD: the two runs
029107 and 028084 are independent, so a surface built on one can be graded on the
other.  PDVD could only split events within a single running period.

Repro:
  python3 docs/scripts/d09_quantile_offline.py /home/xqian/tmp/d09/exits_rows.json \
      --table /home/xqian/tmp/d09/q_table.json --out /home/xqian/tmp/d09/off
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d09_fv_pdhd import XW, CATH, YLO, YHI, ZLO, ZHI, WALLS, VOLS, BIN_EDGES
from d09_quantile_surface import (readout_clipped, quantile_table, knots_from_profile,
                                  QUANTILES, GAP_MAX, JN)

# PDHD production tagger margins (cm), from the compiled TaggerCheckTGM fv_tolerance
BOX_MARGIN = {"y": 17.5, "z": 18.0}


def knot_inset(knots, xabs):
    """Piecewise-linear inset at |x| from [|x|, inset] knots (anode -> cathode)."""
    xs = np.array([k[0] for k in knots])[::-1]
    ys = np.array([k[1] for k in knots])[::-1]
    return float(np.interp(xabs, xs, ys))


class Boundary:
    def __init__(self, name, kind, cushion, knots=None):
        self.name, self.kind, self.cushion, self.knots = name, kind, cushion, knots

    def inset(self, wall, vol, xabs):
        if self.kind == "flat":
            return BOX_MARGIN["y"] if wall[0] == "y" else BOX_MARGIN["z"]
        return knot_inset(self.knots[JN[(wall, vol)]], xabs) + self.cushion


def miss_rate(rows, B, half=None):
    """(n, misses, floor-expected misses).  An exit end is 'missed' when the
    boundary calls it contained, i.e. its gap exceeds the inset there.  The floor
    term is how many of those the flat NON-exit background accounts for -- a
    stopping muon's stop end is a legitimate non-exit and should not be charged
    to the boundary."""
    sel = [r for r in rows if r["wall"] in WALLS and not readout_clipped(r)
           and (not half or r["half"] == half)]
    n = miss = 0
    for r in sel:
        if r["dmin"] >= GAP_MAX:
            continue
        vol = "g02" if r["x"] < 0 else "g13"
        n += 1
        if max(r["dmin"], 0.0) > B.inset(r["wall"], vol, abs(r["x"])):
            miss += 1
    fl = 0.0
    for w in WALLS:
        for vol in VOLS:
            sub = [r for r in sel if r["wall"] == w and ((r["x"] < 0) == (vol == "g02"))]
            if not sub:
                continue
            g = np.array([r["dmin"] for r in sub])
            dens = ((g >= 40.0) & (g < 150.0)).sum() / 110.0
            xs = [abs(r["x"]) for r in sub if r["dmin"] < GAP_MAX]
            if xs:
                fl += dens * float(np.mean([max(GAP_MAX - B.inset(w, vol, x), 0.0) for x in xs]))
    return n, miss, fl


def build_knots(rows, q, rng):
    T = quantile_table(rows, BIN_EDGES, QUANTILES, 0, rng, (40.0, 150.0))
    return {JN[(w, v)]: knots_from_profile(T[w][v]["center"], T[w][v][f"q{q}_pav"])
            for w in WALLS for v in VOLS}


def report(rows, bounds, label):
    print(f"\n=== {label}  (n = {len(rows)} ends) ===")
    print(f"{'boundary':22s} {'n':>5s} {'miss':>6s} {'miss%':>7s} {'floor-corr%':>11s} "
          f"{'anode%':>7s} {'cathode%':>8s}")
    out = {}
    for B in bounds:
        n, m, fl = miss_rate(rows, B)
        na, ma, _ = miss_rate(rows, B, "anode")
        nc, mc, _ = miss_rate(rows, B, "cathode")
        pct = 100*m/max(n, 1); cor = 100*max(m-fl, 0)/max(n, 1)
        print(f"{B.name:22s} {n:5d} {m:6d} {pct:6.1f}% {cor:10.1f}% "
              f"{100*ma/max(na,1):6.1f}% {100*mc/max(nc,1):7.1f}%")
        out[B.name] = dict(n=n, miss=m, pct=pct, floor_corrected_pct=cor,
                           anode_pct=100*ma/max(na, 1), cathode_pct=100*mc/max(nc, 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--out", default="/home/xqian/tmp/d09/off")
    ap.add_argument("--cushions", type=float, nargs="+", default=[3.0, 5.0])
    a = ap.parse_args()

    rows = json.load(open(a.rows))
    rng = np.random.default_rng(12345)

    kn = {q: build_knots(rows, q, rng) for q in (80, 90)}
    bounds = [Boundary("flat (PRODUCTION)", "flat", 0.0)]
    for q in (80, 90):
        for c in a.cushions:
            bounds.append(Boundary(f"p{q} + {c:.0f} cm", "knot", c, kn[q]))

    res = {"in_sample": report(rows, bounds, "IN SAMPLE (surface built on these ends)")}

    # run-split cross-validation: build on one run, grade on the other
    runs = sorted({r["run"] for r in rows})
    if len(runs) >= 2:
        res["cross_validated"] = {}
        for held in runs:
            tr = [r for r in rows if r["run"] != held]
            te = [r for r in rows if r["run"] == held]
            if len(tr) < 100 or len(te) < 100:
                continue
            knx = {q: build_knots(tr, q, rng) for q in (80, 90)}
            bx = [Boundary("flat (PRODUCTION)", "flat", 0.0)]
            for q in (80, 90):
                for c in a.cushions:
                    bx.append(Boundary(f"p{q} + {c:.0f} cm", "knot", c, knx[q]))
            res["cross_validated"][held] = report(
                te, bx, f"CROSS-VALIDATED: surface built WITHOUT run {held}, graded ON it")
    else:
        print(f"\n[note] only one run ({runs}) -- no run-split cross-validation")

    json.dump(res, open(a.out + "_miss.json", "w"), indent=1)
    print(f"\n-> {a.out}_miss.json")


if __name__ == "__main__":
    main()
