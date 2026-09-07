#!/usr/bin/env python3
"""PDVD doc-08 sec 9.3 STM hand scan -- the four objects whose STM verdict moves
under the shipped bridge cap (retile_hack_max_bridge = 10 cm), plus eight controls.

Forked BY DUPLICATION from pdhd/d08_scan/d08_scan_viewer.py, which is untouched.

WHY EIGHT CONTROLS
  Only four PDVD objects flip.  A sheet where every item is a flip tells the
  scanner, before they look, that something changed on every one -- and then they
  hunt for a difference.  Four clusters tagged STM in BOTH arms and four tagged in
  NEITHER are mixed in, from the same events and size band.  You are not told
  which is which, and the controls are what measure your own baseline agreement.

WHAT THIS IS FOR
  doc pdhd/08 sec 9.2: on PDVD the cap takes Steiner points more than 10 cm from
  live charge 22 -> 0 and the worst ghost 13.0 -> 7.6 cm, with TGM (494) and FC
  (522) completely unmoved and STM going 147 -> 145.  All four flips have an
  essentially unchanged fit -- evt 8 cluster 55 has IDENTICAL kink, exit_L and
  npts and only its status moves 0 -> 3.  So the open question is not "did the cap
  reshape the track" (it did not) but "was the tag right, before or after".  That
  is a physics judgement on the charge, and this app is where it gets made.

TWO MODES, AND THE DIFFERENCE MATTERS
  1. JUDGE (default).  Charge only.  You answer "does this object stop inside?"
     from the charge alone.  The sheet carries no verdict, not the direction of a
     flip, and not even WHETHER an item flipped -- knowing an object LOST its tag
     is the single most biasing fact available, so none of it is on the sheet, in
     the UI, or in the item label.
  2. REVEAL (you asked for before/after; the toggle is OFF by default).  Draws
     both arms' Steiner cloud and STM fit over the same charge and prints both
     verdicts.  This is the answer key.  Use it to understand WHY a verdict moved
     -- and note that the app records `revealed_before_label` on anything you
     label after switching it on, so the scoring can report blind and revealed
     labels separately instead of silently mixing them.

WHY THE CHARGE PANELS ARE ARM-INDEPENDENT
  clustering-global has the IDENTICAL point set and charges in all 30 PDVD events
  between the two arms (asserted by selftest_d08pv_scan.py), so the coloured/grey
  pixels cannot encode which arm produced them.  In 2 of 30 events a handful of
  points (0.001-0.021 %) change which cluster they belong to, on clusters 164 and
  237 -- neither is a scan item, so every item here has partition_moved=0.

A NOTE ON PDVD COORDINATES
  About 0.4 % of points carry |x| ~ 1.5e8 cm: the drift coordinate of a cluster
  whose t0 was never resolved.  They are dropped from every panel, or the axes
  collapse.  x is drift and is CATHODE-CENTRED here (drift distance is
  x_anode - |x|, not |x|).

WHAT YOU ARE JUDGING  (unchanged from the retile0 scan)
    STM          the cluster is the whole object, and it stops inside
    THRU         the cluster is the whole object, and it crosses / exits
    FRAG -> STM  the cluster is only PART of the object, and the FULL object stops
    FRAG -> THRU the cluster is only PART of the object, and the FULL object exits
    MESSY        not one track -- so "does it stop" is ill-posed
    UNCLEAR      you genuinely cannot tell

USAGE
  ./serve_d08pv_scan.sh 5017                # then http://localhost:5017/d08pv_scan_viewer
  ./serve_d08pv_scan.sh 5017 --tag pass2    # namespace the saved labels
"""
import sys
import os
import json
import csv
import glob
import re
import zipfile

import numpy as np
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (ColumnDataSource, Select, Button, Div, TextInput,
                          Toggle, LinearColorMapper)
from bokeh.plotting import figure
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
PDHD = os.path.dirname(HERE)          # the PDVD tree; name kept from the fork
WORK = os.path.join(PDHD, "work")
SHEET = os.path.join(PDHD, "docs", "scan", "d08pv_stm_flip_sheet.tsv")

