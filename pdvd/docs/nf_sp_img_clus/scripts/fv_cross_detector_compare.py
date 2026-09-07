#!/usr/bin/env python3
"""Cross-detector comparison of the MEASURED curved fiducial surfaces (doc pdvd/49).

Everything plotted is re-derived from the COMPILED production PR configs -- the
PolyFiducial corner lists and the taggers' fv_tolerance -- not from the jsonnet
source, so the figures show what the taggers actually test.  The only thing read
from the cfg source is each detector's NOMINAL wall constant (XW / Y / Z), which
the polygon cannot supply: a p90 surface is inset from the wall even at the anode
face, so the extreme vertex is not the wall.

Repro (from toolkit/):
  S=$SCRATCH
  (cd pdhd && wcsonnet -A input=/dev/null -A output_dir=$S -S run=28084 -S subrun=0 \
     -S event=1 -S trigger_offset_us=0 -S readout_window_ticks=6000 \
     -o $S/pdhd_prod.json wct-pr-perevt.jsonnet)
  (cd pdhd && ... -S curved_fv=false -o $S/pdhd_flat.json wct-pr-perevt.jsonnet)
  (cd pdvd && wcsonnet -A input=/dev/null -A output_dir=$S -S run=29107 -S subrun=0 \
     -S event=1 -o $S/pdvd_prod.json wct-pr-perevt.jsonnet)
  (cd pdvd && ... -S curved_fv=false -o $S/pdvd_flat.json wct-pr-perevt.jsonnet)
  python3 pdvd/docs/nf_sp_img_clus/scripts/fv_cross_detector_compare.py \
      --pdhd-prod $S/pdhd_prod.json --pdhd-flat $S/pdhd_flat.json \
      --pdvd-prod $S/pdvd_prod.json --pdvd-flat $S/pdvd_flat.json \
      --toolkit-cfg cfg/pgrapher/experiment \
      --out-dir pdvd/docs/nf_sp_img_clus/figs --prefix 49
"""
import argparse, json, os, re, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

MM = 10.0  # compiled config is in mm; everything below is cm


# ---------------------------------------------------------------- cfg readers
def walk(o, pred, out):
    if isinstance(o, dict):
        if pred(o):
            out.append(o)
        for v in o.values():
            walk(v, pred, out)
    elif isinstance(o, list):
        for v in o:
            walk(v, pred, out)


def load_cfg(path):
    return json.load(open(path))


def find_type(cfg, tname, name=None):
    out = []
    walk(cfg, lambda o: o.get('type') == tname and (name is None or o.get('name') == name), out)
    if not out:
        return None
    return out[0]


def tagger_tolerance(cfg):
    """fv_tolerance of TaggerCheckTGM, in cm, as [x_lo, x_hi, y_lo, y_hi, z_max, z_min].

    NOTE the index order: the z pair is REVERSED relative to the y pair
    (pr.jsonnet 'Margin vector convention'), and the values are NEGATIVE = inset.
    """
    t = find_type(cfg, 'TaggerCheckTGM')
    if t is None:
        raise SystemExit('no TaggerCheckTGM in config')
    tol = t['data']['fv_tolerance']
    return [abs(v) / MM for v in tol], t['data']['fiducial']


def poly_corners(cfg, prefix, which):
    """Corner list of one PolyFiducial, in cm.

    axis 2 ('-xy') -> corners are (x, y);  axis 1 ('-xz') -> corners are (z, x).
    Returns a list of (x, w) pairs with w the TRANSVERSE wall coordinate, so both
    planes come back in the same orientation.
    """
    p = find_type(cfg, 'PolyFiducial', prefix + '-' + which)
    if p is None:
        raise SystemExit('no PolyFiducial %s-%s' % (prefix, which))
    d = p['data']
    assert len(d['slabs']) == 1, 'expected one slab'
    cs = [(c[0] / MM, c[1] / MM) for c in d['slabs'][0]['corners']]
    if which == 'xy':          # (x, y)
        return [(a, b) for a, b in cs], d['axis']
    return [(b, a) for a, b in cs], d['axis']   # (z, x) -> (x, z)


