# doc pdvd/52 — how `CheckSTM_Michel` finds the muon, the Michel, and the capture gamma

**Status: information only.** No code, no config, no arm, no new measurement.
This is a walkthrough of the component as it stands at toolkit `055c0e23`
(`clus,cfg/protodunevd,cfg/pdhd: reconstruct the muon-capture gamma at the STM
stop ...`, doc pdvd/51), written to answer six questions:

1. how the muon is identified,
2. how the Michel electron is identified,
3. how the Michel's energy is calculated,
4. if the muon has delta rays, how the cosmic-muon segments are grouped,
5. how a connected Michel is told from nearby isolated gamma points,
6. how the Michel electron is clustered together,
7. how the particle flow is formed (added on request after the first draft).

**Every number quoted here was measured by another doc, and is attributed at
the point of use.** Nothing in this file is a new result; there is no Repro
block because there is nothing to reproduce. To re-derive any figure, go to the
doc named beside it.

**Why this file sits in `nf_sp_img_clus/` next to 48 and 51.** Doc pdvd/25 is
the *chain-level* design (which components run, in what order, on which
detector). Docs pdvd/48 and pdvd/51 and pdhd/03, /13-/17 are the *internals* of
`CheckSTM_Michel` itself. This is an internals doc, so it goes with them.

## Source files

| file | what lives there |
|---|---|
| `clus/src/CheckSTM_Michel.cxx` | the component: candidate loop, chain walk, arm handling, Michel/gamma assembly, energies, persistence |
| `clus/src/StmMichelFunctions.cxx` | the graph-only predicates, so they are doctestable on synthetic graphs: profile, Bragg contrast, arm classification, the two gamma predicates |
| `clus/src/TaggerCheckSTM.cxx` | **upstream**: sets `Flags::STM` and writes the `stm_pass` / `stm_fit` point clouds this component anchors on |
| `clus/src/PRShower.cxx` | `Shower::complete_structure_with_start_segment` — the flood-fill that gathers the Michel |
| `clus/src/MultiAlgBlobClustering.cxx` | `fill_bee_pf_tree` — **the renderer**: turns the graph + showers into the `mc.json` particle flow (§7) |
| `pdvd/wct-pr-perevt.jsonnet`, `pdhd/wct-pr-perevt.jsonnet` | the `stm_michel_knobs` bag (§8) |
| `cfg/pgrapher/experiment/{protodunevd,pdhd}/pr.jsonnet` | binds `check_stm_michel`; the particle-flow display config (§7.5) |

---

## 1. Identifying the muon

### 1.1 The component does not find the muon — it inherits it

`CheckSTM_Michel` never searches for a stopping muon. It runs **after**
`tagger_check_stm` and reconstructs what that tagger already tagged. The
candidate filter is four lines (`visit()`):

```
main_cluster flag set        (the Q-L matched main cluster of a bundle)
NOT Flags::TGM               (a through-going muon is never a stopping one)
Flags::STM                   (require_stm_flag, default true)
```

sorted by `ident()` and capped at `max_candidates` (8) so the cost is bounded.
The sort is by stable id, not pointer, so the order is deterministic.

`Flags::STM` is set in `TaggerCheckSTM.cxx:620`, when
`check_stm_conditions` (`:3530`) returns true and TGM is not already set. That
function's own gate is topological before it is calorimetric — its exit log
lines name the branches directly:

- **not fully contained** — a cluster entirely inside the fiducial volume exits
  at "Mid Point A";
- **exactly one boundary exit point** — "Mid Point C" rejects anything with a
  different count (0 exits ⇒ contained, 2 ⇒ through-going);
- **no disqualifying mid-track kink** at that single exit — "Mid Point B";
- then two rounds of trajectory fitting and `eval_stm_core`, which is the
  actual Bragg/dQ-dx test against the muon `*DeDx` template.

So the muon that reaches this component is, by construction, *a single-ended
track that enters through a detector boundary and stops inside*. The tagger's
criteria are outside this doc's scope — see doc pdvd/48 and pdhd/03, and
`pdhd/docs/stm-tagger-chain.md`.

### 1.2 The anchor: entry point and stop point (`read_stm_anchor`, `:723`)

The tagger persists two cluster point clouds when `save_stm_fit` is on:

- **`stm_pass`** — one row per evaluation pass, with `pass`, `status`, `kink_num`;
- **`stm_fit`** — the fitted trajectory rows, with `x, y, z, L, pass`.

The component picks the **lowest-numbered pass whose `status == 0`** (the
accepted one). Within that pass's rows:

- **entry** = the row with **minimum `L`** — the tagger's `L = 0` end, which is
  the boundary crossing;
- **stop** = the **`kink_num`-th row** of that pass, falling back to the last
  row when `kink_num` is out of range.

If either point cloud is missing or no pass has `status == 0`, the candidate is
recorded with `R_NO_CHAIN` and nothing else is attempted. That is a real
operating condition, not a defect: it is what a config with `save_stm_fit` off
upstream produces, and the warning log says so.

**The particle flow is rooted at the ENTRY point**, not at the stop. That is the
opposite of the neutrino chain's convention (where the root is the interaction
vertex) and it is deliberate: for a cosmic the entry is where the particle came
from, so `entry_v` gets `VertexFlags::kNeutrinoVertex` and
`tf->set_main_vertex(entry_v)`, and `examine_direction` re-orients every reached
segment *outward from the entry* with `flag_final = true` so no earlier
direction survives.

### 1.3 Snapping the anchor onto the PR graph — deliberately asymmetric

The tagger's two points come from its own single-track fit; the PR graph this
component builds has its own vertices. `anchor_vertex` snaps each to the nearest
graph vertex within a tolerance, and **the two tolerances differ on purpose**:

| | knob | default |
|---|---|---|
| entry | `entry_snap_tol_cm` | **5.0** cm (loose) |
| stop | `stop_snap_tol_cm` | **2.0** cm (tight) |

