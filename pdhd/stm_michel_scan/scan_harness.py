#!/usr/bin/env python3
"""doc pdvd/55 -- drive the doc pdhd/12 hand-scan display from an agent.

    ./scan_harness.py --det pdvd --tag smx1a shots  --out DIR --items KEY[,KEY...]
    ./scan_harness.py --det pdvd --tag smx1a apply  --verdicts FILE.json
    ./scan_harness.py --det pdvd --tag smx1a context --items KEY[,KEY...]

WHY A BROWSER AND NOT A SECOND RENDERER.  The obvious cheap path is a matplotlib
script over the same `smprep-*.json` sidecars.  It is the wrong path: it would be
a SECOND INSTRUMENT whose fidelity to what the scanner sees on the served app
would itself need gating, and any silent disagreement between the two would
invalidate every label taken through it without ever failing a check.  So this
drives THE APP -- the same `stm_michel_viewer.py`, the same Bokeh document, the
same glyphs -- in headless chromium, and reads pixels back out.

    Fork of the launch/drive pattern in selftest_smx3d_browser.py:199-246
    (free_port, `bokeh serve` on a scratch port, the exited-process check, and
    `page.evaluate` onto named models through the real websocket).

IT DOES NOT TOUCH THE VIEWER, AND IT DOES NOT TOUCH PORT 5017.  The owner scans
on 5017 while this runs; every run here takes its own scratch port, and the
`bokeh serve` busy-port trap (a second server logs one line, exits, and the OLD
app keeps answering every check you make -- feedback_bokeh_port_in_use_stale_app)
is guarded by the same exited-process poll the selftest uses.

WRITES GO THROUGH THE REAL WIDGETS, never through a JSON writer.  Two reasons,
both load-bearing:
  * the object-table keys are NOT uniform -- a fitted segment row is keyed
    str(seg["id"]) (stm_michel_viewer.py:2265) and a whole unfitted cluster row
    "C%d" % cluster_id (:2317).  A hand-rolled writer that got that wrong would
    have its tags silently dropped by render()'s restore, with the file looking
    perfectly well-formed.
  * clicking exercises the pin's nearest-chain-index snap, the PF write-through
    and the SAVE path, so what lands on disk is what the app writes, not what
    this file believes the app writes.

THE ONE THING TO KNOW ABOUT THE SCREENSHOTS.  Bokeh 3 renders every view inside
an OPEN shadow root, so a flat querySelectorAll finds nothing
(feedback_bokeh3_silent_js_traps trap 1).  Canvases are collected by the same
recursive walk selftest_smx3d_browser.py:100-130 uses, and figures are told
apart by their canvas SIZE, which is unique per view in this layout:

    760x760  the 3-D trackball        470x330  one of the three projections
    430x300  one of the nine 2-D measurement panels
    620x330  dQ/dx vs signed arc length

Every figure owns TWO stacked canvases of identical geometry (Bokeh gives each
one a second, fully transparent, overlay); they are deduplicated on their rect.

A DEFECT FOUND WHILE BUILDING THIS, REPORTED AND NOT FIXED HERE.  `Zoom to
object` does nothing to the three projection panels in a browser, and the three
panels are therefore ALWAYS drawn at full detector extent whatever the toggle
says.  The chain of evidence:

  * the toggle does reach the server -- cam3.seq bumps, so render(reframe=True)
    ran -- and render does assign `f.x_range.start/end`
    (stm_michel_viewer.py:1591-1596);
  * driving the SAME app in process through runpy, the assignment holds: the
    side panel goes from (-19.2, 318.4) to (199.4, 318.0), the chain's own z
    span;
  * in a browser the ranges never move, from a real DOM click as much as from a
    property assignment, and a CLIENT assignment is reverted too -- within about
    a second, read back as the full volume again;
  * because `figure(...)` was called without `x_range=`/`y_range=`
    (stm_michel_viewer.py:455-460), these panels carry **DataRange1d**, whose
    start/end are an OUTPUT of auto-ranging over the renderers and not an input.
    Every assignment is transient.  And the data being auto-ranged over includes
    the full-detector boundary box and the seam lines drawn at :489-496, so what
    auto-ranging lands on is always the whole detector.

The nine measurement panels take their server-set ranges perfectly well, which
is the control: they are built with explicit shared ranges (:782, :803).

The scan does not need the toggle.  A human's wheel-zoom works (an interactive
tool suspends auto-ranging, a bare assignment does not), and everything the
projections would have shown zoomed is already covered: the 3-D panel has real
Range1d ranges, centres on the pin and zooms, and the measurement tab shows the
same neighbourhood in measured charge per plane.  So this harness takes the
projections at full extent -- which is what they are FOR here, telling a stopper
from a through-goer -- and does its zooming in 3-D.
"""
import argparse, json, os, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BOKEH = "/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/bokeh"

