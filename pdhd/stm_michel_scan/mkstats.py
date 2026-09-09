#!/usr/bin/env python3
"""Re-derive every headline number in doc pdvd/55 sec 14-15 from the committed record.

A published table with no committed script cannot be checked, and these numbers
were first computed from a scratch verdict tree that no longer exists in that
form.  This reads only committed artefacts -- the 569-record scan record and the
chain's own per-item payloads -- so any reader can reproduce sec 14.1, 14.2 and
15.1, and so a later re-run can show whether a fix moved them.

    python3 mkstats.py            # print the tables
    python3 mkstats.py --check    # also diff them against the literals in doc 55

--check carries its own copy of what doc 55 published on 2026-09-09.  That makes
it a snapshot test, not a live parse of the document: it catches the numbers
MOVING under a re-run, which is what it was written for, but it cannot catch the
doc and this script being edited apart.  Change both together.
"""
import json, sys, os, re, collections

IMG = "/home/xqian/toolkit-dev/wcp-porting-img"
REC = IMG + "/pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json"
P = IMG + "/pdhd/stm_michel_scan/prep-pdvd"
DOC = IMG + "/pdvd/docs/nf_sp_img_clus/55_stm-michel-handscan-pdvd.md"

recs = json.load(open(REC))


def bare(v):
    return v.replace("FRAG_", "")


def payload(k):
    return json.load(open("%s/smprep-%s.json" % (P, k.replace("/", "-c"))))


def rates(rows, scan_pos, chain_pos):
    tp = sum(1 for r in rows if scan_pos(r) and chain_pos(r))
    fp = sum(1 for r in rows if not scan_pos(r) and chain_pos(r))
    fn = sum(1 for r in rows if scan_pos(r) and not chain_pos(r))
    tn = sum(1 for r in rows if not scan_pos(r) and not chain_pos(r))
    pur = tp / (tp + fp) if tp + fp else float("nan")
    eff = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * pur * eff / (pur + eff) if pur + eff else float("nan")
    return dict(scored=len(rows), tp=tp, fp=fp, fn=fn, tn=tn,
                purity=pur, efficiency=eff, f1=f1)


for r in recs:
    v = payload(r["key"]).get("verdict") or {}
    r["_is_stm"] = bool(v.get("is_stm"))
    r["_mi"] = bool(v.get("michel_found"))
    r["_dis"] = v.get("michel_dis_cm") or 0.0
    r["_ke"] = v.get("michel_ke_best") or 0.0

scored = [r for r in recs if r["verdict"] not in ("MESSY", "UNCLEAR")]
groups = [("tranche 1 (enriched)", [r for r in scored if r["tranche"] == 1]),
          ("tranche 2", [r for r in scored if r["tranche"] == 2]),
          ("census (569)", scored)]

out = {}
print("=== 14.1  is_stm ===")
print("%-22s %6s %5s %4s %5s %5s %8s %8s" % ("", "scored", "TP", "FP", "FN", "TN", "purity", "effic"))
for nm, rows in groups:
    d = rates(rows, lambda r: bare(r["verdict"]) in ("STM_MICHEL", "STM_ONLY"),
              lambda r: r["_is_stm"])
    out["is_stm/" + nm] = d
    print("%-22s %6d %5d %4d %5d %5d %8.3f %8.3f"
          % (nm, d["scored"], d["tp"], d["fp"], d["fn"], d["tn"], d["purity"], d["efficiency"]))

print("\n=== 14.2  michel_found ===")
print("%-22s %6s %5s %4s %5s %5s %8s %8s" % ("", "scored", "TP", "FP", "FN", "TN", "purity", "effic"))
for nm, rows in groups:
    d = rates(rows, lambda r: bare(r["verdict"]) == "STM_MICHEL", lambda r: r["_mi"])
    out["michel/" + nm] = d
    print("%-22s %6d %5d %4d %5d %5d %8.3f %8.3f"
          % (nm, d["scored"], d["tp"], d["fp"], d["fn"], d["tn"], d["purity"], d["efficiency"]))

print("\n=== 15.1  the proposed cut, on the census ===")
print("%-34s %5s %4s %5s %8s %8s %7s" % ("", "TP", "FP", "FN", "purity", "effic", "F1"))
variants = [("as shipped", lambda r: r["_mi"]),
            ("drop dis > 3 cm & KE < 10 MeV",
             lambda r: r["_mi"] and not (r["_dis"] > 3.0 and r["_ke"] < 10.0))]
for nm, fn_ in variants:
    d = rates(scored, lambda r: bare(r["verdict"]) == "STM_MICHEL", fn_)
    out["cut/" + nm] = d
    print("%-34s %5d %4d %5d %8.3f %8.3f %7.3f"
          % (nm, d["tp"], d["fp"], d["fn"], d["purity"], d["efficiency"], d["f1"]))

if "--check" not in sys.argv:
    raise SystemExit(0)

# ---- diff against the literals published in doc 55
doc = open(DOC).read()
want = [
    # (label, doc row regex, (scored, tp, fp, fn, tn, purity, efficiency))
    ("14.1 census", r"\*\*census \(569\)\*\* \| \*\*549\*\* \| \*\*144\*\* \| \*\*9\*\* \| \*\*125\*\* \| \*\*271\*\* \| \*\*0\.941\*\* \| \*\*0\.535\*\*",
     out["is_stm/census (569)"], (549, 144, 9, 125, 271, 0.941, 0.535)),
    ("14.2 census", r"\*\*census \(569\)\*\* \| \*\*549\*\* \| \*\*111\*\* \| \*\*39\*\* \| \*\*41\*\* \| \*\*358\*\* \| \*\*0\.740\*\* \| \*\*0\.730\*\*",
     out["michel/census (569)"], (549, 111, 39, 41, 358, 0.740, 0.730)),
]
bad = 0
print("\n=== --check: recomputed vs the literals in doc 55 ===")
for nm, rx, d, lit in want:
    got = (d["scored"], d["tp"], d["fp"], d["fn"], d["tn"],
           round(d["purity"], 3), round(d["efficiency"], 3))
    ok_row = re.search(rx, doc) is not None
    ok_num = got == lit
    print("  %-12s recomputed %s\n               published %s   %s  (row present in doc: %s)"
          % (nm, got, lit, "MATCH" if ok_num else "*** DIFFERS ***", ok_row))
    bad += (not ok_num) or (not ok_row)

for nm, key, lit in (("15.1 shipped", "cut/as shipped", (111, 39, 41, 0.740, 0.730, 0.735)),
                     ("15.1 cut", "cut/drop dis > 3 cm & KE < 10 MeV", (108, 13, 44, 0.893, 0.711, 0.791))):
    d = out[key]
    got = (d["tp"], d["fp"], d["fn"], round(d["purity"], 3),
           round(d["efficiency"], 3), round(d["f1"], 3))
    print("  %-12s recomputed %s\n               published %s   %s"
          % (nm, got, lit, "MATCH" if got == lit else "*** DIFFERS ***"))
    bad += got != lit

print("\n%d of 4 checked tables differ from the doc" % bad)
raise SystemExit(1 if bad else 0)
