# PDHD: a space-charge fiducial volume from exit-gap quantiles, and what it does to the cosmic taggers

**Status:** PDHD PRODUCTION since 2026-09-07 at **exit-gap p90 + 3 cm cushion**
(owner decision, sec 12).  Set in the driver `pdhd/wct-pr-perevt.jsonnet`; the
`pr.jsonnet` function defaults stay OFF, so a caller passing nothing still gets
the byte-identical legacy box.

PDHD's cosmic taggers test a flat box inset by a uniform 15 cm space-charge
allowance that was **adopted, never measured** — the same construction PDVD
carried until docs pdvd/41 and pdvd/43 replaced it with a measured surface. This
doc makes the PDHD measurement and wires the result in as a default-OFF
alternative, following `cfg/pgrapher/experiment/pdhd/pr.jsonnet`'s own
instruction:

> `pr.jsonnet` (pre-doc-09): *"If a PDHD exit-gap map is ever made, port the four
> arguments and the `curved_fv_cfg` / `mgn_*` locals from protodunevd/pr.jsonnet
> verbatim."*

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
S=docs/scripts; T=/home/xqian/tmp/d09
export LD_LIBRARY_PATH=/home/xqian/tmp/d09_libpin/pin      # binary pin, sec 1

# --- Phase 1: Q/L run 28084, all 31 events (DNN-ROI + L1SP, gain 14) ---------
EVENTS=all JOBS=6 $S/d09_run_chain.sh                       # -> work/028084_<idx>_d09/
# --- Phase 2: the 029107 controls -------------------------------------------
$S/d09_stage_ref.sh                                         # June imaging + pinned Q/L
$S/d09_stage_ctl.sh                                         # re-imaged under the pin  <- the control
python3 $S/d09_ql_stats.py --tag d09    --run 028084 --out $T/ql_28084.json
python3 $S/d09_ql_stats.py --tag d09ctl --run 029107 --out $T/ql_29107.json
python3 $S/d09_ql_compare.py $T/ql_29107.json $T/ql_28084.json
# --- Phase 3: the OFF arm ----------------------------------------------------
ARM=d09fvoff $S/d09_run_pr_arm.sh
# --- Phase 4: the exit census and the surface --------------------------------
python3 $S/d09_exit_census.py     --tag d09fvoff --out $T/exits
python3 $S/d09_quantile_surface.py $T/exits_rows.json --out $T/q
python3 $S/d09_quantile_offline.py $T/exits_rows.json --out $T/off
# --- Phase 6: the ladder -----------------------------------------------------
ARM=d09p90c5 PR_TLA="-S curved_fv=true -A curved_fv_profile=p90 \
    -S curved_fv_margin_y=5 -S curved_fv_margin_z=5" $S/d09_run_pr_arm.sh
```

## 1. Binary pin

`/home/xqian/tmp/d09_libpin/pin` (230 files, 2.5 G), taken 2026-09-06. A 5-arm x
61-event campaign spans days on a shared tree, and doc pdvd/43 lost a round to a
rebuild between arms.

| library | md5 |
|---|---|
| libWireCellClus.so | b3495810c15bf663c4a55e3f335b48a9 |
| libWireCellAux.so | e86c87808585efb11bdf565d2560d20e |
| libWireCellMatch.so | 9b34214131bd09bc77c52b4b67bbdded |
| libWireCellImg.so | 681378e33f0d97fe64636d1c6f1a27da |
| wire-cell | 8a43c53b721f92249d50938f850f2b5b |

## 2. Three pre-flight findings

### 2.1 Run 28084 is 14 mV/fC, not 7.8

Measured, not looked up: the median per-channel noise (MAD x 1.4826) of
`protodunehd-orig-frames-anode0.tar.bz2`.

| run | events checked | median channel MAD [ADC] | implied gain |
|---|---|---|---|
| 028084 | evt 0, 5, 18, 30 | **13.0** (19.27 ADC RMS) | **14** |
| 029107 | evt 0, 5, 18 | 7.0 (10.38) | 7.8 |
| 027980 | evt 0 | 7.0 (10.38) | 7.8 |

Ratio 13/7 = 1.857 against 14/7.8 = 1.795; the residual is integer-MAD
quantization. `input_data_7p8_new_coh_grouping/META.json` agrees.

**The trap:** that directory name records the *coherent-noise grouping epoch*,
not the gain, and both NF/SP runners auto-derive a gain from it
(`run_nf_sp_dnnroi_evt.sh:303`), yielding 7.8. Every event in this campaign runs
with an explicit `-g 14`.

### 2.2 The pre-existing 28084 work dir is a different reconstruction chain

`work/028084_18` holds *traditional* SP frames while the entire 029107 reference
set is DNN-ROI. Any comparison across the two is cross-chain. All 31 events were
therefore reprocessed through `run_nf_sp_dnnroi_evt.sh -g 14 -L on -N dnn`, into
the fresh `_d09` tag; `work/028084_18` itself is untouched (M13).

### 2.3 The taggers do run on t0-corrected coordinates

A curved surface is meaningless unless x is the true drift coordinate. Every PDHD
tagger is built from the `cm` clustering_methods (`pr.jsonnet:1430-1728`), whose
`coords` is `clus_maker.t0cor_coords`; `cm_old` (`scope_coords`) is used only by
`switch_scope`. The exposure a polygon adds over a box is a *wrong* t0, which is
now y/z-dependent.

## 3. Correction: PDHD production DOES carry the flat 15 cm shell

`pr.jsonnet`'s function defaults are x 2.5 / y 3 / zmax 5 / zmin 3 cm — the SBND
operating point, and **not** what PDHD runs. The driver overrides them:

```
pdhd/wct-pr-perevt.jsonnet:1289-1294
    tgm_fv_x_margin = 2, tgm_fv_y_margin = 17.5, tgm_fv_zmin_margin = 18
