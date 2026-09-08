#!/usr/bin/env python3
"""doc pdvd/50 round 2 -- the two figures: the APA-separated dQ/dx-vs-rr
comparison the owner asked for, and the chain before/after anatomy.

Consumes only d51_dqdx_rr_apa.py's <prefix>_{tracks,points,apa}.tsv and the two
production reference tables, so both figures regenerate from the doc's Repro
block.

  51_dqdx_rr_apa.png       (a) dQ/dx vs rr, PDHD split by readout unit against
                               PDHD's own Modified-Box muon curve, PDVD beside
                               it, each with one free scale k;
                           (b) plateau dQ/dx / table per unit, NO free scale;
                           (c) ABSOLUTE plateau point counts in the five
                               expectation bands, per unit, old chain vs new --
                               the deletion-vs-recovery read;
                           (d) the same for PDVD's two drift volumes.

  51_chain_before_after.png (a) f_low and (b) pts_per_cm per arm -- they must be
                               read together (feedback_matched_population_metric_bias);
                           (c) the tier ladder; (d) the reach fraction, which
                               attributes a tier collapse to a trimmed stopping end.

Usage:
  python3 d51_apa_plots.py --ana ANA --figs pdvd/docs/nf_sp_img_clus/figs \
      --pdhd-old gate_pdhd_d30hpost --pdhd-fit0 d51_pdhd_fit0 --pdhd-new d51_pdhd_stm \
      --pdvd-old gate_pdvd_d42fit --pdvd-fit0 d51_pdvd_fit0 --pdvd-new d51_pdvd_stm
"""
import argparse, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BINS = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 60)]
CEN = np.array([(a + b) / 2 for a, b in BINS])
BANDNAME = ["<0.2", "0.2-0.5", "0.5-0.8", "0.8-1.2", ">1.2"]
BANDCOL = ["#b2182b", "#ef8a62", "#f7f7f7", "#67a9cf", "#2166ac"]
REF = {"pdhd": ("pdhd/stm/pdhd_ref_dqdx.json", 0.4959),
       "pdvd": ("pdvd/stm/pdvd_ref_dqdx_045.json", 0.45)}
ROOT = "/nfs/data/1/xqian/toolkit-dev/wcp-porting-img"


def load_ref(det, key="MuonDeDx"):
    t = json.load(open(os.path.join(ROOT, REF[det][0])))[key]
    x = t["start"] + t["step"] * np.arange(len(t["values"]))
    y = np.asarray(t["values"], float)
    return lambda rr: np.interp(rr, x, y)


def read_tsv(path):
    rows, hdr = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f; continue
            if len(f) < 2:
                continue
            rows.append(dict(zip(hdr, f)))
    return rows


def fnum(d, k):
    try:
        return float(d[k])
    except (KeyError, ValueError, TypeError):
        return float("nan")


def apa_row(rows, tier, sel):
    return next((r for r in rows if r["tier"] == tier and r["sel"] == sel), None)


