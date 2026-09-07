#!/usr/bin/env python3
"""doc 30 round 3 -- WHICH product differs between two PR arms, per tree.

d30_hash_gate.py answers "identical or not" and is the right tool when the
answer must be "identical".  This one is its complement, for the knob-ON arm:
the pad filter is *meant* to change the display product, so the claim to prove
is narrower and stronger -- "it changes T_proj_data and the calib dump's proj
block, and NOTHING else".  A pass/fail gate cannot express that; a per-tree
diff can, and it is the empirical form of the consumer census in doc 30 sec
13.1 (which is only a grep).

Per event it compares:
  * every tree of tracking-stm.root and tracking-pr.root, per tree, by CONTENT
    hash (hash_root_trees.py --per-tree; ROOT bytes never compare equal, M2);
  * mabc-pr.zip by member content (hash_archive.py semantics, inlined);
  * calib-pr-evt*.json twice -- whole (minus the *_ms timers, which are a
    wall-clock field and always differ) and again with every "proj" block
    dropped, so a difference confined to the display block is visible as such.

Usage: d30_tree_diff.py <work_root> <base_tag> <arm_tag> [--trees a,b,c]
"""
import argparse, glob, hashlib, json, os, subprocess, sys, zipfile

HRT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), 'qlport', 'scripts', 'hash_root_trees.py')
TREES = ('T_rec_charge,T_proj_data,T_stm_fit,T_stm_pass,T_stm_eval,'
         'T_stm_michel,T_stm_michel_pts,T_tagger,T_kine')

ap = argparse.ArgumentParser()
ap.add_argument('root'); ap.add_argument('base'); ap.add_argument('arm')
ap.add_argument('--trees', default=TREES)
ap.add_argument('--files', default='tracking-stm.root,tracking-pr.root')
a = ap.parse_args()


def zip_members(p):
    if not os.path.exists(p):
        return None
    with zipfile.ZipFile(p) as z:
        return {n: hashlib.sha256(n.encode() + z.read(n)).hexdigest()
                for n in sorted(z.namelist()) if not n.endswith('/')}


def strip(o, drop_proj):
    if isinstance(o, dict):
        return {k: strip(v, drop_proj) for k, v in o.items()
                if not k.endswith('_ms') and not (drop_proj and k == 'proj')}
    if isinstance(o, list):
        return [strip(v, drop_proj) for v in o]
    return o


def calib(d, drop_proj):
    fs = glob.glob(os.path.join(d, 'calib-pr-evt*.json'))
    if not fs:
        return 'NONE'
    return hashlib.sha256(json.dumps(strip(json.load(open(fs[0])), drop_proj),
                                     sort_keys=True).encode()).hexdigest()


HP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'd30_hash_proj.py')


def per_tree(d, name, trees):
    """{tree: hash}.

    hash_root_trees.py --per-tree prints the file hash on column 0 and then one
    INDENTED line per tree, '<hash>  <tree>  [notes]'.  T_proj_data is handled
    separately by d30_hash_proj.py: hash_root_trees.py's row-sorted hash drops
    jagged branches and every T_proj_data branch is jagged, so its per-tree hash
    is the constant sha256("") -- see d30_hash_proj.py's docstring.
    """
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    tl = ','.join(t for t in trees.split(',') if t != 'T_proj_data')
    r = subprocess.run([sys.executable, HRT, '--trees', tl, '--per-tree', p],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {'ERR': r.stderr.strip().splitlines()[-1][:80]}
    out = {}
    for line in r.stdout.splitlines():
        if not line.startswith(' '):
            continue                      # the file-level line
        f = line.split()
        if len(f) >= 2:
            out[f[1]] = f[0]
    if 'T_proj_data' in trees.split(','):
        rp = subprocess.run([sys.executable, HP, p], capture_output=True, text=True)
        fp = rp.stdout.split()
        # "<hash>  <path>  blocks=N cells=N" -- fold the counts in so a changed
        # cell COUNT is visible even if a hash collision were possible.
        out['T_proj_data'] = ' '.join([fp[0]] + fp[2:]) if len(fp) >= 3 else 'ERR'
    return out


events = sorted({os.path.basename(d)[:-len(a.base) - 1]
                 for d in glob.glob(os.path.join(a.root, '*_' + a.base))},
                key=lambda e: (e.split('_')[0], int(e.split('_')[1])))

allsame, changed = [], {}
for e in events:
    db, da_ = os.path.join(a.root, e + '_' + a.base), os.path.join(a.root, e + '_' + a.arm)
    diffs = []
    for fn in a.files.split(','):
        hb, ha = per_tree(db, fn, a.trees), per_tree(da_, fn, a.trees)
        if hb is None and ha is None:
            continue
        if hb is None or ha is None:
            diffs.append(fn + ':MISSING')
            continue
        for t in sorted(set(hb) | set(ha)):
            if hb.get(t) != ha.get(t):
                diffs.append('%s:%s' % (fn, t))
    zb, za = zip_members(os.path.join(db, 'mabc-pr.zip')), zip_members(os.path.join(da_, 'mabc-pr.zip'))
    if zb != za:
        diffs.append('mabc-pr.zip')
    if calib(db, False) != calib(da_, False):
        diffs.append('calib(proj kept)' if calib(db, True) == calib(da_, True) else 'calib(BEYOND proj)')
    print('%-14s %s' % (e, ','.join(diffs) if diffs else 'IDENTICAL on every product'))
    if not diffs:
        allsame.append(e)
    for d in diffs:
        changed.setdefault(d, []).append(e)

print('\nDIFF %s vs %s: %d of %d events identical everywhere' % (a.base, a.arm, len(allsame), len(events)))
for k in sorted(changed):
    print('  %-28s changed on %d/%d events' % (k, len(changed[k]), len(events)))
