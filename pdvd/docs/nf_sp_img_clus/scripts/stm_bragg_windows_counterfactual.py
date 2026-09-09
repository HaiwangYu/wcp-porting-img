import json, statistics
d=json.load(open('/home/xqian/toolkit-dev/wcp-porting-img/pdhd/stm_michel_scan/prep-pdvd/smprep-039349_18-c36.json'))
m=d['muon']; v=d['verdict']
pts=sorted(zip(m['rr'],m['q']))
MIP=56000.0; FRAC=None
# find the live threshold that reproduces n_tail=4 / tail_med
for frac in [0.0,0.05,0.1,0.15,0.2,0.25,0.3]:
    live=[(r,q) for r,q in pts if q>=frac*MIP]
    t=[q for r,q in live if 0.5<=r<=3.0]; p=[q for r,q in live if 20<=r<=40]
    if t and p:
        print('frac=%.2f  n_tail=%d tail_med=%.1f  n_pl=%d pl_med=%.1f  contrast=%.4f'%(
            frac,len(t),statistics.median(t),len(p),statistics.median(p),statistics.median(t)/statistics.median(p)))
print()
print('REPORTED: n_tail=%d tail_med=%.1f n_plateau=%d plateau_med=%.1f contrast=%.4f expected=%.4f bar=%.4f'%(
    v['n_tail'],v['tail_med'],v['n_plateau'],v['plateau_med'],v['contrast'],v['contrast_expected'],0.6*v['contrast_expected']))
print()
frac=0.1
live=[(r,q) for r,q in pts if q>=frac*MIP]
sh=sorted([(r-8.96,q) for r,q in live if r>=8.96])
t=[q for r,q in sh if 0.5<=r<=3.0]; p=[q for r,q in sh if 20<=r<=40]
c=statistics.median(t)/statistics.median(p)
print('COUNTERFACTUAL (chain stops at the kink, same windows, frac=%.2f):'%frac)
print('  n_tail=%d tail_med=%.1f  n_plateau=%d plateau_med=%.1f  contrast=%.2f  bar=%.2f  -> %s'%(
    len(t),statistics.median(t),len(p),statistics.median(p),c,0.6*v['contrast_expected'],
    'PASSES no_bragg' if c>=0.6*v['contrast_expected'] else 'still fails'))
