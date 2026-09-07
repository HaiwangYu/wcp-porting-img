"""doc sbnd_xin/pr/148 -- the blind EM / HADRONIC / MIXED scan display.

Owner request, 2026-09-06: *"you should build a display like stm_display one,
with X-Y, Y-Z, Z-X projection view, and then ask me to put in the answer.
Please use port 5017."*

Run it:
    ./pr148_scan/serve_pr148_scan.sh 5017 [--scan-tag NAME]
    ssh -o ServerAliveInterval=30 -L 5017:localhost:5017 <user>@wcgpu1
    http://localhost:5017/pr148_scan_viewer

FORK BY DUPLICATION (M10).  The three-panel projection block, the Range1d
rule and the detector box are lifted from em_display/em_display_viewer.py
(:57, :193-210); em_display/, split_display/ and pr_display/ are untouched
and still serve their own scans.  Same shape as pdhd/d05_scan, forked from
pdhd/stm_scan.

WHAT IS ON SCREEN, AND WHY EACH THING IS THERE

  Three projections at the FULL detector volume with the active boundary
  dashed.  Full volume is the default on purpose: an object auto-zoomed to
  its own extent fills the frame whatever it is, which flattens exactly the
  "is this a 30 cm stub or a 5 m cascade" judgement.  `Zoom to object` exists
  and is not the default.

  coloured  the object's own segments, one dot per fit point, coloured by
            dQ/dx in MIP units on a FIXED 0.5-3.5 scale.  Fixed, not
            per-object: a per-object rescale makes every object contain its
            own reddest prong, so a 3 MIP proton and a 1 MIP electron stem
            paint identically and the colour stops carrying information.
  grey      every other segment in the event.  An absorbed far blob or a
            neighbouring muon is context the verdict needs.
  red X     the object's start vertex.
  red O     its farthest fit point from that vertex.

WHAT IS DELIBERATELY ABSENT.  The A5 discriminants (growth / bragg / stem),
the derived candidates (n_heavy / f_heavy / star), the A5 verdict, the
stratum, the nue BDT score, the SEGMENT COUNT (doc sec 11 -- it became sec 8's
discriminant, and a count printed next to a bar of 10 is the verdict printed),
and every segment's particle_id / particle_score / flag_shower.  The last group matters most: it is the reconstruction's own
typing answer, and the scan exists to check that answer.
selftest_pr148_scan.py proves the absence by enumerating the keys of every
ColumnDataSource this module builds, rather than asserting it.

THE ANSWER is three buttons -- EM, HADRONIC, MIXED -- plus a `weak` toggle
and a free-text note.  Every click rewrites labels.json AND filled_sheet.tsv,
so a lost browser costs the object in hand, not the session.
"""
import argparse, csv, json, os, sys, time

from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (Button, CheckboxGroup, ColorBar, ColumnDataSource,
                          Div, LinearColorMapper, Range1d, Select, Slider,
                          TextInput, Toggle)
from bokeh.palettes import Turbo256
from bokeh.plotting import figure
from bokeh.transform import linear_cmap

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)

# SBND active volume (cm) -- the same numbers em_display, pr_display and
# nusel_display use (em_display_viewer.py:57).
DET_BOX = dict(x=(-201.05, 201.05), y=(-199.312, 199.312), z=(0.85, 500.15))
MIP_LO, MIP_HI = 0.5, 3.5
VERDICTS = ("EM", "HADRONIC", "MIXED")

ap = argparse.ArgumentParser()
ap.add_argument("--sheet", default=os.path.join(SX, "docs", "pr",
                                                "pr148-pidscan-manifest.tsv"))
ap.add_argument("--prepdir", default=os.path.join(HERE, "prep"))
ap.add_argument("--scan-tag", default="scan0",
                help="names the label directory; a fresh tag per pass, never "
                     "written into an existing one (M13)")
args, _ = ap.parse_known_args(sys.argv[1:])

LABDIR = os.path.join(SX, "work", "pr148_scan_labels", args.scan_tag)
os.makedirs(LABDIR, exist_ok=True)
LABJSON = os.path.join(LABDIR, "labels.json")
LABSHEET = os.path.join(LABDIR, "filled_sheet.tsv")


# ---------------------------------------------------------------------------
# Inputs.  The manifest IS the sample: a committed file, not whatever the
# shell happened to expand, which is what makes the scan reproducible.
# ---------------------------------------------------------------------------
def read_sheet(path):
    with open(path) as fh:
        head = [l for l in fh if l.startswith("#")]
    with open(path) as fh:
        body = [l for l in fh if not l.startswith("#")]
    return head, list(csv.DictReader(body, delimiter="\t"))


