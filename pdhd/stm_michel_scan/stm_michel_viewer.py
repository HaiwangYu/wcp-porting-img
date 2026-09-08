#!/usr/bin/env python3
"""PDHD / PDVD stopping-muon + Michel-electron hand-scan display -- doc pdhd/12.

FORK BY DUPLICATION of pdhd/stm_scan/stm_scan_viewer.py (the PDHD Bokeh scan
app), which is untouched.  The 3-D view is smx3d.py, itself a fork of
sbnd_xin/em_display/em3d.py.  One app serves both detectors: --det picks the
geometry table in smgeom.py and the prep directory; nothing else differs.

WHAT THIS IS FOR
  CheckSTM_Michel reconstructs every STM-tagged main as
  entry -> muon body -> Bragg stop -> Michel e- (+ dots), and persists the whole
  thing (doc pdvd/48, doc pdhd/03).  What it does NOT have is a measured purity
  and efficiency for the "stopping muon WITH a Michel" flag, or a hand-placed
  stopping point to score its own against.  This app produces both, and the
  labels it writes are the sample definition for the Michel energy spectrum and
  the angle-vs-momentum study that come after.

WHAT YOU ARE JUDGING, and what is on screen while you judge it
  From the CHARGE, judge the whole object: does it enter the detector, stop
  inside, and is there a Michel electron at the stop?

  Drawn always -- this is the evidence, and a display that shows only the
  reconstruction's own trajectory would be asking the right question with the
  wrong picture (feedback_scan_display_must_show_the_evidence, which cost
  6 of 36 labels in doc pr/148):
      grey    all other charge in the event, thinned
      colour  every imaged point within 20 cm of the fitted muon, and within
              40 cm of its stopping end, at FULL density -- purely geometric
              over all the charge, never "the points the chain assigned here"
      line    the fitted muon chain, coloured by its own dQ/dx
      panel   dQ/dx vs residual range, against this detector's own muon and
              electron reference curves

  Behind REVEAL -- this is the chain's ANSWER, and seeing it before you label
  makes the agreement number circular (feedback_blind_the_scan_sheet):
      the Michel / delta / dot segments it found, its entry / stop / tagger-stop
      points, is_stm, the reject bits, the Michel energy and kink, and the
      cosmic tagger's own STM fit.
  Every label records `revealed_before_label`, so a revealed label is still
  usable -- it is simply scored separately.

THE PIN, and an honest limit about it
  You place the muon's STOPPING POINT yourself.  Tap any panel to snap it to the
  nearest point of the fitted chain, or drag the residual-range slider.  The
  dQ/dx panel re-anchors on it live, so the muon side and the Michel side of the
  panel separate exactly where you say the muon stopped -- which is the quantity
  the downstream separation needs.

  THE LIMIT, measured rather than assumed (doc pdhd/12 sec 6.2): the chain's own
  `stop_*` scalar is NOT hidden from you, because it is the last point of the
  muon chain that has to be drawn -- and it sits within 0.01 cm of that point on
  97.7 % of items on both detectors (median 0.0000, p99 0.87 cm PDHD /
  0.60 cm PDVD).  So the pin is not a blind independent placement and this doc
  never calls it one.  What it measures is whether you AGREE with the drawn end,
  and the label records `placed` and `moved_cm` so "the scanner accepted it"
  and "the scanner moved it by 4 cm" are different rows rather than the same one.
  What the blind does still withhold is everything the scan is actually about:
  the Michel verdict, the Michel / delta / dot segmentation, the reject bits, and
  the cosmic tagger's own stop -- which differs from `stop_*` by a median
  0.64 cm and up to 266 cm on PDHD, 0.45 cm and up to 34 cm on PDVD.

USAGE
  ./serve_stm_michel_scan.sh 5023 --det pdhd --scan-tag smx1
  then  http://localhost:5023/stm_michel_viewer
"""
import csv
import json
import math
import os
import sys
import time

import numpy as np
from bokeh.events import DocumentReady, Pan, PanEnd, PanStart, Tap
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (BoxSelectTool, Button, CheckboxGroup, ColorBar,
                          ColumnDataSource, CustomJS, Div, HoverTool,
                          LinearColorMapper, RadioButtonGroup, Range1d,
                          ResetTool, SaveTool, Select, Slider, Tabs, TabPanel,
                          TapTool, TextInput, Toggle, WheelZoomTool)
from bokeh.palettes import Turbo256, Viridis256
from bokeh.plotting import figure
from bokeh.transform import linear_cmap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smgeom                                                     # noqa: E402
import smx3d as D3                                                # noqa: E402

IMG = os.path.dirname(os.path.dirname(HERE))


# ---------------------------------------------------------------------------
# arguments
# ---------------------------------------------------------------------------
def parse_args(argv):
    a = dict(det="pdhd", tag="smx1", manifest=None, prepdir=None, labeldir=None)
    i = 0
    while i < len(argv):
        t = argv[i]
        for k in ("det", "tag", "manifest", "prepdir", "labeldir"):
            if t == "--" + k and i + 1 < len(argv):
                a[k] = argv[i + 1]; i += 1
            elif t.startswith("--" + k + "="):
                a[k] = t.split("=", 1)[1]
        i += 1
    return a


ARGS = parse_args(sys.argv[1:])
DETNAME = ARGS["det"]
if DETNAME not in smgeom.ENVELOPE:
    raise SystemExit("unknown --det %r" % DETNAME)
DETROOT = os.path.join(IMG, DETNAME)
SCAN_TAG = ARGS["tag"]
PREPDIR = ARGS["prepdir"] or os.path.join(HERE, "prep-" + DETNAME)
SHEET = ARGS["manifest"] or os.path.join(
    DETROOT, "docs", "scan", "%s_stm_michel_scan_sheet.tsv" % DETNAME)
# A sibling of the per-event dirs, so re-running an arm cannot delete the labels
# (M13).  A second pass is a new --scan-tag, never a write into this one.
# --labeldir exists only so selftest_stm_michel_scan.py can run without writing
# anything under work/ (M13); a real scan never passes it.
LABEL_DIR = ARGS["labeldir"] or os.path.join(
    DETROOT, "work", "stm_michel_labels", SCAN_TAG)
os.makedirs(LABEL_DIR, exist_ok=True)
LABEL_FILE = os.path.join(LABEL_DIR, "labels.json")

VOL = smgeom.ENVELOPE[DETNAME]
PAD = 20.0

# The alphabet.  A FRAG button records the FULL object's verdict plus
# partial=True, so a fragment still scores in the binary AND the
# under-clustering rate falls out as its own number
# (feedback_fragment_label_carries_object_verdict).  Keep the three escape
# hatches distinct: FRAG is about the CLUSTER, MESSY about the OBJECT, UNCLEAR
# about YOUR confidence.
CHOICES = {
    "STM_MICHEL":      dict(label="STM_MICHEL", partial=False),
    "STM_ONLY":        dict(label="STM_ONLY", partial=False),
    "THRU":            dict(label="THRU", partial=False),
    "FRAG_STM_MICHEL": dict(label="STM_MICHEL", partial=True),
    "FRAG_STM_ONLY":   dict(label="STM_ONLY", partial=True),
    "FRAG_THRU":       dict(label="THRU", partial=True),
    "MESSY":           dict(label="MESSY", partial=False),
    "UNCLEAR":         dict(label="UNCLEAR", partial=False),
}
# "not set" is a REAL option and the default, not padding.  The radio only
# resets from a SAVED label, so without it a scanner who clicks STM + MICHEL
# without touching the radio silently records michel_kind = "none" -- a
# contradiction with their own label that no downstream check would catch, on
# the one field doc pdhd/12 sec 7 says goal 2 depends on.
MICHEL_UNSET = "— not set —"
MICHEL_KINDS = [MICHEL_UNSET, "none", "attached", "detached dots", "both"]


# ---------------------------------------------------------------------------
# the item list -- a committed sheet, never a shell glob, so the sample is
# reproducible.  It carries no verdict, no stratum and no chain flag.
# ---------------------------------------------------------------------------
def load_items():
    with open(SHEET) as fh:
        lines = [l for l in fh if not l.startswith("#")]
    rows = []
    for r in csv.DictReader(lines, delimiter="\t"):
        rows.append(dict(scan_id=int(r["scan_id"]), tranche=int(r["tranche"]),
                         event=r["event"], cluster=int(r["cluster"]),
                         npts=int(r["npts"]), muon_len=float(r["muon_len_cm"])))
    rows.sort(key=lambda r: (r["tranche"], r["scan_id"]))
    return rows


ITEMS = load_items()
if not ITEMS:
    raise SystemExit("no scan items in %s" % SHEET)

_REF = {}
_refp = os.path.join(PREPDIR, "dqdx_ref_%s.json" % DETNAME)
if os.path.exists(_refp):
    with open(_refp) as fh:
        _REF = json.load(fh)

_pay_cache = {}


def payload(it):
    k = (it["event"], it["cluster"])
    if k in _pay_cache:
        return _pay_cache[k]
    p = os.path.join(PREPDIR, "smprep-%s-c%d.json" % k)
    d = None
    if os.path.exists(p):
        with open(p) as fh:
            d = json.load(fh)
    if len(_pay_cache) > 6:
        _pay_cache.pop(next(iter(_pay_cache)))
    _pay_cache[k] = d
    return d


# ---------------------------------------------------------------------------
# labels: one file keyed "<event>/<cluster>", rewritten atomically on EVERY click
# ---------------------------------------------------------------------------
def item_key(it):
    return "%s/%d" % (it["event"], it["cluster"])


def load_labels():
    if not os.path.isfile(LABEL_FILE):
        return {}
    try:
        with open(LABEL_FILE) as fh:
            return json.load(fh).get("labels", {})
    except (OSError, ValueError):
        return {}


LABELS = load_labels()          # append-only: an existing file is loaded, never truncated


def save_labels():
    """Write, then READ BACK, and return what the file on disk actually holds.

    The read-back is the point.  "It was saved" is a claim about a write that
    returned; what the scanner needs to trust is the FILE, so every save
    re-opens it, re-parses it, and reports its size, mtime and label count from
    that parse.  A silent truncation, a full disk or a JSON the app can write
    but cannot read all show up here instead of at the end of the scan.
    """
    tmp = LABEL_FILE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"scan": "stm_michel_topology",
                   "doc": "pdhd/docs/12_stm-michel-handscan-display.md",
                   "det": DETNAME, "tag": SCAN_TAG,
                   "sheet": os.path.relpath(SHEET, DETROOT),
                   "labels": LABELS}, fh, indent=1)
    os.replace(tmp, LABEL_FILE)      # atomic: a crash mid-write keeps the old file
    return read_back()


def read_back():
    """(ok, n_on_disk, bytes, mtime string, error) straight from the file.

    A file that does not exist yet is not an error -- it is the truthful state
    "nothing saved yet", and reporting it as a failure would cry wolf on every
    fresh scan tag.  A file that EXISTS but cannot be parsed is an error.
    """
    if not os.path.exists(LABEL_FILE):
        return (True, 0, 0, "never", None)
    try:
        st = os.stat(LABEL_FILE)
        with open(LABEL_FILE) as fh:
            d = json.load(fh)
        return (True, len(d.get("labels", {})), st.st_size,
                time.strftime("%H:%M:%S", time.localtime(st.st_mtime)), None)
    except Exception as ex:                       # noqa: BLE001 - report anything
        return (False, 0, 0, "", "%s: %s" % (type(ex).__name__, ex))


# ---------------------------------------------------------------------------
# layers.  ONE description drives the three 2-D panels and the 3-D panel, so a
# layer cannot exist in one and be forgotten in the other.
#   reveal=True  -> the chain's answer; hidden unless REVEAL is on
# ---------------------------------------------------------------------------
LAYERS = [
    # name       size alpha  colour            marker      reveal cue
    ("far",       1.5, 0.35, "#c9c9c9",        "circle",   False, 1.0),
    # charge that belongs to a DIFFERENT matched Q-L bundle (doc pdhd/13 sec 4).
    # Drawn only when "bundle only" is off, in a colour no other layer uses, so
    # a neighbouring cosmic can never be read as over-clustering.
    ("outb",      2.5, 0.55, "#b07aa1",        "circle",   False, 1.0),
    ("near",      3.0, 0.80, ("q", 0.0, 4e4),  "circle",   False, 1.0),
    ("muon",      6.0, 0.95, ("c", 0.0, 1e5),  "circle",   False, 0.0),
    ("tagfit",    3.0, 0.60, "#7f7f7f",        "circle",   True,  0.0),
    ("delta",     7.0, 0.95, "#ff7f0e",        "circle",   True,  0.0),
    ("michel",    8.0, 0.95, "#1f77b4",        "circle",   True,  0.0),
    ("dots",     10.0, 0.95, "#d62728",        "diamond",  True,  0.0),
    ("entry",    16.0, 0.95, "#2ca02c",        "triangle", True,  0.0),
    ("stop",     16.0, 0.95, "#2ca02c",        "inverted_triangle", True, 0.0),
    ("tstop",    16.0, 0.95, "#2ca02c",        "x",        True,  0.0),
    ("pin",      22.0, 1.00, "#e377c2",        "star",     False, 0.0),
    # the point you last clicked in the dQ/dx panel, echoed in every other view
    ("cursor",   19.0, 1.00, "#17becf",   "circle_cross",    False, 0.0),
    # the PR particle flow.  "@col" = a per-point colour COLUMN, so one layer can
    # carry a categorical palette.  The topology is neutral and always available
    # (behind its own toggle, not behind REVEAL) -- the pdg and the track/shower
    # flag are the chain's answer and live in the verdict block.
    ("pfseg",     4.0, 0.70, "@col",           "circle",   False, 0.0),
    ("pfvtx",    11.0, 0.90, "#8c564b",        "square",   False, 0.0),
    ("pfsel",     9.0, 0.95, "#ffb000",        "circle",   False, 0.0),
    ("pftag",    12.0, 0.95, "@col",           "square",   False, 0.0),
]
# The scanner's own per-segment answer.  Drawn as HOLLOW squares, a different
# channel from every filled marker on the page, so a tag can never be mistaken
# for the reconstruction's colours.
PF_TAGS = {"muon": "#2c7fb8", "michel": "#e31a1c",
           "delta / other": "#7f7f7f", "straddles the stop": "#6a3d9a"}
