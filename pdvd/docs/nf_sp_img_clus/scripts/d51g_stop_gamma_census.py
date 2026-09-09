#!/usr/bin/env python3
"""doc pdvd/51 -- the muon-capture gamma at an STM stop: is it there, and how far?

Reproduces every number in doc pdvd/51 sec 3 (the population) and sec 4 (the
radius).  Reads only committed arm output -- `tracking-pr.root` (T_stm_michel,
T_cluster, T_rec_charge) and `mabc-pr.zip`'s `clustering-global` layer -- so it
runs with no wire-cell rerun.

THE QUESTION.  A mu- that stops in argon is captured by a nucleus far more often
than it decays, and the capture leaves de-excitation gammas.  A gamma is
neutral: it travels, then deposits a compact blob somewhere off the muon's axis.
CheckSTM_Michel's companion search is a MICHEL search -- michel_dot_radius_cm is
15 cm -- so a blob 27 cm away is never even admitted to the fitter.  Before
widening anything we must know whether those blobs are physics or background.

WHAT IT MEASURES, and why each piece is needed:

  A  the population: length, points, charge and charge-derived energy of the
     compact same-bundle blobs that sit past the stop.
  B  shell density around three ANCHORS on the same muons, r^3-normalised.
     A volume-filling background is FLAT in the r^3-normalised column; a real
     emission from the anchor falls.  The three anchors are NOT three equally
     good nulls, and the doc must not pretend they are:
       stop  -- where capture gammas come from.
       entry -- the doc pdhd/13 sec 6 null.  BOUNDARY-BIASED: an entry sits on
                a detector face, so roughly half its sphere is outside the
                detector.  That alone buys a factor ~2, which is the order of
                the stop/entry ratio measured here -- so the excess over entry
                is an upper bound on the effect, not a measurement of it.
       mid   -- the fit point at rr ~ muon_len/2.  DEGENERATE BY CONSTRUCTION,
                and reported only as a predicate sanity check: the body test is
                not anchor-symmetric.  At an endpoint the body lies to one side,
                so a blob past it is far from the body; at a mid-track anchor
                the track runs both ways, so almost nothing can be closer to the
                anchor than to the body.  Its near-zero counts say the predicate
                really does demand "past an endpoint" -- they are not a null.
  B2 WHAT "FLAT" LOOKS LIKE: the same predicate, the same STOP anchor, the same
     shells -- but companions from a DIFFERENT Q-L bundle.  Those are unrelated
     to this muon by construction, so their shell density measures the ambient
     compact-blob density of the event, and it comes out FLAT (~0.6 per
     candidate per 1e6 cm^3 from 30 to 150 cm).  That is the point of the
     column: it validates the r^3 normalisation empirically instead of
     asserting it, and it is what the same-bundle stop-anchored density (which
     falls ~4000x over the same span) has to be read against.

     IT IS NOT A PURITY DENOMINATOR, and the S/B column must not be read as one.
     There are ~340 foreign clusters per event against ~6 same-bundle ones, so
     equal DENSITY means the same-bundle blobs are ~50x more concentrated at the
     stop per available cluster.  The algorithm never admits a foreign cluster
     (the matched_flash_gid test), so its background is same-bundle blobs that
     are not capture gammas -- and the ENTRY anchor, not this, is the handle on
     that.
  C  the mu- signature: capture gives NO Michel and gammas; decay gives a Michel
     and no capture gammas.  So the blob rate must be HIGHER on the
     michel_found==0 population.  This is a free, blind, absolute test -- it
     owes nothing to any threshold in this script.
  D  the ring scan: for every candidate outer radius, the blob count, the
     candidates touched, the excess over each control, and C's ratio -- the
     table that sets stop_gamma_radius_cm.

The anchor predicate is the C++ one, generalised (CheckSTM_Michel.cxx:1467-1474):
a blob belongs to anchor A when its closest approach to A is inside the ring,
its length is under the cap, and it is CLOSER TO A THAN TO THE MUON BODY, where
"body" excludes the `--body-exclusion` cm around A itself.  Using the identical
predicate for all three anchors is what makes the controls controls.

TRAPS OBSERVED (feedback_pctree_dump_offline_traps):
  * Bee `*-global.json` writes a cluster with no t0 at |x| ~ 1.48e8 cm.  Cut
    |x| < 1e4 before any geometry and report how many points that dropped.
  * The bundle key is (flash_id, cluster_t0_us) -- BOTH.  A flash alone is not a
    unique bundle key (feedback_flash_not_unique_bundle_key).
  * T_rec_charge's `cluster_id` is the MOTHER's id; select segments with
    `sub_cluster_id // 1000` (PdvdPrMagnifyTrackingVisitor.cxx:737,857,905).
"""
import argparse, csv, glob, json, os, sys, zipfile
import numpy as np
import uproot

