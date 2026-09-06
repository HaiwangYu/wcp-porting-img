#!/usr/bin/env python3
"""doc sbnd_xin/pr/145 -- regenerate doc 144 sec 14.2.1's split-muon census.

READ-ONLY.  Writes only its --tsv.

doc 144 sec 14.2.1 reported the census (21 candidates showing the signature, 6
of them paying a spurious rest mass, 270.0 MeV total) but shipped no script, so
the working set could not be recovered.  This rebuilds it from the two arms'
calib dumps, which is the primary source (feedback_rederive_from_primary_source:
a table with no script is unverifiable).

THE SIGNATURE, as doc 144 defined it: strictly more counted pdg == 13 nodes on
the ON arm than on the OFF arm, with the TOTAL muon energy preserved to within
5 % -- i.e. one muon rendered as several PF nodes rather than a genuinely
different set of muons.  d_add is the change in kine_reco_add_energy, which is
where a per-node rest term shows up (105.66 MeV = muon mass, 139.57 = charged
pion).

Repro:
    ./scripts/pr145_split_census.py --off d144off --on d144on \
        --tsv docs/pr/pr145-splitcensus.tsv
"""
import argparse, glob, json, os, sys

MU_MASS, PI_MASS = 105.658, 139.570

def load(path):
    try:
        with open(path) as fh:
            return json.load(fh).get("kine")
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", default="d144off")
    ap.add_argument("--on",  default="d144on")
    ap.add_argument("--samples", nargs="+",
                    default=["mcp1k", "mcp2k", "nuecc48", "ncpi0"])
    ap.add_argument("--tol", type=float, default=0.05, help="muon-energy preservation")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    rows, n_both = [], 0
    for s in a.samples:
        for f in sorted(glob.glob(f"work-{s}-{a.off}/pr_evt*/calib-pr-evt*.json")):
            evt = os.path.basename(f)[len("calib-pr-evt"):-len(".json")]
            g = f.replace(f"-{a.off}/", f"-{a.on}/")
            if not os.path.exists(g):
                continue
            ko, kn = load(f), load(g)
            if not ko or not kn:
                continue
            n_both += 1
            def mus(k):
                t = k.get("kine_particle_type", [])
                e = k.get("kine_energy_particle", [])
                return [e[i] for i, p in enumerate(t) if p == 13 and i < len(e)]
            mo, mn = mus(ko), mus(kn)
            if len(mn) <= len(mo):
                continue
            so, sn = sum(mo), sum(mn)
            if so <= 0 or abs(sn - so) / so > a.tol:
                continue          # a different set of muons, not one split
            d_add = kn.get("kine_reco_add_energy", 0) - ko.get("kine_reco_add_energy", 0)
            rows.append(dict(sample=s, event=evt, nmu_off=len(mo), nmu_on=len(mn),
                             Emu_off=so, Emu_on=sn, d_add=d_add,
                             Enu_off=ko.get("kine_reco_Enu", 0),
                             Enu_on=kn.get("kine_reco_Enu", 0)))

    rows.sort(key=lambda r: -r["d_add"])
    pay = [r for r in rows if r["d_add"] > 1.0]
    print("candidates with a calib dump on BOTH arms   %d" % n_both)
    print("showing the split-muon signature            %d" % len(rows))
    print("of those, paying a spurious rest term       %d" % len(pay))
    print("total spurious kine_reco_add_energy         %.1f MeV"
          % sum(r["d_add"] for r in pay))
    print()
    print("%-9s %-8s %8s %10s %10s %10s   %s" %
          ("sample", "event", "nmu", "Emu_off", "Emu_on", "d_add", "term"))
    for r in rows:
        d = r["d_add"]
        term = ("muon"  if abs(d - MU_MASS) < 1.0 else
                "pion"  if abs(d - PI_MASS) < 1.0 else
                "none"  if abs(d) < 1.0 else "other")
        print("%-9s %-8s %3d->%-3d %10.1f %10.1f %+10.1f   %s" %
              (r["sample"], r["event"], r["nmu_off"], r["nmu_on"],
               r["Emu_off"], r["Emu_on"], d, term))

    if a.tsv:
        cols = ["sample", "event", "nmu_off", "nmu_on", "Emu_off", "Emu_on",
                "d_add", "Enu_off", "Enu_on"]
        with open(a.tsv, "w") as fh:
            fh.write("# doc pr/145 -- split-muon census, %s vs %s (doc 144 sec 14.2.1)\n"
                     % (a.off, a.on))
            fh.write("\t".join(cols) + "\n")
            for r in rows:
                fh.write("\t".join(("%.3f" % r[c]) if isinstance(r[c], float)
                                   else str(r[c]) for c in cols) + "\n")
        print("\nwrote %s (%d rows)" % (a.tsv, len(rows)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
