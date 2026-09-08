# doc pdhd/12 — the stopping-muon + Michel-electron hand-scan display

**Both detectors.** PDHD and PDVD are served by one app; `--det` picks the
geometry table and the sample. Written 2026-09-07, on the doc-11 chain.

Owner ask, 2026-09-07: *"I would like to do a hand scan to select good STM +
Michel electrons … X-Y, Y-Z, Z-X projection views, show the 3D image projection
as well as the track trajectory and dQ/dx fit … a 1D dQ/dx vs. RR, separated the
STM vs. Michel electron … a 3D view … save the end point of the STM (or the
Michel electron starting point) … save if this is a STM + Michel electron or
something else … it is also important to be able to show where the STM stopping
point is (different APAs, different CRPs)."* Same technology as `em_display` /
`stm_display`.

Stated downstream goals, and this doc's §7 shows the saved schema is sufficient
for each: (1) robustly select this topology, (2) cleanly separate the muon part
from the Michel part, (3) the Michel energy spectrum, (4) angle vs momentum.
**None of the four is built here.** This round builds the instrument.

**Round 2, 2026-09-07, after the display was first served.** Owner ask: *"add
the 2D measurement and the difference between the predicted measurement vs.
actual measurement like what would show in Magnify Tracking display. For 2D
measurement, it would be useful to add the dead channels etc. In addition, it
would be nice if we can click the dQ/dx vs. rr plot and then show in the 3D
display, 2D projections and the 2D measurement space. Also the yellow color in
the dQ/dx vs. rr is a bit hard to see."* Sections **5.4** (the measurement
panels), **5.5** (the click link) and **5.6** (the colour) are that round; the
gates it added are §10 items 11–16 and its limits are §11 items 6–8. The sample,
the sheet, the key and the label schema are unchanged — the four committed TSVs
are byte-identical after the re-prep, gated with `git diff --exit-code`.

**Round 3, same day.** Owner ask: *"probably good to add a save info button, so
that I know the information is properly saved? also for the CheckSTM_Michel,
does it have a Particle Flow? It would be nice if that particle flow can be
added as well, so that we can select? … With particle flow, we also want the
track vs. shower, etc. If those are not available in the checkSTM_Michel, this
would be one thing that we should improve upon."* Sections **5.7** (the particle
flow, what is available and the one thing that is not) and **5.8** (the save
read-back) are that round, with §7 extended for the new `pf_segments` field.
**It is available**, and §5.7.4 names precisely the one thing that is not.

A question that came with it: *"for the fit results, are they coming from
CheckSTM_Michel PR stage or the STM tagger stage? I would like the former since
the fit is more spaced at 0.6 cm."* **The former, and it always was.** Measured
over 15 events per detector: the `T_stm_michel_pts` chain (CheckSTM_Michel, PR
stage) steps a uniform **0.600 cm** (p10 = p50 = p90 = 0.600); the cosmic
tagger's `tracking-stm.root` fit steps a median 0.610 cm over a p10–p90 range of
0.51–0.82 cm. The muon layer, the dQ/dx panel, the new measurement overlays and
every wire coordinate come from the PR chain. The tagger fit appears only as the
grey `tagfit` layer behind REVEAL, and is deliberately **absent** from the
measurement panels.

## Repro

```bash
cd wcp-porting-img/pdhd/stm_michel_scan
./prep_stm_michel_scan.py --det pdhd            # 61 events  -> 302 items, 126 MB
./prep_stm_michel_scan.py --det pdvd            # 120 events -> 568 items, 212 MB
git -C .. diff --exit-code -- pdhd/docs/scan pdvd/docs/scan   # sheets unchanged
./selftest_stm_michel_scan.py                   # 6252 headless checks, both detectors
./selftest_smx3d_browser.py --det pdhd          # 39 checks in headless chromium
./selftest_smx3d_browser.py --det pdvd
./serve_stm_michel_scan.sh 5023 --det pdhd --scan-tag smx1
cd ../../pdvd/stm_michel_scan
./serve_stm_michel_scan.sh 5024 --scan-tag smx1
# after scanning:
../../pdhd/stm_michel_scan/score_stm_michel_scan.py --det pdvd --tag smx1
```

Everything in this doc comes from those commands. Nothing was re-run in
production for it.

---

## 1. Why this scan exists

`CheckSTM_Michel` (doc pdvd/48, doc pdhd/03) replaced `TaggerCheckNeutrino` as
the PR tail on both ProtoDUNEs on 2026-09-05/06. It reconstructs every
STM-tagged main as `entry → muon body (+ deltas) → Bragg stop → Michel e⁻
(+ dots)` and **persists all of it**. Doc pdvd/48 §11 "next steps" item 1 states
the gap precisely:

> The STM + Michel subsample needs no new code … The development left is
> **purity/efficiency of that flag**, not plumbing.

Purity and efficiency of a topology flag cannot be measured against the flag.
They need labels. This is the instrument that produces them.

## 2. Arm provenance — nothing was re-run

The display reads the doc pdvd/50 round-2 `-nu` arms, which already carry every
input on today's chain:

| | arm | events | per-event files used |
|---|---|---|---|
| PDHD | `pdhd/work/*_d51hnu` | 61 / 61 | `tracking-pr.root`, `tracking-stm.root`, `mabc-pr.zip`, `calib-pr-evt*.json` |
| PDVD | `pdvd/work/*_d51vnu` | 120 / 120 | same |

Toolkit HEAD `c0b1613b` (`apply-pointcloud`); the arms were written 2026-09-07
15:16–15:43, after the `818c47fb` / `c0b1613b` chain flips and the 14:37:28
relink. `-nu` is what matters: `check_stm_michel` is gated on membership of the
pipeline string (`pdhd/pr.jsonnet:2010`, `protodunevd/pr.jsonnet:1995`), so a
`-stm` production arm carries **no** `tracking-pr.root` at all and no Michel
trees. That is why the two `d51*nu` arms are the only ones on disk this can use.

`pdvd/work/039252_11_d51vnu` has no `T_stm_michel` tree. The log says why, in
those words: `CheckSTM_Michel: no STM-tagged main cluster; nothing to
reconstruct`. The job completed normally and the arm is 120/120 — this is one
event with nothing to reconstruct, not a hole.

## 3. What the chain persists, and the one thing it does not

