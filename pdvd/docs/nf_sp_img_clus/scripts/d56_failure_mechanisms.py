#!/usr/bin/env python3
"""doc pdvd/56 -- the payload arithmetic behind every table in the doc.

Reads the committed 569-record scan (doc 55) and the d53v prep payloads, and
prints, in doc order:

  1. the 125 missed stoppers by profile shape (collapse / rise-to-end / flat),
     against found stoppers and THRU;
  2. where the stop comes from: find_first_kink sentinel rate per class, read
     from T_stm_pass in each event's tracking-stm.root;
  3. on the collapse items, whether a PR vertex / a fitted-segment end already
     sits at the collapse onset;
  4. the two shape tests (Bragg contrast, KS) scored one at a time;
  5. dead-channel coverage of the last 15 cm, missed vs found vs THRU;
  6. the missed Michels: where the scan's michel objects live (role, cluster,
     attachment) and which admission gate refuses the arms at the fit end;
  7. the false Michels by conn_type and scan tag; the 9 is_stm false positives;
  8. unassociated (delta / other) segments on stoppers by attachment and length;
  9. the 0.6 cm step: plateau point-to-point scatter PDVD vs PDHD, and the
     effect of a 2-point rebin.

Repro:
    cd wcp-porting-img
    python3 pdvd/docs/nf_sp_img_clus/scripts/d56_failure_mechanisms.py [--prep DIR] [--arm d53v]

Read-only.  Nothing under work/ or pdvd/docs/scan/ is written.
"""
import argparse, collections, glob, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, IMG + "/pdhd/stm_michel_scan")
import census_lib as C                                            # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--prep", default=C.PREP_DEFAULT)
ap.add_argument("--arm", default="d53v", help="work/<evt>_<arm>/tracking-stm.root for T_stm_pass")
ap.add_argument("--prep-pdhd", default=IMG + "/pdhd/stm_michel_scan/prep-pdhd")
a = ap.parse_args()

rec = C.load_record()
P, missing = C.load_payloads(a.prep, rec)
print("record %d items, payloads %d, missing %d" % (len(rec), len(P), len(missing)))
if missing:
    print("  MISSING:", missing[:10], "...")
keys = [k for k in rec if k in P]
J = [k for k in keys if C.judged(rec[k])]
stop = [k for k in J if C.is_stopper(rec[k])]
thru = [k for k in J if not C.is_stopper(rec[k])]
B = [k for k in stop if not P[k]["verdict"]["is_stm"]]
TP = [k for k in stop if P[k]["verdict"]["is_stm"]]
A = [k for k in thru if P[k]["verdict"]["is_stm"]]
print("judged %d: scan stoppers %d (chain found %d, missed %d), non-stoppers %d (chain accepted %d)"
      % (len(J), len(stop), len(TP), len(B), len(thru), len(A)))
print("tagger-level purity on this sample (all 569 are Flags::STM): %d/%d = %.2f" % (len(stop), len(J), len(stop) / len(J)))

SH = {k: C.shape(P[k]) for k in keys}

# ---- 1. shape classes
print("\n=== 1. profile shape of the last 15 cm ===")
print("%-14s %8s %8s %8s" % ("class", "missed", "found", "THRU"))
for cls in ("collapse", "rise-to-end", "flat", "short"):
    print("%-14s %8d %8d %8d" % (cls, sum(SH[k]["cls"] == cls for k in B),
                                  sum(SH[k]["cls"] == cls for k in TP), sum(SH[k]["cls"] == cls for k in thru)))
Bc = [k for k in B if SH[k]["cls"] == "collapse"]
Br = [k for k in B if SH[k]["cls"] == "rise-to-end"]
Bf = [k for k in B if SH[k]["cls"] == "flat"]
pins = {k for k in B if rec[k].get("pin_rr") is not None}
print("collapse & pinned %d, collapse & not pinned %d, pinned & not collapse %d"
      % (len(set(Bc) & pins), len(set(Bc) - pins), len(pins - set(Bc))))
