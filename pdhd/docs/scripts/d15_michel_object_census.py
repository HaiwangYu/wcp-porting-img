#!/usr/bin/env python3
"""doc pdhd/15 -- the Michel as ONE object: what the pieces are worth.

Reproduces every number in doc pdhd/15.  Two reference cases, both PDVD
039252_15:

  cluster 91  a Michel IS found (attached, 11.2 cm) but the 7.8 cm piece
              4.3 cm past its tip is added to the shower and never reaches the
              energy -- 16.2 MeV reported for a 29.2 MeV electron.
  cluster 77  the Michel is a 20.1 cm same-bundle cluster 1.91 cm from the
              stop that never entered the PR at all (doc pdhd/13's admission
              cap), so michel_found=0 with nothing at the stop.

What it measures, over an arm (or a BEFORE/AFTER pair of arms):

  A  the accounting gap: candidates with michel_found=1 AND n_dots>0, and the
     fraction of the object's energy that the doc-14 code left out
     (dots_ke_dqdx / (michel_ke_best + dots_ke_dqdx) on a BEFORE arm).
  B  the admission gap: same-bundle clusters within michel_dot_radius_cm of
     the stop that are LONGER than the old dot_max_len_cm, split at the new
     companion_max_len_cm, with their length so a Michel-sized neighbour can
     be told from another cosmic.
  C  the radius clip: for each such neighbour, the fraction of its charge
     lying beyond michel_dot_radius_cm of the stop -- the charge a PER-SEGMENT
     radius test would drop even after the cluster was admitted.
  D  the population by connection type -- 1 attached, 2 bridged across a
     clustering gap, 3 charge only (a companion the fitter produced no segment
     for) -- and the stop->piece gap distribution, the measurement that decides
     whether a "bridge" threshold can be set at all.
  E  the charge->energy calibration: for candidates with exactly one dot
     segment, the dot cluster's own blob charge converted with the TRACK
     (0.7/0.95) and SHOWER (0.5/0.8) KineChargeOptions pairs, against the
     chain's own segment_cal_kine_dQdx for that piece.
  F  non-finite persisted fields, and the Michel energy spectrum against the
     52.8 MeV endpoint (a free absolute gate: an object gathering too much
     develops a population above it).

With --before and --after it also prints the per-branch movement between two
arms on the candidates whose companion set did NOT change, which is what
bounds the preload perturbation: admitting a companion feeds it to
TrackFitting::preload_clusters, so the candidate's OWN muon dQ/dx can move.
Each candidate builds its own TrackFitting and Graph (CheckSTM_Michel.cxx:837,
:850), so the perturbation cannot cross candidates.

Bundle key is (flash_id, cluster_t0_us) from T_cluster; a flash alone is not a
unique bundle key, so both fields are required.

Repro:
  cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
  python3 pdhd/docs/scripts/d15_michel_object_census.py \
      --before 'pdvd/work/*_d14vnu' --after 'pdvd/work/*_d15vnu' \
      --det pdvd --out /home/xqian/tmp/d15/d15v
  python3 pdhd/docs/scripts/d15_michel_object_census.py \
      --before 'pdhd/work/*_d14hnu' --after 'pdhd/work/*_d15hnu' \
      --det pdhd --out /home/xqian/tmp/d15/d15h
"""
import argparse, glob, json, os, sys, zipfile
import numpy as np
import uproot

# CheckSTM_Michel defaults.  OLD = through doc pdhd/14; NEW = doc pdhd/15.
# Neither ProtoDUNE bag sets any of these, so the C++ defaults are what ran.
DOT_MAX_LEN_OLD_CM = 10.0
COMPANION_MAX_LEN_NEW_CM = 25.0
MICHEL_DOT_RADIUS_CM = 15.0

# KineChargeOptions (NeutrinoPatternBase.h:40-67) and the W value.
TRACK_RECOM, TRACK_FUDGE = 0.7, 0.95
SHOWER_RECOM, SHOWER_FUDGE = 0.5, 0.8
W_EV = 23.6

