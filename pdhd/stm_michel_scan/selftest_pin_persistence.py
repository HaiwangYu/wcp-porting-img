#!/usr/bin/env python3
"""doc pdhd/12 -- the pin and the PF tags really reach the file, and come back.

Every check here names a way the scanner's own hand-placed data used to be lost.
Run the same file against the pre-2026-09-08 viewer and checks 1, 3, 4 and 5
FAIL while `save_now` does not exist at all -- that negative control is what
makes this a test of the fix rather than a description of the code.

Run:  ./selftest_pin_persistence.py [--det pdvd]

It writes ONLY into fresh temp labeldirs under /home/xqian/tmp.  Check 10 copies
the live smx1 labels.json into one of those; the original is never opened for
writing.
"""
import json, os, runpy, shutil, sys, tempfile

DET = "pdvd"
if "--det" in sys.argv:
    DET = sys.argv[sys.argv.index("--det") + 1]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FAILS = []
NP = [0]

def ck(cond, what):
    if cond:
        NP[0] += 1
    else:
        FAILS.append(what)
        print("  FAIL  %s" % what)

def load(det, labeldir):
    argv = ["stm_michel_viewer.py", "--det", det, "--tag", "pintest",
            "--labeldir", labeldir]
    old = sys.argv
    sys.argv = argv
    try:
        return runpy.run_path(os.path.join(HERE, os.environ.get("SM_APP", "stm_michel_viewer.py")))
    finally:
        sys.argv = old

def disk(labeldir):
    p = os.path.join(labeldir, "labels.json")
    if not os.path.isfile(p):
        return {}
    with open(p) as fh:
        return json.load(fh)["labels"]

