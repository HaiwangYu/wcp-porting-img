#!/usr/bin/env python3
"""Evaluate the L1SP trigger gate on PDVD bottom anode 0 against the
hand-scanned ground truth at handscan_039324_anode0.csv.

Two input sources are supported:

  --source npz    Read the C++ tagger's per-ROI dumps under
                  pdvd/work/<RUN>_<EVT>/l1sp_calib/apa<APA>_*.npz.
                  Re-applies the gate offline so the threshold knobs
                  below can be swept without rebuilding C++.

  --source csv    Read the Python script's clustered output at
                  pdvd/sp_plot/pdvd_l1sp_rois_<RUN>_evt<EVT>_anode<APA>.csv.
                  Treats every row as fired (the CSV is a snapshot of
                  the Python script's last run).  Use for a quick
                  sanity check at the script's current defaults.

Per event the script prints TP / FP / FN against the hand-scan and
aggregates F1.  Hand-scan rows are split into:
    real == Yes      → ground-truth positive (must be hit)
    real == Missing  → ground-truth positive (currently missed; recovery target)
    real == No       → reference label of a known false-positive
                       (must NOT match any fired ROI)

Hits / misses are determined by (channel ⊆ [ch1, ch2]) AND
(fired tick interval overlaps [t1, t2]).
"""

import argparse
import csv
import glob
import os
import sys
from collections import defaultdict

import numpy as np


# PDVD bottom anode 0: U 0..475, V 952..1427 (chndb-base.jsonnet).
# Even bottom anodes share this layout; the script is currently anode-0-only,
# but the mapping is exposed so a future caller can pass --apa 2 / --apa 4 ...
PDVD_PLANE_RANGES = {
    'U': (0, 476),
    'V': (952, 1428),
    # W intentionally omitted — L1SP processes induction planes only.
}


# ── Hand-scan loader ─────────────────────────────────────────────────────────

def load_handscan(path, run, planes):
    rows = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if int(r['run']) != run:
                continue
            if r['plane'] not in planes:
                continue
            rows.append({
                'evt':   int(r['evt']),
                'plane': r['plane'],
                'ch1':   int(r['ch1']),
                'ch2':   int(r['ch2']),
                't1':    int(r['t1']),
                't2':    int(r['t2']),
                'asym':  float(r['asym']) if r['asym'] not in ('', None) else None,
                'type':  r['type'],
                'real':  r['real'],
                'note':  r['note'],
            })
    return rows


# ── NPZ source ───────────────────────────────────────────────────────────────

def load_apa_npz(calib_root, run, evt, apa):
    pat_dir = os.path.join(calib_root, f'{int(run):06d}_{int(evt)}', 'l1sp_calib')
    if not os.path.isdir(pat_dir):
        return None
    files = sorted(f for f in os.listdir(pat_dir)
                   if f.startswith(f'apa{apa}_') and f.endswith('.npz'))
    if not files:
        return None
    parts = [np.load(os.path.join(pat_dir, f)) for f in files]
    out = {}
    for k in parts[0].files:
        if parts[0][k].shape == (1,):
            out[k] = np.array([p[k][0] for p in parts])
        else:
            out[k] = np.concatenate([p[k] for p in parts])
    return out


def npz_plane_mask(d, plane):
    lo, hi = PDVD_PLANE_RANGES[plane]
    return (d['channel'] >= lo) & (d['channel'] < hi)


def apply_gate(d, mask, cfg):
    """Re-apply the C++ gate (decide_trigger) offline using core sub-window
    features (matches L1SPFilterPD.cxx::decide_trigger)."""
    if 'core_length' in d:
        nb   = d['core_length'][mask]
        aw   = d['core_raw_asym_wide'][mask]
        fill = d['core_fill'][mask]
        fwhm = d['core_fwhm_frac'][mask]
    else:
        nb   = d['nbin_fit'][mask]
        aw   = d['raw_asym_wide'][mask]
        fill = d['gauss_fill'][mask]
        fwhm = d['gauss_fwhm_frac'][mask]
    gm = d['gmax'][mask]
    ef = d['roi_energy_frac'][mask]

    aabs = np.abs(aw)
    pre = (nb >= cfg['min_length']) & (gm >= cfg['gmax_min']) \
          & (ef >= cfg['energy_frac_thr'])
    fire = pre & (
        (aabs >= cfg['asym_strong']) |
        ((nb >= cfg['len_long_mod'])   & (aabs >= cfg['asym_mod']))   |
        ((nb >= cfg['len_long_loose']) & (aabs >= cfg['asym_loose'])) |
        ((nb >= cfg['len_fill_shape']) &
         (fill <= cfg['fill_shape_fill_thr']) &
         (fwhm <= cfg['fill_shape_fwhm_thr']) &
         (aabs >= cfg['asym_mod']))
    )
    flag = np.zeros_like(nb, dtype=np.int32)
    flag[fire & (aw > 0)] = +1
    flag[fire & (aw < 0)] = -1
    return flag


