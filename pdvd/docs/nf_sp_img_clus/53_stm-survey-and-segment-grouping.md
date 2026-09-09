# doc pdvd/53 — every piece near the stop, fitted, named and re-groupable

**Status: NOT bit-identical with `survey_enable` on.** With it **off** — the C++
default — every branch of `T_stm_michel` *and* every row and column of
`T_stm_michel_pts` is byte-identical to doc pdvd/51 (§6.1). The two ProtoDUNE
`pr.jsonnet` turn it on; nothing else binds `CheckSTM_Michel`, so SBND exposure
is zero.

## Repro

```bash
# the arms (all four on ONE pinned binary; see sec 6 for why the pin is not optional)
S=pdvd/docs/nf_sp_img_clus/scripts
export PIN=/home/xqian/tmp/d53/libpin
LEG='-S stm_michel_extra={survey_enable:false}'
ARM=d53v    DET=pdvd SRC=d16vnu JOBS=10 $S/d53_run_arms.sh
ARM=d53vleg DET=pdvd SRC=d16vnu JOBS=10 PR_TLA="$LEG" $S/d53_run_arms.sh
ARM=d53h    DET=pdhd SRC=d16hnu JOBS=10 $S/d53_run_arms.sh
ARM=d53hleg DET=pdhd SRC=d16hnu JOBS=10 PR_TLA="$LEG" $S/d53_run_arms.sh

# the gates
python3 $S/d51g_branch_census.py --before 'pdvd/work/*_d53vleg' --before-arm d53vleg \
    --after 'pdvd/work/*_d53v' --after-arm d53v --label "the survey" --out feat_pdvd.txt
python3 $S/d53_survey_census.py --arm-dir 'pdvd/work/*_d53v' --arm d53v \
    --base-dir 'pdvd/work/*_d51gv' --base-arm d51gv --out survey_pdvd.txt

# the display
cd pdhd/stm_michel_scan
python3 prep_stm_michel_scan.py --det pdvd --pin-tranche HEAD:pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
python3 selftest_stm_michel_scan.py --det pdvd
```

## What was asked

The owner, hand-scanning PDVD STM+Michel candidates on port 5017
(`--scan-tag smx1`, arm `d51gv`), reported three things:

1. isolated pieces near the stopping point cannot be clicked or grouped —
   `039253_14` cluster 49 has many small clusters near the Michel end;
2. `039253_13` cluster 102 has an isolated gamma that is not identified as a
   gamma associated with the STM;
3. the PF segment list is a flat dropdown and is unusable once the muon or the
   Michel is broken into many pieces.

with the scope ruling that **this round is scaffolding for the scan**: no change
to the particle flow or to Michel clustering, only that every relevant cluster
participates in the PR chain and can be selected and categorised.

## 1. The premise was half wrong, and the half that was wrong matters

> "I assume they were not clustered together with the Michel… I assume this is
> not done in the current CheckSTM_Michel."

**Symptom.** Isolated pieces near the stop are visible as charge and cannot be
selected, and an obvious isolated gamma is not called one.

**Root cause — and it is two different causes wearing one appearance.**

`039253_13` cluster 102's isolated gamma **is cluster 431, and segment
`431017` was already in `T_rec_charge` at doc pdvd/51.** So were `185006`
(cluster 185) and `184005` (cluster 184) in `039253_14` cluster 49. The PR chain
had fitted them. They were invisible because `prep_stm_michel_scan.py:254-255`
selects `sub_cluster_id // 1000 == cid` ∪ the segment ids the chain *names* in
`T_stm_michel_pts` (roles 3/4/5) — and `431 // 1000 = 431 ≠ 102`, with no role
row. **Nothing named them, so nothing drew them.**

What genuinely was not fitted, in `039253_14` cluster 49 (stop at
−190.68, 183.48, 104.90; every distance a closest approach):

