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
  A  the payload's shape and the blind: the chain's answer lives under exactly
     one key, and with REVEAL off it reaches no ColumnDataSource -- proved by
     POISONING that key with values nothing else could produce and looking for
     them in every source on screen.
  B  REVEAL turns the answer on, and the audit field records which way round.
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smgeom                                                     # noqa: E402

IMG = os.path.dirname(os.path.dirname(HERE))
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


def test_blind(det, tmp):
    print("[A] the blind, %s" % det)
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
    ck(pick is not None, "%s: no payload with michel_found=1 to test the blind on" % det)
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
    # A2 -- poison the verdict and prove none of it reaches a source with REVEAL off
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
    ck(POISON not in vals,
       "%s: the poisoned verdict REACHED a data source with REVEAL off" % det)
    ck(not g["REND2"][("z", "y", "michel")].visible,
       "%s: the michel renderer is visible with REVEAL off" % det)
    ck(g["reveal_tog"].active is False, "%s: REVEAL does not start off" % det)
    ck(str(int(POISON)) not in g["seg_div"].text and "REVEALED" not in g["seg_div"].text,
       "%s: the PF segment panel shows the chain's pdg with REVEAL off" % det)
    ck("hidden" in g["reveal_div"].text,
       "%s: the reveal banner does not say the answer is hidden" % det)

    # B -- REVEAL turns it on, through on_change so a test can drive it
    print("[B] REVEAL, %s" % det)
    g["reveal_tog"].active = True
    vals = all_source_values(g)
    ck(POISON in vals, "%s: REVEAL did not bring the verdict onto the screen" % det)
    ck(g["REND2"][("z", "y", "michel")].visible,
       "%s: the michel renderer stayed hidden after REVEAL" % det)
    ck("REVEALED" in g["reveal_div"].text, "%s: no REVEALED banner" % det)
    g["michel_kind"].active = g["MICHEL_KINDS"].index("attached")
    g["set_label"]("STM_MICHEL")
    lab = json.load(open(g["LABEL_FILE"]))["labels"]
    k = list(lab)[0]
    ck(lab[k]["revealed_before_label"] is True,
       "%s: revealed_before_label not recorded as True" % det)
    g["reveal_tog"].active = False
    g["set_label"]("STM_ONLY")
    lab = json.load(open(g["LABEL_FILE"]))["labels"]
    ck(lab[k]["revealed_before_label"] is False,
       "%s: revealed_before_label not recorded as False" % det)
    return g


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
    for choice, spec in g["CHOICES"].items():
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

    # D4 -- with REVEAL on, every Michel/dot point sits on the NEGATIVE side
    g["reveal_tog"].active = True
    for nm in ("michel", "dots"):
        a = np.asarray(g["SRCQ"][nm].data["a"], float)
        ck(a.size == 0 or (a <= 0).all(),
           "%s: a %s point landed on the positive (muon) side of the panel" % (det, nm))
    g["reveal_tog"].active = False

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
    arm = {"pdhd": "d51hnu", "pdvd": "d51vnu"}[det]
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
    arm = {"pdhd": "d51hnu", "pdvd": "d51vnu"}[det]
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

    # H8 -- REVEAL gates the overlays here too
    for nm in ("michel", "delta", "dots"):
        ck(not g["SRCT"][("w", nm)].data["w"],
           "%s: the %s overlay is filled in measurement space with REVEAL off"
           % (det, nm))
        ck(all(not r.visible for r in g["MEAS_REND"][nm]),
           "%s: the %s measurement renderer is visible with REVEAL off" % (det, nm))
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
    g["reveal_tog"].active = True                    # so michel/dots are pickable
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
    arm = {"pdhd": "d51hnu", "pdvd": "d51vnu"}[det]
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
            test_blind(det, tmp)
            test_labels(det, tmp)
            test_pin(det, tmp)
            test_scorer(det, tmp)
            test_meas_static(det)
            test_meas_app(det, tmp)
            test_pf_payload(det)
            test_pf_app(det, tmp)
            test_save_readback(det, tmp)
            if not a.quick:
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
