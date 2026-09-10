#!/usr/bin/env python3
"""doc pdvd/58 -- the offline predictor for T1c, the STM stop SPLIT, run
BEFORE any C++ changed.  Companion to d57_retreat_probe.py: doc 57 sec 1
found that 23 of the 51 missed collapse-shaped stoppers have no chain vertex
within 25 cm of the stop at all, so stm_michel_stop_retreat (graph-local,
onto an EXISTING vertex) cannot reach them -- this script asks whether a
FIT-ROW split, gated on the fitted trajectory's own kink at the row instead
of an existing vertex, can.

Four things, in order:

  1. the population, corrected.  Doc 56 wrote "23"; this splits it by cause
     -- some are unreachable in principle (n_chain_segs <= 1, the retreat's
     loop cannot even start), others only look unreachable because of the
     offline PR-vertex-proximity PROXY this script (and d57's) uses for "the
     chain already has a vertex" -- the real graph may have more;

  2. the discriminator.  Losing the vertex constraint removes the guard that
     kept the retreat honest (doc 57: a vertex within 4cm existed on 24/51
     missed vs 11/80 through-going).  This measures whether the FITTED
     TRAJECTORY'S OWN BEND at the collapse onset replaces it -- the owner's
     kink discriminator (feedback_owner_kink_discriminator), applied at a fit
     row instead of a segment pair;

  3. the operating-point grid over the kink threshold, with recovery decided
     by the ACTUAL shipped verdict -- both the Bragg contrast against the
     muon table AND kslike_compare (util/src/KSTest.cxx) over rr <=
     compare_range_cm, at the shifted residual-range origin a split would
     produce.  All 23 targets carry shape_flat (see census_lib.reject_names
     on them), so a Bragg-only proxy is not a recovery estimate here -- it is
     the wrong metric entirely (feedback_reading_a_loop_is_a_hypothesis: a
     reimplemented verdict must be graded against the production binary
     before it is trusted, done in step 0 below);

  4. the chosen point, named -- every recovered item and every new false
     positive on the collapse-shaped through-going control.

Everything here reads the committed scan record and prep payloads only --
read-only, nothing under work/ or pdvd/docs/scan/ is touched.

Repro:
    cd wcp-porting-img
    python3 pdvd/docs/nf_sp_img_clus/scripts/d58_split_probe.py [--prep DIR]
"""
import argparse, collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, IMG + "/pdhd/stm_michel_scan")
import census_lib as C                                            # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--prep", default=C.PREP_DEFAULT)
ap.add_argument("--live-frac", type=float, default=0.15, help="profile_min_dqdx_frac, PDVD production value")
ap.add_argument("--mip", type=float, default=55000.0, help="mip_dqdx, PDVD production value (e/cm)")
ap.add_argument("--compare-range-cm", type=float, default=35.0, help="C++ default compare_range_cm")
ap.add_argument("--ks-margin", type=float, default=0.0, help="C++ default ks_margin")
ap.add_argument("--contrast-min", type=float, default=0.6, help="C++ default bragg_contrast_min")
a = ap.parse_args()

MIP = a.mip
LIVE = a.live_frac * MIP
CR = a.compare_range_cm
KSM = a.ks_margin
CMIN = a.contrast_min

rec = C.load_record()
keys = [k for k, r in rec.items() if C.judged(r)]
P, missing = C.load_payloads(a.prep, keys)
print("record %d judged items, payloads %d, missing %d" % (len(keys), len(P), len(missing)))
if missing:
    print("  MISSING:", missing[:10], "...")
keys = [k for k in keys if k in P]

# The muon dQ/dx reference table CheckSTM_Michel::mu_fn resolves to (PDVD
# particle_dataset.jsonnet's muon_dEdx_function -- LinterpFunction, e/cm),
# dumped once by prep_stm_michel_scan.py alongside every item's payload.
REF = json.load(open(os.path.join(a.prep, "dqdx_ref_pdvd.json")))
_g = REF["grid"]
_gx = _g["start"] + _g["step"] * np.arange(_g["n"])
_gy = np.asarray(REF["muon"], float)


def mu(rr_cm):
    return np.interp(rr_cm, _gx, _gy)


