#!/usr/bin/env python3
"""Bring the owner's two live pins into line with the scan record.

The owner's call, 2026-09-09: "they are OK either way, you can use your own scan
results."  So 039349_12/45 loses its pin (the record asks for none) and
039349_26/40 moves from rr 0.60 to the record's rr 4.00 (the app snaps to 4.2,
inside verify_scan_record.py's 0.5 cm tolerance).

Both rows were rewritten by clicking the real widgets in fix2/, not edited here.
This only swaps them in, and refuses if anything but `pin` moved on them or if
any of the other 567 rows moved at all.
"""
import json, hashlib, shutil, os, sys

SC = "/home/xqian/tmp/claude-25225/-home-xqian-toolkit-dev-toolkit/d9d688aa-85d3-4ebf-900f-e2f746766f40/scratchpad/scan"
LIVE = "/home/xqian/toolkit-dev/wcp-porting-img/pdvd/work/stm_michel_labels/smx1a/labels.json"
KS = ["039349_12/45", "039349_26/40"]
write = "--write" in sys.argv

want = open(SC + "/t2/smx1a_post_merge.sha").read().split()[0]
have = hashlib.sha256(open(LIVE, "rb").read()).hexdigest()
if have != want:
    raise SystemExit("live smx1a moved:\n  have %s\n  want %s" % (have, want))
print("live smx1a is the expected file (%s)" % have[:12])

live = json.load(open(LIVE))
new = json.load(open(SC + "/t2/fix2/labels.json"))["labels"]
for k in KS:
    a, b = live["labels"][k], new[k]
    moved = [f for f in set(a) | set(b)
             if json.dumps(a.get(f), sort_keys=True) != json.dumps(b.get(f), sort_keys=True)]
    if moved != ["pin"]:
        raise SystemExit("%s: expected only `pin` to change, got %s" % (k, moved))
    pa, pb = a.get("pin") or {}, b.get("pin") or {}
    print("  %-16s pin placed %s->%s  rr %s->%s  moved %.2f->%.2f cm"
          % (k, pa.get("placed"), pb.get("placed"), pa.get("rr"), pb.get("rr"),
             pa.get("moved_cm") or 0.0, pb.get("moved_cm") or 0.0))
    live["labels"][k] = b

if not write:
    print("\n--check only, nothing written"); raise SystemExit(0)

shutil.copy2(LIVE, SC + "/t2/smx1a_pre_patch2_backup.json")
tmp = LIVE + ".patch.tmp"
json.dump(live, open(tmp, "w"), indent=1)
os.replace(tmp, LIVE)
sha = hashlib.sha256(open(LIVE, "rb").read()).hexdigest()
open(SC + "/t2/smx1a_post_merge.sha", "w").write(sha + "  " + LIVE + "\n")

d = json.load(open(LIVE))["labels"]
base = json.load(open(SC + "/t2/smx1a_pre_patch2_backup.json"))["labels"]
coll = [k for k in base if k not in KS
        and json.dumps(base[k], sort_keys=True) != json.dumps(d[k], sort_keys=True)]
print("\nWROTE %s\n  rows %d\n  sha  %s" % (LIVE, len(d), sha))
print("  rows other than the two that moved: %d" % len(coll))
if coll:
    raise SystemExit("collateral change: %s" % coll[:10])
