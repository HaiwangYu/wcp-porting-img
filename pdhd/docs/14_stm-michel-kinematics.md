# The muon energy CheckSTM_Michel computed and threw away — doc pdhd/14

**Status: NOT bit-identical.** `T_stm_michel` gains four branches on every
`-nu` run of both ProtoDUNEs. The 75 pre-existing branches are proven
bit-unchanged (§3). Owner decision 2026-09-07: *"this can be new feature
default on"* — no default-OFF knob, because the module is under active
development on PDHD and PDVD and a knob would only make the display's
provenance ambiguous.

## Repro

```bash
# the C++ (already installed; freshness proof in sec 3)
cd /nfs/data/1/xqian/toolkit-dev/toolkit && wcbuild && ./build/clus/wcdoctest-clus

# one event, the owner's item
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd
mkdir -p work/039252_15_d14vnu && \
  ln -sfn ../039252_15_d51vclus/pctree-evt298777.tar.gz work/039252_15_d14vnu/ && \
  ln -sfn ../039252_15_d51vclus/pctree-evt298777.tlas   work/039252_15_d14vnu/
./run_pr_evt.sh -s d14vnu -nu 039252 15

# both scan arms, re-run with the feature in (sec 5).  Do NOT wcbuild while
# these run: an install swaps local/lib under the live jobs and they die with
# "failed to load plugin: WireCellClus" (it cost 9 events here).
( cd pdvd && PDVD_MAX_JOBS=6 PDVD_LIGHT_SUFFIX=_keep \
    ./run_pr_evt.sh -nu -stm-fit -s d14vnu <run> all )   # 039252 039253 039349
( cd pdhd && PDHD_MAX_JOBS=6 \
    ./run_pr_evt.sh -nu -stm-fit -s d14hnu <run> all )   # 028084 029107

# the display
cd pdhd/stm_michel_scan
python3 prep_stm_michel_scan.py --det pdvd
python3 selftest_stm_michel_scan.py            # includes group L
python3 selftest_smx3d_browser.py --det pdvd
```

## 1. The question

Scanning `039252_15 / 77` on the doc-12 display the owner asked for the muon's
and the Michel's energies, and whether the chain carries a particle flow —
`muon -> Michel electron` — that could be drawn.

A first pass computed the energies in the prep script. The owner stopped it:

> *"all the information should be taken from the output of the chain, not by
> your calculations. Otherwise we cannot improve this module."*

That is the whole design of this round. A display that fills the module's gaps
with its own arithmetic looks complete and measures nothing; a display that
shows exactly what `CheckSTM_Michel` emits is an inventory of what the module
is missing. So no number below is computed by the viewer or the prep. Where the
chain writes nothing, the panel says so in red.

## 2. What the chain had, and the one thing it did not

Already persisted, and already on the display behind REVEAL:

| branch | meaning |
|---|---|
| `michel_ke_dqdx` / `_range` / `_best` | the Michel's energy (`:1197-1226`; with `build_michel_shower` on — the C++ default, not overridden by either job's `stm_michel_knobs` bag (`:312`) — `_dqdx` is `Shower::calculate_kinematics`' multi-segment sum, not one segment) |
| `dots_ke_dqdx` | the detached path's sum over dot segments (`:1262`) |
| `dots_charge_unfit` | electrons in same-bundle clusters that were never fitted — no `dx`, so no MeV is possible |

**Absent: any muon energy at all.** `set_pdg` (`CheckSTM_Michel.cxx:661-668`)
builds a full 4-momentum for every chain segment —

```cpp
auto p4 = segment_cal_4mom(seg, pdg, particle_data(), m_recomb_model, m_mip_dqdx / units::cm);
seg->particle_info(pinfo);
```

— hangs it on the segment, and nothing ever reads it again. A hand scanner
looking at a 40 MeV blob beside a stopping muon could not ask the obvious
question, because the muon's energy was not in the output.

## 3. What was added

`clus/src/CheckSTM_Michel.cxx`, unconditional:

| branch | how |
|---|---|
| `muon_ke_range` | `cal_kine_range(muon_len, 13, particle_data())`. Taken on the **chain's total length**, never per segment: `cal_kine_range` is a table lookup in *range*, so summing per-segment range energies over a chain the stop-extension walked would be wrong. |
| `muon_ke_dqdx` | `segment_cal_kine_dQdx` summed segment by segment — that one *is* additive, and this is the same construction `:1268` uses for the dots. |
| `muon_ke_best` | the toolkit's own rule (`PRSegmentFunctions.cxx:2900`): range at ≥ 4 cm, dQ/dx below. |
| `michel_seg_id` | the daughter's segment id, in the same `cluster*1000 + graph index` encoding as `stop_vtx_id` and `T_stm_michel_pts.seg_id`. |

