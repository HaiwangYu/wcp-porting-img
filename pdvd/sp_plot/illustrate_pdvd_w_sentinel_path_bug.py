#!/usr/bin/env python3
"""
Illustrate the PDVD W-plane all-zero sentinel-path bug.

The PDVD field-response file
``protodunevd_FR_imbalance3p_260501.json.bz2`` contains an
**identically-zero path at pp=0 on the W plane only**.  The
``wirecell.sigproc.l1sp.line_source_response`` integrator used to treat
that entry as legitimate data, pinning the central weight to zero and
under-normalising the W collection peak by ~12%.  PDHD's
``dune-garfield-1d565.json.bz2`` does not have this issue.

The fix (now in production): skip any path whose current is identically
zero.

This script produces a single inspection PNG laid out as a 3×3 grid;
columns are the three planes (U=0, V=1, W=2) and rows are:

  row 0 — PDVD central-wire path currents.  The pp=0 path is drawn on
          top in red; W shows it dead flat (the sentinel), while U/V
          carry real current there.
  row 1 — PDHD central-wire path currents (control).  Every plane has
          a normal pp=0 entry, including W.
  row 2 — line-source response for that plane: production path (with
          the all-zero filter, blue) vs the legacy unfiltered path
          (red).  Only the W column shows a Δ; U and V are identical
          curves, visually proving the bug is W-only.

Run with no arguments — outputs ``pdvd_w_sentinel_path_bug.png`` next
to this script.
"""

import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from wirecell.sigproc.response import persist as fr_persist
from wirecell.util.fileio import wirecell_path

WORKDIR  = os.path.dirname(os.path.abspath(__file__))
OUT_PNG  = os.path.join(WORKDIR, 'pdvd_w_sentinel_path_bug.png')

PDVD_FR  = 'protodunevd_FR_imbalance3p_260501.json.bz2'
PDHD_FR  = 'dune-garfield-1d565.json.bz2'


def line_source_response(plane, skip_zero=True):
    """Re-implementation of wirecell.sigproc.l1sp.line_source_response.

    With ``skip_zero=True`` (production behaviour) all-zero paths are
    discarded so the trapezoidal weights collapse onto the real samples.
    With ``skip_zero=False`` we reproduce the pre-fix behaviour for the
    side-by-side comparison.
    """
    pitch = plane.pitch
    n = len(plane.paths[0].current)

    by_r = defaultdict(list)
    for path in plane.paths:
        cur = np.asarray(path.current, dtype=float)
        if skip_zero and not np.any(cur):
            continue
        r  = int(round(path.pitchpos / pitch))
        xi = path.pitchpos - r * pitch
        by_r[r].append((xi, cur))

    integral = np.zeros(n)
    for items in by_r.values():
        sym = {xi: I for xi, I in items}
        for xi in list(sym):
            if abs(xi) > 1e-9 and (-xi) not in sym:
                sym[-xi] = sym[xi]
        xis = sorted(sym)
        m = len(xis)
        w = np.empty(m)
        w[0]  = (xis[1]  - xis[0])  / 2.0
        w[-1] = (xis[-1] - xis[-2]) / 2.0
        for i in range(1, m - 1):
            w[i] = (xis[i + 1] - xis[i - 1]) / 2.0
        for xi, wi in zip(xis, w):
            integral += wi * sym[xi]
    return integral / pitch


def get_plane(fr, planeid):
    for pl in fr.planes:
        if pl.planeid == planeid:
            return pl
    raise RuntimeError(f'no plane {planeid} in FR')


PLANE_LABELS = {0: 'U', 1: 'V', 2: 'W'}


def central_paths(plane):
    """Sorted list of (pp, current_array) for paths within ±pitch/2."""
    out = []
    for p in plane.paths:
        if abs(p.pitchpos) <= plane.pitch / 2.0 + 1e-3:
            out.append((p.pitchpos, np.asarray(p.current, dtype=float)))
    out.sort(key=lambda x: x[0])
    return out


def _action_window(paths, period_ns, threshold_frac=0.02):
    """Time window (µs) covering the FR's non-trivial activity, with margin."""
    n = len(paths[0][1])
    stack = np.array([cur for _, cur in paths])
    envelope = np.max(np.abs(stack), axis=0)
    thr = threshold_frac * np.max(envelope)
    active = np.where(envelope > thr)[0]
    if not len(active):
        return 0.0, n * period_ns / 1000.0
    pad = max(5, int(2.0 * 1000.0 / period_ns))   # ~2 µs each side
    lo = max(active[0] - pad, 0)
    hi = min(active[-1] + pad, n - 1)
    return lo * period_ns / 1000.0, hi * period_ns / 1000.0


