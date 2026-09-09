#!/usr/bin/env python3
"""doc pdhd/12 -- build the STM + Michel hand-scan sheet, key and payloads.

READ-ONLY apart from what it writes under --outdir and --sheetdir.

For every CheckSTM_Michel candidate in an arm it writes one compact JSON sidecar
carrying exactly what the display draws, plus two TSVs:

  <sheetdir>/<det>_stm_michel_scan_sheet.tsv   the item list, NO verdict
  <sheetdir>/<det>_stm_michel_scan_key.tsv     the answer key, closed until scoring

WHAT IS DELIBERATELY SPLIT OUT OF THE PAYLOAD'S TOP LEVEL
  Everything the chain decided lives under the single key "verdict" and nowhere
  else: roles 2/3/4 (delta / Michel / dot), is_stm, reject_bits, michel_*, n_dots,
  contrast, plateau_med, tail_med, in_fv, bragg_valid, entry/stop/tagger_stop, and
  the tagger's own STM fit.  The viewer reads that key ONLY when REVEAL is on and
  records `revealed_before_label` with the label.  Colouring the main view by
  `role` would hand the scanner `michel_found` in pixels and make the agreement
  number circular (feedback_blind_the_scan_sheet).

WHAT IS ALWAYS IN THE PAYLOAD, AND WHY
  The other half of that rule (feedback_scan_display_must_show_the_evidence):
  a display that draws only a reconstruction PRODUCT withholds the measurement
  the verdict is about.  So the evidence is unconditional --

    muon        the role-1 chain: x,y,z (cm), q = dQ/dx in e/cm ALREADY
                (CheckSTM_Michel.cxx:673), L and rr in cm, and pw joined from
                T_rec_charge so the stop can be labelled by readout unit.
    image_near  every mabc-pr.zip `clustering-global` point within IMAGE_NEAR_R
                of any role-1 point, FULL density.  Purely geometric over all the
                charge in the event -- never "the points the chain assigned to
                this cluster", which would draw the clustering decision.
    image_far   the rest of the event, thinned to IMAGE_FAR_MAX, for containment.

  Only `clustering-global` is opened.  The same archive carries `shower_track`
  (the chain paints Michel/dot segments there via pdg 11), `stm_tagged` and
  `stm_fit`; those are the answer and are not read here at all.

dQ/dx REFERENCE
  From calib-pr-evt*.json's `dqdx_ref` block (401 points, rr 0..100 cm, step
  0.25, e/cm, source ParticleDataSet).  Verified identical across events within
  a detector, so it is written once per detector as dqdx_ref_<det>.json rather
  than 181 times.  NOTE: meta.mip_dqdx_median in that dump is the C++ default
  43000, not the 48000/47000 the taggers run with -- so nothing here normalises
  by it (feedback_dump_meta_is_not_the_config).  The panel plots absolute e/cm
  against the absolute reference and needs no mip at all.

Repro:
  ./prep_stm_michel_scan.py --det pdhd
  ./prep_stm_michel_scan.py --det pdvd

  While a hand scan is in progress, pin the tranche-1 draw to the sheet that
  scan started from, so a re-prep on a new arm cannot re-draw the sample under
  the scanner (doc pdhd/15 sec 10, read_pinned_tranche):

  ./prep_stm_michel_scan.py --det pdvd \
      --pin-tranche 86d78116:pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
"""
import argparse, csv, glob, json, os, random, subprocess, sys, zipfile

import numpy as np
import uproot
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smgeom                                                     # noqa: E402

PDHD = os.path.dirname(HERE)
IMG = os.path.dirname(PDHD)

DET = {
    # doc pdhd/14: the d51*nu arms predate CheckSTM_Michel's muon-kinematics
    # branches, so the display had no muon energy to show.  d14*nu is the SAME
    # pctree input re-run through the same -nu chain with the feature in; every
    # pre-existing T_stm_michel branch is bit-unchanged (doc pdhd/14 sec 3), so
    # the sheet and the stratification are unaffected.
    # doc pdhd/16: d16*nu is the same pctree input again, with the MCS momentum
    # added and check_stm_michel's dQ/dx -> dE/dx inverse carrying the measured
    # normalization.  The verdict branches do not move (the recombination model
    # is not on any verdict path) -- measured 83/88 branches bit-identical, the
    # five movers being the dQ/dx energies -- so the sheet, the stratification
    # and the tranche are unaffected.  Re-prep with --pin-tranche all the same.
    # doc pdvd/51: the arm carrying the capture-gamma branches and the role
    # 4 -> 3 Michel migration.  --arm overrides it for a scratch validation run
    # so a new arm can be diffed against the promoted payloads before it lands.
    "pdhd": dict(root=os.path.join(IMG, "pdhd"), arm="d51gh"),
    "pdvd": dict(root=os.path.join(IMG, "pdvd"), arm="d51gv"),
}
IMAGE_MEMBER = "clustering-global"
IMAGE_NEAR_R = 20.0       # cm, full density inside this of the muon chain
IMAGE_STOP_R = 40.0       # cm, full density inside this of the chain's rr=0 END.
#   Without it a Michel that runs 20 cm off the stop leaves the near set and is
#   thinned 1-in-N -- i.e. the display would hide the object being judged.  The
#   ball is centred on the muon polyline's own last point, so it carries no
#   chain verdict: it is the same geometric rule as the 40 cm dense context in
#   pdhd/stm_scan (feedback_fragment_label_carries_object_verdict).
IMAGE_FAR_MAX = 8000      # thin the rest of the event to at most this many
MIN_PROFILE_PTS = 20
MIN_MUON_LEN = 10.0       # cm
SEED = 20260907           # fixed: tranche 1 is random, not "the interesting ones"
TRANCHE1 = 60             # items per detector served first
T1_S1_CAP = 24            # at most this many from the reco-positive stratum
T1_FLOOR = 8              # per-stratum floor for S2/S3/S4

