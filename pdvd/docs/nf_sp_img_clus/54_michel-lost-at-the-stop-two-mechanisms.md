# 54 — Two ways the Michel is lost at the stopping point: a kink the tagger will not accept, and a residual the PR throws away

**Status (2026-09-08). Diagnosis only. No code is changed, no config is
changed, no arm is run, and therefore no A/B gate is owed by this document and
none is claimed.** Both findings come out of the owner's hand scan of the PDVD
STM/Michel candidates (arm `d53v`, scan tag `smx1`) and are recorded here so
they can be dealt with later. Neither is fixed. In both cases a parameter could
be moved to make the symptom go away; per CLAUDE.md §5.7 this document reports
the mechanism and names the lane, and proposes no constant.

Provenance: toolkit `3e9c1097`, wcp-porting-img `67a0d02b`, arm `d53v`
(569 candidates, 120 events).

---

## 0. Repro

Every number below comes from one of these. They read the shipped arm outputs
and the shipped scan payloads; none of them runs reconstruction.

```bash
cd /home/xqian/toolkit-dev/wcp-porting-img/pdvd/docs/nf_sp_img_clus/scripts

# --- sec 1, event 039349_18 cluster 36 ------------------------------------
python3 stm_find_first_kink_one_event.py     # sec 1.2: the gate table at i=213
python3 stm_stop_is_the_kink_point.py        # sec 1.3: 145/145, the stop IS pts[kink]
python3 stm_find_first_kink_offline.py       # sec 1.3: 140/145 index agreement
python3 stm_bragg_windows_counterfactual.py  # sec 1.4/1.5: contrast 0.480 -> 1.95
python3 stm_swallowed_michel_census.py       # sec 1.6: 6 of 569

# --- sec 2, event 039253_8 cluster 62 -------------------------------------
python3 pr54_isolated_residual_census.py     # sec 2.3: 363 drops / 38 keeps
python3 stm_unfitted_lump_census.py pdvd     # sec 2.4: 44 of 569 lumps
python3 stm_unfitted_lump_steiner.py         # sec 2.5: 17 with a drop, 27 without

# the primary evidence, quoted verbatim in sec 1 and 2
sed -n '804p;805p;806p' ../../../work/039349_18_d53v/wct_pr_039349_18.log
sed -n '4141p;4178p;4179p' ../../../work/039253_8_d53v/wct_pr_039253_8.log
```

Scan payloads: `pdhd/stm_michel_scan/prep-pdvd/smprep-039349_18-c36.json` and
`smprep-039253_8-c62.json`.

---

## 1. `039349_18` cluster 36 — the stopping point is missed and the Michel is labelled muon

The owner's report: *"this event missed the stopping point of the muon, which is
the end of Bragg peak as well as the turning point of the track, it is quite
obvious from the display, but somehow the Michel was overclustered with the
muon."*

### 1.1 It is not blob over-clustering — the PR split it correctly

Cluster 36 is one cluster and the pattern recognition resolved it into 8
segments with a **vertex at (224.66, −276.25, 140.67)** — exactly the Bragg peak
and the turn — plus a separate daughter segment **36018**, 8.96 cm long, from
that vertex to (225.77, −284.21, 141.48), median dQ/dx 25 045 e/cm = **0.52 MIP**,
turning ~94° off the muon. Image charge along it is continuous and all cluster
36; it dips to ~0.1 MIP mid-branch and rises to 1.87 MIP at the tip. That is a
Michel, and it exists in the graph as its own object.

The over-clustering is one stage later, in the **muon chain**:
`chain_role {"36018": 1}` — role 1, muon.

### 1.2 Root cause: `find_first_kink` refuses the stop on charge, not on geometry

`TaggerCheckSTM::find_first_kink` (`clus/src/TaggerCheckSTM.cxx:1570`) is what
marks the stop. On the persisted 228-point trajectory the muon's stop is index
213. The function's own arithmetic there:

| quantity | value at i=213 | gate |
| --- | --- | --- |
| `refl_angle` | 96.0° | > 20 **pass** |
| `ave_angle` | 50.5° | > 10 **pass** |
| `angle3` (start→kink vs kink→end) | 80.2° | > 30 / > 40 **pass** |
| `sum_fQ` (10 pts before) | 1.77 MIP | — |
| `sum_bQ` (10 pts after) | **0.09 MIP** | needs > 0.6 **FAIL** |
| `\|v20\|` (kink → path end) | **8.36 cm** | needs > 10 cm **FAIL** |

Both geometry clauses pass; both charge clauses fail. Clause A (`:1796`) wants MIP-or-more charge on **both** sides of the kink
(`sum_fQ > 0.6 && sum_bQ > 0.6`); clause B relaxes that only for arms longer
than 10 cm (`v10 > 10 cm && v20 > 10 cm`). A Michel is neither — faint and
short. Sweep 2 (`:1901`) repeats `sum_fQ > 0.6 && sum_bQ > 0.6` and fails
identically, so the function returns the no-kink sentinel. The log:

```
persist_stm_fit: cluster 36 stmfit pass=0 status=0 kink=228 exit_L=144.8 left_L=0.0 npts=228
```

`kink == npts` is "no kink found".

This does not hinge on which fit is read. 0.09 MIP is the tagger's own
re-fit, which reads near-zero along the daughter; the PR's independent fit of
36018 gives 0.45 MIP over the same 6 cm — still under the 0.6 bar.

### 1.3 The stop **is** the kink point (measured, not assumed)

Over the 145 `d53v` candidates whose `persist_stm_fit` line reports a real kink
(`kink < npts`), the persisted `tagger_stop_x/y/z` sits **0.000 cm** from
`tagger_fit[kink]` in **145/145** cases, and within 0.5 cm of the trajectory's
last point in **0/145**. So `rec.stop_pt` is the kink-indexed point, and the
no-kink sentinel is what drops the stop onto the trajectory's far end here.

Positive gate on the offline re-implementation (`feedback_reading_a_loop_is_a_hypothesis`):
run over those same 145, `stm_find_first_kink_offline.py` returns the binary's
**exact** kink index in **140/145**; the 5 misses are off by 1–17 points and are
consistent with the offline `dx` approximation plus the fiducial-volume and
dead-region checks that cannot be evaluated outside the job. The negative
result on `039349_18/36` is therefore a measurement, not a reading of the loop.

### 1.4 The cascade

1. No kink ⇒ the stop falls through to the trajectory's far end = the Michel's tip.
2. `CheckSTM_Michel` snaps the stop to the nearest PR vertex
   (`anchor_vertex`, `clus/src/CheckSTM_Michel.cxx:1225`) — 0.18 cm to the
   Michel's tip — and builds the chain as the shortest path entry→stop, which
   therefore runs **through** 36018. The chain-extension loop (`:1298`) only
   ever walks further out, never back.
3. The Bragg test then reads the daughter as the muon's last 3 cm. Reproduced
   exactly against the shipped record: tail (0.5–3 cm) median **28 550**,
   plateau (20–40 cm) median **59 471**, contrast **0.480** against a bar of
   `0.6 × 1.847 = 1.108` ⇒ `no_bragg`; the KS shape test follows ⇒ `shape_flat`;
   **`is_stm = 0`**.
4. `michel_found = 0`, `n_stop_arms = 0` — correctly so: the stop vertex is the
   Michel's own tip and has no arms. The Michel cannot be found because it is
   already inside the muon.

Why the existing guard did not catch it: `vertex_kink_guard` (ON for PDVD,
`protodunevd/pr.jsonnet:442`) is precisely the doc-63 "sharp end-region turn
into a hot prong = vertex, not Bragg" veto, but it is evaluated at
`k = (kink_num >= 0 && kink_num < n) ? kink_num : n-1`. With the sentinel it
measures at index `n−1` — the Michel's tip, 8.4 cm past the real turn.

### 1.5 Counterfactual

Shipped predicates evaluated on measured inputs; not a re-run. Truncate the
chain at the kink vertex and the same windows give tail median **111 463** /
plateau **57 253** = contrast **1.95** against the 1.11 bar ⇒ clears
`no_bragg`. Segment 36018 would then be a stop arm with
`len + far_len = 8.96 ≤ 25 cm`, `mip = 0.52` inside `(0.3, 2.0)` and
`kink 94° ≥ 30°` ⇒ `stm_michel_classify_stop_arm` returns **`kMichel`**.

### 1.6 How common (arm `d53v`, 569 candidates)

| cut | n |
| --- | --- |
| candidates carrying `no_bragg` | 294 |
| … whose last chain segment is Michel-shaped (0.3 < mip < 2.0, ≤ 25 cm) | 88 |
| … and truncating that segment would clear the Bragg bar | 23 |
| … and the junction also turns by ≥ 30° (`michel_min_kink_deg`) | **6** |

The 6: `039349_5/54` (31.7°), `039252_16/110` (30.1°), `039349_18/36` (94.1°),
`039253_10/77` (31.7°), `039349_10/54` (146.2°), `039349_63/47` (88.8°). The
other 17 are collinear (turn < 20°) — the tagger overshooting along a straight
track, a different problem.

**This 6 is a lower bound on the defect, not a count of swallowed Michels.**
The census only scans candidates that already carry `no_bragg`, so a Michel
absorbed into the chain that did not cost the verdict is invisible to it. What
was measured is "6 candidates where a swallowed Michel cost the `is_stm`
verdict".

### 1.7 Blast radius of the two possible intervention points