# Tall enough that the whole document is inside the viewport: page.screenshot's
# `clip` is viewport-relative, and a rect below the fold clips to nothing --
# which is also why the selftest scrolls before its drag.
VIEW_W, VIEW_H = 1920, 2400

TAB_3D, TAB_PROJ, TAB_MEAS = 0, 1, 2

# ---------------------------------------------------------------------------
# JS helpers.  Every one of these goes over the real websocket, so a property
# set here reaches the server callback exactly as a human click does.
# ---------------------------------------------------------------------------
JS_FIND = """
  const _all = () => { const d = Bokeh.documents[0];
    return d._all_models ? Array.from(d._all_models.values()) : (d.all_models || []); };
  const _by = (pred) => _all().filter(pred);
"""

JS_CANVASES = """() => {
  const out = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll('*')) {
      if (el.tagName === 'CANVAS') out.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  const seen = {}, res = [];
  for (const c of out) {
    const r = c.getBoundingClientRect();
    // checkVisibility() is what tells an inactive tab's canvas from the live
    // one: Bokeh keeps both in the DOM and both report a full rect.
    const vis = (typeof c.checkVisibility === 'function')
                ? c.checkVisibility() : (c.offsetParent !== null);
    if (!vis || r.width < 2 || r.height < 2) continue;
    const k = [Math.round(r.x), Math.round(r.y), Math.round(r.width),
               Math.round(r.height)].join(',');
    if (seen[k]) continue;
    seen[k] = 1;
    res.push({x: r.x, y: r.y, w: r.width, h: r.height});
  }
  return res;
}"""

JS_SET_ITEM = """(want) => {
%s
  const sel = _by(m => m.type === 'Select' && m.title === 'Scan item')[0];
  if (!sel) return 'no item Select';
  const opt = sel.options.find(o => o.indexOf(want) >= 0);
  if (!opt) return 'no option matching ' + want;
  sel.value = opt;
  return 'ok';
}""" % JS_FIND

JS_SET_TAB = """(i) => {
%s
  const t = _by(m => m.type === 'Tabs')[0];
  if (!t) return 'no Tabs';
  t.active = i;
  return 'ok';
}""" % JS_FIND

JS_TOGGLE = """(a) => {
%s
  const t = _by(m => m.type === 'Toggle' && m.label === a[0])[0];
  if (!t) return 'no Toggle ' + a[0];
  if (t.active !== a[1]) t.active = a[1];
  return 'ok';
}""" % JS_FIND

JS_RADIO = """(a) => {
%s
  const g = _by(m => m.type === 'RadioButtonGroup'
                     && JSON.stringify(m.labels) === JSON.stringify(a[0]))[0];
  if (!g) return 'no RadioButtonGroup ' + JSON.stringify(a[0]);
  g.active = a[1];
  return 'ok';
}""" % JS_FIND

JS_TEXT = """(a) => {
%s
  const t = _by(m => m.type === 'TextInput' && m.title === a[0])[0];
  if (!t) return 'no TextInput titled ' + a[0];
  t.value = a[1];
  return 'ok';
}""" % JS_FIND

# A Button fires on_click through a ButtonClick EVENT, not a property change,
# so it cannot be driven by assignment the way the widgets above are.
JS_CLICK = """(lab) => {
%s
  const b = _by(m => m.type === 'Button' && m.label === lab)[0];
  if (!b) return 'no Button ' + lab;
  const E = Bokeh.require ? null : null;
  try {
    b.trigger_event(new Bokeh.Models('ButtonClick')());
  } catch (e) {
    try { b.trigger_event(new (Bokeh.require('models/widgets/buttons/button').ButtonClick)()); }
    catch (e2) { return 'cannot construct ButtonClick: ' + e + ' | ' + e2; }
  }
  return 'ok';
}""" % JS_FIND

JS_TABLE = """() => {
%s
  const d = Bokeh.documents[0];
  const t = d.get_model_by_name('seg_table');
  if (!t) return null;
  const s = t.source;
  const o = {};
  for (const k of Object.keys(s.data)) o[k] = Array.from(s.data[k]);
  o._selected = Array.from(s.selected.indices);
  return o;
}""" % JS_FIND

JS_SELECT_ROW = """(i) => {
  const t = Bokeh.documents[0].get_model_by_name('seg_table');
  if (!t) return 'no seg_table';
  // Clear FIRST.  The table opens with row 0 already selected, so assigning
  // [0] is not a change, no property change is emitted, the server's
  // on_seg_pick never runs -- and the tag button that follows then applies to
  // whatever the server last adopted.  That is how row 0 of an item silently
  // ends up untagged.
  t.source.selected.indices = [];
  t.source.selected.indices = [i];
  return 'ok';
}"""

