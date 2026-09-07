#!/usr/bin/env python3
"""Audit which PR-stage components test which fiducial volume (doc pdvd/49 sec 2).

Answers "is the curved surface actually wired to every cosmic tagger and to the
PR-tail stages?" from the COMPILED config, not from the jsonnet source.  Prints,
per config: every component carrying a `fiducial` key with its fv_tolerance in cm,
and every fiducial component instantiated.

Repro (from toolkit/):
  python3 pdvd/docs/nf_sp_img_clus/scripts/fv_consumer_audit.py <compiled.json> ...
"""
import json, sys

MM = 10.0
FVTYPES = ('PolyFiducial', 'BoxFiducial', 'CompositeFiducial', 'DetectorVolumes')


def walk(o, out):
    if isinstance(o, dict):
        if 'type' in o and isinstance(o.get('data'), dict):
            out.append(o)
        for v in o.values():
            walk(v, out)
    elif isinstance(o, list):
        for v in o:
            walk(v, out)


def cm(v):
    return [round(x / MM, 3) for x in v] if v else v


def audit(path):
    nodes = []
    walk(json.load(open(path)), nodes)
    print('=' * 76)
    print(path)
    print('=' * 76)

    rows, comps = [], []
    for n in nodes:
        d = n['data']
        if n['type'] in FVTYPES:
            comps.append(n)
        if 'fiducial' in d:
            rows.append((n['type'], n.get('name', ''), d['fiducial'],
                         tuple(cm(d.get('fv_tolerance'))) if d.get('fv_tolerance') else None,
                         tuple(cm(d.get('interior_fv_tolerance'))) if d.get('interior_fv_tolerance') else None))

    print('--- components naming a fiducial   (fv_tolerance cm, order '
          '[x_lo, x_hi, y_lo, y_hi, z_MAX, z_MIN] -- z pair reversed; '
          'negative = inset) ---')
    for t, nm, f, tol, itol in sorted(set(rows)):
        print('  %-22s %-6s -> %s' % (t, nm, f))
        print('      fv_tolerance          %s' % (list(tol) if tol else tol))
        if itol:
            print('      interior_fv_tolerance %s' % list(itol))

    print('--- fiducial components instantiated ---')
    seen = set()
    for n in comps:
        k = (n['type'], n.get('name', ''))
        if k in seen:
            continue
        seen.add(k)
        d, extra = n['data'], ''
        if n['type'] == 'PolyFiducial':
            extra = '  axis=%d slabs=%d corners=%s' % (
                d['axis'], len(d['slabs']), [len(s['corners']) for s in d['slabs']])
        elif n['type'] == 'CompositeFiducial':
            extra = '  logic=%s of %s' % (d['logic'], d['fiducials'])
        elif n['type'] == 'BoxFiducial':
            b = d['bounds']
            extra = '  x[%.4f,%.4f] y[%.4f,%.4f] z[%.4f,%.4f] cm' % (
                b['tail']['x'] / MM, b['head']['x'] / MM, b['tail']['y'] / MM,
                b['head']['y'] / MM, b['tail']['z'] / MM, b['head']['z'] / MM)
        print('  %-20s %-24s%s' % (n['type'], n.get('name', ''), extra))
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for p in sys.argv[1:]:
        audit(p)