**One gate will churn, expected and dated.**
`pdhd/stm/perf/d30_hash_gate.py:43` names `T_stm_michel` in its explicit tree
list, so its per-tree digest changes for every event from 2026-09-07 onward.
That is these four branches and nothing else — the table above is the evidence.
Re-baseline it against a `d14*` arm; do not chase it as a regression.

**Line numbers doc pdhd/13 cites have moved**, because this change inserts into
the same file. Its `:812` (the `dot_max_len_cm` companion-admission cut) is now
**`:826`**; its `:1169` (`michel_found = 1`, defect D1) is now **`:1197`**.
Doc 13's text is left as the record of what it measured; use this mapping.

**Freshness proof (M1):** `clus/src/CheckSTM_Michel.cxx` 20:28 →
`local/lib/libWireCellClus.so` 20:33. `./build/clus/wcdoctest-clus`: 334 cases,
23144 assertions, 0 failed.

**Containment proof**, at arm scale — every branch of every candidate, `d51*nu`
vs `d14*nu` on the same pctree inputs:

| | files | candidate rows | pre-existing branches | differing |
|---|---|---|---|---|
| PDHD | 61 | 325 | 75 | **none** |
| PDVD | 119 | 579 | 75 | **none** |

Per event, the shape of it:

```
new branches:   michel_seg_id, muon_ke_best, muon_ke_dqdx, muon_ke_range
lost branches:  none
pre-existing branches that changed: NONE (75 branches, 5 rows)
```

So this is additive: nothing the chain already decided moved. That is why the
scan sheet and its four-way stratification survive the arm swap unchanged (§4).

**Arm swap.** The `d51*nu` arms predate the feature, so both were re-run on the
same pctree inputs as `d14hnu` (61 events) / `d14vnu` (120 events) and the prep
now points there. Because the 75 pre-existing branches are bit-unchanged, the
scan sheet and key came back **byte-identical apart from the arm name in their
header comment** — verified with `diff` on the four files — so the tranches, the
S1-S4 strata and the owner's existing labels are untouched by the swap.

**On the owner's item** (`039252_15 / 77`, `muon_len` 112.54 cm):

```
muon_ke_range  278.0 MeV
muon_ke_dqdx   222.1 MeV
muon_ke_best   278.0 MeV
michel_seg_id  -1        <- no daughter: this is the doc-13 loss, in one field
```

The two routes disagree by 20 %. That is not noise to be averaged away and the
display shows both rather than picking one — it is the same "when the two
routes DISAGREE, say so" rule the pin panel already follows.

## 4. The particle flow — what exists and what does not

The chain stamps a PDG on every segment (`set_pdg`: 13 on chain members, 11 on
delta rays, Michel arms, dots and shower members) and
`PdvdPrMagnifyTrackingVisitor.cxx:914` persists it per fitted point as
`T_rec_charge.particle_id`. `T_stm_michel_pts.role` carries the topological
role (1 muon / 2 delta / 3 Michel arm / 4 dot).

**But a PDG is not a parentage.** The only `mu -> e` relation the chain ever
establishes is a **shared vertex**:

- `michel_conn_type == 1` (attached): the Michel arm leaves `stop_v`, the very
  vertex where the muon chain ends. `stop_vtx_id` named the mother's end;
  `michel_seg_id` now names the daughter, so the edge is complete in the output.
- `michel_conn_type == 2` (detached): there is **no shared vertex and no link of
  any kind**. The dots were admitted on distance to the stop alone (`:1250`),
  carry pdg 11, and nothing but proximity ties them to the muon. The panel says
  this in red instead of drawing an edge the chain never established.
- `michel_conn_type == 0`: no daughter.

**One caveat on the ids.** `stop_vtx_id` and `michel_seg_id` share the
`cluster*1000 + graph index` encoding, but vertices and segments have separate
graph-index spaces — so the same integer can name both, and does: on PDVD
`039252_15` cluster 91 the shared vertex and the Michel segment are both
`91002`. They are not the same object. Join `michel_seg_id` against
`T_stm_michel_pts.seg_id` (or `T_rec_charge.sub_cluster_id`) and `stop_vtx_id`
against the vertex rows (`flag_vertex == 1`), never against each other.

