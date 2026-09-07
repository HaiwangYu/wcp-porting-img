#!/usr/bin/env python3
"""doc sbnd_xin/pr/148 -- the radial profile of ONE A5-evaluated shower.

READ-ONLY; prints, writes nothing.

Reproduces, from the calib dump, the two quantities A5's verdict turns on
(NeutrinoShowerClustering.cxx:9840-9948) at the same 3 cm binning, plus the
one thing the log line cannot show: WHERE along the trajectory the member
multiplicity rises.

Two honest caveats, both measured in doc pr/148:

  * the population column counts FIT points, which are near-evenly-spaced
    trajectory samples.  A5's own `growth` counts IMAGED points inside an
    8 cm cylinder with an ownership filter, and has no offline equivalent.
    Read the `nseg` column, not the `npts` column, as the shape signal.
  * the dQ/dx column is raw (the dump's units).  The Bragg ratio A5 computes
    is term/trunk of these medians, so the ratio is directly comparable even
    though the absolute numbers are not MIP-normalised.

`--body CM` recomputes the Bragg ratio with the window cut at CM instead of
at `smax`, which is how doc pr/148 sec 4.2 prices the defect that
`dqdx_term` is currently measured on absorbed members up to 70 cm past the
object's own contiguous body.

Repro:
  ./pr148_profile.py --arm work-nuecc48-d145np --event 137238 --shower 0 --body 51
"""
import argparse, json, math, os, statistics as st, sys
from collections import defaultdict

BINW = 3.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--shower", type=int, required=True)
    ap.add_argument("--body", type=float, default=None,
                    help="cm; also report the Bragg ratio with the window "
                         "cut here instead of at smax")
    a = ap.parse_args()

    d = json.load(open(os.path.join(a.arm, "pr_evt%s" % a.event,
                                    "calib-pr-evt%s.json" % a.event)))
    sh = {s["shower_id"]: s for s in d["showers"]}[a.shower]
    v = {x["id"]: x for x in d["vertices"]}[sh["start_vertex_id"]]["fit"]
    V = (v["x"], v["y"], v["z"])
    mem = [s for s in d["segments"] if s.get("shower_id") == sh["id"]]

    cnt, nsg, dq = defaultdict(int), defaultdict(set), defaultdict(list)
    for s in mem:
        for p in s.get("points", []):
            b = int(math.dist((p["x"], p["y"], p["z"]), V) / BINW)
            cnt[b] += 1
            nsg[b].add(s["id"])
            if p.get("dx", 0) > 0:
                dq[b].append(p["dQ"] / p["dx"])

    print("evt %s shower %d  start segment %s  %d member segment(s)  "
          "kine_best %.1f MeV" % (a.event, a.shower, sh["id"], len(mem),
                                  sh["kine_best"]))
    print("%10s %6s %5s %10s" % ("bin (cm)", "npts", "nseg", "med dQ/dx"))
    for b in range(0, max(cnt) + 1):
        if b not in cnt:
            continue
        m = st.median(dq[b]) if dq[b] else -1
        print("%5.0f-%-4.0f %6d %5d %10.0f"
              % (b * BINW, (b + 1) * BINW, cnt[b], len(nsg[b]), m))

    def bragg(limit):
        bins = [b for b in sorted(cnt) if (b + 1) * BINW <= limit + BINW]
        meds = {b: (st.median(dq[b]) if dq[b] else -1) for b in bins}
        n = max(bins) + 1
        trunk = sorted(meds[b] for b in bins if b < n - 2 and meds[b] > 0)
        term = max([meds[b] for b in bins if b >= n - 2 and meds[b] > 0] or [-1])
        tr = trunk[len(trunk) // 2] if trunk else -1
        return tr, term, (term / tr if tr > 0 and term > 0 else -1)

    tr, te, r = bragg(sh["total_length"] * 10)
    print("\nBragg over the FULL window: trunk %.0f  term %.0f  ratio %.2f"
          % (tr, te, r))
    if a.body:
        tr, te, r = bragg(a.body)
        print("Bragg with the window cut at %.0f cm: trunk %.0f  term %.0f  "
              "ratio %.2f" % (a.body, tr, te, r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
