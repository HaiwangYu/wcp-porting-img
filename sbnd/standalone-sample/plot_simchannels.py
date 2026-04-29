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
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="open an interactive GUI to inspect one channel waveform at a time",
    )
    parser.add_argument(
        "--initial-channel",
        type=int,
        default=None,
        help="channel to show first in --interactive mode; defaults to first nonzero channel",
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

    if not args.interactive:
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


def first_nonzero_channel(charge, channel_range):
    channel_has_charge = np.any(charge > 0.0, axis=1)
    nonzero_indices = np.flatnonzero(channel_has_charge)
    if nonzero_indices.size:
        return int(channel_range[0] + nonzero_indices[0])
    return int(channel_range[0])


def channel_index_for_value(channel, channel_range):
    if channel < channel_range[0] or channel > channel_range[1]:
        return None
    return int(channel - channel_range[0])


def show_interactive_waveforms(charge, channel_range, tdc_range, args):
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, TextBox

    tdcs = np.arange(tdc_range[0], tdc_range[1] + 1)
    image = charge.T
    extent = [
        channel_range[0] - 0.5,
        channel_range[1] + 0.5,
        tdc_range[0] - 0.5,
        tdc_range[1] + 0.5,
    ]
    nonzero = charge[charge > 0.0]
    vmin = 0.0 if args.vmin is None else args.vmin
    vmax = args.vmax
    if vmax is None and nonzero.size:
        vmax = float(np.percentile(nonzero, args.vmax_percentile))
        if vmax <= 0.0:
            vmax = None

    current_channel = (
        args.initial_channel
        if args.initial_channel is not None
        else first_nonzero_channel(charge, channel_range)
    )
    if channel_index_for_value(current_channel, channel_range) is None:
        sys.stderr.write(
            "warning: initial channel %d is outside loaded range %d..%d; using %d\n"
            % (
                current_channel,
                channel_range[0],
                channel_range[1],
                first_nonzero_channel(charge, channel_range),
            )
        )
        current_channel = first_nonzero_channel(charge, channel_range)

    fig = plt.figure(figsize=(12, 8))
    grid = fig.add_gridspec(3, 1, height_ratios=[3.5, 1.0, 0.75])
    image_ax = fig.add_subplot(grid[0])
    wave_ax = fig.add_subplot(grid[1])
    control_ax = fig.add_subplot(grid[2])
    control_ax.set_axis_off()
    fig.subplots_adjust(left=0.08, right=0.94, top=0.95, bottom=0.06, hspace=0.42)
    mesh = image_ax.imshow(
        image,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        extent=extent,
        cmap=args.cmap,
        vmin=vmin,
        vmax=vmax,
    )
    selected_channel_line = image_ax.axvline(current_channel, color="tab:blue", lw=1.5)
    colorbar = fig.colorbar(mesh, ax=image_ax, pad=0.01)
    colorbar.set_label("Charge [electrons]")
    image_ax.set_title("SimChannel charge, entry %d" % args.entry)
    image_ax.set_xlabel("Channel")
    image_ax.set_ylabel("TDC")

    (line,) = wave_ax.plot([], [], lw=1.2)
    status = control_ax.text(0.08, 0.82, "", fontsize=10, transform=control_ax.transAxes)
    state = {
        "channel": current_channel,
        "channel_min": channel_range[0],
        "channel_max": channel_range[1],
        "tdc_min": tdc_range[0],
        "tdc_max": tdc_range[1],
    }

    def set_textbox_value(widget, value):
        widget.eventson = False
        widget.set_val(str(value))
        widget.eventson = True

    def visible_tdc_slice():
        start = state["tdc_min"] - tdc_range[0]
        stop = state["tdc_max"] - tdc_range[0] + 1
        return slice(start, stop)

    def set_channel_range(channel_min, channel_max):
        if channel_min > channel_max:
            status.set_text("Channel min must be <= channel max.")
            fig.canvas.draw_idle()
            return
        if channel_max < channel_range[0] or channel_min > channel_range[1]:
            status.set_text(
                "Channel range must overlap loaded range %d..%d" % channel_range
            )
            fig.canvas.draw_idle()
            return

        state["channel_min"] = max(channel_range[0], channel_min)
        state["channel_max"] = min(channel_range[1], channel_max)
        set_textbox_value(channel_min_box, state["channel_min"])
        set_textbox_value(channel_max_box, state["channel_max"])
        image_ax.set_xlim(state["channel_min"] - 0.5, state["channel_max"] + 0.5)

        channel = state["channel"]
        if channel < state["channel_min"]:
            channel = state["channel_min"]
        if channel > state["channel_max"]:
            channel = state["channel_max"]
        set_channel(channel)

    def set_tdc_range(tdc_min, tdc_max):
        if tdc_min > tdc_max:
            status.set_text("TDC min must be <= TDC max.")
            fig.canvas.draw_idle()
            return
        if tdc_max < tdc_range[0] or tdc_min > tdc_range[1]:
            status.set_text(
                "TDC range must overlap loaded range %d..%d" % tdc_range
            )
            fig.canvas.draw_idle()
            return

        state["tdc_min"] = max(tdc_range[0], tdc_min)
        state["tdc_max"] = min(tdc_range[1], tdc_max)
        set_textbox_value(tdc_min_box, state["tdc_min"])
        set_textbox_value(tdc_max_box, state["tdc_max"])
        image_ax.set_ylim(state["tdc_min"] - 0.5, state["tdc_max"] + 0.5)
        set_channel(state["channel"])

    def set_channel(channel):
        index = channel_index_for_value(channel, channel_range)
        if index is None:
            status.set_text(
                "Channel %d is outside loaded range %d..%d"
                % (channel, channel_range[0], channel_range[1])
            )
            fig.canvas.draw_idle()
            return

        waveform = charge[index]
        visible_waveform = waveform[visible_tdc_slice()]
        nonzero_bins = int(np.count_nonzero(visible_waveform))
        charge_sum = float(visible_waveform.sum(dtype=np.float64))

        line.set_data(tdcs, waveform)
        wave_ax.set_xlim(state["tdc_min"], state["tdc_max"])
        ymax = float(visible_waveform.max()) if visible_waveform.size else 0.0
        if ymax > 0.0:
            wave_ax.set_ylim(0.0, ymax * 1.08)
        else:
            wave_ax.set_ylim(0.0, 1.0)

        selected_channel_line.set_xdata([channel, channel])
        wave_ax.set_title("SimChannel waveform, entry %d, channel %d" % (args.entry, channel))
        wave_ax.set_xlabel("TDC")
        wave_ax.set_ylabel("Charge [electrons]")
        status.set_text(
            "Channel %d    visible channels: %d..%d    visible TDC: %d..%d    nonzero bins: %d    summed charge: %.6g"
            % (
                channel,
                state["channel_min"],
                state["channel_max"],
                state["tdc_min"],
                state["tdc_max"],
                nonzero_bins,
                charge_sum,
            )
        )
        state["channel"] = channel
        set_textbox_value(channel_box, channel)
        fig.canvas.draw_idle()

    def click_image(event):
        if event.inaxes is not image_ax or event.xdata is None:
            return
        channel = int(round(event.xdata))
        if channel < channel_range[0]:
            channel = channel_range[0]
        if channel > channel_range[1]:
            channel = channel_range[1]
        set_channel(channel)

    def submit_channel(text):
        try:
            channel = int(text.strip())
        except ValueError:
            status.set_text("Enter an integer channel number.")
            fig.canvas.draw_idle()
            return
        set_channel(channel)

    def submit_channel_range(_text):
        try:
            channel_min = int(channel_min_box.text.strip())
            channel_max = int(channel_max_box.text.strip())
        except ValueError:
            status.set_text("Enter integer channel min and max values.")
            fig.canvas.draw_idle()
            return
        set_channel_range(channel_min, channel_max)

    def submit_tdc_range(_text):
        try:
            tdc_min = int(tdc_min_box.text.strip())
            tdc_max = int(tdc_max_box.text.strip())
        except ValueError:
            status.set_text("Enter integer TDC min and max values.")
            fig.canvas.draw_idle()
            return
        set_tdc_range(tdc_min, tdc_max)

    def step_channel(delta):
        try:
            channel = int(channel_box.text.strip()) + delta
        except ValueError:
            channel = state["channel"] + delta
        if channel < state["channel_min"]:
            channel = state["channel_min"]
        if channel > state["channel_max"]:
            channel = state["channel_max"]
        set_channel(channel)

    def reset_channel_range(_event):
        set_channel_range(channel_range[0], channel_range[1])

    def reset_tdc_range(_event):
        set_tdc_range(tdc_range[0], tdc_range[1])

    image_ax.set_xlim(state["channel_min"] - 0.5, state["channel_max"] + 0.5)
    image_ax.set_ylim(state["tdc_min"] - 0.5, state["tdc_max"] + 0.5)

    channel_ax = control_ax.inset_axes([0.08, 0.46, 0.18, 0.27])
    channel_box = TextBox(channel_ax, "Channel ")
    channel_box.on_submit(submit_channel)

    channel_min_ax = control_ax.inset_axes([0.08, 0.08, 0.16, 0.27])
    channel_max_ax = control_ax.inset_axes([0.32, 0.08, 0.16, 0.27])
    channel_min_box = TextBox(channel_min_ax, "Ch min ")
    channel_max_box = TextBox(channel_max_ax, "Ch max ")
    channel_min_box.on_submit(submit_channel_range)
    channel_max_box.on_submit(submit_channel_range)

    tdc_min_ax = control_ax.inset_axes([0.58, 0.08, 0.15, 0.27])
    tdc_max_ax = control_ax.inset_axes([0.82, 0.08, 0.15, 0.27])
    tdc_min_box = TextBox(tdc_min_ax, "TDC min ")
    tdc_max_box = TextBox(tdc_max_ax, "TDC max ")
    tdc_min_box.on_submit(submit_tdc_range)
    tdc_max_box.on_submit(submit_tdc_range)

    prev_ax = control_ax.inset_axes([0.32, 0.46, 0.10, 0.27])
    next_ax = control_ax.inset_axes([0.44, 0.46, 0.10, 0.27])
    reset_channel_ax = control_ax.inset_axes([0.58, 0.46, 0.16, 0.27])
    reset_tdc_ax = control_ax.inset_axes([0.78, 0.46, 0.13, 0.27])
    prev_button = Button(prev_ax, "Previous")
    next_button = Button(next_ax, "Next")
    reset_channel_button = Button(reset_channel_ax, "Full Channel")
    reset_tdc_button = Button(reset_tdc_ax, "Full TDC")
    prev_button.on_clicked(lambda event: step_channel(-1))
    next_button.on_clicked(lambda event: step_channel(1))
    reset_channel_button.on_clicked(reset_channel_range)
    reset_tdc_button.on_clicked(reset_tdc_range)
    click_connection = fig.canvas.mpl_connect("button_press_event", click_image)

    # Keep widget objects alive for interactive backends.
    fig._simchannel_widgets = (
        channel_box,
        channel_min_box,
        channel_max_box,
        tdc_min_box,
        tdc_max_box,
        prev_button,
        next_button,
        reset_channel_button,
        reset_tdc_button,
        click_connection,
    )

    set_textbox_value(channel_min_box, state["channel_min"])
    set_textbox_value(channel_max_box, state["channel_max"])
    set_textbox_value(tdc_min_box, state["tdc_min"])
    set_textbox_value(tdc_max_box, state["tdc_max"])
    set_channel(current_channel)
    plt.show()


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

    if args.interactive:
        print("Opening interactive waveform viewer")
        show_interactive_waveforms(charge, channel_range, tdc_range, args)

    root_file.Close()


if __name__ == "__main__":
    main()