def box_bounds(cfg):
    b = find_type(cfg, 'BoxFiducial')
    if b is None:
        return None
    bb = b['data']['bounds']
    return {k: {a: v / MM for a, v in bb[k].items()} for k in ('tail', 'head')}


def geom_constants(cfgdir, det):
    """XW / the four transverse wall positions, parsed from curved_fiducial.jsonnet."""
    src = open(os.path.join(cfgdir, det, 'curved_fiducial.jsonnet')).read()

    def g(name):
        m = re.search(r'^local\s+%s\s*=\s*([-\d.]+)\s*;' % name, src, re.M)
        return float(m.group(1)) if m else None

    XW, CATH = g('XW'), g('CATH')
    YW = g('YW')
    if YW is not None:                    # PDVD: symmetric y
        YLO, YHI = -YW, YW
    else:                                 # PDHD: asymmetric y
        YLO, YHI = g('YLO'), g('YHI')
    return dict(XW=XW, CATH=CATH, YLO=YLO, YHI=YHI, ZLO=g('ZLO'), ZHI=g('ZHI'))


# ------------------------------------------------------------ wall extraction
def split_walls(corners, lo, hi):
    """Group polygon vertices into the four wall arcs and return insets.

    Returns {key: (|x| sorted ascending, inset)} with keys 'lo_neg','lo_pos',
    'hi_neg','hi_pos' -- low/high transverse wall x drift-volume sign.
    The classification is by sign(x) and by which wall the vertex is nearer, so it
    does not depend on the order curved_fiducial.jsonnet emits vertices in.
    """
    groups = {'lo_neg': [], 'lo_pos': [], 'hi_neg': [], 'hi_pos': []}
    for x, w in corners:
        side = 'neg' if x < 0 else 'pos'
        wall = 'lo' if abs(w - lo) <= abs(hi - w) else 'hi'
        inset = (w - lo) if wall == 'lo' else (hi - w)
        groups[wall + '_' + side].append((abs(x), inset))
    out = {}
    for k, v in groups.items():
        v.sort()
        out[k] = (np.array([p[0] for p in v]), np.array([p[1] for p in v]))
    return out


# ------------------------------------------------------------------ detectors
def build(det, prod_path, flat_path, cfgdir, prefix):
    prod, flat = load_cfg(prod_path), load_cfg(flat_path)
    G = geom_constants(cfgdir, det['cfgdir'])
    tol_prod, fid_prod = tagger_tolerance(prod)
    tol_flat, fid_flat = tagger_tolerance(flat)
    xy, ax_xy = poly_corners(prod, prefix, 'xy')
    xz, ax_xz = poly_corners(prod, prefix, 'xz')
    return dict(
        name=det['name'], cfgdir=det['cfgdir'], prefix=prefix, G=G,
        fid_prod=fid_prod, fid_flat=fid_flat,
        cushion=dict(x=tol_prod[0], y=tol_prod[2], zmax=tol_prod[4], zmin=tol_prod[5]),
        shell=dict(x=tol_flat[0], y=tol_flat[2], zmax=tol_flat[4], zmin=tol_flat[5]),
        y=split_walls(xy, G['YLO'], G['YHI']),
        z=split_walls(xz, G['ZLO'], G['ZHI']),
        box=box_bounds(flat), ax=(ax_xy, ax_xz),
        labels=det['labels'])


PDHD = dict(name='PDHD', cfgdir='pdhd',
            labels={'neg': 'APA0/2  (x<0)', 'pos': 'APA1/3  (x>0)'})
PDVD = dict(name='PDVD', cfgdir='protodunevd',
            labels={'neg': 'bottom CRP (x<0)', 'pos': 'top CRP (x>0)'})

