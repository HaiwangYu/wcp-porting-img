"""Positive gate: on events where the binary DID find a kink (kink < npts),
does the persisted tagger stop sit at the kink index of tagger_fit, or at its
last point?  And does kink.py's re-implementation return the same index?"""
import json, glob, os, re, math, subprocess
PREP='/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd/'
WORK='/home/xqian/toolkit-dev/wcp-porting-img/pdvd/work/'
# collect (event, cluster) -> kink,npts from the logs
kn={}
for f in glob.glob(WORK+'*_d53v/wct_pr_*.log'):
    ev=os.path.basename(os.path.dirname(f))[:-5]
    for line in open(f, errors='ignore'):
        if 'persist_stm_fit' not in line: continue
        m=re.search(r'cluster (\d+) stmfit pass=(\S+) status=(\S+) kink=(\d+).*npts=(\d+)', line)
        if m: kn[(ev,int(m.group(1)))]=(int(m.group(4)),int(m.group(5)))
print('persist_stm_fit rows parsed:', len(kn))
hits=[]
for p in sorted(glob.glob(PREP+'smprep-*.json')):
    b=os.path.basename(p)[len('smprep-'):-len('.json')]
    ev,cl=b.rsplit('-c',1); cl=int(cl)
    key=(ev,cl)
    if key not in kn: continue
    k,n=kn[key]
    if k>=n or n<30: continue
    d=json.load(open(p))
    if d.get('arm')!='d53v': continue
    f=(d.get('verdict') or {}).get('tagger_fit') or []
    if not f: continue
    X,Y,Z=f[0]['x'],f[0]['y'],f[0]['z']
    if len(X)!=n: continue
    v=d['verdict']; sp=(v['tagger_stop_x'],v['tagger_stop_y'],v['tagger_stop_z'])
    d_last=math.dist(sp,(X[-1],Y[-1],Z[-1]))
    d_kink=math.dist(sp,(X[k],Y[k],Z[k])) if k<n else float('nan')
    hits.append((ev,cl,k,n,d_kink,d_last))
print('candidates with a real kink and a matching persisted trajectory:', len(hits))
print('  event        cl   kink npts  |stop-pts[kink]|  |stop-pts[last]|')
for h in hits[:25]:
    print('  %-12s %-4d %4d %4d   %10.3f cm    %10.3f cm'%h)
if hits:
    nk=sum(1 for h in hits if h[4]<0.5); nl=sum(1 for h in hits if h[5]<0.5)
    print()
    print('stop within 0.5 cm of the KINK point : %d/%d'%(nk,len(hits)))
    print('stop within 0.5 cm of the LAST point : %d/%d'%(nl,len(hits)))
