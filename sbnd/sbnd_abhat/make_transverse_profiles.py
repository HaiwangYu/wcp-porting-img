#!/usr/bin/env python3
"""
make_transverse_profiles.py  --  Stage 3 (map-level), SBND SCE migration.

Map-level SCE spatial-offset PROFILES vs drift distance, in Lane Kashur's
technote convention:

  * FORWARD displacement (Delta = reco - true)  -> read TrueFwd_Displacement_*
  * horizontal axis = DRIFT DISTANCE (0 = anode, ~200 cm = cathode), not signed x
  * West = orange, East = blue  (matches technote Fig 4)

Produces one figure (08_transverse_profiles.png) with three panels:

  (a) Delta x vs drift  -- CROSS-CHECK. Should reproduce technote Fig 4
      (peak ~0.9 cm near mid-drift, West curve above East). If it does, the
      geometry / drift-distance handling is validated and panels (b),(c) are
      trustworthy.
  (b) Delta y vs drift  -- conditioned near top (y>0) and bottom (y<0) walls.
      Expect top negative / bottom positive, |Delta y| growing toward the
      cathode (large drift). This is the SBND analog of MicroBooNE's
      Delta_y_top(x) / Delta_y_bottom(x) (NOTE-1018, Sec 6.1).
  (c) Delta z vs drift  -- conditioned near the upstream (z->0) and
      downstream (z->~500) ends, where Delta z is non-negligible.

This reads the map ONLY (no BEE / reco output), so it gives the map
EXPECTATION. The reco-vs-map closure (Stage 3a + plot 09) comes later.

Run on the gpvm with the SCE env loaded (ROOT + matplotlib available):

    source $SCE_TOP/restore_sce_env_036_sce.sh
    python make_transverse_profiles.py
    # optional: SCE_MAP_FILE=/some/other/map.root python make_transverse_profiles.py
"""

import os
import numpy as np
import ROOT
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------------
# Configuration  (everything you might want to tune lives here)
# ----------------------------------------------------------------------------
MAP_FILE = os.environ.get(
    "SCE_MAP_FILE",
    "/cvmfs/sbnd.opensciencegrid.org/products/sbnd/sbnd_data/v01_42_00/"
    "SCEoffsets/SCEoffsets_SBND_E500_dualmap_CV_voxelTH3.root",
)

# Forward-displacement TH3 names. Lane's Fig 7/8 are the FORWARD map, so we
# match that. (TrueBkwd_* exist too; do NOT mix the two within SBND.)
FWD = {
    ("x", "E"): "TrueFwd_Displacement_X_E", ("x", "W"): "TrueFwd_Displacement_X_W",
    ("y", "E"): "TrueFwd_Displacement_Y_E", ("y", "W"): "TrueFwd_Displacement_Y_W",
    ("z", "E"): "TrueFwd_Displacement_Z_E", ("z", "W"): "TrueFwd_Displacement_Z_W",
}

# Geometry (cm). Cathode at x = 0, anodes at x = +/- ANODE_ABS_X.
# East TPC = x < 0 (APA 0), West TPC = x > 0 (APA 1).
ANODE_ABS_X = 200.0
TPC_XRANGE = {"E": (-ANODE_ABS_X, 0.0), "W": (0.0, ANODE_ABS_X)}

# Conditioning regions (cm).
TOP_Y_MIN        =  150.0   # "near top wall"     (Delta y)
BOT_Y_MAX        = -150.0   # "near bottom wall"  (Delta y)
UPSTREAM_Z_MAX   =   60.0   # near z = 0 end      (Delta z)
DOWNSTREAM_Z_MIN =  440.0   # near z ~ 500 end    (Delta z)

# Bulk region used for the Delta x cross-check (mimics Lane's edge-avoiding
# calibration selection so the cross-check tracks Fig 4 rather than the corners).
BULK_ABS_Y_MAX = 150.0
BULK_Z_MIN, BULK_Z_MAX = 50.0, 450.0

# Drift-distance binning. 20 cm matches existing plot 06; drop to 10 to mirror
# Lane Fig 4 more finely once you trust the script.
DRIFT_BINS = np.arange(0.0, ANODE_ABS_X + 1e-6, 20.0)

# Lane colors (colorblind-safe).
COL = {"W": "#E69F00", "E": "#0072B2"}   # West orange, East blue
TPC_LABEL = {"W": "West", "E": "East"}

