#!/usr/bin/env python3
"""
L1SPFilterPD response kernel assembly and validation.

Two modes:

  default (no args):  build kernels in-memory via
      ``wirecell.sigproc.l1sp.build_l1sp_kernels`` for both uBooNE and
      PDHD, plot, and round-trip-check by also writing/reading a temp
      JSON file.

  --from-file <path>: load a kernel JSON+bz2 produced by
      ``wirecell-sigproc gen-l1sp-kernels`` and plot from it.  Re-builds
      from FR for the cross-check unless --no-rebuild is passed.

The kernel-build logic lives in wirecell.sigproc.l1sp; this script only
reshapes the result for plotting and produces three PNGs:

  track_response_l1sp_uboone.png  — uBooNE U/V reference panel.
  track_response_l1sp_pdhd_U.png  — PDHD U plane: positive/negative.
  track_response_l1sp_pdhd_V.png  — PDHD V plane: positive/negative.
"""

import argparse
import os
import tempfile

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from wirecell import units
from wirecell.sigproc.l1sp import (
    build_l1sp_kernels, save_l1sp_kernels, load_l1sp_kernels, negative_half,
)

WORKDIR = os.path.dirname(os.path.abspath(__file__))

# FE/ADC calibration is detector-specific.  postgain/adc_per_mv MUST match
# the values used to generate the kernel JSON file (and used at runtime by
# L1SPFilterPD via cfg/.../sp.jsonnet); otherwise the --from-file rebuild
# cross-check below is meaningless.  See pdhd params.jsonnet (resolution=14,
# fullscale=[0.2V,1.6V] → adc_per_mv = 16384/1400 ≈ 11.702; postgain=1.0).
GAIN_MV_PER_FC   = 14.0
SHAPING_US       = 2.2
COARSE_TOFF_US   = -8.0
FINE_TOFF_US     =  0.0

UB = dict(
    fr_file    = 'ub-10-half.json.bz2',
    pitch_cm   = 0.300,
    label      = 'uBooNE',
    postgain   = 1.2,
    adc_per_mv = 4096 / 2000.0,          # 2.048  (12-bit, 2V fullscale)
)
PD = dict(
    # APA1/2/3 baseline (APA0 is anomalous on V — see params.jsonnet:156-161).
    fr_file    = 'dune-garfield-1d565.json.bz2',
    pitch_cm   = 0.471,
    label      = 'PDHD (APA1/2/3 baseline)',
    postgain   = 1.0,
    adc_per_mv = 16384 / 1400.0,         # 11.703 (14-bit, 1.4V fullscale)
)
PLOT_XLIM = (-8, 10)


def _n_mip(pitch_cm):
    """MIP electrons per wire pitch (1.8 MeV/cm, 70% recombination, 23.6 eV/pair)."""
    return (1.8e6 * pitch_cm * 0.7) / 23.6


def _kernels_to_data(kdict, det):
    """Reshape an l1sp.build_l1sp_kernels / load_l1sp_kernels dict into
    {kU, kV, kW, t_us, N_mip, meta} for plotting."""
    meta = kdict['meta']
    n = meta['n_samples']
    t_us = meta['t0_us'] + np.arange(n) * (meta['period_ns'] / 1000.0)

    by_idx = {p['plane_index']: p for p in kdict['planes']}
    kU = np.asarray(by_idx[0]['positive']['bipolar'])
    kV = np.asarray(by_idx[1]['positive']['bipolar'])
    # W kernel is identical in U and V positive blocks; take from U.
    kW = np.asarray(by_idx[0]['positive']['unipolar'])

    return dict(kU=kU, kV=kV, kW=kW, t_us=t_us,
                N_mip=_n_mip(det['pitch_cm']),
                meta=meta, planes=by_idx)


def build_for_detector(det):
    return build_l1sp_kernels(
        fr_file               = det['fr_file'],
        gain                  = GAIN_MV_PER_FC * units.mV / units.fC,
        shaping               = SHAPING_US * units.us,
        postgain              = det['postgain'],
        adc_per_mv            = det['adc_per_mv'],
        coarse_time_offset_us = COARSE_TOFF_US,
        fine_time_offset_us   = FINE_TOFF_US,
    )