| cluster | d_stop | Q-L bundle | fitted at doc pdvd/51 | why |
|---|---|---|---|---|
| 185 | 14.9 cm | same | **yes** → `185006` | admitted, then dropped by a per-piece test |
| 184 | 34.0 cm | same | **yes** → `184005` | admitted, claimed by neither stage |
| 186 | 35.7 cm | same | no | beyond the 35 cm admission radius |
| 183 | 48.9 cm | same | no | beyond 35 cm |
| 187 | 54.4 cm | same | no | beyond 35 cm |
| 167, 47 | 34.5, 54.7 cm | **flash 288, t0 5168 µs** | no | different bundle |
| 169, 182, 48 | 45.8, 48.3, 23.9 cm | **flash 145, t0 2617 µs** | no | different bundle |

**Six of the eleven blobs the owner can see near that Michel are not there.**
The muon (cluster 49) is flash 203 at t0 3709 µs. The Bee `clustering-global`
layer places every cluster at its **own** bundle's t0-corrected x (doc pdhd/13
§4), so a cluster from another flash lands wherever its own drift correction
puts it — 2617 µs and 5168 µs against 3709 µs is roughly ±550 cm of drift. They
are centimetres away on screen and metres away in the detector. The owner ruled
that the survey fits **same-bundle clusters only**, and it does; the display now
says **ANOTHER FLASH** with the flash id and t0 on any such row, and
`bundle only` hides them from the 3-D view entirely.

**Why it hid.** Three separate reasons that all look like "the chain ignored it":
a fitted segment with no role row is invisible to a selector keyed on roles; a
cluster past 35 cm is never admitted at all; and a cluster from another flash is
drawn where it is not. Only the middle one is a reconstruction gap.

## 2. The fix: one knob, four effects

`CheckSTM_Michel` gains three keys, C++ **default OFF**, turned on in
`cfg/pgrapher/experiment/{protodunevd,pdhd}/pr.jsonnet`:

| knob | default | shipped | what it does |
|---|---|---|---|
| `survey_enable` | `false` | `true` | gates everything below |
| `survey_radius_cm` | 60.0 | 60.0 | admission ring, outer edge, from the stop |
| `survey_max_len_cm` | 25.0 | 25.0 | mirrors `companion_max_len_cm` |

**(a) It widens ADMISSION and nothing else.** The companion admission radius
becomes `stm_michel_admit_radius(michel_dot_radius_cm, stop_gamma_radius_cm,
stop_gamma_enable, survey_radius_cm, survey_enable)` — a maximum over the live
stages, in `StmMichelFunctions` so its stage-off behaviour is doctested. The
Michel's cluster re-test still uses `michel_dot_radius_cm` (15 cm) and the gamma
ring's outer edge is still `stop_gamma_radius_cm` (35 cm), so **a cluster
reached only by the survey radius can become neither a Michel piece nor a
capture gamma.** A guard against `companion_max_len_cm` was added to the Michel
loop so that stays true even if `survey_max_len_cm` is raised — by construction
rather than by a coincidence of two defaults.

The one physics consequence is therefore the **preload perturbation**: an
admitted companion enters `TrackFitting::preload_clusters`, its blobs enter
`prepare_data()`, and the candidate's own muon dQ/dx can move. §6.2 measures it.

**(b) Role 6 — "admitted, fitted, and claimed by no stage."** After the Michel
and gamma stages, every admitted companion's segments are walked and any not
already carrying a role gets role-6 point rows. This deliberately covers the
companions **inside** 35 cm as well as the ones only the survey reached — that
is what makes `185006`, `184005` and the owner's `431017` appear at all.

**(c) The chain says why.** `stm_michel_pts` gains three columns, present only
when the knob is on: `rej`, `d_stop`, `d_body`. `rej` names the gate that
dropped the segment; the two distances are the ones the **shipped** predicates
measured, emitted from the C++ rather than re-derived offline. (doc pdvd/51 §6.5
is the standing record of what an offline re-derivation of exactly these
distances costs.) `write_pc_tree`
(`root/src/PdvdPrMagnifyTrackingVisitor.cxx:293`) takes its column set from the
point cloud, so the ROOT writer needed no change.