The code's reason: the entry sits at a detector boundary where the graph's own
end vertex is typically a few cm away, and splitting there would leave a
sub-centimetre stub *beyond* the entry — smoke event 039252/2 cluster 86 produced
a 0.8 cm "pi+" leaf that way. The stop is snapped tightly because **the Michel
search keys on it**: every radius in §5 and §6 is measured from `rec.stop_pt`.

### 1.4 The muon chain is a shortest path

```
chain = stm_michel_shortest_chain(g, entry_v, stop_v)
```

a **Dijkstra route through the PR graph from entry to stop, weighted by
`segment_track_length`** — shortest in centimetres of track, not in number of
segments. This one choice is what answers question 4 — see §4.1. (Ties are
broken by graph index through an index-ordered frontier, so the walk is
deterministic and carries no pointer ordering.)

### 1.5 When the stop does not match (`R_STOP_UNMATCHED`)

If no graph vertex is within 2 cm of the tagger's stop, or the stop is
unreachable from the entry, the muon is taken as the route to **the vertex of the main cluster at the
greatest shortest-path distance from the entry** (`stm_michel_farthest_vertex`,
the same Dijkstra run to exhaustion with the predicate
`v->cluster() == main`), and `R_STOP_UNMATCHED` is recorded. The documented cause
(doc pdhd/03) is that the tagger's single-track fit sometimes bridges 20–40 cm
into a *detached fragment*, so the stop it recorded is in another graph
component.

Doc pdvd/48 walked greedily with `find_cont_muon_segment` instead; on PDHD that
stopped at the first junction and gave 1-segment chains on 8 of 13 such cases.
The farthest-vertex route replaced it.

