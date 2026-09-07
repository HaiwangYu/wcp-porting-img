#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 -- build the scan display's per-object payloads.

READ-ONLY apart from the files it writes under --outdir.

For every row of docs/pr/pr148-pidscan-manifest.tsv this reads the event's
calib dump out of work-<sample>-d145np/pr_evt<ID>/ and writes a compact
`pr148prep-evt<ID>-s<SHOWER>.json` carrying only what the three projection
panels draw.

WHAT IS DELIBERATELY NOT IN THE PAYLOAD, so it cannot reach the browser:
the A5 discriminants (growth / bragg / stem), the derived candidates
(n_heavy / f_heavy / star / stem_run), the A5 verdict, the stratum, the nue
BDT score, **the segment count** (doc sec 11: it became sec 8's discriminant,
so it left both the sheet and the screen) -- and also every segment's `particle_id`, `particle_score` and
`flag_shower`, which are the reconstruction's OWN typing answer.  The scanner
judges charge and geometry, which is what Bee shows; being told what the
reconstruction already decided makes the agreement circular
(feedback_blind_the_scan_sheet).  selftest_pr148_scan.py asserts the absence.

THE 3-D IMAGE (owner request, 2026-09-06: *"in addition to the best-fit
trajectory can you also overlay the 3D image on them"*).  Until now the display
drew only FIT points -- the reconstruction's trajectory samples -- so the
scanner was judging the fit, not the charge.  The image comes from
`mabc-pr.zip`, member `data/0/0-clustering-global.json`, the same 3-D charge
Bee draws (~64 k points on a typical event).

  image_near  every image point within IMAGE_NEAR_R of any member fit point,
              at FULL density.  This is the object's own charge and it is what
              the EM-vs-hadronic judgement is actually made on: a cone that
              opens, or a track that ends in a star.
  image_far   the rest of the event, thinned to at most IMAGE_FAR_MAX points,
              for context and containment.

Both selections are PURELY GEOMETRIC over all the charge in the event.  They
are deliberately NOT "the points the reconstruction assigned to this cluster":
that would draw the clustering decision, which is part of what the scan is
checking (feedback_retile_ident_is_not_bee_cluster_id -- an ident logged in one
stage is not the same id in another, and matching on it here would be both
wrong and leaky).

ONLY `clustering-global` is read.  The same archive carries
`shower_track-global`, whose `q` is the literal marker `15000.0` for
"the chain called this a shower" (MultiAlgBlobClustering.cxx:880, doc pr/67
sec 3.1) -- that is the reconstruction's own verdict and drawing it would hand
the scanner the answer.  The payload records which members were read in
`image_src`, and selftest_pr148_scan.py asserts that list is exactly
clustering-global.

dQ/dx is normalised by `mip_dqdx_median` read from the per-event COMPILED
CONFIG `.wct-cfg-evt<ID>.json` (48000 in SBND production).  It is NOT read
from the calib dump's `meta.mip_dqdx_median`, which writes the C++ default
43000 and would inflate every ratio by 1.116 -- doc pr/148 sec 5.3.

Repro:
  ./pr148_scan/prep_pr148_scan.py            # defaults to the committed sheet
"""
import argparse, csv, glob, json, math, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)
DEF_SHEET = os.path.join(SX, "docs", "pr", "pr148-pidscan-manifest.tsv")
DEF_OUT = os.path.join(HERE, "prep")
ARM_TAG = "d145np"
IMAGE_MEMBER = "data/0/0-clustering-global.json"
IMAGE_NEAR_R = 15.0     # cm; full density inside this of the trajectory
IMAGE_FAR_MAX = 8000    # thin the rest of the event to at most this many


def read_sheet(path):
    with open(path) as fh:
        lines = [l for l in fh if not l.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))


def mip_from_config(evtdir, evt):
    cfg = os.path.join(evtdir, ".wct-cfg-evt%s.json" % evt)
    if not os.path.exists(cfg):
        return None
    with open(cfg) as fh:
        for n in json.load(fh):
            d = n.get("data")
            if isinstance(d, dict) and n.get("type") == "TaggerCheckNeutrino" \
                    and "mip_dqdx_median" in d:
                return float(d["mip_dqdx_median"])
    return None


def load_image(evtdir, evt, mem):
    """(near, far, members_read) from mabc-pr.zip.  Geometric split only."""
    zp = os.path.join(evtdir, "mabc-pr.zip")
    if not os.path.exists(zp):
        return dict(x=[], y=[], z=[]), dict(x=[], y=[], z=[]), []
    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.endswith(IMAGE_MEMBER.split("/")[-1])]
        if not names:
            return dict(x=[], y=[], z=[]), dict(x=[], y=[], z=[]), []
        read = [names[0]]
        g = json.loads(z.read(names[0]))
    # Voxel hash, not the obvious double loop.  The image is ~64 k points and a
    # big object's trajectory is a few thousand, so pairwise is ~10^8 distance
    # checks per object in pure Python -- minutes each over 36 objects.  Binning
    # the trajectory at the search radius and probing the 27 neighbouring cells
    # makes it linear and needs no new dependency.
    R = IMAGE_NEAR_R
    R2 = R * R
    grid = {}
    for sg in mem:
        for a, b, c in zip(sg["x"], sg["y"], sg["z"]):
            grid.setdefault((int(a // R), int(b // R), int(c // R)),
                            []).append((a, b, c))
    NB = [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)]
    near = dict(x=[], y=[], z=[])
    fx, fy, fz = [], [], []
    for X, Y, Z in zip(g["x"], g["y"], g["z"]):
        cx, cy, cz = int(X // R), int(Y // R), int(Z // R)
        hit = False
        for di, dj, dk in NB:
            cell = grid.get((cx + di, cy + dj, cz + dk))
            if not cell:
                continue
            for a, b, c in cell:
                if (X - a) ** 2 + (Y - b) ** 2 + (Z - c) ** 2 < R2:
                    hit = True
                    break
            if hit:
                break
        if hit:
            near["x"].append(round(X, 1)); near["y"].append(round(Y, 1))
            near["z"].append(round(Z, 1))
        else:
            fx.append(X); fy.append(Y); fz.append(Z)
    st = max(1, -(-len(fx) // IMAGE_FAR_MAX))
    far = dict(x=[round(v, 1) for v in fx[::st]],
               y=[round(v, 1) for v in fy[::st]],
               z=[round(v, 1) for v in fz[::st]])
    return near, far, read


def build(row, outdir):
    sample, evt = row["sample"], row["event"]
    sid, obj = int(row["shower_id"]), int(row["obj"])
    evtdir = os.path.join(SX, "work-%s-%s" % (sample, ARM_TAG), "pr_evt%s" % evt)
    calib = os.path.join(evtdir, "calib-pr-evt%s.json" % evt)
    if not os.path.exists(calib):
        raise SystemExit("missing calib dump: %s" % calib)
    with open(calib) as fh:
        dump = json.load(fh)
    mip = mip_from_config(evtdir, evt)
    if not mip:
        raise SystemExit("no mip_dqdx_median in the compiled config for %s" % evt)

    showers = {s["shower_id"]: s for s in dump["showers"]}
    sh = showers[sid]
    if sh["id"] != obj:
        raise SystemExit("sheet obj %s != dump start segment %s (evt %s)"
                         % (obj, sh["id"], evt))
    verts = {v["id"]: v for v in dump["vertices"]}
    v0 = verts.get(sh["start_vertex_id"], {}).get("fit")
    if not v0:
        raise SystemExit("no fit position for start vertex of evt %s" % evt)
    V = (v0["x"], v0["y"], v0["z"])

    mem, oth, far, far_d = [], [], list(V), -1.0
    for s in dump["segments"]:
        pts = [p for p in s.get("points", []) if p.get("dx", 0) > 0]
        if not pts:
            continue
        is_mem = (s.get("shower_id") == sh["id"])
        rec = dict(id=s["id"], len=round(s["length"], 2),
                   x=[round(p["x"], 2) for p in pts],
                   y=[round(p["y"], 2) for p in pts],
                   z=[round(p["z"], 2) for p in pts])
        if is_mem:
            rec["mip"] = [round(p["dQ"] / p["dx"] / mip, 3) for p in pts]
            for p in pts:
                d = math.dist((p["x"], p["y"], p["z"]), V)
                if d > far_d:
                    far_d, far = d, [round(p["x"], 2), round(p["y"], 2),
                                     round(p["z"], 2)]
            mem.append(rec)
        else:
            oth.append(rec)

    img_near, img_far, img_src = load_image(evtdir, evt, mem)

    out = dict(
        idx=int(row["idx"]), sample=sample, run=row["run"], subrun=row["subrun"],
        event=int(evt), shower_id=sid, obj=obj,
        kine_charge_mev=float(row["kine_charge_mev"]),
        kine_best_mev=float(row["kine_best_mev"]),
        total_len_cm=float(row["total_len_cm"]),
        mip_used=mip, start=[round(c, 2) for c in V], far=far,
        far_dist_cm=round(far_d, 2), members=mem, others=oth,
        image_near=img_near, image_far=img_far, image_src=img_src)
    p = os.path.join(outdir, "pr148prep-evt%s-s%d.json" % (evt, sid))
    with open(p, "w") as fh:
        json.dump(out, fh)
    return p, len(mem), len(oth), len(img_near["x"]), len(img_far["x"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=DEF_SHEET)
    ap.add_argument("--outdir", default=DEF_OUT)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    for r in read_sheet(a.sheet):
        p, nm, no, inr, ifr = build(r, a.outdir)
        print("idx %2s evt %-7s shower %-2s  members=%-3d others=%-3d  "
              "image near=%-5d far=%-5d  %s"
              % (r["idx"], r["event"], r["shower_id"], nm, no, inr, ifr,
                 os.path.basename(p)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
