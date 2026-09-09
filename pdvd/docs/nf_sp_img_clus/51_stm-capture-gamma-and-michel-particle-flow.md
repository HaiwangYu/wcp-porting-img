# doc pdvd/51 — the Michel in the particle flow, and the muon-capture gamma

**Status: NOT bit-identical.** `T_stm_michel` goes from **97 branches to 107**;
one existing point-cloud label changes meaning (`role` 4 → 3 for a bridged
Michel's pieces); and the two ProtoDUNE PR configs lower the Bee particle-flow
display floor `em_ke_min` from 5 MeV to 0.2 MeV. Shipped default-ON under the
owner's doc pdhd/14 waiver — *"You do not have default off knob. We are
developing this module for both PDHD and PDVD, this can be new feature default
on"* — with a doc pdhd/15 §7-style census as the substitute gate (§6).

Nothing outside the two ProtoDUNEs can see any of it: only
`cfg/pgrapher/experiment/{protodunevd,pdhd}/pr.jsonnet` bind
`check_stm_michel`, and the one shared-file change
(`MultiAlgBlobClustering`'s `ke_decimal_below`) is a new key whose C++ default
of 0 is today's behaviour, so its absence leaves SBND byte-identical.

## Repro

```bash
# the C++
cd /nfs/data/1/xqian/toolkit-dev/toolkit && wcbuild && ./build/clus/wcdoctest-clus
# NOTE: a new exported symbol plus a doctest that calls it cannot link against
# the STALE installed lib, and the failed build then skips the install that
# would provide it.  Break the cycle once:
#   ./wcb build --notests -p -k && ./wcb install --notests -p -k
# then a normal wcbuild links the tests (feedback_new_symbol_test_link_install).

# the four arms.  RUN NO WAF TARGET WHILE THESE ARE LIVE (doc pdhd/15 Repro).
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
S=pdvd/docs/nf_sp_img_clus/scripts
LEG='-S stm_michel_extra={stop_gamma_enable:false}'
ARM=d51gv    DET=pdvd SRC=d16vnu JOBS=8            $S/d51g_run_arms.sh
ARM=d51gvleg DET=pdvd SRC=d16vnu JOBS=8 PR_TLA="$LEG" $S/d51g_run_arms.sh
ARM=d51gh    DET=pdhd SRC=d16hnu JOBS=8            $S/d51g_run_arms.sh
ARM=d51ghleg DET=pdhd SRC=d16hnu JOBS=8 PR_TLA="$LEG" $S/d51g_run_arms.sh

# the population and the radius (sec 3, sec 4)
python3 $S/d51g_stop_gamma_census.py 'pdvd/work/*_d16vnu' --det pdvd \
        --out /home/xqian/tmp/d51/ana/d51g_pdvd

# every number in sec 6
python3 $S/d51g_branch_census.py --before 'pdvd/work/*_d16vnu' --before-arm d16vnu \
        --after 'pdvd/work/*_d51gvleg' --after-arm d51gvleg --pts \
        --label 'PDVD legacy equivalence' --out /home/xqian/tmp/d51/ana/leg_pdvd.txt
python3 $S/d51g_branch_census.py --before 'pdvd/work/*_d51gvleg' --before-arm d51gvleg \
        --after 'pdvd/work/*_d51gv' --after-arm d51gv --pts \
        --label 'PDVD the feature' --out /home/xqian/tmp/d51/ana/feat_pdvd.txt

# the two named items
grep 'CheckSTM_Michel: cluster 77 ' pdvd/work/039252_0_d51gv/wct_pr_039252_0.log
grep 'CheckSTM_Michel: cluster 77 ' pdvd/work/039252_15_d51gv/wct_pr_039252_15.log
```

Binary pin: `local/lib/libWireCellClus.so` md5 `be6328ac5886`, installed
2026-09-08 15:5x after the last source edit (M1 freshness proof); the arm script
prints the md5 before and after each arm and says so if it changed.

---

## 1. The two questions

The owner, hand-scanning PDVD on port 5017 (`--det pdvd --scan-tag smx1`, arm
`d16vnu`), asked two things about two items:

> *"For the evt 39252_15 cl 77 … I can see the Michel electron shown in red
> attached at the end of the STM, but I am a bit confused on why I did not see
> the Michel electron in the PF segment, which only shows the STM itself. How
> was the Michel electron reconstructed? Why is it not a PF particle?"*
>
> *"For evt 39252_0 cl 77 … the STM does not really attach to a Michel electron,
> but this bundle do have a low energy gamma near the stopping point of the STM.
> This is a typical case of muon capture by nuclei … we want the PF to
> reconstruct some low-energy gamma, and then attached to the STM."*

Both were answered from the **committed `d16vnu` output**. No new run was needed
to diagnose either; the runs in this doc exist to grade the fix.

## 2. Item 1 — the Michel IS a PF particle. Two display facts hid it

`T_stm_michel` for `039252_15` cluster 77:

```
is_stm 1  reject_bits 0  michel_found 1  michel_conn_type 2  michel_seg_id 265003
michel_dis_cm 0.38  michel_ke_best 76.76  n_dots 2  muon_ke_best 279.19
```

`michel_conn_type 2` is **bridged**: the Michel is a *separate live cluster*,
265, 1.91 cm past the fitted stop and in the muon's own Q-L bundle. Doc pdhd/13
found it, doc pdhd/15 admitted it (`companion_max_len_cm` 25 cm), and it is
reconstructed. It is also, already, in the particle flow — twice over:

* `T_rec_charge` rows for this candidate carry `sub_cluster_id` **265003**
  (28 points, `particle_id` **11**) and **265004** (7 points, `particle_id` 11,
  `flag_shower` 1);
* `mc.json` inside `mabc-pr.zip` renders
  `[77001] mu- 279 MeV → [1] gamma 76 MeV → [265003] e- 76 MeV`.

So nothing was missing from the reconstruction. Two separate things hid it from
the scanner, and both are real defects.

### 2.1 The PF panel's selector could not see a companion cluster

`prep_stm_michel_scan.py:231`:

```python
b = (rc["flag_vertex"] == 0) & ((rc["sub_cluster_id"] // 1000) == cid)
```

With `cid = 77`, segments 265003 and 265004 (`// 1000 == 265`) are dropped and
the panel can only ever show the muon. An **attached** Michel (conn type 1, e.g.
this event's cluster 91, segment 91002) lives in the candidate's own cluster and
does show — which is exactly why this looked like a per-item oddity rather than
a whole class. Every `michel_conn_type == 2` item on both detectors had the same
hole, and so does every capture gamma of §3, which is in a companion cluster by
construction.

**The fix rests on a join doc pdhd/12 §5.7 said could not be made.** Both ids are
`cluster_id * 1000 + segment graph index` — `CheckSTM_Michel.cxx:762-763` for
`T_stm_michel_pts.seg_id`, `PdvdPrMagnifyTrackingVisitor.cxx:905` for
`T_rec_charge.sub_cluster_id` — and they join exactly: **all 1107** distinct
`seg_id` values over the 119-event `d16vnu` arm are present in
`sub_cluster_id`. What is true is the weaker statement that the *partitions*
differ (one segment can carry points of more than one role), so a per-**point**
join is still not well posed; the per-**segment** join is, and that is what the
prep now uses. That docstring is corrected in place rather than deleted.

### 2.2 The red points were the `dots` layer, not a Michel layer

`stm_michel_viewer.py:317-318`: michel (`role == 3`) is **blue**, dots
(`role == 4`) are **red**. `CheckSTM_Michel.cxx:1390` set role 3 on **attached
arms only**; every bridged piece got role 4 at the dot loop. So the owner's "the
Michel electron shown in red" was the display telling them, correctly by its own
rules, that those points were *dots*.

Role 3 now means **a member of the Michel object**, for every connection type.
Role 4 remains the residual bucket for a fitted piece the object does not absorb
— today that is empty, because every admitted piece joins the object. The
migration is unconditional (it is a labelling correction, not a behaviour knob),
so it shows up even on the legacy arm; §6 checks that it is *exactly* the
bridged-piece population and that no point's `(seg_id, x, y, z, q)` moved.

One scalar branch is added for a consumer that reads `T_stm_michel` alone and
never opens the point cloud: `michel_n_clusters`, how many clusters the object
spans. The member list itself stays where it belongs — `T_stm_michel_pts`,
`role ∈ {3,4,5}` keyed by `seg_id`.

## 3. Item 2 — the capture gamma was 27 cm away, and one cut kept it out

`T_stm_michel` for `039252_0` cluster 77 said the chain saw **nothing**:
`michel_found 0`, `n_stop_arms 0`, `n_dots 0`, `n_dot_clusters_unfit 0`.

What is there is **cluster 206**: 6 points, 2.17 cm long, 2.26e4 e, `is_associated
1`, same bundle (flash 198, `cluster_t0_us` 3436.372), **26.5 cm from the fitted
stop** — and 26.5 cm from the muon *body* as well, i.e. its nearest muon point
**is** the stop — lying at **73.5°** to the muon direction there. That is a
textbook µ⁻-capture de-excitation gamma: neutral, so it leaves no track from the
stop, travels a couple of Compton mean free paths, and deposits a compact blob
off-axis.

It fails exactly one test. `michel_dot_radius_cm` is 15 cm and gates companion
**admission** (`CheckSTM_Michel.cxx:996`, against the tagger's stop). 26.5 > 15,
so cluster 206 never entered the fitter, never received `find_proto_vertex`, and
could become neither arm nor dot. No log line was emitted for it.

### 3.1 Why widening the Michel radius is the wrong fix

`michel_dot_radius_cm` feeds the Michel piece assembly as well as admission
(`:1448`). Widening it hands the Michel object more distant charge — and
`039252_15` cluster 77, the *other* item the owner is scanning, is already
**the single PDVD object above the 52.8 MeV Michel endpoint** (76.8 MeV of 160
objects on `d16vnu`). The Michel spectrum against that endpoint is the one
absolute, reconstruction-independent gate this module has, and it is not to be
spent on a different particle.

A capture gamma therefore gets its own **ring**, its own compactness and energy
caps, its own branches, its own point-cloud role, and its own PF nodes. Nothing
of it enters `michel_ke_*` — §6 asserts that identity on every candidate.

## 4. Is the population physics? Three measurements, taken before anything was built

`d51g_stop_gamma_census.py` on `d16vnu`. **Population, fixed for the whole
section: `is_stm == 1` candidates only** — 119 events, **151** of them, of which
144 have at least one same-bundle neighbour. (`n_stop_gammas` in §6 is written
for every candidate, `is_stm` or not, so the two populations must not be
compared without saying which is which: the same arm gives 167 objects over all
579 candidates and 57 over the 153 `is_stm` ones.)

The predicate here is the C++ one generalised to an arbitrary anchor: a blob
belongs to anchor A when its closest approach to A is in the ring, its length is
under the cap, and **every point of it** is farther from the muon body than the
blob is from A (body excluding 5 cm around A). That last clause is the one §6.5
is about — this section's measurement was made with it, and the first build of
the C++ was not.

**This section is the design study, not the gate.** Its predicate is an offline
reimplementation; the shipped selection is the C++, and §6.5 is a round in which
the two disagreed by a factor that inverted a sign. Every number the round
*claims* comes from the arm (§6).

### 4.1 The population is gamma-sized

Compact (≤ 25 cm) same-bundle blobs, 15 < d_stop ≤ 60 cm, n = 75:

| | p10 | p50 | p90 | max |
|---|---|---|---|---|
| d_stop (cm) | 21.0 | 39.6 | 54.4 | 59.2 |
| length (cm) | 2.04 | **2.64** | 4.44 | 10.2 |
| points | 4 | **8** | 18 | 36 |
| charge (e) | 1.04e4 | 2.73e4 | 1.23e5 | 3.74e5 |
| E (MeV, track pair) | 0.37 | **0.97** | 4.37 | 13.3 |

Compact and about an MeV — the right size and the right shape for a
de-excitation gamma's deposit.

### 4.2 The stop-anchored density falls; a background does not

Shell counts and r³-normalised density (counts × 1e4 / (r₂³ − r₁³)) around three
anchors on the **same muons**:

| shell (cm) | STOP | /r³ | ENTRY | /r³ | MID | /r³ |
|---|---|---|---|---|---|---|
| 0–10 | 15 | 150.0 | 3 | 30.0 | 0 | 0.0 |
| 10–15 | 7 | 29.5 | 4 | 16.8 | 1 | 4.2 |
| 15–20 | 6 | 13.0 | 2 | 4.3 | 0 | 0.0 |
| 20–30 | 20 | 10.5 | 4 | 2.1 | 3 | 1.6 |
| 30–40 | 14 | 3.8 | 6 | 1.6 | 1 | 0.3 |
| 40–50 | 22 | 3.6 | 7 | 1.1 | 0 | 0.0 |
| 50–60 | 13 | 1.4 | 5 | 0.5 | 1 | 0.1 |
| 60–80 | 41 | 1.4 | 13 | 0.4 | 0 | 0.0 |
| 80–100 | 2 | 0.04 | 2 | 0.04 | 0 | 0.0 |
| 100–150 | 9 | 0.04 | 1 | 0.004 | 0 | 0.0 |

**None of these three anchors is a clean null, and the doc will not pretend
otherwise.**

* **ENTRY** is the doc pdhd/13 §6 control and it is *boundary-biased*: an entry
  sits on a detector face, so roughly half its sphere is outside the detector.
  That alone buys a factor ≈ 2, which is the order of the stop/entry ratio here
  (it sits near 3 at every radius and never dies). The excess over entry is an
  **upper bound** on purity, not a measurement of it.
* **MID** (a body point at rr ≈ muon_len/2) is **degenerate by construction**
  and is reported only as a predicate sanity check. The body test is not
  anchor-symmetric: at an endpoint the body lies to one side, so a blob past it
  is far from the body; at a mid-track anchor the track runs both ways, so
  almost nothing can be closer to the anchor than to the body. Its near-zero
  counts say the predicate really does demand "past an endpoint". They are not
  a null.

### 4.3 What "flat" looks like — the foreign-bundle control

The same anchor, the same shells, the same predicate, but companions from a
**different** Q-L bundle: unrelated to this muon by construction, so their
density is the event's ambient compact-blob density.

| shell (cm) | same-bundle density | foreign-bundle density |
|---|---|---|
| 0–10 | 23.72 | 0.00 |
| 10–15 | 4.66 | 0.67 |
| 15–20 | 2.05 | 1.71 |
| 20–30 | **1.66** | 0.83 |
| 30–40 | 0.60 | 0.90 |
| 40–50 | 0.57 | 0.60 |
| 50–60 | 0.23 | 0.59 |
| 60–80 | 0.22 | 0.71 |
| 80–100 | 0.007 | 0.62 |
| 100–150 | 0.006 | 0.48 |

(blobs per candidate per 1e6 cm³.) The foreign column is **flat at ~0.6 from 30
to 150 cm** — which is what a volume-filling background must look like, and it
validates the r³ normalisation empirically instead of asserting it. Against
that, the same-bundle stop-anchored density falls by a factor **4000**.

**It is not a purity denominator, and the ratio must not be read as one.** There
are ~340 foreign clusters per event against ~6 same-bundle ones, so equal
*density* means the same-bundle blobs are ~50× more concentrated at the stop per
available cluster. The algorithm never admits a foreign cluster (the
`matched_flash_gid` test), so its background is same-bundle blobs that are not
capture gammas, and the entry anchor is the only handle this census has on that.

### 4.4 The µ⁻ signature — the one test that needs no spatial null

Capture gives **no Michel and gammas**; decay gives **a Michel and no capture
gammas**. So the blob rate must be higher on the `michel_found == 0` population,
and that prediction owes nothing to any threshold in this census.

| outer radius R (cm) | blobs | candidates | rate(no Michel) | rate(Michel) | ratio |
|---|---|---|---|---|---|
| 25 | 16 | 12 | 0.133 | 0.074 | 1.80 |
| 30 | 26 | 20 | 0.217 | 0.118 | 1.84 |
| **35** | **28** | **22** | **0.241** | **0.118** | **2.05** |
| 40 | 40 | 30 | 0.337 | 0.176 | 1.91 |
| 45 | 49 | 35 | 0.373 | 0.265 | 1.41 |
| 60 | 74 | 43 | 0.542 | 0.426 | 1.27 |
| 100 | 116 | 60 | 0.855 | 0.662 | 1.29 |

(83 candidates with `michel_found == 0`, 68 with 1.)

The direction is right and the effect dies exactly where §4.3's density knee is.
**It is ~1.9 σ on this sample, and that is stated as a direction, not a
measurement**: at R = 35 the split is 20/8 against 15.4/12.6 expected under a
common rate. It is not evidence that any individual object is a capture gamma —
that is what the hand scan is for (§8).

## 5. What the round changes

### 5.1 A capture-gamma object: the ring, the caps, and the body

A gamma candidate is a **companion cluster** — same Q-L bundle, the only clusters
with a t0 and hence a drift coordinate — that the Michel object does not own and
that passes, in this order:

| stage | test | why |
|---|---|---|
| admission (pre-fit) | `michel_dot_radius_cm < d ≤ stop_gamma_radius_cm` from the **final** stop | inside the inner edge the charge is the Michel's to claim; outside the outer edge the stop-anchored excess has died (§4) |
| admission | cluster length ≤ `stop_gamma_max_len_cm` | a gamma deposit is a blob; a 30 cm object past a stop is another cosmic in the same bundle |
| admission | **cluster-level body exclusion** — every point of the companion, against the muon profile beyond `dot_body_exclusion_cm` of the stop | §6.5. A companion whose charge comes nearer the muon **body** than the stop is a delta ray or Michel activity |
| — | the fitter produces at least one segment | without a segment there is nothing a `PR::Shower` can hold; the cluster is counted in `stop_gamma_n_unfit` and its charge converted, and it makes **no** PF node |
| acceptance (post-fit) | `stop_gamma_min_ke_mev ≤ ΣdQ/dx ≤ stop_gamma_max_ke_mev`, at most `stop_gamma_max_n` | an energy does not exist until the fitter has run, so this cannot gate the loop above |

**Admission and acceptance are deliberately separate.** A candidate rejected at
acceptance is dropped from the object list, *not* from the fitter — its charge
stays in the 2-D maps and it still perturbs the fit (§6.3). Conflating the two
would be a bug waiting to happen, because the energy is simply not available at
admission time.

The ring and window predicates live in `StmMichelFunctions` as free functions
(`stm_michel_stop_gamma_ring`, `stm_michel_stop_gamma_energy`) purely so their
boundaries are doctested: the ring's inner edge is **exclusive** while the
Michel's own cluster test is `<=`, so the two partitions neither overlap nor
leave a gap, and a NaN admits nothing.

### 5.2 `stop_gamma_radius_cm = 35`

Set by §4.3's density knee (1.66 → 0.60 between the 20–30 and 30–40 shells,
against an ambient floor the foreign-bundle control measures **flat** at ~0.6)
and by §4.4's µ⁻ anti-correlation, which peaks at 35 cm and collapses to 1.41 by
45. `039252_0` cluster 77's gamma is at 26.5 cm, comfortably inside. It is a
knob, and it is the value most likely to move after the owner scans.

### 5.3 The ring is doing real work

`039252_0` cluster 77 has **six** same-bundle associated clusters, at 26.5,
99.3, 120.9, 127.7, 131.8 and 168.9 cm from the stop. Only the first is a
plausible capture gamma; a 35 cm ring excludes the other five by construction.
**"Same Q-L bundle" alone is not a discriminator** — that is why admission was
not simply opened to the bundle, and it is the cleanest single illustration of
it in the sample.

### 5.4 The knobs

| knob | default | gates |
|---|---|---|
| `stop_gamma_enable` | `true` | the feature; `false` restores the doc pdhd/17 admission radius exactly |
| `stop_gamma_radius_cm` | `35.0` | the ring's outer edge (inner edge = `michel_dot_radius_cm`) |
| `stop_gamma_max_len_cm` | `10.0` | compactness |
| `stop_gamma_min_ke_mev` / `_max_ke_mev` | `0.2` / `20.0` | the acceptance window |
| `stop_gamma_max_n` | `8` | per-candidate cap |

New `T_stm_michel` branches: `n_stop_gammas`, `stop_gamma_ke_tot`,
`stop_gamma_ke_max`, `stop_gamma_charge`, `stop_gamma_dis_min`,
`stop_gamma_dis_max`, `stop_gamma_n_unfit`, `stop_gamma_seg_id`, plus
`michel_n_clusters` (§2.2). Per-object detail is `T_stm_michel_pts` at **role
5**, keyed by `seg_id`.

### 5.5 The particle-flow node

One `PR::Shower` per admitted cluster, built exactly the way doc pdhd/15 builds a
bridged Michel: `set_start_vertex(stop_v, 2)` → `set_start_segment(nearest)` →
`add_segment(...)` → `set_particle_type(11)`, inserted into the same `showers`
set that reaches `tf->set_showers(showers)`.

**PDG 22 is never stored.** `ParticleDataSet::get_particle_mass(22)` returns 0
and `cal_kine_range` silently falls back to the *muon* range function, which is
why nothing in this codebase writes a 22 onto a segment or a shower. The `gamma`
node is **synthesised by the renderer** from the connection type
(`MultiAlgBlobClustering.cxx:2154`) and the `e-` leaf under it is what was
actually reconstructed — the conversion. For a capture gamma that pseudo-carrier
is not a workaround: it is the correct physical statement, that an unseen neutral
crossed the gap. `mc.json` for the owner's item now reads

```
[77003] mu-  306 MeV
  [1000005] gamma  0.95 MeV
    [206004] e-  0.95 MeV
```

**The energy has to be stamped back.** For a conn-2 EM shower `kenergy_best` is 0
and `get_kine_best()` falls back to `kenergy_charge`, which is 0 on this path
(doc pdhd/15 §6, the beam-frame defect), so without `set_kine_best` the
renderer's `em_ke_min` prune deletes the node whole — the same trap doc pdhd/15
§8 hit on the Michel.

### 5.6 Two display floors in `pr.jsonnet`, and why both had to move

* **`em_ke_min` 5 → 0.2 MeV.** It is a *display* floor (`keep_node`,
  `MultiAlgBlobClustering.cxx:2078`) and at 5 MeV it deletes every capture gamma,
  because the population is ~1 MeV. `append_pseudo_shower` drops the carrier too
  when its only leaf goes (`:2174`), so the node would vanish whole rather than
  appear with a wrong number. **Collateral, measured not assumed:** over
  `d16vnu` (119 events) the PR labels **1096** segments pdg 11 and **666** reach
  `mc.json`, so lowering the floor can restore at most **~430 nodes**
  (≈ 3.6/event), mostly sub-5-MeV delta rays. §6.4 reports what it actually did.
* **`ke_decimal_below` 0 → 10 MeV (new).** `prototype_names` renders KE as an
  *integer* number of MeV (the prototype's `int e = KE*1000`), so the first build
  of this feature produced `gamma  0 MeV` for a 0.95 MeV object — half the
  population would have been labelled 0. Below this value the node text carries
  two decimals. The C++ default is **0 = off = prototype formatting for every
  energy**, so the key's absence is byte-identical and no other detector sees it.
  This is the round's only change to a file SBND shares.

### 5.7 The display

`pdhd/stm_michel_scan/`: the PF panel's selector is widened by the per-segment
join of §2.1 (`chain_segs`, the ids the chain itself names in
`T_stm_michel_pts`); a **role-5 gamma layer** in green hexes joins the 3-D view,
the three 2-D projections and the dQ/dx panel; and the flow panel gains a
capture-γ line under the muon, every field a `T_stm_michel` branch (the owner's
standing rule from doc pdhd/14 — the display computes no energy of its own).

`stm_michel_extra` is a new merge-on-top knob bag in **both**
`wct-pr-perevt.jsonnet`. `-S stm_michel_knobs={...}` *replaces* the driver's
15-key default, so flipping one knob for an A/B arm used to mean re-transcribing
every other one — and the arm's correctness then silently depended on that
transcription. `-S stm_michel_extra={stop_gamma_enable:false}` is a provably
one-key change: the compiled-config diff between the two arms is exactly
`stop_gamma_enable  <absent> → false` and nothing else.

## 6. The gates

Four arms, **one pinned binary** — `libWireCellClus.so` md5 `9ee23d287d57`,
snapshotted to `/home/xqian/tmp/d51/libpin` and prepended to
`LD_LIBRARY_PATH`; the script prints the md5 before and after each arm and all
eight readings agree. The pin is not optional here, see §6.6.

| arm | detector | events | events complete |
|---|---|---|---|
| `d51gv` | PDVD | 120 | 119 |
| `d51gvleg` | PDVD, `stop_gamma_enable=false` | 120 | 119 |
| `d51gh` | PDHD | 61 | 61 |
| `d51ghleg` | PDHD, `stop_gamma_enable=false` | 61 | 61 |

**PDVD's one "incomplete" event is `039252_11`, and it is pre-existing**: that
event has no `T_stm_michel` in `d16vnu` either — the per-bundle PR runs only on
STM-tagged bundles and this event has none, so `CheckSTM_Michel` never visits.
It is not attrition from this round.

| gate | result |
|---|---|
| `./build/clus/wcdoctest-clus` | 338 cases, **23236 assertions, 0 failed** (was 335 / 23172) |
| `selftest_stm_michel_scan.py --det pdvd` | **48894 checks, 0 failed** |
| `selftest_stm_michel_scan.py --det pdhd` | **28552 checks, 0 failed** |
| `selftest_smx3d_browser.py` | **77 browser checks, 0 failed** per detector (was 59) |

### 6.1 Legacy equivalence — the pure code-change gate

`stop_gamma_enable=false` restores the old admission radius exactly, so this arm
carries no preload perturbation and nothing may move.

**PDVD, `d51gvleg` vs `d16vnu`, 579 matched candidates, 97 shared branches:**

> **579 / 579 bit-identical on every one of the 97 shared branches. No shared
> branch moved on any candidate.** 9 branches are new.

**PDHD, `d51ghleg` vs `d16hnu`, 325 matched candidates: 308 / 325
bit-identical.** The 17 movers touch **exactly two** branches, `dots_ke_unfit`
and `michel_ke_best`, and **no verdict-relevant branch at all** (0 `is_stm`
flips). That is not this round: `d16hnu` predates `ff7db93f`, which turned
`michel_unfit_from_model` on in both drivers (doc pdhd/17 §9), and 17 is PDHD's
unfitted-companion population — the only place that knob can act. PDVD has none,
which is why its legacy arm is clean.

`T_stm_michel_pts` **is** expected to differ on the legacy arm, because the
role 4 → 3 migration is unconditional. It is exactly the declared migration:

| | candidates | identical point geometry | role labels moved | purely 4 → 3 |
|---|---|---|---|---|
| PDVD | 579 | **579 / 579** | 63 | **63 / 63** |
| PDHD | 325 | **325 / 325** | 47 | **47 / 47** |

Not one point's `(seg_id, x, y, z, q)` changed. PDVD's role histogram goes
`{1: 166137, 2: 2886, 3: 1505, 4: 413}` → `{1: 166137, 2: 2886, 3: 1918}` —
413 points migrate and **role 4 is now empty**, which is the measured form of
§2.2's claim that every admitted piece joins the object.

### 6.2 The feature

`d51gv` vs `d51gvleg` — same binary, same input, gammas on vs off.

| | candidates | bit-identical on all 106 | moved |
|---|---|---|---|
| PDVD | 579 | **432** | 147 |
| PDHD | 325 | **243** | 82 |

The moved branches are the fit's own — `muon_ke_dqdx`, `plateau_med`, `ks_mu`,
`contrast`, `muon_len`, `n_profile_pts` — which is the **preload perturbation**
and is exactly where the design says it can be: admitting a companion feeds it
to `TrackFitting::preload_clusters`, whose blobs enter `prepare_data()`, so the
candidate's own muon dQ/dx can move. Doc pdhd/15 §7 saw this from 6 new
companions; here the admission radius goes 15 → 35 cm, so the perturbed set is
larger by construction.

**Two `is_stm` flips on PDVD, both 0 → 1, none on PDHD.** Named, not tuned
(CLAUDE.md §5.7):

```
039253_9  cl 111  is_stm 0 -> 1   contrast 1.3434 -> 1.3191   muon_len 72.26 -> 71.78
039349_6  cl  62  is_stm 0 -> 1   contrast 0.9292 -> 1.1529   muon_len 289.79 -> 295.79
```

`039349_6` is the doc pdhd/15 §7 shape with the same sign as its `039349_37`:
the fit is better informed, the Bragg contrast rises through the 0.6 threshold.
`039253_9` is **not** — its contrast *fell* and it still flipped, so the
rejection it lost was a different bit. Both belong in the scan, and neither is a
reason to move a threshold.

Role histogram, PDVD, off → on:
`{1: 166137, 2: 2886, 3: 1918}` → `{1: 166202, 2: 2816, 3: 1917, 5: 345}`.
**Role 5 is the new object class, 345 points.** Role 1 gains 65 points and role
2 loses 70: the perturbed fits are slightly longer and a few delta arms
reclassified — the same perturbation, seen in the point cloud.

### 6.3 The objects, and the µ⁻ signature re-derived FROM THE ARM

§4's ratio came from an offline predicate. This one comes from what the chain
accepted (`d51g_stop_gamma_census.py --from-arm`), and it is the number the
round claims:

| | candidates (`is_stm`) | gamma objects | on N candidates | KE p10/p50/p90 (MeV) | d_stop p50 |
|---|---|---|---|---|---|
| PDVD | 153 | **30** | 22 (14.4 %) | 0.74 / **1.94** / 6.86 | 25.0 cm |
| PDHD | 61 | **10** | 10 (16.4 %) | 0.79 / **0.93** / 3.23 | 20.1 cm |

| µ⁻ signature | no Michel | Michel | ratio |
|---|---|---|---|
| PDVD | 0.238 objects/cand (84 cands) | 0.145 (69) | **1.64** |
| PDHD | 0.176 (34) | 0.148 (27) | **1.19** |

Both point the way the mechanism predicts, and neither is significant on its own
— PDHD's whole sample is 10 objects. PDVD's 1.64 against the offline predicate's
2.05 is the agreement §6.5 exists to establish.

### 6.4 The two Bee display floors, measured separately

Because the legacy arm carries the new floors and no capture gammas, the two
effects separate exactly (`d51g_pf_tree_census.py`, 119 PDVD events):

| | PF nodes with an energy | Δ | Δ/event |
|---|---|---|---|
| `d16vnu` → `d51gvleg` (**`em_ke_min` alone**) | 2542 → 2833 | **+291** | +2.45 |
| `d51gvleg` → `d51gv` (**the capture gammas alone**) | 2833 → 3024 | **+191** | +1.61 |

`em_ke_min` 5 → 0.2 MeV restores **+291** nodes (e⁻ +264, γ +27) on 100 of 119
events and removes none — comfortably under §5.6's ≤ 430 upper bound, and the
gap is the shower-masked segments that were never pruned in the first place.
The capture gammas add +191 (γ +101 carriers, e⁻ +83 leaves, µ⁻ +7 from the
perturbed fits); 4 events *lose* nodes, which is the same perturbation moving a
fit rather than anything being suppressed. Nodes labelled below 1 MeV go
12 → 36 → **97**: without `ke_decimal_below` every one of those would read
"0 MeV".

### 6.5 The defect this round created, found, and fixed — read this before trusting §4

§4's µ⁻ anti-correlation was measured with an **offline** predicate. The first
implementation of the same predicate in C++ gave **0.44** on the arm — the
opposite sign — and it took two fixes to reconcile, because the body-exclusion
clause differed in two independent ways:

1. the C++ tested **one fitted segment's** closest point; the census tested
   **every point of the cluster**;
2. after fixing that, the C++ body was **the muon profile alone**; the census
   body was **every fitted segment of the candidate**, which on an *attached*
   Michel includes the Michel's arms.

The mechanism is that **29 of the 30 spurious admissions land on candidates that
also have a Michel**: they are **Michel satellites**. A Michel showers, and its
outlying blobs sit past the stop, in the bundle, compact, and pass every other
test — and a muon-profile body cannot see them, because an attached Michel's
arms are not in it. Fixing (1) alone changed the arm by **zero** objects, which
is the tell that the first diagnosis was incomplete; an offline filter had
predicted it should drop 30.

The shipped test is therefore at **cluster level against everything the chain has
already claimed** (roles 1–4), snapshotted before the loop so one accepted gamma
cannot exclude the next. Nothing failed while this was wrong: the doctests
passed, the arms ran, the objects looked right. Only re-deriving the headline
physics number *from the arm* exposed it — which is why §6.3 exists and why the
census script grew a `--from-arm` mode.

### 6.6 The campaign had to be run three times

The first two campaigns are **void** and their numbers appear nowhere in this
doc. A peer session ran a waf target in this shared tree while 362 events were
live: `local/lib/libWireCellClus.so` went `75465affecfb` → `ca225ad952e8` →
`9ee23d287d57` under three running arms and 14 PDHD events died with
`file too short` — 4 logs and 10 `wall_s=0` rows, the exact tell from
`feedback_shared_tree_binary_pin`. `wire-cell` dlopens its plugins once per job
at job start, so a mid-campaign rebuild splits an arm across binaries and
**nothing in the output says so**.

The third campaign ran under the private pin, verified the way the memory
prescribes — `grep libWireCellClus /proc/<pid>/maps` on a **running** job showed
`/home/xqian/tmp/d51/libpin/libWireCellClus.so` — and `d51g_run_arms.sh` now
refuses to be quiet about it: it prints the md5 before and after, and warns if
they differ. (One false positive was found and fixed in the same script: its
loader-death check globbed *all* of an arm's logs, so a re-run over a previous
campaign reported the **previous** run's deaths. It now only looks at logs newer
than the arm's start.)

### 6.7 The shipped binary reproduces the arm

The arms were pinned at `9ee23d287d57`; the code committed here builds to
`7907d049ef82`, because two comment corrections landed after the pin **and**
because the peer's `9de28b32` (doc pdhd/16 §9, the MCS cathode-excision
counters) landed at 16:45, mid-campaign. So the installed library is not
byte-equal to the one graded, and the claim has to be made on behaviour rather
than on a hash. Re-running `039252_0` with the installed library:

> **Bit-identical on all 106 shared `T_stm_michel` branches**, every row. The
> only difference is two branches the newer binary *adds* —
> `muon_mcs_cathode_segs` and `muon_mcs_cathode_angles` — which are the peer's
> commit, additive, and orthogonal to everything here.

### 6.8 Cost

`CheckSTM_Michel`'s own wall time on the two named events, `d16vnu` → the fixed
arm: `039252_0` **4802 → 4347 ms**, `039252_15` **1482 → 1426 ms**; whole-job
wall 25 → 17 s and 27 → 23 s, peak RSS 1.39 → 1.43 and 2.09 → 1.95 GB. The
cluster-level body loop is O(body points × companions) `get_closest_point_blob`
queries per candidate with an early break on the deciding comparison, and it
does not show above the run-to-run spread. Two events under different machine
load is a weak measurement, and it is quoted as "not material", not as a speedup.

### 6.9 The hand-scan display, and the owner's two items

The scan on 5017 is preserved exactly. Re-prepped with `--pin-tranche` (doc
pdhd/15 §10) and served under the same tag `smx1`:

| check | PDVD | PDHD |
|---|---|---|
| items | 568 → **568** | 302 → **303** |
| `scan_id` changes vs the committed sheet | **0** | 39 |
| `tranche` changes | **0** | **0** |
| labels intact | **6 / 6**, all tranche 1 | none exist |

PDHD gains one item, `029107_3` cluster 31, at **tranche 2** — a pinned sample
never grows into tranche 1. It entered because the preload perturbation extended
its fit past the sheet's sample cut (10 → 35 profile points, 5.4 → 19.6 cm);
`is_stm` is 0 both before and after. Its insertion shifts 39 PDHD `scan_id`
positions, which disturbs no scan because PDHD has no labels.

The owner's two items, on the final arm:

```
039252_0  cl 77   gammas 1 (0.9 MeV, max 0.9, 26.9-26.9 cm, 0 unfit)
     mc.json:  [77003] mu- 306 MeV -> [1000005] gamma 0.95 MeV -> [206004] e- 0.95 MeV
     PF panel: segments [77003, 206004]        <- was [77003] alone
     layers:   gamma 2 points (seg 206004)

039252_15 cl 77   michel 1 conn 2
     mc.json:  [77001] mu- 279 MeV -> [1] gamma 76 MeV -> [265003] e- 76 MeV
     PF panel: segments [77001, 265003, 265004]   <- was [77001] alone
     layers:   michel 35 points (segs 265003, 265004)   <- was the `dots` layer
```

Three self-test assertions had to be updated to the new role semantics, and each
was made **tighter**, not weaker: `michel_seg_id` must now name a role-3 segment
for both connection types; `dots_ke_dqdx` is now checked against the role-3
segments **whose seg_id names another cluster** (a piece comes from a companion
by construction, an attached arm does not), which is a sharper identification
than the role test it replaces; and a PF segment from a foreign cluster is
admissible **if and only if the chain itself named it** in `chain_segs`, which is
what keeps the selector widening from becoming "anything goes".

## 7. Limits

1. **`is_stm` is a verdict, not truth.** Every rate here is against the chain's
   own verdict. Nothing in this doc is measured against a hand label; §8 is how
   that changes.
2. **Nothing here shows that any individual object is a capture gamma.** What is
   shown is that the population is compact, ~1 MeV, past the stop, in the muon's
   own Q-L bundle, falls steeply with distance from the stop against a flat
   ambient floor, and is anti-correlated with the presence of a Michel. Those
   are consistent with capture. A delta ray thrown forward, a fragment of the
   same cosmic, and a genuinely unrelated in-bundle blob all survive some of
   those tests.
3. **The µ⁻ anti-correlation is ~2 σ**, not a measurement. At R = 35 cm the
   census splits 20/8 against 15.4/12.6 expected under a common rate. It is
   quoted as a direction because it points the way a physical mechanism predicts,
   not because the sample can resolve it.
4. **`michel_found` is itself a reconstruction verdict**, so the two arms of §4.4
   are not "capture" and "decay" — they are "the chain found something at the
   stop" and "it did not". Conditioning on the number of same-bundle companions
   near the stop (0 / 1 / 2 / 3+) leaves the ratio at 9.3 / 9.4 / 1.7, and the
   confound runs the *other* way (Michel-carrying candidates average 1.39
   companions against 0.73), so it dilutes the effect rather than creating it.
5. **The energy upper tail is where the object class is least defensible.** A
   nuclear de-excitation cascade after µ⁻ capture in argon runs to a few MeV; the
   accepted objects reach `stop_gamma_ke_max` well above that, and the 20 MeV
   acceptance ceiling is a guard, not a physics statement. §8 makes this the
   scan's first question.
6. **The charge-only path (`stop_gamma_n_unfit`) makes no PF node.** There is no
   toolkit API to build a `PR::Shower` from a bare point cloud —
   `Shower::set_start_segment` requires a valid graph descriptor — so a companion
   the fitter never reached is counted and its charge converted, and that is all.
   PDVD produces none of these; PDHD is where the path lives.
7. **The bundle key is `(flash_id, cluster_t0_us)` — both.** A flash alone is not
   a unique bundle key.

## 8. What to scan, and what it decides

The doc pdhd/12 display on port 5017 is the instrument, and this round gives it
the three things it needed: the object is drawn in its own colour (role 5), the
flow panel names it with the chain's own numbers, and the PF panel finally shows
a companion-cluster segment — so a bridged Michel and a capture gamma are both
visible where the scanner is already looking.

Three questions, in the order that makes each one answerable:

1. **Are the accepted objects EM blobs at all, or fragments of the muon?** The
   2-D measurement tab is the arbiter: a real deposit shows measured charge with
   no predicted charge, the way `039252_15`'s Michel did in doc pdhd/13 §2.4.
2. **Does the energy tail hold up?** Take the accepted objects above ~5 MeV
   first. If they are single compact blobs the acceptance ceiling is fine; if
   they are the same cosmic's fragments, `stop_gamma_max_len_cm` or the ring is
   what wants tightening, not the ceiling.
3. **Only then, the µ⁻ question.** With hand labels for "is there a Michel" the
   §4.4 ratio can be re-measured against truth rather than against
   `michel_found`, which is the one thing that would turn a 2 σ direction into a
   measurement.

**Recommended next step:** scan the **38 PDVD `is_stm` candidates that carry a
capture-gamma object** on 5017 (they are a strict subset of the existing 568-item
sheet, so no re-draw and no new tag is needed — the tranche pin holds), starting
with the highest `stop_gamma_ke_tot`. That is the smallest sample that can answer
question 2, and question 2 is what decides whether the 20 MeV ceiling and the
35 cm ring are right. Everything else in §9 is cheaper to settle afterwards.

## 9. Open items — the owner's call

1. **`stop_gamma_radius_cm = 35` is the value most likely to move.** §4.3's knee
   and §4.4's plateau agree on it, but both are ~2 σ instruments. The scan of §8
   is what should set it.
2. **The 20 MeV acceptance ceiling** is a guard against absorbing a neighbouring
   cosmic, not a physics limit; §7.5 says the tail above a few MeV is where the
   class is weakest.
3. **`em_ke_min` 5 → 0.2 MeV** restores sub-5-MeV EM leaves across the *whole*
   PF tree, not only the new objects (§6.4 has the measured count). If the owner
   wants the capture gammas without the rest, the alternative is a default-OFF
   `MultiAlgBlobClustering` knob exempting a named shower class from the floor —
   named here, deliberately not taken, because it touches a renderer SBND shares.
4. **The bridged-Michel pseudo-gamma carrier stays** (owner ruling 2026-09-08,
   doc pdhd/15 §9 item 1). It now renders identically to a capture gamma, which
   is correct for the gamma and a bridge artifact for the Michel; the flow panel
   distinguishes them, `mc.json` does not.
5. **`michel_ke_charge` is still 0 by construction** on both ProtoDUNEs (doc
   pdhd/15 §6): the chain's charge estimator is beam-frame only. Unchanged here.
6. **`039252_15` cluster 77 is still 76.8 MeV**, above the 52.8 MeV Michel
   endpoint and the only PDVD object that is. This round deliberately did not
   touch it — it is a Michel-assembly question (doc pdhd/15 §9 item 6, the
   body-exclusion test as the only thing separating a Michel piece from an
   unrelated neighbour), not a gamma question.
7. Still open from doc pdhd/13: why 3-D clustering split a Michel that is
   2-D-contiguous with its muon in all three planes; and defect D3, the segments
   the PR fits and the arm classifier then discards.
