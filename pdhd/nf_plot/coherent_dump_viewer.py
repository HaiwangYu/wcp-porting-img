"""Bokeh viewer for PDHD/PDVD coherent-noise dump (.npz per group).

Run:
    bokeh serve --port 5006 coherent_dump_viewer.py --args <dump_dir>

dump_dir is the root passed to run_nf_sp_evt.sh -d, i.e. the parent of
<RUN_PADDED>_<EVT>/apa<N>/<plane>_g<gid>.npz.

The viewer is detector-agnostic: it discovers groups by globbing.
"""

from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

import numpy as np
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (
    BoxAnnotation,
    Button,
    ColumnDataSource,
    Div,
    HoverTool,
    RadioButtonGroup,
    Select,
    Span,
)
from bokeh.plotting import figure


# ----- discovery -----------------------------------------------------------

def discover(root: str):
    """Walk <root>/<RUN_EVT>/apa<N>/<plane>_g<gid>.npz and group by event/apa.

    Returns a dict {(run_evt, apa_int): [npz_path, ...]} sorted by group id.
    """
    out: dict[tuple[str, int], list[str]] = defaultdict(list)
    pattern = os.path.join(root, "*", "apa*", "*.npz")
    for f in glob.glob(pattern):
        parts = f.split(os.sep)
        run_evt = parts[-3]
        apa_dir = parts[-2]  # 'apa1'
        try:
            apa = int(apa_dir[len("apa"):])
        except ValueError:
            continue
        out[(run_evt, apa)].append(f)
    for k in out:
        out[k].sort()
    return out


def _bytes_to_str(arr) -> str:
    if arr.dtype == np.int8 or arr.dtype == np.uint8:
        if arr.size == 0:
            return ""
        return arr.tobytes().decode("ascii", errors="replace")
    return str(arr)


def load_group(npz_path: str) -> dict:
    z = np.load(npz_path)
    d = {k: z[k] for k in z.files}
    # decode small string fields
    for k in ("time_filter_name", "lf_tighter_filter_name", "lf_loose_filter_name"):
        if k in d:
            d[k] = _bytes_to_str(d[k])
    return d