def kslike(test, ref):
    """WireCell::kslike_compare (util/src/KSTest.cxx): max abs difference of
    the two normalized running cumulative sums, IN INPUT ORDER (not sorted --
    the production caller passes points ordered by increasing rr)."""
    t = np.asarray(test, float)
    r = np.asarray(ref, float)
    return float(np.max(np.abs(np.cumsum(t) / t.sum() - np.cumsum(r) / r.sum())))


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


def cand_vtx(pay, max_len_cm=25.0):
    """The offline proxy for 'the chain already has a vertex here': a PR
    vertex sitting ON the muon polyline (within 1 cm), interior (rr > 0.6cm,
    so it is not the stop itself), within max_len_cm of the stop.  Same
    definition d57_retreat_probe.py used, so the two probes cannot drift on
    what counts as an existing vertex."""
    rr, q, xyz = C.profile(pay)
    V = pay["pf"]["vtx"]
    vx = np.c_[V["x"], V["y"], V["z"]].astype(float)
    if not len(vx) or not len(rr):
        return []
    d = np.linalg.norm(vx[:, None, :] - xyz[None, :, :], axis=2)
    j = np.argmin(d, axis=1)
    dmin = d[np.arange(len(vx)), j]
    rv = rr[j]
    sel = (dmin <= 1.0) & (rv > 0.6) & (rv <= max_len_cm) & (rv < rr.max() - 5.0)
    return sorted(set(np.round(rv[sel], 2)))


def bend_deg(xyz, rr, i, arm_cm=5.0):
    """stm_michel_row_kink_deg's offline twin: the angle between the arm
    arriving at row i (from arm_cm of arclength behind) and the arm leaving
    it (arm_cm ahead).  rr runs opposite to L here (this script's `profile()`
    sorts by ascending rr, the C++ walks by ascending L), so 'behind' in
    arclength is 'larger rr'.  Returns None when unmeasurable (matches the
    C++ -1 convention)."""
    a_idx = int(np.searchsorted(rr, rr[i] + arm_cm))
    b_idx = int(np.searchsorted(rr, max(rr[i] - arm_cm, 0.0)))
    if a_idx >= len(rr) or i - b_idx < 2 or a_idx - i < 2:
        return None
    d_in = xyz[i] - xyz[min(a_idx, len(xyz) - 1)]
    d_out = xyz[max(b_idx, 0)] - xyz[i]
    n1, n2 = np.linalg.norm(d_in), np.linalg.norm(d_out)
    if n1 < 1e-6 or n2 < 1e-6:
        return None
    c = float(np.dot(d_in, d_out) / (n1 * n2))
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))


def verdict_at(rr, q, geo_total, cut):
    """Simulates the shipped reject_bits (CheckSTM_Michel.cxx sec 'dQ/dx vs
    residual range') on the profile AS A SPLIT AT `cut` WOULD LEAVE IT: the
    same plateau-halving convention as stm_michel_bragg_contrast, the same
    tail(0.5-3cm)/plateau(20-40 or 10-20cm) contrast test against the muon
    table, and the same ks_mu/ks_flat comparison over rr<=compare_range_cm
    with the ORIGIN SHIFTED to `cut` (a split moves rr's zero to the new
    stop).  Returns (ok, reason) -- ok=True means every shape bit clears."""
    m = (q >= LIVE) & (rr >= cut)
    rr2, q2 = rr[m] - cut, q[m]
    if len(q2) < 3:
        return False, "sparse"
    tot = geo_total - cut
    plo, phi = (20.0, 40.0) if tot >= 40 else (10.0, 20.0)
    tm = (rr2 >= 0.5) & (rr2 <= 3.0)
    pm = (rr2 >= plo) & (rr2 <= phi)
    if tm.sum() < 3 or pm.sum() < 3 or np.median(q2[pm]) <= 0:
        return False, "sparse"
    exp = float(np.median(mu(rr2[tm])) / np.median(mu(rr2[pm])))
    if exp <= 0:
        return False, "sparse"
    contrast = float(np.median(q2[tm]) / np.median(q2[pm]))
    if contrast < CMIN * exp:
        return False, "no_bragg"
    w = rr2 <= CR
    if w.sum() < 3:
        return True, "ok(no ks -- too few points in compare_range)"
    if kslike(q2[w], mu(rr2[w])) >= kslike(q2[w], np.full(w.sum(), MIP)) + KSM:
        return False, "shape_flat"
    return True, "ok"


CACHE = {}


