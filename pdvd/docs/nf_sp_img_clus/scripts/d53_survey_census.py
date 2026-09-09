#!/usr/bin/env python3
"""doc pdvd/53 -- what the survey actually put in front of the scanner.

Reads the ARM (tracking-pr.root), not a payload, so the numbers are the chain's
and can be re-derived without the display (feedback_rederive_from_primary_source).

Four questions, in the order they decide something:

  1. HOW MUCH MORE IS FITTED.  n_survey_segs / n_survey_clusters per candidate,
     against the doc pdvd/51 arm's companion count.  This is the cost side: every
     admitted companion enters TrackFitting::preload_clusters and can move the
     candidate's own muon dQ/dx.

  2. WHY EACH PIECE WAS DROPPED.  The rej histogram over role-6 segments.  A
     survey piece is one of two things -- "no stage was ever offered it" (9), or
     "a stage looked and said no" -- and the second is the interesting one,
     because it is where a threshold is doing work a hand scan can check.

  3. HOW CLOSE THE REJECTIONS WERE.  For the body exclusions (4 and 6) the
     margin d_stop - d_body.  A discriminator rejecting at 0.3 mm is not
     discriminating; it is rounding.  Reported, NOT tuned (CLAUDE.md sec 5.7).

  4. WHAT IS NOT PHYSICALLY THERE.  Every same-bundle / other-flash split, from
     T_cluster's (flash_id, cluster_t0_us).  The Bee clustering-global layer
     draws every cluster at its OWN bundle's t0-corrected x (doc pdhd/13 sec 4),
     so a piece from another flash is centimetres away on screen and metres away
     in the detector.  The scanner is being asked to group these; the count of
     them is the size of the trap.

Repro:
    ./d53_survey_census.py --arm-dir 'pdvd/work/*_d53v' --arm d53v \
        --base-dir 'pdvd/work/*_d51gv' --base-arm d51gv --out /home/xqian/tmp/d53/ana/survey_pdvd.txt
"""
import argparse, glob, os, sys
import numpy as np
import uproot

REJ = {0: "claimed (should not appear on role 6)",
       1: "outside the Michel radius",
       2: "segment too far from the stop",
       3: "longer than the piece cap",
       4: "Michel body exclusion",
       5: "outside the gamma ring",
       6: "gamma body exclusion",
       7: "the Michel already owns the cluster",
       8: "energy window / per-candidate cap",
       9: "survey only -- neither stage was offered it",
       10: "no stop vertex -- nothing examined it"}


