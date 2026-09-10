#!/usr/bin/env python3
"""doc pdvd/56 -- score ANY PDVD arm against the frozen STM+Michel hand scan.

The 569-record scan (doc 55) is the reference; this turns it into a regression
metric so a CheckSTM_Michel / TaggerCheckSTM / TrackFitting change can be graded
on the whole census without a second hand scan.  It prints, for one arm:

  A. doc 55 sec 14.1 / 14.2 (is_stm and michel_found purity / efficiency, by
     tranche and for the census) and the sec 15.1 cut;
  B. the failure-register class counts of doc 55 sec 17 (A..L), recomputed;
  C. three intermediate metrics the doc-56 tasks are graded on:
       stop residual   |arm stop - scan pin| over the pinned items, the
                       profile-shape census (collapse / rise / flat per class),
                       and the find_first_kink sentinel rate per class;
       Michel attach.  for every fitted segment the scan tagged `michel`, does
                       the arm give it role 3 (Michel object) -- matched by
                       GEOMETRY to the baseline segment, since graph indices
                       are not stable across arms;
       interior arms   same-cluster fitted segments with no role on scan
                       stoppers (the class the scan tagged delta / other).

Usage:
    # baseline (the committed d53v payloads), and the diff against doc 55's literals
    python3 census_score.py --check
    # a new arm: prep its payloads into scratch first (never into prep-pdvd;
    # --sheetdir keeps the committed sheet/key untouched), then score
    ./prep_stm_michel_scan.py --det pdvd --arm <tag> \
        --outdir $W/prep_<tag> --sheetdir $W/sheet_<tag>
    python3 census_score.py --prep $W/prep_<tag> --arm <tag>

Join is by (event, cluster_id) -- stable for any change downstream of
clustering, which is every task in doc 56 -- and the unmatched count is
printed, never swallowed.  Read-only: writes nothing under work/ or
pdvd/docs/scan/.  Baseline (--prep default, --arm d53v) must reproduce doc 55.
"""
import argparse, collections, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import census_lib as C                                            # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--prep", default=C.PREP_DEFAULT, help="payload dir of the arm to score")
ap.add_argument("--arm", default="d53v", help="work/<evt>_<arm>/ tag, for T_stm_pass")
ap.add_argument("--baseline", default=C.PREP_DEFAULT, help="payload dir the scan was taken from (pins, michel geometry)")
ap.add_argument("--check", action="store_true", help="diff the baseline numbers against doc 55's literals")
ap.add_argument("--json", default=None, help="write the summary dict here (scratch)")
a = ap.parse_args()

rec = C.load_record()
sheet = C.load_sheet()
P, missing = C.load_payloads(a.prep, rec)
B0, _ = C.load_payloads(a.baseline, rec) if os.path.abspath(a.baseline) != os.path.abspath(a.prep) else (P, [])
print("arm %s: payloads %d of %d records; UNMATCHED %d" % (a.arm, len(P), len(rec), len(missing)))
if missing:
    print("  unmatched keys:", " ".join(missing[:20]), "..." if len(missing) > 20 else "")
keys = [k for k in rec if k in P]
for k in keys:
    rec[k]["_v"] = P[k]["verdict"]
    rec[k]["_is_stm"] = bool(P[k]["verdict"]["is_stm"])
    rec[k]["_mi"] = bool(P[k]["verdict"]["michel_found"])
J = [k for k in keys if C.judged(rec[k])]
summary = {"arm": a.arm, "n": len(P), "unmatched": len(missing)}

# ------------------------------------------------------------------ A. sec 14
def table(title, scan_pos, chain_pos, tag):
    print("\n=== %s ===" % title)
    print("%-22s %6s %5s %4s %5s %5s %8s %8s" % ("", "scored", "TP", "FP", "FN", "TN", "purity", "effic"))
    for nm, rows in (("tranche 1 (enriched)", [k for k in J if rec[k]["tranche"] == 1]),
                     ("tranche 2", [k for k in J if rec[k]["tranche"] == 2]),
                     ("census", J)):
        d = C.rates([rec[k] for k in rows], scan_pos, chain_pos)
        summary["%s/%s" % (tag, nm)] = d
        print("%-22s %6d %5d %4d %5d %5d %8.3f %8.3f" % (nm, d["scored"], d["tp"], d["fp"], d["fn"], d["tn"], d["purity"], d["efficiency"]))

table("14.1 is_stm", C.is_stopper, lambda r: r["_is_stm"], "is_stm")
table("14.2 michel_found", C.is_michel, lambda r: r["_mi"], "michel")
print("\n=== 15.1 the range-energy cut on the census ===")
for nm, fn_ in (("as shipped", lambda r: r["_mi"]),
                ("drop dis > 3 cm & KE < 10 MeV", lambda r: r["_mi"] and not ((r["_v"]["michel_dis_cm"] or 0) > 3.0 and (r["_v"]["michel_ke_best"] or 0) < 10.0))):
    d = C.rates([rec[k] for k in J], C.is_michel, fn_)
    summary["cut/" + nm] = d
    print("%-34s TP %3d FP %3d FN %3d purity %.3f efficiency %.3f F1 %.3f" % (nm, d["tp"], d["fp"], d["fn"], d["purity"], d["efficiency"], d["f1"]))

