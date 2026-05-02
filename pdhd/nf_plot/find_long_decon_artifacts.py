#!/usr/bin/env python3
"""
Detect long-decon induction-plane artifacts in PDHD magnify root files.

For each induction-plane (U, V) channel, finds ROIs where the gauss deconvolved
signal is anomalously long in time -- the signature of a unipolar raw waveform
passed through a bipolar deconvolution kernel ("collection-on-induction" or
"anode-induction").

Usage:
    python find_long_decon_artifacts.py --run 27409 --evt 0 --apa 0
    python find_long_decon_artifacts.py --run 27409 --evt 0 --apa 0 --validate
    python find_long_decon_artifacts.py --run 27409 --evt 0 --apa 0 --csv out.csv
    python find_long_decon_artifacts.py --run 27409 --evt 0 --apa 0 --magnify-dir /path/to/dir

Default magnify-dir is <script>/../work/<RUN_PADDED>_<EVT>/, which matches the
output layout of run_nf_sp_evt.sh.

Threshold knobs (all have defaults; pass --help for the full list):
  --g-thr     Gauss threshold (ADC)                        default 50
  --l-min     Min ROI length for pre-filter (ticks)        default 30
  --l-long    Length-only trigger threshold (ticks)        default 80
  --l-combo   Min length for fill_shape trigger            default 50
  --l-asym    Min length for asym trigger                  default 30
  --ff-thr    Fill-factor threshold for fill_shape         default 0.38
  --fwhm-thr  FWHM/length threshold for fill_shape         default 0.30
  --a-thr     |raw_asym| threshold for asym trigger        default 0.50
  --raw-eps          Raw noise floor (ADC)                        default 20
  --pad-ticks        Pad around ROI for raw asym window           default 20
  --planes           Planes to scan (e.g. UV)                     default UV
  --gmax-min         Drop candidates with gauss_max below this    default 1500
  --track-ch-window  Half-width (channels) for slope neighbour search  default 8
  --track-slope-thr  Median |slope| (ticks/ch) >= this => track   default 25
  --track-min-nbrs   Min neighbours required for slope rule       default 4
  --track-t-window   Max |Δt_peak| (ticks) for neighbour inclusion  default 200
  --asym-strong      |asym| at-or-above this passes any length      default 0.65
  --asym-mod         |asym| threshold paired with len-long/fill_shape  default 0.40
  --asym-loose       |asym| threshold paired with len-vlong          default 0.30
  --len-long         length (ticks) for asym-mod gate                default 100
  --len-vlong        length (ticks) for asym-loose gate              default 200
  --cluster-ch-gap   max channel gap for cluster merging             default 1
  --energy-pad-ticks half-window (ticks) for ROI energy fraction     default 500
  --energy-frac-thr  min cluster max-member roi_energy_frac to keep  default 0.66
  --probe-ch-max     max channels to walk for boundary extension     default 20
  --probe-pad-ticks  pad around cluster t-range when probing         default 20
  --probe-a-thr      |raw_asym| threshold for boundary extension     default 0.25

A cluster is kept iff
  cl.roi_energy_frac_max >= energy-frac-thr  (isolated-lobe gate;
                                              rejects "long-train" FPs)
AND any of:
  (a) |asym| >= asym-strong
  (b) length >= len-long  AND |asym| >= asym-mod
  (c) length >= len-vlong AND |asym| >= asym-loose
  (d) fill_shape triggered AND |asym| >= asym-mod
"""

import argparse
import csv
import os
import sys
import numpy as np


# ------------------------------------------------------------------
# Hand-scan ground truth (R=27409, APA=0) for --validate mode.
# ch_lo/ch_hi: APA-local absolute channel numbers.
# t_ref: approximate tick center identified in the hand scan.
# ------------------------------------------------------------------
GROUND_TRUTH = [
    dict(run=27409, evt=0, apa=0, plane='U', ch_lo=324, ch_hi=326, t_ref=5850),
    dict(run=27409, evt=0, apa=0, plane='U', ch_lo=286, ch_hi=286, t_ref=2850),
    dict(run=27409, evt=1, apa=0, plane='U', ch_lo=540, ch_hi=565, t_ref=4800),
    dict(run=27409, evt=1, apa=0, plane='U', ch_lo=566, ch_hi=568, t_ref=4250),
    dict(run=27409, evt=1, apa=0, plane='U', ch_lo=578, ch_hi=578, t_ref=1700),
    dict(run=27409, evt=2, apa=0, plane='U', ch_lo=183, ch_hi=185, t_ref=5700),
    dict(run=27409, evt=2, apa=0, plane='U', ch_lo=714, ch_hi=714, t_ref=4870),
    dict(run=27409, evt=2, apa=0, plane='U', ch_lo=39,  ch_hi=41,  t_ref=1100),
]

