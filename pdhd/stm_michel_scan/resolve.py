#!/usr/bin/env python3
"""Collapse t2/v_parts/<scanner>/ into ONE record per item, deterministically.

Why this exists.  517 record files cover 509 items: eight items were scanned
twice, because a wave was re-spawned over a list that still held items another
scanner had already banked.  Seven of the eight pairs agree exactly.  One does
not -- 039349_62/63 was called STM_MICHEL/attached in wave 7 and STM_ONLY/none
in wave 8 -- and that disagreement is real data (it is the inter-scanner
disagreement quoted in the doc's label-quality section), not corruption.

The bug is not the duplicate, it is how the duplicate was being resolved:
mkspec.py, mkrecord.py and mkfailures.py each walked v_parts with os.walk and
did recs[key] = r, i.e. last-writer-wins in whatever order the filesystem
returned directories.  Three tools reading the same tree could disagree about
one item, and the pushed failures.tsv would not be reproducible.

The tie-break here is not a judgement about which scan is better.  It is
"whichever record matches the label that the app actually wrote", so the
committed record provably describes the artifact on disk.  If a duplicate pair
cannot be resolved that way, this refuses rather than picking.
"""
import json, os, sys, collections

# The inputs are this round's SCRATCH tree -- the per-scanner record dirs and the
# five private label dirs -- which is not committed; the committed artefact is
# what this produced (pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json, and
# the eight duplicate pairs in pdvd_stm_michel_duplicate_scans.tsv).  It is here
# so the tie-break RULE doc pdvd/55 sec 17.6 cites can be read and re-run
# against a future round's tree, not so this round can be replayed.
#
#     resolve.py [<scratch scan dir>]
SC = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else \
    "/home/xqian/tmp/claude-25225/-home-xqian-toolkit-dev-toolkit/d9d688aa-85d3-4ebf-900f-e2f746766f40/scratchpad/scan"
OUT = SC + "/t2/v_resolved"

# what the app actually wrote, per key
applied = {}
for n in range(5):
    p = "%s/t2/lbl_t2_%d/labels.json" % (SC, n)
    for k, rec in json.load(open(p))["labels"].items():
        applied[k] = rec

by = collections.defaultdict(list)
for dd, _, fns in os.walk(SC + "/t2/v_parts"):
    for fn in sorted(fns):
        if fn.endswith(".json"):
            p = os.path.join(dd, fn)
            r = json.load(open(p))
            by[r["key"]].append((p, r))

os.makedirs(OUT, exist_ok=True)
n_dup = n_tie = 0
unresolved = []
for k, cands in sorted(by.items()):
    if len(cands) == 1:
        pick = cands[0]
    else:
        n_dup += 1
        rec = applied.get(k)
        if rec is None:
            unresolved.append((k, "not applied yet"))
            continue
        # identical candidates need no tie-break
        sigs = {json.dumps([c[1]["verdict"], c[1]["michel_kind"],
                            c[1]["tags"]], sort_keys=True) for c in cands}
        if len(sigs) == 1:
            # The verdicts agree, but the two scanners wrote different prose.
            # The record has to quote the notes the app actually stored, or the
            # published evidence paragraph belongs to a scan the label does not
            # come from -- so tie-break on the notes, and fall back to sorted
            # path order (never os.walk order) when even that cannot separate.
            nmatch = [c for c in cands
                      if (c[1].get("notes") or "") == (rec.get("notes") or "")]
            pick = nmatch[0] if len(nmatch) == 1 else sorted(cands)[0]
        else:
            n_tie += 1
            match = [c for c in cands
                     if c[1]["verdict"] == rec.get("choice")
                     and c[1]["michel_kind"] == rec.get("michel_kind")
                     and len(c[1]["tags"]) == rec.get("pf_tagged")]
            if len(match) != 1:
                unresolved.append((k, "%d of %d candidates match the label"
                                   % (len(match), len(cands))))
                continue
            pick = match[0]
            print("  tie-break %-16s -> %s/%s (matches the applied label); "
                  "dropped %s" % (k, pick[1]["verdict"], pick[1]["michel_kind"],
                                  [c[1]["verdict"] for c in cands if c is not pick]))
    json.dump(pick[1], open(OUT + "/" + k.replace("/", "_") + ".json", "w"),
              indent=1, ensure_ascii=False)

print("\nresolved %d items into %s" % (len(by) - len(unresolved), OUT))
print("  duplicated items: %d (of which disagreeing: %d)" % (n_dup, n_tie))
if unresolved:
    for k, why in unresolved:
        print("  !! UNRESOLVED %s: %s" % (k, why))
    raise SystemExit("refusing to leave an ambiguous record")

# every resolved record must agree with the applied label
bad = []
for k, rec in applied.items():
    p = OUT + "/" + k.replace("/", "_") + ".json"
    if not os.path.exists(p):
        bad.append((k, "no resolved record")); continue
    r = json.load(open(p))
    if (r["verdict"] != rec.get("choice") or r["michel_kind"] != rec.get("michel_kind")
            or len(r["tags"]) != rec.get("pf_tagged")):
        bad.append((k, "record %s/%s/%d vs label %s/%s/%s"
                    % (r["verdict"], r["michel_kind"], len(r["tags"]),
                       rec.get("choice"), rec.get("michel_kind"), rec.get("pf_tagged"))))
print("cross-check against %d applied labels: %d disagreements" % (len(applied), len(bad)))
for k, why in bad[:10]:
    print("  !! %s: %s" % (k, why))
if bad:
    raise SystemExit("resolved record disagrees with the artifact")
