#!/usr/bin/env python3
"""doc pdvd/50 -- dQ/dx vs residual range, PDHD and PDVD through one code path,
with the CHARGE-COMPLETENESS tier and the proton pools doc 42 did not have.

Fork BY DUPLICATION of doc pdvd/42's d42_dqdx_rr.py (that file and its PDHD
fork are untouched).  What is added over doc 42:

  * f_low, the per-track fraction of pre-kink live points below
    --low-frac x (the detector's own muon plateau).  Doc 42's four tiers hide
    the single biggest PDHD/PDVD difference: the two detectors put the SAME
    scale on charge-complete tracks (k 0.89 vs 0.94) and differ only in how
    many of their fit points carry full charge (median f_low 0.26 vs 0.04).
    The "complete" tier is therefore the like-for-like cross-detector sample,
    and on PDHD it is 49 tracks where the doc-55 five cuts leave 1.
  * both particle hypotheses: a free scale is removed per hypothesis and the
    SHAPE rms decides muon vs proton.  Shape is scale-free, so unlike doc 55's
    k-window assignment (k_muon ~ 1.9 => proton) it does not presuppose the
    charge scale it is later used to measure -- see the circularity paragraph
    in sbnd_xin/dqdx_rr_sample/collect_proton_sample.py.
  * --status, so the tagger's own status==5 ("proton endpoint",
    TaggerCheckSTM.cxx detect_proton) passes can be extracted.  persist_stm_fit
    is unconditional on the verdict, so those passes are already on disk.

Decoding is doc 42's, unchanged (PDHD uses PdvdMagnifyTrackingVisitor verbatim,
so the schema is identical on both detectors):

    dQ/dx [e/cm] = (q - dQdx_offset)/dQdx_scale / nq      nq = dx in cm
    rr already in cm ; two passes per cluster, block = cluster*10 + pass

Michel/leftover removal is the tagger's own kink, as in doc 42: when left_L > 0
the points past kink_num are dropped and rr is re-anchored there.

Usage:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
  python3 ../pdvd/docs/nf_sp_img_clus/scripts/d50_dqdx_rr_cross.py --det pdhd \
      --ref stm/pdhd_ref_dqdx.json --max-abs-x 1e9 \
      --out ANA/pdhd work/*_d30hpost/tracking-stm.root
Writes <out>_{tracks,points,summary}.tsv.
"""
import argparse, json, os, sys
import numpy as np
import uproot