| `rej` | gate |
|---|---|
| 1 | outside `michel_dot_radius_cm`, at cluster level |
| 2 | segment too far from the stop |
| 3 | longer than the piece cap |
| 4 | Michel body exclusion, `d_body < d_stop` |
| 5 | outside the gamma ring |
| 6 | gamma body exclusion, against the roles 1–4 snapshot |
| 7 | the Michel already owns the cluster |
| 8 | gamma energy window / `stop_gamma_max_n` |
| 9 | survey only — neither stage was ever offered it |
| 10 | no stop vertex: everything was fitted and nothing examined it |

Codes 1 and 9 are **provisional** and a later stage overwrites them; every other
code is final. Without that precedence the Michel stage's "not mine" (1) masked
the gamma stage's real answer on exactly the clusters the owner asked about.

**(d) The Michel's absorbed shower members get their point rows.** `49004`
carries PDG 11, is a member of `039253_14` cluster 49's Michel shower, and had
**no role row**: doc pdvd/51 wrote points for `michel_arms` only, while the
segments `complete_structure_with_start_segment` absorbs were PDG-stamped and
nothing else. A table grouped off roles put a real Michel member in
"unassigned", in the owner's own item. Behind the same knob, so knob-off stays
byte-identical.

Three new `T_stm_michel` scalars, also knob-gated: `n_survey_clusters`,
`n_survey_segs`, `n_survey_unfit`.

## 3. The display: a grouped object table, not a segment list

> "if the Michel got separated into many pieces, or the muon got segmented into
> many pieces… a table with two major groups."

The dropdown was not too long by accident. Over the 153 PDVD `is_stm` candidates
of the `d51gv` arm a candidate carries a mean of **4.6** PF segments, p90 **9**,
**max 23** — `039253_12` cluster 41 is 8 muon pieces and 15 EM ones. And the
list was capped by the *prep*, not the widget: it showed the candidate's own
cluster plus whatever the chain had named, which is why the pieces the owner
wanted were absent from it rather than merely buried in it.

What replaced it:

* **Rows are objects.** `S<id>` is a fitted PR segment; `C<id>` is a whole
  cluster the PR produced no segment for — charge on screen and nothing else, so
  it can only be grouped as a whole. Both are taggable, both persist.
* **Groups are muon / Michel / gamma / unassigned**, laid out in that order.
  `delta / other` and `straddles the stop` remain valid values with their own
  buttons, so every row already written under tag `smx1` still loads and still
  means what it meant.
* **The table opens in the chain's own grouping** — role 1 muon, 3 Michel,
  5 gamma, 2 delta, 6 unassigned, and for a segment the chain never named,
  pdg 13 → muon. So the scanner is looking at the reconstruction's answer and
  moving what is wrong, not building a grouping from nothing. (`039253_13`
  cluster 102's muon is six segments and only **one** of them, `102015`, carries
  the role-1 profile: without the pdg fallback five muon pieces would open in
  "unassigned".)
* **A role-6 row says why the chain dropped it**, in words, with the two
  distances the shipped predicate measured.
* **`pf_segments` in `labels.json` keeps its meaning** — the scanner's overrides
  and nothing else, so `pf_tagged` stays comparable across rounds. The chain's
  own grouping rides alongside in a new `pf_chain_group`, because without it a
  saved row reading `{"431017": "gamma"}` cannot be told from one where the
  chain already said gamma and the scanner merely agreed.

Two prep changes make the rest possible:

* `load_image` **keeps the per-point `cluster_id`**. It was read, reduced to the
  in-bundle boolean, and thrown away, so no drawn image point carried any
  identity — there was no route from a point on screen to an object at all. This
  is what makes an unfitted piece selectable.
* `IMAGE_STOP_R` 40 → **60 cm**, tracking `survey_radius_cm`. Beyond it points
  fall into `image_far`, which is thinned to `IMAGE_FAR_MAX`; a 60 cm survey
  behind a 40 cm image radius would draw the new pieces subsampled and
  half-clickable, and look fine while doing it.

## 4. What the survey put in front of the scanner

`d53v` (PDVD, 119 events, 579 candidates, 153 `is_stm`) and `d53h` (PDHD, 61
events, 325 candidates). Per candidate:

| | mean | p50 | p90 | max | total |
|---|---|---|---|---|---|
| PDVD survey segments | 1.51 | 1 | 4.0 | 30 | **872** |
| PDVD survey clusters | 1.44 | 1 | 4.0 | 19 | 834 |
| PDVD clusters admitted but unfittable | 0.00 | 0 | 0 | 1 | 2 |

**All 839 surveyed segments carrying a reject code are in the candidate's own
Q-L bundle**, and zero are from another flash. That is a check on the scope
ruling, not a finding: the survey admits same-bundle clusters only, so a
non-zero second row would have been a defect.

Why each was left unclaimed (PDVD, one row per **segment**):

| `rej` | gate | n | |
|---|---|---|---|
| 9 | survey only — neither stage was offered it | 494 | 58.9 % |
| 6 | **gamma body exclusion** | 275 | 32.8 % |
| 4 | Michel body exclusion | 52 | 6.2 % |
| 5 | outside the gamma ring | 11 | 1.3 % |
| 8 | energy window / per-candidate cap | 5 | 0.6 % |
| 2 | segment too far from the stop | 2 | 0.2 % |

**The single discriminator doing the most work is the gamma body exclusion**,
and it is not doing it marginally: the margin `d_stop − d_body` has median
**8.29 cm** (p10 0.87, p90 17.76), and only **4 of 275** are rejected by under
1 mm. The Michel body exclusion is tighter but still comfortable — median
2.34 cm, 1 of 52 under 1 mm. Neither is a coin flip at these radii.

### The owner's three items, on the new arm

| item | what the chain now says |
|---|---|
| `039253_13` cl 102 | the isolated gamma is **`431017`**, role 6, **rejected by the gamma body exclusion**: `d_stop` 33.09 cm, `d_body` **31.72** cm — 1.38 cm closer to the muon body than to the stop, i.e. 4 % of the baseline. **This is the one to scan.** |
| `039253_14` cl 49 | five same-bundle pieces, all now fitted and named: `185007` (Michel body exclusion, 14.51 vs 7.36), `184006` (gamma body exclusion, 33.98 vs 23.46), and `183005` / `186008` / `187009` at 48.9 / 35.7 / 54.4 cm, survey-only. The Michel is now **two** role-3 segments, `49003` **and `49004`** |
| `039252_15` cl 77, `039252_0` cl 77 | unchanged from doc pdvd/51 — the bridged Michel is 35 role-3 points over `265003`/`265004`, and the capture gamma is still `206004` at role 5 |

## 5. Two things this round got wrong first

Both were caught by measuring rather than by reading, and both would have been
published as physics.

**5.1 The reject code was masked by the stage that did not care.** `note_cl`
kept the *first* gate to fire, and the Michel loop runs before the gamma loop —
so `039253_13` cluster 431 came out as "outside the Michel radius", which is
true, uninteresting, and hides the answer. Codes 1 and 9 are now provisional and
a later stage overwrites them.

**5.2 `d_body` was an upper bound, not a minimum — and the error looked exactly
like a physics result.** The gamma's cluster-level body exclusion breaks out of
its loop as soon as one body point undercuts the stop:

```cpp
d_body_cl = std::min(d_body_cl, (bp - bp0).magnitude());
if (d_body_cl < d_cl) break;          // already decided
```

That is correct for the **verdict** and wrong for the **number**: the value
recorded is whatever the first undercutting body point gave, which is an upper
bound on the true minimum. Published as-is, the first census read:

> gamma body exclusion, n=275, median margin **0.405 cm**, **60 of 275 rejected
> by less than 1 mm** — with the ten narrowest at 0.000–0.017 cm.

which says the discriminator is rounding, not discriminating. It is not true.
`039252_8` cluster 97's segment `466032` reported `d_body` 27.42 cm against a
true minimum of **0.41 cm** — a blob sitting *on* the muon, reported as
"rejected by 0.02 cm". With the loop run out under the survey knob (the verdict
cannot change: finishing can only lower a value already below the threshold) the
same census reads **median 8.29 cm and 4 of 275 under 1 mm**, which is the
opposite conclusion.

The lesson is doc pdvd/51 §6.5's, one layer down: it is not enough to emit the
distance from the shipped predicate rather than re-deriving it offline. The
shipped predicate is optimised to answer a *question*, and the intermediate it
leaves behind need not be the quantity its name suggests.

