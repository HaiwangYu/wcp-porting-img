#!/usr/bin/env python3
"""Evaluate the L1SPFilterPD per-ROI trigger against hand-scanned ground truth.

The C++ filter (sigproc/src/L1SPFilterPD.cxx) runs in dump-mode and writes
one NPZ per (run, event, anode) under <calib_root>/<RUN>_<EVT>/apa<N>_*.npz.
Each NPZ records per-ROI features and the live trigger decision (`flag_l1`).

This script:

  1. loads the NPZ dumps,
  2. matches ROIs to hand-scanned ground-truth rows (interval × channel
     overlap) and reports per-event TP/FP/FN,
  3. reports `sign(raw_asym_wide) == sign(ratio)` agreement on the
     hand-scanned positives,
  4. can re-apply the gate offline with overridden thresholds via CLI
     flags so we can probe what each threshold movement costs.

Usage examples:

    # Default thresholds, U-plane, APA0, evts 0..8.
    python3 eval_l1sp_trigger.py \
      --calib-root ../l1sp_calib_new --run 27409 \
      --evts 0,1,2,3,4,5,6,7,8 --plane U \
      --handscan handscan_27409.csv

    # Override one threshold to see what raising fill_thr to 0.42 does.
    python3 eval_l1sp_trigger.py ... --fill-shape-fill-thr 0.42
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

import numpy as np


# ── Channel-to-plane mapping ─────────────────────────────────────────────────
# PDHD: 2560 channels per APA, with per-APA offsets U=0, V=800, W=1600.
# Hand-scan rows use APA-local U-plane channels (0..799); the dump NPZ stores
# global offline channel numbers, so for APA0 they coincide.

PDHD_PLANE_RANGES = {
    # APA-local lo, hi (half-open) per plane
    'U': (0, 800),
    'V': (800, 1600),
    'W': (1600, 2560),
}


def load_apa_dumps(calib_root, run, evt, apa):
    """Load every NPZ for one (run, evt, apa) triplet and concatenate."""
    pat_dir = os.path.join(calib_root, f'{int(run):06d}_{int(evt)}')
    if not os.path.isdir(pat_dir):
        return None
    files = sorted(f for f in os.listdir(pat_dir)
                   if f.startswith(f'apa{apa}_') and f.endswith('.npz'))
    if not files:
        return None
    parts = [np.load(os.path.join(pat_dir, f)) for f in files]
    out = {}
    # keys are common across files; concatenate per-ROI vectors.
    keys = parts[0].files
    for k in keys:
        if parts[0][k].shape == (1,):
            out[k] = np.array([p[k][0] for p in parts])
        else:
            out[k] = np.concatenate([p[k] for p in parts])
    return out


def filter_to_plane(d, plane, apa):
    """Return a boolean mask selecting ROIs whose channel belongs to the plane."""
    lo, hi = PDHD_PLANE_RANGES[plane]
    lo += 2560 * apa
    hi += 2560 * apa
    return (d['channel'] >= lo) & (d['channel'] < hi)


def apa_local(channels, apa):
    return channels - 2560 * apa


# ── Trigger gate (mirrors C++ decide_trigger in L1SPFilterPD.cxx) ────────────

def apply_gate(d, mask, cfg):
    """Re-apply the multi-arm gate offline using **core sub-window** features.
    Returns flag array same length as masked ROIs (so caller can index with the
    same mask)."""
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


# ── Hand-scan loading + matching ─────────────────────────────────────────────

def load_handscan(path, run, plane):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if int(r['run']) != run:        continue
            if r['plane'] != plane:         continue
            rows.append({
                'evt':  int(r['evt']),
                'ch1':  int(r['ch1']),
                'ch2':  int(r['ch2']),
                't1':   int(r['t1']),
                't2':   int(r['t2']),
                'asym': float(r['asym']),
                'type': r['type'],
                'note': r['note'],
            })
    return rows


def match_event(d, mask, gt_rows, apa, flag_array):
    """For one event: classify each fired ROI as TP/FP and each GT row as hit
    or missed.  Returns (tp_count, fp_count, fired_details, gt_hits)."""
    # Pull masked subset.
    ch  = apa_local(d['channel'][mask], apa)
    rs  = d['roi_start'][mask]
    re_ = d['roi_end'][mask]
    nb  = d['nbin_fit'][mask]
    aw  = d['raw_asym_wide'][mask]
    ef  = d['roi_energy_frac'][mask]
    gm  = d['gmax'][mask]
    fil = d['gauss_fill'][mask]
    fwh = d['gauss_fwhm_frac'][mask]

    fired_idx = np.where(flag_array != 0)[0]

    gt_hits = [False] * len(gt_rows)
    fired_details = []   # (idx, ch, t_lo, t_hi, len, aw, ef, gmax, flag, matched_gt)
    for i in fired_idx:
        c, lo, hi = ch[i], rs[i], re_[i]
        matched = None
        for j, g in enumerate(gt_rows):
            if not (g['ch1'] <= c <= g['ch2']):     continue
            if hi < g['t1'] or lo > g['t2']:        continue
            gt_hits[j] = True
            matched = j
            # don't break: a single fired ROI can mark multiple GT rows
            #   if ranges overlap; the user's table contains a few of those.
        fired_details.append({
            'idx': int(i), 'ch': int(c), 't_lo': int(lo), 't_hi': int(hi),
            'len': int(nb[i]), 'aw': float(aw[i]), 'ef': float(ef[i]),
            'gmax': float(gm[i]), 'fill': float(fil[i]), 'fwhm': float(fwh[i]),
            'flag': int(flag_array[i]),
            'matched_gt': matched,
        })

    tp = sum(1 for r in fired_details if r['matched_gt'] is not None)
    fp = sum(1 for r in fired_details if r['matched_gt'] is None)
    return tp, fp, fired_details, gt_hits


# ── Polarity sanity ──────────────────────────────────────────────────────────

def polarity_sanity(d, mask, gt_rows, apa):
    """For each GT row, find any ROI whose (channel, [t_lo, t_hi]) overlaps,
    and compare sign(raw_asym_wide) vs sign(ratio).  Returns counts."""
    ch  = apa_local(d['channel'][mask], apa)
    rs  = d['roi_start'][mask]
    re_ = d['roi_end'][mask]
    aw  = d['raw_asym_wide'][mask]
    rt  = d['ratio'][mask]
    agree = disagree = no_match = 0
    details = []
    for g in gt_rows:
        cands = np.where(
            (ch >= g['ch1']) & (ch <= g['ch2']) &
            (re_ >= g['t1']) & (rs <= g['t2'])
        )[0]
        if len(cands) == 0:
            no_match += 1
            continue
        # pick the longest candidate ROI — short edge fragments can have
        # extreme asymmetry from a single-tick excursion and mislead polarity.
        lengths = re_[cands] - rs[cands] + 1
        i = cands[np.argmax(lengths)]
        s_aw = np.sign(aw[i])
        s_rt = np.sign(rt[i])
        if s_aw == s_rt or s_aw == 0 or s_rt == 0:
            agree += 1
        else:
            disagree += 1
            details.append({
                'gt': g, 'ch': int(ch[i]),
                't_lo': int(rs[i]), 't_hi': int(re_[i]),
                'aw': float(aw[i]), 'ratio': float(rt[i]),
            })
    return agree, disagree, no_match, details


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--calib-root', required=True,
                   help='directory containing <RUN>_<EVT>/apa<N>_*.npz')
    p.add_argument('--run', type=int, required=True)
    p.add_argument('--evts', required=True,
                   help='comma-separated event ids, e.g. 0,1,2,3')
    p.add_argument('--plane', default='U', choices=['U', 'V', 'W'])
    p.add_argument('--apa', type=int, default=0)
    p.add_argument('--handscan', required=True)
    # Optional gate overrides — defaults match the C++ defaults.
    p.add_argument('--min-length', type=int, default=30)
    p.add_argument('--gmax-min', type=float, default=1500.0)
    p.add_argument('--energy-frac-thr', type=float, default=0.66)
    p.add_argument('--asym-strong', type=float, default=0.65)
    p.add_argument('--asym-mod', type=float, default=0.40)
    p.add_argument('--asym-loose', type=float, default=0.30)
    p.add_argument('--len-long-mod', type=int, default=100)
    p.add_argument('--len-long-loose', type=int, default=200)
    p.add_argument('--len-fill-shape', type=int, default=50)
    p.add_argument('--fill-shape-fill-thr', type=float, default=0.38)
    p.add_argument('--fill-shape-fwhm-thr', type=float, default=0.30)
    p.add_argument('--use-cpp-flag', action='store_true',
                   help='use the live flag_l1 from the dump instead of '
                        'recomputing it offline (overrides --asym-* etc.)')
    p.add_argument('--show-fp-details', action='store_true')
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
    print(f'Trigger config: {cfg}')
    print(f'use_cpp_flag={args.use_cpp_flag}')
    print()

    evts = [int(x) for x in args.evts.split(',')]
    handscan = load_handscan(args.handscan, args.run, args.plane)

    tot_tp = tot_fp = tot_gt = tot_hit = 0
    tot_agree = tot_disagree = tot_nomatch = 0
    print(f'{"evt":>4} {"GT":>3} {"hit":>3} {"miss":>4} {"fired":>5} '
          f'{"TP":>3} {"FP":>3} {"sens":>5} {"FPrate":>6}')
    for evt in evts:
        d = load_apa_dumps(args.calib_root, args.run, evt, args.apa)
        if d is None:
            print(f'{evt:>4}  no dump')
            continue
        mask = filter_to_plane(d, args.plane, args.apa)
        if args.use_cpp_flag:
            flag = d['flag_l1'][mask].astype(np.int32)
        else:
            flag = apply_gate(d, mask, cfg)

        gt_rows = [g for g in handscan if g['evt'] == evt]
        tp, fp, fired_details, gt_hits = match_event(
            d, mask, gt_rows, args.apa, flag)
        agree, disagree, nomatch, sanity_details = polarity_sanity(
            d, mask, gt_rows, args.apa)

        n_fired = (flag != 0).sum()
        n_gt    = len(gt_rows)
        n_hit   = sum(gt_hits)
        sens    = n_hit / n_gt if n_gt else 0.0
        fprate  = fp / n_fired if n_fired else 0.0
        print(f'{evt:>4} {n_gt:>3d} {n_hit:>3d} {n_gt-n_hit:>4d} '
              f'{n_fired:>5d} {tp:>3d} {fp:>3d} '
              f'{sens:>5.2f} {fprate:>6.2f}')

        # surface missed GT rows
        for j, hit in enumerate(gt_hits):
            if not hit:
                g = gt_rows[j]
                print(f'    MISS evt={evt} ch={g["ch1"]}-{g["ch2"]} '
                      f't=[{g["t1"]},{g["t2"]}] asym={g["asym"]:+.2f} '
                      f'type={g["type"]} note="{g["note"]}"')
        if args.show_fp_details:
            for r in fired_details:
                if r['matched_gt'] is None:
                    print(f'    FP   evt={evt} ch={r["ch"]:>4d} '
                          f't=[{r["t_lo"]},{r["t_hi"]}] len={r["len"]:>3d} '
                          f'aw={r["aw"]:+.2f} ef={r["ef"]:.2f} '
                          f'gm={r["gmax"]:.0f} fl={r["fill"]:.2f} '
                          f'fw={r["fwhm"]:.2f} flag={r["flag"]:+d}')

        tot_tp += tp; tot_fp += fp; tot_gt += n_gt; tot_hit += n_hit
        tot_agree += agree; tot_disagree += disagree; tot_nomatch += nomatch

    print()
    print(f'AGGREGATE  GT={tot_gt} hit={tot_hit} miss={tot_gt - tot_hit}  '
          f'TP={tot_tp} FP={tot_fp}  '
          f'sensitivity={tot_hit / max(tot_gt, 1):.2f} '
          f'FP/fired={tot_fp / max(tot_tp + tot_fp, 1):.2f}')
    print(f'Polarity sanity: '
          f'agree={tot_agree} disagree={tot_disagree} '
          f'no_match={tot_nomatch}')


if __name__ == '__main__':
    sys.exit(main() or 0)
