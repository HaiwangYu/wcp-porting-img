#!/usr/bin/env python3
"""
Validator for the PDVD L1SPFilterPD response kernels.

Loads the kernel JSON+bz2 files produced by ``wirecell-sigproc
gen-l1sp-kernels -d pdvd-{top,bottom}`` and produces inspection PNGs
analogous to the PDHD validator at
``pdhd/nf_plot/track_response_l1sp_kernels.py``.

Outputs (in this directory, alongside the script):

  track_response_l1sp_pdvd_top_U.png
  track_response_l1sp_pdvd_top_V.png
  track_response_l1sp_pdvd_bottom_U.png
  track_response_l1sp_pdvd_bottom_V.png
  track_response_l1sp_pdvd_compare.png       — top vs bottom overlay

Each per-plane PNG has two stacked panels:
  - top:    positive ROI  — bipolar (induction) + W (collection,
            shifted so its peak lands at the bipolar zero crossing)
  - bottom: negative ROI  — bipolar (induction) + neg-half(bipolar),
            no shift.

The compare PNG overlays top and bottom bipolar+W kernels on a shared
time axis (relative to each detector's own V-plane zero crossing) so
the relative time shift between the two CRPs is visible at a glance.

Defaults: load ``pdvd_top_l1sp_kernels.json.bz2`` and
``pdvd_bottom_l1sp_kernels.json.bz2`` from ``WIRECELL_PATH``.
"""

import argparse
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from wirecell.sigproc.l1sp import build_l1sp_kernels, load_l1sp_kernels, negative_half
from wirecell.sigproc.track_response import load_detector_config
from wirecell import units

WORKDIR = os.path.dirname(os.path.abspath(__file__))


def _rebuild_from_fr(detector_key):
    """Rebuild PDVD kernels from the same fr/elec preset that produced the JSON files."""
    cfg = load_detector_config(detector_key)
    er_kind = cfg.get('er_kind', 'cold')
    ow = cfg.get('output_window')
    return build_l1sp_kernels(
        fr_file               = cfg['fr'],
        gain                  = cfg['gain']    if er_kind == 'cold' else 0.0,
        shaping               = cfg['shaping'] if er_kind == 'cold' else 0.0,
        postgain              = cfg['postgain'],
        adc_per_mv            = cfg['adc_per_mv'],
        coarse_time_offset_us = -8.0,
        fine_time_offset_us   =  0.0,
        er_kind               = er_kind,
        er_file               = cfg.get('er_file'),
        output_window_us      = float(ow / units.us) if ow else None,
    )

# PDVD U/V wire pitch is 7.65 mm.  Used only for the ADC×N_MIP overlay.
PDVD_PITCH_CM = 0.765

# Time-axis x-limits relative to V-plane zero crossing.  PDVD's bipolar
# tail is longer than PDHD's so we extend the window slightly.
PLOT_XLIM = (-10, 15)

# Per-detector colour palette for the compare figure (matches PDHD style).
COLOR_TOP    = 'crimson'
COLOR_BOTTOM = 'steelblue'


def _n_mip(pitch_cm):
    """MIP electrons per wire pitch (1.8 MeV/cm, 70% recombination, 23.6 eV/pair)."""
    return (1.8e6 * pitch_cm * 0.7) / 23.6


def _kernels_to_data(kdict, label):
    """Reshape a kernel dict into {kU, kV, kW, t_us, N_mip, label, meta, planes}."""
    meta = kdict['meta']
    n = meta['n_samples']
    t_us = meta['t0_us'] + np.arange(n) * (meta['period_ns'] / 1000.0)

    by_idx = {p['plane_index']: p for p in kdict['planes']}
    kU = np.asarray(by_idx[0]['positive']['bipolar'])
    kV = np.asarray(by_idx[1]['positive']['bipolar'])
    # W kernel is shared across U/V positive blocks; take from U.
    kW = np.asarray(by_idx[0]['positive']['unipolar'])

    return dict(kU=kU, kV=kV, kW=kW, t_us=t_us,
                N_mip=_n_mip(PDVD_PITCH_CM),
                label=label, meta=meta, planes=by_idx)


