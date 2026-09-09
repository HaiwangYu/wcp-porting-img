#!/usr/bin/env python3
"""doc pdvd/55 -- does the label file on disk say what the scan record says?

    ./verify_scan_record.py --det pdvd --tag smx1a \
        --record ../../pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json

READ ONLY.  The scan record (committed beside the sheet) is the *input* the
harness applied; `<det>/work/stm_michel_labels/<tag>/labels.json` is the
*artifact* the owner validates and the doc's tables are built from.  A doc that
quotes its numbers from the input has proved nothing about the artifact -- the
tags go in through real widget clicks and have twice failed to stick (a row-0
selection that emitted no change, and a table that re-sorts under the click),
so the two must be compared, not assumed equal.

Checks, per item: the verdict (`choice`, which keeps the FRAG_* form), the
Michel kind, every object tag, that the row tags EVERY object it draws
(`pf_tagged == n_pf_objects`), and that a pin is placed exactly where the
record asked for one.  Exits non-zero and names every mismatch.
"""
import argparse, collections, json, os, sys

IMG = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", default="pdvd", choices=["pdhd", "pdvd"])
    ap.add_argument("--tag", default="smx1a")
    ap.add_argument("--record", required=True)
    ap.add_argument("--labels", default=None)
    o = ap.parse_args(argv)

    lf = o.labels or os.path.join(IMG, o.det, "work", "stm_michel_labels",
                                  o.tag, "labels.json")
    disk = json.load(open(lf))["labels"]
    rec = json.load(open(o.record))

    bad = []
    verdicts, kinds, tags = collections.Counter(), collections.Counter(), collections.Counter()
    pins = 0
    for it in rec:
        k = it["key"]
        r = disk.get(k)
        if r is None:
            bad.append((k, "MISSING from %s" % lf))
            continue
        if r.get("choice") != it["verdict"]:
            bad.append((k, "choice %r, record says %r" % (r.get("choice"), it["verdict"])))
        if r.get("michel_kind") != it.get("michel_kind"):
            bad.append((k, "michel_kind %r, record says %r"
                        % (r.get("michel_kind"), it.get("michel_kind"))))
        seg = r.get("pf_segments") or {}
        want = it.get("tags") or {}
        short = {x: (want[x], seg.get(x)) for x in want if seg.get(x) != want[x]}
        extra = {x: seg[x] for x in seg if x not in want}
        if short or extra:
            bad.append((k, "tags differ -- wanted/on disk %s, on disk only %s"
                        % (short, extra)))
        if r.get("pf_tagged") != r.get("n_pf_objects"):
            bad.append((k, "%s of %s drawn objects carry a tag"
                        % (r.get("pf_tagged"), r.get("n_pf_objects"))))
        p = r.get("pin") or {}
        if bool(p.get("placed")) != (it.get("pin_rr") is not None):
            bad.append((k, "pin placed=%s, record asks pin_rr=%s"
                        % (p.get("placed"), it.get("pin_rr"))))
        pins += int(bool(p.get("placed")))
        verdicts[r.get("choice")] += 1
        kinds[r.get("michel_kind")] += 1
        tags.update(seg.values())

    print("record %s\nlabels %s" % (o.record, lf))
    print("%d records over %d rows on disk" % (len(rec), len(disk)))
    print("verdicts   %s" % dict(verdicts))
    print("kinds      %s" % dict(kinds))
    print("tags       %s  total %d" % (dict(tags), sum(tags.values())))
    print("pins placed %d" % pins)
    if bad:
        print("\n%d MISMATCH(ES):" % len(bad))
        for k, m in bad:
            print("  %-16s %s" % (k, m))
        return 1
    print("\nOK: the artifact says what the record says, on every field the doc "
          "publishes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
