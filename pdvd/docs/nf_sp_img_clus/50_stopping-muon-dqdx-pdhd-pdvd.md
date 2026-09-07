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
2. PDHD's clean-stopper yield looked 11× worse than PDVD's. **It is not a
   charge or calibration difference.** Both detectors put the *same* scale on
   charge-complete tracks (k = 0.89 vs 0.94) and follow the *same* k-vs-
   completeness curve. They differ only in how many fitted points carry full
   charge: median f_low **0.262 on PDHD vs 0.042 on PDVD**.
3. The cut that destroys the PDHD sample is doc-55's **muon shape rms ≤ 0.10**
   (33 → 1 tracks). It is not a stopping-muon selector; it is a charge-
   completeness selector in disguise. Replacing it with an explicit
   completeness cut gives **6 PDHD / 67 PDVD** clean stopping muons and both
   detectors then agree with their own expectation.
4. **No usable stopping-proton population exists in either sample**, and the
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
```

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
- **f_low is a diagnostic, not a fix.** It selects tracks whose charge was
  reconstructed completely; it does not recover the charge missing from the
  other 78 % of PDHD passes.
- Both samples are **data** (PDHD 028084/029107, PDVD 039252/3/039349), so the
  agreement is a real test of the recombination model, not a self-consistency
  check against a simulation that used it.

## 9. Recommended next step

**Measure the PDHD charge deficit, not more PDHD events.** Imaging the two
un-imaged PDHD runs (027980, 027305, ≈ 66 events) would roughly double every
tier — 6 → ~12 clean tracks — and still not settle the hump. The 78 % of PDHD
passes with f_low > 0.05 are the real target: if the wrapped-plane attribution
of `pdhd/docs/04` §8 is the cause, fixing it converts PDHD's 303 accepted passes
into a sample the size of PDVD's and makes the hump decidable on two detectors.
The concrete first step is to check whether f_low correlates with the wrapped
(U/V) plane fraction along the trajectory — `T_rec_charge` already carries
`pu/pv/pw` per point, so it needs no new dump.

Second, an open offer rather than a plan: the completeness cut is new, and
nothing here confirms by eye that it selects *real* stopping muons. The 6 PDHD
and 67 PDVD clean stoppers are listed by event and block in
`figs/50_pdhd_s0_tracks.tsv` / `figs/50_pdvd_s0_tracks.tsv` (rows with
`complete = 1` and `contrast >= 2`), so a Bee scan set of the 6 PDHD ones is
cheap to build on request. Worth having before this tier is used for anything
beyond doc 50, but it costs owner scan time, so it is not assumed here.

---

**Committed products.** This doc;
`scripts/{d50_dqdx_rr_cross,d50_pr_proton_segments,d50_dqdx_rr_plots}.py`;
`figs/50_dqdx_rr_{overlay,diagnosis}.png`;
`figs/50_{pdhd,pdvd}_s{0,5}_{tracks,summary}.tsv`;
`figs/50_{pdhd,pdvd}_pr_proton_{index,points}.tsv`. The per-point TSVs (7.5–14 MB
each) are regenerable from the Repro block and are not committed. `d42_dqdx_rr.py`
and its PDHD fork are untouched.