def report(data):
    """Print one-line summary per plane (matches PDHD validator style)."""
    m = data['meta']
    print(f'\n── {data["label"]} ─────────────────────────────────────────────')
    print(f'  fr_file = {m["fr_file"]}')
    print(f'  elec_type = {m["elec_type"]}'
          + (f' (er_file = {m["er_file"]})' if m.get('er_file') else ''))
    print(f'  postgain={m["postgain"]:.4f}  adc_per_mv={m["adc_per_mv"]:.4f}')
    print(f'  period={m["period_ns"]:.4f} ns  t0={m["t0_us"]:+.4f} µs  '
          f'n={m["n_samples"]}'
          + (f' (padded from {m["fr_n_samples_native"]})'
             if 'fr_n_samples_native' in m else ''))
    print(f'  N_MIP/pitch = {data["N_mip"]:.1f} e⁻')
    for label_p, k in (('U', data['kU']), ('V', data['kV']), ('W', data['kW'])):
        peak = float(np.max(np.abs(k)))
        print(f'  {label_p}: |peak|={peak:.4g} ADC/e  →  ×N_MIP={peak * data["N_mip"]:.2f} ADC')
    for plane_idx, plane_label in ((0, 'U'), (1, 'V')):
        p = data['planes'][plane_idx]
        print(f'  {plane_label}: zero-crossing={p["zero_crossing_us"]:+.3f} µs  '
              f'W shift (positive case)={p["positive"]["unipolar_time_offset_us"]:+.3f} µs')