LD = tempfile.mkdtemp(prefix="pintest-", dir="/home/xqian/tmp")
try:
    G = load(DET, LD)
    state, LABELS = G["state"], G["LABELS"]
    ITEMS = G["ITEMS"]
    key = G["item_key"](G["current"]())
    pay = G["payload"](G["current"]())
    X, Y, Z, Q, RR = G["muon_arrays"](pay)
    print("item %s, %d chain points" % (key, X.size))

    # a point that is NOT the fit end
    j_end = int(RR.argmin())
    step = max(5, X.size // 8)
    j_new = int((j_end + step) % X.size)
    ck(j_new != j_end, "the test needs a point away from the fit end")

    # 1. a pin placed with no label row yet is held, not written
    G["set_pin_index"](j_new)
    ck(key not in disk(LD), "1. a pin with no label row must not invent a row")
    ck("NOT yet on disk" in G["save_div"].text, "1. the app must SAY it is unsaved")

    # 2. the label click writes it
    G["set_label"]("STM_ONLY")
    r = disk(LD)[key]["pin"]
    ck(r["placed"] is True and r["source"] == "pin", "2. label click stores a placed pin")
    ck(abs(r["x"] - float(X[j_new])) < 0.02, "2. stored x is the pinned point")
    moved1 = r["moved_cm"]
    ck(moved1 > 0.0, "2. moved_cm is nonzero for a moved pin")

    # 3. THE BUG THE OWNER HIT: move the pin after labelling, no second label click
    j_third = int((j_end + 2 * step) % X.size)
    G["set_pin_index"](j_third)
    r = disk(LD)[key]["pin"]
    ck(abs(r["x"] - float(X[j_third])) < 0.02,
       "3. moving the pin AFTER the label writes through to the file")

    # 4. leave the item and come back -- the pin must still be there
    other = 1 if state["idx"] == 0 else 0
    G["go"](other)
    ck(state["pin_i"] is None, "4. a fresh item starts on its own fit end")
    G["go"](0)
    ck(state["pin_i"] == j_third, "4. returning to the item RESTORES the pin index")
    px, py, pz, prr, psrc = G["pin_point"](G["payload"](G["current"]()))
    ck(psrc == "pin", "4. the restored pin round-trips as source='pin'")
    ck(abs(px - float(X[j_third])) < 1e-6, "4. restored at the same point")

    # 5. re-labelling must not downgrade it
    G["set_label"]("STM_MICHEL", ) if False else None
    G["set_label"]("THRU")
    r = disk(LD)[key]["pin"]
    ck(r["placed"] is True and abs(r["x"] - float(X[j_third])) < 0.02,
       "5. a RE-LABEL keeps the hand-placed pin instead of resetting it")

    # 6. unset pin is still an explicit way back to the fit end
    G["clear_pin"]()
    r = disk(LD)[key]["pin"]
    ck(r["placed"] is False, "6. `unset pin` really un-pins, and persists that")

    # 7. PF tags: pick whatever row the table adopted and move it
    G["set_pin_index"](j_new)          # re-place, we still want a pin on the row
    k0 = state.get("pf_key")
    ck(k0 is not None, "7. a row is adopted in the object table by default")
    if k0 is not None:
        G["set_pf_tag"]("gamma")
        d = disk(LD)[key]
        ck(d["pf_segments"].get(str(k0)) == "gamma",
           "7. a PF tag on a labelled item writes through immediately")
        ck(d["pf_tagged"] == 1, "7. pf_tagged tracks it")
        # and it survives a round trip
        G["go"](other); G["go"](0)
        ck(state["pf_tag"].get(str(k0)) == "gamma", "7. the tag is restored on return")

    # 8. the Save button
    G["save_now"]()
    d = disk(LD)[key]
    ck(d["pin"]["placed"] is True and d["pf_tagged"] == 1,
       "8. SAVE writes the pin and the tags of the item on screen")
    # the button's whole job is to SAY so: render() rewrites status.text, and
    # Bokeh ships only the last write of a callback
    ck("saved" in G["status"].text and key in G["status"].text,
       "8. ... and the confirmation survives the repaint")

    # 9. ... and refuses on an item with no verdict (the scorer reads rec['label'])
    G["go"](other)
    okey = G["item_key"](G["current"]())
    before = set(disk(LD))
    G["save_now"]()
    ck(okey not in disk(LD) and set(disk(LD)) == before,
       "9. SAVE refuses to write a row with no label")
    ck("needs a verdict" in G["status"].text, "9. ... and says why")
    # ------------------------------------------------------------------
    # 9b. A note and a Michel kind entered BEFORE the label must survive the
    # repaints that every other control triggers.  They used to be re-seeded
    # from the row on every render, so moving the pin wiped both -- and a wiped
    # radio makes the STM + MICHEL button refuse the label as undescribed.
    # ------------------------------------------------------------------
    G["go"](0)
    G["notes"].value = "typed before the label"
    G["michel_kind"].active = 1
    G["set_pin_index"](j_new)
    ck(G["notes"].value == "typed before the label",
       "9b. a typed note survives moving the pin")
    ck(G["michel_kind"].active == 1,
       "9b. a Michel kind picked before the label survives moving the pin")
    G["render"]()
    ck(G["notes"].value == "typed before the label",
       "9b. ... and a plain repaint")
    G["set_label"]("STM_MICHEL")
    d9 = disk(LD)[key]
    ck(d9["notes"] == "typed before the label" and d9["label"] == "STM_MICHEL",
       "9b. the label click stores the note it was typed with")
    ck(d9["michel_kind"] == G["MICHEL_KINDS"][1],
       "9b. ... and the Michel kind, so the label is not refused")
    # switching items still re-seeds both from the row
    G["go"](other); G["go"](0)
    ck(G["notes"].value == "typed before the label",
       "9b. a real item change restores the saved note")

    # ------------------------------------------------------------------
    # 10. THE OWNER'S OWN ROW.  smx1/039349_18/36 is the only one of the 25
    # live labels with placed=True, so it is the one datum whose restore has
    # never been exercised.  Copied into a scratch labeldir -- smx1 is read,
    # never opened for writing.
    # ------------------------------------------------------------------
    SMX1 = ("/home/xqian/toolkit-dev/wcp-porting-img/%s/work/" % DET +
            "stm_michel_labels/smx1/labels.json")
    if os.path.isfile(SMX1):
        LD2 = tempfile.mkdtemp(prefix="pinsmx1-", dir="/home/xqian/tmp")
        try:
            shutil.copy(SMX1, os.path.join(LD2, "labels.json"))
            G2 = load(DET, LD2)
            want = "039349_18/36"
            j = next((i for i, it in enumerate(G2["ITEMS"])
                      if G2["item_key"](it) == want), None)
            ck(j is not None, "10. %s is in the sheet" % want)
            if j is not None:
                G2["go"](j)
                st2 = G2["state"]
                ck(st2["pin_i"] is not None or st2["pin_manual"] is not None,
                   "10. the saved pin is restored on the owner's row")
                ck(not st2.get("pin_warn"),
                   "10. ... without the out-of-tolerance fallback (%s)"
                   % st2.get("pin_warn"))
                px, py, pz, prr, psrc = G2["pin_point"](
                    G2["payload"](G2["current"]()))
                ck(psrc == "pin", "10. restored as source='pin', got %r" % psrc)
                ck(abs(px - 225.17) < 0.02 and abs(py + 275.95) < 0.02
                   and abs(pz - 140.71) < 0.02,
                   "10. restored at (225.17, -275.95, 140.71); got "
                   "(%.2f, %.2f, %.2f)" % (px, py, pz))
                ck(prr is not None and abs(prr - 9.56) < 0.02,
                   "10. residual range comes back at 9.56, got %s" % prr)
                # and a re-label must not throw it away
                G2["set_label"]("STM_MICHEL")
                r2 = disk(LD2)[want]["pin"]
                ck(r2["placed"] is True and abs(r2["moved_cm"] - 8.32) < 0.02,
                   "10. a RE-LABEL of the owner's row keeps moved_cm 8.32, got %s"
                   % r2.get("moved_cm"))
        finally:
            shutil.rmtree(LD2, ignore_errors=True)
    else:
        print("  (smx1 labels.json absent -- check 10 skipped)")
finally:
    shutil.rmtree(LD, ignore_errors=True)

print("\n%d checks passed, %d failed" % (NP[0], len(FAILS)))
for f in FAILS:
    print("  - %s" % f)
sys.exit(1 if FAILS else 0)
