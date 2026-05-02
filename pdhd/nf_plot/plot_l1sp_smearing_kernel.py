#!/usr/bin/env python3
"""
Validate the L1SPFilterPD auto-derived smearing kernel.

Two panels:
  1. MicroBooNE: IFFT-derived kernel vs. hardcoded 21-tap JSON array
     (should be bit-identical to ~1e-4 level)
  2. PDHD: IFFT-derived kernel (sigma=0.12 MHz, tick=500 ns)

Note: SP runs at 500 ns tick on PDHD (post-resampler from 512 ns native).
HfFilter Gaus_wide is configured with max_freq=1 MHz, so the IFFT bin
spacing is 1/(2·max_freq) = 500 ns by construction.

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

# ── hardcoded uBooNE JSON array (cfg/pgrapher/experiment/uboone/sp.jsonnet) ──
UBOONE_FILTER = np.array([
    0.000305453, 0.000978027, 0.00277049, 0.00694322, 0.0153945,
    0.0301973,   0.0524048,   0.0804588,  0.109289,   0.131334,
    0.139629,
    0.131334,    0.109289,    0.0804588,  0.0524048,  0.0301973,
    0.0153945,   0.00694322,  0.00277049, 0.000978027, 0.000305453,
])


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show', action='store_true',
                        help='show interactive window instead of saving')
    parser.add_argument('-o', '--output', default=None,
                        help='output PNG path (default: next to this script)')
    args = parser.parse_args()

    if not args.show:
        matplotlib.use('Agg')

    # ── derive uBooNE kernel ──────────────────────────────────────────────────
    ub_sigma_hz = 1.11408e-01 * 1e6    # 0.111408 MHz
    ub_tick_us  = 0.5                   # 500 ns
    ub_ticks, ub_kernel = derive_kernel(ub_sigma_hz, ub_tick_us)

    # hardcoded array ticks: ±10 ticks centred at 0
    n_ub = len(UBOONE_FILTER)
    ub_json_ticks = (np.arange(n_ub) - (n_ub - 1) / 2) * ub_tick_us

    # ── derive PDHD kernel ────────────────────────────────────────────────────
    pd_sigma_hz = 0.12 * 1e6           # 0.12 MHz
    pd_tick_us  = 0.5                   # 500 ns (post-resampler SP tick)
    pd_ticks, pd_kernel = derive_kernel(pd_sigma_hz, pd_tick_us)

    # ── residuals for panel 1 ─────────────────────────────────────────────────
    # Interpolate IFFT result onto the JSON ticks for a direct residual plot.
    ub_kernel_at_json = np.interp(ub_json_ticks, ub_ticks, ub_kernel)
    residual = ub_kernel_at_json - UBOONE_FILTER

    # ── plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(13, 8),
                             gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.05,
                                          'wspace': 0.30})
    ax_ub, ax_pd   = axes[0]
    ax_res, ax_ann = axes[1]

    # ── panel 1a: uBooNE comparison ──────────────────────────────────────────
    ax_ub.plot(ub_ticks, ub_kernel, 'b-o', ms=4, lw=1.5,
               label=f'IFFT-derived  (σ={ub_sigma_hz/1e6:.5f} MHz, N=4096)')
    ax_ub.plot(ub_json_ticks, UBOONE_FILTER, 'r--s', ms=5, lw=1.5,
               label='Hardcoded 21-tap JSON array')
    ax_ub.set_title('MicroBooNE smearing kernel', fontsize=11)
    ax_ub.set_ylabel('Kernel amplitude (sum=1)')
    ax_ub.legend(fontsize=8)
    ax_ub.set_xlim(-7, 7)
    ax_ub.grid(True, alpha=0.3)
    ax_ub.tick_params(labelbottom=False)

    # ── panel 1b: residual ────────────────────────────────────────────────────
    ax_res.bar(ub_json_ticks, residual, width=0.35, color='steelblue', alpha=0.7)
    ax_res.axhline(0, color='k', lw=0.8)
    ax_res.set_ylabel('IFFT − JSON', fontsize=8)
    ax_res.set_xlabel('Time (µs)')
    ax_res.set_xlim(-7, 7)
    ax_res.set_ylim(-2e-4, 2e-4)
    ax_res.yaxis.set_major_formatter(plt.FormatStrFormatter('%.0e'))
    ax_res.grid(True, alpha=0.3)
    max_res = np.max(np.abs(residual))
    ax_res.text(0.98, 0.85, f'max |Δ| = {max_res:.2e}',
                transform=ax_res.transAxes, ha='right', va='top', fontsize=8)

    # ── panel 2: PDHD ─────────────────────────────────────────────────────────
    # Reference curve: continuous Gaussian sampled at tick Δt, normalised so
    # that the discrete samples sum to 1 (same convention as the IFFT kernel).
    #   ref(t) = (Δt / (σ_t · √(2π))) · exp(-½ (t/σ_t)²)
    # The histogram bars should sit on this curve at every integer tick.
    sigma_t_us = 1.0 / (2 * np.pi * pd_sigma_hz) * 1e6   # µs
    t_cont = np.linspace(pd_ticks[0] - 0.2, pd_ticks[-1] + 0.2, 500)
    g_cont = (pd_tick_us / (sigma_t_us * np.sqrt(2 * np.pi))) \
             * np.exp(-0.5 * (t_cont / sigma_t_us) ** 2)

    ax_pd.bar(pd_ticks, pd_kernel, width=pd_tick_us * 0.85,
              color='darkorange', alpha=0.7, label='IFFT-derived kernel (sum-normalised)')
    ax_pd.plot(t_cont, g_cont, 'k--', lw=1.2,
               label=f'Analytic Gaussian  (σ_t = {sigma_t_us:.3f} µs, same norm)')
    ax_pd.set_title(
        f'PDHD smearing kernel  (σ = {pd_sigma_hz/1e6:.3f} MHz, tick = {pd_tick_us*1e3:.0f} ns, '
        f'ntaps = {len(pd_kernel)})',
        fontsize=11)
    ax_pd.set_ylabel('Kernel amplitude (sum=1)')
    ax_pd.set_xlabel('Time (µs)')
    ax_pd.legend(fontsize=8)
    ax_pd.grid(True, alpha=0.3)
    ax_pd.text(0.98, 0.85,
               f'n_half = {(len(pd_kernel)-1)//2} ticks\n'
               f'σ_t = {sigma_t_us:.3f} µs\n'
               f'peak = {pd_kernel.max():.5f}',
               transform=ax_pd.transAxes, ha='right', va='top', fontsize=8,
               bbox=dict(boxstyle='round', fc='white', alpha=0.7))

    # ── annotation panel (bottom-right) ───────────────────────────────────────
    ax_ann.axis('off')
    info = (
        'Algorithm (L1SPFilterPD):\n'
        '  1. Build HfFilter spectrum: H[k] = exp(−½(|f_k|/σ)²), H[0]=0\n'
        '  2. IFFT (1/N normalisation) → h[n], peak at n=0\n'
        '  3. Scan outward until |h[k]| < 1e-3 · h[0] → n_half\n'
        '  4. Centre: kernel[i] = h[(i+N) % N], i ∈ [−n_half, n_half]\n'
        '  5. Normalise: kernel /= Σkernel\n\n'
        f'uBooNE:  σ = {ub_sigma_hz/1e6:.5f} MHz  tick = {ub_tick_us*1e3:.0f} ns  '
        f'ntaps = {len(ub_kernel)}\n'
        f'PDHD:    σ = {pd_sigma_hz/1e6:.4f} MHz  tick = {pd_tick_us*1e3:.0f} ns  '
        f'ntaps = {len(pd_kernel)}'
    )
    ax_ann.text(0.03, 0.97, info, transform=ax_ann.transAxes,
                va='top', ha='left', fontsize=8.5,
                family='monospace',
                bbox=dict(boxstyle='round', fc='lightyellow', ec='gray', alpha=0.9))

    fig.suptitle('L1SPFilterPD smearing kernel validation', fontsize=13, y=1.01)
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
