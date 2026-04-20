#!/usr/bin/env python3
# Run with: python3 select_frames.py <archive>  (PYTHONPATH set via .envrc)
"""
Interactive UI for selecting time tick range and per-plane channel ranges
from gauss 2D frame histograms.

Selection workflow (4 sequential steps):
  Step 1 — Tick range  : drag UP/DOWN on any plot  (all 3 plots active)
  Step 2 — U channels  : drag LEFT/RIGHT on plane U only
  Step 3 — V channels  : drag LEFT/RIGHT on plane V only
  Step 4 — W channels  : drag LEFT/RIGHT on plane W only

  Press ENTER to confirm each step and advance to the next.
  Once all 4 steps are done the final selection is printed and the
  [Save] button becomes active.

  Clicking [Save] writes a new tar.bz2 with the same file/array
  structure as the original.  Unselected regions are zeroed out;
  all array shapes and dtypes are preserved so the file is a
  drop-in replacement for img.jsonnet.

  Press 'r' at any time to restart from Step 1.

Usage:
  python select_frames.py protodune-sp-frames-anode0.tar.bz2
  python select_frames.py protodune-sp-frames-anode0.tar.bz2 --vmax 1000
  python select_frames.py protodune-sp-frames-anode0.tar.bz2 --out my_output.tar.bz2
"""

import argparse
import io
import os
import re
import sys
import tarfile
import time

import matplotlib
matplotlib.use("QtAgg")  # requires PyQt6 or PySide6
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.widgets import SpanSelector, Button
import numpy as np


PLANE_LABELS = ["U", "V", "W"]

# Step definitions: (label, description, span_direction, active_plane_indices)
STEPS = [
    ("Step 1/4", "Select TICK range — drag UP/DOWN on any plot",        "vertical",   [0, 1, 2]),
    ("Step 2/4", "Select U channel range — drag LEFT/RIGHT on plane U", "horizontal", [0]),
    ("Step 3/4", "Select V channel range — drag LEFT/RIGHT on plane V", "horizontal", [1]),
    ("Step 4/4", "Select W channel range — drag LEFT/RIGHT on plane W", "horizontal", [2]),
]

STEP_COLORS = ["orange", "royalblue", "forestgreen", "crimson"]


# ── data loading ──────────────────────────────────────────────────────────────

def load_archive(path):
    """Return dict of basename-without-npy -> ndarray for every .npy in the archive."""
    data = {}
    with tarfile.open(path, "r:bz2") as tf:
        for member in tf.getmembers():
            if member.name.endswith(".npy"):
                raw = tf.extractfile(member).read()
                data[member.name[:-4]] = np.load(io.BytesIO(raw))
    return data


def split_planes(frame, channels):
    """Split (nch, ntick) frame into [(frame_U,ch_U), (frame_V,ch_V), (frame_W,ch_W)]."""
    diffs = np.diff(channels)
    gap_idx = np.where(diffs > 1)[0]
    starts = [0] + list(gap_idx + 1)
    ends = list(gap_idx + 1) + [len(channels)]
    return [(frame[s:e], channels[s:e]) for s, e in zip(starts, ends)]


# ── save logic ────────────────────────────────────────────────────────────────

