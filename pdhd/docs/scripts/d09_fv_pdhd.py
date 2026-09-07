#!/usr/bin/env python3
"""doc pdhd/09 -- PDHD geometry + PR-stage loaders for the exit-gap fiducial map.

The PDHD counterpart of pdvd/docs/nf_sp_img_clus/scripts/fv_curved_map.py's
geometry block plus fv_curved_{load,longloss,ab}.py's loaders.  Everything that
is detector-specific in doc pdvd/43's instrument lives here; the census and the
surface fit are otherwise the same algorithm.

Constants, and where each comes from -- none is inherited from PDVD:

  XW    357.985  the FV box's anode face, cfg/.../pdhd/pr.jsonnet:1258
                 (pdhd_pr_fv tail/head x).  The surface is built against the
                 volume it replaces, so this -- not the collection plane -- is
                 the plane the ray cast uses.
  XCOLL 353.1    where imaged charge actually stops: measured as the extreme
                 raw x per drift volume over a PR arm (APA0/2 min -353.2,
                 APA1/3 max +353.0).  XW - XCOLL = 4.9 cm is the plane stack,
                 and it is a PEDESTAL on the anode control -- PDVD had none
                 because its FV bound and sensvol anode were the same 339.91.
  YLO/YHI 7.61 / 606.0     pr.jsonnet:1259-1260, the ACTIVE volume (the
  ZLO/ZHI 0.234345 / 462.297   clustering FV's 15 cm inset is NOT in the box)
  CATH  2.54     per-face FV_xmax, clus.jsonnet:84 (a0f0pA -25.4 mm).  PDHD's
                 box spans the CPA continuously, so the cathode is NOT a
                 boundary plane -- a cathode crosser is not an exiter at x=0.

  RAW_EARLY 353.1  tick 0 == the anode plane, in the RAW readout frame
  RAW_LATE  119.2  the far window edge
                 Both MEASURED from the pctree raw x extremes, not derived.
                 Cross-check: 353.1 + 119.2 = 472.3 cm span vs 5999 ticks x
                 0.5 us x 0.1576 cm/us = 472.7 cm.  Agrees to 0.4 cm, which
                 confirms nticks 5999 and the calibrated 1.576 mm/us together.

  side = -1 for APA 0,2 (x<0, group02); +1 for APA 1,3 (x>0, group13).
                 Decoded as (wpid >> 4) & 3, verified on a PR arm: APA0/2 carry
                 raw x in [-353.2, +119.0], APA1/3 in [-119.5, +353.0].
                 Use the ANODE GROUP, never sign(x): after t0 correction a
                 point from one anode can land at the other sign (doc 41).
"""
import io, json, os, re, tarfile, zipfile
from collections import defaultdict
import numpy as np

XW    = 357.985
XCOLL = 353.1
YLO, YHI = 7.61, 606.0
ZLO, ZHI = 0.234345, 462.297
CATH  = 2.54
RAW_EARLY, RAW_LATE, RAW_EDGE_TOL = 353.1, 119.2, 5.0

WALLS = ["y+", "y-", "z-", "z+"]
VOLS  = ["g02", "g13"]                      # x<0 (APA0/2), x>0 (APA1/3)
# the eight profile keys, in curved_fiducial_profiles.jsonnet order
JNAME = [f"{w}_{v}" for w in ("yp", "ym", "zm", "zp") for v in VOLS]
# four ~84 cm drift bins per volume, cathode face -> anode face (PDVD: 80 cm)
BIN_EDGES = [CATH, 84.0, 168.0, 252.0, XW]
HALF_X = 180.0                              # |x| below this = cathode half

NORMAL = {"y+": np.array([0, 1., 0]), "y-": np.array([0, -1., 0]),
          "z-": np.array([0, 0, -1.]), "z+": np.array([0, 0, 1.]), "anode": None}


def wall_dist(w, y, z):
    """Perpendicular distance from a point to a nominal transverse wall, > 0 inside."""
    return {"y+": YHI - y, "y-": y - YLO, "z-": z - ZLO, "z+": ZHI - z}[w]


def vol_of(side):
    return "g02" if side < 0 else "g13"


def first_exit(e, u):
    """The first of the six boundary planes the ray e + t*u (t >= 0) crosses.

    An end already AT or BEYOND a plane it heads out of (signed gap <= 0 -- the
    imaged charge reaches or overshoots the wall) is an immediate hit at t = 0;
    without that clamp such an end is handed to the next plane along the ray,
    hundreds of cm away.  Returns (wall, t_path, signed perpendicular gap).

    Unlike PDVD, PDHD's y walls are NOT symmetric about 0, so the pair is
    (YHI, +1) / (YLO, -1) rather than (+YW, +1) / (-YW, -1).
    """
    cands = []
    for w, ax, pos, n in (("y+", 1, YHI, 1), ("y-", 1, YLO, -1),
                          ("z-", 2, ZLO, -1), ("z+", 2, ZHI, 1),
                          ("anode", 0, XW, 1), ("anode", 0, -XW, -1)):
        un = u[ax] * n
        if un < 1e-9:
            continue                          # heading away from this plane
        g = (pos - e[ax]) * n                 # signed gap, > 0 inside the plane
        cands.append((max(g / un, 0.0), w, g))
    if not cands:
        return None
    t, w, g = min(cands)
    return w, float(t), float(g)