A consequence worth knowing when reading the tree: `stop_dis` (the distance from
the tagger's stop to the one actually used) can be **hundreds of cm** — PDHD
029107_17 cluster 33 records 266.3 cm. That is why the companion admission test
is re-applied against the final stop in §5.

### 1.6 Walking past the tagger's stop (`stop_extend_max`, `michel_guards_stop`)

Doc pdhd/03 §6 found the tagger's stop is often *short* of the muon's real end,
and doc pdvd/42 §4.4 measured that leftover on PDVD as a collinear ~0.9 MIP
segment on **26 %** of passes. So the chain is extended: up to
`stop_extend_max` (3 in production) times, if the stop vertex has a
**continuation** arm (§2.2), the chain absorbs it and the stop moves to its far
vertex.

Two brakes:

- **`michel_guards_stop`** (true in production): if any arm at the stop is
  classified `kMichel`, or the Bragg rise is *already* present in the current
  chain's profile, the walk stops — a Michel or a confirmed Bragg peak says the
  muon stopped **here**.
- **`absorb_bragg_stub`** (**not** set on either ProtoDUNE): a short collinear
  arm *hotter* than a MIP is the muon's own Bragg stub that the partition split
  off, and would be absorbed regardless of the shower flag. It is off because on
  PDHD it turned a clean STM into `no_bragg` (doc pdhd/03 §6.8).

### 1.7 The verdict is separate from the reconstruction

Every candidate is reconstructed and persisted. A "reject" is a **bit**, not a
skip. The bits set on the muon side:

| bit | meaning |
|---|---|
| `R_NO_CHAIN` | no anchor, or no chain from entry to stop |
| `R_SHORT` | fewer than `min_chain_points` (10) profile points |
| `R_STOP_UNMATCHED` | §1.5 |
| `R_PROFILE_SPARSE` | fewer than 3 live points in a window — *cannot judge*, not *fails* |
| `R_NO_BRAGG` | tail/plateau contrast below `bragg_contrast_min` × expected |
| `R_PLATEAU_OFF_MIP` | plateau median outside [0.6, 1.6] × MIP |
| `R_SHAPE_FLAT` | KS says flat beats the muon template |
| `R_NOT_MUON_PID` | `do_track_comp` template PID (see `pid_mode`) |
| `R_STOP_INTO_DEAD` | the visible end walks into a dead region |
| `R_CONTINUATION` | an un-absorbed collinear MIP arm past the stop |
| `R_VERTEX_HADRON` | a long, hot arm at an interior vertex (§4.2) |
| `R_STOP_NEAR_BOUNDARY` | the stop is outside the fiducial inset |
| `R_CLUSTER_NOT_TRACK` | too few of the cluster's points lie on the reconstructed track |

`is_stm` is exactly `reject_bits == 0`. **Michel presence is deliberately NOT a
criterion** (`StmMichelFunctions.h:250-252`) — a μ⁻ that stops in argon is
captured more often than it decays, so requiring a Michel would throw away the
captured half. That is the same physics §5.4 uses as its validation.

The three shape metrics all read the **live** profile — points below
`profile_min_dqdx_frac` (0.15) × MIP are cells the fit could not read (dead
channels, APA edges, PDHD wrapped-wire ambiguity) and carry no particle
information (doc pdhd/03 §5).

---

## 2. Identifying the Michel electron

### 2.1 The Michel is an *arm at the stop vertex*

Once the chain ends at `stop_v`, every graph edge out of that vertex which is
not the last chain segment is measured and classified by
`stm_michel_classify_stop_arm` (`StmMichelFunctions.cxx:279`). `measure_arm`
collects four properties:

| property | how |
|---|---|
| `len` | `segment_track_length(arm)` |
| `mip` | `segment_median_dQ_dx(arm) / mip_dqdx_median` — charge in MIP units |
| `kink_deg` | `segment_pair_kink_deg(last_muon, arm, vertex_point)` — the turn |
| `far_len` | subtree track length beyond the arm's far vertex, capped; 0 if terminal |
| `shower_like` | `kShowerTrajectory` or `kShowerTopology` flag, or PID \|pdg\| == 11 |

### 2.2 Order matters: **continuation is tested first**

```
CONTINUATION   kink < 20 deg  AND  len > 3 cm  AND  0.7 <= mip <= 1.3
               -> the muon is still going; NOT a Michel
MICHEL         len + far_len <= 25 cm  AND  0.3 < mip < 2.0
               AND ( shower-flagged with kink >= 15 deg   OR   kink >= 30 deg )
OTHER          everything else
```

The continuation clause returns *before* the Michel clause is evaluated, so a
collinear MIP-like arm can never be called a Michel however it is flagged. **The
shower flag is not consulted in the continuation test at all** — doc pdhd/03 §6
found `kShowerTopology` stamped on 20–24 cm arms at 2–3° and 1.2–1.3 MIP
(029107/21 cluster 116, 029107/28 cluster 35), which doc pdvd/48's
`!shower_like` guard then handed to the Michel clause as 43–57 MeV "electrons".

### 2.3 The two mistakes that shaped this predicate

Both are recorded in the code because both were made:

- **Charge alone is not enough.** A dQ/dx-only clause calls the PDVD collinear
  leftover (~0.9 MIP, doc pdvd/42 §4.4) a Michel: in the first census **a fifth**
  of the "Michels" had kink < 30°. Hence the mandatory turn.
- **The shower flag alone is not enough.** It admitted the muon's own last 5 cm
  — a collinear 1.6 MIP stub at 4° (029107/1 cluster 113) — as a Michel. Hence
  `michel_shower_min_kink_deg` (15 in production): a shower-flagged arm whose
  kink is *measurable* must still turn by at least that much.

So a Michel must be **a turn, of MIP-or-below charge, of Michel-sized reach**.
`len + far_len` rather than `len` is what stops a 25 cm arm leading into 200 cm
of further track from qualifying.

### 2.4 If nothing attaches at the stop

The 3-D clustering routinely breaks the Michel off the muon. Three connection
types are recorded in `michel_conn_type`, and `michel_found` is simply
`conn_type > 0`:

| type | meaning | seed |
|---|---|---|
| **1** | **attached** — a `kMichel` arm leaves the stop vertex | longest such arm; `michel_dis_cm = 0` |
| **2** | **bridged** — nothing attached, but an admitted companion cluster has a fitted piece near the stop | the **nearest** piece; `michel_dis_cm` = its gap |
| **3** | **charge only** — an admitted companion the fitter produced no segment for | none; `michel_seg_id` stays −1 |

Through doc pdhd/14 `michel_found` was set on the attached path only, so 33 PDHD
/ 41 PDVD reconstructed Michels reported 0 — about **30 %** of them (doc pdhd/13
defect D1). The old meaning is exactly `michel_found && michel_conn_type == 1`.

---

## 3. How the Michel's energy is calculated

### 3.1 The ordering *is* the algorithm: assemble first, energise once

This is the part most likely to be got wrong by a reader, because it was got
wrong in the code. Through doc pdhd/14 the attached path called
`calculate_kinematics` **before** the companion-piece loop and only re-ran it
for `conn_type 2` — so a piece the loop added to the very same shower never
reached the energy. PDVD 039252_15 cluster 91 reported **16.2 MeV for a 29.2 MeV
Michel** whose second piece sits 4.33 cm past the arm's tip at 20°, and the same
16 MeV is what `mc.json`'s `mu- -> e-` node showed. Measured on the d14 arms:
9 PDHD / 17 PDVD candidates affected, missing fraction **median 22.5 % / 12.2 %,
max 62 % / 65 %**.

The current order is:

```
1. seed the Shower on the attached arm (or the nearest bridged piece)
2. complete_structure_with_start_segment      -> gathers the in-cluster pieces (§6)
3. michel_ke_core = get_kine_dQdx()           -- the CORE alone, for the record
4. add_segment() for every admitted companion piece
5. dots_ke_unfit  = charge -> energy for companions with no fitted segment
6. calculate_shower_kinematics(showers, ...)  -- ONE call, all objects
7. michel_ke_dqdx  = get_kine_dQdx()
   michel_ke_charge = get_kine_charge()
8. michel_ke_best  = michel_ke_dqdx + dots_ke_unfit
9. set_kine_best(michel_ke_best) stamped back onto the Shower
```

`michel_ke_core` is kept precisely because it *is* what `michel_ke_dqdx` meant
through doc pdhd/14 — so the two are comparable across the fix.

Step 6 uses `PatternAlgorithms::calculate_shower_kinematics`
(`NeutrinoEnergyReco.cxx:303`), the production chain's own entry point, rather
than a local recipe. That is the owner's standing rule from doc pdhd/14: *every
number in this tree is the chain's, not this file's.*

### 3.2 The charge → energy conversion for unfitted pieces

An admitted companion cluster the fitter produced no segment for has **no dx**,
so there is no dQ/dx to invert. Only its charge can be read.
`stm_michel_charge_to_energy_model` (doc pdhd/17 §9) inverts the recombination
model this component is already holding at an **assumed** dE/dx
(`michel_unfit_dedx = 2.1` MeV/cm, the same MIP pivot the PowerBox fit uses):

```
dQ_model = model(dE, dx)  for dE = 2.1 MeV/cm x 1 cm
energy   = dQ_electrons * dE / dQ_model
```

The predecessor was a flat pair `charge / 0.7 / 0.95 * 23.6 eV`
(`michel_unfit_recom` × `michel_unfit_fudge` × W). Those two constants and the
component's own dQ/dx→dE/dx inverse are **two carriers of one quantity**, and
doc pdhd/16 moved only the second, leaving them 20 % (PDVD) / 16 % (PDHD) apart
at MIP where they had been within 5 %. Deriving one from the other cannot drift
again.

**This is MIP-equivalent and unavoidably so.** Because quenching rises with
dE/dx, a deposit *denser* than MIP needs more MeV per electron than this gives,
so the assumption **under-estimates a dense deposit** (4.13e-5 MeV/e at
2.1 MeV/cm against 4.96e-5 at 5 MeV/cm on PDHD).

What it moved when it landed: on PDVD, **nothing** — `dots_charge_unfit` is 0 on
all 160 `michel_found` candidates of the d16vnu arm. On PDHD, 17 of 124, by
×1.1638, and on all 17 `dots_ke_unfit` *is* `michel_ke_best`.

### 3.3 `michel_ke_best` is deliberately **not** `Shower::get_kine_best()`

The owner's rule (doc pdhd/15 §1): *"there should be range, dQ/dx for the track.
For the dots etc ... either dQ/dx → dE/dx or the charge conversion."* So:

```
michel_ke_best = michel_ke_dqdx  (everything fitted)
               + dots_ke_unfit   (the charge term for what is not)
```

`Shower::get_kine_best()` is **not** used because for a shower-flagged or
graph-disconnected object it falls back to `kenergy_charge`, computed with the
**shower** recombination pair, and overshoots the chain's own dQ/dx by **~1.66×**
(doc pdhd/15 §6).

### 3.4 Why the energy is stamped *back* onto the Shower

`Shower::kenergy_best` is 0 whenever a member is graph-disconnected
(`PRShower.cxx:1855`) — which is **every bridged Michel and every attached one
that gathered a companion piece**. `get_kine_best()` then falls back to
`kenergy_charge`, which is 0 on this path. `fill_bee_pf_tree` prunes an EM leaf
whose ke is below `em_ke_min` (`MultiAlgBlobClustering.cxx:2087` — the
comment in `CheckSTM_Michel.cxx` still cites the pre-drift `:2082`), so leaving it
at 0 **deletes the e- node from `mc.json`** — 039252_15 cluster 91 lost the
daughter it had had since doc pdvd/48. `set_kine_best(michel_ke_best)` is the
fix, and the module's own object energy is the right value to carry. It does a
second job as the node's printed label — see §7.5.

### 3.5 The calibration the Michel inherits — read this before quoting a number

`michel_ke_dqdx` is a dQ/dx → dE/dx inversion through
`PowerBoxRecombination` at `p = 1` with a fitted constant `C` (0.7941 PDVD /
0.8120 PDHD, doc pdhd/16). **`C` was fitted against range on muon TRACKS**, and
every Michel energy inherits it as an **extrapolation** — it is doc pdhd/16's own
listed open item. `C` is a combined gain × lifetime × recombination constant, not
a recombination measurement.

There is one measured cross-check worth knowing: PDVD's largest Michel object is
**76.8 MeV**, above the 52.8 MeV Michel endpoint (doc pdvd/51). Whether that is
the calibration, the assembly, or a genuinely mis-assembled object is **not
settled**, and it is the reason doc pdvd/51 refused to reach the capture gammas
by widening the Michel radius (§5.1).

### 3.6 The NaN guard

A coincident pair of fit points gives `dx == 0`; `cal_kine_dQdx` then evaluates
the Box model at 0/0 and the NaN survives every clamp into the sum, so **one such
point zeroes the whole object's energy**. Two defences: `dqdx_skip_zero_dx` is
turned on for this component's `PatternAlgorithms` (6 of 280 objects on the d15
arms met one), and every persisted energy is checked with `std::isfinite` and
zeroed with a warning if not. A NaN passes no gate and fails every one silently —
PDVD 039349_3 cluster 26 persisted `michel_ke_best = NaN` through doc pdhd/14.