JS_DIVS = """() => {
  const d = Bokeh.documents[0];
  const g = (n) => { const m = d.get_model_by_name(n); return m ? m.text : null; };
  return {status: g('status_div'), flow: g('flow_div'), seg_head: g('seg_head'),
          key: (d.get_model_by_name('copy_key') || {}).value};
}"""

# The ON-CHAIN pin control.  Its server callback is bound to `value_throttled`
# (stm_michel_viewer.py:2966), which the browser sets only at the END of a real
# drag -- so setting `value` alone moves the handle and nothing else.
JS_SLIDER = """(a) => {
%s
  const s = _by(m => m.type === 'Slider' && String(m.title).indexOf(a[0]) >= 0)[0];
  if (!s) return 'no Slider ' + a[0];
  if (a[1] < s.start || a[1] > s.end)
    return 'residual range ' + a[1] + ' outside this item\\'s ['
           + s.start + ', ' + s.end + ']';
  s.value = a[1];
  s.value_throttled = a[1];
  return 'ok';
}""" % JS_FIND

JS_BBOX = """(names) => {
  const d = Bokeh.documents[0];
  let lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30], n = 0;
  for (const nm of names) {
    const m = d.get_model_by_name('src3_' + nm);
    if (!m) continue;
    const X = m.data.x || [], Y = m.data.y || [], Z = m.data.z || [];
    for (let i = 0; i < X.length; i++) {
      const p = [X[i], Y[i], Z[i]];
      for (let k = 0; k < 3; k++) {
        if (p[k] < lo[k]) lo[k] = p[k];
        if (p[k] > hi[k]) hi[k] = p[k];
      }
      n++;
    }
  }
  return n ? {lo: lo, hi: hi, n: n} : null;
}"""

JS_ZOOM_3D = """(h) => {
  const d = Bokeh.documents[0];
  const f = d.get_model_by_name('f3d');
  if (!f) return 'no f3d';
  // The pin is the rotation centre, so it projects to (0,0) at every camera:
  // a symmetric box about the origin IS a box about the stopping point.
  f.x_range.setv({start: -h, end: h});
  f.y_range.setv({start: -h, end: h});
  return 'ok';
}"""

JS_CAM = """(a) => {
  const c = Bokeh.documents[0].get_model_by_name('cam3');
  if (!c) return 'no cam3';
  c.data.az[0] = a[0];
  c.data.el[0] = a[1];
  // js_on_change('data', ...) binds properties.data.change, NOT the model's
  // generic `change`.  Mutating in place and emitting the wrong one leaves the
  // picture exactly where it was -- no error, and two byte-identical files.
  c.properties.data.change.emit();   // cam_src.js_on_change('data', JS_APPLY)
  return 'ok';
}"""


# ---------------------------------------------------------------------------
def free_port(start):
    for p in range(start, start + 60):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise SystemExit("no free port")