> **CORRECTION (doc pdhd/15, 2026-09-07).** The two paragraphs above are
> wrong on one point and this doc's claim below is wrong outright. There **is**
> a PF tree on this path: `MultiAlgBlobClustering::fill_bee_pf_tree()` runs —
> `bee_pf` is bound at `cfg/pgrapher/experiment/pdhd/pr.jsonnet:2243` and
> `protodunevd/pr.jsonnet:2232` — and writes `mc.json` into `mabc-pr.zip`,
> where `039252_15` reads `mu- 278 MeV` for cluster 77 and `mu- 425 MeV ->
> e- 16 MeV` for cluster 91. A **detached** Michel is linked there too, through
> a pseudo-gamma carrier node (`MultiAlgBlobClustering.cxx:2153-2177`), so
> "no link of any kind" was also wrong: what `conn_type == 2` lacked was a link
> in *this tree*, which doc pdhd/15 adds (`michel_parent_vtx_id`,
> `michel_dis_cm`, `michel_start_*`, and `michel_found` for both types).
> Doc pdhd/15 §2 carries the evidence.

~~There is **no PF tree** on this path.~~ `fill_bee_pf_tree` is **not** confined
to the `TaggerCheckNeutrino` tail — see the correction above.

## 5. The display

`pdhd/stm_michel_scan/stm_michel_viewer.py` gains one panel, `flow_div`, and one
clause on the un-blinded status line. Every field in both is a `T_stm_michel`
branch; the viewer computes nothing.

- **un-blinded**, beside `muon_len` which the sheet already shows:
  `chain muon KE 278.0 MeV (range 278.0 / dQ/dx 222.1)`. `muon_ke_best` is
  `cal_kine_range(muon_len, 13)` for every chain over 4 cm, i.e. that same
  already-visible number in MeV, and it says nothing about the Michel.
- **behind REVEAL**, where the Michel verdict already lived: the `mu -> e`
  block — mother, link, daughter — plus, on a `conn_type 2` item, the standing
  doc-13 D1 warning that `michel_found` is 0 although a Michel *was*
  reconstructed.
- On an arm older than this doc the panel prints, in red, that the arm predates
  doc pdhd/14 and carries no muon energy. It does not fall back to a computed
  one.

## 6. Gates

`selftest_stm_michel_scan.py` group **L**. `smkine.py` reimplements the two
toolkit estimators and is used **only here, against the production binary** —
never in the prep and never in the viewer, per §1.

| check | n | result |
|---|---|---|
| L1 `muon_ke_range` vs `np.interp` on the detector's own `particle_dataset.jsonnet` table | 904 | exact, worst 0.0 MeV |
| L2a `muon_ke_dqdx` on **single-segment chains**, where role-1's `seg_id` names the segment exactly | 291 | exact, worst rel 1.3×10⁻¹⁵ |
| L2b an independent **profile integral** `Σ dE/dx(q)·dL` over the role-1 points, on every gap-free chain | 593 (311 skipped, §6.2) | median 0.996 / 0.997, all inside [0.75, 1.25] |
| L3 `muon_ke_best` | 904 | follows the toolkit's ≥ 4 cm rule |
| L4 `michel_seg_id` names a role-3 (attached) or role-4 (detached) segment, or is −1 | 263 | pass, with the §6.3 exception |
| L5 `dots_ke_dqdx` — the pre-doc-14 branch | 104 | exact, worst rel 3.2×10⁻¹² — this is what proves `smkine`'s own arithmetic (the endpoint-shortening and clamp rules) |
| `test_kine_payload` | 52 | the four branches reach the payload byte-for-byte |
| `test_kine_blind` + browser | — | blinded on load, no MeV before REVEAL, painted by the real toggle |

**10636 headless checks, 0 failed** (6452 before this round); **56 browser
checks, 0 failed** per detector (44 before).

Three things the first version of this gate got wrong, all worth recording
because each is a trap for the next person reading this output.

### 6.1 `particle_id == 13` is not chain membership

