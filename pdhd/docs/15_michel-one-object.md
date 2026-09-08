# The Michel as one object — doc pdhd/15

**Status: NOT bit-identical.** `T_stm_michel` goes from **79 branches to 88**.
Nine are new; eight existing ones (`michel_found`, `michel_conn_type`,
`michel_seg_id`, `michel_len`, `n_michel_segs`, `michel_ke_dqdx`,
`michel_ke_range`, `michel_ke_best`) change meaning or value, and two more
(`n_dots`, `dots_ke_dqdx`) move on boundary cases. The remaining **69** move
only on the six candidates whose companion set changed, and that is measured,
not asserted (§7). Owner ruling 2026-09-07, carried over from doc pdhd/14:
*"this can be new feature default on"*.

> **Superseded in one respect — doc pdhd/16 (2026-09-08).** The Michel and muon
> dQ/dx energies quoted here were computed with `PracticalBoxRecombination` as
> configured, i.e. *without* the ×0.85 the PID tables carry. On the `d16*nu`
> arms `check_stm_michel` runs a calibrated inverse and every dQ/dx energy is
> ×1.23–1.31 larger (`michel_ke_dqdx` p90 29.3 → 38.8 MeV on PDVD). The item
> set, the tranche, `michel_found`, `n_pieces` and every verdict here are
> unchanged and were checked bit-for-bit. See `16_stm-muon-energy-scales.md`.

## Repro

```bash
# the C++ (binary provenance in sec 7)
cd /nfs/data/1/xqian/toolkit-dev/toolkit && wcbuild && ./build/clus/wcdoctest-clus

# the two named items, one event
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdvd
./run_pr_evt.sh -nu -stm-fit -s d15vnu 039252 15
grep 'CheckSTM_Michel: cluster 77 \|CheckSTM_Michel: cluster 91 ' \
     work/039252_15_d15vnu/wct_pr_039252_15.log

# both scan arms.  Run NO waf target while these are live -- not `install`,
# not even a plain `./wcb build`: the runner's plugin search reaches
# build/<pkg>/ as well as local/lib, so relinking build/ truncates the .so the
# live jobs are dlopening and they die with
#   Failed to load libWireCellClus.so: .../build/clus/libWireCellClus.so: file too short
# It cost 20 of 31 PDHD events here, and 9 events in doc pdhd/14.
( cd pdvd && PDVD_MAX_JOBS=6 PDVD_LIGHT_SUFFIX=_keep \
    ./run_pr_evt.sh -nu -stm-fit -s d15vnu <run> all )   # 039252 039253 039349
( cd pdhd && PDHD_MAX_JOBS=6 \
    ./run_pr_evt.sh -nu -stm-fit -s d15hnu <run> all )   # 028084 029107

# every number below
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
python3 pdhd/docs/scripts/d15_michel_object_census.py \
    --before 'pdvd/work/*_d14vnu' --after 'pdvd/work/*_d15vnu' \
    --det pdvd --out /home/xqian/tmp/d15/d15v
python3 pdhd/docs/scripts/d15_michel_object_census.py \
    --before 'pdhd/work/*_d14hnu' --after 'pdhd/work/*_d15hnu' \
    --det pdhd --out /home/xqian/tmp/d15/d15h

# the legacy-equivalence gate (sec 7)
( cd pdvd && PDVD_PR_TLA="-S stm_michel_knobs={profile_min_dqdx_frac:0.15,pid_mode:2,\
plateau_mip_lo:0.6,plateau_mip_hi:1.6,stop_extend_max:3,michel_guards_stop:true,\
michel_shower_min_kink_deg:15,stop_fv_use_config_tolerance:true,dead_volume_check:true,\
dot_max_len_cm:10,companion_max_len_cm:10}" PDVD_MAX_JOBS=6 \
  ./run_pr_evt.sh -nu -stm-fit -s d15leg 039252 all )

# the display.  --pin-tranche keeps the in-progress scan's 60-item tranche 1
# fixed while the algorithm underneath it changes (sec 10); drop it only when
# starting a genuinely new scan under a new tag.
cd pdhd/stm_michel_scan
rm -rf prep-pdvd prep-pdhd     # the payload name does not carry the arm
python3 prep_stm_michel_scan.py --det pdvd \
    --pin-tranche 86d78116:pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
python3 prep_stm_michel_scan.py --det pdhd \
    --pin-tranche 86d78116:pdhd/docs/scan/pdhd_stm_michel_scan_sheet.tsv
python3 selftest_stm_michel_scan.py            # groups L and M
python3 selftest_smx3d_browser.py --det pdvd
python3 selftest_smx3d_browser.py --det pdhd

# serve the scan -- SAME tag as before, on the new output (sec 10)
./serve_stm_michel_scan.sh 5017 --det pdvd --scan-tag smx1
```