def fired_from_npz(d, plane, cfg, use_cpp_flag, trigger_only=False):
    """Return list of (ch, t_lo, t_hi, len, aw, gmax, ef, fill, fwhm, flag)
    for ROIs that fired (live or recomputed).

    When use_cpp_flag, the default flag is ``flag_l1_adj`` — the
    post-adjacency-expansion polarity that the C++ actually uses to
    drive LASSO (see L1SPFilterPD.cxx ~line 1440 where polarity_final
    feeds l1_fit).  Pass trigger_only=True to use the un-promoted
    ``flag_l1`` for diagnostic use."""
    mask = npz_plane_mask(d, plane)
    if use_cpp_flag:
        key = 'flag_l1' if trigger_only else 'flag_l1_adj'
        flag = d[key][mask].astype(np.int32)
    else:
        flag = apply_gate(d, mask, cfg)

    ch  = d['channel'][mask]
    rs  = d['roi_start'][mask]
    re_ = d['roi_end'][mask]
    nb  = d['nbin_fit'][mask]
    aw  = d['raw_asym_wide'][mask]
    gm  = d['gmax'][mask]
    ef  = d['roi_energy_frac'][mask]
    fil = d['gauss_fill'][mask]
    fwh = d['gauss_fwhm_frac'][mask]

    out = []
    for i in np.where(flag != 0)[0]:
        out.append({
            'ch': int(ch[i]), 't_lo': int(rs[i]), 't_hi': int(re_[i]),
            'len': int(nb[i]), 'aw': float(aw[i]), 'gmax': float(gm[i]),
            'ef': float(ef[i]), 'fill': float(fil[i]), 'fwhm': float(fwh[i]),
            'flag': int(flag[i]),
        })
    return out


# ── CSV source ───────────────────────────────────────────────────────────────

def fired_from_csv(csv_dir, run, evt, apa, plane):
    """Read a Python-script CSV and return fired clusters as
    (ch_lo, ch_hi, t_lo, t_hi, length, aw, gmax, ef, fill, fwhm, label)."""
    fname = os.path.join(
        csv_dir, f'pdvd_l1sp_rois_{run:06d}_evt{evt}_anode{apa}.csv')
    out = []
    if not os.path.exists(fname):
        return out
    with open(fname) as fh:
        for r in csv.DictReader(fh):
            if r['plane'] != plane:
                continue
            out.append({
                'ch_lo': int(r['ch_lo']), 'ch_hi': int(r['ch_hi']),
                't_lo':  int(r['t_lo']),  't_hi':  int(r['t_hi']),
                'len':   int(r['length_max']),
                'aw':    float(r['raw_asym_extreme']),
                'gmax':  float(r['gauss_max']),
                'ef':    float(r['roi_energy_frac_max']),
                'fill':  float(r['fill_factor_min']),
                'fwhm':  float(r['fwhm_frac_min']),
                'label': r['triggered_by'],
            })
    return out


# ── Match fired vs handscan ──────────────────────────────────────────────────

def overlaps_ch(fired, gt):
    """Channel test that handles both per-ROI (ch) and per-cluster
    (ch_lo, ch_hi) shapes."""
    if 'ch' in fired:
        return gt['ch1'] <= fired['ch'] <= gt['ch2']
    return (fired['ch_lo'] <= gt['ch2']) and (fired['ch_hi'] >= gt['ch1'])


def overlaps_t(fired, gt):
    return (fired['t_lo'] <= gt['t2']) and (fired['t_hi'] >= gt['t1'])