SHEET_HEAD, SHEET = read_sheet(args.sheet)
SHEET_COLS = list(SHEET[0].keys())

PAYLOAD = {}
for r in SHEET:
    p = os.path.join(args.prepdir, "pr148prep-evt%s-s%s.json"
                     % (r["event"], r["shower_id"]))
    with open(p) as fh:
        PAYLOAD[int(r["idx"])] = json.load(fh)

LABELS = {}
if os.path.exists(LABJSON):
    with open(LABJSON) as fh:
        LABELS = {int(k): v for k, v in json.load(fh).items()}


def save_labels():
    with open(LABJSON, "w") as fh:
        json.dump({str(k): v for k, v in LABELS.items()}, fh, indent=1)
    with open(LABSHEET, "w") as fh:
        fh.writelines(SHEET_HEAD)
        fh.write("\t".join(SHEET_COLS) + "\n")
        for r in SHEET:
            lab = LABELS.get(int(r["idx"]), {})
            out = dict(r)
            out["verdict"] = lab.get("verdict", "")
            out["weak"] = "1" if lab.get("weak") else ""
            out["note"] = lab.get("note", "")
            fh.write("\t".join(str(out[c]) for c in SHEET_COLS) + "\n")


# ---------------------------------------------------------------------------
# The three panels
# ---------------------------------------------------------------------------
proj_kw = dict(height=420, width=520, tools="pan,wheel_zoom,box_zoom,reset,save",
               active_scroll="wheel_zoom", match_aspect=False)
# Range1d, never figure()'s default DataRange1d: DataRange1d auto-refits to
# renderer data on every CDS push, which silently undoes the full-volume
# framing the moment a new object is drawn (em_display_viewer.py:195-198).
f_xy = figure(name="f_xy", title="X-Y  (drift vs vertical)",
              x_range=Range1d(*DET_BOX["x"]), y_range=Range1d(*DET_BOX["y"]),
              **proj_kw)
f_yz = figure(name="f_yz", title="Y-Z  (beam view)",
              x_range=Range1d(*DET_BOX["z"]), y_range=Range1d(*DET_BOX["y"]),
              **proj_kw)
f_zx = figure(name="f_zx", title="Z-X  (top view)",
              x_range=Range1d(*DET_BOX["z"]), y_range=Range1d(*DET_BOX["x"]),
              **proj_kw)
f_xy.xaxis.axis_label, f_xy.yaxis.axis_label = "x (cm)", "y (cm)"
f_yz.xaxis.axis_label, f_yz.yaxis.axis_label = "z (cm)", "y (cm)"
f_zx.xaxis.axis_label, f_zx.yaxis.axis_label = "z (cm)", "x (cm)"
PROJ = ((f_xy, "x", "y"), (f_yz, "z", "y"), (f_zx, "z", "x"))

# One CDS per layer, shared by all three panels: a point carries x/y/z and
# each figure names the two columns it needs.
mem_src = ColumnDataSource(data=dict(x=[], y=[], z=[], mip=[]))
oth_src = ColumnDataSource(data=dict(x=[], y=[], z=[]))
lin_src = {k: ColumnDataSource(data=dict(xs=[], ys=[])) for k in ("xy", "yz", "zx")}
box_src = {k: ColumnDataSource(data=dict(xs=[], ys=[])) for k in ("xy", "yz", "zx")}
st_src = ColumnDataSource(data=dict(x=[], y=[], z=[]))
fa_src = ColumnDataSource(data=dict(x=[], y=[], z=[]))

cmap = linear_cmap("mip", Turbo256, MIP_LO, MIP_HI)
psize = Slider(start=1, end=8, value=3, step=1, title="point size", width=200)
gsize = Slider(start=1, end=6, value=2, step=1, title="context size", width=200)

