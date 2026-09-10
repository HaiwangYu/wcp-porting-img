# 56 — From the 569-item hand scan to a task set for the STM + Michel pattern recognition

**Status (2026-09-09, updated same day after T1a and T1c). Analysis and plan;
§8's T1a and T1c rows are now executed — see doc pdvd/57 (T1a: the stop
retreat) and doc pdvd/58 (T1c: the stop split) for their code, gates and
results. Both byte-identical gates PASS for both rounds. Both knobs
(`stop_retreat_max: 2`, `stop_split_max: 1`) are now PDVD PRODUCTION in
`pdvd/wct-pr-perevt.jsonnet` — confirmed on the 569-item scan record, 0
regressions, 0 new `is_stm` false positives. PDHD stays OFF for both: no
PDHD STM/Michel hand-scan record exists to confirm either knob there.
Everything else below is still analysis: no other C++ changed, no other
knob moved.** It answers the owner's request after doc pdvd/55 closed the
hand scan: read the scan against the reconstruction code, find the mechanism
behind each failure class, pick the candidates to dive into first, and write
down the tasks — one per session — with the intermediate metric each one is
graded on, because the final `is_stm` / `michel_found` flag is the wrong
yardstick for most of them.

Provenance: toolkit `3e9c1097`, wcp-porting-img `cbe3e597`, arm `d53v` (120
events, 569 `CheckSTM_Michel` candidates, every one hand-scanned in tag
`smx1a`). Companion docs: pdvd/55 (the scan), pdvd/54 (two mechanisms, from the
owner's own scan), pdvd/52 (how `CheckSTM_Michel` works), pdhd/03 (the knob bag
both ProtoDUNEs run), pdhd/11 (the STM fit walks a Dijkstra stub), pdhd/13 (a
detached Michel lost to a length cut), pdvd/57 (T1a executed: the stop
retreat, its gates and its results), pdvd/58 (T1c executed: the stop split at
a fit row, its gates and its results, and the corrected 9+14 population
count for the items T1a's retreat cannot reach).

---

## 0. Repro

Everything below is arithmetic over two committed inputs — the scan record
`pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json` and the d53v payloads in
`pdhd/stm_michel_scan/prep-pdvd/` — plus `T_stm_pass` read out of each event's
`pdvd/work/<evt>_d53v/tracking-stm.root`. Nothing is written under `work/` or
`pdvd/docs/scan/`.

```bash
cd /home/xqian/toolkit-dev/wcp-porting-img

# every table in sections 2-6, in doc order
python3 pdvd/docs/nf_sp_img_clus/scripts/d56_failure_mechanisms.py

# the regression metric (section 7): the d53v baseline, diffed against doc 55's literals
python3 pdhd/stm_michel_scan/census_score.py --check          # "0 of 14 differ"

# the same metric on a NEW arm <tag> (prep into scratch; the committed sheet/key are not touched)
W=$HOME/tmp/d56
cd pdhd/stm_michel_scan
./prep_stm_michel_scan.py --det pdvd --arm <tag> --outdir $W/prep_<tag> --sheetdir $W/sheet_<tag> \
    --pin-tranche ../../pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
python3 census_score.py --prep $W/prep_<tag> --arm <tag> --json $W/<tag>.json
```

Producing a new arm is the doc-53 recipe, with the binary pinned
(`feedback_shared_tree_binary_pin`) — the PR tail costs ~22 s/event, so the
120-event arm is about five minutes at eight jobs:

```bash
ARM=<tag> DET=pdvd SRC=d16vnu JOBS=8 PR_TLA='-S stm_michel_extra={...}' \
    pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
```

Shared primitives (the shape classifier, the sentinel reader, the offline arm
gate test) live in `pdhd/stm_michel_scan/census_lib.py`, so the analysis script
and the scorer cannot drift apart on a definition.

---

## 1. The owner's five points, and where each one lands in the code

| # | the owner's impression | what the census says | code path | task |
|---|---|---|---|---|
| 1 | some fits never show the Bragg peak; is 0.6 cm the right step for PDVD's pitch; Steiner terminals; dead channels | the peak is usually *there* — the profile is read at the wrong place (the stop overshoots, §2) or judged by a test it fails while rising (§4); dead channels do **not** separate missed from found stoppers (§5); the step is pitch-blind on every detector and one config key reaches only half the fitters (§6) | `TrackFitting.cxx` passes 2-3 (`:9524`, `:9702`, `:10076`), the dead-plane smoother (`:9058-9105`), `examine_end_ps_vec` (`:2562`) | T4, T5, T7, T8 |
| 2 | the STM end point is wrong — `break_segments` or the Bragg search | the stop is, in practice, **the far end of the tagger's trajectory fit**: `find_first_kink` returns its no-kink sentinel on 74 of 131 accepted stoppers and on 29 of the 51 overshoots, and `CheckSTM_Michel` clamps the stop to the last fit row. `break_segments` never reaches the STM verdict (it runs in `CheckSTM_Michel`, downstream); the fit's path end is chosen by geometry, not charge. **T1a executed (doc 57): a graph-local retreat recovers 2 of the 51 outright with 0 regressions. T1c executed (doc 58): of the 23 with no chain vertex to retreat onto (corrected: 9 structurally unreachable by any graph walk + 14 excluded only by an offline proxy), a fit-row split gated on the fitted trajectory's own bend recovers 1 more, 0 regressions. Both knobs are PDVD production** | `TaggerCheckSTM.cxx:1570` (`find_first_kink`), `:3557-3666` (path ends), `CheckSTM_Michel.cxx:788`, `:1226`, `:1298`; `StmMichelFunctions.cxx:stm_michel_stop_retreat`/`stm_michel_stop_split` (doc 57/58) | **T1a ✅, T1c ✅, T1b** |
| 3 | the Michel is not identified when it is nearly isotropic / has no trajectory | 38 of the 41 missed Michels sit on items whose stop was already wrong; of the arms that touch the fit end, 8 fail `michel_mip_lo` and 7 pass every threshold yet are not admitted; 29 scan-michel segments are detached; doc 54 §2's `pr54` residual drop discards every residual in the Michel-size band | `StmMichelFunctions.cxx:279-315`, `CheckSTM_Michel.cxx:1498-1608`, `:1692-1719`, `NeutrinoOtherSegments.cxx:36` | T2, T3 |
| 4 | unassociated segments — delta rays, or over-clustering | 172 same-cluster fitted segments with no role on 51 stoppers; 152 are attached to the chain interior and 46 of those are > 8 cm at median 0.30 MIP, so `stm_michel_classify_chain_arm` returns `kOther` and they vanish from every product | `StmMichelFunctions.cxx:317-332`, `CheckSTM_Michel.cxx:1476-1495` | T6 |
| 5 | the scan doc already holds the key information | yes — and the piece it could not hold is *how the numbers move when code changes*; §7 turns the record into that instrument | `census_score.py` | **T0** |

One framing fact first. All 569 items are candidates because `TaggerCheckSTM`
tagged them `Flags::STM`; the scan calls 269 of the 549 judged items stoppers.
**The tagger's own purity on this sample is 0.49; `CheckSTM_Michel`'s gates
raise it to 0.94 at the price of efficiency 0.535.** The tagger is the purity
problem; the Michel stage's gates are the efficiency problem — and, as §2 shows,
the two share one root.

---

## 2. Where the stop comes from — and why 51 of the 125 missed stoppers are one mechanism

### 2.1 The 125 missed stoppers by the shape of their last 15 cm

`census_lib.shape()`: running median over 3 live points; plateau = median over
rr 20–60 cm; **collapse** = a peak ≥ 1.4× plateau at rr 1.2–15 cm whose last
three points fall below peak/1.8; **rise-to-end** = the peak without the fall;
**flat** = neither.

| shape | missed stoppers (125) | found stoppers (144) | THRU (280) |
|---|---:|---:|---:|
| collapse | **51** | 10 | 81 |
| rise-to-end | **57** | 131 | 66 |
| flat | 17 | 3 | 131 |

The 51 collapse items are doc 54 §1's overshoot, sized on the census: the
profile peaks a median 7.1 cm (p90 11.7) before the fit's last point and then
falls to a fraction of MIP. The scan pinned 29 of them; the other 22 carry the
same arithmetic signature without a pin. **The 81 THRU items with the same
signature are the negative control** for any stop-retreat: a fit that ends flat
after a delta ray looks the same to this arithmetic, and the scan called those
through-going.

### 2.2 The stop is the far end of the fit

`CheckSTM_Michel` takes its stop from the tagger's accepted pass: the
`kink_num`-th row of `stm_fit`, clamped to the **last row** when `kink_num` is
out of range (`CheckSTM_Michel.cxx:788`). `find_first_kink` returns
`fits().size()` — out of range by construction — whenever it finds no kink
(`TaggerCheckSTM.cxx:1579`, `:1604`, `:1930`). Reading `T_stm_pass` for the
accepted pass of every item:

| scan class | n | sentinel (stop = last fit row) | real kink |
|---|---:|---:|---:|
| accepted stoppers, rise-to-end | 131 | **74** | 57 |
| missed stoppers, collapse | 51 | **29** | 22 |
| missed stoppers, rise-to-end | 57 | 28 | 29 |
| THRU, collapse | 80 | 75 | 5 |
| THRU, flat | 131 | 123 | 8 |

The fall-through is the normal path, not the exception. On the 22 overshoots
with a real kink, the kink sits 1–7 rows (0.6–4 cm) from the last row on 16 of
them — still past the collapse. And the fit's far end is not chosen by charge at
all: `TaggerCheckSTM` seeds the fit with a Dijkstra path on the Steiner graph
between the cluster's two boundary/extreme points (`TaggerCheckSTM.cxx:3557-3666`,
`do_rough_path` `:1115`), so when the Michel is in the same cluster and reaches
further than the muon, **the path's far end is the Michel's tip**.
`find_first_kink` was the mechanism meant to pull it back, and its charge gate
(`:1794-1797`, ported verbatim from `ToyFiducial.cxx:1146-1164`) requires
**both** arms ≥ 0.6 MIP — the two-track kink. The muon→Michel junction is the
asymmetric one: Bragg on one side, 0.1–0.4 MIP on the other. Doc 54 §1.2
measured it on `039349_18/36`: `sum_fQ` 1.77, `sum_bQ` 0.09, sentinel.