def report(label, data):
    """Print zero-crossings, peaks, implied W shifts."""
    print(f'\n── {label} ──────────────────────────────────────────────')
    m = data['meta']
    print(f'  fr_file = {m["fr_file"]}')
    print(f'  period={m["period_ns"]:.4f} ns  t0={m["t0_us"]:+.4f} µs  n={m["n_samples"]}')
    Nm = data['N_mip']
    print(f'  N_MIP/pitch = {Nm:.1f} e⁻')
    for label_p, k in (('U', data['kU']), ('V', data['kV']), ('W', data['kW'])):
        peak = float(np.max(np.abs(k)))
        print(f'  {label_p}: |peak|={peak:.4g} ADC/e  →  ×N_MIP={peak * Nm:.2f} ADC')
    for plane_idx, plane_label in ((0, 'U'), (1, 'V')):
        p = data['planes'][plane_idx]
        print(f'  {plane_label}: zero-crossing={p["zero_crossing_us"]:+.3f} µs  '
              f'W shift (positive case)={p["positive"]["unipolar_time_offset_us"]:+.3f} µs')


# ── plotting ───────────────────────────────────────────────────────────────────

def _add_kernel_pair(ax, t_us, k_bipolar, k_unipolar, k_neg, N_mip, shift_us,
                     bipolar_label, unipolar_label, neg_label):
    ax.plot(t_us, k_bipolar * N_mip,
            color='steelblue', lw=1.5, label=bipolar_label)
    ax.plot(t_us + shift_us, k_unipolar * N_mip,
            color='darkorange', lw=1.5, label=unipolar_label)
    ax.plot(t_us, k_neg * N_mip,
            color='forestgreen', lw=1.5, ls='--', label=neg_label)
    ax.axhline(0, color='gray', lw=0.5, ls=':')
    ax.set_xlim(PLOT_XLIM)
    ax.set_ylabel('ADC (×N_MIP)')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)


def plot_uboone(data, outpath):
    """uBooNE reference panel.  Single per-detector offset (V zero-crossing);
    W shift inside the L1 fit is V-driven (single scalar in legacy uBooNE)."""
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    fig.subplots_adjust(hspace=0.08)

    t  = data['t_us']
    Nm = data['N_mip']
    t_zc_V       = data['planes'][1]['zero_crossing_us']
    shift_W_glob = data['planes'][1]['positive']['unipolar_time_offset_us']
    t_plot       = t - t_zc_V

    for ax, k_bip, plane_idx, label in (
        (axes[0], data['kU'], 0, 'U'),
        (axes[1], data['kV'], 1, 'V'),
    ):
        zc_local   = data['planes'][plane_idx]['zero_crossing_us']
        zc_in_plot = zc_local - t_zc_V
        _add_kernel_pair(
            ax, t_plot, k_bip, data['kW'], negative_half(k_bip), Nm, shift_W_glob,
            bipolar_label  = f'{label}-plane bipolar (×{Nm:.0f} e⁻/pitch)  '
                             f'[zero-crossing at {zc_in_plot:+.2f} µs]',
            unipolar_label = f'W-plane unipolar  '
                             f'(global shift {shift_W_glob:+.2f} µs, set by V-zero-crossing)',
            neg_label      = f'neg-half({label}) — anode-induction unipolar',
        )
        ax.set_title(f'uBooNE — {label} plane', fontsize=9)

    axes[-1].set_xlabel('time (µs, relative to V-plane zero crossing)')
    fig.suptitle(f'uBooNE L1SPFilter response bases  '
                 f'(V-zero-crossing @ {t_zc_V:+.2f} µs)', fontsize=12)
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  → {outpath}')