# detector-local wall names, and what each wall physically IS
WALLNAME = {
    'PDHD': {'y_lo': 'y-  floor', 'y_hi': 'y+  ceiling',
             'z_lo': 'z-  upstream (beam)', 'z_hi': 'z+  downstream (beam)'},
    'PDVD': {'y_lo': 'y-  side wall', 'y_hi': 'y+  side wall',
             'z_lo': 'z-  side wall', 'z_hi': 'z+  side wall'},
}
COL = {'lo_neg': '#1f77b4', 'lo_pos': '#4fa3d9', 'hi_neg': '#d62728', 'hi_pos': '#f08080'}


def step(ax, xs, ys, **kw):
    """The profile is a piecewise-linear knot list; draw it as such."""
    ax.plot(xs, ys, **kw)


# ------------------------------------------------------------------ figure 1
def fig_profiles(dets, out, cushion=False):
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.0), sharey=True)
    ymax = 0
    for d in dets:
        for plane in ('y', 'z'):
            for k, (xs, ins) in d[plane].items():
                ymax = max(ymax, ins.max())
    ymax = ymax + (max(d['cushion']['y'] for d in dets) if cushion else 0)
    ymax = 5.0 * np.ceil((ymax + 3.0) / 5.0)          # round up to a tick
    print('   ylim 0 .. %.1f cm' % ymax)

    for col, d in enumerate(dets):
        for row, plane in enumerate(('y', 'z')):
            ax = axes[row][col]
            cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
            shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
            add = cush if cushion else 0.0
            for k in ('lo_neg', 'lo_pos', 'hi_neg', 'hi_pos'):
                xs, ins = d[plane][k]
                wall, side = k.split('_')
                lab = '%s   %s' % (WALLNAME[d['name']]['%s_%s' % (plane, wall)],
                                   d['labels'][side])
                step(ax, xs, ins + add, color=COL[k], lw=2.0,
                     ls='-' if side == 'neg' else '--', marker='o', ms=3.5, label=lab)
            ax.axhline(shell, color='k', ls=':', lw=1.8,
                       label='flat shell replaced (%.1f cm)' % shell)
            ax.axvline(d['G']['XW'], color='0.4', lw=1.2)
            ax.text(d['G']['XW'] - 4, ymax * 0.96, 'anode\n%.1f' % d['G']['XW'],
                    ha='right', va='top', fontsize=8, color='0.3')
            ax.axvline(d['G']['CATH'], color='0.4', lw=1.2)
            ax.set_xlim(-8, 372)
            ax.set_ylim(0, ymax)
            ax.grid(alpha=0.28)
            ax.set_title('%s   %s walls%s' %
                         (d['name'], plane, '  (+ %.0f cm cushion)' % cush if cushion else ''),
                         fontsize=11)
            if row == 1:
                ax.set_xlabel('distance from the CATHODE plane,  |x|  (cm)')
            if col == 0:
                ax.set_ylabel('inset from the nominal wall (cm)')
            ax.legend(fontsize=7.4, loc='upper left', framealpha=0.92)
    ttl = ('Measured space-charge fiducial surfaces, PDHD vs PDVD'
           + ('  --  surface + tagger cushion (what the taggers test)' if cushion
              else '  --  calibrated surface, cushion 0'))
    fig.suptitle(ttl, fontsize=13)
    fig.text(0.5, 0.030,
             'Cathode at |x| = 0 in both detectors; each panel is drawn to its own '
             'anode.  Curves are the p90 exit-gap profiles compiled into production '
             '(doc pdhd/09, doc pdvd/43).',
             ha='center', fontsize=9.0, color='0.25')
    fig.text(0.5, 0.008,
             'ABOVE the dotted line the measured surface is TIGHTER than the flat '
             '15 cm space-charge shell it replaced; BELOW it, looser.',
             ha='center', fontsize=9.0, color='0.25')
    fig.tight_layout(rect=(0, 0.052, 1, 0.962))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print('wrote', out)


