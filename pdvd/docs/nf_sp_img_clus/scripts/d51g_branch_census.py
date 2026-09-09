#!/usr/bin/env python3
"""doc pdvd/51 -- ask EVERY branch of T_stm_michel what this round moved.

Under the doc pdhd/14 waiver this module ships new behaviour default-ON, so the
substitute for a byte-identical gate is a complete census: not "the branches I
expect to move did", but "every branch was asked, and here is the partition".
Two commits had to widen a 23-name hand list before doc pdhd/16's claim was
about the tree rather than about the list (feedback_rederive_from_primary_source).

Three comparisons, and the decomposition matters:

  LEGACY EQUIVALENCE   d51gvleg vs d16vnu
      Same input, same binary as the ON arm, stop_gamma_enable=false.  With the
      feature off the companion admission radius is michel_dot_radius_cm again,
      exactly as before, so NOTHING may move on the shared scalar branches.
      This is the pure code-change gate and it carries no preload perturbation.

  THE FEATURE          d51gv vs d51gvleg
      The whole effect of the round: the new objects, plus the perturbation from
      admitting more companions.  Admitting a companion feeds it to
      TrackFitting::preload_clusters, whose blobs enter prepare_data(), so the
      candidate's OWN muon dQ/dx can move (doc pdhd/15 sec 7 measured 6 movers
      and one is_stm flip from 6 new companions).  Every mover is named.

  ROLES                T_stm_michel_pts, either pair
      role 4 -> 3 for a bridged Michel piece is unconditional, so it moves even
      on the legacy arm.  That is not a gate failure; what IS checked is that
      the migration is exactly the bridged-piece population and that no point's
      (x, y, z, q, seg_id) changed.

`n_stop_gammas > 0` is a LOWER bound on the perturbed set: a companion can be
admitted (and so perturb the fit) and then fail the post-fit energy window, in
which case it leaves no trace in the tree.  The split is reported as such.
"""
import argparse, glob, os, sys
import numpy as np
import uproot

KEY = ("event", "cluster_id")


def load(pattern, arm):
    """{(event, cluster_id): {branch: value}} plus the branch name set."""
    out, names = {}, None
    for d in sorted(glob.glob(pattern)):
        fp = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(fp):
            continue
        try:
            a = uproot.open(fp)["T_stm_michel"].arrays(library="np")
        except Exception as e:
            print("SKIP %s: %s" % (os.path.basename(d), e), file=sys.stderr)
            continue
        ev = os.path.basename(d)[: -len(arm) - 1]
        if names is None:
            names = set(a.keys())
        else:
            names &= set(a.keys())
        for i in range(len(a["cluster_id"])):
            out[(ev, int(a["cluster_id"][i]))] = {k: a[k][i] for k in a}
    return out, (names or set())


def load_pts(pattern, arm):
    """{(event, cluster_id): {(role, seg_id): [(x,y,z,q) ...]}}"""
    out = {}
    for d in sorted(glob.glob(pattern)):
        fp = os.path.join(d, "tracking-pr.root")
        if not os.path.exists(fp):
            continue
        try:
            a = uproot.open(fp)["T_stm_michel_pts"].arrays(library="np")
        except Exception:
            continue
        ev = os.path.basename(d)[: -len(arm) - 1]
        for i in range(len(a["cluster_id"])):
            k = (ev, int(a["cluster_id"][i]))
            out.setdefault(k, []).append(
                (int(a["role"][i]), int(a["seg_id"][i]),
                 round(float(a["x"][i]), 6), round(float(a["y"][i]), 6),
                 round(float(a["z"][i]), 6), round(float(a["q"][i]), 6)))
    return out


def same(u, v):
    fu, fv = isinstance(u, (float, np.floating)), isinstance(v, (float, np.floating))
    if fu or fv:
        if not np.isfinite(u) and not np.isfinite(v):
            return True
        return bool(u == v)          # BIT equality, deliberately not a tolerance
    return bool(u == v)


