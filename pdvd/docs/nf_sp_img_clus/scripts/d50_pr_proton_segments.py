#!/usr/bin/env python3
"""doc pdvd/50 -- the PR chain's own proton-tagged segments, as dQ/dx vs residual range.

The STM fit (tracking-stm.root) only fits STM *candidate* main clusters, so a
short proton stub is structurally absent from it.  The neutrino/PR track fitting
(tracking-pr.root, written by the -nu chain) fits every segment of every
PR-graph cluster and stamps each with `particle_id` (PDG).  This script pulls
the segments the chain itself called protons (particle_id == 2212) and writes
their per-point dQ/dx vs rr, so the proton hypothesis can be tested against the
SAME free scale the muon sample fixes -- no per-track refit, which is what makes
the test non-circular.

Decoding as in doc 42/50:  dQ/dx = (q - dQdx_offset)/dQdx_scale / nq  [e/cm].
Segment key = real_cluster_id*100000 + sub_cluster_id.

Usage:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
  python3 pdvd/docs/nf_sp_img_clus/scripts/d50_pr_proton_segments.py \
      --det pdhd --out ANA/d50_pdhd_pr_proton pdhd/work/*_d30hnupost/tracking-pr.root
Writes <out>_points.tsv and <out>_index.tsv.
"""
import argparse, os, sys
import numpy as np
import uproot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--det", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdg", type=int, default=2212)
    ap.add_argument("--min-npts", type=int, default=6)
    a = ap.parse_args()

    idx, pts = [], []
    for fp in a.roots:
        try:
            f = uproot.open(fp)
            t = f["T_rec_charge"].arrays(library="np")
            tr = f["Trun"].arrays(["dQdx_scale", "dQdx_offset"], library="np")
        except Exception as ex:
            print("skip", fp, ex, file=sys.stderr); continue
        sc, of = float(tr["dQdx_scale"][0]), float(tr["dQdx_offset"][0])
        ev = os.path.basename(os.path.dirname(fp))
        key = t["real_cluster_id"] * 100000 + t["sub_cluster_id"]
        for kk in sorted(set(key.tolist())):
            m = key == kk
            if int(m.sum()) < a.min_npts:
                continue
            if int(np.median(t["particle_id"][m])) != a.pdg:
                continue
            rr = t["rr"][m]; dq = (t["q"][m] - of) / sc; dx = t["nq"][m]
            with np.errstate(divide="ignore", invalid="ignore"):
                v = np.where(dx > 0, dq / dx, np.nan)
            g = np.isfinite(v) & (v > 0) & (rr >= 0)
            if g.sum() < a.min_npts:
                continue
            idx.append((a.det, ev, int(kk), int(m.sum()), int(g.sum()),
                        float(np.nanmax(rr)), float(np.median(v[g]))))
            o = np.argsort(rr[g])
            for r, val, xx, yy, zz, dd in zip(rr[g][o], v[g][o], t["x"][m][g][o], t["y"][m][g][o],
                                              t["z"][m][g][o], dx[g][o]):
                pts.append((a.det, ev, int(kk), "%.2f" % r, "%.1f" % val,
                            "%.2f" % xx, "%.2f" % yy, "%.2f" % zz, "%.3f" % dd))

    with open(a.out + "_index.tsv", "w") as fh:
        fh.write("# doc pdvd/50 d50_pr_proton_segments.py det=%s pdg=%d files=%d\n" % (a.det, a.pdg, len(a.roots)))
        fh.write("det\tevent\tseg\tnpts\tngood\trange_cm\tmed_dqdx\n")
        for r in idx:
            fh.write("\t".join(str(x) for x in r) + "\n")
    with open(a.out + "_points.tsv", "w") as fh:
        fh.write("det\tevent\tseg\trr\tdqdx\tx\ty\tz\tdx\n")
        for p in pts:
            fh.write("\t".join(str(x) for x in p) + "\n")
    print("%s: %d segments with particle_id==%d, %d points -> %s_{index,points}.tsv"
          % (a.det, len(idx), a.pdg, len(pts), a.out))
    for r in idx:
        print("   %s seg %d  npts %d  range %.1f cm  median dQ/dx %.0f" % (r[1], r[2], r[3], r[5], r[6]))


if __name__ == "__main__":
    sys.exit(main())
