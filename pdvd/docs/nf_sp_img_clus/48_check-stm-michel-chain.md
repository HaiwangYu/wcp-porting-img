# 48 — `CheckSTM_Michel`: a stopping-muon + Michel reconstruction stage replaces the neutrino PR tail on PDVD

**Status (2026-09-05).** Shipped. New clustering visitor `CheckSTM_Michel`
(toolkit `clus/`), a `T_stm_michel` / `T_stm_michel_pts` pair in
`tracking-pr.root`, and the PDVD `-nu` chain now runs it in place of
`tagger_check_neutrino` + `tagger_output` (owner decision 2026-09-05: "Replace
the PR chain for PDVD with this new chain").  The runner's default mode stays
`-stm` (doc 39, owner 2026-09-04); the pre-replacement neutrino tail is kept
verbatim as `-nu-legacy`.  **Byte-identity:** the PDVD production chain
(`-stm`) compiles to the same JSON as before and its outputs hash identically
on ref vs new binaries; `-nu-legacy` reproduces the old `-nu` byte-for-byte;
PDHD (binds the same ROOT writer) and SBND (shares `libWireCellClus`) are
unchanged.  **No threshold has been tuned** — the verdict knobs sit at the
values documented in §3 and every input to them is persisted, so the owner
can retune from the output.  Gate record: `pdvd/stm/gates/d48_stm_michel_gate.txt`.

Doc number 48 because a peer holds 47 (the controlled-track sim study,
`scripts/d47_*`).

## 0. Repro

```bash
# toolkit (apply-pointcloud) + wcp-porting-img (main) at the commits named in sec 9.
wcbuild                    # rc must be 0; then the freshness proof (sec 7)
./build/clus/wcdoctest-clus -tc="*stm_michel*,*CheckSTM_Michel*" # 7 cases, 206 assertions
./build/root/wcdoctest-root

cd /home/xqian/toolkit-dev/toolkit/pdvd
# compiled-config proofs (T0/T1/T2, sec 7.1)
./scripts/stage_pr_tag.sh 39252 2 d48cfg d39r2prov
PDVD_PR_COMPILE_ONLY=1 PDVD_KEEP_CFG=1 ./run_pr_evt.sh -s d48cfg -stm -stm-fit 39252 2       # production
PDVD_PR_COMPILE_ONLY=1 PDVD_KEEP_CFG=1 ./run_pr_evt.sh -s d48cfg -nu-legacy -stm-fit 39252 2 # the old -nu
PDVD_PR_COMPILE_ONLY=1 PDVD_KEEP_CFG=1 ./run_pr_evt.sh -s d48cfg -nu -stm-fit 39252 2        # the new chain
# smoke (one event) and the 120-event arm
./scripts/stage_pr_tag.sh 39252 2 d48smoke2 d39r2prov
LD_LIBRARY_PATH=/home/xqian/tmp/d47_libpin/new2:$LD_LIBRARY_PATH ./run_pr_evt.sh -s d48smoke2 -nu -stm-fit 39252 2
ARM=d48nu PIN=new2 PINROOT=/home/xqian/tmp/d47_libpin MODE=nu JOBS=16 ./docs/nf_sp_img_clus/scripts/run_d45_arms.sh
python3 docs/nf_sp_img_clus/scripts/d48_stm_michel_census.py d48nu --tsv docs/nf_sp_img_clus/figs/48_stm_michel_d48nu.tsv
# gates: /home/xqian/tmp/d48_arms/launch_gates2.sh (copied into sec 7), then
python3 docs/nf_sp_img_clus/scripts/d40r3_hash_gate.py d48stmref2 d48stmnew2 /home/xqian/tmp/d48_events2.txt
```

Binary pins (`libWireCell*.so` + `WireCellRootDict_rdict.pcm` copied from `local/lib`):
`/home/xqian/tmp/d47_libpin/ref` = today's production binary before this
round (`libWireCellClus.so e3304cb9…`, `libWireCellRoot.so 1f46de9f…`);
`/home/xqian/tmp/d47_libpin/new2` = the shipped binary (`libWireCellClus.so
8d6a8388…`, `libWireCellRoot.so 4a9efb7f…`).  `new` (Clus `42f60d2f…`) is the
first cut, superseded by a units-only change in `persist()` (sec 5); no gate in
this doc cites it.

## 1. Why

The PDVD `-nu` tail ran the whole neutrino pattern recognition
(`TaggerCheckNeutrino`) on the STM-tagged bundles (doc 25 §13.10).  Two
problems, both measured before this round:

- **Cost.** `TaggerCheckNeutrino` was 73 % of the arm even after the
  STM-only gate (doc 25 §13.10); the 2026-09-05 doc-45 arms still spent
  minutes per event in the per-bundle neutrino PR.
- **Wrong question.** Its main vertex is a *neutrino* vertex.  On a cosmic
  bundle it lands on the entry end or a kink, never the stop (doc 25 §13.7:
  route 1 of the Michel search measured and failing — 16 flag-7 bundles, 7
  energies, two above the Michel endpoint).  The Michel finder it carries
  (`NeutrinoTaggerCosmic.cxx:788-1018`) is a neutrino-rejection feature whose
  `michel_energy` is never persisted.

What the owner asked for (2026-09-05): a dedicated stage that reconstructs
the **stopping muon** — entry point → body with delta rays → Bragg stop →
Michel electron (the wiggly track at the stop *and* nearby isolated "dots")
— reusing the general PR chain's pieces, writing `tracking-pr.root` and the
Bee particle flow **rooted at the STM entry point**, with a **reject flag**
for tagged clusters that are not real stopped muons (still reconstructed).

## 2. Design — what is reused, from where

The stage is one file, `clus/src/CheckSTM_Michel.cxx` (component
`CheckSTM_Michel`, factory + `IEnsembleVisitor`, the `TaggerCheckSTM.cxx:43`
skeleton), plus the graph-only logic in
`clus/inc/WireCellClus/StmMichelFunctions.h` / `clus/src/StmMichelFunctions.cxx`
so it can be doctested on synthetic graphs.

| step | what | reused from |
|---|---|---|
| anchor | `Flags::STM` main clusters (not TGM); the accepted pass (status 0) of the `stm_pass` PC; its `stm_fit` rows: **L = 0 row = entry**, **row `kink_num` = the tagger's stop** | `TaggerCheckSTM::persist_stm_fit` (`:936-1022`), `:1854` (`end_p = pts.at(kink_num)`), `:2141` (bounds) |
| companions | every cluster with the main's `matched_flash_gid` (the only clusters with a t0, hence a drift coordinate), within `michel_dot_radius_cm` of the stop and ≤ `dot_max_len_cm` long | `TaggerCheckSTM.cxx:575-587` idiom, widened past `associated_cluster` because PDVD's `flag_mains` makes every flash-matched cluster a main |
| fitter | one `TrackFitting` per candidate, parameters copied from the member fitter that `load_trackfitting_config` filled from `pdvd_track_fitting.json`; `fit_blob_coverage`, `dqdx_fit_keep_all_points`, `excl_t0_frame` applied the same way | `TaggerCheckNeutrino.cxx:2253-2267`, `:2777-2791` |
| graph | `PR::Graph` attached with `add_graph`; `preload_clusters(main + companions)` | `:2323-2324`, `:2301-2306` |
| partition | `PR::PatternAlgorithms` as a local object; `find_proto_vertex(…,true,2,true,pd)` → `clustering_points` → `separate_track_shower` → `determine_direction` on the main; the other-cluster branch (`>6 cm` / short + `init_point_segment` fallback) on the companions | `:2326`, `:2876-2893`, `:2927-2962` |
| partition knobs | the SAME config keys `TaggerCheckNeutrino` reads for those stages (`pattern_knob_keys()` in the source), same units, filtered out of the PDVD `tcn_knobs` bag in `protodunevd/pr.jsonnet` so the two stages cannot drift | `:2327-2530` |
| entry / stop vertices | `closest_cluster_vertex`; if farther than `stop_snap_tol_cm` the nearest segment is split there with `PR::break_segment` | `NeutrinoPatternBase.h:3241`; `PRSegmentFunctions.h:34` |
| orientation | `entry_v->set_flags(kNeutrinoVertex)` (what the Bee vertex paint and `PrDisplayDump` read), `set_main_vertex(entry_v)`, `examine_direction(g, entry_v, entry_v, …, flag_final=true)` — every reached segment oriented outward from the entry | `:3147`, `:3508`, `MultiAlgBlobClustering.cxx:1230` |
| muon chain | shortest route entry→stop over `segment_track_length` (hand Dijkstra on `sorted_out_edges`); fallback `find_cont_muon_segment(…, ignore_dqdx=true)` when no vertex sits near the tagger's stop | `PRTrajectoryView.h:154`; `NeutrinoPatternBase.h:3388` |
| dQ/dx vs rr | the chain's fits concatenated entry→stop (direction decided by which end touches the running vertex, never by `dirsign`); the STM tagger's KS recipe; `do_track_comp` forward and reversed | `TaggerCheckSTM.cxx:2780-2797`; `PRSegmentFunctions.cxx:2572-2661` |
| Michel | `PR::Shower(g)` seeded at the stop vertex (conn type 1), `complete_structure_with_start_segment` with the chain blocked, `calculate_kinematics`, `kine_best := kine_dQdx` | `PRShower.h`, `PRShower.cxx:813`, `:1589` |
| Michel/delta tests | inverted from the proton veto's own Michel/delta-ray discrimination and the Michel-stem guard | `TaggerCheckSTM.cxx:1862-1916`; `NeutrinoPatternBase.cxx:556-652` |
| publication | `assemble_fitted_charge_2d()`; unnamed slot = candidate 0; `"nu<i>"` per candidate | `:3580-3590` |

Copied rather than called (file-local in their homes): `seg_is_shower`
(`NeutrinoTaggerCosmic.cxx:76-80`) and `load_trackfitting_config`
(`TaggerCheckSTM.cxx:1024-1070`).

Because publication is identical to `TaggerCheckNeutrino`'s, **every existing
consumer renders this stage's output unchanged**: the Bee `track_fit` /
`shower_track` / `vertices` layers and the `mc` particle-flow tree
(`MultiAlgBlobClustering.cxx:968-1000`, `:1315-1360`; the PF tree BFS starts
at `get_main_vertex()` = the entry, so the flow is muon → deltas → Michel),
`PrDisplayDump` (`calib-pr-evt*.json`; tagger/kine info default-constructed,
which it tolerates), and `PdvdPrMagnifyTrackingVisitor` (`T_rec_charge` per
slot, `particle_id` from the `ParticleInfo` this stage sets: 13 on the chain,
11 on deltas / Michel / dots).  Only the visitor *name* in the Bee config
changes (`pr_visitor` in `protodunevd/pr.jsonnet`).

### 2.1 Per-candidate sequence

1. `reset_for_new_event()`; candidates = `main_cluster && STM && !TGM`,
   ident order, capped at `max_candidates` (8).
2. Anchor from the tagger PCs.  No accepted pass ⇒ `R_NO_CHAIN`, verdict row
   only.
3. Fitter + graph + `PatternAlgorithms`; the four stages on the main and on
   the selected companions.
4. Entry and stop vertices (snap or split); `kNeutrinoVertex` on the entry;
   `examine_direction` from it.
5. Chain; pdg 13 + shower flags cleared on chain segments; profile.
6. Bragg contrast, KS shape, `do_track_comp` (fwd/bwd).
7. Interior chain vertices: arms → delta (pdg 11) / hadron (`R_VERTEX_HADRON`) / other.
   Stop vertex: arms → Michel / continuation (`R_CONTINUATION`) / other.
8. Michel shower (longest Michel arm seeds, flood-fill absorbs the rest); dots
   from companion segments within the radius and closer to the stop than to the
   muon body beyond its last `dot_body_exclusion_cm`; a dot with no Michel seeds
   a conn-type-2 shower.  Unfitted companion clusters counted with their blob
   charge.
9. Stop containment (`FiducialUtils::inside_fiducial_volume`, inset by
   `stop_fv_margin_cm`).
10. Publish; persist the `stm_michel` (1 row) and `stm_michel_pts` PCs.

## 3. The reject verdict

`reject_bits` (int, `T_stm_michel`); `is_stm = (reject_bits == 0)`.  Michel
presence is **not** a criterion (μ⁻ capture in argon).

| bit | name | fires when | knob (default) |
|---|---|---|---|
| 1 | `no_chain` | no accepted `stm_pass`, or no entry vertex, or no route | — |
| 2 | `stop_unmatched` | no graph vertex within `stop_snap_tol_cm` of the tagger's stop and the split refused; chain walked greedily | `stop_snap_tol_cm` (2.0) |
| 4 | `no_bragg` | `contrast < bragg_contrast_min × expected`, or windows too thin (`bragg_valid = 0`) | `bragg_contrast_min` (0.6), tail `[0.5, 3]` cm, plateau `[20, 40]` cm (halved with `short_track` when the chain is shorter than 40 cm) |
| 8 | `shape_flat` | `ks_mu + ks_margin ≥ ks_flat` (the tagger's own shape test, `kslike_compare` vs the muon table and vs a flat `mip_dqdx`, over the last `compare_range_cm`) | `ks_margin` (0), `compare_range_cm` (35) |
| 16 | `not_muon_pid` | `do_track_comp` forward: gate ≠ 1, or the proton or electron score beats the muon score | `mip_dqdx` (PDVD 55000 e/cm) |
| 32 | `continuation` | a stop arm that is not shower-like, `kink < 15°`, `> 10 cm`, `0.7–1.3 MIP` — the muon did not stop here | `continuation_*` |
| 64 | `stop_near_boundary` | stop outside the fiducial inset by the margin | `stop_fv_margin_cm` (5) |
| 128 | `vertex_hadron` | an interior arm longer than `delta_max_len_cm` at `> 1.4 MIP` | `delta_max_len_cm` (8), `vertex_hadron_mip` (1.4) |
| 256 | `short` | fewer than `min_chain_points` profile points | `min_chain_points` (10) |

`contrast_expected` is the same two-window ratio evaluated on the muon
dE/dx table at the profile's own residual ranges (PDVD table: ≈ 1.7–2.1 on
the smoke event, depending on how many points fall in each window), so the
0.6 bar asks for 60 % of the tabulated rise.  Doc 25 §13.6 measured that on
PDVD most tagger stops are flat (median contrast 1.00) — that is exactly
what bits 4/8/16 are meant to catch.

Michel arm (stop vertex): `len + far_len ≤ michel_max_len_cm` (25),
`mip > michel_mip_lo` (0.3), and (shower-like OR `mip < michel_mip_hi` (1.3)
OR `kink ≥ michel_min_kink_deg` (30)).  Delta (interior vertex): `len ≤ 8 cm`,
far subtree ≤ 8 cm, terminal.  Dots: `michel_dot_radius_cm` (15),
`dot_max_len_cm` (10), `dot_body_exclusion_cm` (5).

All of these are config keys of `CheckSTM_Michel`
(`default_configuration()`; doctest `doctest_check_stm_michel_defaults.cxx`
pins them) and reach the PDVD job through the `stm_michel_knobs` TLA:
`PDVD_PR_TLA="-S 'stm_michel_knobs={\"bragg_contrast_min\":0.5}'"`.

## 4. What the Michel search can and cannot see

- **Only the bundle.** A cluster with no matched flash has no t0 and no drift
  coordinate; `CreateSteinerGraph` builds graphs for in-window mains and their
  same-gid companions (`CreateSteinerGraph.cxx:205-235`).  So "dots" are
  same-gid clusters near the stop.  A brem photon blob that did not match
  the muon's flash is invisible to this stage — stated limitation.
- **The stop is the tagger's stop.** Doc 25 §13.6 / doc 42 §4.4 established
  that on PDVD the fit's own residual past the kink is collinear muon
  continuation at 0.88 MIP in most cases, not a Michel.  Hence the
  `continuation` bit and the kink requirement: a Michel is a *turn*, a
  continuation is not.
- **Energy.** `michel_ke_dqdx` is `Shower::calculate_kinematics`'s dQ/dx
  energy over the Michel members (`kine_best` is set to it; range energy is
  meaningless for an electron); `dots_ke_dqdx` is the sum over the fitted dot
  segments; `dots_charge_unfit` the raw blob charge of companion clusters the
  partition produced no segment for.  No recombination or dead-region
  correction beyond what the fitter already does.

## 5. Outputs

**`tracking-pr.root`** (`PdvdPrMagnifyTrackingVisitor`, unchanged trees +):

- `T_stm_michel` — one entry per candidate: `cluster_id gid t0_us is_stm
  reject_bits has_pass pass kink_num entry_{x,y,z} stop_{x,y,z}
  tagger_stop_{x,y,z} entry_vtx_id stop_vtx_id stop_dis n_chain_segs
  n_profile_pts muon_len n_delta n_body_other n_body_hadron delta_len ks_mu
  ks_flat ratio_mu ratio_flat comp_fwd0..3 comp_bwd0..3 tail_med plateau_med
  contrast contrast_expected n_tail n_plateau short_track bragg_valid
  n_stop_arms michel_found n_michel_segs michel_conn_type michel_len michel_mip
  michel_kink_deg michel_far_len michel_ke_dqdx michel_ke_range michel_ke_best
  cont_len cont_angle_deg cont_mip n_dots n_dot_clusters_unfit dots_ke_dqdx
  dots_charge_unfit in_fv`.  **Units: cm, MeV, e/cm, degrees** (the PC
  carries human units; the generic PC→tree writer has no unit knowledge).
  `*_vtx_id = cluster_id*1000 + graph index`, the Bee `track_fit` convention.
- `T_stm_michel_pts` — `x y z q L rr role seg_id` per point: role 1 muon
  chain (with L, rr), 2 delta, 3 Michel, 4 dot (L = rr = −1); `q` in e/cm.
- `T_rec_charge` etc. as before, from the published slots.  `T_tagger` /
  `T_kine` are gone from the `-nu` file (they carried neutrino BDT features
  and would be all-defaults); `-nu-legacy` still writes them.

**`mabc-pr.zip`**: `track_fit`, `shower_track` (Michel/dots/deltas painted as
showers via pdg 11, muon as track), `vertices` (entry painted as the main
vertex), `mc` (PF tree rooted at the entry: mu- → e- leaves), plus the
unchanged `clustering` / `stm*` / `steiner*` layers.  A dedicated
`stm_michel_pts` Bee layer is **not** added in this round (it would need a
new pc branch in `MultiAlgBlobClustering::fill_bee_points_from_cluster`);
the roles are in `T_stm_michel_pts`.

**`calib-pr-evt*.json`**: `PrDisplayDump` unchanged (segments, showers, the
main vertex = entry; tagger/kine blocks are defaults).

## 6. Chain replacement

`pdvd/run_pr_evt.sh`:

```
-nu         switch_scope, flag_mains, unmerge_assoc, steiner, fiducialutils, tagger_check_tgm,
            tagger_check_stm, tagger_check_fc, protect_bundle, steiner_refresh,
            check_stm_michel, tracking_visitor, pr_display                      (+ stm_magnify with -stm-fit)
-nu-legacy  … steiner_refresh, tagger_check_neutrino, tracking_visitor, tagger_output, pr_display
-stm        (default, unchanged) … steiner_refresh, pr_display
```

`protect_bundle` + `steiner_refresh` stay: the prototype-faithful
overclustering split (`ClusteringProtectBundle.cxx:32-60`) splits bridged
fragments off the STM cluster and costs ms under `protect_stm_only_bundles`
(doc 25 §13.11).  `tagger_output` is dropped (neutrino BDT trees only).

`pdvd/wct-pr-perevt.jsonnet`: `pipeline_names` default swapped the same way;
new TLA `stm_michel_knobs = {}`.  `cfg/pgrapher/experiment/protodunevd/pr.jsonnet`:
`cm_by_name.check_stm_michel` (after `tagger_check_stm`; the partition knobs
filtered from `tcn_knobs`, the `teb_*` / `kink_dqdx_hot_ratio` / mip scales
from the same `pr()` args as `tagger_check_neutrino`, the fiducial + margins
under `stm_consistent_fv`), `tagger_uses` widened, and the Bee `visitor` /
`require_pr_graph` gates now test `pr_visitor` / `pr_tail_on`.
`cfg/pgrapher/common/clus.jsonnet`: builder `check_stm_michel(...)`.  No other
experiment's config touched (`pdhd/`, `sbnd/`, `uboone/` untouched).

## 7. Gates

Record: `pdvd/stm/gates/d48_stm_michel_gate.txt`.  Pins: `ref` = the production
binary before this round (`libWireCellClus.so e3304cb9…`, `libWireCellRoot.so
1f46de9f…`); `new5` = the shipped binary (`libWireCellClus.so 1af4cbbf…`,
`libWireCellRoot.so 4a9efb7f…`).  Freshness: `local/lib/libWireCellClus.so`
20:50:20 > last source edit 20:49:52; `libWireCellRoot.so` 20:46:44 > 20:29:30.
Doctests: `wcdoctest-clus` 320 cases green (7 new), `wcdoctest-root` green.

### 7.1 Compiled-config proofs (`PDVD_PR_COMPILE_ONLY=1`, tag `d48cfg`)

| proof | what | result |
|---|---|---|
| T0 | production `-stm -stm-fit` compiled JSON, before vs after every jsonnet edit | `cmp` **IDENTICAL** (md5 `fbf5da9d…`) |
| T2 | `-nu-legacy` after vs the old `-nu` before | `cmp` **IDENTICAL** (md5 `8e801a26…`) |
| T1 | the new `-nu` | `CheckSTM_Michel:pr` ×5 (pipeline, 3 Bee layers, `bee_pf`); the node carries 49 keys incl. `mip_dqdx 55000`, `mip_dqdx_median 47000`, `excl_t0_frame true`, `fit_blob_coverage 0`, the curved fiducial + margins |

### 7.2 Byte-identity arms (reference arms round 2 on `ref`; new arms round 4 on `new5`; every job rc=0)

| gate | chain | arms | result |
|---|---|---|---|
| 2 | PDVD production `-stm -stm-fit`, 039252/2 + 039349/23 | `d48stmref2` vs `d48stmnew4` | `d40r3_hash_gate.py` PASS 2/2 (zip members + calib dump); `tracking-stm.root` 3 trees SAME ×2 |
| 3 | PDVD `-nu-legacy -stm-fit` (the old neutrino tail), same events | `d48legref2` vs `d48legnew4` | PASS 2/2; `tracking-pr.root` (T_kine, T_tagger, T_rec_charge) and `tracking-stm.root` trees SAME ×2 |
| 4 | PDHD `-nu -stm-fit`, 029107/0 (same `PdvdPrMagnifyTrackingVisitor` class) | `d48ref2` vs `d48new4` | zip 13 members SAME; both ROOT files' trees SAME |
| 5 | SBND bare production, 284349 / 285999 / 286065 | `work-stmcamp-d48gateold2` vs `-d48gatenew4` | `mabc-pr.zip` SAME 3/3, `pctree-pr-evt*.tar.gz` SAME 3/3 (425/427/425 members), `nusel-evt*.tsv` SAME 3/3 |

Rounds 2 and 3 (pins `new2`, `new4`) passed identically and are not cited;
round 1 is void — its launcher lost the mode flags (a `set --` inside the
function clobbered `"$@"`), so those arms ran the default chain and the tree
comparison was vacuous.  The gate 3 result also settles the one shared-file
change outside `clus/`: `PdvdPrMagnifyTrackingVisitor` writes its two new trees
only when a cluster carries the `stm_michel` PC, and without the stage the
file is unchanged on PDVD (gate 3) and PDHD (gate 4).

## 8. First look: the smoke event and the 120-event arm

### 8.0 Two bugs the first look caught (both fixed before the census arm)

- **A split vertex has no cluster.** `PR::break_segment` stamps the cluster on
  its two child segments but not on the vertex it creates.  A clusterless
  entry vertex made `examine_direction` return false silently and the PF
  builder's main-cluster test (`pf_track_main_cluster_only`, PDVD production)
  reject every seed: cluster 86 of the smoke event lost its mu- node and its
  Michel became a "ROOT shower (fallback: start_vtx not in BFS tree)"
  (`WCT_BEE_PF_PRINT=1`, arm `d48smoke3`).  Fix: the anchor stamps
  `vtx->cluster(&cluster)`.  Arm-wide (`d48nu` → `d48nu2`): PF roots whose
  first child is the muon 473 → 563 of 574, empty roots 73 → 0.  The entry also
  got its own, looser snap (`entry_snap_tol_cm` 5) so an existing end vertex
  beats a split that leaves a sub-cm stub.
- **A collinear MIP piece could be a "Michel".** The first arm's Michel kink
  distribution had its 10th percentile at 11° — doc 42 §4.4's collinear
  leftover, admitted through the low-dQ/dx clause.  The definition now requires
  a turn (or a shower flag) and treats any collinear MIP piece over 3 cm as
  continuation (§3).  Effect (`d48nu2` → `d48nu3`): Michels 152 → 137, kink p10
  11° → 16°.  This is a definition fix, not a threshold moved toward a number.

### 8.1 The smoke event (039252/2 = art 298595, 8 STM-tagged clusters)

| cluster | verdict | chain | contrast / expected | ks_mu / ks_flat | PID fwd (gate, μ, p, e) | Michel | note |
|---|---|---|---|---|---|---|---|
| 39 | no_bragg, shape_flat, not_muon_pid | 2 segs, 43 cm | 0.65 / 1.91 | 0.312 / 0.214 | 0, 0.34, 0.96, 0.19 | — | flat end |
| 55 | shape_flat, not_muon_pid | 1 seg, 31 cm | 1.38 / 1.70 | 0.059 / 0.054 | 0, 0.12, 0.49, 0.23 | 10.7 cm, 72°, 26 MeV | borderline shape |
| 79 | no_bragg, shape_flat, not_muon_pid | 1 seg, 153 cm | 0.05 / 1.92 | 0.343 / 0.250 | 0, 0.98, 2.21, 0.78 | 4 cm, 0.31 MIP, 2.5 MeV | end in a charge desert |
| 83 | **STM** | 1 seg, 30 cm | 1.57 / 1.83 | 0.044 / 0.065 | 1, 0.06, 0.75, 0.13 | 4.6 cm, 80°, 21 MeV | |
| 86 | **STM** | 1 seg, 65 cm | 1.78 / 2.06 | 0.035 / 0.088 | 1, 0.09, 0.79, 0.12 | 13.8 cm, 83°, 28 MeV | §8.0 case |
| 103 | stop_near_boundary | 1 seg, 92 cm | 2.04 / 1.91 | 0.040 / 0.097 | 1, 0.08, 0.79, 0.12 | 4.4 cm, 107°, 22 MeV | everything else passes |
| 109 | **STM** | 3 segs, 151 cm | 2.47 / 2.06 | 0.053 / 0.121 | 1, 0.08, 0.77, 0.15 | — | 2 delta rays |
| 113 | shape_flat, not_muon_pid, stop_near_boundary | 2 segs, 72 cm | 1.65 / 1.99 | 0.151 / 0.129 | 0, 1.39, 2.97, 1.08 | — | |

Stage time 2.0 s of a 39 s job (legacy `TaggerCheckNeutrino` on the same event:
4.4 s of 47 s).  PF trees: eight roots at the entries, `mu-` first child on
all eight, `e-` leaves under the muon on 55 / 83 / 86 / 103 (79's 2.5 MeV
Michel and 109's deltas fall under the display's 5 MeV floor).

### 8.2 The 120-event arm `d48nu3` (pin `new5`, `stm/events.txt`, 120/120 rc=0)

Wall per event: median 31.6 s, p90 59 s, max 93 s (JOBS=16).  The census
(`d48_stm_michel_census.py d48nu3`, TSV `figs/48_stm_michel_d48nu3.tsv`):

| | |
|---|---|
| STM candidates (tagged, not TGM) | **574** on 119 events |
| pass every check (`is_stm`) | **99 = 17.2 %**, on 68 events |
| chain found / stop matched | 574 / 567 (7 `stop_unmatched`, 0 `no_chain`) |
| stop vertex vs tagger stop | median 0.44 cm, p90 1.7 cm |
| muon chain length | p10/50/90 = 38 / 145 / 331 cm; segments per chain median 2 (p90 6) |
| Bragg contrast (552 valid) | p10/50/90 = 0.44 / 1.07 / 2.03; expected 1.83–2.06; **contrast ≥ 2: 62 / 552** (doc 25 §13.6 found 51/538 on the tagger fits) |
| `ks_mu < ks_flat` | 195 / 574 |
| template PID muon-like | 105 / 574 |
| continuation past the stop | 3 / 574 |
| arms at the stop | 188 chains have one; 137 Michel, 3 continuation, 48 neither |
| delta rays | 204 chains carry ≥ 1 (307 total, 0.53 per candidate); hadronic body arms 2 |
| Michel found | **137 / 574** (39 among `is_stm`); length p10/50/90 = 1.8 / 5.5 / 12.5 cm; 0.59–1.54 MIP; kink 16° / 56° / 118° |
| Michel KE (dQ/dx) | all: p10/50/90 = 3.2 / 14.2 / 28.3 MeV; among `is_stm`: 7.6 / 19.6 / 29.5 MeV, max 32.2 MeV |
| dots | 58 candidates with ≥ 1 fitted dot (74 total, 0.4–8.4 MeV); 0 unfitted companion clusters |
| stop inside the fiducial (5 cm inset) | 535 / 574 |
| PF trees | 574 roots, 563 with `mu-` first, 137 with an `e-` under the muon, 0 empty |

Reject bits (count carrying the bit / count where it is the only bit):

| bit | count | % | only |
|---|---|---|---|
| `not_muon_pid` | 469 | 81.7 | 65 |
| `shape_flat` | 379 | 66.0 | 1 |
| `no_bragg` | 321 | 55.9 | 1 |
| `stop_near_boundary` | 39 | 6.8 | 3 |
| `stop_unmatched` | 7 | 1.2 | 0 |
| `short` | 5 | 0.9 | 0 |
| `continuation` | 3 | 0.5 | 0 |
| `vertex_hadron` | 2 | 0.3 | 0 |

What the numbers say, and what they do not:

- The three dQ/dx bits agree with doc 25 §13.6's finding that most PDVD
  tagger stops are flat: the median contrast is 1.07 against an expected
  1.9, and only 62 of 552 chains reach 2×.  The 17 % that pass everything is
  the population doc 25 could not isolate; 39 of those 99 carry a Michel whose
  dQ/dx energy tops out at 32 MeV — consistent with a Michel spectrum ending
  near 53 MeV once the dead-region and recombination corrections it does not
  yet have are applied, but **not a measurement of it**.
- `not_muon_pid` is the workhorse bit and the only one that rejects alone in
  numbers (65).  It bundles the direction gate of `do_track_comp` with the
  three-template score; whether those 65 are stopped muons the template
  dislikes or something else is a hand-scan question, not a threshold one.
- **Continuation is 0.5 %, not doc 42's 26 %.**  The two are different
  quantities: doc 42 measured the tagger fit's own residual beyond its kink;
  here a collinear arm must exist as a separate PR segment leaving the stop
  vertex.  The PR partition places its vertex within 0.44 cm (median) of the
  tagger's kink, so the leftover, when it exists, becomes an arm — and of the
  188 arms at a stop, 137 turned enough to be Michels and 48 were neither.
  Whether those 48 (and the near-30° Michels) are the doc-42 leftover is the
  next hand-scan.
- Every Michel here is inside the muon's own cluster or bundle (§4); the 74
  dots add 3 MeV median.  Nothing in this table used a threshold that was
  chosen after seeing it, except the two definition fixes of §8.0, which are
  reported with their before/after.

## 9. Files and commits

**toolkit `apply-pointcloud`, commit `de1e846a`** (on `76f47614`):

- `clus/inc/WireCellClus/StmMichelFunctions.h`, `clus/src/StmMichelFunctions.cxx` — new: chain walk, profile, Bragg contrast, arm classification, reject bits.
- `clus/src/CheckSTM_Michel.cxx` — new: the visitor.
- `clus/test/doctest_stm_michel.cxx` (6 cases on synthetic graphs), `clus/test/doctest_check_stm_michel_defaults.cxx` — new.
- `root/inc/WireCellRoot/PdvdPrMagnifyTrackingVisitor.h`, `root/src/PdvdPrMagnifyTrackingVisitor.cxx` — `write_pc_tree` / `write_stm_michel_trees` (guarded on the PC's presence).
- `cfg/pgrapher/common/clus.jsonnet` — builder `check_stm_michel(...)`.
- `cfg/pgrapher/experiment/protodunevd/pr.jsonnet` — the node, `tagger_uses`, `pr_visitor` / `pr_tail_on`, `stm_michel_knobs`.

**wcp-porting-img `main`** (this doc's commit):

- `pdvd/docs/nf_sp_img_clus/48_check-stm-michel-chain.md` (this file),
  `pdvd/docs/nf_sp_img_clus/scripts/d48_stm_michel_census.py`,
  `pdvd/docs/nf_sp_img_clus/figs/48_stm_michel_d48nu3.tsv` (one row per candidate),
  `pdvd/stm/gates/d48_stm_michel_gate.txt`.
- `pdvd/wct-pr-perevt.jsonnet` (`pipeline_names` default, `stm_michel_knobs`), `pdvd/run_pr_evt.sh` (`-nu` / `-nu-legacy`).

Arms on disk (fresh tags, M13): `work/*_d48cfg`, `*_d48stmref2`, `*_d48stmnew4`,
`*_d48legref2`, `*_d48legnew4`, `*_d48smoke2..5`, `*_d48nu`, `*_d48nu2`, `*_d48nu3`
(PDVD); `pdhd/work/029107_0_d48ref2`, `_d48new4` (+ the superseded `d48ref`,
`d48new`, `d48new2`, `d48new3`); `sbnd_xin/work-stmcamp-d48gateold2`,
`-d48gatenew4` (+ superseded `-d48gateold`, `-d48gatenew`, `-d48gatenew2`,
`-d48gatenew3`).  Pins under `/home/xqian/tmp/d47_libpin/{ref,new,new2,new3,new4,new5}`.

Not done in this round, for the owner to schedule:

1. **Thresholds are untuned.** §8 gives the distributions; a hand-scan of the
   `is_stm` set and of the `not_muon_pid`-only rejects (the largest single
   class) is the next step, on the `d48nu3` Bee sets (`-nu` zips already on
   disk; upload is ask-first).
2. **A `stm_michel_pts` Bee layer** needs a pc branch in
   `MultiAlgBlobClustering::fill_bee_points_from_cluster` (shared file; the
   `stm_fit` branch is the precedent).  Until then the roles live in
   `T_stm_michel_pts` and the PF layers.
3. **Dots** are bounded to the flash bundle (§4).  Un-matched small clusters
   near a stop would need a t0 hypothesis (the muon's) to be placed — a
   separate design.
4. **MC truth**: the Michel energy scale and the reject rates want the PDVD
   sim (doc 25 owner decision: data first).
5. The legacy `-nu-legacy` tail and `tagger_output` can be retired from the
   PDVD driver once the owner is satisfied with §8 — a config-only follow-up.


## 10. Addendum 2026-09-05 (doc pdhd/03): what PDHD taught the stage

PDHD adopted this stage the same night (`pdhd/docs/03_check-stm-michel-pdhd.md`).  Its 30-event arms
found five defects/weaknesses that are now knobs or verdict semantics in `CheckSTM_Michel`; every
C++ default reproduces this doc's behaviour, and the PDVD `-nu` chain with defaults on the new
binary (`d48nu4`, pin new8) gives the SAME 99 `is_stm` of 574 as sec 8 (28 candidates change reject
*reasons*: 21 `no_bragg` -> `profile_sparse`, 6 collinear shower-flagged "Michels" -> `continuation`,
1 unmatched-stop chain re-walked).  New: `profile_min_dqdx_frac` (dead fit points out of the metrics),
`pid_mode` (the electron test rejected textbook muons; recomputed from this doc's TSV, 151 of 574 pass
everything but that test), `plateau_mip_lo/hi`, `stop_extend_max` + `michel_guards_stop`,
`dead_volume_check`, `min_chain_coverage`; bits 512-4096.  The PDVD arm with PDHD's operating point
(`d48nu5`, pin new9) is reported in doc pdhd/03 sec 7 -- NOT adopted for PDVD here; that is the
owner's call after a hand-scan.  [Corrected 2026-09-06: the arm reported in doc pdhd/03 sec 7 is
`d48nu7`, pin new11 -- the shipped binary; and the operating point WAS adopted, see sec 11.]  The census script `d48_stm_michel_census.py` knows the new bit names.


## 11. Addendum 2026-09-06 (owner flip): the doc pdhd/03 operating point becomes the PDVD default

**Owner ask 2026-09-06**: "please turn it on for PDVD now."  Goal stated with it: (1) select
stopping muons as completely as possible, (2) select STM + Michel out of that sample for other
uses, (3) *no* change to SBND.  The knob bag of doc pdhd/03 sec 6 is now the DEFAULT of
`stm_michel_knobs` in `pdvd/wct-pr-perevt.jsonnet`, so PDVD and PDHD share one operating point.

### Repro

```bash
# the flip is config-only: the knobs are in the shipped binary at their (OFF) C++ defaults
cd /nfs/data/1/xqian/toolkit-dev/toolkit/pdvd
# compiled-config proof (fresh tag; the dir only needs the pctree + .tlas symlinks)
PDVD_PR_COMPILE_ONLY=1 ./run_pr_evt.sh -s d48flipcfg {-stm | -nu | -nu-legacy} 39252 0
#   -> work/039252_0_d48flipcfg/.wct-pr_d48flipcfg.json
# the pre-flip measurement this section quotes (already run, do NOT re-run into these tags):
#   arm d48nu7 = PDVD, 120 events, pin /home/xqian/tmp/d47_libpin/new11, PDHD's bag via PDVD_PR_TLA
#   census     = pdhd/docs/figs/d03_stm_michel_d48nu7.tsv (one row per candidate, every verdict input)
```

### What changed

`stm_michel_knobs` default `{}` -> the nine keys of doc pdhd/03 sec 6:
`profile_min_dqdx_frac 0.15`, `pid_mode 2`, `plateau_mip_lo/hi 0.6/1.6`, `stop_extend_max 3`,
`michel_guards_stop true`, `michel_shower_min_kink_deg 15`, `stop_fv_use_config_tolerance true`,
`dead_volume_check true`.  `absorb_bragg_stub` and `min_chain_coverage` stay OFF (both measured
harmful / non-separating, doc pdhd/03 sec 6.5, 6.8).  No C++ change, no rebuild.

### Status flags

- PDVD `-nu`: **NOT bit-identical, and intended** -- this is the behaviour change the owner asked
  for.  Its pre-flip measurement is arm `d48nu7` (below).
- PDVD `-stm` (production) and `-nu-legacy`: **byte-identical** compiled config, proven below.
  `stm_michel_knobs` is inert unless `check_stm_michel` is in `pipeline_names`.
- **SBND: structurally untouched.**  `check_stm_michel` is instantiated only in
  `cfg/pgrapher/experiment/{pdhd,protodunevd}/pr.jsonnet`; `cfg/pgrapher/common/clus.jsonnet` holds
  the builder *definition* only, and SBND never calls it.  (Name collision to be aware of: SBND's
  `stm_michel_res_cm` in `sbnd/clus.jsonnet` is an unrelated `TaggerCheckSTM` doc-66 parameter.)
  The flip lives in `pdvd/wct-pr-perevt.jsonnet`, which SBND never reads.
- PDHD: untouched; its driver already carried this bag as its default since doc pdhd/03.

### Compiled-config proof (event 039252/0, tag `d48flipcfg`, 2026-09-06)

| mode | before vs after | verdict |
|---|---|---|
| `-stm` (production) | `cmp` of the compiled JSON | **IDENTICAL** |
| `-nu-legacy` | `cmp` of the compiled JSON | **IDENTICAL** |
| `-nu` | 61 nodes before and after; **1 node differs** (`CheckSTM_Michel` / `pr`): exactly the 9 keys ADDED, 0 removed, 0 changed | **as intended** |

### The measurement this flip rests on (arm d48nu7, pre-flip, 120 events / 574 candidates)

| | d48nu3 (C++ defaults = sec 8) | d48nu7 (this bag) |
|---|---|---|
| `is_stm` | 99 (17.2 %) | **148 (25.8 %)** |
| Michel-carrying passers | 39 | **55** |
| Michels overall / kink p10 | 137 / 21 deg | 123 / 31 deg |
| chains extended past the tagger's stop | -- | 7 |
| `dead_volume_check` fires | -- | 2 |
| wall, median | 31.6 s | 23.5 s |

Attribution of the 50 gained / 1 lost: **+49 `pid_mode`** (rejected before by the electron test
alone), **+1 `stop_fv_use_config_tolerance`** (the flat 5 cm inset), **-1 `plateau_off_mip`**.

**Not verified**: the purity of the +49.  They have not been hand-scanned, and PDHD's 8 passers
include one known false positive (029107/11 cluster 18, an EM blob).  Purity is what the next scan
is for; the flip is justified against sec 8's baseline, which is strictly worse on both of the
owner's objectives.

### Where the remaining stopping muons are (sole-bit census of d48nu7, 574 candidates)

Candidates rejected by exactly ONE bit -- i.e. what each single test costs, and how many of those
carry a Michel:

| sole reject bit | candidates | of which Michel-carrying |
|---|---|---|
| `shape_flat` (tagger KS) | **69** | **26** |
| `plateau_off_mip` | 13 | 3 |
| `profile_sparse` | 11 | 4 |
| `no_bragg` | 4 | 0 |
| `stop_near_boundary` | 4 | 2 |

`shape_flat` is now the dominant single rejector and the biggest Michel pool left -- 26 Michels
behind one test, against the 55 being shipped.  That is where the next round pays.

The 13 sole-`plateau_off_mip` rejects are the scan sheet for the one knob where the owner's two
objectives pull apart (a plateau at 0.22 MIP means a broken charge scale, hence an unusable Michel
KE, which is why the window ships ON at 0.6):

| event | cluster | plateau (e/cm) | stop x (cm) | Michel |
|---|---|---|---|---|
| 039252/17 | 88 | 31060 | 201.7 | yes, kink 87.5 deg, 18.8 MeV |
| 039349/77 | 52 | 18118 | 245.0 | yes, kink 43.0 deg, 7.7 MeV |
| 039349/71 | 51 | 12354 | 282.4 | yes, kink 26.9 deg, 3.7 MeV |
| 039252/6 | 106 | 100146 | 220.0 | no (above `plateau_mip_hi`) |
| 039252/8 | 97 | 13471 | 311.4 | no |
| 039349/24 | 21 | 10673 | -57.5 | no |
| 039349/26 | 34 | 22125 | 256.5 | no |
| 039349/37 | 52 | 13134 | 110.5 | no |
| 039349/40 | 49 | 18209 | 122.5 | no |
| 039349/56 | 18 | 32545 | -131.0 | no |
| 039349/60 | 47 | 22843 | 112.5 | no |
| 039349/7 | 65 | 32710 | 238.7 | no |
| 039349/8 | 51 | 18909 | 109.2 | no |

(`mip_dqdx` = 55000 e/cm on PDVD, so the window is 33000-88000.)  Reproduce with
`pdhd/docs/figs/d03_stm_michel_d48nu7.tsv`.

### Next steps

1. **The STM + Michel subsample needs no new code**: `T_stm_michel` already persists
   `michel_found`, `michel_kink_deg`, `michel_ke_best`, `michel_conn_type` per candidate.  The
   development left is purity/efficiency of that flag, not plumbing.
2. **Next round: `shape_flat`** (69 sole rejects, 26 with a Michel) -- the tagger's KS shape test,
   on chains whose Bragg verdict is otherwise clean.
3. Then the 13 above (`plateau_mip_lo`) and the 11 `profile_sparse`.
4. Michel KE still needs an MC-truth calibration (sec 8 next steps, unchanged).
5. A fresh 120-event PDVD arm on the flipped default is NOT taken here: `d48nu7` already is that
   arm's measurement, on the shipped pin.  Take one under a new tag when the next binary lands.
