"""Bokeh viewer for L1SPFilterPD per-triggered-ROI waveform dump.

Run:
    bokeh serve --port 5007 l1sp_roi_viewer.py --args <wf_dir>

wf_dir is the root passed to run_nf_sp_evt.sh -w, i.e. the parent of
<RUN_PADDED>_<EVT>/<dump_tag>_<frame_ident>/wf_p<plane>_c<chan>_t<start>_<pol>.npz.

For each triggered ROI the viewer shows four waveforms with shared x-axis:
  - raw ADC
  - original gauss/decon (before L1SP replacement)
  - unsmeared LASSO fit (LASSO output before Gaussian smearing)
  - smeared LASSO fit (the value that overwrites the gauss output)

To view from a remote laptop:
    ssh -L 5007:localhost:5007 user@workstation
    # then open http://localhost:5007/l1sp_roi_viewer in the laptop's browser
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
    RadioButtonGroup,
    Select,
)
from bokeh.plotting import figure


# ----- discovery -------------------------------------------------------------

def discover(root: str):
    """Walk <root>/<RUN_EVT>/*/<wf_*.npz> and return a nested index.

    Returns:
        {(run_evt, apa_int): {plane_int: [npz_path, ...]}}
    sorted by (channel, start_tick) within each plane list.
    """
    out: dict[tuple[str, int], dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    # Layout: <root>/<RUN_EVT>/<dump_tag>_<frame_ident>/wf_p<plane>_c<chan>_t<start>_<pol>.npz
    # We glob two levels deep to handle any dump_tag naming.
    pattern = os.path.join(root, "*", "*", "wf_*.npz")
    for f in glob.glob(pattern):
        parts = f.split(os.sep)
        # Layout: <root>/<RUN_EVT>/<dump_tag>_<count>_<frame_ident>/wf_*.npz
        # parts[-1]=file, parts[-2]=subdir, parts[-3]=RUN_EVT.
        run_evt = parts[-3]
        # Read plane and channel from the NPZ itself to be robust.
        try:
            z = np.load(f, mmap_mode="r")
            plane = int(z["plane"][0])
            channel = int(z["channel"][0])
            start_tick = int(z["start_tick"][0])
        except Exception:
            continue
        # Infer APA from dump_tag embedded in subdir name (first component before first '_').
        subdir = parts[-2]   # e.g. "apa0_0000_12345678"
        try:
            apa_str = subdir.split("_")[0]  # "apa0"
            apa = int(apa_str[len("apa"):]) if apa_str.startswith("apa") else 0
        except (ValueError, IndexError):
            apa = 0
        out[(run_evt, apa)][plane].append((channel, start_tick, f))

    # Sort within each plane by (channel, start_tick) and flatten to path list.
    result: dict[tuple[str, int], dict[int, list[str]]] = {}
    for (run_evt, apa), plane_map in out.items():
        result[(run_evt, apa)] = {}
        for plane, triples in plane_map.items():
            triples.sort(key=lambda t: (t[0], t[1]))
            result[(run_evt, apa)][plane] = [t[2] for t in triples]
    return result


def roi_label(npz_path: str) -> str:
    """Return a short label for the ROI select widget."""
    try:
        z = np.load(npz_path, mmap_mode="r")
        ch = int(z["channel"][0])
        st = int(z["start_tick"][0])
        pol = int(z["polarity"][0])
        polstr = "pos" if pol > 0 else "neg"
        return f"ch{ch}_t{st}_{polstr}"
    except Exception:
        return os.path.basename(npz_path)


# ----- main ------------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        print("Usage: bokeh serve l1sp_roi_viewer.py --args <wf_dir>", file=sys.stderr)
        sys.exit(1)
    root = os.path.abspath(argv[1])
    if not os.path.isdir(root):
        print(f"Error: wf dir not found: {root}", file=sys.stderr)
        sys.exit(1)

    roi_index = discover(root)
    if not roi_index:
        print(f"No wf_*.npz files found under {root}", file=sys.stderr)
        sys.exit(1)

    # ----- widgets -----------------------------------------------------------
    event_options = sorted({f"{re_}/apa{a}" for (re_, a) in roi_index})
    event_select = Select(title="Run/Event/APA:", value=event_options[0],
                          options=event_options)
    plane_radio = RadioButtonGroup(labels=["U", "V", "W"], active=0)
    roi_select = Select(title="ROI:", value="", options=[])
    prev_btn = Button(label="◀ Prev", width=80)
    next_btn = Button(label="Next ▶", width=80)
    info_div = Div(text="", width=700)

    # ----- figures -----------------------------------------------------------
    fig_kwargs = dict(
        height=220, sizing_mode="stretch_width",
        active_scroll="wheel_zoom",
        tools="pan,wheel_zoom,box_zoom,reset,save",
    )
    f_raw    = figure(title="Raw ADC",                  **fig_kwargs)
    f_decon  = figure(title="Original decon (gauss)",   x_range=f_raw.x_range, **fig_kwargs)
    f_lasso  = figure(title="LASSO fit (unsmeared)",    x_range=f_raw.x_range, **fig_kwargs)
    f_smear  = figure(title="Smeared LASSO (replaces decon)", x_range=f_raw.x_range, **fig_kwargs)

    for f in (f_raw, f_decon, f_lasso, f_smear):
        f.xaxis.axis_label = "tick"

    f_raw.yaxis.axis_label   = "ADC"
    f_decon.yaxis.axis_label = "amplitude"
    f_lasso.yaxis.axis_label = "amplitude"
    f_smear.yaxis.axis_label = "amplitude"

    src_raw   = ColumnDataSource(data=dict(x=[], y=[]))
    src_decon = ColumnDataSource(data=dict(x=[], y=[]))
    src_lasso = ColumnDataSource(data=dict(x=[], y=[]))
    src_smear = ColumnDataSource(data=dict(x=[], y=[]))

    f_raw.line  ("x", "y", source=src_raw,   line_width=1, color="#1f77b4")
    f_decon.line("x", "y", source=src_decon, line_width=1, color="#ff7f0e")
    f_lasso.line("x", "y", source=src_lasso, line_width=1, color="#2ca02c")
    f_smear.line("x", "y", source=src_smear, line_width=1, color="#d62728")

    # ROI extent shading (one BoxAnnotation per figure, updated on render).
    roi_boxes = [
        BoxAnnotation(left=0, right=1, fill_color="#ccccff", fill_alpha=0.25, line_color=None)
        for _ in range(4)
    ]
    for fig, box in zip((f_raw, f_decon, f_lasso, f_smear), roi_boxes):
        fig.add_layout(box)

    # ----- state helpers -----------------------------------------------------
    def selected_paths() -> list[str]:
        run_evt_apa = event_select.value
        run_evt, apa_part = run_evt_apa.split("/")
        apa = int(apa_part[len("apa"):])
        plane = plane_radio.active
        return roi_index.get((run_evt, apa), {}).get(plane, [])

    def update_roi_options():
        paths = selected_paths()
        if not paths:
            # Auto-switch to the first plane that has ROIs for this event/APA.
            run_evt_apa = event_select.value
            run_evt, apa_part = run_evt_apa.split("/")
            apa = int(apa_part[len("apa"):])
            for p in [0, 1, 2]:
                if roi_index.get((run_evt, apa), {}).get(p, []):
                    plane_radio.active = p  # triggers on_plane_change → update_roi_options
                    return
        opts = [roi_label(p) for p in paths]
        roi_select.options = opts
        if opts and (roi_select.value not in opts):
            roi_select.value = opts[0]

    def render():
        paths = selected_paths()
        if not paths:
            info_div.text = "<i>no triggered ROIs for this plane/APA</i>"
            for src in (src_raw, src_decon, src_lasso, src_smear):
                src.data = dict(x=[], y=[])
            return
        label = roi_select.value
        labels = [roi_label(p) for p in paths]
        if label not in labels:
            return
        npz_path = paths[labels.index(label)]
        try:
            z = np.load(npz_path)
            raw    = z["raw"].astype(float)
            decon  = z["decon"].astype(float)
            lasso  = z["lasso"].astype(float)
            smear  = z["smeared"].astype(float)
        except Exception as e:
            info_div.text = f"<b>Error loading {npz_path}:</b> {e}"
            for src in (src_raw, src_decon, src_lasso, src_smear):
                src.data = dict(x=[], y=[])
            return
        nbin   = len(raw)
        # lasso is empty when LASSO declined (sum_beta below threshold); pad
        # with zeros so all four ColumnDataSources get the same length.
        if len(lasso) != nbin:
            lasso = np.zeros(nbin)
        start  = int(z["start_tick"][0])
        end    = int(z["end_tick"][0])
        ch     = int(z["channel"][0])
        plane  = int(z["plane"][0])
        pol    = int(z["polarity"][0])
        frame  = int(z["frame_ident"][0])
        call   = int(z["call_count"][0])

        x = np.arange(start, start + nbin)
        src_raw.data   = dict(x=x, y=raw)
        src_decon.data = dict(x=x, y=decon)
        src_lasso.data = dict(x=x, y=lasso)
        src_smear.data = dict(x=x, y=smear)

        for box in roi_boxes:
            box.left  = start
            box.right = end

        plane_name = ["U", "V", "W"][plane] if plane < 3 else str(plane)
        pol_str = "positive (collection-on-induction)" if pol > 0 else "negative (anode-induction)"
        lasso_note = "" if int(z["lasso"].size) > 0 else " &nbsp; <i>(LASSO declined — sum_beta below threshold)</i>"
        info_div.text = (
            f"<b>ch={ch} &nbsp; plane={plane_name} &nbsp; ticks=[{start},{end}) "
            f"nbin={nbin}</b><br>"
            f"polarity: {pol_str}{lasso_note}<br>"
            f"frame_ident={frame} &nbsp; call_count={call}"
        )

    def step(delta: int):
        if not roi_select.options:
            return
        i = (roi_select.options.index(roi_select.value)
             if roi_select.value in roi_select.options else 0)
        i = (i + delta) % len(roi_select.options)
        roi_select.value = roi_select.options[i]

    # ----- callbacks ---------------------------------------------------------
    def on_event_change(_attr, _old, _new):
        update_roi_options()
        render()

    def on_plane_change(_attr, _old, _new):
        update_roi_options()
        render()

    def on_roi_change(_attr, _old, _new):
        render()

    event_select.on_change("value", on_event_change)
    plane_radio.on_change("active", on_plane_change)
    roi_select.on_change("value", on_roi_change)
    prev_btn.on_click(lambda: step(-1))
    next_btn.on_click(lambda: step(+1))

    # ----- layout ------------------------------------------------------------
    update_roi_options()
    render()
    layout = column(
        row(event_select, plane_radio, roi_select, prev_btn, next_btn,
            sizing_mode="stretch_width"),
        info_div,
        f_raw, f_decon, f_lasso, f_smear,
        sizing_mode="stretch_width",
    )
    curdoc().add_root(layout)
    curdoc().title = "L1SP ROI waveform viewer"


main(sys.argv)
