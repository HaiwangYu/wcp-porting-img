#!/usr/bin/env python3
"""
ProtoDUNE-VD bottom-CRP FR ⊗ ER perpendicular-line track response, U & V planes.

Uses `protodunevd_FR_norminal_260324.json.bz2` (schema FR; resolved via
WIRECELL_PATH).  Field response is integrated as a perpendicular line source
via translation invariance — line_response = (Δx / pitch) × Σ_paths.

Outputs (same directory as this script):
  track_response_pdvd_bottom_U.png
  track_response_pdvd_bottom_V.png

Each PNG: top = ADC waveform vs time (with chndb-resp overlay), bottom = |FFT|.

Note: protodunevd/chndb-resp.jsonnet is a byte-identical copy of SBND's file
(md5 5858e44a…).  No per-PDVD response has been generated yet.  The dashed
overlay is shown for visual continuity only — shape and scale do not reflect
PDVD detector response.

Bottom-CRP electronics (coherent_nf_params_comparison.md §2–3):
  cold electronics  gain=7.8 mV/fC,  shaping=2.2 µs,  postgain=1.1365
  ADC: 14-bit, 0.2–1.6 V → 11.70 ADC/mV
  pitch (per plane, read from FR file):  U=V=7.65 mm,  W=5.10 mm
  N_MIP (user definition) = 1.8 MeV/cm × pitch_cm × 0.7 / 23.6 eV
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
FR_FILE_NOMINAL = 'protodunevd_FR_norminal_260324.json.bz2'
FR_FILE         = 'protodunevd_FR_imbalance3p_260501.json.bz2'

CHNDB_RESP_FILE = ('/nfs/data/1/xqian/toolkit-dev/toolkit/cfg/pgrapher'
                   '/experiment/protodunevd/chndb-resp-bot.jsonnet')
CHNDB_TICK_US = 0.5      # chndb-resp arrays sampled at 500 ns

SIM_DIR      = '/nfs/data/1/xning/wirecell-working/data/sim/'
SIM_FILE_FMT = ('protodune-sp-frames-sim-vd-anode0-{P}-anode0'
                '.tar.bz2.{P}-waveform.npy')
SIM_TICK_US  = 0.5

ADC_TICK_NS = 500.0      # PDVD daq tick = 0.5 µs (params.jsonnet inherits common)

# Working window for FR⊗ER convolution. PDVD's FR file is ~132.5 µs which
# is shorter than the bipolar induction tail; without padding the FFT-based
# convolution wraps. 160 µs gives clear separation between the response and
# the wraparound zone.
OUTPUT_WINDOW_NS = 160_000.0

# PDVD bottom-CRP cold-electronics parameters (§2)
GAIN        = 7.8  * units.mV / units.fC
SHAPING     = 2.2  * units.us
POSTGAIN    = 1.1365

# PDVD bottom ADC: 14-bit, 0.2–1.6 V fullscale → 11.70 ADC/mV (§3)
ADC_PER_MV  = 11.70

# MIP electrons per wire pitch (user formula): N = 1.8 MeV/cm × pitch_cm × 0.7 / 23.6 eV
def n_mip(pitch_mm):
    return (1.8e6 * (pitch_mm / 10.0) * 0.7) / 23.6


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


def load_sim_overlay(plane_label):
    path = os.path.join(SIM_DIR, SIM_FILE_FMT.format(P=plane_label))
    if not os.path.exists(path):
        return None
    return path, np.load(path)


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


def make_plot(wave_adc, chndb_ref, tick_us, plane_label, pitch_mm, n_mip_pl, outpath, sim=None, wave_nominal=None):
    N = len(wave_adc)
    t_us      = np.arange(N) * tick_us
    freqs_mhz = np.fft.rfftfreq(N, d=tick_us)

    pk_pos = wave_adc[np.argmax(wave_adc)]
    pk_neg = wave_adc[np.argmin(wave_adc)]

    i_neg_adc   = int(np.argmin(wave_adc))
    t_neg_us    = t_us[i_neg_adc]
    i_neg_chndb = int(np.argmin(chndb_ref))
    t_chndb     = t_neg_us + (np.arange(len(chndb_ref)) - i_neg_chndb) * CHNDB_TICK_US
    scale       = pk_neg / chndb_ref[i_neg_chndb]
    chndb_scaled = chndb_ref * scale

    params_str = (f'gain={GAIN/(units.mV/units.fC):.1f} mV/fC  '
                  f'shaping={SHAPING/units.us:.1f} µs  '
                  f'postgain={POSTGAIN}  '
                  f'ADC/mV={ADC_PER_MV}  '
                  f'pitch={pitch_mm:.2f} mm  '
                  f'N_MIP≈{n_mip_pl:.0f} e⁻/pitch  '
                  f'tick={tick_us*1000:.0f} ns')

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    ax = axes[0]
    if wave_nominal is not None:
        t_us_nom = np.arange(len(wave_nominal)) * tick_us
        ax.plot(t_us_nom, wave_nominal, color='#888888', lw=1.0, ls='--',
                label='nominal FR (260324)')
    ax.plot(t_us, wave_adc, 'r-', lw=1.5,
            label=f'FR ⊗ ER (digitized at {tick_us*1000:.0f} ns)  [{params_str}]')
    ax.plot(t_chndb, chndb_scaled, 'b--', lw=1.5,
            label=f'chndb-resp.jsonnet — SBND placeholder copy  (×{scale:.3g}, aligned at neg. peak)')
    if sim is not None:
        sim_path, y_sim = sim
        sim_basename = os.path.basename(sim_path)
        j_sim = int(np.argmax(y_sim))
        i_model = int(np.argmax(wave_adc))
        sim_scale = wave_adc[i_model] / y_sim[j_sim]
        t_sim = t_us[i_model] + (np.arange(len(y_sim)) - j_sim) * SIM_TICK_US
        ax.plot(t_sim, y_sim * sim_scale, 'g--', lw=1.5,
                label=(f'sim: {sim_basename}  (×{sim_scale:.3g}, aligned at pos. peak)'
                       f'\n  [sim @ ~50 cm drift, mean ADC over channels >5·RMS]'))
    ax.axhline(0, color='gray', lw=0.5)
    ax.set_xlabel('time (µs)')
    ax.set_ylabel('ADC')
    ax.set_title(
        f'ProtoDUNE-VD bottom CRP  —  plane {plane_label}  '
        f'—  full window ({N * tick_us:.1f} µs)\n'
        f'FR ⊗ ER  (MIP perpendicular-line track)   '
        f'peak = {pk_pos:.1f} ADC,  trough = {pk_neg:.1f} ADC'
    )
    ax.legend(fontsize=8, loc='upper left')

    ax = axes[1]
    ax.plot(freqs_mhz, np.abs(np.fft.rfft(wave_adc)), 'r-', lw=1.5, label='FR ⊗ ER')
    freqs_chndb = np.fft.rfftfreq(len(chndb_scaled), d=CHNDB_TICK_US)
    ax.plot(freqs_chndb, np.abs(np.fft.rfft(chndb_scaled)), 'b--', lw=1.5, label='chndb-resp (SBND placeholder)')
    if sim is not None:
        freqs_sim = np.fft.rfftfreq(len(y_sim), d=SIM_TICK_US)
        ax.plot(freqs_sim, np.abs(np.fft.rfft(y_sim * sim_scale)), 'g--', lw=1.5, label='sim')
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
    print(f'Loading {FR_FILE_NOMINAL} for comparison ...')
    fr_nom = persist.load(FR_FILE_NOMINAL, paths=wirecell_path())
    nom_planes = {pl.planeid: pl for pl in fr_nom.planes}

    period_ns = fr.period
    N_fr_native = len(fr.planes[0].paths[0].current)
    if OUTPUT_WINDOW_NS > N_fr_native * period_ns:
        N_fr = int(round(OUTPUT_WINDOW_NS / period_ns))
        print(f'FR padded: N_native = {N_fr_native} → N = {N_fr} '
              f'({N_fr * period_ns / 1000:.1f} µs)')
    else:
        N_fr = N_fr_native
    times = np.arange(N_fr, dtype=float) * period_ns

    er = np.asarray(wc_resp.electronics(times, peak_gain=GAIN, shaping=SHAPING,
                                        elec_type='cold'), dtype=float)
    print(f'\nElectronics: gain={GAIN/(units.mV/units.fC):.1f} mV/fC  '
          f'shaping={SHAPING/units.us:.1f} µs  postgain={POSTGAIN}')
    print(f'  ER peak at {times[np.argmax(np.abs(er))]/1000.0:.2f} µs')
    print(f'ADC/mV = {ADC_PER_MV}  |  ADC tick = {ADC_TICK_NS:.0f} ns')

    chndb = parse_chndb_resp(CHNDB_RESP_FILE)
    print(f'Loaded chndb-resp from {CHNDB_RESP_FILE}')

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

        n_mip_pl = n_mip(pl.pitch)
        print(f'\n=== planeid={pid}  ({label})  pitch={pl.pitch:.2f} mm  '
              f'N_MIP={n_mip_pl:.0f} e⁻/pitch ===')

        fr_line = line_source_response(pl)
        if N_fr > len(fr_line):
            fr_pad = np.zeros(N_fr)
            fr_pad[:len(fr_line)] = fr_line
            fr_line = fr_pad
        wave_frer = wc_resp.convolve(fr_line, er)

        wave_mv = -(wave_frer
                    * period_ns
                    * n_mip_pl
                    / units.mV
                    * POSTGAIN)

        wave_mv_resampled = sp_resample(wave_mv, N_adc)
        wave_adc = wave_mv_resampled * ADC_PER_MV

        pk_pos_adc = wave_adc[np.argmax(wave_adc)]
        pk_neg_adc = wave_adc[np.argmin(wave_adc)]
        t_adc = np.arange(N_adc) * tick_us
        t_pos = t_adc[np.argmax(wave_adc)]
        t_neg = t_adc[np.argmin(wave_adc)]
        print(f'  FR⊗ER (ADC @ {ADC_TICK_NS:.0f} ns):  '
              f'positive peak  {pk_pos_adc:+.2f} ADC at {t_pos:.2f} µs')
        print(f'                             '
              f'negative trough {pk_neg_adc:+.2f} ADC at {t_neg:.2f} µs')

        sum_pos = float(wave_adc[wave_adc > 0].sum()) * tick_us
        sum_neg = float(wave_adc[wave_adc < 0].sum()) * tick_us
        net     = sum_pos + sum_neg
        total   = sum_pos - sum_neg
        balance = net / total
        print(f'  bipolar balance:  ∫+ = {sum_pos:+.2f}  ∫- = {sum_neg:+.2f}  '
              f'net = {net:+.2f}  total = {total:.2f}  balance = {balance:+.4f} (ADC·µs)')

        # Compute nominal FR response for imbalance comparison
        pl_nom = nom_planes[pid]
        fr_line_nom = line_source_response(pl_nom)
        if N_fr > len(fr_line_nom):
            _pad = np.zeros(N_fr); _pad[:len(fr_line_nom)] = fr_line_nom; fr_line_nom = _pad
        wave_adc_nom = sp_resample(
            -(wc_resp.convolve(fr_line_nom, er) * period_ns * n_mip(pl_nom.pitch) / units.mV * POSTGAIN),
            N_adc) * ADC_PER_MV
        sp_nom = float(wave_adc_nom[wave_adc_nom > 0].sum()) * tick_us
        sn_nom = float(wave_adc_nom[wave_adc_nom < 0].sum()) * tick_us
        net_nom = sp_nom + sn_nom; tot_nom = sp_nom - sn_nom
        print(f'  --- imbalance comparison ---')
        print(f'  {"":18s}  {"nominal 260324":>16s}  {"imbalance3p 260501":>20s}')
        print(f'  {"pos peak (ADC)":18s}  {wave_adc_nom[np.argmax(wave_adc_nom)]:>16.2f}  {pk_pos_adc:>20.2f}')
        print(f'  {"neg trough (ADC)":18s}  {wave_adc_nom[np.argmin(wave_adc_nom)]:>16.2f}  {pk_neg_adc:>20.2f}')
        print(f'  {"∫+ (ADC·µs)":18s}  {sp_nom:>16.2f}  {sum_pos:>20.2f}')
        print(f'  {"∫- (ADC·µs)":18s}  {sn_nom:>16.2f}  {sum_neg:>20.2f}')
        print(f'  {"net (ADC·µs)":18s}  {net_nom:>+16.4f}  {net:>+20.4f}')
        print(f'  {"balance":18s}  {net_nom/tot_nom:>+16.4f}  {balance:>+20.4f}')

        chndb_ref = chndb[chndb_keys[pid]]
        i_neg_c   = int(np.argmin(chndb_ref))
        scale     = pk_neg_adc / chndb_ref[i_neg_c]
        print(f'  chndb-resp neg peak at sample {i_neg_c}  '
              f'({i_neg_c * CHNDB_TICK_US:.1f} µs),  scale = {scale:.4g}')

        sim = load_sim_overlay(label)
        if sim is not None:
            sim_path, y_sim = sim
            j_sim = int(np.argmax(y_sim))
            sim_scale = wave_adc[np.argmax(wave_adc)] / y_sim[j_sim]
            print(f'  sim overlay: {os.path.basename(sim_path)}  '
                  f'pos peak={y_sim[j_sim]:.2f} at idx {j_sim},  scale={sim_scale:.4g}')

        outpath = os.path.join(WORKDIR, f'track_response_pdvd_bottom_{label}.png')
        make_plot(wave_adc, chndb_ref, tick_us, label, pl.pitch, n_mip_pl, outpath, sim=sim,
                  wave_nominal=wave_adc_nom)


if __name__ == '__main__':
    run()