# Measured over 25 events per detector (doc pdhd/12 sec 5.7): only 3.7 % (PDHD)
# and 6.3 % (PDVD) of PF segments carry points on BOTH sides of the muon/Michel
# boundary, so a per-segment tag is well posed -- but it is not always, and
# "straddles the stop" is the honest answer rather than a coin flip.
PF_PALETTE = ["#4c78a8", "#72b7b2", "#54a24b", "#eeca3b", "#b279a2", "#ff9da6",
              "#9d755d", "#bab0ac", "#e45756", "#f58518"]
REVEAL_LAYERS = {n for n, _, _, _, _, rv, _ in LAYERS if rv}

PANELS = [("z", "y", "side view:   Z (beam) vs Y"),
          ("z", "x", "top view:    Z (beam) vs X (drift)"),
          ("x", "y", "end view:    X (drift) vs Y")]

SRC2 = {}          # (ha, va, layer) -> ColumnDataSource with a, b [, q|c]
FIG2 = {}
REND2 = {}


# ---------------------------------------------------------------------------
# colour, and why it is not Viridis any more (doc pdhd/12 sec 5.6)
#
# The dQ/dx panel used Viridis with the muon's own p98 as the top of the scale.
# Two things were wrong with that and BOTH hid the one feature this scan exists
# to judge:
#   * Viridis ends at #FDE725 -- bright yellow on a white page.  So the BRAGG
#     PEAK, the highest-dQ/dx points, rendered as the least visible colour on
#     the plot.  Turbo ends at a dark red (#7A0403) and starts at a dark blue,
#     so nothing on the scale is near the page colour.
#   * a per-ITEM p98 made the colour mean something different on every item, so
#     two objects with a factor-3 difference in dQ/dx looked identical.  The
#     scale is FIXED now, from a measurement rather than a guess: over every
#     role-1 point of both production arms (97 721 PDHD + 166 037 PDVD),
#     p50 = 49.5/50.2 ke/cm, p99 = 112/118 ke/cm, p99.9 = 162/166 ke/cm.
#     1.5e5 puts the MIP plateau at a third of the range (cyan-green) and the
#     Bragg rise in the orange-to-dark-red top, with < 0.3 % saturating.
# Independently of the palette, every marker in the dQ/dx panel now carries a
# thin dark outline, so "invisible fill" cannot come back if the scale is ever
# retuned.
DQDX_HIGH = 1.5e5

# The image-charge layer keeps an adaptive scale (it is context, and its range
# genuinely varies by plane and detector) but gets its OWN cool ramp, because
# `near` and `muon` were both Viridis in the same panels -- charge-per-point and
# charge-per-cm reading as one quantity.
def _ramp(stops, n=256):
    """A 256-step palette from (position, #rrggbb) stops."""
    out = []
    for i in range(n):
        t = i / (n - 1.0)
        for k in range(len(stops) - 1):
            (p0, c0), (p1, c1) = stops[k], stops[k + 1]
            if t <= p1 or k == len(stops) - 2:
                f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                f = min(1.0, max(0.0, f))
                rgb = [int(round(int(c0[1 + 2 * j:3 + 2 * j], 16) * (1 - f)
                                 + int(c1[1 + 2 * j:3 + 2 * j], 16) * f))
                       for j in range(3)]
                out.append("#%02x%02x%02x" % tuple(rgb))
                break
    return out


PAL_NEAR = _ramp([(0.0, "#d5dde5"), (0.45, "#5a8fc0"), (1.0, "#10233f")])
# Diverging and WHITE-CENTRED on purpose: a cell where the fit agrees with the
# wires should vanish into the page, so only disagreement draws the eye.
PAL_DIFF = _ramp([(0.0, "#2166ac"), (0.5, "#ffffff"), (1.0, "#b2182b")])

cm_near = LinearColorMapper(palette=PAL_NEAR, low=0.0, high=4e4)
cm_muon = LinearColorMapper(palette=Turbo256, low=0.0, high=DQDX_HIGH)


def _fields(name):
    """extra data columns a layer carries beyond the two projected ones"""
    if name == "near":
        return ["q"]
    if name in ("muon", "tagfit"):
        return ["c"]
    if name in ("pfseg", "pftag"):
        return ["col"]
    return []


for ha, va, title in PANELS:
    f = figure(title=title, height=330, width=470, match_aspect=True,
               tools="pan,wheel_zoom,box_zoom,reset,save,tap",
               active_scroll="wheel_zoom",
               x_axis_label="%s [cm]" % ha.upper(),
               y_axis_label="%s [cm]" % va.upper())
    for name, sz, al, col, marker, rv, _cue in LAYERS:
        d = dict(a=[], b=[])
        for x in _fields(name):
            d[x] = []
        src = ColumnDataSource(d)
        if isinstance(col, tuple):
            fld, lo, hi = col
            cmap = cm_near if name == "near" else cm_muon
            r = f.scatter("a", "b", source=src, size=sz, alpha=al, marker=marker,
                          line_color=None,
                          color={"field": fld, "transform": cmap})
        elif col == "@col":
            hollow = name == "pftag"
            r = f.scatter("a", "b", source=src, size=sz, marker=marker,
                          fill_color=None if hollow else "col",
                          fill_alpha=0.0 if hollow else al,
                          line_color="col", line_width=2.0 if hollow else 0.0,
                          line_alpha=1.0 if hollow else 0.0)
        else:
            r = f.scatter("a", "b", source=src, size=sz, alpha=al, marker=marker,
                          color=col,
                          line_color="#333333" if name in ("pin", "dots", "cursor",
                                                           "pfsel", "pfvtx") else None)
        SRC2[(ha, va, name)] = src
        REND2[(ha, va, name)] = r
    # the active boundary, so "does it reach a face" is answerable by eye, and
    # the APA / CRP seams, so "which readout unit did it stop in" is too
    x0, x1 = VOL[ha]
    y0, y1 = VOL[va]
    f.line([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0],
           color="#d62728", line_width=1.2, line_dash="dashed")
    for v in smgeom.SEAMS[DETNAME][ha]:
        f.line([v, v], [y0, y1], color="#9467bd", line_width=1.0,
               line_dash="dotted", alpha=0.7)
    for v in smgeom.SEAMS[DETNAME][va]:
        f.line([x0, x1], [v, v], color="#9467bd", line_width=1.0,
               line_dash="dotted", alpha=0.7)
    FIG2[(ha, va)] = f


# ---------------------------------------------------------------------------
# the 3-D panel.  Mechanics, frame constraint and honest limits: smx3d.py.
# ---------------------------------------------------------------------------
_wheel3 = WheelZoomTool(dimensions="both")
_tap3 = TapTool()
f3d = figure(name="f3d", width=760, height=760,
             title="3-D  —  drag rotates, shift+drag pans, wheel zooms, tap pins",
             x_range=Range1d(-100, 100), y_range=Range1d(-100, 100),
             tools=[_wheel3, _tap3, ResetTool(), SaveTool()],
             output_backend="webgl")
f3d.toolbar.active_scroll = _wheel3
f3d.toolbar.active_tap = _tap3
# Explicitly None, NOT the "auto" default: auto would make a drag tool active and
# a bare drag would pan instead of rotating.  smx3d.JS_ROTATE steps aside the
# moment a drag tool IS picked in the toolbar.
f3d.toolbar.active_drag = None
for ax in (f3d.xaxis, f3d.yaxis, f3d.xgrid, f3d.ygrid):
    ax.visible = False

SRC3, REND3 = {}, {}
_PT_SRC, _PT_SIZE, _PT_ALPHA, _PT_CUE = [], [], [], []
for name, sz, al, col, marker, rv, cue in LAYERS:
    d = dict(x=[], y=[], z=[], u=[], v=[], al=[], sz=[])
    for x in _fields(name):
        d[x] = []
    # Named so selftest_smx3d_browser.py can reach the source from inside the
    # page (Bokeh.documents[0].get_model_by_name) and check that a real mouse
    # drag actually moved the projected columns.  em3d's own docstring records
    # that its CustomJS is not machine-tested because its tree has no JS engine;
    # this one has playwright, so the honest limit is narrowed rather than
    # inherited.
    src = ColumnDataSource(d, name="src3_" + name)
    if isinstance(col, tuple):
        fld, lo, hi = col
        cmap = cm_near if name == "near" else cm_muon
        r = f3d.scatter("u", "v", source=src, size="sz", fill_alpha="al",
                        marker=marker, line_color=None,
                        fill_color={"field": fld, "transform": cmap})
    elif col == "@col":
        hollow = name == "pftag"
        r = f3d.scatter("u", "v", source=src, size="sz", marker=marker,
                        fill_color=None if hollow else "col",
                        fill_alpha=0.0 if hollow else "al",
                        line_color="col", line_width=2.0 if hollow else 0.0,
                        line_alpha=1.0 if hollow else 0.0)
    else:
        r = f3d.scatter("u", "v", source=src, size="sz", fill_alpha="al",
                        marker=marker, fill_color=col,
                        line_color="#333333" if name in ("pin", "dots", "cursor",
                                                         "pfsel", "pfvtx") else None)
    SRC3[name] = src
    REND3[name] = r
    _PT_SRC.append(src); _PT_SIZE.append(sz); _PT_ALPHA.append(al)
    _PT_CUE.append(cue)
# The ONE table both mirrors read: fill3() looks a source up here and the JS gets
# the same three lists through args, so nothing else carries a base size.
_PT_CFG = {id(s): (sz, al, cue > 0.5)
           for s, sz, al, cue in zip(_PT_SRC, _PT_SIZE, _PT_ALPHA, _PT_CUE)}

det3_src = ColumnDataSource(dict(xs=[], ys=[], xs3=[], ys3=[], zs3=[]))
f3d.multi_line(xs="xs", ys="ys", source=det3_src, line_color="#cc4444",
               line_width=1, alpha=0.45)

cam_src = ColumnDataSource(name="cam3", data=dict(az=[math.radians(D3.PRESETS["iso"][0])],
                                el=[math.radians(D3.PRESETS["iso"][1])],
                                az0=[0.0], el0=[0.0],
                                cx=[0.0], cy=[0.0], cz=[0.0], R=[100.0],
                                xs0=[0.0], xe0=[0.0], ys0=[0.0], ye0=[0.0]))
camtxt = TextInput(value="", visible=False)
_JS_ARGS = dict(cam=cam_src, pts=_PT_SRC, ptsize=_PT_SIZE, ptalpha=_PT_ALPHA,
                ptcue=_PT_CUE, lines=[det3_src], heads=[])
_js_common = dict(_JS_ARGS, p=f3d, xr=f3d.x_range, yr=f3d.y_range, camtxt=camtxt)
js_panstart = CustomJS(args=_js_common, code=D3.JS_PANSTART)
js_rotate = CustomJS(args=_js_common, code=D3.JS_ROTATE)
js_panend = CustomJS(args=_js_common, code=D3.JS_PANEND)
js_apply = CustomJS(args=_JS_ARGS, code=D3.JS_APPLY)
f3d.js_on_event(PanStart, js_panstart)
f3d.js_on_event(Pan, js_rotate)
f3d.js_on_event(PanEnd, js_panend)
# Any Python push of cam_src.data re-runs the SAME projection in the browser, so
# the server's fill can never be the version left on screen.
cam_src.js_on_change("data", js_apply)


def fill3(name, X, Y, Z, extra=None):
    src = SRC3[name]
    sz, al, cue = _PT_CFG[id(src)]
    n = len(X)
    az, el = cam_src.data["az"][0], cam_src.data["el"][0]
    c = (cam_src.data["cx"][0], cam_src.data["cy"][0], cam_src.data["cz"][0])
    R = cam_src.data["R"][0] or 1.0
    uu, vv, aa, ss = [], [], [], []
    for u, v, d in D3.project(list(zip(X, Y, Z)), az, el, c):
        uu.append(u); vv.append(v)
        if cue:
            t = min(1.0, max(0.0, 0.5 + 0.5 * (d / R)))
            aa.append(al * (0.30 + 0.70 * t)); ss.append(sz * (0.70 + 0.60 * t))
        else:
            aa.append(al); ss.append(sz)
    d = dict(x=list(X), y=list(Y), z=list(Z), u=uu, v=vv, al=aa, sz=ss)
    for k, val in (extra or {}).items():
        d[k] = list(val)
    for k in _fields(name):
        d.setdefault(k, (["#cccccc"] if k == "col" else [0.0]) * n)
    src.data = d


