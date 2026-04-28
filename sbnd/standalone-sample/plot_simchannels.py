#!/usr/bin/env python
"""Extract sim::SimChannel charge into a dense channel x TDC array."""

from __future__ import print_function

import argparse
import json
import os
import sys

import numpy as np


DEFAULT_BRANCH = "sim::SimChannels_simtpc2d_simpleSC_DetSim.obj"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Read one artROOT event's sim::SimChannel collection, sum IDE "
            "numElectrons per channel/TDC, save a dense 2D NumPy array, and plot it."
        )
    )
    parser.add_argument("--input", default="2025f-mc.root", help="input artROOT file")
    parser.add_argument("--entry", type=int, default=0, help="Events tree entry to read")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="SimChannel obj branch")
    parser.add_argument(
        "--out-prefix",
        default="simchannels_entry0",
        help="output prefix for .npy, .json, and .pdf files",
    )
    parser.add_argument("--channel-min", type=int, default=None, help="minimum channel to include")
    parser.add_argument("--channel-max", type=int, default=None, help="maximum channel to include")
    parser.add_argument("--tdc-min", type=int, default=None, help="minimum TDC to include")
    parser.add_argument("--tdc-max", type=int, default=None, help="maximum TDC to include")
    parser.add_argument("--vmin", type=float, default=None, help="plot color minimum")
    parser.add_argument("--vmax", type=float, default=None, help="plot color maximum")
    parser.add_argument(
        "--cmap",
        default="YlOrRd",
        help="matplotlib color map for the plot; default has low values close to white",
    )
    parser.add_argument(
        "--vmax-percentile",
        type=float,
        default=99.0,
        help="percentile of nonzero charge to use as default plot vmax",
    )
    return parser.parse_args()


def import_root():
    try:
        import ROOT
    except ImportError:
        sys.stderr.write(
            "error: could not import ROOT. Run this inside the configured LArSoft/PyROOT environment.\n"
        )
        raise
    return ROOT


def checked_range(name, low, high):
    if low is not None and high is not None and high < low:
        raise ValueError("%s max %s is smaller than min %s" % (name, high, low))


def event_reader(ROOT, filename, branch_name, entry):
    root_file = ROOT.TFile.Open(filename)
    if not root_file or root_file.IsZombie():
        raise RuntimeError("failed to open input file: %s" % filename)

    tree = root_file.Get("Events")
    if not tree:
        raise RuntimeError("input file has no Events tree: %s" % filename)

    entries = int(tree.GetEntries())
    if entry < 0 or entry >= entries:
        raise RuntimeError("entry %d is outside Events range [0, %d)" % (entry, entries))

    if not tree.GetBranch(branch_name):
        raise RuntimeError("Events tree has no branch: %s" % branch_name)

    reader = ROOT.TTreeReader(tree)
    simchannels = ROOT.TTreeReaderArray("sim::SimChannel")(reader, branch_name)
    for _ in range(entry + 1):
        if not reader.Next():
            raise RuntimeError("failed to read entry %d" % entry)

    return root_file, tree, reader, entries, simchannels


def collect_deposits(simchannels, channel_min, channel_max, tdc_min, tdc_max):
    deposits = []
    channels_seen = []
    nonzero = 0

    for index in range(int(simchannels.GetSize())):
        sim_channel = simchannels.At(index)
        channel = int(sim_channel.Channel())

        if channel_min is not None and channel < channel_min:
            continue
        if channel_max is not None and channel > channel_max:
            continue

        channels_seen.append(channel)
        tdcide_map = sim_channel.TDCIDEMap()
        for map_index in range(int(tdcide_map.size())):
            tdc_info = tdcide_map.at(map_index)
            tdc = int(tdc_info.first)

            if tdc_min is not None and tdc < tdc_min:
                continue
            if tdc_max is not None and tdc > tdc_max:
                continue

            charge = 0.0
            for ide in tdc_info.second:
                charge += float(ide.numElectrons)

            if charge == 0.0:
                continue

            nonzero += 1
            deposits.append((channel, tdc, charge))

    return channels_seen, deposits, nonzero


def choose_axis_range(label, requested_min, requested_max, values):
    if requested_min is None and requested_max is None and not values:
        raise RuntimeError("no %s values found; provide --%s-min/--%s-max" % (label, label, label))

    low = requested_min if requested_min is not None else min(values)
    high = requested_max if requested_max is not None else max(values)
    if high < low:
        raise RuntimeError("%s max %d is smaller than min %d" % (label, high, low))
    return int(low), int(high)