OUTDIR = os.environ.get("SCE_PLOT_OUT", "validation_plots")
OUTNAME = "08_transverse_profiles.png"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def load_voxels(h):
    """Flatten a TH3 to (x, y, z, value) arrays of bin centers / contents [cm]."""
    ax, ay, az = h.GetXaxis(), h.GetYaxis(), h.GetZaxis()
    nx, ny, nz = h.GetNbinsX(), h.GetNbinsY(), h.GetNbinsZ()
    xc = np.fromiter((ax.GetBinCenter(i) for i in range(1, nx + 1)), float, nx)
    yc = np.fromiter((ay.GetBinCenter(j) for j in range(1, ny + 1)), float, ny)
    zc = np.fromiter((az.GetBinCenter(k) for k in range(1, nz + 1)), float, nz)
    val = np.empty((nx, ny, nz), dtype=float)
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                val[i, j, k] = h.GetBinContent(i + 1, j + 1, k + 1)
    X, Y, Z = np.meshgrid(xc, yc, zc, indexing="ij")
    return X.ravel(), Y.ravel(), Z.ravel(), val.ravel()


def drift_profile(x, val, mask):
    """Median (+ MAD) of val vs drift distance = ANODE_ABS_X - |x|, within mask."""
    d = ANODE_ABS_X - np.abs(x)
    d, v = d[mask], val[mask]
    cen, med, mad = [], [], []
    for lo, hi in zip(DRIFT_BINS[:-1], DRIFT_BINS[1:]):
        b = (d >= lo) & (d < hi)
        if b.sum() < 5:                      # need a few voxels for a stable median
            continue
        m = float(np.median(v[b]))
        cen.append(0.5 * (lo + hi))
        med.append(m)
        mad.append(float(np.median(np.abs(v[b] - m))))
    return np.array(cen), np.array(med), np.array(mad)


def watermark(ax):
    ax.text(0.03, 0.95, "SBND Simulation\nPreliminary", transform=ax.transAxes,
            ha="left", va="top", color="0.45", fontsize=10)


# ----------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------
if not os.path.exists(MAP_FILE):
    raise SystemExit(f"[fatal] SCE map not found:\n  {MAP_FILE}\n"
                     f"Set SCE_MAP_FILE to the correct path.")

f = ROOT.TFile.Open(MAP_FILE)
if not f or f.IsZombie():
    raise SystemExit(f"[fatal] could not open {MAP_FILE}")

data = {}                       # (comp, tpc) -> (x,y,z,val)
for (comp, tpc), name in FWD.items():
    h = f.Get(name)
    if not h:
        raise SystemExit(f"[fatal] histogram '{name}' not in file. "
                         f"Check names with: rootls -l {MAP_FILE}")
    ax = h.GetXaxis()
    print(f"  {name:32s} nbins=({h.GetNbinsX()},{h.GetNbinsY()},{h.GetNbinsZ()})"
          f"  x:[{ax.GetXmin():.1f},{ax.GetXmax():.1f}] cm")
    data[(comp, tpc)] = load_voxels(h)

os.makedirs(OUTDIR, exist_ok=True)

# ----------------------------------------------------------------------------
# Plot
# ----------------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.2))
fig.suptitle("SBND SCE dualmap -- forward spatial offsets vs drift distance "
             "(map expectation)", fontsize=13)

# (a) Delta x cross-check ----------------------------------------------------
axx = axes[0]
for tpc in ("W", "E"):
    x, y, z, v = data[("x", tpc)]
    xlo, xhi = TPC_XRANGE[tpc]
    bulk = ((x >= xlo) & (x <= xhi) & (np.abs(y) <= BULK_ABS_Y_MAX)
            & (z >= BULK_Z_MIN) & (z <= BULK_Z_MAX))
    # plot |Delta x| to match Lane Fig 4 (which shows the offset as positive)
    c, m, e = drift_profile(x, np.abs(v), bulk)
    axx.errorbar(c, m, yerr=e, marker="s", ms=5, lw=1.6, capsize=2,
                 color=COL[tpc], label=f"{TPC_LABEL[tpc]} TPC")
axx.set_title(r"(a) $|\Delta x|$ vs drift  —  cross-check vs Fig 4")
axx.set_xlabel("Drift Distance [cm]")
axx.set_ylabel(r"Spatial Offset $|\Delta x|$ [cm]")
axx.set_xlim(0, ANODE_ABS_X)
axx.grid(alpha=0.3)
axx.legend()
watermark(axx)

# (b) Delta y top / bottom ---------------------------------------------------
axy = axes[1]
for tpc in ("W", "E"):
    x, y, z, v = data[("y", tpc)]
    xlo, xhi = TPC_XRANGE[tpc]
    inx = (x >= xlo) & (x <= xhi)
    top = inx & (y >= TOP_Y_MIN)
    bot = inx & (y <= BOT_Y_MAX)
    c, m, e = drift_profile(x, v, top)
    axy.errorbar(c, m, yerr=e, marker="^", ms=5, lw=1.6, capsize=2, ls="-",
                 color=COL[tpc], label=f"{TPC_LABEL[tpc]} top")
    c, m, e = drift_profile(x, v, bot)
    axy.errorbar(c, m, yerr=e, marker="v", ms=5, lw=1.6, capsize=2, ls="--",
                 color=COL[tpc], label=f"{TPC_LABEL[tpc]} bottom")