def compare(before, after, bnames, anames, label, out, split_key=None):
    lines = []
    P = lines.append
    shared = sorted(bnames & anames)
    added = sorted(anames - bnames)
    dropped = sorted(bnames - anames)
    keys = sorted(set(before) & set(after))
    P("=" * 78)
    P("%s" % label)
    P("  matched candidates      : %d  (before %d, after %d)"
      % (len(keys), len(before), len(after)))
    P("  branches shared / new / dropped : %d / %d / %d"
      % (len(shared), len(added), len(dropped)))
    if added:
        P("  NEW branches   : %s" % ", ".join(added))
    if dropped:
        P("  DROPPED        : %s" % ", ".join(dropped))
    moved = {}
    movers = set()
    for k in keys:
        for b in shared:
            if not same(before[k][b], after[k][b]):
                moved.setdefault(b, []).append(k)
                movers.add(k)
    P("  candidates BIT-IDENTICAL on all %d shared branches : %d / %d"
      % (len(shared), len(keys) - len(movers), len(keys)))
    if moved:
        P("  branches that moved, and on how many candidates:")
        for b, ks in sorted(moved.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            P("      %-26s %5d" % (b, len(ks)))
    else:
        P("  NO shared branch moved on any candidate.")
    if split_key:
        with_new = {k for k in movers if float(after[k].get(split_key, 0)) > 0}
        P("  movers with %s > 0 : %d of %d  (a LOWER bound on the perturbed set --"
          % (split_key, len(with_new), len(movers)))
        P("      a companion can be admitted, perturb the fit, and then fail the")
        P("      post-fit energy window, leaving no trace in the tree)")
    # verdict-relevant movers, named individually
    vb = [b for b in ("is_stm", "reject_bits", "michel_found", "michel_conn_type",
                      "muon_ke_best", "contrast", "muon_len") if b in shared]
    flips = [k for k in movers if "is_stm" in shared and not same(before[k]["is_stm"], after[k]["is_stm"])]
    P("  is_stm FLIPS : %d" % len(flips))
    for k in sorted(flips):
        P("      %-14s cl %4d  is_stm %d -> %d  contrast %.4f -> %.4f  muon_len %.3f -> %.3f"
          % (k[0], k[1], before[k]["is_stm"], after[k]["is_stm"],
             before[k].get("contrast", float("nan")), after[k].get("contrast", float("nan")),
             before[k].get("muon_len", float("nan")), after[k].get("muon_len", float("nan"))))
    if movers and len(movers) <= 40:
        P("  every mover, on the verdict-relevant branches:")
        for k in sorted(movers):
            bits = []
            for b in vb:
                u, v = before[k][b], after[k][b]
                if not same(u, v):
                    bits.append("%s %s->%s" % (b, u, v))
            P("      %-14s cl %4d  %s" % (k[0], k[1], "; ".join(bits) or "(only non-verdict branches)"))
    txt = "\n".join(lines)
    print(txt)
    with open(out, "a") as fh:
        fh.write(txt + "\n")
    return movers


def compare_pts(before, after, label, out):
    lines = []; P = lines.append
    keys = sorted(set(before) & set(after))
    P("=" * 78)
    P("%s  (T_stm_michel_pts)" % label)
    n_same_geom = n_role_moved = n_other = 0
    role_hist_b, role_hist_a = {}, {}
    migrated = []
    for k in keys:
        b, a = before[k], after[k]
        for r, s, x, y, z, q in b: role_hist_b[r] = role_hist_b.get(r, 0) + 1
        for r, s, x, y, z, q in a: role_hist_a[r] = role_hist_a.get(r, 0) + 1
        gb = sorted((s, x, y, z, q) for r, s, x, y, z, q in b)
        ga = sorted((s, x, y, z, q) for r, s, x, y, z, q in a)
        if gb != ga:
            n_other += 1
            continue
        n_same_geom += 1
        rb = sorted((s, x, y, z, q, r) for r, s, x, y, z, q in b)
        ra = sorted((s, x, y, z, q, r) for r, s, x, y, z, q in a)
        if rb != ra:
            n_role_moved += 1
            moved43 = all(u[5] == 4 and v[5] == 3 for u, v in zip(rb, ra) if u[5] != v[5])
            migrated.append((k, moved43))
    P("  candidates with IDENTICAL point geometry (seg_id,x,y,z,q) : %d / %d"
      % (n_same_geom, len(keys)))
    P("  of those, role labels moved on : %d" % n_role_moved)
    if migrated:
        pure = sum(1 for _, ok in migrated if ok)
        P("  role migrations that are PURELY 4 -> 3 : %d / %d" % (pure, len(migrated)))
        for k, ok in sorted(migrated)[:20]:
            P("      %-14s cl %4d  %s" % (k[0], k[1], "4->3 only" if ok else "OTHER ROLE CHANGE"))
    P("  candidates whose point geometry changed (new gamma points, or the")
    P("      preload perturbation moving the fit)                  : %d" % n_other)
    P("  role histogram before : %s" % dict(sorted(role_hist_b.items())))
    P("  role histogram after  : %s" % dict(sorted(role_hist_a.items())))
    txt = "\n".join(lines); print(txt)
    with open(out, "a") as fh:
        fh.write(txt + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True, help="glob, e.g. 'pdvd/work/*_d16vnu'")
    ap.add_argument("--after", required=True)
    ap.add_argument("--before-arm", required=True)
    ap.add_argument("--after-arm", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split-key", default="n_stop_gammas")
    ap.add_argument("--pts", action="store_true", help="also compare T_stm_michel_pts")
    a = ap.parse_args()
    b, bn = load(a.before, a.before_arm)
    c, cn = load(a.after, a.after_arm)
    if not b or not c:
        sys.exit("empty arm: before %d, after %d" % (len(b), len(c)))
    open(a.out, "w").close()
    compare(b, c, bn, cn, a.label or ("%s -> %s" % (a.before_arm, a.after_arm)),
            a.out, a.split_key if a.split_key in cn else None)
    if a.pts:
        compare_pts(load_pts(a.before, a.before_arm), load_pts(a.after, a.after_arm),
                    a.label or ("%s -> %s" % (a.before_arm, a.after_arm)), a.out)
    print("\nwrote %s" % a.out, file=sys.stderr)


if __name__ == "__main__":
    main()
