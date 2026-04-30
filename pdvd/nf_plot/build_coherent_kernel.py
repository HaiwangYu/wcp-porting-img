#!/usr/bin/env python3
"""
Reconstruct and compare coherent-NF deconvolution kernels.

For uBooNE and SBND: compares two candidate recipes against the existing
chndb-resp.jsonnet reference arrays to identify the generation recipe and
normalization convention.

For PDHD and PDVD: the existing chndb-resp.jsonnet files are SBND placeholders
(identical values).  This script applies the winning recipe to the proper FR
and emits predicted u_resp/v_resp arrays ready for review.

Candidate recipes:
  Recipe-FR     — sum all path currents per plane (SBND's documented recipe)
  Recipe-FR×ER  — convolve Recipe-FR with the cold-electronics impulse response

Normalization metrics computed for each (detector, plane, recipe):
  peak_ratio   — max|ref| / max|candidate|
  lsq_scale    — least-squares scale argmin_α ||ref − α·cand||²
  int_ratio    — Σref / Σcand
  neglobe_ratio — Σref[<0] / Σcand[<0]
  residual_norm — ||ref − α·cand||₂ / ||ref||₂  (post-fit)

Outputs (in the same directory as this script):
  kernel_compare_{det}_{plane}.png        waveform + spectrum overlay
  kernel_compare_summary.txt              table of normalization metrics
  kernel_predicted_{det}_{plane}.json     predicted kernel arrays (PDHD, PDVD)
  kernel_predicted_{det}_{plane}.png      waveform + spectrum of predicted kernel
"""

import os, re, sys, json
import numpy as np
from scipy.signal import resample as sp_resample
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from wirecell.sigproc.response import persist
from wirecell.sigproc import response as wc_resp
from wirecell import units
from wirecell.util.fileio import wirecell_path

WORKDIR    = os.path.dirname(os.path.abspath(__file__))
WC_PATHS   = wirecell_path()
CHNDB_TICK = 500.0   # ns — chndb runs at 500 ns ticks

# Experiment configurations
TOOLKIT_CFG = '/nfs/data/1/xqian/toolkit-dev/toolkit/cfg/pgrapher/experiment'

DETECTORS = {
    'uboone': {
        'fr_file':   'ub-10-half.json.bz2',
        'gain':      14.0 * units.mV / units.fC,
        'shaping':   2.0  * units.us,
        'ref_file':  os.path.join(TOOLKIT_CFG, 'uboone/chndb-resp.jsonnet'),
        'n_samples': 120,
        'placeholder': False,
    },
    'sbnd': {
        'fr_file':   'garfield-sbnd-v1.json.bz2',
        'gain':      14.0 * units.mV / units.fC,
        'shaping':   2.0  * units.us,
        'ref_file':  os.path.join(TOOLKIT_CFG, 'sbnd/chndb-resp.jsonnet'),
        'n_samples': 200,
        'placeholder': False,
    },
    'pdhd': {
        'fr_file':   'np04hd-garfield-6paths-mcmc-bestfit.json.bz2',
        'gain':      14.0 * units.mV / units.fC,
        'shaping':   2.2  * units.us,
        'ref_file':  os.path.join(TOOLKIT_CFG, 'pdhd/chndb-resp.jsonnet'),
        'n_samples': 200,
        'placeholder': True,   # current file is a copy of SBND's values
    },
    'pdvd': {
        'fr_file':   'protodunevd_FR_norminal_260324.json.bz2',
        'gain':      7.8  * units.mV / units.fC,
        'shaping':   2.2  * units.us,
        'ref_file':  os.path.join(TOOLKIT_CFG, 'protodunevd/chndb-resp.jsonnet'),
        'n_samples': 200,
        'placeholder': True,   # current file is a copy of SBND's values
    },
}

PLANE_ID   = {'U': 0, 'V': 1}
PLANE_KEYS = {'U': 'u_resp', 'V': 'v_resp'}

# ---------------------------------------------------------------------------
# Field-response helpers
# ---------------------------------------------------------------------------

def load_fr(fr_file):
    """Return schema.FieldResponse for the given FR JSON.bz2 filename."""
    return persist.load(fr_file, paths=WC_PATHS)


def fr_path_sum(fr, plane_id):
    """
    Sum all path currents for plane_id — this is the SBND-documented recipe:
        for path in plane.paths:
            waveform[i] += path.current[i]
    Returns (array at FR native period, period_ns).
    """
    plane = next(p for p in fr.planes if p.planeid == plane_id)
    N = len(plane.paths[0].current)
    tot = np.zeros(N)
    for path in plane.paths:
        tot += np.array(path.current)
    return tot, fr.period   # period is already in ns (WC units == ns)


def electronics_response(n_samples, period_ns, gain, shaping):
    """Evaluate the cold-electronics impulse response at the FR native period."""
    times = np.arange(n_samples, dtype=float) * period_ns
    er = wc_resp.electronics(times, peak_gain=gain, shaping=shaping, elec_type="cold")
    return np.asarray(er, dtype=float)


