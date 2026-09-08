#!/usr/bin/env python3
"""doc pdhd/13 -- why CheckSTM_Michel loses a Michel that is plainly there.

Reproduces every number in doc pdhd/13.  The reference case is PDVD
039252_15 cluster 77: is_stm=1, reject_bits=0, michel_found=0, and a 20.1 cm
Michel sitting 1.91 cm from the fitted stop in the SAME Q-L bundle.

What it measures, per STM candidate of an arm:

  D2  same-bundle neighbours within michel_dot_radius_cm of the stop, split at
      the dot_max_len_cm cap.  A neighbour above the cap is dropped by
      CheckSTM_Michel.cxx:812 BEFORE any PR runs on it, so it can become
      neither an attached arm nor a dot.
  D1  n_dots>0 with michel_found==0.  michel_found is assigned at exactly one
      line (:1169), inside the attached-arm block, so a Michel reconstructed
      only as detached dots is never reported as found.
  D3  T_rec_charge points (all fitted segments of the main cluster, keyed by
      sub_cluster_id//1000) against T_stm_michel_pts points (roles 1-4 only).
      An excess means the PR DID fit segments that the arm classifier then
      discarded -- a classification failure, not a segmentation failure.
      n_stop_arms==0 separates "nothing attached at the stop at all".
  --  the delay-signed drift offset of each neighbour, WITH the entry-point
      null control.  A Michel is emitted after the muon decays and can only
      ever appear later in time, i.e. displaced along drift away from the
      anode.  The entry point has no delayed emission, so the same measurement
      there is the null floor.  Without it a stop-only number means nothing.

The drift sign is taken per candidate from dx/d(time_slice) on its OWN fit
(T_rec_charge x vs pt), so nothing here assumes which side the anode is on --
PDVD and SBND are cathode-centred and sign(x) is not drift distance.

Bundle key is (flash_id, cluster_t0_us) from T_cluster.  Note that a flash
alone is not a unique bundle key; both fields are required and the t0 must
match exactly, which is what "same bundle" means for these arms.

Repro:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
  python3 pdhd/docs/scripts/d13_michel_loss_census.py 'pdhd/work/*_d51hnu' \
      --det pdhd --out /home/xqian/tmp/d13/d13h
  python3 pdhd/docs/scripts/d13_michel_loss_census.py 'pdvd/work/*_d51vnu' \
      --det pdvd --out /home/xqian/tmp/d13/d13v \
      --connect-item 039252_15_d51vnu:77
"""
import argparse, glob, json, os, sys, zipfile
import numpy as np
import uproot

# CheckSTM_Michel C++ defaults (clus/src/CheckSTM_Michel.cxx:328).  The PDHD and
# PDVD jobs' stm_michel_knobs bags set 9 keys and NONE of these three, so these
# are what ran on d51hnu / d51vnu -- verified against the compiled config.
DOT_MAX_LEN_CM = 10.0
MICHEL_DOT_RADIUS_CM = 15.0

# ChanScheme plane bases, for the 2-D connectivity test only.
BASE = {"pdhd": (0, 3200, 6400), "pdvd": (0, 3808, 7616)}

# The display's sample definition (doc pdhd/12).
MIN_PROFILE_PTS = 20
MIN_MUON_LEN_CM = 10.0


def bundle_of(tc):
    """cluster_id -> (flash_id, cluster_t0_us), plus length and npoints maps."""
    cid = tc["cluster_id"]
    return (dict(zip(cid, zip(tc["flash_id"], tc["cluster_t0_us"]))),
            dict(zip(cid, tc["length_cm"])),
            dict(zip(cid, tc["npoints"])),
            dict(zip(cid, tc["is_associated"])))


def drift_sign(x, pt):
    """+1 if a later time slice reconstructs at larger x, else -1.

    Taken from the candidate's own fit, so no anode-side assumption is made.
    """
    if len(x) < 10 or float(np.std(pt)) < 1e-6:
        return 0.0
    return float(np.sign(np.polyfit(pt, x, 1)[0]))


