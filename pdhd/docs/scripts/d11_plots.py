#!/usr/bin/env python3
"""doc pdhd/11 figure -- the owner's cluster 126, before and after.

Panels (a) and (b): the y-z and y-x projections of ONE object, with the three
Bee layers the owner compared -- `clustering` (grey, the 3-D image), the Steiner
graph (blue) and `stm_fit` (red) -- overlaid, off arm and on arm.  Panel (c):
the per-point distance from the fit to the nearest charge, along the track.
Panel (d): the population, blocks binned by that distance, both arms.

Repro:
    ./d11_plots.py --off ../../work/028084_9_d11off --on ../../work/028084_9_d11on \
                   --cluster 126 --blocks ../figs/11_fit_image_blocks.tsv \
                   --out ../figs/11_cluster126.png
"""
import argparse, csv, json, os, zipfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import uproot
from scipy.spatial import cKDTree


def load(wd, cid):
    z = zipfile.ZipFile(os.path.join(wd, "mabc-pr.zip"))
    def layer(name, only=None):
        n = [x for x in z.namelist() if x.endswith("-%s-global.json" % name)]
        if not n:
            return np.zeros((0, 3))
        j = json.loads(z.read(n[0]))
        P = np.stack([j["x"], j["y"], j["z"]], 1)
        if only is None:
            return P
        return P[np.array(j["cluster_id"]) == only]
    r = uproot.open(os.path.join(wd, "tracking-stm.root"))["T_rec_charge"].arrays(
        ["x", "y", "z", "ndf"], library="np")
    m = r["ndf"].astype(np.int64) // 10 == cid
    F = np.stack([r["x"][m], r["y"][m], r["z"][m]], 1)
    return layer("clustering", cid), layer("steiner_graph", cid), F, cKDTree(layer("clustering"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", required=True)
    ap.add_argument("--on", required=True)
    ap.add_argument("--cluster", type=int, required=True)
    ap.add_argument("--blocks")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    fig, ax = plt.subplots(2, 2, figsize=(13.5, 9.5))
    arms = [("production (knob OFF)", a.off, 0), ("traj_final_fill_charge_test = 1", a.on, 1)]
    for title, wd, col in arms:
        I, S, F, tall = load(wd, a.cluster)
        for row, (u, v, ul, vl) in enumerate(((2, 1, "z [cm]", "y [cm]"), (0, 1, "x [cm]", "y [cm]"))):
            p = ax[row][col]
            if len(I):
                p.plot(I[:, u], I[:, v], ".", ms=1.4, color="0.72", label="clustering (3-D image)")
            if len(S):
                p.plot(S[:, u], S[:, v], ".", ms=1.0, color="#2a6fb5", alpha=.55, label="steiner_graph")
            if len(F):
                p.plot(F[:, u], F[:, v], "-", lw=1.9, color="#c62828", label="stm_fit")
            p.set_xlabel(ul); p.set_ylabel(vl)
            if row == 0:
                p.set_title("%s\ncluster %d, %d fitted points" % (title, a.cluster, len(F)), fontsize=10)
            p.grid(alpha=.25)
            if row == 0 and col == 0:
                p.legend(markerscale=6, fontsize=8, loc="best")
    fig.suptitle("doc pdhd/11 -- PDHD 028084 evt 9: the STM fit against the image it was fitted to",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(a.out, dpi=130)
    print("wrote", a.out)

    if a.blocks:
        rows = list(csv.DictReader((l for l in open(a.blocks) if not l.startswith("#")), delimiter="\t"))
        fig2, p = plt.subplots(1, 2, figsize=(11, 4.2))
        bins = np.logspace(-1.4, 1.6, 34)
        for arm, c in (("OFF", "#c62828"), ("ON", "#2a6fb5")):
            med = np.array([float(r["med"]) for r in rows if r["arm"] == arm])
            neg = np.array([float(r["negq"]) for r in rows if r["arm"] == arm])
            p[0].hist(np.clip(med, bins[0], bins[-1]), bins=bins, histtype="step", lw=1.8,
                      color=c, label="%s  (n=%d, %.1f%% > 3 cm)" % (arm, len(med), 100 * (med > 3).mean()))
            p[1].hist(neg, bins=np.linspace(0, 1, 26), histtype="step", lw=1.8, color=c,
                      label="%s  mean %.3f" % (arm, neg.mean()))
        p[0].set_xscale("log"); p[0].axvline(3, color="k", ls=":", lw=1)
        p[0].set_xlabel("median distance from fit point to nearest charge [cm]")
        p[0].set_ylabel("blocks"); p[0].legend(fontsize=8); p[0].grid(alpha=.25)
        p[1].set_xlabel("fraction of the block's fitted points with dQ/dx < 0")
        p[1].set_ylabel("blocks"); p[1].legend(fontsize=8); p[1].grid(alpha=.25)
        fig2.suptitle("doc pdhd/11 -- PDHD run 028084, 31 events, all accepted and rejected STM passes",
                      fontsize=11)
        fig2.tight_layout(rect=[0, 0, 1, 0.94])
        o2 = a.out.replace(".png", "_population.png")
        fig2.savefig(o2, dpi=130)
        print("wrote", o2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
