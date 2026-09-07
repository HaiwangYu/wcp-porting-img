#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 -- census of the A5 hadronic-shower tag's decisions.

READ-ONLY.  Writes nothing but the file named by --tsv.

Parses the `A5 hadronic census:` / `A5 hadronic retype:` lines that
NeutrinoShowerClustering.cxx:9950-9967 already emits for EVERY evaluated
conn-1 |pdg|=11 shower (doc pr/99 round 3, `shower_hadronic_tag`), out of a
finished arm, and joins each shower to its record in the per-event calib
dump.  So a knob-on arm is its own calibration sample and no reprocessing is
needed -- the design note says exactly that
(NeutrinoPatternBase.h:2054-2055, "the offline calibration channel").

The join adds, per shower, the geometry the log line does NOT carry and the
dump does:

  start_*     the start segment (dump `showers[].id` = pf_node_id of the
              start segment): length, particle_id, particle_score,
              flag_shower.  A start segment longer than 20 cm cannot have
              got pdg 11 from the template PID -- `segment_do_track_pid`
              gates the electron hypothesis at `length < 20*units::cm`
              (PRSegmentFunctions.cxx:2743) -- so pdg 11 there came from a
              reclassification site.
  n_heavy /   short (2-25 cm) member prongs whose median dQ/dx is >= 2.0 MIP,
  f_heavy     and their share of the member length.  `mip_dqdx_median` comes
              from the dump's own `meta`, never a hardcoded 43000.
  star        the largest number of those prongs sharing one graph vertex,
              and that vertex's distance from the shower start vertex.
  stem_run    radial distance from the start vertex over which the member
              set is a SINGLE segment.

  A SECOND trap, measured here: the calib dump's `meta.mip_dqdx_median`
  writes the C++ DEFAULT 43000, not the value the job ran with.  SBND
  production sets `mip_dqdx_median = 48000`
  (cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet; confirmed in every one
  of the 3067 per-event `.wct-cfg-evt<ID>.json`).  Normalising by the dump's
  meta therefore inflates every MIP ratio by 48/43 = 1.116, which is enough to
  move a prong across a 2.0-MIP bar.  This script reads the MIP from the
  COMPILED CONFIG and records the dump's claim beside it in `mip_meta`.

  A WARNING that cost this round a hypothesis: the dump's `points[]` are FIT
  points -- near-evenly-spaced trajectory samples, NOT charge.  Counting them
  per bin measures how many segments are present, not how dense the charge
  is, which is why `n_lead` reads ~11 for essentially every shower.  A5's own
  `growth` is computed from IMAGED points in a cylinder and has no offline
  equivalent.  Do not build a density discriminant on this file.

Which log file: `wct_pr_evt<ID>.log` ONLY.  `stdout.log` in the same
directory carries the identical lines, so a `*.log` glob double-counts every
shower -- the same trap pr145_pointing_census.py and pr146_sat_census.py
document.

Join key: the census line's `id=` is `shower->get_shower_id()`, a compact
per-event index = the dump's `showers[].shower_id`, NOT `showers[].id`
(which is the start segment id).

Repro:
  ./pr148_a5_census.py --arm work-mcp1k-d145np --arm work-mcp2k-d145np \
      --arm work-nuecc48-d145np --arm work-ncpi0-d145np \
      --tsv ../docs/pr/pr148-a5-census.tsv