```

Read off the compiled config rather than the source, `TaggerCheckTGM`'s own data
block carries `fv_tolerance = [-20,-20,-175,-175,-180,-180]` WCT mm, i.e.
x 2 / y 17.5 / z 18 cm. The arithmetic closes exactly on the clustering FV
(15 cm space charge + the dvm per-face margins), the same construction PDVD
adopted in doc pdvd/35.

So PDHD sits in exactly the pre-doc-41 PDVD state, and the consequences are:

* the knob is **not** a pure tightening — it must remove the 17.5/18 shell *and*
  install the surface together, because that 15 cm **is** the allowance the
  surface replaces and carrying both would count it twice;
* the expected direction is PDVD's: **TGM down, fully-contained up**;
* the hand scan therefore targets the tags the knob **removes**.

## 4. Q/L on run 28084, and how it compares to 029107

All 31 events (DAQ idents 74408 + 8*idx, verified from the tar members) went
through NF/SP + DNN-ROI + L1SP at gain 14, imaging, all-PD light and
clus + Q/L + calib, into the `_d09` tag.  31/31 carry a calib dump and a pctree
with the `perblob` provenance `unmerge_assoc` requires.

### 4.1 Two accounting traps in the calib dump

Both were caught because the first `matched / input` came out ABOVE 1:

* **`main_cluster` keys on `uid`, not `ident`.**  `ident` is not unique across
  drift sides (91 distinct values for 101 clusters in 028084/74408).
* **The dump's `apa` field is the per-drift-side ApaRun index, not the WCT APA
  number.**  Verified on the dump's own geometry: `apa=0` holds x in
  [-353.2, +119.0] (group02, APA0/2), `apa=1` holds [-119.5, +353.0] (group13),
  and its `opdets` sit at x = -356.4 / +356.2.  Those x ranges independently
  reproduce the raw readout-window constants of sec 6.

### 4.2 The control needs three arms, not one

029107's products on disk predate the pin by months, so "28084 vs 029107" would
have been part run and part binary:

| arm | imaging | light | clus + Q/L |
|---|---|---|---|
| `d09ref` | 2026-06-17 | 2026-07-08 | pinned |
| `d09ctl` | **pinned** | 2026-07-08 | pinned |
| `d09ctl2` | **pinned** | **pinned** | pinned |

`libWireCellImg.so` is 2026-09-05 and the flash libraries 2026-09-05/06.
`d09ctl2` vs the 28084 `_d09` arm is run-only; the intermediate arms attribute
any residual to imaging or to light.  All three are fresh tags — the June/July
products are untouched (M13).

**The result is that neither epoch matters, and that is worth recording**: all
three arms agree to three decimals on every metric (chi2/ndf 4.749, flashes 253,
pred/meas 0.121, matched/input 0.989).  The reason is not that the arms were
mis-staged — checked, because "identical" is exactly what a staging bug looks
like.  `work/029107_0_d09ctl/clusters-apa-apa0-ms-active.tar.gz` is a real 8.02 MB
file written 2026-09-07T04:23, and its **member-content hash equals June's**
(`6de2d0dc...`, 12 members, via `abtest/hash_archive.py` — never a raw byte
compare, M2).

So PDHD imaging is exactly reproducible across the 2026-06-17 -> 2026-09-05 span
of `libWireCellImg.so`, and the light reco across 2026-07-08 -> 2026-09-06.  The
029107 reference set on disk is therefore usable as-is; the three arms cost ~20
minutes and converted an assumption into a measurement.

### 4.3 The one systematic difference, and what causes it

28084's `chi2/ndf` runs high: 14 of its 31 events sit above 029107's maximum.
`pred/meas` PE is correspondingly low, and 28084 has FEWER flashes.  Those three
are one effect, and the decomposition says which side it is on:

| | 28084 | 029107 |
|---|---|---|
| predicted PE, median bundle | 22.5 | 20.3 |
| **measured PE, median bundle** | **1118.6** | **494.3** |
| cluster charge, median | 76,004 | 80,356 |
| npoints, median | 20 | 22 |

**Predicted PE and cluster charge agree between the runs.**  The charge scale at
gain 14 and the light model are therefore both sound; what differs is the
MEASURED light — 28084's flashes are fewer and 2.3x brighter, i.e. the flash
finder merges light differently in that run.  A merged flash inflates `chi2`
(measured >> predicted) and depresses `pred/meas` exactly as observed, without
any charge-side defect.

This matters for the map only if merging also moves the flash TIME, because the
map consumes the t0 the match assigns.

### 4.4 It does not.  The run-split anode control settles it

A wrong t0 shifts x.  So it moves the gap at the ANODE planes, which are an
x-direction measurement, and leaves the transverse y/z gaps alone.  The
`d09fvoff` census split by run separates the two.

**The estimator has to be conditioned the same way the surface is.**  A median
over ALL ends assigned to a plane is dominated by non-exits (the anode sample's
mean gap is ~72 cm against a median of ~5), and it is far too noisy to answer
this: it gives 028084 - 029107 = +2.97 +- 5.95 cm, i.e. 0.5 sigma, which says
nothing.  Restricted to actual exits (gap < 40 cm, readout-edge ends removed) —
exactly the sample the quantiles are read from — it is decisive:

| sample | n | anode-exit gap to the collection plane |
|---|---|---|
| 028084 | 106 | **1.29 +- 0.04 cm** |
| 029107 | 103 | **1.26 +- 0.03 cm** |
| difference | | **+0.02 +- 0.05 cm = +0.1 +- 0.3 us of t0 (0.4 sigma)** |

and the transverse walls agree independently:

| wall | 028084 | 029107 | difference |
|---|---|---|---|
| y+ | 2.96 +- 0.92 | 4.96 +- 0.92 | -2.01 +- 1.30 (1.5 sigma) |
| y- | 4.03 +- 0.73 | 3.85 +- 0.56 | +0.19 +- 0.92 |
| z- | 4.79 +- 1.16 | 4.75 +- 1.04 | +0.05 +- 1.55 |
| z+ | 4.55 +- 0.99 | 3.88 +- 1.41 | +0.67 +- 1.73 |

chi2/ndf against "no difference" = 0.64 on the four transverse walls.

**There is no measurable x offset between the runs**, so the flash-merging
difference of sec 4.3 does not move the fitted t0, and 28084 carries the map on
the same footing as 029107.

The conditioned anode control is also the instrument's own null test, and it
passes: imaged charge stops **1.3 cm** short of the collection plane in both runs.
(PDVD's read -2.5 cm, an overshoot; both are cm-level.)  Note PDHD's FV bound
357.985 and its collection plane 353.1 differ by 4.9 cm where PDVD's coincided —
that pedestal is subtracted here, and being an x-direction offset it does not
propagate into a transverse surface in any case.

## 5. The instrument

Doc pdvd/43's exit census, ported.  Every end of every long (> 2 m, >= 40 pt)
Q/L-matched cluster is assigned to exactly ONE surface: the first of six planes
that the ray from the end, along the track's outward local direction, crosses.
The record is the signed perpendicular gap.

Why an exit census and not a closest-approach one: doc pdvd/41 sec 13 built its
table from "closest approach within a cap", which is contaminated by tracks that
merely PASS a wall on the way out through another — and that contamination IS the
tail a quantile reads (raising PDVD's cap 25 -> 40 cm moved its anode-half p90
from 15 to 26 cm).

Ported verbatim: the t=0 clamp for an end at or beyond its plane (without it 40 %
of ends are handed to a plane 250 cm away); orientation by the cluster's global
axis with a fallback below |cos| 0.7; the readout-edge exclusion; the flat
non-exit floor measured over 40-150 cm and subtracted; 300 bootstraps **of ends**
(doc 41 bootstrapped events — a different resampling unit); PAV regularization
non-increasing toward the anode.

PDHD-specific changes, all forced by the detector and all in `d09_fv_pdhd.py`:

* **y is not symmetric.**  PDVD's walls are +-336.39, so its ray list is
  (+YW, +1) / (-YW, -1); PDHD's are 7.61 and 606.0, so the pair becomes
  (YHI, +1) / (YLO, -1).  This is the only structural edit.
* `XW` 357.985, `ZLO/ZHI` 0.234345 / 462.297, `CATH` 2.54; four ~84 cm drift bins
  per volume (PDVD 80).
* Volume keys `_g02` (x<0, APA0/2) and `_g13` (x>0, APA1/3).
* `RAW_EARLY / RAW_LATE` = 353.1 / 119.2 cm, **measured** from the pctree raw-x
  extremes, not derived.  Cross-check: 353.1 + 119.2 = 472.3 cm against 5999
  ticks x 0.5 us x 0.1576 cm/us = 472.7 cm — agreement to 0.4 cm, which confirms
  the tick count and the calibrated drift speed together.
* PDVD's `--d50` argument is dropped.  It was `required=True` there but fed only a
  printed column and a figure — the emitted knots never depended on it — so PDHD
  does not have to reproduce doc pdvd/41's withdrawn half-density map first.

## 6. The measured surface

`d09fvoff`, 61 events, one pinned binary (fingerprint identical before and after
the arm): **2218 ends of long clusters, 299 at a readout edge excluded.**
Distribution by wall — y+ 625, y- 609, z- 338, z+ 311, anode 335 — which is the
expected shape for a horizontal-drift detector whose cosmics run along y.

The signature is monotone on all eight profiles: the median inset falls from
7-13 cm at the cathode to **0.4-1.5 cm in the anode-most bin**, i.e. the
anode-side control returns the nominal wall.

**Statistics gate.**  8 of 32 bins hold fewer than 20 in-window ends (it was 20 of
32 at 30 events).  Every one is on a z wall — z-/z+ are the narrow side for
cosmics here, the mirror of PDVD's y+ problem.  They are listed by name in the
header of `curved_fiducial_profiles.jsonnet`; PAV smooths but does not manufacture
statistics, and a starved bin must not be allowed to hide inside it.

## 7. Grading: the per-exit-end miss rate

The primary number, and it ranks the ladder without running an arm: of the ends
that genuinely EXIT through a wall, what fraction does the boundary wrongly call
CONTAINED?  1340 in-window exit ends.

| boundary | in sample | held out 028084 | held out 029107 |
|---|---|---|---|
| **flat (PDHD production)** | 11.0 % | 11.3 % | 10.8 % |
| p80 + 3 | 13.9 % | 15.3 % | 13.3 % |
| p80 + 5 | 11.3 % | 13.3 % | 11.2 % |
| p90 + 3 | 7.2 % | 10.1 % | 8.9 % |
| **p90 + 5** | **6.0 %** | **8.8 %** | **7.6 %** |

The cross-validation is stronger here than PDVD could manage: two independent
runs, so the surface is built without the run it is graded on.  The ranking is
stable across both splits, and p80 is WORSE than flat — the same shape doc
pdvd/43 found for d50.

The flat shell is also badly **unbalanced**: it misses 7.4 % of anode-half exits
but 13.7 % of cathode-half ones.  p90 + 5 reads 5.5 / 6.4.  That imbalance is the
signature of a uniform inset on a boundary that curves, and it is why PDHD gains
more from the surface (11.0 -> 6.0 %) than PDVD did (7.5 -> 6.7 %).

## 8. Is the tail space charge, or imaging?

This is the test that overturned doc pdvd/41, and it must be answered before any
surface is emitted.  PDHD has a structural reason to fear it: read out of
`protodunehd-wires-larsoft-v1.json.bz2`, U and V run at +-35.71 degrees but **W is
exactly vertical (0, 1, 0)** — and PDHD's cosmics are vertical too, so 69 % of
exit ends run along the collection strips, the prolonged-signal case.

It does not bite.  Splitting the census by |cos| to the nearest plane's strips:

| | n | > 8 cm short | p80 |
|---|---|---|---|
| parallel to strips | 1298 | 51.6 % | 96.6 |
| not parallel | 585 | 54.7 % | 80.7 |

PDVD's equivalent split was 26.5 % against 12.6 %.  PDHD's is flat.

The number that matters is how much of the EMITTED inset is angle-correlated —
p90 rebuilt from non-parallel ends only, over p90 from all ends, on the cathode
half where the inset lives:

| wall | ratio |
|---|---|
| y+ | 1.15 |
| y- | 0.97 |
| z- | 0.83 |
| z+ | 1.01 |

All approximately 1.  **The inset survives the decomposition**, so PDHD's tail is
drift field and not reconstruction — the opposite of PDVD's first attempt.

Readout-edge ends are a real and separate effect: 12.4 % of side-wall ends, of
which 90.2 % stop more than 8 cm short against 47.0 % away from an edge.  They are
excluded from the surface.  Note that PDHD's `stm_readout_edge_guard` is default
OFF (`pr.jsonnet:91`) and TGM/FC have no such guard at all — the same open defect
doc pdvd/41 R4 named on PDVD.  **Reported, not fixed here**: it is a C++ change
with an A/B of its own.

## 9. What the surface does to the taggers

Arms are `d09fvoff / d09p80c3 / d09p80c5 / d09p90c3 / d09p90c5`, 61 events each,
one pinned binary (fingerprint identical before and after every arm).  Verdicts
come from the taggers' own per-cluster log lines; the two arms are asserted to
expose identical cluster-id sets per event before anything is differenced.

### 9.1 The direction is the OPPOSITE of PDVD's, and the reason is measurable

PDVD's curved surface LOOSENED its tagger volume (its flat 17.5/18 shell was far
larger than its measured p90, whose anode half is 5.6 cm), and TGM fell 33 %.
PDHD's measured p90 is much bigger — its anode-half p90 reaches 18.9 cm — so the
same flat shell UNDER-covers, and the surface is a net tightening.  Effective
inset, flat vs p90 + 5 cm, at four drift positions (cm; positive = ON is tighter):

| wall | \|x\|=330 | 210 | 126 | 43 |
|---|---|---|---|---|
| ym_g02 | +6.4 | +6.4 | +8.9 | +9.1 |
| zp_g13 | +6.1 | +15.1 | +15.1 | +15.1 |
| yp_g02 | **-5.9** | +2.4 | +2.4 | +8.1 |
| zm_g02 | **-4.1** | -4.1 | +10.0 | +10.0 |

28 of 32 sampled points are tighter.  Hence TGM RISES: 1561 -> 1843 (+18.1 %) at
p90 + 5, fully-contained 2180 -> 1980 (-9.2 %), STM 318 -> 329.

### 9.2 The raw TGM count is not a usable metric on PDHD

Decomposed by track length, the count is dominated by objects that are not tracks:

| arm | 0-10 cm | 10-50 | 50-100 | 100-200 | **> 200 cm** | total |
|---|---|---|---|---|---|---|
| flat (PRODUCTION) | **724** | 133 | 86 | 105 | **430** | 1478 |
| p90 + 3 | 815 | 165 | 95 | 125 | **464** | 1664 |
| p90 + 5 | 879 | 173 | 96 | 127 | **469** | 1744 |

**49 % of the production arm's TGM tags are already under 10 cm.**  That is
pre-existing, not something the surface introduces — the sub-10 cm SHARE is
essentially unchanged (49.0 -> 49.0 -> 50.4 %).

So the adjudicating metric is long-track TGM, as it was in doc pdvd/43:
**430 -> 464 (+7.9 %) at p90 + 3, -> 469 (+9.1 %) at p90 + 5**, which agrees in
sign and roughly in size with the independent offline miss rate (sec 7).

### 9.3 The defect behind the sub-10 cm tags, named and traced

`TaggerCheckTGM.cxx:1066`, inside CASE A (both ends outside the FV):

```cpp
else {
    if (out_vec_wcps.size() == 2) return true;
```

A cluster with exactly two extreme-point groups whose ends both fall outside the
fiducial volume is tagged through-going with **no interior-support requirement and
no length requirement**.  Traced on the data rather than read off the source, with
the tagger's own `WCT_TGM_DEBUG` instrumentation:

```
check_tgm dbg: cluster 2 pair (0,1) ngrp 2 pe1 (-1.8,183.5,22.5) pe2 (-1.5,181.9,22.5)
               mid_inside false len 1.6/1.6 cm
visit: TaggerCheckTGM: cluster 2 -> TGM=true
```

a **1.6 cm** object, no interior support, tagged.  9 of 41 CASE-A pair evaluations
in that single event take this path.  `component_min_length` (10 cm) does not
gate it — it only filters which components donate extreme points.

This is shared code, so it is not a PDHD-only defect: doc pdvd/41 R3's lost
population had the same shape (409 of 670 under 50 cm).  **Reported, not fixed
here** — it is a C++ behaviour change needing its own default-OFF knob and A/B,
and fixing it inside a config round would confound this one.

### 9.4 The scan

Panels rendered for both strata of the p90 + 3 gains and scanned directly (the
doc pdhd/03 `d03_render` substitute; each panel shows the cluster's own points,
both PCA ends, and BOTH boundaries, so the reader can see which boundary moved the
verdict).  Note the green markers are PCA ends — a proxy for the tagger's extreme
points, and doc pdvd/41 R4 warns the proxy is loose for outliers.

* **Long gains (> 2 m): genuine.**  e.g. 028084/7 cluster 112, 529 cm, 5542 pts,
  running from the top y wall at the cathode to the anode face; 028084/1 cluster
  145, 274 cm, 1966 pts, bottom y wall to the z+ wall.  Both ends on walls.
* **Short gains (< 50 cm): spurious.**  e.g. 028084/8 cluster 2 — 2 cm, 9 points,
  sitting at the cathode near the z- wall; 028084/0 cluster 85 — 4 cm, 21 points,
  isolated in the middle of the detector in y.  These flip because the tighter
  boundary crosses them, and sec 9.3 then tags them without further test.

### 9.4b STM is essentially untouched -- and its denominator is not

`TaggerCheckSTM` skips clusters already TGM-tagged, so a change in TGM moves the
set STM is even allowed to evaluate.  On PDHD the skip count equals the TGM count
exactly in every arm, which confirms the mechanism:

| arm | TGM | STM=1 | skipped | evaluated | STM/evaluated | STM > 2 m |
|---|---|---|---|---|---|---|
| flat (PRODUCTION) | 1561 | 318 | 1561 | 4318 | 7.36 % | 86 |
| p80 + 3 | 1432 | 316 | 1432 | 4447 | 7.11 % | 83 |
| p80 + 5 | 1528 | 315 | 1528 | 4351 | 7.24 % | 83 |
| p90 + 3 | 1755 | 320 | 1755 | 4124 | 7.76 % | 85 |
| p90 + 5 | 1843 | 329 | 1843 | 4036 | 8.15 % | 84 |

The STM total moves by at most 11 of 318 (3.5 %) and long-track STM by at most 3
of 86, while the evaluated set shrinks by 282.  So the surface does **not**
disturb the stopping-muon sample; the rate per evaluated cluster rises only
because TGM removes more candidates from the front of the queue.

Per-cluster flips confirm it is a queue effect and not a re-classification:

| arm | STM gained | (of which previously skipped as TGM) | STM lost | (of which became TGM) |
|---|---|---|---|---|
| p80 + 3 | 38 | 30 | 40 | 11 |
| p80 + 5 | 33 | 20 | 36 | 12 |
| p90 + 3 | 31 | 7 | 29 | **25** |
| p90 + 5 | 43 | 11 | 32 | **28** |

For the p90 arms almost every lost STM is a cluster that became TGM — the two
taggers trading a verdict, not one of them getting a track wrong.  The doc pdvd/25
stopping-muon census is the sentinel to re-run before any flip.

### 9.5 The full ladder

| arm | 0-10 cm | 10-50 | 50-200 | **> 200 cm** | TGM total | STM | FC |
|---|---|---|---|---|---|---|---|
| flat (PRODUCTION) | 724 | 133 | 191 | **430** | 1478 | 318 | 2180 |
| p80 + 3 | **617** | 115 | 187 | 440 | 1359 | 316 | 2295 |
| p80 + 5 | 676 | 132 | 196 | 445 | 1449 | 315 | 2222 |
| p90 + 3 | 815 | 165 | 220 | 464 | 1664 | 320 | 2058 |
| p90 + 5 | 879 | 173 | 223 | **469** | 1744 | 329 | 1980 |

**Every rung beats the flat shell on long-track TGM.**  That is the strongest
single statement this campaign can make: whatever operating point is chosen, the
measured surface recovers through-going muons the uniform inset was missing, and
the recovery is confirmed independently by the offline per-exit-end miss rate,
which never saw a tagger.

The three metrics do not rank the rungs the same way, so this is a Pareto trade
and not a single winner:

| ranking (best first) | order |
|---|---|
| offline per-end miss rate | p90+5, p90+3, flat ~ p80+5, p80+3 |
| long-track TGM | p90+5, p90+3, p80+5, p80+3, flat |
| sub-10 cm over-tags | p80+3, p80+5, flat, p90+3, p90+5 |

### 9.6 Operating point — the recommendation, and its condition

The two PHYSICS metrics (miss rate, long-track TGM) both rank p90 first, and they
are independent of one another.  The third column is not a property of the
fiducial at all: it is sec 9.3's `:1066` defect, which tags any two-group cluster
whose ends fall outside, and a tighter volume simply feeds it more candidates.

So the recommendation is **p90**, with the cushion the owner's risk appetite
(3 keeps the over-tag growth to +91; 5 buys 5 more long tracks for +64 more),
**conditional on fixing sec 9.3 first**.  Flipping p90 while `:1066` stands would
raise sub-10 cm TGM tags by 12-21 %, and those tags remove real charge from the
cosmic-rejected sample.

Choosing p80 instead in order to hold the over-tag count down would be treating
the symptom with the wrong instrument: p80 + 3 does reduce sub-10 cm tags by 107,
but it does so by LOOSENING the anode half, where its offline miss rate is 14.0 %
against the flat shell's 7.4 % — i.e. it pays for tag purity with exit-end
sensitivity, which is the quantity the fiducial exists to get right.

**Owner decision 2026-09-07: p90 + 3 is PDHD production** (sec 12).

## 10. Gates

Record: `pdhd/stm/gates/d09_curved_fv_gate.txt`.

| arm | extra TLAs | bytes | vs pre-doc-09 |
|---|---|---|---|
| knob absent (default OFF) | -- | 254398 | **IDENTICAL** |
| explicit OFF | `-S curved_fv=false` | 254398 | **IDENTICAL** |
| ON p90 + 5 | `-S curved_fv=true -A curved_fv_profile=p90 -S curved_fv_margin_y=5 -S curved_fv_margin_z=5` | 257804 | differs |
| ON p80 + 3 | `-S curved_fv=true -A curved_fv_profile=p80` | 257711 | differs |

Compiled-config proof, from `TaggerCheckTGM`'s own data block:

* OFF: `fiducial = BoxFiducial:pdhd_pr_fv`, `fv_tolerance = [-20,-20,-175,-175,-180,-180]`
  (x 2 / y 17.5 / z 18 cm)
* ON: `fiducial = CompositeFiducial:pdhdcurved-fv` plus `PolyFiducial:pdhdcurved-xy`
  and `-xz`, `fv_tolerance = [-20,-20,-50,-50,-50,-50]` (x 2 / y 5 / z 5 cm)

One knob moves both halves, because they must move together: the 17.5/18 those
margins carry IS the flat allowance the surface replaces, and carrying both would
count it twice.  x is untouched -- no drift-direction surface was measured.

Binary pin `/home/xqian/tmp/d09_libpin/pin`; every arm's fingerprint was recorded
before and after and never changed.

## 11. Open items

1. **`TaggerCheckTGM.cxx:1066`** (sec 9.3): tag without interior support or a
   length requirement.  49 % of PDHD production TGM tags are already under 10 cm.
   Shared code -- PDVD and SBND bind the same tagger.  Needs its own default-OFF
   knob and A/B; **fix this before flipping any surface.**
2. **TGM and FC have no readout-edge guard.**  `stm_readout_edge_guard` exists
   only in `TaggerCheckSTM.cxx:2268` and is default OFF on PDHD (`pr.jsonnet:91`).
   Readout-edge ends are 12.4 % of side-wall ends and 90.2 % of them stop > 8 cm
   short, against 47.0 % away from an edge.  Doc pdvd/41 R4 named this and doc
   pdvd/43 sec 7 asked for it first; it is still open on both detectors.
3. **8 of 32 bins are statistics-starved**, all on z (sec 6).  They are named in
   the profile header.  ~60 more Q/L-matched events would clear them; run 27980
   is the obvious candidate (7.8 mV/fC, light already validated).
4. **No measurable x offset between the runs** (sec 4.4): +0.02 +- 0.05 cm on the
   conditioned anode control.  An earlier unconditioned median suggested ~3 cm;
   that estimator is dominated by non-exits and carries a +-6 cm error.  Any
   future drift-direction measurement should use the conditioned form.
5. The surface is built and graded on the same 61 events.  The run-split
   cross-validation holds (sec 7), but the arm counts are in-sample.

## 12. Owner decision: p90 + 3 is PDHD production (2026-09-07)

Set in the driver, `pdhd/wct-pr-perevt.jsonnet`, which is the only production
caller of `pdhd/pr.jsonnet` — the doc pdvd/43 sec 8 precedent:

```jsonnet
curved_fv = true,
curved_fv_margin_y = 3,
curved_fv_margin_z = 3,
curved_fv_profile = 'p90',
```

`pr.jsonnet`'s function defaults are unchanged (`false` / `'flat'` / 3), so any
other caller keeps the byte-identical legacy box; the change there is
comments-only, naming where production lives.

**Why p90.**  The two physics metrics rank it first and they are independent of
one another: the offline per-exit-end miss rate, which never sees a tagger
(11.0 % flat -> 7.2 %, cross-validated 10.8-11.3 -> 8.9-10.1 by holding out
either run), and long-track TGM (430 -> 464).

**Why cushion 3 and not PDVD's 5.**  Going 3 -> 5 buys 5 more long tracks for 64
more sub-10 cm tags.  Those tags are sec 9.3's `TaggerCheckTGM.cxx:1066` — a
two-extreme-group cluster tagged with no interior support and no length test —
not a property of the surface.  **Revisit the cushion once that is fixed**: p90+5
has the better miss rate (6.0 %) and its only cost is the over-tagging 1066
causes.

**Why not p80**, which would have held the over-tag count down: p80 + 3 reduces
sub-10 cm tags by 107, but it gets there by loosening the anode half, where its
miss rate is 14.0 % against the flat shell's 7.4 %.  That pays for tag purity
with exit-end sensitivity, which is the quantity the fiducial exists to provide.

### 12.1 Gates

| check | result |
|---|---|
| production (no TLA) == the graded `d09p90c3` arm's compile | **IDENTICAL**, 257804 B |
| `-S curved_fv=false` == the pre-doc-09 flat compile | **IDENTICAL**, 254398 B |
| `pr.jsonnet` comment addition changes no compiled config | production and flat both unchanged |
| p90+5 and p80+3 arms still reachable and distinct | yes |

Compiled-config proof, `TaggerCheckTGM`'s own data block:

| compile | fiducial | fv_tolerance (cm) |
|---|---|---|
| production | `CompositeFiducial:pdhdcurved-fv` (+ 2 PolyFiducial, 24 corners/plane) | x 2 / y 3 / z 3 |
| `curved_fv=false` | `BoxFiducial:pdhd_pr_fv` | x 2 / y 17.5 / z 18 |
| `curved_fv_margin_y/z=5` | same polygon | x 2 / y 5 / z 5 |
| `curved_fv_profile=p80` | different polygon | x 2 / y 3 / z 3 |

Equivalence run `d09prod`: the 61 events re-run with NO TLA under the new
defaults, verdicts compared per (event, cluster) against the graded `d09p90c3`
arm — **0 flips of 5879 clusters** on TGM, STM and FC alike (1755 / 320 / 2058
unchanged), pin fingerprint identical before and after.  The compiled configs
were already cmp-identical; this run proves the identity holds through the
binary, which a config-level cmp cannot show.

### 12.2 What production changes, against the flat shell it replaces

| | flat (was) | p90 + 3 (now) |
|---|---|---|
| TGM, all | 1561 | 1755 |
| **TGM, tracks > 2 m** | **430** | **464** |
| TGM, < 10 cm (see sec 9.3) | 724 | 815 |
| STM | 318 | 320 |
| STM, tracks > 2 m | 86 | 85 |
| fully contained | 2180 | 2058 |
| offline per-exit-end miss | 11.0 % | 7.2 % |

### 12.3 Arm switches

| want | `PDHD_PR_TLA` |
|---|---|
| production (p90 + 3) | *(none)* |
| the doc-35-style flat shell | `-S curved_fv=false` |
| p90 + 5 | `-S curved_fv_margin_y=5 -S curved_fv_margin_z=5` |
| p80 + 3 | `-A curved_fv_profile=p80` |
| p80 + 5 | `-A curved_fv_profile=p80 -S curved_fv_margin_y=5 -S curved_fv_margin_z=5` |

### 12.4 Sentinels to re-run before trusting production

1. The doc pdvd/25 stopping-muon census (sec 9.4b shows STM is undisturbed, but
   that is the tagger count, not the census).
2. Sec 11 item 1 (`:1066`) remains the first thing to fix; it is what makes the
   cushion choice a trade at all.
