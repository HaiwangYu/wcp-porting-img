#!/usr/bin/env python3
"""doc pdhd/12 -- drive the 3-D view's CustomJS in a real browser.

Run:  ./selftest_smx3d_browser.py [--det pdhd] [--port 5099]

em3d.py's docstring records an honest limit: "there is no JS engine and no node
in this tree, so the CustomJS is not machine-tested".  That is true of its home
tree and NOT of this one -- playwright is installed in the .direnv python -- so
this file closes the gap for the fork rather than inheriting the caveat.

It starts the app on a scratch port, opens it in headless chromium, reads the
projected `u` column of the muon layer out of the live document, performs a real
mouse drag over the 3-D canvas, and asserts that

  * the projection MOVED (the drag reached JS_ROTATE at all),
  * every layer moved with it (a source left out of the `pts` list would stay
    frozen at the camera it was filled from and drift off the picture),
  * the row count did not change (an in-place mutation, not a re-fill), and
  * |u|^2 + |v|^2 + d^2 is preserved point by point -- the basis is orthonormal,
    so a drag may rotate the picture but can never change any point's distance
    from the camera centre.  That last one is what would catch a sign error in
    the JS that a "did the pixels change" test would sail past.

It then does the same for the two things added in the measurement round:

  * the 2-D MEASUREMENT tab -- switch to it and assert nine canvases actually
    put ink on the page.  It is run on the HEAVIEST item of the arm (22 106
    cells on PDHD, 20 574 on PDVD, drawn three times over), because that is the
    one that would be unusable if anything is, and the first-paint time is
    printed rather than asserted.
  * the PARTICLE FLOW toggle and the grouped object table (doc pdvd/53) --
    pressed as real widgets,
    so the server callback and the round trip back are both under test.
  * the dQ/dx CLICK LINK -- select a point through the live document and assert
    the cursor appears in the 3-D layer AND in all three measurement rows.  The
    selection is set in the BROWSER, so it travels the websocket and fires the
    real server callback; the in-process gate in selftest_stm_michel_scan.py
    cannot test that hop.

and the one added on 2026-09-08, which is the reason this file exists:

  * THE DRAG SURVIVES A SERVER REPAINT.  The camera the scanner drags to lives
    ONLY in the browser -- JS_ROTATE mutates cam.data.az/el in place -- so the
    server's copy is whatever it last pushed.  Every repaint re-sends the whole
    of cam_src.data, and until camtxt was wired back that meant a label click
    snapped the view to the iso preset.  Nothing in-process can see this: with
    no browser there is no second copy of the camera to disagree with.  So:
    drag, zoom, click a real label button, and assert the projected columns,
    the camera angle and the ranges are all exactly where the drag left them.

Four Bokeh 3 traps make a broken binding look like a working page with no
console error, so a failure here is read as "the handler never bound", not as
"the formula is wrong": see feedback_bokeh3_silent_js_traps.
"""
import argparse, json, os, re, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BOKEH = "/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/bokeh"

FAILS = []
NPASS = [0]


def ck(cond, what):
    if cond:
        NPASS[0] += 1
    else:
        FAILS.append(what)
        print("  FAIL  %s" % what)


def free_port(start):
    for p in range(start, start + 40):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise SystemExit("no free port")


READ = """() => {
  const d = Bokeh.documents[0];
  const out = {};
  for (const n of %s) {
    const m = d.get_model_by_name('src3_' + n);
    out[n] = m ? {u: Array.from(m.data.u || []), v: Array.from(m.data.v || []),
                  x: Array.from(m.data.x || []), y: Array.from(m.data.y || []),
                  z: Array.from(m.data.z || [])} : null;
  }
  const c = d.get_model_by_name('cam3');
  out._cam = c ? {az: c.data.az[0], el: c.data.el[0], cx: c.data.cx[0],
                  cy: c.data.cy[0], cz: c.data.cz[0], R: c.data.R[0]} : null;
  return out;
}"""


INK = """() => {
  // Bokeh 3 renders every view inside an OPEN shadow root, so a flat
  // querySelectorAll finds nothing (feedback_bokeh3_silent_js_traps trap 1).
  const out = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll('*')) {
      if (el.tagName === 'CANVAS') out.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  return out.map(c => {
    const r = c.getBoundingClientRect();
    let ink = -1;
    try {
      const ctx = c.getContext('2d');          // null on the webgl 3-D canvas
      if (ctx && c.width > 0) {
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        ink = 0;
        for (let i = 0; i < d.length; i += 4 * 7) {
          // ALPHA FIRST.  Bokeh gives every figure two canvases and the second
          // is fully transparent; getImageData returns 0,0,0,0 there, so an
          // rgb-only test counts every one of its pixels as ink and the whole
          // probe reports a constant.
          if (d[i + 3] > 10 && (d[i] < 245 || d[i + 1] < 245 || d[i + 2] < 245)) ink++;
        }
      }
    } catch (e) { ink = -2; }
    return {w: Math.round(r.width), h: Math.round(r.height), ink: ink};
  });
}"""