# (plane_label, raw_hist_prefix, gauss_hist_prefix, ch_offset)
# ch_offset: APA-local absolute channel = array_index + ch_offset
PLANE_DEFS = [
    ('U', 'hu_raw', 'hu_gauss',   0),
    ('V', 'hv_raw', 'hv_gauss', 800),
]


def find_rois(arr1d, thr):
    """Find contiguous runs where |arr1d| > thr. Returns list of (lo, hi) inclusive."""
    mask = np.abs(arr1d) > thr
    rois = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            rois.append((i, j))
            i = j + 1
        else:
            i += 1
    return rois


def shape_features(gauss, raw, t_lo, t_hi, raw_eps, pad_ticks, energy_pad):
    """
    Compute per-ROI discriminant features for gauss ROI [t_lo, t_hi] inclusive.
    Returns (length, fill_factor, fwhm_frac, raw_asym, gmax, roi_energy_frac).

    roi_energy_frac = |gauss| energy in the ROI divided by |gauss| energy in
    [t_lo - energy_pad, t_hi + energy_pad]. A real isolated unipolar artifact
    has its energy concentrated in one ROI (frac near 1); a "long train" of
    multiple gauss peaks has energy scattered (frac well below 1).
    """
    nticks = len(gauss)
    seg = gauss[t_lo:t_hi + 1]
    aseg = np.abs(seg)
    gmax = float(aseg.max())
    length = t_hi - t_lo + 1
    fill = float(aseg.sum()) / (gmax * length + 1e-9)
    fwhm = int((aseg > 0.5 * gmax).sum())
    fwhm_frac = fwhm / length

    # raw asymmetry over the padded window; range [-1, +1]
    r_lo = max(0, t_lo - pad_ticks)
    r_hi = min(nticks - 1, t_hi + pad_ticks)
    raw_seg = raw[r_lo:r_hi + 1]
    pos = float(raw_seg[raw_seg >  raw_eps].sum())
    neg = float(raw_seg[raw_seg < -raw_eps].sum())
    denom = pos - neg  # always >= 0
    raw_asym = (pos + neg) / (denom + 1e-9)

    # ROI gauss energy fraction within the wide window
    e_lo = max(0, t_lo - energy_pad)
    e_hi = min(nticks - 1, t_hi + energy_pad)
    roi_energy = float(aseg.sum())
    wide_energy = float(np.abs(gauss[e_lo:e_hi + 1]).sum())
    roi_energy_frac = roi_energy / (wide_energy + 1e-9)

    return length, fill, fwhm_frac, raw_asym, gmax, roi_energy_frac


def process_plane(gauss_all, raw_all, plane, ch_offset, args):
    """
    Scan all channels in one plane.
    gauss_all, raw_all: (n_channels, n_ticks).
    Returns list of per-channel candidate ROI dicts.
    """
    nch = gauss_all.shape[0]
    candidates = []

    for idx in range(nch):
        gauss = gauss_all[idx]
        raw = raw_all[idx]
        ch = idx + ch_offset

        for t_lo, t_hi in find_rois(gauss, args.g_thr):
            length = t_hi - t_lo + 1
            if length < args.l_min:
                continue

            length, fill, fwhm_frac, raw_asym, gmax, roi_energy_frac = shape_features(
                gauss, raw, t_lo, t_hi, args.raw_eps, args.pad_ticks,
                args.energy_pad_ticks)

            triggered = []
            if length >= args.l_long:
                triggered.append('L_long')
            if length >= args.l_combo:
                if fill <= args.ff_thr and fwhm_frac <= args.fwhm_thr:
                    triggered.append('fill_shape')
            if length >= args.l_asym and abs(raw_asym) >= args.a_thr:
                triggered.append('asym')

            if not triggered:
                continue
            if gmax < args.gmax_min:
                continue

            candidates.append(dict(
                plane=plane, ch=ch, t_lo=t_lo, t_hi=t_hi,
                length=length, fill=fill, fwhm_frac=fwhm_frac,
                raw_asym=raw_asym, gmax=gmax, triggered=triggered,
                roi_energy_frac=roi_energy_frac,
            ))

    return candidates


