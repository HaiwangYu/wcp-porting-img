#!/usr/bin/env python3
"""doc pdvd/50 round 2 -- dQ/dx vs residual range with a PER-POINT READOUT-UNIT
label, and the two counters that tell charge RECOVERY from point DELETION.

Fork BY DUPLICATION of d50_dqdx_rr_cross.py (that file, d42_dqdx_rr.py and the
PDHD fork of the latter are untouched).  The decode, the kink re-anchor, the 11
rr bins, the 3 % systematic floor and the tier definitions are doc 50's,
unchanged, so this script reproduces doc 50 sections 2-3 on doc 50's own arms --
which is the round's engine gate.

What is added over doc 50:

  * a per-point APA / drift-volume label, so the owner's "separate APA0" can be
    answered on the dQ/dx-vs-rr curve itself and not only in the deficit
    anatomy.  PDHD: (pw - 6400) // 960, the wire-index route doc 50 sec 4.2b
    validated at 78867/78867 against the sign(x)+z guess but never committed as
    code; this closes that gap.  PDVD: the geometric drift volume (anodes 0-3
    bottom x<0, anodes 4-7 top x>0, clus.jsonnet:63-72), because PDVD's two CRP
    faces carry different partly-overlapping channel sets and the analogous
    block arithmetic (pw - 7616) // 584 is NOT verified contiguous
    (PdvdMagnifyTrackingVisitor.h:74-82).  Both labels are emitted on PDVD and
    --confusion prints their agreement, so the cheap route is earned or refused
    rather than assumed.

  * pts_per_cm = live fit points / kept path length.  R3
    (traj_final_fill_charge_test) DELETES the charge-free points that f_low
    counts, so f_low must fall whether or not any charge was recovered.  Read
    the two together: f_low down WITH pts_per_cm held is recovery, f_low down
    WITH pts_per_cm down is deletion (feedback_matched_population_metric_bias).

  * absolute point counts in the five expectation bands doc 50 sec 4.2
    published as fractions.  Deletion shrinks every band; recovery collapses
    only the < 0.2 band while 0.8-1.2 holds.

  * reach counters (rrmin < 2 and rrmax >= 22, the doc-55 reach cut), so a tier
    collapse can be attributed to R3 trimming the stopping end instead of to
    the old cause -- doc pdvd/32's amputated track ends and doc 38's end trim
    already act exactly there.

Decoding, from doc 42 via doc 50 (PDHD uses PdvdMagnifyTrackingVisitor verbatim,
so the schema is identical on both detectors):

    dQ/dx [e/cm] = (q - dQdx_offset)/dQdx_scale / nq      nq = dx in cm
    rr already in cm ; two passes per cluster, block = cluster*10 + pass

Michel/leftover removal is the tagger's own kink, as in doc 42/50: when
left_L > 0 the points past kink_num are dropped and rr is re-anchored there.

Usage:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
  python3 ../pdvd/docs/nf_sp_img_clus/scripts/d51_dqdx_rr_apa.py --det pdhd \
      --ref stm/pdhd_ref_dqdx.json --max-abs-x 1e9 --status 0 \
      --out ANA/d51_pdhd work/*_d51hstm/tracking-stm.root
Writes <out>_{tracks,points,summary,apa}.tsv.
"""
import argparse, json, os, sys
import numpy as np
import uproot

BINS = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 60)]
SYS_FLOOR = 0.03
HYPS = ["muon", "proton"]
KEYS = {"muon": "MuonDeDx", "proton": "ProtonDeDx"}
PLATEAU_RR = (40.0, 60.0)                      # doc 50 sec 4.2's plateau window
BANDS = [(0.0, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 1.2), (1.2, 1e9)]
BANDNAME = ["lt0.2", "0.2-0.5", "0.5-0.8", "0.8-1.2", "gt1.2"]