class App:
    """The served viewer plus a chromium page pointed at it."""

    def __init__(self, det, tag, labeldir=None, logdir="/home/xqian/tmp"):
        self.det, self.tag = det, tag
        self.port = free_port(5300)
        self.logpath = os.path.join(logdir, "scan_harness_%d.log" % self.port)
        args = ["--det", det, "--tag", tag]
        if labeldir:
            args += ["--labeldir", labeldir]
        self.log = open(self.logpath, "w")
        self.proc = subprocess.Popen(
            [BOKEH, "serve", "--port", str(self.port),
             "--allow-websocket-origin=localhost:%d" % self.port,
             "--session-token-expiration", "86400",
             os.path.join(HERE, "stm_michel_viewer.py"), "--args"] + args,
            stdout=self.log, stderr=subprocess.STDOUT)
        self.url = "http://localhost:%d/stm_michel_viewer" % self.port
        for _ in range(400):
            if self.proc.poll() is not None:
                raise SystemExit("bokeh serve exited rc=%s -- see %s"
                                 % (self.proc.returncode, self.logpath))
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", self.port)) == 0:
                    break
            time.sleep(0.2)
        else:
            raise SystemExit("bokeh serve never opened %d" % self.port)
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch()
        self.page = self.browser.new_page(viewport={"width": VIEW_W, "height": VIEW_H})
        self.errs = []
        self.page.on("pageerror", lambda e: self.errs.append(str(e)))
        self.page.goto(self.url, wait_until="networkidle", timeout=180000)
        self.page.wait_for_timeout(2500)

    def close(self):
        try:
            self.browser.close()
        finally:
            self._pw.stop()
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()

    # -- driving -----------------------------------------------------------
    def _ev(self, js, arg=None, what=""):
        r = self.page.evaluate(js, arg) if arg is not None else self.page.evaluate(js)
        if r != "ok" and isinstance(r, str) and what:
            raise SystemExit("%s failed: %s" % (what, r))
        return r

    def click(self, label, settle=900):
        """Press a real Button.  DOM first -- that is what a human does -- with
        the model event as the fallback for a button the layout has scrolled or
        a shadow root hides from the text engine."""
        try:
            self.page.get_by_role("button", name=label, exact=True).first.click(timeout=4000)
        except Exception:
            r = self.page.evaluate(JS_CLICK, label)
            if r != "ok":
                raise SystemExit("cannot press %r: %s" % (label, r))
        self.page.wait_for_timeout(settle)

    def goto(self, key, settle=1800, tries=4):
        """Switch items, and CHECK the app actually switched.

        Saving a label rewrites every entry of the item Select's `options`
        (item_option stamps the choice into the text), so a value assigned from
        a list the client had a moment earlier can name a string that no longer
        exists -- Bokeh drops it silently and the app stays where it was, which
        would label the WRONG ITEM.  Re-read the options and try again.
        """
        ev, cl = key.split("/")
        want = "evt %s cl %s " % (ev, cl)
        got = ""
        for n in range(tries):
            self._ev(JS_SET_ITEM, want, "goto %s" % key)
            # POLL, do not sleep a fixed amount.  After an item with a dozen
            # tag clicks the server has a queue of callbacks to work through and
            # the switch can take several seconds; a fixed wait turns that into
            # a spurious "the app is showing the previous item".
            for _ in range(int(settle / 250) + 24):
                self.page.wait_for_timeout(250)
                got = self.page.evaluate(JS_DIVS)["key"] or ""
                if key in got:
                    return
        raise SystemExit("asked for %s, the app is showing %r after %d tries"
                         % (key, got, tries))

    def tab(self, i, settle=700):
        self._ev(JS_SET_TAB, i, "set tab %d" % i)
        self.page.wait_for_timeout(settle)

    def toggle(self, label, on, settle=900):
        self._ev(JS_TOGGLE, [label, bool(on)], "toggle %s" % label)
        self.page.wait_for_timeout(settle)

    def radio(self, labels, active, settle=600):
        self._ev(JS_RADIO, [labels, int(active)], "radio %s" % labels[:1])
        self.page.wait_for_timeout(settle)

    def text(self, title, value, settle=400):
        self._ev(JS_TEXT, [title, value], "text %s" % title)
        self.page.wait_for_timeout(settle)

    def table(self):
        return self.page.evaluate(JS_TABLE)

    def pick_row(self, i, settle=700):
        self._ev(JS_SELECT_ROW, i, "select row %d" % i)
        self.page.wait_for_timeout(settle)

    def divs(self):
        return self.page.evaluate(JS_DIVS)

    def camera(self, az, el, settle=700):
        self._ev(JS_CAM, [az, el], "camera")
        self.page.wait_for_timeout(settle)

    def slider(self, title_part, value, settle=1000):
        self._ev(JS_SLIDER, [title_part, float(value)], "slider %s" % title_part)
        self.page.wait_for_timeout(settle)

    def bbox(self, names):
        return self.page.evaluate(JS_BBOX, list(names))

    def zoom_3d(self, half, settle=600):
        self._ev(JS_ZOOM_3D, float(half), "zoom_3d")
        self.page.wait_for_timeout(settle)

    # -- pixels ------------------------------------------------------------
    def canvases(self):
        return self.page.evaluate(JS_CANVASES)

    def shoot(self, path, want, pad=4):
        """Screenshot the union of every visible canvas of size class `want`.

        `want` is a list of (w, h) tolerated to a few px -- Bokeh rounds.
        """
        cs = [c for c in self.canvases()
              if any(abs(c["w"] - w) < 6 and abs(c["h"] - h) < 6 for w, h in want)]
        if not cs:
            raise SystemExit("no visible canvas of size %s (saw %s)"
                             % (want, [(round(c["w"]), round(c["h"]))
                                       for c in self.canvases()]))
        x0 = min(c["x"] for c in cs) - pad
        y0 = min(c["y"] for c in cs) - pad
        x1 = max(c["x"] + c["w"] for c in cs) + pad
        y1 = max(c["y"] + c["h"] for c in cs) + pad
        x0, y0 = max(0.0, x0), max(0.0, y0)
        self.page.screenshot(path=path, clip=dict(x=x0, y=y0,
                                                  width=min(x1, VIEW_W) - x0,
                                                  height=min(y1, VIEW_H) - y0))
        return dict(n=len(cs), x=x0, y=y0, w=x1 - x0, h=y1 - y0)