# PDVD active volume, doc pdvd/33: the union's outer envelope over all 16 boxes.
VOL = dict(x=(-339.91, 339.91), y=(-336.39, 336.39), z=(0.813, 298.435))
XSENTINEL = 1000.0                    # |x| above this is an unresolved-t0 point
CONTEXT_MAX = 8000
DENSE_R = 40.0
DENSE_MAX = 25000
BASE_ARM = "d08pv30off"     # -S retile_hack_max_bridge=null -- "before"
KNOB_ARM = "d08pv30on"      # the shipped default, 10 cm      -- "after"
RUN6 = "039349"

CHOICES = {"STM":  dict(label="STM", partial=False),
           "THRU": dict(label="THRU", partial=False),
           "FRAG_STM":  dict(label="STM", partial=True),
           "FRAG_THRU": dict(label="THRU", partial=True),
           "MESSY": dict(label="MESSY", partial=False),
           "UNCLEAR": dict(label="UNCLEAR", partial=False)}


def parse_args(argv):
    tag = "d08pvflip0"
    if "--tag" in argv:
        i = argv.index("--tag")
        if i + 1 < len(argv):
            tag = argv[i + 1]
    return tag


SCAN_TAG = parse_args(sys.argv[1:])
LABEL_DIR = os.path.join(WORK, "d08pv_scan_labels", SCAN_TAG)
os.makedirs(LABEL_DIR, exist_ok=True)
LABEL_FILE = os.path.join(LABEL_DIR, "labels.json")


# ---------------------------------------------------------------------------
# the item list -- the sheet carries no verdict and no direction
# ---------------------------------------------------------------------------
def load_items():
    rows = []
    with open(SHEET) as fh:
        lines = [l for l in fh if not l.startswith("#")]
    for r in csv.DictReader(lines, delimiter="\t"):
        rows.append(dict(scan_id=int(r["scan_id"]), tranche=int(r["tranche"]),
                         event=r["event"], cluster=int(r["cluster"]),
                         npts=int(r["npts"]), length=float(r["length_cm"]),
                         moved=int(r["partition_moved"])))
    rows.sort(key=lambda r: r["scan_id"])
    return rows


ITEMS = load_items()
if not ITEMS:
    raise SystemExit("no scan items in %s" % SHEET)


# ---------------------------------------------------------------------------
# charge -- BASE arm only, and only the blind-safe member
# ---------------------------------------------------------------------------
_cache = {}


def _layer(zp, name):
    if not os.path.exists(zp):
        return None
    with zipfile.ZipFile(zp) as z:
        hits = [n for n in z.namelist() if n.endswith("-%s-global.json" % name)]
        if not hits:
            return None
        return json.loads(z.read(hits[0]))


def event_charge(event):
    if event in _cache:
        return _cache[event]
    d = _layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, event, BASE_ARM), "mabc-pr.zip"),
               "clustering")
    if d is None:
        out = None
    else:
        # PDVD only: ~0.4 % of points carry |x| ~ 1.5e8 cm -- the drift coordinate
        # of a cluster whose t0 was never resolved.  Drawing them collapses every
        # axis, so they are dropped here, once, for every consumer downstream.
        X = np.asarray(d["x"], float)
        keep = np.abs(X) < XSENTINEL
        out = (X[keep], np.asarray(d["y"], float)[keep],
               np.asarray(d["z"], float)[keep], np.asarray(d["q"], float)[keep],
               np.asarray(d["cluster_id"], int)[keep])
    _cache[event] = out
    return out


# ---- the REVEAL side: read lazily and ONLY when the toggle is on ----------
_reveal_cache = {}
_fitline_cache = {}
_knobpart_cache = {}

# The STM tag does NOT turn on the fit's point count -- it turns on the fit's
# status, and on where the kink lands relative to the track end.  doc pdvd/40 r3
# found 3 of 13 verdict flips were kink relocation with the trajectory essentially
# unchanged, and [[feedback_status_code_is_not_a_mechanism]] records the same trap
# (same fit, kink 215 -> 3).  So two near-identical overlays with an inverted
# verdict are the NORMAL case, and without these fields the reveal cannot explain
# them.  Every pass is shown: a cluster is fitted up to twice per event.
RE_FIT = re.compile(r"persist_stm_fit: cluster (\d+) stmfit (pass=\d+ status=\S+ "
                    r"kink=\S+ exit_L=\S+ left_L=\S+ npts=\d+)")