def npy_bytes(arr):
    """Serialise a numpy array to bytes (npy format)."""
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def save_masked_archive(src_path, out_path, anode_id, data,
                        tick_range, ch_ranges, plane_channels_list):
    """
    Write a new tar.bz2 that mirrors src_path exactly, but with frame data
    outside the selected tick / channel ranges zeroed out.

    tick_range  : (tick_min, tick_max)  — absolute tick values
    ch_ranges   : [(u_min, u_max), (v_min, v_max), (w_min, w_max)]
    """
    t0, t1 = tick_range

    # Build a boolean mask over the full (nch, ntick) shape for each filter.
    # We work in array-index space (row=channel-index, col=tick-index).
    def build_mask(frame, channels, start_tick):
        mask = np.zeros(frame.shape, dtype=bool)
        nticks = frame.shape[1]

        # tick columns to keep
        col_lo = max(0, t0 - start_tick)
        col_hi = min(nticks, t1 - start_tick + 1)

        for plane_idx, (pch_lo, pch_hi) in enumerate(ch_ranges):
            pch = plane_channels_list[plane_idx]
            row_mask = (channels >= pch_lo) & (channels <= pch_hi)
            row_indices = np.where(row_mask)[0]
            if len(row_indices) == 0:
                continue
            mask[row_indices[:, None],
                 np.arange(col_lo, col_hi)[None, :]] = True
        return mask

    # Collect the modified arrays keyed by member name (without .npy)
    modified = {}
    for key, arr in data.items():
        if not key.startswith("frame_"):
            modified[key] = arr          # channels / tickinfo / summary unchanged
            continue
        # determine filter tag and start_tick for this frame
        if f"gauss{anode_id}" in key:
            ti_key = next(k for k in data if k.startswith(f"tickinfo_gauss{anode_id}_"))
            ch_key = next(k for k in data if k.startswith(f"channels_gauss{anode_id}_"))
        else:
            ti_key = next(k for k in data if k.startswith(f"tickinfo_wiener{anode_id}_"))
            ch_key = next(k for k in data if k.startswith(f"channels_wiener{anode_id}_"))

        start_tick = int(data[ti_key][0])
        channels   = data[ch_key]

        mask = build_mask(arr, channels, start_tick)
        new_frame = np.where(mask, arr, np.float32(0))
        modified[key] = new_frame

    # Write the new archive, preserving member ordering from the original
    with tarfile.open(src_path, "r:bz2") as src_tf:
        orig_members = src_tf.getmembers()

    with tarfile.open(out_path, "w:bz2") as out_tf:
        for orig_m in orig_members:
            key = orig_m.name[:-4]          # strip .npy
            raw = npy_bytes(modified[key])

            info = tarfile.TarInfo(name=orig_m.name)
            info.size  = len(raw)
            info.mode  = orig_m.mode
            info.mtime = int(time.time())
            info.type  = tarfile.REGTYPE
            out_tf.addfile(info, io.BytesIO(raw))

    print(f"Saved: {out_path}")


# ── overlay helpers ───────────────────────────────────────────────────────────

def clear_overlays(ax, tag):
    for patch in list(ax.patches):
        if getattr(patch, "_overlay_tag", None) == tag:
            patch.remove()


def draw_hband(ax, ymin, ymax, color, tag, alpha=0.25):
    clear_overlays(ax, tag)
    xlim = ax.get_xlim()
    p = mpatches.Rectangle(
        (xlim[0], ymin), xlim[1] - xlim[0], ymax - ymin,
        color=color, alpha=alpha, zorder=3
    )
    p._overlay_tag = tag
    ax.add_patch(p)


def draw_vband(ax, xmin, xmax, color, tag, alpha=0.25):
    clear_overlays(ax, tag)
    ylim = ax.get_ylim()
    p = mpatches.Rectangle(
        (xmin, ylim[0]), xmax - xmin, ylim[1] - ylim[0],
        color=color, alpha=alpha, zorder=3
    )
    p._overlay_tag = tag
    ax.add_patch(p)


# ── main UI ───────────────────────────────────────────────────────────────────

