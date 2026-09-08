#!/usr/bin/env python3
"""doc pdhd/12 -- headless gate for the STM + Michel hand-scan display.

Run:  ./selftest_stm_michel_scan.py [--det pdhd|pdvd] [--quick]

HOW IT DRIVES THE APP, and why not the obvious way.
  It runs stm_michel_viewer.py IN PROCESS with runpy.run_path, takes the widgets
  and functions out of the returned globals, sets state and calls render()
  directly.  It does NOT use bokeh.client.pull_session: that hands back a
  DETACHED document, a property change pushed from it fires no server callback,
  and it therefore reports working production patterns as broken -- which once
  cost a rewrite of correct code (feedback_bokeh_client_session_false_negative).

  Nothing here writes under work/: the app is started with --labeldir pointing
  into a scratch dir, so a self-test run can never touch a scan record (M13).

WHAT IT ASSERTS, grouped:
  A  the payload's shape, and that the chain's answer IS on screen from the
     first paint -- the blind was removed by the owner on 2026-09-08, so the
     poison test is INVERTED: the verdict key is poisoned with values nothing
     else could produce, and they must appear in the sources and in the panels
     with no toggle pressed.  A1, that the answer still lives under exactly one
     key, is unchanged and is what would let a future round re-blind it.
  B  the audit field: `revealed_before_label` is written True on every label,
     and no REVEAL widget survives anywhere in the app.
  V  the view (owner 2026-09-08): the 3-D rotation centre is the stopping point,
     a tap can move it, and NOTHING except a new item or an explicit reset may
     touch a range -- not a label, not a PF tag, not a pin move, not a bundle
     switch.  Plus the copy box and the saved-labels table.
  C  every label round-trips, including the FRAG rule that a partial label still
     carries the FULL object's verdict.
  D  the pin: unset by default and equal to the fit's own last point, NOT to the
     chain's refined stop; tap-snap reproduced by brute force; the slider, the
     manual x/y/z, and the dQ/dx panel re-anchoring exactly.
  E  the geometry: unit_from_wire re-derived from the production wire file, and
     the wire-vs-geometric confusion matrix over every payload.
  F  the prep's near/far split reproduced by brute force on one item.
  G  the scorer, on synthetic labels with a known answer.
  H  the 2-D measurement panels: the plane split gated causally against the
     fitter's own wire coordinate, the tick -> slice conversion gated against
     the files rather than the config, the residual recomputed independently,
     the dead-band overlay, the reveal gating of the overlays, and the dQ/dx
     click landing on the SAME point in all thirteen views.
"""
import argparse, bz2, glob, json, os, runpy, shutil, sys, tempfile

import numpy as np
import uproot

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smgeom                                                     # noqa: E402
import smkine                                                     # noqa: E402
# doc pdhd/14: the arm name lives in ONE place, prep_stm_michel_scan.DET, so a
# re-run cannot leave the self-test silently checking the previous arm's files.
_prep = runpy.run_path(os.path.join(HERE, "prep_stm_michel_scan.py"),
                       run_name="_selftest_import")
ARM = {d: _prep["DET"][d]["arm"] for d in ("pdhd", "pdvd")}

IMG = os.path.dirname(os.path.dirname(HERE))
# doc pdhd/15: the C++ admission radius (CheckSTM_Michel.cxx default 15 cm; the
# ProtoDUNE bags do not set it) and the Michel endpoint (m_mu^2 + m_e^2)/(2 m_mu).
MICHEL_DOT_RADIUS_CM = 15.0
COMPANION_MAX_LEN_CM = 25.0
MICHEL_ENDPOINT_MEV = 52.8
WIREDIR = "/nfs/data/1/xqian/toolkit-dev/wire-cell-data"
WIRES = {"pdhd": "protodunehd-wires-larsoft-v1.json.bz2",
         "pdvd": "protodunevd-wires-larsoft-v7-uvwfit.json.bz2"}

NPASS = [0]
FAILS = []


def ck(cond, what):
    if cond:
        NPASS[0] += 1
    else:
        FAILS.append(what)
        print("  FAIL  %s" % what)


def load_app(det, labeldir, prepdir=None, manifest=None):
    argv = ["stm_michel_viewer.py", "--det", det, "--tag", "selftest",
            "--labeldir", labeldir]
    if prepdir:
        argv += ["--prepdir", prepdir]
    if manifest:
        argv += ["--manifest", manifest]
    old = sys.argv
    sys.argv = argv
    try:
        return runpy.run_path(os.path.join(HERE, "stm_michel_viewer.py"))
    finally:
        sys.argv = old


# ---------------------------------------------------------------------------
# E -- geometry, against the production wire files
# ---------------------------------------------------------------------------
def wire_blocks(det):
    """{(anode, face): (rank_lo, rank_hi)} for the collection plane, plus base."""
    with bz2.open(os.path.join(WIREDIR, WIRES[det])) as fh:
        st = json.load(fh)["Store"]
    W = [w["Wire"] for w in st["wires"]]
    P = [p["Plane"] for p in st["planes"]]
    F = [f["Face"] for f in st["faces"]]
    A = [a["Anode"] for a in st["anodes"]]
    rows = []
    for a in A:
        for fidx in a["faces"]:
            if fidx < 0:
                continue
            f = F[fidx]
            for pi, pidx in enumerate(f["planes"]):
                rows.append((a["ident"], f["ident"], pi,
                             set(W[wi]["channel"] for wi in P[pidx]["wires"])))
    allch = [set(), set(), set()]
    for a, fid, pi, ch in rows:
        allch[pi] |= ch
    base = [0, len(allch[0]), len(allch[0]) + len(allch[1])]
    rank = {c: i for i, c in enumerate(sorted(allch[2]))}
    blocks = {}
    for a, fid, pi, ch in rows:
        if pi != 2:
            continue
        r = sorted(rank[c] for c in ch)
        blocks[(a, fid)] = (r[0], r[-1], (r[-1] - r[0] + 1) == len(r))
    return blocks, base, len(allch[2])


