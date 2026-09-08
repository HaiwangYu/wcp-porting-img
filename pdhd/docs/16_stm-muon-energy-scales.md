# The STM muon's three energy scales — doc pdhd/16

**Status: NOT bit-identical, and deliberately so.** `T_stm_michel` goes from
**88 branches to 97**. Nine are new (MCS and the three momenta). Six existing
ones move — `muon_ke_dqdx`, `michel_ke_dqdx`, `michel_ke_core`,
`dots_ke_dqdx`, `michel_ke_best`, and `muon_ke_best` below 4 cm — because
`check_stm_michel`'s dQ/dx → dE/dx inverse now carries the normalization its
own PID tables were built with. They are the *only* six: the before/after
census in §6.2 covers all 37 persisted scalars on all 579 / 325 candidates. **No
verdict moves**: `is_stm`, `reject_bits`, `contrast`, `plateau_med`, `ks_mu`,
`muon_len` are bit-identical candidate by candidate (§6), and the STM and
neutrino taggers keep the uncalibrated recombination instance untouched.

Owner ask, 2026-09-08: *"integrate the MCS so that we can provide the MCS
momentum estimation for the STM … the range estimation of muon energy is the
baseline … the inverse of this recombination model should be what we can use to
do dQ/dx → dE/dx conversion … the key question is whether this dQ/dx → dE/dx
energy estimation of muon agrees with the range estimation? If not, we need to
iterate on the recombination model."*

**The answer, in three lines.** It did not agree: the dQ/dx energy sat at
**0.765** of the range energy. The cause is not the drift field — that lever is
~1.5 % across 0.40–0.60 kV/cm and above 0.45 it pushes the *wrong way* — it is
the **×0.85 the PID tables carry and the recombination model has no slot for**,
times the charge the reconstruction does not recover. One measured
normalization `C` closes it, and the same number falls out of doc pdvd/50's
independent differential comparison.

## Repro

```bash
# the C++ and the model identity
cd /nfs/data/1/xqian/toolkit-dev/toolkit && wcbuild
./build/gen/wcdoctest-gen && ./build/clus/wcdoctest-clus && ./build/mcs/wcdoctest-mcs

# the fit, on arms already on disk -- no new arm needed to MEASURE C
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
python3 pdhd/docs/scripts/d16_stm_energy_scales.py --det pdvd \
    --arm 'pdvd/work/*_d15vnu' --out /home/xqian/tmp/d16/d16v_pre
python3 pdhd/docs/scripts/d16_stm_energy_scales.py --det pdhd \
    --arm 'pdhd/work/*_d15hnu' --exclude-apa0 --out /home/xqian/tmp/d16/d16h_pre

# the shipping arms.  RUN NO WAF TARGET WHILE THESE ARE LIVE -- not `install`,
# not even a plain `./wcb build`: the runner's plugin search reaches
# build/<pkg>/ as well as local/lib, so relinking build/ truncates the .so the
# live jobs are dlopening (it cost 20 of 31 PDHD events in doc pdhd/15).
ARM=d16vnu DET=pdvd SRC=d15vnu JOBS=8 pdhd/docs/scripts/d16_run_arms.sh
ARM=d16hnu DET=pdhd SRC=d15hnu JOBS=8 pdhd/docs/scripts/d16_run_arms.sh

# the closure, the before/after branch census and the figure
python3 pdhd/docs/scripts/d16_stm_energy_scales.py --det pdvd \
    --arm 'pdvd/work/*_d16vnu' --compare 'pdvd/work/*_d15vnu' \
    --out /home/xqian/tmp/d16/d16v
python3 pdhd/docs/scripts/d16_stm_energy_scales.py --det pdhd \
    --arm 'pdhd/work/*_d16hnu' --compare 'pdhd/work/*_d15hnu' \
    --out /home/xqian/tmp/d16/d16h
python3 pdhd/docs/scripts/d16_energy_plots.py --det pdvd \
    --before 'pdvd/work/*_d15vnu' --after 'pdvd/work/*_d16vnu' \
    -o pdhd/docs/figs/d16_energy_scales_pdvd.png

# the display
cd pdhd/stm_michel_scan
./prep_stm_michel_scan.py --det pdvd \
    --pin-tranche HEAD:pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
./selftest_stm_michel_scan.py            # group [O] is this round
```

---

## 1. The comparator already existed

`CheckSTM_Michel.cxx:1096-1097` has written both estimators for the same muon
since doc pdhd/14:

```cpp
rec.muon_ke_range = cal_kine_range(rec.muon_len, 13, particle_data()) / units::MeV;
for (auto& s : chain) rec.muon_ke_dqdx += segment_cal_kine_dQdx(s, m_recomb_model) / units::MeV;
```

`cal_kine_range` (`PRSegmentFunctions.cxx:2673`) is a lookup in the CSDA
range → KE table (`protodunevd/particle_dataset.jsonnet:146`,
`muon_range_function`, 1067 points, byte-identical across all three
detectors — it is the one table that does **not** depend on drift field or
charge calibration). `segment_cal_kine_dQdx` (`:2483`) integrates
`recomb_model->dE(dQ, dx)` over the fitted points.

So the question the owner asked was already answerable from arms on disk.
On `d15vnu` — 120 events, 579 candidates, **151 `is_stm`**, 166 137 fitted
chain points:

| quantity | value |
|---|---|
| `muon_ke_dqdx / muon_ke_range`, `is_stm` | **median 0.765**, IQR 0.691–0.818 |
| the same, all 579 candidates | 0.738 |
| median `muon_ke_range` / `muon_len` | 367 MeV / 154 cm (CSDA-consistent) |
| PDHD `d15hnu`, 61 events, 61 `is_stm` | **0.784** (0.793 excluding APA0) |

`T_stm_michel_pts` persists the per-point dQ/dx (`q`, e/cm, **already dQ/dx and
needing no `dQdx_scale` unwind**, unlike `T_rec_charge`), so the whole fit below
is a re-analysis: `d16_stm_energy_scales.py` reproduces the chain's own
`muon_ke_dqdx` from that tree to **0.19 %** (median ratio 1.0019 PDVD /
1.0026 PDHD), including both of `segment_cal_kine_dQdx`'s clamps.

---

## 2. Root cause — the ×0.85 the model has no slot for

**Symptom.** The calorimetric energy of a stopping muon is a quarter below its
range energy, on both ProtoDUNEs.

**Root cause.** Two objects in the same config are built from the same
Modified Box and differ by a constant:

* the PID `*DeDx` tables (`protodunevd/particle_dataset.jsonnet:13-31`),
  generated by `energy_loss/pion_travel/convert_field.C:42,71` as
  ```
  dQ/dx = ln(alpha + beta'*dE/dx) / (beta' * W_ion) * 0.85
  alpha = 0.93, beta = 0.212, rho = 1.38, W_ion = 23.6 eV, beta' = beta/(rho*E)
  ```
* the live recombination model, `Gen::PracticalBoxRecombination`
  (`pr.jsonnet:1230-1234`) — the *same* α/β/ρ and the *same* field, and
  **no 0.85** (`gen/src/PracticalRecombinationModels.cxx:43-52`).

`recomb_model->dE()` applied to a measured dQ/dx therefore lands
`1/0.85 = 1.176` away from the scale its own tables were built on. At the PDVD
plateau (54.7 ke/cm) it returns **1.826 MeV/cm** where inverting the table's own
rr = 59.5 cm entry gives **2.193**.

**Why it hid.** Nothing in the chain ever put the two numbers next to each
other. `do_track_comp` compares measured dQ/dx against the *tables* and never
touches a recombination model; `segment_cal_kine_dQdx` inverts the *model* and
never touches the tables. Both are reached from the same component with the
same charge. The energy they disagree about was not persisted at all until doc
pdhd/14, and doc pdhd/14 persisted both estimators without comparing them.
`energy_loss/docs/dqdx_consistency_check.md` §6 names the 0.85 as "the thing to
chase"; this is the first measurement that prices it on ProtoDUNE data.

---

## 3. The field is not the lever — measured, not asserted

The owner's hypothesis was *"maybe with slightly higher effective E-field"*.
It is testable two ways and fails both.

**Pointwise.** At a fixed measured plateau dQ/dx of 54.7 ke/cm,
`PracticalBoxRecombination::dE()` returns

| E (kV/cm) | 0.40 | 0.45 | 0.4959 | 0.55 | 0.60 |
|---|---|---|---|---|---|
| inferred dE/dx (MeV/cm) | 1.853 | **1.826** | 1.803 | 1.784 | 1.771 |

against a true plateau near 2.19. The entire 0.40–0.60 span moves the answer by
4 %, against a 17 % gap, and **above 0.45 it moves the wrong way** — raising the
field lowers the inferred dE/dx.

