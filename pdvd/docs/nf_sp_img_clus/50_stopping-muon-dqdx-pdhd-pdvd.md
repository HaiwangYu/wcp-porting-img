# doc pdvd/50 — dQ/dx vs residual range for stopping muons: PDHD next to PDVD

**Scope.** No code is changed. This is an analysis of reconstruction products
already on disk, against the Modified-Box expectation tables the production
taggers already carry. Owner question (2026-09-07): *"For PDHD, I forgot if we
have got the dQ/dx vs. residual range for stopping muon and compared them with
expectation. Can we summarize this for PDHD and PDVD and compare them… overlay
with the expected dQ/dx for two cases… if you can find some proton candidates
that would be good to add as well."*

**The short answer.**

1. PDVD was measured and published (doc 42 §4). **PDHD had not been** — doc
   `pdhd/docs/stm-tagger-chain.md` §6 said so itself ("derived and consistent,
   NOT confirmed", n = 1 track). It is measured here.
2. **The PDHD tagger is not the problem** — it tags 5.25 STM per event against
   PDVD's 4.88, i.e. slightly *more*. What is 11× worse is the *analysis*
   selection applied afterwards, and **it is not a charge or calibration
   difference either.** Both detectors put the *same* scale on
   charge-complete tracks (k = 0.89 vs 0.94) and follow the *same* k-vs-
   completeness curve. They differ only in how many fitted points carry full
   charge: median f_low **0.262 on PDHD vs 0.042 on PDVD**.
3. **PDHD's two drift volumes disagree by a factor 1.63.** APA0+APA2 (x<0,
   face 0) read **0.573** of the muon table on the plateau; APA1+APA3 (x>0,
   face 1) read 0.935-0.941 — with no free scale, on 21 of 26 events. It is
   **not a gain shift**: the surviving points agree to 5 % in all four APAs,
   and what differs is the share of points killed (43-47 % vs 29 %). PDVD's
   control asymmetry is 1.18 with 4-19 % killed. §4.2-§4.4.
4. The cut that destroys the PDHD sample is doc-55's **muon shape rms ≤ 0.10**
   (33 → 1 tracks). It is not a stopping-muon selector; it is a charge-
   completeness selector in disguise. Replacing it with an explicit
   completeness cut gives **6 PDHD / 67 PDVD** clean stopping muons and both
   detectors then agree with their own expectation.
5. **No usable stopping-proton population exists in either sample**, and the
   dQ/dx-vs-rr shape cannot supply one: the proton and muon tables differ by a
   ×1.6 *normalisation* but only 0.06 in *shape*. Section 7 gives the four
   independent searches and what each returned.

---

## Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
S=<scratch>            # ANA=$S/ana ; all TSVs below land there