def fit_lines(event, arm):
    """{cluster: [one string per persist_stm_fit pass]} from the arm's own log."""
    k = (event, arm)
    if k in _fitline_cache:
        return _fitline_cache[k]
    out = {}
    lg = glob.glob(os.path.join(WORK, "%s_%s_%s" % (RUN6, event, arm), "wct_pr_*.log"))
    if lg:
        with open(lg[0], errors="replace") as fh:
            for line in fh:
                m = RE_FIT.search(line)
                if m:
                    out.setdefault(int(m.group(1)), []).append(m.group(2))
    _fitline_cache[k] = out
    return out


def knob_npts(event, cluster):
    """Point count of the same cluster id in the KNOB arm's clustering layer.

    Only called for partition_moved items.  The panels always draw the BASE arm's
    partition, and for those items the other arm's version of the cluster can be a
    different size (one of the two is half, the other twice) -- which the scanner
    has to be told, or they judge an object the knob arm never saw.
    """
    k = (event, cluster)
    if k in _knobpart_cache:
        return _knobpart_cache[k]
    d = _layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, event, KNOB_ARM), "mabc-pr.zip"),
               "clustering")
    n = None if d is None else int(np.count_nonzero(
        (np.asarray(d["cluster_id"], int) == cluster)
        & (np.abs(np.asarray(d["x"], float)) < XSENTINEL)))
    _knobpart_cache[k] = n
    return n


def reveal_layers(event, arm):
    """(steiner xyz+cid, stm_fit xyz+cid, the `stm` layer's cluster ids)."""
    k = (event, arm)
    if k in _reveal_cache:
        return _reveal_cache[k]
    zp = os.path.join(WORK, "%s_%s_%s" % (RUN6, event, arm), "mabc-pr.zip")
    out = {}
    for name in ("steiner_graph", "stm_fit", "stm"):
        d = _layer(zp, name)
        out[name] = None if d is None else (
            np.asarray(d["x"], float), np.asarray(d["y"], float),
            np.asarray(d["z"], float), np.asarray(d["cluster_id"], int))
    _reveal_cache[k] = out
    return out


def reveal_sel(event, arm, name, cluster):
    d = reveal_layers(event, arm).get(name)
    if d is None:
        return None
    X, Y, Z, C = d
    m = (C == cluster) & (np.abs(X) < XSENTINEL)
    return X[m], Y[m], Z[m]


