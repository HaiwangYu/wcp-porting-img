#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 -- headless self-test for the scan display.

Run before serving; rc 0 or do not serve.

    ./pr148_scan/selftest_pr148_scan.py

It builds the viewer's document in-process (no browser, no bokeh server) and
asserts five things.  Deliberately NOT via bokeh.client.pull_session, which
hands back a DETACHED document and so passes on an app that is broken in the
browser (feedback_bokeh_client_session_false_negative).

  T1  all 24 sheet rows have a payload, and every payload's start segment
      matches the sheet's `obj`.
  T2  THE BLIND.  Every key of every ColumnDataSource the module builds, and
      every payload key, is on an allow-list.  An absence has to be PROVEN,
      not asserted, so this enumerates what IS there rather than looking for
      what should not be.  The forbidden set -- growth, bragg, stem, f_heavy,
      n_heavy, star, verdict, stratum, nue_score, particle_id,
      particle_score, flag_shower, pdg -- is checked separately by name so a
      rename of the allow-list cannot quietly re-admit one.
  T3  the KEY file exists and is NEVER opened.  open()/json.load are wrapped
      for the whole build and the recorded path set must not contain it.
  T4  the three panels are framed at the FULL detector box, in the right
      axis pair, on a Range1d (not DataRange1d, which would silently refit).
  T5  the label round-trip: set a verdict, read labels.json and
      filled_sheet.tsv back, then restore the tag directory to exactly what
      it was.  Uses a throwaway --scan-tag, never a real one (M13).
"""
import builtins, csv, glob, io, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)
SHEET = os.path.join(SX, "docs", "pr", "pr148-pidscan-manifest.tsv")
KEY = os.path.join(SX, "docs", "pr", "pr148-pidscan.KEY.tsv")

CDS_ALLOWED = {"x", "y", "z", "mip", "xs", "ys"}
PAYLOAD_ALLOWED = {"idx", "sample", "run", "subrun", "event", "shower_id",
                   "obj", "kine_charge_mev", "kine_best_mev", "total_len_cm",
                   "nseg", "mip_used", "start", "far", "far_dist_cm",
                   "members", "others"}
SEG_ALLOWED = {"id", "len", "x", "y", "z", "mip"}
FORBIDDEN = {"growth", "bragg", "stem", "stem_mip", "f_heavy", "n_heavy",
             "len_heavy_cm", "max_mip", "star_n", "star_dist_cm", "stem_run_cm",
             "verdict_a5", "a5_verdict", "stratum", "nue_score", "numu_score",
             "particle_id", "particle_score", "flag_shower", "pdg",
             "n_early", "n_late", "dqdx_trunk", "dqdx_term"}

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def main():
    tag = "selftest-%d" % os.getpid()
    labdir = os.path.join(SX, "work", "pr148_scan_labels", tag)

    opened = []
    real_open = builtins.open

    def spy_open(f, *a, **k):
        try:
            opened.append(os.path.abspath(f))
        except TypeError:
            pass
        return real_open(f, *a, **k)

    print("T1/T2/T3  build the document with open() under a spy")
    builtins.open = spy_open
    try:
        sys.argv = ["pr148_scan_viewer.py", "--scan-tag", tag]
        sys.path.insert(0, HERE)
        import importlib
        V = importlib.import_module("pr148_scan_viewer")
    finally:
        builtins.open = real_open

    rows = V.SHEET
    check(len(rows) == 24, "sheet has 24 rows (got %d)" % len(rows))
    check(len(V.PAYLOAD) == len(rows),
          "every row has a payload (%d/%d)" % (len(V.PAYLOAD), len(rows)))
    bad = [r["event"] for r in rows
           if V.PAYLOAD[int(r["idx"])]["obj"] != int(r["obj"])]
    check(not bad, "payload start segment matches the sheet obj (bad: %s)" % bad)

    # T2 -- enumerate what actually reaches the browser
    srcs = {"mem_src": V.mem_src, "oth_src": V.oth_src, "st_src": V.st_src,
            "fa_src": V.fa_src}
    for k, s in V.lin_src.items():
        srcs["lin_src[%s]" % k] = s
    for k, s in V.box_src.items():
        srcs["box_src[%s]" % k] = s
    seen = set()
    for nm, s in srcs.items():
        seen |= set(s.data.keys())
    check(seen <= CDS_ALLOWED,
          "every CDS column is on the allow-list; saw %s" % sorted(seen))
    check(not (seen & FORBIDDEN), "no forbidden column in any CDS")

    pk, sk = set(), set()
    for p in V.PAYLOAD.values():
        pk |= set(p.keys())
        for s in p["members"] + p["others"]:
            sk |= set(s.keys())
    check(pk <= PAYLOAD_ALLOWED, "payload keys on the allow-list; saw %s"
          % sorted(pk - PAYLOAD_ALLOWED))
    check(sk <= SEG_ALLOWED, "segment keys on the allow-list; saw %s"
          % sorted(sk - SEG_ALLOWED))
    check(not ((pk | sk) & FORBIDDEN), "no forbidden key in any payload")

    txt = " ".join([V.hdr.text, V.info.text, V.LEGEND.text, V.prog.text]
                   + [str(o) for o in V.sel.options])
    leak = sorted(w for w in FORBIDDEN if w in txt)
    check(not leak, "no forbidden word rendered on screen (%s)" % leak)

    # T3 -- the key was never opened
    check(os.path.exists(KEY), "the KEY file exists (%s)" % os.path.basename(KEY))
    check(os.path.abspath(KEY) not in opened,
          "the KEY file was never opened while building the document")
    check(any(p.endswith("pr148-pidscan-manifest.tsv") for p in opened),
          "the manifest WAS opened (the spy is live, so the negative means "
          "something)")

    # T4 -- framing
    print("T4  panel framing")
    from bokeh.models import Range1d
    for f, ax, ay in V.PROJ:
        ok = (isinstance(f.x_range, Range1d) and isinstance(f.y_range, Range1d)
              and (f.x_range.start, f.x_range.end) == V.DET_BOX[ax]
              and (f.y_range.start, f.y_range.end) == V.DET_BOX[ay])
        check(ok, "%s is a Range1d framed at the full %s/%s box" % (f.name, ax, ay))
    check([f.name for f, _, _ in V.PROJ] == ["f_xy", "f_yz", "f_zx"],
          "the three panels are X-Y, Y-Z, Z-X")
    check(V.zoomer.active is False, "Zoom to object defaults OFF")

    # T5 -- label round-trip, then leave no trace
    print("T5  label round-trip")
    V.state["i"] = 0
    V.set_verdict("HADRONIC")()
    with real_open(V.LABJSON) as fh:
        got = json.load(fh)
    check(got.get("0", {}).get("verdict") == "HADRONIC",
          "labels.json carries the verdict")
    with real_open(V.LABSHEET) as fh:
        body = [l for l in fh if not l.startswith("#")]
    fr = list(csv.DictReader(body, delimiter="\t"))
    check(fr[0]["verdict"] == "HADRONIC", "filled_sheet.tsv carries the verdict")
    check(len(fr) == 24 and [r["event"] for r in fr] == [r["event"] for r in rows],
          "filled_sheet.tsv keeps the sheet's rows and order")
    shutil.rmtree(labdir, ignore_errors=True)
    check(not os.path.exists(labdir), "the self-test's label dir is removed")

    print()
    if fails:
        print("FAILED %d check(s)" % len(fails))
        for m in fails:
            print("  - " + m)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