def fill3_box():
    e = smgeom.ENVELOPE[DETNAME]
    (x0, x1), (y0, y1), (z0, z1) = e["x"], e["y"], e["z"]
    C = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    E = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7),
         (4, 5), (4, 6), (5, 7), (6, 7)]
    xs3 = [[C[i][0], C[j][0]] for i, j in E]
    ys3 = [[C[i][1], C[j][1]] for i, j in E]
    zs3 = [[C[i][2], C[j][2]] for i, j in E]
    az, el = cam_src.data["az"][0], cam_src.data["el"][0]
    c = (cam_src.data["cx"][0], cam_src.data["cy"][0], cam_src.data["cz"][0])
    xs, ys = [], []
    for a, b, cc in zip(xs3, ys3, zs3):
        pr = D3.project(list(zip(a, b, cc)), az, el, c)
        xs.append([p[0] for p in pr]); ys.append([p[1] for p in pr])
    det3_src.data = dict(xs=xs, ys=ys, xs3=xs3, ys3=ys3, zs3=zs3)


# ---------------------------------------------------------------------------
# the dQ/dx panel.  x is SIGNED ARC LENGTH THROUGH THE ORIGIN, not rr, because
# only the muon chain carries rr at all -- CheckSTM_Michel.cxx:682 writes
# rr = L = -1 for every Michel, delta and dot point.  Muon points sit at
# rr - rr(origin); everything else at MINUS its 3-D distance from the origin.
# The origin is your pin once you place one, and the fit's own last point until
# then.  So the panel separates muon from Michel exactly where YOU say the muon
# stopped, which is the quantity the downstream separation needs.
# ---------------------------------------------------------------------------
# CLICK a point here and it is echoed by a cyan cursor in the 3-D view, all
# three projections and all nine measurement panels -- so "what is that outlier
# at rr = 12 cm" is answered by pointing at it rather than by hunting.  Every
# scatter source therefore carries the point's own 3-D position AND its wire
# coordinates, and the callback just reads the tapped row: no index arithmetic
# between the panel's live-only rows and the chain arrays, which is where an
# off-by-a-few cursor would come from.
_tapq = TapTool()
fq = figure(title="dQ/dx vs signed arc length  (+ muon side, − Michel side)",
            height=330, width=620,
            tools=["pan", "wheel_zoom", "box_zoom", "reset", "save", _tapq],
            active_scroll="wheel_zoom",
            x_axis_label="signed arc length through the origin [cm]",
            y_axis_label="dQ/dx [e/cm]  —  click a point to locate it")
fq.toolbar.active_tap = _tapq
# a, b are the plotted pair; c the colour field; the rest ride along for the
# cursor.  ONE column list, so a fill that forgets one fails loudly.
QCOLS = ["a", "b", "c", "x", "y", "z", "pu", "pv", "pw", "pt"]
QSCAT = ("muon", "delta", "michel", "dots")
SRCQ = {}
for name, col, sz in (("ref_muon", "#333333", 0), ("ref_electron", "#8c564b", 0),
                      ("muon", "#000000", 6), ("delta", "#ff7f0e", 8),
                      ("michel", "#1f77b4", 9), ("dots", "#d62728", 11)):
    src = ColumnDataSource(dict(a=[], b=[]) if sz == 0
                           else {k: [] for k in QCOLS}, name="srcq_" + name)
    SRCQ[name] = src
    if sz == 0:
        fq.line("a", "b", source=src, color=col, line_width=2,
                line_dash="solid" if name == "ref_muon" else "dashed", alpha=0.8)
        continue
    # A thin dark outline on EVERY marker.  This is what makes the panel
    # readable independently of the palette: whatever the fill, the point has an
    # edge (doc pdhd/12 sec 5.6).
    common = dict(size=sz, alpha=0.92, line_color="#2b2b2b", line_width=0.6,
                  line_alpha=0.65, nonselection_alpha=0.92,
                  nonselection_line_alpha=0.65)
    if name == "muon":
        fq.scatter("a", "b", source=src,
                   fill_color={"field": "c", "transform": cm_muon}, **common)
    else:
        fq.scatter("a", "b", source=src, fill_color=col,
                   marker="diamond" if name == "dots" else "circle", **common)
fq.line("a", "b", source=ColumnDataSource(dict(a=[], b=[])), color="#e377c2")
SRCQ["origin"] = ColumnDataSource(dict(a=[], b=[]))
fq.line("a", "b", source=SRCQ["origin"], color="#e377c2", line_width=2,
        line_dash="dashed")


# ---------------------------------------------------------------------------
# the 2-D MEASUREMENT panels -- what the wires actually saw (doc pdhd/12 sec 5.4)
#
# Three rows (U, V, W) x three columns: the MEASURED charge in each (channel,
# time slice) cell, the charge the fitted track PREDICTS there, and their
# difference.  This is the content of a Magnify tracking display, from the same
# tree Magnify reads -- T_proj_data, one row per fitted cluster, written by
# PdvdPrMagnifyTrackingVisitor::write_proj_data.
#
# WHY IT IS HERE AT ALL.  Every other panel is reconstruction-space: 3-D points
# and a trajectory.  A track that looks clean in 3-D can be a fit riding on
# charge that is not there, and the only place that shows is the residual.  For
# this scan specifically, "did the muon stop or did it leave through a dead
# region" and "is the Michel a real deposit or a prediction artefact" are
# measurement-space questions.
#
# THREE THINGS THAT WOULD MAKE IT LIE, and what is done about each:
#  1. THE PLANE SPLIT.  channel is a per-plane RANK, not a LArSoft channel id;
#     a wrong split is silent (feedback_magnify_channel_is_a_plane_rank).
#     smgeom.BASE, gated causally -- see that module.
#  2. DEAD REGIONS.  Inside one, `charge` is not a measurement: Cell::charge()
#     falls back to prepare_data's FILLER when a slice has no live entry, and
#     the tree does not carry the flag.  So meas - pred there is model minus
#     model.  The dead bands are drawn OVER the cells for exactly that reason --
#     they are the only thing that says which residual cells mean anything.
#  3. THE SCALE.  A per-item colour scale makes items incomparable, which is
#     fatal for a hand scan.  Both scales are FIXED per (detector, plane), from
#     the measured distribution over both production arms, and the one control
#     the scanner has is a global multiplier that moves every item together.
# ---------------------------------------------------------------------------
PLANES = ("u", "v", "w")

# Top of the measured/predicted scale: the plane's p90 cell charge over ~30
# events of the production arm.  p90 rather than p99 because the p99 tail runs
# to 1.2e6 and would push the bulk (p50 ~ 3-12 ke) into the bottom tenth of the
# map.  Cells above the top saturate, which reads correctly as "a lot".
CELL_HIGH = {"pdhd": dict(u=5.6e4, v=5.7e4, w=3.1e4),
             "pdvd": dict(u=3.1e4, v=2.7e4, w=1.8e4)}
# Half-span of the symmetric residual scale: the plane's p99 |meas - pred|.
DIFF_SPAN = {"pdhd": dict(u=8.0e4, v=1.0e5, w=4.8e4),
             "pdvd": dict(u=4.5e4, v=3.6e4, w=2.1e4)}
CELL_MULT = [0.5, 1.0, 2.0, 4.0]
# Cell marker size in SCREEN pixels, not data units.  A rect one channel wide
# was the obvious choice and it drew NOTHING: the biggest item spans 2 322
# channels and 1 095 slices in a 430 x 300 px panel, so a data-unit cell is
# 0.16 x 0.27 px and antialiases to invisible.  Caught by the browser gate --
# emptying the cell sources changed the painted pixels by zero.  A screen-unit
# square is always visible, and zooming in separates the cells the normal way.
CELL_PX = [2, 3, 5, 8]

MEAS_COLS = [("q", "measured"), ("qp", "predicted"), ("d", "measured − predicted")]
SRCM, SRCD, SRCT, FIGM = {}, {}, {}, {}
CELL_REND = []
CM_CELL, CM_DIFF = {}, {}
_meas_y = Range1d(0, 1)                     # ONE time range for all nine panels
# The trajectory layers echoed into measurement space.  tagfit is deliberately
# absent: it is the cosmic tagger's fit, not this chain's, and nine more
# renderers of a secondary overlay buys nothing here.
MEAS_TRACKS = [("muon", "#000000", 3.0, False),
               ("delta", "#ff7f0e", 5.0, True),
               ("michel", "#1f77b4", 6.0, True),
               ("dots", "#d62728", 8.0, True),
               # the particle flow, in the space where the charge lives -- which
               # is where "is this branch a real deposit" is answerable
               ("pfvtx", "#8c564b", 9.0, False),
               ("pfsel", "#ffb000", 7.0, False),
               ("cursor", "#17becf", 15.0, False)]
MEAS_REND = {}

for pl in PLANES:
    CM_CELL[pl] = LinearColorMapper(palette=Turbo256, low=0.0,
                                    high=CELL_HIGH[DETNAME][pl])
    CM_DIFF[pl] = LinearColorMapper(palette=PAL_DIFF,
                                    low=-DIFF_SPAN[DETNAME][pl],
                                    high=DIFF_SPAN[DETNAME][pl])
    SRCM[pl] = ColumnDataSource(dict(ch=[], ts=[], q=[], qp=[], qe=[], d=[]),
                                name="srcm_" + pl)
    SRCD[pl] = ColumnDataSource(dict(left=[], right=[], bottom=[], top=[]),
                                name="srcd_" + pl)
    for nm, _c, _sz, _rv in MEAS_TRACKS:
        SRCT[(pl, nm)] = ColumnDataSource(dict(w=[], t=[]),
                                          name="srct_%s_%s" % (pl, nm))
    # ONE x range per row: the three columns MUST show the same window or the
    # eye compares three different pictures and the difference panel answers
    # nothing.  y (time) is shared across all nine.
    xr = Range1d(0, 1)
    for fld, cname in MEAS_COLS:
        f = figure(height=300, width=430, x_range=xr, y_range=_meas_y,
                   tools="pan,wheel_zoom,box_zoom,reset,save",
                   active_scroll="wheel_zoom",
                   x_axis_label="%s channel (global rank)" % pl.upper(),
                   y_axis_label="time slice")
        f.title.text = "%s — %s" % (pl.upper(), cname)
        f.title.text_font_size = "10pt"
        # dead channels UNDER, as a solid band: a dead region with no cells at
        # all has to read as "dead", not as "nothing was there".
        f.quad(left="left", right="right", bottom="bottom", top="top",
               source=SRCD[pl], fill_color="#b9b9b9", fill_alpha=0.5,
               line_color=None, level="underlay")
        r = f.scatter(x="ch", y="ts", marker="square", size=CELL_PX[1],
                      source=SRCM[pl], line_color=None,
                      fill_color={"field": fld,
                                  "transform": CM_DIFF[pl] if fld == "d" else CM_CELL[pl]})
        CELL_REND.append(r)
        # ... and again OVER, hatched, so a residual sitting inside a dead
        # region cannot be read as a measurement.
        f.quad(left="left", right="right", bottom="bottom", top="top",
               source=SRCD[pl], fill_color="#000000", fill_alpha=0.10,
               hatch_pattern="/", hatch_alpha=0.30, hatch_color="#000000",
               line_color="#666666", line_alpha=0.45, line_width=0.5)
        for nm, col, sz, _rv in MEAS_TRACKS:
            src = SRCT[(pl, nm)]
            if nm == "muon":
                # A THIN, SEMI-TRANSPARENT line and no markers.  The first
                # version drew a 3 px white halo, a 1.2 px black line and a
                # marker per fit point on top -- and since the cluster's cells
                # ARE the track's own cells, at full-cluster zoom (2 300
                # channels in 430 px) they land on the same pixels and the
                # overlay painted the entire measurement out.  The picture
                # looked like an empty panel with a track drawn on it.  The
                # cells are the evidence; the trajectory is the annotation, and
                # it has to read as one.
                f.line("w", "t", source=src, color="#ffffff", line_width=2.2,
                       alpha=0.40)
                f.line("w", "t", source=src, color="#000000", line_width=0.9,
                       alpha=0.55)
                MEAS_REND.setdefault(nm, []).append(
                    f.scatter("w", "t", source=src, size=1.4, color="#000000",
                              line_color=None, alpha=0.45))
                continue
            rr = f.scatter("w", "t", source=src, size=sz, color=col,
                           marker="circle_cross" if nm == "cursor" else "circle",
                           line_color="#333333" if nm in ("dots", "cursor") else None,
                           fill_alpha=0.85, line_alpha=0.9)
            MEAS_REND.setdefault(nm, []).append(rr)
        f.add_tools(HoverTool(renderers=[r], tooltips=[
            ("channel", "@ch{0}"), ("slice", "@ts{0}"),
            ("measured", "@q{0} e"), ("predicted", "@qp{0} e"),
            ("meas−pred", "@d{0} e"), ("err", "@qe{0} e")]))
        FIGM[(pl, fld)] = f
    FIGM[(pl, "xr")] = xr
    FIGM[(pl, "cb")] = ColorBar(color_mapper=CM_CELL[pl], width=8,
                                label_standoff=4, padding=2)
    FIGM[(pl, "q")].add_layout(FIGM[(pl, "cb")], "right")
    FIGM[(pl, "d")].add_layout(ColorBar(color_mapper=CM_DIFF[pl], width=8,
                                        label_standoff=4, padding=2), "right")

cell_scale = RadioButtonGroup(labels=["×0.5", "×1", "×2", "×4"], active=1, width=210)
cell_size = RadioButtonGroup(labels=["2 px", "3 px", "5 px", "8 px"], active=1, width=210)
# The whole cluster is what Magnify shows and it is the right default -- but a
# 677 cm muon spans 2 300 channels, and the Michel lives in the last 30 of them.
MEAS_WIN = 150
meas_zoom = RadioButtonGroup(labels=["whole cluster", "± %d around the stop" % MEAS_WIN],
                             active=0, width=280)
