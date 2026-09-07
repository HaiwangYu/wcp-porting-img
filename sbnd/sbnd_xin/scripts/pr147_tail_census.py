#!/usr/bin/env python3
"""doc pr/147 round 2 -- the RECEIVER-SIDE bare tail.

177536's second muon node is not a cathode pair at all.  Its 279.6 cm bare
pdg-13 segment 17008 (vtx 17004->17005) shares vertex 17005 with segment 17009,
an 11.6 cm MEMBER of the muon shower the bridge just built.  It is the same
side of the cathode: the muon crosses, then keeps going.  The bare-chain BFS in
long_muon_cathode_bridge_pass walks only from the PARTNER (best->seg) and never
from the receiver's own far end, so it never reaches it.

This censuses the population that a receiver-side absorb would move: for every
|13|-typed shower, a bare (shower_id -1) segment that shares a graph vertex
with one of its members.  Reports pdg and length so the scope of a knob can be
argued from data rather than from 177536 alone.

Usage: pr147_tail_census.py --arms DIR:SAMPLE [...] [--min-len 20]
"""
import argparse, collections, glob, json, os, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True, metavar="DIR:SAMPLE")
    ap.add_argument("--min-len", type=float, default=20.0)
    ap.add_argument("--tsv", default=None)
    a = ap.parse_args()
    rows = []; nevt = 0; nmu_shw = 0
    for arm in a.arms:
        d, sample = arm.rsplit(":", 1)
        for f in sorted(glob.glob(os.path.join(d, "pr_evt*", "calib-pr-evt*.json"))):
            evt = os.path.basename(os.path.dirname(f))[len("pr_evt"):]
            try: J = json.load(open(f))
            except Exception: continue
            nevt += 1
            segs = J.get("segments") or []
            shws = {s.get("id"): s for s in J.get("showers") or []}
            # vertices touched by each shower's members
            mem_vtx = collections.defaultdict(set)
            for s in segs:
                sid = s.get("shower_id", -1)
                if sid == -1: continue
                mem_vtx[sid].add(s.get("start_vertex_id"))
                mem_vtx[sid].add(s.get("end_vertex_id"))
            for sid, vs in mem_vtx.items():
                sh = shws.get(sid)
                if not sh or abs(sh.get("particle_id", 0)) != 13: continue
                nmu_shw += 1
                for s in segs:
                    if s.get("shower_id", -1) != -1: continue          # bare only
                    if s.get("length", 0.0) < a.min_len: continue
                    if s.get("start_vertex_id") not in vs and \
                       s.get("end_vertex_id") not in vs: continue
                    rows.append((sample, evt, sh.get("shower_id"),
                                 round(sh.get("total_length", 0.0), 1),
                                 s.get("id"), abs(s.get("particle_id", 0)),
                                 round(s.get("length", 0.0), 1)))
    print("events: %d   |13|-typed showers: %d" % (nevt, nmu_shw))
    print("bare segments >= %.0f cm sharing a vertex with a muon shower's member: %d rows in %d events"
          % (a.min_len, len(rows), len({(r[0], r[1]) for r in rows})))
    by = collections.Counter(r[5] for r in rows)
    print("  by bare-segment pdg:", dict(by))
    mu = [r for r in rows if r[5] == 13]
    print("  of which pdg 13: %d rows in %d events" % (mu.__len__(),
          len({(r[0], r[1]) for r in mu})))
    for r in sorted(mu, key=lambda r: -r[6])[:25]:
        print("   %-6s %-8s shower %-7s (%6.1f cm)  <- bare seg %-6s pdg %-4d len %7.1f"
              % (r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
    if a.tsv:
        with open(a.tsv, "w") as fp:
            fp.write("sample\tevt\tshower_id\tshower_len\tbare_seg\tbare_pdg\tbare_len\n")
            for r in rows: fp.write("\t".join(str(x) for x in r) + "\n")
    return 0

if __name__ == "__main__": sys.exit(main())
