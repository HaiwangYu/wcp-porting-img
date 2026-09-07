#!/usr/bin/env python3
"""doc 30 -- member-content hash gate between two PR arms, either detector.

Forked BY DUPLICATION from pdhd/docs/scripts/d02_hash_gate.py (untouched).
Three things differ, all of them load-bearing here:

  * the work root and the event manifest are arguments, so one script gates the
    PDHD 61-event and the PDVD 120-event arms;
  * tracking-stm.root and tracking-pr.root are hashed by TREE CONTENT, not by
    md5 -- ROOT embeds a UUID and timestamps, so raw bytes never compare equal
    (the tarball trap, M2).  The tree list is EXPLICIT: the default list in
    qlport/scripts/hash_root_trees.py covers only T_rec_charge, which would
    make this gate blind to T_proj_data -- exactly the tree doc 30's change
    touches.  A gate that cannot see the thing it gates is worse than none;

  * the calib dump is compared with the *_ms timer keys stripped (a raw diff
    trips on the timer, not on physics).

ROUND 3 CORRECTION (2026-09-07), and the gate now checks FIVE products.
Naming T_proj_data in --trees was necessary and NOT sufficient: hash_root_trees
.py's row-sorted hash skips jagged branches, every T_proj_data branch is jagged,
so its per-tree digest was the constant sha256("") in every file.  Rounds 1 and
2 therefore ran a gate that named the display tree and could not read it.  The
tree is now hashed by d30_hash_proj.py (sorted multiset of cell tuples) as a
fifth product.  The round-1 arms were re-checked with it after the fact --
doc 30 sec 13.2.  Runs of this script from before 2026-09-07 report FOUR
products; the PASS lines they printed remain true of those four.

Usage: d30_hash_gate.py <work_root> <base_tag> <arm_tag>
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

HRT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), 'qlport', 'scripts', 'hash_root_trees.py')
HP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'd30_hash_proj.py')
TREES = 'T_rec_charge,T_proj_data,T_stm_pass,T_stm_eval,T_stm_michel,T_stm_michel_pts,T_tagger,T_kine'

root, base, arm = sys.argv[1], sys.argv[2], sys.argv[3]


def zip_members(p):
    out = {}
    with zipfile.ZipFile(p) as z:
        for n in sorted(z.namelist()):
            if n.endswith('/'):
                continue
            out[n] = hashlib.sha256(n.encode() + z.read(n)).hexdigest()
    return out


def strip_timers(o):
    if isinstance(o, dict):
        return {k: strip_timers(v) for k, v in o.items() if not k.endswith('_ms')}
    if isinstance(o, list):
        return [strip_timers(v) for v in o]
    return o


def calib_hash(d):
    fs = glob.glob(os.path.join(d, 'calib-pr-evt*.json'))
    if not fs:
        return 'NONE'
    return hashlib.sha256(json.dumps(strip_timers(json.load(open(fs[0]))),
                                     sort_keys=True).encode()).hexdigest()


def proj_hash(d, name):
    """T_proj_data by cell content -- see the ROUND 3 CORRECTION above."""
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return 'NONE'
    r = subprocess.run([sys.executable, HP, p], capture_output=True, text=True)
    f = r.stdout.split()
    return ' '.join([f[0]] + f[2:]) if len(f) >= 3 else 'ERR'


def root_hash(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return 'NONE'
    r = subprocess.run([sys.executable, HRT, '--trees', TREES, p],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return 'ERR:' + r.stderr.strip().splitlines()[-1][:60]
    return r.stdout.split()[0]


events = sorted({os.path.basename(d)[:-len(base) - 1]
                 for d in glob.glob(os.path.join(root, '*_' + base))},
                key=lambda e: (e.split('_')[0], int(e.split('_')[1])))
npass = nfail = nmiss = 0
for e in events:
    db, da = os.path.join(root, e + '_' + base), os.path.join(root, e + '_' + arm)
    zb, za = os.path.join(db, 'mabc-pr.zip'), os.path.join(da, 'mabc-pr.zip')
    if not (os.path.exists(zb) and os.path.exists(za)):
        print('%-14s MISSING' % e)
        nmiss += 1
        continue
    mb, ma = zip_members(zb), zip_members(za)
    parts = [('mabc-pr.zip', mb == ma),
             ('calib', calib_hash(db) == calib_hash(da)),
             ('tracking-stm.root', root_hash(db, 'tracking-stm.root') == root_hash(da, 'tracking-stm.root')),
             ('tracking-pr.root', root_hash(db, 'tracking-pr.root') == root_hash(da, 'tracking-pr.root')),
             ('T_proj_data', proj_hash(db, 'tracking-stm.root') == proj_hash(da, 'tracking-stm.root')
                             and proj_hash(db, 'tracking-pr.root') == proj_hash(da, 'tracking-pr.root'))]
    bad = [n for n, ok in parts if not ok]
    if not bad:
        npass += 1
        continue
    nfail += 1
    extra = ''
    if 'mabc-pr.zip' in bad:
        diff = [n for n in sorted(set(mb) | set(ma)) if mb.get(n) != ma.get(n)]
        extra = '  zip members differing: %d %s' % (len(diff), diff[:3])
    print('%-14s DIFF  %s%s' % (e, ','.join(bad), extra))
print('GATE %s vs %s (%s): PASS %d  FAIL %d  MISSING %d  of %d events, 5 products each'
      % (base, arm, root, npass, nfail, nmiss, len(events)))