---

## 4. Delta rays, and how the cosmic-muon segments are grouped

### 4.1 The grouping is a *shortest path*, so delta rays are excluded by construction

This is the whole answer, and it is a one-line consequence of §1.4. The PR
partition breaks a real cosmic muon into many segments joined at vertices, and a
delta ray appears as an extra edge at one of those interior vertices. Because the
muon is defined as `stm_michel_shortest_chain(entry_v, stop_v)` and the edge
weight **is track length**, a delta arm is **off the path**: going out along it
and back adds twice its length and reaches no new vertex, so no shortest route
uses it. There is no delta-ray *rejection* step in the chain walk; there is
nothing to reject.

The corollary is worth stating because it bounds the method: this works for a
delta ray, which is a *spur*. It would not by itself protect against a delta ray
that happened to rejoin the muon further along and offer a genuinely shorter
route — that topology is not something the chain walk defends against, and the
component relies on the PR partition not producing it.

`stm_michel_chain_vertices` then returns the vertex sequence, and the component
asserts `chain_vtxs.size() == chain.size() + 1`; if not, the chain is discarded
with `R_NO_CHAIN` rather than reconstructed from an inconsistent walk.

Every chain segment is stamped `pdg = 13` and has its shower flags
(`kShowerTrajectory`, `kShowerTopology`) explicitly **cleared** — the partition's
own track/shower call does not survive onto the muon.

### 4.2 The arms that hang off the chain are classified, not ignored

For every interior vertex `chain_vtxs[1 .. n-1]`, each edge that is neither the
incoming nor the outgoing chain segment goes to
`stm_michel_classify_chain_arm` (`StmMichelFunctions.cxx:317`):

```
DELTA    len <= 8 cm  AND  far_len <= 8 cm  AND  terminal
HADRON   len >  8 cm  AND  mip > 1.4        -> sets R_VERTEX_HADRON
OTHER    everything else                     -> counted only (n_body_other)
```

A `kDelta` arm is stamped `pdg = 11`, counted in `n_delta`, summed into
`delta_len`, and its points enter the point cloud with **role 2**. It is
*attributed*, not discarded — but note it does **not** enter `muon_ke_dqdx`,
which sums the chain only. The delta ray's energy came from the muon, so a
strict energy budget would add it back; today it is available separately
(`n_delta`, `delta_len`, role-2 points) and not folded in.

`kHadron` is the interesting one: a long, hot arm at an interior vertex is not a
delta ray, and its presence sets a reject bit, because a stopping muon should not
have one.