MICHEL_ENDPOINT_MEV = 52.8      # (m_mu^2 + m_e^2) / (2 m_mu)

# The display's sample definition (doc pdhd/12).
MIN_PROFILE_PTS = 20
MIN_MUON_LEN_CM = 10.0


def q_to_mev(q, recom, fudge):
    return q / recom / fudge * W_EV / 1e6


def read_arm(pattern):
    """[(dir, T_stm_michel row dict, T_stm_michel_pts, T_cluster, bee points)]"""
    out = []
    for d in sorted(glob.glob(pattern)):
        rp = os.path.join(d, "tracking-pr.root")
        zp = os.path.join(d, "mabc-pr.zip")
        if not os.path.exists(rp):
            continue
        try:
            f = uproot.open(rp)
            keys = [k.split(";")[0] for k in f.keys()]
            if "T_stm_michel" not in keys:
                continue
            sm = f["T_stm_michel"].arrays(library="np")
            pts = f["T_stm_michel_pts"].arrays(library="np")
            tc = f["T_cluster"].arrays(library="np")
        except Exception as e:                       # a killed job leaves a short file
            print("  [skip] %s: %s" % (d, e), file=sys.stderr)
            continue
        bee = None
        if os.path.exists(zp):
            try:
                z = zipfile.ZipFile(zp)
                nm = [n for n in z.namelist() if n.endswith("clustering-global.json")]
                if nm:
                    g = json.loads(z.read(nm[0]))
                    bee = (np.array(g["x"]), np.array(g["y"]), np.array(g["z"]),
                           np.array(g["q"]), np.array(g["cluster_id"]))
            except Exception:
                bee = None
        out.append((d, sm, pts, tc, bee))
    return out


def in_sample(sm, i):
    return (sm["has_pass"][i] == 1 and sm["n_profile_pts"][i] >= MIN_PROFILE_PTS
            and sm["muon_len"][i] >= MIN_MUON_LEN_CM)


def neighbours(tc, bee, main_cid, stop, radius):
    """Same-bundle clusters whose closest point is within `radius` of `stop`.

    Returns (cid, length_cm, d_min, total_q, q_beyond_radius).
    """
    if bee is None:
        return []
    X, Y, Z, Q, CID = bee
    j = np.where(tc["cluster_id"] == main_cid)[0]
    if len(j) == 0:
        return []
    key = (tc["flash_id"][j[0]], tc["cluster_t0_us"][j[0]])
    out = []
    for jj in np.where(tc["flash_id"] == key[0])[0]:
        if abs(tc["cluster_t0_us"][jj] - key[1]) > 1e-6:
            continue
        c = int(tc["cluster_id"][jj])
        if c == main_cid:
            continue
        m = CID == c
        if not m.any():
            continue
        d = np.sqrt((X[m] - stop[0]) ** 2 + (Y[m] - stop[1]) ** 2 + (Z[m] - stop[2]) ** 2)
        if d.min() > radius:
            continue
        out.append((c, float(tc["length_cm"][jj]), float(d.min()),
                    float(Q[m].sum()), float(Q[m][d > MICHEL_DOT_RADIUS_CM].sum())))
    return out


def companion_key(tc, bee, main_cid, stop, cap):
    """The set of cluster ids CheckSTM_Michel would admit at length cap `cap`.

    Mirrors CheckSTM_Michel.cxx:871-884: same bundle, length <= cap, closest
    point within michel_dot_radius_cm of the stop.
    """
    return frozenset(c for c, L, d, q, qb in neighbours(tc, bee, main_cid, stop, MICHEL_DOT_RADIUS_CM)
                     if L <= cap)