# ------------------------------------------------------------------ figure 2
def fig_polygons(dets, out):
    """The polygon itself, in a BAND around each wall.

    A full-extent x-y plot is useless here: the insets are ~20 cm against a
    600 cm wall separation.  So each wall gets its own strip, drawn to the same
    45 cm vertical span in every panel, with the interior of the detector
    pointing INTO the panel (up for a low wall, down for a high wall).
    """
    SPAN, OUT = 40.0, 6.0
    fig, axes = plt.subplots(4, 2, figsize=(13.6, 13.2))
    for col, d in enumerate(dets):
        G = d['G']
        planes = (('y', G['YLO'], G['YHI']), ('z', G['ZLO'], G['ZHI']))
        for pi, (plane, lo, hi) in enumerate(planes):
            cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
            shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
            for wi, wall in enumerate(('hi', 'lo')):      # high wall on top
                ax = axes[2 * pi + wi][col]
                wpos, sgn = (hi, -1) if wall == 'hi' else (lo, +1)
                # The flat arm tested the COMPILED BoxFiducial, whose wall is not
                # always the constant curved_fiducial.jsonnet uses (PDVD z differs
                # by ~0.8 cm -- see the doc's geometry cross-check).  Draw the
                # shell off the box wall, i.e. off what was actually tested.
                bw = (d['box']['head'][plane] if wall == 'hi'
                      else d['box']['tail'][plane]) if d['box'] else wpos
                ax.axhline(wpos, color='0.55', lw=1.6,
                           label='nominal wall (curved_fiducial.jsonnet)')
                if abs(bw - wpos) > 0.05:
                    ax.axhline(bw, color='0.72', lw=1.4, ls=(0, (6, 3)),
                               label='nominal wall (compiled BoxFiducial): %+.2f cm'
                                     % (bw - wpos))
                ax.axhline(bw + sgn * shell, color='k', lw=1.7, ls=':',
                           label='flat box + %.1f cm shell (was)' % shell)
                for add, ls, lw, cl, lab in (
                        (0.0, '--', 1.5, '#e58080', 'measured surface (cushion 0)'),
                        (cush, '-', 2.4, '#c00000',
                         'surface + %.0f cm cushion (production)' % cush)):
                    xs_all, ys_all = [], []
                    for side, order in (('neg', -1), ('pos', +1)):
                        xs, ins = d[plane][wall + '_' + side]
                        xx = order * xs
                        idx = np.argsort(xx)
                        xs_all += list(xx[idx])
                        ys_all += list((wpos + sgn * (ins + add))[idx])
                    ax.plot(xs_all, ys_all, color=cl, lw=lw, ls=ls, marker='o',
                            ms=3.0, label=lab)
                ax.axvline(0, color='0.75', lw=1.0)
                ax.axvline(-G['XW'], color='0.4', lw=1.0)
                ax.axvline(G['XW'], color='0.4', lw=1.0)
                if sgn > 0:
                    ax.set_ylim(wpos - OUT, wpos + SPAN)
                else:
                    ax.set_ylim(wpos - SPAN, wpos + OUT)
                ax.set_xlim(-G['XW'] - 12, G['XW'] + 12)
                ax.grid(alpha=0.25)
                ax.set_ylabel('%s  (cm)' % plane)
                ax.set_title('%s   %s   -- the %s' %
                             (d['name'], WALLNAME[d['name']]['%s_%s' % (plane, wall)],
                              'detector interior is BELOW' if sgn < 0
                              else 'detector interior is ABOVE'), fontsize=10)
                if 2 * pi + wi == 3:
                    ax.set_xlabel('x  (cm)   -- drift; cathode at 0, anodes at '
                                  '+-%.1f' % G['XW'])
                if pi == 0 and wi == 0:
                    ax.legend(fontsize=7.4, loc='lower center', ncol=2,
                              framealpha=0.93)
    fig.suptitle('The two AND-ed fiducial polygons as compiled into production, '
                 'shown wall by wall\n'
                 '(every panel spans %.0f cm vertically, so shapes are directly '
                 'comparable)' % (SPAN + OUT), fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print('wrote', out)


# ------------------------------------------------------------------ figure 3
def fig_overlay(dets, out):
    """The direct cross-detector overlay: effective boundary vs distance from cathode."""
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.4), sharey=True)
    style = {'PDHD': dict(color='#1a6fb5'), 'PDVD': dict(color='#c0392b')}
    for i, plane in enumerate(('y', 'z')):
        ax = axes[i]
        for d in dets:
            cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
            shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
            # envelope across the four walls of this plane, on a common grid
            grid = np.linspace(0, d['G']['XW'], 400)
            curves = []
            for k, (xs, ins) in d[plane].items():
                curves.append(np.interp(grid, xs, ins + cush))
            curves = np.array(curves)
            ax.fill_between(grid, curves.min(0), curves.max(0), alpha=0.16, **style[d['name']])
            ax.plot(grid, curves.mean(0), lw=2.4, label='%s  mean of 4 walls (+%.0f cm cushion)'
                    % (d['name'], cush), **style[d['name']])
            ax.axvline(d['G']['XW'], ls='-', lw=1.2, alpha=0.55, **style[d['name']])
            ax.annotate('%s anode' % d['name'], xy=(d['G']['XW'], 0.03),
                        xycoords=('data', 'axes fraction'), rotation=90,
                        fontsize=7.6, ha='right', va='bottom', **style[d['name']])
        # ONE shell line: both detectors replaced the SAME flat allowance
        shells = {round(dd['shell']['y' if plane == 'y' else 'zmin'], 3) for dd in dets}
        assert len(shells) == 1, 'detectors replaced different shells: %s' % shells
        ax.axhline(shells.pop(), color='k', ls=':', lw=1.9,
                   label='flat shell replaced -- SAME in both detectors (%.1f cm)'
                         % (17.5 if plane == 'y' else 18.0))
        ax.set_xlabel('distance from the CATHODE plane,  |x|  (cm)')
        ax.set_title('%s walls   (band = spread over the four walls)' % plane, fontsize=11)
        ax.grid(alpha=0.28)
        ax.legend(fontsize=8.4, loc='upper left')
        ax.set_xlim(-6, 372)
    axes[0].set_ylabel('effective inset from the nominal wall (cm)')
    fig.suptitle('Effective tagger boundary vs drift position -- what PDHD and PDVD '
                 'actually test  (dotted = the flat shell each replaced)', fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print('wrote', out)


# ------------------------------------------------------------------ knot table
def write_table(dets, out):
    with open(out, 'w') as fh:
        fh.write('detector\tplane\twall\tdrift_volume\t|x|_cm\tinset_cm\tcushion_cm'
                 '\teffective_cm\tflat_shell_cm\ttighter_than_shell\n')
        for d in dets:
            for plane in ('y', 'z'):
                cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
                shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
                for k in ('lo_neg', 'lo_pos', 'hi_neg', 'hi_pos'):
                    wall, side = k.split('_')
                    xs, ins = d[plane][k]
                    for x, v in zip(xs, ins):
                        eff = v + cush
                        fh.write('%s\t%s\t%s\t%s\t%.3f\t%.2f\t%.1f\t%.2f\t%.1f\t%s\n' %
                                 (d['name'], plane, wall, side, x, v, cush, eff, shell,
                                  'yes' if eff > shell else 'no'))
    print('wrote', out)


def summarize(dets):
    print('\n%-6s %-28s %s' % ('det', 'production fiducial', 'cushion (x, y, zmax, zmin) cm'))
    for d in dets:
        c = d['cushion']; s = d['shell']
        print('%-6s %-28s %.1f  %.1f  %.1f  %.1f      [flat arm: %.1f %.1f %.1f %.1f]'
              % (d['name'], d['fid_prod'], c['x'], c['y'], c['zmax'], c['zmin'],
                 s['x'], s['y'], s['zmax'], s['zmin']))
    print('\n%-6s %-6s %-8s %-10s %8s %8s %8s %8s' %
          ('det', 'plane', 'wall', 'volume', 'anode', 'cathode', '+cush@c', 'shell'))
    for d in dets:
        for plane in ('y', 'z'):
            cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
            shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
            for k in ('lo_neg', 'lo_pos', 'hi_neg', 'hi_pos'):
                wall, side = k.split('_')
                xs, ins = d[plane][k]
                # xs ascending in |x|: index 0 = cathode end, -1 = anode end
                print('%-6s %-6s %-8s %-10s %8.2f %8.2f %8.2f %8.1f' %
                      (d['name'], plane, wall, side, ins[-1], ins[0], ins[0] + cush, shell))
    # where the mean surface crosses the shell it replaced, and over what
    # fraction of the drift it is the tighter of the two
    print('\ncrossing of the flat shell by the mean of the four walls'
          '  (|x| measured from the CATHODE):')
    for d in dets:
        for plane in ('y', 'z'):
            cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
            shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
            grid = np.linspace(0, d['G']['XW'], 4000)
            mean = np.array([np.interp(grid, xs, ins + cush)
                             for xs, ins in d[plane].values()]).mean(0)
            tight = mean > shell
            frac = tight.mean()
            idx = np.where(np.diff(tight.astype(int)) != 0)[0]
            xs_cross = ', '.join('%.0f' % grid[i] for i in idx) if len(idx) else 'none'
            print('  %-6s %s walls: shell %.1f cm, crossing at |x| = %s cm;'
                  ' TIGHTER over %.0f %% of the drift'
                  % (d['name'], plane, shell, xs_cross, 100 * frac))

    print('\nfraction of sampled knots where surface+cushion is TIGHTER than the flat shell:')
    for d in dets:
        for plane in ('y', 'z'):
            cush = d['cushion']['y'] if plane == 'y' else d['cushion']['zmin']
            shell = d['shell']['y'] if plane == 'y' else d['shell']['zmin']
            n = t = 0
            for k, (xs, ins) in d[plane].items():
                n += len(ins); t += int((ins + cush > shell).sum())
            print('  %-6s %s walls: %d/%d' % (d['name'], plane, t, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdhd-prod', required=True)
    ap.add_argument('--pdhd-flat', required=True)
    ap.add_argument('--pdvd-prod', required=True)
    ap.add_argument('--pdvd-flat', required=True)
    ap.add_argument('--toolkit-cfg', required=True,
                    help='cfg/pgrapher/experiment (holds pdhd/ and protodunevd/)')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--prefix', default='49')
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    dets = [build(PDHD, a.pdhd_prod, a.pdhd_flat, a.toolkit_cfg, 'pdhdcurved'),
            build(PDVD, a.pdvd_prod, a.pdvd_flat, a.toolkit_cfg, 'pdvdcurved')]

    p = lambda s: os.path.join(a.out_dir, '%s_%s' % (a.prefix, s))
    fig_profiles(dets, p('fv_profiles.png'), cushion=False)
    fig_profiles(dets, p('fv_profiles_cushioned.png'), cushion=True)
    fig_polygons(dets, p('fv_polygons.png'))
    fig_overlay(dets, p('fv_overlay.png'))
    write_table(dets, p('fv_knots.tsv'))
    summarize(dets)

    # geometry cross-check: the curved file's wall constants vs the flat box the
    # taggers used before.  A mismatch means the two surfaces do not share a wall.
    print('\ngeometry cross-check (curved_fiducial.jsonnet constant vs compiled flat box, cm):')
    for d in dets:
        b, G = d['box'], d['G']
        if b is None:
            continue
        print('  %-6s XW  %9.4f / %9.4f    YLO %9.4f / %9.4f    YHI %9.4f / %9.4f'
              '    ZLO %9.4f / %9.4f    ZHI %9.4f / %9.4f' %
              (d['name'], G['XW'], b['head']['x'], G['YLO'], b['tail']['y'],
               G['YHI'], b['head']['y'], G['ZLO'], b['tail']['z'], G['ZHI'], b['head']['z']))


if __name__ == '__main__':
    main()
