#!/usr/bin/env python3
"""
Visual check that the CoherentNoiseSub response_offset is correct.

For each plane, reads the debug dump written by PDHD::SignalProtection
and overlays:
  - medians          (raw pre-deconv ADC, red)
  - decon_shifted    (medians_decon rolled by +res_offset, scaled, blue dashed)

If the offset is correct the dominant features should overlap.
"""

import argparse
import os
import re
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PLANES = [
    ("U", "sp_decon_dump_offset127.txt"),
    ("V", "sp_decon_dump_offset132.txt"),
]

DEFAULT_INDIR = "/home/xqian/tmp"
DEFAULT_OUTDIR = os.path.dirname(os.path.abspath(__file__))


def parse_header(path):
    with open(path) as fh:
        line = fh.readline()
    nbin = int(re.search(r'nbin=(\d+)', line).group(1))
    res_offset = int(re.search(r'res_offset=(\d+)', line).group(1))
    m = re.search(r'ptp=([\d.eE+\-]+)', line)
    ptp = float(m.group(1)) if m else None
    return nbin, res_offset, ptp


def plot_plane(plane, dump_path, outdir):
    nbin, res_offset, ptp = parse_header(dump_path)
    data = np.loadtxt(dump_path, comments='#')
    medians = data[:, 0]
    medians_decon = data[:, 1]

    decon_shifted = np.roll(medians_decon, +res_offset)

    ptp_raw = np.ptp(medians)
    ptp_dec = np.ptp(decon_shifted)
    scale = ptp_raw / ptp_dec if ptp_dec != 0 else 1.0
    decon_scaled = decon_shifted * scale

    ticks = np.arange(nbin)
    centre = int(np.argmin(medians))
    lo = max(0, centre - 200)
    hi = min(nbin, centre + 200)

    fig, axes = plt.subplots(2, 1, figsize=(14, 8))

    for ax, (t, m, d, title) in zip(
        axes,
        [
            (ticks, medians, decon_scaled,
             f'Full window ({nbin} ticks)  —  plane {plane}  '
             f'res_offset={res_offset}  scale={scale:.3g}'
             + (f'  ptp={ptp:.1f} ADC' if ptp else '')),
            (ticks[lo:hi], medians[lo:hi], decon_scaled[lo:hi],
             f'Zoom ±200 ticks around dominant feature (tick {centre})'),
        ],
    ):
        ax.plot(t, m, 'r-', lw=1, label='medians (pre-deconv)')
        ax.plot(t, d, 'b--', lw=1, label=f'decon_shifted×{scale:.3g} (post-deconv, +{res_offset} roll)')
        ax.axhline(0, color='gray', lw=0.5)
        ax.set_xlabel('tick')
        ax.set_ylabel('ADC')
        ax.set_title(title)
        ax.legend(fontsize=8, loc='upper right')

    plt.tight_layout()
    outpath = os.path.join(outdir, f'sp_decon_alignment_{plane}.png')
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(outpath)
    return outpath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--indir', default=DEFAULT_INDIR)
    parser.add_argument('--outdir', default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    for plane, fname in PLANES:
        dump_path = os.path.join(args.indir, fname)
        if not os.path.exists(dump_path):
            print(f'WARNING: {dump_path} not found, skipping', file=sys.stderr)
            continue
        plot_plane(plane, dump_path, args.outdir)


if __name__ == '__main__':
    main()
