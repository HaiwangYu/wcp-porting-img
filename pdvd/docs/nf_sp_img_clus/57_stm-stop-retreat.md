# 57 — T1a: the STM stop retreat

**Status (2026-09-09, updated same day). `stop_retreat_max: 2` is now PDVD
PRODUCTION in `pdvd/wct-pr-perevt.jsonnet` (confirmed on this round's own
census: 0 regressions, 0 new `is_stm` false positives). PDHD stays OFF: no
PDHD STM/Michel hand-scan record exists to confirm it there. Two
byte-identical gates PASS (PDVD 579/579, PDHD 325/325 shared branches); the
feature arm is scored against the frozen 569-item scan record, not a new
hand scan. See doc pdvd/58 for T1c, the companion mechanism this round's §1
sized (the stop split, for the 23 items the retreat cannot reach — now
9 structural + 14 proxy-only, corrected there).**

Doc pdvd/56 §8 named T1a first: on 51 of the 125 missed stoppers the STM stop
is, in practice, the far end of the tagger's trajectory fit, because
`find_first_kink`'s charge gate wants both arms of a kink ≥ 0.6 MIP and the
muon→Michel junction is asymmetric, so it returns the no-kink sentinel and
`CheckSTM_Michel.cxx:788` clamps the stop to the last fit row. `stop_extend_max`
can only walk the stop *outward*. This round adds the mirror — a graph-only
retreat — and reports what it actually recovers, on the real chain graph, not
the offline proxy that sized the design.

Provenance: toolkit `3e9c1097` before this round's edit; wcp-porting-img
`6feb53ef`. Arms this round: `d53v`/`d53h` (existing, 120/61 events) vs
`d57vleg`/`d57hleg` (knob off, new binary) vs `d57v` (knob on, PDVD only).

---

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/toolkit
wcbuild && ./build/clus/wcdoctest-clus -tc="stm_michel*"     # the 6 new cases

cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
# the offline predictor, run BEFORE any C++ changed (section 1 below)
python3 pdvd/docs/nf_sp_img_clus/scripts/d57_retreat_probe.py

# the arms (PIN = a private snapshot of local/lib; feedback_shared_tree_binary_pin)
SURVEY='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0}'
FEAT='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0,stop_retreat_max:2}'
ARM=d57vleg DET=pdvd SRC=d16vnu JOBS=8 PIN=<pin> PR_TLA="$SURVEY" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
ARM=d57hleg DET=pdhd SRC=d16hnu JOBS=8 PIN=<pin> PR_TLA="$SURVEY" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
ARM=d57v    DET=pdvd SRC=d16vnu JOBS=8 PIN=<pin> PR_TLA="$FEAT"  pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh

# byte-identical gate, both detectors
python3 pdvd/docs/nf_sp_img_clus/scripts/d51g_branch_census.py \
    --before 'pdvd/work/*_d53v' --after 'pdvd/work/*_d57vleg' --before-arm d53v --after-arm d57vleg --pts --out /tmp/g1
python3 pdvd/docs/nf_sp_img_clus/scripts/d51g_branch_census.py \
    --before 'pdhd/work/*_d53h' --after 'pdhd/work/*_d57hleg' --before-arm d53h --after-arm d57hleg --pts --out /tmp/g2

# the feature arm, scored against the frozen scan record
cd pdhd/stm_michel_scan
./prep_stm_michel_scan.py --det pdvd --arm d57v --outdir $W/prep_d57v --sheetdir $W/sheet_d57v \
    --pin-tranche ../../pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
