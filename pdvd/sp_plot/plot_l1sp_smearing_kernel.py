#!/usr/bin/env python3
"""
Validate the L1SPFilterPD auto-derived smearing kernel for PDVD.

Two kernel panels (Bottom and Top electronics) against an analytic Gaussian
reference, plus a residual panel showing the Top-minus-Bottom difference.

PDVD has two separate sets of HfFilter instances for the smearing kernel:
  HfFilter:Gaus_wide_b  — Bottom anodes (ident 0..3)
  HfFilter:Gaus_wide_t  — Top    anodes (ident 4..7)
Selected in cfg/pgrapher/experiment/protodunevd/sp.jsonnet:24,151 via sfx.
Parameters are currently identical but are kept separate so they can diverge.

Usage:
    python plot_l1sp_smearing_kernel.py            # saves PNG next to this file
    python plot_l1sp_smearing_kernel.py --show     # interactive window
    python plot_l1sp_smearing_kernel.py -o /path/to/out.png
"""

import argparse
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


def hf_spectrum(N, sigma_hz, max_freq_hz=1e6, power=2, flag=True):
    """Reproduce HfFilter::filter_waveform(N) in Python.

    Returns a real array of length N: freq-domain Gaussian spectrum.
    Bin spacing = 2*max_freq / N; DC bin zeroed when flag=True.
    """
    wf = np.zeros(N)
    for i in range(N):
        freq = i / N * 2 * max_freq_hz
        if freq > max_freq_hz:
            freq -= 2 * max_freq_hz
        freq = abs(freq)
        if flag and freq == 0:
            wf[i] = 0.0
        else:
            wf[i] = np.exp(-0.5 * (freq / sigma_hz) ** power)
    return wf


def derive_kernel(sigma_hz, tick_us, N=4096, threshold=1e-3, max_half=64,
                  max_freq_hz=1e6, power=2):
    """Derive the L1SP smearing kernel using the same algorithm as L1SPFilterPD.

    Returns (ticks, kernel) where ticks are centred on 0 in microseconds.
    """
    spec = hf_spectrum(N, sigma_hz, max_freq_hz, power, flag=True)
    # IFFT (1/N normalization) → peak at index 0, negative-time wraps to N-1..
    time_wf = np.fft.ifft(spec).real

    peak = abs(time_wf[0])
    thr = threshold * peak
    n_half = 0
    for k in range(1, max_half + 1):
        if abs(time_wf[k]) < thr and abs(time_wf[N - k]) < thr:
            break
        n_half = k

    indices = np.arange(-n_half, n_half + 1)
    kernel = time_wf[(indices + N) % N]

    s = kernel.sum()
    if s > 0:
        kernel /= s

    ticks_us = indices * tick_us
    return ticks_us, kernel


def _analytic_gauss(ticks_us, sigma_hz, tick_us):
    """Continuous Gaussian sampled at ticks, normalised so discrete sum = 1."""
    sigma_t_us = 1.0 / (2 * np.pi * sigma_hz) * 1e6
    t_cont = np.linspace(ticks_us[0] - 0.2, ticks_us[-1] + 0.2, 500)
    g_cont = (tick_us / (sigma_t_us * np.sqrt(2 * np.pi))) \
             * np.exp(-0.5 * (t_cont / sigma_t_us) ** 2)
    return t_cont, g_cont, sigma_t_us