meas_note = Div(width=1320, text="")


def apply_cell_size():
    for r in CELL_REND:
        r.glyph.size = CELL_PX[cell_size.active]


def _fmt_e(v):
    return "%.0fk" % (v / 1e3)


def apply_cell_scale():
    m = CELL_MULT[cell_scale.active]
    for pl in PLANES:
        CM_CELL[pl].high = CELL_HIGH[DETNAME][pl] * m
        CM_DIFF[pl].low = -DIFF_SPAN[DETNAME][pl] * m
        CM_DIFF[pl].high = DIFF_SPAN[DETNAME][pl] * m
    meas_note.text = (
        "<span style='font-size:90%%'><b>2-D measurement</b> — every (channel, time slice) "
        "cell of this cluster, from T_proj_data. Colour scales are <b>FIXED per plane</b> "
        "(× %g): charge 0–%s / 0–%s / 0–%s e for U/V/W, residual ±%s / ±%s / ±%s e, so two "
        "items are comparable. Grey hatched = dead channel — <b>inside one, `measured` is "
        "the imaging model's filler, not a reading, so the residual there means nothing.</b> "
        "Black line = the CheckSTM_Michel PR fit (0.600 cm steps); click a point in the "
        "dQ/dx panel to drop the cyan cursor here.</span>"
        % (m, _fmt_e(CELL_HIGH[DETNAME]["u"] * m), _fmt_e(CELL_HIGH[DETNAME]["v"] * m),
           _fmt_e(CELL_HIGH[DETNAME]["w"] * m), _fmt_e(DIFF_SPAN[DETNAME]["u"] * m),
           _fmt_e(DIFF_SPAN[DETNAME]["v"] * m), _fmt_e(DIFF_SPAN[DETNAME]["w"] * m)))


apply_cell_scale()
apply_cell_size()


def blank_meas():
    for pl in PLANES:
        SRCM[pl].data = dict(ch=[], ts=[], q=[], qp=[], qe=[], d=[])
        SRCD[pl].data = dict(left=[], right=[], bottom=[], top=[])
        for nm, _c, _sz, _rv in MEAS_TRACKS:
            SRCT[(pl, nm)].data = dict(w=[], t=[])


def _wt(block, pl):
    """(wire, time) of a chain block in one plane, dropping unjoined points."""
    if not block:
        return [], []
    W = np.asarray([np.nan if t is None else t for t in (block.get("p" + pl) or [])], float)
    T = np.asarray([np.nan if t is None else t for t in (block.get("pt") or [])], float)
    if W.size != T.size or not W.size:
        return [], []
    k = np.isfinite(W) & np.isfinite(T)
    return [float(t) for t in W[k]], [float(t) for t in T[k]]


def fill_meas(pay, v, rev, pin=None):
    """The nine panels for one item.  `v` is empty unless REVEAL is on.

    `pin` is the (x, y, z) origin; when the scanner asks for the stop window,
    the panels centre on THAT point's own wire coordinates -- taken from the
    nearest chain point, so the window is in the same numbers the panel plots
    rather than a geometric guess.
    """
    stop_w = {}
    if pin is not None:
        m = pay.get("muon") or {}
        MX = np.c_[np.asarray(m.get("x") or [], float),
                   np.asarray(m.get("y") or [], float),
                   np.asarray(m.get("z") or [], float)]
        if MX.size:
            i = int(np.argmin(((MX - np.asarray(pin, float)) ** 2).sum(axis=1)))
            for pl in PLANES:
                w = (m.get("p" + pl) or [None] * len(MX))[i]
                t = (m.get("pt") or [None] * len(MX))[i]
                if w is not None and t is not None:
                    stop_w[pl] = (float(w), float(t))
    blank_meas()
    prj = pay.get("proj") or {}
    dead = pay.get("dead") or {}
    tlo, thi = [], []
    for pl in PLANES:
        c = prj.get(pl) or dict(ch=[], ts=[], q=[], qp=[], qe=[])
        ch = np.asarray(c["ch"], float); ts = np.asarray(c["ts"], float)
        q = np.asarray(c["q"], float); qp = np.asarray(c["qp"], float)
        qe = np.asarray(c["qe"], float)
        SRCM[pl].data = dict(ch=list(ch), ts=list(ts), q=list(q), qp=list(qp),
                             qe=list(qe), d=list(q - qp))
        mw, mt = _wt(pay.get("muon"), pl)
        SRCT[(pl, "muon")].data = dict(w=mw, t=mt)
        if rev:
            for nm in ("delta", "michel", "dots"):
                w_, t_ = _wt(v.get(nm), pl)
                SRCT[(pl, nm)].data = dict(w=w_, t=t_)
        allw = list(ch) + mw
        allt = list(ts) + mt
        xr = FIGM[(pl, "xr")]
        if meas_zoom.active == 1 and pl in stop_w:
            xr.start, xr.end = stop_w[pl][0] - MEAS_WIN, stop_w[pl][0] + MEAS_WIN
            tlo.append(stop_w[pl][1] - MEAS_WIN); thi.append(stop_w[pl][1] + MEAS_WIN)
        elif allw:
            lo, hi = min(allw), max(allw)
            pad = max(3.0, 0.04 * (hi - lo))
            xr.start, xr.end = lo - pad, hi + pad
            tlo.append(min(allt)); thi.append(max(allt))
        else:
            xr.start, xr.end = smgeom.plane_span(DETNAME, PLANES.index(pl))
        # dead bands, clipped to the drawn box so a whole-readout band does not
        # decide the time range
        d = dead.get(pl) or dict(ch=[], t0=[], t1=[])
        keep = [i for i, cc in enumerate(d["ch"]) if xr.start <= cc <= xr.end]
        SRCD[pl].data = dict(
            left=[d["ch"][i] - 0.5 for i in keep], right=[d["ch"][i] + 0.5 for i in keep],
            bottom=[d["t0"][i] for i in keep], top=[d["t1"][i] for i in keep])
    if tlo:
        lo, hi = min(tlo), max(thi)
        pad = 0.0 if meas_zoom.active == 1 else max(5.0, 0.05 * (hi - lo))
        _meas_y.start, _meas_y.end = lo - pad, hi + pad
    else:
        _meas_y.start, _meas_y.end = 0, 1
    for nm, _c, _sz, rv in MEAS_TRACKS:
        for r in MEAS_REND.get(nm, []):
            r.visible = (rev or not rv)
    # blank_meas() cleared every SRCT above; the PF ones are refilled by
    # fill_pf_meas(), which render() calls immediately after this.


# ---------------------------------------------------------------------------
# widgets
# ---------------------------------------------------------------------------
def item_option(it):
    rec = LABELS.get(item_key(it), {})
    mark = rec.get("choice", "")
    return "%3d %s t%d  evt %s cl %d  n=%d  %.0f cm%s" % (
        it["scan_id"], "*" if mark else " ", it["tranche"], it["event"],
        it["cluster"], it["npts"], it["muon_len"],
        ("   [%s]" % mark) if mark else "")


item_select = Select(title="Scan item", value=item_option(ITEMS[0]),
                     options=[item_option(i) for i in ITEMS], width=430)
prev_btn = Button(label="< prev", width=90)
next_btn = Button(label="next >", width=90)
next_unl_btn = Button(label="next unlabelled >>", width=160)

stm_mic_btn = Button(label="STM + MICHEL", button_type="success", width=190)
stm_only_btn = Button(label="STM, no Michel", button_type="success", width=170)
thru_btn = Button(label="THRU (through-going / exits)", button_type="primary", width=240)
frag_mic_btn = Button(label="FRAG → STM + MICHEL", button_type="success", width=210)
frag_only_btn = Button(label="FRAG → STM, no Michel", button_type="success", width=210)
frag_thru_btn = Button(label="FRAG → THRU", button_type="primary", width=160)
messy_btn = Button(label="MESSY (not one track)", button_type="warning", width=190)
uncl_btn = Button(label="UNCLEAR", button_type="warning", width=120)
clear_btn = Button(label="clear this label", width=130)

michel_kind = RadioButtonGroup(labels=MICHEL_KINDS, active=0, width=560)
reveal_tog = Toggle(label="REVEAL the reconstruction", width=230)
zoom_tog = Toggle(label="Zoom to object", width=140)
# doc pdhd/13 sec 4: the Bee layer draws EVERY cluster at its OWN bundle's
# t0-corrected position, so an unrelated cosmic thousands of us away in drift
# time can land centimetres from the muon and read as over-clustering.  ON by
# default; turning it off restores the old picture exactly, with the
# out-of-bundle charge recoloured rather than hidden.
bundle_tog = Toggle(label="bundle only", button_type="default", width=130, active=True)
bundle_div = Div(text="", width=620)
rr_slider = Slider(start=0.0, end=100.0, value=0.0, step=0.1, width=430,
                   title="pin the stopping point at residual range [cm]")
pin_clear_btn = Button(label="unset pin", width=110)
off_fit_chk = CheckboxGroup(labels=["the true stop is OFF the fit"], active=[], width=250)
manual_x = TextInput(title="x", width=100)
manual_y = TextInput(title="y", width=100)
manual_z = TextInput(title="z", width=100)
manual_btn = Button(label="pin at x,y,z", width=110)
notes = TextInput(title="notes (optional) — type BEFORE clicking a label", width=430)
progress = Div(text="", width=620)
badge = Div(text="", width=1420)
status = Div(text="", width=1420, name="status_div")
reveal_div = Div(text="", width=620)
flow_div = Div(text="", width=1420, name="flow_div")
cursor_div = Div(text="", width=620)
save_div = Div(text="", width=620)
pf_tog = Toggle(label="show particle flow", button_type="default", width=200)
seg_select = Select(title="PF segment (pick one to highlight and tag it)",
                    options=[], value="", width=430)
seg_div = Div(text="", width=620)
pf_mu_btn = Button(label="muon", button_type="primary", width=105)
pf_mic_btn = Button(label="Michel", button_type="danger", width=105)
pf_oth_btn = Button(label="delta / other", button_type="default", width=125)
pf_mix_btn = Button(label="straddles the stop", button_type="warning", width=165)
pf_clr_btn = Button(label="untag", button_type="default", width=90)
save_info_btn = Button(label="what is saved on disk?", button_type="default", width=200)

header = Div(width=1420, text="""
<b>%s stopping-muon + Michel-electron hand scan</b> &mdash; doc pdhd/12.
<br><b>Judge the charge.</b> Does the object enter the detector and <b>stop</b> inside,
and is there a <b>Michel electron</b> at the stop?
<br><span style="color:#555">Colour = every imaged point within 20&nbsp;cm of the fitted
muon (and 40&nbsp;cm of its stopping end), at full density. Grey = the rest of the event,
thinned. Black-outlined line = the fitted muon, coloured by its own dQ/dx. Red dashed =
the active boundary; purple dotted = the APA&nbsp;/&nbsp;CRP seams.
<br><b>Place the pin</b> where you think the muon stopped &mdash; tap any panel, or drag
the slider. The dQ/dx panel re-anchors on it, so the muon side and the Michel side
separate exactly where you say. It starts at the drawn chain's own last point, which is
the reconstruction's stopping point on 98&nbsp;%% of objects &mdash; so this is asking
whether you <i>agree</i>, and the label records how far you moved it.
<br><b>2-D measurement</b> is the third tab: what the wires actually saw, what the fit
predicts they should have seen, and the difference &mdash; per plane, with the dead
channels hatched. The fit drawn everywhere is the <b>CheckSTM_Michel PR</b> chain
(uniform 0.600&nbsp;cm step); the cosmic tagger's own fit is the grey REVEAL layer only.
<br><b>Click a point in the dQ/dx panel</b> and a cyan cursor marks it in the 3-D view,
in all three projections and in all nine measurement panels.
<br><b>show particle flow</b> draws the PR graph &mdash; its segments and junction
vertices. Pick a segment and tag it muon / Michel / delta / straddles-the-stop; your
tags are hollow squares, never confusable with the reconstruction's colours.
<br><b>Every save is read back from the file</b> &mdash; the banner under the buttons
says what is actually on disk, and <i>what is saved on disk?</i> prints this item's row.
<br><b>REVEAL</b> shows what the reconstruction decided. Every label records whether you
had revealed it, so a revealed label is still usable &mdash; it is just scored separately.
</span>""" % DETNAME.upper())

state = dict(idx=0, pin=None, pin_i=None, pin_manual=None, cursor=None,
             pf_tag={}, pf_seg=None)


def current():
    return ITEMS[state["idx"]]


# ---------------------------------------------------------------------------
# the pin
# ---------------------------------------------------------------------------
def muon_arrays(pay):
    m = pay["muon"]
    return (np.asarray(m["x"], float), np.asarray(m["y"], float),
            np.asarray(m["z"], float), np.asarray(m["q"], float),
            np.asarray(m["rr"], float))


def pin_point(pay):
    """(x, y, z, rr, source) of the current origin.

    `source` is 'pin' when the scanner placed it, 'manual' for a typed x/y/z and
    'fit-end' for the untouched default -- the fit's own last point.  That
    default IS the chain's `stop_*` scalar on 97.7 % of items (see the module
    docstring); it is not offered as a blind starting value, only as the
    already-visible end of the drawn trajectory.
    """
    if state["pin_manual"] is not None:
        x, y, z = state["pin_manual"]
        return x, y, z, None, "manual"
    if pay is None:
        return None
    X, Y, Z, Q, RR = muon_arrays(pay)
    if not X.size:
        return None
    i = state["pin_i"]
    if i is None:
        i = int(np.argmin(RR))
        return float(X[i]), float(Y[i]), float(Z[i]), float(RR[i]), "fit-end"
    i = int(min(max(i, 0), X.size - 1))
    return float(X[i]), float(Y[i]), float(Z[i]), float(RR[i]), "pin"