python3 census_score.py --prep $W/prep_d57v --arm d57v --json $W/d57v.json
python3 census_score.py --prep prep-pdvd    --arm d53v --json $W/d53v.json   # same-script baseline, apples to apples
```

Nothing under `work/`, `prep-pdvd/`, or `pdvd/docs/scan/` is written; the new
prep lives in scratch (`$HOME/tmp/d57/`).

---

## 1. The offline probe, run before any C++ changed

`pdvd/docs/nf_sp_img_clus/scripts/d57_retreat_probe.py` simulates the retreat
on the committed d53v payloads, using a PR-vertex-proximity-to-the-muon-
polyline proxy for "the chain already has this vertex" (the real graph vertex
is not queryable offline). Two things it found **changed the design** before
any code was written:

**A retreat that fires on shape alone is dead on arrival.** All 51 missed
collapse-shaped stoppers are rejected by the shape bits *only*
(`no_bragg|shape_flat` 39, `shape_flat` 7, `profile_sparse` 5) — and so are
**63 of the 80** collapse-shaped THRU items. Nothing downstream protects the
look-alikes.

**The on-chain-vertex constraint is what keeps the retreat honest.** An
interior vertex sitting on the muon polyline within 4 cm of the collapse onset
exists on **24 of 51** missed-collapse items but only **11 of 80** THRU-collapse
(1 of 10 found-collapse). Requiring the retreat to land on a vertex the chain
already has — never a fit-row split — is the constraint that separates the two
populations.

Operating-point grid (script output, `tail_med < frac × {plateau, peak}`,
skip when already Bragg-confirmed, budget 4 candidate vertices):

| criterion | missed recovered | THRU new false positives |
|---|---:|---:|
| tail < 0.5 × plateau | **7** | **0** |
| tail < 0.6 × plateau | 8 | 1 |
| tail < 0.7 × plateau | 9 | 1 |
| tail < 0.5 × peak | 11 | 4 |
| tail < 0.6 × peak | 13 | 7 |
| tail < 0.7 × peak | 13 | 7 |

**Shipped: `tail_med < 0.5 × plateau`**, `peak_frac 1.4`, `peak_window 15 cm` —
the only point that costs no purity in the offline proxy. The peak-referenced
variant is exposed as a knob but is the owner's call (CLAUDE.md §5.1/§5.7), not
tuned here.

**23 of the 51** missed-collapse items have no candidate vertex within 25 cm at
all — the collapse is *inside* the fit's last chain segment, so no graph-local
walk reaches it. `anchor_vertex` also snaps the tagger's own stop to a vertex
within `stop_snap_tol_cm` (2 cm), so a kink-corrected `find_first_kink` (T1b)
cannot reach these either: it would land where no vertex exists and fall
through to the same sentinel path. **New task, T1c: split the fit at a chosen
row when the retreat's own criteria fire but no chain vertex is close enough.**
Folded into doc 56 §8 below.

---

## 2. The mechanism

`stm_michel_stop_retreat` (`clus/src/StmMichelFunctions.cxx`, declared in the
header beside `stm_michel_classify_stop_arm`) is graph-free: it reads a
`StmMichelProfile` and `n_chain_segs`, and answers "how many trailing chain
segments should be dropped". Per candidate `n_drop` (1, 2, … up to
`stop_retreat_max`):

1. the cumulative dropped length ≤ `michel_max_len_cm` (reused, not a new
   knob — the same ceiling an attached Michel arm already faces);
2. the live points of the segment(s) being dropped (≥ 2 of them) have
   median dQ/dx < `retreat_collapse_frac` (0.5) × the plateau — the SAME
   window (`bragg_plateau_lo/hi_cm`, with the short-track halving) that
   `stm_michel_bragg_contrast` uses, computed **once** from the un-shrunk
   chain so the reference does not chase the retreat;
3. the profile that *survives* the drop still peaks ≥ `retreat_peak_frac`
   (1.4) × plateau somewhere within `retreat_peak_window_cm` (15) of its new
   end — there must be a Bragg rise to retreat *to*.

`CheckSTM_Michel.cxx` calls it once, after the `stop_extend_max` loop
(extend-then-retreat: a wrong extension can still be undone) and before the
chain-vertex list is built, guarded by `stop_v` non-null, `chain.size() > 1`,
`!(reject_bits & R_STOP_UNMATCHED)` (that chain was never anchored to the
tagger's stop at all), and **skip when `bragg_confirmed(chain)` is already
true** — the existing lambda, unchanged, that is what protects the found
stoppers. On acceptance the chain is truncated, `stop_v` becomes the vertex at
the new end, and the existing code immediately below (unchanged) refreshes
`stop_pt`/`stop_vtx_id`/`stop_dis` and re-derives every downstream stage (Michel
search, interior arms, contrast/KS) at the new stop.

Four knobs, all default OFF/legacy: `stop_retreat_max` (int, **0**),
`retreat_collapse_frac` (0.5), `retreat_peak_frac` (1.4),
`retreat_peak_window_cm` (15.0). Two new persisted scalars, `n_retreat` /
`retreat_len`, appended unconditionally next to `n_ext`/`ext_len` (the same
pattern doc pdhd/03's `stop_extend_max` used) — additive branches on
`T_stm_michel`, never populated pre-doc-57.

---

## 3. Tests

`clus/test/doctest_stm_michel.cxx`: fires on a collapsed 0.15-MIP tail behind
a 3×-boosted Bragg rise (`n_drop == 1`); does not fire on a 1.0 MIP
continuation tail; does not fire when nothing peaks before the collapse (a
flat 1.0 MIP muon, no Bragg rise to retreat to); `max_drop = 0` is off; a
collapsed tail longer than `max_drop_len` is refused; and the same fire case
with the trailing segment's fits stored in reverse (the function reads
`seg_idx`, not storage order). `clus/test/doctest_check_stm_michel_defaults.cxx`
pins the four new keys.

```
./build/clus/wcdoctest-clus -tc="stm_michel*"
[doctest] test cases:  20 |  20 passed | 0 failed
./build/clus/wcdoctest-clus
[doctest] test cases: 346 | 346 passed | 0 failed | 1 skipped   (was 340 before this round)
```

Freshness proof: `local/lib/libWireCellClus.so` `18:07:xx`, after the last
source edit `18:06:xx`.

---

## 4. Byte-identical gates (knob off)

`d51g_branch_census.py`, same binary as the feature arm, `stop_retreat_max`
absent from the TLA:

| gate | matched | shared branches | bit-identical | `is_stm` flips |
|---|---:|---:|---:|---:|
| `d57vleg` vs `d53v` (PDVD) | 579 | 111 | **579 / 579** | 0 |
| `d57hleg` vs `d53h` (PDHD) | 325 | 111 | **325 / 325** | 0 |

Both comparisons show exactly two new-at-HEAD branches, `n_retreat` /
`retreat_len`, unfired (0) on every candidate — nothing else moved.
`T_stm_michel_pts` role histograms are identical on both detectors. This is
the load-bearing evidence for "this is a real knob, not an unconditional
change": the component is shared, so the PDHD gate matters as much as PDVD's.

---

## 5. The feature arm: what `stop_retreat_max = 2` actually recovers

Same `census_score.py`, run on the committed `prep-pdvd/` (baseline) and on a
fresh prep of `d57v` (scratch, `--pin-tranche`), 569/569 matched both times.

| | `is_stm` TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|
| `d53v` (baseline) | 144 | 9 | 125 | 271 | 0.941 | 0.535 |
| `d57v` (retreat on) | **146** | 9 | **123** | 271 | 0.942 | 0.543 |

| | `michel_found` TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|
| `d53v` | 111 | 39 | 41 | 358 | 0.740 | 0.730 |
| `d57v` | 115 | 41 | **37** | 356 | 0.737 | 0.757 |

Verified item-by-item, not just in aggregate: **exactly two 0→1 `is_stm`
flips** (`039252_2/39`, `039349_18/36`), **zero 1→0 regressions** — every
stopper `d53v` already found stays found. The offline proxy predicted 7
recoverable with 0 new false positives; the real chain graph delivers **2**
recovered with **0** new `is_stm` false positives — the negative control
(§1) held exactly as designed, but the real graph offers fewer usable retreat
vertices than the proxy's "any nearby PR vertex" over-counted. That gap is
itself the finding: **the proxy is an upper bound on what a graph-local
retreat can do, not an estimate of it.**

`n_retreat > 0` fired on **11 of 569** items:

| key | n_retreat | drop (cm) | scan | is_stm | reject bits after |
|---|---:|---:|---|---:|---|
| `039252_2/39` | 1 | 11.0 | STM_MICHEL | **1** | (none) |
| `039349_18/36` | 1 | 9.0 | STM_MICHEL | **1** | (none) |
| `039349_36/63` | 1 | 1.8 | STM_MICHEL | 0 | `shape_flat` only (contrast 1.63/1.91 now PASSES 0.6×; the KS test still fails it) |
| `039253_13/73` | 2 | 10.5 | STM_MICHEL | 0 | `shape_flat` |
| `039349_28/60` | 1 | 19.2 | STM_MICHEL | 0 | `no_bragg,shape_flat` |
| `039349_54/56` | 1 | 2.7 | STM_MICHEL | 0 | `shape_flat,profile_sparse` |
| `039349_7/4` | 1 | 2.7 | STM_MICHEL | 0 | `no_bragg,shape_flat` |
| `039349_20/41` | 1 | 4.3 | THRU | 0 | `no_bragg,shape_flat` |
| `039349_38/61` | 1 | 8.4 | THRU | 0 | `no_bragg,shape_flat` |
| `039349_48/21` | 2 | 12.0 | THRU | 0 | `no_bragg,shape_flat` |
| `039349_76/23` | 1 | 3.6 | THRU | 0 | `no_bragg,shape_flat,vertex_hadron` |

Two results worth separating out:

* **`039349_36/63` is a near miss, and it names T7's job precisely.** The
  retreat correctly identifies the collapse and the truncated contrast clears
  `bragg_contrast_min` (1.63 vs 0.6 × 1.91 expected) — but the KS shape test
  (`ks_mu + ks_margin ≥ ks_flat`) still rejects it. Doc 56 §4 already measured
  that the KS test kills 18 true stoppers whose contrast alone would pass; this
  is the same mechanism, now visible on an item the retreat *did* fix the stop
  for.
* **All four THRU items where the retreat fired stayed correctly rejected on
  `is_stm`** (three by `no_bragg|shape_flat`, one additionally by
  `vertex_hadron`) — the negative control held at the item level, not only in
  the aggregate count. But **two of them (`039349_20/41`, `039349_48/21`)
  picked up a spurious `michel_found = 1`** (both `conn_type 1`, attached at
  distance 0, 5.7 / 8.7 MeV) — `michel_found` is deliberately not gated on
  `is_stm` (a mu⁻ can be captured with no Michel), so retreating the stop on a
  through-going track can hang a Michel-shaped arm off the new vertex even
  though the overall verdict stays correctly THRU. This is the source of the
  `michel_found` purity dropping 0.740 → 0.737 even as its efficiency and F1
  both improve (0.730 → 0.757, 0.735 → 0.747). **Not a regression the knob-off
  gate would have caught** (it only exists when the knob fires) and **not a
  blocker for T1a** (the knob stays out of production), but T2 (Michel
  admission) needs to know a retreated stop is not automatically an `is_stm`-
  confirmed one.

**Side effects, in the direction the design intended:**

* Michel attachment (doc 56 §7's C2 metric) improves beyond the two flips:
  role 3 (proper Michel) 180 → **185**, role 1 (swallowed into the muon chain)
  19 → **13** — six previously-swallowed Michel segments are freed by the
  retreat, five of them landing correctly as role 3.
* The pin residual over the 36 scan pins improves: median 4.60 → **3.53 cm**,
  within 2 cm 3 → **6**.
* Failure class G (coiled fit end) 18 → 16; class D (missed Michel) 41 → 37.
  Every other class within ±2 of baseline (shape reclassification on
  retreat-touched items that did not flip `is_stm`, expected since `shape()`
  reads whatever profile the arm currently persists).

---

## 6. Gates

| gate | result |
|---|---|
| `./build/clus/wcdoctest-clus -tc="stm_michel*"` | 20/20, 331 assertions |
| `./build/clus/wcdoctest-clus` (full clus suite) | 346/346 (was 340), 1 skipped, 0 failed |
| freshness proof | `libWireCellClus.so` newer than every edited source file |
| `d57vleg` vs `d53v` | 579/579 bit-identical, 0 `is_stm` flips |
| `d57hleg` vs `d53h` | 325/325 bit-identical, 0 `is_stm` flips |
| `d57v` census vs `d53v` census (same script) | +2 `is_stm` TP, 0 regressions, 0 new `is_stm` FP; +4 fewer `michel_found` FN, +2 new `michel_found` FP (named above) |
| `d57_retreat_probe.py` | rc 0, reproduces the operating-point table above |
| `census_score.py --check` on committed `prep-pdvd/` | still 0 of 14 differ (untouched) |
| `pdvd/docs/scan/*`, `work/`, `smx1a`/`smx1` | untouched |

---

## 7. Found on the way, not fixed

1. **T1c (new task).** 23 of the 51 missed-collapse items have no chain vertex
   within 25 cm of the stop; the collapse sits inside the last fit segment.
   Neither this retreat nor T1b's `find_first_kink` fix (which is also
   `anchor_vertex`-snapped to an existing vertex) can reach them. Needs a fit-
   row split, which is a different, larger change (a new Steiner/fit boundary,
   not a graph walk) — sized here, not attempted.
2. **T1a does not make a retreated stop `is_stm`-safe for the Michel stage.**
   `039349_20/41` and `039349_48/21` show a retreat can manufacture a
   Michel-shaped arm on a through-going track even while `is_stm` stays
   correctly 0. T2 should treat "did the retreat fire" as part of the
   admission context, not assume a retreated stop carries the same confidence
   as an un-retreated one.
3. `039349_36/63` is a clean demonstration that the contrast and KS tests
   disagree even after the stop is right — T7's job, not this one's.
4. The four PDHD/SBND-shared pieces this round did **not** touch:
   `find_first_kink`'s asymmetric-kink clause and `vertex_kink_reject`'s `n−1`
   fallback (T1b, its own SBND gate), the `TrackFitting.cxx:9702` literal (T7),
   and no per-plane dead flag is persisted (T4).

---

## 8. Update to doc 56

Doc pdvd/56 §8's T1a row is marked done, with a link here; a new row **T1c**
is added for the no-reachable-vertex population sized in §1/§7 above; and the
§1 owner-point-2 table gains one line noting the KS/contrast disagreement is
now demonstrated on a retreat-fixed item, strengthening T7's case (see doc 56
directly for the updated task table).