# The KineChargeOptions TRACK pair and W, the same constants CheckSTM_Michel's
# stm_michel_charge_to_energy uses (doc pdhd/15 sec 6).  Used here only to put a
# blob's charge on a MeV scale for the reader; nothing in the census depends on
# the absolute value.
RECOM, FUDGE, W_EV = 0.7, 0.95, 23.6


def charge_to_mev(q_e):
    return q_e / RECOM / FUDGE * W_EV / 1e6


def bee_points(zip_path):
    """The clustering-global layer as (P[n,3] cm, cluster_id, q), sentinels cut."""
    with zipfile.ZipFile(zip_path) as z:
        d = json.loads(z.read("data/0/0-clustering-global.json"))
    x = np.asarray(d["x"], float); y = np.asarray(d["y"], float); z_ = np.asarray(d["z"], float)
    cid = np.asarray(d["cluster_id"], int); q = np.asarray(d["q"], float)
    ok = np.abs(x) < 1e4                       # trap 5: the no-t0 sentinel
    return np.stack([x[ok], y[ok], z_[ok]], 1), cid[ok], q[ok], int((~ok).sum())


def anchor_rows(sm, i, tc, rc, P, C, Q, body_excl):
    """Every same-bundle companion of candidate i, measured against 3 anchors."""
    cid = int(sm["cluster_id"][i])
    j = np.where(tc["cluster_id"] == cid)[0]
    if not len(j):
        return []
    j = j[0]
    same = (tc["flash_id"] == tc["flash_id"][j]) & (tc["cluster_t0_us"] == tc["cluster_t0_us"][j])
    others = [(int(c), 1) for c in tc["cluster_id"][same] if int(c) != cid]
    # B2: the fair control -- every OTHER-bundle cluster, same anchor, same
    # predicate.  Capped by the ring test below, so the cost is bounded.
    others += [(int(c), 0) for c in tc["cluster_id"][~same] if int(c) != cid]

    fit = (rc["sub_cluster_id"] // 1000 == cid) & (rc["flag_vertex"] == 0)
    if fit.sum() < 5:
        return []
    MU = np.stack([rc["x"][fit], rc["y"][fit], rc["z"][fit]], 1)

    stop = np.array([sm["stop_x"][i], sm["stop_y"][i], sm["stop_z"][i]])
    entry = np.array([sm["entry_x"][i], sm["entry_y"][i], sm["entry_z"][i]])
    # mid: the fit point whose distance from the stop is closest to half the
    # muon length -- a body point, boundary-neutral by construction.
    dstop_fit = np.linalg.norm(MU - stop, axis=1)
    mid = MU[np.argmin(np.abs(dstop_fit - 0.5 * float(sm["muon_len"][i])))]

    out = []
    for c, in_bundle in others:
        m = C == c
        if not m.sum():
            continue
        B = P[m]
        k = np.where(tc["cluster_id"] == c)[0]
        row = dict(ev="", cl=cid, nb=c, in_bundle=in_bundle,
                   npts=int(m.sum()), q=float(Q[m].sum()),
                   len_cm=float(tc["length_cm"][k[0]]) if len(k) else -1.0,
                   michel_found=int(sm["michel_found"][i]),
                   michel_conn=int(sm["michel_conn_type"][i]),
                   n_dots=int(sm["n_dots"][i]), is_stm=int(sm["is_stm"][i]),
                   muon_len=float(sm["muon_len"][i]))
        for name, A in (("stop", stop), ("entry", entry), ("mid", mid)):
            d_a = float(np.linalg.norm(B - A, axis=1).min())
            body = MU[np.linalg.norm(MU - A, axis=1) >= body_excl]
            d_b = (float(np.min(np.linalg.norm(B[:, None, :] - body[None, :, :], axis=2)))
                   if len(body) else 1e9)
            row["d_" + name] = d_a
            row["dbody_" + name] = d_b
        if in_bundle or row["d_stop"] <= 150.0:
            out.append(row)
    return out


def from_arm(a):
    """Section C, re-derived from what the chain ACCEPTED, not from a predicate.

    The offline predicate in this script motivated the design; it is not the
    shipped selection, and the two can disagree -- doc pdvd/51 sec 6.5 is a
    round where they did, by a factor that inverted the sign.  So the number the
    doc quotes has to come from the arm.
    """
    dirs = sorted(set(d for g in a.globs for d in glob.glob(g)))
    n_cand = n_obj = 0
    mf, ng, ke, dmin = [], [], [], []
    for d in dirs:
        fp = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(fp):
            continue
        try:
            m = uproot.open(fp)["T_stm_michel"].arrays(library="np")
        except Exception:
            continue
        if "n_stop_gammas" not in m:
            continue
        for i in range(len(m["cluster_id"])):
            if a.is_stm_only and int(m["is_stm"][i]) != 1:
                continue
            n_cand += 1
            g = int(m["n_stop_gammas"][i]); n_obj += g
            mf.append(int(m["michel_found"][i])); ng.append(g)
            if g > 0:
                ke.append(float(m["stop_gamma_ke_tot"][i]))
                dmin.append(float(m["stop_gamma_dis_min"][i]))
    if not n_cand:
        sys.exit("no candidates with doc-51 branches in %r" % (a.globs,))
    mf = np.array(mf); ng = np.array(ng)
    L = []
    P = L.append
    P("doc pdvd/51 -- the mu- signature, measured on the objects the CHAIN accepted")
    P("arm globs   : %s" % " ".join(a.globs))
    P("population  : %s" % ("is_stm only" if a.is_stm_only else "all candidates"))
    P("candidates %d, gamma objects %d on %d candidates (%.1f %%)"
      % (n_cand, n_obj, int((ng > 0).sum()), 100.0 * (ng > 0).mean()))
    if ke:
        P("stop_gamma_ke_tot  p10/p50/p90 %.2f / %.2f / %.2f MeV, max %.2f"
          % (*np.percentile(ke, [10, 50, 90]), max(ke)))
        P("stop_gamma_dis_min p10/p50/p90 %.1f / %.1f / %.1f cm"
          % tuple(np.percentile(dmin, [10, 50, 90])))
    r0 = ng[mf == 0].mean() if (mf == 0).any() else float("nan")
    r1 = ng[mf == 1].mean() if (mf == 1).any() else float("nan")
    P("")
    P("mu- signature -- capture gives NO Michel and gammas, decay gives a Michel:")
    P("  michel_found == 0 : %3d candidates, %.3f objects/candidate, %d with >= 1"
      % (int((mf == 0).sum()), r0, int((ng[mf == 0] > 0).sum())))
    P("  michel_found == 1 : %3d candidates, %.3f objects/candidate, %d with >= 1"
      % (int((mf == 1).sum()), r1, int((ng[mf == 1] > 0).sum())))
    P("  RATIO (no-Michel / Michel) : %.2f   -- must be > 1 if these are capture gammas"
      % (r0 / r1 if r1 > 0 else float("inf")))
    txt = "\n".join(L)
    print(txt)
    with open(a.out + "_from_arm.txt", "w") as fh:
        fh.write(txt + "\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("globs", nargs="+", help="work-dir globs, e.g. 'pdvd/work/*_d16vnu'")
    ap.add_argument("--det", required=True)
    ap.add_argument("--out", required=True, help="output prefix")
    ap.add_argument("--is-stm-only", action="store_true", default=True)
    ap.add_argument("--all-candidates", dest="is_stm_only", action="store_false")
    ap.add_argument("--body-exclusion", type=float, default=5.0,
                    help="cm around the anchor that is not 'body' (C++ dot_body_exclusion_cm)")
    ap.add_argument("--max-len", type=float, default=10.0,
                    help="cm, the compactness cap a gamma blob must pass")
    ap.add_argument("--inner", type=float, default=15.0,
                    help="cm, the inner edge of the ring (the Michel radius already admits inside)")
    ap.add_argument("--from-arm", action="store_true",
                    help="skip the offline predicate; measure section C on the objects the "
                         "CHAIN ITSELF accepted (T_stm_michel.n_stop_gammas).  This is the "
                         "measurement; the offline predicate is only the design study.")
    a = ap.parse_args()
    if a.from_arm:
        return from_arm(a)

    dirs = sorted(set(d for g in a.globs for d in glob.glob(g)))
    if not dirs:
        sys.exit("no work dirs matched %r" % (a.globs,))

    rows, nev, nsent, ncand = [], 0, 0, 0
    for d in dirs:
        fp, zp = os.path.join(d, "tracking-pr.root"), os.path.join(d, "mabc-pr.zip")
        if not (os.path.exists(fp) and os.path.exists(zp)):
            continue
        try:
            f = uproot.open(fp)
            sm = f["T_stm_michel"].arrays(library="np")
            tc = f["T_cluster"].arrays(library="np")
            rc = f["T_rec_charge"].arrays(library="np")
            P, C, Q, ns = bee_points(zp)
        except Exception as e:
            print("SKIP %s: %s" % (os.path.basename(d), e), file=sys.stderr)
            continue
        nev += 1; nsent += ns
        ev = os.path.basename(d).rsplit("_", 1)[0]
        for i in range(len(sm["cluster_id"])):
            if a.is_stm_only and int(sm["is_stm"][i]) != 1:
                continue
            ncand += 1
            for r in anchor_rows(sm, i, tc, rc, P, C, Q, a.body_exclusion):
                r["ev"] = ev
                rows.append(r)
    if not rows:
        sys.exit("no neighbour rows")

    fields = ["ev", "cl", "nb", "in_bundle", "npts", "q", "len_cm", "michel_found", "michel_conn",
              "n_dots", "is_stm", "muon_len",
              "d_stop", "dbody_stop", "d_entry", "dbody_entry", "d_mid", "dbody_mid"]
    with open(a.out + "_neighbours.tsv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})

    L = np.array([r["len_cm"] for r in rows])
    NP = np.array([r["npts"] for r in rows])
    QQ = np.array([r["q"] for r in rows])
    MF = np.array([r["michel_found"] for r in rows])
    IB = np.array([r["in_bundle"] for r in rows], bool)
    D = {k: np.array([r["d_" + k] for r in rows]) for k in ("stop", "entry", "mid")}
    DB = {k: np.array([r["dbody_" + k] for r in rows]) for k in ("stop", "entry", "mid")}
    cands = sorted(set((r["ev"], r["cl"]) for r in rows))
    cand_mf = {(r["ev"], r["cl"]): r["michel_found"] for r in rows}
    ncand_nb = len(cands)

    def belongs(anchor, lo, hi, maxlen, bundle=True):
        """The C++ predicate, generalised to any anchor (see the module docstring).

        bundle=True is the signal class (same Q-L bundle); bundle=False is the
        B2 accidental control (a different bundle, same anchor, same ring)."""
        m = (D[anchor] > lo) & (D[anchor] <= hi) & (L <= maxlen) & (DB[anchor] >= D[anchor])
        return m & (IB if bundle else ~IB)

    lines = []
    P_ = lines.append
    P_("doc pdvd/51 -- stop-gamma census")
    P_("arm globs           : %s" % " ".join(a.globs))
    P_("detector            : %s" % a.det)
    P_("events / candidates : %d / %d  (%s)"
       % (nev, ncand, "is_stm only" if a.is_stm_only else "all candidates"))
    P_("candidates with >=1 neighbour of any bundle : %d" % len(cands))
    P_("neighbour rows      : %d" % len(rows))
    P_("Bee sentinel points dropped (|x| >= 1e4 cm) : %d" % nsent)
    P_("predicate           : ring < d <= R, length <= %.1f cm, closer to the anchor"
       % a.max_len)
    P_("                      than to the body (body excludes %.1f cm around the anchor)"
       % a.body_exclusion)
    P_("")

    # ---- A: the population -------------------------------------------------
    sel = belongs("stop", a.inner, 60.0, 25.0)
    P_("[A] compact same-bundle blobs %g < d_stop <= 60 cm (length <= 25 cm): n = %d"
       % (a.inner, sel.sum()))
    if sel.sum():
        for nm, arr in (("d_stop cm", D["stop"][sel]), ("length cm", L[sel]),
                        ("npoints", NP[sel].astype(float)), ("charge e", QQ[sel]),
                        ("E MeV (track pair)", charge_to_mev(QQ[sel]))):
            P_("    %-20s p10 %10.3f  p50 %10.3f  p90 %10.3f  max %10.3f"
               % (nm, *[np.percentile(arr, p) for p in (10, 50, 90)], arr.max()))
    P_("")

    # ---- B: r^3-normalised shell density around three anchors ---------------
    P_("[B] shell counts and r^3-normalised density, compact (<= 25 cm) blobs")
    P_("    %-12s %22s %22s %22s" % ("", "STOP", "ENTRY (boundary-biased)", "MID (body, neutral)"))
    P_("    %-12s %10s %11s %10s %11s %10s %11s"
       % ("shell cm", "n", "n/r^3*1e4", "n", "n/r^3*1e4", "n", "n/r^3*1e4"))
    edges = [0, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150]
    shell_rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        vol = hi ** 3 - lo ** 3
        cells = []
        for k in ("stop", "entry", "mid"):
            n = int(belongs(k, lo, hi, 25.0).sum())
            cells += [n, n / vol * 1e4]
        shell_rows.append([lo, hi] + cells)
        P_("    %5d-%-6d %10d %11.4f %10d %11.4f %10d %11.4f" % (lo, hi, *cells))
    P_("    A volume-filling background is FLAT in the n/r^3 columns.")
    P_("    MID is a predicate sanity check, not a null -- see the docstring.")
    P_("")

    # ---- B2: the fair control -- foreign bundle, same anchor, same ring -----
    P_("[B2] SAME stop anchor, SAME predicate, DIFFERENT Q-L bundle: what FLAT looks")
    P_("     like.  Density = blobs per candidate per 1e6 cm^3 of shell volume.")
    P_("     The foreign column is the event's ambient compact-blob density and is")
    P_("     expected to be flat; it validates the r^3 normalisation.  S/B is NOT a")
    P_("     purity -- ~340 foreign clusters per event against ~6 same-bundle ones.")
    P_("    %5s-%-6s %10s %12s %10s %12s %9s" %
       ("lo", "hi", "n_bundle", "dens_bundle", "n_foreign", "dens_foreign", "S/B"))
    b2_rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        vol = 4.0 / 3.0 * np.pi * (hi ** 3 - lo ** 3) * ncand_nb
        nb_ = int(belongs("stop", lo, hi, 25.0, True).sum())
        nf_ = int(belongs("stop", lo, hi, 25.0, False).sum())
        db_, df_ = nb_ / vol * 1e6, nf_ / vol * 1e6
        sb = db_ / df_ if df_ > 0 else float("inf")
        b2_rows.append([lo, hi, nb_, db_, nf_, df_, sb])
        P_("    %5d-%-6d %10d %12.4f %10d %12.4f %9.2f" % (lo, hi, nb_, db_, nf_, df_, sb))
    P_("")

    # ---- C + D: the ring scan and the mu- signature -------------------------
    P_("[C+D] ring scan: outer radius R, inner edge %g cm, length <= %.1f cm"
       % (a.inner, a.max_len))
    P_("      exc_ent = 1 - n_entry/n_stop: the ENTRY anchor's implied purity floor,")
    P_("      the one control that is same-muon, same-bundle and same-predicate.  Its")
    P_("      bias is geometric and one-signed (doc pdhd/13 sec 6), so it is an UPPER")
    P_("      bound on purity.  n_foreign is the ambient count, NOT a background")
    P_("      estimate for this algorithm -- see B2.")
    P_("      mu- signature: blobs per candidate, michel_found 0 vs 1.  Capture")
    P_("      (no Michel) must be the RICHER population if these are real.")
    P_("    %5s %6s %6s %8s %9s %8s %8s %7s"
       % ("R cm", "blobs", "cands", "n_entry", "n_foreign", "exc_ent", "r(mf0)", "ratio"))
    ring_rows = []
    n_mf0 = sum(1 for c in cands if cand_mf[c] == 0)
    n_mf1 = len(cands) - n_mf0
    for R in (20, 25, 30, 35, 40, 45, 50, 60, 80, 100):
        s = belongs("stop", a.inner, R, a.max_len)
        ne = int(belongs("entry", a.inner, R, a.max_len).sum())
        nm = int(belongs("stop", a.inner, R, a.max_len, False).sum())
        ns_ = int(s.sum())
        touched = len(set((rows[i]["ev"], rows[i]["cl"]) for i in np.flatnonzero(s)))
        k0 = int((s & (MF == 0)).sum()); k1 = int((s & (MF == 1)).sum())
        r0 = k0 / n_mf0 if n_mf0 else float("nan")
        r1 = k1 / n_mf1 if n_mf1 else float("nan")
        ratio = r0 / r1 if r1 > 0 else float("inf")
        exc_e = 1 - ne / ns_ if ns_ else float("nan")
        exc_m = 1 - nm / ns_ if ns_ else float("nan")   # foreign-bundle, raw count
        ring_rows.append(dict(R=R, blobs=ns_, cands=touched, n_entry=ne, n_foreign=nm,
                              exc_entry=exc_e, exc_foreign=exc_m, rate_mf0=r0,
                              rate_mf1=r1, ratio=ratio))
        P_("    %5d %6d %6d %8d %9d %8.3f %7.3f %7.2f"
           % (R, ns_, touched, ne, nm, exc_e, r0, ratio))
    P_("")
    P_("      candidates: michel_found==0 %d, ==1 %d" % (n_mf0, n_mf1))

    with open(a.out + "_rings.tsv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ring_rows[0].keys()), delimiter="\t")
        w.writeheader()
        for r in ring_rows:
            w.writerow(r)
    with open(a.out + "_shells.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["lo_cm", "hi_cm", "n_stop", "dens_stop", "n_entry", "dens_entry",
                    "n_mid", "dens_mid"])
        for r in shell_rows:
            w.writerow(r)
    with open(a.out + "_accidental.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["lo_cm", "hi_cm", "n_bundle", "dens_bundle", "n_foreign",
                    "dens_foreign", "s_over_b"])
        for r in b2_rows:
            w.writerow(r)

    txt = "\n".join(lines)
    print(txt)
    with open(a.out + "_summary.txt", "w") as fh:
        fh.write(txt + "\n")
    print("\nwrote %s_{neighbours,rings,shells}.tsv and _summary.txt" % a.out,
          file=sys.stderr)


if __name__ == "__main__":
    main()
