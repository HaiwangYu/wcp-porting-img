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

import numpy as np
from bokeh.events import DocumentReady, Pan, PanEnd, PanStart, Tap
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (BoxSelectTool, Button, CheckboxGroup, ColumnDataSource,
                          CustomJS, Div, LinearColorMapper, RadioButtonGroup,
                          Range1d, ResetTool, SaveTool, Select, Slider, Tabs,
                          TabPanel, TapTool, TextInput, Toggle, WheelZoomTool)
from bokeh.palettes import Viridis256
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
MICHEL_KINDS = ["none", "attached", "detached dots", "both"]


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
    tmp = LABEL_FILE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"scan": "stm_michel_topology",
                   "doc": "pdhd/docs/12_stm-michel-handscan-display.md",
                   "det": DETNAME, "tag": SCAN_TAG,
                   "sheet": os.path.relpath(SHEET, DETROOT),
                   "labels": LABELS}, fh, indent=1)
    os.replace(tmp, LABEL_FILE)      # atomic: a crash mid-write keeps the old file


# ---------------------------------------------------------------------------
# layers.  ONE description drives the three 2-D panels and the 3-D panel, so a
# layer cannot exist in one and be forgotten in the other.
#   reveal=True  -> the chain's answer; hidden unless REVEAL is on
# ---------------------------------------------------------------------------
LAYERS = [
    # name       size alpha  colour            marker      reveal cue
    ("far",       1.5, 0.35, "#c9c9c9",        "circle",   False, 1.0),
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
]
REVEAL_LAYERS = {n for n, _, _, _, _, rv, _ in LAYERS if rv}

PANELS = [("z", "y", "side view:   Z (beam) vs Y"),
          ("z", "x", "top view:    Z (beam) vs X (drift)"),
          ("x", "y", "end view:    X (drift) vs Y")]

SRC2 = {}          # (ha, va, layer) -> ColumnDataSource with a, b [, q|c]
FIG2 = {}
REND2 = {}
cm_near = LinearColorMapper(palette=Viridis256, low=0.0, high=4e4)
cm_muon = LinearColorMapper(palette=Viridis256, low=0.0, high=1e5)


def _fields(name):
    """extra data columns a layer carries beyond the two projected ones"""
    if name == "near":
        return ["q"]
    if name in ("muon", "tagfit"):
        return ["c"]
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
        else:
            r = f.scatter("a", "b", source=src, size=sz, alpha=al, marker=marker,
                          color=col,
                          line_color="#333333" if name in ("pin", "dots") else None)
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
    else:
        r = f3d.scatter("u", "v", source=src, size="sz", fill_alpha="al",
                        marker=marker, fill_color=col,
                        line_color="#333333" if name in ("pin", "dots") else None)
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
        d.setdefault(k, [0.0] * n)
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
fq = figure(title="dQ/dx vs signed arc length  (+ muon side, − Michel side)",
            height=330, width=620, tools="pan,wheel_zoom,box_zoom,reset,save",
            active_scroll="wheel_zoom",
            x_axis_label="signed arc length through the origin [cm]",
            y_axis_label="dQ/dx [e/cm]")
SRCQ = {}
for name, col, sz in (("ref_muon", "#333333", 0), ("ref_electron", "#8c564b", 0),
                      ("muon", "#000000", 5), ("delta", "#ff7f0e", 7),
                      ("michel", "#1f77b4", 8), ("dots", "#d62728", 10)):
    s = ColumnDataSource(dict(a=[], b=[]))
    SRCQ[name] = s
    if sz == 0:
        fq.line("a", "b", source=s, color=col, line_width=2,
                line_dash="solid" if name == "ref_muon" else "dashed", alpha=0.8)
    elif name == "muon":
        fq.scatter("a", "b", source=s, size=sz, line_color=None,
                   color={"field": "c", "transform": cm_muon}, alpha=0.9)
        s.data = dict(a=[], b=[], c=[])
    else:
        fq.scatter("a", "b", source=s, size=sz, color=col, alpha=0.9,
                   marker="diamond" if name == "dots" else "circle",
                   line_color="#333333" if name == "dots" else None)
fq.line("a", "b", source=ColumnDataSource(dict(a=[], b=[])), color="#e377c2")
SRCQ["origin"] = ColumnDataSource(dict(a=[], b=[]))
fq.line("a", "b", source=SRCQ["origin"], color="#e377c2", line_width=2,
        line_dash="dashed")


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

