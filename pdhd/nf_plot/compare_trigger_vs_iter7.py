#!/usr/bin/env python3
"""Compare the L1SPFilterPD per-ROI trigger (from C++ dump NPZs) against the
iter-7 Python detector (find_long_decon_artifacts.py CSV output).

Recall:  fraction of iter-7 clusters that have at least one C++-fired ROI
         overlapping in (channel range × tick range).
Extras:  fraction of C++-fired ROIs that overlap NO iter-7 cluster.

Usage:
    compare_trigger_vs_iter7.py \
        --calib-root <dir>          # contains <RUN>_<EVT>/apa<N>_*.npz
        --iter7-csv-glob '/path/*_evt%E_apa%A_U.csv'   # %E, %A placeholders
        --run 27409 --evts 0,1,2,3,4,5,6,7,12 --apas 0,1,2,3
        --plane U
        [--use-cpp-flag | --asym-strong 0.65 ...]
"""

import argparse
import csv
import glob
import os
import sys

import numpy as np


PDHD_PLANE_RANGES = {'U': (0, 800), 'V': (800, 1600), 'W': (1600, 2560)}


def load_apa_dumps(calib_root, run, evt, apa):
    pat_dir = os.path.join(calib_root, f'{int(run):06d}_{int(evt)}')
    if not os.path.isdir(pat_dir):
        return None
    files = sorted(f for f in os.listdir(pat_dir)
                   if f.startswith(f'apa{apa}_') and f.endswith('.npz'))
    if not files:
        return None
    parts = [np.load(os.path.join(pat_dir, f)) for f in files]
    out = {}
    keys = parts[0].files
    for k in keys:
        if parts[0][k].shape == (1,):
            out[k] = np.array([p[k][0] for p in parts])
        else:
            out[k] = np.concatenate([p[k] for p in parts])
    return out


def filter_to_plane(d, plane, apa):
    lo, hi = PDHD_PLANE_RANGES[plane]
    lo += 2560 * apa
    hi += 2560 * apa
    return (d['channel'] >= lo) & (d['channel'] < hi)


def apa_local(channels, apa):
    return channels - 2560 * apa


def apply_gate(d, mask, cfg):
    """Re-apply the multi-arm gate offline using **core sub-window** features.
    Falls back to the full-ROI features if `core_length` is absent (older dump).
    """
    if 'core_length' in d:
        nb = d['core_length'][mask]
        aw = d['core_raw_asym_wide'][mask]
        fill = d['core_fill'][mask]
        fwhm = d['core_fwhm_frac'][mask]
    else:
        nb = d['nbin_fit'][mask]
        aw = d['raw_asym_wide'][mask]
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


