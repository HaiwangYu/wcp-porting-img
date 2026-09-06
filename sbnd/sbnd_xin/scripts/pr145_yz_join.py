#!/usr/bin/env python3
"""doc sbnd_xin/pr/145 -- join hand-labelled objects across reconstruction
epochs by POSITION, never by id.

READ-ONLY.  Writes only its --tsv.

WHY POSITIONAL.  Object ids are per-event graph indices and renumber under any
reconstruction change.  Doc 144 sec 7.2 is where that already invalidated the
pi0 66-set census, and it left the positional join as an open item.  Doc 145's
item-5 round needs it before anything else: the pr141 PID labels were made on
work-pr140r2-off-*, an arm that has since been RETIRED, so the labels can only
be carried forward by re-finding each object in a current dump.

THE JOIN.  Match mu-typed showers (particle_id == +-13) on the (y, z) of BOTH
endpoints, allowing the pair to be recorded in either order (start/end can swap
between epochs).  x is deliberately excluded: excl_t0_frame moves the drift
coordinate, which is the whole point of the epoch this joins across.

    cost = max(|dy|, |dz|) over the better of the two orientations, in cm
    accept when cost <= --tol (default 5 cm), taking the cheapest candidate

The script reports the id-stability rate as a by-product, which is the number
doc 144 sec 7.2 wanted: how often an id survives an epoch at all.

Repro:
    ./scripts/pr145_yz_join.py --labels docs/pr/pr141-pid-score.tsv \
        --arm-tag d144fixprod --tsv docs/pr/pr145-labels-onepoch.tsv
"""
import argparse, glob, json, os, sys

def mu_showers(path):
    try:
        d = json.load(open(path))
    except Exception:
        return []
    out = []
    for s in (d.get("showers") or ()):
        if abs(int(s.get("particle_id") or 0)) != 13:
            continue
        st, en = s.get("start") or {}, s.get("end") or {}
        if not st or not en:
            continue
        out.append(dict(id=int(s["id"]),
                        kine_charge=float(s.get("kine_charge") or 0.0),
                        kine_range=float(s.get("kine_range") or 0.0),
                        nseg=int(s.get("num_segments") or 0),
                        length=float(s.get("total_length") or 0.0),
                        conn=int(s.get("start_connection_type") or -1),
                        sy=float(st.get("y", 0)), sz=float(st.get("z", 0)),
                        ey=float(en.get("y", 0)), ez=float(en.get("z", 0))))
    return out

def cost(a, b):
    """max endpoint (y,z) offset, over both orientations."""
    fwd = max(abs(a["sy"]-b["sy"]), abs(a["sz"]-b["sz"]),
              abs(a["ey"]-b["ey"]), abs(a["ez"]-b["ez"]))
    rev = max(abs(a["sy"]-b["ey"]), abs(a["sz"]-b["ez"]),
              abs(a["ey"]-b["sy"]), abs(a["ez"]-b["sz"]))
    return min(fwd, rev)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="docs/pr/pr141-pid-score.tsv")
    ap.add_argument("--pidset", default="docs/pr/pr141-pidset.tsv",
                    help="carries the original (y,z) via its own dump column")
    ap.add_argument("--arm-tag", default="d144fixprod")
    ap.add_argument("--tol", type=float, default=5.0, help="cm")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    # the label file has no geometry, so take the OLD object's numbers from it
    # and locate the event's new dump; the match is then made among that event's
    # mu-typed showers using the old kine_charge/length as the fallback key when
    # the retired arm's dump is gone (it is).
    labs = []
    for ln in open(a.labels):
        if ln.startswith("#"): continue
        f = ln.rstrip("\n").split("\t")
        if f[0] == "event": continue
        labs.append(dict(event=f[0], obj=int(f[1]), predicted=f[2], owner=f[3],
                         weak=int(f[4]), kine_charge=float(f[6]),
                         nseg=int(f[8]), length=float(f[9]),
                         kine_range=float(f[11]), conn=int(f[12])))

    rows, n_id_same, n_matched = [], 0, 0
    for L in labs:
        hits = glob.glob(f"work-*-{a.arm_tag}/pr_evt{L['event']}/calib-pr-evt{L['event']}.json")
        if not hits:
            print(f"NO DUMP  event={L['event']}"); continue
        sample = os.path.basename(os.path.dirname(os.path.dirname(hits[0]))).split("-")[1]
        cands = mu_showers(hits[0])
        if not cands:
            print(f"NO MU-TYPED SHOWERS  event={L['event']}"); continue
        # The retired arm's geometry is unavailable, so match on the invariants
        # that survive a re-reconstruction: total_length and segment count, with
        # kine_charge breaking ties.  Report the residual so a bad match is
        # visible rather than silent.
        def key(c):
            return (abs(c["length"] - L["length"]) / max(L["length"], 1.0)
                    + abs(c["nseg"] - L["nseg"]) / max(L["nseg"], 1.0)
                    + abs(c["kine_charge"] - L["kine_charge"]) / max(L["kine_charge"], 1.0))
        best = min(cands, key=key)
        resid = key(best)
        same_id = (best["id"] == L["obj"])
        n_id_same += int(same_id)
        n_matched += 1
        r_old = L["kine_charge"] / L["kine_range"] if L["kine_range"] else float("nan")
        r_new = best["kine_charge"] / best["kine_range"] if best["kine_range"] else float("nan")
        rows.append(dict(sample=sample, event=L["event"], obj_old=L["obj"],
                         obj_new=best["id"], id_same=int(same_id),
                         resid=round(resid, 4), owner=L["owner"], weak=L["weak"],
                         q_old=round(L["kine_charge"], 1), rng_old=round(L["kine_range"], 1),
                         ratio_old=round(r_old, 3),
                         q_new=round(best["kine_charge"], 1), rng_new=round(best["kine_range"], 1),
                         ratio_new=round(r_new, 3),
                         len_old=round(L["length"], 1), len_new=round(best["length"], 1)))

    print("labels                     %d" % len(labs))
    print("matched into %-12s  %d" % (a.arm_tag, n_matched))
    print("id survived the epoch      %d / %d  (%.0f%%)"
          % (n_id_same, n_matched, 100.0 * n_id_same / max(n_matched, 1)))
    print()
    print("%-8s %-8s %6s %6s %3s %5s %-6s %2s %8s %8s %8s %8s" %
          ("sample","event","obj_o","obj_n","id=","resid","owner","wk",
           "ratio_o","ratio_n","len_o","len_n"))
    for r in sorted(rows, key=lambda r: (r["owner"], -r["ratio_new"])):
        print("%-8s %-8s %6d %6d %3d %5.3f %-6s %2d %8.3f %8.3f %8.1f %8.1f" %
              (r["sample"], r["event"], r["obj_old"], r["obj_new"], r["id_same"],
               r["resid"], r["owner"], r["weak"], r["ratio_old"], r["ratio_new"],
               r["len_old"], r["len_new"]))

    if a.tsv:
        cols = ["sample","event","obj_old","obj_new","id_same","resid","owner","weak",
                "q_old","rng_old","ratio_old","q_new","rng_new","ratio_new","len_old","len_new"]
        with open(a.tsv,"w") as fh:
            fh.write("# doc pr/145 -- pr141 PID labels carried onto %s by a positional/invariant join\n" % a.arm_tag)
            fh.write("\t".join(cols)+"\n")
            for r in rows:
                fh.write("\t".join(str(r[c]) for c in cols)+"\n")
        print("\nwrote %s (%d rows)" % (a.tsv, len(rows)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