### 2.3 The graph already has the vertex

On the 51 collapse items, the nearest PR-graph vertex to the collapse onset sits
a median **1.7 cm** away: **29 within 2 cm, 40 within 4 cm**, 4 beyond 6 cm.
`stop_extend_max` (`CheckSTM_Michel.cxx:1298`, PDVD runs 3) can only walk the
stop *outward*; nothing walks it back. So on four in five overshoots the fix is a
graph-local walk with no new fit: the Michel arms are already hanging off that
interior vertex, where `stm_michel_classify_chain_arm` files them under
`n_body_other` with no role (`:1492`).

| item | peak at rr | onset rr | nearest vertex | scan pin |
|---|---:|---:|---:|---:|
| `039252_2/39` | 14.6 | 11.0 | 0.0 | 11.1 |
| `039349_18/36` | 10.8 | 9.6 | 0.6 | 9.5 |
| `039253_7/80` | 10.5 | 6.6 | 0.9 | 9.2 |
| `039349_81/44` | 10.0 | 9.4 | 0.6 | 7.5 |
| `039349_60/40` | 7.4 | 6.2 | 0.6 | 6.1 |
| `039349_19/52` | 13.8 | 12.6 | 8.8 | 7.0 |
| `039349_34/48` | 11.8 | 10.0 | 9.2 | 5.5 |