def set_pin_index(i):
    state["pin_i"] = int(i)
    state["pin_manual"] = None
    off_fit_chk.active = []
    render()


def snap_2d(ha, va, ax, bx):
    pay = payload(current())
    if pay is None:
        return
    X, Y, Z, Q, RR = muon_arrays(pay)
    axes = dict(x=X, y=Y, z=Z)
    d = (axes[ha] - ax) ** 2 + (axes[va] - bx) ** 2
    if d.size:
        set_pin_index(int(np.argmin(d)))


def snap_3d(u0, v0):
    pay = payload(current())
    if pay is None:
        return
    X, Y, Z, Q, RR = muon_arrays(pay)
    az, el = cam_src.data["az"][0], cam_src.data["el"][0]
    c = (cam_src.data["cx"][0], cam_src.data["cy"][0], cam_src.data["cz"][0])
    pr = D3.project(list(zip(X, Y, Z)), az, el, c)
    if not pr:
        return
    d = [(u - u0) ** 2 + (v - v0) ** 2 for u, v, _ in pr]
    set_pin_index(int(np.argmin(np.asarray(d))))


def pin_unit(pay, px, py, pz, src):
    """(unit, cru, face, how) for the pinned point.

    The wire route is primary: T_rec_charge's pw is a readout fact and needs no
    T0, while sign(x) is unsafe on PDVD, where the two drift volumes overlap in
    the pre-T0 apparent-x frame (protodunevd/clus.jsonnet:80-84) and this scan
    looks at exactly the out-of-time cosmics that lands on.  A manual pin has no
    wire, so it falls back to geometry and SAYS so.

    When the two routes DISAGREE the badge says so rather than picking silently.
    Measured over every chain point of both arms they agree 97718/97721 (PDHD)
    and 166031/166037 (PDVD), and every exception is the writer's default wire
    smgeom.SENTINEL_PW -- a fit point whose (apa, face, wire) was never filled.
    A pin that lands on one of those must not be labelled with confidence.
    """
    gu, gc, gf = smgeom.unit_from_geometry(DETNAME, px, py, pz)
    if src != "manual":
        X, Y, Z, Q, RR = muon_arrays(pay)
        pws = pay["muon"].get("pw") or []
        if len(pws) == X.size:
            d = (X - px) ** 2 + (Y - py) ** 2 + (Z - pz) ** 2
            j = int(np.argmin(d))
            w = pws[j]
            u, c, f = smgeom.unit_from_wire(DETNAME, w)
            if u is not None:
                if u == gu:
                    return u, c, f, "wire"
                how = "wire, DISPUTED: geometry says %s" % (
                    smgeom.unit_label(DETNAME, gu, gc, gf).split(" ")[0])
                if w is not None and int(w) == smgeom.SENTINEL_PW[DETNAME]:
                    how += " — this fit point carries the writer's DEFAULT wire"
                return u, c, f, how
    return gu, gc, gf, "geometric"


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------
def blank():
    for k in SRC2:
        d = dict(a=[], b=[])
        for x in _fields(k[2]):
            d[x] = []
        SRC2[k].data = d
    for n in SRC3:
        fill3(n, [], [], [])
    for n in SRCQ:
        SRCQ[n].data = ({k: [] for k in QCOLS} if n in QSCAT else dict(a=[], b=[]))
    blank_meas()
    clear_cursor()


def render():
    it = current()
    pay = payload(it)
    rev = bool(reveal_tog.active)
    for name in REVEAL_LAYERS:
        for ha, va, _t in PANELS:
            REND2[(ha, va, name)].visible = rev
        REND3[name].visible = rev
    if pay is None:
        blank()
        badge.text = ""
        status.text = ("<b style='color:#b00'>missing payload</b> for %s "
                       "&mdash; run prep_stm_michel_scan.py --det %s"
                       % (item_key(it), DETNAME))
        return

    X, Y, Z, Q, RR = muon_arrays(pay)
    near, far = pay["image_near"], pay["image_far"]
    v = pay.get("verdict", {}) if rev else {}

    # cm_muon is FIXED at 0..DQDX_HIGH for every item on both detectors -- see
    # the palette block.  Only the context layer still adapts.
    nq = np.asarray(_bundle_near(pay, near).get("q") or [], float)
    cm_near.low = 0.0
    cm_near.high = float(np.percentile(nq[nq > 0], 98)) if (nq > 0).any() else 4e4

    # the scanner's own per-segment answer, restored from the saved row
    rec0 = LABELS.get(item_key(it), {})
    if state.get("_pf_item") != item_key(it):
        state["pf_tag"] = dict(rec0.get("pf_segments") or {})
        state["pf_seg"] = None
        state["_pf_item"] = item_key(it)
    refresh_segments(pay)

    P = pin_point(pay)
    px, py, pz, prr, psrc = P
    (near, far, outb, nb_hidden) = split_bundle(pay, near, far)
    layers = {
        "far": (far["x"], far["y"], far["z"], {}),
        "outb": (outb["x"], outb["y"], outb["z"], {}),
        "near": (near["x"], near["y"], near["z"], {"q": near.get("q") or []}),
        "muon": (list(X), list(Y), list(Z), {"c": list(Q)}),
        "pin": ([px], [py], [pz], {}),
    }
    if rev:
        for nm in ("delta", "michel", "dots"):
            g = v.get(nm) or dict(x=[], y=[], z=[])
            layers[nm] = (g["x"], g["y"], g["z"], {})
        tf = v.get("tagger_fit") or []
        tx = [a for s in tf for a in s["x"]]
        ty = [a for s in tf for a in s["y"]]
        tz = [a for s in tf for a in s["z"]]
        tc = [a for s in tf for a in s["dqdx"]]
        layers["tagfit"] = (tx, ty, tz, {"c": tc})
        for nm, pre in (("entry", "entry"), ("stop", "stop"), ("tstop", "tagger_stop")):
            if pre + "_x" in v:
                layers[nm] = ([v[pre + "_x"]], [v[pre + "_y"]], [v[pre + "_z"]], {})
    layers.update(fill_pf(pay, v, rev))
    for nm, _sz, _al, _c, _mk, rv, _cue in LAYERS:
        if nm not in layers:
            layers[nm] = ([], [], [], {})

    axes_of = dict(x=0, y=1, z=2)
    for ha, va, _t in PANELS:
        for nm, (lx, ly, lz, ex) in layers.items():
            arr = (lx, ly, lz)
            d = dict(a=list(arr[axes_of[ha]]), b=list(arr[axes_of[va]]))
            for k in _fields(nm):
                d[k] = list(ex.get(k, [0.0] * len(d["a"])))
                if len(d[k]) != len(d["a"]):
                    d[k] = [0.0] * len(d["a"])
            SRC2[(ha, va, nm)].data = d
        f = FIG2[(ha, va)]
        if zoom_tog.active and X.size:
            arr = dict(x=X, y=Y, z=Z)
            f.x_range.start = float(arr[ha].min() - PAD)
            f.x_range.end = float(arr[ha].max() + PAD)
            f.y_range.start = float(arr[va].min() - PAD)
            f.y_range.end = float(arr[va].max() + PAD)
        else:
            f.x_range.start, f.x_range.end = VOL[ha][0] - PAD, VOL[ha][1] + PAD
            f.y_range.start, f.y_range.end = VOL[va][0] - PAD, VOL[va][1] + PAD

    refit_camera(X, Y, Z)
    fill3_box()
    for nm, (lx, ly, lz, ex) in layers.items():
        fill3(nm, lx, ly, lz, ex)
    show_bundle(pay, nb_hidden)

    fill_dqdx(pay, v, px, py, pz, prr, psrc, rev)
    fill_meas(pay, v, rev, (px, py, pz))
    fill_pf_meas(pay, rev)
    fill_seg_div(pay, v, rev)
    # a cursor from the previous item would point at a point that is no longer
    # on screen; and render() runs on REVEAL too, where the tapped point may
    # have just been hidden.
    clear_cursor()
    fill_badge(it, pay, px, py, pz, prr, psrc)
    fill_reveal(v, rev)
    fill_flow(v, rev)

    rec = LABELS.get(item_key(it), {})
    notes.value = rec.get("notes", "")
    mk = rec.get("michel_kind")
    michel_kind.active = MICHEL_KINDS.index(mk) if mk in MICHEL_KINDS else 0
    michel_kind.width = 560
    done = sum(1 for i in ITEMS if item_key(i) in LABELS)
    t1 = [i for i in ITEMS if i["tranche"] == 1]
    d1 = sum(1 for i in t1 if item_key(i) in LABELS)
    progress.text = ("<b>%d / %d</b> labelled &nbsp;|&nbsp; tranche 1: <b>%d / %d</b>"
                     " &nbsp;|&nbsp; this item: <b>%s</b>"
                     % (done, len(ITEMS), d1, len(t1), rec.get("choice", "&mdash;")))
    # The muon's KE rides on the un-blinded line beside muon_len, which the
    # sheet already shows: muon_ke_best is cal_kine_range(muon_len, 13) for
    # every chain over 4 cm, so it is that same number in MeV and leaks nothing
    # about the Michel.  Both routes are named because they DISAGREE (222 vs
    # 278 MeV on 039252_15/77) and the scanner should see that, not one number
    # picked silently.  Absent on a pre-doc-14 arm -> say so, invent nothing.
    ke = _muon_ke_text(pay.get("verdict") or {})
    status.text = ("event %s cluster %d &mdash; %d chain points over %.1f cm%s, "
                   "%d image points at full density, %d thinned context points"
                   % (it["event"], it["cluster"], X.size, it["muon_len"], ke,
                      len(near["x"]), len(far["x"])))


def refit_camera(X, Y, Z):
    pts = list(zip(X, Y, Z))
    c, R = D3.bounding_sphere(pts, pad=1.25, floor=30.0) if pts else ((0, 0, 0), 100.0)
    d = dict(cam_src.data)
    d["cx"], d["cy"], d["cz"], d["R"] = [c[0]], [c[1]], [c[2]], [R]
    cam_src.data = d
    # Range1d, never DataRange1d: an auto range would re-fit on every drag frame
    # and the object would breathe as it turned.
    f3d.x_range.start, f3d.x_range.end = -R, R
    f3d.y_range.start, f3d.y_range.end = -R, R


def _col(block, key, mask):
    """block[key] as a float array under `mask`, None -> NaN, absent -> all NaN.

    A payload written before the wire columns existed still renders; the point
    is simply not locatable in measurement space, which is honest.
    """
    n = int(np.count_nonzero(mask)) if mask is not None else 0
    raw = (block or {}).get(key)
    if raw is None:
        return np.full(n, np.nan)
    a = np.asarray([np.nan if t is None else t for t in raw], float)
    if a.size != np.asarray(mask).size:
        return np.full(n, np.nan)
    return a[mask]


def _qdata(*cols):
    return {k: [float(t) for t in c] for k, c in zip(QCOLS, cols)}


def show_save(after_write=True):
    """The save banner, filled from the READ-BACK, never from the write."""
    ok, n, nb, mt, err = read_back()
    if not ok:
        save_div.text = ("<div style='background:#ffe6e6;padding:6px'>"
                         "<b style='color:#b00'>NOT SAVED &mdash; %s</b><br>"
                         "<span style='font-size:85%%'>%s</span></div>"
                         % (err, LABEL_FILE))
        return
    save_div.text = (
        "<div style='background:%s;padding:6px;font-size:92%%'><b>%s</b> "
        "&mdash; the file on disk holds <b>%d</b> label%s, %s bytes, last written "
        "%s<br><span style='font-size:88%%;color:#555'>%s</span></div>"
        % ("#e8f6e8" if after_write else "#f2f2f2",
           "saved and read back" if after_write else "labels on disk",
           n, "" if n == 1 else "s", "{:,}".format(nb), mt, LABEL_FILE))
    if n == 0:
        save_div.text = save_div.text.replace(
            "the file on disk holds <b>0</b> labels",
            "<b>nothing saved yet</b> &mdash; the file holds 0 labels")


def save_info():
    """The button: re-read the file and print THIS item's row out of it."""
    ok, n, nb, mt, err = read_back()
    show_save(after_write=False)
    if not ok:
        status.text = ("<b style='color:#b00'>could not read %s: %s</b>"
                       % (LABEL_FILE, err))
        return
    key = item_key(current())
    try:
        with open(LABEL_FILE) as fh:
            rec = json.load(fh).get("labels", {}).get(key)
    except Exception as ex:                       # noqa: BLE001
        rec = None
        err = str(ex)
    if rec is None:
        status.text = ("<b>%d label%s on disk</b> (%s bytes, %s). "
                       "<b style='color:#b00'>This item (%s) is NOT among them.</b>"
                       % (n, "" if n == 1 else "s", "{:,}".format(nb), mt, key))
        return
    keep = ("label", "choice", "partial", "michel_kind", "revealed_before_label",
            "notes", "pf_tagged")
    bits = ["<b>%s</b> = %s" % (k, rec.get(k)) for k in keep if k in rec]
    pin = rec.get("pin") or {}
    if pin:
        bits.append("<b>pin</b> = (%.1f, %.1f, %.1f) rr %s, placed %s, moved %s cm, %s"
                    % (pin.get("x", 0), pin.get("y", 0), pin.get("z", 0),
                       pin.get("rr"), pin.get("placed"), pin.get("moved_cm"),
                       smgeom.unit_label(DETNAME, pin.get("unit"), pin.get("cru"),
                                         pin.get("face"))))
    seg = rec.get("pf_segments") or {}
    if seg:
        bits.append("<b>pf_segments</b> = %s"
                    % ", ".join("%s:%s" % (k, v) for k, v in sorted(seg.items())))
    status.text = ("<div style='background:#eef4ff;padding:6px'><b>%s</b> is on disk "
                   "(%d label%s in the file, %s bytes, written %s):<br>%s</div>"
                   % (key, n, "" if n == 1 else "s", "{:,}".format(nb), mt,
                      " &nbsp;|&nbsp; ".join(bits)))