michel_kind = RadioButtonGroup(labels=MICHEL_KINDS, active=0, width=430)
reveal_tog = Toggle(label="REVEAL the reconstruction", width=230)
zoom_tog = Toggle(label="Zoom to object", width=140)
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
status = Div(text="", width=1420)
reveal_div = Div(text="", width=620)

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
<br><b>REVEAL</b> shows what the reconstruction decided. Every label records whether you
had revealed it, so a revealed label is still usable &mdash; it is just scored separately.
</span>""" % DETNAME.upper())

state = dict(idx=0, pin=None, pin_i=None, pin_manual=None)


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
        SRCQ[n].data = (dict(a=[], b=[], c=[]) if n == "muon" else dict(a=[], b=[]))


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

    # colour scales from THIS object, so a low-dQ/dx track is not a black smear
    cm_muon.low = 0.0
    cm_muon.high = float(np.percentile(Q[Q > 0], 98)) if (Q > 0).any() else 1e5
    nq = np.asarray(near.get("q") or [], float)
    cm_near.low = 0.0
    cm_near.high = float(np.percentile(nq[nq > 0], 98)) if (nq > 0).any() else 4e4

    P = pin_point(pay)
    px, py, pz, prr, psrc = P
    layers = {
        "far": (far["x"], far["y"], far["z"], {}),
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

    fill_dqdx(pay, v, px, py, pz, prr, psrc, rev)
    fill_badge(it, pay, px, py, pz, prr, psrc)
    fill_reveal(v, rev)

    rec = LABELS.get(item_key(it), {})
    notes.value = rec.get("notes", "")
    mk = rec.get("michel_kind")
    michel_kind.active = MICHEL_KINDS.index(mk) if mk in MICHEL_KINDS else 0
    done = sum(1 for i in ITEMS if item_key(i) in LABELS)
    t1 = [i for i in ITEMS if i["tranche"] == 1]
    d1 = sum(1 for i in t1 if item_key(i) in LABELS)
    progress.text = ("<b>%d / %d</b> labelled &nbsp;|&nbsp; tranche 1: <b>%d / %d</b>"
                     " &nbsp;|&nbsp; this item: <b>%s</b>"
                     % (done, len(ITEMS), d1, len(t1), rec.get("choice", "&mdash;")))
    status.text = ("event %s cluster %d &mdash; %d chain points over %.1f cm, "
                   "%d image points at full density, %d thinned context points"
                   % (it["event"], it["cluster"], X.size, it["muon_len"],
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
    SRCQ["muon"].data = dict(a=[float(t) for t in s_mu[live]],
                             b=[float(t) for t in Q[live]],
                             c=[float(t) for t in Q[live]])
    for nm in ("delta", "michel", "dots"):
        g = (v.get(nm) if rev else None) or dict(x=[], y=[], z=[], q=[])
        gx = np.asarray(g["x"], float); gy = np.asarray(g["y"], float)
        gz = np.asarray(g["z"], float); gq = np.asarray(g["q"], float)
        k = gq > 0
        d = np.sqrt((gx - px) ** 2 + (gy - py) ** 2 + (gz - pz) ** 2) if gx.size else gx
        SRCQ[nm].data = dict(a=[-float(t) for t in d[k]],
                             b=[float(t) for t in gq[k]])
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
        muon_len_cm=it["muon_len"], det=DETNAME)
    save_labels()                     # every click, not only on Save
    refresh_options()
    render()
    nxt = next((k for k in range(state["idx"] + 1, len(ITEMS))
                if item_key(ITEMS[k]) not in LABELS), None)
    if nxt is not None:
        go(nxt)


def clear_label():
    LABELS.pop(item_key(current()), None)
    save_labels()
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
pin_clear_btn.on_click(clear_pin)
manual_btn.on_click(on_manual)
rr_slider.on_change("value_throttled", on_rr)
# on_change("active"), never on_click: on_click is a browser button event, while
# on_change fires for a click AND for a programmatic set -- so the self-test can
# drive it.  A binding only a human can exercise is a binding nothing tests
# (feedback_bokeh_client_session_false_negative).
reveal_tog.on_change("active", lambda a, o, n: render())
zoom_tog.on_change("active", lambda a, o, n: render())
for _ha, _va, _t in PANELS:
    FIG2[(_ha, _va)].on_event(
        Tap, (lambda h, v: (lambda e: snap_2d(h, v, e.x, e.y)))(_ha, _va))
f3d.on_event(Tap, lambda e: snap_3d(e.x, e.y))

left = Tabs(tabs=[
    TabPanel(child=column(f3d), title="3-D"),
    TabPanel(child=column(row(*[FIG2[(h, v)] for h, v, _ in PANELS])),
             title="2-D projections"),
])
right = column(
    fq,
    rr_slider,
    row(pin_clear_btn, off_fit_chk),
    row(manual_x, manual_y, manual_z, manual_btn),
    row(reveal_tog, zoom_tog),
    reveal_div,
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
    Div(text="<b>the Michel, if any, is:</b>", width=430),
    michel_kind,
    row(notes, progress),
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