(The full 51-row table is printed by the script, §3 of its output.)

### 2.4 The Michel defect is the stop defect

Of the 41 missed Michels, **38 are on items the chain rejected as non-STM**.
Matching every scan-tagged `michel` segment into the arm by geometry: 180 carry
role 3 already, **85 carry no role**, **19 are role 1 — typed as the muon's own
last segment** (the `039349_18/36` failure, twice in tranche 1 and now sized),
8 are survey-only. By attachment: 38 segments touch the fit end, 16 hang off an
interior vertex, 29 are detached > 3 cm. Fixing the stop re-roots the Michel
search at the right vertex; that is why T1 comes before T2 and T3.

---

## 3. The Michel admission gate, on the arms that do reach the stop

`stm_michel_classify_stop_arm` (`StmMichelFunctions.cxx:279-315`) admits an arm
as a Michel when `len + far_len ≤ michel_max_len_cm` (25), `michel_mip_lo` (0.3)
< mip < `michel_mip_hi` (2.0), and either a shower flag or a kink ≥
`michel_min_kink_deg` (30). Testing the same thresholds offline on the 20
non-muon-typed arms that touch the fit end on missed-Michel items
(`mip_dqdx_median` 47000 as the PDVD driver sets it):

| why not admitted | arms | examples |
|---|---:|---|
| `mip ≤ 0.3` | **8** | `039253_17/77` 77007 (8.8 cm, **0.10** MIP, 73°), `039349_22/63` 63005 (0.15), `039252_0/75` 75022 (0.18), `039349_11/19` 19004 (0.21) |
| `kink < 30°` | 5 | `039349_52/36` 36013 (4°), `039349_64/65` 65003 (5°), `039349_5/65` 65019 (20°) |
| passes every threshold | **7** | `039349_32/63` 63006 (8.6 cm, 0.78 MIP, 89°), `039349_7/4` 4010 (168°), `039349_82/54` 54003, `039253_3/61` 61007, `039252_16/98` 98007 |