def load_iter7(path):
    """Return list of (ch_lo, ch_hi, t_lo, t_hi, raw_asym_extreme, triggered_by)."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({
                'ch_lo': int(r['ch_lo']),
                'ch_hi': int(r['ch_hi']),
                't_lo':  int(r['t_lo']),
                't_hi':  int(r['t_hi']),
                'asym':  float(r['raw_asym_extreme']),
                'type':  r['triggered_by'],
            })
    return rows


def overlap(ch, t_lo, t_hi, cl):
    if not (cl['ch_lo'] <= ch <= cl['ch_hi']):
        return False
    if t_hi < cl['t_lo'] or t_lo > cl['t_hi']:
        return False
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--calib-root', required=True)
    p.add_argument('--iter7-csv-glob', required=True,
                   help='filename pattern, e.g. '
                   '"/tmp/iter7_csv/run27409_evt%%E_apa%%A_U.csv"')
    p.add_argument('--run', type=int, required=True)
    p.add_argument('--evts', required=True)
    p.add_argument('--apas', default='0,1,2,3')
    p.add_argument('--plane', default='U', choices=['U', 'V', 'W'])
    p.add_argument('--use-cpp-flag', action='store_true')
    p.add_argument('--show-misses', action='store_true')
    p.add_argument('--show-extras', action='store_true')
    # Threshold overrides (default = same as C++ default)
    p.add_argument('--min-length',   type=int,   default=30)
    p.add_argument('--gmax-min',     type=float, default=1500.0)
    p.add_argument('--energy-frac-thr',     type=float, default=0.66)
    p.add_argument('--asym-strong',  type=float, default=0.65)
    p.add_argument('--asym-mod',     type=float, default=0.40)
    p.add_argument('--asym-loose',   type=float, default=0.30)
    p.add_argument('--len-long-mod',   type=int, default=100)
    p.add_argument('--len-long-loose', type=int, default=200)
    p.add_argument('--len-fill-shape', type=int, default=50)
    p.add_argument('--fill-shape-fill-thr', type=float, default=0.38)
    p.add_argument('--fill-shape-fwhm-thr', type=float, default=0.30)
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
    print(f'cfg={cfg}')
    print(f'use_cpp_flag={args.use_cpp_flag}\n')

    evts = [int(x) for x in args.evts.split(',')]
    apas = [int(x) for x in args.apas.split(',')]

    print(f'{"evt":>4} {"apa":>3} {"iter7":>5} {"hit":>3} {"miss":>4} '
          f'{"cpp_fired":>9} {"matched":>7} {"extras":>6} '
          f'{"recall":>6} {"extra%":>6}')

    tot_iter7 = tot_hit = 0
    tot_fired = tot_matched = tot_extras = 0
    miss_log = []
    extra_log = []

    for evt in evts:
        for apa in apas:
            d = load_apa_dumps(args.calib_root, args.run, evt, apa)
            if d is None: continue
            mask = filter_to_plane(d, args.plane, apa)
            if args.use_cpp_flag:
                flag = d['flag_l1'][mask].astype(np.int32)
            else:
                flag = apply_gate(d, mask, cfg)

            ch  = apa_local(d['channel'][mask], apa)
            rs  = d['roi_start'][mask]
            re_ = d['roi_end'][mask]
            aw  = d['raw_asym_wide'][mask]
            nb  = d['nbin_fit'][mask]
            ef  = d['roi_energy_frac'][mask]
            gm  = d['gmax'][mask]

            csv_path = (args.iter7_csv_glob
                        .replace('%E', str(evt))
                        .replace('%A', str(apa)))
            it7 = load_iter7(csv_path)

            fired_idx = np.where(flag != 0)[0]
            n_fired = len(fired_idx)

            it7_hits = [False] * len(it7)
            cpp_match = [False] * n_fired
            for k, i in enumerate(fired_idx):
                for j, cl in enumerate(it7):
                    if overlap(int(ch[i]), int(rs[i]), int(re_[i]), cl):
                        it7_hits[j] = True
                        cpp_match[k] = True
            n_hit = sum(it7_hits)
            n_match = sum(cpp_match)
            n_extra = n_fired - n_match

            recall = n_hit / len(it7) if it7 else (1.0 if n_fired == 0 else float('nan'))
            extra_pct = n_extra / max(n_fired, 1)

            print(f'{evt:>4} {apa:>3} {len(it7):>5d} {n_hit:>3d} {len(it7)-n_hit:>4d} '
                  f'{n_fired:>9d} {n_match:>7d} {n_extra:>6d} '
                  f'{recall:>6.2f} {extra_pct:>6.2f}')

            if args.show_misses:
                for j, hit in enumerate(it7_hits):
                    if not hit:
                        cl = it7[j]
                        miss_log.append(
                            f'  MISS evt={evt} apa={apa} ch={cl["ch_lo"]}-{cl["ch_hi"]} '
                            f't=[{cl["t_lo"]},{cl["t_hi"]}] '
                            f'asym={cl["asym"]:+.2f} type={cl["type"]}')
            if args.show_extras:
                for k, i in enumerate(fired_idx):
                    if not cpp_match[k]:
                        extra_log.append(
                            f'  EXTRA evt={evt} apa={apa} ch={int(ch[i]):>4d} '
                            f't=[{int(rs[i])},{int(re_[i])}] len={int(nb[i]):>3d} '
                            f'aw={float(aw[i]):+.2f} ef={float(ef[i]):.2f} '
                            f'gm={float(gm[i]):.0f}')

            tot_iter7 += len(it7); tot_hit += n_hit
            tot_fired += n_fired; tot_matched += n_match; tot_extras += n_extra

    print()
    print(f'AGGREGATE  iter7={tot_iter7}  hit={tot_hit} miss={tot_iter7-tot_hit}')
    print(f'           cpp_fired={tot_fired}  matched={tot_matched} extras={tot_extras}')
    if tot_iter7:
        print(f'           recall = {tot_hit/tot_iter7:.3f}  '
              f'  miss_rate = {(tot_iter7-tot_hit)/tot_iter7:.3f}  '
              f'(target ≤ 0.05)')
    if tot_fired:
        print(f'           extras / cpp_fired = {tot_extras/tot_fired:.3f}  '
              f'(target ≤ 0.10)')

    if args.show_misses and miss_log:
        print('\nMisses:')
        for line in miss_log:
            print(line)
    if args.show_extras and extra_log:
        print('\nExtras:')
        for line in extra_log:
            print(line)


if __name__ == '__main__':
    sys.exit(main() or 0)
