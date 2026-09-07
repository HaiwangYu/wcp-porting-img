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

dQ/dx is normalised by `mip_dqdx_median` read from the per-event COMPILED
CONFIG `.wct-cfg-evt<ID>.json` (48000 in SBND production).  It is NOT read
from the calib dump's `meta.mip_dqdx_median`, which writes the C++ default
43000 and would inflate every ratio by 1.116 -- doc pr/148 sec 5.3.

Repro:
  ./pr148_scan/prep_pr148_scan.py            # defaults to the committed sheet
"""
import argparse, csv, glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)
DEF_SHEET = os.path.join(SX, "docs", "pr", "pr148-pidscan-manifest.tsv")
DEF_OUT = os.path.join(HERE, "prep")
ARM_TAG = "d145np"


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

    out = dict(
        idx=int(row["idx"]), sample=sample, run=row["run"], subrun=row["subrun"],
        event=int(evt), shower_id=sid, obj=obj,
        kine_charge_mev=float(row["kine_charge_mev"]),
        kine_best_mev=float(row["kine_best_mev"]),
        total_len_cm=float(row["total_len_cm"]),
        mip_used=mip, start=[round(c, 2) for c in V], far=far,
        far_dist_cm=round(far_d, 2), members=mem, others=oth)
    p = os.path.join(outdir, "pr148prep-evt%s-s%d.json" % (evt, sid))
    with open(p, "w") as fh:
        json.dump(out, fh)
    return p, len(mem), len(oth)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=DEF_SHEET)
    ap.add_argument("--outdir", default=DEF_OUT)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    for r in read_sheet(a.sheet):
        p, nm, no = build(r, a.outdir)
        print("idx %2s evt %-7s shower %-2s  members=%-3d others=%-3d  %s"
              % (r["idx"], r["event"], r["shower_id"], nm, no,
                 os.path.basename(p)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
