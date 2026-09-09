#!/usr/bin/env python3
"""Build the CheckSTM_Michel failure register: every item, keyed by failure class.

The point is to hand a developer a *starting set*, not a narrative: each class
is a query over the payloads plus the hand scan, so the list regenerates and can
be re-run after a fix to see whether the class shrank.

Writes:
  pdvd/docs/scan/pdvd_stm_michel_failures.tsv   one row per (item, class)
and prints the per-class census.
"""
import csv, json, math, os, statistics as st, sys, collections

IMG = "/home/xqian/toolkit-dev/wcp-porting-img"
P = IMG + "/pdhd/stm_michel_scan/prep-pdvd"
sys.path.insert(0, IMG + "/pdhd/stm_michel_scan")
import scan_harness as H                                          # noqa: E402

MIP = 54000.0

# ---- the hand scan: the committed 569-record scan record, and nothing else.
#
# This used to merge a raw os.walk of the scratch t2/v_parts tree on top of the
# record.  That was a defect: v_parts holds 517 per-scanner files for 509 items
# (eight were scanned twice), and one of those pairs disagrees, so "recs[key] =
# r" in filesystem order let two runs of this script produce different rows for
# 039349_62/63.  A published register has to regenerate identically, so the
# duplicate is now resolved once, upstream, by t2/resolve.py -- which breaks the
# tie to whichever scan matches the label the app actually wrote -- and this
# reads only the committed record that resolution produced.
scan = {r["key"]: r for r in
        json.load(open(IMG + "/pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json"))}

sheet = {"%s/%s" % (r["event"], r["cluster"]): r for r in csv.DictReader(
    [l for l in open(IMG + "/pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv")
     if not l.startswith("#")], delimiter="\t")}


def is_stm_scan(v):
    return v.replace("FRAG_", "") in ("STM_MICHEL", "STM_ONLY")


def is_mi_scan(v):
    return v.replace("FRAG_", "") == "STM_MICHEL"


rows = []      # (item, class, detail)
def add(k, cls, detail):
    rows.append((k, cls, detail))