def test_geometry(det):
    print("[E] geometry, %s" % det)
    blocks, base, nw = wire_blocks(det)
    ck(base[2] == smgeom.CHAN[det]["base_w"],
       "%s collection base %d != smgeom %d" % (det, base[2], smgeom.CHAN[det]["base_w"]))
    ck(nw == smgeom.CHAN[det]["per_unit"] * smgeom.CHAN[det]["nunit"],
       "%s collection channel count %d" % (det, nw))
    ck(all(c for _, _, c in blocks.values()),
       "%s: a per-(anode,face) collection rank block is NOT contiguous" % det)
    # every wire rank in a block must map back to that block's (anode, face)
    bad = 0
    for (a, fid), (lo, hi, _c) in sorted(blocks.items()):
        for r in (lo, (lo + hi) // 2, hi):
            u, cru, face = smgeom.unit_from_wire(det, base[2] + r)
            if u != a or face != fid:
                bad += 1
                print("     rank %d -> unit %s face %s, wire file says %d/%d"
                      % (r, u, face, a, fid))
    ck(bad == 0, "%s: unit_from_wire disagrees with the wire file on %d probes"
       % (det, bad))
    # out of range -> (None, None, None), never a silent clip
    ck(smgeom.unit_from_wire(det, base[2] - 1) == (None, None, None),
       "%s: unit_from_wire did not reject a below-base wire" % det)
    ck(smgeom.unit_from_wire(det, base[2] + nw) == (None, None, None),
       "%s: unit_from_wire did not reject an above-range wire" % det)
    if det == "pdvd":
        ck(sorted({smgeom.unit_from_wire(det, base[2] + r)[1]
                   for r in range(0, nw, 37)}) == list(range(16)),
           "pdvd: the 16 CRUs are not all reachable from pw")


def test_unit_agreement(det, prepdir):
    """Wire label vs geometric label over every chain point of every payload."""
    print("[E] wire-vs-geometric label, %s" % det)
    n = agree = nowire = 0
    conf = {}
    for fn in sorted(glob.glob(os.path.join(prepdir, "smprep-*.json"))):
        with open(fn) as fh:
            d = json.load(fh)
        m = d["muon"]
        for x, y, z, pw in zip(m["x"], m["y"], m["z"], m["pw"]):
            n += 1
            uw = smgeom.unit_from_wire(det, pw)[0]
            ug = smgeom.unit_from_geometry(det, x, y, z)[0]
            if uw is None:
                nowire += 1
                continue
            conf[(uw, ug)] = conf.get((uw, ug), 0) + 1
            agree += (uw == ug)
    tot = n - nowire
    print("     %d chain points, %d with a collection wire, %d agree (%.4f)"
          % (n, tot, agree, agree / max(tot, 1)))
    off = {k: v for k, v in conf.items() if k[0] != k[1]}
    if off:
        print("     off-diagonal: " + "  ".join(
            "wire%d/geom%d=%d" % (a, b, c) for (a, b), c in sorted(off.items())))
    # This is a MEASUREMENT, not a pass/fail: on PDVD the geometric route reads
    # sign(x), which is documented unsafe in the pre-T0 frame.  What must hold is
    # that the wire route always produced a label.
    ck(nowire == 0 or nowire / max(n, 1) < 0.01,
       "%s: %d of %d chain points carry no collection wire" % (det, nowire, n))
    return agree / max(tot, 1)


# ---------------------------------------------------------------------------
# A / B -- the blind
# ---------------------------------------------------------------------------
POISON = -987654.0


def all_source_values(g):
    """Every number on screen -- the measurement panels included.

    A poison test that does not walk the NEW sources passes vacuously, which is
    the failure mode that makes a blind test worthless.
    """
    out = []
    for s in (list(g["SRC2"].values()) + list(g["SRC3"].values())
              + list(g["SRCQ"].values()) + list(g["SRCM"].values())
              + list(g["SRCD"].values()) + list(g["SRCT"].values())):
        for col in s.data.values():
            try:
                out.extend(float(t) for t in col)
            except (TypeError, ValueError):
                pass
    return out


def test_answer_on_screen(det, tmp):
    print("[A] the chain's answer is on screen, %s" % det)
    prep = os.path.join(tmp, "prep-" + det)
    os.makedirs(prep, exist_ok=True)
    src = os.path.join(HERE, "prep-" + det)
    # one item that HAS a Michel, so the poison has somewhere to live
    pick = None
    for fn in sorted(glob.glob(os.path.join(src, "smprep-*.json"))):
        with open(fn) as fh:
            d = json.load(fh)
        if d["verdict"].get("michel_found"):
            pick = (fn, d)
            break
    ck(pick is not None, "%s: no payload with michel_found=1 to poison" % det)
    if pick is None:
        return
    fn, d = pick
    # A1 -- the answer is under exactly one key
    # Exact field names, not substrings: `image_stop_r` and `image_near_r` are
    # drawing parameters of the geometric context selection, not chain output,
    # and a substring match on "stop" flagged one of them.
    ANSWER = {"is_stm", "in_fv", "bragg_valid", "reject_bits", "reject_names",
              "michel_found", "michel_conn_type", "michel_len", "michel_mip",
              "michel_kink_deg", "michel_ke_best", "michel_ke_dqdx",
              "michel_ke_range", "n_michel_segs", "n_dots", "dots_ke_dqdx",
              "n_delta", "delta_len", "contrast", "contrast_expected",
              "plateau_med", "tail_med", "role", "michel", "dots", "delta",
              "entry_x", "stop_x", "tagger_stop_x", "tagger_fit"}
    top = set(d.keys()) - {"verdict"}
    leak = sorted(top & ANSWER)
    ck(not leak, "%s: chain verdict fields at payload top level: %s" % (det, leak))
    # A2 -- poison the verdict and prove ALL of it reaches the screen unprompted
    v = d["verdict"]
    for nm in ("michel", "dots", "delta"):
        g0 = v.get(nm) or {}
        k = len(g0.get("x") or []) or 5
        v[nm] = dict(x=[POISON] * k, y=[POISON] * k, z=[POISON] * k,
                     q=[POISON] * k, seg=[0] * k,
                     # the wire columns the measurement panel draws from: a
                     # poison that omitted them would leave that panel untested
                     pu=[POISON] * k, pv=[POISON] * k, pw=[POISON] * k,
                     pt=[POISON] * k)
    for key in ("stop_x", "stop_y", "stop_z", "entry_x", "entry_y", "entry_z",
                "tagger_stop_x", "tagger_stop_y", "tagger_stop_z"):
        v[key] = POISON
    v["tagger_fit"] = [dict(pass_=0, x=[POISON], y=[POISON], z=[POISON],
                            rr=[POISON], dqdx=[POISON])]
    # the PF answer.  pdg and the shower flag never reach a ColumnDataSource --
    # they are rendered as TEXT -- so this one is checked in the Div as well.
    v["pf_type"] = {k: dict(pdg=int(POISON), shower=1, frac_shower=POISON)
                    for k in (v.get("pf_type") or {})} or {"0": dict(
                        pdg=int(POISON), shower=1, frac_shower=POISON)}
    with open(os.path.join(prep, os.path.basename(fn)), "w") as fh:
        json.dump(d, fh)
    refp = os.path.join(src, "dqdx_ref_%s.json" % det)
    if os.path.exists(refp):
        shutil.copy(refp, prep)
    man = os.path.join(tmp, "one_%s.tsv" % det)
    with open(man, "w") as fh:
        fh.write("scan_id\ttranche\tevent\tcluster\tnpts\tmuon_len_cm\tn_near\tn_far\n")
        fh.write("1\t1\t%s\t%d\t%d\t%.2f\t0\t0\n"
                 % (d["event"], d["cluster_id"], d["npts"], d["muon_len_cm"]))

    g = load_app(det, os.path.join(tmp, "lab_" + det), prep, man)
    vals = all_source_values(g)
    # INVERTED on 2026-09-08.  The same poison, the same sweep of every source
    # on the page -- what changed is the sign of the assertion, which is the
    # honest way to record that the blind is gone rather than deleting the test.
    ck(POISON in vals,
       "%s: the verdict did NOT reach a data source on the first paint" % det)
    ck(g["REND2"][("z", "y", "michel")].visible,
       "%s: the michel renderer is hidden with no toggle to un-hide it" % det)
    ck(str(int(POISON)) in g["seg_div"].text,
       "%s: the PF segment panel does not show the chain's pdg" % det)
    ck("hidden" not in g["reveal_div"].text and "answer" in g["reveal_div"].text,
       "%s: the verdict banner still says the answer is hidden" % det)

    # B -- the audit field, and that the toggle is really gone
    print("[B] the audit field, %s" % det)
    ck(not [k for k in g if "reveal_tog" in k],
       "%s: a REVEAL toggle survives in the app globals" % det)
    ck(not any(getattr(w, "label", "").startswith("REVEAL")
               for w in g["curdoc"]().select({"type": g["Toggle"]})),
       "%s: a widget labelled REVEAL is still in the document" % det)
    g["michel_kind"].active = g["MICHEL_KINDS"].index("attached")
    g["set_label"]("STM_MICHEL")
    lab = json.load(open(g["LABEL_FILE"]))["labels"]
    k = list(lab)[0]
    ck(lab[k]["revealed_before_label"] is True,
       "%s: revealed_before_label not recorded as True" % det)
    g["set_label"]("STM_ONLY")
    lab = json.load(open(g["LABEL_FILE"]))["labels"]
    ck(lab[k]["revealed_before_label"] is True,
       "%s: revealed_before_label is not True on every label now" % det)
    return g


# ---------------------------------------------------------------------------
# V -- the view: the rotation centre, and what may touch a range
#      (owner 2026-09-08, doc pdhd/12 sec 13)
# ---------------------------------------------------------------------------
def test_view(det, tmp):
    """Ranges are the one thing this display can throw away in total silence.

    The scanner zooms into the Bragg end, clicks a label, and the object is a
    dot again with nothing on screen saying why -- which is exactly what the
    owner reported.  So every assertion here is about a RANGE, and the negative
    ones (a label, a tag, a bundle switch must NOT reframe) matter more than the
    positive ones.
    """
    print("[V] the 3-D centre and the view that stays put, %s" % det)
    g = load_app(det, os.path.join(tmp, "view_" + det))
    f3d, cam, st, D3 = g["f3d"], g["cam_src"], g["state"], g["D3"]
    pay = g["payload"](g["current"]())
    ck(pay is not None, "%s: no payload for the view test" % det)
    if pay is None:
        return

    # V1 -- the rotation centre IS the stopping point
    px, py, pz, _rr, psrc = g["pin_point"](pay)
    ck(psrc == "fit-end", "%s: the pin does not start at the fit's own end" % det)
    ck(abs(cam.data["cx"][0] - px) < 1e-9 and abs(cam.data["cy"][0] - py) < 1e-9
       and abs(cam.data["cz"][0] - pz) < 1e-9,
       "%s: the 3-D rotation centre is not the stopping point" % det)

    # V2 -- and the framing guarantee survives the move to an OFF-CENTRE origin.
    # smx3d rests on |(u, v)| <= |p - centre| <= R for every camera; a centre at
    # one end of the track is the case that would break it if the radius were
    # still the bounding sphere's.
    X, Y, Z, _q, _r = g["muon_arrays"](pay)
    R = cam.data["R"][0]
    worst = 0.0
    for az, el in [(0.0, 0.0), (1.0, 0.4), (-2.3, -1.1), (3.0, 1.4)]:
        for u, v, _d in D3.project(list(zip(X, Y, Z)), az, el, (px, py, pz)):
            worst = max(worst, (u * u + v * v) ** 0.5)
    ck(worst <= R + 1e-6,
       "%s: a chain point projects outside the frame radius (%.3f > %.3f)"
       % (det, worst, R))

    # V3 -- a tap moves the centre to a point that is actually drawn, and does
    # NOT move the pin
    CX, CY, CZ = g["centre_candidates"](pay)
    ck(CX.size > len(X), "%s: the centre candidates are only the chain" % det)
    j = int(CX.size // 3)
    g["centre_tog"].active = True
    g["snap_2d"]("z", "y", float(CZ[j]), float(CY[j]))
    ck(st["centre"] is not None, "%s: a centre tap set no centre" % det)
    if st["centre"] is not None:
        hit = [k for k in range(CX.size)
               if abs(CX[k] - st["centre"][0]) < 1e-9
               and abs(CY[k] - st["centre"][1]) < 1e-9
               and abs(CZ[k] - st["centre"][2]) < 1e-9]
        ck(bool(hit), "%s: the tapped centre is not one of the drawn points" % det)
        ck(abs(cam.data["cx"][0] - st["centre"][0]) < 1e-9,
           "%s: the tapped centre never reached the camera" % det)
    ck(st["pin_i"] is None, "%s: a centre tap moved the stopping-point pin" % det)
    g["clear_centre"]()
    ck(st["centre"] is None and abs(cam.data["cx"][0] - px) < 1e-9,
       "%s: 'centre on the stop' did not restore the stopping point" % det)
    g["centre_tog"].active = False
    g["snap_2d"]("z", "y", float(Z[5]), float(Y[5]))
    ck(st["pin_i"] is not None,
       "%s: with the centre toggle off a tap no longer moves the pin" % det)
    g["clear_pin"]()

    # V4 -- nothing but a new item or an explicit reset may touch a range
    ZOOM = (-13.0, 13.0)
    P2 = g["FIG2"][("z", "y")]

    def _set_zoom():
        f3d.x_range.start, f3d.x_range.end = ZOOM
        f3d.y_range.start, f3d.y_range.end = ZOOM
        P2.x_range.start, P2.x_range.end = 11.0, 41.0
        g["_meas_y"].start, g["_meas_y"].end = 101.0, 201.0

    def _kept(what, three_d=True):
        ok = ((P2.x_range.start, P2.x_range.end) == (11.0, 41.0)
              and (g["_meas_y"].start, g["_meas_y"].end) == (101.0, 201.0))
        if three_d:
            ok = ok and (f3d.x_range.start, f3d.x_range.end) == ZOOM
        ck(ok, "%s: %s reframed the view" % (det, what))

    _set_zoom()
    seq0 = cam.data["seq"][0]
    g["set_label"]("STM_ONLY")
    _kept("a label click")
    # ... and the camera was still PUSHED, which is what re-projects the browser
    # copy at the angle the scanner dragged to.  Skipping that push is how a
    # "do not reframe" change turns into a snap-back to the server's stale angle.
    ck(cam.data["seq"][0] > seq0,
       "%s: render() did not push the camera, so a drag would snap back" % det)

    idx0 = st["idx"]
    ck(idx0 == 0, "%s: the view test did not start on item 0" % det)
    ck(st["idx"] == idx0, "%s: a label click still advanced to the next item" % det)

    _set_zoom()
    g["bundle_tog"].active = not g["bundle_tog"].active
    _kept("the bundle toggle")
    _set_zoom()
    g["pf_tog"].active = True
    _kept("the particle-flow toggle")
    segs = g["pf_segments"](pay)
    if segs:
        _set_zoom()
        st["pf_seg"] = segs[0]["id"]
        g["set_pf_tag"]("muon")
        _kept("a PF segment tag")
    # a PIN move is allowed to re-centre the 3-D view -- the centre IS the pin --
    # but only by recentring: the zoom LEVEL and the 2-D panels must survive
    _set_zoom()
    g["set_pin_index"](int(len(X) // 2))
    _kept("a pin move", three_d=False)
    ck(abs((f3d.x_range.end - f3d.x_range.start) - (ZOOM[1] - ZOOM[0])) < 1e-6,
       "%s: a pin move changed the 3-D zoom level" % det)
    ck(abs(f3d.x_range.start + f3d.x_range.end) < 1e-6,
       "%s: a pin move did not put the new centre in the middle of the view" % det)

    # V5 -- and the two things that SHOULD reframe, do
    _set_zoom()
    g["render"](reframe=True)
    ck((f3d.x_range.start, f3d.x_range.end) != ZOOM,
       "%s: 'reset the view' did not reframe the 3-D panel" % det)
    _set_zoom()
    g["zoom_tog"].active = not g["zoom_tog"].active
    ck((P2.x_range.start, P2.x_range.end) != (11.0, 41.0),
       "%s: the zoom toggle did not reframe the projections" % det)
    if len(g["ITEMS"]) > 1:
        _set_zoom()
        g["go"](1)
        ck((f3d.x_range.start, f3d.x_range.end) != ZOOM,
           "%s: a new item did not reframe the 3-D panel" % det)
        ck(st["centre"] is None, "%s: a new item kept the previous centre" % det)
        g["go"](0)

    # V6 -- the copy box: the item key, and paste-to-navigate
    ck(g["copy_key"].value == g["item_key"](g["current"]()),
       "%s: the copy box does not carry this item's key" % det)
    if len(g["ITEMS"]) > 4:
        k = g["item_key"](g["ITEMS"][4])
        g["copy_key"].value = k
        ck(st["idx"] == 4, "%s: pasting an item key did not navigate to it" % det)
        ck(g["copy_key"].value == k, "%s: the copy box lost the key it landed on" % det)
        g["go"](0)

    # V7 -- the saved table is the FILE, row for row
    lab = json.load(open(g["LABEL_FILE"]))["labels"]
    tab = g["saved_src"].data
    ck(len(tab["item"]) == len(lab),
       "%s: the saved table has %d rows for %d on disk"
       % (det, len(tab["item"]), len(lab)))
    for i2, k2 in enumerate(tab["item"]):
        ck(k2 in lab, "%s: the table shows %s, which is not in the file" % (det, k2))
        if k2 in lab:
            ck(tab["label"][i2] == (lab[k2].get("choice") or ""),
               "%s: the table's label for %s is not the file's" % (det, k2))
    here = g["item_key"](g["current"]())
    ck(tab["now"].count("\u25b6") == (1 if here in lab else 0),
       "%s: the current item is not marked exactly once in the table" % det)

    # V8 -- and it says what is NOT saved.  PF tags on an item with no label row
    # live in memory only, and that is precisely the case the owner could not see.
    nxt = next((i for i, it in enumerate(g["ITEMS"])
                if g["item_key"](it) not in lab), None)
    if nxt is not None:
        g["go"](nxt)
        ck("not saved" in g["saved_head"].text,
           "%s: an unlabelled item is not called out as unsaved" % det)
        segs = g["pf_segments"](g["payload"](g["current"]()))
        if segs:
            st["pf_seg"] = segs[0]["id"]
            g["set_pf_tag"]("muon")
            ck("memory only" in g["saved_head"].text,
               "%s: a PF tag held off disk is not reported as pending" % det)
            ck(g["item_key"](g["current"]()) not in
               json.load(open(g["LABEL_FILE"]))["labels"],
               "%s: a PF tag wrote a label row that does not exist" % det)


# ---------------------------------------------------------------------------
# C -- the label alphabet
# ---------------------------------------------------------------------------
def test_labels(det, tmp):
    print("[C] the label alphabet, %s" % det)
    g = load_app(det, os.path.join(tmp, "lab2_" + det))
    # A Michel verdict with michel_kind unset must be REFUSED, not defaulted:
    # the radio only resets from a saved label, so a silent default would put
    # michel_kind="none" on a row labelled STM_MICHEL.
    g["michel_kind"].active = 0
    before = len(json.load(open(g["LABEL_FILE"]))["labels"]) if \
        os.path.exists(g["LABEL_FILE"]) else 0
    g["set_label"]("STM_MICHEL")
    after = len(json.load(open(g["LABEL_FILE"]))["labels"]) if \
        os.path.exists(g["LABEL_FILE"]) else 0
    ck(after == before and "say what the Michel is" in g["status"].text,
       "%s: STM_MICHEL was accepted with michel_kind unset" % det)
    g["set_label"]("FRAG_STM_MICHEL")
    ck("say what the Michel is" in g["status"].text,
       "%s: FRAG_STM_MICHEL was accepted with michel_kind unset" % det)
    # render() resets the radio to "not set" on every item, which is correct --
    # it is a per-object question -- so it has to be answered per label here too.
    ATT = g["MICHEL_KINDS"].index("attached")
    for i, (choice, spec) in enumerate(g["CHOICES"].items()):
        # A label no longer advances (owner 2026-09-08, item 6), so the walk is
        # explicit.  It used to be implicit in set_label's own jump, which is
        # exactly the coupling that made a mis-click a navigation event too.
        g["go"](i % len(g["ITEMS"]))
        g["michel_kind"].active = ATT
        g["set_label"](choice)
        rec = [r for r in json.load(open(g["LABEL_FILE"]))["labels"].values()
               if r["choice"] == choice]
        ck(len(rec) == 1, "%s: %s did not round-trip" % (det, choice))
        if rec:
            ck(rec[0]["label"] == spec["label"] and rec[0]["partial"] == spec["partial"],
               "%s: %s stored label/partial %s/%s" % (det, choice,
                                                      rec[0]["label"], rec[0]["partial"]))
    # the FRAG rule: a partial label carries the FULL object's verdict
    L = json.load(open(g["LABEL_FILE"]))["labels"]
    frag = [r for r in L.values() if r["partial"]]
    ck(frag and all(r["label"] in ("STM_MICHEL", "STM_ONLY", "THRU") for r in frag),
       "%s: a FRAG label does not carry an object-level verdict" % det)
    ck(all("michel_kind" in r and "pin" in r for r in L.values()),
       "%s: a label is missing michel_kind or pin" % det)
    ck(all(r["michel_kind"] != g["MICHEL_UNSET"] or r["label"] != "STM_MICHEL"
           for r in L.values()),
       "%s: a STM_MICHEL row was stored with michel_kind unset" % det)
    # an unknown label must not be storable through the same path
    ck("SOMETHING_ELSE" not in g["CHOICES"], "%s: CHOICES is not a closed set" % det)
    return g


# ---------------------------------------------------------------------------
# D -- the pin
# ---------------------------------------------------------------------------
def test_pin(det, tmp):
    print("[D] the pin, %s" % det)
    g = load_app(det, os.path.join(tmp, "lab3_" + det))
    # find an item whose payload has a Michel, so the panel has both sides
    for i, it in enumerate(g["ITEMS"]):
        p = g["payload"](it)
        if p and p["verdict"].get("michel_found"):
            g["go"](i)
            break
    pay = g["payload"](g["current"]())
    ck(pay is not None, "%s: no payload for the pin test" % det)
    if pay is None:
        return g
    X = np.asarray(pay["muon"]["x"], float)
    Y = np.asarray(pay["muon"]["y"], float)
    Z = np.asarray(pay["muon"]["z"], float)
    RR = np.asarray(pay["muon"]["rr"], float)

    # D1 -- unset by default, and equal to the FIT'S OWN END, not the chain's stop
    ck(g["state"]["pin_i"] is None and g["state"]["pin_manual"] is None,
       "%s: the pin does not start unset" % det)
    px, py, pz, prr, psrc = g["pin_point"](pay)
    ck(psrc == "fit-end", "%s: the default origin is %r, not the fit end" % (det, psrc))
    j = int(np.argmin(RR))
    ck(abs(px - X[j]) < 1e-6 and abs(py - Y[j]) < 1e-6 and abs(pz - Z[j]) < 1e-6,
       "%s: the default origin is not the min-rr chain point" % det)
    ck("NO PIN PLACED YET" in g["badge"].text,
       "%s: the badge does not say the pin is unplaced" % det)
    # The measured limit the app documents rather than an assertion that it is
    # blind: `stop_*` is the drawn chain's own last point on almost every item,
    # so the pin measures AGREEMENT, not an independent placement.  This prints
    # the population number the doc quotes and fails only if it drifts.
    nd = 0
    for it in g["ITEMS"]:
        p = g["payload"](it)
        if not p:
            continue
        r = np.asarray(p["muon"]["rr"], float)
        if not r.size:
            continue
        k = int(np.argmin(r))
        v = p["verdict"]
        d = ((p["muon"]["x"][k] - v["stop_x"]) ** 2
             + (p["muon"]["y"][k] - v["stop_y"]) ** 2
             + (p["muon"]["z"][k] - v["stop_z"]) ** 2) ** 0.5
        nd += (d < 0.01)
    frac = nd / max(len(g["ITEMS"]), 1)
    print("     chain end == chain stop_* on %.4f of items (doc quotes 0.977)" % frac)
    ck(frac > 0.90, "%s: chain-end/stop_* identity fell to %.4f -- the doc's "
                    "honest-limit paragraph needs re-measuring" % (det, frac))

    # D2 -- tap-snap, against a brute-force nearest point in the panel's own axes
    for (ha, va) in (("z", "y"), ("z", "x"), ("x", "y")):
        ax = dict(x=X, y=Y, z=Z)
        t = len(X) // 3
        a0, b0 = float(ax[ha][t]) + 0.4, float(ax[va][t]) - 0.3
        g["snap_2d"](ha, va, a0, b0)
        want = int(np.argmin((ax[ha] - a0) ** 2 + (ax[va] - b0) ** 2))
        ck(g["state"]["pin_i"] == want,
           "%s: snap_2d(%s,%s) picked %s, brute force says %d"
           % (det, ha, va, g["state"]["pin_i"], want))
    px, py, pz, prr, psrc = g["pin_point"](pay)
    ck(psrc == "pin", "%s: origin is %r after a tap" % (det, psrc))
    ck("YOUR PIN" in g["fq"].title.text,
       "%s: the dQ/dx panel title does not name the pin" % det)

    # D3 -- the panel re-anchors EXACTLY: every muon x-value shifts by delta rr
    g["set_pin_index"](int(np.argmin(RR)))
    a0 = np.asarray(g["SRCQ"]["muon"].data["a"], float)
    i2 = int(np.argmin(np.abs(RR - (RR.min() + 10.0))))
    g["set_pin_index"](i2)
    a1 = np.asarray(g["SRCQ"]["muon"].data["a"], float)
    shift = RR[int(np.argmin(RR))] - RR[i2]
    ck(a0.size == a1.size and np.allclose(a1 - a0, shift, atol=1e-6),
       "%s: the dQ/dx panel did not re-anchor by exactly the pin's rr shift" % det)

    # D4 -- every Michel/dot point sits on the NEGATIVE side of the panel
    for nm in ("michel", "dots"):
        a = np.asarray(g["SRCQ"][nm].data["a"], float)
        ck(a.size == 0 or (a <= 0).all(),
           "%s: a %s point landed on the positive (muon) side of the panel" % (det, nm))

    # D5 -- the rr slider and the manual pin
    g["rr_slider"].value = float(RR.min() + 5.0)
    g["on_rr"](None, None, g["rr_slider"].value)
    ck(g["state"]["pin_i"] == int(np.argmin(np.abs(RR - (RR.min() + 5.0)))),
       "%s: the rr slider did not move the pin to the nearest chain point" % det)
    g["manual_x"].value, g["manual_y"].value, g["manual_z"].value = "1.0", "2.0", "3.0"
    g["on_manual"]()
    ck(g["pin_point"](pay)[:3] == (1.0, 2.0, 3.0),
       "%s: the manual pin did not take" % det)
    ck(g["off_fit_chk"].active == [0],
       "%s: a manual pin did not set the off-the-fit flag" % det)
    ck(g["pin_unit"](pay, 1.0, 2.0, 3.0, "manual")[3] == "geometric",
       "%s: a manual pin claimed a wire label it cannot have" % det)
    # a disagreement must be FLAGGED, not silently resolved either way.  Forge
    # one by pointing every chain point's wire at the writer's default.
    saved = list(pay["muon"]["pw"])
    pay["muon"]["pw"] = [float(smgeom.SENTINEL_PW[det])] * len(saved)
    how = g["pin_unit"](pay, X[0], Y[0], Z[0], "pin")[3]
    ck("DISPUTED" in how and "DEFAULT wire" in how,
       "%s: a wire/geometry disagreement was not flagged (%r)" % (det, how))
    pay["muon"]["pw"] = saved
    g["manual_x"].value = "not a number"
    g["on_manual"]()
    ck("must all be numbers" in g["status"].text,
       "%s: a non-numeric manual pin was not refused" % det)
    g["clear_pin"]()
    ck(g["state"]["pin_i"] is None and g["state"]["pin_manual"] is None,
       "%s: unset pin did not clear" % det)

    # D6 -- the pin is saved with its readout unit
    g["set_pin_index"](i2)
    g["michel_kind"].active = g["MICHEL_KINDS"].index("attached")
    g["set_label"]("STM_MICHEL")
    rec = json.load(open(g["LABEL_FILE"]))["labels"]
    r = [x for x in rec.values() if x["choice"] == "STM_MICHEL"][0]
    ck(r["pin"] and r["pin"]["placed"] is True and r["pin"]["unit"] is not None,
       "%s: the saved pin has no unit" % det)
    ck(r["pin"].get("moved_cm") is not None and r["pin"]["moved_cm"] > 0.0,
       "%s: the saved pin does not record how far it moved from the chain end" % det)
    ck(r["pin"]["unit_source"] == "wire",
       "%s: a pin on the fit was labelled %r, not from the wire"
       % (det, r["pin"]["unit_source"]))
    # navigating away must reset the pin, or the next item inherits it
    g["go"](g["state"]["idx"] + 1)
    ck(g["state"]["pin_i"] is None, "%s: the pin survived navigation" % det)
    return g


# ---------------------------------------------------------------------------
# F -- the prep's geometric near/far split, by brute force
# ---------------------------------------------------------------------------
def test_image_split(det):
    print("[F] the image near/far split, %s" % det)
    import zipfile
    fns = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    ck(bool(fns), "%s: no payloads to check" % det)
    if not fns:
        return
    with open(fns[0]) as fh:
        d = json.load(fh)
    arm = ARM[det]
    zp = os.path.join(IMG, det, "work", "%s_%s" % (d["event"], arm), "mabc-pr.zip")
    ck(os.path.exists(zp), "%s: %s missing" % (det, zp))
    if not os.path.exists(zp):
        return
    with zipfile.ZipFile(zp) as z:
        nm = [n for n in z.namelist() if n.endswith("clustering-global.json")][0]
        g = json.loads(z.read(nm))
    ck([nm] == d["image_src"],
       "%s: the payload read %s, not clustering-global alone" % (det, d["image_src"]))
    X = np.asarray(g["x"], float); Y = np.asarray(g["y"], float); Z = np.asarray(g["z"], float)
    M = np.c_[np.asarray(d["muon"]["x"], float), np.asarray(d["muon"]["y"], float),
              np.asarray(d["muon"]["z"], float)]
    R, RS = d["image_near_r"], d["image_stop_r"]
    rr = np.asarray(d["muon"]["rr"], float)
    stop = M[int(np.argmin(rr))]
    # brute force, no KD-tree: the thing the prep's accelerator has to reproduce
    near = np.zeros(X.size, bool)
    P = np.c_[X, Y, Z]
    for k in range(0, M.shape[0], 1):
        near |= (((P - M[k]) ** 2).sum(axis=1) < R * R)
    near |= (((P - stop) ** 2).sum(axis=1) < RS * RS)
    ck(int(near.sum()) == len(d["image_near"]["x"]),
       "%s: brute force says %d near points, the payload has %d"
       % (det, int(near.sum()), len(d["image_near"]["x"])))
    ck(len(d["image_far"]["x"]) <= 8000,
       "%s: the far set was not thinned (%d)" % (det, len(d["image_far"]["x"])))
    ck(int((~near).sum()) >= len(d["image_far"]["x"]),
       "%s: the far set is bigger than the complement of the near set" % det)


def test_reference(det):
    print("[*] the dQ/dx reference, %s" % det)
    p = os.path.join(HERE, "prep-" + det, "dqdx_ref_%s.json" % det)
    ck(os.path.exists(p), "%s: no dqdx_ref" % det)
    if not os.path.exists(p):
        return
    with open(p) as fh:
        r = json.load(fh)
    ck(r["grid"] == dict(start=0.0, step=0.25, n=401), "%s: unexpected ref grid" % det)
    ck(r["units"] == "e/cm", "%s: ref units %r" % (det, r["units"]))
    # the muon plateau doc pdvd/50 published, so a chain change that moved the
    # reference cannot slip past unnoticed
    want = {"pdhd": 54609.2, "pdvd": 53965.5}[det]
    ck(abs(r["muon"][-1] - want) < 1.0,
       "%s: muon plateau %.1f, doc 50 says %.1f" % (det, r["muon"][-1], want))


def test_scorer(det, tmp):
    """Drive score_stm_michel_scan.py on SYNTHETIC labels.

    Without this the scorer is the one deliverable with no coverage, and a
    traceback in it is discovered after somebody has spent three hours scanning.
    Every branch is exercised: all five labels, both FRAG variants, revealed and
    hidden rows, placed and unplaced pins, and the unknown-label hard error.
    """
    print("[G] the scorer, %s" % det)
    import csv as _csv, random, subprocess
    keyf = os.path.join(IMG, det, "docs", "scan",
                        "%s_stm_michel_scan_key.tsv" % det)
    ck(os.path.exists(keyf), "%s: no key at %s" % (det, keyf))
    if not os.path.exists(keyf):
        return
    rows = list(_csv.DictReader([l for l in open(keyf) if not l.startswith("#")],
                                delimiter="\t"))
    t1 = [r for r in rows if r["tranche"] == "1"]
    rnd = random.Random(7)
    CH = {"STM_MICHEL": ("STM_MICHEL", False, "attached"),
          "STM_ONLY": ("STM_ONLY", False, "none"),
          "THRU": ("THRU", False, "none"),
          "FRAG_STM_MICHEL": ("STM_MICHEL", True, "detached dots"),
          "FRAG_STM_ONLY": ("STM_ONLY", True, "none"),
          "FRAG_THRU": ("THRU", True, "none"),
          "MESSY": ("MESSY", False, "none"),
          "UNCLEAR": ("UNCLEAR", False, "none")}
    order = list(CH)
    lab = {}
    for i, r in enumerate(t1):
        c = order[i % len(order)]            # every branch, deterministically
        L, part, mk = CH[c]
        placed = (i % 2 == 0)
        lab["%s/%s" % (r["event"], r["cluster"])] = dict(
            label=L, partial=part, choice=c, michel_kind=mk,
            pin=dict(x=1.0, y=2.0, z=3.0, rr=0.0, placed=placed, source="pin",
                     moved_cm=round(rnd.uniform(0, 6), 2) if placed else None,
                     off_fit=False, unit=0, cru=0, face=0, unit_source="wire"),
            revealed_before_label=(i % 13 == 0), notes="",
            scan_id=int(r["scan_id"]), tranche=1, event=r["event"],
            cluster=int(r["cluster"]), npts=int(r["npts"]),
            muon_len_cm=float(r["muon_len_cm"]), det=det)
    good = os.path.join(tmp, "score_%s.json" % det)
    with open(good, "w") as fh:
        json.dump({"labels": lab}, fh)
    bad = os.path.join(tmp, "score_%s_bogus.json" % det)
    l2 = dict(lab)
    k0 = list(l2)[0]
    l2[k0] = dict(l2[k0], label="BOGUS")
    with open(bad, "w") as fh:
        json.dump({"labels": l2}, fh)
    py = sys.executable
    sc = os.path.join(HERE, "score_stm_michel_scan.py")
    r1 = subprocess.run([py, sc, "--det", det, "--labels", good],
                        capture_output=True, text=True)
    ck(r1.returncode == 0, "%s: the scorer crashed:\n%s" % (det, r1.stderr[-800:]))
    for want in ("purity", "efficiency", "confusion", "Michel only",
                 "under-clustering", "pin moved off"):
        ck(want in r1.stdout, "%s: the scorer printed no %r section" % (det, want))
    ck("REVEALED" in r1.stdout and "hidden" in r1.stdout,
       "%s: the scorer merged revealed and hidden labels" % det)
    r2 = subprocess.run([py, sc, "--det", det, "--labels", bad],
                        capture_output=True, text=True)
    ck(r2.returncode != 0 and "refusing to guess" in (r2.stdout + r2.stderr),
       "%s: the scorer accepted an unknown label" % det)


# ---------------------------------------------------------------------------
# H -- the 2-D measurement panels
# ---------------------------------------------------------------------------
def _one_prep(det):
    """(payload, path) of the first item that has a Michel AND some cells."""
    for fn in sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json"))):
        with open(fn) as fh:
            d = json.load(fh)
        if d.get("proj") and len(d["proj"]["w"]["ch"]) > 200 and \
                d["verdict"].get("michel_found") and (d["verdict"].get("michel") or {}).get("x"):
            return d, fn
    return None, None


def test_meas_static(det):
    """Everything about the panel that can be checked from the payloads alone."""
    print("[H] the 2-D measurement, %s" % det)
    files = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    ck(bool(files), "%s: no payloads to check the measurement panel on" % det)
    if not files:
        return
    b, nch = smgeom.BASE[det], smgeom.NCH[det]
    ncell = nsplit = 0
    bad_span = []
    for fn in files[::7]:
        with open(fn) as fh:
            d = json.load(fh)
        prj = d.get("proj") or {}
        for pl, nm in enumerate("uvw"):
            c = prj.get(nm) or dict(ch=[], ts=[], q=[], qp=[], qe=[])
            n = len(c["ch"])
            ck(all(len(c[k]) == n for k in ("ts", "q", "qp", "qe")),
               "%s %s: ragged proj columns in %s" % (det, nm, os.path.basename(fn)))
            for ch in c["ch"]:
                ncell += 1
                # H1: the module's own splitter must agree with the vectorised
                # one prep used, on every cell -- one wrong `base` is silent.
                if smgeom.plane_from_chan(det, ch) == pl and b[pl] <= ch < b[pl] + nch[pl]:
                    nsplit += 1
                else:
                    bad_span.append((os.path.basename(fn), nm, ch))
            # H4: the residual the panel draws is meas - pred, recomputed here
            for q, qp in list(zip(c["q"], c["qp"]))[:50]:
                pass
        dead = d.get("dead") or {}
        for pl, nm in enumerate("uvw"):
            dd = dead.get(nm) or dict(ch=[], t0=[], t1=[])
            for ch in dd["ch"]:
                ck(smgeom.plane_from_chan(det, ch) == pl,
                   "%s: T_bad_ch channel %d filed under plane %s" % (det, ch, nm))
                break
            for t0, t1 in list(zip(dd["t0"], dd["t1"]))[:1]:
                # H3 consequence: a band converted to SLICES cannot run past the
                # slice count.  At /1 it would end at 6000 (pdhd) / 10000 (pdvd).
                ck(t1 <= 4000.0,
                   "%s: dead band ends at slice %.1f -- ticks were not converted"
                   % (det, t1))
        ck(d.get("ticks_per_slice") == smgeom.TICKS_PER_SLICE[det],
           "%s: payload ticks_per_slice %r != %d"
           % (det, d.get("ticks_per_slice"), smgeom.TICKS_PER_SLICE[det]))
    ck(nsplit == ncell,
       "%s: %d of %d projection cells fall outside their plane's base block: %s"
       % (det, ncell - nsplit, ncell, bad_span[:3]))
    print("     %d projection cells, %d in their own plane block (%.4f)"
          % (ncell, nsplit, nsplit / max(ncell, 1)))


def test_meas_causal(det):
    """H2/H3 -- the two silent failures, each gated against the FILES.

    H2 the plane split: the fitter writes pu/pv/pw with globalf() and the
       projection writer writes channel with global().  Two code paths, one
       coordinate -- so a fit point's own wire has to land on a cell of the same
       channel.  A wrong `base` breaks that immediately.
    H3 the tick -> slice conversion: max(T_bad_ch.end_time) over
       (max(T_proj_data.time_slice) + 1) IS the ratio, read off the files.  The
       config says 4 too, but a config is not a measurement.
    """
    try:
        import uproot
    except ImportError:
        print("     (uproot missing -- H2/H3 skipped)")
        return
    arm = ARM[det]
    fns = sorted(glob.glob(os.path.join(IMG, det, "work", "*_" + arm,
                                        "tracking-pr.root")))[:8]
    ck(bool(fns), "%s: no arm files for the causal measurement gates" % det)
    hit = [0, 0, 0]; tot = [0, 0, 0]
    mx_ts = 0; mx_end = 0
    for fn in fns:
        f = uproot.open(fn)
        keys = {k.split(";")[0] for k in f.keys()}
        if "T_bad_ch" in keys:
            bc = f["T_bad_ch"].arrays(["end_time"], library="np")
            if len(bc["end_time"]):
                mx_end = max(mx_end, int(bc["end_time"].max()))
        if "T_proj_data" not in keys:
            continue
        d0 = f["T_proj_data"].arrays(library="np")
        if not len(d0["cluster_id"]):
            continue
        idx = {int(c): i for i, c in enumerate(d0["cluster_id"][0])}
        rc = f["T_rec_charge"].arrays(["pu", "pv", "pw", "pt", "cluster_id"],
                                      library="np")
        # ONLY the clusters this display draws.  T_proj_data also carries rows
        # for satellite/associated clusters and for the fallback blob-ownership
        # tagging, whose cells are not the fit's own -- including them measured
        # 0.70-0.74 rather than 0.91-0.95 and would turn this gate into a
        # threshold nobody could interpret.  The panel shows one cluster: the
        # item's.  So does the gate.
        if "T_stm_michel" not in keys:
            continue
        mm = f["T_stm_michel"].arrays(
            ["cluster_id", "has_pass", "n_profile_pts", "muon_len"], library="np")
        shown = {int(c) for i, c in enumerate(mm["cluster_id"])
                 if int(mm["has_pass"][i]) and int(mm["n_profile_pts"][i]) >= 20
                 and float(mm["muon_len"][i]) >= 10.0}
        for cid, j in ((c, k) for c, k in idx.items() if c in shown):
            ch = np.asarray(d0["channel"][0][j], np.int64)
            ts = np.asarray(d0["time_slice"][0][j], np.int64)
            if ts.size:
                mx_ts = max(mx_ts, int(ts.max()))
            cells = {}
            for c_, t_ in zip(ch, ts):
                cells.setdefault(int(c_), []).append(int(t_))
            k = rc["cluster_id"] == cid
            if not k.sum():
                continue
            for pl, key in enumerate(("pu", "pv", "pw")):
                w = np.floor(rc[key][k]).astype(np.int64)
                lo, hi = smgeom.plane_span(det, pl)
                ck(int(w.min()) >= lo and int(w.max()) <= hi,
                   "%s: plane %d fit wires %d..%d escape their block %d..%d"
                   % (det, pl, w.min(), w.max(), lo, hi))
                for ww, tt in zip(w, rc["pt"][k]):
                    tot[pl] += 1
                    tl = cells.get(int(ww))
                    if tl and min(abs(t - tt) for t in tl) <= 2:
                        hit[pl] += 1
    for pl, nm in enumerate("UVW"):
        fr = hit[pl] / max(tot[pl], 1)
        ck(fr > 0.80, "%s %s: only %.4f of fit points land on a cell of their own "
                      "channel -- the plane split is probably wrong" % (det, nm, fr))
    print("     fit point lands on a T_proj_data cell of the same channel:"
          "  U %.4f  V %.4f  W %.4f"
          % tuple(hit[i] / max(tot[i], 1) for i in range(3)))
    if mx_end and mx_ts:
        ratio = mx_end / float(mx_ts + 1)
        ck(abs(ratio - smgeom.TICKS_PER_SLICE[det]) < 0.2,
           "%s: files say %.3f ticks per slice, smgeom says %d"
           % (det, ratio, smgeom.TICKS_PER_SLICE[det]))
        print("     ticks per slice from the files: %.3f (smgeom %d)"
              % (ratio, smgeom.TICKS_PER_SLICE[det]))


def test_meas_app(det, tmp):
    """H4-H10 -- the panel as the app actually fills it, and the click linking."""
    d, fn = _one_prep(det)
    ck(d is not None, "%s: no payload with cells AND a Michel for the panel test" % det)
    if d is None:
        return
    man = os.path.join(tmp, "meas_%s.tsv" % det)
    with open(man, "w") as fh:
        fh.write("scan_id\ttranche\tevent\tcluster\tnpts\tmuon_len_cm\tn_near\tn_far\n")
        fh.write("1\t1\t%s\t%d\t%d\t%.2f\t0\t0\n"
                 % (d["event"], d["cluster_id"], d["npts"], d["muon_len_cm"]))
    g = load_app(det, os.path.join(tmp, "labm_" + det),
                 os.path.join(HERE, "prep-" + det), man)

    # H4 -- the residual is meas - pred, recomputed from the payload
    for pl in "uvw":
        sm = g["SRCM"][pl].data
        exp = [a - b for a, b in zip(d["proj"][pl]["q"], d["proj"][pl]["qp"])]
        ck(len(sm["d"]) == len(exp) and all(abs(x - y) < 1e-6 for x, y in zip(sm["d"], exp)),
           "%s %s: the difference panel is not measured - predicted" % (det, pl))
        ck(list(sm["q"]) == [float(t) for t in d["proj"][pl]["q"]],
           "%s %s: the measured panel does not carry T_proj_data charge" % (det, pl))

    # H5 -- dead bands are inside the drawn window and in SLICE units
    for pl in "uvw":
        sd = g["SRCD"][pl].data
        xr = g["FIGM"][(pl, "xr")]
        for l_, r_, t_ in zip(sd["left"], sd["right"], sd["top"]):
            ck(r_ >= xr.start and l_ <= xr.end,
               "%s %s: a dead band is drawn outside the panel window" % (det, pl))
            ck(t_ <= 4000.0, "%s %s: dead band top %.1f is in ticks" % (det, pl, t_))
            break
        ck(g["FIGM"][(pl, "q")].x_range is g["FIGM"][(pl, "d")].x_range,
           "%s %s: the three columns do not share an x range" % (det, pl))
        ck(g["FIGM"][(pl, "q")].y_range is g["FIGM"][("w", "d")].y_range,
           "%s %s: the nine panels do not share a time range" % (det, pl))

    # H8 -- the chain's overlays reach measurement space too, unprompted.
    # INVERTED with the blind's removal (owner 2026-09-08): what used to prove
    # the nine panels honoured REVEAL now proves they honour its absence, which
    # is the assertion that would fail if a renderer were left switched off.
    for nm in ("michel", "delta", "dots"):
        ck(all(r.visible for r in g["MEAS_REND"][nm]),
           "%s: the %s measurement renderer is hidden with nothing to un-hide it"
           % (det, nm))
    v = (g["payload"](g["current"]()) or {}).get("verdict") or {}
    drawn = [nm for nm in ("michel", "delta", "dots")
             if (v.get(nm) or {}).get("x")]
    for nm in drawn:
        ck(bool(g["SRCT"][("w", nm)].data["w"]) or
           not any(t is not None for t in (v[nm].get("pw") or [])),
           "%s: the %s overlay is empty in measurement space although the chain "
           "found one" % (det, nm))
    ck(bool(g["SRCT"][("w", "muon")].data["w"]),
       "%s: the muon trajectory is missing from the measurement panel" % det)

    # H9 -- the scales are FIXED, and the multiplier moves all six together
    ck(g["cm_muon"].high == g["DQDX_HIGH"],
       "%s: the dQ/dx colour scale is not the fixed one" % det)
    hi0 = [g["CM_CELL"][p].high for p in "uvw"] + [g["CM_DIFF"][p].high for p in "uvw"]
    g["cell_scale"].active = 3                       # x4
    hi1 = [g["CM_CELL"][p].high for p in "uvw"] + [g["CM_DIFF"][p].high for p in "uvw"]
    ck(all(abs(b - 4 * a) < 1e-6 for a, b in zip(hi0, hi1)),
       "%s: the colour-scale multiplier did not move every mapper" % det)
    g["cell_scale"].active = 1

    # H10 -- no marker in the dQ/dx panel can be invisible on a white page
    pal = g["cm_muon"].palette
    def _lum(c):
        r, gg, bb = (int(c[1 + 2 * i:3 + 2 * i], 16) for i in range(3))
        return (0.2126 * r + 0.7152 * gg + 0.0722 * bb) / 255.0
    ck(max(_lum(c) for c in pal) < 0.90,
       "%s: the dQ/dx palette still contains a near-white colour (max luminance "
       "%.3f) -- the Bragg peak would be invisible" % (det, max(_lum(c) for c in pal)))
    outlined = 0
    for r in g["fq"].renderers:
        gl = getattr(r, "glyph", None)
        if gl is not None and getattr(gl, "line_color", None) not in (None, "#00000000"):
            outlined += 1
    ck(outlined >= 4, "%s: only %d dQ/dx glyphs carry an outline" % (det, outlined))

    # H6/H7 -- the click lands on the SAME point in every view
    for nm in ("muon", "michel"):
        src = g["SRCQ"][nm]
        n = len(src.data["a"])
        if not n:
            continue
        k = n // 3
        src.selected.indices = [k]
        row = {c: src.data[c][k] for c in g["QCOLS"]}
        c3 = g["SRC3"]["cursor"].data
        ck(len(c3["x"]) == 1 and abs(c3["x"][0] - row["x"]) < 1e-9
           and abs(c3["y"][0] - row["y"]) < 1e-9 and abs(c3["z"][0] - row["z"]) < 1e-9,
           "%s %s: the 3-D cursor is not on the clicked point" % (det, nm))
        ax = dict(x=row["x"], y=row["y"], z=row["z"])
        for ha, va, _t in g["PANELS"]:
            c2 = g["SRC2"][(ha, va, "cursor")].data
            ck(len(c2["a"]) == 1 and abs(c2["a"][0] - ax[ha]) < 1e-9
               and abs(c2["b"][0] - ax[va]) < 1e-9,
               "%s %s: the %s%s projection cursor is off the clicked point"
               % (det, nm, ha, va))
        for pl in "uvw":
            ct = g["SRCT"][(pl, "cursor")].data
            ck(len(ct["w"]) == 1 and abs(ct["w"][0] - row["p" + pl]) < 1e-9
               and abs(ct["t"][0] - row["pt"]) < 1e-9,
               "%s %s: the %s measurement cursor is off the clicked point"
               % (det, nm, pl))
        # the wire coordinates the cursor used are the FITTER's own, not derived
        ck(smgeom.plane_from_chan(det, int(row["pu"])) == 0
           and smgeom.plane_from_chan(det, int(row["pv"])) == 1
           and smgeom.plane_from_chan(det, int(row["pw"])) == 2,
           "%s %s: the clicked point's pu/pv/pw are not one per plane" % (det, nm))
        src.selected.indices = []
        ck(not g["SRC3"]["cursor"].data["x"] and not g["SRCT"][("u", "cursor")].data["w"],
           "%s %s: deselecting did not clear the cursor" % (det, nm))
    # picking in one series drops the pick in another
    if len(g["SRCQ"]["muon"].data["a"]) and len(g["SRCQ"]["michel"].data["a"]):
        g["SRCQ"]["muon"].selected.indices = [0]
        g["SRCQ"]["michel"].selected.indices = [0]
        ck(not g["SRCQ"]["muon"].selected.indices,
           "%s: two dQ/dx series stayed selected at once" % det)
    # a new item must not leave a stale cursor behind
    g["SRCQ"]["muon"].selected.indices = [0]
    g["render"]()
    ck(not g["SRC3"]["cursor"].data["x"],
       "%s: the cursor survived a re-render onto a different state" % det)


# ---------------------------------------------------------------------------
# I -- the particle flow
# ---------------------------------------------------------------------------
def test_pf_selector(det):
    """The row selector, gated against the FILES.

    T_rec_charge's `cluster_id` branch is bound to reco_mother_cluster_id -- a
    GROUP id -- while `sub_cluster_id` is cluster_id * 1000 + graph index.  Using
    the former silently returns another cluster's segments, or none at all.  This
    asserts the trap is real on this arm rather than taking the header's word.
    """
    print("[I] the particle flow, %s" % det)
    try:
        import uproot
    except ImportError:
        print("     (uproot missing -- I1 skipped)")
        return
    arm = ARM[det]
    nz = ndiff = ncand = 0
    for fn in sorted(glob.glob(os.path.join(IMG, det, "work", "*_" + arm,
                                            "tracking-pr.root")))[:8]:
        f = uproot.open(fn)
        keys = {k.split(";")[0] for k in f.keys()}
        if "T_stm_michel" not in keys:
            continue
        m = f["T_stm_michel"].arrays(["cluster_id"], library="np")
        rc = f["T_rec_charge"].arrays(
            ["sub_cluster_id", "flag_vertex", "cluster_id"], library="np")
        seg = rc["flag_vertex"] == 0
        for cid in m["cluster_id"]:
            cid = int(cid); ncand += 1
            by_mother = set(np.flatnonzero(seg & (rc["cluster_id"] == cid)).tolist())
            by_seg = set(np.flatnonzero(seg & ((rc["sub_cluster_id"] // 1000) == cid)).tolist())
            ck(bool(by_seg), "%s: cluster %d has no PF rows under sub_cluster_id//1000" % (det, cid))
            if not by_mother:
                nz += 1
            if by_mother != by_seg:
                ndiff += 1
    ck(nz > 0 or ndiff > 0,
       "%s: selecting PF rows by cluster_id gave the SAME answer everywhere -- "
       "the documented trap did not reproduce" % det)
    print("     %d/%d candidates get a DIFFERENT row set from cluster_id "
          "(%d of them get none at all)" % (ndiff, ncand, nz))


def test_pf_payload(det):
    files = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    nseg = npt = 0
    for fn in files[::9]:
        with open(fn) as fh:
            d = json.load(fh)
        pf = d.get("pf") or {}
        ck("seg" in pf and "vtx" in pf, "%s: payload has no pf block" % det)
        types = (d.get("verdict") or {}).get("pf_type") or {}
        for sg in pf.get("seg") or []:
            nseg += 1
            n = sg["npts"]
            ck(all(len(sg[k]) == n for k in ("x", "y", "z", "pu", "pv", "pw",
                                             "pt", "dqdx", "rr")),
               "%s: ragged PF segment %s" % (det, sg["id"]))
            ck(sg["id"] // 1000 == d["cluster_id"],
               "%s: PF segment %d does not belong to cluster %d"
               % (det, sg["id"], d["cluster_id"]))
            ck(str(sg["id"]) in types,
               "%s: PF segment %d has no pf_type entry" % (det, sg["id"]))
            for i in range(0, n, max(1, n // 5)):
                npt += 1
                ck(smgeom.plane_from_chan(det, int(sg["pu"][i])) == 0
                   and smgeom.plane_from_chan(det, int(sg["pv"][i])) == 1
                   and smgeom.plane_from_chan(det, int(sg["pw"][i])) == 2,
                   "%s: PF point of segment %d is not one wire per plane"
                   % (det, sg["id"]))
        # pf_type must live ONLY in the verdict block
        ck("pf_type" not in d and "shower" not in d,
           "%s: the PF particle type leaked to the payload top level" % det)
    print("     %d PF segments checked, %d PF points wire-split" % (nseg, npt))


def test_pf_app(det, tmp):
    g = load_app(det, os.path.join(tmp, "labpf_" + det))
    # find an item that HAS more than one PF segment
    for i in range(len(g["ITEMS"])):
        g["go"](i)
        if len(g["seg_select"].options) > 1:
            break
    segs = g["pf_segments"](g["payload"](g["current"]()))
    ck(len(segs) > 1, "%s: no item with more than one PF segment" % det)
    if len(segs) < 2:
        return
    # the toggle gates the topology layers and nothing else
    g["pf_tog"].active = False
    ck(not g["SRC3"]["pfseg"].data["x"] and not g["SRC3"]["pfvtx"].data["x"],
       "%s: the PF topology is drawn with the toggle off" % det)
    g["pf_tog"].active = True
    ck(bool(g["SRC3"]["pfseg"].data["x"]) and bool(g["SRC3"]["pfvtx"].data["x"]),
       "%s: the PF toggle did not turn the topology on" % det)
    ck(len(set(g["SRC3"]["pfseg"].data["col"])) == min(len(segs), len(g["PF_PALETTE"])),
       "%s: the PF segments are not separately coloured" % det)
    # the segment the panel REPORTS is the segment that was picked
    for i, sg in enumerate(segs):
        g["seg_select"].value = g["seg_select"].options[i]
        ck(g["state"]["pf_seg"] == sg["id"],
           "%s: picking option %d selected segment %s, not %s"
           % (det, i, g["state"]["pf_seg"], sg["id"]))
        ck(len(g["SRC3"]["pfsel"].data["x"]) == sg["npts"],
           "%s: the highlight has %d points, the segment has %d"
           % (det, len(g["SRC3"]["pfsel"].data["x"]), sg["npts"]))
        ck(("S%d" % sg["id"]) in g["seg_div"].text
           and ("%d points" % sg["npts"]) in g["seg_div"].text
           and ("%.1f cm" % sg["len_cm"]) in g["seg_div"].text,
           "%s: the inspector does not report segment %d's own id/npts/length"
           % (det, sg["id"]))
        for pl in "uvw":
            ck(len(g["SRCT"][(pl, "pfsel")].data["w"]) <= sg["npts"],
               "%s: the %s measurement highlight has more points than the segment"
               % (det, pl))
    # tag, save, reload
    g["seg_select"].value = g["seg_select"].options[0]
    g["set_pf_tag"]("michel")
    ck(len(g["SRC3"]["pftag"].data["x"]) == segs[0]["npts"],
       "%s: the tag ring does not cover the tagged segment" % det)
    ck(set(g["SRC3"]["pftag"].data["col"]) == {g["PF_TAGS"]["michel"]},
       "%s: the tag ring is not in the tag colour" % det)
    ck("NOT yet on disk" in g["save_div"].text,
       "%s: a tag with no label claimed to be saved" % det)
    g["michel_kind"].active = g["MICHEL_KINDS"].index("attached")
    key = g["item_key"](g["current"]())
    g["set_label"]("STM_MICHEL")
    with open(g["LABEL_FILE"]) as fh:
        rec = json.load(fh)["labels"][key]
    ck(rec.get("pf_segments") == {str(segs[0]["id"]): "michel"},
       "%s: pf_segments did not round-trip: %r" % (det, rec.get("pf_segments")))
    ck(rec.get("pf_tagged") == 1 and rec.get("n_pf_segments") == len(segs),
       "%s: pf_tagged/n_pf_segments wrong: %r %r"
       % (det, rec.get("pf_tagged"), rec.get("n_pf_segments")))
    # write-through on an ALREADY labelled item
    g["go"](g["ITEMS"].index(next(it for it in g["ITEMS"]
                                  if g["item_key"](it) == key)))
    g["seg_select"].value = g["seg_select"].options[1]
    g["set_pf_tag"]("muon")
    with open(g["LABEL_FILE"]) as fh:
        rec = json.load(fh)["labels"][key]
    ck(rec.get("pf_segments", {}).get(str(segs[1]["id"])) == "muon",
       "%s: tagging an already-labelled item did not write through" % det)
    ck("saved and read back" in g["save_div"].text,
       "%s: the write-through did not report the read-back" % det)
    # BACKWARD COMPATIBILITY: a row written before pf_segments existed
    with open(g["LABEL_FILE"]) as fh:
        blob = json.load(fh)
    blob["labels"][key].pop("pf_segments", None)
    blob["labels"][key].pop("pf_tagged", None)
    blob["labels"][key].pop("n_pf_segments", None)
    with open(g["LABEL_FILE"], "w") as fh:
        json.dump(blob, fh)
    g2 = load_app(det, os.path.dirname(g["LABEL_FILE"]))
    ck(g2["LABELS"].get(key, {}).get("label") == "STM_MICHEL",
       "%s: a label with no pf_segments failed to load" % det)
    g2["go"](g2["ITEMS"].index(next(it for it in g2["ITEMS"]
                                    if g2["item_key"](it) == key)))
    ck(g2["state"]["pf_tag"] == {},
       "%s: a label with no pf_segments produced phantom tags" % det)


# ---------------------------------------------------------------------------
# J -- the save read-back
# ---------------------------------------------------------------------------
def test_save_readback(det, tmp):
    print("[J] the save read-back, %s" % det)
    lab = os.path.join(tmp, "labsv_" + det)
    g = load_app(det, lab)
    ok, n, nb, mt, err = g["read_back"]()
    ck(ok and n == 0, "%s: a fresh label dir did not read back as empty (%r)"
       % (det, err))
    ck("nothing saved yet" in g["save_div"].text,
       "%s: the opening banner does not say the file is empty: %s"
       % (det, g["save_div"].text[:140]))
    key = g["item_key"](g["current"]())
    g["set_label"]("THRU")            # NOTE: this advances to the next item
    ok, n, nb, mt, err = g["read_back"]()
    ck(ok and n == 1 and nb > 0,
       "%s: after one label the file reads back %r labels" % (det, n))
    ck("saved and read back" in g["save_div"].text
       and "holds <b>1</b> label" in g["save_div"].text,
       "%s: the save banner does not report the read-back: %s"
       % (det, g["save_div"].text[:160]))
    # the banner must come from the FILE, not from LABELS in memory
    g["LABELS"]["fake/999"] = dict(label="THRU")
    g["show_save"](after_write=False)
    ck("holds <b>1</b> label" in g["save_div"].text,
       "%s: the banner counted an in-memory label the file does not hold: %s"
       % (det, g["save_div"].text[:160]))
    g["LABELS"].pop("fake/999")
    # save_info names THIS item and finds it -- go back to the one just labelled
    g["go"](g["ITEMS"].index(next(it for it in g["ITEMS"]
                                  if g["item_key"](it) == key)))
    g["save_info"]()
    ck(key in g["status"].text and "is on disk" in g["status"].text,
       "%s: save_info did not report this item's saved row: %s"
       % (det, g["status"].text[:160]))
    # an unreadable file is reported as NOT saved, not as saved
    with open(g["LABEL_FILE"], "w") as fh:
        fh.write("{ this is not json")
    ok, n, nb, mt, err = g["read_back"]()
    ck(not ok, "%s: a corrupt labels.json read back as OK" % det)
    g["show_save"]()
    ck("NOT SAVED" in g["save_div"].text,
       "%s: a corrupt labels.json was still reported as saved" % det)
    g["save_info"]()
    ck("could not read" in g["status"].text,
       "%s: save_info did not report the unreadable file" % det)



# ---------------------------------------------------------------------------
# K -- the matched Q-L bundle (doc pdhd/13 sec 4).  The Bee layer draws every
# cluster at its OWN bundle's t0-corrected position, so an unrelated cosmic can
# land centimetres from the muon and read as over-clustering.  These gates prove
# the payload's bundle is the one T_cluster says, and that the control actually
# removes charge rather than merely claiming to.
# ---------------------------------------------------------------------------
def test_bundle_payload(det):
    print("[K] the Q-L bundle in the payload, %s" % det)
    import zipfile
    arm = ARM[det]
    fns = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    ck(bool(fns), "%s: no payloads for the bundle test" % det)
    if not fns:
        return
    nchecked = 0
    for fn in fns[:: max(1, len(fns) // 20)]:
        with open(fn) as fh:
            d = json.load(fh)
        evd = os.path.join(IMG, det, "work", "%s_%s" % (d["event"], arm))
        rf = os.path.join(evd, "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        tc = uproot.open(rf)["T_cluster"].arrays(
            ["cluster_id", "flash_id", "cluster_t0_us"], library="np")
        cid = int(d["cluster_id"])
        w = np.where(tc["cluster_id"] == cid)[0]
        if not len(w):
            continue
        i = int(w[0])
        # independent re-derivation: BOTH fields, exactly, as the doc requires
        want = sorted(int(c) for c, fl, t0 in
                      zip(tc["cluster_id"], tc["flash_id"], tc["cluster_t0_us"])
                      if fl == tc["flash_id"][i]
                      and abs(t0 - tc["cluster_t0_us"][i]) <= 1e-6)
        ck(d.get("bundle") == want,
           "%s: %s c%d bundle %s != T_cluster's %s"
           % (det, d["event"], cid, d.get("bundle"), want))
        ck(cid in (d.get("bundle") or []),
           "%s: %s c%d is not in its own bundle" % (det, d["event"], cid))
        for lyr in ("image_near", "image_far"):
            g = d.get(lyr) or {}
            ck(len(g.get("b") or []) == len(g.get("x") or []),
               "%s: %s c%d %s has %d flags for %d points"
               % (det, d["event"], cid, lyr,
                  len(g.get("b") or []), len(g.get("x") or [])))
        nchecked += 1
    ck(nchecked > 0, "%s: no payload could be checked against T_cluster" % det)

    # one payload re-derived point by point, against the Bee cluster_id itself
    with open(fns[0]) as fh:
        d = json.load(fh)
    zp = os.path.join(IMG, det, "work", "%s_%s" % (d["event"], arm), "mabc-pr.zip")
    if not (os.path.exists(zp) and d.get("bundle") is not None):
        return
    with zipfile.ZipFile(zp) as z:
        nm = [n for n in z.namelist() if n.endswith("clustering-global.json")][0]
        g = json.loads(z.read(nm))
    bset = set(d["bundle"])
    inb, outb = set(), set()
    for x, y, zz, c in zip(g["x"], g["y"], g["z"], g["cluster_id"]):
        key = (round(float(x), 1), round(float(y), 1), round(float(zz), 1))
        (inb if int(c) in bset else outb).add(key)
    bad = 0
    lay = d["image_near"]
    for x, y, zz, b in zip(lay["x"], lay["y"], lay["z"], lay["b"]):
        key = (round(float(x), 1), round(float(y), 1), round(float(zz), 1))
        # a position claimed in-bundle must exist among bundle clusters, and
        # vice versa; a position in BOTH is a rounding collision, allowed
        if b and key not in inb:
            bad += 1
        if (not b) and key not in outb:
            bad += 1
    ck(bad == 0,
       "%s: %d near points carry a bundle flag the Bee cluster_id contradicts"
       % (det, bad))
    print("     %s %s c%d: bundle %s, %d/%d near points in it"
          % (det, d["event"], d["cluster_id"], d["bundle"],
             sum(lay["b"]), len(lay["b"])))


def test_bundle_app(det, tmp):
    g = load_app(det, os.path.join(tmp, "labbn_" + det))
    # the item with the most out-of-bundle charge -- where the control matters
    best_i, best_out, best_in = 0, -1, 0
    for i, it in enumerate(g["ITEMS"]):
        p = g["payload"](it)
        if not p or p.get("bundle") is None:
            continue
        tot = 0
        inb = 0
        for lyr in ("image_near", "image_far"):
            b = (p.get(lyr) or {}).get("b") or []
            tot += len(b) - sum(b)
            inb += sum(b)
        if tot > best_out:
            best_out, best_in, best_i = tot, inb, i
    ck(best_out > 0,
       "%s: no item has out-of-bundle image charge to test the control on" % det)
    if best_out <= 0:
        return
    g["go"](best_i)

    def drawn():
        n = len(g["SRC3"]["near"].data["x"]) + len(g["SRC3"]["far"].data["x"])
        return n, len(g["SRC3"]["outb"].data["x"])

    g["bundle_tog"].active = True
    on_n, on_out = drawn()
    ck(on_out == 0, "%s: out-of-bundle charge drawn with `bundle only` ON" % det)
    ck(on_n == best_in,
       "%s: `bundle only` ON drew %d points, the payload says %d are in the bundle"
       % (det, on_n, best_in))

    g["bundle_tog"].active = False
    off_n, off_out = drawn()
    # CAUSAL CONTROL: turning it off restores every point, in its own layer
    ck(off_out == best_out,
       "%s: `bundle only` OFF drew %d out-of-bundle points, expected %d"
       % (det, off_out, best_out))
    ck(off_n == on_n,
       "%s: the in-bundle layers changed when the control was toggled" % det)
    ck(on_n + off_out == best_in + best_out,
       "%s: the control loses charge -- %d + %d != %d"
       % (det, on_n, off_out, best_in + best_out))
    # the 2-D panels carry the same split, so a layer cannot exist in one view
    # and be forgotten in the other
    for ha, va, _t in g["PANELS"]:
        ck(len(g["SRC2"][(ha, va, "outb")].data["a"]) == off_out,
           "%s: the %s-%s panel drew %d out-of-bundle points, the 3-D drew %d"
           % (det, ha, va, len(g["SRC2"][(ha, va, "outb")].data["a"]), off_out))
    g["bundle_tog"].active = True
    for ha, va, _t in g["PANELS"]:
        ck(not g["SRC2"][(ha, va, "outb")].data["a"],
           "%s: the %s-%s panel still draws out-of-bundle charge" % (det, ha, va))
    ck("hidden" in g["bundle_div"].text,
       "%s: the bundle banner does not say what was hidden" % det)
    print("     %s: control removes %d of %d image points on the worst item"
          % (det, best_out, best_in + best_out))


# ---------------------------------------------------------------------------
# L -- doc pdhd/14: the kinematics CheckSTM_Michel now writes
#
# The display is forbidden to compute an energy (owner, 2026-09-07: "all the
# information should be taken from the output of the chain, not by your
# calculations. Otherwise we cannot improve this module"), so these checks run
# the OTHER way round: smkine reimplements the two toolkit estimators and is
# used HERE, against the production binary's own branches, and nowhere near the
# payload.  A disagreement means the C++ is wrong, not the display.
# ---------------------------------------------------------------------------
def test_kine_gate(det):
    print("[L] the chain's muon kinematics, %s" % det)
    arm = ARM[det]
    fns = sorted(glob.glob(os.path.join(IMG, det, "work", "*_" + arm,
                                        "tracking-pr.root")))
    ck(bool(fns), "%s: no %s arm files for the kinematics gate" % (det, arm))
    n_rng = n_dq = n_dots = n_seg = n_prof = n_gap = 0
    w_rng = w_dq = w_dots = 0.0
    prof = []
    for rf in fns:
        f = uproot.open(rf)
        if "T_stm_michel" not in {k.split(";")[0] for k in f.keys()}:
            continue
        a = f["T_stm_michel"].arrays(library="np")
        if "muon_ke_range" not in a:
            ck(False, "%s: %s carries no muon_ke_range -- arm predates doc 14"
               % (det, os.path.basename(os.path.dirname(rf))))
            return
        p = f["T_stm_michel_pts"].arrays(
            ["cluster_id", "role", "seg_id", "q", "L"], library="np")
        rc = f["T_rec_charge"].arrays(
            ["x", "y", "z", "q", "nq", "sub_cluster_id", "particle_id",
             "flag_vertex"], library="np")
        tr = f["Trun"].arrays(["dQdx_scale", "dQdx_offset"], library="np")
        sc, off = float(tr["dQdx_scale"][0]), float(tr["dQdx_offset"][0])
        raw = (rc["q"] - off) / sc          # fit.dQ, before the visitor scaled it
        XYZ = np.c_[rc["x"], rc["y"], rc["z"]]

        for i in range(len(a["cluster_id"])):
            cid = int(a["cluster_id"][i])
            # L1  muon_ke_range == cal_kine_range(muon_len, 13)
            want = smkine.ke_range(float(a["muon_len"][i]), 13, det)
            d = abs(float(a["muon_ke_range"][i]) - want)
            w_rng = max(w_rng, d); n_rng += 1
            ck(d < 1e-6, "%s cl %d: muon_ke_range %.4f != %.4f"
               % (det, cid, a["muon_ke_range"][i], want))

            # L2  muon_ke_dqdx, two ways.
            #
            # It CANNOT be checked by selecting pdg-13 rows: `particle_id` is
            # the PR's own direction/PID verdict, not chain membership, and it
            # marks far more track than the STM chain -- measured on PDVD
            # 039253_6 cluster 82, twelve pdg-13 segments totalling 723.4 cm
            # against a muon_len of 418.6 cm.  Nor is the chain's segment list
            # in the output at all: n_chain_segs gives the COUNT, role-1 points
            # are the resampled profile and every one of them is stamped with
            # chain.back()'s id (CheckSTM_Michel.cxx:671, add_points), so the
            # composition of a multi-segment chain is unrecoverable.  Doc
            # pdhd/14 sec 8 names the one-line fix (StmMichelProfile::seg_idx
            # already carries it per point).
            #
            # So: EXACT where the chain is one segment and role-1's seg_id
            # therefore names it, and an independent PROFILE integral on the
            # rest -- a different quantity (resampled), so it is a
            # physics-level cross-check with a measured band, not a bit gate.
            k1 = (p["cluster_id"] == cid) & (p["role"] == 1)
            sids = {int(t) for t in p["seg_id"][k1]}
            ref = float(a["muon_ke_dqdx"][i])
            if int(a["n_chain_segs"][i]) == 1 and len(sids) == 1:
                k = ((rc["sub_cluster_id"] == sids.pop()) & (rc["flag_vertex"] == 0))
                if k.sum():
                    got = smkine.ke_dqdx(raw[k], rc["nq"][k], XYZ[k], det)
                    rel = abs(ref - got) / max(got, 1e-9)
                    w_dq = max(w_dq, rel); n_dq += 1
                    ck(rel < 1e-6, "%s cl %d: muon_ke_dqdx %.4f != %.4f"
                       % (det, cid, ref, got))
            if int(k1.sum()) > 2 and ref > 0:
                o = np.argsort(p["L"][k1])
                L, qq = p["L"][k1][o], p["q"][k1][o]
                d = np.diff(L)
                # The profile is a fixed-step resample (~0.6 cm), but the job
                # runs profile_min_dqdx_frac=0.15, which DELETES points in dead
                # cells and leaves multi-cm gaps.  A trapezoid across such a gap
                # multiplies one point's dQ/dx by tens of cm: measured 1.60 and
                # 1.63 on PDHD 028084_30/107 and 029107_18/54 (30.7 and 27.3 cm
                # steps), 0.43 on PDVD 039349_30/44.  That is this check's
                # artefact, not the chain's -- so a gapped profile is not
                # cross-checkable this way and is counted as skipped, never
                # silently widened away.
                gapped = bool(d.size and d.max() > 3.0 * max(float(np.median(d)), 1e-6))
                if gapped:
                    n_gap += 1
                e = 0.0 if gapped else float(
                    (smkine.dedx_from_dqdx(qq, det) * np.gradient(L)).sum())
                r = e / ref
                n_prof += 0 if gapped else 1
                # measured 2026-09-07 over 904 candidates: median 0.996,
                # p05-p95 [0.965, 1.011] on both detectors.  The window is
                # deliberately wide -- it exists to catch a wrong recombination
                # model or a unit slip, which would be off by 10x, not 3 %.
                if not gapped:
                    # measured 2026-09-07 over the 593 gap-free profiles of both
                    # arms: median 0.996, full range [0.84, 1.02].  The window is
                    # set from that range, not tightened onto it -- this check
                    # exists to catch a wrong recombination model or a unit slip
                    # (which are 10x errors), and the residual few per cent is
                    # the resampling difference it can never remove.
                    ck(0.75 < r < 1.25,
                       "%s cl %d: profile integral / muon_ke_dqdx = %.3f"
                       % (det, cid, r))
                    prof.append(r)

            # L3  muon_ke_best follows the toolkit's own >= 4 cm rule
            #     (PRSegmentFunctions.cxx:2900)
            exp = (float(a["muon_ke_dqdx"][i]) if float(a["muon_len"][i]) < 4.0
                   else float(a["muon_ke_range"][i]))
            ck(abs(float(a["muon_ke_best"][i]) - exp) < 1e-9,
               "%s cl %d: muon_ke_best is neither route" % (det, cid))

            # L4  michel_seg_id names a segment of the right ROLE, or -1
            conn = int(a["michel_conn_type"][i])
            msid = int(a["michel_seg_id"][i])
            role = {1: 3, 2: 4}.get(conn)
            if role is None:
                ck(msid == -1, "%s cl %d: conn 0 but michel_seg_id %d"
                   % (det, cid, msid))
            else:
                have = {int(t) for t in
                        p["seg_id"][(p["cluster_id"] == cid) & (p["role"] == role)]}
                # add_points skips every fit with dx <= 0 (:683), so a dot whose
                # fits ALL have dx <= 0 is counted in n_dots and named by
                # michel_seg_id while leaving no role-4 point at all -- and is
                # therefore invisible on the display.  Seen once: PDHD
                # 029107_20 cluster 136, seg 135010, 2 fits, both dx == 0.
                nofit = not (((rc["sub_cluster_id"] == msid)
                              & (rc["flag_vertex"] == 0) & (rc["nq"] > 0)).any())
                ck(msid in have or nofit,
                   "%s cl %d: michel_seg_id %d not a role-%d segment"
                   % (det, cid, msid, role))
                n_seg += 1

            # L5  dots_ke_dqdx -- the pre-doc-14 branch, still the anchor that
            #     keeps smkine honest about the endpoint/clamp rules
            if int(a["n_dots"][i]):
                k4 = (p["cluster_id"] == cid) & (p["role"] == 4)
                got = 0.0
                for sid in sorted({int(t) for t in p["seg_id"][k4]}):
                    k = (rc["sub_cluster_id"] == sid) & (rc["flag_vertex"] == 0)
                    if not k.sum():
                        continue
                    got += smkine.ke_dqdx(raw[k], rc["nq"][k], XYZ[k], det)
                ref = float(a["dots_ke_dqdx"][i])
                rel = abs(got - ref) / max(ref, 1e-9)
                w_dots = max(w_dots, rel); n_dots += 1
                ck(rel < 2e-3, "%s cl %d: dots_ke_dqdx %.4f != %.4f"
                   % (det, cid, ref, got))
    print("     %d muon_ke_range exact (worst %.1e MeV), %d single-segment"
          " muon_ke_dqdx exact (worst rel %.1e), %d profile cross-checks"
          " (median %.3f, %d skipped for a gapped profile), %d dots_ke_dqdx"
          " (worst rel %.1e), %d michel_seg_id links"
          % (n_rng, w_rng, n_dq, w_dq, n_prof,
             float(np.median(prof)) if prof else float("nan"), n_gap,
             n_dots, w_dots, n_seg))


def test_kine_payload(det):
    """The four branches reach the payload, unmodified, and nothing else does."""
    print("[L] the kinematics in the payload, %s" % det)
    arm = ARM[det]
    fns = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    ck(bool(fns), "%s: no payloads for the kinematics test" % det)
    n = 0
    for fn in fns[:: max(1, len(fns) // 25)]:
        with open(fn) as fh:
            d = json.load(fh)
        v = d.get("verdict") or {}
        for k in ("muon_ke_range", "muon_ke_dqdx", "muon_ke_best", "michel_seg_id",
                  "stop_vtx_id"):
            ck(k in v, "%s %s/%s: verdict has no %s"
               % (det, d["event"], d["cluster_id"], k))
        rf = os.path.join(IMG, det, "work", "%s_%s" % (d["event"], arm),
                          "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        a = uproot.open(rf)["T_stm_michel"].arrays(library="np")
        w = np.where(a["cluster_id"] == int(d["cluster_id"]))[0]
        if not len(w):
            continue
        i = int(w[0])
        for k in ("muon_ke_range", "muon_ke_dqdx", "muon_ke_best"):
            ck(abs(float(v[k]) - float(a[k][i])) < 1e-9,
               "%s %s/%s: %s was altered between tree and payload"
               % (det, d["event"], d["cluster_id"], k))
        ck(int(v["michel_seg_id"]) == int(a["michel_seg_id"][i]),
           "%s %s/%s: michel_seg_id altered" % (det, d["event"], d["cluster_id"]))
        n += 1
    print("     %d payloads carry the chain's kinematics verbatim" % n)


def test_kine_panel(det, tmp):
    """The mu -> e panel is filled on load -- there is nothing left to un-hide."""
    print("[L] the flow panel, %s" % det)
    g = load_app(det, os.path.join(tmp, "kine_" + det))
    ck("flow_div" in g, "%s: no flow_div in the app" % det)
    if "flow_div" not in g:
        return
    t = g["flow_div"].text
    ck("hidden" not in t.lower(), "%s: flow panel still says it is hidden" % det)
    ck("MeV" in t or "predates doc" in t,
       "%s: flow panel carries no energy on load" % det)
    # ... and the muon KE on the status line is still the chain's own number
    it = g["current"]()
    v = (g["payload"](it) or {}).get("verdict") or {}
    ck("MeV" in g["status"].text or v.get("muon_ke_best") is None,
       "%s: status line carries no muon KE" % det)
    if v.get("muon_ke_best") is not None:
        ck(("%.1f" % v["muon_ke_best"]) in g["status"].text,
           "%s: status muon KE is not the chain's muon_ke_best" % det)
        # the status line is the MUON's line and stays that way: the Michel
        # energy has its own panel and putting it here would say twice what the
        # scanner reads once
        ck(("%.1f MeV" % v.get("michel_ke_best", -1.0)) not in g["status"].text
           or not v.get("michel_ke_best"),
           "%s: the status line carries the Michel energy, not just the muon's" % det)


# ---------------------------------------------------------------------------
# [M] doc pdhd/15 -- the Michel as ONE object.
# ---------------------------------------------------------------------------

def test_object_tree(det):
    """The tree's own arithmetic: the object energy is core + pieces + charge.

    Every claim here is a relation BETWEEN branches of T_stm_michel, checked
    on the production tree, so it fails if the C++ ever stops adding a piece
    to the energy (the doc-14 defect) or starts double counting.
    """
    print("[M] the Michel object, %s" % det)
    arm = ARM[det]
    dirs = sorted(glob.glob(os.path.join(IMG, det, "work", "*_" + arm)))
    ck(bool(dirs), "%s: no %s event dirs" % (det, arm))
    n = n_obj = n_attached = n_bridged = n_charge = n_piece = 0
    worst = 0.0
    worst_gap = [0.0]
    for d in dirs:
        rf = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        f = uproot.open(rf)
        if "T_stm_michel" not in [k.split(";")[0] for k in f.keys()]:
            continue
        a = f["T_stm_michel"].arrays(library="np")
        ck("michel_ke_core" in a, "%s: %s predates doc pdhd/15 (no michel_ke_core)"
           % (det, os.path.basename(d)))
        if "michel_ke_core" not in a:
            return
        for i in range(len(a["cluster_id"])):
            tag = "%s %s/%d" % (det, os.path.basename(d), int(a["cluster_id"][i]))
            n += 1
            # nothing persisted may be non-finite: a NaN passes no gate and
            # fails every one silently (PDVD 039349_3 cluster 26, pre-doc-15)
            for k in a:
                x = a[k][i]
                if isinstance(x, (float, np.floating)):
                    ck(np.isfinite(x), "%s: %s is not finite (%s)" % (tag, k, x))
            conn = int(a["michel_conn_type"][i])
            found = int(a["michel_found"][i])
            # michel_found now means "a Michel object exists", detached included
            ck((found == 1) == (conn > 0),
               "%s: michel_found %d with conn_type %d" % (tag, found, conn))
            if conn == 0:
                ck(a["michel_ke_best"][i] == 0 and a["n_michel_segs"][i] == 0,
                   "%s: no object but a non-zero energy/segment count" % tag)
                ck(int(a["michel_parent_vtx_id"][i]) < 0,
                   "%s: no object but a parent vertex" % tag)
                continue
            n_obj += 1
            n_attached += conn == 1
            n_bridged += conn == 2
            n_charge += conn == 3
            n_piece += int(a["michel_n_pieces"][i])
            # the object energy IS dQ/dx over everything fitted plus the charge
            # term for what is not -- the owner's rule, doc pdhd/15 sec 1
            lhs = float(a["michel_ke_best"][i])
            rhs = float(a["michel_ke_dqdx"][i]) + float(a["dots_ke_unfit"][i])
            worst = max(worst, abs(lhs - rhs))
            ck(abs(lhs - rhs) < 1e-9,
               "%s: michel_ke_best %.6f != ke_dqdx + dots_ke_unfit %.6f" % (tag, lhs, rhs))
            # the object is never smaller than its own core
            ck(float(a["michel_ke_dqdx"][i]) >= float(a["michel_ke_core"][i]) - 1e-9,
               "%s: the object energy %.3f is below its core %.3f"
               % (tag, a["michel_ke_dqdx"][i], a["michel_ke_core"][i]))
            # the parentage is persisted for BOTH connection types
            ck(int(a["michel_parent_vtx_id"][i]) == int(a["stop_vtx_id"][i]),
               "%s: michel_parent_vtx_id %d is not the muon stop vertex %d"
               % (tag, a["michel_parent_vtx_id"][i], a["stop_vtx_id"][i]))
            # conn 3 is CHARGE ONLY: no fitted segment, hence no seg id and no
            # dQ/dx -- its whole energy is the charge conversion.
            if conn == 3:
                ck(int(a["michel_seg_id"][i]) < 0,
                   "%s: a charge-only object names a segment" % tag)
                ck(int(a["n_michel_segs"][i]) == 0 and float(a["michel_ke_dqdx"][i]) == 0.0,
                   "%s: a charge-only object has fitted members" % tag)
                ck(float(a["dots_ke_unfit"][i]) > 0,
                   "%s: a charge-only object with no charge" % tag)
            else:
                ck(int(a["michel_seg_id"][i]) >= 0, "%s: an object with no seg id" % tag)
            # the gap is 0 exactly when the arm shares the stop vertex
            gap = float(a["michel_dis_cm"][i])
            ck((gap == 0.0) == (conn == 1),
               "%s: michel_dis_cm %.3f with conn_type %d" % (tag, gap, conn))
            ck(gap >= 0, "%s: negative gap %.3f" % (tag, gap))
            if conn in (2, 3):
                # The seed piece belongs to a CLUSTER admitted within
                # michel_dot_radius_cm of the stop (doc pdhd/15 sec 3), so the
                # piece itself is bounded by radius + the cluster length cap --
                # NOT by the radius alone: the per-segment radius test was
                # removed on purpose, and 039252_1 cluster 30 carries a piece
                # whose own closest approach is 15.85 cm.
                bound = (MICHEL_DOT_RADIUS_CM if conn == 3 else
                         MICHEL_DOT_RADIUS_CM + COMPANION_MAX_LEN_CM)
                ck(gap <= bound + 1e-6,
                   "%s: conn-%d gap %.2f cm beyond the %.0f cm structural bound"
                   % (tag, conn, gap, bound))
                worst_gap[0] = max(worst_gap[0], gap)
            # the unfitted-charge term is the published conversion, or 0
            q = float(a["dots_charge_unfit"][i])
            e = float(a["dots_ke_unfit"][i])
            want = q / 0.7 / 0.95 * 23.6 / 1e6 if q > 0 else 0.0
            ck(abs(e - want) < 1e-6,
               "%s: dots_ke_unfit %.6f is not the 0.7/0.95/23.6 conversion of %.4g e (%.6f)"
               % (tag, e, q, want))
    print("     %d candidates, %d Michel objects (%d attached, %d bridged, %d charge-only), "
          "%d pieces; worst |best - (dqdx+unfit)| = %.2e MeV, widest bridge %.2f cm"
          % (n, n_obj, n_attached, n_bridged, n_charge, n_piece, worst, worst_gap[0]))


def test_object_spectrum(det):
    """A free absolute gate: the Michel spectrum ends at 52.8 MeV.

    An object that gathers charge it should not own shows up here before it
    shows up anywhere else -- the endpoint is fixed by (m_mu^2 + m_e^2)/(2 m_mu)
    and owes nothing to this reconstruction.  A few items may sit above it
    (the fit reads 2-D charge, so dQ can exceed a cluster's own blob charge),
    but a POPULATION above it means the gathering rule is wrong.
    """
    print("[M] the Michel spectrum against the endpoint, %s" % det)
    arm = ARM[det]
    ke = []
    for d in sorted(glob.glob(os.path.join(IMG, det, "work", "*_" + arm))):
        rf = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        f = uproot.open(rf)
        if "T_stm_michel" not in [k.split(";")[0] for k in f.keys()]:
            continue
        a = f["T_stm_michel"].arrays(library="np")
        for i in range(len(a["cluster_id"])):
            if a["has_pass"][i] == 1 and a["muon_len"][i] >= 10 and a["michel_found"][i]:
                ke.append(float(a["michel_ke_best"][i]))
    ck(bool(ke), "%s: no Michel objects to spectrum-check" % det)
    if not ke:
        return
    k = np.array(ke)
    over = int((k > MICHEL_ENDPOINT_MEV).sum())
    print("     n=%d  med %.1f  p90 %.1f  max %.1f MeV  | above %.1f MeV: %d (%.1f %%)"
          % (k.size, np.median(k), np.percentile(k, 90), k.max(),
             MICHEL_ENDPOINT_MEV, over, 100.0 * over / k.size))
    ck(np.median(k) < MICHEL_ENDPOINT_MEV,
       "%s: the MEDIAN Michel energy %.1f is above the %.1f MeV endpoint"
       % (det, np.median(k), MICHEL_ENDPOINT_MEV))
    ck(over <= 0.10 * k.size,
       "%s: %d of %d Michel objects (%.0f %%) exceed the %.1f MeV endpoint -- "
       "the object is gathering charge it does not own"
       % (det, over, k.size, 100.0 * over / k.size, MICHEL_ENDPOINT_MEV))


# ---------------------------------------------------------------------------
# doc pdhd/16 -- the muon's three energy scales
# ---------------------------------------------------------------------------
MMU_MEV = 105.658          # mcs/src/MuonMCS.cxx:37, and CheckSTM_Michel's mom_from_ke


def test_energy_scales(det):
    """The three muon energies and their momenta, as the chain emits them.

    O1  the nine doc-16 branches exist on this arm;
    O2  p = sqrt((KE+m)^2 - m^2) for each of range / dQ/dx / MCS, and a KE that
        was never computed carries p = -1 rather than 0 -- a zero momentum
        would pass every `>= 0` gate as if it had been measured;
    O3  muon_ke_mcs > 0 IFF the engine accepted the path: not bad_path and
        nsegs >= 2 (mcs/src/MuonMCS.cxx:1147-1169).  A positive energy with
        fewer than two fitted 14 cm segments would mean the abort branch is not
        firing;
    O4  muon_ke_best is STILL the range energy above 4 cm.  MCS is a
        cross-check, never the answer: this pins that nothing silently promoted
        it;
    O5  the CALIBRATION closes -- median(muon_ke_dqdx / muon_ke_range) on the
        is_stm sample is 1 within 5 %.  This is the whole point of the round and
        it is checked against the chain's own output, not against the fit that
        produced C.
    """
    print("[O] the muon's three energy scales, %s" % det)
    arm = ARM[det]
    cols = ["is_stm", "muon_len", "muon_ke_range", "muon_ke_dqdx", "muon_ke_best",
            "muon_ke_mcs", "muon_mcs_amb", "muon_mcs_nsegs", "muon_mcs_bad_path",
            "muon_mcs_tracklen", "muon_mcs_range_ke",
            "muon_p_range", "muon_p_dqdx", "muon_p_mcs"]
    acc = {c: [] for c in cols}
    nfile = 0
    for d in sorted(glob.glob(os.path.join(IMG, det, "work", "*_" + arm))):
        rf = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        f = uproot.open(rf)
        if "T_stm_michel" not in [k.split(";")[0] for k in f.keys()]:
            continue
        t = f["T_stm_michel"]
        miss = [c for c in cols if c not in t.keys()]
        ck(not miss, "%s %s: T_stm_michel is missing %s -- pre-doc-16 arm"
           % (det, os.path.basename(d), miss))
        if miss:
            return
        a = t.arrays(cols, library="np")
        for c in cols:
            acc[c].append(a[c])
        nfile += 1
    ck(nfile > 0, "%s: no %s event dirs with T_stm_michel" % (det, arm))
    if not nfile:
        return
    v = {c: np.concatenate(acc[c]) for c in cols}
    n = v["is_stm"].size

    # O2 -- the momentum identity, on every row
    def pmom(ke):
        return np.where(ke > 0, np.sqrt(np.maximum((ke + MMU_MEV) ** 2 - MMU_MEV ** 2, 0.0)), -1.0)
    for ke_k, p_k in (("muon_ke_range", "muon_p_range"),
                      ("muon_ke_dqdx", "muon_p_dqdx"),
                      ("muon_ke_mcs", "muon_p_mcs")):
        want = pmom(v[ke_k])
        bad = int((np.abs(want - v[p_k]) > 1e-3).sum())
        ck(bad == 0, "%s: %d of %d rows have %s != sqrt((%s+m)^2-m^2)"
           % (det, bad, n, p_k, ke_k))
        nz = int(((v[ke_k] <= 0) & (v[p_k] == 0)).sum())
        ck(nz == 0, "%s: %d rows carry %s = 0 for an uncomputed %s -- the -1 "
                    "sentinel was lost and a zero momentum reads as measured"
           % (det, nz, p_k, ke_k))

    # O3 -- the engine's own accept condition
    accepted = (v["muon_mcs_bad_path"] == 0) & (v["muon_mcs_nsegs"] >= 2)
    bad = int(((v["muon_ke_mcs"] > 0) & ~accepted).sum())
    ck(bad == 0, "%s: %d rows report an MCS energy the engine should have "
                 "refused (bad_path or < 2 fitted segments)" % (det, bad))

    # O4 -- range is still `best`
    lon = v["muon_len"] >= 4.0
    bad = int((np.abs(v["muon_ke_best"][lon] - v["muon_ke_range"][lon]) > 1e-6).sum())
    ck(bad == 0, "%s: %d of %d muons longer than 4 cm no longer take their "
                 "`best` energy from range" % (det, bad, int(lon.sum())))

    # O5 -- the calibration closes on the chain's own numbers
    sel = (v["is_stm"] == 1) & (v["muon_ke_range"] > 0) & (v["muon_ke_dqdx"] > 0)
    ck(int(sel.sum()) >= 20, "%s: only %d is_stm muons to close the calibration on"
       % (det, int(sel.sum())))
    if sel.sum() >= 20:
        r = v["muon_ke_dqdx"][sel] / v["muon_ke_range"][sel]
        med = float(np.median(r))
        mk = v["muon_ke_mcs"][sel] > 0
        amb = v["muon_mcs_amb"][sel]
        print("     n=%d  dQ/dx-over-range median %.4f (IQR %.3f-%.3f) | MCS on %d "
              "(%.0f %%), amb<0.2 on %d"
              % (int(sel.sum()), med, *np.percentile(r, [25, 75]),
                 int(mk.sum()), 100.0 * mk.sum() / sel.sum(),
                 int((mk & (amb < 0.2)).sum())))
        if mk.sum() >= 5:
            rm = v["muon_ke_mcs"][sel][mk] / v["muon_ke_range"][sel][mk]
            print("     MCS-over-range median %.4f (IQR %.3f-%.3f) on %d"
                  % (float(np.median(rm)), *np.percentile(rm, [25, 75]), int(mk.sum())))
        ck(abs(med - 1.0) <= 0.05,
           "%s: the calibrated dQ/dx energy sits at %.4f of range, not 1.00 -- "
           "the C in %s_stm_recomb no longer matches this arm" % (det, med, det))


def test_energy_payload(det):
    """The doc-16 branches reach the scan payload unmodified."""
    print("[O] the energy scales in the payload, %s" % det)
    fns = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    ck(bool(fns), "%s: no payloads for the energy-scale test" % det)
    KEYS = ("muon_ke_mcs", "muon_mcs_amb", "muon_mcs_nsegs", "muon_mcs_bad_path",
            "muon_mcs_tracklen", "muon_mcs_range_ke",
            "muon_p_range", "muon_p_dqdx", "muon_p_mcs")
    arm = ARM[det]
    n = 0
    for fn in fns[:: max(1, len(fns) // 25)]:
        with open(fn) as fh:
            d = json.load(fh)
        v = d.get("verdict") or {}
        for k in KEYS:
            ck(k in v, "%s %s/%s: verdict has no %s"
               % (det, d["event"], d["cluster_id"], k))
        rf = os.path.join(IMG, det, "work", "%s_%s" % (d["event"], arm),
                          "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        a = uproot.open(rf)["T_stm_michel"].arrays(library="np")
        w = np.where(a["cluster_id"] == int(d["cluster_id"]))[0]
        if not len(w):
            continue
        i = int(w[0])
        for k in KEYS:
            if k not in a:
                continue
            ck(abs(float(v[k]) - float(a[k][i])) < 1e-9,
               "%s %s/%s: %s payload %s != tree %s"
               % (det, d["event"], d["cluster_id"], k, v[k], a[k][i]))
        n += 1
    print("     %d payload(s) cross-checked against the tree" % n)


def test_object_payload(det):
    """The doc-15 branches reach the payload unmodified."""
    print("[M] the object in the payload, %s" % det)
    arm = ARM[det]
    fns = sorted(glob.glob(os.path.join(HERE, "prep-" + det, "smprep-*.json")))
    ck(bool(fns), "%s: no payloads for the object test" % det)
    KEYS = ("michel_ke_core", "michel_ke_charge", "michel_n_pieces",
            "michel_parent_vtx_id", "michel_dis_cm", "dots_ke_unfit")
    n = 0
    for fn in fns[:: max(1, len(fns) // 25)]:
        with open(fn) as fh:
            d = json.load(fh)
        v = d.get("verdict") or {}
        for k in KEYS:
            ck(k in v, "%s %s/%s: verdict has no %s"
               % (det, d["event"], d["cluster_id"], k))
        rf = os.path.join(IMG, det, "work", "%s_%s" % (d["event"], arm),
                          "tracking-pr.root")
        if not os.path.exists(rf):
            continue
        a = uproot.open(rf)["T_stm_michel"].arrays(library="np")
        w = np.where(a["cluster_id"] == int(d["cluster_id"]))[0]
        if not len(w):
            continue
        i = int(w[0])
        for k in KEYS:
            if k not in a:
                continue
            ck(abs(float(v[k]) - float(a[k][i])) < 1e-9,
               "%s %s/%s: %s was altered between tree and payload"
               % (det, d["event"], d["cluster_id"], k))
        n += 1
    print("     %d payloads carry the object fields verbatim" % n)


def test_object_panel(det, tmp):
    """The flow panel states one object and one link, for both connection types."""
    print("[M] the flow panel says ONE object, %s" % det)
    g = load_app(det, os.path.join(tmp, "obj_" + det))
    ck("flow_div" in g, "%s: no flow_div in the app" % det)
    if "flow_div" not in g:
        return
    seen = {1: 0, 2: 0, 3: 0, 0: 0}
    for i, it in enumerate(g["ITEMS"]):
        v = (g["payload"](it) or {}).get("verdict") or {}
        conn = int(v.get("michel_conn_type") or 0)
        if seen[conn]:
            continue
        g["go"](i)
        t = g["flow_div"].text
        ck("the chain's answer" in t, "%s: the flow panel is not filled" % det)
        ck("no parentage is persisted" not in t,
           "%s: the panel still claims a bridged Michel has no persisted parentage" % det)
        if conn == 1:
            # substring checks skip the <b> tags: the panel renders
            # "<b>attached</b> at the shared stop vertex"
            ck("at the shared stop vertex" in t,
               "%s: an attached Michel is not described as attached" % det)
            ck(str(int(v["stop_vtx_id"])) in t,
               "%s: the attached link does not name the shared vertex" % det)
        elif conn in (2, 3):
            ck(("to the same stop vertex" if conn == 2 else "charge only") in t,
               "%s: a conn-%d Michel is not described as such" % (det, conn))
            ck(("%.2f cm" % v["michel_dis_cm"]) in t,
               "%s: the conn-%d link does not carry the measured gap" % (det, conn))
            ck(str(int(v["michel_parent_vtx_id"])) in t,
               "%s: the conn-%d link does not name the parent vertex" % (det, conn))
        else:
            ck("no daughter" in t, "%s: an item with no Michel does not say so" % det)
        if conn:
            ck(("%.1f" % v["michel_ke_best"]) in t,
               "%s: the panel does not show the object energy" % det)
            ck(("%.1f" % v["michel_ke_core"]) in t,
               "%s: the panel does not show the core energy" % det)
            ck("piece" in t, "%s: the panel does not describe the object's pieces" % det)
        seen[conn] = 1
        # conn 3 exists only where a companion went unfitted (PDHD only on these
        # arms), so do not require it before stopping.
        if all(seen[k] for k in (0, 1, 2)):
            break
    print("     panel checked for conn types: %s"
          % ", ".join(str(k) for k, v in sorted(seen.items()) if v))


def test_tranche_draw(det):
    """[N] The tranche column -- pinned to a named sheet, or reproducible from the key.

    doc pdhd/15 sec 10.  `stratum()` keys on `michel_found`, so an algorithm
    change silently RE-DRAWS the hand-scan sample: 41 of 60 pdvd and 32 of 60
    pdhd tranche-1 items moved between the d14 and d15 sheets, under a scan
    already in progress, and nothing was watching that column.  This gate
    watches it in BOTH modes, so it cannot just bless whatever is on disk:

      * a PINNED sheet must reproduce its declared source exactly, and the
        "N key(s) absent" count in its header must be the true count;
      * an UNPINNED sheet must reproduce prep's own draw from the key's strata.

    It also re-derives `scan_id`, which is a POSITIONAL index (enumerate over
    the (event, cluster) sort): one candidate more or fewer shifts every id
    after it and silently invalidates the scan_id stored in every label record
    already written.
    """
    print("[N] the tranche draw, %s" % det)
    import csv as _csv, re as _re
    sd = os.path.join(IMG, det, "docs", "scan")
    sheetf = os.path.join(sd, "%s_stm_michel_scan_sheet.tsv" % det)
    keyf = os.path.join(sd, "%s_stm_michel_scan_key.tsv" % det)
    for f in (sheetf, keyf):
        ck(os.path.exists(f), "%s: missing %s" % (det, f))
    if not (os.path.exists(sheetf) and os.path.exists(keyf)):
        return

    def rows_of(f):
        txt = open(f).read()
        body = [l for l in txt.splitlines(True) if not l.startswith("#")]
        hdr = [l for l in txt.splitlines() if l.startswith("#")]
        out = {}
        for r in _csv.DictReader(body, delimiter="\t"):
            out[(r["event"], int(r["cluster"]))] = r
        return hdr, out

    shdr, srow = rows_of(sheetf)
    khdr, krow = rows_of(keyf)

    # N1 -- the two files describe the same sample, item for item
    ck(set(srow) == set(krow),
       "%s: sheet and key key-sets differ (%d vs %d)" % (det, len(srow), len(krow)))
    common = sorted(set(srow) & set(krow))
    bad = [k for k in common if srow[k]["scan_id"] != krow[k]["scan_id"]]
    ck(not bad, "%s: scan_id differs between sheet and key on %d item(s)" % (det, len(bad)))
    bad = [k for k in common if srow[k]["tranche"] != krow[k]["tranche"]]
    ck(not bad, "%s: tranche differs between sheet and key on %d item(s)" % (det, len(bad)))

    # N2 -- scan_id is the dense rank in (event, cluster) order, 1..N
    order = sorted(srow, key=lambda k: (k[0], k[1]))
    bad = [k for n, k in enumerate(order, start=1) if int(srow[k]["scan_id"]) != n]
    ck(not bad, "%s: scan_id is not the dense (event, cluster) rank on %d item(s): %s"
       % (det, len(bad), bad[:3]))

    # N3 -- the tranche column itself
    vals = {srow[k]["tranche"] for k in srow}
    ck(vals <= {"1", "2"}, "%s: tranche values outside {1,2}: %s" % (det, sorted(vals)))
    n1 = sum(1 for k in srow if srow[k]["tranche"] == "1")
    want = min(_prep["TRANCHE1"], len(srow))
    ck(n1 == want, "%s: tranche 1 holds %d items, expected %d" % (det, n1, want))

    # N4 -- the draw is either inherited from a NAMED source, or reproducible
    pin_spec = None
    for h in shdr:
        m = _re.match(r"#\s*tranche INHERITED from (\S+)", h)
        if m:
            pin_spec = m.group(1)
            break
    declares_seed = any(h.startswith("# seed=") for h in shdr)
    ck((pin_spec is None) != (not declares_seed),
       "%s: sheet header must declare EITHER a pin OR a seed draw, not both/neither"
       % det)

    if pin_spec:
        try:
            pin = _prep["read_pinned_tranche"](pin_spec)
        except Exception as e:                                   # noqa: BLE001
            ck(False, "%s: pin source %s is unreadable: %s" % (det, pin_spec, e))
            return
        bad = [k for k in srow if k in pin and int(srow[k]["tranche"]) != pin[k]]
        ck(not bad, "%s: %d item(s) disagree with the pinned source %s: %s"
           % (det, len(bad), pin_spec, bad[:3]))
        absent = [k for k in srow if k not in pin]
        ck(all(srow[k]["tranche"] == "2" for k in absent),
           "%s: %d key(s) absent from the pin are not tranche 2" % (det, len(absent)))
        said = None
        for h in shdr:
            m = _re.search(r"(\d+) key\(s\) absent from it are tranche 2", h)
            if m:
                said = int(m.group(1))
        ck(said == len(absent),
           "%s: header claims %s unpinned key(s), the sheet has %d"
           % (det, said, len(absent)))
        # the key file must carry the SAME inherited column (it is pinned too)
        bad = [k for k in krow if k in pin and int(krow[k]["tranche"]) != pin[k]]
        ck(not bad, "%s: the answer key's tranche is not pinned (%d item(s))"
           % (det, len(bad)))
        # and the header must NOT also claim a draw that did not happen
        ck(not declares_seed,
           "%s: a pinned sheet still advertises `seed=` -- it describes a draw "
           "that did not run (feedback_rederive_from_primary_source)" % det)
    else:
        kk = []
        for k in order:
            r = krow[k]
            kk.append({"event": r["event"], "cluster": int(r["cluster"]),
                       "is_stm": int(r["is_stm"]), "michel_found": int(r["michel_found"])})
        drawn = _prep["tranche"](kk)
        bad = [k for k in srow
               if int(srow[k]["tranche"]) != (1 if k in drawn else 2)]
        ck(not bad, "%s: the sheet's tranche is not prep's own draw on %d item(s): %s"
           % (det, len(bad), bad[:3]))
        # the strata the draw used must be the ones the key records
        bad = [k for k in krow
               if _prep["stratum"]({"is_stm": int(krow[k]["is_stm"]),
                                    "michel_found": int(krow[k]["michel_found"])})
               != krow[k]["stratum"]]
        ck(not bad, "%s: the key's stratum column is not stratum() on %d item(s)"
           % (det, len(bad)))

    # N5 -- the labels ALREADY WRITTEN must still sit where the sheet puts them.
    # This is the check that discriminates a re-draw from a correct fresh draw:
    # a forgotten --pin-tranche produces a sheet that is internally consistent
    # and passes every check above, and the only witness that the sample moved
    # is the scan record itself.  Each label carries the scan_id and tranche it
    # was placed under.  npts / muon_len_cm are NOT compared: they are recorded
    # at label time and legitimately move with the fit (doc pdhd/15 sec 10,
    # 039252_15/77 188 -> 189 points).
    nlab = 0
    for lf in sorted(glob.glob(os.path.join(IMG, det, "work", "stm_michel_labels",
                                            "*", "labels.json"))):
        tag = os.path.basename(os.path.dirname(lf))
        try:
            with open(lf) as fh:
                d = json.load(fh)
        except Exception as e:                                   # noqa: BLE001
            ck(False, "%s: label file %s is unreadable: %s" % (det, lf, e))
            continue
        moved, absent = [], []
        for k, rec in sorted((d.get("labels") or {}).items()):
            ev, _, cl = k.partition("/")
            kk = (ev, int(cl))
            if kk not in srow:
                absent.append(k)
                continue
            nlab += 1
            if (int(rec.get("scan_id", -1)) != int(srow[kk]["scan_id"]) or
                    int(rec.get("tranche", -1)) != int(srow[kk]["tranche"])):
                moved.append("%s t%s->t%s id%s->%s"
                             % (k, rec.get("tranche"), srow[kk]["tranche"],
                                rec.get("scan_id"), srow[kk]["scan_id"]))
        ck(not moved,
           "%s tag %s: %d label(s) no longer sit where the sheet puts them -- the "
           "sample was RE-DRAWN under a scan in progress (doc pdhd/15 sec 10; "
           "re-prep with --pin-tranche): %s" % (det, tag, len(moved), moved[:3]))
        if absent:
            print("     note: %s tag %s: %d label(s) are not in the current sheet"
                  % (det, tag, len(absent)))
    if nlab:
        print("     %d existing label(s) still sit where the sheet puts them" % nlab)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", default=None, choices=["pdhd", "pdvd"])
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    dets = [a.det] if a.det else ["pdhd", "pdvd"]
    tmp = tempfile.mkdtemp(prefix="smx_selftest_", dir="/home/xqian/tmp")
    agree = {}
    try:
        for det in dets:
            print("\n===== %s =====" % det)
            test_geometry(det)
            test_reference(det)
            test_answer_on_screen(det, tmp)
            test_view(det, tmp)
            test_labels(det, tmp)
            test_pin(det, tmp)
            test_tranche_draw(det)
            test_scorer(det, tmp)
            test_meas_static(det)
            test_meas_app(det, tmp)
            test_pf_payload(det)
            test_pf_app(det, tmp)
            test_save_readback(det, tmp)
            test_bundle_app(det, tmp)
            test_kine_payload(det)
            test_kine_panel(det, tmp)
            test_object_payload(det)
            test_object_panel(det, tmp)
            test_energy_payload(det)
            if not a.quick:
                test_kine_gate(det)
                test_object_tree(det)
                test_object_spectrum(det)
                test_energy_scales(det)
                test_bundle_payload(det)
                test_meas_causal(det)
                test_pf_selector(det)
                test_image_split(det)
                agree[det] = test_unit_agreement(det, os.path.join(HERE, "prep-" + det))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks passed, %d failed" % (NPASS[0], len(FAILS)))
    for f in FAILS:
        print("  FAIL  %s" % f)
    if agree:
        print("wire-vs-geometric agreement: " +
              "  ".join("%s %.4f" % (k, v) for k, v in sorted(agree.items())))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