### 4.3 The profile re-orients each segment (why a multi-segment chain still gives a monotone axis)

`stm_michel_profile` (`StmMichelFunctions.cxx:128`) walks the chain from the
entry vertex. For each segment it compares the distance from the **current
vertex** to `fits.front().point` and `fits.back().point`, and **iterates the fit
rows in whichever direction starts nearest the vertex it arrived at**. Segment
storage order is not walk order, so without this a chain of several segments
would produce a sawtooth in `L`.

Points with `dx <= 0` or `dQ < 0` are skipped. `L` accumulates the *3-D distance
between consecutive kept points*, so it is a path length rather than a sum of
segment lengths. Residual range is `rr[i] = L_total - L[i]`, which is what the
Bragg and PID metrics bin in.

### 4.4 The energy consequence of the grouping — the asymmetry that matters

```
muon_ke_range = cal_kine_range(rec.muon_len, 13, ...)   -- ONCE, on the chain total
muon_ke_dqdx  = sum over segments of segment_cal_kine_dQdx(s)
```

**Range is taken on the chain's total length, not per segment, because
`cal_kine_range` is not additive** — the range–energy relation is non-linear, so
summing per-segment range energies over a chain the stop-extension walked would
be wrong. dQ/dx **is** additive and is summed segment by segment. Getting this
backwards is the classic way to break a multi-segment track's energy, and the
two estimators are treated differently for that reason alone.

`muon_ke_best` picks between them with the same ≥ 4 cm rule
`Shower::calculate_kinematics` uses (`PRSegmentFunctions.cxx:2900`): dQ/dx below
4 cm, range above. In practice every STM muon is above.

A third, charge-free estimator exists: **`muon_ke_mcs`** from
`Mcs::MuonMCS::run()` on the profile points (doc pdhd/16), with the cathode band
excised (doc pdhd/16 §9). It reads 6–10 % below CSDA range on all three
detectors and `muon_ke_best` stays range — reported, not tuned.

---

## 5. A connected Michel vs nearby isolated gamma points

This is doc pdvd/51's subject, and it is the sharpest discriminator in the
component. The short answer: **two concentric radii around the stop, a
compactness cap, an energy window, and a body exclusion — and the body exclusion
is what actually does the work.**

### 5.1 Two radii, and they share an edge

```
        stop
         |<--- 15 cm --->|<-------- 35 cm -------->|
         |    MICHEL     |        GAMMA RING       |   nothing
              (dots)          (capture gammas)
```

- **Michel admission**: a companion cluster whose closest approach to the stop is
  ≤ `michel_dot_radius_cm` = **15 cm**.
- **Gamma ring**: `stm_michel_stop_gamma_ring` (`StmMichelFunctions.cxx:334`)
  requires `d_stop > 15 cm` **and** `d_stop <= stop_gamma_radius_cm` = **35 cm**
  **and** `cluster length <= stop_gamma_max_len_cm` = **10 cm**.

The ring's inner edge **is** the Michel's radius, so the two are mutually
exclusive by construction, and a cluster the Michel already owns is additionally
excluded by id. **Note the coupling: widening `michel_dot_radius_cm` moves both
boundaries at once.** That is exactly why doc pdvd/51 gave the gamma its own ring
instead of widening the Michel radius — PDVD's 76.8 MeV object (§3.5) is already
the one the owner is scanning, and handing it more distant charge makes precisely
that item worse.

The 35 cm is measured, not chosen: the same-bundle stop-anchored blob density
falls from 1.66 to 0.60 per candidate per 1e6 cm³ between the 20–30 and 30–40 cm
shells, against a foreign-bundle control that is **flat at ~0.6** — and the mu⁻
anti-correlation peaks at 2.05 there and collapses to 1.41 by 45 cm.

### 5.2 Compactness and energy — "a blob, not another cosmic"

A gamma is neutral: it leaves no track from the stop, travels a couple of Compton
mean free paths, and deposits a compact blob at an arbitrary angle. So:

- `length <= 10 cm` — a 30 cm object past a stop is another cosmic in the same
  bundle. 039252_0 cluster 77 has six same-bundle neighbours at 26.5 … 168.9 cm
  and **only the first is a candidate**: "same Q-L bundle" alone is not a
  discriminator; the ring and the cap are.
- `stm_michel_stop_gamma_energy` (`:345`): KE ∈ **[0.2, 20]** MeV, and at most
  `stop_gamma_max_n` = 8 objects, taken nearest-first.

Acceptance is a **separate stage from admission**, because the energy only exists
after the fitter has run. A candidate rejected on energy is dropped from the
object list, not from the fitter — its charge stays in the 2-D maps.

### 5.3 The body exclusion — the actual discriminator, and both its properties matter

A companion in the ring is rejected if it is **closer to something already
claimed than it is to the stop**:

```
d_body_cl = min over claimed points of (closest approach of THIS CLUSTER to that point)
if (d_body_cl < d_stop) reject
```

Two properties, each of which was got wrong once (doc pdvd/51 §6.5):

1. **At CLUSTER level**, not per fitted segment.
2. **Against everything the candidate has already claimed** — the muon chain
   (role 1), the deltas (role 2), and **the whole Michel object** (roles 3–4) —
   not against the muon profile alone. The set is snapshotted **before** the loop
   so one accepted gamma cannot exclude the next.

Points within `dot_body_exclusion_cm` (5 cm) of the stop are removed from the
body set — that is the one place a real daughter is allowed to start.

**Why property 2 is load-bearing.** With either mistake, the component's one
physics test reads **0.44** on PDVD `d51gv`; with both fixed it reads **1.64**,
against **2.05** for the same predicate measured offline. The mechanism: 29 of
the 30 spurious admissions land on candidates that **also** have a Michel — they
are **Michel satellites**. A Michel showers, its outlying blobs sit past the
stop, in the bundle, compact, and pass every other test — and the muon profile
cannot see them, because *an attached Michel's arms are not in the profile*.

