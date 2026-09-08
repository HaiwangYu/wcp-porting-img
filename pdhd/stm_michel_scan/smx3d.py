#!/usr/bin/env python3
"""doc pdhd/12 -- the rotatable 3-D view of the STM + Michel hand-scan display.

FORK BY DUPLICATION of sbnd/sbnd_xin/em_display/em3d.py (doc pr/114 round 3),
which is untouched.  The camera helpers and the CustomJS below are carried over
VERBATIM -- copied programmatically rather than retyped, so the JS the browser
runs here is byte-identical to the JS that has been driven by hand in em_display.
What is dropped is everything about SBND's Bee cloud (`load_bee_cloud`,
`bee_zip_path`, `bee_event_index`, `match_cluster_ids`, `candidate_clusters` and
their caches): this app's charge arrives already selected in the per-item
sidecar that prep_stm_michel_scan.py writes, so there is nothing to match or
decimate at draw time.

WHAT THIS IS
  Bokeh 3.9 has no 3-D glyph, so this is an ORTHOGRAPHIC TRACKBALL INSIDE AN
  ORDINARY BOKEH FIGURE.  Every glyph carries its 3-D columns plus the projected
  2-D pair it actually draws; a CustomJS recomputes the projection in the browser
  on each drag frame and calls source.change.emit().  Zero new dependencies, zero
  JS assets, zero build step -- and, because the glyphs live in normal data
  space, Bokeh's own tap and hover keep working, which is what lets the scanner
  pin the muon's stopping point by clicking in 3-D as well as in the projections.

  Bee is the other 3-D viewer in this project, and it is not an option here: it
  runs three.js r145 from a CDN, the only copy on disk is r71, its bundle is
  gitignored and unbuilt in this checkout, and there is no node/npm on this box.
  Vendoring it is a project, not a step.

THE TWO bokehjs FACTS IT RESTS ON, both read in the shipped bundle rather than
recalled (bokeh/server/static/js/bokeh.js):
  * UIEventBus.__trigger calls _trigger_bokeh_event unconditionally after the
    active-tool switch, so Pan / PanStart / PanEnd reach js_on_event even with no
    pan tool active, and PointEvent carries modifiers and cumulative deltas.
    That is what lets a bare drag mean "rotate" without a tool fighting for it.
  * GlyphRendererView.connect_signals binds data_source.change, so mutating
    source.data.<col> IN PLACE and emitting repaints locally instead of shipping
    every point back to the server on every frame.

HONEST LIMIT, inherited and then narrowed.  em3d's docstring records that its
CustomJS is not machine-tested because there is no JS engine in its tree.  There
IS one here -- playwright is installed in the .direnv python -- so
selftest_stm_michel_scan.py drives a real drag in headless chromium and asserts
the projected columns move.  The Python mirrors (project, camera_basis,
bounding_sphere) are asserted against the JS constants' own algebra as well.

FOUR BOKEH 3 TRAPS that bind zero handlers with no console error
(feedback_bokeh3_silent_js_traps) -- all four are live in this file's consumers:
  1. every view renders inside an OPEN shadow root, so document.getElementById
     from a CustomJS finds nothing;
  2. js_on_change on a widget with visible=False never reaches the client;
  3. a property set while the document is being BUILT is serialised as initial
     state, not emitted as a change -- curdoc().js_on_event(DocumentReady, cb)
     is the one channel that is neither hidden nor build-time;
  4. `pts` is a LIST of ColumnDataSources to JS_REDRAW, not one source.
"""
import math

def camera_basis(az, el):
    """Right / up / forward for an orthographic camera at azimuth `az` and
    elevation `el` (radians).  Orthonormal by construction -- which is what makes
    the framing in `bounding_sphere` rotation-invariant."""
    ca, sa = math.cos(az), math.sin(az)
    ce, se = math.cos(el), math.sin(el)
    right = (-sa, ca, 0.0)
    up = (-ca * se, -sa * se, ce)
    fwd = (ca * ce, sa * ce, se)
    return right, up, fwd