def arm_events(pattern):
    for d in sorted(glob.glob(pattern)):
        fp = os.path.join(d, "tracking-pr.root")
        if os.path.exists(fp):
            yield d, fp


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm-dir", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--base-dir", default=None, help="the doc pdvd/51 arm, for the cost delta")
    ap.add_argument("--base-arm", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    L = []
    P = L.append
    nseg = []; nclus = []; nunfit = []
    rej = {}; margin = {4: [], 6: []}
    n_cand = n_stm = 0
    nearest_rej6 = []
    # the bundle picture, from T_cluster
    nb_in = nb_out = 0
    per_cand_out = []
    for d, fp in arm_events(a.arm_dir):
        try:
            f = uproot.open(fp)
            t = f["T_stm_michel"].arrays(library="np")
        except Exception as e:
            print("SKIP %s: %s" % (os.path.basename(d), e), file=sys.stderr)
            continue
        if "n_survey_segs" not in t:
            print("SKIP %s: no survey branches (survey off?)" % os.path.basename(d),
                  file=sys.stderr)
            continue
        try:
            p = f["T_stm_michel_pts"].arrays(library="np")
        except Exception:
            p = None
        try:
            tc = f["T_cluster"].arrays(
                ["cluster_id", "flash_id", "cluster_t0_us"], library="np")
        except Exception:
            tc = None
        ev = os.path.basename(d)[: -len(a.arm) - 1]
        for i in range(len(t["cluster_id"])):
            n_cand += 1
            if int(t["is_stm"][i]):
                n_stm += 1
            nseg.append(int(t["n_survey_segs"][i]))
            nclus.append(int(t["n_survey_clusters"][i]))
            nunfit.append(int(t["n_survey_unfit"][i]))
            cid = int(t["cluster_id"][i])
            if p is None:
                continue
            k = (p["cluster_id"] == cid) & (p["role"] == 6)
            if not k.sum():
                continue
            # one row per SEGMENT, not per point
            seen = set()
            for j in np.flatnonzero(k):
                sid = int(p["seg_id"][j])
                if sid in seen:
                    continue
                seen.add(sid)
                code = int(p["rej"][j])
                rej[code] = rej.get(code, 0) + 1
                ds, db = float(p["d_stop"][j]), float(p["d_body"][j])
                if code in margin and db >= 0:
                    margin[code].append(ds - db)
                    if ds - db < 1.0:
                        nearest_rej6.append((ds - db, ev, cid, sid, code, ds, db))
                if tc is not None:
                    w = np.where(tc["cluster_id"] == sid // 1000)[0]
                    wc = np.where(tc["cluster_id"] == cid)[0]
                    if len(w) and len(wc):
                        same = (tc["flash_id"][w[0]] == tc["flash_id"][wc[0]]
                                and abs(tc["cluster_t0_us"][w[0]]
                                        - tc["cluster_t0_us"][wc[0]]) <= 1e-6)
                        if same:
                            nb_in += 1
                        else:
                            nb_out += 1
    P("=" * 78)
    P("doc pdvd/53 survey census -- arm %s" % a.arm)
    P("  candidates %d (is_stm %d)" % (n_cand, n_stm))
    for name, v in (("survey segments", nseg), ("survey clusters", nclus),
                    ("survey unfit clusters", nunfit)):
        A = np.asarray(v)
        P("  %-22s per candidate: mean %5.2f  p50 %3.0f  p90 %4.1f  max %3d  total %d"
          % (name, A.mean(), np.median(A), np.percentile(A, 90), A.max(), A.sum()))

    if a.base_dir and a.base_arm:
        b = []
        for d, fp in arm_events(a.base_dir):
            try:
                t = uproot.open(fp)["T_stm_michel"].arrays(["cluster_id"], library="np")
            except Exception:
                continue
            b.append(len(t["cluster_id"]))
        P("  base arm %s: %d candidates over %d events"
          % (a.base_arm, sum(b), len(b)))

    P("")
    P("WHY each surveyed segment was left unclaimed (one row per SEGMENT):")
    tot = sum(rej.values()) or 1
    for code in sorted(rej):
        P("  %2d  %-46s %5d  %5.1f%%" % (code, REJ.get(code, "?"), rej[code],
                                         100.0 * rej[code] / tot))
    P("  %-50s %5d" % ("total", tot))

    P("")
    P("HOW CLOSE the body exclusions were  (margin = d_stop - d_body, cm;")
    P("a NEGATIVE margin is a rejection, and a margin near zero is a coin flip):")
    for code in (4, 6):
        A = np.asarray(margin[code])
        if not A.size:
            P("  %2d  %-40s (none)" % (code, REJ[code]))
            continue
        P("  %2d  %-40s n=%d  p10 %7.3f  p50 %7.3f  p90 %7.3f"
          % (code, REJ[code], A.size, np.percentile(A, 10), np.median(A),
             np.percentile(A, 90)))
        P("      rejected by less than 1 mm: %d of %d"
          % (int((np.abs(A) < 0.1).sum()), A.size))
    if nearest_rej6:
        nearest_rej6.sort(key=lambda r: abs(r[0]))
        P("")
        P("  the ten narrowest body-exclusion margins:")
        P("      %-14s %-6s %-9s %-4s %8s %8s %8s" %
          ("event", "clus", "seg", "gate", "margin", "d_stop", "d_body"))
        for m, ev, cid, sid, code, ds, db in nearest_rej6[:10]:
            P("      %-14s %-6d %-9d %-4d %8.3f %8.2f %8.2f"
              % (ev, cid, sid, code, m, ds, db))

    P("")
    P("WHERE the surveyed segments live (the doc pdhd/13 sec 4 trap):")
    P("  same Q-L bundle as the candidate : %d" % nb_in)
    P("  ANOTHER flash / t0               : %d" % nb_out)
    P("  (the survey admits only same-bundle clusters, so a non-zero second row")
    P("   would be a defect, not a finding.)")

    txt = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
