#!/usr/bin/env python3
"""doc pr/147 -- turn the pr147_cathode_census.py pair table into the owner's
candidate list, and name the ONE shipped cut that holds each candidate out.

Why a second script: the census records, per candidate pair, the FIRST guard
that rejects it, in the pass's own order.  That order puts the type guards
above the geometry gates, so a row whose verdict is `receiver_type` /
`partner_type` never had its gap or angles tested -- it can carry a 105 cm gap
and still be listed.  Filtering the census output therefore has to re-apply the
geometry cuts explicitly; doing it inline in a shell one-liner is how an
earlier pass of this analysis published a 9-row table containing two pairs
105 cm apart.

De-duplication mirrors production, not convenience: `long_muon_cathode_bridge_pass`
picks its partner with a best-gap MINIMISER over admissible candidates
(TaggerCheckNeutrino.cxx:1456), so among the four end-orientations of one
segment pair we keep the angle-passing row with the smallest gap, and only if
none passes do we fall back to the smallest gap overall.  Keeping the
longest-receiver row instead -- the obvious choice -- silently dropped 347890,
whose good orientation (gap 14.3, a_tan 7.1) loses to its bad one (gap 30.6,
a_tan 171.5).

SHIPPED = the SBND production operating point (wct-pr-perevt.jsonnet:2235-2247).

Usage: pr147_adjudicate.py CENSUS_DIR [--min-long 20] [--min-short 3]
"""
import argparse, collections, csv, os, sys

SHIPPED = dict(xcut=6.0, gap=20.0, angle=25.0, min_len=5.0)
CATHODE_X = 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("census_dir")
    ap.add_argument("--min-long", type=float, default=20.0,
                    help="one side must be at least this long to matter [cm]")
    ap.add_argument("--min-short", type=float, default=3.0)
    a = ap.parse_args()
    R = list(csv.DictReader(open(os.path.join(a.census_dir, "pr147-cathode-pairs.tsv")),
                            delimiter="\t"))
    F = lambda r, k: float(r[k])
    ang_ok = lambda r: 0 <= F(r, "a_gap_deg") <= SHIPPED["angle"] and \
                       0 <= F(r, "a_tan_deg") <= SHIPPED["angle"]

    best = {}
    for r in R:
        k = (r["sample"], r["evt"], r["pair_key"])
        rank = (0 if ang_ok(r) else 1, F(r, "gap_cm"))
        if k not in best or rank < best[k][0]: best[k] = (rank, r)
    D = [v[1] for v in best.values()]

    out = []
    for r in D:
        if not ang_ok(r): continue
        # The far ends must straddle the cathode.  This is re-applied HERE and
        # not taken from the verdict because the census stops at the FIRST
        # failing guard and the type guards sit above this one -- so a pair
        # that is not a cathode crosser at all can still be recorded as
        # `receiver_type`.  394796 is why this line exists: both halves span
        # x = +1.7..+36.8, entirely on one side, and it survived an earlier
        # draft of this table as a candidate until the C++ refused to bridge it.
        if (F(r, "recv_far_x") - CATHODE_X) * (F(r, "partner_far_x") - CATHODE_X) > 0:
            continue
        lo, hi = sorted((F(r, "recv_len"), F(r, "partner_len")))
        if hi < a.min_long or lo < a.min_short: continue
        # which SHIPPED cut, if any, holds this pair out?
        held = []
        if F(r, "gap_cm") >= SHIPPED["gap"]: held.append("gap>=%g" % SHIPPED["gap"])
        if abs(F(r, "recv_end_x")) >= SHIPPED["xcut"] or \
           abs(F(r, "partner_end_x")) >= SHIPPED["xcut"]:
            held.append("xcut>=%g" % SHIPPED["xcut"])
        if lo < SHIPPED["min_len"]: held.append("min_len<%g" % SHIPPED["min_len"])
        if r["verdict"] in ("receiver_type", "receiver_seg_type", "partner_type"):
            held.append(r["verdict"])
        out.append((r, held))

    out.sort(key=lambda t: -min(F(t[0], "recv_len"), F(t[0], "partner_len")))
    h = ("%-6s %-8s %-8s %6s %6s %6s | %-6s %6s %6s %6s | %5s %5s %5s %6s %6s | %s")
    print(h % ("sample", "evt", "verdict", "rlen", "rdqdx", "rstr", "pkind",
               "plen", "pdqdx", "pstr", "gap", "agap", "atan", "recv_x", "part_x",
               "held out by"))
    for r, held in out:
        print(h % (r["sample"], r["evt"], r["verdict"], r["recv_len"],
                   r["recv_dqdx_mip"], r["recv_straight"], r["partner_kind"],
                   r["partner_len"], r["partner_dqdx_mip"], r["partner_straight"],
                   r["gap_cm"], r["a_gap_deg"], r["a_tan_deg"],
                   r["recv_end_x"], r["partner_end_x"],
                   ", ".join(held) if held else "NOTHING (would bridge)"))
    print()
    print("candidate pairs: %d in %d events" % (out.__len__(),
          len({(r["sample"], r["evt"]) for r, _ in out})))
    c = collections.Counter(hh for _, held in out for hh in (held or ["none"]))
    print("binding cuts:", dict(c))
    return 0

if __name__ == "__main__": sys.exit(main())