# ChanScheme (PdvdMagnifyTrackingVisitor.h:83-103) is base[plane] + the rank of
# the wire's channel among that plane's channels over ALL anodes, so the block
# size is a property of the WIRE FILE, not of config.  Both rows below are the
# runtime 'channel scheme nch=... base=...' line from the production job logs.
CHAN = {
    "pdhd": dict(base=(0, 3200, 6400), nch=(3200, 3200, 3840), nunit=4),
    "pdvd": dict(base=(0, 3808, 7616), nch=(3808, 3808, 4672), nunit=8),
}


def load_ref(path, key):
    t = json.load(open(path))[key]
    x = t["start"] + t["step"] * np.arange(len(t["values"]))
    y = np.asarray(t["values"], float)
    return lambda rr: np.interp(rr, x, y)          # clamped outside, like LinterpFunction


def scale_and_shape(meds, cen, ref):
    """One free scale k = geometric mean of median/ref; shape rms = rms of
    log(median/(k ref)).  k is the scale, shape is scale-free."""
    r = meds / ref(cen)
    k = float(np.exp(np.mean(np.log(r))))
    return k, float(np.sqrt(np.mean(np.log(r / k) ** 2)))


def unit_from_wire(det, pw):
    """Readout unit from the stored collection-plane wire coordinate.

    VALID ON PDHD ONLY (doc 50 sec 4.2b, 78867/78867 against sign(x)+z).  On
    PDVD the per-anode channel run is not verified contiguous, so the value is
    computed for the --confusion cross-check and never used as the label."""
    c = CHAN[det]
    per = c["nch"][2] // c["nunit"]
    u = np.floor((np.asarray(pw, float) - c["base"][2]) / per).astype(np.int64)
    return np.clip(u, 0, c["nunit"] - 1)


def unit_geometric(det, x, y, z):
    """Readout unit from geometry, the route d50_deficit_plots.py uses.

    PDHD (protodunehd-wires-larsoft-v1.json.bz2, 4 APAs):
        APA0 x<0 z<231 ; APA1 x>0 z<231 ; APA2 x<0 z>=231 ; APA3 x>0 z>=231,
      and cfg/pgrapher/experiment/pdhd/clus.jsonnet groups APA0+APA2 = face 0
      (drift -x), APA1+APA3 = face 1 (drift +x).
    PDVD (protodunevd-wires-larsoft-v7-uvwfit.json.bz2, 8 anodes x 2 faces):
      the label is the DRIFT VOLUME -- anodes 0-3 bottom (x<0), anodes 4-7 top
      (x>0), protodunevd/clus.jsonnet:63-72 -- coded 0 and 1."""
    x = np.asarray(x, float); z = np.asarray(z, float)
    if det == "pdhd":
        return np.where(z < 231.0, np.where(x < 0, 0, 1), np.where(x < 0, 2, 3)).astype(np.int64)
    return (x > 0).astype(np.int64)


def unit_labels(det):
    if det == "pdhd":
        return {0: "APA0 (x<0,face0)", 1: "APA1 (x>0,face1)",
                2: "APA2 (x<0,face0)", 3: "APA3 (x>0,face1)"}
    return {0: "bottom (x<0, anodes 0-3)", 1: "top (x>0, anodes 4-7)"}


def selections(det):
    """Named per-point unit selections the summary reports.  On PDHD these
    answer the owner's 'separate APA0' directly; the units are NOT disjoint at
    track level -- a track crossing APAs contributes points to more than one
    row -- which is why every selection is defined on POINTS."""
    if det == "pdhd":
        return [("all", [0, 1, 2, 3]), ("APA0", [0]), ("APA1", [1]), ("APA2", [2]),
                ("APA3", [3]), ("noAPA0", [1, 2, 3]), ("face0_xneg", [0, 2]),
                ("face1_xpos", [1, 3])]
    return [("all", [0, 1]), ("bottom_xneg", [0]), ("top_xpos", [1])]


