#!/usr/bin/env python3
"""doc pdhd/10 -- the four figures.

(a) per-point wire coverage per APA per plane (from d10_coverage.py's summary)
(b) charge per cm at each stage, per APA, both runs (from d10_tube_census.py)
(c) hit fraction vs collection wire index, APA2 vs APA3
(d) hit fraction vs y, APA2 vs APA3
Panels (c) and (d) are recomputed here from tracking-stm.root so the figure has
no hidden intermediate.
"""
import argparse, glob, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import uproot

BASE = (0, 3200, 6400); PER = (800, 800, 960)
COL = {0: "#d62728", 1: "#1f77b4", 2: "#2ca02c", 3: "#9467bd"}


def scan(files, tol=2):
    out = {a: dict(hit=[], wire=[], y=[]) for a in range(4)}
    for fn in files:
        try:
            f = uproot.open(fn)
            r = f["T_rec_charge"].arrays(["y", "pw", "pt", "ndf", "status"], library="np")
            pj = f["T_proj_data"].arrays(["cluster_id", "channel", "time_slice", "charge"],
                                         library="np")
        except Exception:
            continue
        if not len(pj["cluster_id"]):
            continue
        cid = list(pj["cluster_id"][0])
        blocks = r["ndf"].astype(np.int64)
        for b in np.unique(blocks):
            m = blocks == b
            if m.sum() < 20 or int(r["status"][m][0]) != 0 or int(b) not in cid:
                continue
            i = cid.index(int(b))
            ch = np.asarray(pj["channel"][0][i]); ts = np.asarray(pj["time_slice"][0][i])
            q = np.asarray(pj["charge"][0][i])
            liv = (q > 0) & (ch >= BASE[2])
            cells = set(zip(ch[liv].tolist(), ts[liv].tolist()))
            w = np.floor(r["pw"][m]).astype(np.int64)
            tt = np.rint(r["pt"][m]).astype(np.int64)
            apa = (w - BASE[2]) // PER[2]
            for k in range(len(w)):
                a = int(apa[k])
                if a < 0 or a > 3:
                    continue
                h = any((int(w[k]), int(tt[k] + d)) in cells for d in range(-tol, tol + 1))
                out[a]["hit"].append(h)
                out[a]["wire"].append(int(w[k]) - BASE[2] - a * PER[2])
                out[a]["y"].append(float(r["y"][m][k]))
    return out