SZ_3D = [(760, 760)]
SZ_PROJ = [(470, 330)]
SZ_MEAS = [(430, 300)]
SZ_DQDX = [(620, 330)]


# Layers that make up "the object": the muon chain and everything the chain
# calls a product of its stop.  `near`/`far` are deliberately excluded -- they
# are the whole event's imaged charge, and framing on them would undo the zoom.
OBJ_LAYERS = ["muon", "michel", "dots", "gamma", "delta", "survey", "pfseg"]
D3_HALF = 45.0          # cm about the pin in the 3-D panel
# Three cameras 90 deg apart in azimuth, at a modest elevation.  The pin is the
# rotation centre (owner 2026-09-08), so all three are views OF THE STOP.
CAM = [(0.60, 0.35), (2.17, 0.35), (3.74, 0.35)]


def do_shots(app, keys, out):
    """Seven frames per item, in the order a scanner actually looks at them."""
    os.makedirs(out, exist_ok=True)
    made = {}
    for key in keys:
        d = os.path.join(out, key.replace("/", "_"))
        os.makedirs(d, exist_ok=True)
        app.goto(key)
        # Particle flow ON: the per-segment colouring is the whole basis of the
        # attribution half of the scan.  `bundle only` stays at its default (on).
        app.toggle("show particle flow", True)

        # 1. the three projections, at the full detector extent they are stuck
        # at (docstring).  That is the frame this question wants anyway: does
        # the track end inside the volume, or reach a face?  An object framed on
        # itself looks contained in every projection, which is how a through-
        # goer reads as a stopper (doc pdhd/12).
        app.tab(TAB_PROJ)
        app.shoot(os.path.join(d, "a_proj_full.png"), SZ_PROJ)

        # 2. the whole object in 3-D, then the stop at three azimuths 90 deg
        # apart.  Three, because the owner's rule -- gammas lie ALONG the Michel
        # direction, and activity close to the track and BACKWARD is not the
        # Michel -- is a 3-D judgement, and one viewing angle can fake either
        # answer by projecting a separation to zero.
        app.tab(TAB_3D)
        app.camera(*CAM[0])
        app.shoot(os.path.join(d, "b_3d_wide.png"), SZ_3D)
        for nm, (az, el) in zip(("c", "d", "e"), CAM):
            app.camera(az, el)
            app.zoom_3d(D3_HALF)
            app.shoot(os.path.join(d, "%s_3d_stop.png" % nm), SZ_3D)

        # 3. the nine measured / predicted / difference panels around the stop
        # -- did it stop, or leave through a dead region, and is that Michel
        # real charge or a prediction artefact.  This is the zoomed 2-D view of
        # the real image, and it is the one the projections cannot give.
        app.tab(TAB_MEAS)
        app.radio(["whole cluster", "± 150 around the stop"], 1)
        app.shoot(os.path.join(d, "f_meas.png"), SZ_MEAS)

        # 4. the Bragg evidence.  Always visible, so no tab switch.
        app.shoot(os.path.join(d, "g_dqdx.png"), SZ_DQDX)

        ctx = context_of(app)
        json.dump(ctx, open(os.path.join(d, "context.json"), "w"), indent=1)
        made[key] = d
        print("shot %s -> %s  (%d objects)" % (key, d, len(ctx["objects"])))
    return made


def payload_of(det, key):
    ev, cl = key.split("/")
    p = os.path.join(HERE, "prep-" + det, "smprep-%s-c%s.json" % (ev, cl))
    return json.load(open(p)) if os.path.exists(p) else None


def face_distances(det, key):
    """Both ends of the chain, and how far each is from leaving the detector.

    The STM-vs-through-going call turns on exactly this, and it is the one thing
    the picture cannot resolve: the three projections are locked at the full
    detector extent (docstring), so ~700 cm is drawn across 470 px and 10 cm
    from a face is about seven pixels.  `entry_*` and `stop_*` are persisted
    scalars, and `smgeom.ENVELOPE` is the same active boundary the panels draw
    as the red dashed box, so nothing here is a new measurement -- it is the
    display's own numbers read at a resolution the eye is not being given.
    """
    import smgeom
    pay = payload_of(det, key)
    if pay is None:
        return {}
    v = pay.get("verdict") or {}
    env = smgeom.ENVELOPE[det]
    out = {}
    for nm, pre in (("entry", "entry_"), ("stop", "stop_")):
        try:
            p = [float(v[pre + a]) for a in "xyz"]
        except (KeyError, TypeError, ValueError):
            continue
        d = {a: round(min(p[i] - env[a][0], env[a][1] - p[i]), 1)
             for i, a in enumerate("xyz")}
        out[nm] = dict(xyz=[round(c, 1) for c in p], face=d,
                       nearest=min(d, key=d.get), d_face=min(d.values()))
    try:
        out["seams_at_stop"] = {
            k: round(x, 1) for k, x in
            smgeom.seam_distances(det, *out["stop"]["xyz"]).items()}
    except Exception:
        pass
    out["in_fv"] = v.get("in_fv")
    out["reject_names"] = v.get("reject_names")
    out["is_stm"] = v.get("is_stm")
    return out


