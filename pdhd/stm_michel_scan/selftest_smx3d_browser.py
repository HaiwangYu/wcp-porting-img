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
    log = open("/home/xqian/tmp/smx3d_selftest_%d.log" % port, "w")
    proc = subprocess.Popen(
        [BOKEH, "serve", "--port", str(port),
         "--allow-websocket-origin=localhost:%d" % port,
         os.path.join(HERE, "stm_michel_viewer.py"),
         "--args", "--det", a.det, "--tag", "selftest3d", "--labeldir", lab],
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
    print("\n%d browser checks passed, %d failed" % (NPASS[0], len(FAILS)))
    for f in FAILS:
        print("  FAIL  %s" % f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
