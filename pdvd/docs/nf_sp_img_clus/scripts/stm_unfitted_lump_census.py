"""How often does in-bundle charge near the stop have NO fitted segment through it?

Reads only the shipped scan payloads (the same JSON the display reads), so the
numbers are the display's own point set.  A point counts as UNFITTED when no
fit point of any segment in the panel lies within 3 cm of it.
"""
import json, os, sys, numpy as np
from scipy.spatial import cKDTree
det = sys.argv[1]
D = "/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-%s" % det
rows = []
for fn in sorted(os.listdir(D)):
    if not fn.startswith("smprep-"):
        continue
    d = json.load(open(os.path.join(D, fn)))
    mu = d.get("muon") or {}
    if not mu.get("x"):
        continue
    MX = np.array([mu["x"], mu["y"], mu["z"]]).T
    rr = np.array(mu["rr"])
    stop = MX[int(np.argmin(rr))]
    segs = (d.get("pf") or {}).get("seg") or []
    SP = np.array([[x, y, z] for s in segs for x, y, z in zip(s["x"], s["y"], s["z"])])
    im = d.get("image_near") or {}
    if not im.get("x") or SP.size == 0:
        continue
    IX = np.array([im["x"], im["y"], im["z"]]).T
    Q = np.array(im.get("q") or [0.0] * len(IX))
    B = np.array(im.get("b") or [1] * len(IX))
    dd = np.linalg.norm(IX - stop, axis=1)
    tree = cKDTree(SP)
    for R in (20.0,):
        m = (dd <= R) & (B == 1)
        if m.sum() == 0:
            continue
        dfit, _ = tree.query(IX[m], k=1)
        un = dfit > 3.0
        # the biggest single unfitted lump: single-link at 3 cm
        big_n, big_q = 0, 0.0
        if un.sum():
            P = IX[m][un]; q = Q[m][un]
            t = cKDTree(P); seen = np.zeros(len(P), bool)
            for i in range(len(P)):
                if seen[i]:
                    continue
                stack = [i]; seen[i] = True; grp = [i]
                while stack:
                    j = stack.pop()
                    for k in t.query_ball_point(P[j], 3.0):
                        if not seen[k]:
                            seen[k] = True; stack.append(k); grp.append(k)
                if q[grp].sum() > big_q:
                    big_q = q[grp].sum(); big_n = len(grp)
        rows.append(dict(item="%s/%d" % (d["event"], d["cluster_id"]),
                         n=int(m.sum()), q=float(Q[m].sum()),
                         nun=int(un.sum()), qun=float(Q[m][un].sum()),
                         big_n=big_n, big_q=big_q))
print("=== %s: %d candidates with a muon fit and drawn charge" % (det, len(rows)))
fr = np.array([r["qun"] / r["q"] if r["q"] > 0 else 0.0 for r in rows])
print("  unfitted share of in-bundle charge within 20 cm of the stop:"
      "  p50 %.0f%%  p90 %.0f%%  mean %.0f%%" % (100*np.median(fr), 100*np.percentile(fr, 90), 100*fr.mean()))
for thr_n, thr_q in ((20, 2e5),):
    hit = [r for r in rows if r["big_n"] >= thr_n and r["big_q"] >= thr_q]
    print("  candidates with a single unfitted lump of >=%d blobs AND >=%.0e e- : %d / %d  (%.0f%%)"
          % (thr_n, thr_q, len(hit), len(rows), 100.0*len(hit)/max(len(rows), 1)))
    for r in sorted(hit, key=lambda r: -r["big_q"])[:60]:
        print("     %-14s biggest lump %3d blobs %8.2e e-   (unfitted %3d/%3d blobs, %2.0f%% of the near charge)"
              % (r["item"], r["big_n"], r["big_q"], r["nun"], r["n"], 100*r["qun"]/max(r["q"],1)))
