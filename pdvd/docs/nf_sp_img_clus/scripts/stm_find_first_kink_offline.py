"""find_first_kink re-implementation, run over every d53v candidate where the
binary reported a real kink -- a POSITIVE gate on the arithmetic in kink.py.
Fiducial-volume and dead-region checks are not available offline and are
assumed to pass; they can only reject more, so disagreements of the form
'mine fires earlier than the binary' are expected at some rate."""
import json, glob, os, re, math
MIP=56000.0
def sub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def mag(v): return math.sqrt(v[0]**2+v[1]**2+v[2]**2)
def ang(a,b):
    ma,mb=mag(a),mag(b)
    if ma==0 or mb==0: return 0.0
    return math.degrees(math.acos(max(-1,min(1,(a[0]*b[0]+a[1]*b[1]+a[2]*b[2])/(ma*mb)))))
def find_first_kink(P,Q):
    n=len(P)
    dx=[0.0]*n
    for i in range(n):
        a=P[max(0,i-1)]; b=P[min(n-1,i+1)]
        dx[i]=math.dist(a,b)/(2 if 0<i<n-1 else 1)
    dQ=[Q[i]*dx[i] for i in range(n)]
    drift=(1.0,0.0,0.0); refl=[0.0]*n; para=[0.0]*n
    for i in range(n):
        a1=0.0;a2=0.0
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
        s=0.0;ns=0;ma=0.0;mn=-1
        for j in (-2,-1,0,1,2):
            k=i+j
            if 0<=k<n and para[k]>12:
                s+=refl[k]**2; ns+=1
                if refl[k]>ma: ma=refl[k]; mn=k
        ave[i]=math.sqrt(s/ns) if ns else 0.0; maxn[i]=mn
    def sums(i):
        fQ=fx=bQ=bx=0.0
        for k in range(10):
            if i>=k+1: fQ+=dQ[i-k-1]; fx+=dx[i-k-1]
            if i+k+1<n: bQ+=dQ[i+k+1]; bx+=dx[i+k+1]
        return fQ/((fx+1e-9)*MIP), bQ/((bx+1e-9)*MIP)
    def a3s(i):
        v10=sub(P[i],P[0]); v20=sub(P[-1],P[i]); a=ang(v10,v20)
        ap=a
        if i+1<n: ap=ang(sub(P[i+1],P[0]),sub(P[-1],P[i+1]))
        return a,ap,mag(v10),mag(v20)
    for sweep in (1,2):
        for i in range(n):
            lim=10 if sweep==1 else 15
            if not (refl[i]>20 and ave[i]>lim): continue
            a3,a3p,m10,m20=a3s(i)
            if (a3<20 and ave[i]<20) or a3<7.5 or i<=4: continue
            fQ,bQ=sums(i)
            if sweep==1:
                if not ((a3>30 and refl[i]>25.5 and ave[i]>12.5) or
                        (a3>40 and a3>a3p and m10>5 and m20>5)): continue
                if not ((fQ>0.6 and bQ>0.6) or
                        (fQ+bQ>1.4 and (fQ>0.8 or bQ>0.8) and m10>10 and m20>10)): continue
            else:
                if not a3>30: continue
                if not (fQ>0.6 and bQ>0.6): continue
            if i+2<n: return maxn[i]
    return n
PREP='/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd/'
WORK='/home/xqian/toolkit-dev/wcp-porting-img/pdvd/work/'
kn={}
for f in glob.glob(WORK+'*_d53v/wct_pr_*.log'):
    ev=os.path.basename(os.path.dirname(f))[:-5]
    for line in open(f, errors='ignore'):
        if 'persist_stm_fit' not in line: continue
        m=re.search(r'cluster (\d+) stmfit .* kink=(\d+).*npts=(\d+)', line)
        if m: kn[(ev,int(m.group(1)))]=(int(m.group(2)),int(m.group(3)))
same=0; tot=0; diff=[]
for p in sorted(glob.glob(PREP+'smprep-*.json')):
    b=os.path.basename(p)[len('smprep-'):-len('.json')]
    ev,cl=b.rsplit('-c',1); cl=int(cl)
    if (ev,cl) not in kn: continue
    k,n=kn[(ev,cl)]
    if k>=n or n<30: continue
    d=json.load(open(p))
    if d.get('arm')!='d53v': continue
    f=(d.get('verdict') or {}).get('tagger_fit') or []
    if not f or len(f[0]['x'])!=n: continue
    P=list(zip(f[0]['x'],f[0]['y'],f[0]['z'])); Q=f[0]['dqdx']
    mine=find_first_kink(P,Q); tot+=1
    if mine==k: same+=1
    else: diff.append((ev,cl,k,mine,n))
print('positive gate over d53v candidates with a real binary kink:')
print('  exact index agreement: %d/%d'%(same,tot))
print('  first 15 disagreements (event, cl, binary, mine, npts):')
for x in diff[:15]: print('   ', x)
