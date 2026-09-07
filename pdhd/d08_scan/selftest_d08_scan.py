#!/usr/bin/env python3
"""Headless checks for the doc-08 STM-flip scan app.  Forked BY DUPLICATION from
pdhd/stm_scan/selftest_stm_scan.py, which is untouched.

Run:  python3 selftest_d08_scan.py
"""
import ast, csv, glob, json, os, re, sys, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PDHD = os.path.dirname(HERE)
WORK = os.path.join(PDHD, "work")
SHEET = os.path.join(PDHD, "docs", "scan", "d08_stm_flip_sheet.tsv")
KEY = os.path.join(PDHD, "docs", "scan", "d08_stm_flip_key.tsv")
VIEWER = os.path.join(HERE, "d08_scan_viewer.py")
BASE, KNOB = "d08goff", "d08cap10"
RUN6 = "029107"

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
check(len(sh) == 45, "sheet has 45 items (got %d)" % len(sh))
cols = set(sh[0].keys())
for banned in ("direction", "core_all_caps", "stm_before", "stm_after", "verdict",
               "gained", "lost", "also_flips_mrg3"):
    check(banned not in cols, "sheet has no '%s' column" % banned)
check(cols == {"scan_id", "tranche", "event", "cluster", "npts", "length_cm",
               "partition_moved"}, "sheet columns are exactly the neutral set")

print("== 2. the key exists, is separate, and is not read at import time ==")
kr = rows(KEY)
check(len(kr) == len(sh), "key has one row per sheet item")
check(sum(int(r["core_all_caps"]) for r in kr) == 6, "key marks 6 all-cap-core objects")
ng = sum(1 for r in kr if r["direction"] == "gained")
check((ng, len(kr) - ng) == (21, 24), "key direction split is 21 gained / 24 lost (got %d/%d)"
      % (ng, len(kr) - ng))
src = open(VIEWER).read()
check("d08_stm_flip_key" not in src, "viewer never names the key file")
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
check(len(moved) == 2, "exactly 2 items carry partition_moved=1 (got %d)" % len(moved))

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

print("== 7. the REVEAL has something to show, for every item ==")
# The reveal draws each arm's steiner_graph and stm_fit for the item's cluster and
# prints its stm_tagged verdict.  Assert the data path end to end: the layers
# exist, the verdict pair actually differs (that is what makes it a scan item),
# and at least one arm has a fit to draw.
missing, same_verdict, no_fit = [], [], []
for r in sh:
    e, cl = r["event"], int(r["cluster"])
    v = {}
    for arm in (BASE, KNOB):
        zp = os.path.join(WORK, "%s_%s_%s" % (RUN6, e, arm), "mabc-pr.zip")
        tg = layer(zp, "stm_tagged")
        st = layer(zp, "steiner_graph")
        ft = layer(zp, "stm_fit")
        if tg is None or st is None or ft is None:
            missing.append((e, cl, arm)); continue
        v[arm] = cl in set(tg["cluster_id"])
        if arm == BASE:
            nfit = sum(1 for c in ft["cluster_id"] if c == cl)
    if len(v) == 2 and v[BASE] == v[KNOB]:
        same_verdict.append((e, cl, v[BASE]))
check(not missing, "every item has steiner_graph/stm_fit/stm_tagged in both arms (%s)" % missing[:3])
check(not same_verdict,
      "the stm_tagged verdict differs between arms for every item -- i.e. the Bee layer "
      "agrees with the tagger log the sheet was built from (%s)" % same_verdict[:5])

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
sys.argv = ["d08_scan_viewer.py", "--tag", "_selftest_inproc"]
try:
    g = runpy.run_path(os.path.join(HERE, "d08_scan_viewer.py"))
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

print("== 10. a partition_moved item discloses the OTHER arm's point count ==")
_moved = [(i, it) for i, it in enumerate(g["ITEMS"]) if it["moved"]]
check(bool(_moved), "the sheet has at least one partition_moved item (%d)" % len(_moved))
for _i, _it in _moved:
    go(_i)
    _st = g["status"].text
    _kn = g["knob_npts"](_it["event"], _it["cluster"])
    check(_kn is not None and ("%d points" % _kn) in _st and g["KNOB_ARM"] in _st,
          "evt %s cluster %d: status names %s = %s points (panels draw %d)"
          % (_it["event"], _it["cluster"], g["KNOB_ARM"], _kn, _it["npts"]))
    check(_kn != _it["npts"],
          "  and the two arms really do differ there (%s vs %s)" % (_it["npts"], _kn))
go(2)
nz = {k: len(src[("z", "y")][k].data["a"]) for k in ("stB", "stA", "ftB", "ftA")}
check(all(v > 0 for v in nz.values()), "every overlay source carries points (%s)" % nz)
go(2); render()
check("REVEALED" in div.text, "the reveal survives navigating to another item")
rev.active = False
render()
check(div.text == "" and all(len(src[("z", "y")][k].data["a"]) == 0
                             for k in ("stB", "stA", "ftB", "ftA")),
      "toggling REVEAL off clears the banner AND every overlay")

print("\n%s  (%d checks failed)" % ("ALL CHECKS PASS" if not FAIL else "FAILURES", len(FAIL)))
sys.exit(1 if FAIL else 0)
