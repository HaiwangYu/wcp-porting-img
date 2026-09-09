import zipfile, json, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ROOT

ZIP="mabc-all-apa.zip"; OUT="validation_plots"; os.makedirs(OUT,exist_ok=True)
MAP="/cvmfs/sbnd.opensciencegrid.org/products/sbnd/sbnd_data/v01_42_00/SCEoffsets/SCEoffsets_SBND_E500_dualmap_CV_voxelTH3.root"
SIGN=-1.0
f=ROOT.TFile.Open(MAP); hE=f.Get("TrueBkwd_Displacement_X_E"); hW=f.Get("TrueBkwd_Displacement_X_W")

def clampax(a,v):
    lo=a.GetBinCenter(1); hi=a.GetBinCenter(a.GetNbins()); pad=1e-3*a.GetBinWidth(1)
    return lo+pad if v<lo+pad else hi-pad if v>hi-pad else v
def mapdx(h,x,y,z):
    return h.Interpolate(clampax(h.GetXaxis(),x),clampax(h.GetYaxis(),y),clampax(h.GetZaxis(),z))

z=zipfile.ZipFile(ZIP)
evs=sorted({n.split("/")[1] for n in z.namelist() if n.startswith("data/")},key=int)
xr=[]; dr=[]; dm=[]; tp=[]
for e in evs:
    try:
        img=json.load(z.open("data/%s/%s-img-global.json"%(e,e)))
        sce=json.load(z.open("data/%s/%s-sce-global.json"%(e,e)))
    except KeyError: continue
    mi={}
    for x,y,zz,q in zip(img["x"],img["y"],img["z"],img["q"]):
        mi.setdefault((y,zz,q),[]).append(x)
    for x,y,zz,q in zip(sce["x"],sce["y"],sce["z"],sce["q"]):
        c=mi.get((y,zz,q))
        if not c or len(c)!=1: continue
        x0=c[0]; h=hE if x0<0 else hW
        xr.append(x0); dr.append(x-x0); dm.append(SIGN*mapdx(h,x0,y,zz)); tp.append(0 if x0<0 else 1)
xr=np.array(xr); dr=np.array(dr); dm=np.array(dm); tp=np.array(tp)
E=tp==0; W=tp==1; res=dr-dm
print("points %d  East %d  West %d"%(len(xr),E.sum(),W.sum()))

# -------- Fig 1: per-point residual (log-y, tight range, boxed annotation) --------
fig,ax=plt.subplots(figsize=(7,4.5))
ax.hist(res[E]*1e4, bins=48, range=(-6,6), histtype="step", lw=1.6, label="East (APA 0)")
ax.hist(res[W]*1e4, bins=48, range=(-6,6), histtype="step", lw=1.6, label="West (APA 1)")
ax.set_yscale("log"); ax.set_ylim(bottom=0.5)
ax.set_xlabel(r"reco $\Delta x$ $-$ map $\Delta x$  [$\mu$m]")
ax.set_ylabel("points (log scale)")
ax.set_title("SCE reco vs TH3 map: per-point residual")
ax.legend(loc="upper right")
ax.text(0.02, 0.96,
        "rms  E=%.1f µm,  W=%.1f µm\nmax |res| = %.1f µm\nN = %d  (E %d, W %d)"
        % (res[E].std()*1e4, res[W].std()*1e4, np.abs(res).max()*1e4,
           len(res), E.sum(), W.sum()),
        transform=ax.transAxes, va="top", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="0.7"))
fig.tight_layout(); fig.savefig(OUT+"/01_residual.png",dpi=130); plt.close(fig)

# -------- Fig 2: Δx vs drift coordinate (per-panel colorbars, TPC labels, sign hint) --------
fig,axs=plt.subplots(1,2,figsize=(12,4.8),sharey=True)
for ax,sel,lab,rng in [(axs[0],E,"East (APA 0)",(-200,0)),
                        (axs[1],W,"West (APA 1)",(0,200))]:
    h=ax.hist2d(xr[sel], dr[sel], bins=[100,80], range=[rng,(-1.4,1.4)],
                cmap="viridis", cmin=1)
    ax.set_xlabel("drift coordinate x [cm]"); ax.set_title(lab)
    ax.axhline(0, color="w", lw=0.5, alpha=0.6)
    fig.colorbar(h[3], ax=ax, pad=0.02, label="points / bin")