`find_first_kink` lives in `TaggerCheckSTM`, which **SBND binds as well** as
both ProtoDUNEs (`cfg/pgrapher/experiment/sbnd/{clus,particle_dataset,
sbnd_track_fitting.json,wct-pr-perevt,wct-clus-matching-perevt}`).
`CheckSTM_Michel` is bound by `pdhd/pr.jsonnet` and `protodunevd/pr.jsonnet`
only. A stop **walk-back local to `CheckSTM_Michel`** — when the snapped stop
vertex is terminal, its incoming chain segment is Michel-shaped
(`stm_michel_classify_stop_arm` already holds the predicate) and it turns by at
least `michel_min_kink_deg` from the preceding chain segment, retreat the stop
to that segment's other vertex and re-judge — therefore carries **zero SBND
exposure**, where loosening the shared charge gate does not. The 23-row table
of §1.6 is the ready-made pricing set. Naming the lane only; no constant is
proposed.

---

## 2. `039253_8` cluster 62 — in-bundle charge near the stop with no fitted trajectory

The owner's report: *"there is a sizable piece that seems to be detached to the
main cluster, or it is contacted, but not covered by the Michel electron? This
piece is not in the segment list."* Then: *"do you know why the fit is short of
this part?"*

### 2.1 What the piece is

It is **cluster 62 itself** — the main cluster, in the muon's own Q-L bundle
(flash 124, t0 2563.78 µs) — not a companion. It is **contacted, not detached**:
0.66 cm from the nearest other C62 blob, ordinary blob spacing, with a 39-blob /
3.6 × 10⁵ e⁻ bridge back to the stop. It spans 3–15 cm past the stop and 3–15 cm
transverse: 78 blobs, 9.5 × 10⁵ e⁻.

It has **no row in the object table** because the table has exactly two row
types — `S` = a fitted PR segment, `C` = a whole near cluster the PR fitted
nothing for (`unfitted_near` skips any cluster with `segs`). Unfitted charge
*inside* a fitted cluster falls between them. That is a structural hole in the
display, reported here, not fixed.

Against the raw tree rather than the payload: within 3 cm of the piece
`T_rec_charge` holds 8 rows (7 of `S62001` plus one vertex); **63 of the 78
blobs** have no fit row within 3 cm, median distance 6.7 cm.

The stage that stops short is the **trajectory fit**, not imaging or Steiner.
By Bee layer, inside the clump: `steiner_graph` 66 points and
`steiner_terminals` 13 (all cluster 62), `shower_track`/`stm` 63 points, but
**zero** `track_fit`/`stm_fit` points within 3 cm (nearest 4.11 cm).

The physics carries the same hole: `michel_len` 4.22 cm, `michel_ke_best`
17.96 MeV, `n_michel_segs` 1, while `dots_charge_unfit = 0.0` and
`n_dot_clusters_unfit = 0` with 129 blobs / 1.3 × 10⁶ e⁻ untraced within 20 cm —
the unfitted-charge path counts whole unfitted **companion clusters** only.

### 2.2 Root cause: `pr54 isolated-residual drop`

```
wct_pr_039253_8.log:4141  pr30 P2 local-PCA endpoint moved 9.794 cm:
                          (276.59,25.56,134.55) -> (272.15,18.32,129.67) cluster 62
wct_pr_039253_8.log:4178  pr55 do_rough_path: cluster 62 ...
                          first=(2748.1,200.9,1312.0) last=(2765.9,258.5,1350.6)
wct_pr_039253_8.log:4179  pr54 isolated-residual drop: cluster 62 n_points=13
                          length=8.19 cm dir_mag=7.16 cm
                          v1=(274.8,20.1,131.2) v2=(276.6,25.9,135.1) cm
```

`v1→v2` is the clump (measured bbox x 272.4–276.6, y 20.3–26.4, z 132.0–135.1)
and `n_points=13` is its 13 Steiner terminals. The sequence:

1. **The seed endpoint was pulled off it.** `pr30 P2` local-PCA refinement moved
   the cluster's extreme endpoint 9.794 cm, from the clump's far tip back onto
   the track end, so the main rough path never ran through the clump.
2. **It survived as a residual, and `find_other_segments` did fit it** —
   `pr55 do_rough_path` traced exactly that span immediately before the drop.
3. **It could not be attached to the existing graph** (`!flag_parallel`), so it
   fell to the keep-or-discard test.
4. **`other_seg_keep_isolated_ok` refused it**
   (`clus/src/NeutrinoOtherSegments.cxx:36`): keep if
   `n_points ≥ min_points AND length ≥ min_length`, **or** `length ≥ len_admit`.
   PDVD runs `other_seg_keep_isolated = true`, `min_points = null → 25`,
   `min_length = null → 3 cm`, `len_admit = 30 cm`
   (`pdvd/wct-pr-perevt.jsonnet:3335, 3360`). This residual is **13 points,
   8.19 cm** — too few terminals for the count floor, too short for the length
   admit. Both fail, so `remove_vertex(graph, v1); remove_vertex(graph, v2);`
   runs and the segment is never added.

