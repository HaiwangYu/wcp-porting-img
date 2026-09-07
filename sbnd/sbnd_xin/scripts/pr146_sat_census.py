#!/usr/bin/env python3
"""doc sbnd_xin/pr/146 -- census of kine_drop_stray_satellites decisions.

READ-ONLY.  Writes nothing but the file named by --tsv.

Parses the `kine_sat DROP` / `kine_sat census:` lines that
NeutrinoKinematics.cxx already emits (doc pr/92 classifier, arms A/B/C/E)
out of a finished arm, and joins each dropped shower to its record in the
per-event calib dump so the energy quoted is the SAME quantity the leftover
shower loop would have pushed (`showers[].kine_best`, NeutrinoKinematics.cxx
:598) rather than the log line's rounded `E=`.

Which log file: `wct_pr_evt<ID>.log` ONLY.  `stdout.log` in the same
directory carries the identical lines, so a `*.log` glob double-counts every
drop -- the same trap pr145_pointing_census.py documents.

Join key: the drop line's `id=` is `shower->get_shower_id()`, which is the
calib dump's `showers[].shower_id` (a compact per-event index), NOT
`showers[].id` (the start segment id).

Repro:
  ./pr146_sat_census.py --arm work-mcp1k-d145np --arm work-mcp2k-d145np \
      --tsv ../docs/pr/pr146-sat-census.tsv
"""
import argparse, glob, json, os, re, sys

DROP_RE = re.compile(
    r'kine_sat DROP id=(?P<sid>\d+) arm=(?P<arm>\S+) E=(?P<E>[\d.]+) '
    r'conn=(?P<conn>\d+) d_sv=(?P<d_sv>[-\d.]+) ang_sv=(?P<ang_sv>[-\d.]+) '
    r'in_main=(?P<in_main>\w+) d_mv=(?P<d_mv>[-\d.]+) ang_mv=(?P<ang_mv>[-\d.]+) '
    r'cont=(?P<cont>\w+) track=(?P<track>\w+)')
CENSUS_RE = re.compile(r'kine_sat census: candidates=(\d+) dropped=(\d+)')

COLS = ["sample", "event", "arm", "shower_id", "seg_id", "pdg", "e_logline_mev",
        "kine_best_mev", "start_seg_len_cm", "binding_gate", "conn", "d_sv_cm",
        "ang_sv_deg", "in_main", "d_mv_cm", "ang_mv_deg", "cont", "track",
        "n_candidates", "n_dropped"]


def load_calib(evtdir, evt):
    p = os.path.join(evtdir, "calib-pr-evt%s.json" % evt)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="work-<sample>-<TAG> directory; repeatable")
    ap.add_argument("--tsv", required=True)
    args = ap.parse_args()

    rows = []
    per_arm = {}
    for arm in args.arm:
        sample = os.path.basename(arm.rstrip("/")).split("-")[1]
        n_drop = n_evt = 0
        for evtdir in sorted(glob.glob(os.path.join(arm, "pr_evt*"))):
            evt = os.path.basename(evtdir)[len("pr_evt"):]
            log = os.path.join(evtdir, "wct_pr_evt%s.log" % evt)
            if not os.path.exists(log):
                continue
            n_evt += 1
            with open(log, errors="replace") as fh:
                text = fh.read()
            drops = list(DROP_RE.finditer(text))
            if not drops:
                continue
            cen = CENSUS_RE.search(text)
            n_cand, n_drp = (cen.group(1), cen.group(2)) if cen else ("", "")
            calib = load_calib(evtdir, evt)
            segs = {s["id"]: s for s in calib["segments"]} if calib else {}
            shws = {s["shower_id"]: s for s in calib["showers"]} if calib else {}
            for m in drops:
                n_drop += 1
                sid = int(m.group("sid"))
                sh = shws.get(sid)
                seg_id = sh["id"] if sh else ""
                pdg = sh["particle_id"] if sh else ""
                kbest = "%.2f" % sh["kine_best"] if sh else ""
                sl = segs.get(seg_id, {}).get("length") if sh else None
                # NeutrinoKinematics.cxx:611-633 -- binding energy is added only
                # for nucleon-typed showers whose START SEGMENT exceeds 5 cm.
                if sh and abs(int(pdg)) in (2212, 2112) and sl is not None:
                    gate = "fires" if sl > 5.0 else "under5cm"
                else:
                    gate = "n/a"
                rows.append(dict(
                    sample=sample, event=evt, arm=m.group("arm"), shower_id=sid,
                    seg_id=seg_id, pdg=pdg, e_logline_mev=m.group("E"),
                    kine_best_mev=kbest,
                    start_seg_len_cm=("%.2f" % sl) if sl is not None else "",
                    binding_gate=gate, conn=m.group("conn"),
                    d_sv_cm=m.group("d_sv"), ang_sv_deg=m.group("ang_sv"),
                    in_main=m.group("in_main"), d_mv_cm=m.group("d_mv"),
                    ang_mv_deg=m.group("ang_mv"), cont=m.group("cont"),
                    track=m.group("track"), n_candidates=n_cand, n_dropped=n_drp))
        per_arm[arm] = (n_evt, n_drop)

    rows.sort(key=lambda r: (r["arm"], -float(r["kine_best_mev"] or r["e_logline_mev"])))
    with open(args.tsv, "w") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in COLS) + "\n")

    for arm, (n_evt, n_drop) in per_arm.items():
        print("%-28s %5d events scanned, %3d drops" % (arm, n_evt, n_drop))
    print("\nby arm:")
    tot = {}
    for r in rows:
        a = r["arm"]
        e = float(r["kine_best_mev"] or r["e_logline_mev"])
        tot.setdefault(a, [0, 0.0])
        tot[a][0] += 1
        tot[a][1] += e
    for a in sorted(tot):
        print("  %-8s n=%-4d sum=%9.1f MeV" % (a, tot[a][0], tot[a][1]))
    print("\nwrote %s (%d rows)" % (args.tsv, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