for k, r in sorted(scan.items()):
    p = "%s/smprep-%s.json" % (P, k.replace("/", "-c"))
    if not os.path.exists(p):
        continue
    pay = json.load(open(p))
    v = pay.get("verdict") or {}
    m = pay.get("muon") or {}
    q = m.get("q") or []
    rr = m.get("rr") or []
    L = m.get("L") or []
    X, Y, Z = m.get("x") or [], m.get("y") or [], m.get("z") or []
    sv = r["verdict"]
    judged = sv not in ("MESSY", "UNCLEAR")
    chain_stm = bool(v.get("is_stm"))
    chain_mi = bool(v.get("michel_found"))

    # ---- A/B: the flag's own errors, scored against the scan
    if judged:
        if chain_stm and not is_stm_scan(sv):
            add(k, "A_is_stm_false_positive",
                "chain is_stm=1, scan %s" % sv)
        if is_stm_scan(sv) and not chain_stm:
            add(k, "B_is_stm_false_negative",
                "scan %s, chain rejects %s" % (sv, "|".join(v.get("reject_names") or [])))
        if chain_mi and not is_mi_scan(sv):
            add(k, "C_michel_false_positive",
                "chain michel_found=1 (conn %s, dis %.1f cm, KE %.1f MeV), scan %s"
                % (v.get("michel_conn_type"), v.get("michel_dis_cm") or 0.0,
                   v.get("michel_ke_best") or 0.0, sv))
        if is_mi_scan(sv) and not chain_mi:
            add(k, "D_michel_false_negative",
                "scan STM_MICHEL, chain reports no daughter")

    # ---- E: the chain's Michel is kinematically impossible
    if chain_mi:
        dis = v.get("michel_dis_cm") or 0.0
        ke = v.get("michel_ke_best") or 0.0
        if dis > 3.0 and ke < 10.0:
            add(k, "E_michel_range_energy_impossible",
                "michel %.1f cm from the stop carrying %.1f MeV (conn %s)"
                % (dis, ke, v.get("michel_conn_type")))

    # ---- F: the fit stops SHORT (a forward high-charge tip past the fit end)
    try:
        pin = [float(v["stop_" + a]) for a in "xyz"]
        geo = H.object_geometry("pdvd", k, pin)
    except Exception:
        geo = {}
    for s in pay["pf"]["seg"]:
        g = geo.get(str(s["id"]))
        if not g:
            continue
        cf, dm = g.get("cos_fwd"), g.get("d_min")
        ln = s.get("len_cm") or 0
        md = s.get("dqdx_med") or 0
        if cf is None or dm is None:
            continue
        if cf >= 0.85 and dm <= 2.0 and ln <= 6.0 and md >= 1.67 * MIP:
            add(k, "F_fit_stops_short",
                "seg %s: %.1f cm at %d e/cm (%.2f MIP) forward of the fit end"
                % (s["id"], ln, md, md / MIP))

    # ---- G: coiled fit end (arc >> 3-D span over the last 20 cm)
    if X and L and len(X) >= 10 and len(rr) == len(X):
        idx = sorted(range(len(X)), key=lambda i: rr[i])
        take = [i for i in idx if rr[i] <= 20.0]
        if len(take) >= 6:
            arc = abs(L[take[-1]] - L[take[0]])
            if len(take) <= 60:
                span = max(math.dist((X[i], Y[i], Z[i]), (X[j], Y[j], Z[j]))
                           for a2, i in enumerate(take) for j in take[a2 + 1:])
            else:
                span = math.dist((X[take[0]], Y[take[0]], Z[take[0]]),
                                 (X[take[-1]], Y[take[-1]], Z[take[-1]]))
            if span > 0.01 and arc / span >= 1.5:
                add(k, "G_coiled_fit_end",
                    "%.1f cm of fit arc inside a %.1f cm ball (ratio %.2f)"
                    % (arc, span, arc / span))

    # ---- H: a long fitted segment carrying almost no charge
    live = [x for x in q if x > 0]
    if len(live) >= 20:
        plat = st.median(live)
        for s in pay["pf"]["seg"]:
            ln = s.get("len_cm") or 0
            md = s.get("dqdx_med") or 0
            if ln >= 20.0 and md > 0 and md < 0.25 * plat:
                add(k, "H_fit_unsupported_by_charge",
                    "seg %s: %.1f cm at %d e/cm = %.2f of the track plateau"
                    % (s["id"], ln, md, md / plat))

    # ---- I: seg_rej.d_stop disagrees with the geometry, or carries a sentinel
    segs = {str(s["id"]): s for s in pay["pf"]["seg"]}
    try:
        stop = [float(v["stop_" + a]) for a in "xyz"]
    except Exception:
        stop = None
    if stop:
        for i, rj in (pay["pf"].get("seg_rej") or {}).items():
            ds = rj.get("d_stop")
            s = segs.get(str(i))
            if s is None or ds is None or not s.get("x"):
                continue
            true = min(math.dist((s["x"][j], s["y"][j], s["z"][j]), stop)
                       for j in range(len(s["x"])))
            if ds > 1e6:
                add(k, "I_d_stop_sentinel",
                    "seg %s: d_stop=%g reaches the display; true %.1f cm" % (i, ds, true))
            elif abs(true - ds) > 5.0:
                add(k, "I_d_stop_wrong",
                    "seg %s: d_stop=%.1f, true %.1f cm (off by %.1f)"
                    % (i, ds, true, abs(true - ds)))

    # ---- J: the scan says this is not a muon at all
    if "not_muon_pid" in (v.get("reject_names") or []):
        add(k, "J_not_a_muon", "chain reject not_muon_pid; scan %s" % sv)

    # ---- K: the scan moved the stop (the chain's own end was wrong)
    if r.get("pin_rr") is not None:
        add(k, "K_stop_moved_by_scan",
            "scan moved the stop %.2f cm back along the fit" % r["pin_rr"])

    # ---- L: classes where the charge scale is not to be trusted
    for nm in ("plateau_off_mip", "profile_sparse"):
        if nm in (v.get("reject_names") or []):
            add(k, "L_" + nm, "chain flags %s" % nm)

out = IMG + "/pdvd/docs/scan/pdvd_stm_michel_failures.tsv"
with open(out, "w") as fh:
    fh.write("# doc pdvd/55 sec 17 -- CheckSTM_Michel failure register, arm d53v.\n")
    fh.write("# One row per (item, failure class).  Regenerate with "
             "pdhd/stm_michel_scan/mkfailures.py after a fix to see whether a class shrank.\n")
    fh.write("# 'scan' columns are the hand scan (doc 55); everything else is the chain's own payload.\n")
    fh.write("item\tscan_id\ttranche\tfailure_class\tscan_verdict\tchain_is_stm\tchain_reject\tdetail\n")
    for k, cls, detail in sorted(rows, key=lambda t: (t[1], t[0])):
        p = "%s/smprep-%s.json" % (P, k.replace("/", "-c"))
        v = (json.load(open(p)).get("verdict") or {})
        sh = sheet.get(k, {})
        fh.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n"
                 % (k, sh.get("scan_id", ""), sh.get("tranche", ""), cls,
                    scan[k]["verdict"], 1 if v.get("is_stm") else 0,
                    "|".join(v.get("reject_names") or []), detail))
print("wrote %s" % out)
c = collections.Counter(cls for _, cls, _ in rows)
items = collections.defaultdict(set)
for k, cls, _ in rows:
    items[cls].add(k)
print("\n%-38s %6s %6s" % ("failure class", "rows", "items"))
for cls in sorted(c):
    print("  %-36s %6d %6d" % (cls, c[cls], len(items[cls])))
print("\ntotal rows %d over %d distinct items" % (len(rows), len({k for k, _, _ in rows})))