def run_ui(archive_path, out_path=None, vmax=None, vmin=0, cmap="Blues"):
    print(f"Loading {archive_path} ...")
    data = load_archive(archive_path)

    m = re.search(r"anode(\d+)", os.path.basename(archive_path))
    anode_id = int(m.group(1)) if m else 0

    frame_key = next((k for k in data if k.startswith(f"frame_gauss{anode_id}_")), None)
    ch_key    = next((k for k in data if k.startswith(f"channels_gauss{anode_id}_")), None)
    ti_key    = next((k for k in data if k.startswith(f"tickinfo_gauss{anode_id}_")), None)

    if frame_key is None:
        print("ERROR: No gauss frame found in archive.")
        sys.exit(1)

    frame      = data[frame_key]
    channels   = data[ch_key]
    tickinfo   = data[ti_key]
    start_tick = int(tickinfo[0])
    nticks     = frame.shape[1]
    end_tick   = start_tick + nticks - 1

    plane_data          = split_planes(frame, channels)
    plane_channels_list = [pch for _, pch in plane_data]

    sel = {
        "tick": None,        # (min, max) once confirmed
        "ch":   [None, None, None],
    }

    # default output path
    if out_path is None:
        base = os.path.splitext(os.path.splitext(archive_path)[0])[0]
        out_path = base + "-selected.tar.bz2"

    # ── build figure ──────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(19, 8))

    # Reserve space: plots top, button + bars bottom
    # axes for the 3 plots
    ax_h = 0.68
    ax_y = 0.18
    axes = [
        fig.add_axes([0.04 + i * 0.32, ax_y, 0.28, ax_h])
        for i in range(3)
    ]

    # instruction bar
    instr_ax = fig.add_axes([0.01, 0.91, 0.98, 0.05])
    instr_ax.axis("off")
    instr_text = instr_ax.text(
        0.5, 0.5, "",
        transform=instr_ax.transAxes,
        fontsize=11, ha="center", va="center",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.9),
    )

    # summary bar
    summary_ax = fig.add_axes([0.01, 0.10, 0.78, 0.06])
    summary_ax.axis("off")
    summary_text = summary_ax.text(
        0.01, 0.5, "— no selection yet —",
        transform=summary_ax.transAxes,
        fontsize=9, va="center", family="monospace",
        bbox=dict(boxstyle="round", facecolor="#e8f4e8", alpha=0.8),
    )

    # Save button
    btn_ax = fig.add_axes([0.82, 0.10, 0.15, 0.06])
    save_btn = Button(btn_ax, "Save selection", color="0.85", hovercolor="lightgreen")
    save_btn.label.set_fontsize(11)
    btn_ax.set_visible(False)   # hidden until all steps done

    fig.suptitle(f"APA anode {anode_id} — Gauss frames", fontsize=13, y=0.98)

    # draw images
    for col, (plane_name, (pframe, pchannels)) in enumerate(zip(PLANE_LABELS, plane_data)):
        ax = axes[col]
        ch_min, ch_max = pchannels[0], pchannels[-1]
        vm = vmax
        if vm is None:
            nz = pframe[pframe != 0]
            vm = float(np.percentile(nz, 99)) if len(nz) else 1.0
        im = ax.imshow(
            pframe.T,
            aspect="auto", origin="lower",
            extent=[ch_min - 0.5, ch_max + 0.5, start_tick, end_tick + 1],
            vmin=vmin, vmax=vm, cmap=cmap, interpolation="none",
        )
        ax.set_title(f"Plane {plane_name}  (ch {ch_min}–{ch_max})")
        ax.set_xlabel("Channel number")
        ax.set_ylabel("Time tick")
        fig.colorbar(im, ax=ax, label="ADC")

    # ── step machine ──────────────────────────────────────────────────────────
    step_state = {"current": 0, "pending": None}
    span_refs  = []

    def update_instruction():
        idx = step_state["current"]
        label, desc, _, active = STEPS[idx]
        color = STEP_COLORS[idx]
        for i, ax in enumerate(axes):
            for spine in ax.spines.values():
                spine.set_linewidth(3 if i in active else 0.8)
                spine.set_edgecolor(color if i in active else "gray")
        instr_text.set_text(f"{label}:  {desc}    [press ENTER to confirm]")
        instr_text.set_bbox(dict(boxstyle="round", facecolor=color, alpha=0.3))
        fig.canvas.draw_idle()

    def update_summary():
        parts = []
        if sel["tick"]:
            t0, t1 = sel["tick"]
            parts.append(f"Ticks: {t0}–{t1} (n={t1-t0+1})")
        else:
            parts.append("Ticks: (not set)")
        for i, label in enumerate(PLANE_LABELS):
            if sel["ch"][i]:
                c0, c1 = sel["ch"][i]
                pch = plane_channels_list[i]
                n = int(((pch >= c0) & (pch <= c1)).sum())
                parts.append(f"Plane {label}: ch {c0}–{c1} (n={n})")
            else:
                parts.append(f"Plane {label}: (not set)")
        summary_text.set_text("   |   ".join(parts))
        fig.canvas.draw_idle()

    def print_final():
        print("\n" + "=" * 55)
        print("=== Final Selection ===")
        t0, t1 = sel["tick"] if sel["tick"] else (start_tick, end_tick)
        print(f"Tick range : {t0} – {t1}  (n={t1-t0+1})")
        print(f"Tick array : {list(range(t0, min(t0+5, t1+1)))}{'...' if t1-t0>=4 else ''}")
        for i, (label, pch) in enumerate(zip(PLANE_LABELS, plane_channels_list)):
            c0, c1 = sel["ch"][i] if sel["ch"][i] else (int(pch[0]), int(pch[-1]))
            chosen = pch[(pch >= c0) & (pch <= c1)]
            print(f"Plane {label} ch  : {c0} – {c1}  (n={len(chosen)})"
                  f"  first5={chosen[:5].tolist()}")
        print("=" * 55 + "\n")
        print(f"Click [Save selection] to write  {out_path}")

    def on_save(_event):
        tick_range = sel["tick"] if sel["tick"] else (start_tick, end_tick)
        ch_ranges  = []
        for i, pch in enumerate(plane_channels_list):
            if sel["ch"][i]:
                ch_ranges.append(sel["ch"][i])
            else:
                ch_ranges.append((int(pch[0]), int(pch[-1])))
        print(f"\nSaving to {out_path} ...")
        save_masked_archive(
            archive_path, out_path, anode_id, data,
            tick_range, ch_ranges, plane_channels_list,
        )
        # update button label to confirm
        save_btn.label.set_text(f"Saved → {os.path.basename(out_path)}")
        save_btn.color = "lightgreen"
        fig.canvas.draw_idle()

    save_btn.on_clicked(on_save)

    # ── SpanSelectors ─────────────────────────────────────────────────────────
    def make_spans(step_idx):
        for sp in span_refs:
            sp.set_active(False)
        span_refs.clear()

        _, _, direction, active_planes = STEPS[step_idx]
        color = STEP_COLORS[step_idx]

        def on_select(vmin_sel, vmax_sel):
            step_state["pending"] = (vmin_sel, vmax_sel)
            if step_idx == 0:
                for ax in axes:
                    draw_hband(ax, vmin_sel, vmax_sel, color, "tick_preview")
            else:
                pi = active_planes[0]
                draw_vband(axes[pi], vmin_sel, vmax_sel, color, f"ch_preview_{pi}")
            fig.canvas.draw_idle()

        for pi in active_planes:
            sp = SpanSelector(
                axes[pi], on_select, direction=direction,
                useblit=True,
                props=dict(alpha=0.3, facecolor=color),
                interactive=True,
                drag_from_anywhere=False,
            )
            span_refs.append(sp)

    def confirm_step():
        idx     = step_state["current"]
        pending = step_state["pending"]

        if pending is not None:
            vlo, vhi = pending
            if idx == 0:
                sel["tick"] = (int(vlo), int(vhi))
                for ax in axes:
                    clear_overlays(ax, "tick_preview")
                    draw_hband(ax, vlo, vhi, STEP_COLORS[0], "tick_final", alpha=0.18)
            else:
                pi = STEPS[idx][3][0]
                sel["ch"][pi] = (int(vlo), int(vhi))
                clear_overlays(axes[pi], f"ch_preview_{pi}")
                draw_vband(axes[pi], vlo, vhi,
                           STEP_COLORS[idx], f"ch_final_{pi}", alpha=0.22)
        else:
            print(f"  ({STEPS[idx][0]}: no drag made, step skipped)")

        step_state["pending"] = None
        update_summary()

        next_idx = idx + 1
        if next_idx >= len(STEPS):
            # all done
            for sp in span_refs:
                sp.set_active(False)
            instr_text.set_text("✓ All selections done! — Click [Save selection] or press 'r' to redo")
            instr_text.set_bbox(dict(boxstyle="round", facecolor="lightgreen", alpha=0.6))
            for ax in axes:
                for spine in ax.spines.values():
                    spine.set_linewidth(1)
                    spine.set_edgecolor("gray")
            btn_ax.set_visible(True)
            fig.canvas.draw_idle()
            print_final()
        else:
            step_state["current"] = next_idx
            make_spans(next_idx)
            update_instruction()

    def reset_all():
        sel["tick"]   = None
        sel["ch"]     = [None, None, None]
        step_state["current"] = 0
        step_state["pending"] = None
        btn_ax.set_visible(False)
        save_btn.label.set_text("Save selection")
        for ax in axes:
            for tag in ["tick_preview", "tick_final",
                        "ch_preview_0", "ch_final_0",
                        "ch_preview_1", "ch_final_1",
                        "ch_preview_2", "ch_final_2"]:
                clear_overlays(ax, tag)
        make_spans(0)
        update_instruction()
        update_summary()
        print("Selection reset — back to Step 1.")

    def on_key(event):
        if event.key in ("enter", "return"):
            confirm_step()
        elif event.key == "r":
            reset_all()

    fig.canvas.mpl_connect("key_press_event", on_key)

    make_spans(0)
    update_instruction()
    update_summary()

    print("\nUI ready.")
    print("  Step 1 — drag UP/DOWN   on any plot → tick range")
    print("  Step 2 — drag LEFT/RIGHT on plane U → U channel range")
    print("  Step 3 — drag LEFT/RIGHT on plane V → V channel range")
    print("  Step 4 — drag LEFT/RIGHT on plane W → W channel range")
    print("  Press ENTER after each step to confirm and advance")
    print("  Press 'r' to reset | Click [Save selection] when done\n")

    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Interactive step-by-step selection UI for WireCell gauss frames")
    parser.add_argument("archive", help="protodune-sp-frames-anodeN.tar.bz2 file")
    parser.add_argument("--out", default=None,
                        help="Output tar.bz2 path (default: <input>-selected.tar.bz2)")
    parser.add_argument("--vmax", type=float, default=None)
    parser.add_argument("--vmin", type=float, default=0)
    parser.add_argument("--cmap", default="Blues")
    args = parser.parse_args()

    run_ui(args.archive, out_path=args.out,
           vmax=args.vmax, vmin=args.vmin, cmap=args.cmap)


if __name__ == "__main__":
    main()