The obvious gate — "sum `segment_cal_kine_dQdx` over the cluster's pdg-13 rows"
— fails on 248 of 904 candidates, and **the chain is right every time**.
`T_rec_charge.particle_id` is the PR's own direction/PID verdict, written by
`determine_direction` long before the STM chain is chosen, and it marks far more
track than the chain contains. Measured on PDVD `039253_6` cluster 82: twelve
pdg-13 segments totalling **723.4 cm** against a `muon_len` of **418.6 cm**.

Worse, **the chain's segment list is not in the output at all**.
`n_chain_segs` gives the count; role-1 points are the resampled *profile* and
`add_points` stamps every one of them with `chain.back()`'s id
(`CheckSTM_Michel.cxx:671`). So for a multi-segment chain nothing downstream can
say which segments the muon is made of — which is why L2a can only be exact
where `n_chain_segs == 1`. §8 names the one-line fix.

### 6.2 A gapped profile is not cross-checkable by trapezoid

The job runs `profile_min_dqdx_frac = 0.15`, which *deletes* profile points in
dead cells. The nominal step is ~0.6 cm, but the survivors can be 30 cm apart,
and a trapezoid across such a gap multiplies one point's dQ/dx by tens of cm:
ratios of 1.60 and 1.63 on PDHD `028084_30`/107 and `029107_18`/54 (30.7 and
27.3 cm steps) and 0.43 on PDVD `039349_30`/44. That is the check's artefact,
not the chain's, so a profile whose largest step exceeds 3× its median is
**counted as skipped** — 311 of 904 — rather than absorbed by a wider window.

### 6.3 A dot with no valid fit is counted but invisible

`add_points` skips every fit with `dx <= 0` (`:683`), so a dot segment whose
fits *all* have `dx == 0` increments `n_dots`, is named by `michel_seg_id`, and
leaves **no role-4 point at all** — so it cannot be drawn. Seen once in 263
links: PDHD `029107_20` cluster 136, segment 135010, two fits, both `dx == 0`.
It also contributes exactly 0 MeV, because `segment_cal_kine_dQdx` skips the
same points. Reported, not fixed — it is a pre-existing behaviour of
`add_points`, not something this round introduced.

## 7. Limits

- `muon_ke_dqdx` runs over the chain's fitted segments only. Charge the fit
  never covered is not in it; `chain_coverage` is the branch that says how much
  that is.
- The MIP-equivalent conversion needed to put MeV on `dots_charge_unfit` is
  **not** applied anywhere. Without a `dx` there is no recombination correction
  to make, only one to assume, and the SBND EM campaign measured an 0.84–0.86
  charge-scale fudge on showers (doc pr/126) — the size of the systematic. The
  branch stays in electrons.
- The 20 % range-vs-dQ/dx gap on `039252_15 / 77` is reported, not explained.
  It is worth a round of its own on a clean stopping-muon sample.
- `muon_ke_dqdx` is only independently verifiable where the chain is one
  segment (§6.1). On the other 613 candidates the gate is the profile
  cross-check, which is a few-per-cent-level statement, not a bit-level one.

## 8. Next

1. **Name the chain's segments** (§6.1). `StmMichelProfile` already carries
   `seg_idx` — the index into the chain vector, per profile point
   (`StmMichelFunctions.h:72`) — and `add_points` throws it away in favour of a
   constant. Stamping the true id would make the muon's composition readable
   downstream and make L2a exact on every candidate instead of 291 of 904. It
   changes an existing column's *values*, so it wants its own round and a look
   at doc pdhd/12 §5.7 and the doc-13 census, which both join on `role`.
2. `michel_conn_type == 2` still has no persisted parentage. The honest fix is
   not a fake edge but a distance: a `michel_dot_dis_cm` branch would at least
   record *why* the dots were admitted.
3. The muon 4-momentum's **direction** is still dropped — only the energy is
   kept here. `segment_cal_4mom` already computes it.
4. The 6.3 dot-with-no-valid-fit case: either exclude it from `n_dots` or give
   it a point, but it should not be counted and invisible.
5. Doc pdhd/13 §8's knobs (`companion_max_len_cm`, the anisotropic dot window,
   `michel_any`) are unchanged and still the fix for the loss this display now
   makes visible.

## See also

- `pdhd/docs/13_michel-detached-loss.md` — why `039252_15 / 77`'s Michel was
  lost, and why `michel_seg_id` is −1 on it.
- `pdhd/docs/12_stm-michel-handscan-display.md` — the display this extends.
- `pdvd/docs/nf_sp_img_clus/48_check-stm-michel-chain.md` — the module.
