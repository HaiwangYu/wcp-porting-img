#!/usr/bin/env python3
"""doc pdvd/57 -- the offline predictor for the STM stop retreat, BEFORE any
C++ ran.  Simulates stm_michel_stop_retreat (clus/src/StmMichelFunctions.cxx)
on the committed d53v payloads using only a graph-vertex PROXY (a PR vertex
that sits on the muon polyline is the closest offline stand-in for "the chain
already has this vertex"), and prints:

  1. what the negative control (the collapse-shaped THRU items) is protected
     by TODAY -- the reject-bit composition of the 51 missed-collapse and the
     80 THRU-collapse items (section 1: this is what killed the naive
     "truncate wherever the shape looks collapsed" design);
  2. how often an on-chain interior vertex sits near the collapse onset, in
     each of missed / found / THRU (section 2: the constraint that makes the
     retreat implementable is the same constraint that keeps it honest);
  3. the operating-point grid: recovered missed stoppers vs new THRU false
     positives, for the criterion actually shipped (tail_med < frac * plateau
     or * peak) at a few candidate fractions (section 3 -- the ROC table in
     the doc);
  4. the chosen point (tail_med < 0.5 x plateau), with every recovered item
     and every new false positive named, plus how many of the 51 have NO
     candidate vertex at all (unreachable by any graph-local retreat --
     section 4, the T1c finding).

This script is independent of the actual C++ arms: it exists so the design
was measured before the first line of CheckSTM_Michel.cxx changed, and so a
disagreement between this prediction and the real d57v arm is itself a
finding.  Everything here reads the committed scan record and prep payloads
only -- read-only, nothing under work/ or pdvd/docs/scan/ is touched.

Repro:
    cd wcp-porting-img
    python3 pdvd/docs/nf_sp_img_clus/scripts/d57_retreat_probe.py [--prep DIR]
"""
import argparse, collections, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, IMG + "/pdhd/stm_michel_scan")
import census_lib as C                                            # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--prep", default=C.PREP_DEFAULT)
ap.add_argument("--live-frac", type=float, default=0.15, help="profile_min_dqdx_frac, PDVD production value")
ap.add_argument("--mip", type=float, default=55000.0, help="mip_dqdx, PDVD production value (e/cm)")
a = ap.parse_args()

MIP = a.mip
LIVE = a.live_frac * MIP

rec = C.load_record()
keys = [k for k, r in rec.items() if C.judged(r)]
P, missing = C.load_payloads(a.prep, keys)
print("record %d judged items, payloads %d, missing %d" % (len(keys), len(P), len(missing)))
if missing:
    print("  MISSING:", missing[:10], "...")
keys = [k for k in keys if k in P]


def grp_of(k, pay):
    v = pay["verdict"]
    r = rec[k]
    st = C.is_stopper(r)
    s = int(v.get("is_stm") or 0)
    if st and not s:
        return "missed"
    if st and s:
        return "found"
    return "THRU_fp" if s else "THRU"


def bragg_pass(rr, q, exp, cut=0.0):
    """stm_michel_bragg_contrast, evaluated from residual range `cut` inward
    (the profile as it would read AFTER a retreat to `cut`), live points only.
    """
    m = (q >= LIVE) & (rr >= cut)
    rr2 = rr[m] - cut
    q2 = q[m]
    if len(q2) < 6 or exp <= 0:
        return None
    tot = rr2.max()
    plo, phi = (20.0, 40.0) if tot >= 40 else (10.0, 20.0)
    t = q2[(rr2 >= 0.5) & (rr2 <= 3.0)]
    pl = q2[(rr2 >= plo) & (rr2 <= phi)]
    if len(t) < 3 or len(pl) < 3:
        return None
    pm = float(np.median(pl))
    if pm <= 0:
        return None
    return float(np.median(t)) / pm / exp


def candidate_vertices(pay, max_drop_len_cm=25.0):
    """PR vertices sitting ON the muon polyline (within 1 cm), strictly
    interior (rr > 0.6 cm so it is not the stop itself) and reachable within
    max_drop_len_cm of the stop -- the offline proxy for "the chain already
    has this vertex", ordered by increasing residual range from the stop."""
    rr, q, xyz = C.profile(pay)
    V = pay["pf"]["vtx"]
    vx = np.c_[V["x"], V["y"], V["z"]].astype(float)
    if not len(vx) or not len(rr):
        return []
    d = np.linalg.norm(vx[:, None, :] - xyz[None, :, :], axis=2)
    j = np.argmin(d, axis=1)
    dmin = d[np.arange(len(vx)), j]
    rv = rr[j]
    sel = (dmin <= 1.0) & (rv > 0.6) & (rv <= max_drop_len_cm) & (rv < rr.max() - 5.0)
    return sorted(set(np.round(rv[sel], 2)))


CACHE = {}


def prep_item(k, pay):
    if k in CACHE:
        return CACHE[k]
    rr, q, xyz = C.profile(pay)
    v = pay["verdict"]
    exp = float(v.get("contrast_expected") or 0)
    live = q >= LIVE
    rl, ql = rr[live], q[live]
    pls = (rl >= 20) & (rl <= 40)
    plateau = float(np.median(ql[pls])) if pls.sum() >= 3 else 0.0
    cv = candidate_vertices(pay)
    b0 = bragg_pass(rr, q, exp)
    CACHE[k] = (rr, q, exp, rl, ql, plateau, cv, b0)
    return CACHE[k]