`tracking-pr.root`, written by `PdvdPrMagnifyTrackingVisitor::write_stm_michel_trees`
(`root/src/PdvdPrMagnifyTrackingVisitor.cxx:358-362`) out of the cluster-local
point clouds `stm_michel` / `stm_michel_pts` (`CheckSTM_Michel.cxx:729,:739`):

| tree | rows | what |
|---|---|---|
| `T_stm_michel` | one per candidate, 74 branches | `entry_*`, `stop_*` (**the Michel start**), `tagger_stop_*`, `stop_dis`, `is_stm`, `reject_bits`, `michel_found`, `michel_conn_type`, `michel_len/mip/kink_deg/far_len`, `michel_ke_{dqdx,range,best}`, `n_dots`, `dots_ke_dqdx`, `muon_len`, `contrast` vs `contrast_expected`, `plateau_med`, `tail_med`, `in_fv`, `kink_num` |
| `T_stm_michel_pts` | one per fit point | `x,y,z` (cm), `q` = **dQ/dx in e/cm already**, `L`, `rr` (cm), `seg_id`, `role` |

`role` (`CheckSTM_Michel.cxx:1007, 1120, 1172, 1226`): **1** muon chain,
**2** delta ray, **3** Michel arm, **4** detached Michel dot. There is no role 0.

**`rr` and `L` exist only on role 1.** `add_points`'s no-profile branch
(`CheckSTM_Michel.cxx:682`) writes `-1` for both on every Michel, delta and dot
point. So *"dQ/dx vs residual range, STM separated from Michel"* cannot be
plotted as literally asked: the Michel points have a dQ/dx and a position but no
residual range. §5 is how the display answers the question anyway.

Units are human throughout (`CheckSTM_Michel.cxx:686-691`): cm, MeV, e/cm,
degrees. In particular `q` here is **not** the display-scaled `T_rec_charge.q`
and must not be decoded — `(q − offset)/scale/nq` applied to it would be wrong.

`is_stm = (reject_bits == 0)`, and **a Michel is deliberately not a criterion**
(`StmMichelFunctions.h:167-168`) — µ⁻ capture in argon is real. So `is_stm` and
`michel_found` are two independent flags, which is what makes a four-way
stratification (§6) the right shape.

The 3-D imaged charge is in no ROOT tree. It is `mabc-pr.zip` member
`data/0/0-clustering-global.json`, and that member alone is what the prep opens.

## 4. Where the stopping point is — the wire route, earned on both detectors

The owner asked to see which APA (PDHD) or CRP (PDVD) a muon stopped in. Two
routes exist and they are not equivalent.

### 4.1 Why not `sign(x)`

`cfg/pgrapher/experiment/protodunevd/clus.jsonnet:80-84` says it outright: the
imaging Bee groups are routed by physical anode, **not** by reconstructed x,
because *"the two volumes overlap in the pre-T0 apparent-x frame, so only anode
membership separates them"*. PDVD runs with `time_offset = 0`. Out-of-time
cosmics are exactly the population a stopping-muon scan looks at. PDHD is
different — imaging runs per APA there, so a wrong T0 slides x *within* one APA
— which is why doc pdvd/50 §4.2b could measure 78 867/78 867 agreement there and
say nothing about PDVD.

### 4.2 The rank blocks, re-derived from the production wire files

`T_rec_charge.pw` is `ChanScheme::globalf(2, apa, face, wire)`
(`PdvdMagnifyTrackingVisitor.cxx:601`) — `base[2]` plus the rank of the channel
among the **collection** plane's channels over every anode and face. That is a
property of the wire file, so it was re-derived from the wire files themselves
(`selftest_stm_michel_scan.py::wire_blocks` re-runs the derivation on every
call). Every block is **exactly contiguous**:

| | wire file | `nch` / `base` | unit | sub-unit |
|---|---|---|---|---|
| PDHD | `protodunehd-wires-larsoft-v1.json.bz2` | `[3200,3200,3840]` / `[0,3200,6400]` | `apa = (pw − 6400) // 960` | face blocks of 480; face 1 is the **lower** half on all four APAs |
| PDVD | `protodunevd-wires-larsoft-v7-uvwfit.json.bz2` | `[3808,3808,4672]` / `[0,3808,7616]` | `anode = (pw − 7616) // 584` | **`cru = (pw − 7616) // 292`**, 16 CRUs, anode-major then y-ascending |

The PDVD face order **flips** between the y<0 anodes (0,1,4,5 → face 1 lower)
and the y>0 anodes (2,3,6,7 → face 0 lower), and cross-referencing the sensvol
boxes that flip is exactly what makes the sub-block monotone in y in both. So
`cru` alone orders the detector in y, and `anode ≥ 4` is the drift volume,
`anode ∈ {2,3,6,7}` the y>0 CRP.

