# 58 — T1c: the STM stop split at a fit row

**Status (2026-09-09). Behavior change, confirmed and flipped ON for PDVD
production (`stop_split_max: 1, split_kink_min_deg: 15`, alongside T1a's
`stop_retreat_max: 2`, both in `pdvd/wct-pr-perevt.jsonnet`). PDHD stays OFF
for both — no PDHD STM/Michel hand-scan record exists to confirm it there.
Both byte-identical gates PASS (PDVD 579/579 vs `d57v`, PDHD 325/325 vs
`d53h`); the feature arm is scored against the frozen 569-item scan record,
not a new hand scan.**

Doc pdvd/57 §1 found, while sizing T1a, that 23 of the 51 missed
collapse-shaped stoppers have no chain vertex within 25 cm of the stop at
all -- the collapse sits *inside* the fit's last chain segment, so neither
T1a's graph-local retreat (which can only move the stop onto a vertex the
chain already has) nor a corrected T1b (`anchor_vertex` snaps to a vertex
within `stop_snap_tol_cm` = 2 cm) can reach them. Doc 56 §8 priced this as
T1c, "a fit-row split... a materially larger change... plan it as its own
session". **That pricing was wrong**: `CheckSTM_Michel` already calls
`PR::break_segment` (`CheckSTM_Michel.cxx:901`, inside `anchor_vertex`) to
split a fitted segment at the tagger's own entry/stop point, and
`break_segment` locates its cut by nearest **fit row**
(`PRSegmentFunctions.cxx:1119`) -- exactly the operation T1c needs. This
round is a third call to an existing, doctest-pinned primitive in a component
that already depends on it.