# ------------------------------------------------- B. failure classes (sec 17)
def stop_frame(pay):
    """Forward direction at the stop (from rr~20 cm to the stop) and the stop point."""
    rr, q, xyz = C.profile(pay)
    j = int(np.searchsorted(rr, 20.0))
    fwd = xyz[0] - xyz[min(j, len(xyz) - 1)]
    n = np.linalg.norm(fwd)
    return xyz[0], (fwd / n if n > 0 else fwd)

cls_items = collections.defaultdict(set)
def add(k, c):
    cls_items[c].add(k)
for k in keys:
    r = rec[k]; v = r["_v"]; pay = P[k]; sv = r["verdict"]
    if C.judged(r):
        if r["_is_stm"] and not C.is_stopper(r): add(k, "A_is_stm_false_positive")
        if C.is_stopper(r) and not r["_is_stm"]: add(k, "B_is_stm_false_negative")
        if r["_mi"] and not C.is_michel(r): add(k, "C_michel_false_positive")
        if C.is_michel(r) and not r["_mi"]: add(k, "D_michel_false_negative")
    if r["_mi"] and (v["michel_dis_cm"] or 0) > 3.0 and (v["michel_ke_best"] or 0) < 10.0:
        add(k, "E_michel_range_energy_impossible")
    stop, fwd = stop_frame(pay)
    rr, q, xyz = C.profile(pay)
    for s in pay["pf"]["seg"]:
        pts = C.seg_points(s)
        d_min = float(np.linalg.norm(pts - stop, axis=1).min())
        cen = pts.mean(0) - stop
        cf = float(np.dot(cen, fwd) / (np.linalg.norm(cen) + 1e-9))
        if cf >= 0.85 and d_min <= 2.0 and (s["len_cm"] or 0) <= 6.0 and (s["dqdx_med"] or 0) >= 1.67 * C.MIP:
            add(k, "F_fit_stops_short")
        live = q[q > 0]
        if len(live) >= 20 and (s["len_cm"] or 0) >= 20.0 and 0 < (s["dqdx_med"] or 0) < 0.25 * float(np.median(live)):
            add(k, "H_fit_unsupported_by_charge")
    take = np.where(rr <= 20.0)[0]
    if len(take) >= 6:
        L = np.asarray(pay["muon"]["L"], float)[np.argsort(np.asarray(pay["muon"]["rr"], float))]
        arc = abs(L[take[-1]] - L[take[0]])
        pts = xyz[take]
        if len(take) <= 60:
            span = max(np.linalg.norm(pts[i] - pts[j]) for i in range(len(pts)) for j in range(i + 1, len(pts)))
        else:
            span = float(np.linalg.norm(pts[0] - pts[-1]))
        if span > 0.01 and arc / span >= 1.5:
            add(k, "G_coiled_fit_end")
    if "not_muon_pid" in C.reject_names(v): add(k, "J_not_a_muon")
    if r.get("pin_rr") is not None: add(k, "K_stop_moved_by_scan")
    for nm in ("plateau_off_mip", "profile_sparse"):
        if nm in C.reject_names(v): add(k, "L_" + nm)
print("\n=== 17 failure classes (items) ===")
for c in sorted(cls_items):
    summary["class/" + c] = len(cls_items[c])
    print("  %-36s %4d" % (c, len(cls_items[c])))

# ------------------------------------------------------ C. intermediate metrics
print("\n=== C1. the stop ===")
SH = {k: C.shape(P[k]) for k in keys}
grp = collections.defaultdict(collections.Counter)
for k in J:
    g = ("stopper" if C.is_stopper(rec[k]) else "THRU") + ("/found" if rec[k]["_is_stm"] else "/missed")
    grp[g][SH[k]["cls"]] += 1
    s = C.sentinel(k, a.arm)
    grp[g]["sentinel" if s and s[0] >= s[1] else ("kink" if s else "no T_stm_pass")] += 1
print("%-16s %9s %6s %5s %9s %6s %12s" % ("class", "collapse", "rise", "flat", "sentinel", "kink", "no T_stm_pass"))
for g in sorted(grp):
    c = grp[g]
    print("%-16s %9d %6d %5d %9d %6d %12d" % (g, c["collapse"], c["rise-to-end"], c["flat"], c["sentinel"], c["kink"], c["no T_stm_pass"]))
    summary["shape/" + g] = dict(c)