def plot_pdhd_plane(data, plane_idx, outpath, ref_data=None):
    """PDHD positive (top) + negative (bottom).  t-axis offset = V zero
    crossing (shared across U/V).  W shift is per-plane: W peak lands at
    each plane's own bipolar zero crossing.

    If ref_data is provided (e.g. the in-memory FR rebuild), its curves are
    drawn as thin dashed lines underneath the main curves so the two sources
    can be visually compared."""
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
        r_bip = ref_data['kU'] if plane_idx == 0 else ref_data['kV']
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
    ax.set_xlim(PLOT_XLIM)
    ax.set_ylabel('ADC (×N_MIP)')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_title(f'PDHD — {plane_label} plane, positive ROI '
                 f'(collection-on-induction)', fontsize=9)

    # negative case
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
    ax.set_title(f'PDHD — {plane_label} plane, negative ROI '
                 f'(anode-induction)', fontsize=9)

    axes[-1].set_xlabel('time (µs, relative to V-plane zero crossing)')
    overlay_note = '  [thick band = rebuilt from FR; thin line = from file — bit-identical]' \
                   if ref_data is not None else ''
    fig.suptitle(f'PDHD L1SPFilterPD — {plane_label} plane  '
                 f'(N_MIP/pitch={Nm:.0f} e⁻;  V-zero-crossing @ {t_zc_V:+.2f} µs)'
                 f'{overlay_note}',
                 fontsize=10)
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  → {outpath}')


def assert_kernels_equal(a, b, label):
    """Verify two kernel dicts are bit-identical for the array fields."""
    assert a['meta']['n_samples'] == b['meta']['n_samples'], f'{label}: n_samples'
    by_a = {p['plane_index']: p for p in a['planes']}
    by_b = {p['plane_index']: p for p in b['planes']}
    assert set(by_a) == set(by_b), f'{label}: plane indices'
    for idx in by_a:
        for case in ('positive', 'negative'):
            for arr in ('bipolar', 'unipolar'):
                aa = np.asarray(by_a[idx][case][arr])
                bb = np.asarray(by_b[idx][case][arr])
                if not np.array_equal(aa, bb):
                    raise AssertionError(
                        f'{label}: plane {idx} {case}.{arr} differs '
                        f'(max |Δ| = {np.max(np.abs(aa - bb)):.3e})')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from-file', metavar='PATH',
                        help='Load a PDHD kernel JSON+bz2 file produced by '
                             'wirecell-sigproc gen-l1sp-kernels and plot from it.')
    parser.add_argument('--no-rebuild', action='store_true',
                        help='With --from-file, skip the in-memory rebuild '
                             'cross-check (saves time).')
    args = parser.parse_args()

    # ── PDHD ──────────────────────────────────────────────────────────────────
    if args.from_file:
        print(f'Loading PDHD kernels from {args.from_file}')
        pd_kernels = load_l1sp_kernels(args.from_file)
        if not args.no_rebuild:
            print('Cross-check: rebuilding from FR + electronics...')
            ref = build_for_detector(PD)
            assert_kernels_equal(pd_kernels, ref, label='PDHD --from-file vs rebuild')
            print('  ✓ file is bit-identical to FR rebuild')
    else:
        pd_kernels = build_for_detector(PD)
        # Round-trip check via temp JSON.
        with tempfile.NamedTemporaryFile(suffix='.json.bz2', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            save_l1sp_kernels(pd_kernels, tmp_path)
            roundtrip = load_l1sp_kernels(tmp_path)
            assert_kernels_equal(pd_kernels, roundtrip, label='PDHD round-trip')
            print(f'PDHD round-trip via {tmp_path}: ✓ bit-identical')
        finally:
            os.unlink(tmp_path)

    pd = _kernels_to_data(pd_kernels, PD)
    report(PD['label'], pd)

    # ref_pd: the in-memory FR rebuild, passed to plot functions for visual overlay.
    # Only available when --from-file + rebuild; None otherwise (no overlay shown).
    ref_pd = _kernels_to_data(ref, PD) if (args.from_file and not args.no_rebuild) else None

    plot_pdhd_plane(pd, 0, os.path.join(WORKDIR, 'track_response_l1sp_pdhd_U.png'), ref_data=ref_pd)
    plot_pdhd_plane(pd, 1, os.path.join(WORKDIR, 'track_response_l1sp_pdhd_V.png'), ref_data=ref_pd)

    # ── uBooNE reference (always rebuilt from FR; legacy detector, no JSON file) ──
    ub_kernels = build_for_detector(UB)
    ub = _kernels_to_data(ub_kernels, UB)
    report(UB['label'], ub)
    plot_uboone(ub, os.path.join(WORKDIR, 'track_response_l1sp_uboone.png'))

    print('\nDone.')


if __name__ == '__main__':
    main()