def _norm(v):
    m = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5
    return [c / m for c in v] if m > 1e-9 else [0.0, 0.0, 0.0]


def object_geometry(det, key, pin):
    """Where each object sits relative to the stop, in the muon's own frame.

    The app's object table carries `d_stop` for a whole-cluster row and leaves
    it blank for a fitted segment, and it carries no direction at all.  Both are
    exactly what the owner's rule needs: "most of the gammas go along the Michel
    direction, but if the activity is close to the track and BACKWARD, very
    likely it is not part of the Michel."  So this reads the same sidecar the
    app is drawing from and answers, per object: how far from the stop, and
    which side of it.

    This is a READING AID for the pictures, not a classifier -- nothing here
    decides anything, and the verdicts are taken off the frames.
    """
    pay = payload_of(det, key)
    if pay is None:
        return {}
    mu = pay.get("muon") or {}
    MX, MY, MZ = mu.get("x") or [], mu.get("y") or [], mu.get("z") or []
    rr = mu.get("rr") or []

    # the muon's direction of travel at the stop: from the last point that is
    # ~20 cm of residual range back, to the stop itself.
    fwd = [0.0, 0.0, 0.0]
    if len(MX) > 2 and len(rr) == len(MX):
        j = min(range(len(rr)), key=lambda i: rr[i])
        far = min(range(len(rr)), key=lambda i: abs(rr[i] - 20.0))
        fwd = _norm([MX[j] - MX[far], MY[j] - MY[far], MZ[j] - MZ[far]])

    pts = {}
    for sg in (pay.get("pf") or {}).get("seg") or []:
        pts[str(sg["id"])] = list(zip(sg["x"], sg["y"], sg["z"]))
    near = pay.get("image_near") or {}
    if near.get("c"):
        by = {}
        for x, y, z, c in zip(near["x"], near["y"], near["z"], near["c"]):
            by.setdefault("C%d" % int(c), []).append((x, y, z))
        for k, v in by.items():
            pts.setdefault(k, v)

    out = {}
    for k, P in pts.items():
        if not P:
            continue
        d = [((q[0] - pin[0]) ** 2 + (q[1] - pin[1]) ** 2
              + (q[2] - pin[2]) ** 2) ** 0.5 for q in P]
        cen = [sum(q[i] for q in P) / len(P) for i in range(3)]
        u = _norm([cen[i] - pin[i] for i in range(3)])
        out[k] = dict(n=len(P),
                      d_min=round(min(d), 2), d_max=round(max(d), 2),
                      cen=[round(c, 1) for c in cen],
                      # +1 straight on past the stop, -1 back along the muon
                      cos_fwd=round(sum(u[i] * fwd[i] for i in range(3)), 2))
    return out


def context_of(app):
    """The non-visual half of what the scanner has in front of them."""
    t = app.table() or {}
    n = len(t.get("key") or [])
    objs = [dict(i=i, key=t["key"][i], group=t["group"][i], obj=t["obj"][i],
                 npts=t["npts"][i], size=t["size"][i], dqdx=t["dqdx"][i],
                 dstop=t["dstop"][i], chain=t["chain"][i]) for i in range(n)]
    d = app.divs()
    key = d.get("key") or ""
    pinb = app.bbox(["pin"])
    pin = [0.5 * (pinb["lo"][i] + pinb["hi"][i]) for i in range(3)] if pinb else None
    geo = object_geometry(app.det, key, pin) if (pin and "/" in key) else {}
    for o in objs:
        g = geo.get(o["key"])
        if g:
            o.update(g)
    return dict(key=key, pin=[round(c, 2) for c in pin] if pin else None,
                ends=face_distances(app.det, key) if "/" in key else {},
                objects=objs, seg_head=d.get("seg_head"),
                status=d.get("status"), flow=d.get("flow"))


