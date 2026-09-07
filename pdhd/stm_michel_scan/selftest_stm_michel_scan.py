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
    out = []
    for s in list(g["SRC2"].values()) + list(g["SRC3"].values()) + list(g["SRCQ"].values()):
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
                     q=[POISON] * k, seg=[0] * k)
    for key in ("stop_x", "stop_y", "stop_z", "entry_x", "entry_y", "entry_z",
                "tagger_stop_x", "tagger_stop_y", "tagger_stop_z"):
        v[key] = POISON
    v["tagger_fit"] = [dict(pass_=0, x=[POISON], y=[POISON], z=[POISON],
                            rr=[POISON], dqdx=[POISON])]
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
    for choice, spec in g["CHOICES"].items():
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
            if not a.quick:
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