def prep_item(k):
    if k in CACHE:
        return CACHE[k]
    pay = P[k]
    rr, q, xyz = C.profile(pay)
    live = q >= LIVE
    rl, ql = rr[live], q[live]
    pls = (rl >= 20) & (rl <= 40)
    plateau = float(np.median(ql[pls])) if pls.sum() >= 3 else 0.0
    CACHE[k] = (rr, q, xyz, float(rr.max()) if len(rr) else 0.0, rl, ql, plateau)
    return CACHE[k]


def population():
    """The T1c target and control populations, keyed the same way for every
    section below."""
    grp = collections.defaultdict(list)
    for k in keys:
        pay = P[k]
        sh = C.shape(pay)
        if sh["cls"] != "collapse":
            continue
        g = grp_of(k, pay)
        v = pay["verdict"]
        nseg = int(v.get("n_chain_segs") or 0)
        novtx = (cand_vtx(pay) == [])
        grp[(g, novtx)].append(k)
    return grp


print()
print("=" * 78)
print("0. Sanity: offline ks_mu/ks_flat/contrast reproduce the production binary's own numbers")
print("=" * 78)
dc, dkm, dkf = [], [], []
for k in keys:
    pay = P[k]
    v = pay["verdict"]
    rr, q, xyz = C.profile(pay)
    ok, why = verdict_at(rr, q, float(rr.max()) if len(rr) else 0.0, 0.0)
    # contrast/ks are computed inside verdict_at only as pass/fail; re-derive
    # the raw numbers here for the direct numeric comparison.
    live = q >= LIVE
    rl, ql = rr[live], q[live]
    if v.get("bragg_valid"):
        tot = float(rr.max()) if len(rr) else 0.0
        plo, phi = (20.0, 40.0) if tot >= 40 else (10.0, 20.0)
        tm = (rl >= 0.5) & (rl <= 3.0)
        pm = (rl >= plo) & (rl <= phi)
        if tm.sum() >= 3 and pm.sum() >= 3 and np.median(ql[pm]) > 0 and v.get("contrast"):
            dc.append(float(np.median(ql[tm]) / np.median(ql[pm])) - float(v["contrast"]))
    w = rl <= CR
    if w.sum() >= 3 and v.get("ks_mu") is not None:
        dkm.append(kslike(ql[w], mu(rl[w])) - float(v["ks_mu"]))
        dkf.append(kslike(ql[w], np.full(w.sum(), MIP)) - float(v["ks_flat"]))
for nm, d in (("contrast", dc), ("ks_mu", dkm), ("ks_flat", dkf)):
    if not d:
        continue
    ad = np.abs(np.array(d))
    print("  %-9s n=%4d  max|diff|=%.6f  median|diff|=%.7f" % (nm, len(ad), ad.max(), np.median(ad)))

print()
print("=" * 78)
print("1. The population, corrected (doc 56 wrote a single number: 23)")
print("=" * 78)
grp = population()
n_struct = len(grp[("missed", True)])
missed_all = [k for k in keys if grp_of(k, P[k]) == "missed" and C.shape(P[k])["cls"] == "collapse"]
n_novtx = sum(1 for k in missed_all if cand_vtx(P[k]) == [])
n_struct_only = sum(1 for k in missed_all if cand_vtx(P[k]) == [] and int(P[k]["verdict"].get("n_chain_segs") or 0) <= 1)
n_proxy_only = n_novtx - n_struct_only
thru_novtx = sum(1 for k in keys if grp_of(k, P[k]) == "THRU" and C.shape(P[k])["cls"] == "collapse" and cand_vtx(P[k]) == [])
thru_novtx_struct = sum(1 for k in keys if grp_of(k, P[k]) == "THRU" and C.shape(P[k])["cls"] == "collapse"
                        and cand_vtx(P[k]) == [] and int(P[k]["verdict"].get("n_chain_segs") or 0) <= 1)
print("  missed + collapse, no chain-vertex proxy within 25cm:            %d" % n_novtx)
print("    of which n_chain_segs <= 1 (STRUCTURALLY unreachable by T1a):  %d" % n_struct_only)
print("    of which n_chain_segs >= 2 (proxy-only exclusion, T1c target): %d" % n_proxy_only)
print("  negative control: THRU + collapse, no chain-vertex proxy:        %d  (n_chain_segs<=1: %d)"
      % (thru_novtx, thru_novtx_struct))