def plot_pdvd_plane(data, plane_idx, outpath, ref_data=None):
    """Two-panel figure for one plane: positive ROI (top) + negative ROI (bottom).

    If ref_data is provided (FR rebuild), its curves are drawn as thick translucent
    bands behind the from-file curves so any mismatch is immediately visible."""
    plane_label = {0: 'U', 1: 'V'}[plane_idx]
    k_bip = data['kU'] if plane_idx == 0 else data['kV']
    t  = data['t_us']
    Nm = data['N_mip']

    t_zc_V    = data['planes'][1]['zero_crossing_us']
    t_plot    = t - t_zc_V
    p         = data['planes'][plane_idx]
    zc_local  = p['zero_crossing_us']
    zc_in_plot = zc_local - t_zc_V
    shift_W   = p['positive']['unipolar_time_offset_us']

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    fig.subplots_adjust(hspace=0.10)

    # positive case: bipolar + W (collection-on-induction)
    ax = axes[0]
    if ref_data is not None:
        r_bip   = ref_data['kU'] if plane_idx == 0 else ref_data['kV']
        r_shift = ref_data['planes'][plane_idx]['positive']['unipolar_time_offset_us']
        ax.plot(t_plot, r_bip * Nm, color='steelblue', lw=4, alpha=0.35, ls='-',
                label='_bipolar (rebuilt from FR)')
        ax.plot(t_plot + r_shift, ref_data['kW'] * Nm, color='darkorange', lw=4, alpha=0.35, ls='-',
                label='_unipolar (rebuilt from FR)')
    ax.plot(t_plot, k_bip * Nm, color='steelblue', lw=1.5,
            label=f'{plane_label}-plane bipolar (×{Nm:.0f} e⁻/pitch)  '
                  f'[zero-crossing at {zc_in_plot:+.2f} µs]')
    ax.plot(t_plot + shift_W, data['kW'] * Nm, color='darkorange', lw=1.5,
            label=f'W-plane unipolar  '
                  f'(W-peak ↔ {plane_label}-zero-crossing; raw shift {shift_W:+.2f} µs)')
    if ref_data is not None:
        ax.plot([], [], color='gray', lw=4, alpha=0.35, label='thick band = rebuilt from FR')
    ax.axhline(0, color='gray', lw=0.5, ls=':')
    ax.axvline(zc_in_plot, color='steelblue', lw=0.5, ls=':')
    ax.set_xlim(PLOT_XLIM)
    ax.set_ylabel('ADC (×N_MIP)')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_title(f'{data["label"]} — {plane_label} plane, positive ROI '
                 f'(collection-on-induction)', fontsize=9)

    # negative case: bipolar + neg-half(bipolar), no shift
    ax = axes[1]
    if ref_data is not None:
        r_bip = ref_data['kU'] if plane_idx == 0 else ref_data['kV']
        ax.plot(t_plot, r_bip * Nm, color='steelblue', lw=4, alpha=0.35, ls='-',
                label='_bipolar (rebuilt from FR)')
        ax.plot(t_plot, negative_half(r_bip) * Nm, color='forestgreen', lw=4, alpha=0.35, ls='-',
                label='_neg-half (rebuilt from FR)')
    ax.plot(t_plot, k_bip * Nm, color='steelblue', lw=1.5,
            label=f'{plane_label}-plane bipolar (×{Nm:.0f} e⁻/pitch)  '
                  f'[zero-crossing at {zc_in_plot:+.2f} µs]')
    ax.plot(t_plot, negative_half(k_bip) * Nm, color='forestgreen', lw=1.5, ls='--',
            label=f'neg-half({plane_label}) — anode-induction unipolar (no shift)')
    if ref_data is not None:
        ax.plot([], [], color='gray', lw=4, alpha=0.35, label='thick band = rebuilt from FR')
    ax.axhline(0, color='gray', lw=0.5, ls=':')
    ax.set_xlim(PLOT_XLIM)
    ax.set_ylabel('ADC (×N_MIP)')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_title(f'{data["label"]} — {plane_label} plane, negative ROI '
                 f'(anode-induction)', fontsize=9)

    axes[-1].set_xlabel('time (µs, relative to V-plane zero crossing)')
    overlay_note = ('  [thick band = rebuilt from FR; thin line = from file]'
                    if ref_data is not None else '')
    fig.suptitle(f'{data["label"]} L1SPFilterPD — {plane_label} plane  '
                 f'(N_MIP/pitch={Nm:.0f} e⁻;  V-zero-crossing @ {t_zc_V:+.2f} µs)'
                 f'{overlay_note}',
                 fontsize=10)
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  → {outpath}')