Two things to take from it. The eight `mip_lo` failures are Michel charge the
fit barely reads — 0.10–0.30 MIP over 5–9 cm — which the scan nevertheless
attributed on the 3-D picture and the object table; whether the gate should read
the arm's *total* charge (its KE) rather than its median dQ/dx is T2's question.
The seven that pass every threshold and are still not admitted must be hanging
off a vertex that is not `stop_v` (the stop snaps within 2 cm,
`stop_snap_tol_cm`; a Michel attached one vertex earlier is an interior arm) —
each needs its own trace, which is exactly the dive T2 is for.

---

## 4. The two shape tests, scored one at a time

`no_bragg` is `contrast < bragg_contrast_min × expected` with `contrast =
tail_med(0.5–3 cm) / plateau_med(20–40 cm)` (`StmMichelFunctions.cxx:215-245`,
`CheckSTM_Michel.cxx:1405`); `shape_flat` is `ks_mu + ks_margin ≥ ks_flat` over
the last 35 cm (`:1443`). On the 524 judged items with a valid profile (260 scan
stoppers):

| test alone | TP | FP | FN | purity | efficiency |
|---|---:|---:|---:|---:|---:|
| contrast ≥ 0.60 × expected (shipped) | 199 | 34 | 61 | 0.854 | 0.765 |
| contrast ≥ 0.70 × expected | 176 | 14 | 84 | 0.926 | 0.677 |
| contrast ≥ 0.75 × expected | 170 | 9 | 90 | 0.950 | 0.654 |
| KS `ks_flat − ks_mu > 0` (shipped) | 158 | 23 | 102 | 0.873 | 0.608 |
| both, as shipped | 155 | 16 | 105 | 0.906 | 0.596 |

The 57 missed stoppers whose profile rises to the end are killed by `shape_flat`
alone on 31, `no_bragg|shape_flat` on 10, `plateau_off_mip` on 6,
`stop_near_boundary` on 4. The 9 `is_stm` false positives all have contrast
0.60–0.93 × expected and pass the 0.6 bar; the KS test kills 18 true stoppers
whose contrast is ≥ 0.8 × expected. **A threshold-only retune tops out around
0.65–0.77 efficiency; the rest is the stop.** Per CLAUDE.md §5.7 no operating
point is moved here; the table is the input to T7, where the owner decides.

The prototype's `eval_stm` does one thing the Michel stage does not: it locates
the Bragg peak first and measures residual range **from the peak bin**
(`ToyFiducial.cxx:1551`, `end_L = L[max_bin] + 0.2 cm`), whereas
`stm_michel_bragg_contrast` measures from the chain end. On an overshoot the
tagger's recipe survives and the Michel stage's does not — which is consistent
with the tagger having accepted all 569 while the Michel stage rejects 125 scan
stoppers. Testing the peak-anchored origin is part of T7.

---

## 5. Dead channels are not the mechanism

Testing each item's last 15 cm of chain points against the payload's dead-band
lists, plane by plane:

| | n | ≥ 20 % of points on a dead band in ≥ 1 plane | in ≥ 2 planes |
|---|---:|---:|---:|
| missed stoppers | 125 | 14 (11 %) | 0 |
| found stoppers | 144 | 14 (10 %) | 0 |
| THRU | 280 | 38 (14 %) | 1 |

