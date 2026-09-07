#!/usr/bin/env python3
"""doc 30 round 3 -- a content hash of T_proj_data that is not vacuous.

WHY THIS EXISTS (a gate blindness found in round 3, applying to rounds 1-2).

qlport/scripts/hash_root_trees.py's default (row-sorted) hash SKIPS jagged
branches: _rowsorted_hash drops every branch with dtype object, and when that
leaves no columns it returns sha256("") for the tree.  EVERY branch of
T_proj_data is jagged, so its per-tree hash is the constant
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 -- sha256 of
the empty string -- for every file ever written.

So passing --trees T_proj_data (doc 30 sec 5, and d30_hash_gate.py's docstring)
named the tree but did not hash it.  The list was explicit and the gate was
still blind: naming a tree is not the same as the tool being able to read it.
hash_root_trees.py --ordered DOES fold jagged branches in, but it is
sequence-sensitive and T_rec_charge's row order is run-dependent, so it cannot
be used for the whole file.

This hashes T_proj_data on its own terms.  The tree is one entry holding N
blocks (one per cluster fit / STM pass); cluster_id is one int per block and
channel/time_slice/charge/charge_err/charge_pred are one vector per block, one
element per CELL.  The hash is over the sorted multiset of
(cluster_id, channel, time_slice, charge, charge_err, charge_pred) cell tuples,
so it is insensitive to block and cell ORDER but sensitive to every value --
which is exactly the question "is this the same set of displayed cells".

Prints: "<hash>  <path>  blocks=<n> cells=<n>".
Usage: d30_hash_proj.py <file.root> [...]
"""
import hashlib, sys
import numpy as np
import uproot

NAN = np.float64(-1.234567890123456e300)

def hash_one(path):
    try:
        f = uproot.open(path)
    except Exception as e:
        return None, 'ERR:' + type(e).__name__, 0, 0
    if 'T_proj_data' not in {k.split(';')[0] for k in f.keys()}:
        return None, 'ABSENT', 0, 0
    t = f['T_proj_data']
    cid = t['cluster_id'].array(library='np')[0]
    cols = {b: t[b].array(library='np')[0]
            for b in ('channel', 'time_slice', 'charge', 'charge_err', 'charge_pred')}
    nblocks = len(cid)
    rows = []
    for i in range(nblocks):
        ch = np.asarray(cols['channel'][i], dtype=np.int64)
        ts = np.asarray(cols['time_slice'][i], dtype=np.int64)
        q = np.asarray(cols['charge'][i], dtype=np.float64)
        qe = np.asarray(cols['charge_err'][i], dtype=np.float64)
        qp = np.asarray(cols['charge_pred'][i], dtype=np.float64)
        q = np.where(np.isnan(q), NAN, q)
        qe = np.where(np.isnan(qe), NAN, qe)
        qp = np.where(np.isnan(qp), NAN, qp)
        n = len(ch)
        if n == 0:
            continue
        rows.append(np.rec.fromarrays(
            [np.full(n, int(cid[i]), dtype=np.int64), ch, ts, q, qe, qp],
            names='cid,ch,ts,q,qe,qp'))
    if not rows:
        return hashlib.sha256(b'|empty|').hexdigest(), '', nblocks, 0
    allrows = np.concatenate(rows)
    allrows.sort(order=['cid', 'ch', 'ts', 'q', 'qe', 'qp'])
    h = hashlib.sha256()
    for nm in ('cid', 'ch', 'ts', 'q', 'qe', 'qp'):
        h.update(nm.encode())
        h.update(np.ascontiguousarray(allrows[nm]).tobytes())
    return h.hexdigest(), '', nblocks, len(allrows)

if __name__ == '__main__':
    for p in sys.argv[1:]:
        d, err, nb, nc = hash_one(p)
        print('%s  %s  blocks=%d cells=%d' % (d if d else err, p, nb, nc))