## 1. The question

Three asks, all about the same object:

> *"In the previous particle flow, you identified a gap in the
> `michel_conn_type==1`. For `==2`, which should be fixed."*
>
> *"In evt 039252_15 cl 77, there is a Michel electron at the end of STM, which
> is not identified. ... Now it is time to improve the algorithm and identify
> and add it to the particle flow."*
>
> *"In evt 039252_15 cl 91, a Michel electron was identified, but it also have
> some nearby activities that I feel was not counted in the energy calculation.
> For Michel electron, it may be a track + some dots and some additional
> activities. They should be counted as a single object. ... For energy
> calculation, there should be range, dQ/dx for the track. For the dots etc, I
> think we should have either dQ/dx --> dE/dx or the charge conversion to
> improve the energy."*

The last sentence is the specification this round is built to, literally:
**dQ/dx on everything the fitter reached, a charge conversion only where it did
not, and one object.**

## 2. The particle flow that already existed — and doc pdhd/14 §4 was wrong about it

Doc pdhd/14 §4 says *"There is no PF tree on this path."* That is incorrect and
was already pushed; the correction is now in that file.
`MultiAlgBlobClustering::fill_bee_pf_tree()` runs — `bee_pf` is bound at
`cfg/pgrapher/experiment/pdhd/pr.jsonnet:2243` and
`protodunevd/pr.jsonnet:2232` — and writes `mc.json` into `mabc-pr.zip`.
Before this round, `039252_15`:

```
[1000001] nu
  [77001] mu-  278 MeV                 <- no daughter: the missing Michel
[1000004] nu
  [91001] mu-  425 MeV
    [91002] e-  16 MeV                 <- the stale 16.2, missing the dot's 13.0
```

and a `michel_conn_type == 2` item (`039252_14` cluster 37):

```
  [37004] mu-  253 MeV
    [1] gamma  8 MeV                   <- pseudo-carrier interposed
      [129006] e-  8 MeV               <- the detached Michel IS linked
    [37005] e-  13 MeV                 <- a delta ray, rendered identically
```

So a bridged Michel *is* linked in `mc.json`, through a **pseudo-gamma carrier**
(`MultiAlgBlobClustering.cxx:2153-2177`, selected by
`start_connection_type == 2`), and it renders indistinguishably from a delta
ray. The existing escape hatch does not reach here: `pf_direct_when_touching`'s
`effectively_touching` (`MultiAlgBlobClustering.cxx:2188-2196`) measures the
distance to `main_vertex`, which this component sets to the **entry**
(`CheckSTM_Michel.cxx:901`) — 100+ cm from the stop on every candidate.

What `conn_type == 2` genuinely lacked was a link **in this module's own tree**,
and that is §4's fix.

## 3. Item 2 — why cluster 77's Michel was invisible, and why the radius must not be re-applied

`039252_15` cluster 77 before: `is_stm=1`, `reject_bits=0`, `michel_found=0`,
`n_stop_arms=0`, `n_dots=0`, `michel_seg_id=-1`.

The Michel is cluster **265**: same Q-L bundle (flash 298, `is_associated=1`),
20.1 cm, 116 points, 9.12e5 e, closest point **1.91 cm** from the fitted stop,
and **entirely unreconstructed** — 115 of its 116 cloud points lie more than
2 cm from any reconstructed point. Doc pdhd/13 named the line; it is the
companion **admission** cut, which used the same knob as the per-piece cut
(`dot_max_len_cm`, 10 cm — doc pdhd/13 defect D2), so a cluster over 10 cm never
entered the fitter, never received `find_proto_vertex`, and could become neither
an attached arm nor a dot. No log line was emitted.

### The knobs

| knob | before | now | site |
|---|---|---|---|
| `companion_max_len_cm` | — (new) | **25.0** | companion **admission** |
| `dot_max_len_cm` | 10.0 | **25.0** (declared default change) | per-**piece** length cap |
| `michel_unfit_recom` / `_fudge` / `_w_ev` | — (new) | 0.7 / 0.95 / 23.6 | the charge conversion (§6) |

Neither ProtoDUNE `stm_michel_knobs` bag sets any of them
(`pdhd/wct-pr-perevt.jsonnet:235`, `pdvd/wct-pr-perevt.jsonnet:223`), so the C++
defaults are what runs, and no jsonnet changes. Only `pdhd/pr.jsonnet` and
`protodunevd/pr.jsonnet` bind `check_stm_michel`, so nothing outside the two
ProtoDUNEs can see any of this. Setting `dot_max_len_cm: 10` and
`companion_max_len_cm: 10` reproduces the doc pdhd/14 length behaviour, which is
what the gate in §7 uses. The `dot_max_len_cm` default change is deliberate and
declared here rather than hidden: leaving it at 10 while raising admission would
admit the cluster and then reject every segment of it.

