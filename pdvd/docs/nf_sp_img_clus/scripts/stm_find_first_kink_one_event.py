"""Re-run find_first_kink's arithmetic on the PERSISTED tagger trajectory.

Gated against the production binary: the log says kink=228 (= npts, the
no-kink sentinel), so a faithful re-run must also find no kink.  Fiducial
and dead-wire checks are assumed to PASS (they can only reject more).
"""
import json, math
MIP=56000.0
d=json.load(open('/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd/smprep-039349_18-c36.json'))
f=d['verdict']['tagger_fit'][0]
P=list(zip(f['x'],f['y'],f['z'])); Q=f['dqdx']; n=len(P)
dx=[0.0]*n
for i in range(n):
    a=P[max(0,i-1)]; b=P[min(n-1,i+1)]
    dx[i]=math.dist(a,b)/ (2 if 0<i<n-1 else 1)
dQ=[Q[i]*dx[i] for i in range(n)]
def sub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def mag(v): return math.sqrt(v[0]**2+v[1]**2+v[2]**2)
def ang(a,b):
    ma,mb=mag(a),mag(b)
    if ma==0 or mb==0: return 0.0
    return math.degrees(math.acos(max(-1,min(1,(a[0]*b[0]+a[1]*b[1]+a[2]*b[2])/(ma*mb)))))
drift=(1.0,0.0,0.0)
refl=[0.0]*n; para=[0.0]*n
for i in range(n):
    a1=0.0; a2=0.0
    for j in range(6):
        v10=sub(P[i],P[i-j-1]) if i>j else (0,0,0)
        v20=sub(P[i+j+1],P[i]) if i+j+1<n else (0,0,0)
        if j==0:
            if mag(v10)>0 and mag(v20)>0: a1=ang(v10,v20)
            if mag(v10)>0: a2=abs(ang(v10,drift)-90.0)
            if mag(v20)>0: a2=max(a2,abs(ang(v20,drift)-90.0))
        else:
            if mag(v10)!=0 and mag(v20)!=0:
                a1=min(ang(v10,v20),a1)
                a2=min(max(abs(ang(v10,drift)-90.0),abs(ang(v20,drift)-90.0)),a2)
    refl[i]=a1; para[i]=a2
ave=[0.0]*n; maxn=[-1]*n
for i in range(n):
    s=0.0; ns=0; ma=0.0; mn=-1
    for j in (-2,-1,0,1,2):
        k=i+j
        if 0<=k<n and para[k]>12:
            s+=refl[k]**2; ns+=1
            if refl[k]>ma: ma=refl[k]; mn=k
    ave[i]=math.sqrt(s/ns) if ns else 0.0
    maxn[i]=mn
def sums(i):
    fQ=fx=bQ=bx=0.0
    for k in range(10):
        if i>=k+1: fQ+=dQ[i-k-1]; fx+=dx[i-k-1]
        if i+k+1<n: bQ+=dQ[i+k+1]; bx+=dx[i+k+1]
    return fQ/((fx+1e-9)*MIP), bQ/((bx+1e-9)*MIP)
print('  i  refl   para   ave   maxn  angle3 angle3p  |v10|  |v20|   sum_fQ sum_bQ  gateA gateB  chargeA chargeB')
hits=[]
for i in range(n):
    if not (refl[i]>20 and ave[i]>10): continue
    v10=sub(P[i],P[0]); v20=sub(P[-1],P[i]); a3=ang(v10,v20)
    a3p=a3
    if i+1<n:
        a3p=ang(sub(P[i+1],P[0]),sub(P[-1],P[i+1]))
    if (a3<20 and ave[i]<20) or a3<7.5 or i<=4: continue
    gA = a3>30 and refl[i]>25.5 and ave[i]>12.5
    gB = a3>40 and a3>a3p and mag(v10)>5 and mag(v20)>5
    fQ,bQ=sums(i)
    cA = fQ>0.6 and bQ>0.6
    cB = fQ+bQ>1.4 and (fQ>0.8 or bQ>0.8) and mag(v10)>10 and mag(v20)>10
    star='  <== ACCEPT' if ((gA or gB) and (cA or cB) and i+2<n) else ''
    print('%4d %6.1f %6.1f %6.1f %5d %7.1f %7.1f %7.2f %7.2f  %6.2f %6.2f   %d %d      %d %d%s'
          %(i,refl[i],para[i],ave[i],maxn[i],a3,a3p,mag(v10),mag(v20),fQ,bQ,gA,gB,cA,cB,star))
    if (gA or gB) and (cA or cB) and i+2<n: hits.append(i)
print()
print('candidates that would be ACCEPTED by sweep 1:', hits or 'NONE  -> falls through to sweep 2 / sentinel', )
