"""For each unfitted lump: does the Steiner stage even have points there?"""
import re, os, json, glob, zipfile, numpy as np
from scipy.spatial import cKDTree
W="/home/xqian/toolkit-dev/wcp-porting-img/pdvd/work"
PREP="/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd"
RE=re.compile(r"pr54 isolated-residual drop: cluster (\d+) n_points=(\d+) length=([\d.]+) cm "
              r"dir_mag=([\d.]+) cm v1=\(([-\d.]+),([-\d.]+),([-\d.]+)\) v2=\(([-\d.]+),([-\d.]+),([-\d.]+)\)")
def drops_for(ev):
    logs=glob.glob(os.path.join(W,ev+"_d53v","wct_pr_*.log"))
    out=[]
    if not logs: return out
    for line in open(logs[0],errors="replace"):
        m=RE.search(line)
        if m:
            g=m.groups()
            out.append((int(g[1]),float(g[2]),np.array([float(g[4]),float(g[5]),float(g[6])]),
                                              np.array([float(g[7]),float(g[8]),float(g[9])])))
    return out
def steiner(ev):
    zp=os.path.join(W,ev+"_d53v","mabc-pr.zip")
    with zipfile.ZipFile(zp) as z:
        g=json.loads(z.read("data/0/0-steiner_graph-global.json"))
        t=json.loads(z.read("data/0/0-steiner_terminals-global.json"))
    return (np.c_[g["x"],g["y"],g["z"]], np.array(g["cluster_id"]),
            np.c_[t["x"],t["y"],t["z"]], np.array(t["cluster_id"]))
cache={}
print("%-13s %-5s %5s %9s  %7s %8s  %s"%("event","clus","blobs","charge","stein","terms","pr54 drop"))
nd=ns=0
for fn in sorted(os.listdir(PREP)):
    if not fn.startswith("smprep-"): continue
    p=json.load(open(os.path.join(PREP,fn)))
    mu=p.get("muon") or {}; segs=(p.get("pf") or {}).get("seg") or []; im=p.get("image_near") or {}
    if not mu.get("x") or not segs or not im.get("x"): continue
    MX=np.array([mu["x"],mu["y"],mu["z"]]).T
    stop=MX[int(np.argmin(np.array(mu["rr"])))]
    SP=np.array([[x,y,z] for s in segs for x,y,z in zip(s["x"],s["y"],s["z"])])
    IX=np.array([im["x"],im["y"],im["z"]]).T; Q=np.array(im["q"]); B=np.array(im["b"])
    dd=np.linalg.norm(IX-stop,axis=1); m=(dd<=20)&(B==1)
    if m.sum()==0: continue
    dfit,_=cKDTree(SP).query(IX[m],k=1); un=dfit>3.0
    if un.sum()==0: continue
    P=IX[m][un]; q=Q[m][un]
    t=cKDTree(P); seen=np.zeros(len(P),bool); best=None
    for i in range(len(P)):
        if seen[i]: continue
        st=[i]; seen[i]=True; grp=[i]
        while st:
            j=st.pop()
            for k in t.query_ball_point(P[j],3.0):
                if not seen[k]: seen[k]=True; st.append(k); grp.append(k)
        if best is None or q[grp].sum()>best[1]: best=(len(grp),q[grp].sum(),P[grp])
    if best[0]<20 or best[1]<2e5: continue
    ev=p["event"]; cid=p["cluster_id"]
    if ev not in cache: cache[ev]=steiner(ev)
    SG,SGC,ST,STC=cache[ev]
    lump=best[2]
    dsg=cKDTree(lump).query(SG,k=1)[0]; dst=cKDTree(lump).query(ST,k=1)[0]
    nsg=int((dsg<3).sum()); nst=int((dst<3).sum())
    dr=[d for d in drops_for(ev) if min(np.linalg.norm(lump-d[2],axis=1).min(),
                                        np.linalg.norm(lump-d[3],axis=1).min())<=5.0]
    tag="n=%d L=%.1f"%(dr[0][0],dr[0][1]) if dr else "--"
    if dr: nd+=1
    else: ns+=1
    print("%-13s %-5d %5d %9.2e  %7d %8d  %s"%(ev,cid,best[0],best[1],nsg,nst,tag))
print("with a drop: %d   without: %d"%(nd,ns))