CURSOR = """() => {
  const d = Bokeh.documents[0];
  const g = (n) => { const m = d.get_model_by_name(n);
                     return m ? Object.fromEntries(Object.entries(m.data).map(
                       ([k, v]) => [k, Array.from(v)])) : null; };
  return {c3: g('src3_cursor'), u: g('srct_u_cursor'), v: g('srct_v_cursor'),
          w: g('srct_w_cursor'), q: g('srcq_muon')};
}"""


def table_rows(d):
    """How many rows the grouped object table will hold for this payload.

    Mirrors object_rows()/unfitted_near() with `bundle only` ON (doc pdvd/53
    sec 8): every PF segment, plus every near cluster that has no segment, is
    not the candidate itself and is IN the bundle.
    """
    n = len((d.get("pf") or {}).get("seg") or [])
    for c in d.get("near_clusters") or []:
        if c.get("segs") or c["id"] == d.get("cluster_id"):
            continue
        if c.get("in_bundle") == 0:
            continue
        n += 1
    return n


def heaviest_manifest(det, path):
    """The arm's biggest item FIRST, then a short walk set for the step check.

    Row 1 is still the heaviest item, so every check that runs on the opening
    item is unchanged.  The extra rows exist for one reason: the object table
    used to keep the PREVIOUS item's rows on screen whenever the next item had
    the same NUMBER of rows (doc pdvd/53 sec 9), and a one-item sheet has no
    `next >` to press.  The walk set is chosen so that at least one adjacent
    pair has an EQUAL row count -- the transition that was broken -- rather than
    hoping the sheet happens to contain one.
    """
    import glob as _g
    best = None
    by_n = {}
    for fn in _g.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")):
        with open(fn) as fh:
            d = json.load(fh)
        n = sum(len((d.get("proj") or {}).get(p, {}).get("ch", [])) for p in "uvw")
        if best is None or n > best[0]:
            best = (n, d)
        by_n.setdefault(table_rows(d), []).append(d)
    if best is None:
        return None, 0
    walk = []
    for k in sorted(by_n, reverse=True):          # a busy table, not an empty one
        if k >= 2 and len(by_n[k]) >= 3:
            walk = sorted(by_n[k], key=lambda x: (x["event"], x["cluster_id"]))[:3]
            break
    rows = [best[1]] + [d for d in walk if d is not best[1]]
    with open(path, "w") as fh:
        fh.write("scan_id\ttranche\tevent\tcluster\tnpts\tmuon_len_cm\tn_near\tn_far\n")
        for i, d in enumerate(rows):
            fh.write("%d\t1\t%s\t%d\t%d\t%.2f\t0\t0\n"
                     % (i + 1, d["event"], d["cluster_id"], d["npts"],
                        d["muon_len_cm"]))
    return path, best[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", default="pdhd", choices=["pdhd", "pdvd"])
    ap.add_argument("--port", type=int, default=5099)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not importable -- skipping the browser gate")
        return 0

    port = free_port(a.port)
    lab = os.path.join("/home/xqian/tmp", "smx3d_selftest_labels_%d" % os.getpid())
    # The heaviest item of the arm, so the paint measurement is the worst case.
    man, ncell = heaviest_manifest(a.det, lab + "_man.tsv")
    log = open("/home/xqian/tmp/smx3d_selftest_%d.log" % port, "w")
    proc = subprocess.Popen(
        [BOKEH, "serve", "--port", str(port),
         "--allow-websocket-origin=localhost:%d" % port,
         os.path.join(HERE, "stm_michel_viewer.py"),
         "--args", "--det", a.det, "--tag", "selftest3d", "--labeldir", lab]
        + (["--manifest", man] if man else []),
        stdout=log, stderr=subprocess.STDOUT)
    url = "http://localhost:%d/stm_michel_viewer" % port
    try:
        # Wait for the socket, then check the process did not exit: `bokeh serve`
        # on a busy port logs one line and exits while the OLD server keeps
        # answering (feedback_bokeh_port_in_use_stale_app).
        for _ in range(120):
            if proc.poll() is not None:
                raise SystemExit("bokeh serve exited rc=%s, see %s"
                                 % (proc.returncode, log.name))
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.5)
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={"width": 1900, "height": 1200})
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(url, wait_until="networkidle", timeout=90000)
            page.wait_for_function("() => window.Bokeh && Bokeh.documents.length > 0",
                                   timeout=60000)
            names = ["muon", "near", "far", "pin"]
            page.wait_for_function(
                "() => { const m = Bokeh.documents[0]"
                ".get_model_by_name('src3_muon'); return m && m.data.u"
                " && m.data.u.length > 0; }", timeout=60000)
            before = page.evaluate(READ % json.dumps(names))
            ck(before["muon"] is not None and len(before["muon"]["u"]) > 0,
               "the muon layer never reached the browser")

            cv = page.locator("canvas").first
            # SCROLL IT IN FIRST.  A mouse.move to a point below the viewport
            # reaches nothing and the drag silently does not happen -- which is
            # how a taller header reads here as "JS_ROTATE is not bound".  The
            # canvas must also be BELOW the fold-free part of the page for that
            # to matter, so this is a real check on the layout as well.
            cv.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            box = cv.bounding_box()
            ck(box is not None, "no canvas bounding box")
            vp = page.viewport_size or {"height": 1200}
            ck(box is not None and box["y"] + box["height"] / 2 < vp["height"],
               "the 3-D canvas centre is below the window even after scrolling "
               "-- the page is too tall to hand-scan")
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            page.mouse.move(cx, cy)
            page.mouse.down()
            for k in range(1, 9):
                page.mouse.move(cx + 15 * k, cy + 5 * k)
                page.wait_for_timeout(20)
            page.mouse.up()
            page.wait_for_timeout(300)
            after = page.evaluate(READ % json.dumps(names))

            ck(not errs, "javascript errors in the page: %s" % errs[:3])
            for n in names:
                b0, a0 = before.get(n), after.get(n)
                if not b0 or not b0["u"]:
                    continue
                ck(len(a0["u"]) == len(b0["u"]),
                   "layer %r changed row count on a drag (%d -> %d)"
                   % (n, len(b0["u"]), len(a0["u"])))
                if n == "pin":
                    # The pin IS the rotation centre since 2026-09-08, so it
                    # projects to (0, 0) at EVERY camera.  "Did it move" is the
                    # wrong question for it, and its answer is the stronger
                    # statement: it cannot move, and that is what makes a drag
                    # keep the stopping point on screen.
                    ck(all(abs(t) < 1e-9 for t in list(a0["u"]) + list(a0["v"])),
                       "the pin does not sit at the rotation centre (u,v = %s)"
                       % ([a0["u"][:1], a0["v"][:1]],))
                    continue
                moved = any(abs(p - q) > 1e-6 for p, q in zip(b0["u"], a0["u"]))
                ck(moved, "layer %r did NOT move on the drag -- it is probably "
                          "missing from the pts list handed to JS_REDRAW" % n)
                # The invariant.  u^2 + v^2 alone is NOT conserved -- a point
                # seen end-on swings to broadside and its projected radius grows,
                # which is the whole point of rotating.  What IS conserved,
                # because right/up/fwd is orthonormal, is
                #     u^2 + v^2 + d^2 == |p - centre|^2
                # so u^2 + v^2 <= |p - centre|^2 at EVERY camera.  A sign error
                # or a non-orthonormal basis in the JS breaks that bound; a
                # "did the pixels change" test would sail past it.
                cam = after.get("_cam") or before.get("_cam")
                ck(cam is not None, "the camera source never reached the browser")
                bad = 0
                if cam:
                    st = max(1, len(b0["u"]) // 200)
                    for i in range(0, len(b0["u"]), st):
                        R2 = ((b0["x"][i] - cam["cx"]) ** 2
                              + (b0["y"][i] - cam["cy"]) ** 2
                              + (b0["z"][i] - cam["cz"]) ** 2)
                        for src in (b0, a0):
                            if src["u"][i] ** 2 + src["v"][i] ** 2 > R2 * 1.000001 + 1e-6:
                                bad += 1
                ck(bad == 0, "layer %r: %d sampled points project OUTSIDE their own "
                             "distance from the camera centre -- the JS basis is not "
                             "orthonormal" % (n, bad))
            # ---- the drag survives a server repaint (owner 2026-09-08) ----
            # The gate the in-process test cannot write, and the one that would
            # have caught the snap-back: with no browser there is no second copy
            # of the camera for the server's to disagree with.
            drag_cam = (after.get("_cam") or {})
            ck(abs(drag_cam.get("az", 0.0)
                   - (before.get("_cam") or {}).get("az", 0.0)) > 1e-6,
               "the drag did not change the camera azimuth at all")
            page.evaluate(
                "() => { const f = Bokeh.documents[0].get_model_by_name('f3d');"
                " f.x_range.start = -25; f.x_range.end = 25;"
                " f.y_range.start = -25; f.y_range.end = 25; }")
            page.wait_for_timeout(600)
            pre = page.evaluate(READ % json.dumps(["muon"]))
            page.get_by_role("button", name="STM, no Michel").first.click()
            page.wait_for_timeout(2000)
            post = page.evaluate(READ % json.dumps(["muon"]))
            rng = page.evaluate(
                "() => { const f = Bokeh.documents[0].get_model_by_name('f3d');"
                " return [f.x_range.start, f.x_range.end]; }")
            pm, qm = pre.get("muon"), post.get("muon")
            ck(pm and qm and len(pm["u"]) == len(qm["u"]),
               "the muon layer changed row count on a label click")
            if pm and qm and len(pm["u"]) == len(qm["u"]):
                worst = max([abs(p - q) for p, q in zip(pm["u"], qm["u"])] or [0.0])
                ck(worst < 1e-6,
                   "a label click re-projected the muon layer by up to %.3f cm -- "
                   "the server's stale camera reached the screen" % worst)
            ck(abs((post.get("_cam") or {}).get("az", -9)
                   - drag_cam.get("az", 0.0)) < 1e-9,
               "a label click reset the camera azimuth the scanner dragged to")
            ck(abs(rng[0] + 25.0) < 1e-6 and abs(rng[1] - 25.0) < 1e-6,
               "a label click threw away the 3-D zoom (%s)" % (rng,))
            ck(not errs, "javascript errors after the repaint checks: %s" % errs[:3])
            print("     the drag survives a label click: az %.4f kept, zoom kept"
                  % drag_cam.get("az", 0.0))

            # ---- the rotation-centre tap, in the browser --------------------
            # The in-process gate calls snap_2d/snap_3d as functions, so it
            # proves the logic and NOT that a tap reaches it: the Tap handler
            # shares the gesture with JS_ROTATE's PanStart/Pan/PanEnd, and the
            # toggle that routes the tap has to have crossed the websocket
            # first.  Both hops are only testable here.
            def _cam():
                return page.evaluate(
                    "() => { const c = Bokeh.documents[0]"
                    ".get_model_by_name('cam3');"
                    " return [c.data.cx[0], c.data.cy[0], c.data.cz[0]]; }")

            def _pin3():
                return page.evaluate(
                    "() => { const m = Bokeh.documents[0]"
                    ".get_model_by_name('src3_pin');"
                    " return [Array.from(m.data.x), Array.from(m.data.u),"
                    " Array.from(m.data.v)]; }")

            c_before, pin_before = _cam(), _pin3()
            ck(abs(pin_before[1][0]) < 1e-9 and abs(pin_before[2][0]) < 1e-9,
               "the pin is not at the origin of the view before the centre tap")
            page.get_by_role(
                "button", name="tap sets the 3-D rotation centre").first.click()
            page.wait_for_timeout(800)
            box2 = cv.bounding_box()
            page.mouse.click(box2["x"] + box2["width"] * 0.62,
                             box2["y"] + box2["height"] * 0.42)
            page.wait_for_timeout(1800)
            c_tap, pin_tap = _cam(), _pin3()
            moved_c = max(abs(a - b) for a, b in zip(c_before, c_tap))
            ck(moved_c > 1e-6,
               "a tap with the centre toggle on did not move the rotation "
               "centre -- the Tap handler never reached snap_3d")
            ck(abs(pin_tap[0][0] - pin_before[0][0]) < 1e-9,
               "a centre tap moved the stopping-point pin as well")
            ck(abs(pin_tap[1][0]) > 1e-9 or abs(pin_tap[2][0]) > 1e-9,
               "the pin still projects to the origin after the centre moved")
            # ... and it is EXACTLY one of the points on screen.  The tap snaps
            # to the nearest candidate IN PROJECTION, and the candidates are a
            # near-1-D locus (the track and the thin cloud around it), so a
            # click off the track lands back near it -- the distance moved is
            # therefore not the assertion.  Membership is.
            on_screen = page.evaluate("""(c) => {
              const d = Bokeh.documents[0];
              for (const n of ['src3_muon', 'src3_near', 'src3_outb']) {
                const s = d.get_model_by_name(n);
                if (!s) continue;
                for (let i = 0; i < s.data.x.length; i++)
                  if (Math.abs(s.data.x[i] - c[0]) < 1e-9 &&
                      Math.abs(s.data.y[i] - c[1]) < 1e-9 &&
                      Math.abs(s.data.z[i] - c[2]) < 1e-9) return true;
              }
              return false; }""", c_tap)
            ck(on_screen,
               "the new rotation centre is not one of the points on screen")
            page.get_by_role("button", name="centre on the stop").first.click()
            page.wait_for_timeout(1800)
            c_back, pin_back = _cam(), _pin3()
            ck(max(abs(a - b) for a, b in zip(c_before, c_back)) < 1e-9,
               "'centre on the stop' did not restore the stopping point")
            ck(abs(pin_back[1][0]) < 1e-9 and abs(pin_back[2][0]) < 1e-9,
               "the pin is not back at the origin of the view")
            page.get_by_role(
                "button", name="tap sets the 3-D rotation centre").first.click()
            page.wait_for_timeout(500)
            ck(not errs, "javascript errors after the centre-tap checks: %s"
               % errs[:3])
            print("     centre tap moved the rotation centre by %.1f cm (the pin "
                  "now projects at u %.1f v %.1f) and left the pin alone"
                  % (moved_c, pin_tap[1][0], pin_tap[2][0]))

            # ---- the 2-D measurement tab --------------------------------
            # The TAB, not the words.  get_by_text matched the header prose
            # first -- harmless while that prose was visible, a 30 s timeout the
            # moment it moved inside a collapsed <details>.  Bokeh 3 tab headers
            # carry .bk-tab, and Playwright's CSS engine pierces open shadow
            # roots (trap 1 applies to querySelectorAll, not to locators).
            tab = page.locator(".bk-tab").filter(
                has_text="2-D measurement").first
            if tab.count() == 0:
                tab = page.get_by_text("2-D measurement", exact=True).last
            ck(tab.count() > 0, "no '2-D measurement' tab in the page")
            # Identify the measurement canvases by SIZE: those figures are the
            # only ones 250 px tall (projections and dQ/dx are 330, the 3-D view
            # 760).  A plain "nine inked canvases exist" would pass with the tab
            # blank, because Bokeh paints a hidden tab's children anyway.
            def _meas():
                cs = [c for c in page.evaluate(INK)
                      if 285 <= c["h"] <= 315 and c["w"] > 200 and c["ink"] > 50]
                return len(cs), sum(c["ink"] for c in cs)

            def _meas_inked():
                return _meas()[0]
            t0 = time.time()
            tab.click()
            page.wait_for_timeout(1500)
            paint = time.time() - t0
            n_after, ink_after = _meas()
            ck(n_after >= 9,
               "only %d measurement-sized canvases carry ink -- the nine panels "
               "did not draw" % n_after)
            # ... and the causal control: empty the cell sources and the same
            # canvases must go quiet.  Without this, "there is ink" could be the
            # axes and the title (feedback_guard_needs_causal_negative_control).
            page.evaluate(
                "() => { for (const p of ['u','v','w']) {"
                " const m = Bokeh.documents[0].get_model_by_name('srcm_' + p);"
                " const d = {}; for (const k in m.data) d[k] = [];"
                " m.data = d; } }")
            page.wait_for_timeout(1200)
            n_empty, ink_empty = _meas()
            # the AMOUNT of ink, not the number of canvases: axes, titles, the
            # dead bands and the trajectory all survive an empty cell source, so
            # every panel stays non-blank and only the total can move.
            #
            # The bar is a FIXED number of pixels, not a fraction, and it is set
            # by what actually discriminates.  At whole-cluster zoom a 677 cm
            # muon's cells are a one-pixel-wide diagonal in a 430 x 300 panel, so
            # they are only a few per cent of the inked pixels -- but when they
            # are genuinely not drawn the drop is EXACTLY ZERO, which is how the
            # sub-pixel `rect` bug was caught (30146 -> 30146).  Measured with
            # the fix: 700-800 pixels on both detectors.
            ck(ink_after - ink_empty >= 150,
               "emptying the cell sources moved only %d pixels on the measurement "
               "panels (%d -> %d) -- the cells are not being drawn"
               % (ink_after - ink_empty, ink_after, ink_empty))
            print("     measurement tab: %d cells over 3 planes, drawn 3x, "
                  "first paint %.2f s, %d panels, %d cell pixels "
                  "(ink %d -> %d when emptied)"
                  % (ncell, paint, n_after, ink_after - ink_empty,
                     ink_after, ink_empty))
            page.reload(wait_until="networkidle", timeout=90000)
            page.wait_for_function("() => window.Bokeh && Bokeh.documents.length > 0",
                                   timeout=60000)
            page.wait_for_function(
                "() => { const m = Bokeh.documents[0]"
                ".get_model_by_name('srcq_muon'); return m && m.data.a"
                " && m.data.a.length > 0; }", timeout=60000)
            ck(not errs, "javascript errors after switching tab: %s" % errs[:3])

            # ---- the dQ/dx click link, over the real websocket --------------
            got = page.evaluate(CURSOR)
            ck(got["q"] is not None and len(got["q"]["a"]) > 0,
               "the dQ/dx muon source never reached the browser")
            if got["q"]:
                k = len(got["q"]["a"]) // 2
                page.evaluate(
                    "(k) => { const m = Bokeh.documents[0]"
                    ".get_model_by_name('srcq_muon');"
                    " m.selected.indices = [k]; }", k)
                page.wait_for_timeout(1200)
                got = page.evaluate(CURSOR)
                ck(got["c3"] is not None and len(got["c3"]["x"]) == 1,
                   "clicking a dQ/dx point did not put a cursor in the 3-D layer")
                for pl in ("u", "v", "w"):
                    ck(got[pl] is not None and len(got[pl]["w"]) == 1,
                       "clicking a dQ/dx point did not put a cursor in the %s "
                       "measurement panel" % pl.upper())
                if got["c3"] and len(got["c3"]["x"]) == 1:
                    src = page.evaluate(
                        "(k) => { const m = Bokeh.documents[0]"
                        ".get_model_by_name('srcq_muon');"
                        " return {x: m.data.x[k], y: m.data.y[k], z: m.data.z[k],"
                        "         pu: m.data.pu[k], pt: m.data.pt[k]}; }", k)
                    ck(abs(src["x"] - got["c3"]["x"][0]) < 1e-6
                       and abs(src["z"] - got["c3"]["z"][0]) < 1e-6,
                       "the 3-D cursor is not on the point that was selected")
                    ck(got["u"] and abs(src["pu"] - got["u"]["w"][0]) < 1e-6
                       and abs(src["pt"] - got["u"]["t"][0]) < 1e-6,
                       "the U measurement cursor is not on the selected point's "
                       "own wire and slice")
                page.evaluate(
                    "() => { const m = Bokeh.documents[0]"
                    ".get_model_by_name('srcq_muon');"
                    " m.selected.indices = []; }")
                page.wait_for_timeout(800)
                got = page.evaluate(CURSOR)
                ck(got["c3"] is not None and len(got["c3"]["x"]) == 0,
                   "deselecting in the browser did not clear the cursor")
            ck(not errs, "javascript errors after the click link: %s" % errs[:3])

            # ---- the particle flow, over the real websocket ------------------
            def _rows(name):
                return page.evaluate(
                    "(n) => { const m = Bokeh.documents[0].get_model_by_name(n);"
                    " return m ? (m.data.x || m.data.w || []).length : -1; }", name)
            ck(_rows("src3_pfseg") == 0,
               "the PF topology is drawn before the toggle is pressed")
            # press the real widget, not the model: this is the binding under test.
            # get_by_role("button"), NOT get_by_text: the instructions Div now
            # contains the phrase "show particle flow" too, and a text locator
            # matched that paragraph and clicked nothing.
            page.get_by_role("button", name="show particle flow").first.click()
            page.wait_for_timeout(1500)
            npf = _rows("src3_pfseg")
            ck(npf > 0, "the 'show particle flow' toggle drew nothing (%d rows)" % npf)
            ck(_rows("src3_pfvtx") > 0, "no PF vertices reached the browser")
            # doc pdvd/53: the flat Select is gone; the picker is the grouped
            # object table.  Driving it means SELECTING A ROW in the real
            # DataTable's source, which is what a click in the browser does --
            # setting a model property the server never sees would prove nothing
            # (feedback_bokeh_client_session_false_negative).
            keys = page.evaluate(
                "() => { const m = Bokeh.documents[0].get_model_by_name('seg_table');"
                " return m ? m.source.data.key : null; }")
            ck(keys is not None and len(keys) > 0,
               "no grouped object table in the page")
            groups = page.evaluate(
                "() => { const m = Bokeh.documents[0].get_model_by_name('seg_table');"
                " return m ? m.source.data.group : null; }") or []
            ck(len(set(groups)) >= 1, "the object table has no group column")
            if keys and len(keys) > 1:
                page.evaluate(
                    "() => { const m = Bokeh.documents[0].get_model_by_name('seg_table');"
                    " m.source.selected.indices = [1]; }")
                page.wait_for_timeout(1500)
                nsel = _rows("src3_pfsel")
                ck(nsel > 0, "picking a row in the object table highlighted nothing")
                ck(_rows("srct_w_pfsel") >= 0,
                   "the PF highlight never reached the measurement panels")
                # and the group buttons are really there to move it with
                for lab in ("\u2192 muon", "\u2192 Michel", "\u2192 gamma",
                            "\u2192 unassigned"):
                    ck(page.get_by_role("button", name=lab).count() > 0,
                       "no %r button in the page" % lab)
            ck(not errs, "javascript errors after the PF checks: %s" % errs[:3])

            # ---- the matched Q-L bundle (doc pdhd/13 sec 4) -----------------
            # ON by default, so out-of-bundle charge must start hidden; pressing
            # the real widget must PAINT it.  A data-only check cannot see a
            # layer that was never given a renderer.
            ck(_rows("src3_outb") == 0,
               "out-of-bundle charge is drawn while `bundle only` is ON")
            n_in_before = _rows("src3_near") + _rows("src3_far")
            page.get_by_role("button", name="bundle only").first.click()
            page.wait_for_timeout(1500)
            n_out = _rows("src3_outb")
            ck(n_out > 0,
               "turning `bundle only` off drew no out-of-bundle charge (%d rows)" % n_out)
            ck(_rows("src3_near") + _rows("src3_far") == n_in_before,
               "the in-bundle layers changed when `bundle only` was toggled")
            page.get_by_role("button", name="bundle only").first.click()
            page.wait_for_timeout(1500)
            ck(_rows("src3_outb") == 0,
               "`bundle only` did not hide the other bundles again")
            ck(not errs, "javascript errors after the bundle checks: %s" % errs[:3])
            print("     bundle control: %d out-of-bundle points paint and unpaint" % n_out)

            # ---- the mu -> e flow panel (doc pdhd/14) ------------------------
            # PAINTED ON LOAD since 2026-09-08 -- the REVEAL toggle is gone.
            # Checked in the browser and not only in the payload because a Div
            # whose text is set before its model reaches the page renders EMPTY
            # with no error (feedback_bokeh3_silent_js_traps).
            # The MODEL text proves the update crossed the websocket; the DOM
            # text proves it painted.  Both, because a Div whose text is set
            # before its model reaches the page renders empty with no error.
            def _model_text(name):
                return page.evaluate(
                    "(n) => { const m = Bokeh.documents[0].get_model_by_name(n);"
                    " return m ? m.text : null; }", name)

            # page.inner_text("body") does NOT see a Bokeh 3 widget: they render
            # inside open shadow roots, which inner_text skips and Playwright
            # LOCATORS pierce.  Reading the body gave "did not paint" on text
            # that was plainly on screen.
            def _painted(txt):
                return page.get_by_text(txt, exact=False).count()

            FLOWMARK = "every field is a T_stm_michel branch"
            st = _model_text("status_div") or ""
            ck("chain muon KE" in st or "no muon energy in this arm" in st,
               "the status line carries no muon KE statement")
            ck(_painted("chain points over") > 0, "the status line did not paint")
            ck(not page.get_by_role("button",
                                    name="REVEAL the reconstruction").count(),
               "a REVEAL button is still on the page")

            after_m = _model_text("flow_div") or ""
            ck(after_m, "flow_div never reached the browser")
            ck("hidden" not in after_m.lower(),
               "the flow panel still says it is hidden")
            n_rev = _painted(FLOWMARK)
            ck(n_rev > 0, "the flow panel did not paint on load")
            ck("MeV" in after_m, "no energy reached the flow panel")
            ck(_painted("MeV") > 0, "no energy painted")
            ck("pdg 13" in after_m, "the flow panel names no mother particle")
            # doc pdhd/15: the Michel is ONE object.  Whatever the item, the
            # panel must state the link with the parent vertex, and when there
            # IS a daughter it must break the energy into the object's parts --
            # the whole point of the round is that the pieces are counted.
            has_dau = "pdg 11" in after_m
            # tag-free fragments: the panel renders "<b>attached</b> at the
            # shared stop vertex" / "<b>bridged</b> to the same stop vertex"
            ck(("at the shared stop vertex" in after_m)
               or ("to the same stop vertex" in after_m)
               or ("charge only" in after_m)
               or ("no daughter" in after_m),
               "the flow panel states no mu -> e link at all")
            if has_dau:
                ck("piece" in after_m, "the daughter is not described as an object of pieces")
                ck("core alone" in after_m,
                   "the flow panel does not separate the object energy from its core")
                ck("unfitted charge" in after_m,
                   "the flow panel does not show the charge term for unfitted pieces")
                ck("pre-doc-15 arm" not in after_m,
                   "the served arm predates doc pdhd/15: michel_ke_core is absent")
                ck(_painted("core alone") > 0, "the energy breakdown did not paint")
            else:
                ck("nothing at the stop" in after_m,
                   "an item with no daughter does not say so")
            # the pre-doc-15 wording must be gone: mc.json DOES carry a parentage
            # for a bridged Michel (through a pseudo-gamma carrier), so the old
            # "no parentage is persisted" line was wrong (doc pdhd/15 sec 2).
            ck("no parentage is persisted" not in after_m,
               "the flow panel still claims a bridged Michel has no persisted parentage")
            ck(not errs, "javascript errors after the flow checks: %s" % errs[:3])
            # ---- the copy box and the saved-labels table (owner 2026-09-08) --
            key = page.evaluate(
                "() => { const m = Bokeh.documents[0]"
                ".get_model_by_name('copy_key'); return m ? m.value : null; }")
            ck(key and "/" in key, "the copy box carries no event/cluster key")
            # the MODEL value proves the server filled it; the DOM value proves
            # it painted -- and Bokeh 3 puts the <input> inside a shadow root, so
            # a flat querySelectorAll finds nothing (trap 1)
            vals = page.evaluate("""() => {
              const out = [];
              const walk = (root) => {
                for (const el of root.querySelectorAll('input')) out.push(el.value);
                for (const el of root.querySelectorAll('*'))
                  if (el.shadowRoot) walk(el.shadowRoot);
              };
              walk(document); return out; }""")
            ck(key in vals, "the copy box's key reached no <input> on the page")
            rows = page.evaluate(
                "() => { const m = Bokeh.documents[0]"
                ".get_model_by_name('saved_src');"
                " return m ? Array.from(m.data.item) : null; }")
            ck(rows is not None, "the saved-labels table never reached the browser")
            ck(rows and key in rows,
               "the item just labelled is not in the saved-labels table")
            ck(_painted("what is in the scan") > 0,
               "the saved-labels heading did not paint")
            head = _model_text("saved_head") or ""
            # the SAVED branch specifically: "not saved" contains "saved", so a
            # substring test on the short word passes on the unsaved branch too
            # and proves nothing (it would keep passing through a regression)
            ck("is <b>saved</b> as" in head,
               "the saved-labels heading does not report this item as saved: %r"
               % head[-120:])
            ck(not errs, "javascript errors after the table checks: %s" % errs[:3])

            print("     mu -> e flow panel: painted on load "
                  "(%d MeV figures on the page, daughter=%s)"
                  % (_painted("MeV"), has_dau))
            print("     copy box %s, saved table %d row(s)" % (key, len(rows or [])))

            # ---- the object table repaints when the ITEM changes ------------
            # doc pdvd/53 sec 9, owner 2026-09-08: `next >` / `< prev` left the
            # PREVIOUS item's rows on screen whenever the new item happened to
            # have the same NUMBER of rows -- SlickGrid repaints only rows it has
            # invalidated, and nothing is invalidated when the count is equal.
            # The server's ColumnDataSource was already correct, which is why
            # every in-process test passed through the whole regression: only a
            # check that reads the RENDERED DOM can see this.  The grid lives in
            # a shadow root (feedback_bokeh3_silent_js_traps trap 1), so the read
            # walks the roots.
            READ_TBL = r"""() => {
              const out = [];
              const walk = (root) => {
                for (const el of root.querySelectorAll('*')) {
                  if (el.classList && el.classList.contains('slick-cell'))
                    out.push((el.textContent || '').trim());
                  if (el.shadowRoot) walk(el.shadowRoot);
                }
              };
              walk(document);
              const m = Bokeh.documents[0].get_model_by_name('seg_table');
              return {dom: out, objs: m ? Array.from(m.source.data.obj) : []};
            }"""
            walk = []
            n_same = 0
            prev_objs = None
            for btn in [None] + ["next >"] * 3 + ["< prev"] * 2:
                if btn:
                    if page.get_by_role("button", name=btn).count() == 0:
                        break
                    page.get_by_role("button", name=btn).first.click()
                    page.wait_for_timeout(1800)
                t = page.evaluate(READ_TBL)
                # Cell by cell: a row's text runs the columns together
                # ("muonS7700321112..."), so an object name is a token only when
                # it is read from its own cell.
                shown = {c for c in t["dom"] if re.match(r"^[SC]\d+$", c)}
                want = set(t["objs"])
                # THE regression signal: an object on screen that this item's
                # source does not hold is a row left behind by the previous item.
                ck(not (shown - want),
                   "after %r the table still paints %r -- rows left over from "
                   "another item" % (btn or "load", sorted(shown - want)[:4]))
                ck(shown, "after %r the object table painted nothing" % (btn or "load"))
                if prev_objs is not None and len(prev_objs) == len(t["objs"]):
                    n_same += 1
                prev_objs = list(t["objs"])
                walk.append((btn or "load", shown, want))
            # SlickGrid VIRTUALISES: it paints only the rows that fit, so a
            # 24-row source legitimately paints ~22.  The capacity is measured
            # from this run rather than guessed, and then every step must paint
            # its whole source up to that capacity -- which is what makes the
            # check see a table that painted a stale subset.
            cap = max((len(sh) for _, sh, _ in walk), default=0)
            for btn, sh, wa in walk:
                ck(len(sh) == min(len(wa), cap),
                   "after %r the table paints %d of the source's %d object(s) "
                   "(the grid fits %d) -- missing %r"
                   % (btn, len(sh), len(wa), cap, sorted(wa - sh)[:4]))
            n_step = len(walk)
            # ... and the check is only worth anything if the walk actually hit
            # the broken transition
            ck(n_same > 0,
               "the walk never hit two items with the same row count -- this "
               "check cannot see the doc pdvd/53 sec 9 regression on this sheet")
            ck(not errs, "javascript errors after the table walk: %s" % errs[:3])
            print("     object table: %d step(s), %d same-row-count transition(s),"
                  " every rendered row matches the source" % (n_step, n_same))
            b.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        if not a.keep:
            import shutil
            shutil.rmtree(lab, ignore_errors=True)
            for x in (lab + "_man.tsv",):
                if os.path.exists(x):
                    os.remove(x)
    print("\n%d browser checks passed, %d failed" % (NPASS[0], len(FAILS)))
    for f in FAILS:
        print("  FAIL  %s" % f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