No stopper has a `q ≤ 0` point in its last 10 cm. So dead channels near the
stop do not separate missed from found, and are not where the 125 come from.
What the code does with a dead plane is still worth knowing: `dQ_dx_fit` does
not drop the point, it adds `dead_col_weight` 0.9 (W) / `dead_ind_weight` 0.3
(U, V) to a second-difference **smoother** (`TrackFitting.cxx:9058-9105`) — the
one mechanism that would flatten a Bragg peak inside a dead band — and the
per-plane flags `reg_flag_u/v/w` are function-locals that **no product
persists**; `T_proj_data` drops `FittedCharge2D::flag` too. The 14 missed
stoppers with one dead plane at the end are the candidates for T4, which adds
the flags to the `stm_fit` PC before anyone tunes anything.

---

## 6. The 0.6 cm step, the Steiner terminals and the fit end

* The sampling step is 0.600 cm on every item, PDVD and PDHD alike: pass 1 of
  the fit uses `low_dis_limit` 1.2 cm, passes 2 and 3 halve it. Pass 3 of
  `do_multi_tracking` is a **hard literal `0.6*units::cm`** at
  `TrackFitting.cxx:9702`, while `do_single_tracking` derives it from the knob
  (`:10076`); the three detectors ship byte-identical geometric fit keys
  (`low_dis_limit 12`, `end_point_limit 6`, `dx_norm_length 6`, `div_sigma 6`
  mm) across pitches 0.300 / 0.479 / 0.765 cm. So the step is 2× the SBND pitch
  and 0.78× PDVD's U/V pitch — an inversion, not a scaling — and today one
  config key reaches only half the fitters. The only pitch-aware mechanism live
  in the chain, `ctpc_aniso_metric`, sits in the good-point test, not in
  sampling.
