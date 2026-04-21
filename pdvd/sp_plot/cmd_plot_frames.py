"""CLI subcommand: woodpecker plot-frames

Draw U, V, W wire plane views from a FrameFileSink tar.bz2 archive.
Works with any tag (gauss, wiener, raw, orig, ...).

Usage
-----
  woodpecker plot-frames woodpecker_data/protodune-sp-frames-sim-anode2.tar.bz2
  woodpecker plot-frames data.tar.bz2 --tag raw2
  woodpecker plot-frames data.tar.bz2 --out frames.png
  woodpecker plot-frames data.tar.bz2 --tick-range 1000 3000
  woodpecker plot-frames data.tar.bz2 --zrange -50 50
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import tarfile

import numpy as np


def add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "plot-frames",
        help="Draw U/V/W wire plane views from a FrameFileSink tar.bz2",
    )
    p.add_argument("frame_file", help="Path to *-anode<N>.tar.bz2")
    p.add_argument(
        "--tag", default=None,
        help="Frame tag to load (default: auto-detect first available tag)",
    )
    p.add_argument(
        "--out", default=None,
        help="Output image path (default: <frame_file>.png)",
    )
    p.add_argument(
        "--tick-range", nargs=2, type=int, default=None, metavar=("T0", "T1"),
        help="Tick range to display (default: full range)",
    )
    p.add_argument(
        "--zrange", nargs=2, type=float, default=None, metavar=("ZMIN", "ZMAX"),
        help="Color scale range (default: symmetric ±3*RMS)",
    )
    p.add_argument(
        "--dpi", type=int, default=150,
        help="Output image DPI (default: 150)",
    )
    p.set_defaults(func=run)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_archive(path: str) -> dict:
    """Return dict of name-without-.npy → ndarray for every .npy in archive."""
    data = {}
    with tarfile.open(path, "r:bz2") as tf:
        for member in tf.getmembers():
            if member.name.endswith(".npy"):
                raw = tf.extractfile(member).read()
                data[member.name[:-4]] = np.load(io.BytesIO(raw))
    return data


def _find_tag(raw_data: dict, requested_tag: str | None, anode_id: int) -> str:
    """Return the best matching frame tag."""
    frame_keys = [k for k in raw_data if k.startswith("frame_")]
    if not frame_keys:
        raise ValueError(f"No frame_* keys found. Available: {list(raw_data)[:10]}")

    # Extract all available tags
    tag_re = re.compile(r"^frame_(.+)_\d+$")
    available = []
    for k in frame_keys:
        m = tag_re.match(k)
        if m:
            available.append(m.group(1))

    if requested_tag:
        if requested_tag in available:
            return requested_tag
        raise ValueError(f"Tag '{requested_tag}' not found. Available: {available}")

    # Auto-detect: prefer raw > gauss > wiener > * > first available
    for preferred in [f"raw{anode_id}", "raw", f"gauss{anode_id}", "gauss",
                      f"wiener{anode_id}", "wiener", "*"]:
        if preferred in available:
            return preferred

    return available[0]


def _split_planes(frame: np.ndarray, channels: np.ndarray):
    """Split (nch, ntick) into [(frame_U,ch_U), (frame_V,ch_V), (frame_W,ch_W)]."""
    diffs = np.diff(channels)
    gap_idx = list(np.where(diffs > 1)[0])
    starts = [0] + [i + 1 for i in gap_idx]
    ends = [i + 1 for i in gap_idx] + [len(channels)]
    return [(frame[s:e], channels[s:e]) for s, e in zip(starts, ends)]


# ── main ──────────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import TwoSlopeNorm
    except ImportError:
        print("ERROR: matplotlib is required. Install with: pip install matplotlib",
              file=sys.stderr)
        sys.exit(1)

    path = args.frame_file
    if not os.path.exists(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {path} ...")
    raw_data = _load_archive(path)
    print(f"  Keys found: {sorted(raw_data)}")

    m = re.search(r"anode(\d+)", os.path.basename(path))
    anode_id = int(m.group(1)) if m else 0

    tag = _find_tag(raw_data, args.tag, anode_id)
    print(f"  Using tag: {tag}")

    frame_key = next((k for k in raw_data if k.startswith(f"frame_{tag}_")), None)
    ch_key    = next((k for k in raw_data if k.startswith(f"channels_{tag}_")), None)
    ti_key    = next((k for k in raw_data if k.startswith(f"tickinfo_{tag}_")), None)
    bad_key   = next((k for k in raw_data if k.startswith("chanmask_bad_")), None)

    if frame_key is None:
        print(f"ERROR: frame_{tag}_* not found. Available: {sorted(raw_data)}",
              file=sys.stderr)
        sys.exit(1)

    frame    = raw_data[frame_key].astype(np.float32)
    channels = raw_data[ch_key]
    tickinfo = raw_data[ti_key] if ti_key else np.array([0, frame.shape[1], 0.5])

    # Bad channel mask: shape (N, 3) → columns [channel, tick_start, tick_end]
    bad_channels: set[int] = set()
    if bad_key is not None:
        bad_mask = raw_data[bad_key]
        bad_channels = set(int(r[0]) for r in bad_mask)
        print(f"  Bad channels ({len(bad_channels)}): {sorted(bad_channels)}")

    start_tick = int(tickinfo[0])
    nticks = frame.shape[1]
    # Use relative ticks (0-based index) for display — absolute start_tick is
    # a simulation clock offset and not meaningful for visual inspection.
    ticks = np.arange(nticks)

    # Tick range selection (relative indices)
    if args.tick_range:
        t0, t1 = args.tick_range
        i0 = max(0, t0)
        i1 = min(nticks, t1)
        frame = frame[:, i0:i1]
        ticks = ticks[i0:i1]

    planes = _split_planes(frame, channels)
    plane_labels = ["U", "V", "W"]
    # pad to 3 if fewer splits
    while len(planes) < 3:
        planes.append((np.zeros((1, frame.shape[1])), np.array([0])))

    # Global RMS from all non-zero samples (used when --zrange not given)
    global_rms = float(np.std(frame[frame != 0])) if np.any(frame != 0) else 1.0

    print(f"  Anode {anode_id}, tag={tag}, "
          f"relative ticks={ticks[0]}..{ticks[-1]} (abs start={start_tick}), "
          f"channels={channels[0]}..{channels[-1]}, "
          f"global RMS={global_rms:.1f}")

    fig, axes = plt.subplots(3, 1, figsize=(10, 18), sharex=False)
    fig.suptitle(f"{os.path.basename(path)}  |  tag={tag}  |  anode{anode_id}",
                 fontsize=11)

    for ax, (pframe, pch), label in zip(axes, planes[:3], plane_labels):
        if pframe.shape[0] == 0:
            ax.set_title(f"Plane {label} — no channels")
            continue

        # Per-plane color scale
        if "gauss" in tag:
            # Gauss tag: fixed 0..1000, white at 0
            vmin, vmax = 0.0, 1000.0
            norm = None
            cmap = "hot_r"  # white at low end (0), dark at high end
        elif args.zrange:
            vmin, vmax = args.zrange
            norm = TwoSlopeNorm(vcenter=0, vmin=vmin, vmax=vmax)
            cmap = "RdBu_r"
        else:
            plane_rms = float(np.std(pframe[pframe != 0])) if np.any(pframe != 0) else global_rms
            if label == "W":
                # Collection plane: unipolar (positive signal), use 0..10*RMS
                vmin, vmax = 0.0, 10 * plane_rms
                norm = None
                cmap = "hot_r"  # white at 0
            else:
                # Induction planes: bipolar, use ±10*RMS
                vmin, vmax = -10 * plane_rms, 10 * plane_rms
                norm = TwoSlopeNorm(vcenter=0, vmin=vmin, vmax=vmax)
                cmap = "RdBu_r"
            print(f"  Plane {label}: RMS={plane_rms:.1f}, range=[{vmin:.1f}, {vmax:.1f}]")

        # pframe shape: (nch, ntick) — transpose so x=channel, y=tick
        im = ax.imshow(
            pframe.T,
            aspect="auto",
            origin="lower",
            interpolation="none",
            norm=norm,
            vmin=vmin if norm is None else None,
            vmax=vmax if norm is None else None,
            cmap=cmap,
            extent=[pch[0], pch[-1], ticks[0], ticks[-1]],
        )
        # Overlay bad channels as vertical lines
        plane_bad = [ch for ch in bad_channels if pch[0] <= ch <= pch[-1]]
        for bch in plane_bad:
            ax.axvline(x=bch, color="blue", linewidth=0.6, alpha=0.8)
        bad_label = f"  [{len(plane_bad)} bad ch]" if plane_bad else ""
        ax.set_title(f"Plane {label}  (ch {pch[0]}–{pch[-1]},  {pframe.shape[0]} wires){bad_label}")
        ax.set_xlabel("Channel")
        ax.set_ylabel("Tick")
        fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)

    axes[-1].set_xlabel("Channel")
    plt.tight_layout()

    # Strip all extensions (e.g. .tar.bz2) then add .png
    base = os.path.basename(path)
    for ext in (".tar.bz2", ".tar.gz", ".bz2", ".gz"):
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    else:
        base = os.path.splitext(base)[0]
    out_path = args.out or os.path.join(os.path.dirname(path) or ".", base + ".png")
    plt.savefig(out_path, dpi=args.dpi, bbox_inches="tight")
    plt.close()
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Draw U/V/W wire plane views from a FrameFileSink tar.bz2"
    )
    parser.add_argument("frame_file", help="Path to *-anode<N>.tar.bz2")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--tick-range", nargs=2, type=int, default=None, metavar=("T0", "T1"))
    parser.add_argument("--zrange", nargs=2, type=float, default=None, metavar=("ZMIN", "ZMAX"))
    parser.add_argument("--dpi", type=int, default=150)
    run(parser.parse_args())