### 5.4 The physics test that makes this a measurement

The mechanism predicts an anti-correlation: a μ⁻ that is **captured** gives
de-excitation gammas and **no** Michel; one that **decays** gives a Michel and no
capture gammas. Measured (doc pdvd/51 §4, d16vnu, 119 events, 151 `is_stm`): the
population is **~2× commoner on candidates with NO Michel**. That anti-correlation
owes nothing to any threshold in the code, which is what makes it evidence rather
than tuning — and it is the quantity the §6.5 defect inverted.

### 5.5 What is *not* claimed

- The gammas are **not folded into the Michel**. One object per companion
  cluster, its own `Shower`, its own branches, **role 5** in the point cloud.
- `particle_type` stays **11**, not 22 — PDG 22 is never stored anywhere in this
  codebase (`get_particle_mass(22)` is 0 and `cal_kine_range` would fall back to
  the muon range function). The `gamma` node in the display is synthesised by the
  renderer from the connection type — the mechanism is §7.4; the e⁻ leaf under
  it is what was actually reconstructed: the conversion.
- The muon → gamma edge is a **claim about a neutral**, not a reconstructed
  connection. `set_start_vertex(stop_v, 2)` is the whole stitch: the gamma's
  segments live in a companion cluster with no graph edge into the muon's
  component, so a track BFS could never reach them at any knob setting.

---

## 6. How the Michel electron is clustered together

### 6.1 In-cluster: a guarded flood-fill

```
michel_shower = Shower(g)
michel_shower->set_start_vertex(stop_v, 1)
michel_shower->set_start_segment(seed.seg, ...)
IndexedSegmentSet used(chain_set);            // <-- the muon is off limits
michel_shower->complete_structure_with_start_segment(used, ..., /*absorb_track_guard=*/true);
```

`complete_structure_with_start_segment` (`PRShower.cxx:813`) is a worklist
flood-fill: from the seed's far vertices, every connected segment not already in
`used_segments` is absorbed, and its vertices enqueued, until nothing new is
reachable.

Three things control it:

- **`used` is pre-seeded with `chain_set`**, so the walk can never swallow the
  muon it just reconstructed. This is the barrier that makes an unconstrained
  flood-fill safe here.
- **`absorb_track_guard = true`**: the flood-fill otherwise has *no per-segment
  test at all* — one shower-flagged seed swallows every connected segment
  regardless of its own PID (doc pr/40 round 6 F12). With the guard, a
  confidently-PID'd non-electron (`pdg != 0`, `|pdg| != 11`) that is
  `segment_is_straight_long_track` is **not** absorbed and the walk terminates
  there. The excluded segment is deliberately *not* inserted into
  `used_segments`, and its shower flags are deliberately *not* consulted, so a
  stale flag cannot defeat the exclusion.
- Long-muon pseudo-showers are exempt (`particle_type == 13`), which does not
  apply here — this shower is type 11.

Every member segment that is not in the chain is stamped `pdg = 11`.

### 6.2 Across clusters: explicit `add_segment`, with a cluster-level admission test

The flood-fill only reaches what the graph connects. Pieces the 3-D clustering
broke into *separate clusters* are gathered by the companion loop, in two passes
so the result does not depend on graph edge order:

1. **Collect** every admissible piece with its distance to the stop.
2. **Assemble** in `(d_stop, cluster_id, graph_index)` order — so the seed of a
   bridged object is the **nearest** piece, and `michel_seg_id` names the piece
   the gap is measured to.

Admission is:

- the companion cluster was in the flash bundle, ≤ `companion_max_len_cm` (25 cm)
  long, and within the admit radius of the tagger's stop (the outer of the Michel
  and gamma radii, so one loop serves both);
- **re-tested at cluster level** against the stop the chain *actually ended on*
  — see §1.5, the two can be far apart;
- per piece: `segment_track_length <= dot_max_len_cm` (25 cm), and
- **the body exclusion**: a piece closer to the muon body (beyond
  `dot_body_exclusion_cm` = 5 cm of residual range) than to the stop is a delta
  ray thrown along the track, not a Michel piece.

**The radius test is a CLUSTER test, and re-applying it per segment is a bug that
was shipped.** It clipped **39.8 %** of the charge of PDVD 039252_15 cluster 77's
Michel — that cluster spans 1.91 → 19.36 cm from the stop, so more than a third
of the object sat outside a radius its *closest point* had already passed (doc
pdhd/15 §3). A segment of an admitted cluster is bounded by radius + cluster
length by construction, so the cluster test **is** the whole bound.

There is also a sentinel trap the code guards explicitly:
`segment_get_closest_point` returns 1e9 when a segment carries no usable point,
and on a chain shorter than the body exclusion the body distance is *the same
sentinel*, so `d_body < d_stop` is false and the piece would be kept with
`michel_dis_cm = 1e8` cm (PDHD 028084_12 cluster 3, a 1.0 cm 3-point chain).

### 6.3 What the tree tells you about the assembly

| branch | meaning |
|---|---|
| `michel_conn_type` | 1 attached / 2 bridged / 3 charge-only (§2.4) |
| `michel_n_pieces` | `n_michel_segs + n_dot_clusters_unfit` |
| `michel_n_clusters` | **> 1 says the object is not in the candidate's own cluster** — the fact a `T_stm_michel`-only consumer cannot otherwise derive |
| `michel_dis_cm` | 0 when attached; the gap to the nearest piece when bridged |
| `michel_seg_id` | `cluster_id * 1000 + graph_index` of the piece the gap is measured to |
| `n_dots`, `dots_ke_dqdx` | fitted companion pieces the object absorbed |
| `n_dot_clusters_unfit`, `dots_charge_unfit`, `dots_ke_unfit` | companions with no fitted segment |

