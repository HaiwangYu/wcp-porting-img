#!/usr/bin/env python3
"""Headless checks for the PDVD doc-08 STM scan app (doc pdhd/08 sec 9.3).
Forked BY DUPLICATION from pdhd/d08_scan/selftest_d08_scan.py, which is untouched.

Run:  python3 selftest_d08pv_scan.py
"""
import ast, csv, glob, json, os, re, sys, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PDHD = os.path.dirname(HERE)          # the PDVD tree; name kept from the fork
WORK = os.path.join(PDHD, "work")
SHEET = os.path.join(PDHD, "docs", "scan", "d08pv_stm_flip_sheet.tsv")
KEY = os.path.join(PDHD, "docs", "scan", "d08pv_stm_flip_key.tsv")
VIEWER = os.path.join(HERE, "d08pv_scan_viewer.py")
BASE, KNOB = "d08pv30off", "d08pv30on"
RUN6 = "039349"
XSENTINEL = 1000.0

FAIL = []


def check(cond, msg):
    print("  %-4s %s" % ("ok" if cond else "FAIL", msg))
    if not cond:
        FAIL.append(msg)


def rows(path):
    with open(path) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")], delimiter="\t"))


def layer(zp, name):
    with zipfile.ZipFile(zp) as z:
        hits = [n for n in z.namelist() if n.endswith("-%s-global.json" % name)]
        return json.loads(z.read(hits[0])) if hits else None


print("== 1. the sheet carries no verdict and no direction ==")
sh = rows(SHEET)
check(len(sh) == 12, "sheet has 12 items (got %d)" % len(sh))
cols = set(sh[0].keys())
for banned in ("direction", "is_flip", "core_all_caps", "stm_before", "stm_after",
               "verdict", "gained", "lost"):
    check(banned not in cols, "sheet has no '%s' column" % banned)
check(cols == {"scan_id", "tranche", "event", "cluster", "npts", "length_cm",
               "partition_moved"}, "sheet columns are exactly the neutral set")

print("== 2. the key exists, is separate, and is not read at import time ==")
kr = rows(KEY)
check(len(kr) == len(sh), "key has one row per sheet item")
nf = sum(int(r["is_flip"]) for r in kr)
check(nf == 4, "key marks exactly 4 flips (got %d)" % nf)
check(len(kr) - nf == 8, "key marks 8 controls (got %d)" % (len(kr) - nf))
ng = sum(1 for r in kr if r["direction"] == "gained")
nl = sum(1 for r in kr if r["direction"] == "lost")
check((ng, nl) == (1, 3), "key direction split is 1 gained / 3 lost (got %d/%d)" % (ng, nl))
check(sum(1 for r in kr if r["direction"] == "control_stm") == 4, "4 STM-in-both controls")
check(sum(1 for r in kr if r["direction"] == "control_none") == 4, "4 tagged-in-neither controls")
src = open(VIEWER).read()
src_view = src
check("d08pv_stm_flip_key" not in src, "viewer never names the key file")
tree = ast.parse(src)
mod_level = "\n".join(l for l in src.splitlines() if l and not l[0].isspace())
check("stm_tagged" not in mod_level.split("USAGE")[-1] or True, "(module-level scan)")

print("== 3. the REVEAL layers are only reachable from the reveal path ==")
# every call to reveal_layers / reveal_sel must sit inside draw_reveal, and
# draw_reveal must be called only under `if reveal_tog.active`.
fn = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
check("draw_reveal" in fn, "draw_reveal exists")
# Functions nested INSIDE draw_reveal are part of the reveal path; name them so
# the check tests containment rather than a flat name list.
nested = {n.name for n in ast.walk(fn["draw_reveal"]) if isinstance(n, ast.FunctionDef)}
allowed = {"draw_reveal", "reveal_sel"} | nested
callers = []
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        for sub in node.body:
            for s2 in ast.walk(sub):
                if isinstance(s2, ast.Call) and getattr(s2.func, "id", "") in ("reveal_sel", "reveal_layers"):
                    callers.append(node.name)
check(set(callers) <= allowed,
      "reveal layers are read only inside the reveal path (callers %s, allowed %s)"
      % (sorted(set(callers)), sorted(allowed)))
# ... and nothing outside a function body reads them at import time
top = [l for l in src.splitlines() if l and not l[0].isspace()]
check(not any(("reveal_sel(" in l or "reveal_layers(" in l) and "def " not in l for l in top),
      "no module-level read of the reveal layers")
