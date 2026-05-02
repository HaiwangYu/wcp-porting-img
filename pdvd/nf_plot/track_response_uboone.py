#!/usr/bin/env python3
"""
MicroBooNE FR ⊗ ER perpendicular-line track response, full window, per plane.

Uses `ub-10-half.json.bz2` (schema format, resolved via WIRECELL_PATH).
Line-source averaging uses per-region symmetrize + non-uniform trapezoidal
(Option B): for each integer wire region the one-sided impacts in the file
are mirrored about the wire centre, then integrated with trapezoidal weights
(endpoints 0.5, interior 1.0), and the per-region integrals are summed and
divided by plane.pitch.

Outputs (same directory as this script):
  track_response_uboone_U.png
  track_response_uboone_V.png

Each PNG: top = ADC waveform vs time (with chndb-resp overlay), bottom = |FFT| spectrum.

Scaling chain (per coherent_nf_params_comparison.md §2–3):
  fr_line [e/ns/electron, WC units]
    ⊗ er        — at native FR period (100 ns)
    × period_ns — dt factor (discrete convolution → integral)
    × N_MIP     — MIP electrons per wire pitch
    / units.mV  — WC-internal voltage → real mV
    × POSTGAIN  — uBooNE postgain = 1.2
    × ADC_PER_MV— uBooNE 12-bit 0–2 V → 2.048 ADC/mV
    → resample from 100 ns to 500 ns (ADC tick) via FFT resampling
    = ADC at 0.5 µs/tick
"""

import os, re
import numpy as np
from scipy.signal import resample as sp_resample
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from wirecell.sigproc.response import persist
from wirecell.sigproc import response as wc_resp
from wirecell import units
from wirecell.util.fileio import wirecell_path

WORKDIR = os.path.dirname(os.path.abspath(__file__))
FR_FILE = 'ub-10-half.json.bz2'

CHNDB_RESP_FILE = ('/nfs/data/1/xqian/toolkit-dev/toolkit/cfg/pgrapher'
                   '/experiment/uboone/chndb-resp.jsonnet')
CHNDB_TICK_US = 0.5   # 500 ns per sample

ADC_TICK_NS = 500.0   # digitize at 0.5 µs

# uBooNE FE electronics (coherent_nf_params_comparison.md §2)
GAIN        = 14.0 * units.mV / units.fC
SHAPING     = 2.2  * units.us
POSTGAIN    = 1.2

# uBooNE ADC: 12-bit, 0–2 V fullscale → 2.048 ADC/mV
# (coherent_nf_params_comparison.md §3)
ADC_PER_MV  = 2.048

# MIP electrons per wire pitch (uBooNE pitch = 3 mm = 0.3 cm):
#   1.8 MeV/cm × 0.3 cm × 0.7 (recombination) / 23.6 eV per ion pair
N_MIP_PER_PITCH = (1.8e6 * 0.3 * 0.7) / 23.6   # ≈ 16017 e-

# L1SPFilter (uBooNE) default time offsets — from L1SPFilter.h default params
L1SP_COARSE_TIME_OFFSET_US  = -8.0   # m_coarse_time_offset
L1SP_FINE_TIME_OFFSET_US    =  0.0   # m_fine_time_offset
L1SP_COLLECT_TIME_OFFSET_US = +3.0   # collect_time_offset (W-basis arg shift in L1_fit)

# ---------------------------------------------------------------------------

def l1sp_response(fr_line, er, period_ns):
    """Reproduce L1SPFilter::init_resp() for one plane.

    Returns the kernel sampled at period_ns (ADC per single electron),
    matching lin_V / lin_W before the x250 conditioning inside L1_fit.
    Uses circular FFT — same as the C++ FFT helper.
    """
    ewave = -1.0 * POSTGAIN * (ADC_PER_MV / units.mV) * er
    S = np.fft.rfft(fr_line) * np.fft.rfft(ewave) * period_ns
    return np.fft.irfft(S, n=len(fr_line))


def parse_chndb_resp(path):
    """Extract u_resp and v_resp float arrays from chndb-resp.jsonnet."""
    with open(path) as fh:
        text = fh.read()
    result = {}
    for key in ('u_resp', 'v_resp'):
        m = re.search(r'\b' + key + r'\b\s*:\s*\[([^\]]*)\]', text, re.DOTALL)
        if not m:
            raise ValueError(f'Cannot find {key} in {path}')
        nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', m.group(1))
        result[key] = np.array([float(x) for x in nums])
    return result


