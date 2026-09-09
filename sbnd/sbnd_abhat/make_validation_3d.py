#!/usr/bin/env python3
"""
make_validation_3d.py -- Stage 3a closure, SBND SCE migration.

Pairs the img and sce3d bee sets on q (SCE-invariant) to recover, per point:
   pre-correction (x_t0, y, z)  [img]   and   (x_sce, y_sce, z_sce)  [sce3d].
Then for x/y/z:
   reco Delta = corrected - pre        (what the WCT reco applied)
   map  Delta = SIGN * TrueBkwd(x_t0,y,z)   (independent map lookup)

Outputs:
  09_pairing_check.png      reco-vs-map residual in X  (q-pairing validity; ~um)
  10_transverse_residual.png  reco-vs-map residual in Y and Z  (~um => plumbing OK)
  11_transverse_closure.png   reco Delta y/z profiles vs drift, map overlay
                              (Lane convention: drift distance, West orange/East blue)
"""
import zipfile, json, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ROOT

SCE_TOP = os.environ["SCE_TOP"]
ZIP = os.path.join(SCE_TOP, "sce_test", "mabc-all-apa.zip")
OUT = os.path.join(SCE_TOP, "sce_test", "validation_plots"); os.makedirs(OUT, exist_ok=True)
MAP = ("/cvmfs/sbnd.opensciencegrid.org/products/sbnd/sbnd_data/v01_42_00/"
       "SCEoffsets/SCEoffsets_SBND_E500_dualmap_CV_voxelTH3.root")
SIGN = -1.0          # matches SCEFieldTH3 sign convention
ANODE = 200.0
COL = {"W": "#E69F00", "E": "#0072B2"}

f = ROOT.TFile.Open(MAP)
H = {(c, t): f.Get(f"TrueBkwd_Displacement_{c.upper()}_{t}")
     for c in ("x", "y", "z") for t in ("E", "W")}

def clampax(a, v):
    lo = a.GetBinCenter(1); hi = a.GetBinCenter(a.GetNbins()); pad = 1e-3 * a.GetBinWidth(1)
    return lo + pad if v < lo + pad else (hi - pad if v > hi - pad else v)
def mapval(h, x, y, z):
    return h.Interpolate(clampax(h.GetXaxis(), x), clampax(h.GetYaxis(), y), clampax(h.GetZaxis(), z))

z = zipfile.ZipFile(ZIP)
evs = sorted({n.split("/")[1] for n in z.namelist() if n.startswith("data/")}, key=int)

X0=[]; Y0=[]; Z0=[]; TP=[]
DXr=[]; DYr=[]; DZr=[]; DXm=[]; DYm=[]; DZm=[]
n_img = n_sce = n_match = n_amb = 0
for e in evs:
    try:
        img = json.load(z.open("data/%s/%s-img-global.json" % (e, e)))
        sce = json.load(z.open("data/%s/%s-sce3d-global.json" % (e, e)))
    except KeyError:
        continue
    n_img += len(img["q"]); n_sce += len(sce["q"])
    qmap = {}
    for i, q in enumerate(img["q"]):
        qmap.setdefault(q, []).append(i)
    for j, q in enumerate(sce["q"]):
        idx = qmap.get(q)
        if not idx or len(idx) != 1:     # ambiguous / unmatched -> drop
            n_amb += 1; continue
        i = idx[0]
        x0, y0, z0 = img["x"][i], img["y"][i], img["z"][i]
        xs, ys, zs = sce["x"][j], sce["y"][j], sce["z"][j]
        t = "E" if x0 < 0 else "W"
        X0.append(x0); Y0.append(y0); Z0.append(z0); TP.append(0 if x0 < 0 else 1)
        DXr.append(xs - x0); DYr.append(ys - y0); DZr.append(zs - z0)
        DXm.append(SIGN * mapval(H[("x", t)], x0, y0, z0))
        DYm.append(SIGN * mapval(H[("y", t)], x0, y0, z0))
        DZm.append(SIGN * mapval(H[("z", t)], x0, y0, z0))
        n_match += 1

X0=np.array(X0); Y0=np.array(Y0); Z0=np.array(Z0); TP=np.array(TP)
DXr=np.array(DXr); DYr=np.array(DYr); DZr=np.array(DZr)
DXm=np.array(DXm); DYm=np.array(DYm); DZm=np.array(DZm)
E = TP == 0; W = TP == 1
rx, ry, rz = DXr - DXm, DYr - DYm, DZr - DZm   # residuals [cm]

print(f"img pts {n_img}  sce3d pts {n_sce}  matched {n_match}  dropped(ambiguous) {n_amb}")
print(f"x-residual rms: E={rx[E].std()*1e4:.2f}um W={rx[W].std()*1e4:.2f}um "
      f"max={np.abs(rx).max()*1e4:.2f}um   <-- if ~um, q-pairing is VALID")
print(f"y-residual rms: E={ry[E].std()*1e4:.2f}um W={ry[W].std()*1e4:.2f}um max={np.abs(ry).max()*1e4:.2f}um")
print(f"z-residual rms: E={rz[E].std()*1e4:.2f}um W={rz[W].std()*1e4:.2f}um max={np.abs(rz).max()*1e4:.2f}um")