## 6. Gates

**Binary pin.** All four arms ran under `LD_LIBRARY_PATH=/home/xqian/tmp/d53/libpin`
with `libWireCellClus.so` md5 `419b9dbfd777`, printed before and after each arm
and unchanged; no job died in the loader. The arms were re-run from scratch
after the §5.2 fix so that all four share one binary.

**6.1 Legacy equivalence — a true byte-identical gate.** Because the C++ default
is OFF, `survey_enable:false` is not a census waiver, it is the real thing:

| | matched candidates | shared branches | bit-identical | `is_stm` flips |
|---|---|---|---|---|
| `d53vleg` vs `d51gv` | 579 | 106 | **579 / 579** | 0 |
| `d53hleg` vs `d51gh` | 325 | 106 | **325 / 325** | 0 |

No shared branch moved on any candidate, on either detector. `T_stm_michel_pts`
is byte-identical too — same nine columns, same rows: the role-6 rows, the three
new columns and the role-3 rows for absorbed shower members are all behind the
knob. (Both comparisons show two branches *new at HEAD* —
`muon_mcs_cathode_angles`, `muon_mcs_cathode_segs`. They are not this round's:
they arrived with `9de28b32` at 16:45, eight minutes after the `d51gv` arm was
written at 16:37. That epoch gap is why this round carries its own `…leg`
baseline instead of comparing to `d51gv` directly.)

**6.2 The feature — the preload perturbation, which is not small.**
`d53v` vs `d53vleg`: same binary, one key.

| | matched | bit-identical | movers | `is_stm` flips |
|---|---|---|---|---|
| PDVD | 579 | 464 / 579 | **115 (20 %)** | **2** |
| PDHD | 325 | 245 / 325 | **80 (25 %)** | 0 |

This is far more than doc pdhd/15's six movers, and the reason is arithmetic:
that round added ~1 companion to a handful of candidates, this one adds
0.9 companions to *every* candidate that has a neighbour within 60 cm. The
branches that move are the muon's own profile quantities — `muon_ke_dqdx`
(60 PDVD candidates), `plateau_med`, `ks_mu`, `contrast`, `muon_len` — exactly
what `preload_clusters` → `prepare_data()` can shift.

**Every mover is accounted for.** On PDVD **115 of 115** movers surveyed at
least one segment; on PDHD **79 of 80** did, and the one exception,
`029107_19` cluster 120, has `n_survey_clusters` 0 with `n_stop_gammas` 1 — a
companion the widened radius admitted and the *gamma* stage then claimed, so it
left no role-6 row. Not a single candidate moved without the survey having
touched it. Conversely 211 PDVD candidates surveyed something and did **not**
move, so admitting a companion perturbs the fit about a third of the time.

**The two `is_stm` flips are reported, not tuned** (CLAUDE.md §5.7):

* `039349_53` cluster 51: **1 → 0**, `contrast` 1.3022 → 1.3169,
  `muon_len` 242.09 → 242.86 — a marginal candidate that moved across a
  threshold by a hair.
* `039349_64` cluster 61: **0 → 1**, `contrast` 0.5268 → **1.4977**,
  `muon_len` 292.49 → 290.80. This one is not marginal — the contrast nearly
  tripled, which means the muon profile itself changed materially, not that a
  cut was grazed. **It should be scanned before the survey radius is trusted at
  60 cm.**