def bin_table(rr, v, ref_muon, k_pop=None):
    """Per-bin median of v/(k ref) with a 3 % systematic floor, and the chi2
    against 1.  Returns (k_pop, chi2, nb, ratios, errs, ns)."""
    if k_pop is None:
        k_pop = float(np.exp(np.median(np.log(v / ref_muon(rr))))) if len(v) else float("nan")
    ratios, errs, ns, chi2, nb = [], [], [], 0.0, 0
    for lo, hi in BINS:
        m = (rr >= lo) & (rr < hi)
        ns.append(int(m.sum()))
        if m.sum() < 5:
            ratios.append(float("nan")); errs.append(float("nan")); continue
        r = v[m] / (k_pop * ref_muon(rr[m]))
        med = float(np.median(r))
        err = float(1.2533 * 1.4826 * np.median(np.abs(r - med)) / np.sqrt(m.sum()))
        err = float(np.hypot(err, SYS_FLOOR * med))
        ratios.append(med); errs.append(err); chi2 += ((med - 1) / err) ** 2; nb += 1
    return k_pop, chi2, nb, ratios, errs, ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--det", required=True, choices=sorted(CHAN))
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-abs-x", type=float, default=1e9)
    ap.add_argument("--min-npts", type=int, default=10)
    ap.add_argument("--status", default="0", help="comma list of T_stm_pass status codes to keep (0 = accepted STM, 5 = proton endpoint)")
    ap.add_argument("--low-frac", type=float, default=0.40, help="a point is charge-DEFICIENT below this fraction of the muon plateau")
    ap.add_argument("--complete-max-flow", type=float, default=0.05, help="a track is charge-COMPLETE below this f_low")
    ap.add_argument("--confusion", action="store_true", help="print the wire-label vs geometric-label confusion matrix and exit code 0")
    a = ap.parse_args()

    refs = {h: load_ref(a.ref, KEYS[h]) for h in HYPS}
    plateau = float(refs["muon"](np.array([59.5]))[0])
    low_thr = a.low_frac * plateau
    want = {int(s) for s in a.status.split(",")}
    labels = unit_labels(a.det)
    nunit = 4 if a.det == "pdhd" else 2

    tracks, points = [], []
    conf = np.zeros((CHAN[a.det]["nunit"], CHAN[a.det]["nunit"]), dtype=np.int64)
    for path in a.roots:
        try:
            f = uproot.open(path)
            t = f["T_rec_charge"].arrays(["x", "y", "z", "q", "nq", "rr", "ndf", "status",
                                          "pass", "reduced_chi2", "pu", "pv", "pw"], library="np")
            tr = f["Trun"].arrays(["dQdx_scale", "dQdx_offset"], library="np")
            sp = f["T_stm_pass"].arrays(library="np")
        except Exception as ex:
            print("skip", path, ex, file=sys.stderr); continue
        ev = os.path.basename(os.path.dirname(path))
        pinfo = {(int(c) * 10 + int(p)): (int(k), float(eL), float(lL))
                 for c, p, k, eL, lL in zip(sp["cluster_id"], sp["pass"], sp["kink_num"], sp["exit_L"], sp["left_L"])}
        for blk in sorted(set(t["ndf"].tolist())):
            mk = t["ndf"] == blk
            st = int(t["status"][mk][0])
            if st not in want or mk.sum() < a.min_npts:
                continue
            n = int(mk.sum())
            dQ = (t["q"][mk] - tr["dQdx_offset"][0]) / tr["dQdx_scale"][0]
            dx = t["nq"][mk]; x = t["x"][mk]; rr_end = t["rr"][mk]; chi2 = t["reduced_chi2"][mk]
            yy = t["y"][mk]; zz = t["z"][mk]; pw = t["pw"][mk]
            with np.errstate(divide="ignore", invalid="ignore"):
                dqdx = np.where(dx > 0, dQ / dx, np.nan)
            dqdx = np.where(np.abs(x) > a.max_abs_x, np.nan, dqdx)

            # --- readout unit, per point -------------------------------------
            uw = unit_from_wire(a.det, pw)
            ug = unit_geometric(a.det, x, yy, zz)
            if a.det == "pdhd":
                unit = uw                       # validated route (doc 50 sec 4.2b)
                for i in range(n):
                    conf[uw[i], ug[i]] += 1
            else:
                unit = ug                       # drift volume; wire route unproven
                # bottom = anodes 0-3, top = anodes 4-7, so fold the wire label
                for i in range(n):
                    conf[uw[i], ug[i]] += 1

            kink, exL, lfL = pinfo.get(int(blk), (-1, float("nan"), 0.0))
            has_left = (lfL > 0) and (0 <= kink < n - 1)
            keep = np.ones(n, bool)
            if has_left:
                keep[kink + 1:] = False
                rr_k = rr_end - rr_end[kink]
            else:
                rr_k = rr_end.copy()
            rr_use = rr_k[keep]; v = dqdx[keep]; u_use = unit[keep]
            good = np.isfinite(v) & (v > 0)                    # live points only
            f_low = float((v[good] < low_thr).mean()) if good.sum() else float("nan")
            # kept path length, for the deletion-vs-recovery counter
            len_kept = float(rr_use.max() - rr_use.min()) if keep.sum() else float("nan")
            pts_per_cm = float(good.sum()) / len_kept if len_kept and len_kept > 1.0 else float("nan")

            meds, cen, cnt = [], [], []
            for lo, hi in BINS:
                b = good & (rr_use >= lo) & (rr_use < hi)
                meds.append(float(np.median(v[b])) if b.sum() >= 3 else float("nan"))
                cnt.append(int(b.sum())); cen.append((lo + hi) / 2)
            meds = np.array(meds); cen = np.array(cen); cnt = np.array(cnt)
            pop = np.isfinite(meds)
            hyp = {}
            for h in HYPS:
                if pop.sum() >= 2:
                    hyp[h] = scale_and_shape(meds[pop], cen[pop], refs[h])
                else:
                    hyp[h] = (float("nan"), float("nan"))
            best = min(HYPS, key=lambda h: hyp[h][1] if np.isfinite(hyp[h][1]) else 1e9) if pop.sum() >= 2 else "none"

            bragg = v[good & (rr_use < 2)]; plat = v[good & (rr_use >= 20) & (rr_use < 40)]
            contrast = float(np.median(bragg) / np.median(plat)) if len(bragg) >= 3 and len(plat) >= 3 else float("nan")
            mchi2 = float(np.nanmedian(chi2[keep])) if keep.sum() else float("nan")
            rrmin = float(rr_use[good].min()) if good.sum() else float("nan")
            rrmax = float(rr_use[good].max()) if good.sum() else float("nan")
            reach = int(np.isfinite(rrmin) and rrmin < 2.0 and rrmax >= 22.0)
            doc55 = (n >= 40 and pop.sum() >= 6 and rrmin < 2.0 and rrmax >= 22.0
                     and contrast >= 2.0 and mchi2 <= 2.5 and hyp["muon"][1] <= 0.10)
            complete = (n >= 40 and pop.sum() >= 2 and np.isfinite(f_low) and f_low < a.complete_max_flow)
            row = dict(det=a.det, event=ev, block=int(blk), cluster=int(blk) // 10, status=st,
                       npts=n, nkept=int(keep.sum()), ngood=int(good.sum()),
                       length=float(rr_end.max()), len_kept=len_kept, pts_per_cm=pts_per_cm,
                       kink=kink, exit_L=exL, left_L=lfL,
                       has_left=int(has_left), f_low=f_low, rrmin=rrmin, rrmax=rrmax, reach=reach,
                       nbins=int(pop.sum()), contrast=contrast,
                       k_muon=hyp["muon"][0], shape_muon=hyp["muon"][1],
                       k_proton=hyp["proton"][0], shape_proton=hyp["proton"][1],
                       best=best, med_chi2=mchi2, doc55=int(doc55), complete=int(complete))
            for uu in range(nunit):
                row["n_u%d" % uu] = int((u_use[good] == uu).sum())
            row["meds"] = meds; row["cnt"] = cnt
            tracks.append(row)
            for i in range(n):
                points.append((a.det, ev, int(blk), st, i, "%.2f" % rr_k[i], "%.2f" % rr_end[i],
                               "%.1f" % dqdx[i] if np.isfinite(dqdx[i]) else "nan",
                               "%.3f" % dx[i], "%.2f" % x[i], "%.2f" % yy[i], "%.2f" % zz[i],
                               "%.3f" % chi2[i], int(not keep[i]), int(unit[i]),
                               int(uw[i]), "%.2f" % pw[i]))

    if a.confusion:
        print("CONFUSION  rows = unit from pw (wire rank)  cols = unit from geometry   det=%s" % a.det)
        for r in range(conf.shape[0]):
            print("  wire%-2d  " % r + "  ".join("%7d" % c for c in conf[r][:nunit]))
        # PDHD compares like with like (4 APAs both ways).  On PDVD the geometric
        # label is the DRIFT VOLUME, so fold the 8 wire-anodes into their volume
        # (anodes 0-3 bottom, 4-7 top; protodunevd/clus.jsonnet:63-72) before
        # scoring -- comparing an 8-valued row against a 2-valued column on the
        # diagonal would score a correct labelling as 50 % wrong.
        agree = 0
        for r in range(conf.shape[0]):
            for c in range(nunit):
                fold = r if a.det == "pdhd" else (0 if r < 4 else 1)
                if fold == c:
                    agree += int(conf[r, c])
        print("  agreement %d/%d = %.1f %%%s" % (agree, conf.sum(), 100.0 * agree / max(conf.sum(), 1),
              "" if a.det == "pdhd" else "  (wire anode folded to drift volume)"))

    # ---- per-track TSV ----------------------------------------------------
    TCOLS = (["det", "event", "block", "cluster", "status", "npts", "nkept", "ngood",
              "length", "len_kept", "pts_per_cm", "kink", "exit_L", "left_L", "has_left",
              "f_low", "rrmin", "rrmax", "reach", "nbins", "contrast",
              "k_muon", "shape_muon", "k_proton", "shape_proton", "best", "med_chi2",
              "doc55", "complete"] + ["n_u%d" % u for u in range(nunit)])
    with open(a.out + "_tracks.tsv", "w") as fh:
        fh.write("# doc pdvd/50 r2 d51_dqdx_rr_apa.py det=%s ref=%s status=%s max_abs_x=%g "
                 "low_thr=%.0f (%.2f x plateau %.1f) complete_max_flow=%.2f files=%d\n"
                 % (a.det, a.ref, a.status, a.max_abs_x, low_thr, a.low_frac, plateau, a.complete_max_flow, len(a.roots)))
        fh.write("\t".join(TCOLS) + "\t" + "\t".join("med_%d_%d" % b for b in BINS)
                 + "\t" + "\t".join("n_%d_%d" % b for b in BINS) + "\n")
        for tk in tracks:
            fh.write("\t".join(("%.4f" % tk[c]) if isinstance(tk[c], float) else str(tk[c]) for c in TCOLS)
                     + "\t" + "\t".join("%.0f" % m if np.isfinite(m) else "nan" for m in tk["meds"])
                     + "\t" + "\t".join(str(c) for c in tk["cnt"]) + "\n")
    with open(a.out + "_points.tsv", "w") as fh:
        fh.write("det\tevent\tblock\tstatus\ti\trr_kink\trr_end\tdqdx\tdx\tx\ty\tz\treduced_chi2\tpast_kink\tunit\tunit_wire\tpw\n")
        for p in points:
            fh.write("\t".join(str(v) for v in p) + "\n")

    # ---- tier definitions, doc 50's, unchanged ----------------------------
    tset = {
        "all_kept":      lambda tk: True,
        "contrast_ge2":  lambda tk: tk["contrast"] >= 2.0,
        "doc55_cuts":    lambda tk: bool(tk["doc55"]),
        "doc55_muon":    lambda tk: tk["doc55"] and 0.85 <= tk["k_muon"] <= 1.25,
        "complete":      lambda tk: bool(tk["complete"]),
        "complete_bragg": lambda tk: tk["complete"] and tk["contrast"] >= 2.0,
        "complete_muonshape": lambda tk: tk["complete"] and tk["best"] == "muon",
        "complete_protonshape": lambda tk: tk["complete"] and tk["best"] == "proton",
    }
    pidx = {}
    for j, p in enumerate(points):
        pidx.setdefault((p[1], p[2]), []).append(j)

    def tier_points(tks):
        """live, pre-kink points of a tier, as (rr, dqdx, unit)."""
        keys = {(tk["event"], tk["block"]) for tk in tks}
        idx = [j for kk in keys for j in pidx.get(kk, [])]
        sel = [j for j in idx if points[j][13] == 0 and points[j][7] != "nan"]
        rr = np.array([float(points[j][5]) for j in sel])
        v = np.array([float(points[j][7]) for j in sel])
        u = np.array([int(points[j][14]) for j in sel])
        if len(v) == 0:
            return rr, v, u
        ok = (v > 0) & (rr >= 0)
        return rr[ok], v[ok], u[ok]

    with open(a.out + "_summary.tsv", "w") as fh:
        fh.write("# per tier: ntracks, npoints, k_pop (vs MuonDeDx), chi2 over populated bins (3%% floor),\n"
                 "# then per-bin median(dqdx/(k_pop*muon ref)), per-bin err, per-bin npoints.\n"
                 "# pts_per_cm_med and reach_frac are the round-2 additions: read f_low_med WITH\n"
                 "# pts_per_cm_med (deletion vs recovery), and reach_frac attributes a tier collapse.\n")
        fh.write("tier\tntracks\tnpoints\tk_pop\tchi2\tnbins\tk_med\tk_rms\tcontrast_med\tf_low_med\t"
                 "pts_per_cm_med\treach_frac\thas_left_frac\t"
                 + "\t".join("r_%d_%d" % b for b in BINS) + "\t" + "\t".join("e_%d_%d" % b for b in BINS)
                 + "\t" + "\t".join("n_%d_%d" % b for b in BINS) + "\n")
        for name, sel in tset.items():
            tks = [tk for tk in tracks if sel(tk)]
            rr, v, _u = tier_points(tks)
            if len(v) == 0:
                fh.write("%s\t%d\t0\n" % (name, len(tks))); continue
            k_pop, chi2, nb, ratios, errs, ns = bin_table(rr, v, refs["muon"])
            ks = np.array([tk["k_muon"] for tk in tks]); ks = ks[np.isfinite(ks)]
            cs = np.array([tk["contrast"] for tk in tks]); cs = cs[np.isfinite(cs)]
            fs = np.array([tk["f_low"] for tk in tks]); fs = fs[np.isfinite(fs)]
            ds = np.array([tk["pts_per_cm"] for tk in tks]); ds = ds[np.isfinite(ds)]
            fh.write("%s\t%d\t%d\t%.4f\t%.2f\t%d\t%.4f\t%.4f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t"
                     % (name, len(tks), len(v), k_pop, chi2, nb,
                        np.median(ks) if len(ks) else np.nan, np.std(ks) if len(ks) else np.nan,
                        np.median(cs) if len(cs) else np.nan, np.median(fs) if len(fs) else np.nan,
                        np.median(ds) if len(ds) else np.nan,
                        np.mean([tk["reach"] for tk in tks]) if tks else np.nan,
                        np.mean([tk["has_left"] for tk in tks]) if tks else np.nan)
                     + "\t".join("%.4f" % r for r in ratios) + "\t" + "\t".join("%.4f" % e for e in errs)
                     + "\t" + "\t".join(str(x) for x in ns) + "\n")

    # ---- per-readout-unit TSV: the owner's APA0 separation ----------------
    with open(a.out + "_apa.tsv", "w") as fh:
        fh.write("# doc pdvd/50 r2: dQ/dx vs rr per READOUT-UNIT SELECTION, per tier.\n"
                 "# Selections are on POINTS, so units are NOT disjoint at track level -- a track\n"
                 "# crossing APAs contributes to more than one row.  ntracks counts tracks with at\n"
                 "# least one point in the selection.\n"
                 "# plateau_ratio is median(dqdx / muon table) over rr in [%g, %g) with NO free\n"
                 "# scale; plateau_ratio_hi is the same over points above 0.5 x plateau only\n"
                 "# (doc 50 sec 4.2's 'the surviving points are right to 5 %%' test).\n"
                 "# band_* are ABSOLUTE plateau point counts by dqdx/table, not fractions.\n"
                 % PLATEAU_RR)
        fh.write("tier\tsel\tunits\tntracks\tnpoints\tk_pop\tchi2\tnbins\tplateau_ratio\tplateau_npts\t"
                 "plateau_ratio_hi\tplateau_npts_hi\tkilled_frac\t"
                 + "\t".join("band_" + b for b in BANDNAME) + "\t"
                 + "\t".join("r_%d_%d" % b for b in BINS) + "\t"
                 + "\t".join("e_%d_%d" % b for b in BINS) + "\t"
                 + "\t".join("n_%d_%d" % b for b in BINS) + "\n")
        for tname in ("all_kept", "complete", "complete_bragg"):
            tks = [tk for tk in tracks if tset[tname](tk)]
            rr, v, u = tier_points(tks)
            for sname, units in selections(a.det):
                if len(v) == 0:
                    continue
                m = np.isin(u, units)
                if m.sum() == 0:
                    continue
                rrs, vs = rr[m], v[m]
                ntrk = sum(1 for tk in tks if any(tk.get("n_u%d" % uu, 0) > 0 for uu in units))
                k_pop, chi2, nb, ratios, errs, ns = bin_table(rrs, vs, refs["muon"])
                pm = (rrs >= PLATEAU_RR[0]) & (rrs < PLATEAU_RR[1])
                ref_p = refs["muon"](rrs[pm])
                ratio_p = float(np.median(vs[pm] / ref_p)) if pm.sum() else float("nan")
                hi = pm & (vs > 0.5 * plateau)
                ratio_hi = float(np.median(vs[hi] / refs["muon"](rrs[hi]))) if hi.sum() else float("nan")
                killed = 1.0 - hi.sum() / pm.sum() if pm.sum() else float("nan")
                bc = []
                if pm.sum():
                    frac = vs[pm] / ref_p
                    for lo, hi_b in BANDS:
                        bc.append(int(((frac >= lo) & (frac < hi_b)).sum()))
                else:
                    bc = [0] * len(BANDS)
                fh.write("%s\t%s\t%s\t%d\t%d\t%.4f\t%.2f\t%d\t%.4f\t%d\t%.4f\t%d\t%.4f\t"
                         % (tname, sname, "+".join(str(x) for x in units), ntrk, len(vs),
                            k_pop, chi2, nb, ratio_p, int(pm.sum()), ratio_hi, int(hi.sum()), killed)
                         + "\t".join(str(c) for c in bc) + "\t"
                         + "\t".join("%.4f" % r for r in ratios) + "\t"
                         + "\t".join("%.4f" % e for e in errs) + "\t"
                         + "\t".join(str(x) for x in ns) + "\n")

    print("%s: %d passes (status %s) from %d files -> %s_{tracks,points,summary,apa}.tsv"
          % (a.det, len(tracks), a.status, len(a.roots), a.out))
    for line in open(a.out + "_summary.tsv"):
        if not line.startswith("#") :
            print("  " + "\t".join(line.split("\t")[:13]).rstrip())
    print("  unit labels: " + "; ".join("%d=%s" % (k, w) for k, w in sorted(labels.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