Nothing failed in imaging, clustering or Steiner: the fit was built and then
deliberately discarded by a noise floor.

### 2.3 The floors' blind band is exactly Michel scale

Arm `d53v`: **363 residuals dropped, 38 kept**. Every dropped residual is below
**both** floors — `n_points` p50 5, p90 14, **max 24**; length p50 5.3 cm,
p90 12.2, **max 25.0 cm**. Moving either floor alone keeps none of them
(`n_points ≥ 25`: 0; `length ≥ 30 cm`: 0). The kept ones are the ≥ 30 cm tracks
admitted by `len_admit`.

The drop population lives entirely in the 2–24 terminal / 0–25 cm band, which is
the size of a Michel fragment or a delta. Note that the `keep-isolated` log line
prints the **post-refit** length while the drop line prints the **pre-test**
length, so the two length distributions are not directly comparable.

Those floors come from SBND — `other_seg_keep_isolated` is doc `sbnd_xin/pr/54`
("missing gammas"), `len_admit = 30` is doc `pr/102` P1b — and PDVD inherits
them verbatim. They were never tuned against a stopping-muon Michel, and they
carry no notion of *where* the residual sits: a 13-terminal residual 8 cm off a
muon stop is treated exactly like a 13-terminal residual in the middle of
nowhere.

### 2.4 How common (arm `d53v`, 569 candidates)

Unfitted share of in-bundle charge within 20 cm of the stop: **p50 0 %**,
p90 8 %, mean 3 % — so this is not a generic artifact. But **44 of 569 (8 %)**
carry a single unfitted lump of ≥ 20 blobs **and** ≥ 2 × 10⁵ e⁻. The worst:
`039253_2/77` (207 blobs, 2.56 × 10⁶ e⁻), `039252_8/93` (187, 2.21 × 10⁶),
`039349_33/45` (138, 1.71 × 10⁶), `039349_81/54` (144, 1.63 × 10⁶).
`039253_8/62` ranks ~19th. On PDHD the same census gives 68/303 (22 %).

### 2.5 Honest attribution — 17 of the 44, and a second unverified mechanism

Only **17 of the 44** lumps contain a `pr54` drop inside them. The other **27
emit no drop line at all**, yet the Steiner stage clearly has the points —
`039349_81/54` holds **423** Steiner graph points and **117** terminals inside
its lump.

Those terminals must therefore have been marked "already covered" in **step 1**
of `find_other_segments`, which credits a point when its 3-D distance to an
existing segment is under `search_range`, **or** all three of its 2-D
projections are within `0.8 × search_range`, **or** it falls in dead channels
(`clus/src/NeutrinoOtherSegments.cxx:76-140`). Charge several cm away in 3-D can
be declared covered by its own shadow. **This is the leading hypothesis for the
remaining 27 and it is NOT verified** — confirming it needs the per-group
`pr67 fos` instrumentation turned on for a re-run (it emits zero lines in the
current arm).

### 2.6 Lane

Do not touch the shared floors — SBND binds the same knob and a retune moves it.
The measurable round is a **new, default-OFF, stop-local admission**: keep an
isolated residual regardless of terminal count when it sits within ~20 cm of a
stopping-muon endpoint, priced on both ProtoDUNEs (`is_stm` flips, the
"0 unclaimed" census, and what it admits away from stops). The cheap probe
before any code: over the arm, how many of the 363 drops are within 20 cm of an
`is_stm` stop, and what a `d_stop`-gated floor would admit. Separately, one
re-run with `pr67 fos` on would settle the other 27.

---

## 3. What is open

| # | symptom | mechanism | verified | exposure of the fix lane |
| --- | --- | --- | --- | --- |
| 1 | stop missed, Michel labelled muon (`039349_18/36`) | `find_first_kink` charge clauses reject a faint short daughter; stop falls to the trajectory end | yes (§1.2, §1.3) | `CheckSTM_Michel` walk-back = PDHD+PDVD only |
| 2a | in-bundle charge near the stop with no fit (`039253_8/62`, 17 of 44) | `pr54 isolated-residual drop`; both `other_seg_keep_isolated_ok` floors fail | yes (§2.2, §2.3) | stop-local admission knob, both ProtoDUNEs |
| 2b | same symptom, no drop line (27 of 44) | `find_other_segments` step-1 2-D / dead-channel "already covered" tagging | **no** | unknown until `pr67 fos` is run |
| 3 | unfitted charge inside a fitted cluster has no object-table row | the table has only `S` (fitted segment) and `C` (wholly unfitted near cluster) rows | yes (§2.1) | display only (`prep_stm_michel_scan.py`) |