def quant(v, name, unit=""):
    v = np.asarray(v, float)
    if v.size == 0:
        return "%s: none" % name
    return ("%s: n=%d  min %.2f  p25 %.2f  med %.2f  p75 %.2f  max %.2f %s"
            % (name, v.size, v.min(), np.percentile(v, 25), np.median(v),
               np.percentile(v, 75), v.max(), unit))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", help="glob of the pre-doc-15 arm (d14*)")
    ap.add_argument("--after", help="glob of the doc-15 arm (d15*)")
    ap.add_argument("--det", required=True, choices=("pdhd", "pdvd"))
    ap.add_argument("--out", help="prefix for the TSV dumps")
    a = ap.parse_args()

    rows_b, rows_a = [], []
    if a.before:
        rows_b = read_arm(a.before)
        print("BEFORE arm %s: %d event dirs" % (a.before, len(rows_b)))
    if a.after:
        rows_a = read_arm(a.after)
        print("AFTER  arm %s: %d event dirs" % (a.after, len(rows_a)))
    if not rows_b and not rows_a:
        raise SystemExit("no arm given")

    # ---------------- A: the accounting gap, measured on the BEFORE arm ------
    if rows_b:
        n_cand = n_stale = 0
        frac, add = [], []
        for d, sm, pts, tc, bee in rows_b:
            for i in range(len(sm["cluster_id"])):
                if not in_sample(sm, i):
                    continue
                n_cand += 1
                if sm["michel_found"][i] == 1 and sm["n_dots"][i] > 0:
                    n_stale += 1
                    base = float(sm["michel_ke_best"][i])
                    extra = float(sm["dots_ke_dqdx"][i])
                    add.append(extra)
                    frac.append(extra / max(base + extra, 1e-9))
        print("\n[A] accounting gap (BEFORE): %d candidates, %d with michel_found=1 & n_dots>0"
              % (n_cand, n_stale))
        if frac:
            print("    missing fraction: median %.3f  max %.3f  n(>0.2) %d"
                  % (np.median(frac), max(frac), int((np.array(frac) > 0.2).sum())))
            print("    " + quant(add, "dots_ke_dqdx left out", "MeV"))

    # ---------------- B/C: admission and the radius clip --------------------
    if rows_b:
        big, clip = [], []
        for d, sm, pts, tc, bee in rows_b:
            for i in range(len(sm["cluster_id"])):
                if not in_sample(sm, i):
                    continue
                stop = (sm["stop_x"][i], sm["stop_y"][i], sm["stop_z"][i])
                for c, L, dm, q, qb in neighbours(tc, bee, int(sm["cluster_id"][i]),
                                                  stop, MICHEL_DOT_RADIUS_CM):
                    if L <= DOT_MAX_LEN_OLD_CM:
                        continue
                    big.append((os.path.basename(d), int(sm["cluster_id"][i]), c, L, dm, q,
                                int(sm["michel_found"][i]), int(sm["n_dots"][i])))
                    if L <= COMPANION_MAX_LEN_NEW_CM and q > 0:
                        clip.append(qb / q)
        print("\n[B] admission: %d same-bundle neighbours within %.0f cm of a stop "
              "longer than the old %.0f cm cap" % (len(big), MICHEL_DOT_RADIUS_CM,
                                                   DOT_MAX_LEN_OLD_CM))
        adm = [b for b in big if b[3] <= COMPANION_MAX_LEN_NEW_CM]
        print("    of those, <= the new %.0f cm cap (admitted): %d ; longer (kept out): %s"
              % (COMPANION_MAX_LEN_NEW_CM, len(adm),
                 sorted(round(b[3], 1) for b in big if b[3] > COMPANION_MAX_LEN_NEW_CM)))
        for b in adm:
            print("      %-22s cl %4d <- cluster %4d  %6.1f cm  d %5.2f cm  %.3g e  "
                  "(michel_found %d, n_dots %d)" % b[:8])
        if clip:
            print("[C] charge of an ADMITTED neighbour lying beyond the %.0f cm radius: "
                  "median %.3f  max %.3f  (a per-segment radius test would drop it)"
                  % (MICHEL_DOT_RADIUS_CM, np.median(clip), max(clip)))

    # ---------------- D/E/F on whichever arms are given ----------------------
    for label, rows in (("BEFORE", rows_b), ("AFTER", rows_a)):
        if not rows:
            continue
        gap, ke, nonfinite, ncand = [], [], [], 0
        ke_named = []
        n_found = n_conn1 = n_conn2 = n_conn3 = n_pieces = 0
        calib_t, calib_s = [], []
        for d, sm, pts, tc, bee in rows:
            for i in range(len(sm["cluster_id"])):
                if not in_sample(sm, i):
                    continue
                ncand += 1
                for k in sm:
                    v = sm[k][i]
                    if isinstance(v, (float, np.floating)) and not np.isfinite(v):
                        nonfinite.append((os.path.basename(d), int(sm["cluster_id"][i]), k))
                if sm["michel_found"][i]:
                    n_found += 1
                ct = int(sm["michel_conn_type"][i])
                n_conn1 += ct == 1
                n_conn2 += ct == 2
                n_conn3 += ct == 3
                if "michel_n_pieces" in sm:
                    n_pieces += int(sm["michel_n_pieces"][i])
                if sm["michel_found"][i] or sm["n_dots"][i] > 0:
                    ke.append(float(sm["michel_ke_best"][i]))
                    ke_named.append((float(sm["michel_ke_best"][i]), os.path.basename(d),
                                     int(sm["cluster_id"][i]), ct,
                                     int(sm["michel_n_pieces"][i]) if "michel_n_pieces" in sm else 0,
                                     float(sm["michel_ke_core"][i]) if "michel_ke_core" in sm else 0.0,
                                     float(sm["dots_ke_dqdx"][i])))
                cid = int(sm["cluster_id"][i])
                sel = (pts["cluster_id"] == cid) & (pts["role"] == 4)
                if ct == 2 and sel.any():
                    stop = np.array([sm["stop_x"][i], sm["stop_y"][i], sm["stop_z"][i]])
                    P = np.stack([pts["x"][sel], pts["y"][sel], pts["z"][sel]], 1)
                    gap.append(float(np.linalg.norm(P - stop, axis=1).min()))
                # E: the charge calibration, single-piece items only
                if sm["n_dots"][i] == 1 and bee is not None and sel.any():
                    segs = set(int(s) for s in pts["seg_id"][sel])
                    if len(segs) == 1:
                        dot_cl = list(segs)[0] // 1000
                        m = bee[4] == dot_cl
                        if m.any():
                            e_dqdx = float(sm["dots_ke_dqdx"][i])
                            q = float(bee[3][m].sum())
                            if e_dqdx > 0:
                                calib_t.append(q_to_mev(q, TRACK_RECOM, TRACK_FUDGE) / e_dqdx)
                                calib_s.append(q_to_mev(q, SHOWER_RECOM, SHOWER_FUDGE) / e_dqdx)
        print("\n[D] %s: %d candidates; michel_found %d (attached %d, bridged %d, "
              "charge-only %d), total pieces %d"
              % (label, ncand, n_found, n_conn1, n_conn2, n_conn3, n_pieces))
        print("    " + quant(gap, "stop -> nearest bridged piece", "cm"))
        if gap:
            g = np.array(gap)
            print("    <=3 cm %d  <=5 cm %d  <=8 cm %d  (of %d)"
                  % ((g <= 3).sum(), (g <= 5).sum(), (g <= 8).sum(), g.size))
        if calib_t:
            print("[E] %s charge/dQdx on %d single-piece items: TRACK %.3f  SHOWER %.3f (medians)"
                  % (label, len(calib_t), np.median(calib_t), np.median(calib_s)))
        k = np.array(ke) if ke else np.array([])
        if k.size:
            print("[F] %s michel_ke_best: n=%d med %.1f p90 %.1f max %.1f MeV | > %.1f MeV: %d"
                  % (label, k.size, np.median(k), np.percentile(k, 90), k.max(),
                     MICHEL_ENDPOINT_MEV, int((k > MICHEL_ENDPOINT_MEV).sum())))
            over = [x for x in ke_named if x[0] > MICHEL_ENDPOINT_MEV]
            if over:
                print("      above the endpoint: %s"
                      % "; ".join("%s cl %d %.1f MeV (conn %d, %d pieces, core %.1f, "
                                  "pieces %.1f)" % (x[1], x[2], x[0], x[3], x[4], x[5], x[6])
                                  for x in sorted(over, key=lambda y: -y[0])))
        print("[F] %s non-finite persisted fields: %d %s"
              % (label, len(nonfinite), nonfinite[:5]))

    # ---------------- the preload perturbation ------------------------------
    if rows_b and rows_a:
        idx_b = {}
        for d, sm, pts, tc, bee in rows_b:
            ev = os.path.basename(d).rsplit("_", 1)[0]
            for i in range(len(sm["cluster_id"])):
                idx_b[(ev, int(sm["cluster_id"][i]))] = (sm, i, tc, bee)
        same, moved, changed_set = [], [], []
        PINS = ["muon_len", "contrast", "plateau_med", "ks_mu", "n_profile_pts", "is_stm",
                "muon_ke_best"]
        for d, sm, pts, tc, bee in rows_a:
            ev = os.path.basename(d).rsplit("_", 1)[0]
            for i in range(len(sm["cluster_id"])):
                key = (ev, int(sm["cluster_id"][i]))
                if key not in idx_b:
                    continue
                smb, j, tcb, beeb = idx_b[key]
                if not (in_sample(sm, i) or in_sample(smb, j)):
                    continue
                stop = (smb["stop_x"][j], smb["stop_y"][j], smb["stop_z"][j])
                old = companion_key(tcb, beeb, key[1], stop, DOT_MAX_LEN_OLD_CM)
                new = companion_key(tcb, beeb, key[1], stop, COMPANION_MAX_LEN_NEW_CM)
                rec = dict(ev=ev, cl=key[1],
                           **{p: (float(smb[p][j]), float(sm[p][i])) for p in PINS if p in sm and p in smb})
                (changed_set if old != new else same).append(rec)
        def bitcmp(rows_):
            n_id = 0
            for r in rows_:
                if all(r[p][0] == r[p][1] for p in PINS if p in r):
                    n_id += 1
            return n_id
        print("\n[G] preload perturbation, BEFORE vs AFTER, on %d matched candidates:"
              % (len(same) + len(changed_set)))
        print("    companion set UNCHANGED: %d, of which bit-identical on %s: %d"
              % (len(same), "/".join(PINS), bitcmp(same)))
        print("    companion set CHANGED  : %d, of which bit-identical: %d"
              % (len(changed_set), bitcmp(changed_set)))
        for r in changed_set:
            print("      %-16s cl %4d  " % (r["ev"], r["cl"])
                  + "  ".join("%s %.4g->%.4g" % (p, r[p][0], r[p][1])
                              for p in PINS if p in r and r[p][0] != r[p][1]))
        for r in same:
            diff = [p for p in PINS if p in r and r[p][0] != r[p][1]]
            if diff:
                print("      [!] UNCHANGED set but moved: %-16s cl %4d  " % (r["ev"], r["cl"])
                      + "  ".join("%s %.6g->%.6g" % (p, r[p][0], r[p][1]) for p in diff))
        if a.out:
            os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
            with open(a.out + "_movers.tsv", "w") as fh:
                fh.write("event\tcluster\tset_changed\t" + "\t".join(
                    "%s_before\t%s_after" % (p, p) for p in PINS) + "\n")
                for tag, rs in (("1", changed_set), ("0", same)):
                    for r in rs:
                        fh.write("%s\t%d\t%s\t" % (r["ev"], r["cl"], tag) + "\t".join(
                            "%.10g\t%.10g" % r[p] for p in PINS if p in r) + "\n")
            print("    wrote %s_movers.tsv" % a.out)


if __name__ == "__main__":
    main()