Point-cloud roles in `T_stm_michel_pts`: **1** muon chain, **2** delta rays,
**3** the Michel object (every connection type), **4** a fitted piece the object
did not absorb (today: none), **5** capture gammas. Role 3 was widened from
"attached arms only" in doc pdvd/51 — before that every bridged Michel got role 4
and the hand-scan display drew it in the `dots` colour and called it a dot, which
is what the owner saw on 039252_15 cluster 77.

---

## 7. How the particle flow is formed

### 7.1 There is no particle-flow data structure — the PF *is* the PR graph

Nothing in this component builds a particle tree. What it builds is state on the
per-candidate `TrackFitting` object, and the **renderer** turns that into a tree
at write time. Exactly three things are handed over
(`grep 'tf->' CheckSTM_Michel.cxx` returns nothing else that matters):

| call | what it contributes |
|---|---|
| `tf->add_graph(pr_graph)` | the vertices and segments — the skeleton |
| `tf->set_main_vertex(entry_v)` | **the root** |
| `tf->set_showers(showers)` | the Michel and every capture gamma, as `PR::Shower` views over that graph |

plus, on each segment, a `ParticleInfo` written by `set_pdg`: PDG code, mass,
name, and a 4-momentum from `segment_cal_4mom`, with `particle_score(100.0)`.
That stamp is what gives a node its name and its energy. The chain gets 13; every
delta arm, Michel piece and gamma segment gets 11.

So the flow's topology is the graph's topology. Everything §1–§6 did — clearing
the muon's shower flags, stamping PDGs, seeding showers at the stop — was
already writing the particle flow.

### 7.2 Publication: the slots

```
tf->assemble_fitted_charge_2d();
if (ci == 0)          grouping.set_track_fitting(tf);                        // unnamed slot
if (publish_nu_slots) grouping.set_track_fitting("nu" + std::to_string(ci), tf);
```

This is byte-for-byte the neutrino chain's publication
(`TaggerCheckNeutrino.cxx:3580-3590`), and that is the point: every existing
consumer renders this stage's graph unchanged — the Bee `track_fit`,
`shower_track`, `vertices` and `mc` layers, `PdvdPrMagnifyTrackingVisitor`, and
`PrDisplayDump`.

Two conventions are **inherited, not chosen here**:

- the **unnamed slot is candidate 0**, and
- the per-candidate slots are named **`nu0`, `nu1`, …** — so a cosmic-ray
  stopping muon is published in a slot called "nu". That reads oddly and is
  deliberate: it is the slot name those writers already walk.

Each candidate gets its **own** fitter and its own graph (a fresh
`TrackFitting` per candidate, §1 of `visit()`). Resolving the unnamed slot
implicitly is therefore only correct while there is exactly one candidate —
`fill_bee_pf_tree` takes the fitter explicitly for that reason (doc pr/94
Phase 4), after a bundle-0 graph was once walked from bundle *i*'s vertex.

### 7.3 How the renderer walks it (`fill_bee_pf_tree`, `MultiAlgBlobClustering.cxx:1298`)

The output is a jsTree array — `{id, text: "name  KE MeV", data:{start,end},
children:[…]}` — and the algorithm is the prototype's
`NeutrinoID::fill_particle_tree` (documented at `:1278-1297`):

1. **BFS from the main vertex through non-shower track segments**, establishing
   parent–child among segments and recording which segment arrived at each
   vertex.
2. **Disconnected track segments** — not reachable from the main vertex — become
   additional root-level nodes, so nothing is silently lost.
3. **Showers attach under their parent track segment by
   `start_connection_type`** (§7.4).
4. **Node ids are `cluster_id * 1000 + seg_id`.**

For an STM candidate that resolves to: root at the **entry** vertex; the BFS runs
outward along the muon chain, which is walkable precisely because §4.1 cleared
`kShowerTrajectory`/`kShowerTopology` off every chain segment — a shower-flagged
segment is not a track segment and the BFS would not pass through it. Delta arms
hang off the chain segment at whose vertex they sit. The Michel and the gammas
arrive in step 3.

Step 4 is worth noticing: **`cluster_id * 1000 + seg_id` is the same encoding as
`stop_vtx_id`, `michel_seg_id`, `entry_vtx_id` and `T_stm_michel_pts.seg_id`.**
The tree and the flow are joinable on it without a lookup table — that is what
lets a hand-scan display put a `T_stm_michel` row beside the node it produced.

### 7.4 Why a *gamma* node appears at all — the pseudo-carrier

`Shower::set_start_vertex(vtx, type)` is the whole mechanism, and this component
uses exactly two types:

| where | call | renders as |
|---|---|---|
| attached Michel (§2.4 type 1) | `set_start_vertex(stop_v, **1**)` | a **direct leaf child** of the last muon segment |
| bridged Michel (type 2), **every** capture gamma | `set_start_vertex(stop_v, **2**)` | an intermediate **pseudo-particle node**, with the shower as its child |

The pseudo node's PDG is chosen by `append_pseudo_shower` (`:2163`): **22 when
the shower's `particle_type` is 11 or 22**, 2112 otherwise. That is the answer to
"where does the gamma come from" — the shower's `particle_type` stays **11**
throughout (PDG 22 is never stored in this codebase: `get_particle_mass(22)` is 0
and `cal_kine_range` would fall back to the *muon* range function). The `gamma`
node is **synthesised by the renderer from the connection type**, and the e⁻ leaf
beneath it is what was actually reconstructed — the conversion.

This is also the honest rendering of the physics: a capture gamma is neutral, so
there is no reconstructed connection between the stop and the blob. The
pseudo-carrier draws that claim, from `stop_v` to the shower's start point,
rather than pretending an edge exists. The gammas' segments live in a companion
cluster with no graph edge into the muon's component, so the step-1 BFS could
never reach them at any knob setting — `stop_v` is BFS-reachable, and the
renderer hangs the shower off it.