for f, ax, ay in PROJ:
    k = {"f_xy": "xy", "f_yz": "yz", "f_zx": "zx"}[f.name]
    f.multi_line("xs", "ys", source=box_src[k], line_color="#888888",
                 line_dash="dashed", line_width=1)
    f.scatter(ax, ay, source=oth_src, size=gsize.value, color="#b9b9b9",
              alpha=0.55, name="ctx_%s" % k)
    f.multi_line("xs", "ys", source=lin_src[k], line_color="#404040",
                 line_width=1, alpha=0.35)
    f.scatter(ax, ay, source=mem_src, size=psize.value, color=cmap,
              name="mem_%s" % k)
    f.scatter(ax, ay, source=st_src, marker="x", size=16, color="#d62728",
              line_width=3)
    # fill_color, NOT color: `color=` writes fill AND line, so `color=None`
    # followed by line_color is two settings racing for the same property and
    # the marker can end up invisible -- half of what says where the object
    # ends.  Hollow is fill_color=None with the outline set explicitly.
    f.scatter(ax, ay, source=fa_src, marker="circle", size=13, fill_color=None,
              line_color="#d62728", line_width=3)

cbar = ColorBar(color_mapper=LinearColorMapper(palette=Turbo256, low=MIP_LO,
                                               high=MIP_HI),
                title="dQ/dx  (MIP)", width=12)
f_xy.add_layout(cbar, "right")

def _sizes(attr, old, new):
    for k in ("xy", "yz", "zx"):
        f = {"xy": f_xy, "yz": f_yz, "zx": f_zx}[k]
        f.select(name="mem_%s" % k)[0].glyph.size = psize.value
        f.select(name="ctx_%s" % k)[0].glyph.size = gsize.value


psize.on_change("value", _sizes)
gsize.on_change("value", _sizes)


def det_lines(ax, ay):
    (a0, a1), (b0, b1) = DET_BOX[ax], DET_BOX[ay]
    return dict(xs=[[a0, a1, a1, a0, a0]], ys=[[b0, b0, b1, b1, b0]])


for f, ax, ay in PROJ:
    box_src[{"f_xy": "xy", "f_yz": "yz", "f_zx": "zx"}[f.name]].data = \
        det_lines(ax, ay)


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
state = dict(i=0, busy=False)

hdr = Div(text="", width=1120)
info = Div(text="", width=1120)
prog = Div(text="", width=1120)

sel = Select(title="object", options=[], value="0", width=330)
b_prev = Button(label="◀ prev", width=95)
b_next = Button(label="next ▶", width=95)
b_em = Button(label="EM", button_type="primary", width=150, height=44)
b_had = Button(label="HADRONIC", button_type="danger", width=150, height=44)
b_mix = Button(label="MIXED", button_type="warning", width=150, height=44)
b_clear = Button(label="clear this label", width=150)
weak = CheckboxGroup(labels=["weak / not confident"], active=[], width=210)
note = TextInput(title="note (optional)", width=560)
zoomer = Toggle(label="Zoom to object (default OFF: full volume)", width=330)


def label_of(i):
    return LABELS.get(i, {})


def refresh_texts():
    p = PAYLOAD[state["i"]]
    lab = label_of(state["i"])
    v = lab.get("verdict", "")
    hdr.text = (
        "<div style='font-size:17px'><b>object %d of %d</b> &nbsp;&mdash;&nbsp; "
        "run %s subrun %s <b>event %s</b> &nbsp; object id <b>%s</b> &nbsp; "
        "<span style='color:%s'><b>%s</b></span></div>"
        % (state["i"] + 1, len(SHEET), p["run"], p["subrun"], p["event"],
           p["obj"], "#2ca02c" if v else "#999999",
           (v + (" (weak)" if lab.get("weak") else "")) if v else "unlabelled"))
    info.text = (
        "<div style='font-size:13px;color:#333'>"
        "charge energy <b>%.1f MeV</b> &nbsp;|&nbsp; best energy <b>%.1f MeV</b> "
        "&nbsp;|&nbsp; total length <b>%.1f cm</b> &nbsp;|&nbsp; "
        "farthest point from the start vertex <b>%.1f cm</b>"
        "<br/><span style='color:#777'>colour is dQ/dx in MIP units, fixed "
        "%.1f&ndash;%.1f across every object; grey is all other charge in the "
        "event; red X is the start vertex, red O the far end. "
        "Question: is this object an EM shower, a hadronic interaction, or "
        "both clustered together?</span></div>"
        % (p["kine_charge_mev"], p["kine_best_mev"], p["total_len_cm"],
           p["far_dist_cm"], MIP_LO, MIP_HI))
    done = sum(1 for k in LABELS if LABELS[k].get("verdict"))
    prog.text = ("<div style='font-size:13px'><b>%d of %d labelled.</b> "
                 "Written on every click to<br/><code>%s</code><br/>"
                 "<code>%s</code></div>" % (done, len(SHEET), LABJSON, LABSHEET))
    opts = []
    for j, rr in enumerate(SHEET):
        mark = LABELS.get(j, {}).get("verdict", "")
        opts.append((str(j), "%2d  evt %-7s  %s" % (j + 1, rr["event"],
                                                    mark or "—")))
    sel.options = opts
    sel.value = str(state["i"])