def plot_compare(top_data, bot_data, outpath, ref_top=None, ref_bot=None):
    """Top-vs-bottom overlay: each plane as one row, bipolar + W on a single
    panel, time axis relative to each detector's own V-plane zero crossing.
    ref_top/ref_bot, if provided, are drawn as thick translucent bands."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.subplots_adjust(hspace=0.12)

    for ax, plane_idx, plane_label in (
        (axes[0], 0, 'U'),
        (axes[1], 1, 'V'),
    ):
        for det, ref, color in ((top_data, ref_top, COLOR_TOP),
                                (bot_data, ref_bot, COLOR_BOTTOM)):
            t_zc_V  = det['planes'][1]['zero_crossing_us']
            t_plot  = det['t_us'] - t_zc_V
            k_bip   = det['kU'] if plane_idx == 0 else det['kV']
            shift_W = det['planes'][plane_idx]['positive']['unipolar_time_offset_us']
            zc_local = det['planes'][plane_idx]['zero_crossing_us'] - t_zc_V

            if ref is not None:
                r_bip   = ref['kU'] if plane_idx == 0 else ref['kV']
                r_shift = ref['planes'][plane_idx]['positive']['unipolar_time_offset_us']
                ax.plot(t_plot, r_bip * ref['N_mip'], color=color, lw=4, alpha=0.35)
                ax.plot(t_plot + r_shift, ref['kW'] * ref['N_mip'],
                        color=color, lw=4, alpha=0.35, ls='--')

            ax.plot(t_plot, k_bip * det['N_mip'], color=color, lw=1.5,
                    label=f'{det["label"]} — {plane_label} bipolar  '
                          f'[zc={zc_local:+.2f} µs]')
            ax.plot(t_plot + shift_W, det['kW'] * det['N_mip'],
                    color=color, lw=1.5, ls='--',
                    label=f'{det["label"]} — W (shifted {shift_W:+.2f} µs)')

        if ref_top is not None or ref_bot is not None:
            ax.plot([], [], color='gray', lw=4, alpha=0.35, label='thick band = rebuilt from FR')
        ax.axhline(0, color='gray', lw=0.5, ls=':')
        ax.set_xlim(PLOT_XLIM)
        ax.set_ylabel('ADC (×N_MIP)')
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_title(f'{plane_label} plane: PDVD top vs bottom (positive ROI)',
                     fontsize=9)

    axes[-1].set_xlabel('time (µs, relative to each detector\'s V-plane zero crossing)')
    overlay_note = '  [thick band = rebuilt from FR]' if (ref_top or ref_bot) else ''
    fig.suptitle('PDVD L1SP kernel comparison: top CRP (JsonElec) vs bottom CRP (cold)'
                 + overlay_note, fontsize=11)
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  → {outpath}')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--top-file', default='pdvd_top_l1sp_kernels.json.bz2',
                        help='PDVD-top kernel JSON+bz2 (default: '
                             'pdvd_top_l1sp_kernels.json.bz2 via WIRECELL_PATH).')
    parser.add_argument('--bottom-file', default='pdvd_bottom_l1sp_kernels.json.bz2',
                        help='PDVD-bottom kernel JSON+bz2 (default: '
                             'pdvd_bottom_l1sp_kernels.json.bz2 via WIRECELL_PATH).')
    parser.add_argument('--no-rebuild', action='store_true',
                        help='Skip the FR rebuild overlay (faster; just plot the JSON file).')
    args = parser.parse_args()

    print(f'Loading PDVD-top    kernels from {args.top_file}')
    top_kernels = load_l1sp_kernels(args.top_file)
    print(f'Loading PDVD-bottom kernels from {args.bottom_file}')
    bot_kernels = load_l1sp_kernels(args.bottom_file)

    top = _kernels_to_data(top_kernels, 'PDVD top')
    bot = _kernels_to_data(bot_kernels, 'PDVD bottom')

    report(top)
    report(bot)

    ref_top = ref_bot = None
    if not args.no_rebuild:
        print('\nRebuilding PDVD top    kernels from FR + electronics...')
        ref_top = _kernels_to_data(_rebuild_from_fr('pdvd-top'),    'PDVD top (FR rebuild)')
        print('Rebuilding PDVD bottom kernels from FR + electronics...')
        ref_bot = _kernels_to_data(_rebuild_from_fr('pdvd-bottom'), 'PDVD bottom (FR rebuild)')

    print()
    plot_pdvd_plane(top, 0, os.path.join(WORKDIR, 'track_response_l1sp_pdvd_top_U.png'),    ref_data=ref_top)
    plot_pdvd_plane(top, 1, os.path.join(WORKDIR, 'track_response_l1sp_pdvd_top_V.png'),    ref_data=ref_top)
    plot_pdvd_plane(bot, 0, os.path.join(WORKDIR, 'track_response_l1sp_pdvd_bottom_U.png'), ref_data=ref_bot)
    plot_pdvd_plane(bot, 1, os.path.join(WORKDIR, 'track_response_l1sp_pdvd_bottom_V.png'), ref_data=ref_bot)
    plot_compare(top, bot, os.path.join(WORKDIR, 'track_response_l1sp_pdvd_compare.png'),
                 ref_top=ref_top, ref_bot=ref_bot)

    print('\nDone.')


if __name__ == '__main__':
    main()
