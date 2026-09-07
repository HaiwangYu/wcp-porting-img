#!/usr/bin/env python3
"""doc pr/147 -- cathode-crossing long-muon census, read-only over EXISTING arms.

FORKED FROM scripts/d84r2_census.py (doc 84 round 2 Pop-B census).  Why the
fork rather than a re-run: d84r2 answered "which pairs LOOK bridgeable", over
129 events, with an end-tangent that is not the one production uses.  pr/147
needs "which guard KILLS each pair", over the whole population, because the
class the owner reported (347890, 168448) dies ABOVE the geometry tests and is
therefore invisible both in d84r2's output and in the production logs -- only
1 event in 1435 emits a `long_muon_cathode_bridge: reject` line, since that
logging sits below the type guards.

So this script re-implements long_muon_cathode_bridge_pass
(clus/src/TaggerCheckNeutrino.cxx:1350) faithfully, including:

  * segment_cal_dir_3vector(seg, p, lever) as the CENTROID form
    (PRSegmentFunctions.cxx:2412 -- mean of every fit point within `lever` of
    the end, minus the end, normalised).  d84r2 used an arc-length walk to the
    first point beyond `lever`, which is a different vector; doc 84 R4.2's
    "probe-vs-production mismatch" is that difference.
  * the round-4 admission params (G1 lever, G2 track_partner, G3 short_gap)
  * the `gap > 0` hard precondition on the G3 waiver (407798 must stay refused)
  * the best-gap MINIMISER, so "which partner won" is reproduced, not just
    "which partners were eligible"

and then reports, per candidate pair, the FIRST guard that rejects it under
PRODUCTION settings -- while the enumeration itself runs with the type guards
relaxed, which is the only way to see the silent class.

Verdict vocabulary (production rules applied to an unrestricted enumeration):
    ok             would be admitted (and, if it wins the minimiser, bridges)
    receiver_type  receiver shower pdg != 13      <- 168448 dies here (:1404)
    partner_type   partner shower pdg not admitted <- 347890 dies here (:1431)
    min_len_recv / min_len_part   segment shorter than the hardcoded 5 cm
    same_side      far ends on the same drift side
    gap            3D gap >= cap
    angle_gap / angle_tan         the two collinearity tests

Usage:
  pr147_cathode_census.py --arms DIR:SAMPLE [...] --out OUTDIR [--tag AFTER]
Outputs OUTDIR/pr147-cathode-pairs.tsv and OUTDIR/summary.txt.
"""
import argparse, collections, glob, json, math, os, sys

# ---- SBND production operating point (wct-pr-perevt.jsonnet:2235-2247) ----
P = dict(x=0.0, xcut=6.0, gap=20.0, angle=25.0, lever=15.0,
         track_partner=True, short_gap=8.0, short_gap_angle=10.0,
         short_gap_len=50.0, min_len=5.0)

def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vmag(a): return math.sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])
def vneg(a): return (-a[0], -a[1], -a[2])
def pt(p): return (p["x"], p["y"], p["z"])

def cb_angle_deg(a, b):
    """clus/src/TaggerCheckNeutrino.cxx:1336 -- 181.0 for a degenerate vector."""
    ma, mb = vmag(a), vmag(b)
    if ma <= 0 or mb <= 0: return 181.0
    c = (a[0]*b[0] + a[1]*b[1] + a[2]*b[2]) / (ma*mb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))

def cal_dir_3vector(pts, p, lever):
    """PRSegmentFunctions.cxx:2412, the (seg, point, dis_cut) overload:
    centroid of every fit point within `lever` of p, minus p, normalised."""
    sx = sy = sz = 0.0; n = 0
    for q in pts:
        if vmag(vsub(q, p)) < lever:
            sx += q[0]; sy += q[1]; sz += q[2]; n += 1
    if n == 0: return (0.0, 0.0, 0.0)
    v = (sx/n - p[0], sy/n - p[1], sz/n - p[2])
    m = vmag(v)
    return (v[0]/m, v[1]/m, v[2]/m) if m > 0 else (0.0, 0.0, 0.0)

def seg_points(seg): return [pt(q) for q in (seg.get("points") or [])]