def profile(v, h, edges):
    xs, ys, ns = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (v >= lo) & (v < hi)
        if s.sum() < 30:
            continue
        xs.append(0.5 * (lo + hi)); ys.append(h[s].mean()); ns.append(int(s.sum()))
    return np.array(xs), np.array(ys), np.array(ns)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cov-summary", required=True)
    ap.add_argument("--tube", nargs="+", required=True,
                    help="run:label:summary.tsv triples, e.g. 028084:028084:tube_028084_summary.tsv")
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    files = []
    for pat in args.files:
        files.extend(sorted(glob.glob(pat)))
    D = scan(files)

    fig, ax = plt.subplots(2, 2, figsize=(13.5, 9.5))

    # (a) coverage per APA per plane
    cov = {}
    for line in open(args.cov_summary):
        p = line.split("\t")
        if p[0] == "apa" or len(p) < 6:
            continue
        if p[2] != "ALL":
            continue
        cov[(int(p[0]), p[1])] = float(p[5])
    a0 = ax[0, 0]
    wdt = 0.25
    for j, pl in enumerate("UVW"):
        a0.bar(np.arange(4) + (j - 1) * wdt, [cov.get((a, pl), 0) for a in range(4)],
               wdt, label="plane %s" % pl)
    a0.set_xticks(range(4)); a0.set_xticklabels(["APA0\nx<0", "APA1\nx>0", "APA2\nx<0", "APA3\nx>0"])
    a0.set_ylabel("fraction of fit points whose own wire\ncarries charge at its own time")
    a0.set_title("(a) per-point coverage — APA2 fails on all three planes equally")
    a0.axhline(0.5, color="0.6", lw=0.8, ls=":")
    a0.legend(fontsize=8); a0.set_ylim(0, 1.0); a0.grid(axis="y", alpha=0.3)

    # (b) charge per cm at each stage
    a1 = ax[0, 1]
    stages = ["SP frame", "ctpc", "fit"]
    off = np.linspace(-0.28, 0.28, 3)
    marks = ["o", "s", "^"]
    for t, spec in enumerate(args.tube):
        run, lab, path = spec.split(":", 2)
        vals = {}
        for line in open(path):
            p = line.split()
            if p[0] == "apa":
                continue
            # the summary gained two ADC columns when --adc is used; key off
            # the field count so both flavours read correctly
            k = 5 if len(p) >= 10 else 3
            vals[int(p[0])] = [float(p[k]), float(p[k + 1]), float(p[k + 2])]
        for k in range(3):
            a1.plot(np.arange(4) + off[k] + (t - 0.5) * 0.06,
                    [vals.get(a, [np.nan] * 3)[k] / 1e3 for a in range(4)],
                    marks[k], ms=8 if t == 0 else 5,
                    mfc="none" if t else None, color="C%d" % k,
                    label="%s (%s)" % (stages[k], lab))
    a1.set_xticks(range(4)); a1.set_xticklabels(["APA0", "APA1", "APA2", "APA3"])
    a1.set_ylabel("charge per cm of 3-D track [ke/cm]")
    a1.set_title("(b) same muons, every stage — nothing is lost between the\n"
              "SP frame and the fit; APA2 already starts 0.6x low")
    a1.legend(fontsize=7, ncol=2); a1.grid(alpha=0.3); a1.set_ylim(bottom=0)

    # (c) hit fraction vs wire
    a2 = ax[1, 0]
    for a in (2, 3):
        wv = np.array(D[a]["wire"]); hv = np.array(D[a]["hit"], float)
        if not len(wv):
            continue
        x, y, n = profile(wv, hv, np.arange(0, 961, 48))
        a2.plot(x, y, "o-", color=COL[a], label="APA%d (n=%d)" % (a, len(wv)))
    a2.set_xlabel("collection wire index within the anode's 960-wire block")
    a2.set_ylabel("hit fraction")
    a2.set_title("(c) APA2 collapses in its last 96 wires; APA3 is flat")
    a2.legend(fontsize=8); a2.grid(alpha=0.3); a2.set_ylim(0, 1.0)

    # (d) where the fit points are, in y -- APA2 piles them into the weak band
    a3 = ax[1, 1]
    edges = np.arange(0, 660, 60)
    for a in range(4):
        yv = np.array(D[a]["y"]); hv = np.array(D[a]["hit"], float)
        if not len(yv):
            continue
        x, y, n = profile(yv, hv, edges)
        a3.plot(x, y, "o-", color=COL[a], label="APA%d hit (n=%d)" % (a, len(yv)))
    a3.set_xlabel("y [cm]")
    a3.set_ylabel("hit fraction (lines)")
    a3.set_ylim(0, 1.05)
    for a in range(4):
        yv = np.array(D[a]["y"])
        if not len(yv):
            continue
        a3.annotate("APA%d: %d pts at y<100" % (a, int((yv < 100).sum())),
                    xy=(0.03, 0.30 - 0.06 * a), xycoords="axes fraction",
                    fontsize=7, color=COL[a])
    n2 = int((np.array(D[2]["y"]) < 100).sum()); n3 = int((np.array(D[3]["y"]) < 100).sum())
    a3.set_title("(d) every APA is weak at low y — APA2 puts %d of its %d\n"
                 "points there, against APA3's %d of %d"
                 % (n2, len(D[2]["y"]), n3, len(D[3]["y"])))
    a3.legend(fontsize=7, loc="lower right"); a3.grid(alpha=0.3)

    fig.suptitle("doc pdhd/10 — the APA2 deficit is a trajectory problem, not a charge problem",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(args.out, dpi=110)
    print("wrote", args.out)

    # dump the two profiles beside the figure
    base = os.path.splitext(args.out)[0]
    with open(base + "_profiles.tsv", "w") as fh:
        fh.write("apa\tvar\tbin_centre\thit_fraction\tnpoints\n")
        for a in range(4):
            for var, edges in (("wire", np.arange(0, 961, 48)), ("y", np.arange(0, 660, 60))):
                v = np.array(D[a][var]); hv = np.array(D[a]["hit"], float)
                if not len(v):
                    continue
                x, y, n = profile(v, hv, edges)
                for xi, yi, ni in zip(x, y, n):
                    fh.write("%d\t%s\t%.1f\t%.4f\t%d\n" % (a, var, xi, yi, ni))
    print("wrote", base + "_profiles.tsv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