This **settles** the caveat `d51_dqdx_rr_apa.py:96-98` refused to act on
(*"the per-anode channel run is not verified contiguous … computed for the
`--confusion` cross-check and never used as the label"*). It is verified, and
the PDVD label can now be a CRU rather than a drift volume.

### 4.3 Measured agreement, and the nine exceptions

Wire label vs geometric label over **every** chain point of both arms
(`selftest_stm_michel_scan.py::test_unit_agreement`):

| | chain points | with a collection wire | agree |
|---|---|---|---|
| PDHD | 97 721 | 97 721 | **97 718** (1.0000) |
| PDVD | 166 037 | 166 037 | **166 031** (1.0000) |

The PDVD row is a new result — doc pdvd/50 could only measure PDHD.

The nine exceptions are **one value each**: `pw = 6880` on PDHD and `pw = 7908`
on PDVD. Those are `base + per_face`, i.e. `globalf(2, apa=0, face=0, wire=0)` —
the writer's coordinate for a fit point whose `(apa, face, wire)` was never
filled. Their x/y/z are scattered across the detector, which is how they show up
at all. Rate 3.1 × 10⁻⁵ (PDHD) and 3.6 × 10⁻⁵ (PDVD).

They are not silently resolved. `smgeom.SENTINEL_PW` names the value, and when
the two routes disagree the badge says
`wire, DISPUTED: geometry says APA3 — this fit point carries the writer's
DEFAULT wire` rather than picking one. The self-test forges the case and asserts
the flag appears.

*(Cheapest upstream fix, not made here: two `Branch("apa")`/`Branch("face")`
lines in `PdvdMagnifyTrackingVisitor.cxx:531-559`. `apa` and `face` are already
read at `:577-578` and used only to feed `globalf`. Mentioned, not fixed — it is
an unrelated change.)*

### 4.4 The envelopes drawn

The sensvol union, **not** `dvm.overall` from `clus.jsonnet`, which already
carries a 15 cm space-charge inset and would draw a box inside the charge.

| | x [cm] | y [cm] | z [cm] | seams drawn |
|---|---|---|---|---|
| PDHD | ±357.985 (cathode ∓2.54) | 7.61 … 606.0 | 0.234 … 462.297 | z = 231, x = 0 |
| PDVD | ±339.91 (cathode ∓3.0) | ±336.39 | 0.813 … 298.435 | y = 0, ±168.50; z = 149.65; x = 0 |

## 5. The display

`pdhd/stm_michel_scan/` — one app, `--det`. `pdvd/stm_michel_scan/` is a
three-line wrapper, not a fork: the two detectors differ by a geometry table,
and a forked viewer would have to be fixed twice. `stm_michel_viewer.py` is a
fork by duplication of `pdhd/stm_scan/stm_scan_viewer.py` and `smx3d.py` of
`sbnd_xin/em_display/em3d.py`; both parents are byte-untouched.

**Left, two tabs.** A rotatable orthographic **3-D** view (default) and the
three **2-D projections** Z-Y / Z-X / X-Y at full detector extent with the
active boundary dashed and the APA/CRP seams dotted. Full extent is deliberate:
an object auto-zoomed to its own extent looks contained in every projection,
which inverts STM/THRU calls.

**Both draw the same layers, and the split between them is the whole design:**

| layer | source | when |
|---|---|---|
| thinned grey context | the rest of the event | always |
| full-density image charge | `clustering-global` within 20 cm of any chain point **or** 40 cm of the chain's stopping end | always |
| the fitted muon chain, coloured by its own dQ/dx | role 1 | always |
| Michel / delta / dot segments, entry / stop / tagger-stop markers, the cosmic tagger's own STM fit | roles 2–4 and the `T_stm_michel` scalars | **REVEAL only** |

Both charge selections are **purely geometric over all the charge in the event**
— never "the points the chain assigned to this cluster", which would draw the
clustering decision, and never `shower_track-global`, where the chain paints its
own Michel via pdg 11. The prep records which zip members it opened
(`image_src`) and the self-test asserts that list is exactly `clustering-global`.

The 40 cm ball on the chain's stopping end is not decoration: Michel lengths run
to 20 cm, so a Michel running off the end would otherwise leave the 20 cm tube
and be thinned 1-in-N — the display would hide the object being judged.

**Right — dQ/dx vs signed arc length.** Since only role 1 carries `rr` (§3), the
axis is signed arc length through the pin: muon points at `rr − rr(pin)`,
everything else at **minus** its 3-D distance from the pin. The detector's own
muon and electron reference curves are overlaid from `calib-pr-evt*.json`'s
`dqdx_ref` block (401 points, rr 0–100 cm, step 0.25, e/cm, `ParticleDataSet`),
verified identical across events within a detector and written once per detector
rather than 181 times. Muon plateau 54 609.2 e/cm (PDHD) and 53 965.5 (PDVD) —
the same numbers doc pdvd/50 published, and the self-test pins them so a chain
change that moved the reference cannot slip past.

Nothing is normalised to a MIP. In particular `meta.mip_dqdx_median` in that
dump is the C++ default **43 000**, not the 48 000 / 47 000 the taggers actually
run with, so normalising by it would inflate every ratio by 1.12.

### 5.4 The 2-D measurement — what the wires actually saw

Every other panel is reconstruction space: 3-D points and a trajectory. A track
that looks clean in 3-D can be a fit riding on charge that is not there, and the
only place that shows is the residual. For this scan specifically, *"did the
muon stop, or did it leave through a dead region"* and *"is that Michel a real
deposit or a prediction artefact"* are **measurement-space** questions.

A third tab, **2-D measurement**, holds nine panels: three rows (U, V, W) by
three columns — the **measured** charge in each (channel, time slice) cell, the
charge the fitted track **predicts** there, and their **difference**. That is
the content of a Magnify tracking display, read from the tree Magnify reads:
`T_proj_data` in the same `tracking-pr.root`, one row per fitted cluster, with
`channel`, `time_slice`, `charge`, `charge_err` and `charge_pred`, written by
`PdvdPrMagnifyTrackingVisitor::write_proj_data`.

Drawn on top: the **dead channels** from `T_bad_ch`, and the fitted muon chain
in its own wire coordinates. The chain's Michel / delta / dot points appear here
too, behind REVEAL, which is what makes "separate the muon part from the Michel
part" (downstream goal 2) answerable in the space where the charge lives. The
cosmic tagger's fit is not drawn here.

**How a fit point gets a wire coordinate.** `T_rec_charge` carries `pu/pv/pw`
(the fractional wire in each plane) and `pt` (the time slice), and every
CheckSTM_Michel chain point *is* a `T_rec_charge` point of the same file —
measured 8962/8962 role-1, 142/142 role-2, 73/73 role-3, 2/2 role-4 on PDHD and
7736/7736, 82/82, 42/42, 22/22 on PDVD, all within 0.05 cm. So the join is an
index lookup dressed as a nearest-neighbour query. A point that misses the
0.05 cm tripwire is simply not drawn in measurement space.

**Three things that would make this panel lie, and what is done about each.**

1. **The plane split.** `channel`, `chid` and `pu/pv/pw` are all a per-plane
   *rank*, not a LArSoft channel id, and a wrong-but-self-consistent split
   produces no error, no empty bin and no NaN — it silently answers a different
   question (`feedback_magnify_channel_is_a_plane_rank`, which is this exact
   trap on these exact files). `smgeom.BASE` carries the full scheme
   (`(0, 3200, 6400)` PDHD, `(0, 3808, 7616)` PDVD) and it is gated **causally**,
   by two independently written code paths having to agree: the fitter writes
   `pu/pv/pw` with `ChanScheme::globalf`, the projection writer writes `channel`
   with `ChanScheme::global`, so a fit point's own wire has to land on a cell of
   the same channel. Over the clusters this display draws, ±2 slices:

   | | U | V | W |
   |---|---|---|---|
   | PDHD | 0.9646 | 0.9636 | 0.9149 |
   | PDVD | 0.8692 | 0.9102 | 0.9165 |

   and every plane's fit-wire range lies strictly inside its own base block. The
   shortfall from 1.0 is fit points where the projection has no cell within two
   slices — not a mapping error, which would read ≈ 0. Restricting to the shown
   clusters matters: over *every* row of `T_proj_data`, including satellite and
   fallback blob-ownership rows whose cells are not the fit's own, the same
   numbers are 0.70–0.74. The panel shows one cluster; so does the gate.

2. **Ticks versus slices.** `T_bad_ch.start_time`/`end_time` are in **ticks**
   while `T_proj_data.time_slice` and `T_rec_charge`'s `pt` are in **slices**.
   The asymmetry is real, not a bug to fix: `write_bad_channels` clamps against
   `m_nticks` while `write_proj_data` divides by `nticks_per_slice`. The
   production configs set `nticks_live_slice: 4` — but a config is not a
   measurement (`feedback_dump_meta_is_not_the_config`), so the constant is
   gated on the **files**: `max(T_bad_ch.end_time) / (max(time_slice) + 1)` is
   **4.000** on PDHD (6000/1500) and **4.027** on PDVD. At ÷1 every dead band
   would sit at a quarter of its true time and visibly miss every gap.

3. **The residual is meaningless inside a dead region.** `Cell::charge()` falls
   back to `prepare_data`'s **filler** when a slice has no live entry, and the
   tree does not carry the per-cell live/dead flag — so `measured − predicted`
   there is model minus model. This is why the dead-channel overlay is not
   decoration: it is the only thing that says which residual cells mean
   anything. Dead bands are drawn twice, as a solid grey fill **under** the
   cells (so a gap with no cells at all still reads as *dead*, not as *nothing
   was there*) and hatched **over** them.

**Scales are fixed, not per-item.** A per-item colour scale makes two items
incomparable, which is fatal for a hand scan. The charge scale is each plane's
p90 cell charge over ~30 events of the production arm, and the residual scale
its p99 |measured − predicted|, both fixed and stated in the panel:

| | charge 0 – … (e) | residual ± … (e) |
|---|---|---|
| PDHD U / V / W | 56 000 / 57 000 / 31 000 | 80 000 / 100 000 / 48 000 |
| PDVD U / V / W | 31 000 / 27 000 / 18 000 | 45 000 / 36 000 / 21 000 |

p90 rather than p99 because the p99 tail runs to 1.2 × 10⁶ and would push the
bulk (p50 ≈ 3–12 ke) into the bottom tenth of the map. A `×0.5 / ×1 / ×2 / ×4`
multiplier moves **all six** mappers together, so contrast is adjustable without
ever making two items incomparable. The residual map is diverging and
**white-centred on purpose**: a cell where the fit agrees vanishes into the page,
so only disagreement draws the eye.

**A cell is a screen-pixel square, not a data-unit rectangle**, and that is a
correction rather than a preference. The first version drew a `rect` one channel
by one slice. On the heaviest item — 22 106 cells spanning 2 322 channels and
1 095 slices in a 430 × 300 panel — a data-unit cell is 0.16 × 0.27 px and
antialiases to nothing: the tab rendered as nine empty axes with a track drawn
on them. The browser gate caught it because emptying the cell sources changed
the painted pixels by **exactly zero**. Two things were wrong and both are fixed:
the cells are square markers sized in screen pixels (2 / 3 / 5 / 8, default 3),
and the trajectory overlay — which had a 3 px white halo, a 1.2 px black line
and a marker per fit point — is now a thin translucent line, because the
cluster's cells *are* the track's own cells and at full-cluster zoom the
annotation was painting out the evidence.

The default window is the whole cluster, which is what Magnify shows. A
**± 150 channels / ± 150 slices around the stop** window is one click away,
because a 677 cm muon spans 2 300 channels and the Michel lives in the last 30.

### 5.5 Click a dQ/dx point, find it everywhere

Tapping a point in the dQ/dx panel drops a cyan cursor on the **same point** in
the 3-D view, all three projections and all nine measurement panels, and prints
its arc length, dQ/dx, x/y/z, U/V/W wire, time slice and readout unit. So *"what
is that outlier at rr = 12 cm"* is answered by pointing at it.

Every scatter source in that panel therefore carries the point's own
`x, y, z, pu, pv, pw, pt` alongside the plotted pair, and the callback reads the
tapped **row** — no index arithmetic between the panel's live-only rows and the
chain arrays, which is exactly where an off-by-a-few cursor would come from. All
columns are masked identically. Deselecting clears the cursor; so does moving to
another item or toggling REVEAL, since a cursor from the previous state would
point at something no longer on screen.

The link is deliberately **one-directional**. Taps on the 3-D view and on the
projections already place the pin, and making them do two things would make the
pin unpredictable.

### 5.6 The colour, and why it is not Viridis any more

The dQ/dx panel used Viridis with the object's own p98 as the top of the scale.
Both halves of that were wrong, and both hid the one feature this scan exists to
judge:

- **Viridis ends at `#FDE725`** — bright yellow on a white page. The Bragg peak,
  the highest-dQ/dx points, rendered as the least visible colour on the plot.
  Turbo ends at a dark red (`#7A0403`) and starts at a dark blue, so nothing on
  the scale is near the page colour.
- **A per-item p98 made the colour mean something different on every item**, so
  two objects a factor of three apart in dQ/dx looked identical. The scale is
  now fixed at **0 – 1.5 × 10⁵ e/cm** on both detectors, from a measurement
  rather than a guess: over every role-1 point of both arms (97 721 PDHD +
  166 037 PDVD) the median is 49.5 / 50.2 ke/cm, p99 is 112 / 118 ke/cm and
  p99.9 is 162 / 166 ke/cm. So the MIP plateau sits at a third of the range
  (cyan-green) and the Bragg rise in the orange-to-dark-red top, with under
  0.3 % saturating.

Independently of the palette, **every marker in the dQ/dx panel now carries a
thin dark outline**, so "invisible fill" cannot come back if the scale is ever
retuned — the palette stops being load-bearing. The self-test asserts both: no
colour in the palette exceeds 0.90 relative luminance, and the glyphs are
outlined.

The image-charge layer keeps an adaptive scale — it is context, and its range
genuinely varies by plane and detector — but gets its own **cool** ramp, because
`near` and `muon` were both Viridis in the same panels, so charge-per-point and
charge-per-cm read as one quantity.

### 5.7 The particle flow

**Yes, CheckSTM_Michel has one, and all of it is persisted.** The chain runs the
full PR sequence — `find_proto_vertex` → `clustering_points` →
`separate_track_shower`, rooted at the entry vertex via `set_main_vertex` — and
`PdvdPrMagnifyTrackingVisitor.cxx:855-915` writes every part of it per point in
`T_rec_charge`:

| what | branch | how it is written |
|---|---|---|
| **segment id** | `sub_cluster_id` (and `real_cluster_id` — the *same buffer*) | `cluster_id × 1000 + segment graph index` (`:905`) |
| **vertices** | `flag_vertex == 1` | one row per graph vertex, `sub_cluster_id = −1`, `rr = −1` (`:864-889`) |
| **track vs shower** | `flag_shower` | `kShowerTrajectory ∨ kShowerTopology` (`:909-911`) |
| **particle type** | `particle_id` | the segment's PDG, or **4** = track with no hypothesis, **1** = shower with no hypothesis, **−1** on a vertex row (`:913-914`) |

Over the 870 scan items: median **5** segments (PDHD) / **4** (PDVD), p90 16/10,
max 42/31; median 6/5 vertices, max 42/34; median 310/271 PF fit points. **No
item has zero PF segments.**

#### 5.7.1 What is on screen

A `show particle flow` toggle draws the segments — each in its own colour — and
the junction vertices, in the 3-D view and the three projections, plus the
vertices and the picked segment in the nine measurement panels. A dropdown lists
every segment with its point count, length and median dQ/dx; picking one
highlights it everywhere in amber and prints its numbers.

The toggle defaults **off**, so the view a scanner already knows is unchanged
until they ask for the graph.

#### 5.7.2 What you tag, and why per segment is well posed

For the picked segment: **muon**, **Michel**, **delta / other**, **straddles the
stop**, or untag. The tags are drawn as **hollow squares** — a channel no other
marker on the page uses — so a scanner's own answer can never be read as the
reconstruction's colour.

"Straddles the stop" exists because per-segment tagging is *almost* but not
always well posed. Measured over 25 events per detector, joining each PF point
to the chain point at the same position and asking which `role`s a PF segment
carries:

| | one side only | muon ↔ Michel straddle | muon + delta | delta only | Michel only |
|---|---|---|---|---|---|
| PDHD (780 segments) | 0.760 | **0.035** | 0.205 | 0.068 | 0.029 |
| PDVD (472 segments) | 0.790 | **0.066** | 0.144 | 0.040 | 0.072 |

So the boundary the scan is actually about — muon versus Michel — is straddled
by only 3.5 % / 6.6 % of segments. The common mixing is delta-plus-muon (a delta
ray on the muon body), which the alphabet already separates. Without the
straddle button those few per cent would be forced into a coin flip.

#### 5.7.3 The blind, and the selector trap

`CheckSTM_Michel.cxx:1184` sets the Michel arm's type to **11**, so
`particle_id` and `flag_shower` **are** the chain's Michel verdict — 93 % of
role-3 points carry pdg 11 and 99.3 % of role-1 points carry pdg 13. They live
in the verdict block behind REVEAL, exactly like `role`. The *topology* — which
segments exist, where they run, where the junctions are — is the PR graph rather
than the STM verdict, and is always available.

**The rows are selected by `sub_cluster_id // 1000`, never by `cluster_id`.**
`T_rec_charge`'s `cluster_id` branch is bound to `reco_mother_cluster_id`
(`:737`, `:857`) — the id of the *group*, chosen once per fill and shared by
every cluster in it. Selecting on it is silently wrong: on PDHD `028084_0` it
returns **zero** rows for two of the five STM candidates (their own ids are 35
and 117, their mother's are 34 and 116) and *another cluster's* segments for the
rest. Over the first 8 events of each arm the two selectors differ on **7 of 32**
PDHD candidates (6 of them getting nothing) and **12 of 37** PDVD candidates.
The self-test asserts that this trap still reproduces, so the reason for the
selector cannot quietly rot away.

#### 5.7.4 The one thing that is NOT available — and it is worth fixing

`T_stm_michel_pts` carries a `seg_id` computed by the **identical formula** as
`T_rec_charge.sub_cluster_id` — `cluster_id × 1000 + graph index`
(`CheckSTM_Michel.cxx:668-669` vs `PdvdPrMagnifyTrackingVisitor.cxx:905`) — and
the two are nevertheless **not the same partition of the same points**. Measured
over 25 events per detector, with the correct selector and matching points by
position:

| | `seg_id == sub_cluster_id` | chain segment → exactly one PF segment | PF segment → exactly one chain segment |
|---|---|---|---|
| PDHD | 0.3771 | 0.2599 (277 segments) | 0.7977 (692 segments) |
| PDVD | 0.5499 | 0.3251 (203) | 0.8144 (431) |

Neither is a refinement of the other: they **cross-cut**. This doc does not
claim to know why — that would need tracing, and a plausible-looking line is not
a defect site. What is measured is that the two ids are not a shared identity,
and the consequence is concrete:

- **Nothing here may be joined by id.** The display joins the chain and the PF
  **by position**, which is exact — every chain point matches a `T_rec_charge`
  point within 0.05 cm, 1.000 on both detectors and on every role (§5.4).
  An id join would look entirely plausible and be wrong on more than half the
  points.
- **The scorer inherits this.** A `pf_segments` tag is an answer about a **PF**
  segment while `role` is about a **chain** segment, so scoring the two against
  each other must go through the positional map, per point. §7 says so, and the
  scorer is not written to assume otherwise.

**The improvement to make in `CheckSTM_Michel`** — recorded here rather than
done, because it is a change to a production component and needs its own
default-OFF round: persist, alongside each chain point, the segment identity the
*visitor* will write, or have the visitor persist the chain's `seg_id`. Either
one makes the chain's roles and the PF segments joinable exactly, and would turn
the positional join above into an index lookup. Two branches' worth of change;
the rest of this display is already built to survive without it.

### 5.8 Knowing the labels are saved

Labels were already written atomically on every click, but "it was saved" was a
claim about a write that returned. Now every save **reads the file back** — it
re-opens `labels.json`, re-parses it, and reports the count, byte size and
modification time *from that parse*. A green banner under the buttons says what
the file holds; a `what is saved on disk?` button re-reads on demand and prints
this item's own saved row, including its pin and its segment tags.

The distinctions the banner makes, all of which have been wrong somewhere:

- **a file that does not exist yet** reads back as *"nothing saved yet"*, not as
  an error — otherwise a fresh `--scan-tag` cries wolf on every start;
- **a file that exists but will not parse** reads back as **NOT SAVED**, in red,
  rather than as saved;
- **the count comes from the file, never from `LABELS` in memory** — the
  self-test adds a phantom label to the in-memory dict and asserts the banner
  does not count it;
- **segment tags placed before any label** are held, not saved, and the banner
  says so in amber; tagging an item that *already* has a saved row writes
  through immediately and re-reports the read-back.

## 6. The blind, and one honest limit

Two published rules pull in opposite directions here and both are right:

- `feedback_blind_the_scan_sheet` — a scan validating a proxy must not show the
  proxy's answer, or the agreement number measures nothing.
- `feedback_scan_display_must_show_the_evidence` — a display that draws only a
  reconstruction *product* withholds the measurement the verdict is about. Doc
  pr/148 measured the cost: re-scanning 36 objects with the charge added
  **changed 6 answers**, one of them the round's conclusion.

The resolution is the table in §5: the **charge** is unconditional, the **answer**
is behind `REVEAL`, and every label records `revealed_before_label`.
`score_stm_michel_scan.py` scores revealed and hidden labels **separately** and
never merges them. This is the `pdhd/d08_scan` pattern, and it is deliberately
*not* the sibling `pdhd/stm_scan` pattern, whose blind is structural (it refuses
to open the layers) — here the chain's Michel is the thing under test, so it has
to be showable; the discipline moves from "cannot" to "recorded".

**Which half of the blind is structural, precisely.** In the *display* it is
structural and proved: §10's first gate poisons the payload's `verdict` key with
a value nothing else could produce and searches every `ColumnDataSource` on
screen for it with `REVEAL` off. On the *key file* it is not. The key is
committed beside the sheet, and that is a deliberate trade: a scan whose key
lives only next to a `work/` arm stops being scorable the day that arm is
retired (`feedback_gate_source_arm_retired`), and these arms will be. So the key
carries a header saying in as many words that its blind is an **honour rule, not
a structural one** — including for an assistant asked to help with a scan. The
sibling scans in this tree (`pdhd_retile_scan_key.tsv`, `pr148`'s `.KEY.tsv`)
make the same trade; this doc is only refusing to describe it as more than it
is.

### 6.1 What the pin is

The scanner places the muon's stopping point: tap any panel to snap to the
nearest chain point, drag the residual-range slider, or type an x/y/z. The dQ/dx
panel re-anchors live, so the muon side and the Michel side separate exactly
where the scanner says — which *is* downstream goal 2.

### 6.2 What the pin is not — measured, not assumed

The plan for this round said the pin would start unset so that
`(hand − chain)` would score the chain's stop finder. **The self-test showed
that claim is false**, and it is recorded here rather than quietly dropped.

`stop_*` is not hidden: it **is** the last point of the muon chain, which has to
be drawn. Over all 870 items:

| | median | p99 | max | fraction < 0.01 cm |
|---|---|---|---|---|
| `\|chain end − stop_*\|` PDHD | 0.0000 | 0.87 | 3.37 cm | **0.9768** |
| `\|chain end − stop_*\|` PDVD | 0.0000 | 0.60 | 1.93 cm | **0.9771** |

So the pin measures **agreement**, not an independent placement, and the label
records `placed` and `moved_cm` so *"I looked and I agree"* (`placed=true,
moved_cm=0`) and *"I never touched it"* (`placed=false`) and *"I moved it 4 cm"*
are three different rows. The self-test re-measures the 0.977 on every run and
fails if it drifts below 0.90, so this paragraph cannot go stale silently.

What the blind *does* still withhold is what the scan is about: the Michel
verdict, the Michel / delta / dot segmentation, the 13 reject bits, and the
cosmic tagger's own stop — which differs from `stop_*` by a median 0.64 cm and
by up to **266 cm** on PDHD, and by a median 0.45 cm and up to 34 cm on PDVD.

## 7. What is saved, and why it is sufficient

```
label        STM_MICHEL | STM_ONLY | THRU | MESSY | UNCLEAR
choice       the button, incl. FRAG_STM_MICHEL / FRAG_STM_ONLY / FRAG_THRU
partial      true for a FRAG button; `label` still carries the FULL object's verdict
michel_kind  none | attached | detached dots | both
pin          {x, y, z, rr, placed, source, moved_cm, off_fit,
              unit, cru, face, unit_source}
revealed_before_label, notes, scan_id, tranche, event, cluster, npts,
muon_len_cm, det
pf_segments  {"<PF segment id>": "muon" | "michel" | "delta / other"
                                 | "straddles the stop"}      (round 3)
pf_tagged    how many segments carry a tag
n_pf_segments how many the cluster has, so a partial tagging is visible as one
```

`pf_segments` is **optional and additive**: the row written before it existed
loads, renders and scores unchanged, and the self-test asserts exactly that by
stripping the field from a saved row and reloading the app.

`FRAG` is three buttons and not one because *"the chain ends but grey charge
continues"* holds two opposite truths — a fragment of a through-goer (the tag is
wrong) and a fragment of a stopper (the tag is right, on a wrong-sized object).
Recording the full object's verdict plus `partial: true` costs the scan **no**
statistical power and makes the under-clustering rate its own number.

Sufficiency for the four downstream goals, so the schema can be checked rather
than trusted:

| goal | the fields that serve it |
|---|---|
| 1. select the topology robustly | `label` against the key's `is_stm` / `michel_found` gives purity **and** efficiency; the sole-reject-bit census then names what costs the most. Doc pdvd/48 §11 already measured `shape_flat` as 69 sole rejects, 26 of them Michel-carrying |
| 2. separate muon from Michel | `pin` is the boundary; `moved_cm` is the residual against the chain's own stop; the role partition scores against the pin. **`pf_segments` is the direct answer**: a hand assignment of each PR segment to the muon or the Michel, which is the separation stated as a per-object partition rather than as a single point |
| 3. the Michel energy spectrum | `michel_ke_best` on the rows the scanner called `STM_MICHEL` — the label **is** the sample definition |
| 4. angle vs momentum | `michel_kink_deg` (angle), `michel_ke_best`, and `muon_len` → muon momentum by range, on that same subsample |

`michel_kind` is asked of the scanner rather than taken from
`michel_conn_type`: the chain's 1 = attached / 2 = detached-dot is a decision,
not an observation, and goal 2 needs the observation.

**One trap `pf_segments` carries, stated here so the scorer cannot fall into
it.** A tag is an answer about a **PF segment**; `role` is an answer about a
**chain segment**; and §5.7.4 measured that those are not the same partition —
a chain segment maps to exactly one PF segment only 0.26 (PDHD) / 0.33 (PDVD) of
the time, and the reverse only 0.80 / 0.81. So `pf_segments` may **never** be
scored against `role` by joining segment ids, however identical the two id
formulas look. The comparison is per POINT, through the positional map: take each
PF point of a tagged segment, find the chain point at the same position (exact
to 0.05 cm), and compare the tag to that point's `role`. `straddles the stop`
rows are excluded from the agreement and counted separately — they are the
scanner saying the question was not well posed for that segment, which is a
datum about the segmentation, not a failure to answer.

## 8. The sample

One item per `T_stm_michel` row with `has_pass = 1`, `n_profile_pts ≥ 20` and
`muon_len ≥ 10 cm`. Strata live **in the key only** — never on the sheet, never
on the screen:

| | S1 `is_stm` & Michel | S2 `is_stm` only | S3 Michel only | S4 neither | total |
|---|---|---|---|---|---|
| PDHD, 61 events | **19** | 42 | 50 | 191 | **302** |
| PDVD, 120 events | **56** | 94 | 59 | 359 | **568** |

Tranche 1 is **60 per detector**, fixed seed 20260907: up to 24 from S1, then a
floor of 8 from each of S2/S3/S4, then round-robin to 60. Every item — all 870 —
gets a sidecar, so tranche 2 needs no re-prep. The sheet carries no stratum, no
verdict and no direction; the key carries all three and is read only by the
scorer.

Judgeability is the known risk here. Doc pdhd/stm-tagger-chain §13 measured the
unjudgeable rate as a clean function of object size — 100 % below 50 points,
95 % at 50–200 — and a bar clause resting on a stratum that came back 98 %
`UNCLEAR` returned its verdict mechanically, carrying no information. The
`n_profile_pts ≥ 20` and `muon_len ≥ 10 cm` floors are set against that, and the
scorer reports the unscored rate **per stratum** so a repeat is visible rather
than absorbed.

## 9. The bar, fixed before any label exists

`score_stm_michel_scan.py` computes, from hidden-label rows only:

- **purity** — of items the chain calls STM + Michel, the fraction the scanner
  also calls `STM_MICHEL`;
- **efficiency** — of items the scanner calls `STM_MICHEL`, the fraction the
  chain flags;
- both **re-weighted per stratum** by `n_parent / n_labelled`, because tranche 1
  takes every reco-positive item it can and only a floor from the rest, so a raw
  purity would be a purity of the *sheet*, not of the detector. Raw and
  reweighted are printed side by side and never substituted for one another;
- `is_stm` alone, Michel ignored, as the separable half;
- the 3 × 3 human-vs-chain confusion;
- the unscored (`MESSY` + `UNCLEAR`) rate per stratum;
- the under-clustering (`FRAG`) rate;
- the distribution of `moved_cm` over labels where the pin was placed.

`TRUTH` is a closed whitelist and an unknown label is a **hard error**: a bare
`else` folding an unrecognised label into a class is the silent failure the
table exists to prevent.

## 10. Gates

All run and passing at the time of writing.

| gate | result |
|---|---|
| the blind — poison the payload's `verdict` key with a value nothing else could produce, render with REVEAL off, search **every** `ColumnDataSource` on screen for it | PASS, both detectors |
| a `STM_MICHEL` label is **refused** while `michel_kind` is unset, rather than silently defaulting to `none` | PASS |
| the scorer runs end to end on synthetic labels covering all 8 buttons, both FRAG variants, revealed and hidden rows, placed and unplaced pins; and hard-errors on an unknown label | PASS |
| the answer lives under exactly one payload key | PASS |
| REVEAL brings it on and `revealed_before_label` records both directions | PASS |
| every one of the 8 labels round-trips; a `FRAG` label carries an object-level verdict | PASS |
| the pin: unset default = the min-`rr` chain point; tap-snap reproduced by brute force in all three panels; the dQ/dx panel re-anchors by **exactly** the pin's Δrr; every Michel/dot point lands on the negative side; slider, manual x/y/z, non-numeric refusal, reset on navigation; the saved pin carries a wire-derived unit and a `moved_cm` | PASS |
| a wire/geometry disagreement is **flagged**, not silently resolved | PASS |
| `unit_from_wire` vs the production wire file, 3 probes per (anode, face) block, plus out-of-range rejection, plus all 16 PDVD CRUs reachable | PASS |
| the prep's near/far split reproduced by brute force with no KD-tree | PASS |
| `dqdx_ref` grid, units, and the muon plateau against doc pdvd/50's published numbers | PASS |
| **the plane split, causally**: the fitter's own `pu/pv/pw` (written by `globalf`) must land on a `T_proj_data` cell of the same channel (written by `global`) within ±2 slices — two independently written code paths agreeing | PASS, published per plane (§5.4) |
| every projection cell and every `T_bad_ch` row falls inside its own plane's base block, and `smgeom.plane_from_chan` agrees with the vectorised split prep used, on all 155 735 / 326 301 cells | PASS |
| **ticks → slices, from the files not the config**: `max(end_time)/(max(time_slice)+1)` = 4.000 PDHD / 4.027 PDVD, and no drawn dead band ends past slice 4000 | PASS |
| the difference panel is `measured − predicted`, recomputed independently from the payload, cell by cell; the measured panel carries `T_proj_data.charge` verbatim | PASS |
| the three columns of a row share **both** ranges and all nine share the time range; dead bands are inside the drawn window | PASS |
| REVEAL gates the Michel/delta/dot overlays in measurement space too — sources empty **and** renderers invisible when off | PASS |
| the poison test walks the measurement sources as well, and the poisoned verdict now carries `pu/pv/pw/pt` — a poison that omitted them would leave the new panel untested | PASS |
| the dQ/dx scale is the fixed one; the `×0.5…×4` multiplier moves all six cell/residual mappers together | PASS |
| no colour in the dQ/dx palette exceeds 0.90 relative luminance, and every marker in that panel is outlined | PASS |
| **the click link**: driving a selection puts the cursor on the *same* point in the 3-D layer, all 3 projections and all 3 measurement rows; its `pu/pv/pw` are one per plane; deselect clears it; a re-render clears it; two series cannot stay selected at once | PASS |
| **the PF row selector**: selecting by `cluster_id` must give a *different* row set from `sub_cluster_id // 1000` on this arm — the trap is asserted to still reproduce (7/32 PDHD candidates, 6 getting none; 12/37 PDVD) | PASS |
| every PF segment belongs to its item's cluster, its columns are the same length, it has a `pf_type` entry, and its points split one wire per plane | PASS, 173 / 293 segments |
| the PF blind: the poisoned `pf_type` reaches no source **and** no Div with REVEAL off — pdg is rendered as text, so the source walk alone would miss it | PASS |
| the toggle gates the topology and nothing else; the segments are separately coloured; the inspector reports the id, point count and length of the segment that was **picked** | PASS |
| `pf_segments` round-trips, a tag on an already-labelled item writes through immediately, a tag with no label says it is **not** on disk, and a row with the field stripped still loads with no phantom tags | PASS |
| the save read-back: a missing file reads as *nothing saved yet*, a corrupt one as **NOT SAVED**, the count comes from the file and not from `LABELS` (asserted by adding a phantom in-memory label), and `save_info` names this item's row | PASS |
| **headless total** | **6252 checks, 0 failures** |
| a real mouse drag in headless chromium reaches the CustomJS; every layer moves with it; no row count changes; no point projects outside its own distance from the camera centre; no page errors | PASS |
| the measurement tab paints in a real browser on the **heaviest** item of the arm (22 106 / 20 574 cells, drawn three times), with the causal control that emptying the cell sources moves 748 / 877 painted pixels — the check that caught the sub-pixel `rect` bug, where it moved exactly 0 | PASS, first paint 1.6 s |
| the click link over the real websocket: set the selection **in the browser**, assert the cursor reaches the 3-D layer and all three measurement panels on the point's own wire and slice | PASS |
| the `show particle flow` toggle and the segment dropdown pressed as **real widgets** in the browser, so the server callback and the round trip back are both exercised | PASS |
| **browser total** | **39 checks each detector, 0 failures** |
| `serve_*.sh` refuses a busy port (rc=2, names the owning pid) | PASS |
| labels live in `work/stm_michel_labels/<tag>/`, a sibling of the per-event dirs | by construction |

The browser gate is worth naming: `em3d.py`'s own docstring records the honest
limit *"there is no JS engine and no node in this tree, so the CustomJS is not
machine-tested"*. That is true of `sbnd_xin` and not of this tree — playwright is
in the `.direnv` python — so the fork narrows the caveat instead of inheriting
it. The invariant it checks is the useful one: `right/up/fwd` is orthonormal, so
`u² + v² ≤ |p − centre|²` at **every** camera. A sign error in the JS breaks
that; a "did the pixels change" test would sail past it.

Two things are deliberately **not** gated, because they are measurements and not
pass/fail: the wire-vs-geometric agreement (§4.3) and the chain-end/`stop_*`
identity (§6.2). Both are printed on every run, and the second fails only if it
drifts far enough to invalidate §6.2's prose.

## 11. Limits

1. **The pin is a confirmation, not a blind placement** (§6.2). Any statement
   of the form "the scanner independently found the stop to X cm" would be
   wrong; the honest statement is "the scanner moved the chain's drawn stop by
   `moved_cm`".
2. **One arm, one epoch.** Everything is the `d51hnu` / `d51vnu` arms at HEAD
   `c0b1613b`. The labels are about *those* reconstructions. A chain change
   invalidates the key, not the labels — re-prep and re-score, and a re-scan is
   a new `--scan-tag` (M13).
3. **`michel_ke_best` carries no recombination or dead-region correction**
   beyond the fitter's (doc pdvd/48 §4 item iii). The spectrum in goal 3 will
   need one; this scan only defines the sample.
4. **Only the flash bundle is visible.** A Michel brem blob that did not make
   the muon's bundle is invisible to the chain *and* to this display's
   full-density set if it is more than 40 cm from the stop.
5. **870 items is not the detector.** 61 PDHD + 120 PDVD events of two runs
   each; no statement here is a rate per unit exposure.
6. There is **no `stm_michel` Bee layer** — doc pdvd/48 §5 and §9 item 2
   deferred it, and the roles live only in `T_stm_michel_pts`. This display is
   the substitute, not a replacement for that decision.
7. **Inside a dead region the residual panel compares a model with a model**
   (§5.4 item 3). `T_proj_data` collapses the live/dead flag, so `charge` there
   is `prepare_data`'s filler. The hatched overlay marks exactly where this
   applies; nothing in the panel can distinguish a filler from a reading.
8. **`nticks_per_slice` is one number per detector here**, while the C++ reads
   it per `(apa, face)`. Both production configs set it globally, so the two
   agree today; a config that varied it per face would silently shift the dead
   bands on the faces that differ.
9. **The residual drawn is the raw difference**, matching Magnify and the ask.
   The statistically correct residual is the pull `(measured − predicted) /
   charge_err`, and `charge_err` is already in the payload — a one-line addition
   if it turns out to be the more readable panel.
10. **The chain's `seg_id` and the PF's `sub_cluster_id` are not a shared
    identity** (§5.7.4). Everything here joins by position instead, which is
    exact; but any *future* analysis that reaches for the id join will be wrong
    on more than half the points and will not look wrong. This is the one thing
    §5.7.4 names as worth fixing in `CheckSTM_Michel` itself.
11. **`pf_segments` is the scanner's segmentation of the PR graph, not of the
    truth.** Where the PR graph itself is wrong — a Michel merged into the muon
    body as one segment — the best available tag is `straddles the stop`, and
    that row measures the segmentation rather than the scanner.

## 12. Next step

**Scan tranche 1 on PDVD first.** Its S1 is 56 items against PDHD's 19, so PDVD
is where purity becomes measurable at all this round, and PDVD is the detector
whose CRU label §4.3 just earned. Then run the scorer and read one number before
anything else: the **efficiency** of `michel_found`. Doc pdvd/48 §11's sole-bit
census already says `shape_flat` is the dominant sole rejector and carries 26
Michel-bearing candidates with it — if the hand labels agree that those are real
STM + Michel objects, the next code round is `shape_flat`, and the scan will
have named it rather than guessed it.

Offered, not done: a Bee set of whatever tranche 1 confirms, so the same objects
can be turned in Bee alongside this display; and the two `Branch` lines of §4.3
that would put `apa`/`face` in `T_rec_charge` and retire the sentinel-wire
caveat entirely.
