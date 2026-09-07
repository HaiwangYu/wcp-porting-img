#!/usr/bin/env python3
"""doc pdhd/09 sec 4b -- is the exit-gap tail SPACE CHARGE or IMAGING?

This is the test that overturned PDVD doc 41.  There, the endpoint tail turned out
to be per-CRU, per-angle imaging efficiency at the anode-plane edge: 26.5 % of
approaches stopped > 8 cm short when the track ran parallel to a plane's strips
against 12.6 % otherwise.  A surface built without this check measures the
detector's reconstruction, not its drift field.

PDHD has a STRUCTURAL reason to expect the effect to be larger, read out of
protodunehd-wires-larsoft-v1.json.bz2 rather than assumed:

    plane 0 (U)  dir (0, +0.812, +0.584)   35.71 deg from vertical
    plane 1 (V)  dir (0, +0.812, -0.584)   35.71 deg
    plane 2 (W)  dir (0, +1.000,  0.000)   EXACTLY VERTICAL

PDHD's collection wires run along y -- and PDHD's cosmics also run along y.  So a
vertical cosmic is parallel to the collection strips, the prolonged-signal case,
and it is exactly the population that exits through the y walls.  If the y-wall
tail is carried by wire-parallel tracks then the surface there is measuring
imaging, not space charge, and must be reported as such.

Splits, all on the census rows (no re-run needed -- ux/uy/uz are recorded):
  (i)   wire-parallel:  max over planes of |u . wiredir|  (1 = along the strips)
  (ii)  drift half and wall
  (iii) readout-edge proximity

Repro:
  python3 docs/scripts/d09_instrumental.py /home/xqian/tmp/d09/exits_rows.json
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d09_fv_pdhd import WALLS, HALF_X

WIRE_DIRS = {"U": np.array([0.0,  0.812,  0.584]),
             "V": np.array([0.0,  0.812, -0.584]),
             "W": np.array([0.0,  1.000,  0.000])}
PAR_CUT = 0.85          # |cos| above this = running along that plane's strips
SHORT = 8.0             # doc pdvd/41 sec 13.2's threshold


def wire_cos(r):
    u = np.array([r["ux"], r["uy"], r["uz"]], float)
    n = np.linalg.norm(u)
    if n == 0:
        return {k: 0.0 for k in WIRE_DIRS}, 0.0
    u = u / n
    c = {k: abs(float(np.dot(u, v))) for k, v in WIRE_DIRS.items()}
    return c, max(c.values())


def frac(sel, thr=SHORT):
    g = np.array([r["dmin"] for r in sel], float)
    if not len(g):
        return float("nan"), float("nan"), 0
    return 100.0 * np.mean(g > thr), float(np.percentile(g, 80)), len(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--out", default="/home/xqian/tmp/d09/instrumental.json")
    a = ap.parse_args()
    rows = [r for r in json.load(open(a.rows)) if r["wall"] in WALLS]
    for r in rows:
        c, m = wire_cos(r)
        r["_cW"], r["_cmax"] = c["W"], m
        r["_par"] = m >= PAR_CUT
        r["_ro"] = (r.get("d_late") is not None and
                    (r["d_late"] < 5 or (r["d_early"] < 5 and abs(r["x"]) < 330)))

    out = {"par_cut": PAR_CUT, "short_cm": SHORT}
    print(f"=== (i) wire-parallel vs not  (|cos| to the nearest plane's strips >= {PAR_CUT}) ===")
    print(f"{'sample':28s} {'n':>6s} {'>8cm short':>11s} {'p80 [cm]':>9s}")
    for name, sel in (("ALL side-wall ends", rows),
                      ("  parallel to strips", [r for r in rows if r["_par"]]),
                      ("  not parallel", [r for r in rows if not r["_par"]]),
                      ("  parallel to W (vertical)", [r for r in rows if r["_cW"] >= PAR_CUT]),
                      ("  not parallel to W", [r for r in rows if r["_cW"] < PAR_CUT])):
        f, p80, n = frac(sel)
        print(f"{name:28s} {n:6d} {f:10.1f}% {p80:9.2f}")
        out[name.strip()] = dict(n=n, short_pct=f, p80=p80)

    print(f"\n=== (ii) per wall x drift half ===")
    print(f"{'wall':5s} {'half':9s} {'n':>5s} {'par%':>6s} {'>8cm all':>9s} {'>8cm par':>9s} {'>8cm npar':>10s} "
          f"{'p80 par':>8s} {'p80 npar':>9s}")
    for w in WALLS:
        for h in ("anode", "cathode"):
            sel = [r for r in rows if r["wall"] == w and r["half"] == h]
            if not sel:
                continue
            par = [r for r in sel if r["_par"]]; npar = [r for r in sel if not r["_par"]]
            fa, _, na = frac(sel); fp, p80p, np_ = frac(par); fn, p80n, nn = frac(npar)
            print(f"{w:5s} {h:9s} {na:5d} {100*np_/max(na,1):5.1f}% {fa:8.1f}% {fp:8.1f}% {fn:9.1f}% "
                  f"{p80p:8.2f} {p80n:9.2f}")

    print(f"\n=== (iii) readout-edge share ===")
    nro = sum(1 for r in rows if r["_ro"])
    print(f"  side-wall ends at a readout edge: {nro} of {len(rows)} ({100*nro/max(len(rows),1):.1f}%)")
    fa, _, _ = frac([r for r in rows if r["_ro"]]); fb, _, _ = frac([r for r in rows if not r["_ro"]])
    print(f"  >8 cm short: at edge {fa:.1f}%   away from edge {fb:.1f}%")
    print(f"  (these are EXCLUDED from the surface; the split says whether that mattered)")

    # how much of the inset survives if only non-parallel ends are used
    print(f"\n=== (iv) how much of the emitted inset is angle-correlated? ===")
    print(f"{'wall':5s} {'half':9s} {'p90 all':>8s} {'p90 npar':>9s} {'ratio':>7s}")
    for w in WALLS:
        for h in ("anode", "cathode"):
            sel = [r for r in rows if r["wall"] == w and r["half"] == h and r["dmin"] < 40.0]
            npar = [r for r in sel if not r["_par"]]
            if len(sel) < 5 or len(npar) < 5:
                continue
            pa = np.percentile([r["dmin"] for r in sel], 90)
            pn = np.percentile([r["dmin"] for r in npar], 90)
            print(f"{w:5s} {h:9s} {pa:8.2f} {pn:9.2f} {pn/max(pa,1e-9):7.2f}")
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
