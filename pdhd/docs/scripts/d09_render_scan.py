#!/usr/bin/env python3
"""doc pdhd/09 Phase 6 -- render one PNG panel per contested TGM cluster.

The doc pdhd/03 `d03_render` substitute for a Bee scan: nothing leaves the
machine, and the panels can be scanned immediately.  A Bee set is built
separately for the owner's spot-check.

Design rule taken from the SBND rounds: a scan display must show the EVIDENCE,
not a fit.  A fit-only picture changed 6 of 36 hand labels once.  So each panel
draws, in both the x-y and x-z projections:
  * every imaged point of the cluster (t0-corrected, the frame the taggers use),
  * the two PCA ends, marked,
  * the OFF boundary (flat 17.5 / 18 cm inset) and the ON boundary (the measured
    surface + its cushion), so the reader can see WHICH boundary moved the verdict,
  * the nominal active wall.
The question the scanner answers is single and pre-registered: does this object
exit the detector (deserve TGM) or stop inside it?

Repro:
  python3 docs/scripts/d09_render_scan.py /home/xqian/tmp/d09/ab_p90c5_verdicts.json \
      --key tgm_lost --profile p90 --cushion 5 --n 40 --out /home/xqian/tmp/d09/panels
"""
import argparse, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d09_fv_pdhd import XW, CATH, YLO, YHI, ZLO, ZHI, WALLS, event_points
from d09_quantile_offline import Boundary, knot_inset, BOX_MARGIN
from d09_quantile_surface import JN


def load_profile(path, q):
    """Read the generated jsonnet knot lists without a jsonnet dependency."""
    import re
    txt = open(path).read()
    blk = re.search(rf"\bp{q}:\s*\{{(.*?)\n  \}}", txt, re.S)
    if not blk:
        raise SystemExit(f"no p{q} block in {path}")
    out = {}
    for m in re.finditer(r"(\w+):\s*\[(.*?)\],\s*$", blk.group(1), re.M):
        out[m.group(1)] = [[float(x) for x in pair.strip("[] ").split(",")]
                           for pair in re.findall(r"\[[^\]]*\]", m.group(2))]
    return out


def draw(ax, plane, B_off, B_on):
    lo, hi, wlo, whi = (YLO, YHI, "y-", "y+") if plane == "y" else (ZLO, ZHI, "z-", "z+")
    xs = np.concatenate([np.linspace(-XW, -CATH, 160), np.linspace(CATH, XW, 160)])
    ax.add_patch(plt.Rectangle((-XW, lo), 2*XW, hi-lo, fill=False, ec="k", lw=1.0))
    for B, c, ls, lab in ((B_off, "tab:red", "--", "OFF (flat 17.5/18)"),
                          (B_on, "tab:blue", "-", "ON (measured + cushion)")):
        vol = lambda x: "g02" if x < 0 else "g13"
        ax.plot(xs, [lo + B.inset(wlo, vol(x), abs(x)) for x in xs], color=c, ls=ls, lw=1.3, label=lab)
        ax.plot(xs, [hi - B.inset(whi, vol(x), abs(x)) for x in xs], color=c, ls=ls, lw=1.3)
    ax.axvspan(-CATH, CATH, color="0.85")
    ax.set_xlim(-XW-15, XW+15); ax.set_ylim(lo-25, hi+25)
    ax.set_xlabel("x [cm]   (g02 < 0, g13 > 0)"); ax.set_ylabel(f"{plane} [cm]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verdicts"); ap.add_argument("--key", default="tgm_lost")
    ap.add_argument("--pdhd", default="/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd")
    ap.add_argument("--arm", default="d09fvoff")
    ap.add_argument("--profiles", default="/home/xqian/toolkit-dev/toolkit/cfg/pgrapher/experiment/pdhd/curved_fiducial_profiles.jsonnet")
    ap.add_argument("--profile", default="p90"); ap.add_argument("--cushion", type=float, default=5.0)
    ap.add_argument("--n", type=int, default=40); ap.add_argument("--minlen", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="/home/xqian/tmp/d09/panels")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    V = json.load(open(a.verdicts))
    items = [d for d in V.get("geom", {}).get(a.key, []) if d["len_cm"] >= a.minlen]
    if not items:
        raise SystemExit(f"no items under geom.{a.key}")
    rng = np.random.default_rng(a.seed)
    if len(items) > a.n:
        items = [items[i] for i in sorted(rng.choice(len(items), a.n, replace=False))]
    kn = load_profile(a.profiles, str(a.profile).lstrip("p"))
    B_off = Boundary("flat", "flat", 0.0)
    B_on = Boundary(f"{a.profile}+{a.cushion:.0f}", "knot", a.cushion, kn)

    sheet = []
    cache = {}
    for i, d in enumerate(sorted(items, key=lambda r: (r["run"], int(r["idx"]), r["cid"]))):
        wd = os.path.join(a.pdhd, "work", f"{d['run']}_{d['idx']}_{a.arm}")
        if wd not in cache:
            try: cache[wd] = event_points(wd)
            except Exception as ex: print("skip", wd, ex); continue
        E = cache[wd]
        m = (E["cid"] == d["cid"]) & E["phys"]
        if m.sum() < 5: continue
        Q = E["P"][m]
        fig, axes = plt.subplots(1, 2, figsize=(15, 5.2))
        for ax, plane, col in zip(axes, ("y", "z"), (1, 2)):
            draw(ax, plane, B_off, B_on)
            ax.scatter(Q[:, 0], Q[:, col], s=1.2, c="0.25", alpha=0.55, zorder=3)
            for e, mk in ((d["e1"], "o"), (d["e2"], "s")):
                ax.plot(e[0], e[col], mk, ms=9, mfc="none", mec="tab:green", mew=2.0, zorder=5)
            if plane == "y": ax.legend(fontsize=7, loc="lower center")
        fig.suptitle(f"[{i}] {d['run']}/{d['idx']} cluster {d['cid']}   "
                     f"len {d['len_cm']:.0f} cm   {d['npts']} pts   {d['half']} half   "
                     f"{a.key}  ({a.profile}+{a.cushion:.0f} vs flat)", fontsize=10)
        fig.tight_layout()
        fn = os.path.join(a.out, f"{i:03d}_{d['run']}_{d['idx']}_c{d['cid']}.png")
        fig.savefig(fn, dpi=105); plt.close(fig)
        sheet.append(dict(i=i, png=os.path.basename(fn), run=d["run"], idx=d["idx"],
                          cid=d["cid"], len_cm=d["len_cm"], half=d["half"], verdict=""))
    json.dump(sheet, open(os.path.join(a.out, "sheet.json"), "w"), indent=1)
    print(f"{len(sheet)} panels -> {a.out}  (blank 'verdict' field per row in sheet.json)")


if __name__ == "__main__":
    main()