def _draw_kernel_panel(ax, ticks_us, kernel, sigma_hz, tick_us, label):
    """Draw kernel bars + analytic Gaussian on ax."""
    t_cont, g_cont, sigma_t_us = _analytic_gauss(ticks_us, sigma_hz, tick_us)
    n_half = (len(kernel) - 1) // 2

    ax.bar(ticks_us, kernel, width=tick_us * 0.85,
           color='darkorange', alpha=0.7,
           label='IFFT-derived kernel (sum-normalised)')
    ax.plot(t_cont, g_cont, 'k--', lw=1.2,
            label=f'Analytic Gaussian  (σ_t = {sigma_t_us:.3f} µs)')
    ax.set_title(
        f'PDVD {label} smearing kernel  '
        f'(σ = {sigma_hz/1e6:.3f} MHz, tick = {tick_us*1e3:.0f} ns, '
        f'ntaps = {len(kernel)})',
        fontsize=11)
    ax.set_ylabel('Kernel amplitude (sum=1)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.text(0.98, 0.85,
            f'n_half = {n_half} ticks\n'
            f'σ_t = {sigma_t_us:.3f} µs\n'
            f'peak = {kernel.max():.5f}',
            transform=ax.transAxes, ha='right', va='top', fontsize=8,
            bbox=dict(boxstyle='round', fc='white', alpha=0.7))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show', action='store_true',
                        help='show interactive window instead of saving')
    parser.add_argument('-o', '--output', default=None,
                        help='output PNG path (default: next to this script)')
    args = parser.parse_args()

    if not args.show:
        matplotlib.use('Agg')

    # ── filter parameters ─────────────────────────────────────────────────────
    # Source: cfg/pgrapher/experiment/protodunevd/sp-filters.jsonnet:94-95
    # anode ident 0..3 = Bottom (_b), ident 4..7 = Top (_t); sp.jsonnet:24,151
    bot_sigma_hz = 0.12 * 1e6   # Gaus_wide_b
    top_sigma_hz = 0.12 * 1e6   # Gaus_wide_t
    tick_us      = 0.5          # post-resampler SP tick (params.jsonnet:96-97)
    max_freq_hz  = 1e6          # hf() default in sp-filters.jsonnet
    power        = 2            # hf() default

    # ── derive kernels ────────────────────────────────────────────────────────
    bot_ticks, bot_kernel = derive_kernel(bot_sigma_hz, tick_us,
                                          max_freq_hz=max_freq_hz, power=power)
    top_ticks, top_kernel = derive_kernel(top_sigma_hz, tick_us,
                                          max_freq_hz=max_freq_hz, power=power)

    # ── residual on a common tick grid ────────────────────────────────────────
    all_ticks = np.union1d(bot_ticks, top_ticks)
    bot_interp = np.interp(all_ticks, bot_ticks, bot_kernel, left=0.0, right=0.0)
    top_interp = np.interp(all_ticks, top_ticks, top_kernel, left=0.0, right=0.0)
    residual = top_interp - bot_interp

    # ── plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(13, 8),
                             gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.05,
                                          'wspace': 0.30})
    ax_bot, ax_top = axes[0]
    ax_res, ax_ann = axes[1]

    _draw_kernel_panel(ax_bot, bot_ticks, bot_kernel, bot_sigma_hz, tick_us,
                       'Bottom (_b)')
    ax_bot.set_xlabel('Time (µs)')

    _draw_kernel_panel(ax_top, top_ticks, top_kernel, top_sigma_hz, tick_us,
                       'Top (_t)')
    ax_top.set_xlabel('Time (µs)')

    # ── residual panel ────────────────────────────────────────────────────────
    ax_res.bar(all_ticks, residual, width=tick_us * 0.85,
               color='steelblue', alpha=0.7)
    ax_res.axhline(0, color='k', lw=0.8)
    ax_res.set_ylabel('Top − Bottom', fontsize=8)
    ax_res.set_xlabel('Time (µs)')
    max_res = np.max(np.abs(residual))
    ax_res.yaxis.set_major_formatter(plt.FormatStrFormatter('%.0e'))
    ax_res.grid(True, alpha=0.3)
    ax_res.text(0.98, 0.85, f'max |Δ| = {max_res:.2e}',
                transform=ax_res.transAxes, ha='right', va='top', fontsize=8)

    # ── annotation panel ──────────────────────────────────────────────────────
    ax_ann.axis('off')
    info = (
        'Algorithm (L1SPFilterPD):\n'
        '  1. Build HfFilter spectrum: H[k] = exp(−½(|f_k|/σ)²), H[0]=0\n'
        '  2. IFFT (1/N normalisation) → h[n], peak at n=0\n'
        '  3. Scan outward until |h[k]| < 1e-3 · h[0] → n_half\n'
        '  4. Centre: kernel[i] = h[(i+N) % N], i ∈ [−n_half, n_half]\n'
        '  5. Normalise: kernel /= Σkernel\n\n'
        f'Bottom (_b):  σ = {bot_sigma_hz/1e6:.4f} MHz  '
        f'tick = {tick_us*1e3:.0f} ns  ntaps = {len(bot_kernel)}\n'
        f'Top    (_t):  σ = {top_sigma_hz/1e6:.4f} MHz  '
        f'tick = {tick_us*1e3:.0f} ns  ntaps = {len(top_kernel)}\n\n'
        'Source: cfg/.../protodunevd/sp-filters.jsonnet:94-95'
    )
    ax_ann.text(0.03, 0.97, info, transform=ax_ann.transAxes,
                va='top', ha='left', fontsize=8.5,
                family='monospace',
                bbox=dict(boxstyle='round', fc='lightyellow', ec='gray', alpha=0.9))

    fig.suptitle('PDVD L1SPFilterPD smearing kernel validation (Top vs Bottom)',
                 fontsize=13, y=1.01)
    plt.tight_layout()

    if args.show:
        plt.show()
    else:
        outpath = args.output or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'l1sp_smearing_kernel_validation.png')
        fig.savefig(outpath, dpi=150, bbox_inches='tight')
        print(f'Saved to {outpath}')


if __name__ == '__main__':
    main()
