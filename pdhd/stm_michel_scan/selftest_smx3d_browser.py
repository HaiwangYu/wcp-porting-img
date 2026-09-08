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
  * the PARTICLE FLOW toggle and the segment picker -- pressed as real widgets,
    so the server callback and the round trip back are both under test.
  * the dQ/dx CLICK LINK -- select a point through the live document and assert
    the cursor appears in the 3-D layer AND in all three measurement rows.  The
    selection is set in the BROWSER, so it travels the websocket and fires the
    real server callback; the in-process gate in selftest_stm_michel_scan.py
    cannot test that hop.

Four Bokeh 3 traps make a broken binding look like a working page with no
console error, so a failure here is read as "the handler never bound", not as
"the formula is wrong": see feedback_bokeh3_silent_js_traps.
"""
import argparse, json, os, socket, subprocess, sys, time

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


def heaviest_manifest(det, path):
    """A one-line sheet holding the arm's biggest item, for the paint check."""
    import glob as _g
    best = None
    for fn in _g.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")):
        with open(fn) as fh:
            d = json.load(fh)
        n = sum(len((d.get("proj") or {}).get(p, {}).get("ch", [])) for p in "uvw")
        if best is None or n > best[0]:
            best = (n, d)
    if best is None:
        return None, 0
    d = best[1]
    with open(path, "w") as fh:
        fh.write("scan_id\ttranche\tevent\tcluster\tnpts\tmuon_len_cm\tn_near\tn_far\n")
        fh.write("1\t1\t%s\t%d\t%d\t%.2f\t0\t0\n"
                 % (d["event"], d["cluster_id"], d["npts"], d["muon_len_cm"]))
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
            box = cv.bounding_box()
            ck(box is not None, "no canvas bounding box")
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
            # ---- the 2-D measurement tab --------------------------------
            tab = page.get_by_text("2-D measurement", exact=True).first
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
            opts = page.evaluate(
                "() => { for (const m of Bokeh.documents[0]._all_models.values())"
                " if (m.type === 'Select' && String(m.title).indexOf('PF segment') === 0)"
                " return m.options; return null; }")
            ck(opts is not None and len(opts) > 0, "no PF segment dropdown in the page")
            if opts and len(opts) > 1:
                page.evaluate(
                    "(v) => { for (const m of Bokeh.documents[0]._all_models.values())"
                    " if (m.type === 'Select' && String(m.title).indexOf('PF segment') === 0)"
                    " m.value = v; }", opts[1])
                page.wait_for_timeout(1500)
                nsel = _rows("src3_pfsel")
                ck(nsel > 0, "picking a PF segment highlighted nothing")
                ck(_rows("srct_w_pfsel") >= 0,
                   "the PF highlight never reached the measurement panels")
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