def match_event(fired_rois, gt_rows):
    """Return (tp_count, fp_count, fn_count, fp_on_no_count, gt_status,
    fired_status)."""
    pos_idx = [i for i, g in enumerate(gt_rows) if g['real'] in ('Yes', 'Missing')]
    neg_idx = [i for i, g in enumerate(gt_rows) if g['real'] == 'No']

    gt_hit = [False] * len(gt_rows)
    fired_match = [None] * len(fired_rois)  # store gt index of FIRST positive hit, or 'NEG' or None

    for fi, fr in enumerate(fired_rois):
        # First check positive matches.
        for gi in pos_idx:
            g = gt_rows[gi]
            if g['plane'] != _plane_of(fr, g):
                continue
            if overlaps_ch(fr, g) and overlaps_t(fr, g):
                gt_hit[gi] = True
                if fired_match[fi] is None:
                    fired_match[fi] = gi
        # Also note overlap with a known-No row (informational).
        if fired_match[fi] is None:
            for gi in neg_idx:
                g = gt_rows[gi]
                if g['plane'] != _plane_of(fr, g):
                    continue
                if overlaps_ch(fr, g) and overlaps_t(fr, g):
                    fired_match[fi] = ('NEG', gi)
                    break

    tp = sum(1 for m in fired_match if isinstance(m, int))
    fp = sum(1 for m in fired_match if m is None)
    fp_on_no = sum(1 for m in fired_match if isinstance(m, tuple))
    n_pos = len(pos_idx)
    n_hit = sum(1 for gi in pos_idx if gt_hit[gi])
    fn = n_pos - n_hit
    return {
        'tp': tp, 'fp': fp, 'fp_on_no': fp_on_no, 'fn': fn,
        'n_pos': n_pos, 'n_hit': n_hit,
        'gt_hit': gt_hit, 'fired_match': fired_match,
    }


