#!/usr/bin/env python3
"""doc pdvd/59 (T1b) -- offline SIZING probe for the asymmetric kink clause,
run BEFORE writing find_first_kink's actual C++ change was authorised.

This is deliberately NOT a full find_first_kink reimplementation.
find_first_kink's real candidate rows are filtered by geometry this script
does not replicate (refl_angles > 20 && ave_angles > 10, the angle3 turn
tests, the dead-region/shorted-wire guards) -- only its CHARGE test
(sum_fQ/sum_bQ, 10-point MIP-fraction sums on either side of a row) is
reproduced here, and even that is an approximation: the real code sums dQ
then divides by summed dx (a charge-weighted mean); this script instead
averages the payload's already-computed per-point dQ/dx (`q`, e/cm) over a
10-LIVE-point window on each side, since the prep payload does not carry raw
per-row dQ/dx separately.  Zero-charge (non-live) points are excluded from
every window BEFORE the mean, per feedback_zero_charge_points_corrupt_medians
-- a window that cannot find 3 live points on a side is skipped, not
counted as a fake near-zero density.

What this answers: "does ANY point along the item's fitted profile show an
asymmetric charge structure (one side >= entry_mip, the other <= far_mip)
at all" -- a necessary-condition population size, not a verdict prediction.
The real arm (d59v) decides the actual recovered count and false-positive
rate, exactly as T1a's proxy (7 -> 2 real) and T1c's KS-inclusive probe
(3 -> 1 real) were sized offline and then measured for real.

Repro:
    cd wcp-porting-img
    python3 pdvd/docs/nf_sp_img_clus/scripts/d59_kink_asym_probe.py
"""
import argparse, collections, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, IMG + "/pdhd/stm_michel_scan")
import census_lib as C                                            # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--prep", default=C.PREP_DEFAULT)
ap.add_argument("--mip", type=float, default=55000.0, help="mip_dqdx, PDVD production value (e/cm)")
ap.add_argument("--live-frac", type=float, default=0.15, help="profile_min_dqdx_frac, PDVD production value")
ap.add_argument("--entry-mip", type=float, default=1.2)
ap.add_argument("--far-mip", type=float, default=0.5)
ap.add_argument("--window", type=int, default=10, help="points per arm, matching find_first_kink's k=0..9")
ap.add_argument("--min-live", type=int, default=3, help="minimum live points required in EACH arm")
a = ap.parse_args()

MIP = a.mip
LIVE = a.live_frac * MIP

rec = C.load_record()
keys = [k for k, r in rec.items() if C.judged(r)]
P, missing = C.load_payloads(a.prep, keys)
print("record %d judged items, payloads %d, missing %d" % (len(keys), len(P), len(missing)))
if missing:
    print("  MISSING:", missing[:10], "...")
keys = [k for k in keys if k in P]


def grp_of(k, pay):
    v = pay["verdict"]
    r = rec[k]
    st = C.is_stopper(r)
    s = int(v.get("is_stm") or 0)
    if st and not s:
        return "missed"
    if st and s:
        return "found"
    return "THRU_fp" if s else "THRU"


def has_asym_row(pay, entry_mip, far_mip, window, min_live):
    """True (+ the best row's asymmetry margin) if ANY row i has a 10-live-
    point window on each side with one side's mean >= entry_mip*MIP and the
    other <= far_mip*MIP, either direction."""
    rr, q, xyz = C.profile(pay)
    n = len(rr)
    if n < 2 * window + 1:
        return False, None
    live = q >= LIVE
    best = None
    for i in range(window, n - window):
        a_side = q[max(0, i - window):i][live[max(0, i - window):i]]
        b_side = q[i + 1:i + 1 + window][live[i + 1:i + 1 + window]]
        if len(a_side) < min_live or len(b_side) < min_live:
            continue
        ma, mb = a_side.mean() / MIP, b_side.mean() / MIP
        ok = (ma >= entry_mip and mb <= far_mip) or (mb >= entry_mip and ma <= far_mip)
        if ok:
            margin = max(ma, mb) - entry_mip
            if best is None or margin > best:
                best = margin
    return best is not None, best


grp = collections.defaultdict(list)
for k in keys:
    grp[grp_of(k, P[k])].append(k)

print("\npopulation: missed %d, found %d, THRU %d, THRU_fp %d" %
      (len(grp["missed"]), len(grp["found"]), len(grp["THRU"]), len(grp["THRU_fp"])))

print("\n=== operating point: entry >= %.1f MIP, far <= %.1f MIP, window %d, min_live %d ===" %
      (a.entry_mip, a.far_mip, a.window, a.min_live))
counts = {}
fires_by_class = {}
for g in ("missed", "found", "THRU", "THRU_fp"):
    n_fire = 0
    by_shape = collections.Counter()
    fired_keys = []
    for k in grp[g]:
        pay = P[k]
        ok, margin = has_asym_row(pay, a.entry_mip, a.far_mip, a.window, a.min_live)
        if ok:
            n_fire += 1
            sh = C.shape(pay)
            by_shape[sh.get("cls", "short")] += 1
            fired_keys.append(k)
    counts[g] = n_fire
    fires_by_class[g] = (by_shape, fired_keys)
    print("%-10s n=%-5d fires=%-4d (%s)" % (g, len(grp[g]), n_fire, dict(by_shape)))

print("\nmissed items with a candidate row (first 25, shape class in parens):")
by_shape, fired = fires_by_class["missed"]
for k in fired[:25]:
    print("  ", k, "(%s)" % C.shape(P[k]).get("cls", "short"))

print("\nTHRU/THRU_fp items with a candidate row -- the negative-control exposure "
      "(this coarse charge-only proxy is expected to over-fire vs the real "
      "geometry-gated code, same as T1a's own proxy did):")
for g in ("THRU", "THRU_fp"):
    _, fired = fires_by_class[g]
    print("  %s: %d of %d" % (g, len(fired), len(grp[g])), fired[:15])

print("\nNote: this probe answers population SIZE only (is the population worth")
print("building the knob for) -- it does not replicate find_first_kink's geometry")
print("gates or the downstream is_stm verdict test.  The real arm (d59v) decides")
print("the actual recovered count and false-positive rate.")
