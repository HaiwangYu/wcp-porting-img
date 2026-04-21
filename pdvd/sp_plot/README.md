# cmd_plot_frames.py — Usage Guide

Draws U, V, W wire-plane views from a WireCell `FrameFileSink` archive (`.tar.bz2`).
Each output is a single PNG with three stacked panels — one per plane.

## Requirements

```
pip install numpy matplotlib
```

## Usage

Run the script directly — no woodpecker installation needed:

```bash
python cmd_plot_frames.py data/protodune-sp-frames-anode2.tar.bz2
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `frame_file` | yes | Path to a `*-anode<N>.tar.bz2` archive |
| `--tag TAG` | no | Frame tag to load (`raw`, `gauss`, `wiener`, …). Defaults to auto-detect. |
| `--out PATH` | no | Output PNG path. Defaults to `<frame_file>.png` beside the input. |
| `--tick-range T0 T1` | no | Restrict displayed ticks to `[T0, T1)` (relative, 0-based). |
| `--zrange ZMIN ZMAX` | no | Fix color-scale range. Otherwise auto-scaled per plane. |
| `--dpi N` | no | Output image resolution (default 150). |

## Examples

```bash
# Basic — auto-detect tag, output next to input file
python cmd_plot_frames.py data/protodune-sp-frames-anode2.tar.bz2

# Explicit tag
python cmd_plot_frames.py data.tar.bz2 --tag raw2

# Custom output path
python cmd_plot_frames.py data.tar.bz2 --out my_frames.png

# Zoom into ticks 1000–3000
python cmd_plot_frames.py data.tar.bz2 --tick-range 1000 3000

# Fix color scale to ±50 ADC
python cmd_plot_frames.py data.tar.bz2 --zrange -50 50

# High-res export
python cmd_plot_frames.py data.tar.bz2 --dpi 300
```

## Input archive format

The archive must contain `.npy` files produced by WireCell's `FrameFileSink`:

| Key pattern | Content |
|---|---|
| `frame_<tag>_<N>.npy` | 2-D array `(nchannels, nticks)` of ADC values |
| `channels_<tag>_<N>.npy` | 1-D array of channel IDs |
| `tickinfo_<tag>_<N>.npy` | `[start_tick, nticks, tick_period]` |
| `chanmask_bad_<N>.npy` | Optional bad-channel mask `(M, 3)` |

The anode index `N` is inferred from the filename (`anode<N>`).

## Color scale logic

| Plane / tag | Color map | Range |
|---|---|---|
| Any `gauss` tag | `hot_r` (white→black) | Fixed `0–1000` |
| W (collection), default | `hot_r` | `0 … 10×plane RMS` |
| U, V (induction), default | `RdBu_r` (blue–white–red) | `±10×plane RMS` |
| Any plane, `--zrange` | `RdBu_r` | User-supplied |

Bad channels are drawn as thin blue vertical lines on each panel.

## Tick axis

The y-axis shows **relative** ticks (0-based index into the stored frame), not the
absolute simulation clock tick. The absolute start tick is printed to stdout but not
shown on the plot, since it is typically a large simulation offset with no visual value.