axs[0].set_ylabel(r"$\Delta x = x_{\rm sce}-x_{\rm raw}$ [cm]")
fig.suptitle("SCE spatial offset vs drift (50 crossing-muon events)  —  "
             r"East $\Delta x>0$, West $\Delta x<0$: inward backward correction",
             fontsize=10)
fig.tight_layout(); fig.savefig(OUT+"/02_dx_vs_drift.png",dpi=130); plt.close(fig)

# -------- Fig 3: |Δx| profile + W/E ratio (errorbars, map overlay, label in legend) --------
BW=20; nb=200//BW; dc=np.abs(xr); cen=np.array([(b+0.5)*BW for b in range(nb)])
def prof(arr, sel):
    m=[]; sem=[]
    for b in range(nb):
        s=sel & (dc>=b*BW) & (dc<(b+1)*BW); n=s.sum()
        if n>50:
            v=np.abs(arr[s]); m.append(v.mean()); sem.append(v.std(ddof=1)/np.sqrt(n))
        else:
            m.append(np.nan); sem.append(np.nan)
    return np.array(m), np.array(sem)
pE, seE = prof(dr, E); pW, seW = prof(dr, W)
pEm,_   = prof(dm, E); pWm,_   = prof(dm, W)
ratio   = pW/pE
rsem    = ratio*np.sqrt((seE/pE)**2 + (seW/pW)**2)

fig,(a1,a2)=plt.subplots(2,1,figsize=(7.5,6.5),sharex=True,
                         gridspec_kw={"height_ratios":[3,1]})
a1.errorbar(cen, pE, yerr=seE, fmt="o-", color="C0", capsize=2, label="East reco")
a1.errorbar(cen, pW, yerr=seW, fmt="s-", color="C1", capsize=2, label="West reco")
a1.plot(cen, pEm, "--", color="C0", alpha=0.55, label="East map prediction")
a1.plot(cen, pWm, "--", color="C1", alpha=0.55, label="West map prediction")
a1.set_ylabel(r"mean $|\Delta x|$ [cm]")
a1.set_title("SCE offset profile vs drift (reco vs TH3 map)")
a1.legend(fontsize=8, loc="upper right", ncol=2)
a1.grid(True, alpha=0.25)

a2.errorbar(cen, ratio, yerr=rsem, fmt="^-", color="k", capsize=2, label="reco W / E")
a2.axhline(1.276, ls="--", color="gray", label="map vol-avg = 1.276")
a2.axhline(1.0,   ls=":",  color="0.7", lw=0.7)
a2.set_ylim(0.9, 1.9)
a2.set_ylabel("W / E"); a2.set_xlabel("distance from cathode |x| [cm]")
a2.legend(fontsize=8, loc="upper left", ncol=2)
a2.grid(True, alpha=0.25)
fig.tight_layout(); fig.savefig(OUT+"/03_profile_ratio.png",dpi=130); plt.close(fig)

with open(OUT+"/SUMMARY.txt","w") as fh:
    fh.write("SBND WCT 0.36 SCECorrection validation -- 50 crossing-muon events\n")
    fh.write("points: %d (East %d, West %d)\n"%(len(xr),E.sum(),W.sum()))
    fh.write("per-point residual reco-map: rms E=%.2e W=%.2e cm, max %.2e cm\n"%(res[E].std(),res[W].std(),np.abs(res).max()))
    fh.write("pooled mean|Dx|: East=%.4f West=%.4f  W/E=%.3f\n"%(np.abs(dr[E]).mean(),np.abs(dr[W]).mean(),np.abs(dr[W]).mean()/np.abs(dr[E]).mean()))
    fh.write("references: map vol-avg 1.276, 0.33-era reco 1.271\n")
print("wrote",OUT,"->",sorted(os.listdir(OUT)))