**The ceiling.** 25 cm is not a new number: it is `michel_max_len_cm`, the
ceiling an *attached* Michel arm already faces. Measured over both d14 arms,
the same-bundle neighbours within 15 cm of a stop that exceed the old 10 cm cap:

| detector | over 10 cm | of those ≤ 25 cm (now admitted) | over 25 cm (still excluded) |
|---|---|---|---|
| PDVD | 8 | **6** (11.0–20.1 cm) | 57.8, 171.3 cm |
| PDHD | 6 | **3** (12.4–23.5 cm) | 180.6, 246.2, 291.8 cm |

Every object the new cap admits is Michel-sized; everything it keeps out is
another cosmic. The PDHD three are `028084_12` cl 46 (12.4 cm), `028084_18`
cl 122 (23.5 cm) and `029107_4` cl 24 (13.5 cm); the PDVD six:

```
039252_15  cl  77 <- cluster 265   20.1 cm  d  1.91 cm  9.12e+05 e   (michel_found 0, n_dots 0)
039349_37  cl  39 <- cluster 320   12.7 cm  d  0.99 cm  6.25e+05 e   (michel_found 0, n_dots 0)
039349_58  cl  72 <- cluster 164   13.8 cm  d  1.42 cm  5.79e+05 e   (michel_found 0, n_dots 1)
039349_62  cl  36 <- cluster 125   11.1 cm  d 14.52 cm  1.88e+05 e   (michel_found 0, n_dots 0)
039349_63  cl  41 <- cluster 260   17.7 cm  d  9.80 cm  1.52e+06 e   (michel_found 0, n_dots 1)
039349_81  cl  51 <- cluster 201   11.0 cm  d  9.25 cm  7.92e+05 e   (michel_found 1, n_dots 1)
```

**The radius is a cluster test, not a segment test.** Admitting the cluster is
not enough: the old code re-applied the 15 cm `michel_dot_radius_cm` to every
*segment*. Cluster 265 spans **1.91 → 19.36 cm** from the stop, so **39.8 % of
its charge lies beyond 15 cm** — a per-segment test would have clipped exactly
the energy the owner says must not be missed. Over the whole admitted set the
clipped fraction is **median 20.7 % (PDVD) / 49.2 % (PDHD), max 99.7 %**. A segment of an admitted
cluster is bounded by `radius + cluster length` by construction, so the cluster
test is the whole bound; the per-segment radius test is removed. The
body-exclusion test (a piece closer to the muon body than to the stop is a delta
ray) and the per-piece length cap stay.

**But the radius must be re-applied — at cluster level, against the stop the
chain actually ended on.** `companions` is selected against the *tagger's* stop,
and the chain's stop is a different point: `R_STOP_UNMATCHED` walks to the
farthest vertex of the main cluster and `stop_extend_max` walks along a
continuation, so the two can be hundreds of cm apart. PDHD `029107_17`
cluster 33 has `stop_dis` **266.3 cm**, and with the per-segment test simply
deleted it acquired a "Michel piece" **255.4 cm** from its stop. The old
per-segment test had been masking that mismatch. The cluster-level test against
the final `stop_pt` is the correct place for it — it keeps the object whole and
still bounds it — and the self-test now asserts the resulting structural bound
(`radius + companion_max_len_cm`) on every bridged item.

## 4. Item 1 — the mu → e link, persisted for both connection types

The chain already knew the parentage: for a bridged Michel it builds the shower
with `set_start_vertex(stop_v, 2)` — the muon's own stop vertex — and then threw
that away at persist time, exactly the shape of the doc pdhd/14 defect. Now:

| branch | meaning |
|---|---|
| `michel_parent_vtx_id` | the vertex `Shower::start_vertex()` names; equals `stop_vtx_id` |
| `michel_dis_cm` | 0 when attached; the measured stop → object gap when bridged |
| `michel_start_x/y/z` | `Shower::get_start_point()`, cm |
| `michel_seg_id` | the core arm (attached) or the **nearest** piece (bridged) |
| `michel_conn_type` | **1** attached / **2** bridged / **3** charge only — now set outside the `build_michel_shower` guard |
| `michel_found` | **1 whenever an object exists**, bridged and charge-only included |

Two defects closed by those last two rows:

- `michel_conn_type = 2` was assigned *inside* `if (m_build_michel_shower)`, so
  with that knob off a real Michel reported `conn_type 0` with `n_dots > 0`.
- `michel_found` was set on the attached path only (doc pdhd/13 defect D1):
  **41 PDVD / 33 PDHD** reconstructed Michels reported 0, about 30 % of them.
  The old meaning is exactly `michel_found && michel_conn_type == 1`; every
  consumer that wants "attached" must now say so.