axy.axhline(0, color="0.6", lw=0.8)
axy.set_title(r"(b) $\Delta y$ vs drift  —  near top / bottom walls")
axy.set_xlabel("Drift Distance [cm]")
axy.set_ylabel(r"Spatial Offset $\Delta y$ [cm]")
axy.set_xlim(0, ANODE_ABS_X)
axy.grid(alpha=0.3)
axy.legend(fontsize=8)
watermark(axy)

# (c) Delta z upstream / downstream -----------------------------------------
axz = axes[2]
for tpc in ("W", "E"):
    x, y, z, v = data[("z", tpc)]
    xlo, xhi = TPC_XRANGE[tpc]
    inx = (x >= xlo) & (x <= xhi)
    up = inx & (z <= UPSTREAM_Z_MAX)
    dn = inx & (z >= DOWNSTREAM_Z_MIN)
    c, m, e = drift_profile(x, v, up)
    axz.errorbar(c, m, yerr=e, marker="^", ms=5, lw=1.6, capsize=2, ls="-",
                 color=COL[tpc], label=f"{TPC_LABEL[tpc]} upstream")
    c, m, e = drift_profile(x, v, dn)
    axz.errorbar(c, m, yerr=e, marker="v", ms=5, lw=1.6, capsize=2, ls="--",
                 color=COL[tpc], label=f"{TPC_LABEL[tpc]} downstream")
axz.axhline(0, color="0.6", lw=0.8)
axz.set_title(r"(c) $\Delta z$ vs drift  —  near upstream / downstream ends")
axz.set_xlabel("Drift Distance [cm]")
axz.set_ylabel(r"Spatial Offset $\Delta z$ [cm]")
axz.set_xlim(0, ANODE_ABS_X)
axz.grid(alpha=0.3)
axz.legend(fontsize=8)
watermark(axz)

fig.tight_layout(rect=(0, 0, 1, 0.96))
outpath = os.path.join(OUTDIR, OUTNAME)
fig.savefig(outpath, dpi=140)
print(f"\n[ok] wrote {outpath}")

# ----------------------------------------------------------------------------
# Console summary (sanity numbers)
# ----------------------------------------------------------------------------
'''
print("\nPeak |median| offset per component (over plotted drift bins):")
for comp, label in (("x", "|dx| bulk"), ("y", "dy top/bot"), ("z", "dz up/dn")):
    for tpc in ("E", "W"):
        x, y, z, v = data[(comp, tpc)]
        xlo, xhi = TPC_XRANGE[tpc]
        inx = (x >= xlo) & (x <= xhi)
        if comp == "x":
            mask = inx & (np.abs(y) <= BULK_ABS_Y_MAX) & (z >= BULK_Z_MIN) & (z <= BULK_Z_MAX)
            vals = np.abs(v)
        elif comp == "y":
            mask = inx & ((y >= TOP_Y_MIN) | (y <= BOT_Y_MAX))
            vals = v
        else:
            mask = inx & ((z <= UPSTREAM_Z_MAX) | (z >= DOWNSTREAM_Z_MIN))
            vals = v
        _, m, _ = drift_profile(x, vals, mask)
        peak = np.max(np.abs(m)) if m.size else float("nan")
        print(f"  {label:12s} {TPC_LABEL[tpc]:5s}: {peak:6.3f} cm")
'''
print("\nPeak |median| offset per component / region (over plotted drift bins):")
def _peak(x, v, mask):
    _, m, _ = drift_profile(x, v, mask)
    return np.max(np.abs(m)) if m.size else float("nan")

for tpc in ("E", "W"):
    xlo, xhi = TPC_XRANGE[tpc]
    x, y, z, v = data[("x", tpc)]; inx = (x >= xlo) & (x <= xhi)
    bulk = inx & (np.abs(y) <= BULK_ABS_Y_MAX) & (z >= BULK_Z_MIN) & (z <= BULK_Z_MAX)
    print(f"  |dx| bulk      {TPC_LABEL[tpc]:5s}: {_peak(x, np.abs(v), bulk):6.3f} cm")
    x, y, z, v = data[("y", tpc)]; inx = (x >= xlo) & (x <= xhi)
    print(f"  dy top         {TPC_LABEL[tpc]:5s}: {_peak(x, v, inx & (y >= TOP_Y_MIN)):6.3f} cm")
    print(f"  dy bottom      {TPC_LABEL[tpc]:5s}: {_peak(x, v, inx & (y <= BOT_Y_MAX)):6.3f} cm")
    x, y, z, v = data[("z", tpc)]; inx = (x >= xlo) & (x <= xhi)
    print(f"  dz upstream    {TPC_LABEL[tpc]:5s}: {_peak(x, v, inx & (z <= UPSTREAM_Z_MAX)):6.3f} cm")
    print(f"  dz downstream  {TPC_LABEL[tpc]:5s}: {_peak(x, v, inx & (z >= DOWNSTREAM_Z_MIN)):6.3f} cm")
