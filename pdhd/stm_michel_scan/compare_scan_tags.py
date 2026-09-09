#!/usr/bin/env python3
"""doc pdvd/55 -- compare two hand-scan tags item by item.

    ./compare_scan_tags.py --det pdvd --a smx1 --b smx1a [--csv OUT.tsv]

READ ONLY on both tags.  It opens `labels.json` and nothing else, and it never
writes into a label dir (M13).

WHY THE ATTRIBUTION COMPARISON IS NOT A DICT DIFF.  `pf_segments` holds the
scanner's OVERRIDES, so an absent key means "agreed with the chain" on one row
and "never looked" on another, and the two are indistinguishable in the file
(doc pdvd/53 sec 3 -- which is why `pf_chain_group` is persisted beside it).
Every object is therefore resolved to an EFFECTIVE group,

    effective(obj) = pf_segments[obj]  if the scanner tagged it
                     pf_chain_group[obj]  otherwise

and the two tags are compared on that.  Two scanners who both accept the chain
agree, which a dict diff would score as agreement only by accident; and a
scanner who explicitly confirms the chain's call is not counted as disagreeing
with one who left it alone.

A segment id present in `pf_segments` but absent from that row's
`pf_chain_group` is a tag written against an EARLIER ARM (two exist in smx1).
Those are reported separately rather than silently scored.
"""
import argparse, json, os, sys

# THREE dirnames: this file is <img>/pdhd/stm_michel_scan/..., so two of
# them stop at <img>/pdhd and every label path would be read one
# directory too deep.
IMG = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(det, tag):
    p = os.path.join(IMG, det, "work", "stm_michel_labels", tag, "labels.json")
    if not os.path.isfile(p):
        raise SystemExit("no labels at %s" % p)
    return json.load(open(p)), p