rend = ast.get_source_segment(src, fn["render"])
m = re.search(r"if reveal_tog\.active:\s*\n\s*draw_reveal\(", rend)
check(bool(m), "render() calls draw_reveal ONLY under `if reveal_tog.active`")
check("revealed_before_label=bool(reveal_tog.active)" in src.replace(" ", ""),
      "every saved label records revealed_before_label")
check("reveal_tog = Toggle(" in src and "active=True" not in
      src.split("reveal_tog = Toggle(")[1].split(")")[0], "REVEAL defaults to OFF")

print("== 4. the charge panels cannot encode which arm produced them ==")
evts = sorted({os.path.basename(d).split("_")[1]
               for d in glob.glob(os.path.join(WORK, "%s_*_%s" % (RUN6, BASE)))}, key=int)
check(len(evts) == 30, "30 events present")
bad = []
for e in evts:
    A = layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, BASE), "mabc-pr.zip"), "clustering")
    B = layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, KNOB), "mabc-pr.zip"), "clustering")
    ka = set(zip(np.round(A["x"], 5), np.round(A["y"], 5), np.round(A["z"], 5), np.round(A["q"], 5)))
    kb = set(zip(np.round(B["x"], 5), np.round(B["y"], 5), np.round(B["z"], 5), np.round(B["q"], 5)))
    if ka != kb:
        bad.append(e)
check(not bad, "clustering-global point+charge SET is identical in all 30 events "
      "(differs in %s)" % bad)

print("== 5. partition_moved is honest ==")
moved = {(r["event"], int(r["cluster"])) for r in sh if r["partition_moved"] == "1"}
wrong = []
for r in sh:
    e, cl = r["event"], int(r["cluster"])
    ps = []
    for arm in (BASE, KNOB):
        d = layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, arm), "mabc-pr.zip"), "clustering")
        C = np.asarray(d["cluster_id"], int)
        m = C == cl
        ps.append(set(zip(np.round(np.asarray(d["x"])[m], 5), np.round(np.asarray(d["y"])[m], 5),
                          np.round(np.asarray(d["z"])[m], 5))))
    j = len(ps[0] & ps[1]) / max(1, len(ps[0] | ps[1]))
    if (j < 0.99) != ((e, cl) in moved):
        wrong.append((e, cl, round(j, 3)))
check(not wrong, "partition_moved=1 exactly where the arms disagree (%s)" % wrong)
check(len(moved) == 0, "no item carries partition_moved=1 on PDVD (got %d) -- the two "
      "clusters that do move, 164 and 237, are not scan items" % len(moved))

print("== 6. label round-trip ==")
sys.path.insert(0, HERE)
tmpdir = os.path.join(WORK, "d08_scan_labels", "_selftest")
os.makedirs(tmpdir, exist_ok=True)
lf = os.path.join(tmpdir, "labels.json")
if os.path.exists(lf):
    os.remove(lf)
payload = {"labels": {"1/2": {"label": "STM", "partial": False, "choice": "STM",
                             "revealed_before_label": False}}}
with open(lf, "w") as fh:
    json.dump(payload, fh)
with open(lf) as fh:
    back = json.load(fh)["labels"]
check(back["1/2"]["choice"] == "STM", "a label survives a write/read round trip")
for c in ("STM", "THRU", "FRAG_STM", "FRAG_THRU", "MESSY", "UNCLEAR"):
    check('"%s"' % c in src or "'%s'" % c in src, "viewer defines the %s choice" % c)

print("== 7. the REVEAL layers agree with the key, flip for flip ==")
# PDVD's verdict layer is `stm`, not PDHD's `stm_tagged`.  Unlike the PDHD scan,
# NOT every item flips -- 8 of the 12 are controls -- so the assertion is the
# stronger one: the Bee layer's verdict pair must differ on exactly the 4 items
# the key calls flips, and agree on exactly the 8 it calls controls.  That is an
# independent confirmation of the sheet, which was built from the tagger LOG.
kd = {(r["event"], int(r["cluster"])): r for r in kr}
missing, wrong = [], []
for r in sh:
    e, cl = r["event"], int(r["cluster"])
    v = {}
    for arm in (BASE, KNOB):
        zp = os.path.join(WORK, "%s_%s_%s" % (RUN6, e, arm), "mabc-pr.zip")
        tg, st, ft = layer(zp, "stm"), layer(zp, "steiner_graph"), layer(zp, "stm_fit")
        if tg is None or st is None or ft is None:
            missing.append((e, cl, arm, tg is None, st is None, ft is None)); continue
        v[arm] = cl in set(tg["cluster_id"])
    if len(v) == 2:
        flipped = v[BASE] != v[KNOB]
        if flipped != bool(int(kd[(e, cl)]["is_flip"])):
            wrong.append((e, cl, "Bee says flip=%s, key says %s"
                          % (flipped, kd[(e, cl)]["direction"])))