print("  pinned, no arithmetic collapse:", sorted(pins - set(Bc)))
print("  collapse, not pinned:", sorted(set(Bc) - pins))
print("collapse peak at rr: median %.1f cm, p90 %.1f" % (np.median([SH[k]["rpk"] for k in Bc]), np.percentile([SH[k]["rpk"] for k in Bc], 90)))
print("missed rise-to-end, reject bits:", collections.Counter("|".join(C.reject_names(P[k]["verdict"])) for k in Br).most_common())
print("missed flat: n %d, michel_kind %s, confidence %s" % (len(Bf), dict(collections.Counter(rec[k]["michel_kind"] for k in Bf)), dict(collections.Counter(rec[k]["confidence"] for k in Bf))))
print("all missed, reject bits:", collections.Counter("|".join(C.reject_names(P[k]["verdict"])) for k in B).most_common())

# ---- 2. the sentinel
print("\n=== 2. find_first_kink: sentinel (stop = last fit row) per class, from T_stm_pass ===")
print("%-28s %4s %8s %10s %9s" % ("class", "n", "no-pass", "sentinel", "real kink"))
groups = collections.defaultdict(list)
for k in J:
    g = ("stopper" if C.is_stopper(rec[k]) else "THRU", "found" if P[k]["verdict"]["is_stm"] else "missed", SH[k]["cls"])
    groups[g].append(C.sentinel(k, a.arm))
for g in sorted(groups):
    v = groups[g]
    nn = sum(1 for s in v if s is None)
    sen = sum(1 for s in v if s and s[0] >= s[1])
    ok = sum(1 for s in v if s and s[0] < s[1])
    print("%-28s %4d %8d %10d %9d" % ("/".join(g), len(v), nn, sen, ok))
d = sorted(s[1] - 1 - s[0] for k in Bc for s in [C.sentinel(k, a.arm)] if s and s[0] < s[1])
print("missed collapse with a real kink: rows between kink and last row:", d)

# ---- 3. a vertex at the collapse onset?
print("\n=== 3. missed collapse items: nearest PR vertex / segment end to the collapse onset ===")
rows = []
for k in Bc:
    dv, de = C.collapse_vertex_distance(P[k], SH[k])
    v = P[k]["verdict"]
    rows.append((k, SH[k]["rpk"], SH[k]["onset_rr"], dv, de, v["stop_dis"], v["n_ext"], v["n_chain_segs"], rec[k].get("pin_rr")))
dv = np.array([r[3] for r in rows])
print("n %d; nearest vertex to onset: median %.1f cm, <=2 cm %d, <=4 cm %d, >6 cm %d"
      % (len(rows), np.median(dv), (dv <= 2).sum(), (dv <= 4).sum(), (dv > 6).sum()))
print("n_ext>0 on %d; chain stop vs tagger stop median %.2f cm" % (sum(r[6] > 0 for r in rows), np.median([r[5] for r in rows])))
print("%-14s %5s %6s %5s %5s %7s %4s %4s %s" % ("item", "rpk", "onset", "dvtx", "dseg", "stopdis", "next", "nseg", "pin"))
for r in sorted(rows, key=lambda r: -r[1]):
    print("%-14s %5.1f %6.1f %5.1f %5.1f %7.2f %4d %4d %s" % r)

# ---- 4. the two shape tests alone
print("\n=== 4. contrast and KS scored one at a time (judged items with a valid profile) ===")
X, Y, K = [], [], []
for k in J:
    v = P[k]["verdict"]
    if not v["bragg_valid"] or v["contrast_expected"] <= 0:
        continue
    X.append(v["contrast"] / v["contrast_expected"]); Y.append(v["ks_flat"] - v["ks_mu"]); K.append(C.is_stopper(rec[k]))
X, Y, K = np.array(X), np.array(Y), np.array(K)
print("n %d, stoppers %d" % (len(X), K.sum()))
def pe(sel):
    tp = (sel & K).sum(); fp = (sel & ~K).sum(); fn = (~sel & K).sum()
    return "TP %3d FP %3d FN %3d purity %.3f efficiency %.3f" % (tp, fp, fn, tp / max(tp + fp, 1), tp / max(tp + fn, 1))
for thr in (0.6, 0.7, 0.75, 0.8, 0.9):
    print("contrast >= %.2f x expected: %s" % (thr, pe(X >= thr)))
for m in (0.0, -0.02, -0.05):
    print("ks_flat - ks_mu > %.2f:        %s" % (m, pe(Y > m)))