print()
print("=" * 78)
print("2. The discriminator: bend of the fitted trajectory at the collapse onset")
print("=" * 78)


def onset_row(pay, sh):
    rr, q, xyz = C.profile(pay)
    onset = sh.get("onset_rr")
    if onset is None:
        return None
    return int(np.argmin(np.abs(rr - onset)))


tab = collections.defaultdict(list)
for k in keys:
    pay = P[k]
    sh = C.shape(pay)
    if sh["cls"] != "collapse" or cand_vtx(pay) != []:
        continue
    g = grp_of(k, pay)
    rr, q, xyz = C.profile(pay)
    i = onset_row(pay, sh)
    if i is None:
        continue
    b = bend_deg(xyz, rr, i)
    tab[g].append(b if b is not None else float("nan"))
print("  %-8s %5s %8s %8s %8s %8s %8s" % ("group", "n", "p25", "median", "p75", "p90", ">=20deg"))
for g in ("missed", "THRU", "found", "THRU_fp"):
    v = np.array([x for x in tab[g] if not np.isnan(x)])
    if not len(v):
        continue
    print("  %-8s %5d %8.1f %8.1f %8.1f %8.1f %8d" % (g, len(v), np.percentile(v, 25), np.median(v),
                                                       np.percentile(v, 75), np.percentile(v, 90), (v >= 20).sum()))

print()
print("=" * 78)
print("3. Operating-point grid: kink threshold vs recovered / new false positives")
print("=" * 78)
print("(recovery = the FULL shipped verdict clears -- Bragg contrast AND the KS shape test,")
print(" not a Bragg-only proxy: every one of the 'missed' targets below already fails on shape_flat)")


def run(kink_thr, min_drop_cm=3.0, min_tail_pts=3, collapse_frac=0.5, peak_frac=1.4, peak_window_cm=15.0,
       max_drop_len_cm=25.0):
    out = collections.defaultdict(collections.Counter)
    hit = collections.defaultdict(list)
    for k in keys:
        pay = P[k]
        sh = C.shape(pay)
        if sh["cls"] != "collapse" or cand_vtx(pay) != []:
            continue
        g = grp_of(k, pay)
        rr, q, xyz, geo_tot, rl, ql, plateau = prep_item(k)
        if plateau <= 0 or len(ql) < 10:
            continue
        ok0, _ = verdict_at(rr, q, geo_tot, 0.0)
        if ok0:
            continue   # already passes: nothing for a split to do
        best = None
        for i in range(len(rr)):
            cut = rr[i]
            if cut < min_drop_cm or cut > max_drop_len_cm:
                continue
            kb = bend_deg(xyz, rr, i)
            if kb is None or kb < kink_thr:
                continue
            tail = ql[rl < cut]
            keep = rl >= cut
            if len(tail) < min_tail_pts or keep.sum() < 6:
                continue
            if float(np.median(tail)) >= collapse_frac * plateau:
                continue
            rm = C.running_median(ql[keep], 3)
            rk = rl[keep] - cut
            w = rk <= peak_window_cm
            if w.sum() < 3 or float(np.max(rm[w])) < peak_frac * plateau:
                continue
            if best is None or kb > best[1]:
                best = (cut, kb)
        if best is None:
            continue
        cut, kb = best
        out[g]["fires"] += 1
        ok, why = verdict_at(rr, q, geo_tot, cut)
        if ok:
            out[g]["recovered"] += 1
            hit[g].append((k, round(cut, 1), round(kb, 1)))
        else:
            out[g][why] += 1
    return out, hit


print("  %-9s %10s %10s %10s %10s" % ("kink>=", "missed fire", "recovered", "THRU fire", "THRU new FP"))
for thr in (0, 15, 20, 25, 30):
    o, h = run(thr)
    print("  %-9s %10d %10d %10d %10d" % ("%d deg" % thr, o["missed"]["fires"], o["missed"]["recovered"],
                                          o["THRU"]["fires"], o["THRU"]["recovered"]))

print()
print("=" * 78)
print("4. The chosen point (kink >= 15 deg, min drop 3cm) -- named")
print("=" * 78)
o, h = run(15.0)
for g in ("missed", "found", "THRU", "THRU_fp"):
    c = o[g]
    print("  %-8s fires %3d  recovered %3d   items: %s" % (g, c["fires"], c["recovered"], sorted(h[g])))