# pins: the scan's pin lives on the BASELINE chain at rr = pin_rr; residual = distance to the arm's stop
res = []
for k in keys:
    pr = rec[k].get("pin_rr")
    if pr is None or k not in B0:
        continue
    rr0, q0, xyz0 = C.profile(B0[k])
    pin = xyz0[int(np.argmin(np.abs(rr0 - pr)))]
    v = P[k]["verdict"]
    stop = np.array([v["stop_x"], v["stop_y"], v["stop_z"]], float)
    res.append(float(np.linalg.norm(stop - pin)))
if res:
    res = np.array(res)
    print("stop residual vs the %d scan pins: median %.2f cm, p90 %.2f, max %.2f, within 2 cm: %d"
          % (len(res), np.median(res), np.percentile(res, 90), res.max(), (res <= 2).sum()))
    summary["pin_residual"] = dict(n=len(res), median=float(np.median(res)), p90=float(np.percentile(res, 90)), within2=int((res <= 2).sum()))

print("\n=== C2. Michel attachment: scan-tagged michel segments, matched by geometry into the arm ===")
def match_segment(pts0, pay):
    """The arm segment whose points sit on the baseline segment: best mean nearest-distance under 1.5 cm."""
    best, bd = None, 1.5
    for s in pay["pf"]["seg"]:
        pts = C.seg_points(s)
        d = np.mean([np.linalg.norm(pts0 - p, axis=1).min() for p in pts[:: max(1, len(pts) // 12)]])
        if d < bd:
            best, bd = s, d
    return best
att = collections.Counter(); att_items = collections.Counter()
for k in keys:
    if k not in B0 or not C.is_michel(rec[k]):
        continue
    segs0, _ = C.seg_index(B0[k])
    role = P[k]["pf"]["chain_role"]
    for t, tag in rec[k]["tags"].items():
        if tag != "michel" or t not in segs0:
            continue
        s = match_segment(C.seg_points(segs0[t]), P[k])
        if s is None:
            att["lost (no fitted segment there)"] += 1; att_items[k] += 1; continue
        rl = role.get(str(s["id"]))
        att[{3: "role 3 michel", 1: "role 1 muon (swallowed)", 2: "role 2 delta", 5: "role 5 gamma", 6: "role 6 survey", None: "no role"}.get(rl, "role %s" % rl)] += 1
tot = sum(att.values())
for nm, c in att.most_common():
    print("  %-28s %4d  (%.0f%%)" % (nm, c, 100 * c / max(tot, 1)))
summary["michel_attach"] = dict(att)

print("\n=== C3. interior arms: same-cluster fitted segments with no role, on scan stoppers ===")
n_items = 0; n_segs = 0; n_long = 0
for k in J:
    if not C.is_stopper(rec[k]):
        continue
    pay = P[k]; segs, cl = C.seg_index(pay); role = pay["pf"]["chain_role"]
    here = [s for t, s in segs.items() if t not in role and cl.get(t, {}).get("id") == pay["cluster_id"]]
    if here:
        n_items += 1; n_segs += len(here); n_long += sum(1 for s in here if s["len_cm"] > 5)
print("stoppers with >= 1: %d; segments %d; > 5 cm: %d" % (n_items, n_segs, n_long))
summary["interior_arms"] = dict(items=n_items, segs=n_segs, long=n_long)

if a.json:
    json.dump(summary, open(a.json, "w"), indent=1)
    print("\nwrote", a.json)

# ---------------------------------------------------------------- --check
if a.check:
    print("\n=== --check: recomputed baseline vs the literals of doc 55 (sec 14, sec 17 table) ===")
    want = {
        "is_stm/census": (549, 144, 9, 125, 271, 0.941, 0.535),
        "michel/census": (549, 111, 39, 41, 358, 0.740, 0.730),
        "class/A_is_stm_false_positive": 9, "class/B_is_stm_false_negative": 125,
        "class/C_michel_false_positive": 39, "class/D_michel_false_negative": 41,
        "class/E_michel_range_energy_impossible": 32, "class/F_fit_stops_short": 5,
        "class/G_coiled_fit_end": 18, "class/H_fit_unsupported_by_charge": 20,
        "class/J_not_a_muon": 1, "class/K_stop_moved_by_scan": 36,
        "class/L_plateau_off_mip": 50, "class/L_profile_sparse": 33,
    }
    bad = 0
    for key, w in want.items():
        got = summary.get(key)
        if isinstance(w, tuple):
            g = (got["scored"], got["tp"], got["fp"], got["fn"], got["tn"], round(got["purity"], 3), round(got["efficiency"], 3))
            ok = g == w
        else:
            g = got; ok = got == w
        bad += not ok
        print("  %-40s %s  doc %s  got %s" % (key, "OK  " if ok else "DIFF", w, g))
    print("%d of %d differ" % (bad, len(want)))
    sys.exit(1 if bad else 0)