def line_source_response(plane):
    """
    Perpendicular-line-source response on the central wire.

    L(t) = (1/pitch) × ∫ I(t;X) dX, approximated per-region:
      for each integer wire region r = round(pitchpos/pitch):
        local offset ξ = pitchpos − r·pitch
        mirror about ξ=0: for ξ_i ≠ 0 missing −ξ_i, add −ξ_i with same I
        non-uniform trapezoidal weights: w_0=(ξ_1−ξ_0)/2,
            w_i=(ξ_{i+1}−ξ_{i−1})/2, w_N=(ξ_N−ξ_{N−1})/2
        region contribution: Σ_i w_i × I(ξ_i)
      sum across regions, divide by pitch.
    """
    from collections import defaultdict
    pitch = plane.pitch
    N = len(plane.paths[0].current)

    by_r = defaultdict(list)
    for path in plane.paths:
        r  = int(round(path.pitchpos / pitch))
        xi = path.pitchpos - r * pitch
        by_r[r].append((xi, np.asarray(path.current, dtype=float)))

    integral = np.zeros(N)
    for items in by_r.values():
        sym = {xi: I for xi, I in items}
        for xi in list(sym):
            if abs(xi) > 1e-9 and (-xi) not in sym:
                sym[-xi] = sym[xi]
        xis = sorted(sym)
        n = len(xis)
        w = np.empty(n)
        w[0]  = (xis[1] - xis[0]) / 2.0
        w[-1] = (xis[-1] - xis[-2]) / 2.0
        for i in range(1, n - 1):
            w[i] = (xis[i + 1] - xis[i - 1]) / 2.0
        for xi, wi in zip(xis, w):
            integral += wi * sym[xi]

    return integral / pitch


def make_plot(wave_adc, chndb_ref, tick_us, plane_label, outpath,
              resp_l1_mip=None, t_l1sp_us=None):
    """Two-panel plot: ADC waveform at 0.5 µs tick (top) + |FFT| (bottom)."""
    N = len(wave_adc)
    t_us      = np.arange(N) * tick_us
    freqs_mhz = np.fft.rfftfreq(N, d=tick_us)   # MHz (d in µs)

    pk_pos = wave_adc[np.argmax(wave_adc)]
    pk_neg = wave_adc[np.argmin(wave_adc)]

    # Align chndb_ref to our waveform at the negative peak.
    i_neg_adc   = int(np.argmin(wave_adc))
    t_neg_us    = t_us[i_neg_adc]
    i_neg_chndb = int(np.argmin(chndb_ref))
    t_chndb     = t_neg_us + (np.arange(len(chndb_ref)) - i_neg_chndb) * CHNDB_TICK_US

    # Scale chndb so its negative peak matches our trough.
    scale       = pk_neg / chndb_ref[i_neg_chndb]
    chndb_scaled = chndb_ref * scale

    params_str = (f'gain={GAIN/(units.mV/units.fC):.1f} mV/fC  '
                  f'shaping={SHAPING/units.us:.1f} µs  '
                  f'postgain={POSTGAIN}  '
                  f'ADC/mV={ADC_PER_MV}  '
                  f'N_MIP≈{N_MIP_PER_PITCH:.0f} e⁻/pitch  '
                  f'tick={tick_us*1000:.0f} ns')

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    ax = axes[0]
    ax.plot(t_us, wave_adc, 'r-', lw=1.5,
            label=f'FR ⊗ ER (digitized at {tick_us*1000:.0f} ns)  [{params_str}]')
    ax.plot(t_chndb, chndb_scaled, 'b--', lw=1.5,
            label=f'chndb-resp.jsonnet  (scaled ×{scale:.3g}, aligned at neg. peak)')
    if resp_l1_mip is not None and t_l1sp_us is not None:
        i_neg_l1 = int(np.argmin(resp_l1_mip))
        t_l1sp_aligned = t_l1sp_us + (t_neg_us - t_l1sp_us[i_neg_l1])
        l1_pk = resp_l1_mip[np.argmax(resp_l1_mip)]
        l1_tr = resp_l1_mip[i_neg_l1]
        ax.plot(t_l1sp_aligned, resp_l1_mip, color='green', lw=1.0, alpha=0.85,
                label=(f'L1SP kernel × N_MIP  (100 ns, trough-aligned)  '
                       f'pk={l1_pk:.1f}  trough={l1_tr:.1f} ADC'))
    ax.axhline(0, color='gray', lw=0.5)
    ax.set_xlabel('time (µs)')
    ax.set_ylabel('ADC')
    ax.set_title(
        f'MicroBooNE  —  plane {plane_label}  —  full window ({N * tick_us:.1f} µs)\n'
        f'FR ⊗ ER  (MIP perpendicular-line track)   '
        f'peak = {pk_pos:.1f} ADC,  trough = {pk_neg:.1f} ADC'
    )
    ax.legend(fontsize=8, loc='upper left')

    ax = axes[1]
    ax.plot(freqs_mhz, np.abs(np.fft.rfft(wave_adc)), 'r-', lw=1.5, label='FR ⊗ ER')
    freqs_chndb = np.fft.rfftfreq(len(chndb_scaled), d=CHNDB_TICK_US)   # MHz
    ax.plot(freqs_chndb, np.abs(np.fft.rfft(chndb_scaled)), 'b--', lw=1.5, label='chndb-resp')
    if resp_l1_mip is not None and t_l1sp_us is not None:
        fine_tick_us = t_l1sp_us[1] - t_l1sp_us[0]
        freqs_l1 = np.fft.rfftfreq(len(resp_l1_mip), d=fine_tick_us)
        ax.plot(freqs_l1, np.abs(np.fft.rfft(resp_l1_mip)), color='green',
                lw=1.0, alpha=0.85, label='L1SP kernel × N_MIP')
    ax.set_xlabel('frequency (MHz)')
    ax.set_ylabel('|FFT| (ADC)')
    ax.set_title('Frequency spectrum')
    ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f'  wrote {outpath}')


