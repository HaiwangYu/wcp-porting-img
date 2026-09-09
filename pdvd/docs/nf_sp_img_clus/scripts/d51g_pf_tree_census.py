#!/usr/bin/env python3
"""doc pdvd/51 -- what the two Bee particle-flow display floors actually did.

`mc.json` inside `mabc-pr.zip` is the PF product a human looks at.  This round
moves two floors that decide what appears in it, and both need their effect
counted rather than argued:

  em_ke_min  5 -> 0.2 MeV   a DISPLAY floor (MultiAlgBlobClustering.cxx:2078
                            keep_node): a childless |pdg| in {11,22} leaf below
                            it is dropped, and append_pseudo_shower drops the
                            carrier too when its only leaf goes.  At 5 MeV every
                            ~1 MeV capture gamma would vanish WHOLE.
  ke_decimal_below 0 -> 10  prototype_names writes an INTEGER MeV, so a 0.95 MeV
                            object was labelled "0 MeV".

The isolation is exact if the arms are chosen properly: a LEGACY arm
(stop_gamma_enable=false) built from the new config differs from the pre-round
arm ONLY in the two floors, so the node count between them is the em_ke_min
collateral with no capture gammas in it.  Comparing the FEATURE arm to the
legacy one then counts the gammas alone.

Reports, per pair: total nodes, nodes by pdg name, how many nodes carry a
sub-1-MeV label (the ke_decimal_below population), and the per-event delta.
"""
import argparse, glob, json, os, re, sys, zipfile
from collections import Counter


def tree(zp):
    try:
        with zipfile.ZipFile(zp) as z:
            return json.loads(z.read("data/0/0-mc.json"))
    except Exception:
        return None


def walk(n, out):
    out.append(n.get("text", ""))
    for c in n.get("children", []) or []:
        walk(c, out)


NAME_KE = re.compile(r"^\s*(\S+)\s+([0-9.]+)\s*MeV")


def census(pattern, arm):
    per_ev, names, small, tot = {}, Counter(), 0, 0
    for d in sorted(glob.glob(pattern)):
        zp = os.path.join(d, "mabc-pr.zip")
        t = tree(zp)
        if t is None:
            continue
        ev = os.path.basename(d)[: -len(arm) - 1]
        texts = []
        for n in t:
            walk(n, texts)
        n_nodes = 0
        for s in texts:
            m = NAME_KE.match(s)
            if not m:
                continue                      # the "nu" roots carry no energy
            n_nodes += 1
            names[m.group(1)] += 1
            if float(m.group(2)) < 1.0:
                small += 1
        per_ev[ev] = n_nodes
        tot += n_nodes
    return per_ev, names, small, tot


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True)
    ap.add_argument("--before-arm", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--after-arm", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    pb, nb, sb, tb = census(a.before, a.before_arm)
    pa, na, sa, ta = census(a.after, a.after_arm)
    keys = sorted(set(pb) & set(pa))
    L = []
    P = L.append
    P("=" * 74)
    P(a.label or ("%s -> %s" % (a.before_arm, a.after_arm)))
    P("  events matched            : %d" % len(keys))
    P("  PF nodes carrying an energy: %d -> %d   (%+d, %+.2f per event)"
      % (tb, ta, ta - tb, (ta - tb) / max(len(keys), 1)))
    P("  nodes labelled below 1 MeV : %d -> %d   (0 before ke_decimal_below is on,"
      % (sb, sa))
    P("                               because an integer MeV cannot express one)")
    P("  by particle name:")
    for k in sorted(set(nb) | set(na)):
        P("      %-10s %6d -> %6d  (%+d)" % (k, nb.get(k, 0), na.get(k, 0),
                                             na.get(k, 0) - nb.get(k, 0)))
    grew = [k for k in keys if pa[k] > pb[k]]
    shrank = [k for k in keys if pa[k] < pb[k]]
    P("  events that gained nodes   : %d" % len(grew))
    P("  events that lost nodes     : %d" % len(shrank))
    if shrank:
        P("      %s" % ", ".join("%s %d->%d" % (k, pb[k], pa[k]) for k in shrank[:10]))
    txt = "\n".join(L)
    print(txt)
    if a.out:
        with open(a.out, "a") as fh:
            fh.write(txt + "\n")


if __name__ == "__main__":
    main()