def project(pts, az, el, centre=(0.0, 0.0, 0.0)):
    """(u, v, d) for a sequence of (x, y, z).  `d` is depth along the view
    direction, used only for depth cueing.  The Python mirror of JS_PROJECT."""
    r, u, f = camera_basis(az, el)
    cx, cy, cz = centre
    out = []
    for p in pts:
        px, py, pz = p[0] - cx, p[1] - cy, p[2] - cz
        out.append((px * r[0] + py * r[1] + pz * r[2],
                    px * u[0] + py * u[1] + pz * u[2],
                    px * f[0] + py * f[1] + pz * f[2]))
    return out


def sphere_about(pts, centre, pad=1.25, floor=30.0):
    """Radius framing `pts` about a centre SOMEONE ELSE chose (doc pdhd/12 sec 13).

    `bounding_sphere` picks the centre that minimises the radius; this one takes
    the centre as given -- the muon's stopping point -- and returns the radius
    that still frames everything from it.  The framing guarantee is the same and
    rests on the same fact: right/up/fwd is orthonormal, so
    |(u, v)| <= |p - centre| <= R for every camera, and nothing can swing out of
    frame as the object turns.

    THE COST, stated rather than discovered: a stopping point sits at one END of
    the muon, so R here is the muon's full length where `bounding_sphere` gave
    half of it.  The default 3-D view is therefore about twice as wide.  That is
    the price of rotating about the stop instead of about the middle, and it is
    paid once per item now that the zoom survives a label click.
    """
    if not pts:
        return floor
    cx, cy, cz = centre
    r = 0.0
    for p in pts:
        d = math.sqrt((p[0] - cx) ** 2 + (p[1] - cy) ** 2 + (p[2] - cz) ** 2)
        if d > r:
            r = d
    return max(floor, r * pad)