One conditional does **not** apply on either ProtoDUNE: `effectively_touching`
(`:2198`) would suppress the carrier for a conn-2 shower that starts within
`pf_touch_max` of the main vertex, but both drivers set
`pf_direct_when_touching = false` (`pr.jsonnet:277` / `:260`), so the carrier is
unconditional here. Note it would key on the **main vertex**, which for this
chain is the *entry* — the far end of the muon from where these showers start.

### 7.5 The pruning floor, and the second reason the energy stamp matters

`keep_node` (`:2087`) is the prototype's `KeepMC`: **a LEAF node** whose
\|PDG\| is 11 or 22 is dropped below `em_ke_min`, and 2112 / 2212 / a nucleus
below `np_ke_min`. A node with surviving children is always kept, so the
hierarchy never breaks.

Both ProtoDUNEs configure (`pr.jsonnet`):

| key | value | why |
|---|---|---|
| `em_ke_min` | **0.2 MeV** | lowered from 5 MeV by doc pdvd/51 so a sub-MeV capture gamma survives |
| `np_ke_min` | 3 MeV | |
| `prototype_names` | true | integer-MeV labels, as the prototype's `WCReader::MCJSON` |
| `ke_decimal_below` | **10 MeV** | an integer label reads "**0**" for a 0.8 MeV gamma; below 10 MeV the label carries two decimals (doc pdvd/51) |

This closes the loop on §3.4. The Michel's energy is stamped back with
`set_kine_best` for **two** reasons, not one: a 0 there would put the node under
`em_ke_min` and **delete it**, *and* `get_kine_best()` is what
`append_pseudo_shower` formats into the label. An un-stamped Michel would
therefore either vanish or render as "e-  0 MeV".

### 7.6 What the STM chain does not use

`fill_bee_pf_tree` also carries pi0 grouping, stray-satellite drops,
bridged-cluster BFS widening and orphan-track parentage. All of it is
**inert here**: those inputs come from `tf->get_pi0_showers()`,
`get_dropped_satellite_shower_ids()` and `get_bridged_cluster_ids()`, and this
component never populates any of them (§7.1 lists everything it sets). Reading
that code, do not assume a branch fires for a stopping muon just because it is in
the function.

## 8. The production knob bag

Both ProtoDUNEs run the **identical** 15-key bag (only the surrounding comments
differ), so one baseline serves both:

```
profile_min_dqdx_frac: 0.15     pid_mode: 2               plateau_mip_lo: 0.6
plateau_mip_hi: 1.6             stop_extend_max: 3        michel_guards_stop: true
michel_shower_min_kink_deg: 15  stop_fv_use_config_tolerance: true
dead_volume_check: true         mcs_enable: true          mcs_cathode_x: cathode_x
mcs_cathode_xcut: 5.0           michel_unfit_from_model: true
michel_unfit_dedx: 2.1
```

Everything in §2, §4.2, §5.1 and §5.2 that is *not* in this list is running at
its C++ default (`CheckSTM_Michel.cxx:372-455`) — including every Michel, delta,
dot and gamma threshold. `stop_gamma_enable` defaults **true** in C++ under the
owner's doc pdhd/14 waiver, so it is on without appearing in the bag.

`stm_michel_extra` (doc pdvd/51) merges **on top** of the bag, so
`-S stm_michel_extra={stop_gamma_enable:false}` changes exactly one key;
`-S stm_michel_knobs={...}` **replaces** all 15.

## 9. Caveats a reader should carry away

1. **The Michel energy inherits a muon-track calibration** (§3.5). PDVD's largest
   object is 76.8 MeV against a 52.8 MeV endpoint, and that is not explained.
2. **Delta-ray energy is attributed but not added back** to the muon (§4.2).
3. **The unfitted-charge term is MIP-equivalent** and under-estimates dense
   deposits (§3.2).
4. **`michel_dot_radius_cm` moves two boundaries at once** (§5.1) — it is the
   Michel's admission radius *and* the gamma ring's inner edge.
5. **The muon is only ever as good as the tagger's anchor.** `R_STOP_UNMATCHED`
   with a large `stop_dis` means the chain, the profile, every radius in §5-§6,
   and the Michel search all keyed on a stop the tagger did not intend (§1.5).
6. **Reject bits are not skips.** Every candidate is persisted; a consumer that
   forgets to filter on `reject_bits` is reading rejected reconstructions.
7. `R_PROFILE_SPARSE` means *cannot judge*, not *fails* — do not fold it into a
   physics inefficiency.
8. **The particle flow is rendered, not stored.** Every node in `mc.json` is
   derived at write time from the graph, the PDG stamps and the shower
   connection types (§7); a `gamma` node is the renderer's synthesis and no PDG
   22 exists anywhere upstream of it. The display floors (`em_ke_min` 0.2 MeV,
   `np_ke_min` 3 MeV) are **display** floors — a pruned node is still in
   `T_stm_michel`.
9. **Each candidate has its own fitter and graph**, published to slot `nu<i>`;
   the unnamed slot is candidate 0. Reading the unnamed slot when a event has
   several candidates renders candidate 0's flow for all of them.

## 10. Related docs

| doc | what it settles |
|---|---|
| pdvd/25 | the chain-level design: which components run where |
| pdvd/48 | the original `CheckSTM_Michel` design |
| pdhd/03 | the operating point both detectors now share (§6: stop extension, PID mode, plateau window) |
| pdhd/13 | defect census D1/D2 (`michel_found`, the admission cap) |
| pdhd/14 | the persisted kinematics, and the energise-once defect |
| pdhd/15 | the Michel as ONE object; the cluster-vs-segment radius fix |
| pdhd/16 | the three muon energy scales; MCS; §9 the cathode band |
| pdhd/17 | the unfitted-charge survival read out of the recombination model |
| pdvd/42 | the collinear leftover past the tagger's stop (26 % of passes) |
| pdvd/51 | the capture gamma, the particle flow, and the body-exclusion fix |