def convolve_fr_er(k_fr, er):
    """Convolve FR path-sum with electronics response via FFT (circular)."""
    return np.real(np.fft.ifft(np.fft.fft(k_fr) * np.fft.fft(er)))


def decimate(arr, fr_period_ns, tick_ns, n_out):
    """
    Resample arr from fr_period_ns to tick_ns, returning n_out samples.
    Uses scipy FFT-based resampling (anti-aliased).
    """
    total_duration = len(arr) * fr_period_ns
    n_target = int(round(total_duration / tick_ns))
    arr_rs = sp_resample(arr, n_target)
    if len(arr_rs) >= n_out:
        return arr_rs[:n_out]
    out = np.zeros(n_out)
    out[:len(arr_rs)] = arr_rs
    return out

# ---------------------------------------------------------------------------
# Reference file parsing
# ---------------------------------------------------------------------------

def parse_chndb_resp(path):
    """
    Extract u_resp and v_resp float arrays from a chndb-resp.jsonnet file.
    Handles the simple jsonnet literal-array format used in these files.
    """
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

# ---------------------------------------------------------------------------
# Normalization metrics
# ---------------------------------------------------------------------------

def best_shift(ref, cand):
    """Return the integer shift (in samples) that maximises xcorr(ref, cand)."""
    xcorr = np.real(np.fft.ifft(np.fft.fft(ref) * np.conj(np.fft.fft(cand))))
    sh = int(np.argmax(xcorr))
    if sh > len(ref) // 2:
        sh -= len(ref)
    return sh


def normalization_metrics(ref, cand):
    """
    Align cand to ref via cross-correlation then compute:
      peak_ratio, lsq_scale, int_ratio, neglobe_ratio, residual_norm, shift
    """
    sh = best_shift(ref, cand)
    cand_a = np.roll(cand, sh)

    peak_cand = np.max(np.abs(cand_a))
    peak_ratio = np.max(np.abs(ref)) / peak_cand if peak_cand else float('nan')

    denom = np.dot(cand_a, cand_a)
    lsq_scale = np.dot(ref, cand_a) / denom if denom else float('nan')

    int_cand = np.sum(cand_a)
    integral_ratio = np.sum(ref) / int_cand if int_cand else float('nan')

    neg_ref  = np.sum(ref[ref < 0])
    neg_cand = np.sum(cand_a[cand_a < 0])
    neglobe_ratio = neg_ref / neg_cand if neg_cand else float('nan')

    fitted = lsq_scale * cand_a
    norm_ref = np.linalg.norm(ref)
    residual_norm = np.linalg.norm(ref - fitted) / norm_ref if norm_ref else float('nan')

    return peak_ratio, lsq_scale, integral_ratio, neglobe_ratio, residual_norm, sh

# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_comparison(ref, k_fr, k_frer, tick_ns, label, outpath):
    """Overlay: reference vs two scaled candidates (waveform + spectrum)."""
    _, sc_fr,   _, _, _, sh_fr   = normalization_metrics(ref, k_fr)
    _, sc_frer, _, _, _, sh_frer = normalization_metrics(ref, k_frer)

    t_us   = np.arange(len(ref)) * tick_ns / 1000.0
    freqs  = np.fft.rfftfreq(len(ref), d=tick_ns * 1e-3)  # MHz

    fig, axes = plt.subplots(2, 1, figsize=(10, 8))

    ax = axes[0]
    ax.plot(t_us, ref,                              'k-',  lw=2.0, label='chndb reference')
    ax.plot(t_us, sc_fr   * np.roll(k_fr,   sh_fr),  'b--', lw=1.5, label=f'Recipe-FR  (scale={sc_fr:.3g})')
    ax.plot(t_us, sc_frer * np.roll(k_frer, sh_frer), 'r:',  lw=1.5, label=f'Recipe-FR×ER (scale={sc_frer:.3g})')
    ax.axhline(0, color='gray', lw=0.5)
    ax.set_xlabel('time (µs)')
    ax.set_ylabel('amplitude (arb.)')
    ax.set_title(label)
    ax.legend(fontsize=8)

    ax = axes[1]
    ax.plot(freqs, np.abs(np.fft.rfft(ref)),                                   'k-',  lw=2.0, label='reference |FFT|')
    ax.plot(freqs, sc_fr   * np.abs(np.fft.rfft(np.roll(k_fr,   sh_fr))),   'b--', lw=1.5, label='Recipe-FR |FFT|')
    ax.plot(freqs, sc_frer * np.abs(np.fft.rfft(np.roll(k_frer, sh_frer))), 'r:',  lw=1.5, label='Recipe-FR×ER |FFT|')
    ax.set_xlabel('frequency (MHz)')
    ax.set_ylabel('|FFT| (arb.)')
    ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f'  wrote {outpath}')