# 1. the tier ladder, doc 42's engine unchanged (sanity anchor + arm stability)
( cd pdhd && python3 docs/scripts/d42_dqdx_rr.py --det pdhd \
      --ref stm/pdhd_ref_dqdx.json --ref-key MuonDeDx --max-abs-x 1e9 \
      --out $S/ana/pdhd_d30hpost_nox work/*_d30hpost/tracking-stm.root )
( cd pdvd && python3 docs/nf_sp_img_clus/scripts/d42_dqdx_rr.py --det pdvd \
      --ref stm/pdvd_ref_dqdx_045.json --ref-key MuonDeDx \
      --out $S/ana/pdvd_d42fit work/*_d42fit/tracking-stm.root )

# 2. this round's engine: adds f_low, the completeness tier, both hypotheses
D=$PWD/pdvd/docs/nf_sp_img_clus/scripts/d50_dqdx_rr_cross.py
( cd pdhd && python3 $D --det pdhd --ref stm/pdhd_ref_dqdx.json --max-abs-x 1e9 \
      --status 0 --out $S/ana/d50_pdhd_s0 work/*_d30hpost/tracking-stm.root )
( cd pdvd && python3 $D --det pdvd --ref stm/pdvd_ref_dqdx_045.json --max-abs-x 305 \
      --status 0 --out $S/ana/d50_pdvd_s0 work/*_d42fit/tracking-stm.root )
#   ... and again with --status 5 (the tagger's "proton endpoint" rejects) -> _s5

# 3. the PR chain's own proton-tagged segments
P=$PWD/pdvd/docs/nf_sp_img_clus/scripts/d50_pr_proton_segments.py
python3 $P --det pdhd --out $S/ana/d50_pdhd_prp pdhd/work/*_d30hnupost/tracking-pr.root
python3 $P --det pdvd --out $S/ana/d50_pdvd_prp pdvd/work/*_d30vnupost/tracking-pr.root

# 4. figures
python3 pdvd/docs/nf_sp_img_clus/scripts/d50_dqdx_rr_plots.py \
      --ana $S/ana --figs pdvd/docs/nf_sp_img_clus/figs
for D in pdhd pdvd; do
  python3 pdvd/docs/nf_sp_img_clus/scripts/d50_deficit_plots.py \
      --det $D --ana $S/ana --figs pdvd/docs/nf_sp_img_clus/figs
done
```

Readout-unit assignment in `d50_deficit_plots.py` is geometric, read from the
production wire files: `protodunehd-wires-larsoft-v1.json.bz2` (PDHD, 4 APAs)
and `protodunevd-wires-larsoft-v7-uvwfit.json.bz2` (PDVD, 8 anodes x 2 faces).

**Arms and epoch.**

| detector | arm | events | runs | written |
|---|---|---|---|---|
| PDHD | `work/*_d30hpost` | 61 | 028084 ×31, 029107 ×30 | 2026-09-07 06:47 |
| PDVD | `work/*_d42fit` | 120 | 039252 ×18, 039253 ×18, 039349 ×84 | 2026-09-05 07:42 |
| PDHD protons | `work/*_d30hnupost` | 61 | — | 2026-09-07 07:09 |
| PDVD protons | `work/*_d30vnupost` | 120 | — | 2026-09-07 07:14 |

`local/lib/libWireCellClus.so` 2026-09-07 06:35; toolkit HEAD `c61de88a`.

**Why `d30hpost` is the PDHD production arm.** It is the doc-30 post-fix arm and
carries `tracking-stm.root`, which the production PR arm `d09prod` does not
(`d09_run_pr_arm.sh` runs without `-stm-fit`). Its output is *content-identical*
to production — `abtest/hash_archive.py` on `028084_0`:

```
4c5a4ba68dcddd8a4ef90901bd0c6e4a5d29f4cfcfa71c32162e024ee76c4916  9  .../028084_0_d09prod/mabc-pr.zip
4c5a4ba68dcddd8a4ef90901bd0c6e4a5d29f4cfcfa71c32162e024ee76c4916  9  .../028084_0_d30hpost/mabc-pr.zip
```

so the STM fits analysed here are production's, with the dump added. **PASS.**

---

## 1. Gate: the expectation curves are the ones production uses

The two overlaid curves are not re-derived here. They are
`pdhd/stm/pdhd_ref_dqdx.json` (E = 0.4959 kV/cm) and
`pdvd/stm/pdvd_ref_dqdx_045.json` (E = 0.45 kV/cm), re-gated against the
**compiled** `cfg/pgrapher/experiment/{pdhd,protodunevd}/particle_dataset.jsonnet`
that `TaggerCheckSTM` is actually handed:

| detector | tables | worst relative difference | tolerance | verdict |
|---|---|---|---|---|
| PDHD | 5 (Muon/Proton/Pion/Kaon/Electron DeDx) | 4.89 × 10⁻⁶ | 1 × 10⁻⁵ | **PASS** |
| PDVD | 5 | 4.67 × 10⁻⁶ | 1 × 10⁻⁵ | **PASS** |

Both are Modified Box with α = 0.93, β = 0.212, ρ = 1.38 g/cm³, W_ion = 23.6 eV
and the retained undocumented `× 0.85` fudge. Muon plateau (rr = 59.5 cm):
PDHD 54 609.2 e/cm, PDVD 53 965.5 e/cm.

## 2. Sanity anchor: doc 42 reproduces exactly

Doc 42 §4.1 on the same `d42fit` arm, recomputed today:

| tier | doc 42 published | this round |
|---|---|---|
| all status 0 | 582 trk, 143 379 pts, k 0.922, χ² 2343 | 582, 143 379, 0.9217, 2343.44 |
| contrast ≥ 2 | 102, 25 314, 0.916, 47.2 | 102, 25 314, 0.9159, 47.23 |
| doc-55 five cuts | 47, 13 039, 0.926, 67.8 | 47, 13 039, 0.9261, 67.75 |
| doc-55 + muon k | 45, 12 544, 0.931, 69.5 | 45, 12 544, 0.9305, 69.55 |

Bit-for-bit on every published figure. The pipeline has not moved under doc 42.
Across three PDVD arms the doc-55+muon-k tier is stable: `d42fit` 45 tracks
k 0.9305, `d30vpost` 40 / 0.9315, `d45prod` 41 / 0.9335.

## 3. The tier ladder, both detectors

Accepted STM passes (`T_stm_pass.status == 0`), kink-anchored, live points only.
k_pop = exp(median log(dQ/dx / muon table)); χ² over 11 rr bins with a 3 %
systematic floor.

| det | tier | tracks | points | k_pop | χ²/11 | per-track k | contrast med | f_low med |
|---|---|---|---|---|---|---|---|---|
| PDHD | all status 0 | 303 | 77 801 | 0.886 | 12 478 | 0.50 ± 0.32 | 0.90 | 0.262 |
| PDHD | contrast ≥ 2 | 57 | 16 599 | 0.784 | 2 408 | 0.24 ± 0.37 | 3.11 | 0.435 |
| PDHD | doc-55 five cuts | **1** | 365 | 1.133 | 9.6 | 1.16 | 2.42 | 0.008 |
| PDHD | **charge-complete** | 49 | 21 491 | 1.029 | 914 | 0.89 ± 0.21 | 0.93 | 0.023 |
| PDHD | **complete + Bragg ≥ 2** | **6** | 2 606 | **1.049** | **14.4** | 1.00 ± 0.14 | 2.24 | 0.016 |
| PDVD | all status 0 | 582 | 143 379 | 0.922 | 2 343 | 0.86 ± 0.25 | 1.07 | 0.043 |
| PDVD | contrast ≥ 2 | 102 | 25 314 | 0.916 | 47.2 | 0.97 ± 0.25 | 2.43 | 0.034 |
| PDVD | doc-55 + muon k | 45 | 12 544 | 0.931 | 69.6 | 1.01 ± 0.08 | 2.29 | 0.015 |
| PDVD | **charge-complete** | 284 | 80 655 | 0.964 | 911 | 0.94 ± 0.16 | 1.19 | 0.018 |
| PDVD | **complete + Bragg ≥ 2** | **67** | 17 973 | **0.952** | **40.0** | 1.00 ± 0.10 | 2.28 | 0.012 |

`complete + Bragg` is the like-for-like cross-detector stopping-muon sample and
is what every number below uses.

**k is not a charge scale.** No electron-lifetime correction is wired up on
either detector, and the tables carry the uncalibrated `× 0.85` fudge, so k
absorbs gain × lifetime × fudge. Only the *shape* is interpretable.

## 4. Why PDHD's sample looked 11× worse — the per-cut attrition

### 4.0 First: the PDHD tagger is not the problem

This section is about the *analysis* selection, not about the tagger. Stated
plainly, because "PDHD has trouble finding stopping muons" is the wrong reading:

| | PDHD (61 evt) | PDVD (120 evt) |
|---|---|---|
| clusters tagged `STM=1` | 320 — **5.25 / event** | 586 — **4.88 / event** |
| STM passes fitted | 23.2 / event | 15.1 / event |
| accepted passes (status 0) | 5.25 / event | 4.88 / event |

**PDHD tags slightly *more* stopping muons per event than PDVD.** The tagger
finds them; what collapses is the quality selection applied afterwards, and
§4.1 below shows it collapses on one cut.

Two independent things are easy to conflate here, so they are kept apart:

- **Purity** — the tagger's accepted population is not a Bragg-bearing sample on
  *either* detector (median Bragg contrast 0.90 PDHD, 1.07 PDVD; only ~20 % of
  accepted passes on either detector reach contrast ≥ 2). That is doc 42 §4.2's
  finding, it is not PDHD-specific, and a contrast cut is the fix.
- **Charge completeness** — PDHD's fitted points carry deficient charge 3× as
  often as PDVD's. That *is* PDHD-specific and is what §4.2 characterises.

The doc-55 five cuts fail PDHD tracks for the second while appearing to select
for the first.

### 4.1 The attrition

Cuts applied cumulatively in doc-55 order:

| cut applied cumulatively | PDHD | PDVD |
|---|---|---|
| accepted STM passes (status 0) | 303 | 582 |
| + npts ≥ 40 | 302 | 563 |
| + ≥ 6 populated rr bins | 219 | 474 |
| + reaches rr < 2 and rr ≥ 22 cm | 219 | 471 |
| + Bragg contrast ≥ 2 | 46 | 98 |
| + median reduced χ² ≤ 2.5 | 33 | 81 |
| **+ muon shape rms ≤ 0.10** | **1** | **47** |
| *(instead)* npts ≥ 40 and f_low < 0.05 | 49 | 284 |
| *(instead)* … and Bragg contrast ≥ 2 | **6** | **67** |

The stopping-muon cuts proper (contrast, χ², reach) cost PDHD no more than PDVD
in proportion: 303 → 33 vs 582 → 81. **The whole 11× is the last line.** The
shape rms is computed on per-bin medians, and a track with a quarter of its fit
points carrying partial charge has scattered medians whatever particle it is.

![](figs/50_dqdx_rr_diagnosis.png)

*(a)* f_low, the fraction of live fit points below 0.4 × plateau: PDHD median
0.262, PDVD 0.042 — a 6× difference in charge completeness, the single largest
PDHD/PDVD difference in this analysis. *(b)* **the same relation on both
detectors.** Per-track k against f_low:

| f_low | PDHD k (n) | PDVD k (n) |
|---|---|---|
| 0.00–0.05 | 0.893 (49) | 0.940 (276) |
| 0.05–0.10 | 0.740 (27) | 0.821 (108) |
| 0.10–0.15 | 0.663 (22) | 0.710 (37) |
| 0.15–0.25 | 0.537 (44) | 0.641 (31) |
| 0.25–0.40 | 0.497 (57) | 0.443 (21) |
| 0.40–1.00 | 0.187 (89) | 0.234 (24) |

Two detectors, one curve. PDHD's apparent 4× charge deficit was a population
effect, not a detector property. The mechanism on the PDHD side is already
documented — the wrapped-plane charge attribution of `pdhd/docs/04` §8 and the
retiler ghosts of `pdhd/docs/07`; this round measures its cost to calorimetry
for the first time. It is also exactly the failure mode of
`feedback_zero_charge_points_corrupt_medians`: at the contrast ≥ 2 tier PDHD's
median Bragg contrast is 3.11 with k = 0.24, i.e. *fake* Bragg peaks made by
depressed plateaus, not real ones.

**On selecting with f_low.** The cut is on completeness, not on charge scale,
but it is not free of bias: PDVD moves from k 0.86 (all) to 0.94 (complete).
The check that it lands on the right population is that on PDVD it reproduces
the established doc-55 tier's scale — 0.952 (67 tracks) vs 0.931 (45 tracks) —
with 50 % more tracks and a *better* χ² (40.0 vs 69.6).

### 4.2 What the PDHD deficit actually is: a drift-volume effect

![](figs/50_pdhd_deficit_anatomy.png)

*PDHD. (a) plateau charge split by drift volume; (b) per APA, all plateau points
(solid) against only the points above 0.5 x plateau (hatched), with the share
killed printed below; (c,d) the deficient fraction mapped in (y, z), one panel
per drift volume, APA boundary drawn; (e) one typical track from each volume;
(f) the per-event ratio between the volumes.*

**The deficit tracks the drift volume, not a region.** Assigning every fit point
to its APA geometrically from `protodunehd-wires-larsoft-v1.json.bz2`
(APA0: x<0 z<231; APA1: x>0 z<231; APA2: x<0 z>=231; APA3: x>0 z>=231), the
plateau (rr 40-60 cm) charge against the table, **with no free scale**:

| APA | drift volume | plateau dQ/dx / table | points |
|---|---|---|---|
| APA0 | x < 0 (face 0) | **0.573** | 2 128 |
| APA1 | x > 0 (face 1) | **0.941** | 1 378 |
| APA2 | x < 0 (face 0) | **0.573** | 1 774 |
| APA3 | x > 0 (face 1) | **0.935** | 1 643 |

APA0 and APA2 agree with each other to three decimal places, as do APA1 and
APA3, and `cfg/pgrapher/experiment/pdhd/clus.jsonnet` groups them exactly that
way: **APA0+APA2 = face 0 (drift -x), APA1+APA3 = face 1 (drift +x)**. On PDHD
the sign of x *is* the drift volume, so this is a **factor 1.63 between the two
halves of the detector**, not an APA0 problem and not the corner effect an
earlier version of this section reported (that reading was an artifact of
pooling the two volumes: panel (c) shows the x<0 deficit is detector-wide).

It is on **every event**, not a few: over the 26 events with >=40 plateau points
in both volumes, median(x<0)/median(x>0) has median **0.56**, and **21 of 26**
events fall below 0.8 (panel f).

**It is not a gain shift.** If one volume were simply mis-calibrated, its whole
charge distribution would slide. It does not — the distribution is **bimodal**
(panel a), and the points that survive land in the same place everywhere:

| APA | all plateau points | only points > 0.5 x plateau | share killed |
|---|---|---|---|
| APA0 | 0.573 | **0.952** | 43 % |
| APA1 | 0.941 | **1.045** | 29 % |
| APA2 | 0.573 | **1.032** | 47 % |
| APA3 | 0.935 | **1.043** | 29 % |

So the surviving charge is right to within 5 % in all four APAs. What differs is
**how many points get killed**. That is a charge-attribution failure, not a
calorimetry constant, and it is why a *scale* correction cannot repair it.

**The two bad APAs fail differently**, which matters for where to look. Binning
the plateau points by fraction of the expectation:

| APA | < 0.2 (dead) | 0.2-0.5 (partial) | 0.5-0.8 | 0.8-1.2 | > 1.2 |
|---|---|---|---|---|---|
| APA0 | 0.13 | **0.29** | 0.21 | 0.21 | 0.16 |
| APA1 | 0.16 | 0.12 | 0.09 | 0.42 | 0.21 |
| APA2 | **0.31** | 0.16 | 0.13 | 0.27 | 0.13 |
| APA3 | 0.14 | 0.15 | 0.11 | 0.40 | 0.20 |

APA0's excess sits in the **partial** band — points that keep some charge but
not enough. That is the signature of a *weakened* plane, and PDHD has a
documented one: `pdhd/docs/sp-apa0-plane2.md` records that **APA0's collection
plane behaves like an induction plane with much weaker signals because of a
hardware fault**. APA2's excess sits in the **dead** band instead, so whatever
APA2 suffers from is not the APA0 fault. The face-0 grouping is common to both.

### 4.2b The APA label does not depend on x or on t0 (owner check, 2026-09-07)

The assignment above used `sign(x)` and `z`, and the owner rightly asked whether
that is legitimate: **before Q/L matching or a t0 correction, x is a drift-time
proxy, not a position, so it cannot by itself say which APA read the charge.**

It does not have to. The dump carries a wire-based label. `pu/pv/pw` in
`T_rec_charge` are not per-face wire numbers — `PdvdMagnifyTrackingVisitor.cxx:599-601`
writes them through `ChanScheme::globalf`, i.e. `base[plane] +` the rank of the
channel in the ascending list of that plane's channels over **all** anodes. From
the production wire file the blocks are exact:

| plane | base | block size | APA from the stored value |
|---|---|---|---|
| U | 0 | 800 / APA | `pu // 800` |
| V | 3200 | 800 / APA | `(pv - 3200) // 800` |
| W | 6400 | 960 / APA (480 per face) | `(pw - 6400) // 960` |

Labelling every accepted-pass fit point by `(pw - 6400) // 960` and comparing
with the `sign(x) + z` guess, over all 61 events:

```
CONFUSION   rows = APA from pw (wire index)   cols = APA guessed from sign(x), z
   true APA0     20747       0       0       0
   true APA1         0   14764       0       0
   true APA2         0       0   22684       0
   true APA3         0       0       0   20672
                                     agreement 78867/78867 = 100.0 %
```

The two agree on **every point**. The reason is that imaging runs per APA, so a
point's x is built from the drift time relative to *that* APA's own anode and
stays inside that APA's drift volume whatever the t0 error is — a wrong t0 slides
x within the volume, it does not move it across the cathode. The W-rank blocks
also confirm which face is live: the APA0-face1, APA1-face0, APA2-face1 and
APA3-face0 blocks are **empty**, exactly matching `clus.jsonnet`'s statement that
APA0+APA2 run on face 0 and APA1+APA3 on face 1.

So the per-APA numbers stand, and **APA2 really is APA2**. (An earlier attempt to
check this through `T_proj_data.channel` gave 28 % agreement; that was an error on
my side — that branch is `cs.global(...) = base[plane] + rank`, not a raw LArSoft
channel, and decoding it as `channel // 2560` scrambles the APAs.)

### 4.2c The charge is already missing before the fit runs

This is §9's first test, answered here rather than deferred. `T_proj_data` holds
the 2-D pixels the fit was actually handed. Per accepted pass, normalised by the
**true 3-D path length** (not `sum(nq)` — the fitter's `dx` is
`|p-prev| + |p-next|`, about twice the step):

| APA | measured W charge per cm | W pixels per cm | charge per pixel | slices per channel |
|---|---|---|---|---|
| APA0 | 369 954 | 34.8 | 6 776 | 18.4 |
| APA1 | 785 593 | 90.9 | 5 620 | 18.7 |
| APA2 | 429 756 | 46.8 | 5 937 | 16.9 |
| APA3 | 1 053 035 | 114.9 | 5 517 | 17.2 |

Relative to the APA1/APA3 mean the measured collection charge per cm is **APA0
0.40, APA1 0.85, APA2 0.47, APA3 1.15** — the same ordering, and roughly the same
factor, as the fit's own dQ/dx (0.59 / 0.95 / 0.53 / 0.92). Two further points:
the **charge per pixel is the same in all four APAs** (5.5-6.8 k), and the **ROI
time extent per channel is the same** (17-19 slices) and essentially no pixel
carries zero charge. So APA0 and APA2 are not being read at a lower gain and
their ROIs are not being truncated in time — the fit is simply handed about half
as much collection-plane charge per unit track.

**`TrackFitting` is therefore not the culprit; the deficit arrives with the
input.** That moves the investigation upstream into SP/imaging.

*Caveat, stated rather than solved:* `T_proj_data` is a region around the
trajectory, not only the wires the track crosses, so "pixels per cm" is not a
pure geometric rate and can carry a track-angle dependence; APA1 and APA3
themselves differ by 35 %. The robust part of this table is the ordering and the
fact that charge-per-pixel and slices-per-channel are flat while the total is
not.

### 4.2d The long swings are the deficit, not a second effect (owner check)

PDHD profiles show large slow swings along the track — the charge falls away and
comes back over tens of centimetres — and the question is whether that is a
separate artifact or the same thing as §4.2. Quantifying it per track: normalise
dQ/dx by the track median, smooth with a 15-point boxcar, and take
**swing** = p90 − p10 of the smoothed profile, with **hf** = the residual
point-to-point scatter.

| sample | n | swing | hf | swing/hf |
|---|---|---|---|---|
| PDHD APA0 | 57 | 1.07 | 0.36 | 2.78 |
| PDHD APA1 | 36 | 0.66 | 0.21 | 3.34 |
| PDHD APA2 | 61 | **1.39** | 0.22 | **5.74** |
| PDHD APA3 | 51 | 0.53 | 0.19 | 2.58 |
| PDHD x<0 (APA0+APA2) | 118 | **1.19** | — | — |
| PDHD x>0 (APA1+APA3) | 87 | 0.60 | — | — |
| PDVD x<0 | 150 | 0.45 | 0.29 | 1.52 |
| PDVD x>0 | 274 | 0.46 | 0.29 | 1.60 |

**Yes, the swings track the bad volume**: 1.19 in x<0 against 0.60 in x>0, a
factor 2, while PDVD is flat at 0.45/0.46 across both of its volumes — and
PDHD's *good* volume (0.53-0.66) is already close to PDVD.

**But it is not an independent phenomenon.** Restricted to charge-complete
tracks (f_low < 0.05) the swing collapses to **0.35** on PDHD with the volume
difference gone (x<0 0.39 on 8 tracks, x>0 0.34 on 36), against PDVD's 0.37.
Removing the killed points removes the swings. They *are* §4.2's extended
deficient stretches seen in profile, not a separate oscillation riding on top.

**And there is no characteristic period.** The dominant wavelength of the
smoothed profile scales with the track: λ/span = 1.00, 0.50, 0.50, 0.33, 0.25
across length bins from <60 cm to >250 cm, correlation(length, λ) = 0.57. The
FFT is picking the longest mode the track can hold. An earlier reading of these
profiles as a "~40 cm periodic oscillation" was an artifact of finite track
length and should not be carried forward — nothing here supports a periodic
mechanism such as a wire-pattern beat.

### 4.3 PDVD as the control: this is PDHD-specific

![](figs/50_pdvd_deficit_anatomy.png)

*The identical analysis on PDVD, whose 16 CRP quadrants (2 drift volumes x 4 y
bands x 2 z bands) come from `protodunevd-wires-larsoft-v7-uvwfit.json.bz2`.*

PDVD does have a drift-volume asymmetry, and that is the useful part of the
control — it is **mild, uniform, and the opposite sign**:

| | PDHD | PDVD |
|---|---|---|
| plateau ratio, x<0 volume | **0.573** | 1.00 - 1.07 |
| plateau ratio, x>0 volume | 0.935 - 0.941 | 0.86 - 0.92 |
| volume asymmetry | **0.61** | 1.18 |
| share of points killed | **29 % (good volume) - 47 %** | **4 - 19 %** |
| spread across readout units *within* a volume | 0.000 (2 APAs) | <= 0.08 (8 CRPs) |
| per-event ratio | median 0.56, **21/26 events below 0.8** | median 1.20, **0/44 below 0.8** |

Three things follow. **First**, a modest uniform volume asymmetry is normal in
this chain — PDVD's 18 % is there and nobody has chased it — so PDHD's factor
1.63 is the anomaly, not the existence of an asymmetry. **Second**, PDVD's 16
quadrants are homogeneous *within* each volume (1.00-1.07 and 0.86-0.92), so the
effect is per-volume on both detectors, not per-readout-unit. **Third, even
PDHD's good volume is worse than PDVD's bad one** — 29 % of points killed
against 9-19 % — so PDHD carries a baseline attribution problem on top of the
volume split. Panel (e) makes the difference visible directly: PDVD's tracks
scatter around the expectation, PDHD's x<0 track spends most of its length
below the deficient threshold.

### 4.4 What this does and does not invalidate

**Does not**: the doc-50 clean tier survives. Its 6 PDHD tracks have median
dQ/dx 53 500 - 62 900 e/cm, i.e. all normal, and they split 3 purely x>0, 2
purely x<0, 1 mixed. The completeness cut removes the killed points *before* the
scale is measured, which is why §5's k_pop = 1.049 stands and why restricting to
either volume moves it only to 1.076 (x>0) or 1.014 (x<0). The cut is doing
exactly what §4.1 says it does.

**Does**: any PDHD quantity built on *pooled, unselected* per-point dQ/dx. That
includes the raw plateau of §5's decode cross-check when read as a calorimetry
statement, and — more importantly — anything inside the reconstruction that
consumes dQ/dx without a completeness cut. `TaggerCheckSTM`'s own Bragg and KS
tests are in that category: they run on the same points, they are normalised to
a single `mip_dqdx = 56000 e/cm` for the whole detector, and in the x<0 volume
the median plateau point is at 32 000. That is a plausible mechanism for the
purity finding of §4.0 (median accepted Bragg contrast 0.90 on PDHD against 1.07
on PDVD) but it is **not tested here** and should not be quoted as established.

## 5. The comparison the owner asked for

![](figs/50_dqdx_rr_overlay.png)

*Left: measured per-bin medians for both detectors with **both detectors' own**
Modified-Box muon curves (solid) and proton curves (dashed) at each detector's
own field, each scaled by that detector's single free k. Right: each detector
against its own table with one free scale removed.*

Per-bin median of dQ/dx / (k_pop × own muon table), complete + Bragg tier:

| det | k_pop | χ²/11 | 0–1 | 1–2 | 2–3 | 3–5 | 5–7 | 7–10 | 10–15 | 15–20 | 20–30 | 30–40 | 40–60 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PDHD | 1.049 | 14.4 | 0.943 | 0.988 | 1.056 | 0.930 | 0.985 | 1.032 | 1.084 | 1.034 | 0.955 | 1.083 | 0.983 |
| PDVD | 0.952 | 40.0 | 1.003 | 1.057 | 1.075 | 1.084 | 1.075 | 1.078 | 1.096 | 1.091 | 1.045 | 1.031 | 1.027 |

Points per bin — PDHD 12, 7, 11, 18, 20, 26, 49, 44, 95, 93, 187; PDVD 137, 100,
110, 206, 208, 308, 534, 515, 1024, 996, 1895. **PDHD's three lowest bins hold
7–12 points between them: the PDHD Bragg peak is not measured in this sample.**

**The absolute scale, with no free parameter.** Before any k is removed, the
raw plateau median (rr 40–60 cm, complete + Bragg tier) against the table
evaluated on the same points:

| det | measured | table | ratio | points |
|---|---|---|---|---|
| PDHD | 57 318 e/cm | 55 627 e/cm | **1.030** | 187 |
| PDVD | 53 628 e/cm | 54 948 e/cm | **0.976** | 1 895 |

Both within 3 %, in opposite directions, with the `× 0.85` fudge left in. This
is a decode cross-check first — it confirms `(q − offset)/scale/nq` and the rr
convention — but it also says the uncalibrated absolute charge scale of both
chains is already right to a few percent, which is more than k alone shows.

Reading it:

- **Both detectors follow their own muon expectation over 0.5–60 cm**, at
  k = 1.05 (PDHD) and 0.95 (PDVD) — both inside the few-percent uncalibrated
  gain / lifetime / fudge freedom. This is the first confirmation of the PDHD
  0.4959 kV/cm tables against PDHD data.
- **The two samples carry different geometric cuts** — PDHD none, PDVD
  |x| < 305 cm — because §6 derives them separately. This does not manufacture
  the difference below: PDVD's excess is measured *after* its near-CRP points
  are already excluded, so the near-CRP rise cannot be its cause; and applying
  the same 305 cut to the PDHD clean tier drops 17 % of its points and moves
  k_pop by **+0.7 %** (1.0495 → 1.0573), leaving every conclusion below intact.
  The asymmetry is a per-detector geometry choice, not a lever on the result.
- **PDVD's +10 % hump at 3–20 cm reproduces** (1.075–1.096 across 2–20 cm,
  1.03–1.05 at the plateau, same sign in every bin, χ² 40.0/11). Doc 42 saw it
  at 69.5/11 on 45 tracks; on the 67-track completeness tier it is smaller but
  unmistakable.
- **PDHD neither confirms nor excludes it.** PDHD's own χ² against a flat 1.0
  is 14.4/11 — consistent. But its median per-bin error is 4.9 %, so a +8 % hump
  is only a 1.6 σ per-bin effect, and comparing shapes directly (each
  renormalised to unit geometric mean) gives χ² 14.7 flat vs **12.1 against the
  PDVD hump template — Δχ² = −2.5, marginally *favouring* the hump.** With 6
  tracks PDHD cannot discriminate. **Do not read this table as "the hump is
  PDVD-specific."** Settling that needs more PDHD stopping muons (§9).

## 6. Two things measured on the way

**The inherited `--max-abs-x 305`.** Every published PDHD dQ/dx number
(`pdhd/docs/stm-tagger-chain.md` §6, docs 01 and 02) was taken with
`d42_dqdx_rr.py`'s default 305 cm, inherited verbatim from PDVD's near-CRP rise.
PDHD is cathode-centred with anodes at |x| ≈ 352, so it silently dropped 20 % of
PDHD points. Panel (d) shows the two detectors have **opposite** near-anode
behaviour: PDVD *rises* to 1.09–1.14 beyond |x| = 280 (which is what 305 was for),
PDHD *falls* to 0.86–0.95 beyond |x| ≈ 260. The PDHD fall is gradual, not a
cliff, and cutting at |x| < 250 discards 45 % of plateau points to move the
plateau median by 3.6 % — inside the 3 % systematic floor. **Derived value for
PDHD: no cut** (`--max-abs-x 1e9`), with the ≈ 4 % near-anode depression carried
as a systematic. PDVD keeps 305.

**No attenuation with drift on either detector** (panel c, rr 20–80 cm,
charge-complete). A finite electron lifetime would fall monotonically toward
large drift; neither does. PDHD is 6 % *low* near its anodes and PDVD 11 %
*high* near its CRP — the same geometric structure as panel (d), opposite in
sign, and not lifetime. This supports leaving the lifetime correction unwired
(`protodunevd/params.jsonnet`'s note) but does not measure the lifetime.

## 7. Protons: four searches, one null

The owner asked for proton candidates. There are none usable in either sample.
Four independent searches, in increasing order of independence from the charge
scale:

1. **The shape discriminator does not exist.** Removing one free scale, the
   proton and muon tables differ by ×1.612 (PDHD) / ×1.589 (PDVD) in
   *normalisation* but only **0.062 / 0.060 in shape rms** over 0.5–59.5 cm —
   they are nearly parallel. Tracks whose proton shape rms beats their muon
   shape rms do so by 0.01–0.04, well inside that. Those "proton-shaped" tracks
   (PDHD 10, PDVD 80) have median *range* 221 and 190 cm — they are muons.
   Separating μ from p on this plot is a scale question, which is precisely the
   circularity `sbnd_xin/dqdx_rr_sample/collect_proton_sample.py` documents.
2. **The tagger's own verdict.** `TaggerCheckSTM` status 5 ("proton endpoint",
   `detect_proton`) marks 13 PDHD / 73 PDVD passes, and `persist_stm_fit` writes
   them regardless of the verdict. But they run to 1300 fit points: status 5 is a
   statement about a long muon's *endpoint*, not a proton track. Charge-complete
   and Bragg-bearing, they reduce to 2 PDHD / 11 PDVD, all sitting on the muon
   curve.
3. **Range, which is scale-free.** Charge-complete, contrast ≥ 2, range < 40 cm:
   **0 PDHD, 3 PDVD** (039252_3 blk 750, 039349_0 blk 280, 039349_9 blk 190;
   31–36 cm). All three have k_muon 0.97–1.14 and k_proton 0.58–0.68 — they sit
   on the **muon** curve at the same scale as the muon sample, i.e. they are
   short stopping muons.
4. **The PR chain's own PID.** `tracking-pr.root`'s `T_rec_charge.particle_id`
   tags **2 segments per detector** as 2212 (`50_{pdhd,pdvd}_pr_proton_index.tsv`;
   for scale, the same files carry 1203/1662 muon-tagged and 635/730
   electron-tagged segments). Plotted as triangles/squares in §5:
   - PDVD `039349_10` seg 1107986733 (4.8 cm, 10 pts) and `039349_77` seg
     105876712 (4.3 cm, 9 pts) — genuinely short and 93–98 ke/cm, but k_muon
     0.94–1.05 against k_proton 0.55–0.61. They lie on the **muon** curve.
   - PDHD `028084_1` seg 215729117 (64.3 cm) and `029107_25` seg 210253409
     (37.4 cm) — too long for cosmic protons, and the second's dQ/dx peaks at
     rr ≈ 33 cm rather than at rr = 0, i.e. its residual range is anchored at the
     wrong end. Neither is usable.

**Mechanism, not just a null.** The STM fit runs only on STM-*candidate* main
clusters, so a short proton stub is structurally absent from `tracking-stm.root`;
and these are cosmic-ray data, where stopping protons of usable range are rare.
The proton curves are drawn in §5 anyway, at each detector's own k, so the null
is legible: every measured sample sits on the muon curve, a factor ≈ 1.6 below
the proton curve. **A proton measurement needs a different sample** — beam
protons, or a dedicated selection over PR segments rather than STM fits.

## 8. Honest limits

- **PDHD n = 6.** Enough to confirm the tables at the plateau, not enough to
  measure the Bragg region (7–12 points below rr = 3 cm) or to discriminate
  PDVD's hump.
- **k is not a charge scale** (§3). Nothing here calibrates PDHD or PDVD gain.
- **The lowest rr bins are the least trustworthy on both detectors** — doc
  pdvd/32 showed the STM trajectory's track ends are amputated, and doc 38's
  end trim moves points near the stop. The Bragg bin sits exactly there.
- **PDHD's pooled per-point dQ/dx is not a calorimetry measurement** until the
  drift-volume split of §4.2 is understood. Only the completeness-selected tier
  is quoted here as a scale, and §4.4 says what that does and does not cover.
- **f_low is a diagnostic, not a fix.** It selects tracks whose charge was
  reconstructed completely; it does not recover the charge missing from the
  other 78 % of PDHD passes.
- Both samples are **data** (PDHD 028084/029107, PDVD 039252/3/039349), so the
  agreement is a real test of the recombination model, not a self-consistency
  check against a simulation that used it.

## 9. Recommended next step

The target moved. §4.2 replaces "PDHD loses charge in a corner" with a specific,
first-order defect: **the x<0 drift volume (APA0+APA2, face 0) kills 43-47 % of
its fit points where the x>0 volume kills 29 %, and the surviving points in both
are correct to 5 %.** Imaging more PDHD events buys nothing against this.

Four tests, in the order that narrows fastest. None needs a new dump.

1. ~~Is the charge already missing before the fit?~~ **Answered in §4.2c: yes.**
   The 2-D collection charge per cm handed to the fit is 0.40 / 0.85 / 0.47 /
   1.15 for APA0-3, with identical charge-per-pixel and ROI time extent. It is
   **not** `TrackFitting`. The next step inherits from this: take the same
   comparison one stage further upstream, into the per-APA imaging products
   (`clusters-apa-apa{0..3}-ms-active.tar.gz`, already on disk) and then the SP
   frames, and find the stage at which APA0 and APA2 diverge from APA1 and APA3.
2. **Separate the APA0 hardware fault from whatever APA2 has.** This is now the
   central question — the owner's position is that APA2 is a normal APA, and
   §4.2b rules out a mis-labelling. §4.2 shows they
   fail differently — APA0 in the partial band (0.29), APA2 in the dead band
   (0.31). `pdhd/docs/sp-apa0-plane2.md` explains APA0. APA2 needs its own
   explanation, and the fact that both are face 0 is the clue.
3. **Check `T_bad_ch`**, present in the same ROOT files, against the killed
   points. If they coincide this is a masking problem with a different fix than
   an attribution problem.
4. **Ask whether the tagger inherits it.** `TaggerCheckSTM` normalises to a
   single `mip_dqdx = 56000 e/cm` for the whole detector while the x<0 volume's
   median plateau point sits at 32 000. §4.4 flags this as a plausible mechanism
   for PDHD's low accepted-population Bragg contrast; a per-volume census of the
   tagger's own contrast would confirm or kill it.

The two earlier suggestions still stand but are now lower priority: overlaying
the killed points on the wrapped U/V wire map (`pu/pv/pw` are in
`T_rec_charge`), and imaging runs 027980/027305, which the owner has already
declined and which §4.2 makes clearly not worth it.

Finally, an offer rather than a plan: the completeness cut is new, and nothing
here confirms by eye that it selects *real* stopping muons. The 6 PDHD and 67
PDVD clean stoppers are listed by event and block in
`figs/50_pdhd_s0_tracks.tsv` / `figs/50_pdvd_s0_tracks.tsv` (rows with
`complete = 1` and `contrast >= 2`), so a Bee scan set of the 6 PDHD ones is
cheap to build on request.

---

**Committed products.** This doc;
`scripts/{d50_dqdx_rr_cross,d50_pr_proton_segments,d50_dqdx_rr_plots,d50_deficit_plots}.py`;
`figs/50_dqdx_rr_{overlay,diagnosis}.png`; `figs/50_{pdhd,pdvd}_deficit_anatomy.png`;
`figs/50_{pdhd,pdvd}_s{0,5}_{tracks,summary}.tsv`;
`figs/50_{pdhd,pdvd}_pr_proton_{index,points}.tsv`. The per-point TSVs (7.5–14 MB
each) are regenerable from the Repro block and are not committed. `d42_dqdx_rr.py`
and its PDHD fork are untouched.