def track_likeness(seg, mip):
    """Columns the PID-independent predicate would use.  Zero-charge fit points
    are cells the fit could not attribute and they corrupt a median
    (feedback_zero_charge_points_corrupt_medians), so they are filtered."""
    dqdx = []; chi2 = []
    for q in seg.get("points") or []:
        dQ = q.get("dQ", 0.0); dx = q.get("dx", 0.0)
        if dQ > 0 and dx > 0: dqdx.append(dQ/dx)
        c = q.get("reduced_chi2")
        if c is not None and c == c: chi2.append(c)
    pts = seg_points(seg)
    med = sorted(dqdx)[len(dqdx)//2] if dqdx else -1.0
    mchi = sorted(chi2)[len(chi2)//2] if chi2 else -1.0
    L = seg.get("length", 0.0)
    straight = (vmag(vsub(pts[-1], pts[0])) / L) if (len(pts) >= 2 and L > 0) else -1.0
    frac0 = (1.0 - len(dqdx)/len(pts)) if pts else -1.0
    return (med/mip if med > 0 else -1.0), mchi, straight, frac0

def collect_ends(seg, sh, pts, cfg):
    """TaggerCheckNeutrino.cxx:1386.  Returns [(p, far_p, into)]."""
    out = []
    if len(pts) < 2: return out
    if seg.get("length", 0.0) < cfg["min_len"]: return out
    ends = (pts[0], pts[-1])
    for e in (0, 1):
        p = ends[e]
        if abs(p[0] - cfg["x"]) >= cfg["xcut"]: continue
        into = cal_dir_3vector(pts, p, cfg["lever"])
        if vmag(into) <= 0: continue
        out.append((p, ends[1-e], into))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True, metavar="DIR:SAMPLE")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--events", nargs="*", default=None,
                    help="restrict to these event ids (probe/validation runs)")
    for k in ("xcut", "gap", "angle", "lever", "min_len"):
        ap.add_argument("--"+k.replace("_", "-"), type=float, default=P[k])
    a = ap.parse_args()
    cfg = dict(P)
    for k in ("xcut", "gap", "angle", "lever", "min_len"):
        cfg[k] = getattr(a, k)
    os.makedirs(a.out, exist_ok=True)

    rows = []; nevt = 0; ncand_evt = set(); verd = collections.Counter()
    fires_evt = set(); split_rows = []
    for arm in a.arms:
        d, sample = arm.rsplit(":", 1)
        for f in sorted(glob.glob(os.path.join(d, "pr_evt*", "calib-pr-evt*.json"))):
            evt = os.path.basename(os.path.dirname(f))[len("pr_evt"):]
            if a.events and evt not in a.events: continue
            try: J = json.load(open(f))
            except Exception: continue
            nevt += 1
            # ---- split-muon signature (177536's class).  Recorded FIRST,
            # before any of the early `continue`s below: this table is a
            # per-EVENT census and must cover every event with a calib
            # dump, not only the ones that reach the pair stage.  Filled
            # after them it silently covered 84 of 1435.
            k = J.get("kine") or {}
            t = k.get("kine_particle_type") or []; e = k.get("kine_energy_particle") or []
            nmu = sum(1 for x in t if abs(x) == 13)
            emu = sum(ee for x, ee in zip(t, e) if abs(x) == 13)
            split_rows.append((sample, evt, nmu, "%.1f" % emu,
                               "%.1f" % k.get("kine_reco_add_energy", 0.0),
                               "%.1f" % k.get("kine_reco_Enu", 0.0)))
            mip = (J.get("meta") or {}).get("mip_dqdx_median", 43000.0)
            segs = J.get("segments") or []; shws = J.get("showers") or []
            sh_by_id = {s.get("id"): s for s in shws}
            ptcache = {s.get("id"): seg_points(s) for s in segs}

            # ---- receiver ends: production wants |13| showers AND |13| members.
            # We enumerate ALL showers/members and record why production refused.
            mu_ends = []
            for s in segs:
                sid = s.get("shower_id", -1)
                if sid == -1: continue                     # a receiver must own a shower
                osh = sh_by_id.get(sid)
                if osh is None: continue
                spdg = abs(s.get("particle_id", 0))
                shpdg = abs(osh.get("particle_id", 0))
                # NO pdg pre-filter here.  An earlier draft kept only receivers
                # that were track-typed on the segment or the shower, and that
                # silently dropped 168448 -- whose receiver is EM on BOTH after
                # the excl_t0_frame flip, which is the entire point of the
                # round.  production's own min_len + xcut are the filter; the
                # pdg is recorded as a column and adjudicated as a verdict.
                for p, farp, into in collect_ends(s, osh, ptcache[s.get("id")], cfg):
                    mu_ends.append(dict(sh=osh, seg=s, p=p, far=farp, into=into,
                                        shpdg=shpdg, segpdg=spdg))
            if not mu_ends: continue

            partner_ends = []
            for s in segs:
                sid = s.get("shower_id", -1)
                osh = sh_by_id.get(sid) if sid != -1 else None
                ppdg = abs(osh.get("particle_id", 0)) if osh else -1
                for p, farp, into in collect_ends(s, osh, ptcache[s.get("id")], cfg):
                    partner_ends.append(dict(sh=osh, seg=s, p=p, far=farp,
                                             into=into, shpdg=ppdg))
            if not partner_ends: continue
            ncand_evt.add((sample, evt))

            for me in mu_ends:
                for pe in partner_ends:
                    if pe["seg"].get("id") == me["seg"].get("id"): continue
                    if pe["sh"] is not None and pe["sh"] is me["sh"]: continue
                    gapv = vsub(pe["p"], me["p"]); gap = vmag(gapv)
                    cont = vneg(me["into"])
                    a_gap = cb_angle_deg(cont, gapv)
                    a_tan = cb_angle_deg(cont, pe["into"])
                    waive = (cfg["short_gap"] > 0 and gap > 0 and gap <= cfg["short_gap"]
                             and a_tan <= cfg["short_gap_angle"]
                             and pe["seg"].get("length", 0.0) >= cfg["short_gap_len"])
                    # first failing guard, in the pass's own order
                    if me["shpdg"] != 13:                      v = "receiver_type"
                    elif me["segpdg"] != 13:                   v = "receiver_seg_type"
                    elif pe["sh"] is not None and not (
                         pe["shpdg"] == 13 or (cfg["track_partner"] and pe["shpdg"] == 211)):
                                                               v = "partner_type"
                    elif (me["far"][0]-cfg["x"])*(pe["far"][0]-cfg["x"]) > 0:
                                                               v = "same_side"
                    elif gap >= cfg["gap"]:                    v = "gap"
                    elif (not waive) and a_gap > cfg["angle"]:  v = "angle_gap"
                    elif a_tan > cfg["angle"]:                 v = "angle_tan"
                    else:                                      v = "ok"
                    if v in ("same_side", "gap"): continue     # not a candidate at all
                    verd[v] += 1
                    ptl, pchi, pstr, pfr0 = track_likeness(pe["seg"], mip)
                    rtl, rchi, rstr, rfr0 = track_likeness(me["seg"], mip)
                    pk = "-".join(sorted([str(me["seg"].get("id")),
                                          str(pe["seg"].get("id"))]))
                    rows.append((sample, evt, v, pk,
                        me["sh"].get("shower_id"), me["shpdg"], me["segpdg"],
                        me["seg"].get("id"), "%.2f" % me["p"][0], "%.2f" % me["far"][0],
                        "%.1f" % me["seg"].get("length", 0.0),
                        "%.3f" % rtl, "%.2f" % rchi, "%.3f" % rstr,
                        "bare" if pe["sh"] is None else "shower",
                        pe["shpdg"], abs(pe["seg"].get("particle_id", 0)),
                        pe["seg"].get("id"), "%.2f" % pe["p"][0], "%.2f" % pe["far"][0],
                        "%.1f" % pe["seg"].get("length", 0.0),
                        "%.3f" % ptl, "%.2f" % pchi, "%.3f" % pstr, "%.3f" % pfr0,
                        "%.1f" % gap, "%.1f" % a_gap, "%.1f" % a_tan,
                        1 if waive else 0,
                        1 if pe["seg"].get("cluster_id") == me["seg"].get("cluster_id") else 0))

    hdr = ("sample evt verdict pair_key recv_shower_id recv_sh_pdg recv_seg_pdg recv_seg_id "
           "recv_end_x recv_far_x recv_len recv_dqdx_mip recv_chi2 recv_straight "
           "partner_kind partner_sh_pdg partner_seg_pdg partner_seg_id partner_end_x "
           "partner_far_x partner_len partner_dqdx_mip partner_chi2 partner_straight "
           "partner_zerofrac gap_cm a_gap_deg a_tan_deg waived same_clus").split()
    with open(os.path.join(a.out, "pr147-cathode-pairs.tsv"), "w") as fp:
        fp.write("\t".join(hdr) + "\n")
        for r in rows: fp.write("\t".join(str(x) for x in r) + "\n")
    with open(os.path.join(a.out, "pr147-muon-nodes.tsv"), "w") as fp:
        fp.write("sample\tevt\tn_mu_nodes\tE_mu\tadd_energy\tEnu\n")
        for r in split_rows: fp.write("\t".join(str(x) for x in r) + "\n")

    out = []
    out.append("arms: %s" % " ".join(a.arms))
    out.append("cfg : " + " ".join("%s=%s" % (k, cfg[k]) for k in sorted(cfg)))
    out.append("events with a calib dump      : %d" % nevt)
    out.append("events with >=1 candidate pair: %d" % len(ncand_evt))
    out.append("candidate pairs by verdict:")
    for v, n in verd.most_common():
        ev = len({(r[0], r[1]) for r in rows if r[2] == v})
        out.append("   %-18s %6d rows  %4d events" % (v, n, ev))
    txt = "\n".join(out)
    open(os.path.join(a.out, "summary.txt"), "w").write(txt + "\n")
    print(txt)
    return 0

if __name__ == "__main__": sys.exit(main())