def draw():
    p = PAYLOAD[state["i"]]
    mx, my, mz, mm = [], [], [], []
    for s in p["members"]:
        mx += s["x"]; my += s["y"]; mz += s["z"]; mm += s["mip"]
    ox, oy, oz = [], [], []
    for s in p["others"]:
        ox += s["x"]; oy += s["y"]; oz += s["z"]
    mem_src.data = dict(x=mx, y=my, z=mz, mip=mm)
    oth_src.data = dict(x=ox, y=oy, z=oz)
    for k, (ax, ay) in (("xy", ("x", "y")), ("yz", ("z", "y")),
                        ("zx", ("z", "x"))):
        lin_src[k].data = dict(xs=[s[ax] for s in p["members"]],
                               ys=[s[ay] for s in p["members"]])
    st_src.data = dict(x=[p["start"][0]], y=[p["start"][1]], z=[p["start"][2]])
    fa_src.data = dict(x=[p["far"][0]], y=[p["far"][1]], z=[p["far"][2]])
    apply_zoom()
    refresh_texts()


def apply_zoom():
    p = PAYLOAD[state["i"]]
    if not zoomer.active:
        for f, ax, ay in PROJ:
            f.x_range.start, f.x_range.end = DET_BOX[ax]
            f.y_range.start, f.y_range.end = DET_BOX[ay]
        return
    pts = dict(x=[], y=[], z=[])
    for s in p["members"]:
        for a in "xyz":
            pts[a] += s[a]
    pad = 25.0
    for f, ax, ay in PROJ:
        f.x_range.start, f.x_range.end = min(pts[ax]) - pad, max(pts[ax]) + pad
        f.y_range.start, f.y_range.end = min(pts[ay]) - pad, max(pts[ay]) + pad


def goto(i):
    if state["busy"]:
        return
    state["busy"] = True
    try:
        state["i"] = max(0, min(len(SHEET) - 1, i))
        lab = label_of(state["i"])
        weak.active = [0] if lab.get("weak") else []
        note.value = lab.get("note", "")
        draw()
    finally:
        state["busy"] = False


def set_verdict(v):
    def cb():
        LABELS.setdefault(state["i"], {})
        LABELS[state["i"]].update(
            verdict=v, weak=bool(weak.active), note=note.value,
            event=PAYLOAD[state["i"]]["event"],
            shower_id=PAYLOAD[state["i"]]["shower_id"],
            ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
        save_labels()
        refresh_texts()
        if state["i"] < len(SHEET) - 1:
            goto(state["i"] + 1)
    return cb


def clear_label():
    LABELS.pop(state["i"], None)
    save_labels()
    weak.active = []
    note.value = ""
    refresh_texts()


b_em.on_click(set_verdict("EM"))
b_had.on_click(set_verdict("HADRONIC"))
b_mix.on_click(set_verdict("MIXED"))
b_clear.on_click(clear_label)
b_prev.on_click(lambda: goto(state["i"] - 1))
b_next.on_click(lambda: goto(state["i"] + 1))
sel.on_change("value", lambda a, o, n: goto(int(n)) if int(n) != state["i"] else None)
zoomer.on_click(lambda act: apply_zoom())

LEGEND = Div(width=1120, text=
             "<div style='font-size:13px;background:#f4f4f4;padding:7px 10px;"
             "border-left:4px solid #666'>"
             "<b>EM</b> &mdash; an electron or photon shower. &nbsp; "
             "<b>HADRONIC</b> &mdash; a pion / proton / neutron interaction: it "
             "should not be typed 11 and should not be valued as EM. &nbsp; "
             "<b>MIXED</b> &mdash; both, clustered into one object. &nbsp; "
             "Tick <b>weak</b> if you are not confident; the note is free text."
             "</div>")

curdoc().add_root(column(
    hdr, info, LEGEND,
    row(sel, b_prev, b_next, zoomer, psize, gsize),
    row(f_xy, f_yz),
    row(f_zx, column(Div(text="<div style='height:14px'></div>"),
                     row(b_em, b_had, b_mix),
                     row(weak, b_clear), note, prog)),
))
curdoc().title = "pr/148 EM vs hadronic scan"
goto(0)