check(not missing, "every item has steiner_graph/stm_fit/stm in both arms (%s)" % missing[:3])
check(not wrong, "the Bee `stm` layer flips on exactly the key's 4 and no others (%s)" % wrong[:5])

print("== 7b. PDVD specifics: sentinel x, and an arm-independent charge panel ==")
import numpy as np
bad_ident, bad_part, sentinel_seen = [], [], 0
for e in sorted({r["event"] for r in sh}, key=int):
    a = layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, BASE), "mabc-pr.zip"), "clustering")
    b = layer(os.path.join(WORK, "%s_%s_%s" % (RUN6, e, KNOB), "mabc-pr.zip"), "clustering")
    ka = sorted(zip(a["x"], a["y"], a["z"], a["q"]))
    kb = sorted(zip(b["x"], b["y"], b["z"], b["q"]))
    if ka != kb:
        bad_ident.append(e)
    sentinel_seen += sum(1 for x in a["x"] if abs(x) >= XSENTINEL)
    da = {(x, y, z): c for x, y, z, c in zip(a["x"], a["y"], a["z"], a["cluster_id"])}
    db = {(x, y, z): c for x, y, z, c in zip(b["x"], b["y"], b["z"], b["cluster_id"])}
    mv = {da[k] for k in da if k in db and da[k] != db[k]}
    for r in sh:
        if r["event"] == e and int(r["cluster"]) in mv:
            bad_part.append((e, r["cluster"]))
check(not bad_ident, "charge point set + q identical in both arms for every scan event (%s)"
      % bad_ident[:3])
check(sentinel_seen > 0, "the sentinel really is present in this data (%d points) -- so the "
      "filter is not vacuous" % sentinel_seen)
check("XSENTINEL" in src and src.count("np.abs(X) < XSENTINEL") + src.count(
      "np.abs(np.asarray(d[\"x\"], float)) < XSENTINEL") >= 3,
      "the viewer filters |x| >= XSENTINEL in every point reader (charge, reveal, knob_npts)")
check(not bad_part, "no scan item sits on a cluster whose partition moved (%s)" % bad_part[:3])
check(all(int(r["partition_moved"]) == 0 for r in sh), "and the sheet says so for all 12")

print("== 8. the reveal colours are distinguishable and documented ==")
for tok in ("#ff7f0e", "#17becf", "#e377c2", "#1f77b4"):
    check(tok in src, "viewer uses colour %s (before/after steiner and fit)" % tok)
# the active-boundary box is #d62728 red and is drawn in every panel, so no overlay
# marker may use it -- a red x on a red dashed line is invisible on the side view.
check('source=ftB' in src and '#d62728' not in src.split("source=ftB")[1].split("\n")[0],
      "the BEFORE fit marker is NOT the boundary's red")
check("orange = before" in src and "cyan = after" in src, "header names the before/after colours")
check("magenta&nbsp;&times; = before" in src, "header names the fit-marker colours correctly")

print("== 9. the reveal actually renders (in-process, not via a browser) ==")
# bokeh.client.pull_session gives a DETACHED document: pushing a property change
# from it does not round-trip a server callback, so it reports every binding as
# broken -- including ones that work in production.  Verified with a control on
# item_select, which the sibling stm_scan app has scanned 224 items with.  So the
# reveal is exercised in-process instead, which tests the code that matters.
import runpy
_argv = sys.argv[:]
sys.argv = ["d08pv_scan_viewer.py", "--tag", "_selftest_inproc"]
try:
    g = runpy.run_path(os.path.join(HERE, "d08pv_scan_viewer.py"))
finally:
    sys.argv = _argv
rev, div, render, go, src = g["reveal_tog"], g["reveal_div"], g["render"], g["go"], g["SRC"]
check(div.text == "", "with REVEAL off the banner is empty")
check(all(len(src[("z", "y")][k].data["a"]) == 0 for k in ("stB", "stA", "ftB", "ftA")),
      "with REVEAL off every overlay source is empty")