print("both as shipped (0.60, 0):      %s" % pe((X >= 0.6) & (Y > 0)))
print("stoppers with contrast >= 0.8 x expected: %d, of which KS calls flat: %d" % (((X >= 0.8) & K).sum(), ((X >= 0.8) & K & (Y <= 0)).sum()))
print("\nthe %d is_stm false positives:" % len(A))
for k in A:
    v = P[k]["verdict"]; r = rec[k]
    print("  %-14s %s conf %-6s len %5.0f contrast %.2f/%.2f (%.2f) ks %.2f/%.2f ke_range %.0f mcs %.0f"
          % (k, r["verdict"], r["confidence"], P[k]["muon_len_cm"], v["contrast"], v["contrast_expected"],
             v["contrast"] / v["contrast_expected"], v["ks_mu"], v["ks_flat"], v["muon_ke_range"], v["muon_ke_mcs"]))

# ---- 5. dead channels
print("\n=== 5. dead-channel coverage of the last 15 cm (>= 20 %% of points on a dead band) ===")
for nm, S in (("missed", B), ("found", TP), ("THRU", thru)):
    fr = [C.dead_fraction_last(P[k]) for k in S]
    a1 = sum(1 for f in fr if max(f.values()) > 0.2); a2 = sum(1 for f in fr if sum(x > 0.2 for x in f.values()) >= 2)
    print("%-7s n=%3d  >=1 plane: %3d (%2.0f%%)  >=2 planes: %d" % (nm, len(S), a1, 100 * a1 / len(S), a2))
z = sum(1 for k in stop for rr_, q_, _ in [C.profile(P[k])] if ((rr_ <= 10) & (q_ <= 0)).any())
print("stoppers with a q<=0 point in the last 10 cm: %d" % z)

# ---- 6. missed Michels
D = [k for k in J if C.is_michel(rec[k]) and not P[k]["verdict"]["michel_found"]]
print("\n=== 6. the %d missed Michels ===" % len(D))
print("on chain-rejected items: %d; michel_kind %s" % (sum(1 for k in D if not P[k]["verdict"]["is_stm"]), dict(collections.Counter(rec[k]["michel_kind"] for k in D))))
where = collections.Counter(); att = collections.Counter(); gates = collections.Counter(); armrows = []
for k in D:
    p = P[k]; segs, cl = C.seg_index(p); role = p["pf"]["chain_role"]
    mi = [t for t, v in rec[k]["tags"].items() if v == "michel"]
    if not mi:
        where["no michel tag (split row)"] += 1
    for t in mi:
        if t.startswith("C"):
            where["unfitted cluster"] += 1; continue
        if t not in segs:
            where["unknown"] += 1; continue
        same = cl.get(t, {}).get("id") == p["cluster_id"]
        rl = role.get(t)
        where[("role %s" % rl if rl is not None else "no role") + (" same cluster" if same else " other cluster")] += 1
        d0 = C.arm_at_fit_end(p, segs[t])
        rr_, q_, xyz_ = C.profile(p)
        pts = C.seg_points(segs[t])
        dmin = min(np.linalg.norm(xyz_ - pts[0], axis=1).min(), np.linalg.norm(xyz_ - pts[-1], axis=1).min())
        i = int(np.argmin(np.minimum(np.linalg.norm(xyz_ - pts[0], axis=1), np.linalg.norm(xyz_ - pts[-1], axis=1))))
        att["detached >3 cm" if dmin > 3 else ("at the fit end (rr<1.5)" if rr_[i] < 1.5 else "interior vertex (rr>=1.5)")] += 1
        if rl != 1 and d0 <= 1.5:
            f, mip, kink = C.michel_gate_failures(p, segs[t])
            gates[",".join(f) if f else "passes every threshold"] += 1
            armrows.append((k, t, round(segs[t]["len_cm"], 1), round(mip, 2), round(kink), ",".join(f)))
print("scan michel objects by chain role:", dict(where))
print("scan michel segments by attachment:", dict(att))
print("arms touching the fit end, offline gate test (C++ defaults, mip_median %d):" % C.MIP_MEDIAN, dict(gates))
for r in armrows:
    print("  ", r)

# ---- 7. false Michels and STM false positives
Cm = [k for k in J if not C.is_michel(rec[k]) and P[k]["verdict"]["michel_found"]]
print("\n=== 7. the %d false Michels ===" % len(Cm))
cnt = collections.Counter()
for k in Cm:
    v = P[k]["verdict"]
    cnt[(rec[k]["verdict"], v["michel_conn_type"], rec[k]["tags"].get(str(v["michel_seg_id"]), "(absent)"))] += 1