def cluster_candidates(candidates, ch_gap=20):
    """
    Merge channel-near (|Δch| ≤ ch_gap) candidates with overlapping tick spans
    into cluster dicts. Time-overlap is still required, so unrelated artifacts
    sharing a channel region but living at different drift times stay separate.
    """
    if not candidates:
        return []

    cands = sorted(candidates, key=lambda c: (c['plane'], c['ch'], c['t_lo']))
    used = [False] * len(cands)
    clusters = []

    for i, c in enumerate(cands):
        if used[i]:
            continue
        cl = dict(
            plane=c['plane'],
            ch_lo=c['ch'], ch_hi=c['ch'],
            t_lo=c['t_lo'], t_hi=c['t_hi'],
            n_channels=1,
            length_max=c['length'],
            gauss_max=c['gmax'],
            fill_min=c['fill'],
            fwhm_frac_min=c['fwhm_frac'],
            raw_asym_extreme=c['raw_asym'],
            roi_energy_frac_max=c['roi_energy_frac'],
            triggered=set(c['triggered']),
        )
        used[i] = True

        # grow cluster greedily
        changed = True
        while changed:
            changed = False
            for j, d in enumerate(cands):
                if used[j] or d['plane'] != cl['plane']:
                    continue
                if not (cl['ch_lo'] - ch_gap <= d['ch'] <= cl['ch_hi'] + ch_gap):
                    continue
                if d['t_lo'] > cl['t_hi'] or d['t_hi'] < cl['t_lo']:
                    continue
                cl['ch_lo'] = min(cl['ch_lo'], d['ch'])
                cl['ch_hi'] = max(cl['ch_hi'], d['ch'])
                cl['t_lo']  = min(cl['t_lo'],  d['t_lo'])
                cl['t_hi']  = max(cl['t_hi'],  d['t_hi'])
                cl['n_channels'] += 1
                cl['length_max']  = max(cl['length_max'],  d['length'])
                cl['gauss_max']   = max(cl['gauss_max'],   d['gmax'])
                cl['fill_min']    = min(cl['fill_min'],    d['fill'])
                cl['fwhm_frac_min'] = min(cl['fwhm_frac_min'], d['fwhm_frac'])
                if abs(d['raw_asym']) > abs(cl['raw_asym_extreme']):
                    cl['raw_asym_extreme'] = d['raw_asym']
                if d['roi_energy_frac'] > cl['roi_energy_frac_max']:
                    cl['roi_energy_frac_max'] = d['roi_energy_frac']
                cl['triggered'].update(d['triggered'])
                used[j] = True
                changed = True

        cl['triggered'] = '+'.join(sorted(cl['triggered']))
        clusters.append(cl)

    return clusters