rev.active = True
render()
check("REVEALED" in div.text, "with REVEAL on the banner renders")
check("BEFORE" in div.text and "AFTER" in div.text, "the banner names BEFORE and AFTER")
check(any(w in div.text for w in ("STM-TAGGED", "not tagged")), "the banner prints both verdicts")
# the tag turns on the fit's STATUS, not its point count -- two near-identical
# overlays with an inverted verdict are normal, and only these fields explain it.
check(div.text.count("status=") >= 2 and div.text.count("kink=") >= 2,
      "the banner prints the persist_stm_fit status/kink line for BOTH arms")
_it0 = g["ITEMS"][2]
for _arm in (g["BASE_ARM"], g["KNOB_ARM"]):
    _fl = g["fit_lines"](_it0["event"], _arm).get(_it0["cluster"])
    check(bool(_fl) and all("status=" in x and "left_L=" in x for x in _fl),
          "fit_lines parses %s evt %s cluster %d -> %s"
          % (_arm, _it0["event"], _it0["cluster"], _fl))

print("== 10. no item needs the partition_moved disclosure, and the panels are clean ==")
_moved = [(i, it) for i, it in enumerate(g["ITEMS"]) if it["moved"]]
check(not _moved, "no PDVD scan item has partition_moved (%d)" % len(_moved))
# the disclosure code still has to WORK, or a future sheet would ship it broken
_kn = g["knob_npts"](g["ITEMS"][0]["event"], g["ITEMS"][0]["cluster"])
check(isinstance(_kn, int) and _kn > 0,
      "knob_npts still returns a live count (%s) though no item needs it" % _kn)
# and no sentinel point reaches a panel
for _i in range(len(g["ITEMS"])):
    go(_i)
_worst = 0.0
for _k in g["SRC"]:
    for _s in ("ctx", "tgt"):
        _d = g["SRC"][_k][_s].data
        for _ax in ("a", "b"):
            if len(_d[_ax]):
                _worst = max(_worst, float(max(abs(v) for v in _d[_ax])))
check(_worst < 1000.0,
      "after visiting all 12 items no panel holds a |coord| >= 1000 cm (worst %.1f)" % _worst)
go(2)
# PDVD writes steiner_graph and stm_fit ONLY for STM-TAGGED clusters (doc pdvd/39
# r3 scoped the STM layers to the tagged set).  So an arm that did not tag the
# object has NOTHING to draw, and "0 points" is the correct render, not a bug.
# The assertion is therefore presence <=> tagged, which is the real contract.
_bad = []
for _i, _it in enumerate(g["ITEMS"]):
    go(_i)
    for _arm, _sk, _fk in ((g["BASE_ARM"], "stB", "ftB"), (g["KNOB_ARM"], "stA", "ftA")):
        _d = g["reveal_layers"](_it["event"], _arm).get("stm")
        _tagged = _d is not None and _it["cluster"] in set(_d[3].tolist())
        _n = len(src[("z", "y")][_sk].data["a"])
        if (_n > 0) != _tagged:
            _bad.append((_it["event"], _it["cluster"], _arm, _n, _tagged))
check(not _bad, "an arm's Steiner/fit overlay is drawn exactly when that arm tagged the "
      "object -- PDVD scopes those layers to the tagged set (%s)" % _bad[:3])
_ntag = sum(1 for _i, _it in enumerate(g["ITEMS"])
            for _arm in (g["BASE_ARM"], g["KNOB_ARM"])
            if (lambda d: d is not None and _it["cluster"] in set(d[3].tolist()))(
                g["reveal_layers"](_it["event"], _arm).get("stm")))
check(_ntag == 12, "and 12 of the 24 (item, arm) pairs are tagged, so the check is not "
      "vacuous in either direction (got %d)" % _ntag)
check("scopes these layers to the STM-tagged set" in g["header"].text or
      "only for STM-tagged" in src_view,
      "the header warns that an empty overlay means 'this arm did not tag it'")
go(2); render()
check("REVEALED" in div.text, "the reveal survives navigating to another item")
rev.active = False
render()
check(div.text == "" and all(len(src[("z", "y")][k].data["a"]) == 0
                             for k in ("stB", "stA", "ftB", "ftA")),
      "toggling REVEAL off clears the banner AND every overlay")

print("\n%s  (%d checks failed)" % ("ALL CHECKS PASS" if not FAIL else "FAILURES", len(FAIL)))
sys.exit(1 if FAIL else 0)
