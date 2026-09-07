#!/usr/bin/env python3
"""doc pdhd/09 -- exit-gap quantiles -> the eight PDHD fiducial profiles.

PDHD port of pdvd/docs/nf_sp_img_clus/scripts/fv_quantile_surface.py (doc pdvd/43).
Algorithm unchanged.  Differences, all forced by the detector:
  * eight keys are *_g02 / *_g13 (x<0 = APA0/2, x>0 = APA1/3), not *_bot / *_top;
  * BIN_EDGES scale to PDHD's 357.985 cm drift (four ~84 cm bins, PDVD 80);
  * PDVD's --d50 argument is dropped.  It was required=True there but fed only a
    printed comparison column and a figure -- the emitted knots never depended on
    it -- so PDHD does not have to redo doc pdvd/41's half-density map first.

Volume assignment is by sign(x) of the END POINT, matching PDVD and, more to the
point, matching how PolyFiducial will evaluate the polygon at that same x.  That
is deliberately NOT the wpid anode group the census also records: after t0
correction a point from one anode can land at the other sign, and for the
SURFACE the question is which side of the cathode the point is tested on.

Repro:
  python3 docs/scripts/d09_quantile_surface.py /home/xqian/tmp/d09/exits_rows.json \
      --out /home/xqian/tmp/d09/q
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d09_fv_pdhd import XW, CATH, BIN_EDGES, WALLS, VOLS

QUANTILES = (50, 80, 90)
GAP_MAX = 40.0
MIN_ENDS = 20             # statistics gate, doc 09 sec 4a
JN = {("y+", "g02"): "yp_g02", ("y+", "g13"): "yp_g13",
      ("y-", "g02"): "ym_g02", ("y-", "g13"): "ym_g13",
      ("z-", "g02"): "zm_g02", ("z-", "g13"): "zm_g13",
      ("z+", "g02"): "zp_g02", ("z+", "g13"): "zp_g13"}


def readout_clipped(r):
    if r.get("d_late") is None:
        return False
    return r["d_late"] < 5 or (r["d_early"] < 5 and abs(r["x"]) < 330)


def pav_nonincreasing(y, w):
    """Weighted pool-adjacent-violators: closest non-increasing sequence to y,
    indexed cathode -> anode.  Space charge can only grow with drift, and the
    instrumental stop-short tail does not depend on x, so a per-bin p90 that is
    the 2nd-largest of 15 values must not be allowed to RISE toward the anode.
    It smooths; it does not manufacture statistics -- see the MIN_ENDS gate."""
    blocks = [[float(v), float(wt), 1] for v, wt in zip(y, w)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] < blocks[i + 1][0] - 1e-12:
            v = (blocks[i][0]*blocks[i][1] + blocks[i+1][0]*blocks[i+1][1]) / (blocks[i][1] + blocks[i+1][1])
            blocks[i] = [v, blocks[i][1] + blocks[i+1][1], blocks[i][2] + blocks[i+1][2]]
            del blocks[i+1]; i = max(i-1, 0)
        else:
            i += 1
    out = []
    for v, _, c in blocks:
        out += [v]*c
    return np.array(out)


def excess_quantiles(g, quantiles, floor_per_cm, gap_max=GAP_MAX):
    """Quantiles of the gap distribution inside [0, gap_max] after subtracting a
    flat floor of non-exits.  Negative gaps (charge past the wall) count at 0."""
    gg = np.clip(g[g < gap_max], 0.0, None)
    if len(gg) == 0:
        return {q: float("nan") for q in quantiles}
    edges = np.arange(0.0, gap_max + 0.5, 0.5)
    h, _ = np.histogram(gg, edges)
    ex = np.clip(h - floor_per_cm*0.5, 0.0, None)
    tot = ex.sum()
    if tot <= 0:
        return {q: float("nan") for q in quantiles}
    cum = np.cumsum(ex)/tot
    out = {}
    for q in quantiles:
        i = min(int(np.searchsorted(cum, q/100.0)), len(edges)-2)
        c0 = cum[i-1] if i > 0 else 0.0
        frac = (q/100.0 - c0)/max(cum[i]-c0, 1e-12)
        out[q] = float(edges[i] + 0.5*np.clip(frac, 0, 1))
    return out


def quantile_table(rows, edges, quantiles, boot, rng, bg_range, mincos=0.0, subtract=True):
    T = {}
    centers = [(edges[i]+edges[i+1])/2 for i in range(len(edges)-1)]
    for w in WALLS:
        T[w] = {}
        for vol in VOLS:
            sg = -1 if vol == "g02" else 1
            rec = {"n": [], "n_exit_window": [], "floor_per_cm": [], "center": centers, "edges": edges}
            for q in quantiles:
                rec[f"q{q}"] = []; rec[f"q{q}_err"] = []; rec[f"q{q}_raw"] = []
            for i in range(len(edges)-1):
                sel = [r for r in rows if r["wall"] == w and np.sign(r["x"]) == sg
                       and edges[i] <= abs(r["x"]) < edges[i+1] and r["cos"] >= mincos
                       and not readout_clipped(r)]
                g = np.array([r["dmin"] for r in sel], float)
                inwin = g < GAP_MAX
                nbg = int(((g >= bg_range[0]) & (g < bg_range[1])).sum())
                floor = (nbg/(bg_range[1]-bg_range[0])) if subtract else 0.0
                rec["n"].append(int(len(g))); rec["n_exit_window"].append(int(inwin.sum()))
                rec["floor_per_cm"].append(float(floor))
                est = excess_quantiles(g, quantiles, floor)
                raw = excess_quantiles(g, quantiles, 0.0)
                bs = {q: [] for q in quantiles}
                if len(g):
                    for _ in range(boot):                 # bootstrap of ENDS (doc 43),
                        gb = rng.choice(g, len(g))        # not of events (doc 41)
                        nb = int(((gb >= bg_range[0]) & (gb < bg_range[1])).sum())
                        fb = (nb/(bg_range[1]-bg_range[0])) if subtract else 0.0
                        eb = excess_quantiles(gb, quantiles, fb)
                        for q in quantiles:
                            bs[q].append(eb[q])
                for q in quantiles:
                    rec[f"q{q}"].append(est[q]); rec[f"q{q}_raw"].append(raw[q])
                    rec[f"q{q}_err"].append(float(np.nanstd(bs[q])) if bs[q] else float("nan"))
            for q in quantiles:
                rawv = np.array(rec[f"q{q}"], float); n = np.array(rec["n_exit_window"], float)
                ok = np.isfinite(rawv)
                sm = rawv.copy()
                if ok.sum() >= 2:
                    sm[ok] = pav_nonincreasing(rawv[ok], np.maximum(n[ok], 1))
                rec[f"q{q}_pav"] = [float(np.clip(x, 0.0, None)) if np.isfinite(x) else float("nan") for x in sm]
            T[w][vol] = rec
    return T


def knots_from_profile(centers, values):
    """[|x|, inset] knots anode face -> cathode face, held flat outside the bin centres."""
    c = list(centers); v = [round(float(x), 2) for x in values]
    k = [[XW, v[-1]]]
    for ci, vi in zip(reversed(c), reversed(v)):
        k.append([round(float(ci), 2), vi])
    k.append([CATH, v[0]])
    return k


def profiles_jsonnet(T, quantiles, meta, starved):
    L = ["// PDHD exit-gap QUANTILE fiducial profiles, MEASURED -- doc pdhd/09.",
         "//",
         f"// Each entry is one wall of one drift volume as [|x|, inset] knots in cm from the",
         f"// anode face ({XW}) to the cathode face ({CATH}), the form curved_fiducial.jsonnet's",
         "// `profile` argument takes.  The inset at a bin is the p<q> of the perpendicular gap",
         "// between the end of a long (> 2 m) Q/L-matched cosmic track and the wall its own",
         "// direction exits through, per drift bin, after subtracting the flat non-exit floor,",
         "// regularized non-increasing toward the anode, CUSHION 0 -- the cushion is the",
         "// taggers' fv_tolerance (pr.jsonnet curved_fv_margin_y/z).",
         "//",
         "// g02 = the x<0 drift volume (APA0/2); g13 = x>0 (APA1/3).",
         "//",
         "// GENERATED by docs/scripts/d09_quantile_surface.py (wcp-porting-img);",
         "// do not edit by hand -- re-run the doc 09 Repro block.",
         "// " + meta]
    if starved:
        L.append("// STATISTICS GATE: bins with < %d in-window ends, carried but NOT trustworthy:" % MIN_ENDS)
        for s in starved:
            L.append("//   " + s)
    L.append("{")
    for q in quantiles:
        if q == 50:
            continue
        L.append(f"  p{q}: {{")
        for w in WALLS:
            for vol in VOLS:
                rec = T[w][vol]
                k = knots_from_profile(rec["center"], rec[f"q{q}_pav"])
                ks = ", ".join(f"[{a:.2f}, {b:.2f}]" for a, b in k)
                L.append(f"    {JN[(w, vol)]}: [{ks}],")
        L.append("  },")
    L.append("}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--out", default="/home/xqian/tmp/d09/q")
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--mincos", type=float, default=0.3)
    ap.add_argument("--bg-range", type=float, nargs=2, default=[40.0, 150.0])
    ap.add_argument("--no-subtract", action="store_true")
    a = ap.parse_args()

    rows = json.load(open(a.rows))
    rng = np.random.default_rng(12345)
    T = quantile_table(rows, BIN_EDGES, QUANTILES, a.boot, rng, a.bg_range,
                       a.mincos, not a.no_subtract)

    nev = len({(r["run"], r["idx"]) for r in rows})
    nclip = sum(1 for r in rows if readout_clipped(r))
    meta = (f"{len(rows)} ends of long clusters in {nev} events ({nclip} at a readout edge "
            f"excluded), exit window {GAP_MAX:.0f} cm, floor from {a.bg_range[0]:.0f}-{a.bg_range[1]:.0f} cm, "
            f"bins {BIN_EDGES}, {a.boot} bootstraps.")

    starved = []
    print(f"\n{'wall':4s} {'vol':4s} {'bin':>12s} {'n':>5s} {'nwin':>5s} {'floor':>6s} "
          f"{'p50':>6s} {'p80':>6s} {'p90':>6s} {'+-p90':>6s}")
    for w in WALLS:
        for vol in VOLS:
            rec = T[w][vol]
            for i, cen in enumerate(rec["center"]):
                nw = rec["n_exit_window"][i]
                flag = " <-- STARVED" if nw < MIN_ENDS else ""
                if nw < MIN_ENDS:
                    starved.append(f"{JN[(w,vol)]} bin |x| {BIN_EDGES[i]:.0f}-{BIN_EDGES[i+1]:.0f}: {nw} ends")
                print(f"{w:4s} {vol:4s} {BIN_EDGES[i]:5.0f}-{BIN_EDGES[i+1]:5.0f} {rec['n'][i]:5d} {nw:5d} "
                      f"{rec['floor_per_cm'][i]:6.2f} {rec['q50_pav'][i]:6.2f} {rec['q80_pav'][i]:6.2f} "
                      f"{rec['q90_pav'][i]:6.2f} {rec['q90_err'][i]:6.2f}{flag}")

    json.dump({"meta": meta, "bin_edges": BIN_EDGES, "quantiles": list(QUANTILES),
               "gap_max": GAP_MAX, "bg_range": a.bg_range, "table": T,
               "starved": starved}, open(a.out + "_table.json", "w"), indent=1)
    open(a.out + "_profiles.jsonnet", "w").write(profiles_jsonnet(T, QUANTILES, meta, starved))
    print(f"\n{meta}")
    print(f"starved bins (< {MIN_ENDS} in-window ends): {len(starved)} of {4*len(WALLS)*len(VOLS)}")
    print(f"-> {a.out}_table.json  {a.out}_profiles.jsonnet")


if __name__ == "__main__":
    main()