One consequence downstream: the PDVD scan sheet gains exactly one candidate
(`039349_42` cluster 41, which now passes the prep's profile/length filters) and
loses none.

**6.3 The particle flow does not grow.** Counting `mc.json` nodes recursively,
survey off → on: PDVD **3603 → 3592** (−11 over 119 events, 24 events changed),
PDHD **2557 → 2555** (−2 over 61, 7 events changed), and the changes go both
ways. A role-6 segment lives in a companion cluster with no graph edge into the
muon's component, so the tree walk cannot reach it at any knob setting — the
survey is invisible to the renderer, which is what "do not worry about the PF
yet" required. The small net change is the §6.2 perturbation moving fits, not
the survey adding nodes.

**6.4 Compiled-config proof.** `wcsonnet` on both ProtoDUNE drivers, against the
same file at HEAD: **exactly one node differs** (`CheckSTM_Michel:pr`), by
exactly three added keys (`survey_enable`, `survey_radius_cm`,
`survey_max_len_cm`), with no key changed or dropped, on both detectors. Only
`cfg/pgrapher/experiment/{protodunevd,pdhd}/pr.jsonnet` were touched; SBND's own
`pr.jsonnet` is unmodified.

**6.5 Tests.**

* `./build/clus/wcdoctest-clus` — 340 cases, **23 272 assertions**, 0 failed,
  including a new suite pinning `stm_michel_admit_radius` (each stage off drops
  exactly its own contribution; survey-off reproduces 35 cm for *every* survey
  radius; a non-finite radius contributes nothing rather than poisoning the
  maximum) and the ring/survey partition on the owner's own measured distances.
* `doctest_check_stm_michel_defaults.cxx` round-trips the three new keys.
* `selftest_stm_michel_scan.py`: **51 117** checks PDVD, **30 149** PDHD, 0
  failed — including the new `[Q]` group, with a causal negative control on each
  claim (emptying `chain_role` must collapse the table to muon/unassigned, and
  the control asserts it was not already collapsed).
* `selftest_smx3d_browser.py`: **82 + 82** checks in headless chromium, 0
  failed, driving the grouped table's real selection and the four move buttons.

**6.6 The live scan (M13).** `smx1` was backed up before anything, re-prepped
with `--pin-tranche`, and kept. All **12** labels still resolve to a sheet row,
all still in tranche 1, tranche 1 still 60 rows, and **none of the 12 was
renumbered** — the one added candidate sorts after them all. 224 of 568
`scan_id`s did shift, which is what inserting a row into a positional index
does; the owner's rows are not among them.

## 7. What this round did not do, and what is open

**Not done, deliberately.** No object is re-assigned, no Michel is re-clustered,
no particle-flow node is added or moved. The survey pieces are fitted, named and
selectable; deciding what they *are* is the scan's job and the next round's.

**Open, in the order they matter:**

1. **`039349_64` cluster 61** — the `is_stm` 0 → 1 flip with `contrast`
   0.53 → 1.50. A preload perturbation that changes a shape metric threefold is
   not a threshold being grazed; scan it before trusting `survey_radius_cm` at
   60 cm. `039349_53` cluster 51 (1 → 0, contrast 1.302 → 1.317) is the ordinary
   kind and needs only a look.
2. **`039253_13` cluster 102 / segment `431017`** — the owner's own isolated
   gamma, rejected by the gamma body exclusion at `d_stop` 33.09 vs `d_body`
   31.72. If the scan calls it a real capture gamma, the body exclusion is too
   aggressive for blobs at large radius; if it calls it a satellite of the muon,
   the cut is right and the 4 % margin is simply where this class lives.
3. **The 20 % / 25 % mover rate.** It is the price of the survey and it is paid
   on the *muon's own* profile branches. Nothing in this round's evidence says
   whether the perturbed fits are better or worse — only that they differ. A
   smaller `survey_radius_cm` would buy fewer movers and fewer visible pieces;
   the trade is the owner's to set after scanning.
4. **`survey_radius_cm` = 60 cm has no measurement behind it.** It was chosen to
   put the owner's named pieces on screen (the farthest, `187009`, is at
   54.4 cm) and to match the display's near-image radius. That is a scanning
   argument, not a physics one — the same standing caveat doc pdvd/51 §9 carries
   for `stop_gamma_radius_cm` = 35.
5. **A pre-existing gap, found beside this work and fixed here rather than
   silently:** doc pdvd/51 gave the capture gamma a dQ/dx-panel source and
   marker and then never filled it, so **every capture gamma has been missing
   from that panel since it shipped**. `gamma` and the new `survey` are both
   filled now.
6. **`039252_11` has no STM candidate** and so trips the arm runner's completion
   check in every arm, this round's and doc pdvd/51's alike. It is a
   candidate-less event, not an incomplete job: 119 of 120 is the real PDVD
   count.