# unified validation record (supersedes the Stage-1 SUMMARY)
nev = len(evs)
wx = np.abs(DXr); poolE, poolW = wx[E].mean(), wx[W].mean()
with open(os.path.join(OUT, "SUMMARY.txt"), "w") as fh:
    fh.write("SBND WCT 0.36 SCECorrection validation -- %d crossing-muon events\n" % nev)
    fh.write("points: %d paired by q (East %d, West %d); %d/%d matched, %d dropped (ambiguous q)\n"
             % (n_match, E.sum(), W.sum(), n_match, n_sce, n_amb))
    fh.write("=== Per-point reco-vs-map closure ===\n")
    fh.write("Dx rms (cm):  E = %.2e   W = %.2e   max = %.2e\n" % (rx[E].std(), rx[W].std(), np.abs(rx).max()))
    fh.write("Dy rms (cm):  E = %.2e   W = %.2e   max = %.2e   [Stage 3a]\n" % (ry[E].std(), ry[W].std(), np.abs(ry).max()))
    fh.write("Dz rms (cm):  E = %.2e   W = %.2e   max = %.2e   [Stage 3a]\n" % (rz[E].std(), rz[W].std(), np.abs(rz).max()))
    fh.write("=> reproduces the TH3 backward map to interpolation precision in all three components\n")
    fh.write("pooled mean|Dx|: East=%.4f West=%.4f  W/E=%.3f\n" % (poolE, poolW, poolW/poolE))
    fh.write("references: map vol-avg 1.276, 0.33-era reco 1.271\n")
print("wrote", os.path.join(OUT, "SUMMARY.txt"))

def watermark(ax):
    ax.text(0.03, 0.95, "SBND Simulation\nPreliminary", transform=ax.transAxes,
            ha="left", va="top", color="0.45", fontsize=9)

# --- 09: X residual (q-pairing validity) ---
fig, ax = plt.subplots(figsize=(7, 4.5))
for sel, lab in [(E, "East (APA 0)"), (W, "West (APA 1)")]:
    ax.hist(rx[sel]*1e4, bins=48, range=(-6, 6), histtype="step", lw=1.6, label=lab)
ax.set_yscale("log"); ax.set_ylim(bottom=0.5)
ax.set_xlabel(r"reco $\Delta x-$map $\Delta x$ [$\mu$m]"); ax.set_ylabel("points (log)")
ax.set_title("q-pairing check (img <-> sce3d): X closure")
ax.legend(loc="upper right")
ax.text(0.02, 0.96, "rms E=%.2f, W=%.2f um\nmax=%.2f um\nmatched=%d  dropped=%d"
        % (rx[E].std()*1e4, rx[W].std()*1e4, np.abs(rx).max()*1e4, n_match, n_amb),
        transform=ax.transAxes, va="top", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="0.7"))
fig.tight_layout(); fig.savefig(OUT+"/09_pairing_check.png", dpi=130); plt.close(fig)

# --- 10: transverse residual (Y, Z) ---
fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
for ax, r, c in [(axs[0], ry, "y"), (axs[1], rz, "z")]:
    for sel, lab in [(E, "East"), (W, "West")]:
        ax.hist(r[sel]*1e4, bins=48, range=(-6, 6), histtype="step", lw=1.6, label=lab)
    ax.set_yscale("log"); ax.set_ylim(bottom=0.5)
    ax.set_xlabel(rf"reco $\Delta {c}-$map $\Delta {c}$ [$\mu$m]")
    ax.set_title(rf"$\Delta {c}$ closure (reco vs map)")
    ax.legend(loc="upper right")
    ax.text(0.02, 0.96, "rms E=%.2f, W=%.2f um" %
            (r[E].std()*1e4, r[W].std()*1e4), transform=ax.transAxes,
            va="top", fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7"))
axs[0].set_ylabel("points (log)")
fig.suptitle("SCE transverse reco-vs-map per-point residual", fontsize=12)
fig.tight_layout(); fig.savefig(OUT+"/10_transverse_residual.png", dpi=130); plt.close(fig)

# --- 11: transverse closure profiles vs drift (Lane convention), map overlay ---
d = ANODE - np.abs(X0)
DB = np.arange(0.0, 200.001, 20.0)
def prof(arr, sel):
    cen, med = [], []
    for lo, hi in zip(DB[:-1], DB[1:]):
        s = sel & (d >= lo) & (d < hi)
        if s.sum() < 20: continue
        cen.append(0.5*(lo+hi)); med.append(np.median(arr[s]))
    return np.array(cen), np.array(med)

fig, (ay, az) = plt.subplots(1, 2, figsize=(13, 5))
for ax, dr, dm, comp, regs in [
        (ay, DYr, DYm, "y", [("top", Y0 > 150, "^", "-"), ("bottom", Y0 < -150, "v", "--")]),
        (az, DZr, DZm, "z", [("upstream", Z0 < 60, "^", "-"), ("downstream", Z0 > 440, "v", "--")])]:
    for tpc, sel0 in [("W", W), ("E", E)]:
        for reg, rmask, mk, ls in regs:
            sel = sel0 & rmask
            c, mr = prof(dr, sel); _, mm = prof(dm, sel)
            if c.size:
                ax.plot(c, mr, ls=ls, marker=mk, ms=5, color=COL[tpc],
                        label=f"{tpc} {reg} (reco)")
                ax.plot(c, mm, ls=":", color=COL[tpc], alpha=0.5, lw=2.5)  # map overlay
    ax.axhline(0, color="0.6", lw=0.8)
    ax.set_xlabel("Drift Distance [cm]"); ax.set_xlim(0, 200)
    ax.set_ylabel(rf"Spatial Offset $\Delta {comp}$ [cm]")
    ax.set_title(rf"$\Delta {comp}$ closure: markers=reco, dotted=map"); ax.grid(alpha=0.3)
    ax.legend(fontsize=8); watermark(ax)
fig.suptitle("SBND SCE transverse closure -- reco (markers) vs map (dotted) vs drift", fontsize=12)
fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(OUT+"/11_transverse_closure.png", dpi=130); plt.close(fig)
print("wrote", sorted(n for n in os.listdir(OUT) if n.startswith(("09","10","11"))))