VERDICT_BTN = {
    "STM_MICHEL": "STM + MICHEL",
    "STM_ONLY": "STM, no Michel",
    "THRU": "THRU (through-going / exits)",
    "FRAG_STM_MICHEL": "FRAG → STM + MICHEL",
    "FRAG_STM_ONLY": "FRAG → STM, no Michel",
    "FRAG_THRU": "FRAG → THRU",
    "MESSY": "MESSY (not one track)",
    "UNCLEAR": "UNCLEAR",
}
TAG_BTN = {
    "muon": "→ muon",
    "michel": "→ Michel",
    "gamma": "→ gamma",
    "delta / other": "delta / other",
    "straddles the stop": "straddles",
    None: "→ unassigned",
}
MICHEL_KINDS = ["— not set —", "none", "attached", "detached dots", "both"]


def do_apply(app, spec, labelfile):
    """One scanned item onto the real widgets, in the order a human uses them.

    notes and michel_kind BEFORE the verdict button, because set_label() reads
    them off the widgets; the tags before it too, so the label click stores them
    in the same act.
    """
    for it in spec:
        key = it["key"]
        app.goto(key)
        app.toggle("show particle flow", True)

        if it.get("notes"):
            app.text("notes (optional) — type BEFORE clicking a label", it["notes"])

        mk = it.get("michel_kind", "— not set —")
        if mk not in MICHEL_KINDS:
            raise SystemExit("%s: michel_kind %r not in the alphabet" % (key, mk))
        app.radio(MICHEL_KINDS, MICHEL_KINDS.index(mk))

        # tags.  The table row order is the app's, so address rows by KEY and
        # never by position -- the group column re-sorts as tags are applied.
        want = dict(it.get("tags") or {})
        # EVERY drawn object carries a tag (owner 2026-09-08), including the
        # ones where the scanner agrees with the chain.  Checking only that the
        # tags you LISTED landed cannot catch a row you forgot to list: that
        # saves cleanly, with pf_tagged simply smaller than n_pf_objects.  So
        # the coverage is asserted here, by name, before anything is written.
        have = list((app.table() or {}).get("key") or [])
        if not it.get("allow_partial"):
            miss = [k for k in have if k not in want]
            if miss:
                raise SystemExit("%s: %d of %d objects carry no tag: %s"
                                 % (key, len(miss), len(have), miss))
        # Address rows by KEY, never by position: the group column re-sorts as
        # tags are applied.
        #
        # And do NOT use that column to decide which rows still need clicking.
        # `group` is the scanner's tag WHEN THERE IS ONE and the chain's own
        # grouping otherwise (stm_michel_viewer.py:2054), so on every row where
        # the scanner agrees with the chain the two are indistinguishable -- a
        # "skip the ones that already read right" loop skips exactly the
        # agreements, which are most of them, and writes a row whose pf_segments
        # is silently short.  So: click every row, every pass, and let the
        # FILE ON DISK be the check.  set_pf_tag is idempotent, so extra passes
        # cost time and nothing else.
        # THE ROW ORDER MOVES UNDER YOU.  object_rows() sorts by GROUP_ORDER
        # then id (stm_michel_viewer.py:2040), so every tag RE-SORTS the table.
        # The row is addressed by INDEX -- that is the only handle a Bokeh
        # DataTable selection has -- so an index computed from a table read
        # taken before the repaint arrives points at a different object, and
        # the tag lands on that one instead.  On 039253_14/49 that scrambled
        # four of eight rows and four passes could not converge, because each
        # pass mis-tagged about as many rows as it fixed.
        #
        # So: never compute an index from a single read.  Read until two
        # consecutive reads agree on the order, and after each click poll until
        # the row actually carries the tag.
        def stable_keys(tries=10):
            prev, t = None, {}
            for _ in range(tries):
                t = app.table() or {}
                cur = list(t.get("key") or [])
                if cur and cur == prev:
                    return cur, list(t.get("group") or [])
                prev = cur
                app.page.wait_for_timeout(350)
            return list(t.get("key") or []), list(t.get("group") or [])

        def tag_pass():
            keys, grp = stable_keys()
            wait = 650 + 6 * max(len(keys), 1)
            for k in want:
                for _ in range(3):
                    if k not in keys:
                        raise SystemExit("%s: object row %r left the table"
                                         % (key, k))
                    app.pick_row(keys.index(k), settle=wait)
                    app.click(TAG_BTN[want[k]], settle=wait)
                    # `group` is the scanner's tag once set (viewer:2052), so
                    # this says the CLICK LANDED.  On a row whose tag agrees
                    # with the chain it reads right either way -- which is why
                    # the file on disk stays the authority below.
                    for _ in range(12):
                        keys, grp = stable_keys()
                        if k in keys and grp and grp[keys.index(k)] == want[k]:
                            break
                        app.page.wait_for_timeout(400)
                    if k in keys and grp and grp[keys.index(k)] == want[k]:
                        break

        tag_pass()

        # Two ways to move the stop, and they mean different things.
        # `pin_rr` slides it ALONG the drawn trajectory to a residual range and
        # records source="pin"; `pin` puts it at a free x,y,z and records
        # source="manual" with off_fit set -- i.e. "the true stop is not on this
        # fit at all".  Prefer the slider: saying the fit overshot is a weaker
        # and more common claim than saying the fit is in the wrong place.
        pin = it.get("pin")
        if it.get("pin_rr") is not None:
            app.slider("residual range", it["pin_rr"])
        elif pin:
            app.text("x", "%.2f" % pin[0])
            app.text("y", "%.2f" % pin[1])
            app.text("z", "%.2f" % pin[2])
            app.click("pin at x,y,z")

        # Scale the wait with the work just queued: on a 53-object item the tag
        # clicks leave a long callback queue, and a verdict click still sitting
        # in it means SAVE refuses the item for having no verdict.
        vs = max(1200, 60 * len(want))
        app.click(VERDICT_BTN[it["verdict"]], settle=vs)
        app.click("SAVE this item", settle=vs)

        rec, short = None, []
        for _ in range(4):
            rec = None
            for _ in range(20):        # the write is a websocket round trip
                rec = json.load(open(labelfile))["labels"].get(key)
                if rec is not None:
                    break
                app.page.wait_for_timeout(1000)
            if rec is None:
                # Both clicks can be swallowed while the server works through
                # the queue of tag callbacks this item just made, and SAVE
                # refuses an item that has no verdict yet -- so press the
                # verdict again too, not only SAVE.
                print("  %s: not on disk yet -- verdict + SAVE again" % key)
                app.click(VERDICT_BTN[it["verdict"]], settle=3000)
                app.click("SAVE this item", settle=3000)
                continue
            short = [k for k in want
                     if (rec.get("pf_segments") or {}).get(k) != want[k]]
            if not short:
                break
            print("  %s: %d tag(s) short on disk (%s) -- another pass"
                  % (key, len(short), short[:4]))
            tag_pass()
            app.click("SAVE this item", settle=1200)
        else:
            raise SystemExit("%s: did not land: %s"
                             % (key, "nothing on disk" if rec is None else short))

        got = dict(label=rec.get("label"), choice=rec.get("choice"),
                   kind=rec.get("michel_kind"), tags=rec.get("pf_tagged"))
        exp_choice = it["verdict"]
        if got["choice"] != exp_choice or got["kind"] != mk \
           or got["tags"] != len(want):
            raise SystemExit("%s: disk says %r, asked for choice=%s kind=%r tags=%d"
                             % (key, got, exp_choice, mk, len(want)))
        p = rec.get("pin") or {}
        print("saved %s  %-16s %-14s tags=%d%s"
              % (key, got["label"], got["kind"], got["tags"],
                 ("  pin %s moved %.2f cm" % (p.get("source"), p.get("moved_cm") or 0.0))
                 if p.get("placed") else ""))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["shots", "apply", "context"])
    ap.add_argument("--det", default="pdvd")
    ap.add_argument("--tag", default="smx1a")
    ap.add_argument("--labeldir", default=None)
    ap.add_argument("--items", default="")
    ap.add_argument("--items-file", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--verdicts", default=None)
    a = ap.parse_args(argv)

    keys = [k for k in a.items.split(",") if k.strip()]
    if a.items_file:
        keys += [l.strip() for l in open(a.items_file) if l.strip()
                 and not l.startswith("#")]

    # TWO dirnames.  HERE is <img>/pdhd/stm_michel_scan, so one lands on
    # <img>/pdhd and the join would read back <img>/pdhd/pdvd/work/... -- a path
    # the viewer never writes, because the viewer computes its own.  The failure
    # is invisible until an `apply` run without --labeldir.
    labeldir = a.labeldir or os.path.join(
        os.path.dirname(os.path.dirname(HERE.rstrip("/"))),
        a.det, "work", "stm_michel_labels", a.tag)
    labelfile = os.path.join(labeldir, "labels.json")

    app = App(a.det, a.tag, a.labeldir)
    try:
        if a.cmd == "shots":
            if not a.out:
                raise SystemExit("shots needs --out")
            do_shots(app, keys, a.out)
        elif a.cmd == "context":
            out = {}
            for k in keys:
                app.goto(k)
                app.toggle("show particle flow", True)
                out[k] = context_of(app)
            print(json.dumps(out, indent=1))
        else:
            spec = json.load(open(a.verdicts))
            do_apply(app, spec, labelfile)
        if app.errs:
            print("JS ERRORS: %s" % app.errs[:5], file=sys.stderr)
            return 1
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
