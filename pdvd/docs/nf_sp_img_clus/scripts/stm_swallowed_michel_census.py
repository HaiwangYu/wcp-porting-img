"""As census.py, plus the TURN at the junction where the last chain segment
joins the rest -- the thing that separates a swallowed daughter from a
straight overshoot.  Angle = between the mean direction over the 10 cm
BEFORE the junction and the mean direction over the last segment."""
import json, glob, statistics, math
MIP=56000.0; MIPMED=48000.0; FRAC=0.15
TL,TH,PL,PH=0.5,3.0,20.0,40.0
def med(v): return statistics.median(v) if v else None
def contrast(pts, shift=0.0):
    live=[(r-shift,q) for r,q in pts if q>=FRAC*MIP and r>=shift]
    t=[q for r,q in live if TL<=r<=TH]; p=[q for r,q in live if PL<=r<=PH]
    if len(t)<3 or len(p)<3: return None
    pm=med(p); return med(t)/pm if pm and pm>0 else None
def unit(a,b):
    v=[b[i]-a[i] for i in range(3)]; n=math.sqrt(sum(t*t for t in v))
    return [t/n for t in v] if n>0 else None
rows=[]
for f in sorted(glob.glob('/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd/smprep-*.json')):
    try: d=json.load(open(f))
    except Exception: continue
    v=d.get('verdict') or {}
    if d.get('arm')!='d53v' or 'no_bragg' not in (v.get('reject_names') or []): continue
    m=d.get('muon') or {}
    if not m.get('rr'): continue
    role=(d['pf'].get('chain_role') or {}); last=[k for k,r in role.items() if r==1]
    if len(last)!=1: continue
    seg=next((s for s in d['pf'].get('seg') or [] if str(s.get('id'))==last[0]), None)
    if not seg: continue
    L=seg.get('len_cm') or 0.0; mip=(seg.get('dqdx_med') or 0.0)/MIPMED
    if not (0.3<mip<2.0 and L<=25.0): continue
    pts=list(zip(m['rr'],m['q'])); c1=contrast(pts,L); exp=v.get('contrast_expected') or 0.0
    if c1 is None or exp<=0 or c1<0.6*exp: continue
    # turn at the junction, from the chain profile ordered by rr
    P=sorted(zip(m['rr'],m['x'],m['y'],m['z']))
    def at(r):
        return min(P,key=lambda p:abs(p[0]-r))[1:]
    a=unit(at(L),at(0.0))            # along the last segment, junction -> stop
    b=unit(at(min(L+10.0,P[-1][0])),at(L))   # the 10 cm of muon before the junction
    ang=-1.0
    if a and b:
        ang=math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(a,b))))))
    rows.append((v.get('contrast'),d['event'],d['cluster_id'],last[0],L,mip,c1,0.6*exp,ang))
rows.sort()
print('no_bragg + Michel-shaped last chain segment + truncation clears the bar:', len(rows))
print('  event        cl   seg      L_cm  mip   contrast -> trunc  bar   turn_deg')
for r in rows:
    print('  %-12s %-4s %-8s %5.2f %5.2f   %6.3f    %6.2f %5.2f   %6.1f'%(r[1],r[2],r[3],r[4],r[5],r[0],r[6],r[7],r[8]))
big=[r for r in rows if r[8]>=30]
print()
print('of these, turn >= 30 deg (the michel_min_kink_deg bar):', len(big))
