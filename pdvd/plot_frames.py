#!/usr/bin/env python3
"""
Plot gauss and wiener 2D frames from protodune-sp-frames-anodeN.tar.bz2 files.

File structure per archive:
  frame_{gauss,wiener}N_XXXXXX.npy  : shape (nchannels, nticks), float32
  channels_{gauss,wiener}N_XXXXXX.npy : shape (nchannels,), int32 — global channel numbers
  tickinfo_{gauss,wiener}N_XXXXXX.npy : shape (3,), float64 — [start_tick, nticks, tick_period_us]
  summary_wienerN_XXXXXX.npy          : shape (nchannels,), float64

Channel layout per APA (3 planes):
  U: 476 channels (induction)
  V: 476 channels (induction)
  W: 584 channels (collection)
  (with gaps in global channel numbering between planes)

Usage:
  python plot_frames.py protodune-sp-frames-anode0.tar.bz2 [--anode 0] [--vmax 500] [--out output.png]
  python plot_frames.py protodune-sp-frames-anode0.tar.bz2 --plane W --filter wiener
"""

import argparse
import io
import os
import re
import tarfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PLANE_LABELS = ["U", "V", "W"]


def load_archive(path):
    """Load all npy arrays from a tar.bz2 archive. Returns dict name->array."""
    data = {}
    with tarfile.open(path, "r:bz2") as tf:
        for member in tf.getmembers():
            if member.name.endswith(".npy"):
                raw = tf.extractfile(member).read()
                arr = np.load(io.BytesIO(raw))
                # strip .npy suffix as key
                key = member.name[:-4]
                data[key] = arr
    return data


def split_planes(frame, channels):
    """
    Split a (nchannels, nticks) frame into 3 planes based on channel gaps.
    Returns list of (plane_frame, plane_channels) for U, V, W order.
    """
    diffs = np.diff(channels)
    gap_idx = np.where(diffs > 1)[0]
    starts = [0] + list(gap_idx + 1)
    ends = list(gap_idx + 1) + [len(channels)]
    planes = []
    for s, e in zip(starts, ends):
        planes.append((frame[s:e], channels[s:e]))
    return planes  # [U, V, W]


def plot_anode(data, anode_id, filters=("gauss", "wiener"), planes=("U", "V", "W"),
               vmax=None, vmin=0, cmap="Blues", out=None, show=False):
    """
    Plot 2D images for selected filters and planes.
    Each subplot: x=channel number, y=time tick.
    """
    plane_sel = [p.upper() for p in planes]
    nrows = len(filters)
    ncols = len(plane_sel)
    if nrows == 0 or ncols == 0:
        print("Nothing to plot.")
        return

    fig, axes = plt.subplots(nrows, ncols,
                              figsize=(6 * ncols, 5 * nrows),
                              squeeze=False)
    fig.suptitle(f"APA anode {anode_id}", fontsize=14)

    for row, filt in enumerate(filters):
        # Find matching keys for this filter
        frame_key = next((k for k in data if k.startswith(f"frame_{filt}{anode_id}_")), None)
        ch_key = next((k for k in data if k.startswith(f"channels_{filt}{anode_id}_")), None)
        ti_key = next((k for k in data if k.startswith(f"tickinfo_{filt}{anode_id}_")), None)

        if frame_key is None:
            for col in range(ncols):
                axes[row][col].set_visible(False)
            continue

        frame = data[frame_key]       # (nch, ntick)
        channels = data[ch_key]       # (nch,)
        tickinfo = data[ti_key]       # [start_tick, ?, tick_period]
        start_tick = int(tickinfo[0])
        nticks = frame.shape[1]
        tick_end = start_tick + nticks

        plane_data = split_planes(frame, channels)

        for col_idx, plane_name in enumerate(plane_sel):
            ax = axes[row][col_idx]
            pframe_idx = PLANE_LABELS.index(plane_name)
            if pframe_idx >= len(plane_data):
                ax.set_visible(False)
                continue
            pframe, pchannels = plane_data[pframe_idx]

            # Determine color scale
            vm = vmax
            if vm is None:
                # use 99th percentile of nonzero values
                nz = pframe[pframe != 0]
                vm = float(np.percentile(nz, 99)) if len(nz) else 1.0

            ch_min, ch_max = pchannels[0], pchannels[-1]

            # imshow: rows=ticks, cols=channels
            # pframe is (nch, ntick) -> transpose to (ntick, nch)
            im = ax.imshow(
                pframe.T,
                aspect="auto",
                origin="lower",
                extent=[ch_min - 0.5, ch_max + 0.5, start_tick, tick_end],
                vmin=vmin,
                vmax=vm,
                cmap=cmap,
                interpolation="none",
            )
            ax.set_title(f"{filt.capitalize()} — Plane {plane_name}  (ch {ch_min}–{ch_max})")
            ax.set_xlabel("Channel number")
            ax.set_ylabel("Time tick")
            plt.colorbar(im, ax=ax, label="ADC")

    plt.tight_layout()

    if out:
        plt.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved: {out}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Plot WireCell frame NPY archives")
    parser.add_argument("archives", nargs="+",
                        help="protodune-sp-frames-anodeN.tar.bz2 file(s)")
    parser.add_argument("--filter", choices=["gauss", "wiener", "both"], default="both",
                        help="Which filter to plot (default: both)")
    parser.add_argument("--plane", choices=["U", "V", "W", "all"], default="all",
                        help="Which plane to plot (default: all)")
    parser.add_argument("--vmax", type=float, default=None,
                        help="Color scale maximum (default: 99th percentile of nonzero)")
    parser.add_argument("--vmin", type=float, default=0,
                        help="Color scale minimum (default: 0)")
    parser.add_argument("--cmap", default="Blues",
                        help="Matplotlib colormap (default: Blues)")
    parser.add_argument("--out", default=None,
                        help="Output filename pattern. Use {anode} as placeholder. "
                             "If not set, saves as frames_anodeN.png next to input.")
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively (requires display)")
    args = parser.parse_args()

    filters = ["gauss", "wiener"] if args.filter == "both" else [args.filter]
    planes = ["U", "V", "W"] if args.plane == "all" else [args.plane]

    for archive_path in args.archives:
        # Extract anode ID from filename
        m = re.search(r"anode(\d+)", os.path.basename(archive_path))
        anode_id = int(m.group(1)) if m else 0

        print(f"Loading {archive_path} ...")
        data = load_archive(archive_path)
        print(f"  Keys: {list(data.keys())}")

        if args.out:
            out_path = args.out.format(anode=anode_id)
        else:
            base = os.path.splitext(os.path.splitext(archive_path)[0])[0]  # strip .tar.bz2
            out_path = base + ".png"

        plot_anode(data, anode_id,
                   filters=filters,
                   planes=planes,
                   vmax=args.vmax,
                   vmin=args.vmin,
                   cmap=args.cmap,
                   out=out_path,
                   show=args.show)


if __name__ == "__main__":
    main()