def clear_cursor():
    state["cursor"] = None
    fill3("cursor", [], [], [])
    for ha, va, _t in PANELS:
        SRC2[(ha, va, "cursor")].data = dict(a=[], b=[])
    for pl in PLANES:
        SRCT[(pl, "cursor")].data = dict(w=[], t=[])
    cursor_div.text = ("<span style='color:#777'>click a point in the dQ/dx panel "
                       "to locate it in every other view</span>")


def set_cursor(src, i):
    """Echo one dQ/dx point into the 3-D view, the projections and the wires."""
    d = src.data
    if i is None or i < 0 or i >= len(d.get("a", [])):
        return clear_cursor()
    g = lambda k: (float(d[k][i]) if k in d and i < len(d[k]) else float("nan"))
    x, y, z = g("x"), g("y"), g("z")
    state["cursor"] = (x, y, z)
    fill3("cursor", [x], [y], [z])
    axes = dict(x=x, y=y, z=z)
    for ha, va, _t in PANELS:
        SRC2[(ha, va, "cursor")].data = dict(a=[axes[ha]], b=[axes[va]])
    t = g("pt")
    for pl in PLANES:
        w = g("p" + pl)
        ok = math.isfinite(w) and math.isfinite(t)
        SRCT[(pl, "cursor")].data = dict(w=[w] if ok else [], t=[t] if ok else [])
    u, cr, fa = smgeom.unit_from_wire(DETNAME, None if not math.isfinite(g("pw")) else g("pw"))
    cursor_div.text = (
        "<div style='background:#e6f7f9;padding:5px;font-size:95%%'><b>cursor</b> "
        "&nbsp; arc %.2f cm &nbsp; dQ/dx %.0f e/cm &nbsp;|&nbsp; x %.1f y %.1f z %.1f cm"
        " &nbsp;|&nbsp; U %s &nbsp; V %s &nbsp; W %s &nbsp; slice %s &nbsp;|&nbsp; %s</div>"
        % (g("a"), g("b"), x, y, z,
           "—" if not math.isfinite(g("pu")) else "%.1f" % g("pu"),
           "—" if not math.isfinite(g("pv")) else "%.1f" % g("pv"),
           "—" if not math.isfinite(g("pw")) else "%.1f" % g("pw"),
           "—" if not math.isfinite(t) else "%.1f" % t,
           smgeom.unit_label(DETNAME, u, cr, fa)))


# ---------------------------------------------------------------------------
# the particle flow -- the PR graph CheckSTM_Michel actually walked
# ---------------------------------------------------------------------------
def pf_segments(pay):
    return ((pay or {}).get("pf") or {}).get("seg") or []


def seg_label(sg, tag):
    return "S%d   %d pts   %.1f cm%s%s" % (
        sg["id"], sg["npts"], sg["len_cm"],
        "" if sg.get("dqdx_med") is None else "   %.0f e/cm" % sg["dqdx_med"],
        "" if not tag else "   [%s]" % tag)


def refresh_segments(pay, keep=True):
    """Rebuild the segment dropdown, preserving the current pick if it survives."""
    segs = pf_segments(pay)
    opts = [seg_label(sg, state["pf_tag"].get(str(sg["id"]))) for sg in segs]
    cur = state["pf_seg"]
    seg_select.options = opts
    if opts:
        idx = next((i for i, sg in enumerate(segs) if str(sg["id"]) == str(cur)), None)
        seg_select.value = opts[idx] if (keep and idx is not None) else opts[0]
        state["pf_seg"] = segs[seg_select.options.index(seg_select.value)]["id"]
    else:
        seg_select.value = ""
        state["pf_seg"] = None


def _bundle_mask(g, n):
    """per-point in-bundle flags, defaulting to all-in when the prep had none"""
    b = g.get("b")
    if not b or len(b) != n:
        return None
    return [bool(t) for t in b]


def _bundle_near(pay, near):
    """the near layer as it will actually be drawn, for the colour scale"""
    if not bundle_tog.active or pay.get("bundle") is None:
        return near
    m = _bundle_mask(near, len(near.get("x") or []))
    if m is None:
        return near
    return {k: [w for w, keep in zip(near.get(k) or [], m) if keep]
            for k in ("x", "y", "z", "q")}


def split_bundle(pay, near, far):
    """(near, far, out_of_bundle, n_hidden), honouring the `bundle only` control.

    doc pdhd/13 sec 4.  With the control ON, only charge sharing the muon's
    (flash_id, cluster_t0_us) is drawn.  With it OFF nothing is lost: the
    out-of-bundle points move to their own layer and are recoloured, so the
    union is exactly the old picture.  A payload with no `bundle` (T_cluster
    absent) cannot restrict and is drawn whole.
    """
    empty = dict(x=[], y=[], z=[], q=[])
    bundle = pay.get("bundle")
    if bundle is None:
        return near, far, empty, -1
    mn = _bundle_mask(near, len(near.get("x") or []))
    mf = _bundle_mask(far, len(far.get("x") or []))
    if mn is None and mf is None:
        return near, far, empty, -1

    def take(g, m, keys, keep):
        if m is None:
            return {k: list(g.get(k) or []) for k in keys} if keep else \
                   {k: [] for k in keys}
        return {k: [w for w, t in zip(g.get(k) or [], m) if t == keep]
                for k in keys}

    nk, fk = ("x", "y", "z", "q"), ("x", "y", "z")
    n_in = take(near, mn, nk, True)
    f_in = take(far, mf, fk, True)
    n_out = take(near, mn, nk, False)
    f_out = take(far, mf, fk, False)
    hidden = len(n_out["x"]) + len(f_out["x"])
    if bundle_tog.active:
        return n_in, f_in, empty, hidden
    out = dict(x=n_out["x"] + f_out["x"], y=n_out["y"] + f_out["y"],
               z=n_out["z"] + f_out["z"], q=[])
    return n_in, f_in, out, 0


def show_bundle(pay, hidden):
    """say what the bundle control is doing, in points, never silently"""
    bundle = pay.get("bundle")
    if bundle is None:
        bundle_div.text = ("<span style='color:#b00'>no T_cluster in this arm "
                           "&mdash; the bundle cannot be resolved, every cluster "
                           "is drawn</span>")
        return
    n = len(bundle)
    if hidden < 0:
        bundle_div.text = ("<span style='color:#b00'>this payload predates the "
                           "bundle field &mdash; re-run prep_stm_michel_scan.py"
                           "</span>")
    elif bundle_tog.active:
        bundle_div.text = (
            "<span style='font-size:90%%'>bundle of <b>%d</b> cluster%s; "
            "<b>%d</b> image point%s from other bundles hidden</span>"
            % (n, "" if n == 1 else "s", hidden, "" if hidden == 1 else "s"))
    else:
        bundle_div.text = (
            "<span style='font-size:90%%'>bundle of <b>%d</b> cluster%s; other "
            "bundles shown in <b style='color:#b07aa1'>mauve</b> &mdash; that "
            "charge is a different t0 and is NOT over-clustered with this "
            "muon</span>" % (n, "" if n == 1 else "s"))


def fill_pf(pay, v, rev):
    """The PF layers, the highlight and the tag rings.

    The TOPOLOGY -- which segments exist and where the junctions are -- is drawn
    whenever the toggle is on.  It is not behind REVEAL because it is the PR
    graph, not the STM/Michel verdict.  What IS behind REVEAL is `pf_type`: the
    segment's pdg and its track/shower flag, which CheckSTM_Michel sets to 11 /
    shower on the Michel arm (CheckSTM_Michel.cxx:1184) and which would hand the
    scanner the answer.
    """
    segs = pf_segments(pay)
    pf = (pay or {}).get("pf") or {}
    on = bool(pf_tog.active)
    X = Y = Z = []
    cols = []
    if segs:
        X, Y, Z, cols = [], [], [], []
        for i, sg in enumerate(segs):
            c = PF_PALETTE[i % len(PF_PALETTE)]
            X += sg["x"]; Y += sg["y"]; Z += sg["z"]; cols += [c] * len(sg["x"])
    out = {"pfseg": (X, Y, Z, {"col": cols}) if on else ([], [], [], {"col": []})}
    vtx = pf.get("vtx") or dict(x=[], y=[], z=[])
    out["pfvtx"] = ((vtx["x"], vtx["y"], vtx["z"], {}) if on
                    else ([], [], [], {}))
    sel = next((sg for sg in segs if sg["id"] == state["pf_seg"]), None)
    out["pfsel"] = ((sel["x"], sel["y"], sel["z"], {}) if sel else ([], [], [], {}))
    tx, ty, tz, tc = [], [], [], []
    for sg in segs:
        t = state["pf_tag"].get(str(sg["id"]))
        if not t:
            continue
        c = PF_TAGS.get(t, "#000000")
        tx += sg["x"]; ty += sg["y"]; tz += sg["z"]; tc += [c] * len(sg["x"])
    out["pftag"] = (tx, ty, tz, {"col": tc})
    return out


def fill_pf_meas(pay, rev):
    """The PF into the nine measurement panels: vertices and the picked segment."""
    pf = (pay or {}).get("pf") or {}
    on = bool(pf_tog.active)
    vtx = pf.get("vtx") or {}
    sel = next((sg for sg in pf_segments(pay) if sg["id"] == state["pf_seg"]), None)
    for pl in PLANES:
        w, t = _wt(vtx, pl) if on else ([], [])
        SRCT[(pl, "pfvtx")].data = dict(w=w, t=t)
        w, t = _wt(sel, pl) if sel else ([], [])
        SRCT[(pl, "pfsel")].data = dict(w=w, t=t)


def fill_seg_div(pay, v, rev):
    segs = pf_segments(pay)
    if not segs:
        seg_div.text = ("<span style='color:#777'>this cluster has no particle-flow "
                        "segments in T_rec_charge</span>")
        return
    sel = next((sg for sg in segs if sg["id"] == state["pf_seg"]), None)
    ntag = len(state["pf_tag"])
    if sel is None:
        seg_div.text = "<span style='color:#777'>%d PF segments</span>" % len(segs)
        return
    tag = state["pf_tag"].get(str(sel["id"]))
    extra = ""
    if rev:
        ty = ((v.get("pf_type") or {}).get(str(sel["id"])) or {})
        pdg = ty.get("pdg")
        name = {13: "muon", 11: "electron/shower", 211: "pion", 2212: "proton",
                4: "track, no hypothesis", 1: "shower, no hypothesis"}.get(pdg, str(pdg))
        extra = ("<br><span style='background:#fff6e5'><b>REVEALED</b> &mdash; "
                 "chain calls it <b>%s</b> (pdg %s), %s (shower fraction %.2f)</span>"
                 % (name, pdg, "SHOWER" if ty.get("shower") else "track",
                    ty.get("frac_shower", 0.0)))
    seg_div.text = (
        "<div style='background:#f7f7f7;padding:6px;font-size:93%%'>"
        "<b>segment S%d</b> &mdash; %d points, %.1f cm, median dQ/dx %s e/cm"
        "%s &nbsp;|&nbsp; your tag: <b style='color:%s'>%s</b>"
        " &nbsp;|&nbsp; %d of %d segments tagged%s</div>"
        % (sel["id"], sel["npts"], sel["len_cm"],
           "—" if sel.get("dqdx_med") is None else "%.0f" % sel["dqdx_med"],
           "" if not sel.get("n_rr_sentinel") else
           " &nbsp;(%d rr sentinel%s at branch vertices)"
           % (sel["n_rr_sentinel"], "" if sel["n_rr_sentinel"] == 1 else "s"),
           PF_TAGS.get(tag, "#777"), tag or "none", ntag, len(segs), extra))


def on_seg_pick(attr, old_, new_):
    segs = pf_segments(payload(current()))
    if new_ in seg_select.options and segs:
        state["pf_seg"] = segs[seg_select.options.index(new_)]["id"]
    render()


def set_pf_tag(tag):
    """Tag the picked segment, and persist it the moment there is a row to hold it."""
    if state["pf_seg"] is None:
        status.text = "<b style='color:#b00'>pick a PF segment first</b>"
        return
    k = str(state["pf_seg"])
    if tag is None:
        state["pf_tag"].pop(k, None)
    else:
        state["pf_tag"][k] = tag
    it = current()
    rec = LABELS.get(item_key(it))
    if rec is not None:
        # there is already a saved row for this item -- write through NOW rather
        # than waiting for another label click, and say what the file holds
        rec["pf_segments"] = dict(state["pf_tag"])
        rec["pf_tagged"] = len(state["pf_tag"])
        save_labels()
        show_save()
    else:
        save_div.text = ("<div style='background:#fff6e5;padding:6px;font-size:92%%'>"
                         "<b>%d segment tag%s held, NOT yet on disk</b> &mdash; they "
                         "are written with the label. Click a label button to save."
                         "</div>" % (len(state["pf_tag"]),
                                     "" if len(state["pf_tag"]) == 1 else "s"))
    render()