# --------------------------------------------------------------------------- IO

def bee_points(workdir):
    """The PR stage's clustering-global layer: t0-corrected points, in cm."""
    z = zipfile.ZipFile(os.path.join(workdir, "mabc-pr.zip"))
    for n in z.namelist():
        if n.endswith("-clustering-global.json"):
            d = json.loads(z.read(n))
            return (np.column_stack([d["x"], d["y"], d["z"]]).astype(float),
                    np.asarray(d["q"], float), np.asarray(d["cluster_id"], int),
                    int(d["runNo"]), int(d["eventNo"]))
    raise RuntimeError("no clustering-global layer in " + workdir)


def load_pct(tgz, want):
    out = {}
    with tarfile.open(tgz, "r:gz") as tf:
        members = {m.name: m for m in tf.getmembers()}
        for name, m in members.items():
            if not name.endswith("_metadata.json"):
                continue
            md = json.load(io.BytesIO(tf.extractfile(m).read()))
            if md.get("datatype") != "pcarray":
                continue
            dp = md.get("datapath", "")
            if not want(dp):
                continue
            an = name.replace("_metadata.json", "_array.npy")
            if an in members:
                out[dp] = np.load(io.BytesIO(tf.extractfile(members[an]).read()))
    return out


def event_points(workdir):
    """Bee points (t0-corrected cm) + the matching RAW readout x and drift side.

    The Bee layer is a re-partition of the pctree in a DIFFERENT order, so the
    raw x is attached by k-d match on (x_t0cor, y, z) rather than by index.
    """
    from scipy.spatial import cKDTree
    P, Q, C, run, evt = bee_points(workdir)
    tgz = [f for f in os.listdir(workdir) if re.match(r"pctree-evt\d+\.tar\.gz$", f)]
    if not tgz:
        raise RuntimeError("no pctree in " + workdir)
    tgz = os.path.join(workdir, tgz[0])
    d = load_pct(tgz, lambda p: "/namedpcs/3d/arrays/" in p
                 and p.rsplit("/", 1)[-1] in ("x", "x_t0cor", "y", "z", "wpid"))
    g = lambda n: [v for k, v in d.items() if k.endswith("/arrays/" + n)][0]
    xraw, xcor, py, pz = g("x") / 10.0, g("x_t0cor") / 10.0, g("y") / 10.0, g("z") / 10.0
    apa = (g("wpid") >> 4) & 3
    side = np.where((apa % 2) == 0, -1, 1).astype(np.int8)   # APA0/2 = x<0
    phys = np.abs(P[:, 0]) < 1e4                             # drop t0 = -1e12 sentinels
    pp = np.abs(xcor) < 1e4
    tree = cKDTree(np.column_stack([xcor[pp], py[pp], pz[pp]]))
    dist, idx = tree.query(P[phys], k=1)
    xr = np.full(len(P), np.nan); sd = np.zeros(len(P), np.int8)
    xr[phys] = xraw[pp][idx]; sd[phys] = side[pp][idx]
    return dict(P=P, q=Q, cid=C, xraw=xr, side=sd, phys=phys, run=run, evt=evt,
                match_max_cm=float(dist.max()) if len(dist) else 0.0)


RE_TGM      = re.compile(r"TaggerCheckTGM: cluster (\d+) . TGM=(true|false)")
RE_STM      = re.compile(r"TaggerCheckSTM: cluster (\d+) . STM=(\d) TGM=(\d)")
RE_STM_SKIP = re.compile(r"TaggerCheckSTM: cluster (\d+) already TGM; skipping")
RE_FC       = re.compile(r"TaggerCheckFC: cluster (\d+) . FC=(true|false)")


def read_arm(pdhd, tag, logglob="wct_pr_*.log"):
    """{(run, idx): {cluster: {'tgm','stm','fc','stm_skipped'}}} from the taggers'
    OWN per-cluster verdict lines.  Never a line count: TaggerCheckSTM emits a
    second shape ("already TGM; skipping") for clusters it never evaluates."""
    import glob
    out = {}
    for d in sorted(glob.glob(os.path.join(pdhd, "work", f"*_{tag}"))):
        base = os.path.basename(d)
        parts = base.split("_")
        run, idx = parts[0], parts[1]
        logs = glob.glob(os.path.join(d, logglob))
        if not logs:
            continue
        ev = defaultdict(lambda: dict(tgm=None, stm=None, fc=None, stm_skipped=False))
        with open(logs[0], errors="replace") as f:
            for line in f:
                if "TaggerCheck" not in line:
                    continue
                m = RE_TGM.search(line)
                if m:
                    ev[int(m.group(1))]["tgm"] = (m.group(2) == "true"); continue
                m = RE_STM.search(line)
                if m:
                    ev[int(m.group(1))]["stm"] = (m.group(2) == "1"); continue
                m = RE_STM_SKIP.search(line)
                if m:
                    ev[int(m.group(1))]["stm_skipped"] = True; continue
                m = RE_FC.search(line)
                if m:
                    ev[int(m.group(1))]["fc"] = (m.group(2) == "true")
        out[(run, idx)] = dict(ev)
    return out