BINS = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 60)]
SYS_FLOOR = 0.03
HYPS = ["muon", "proton"]
KEYS = {"muon": "MuonDeDx", "proton": "ProtonDeDx"}


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--det", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-abs-x", type=float, default=1e9)
    ap.add_argument("--min-npts", type=int, default=10)
    ap.add_argument("--status", default="0", help="comma list of T_stm_pass status codes to keep (0 = accepted STM, 5 = proton endpoint)")
    ap.add_argument("--low-frac", type=float, default=0.40, help="a point is charge-DEFICIENT below this fraction of the muon plateau")
    ap.add_argument("--complete-max-flow", type=float, default=0.05, help="a track is charge-COMPLETE below this f_low")
    a = ap.parse_args()

    refs = {h: load_ref(a.ref, KEYS[h]) for h in HYPS}
    plateau = float(refs["muon"](np.array([59.5]))[0])
    low_thr = a.low_frac * plateau
    want = {int(s) for s in a.status.split(",")}

    tracks, points = [], []
    for path in a.roots:
        try:
            f = uproot.open(path)
            t = f["T_rec_charge"].arrays(["x", "y", "z", "q", "nq", "rr", "ndf", "status", "pass", "reduced_chi2"], library="np")
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
            with np.errstate(divide="ignore", invalid="ignore"):
                dqdx = np.where(dx > 0, dQ / dx, np.nan)
            dqdx = np.where(np.abs(x) > a.max_abs_x, np.nan, dqdx)
            kink, exL, lfL = pinfo.get(int(blk), (-1, float("nan"), 0.0))
            has_left = (lfL > 0) and (0 <= kink < n - 1)
            keep = np.ones(n, bool)
            if has_left:
                keep[kink + 1:] = False
                rr_k = rr_end - rr_end[kink]
            else:
                rr_k = rr_end.copy()
            rr_use = rr_k[keep]; v = dqdx[keep]
            good = np.isfinite(v) & (v > 0)                    # live points only
            f_low = float((v[good] < low_thr).mean()) if good.sum() else float("nan")

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
            doc55 = (n >= 40 and pop.sum() >= 6 and rrmin < 2.0 and rrmax >= 22.0
                     and contrast >= 2.0 and mchi2 <= 2.5 and hyp["muon"][1] <= 0.10)
            complete = (n >= 40 and pop.sum() >= 2 and np.isfinite(f_low) and f_low < a.complete_max_flow)
            tracks.append(dict(det=a.det, event=ev, block=int(blk), cluster=int(blk) // 10, status=st,
                               npts=n, nkept=int(keep.sum()), ngood=int(good.sum()),
                               length=float(rr_end.max()), kink=kink, exit_L=exL, left_L=lfL,
                               has_left=int(has_left), f_low=f_low, rrmin=rrmin, rrmax=rrmax,
                               nbins=int(pop.sum()), contrast=contrast,
                               k_muon=hyp["muon"][0], shape_muon=hyp["muon"][1],
                               k_proton=hyp["proton"][0], shape_proton=hyp["proton"][1],
                               best=best, med_chi2=mchi2, doc55=int(doc55), complete=int(complete),
                               meds=meds, cnt=cnt))
            for i in range(n):
                points.append((a.det, ev, int(blk), st, i, "%.2f" % rr_k[i], "%.2f" % rr_end[i],
                               "%.1f" % dqdx[i] if np.isfinite(dqdx[i]) else "nan",
                               "%.3f" % dx[i], "%.2f" % x[i], "%.2f" % t["y"][mk][i], "%.2f" % t["z"][mk][i],
                               "%.3f" % chi2[i], int(not keep[i])))

    TCOLS = ["det", "event", "block", "cluster", "status", "npts", "nkept", "ngood", "length", "kink",
             "exit_L", "left_L", "has_left", "f_low", "rrmin", "rrmax", "nbins", "contrast",
             "k_muon", "shape_muon", "k_proton", "shape_proton", "best", "med_chi2", "doc55", "complete"]
    with open(a.out + "_tracks.tsv", "w") as fh:
        fh.write("# doc pdvd/50 d50_dqdx_rr_cross.py det=%s ref=%s status=%s max_abs_x=%g "
                 "low_thr=%.0f (%.2f x plateau %.1f) complete_max_flow=%.2f files=%d\n"
                 % (a.det, a.ref, a.status, a.max_abs_x, low_thr, a.low_frac, plateau, a.complete_max_flow, len(a.roots)))
        fh.write("\t".join(TCOLS) + "\t" + "\t".join("med_%d_%d" % b for b in BINS)
                 + "\t" + "\t".join("n_%d_%d" % b for b in BINS) + "\n")
        for tk in tracks:
            fh.write("\t".join(("%.4f" % tk[c]) if isinstance(tk[c], float) else str(tk[c]) for c in TCOLS)
                     + "\t" + "\t".join("%.0f" % m if np.isfinite(m) else "nan" for m in tk["meds"])
                     + "\t" + "\t".join(str(c) for c in tk["cnt"]) + "\n")
    with open(a.out + "_points.tsv", "w") as fh:
        fh.write("det\tevent\tblock\tstatus\ti\trr_kink\trr_end\tdqdx\tdx\tx\ty\tz\treduced_chi2\tpast_kink\n")
        for p in points:
            fh.write("\t".join(str(v) for v in p) + "\n")

    # ---- population summary per tier -------------------------------------
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
    with open(a.out + "_summary.tsv", "w") as fh:
        fh.write("# per tier: ntracks, npoints, k_pop (vs MuonDeDx), chi2 over populated bins (3%% floor),\n"
                 "# then per-bin median(dqdx/(k_pop*muon ref)), per-bin err, per-bin npoints\n")
        fh.write("tier\tntracks\tnpoints\tk_pop\tchi2\tnbins\tk_med\tk_rms\tcontrast_med\tf_low_med\thas_left_frac\t"
                 + "\t".join("r_%d_%d" % b for b in BINS) + "\t" + "\t".join("e_%d_%d" % b for b in BINS)
                 + "\t" + "\t".join("n_%d_%d" % b for b in BINS) + "\n")
        for name, sel in tset.items():
            tks = [tk for tk in tracks if sel(tk)]
            keys = {(tk["event"], tk["block"]) for tk in tks}
            idx = [j for kk in keys for j in pidx.get(kk, [])]
            rr = np.array([float(points[j][5]) for j in idx if points[j][13] == 0 and points[j][7] != "nan"])
            v = np.array([float(points[j][7]) for j in idx if points[j][13] == 0 and points[j][7] != "nan"])
            if len(v) == 0:
                fh.write("%s\t%d\t0\n" % (name, len(tks))); continue
            ok = (v > 0) & (rr >= 0); rr, v = rr[ok], v[ok]
            k_pop = float(np.exp(np.median(np.log(v / refs["muon"](rr)))))
            ratios, errs, ns, chi2, nb = [], [], [], 0.0, 0
            for lo, hi in BINS:
                m = (rr >= lo) & (rr < hi)
                ns.append(int(m.sum()))
                if m.sum() < 5:
                    ratios.append(float("nan")); errs.append(float("nan")); continue
                r = v[m] / (k_pop * refs["muon"](rr[m]))
                med = float(np.median(r))
                err = float(1.2533 * 1.4826 * np.median(np.abs(r - med)) / np.sqrt(m.sum()))
                err = float(np.hypot(err, SYS_FLOOR * med))
                ratios.append(med); errs.append(err); chi2 += ((med - 1) / err) ** 2; nb += 1
            ks = np.array([tk["k_muon"] for tk in tks]); ks = ks[np.isfinite(ks)]
            cs = np.array([tk["contrast"] for tk in tks]); cs = cs[np.isfinite(cs)]
            fs = np.array([tk["f_low"] for tk in tks]); fs = fs[np.isfinite(fs)]
            fh.write("%s\t%d\t%d\t%.4f\t%.2f\t%d\t%.4f\t%.4f\t%.3f\t%.3f\t%.3f\t"
                     % (name, len(tks), len(v), k_pop, chi2, nb,
                        np.median(ks) if len(ks) else np.nan, np.std(ks) if len(ks) else np.nan,
                        np.median(cs) if len(cs) else np.nan, np.median(fs) if len(fs) else np.nan,
                        np.mean([tk["has_left"] for tk in tks]) if tks else np.nan)
                     + "\t".join("%.4f" % r for r in ratios) + "\t" + "\t".join("%.4f" % e for e in errs)
                     + "\t" + "\t".join(str(x) for x in ns) + "\n")
    print("%s: %d passes (status %s) from %d files -> %s_{tracks,points,summary}.tsv"
          % (a.det, len(tracks), a.status, len(a.roots), a.out))
    for line in open(a.out + "_summary.tsv"):
        if not line.startswith("#"):
            print("  " + "\t".join(line.split("\t")[:11]).rstrip())


if __name__ == "__main__":
    sys.exit(main())