# The key's header.  It states what the blind on THIS FILE actually is, because
# doc pdhd/12 sec 6 argues that structural beats request and the file itself is
# the one place where the blind is a request.
KEY_HEADER = (
    "# doc pdhd/12 -- ANSWER KEY for the %s STM + Michel scan.\n"
    "# Committed on purpose: it is the record of the sample at arm %s /\n"
    "# HEAD c0b1613b, and a scan whose key lives only beside a work/ arm stops\n"
    "# being scorable the day that arm is retired.\n"
    "# THE BLIND ON THIS FILE IS AN HONOUR RULE, NOT A STRUCTURAL ONE, and doc\n"
    "# pdhd/12 sec 6 says so.  What IS structural is the display: the viewer\n"
    "# never opens this file, and the chain's answer reaches no data source\n"
    "# unless REVEAL is on -- proved by poisoning it.  Do not open this while\n"
    "# scanning, and that goes for an assistant reading it on your behalf.\n")

# clus/inc/WireCellClus/StmMichelFunctions.h:169-183
BITS = ["no_chain", "stop_unmatched", "no_bragg", "shape_flat", "not_muon_pid",
        "continuation", "stop_near_boundary", "vertex_hadron", "short",
        "profile_sparse", "plateau_off_mip", "stop_into_dead", "cluster_not_track"]

# T_stm_michel scalars carried into the reveal block, verbatim.
VERDICT_SCALARS = [
    "is_stm", "in_fv", "bragg_valid", "reject_bits", "has_pass", "pass",
    "kink_num", "n_profile_pts", "n_live_pts", "n_dead_pts", "muon_len",
    "michel_found", "michel_conn_type", "n_michel_segs", "michel_len",
    "michel_mip", "michel_kink_deg", "michel_far_len",
    "michel_ke_dqdx", "michel_ke_range", "michel_ke_best",
    # doc pdhd/14 -- written by CheckSTM_Michel, not recomputed here.  Absent
    # on any arm older than doc 14; the dict comprehension below skips missing
    # keys, and the viewer renders the gap rather than inventing a number.
    "muon_ke_range", "muon_ke_dqdx", "muon_ke_best", "michel_seg_id",
    "stop_vtx_id", "n_chain_segs",
    # doc pdhd/15 -- the Michel as ONE object.  michel_ke_dqdx is now the whole
    # object (core + every piece); michel_ke_core is the core alone, i.e. what
    # michel_ke_dqdx meant through doc pdhd/14.  Also absent on an older arm.
    "michel_ke_core", "michel_ke_charge", "michel_n_pieces",
    "michel_parent_vtx_id", "michel_dis_cm",
    "michel_start_x", "michel_start_y", "michel_start_z",
    "n_dots", "dots_ke_dqdx", "n_dot_clusters_unfit", "dots_charge_unfit",
    "dots_ke_unfit",
    # doc pdvd/51 -- the muon-capture gamma at the stop, a SEPARATE object class
    # from the Michel (never folded into michel_ke_*), and michel_n_clusters,
    # which is how many clusters the Michel object spans.  Absent on any arm
    # older than doc 51.
    "michel_n_clusters", "n_stop_gammas", "stop_gamma_n_unfit",
    "stop_gamma_seg_id", "stop_gamma_ke_tot", "stop_gamma_ke_max",
    "stop_gamma_charge", "stop_gamma_dis_min", "stop_gamma_dis_max",
    # doc pdhd/16 -- the muon's third energy scale and the three momenta.  MCS
    # reads no charge at all, so it is the one estimator blind to gain,
    # lifetime and recombination.  -1 means "not computed" (bad_path, < 20
    # trimmed points, trimmed end < 28 cm from the stop, or < 2 fitted 14 cm
    # segments) and the viewer must render that as a gap, never as 0 MeV.
    "muon_ke_mcs", "muon_mcs_amb", "muon_mcs_tracklen", "muon_mcs_range_ke",
    "muon_mcs_nsegs", "muon_mcs_bad_path",
    "muon_p_range", "muon_p_dqdx", "muon_p_mcs",
    "n_delta", "delta_len", "n_body_hadron", "n_stop_arms",
    "cont_len", "cont_angle_deg", "cont_mip", "n_ext", "ext_len", "dead_ahead",
    "contrast", "contrast_expected", "plateau_med", "tail_med",
    "n_tail", "n_plateau", "short_track", "ks_mu", "ks_flat",
    "stop_dis", "t0_us", "gid", "chain_coverage", "n_cluster_pts",
]
VERDICT_POINTS = ["entry_x", "entry_y", "entry_z", "stop_x", "stop_y", "stop_z",
                  "tagger_stop_x", "tagger_stop_y", "tagger_stop_z"]


def bit_names(bits):
    b = int(bits)
    return [n for i, n in enumerate(BITS) if b & (1 << i)] or (["STM"] if b == 0 else [])


def r1(v):
    return [round(float(t), 1) for t in v]


def r2(v):
    return [round(float(t), 2) for t in v]


def ri(v):
    return [int(t) for t in v]