def build_array(channels_seen, deposits, args):
    deposit_channels = [channel for channel, _, _ in deposits]
    deposit_tdcs = [tdc for _, tdc, _ in deposits]

    channel_values = channels_seen or deposit_channels
    channel_min, channel_max = choose_axis_range(
        "channel", args.channel_min, args.channel_max, channel_values
    )
    tdc_min, tdc_max = choose_axis_range("tdc", args.tdc_min, args.tdc_max, deposit_tdcs)

    n_channels = channel_max - channel_min + 1
    n_tdcs = tdc_max - tdc_min + 1
    if n_channels <= 0 or n_tdcs <= 0:
        raise RuntimeError("invalid output shape (%d, %d)" % (n_channels, n_tdcs))

    charge = np.zeros((n_channels, n_tdcs), dtype=np.float32)
    for channel, tdc, value in deposits:
        if channel_min <= channel <= channel_max and tdc_min <= tdc <= tdc_max:
            charge[channel - channel_min, tdc - tdc_min] += value

    return charge, (channel_min, channel_max), (tdc_min, tdc_max)


def plot_array(charge, channel_range, tdc_range, args, plot_name):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nonzero = charge[charge > 0.0]
    vmin = 0.0 if args.vmin is None else args.vmin
    vmax = args.vmax
    if vmax is None and nonzero.size:
        vmax = float(np.percentile(nonzero, args.vmax_percentile))
        if vmax <= 0.0:
            vmax = None

    # Transpose for image coordinates: rows are TDC, columns are channel.
    image = charge.T
    extent = [
        channel_range[0] - 0.5,
        channel_range[1] + 0.5,
        tdc_range[0] - 0.5,
        tdc_range[1] + 0.5,
    ]

    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    mesh = ax.imshow(
        image,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        extent=extent,
        cmap=args.cmap,
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_xlabel("Channel")
    ax.set_ylabel("TDC")
    ax.set_title("SimChannel charge, entry %d" % args.entry)
    colorbar = fig.colorbar(mesh, ax=ax)
    colorbar.set_label("Charge [electrons]")
    fig.savefig(plot_name, dpi=150)
    plt.close(fig)


def write_metadata(json_name, args, entries, charge, channel_range, tdc_range, nonzero_deposits):
    metadata = {
        "input": os.path.abspath(args.input),
        "entry": args.entry,
        "events_entries": entries,
        "branch": args.branch,
        "array_file": os.path.abspath(args.out_prefix + ".npy"),
        "plot_file": os.path.abspath(args.out_prefix + ".pdf"),
        "shape": list(charge.shape),
        "dtype": str(charge.dtype),
        "axis_mapping": {
            "array_shape": "[channel_index, tdc_index]",
            "channel": {
                "axis": 0,
                "min": channel_range[0],
                "max": channel_range[1],
                "value_for_index": "channel = index + channel_min",
            },
            "tdc": {
                "axis": 1,
                "min": tdc_range[0],
                "max": tdc_range[1],
                "value_for_index": "tdc = index + tdc_min",
            },
        },
        "nonzero_deposits": nonzero_deposits,
        "nonzero_array_bins": int(np.count_nonzero(charge)),
        "charge_sum": float(charge.sum(dtype=np.float64)),
    }

    with open(json_name, "w") as stream:
        json.dump(metadata, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    args = parse_args()
    checked_range("channel", args.channel_min, args.channel_max)
    checked_range("tdc", args.tdc_min, args.tdc_max)

    ROOT = import_root()
    root_file, tree, reader, entries, simchannels = event_reader(
        ROOT, args.input, args.branch, args.entry
    )

    print("Opened input: %s" % args.input)
    print("Found Events tree with %d entries" % entries)
    print("Found branch: %s" % args.branch)
    print("Reading entry %d with %d SimChannel objects" % (args.entry, simchannels.GetSize()))

    channels_seen, deposits, nonzero_deposits = collect_deposits(
        simchannels, args.channel_min, args.channel_max, args.tdc_min, args.tdc_max
    )
    charge, channel_range, tdc_range = build_array(channels_seen, deposits, args)

    npy_name = args.out_prefix + ".npy"
    json_name = args.out_prefix + ".json"
    pdf_name = args.out_prefix + ".pdf"

    np.save(npy_name, charge)
    write_metadata(json_name, args, entries, charge, channel_range, tdc_range, nonzero_deposits)
    plot_array(charge, channel_range, tdc_range, args, pdf_name)

    print("Nonzero deposits read: %d" % nonzero_deposits)
    print("Dense array shape: %s [channel, TDC]" % (charge.shape,))
    print("Channel range: %d..%d" % channel_range)
    print("TDC range: %d..%d" % tdc_range)
    for channel, tdc, value in deposits[:5]:
        print("Sample deposit: channel=%d tdc=%d charge=%g" % (channel, tdc, value))
    print("Wrote %s" % npy_name)
    print("Wrote %s" % json_name)
    print("Wrote %s" % pdf_name)

    root_file.Close()


if __name__ == "__main__":
    main()