def plot_predicted(kernel, tick_ns, label, outpath):
    """Waveform + spectrum for a predicted (new) kernel."""
    t_us  = np.arange(len(kernel)) * tick_ns / 1000.0
    freqs = np.fft.rfftfreq(len(kernel), d=tick_ns * 1e-3)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7))
    axes[0].plot(t_us, kernel, 'k-', lw=1.5)
    axes[0].axhline(0, color='gray', lw=0.5)
    axes[0].set_xlabel('time (µs)')
    axes[0].set_ylabel('amplitude (arb.)')
    axes[0].set_title(label)

    axes[1].plot(freqs, np.abs(np.fft.rfft(kernel)), 'k-', lw=1.5)
    axes[1].set_xlabel('frequency (MHz)')
    axes[1].set_ylabel('|FFT| (arb.)')

    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f'  wrote {outpath}')

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    hdr = (f"{'det':8s}  {'pl':2s}  {'recipe':6s}  "
           f"{'peak_ratio':>10s}  {'lsq_scale':>10s}  "
           f"{'int_ratio':>10s}  {'neglobe_r':>10s}  "
           f"{'residual':>8s}  {'shift_smp':>9s}")
    sep = '-' * len(hdr)
    rows = [hdr, sep]

    for det, cfg in DETECTORS.items():
        print(f'\n=== {det} (FR: {cfg["fr_file"]}) ===')
        if cfg['placeholder']:
            print('  NOTE: existing chndb-resp.jsonnet is a copy of SBND values (placeholder)')

        fr       = load_fr(cfg['fr_file'])
        n_out    = cfg['n_samples']
        gain     = cfg['gain']
        shaping  = cfg['shaping']
        ref_data = parse_chndb_resp(cfg['ref_file'])

        n_fr     = len(fr.planes[0].paths[0].current)
        period   = fr.period   # ns

        # Electronics response at native FR period
        er = electronics_response(n_fr, period, gain, shaping)

        predicted = {}

        for plane, pid in PLANE_ID.items():
            ref = ref_data[PLANE_KEYS[plane]]

            # Build candidates at native FR period
            k_fr_nat, _ = fr_path_sum(fr, pid)
            k_frer_nat  = convolve_fr_er(k_fr_nat, er)

            # Resample to chndb tick
            k_fr   = decimate(k_fr_nat,   period, CHNDB_TICK, n_out)
            k_frer = decimate(k_frer_nat, period, CHNDB_TICK, n_out)

            predicted[plane] = k_fr   # use Recipe-FR for prediction

            for recipe, cand in [('FR', k_fr), ('FR×ER', k_frer)]:
                pr, lsq, ir, nr, res, sh = normalization_metrics(ref, cand)
                row = (f'{det:8s}  {plane:2s}  {recipe:6s}  '
                       f'{pr:+10.4f}  {lsq:+10.4f}  '
                       f'{ir:+10.4f}  {nr:+10.4f}  '
                       f'{res:8.4f}  {sh:+9d}')
                rows.append(row)
                print(f'  {row}')

            # Comparison plot (all four detectors)
            note = ' [ref=SBND placeholder]' if cfg['placeholder'] else ''
            label = f'{det.upper()} plane {plane}{note}'
            plot_comparison(
                ref, k_fr, k_frer, CHNDB_TICK, label,
                os.path.join(WORKDIR, f'kernel_compare_{det}_{plane}.png'))

        # For PDHD and PDVD: emit predicted kernel JSON + PNG
        if cfg['placeholder']:
            for plane, kernel in predicted.items():
                out_json = os.path.join(WORKDIR, f'kernel_predicted_{det}_{plane}.json')
                with open(out_json, 'w') as fh:
                    json.dump({
                        'detector':  det,
                        'plane':     plane,
                        'recipe':    'FR-path-sum',
                        'fr_file':   cfg['fr_file'],
                        'gain_mVfC': cfg['gain'] / (units.mV / units.fC),
                        'shaping_us': cfg['shaping'] / units.us,
                        'tick_ns':   CHNDB_TICK,
                        PLANE_KEYS[plane]: kernel.tolist(),
                    }, fh, indent=2)
                print(f'  wrote {out_json}')

                plot_predicted(
                    kernel, CHNDB_TICK,
                    f'{det.upper()} plane {plane} — predicted (Recipe-FR)',
                    os.path.join(WORKDIR, f'kernel_predicted_{det}_{plane}.png'))

    # Write summary text
    rows.append(sep)
    rows.append('')
    rows.append('Notes:')
    rows.append('  residual_norm < 0.05 indicates a good recipe match.')
    rows.append('  lsq_scale converts candidate units to reference units.')
    rows.append('  PDHD and PDVD refs are SBND placeholders — their comparison is informative only.')
    summary = '\n'.join(rows)
    summary_path = os.path.join(WORKDIR, 'kernel_compare_summary.txt')
    with open(summary_path, 'w') as fh:
        fh.write(summary + '\n')
    print(f'\nwrote {summary_path}')
    print('\n' + summary)


if __name__ == '__main__':
    run()