def wire_join(rc_tree, rc, P):
    """(pu, pv, pw, pt) of the T_rec_charge point at each row of P.

    Every CheckSTM_Michel chain point IS a T_rec_charge point of the same file:
    measured 8962/8962 role-1, 142/142 role-2, 73/73 role-3 and 2/2 role-4
    matches within 0.05 cm on PDHD, and 7736/7736, 82/82, 42/42, 22/22 on PDVD
    (doc pdhd/12 sec 5.4b).  So this is an index lookup dressed as a query, and
    the 0.05 cm cut is a tripwire rather than a tolerance -- a point that misses
    gets None and is simply not drawn in the measurement panel.
    """
    n = 0 if P is None else P.shape[0]
    out = [np.full(n, np.nan) for _ in range(4)]
    if n and rc_tree is not None:
        d, j = rc_tree.query(P, k=1)
        g = d < 0.05
        for a, key in zip(out, ("pu", "pv", "pw", "pt")):
            a[g] = rc[key][j[g]]
    return [[None if not np.isfinite(t) else round(float(t), 2) for t in a]
            for a in out]


def particle_flow(rc, cid, sc, off, extra_segs=()):
    """The PR particle flow of one cluster, from T_rec_charge.

    CheckSTM_Michel runs the full PR chain -- find_proto_vertex ->
    clustering_points -> separate_track_shower -- and the visitor persists all
    of it per point (PdvdPrMagnifyTrackingVisitor.cxx:855-915):

        sub_cluster_id  = cluster_id * 1000 + segment graph index   (== real_cluster_id,
                          the same buffer)                          -- the SEGMENT id
        flag_vertex     = 1 on a graph vertex row (segment id -1, rr -1)
        flag_shower     = kShowerTrajectory | kShowerTopology       -- track vs shower
        particle_id     = the segment's pdg, or 4 for a track and 1 for a shower
                          with no particle hypothesis, or -1 on a vertex row

    Returns (topology, types).  The topology -- which segments exist, where they
    run, where the junctions are -- is NEUTRAL and always drawn.  `flag_shower`
    and `particle_id` are the chain's ANSWER (CheckSTM_Michel.cxx:1184 sets the
    Michel arm's type to 11) and go into the verdict block behind REVEAL, for
    the same reason `role` does.

    doc pdvd/51 CORRECTS the limit this docstring used to state.  The two ids
    ARE the same encoding -- `cluster_id * 1000 + segment graph index` on both
    sides (CheckSTM_Michel.cxx:762-763 against
    PdvdPrMagnifyTrackingVisitor.cxx:905) -- and they join exactly: all 1107
    distinct T_stm_michel_pts.seg_id values over the 119-event d16vnu arm are
    present in T_rec_charge.sub_cluster_id.  What is true is the weaker
    statement that the PARTITIONS differ (one segment can carry points of more
    than one role), so a per-POINT join is still not well posed.  The per-SEGMENT
    join is, and `extra_segs` below is exactly that join.
    """
    # THE SELECTOR IS sub_cluster_id // 1000, NOT cluster_id.  T_rec_charge's
    # `cluster_id` branch is bound to reco_mother_cluster_id
    # (PdvdPrMagnifyTrackingVisitor.cxx:737, 857) -- the id of the GROUP, chosen
    # once per fill and shared by every cluster in it.  On PDHD 028084_0 it
    # selects ZERO rows for two of the five STM candidates (their mothers are 34
    # and 116, their own ids 35 and 117) and the OTHER clusters' segments for the
    # rest.  `sub_cluster_id` is cluster_id * 1000 + segment graph index (:905),
    # so its top part is the segment's OWN cluster.
    empty = dict(seg=[], vtx=dict(x=[], y=[], z=[], pu=[], pv=[], pw=[], pt=[]))
    # doc pdvd/51.  `sub_cluster_id // 1000 == cid` alone shows the MUON and
    # nothing else whenever the chain's object lives in a companion cluster --
    # a BRIDGED Michel (039252_15 cluster 77's is segments 265003/265004, pdg 11
    # in T_rec_charge, rendered in mc.json, and invisible in this panel) or a
    # capture gamma, which is ALWAYS in a companion cluster by construction.
    # `extra_segs` are the segment ids the chain itself names in
    # T_stm_michel_pts, so the panel shows the object the rest of the page shows.
    b = (rc["flag_vertex"] == 0) & (((rc["sub_cluster_id"] // 1000) == cid)
                                    | np.isin(rc["sub_cluster_id"], list(extra_segs or ())))
    if not b.sum():
        return empty, {}
    # A vertex row carries sub_cluster_id = -1 and only the mother's cluster_id,
    # so it cannot be selected by id at all.  It sits ON a segment endpoint of
    # its own graph, so keep the vertex rows that land within 1 cm of one of
    # THIS cluster's segment points.
    SEG = np.c_[rc["x"][b], rc["y"][b], rc["z"][b]]
    vall = rc["flag_vertex"] == 1
    v = np.zeros(len(rc["x"]), bool)
    if vall.sum() and SEG.size:
        d, _ = cKDTree(SEG).query(
            np.c_[rc["x"][vall], rc["y"][vall], rc["z"][vall]], k=1)
        v[np.flatnonzero(vall)[d < 1.0]] = True
    out = dict(seg=[], vtx=dict(
        x=r2(rc["x"][v]), y=r2(rc["y"][v]), z=r2(rc["z"][v]),
        pu=r2(rc["pu"][v]), pv=r2(rc["pv"][v]), pw=r2(rc["pw"][v]),
        pt=r2(rc["pt"][v])))
    types = {}
    with np.errstate(divide="ignore", invalid="ignore"):
        dq = np.where(rc["nq"] > 0, (rc["q"] - off) / sc / rc["nq"], np.nan)
    for sid in sorted({int(t) for t in rc["sub_cluster_id"][b]}):
        j = b & (rc["sub_cluster_id"] == sid)
        n = int(j.sum())
        if not n:
            continue
        X, Y, Z = rc["x"][j], rc["y"][j], rc["z"][j]
        L = float(np.sum(np.sqrt(np.diff(X) ** 2 + np.diff(Y) ** 2 + np.diff(Z) ** 2)))
        # rr carries a -1 SENTINEL at any vertex of degree > 1
        # (PdvdPrMagnifyTrackingVisitor.cxx:947-955), not a residual range.
        rr = rc["rr"][j]
        d = dq[j]
        live = np.isfinite(d) & (d > 0)
        out["seg"].append(dict(
            id=sid, npts=n, len_cm=round(L, 2),
            x=r2(X), y=r2(Y), z=r2(Z),
            pu=r2(rc["pu"][j]), pv=r2(rc["pv"][j]), pw=r2(rc["pw"][j]),
            pt=r2(rc["pt"][j]),
            dqdx=r1(np.nan_to_num(d, nan=-1.0, posinf=-1.0, neginf=-1.0)),
            rr=r2(rr),
            dqdx_med=round(float(np.median(d[live])), 1) if live.any() else None,
            n_rr_sentinel=int((rr < 0).sum())))
        pid = rc["particle_id"][j]
        sh = rc["flag_shower"][j]
        types[str(sid)] = dict(
            pdg=int(np.bincount(np.abs(pid)).argmax()) if n else 0,
            shower=int(round(float(sh.mean()))),
            frac_shower=round(float(sh.mean()), 3))
    return out, types


def proj_cells(pj, cid, det):
    """The cluster's 2-D measurement, split by plane.

    This is exactly what a Magnify tracking display shows: for every (channel,
    time slice) cell the fitter touched, the MEASURED charge, its error, and the
    charge the fitted track PREDICTS there.  Written by
    PdvdPrMagnifyTrackingVisitor::write_proj_data as one row per fitted cluster.

    LIMIT, and it is why the dead-channel overlay is not decoration: inside a
    dead region `charge` is not a measurement at all -- Cell::charge() returns
    prepare_data's FILLER when the slice has no live entry
    (PdvdPrMagnifyTrackingVisitor.cxx:526-531), and the tree does not carry the
    per-cell live/dead flag.  So meas - pred there is model minus model.
    """
    out = {k: dict(ch=[], ts=[], q=[], qp=[], qe=[]) for k in "uvw"}
    if pj is None:
        return out
    j = pj["idx"].get(int(cid))
    if j is None:
        return out
    ch = np.asarray(pj["channel"][j], np.int64)
    ts = np.asarray(pj["time_slice"][j], np.int64)
    q = np.asarray(pj["charge"][j], np.int64)
    qe = np.asarray(pj["charge_err"][j], np.int64)
    qp = np.asarray(pj["charge_pred"][j], np.int64)
    # vectorised form of smgeom.plane_from_chan; the self-test asserts the two
    # give the same answer on every cell of a sample of items.
    b, nch = smgeom.BASE[det], smgeom.NCH[det]
    pln = np.where(ch < b[1], 0, np.where(ch < b[2], 1, 2))
    pln[(ch < 0) | (ch >= b[2] + nch[2])] = -1
    for pl, nm in enumerate("uvw"):
        k = pln == pl
        out[nm] = dict(ch=ri(ch[k]), ts=ri(ts[k]), q=ri(q[k]),
                       qp=ri(qp[k]), qe=ri(qe[k]))
    return out


def dead_bands(bc, det):
    """T_bad_ch as [channel, first slice, last slice] per plane.

    The tick -> slice conversion and the causal gate on it: smgeom.TICKS_PER_SLICE.
    Kept whole rather than clipped to the cluster's window, so a gap that runs
    off the edge of the drawn box is still explained.
    """
    out = {k: dict(ch=[], t0=[], t1=[]) for k in "uvw"}
    if bc is None or not len(bc["chid"]):
        return out
    for pl, nm in enumerate("uvw"):
        k = bc["plane"] == pl
        out[nm] = dict(
            ch=ri(bc["chid"][k]),
            t0=[round(smgeom.ticks_to_slice(det, int(t)), 2) for t in bc["start_time"][k]],
            t1=[round(smgeom.ticks_to_slice(det, int(t)), 2) for t in bc["end_time"][k]])
    return out


def event_dirs(det):
    d = DET[det]
    out = []
    for p in sorted(glob.glob(os.path.join(d["root"], "work", "*_" + d["arm"]))):
        if os.path.exists(os.path.join(p, "tracking-pr.root")):
            out.append(p)
    return out


def bundle_ids(f, cid):
    """Cluster ids sharing this cluster's matched Q-L bundle, the muon included.

    doc pdhd/13 sec 4.  The Bee `clustering-global` layer places EVERY cluster
    at its OWN bundle's t0-corrected position, so two cosmics separated by
    thousands of us of drift time can land centimetres apart on screen -- on
    039252_15 that drew a 434 cm through-goer (cluster 103, flash 134, t0
    2542.4 us) 5.6 cm from a 107 cm stopping muon (cluster 77, flash 298, t0
    6199.7 us), 541 cm apart in drift.  It reads as over-clustering and is not.

    The bundle key is (flash_id, cluster_t0_us) and BOTH are required: a flash
    alone is not a unique bundle key.  Returns None when T_cluster is absent or
    the cluster is not in it, which the viewer treats as "cannot restrict".
    """
    try:
        tc = f["T_cluster"].arrays(
            ["cluster_id", "flash_id", "cluster_t0_us"], library="np")
    except Exception:
        return None
    w = np.where(tc["cluster_id"] == cid)[0]
    if not len(w):
        return None
    i = int(w[0])
    same = ((tc["flash_id"] == tc["flash_id"][i])
            & (np.abs(tc["cluster_t0_us"] - tc["cluster_t0_us"][i]) <= 1e-6))
    return sorted(int(c) for c in tc["cluster_id"][same])


def load_image(evtdir, muon_xyz, stop_xyz=None, bundle=None):
    """(near, far, members_read).  Geometric split only, over ALL the charge.

    When `bundle` is a set of cluster ids, each returned point also carries `b`
    = 1 when its cluster is in the muon's Q-L bundle.  The split stays purely
    geometric -- `b` only lets the viewer HIDE what is not in the bundle, so
    turning the filter off restores exactly the old picture.
    """
    zp = os.path.join(evtdir, "mabc-pr.zip")
    empty = dict(x=[], y=[], z=[], q=[], b=[])
    if not os.path.exists(zp) or not len(muon_xyz):
        return empty, dict(x=[], y=[], z=[], b=[]), []
    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.endswith(IMAGE_MEMBER + ".json")]
        if not names:
            return empty, dict(x=[], y=[], z=[]), []
        read = [names[0]]
        g = json.loads(z.read(names[0]))
    X = np.asarray(g.get("x") or [], float)
    if X.size == 0:
        return empty, dict(x=[], y=[], z=[], b=[]), read
    Y = np.asarray(g["y"], float); Z = np.asarray(g["z"], float)
    Q = np.asarray(g.get("q") or [0.0] * X.size, float)
    # nearest muon-chain point for every image point, once.  cKDTree is an
    # accelerator here, not a requirement -- selftest reimplements this by brute
    # force on a sample and demands the same index set.
    P = np.c_[X, Y, Z]
    d, _ = cKDTree(muon_xyz).query(P, k=1, distance_upper_bound=IMAGE_NEAR_R)
    m = np.isfinite(d)
    if stop_xyz is not None:
        s2 = ((P - np.asarray(stop_xyz, float)) ** 2).sum(axis=1)
        m |= s2 < IMAGE_STOP_R ** 2
    # in-bundle flag, per point.  Absent cluster_id or absent bundle => every
    # point counts as in-bundle, so the filter can only ever remove charge it
    # can positively attribute elsewhere.
    CIDS = np.asarray(g.get("cluster_id") or [], float)
    if bundle is None or CIDS.size != X.size:
        B = np.ones(X.size, bool)
    else:
        B = np.isin(CIDS.astype(np.int64), np.asarray(sorted(bundle), np.int64))
    near = dict(x=r1(X[m]), y=r1(Y[m]), z=r1(Z[m]), q=r1(Q[m]),
                b=[int(v) for v in B[m]])
    fx, fy, fz, fb = X[~m], Y[~m], Z[~m], B[~m]
    st = max(1, -(-fx.size // IMAGE_FAR_MAX))
    far = dict(x=r1(fx[::st]), y=r1(fy[::st]), z=r1(fz[::st]),
               b=[int(v) for v in fb[::st]])
    return near, far, read


def build_event(det, evtdir, with_tagger_fit=True):
    """[(row dict, payload dict)] for every candidate in one event."""
    f = uproot.open(os.path.join(evtdir, "tracking-pr.root"))
    keys = {k.split(";")[0] for k in f.keys()}
    if "T_stm_michel" not in keys:
        return []
    m = f["T_stm_michel"].arrays(library="np")
    p = f["T_stm_michel_pts"].arrays(library="np")
    rc = f["T_rec_charge"].arrays(
        ["x", "y", "z", "q", "nq", "rr", "pu", "pv", "pw", "pt", "cluster_id",
         "sub_cluster_id", "particle_id", "flag_vertex", "flag_shower"],
        library="np")
    # dQ/dx unwind, the SAME one used for the tagger fit below: the tree stores
    # dQ * scale + offset and dx separately (Trun of this very file).
    _tr = f["Trun"].arrays(["dQdx_scale", "dQdx_offset"], library="np")
    pf_sc, pf_off = float(_tr["dQdx_scale"][0]), float(_tr["dQdx_offset"][0])
    # the 2-D measurement, once per event.  T_proj_data is ONE entry holding
    # vector-of-vector branches keyed by cluster_id, so unwrap the entry first.
    pj = None
    if "T_proj_data" in keys:
        d0 = f["T_proj_data"].arrays(library="np")
        if len(d0["cluster_id"]):
            pj = {k: d0[k][0] for k in d0}
            pj["idx"] = {int(c): i for i, c in enumerate(pj["cluster_id"])}
    bc = f["T_bad_ch"].arrays(library="np") if "T_bad_ch" in keys else None
    run = f["Trun"].arrays(["runNo", "eventNo"], library="np")
    runno, evtno = int(run["runNo"][0]), int(run["eventNo"][0])
    ev = os.path.basename(evtdir).rsplit("_", 1)[0]          # <run6>_<evt>

    # pw for every fit point of the whole event, once.  The role-1 points ARE
    # T_rec_charge points -- measured NN distance 0.00000 cm and cluster_id
    # agreement 1.0000 on both detectors (doc pdhd/12 sec 4.2) -- so this join
    # is an index lookup dressed as a query, not an approximation.
    RC = np.c_[rc["x"], rc["y"], rc["z"]]
    rc_tree = cKDTree(RC) if RC.size else None

    tagfit = {}
    if with_tagger_fit:
        sp = os.path.join(evtdir, "tracking-stm.root")
        if os.path.exists(sp):
            try:
                g = uproot.open(sp)
                t = g["T_rec_charge"].arrays(
                    ["x", "y", "z", "q", "nq", "rr", "cluster_id", "pass", "status"],
                    library="np")
                tr = g["Trun"].arrays(["dQdx_scale", "dQdx_offset"], library="np")
                sc, off = float(tr["dQdx_scale"][0]), float(tr["dQdx_offset"][0])
                ok = t["status"] == 0
                with np.errstate(divide="ignore", invalid="ignore"):
                    dq = np.where(t["nq"] > 0, (t["q"] - off) / sc / t["nq"], np.nan)
                for cid in np.unique(t["cluster_id"][ok]):
                    for ps in np.unique(t["pass"][ok & (t["cluster_id"] == cid)]):
                        k = ok & (t["cluster_id"] == cid) & (t["pass"] == ps)
                        tagfit.setdefault(int(cid), []).append(dict(
                            pass_=int(ps), x=r2(t["x"][k]), y=r2(t["y"][k]),
                            z=r2(t["z"][k]), rr=r2(t["rr"][k]),
                            dqdx=r1(np.nan_to_num(dq[k], nan=-1.0))))
            except Exception as ex:                       # a short/absent file
                print("#  no tagger fit for %s: %s" % (ev, ex), file=sys.stderr)

    out = []
    for i, cid in enumerate(m["cluster_id"]):
        cid = int(cid)
        if not int(m["has_pass"][i]):
            continue
        if int(m["n_profile_pts"][i]) < MIN_PROFILE_PTS:
            continue
        if float(m["muon_len"][i]) < MIN_MUON_LEN:
            continue
        sel = p["cluster_id"] == cid
        mu = sel & (p["role"] == 1)
        if not mu.sum():
            continue
        MX = np.c_[p["x"][mu], p["y"][mu], p["z"][mu]]
        m_pu, m_pv, m_pw, m_pt = wire_join(rc_tree, rc, MX)
        pw = np.asarray([np.nan if t is None else t for t in m_pw], float)
        rr_mu = p["rr"][mu]
        stop_pt = MX[int(np.argmin(rr_mu))] if rr_mu.size else None
        bundle = bundle_ids(f, cid)
        near, far, src = load_image(evtdir, MX, stop_pt, bundle)

        # the readout unit of every chain point, from the wire coordinate
        units = [smgeom.unit_from_wire(det, None if not np.isfinite(w) else w)[0]
                 for w in pw]
        crus = [smgeom.unit_from_wire(det, None if not np.isfinite(w) else w)[1]
                for w in pw]

        pay = dict(
            det=det, arm=DET[det]["arm"], event=ev, run=runno, evtno=evtno,
            cluster_id=cid, npts=int(mu.sum()),
            muon_len_cm=round(float(m["muon_len"][i]), 2),
            image_src=src, image_near_r=IMAGE_NEAR_R, image_stop_r=IMAGE_STOP_R,
            muon=dict(x=r2(p["x"][mu]), y=r2(p["y"][mu]), z=r2(p["z"][mu]),
                      q=r1(p["q"][mu]), L=r2(p["L"][mu]), rr=r2(p["rr"][mu]),
                      pw=m_pw, pu=m_pu, pv=m_pv, pt=m_pt,
                      unit=units, cru=crus),
            image_near=near, image_far=far,
            # the muon's matched Q-L bundle (doc pdhd/13 sec 4); None when
            # T_cluster cannot supply it, which disables the viewer's filter
            bundle=bundle,
            # the 2-D measurement space, per plane: what the wires SAW, what the
            # fit PREDICTS they should have seen, and which channels were dead
            ticks_per_slice=smgeom.TICKS_PER_SLICE[det],
            proj=proj_cells(pj, cid, det), dead=dead_bands(bc, det),
        )
        # doc pdvd/51: hand the PF selector the chain's own member segments
        # (roles 3 michel / 4 dot / 5 capture gamma), so a bridged Michel and a
        # capture gamma appear in the flow panel and not only in the 3-D view.
        extra = sorted({int(t) for t in p["seg_id"][sel & np.isin(p["role"], (3, 4, 5))]})
        pf, pf_types = particle_flow(rc, cid, pf_sc, pf_off, extra_segs=extra)
        pf["chain_segs"] = extra
        pay["pf"] = pf
        v = {k: (float(m[k][i]) if m[k].dtype.kind == "f" else int(m[k][i]))
             for k in VERDICT_SCALARS if k in m}
        v["reject_names"] = bit_names(m["reject_bits"][i])
        for k in VERDICT_POINTS:
            if k in m:
                v[k] = round(float(m[k][i]), 2)
        # doc pdvd/51: role 3 now means "a member of the Michel OBJECT" for
        # every connection type -- through doc pdhd/17 a BRIDGED Michel's pieces
        # carried role 4, so the display drew them in the `dots` red and called
        # them dots, which is what the owner saw on 039252_15 cluster 77.
        # Role 5 is the new capture-gamma class and gets its own colour.
        for role, name in ((2, "delta"), (3, "michel"), (4, "dots"), (5, "gamma")):
            k = sel & (p["role"] == role)
            RX = np.c_[p["x"][k], p["y"][k], p["z"][k]] if k.sum() else None
            r_pu, r_pv, r_pw, r_pt = wire_join(rc_tree, rc, RX)
            v[name] = dict(x=r2(p["x"][k]), y=r2(p["y"][k]), z=r2(p["z"][k]),
                           q=r1(p["q"][k]), seg=[int(s) for s in p["seg_id"][k]],
                           pu=r_pu, pv=r_pv, pw=r_pw, pt=r_pt)
        v["tagger_fit"] = tagfit.get(cid, [])
        v["pf_type"] = pf_types          # pdg + track/shower per PF segment
        pay["verdict"] = v

        row = dict(event=ev, cluster=cid, npts=pay["npts"],
                   muon_len_cm=pay["muon_len_cm"],
                   n_near=len(near["x"]), n_far=len(far["x"]),
                   n_near_bundle=int(sum(near.get("b") or [])),
                   n_bundle_clusters=(0 if bundle is None else len(bundle)))
        key = dict(row, is_stm=int(m["is_stm"][i]),
                   michel_found=int(m["michel_found"][i]),
                   michel_conn_type=int(m["michel_conn_type"][i]),
                   michel_len=round(float(m["michel_len"][i]), 2),
                   michel_ke_best=round(float(m["michel_ke_best"][i]), 2),
                   michel_kink_deg=round(float(m["michel_kink_deg"][i]), 1),
                   n_dots=int(m["n_dots"][i]), in_fv=int(m["in_fv"][i]),
                   reject_bits=int(m["reject_bits"][i]),
                   reject_names="|".join(v["reject_names"]))
        out.append((row, key, pay))
    return out


def stratum(k):
    if k["is_stm"] and k["michel_found"]:
        return "S1"
    if k["is_stm"]:
        return "S2"
    if k["michel_found"]:
        return "S3"
    return "S4"


def tranche(keys):
    """Fixed-seed tranche-1 membership.  Returns {(event, cluster): 1 or 2}."""
    by = {}
    for k in keys:
        by.setdefault(stratum(k), []).append((k["event"], k["cluster"]))
    rnd = random.Random(SEED)
    for s in by:
        by[s].sort()
        rnd.shuffle(by[s])
    picked = list(by.get("S1", [])[:T1_S1_CAP])
    rest = [s for s in ("S2", "S3", "S4") if by.get(s)]
    for s in rest:                                     # floor first
        picked += by[s][:T1_FLOOR]
    cur = {s: T1_FLOOR for s in rest}
    while len(picked) < TRANCHE1 and any(cur[s] < len(by[s]) for s in rest):
        for s in rest:
            if len(picked) >= TRANCHE1:
                break
            if cur[s] < len(by[s]):
                picked.append(by[s][cur[s]]); cur[s] += 1
    return {p: 1 for p in picked}


def read_pinned_tranche(spec):
    """Tranche membership inherited from a previous sheet, keyed (event, cluster).

    doc pdhd/15 sec 10.  `tranche()` draws its sample per `stratum()`, which is
    a function of `is_stm` and `michel_found` -- and doc pdhd/15 REDEFINED
    michel_found ("a Michel object exists", detached included).  So a re-prep on
    a new arm silently RE-DRAWS the sample under a scan already in progress: 41
    of 60 pdvd and 32 of 60 pdhd tranche-1 items changed between the d14 and d15
    sheets.  A hand-scan sample must not depend on the quantity being measured,
    so a scan that is under way pins its draw to the sheet it started from.

    `spec` is a path, or `<rev>:<repo-relative-path>` resolved with `git show`
    so a retired sheet stays usable as a pin.  Keys ABSENT from the pinned sheet
    get tranche 2: a pinned sample never grows retroactively.
    """
    if os.path.exists(spec):
        text = open(spec).read()
    elif ":" in spec:
        text = subprocess.run(["git", "-C", IMG, "show", spec],
                              capture_output=True, text=True, check=True).stdout
    else:
        raise SystemExit("--pin-tranche: no such file %s" % spec)
    out = {}
    for r in csv.DictReader([l for l in text.splitlines(True)
                             if not l.startswith("#")], delimiter="\t"):
        out[(r["event"], int(r["cluster"]))] = int(r["tranche"])
    if not out:
        raise SystemExit("--pin-tranche: no rows in %s" % spec)
    return out


def write_tsv(path, rows, cols, header):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(header)
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")
    os.replace(tmp, path)


def tranche_header(a, n_unpinned):
    """The provenance line for the tranche column -- drawn here, or inherited.

    A pinned sheet must NOT carry "seed=... (S1 cap ...)": that describes a draw
    which did not happen, and someone re-deriving the sample later would try to
    reproduce it and fail (feedback_rederive_from_primary_source).
    """
    if not a.pin_tranche:
        return ("# seed=%d tranche1=%d (S1 cap %d, floor %d per other stratum)\n"
                % (SEED, TRANCHE1, T1_S1_CAP, T1_FLOOR))
    return ("# tranche INHERITED from %s -- NOT drawn here (--pin-tranche).\n"
            "# That draw was seed=%d, tranche1=%d, S1 cap %d, floor %d, stratified\n"
            "# on ITS arm's is_stm/michel_found -- deliberately the PRE-doc-15\n"
            "# meaning of michel_found, so the sample does not move with the\n"
            "# quantity it measures.  %d key(s) absent from it are tranche 2.\n"
            % (a.pin_tranche, SEED, TRANCHE1, T1_S1_CAP, T1_FLOOR, n_unpinned))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=sorted(DET))
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--sheetdir", default=None)
    ap.add_argument("--no-tagger-fit", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="first N events (debug)")
    ap.add_argument("--arm", default=None,
                    help="override the arm in DET (doc pdvd/51); use with --outdir "
                         "to validate a new arm before promoting its payloads")
    ap.add_argument("--redraw", action="store_true",
                    help="re-draw tranche 1 even though labels already exist "
                         "for this detector; see the guard in main()")
    ap.add_argument("--pin-tranche", default=None, metavar="SHEET_OR_REV",
                    help="inherit tranche membership from a previous sheet "
                         "(path, or <rev>:<path> read with git show) instead "
                         "of re-drawing it; see read_pinned_tranche")
    a = ap.parse_args()
    det = a.det
    if a.arm:                     # doc pdvd/51: validate a new arm before promoting
        DET[det]["arm"] = a.arm
    outdir = a.outdir or os.path.join(HERE, "prep-" + det)
    sheetdir = a.sheetdir or os.path.join(DET[det]["root"], "docs", "scan")
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(sheetdir, exist_ok=True)

    # A hand scan already under way is a reason NOT to re-draw.  `tranche()`
    # stratifies on `michel_found`, so re-drawing moves the sample every time
    # the algorithm improves -- 41 of 60 pdvd tranche-1 items moved between the
    # d14 and d15 arms, under a scan with labels already in it (doc pdhd/15
    # sec 10).  Refuse rather than warn: this prep prints ~180 progress lines
    # and a warning inside them is a warning nobody reads.
    if not a.pin_tranche and not a.redraw:
        labs = sorted(glob.glob(os.path.join(DET[det]["root"], "work",
                                             "stm_michel_labels", "*",
                                             "labels.json")))
        if labs:
            raise SystemExit(
                "REFUSING to re-draw tranche 1: %d label file(s) already exist "
                "for %s\n  %s\nA scan in progress must keep its sample. Either\n"
                "  --pin-tranche <sheet|rev:path>   inherit the draw those labels "
                "were placed under (doc pdhd/15 sec 10), or\n"
                "  --redraw                          start a genuinely new scan "
                "-- then serve it under a NEW --scan-tag."
                % (len(labs), det, "\n  ".join(labs)))

    dirs = event_dirs(det)
    if a.limit:
        dirs = dirs[:a.limit]
    if not dirs:
        raise SystemExit("no %s event dirs for arm %s" % (det, DET[det]["arm"]))

    rows, keys, nmissing = [], [], 0
    for i, d in enumerate(dirs):
        got = build_event(det, d, not a.no_tagger_fit)
        if not got:
            nmissing += 1
        for row, key, pay in got:
            p = os.path.join(outdir, "smprep-%s-c%d.json" % (row["event"], row["cluster"]))
            with open(p + ".tmp", "w") as fh:
                json.dump(pay, fh)
            os.replace(p + ".tmp", p)
            rows.append(row); keys.append(key)
        print("  [%3d/%3d] %-24s %2d candidates" %
              (i + 1, len(dirs), os.path.basename(d), len(got)), flush=True)

    # the reference curves, once per detector (verified identical across events)
    ref = None
    for d in dirs:
        c = glob.glob(os.path.join(d, "calib-pr-evt*.json"))
        if c:
            ref = json.load(open(c[0])).get("dqdx_ref")
            if ref:
                break
    if ref:
        with open(os.path.join(outdir, "dqdx_ref_%s.json" % det), "w") as fh:
            json.dump(ref, fh)

    order = sorted(range(len(rows)), key=lambda i: (rows[i]["event"], rows[i]["cluster"]))
    rows = [rows[i] for i in order]; keys = [keys[i] for i in order]
    pinned = read_pinned_tranche(a.pin_tranche) if a.pin_tranche else None
    t1 = tranche(keys)
    n_unpinned = 0
    for n, (r, k) in enumerate(zip(rows, keys), start=1):
        r["scan_id"] = k["scan_id"] = n
        kk = (r["event"], r["cluster"])
        if pinned is None:
            tr = t1.get(kk, 2)
        elif kk in pinned:
            tr = pinned[kk]
        else:
            tr = 2                       # never grow a pinned sample
            n_unpinned += 1
        r["tranche"] = k["tranche"] = tr
        k["stratum"] = stratum(k)
    # tranche 1 first, then scan_id -- the viewer serves the list in file order
    rows.sort(key=lambda r: (r["tranche"], r["scan_id"]))
    keys.sort(key=lambda r: (r["tranche"], r["scan_id"]))

    sheet = os.path.join(sheetdir, "%s_stm_michel_scan_sheet.tsv" % det)
    keyf = os.path.join(sheetdir, "%s_stm_michel_scan_key.tsv" % det)
    write_tsv(sheet, rows,
              ["scan_id", "tranche", "event", "cluster", "npts", "muon_len_cm",
               "n_near", "n_far"],
              "# doc pdhd/12 -- STM + Michel hand-scan sheet, det=%s arm=%s\n"
              "# NO verdict, NO stratum, NO chain flag: those are in the KEY.\n"
              % (det, DET[det]["arm"]) + tranche_header(a, n_unpinned))
    write_tsv(keyf, keys,
              ["scan_id", "tranche", "stratum", "event", "cluster", "npts",
               "muon_len_cm", "is_stm", "michel_found", "michel_conn_type",
               "michel_len", "michel_ke_best", "michel_kink_deg", "n_dots",
               "in_fv", "reject_bits", "reject_names", "n_near", "n_far"],
              KEY_HEADER % (det, DET[det]["arm"]) + tranche_header(a, n_unpinned))

    cnt = {}
    for k in keys:
        cnt[k["stratum"]] = cnt.get(k["stratum"], 0) + 1
    print("\n%s: %d events (%d with no candidate), %d items"
          % (det, len(dirs), nmissing, len(rows)))
    print("  strata: " + "  ".join("%s=%d" % (s, cnt[s]) for s in sorted(cnt)))
    print("  tranche 1: %d" % sum(1 for r in rows if r["tranche"] == 1))
    print("  sheet: %s\n  key:   %s\n  prep:  %s" % (sheet, keyf, outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