"""
import argparse, glob, json, math, os, re, statistics as st, sys
from collections import defaultdict

CENSUS_RE = re.compile(
    r'A5 hadronic census: shower id=(?P<sid>\d+) pdg=(?P<pdg>-?\d+) '
    r'conn=(?P<conn>\d+) nseg=(?P<nseg>\d+) smax=(?P<smax>[\d.]+)cm '
    r'growth=(?P<growth>[-\d.]+) n_early=(?P<n_early>[\d.]+) '
    r'n_late=(?P<n_late>[\d.]+) dqdx_trunk=(?P<trunk>[-\d.]+) '
    r'dqdx_term=(?P<term>[-\d.]+) bragg=(?P<bragg>[-\d.]+) '
    r'stem=(?P<stem>[-\d.]+) verdict=(?P<verdict>\d)')
RETYPE_RE = re.compile(
    r'A5 hadronic retype: shower id=(?P<sid>\d+) start_seg len=(?P<len>[\d.]+)cm')
TAG_RE = re.compile(
    r'tagger: nue_score (?P<nue>[-\d.]+) numu_score (?P<numu>[-\d.]+).*?Enu (?P<enu>[\d.]+)')

BINW = 3.0            # same bin as A5's own m_shower_hadronic_bin default
HEAVY_MIP = 2.0       # a prong at/above this median dQ/dx is heavily ionising
HEAVY_LO, HEAVY_HI = 2.0, 25.0   # cm; "short prong" window

COLS = ["sample", "event", "shower_id", "start_seg", "verdict", "pdg", "conn",
        "nseg_census", "nseg_final", "smax_cm", "growth", "n_early", "n_late",
        "dqdx_trunk", "dqdx_term", "bragg", "stem_mip", "retype_start_len_cm",
        "kine_best_mev", "kine_charge_mev", "kine_dQdx_mev", "kine_range_mev",
        "total_len_cm", "start_len_cm", "start_pdg", "start_score",
        "start_flag_shower", "n_heavy", "len_heavy_cm", "f_heavy", "max_mip",
        "star_n", "star_dist_cm", "stem_run_cm", "n_lead_fitpts",
        "mip_used", "mip_meta", "nue_score", "numu_score", "enu_mev"]


def mip_from_config(evtdir, evt):
    """m_mip_dqdx_median as the job actually ran it.  The calib dump's
    meta.mip_dqdx_median is the C++ default (43000) and is NOT this."""
    cfg = os.path.join(evtdir, ".wct-cfg-evt%s.json" % evt)
    if not os.path.exists(cfg):
        return None
    with open(cfg) as fh:
        nodes = json.load(fh)
    for n in nodes:
        d = n.get("data")
        if isinstance(d, dict) and n.get("type") == "TaggerCheckNeutrino" \
                and "mip_dqdx_median" in d:
            return float(d["mip_dqdx_median"])
    return None


def seg_median_mip(seg, mip):
    v = [p["dQ"] / p["dx"] for p in seg.get("points", []) if p.get("dx", 0) > 0]
    return st.median(v) / mip if v else -1.0


def census_one_event(sample, evt, logpath, calibpath, mip_cfg):
    """One event -> list of row dicts.  Returns [] if the event has no A5 line."""
    with open(logpath, errors="ignore") as fh:
        txt = fh.read()
    hits = list(CENSUS_RE.finditer(txt))
    if not hits:
        return []
    retype_len = {m.group("sid"): float(m.group("len"))
                  for m in RETYPE_RE.finditer(txt)}
    tg = TAG_RE.search(txt)
    nue = float(tg.group("nue")) if tg else None
    numu = float(tg.group("numu")) if tg else None
    enu = float(tg.group("enu")) if tg else None

    dump = None
    if calibpath and os.path.exists(calibpath):
        with open(calibpath) as fh:
            dump = json.load(fh)

    rows = []
    for m in hits:
        r = {c: "" for c in COLS}
        r.update(sample=sample, event=evt, shower_id=m.group("sid"),
                 verdict=m.group("verdict"), pdg=m.group("pdg"),
                 conn=m.group("conn"), nseg_census=m.group("nseg"),
                 smax_cm=m.group("smax"), growth=m.group("growth"),
                 n_early=m.group("n_early"), n_late=m.group("n_late"),
                 dqdx_trunk=m.group("trunk"), dqdx_term=m.group("term"),
                 bragg=m.group("bragg"), stem_mip=m.group("stem"),
                 retype_start_len_cm=retype_len.get(m.group("sid"), ""),
                 nue_score=("" if nue is None else nue),
                 numu_score=("" if numu is None else numu),
                 enu_mev=("" if enu is None else enu))
        if dump is not None:
            join_dump(r, dump, int(m.group("sid")), mip_cfg)
        rows.append(r)
    return rows


def join_dump(r, dump, sid, mip_cfg):
    showers = {s["shower_id"]: s for s in dump.get("showers", [])}
    sh = showers.get(sid)
    if sh is None:
        return
    mip_meta = dump.get("meta", {}).get("mip_dqdx_median", 0) or 0
    mip = mip_cfg if mip_cfg else mip_meta
    r["mip_used"] = mip
    r["mip_meta"] = mip_meta
    segs = dump.get("segments", [])
    byid = {s["id"]: s for s in segs}
    verts = {v["id"]: v for v in dump.get("vertices", [])}

    r.update(start_seg=sh["id"], nseg_final=sh["num_segments"],
             kine_best_mev=round(sh["kine_best"], 3),
             kine_charge_mev=round(sh["kine_charge"], 3),
             kine_dQdx_mev=round(sh["kine_dQdx"], 3),
             kine_range_mev=round(sh["kine_range"], 3),
             total_len_cm=round(sh["total_length"], 3))
    ss = byid.get(sh["id"])
    if ss is not None:
        r.update(start_len_cm=round(ss["length"], 3), start_pdg=ss["particle_id"],
                 start_score=ss["particle_score"],
                 start_flag_shower=int(bool(ss["flag_shower"])))
    if mip <= 0:
        return

    mem = [s for s in segs if s.get("shower_id") == sh["id"]]
    heavy, l_heavy, l_tot, mx = [], 0.0, 0.0, 0.0
    vhit = defaultdict(set)
    for s in mem:
        med, L = seg_median_mip(s, mip), s["length"]
        l_tot += L
        mx = max(mx, med)
        if med >= HEAVY_MIP and HEAVY_LO <= L <= HEAVY_HI:
            heavy.append(s)
            l_heavy += L
            vhit[s["start_vertex_id"]].add(s["id"])
            vhit[s["end_vertex_id"]].add(s["id"])
    r.update(n_heavy=len(heavy), len_heavy_cm=round(l_heavy, 3),
             f_heavy=round(l_heavy / l_tot, 4) if l_tot > 0 else "",
             max_mip=round(mx, 3))

    star_n, star_v = 0, None
    for vid, ids in sorted(vhit.items()):
        if len(ids) > star_n:
            star_n, star_v = len(ids), vid
    r["star_n"] = star_n

    v0 = verts.get(sh["start_vertex_id"])
    if not v0 or "fit" not in v0:
        return
    V = (v0["fit"]["x"], v0["fit"]["y"], v0["fit"]["z"])
    if star_v is not None and star_v in verts and "fit" in verts[star_v]:
        f = verts[star_v]["fit"]
        r["star_dist_cm"] = round(math.dist((f["x"], f["y"], f["z"]), V), 2)

    cnt, nsg = defaultdict(int), defaultdict(set)
    for s in mem:
        for p in s.get("points", []):
            b = int(math.dist((p["x"], p["y"], p["z"]), V) / BINW)
            cnt[b] += 1
            nsg[b].add(s["id"])
    if not cnt:
        return
    run = 0.0
    for b in range(0, max(cnt) + 1):
        if cnt.get(b, 0) > 0 and len(nsg.get(b, set())) <= 1:
            run = (b + 1) * BINW
        else:
            break
    r["stem_run_cm"] = run
    r["n_lead_fitpts"] = cnt.get(0, 0) + cnt.get(1, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="work-<sample>-<tag> dir; repeatable")
    ap.add_argument("--tsv", required=True)
    a = ap.parse_args()

    rows = []
    for arm in a.arm:
        sample = os.path.basename(arm.rstrip("/")).split("-")[1]
        for d in sorted(glob.glob(os.path.join(arm, "pr_evt*"))):
            m = re.search(r"pr_evt(\d+)$", d)
            if not m:
                continue
            evt = m.group(1)
            lg = os.path.join(d, "wct_pr_evt%s.log" % evt)
            if not os.path.exists(lg):
                continue
            rows += census_one_event(sample, evt, lg,
                                     os.path.join(d, "calib-pr-evt%s.json" % evt),
                                     mip_from_config(d, evt))

    with open(a.tsv, "w") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in COLS) + "\n")

    n_ret = sum(1 for r in rows if r["verdict"] == "1")
    n_joined = sum(1 for r in rows if r["start_seg"] != "")
    print("A5 census: %d shower(s) in %d event(s); %d re-typed; %d joined to a dump"
          % (len(rows), len({(r["sample"], r["event"]) for r in rows}), n_ret, n_joined))
    print("wrote %s" % a.tsv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