for kk, c in sorted(cnt.items(), key=lambda x: -x[1]):
    print("  %3d  scan %-10s conn %d  chain's michel seg tagged %s" % (c, *kk))
so = [k for k in Cm if rec[k]["verdict"] == "STM_ONLY"]
print("on STM_ONLY: n %d, conn2 %d, dis median %.1f cm, KE median %.1f MeV" % (len(so), sum(P[k]["verdict"]["michel_conn_type"] == 2 for k in so),
      np.median([P[k]["verdict"]["michel_dis_cm"] for k in so]), np.median([P[k]["verdict"]["michel_ke_best"] for k in so])))

# ---- 8. unassociated segments
print("\n=== 8. delta / other tags on stoppers ===")
loc = collections.Counter(); cat = collections.Counter(); big = collections.Counter(); mips = []
for k in stop:
    p = P[k]; segs, cl = C.seg_index(p); role = p["pf"]["chain_role"]; rr_, q_, xyz_ = C.profile(p)
    for t, v in rec[k]["tags"].items():
        if v != "delta / other":
            continue
        if t.startswith("C"):
            loc["unfitted cluster"] += 1; continue
        if t not in segs:
            continue
        same = cl.get(t, {}).get("id") == p["cluster_id"]
        rl = role.get(t)
        loc[("same cluster" if same else "other cluster") + (", role %s" % rl if rl is not None else ", no role")] += 1
        if not same or rl is not None:
            continue
        s = segs[t]; pts = C.seg_points(s)
        d = min(np.linalg.norm(xyz_ - pts[0], axis=1).min(), np.linalg.norm(xyz_ - pts[-1], axis=1).min())
        i = int(np.argmin(np.minimum(np.linalg.norm(xyz_ - pts[0], axis=1), np.linalg.norm(xyz_ - pts[-1], axis=1))))
        cat[("attached" if d <= 2 else "near 2-6 cm" if d <= 6 else "far >6 cm", "<=8 cm" if s["len_cm"] <= 8 else ">8 cm", "stop rr<3" if rr_[i] < 3 else "interior")] += 1
        if s["len_cm"] > 8:
            big[k] += 1
            if d <= 2:
                mips.append(s["dqdx_med"] / C.MIP_MEDIAN)
print("by location / role:", dict(loc))
for kk, c in sorted(cat.items(), key=lambda x: -x[1]):
    print("  %4d  %s" % (c, ", ".join(kk)))
print("attached > 8 cm: n %d, mip median %.2f, > 1.4 MIP: %d" % (len(mips), np.median(mips), sum(m > 1.4 for m in mips)))
print("items with most > 8 cm no-role same-cluster segments:", big.most_common(8))
print("chain n_delta on stoppers:", dict(collections.Counter(P[k]["verdict"]["n_delta"] for k in stop)))

# ---- 9. the step
print("\n=== 9. the 0.6 cm step: plateau point-to-point |dlog q| (rr 20-80 cm, live) ===")
def scatter(files, w=1):
    out = []
    for f in files:
        import json
        d = json.load(open(f)); m = d["muon"]; rr = np.asarray(m["rr"]); q = np.asarray(m["q"]); o = np.argsort(rr); rr, q = rr[o], q[o]
        sel = (rr > 20) & (rr < 80) & (q > 0); qq = q[sel]
        if len(qq) < 16:
            continue
        if w > 1:
            qq = qq[:len(qq) // w * w].reshape(-1, w).mean(1)
        out.append(np.median(np.abs(np.diff(np.log(qq)))))
    return np.array(out)
fv = sorted(glob.glob(a.prep + "/smprep-*.json")); fh = sorted(glob.glob(a.prep_pdhd + "/smprep-*.json"))
import json
steps = [np.median(np.abs(np.diff(json.load(open(f))["muon"]["L"]))) for f in fv[:100]]
print("PDVD L step: median %.3f cm (p10 %.3f, p90 %.3f)" % (np.median(steps), np.percentile(steps, 10), np.percentile(steps, 90)))
for w in (1, 2):
    sv, shd = scatter(fv, w), scatter(fh, w)
    print("bin %d pt: PDVD %.3f (n=%d)   PDHD %.3f (n=%d)" % (w, np.median(sv), len(sv), np.median(shd), len(shd)))