def fill_dqdx(pay, v, px, py, pz, prr, psrc, rev):
    X, Y, Z, Q, RR = muon_arrays(pay)
    live = Q > 0                      # roles 2/3/4 carry negative dQ/dx where the
    #                                   fit found no charge; a median over those
    #                                   is meaningless (feedback_zero_charge_points)
    if psrc == "manual" or prr is None:
        d = np.sqrt((X - px) ** 2 + (Y - py) ** 2 + (Z - pz) ** 2)
        s_mu = np.where(RR >= RR[int(np.argmin(d))] if RR.size else True,
                        RR - (RR[int(np.argmin(d))] if RR.size else 0.0),
                        RR - (RR[int(np.argmin(d))] if RR.size else 0.0))
    else:
        s_mu = RR - prr
    m = pay["muon"]
    SRCQ["muon"].data = _qdata(s_mu[live], Q[live], Q[live], X[live], Y[live], Z[live],
                               _col(m, "pu", live), _col(m, "pv", live),
                               _col(m, "pw", live), _col(m, "pt", live))
    for nm in ("delta", "michel", "dots"):
        g = (v.get(nm) if rev else None) or dict(x=[], y=[], z=[], q=[])
        gx = np.asarray(g["x"], float); gy = np.asarray(g["y"], float)
        gz = np.asarray(g["z"], float); gq = np.asarray(g["q"], float)
        k = gq > 0
        d = np.sqrt((gx - px) ** 2 + (gy - py) ** 2 + (gz - pz) ** 2) if gx.size else gx
        # the SAME mask on every column: a different one would offset the cursor
        # from the point that was clicked by however many dead points precede it
        SRCQ[nm].data = _qdata(-d[k], gq[k], gq[k], gx[k], gy[k], gz[k],
                               _col(g, "pu", k), _col(g, "pv", k),
                               _col(g, "pw", k), _col(g, "pt", k))
    grid = (_REF or {}).get("grid") or dict(start=0.0, step=0.25, n=0)
    xs = [grid["start"] + grid["step"] * i for i in range(int(grid["n"]))]
    for nm, key in (("ref_muon", "muon"), ("ref_electron", "electron")):
        ys = (_REF or {}).get(key) or []
        SRCQ[nm].data = dict(a=xs[:len(ys)], b=list(ys))
    hi = max([1.0] + [t for t in Q[live]] + [t for t in ((_REF or {}).get("muon") or [])[:80]])
    SRCQ["origin"].data = dict(a=[0.0, 0.0], b=[0.0, hi * 1.05])
    fq.x_range.start = -40.0
    fq.x_range.end = float(max(60.0, (s_mu.max() if s_mu.size else 60.0)))
    fq.y_range.start = 0.0
    fq.y_range.end = float(hi * 1.05)
    fq.title.text = ("dQ/dx vs signed arc length — origin: %s%s"
                     % ({"pin": "YOUR PIN", "manual": "your typed x,y,z",
                         "fit-end": "the fit's own last point (no pin yet)"}[psrc],
                        "" if prr is None else " at rr = %.1f cm" % prr))


def fill_badge(it, pay, px, py, pz, prr, psrc):
    u, c, f, how = pin_unit(pay, px, py, pz, psrc)
    sd = smgeom.seam_distances(DETNAME, px, py, pz)
    seam = min(sd["seam_x"], sd["seam_y"], sd["seam_z"])
    badge.text = (
        "<div style='font-size:110%%'><b>stopping point</b> "
        "(%s): &nbsp; x %.1f &nbsp; y %.1f &nbsp; z %.1f cm &nbsp;&mdash;&nbsp; "
        "<b>%s</b> <span style='color:#777'>[%s]</span>"
        "<br><span style='font-size:85%%;color:#555'>nearest APA/CRP seam %.1f cm"
        " &nbsp;|&nbsp; cathode %.1f cm &nbsp;|&nbsp; anode face %.1f cm"
        " &nbsp;|&nbsp; nearest wall %.1f cm</span></div>"
        % ({"pin": "your pin", "manual": "your typed x,y,z",
            "fit-end": "the fit's own end — NO PIN PLACED YET"}[psrc],
           px, py, pz, smgeom.unit_label(DETNAME, u, c, f), how,
           seam, sd["cathode"], sd["anode_face"],
           min(sd["wall_x"], sd["wall_y"], sd["wall_z"])))


# ---------------------------------------------------------------------------
# the mu -> e particle flow, doc pdhd/14
#
# EVERY number in these two functions is a T_stm_michel branch.  Nothing is
# recomputed here, and nothing is estimated when a branch is missing -- the
# point of the panel is to show what CheckSTM_Michel actually emits, so a gap
# in the chain's output has to read as a gap.  Recomputing it in the viewer
# would hide exactly the deficiency this display exists to find.
# ---------------------------------------------------------------------------
def _mcs_text(v, long_form=False):
    """doc pdhd/16: the MCS leg of the muon energy, or why there isn't one.

    -1 is the chain's "not computed" sentinel and MUST read as a gap: the
    engine refuses a path it could not trim, one with fewer than 20 trimmed
    points, one whose trimmed end is nearer than 28 cm to the stop, or one that
    yields fewer than two 14 cm segments.  Rendering that as "0.0 MeV" would
    invent a measurement.  muon_mcs_amb is the ratio of the better side minimum
    to the global one, so 1 = maximally ambiguous and small = a clean fit; doc
    84 R3.5 measured the SBND scale only for amb < 0.2.
    """
    ke = v.get("muon_ke_mcs")
    if ke is None:
        return " <span style='color:#777'>(no MCS in this arm &mdash; pre-doc-16)</span>"
    if ke is not None and float(ke) < 0:
        why = "trim failed" if int(v.get("muon_mcs_bad_path") or 0) else (
            "%d segment%s" % (int(v.get("muon_mcs_nsegs") or 0),
                              "" if int(v.get("muon_mcs_nsegs") or 0) == 1 else "s"))
        return " <span style='color:#777'>MCS &mdash; not computed (%s)</span>" % why
    amb = float(v.get("muon_mcs_amb") or -1)
    col = "#0a0" if 0 <= amb < 0.2 else "#a60"
    tail = ""
    if long_form:
        tail = (" over %.0f cm / %d seg" % (float(v.get("muon_mcs_tracklen") or 0),
                                            int(v.get("muon_mcs_nsegs") or 0)))
    return (" MCS <b>%.1f MeV</b> <span style='color:%s'>(amb %.2f)</span>"
            "<span style='color:#777'>%s</span>" % (float(ke), col, amb, tail))


def _muon_ke_text(v):
    """The chain's muon energy for the un-blinded status line."""
    if v.get("muon_ke_best") is None:
        return (" &nbsp;<span style='color:#b00'>(no muon energy in this arm "
                "&mdash; pre-doc-14 CheckSTM_Michel)</span>")
    return (" &nbsp;&mdash;&nbsp; chain muon KE <b>%.1f MeV</b>"
            " <span style='color:#777'>(range %.1f / dQ&thinsp;/&thinsp;dx %.1f)</span>%s"
            % (v.get("muon_ke_best", 0.0), v.get("muon_ke_range", 0.0),
               v.get("muon_ke_dqdx", 0.0), _mcs_text(v)))


def fill_flow(v, rev):
    """mu -> e as CheckSTM_Michel recorded it: two particles, one link.

    Every number here is a T_stm_michel branch; nothing is recomputed.

    Since doc pdhd/15 the Michel is ONE object -- the stop arm (or, when the
    3-D clustering detached it, the nearest admitted piece), everything the
    shower walk reaches, and every fitted segment of an admitted companion
    near the stop.  michel_ke_dqdx is that whole object, michel_ke_core is
    the core alone (what michel_ke_dqdx meant through doc pdhd/14), and
    dots_ke_unfit converts the charge of a companion the fitter never
    reached, which has no dx and so no dQ/dx to invert.

    The parentage is the muon's stop vertex in every case:
      conn 1  the arm leaves stop_vtx_id itself -- a shared graph vertex;
      conn 2  the 3-D clustering split the electron off, so the object is
              BRIDGED to the same vertex across michel_dis_cm of empty space;
      conn 3  CHARGE ONLY -- a companion cluster the fitter produced no segment
              for, so there is no shape and no michel_seg_id, only charge.
    michel_parent_vtx_id names the vertex in all three.
    """
    if not rev:
        flow_div.text = ("<span style='color:#777'>the chain's particle flow is "
                         "<b>hidden</b> until REVEAL</span>")
        return
    if v.get("muon_ke_best") is None:
        flow_div.text = ("<div style='background:#fff6e5;padding:6px'><b>REVEALED</b>"
                         " &mdash; <span style='color:#b00'>this arm predates doc "
                         "pdhd/14: T_stm_michel carries no muon energy and no "
                         "michel_seg_id. Re-run the PR arm to populate them."
                         "</span></div>")
        return
    one_object = v.get("michel_ke_core") is not None

    # doc pdhd/16: three scales for one muon, side by side.  RANGE is the
    # baseline and is what muon_ke_best carries above 4 cm -- it reads no charge
    # except through where the track ends.  dQ/dx is calorimetric and therefore
    # the only one carrying the gain x lifetime x recombination normalization
    # (this arm's check_stm_michel inverts the Modified Box with the measured C;
    # doc pdhd/16 sec 5).  MCS reads no charge at all.  They are shown, never
    # combined: a disagreement here is the finding, not something to average.
    mu = ("<b>&mu;</b> &nbsp; pdg 13 &nbsp; %.1f cm &nbsp; <b>%.1f MeV</b>"
          " <span style='color:#777'>(range %.1f / dQ&thinsp;/&thinsp;dx %.1f)</span>%s"
          " &nbsp; %d chain seg%s"
          % (v.get("muon_len", 0.0), v.get("muon_ke_best", 0.0),
             v.get("muon_ke_range", 0.0), v.get("muon_ke_dqdx", 0.0),
             _mcs_text(v, long_form=True),
             v.get("n_chain_segs", 0), "" if v.get("n_chain_segs") == 1 else "s"))
    if v.get("muon_p_range") is not None and float(v.get("muon_p_range") or -1) > 0:
        mu += ("<br><span style='color:#777'>&nbsp;&nbsp;&nbsp;p = "
               "%.1f (range) / %.1f (dQ/dx)%s MeV/c</span>"
               % (float(v.get("muon_p_range") or 0), float(v.get("muon_p_dqdx") or 0),
                  ("" if float(v.get("muon_p_mcs") or -1) < 0
                   else " / %.1f (MCS)" % float(v.get("muon_p_mcs")))))

    conn = int(v.get("michel_conn_type") or 0)
    seg = v.get("michel_seg_id")
    seg = None if seg is None or int(seg) < 0 else int(seg)
    parent = v.get("michel_parent_vtx_id")
    parent = v.get("stop_vtx_id") if parent is None or int(parent) < 0 else int(parent)
    gap = v.get("michel_dis_cm")

    if conn == 1:
        link = ("&#9492;&#9472; <b>attached</b> at the shared stop vertex "
                "<code>%s</code> &mdash; the arm leaves the very vertex where the "
                "muon chain ends" % parent)
    elif conn == 2:
        link = ("&#9492;&#9472; <b>bridged</b> to the same stop vertex "
                "<code>%s</code> across <b>%.2f cm</b> of empty space &mdash; the "
                "3-D clustering split the electron off the muon, so the parentage "
                "is proximity to the stop, not a graph edge"
                % (parent, gap if gap is not None else -1.0))
    elif conn == 3:
        link = ("&#9492;&#9472; <b>charge only</b>, %.2f cm from the stop vertex "
                "<code>%s</code> &mdash; the companion passed every admission test "
                "but the fitter produced no segment for it, so there is no shape "
                "and no dQ&thinsp;/&thinsp;dx; the energy is the charge conversion "
                "alone" % (gap if gap is not None else -1.0, parent))
    else:
        link = "&#9492;&#9472; <span style='color:#b00'><b>no daughter</b></span>"

    if conn:
        pieces = v.get("michel_n_pieces")
        head = ("<b>e</b> &nbsp; pdg 11 &nbsp; %s &nbsp; %d piece%s in the object"
                % ("no fitted segment" if conn == 3 else
                   ("%s seg <code>%s</code>" % ("core" if conn == 1 else "seed", seg)),
                   pieces if pieces is not None else v.get("n_michel_segs", 0),
                   "" if pieces == 1 else "s"))
        if one_object:
            energy = ("&nbsp; <b>%.1f MeV</b> = dQ&thinsp;/&thinsp;dx <b>%.1f</b> "
                      "+ unfitted charge <b>%.1f</b>"
                      "<br><span style='color:#777'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                      "core alone %.1f &middot; pieces %.1f &middot; core range %.1f "
                      "&middot; chain kine_charge %.1f%s</span>"
                      % (v.get("michel_ke_best", 0.0), v.get("michel_ke_dqdx", 0.0),
                         v.get("dots_ke_unfit", 0.0), v.get("michel_ke_core", 0.0),
                         v.get("dots_ke_dqdx", 0.0), v.get("michel_ke_range", 0.0),
                         v.get("michel_ke_charge", 0.0),
                         " &mdash; 0 by construction on a t0-corrected cosmic, doc pdhd/15 sec 6"
                         if not v.get("michel_ke_charge") else ""))
        else:
            energy = ("&nbsp; <b>%.1f MeV</b> <span style='color:#b00'>(pre-doc-15 arm: "
                      "the pieces are not in this number)</span>"
                      % v.get("michel_ke_best", 0.0))
        extra = ("<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:#777'>"
                 "core %.1f cm, kink %.0f deg &middot; %d dot%s (%d unfitted cluster%s "
                 "carrying %.3g e)</span>"
                 % (v.get("michel_len", 0.0), v.get("michel_kink_deg", -1.0),
                    v.get("n_dots", 0), "" if v.get("n_dots") == 1 else "s",
                    v.get("n_dot_clusters_unfit", 0),
                    "" if v.get("n_dot_clusters_unfit") == 1 else "s",
                    v.get("dots_charge_unfit", 0.0)))
        dau = head + energy + extra
    else:
        dau = ("nothing at the stop: n_stop_arms %s, n_dots %s, unfitted dot "
               "clusters %s carrying %.3g e"
               % (v.get("n_stop_arms"), v.get("n_dots"),
                  v.get("n_dot_clusters_unfit"), v.get("dots_charge_unfit", 0.0)))

    warn = ""
    if conn and not int(v.get("michel_found") or 0):
        warn = ("<br><span style='color:#b00'>michel_found is 0 even though a "
                "Michel WAS reconstructed &mdash; this arm predates doc pdhd/15, "
                "where michel_found was set only on the attached path. "
                "Doc pdhd/13 defect D1.</span>")
    flow_div.text = (
        "<div style='background:#fff6e5;padding:6px;font-size:96%%'><b>REVEALED "
        "&mdash; particle flow</b> <span style='color:#777'>(every field is a "
        "T_stm_michel branch)</span><br>%s<br>&nbsp;&nbsp;%s<br>&nbsp;&nbsp;&nbsp;"
        "&nbsp;&nbsp;%s%s</div>" % (mu, link, dau, warn))