def run(collapse_frac, ref, peak_frac=1.4, peak_window=15.0, budget=4, min_tail_pts=2):
    """One pass of the criterion over every judged item.  `ref` = 'plateau'
    or 'peak' selects what the dropped tail's median is compared against
    (peak is NOT what shipped; kept here only to show why plateau was chosen
    -- see section 3)."""
    out = collections.defaultdict(collections.Counter)
    hit = collections.defaultdict(list)
    for k in keys:
        pay = P[k]
        g = grp_of(k, pay)
        rr, q, exp, rl, ql, plateau, cv, b0 = prep_item(k, pay)
        if plateau <= 0 or len(ql) < 10 or not cv:
            continue
        if b0 is not None and b0 >= 0.6:
            continue   # already Bragg-confirmed: the guard that protects the found stoppers
        for cut in cv[:budget]:
            tail = ql[rl < cut]
            keep = rl >= cut
            if len(tail) < min_tail_pts or keep.sum() < 6:
                continue
            rm = C.running_median(ql[keep], 3)
            rk = rl[keep] - cut
            w = rk <= peak_window
            if w.sum() < 3:
                continue
            pk = float(np.max(rm[w]))
            if pk < peak_frac * plateau:
                continue
            thr = collapse_frac * (pk if ref == "peak" else plateau)
            if float(np.median(tail)) >= thr:
                continue
            out[g]["fires"] += 1
            bp = bragg_pass(rr, q, exp, cut)
            if bp is not None and bp >= 0.6:
                out[g]["pass"] += 1
                hit[g].append(k)
            break
    return out, hit


print()
print("=" * 78)
print("1. What holds the 51 missed-collapse and the 80 THRU-collapse items back TODAY")
print("=" * 78)
grp = collections.defaultdict(list)
for k in keys:
    pay = P[k]
    sh = C.shape(pay)
    grp[(grp_of(k, pay), sh["cls"])].append(k)
for label, gk in [("missed-collapse", ("missed", "collapse")), ("THRU-collapse", ("THRU", "collapse"))]:
    ks = grp[gk]
    single = collections.Counter()
    shape_only = 0
    combos = collections.Counter()
    for k in ks:
        names = tuple(sorted(C.reject_names(P[k]["verdict"])))
        combos[names] += 1
        for n in names:
            single[n] += 1
        if names and set(names) <= {"no_bragg", "shape_flat", "profile_sparse"}:
            shape_only += 1
    print("%s n=%d" % (label, len(ks)))
    print("   per-bit: %s" % dict(single.most_common()))
    print("   held ONLY by the shape bits (no_bragg/shape_flat/profile_sparse, nothing else): %d of %d"
          % (shape_only, len(ks)))
    for c, n in combos.most_common(6):
        print("     %2d  %s" % (n, "|".join(c) if c else "(none)"))

print()
print("=" * 78)
print("2. Does an on-chain interior vertex sit near the collapse onset?")
print("=" * 78)


def onchain_vertex(pay, sh):
    rr, q, xyz = C.profile(pay)
    V = pay["pf"]["vtx"]
    vx = np.c_[V["x"], V["y"], V["z"]].astype(float)
    if not len(vx):
        return None
    d = np.linalg.norm(vx[:, None, :] - xyz[None, :, :], axis=2)
    j = np.argmin(d, axis=1)
    dmin = d[np.arange(len(vx)), j]
    rv = rr[j]
    sel = (dmin <= 1.0) & (rv > 0.6) & (rv < rr.max() - 1.0)
    if not sel.any():
        return None
    cand = vx[sel]
    dd = np.linalg.norm(cand - np.asarray(sh["onset_pt"], float), axis=1)
    i = int(np.argmin(dd))
    return float(dd[i])


tab = collections.defaultdict(collections.Counter)
for k in keys:
    pay = P[k]
    sh = C.shape(pay)
    if sh["cls"] != "collapse":
        continue
    g = grp_of(k, pay)
    tab[g]["n"] += 1
    d = onchain_vertex(pay, sh)
    if d is None:
        tab[g]["no_vertex"] += 1
        continue
    for tol in (2, 4, 6):
        if d <= tol:
            tab[g]["within%d" % tol] += 1
print("%-8s %5s %10s %10s %10s %10s" % ("class", "n", "no_vertex", "<=2cm", "<=4cm", "<=6cm"))
for g in ("missed", "found", "THRU", "THRU_fp"):
    c = tab[g]
    if not c["n"]:
        continue
    print("%-8s %5d %10d %10d %10d %10d" % (g, c["n"], c["no_vertex"], c["within2"], c["within4"], c["within6"]))

print()
print("=" * 78)
print("3. Operating-point grid: recovered missed vs new THRU false positives")
print("=" * 78)
print("%-22s %10s %10s %10s %10s" % ("criterion", "missed", "recovered", "THRU_fires", "THRU_new_FP"))
for ref in ("plateau", "peak"):
    for cf in (0.5, 0.6, 0.7):
        o, _ = run(cf, ref)
        print("tail < %.1f x %-8s   %10d %10d %10d %10d" %
              (cf, ref, o["missed"]["fires"], o["missed"]["pass"], o["THRU"]["fires"], o["THRU"]["pass"]))

print()
print("=" * 78)
print("4. The chosen point (tail_med < 0.5 x plateau) -- named")
print("=" * 78)
o, hit = run(0.5, "plateau")
for g in ("missed", "found", "THRU", "THRU_fp"):
    c = o[g]
    print("%-8s fires %3d  recovered/new-FP %3d   items: %s" %
          (g, c["fires"], c["pass"], sorted(hit[g])))

no_vertex_51 = sum(1 for k in grp[("missed", "collapse")] if candidate_vertices(P[k], max_drop_len_cm=25.0) == [])
print()
print("of the 51 missed-collapse items, %d have NO candidate vertex within 25 cm at all "
      "(unreachable by ANY graph-local retreat -- the T1c finding)" % no_vertex_51)