# ---------------------------------------------------------------------------
# context selection -- purely geometric, identical to the retile0 app
# ---------------------------------------------------------------------------
def context_index(P, mask, dense):
    other = np.flatnonzero(~mask)
    if other.size == 0:
        return other, 1, 0
    step = max(1, other.size // CONTEXT_MAX)
    far = other[::step]
    if not dense:
        return far, step, 0
    tgt = P[mask]
    if tgt.size == 0:
        return far, step, 0
    d, _ = cKDTree(tgt).query(P[other], k=1, distance_upper_bound=DENSE_R)
    near = other[np.isfinite(d)]
    if near.size > DENSE_MAX:
        near = near[::max(1, near.size // DENSE_MAX)]
    return np.union1d(far, near), step, int(near.size)


# ---------------------------------------------------------------------------
# labels
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


LABELS = load_labels()


def save_labels():
    tmp = LABEL_FILE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"scan": "doc pdhd/08 sec 9.3 -- PDVD STM flips (4) + controls (8)",
                   "doc": "pdhd/docs/08_steiner-ghost-fix.md sec 9.2-9.3",
                   "base_arm": BASE_ARM, "knob_arm": KNOB_ARM,
                   "tag": SCAN_TAG, "sheet": os.path.relpath(SHEET, PDHD),
                   "labels": LABELS}, fh, indent=1)
    os.replace(tmp, LABEL_FILE)


# ---------------------------------------------------------------------------
# figures, built once
# ---------------------------------------------------------------------------
SRC = {}
FIGS = {}
PANELS = [("z", "y", "side view:  Z (beam) vs Y (vertical)"),
          ("z", "x", "top view:   Z (beam) vs X (drift)"),
          ("x", "y", "end view:   X (drift) vs Y (vertical)")]
cmap = LinearColorMapper(palette="Viridis256", low=0, high=1)

for ha, va, title in PANELS:
    ctx = ColumnDataSource(dict(a=[], b=[]))
    tgt = ColumnDataSource(dict(a=[], b=[], q=[]))
    stB = ColumnDataSource(dict(a=[], b=[]))     # steiner, BEFORE
    stA = ColumnDataSource(dict(a=[], b=[]))     # steiner, AFTER
    ftB = ColumnDataSource(dict(a=[], b=[]))     # stm fit, BEFORE
    ftA = ColumnDataSource(dict(a=[], b=[]))     # stm fit, AFTER
    f = figure(title=title, height=330, width=470, match_aspect=True,
               tools="pan,wheel_zoom,box_zoom,reset,save",
               active_scroll="wheel_zoom",
               x_axis_label="%s [cm]" % ha.upper(), y_axis_label="%s [cm]" % va.upper())
    f.scatter("a", "b", source=ctx, size=1.5, color="#b9b9b9", alpha=0.45)
    f.scatter("a", "b", source=tgt, size=3.5,
              color={"field": "q", "transform": cmap}, alpha=0.95)
    # reveal overlays -- empty unless the toggle is on
    f.scatter("a", "b", source=stB, size=2.0, color="#ff7f0e", alpha=0.30)
    f.scatter("a", "b", source=stA, size=2.0, color="#17becf", alpha=0.30)
    f.scatter("a", "b", source=ftB, size=5.0, color="#e377c2", alpha=0.9, marker="x")
    f.scatter("a", "b", source=ftA, size=5.0, color="#1f77b4", alpha=0.85, marker="cross")
    x0, x1 = VOL[ha]
    y0, y1 = VOL[va]
    f.line([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0],
           color="#d62728", line_width=1.2, line_dash="dashed")
    SRC[(ha, va)] = dict(ctx=ctx, tgt=tgt, stB=stB, stA=stA, ftB=ftB, ftA=ftA)
    FIGS[(ha, va)] = f


# ---------------------------------------------------------------------------
# widgets
# ---------------------------------------------------------------------------
def item_option(it):
    rec = LABELS.get(item_key(it), {})
    mark = rec.get("choice") or rec.get("label", "")
    return "%3d %s  evt %s cl %d  n=%d  %.0f cm%s" % (
        it["scan_id"], "*" if mark else " ", it["event"], it["cluster"],
        it["npts"], it["length"], ("   [%s]" % mark) if mark else "")


item_select = Select(title="Scan item", value=item_option(ITEMS[0]),
                     options=[item_option(i) for i in ITEMS], width=430)
prev_btn = Button(label="< prev", width=90)
next_btn = Button(label="next >", width=90)
next_unl_btn = Button(label="next unlabelled >>", width=150)
stm_btn = Button(label="STM  (stops inside)", button_type="success", width=200)
thru_btn = Button(label="THRU (through-going / exits)", button_type="primary", width=230)
frag_stm_btn = Button(label="FRAG → STM  (part of a stopper)",
                      button_type="success", width=250)
frag_thru_btn = Button(label="FRAG → THRU  (part of a TGM)",
                       button_type="primary", width=250)
messy_btn = Button(label="MESSY (not one track)", button_type="warning", width=190)
uncl_btn = Button(label="UNCLEAR", button_type="warning", width=120)
clear_btn = Button(label="clear this label", width=130)
zoom_tog = Toggle(label="Zoom to cluster", width=140)
dense_tog = Toggle(label="Dense context near cluster", width=200, active=True)
reveal_tog = Toggle(label="REVEAL before/after (answer key)", width=250,
                    button_type="danger")
notes = TextInput(title="notes (optional)", width=430)
progress = Div(text="", width=430)
status = Div(text="", width=1420)
reveal_div = Div(text="", width=1420)
header = Div(width=1420, text="""
<b>PDVD doc-08 STM hand scan</b> &mdash; 12 objects under
<code>retile_hack_max_bridge = 10&nbsp;cm</code> (doc pdhd/08 &sect;9.2&ndash;9.3).
<b>Some of these flipped their STM tag and some did not</b>, and you are not told which
&mdash; the ones that did not are the control on your own agreement rate.
<br><b>Judge the whole object, including the grey continuation.</b> Does it enter the
detector and <b>stop</b> inside the active volume, or pass through / exit a face?
<br><span style="color:#555">Coloured = the cluster (colour is its charge). Grey = all other
charge in the event; with <i>Dense context</i> on, <b>every</b> grey point within %.0f&nbsp;cm
of the cluster is drawn. Red dashed = the PDVD active boundary
(|x|&nbsp;&le;&nbsp;339.9, |y|&nbsp;&le;&nbsp;336.4, z&nbsp;0.8&ndash;298.4&nbsp;cm, doc pdvd/33).
Full detector by default on purpose &mdash; a cluster zoomed to its own extent looks
contained in every view. <b>x is drift and is cathode-centred</b>: drift distance is
x<sub>anode</sub>&nbsp;&minus;&nbsp;|x|, so both large +x and large &minus;x are near an anode.</span>
<br><span style="color:#a00"><b>PDVD scopes these layers to the STM-tagged set</b> (doc pdvd/39
r3), so under REVEAL an arm that did not tag the object draws <b>nothing</b> &mdash; an empty
overlay is that arm's verdict, not a missing file. The banner says so explicitly.</span>
<br><span style="color:#a00"><b>REVEAL is the answer key.</b> It draws both arms' Steiner
cloud (orange = before, cyan = after) and STM fit (magenta&nbsp;&times; = before,
blue&nbsp;+ = after &mdash; the red dashed box is the boundary, not a fit) and prints both
verdicts together with each arm's <code>persist_stm_fit</code> status/kink line. It is off by default because the direction of
a flip is the most biasing fact available; anything you label while it is on is recorded
with <code>revealed_before_label</code> so blind and revealed labels can be reported apart.</span>
""" % DENSE_R)

state = dict(idx=0)


def current():
    return ITEMS[state["idx"]]


def clear_reveal():
    for k in SRC:
        for s in ("stB", "stA", "ftB", "ftA"):
            SRC[k][s].data = dict(a=[], b=[])
    reveal_div.text = ""


def draw_reveal(it, axes):
    """Overlay both arms' Steiner cloud and STM fit, and print both verdicts."""
    e, cl = it["event"], it["cluster"]
    for arm, sk, fk in ((BASE_ARM, "stB", "ftB"), (KNOB_ARM, "stA", "ftA")):
        st = reveal_sel(e, arm, "steiner_graph", cl)
        ft = reveal_sel(e, arm, "stm_fit", cl)
        for ha, va in SRC:
            ax = dict(x=0, y=1, z=2)
            SRC[(ha, va)][sk].data = (dict(a=st[ax[ha]], b=st[ax[va]])
                                      if st is not None else dict(a=[], b=[]))
            SRC[(ha, va)][fk].data = (dict(a=ft[ax[ha]], b=ft[ax[va]])
                                      if ft is not None else dict(a=[], b=[]))
    def verdict(arm):
        d = reveal_layers(e, arm).get("stm")
        if d is None:
            return "no stm layer"
        return "STM-TAGGED" if cl in set(d[3].tolist()) else "not tagged"
    def nst(arm):
        s = reveal_sel(e, arm, "steiner_graph", cl)
        f = reveal_sel(e, arm, "stm_fit", cl)
        return (0 if s is None else len(s[0])), (0 if f is None else len(f[0]))
    sb, fb = nst(BASE_ARM)
    sa, fa = nst(KNOB_ARM)

    def scoped(arm, n):
        """PDVD writes steiner_graph/stm_fit ONLY for STM-tagged clusters."""
        if n == 0:
            return ("&nbsp; <span style='color:#a00'>(nothing drawn &mdash; this arm did not "
                    "tag it, and PDVD writes these layers only for tagged clusters)</span>")
        return ""

    def fitfmt(arm):
        ls = fit_lines(e, arm).get(cl)
        if not ls:
            return ("<br>&nbsp;&nbsp;&nbsp;<i>no persist_stm_fit line for this cluster "
                    "in the arm's log</i>")
        return "".join("<br>&nbsp;&nbsp;&nbsp;<code>%s</code>" % x for x in ls)
    reveal_div.text = (
        "<div style='background:#fff4f4;border:1px solid #d99;padding:6px'>"
        "<b>REVEALED &mdash; this is the answer key.</b><br>"
        "<b>BEFORE</b> (<code>%s</code>, knobs off): <b>%s</b> &nbsp;|&nbsp; steiner %d pts, "
        "stm_fit %d pts &nbsp; <span style='color:#ff7f0e'>&#9679; orange</span> / "
        "<span style='color:#e377c2'>&times; magenta</span>%s%s<br>"
        "<b>AFTER</b> (<code>%s</code>, bridge cap 10 cm): <b>%s</b> &nbsp;|&nbsp; steiner %d pts, "
        "stm_fit %d pts &nbsp; <span style='color:#17becf'>&#9679; cyan</span> / "
        "<span style='color:#1f77b4'>+ blue</span>%s%s<br>"
        "<span style='color:#555'>The verdict turns on <b>status / kink / exit_L / left_L</b>, "
        "not on the point count &mdash; a flip between two near-identical fits is normal, and "
        "those fields are what explain it.</span></div>"
        % (BASE_ARM, verdict(BASE_ARM), sb, fb, scoped(BASE_ARM, sb), fitfmt(BASE_ARM),
           KNOB_ARM, verdict(KNOB_ARM), sa, fa, scoped(KNOB_ARM, sa), fitfmt(KNOB_ARM)))


def render():
    it = current()
    ch = event_charge(it["event"])
    if ch is None:
        status.text = ("<b style='color:#b00'>missing</b> %s -- no mabc-pr.zip for event %s"
                       % (item_key(it), it["event"]))
        for k in SRC:
            SRC[k]["ctx"].data = dict(a=[], b=[])
            SRC[k]["tgt"].data = dict(a=[], b=[], q=[])
        clear_reveal()
        return
    X, Y, Z, Q, C = ch
    m = C == it["cluster"]
    P = np.c_[X, Y, Z]
    oi, step, n_near = context_index(P, m, bool(dense_tog.active))
    axes = dict(x=X, y=Y, z=Z)
    qt = Q[m]
    cmap.low = float(qt.min()) if qt.size else 0.0
    cmap.high = float(qt.max()) if qt.size else 1.0
    for ha, va in SRC:
        SRC[(ha, va)]["ctx"].data = dict(a=axes[ha][oi], b=axes[va][oi])
        SRC[(ha, va)]["tgt"].data = dict(a=axes[ha][m], b=axes[va][m], q=qt)
        f = FIGS[(ha, va)]
        if zoom_tog.active and m.any():
            pad = 20.0
            f.x_range.start = float(axes[ha][m].min() - pad)
            f.x_range.end = float(axes[ha][m].max() + pad)
            f.y_range.start = float(axes[va][m].min() - pad)
            f.y_range.end = float(axes[va][m].max() + pad)
        else:
            f.x_range.start, f.x_range.end = VOL[ha][0] - 20, VOL[ha][1] + 20
            f.y_range.start, f.y_range.end = VOL[va][0] - 20, VOL[va][1] + 20
    if reveal_tog.active:
        draw_reveal(it, axes)
    else:
        clear_reveal()
    rec = LABELS.get(item_key(it), {})
    notes.value = rec.get("notes", "")
    done = sum(1 for i in ITEMS if item_key(i) in LABELS)
    t1 = [i for i in ITEMS if i["tranche"] == 1]
    d1 = sum(1 for i in t1 if item_key(i) in LABELS)
    progress.text = ("<b>%d / %d</b> labelled &nbsp;|&nbsp; tranche 1: <b>%d / %d</b>"
                     "&nbsp;|&nbsp; this item: <b>%s</b>%s"
                     % (done, len(ITEMS), d1, len(t1),
                        rec.get("choice") or rec.get("label", "&mdash;"),
                        " <span style='color:#a00'>(revealed)</span>"
                        if rec.get("revealed_before_label") else ""))
    warn = ""
    if it["moved"]:
        kn = knob_npts(it["event"], it["cluster"])
        warn = ("&nbsp; <b style='color:#b00'>note: the two arms disagree on this cluster's "
                "point set; the panels show the %s partition (%d points), while in %s the same "
                "cluster id has %s points</b>"
                % (BASE_ARM, it["npts"], KNOB_ARM,
                   "no" if kn is None else str(kn)))
    status.text = ("event %s, cluster %d &mdash; %d points, %.0f cm, %d grey context points "
                   "(1 in %d overall%s)%s"
                   % (it["event"], it["cluster"], it["npts"], it["length"], len(oi), step,
                      ("; %d of them ALL charge within %.0f cm of the cluster"
                       % (n_near, DENSE_R)) if n_near else "", warn))


def refresh_options():
    opts = [item_option(i) for i in ITEMS]
    item_select.options = opts
    item_select.value = opts[state["idx"]]


def go(idx):
    state["idx"] = max(0, min(len(ITEMS) - 1, idx))
    refresh_options()
    render()


def set_label(choice):
    it = current()
    c = CHOICES[choice]
    LABELS[item_key(it)] = dict(label=c["label"], partial=c["partial"],
                                choice=choice, notes=notes.value,
                                revealed_before_label=bool(reveal_tog.active),
                                scan_id=it["scan_id"], event=it["event"],
                                cluster=it["cluster"], npts=it["npts"],
                                length_cm=it["length"], partition_moved=it["moved"])
    save_labels()
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


def on_select(attr, old, new):
    if new in item_select.options:
        go(item_select.options.index(new))


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


item_select.on_change("value", on_select)
prev_btn.on_click(lambda: go(state["idx"] - 1))
next_btn.on_click(lambda: go(state["idx"] + 1))
next_unl_btn.on_click(next_unlabelled)
stm_btn.on_click(lambda: set_label("STM"))
thru_btn.on_click(lambda: set_label("THRU"))
frag_stm_btn.on_click(lambda: set_label("FRAG_STM"))
frag_thru_btn.on_click(lambda: set_label("FRAG_THRU"))
messy_btn.on_click(lambda: set_label("MESSY"))
uncl_btn.on_click(lambda: set_label("UNCLEAR"))
clear_btn.on_click(clear_label)
# Toggle: bind on the `active` PROPERTY, not on_click.  on_click is wired to a
# browser button event, so a programmatic change of `active` -- which is how the
# headless end-to-end test in selftest_d08pv_scan.py drives the reveal -- silently
# does nothing, and a binding that only a human can exercise is a binding nothing
# tests.  on_change fires for both.  (bokeh 3 silent-binding trap.)
zoom_tog.on_change("active", lambda a, o, n: render())
dense_tog.on_change("active", lambda a, o, n: render())
reveal_tog.on_change("active", lambda a, o, n: render())

curdoc().add_root(column(
    header,
    row(item_select, prev_btn, next_btn, next_unl_btn),
    Div(text="<b>the cluster IS the whole object:</b>", width=1420),
    row(stm_btn, thru_btn),
    Div(text="<b>the cluster is only PART of the object</b> "
             "(under-clustered) &mdash; verdict is for the FULL object:", width=1420),
    row(frag_stm_btn, frag_thru_btn),
    row(messy_btn, uncl_btn, clear_btn, zoom_tog, dense_tog, reveal_tog),
    row(notes, progress),
    reveal_div,
    row(*[FIGS[(ha, va)] for ha, va, _ in PANELS]),
    status,
))
curdoc().title = "PDVD doc-08 STM scan (%s)" % SCAN_TAG
go(0)
