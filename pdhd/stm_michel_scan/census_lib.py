#!/usr/bin/env python3
"""doc pdvd/56 -- shared primitives for scoring an arm against the STM+Michel hand scan.

Imported by census_score.py (the per-arm regression metric) and by
pdvd/docs/nf_sp_img_clus/scripts/d56_failure_mechanisms.py (the analysis behind
the doc's tables).  Everything here is arithmetic over two inputs and nothing
else:

  * the committed scan record  pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json
    (569 records: verdict, michel_kind, confidence, evidence, per-object tags),
  * a directory of prep payloads written by prep_stm_michel_scan.py for ONE arm
    (default: pdhd/stm_michel_scan/prep-pdvd, arm d53v).

No file under work/ or pdvd/docs/scan/ is ever written.  The scan record is
"the chain's reconstruction reviewed by a physicist" (doc 55 sec 16.3), so every
number computed here is a change RELATIVE to the d53v baseline, not truth.

Definitions that the doc quotes (keep the doc and this file in step):

  stopper      scan verdict STM_MICHEL or STM_ONLY, FRAG_ prefix stripped
  judged       scan verdict not MESSY / UNCLEAR
  shape class  of the last 15 cm of the LIVE profile (q > 0), running median
               over 3 points, plateau = median over rr 20-60 cm (or rr > 10 cm):
                 collapse     peak >= 1.4 x plateau at rr 1.2-15 cm AND the last
                              3 points' median < peak / 1.8
                 rise-to-end  peak >= 1.4 x plateau, no collapse
                 flat         otherwise
                 short        fewer than 10 live points or < 3 in the window
  collapse onset  walking from the peak towards rr = 0, the first point whose
               running median falls below 0.6 x peak
  sentinel     T_stm_pass.kink_num >= npoints on the accepted pass (status 0,
               lowest pass index) -- find_first_kink found no kink and
               CheckSTM_Michel.cxx:788 clamped the stop to the last fit row
"""
import csv, glob, json, os, sys
import numpy as np

IMG = "/home/xqian/toolkit-dev/wcp-porting-img"
REC = IMG + "/pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json"
SHEET = IMG + "/pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv"
PREP_DEFAULT = IMG + "/pdhd/stm_michel_scan/prep-pdvd"
WORK = IMG + "/pdvd/work"
MIP = 54000.0            # e/cm, the display's own reference curve plateau
MIP_MEDIAN = 47000.0     # mip_dqdx_median the PDVD taggers run with (wct-pr-perevt.jsonnet:301)
STM_BITS = ["no_chain", "stop_unmatched", "no_bragg", "shape_flat", "not_muon_pid",
            "continuation", "stop_near_boundary", "vertex_hadron", "short",
            "profile_sparse", "plateau_off_mip", "stop_into_dead", "cluster_not_track"]


def bare(v):
    return v.replace("FRAG_", "")


def is_stopper(r):
    return bare(r["verdict"]) in ("STM_MICHEL", "STM_ONLY")


def is_michel(r):
    return bare(r["verdict"]) == "STM_MICHEL"


def judged(r):
    return r["verdict"] not in ("MESSY", "UNCLEAR")


def load_record():
    return {r["key"]: r for r in json.load(open(REC))}


def load_sheet():
    return {"%s/%s" % (r["event"], r["cluster"]): r for r in csv.DictReader(
        [l for l in open(SHEET) if not l.startswith("#")], delimiter="\t")}


def payload_path(prep, key):
    return "%s/smprep-%s.json" % (prep, key.replace("/", "-c"))


def load_payloads(prep, keys):
    """Return ({key: payload}, [missing keys]).  A missing payload is reported,
    never silently skipped: a re-run that lost a candidate is a finding."""
    P, missing = {}, []
    for k in keys:
        p = payload_path(prep, k)
        if os.path.exists(p):
            P[k] = json.load(open(p))
        else:
            missing.append(k)
    return P, missing


def reject_names(v):
    rb = int(v.get("reject_bits") or 0)
    return [n for i, n in enumerate(STM_BITS) if rb >> i & 1]


