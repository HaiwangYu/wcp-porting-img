#!/usr/bin/env python3
"""doc 30: which variable sets the STM stage's resident cost? Fit log-log on one arm."""
import math, sys
rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[1])]
hdr = rows[0]; idx = {c: i for i, c in enumerate(hdr)}
D = []
for r in rows[1:]:
    g = lambda c: float(r[idx[c]])
    if g("nfit") < 1 or g("stm_gb") <= 0: continue
    D.append(dict(ev=r[idx["event"]], stm=g("stm_gb"), nfit=g("nfit"), npts=g("sum_npts"),
                  maxn=g("max_npts"), load=g("load_gb"), nclus=g("nclus"), nstm1=g("nstm1")))
print("n events with fits =", len(D))

def fit(name, f):
    xs = [f(d) for d in D]; ys = [d["stm"] for d in D]
    lx = [math.log(x) for x in xs]; ly = [math.log(y) for y in ys]
    n = len(lx); mx = sum(lx)/n; my = sum(ly)/n
    sxx = sum((a-mx)**2 for a in lx); sxy = sum((a-mx)*(b-my) for a, b in zip(lx, ly))
    b = sxy/sxx; a = my - b*mx
    ss_t = sum((y-my)**2 for y in ly); ss_r = sum((y-(a+b*x))**2 for x, y in zip(lx, ly))
    r2 = 1 - ss_r/ss_t
    ratios = sorted(y/x for x, y in zip(xs, ys))
    print("  %-22s exponent=%.2f  R2=%.3f   GB per unit: p10=%.4g p50=%.4g p90=%.4g  spread=%.1fx"
          % (name, b, r2, ratios[int(.1*len(ratios))], ratios[len(ratios)//2],
             ratios[int(.9*len(ratios))],
             ratios[int(.9*len(ratios))]/max(ratios[int(.1*len(ratios))], 1e-9)))

print("STM-stage resident (GB) vs:")
for nm, f in [("nfit", lambda d: d["nfit"]),
              ("sum_npts", lambda d: d["npts"]),
              ("max_npts", lambda d: d["maxn"]),
              ("nclus", lambda d: d["nclus"]),
              ("nstm1 (tagged)", lambda d: max(d["nstm1"], 1)),
              ("load_gb", lambda d: d["load"]),
              ("nfit * load_gb", lambda d: d["nfit"]*d["load"]),
              ("sum_npts * load_gb", lambda d: d["npts"]*d["load"])]:
    fit(nm, f)