def run():
    print(f'Loading {FR_FILE} ...')
    fr = persist.load(FR_FILE, paths=wirecell_path())

    print(f'FR period = {fr.period} ns,  tstart = {fr.tstart}')
    print(f'Planes:')
    for pl in fr.planes:
        print(f'  planeid={pl.planeid}  location={pl.location:.3f}  pitch={pl.pitch:.3f}  npaths={len(pl.paths)}')

    period_ns = fr.period
    N_fr = len(fr.planes[0].paths[0].current)
    times = np.arange(N_fr, dtype=float) * period_ns

    # Electronics impulse at native FR period (100 ns)
    er = np.asarray(wc_resp.electronics(times, peak_gain=GAIN, shaping=SHAPING, elec_type='cold'), dtype=float)
    er_peak_t = times[np.argmax(np.abs(er))] / 1000.0
    print(f'\nElectronics: gain={GAIN/(units.mV/units.fC):.1f} mV/fC  '
          f'shaping={SHAPING/units.us:.1f} µs  postgain={POSTGAIN}')
    print(f'  ER peak at {er_peak_t:.2f} µs,  peak value = {np.max(np.abs(er)):.4g} (WC units)')
    print(f'MIP electrons per pitch: {N_MIP_PER_PITCH:.1f}')
    print(f'ADC/mV = {ADC_PER_MV}  |  ADC tick = {ADC_TICK_NS:.0f} ns')

    # Load chndb reference arrays
    chndb = parse_chndb_resp(CHNDB_RESP_FILE)
    print(f'\nLoaded chndb-resp from {CHNDB_RESP_FILE}')

    # Number of output samples after resampling to ADC_TICK_NS
    total_ns = N_fr * period_ns
    N_adc    = int(round(total_ns / ADC_TICK_NS))
    tick_us  = ADC_TICK_NS / 1000.0
    print(f'Resampling {N_fr} × {period_ns:.0f} ns → {N_adc} × {ADC_TICK_NS:.0f} ns')

    plane_labels = {0: 'U', 1: 'V', 2: 'W'}
    chndb_keys   = {0: 'u_resp', 1: 'v_resp'}

    for pl in fr.planes:
        pid = pl.planeid
        label = plane_labels.get(pid, f'plane{pid}')
        if label == 'W':
            print(f'\nSkipping W plane (planeid={pid})')
            continue

        print(f'\n=== planeid={pid}  ({label}) ===')
        fr_line = line_source_response(pl)

        # Convolve FR with electronics at native 100 ns period
        wave_frer = wc_resp.convolve(fr_line, er)

        # Convert to mV (full-resolution, 100 ns)
        wave_mv = -(wave_frer
                    * period_ns
                    * N_MIP_PER_PITCH
                    / units.mV
                    * POSTGAIN)

        # Resample from 100 ns to ADC tick (500 ns) — anti-aliased via FFT
        wave_mv_resampled = sp_resample(wave_mv, N_adc)

        # Apply ADC gain after resampling
        wave_adc = wave_mv_resampled * ADC_PER_MV

        pk_pos_adc = wave_adc[np.argmax(wave_adc)]
        pk_neg_adc = wave_adc[np.argmin(wave_adc)]
        t_adc = np.arange(N_adc) * tick_us
        t_pos = t_adc[np.argmax(wave_adc)]
        t_neg = t_adc[np.argmin(wave_adc)]
        print(f'  FR⊗ER (ADC @ {ADC_TICK_NS:.0f} ns):  positive peak  {pk_pos_adc:+.2f} ADC  at {t_pos:.2f} µs')
        print(f'                             negative trough {pk_neg_adc:+.2f} ADC  at {t_neg:.2f} µs')

        chndb_ref = chndb[chndb_keys[pid]]
        i_neg_c   = int(np.argmin(chndb_ref))
        scale     = pk_neg_adc / chndb_ref[i_neg_c]
        print(f'  chndb-resp neg peak at sample {i_neg_c}  ({i_neg_c * CHNDB_TICK_US:.1f} µs),  scale = {scale:.4g}')

        # L1SP kernel (ADC/electron at fine period) and numerical verification
        resp_l1     = l1sp_response(fr_line, er, period_ns)
        resp_l1_mip = resp_l1 * N_MIP_PER_PITCH
        wave_adc_fine = wave_mv * ADC_PER_MV
        maxdiff  = np.max(np.abs(resp_l1_mip - wave_adc_fine))
        allclose = np.allclose(resp_l1_mip, wave_adc_fine, atol=1.0)
        print(f'  L1SP kernel vs fine-period FR⊗ER: allclose(atol=1)={allclose}'
              f'  max_abs_diff={maxdiff:.3e} ADC')

        # Time axis for the L1SP linterp (x0 convention from L1SPFilter::init_resp)
        intrinsic_toff_ns = fr.origin / fr.speed
        intrinsic_toff_us = intrinsic_toff_ns / units.us
        x0_us = (-intrinsic_toff_us
                 - L1SP_COARSE_TIME_OFFSET_US
                 + L1SP_FINE_TIME_OFFSET_US)
        t_l1sp_us = x0_us + np.arange(N_fr) * (period_ns / 1000.0)

        adc_mv_wc  = ADC_PER_MV / units.mV
        kern_peak  = np.max(np.abs(resp_l1))
        print(f'\nL1SP normalization chain ({label} plane):')
        print(f'  postgain                    = {POSTGAIN}')
        print(f'  ADC_PER_MV (count/mV)       = {ADC_PER_MV}')
        print(f'  units.mV (WC unit value)    = {units.mV:.6g}')
        print(f'  ADC_MV_WC = ADC_PER_MV/mV  = {adc_mv_wc:.6g}  count/(WC-mV)')
        print(f'  fine_period (ns)            = {period_ns}')
        print(f'  sign                        = -1')
        print(f'  kernel |peak| (ADC/e)       = {kern_peak:.4g}')
        print(f'  kernel |peak| × N_MIP (ADC) = {kern_peak * N_MIP_PER_PITCH:.2f}')
        print(f'\nL1SP time-offset chain ({label} plane):')
        print(f'  fr.origin (WC length)       = {fr.origin:.6g}')
        print(f'  fr.speed  (WC velocity)     = {fr.speed:.6g}')
        print(f'  intrinsic_toff (µs)         = {intrinsic_toff_us:.4f}')
        print(f'  coarse_time_offset (µs)     = {L1SP_COARSE_TIME_OFFSET_US}')
        print(f'  fine_time_offset (µs)       = {L1SP_FINE_TIME_OFFSET_US}')
        print(f'  x0 for lin_{label}(t) (µs)   = {x0_us:.4f}')
        print(f'  inside L1_fit:')
        print(f'    overall_time_offset (µs)  = 0.0  (uBooNE default)')
        print(f'    collect_time_offset (µs)  = {L1SP_COLLECT_TIME_OFFSET_US:+.1f}  (W-basis arg shift; V unshifted)')
        print(f'    output placement          = start_tick + j  (no shift)')

        outpath = os.path.join(WORKDIR, f'track_response_uboone_{label}.png')
        make_plot(wave_adc, chndb_ref, tick_us, label, outpath,
                  resp_l1_mip=resp_l1_mip, t_l1sp_us=t_l1sp_us)


if __name__ == '__main__':
    run()
