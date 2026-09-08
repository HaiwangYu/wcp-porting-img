# doc pdhd/13 — why `CheckSTM_Michel` loses a Michel that is plainly there

**Scope: no code is changed in this round.** This is a diagnosis plus a
committed census script and one change to the hand-scan display. The C++ fix is
specified in §8 and held for a separate default-OFF round.

## Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
python3 pdhd/docs/scripts/d13_michel_loss_census.py 'pdhd/work/*_d51hnu' \
    --det pdhd --out /home/xqian/tmp/d13/d13h
python3 pdhd/docs/scripts/d13_michel_loss_census.py 'pdvd/work/*_d51vnu' \
    --det pdvd --out /home/xqian/tmp/d13/d13v \
    --connect-item 039252_15_d51vnu:77
```

Writes `<out>_candidates.tsv`, `<out>_neighbours.tsv`, `<out>_summary.txt`.

**Provenance.** Arms `pdhd/work/*_d51hnu` (61 events, 302 STM candidates) and
`pdvd/work/*_d51vnu` (120 events, 568 candidates), both the production-defaults
`-nu` arm with no `PR_TLA` (doc pdvd/50 §16). Binary pin:
`local/lib/libWireCellClus.so` md5 `ec5d0133948913343d21776e6e734e65`, built
2026-09-07 14:37 — i.e. the tree at **818c47fb**, *before* c0b1613b (14:52);
the arms were written 15:39. Reference case: PDVD run 39252 event 15
(`evt298777`), cluster 77.

---

## 1. The question

Hand-scanning `039252_15 / 77` (188 fit points) in the doc pdhd/12 display, the
owner saw a Michel electron near the muon's end and, alongside it, what looked
like an over-clustered track. `CheckSTM_Michel` reported neither: only the muon.
The suspicion was a forgotten pattern-recognition step.

The answer is that no step is missing from the chain (§7). The Michel was
dropped by a single length cut before any pattern recognition ran on it (§3),
and the "over-clustered track" belongs to a different Q-L bundle (§4).

**A note on the word "detached".** In this case the Michel is *attached* in the
raw charge — contiguous with the muon in all three 2-D views, and the owner's
hand label says `michel_kind: attached`. "Detached" throughout this doc means
detached **in the reconstruction**, i.e. the 3-D clustering put it in a separate
cluster. That split is itself the upstream defect of §9, and the two senses of
the word must not be conflated when this scan is scored. (`michel_conn_type`
carries the reconstruction's sense; the scanner's `michel_kind` carries the
image's. `score_stm_michel_scan.py` reads neither, so nothing is mis-scored
today — but a future scorer must not simply map one onto the other.)

## 2. What is actually there

`T_stm_michel` for cluster 77: `is_stm=1`, `reject_bits=0` — a clean STM
verdict — `muon_len` 112.5 cm, `n_profile_pts` 188, `stop_dis` 0.36 cm, and

```
michel_found 0   n_stop_arms 0   n_dots 0   n_dot_clusters_unfit 0   n_chain_segs 1
```

Measured (`d13_michel_loss_census.py`, and the per-item checks below):

1. **Cluster 77 is not over-clustered.** All 718 of its point-cloud points lie
   within **2.26 cm** of its own 188-point fit; 99.7 % within 2 cm. Nothing
   foreign is inside it. (`cloud_fit_resid_cm` in `_candidates.tsv`.)

2. **The Michel is cluster 265** — a separate live cluster: 116 points,
   **20.1 cm** long, `is_associated=1`, in **the same Q-L bundle as the muon**
   (flash 298, `cluster_t0_us` 6199.677, identical to cluster 77's). Its
   closest point is **1.91 cm** from the fitted stop, and it lies entirely
   *beyond* the stop along the muon direction (arc coordinate 1.55 → 9.16 cm).

3. **The fit is not amputated.** Contrary to the doc pdvd/32 failure mode, the
   trajectory reaches its own cluster's last point to within **1.20 cm** (9 of
   718 points lie beyond it), and `stop_extend_max=3` is enabled on this arm but
   did not fire (`n_ext=0`). The 1.91 cm is a real gap between two clusters, not
   a short fit.

4. **It is visible in the 2-D measurement, exactly as the owner reported.** In
   cluster 77's own `T_proj_data`, the cells near the stop carry measured charge
   with essentially no predicted charge: **9.75×10⁴ e (U), 1.70×10⁵ e (V),
   1.66×10⁵ e (W)** — between 44 % and 61 % of all the measured-but-unpredicted
   charge in each plane's entire projection. The Michel is the dominant thing
   the fit fails to model in this cluster.

5. **In 2-D it is attached, with no gap at all.** Per plane, 8-connectivity over
   live `T_proj_data` cells puts the muon's modelled cells and the unpredicted
   near-stop cells in the **same connected component in all three planes**, with
   a Chebyshev cell gap of **0**:

   | plane | live cells | components | shares a component with the muon | cell gap |
   |---|---|---|---|---|
   | U | 393 | 1 | yes | 0 |
   | V | 753 | 7 | yes | 0 |
   | W | 759 | 8 | yes | 0 |

   The 1.91 cm separation exists **only in the 3-D cloud**. See §9.

## 3. Why it was lost — one line

**Symptom.** A 20.1 cm Michel, in the muon's own Q-L bundle, 1.91 cm from the
stop, reported as `michel_found=0` with `n_stop_arms=0`, `n_dots=0` and
`n_dot_clusters_unfit=0` — i.e. not merely rejected but never seen.

**Root cause.** `clus/src/CheckSTM_Michel.cxx:812`, in the companion selection:

```cpp
for (auto* oc : grouping.children()) {
    if (oc == main) continue;
    if (oc->get_scalar<int>("matched_flash_gid", -1) != rec.gid) continue;   // :811
    if (oc->get_length() > m_dot_max_len_cm * units::cm) continue;           // :812  <-- 10 cm
    if (oc->npoints() == 0) continue;                                        // :813
    const auto [cp, blob] = oc->get_closest_point_blob(rec.stop_pt);
    if ((cp - rec.stop_pt).magnitude() > m_michel_dot_radius_cm * units::cm) continue;  // :815
    companions.push_back(oc);
}
```

Cluster 265 passes `:811` (same gid) and `:815` (1.91 cm ≪ 15 cm) and fails
**only** `:812`, because 20.1 cm > `dot_max_len_cm` = 10 cm. It is therefore
never added to `companions`, never preloaded into the fitter (`:834`), and never
given `find_proto_vertex` (`:856-859`). Since it contributes no segment to the
graph, it can become neither an attached arm at the stop vertex (`:1132-1139`,
which walks the stop vertex's out-edges) nor a detached dot (`:1201`, which
iterates `companions`). **The same 10 cm constant is applied a second time per
segment at `:1215`, so raising it at one site alone does not open the path.**

**Why it hid.** No log line is emitted for a cluster rejected at `:812` — the
per-candidate summary reports `dots 0 ... unfit 0`, which is
indistinguishable from "there was nothing there". `n_dot_clusters_unfit`
(`:1206`) counts only companions that were *admitted* and then failed to fit,
so it cannot see this case either.

**Compiled-config proof.** The 10 cm is the C++ default (`:328`), not a job
setting: the `stm_michel_knobs` bag in `pdvd/wct-pr-perevt.jsonnet:224-236`
(and PDHD `:236-248`) sets nine keys — `profile_min_dqdx_frac`, `pid_mode`,
`plateau_mip_lo/hi`, `stop_extend_max`, `michel_guards_stop`,
`michel_shower_min_kink_deg`, `stop_fv_use_config_tolerance`,
`dead_volume_check` — and **none of `dot_max_len_cm`, `michel_dot_radius_cm`,
`dot_body_exclusion_cm`**. The defaults 10 / 15 / 5 cm are what ran.

**Fix.** §8. Not applied in this round.

**Verification.** `d13_michel_loss_census.py --det pdvd` lists
`039252_15_d51vnu cl 77 is_stm 1 n_stop_arms 0 n_dots 0` as one of six
candidates whose only same-bundle neighbour near the stop is over the cap.

## 4. The "over-clustered track" is a different bundle — a display artifact

The second object the owner saw is **cluster 103**: 3395 points, 434 cm, and it
belongs to a **different Q-L bundle** — flash 134, `cluster_t0_us` 2542.38,
against the muon's flash 298 at 6199.68. That is Δt0 = 3657.3 µs, i.e.
**541 cm of drift** at PDVD's 1.48073 mm/µs.

The Bee `clustering-global` layer, which the display draws, places every cluster
at its *own* bundle's t0-corrected position. Two cosmics separated by 541 cm of
drift time therefore land 5.6 cm apart on screen. Cluster 77 is not
over-clustered with anything; the display simply cannot show which charge shares
the muon's bundle.

**Acted on in this round.** The owner asked that the 3-D and 2-D projection
views be restricted to the matched Q-L bundle. `T_cluster` already carries
`flash_id`, `cluster_t0_us`, `is_main` and `is_associated`, so the bundle is
computable in the prep with no new production output. See §10.

## 5. Three general defects

Measured over both arms — 302 PDHD and 568 PDVD STM candidates
(`has_pass==1`, `n_profile_pts ≥ 20`, `muon_len ≥ 10 cm`, the doc pdhd/12
sample).

### D1 — `michel_found` never reports a detached Michel

`rec.michel_found = 1` is assigned at **exactly one place**, `:1169`, inside the
attached-arm block. The detached-dot path (`:1201-1246`) sets `n_dots`,
`dots_ke_dqdx` and `michel_conn_type = 2` but never touches `michel_found`.

| | `michel_found==1` | `n_dots>0 & michel_found==0` | share of all reconstructed Michels |
|---|---|---|---|
| PDHD | 69 | **33** | **0.324** |
| PDVD | 115 | **41** | **0.263** |

`michel_conn_type==2` matches the second column exactly on both detectors
(33 and 41), which is the internal consistency check.

Consequences: the per-event summary line
(`"{} candidate(s), {} pass every check, {} with a Michel"`, `:1301`) undercounts
by the same fraction, and **doc pdhd/12's S1–S4 stratification, which keys on
`michel_found`, mis-labelled ~30 % of the scan sample** — items with a
reconstructed detached Michel were drawn as "no Michel".

Two readings, per CLAUDE.md §5.4:

- **(a) it is a bug.** `michel_conn_type` exists precisely to encode
  1 = attached / 2 = detached, so `michel_found` was meant to mean "a Michel was
  reconstructed" and the dot path forgot to set it.
- **(b) it is the intended contract.** `michel_found` means *attached*, and
  consumers are meant to write `michel_found || n_dots > 0`.

**Recommendation: neither branch should change `michel_found`'s meaning
silently.** Add a separate `michel_any` branch (= `michel_found || n_dots>0`),
fix the summary log line, and leave `michel_found` as it is so every existing
scan, TSV and scorer keeps its meaning. Reading (b) then becomes explicit rather
than implicit, and no committed record is retroactively re-interpreted.

### D2 — one knob gates two different decisions

`dot_max_len_cm` gates both

- **admission** — whether a cluster enters the PR at all (`:812`), and
- **classification** — whether a fitted segment counts as a dot (`:1215`).

They are different questions. Admission should be generous (a 20 cm Michel is
still a Michel); the dot cut is a shape statement about small detached blobs.
Because one constant serves both, opening admission necessarily loosens what
counts as a dot.

Candidates with `michel_found==0` whose only same-bundle neighbour within 15 cm
of the stop is **over** the cap — dropped before any PR ran on them:
**5 (PDHD, 0 of them `is_stm`) and 6 (PDVD, 2 of them `is_stm`)**. Rare, but
unrecoverable by tuning: `039252_15/77` and `039349_58/72` are both clean
`is_stm=1` stopping muons.

### D3 — the dominant failure is classification, not admission

On the `is_stm==1 & michel_found==0` set, compare `T_rec_charge` points for the
main cluster (every fitted segment, keyed `sub_cluster_id // 1000`) against
`T_stm_michel_pts` (roles 1–4 only). An excess means the PR *did* fit segments
that the arm classifier then discarded — arms classified `kOther` or
`kContinuation` add no points.

| | n | fitted-but-unroled > 0 | p50 | p90 | max |
|---|---|---|---|---|---|
| PDHD | 42 | **32 (0.762)** | 13 | 80 | 479 |
| PDVD | 94 | **68 (0.723)** | 1 | 28 | 376 |

Role 4 is excluded from the `T_stm_michel_pts` side on purpose: a dot's points
come from a **companion** cluster, so they sit in `T_rec_charge` under the
companion's own id, not the candidate's. Counting them would credit the
candidate with points its own cluster never had and deflate the excess by
exactly `n_dots` — which, since 33/41 of the candidates in this very population
have `n_dots>0` (D1), is not a small effect.

Restricted further to `n_dots==0` — the genuinely empty set:

| | n | `n_stop_arms==0` | `n_stop_arms>0` |
|---|---|---|---|
| PDHD | 34 | 24 (0.706) | 10 (0.294) |
| PDVD | 84 | 77 (0.917) | 7 (0.083) |

So the loss splits into "the graph has no arm at the stop at all" (the majority,
and cluster 77's case) and "an arm existed and `stm_michel_classify_stop_arm`
rejected it". These need different fixes and should not be conflated.

A large part of the remainder is expected physics, not defect: µ⁻ capture in
argon means a substantial fraction of stopping cosmic muons produce no Michel.
This doc does not attempt to separate that; doing so needs the hand scan.

## 6. The muon lifetime — real physics, but not the cause of this gap

The muon lifetime *does* displace a Michel, and only ever in one direction: the
decay happens after the muon stops, so the Michel's charge arrives later and is
reconstructed farther from the anode. The scale, however, is small:

| | v_drift | τ(µ⁺)=2.197 µs | 1 slice (4 ticks) |
|---|---|---|---|
| PDVD | 1.48073 mm/µs | **0.325 cm** | 0.296 cm |
| PDHD | 1.576 mm/µs | **0.346 cm** | 0.315 cm |

One lifetime is about **one time slice**, at or below the imaging resolution.
For µ⁻ in argon τ ≈ 0.6 µs and nuclear capture dominates, so the displacement is
smaller still.

Cluster 265's offset from the stop is 1.55 cm along drift and 1.12 cm
transverse. As a delay that would be **10.5 µs ≈ 4.8 τ** (p ≈ 0.9 % for µ⁺) —
an order of magnitude beyond what the lifetime supplies, and the transverse
component has no time interpretation at all. **The lifetime did not open this
gap.**

**Null control.** The same delay-signed drift offset measured at the **entry**
point, where no delayed emission exists, is the floor a stop-only number must
beat. The drift sign is taken per candidate from `dx/d(time_slice)` on its own
fit, so nothing assumes an anode side (PDVD is cathode-centred; `sign(x)` is not
drift distance).

| | stop, delay-side fraction | entry (null) | stop − entry |
|---|---|---|---|
| PDHD | 0.458 (n=24) | 0.261 (n=23) | +0.197 |
| PDVD | 0.537 (n=41) | 0.318 (n=22) | +0.218 |

The stop shows **no** delay-side asymmetry — both detectors sit at ~0.5. The
apparent +0.20 "excess" is carried entirely by the entry control being
*early*-biased, which is geometry: the entry sits on a detector boundary, so
nearby companions are preferentially on one side. **There is no measurable
delayed-emission signature in this sample**, and there should not be: a 0.3 cm
mean displacement cannot be resolved at this pitch.

**The design consequence survives on principle, not on this measurement.** A
Michel can only ever appear later than the muon, so a *delay-only,
drift-anisotropic* admission window is free background rejection — a delta ray,
a foreign fragment or a co-located cosmic has no such asymmetry. But its size
must be set by imaging resolution plus a measured clustering-gap distribution,
**never by τ**, which would give ~1 slice and admit nothing.

## 7. Was a pattern-recognition step forgotten? No

- The PDHD and PDVD `-nu` pipelines are **character-for-character identical**
  (13 stages: `switch_scope, flag_mains, unmerge_assoc, steiner, fiducialutils,
  tagger_check_tgm, tagger_check_stm, tagger_check_fc, protect_bundle,
  steiner_refresh, check_stm_michel, tracking_visitor, pr_display`;
  `pdvd/run_pr_evt.sh:130`, `pdhd/run_pr_evt.sh:129`).
- Track/shower separation **is** run. `CheckSTM_Michel` calls the same four PR
  stages `TaggerCheckNeutrino` does — `find_proto_vertex`, `clustering_points`,
  `separate_track_shower`, `determine_direction` — on the main cluster
  (`:844-849`) **and on every companion** (`:853-866`), plus `examine_direction`
  (`:893`). The companions simply never included cluster 265.
- What is genuinely absent, **by design**, is the rest of the
  `TaggerCheckNeutrino` tail: `deghosting` (`:3203`),
  `determine_overall_main_vertex_DL` / `determine_overall_main_vertex`
  (`:3216`, `:3238`), `improve_vertex` (`:3301`), the five neutrino taggers, and
  — the one that matters here — **`shower_clustering_with_nv` (`:3425`)**, the
  event-level shower clustering whose job is to gather detached EM activity
  around a vertex. `CheckSTM_Michel.cxx:1-3` describes itself as "a light
  replacement for the neutrino PR tail (TaggerCheckNeutrino) on a cosmic
  detector".

So the owner's instinct points at a real hole, but it is an omitted *capability*,
not a runner mistake: the component has no event-level EM gathering, and its
substitute — the companion list — is capped at 10 cm.

`ClusteringExamineBundles` is also commented out on both detectors
(PDVD `clus.jsonnet:579`, PDHD `:556`) with a written justification; it is not
implicated here.

## 8. What to change — next round, default-OFF

Behaviour changes, so each ships as a knob defaulting to today's value with a
byte-identical A/B on both detectors (CLAUDE.md §1, §4). Not applied here.

| knob | default | effect | how its value gets set |
|---|---|---|---|
| `companion_max_len_cm` | `-1` ⇒ use `dot_max_len_cm` | splits admission (`:812`) from the dot cut (`:1215`), fixing D2 without loosening what a dot is | the length distribution of same-bundle neighbours near a stop, `_neighbours.tsv` |
| `michel_dot_radius_drift_cm` | `-1` ⇒ isotropic | drift/transverse anisotropy on `:815` and `:1214` | the measured clustering-gap distribution, decomposed drift vs transverse |
| `michel_dot_delay_only` | `false` | admit a companion only on the later-time side of the stop | §6: principled, and its purity gain is measurable against the entry null |
| `michel_any` branch | — | D1, without redefining `michel_found` | none — a bookkeeping addition |
| a log line at `:812` | — | name the cluster and its length when a same-bundle neighbour is rejected | none |

Grading: the doc pdhd/12 hand scan is the instrument. Because D1 mis-stratified
that sample (§5), the strata should be recomputed on `michel_found || n_dots>0`
before the scan is used to grade any of this.

## 9. Open question — the 3-D clustering split a 2-D-contiguous Michel

The Michel is contiguous with the muon in **all three** 2-D views with a 0-cell
gap (§2.5), the Q-L matching already put both clusters in one bundle
(`is_associated=1`, identical `flash_id` and `cluster_t0_us`), and yet the 3-D
clustering produced two clusters 1.91 cm apart. There are no dead channels
involved (`n_dead_pts=0`, `dead_ahead=0`).

That is a defect upstream of `CheckSTM_Michel`, and this round does not diagnose
it — naming a cause without tracing the data would be a guess. What is recorded
is the evidence and the reproducer (`--connect-item 039252_15_d51vnu:77`). It
deserves its own round, starting from the blob tiling and the live-cluster
connectivity in the stop region, because a fix there would make the Michel
*attached* and remove the need for any companion search in this case.

## 10. The display change made in this round

`pdhd/stm_michel_scan/` gains a **`bundle only`** control (default **on**): the
prep records, per item, the set of cluster ids sharing the muon's
`(flash_id, cluster_t0_us)`, and the viewer restricts the near/far image-charge
layers and the three 2-D projections to those ids, colouring out-of-bundle
charge distinctly when the control is off.

**The 2-D measurement panels are deliberately NOT filtered.** `T_proj_data`
cells carry no cluster attribution (§11 limit 5), and more importantly they
must not be: those panels show every electron the wires measured against what
the fit predicts, and that is precisely where an unreconstructed Michel appears
— it is how this one was found (§2.4). Filtering them would hide the evidence
the panel exists to show. This is the
scan instrument, not production, so it carries no knob gate; the self-test's
causal control is that cluster 103's 429 points within 20 cm of the
`039252_15/77` stop disappear when the control is on, while cluster 265's remain.

## 11. Limits

1. `is_stm` is `reject_bits == 0`, a verdict, not truth. Every rate here is
   against the chain's own verdict, not against a hand label.
2. The bundle key is `(flash_id, cluster_t0_us)`. A flash alone is not a unique
   bundle key; both fields are required and the t0 must match exactly.
3. The delayed-emission test has n = 22–41 per anchor. It is powered to exclude
   a large asymmetry, not to measure a small one.
4. §5's `no Michel` remainder mixes genuine µ⁻ capture with reconstruction
   failure; separating them needs the hand scan, not this census.
5. The 2-D connectivity test uses `T_proj_data`, which spans the bounding box of
   the main plus associated clusters — that is precisely why the Michel's cells
   are in it, and why the test can be run at all, but it also means the test
   cannot by itself attribute a cell to a cluster.
6. Two unrelated config issues were found and **flagged, not fixed**:
   `pdvd/wct-pr-perevt.jsonnet:207`'s default `pipeline_names` omits
   `unmerge_assoc` and its comment contradicts `run_pr_evt.sh:132-133` (harmless
   while every arm goes through the runner, which overrides it); and
   `nu_per_bundle_stm_only=true` (`:1629`) gates `TaggerCheckNeutrino`, which
   doc pdvd/48 removed from `PIPE_NU`, so it is now inert on `-nu`.

## 12. Recommended next step

Recompute doc pdhd/12's strata on `michel_found || n_dots>0` and re-prep the
scan sheet, then scan the `is_stm==1 & no Michel` set — 42 PDHD and 94 PDVD
items — with the bundle-restricted display. That measures the one number none of
this census can: how many of them really have a Michel. It is also the sample
that sets every knob value in §8.

**Follow-up, doc pdhd/14 (2026-09-07).** `CheckSTM_Michel` now persists the muon
kinematics it previously computed and dropped (`muon_ke_range/_dqdx/_best`) and
the daughter's id (`michel_seg_id`), so the loss described above is now visible
in one field: on `039252_15 / 77` the chain reports a 278.0 MeV muon and
`michel_seg_id = -1`. That doc also settles the particle-flow question — the
only `mu -> e` parentage the chain writes is the vertex shared by the muon's end
and an *attached* arm, so the detached population of D1 has no persisted link at
all.

**Follow-up, doc pdhd/15 (2026-09-07).** Defects **D1** and **D2** are fixed.
D2: companion **admission** now has its own knob (`companion_max_len_cm`, C++
default 25 cm = `michel_max_len_cm`) separate from the per-piece cap, so
`039252_15 / 77`'s 20.1 cm Michel enters the PR and is reconstructed — 51.6 MeV,
`michel_conn_type 2`, gap 0.38 cm. D1: `michel_found` now means "a Michel object
exists", detached included (PDVD 115 → 158). That doc also **corrects this one's
premise about the particle flow**: `mc.json` *is* written on this path, and a
detached Michel *is* linked there, through a pseudo-gamma carrier node. What was
missing was a link in `T_stm_michel`, now `michel_parent_vtx_id` /
`michel_dis_cm` / `michel_start_*`. D3 (segments fitted and then discarded by
the arm classifier) is untouched and remains open.