def neighbours(byc, bmap, lmap, main_cid, pt, radius):
    """Same-bundle clusters whose closest point is within `radius` of `pt`."""
    key = bmap.get(main_cid)
    out = []
    if key is None:
        return out
    for c, pts in byc.items():
        if c == main_cid:
            continue
        k = bmap.get(c)
        if k is None or k[0] != key[0] or abs(k[1] - key[1]) > 1e-6:
            continue
        d = np.sqrt(((pts - pt) ** 2).sum(1))
        j = int(d.argmin())
        if d[j] > radius:
            continue
        out.append((int(c), float(lmap.get(c, 0.0)), float(d[j]), pts[j] - pt, pts))
    return out


def connectivity_2d(f, det, cid):
    """Is the unmodelled near-stop charge 2-D contiguous with the muon?

    8-connectivity over live cells of the cluster's own T_proj_data, per plane.
    A 3-D gap that vanishes here is an imaging/clustering split, not a real gap.
    """
    from scipy import ndimage
    pj = f["T_proj_data"].arrays(
        ["cluster_id", "channel", "time_slice", "charge", "charge_pred"], library="np")
    ids = np.asarray(pj["cluster_id"][0])
    w = np.where(ids == cid)[0]
    if not len(w):
        return None
    i = int(w[0])
    ch = np.asarray(pj["channel"][0][i], dtype=np.int64)
    ts = np.asarray(pj["time_slice"][0][i], dtype=np.int64)
    q = np.asarray(pj["charge"][0][i], dtype=np.float64)
    qp = np.asarray(pj["charge_pred"][0][i], dtype=np.float64)
    rc = f["T_rec_charge"].arrays(["pu", "pv", "pw", "pt", "rr", "sub_cluster_id"], library="np")
    k = (rc["sub_cluster_id"] // 1000) == cid
    if k.sum() < 2:
        return None
    j = int(np.argmin(rc["rr"][k]))
    stop_ch = (rc["pu"][k][j], rc["pv"][k][j], rc["pw"][k][j])
    stop_ts = rc["pt"][k][j]
    b = BASE[det]
    plane = np.where(ch < b[1], 0, np.where(ch < b[2], 1, 2))
    res = []
    for p, name in enumerate("UVW"):
        m = plane == p
        C, T, Q, QP = ch[m], ts[m], q[m], qp[m]
        live = Q > 500
        C, T, Q, QP = C[live], T[live], Q[live], QP[live]
        if len(C) == 0:
            continue
        c0, t0 = C.min(), T.min()
        grid = np.zeros((C.max() - c0 + 1, T.max() - t0 + 1), bool)
        grid[C - c0, T - t0] = True
        lab, n = ndimage.label(grid, structure=np.ones((3, 3), int))
        modelled = QP > 0.2 * np.maximum(Q, 1.0)
        michel = ((QP < 0.05 * np.maximum(Q, 1.0)) & (Q > 2000)
                  & (T >= stop_ts - 2) & (np.abs(C - stop_ch[p]) < 60))
        if not modelled.any() or not michel.any():
            continue
        lm = set(lab[C[modelled] - c0, T[modelled] - t0].tolist())
        lx = set(lab[C[michel] - c0, T[michel] - t0].tolist())
        mm = np.isin(lab[C - c0, T - t0], list(lm))
        xx = np.isin(lab[C - c0, T - t0], list(lx))
        gap = int(np.min(np.maximum(np.abs(C[xx][:, None] - C[mm][None, :]),
                                    np.abs(T[xx][:, None] - T[mm][None, :]))))
        # all measured-but-unpredicted charge in this plane's whole projection,
        # for scale: if the near-stop blob dominates it, the Michel is the only
        # thing the fit is failing to model.
        allun = (QP < 0.05 * np.maximum(Q, 1.0)) & (Q > 2000)
        res.append(dict(plane=name, ncell=int(len(C)), ncomp=int(n),
                        shared=len(lm & lx), gap=gap,
                        q_unmodelled=float(Q[michel].sum()),
                        q_unmodelled_all=float(Q[allun].sum())))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="work-dir globs, e.g. 'pdvd/work/*_d51vnu'")
    ap.add_argument("--det", required=True, choices=sorted(BASE))
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius", type=float, default=MICHEL_DOT_RADIUS_CM)
    ap.add_argument("--dot-max-len", type=float, default=DOT_MAX_LEN_CM)
    ap.add_argument("--orphan-cm", type=float, default=3.0,
                    help="a cluster point this far from every reconstructed point is orphan")
    ap.add_argument("--connect-item", default=None,
                    help="<workdir basename>:<cluster_id>, run the 2-D connectivity test on it")
    args = ap.parse_args()

    dirs = []
    for pat in args.files:
        dirs.extend(sorted(glob.glob(pat)) if any(c in pat for c in "*?[") else [pat])

    rows, nbr_rows = [], []
    for w in dirs:
        rf, zf = os.path.join(w, "tracking-pr.root"), os.path.join(w, "mabc-pr.zip")
        if not (os.path.exists(rf) and os.path.exists(zf)):
            continue
        ev = os.path.basename(w)
        try:
            f = uproot.open(rf)
            if "T_stm_michel" not in [k.split(";")[0] for k in f.keys()]:
                continue          # no STM-tagged main in this event; benign
            sm = f["T_stm_michel"].arrays(library="np")
            tc = f["T_cluster"].arrays(library="np")
            rc = f["T_rec_charge"].arrays(["x", "y", "z", "pt", "sub_cluster_id"], library="np")
            pp = f["T_stm_michel_pts"].arrays(["cluster_id", "x", "y", "z"], library="np")
            d = json.load(zipfile.ZipFile(zf).open("data/0/0-clustering-global.json"))
        except Exception as e:
            print("# skip %s: %s" % (ev, e), file=sys.stderr)
            continue

        P = np.stack([np.array(d["x"]), np.array(d["y"]), np.array(d["z"])], 1)
        CI = np.array(d["cluster_id"])
        byc = {int(c): P[CI == c] for c in np.unique(CI)}
        bmap, lmap, npmap, amap = bundle_of(tc)

        for i in range(len(sm["cluster_id"])):
            if (sm["has_pass"][i] != 1 or sm["n_profile_pts"][i] < MIN_PROFILE_PTS
                    or sm["muon_len"][i] < MIN_MUON_LEN_CM):
                continue
            mc = int(sm["cluster_id"][i])
            stop = np.array([sm["stop_x"][i], sm["stop_y"][i], sm["stop_z"][i]])
            entry = np.array([sm["entry_x"][i], sm["entry_y"][i], sm["entry_z"][i]])

            k = (rc["sub_cluster_id"] // 1000) == mc
            n_rc = int(k.sum())
            F = np.stack([rc["x"][k], rc["y"][k], rc["z"][k]], 1)
            sgn = drift_sign(rc["x"][k], rc["pt"][k])

            pk = pp["cluster_id"] == mc
            n_role = int(pk.sum())
            R = np.stack([pp["x"][pk], pp["y"][pk], pp["z"][pk]], 1)

            # is the main cluster itself over-clustered?  max distance from its
            # own cloud to its own fit.
            cloud = byc.get(mc, np.zeros((0, 3)))
            resid = -1.0
            n_orphan = 0
            if len(cloud) and len(F):
                dd = np.sqrt(((cloud[:, None, :] - F[None, :, :]) ** 2).sum(-1)).min(1)
                resid = float(dd.max())
                if len(R):
                    near = cloud[np.sqrt(((cloud - stop) ** 2).sum(1)) <= args.radius]
                    if len(near):
                        dr = np.sqrt(((near[:, None, :] - R[None, :, :]) ** 2).sum(-1)).min(1)
                        n_orphan = int((dr > args.orphan_cm).sum())

            nb_short = nb_long = 0
            for anchor, tag in ((stop, "stop"), (entry, "entry")):
                for (c, L, dist, vec, pts) in neighbours(byc, bmap, lmap, mc, anchor, args.radius):
                    drift = sgn * float(vec[0])
                    frac_delay = float((sgn * (pts[:, 0] - anchor[0]) > 0).mean()) if sgn else -1.0
                    nbr_rows.append(dict(
                        det=args.det, event=ev, main=mc, anchor=tag, cid=c,
                        length_cm=L, npoints=int(npmap.get(c, 0)),
                        is_associated=int(amap.get(c, 0)), dist_cm=dist,
                        drift_cm=drift, trans_cm=float(np.hypot(vec[1], vec[2])),
                        frac_delay=frac_delay,
                        over_cap=int(L > args.dot_max_len),
                        michel_found=int(sm["michel_found"][i]),
                        n_dots=int(sm["n_dots"][i])))
                    if tag == "stop":
                        if L > args.dot_max_len:
                            nb_long += 1
                        else:
                            nb_short += 1

            rows.append(dict(
                det=args.det, event=ev, run=ev.split("_")[0], cluster=mc,
                is_stm=int(sm["is_stm"][i]), reject_bits=int(sm["reject_bits"][i]),
                michel_found=int(sm["michel_found"][i]),
                michel_conn_type=int(sm["michel_conn_type"][i]),
                n_dots=int(sm["n_dots"][i]),
                n_dot_clusters_unfit=int(sm["n_dot_clusters_unfit"][i]),
                n_stop_arms=int(sm["n_stop_arms"][i]),
                n_chain_segs=int(sm["n_chain_segs"][i]),
                n_body_other=int(sm["n_body_other"][i]),
                n_ext=int(sm["n_ext"][i]),
                muon_len=float(sm["muon_len"][i]),
                n_rec_charge_pts=n_rc, n_role_pts=n_role,
                n_discarded_pts=n_rc - n_role,
                cloud_fit_resid_cm=resid, n_orphan_near_stop=n_orphan,
                nbr_short=nb_short, nbr_long=nb_long, drift_sign=sgn))

    if not rows:
        print("no candidates", file=sys.stderr)
        return 1

    def tsv(path, recs, header):
        cols = list(recs[0].keys())
        with open(path, "w") as fh:
            fh.write("# %s\n" % header)
            fh.write("\t".join(cols) + "\n")
            for r in recs:
                fh.write("\t".join(("%.6g" % r[c]) if isinstance(r[c], float) else str(r[c])
                                   for c in cols) + "\n")

    hdr = ("doc pdhd/13 d13_michel_loss_census.py det=%s arms=%d radius=%g dot_max_len=%g"
           % (args.det, len(dirs), args.radius, args.dot_max_len))
    tsv(args.out + "_candidates.tsv", rows, hdr)
    if nbr_rows:
        tsv(args.out + "_neighbours.tsv", nbr_rows, hdr)

    # ---------------- summary ----------------
    R = rows
    out = []
    A = lambda k: np.array([r[k] for r in R])
    out.append("=== %s : %d STM candidates over %d arms ===" % (args.det, len(R), len(dirs)))
    out.append("  michel_found==1 : %d      n_dots>0 : %d"
               % ((A("michel_found") == 1).sum(), (A("n_dots") > 0).sum()))

    # D1 -- dot-only Michels are never reported
    d1 = [r for r in R if r["n_dots"] > 0 and r["michel_found"] == 0]
    nfound = int((A("michel_found") == 1).sum())
    out.append("")
    out.append("  D1  michel_found is set only by the attached path (CheckSTM_Michel.cxx:1169)")
    out.append("      n_dots>0 with michel_found==0        : %d" % len(d1))
    out.append("      michel_conn_type==2 rows             : %d  (must equal the line above)"
               % (A("michel_conn_type") == 2).sum())
    out.append("      share of ALL reconstructed Michels   : %.3f  (%d of %d)"
               % (len(d1) / max(nfound + len(d1), 1), len(d1), nfound + len(d1)))

    # D2 -- the companion admission cap
    S = [r for r in R if r["is_stm"] == 1]
    nm = [r for r in R if r["michel_found"] == 0]
    d2 = [r for r in nm if r["nbr_long"] > 0]
    out.append("")
    out.append("  D2  companion admission is gated by dot_max_len_cm (:812), %g cm" % args.dot_max_len)
    out.append("      michel_found==0                      : %d" % len(nm))
    out.append("      ...with a same-bundle neighbour <%g cm of the stop and LONGER than the cap"
               % args.radius)
    out.append("         (dropped before any PR ran on it) : %d   of which is_stm==1 : %d"
               % (len(d2), len([r for r in d2 if r["is_stm"] == 1])))
    if d2:
        for r in sorted(d2, key=lambda r: -r["is_stm"])[:6]:
            out.append("           %-24s cl %-4d is_stm %d  n_stop_arms %d  n_dots %d"
                       % (r["event"], r["cluster"], r["is_stm"], r["n_stop_arms"], r["n_dots"]))

    # D3 -- classification vs segmentation
    E = [r for r in S if r["michel_found"] == 0]
    E0 = [r for r in E if r["n_dots"] == 0]
    out.append("")
    out.append("  D3  is_stm==1 and michel_found==0 : %d" % len(E))
    if E:
        disc = np.array([r["n_discarded_pts"] for r in E])
        out.append("      main-cluster points fitted but carried into NO role (classifier dropped them)")
        out.append("         >0 on %d of %d (%.3f)   p50 %d  p90 %d  max %d"
                   % ((disc > 0).sum(), len(E), (disc > 0).mean(),
                      int(np.percentile(disc, 50)), int(np.percentile(disc, 90)), int(disc.max())))
    if E0:
        arms = np.array([r["n_stop_arms"] for r in E0])
        out.append("      restricted to n_dots==0 (the genuinely empty set), n=%d :" % len(E0))
        out.append("         n_stop_arms==0 (nothing attached at the stop) : %d (%.3f)"
                   % ((arms == 0).sum(), (arms == 0).mean()))
        out.append("         n_stop_arms >0 (arms existed, none was a Michel): %d (%.3f)"
                   % ((arms > 0).sum(), (arms > 0).mean()))

    # the delayed-emission test, with its null control
    if nbr_rows:
        out.append("")
        out.append("  Delayed emission: delay-signed drift offset at the STOP, with the ENTRY as")
        out.append("  the null control (no delayed emission exists there).")
        N = nbr_rows
        for tag in ("stop", "entry"):
            sub = [n for n in N if n["anchor"] == tag and n["dist_cm"] < 8 and n["frac_delay"] >= 0]
            if not sub:
                continue
            a = np.array([n["drift_cm"] for n in sub])
            out.append("      %-5s n=%3d   delay-side fraction %.3f   drift p50 %+.2f cm"
                       % (tag.upper(), len(sub), (a > 0).mean(), np.median(a)))
        ss = [n for n in N if n["anchor"] == "stop" and n["dist_cm"] < 8 and n["frac_delay"] >= 0]
        ee = [n for n in N if n["anchor"] == "entry" and n["dist_cm"] < 8 and n["frac_delay"] >= 0]
        if ss and ee:
            ds = (np.array([n["drift_cm"] for n in ss]) > 0).mean()
            de = (np.array([n["drift_cm"] for n in ee]) > 0).mean()
            out.append("      stop - entry = %+.3f   (a delayed Michel would make the STOP one-sided;" % (ds - de))
            out.append("                            an excess carried by the ENTRY control is geometry)")

    txt = "\n".join(out)
    with open(args.out + "_summary.txt", "w") as fh:
        fh.write("# " + hdr + "\n" + txt + "\n")
    print(txt)

    # optional: the 2-D connectivity test on one named item
    if args.connect_item:
        ev, _, cs = args.connect_item.partition(":")
        cid = int(cs)
        hit = [w for w in dirs if os.path.basename(w) == ev]
        if not hit:
            print("\n# connect-item %s not among the arms" % ev, file=sys.stderr)
        else:
            f = uproot.open(os.path.join(hit[0], "tracking-pr.root"))
            res = connectivity_2d(f, args.det, cid)
            print("\n=== 2-D connectivity, %s cluster %d ===" % (ev, cid))
            print("    Is the unmodelled near-stop charge in the SAME connected component as")
            print("    the muon's modelled cells?  8-connectivity over live T_proj_data cells.")
            if not res:
                print("    no T_proj_data entry for this cluster")
            for r in res:
                print("      %s: %5d live cells, %d component(s); shared with the muon: %d"
                      " -> %s  (cell gap %d)"
                      % (r["plane"], r["ncell"], r["ncomp"], r["shared"],
                         "ATTACHED" if r["shared"] else "separated", r["gap"]))
                print("         measured-but-unpredicted charge: %.3g e near the stop,"
                      " %.3g e in the whole projection"
                      % (r["q_unmodelled"], r["q_unmodelled_all"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
