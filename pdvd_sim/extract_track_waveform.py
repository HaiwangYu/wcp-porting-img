#!/usr/bin/env python3
"""Extract a 1D peak-aligned mean waveform from one wire plane of a sim frame
archive (ProtoDUNE-VD).

Reuses helpers from the xqian woodpecker tree at
/nfs/data/1/xqian/toolkit-dev/Woodpecker/. This script exists because that
woodpecker version registers `compare-waveforms` but not the standalone
`extract-track-waveform` subcommand — so we wire up the same algorithm
locally, with detector and plane-split hard-coded for VD.

Plane split (VD): use the discontinuities (gaps) in the global channel
numbering — channel arrays are non-contiguous at plane boundaries.

Outputs (next to the frame archive):
    <archive>.<plane>-waveform.png
    <archive>.<plane>-waveform.npy

Usage:
    ./extract_track_waveform.py work/anode0-W/protodune-sp-frames-sim-anode0.tar.bz2
    ./extract_track_waveform.py <file> --plane V --threshold 7
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import numpy as np

# Use xqian's local woodpecker source (it isn't pip-installed as a module).
_WOODPECKER = "/nfs/data/1/xqian/toolkit-dev/Woodpecker"
if _WOODPECKER not in sys.path:
    sys.path.insert(0, _WOODPECKER)
from woodpecker.cli.cmd_compare_waveforms import (
    _aligned_mean_waveform_full,
    _load_frames,
    _split_planes,  # gap-based VD plane split
)


PLANE_LABELS = ["U", "V", "W"]


def _detect_plane(name: str, parent_dir: str):
    m = re.search(r"-anode\d+-([UVW])(?:-|\.)", name)
    if m:
        return m.group(1)
    m = re.match(r"anode\d+-([UVW])$", parent_dir)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("frame_file", help="Sim frame archive (e.g. *-anode<N>.tar.bz2)")
    ap.add_argument("--plane", default=None, choices=PLANE_LABELS,
                    help="Target plane (default: parse from filename or parent dir)")
    ap.add_argument("--tag", default=None,
                    help="Frame tag (default: auto-detect raw<N>/raw)")
    ap.add_argument("--threshold", type=float, default=5.0,
                    help="Signal-channel cut: |peak| > threshold * RMS (default: 5)")
    ap.add_argument("--half-window", type=int, default=200,
                    help="Half-width of output waveform in ticks (default: 200)")
    ap.add_argument("--out", default=None,
                    help="Output PNG (default: <frame_file>.<plane>-waveform.png; "
                         ".npy is written alongside)")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    path = args.frame_file
    if not os.path.exists(path):
        sys.exit(f"ERROR: file not found: {path}")

    base = os.path.basename(path)
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    plane = args.plane or _detect_plane(base, parent)
    if plane is None:
        sys.exit(f"ERROR: could not parse plane from '{base}' or parent dir '{parent}'. Use --plane.")

    print(f"Loading {path}")
    print(f"  detector=vd  target plane={plane}")
    frame, channels, _tickinfo, used_tag = _load_frames(path, args.tag)
    print(f"  tag={used_tag}  frame shape={frame.shape}  "
          f"channels {channels.min()}..{channels.max()}")

    plane_data = _split_planes(frame, channels)
    if len(plane_data) != 3:
        sys.exit(f"ERROR: expected 3 planes after split, got {len(plane_data)}.")

    pframe, pchannels = plane_data[PLANE_LABELS.index(plane)]
    rms = float(pframe.std())
    sig_mask = np.abs(pframe).max(axis=1) > args.threshold * rms
    n_sig = int(sig_mask.sum())
    if n_sig == 0:
        sys.exit(f"ERROR: no channels above {args.threshold}*RMS on plane {plane} "
                 f"(RMS={rms:.2f}).")

    sig_channels = pchannels[sig_mask]
    print(f"  Plane {plane}: {len(pchannels)} channels, RMS={rms:.2f}, "
          f"signal channels: {n_sig} ({sig_channels.min()}..{sig_channels.max()})")

    waveform = _aligned_mean_waveform_full(
        frame=pframe, channels=pchannels, ch_sel=sig_channels,
        nticks=2 * args.half_window, half_window=args.half_window,
    )

    print(f"  Mean waveform: length={len(waveform)}, "
          f"peak={waveform[args.half_window]:.2f}, "
          f"abs-max={np.max(np.abs(waveform)):.2f}")

    png_path = args.out or f"{path}.{plane}-waveform.png"
    npy_path = os.path.splitext(png_path)[0] + ".npy"
    np.save(npy_path, waveform)
    print(f"  Saved {npy_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("WARNING: matplotlib not available — skipping PNG.", file=sys.stderr)
        return

    ticks_axis = np.arange(-args.half_window, args.half_window)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(ticks_axis, waveform, lw=1.0)
    ax.axhline(0, color="0.5", lw=0.5)
    ax.axvline(0, color="0.5", lw=0.5, ls="--")
    ax.set_xlabel("Tick (peak-aligned)")
    ax.set_ylabel("Mean ADC")
    ax.set_title(
        f"{base}\nplane {plane}, {n_sig} signal channels "
        f"(threshold = {args.threshold}*RMS = {args.threshold * rms:.1f})"
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=args.dpi)
    print(f"  Saved {png_path}")


if __name__ == "__main__":
    main()