**Connection type 3 — charge only.** A companion cluster can pass every
admission test (same bundle, within 15 cm of the stop, ≤ 25 cm, closer to the
stop than to the muon body) and still yield no fitted segment. Through doc
pdhd/14 it landed in `n_dot_clusters_unfit` and nowhere else. Once §6's charge
conversion exists, that left **14 of 302 PDHD candidates** (15 `T_stm_michel`
rows before the scan's sample cut) reporting `michel_found = 0` beside a
non-zero `michel_ke_best` — a contradiction the tree would carry silently.
PDVD has none: every companion it admits gets fitted. Such an object is now `michel_conn_type = 3`: no
`michel_seg_id`, no `michel_ke_dqdx`, `michel_dis_cm` from the companion's
closest approach, and the whole energy from charge. It is deliberately a
*separate* type, not folded into 2, because there is no shape behind it.

| | before | after | attached | bridged | charge-only | pieces |
|---|---|---|---|---|---|---|
| PDVD | 115 | **158** | 115 | 43 | 0 | 247 |
| PDHD | 69 | **120** | 69 | 37 | 14 | 171 |

The attached count is unchanged on both detectors, so nothing was reclassified:
every added object is one that was already reconstructed and not reported.

**Not changed, and why.** The `mc.json` pseudo-gamma carrier stays. Re-stamping
`start_connection_type` to 1 for a "close enough" bridged Michel needs a
threshold, and the gap distribution supplies none: PDVD median 8.3 cm, p25 4.3,
p75 11.2, max 14.9 — broad, unimodal, and cut off by the 15 cm admission radius
rather than by any feature of the data. A gap in a monotone tail is sparsity,
not a class boundary. That field is also read outside the PF renderer
(`PrDisplayDump.cxx:589`) by a renderer SBND shares. Owner decision, §9.

## 5. Item 3 — one object, energised once

`039252_15` cluster 91 before: `michel_found=1`, `conn_type=1`,
`michel_ke_best` **16.20 MeV**, and separately `n_dots=1`,
`dots_ke_dqdx` **13.00 MeV**. The dot is cluster 309 — 45 points, 3.85e5 e,
lying **4.33 cm beyond the Michel arm's tip at 20.3° from the arm direction**:
the same electron across a clustering gap. Nothing near that stop is
unreconstructed — every cloud point within 20 cm of it is within 2 cm of a
reconstructed point. Only the energy was wrong.

**Root cause, one line.** The dot *was* added to the shower
(`add_segment`, old `:1274`), but `calculate_kinematics` had already run at old
`:1221`, before the dot loop, and was re-run only for `conn_type == 2`
(old `:1279`). The stale number then propagated into `mc.json`.

**Why it hid.** `dots_ke_dqdx` sat in the same tree row all along, so the tree
was never self-inconsistent — the two numbers simply never had to add up, and no
consumer added them.

**Fix.** The object is assembled first — the stop arm plus everything the shower
walk reaches, then every admitted companion piece — and energised once, at the
end, through the chain's own production entry point
`PatternAlgorithms::calculate_shower_kinematics` (`NeutrinoEnergyReco.cxx:303`),
which runs `Shower::calculate_kinematics` **and** sets `kine_charge`.

Energy fields, following the owner's sentence exactly:

| branch | what it is |
|---|---|
| `michel_ke_dqdx` | dQ/dx over **every fitted member** — core + completion + pieces |
| `michel_ke_core` | the core alone: exactly what `michel_ke_dqdx` meant through doc pdhd/14 |
| `michel_ke_range` | the **core track's** range energy |
| `dots_ke_unfit` | the charge conversion for companions the fitter never reached |
| `michel_ke_charge` | the chain's own `Shower::get_kine_charge()`, for comparison |
| `michel_ke_best` | `michel_ke_dqdx + dots_ke_unfit` |
| `michel_n_pieces` | fitted member segments + unfitted companion clusters |

`michel_ke_best` is deliberately **not** `Shower::get_kine_best()`: for a
shower-flagged or graph-disconnected object that returns `kenergy_charge`
(`PRShower.h:154`), computed with the SHOWER recombination pair, which overshoots
the chain's own dQ/dx by ~1.66× (§6). The object energy is instead stamped back
*onto* the Shower with `set_kine_best`, which is what `mc.json` renders (§8).

Cluster 91 after: `michel_ke_core 16.20` + piece `13.00` = `michel_ke_dqdx
29.20` = `michel_ke_best`, `michel_n_pieces 2`.

## 6. The charge conversion — and why the chain's own one reads 0 here

Where the fitter reached nothing there is no dx, so `dQ/dx` cannot be inverted
and only charge is left. `dots_ke_unfit` uses the one line every charge-based
energy in this repo ends on (`NeutrinoEnergyReco.cxx:509`, itself the port of
`NeutrinoID_energy_reco.h:248`), duplicated rather than extracted (CLAUDE.md
M10) as `stm_michel_charge_to_energy` and doctested:

    E = Q / recom / fudge * W / 1e6   [MeV],  W = 23.6 eV/ion pair

The factor pair is the KineChargeOptions **TRACK** pair (0.7 / 0.95), not the
shower pair, and that is measured rather than assumed. On the single-piece items
(46 PDVD / 26 PDHD), the dot cluster's own blob charge converted and divided by
the chain's `segment_cal_kine_dQdx` for the same piece:

| factors | PDVD (46 items) | PDHD (24 items) |
|---|---|---|
| track 0.7 / 0.95 | **1.19** | **1.01** |
| shower 0.5 / 0.8 | 1.98 | 1.67 |

The track pair puts an unfitted piece on the same scale as the fitted ones; the
shower pair would inflate it by two thirds. Both are exposed
(`michel_unfit_recom`, `michel_unfit_fudge`, `michel_unfit_w_ev`).

**`michel_ke_charge` is 0 on this path, by construction.** The chain's own
charge estimator projects each 2-D charge cell with
`Grouping::convert_time_wire_2Dpoint(time_slice, ...)`, which carries **no t0**,
and matches it against the shower's point cloud within 0.6 cm — but that cloud
*is* t0-corrected. On a cosmic the two frames are hundreds of cm apart and
nothing matches. Traced on `039252_15`:

```
kine_charge_from_maps: plane=0 ts=9032 ch=6916 ... p2d=(-327.148, 10.781)
                       dis=492.0779 cm  dis_cut=0.6000 cm  cluster=ok
                       pc0_3d=(176.078, -103.850, 220.335) cm
```

— a 503 cm offset on a cluster whose t0 is 6199.68 µs. The maps are not empty
(U=603 V=1175 W=1417 hits) and the clouds are not empty (115 / 35 points): the
frames simply do not meet. This is a **shared-path defect** — the estimator is
correct for a beam-frame neutrino cluster at t0 ≈ 0 and wrong for every
t0-corrected cosmic — so it is reported here and not fixed in this change
(§9). The branch is kept because it is the chain's own number and becomes
meaningful the day the frame is fixed; the display says so rather than showing
a bare 0.

## 7. What moved, and what provably did not

### The preload perturbation is confined, and measured

Admitting a companion feeds it to `TrackFitting::preload_clusters`
(`TrackFitting.cxx:717`), whose blobs go into `prepare_data()`, so the
candidate's **own** muon dQ/dx can move. It cannot cross candidates: each builds
its own `TrackFitting` and its own `Graph`
(`CheckSTM_Michel.cxx:837`, `:850`).

Measured d14 vs d15 on
`muon_len / contrast / plateau_med / ks_mu / n_profile_pts / is_stm / muon_ke_best`:

| | matched | set unchanged | of those bit-identical | set changed | of those bit-identical |
|---|---|---|---|---|---|
| PDVD | 568 | 562 | **562** | 6 | 1 |
| PDHD | 302 | 299 | **299** | 3 | 2 |

**Not one candidate whose companion set did not change moved at all**, on either
detector. The perturbation is exactly where the design says it can be.

All six, in full (`/home/xqian/tmp/d15/d15v_movers.tsv`):

```
039252_15 cl 77  muon_len 112.535->113.082  contrast 1.6368->2.1200  ks_mu 0.02743->0.04458  npts 188->189  KE 278.02->279.19
039349_37 cl 39  muon_len 258.872->262.000  contrast 0.5497->1.5155  ks_mu 0.15272->0.03722  npts 443->447  KE 597.51->604.55  is_stm 0->1
039349_58 cl 72  muon_len 129.822->129.942  contrast 1.8352->1.3406  ks_mu 0.08617->0.07634  npts 217->218  KE 314.85->315.11
039349_62 cl 36  bit-identical on all seven
039349_63 cl 41  contrast 0.38334667->0.38334667 (12th digit), ks_mu 0.2001644->0.2001721; muon_len, npts, KE identical
039349_81 cl 51  contrast 1.09282->1.12411, ks_mu 0.097326->0.099322; muon_len, npts, KE identical
```

The bottom three are noise-level: the fit re-converged with one more cluster in
the 2-D charge map and moved in the 5th–12th digit. Only the top three moved a
number a human would read.

PDHD's one mover is `029107_4` cluster 24:
`muon_len 149.0 -> 146.9, contrast 0.7594 -> 0.2103, ks_mu 0.2836 -> 0.3669,
npts 252 -> 248, KE 355.9 -> 351.3` (`is_stm` 0 in both).

Two of these deserve naming, and they move in **opposite** directions:

- `039349_37` cluster 39 **flips `is_stm` 0 → 1**: its Bragg contrast rises
  0.55 → 1.52 once the 12.7 cm neighbour sitting 0.99 cm from the stop is given
  to the fitter — the muon's tail had been asked to explain the Michel's charge.
- `029107_4` cluster 24's contrast **falls 0.76 → 0.21** for the same structural
  reason with the opposite sign: the fit shortened by 2.1 cm and the tail window
  moved off the rise.

One improved verdict and one degraded one out of 870 candidates. Both are
reported, neither is tuned (CLAUDE.md §5.7), and both are listed in §9.

### The legacy-equivalence gate

The new binary with the old length knobs
(`dot_max_len_cm: 10, companion_max_len_cm: 10`; compiled-config proof in
`pdvd/work/039252_0_d15cfg/.wct-pr_d15cfg.json`) against the `d14vnu` arm, run
039252, 85 candidates, 79 shared branches:

- **72 of 85 rows bit-identical on every one of the 79 shared branches.**
- The 13 that moved touch **only** the branches the doc-15 semantics own:
  `michel_found` (10), `michel_ke_dqdx` and `n_michel_segs` (13),
  `michel_ke_range` and `michel_len` (10), `michel_ke_best` (3),
  `michel_seg_id` (1).
- **Nothing else moved** — in particular `n_dots` and `dots_ke_dqdx` are
  bit-identical, which is the check that the radius rework (§3) reproduces the
  old admission exactly when the caps are set back to 10 cm.

So with the two length knobs at their doc-14 values the module reproduces the
doc-14 tree everywhere except the branches this round deliberately redefines.

### Binary provenance and the gate tally

Every arm quoted here — `d15vnu` (120 events), `d15hnu` (61) and `d15leg` (18) —
was produced by **one** `local/lib/libWireCellClus.so`, installed 22:29:30 after
the last source edit at 22:29:03 (M1 freshness proof). All 199 events completed,
0 failed.

| gate | result |
|---|---|
| `./build/clus/wcdoctest-clus` | 335 cases, **23164 assertions, 0 failed** |
| `selftest_stm_michel_scan.py` (groups A–M, both detectors) | **64616 checks, 0 failed** |
| `selftest_smx3d_browser.py` | **59 browser checks, 0 failed** per detector |

### The Michel spectrum against a free absolute gate

The Michel endpoint is `(m_mu² + m_e²)/(2 m_mu) = 52.8 MeV` and owes nothing to
this reconstruction, so an object that gathers charge it does not own shows up
there first.

| | objects | median | p90 | max | above 52.8 MeV |
|---|---|---|---|---|---|
| PDVD | 158 | 12.7 | 29.3 | 51.6 | **0** |
| PDHD | 120 | 8.5 | 28.2 | 70.4 | 2 (1.6 %) |

The self-test asserts both the median and a ≤ 10 % tail above the endpoint.
PDHD's two are named rather than hidden, and both look like the gathering rule
reaching one object too far:

- `029107_19` cluster 95 — **70.4 MeV**, attached, core 28.5 + a single 41.9 MeV
  piece. A 41.9 MeV "dot" beside a 28.5 MeV arm is almost certainly not the same
  electron.
- `028084_18` cluster 122 — **60.7 MeV**, bridged, three pieces of the 23.5 cm
  neighbour §3 admits. Its 1.8e6 e is 64 MeV by the charge route too, so the
  charge is real; whether it is a Michel is the open question.

Two of 120 is the honest tail, not a population, and the body-exclusion test is
the only thing separating a Michel piece from an unrelated neighbour past the
stop. Sharpening it is named as future work rather than tuned here.

### The NaN, and where it came from

PDVD `039349_3` cluster 26 (`conn_type 2`, `n_dots 2`) persisted
`michel_ke_best = NaN` through doc pdhd/14 — the only non-finite field in 568
rows. A NaN passes no gate and fails every one silently.

The mechanism, found because this round's guard fired on **six** objects rather
than one: a coincident pair of fit points gives `dx == 0`, `cal_kine_dQdx`
(`PRSegmentFunctions.cxx:2562-2565`) then divides by it, the `> 1000` filter
zeroes `dQ`, the Box model evaluates `0/0`, and the NaN passes every clamp
(`dE < 0` and `dE > …` are both false for a NaN) into the running sum. **One
such point therefore zeroes an entire object's energy.** A multi-segment Michel
meets one far more often than a single arm did, which is why doc pdhd/14 saw it
once and this round saw six.

`dqdx_skip_zero_dx` exists for exactly this (doc pdvd/45 §5.4) and is off by
default for bit-identicality elsewhere; this module now turns it on, so the
point contributes 0 instead of poisoning the sum — what the prototype's
`(dx + 1e-9)` did. The finite guard stays as a backstop and both arms report
**0** non-finite fields.

## 8. The display

The flow panel now reads the object rather than a segment:

```
mu   pdg 13   180.5 cm   424.1 MeV (range 424.1 / dQ/dx 330.2)   1 chain seg
  └─ attached at the shared stop vertex 91002
       e   pdg 11   core seg 91002   2 pieces in the object   29.2 MeV = dQ/dx 29.2 + unfitted charge 0.0
              core alone 16.2 · pieces 13.0 · core range 36.5 · chain kine_charge 0.0 — 0 by construction …
              core 11.2 cm, kink 36 deg · 1 dot (0 unfitted clusters carrying 0 e)
```

and a bridged or charge-only item carries its gap:

```
  └─ bridged to the same stop vertex 77002 across 0.38 cm of empty space
  └─ charge only, 6.31 cm from the stop vertex 43002 — the companion passed every
     admission test but the fitter produced no segment for it …
```

Every field is a `T_stm_michel` branch; the display computes no energy of its
own (the owner's standing rule from doc pdhd/14). The pre-doc-15 wording
*"no shared vertex, so no parentage is persisted"* was wrong on both counts and
is gone; the browser gate now asserts its absence.

**One defect this round created and caught.** Stamping nothing back onto the
Shower deleted the `e-` node from `mc.json`: `Shower::kenergy_best` is 0 whenever
a member is graph-disconnected (`PRShower.cxx:1855`) — which is every bridged
Michel and every attached one that gathered a piece — `get_kine_best()` then
falls back to the 0-valued `kenergy_charge`, and `fill_bee_pf_tree` prunes an EM
leaf below `em_ke_min` (`MultiAlgBlobClustering.cxx:2082`). Cluster 91 lost the
daughter it had carried since doc pdvd/48. The module's own object energy is
stamped back with `set_kine_best`, which is both the fix and the right value.

## 9. Open items — the owner's call

1. **The `mc.json` pseudo-gamma carrier** for a bridged Michel (§4). Rendering
   it as a direct `e-` daughter is a one-line change here, but it needs a
   threshold the gap distribution does not supply, and it touches a field a
   renderer SBND shares.
2. **`cal_kine_charge` is beam-frame only** (§6). Fixing it means giving
   `convert_time_wire_2Dpoint` a t0, which touches `Grouping` and every detector
   that uses the charge-based energy. Reported, not fixed.
3. **Two verdict-relevant movers** (§7), in opposite directions: PDVD
   `039349_37` cluster 39 flips `is_stm` 0 → 1 (contrast 0.55 → 1.52), and PDHD
   `029107_4` cluster 24's contrast falls 0.76 → 0.21. Both are better-informed
   fits; both are verdict changes.
4. ~~**The scan labels and the tranche.**~~ **Answered by the owner
   2026-09-08 — see §10.** The scan continues under `smx1` on the d15 output,
   and the tranche-1 draw is now pinned rather than re-drawn. The
   stratification's dependence on `michel_found` remains doc pdhd/13's open
   question about what that flag should mean to a consumer; §10 removes its
   ability to move a scan in progress, not the ambiguity itself.
5. **`pdhd/stm/perf/d30_hash_gate.py:43`** hashes `T_stm_michel` and will churn
   again on this round's nine new branches; it needs re-baselining against a
   `d15*` arm.
6. **The body-exclusion test is the only thing separating a Michel piece from an
   unrelated neighbour past the stop**, and §7's two over-endpoint objects are
   where it gives way. A direction or collinearity requirement on a piece
   relative to the core is the obvious next discriminator; it needs its own
   measurement round, so it is named here rather than guessed at.
7. Still open from doc pdhd/13: why 3-D clustering split a Michel that is
   2-D-contiguous with its muon in all three planes.
8. Still open from doc pdhd/13: defect D3 — on the `is_stm & no Michel` set the
   PR fits segments of the main cluster that the arm classifier then discards
   (74 % PDHD / 67 % PDVD). Untouched by this round.

---

## 10. The tranche pin — a scan sample must not move with the quantity it measures

**Symptom.** The owner reopened the display on 5017 after this round landed and
did not recognise it: the four labels they had placed were absent, and the list
was not the list they had been working through.

**Root cause, two independent parts.**

*Part 1 — the tag.* The round restarted the display under a new scan tag
`smx2`, whose `labels.json` did not exist, so the page opened with zero labels
and no memory of position. That was M13 caution applied where M13 does not
reach: the rule protects an existing label record from being overwritten, and
nothing here was going to overwrite one — the candidate set was the same 568
PDVD keys before and after. A new algorithm epoch is not a new scan pass. The
scan belongs under `smx1`; `smx2` was never written to and holds no labels.

*Part 2 — the draw.* `prep_stm_michel_scan.py:tranche()` samples tranche 1 per
`stratum()`, and `stratum()` is a function of `is_stm` and **`michel_found`** —
the flag §4 of this doc redefines. So regenerating the sheet on the `d15` arms
re-drew the sample:

| | tranche-1 items still in tranche 1 | dropped | added |
|---|---|---|---|
| pdvd | 19 of 60 | 41 | 41 |
| pdhd | 28 of 60 | 32 | 32 |

Three of the owner's four labelled items (`039252_0/77`, `039252_15/91`,
`039252_16/88`) moved to tranche 2. This is the more serious half: a hand-scan
sample stratified on the quantity being measured re-draws itself every time the
algorithm improves, so `tranche 1: N / 60` is not comparable across rounds and
a scan in progress loses its list.

**Why it hid.** The sheet regenerates as a side effect of re-prepping the
display on a new arm, and the item *set* never changes — 568 PDVD / 302 PDHD,
no key added, no key dropped, `scan_id` identical on every one of them. Only
the `tranche` column moves, and nothing was watching that column.

**Fix.** `prep_stm_michel_scan.py` gains `--pin-tranche SHEET_OR_REV`
(`read_pinned_tranche`): tranche membership is inherited per `(event, cluster)`
from a previous sheet instead of re-drawn. The argument is a path or a
`<rev>:<repo-relative-path>` read with `git show`, so a superseded sheet stays
usable as a pin after it is overwritten. Keys **absent** from the pinned sheet
get tranche 2 — a pinned sample never grows retroactively. Both the sheet and
the answer key are pinned (both carry the column), and `tranche_header()`
replaces the `seed=… (S1 cap …)` provenance line on a pinned sheet, which would
otherwise describe a draw that did not happen
(`feedback_rederive_from_primary_source`).

The strata themselves are **not** changed. A genuinely new scan under a new tag
should draw fresh; the pin exists for a scan already under way.

Two guards, because a knob you must remember to pass is not a fix:

* **Prevention.** `prep` **refuses** to draw at all while any
  `work/stm_michel_labels/*/labels.json` exists for that detector, unless
  `--pin-tranche` or an explicit `--redraw` is passed. It refuses rather than
  warns: the prep prints ~180 progress lines and a warning inside them is a
  warning nobody reads.
* **Detection.** Self-test group `[N]` compares the **labels already written**
  against the sheet — every record carries the `scan_id` and `tranche` it was
  placed under. This is the only check that separates a re-draw from a correct
  fresh draw: a forgotten `--pin-tranche` yields a sheet that is internally
  consistent and passes everything else. `npts` / `muon_len_cm` are deliberately
  not compared (see the caveat below).

**Verification.** Both detectors re-prepped to a scratch `--outdir`/`--sheetdir`
first and diffed before the sheets were promoted:

| check | pdhd | pdvd |
|---|---|---|
| key set == committed d15 sheet | ✅ 302 | ✅ 568 |
| `scan_id` changes vs d15 | 0 | 0 |
| `npts` / `muon_len_cm` / `n_near` / `n_far` changes vs d15 | 0 | 0 |
| `tranche` changes vs the d14 sheet | 0 | 0 |
| viewer order `(tranche, scan_id)` identical to d14 | ✅ | ✅ |
| answer-key non-`tranche` columns == committed d15 key | ✅ | ✅ |
| prep payloads byte-identical to the committed ones | 303/303 | 569/569 |

So the promoted sheet is exactly the d15 physics in the d14 order. The payloads
being byte-identical is also the re-run determinism check: the same arm re-read
end to end reproduces all 872 sidecars bit for bit.

Group `[N]` was built against causal negative controls, not just run once: a
flipped `tranche`, a shifted `scan_id`, a pinned sheet that still advertises
`seed=`, an understated unpinned count, and the same flip on an unpinned sheet
are each caught by the check that targets them, and the clean sheets pass. The
label check was verified against the **pre-pin d15 sheet**, where it names the
three that moved — `039252_0/77`, `039252_15/91`, `039252_16/88`, all
`t1 -> t2` — and passes on the promoted one.

In the browser, on `smx1` at 5017, the progress widget reads
**`4 / 568 labelled | tranche 1: 4 / 60`** — 4/60 is the discriminating number
(it was `1 / 60` before the pin; `4 / 568` was already true and proves nothing).
Read through a Playwright locator: `inner_text("body")` misses Bokeh 3's open
shadow DOM.

**One measured caveat, already known.** Three of 568 PDVD items differ in
`npts` / `muon_len_cm` between the d14 and d15 sheets, one of them being
`039252_15/77` (188 → 189 points, 112.54 → 113.08 cm). That is not the pin: it
is §7's `preload_clusters` perturbation from admitting cluster 265 as a
companion — the fit gains one point. The labels record `npts` and `muon_len_cm`
as written at label time, so those two fields in the four `smx1` records are
d14-era for that one item; the label itself (a topology verdict) is unaffected.