def fill_reveal(v, rev):
    if not rev:
        reveal_div.text = ("<span style='color:#777'>the reconstruction's answer is "
                           "<b>hidden</b>. Label first; REVEAL is recorded either way."
                           "</span>")
        return
    reveal_div.text = (
        "<div style='background:#fff6e5;padding:6px'><b>REVEALED</b> &mdash; "
        "is_stm <b>%s</b>, in_fv %s, verdict <b>%s</b><br>"
        "michel_found <b>%s</b> (conn %s, %s segs, %.1f cm, %.2f mip, kink %.0f deg,"
        " KE %.1f MeV) &nbsp; dots %s (%.1f MeV) &nbsp; delta %s<br>"
        "contrast %.2f vs expected %.2f &nbsp; plateau %.0f &nbsp; tail %.0f e/cm"
        " &nbsp; chain %.1f cm, %s live / %s dead pts</div>"
        % (v.get("is_stm"), v.get("in_fv"), "|".join(v.get("reject_names") or []),
           v.get("michel_found"), v.get("michel_conn_type"),
           v.get("n_michel_segs"), v.get("michel_len", 0.0), v.get("michel_mip", 0.0),
           v.get("michel_kink_deg", -1.0), v.get("michel_ke_best", 0.0),
           v.get("n_dots"), v.get("dots_ke_dqdx", 0.0), v.get("n_delta"),
           v.get("contrast", 0.0), v.get("contrast_expected", 0.0),
           v.get("plateau_med", 0.0), v.get("tail_med", 0.0),
           v.get("muon_len", 0.0), v.get("n_live_pts"), v.get("n_dead_pts")))


# ---------------------------------------------------------------------------
# navigation and labelling
# ---------------------------------------------------------------------------
def refresh_options():
    opts = [item_option(i) for i in ITEMS]
    item_select.options = opts
    item_select.value = opts[state["idx"]]


def go(idx):
    state["idx"] = max(0, min(len(ITEMS) - 1, idx))
    state["pin_i"] = None
    state["pin_manual"] = None
    off_fit_chk.active = []
    manual_x.value = manual_y.value = manual_z.value = ""
    pay = payload(current())
    if pay is not None:
        rr = pay["muon"].get("rr") or [0.0]
        rr_slider.start = float(min(rr))
        rr_slider.end = float(max(max(rr), min(rr) + 1.0))
        rr_slider.value = float(min(rr))
    refresh_options()
    render()


def set_label(choice):
    it = current()
    pay = payload(it)
    c = CHOICES[choice]
    # A Michel verdict with no Michel description is not a usable row.  Refuse
    # rather than defaulting: this is the field goal 2 rests on.
    if c["label"] == "STM_MICHEL" and MICHEL_KINDS[michel_kind.active] == MICHEL_UNSET:
        status.text = ("<b style='color:#b00'>say what the Michel is</b> "
                       "&mdash; pick attached, detached dots or both below the "
                       "buttons, then click the label again.")
        return
    P = pin_point(pay) if pay is not None else None
    pin = None
    if P is not None:
        px, py, pz, prr, psrc = P
        u, cr, fa, how = pin_unit(pay, px, py, pz, psrc)
        # how far the scanner moved it from the drawn chain end.  0.0 with
        # placed=True means "I looked and I agree", which is a different datum
        # from placed=False ("I never touched it").
        X, Y, Z, Q, RR = muon_arrays(pay)
        j = int(np.argmin(RR)) if RR.size else 0
        moved = (float(np.hypot(np.hypot(px - X[j], py - Y[j]), pz - Z[j]))
                 if RR.size else None)
        pin = dict(x=round(px, 2), y=round(py, 2), z=round(pz, 2),
                   rr=None if prr is None else round(prr, 2),
                   placed=(psrc != "fit-end"), source=psrc,
                   moved_cm=None if moved is None else round(moved, 2),
                   off_fit=bool(off_fit_chk.active),
                   unit=u, cru=cr, face=fa, unit_source=how)
    LABELS[item_key(it)] = dict(
        label=c["label"], partial=c["partial"], choice=choice,
        michel_kind=MICHEL_KINDS[michel_kind.active],
        pin=pin, revealed_before_label=bool(reveal_tog.active),
        notes=notes.value, scan_id=it["scan_id"], tranche=it["tranche"],
        event=it["event"], cluster=it["cluster"], npts=it["npts"],
        muon_len_cm=it["muon_len"], det=DETNAME,
        # the per-segment answer.  OPTIONAL and additive: a row written before
        # this existed loads and scores unchanged.
        pf_segments=dict(state["pf_tag"]), pf_tagged=len(state["pf_tag"]),
        n_pf_segments=len(pf_segments(pay)))
    save_labels()                     # every click, not only on Save
    show_save()                       # ... and say what the FILE now holds
    refresh_options()
    render()
    nxt = next((k for k in range(state["idx"] + 1, len(ITEMS))
                if item_key(ITEMS[k]) not in LABELS), None)
    if nxt is not None:
        go(nxt)


def clear_label():
    LABELS.pop(item_key(current()), None)
    save_labels()
    show_save()
    refresh_options()
    render()


def next_unlabelled():
    nxt = next((k for k in range(state["idx"] + 1, len(ITEMS))
                if item_key(ITEMS[k]) not in LABELS), None)
    if nxt is None:
        nxt = next((k for k in range(0, len(ITEMS))
                    if item_key(ITEMS[k]) not in LABELS), None)
    if nxt is None:
        status.text = "<b>every item is labelled.</b>"
    else:
        go(nxt)


def on_rr(attr, old, new):
    pay = payload(current())
    if pay is None:
        return
    rr = np.asarray(pay["muon"].get("rr") or [], float)
    if rr.size:
        set_pin_index(int(np.argmin(np.abs(rr - float(new)))))


def on_manual():
    try:
        p = (float(manual_x.value), float(manual_y.value), float(manual_z.value))
    except ValueError:
        status.text = "<b style='color:#b00'>x, y and z must all be numbers.</b>"
        return
    state["pin_manual"] = p
    state["pin_i"] = None
    off_fit_chk.active = [0]
    render()


def clear_pin():
    state["pin_i"] = None
    state["pin_manual"] = None
    off_fit_chk.active = []
    render()


item_select.on_change("value", lambda a, o, n: go(item_select.options.index(n))
                      if n in item_select.options else None)
prev_btn.on_click(lambda: go(state["idx"] - 1))
next_btn.on_click(lambda: go(state["idx"] + 1))
next_unl_btn.on_click(next_unlabelled)
stm_mic_btn.on_click(lambda: set_label("STM_MICHEL"))
stm_only_btn.on_click(lambda: set_label("STM_ONLY"))
thru_btn.on_click(lambda: set_label("THRU"))
frag_mic_btn.on_click(lambda: set_label("FRAG_STM_MICHEL"))
frag_only_btn.on_click(lambda: set_label("FRAG_STM_ONLY"))
frag_thru_btn.on_click(lambda: set_label("FRAG_THRU"))
messy_btn.on_click(lambda: set_label("MESSY"))
uncl_btn.on_click(lambda: set_label("UNCLEAR"))
clear_btn.on_click(clear_label)
save_info_btn.on_click(save_info)
pf_tog.on_change("active", lambda a, o, n: render())
seg_select.on_change("value", on_seg_pick)
pf_mu_btn.on_click(lambda: set_pf_tag("muon"))
pf_mic_btn.on_click(lambda: set_pf_tag("michel"))
pf_oth_btn.on_click(lambda: set_pf_tag("delta / other"))
pf_mix_btn.on_click(lambda: set_pf_tag("straddles the stop"))
pf_clr_btn.on_click(lambda: set_pf_tag(None))
pin_clear_btn.on_click(clear_pin)
manual_btn.on_click(on_manual)
rr_slider.on_change("value_throttled", on_rr)
# on_change("active"), never on_click: on_click is a browser button event, while
# on_change fires for a click AND for a programmatic set -- so the self-test can
# drive it.  A binding only a human can exercise is a binding nothing tests
# (feedback_bokeh_client_session_false_negative).
reveal_tog.on_change("active", lambda a, o, n: render())
cell_scale.on_change("active", lambda a, o, n: apply_cell_scale())
cell_size.on_change("active", lambda a, o, n: apply_cell_size())
meas_zoom.on_change("active", lambda a, o, n: render())


def _on_pick(name):
    def cb(attr, old_, new_):
        # [] on deselect; overlapping hits give several -- take the first.
        if not new_:
            return clear_cursor()
        for other in QSCAT:
            if other != name and SRCQ[other].selected.indices:
                SRCQ[other].selected.indices = []
        set_cursor(SRCQ[name], int(new_[0]))
    return cb


for _nm in QSCAT:
    SRCQ[_nm].selected.on_change("indices", _on_pick(_nm))
zoom_tog.on_change("active", lambda a, o, n: render())
bundle_tog.on_change("active", lambda a, o, n: render())
for _ha, _va, _t in PANELS:
    FIG2[(_ha, _va)].on_event(
        Tap, (lambda h, v: (lambda e: snap_2d(h, v, e.x, e.y)))(_ha, _va))
f3d.on_event(Tap, lambda e: snap_3d(e.x, e.y))

meas_grid = column(
    row(Div(text="<b>colour scale</b>", width=95), cell_scale,
        Div(text="<b>cell size</b>", width=75), cell_size,
        Div(text="<b>window</b>", width=60), meas_zoom),
    meas_note,
    *[row(*[FIGM[(pl, fld)] for fld, _t in MEAS_COLS]) for pl in PLANES])
left = Tabs(tabs=[
    TabPanel(child=column(f3d), title="3-D"),
    TabPanel(child=column(row(*[FIG2[(h, v)] for h, v, _ in PANELS])),
             title="2-D projections"),
    TabPanel(child=meas_grid, title="2-D measurement"),
])
right = column(
    fq,
    cursor_div,
    rr_slider,
    row(pin_clear_btn, off_fit_chk),
    row(manual_x, manual_y, manual_z, manual_btn),
    row(reveal_tog, zoom_tog, bundle_tog, pf_tog),
    bundle_div,
    Div(text="<b>particle flow</b> &mdash; the PR graph this chain walked. Pick a "
             "segment, then say what it is. Your tags are drawn as hollow squares, "
             "so they can never be confused with the reconstruction's colours.",
        width=620),
    seg_select,
    row(pf_mu_btn, pf_mic_btn, pf_oth_btn, pf_mix_btn, pf_clr_btn),
    seg_div,
    reveal_div,
    flow_div,
)
curdoc().add_root(column(
    header,
    row(item_select, prev_btn, next_btn, next_unl_btn),
    badge,
    Div(text="<b>the cluster IS the whole object:</b>", width=1420),
    row(stm_mic_btn, stm_only_btn, thru_btn),
    Div(text="<b>the cluster is only PART of the object</b> (under-clustered) "
             "&mdash; the verdict is for the FULL object:", width=1420),
    row(frag_mic_btn, frag_only_btn, frag_thru_btn),
    row(messy_btn, uncl_btn, clear_btn),
    Div(text="<b>the Michel, if any, is:</b> &mdash; required before a STM&nbsp;+&nbsp;MICHEL label is accepted", width=700),
    michel_kind,
    row(notes, progress, save_info_btn),
    save_div,
    row(left, right),
    status,
))
curdoc().title = "%s STM+Michel hand scan (%s)" % (DETNAME.upper(), SCAN_TAG)
# A property set while the document is BUILT is serialised as initial state, not
# emitted as a change, so a JS callback registered on it never fires on first
# paint.  DocumentReady is the one channel that is neither hidden nor
# build-time (feedback_bokeh3_silent_js_traps trap 3).
curdoc().js_on_event(DocumentReady, js_apply)
go(0)
show_save(after_write=False)