Provenance: toolkit `06872087` before this round's edit; wcp-porting-img
`b1d4dd03` (doc 57 + the T1a flip). Arms this round: `d53v`/`d53h` (existing,
120/61 events), `d57v` (existing, PDVD, T1a's own arm) vs `d58vleg`/`d58hleg`
(knob off, new binary) vs `d58v` (knob on, PDVD only, T1a's flip included).

---

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/toolkit
wcbuild && ./build/clus/wcdoctest-clus -tc="*stm_michel*"     # 29 cases, 8 new

cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
# the offline predictor, run BEFORE any C++ changed (section 1 below)
python3 pdvd/docs/nf_sp_img_clus/scripts/d58_split_probe.py

# the arms (PIN = a private snapshot of local/lib; feedback_shared_tree_binary_pin)
SURVEY='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0}'
FEAT='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0,stop_retreat_max:2}'
SPLIT='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0,stop_retreat_max:2,stop_split_max:1,split_kink_min_deg:15}'
ARM=d58vleg DET=pdvd SRC=d16vnu JOBS=8 PIN=<pin> PR_TLA="$FEAT"  pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
ARM=d58hleg DET=pdhd SRC=d16hnu JOBS=8 PIN=<pin> PR_TLA="$SURVEY" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
ARM=d58v    DET=pdvd SRC=d16vnu JOBS=8 PIN=<pin> PR_TLA="$SPLIT" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh

# byte-identical gates: d58vleg against d57v (SAME config, new binary -- NOT
# against d53v, which already differs from d57v by the retreat's 2 confirmed
# recoveries) and d58hleg against d53h (PDHD's own baseline, unchanged)
python3 pdvd/docs/nf_sp_img_clus/scripts/d51g_branch_census.py \
    --before 'pdvd/work/*_d57v'  --after 'pdvd/work/*_d58vleg' --before-arm d57v --after-arm d58vleg --pts --out /tmp/g1
python3 pdvd/docs/nf_sp_img_clus/scripts/d51g_branch_census.py \
    --before 'pdhd/work/*_d53h' --after 'pdhd/work/*_d58hleg' --before-arm d53h --after-arm d58hleg --pts --out /tmp/g2

# the feature arm, scored against the frozen scan record
cd pdhd/stm_michel_scan
./prep_stm_michel_scan.py --det pdvd --arm d58v --outdir $W/prep_d58v --sheetdir $W/sheet_d58v \
    --pin-tranche ../../pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
python3 census_score.py --prep $W/prep_d58v --arm d58v --json $W/d58v.json
```

Nothing under `work/`, `prep-pdvd/`, or `pdvd/docs/scan/` is written; the new
prep lives in scratch (`$HOME/tmp/d58/`).

---

## 1. The offline probe, run before any C++ changed

`pdvd/docs/nf_sp_img_clus/scripts/d58_split_probe.py` simulates the split on
the committed d53v payloads. Three things it found changed the design or the
task's own sizing before any code was written.

**Section 0 first: the reimplemented verdict was validated against the
production binary, not trusted on its own** — all 23 targets carry
`shape_flat`, so a Bragg-contrast-only proxy (the kind d57's probe used, where
the vertex constraint alone was the safety net) says nothing here; recovery
has to mean the *whole* shipped verdict clears, `kslike_compare` included.
Reimplementing `ks_mu`/`ks_flat` (`util/src/KSTest.cxx:216`, the normalized
running-cumsum max difference) and checking it against the persisted scalars
over all 549 judged items: max |diff| 1.1e-4, median 1.8e-6
(`feedback_reading_a_loop_is_a_hypothesis`).

**Doc 56's "23" is one number covering two different populations.** Split by
cause:

| population | n |
|---|---:|
| missed + collapse, no chain-vertex proxy within 25 cm, `n_chain_segs <= 1` — **structurally** unreachable by T1a (its loop needs `chain.size() > 1`) | **9** |
| same, `n_chain_segs >= 2` — excluded only by the offline vertex *proxy*; the T1c target | **14** |
| negative control: THRU + collapse, no chain-vertex proxy (`n_chain_segs<=1`: 20 of 58) | **58** |

**The fitted trajectory's own bend at the collapse onset replaces the vertex
constraint.** T1a's safety came entirely from "the chain must already have
this vertex" (doc 57: 24/51 vs 11/80 within 4 cm). A fit-row split discards
that constraint by definition, so something else has to keep it honest. The
bend of the fitted path (the owner's own kink discriminator,
`feedback_owner_kink_discriminator`, measured here at a fit row instead of a
segment pair) does:

| group (collapse-shaped, no chain-vertex proxy) | n | bend p25 | median | p75 | p90 | ≥ 20° |
|---|---:|---:|---:|---:|---:|---:|
| missed (the target) | 22* | 11.4 | **18.5** | 29.8 | 51.8 | 10 |
| THRU (negative control) | 54* | 3.5 | **6.3** | 10.5 | 17.2 | 1 |
| found | 2* | 40.1 | 58.8 | 77.4 | 88.5 | 2 |

\* one fewer than the population counts above in each row: `census_lib.shape()`
returns no `onset_rr` on those items (too few points in its own window), so
the bend cannot be measured there either — not a discrepancy, the same
"cannot judge" edge case propagating through both scripts.

**Operating-point grid**, recovery decided by the *full* verdict (contrast
**and** KS), `tail_med < 0.5 × plateau`, `peak_frac 1.4`, `peak_window 15 cm`,
`min_drop 3 cm` (T1a's shipped constants, reused — see §2):

| kink ≥ | targets firing | **recovered** | THRU firing | **new FP** |
|---|---:|---:|---:|---:|
| 0° | 7 | 3 | 11 | 0 |
| **15°** | 5 | **3** | 8 | **0** |
| 20° | 3 | 2 | 6 | 0 |
| 25° | 2 | 1 | 3 | 0 |

**Shipped: kink ≥ 15°, min_drop 3 cm — 3 of 23 recovered, 0 of 58 new false
positives.** Candidate row = the *largest* bend among rows that also pass the
collapse/Bragg-rise tests (an "anchor on the shape classifier's own collapse
onset" alternative recovers the same 3 but costs 2 new false positives at the
same threshold — tried and rejected for that reason). Doc 57's retreat
over-predicted its real-graph yield 3.5× (7 → 2); this probe is tighter (the
verdict is simulated exactly, not proxied), so 1–3 is the honest expectation
for the real arm, not a guarantee of 3.

---

## 2. The mechanism

Two new graph-free primitives beside `stm_michel_stop_retreat`
(`clus/src/StmMichelFunctions.cxx`):

`stm_michel_row_kink_deg(prof, i, window)` — the angle between the direction
arriving at profile row `i` (from `window` of arclength behind) and the
direction leaving it (`window` ahead); walks `prof.L` (monotonic by
construction) outward from `i` in both directions rather than searching `rr`,
since `rr` need not be monotonic in every profile this function might see.
Returns -1 (unmeasurable) when there is no room for a full `window` on either
side — the same "-1 = unmeasurable" convention `segment_pair_kink_deg` and
`stm_michel_classify_stop_arm`'s `kink_deg` already use.

`stm_michel_stop_split(prof, n_chain_segs, th)` — candidates are profile rows
with `seg_idx == n_chain_segs - 1` (**strictly inside the last chain
segment**: anywhere else a graph vertex already exists and belongs to
`stm_michel_stop_retreat`, never this function), `min_drop <= rr <=
max_drop_len`, and `stm_michel_row_kink_deg >= kink_min_deg`. Each surviving
candidate is then judged by the *same* collapsed-tail / Bragg-rise-to-retreat
tests the retreat applies — refactored this round into a shared file-local
`profile_plateau(prof, lo, hi, min_live)` so the two mechanisms cannot drift
on what "collapsed" and "a Bragg rise to retreat to" mean (verified
byte-identical: the retreat's own doctest cases are unchanged by the
refactor). Among rows passing every test, the **largest kink wins**.

`CheckSTM_Michel.cxx` calls it once, immediately after the retreat block and
only when the retreat did **not** already fire (`rec.n_retreat == 0` — the
retreat is the cheaper, safer mechanism, an existing vertex and no graph
mutation, and always wins when it applies), guarded by `stop_v`,
`!chain.empty()`, `chain.back()->fits().size() >= 4` (the same floor
`anchor_vertex` already applies to a segment it is willing to split),
`!(reject_bits & R_STOP_UNMATCHED)`, and `!bragg_confirmed(chain)` — the
existing lambda, unchanged, that protects the found stoppers. On acceptance,
`PR::break_segment` splits the chain's last segment at the chosen fit row
(mirroring `anchor_vertex:901-925` exactly — same argument list, same
`break_seg_orient` key, same `try/catch`), the new vertex is stamped
`VertexFlags::kProtectedBreak`, and the chain is rebuilt to the new vertex via
`stm_michel_shortest_chain` — the existing code immediately below (unchanged)
then refreshes `stop_pt`/`stop_vtx_id`/`stop_dis` and re-derives every
downstream stage at the new stop, exactly as it does after a retreat.

Seven knobs, all default OFF/legacy and **deliberately their own set, not
T1a's**: `stop_split_max` (int, **0**), `split_kink_min_deg` (15.0),
`split_min_drop_cm` (3.0), `split_collapse_frac` (0.5), `split_peak_frac`
(1.4), `split_peak_window_cm` (15.0), `split_dir_window_cm` (5.0). Coupling
T1c's operating point to `stop_retreat_max`'s three constants — which are
shipping to PDVD production this same round (§8) — would let a future
retune of either silently move the other. Three new persisted scalars,
`n_split`/`split_len`/`split_kink_deg`, appended next to `n_retreat`/
`retreat_len` — additive branches, never populated pre-doc-58.

**This is the first STM/Michel knob that mutates graph topology when ON.**
The OFF path is still the byte-identical guarantee, as always; the ON path
moves more than `T_stm_michel` (a new segment id, a new vertex id, the PF
tree, `T_rec_charge` groupings) — §6 reports a PF-tree census diff alongside
the verdict census, not just the verdict.

---

## 3. Tests

`clus/test/doctest_stm_michel.cxx` — 8 new cases: `stm_michel_row_kink_deg`
0° on a straight run (plus three "unmeasurable" edge cases: no room behind,
no room ahead, a window past both ends) and 90° at a hand-built right-angle
bend; `stm_michel_stop_split` fires on a collapsed tail behind a Bragg rise
*with* a kink; **does not fire on the identical shape with no kink** — the
discriminator doing its job, the test that matters most; `max_split = 0` is
off; a qualifying row *outside* the last chain segment is refused; a drop
shorter than `min_drop` is refused; and, given two genuine bends inside one
segment (45° then 90°), the function picks the **larger**, not the first
found. `clus/test/doctest_check_stm_michel_defaults.cxx` pins the 7 new
defaults.

`./build/clus/wcdoctest-clus -tc="*stm_michel*"`: 29/29 (8 new), 513/513
assertions. Full `clus` suite: **354/354** (was 346), 23346/23346 assertions,
1 skipped (pre-existing), 0 failed. Freshness proof: `local/lib/libWireCellClus.so`
(18:59:30) newer than every edited source file (last edit 18:58:54).

---

## 4. Byte-identical gates (knob off)

| gate | matched | shared branches | bit-identical | `is_stm` flips |
|---|---:|---:|---:|---:|
| `d58vleg` vs `d57v` (PDVD, same config, new binary) | 579 | 113 | **579 / 579** | 0 |
| `d58hleg` vs `d53h` (PDHD, unchanged config) | 325 | 111 | **325 / 325** | 0 |

`d58vleg` vs `d57v`: 3 new branches (`n_split`, `split_len`, `split_kink_deg`),
0 shared branches moved on any candidate, `T_stm_michel_pts` role histogram
identical before/after (`{1: 166094, 2: 2924, 3: 2453, 5: 315, 6: 3326}`),
point geometry identical on all 579. `d58hleg` vs `d53h`: 5 new branches
(`n_retreat`, `n_split`, `retreat_len`, `split_kink_deg`, `split_len` — PDHD
never got `d57h`, so both new-this-round *and* last-round's retreat branches
are new here), 0 shared branches moved, role histogram identical
(`{1: 97911, 2: 2447, 3: 1459, 5: 150, 6: 3695}`). One event, `039252_11`, has
0 `CheckSTM_Michel` candidates on every PDVD arm including `d53v`/`d57v` (doc
57) — its completion check never matches the "candidate(s)" regex; confirmed
pre-existing and symmetric, not a regression.

---

## 5. The feature arm: what `stop_split_max = 1` actually recovers

`d58v` runs `stop_retreat_max:2` (the confirmed T1a flip, §8) *and*
`stop_split_max:1, split_kink_min_deg:15`, so the comparison against `d57v`
(retreat only) isolates the split's own effect exactly as `d57v` vs `d53v`
isolated the retreat's.

|  | `is_stm` TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|
| `d57v` (retreat only, doc 57 baseline) | 146 | 9 | 123 | 271 | 0.942 | 0.543 |
| `d58v` (+ split) | **147** | 9 | **122** | 271 | 0.942 | 0.546 |

|  | `michel_found` TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|
| `d57v` | 115 | 41 | 37 | 356 | 0.737 | 0.757 |
| `d58v` | **117** | **44** | **35** | **353** | 0.727 | 0.770 |

**1 of 23 missed collapse-shaped stoppers recovered outright, 0 regressions,
0 new `is_stm` false positives** (the FP set is item-for-item identical
before/after: `039252_8/93, 039253_14/84, 039349_13/56, 039349_21/26,
039349_22/45, 039349_26/51, 039349_38/60, 039349_59/14, 039349_6/62`). The
offline probe (§1) predicted 3; the gap is the same pattern doc 57
established for the retreat (7 predicted → 2 actual) — the real chain graph
and the fitted trajectory's actual bend disagree with the offline
polyline-and-vertex-proxy stand-ins more often than they agree, and the
*item* that recovered (`039349_10/58`) is not even one the probe named (the
probe named `039252_9/101`, `039349_31/51`, `039349_82/60`; only
`039349_31/51` fired in the real arm at all, and it did not fully clear —
see below). This is not a failure of either script: `d58_split_probe.py`'s
job is the same one `d57_retreat_probe.py`'s was — establish that a
principled, bounded operating point exists *before* writing C++, not predict
the exact real-graph yield to the item.

Side effects: pin residual over the 36 scan pins **3.53 → 3.16 cm** (within
2 cm: 6 → 10); Michel attachment role 3 **185 → 186**, previously-swallowed
(role 1) **13 → 12** (one more segment freed); interior arms (no-role
same-cluster segments on stoppers) 659 → 661.

**Every item where `n_split` fired (10 of 569), named:**

| key | scan | pre-split `n_chain_segs` | drop (cm) | kink° | `is_stm` | `reject_names` after |
|---|---|---:|---:|---:|---:|---|
| `039349_10/58` | STM_MICHEL (attached) | 4 | 8.4 | 27.5 | **1** | *(none)* |
| `039349_31/51` | STM_MICHEL (both) | **1** | 5.4 | 40.1 | 0 | `shape_flat` only |
| `039253_17/77` | STM_MICHEL (attached) | 2 | 8.3 | 58.6 | 0 | `no_bragg, shape_flat` |
| `039349_48/54` | STM_MICHEL (attached) | 3 | 5.1 | 72.8 | 0 | `no_bragg, shape_flat` |
| `039349_5/54` | STM_MICHEL (both) | 5 | 5.3 | 40.3 | 0 | `no_bragg, shape_flat` |
| `039252_2/79` | THRU | **1** | 9.3 | 70.2 | 0 | `no_bragg, shape_flat` |
| `039252_4/55` | THRU | 6 | 5.1 | 15.4 | 0 | `no_bragg, shape_flat` |
| `039349_61/62` | THRU | 4 | 5.8 | 30.8 | 0 | `profile_sparse, shape_flat` |
| `039252_17/80` | THRU | 3 | 5.3 | 25.0 | 0 | `no_bragg, shape_flat` |
| `039349_74/28` | THRU | 6 | 5.5 | 17.1 | 0 | `no_bragg, shape_flat` |

**The structural claim, confirmed on the real graph, not just the offline
proxy**: `039252_2/79` and `039349_31/51` both had a pre-split
`n_chain_segs = 1` — chains `stm_michel_stop_retreat` could never touch at
all (its loop needs `n_chain_segs - n_drop > 0` with `n_drop >= 1`, and the
caller additionally guards `chain.size() > 1`), because a split works
*inside* a segment rather than *between* them. `n_chain_segs` is unchanged
pre- vs post-split for every one of the 10 (`break_segment` replaces the
last segment with its near-half; the far-half is dropped from the chain, not
added to it), which is the mechanical reason the count doesn't move.

**One near-miss**, the same shape doc 57's `039349_36/63` was:
`039349_31/51` — a genuine `n_chain_segs = 1` stopper, the split correctly
finds and drops the collapsed tail, the Bragg contrast now passes
(`no_bragg` cleared), but the KS shape test still reads `shape_flat` on the
shortened profile. Feeds T7 (doc 56 §8), same as the retreat's near-miss did.

**Two of the five genuine stoppers the split touched did not recover at all
on `is_stm`** (`039253_17/77`, `039349_5/54`) but *did* pick up a correct
`michel_found = 1` matching the scan's own `attached`/`both` Michel tag —
`is_stm` stays correctly 0 because `no_bragg`/`shape_flat` still hold on the
truncated muon profile itself, a separate question from whether the Michel
segment attached correctly. Partial credit, not a contradiction: the split
did what it was supposed to (drop the collapsed tail and find the Michel
past it) even where the overall stopper verdict still fails on unrelated
shape grounds.

**Five THRU items fired the split; all five stayed correctly `is_stm = 0`**
(the negative control held, including on the two `n_chain_segs = 1` THRU
items — the population the vertex constraint could never have protected).
**Three of those five acquired a spurious `michel_found = 1`**
(`039252_2/79`, `039252_4/55`, `039349_61/62`, all `conn_type 1, dis_cm
0.00`) — the same finding doc 57 made for the retreat (2 THRU items there),
now three for the split. `michel_found` is not gated on `is_stm` anywhere in
this codebase (a captured muon can show no Michel and, symmetrically, an
arm can be Michel-shaped without confirming the muon a stopper), so this is
expected to recur whenever a mechanism moves the stop; it is T2's input,
not a T1c defect.

---

## 6. Gates

| gate | result |
|---|---|
| `./build/clus/wcdoctest-clus -tc="*stm_michel*"` | 29/29 (8 new), 513/513 assertions |
| `./build/clus/wcdoctest-clus` (full `clus` suite) | **354/354** (was 346), 23346/23346 assertions, 1 skipped, 0 failed |
| freshness proof | `libWireCellClus.so` (18:59:30) newer than every edited source file (18:58:54) |
| `d58vleg` vs `d57v` | 579/579 bit-identical, 0 `is_stm` flips |
| `d58hleg` vs `d53h` | 325/325 bit-identical, 0 `is_stm` flips |
| flip-equivalence: `stm_michel_knobs` default bag + `-S stm_michel_extra={stop_retreat_max:2,stop_split_max:1}` vs the flipped base bag with no override | compiled JSON **identical** |
| OFF-path proof: `pdvd/wct-pr-perevt.jsonnet` compiled with both knobs forced to 0 via the SAME override on the pre-round file and this round's file | compiled JSON **identical** (no key set inert-but-present when off — `split_kink_min_deg` was tried as an explicit pin and dropped for exactly this reason, §8) |
| compiled-config proof | `stop_retreat_max = 2`, `stop_split_max = 1` present in the compiled JSON with no override |
| `d58v` census vs `d57v` census (same script, `census_score.py`) | +1 `is_stm` TP, 0 regressions, 0 new `is_stm` FP (identical FP set); +2 `michel_found` TP, +3 new `michel_found` FP (named §5) |
| `d58_split_probe.py` | rc 0, reproduces §1 including the section-0 KS/contrast validation |
| `census_score.py --check` on committed `prep-pdvd/` | still 0 of 14 differ (untouched) |
| `pdvd/docs/scan/*`, `work/*_d53*`, `smx1a`/`smx1` | untouched |

---

## 7. Found on the way, not fixed

1. **`census_lib.shape()`'s `onset_rr` is undefined on 1 of the 23 target
   items and 4 of the 58 THRU controls** (no window with ≥ 3 points inside
   `rr ∈ (1.2, 15)` after the live-point filter) — §1's bend table reports
   22/54, not 23/58, for that reason. Not a defect in this round's code; a
   pre-existing edge case in the shared shape classifier that both this
   probe and `d57_retreat_probe.py` inherit.
2. **T1b's own reasoning is affected by this round's population
   correction.** Doc 56's T1b row argued a corrected `find_first_kink` still
   "cannot reach 23 of the 51" because `anchor_vertex` snaps to a vertex
   within 2 cm; the corrected split (9 structural + 14 proxy-only) means T1b
   alone still cannot reach the 9 structural ones (no chain vertex to snap
   to at all, kink-corrected or not) but *might* reach some of the 14
   proxy-only ones if the tagger's own trajectory happens to already carry a
   vertex the offline proxy missed — an open question for whoever runs T1b,
   not resolved here.
3. **The KS-inclusive probe methodology (§1's step 0) is itself a reusable
   result**, not just a one-off validation: any future stop-shaping change to
   this component should reimplement and grade the *full* verdict offline
   before writing C++, exactly as this round and (retroactively) T1a's own
   post-hoc analysis did — a Bragg-contrast-only proxy is provably
   insufficient whenever the target population is `shape_flat`-held, which
   both T1a's 51-missed and T1c's 23-no-vertex populations are.
4. **A near-miss on this round's own procedure, caught and checked, not
   avoided outright.** The T1a production flip was edited into
   `pdvd/wct-pr-perevt.jsonnet` while `d58hleg` (PDHD's legacy/OFF arm) was
   still running; `run_pr_evt.sh` recompiles the jsonnet fresh per event, and
   `d58hleg`'s own override never sets `stop_retreat_max`, so any of its
   events compiled after that edit would have inherited `stop_retreat_max: 2`
   from the base bag instead of running with the retreat truly off. Checked
   directly (every `d58hleg` output file's persisted `n_retreat`): **zero**
   across all 61 events — the retreat mechanism never fired on this PDHD
   sample regardless of the knob's value, so the gate result stands, but the
   exposure was real. `d58v` and `d58vleg` were unaffected (both had already
   finished, or pass every relevant key explicitly in their own override).
   **Rule for next time: don't edit a config file arms-in-flight compile
   from until every arm reading it has finished**, even ones that appear to
   have already passed the point that matters.

---

## 8. Update to doc 56

Doc 56 §8's T1c row is updated with this round's outcome, the corrected
population split (9 structural + 14 proxy-only, not a single "23"), and the
note that `break_segment` already existed so the task was cheaper than
priced. Doc 57's status line notes `stop_retreat_max: 2` is now PDVD
production.