# ----- main ----------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        print("Usage: bokeh serve coherent_dump_viewer.py --args <dump_dir>", file=sys.stderr)
        sys.exit(1)
    root = os.path.abspath(argv[1])
    if not os.path.isdir(root):
        print(f"Error: dump dir not found: {root}", file=sys.stderr)
        sys.exit(1)

    groups_by_event = discover(root)
    if not groups_by_event:
        print(f"No NPZ files under {root}", file=sys.stderr)
        sys.exit(1)

    # Per-event/APA partition further by plane.
    # state[(run_evt, apa)] = {0: [paths], 1: [...], 2: [...]}
    plane_index: dict[tuple[str, int], dict[int, list[str]]] = {}
    for (run_evt, apa), files in groups_by_event.items():
        per_plane = defaultdict(list)
        for f in files:
            z = np.load(f, mmap_mode="r")
            per_plane[int(z["plane"][0])].append(f)
        for p in per_plane:
            per_plane[p].sort(key=lambda fp: int(np.load(fp, mmap_mode="r")["gid"][0]))
        plane_index[(run_evt, apa)] = per_plane

    # ----- widgets ---------------------------------------------------------
    event_options = sorted({f"{re_}/apa{a}" for (re_, a) in plane_index})
    event_select = Select(title="Run/Event/APA:", value=event_options[0], options=event_options)
    plane_radio = RadioButtonGroup(labels=["U", "V", "W"], active=0)
    prev_btn = Button(label="◀ Prev", width=80)
    next_btn = Button(label="Next ▶", width=80)
    group_select = Select(title="Group (gid):", value="", options=[])
    knob_div = Div(text="", width=600)

    # ----- figures ---------------------------------------------------------
    top = figure(
        title="Median waveform + signal protection window",
        height=320, sizing_mode="stretch_width",
        active_scroll="wheel_zoom",
        tools="pan,wheel_zoom,box_zoom,reset,save",
    )
    top.xaxis.axis_label = "tick"
    top.yaxis.axis_label = "ADC (median)"

    bot = figure(
        title="Deconvolved median + per-ROI accept",
        height=320, sizing_mode="stretch_width",
        active_scroll="wheel_zoom",
        tools="pan,wheel_zoom,box_zoom,reset,save,hover",
        x_range=top.x_range,
    )
    bot.xaxis.axis_label = "tick"
    bot.yaxis.axis_label = "deconv amplitude"

    median_src = ColumnDataSource(data=dict(x=[], y=[]))
    decon_src = ColumnDataSource(data=dict(x=[], y=[]))

    top.line("x", "y", source=median_src, line_width=1, color="#1f77b4")
    bot.line("x", "y", source=decon_src, line_width=1, color="#1f77b4")

    # threshold lines (mutated on update)
    top_pos = Span(location=0, dimension="width", line_color="red", line_dash="dashed", line_width=1.5)
    top_neg = Span(location=0, dimension="width", line_color="red", line_dash="dashed", line_width=1.5)
    top.add_layout(top_pos)
    top.add_layout(top_neg)

    bot_decon_thresh = Span(location=0, dimension="width", line_color="red", line_dash="dashed", line_width=1.5)
    bot_decon_limit1 = Span(location=0, dimension="width", line_color="purple", line_dash="dotted", line_width=1.5)
    bot_decon_limit1n = Span(location=0, dimension="width", line_color="purple", line_dash="dotted", line_width=1.5)
    bot.add_layout(bot_decon_thresh)
    bot.add_layout(bot_decon_limit1)
    bot.add_layout(bot_decon_limit1n)

    # ROI box annotations (recreated on update)
    top_boxes: list[BoxAnnotation] = []
    bot_boxes: list[BoxAnnotation] = []

    # Per-ROI hover source for bot
    roi_hover_src = ColumnDataSource(
        data=dict(x=[], y=[], w=[], h=[], color=[],
                  start=[], end=[], max_med=[], min_med=[],
                  ratio_med=[], accept_med=[], n_ch_accept=[])
    )
    roi_glyph = bot.rect(
        x="x", y="y", width="w", height="h", source=roi_hover_src,
        fill_color="color", fill_alpha=0.18, line_color=None,
    )
    bot.add_tools(HoverTool(
        renderers=[roi_glyph],
        tooltips=[
            ("ROI", "@start..@end"),
            ("max(median_decon)", "@max_med{0.0000}"),
            ("min(median_decon)", "@min_med{0.0000}"),
            ("|min|/max",  "@ratio_med{0.000}"),
            ("median accept", "@accept_med"),
            ("ch accept count", "@n_ch_accept"),
        ],
    ))

    # ----- update ----------------------------------------------------------
    def selected_paths() -> list[str]:
        run_evt_apa = event_select.value
        run_evt, apa_part = run_evt_apa.split("/")
        apa = int(apa_part[len("apa"):])
        plane = plane_radio.active
        return plane_index.get((run_evt, apa), {}).get(plane, [])

    def update_group_options():
        paths = selected_paths()
        opts = []
        for p in paths:
            z = np.load(p, mmap_mode="r")
            opts.append(str(int(z["gid"][0])))
        group_select.options = opts
        if opts and (group_select.value not in opts):
            group_select.value = opts[0]

    def clear_boxes():
        for b in top_boxes:
            top.center.remove(b) if b in top.center else None
        for b in bot_boxes:
            bot.center.remove(b) if b in bot.center else None
        top_boxes.clear()
        bot_boxes.clear()

    def render():
        paths = selected_paths()
        if not paths:
            knob_div.text = "<i>no groups for this plane</i>"
            return
        gid = group_select.value
        match = [p for p in paths
                 if str(int(np.load(p, mmap_mode="r")["gid"][0])) == gid]
        if not match:
            return
        d = load_group(match[0])
        nbin = int(d["nbin"][0])
        x = np.arange(nbin)

        median_src.data = dict(x=x, y=d["median"])
        if int(d["decon_stage_ran"][0]) == 1:
            decon_src.data = dict(x=x, y=d["medians_decon_aligned"])
        else:
            decon_src.data = dict(x=x, y=np.zeros(nbin))

        adc = float(d["adc_threshold_chosen"][0])
        mean_adc = float(d["mean_adc"][0])
        top_pos.location = mean_adc + adc
        top_neg.location = mean_adc - adc

        bot_decon_thresh.location = float(d["decon_threshold_chosen"][0]) + float(d["mean_decon"][0])
        bot_decon_limit1.location = float(d["decon_limit1"][0])
        bot_decon_limit1n.location = -float(d["decon_limit1"][0]) * float(d["roi_min_max_ratio"][0])

        # Recreate ROI annotations
        clear_boxes()

        roi_starts = d["roi_starts"]
        roi_ends = d["roi_ends"]
        roi_max = d["roi_max_median"]
        roi_min = d["roi_min_median"]
        roi_ratio = d["roi_ratio_median"]
        roi_accept = d["roi_accepted_median"]
        nrois = roi_starts.size

        # protection bands on top panel: signal_bool (post-pad) shaded
        signal_bool = d["signal_bool"]
        # Build contiguous intervals from signal_bool
        if signal_bool.any():
            diff = np.diff(signal_bool.astype(np.int8), prepend=0, append=0)
            on_edges = np.where(diff == 1)[0]
            off_edges = np.where(diff == -1)[0]
            for s, e in zip(on_edges, off_edges):
                ann = BoxAnnotation(left=int(s), right=int(e), fill_color="#ffaaaa",
                                    fill_alpha=0.30, line_color=None)
                top.add_layout(ann)
                top_boxes.append(ann)

        # Per-ROI rectangles on bot panel: green if accepted (median), red if rejected
        if nrois > 0:
            nch = int(d["channels"].size)
            ch_accept_count = d["roi_accepted_per_ch"].reshape(nch, nrois).sum(axis=0)
            ymin, ymax = float(np.min(decon_src.data["y"])), float(np.max(decon_src.data["y"]))
            cy = 0.5 * (ymin + ymax)
            ch = max(ymax - ymin, 1e-3)
            xs, ws, ys, hs, colors = [], [], [], [], []
            for r in range(nrois):
                s = int(roi_starts[r]); e = int(roi_ends[r])
                xs.append(0.5 * (s + e)); ws.append(max(e - s, 1))
                ys.append(cy); hs.append(ch * 0.9)
                colors.append("#4daf4a" if int(roi_accept[r]) == 1 else "#e41a1c")
            roi_hover_src.data = dict(
                x=xs, y=ys, w=ws, h=hs, color=colors,
                start=[int(roi_starts[r]) for r in range(nrois)],
                end=[int(roi_ends[r]) for r in range(nrois)],
                max_med=[float(roi_max[r]) for r in range(nrois)],
                min_med=[float(roi_min[r]) for r in range(nrois)],
                ratio_med=[float(roi_ratio[r]) for r in range(nrois)],
                accept_med=[int(roi_accept[r]) for r in range(nrois)],
                n_ch_accept=[int(ch_accept_count[r]) for r in range(nrois)],
            )
        else:
            roi_hover_src.data = dict(x=[], y=[], w=[], h=[], color=[],
                                      start=[], end=[], max_med=[], min_med=[],
                                      ratio_med=[], accept_med=[], n_ch_accept=[])

        # Knob summary
        plane_name = ["U", "V", "W"][int(d["plane"][0])]
        knob_div.text = (
            f"<b>APA {int(d['apa'][0])} / plane {plane_name} / gid {int(d['gid'][0])}</b>"
            f" &nbsp; nbin={nbin}, res_offset={int(d['res_offset'][0])}, nrois={nrois}<br>"
            f"<b>knobs:</b> "
            f"protection_factor={float(d['protection_factor'][0]):.2f}, "
            f"min_adc_limit={float(d['min_adc_limit'][0]):.1f}, "
            f"upper_adc_limit={float(d['upper_adc_limit'][0]):.1f}, "
            f"upper_decon_limit={float(d['upper_decon_limit'][0]):.4f}, "
            f"decon_limit1={float(d['decon_limit1'][0]):.4f}, "
            f"roi_min_max_ratio={float(d['roi_min_max_ratio'][0]):.3f}, "
            f"pad_front={int(d['pad_front'][0])}, pad_back={int(d['pad_back'][0])}<br>"
            f"<b>chosen:</b> "
            f"adc_threshold={float(d['adc_threshold_chosen'][0]):.2f} "
            f"(rms_adc={float(d['rms_adc'][0]):.3f}), "
            f"decon_threshold={float(d['decon_threshold_chosen'][0]):.4f} "
            f"(rms_decon={float(d['rms_decon'][0]):.4e})<br>"
            f"<b>filters:</b> "
            f"time={d['time_filter_name']}, "
            f"lf_tighter={d['lf_tighter_filter_name']}, "
            f"lf_loose={d['lf_loose_filter_name']}<br>"
            f"<b>scaling:</b> ave_coef={float(d['ave_coef'][0]):.4f}"
        )

    def step(delta: int):
        if not group_select.options:
            return
        i = group_select.options.index(group_select.value) if group_select.value in group_select.options else 0
        i = (i + delta) % len(group_select.options)
        group_select.value = group_select.options[i]

    # ----- callbacks -------------------------------------------------------
    def on_event_change(_attr, _old, _new):
        update_group_options()
        render()

    def on_plane_change(_attr, _old, _new):
        update_group_options()
        render()

    def on_group_change(_attr, _old, _new):
        render()

    event_select.on_change("value", on_event_change)
    plane_radio.on_change("active", on_plane_change)
    group_select.on_change("value", on_group_change)
    prev_btn.on_click(lambda: step(-1))
    next_btn.on_click(lambda: step(+1))

    # ----- layout ----------------------------------------------------------
    update_group_options()
    render()
    layout = column(
        row(event_select, plane_radio, group_select, prev_btn, next_btn,
            sizing_mode="stretch_width"),
        knob_div,
        top, bot,
        sizing_mode="stretch_width",
    )
    curdoc().add_root(layout)
    curdoc().title = "PDHD/PDVD coherent-NF dump viewer"


main(sys.argv)