# ---------------------------------------------------------------- the profile
def profile(pay):
    m = pay["muon"]
    rr = np.asarray(m["rr"], float)
    q = np.asarray(m["q"], float)
    xyz = np.c_[m["x"], m["y"], m["z"]].astype(float)
    o = np.argsort(rr)
    return rr[o], q[o], xyz[o]


def running_median(q, w=3):
    return np.array([np.median(q[max(0, i - w // 2):i + w // 2 + 1]) for i in range(len(q))])


def shape(pay):
    """-> dict(cls, peak, rpk, tail, ratio, onset_rr, onset_pt, plateau) or cls='short'."""
    rr, q, xyz = profile(pay)
    live = q > 0
    rr, q, xyz = rr[live], q[live], xyz[live]
    if len(q) < 10:
        return dict(cls="short")
    rm = running_median(q, 3)
    sel = (rr > 20) & (rr < 60)
    plateau = float(np.median(q[sel])) if sel.sum() > 5 else float(np.median(q[rr > 10])) if (rr > 10).sum() else float(np.median(q))
    win = (rr >= 1.2) & (rr <= 15)
    if win.sum() < 3 or plateau <= 0:
        return dict(cls="short")
    ipk = int(np.argmax(np.where(win, rm, -1)))
    peak = float(rm[ipk])
    last3 = float(np.median(q[:3]))
    ratio = peak / last3 if last3 > 0 else float("inf")
    out = dict(peak=peak / plateau, rpk=float(rr[ipk]), tail=last3 / plateau, ratio=ratio, plateau=plateau)
    if out["peak"] > 1.4 and ratio > 1.8:
        j = ipk
        while j > 0 and rm[j] >= 0.6 * peak:
            j -= 1
        out.update(cls="collapse", onset_rr=float(rr[j]), onset_pt=xyz[j])
    elif out["peak"] > 1.4:
        out["cls"] = "rise-to-end"
    else:
        out["cls"] = "flat"
    return out


# ------------------------------------------------------- the tagger's own pass
_stm_pass_cache = {}


def stm_pass(event, arm):
    """T_stm_pass arrays of one event's tracking-stm.root, or None when absent."""
    fn = "%s/%s_%s/tracking-stm.root" % (WORK, event, arm)
    if fn in _stm_pass_cache:
        return _stm_pass_cache[fn]
    t = None
    if os.path.exists(fn):
        import uproot
        try:
            t = uproot.open(fn)["T_stm_pass"].arrays(library="np")
        except Exception:
            t = None
    _stm_pass_cache[fn] = t
    return t


def sentinel(key, arm):
    """(kink_num, npoints) of the accepted pass, or None (no file / no pass)."""
    ev, c = key.split("/")
    t = stm_pass(ev, arm)
    if t is None:
        return None
    sel = (t["cluster_id"] == int(c)) & (t["status"] == 0)
    if not sel.any():
        return None
    i = np.where(sel)[0][np.argmin(t["pass"][sel])]
    return int(t["kink_num"][i]), int(t["npoints"][i])


# ------------------------------------------------------------ objects, arms
def seg_index(pay):
    segs = {str(s["id"]): s for s in pay["pf"]["seg"]}
    cl_of = {}
    for nc in pay["near_clusters"]:
        for s in nc["segs"]:
            cl_of[str(s)] = nc
    return segs, cl_of


def seg_points(s):
    return np.c_[s["x"], s["y"], s["z"]].astype(float)


def arm_at_fit_end(pay, s, tol=1.5):
    """Distance of the segment's nearer endpoint to the chain's rr=0 point."""
    rr, q, xyz = profile(pay)
    pts = seg_points(s)
    return float(min(np.linalg.norm(pts[0] - xyz[0]), np.linalg.norm(pts[-1] - xyz[0])))


def arm_kink_deg(pay, s):
    """Angle between the muon's last 5 cm and the arm's first ~5 cm, from the
    endpoint nearer the stop.  An offline stand-in for segment_pair_kink_deg."""
    rr, q, xyz = profile(pay)
    i5 = int(np.searchsorted(rr, 5.0))
    mdir = xyz[0] - xyz[min(i5, len(xyz) - 1)]
    mdir /= np.linalg.norm(mdir) + 1e-9
    pts = seg_points(s)
    if np.linalg.norm(pts[-1] - xyz[0]) < np.linalg.norm(pts[0] - xyz[0]):
        pts = pts[::-1]
    L = np.cumsum(np.r_[0, np.linalg.norm(np.diff(pts, axis=0), axis=1)])
    j = int(np.searchsorted(L, 5.0))
    adir = pts[min(j, len(pts) - 1)] - pts[0]
    adir /= np.linalg.norm(adir) + 1e-9
    return float(np.degrees(np.arccos(np.clip(np.dot(mdir, adir), -1, 1))))


def michel_gate_failures(pay, s, mip_median=MIP_MEDIAN):
    """Which stm_michel_classify_stop_arm thresholds (C++ defaults; PDVD sets
    michel_shower_min_kink_deg 15 and nothing else) the arm fails, offline."""
    mip = (s.get("dqdx_med") or 0.0) / mip_median
    kink = arm_kink_deg(pay, s)
    ln = s.get("len_cm") or 0.0
    fails = []
    if kink < 20 and ln > 3 and 0.7 <= mip <= 1.3:
        return ["CONTINUATION"], mip, kink
    if mip <= 0.3:
        fails.append("mip<0.3")
    if mip >= 2.0:
        fails.append("mip>2")
    if kink < 30:
        fails.append("kink<30")
    if ln > 25:
        fails.append("len>25")
    return fails, mip, kink


def collapse_vertex_distance(pay, sh):
    """Nearest PR vertex, and nearest fitted-segment end, to the collapse onset."""
    V = pay["pf"]["vtx"]
    vx = np.c_[V["x"], V["y"], V["z"]].astype(float)
    dv = float(np.linalg.norm(vx - sh["onset_pt"], axis=1).min()) if len(vx) else float("nan")
    ends = []
    for s in pay["pf"]["seg"]:
        pts = seg_points(s)
        ends.append(float(np.linalg.norm(pts[0] - sh["onset_pt"])))
        ends.append(float(np.linalg.norm(pts[-1] - sh["onset_pt"])))
    de = min(ends) if ends else float("nan")
    return dv, de


def dead_fraction_last(pay, cm=15.0, planes="uvw"):
    """Fraction of the last `cm` of chain points sitting on a dead (ch, t) band, per plane."""
    m = pay["muon"]
    rr = np.asarray(m["rr"], float)
    sel = rr <= cm
    out = {}
    for pl in planes:
        ch = np.asarray(m["p" + pl], float)[sel]
        t = np.asarray(m["pt"], float)[sel]
        D = pay["dead"][pl]
        dch, t0, t1 = np.asarray(D["ch"]), np.asarray(D["t0"], float), np.asarray(D["t1"], float)
        hit = 0
        for c, tt in zip(ch, t):
            j = np.where(dch == int(round(c)))[0]
            if len(j) and np.any((t0[j] <= tt) & (tt <= t1[j])):
                hit += 1
        out[pl] = hit / len(ch) if len(ch) else 0.0
    return out


def rates(rows, scan_pos, chain_pos):
    tp = sum(1 for r in rows if scan_pos(r) and chain_pos(r))
    fp = sum(1 for r in rows if not scan_pos(r) and chain_pos(r))
    fn = sum(1 for r in rows if scan_pos(r) and not chain_pos(r))
    tn = sum(1 for r in rows if not scan_pos(r) and not chain_pos(r))
    pur = tp / (tp + fp) if tp + fp else float("nan")
    eff = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * pur * eff / (pur + eff) if pur + eff else float("nan")
    return dict(scored=len(rows), tp=tp, fp=fp, fn=fn, tn=tn, purity=pur, efficiency=eff, f1=f1)