def _plane_of(fired, gt):
    """Fired ROIs from CSV/NPZ are loaded inside a plane loop, so the GT's
    plane is the truth.  Returning g['plane'] makes the equality vacuous; the
    caller has already filtered fired to a single plane."""
    return gt['plane']


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_handscan = os.path.join(here, 'handscan_039324_anode0.csv')
    default_csv_dir = here
    default_npz_root = os.path.join(here, '..', 'work')

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--run', type=int, default=39324)
    p.add_argument('--evts', default='0,1,2,3,4,5',
                   help='comma list of event ids')
    p.add_argument('--apa', type=int, default=0)
    p.add_argument('--planes', default='UV')
    p.add_argument('--handscan', default=default_handscan)
    p.add_argument('--source', choices=['csv', 'npz'], default='csv')
    p.add_argument('--csv-dir', default=default_csv_dir,
                   help='dir holding pdvd_l1sp_rois_*.csv (--source csv)')
    p.add_argument('--calib-root', default=default_npz_root,
                   help='dir holding <RUN>_<EVT>/l1sp_calib/apa*.npz (--source npz)')
    p.add_argument('--use-cpp-flag', action='store_true',
                   help='(--source npz) use the live flag_l1_adj from the dump '
                        'instead of recomputing the gate')
    p.add_argument('--trigger-only', action='store_true',
                   help='(--source npz --use-cpp-flag) use flag_l1 only '
                        '(skip the adjacency-promoted fires)')
    # Gate overrides (only used when --source npz and not --use-cpp-flag).
    p.add_argument('--min-length',           type=int,   default=30)
    p.add_argument('--gmax-min',             type=float, default=1500.0)
    p.add_argument('--energy-frac-thr',      type=float, default=0.66)
    p.add_argument('--asym-strong',          type=float, default=0.65)
    p.add_argument('--asym-mod',             type=float, default=0.40)
    p.add_argument('--asym-loose',           type=float, default=0.30)
    p.add_argument('--len-long-mod',         type=int,   default=100)
    p.add_argument('--len-long-loose',       type=int,   default=200)
    p.add_argument('--len-fill-shape',       type=int,   default=50)
    p.add_argument('--fill-shape-fill-thr',  type=float, default=0.38)
    p.add_argument('--fill-shape-fwhm-thr',  type=float, default=0.30)
    p.add_argument('--show-fp', action='store_true',
                   help='print details for FPs and FP-on-No matches')
    p.add_argument('--show-miss', action='store_true', default=True,
                   help='print missed ground-truth rows (default ON)')
    args = p.parse_args()

    cfg = dict(
        min_length=args.min_length, gmax_min=args.gmax_min,
        energy_frac_thr=args.energy_frac_thr,
        asym_strong=args.asym_strong, asym_mod=args.asym_mod,
        asym_loose=args.asym_loose,
        len_long_mod=args.len_long_mod, len_long_loose=args.len_long_loose,
        len_fill_shape=args.len_fill_shape,
        fill_shape_fill_thr=args.fill_shape_fill_thr,
        fill_shape_fwhm_thr=args.fill_shape_fwhm_thr,
    )

    print(f'source={args.source}  use_cpp_flag={args.use_cpp_flag}')
    print(f'gate cfg={cfg}')
    print()

    evts = [int(x) for x in args.evts.split(',')]
    planes = list(args.planes.upper())
    handscan = load_handscan(args.handscan, args.run, planes)

    print(f'{"evt":>3} {"plane":>5} {"GTpos":>5} {"hit":>3} {"miss":>4} '
          f'{"GTneg":>5} {"fired":>5} {"TP":>3} {"FP":>3} {"FPneg":>5} '
          f'{"sens":>5} {"prec":>5}')

    tot_tp = tot_fp = tot_fpneg = tot_pos = tot_hit = 0

    for evt in evts:
        # Load whichever source.
        if args.source == 'npz':
            d = load_apa_npz(args.calib_root, args.run, evt, args.apa)
            if d is None:
                print(f'{evt:>3}  no NPZ dumps under {args.calib_root}')
                continue

        for plane in planes:
            if args.source == 'npz':
                fired = fired_from_npz(d, plane, cfg, args.use_cpp_flag,
                                        trigger_only=args.trigger_only)
            else:
                fired = fired_from_csv(args.csv_dir, args.run, evt, args.apa, plane)

            gt_rows = [g for g in handscan if g['evt'] == evt and g['plane'] == plane]
            res = match_event(fired, gt_rows)
            n_pos = res['n_pos']
            n_neg = sum(1 for g in gt_rows if g['real'] == 'No')
            sens = res['n_hit'] / n_pos if n_pos else 0.0
            prec = res['tp'] / (res['tp'] + res['fp']) if (res['tp'] + res['fp']) else 0.0

            print(f'{evt:>3} {plane:>5} {n_pos:>5d} {res["n_hit"]:>3d} '
                  f'{res["fn"]:>4d} {n_neg:>5d} {len(fired):>5d} '
                  f'{res["tp"]:>3d} {res["fp"]:>3d} {res["fp_on_no"]:>5d} '
                  f'{sens:>5.2f} {prec:>5.2f}')

            if args.show_miss:
                for gi, hit in enumerate(res['gt_hit']):
                    g = gt_rows[gi]
                    if g['real'] in ('Yes', 'Missing') and not hit:
                        print(f'    MISS  evt={evt} {plane} ch={g["ch1"]}-{g["ch2"]} '
                              f't=[{g["t1"]},{g["t2"]}] real={g["real"]} '
                              f'asym={g["asym"]} type="{g["type"]}" note="{g["note"]}"')
            if args.show_fp:
                for fi, m in enumerate(res['fired_match']):
                    fr = fired[fi]
                    if m is None:
                        ch_repr = fr.get('ch', f'{fr.get("ch_lo")}-{fr.get("ch_hi")}')
                        print(f'    FP    evt={evt} {plane} ch={ch_repr} '
                              f't=[{fr["t_lo"]},{fr["t_hi"]}] len={fr["len"]} '
                              f'aw={fr["aw"]:+.2f} gmax={fr["gmax"]:.0f} '
                              f'ef={fr["ef"]:.2f} fill={fr["fill"]:.2f} '
                              f'fwhm={fr["fwhm"]:.2f}')
                    elif isinstance(m, tuple):  # ('NEG', gi)
                        gi_neg = m[1]
                        g = gt_rows[gi_neg]
                        ch_repr = fr.get('ch', f'{fr.get("ch_lo")}-{fr.get("ch_hi")}')
                        print(f'    FPneg evt={evt} {plane} ch={ch_repr} '
                              f't=[{fr["t_lo"]},{fr["t_hi"]}] len={fr["len"]} '
                              f'aw={fr["aw"]:+.2f} matches No-row '
                              f'ch={g["ch1"]}-{g["ch2"]} note="{g["note"]}"')

            tot_tp += res['tp']; tot_fp += res['fp']; tot_fpneg += res['fp_on_no']
            tot_pos += n_pos; tot_hit += res['n_hit']

    fp_total = tot_fp + tot_fpneg  # both classes are real false positives
    sens = tot_hit / tot_pos if tot_pos else 0.0
    prec = tot_tp / (tot_tp + fp_total) if (tot_tp + fp_total) else 0.0
    f1 = 2 * sens * prec / (sens + prec) if (sens + prec) else 0.0

    print()
    print(f'AGGREGATE  GTpos={tot_pos} hit={tot_hit} miss={tot_pos - tot_hit}  '
          f'TP={tot_tp} FP={tot_fp} FPneg={tot_fpneg}')
    print(f'  sensitivity={sens:.3f}  precision={prec:.3f}  F1={f1:.3f}')


if __name__ == '__main__':
    sys.exit(main() or 0)