def bounding_sphere(pts, pad=1.15, floor=30.0):
    """(centre, R) framing a point set.

    The frame is set from the 3-D bounding sphere and NEVER from the projected
    extent.  Because right/up/fwd is orthonormal, |(u,v)| <= |p - centre| <= R
    for every camera, so an elongated track swinging from broadside to end-on can
    neither balloon out of frame nor shrink to a dot -- zoom stays entirely the
    user's.  Framing off the projected extent would re-fit on every drag frame,
    which is the same failure the Range1d-not-DataRange1d comment in the viewer
    warns about, one level up.
    """
    if not pts:
        return (0.0, 0.0, 0.0), floor
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    c = (0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys)),
         0.5 * (min(zs) + max(zs)))
    r = 0.0
    for p in pts:
        d = math.sqrt((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2)
        if d > r:
            r = d
    return c, max(floor, r * pad)


# Preset cameras, (azimuth, elevation) in degrees.  Three of them reproduce the
# 2-D panels EXACTLY, which is the point -- a scanner who loses their bearings in
# 3-D can step back to a view they already trust and then rotate out of it again.
# Worked through from camera_basis:
#   az=-90, el=+89  ->  right=+x, up=+y   : the X-Y panel
#   az=-90, el=  0  ->  right=+x, up=+z   : the X-Z panel
#   az=  0, el=  0  ->  right=+y, up=+z   : Y-Z with the axes swapped
# `right` always has rz == 0 (there is no roll), so a z-horizontal Y-Z view is
# not reachable; "z-y" is the honest name for what the third one shows.
PRESETS = {
    "x-y": (-90.0, 89.0),
    "x-z": (-90.0, 0.0),
    "z-y": (0.0, 0.0),
    "iso": (-55.0, 20.0),
}
PRESET_ORDER = ["iso", "x-y", "x-z", "z-y"]


JS_PROJECT = r"""
// --- camera --------------------------------------------------------------
// Mirror of em3d.camera_basis / em3d.project.  Orthonormal triple, so
// u^2 + v^2 + d^2 == |p - centre|^2 exactly (the selftest pins this in Python).
const _az = cam.data.az[0], _el = cam.data.el[0];
const _cx = cam.data.cx[0], _cy = cam.data.cy[0], _cz = cam.data.cz[0];
const _R  = cam.data.R[0] || 1.0;
const _ca = Math.cos(_az), _sa = Math.sin(_az);
const _ce = Math.cos(_el), _se = Math.sin(_el);
const rx = -_sa,       ry =  _ca,       rz = 0.0;
const ux = -_ca * _se, uy = -_sa * _se, uz = _ce;
const fx =  _ca * _ce, fy =  _sa * _ce, fz = _se;
"""

JS_REDRAW = JS_PROJECT + r"""
// --- point layers --------------------------------------------------------
// Depth CUEING, not depth sorting.  Bokeh draws in row order, so the only
// occlusion cue available without permuting every column on every frame is
// alpha and size falling off with depth -- and that is the cue that actually
// carries depth in a still frame.  Motion parallax covers the rest on a drag.
// ptalpha / ptsize / ptcue are three PARALLEL ARRAYS indexed the same way as
// `pts`, because the viewer keeps one table (_PT_CFG) that both the Python fill
// and these frames read -- neither mirror carries its own copy of a base size.
//
// (An array of {size, alpha, cue} objects would also work: Bokeh serialises a
// Python dict as {"type":"map", ...} but bokehjs's `_decode_map` returns a plain
// object whenever every key is a string.  It returns a real JS **Map** as soon
// as one key is not -- which is the shape trap worth remembering, and the one
// selftest_em_display.py guards.)
for (let s = 0; s < pts.length; s++) {
    const d = pts[s].data;
    const n = d.x.length;
    const a0 = ptalpha[s], s0 = ptsize[s], cue = ptcue[s] > 0.5;
    const u = new Float64Array(n), v = new Float64Array(n);
    const al = new Float64Array(n), sz = new Float64Array(n);
    for (let i = 0; i < n; i++) {
        const px = d.x[i] - _cx, py = d.y[i] - _cy, pz = d.z[i] - _cz;
        u[i] = px * rx + py * ry + pz * rz;
        v[i] = px * ux + py * uy + pz * uz;
        if (cue) {
            const t = 0.5 + 0.5 * ((px * fx + py * fy + pz * fz) / _R);
            const tc = t < 0 ? 0 : (t > 1 ? 1 : t);
            al[i] = a0 * (0.30 + 0.70 * tc);
            sz[i] = s0 * (0.70 + 0.60 * tc);
        } else {
            al[i] = a0;
            sz[i] = s0;
        }
    }
    d.u = u; d.v = v; d.al = al; d.sz = sz;
    // In-place mutation + change.emit(): repaints locally (GlyphRendererView
    // connects data_source.change -> update_data) without assigning .data,
    // which would ship every point back to the server on every drag frame.
    pts[s].change.emit();
}
// --- polyline layers -----------------------------------------------------
for (let s = 0; s < lines.length; s++) {
    const d = lines[s].data;
    const n = d.xs3.length;
    const xs = new Array(n), ys = new Array(n);
    for (let i = 0; i < n; i++) {
        const X = d.xs3[i], Y = d.ys3[i], Z = d.zs3[i], m = X.length;
        const a = new Float64Array(m), b = new Float64Array(m);
        for (let j = 0; j < m; j++) {
            const px = X[j] - _cx, py = Y[j] - _cy, pz = Z[j] - _cz;
            a[j] = px * rx + py * ry + pz * rz;
            b[j] = px * ux + py * uy + pz * uz;
        }
        xs[i] = a; ys[i] = b;
    }
    d.xs = xs; d.ys = ys;
    lines[s].change.emit();
}
// --- arrow heads ---------------------------------------------------------
// The head angle has no 3-D analogue: it is the projected direction, so it must
// be recomputed here alongside u/v.  Bokeh's triangle marker points at +y.
for (let s = 0; s < heads.length; s++) {
    const d = heads[s].data;
    const n = d.x.length;
    const u = new Float64Array(n), v = new Float64Array(n), an = new Float64Array(n);
    for (let i = 0; i < n; i++) {
        const px = d.x[i] - _cx, py = d.y[i] - _cy, pz = d.z[i] - _cz;
        const qx = d.x0[i] - _cx, qy = d.y0[i] - _cy, qz = d.z0[i] - _cz;
        const uu = px * rx + py * ry + pz * rz;
        const vv = px * ux + py * uy + pz * uz;
        const u0 = qx * rx + qy * ry + qz * rz;
        const v0 = qx * ux + qy * uy + qz * uz;
        u[i] = uu; v[i] = vv;
        an[i] = Math.atan2(vv - v0, uu - u0) - Math.PI / 2.0;
    }
    d.u = u; d.v = v; d.angle = an;
    heads[s].change.emit();
}
"""

JS_PANSTART = r"""
// Hammer reports deltas CUMULATIVE from the gesture start, so the handler must
// anchor on the state at panstart and add -- integrating per frame would drift.
const d = cam.data;
d.az0[0] = d.az[0];  d.el0[0] = d.el[0];
d.xs0[0] = xr.start; d.xe0[0] = xr.end;
d.ys0[0] = yr.start; d.ye0[0] = yr.end;
"""

JS_ROTATE = r"""
// A bare drag rotates.  The guard is the whole mode system: the moment the user
// picks Box Select (or Pan) in the toolbar, rotation steps aside for it -- no
// extra mode UI, and no gesture fought over by two handlers.  (Pan events reach
// js_on_event even with no pan tool active; see the module docstring.)
//
// The guard reads `toolbar.gestures.pan.active`, NOT `toolbar.active_drag`, and
// the difference is not cosmetic.  `active_drag` is the CONFIGURATION property
// ("auto" by default, set to null here); bokehjs's Toolbar._active_change writes
// the live state to `this.gestures[et].active` and never touches active_drag,
// so a guard on active_drag stays null forever and rotation would fight
// box-select on every drag.  `gestures.pan.active` is exactly what
// UIEventBus.__trigger itself consults.  BoxSelect, BoxZoom, Lasso and Pan all
// declare event_type "pan", so this one check covers every drag tool.
const _g = p.toolbar.gestures;
if (_g != null && _g.pan != null && _g.pan.active != null) { return; }
const d = cam.data;
const dx = cb_obj.delta_x || 0.0, dy = cb_obj.delta_y || 0.0;
const shift = cb_obj.modifiers ? cb_obj.modifiers.shift : false;
if (shift) {
    const W = d.xe0[0] - d.xs0[0], H = d.ye0[0] - d.ys0[0];
    const wpx = p.inner_width || p.width || 800;
    const hpx = p.inner_height || p.height || 640;
    const ox = -dx / wpx * W, oy = dy / hpx * H;
    xr.start = d.xs0[0] + ox; xr.end = d.xe0[0] + ox;
    yr.start = d.ys0[0] + oy; yr.end = d.ye0[0] + oy;
    return;
}
const K = 0.0075;                       // rad per pixel
let el = d.el0[0] - dy * K;
const lim = Math.PI / 2.0 - 0.02;       // never look exactly down the pole
if (el >  lim) el =  lim;
if (el < -lim) el = -lim;
d.az[0] = d.az0[0] + dx * K;
d.el[0] = el;
""" + JS_REDRAW

JS_PANEND = r"""
// One round trip per gesture, not per frame.  THE ONE DIVERGENCE from em3d's
// verbatim JS (2026-09-08): em3d sent .toFixed(4) because nothing read the
// value back.  The viewer now DOES -- it is the only channel by which the
// server ever learns the angle the scanner dragged to, and every repaint
// re-sends the whole of cam_src.data, so a 1e-4 rad rounding here is a 0.02 cm
// jump in the picture on every label click.  Number.toString gives the shortest
// representation that parses back to the same double, so the round trip is
// exact rather than merely close.
const d = cam.data;
camtxt.value = String(d.az[0]) + "," + String(d.el[0]);
"""

# Set the camera from Python (preset buttons, sliders, event load) and redraw.
JS_APPLY = JS_REDRAW