def _plot_central_paths(ax, plane, period_ns, title):
    paths = central_paths(plane)
    t_us = np.arange(len(paths[0][1])) * period_ns / 1000.0
    # Excluding the boundary path (|pp| ≈ pitch/2) when it would otherwise
    # dominate the y-range; keep it visible in legend but on a softer line.
    boundary_thr = plane.pitch / 2.0 - 1e-3
    # plot the non-zero, non-boundary paths first (background)
    for pp, cur in paths:
        if abs(pp) < 1e-6:
            continue
        is_boundary = abs(pp) >= boundary_thr
        ax.plot(t_us, cur * 1e3,
                lw=0.6 if is_boundary else 1.0,
                alpha=0.4 if is_boundary else 0.85,
                ls=':' if is_boundary else '-',
                label=f'pp={pp:+.3f} mm' + ('  (wire boundary)' if is_boundary else ''))
    # highlight pp=0 on top
    for pp, cur in paths:
        if abs(pp) < 1e-6:
            zero_flag = '  ALL ZEROS (sentinel)' if not np.any(cur) else ''
            ax.plot(t_us, cur * 1e3, color='crimson', lw=2.4, ls='-',
                    label=f'pp={pp:+.3f} mm{zero_flag}', zorder=5)
    ax.axhline(0, color='gray', lw=0.5, ls=':')
    lo_us, hi_us = _action_window(paths, period_ns)
    ax.set_xlim(lo_us, hi_us)
    ax.set_xlabel('time (µs)')
    ax.set_ylabel('current per electron  (×10$^{-3}$ WC units)')
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, ncol=2, loc='best')
    ax.grid(True, alpha=0.3)
    return lo_us, hi_us


def _has_zero_sentinel(plane):
    """True if the plane has at least one identically-zero path."""
    for p in plane.paths:
        if not np.any(np.asarray(p.current)):
            return True
    return False


def main():
    print('Loading PDVD FR ...')
    pdvd = fr_persist.load(PDVD_FR, paths=wirecell_path())
    print('Loading PDHD FR ...')
    pdhd = fr_persist.load(PDHD_FR, paths=wirecell_path())

    period_pdvd = float(pdvd.period)
    period_pdhd = float(pdhd.period)

    fig, axes = plt.subplots(3, 3, figsize=(18, 12))
    fig.subplots_adjust(hspace=0.42, wspace=0.20)

    for col, planeid in enumerate((0, 1, 2)):
        plabel  = PLANE_LABELS[planeid]
        pdvd_pl = get_plane(pdvd, planeid)
        pdhd_pl = get_plane(pdhd, planeid)

        # Row 0: PDVD central-wire path currents.
        sentinel_tag = '  ← SENTINEL' if _has_zero_sentinel(pdvd_pl) else ''
        pdvd_lo, pdvd_hi = _plot_central_paths(
            axes[0, col], pdvd_pl, period_pdvd,
            title=f'PDVD {plabel} plane (pitch={pdvd_pl.pitch} mm){sentinel_tag}')

        # Row 1: PDHD central-wire path currents (control).
        _plot_central_paths(
            axes[1, col], pdhd_pl, period_pdhd,
            title=f'PDHD {plabel} plane (pitch={pdhd_pl.pitch} mm)  — control')

        # Row 2: line_source_response, buggy vs fixed (PDVD).
        line_buggy = line_source_response(pdvd_pl, skip_zero=False)
        line_fixed = line_source_response(pdvd_pl, skip_zero=True)
        peak_buggy = float(np.max(np.abs(line_buggy)))
        peak_fixed = float(np.max(np.abs(line_fixed)))
        int_buggy  = float(np.sum(line_buggy)) * period_pdvd
        int_fixed  = float(np.sum(line_fixed)) * period_pdvd
        peak_ratio = peak_fixed / peak_buggy if peak_buggy > 0 else 1.0
        int_ratio  = (int_fixed  / int_buggy)  if int_buggy  != 0 else 1.0
        print(f'  PDVD {plabel}: buggy |peak|={peak_buggy:.3e} ∫={int_buggy:+.4f}   '
              f'fixed |peak|={peak_fixed:.3e} ∫={int_fixed:+.4f}   '
              f'ratios peak ×{peak_ratio:.4f} ∫ ×{int_ratio:.4f}')

        n = len(line_fixed)
        t_us = np.arange(n) * period_pdvd / 1000.0
        ax = axes[2, col]
        ax.plot(t_us, line_buggy * 1e3, color='crimson',   lw=1.4, alpha=0.85,
                label=f'buggy: |peak|={peak_buggy:.3e}\n        ∫={int_buggy:+.3f}')
        ax.plot(t_us, line_fixed * 1e3, color='steelblue', lw=1.4,
                label=f'fixed:  |peak|={peak_fixed:.3e}\n        ∫={int_fixed:+.3f}')
        ax.fill_between(t_us, line_buggy * 1e3, line_fixed * 1e3,
                        color='black', alpha=0.10, label='Δ')
        ax.axhline(0, color='gray', lw=0.5, ls=':')
        ax.set_xlim(pdvd_lo, pdvd_hi)
        ax.set_xlabel('time (µs)')
        ax.set_ylabel('line-source resp.  (×10$^{-3}$ per electron)')
        delta_tag = (f'peak ×{peak_ratio:.3f}, ∫ ×{int_ratio:.3f}'
                     if abs(peak_ratio - 1.0) > 1e-6
                     else 'identical (no sentinel; filter is no-op)')
        ax.set_title(f'PDVD {plabel} line_source_response  —  {delta_tag}',
                     fontsize=10)
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        'All-zero sentinel-path bug  —  central-wire FR currents per plane '
        '(PDVD vs PDHD) + line_source_response Δ',
        fontsize=13)
    plt.savefig(OUT_PNG, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'\nWrote {OUT_PNG}')


if __name__ == '__main__':
    main()