def track_filter(candidates, ch_window=8, slope_thr=25.0, min_neighbors=4, t_window=200):
    """
    Drop candidates that look like track bodies rather than artifacts.

    For each candidate at (plane, ch, t_peak), collect neighbours at the same
    plane within ch ± ch_window whose t_peak is also within ± t_window ticks
    (guards against candidates on the same channel or adjacent channels but from
    a completely different physics feature contaminating the slope estimate).
    Compute slope = Δt_peak / Δch for each qualifying neighbour.  If at least
    min_neighbors such neighbours exist and their median |slope| >= slope_thr
    (ticks/ch), the candidate is classified as a track body and excluded.

    Artifacts live at the same time on adjacent channels → few qualifying
    neighbours (short cluster) or small median slope (consistent midpoints).
    Track bodies span many consecutive channels with steadily shifting t_peak →
    many neighbours, large consistent slopes.
    """
    by_ch = {}
    for c in candidates:
        by_ch.setdefault((c['plane'], c['ch']), []).append(c)

    surviving = []
    for c in candidates:
        t_peak = (c['t_lo'] + c['t_hi']) / 2.0
        slopes = []
        for delta in range(1, ch_window + 1):
            for direction in (+1, -1):
                nbr_ch = c['ch'] + direction * delta
                for n in by_ch.get((c['plane'], nbr_ch), []):
                    n_t_peak = (n['t_lo'] + n['t_hi']) / 2.0
                    if abs(n_t_peak - t_peak) > t_window:
                        continue
                    slopes.append((n_t_peak - t_peak) / (nbr_ch - c['ch']))
        if len(slopes) >= min_neighbors:
            abs_slopes = sorted(abs(s) for s in slopes)
            median_slope = abs_slopes[len(abs_slopes) // 2]
            if median_slope >= slope_thr:
                continue
        surviving.append(c)
    return surviving


def cluster_pass(cl, asym_strong, asym_mod, asym_loose, len_long, len_vlong,
                 energy_frac_thr):
    """
    Multi-tier keep test: keep a cluster iff
      cl.roi_energy_frac_max >= energy_frac_thr  (isolated-lobe gate)
    AND any of
      (a) |asym| >= asym_strong
      (b) length >= len_long  AND |asym| >= asym_mod
      (c) length >= len_vlong AND |asym| >= asym_loose
      (d) fill_shape triggered AND |asym| >= asym_mod
    """
    if cl['roi_energy_frac_max'] < energy_frac_thr:
        return False
    asym = abs(cl['raw_asym_extreme'])
    L = cl['length_max']
    is_fill_shape = 'fill_shape' in cl['triggered']
    if asym >= asym_strong:
        return True
    if L >= len_long and asym >= asym_mod:
        return True
    if L >= len_vlong and asym >= asym_loose:
        return True
    if is_fill_shape and asym >= asym_mod:
        return True
    return False


def extend_cluster_boundaries(clusters, raw_by_plane,
                              probe_max, probe_pad, probe_a_thr, raw_eps):
    """
    For each cluster, walk outward by ±1 channel up to ±probe_max. On each
    side, compute raw_asym at that channel within [t_lo - probe_pad,
    t_hi + probe_pad]. If sign matches sign(cl.raw_asym_extreme) and
    |raw_asym| >= probe_a_thr, absorb the channel into ch_lo/ch_hi and
    continue outward; otherwise stop on that side.

    Purely cosmetic: never adds or removes clusters, only widens reported
    ch_lo/ch_hi of already-confirmed survivors.
    """
    for cl in clusters:
        info = raw_by_plane.get(cl['plane'])
        if info is None:
            continue
        raw_arr, ch_offset = info  # raw_arr: (nch, nticks)
        nch_arr = raw_arr.shape[0]
        nticks = raw_arr.shape[1]
        target_sign = 1 if cl['raw_asym_extreme'] >= 0 else -1

        t_lo = max(0, cl['t_lo'] - probe_pad)
        t_hi = min(nticks - 1, cl['t_hi'] + probe_pad)

        def asym_at(ch_abs):
            idx = ch_abs - ch_offset
            if idx < 0 or idx >= nch_arr:
                return None
            seg = raw_arr[idx, t_lo:t_hi + 1]
            pos = float(seg[seg >  raw_eps].sum())
            neg = float(seg[seg < -raw_eps].sum())
            denom = pos - neg
            return (pos + neg) / (denom + 1e-9)

        # walk up
        for step in range(1, probe_max + 1):
            ch = cl['ch_hi'] + 1
            a = asym_at(ch)
            if a is None:
                break
            sgn = 1 if a >= 0 else -1
            if sgn == target_sign and abs(a) >= probe_a_thr:
                cl['ch_hi'] = ch
            else:
                break

        # walk down
        for step in range(1, probe_max + 1):
            ch = cl['ch_lo'] - 1
            a = asym_at(ch)
            if a is None:
                break
            sgn = 1 if a >= 0 else -1
            if sgn == target_sign and abs(a) >= probe_a_thr:
                cl['ch_lo'] = ch
            else:
                break

    return clusters


def print_table(clusters, run, evt, apa):
    if not clusters:
        print("No artifacts detected.")
        return
    h = "{:<7}{:<5}{:<5}{:<6}{:<7}{:<7}{:<6}{:<7}{:<5}{:<9}{:<10}{:<10}{:<12}{:<14}{:<10}{}"
    print(h.format(
        'run', 'evt', 'apa', 'plane', 'ch_lo', 'ch_hi',
        't_lo', 't_hi', 'nch', 'len_max', 'gmax',
        'fill_min', 'fwhm_f_min', 'asym_extreme', 'efrac_max', 'triggered'))
    for cl in clusters:
        print(h.format(
            run, evt, apa, cl['plane'],
            cl['ch_lo'], cl['ch_hi'], cl['t_lo'], cl['t_hi'],
            cl['n_channels'], cl['length_max'],
            f"{cl['gauss_max']:.0f}", f"{cl['fill_min']:.2f}",
            f"{cl['fwhm_frac_min']:.2f}", f"{cl['raw_asym_extreme']:+.2f}",
            f"{cl['roi_energy_frac_max']:.2f}",
            cl['triggered']))



def write_csv(clusters, run, evt, apa, path):
    fields = ['run', 'evt', 'apa', 'plane', 'ch_lo', 'ch_hi', 't_lo', 't_hi',
              'n_channels', 'length_max', 'gauss_max', 'fill_factor_min',
              'fwhm_frac_min', 'raw_asym_extreme', 'roi_energy_frac_max',
              'triggered_by']
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for cl in clusters:
            w.writerow({
                'run': run, 'evt': evt, 'apa': apa,
                'plane': cl['plane'],
                'ch_lo': cl['ch_lo'], 'ch_hi': cl['ch_hi'],
                't_lo': cl['t_lo'],   't_hi': cl['t_hi'],
                'n_channels': cl['n_channels'],
                'length_max': cl['length_max'],
                'gauss_max': f"{cl['gauss_max']:.1f}",
                'fill_factor_min': f"{cl['fill_min']:.3f}",
                'fwhm_frac_min': f"{cl['fwhm_frac_min']:.3f}",
                'raw_asym_extreme': f"{cl['raw_asym_extreme']:+.3f}",
                'roi_energy_frac_max': f"{cl['roi_energy_frac_max']:.3f}",
                'triggered_by': cl['triggered'],
            })
    print(f"CSV written: {path}")


def validate(clusters, args):
    """
    Compare detected clusters against the hand-scan ground truth for this
    (run, evt, apa). Print HIT / MISS / EXTRA summary.
    """
    gt_rows = [g for g in GROUND_TRUTH
               if g['run'] == args.run and g['evt'] == args.evt and g['apa'] == args.apa]
    if not gt_rows:
        print("No ground-truth entries for this (run, evt, apa). Skipping validation.")
        return

    tol = 200  # tick tolerance for t_ref match

    def overlaps(cl, gt):
        if cl['plane'] != gt['plane']:
            return False
        ch_hit = (cl['ch_lo'] <= gt['ch_hi'] + 1) and (cl['ch_hi'] >= gt['ch_lo'] - 1)
        t_hit  = (cl['t_lo']  <= gt['t_ref'] + tol) and (cl['t_hi'] >= gt['t_ref'] - tol)
        return ch_hit and t_hit

    hit_gt = set()
    hit_cl = set()
    for gi, gt in enumerate(gt_rows):
        for ci, cl in enumerate(clusters):
            if overlaps(cl, gt):
                hit_gt.add(gi)
                hit_cl.add(ci)

    print(f"\n{'='*70}")
    print(f"VALIDATION: run={args.run} evt={args.evt} apa={args.apa}")
    print(f"  Ground-truth entries : {len(gt_rows)}")
    print(f"  Detected clusters    : {len(clusters)}")
    print(f"  Hits                 : {len(hit_gt)}/{len(gt_rows)}")
    print(f"  Extra (not in GT)    : {len(clusters) - len(hit_cl)}")
    print(f"{'='*70}")

    print("\n--- Ground-truth status ---")
    fmt = "  {:<6} {:<7} {:<7} {:<8}  {}"
    print(fmt.format('plane', 'ch_lo', 'ch_hi', 't_ref', 'status'))
    for gi, gt in enumerate(gt_rows):
        status = 'HIT' if gi in hit_gt else 'MISS'
        print(fmt.format(gt['plane'], gt['ch_lo'], gt['ch_hi'], gt['t_ref'], status))

    extra = [(ci, cl) for ci, cl in enumerate(clusters) if ci not in hit_cl]
    if extra:
        print(f"\n--- Extra detections ({len(extra)}) ---")
        h = "  {:<5}{:<7}{:<7}{:<6}{:<6}{:<5}{:<9}{:<10}{:<10}{:<12}{:<14}{:<10}{}"
        print(h.format('plane', 'ch_lo', 'ch_hi', 't_lo', 't_hi', 'nch',
                       'len_max', 'gmax', 'fill_min', 'fwhm_f_min',
                       'asym_extreme', 'efrac_max', 'triggered'))
        for _, cl in extra:
            print(h.format(
                cl['plane'], cl['ch_lo'], cl['ch_hi'], cl['t_lo'], cl['t_hi'],
                cl['n_channels'], cl['length_max'], f"{cl['gauss_max']:.0f}",
                f"{cl['fill_min']:.2f}", f"{cl['fwhm_frac_min']:.2f}",
                f"{cl['raw_asym_extreme']:+.2f}",
                f"{cl['roi_energy_frac_max']:.2f}", cl['triggered']))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run',  type=int, required=True,  help='Run number')
    parser.add_argument('--evt',  type=int, required=True,  help='Event number')
    parser.add_argument('--apa',  type=int, required=True,  help='APA index')
    parser.add_argument('--magnify-dir', default=None,
                        help='Directory containing magnify root file '
                             '(default: <script>/../work/<RUN_PADDED>_<EVT>/)')
    parser.add_argument('--csv', default=None, metavar='PATH',
                        help='Write detections to CSV file')
    parser.add_argument('--planes', default='UV',
                        help='Planes to scan (default: UV)')
    parser.add_argument('--validate', action='store_true',
                        help='Compare against hand-scan ground truth')
    # Threshold knobs
    parser.add_argument('--g-thr',     type=float, default=50.0,
                        help='Gauss threshold ADC (default 50)')
    parser.add_argument('--l-min',     type=int,   default=30,
                        help='Min ROI length for pre-filter (default 30)')
    parser.add_argument('--l-long',    type=int,   default=80,
                        help='Length-only trigger threshold (default 80)')
    parser.add_argument('--l-combo',   type=int,   default=50,
                        help='Min length for fill_shape trigger (default 50)')
    parser.add_argument('--l-asym',    type=int,   default=30,
                        help='Min length for asym trigger (default 30)')
    parser.add_argument('--ff-thr',    type=float, default=0.38,
                        help='Fill-factor threshold for fill_shape trigger (default 0.38)')
    parser.add_argument('--fwhm-thr',  type=float, default=0.30,
                        help='FWHM/length threshold for fill_shape trigger (default 0.30)')
    parser.add_argument('--a-thr',     type=float, default=0.50,
                        help='|raw_asym| threshold for asym trigger (default 0.50)')
    parser.add_argument('--raw-eps',   type=float, default=20.0,
                        help='Raw noise floor ADC (default 20)')
    parser.add_argument('--pad-ticks', type=int,   default=20,
                        help='Pad around ROI for raw asym window (default 20)')
    parser.add_argument('--gmax-min',       type=float, default=1500.0,
                        help='Drop candidates with gauss_max below this (default 1500)')
    parser.add_argument('--track-ch-window', type=int,  default=8,
                        help='Half-width (ch) for track-slope neighbour search (default 8)')
    parser.add_argument('--track-slope-thr', type=float, default=25.0,
                        help='Median |slope| ticks/ch >= this classifies as track (default 25)')
    parser.add_argument('--track-min-nbrs', type=int,   default=4,
                        help='Min neighbours required before slope rule applies (default 4)')
    parser.add_argument('--track-t-window', type=int,   default=200,
                        help='Max |Δt_peak| (ticks) to include a neighbour in slope (default 200)')
    parser.add_argument('--asym-strong', type=float, default=0.65,
                        help='|asym| >= this passes regardless of length (default 0.65)')
    parser.add_argument('--asym-mod',    type=float, default=0.40,
                        help='|asym| threshold paired with len-long/fill_shape (default 0.40)')
    parser.add_argument('--asym-loose',  type=float, default=0.30,
                        help='|asym| threshold paired with len-vlong (default 0.30)')
    parser.add_argument('--len-long',    type=int,   default=100,
                        help='Length threshold for asym-mod gate (default 100)')
    parser.add_argument('--len-vlong',   type=int,   default=200,
                        help='Length threshold for asym-loose gate (default 200)')
    parser.add_argument('--cluster-ch-gap', type=int, default=1,
                        help='Max channel gap (chs) for cluster merging (default 1)')
    parser.add_argument('--energy-pad-ticks', type=int, default=500,
                        help='Half-window (ticks) for ROI energy-fraction (default 500)')
    parser.add_argument('--energy-frac-thr', type=float, default=0.66,
                        help='Min cluster max-member roi_energy_frac to keep (default 0.66)')
    parser.add_argument('--probe-ch-max', type=int, default=20,
                        help='Max channels to walk outward when extending boundaries (default 20)')
    parser.add_argument('--probe-pad-ticks', type=int, default=20,
                        help='Pad around cluster t-range when probing extension (default 20)')
    parser.add_argument('--probe-a-thr', type=float, default=0.25,
                        help='|raw_asym| threshold for boundary extension (default 0.25)')
    args = parser.parse_args()

    try:
        import uproot
    except ImportError:
        print("ERROR: uproot not found. Install with: pip install uproot", file=sys.stderr)
        sys.exit(1)

    run_padded = f"{args.run:06d}"
    if args.magnify_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.magnify_dir = os.path.join(
            script_dir, '..', 'work', f'{run_padded}_{args.evt}')

    fname = os.path.join(
        args.magnify_dir,
        f'magnify-run{run_padded}-evt{args.evt}-apa{args.apa}.root')
    if not os.path.exists(fname):
        print(f"ERROR: file not found: {fname}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {fname}")
    f = uproot.open(fname)

    plane_filter = args.planes.upper()
    all_candidates = []
    raw_by_plane = {}  # plane label -> (raw_all, ch_offset) for boundary extension

    for plane, raw_pfx, gauss_pfx, ch_offset in PLANE_DEFS:
        if plane not in plane_filter:
            continue
        rk = f'{raw_pfx}{args.apa}'
        gk = f'{gauss_pfx}{args.apa}'
        try:
            raw_all   = f[rk].values()
            gauss_all = f[gk].values()
        except KeyError:
            print(f"  plane {plane}: histogram {rk} not found in file, skipping")
            continue
        print(f"  plane {plane}: {raw_all.shape[0]} channels x {raw_all.shape[1]} ticks")
        cands = process_plane(gauss_all, raw_all, plane, ch_offset, args)
        print(f"  plane {plane}: {len(cands)} candidates pre-clustering")
        all_candidates.extend(cands)
        raw_by_plane[plane] = (raw_all, ch_offset)

    all_candidates = track_filter(
        all_candidates,
        ch_window=args.track_ch_window,
        slope_thr=args.track_slope_thr,
        min_neighbors=args.track_min_nbrs,
        t_window=args.track_t_window)
    print(f"  {len(all_candidates)} candidates after track filter")

    clusters = cluster_candidates(all_candidates, ch_gap=args.cluster_ch_gap)
    clusters = [cl for cl in clusters
                if cluster_pass(cl,
                                asym_strong=args.asym_strong,
                                asym_mod=args.asym_mod,
                                asym_loose=args.asym_loose,
                                len_long=args.len_long,
                                len_vlong=args.len_vlong,
                                energy_frac_thr=args.energy_frac_thr)]
    if args.probe_ch_max > 0:
        clusters = extend_cluster_boundaries(
            clusters, raw_by_plane,
            probe_max=args.probe_ch_max,
            probe_pad=args.probe_pad_ticks,
            probe_a_thr=args.probe_a_thr,
            raw_eps=args.raw_eps)
    clusters.sort(key=lambda c: (c['plane'], c['ch_lo'], c['t_lo']))

    print(f"\n{len(clusters)} artifact cluster(s) detected\n")
    print_table(clusters, args.run, args.evt, args.apa)

    if args.csv:
        write_csv(clusters, args.run, args.evt, args.apa, args.csv)

    if args.validate:
        validate(clusters, args)


if __name__ == '__main__':
    main()