**Whole-sample.** Refitting the normalization at each trial field only trades
`C` against `E` and does not tighten the sample:

| E (kV/cm) | 0.40 | 0.45 | 0.4959 | 0.55 | 0.60 |
|---|---|---|---|---|---|
| PDVD fitted `C` | 0.8134 | **0.7941** | 0.7812 | 0.7698 | 0.7611 |
| rms(log ratio) | 0.2306 | 0.2242 | 0.2189 | 0.2134 | 0.2089 |

The spread improves by 7 % relative over a 33 % change in field — the two
parameters are degenerate and the data does not prefer a field.

**And the residual has no shape to fix.** After one flat `C`, the ratio is flat
in muon length across the whole range — short muons are Bragg-dominated, long
ones plateau-dominated, so a shape error would show here and does not:

| muon length (cm) | <80 | 80–120 | 120–180 | 180–250 | >250 |
|---|---|---|---|---|---|
| PDVD, n | 32 | 31 | 20 | 27 | 41 |
| ratio median | 0.975 | 1.016 | 1.020 | 0.999 | 0.984 |

A free power on dE/dx (`PowerBoxRecombination`'s `p`) gives χ² 0.48 at p = 0.85
against 0.65 at p = 1 over those five bins — **Δχ² = 0.17, nothing**. So p = 1,
the plain Modified Box, is what ships.

---

## 4. What is fitted, and what the number means

Requiring `median(E_dQdx / E_range) = 1` over the `is_stm` sample:

| detector | arm | n | `C` | k (= β′·pivot) | E (kV/cm) |
|---|---|---|---|---|---|
| PDVD | `d15vnu`, 120 evt | 151 | **0.7941 ± 0.0093** | 0.7169082125603865 | 0.45 |
| PDHD, APA0 excluded | `d15hnu`, 61 evt | 54 | **0.8120 ± 0.0138** | 0.6505519170239442 | 0.4959 |
| PDHD, all APAs | " | 61 | 0.8088 ± 0.0151 | " | " |

errors from a 200-sample bootstrap over tracks.

**APA0 is excluded on purpose.** Doc pdvd/50 §13 measures APA0 at 0.654 of the
muon table against 1.01–1.03 for APA1/2/3 — the `pdhd/docs/sp-apa0-plane2.md`
hardware fault. This sample sees the same thing per readout unit:

| unit | PDVD | | unit | PDHD |
|---|---|---|---|---|
| bottom (x<0, anodes 0–3), n=43 | 1.109 | | APA0, n=7 | **0.845** |
| top (x>0, anodes 4–7), n=108 | 0.976 | | APA1, n=10 | 1.001 |
| | | | APA2, n=23 | 1.032 |
| | | | APA3, n=21 | 1.008 |

(ratios after the calibration). Only 7 of 61 PDHD muons stop in APA0, so the two
PDHD constants agree inside their errors — but a blended constant would still be
absorbing a known instrumental defect.

**`C` is not a recombination measurement.** It is
`0.85 × (the charge the reconstruction does not recover)`, and both halves are
independently known:

* 0.85 is `convert_field.C`'s own factor, documented in
  `particle_dataset.jsonnet:55-59` as "not a physics term and degenerate with
  the missing gain / electron-lifetime calibration";
* doc pdvd/50 §14 measures the second half *differentially* — PDVD's
  reconstructed dQ/dx against its own tables — at k = 0.86 (unselected) to 0.95
  (charge-complete tracks). 0.85 × 0.93 = **0.79**.

So a differential dQ/dx-vs-residual-range comparison and an absolute
energy-vs-range comparison, on different samples through different code, give
the same normalization to ~1 %. That agreement is the evidence that the
Modified Box *shape* at 0.45 kV/cm is right and only its scale was missing.

**One carrier only.** Three places in this tree can absorb the same
gain × lifetime × recombination degeneracy: the tables' ×0.85,
`PowerBoxRecombination`'s `C`, and the
`kine_recom_factor` / `kine_fudge_factor` family (PDVD runs SBND-transfer
0.87 / 0.58 / 0.51). This round moves **only** `C`. The tables are not
regenerated and the `kine_*` factors are not touched.

---

## 5. The change

### 5.1 The calibrated inverse needs no new C++

`Gen::PowerBoxRecombination` (`gen/src/RecombinationModels.cxx:143-180`)
computes `u = k(dE/dx / pivot)^p`, `R = ln(A+u)/u`, `dQ/dx = C·R·(dE/dx)/W`. At
**p = 1** and **k = β′·pivot** that *is* the Modified Box at field E, with `C`
exposed. `gen/test/doctest_powerbox_recombination.cxx` pins the identity for
both ProtoDUNE fields to 1e-9 in both directions, and — because the two classes
*do* diverge outside the interpolation range (PowerBox saturates at
`dedx_max = 77` MeV/cm and returns 0 for dQ/dx ≤ 0, the Box does neither) — it
also replays `segment_cal_kine_dQdx`'s own guards to show the divergence is
**unobservable through the only function that consumes these models**: any
dQ/dx that reaches saturation already exceeds the 50 MeV/cm ceiling
(285 vs 326 ke/cm on PDVD, 311 vs 357 on PDHD), and a negative dQ/dx is clamped
to zero either way.

New `pdvd_stm_recomb` / `pdhd_stm_recomb` instances in
`cfg/pgrapher/experiment/{protodunevd,pdhd}/pr.jsonnet`, bound as
`recombination_model` on the **`check_stm_michel` node alone**. New function arg
`stm_recomb_calibrated`, C++/jsonnet default **false**; both ProtoDUNE drivers
set it true.

### 5.2 MCS, called directly

`clus` already links `WireCellMcs` (`clus/wscript_build:1`) — no build-system
change and no new dependency. `PR::mcs_fill_kine` is **not** reused: it writes a
`KineInfo` this component does not have, and its `beam_window_only` default
returns silently on cosmics. `CheckSTM_Michel::fill_mcs` calls the engine
directly with the muon profile's own points (cm on that boundary), entry as
`vtx_start` — the high-energy end the CSDA walk starts from — and the stop as
`vtx_end`.

Knobs, all C++ default off/legacy so an absent bag leaves the compiled config
where doc pdhd/15 left it: `mcs_enable` (false), `mcs_min_len_cm` (40),
`mcs_cathode_x` (0), `mcs_cathode_xcut` (0). Both drivers set
`mcs_enable: true` and `mcs_cathode_xcut: 5.0` — both ProtoDUNEs are
cathode-centred at x = 0 and lose charge at the seam, the same value SBND
production runs.

### 5.3 The nine new branches

`muon_ke_mcs`, `muon_mcs_amb`, `muon_mcs_tracklen`, `muon_mcs_range_ke`
(the engine's own CSDA over its trimmed path — an independent second range
estimate), `muon_mcs_nsegs`, `muon_mcs_bad_path`, and
`muon_p_range` / `muon_p_dqdx` / `muon_p_mcs` =
`sqrt((KE + m_mu)² − m_mu²)`, m_mu = 105.658 MeV.

**`-1` means "not computed" and stays −1.** The engine refuses a path it could
not trim, one with fewer than 20 trimmed points, one whose trimmed end is
nearer than 28 cm to the stop, or one yielding fewer than two 14 cm segments.
A zero there would read as a measured zero energy and pass every `>= 0` gate,
so the non-finite guard at `:1495` gained a second loop that restores −1 rather
than 0 for these fields (`feedback_nan_fails_positive_gate`).

**`muon_ke_best` does not change.** For a stopping muon range is the better
estimator and MCS is a cross-check; the `< 4 cm ⇒ dQ/dx` rule stands. Group
`[O]` of the scan self-test pins that nothing silently promoted MCS.

---

## 6. Verification

Arms `d16vnu` (120 events, 579 candidates) and `d16hnu` (61, 325), the same
pctree input as `d15*nu` (symlinked, `d16_run_arms.sh`). `libWireCellClus.so`
md5 **`4cd43f0e1c75`** before **and** after both arms — the runner fingerprints
the pin at both ends because doc pdvd/43 lost a round to a rebuild between arms.
The arms were produced twice: a first pass on `0da184196bf0`, then re-run in
full on the shipped `.so` after a comment/definition reorder inside
`CheckSTM_Michel`'s class body changed the binary. Every number below is from
the second pass, so no result carries a "the source moved afterwards" asterisk.
119 of 120 PDVD events carry `T_stm_michel`; `039252_11` produces no STM
candidate and did not in `d15vnu` either.

### 6.1 The closure

| | PDVD `d16vnu` | PDHD `d16hnu` | PDHD, APA0 excluded |
|---|---|---|---|
| n `is_stm` | 151 | 61 | 54 |
| `muon_ke_dqdx / muon_ke_range` | **1.0021** | **0.9999** | 1.0119 |
| IQR | 0.904–1.091 | 0.894–1.086 | 0.906–1.089 |
| still flat in length | yes, 0.97–1.02 | yes | yes |

The per-track spread (IQR ±10 %) is **not** reduced by this round and is not
meant to be: it is the drift and readout-unit structure of §7, plus fit quality.
`C` is a median.

### 6.2 What moved, and the causal check

`is_stm` matching before and after proves nothing on its own — the
recombination model is on no verdict path, so that is my own reasoning restated.
The branches a **re-run** could move are the ones fed by `preload_clusters` →
`prepare_data()` (doc pdhd/15 §7's companion perturbation). Those are checked
explicitly:

The census covers **every** persisted scalar that could carry an energy or a
verdict — 37 branches, including all six other `*_ke_*` columns — so the two
lists below are exhaustive over the compared set, not a sample. Both are read
off all 579 (PDVD) / 325 (PDHD) common candidates, and the two detectors give
the *same* partition.

**Bit-identical, candidate by candidate, on all 579 / 325 rows (31):**
`cluster_id`, `is_stm`, `reject_bits`, `muon_len`, `muon_ke_range`,
`michel_ke_range`, `michel_ke_charge`, `dots_ke_unfit`, `dots_charge_unfit`,
`michel_n_pieces`, `n_dots`, `n_michel_segs`, `michel_conn_type`,
`michel_found`, `n_live_pts`, `n_dead_pts`, `dead_frac_cmp`, `contrast`,
`plateau_med`, `ks_mu`, `n_chain_segs`, `stop_dis`, and the ten geometry
columns (`entry_{x,y,z}`, `stop_{x,y,z}`, `tagger_stop_{x,y,z}`).

`michel_ke_range` sitting in this list is the check that the *range* arm of the
comparator is genuinely independent of the recombination model — it is a CSDA
table lookup on a length, and the length itself (`muon_len`) is bit-identical
too.

**Moved (6):** `muon_ke_dqdx` (×1.3114 PDVD / ×1.2587 PDHD, median),
`michel_ke_dqdx` (×1.2994 / ×1.2273), `michel_ke_core`, `dots_ke_dqdx`,
`michel_ke_best`, and `muon_ke_best` — the last only on muons shorter than
4 cm, where `best` is the dQ/dx number by the `PRSegmentFunctions.cxx:2900`
rule. Every mover is a dQ/dx-derived energy; nothing else in the tree moves.
`michel_ke_charge`, `dots_ke_unfit` and `dots_charge_unfit` do **not** move:
they ride the flat `kine_*` / `stm_michel_charge_to_energy` factors, the
carrier this round deliberately leaves alone.

**A second, smaller behaviour change, measured rather than assumed.** The
PowerBox inverse returns 0 for dQ/dx ≤ 0 where the Box's returns a spurious
`(1−A)/β′` — **0.205 MeV/cm on PDVD, 0.226 on PDHD** — because `R = ln(A+u)/u`
sends dQ/dx to −∞ as dE/dx → 0 and inverting there is meaningless. The window
is dQ/dx ∈ (ln A/(β′·W), 0], i.e. (−9008, 0] e/cm on PDVD. Priced on the arms:

| points | PDVD | PDHD |
|---|---|---|
| muon chain (role 1) | **0 of 166 137** | **0 of 97 872** |
| Michel arm (role 3) | 30 of 1 505 (2.0 %) | 16 of 899 (1.8 %) |
| dot / piece (role 4) | 12 of 413 | 7 of 382 |

So `muon_ke_dqdx` is untouched by it, and the whole effect on the Michel side is
under **0.03 MeV per object**. It is an improvement — a cell the charge solve
could not read should contribute no energy — but it is a change and it is named.

### 6.3 The Michel endpoint — an absolute scale the fit never saw

`michel_ke_dqdx`, objects with `michel_found` and a ≥ 10 cm muon:

| | n | median | p90 | max | above 52.8 MeV |
|---|---|---|---|---|---|
| PDVD before | 158 | 12.7 | 29.3 | 51.6 | 0 |
| PDVD after | 158 | 16.5 | 38.8 | 76.8 | **1** |
| PDHD before | 122 | 6.2 | 23.8 | 70.4 | 2 |
| PDHD after | 122 | 7.5 | 30.4 | 105.6 | **2** |

No population appears above the endpoint — PDHD's count does not move at all,
and PDVD's single new entry is `039252_15` cluster **77**, which already sat at
**51.6 MeV**, 2 % under the ceiling, before this round. The other two are
`028084_18/122` (60.7 → 79.3) and `029107_19/95` (70.4 → 105.6, a 677 cm muon).
All three predate the calibration; it re-scaled a tail it did not create. The
thing to check on them is doc pdhd/15's **gathering** rule, not the scale.

**A caveat that must not be lost:** `C` was fitted on muon *tracks* and the
Michel energies inherit it because a component has one recombination model. For
a shower-like object at higher local dE/dx that is an extrapolation. The
endpoint is the only absolute handle available and it is consistent; a Michel
scale of its own would need MC truth (doc pdvd/48's open item).

### 6.4 MCS, validated against range on data

This is the first data-side answer to doc 84's deferred item 1 (the MCS
absolute scale), and it is on two detectors that were not part of the SBND tune.

| | PDVD | PDHD |
|---|---|---|
| MCS computed | 134 / 151 (**88.7 %**) | 59 / 61 (**96.7 %**) |
| `amb < 0.2` | 65 (43.0 %) | 39 (63.9 %) |
| `ke_MCS / ke_range`, all computed | 0.956 (IQR 0.897–1.033) | 0.901 (IQR 0.816–0.954) |
| `ke_MCS / ke_range`, `amb < 0.2` | **0.933** (IQR 0.893–0.958) | **0.897** (IQR 0.853–0.938) |

Doc 84 R3.5 measured **0.943** (IQR 0.914–0.980) on SBND with the same
`amb < 0.2` cut. Three detectors, three samples, one code path: MCS reads
**6–10 % below the CSDA range** of a contained stopping muon and the ambiguity
cut is what makes the number meaningful — the unselected sample scatters by a
factor of two (panel 3 of the figure). The usable fraction here (43 % / 64 %)
is far better than SBND's 23.5 %, as expected for clean single stopping muons.

**This is reported, not acted on.** Whether that 6–10 % is an MCS scale, a
range-table convention, or the muon sample is exactly the question doc 84 left
to MC truth. Nothing in this round tunes it.

### 6.5 Gates

| gate | result |
|---|---|
| `./build/gen/wcdoctest-gen` | **18 / 18**, 789 assertions — includes the p = 1 identity for both fields, the whole-domain replay of `segment_cal_kine_dQdx`'s guards, and the calibrated PDVD operating point |
| `./build/clus/wcdoctest-clus` | **335 / 335**, 23 172 assertions |
| `./build/mcs/wcdoctest-mcs` | **4 / 4**, 5 651 assertions |
| compiled-config, knob **off** vs pre-doc-16 HEAD | 60 nodes vs 60, **one** difference: the three `mcs_*` keys added to `CheckSTM_Michel` |
| compiled-config, knob **on** vs off | adds exactly one node (`PowerBoxRecombination:pdvd_stm_recomb`) and changes exactly one (`CheckSTM_Michel`); `TaggerCheckSTM` keeps `pdvd_box_recomb` |
| python re-implementation vs the chain (G1) | 1.0017 PDVD / 1.0024 PDHD at the shipped `C` |
| before/after census coverage | **37 scalars** — every persisted energy, verdict and geometry column — on 579 / 325 common candidates; 31 bit-identical, 6 moved, the same partition on both detectors (§6.2) |
| both clamps (`43e3×1000`, 50 MeV/cm) | 0 and **1** firing of 46 592 / 20 021 points |
| PowerBox saturation reachable? | no — the 50 MeV/cm ceiling binds at 285 ke/cm against the branch end at 326 (PDVD), 311 vs 357 (PDHD) |
| `selftest_stm_michel_scan.py` | **72 069 checks, 0 failed**, both detectors, incl. new group `[O]` |
| `selftest_smx3d_browser.py` | **59 / 59** each detector |
| scan sheet vs the committed one | identical on every data row; the only diff is the two header lines (arm name, pin source). 568 / 302 items, `scan_id` and `tranche` unchanged |
| answer key | one column moves: `michel_ke_best`, on the 158 Michel-carrying rows |

The scan was re-prepped with **`--pin-tranche`** from the committed sheet (doc
pdhd/15 §10's rule) and `pdvd/work/stm_michel_labels/smx1` was not touched —
the owner's four labels keep their tag, their `scan_id` and their list order.

---

## 7. Open items — reported, not fixed

1. **A drift-dependent charge scale, ~8 % on PDVD**, which one flat constant
   cannot absorb: after calibration the ratio runs 0.981 / 0.961 / 1.039 /
   1.043 / 1.055 across drift bins 0–60 … 240–400 cm. The sign is **wrong for
   attenuation** — charge appears to grow with drift — which is the same
   unphysical `tau_eff = −6037 us` `pdvd/stm/dqdx_rr_field_check.tsv` already
   records. Owner decision 2026-09-08: report it, do not fit it. It is a
   position calibration, not a recombination result.
2. **PDVD's two drift volumes disagree by 14 %**: bottom (x < 0, anodes 0–3)
   1.109 against top 0.976, on 43 and 108 muons. Doc pdhd/03 §6 saw the same
   asymmetry in the raw plateau (44.5 vs 53.5 ke/cm).
3. **PDHD APA0 sits at 0.845** where APA1/2/3 give 1.00–1.03, consistent with
   doc pdvd/50 §13 and `pdhd/docs/sp-apa0-plane2.md`. Excluded from the fit;
   with only 7 of 61 muons there it moves `C` by 0.4 %.
4. **The chain-wide flip is not taken.** `use_power_recomb` would hand the same
   calibrated model to the STM and neutrino taggers and to every model-driven
   dE/dx in the PR chain — a production output change needing its own A/B
   campaign. Doc pdvd/25 M7 ("fit a PDVD power box") is now answerable: the
   parameters are `{A: 0.93, k: 0.7169082125603865, p: 1.0, C: 0.7941,
   pivot: 2.1, Wi: 23.6e-6, dedx_max: 77.0}`, but they are **not** written into
   `pdvd_power_recomb`, because that block is what `use_power_recomb=true`
   selects and editing it would change what a flip means without measuring it.
5. **The Michel object has no scale of its own** (§6.3) and three objects sit
   above the 52.8 MeV endpoint, all of them there before this round.
6. **MCS reads 6–10 % below range** on all three detectors (§6.4) — doc 84's
   deferred item, still needing MC truth to say whether it is scale or
   convention.

## 8. Files

| | |
|---|---|
| `clus/src/CheckSTM_Michel.cxx` | `fill_mcs`, `mom_from_ke`, four knobs, nine branches, the −1-preserving guard, the log line |
| `cfg/pgrapher/experiment/{protodunevd,pdhd}/pr.jsonnet` | `{pdvd,pdhd}_stm_recomb`, `stm_recomb_calibrated` (default false), the component-only binding |
| `gen/test/doctest_powerbox_recombination.cxx` | the p = 1 identity, the domain replay, the calibrated operating point |
| `clus/test/doctest_check_stm_michel_defaults.cxx` | the four MCS knob defaults |
| `pdvd/wct-pr-perevt.jsonnet`, `pdhd/wct-pr-perevt.jsonnet` | `stm_recomb_calibrated=true`, the `mcs_*` bag |
| `pdhd/docs/scripts/d16_stm_energy_scales.py` | the fit and every number above |
| `pdhd/docs/scripts/d16_energy_plots.py`, `d16_run_arms.sh` | the figure, the arms |
| `pdhd/stm_michel_scan/{prep_stm_michel_scan,stm_michel_viewer,smkine,selftest_stm_michel_scan}.py` | d16 arms, the MCS keys, the calibrated inverse, group `[O]` |
| `pdhd/docs/figs/d16_energy_scales_{pdvd,pdhd}.png` | the figure |

**Not touched, on purpose:** `energy_loss/` is a separate repository, and
nothing in this round changes it. Its `pion_travel/convert_field.C` is the
*source* of the ×0.85 (§2) and its `docs/dqdx_consistency_check.md` §6 already
names that factor as "the thing to chase" — but that question is answered
**here**, on ProtoDUNE data, and no file over there records it. A reader who
starts from `energy_loss/docs` should be sent to this doc; a reader who starts
here should not go looking for a companion change in `energy_loss/`, because
there isn't one. The ×0.85 stays in the table generator, where it belongs: the
tables are the PID reference and moving them would move every verdict. What
this round did was give the *inverse* the matching normalization.

![PDVD](figs/d16_energy_scales_pdvd.png)

![PDHD](figs/d16_energy_scales_pdhd.png)
