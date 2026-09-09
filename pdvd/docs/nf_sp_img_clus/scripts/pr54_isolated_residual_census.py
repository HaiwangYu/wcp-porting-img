"""Map every pr54 isolated-residual drop onto the scan candidates' stops."""
import re, os, json, glob, numpy as np
W="/home/xqian/toolkit-dev/wcp-porting-img/pdvd/work"
PREP="/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd"
RE=re.compile(r"pr54 isolated-residual drop: cluster (\d+) n_points=(\d+) length=([\d.]+) cm "
              r"dir_mag=([\d.]+) cm v1=\(([-\d.]+),([-\d.]+),([-\d.]+)\) v2=\(([-\d.]+),([-\d.]+),([-\d.]+)\)")
REK=re.compile(r"pr54 keep-isolated: cluster (\d+) n_points=(\d+) length=([\d.]+) cm")
allrows=[]; keeps=[]
for d in sorted(glob.glob(os.path.join(W,"*_d53v"))):
    ev=os.path.basename(d)[:-len("_d53v")]
    logs=glob.glob(os.path.join(d,"wct_pr_*.log"))
    if not logs: continue
    for line in open(logs[0], errors="replace"):
        m=RE.search(line)
        if m:
            g=m.groups()
            allrows.append(dict(ev=ev,cl=int(g[0]),n=int(g[1]),L=float(g[2]),dir=float(g[3]),
                                v1=np.array([float(g[4]),float(g[5]),float(g[6])]),
                                v2=np.array([float(g[7]),float(g[8]),float(g[9])])))
        m=REK.search(line)
        if m: keeps.append((ev,int(m.group(1)),int(m.group(2)),float(m.group(3))))
print("d53v arm: %d isolated-residual DROPS, %d KEPT"%(len(allrows),len(keeps)))
n=np.array([r["n"] for r in allrows]); L=np.array([r["L"] for r in allrows])
print("  dropped residuals: n_points p50 %d p90 %d max %d | length p50 %.1f p90 %.1f max %.1f cm"
      %(np.median(n),np.percentile(n,90),n.max(),np.median(L),np.percentile(L,90),L.max()))
print("  of the drops, how many would the CURRENT floors have kept if only one moved:")
print("    n_points >= 25 : %d   length >= 30 cm : %d   (both floors are ORs)"%((n>=25).sum(),(L>=30).sum()))
if keeps:
    kn=np.array([k[2] for k in keeps]); kL=np.array([k[3] for k in keeps])
    print("  kept residuals:    n_points p50 %d min %d | length p50 %.1f min %.1f cm"%(np.median(kn),kn.min(),np.median(kL),kL.min()))
# now: drops within 20 cm of a scan candidate's stop
hits=0; cands=0; per=[]
for fn in sorted(os.listdir(PREP)):
    if not fn.startswith("smprep-"): continue
    p=json.load(open(os.path.join(PREP,fn)))
    mu=p.get("muon") or {}
    if not mu.get("x"): continue
    MX=np.array([mu["x"],mu["y"],mu["z"]]).T
    stop=MX[int(np.argmin(np.array(mu["rr"])))]
    cands+=1
    mine=[r for r in allrows if r["ev"]==p["event"]
          and min(np.linalg.norm(r["v1"]-stop),np.linalg.norm(r["v2"]-stop))<=20.0]
    if mine:
        hits+=1
        per.append((p["event"],p["cluster_id"],mine))
print("  candidates with >=1 dropped residual within 20 cm of the stop: %d / %d (%.0f%%)"%(hits,cands,100.0*hits/cands))
for ev,cl,mine in per[:8]:
    for r in mine:
        print("     %-12s/%-4d drop cluster %-4d n=%-3d L=%5.2f cm dir=%5.2f"%(ev,cl,r["cl"],r["n"],r["L"],r["dir"]))