def bins_from(row):
    r = np.array([fnum(row, "r_%d_%d" % b) for b in BINS])
    e = np.array([fnum(row, "e_%d_%d" % b) for b in BINS])
    n = np.array([fnum(row, "n_%d_%d" % b) for b in BINS])
    return r, e, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ana", required=True)
    ap.add_argument("--figs", required=True)
    for d in ("pdhd", "pdvd"):
        for a in ("old", "fit0", "new"):
            ap.add_argument("--%s-%s" % (d, a), required=True)
    ap.add_argument("--tier", default="complete_bragg")
    ap.add_argument("--mid-label-pdhd", default="PDHD mid",
                    help="what the --pdhd-fit0 arm isolates, for the legends")
    ap.add_argument("--mid-label-pdvd", default="PDVD mid",
                    help="what the --pdvd-fit0 arm isolates, for the legends")
    ap.add_argument("--apa-tier", default="all_kept")
    a = ap.parse_args()
    P = lambda name: os.path.join(a.ana, name)
    arms = {(d, w): getattr(a, "%s_%s" % (d, w)) for d in ("pdhd", "pdvd") for w in ("old", "fit0", "new")}
    apa = {k: read_tsv(P(v + "_apa.tsv")) for k, v in arms.items()}
    trk = {k: read_tsv(P(v + "_tracks.tsv")) for k, v in arms.items()}

    # ================= figure 1: the APA separation ======================
    fig = plt.figure(figsize=(15, 10.5))
    gs = fig.add_gridspec(2, 2, hspace=0.30, wspace=0.22)

    # (a) dQ/dx vs rr per selection, clean tier, one free k each
    ax = fig.add_subplot(gs[0, 0])
    curves = [("pdhd", "all", "PDHD all APAs", "k", "o"),
              ("pdhd", "noAPA0", "PDHD excl. APA0", "#2166ac", "s"),
              ("pdhd", "APA0", "PDHD APA0 only", "#b2182b", "^"),
              ("pdvd", "all", "PDVD", "#1a9850", "D")]
    for det, sel, lab, col, mk in curves:
        row = apa_row(apa[(det, "new")], a.tier, sel)
        if row is None:
            continue
        r, e, n = bins_from(row)
        # 20, not 5: doc 50 sec 5 warns the lowest rr bins are thin, and a
        # per-APA curve drawn through 3-point bins is noise with error bars.
        m = np.isfinite(r) & (n >= 20)
        ax.errorbar(CEN[m], r[m], yerr=e[m], color=col, marker=mk, ms=5, lw=1.4,
                    capsize=2, label="%s  k=%.3f, n=%d" % (lab, fnum(row, "k_pop"), int(fnum(row, "npoints"))))
    ax.axhline(1.0, color="0.4", lw=1, ls="--")
    ax.set_xscale("log"); ax.set_xlabel("residual range [cm]")
    ax.set_ylabel("median dQ/dx / (k x own muon table)")
    ax.set_title("(a) new chain, %s tier: each against its OWN Modified-Box muon curve" % a.tier, fontsize=10)
    ax.set_ylim(0.80, 1.30)
    ax.text(0.02, 0.03, "bins with < 20 points are not drawn: APA0 alone contributes only\n"
                        "3 tracks / 351 points to this tier, so it has almost no curve to draw --\n"
                        "which is itself the answer to \"what does APA0 do here\".",
            transform=ax.transAxes, fontsize=7, va="bottom", color="0.25")
    ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=0.25)

    # (b) plateau ratio per unit, NO free scale, old vs new
    ax = fig.add_subplot(gs[0, 1])
    sels = ["APA0", "APA1", "APA2", "APA3"]
    w = 0.26
    for i, (which, col, lab) in enumerate([("old", "0.62", "old chain"),
                                           ("fit0", "#f4a582", a.mid_label_pdhd),
                                           ("new", "#2166ac", "new chain")]):
        vals = [fnum(apa_row(apa[("pdhd", which)], a.apa_tier, s) or {}, "plateau_ratio") for s in sels]
        ax.bar(np.arange(len(sels)) + (i - 1) * w, vals, w, color=col, label=lab, edgecolor="k", lw=0.4)
    ax.axhline(1.0, color="0.3", lw=1, ls="--")
    ax.set_xticks(range(len(sels))); ax.set_xticklabels(["APA0\nx<0 f0", "APA1\nx>0 f1", "APA2\nx<0 f0", "APA3\nx>0 f1"])
    ax.set_ylabel("plateau dQ/dx / table  (rr 40-60, NO free scale)")
    ax.set_title("(b) PDHD, %s: the drift-volume split, and what the chain did to it" % a.apa_tier, fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.25, axis="y")

    # (c) ABSOLUTE band counts per APA, old vs new -- deletion vs recovery
    ax = fig.add_subplot(gs[1, 0])
    xs, labs = [], []
    pos = 0
    for s in sels:
        for which, hatch in (("old", ""), ("new", "//")):
            row = apa_row(apa[("pdhd", which)], a.apa_tier, s)
            if row is None:
                pos += 1; continue
            bot = 0
            for bi, bn in enumerate(BANDNAME):
                v = fnum(row, "band_" + bn.replace("<", "lt").replace(">", "gt"))
                ax.bar(pos, v, 0.8, bottom=bot, color=BANDCOL[bi], edgecolor="k", lw=0.3, hatch=hatch)
                bot += v
            xs.append(pos); labs.append("%s\n%s" % (s, which)); pos += 1
        pos += 0.6
    ax.set_xticks(xs); ax.set_xticklabels(labs, fontsize=7)
    ax.set_ylabel("plateau points (ABSOLUTE)")
    ax.set_title("(c) PDHD plateau points by dQ/dx / table -- counts, not fractions.\n"
                 "Recovery collapses the red band while blue holds; deletion shrinks every band.", fontsize=9)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc=BANDCOL[i], ec="k", lw=0.3) for i in range(5)],
              labels=BANDNAME, fontsize=8, ncol=5, loc="upper right")
    ax.grid(alpha=0.25, axis="y")

    # (d) PDVD control, same treatment
    ax = fig.add_subplot(gs[1, 1])
    vsels = [s for s in ("bottom_xneg", "top_xpos") if apa_row(apa[("pdvd", "new")], a.apa_tier, s)]
    xs, labs, pos = [], [], 0
    for s in vsels:
        for which, hatch in (("old", ""), ("new", "//")):
            row = apa_row(apa[("pdvd", which)], a.apa_tier, s)
            if row is None:
                pos += 1; continue
            bot = 0
            for bi, bn in enumerate(BANDNAME):
                v = fnum(row, "band_" + bn.replace("<", "lt").replace(">", "gt"))
                ax.bar(pos, v, 0.8, bottom=bot, color=BANDCOL[bi], edgecolor="k", lw=0.3, hatch=hatch)
                bot += v
            xs.append(pos); labs.append("%s\n%s" % (s.split("_")[0], which)); pos += 1
        pos += 0.6
    ax.set_xticks(xs); ax.set_xticklabels(labs, fontsize=7)
    ax.set_ylabel("plateau points (ABSOLUTE)")
    ax.set_title("(d) PDVD control, %s: the same bands on the detector whose\nonly chain change is R3" % a.apa_tier, fontsize=9)
    ax.grid(alpha=0.25, axis="y")

    fig.suptitle("doc pdvd/50 round 2 -- dQ/dx vs residual range with APA0 separated (PDHD) and PDVD as control", fontsize=12)
    out1 = os.path.join(a.figs, "51_dqdx_rr_apa.png")
    fig.savefig(out1, dpi=110, bbox_inches="tight"); plt.close(fig)

    # ============ figure 2: what the chain changed =======================
    fig, axs = plt.subplots(2, 2, figsize=(14, 9))
    order = [("pdhd", "old"), ("pdhd", "fit0"), ("pdhd", "new"),
             ("pdvd", "old"), ("pdvd", "fit0"), ("pdvd", "new")]
    names = ["PDHD old", a.mid_label_pdhd, "PDHD new", "PDVD old", a.mid_label_pdvd, "PDVD new"]
    cols = ["0.62", "#f4a582", "#2166ac", "#c7e9c0", "#a1d99b", "#1a9850"]

    ax = axs[0, 0]
    data = [[fnum(t, "f_low") for t in trk[k] if np.isfinite(fnum(t, "f_low"))] for k in order]
    bp = ax.boxplot(data, labels=names, showfliers=False, patch_artist=True)
    for p, c in zip(bp["boxes"], cols):
        p.set_facecolor(c)
    ax.set_ylabel("f_low  (fraction of live points < 0.4 x plateau)")
    ax.set_title("(a) f_low -- falls when charge is recovered OR when R3 deletes the points", fontsize=9)
    ax.grid(alpha=0.25, axis="y"); ax.tick_params(axis="x", labelsize=8)

    ax = axs[0, 1]
    data = [[fnum(t, "pts_per_cm") for t in trk[k] if np.isfinite(fnum(t, "pts_per_cm"))] for k in order]
    bp = ax.boxplot(data, labels=names, showfliers=False, patch_artist=True)
    for p, c in zip(bp["boxes"], cols):
        p.set_facecolor(c)
    ax.set_ylabel("live fit points per cm of kept path")
    ax.set_title("(b) the discriminator: density HELD with f_low down = recovery;\ndensity DOWN with f_low down = deletion", fontsize=9)
    ax.grid(alpha=0.25, axis="y"); ax.tick_params(axis="x", labelsize=8)

    ax = axs[1, 0]
    tiers = ["all_kept", "contrast_ge2", "complete", "complete_bragg"]
    xw = 0.13
    for i, (k, nm, c) in enumerate(zip(order, names, cols)):
        rows = read_tsv(P(arms[k] + "_summary.tsv"))
        vals = [fnum(next((r for r in rows if r["tier"] == t), {}), "ntracks") for t in tiers]
        ax.bar(np.arange(len(tiers)) + (i - 2.5) * xw, vals, xw, color=c, edgecolor="k", lw=0.3, label=nm)
    ax.set_yscale("log"); ax.set_xticks(range(len(tiers))); ax.set_xticklabels(tiers, fontsize=8)
    ax.set_ylabel("tracks"); ax.set_title("(c) the tier ladder", fontsize=9)
    ax.legend(fontsize=7, ncol=2); ax.grid(alpha=0.25, axis="y")

    ax = axs[1, 1]
    vals = [np.mean([fnum(t, "reach") for t in trk[k]]) if trk[k] else np.nan for k in order]
    ax.bar(range(len(order)), vals, color=cols, edgecolor="k", lw=0.4)
    ax.set_xticks(range(len(order))); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("fraction reaching rr < 2 cm and rr >= 22 cm")
    ax.set_title("(d) reach -- if this falls, a tier collapse is a TRIMMED STOPPING END,\nnot a charge effect (doc pdvd/32, doc 38 and R3 all act there)", fontsize=9)
    ax.grid(alpha=0.25, axis="y")

    fig.suptitle("doc pdvd/50 round 2 -- what the doc-11 chain changed", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out2 = os.path.join(a.figs, "51_chain_before_after.png")
    fig.savefig(out2, dpi=110, bbox_inches="tight"); plt.close(fig)

    print("wrote", out1)
    print("wrote", out2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