def effective(rec):
    """Every object this row knows about, resolved to one group.

    `pf_chain_group` carries the FITTED segments only, so an unfitted-cluster
    row -- keyed "C<id>" (stm_michel_viewer.py:2317) -- is absent from it by
    construction and must not be reported as a tag against an earlier arm.
    Those come back separately.
    """
    chain = dict(rec.get("pf_chain_group") or {})
    mine = dict(rec.get("pf_segments") or {})
    out = dict(chain)
    stale, clus = [], []
    for k, v in mine.items():
        if k not in chain:
            (clus if k.startswith("C") else stale).append(k)
        out[k] = v
    return out, stale, clus


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", default="pdvd")
    ap.add_argument("--a", required=True, help="reference tag (e.g. the owner's)")
    ap.add_argument("--b", required=True, help="tag to compare against it")
    ap.add_argument("--csv", default=None)
    o = ap.parse_args(argv)

    A, pa = load(o.det, o.a)
    B, pb = load(o.det, o.b)
    LA, LB = A["labels"], B["labels"]
    both = sorted(set(LA) & set(LB))
    print("%s  %d rows   %s" % (o.a, len(LA), pa))
    print("%s  %d rows   %s" % (o.b, len(LB), pb))
    print("shared %d   only in %s: %d   only in %s: %d\n"
          % (len(both), o.a, len(set(LA) - set(LB)), o.b, len(set(LB) - set(LA))))
    if not both:
        return 0

    rows, conf, kinds = [], {}, [0, 0]
    substantive, over = [], []
    obj_n = obj_ok = 0
    obj_moves = {}
    stale_all, clus_all = [], []
    for k in both:
        ra, rb = LA[k], LB[k]
        la, lb = ra.get("label"), rb.get("label")
        conf[(la, lb)] = conf.get((la, lb), 0) + 1
        ka, kb = ra.get("michel_kind"), rb.get("michel_kind")
        kinds[1] += 1
        kinds[0] += int(ka == kb)
        ea, sa, ca = effective(ra)
        eb, sb, cb = effective(rb)
        ta = set(ra.get("pf_segments") or {})
        tb = set(rb.get("pf_segments") or {})
        chain = dict(ra.get("pf_chain_group") or {})
        chain.update(rb.get("pf_chain_group") or {})
        stale_all += [(k, o.a, x) for x in sa] + [(k, o.b, x) for x in sb]
        clus_all += [(k, o.a, x) for x in ca] + [(k, o.b, x) for x in cb]
        keys = sorted(set(ea) | set(eb))
        n = ok = 0
        for x in keys:
            va, vb = ea.get(x), eb.get(x)
            if va is None or vb is None:
                continue          # the object is not in both rows' tables
            n += 1
            if va == vb:
                ok += 1
            else:
                obj_moves[(va, vb)] = obj_moves.get((va, vb), 0) + 1
                # THREE different things live in this bucket, and only one of
                # them is two scanners disagreeing.
                #   both tagged it     -> a real disagreement
                #   one tagged it, the chain had NO grouping ("unassigned")
                #                      -> one scanner was more explicit
                #   one tagged it, the chain DID group it
                #                      -> that scanner overrode the chain while
                #                         the other left it -- which is a
                #                         statement about the chain, not about
                #                         the other scanner
                if x in ta and x in tb:
                    substantive.append((k, x, va, vb))
                elif chain.get(x, "unassigned") != "unassigned":
                    over.append((k, x, chain.get(x), o.a if x in ta else o.b,
                                 va if x in ta else vb))
        obj_n += n
        obj_ok += ok
        pa_ = (ra.get("pin") or {}).get("placed")
        pb_ = (rb.get("pin") or {}).get("placed")
        rows.append((k, la, lb, ka, kb, n, ok,
                     "%.2f" % ((ra.get("pin") or {}).get("moved_cm") or 0.0) if pa_ else "-",
                     "%.2f" % ((rb.get("pin") or {}).get("moved_cm") or 0.0) if pb_ else "-"))

    agree = sum(v for (x, y), v in conf.items() if x == y)
    print("VERDICT  %d/%d agree  (%.0f%%)" % (agree, len(both), 100.0 * agree / len(both)))
    labs = sorted({x for p in conf for x in p if x})
    w = max(len(x) for x in labs) + 1
    print("    %-*s | %s" % (w, "%s \\ %s" % (o.a, o.b), "  ".join("%-*s" % (w, x) for x in labs)))
    for x in labs:
        print("    %-*s | %s" % (w, x, "  ".join("%-*d" % (w, conf.get((x, y), 0))
                                                 for y in labs)))
    print("\nMICHEL KIND  %d/%d agree  (%.0f%%)"
          % (kinds[0], kinds[1], 100.0 * kinds[0] / max(1, kinds[1])))
    print("ATTRIBUTION  %d/%d objects agree on the effective group  (%.0f%%)"
          % (obj_ok, obj_n, 100.0 * obj_ok / max(1, obj_n)))
    if obj_moves:
        print("  disagreements, %s -> %s:" % (o.a, o.b))
        for (x, y), v in sorted(obj_moves.items(), key=lambda t: -t[1]):
            print("    %-16s -> %-16s  %d" % (x, y, v))
    if substantive:
        print("\n  the %d where BOTH scanners tagged, and differently:"
              % len(substantive))
        for k, x, va, vb in substantive:
            print("    %-16s %-8s %-16s -> %s" % (k, x, va, vb))
    if over:
        print("\n  the %d where the CHAIN had grouped the object and one scanner "
              "overrode it while the other left it:" % len(over))
        for k, x, cg, who, val in over:
            print("    %-16s %-8s chain %-10s  %s says %s" % (k, x, cg, who, val))
    if stale_all:
        print("\nTAGS AGAINST AN ID THE ROW'S OWN pf_chain_group DOES NOT CARRY "
              "(an earlier arm):")
        for k, t, x in stale_all:
            print("    %s  %s  %s" % (k, t, x))
    if clus_all:
        print("\nUNFITTED-CLUSTER ROWS TAGGED (\"C<id>\"; pf_chain_group carries "
              "fitted segments only, so these are NOT stale):")
        for k, t, x in clus_all:
            print("    %s  %s  %s" % (k, t, x))

    print("\n%-16s %-12s %-12s %-14s %-14s %6s %s"
          % ("item", o.a, o.b, "kind " + o.a, "kind " + o.b, "obj", "pin a / b"))
    for r in rows:
        flag = "" if r[1] == r[2] else "   <-- verdict differs"
        print("%-16s %-12s %-12s %-14s %-14s %2d/%-3d %s / %s%s"
              % (r[0], r[1], r[2], r[3], r[4], r[6], r[5], r[7], r[8], flag))

    if o.csv:
        with open(o.csv, "w") as fh:
            fh.write("item\tlabel_%s\tlabel_%s\tkind_%s\tkind_%s\tobj_agree\tobj_n"
                     "\tpin_%s\tpin_%s\n" % (o.a, o.b, o.a, o.b, o.a, o.b))
            for r in rows:
                fh.write("%s\t%s\t%s\t%s\t%s\t%d\t%d\t%s\t%s\n"
                         % (r[0], r[1], r[2], r[3], r[4], r[6], r[5], r[7], r[8]))
        print("\nwrote %s" % o.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