* Plateau point-to-point |Δlog q| is 0.114 on PDVD against 0.089 on PDHD, and
  rebinning to 1.2 cm *raises* it to 0.150 / 0.159: adjacent 0.6 cm points are
  positively correlated, i.e. the fit's dQ/dx is smoother than its sampling and
  the tail median over 0.5–3 cm averages ~4 correlated points. The right first
  measurement is the profile's autocorrelation length per detector, not a step
  change. `dx_norm_length` (the smoother's length scale) is the most direct
  Bragg-relevant knob.
* The **undershoot** is real and small: 5 items carry a > 1.67 MIP forward stub
  past the fit end (class F, doc 55 §15.3), all rejected. `examine_end_ps_vec`'s
  tip trim (`TrackFitting.cxx:2609`) and the Steiner terminal set are the two
  owners; `absorb_bragg_stub` was the last attempt and regressed on PDHD (doc
  pdhd/03 §6.8).
* The **coiled** (class G, 18) and **unsupported** (class H, 20 items) fits are
  the cases where the *path* is wrong and the profile is not a measurement; they
  are the tail of the list on purpose.

---

## 7. The instrument: `census_score.py`

The final flag cannot grade most of these tasks: the Michel degrades the very
quantity the flag tests (doc 55 §15.2), and the stop defect feeds the Michel
defect. So each task carries its own number, and `census_score.py` prints them
for any arm against the frozen record:

| metric | what it reads | d53v today |
|---|---|---|
| doc 55 §14.1 / §14.2 | `is_stm`, `michel_found` vs scan | 0.941 / 0.535, 0.740 / 0.730 |
| failure classes A–L | doc 55 §17 queries, recomputed | A 9, B 125, C 39, D 41, E 32, F 5, G 18, H 20, K 36 |
| **stop residual** | \|arm stop − scan pin\| over the 36 pins; shape census; sentinel rate per class | median 4.60 cm, within 2 cm **3 of 36**; collapse 51 / 10 / 81; sentinel 29 of 51 |
| **Michel attachment** | every scan-`michel` segment matched by geometry, its role in the arm | role 3 **180**, no role 85, role 1 (swallowed) 19, survey 8 |
| **interior arms** | same-cluster no-role segments on scan stoppers | 174 stoppers, 664 segments, 518 > 5 cm |

`--check` diffs the baseline against doc 55's published literals: **0 of 14
differ**. The join is by `(event, cluster_id)`, stable for any change downstream
of clustering — every task here — and the unmatched count is printed, never
swallowed. Segment ids are *not* stable across arms (`cluster_id*1000 +
graph_index`), which is why the Michel-attachment metric matches by geometry.

---

## 8. The task set

Ordered by evidence × cost; one per session; every code task behind a
default-OFF knob, byte-identical off (CLAUDE.md §1/§4), graded with
`census_score.py` on a fresh arm tag (never over d53v — M13). Anything in
`TaggerCheckSTM` or `TrackFitting` is also gated on SBND, which binds the same
components (`feedback_shared_component_merge_gating`).

| # | task | point | dive into first | metric | gate |
|---|---|---|---|---|---|
| **T0** | the census scorer — done in this round (§7) | 5 | — | reproduces doc 55 | `--check` 0 of 14 |
| **T1a** | ✅ **DONE, doc pdvd/57. Knob `stop_retreat_max: 2` is PDVD PRODUCTION.** stop retreat, graph level: in `CheckSTM_Michel`, after the chain is built, walk *back* from `stop_v` while the trailing chain segment(s) are collapsed (median < 0.5 × plateau) and the profile before them still peaks ≥ 1.4×; mirror of `stop_extend_max` (`:1298`); graph-only in `StmMichelFunctions`, 6 doctests. Result on the real chain graph (not the offline proxy that sized it): **2 of 51** missed collapse-shaped stoppers recovered (`039252_2/39`, `039349_18/36`), **0** regressions, **0** new `is_stm` false positives on the 80-item negative control (both byte-identical gates PASS, PDVD 579/579 + PDHD 325/325). Michel attachment improves as a side effect (role 3 180→185, swallowed 19→13); pin residual median 4.60→3.53 cm. Two THRU items where the retreat fired stayed correctly non-`is_stm` but picked up a spurious `michel_found=1` — feeds T2. PDHD stays OFF: no PDHD hand-scan record exists to confirm it there | 2 | (scored, see doc 57 §5) | stop residual 36 pins 4.60→**3.53 cm**, within 2 cm 3→**6**; collapse 51→**48** missed; `is_stm` census (549,144,9,125,271,.941,.535)→(549,146,9,123,271,.942,.543) | knob `stop_retreat_max`; off = byte-identical (both detectors, verified); scorer on/off; zero unconditional SBND exposure (component shared, not yet gated there since T1b is what touches `TaggerCheckSTM`) |
| **T1c** | ✅ **DONE, doc pdvd/58. Knob `stop_split_max: 1` is PDVD PRODUCTION.** Fit-row split: `PR::break_segment` (already used by `anchor_vertex` to split at the tagger's own entry/stop) splits the chain's last segment at a fit row instead of an existing vertex, gated on the fitted trajectory's own bend at that row (`stm_michel_row_kink_deg >= 15°`) rather than a vertex — losing the vertex constraint is what T1a's safety depended on, so the kink is what replaces it (median bend 18.5° on the target population vs 6.3° on the through-going negative control). **Correction to the population this task targets**: the "23" doc 57 named is 9 items structurally unreachable by any graph walk (`n_chain_segs <= 1`, T1a's loop cannot even start) + 14 excluded only by the offline vertex proxy. Result: **1 of 23 recovered**, 0 regressions, 0 new `is_stm` false positives (identical FP set before/after); pin residual 3.53→3.16 cm; role 3 185→186. Confirms the structural claim directly: 2 of the 10 items the split fired on had a pre-split `n_chain_segs = 1`, unreachable by T1a by construction. Three THRU items (of five that fired) picked up a spurious `michel_found=1`, on top of T1a's own two — feeds T2. **Correction to doc 56's original pricing**: this was NOT "a materially larger change... plan it as its own session" — `break_segment` already existed in this exact component, so T1c was a third call to a doctest-pinned primitive, not new graph machinery | 2 | (scored, see doc 58 §5) | stop residual 36 pins 3.53→**3.16 cm**, within 2 cm 6→**10**; `is_stm` census (549,146,9,123,271,.942,.543)→(549,147,9,122,271,.942,.546) | knob `stop_split_max`; off = byte-identical vs `d57v` (same config, new binary — not vs `d53v`, which already differs by T1a's own recoveries) and vs `d53h`; first STM/Michel knob that mutates PR graph topology when on (new vertex, new segment), reported via the `T_stm_michel_pts` role/geometry census |
| **T1b** | **the asymmetric kink in `find_first_kink`.** A third clause accepting a kink where the entry-side 10-point density is ≥ 1.2 MIP and the far side ≤ 0.5 MIP (Bragg into Michel), so the tagger's own `kink_num` stops at the muon; and `vertex_kink_reject` (`TaggerCheckSTM.cxx:2474`) evaluating at `n−1` under the sentinel. The gate is ported verbatim, so this is a documented divergence (M15). Doc 57/58 measured this clause **still cannot reach the 9 structurally-unreachable items** — `anchor_vertex` snaps to a vertex within 2 cm, and those 9 have none nearby by construction — but T1c (now done) already recovers what it can from that population, so T1b's remaining value is the 14 proxy-only items plus whatever fraction of the general 51 a kink-corrected sentinel reaches on its own, independent of T1c | 2 | same six + the 22 collapse items whose kink sits 1–7 rows from the end | sentinel rate on the 51 (29 today); `T_stm_pass.kink_num` vs scan pin | knob in `TaggerCheckSTM`; SBND `ab_check.sh` PASS with it off; PDHD arm |
| **T2** | **Michel admission at the stop.** Trace the 7 "passes everything" arms and the 8 `michel_mip_lo` failures item by item; decide whether `mip_lo` should read total charge (KE) rather than median dQ/dx, and whether the arm may hang off any vertex within `stop_snap_tol`. Doc 57/58 add a concrete, now-recurring input: neither a retreated nor a split stop is automatically `is_stm`-confirmed (2 THRU items from the retreat, 3 more from the split — 5 total — picked up `michel_found=1` at `conn_type 1, dis 0` when the mechanism fired but the shape tests still correctly rejected the track) — T2 should decide whether a Michel arm at a *moved* stop (retreated or split) needs a stronger gate than one at the tagger's original stop | 3 | `039253_17/77` (77007, 0.10 MIP), `039349_22/63`, `039349_5/64`, `039252_0/75`, `039349_32/63`, `039349_7/4`, `039349_82/54`; plus the 5 stop-move-caused false Michels `039349_20/41`, `039349_48/21` (T1a) and `039252_2/79`, `039252_4/55`, `039349_61/62` (T1c) | Michel attachment (180 role 3 → 186 now); D 41 → ? | knob; §14.2 purity must not drop |
| **T3** | **Michel with no trajectory.** Doc 54 §2: the `pr54` isolated-residual drop (`NeutrinoOtherSegments.cxx:36`) discards every residual in the 2–24-point band — 363 on d53v — so add a default-OFF *stop-local admission* (keep a residual within ~20 cm of the STM stop regardless of the terminal floor). Cheap probe first: how many of the 363 sit within 20 cm of a scan stop. Plus the 29 detached scan-michel segments (doc pdhd/13 §8's held fix) and doc 55 §15.1's range-energy gate on `conn_type 2` | 3 | `039253_8/62`, `039253_2/77`, `039349_33/45`, `039349_81/54`; detached: `039252_6/100` (9.4 cm gap), `039252_15/77`, `039349_23/54`, `039349_5/65` | D 41 → ?, C 39 → ?, the 44-item unfitted-lump census | §15.1 cut as a knob first; admission knob priced on both ProtoDUNEs; a `pr67 fos` re-run for the 27 lumps with no drop line |
| **T4** | **instrument the fit at the stop** (writer-only). Persist `reg_flag_u/v/w` and per-plane `qU/qV/qW` on the `stm_fit` PC (`TaggerCheckSTM.cxx:1020`) and `FittedCharge2D::flag` on `T_proj_data`; then measure whether the smoother flattens the last 5 cm where a plane is dead | 1 | the 14 missed stoppers with one dead plane over the last 15 cm; `039253_3/29`, `039253_7/80` | per-item dead-plane fraction vs contrast | no verdict path; every existing branch byte-identical |
| **T5** | **fit-end undershoot.** Which of the tip trim (`TrackFitting.cxx:2609`), `end_point_limit`, or the terminal set owns the 5 class-F items; `absorb_bragg_stub` regressed on PDHD, so a new mechanism is needed | 1, 2 | `039252_5/73`, `039349_66/78`, `039253_13/39`, `039349_18/33`, `039253_0/110` | F 5 → 0; last-point dQ/dx | knob; PDHD gate |
| **T6** | **interior arms.** Classify the 172 no-role same-cluster segments — 152 attached to the chain interior, 46 of them > 8 cm at median 0.30 MIP (none hadron-hot, so `kOther`); publish `role 7 = other` so display and scan can see them; the over-clustering half goes upstream to `unmerge_assoc` / `protect_bundle` | 4 | `039252_3/74` (11), `039253_12/41`, `039253_17/127`, `039253_2/77`, `039253_8/62` | interior-arm table vs scan tags | payload/display first; no verdict path |
| **T7** | **sampling step and the two shape tests** (analysis; the owner decides). Make `TrackFitting.cxx:9702` read the knob; sweep `low_dis_limit` / `dx_norm_length`; measure the profile autocorrelation length; re-derive `bragg_tail_*`, `compare_range_cm`, `bragg_contrast_min`, `ks_margin` jointly on §4's table; test the peak-anchored `rr` origin; note `stm_recomb_calibrated` is false in production so the Bragg reference and the data are on different charge scales (doc pdhd/16) | 1 | the 57 rise-to-end misses (`039349_2/38`, `039349_29/45`, `039349_27/41`, `039349_3/46`); the 9 FPs (`039349_22/45`, `039349_6/62`) | §4's purity / efficiency table | any operating-point move is the owner's call (§5.1, §5.7) |
| **T8** | **coiled and unsupported fits** (G 18, H 20): publish `arc/span` over the last 20 cm and `charge_supported` per segment as reject-class inputs | 1 | `039349_48/21` (arc/span 3.41), `039253_6/82` (208 cm at 0.11 plateau) | G, H counts | later; doc pdvd/31/37/40 machinery |

**Order.** T1a and T1c are both done → T2 → T3 share the stop and each unlocks
the next; together T1a+T1c touched the class the scan sized largest, and
recovered 3 of it outright (2 + 1) with 7 more Michel segments freed as a side
effect (docs 57+58). T1b and T4 are independent of the graph stage and can run
in parallel; T1b's remaining value after T1c is smaller than doc 56 originally
priced it, since the 9 structurally-unreachable items are now split's alone to
reach and it already has. Then T2, T3, T5, T6, T7, T8.

**What stays out of this round.** The §15.1 cut is not applied; no threshold is
moved; the scan record is not re-labelled; no C++ is touched.

---

## 9. Found on the way, not fixed

1. `TrackFitting.cxx:9702` hard-codes `0.6*units::cm` where `:10076` derives
   the same quantity from `m_params.low_dis_limit/2` — moving the knob today
   desynchronises the multi-track third pass (T7's first step).
2. `vertex_kink_reject` (`TaggerCheckSTM.cxx:2474`) measures at `n−1` under the
   no-kink sentinel — at the Michel's tip on an overshoot (T1b).
3. No product carries the per-plane dead flag at a fit point (T4).
4. Scan-record segment ids are graph indices and will not survive a re-fit;
   `census_score.py` matches Michel segments by geometry for that reason, and
   the failure register's `F`/`H` rows (segment ids in `detail`) will need the
   same treatment when they are re-counted on a new arm.
5. `prep_stm_michel_scan.py` refuses to run without `--pin-tranche` once a label
   file exists — correct (doc pdhd/15 §10), but the repro in §0 has to say so.

---

## 10. Gates

| gate | result |
|---|---|
| `d56_failure_mechanisms.py` | rc 0; every table in §2–§6 is its output |
| `census_score.py --check` on d53v | **0 of 14 differ** from doc 55 §14 and the §17 class table |
| `mkstats.py --check` | still 0 of 4 differ (nothing in `pdvd/docs/scan/` moved) |
| re-prep of d53v into scratch (`--outdir`, `--sheetdir` under `$HOME/tmp/d56`) then `census_score.py --prep` on it | 569 of 569 payloads **byte-identical** to the committed `prep-pdvd/`; scorer output identical, `--check` 0 of 14 differ; the committed sheet and key untouched |
| `pdvd/docs/scan/*`, `pdvd/work/**`, `smx1a` (`5ffc889e`), `smx1` (`8fc76b33`) | untouched |
