# 145 — Items 3, 4 and 5 on SBND: pricing the pointing test, naming the rest-mass escape, and opening the PID round

Doc 144 closed the owner's items 1 (flip `excl_t0_frame` ON) and 2 (the `494297`
use-after-free).  Items **3, 4 and 5** — his three *"improve"* items from the Bee
scan — were left **diagnosed but not improved**.  This doc is that round.

It is deliberately **not** three investigations.  Doc 144's diagnoses collapse
them into three different *kinds* of work:

| item | the owner's words | what doc 144 found | what this round does |
|---|---|---|---|
| **4** | *"understand why the energy was added for idx 3, improve"* | understood **and fixed**, toolkit `7c4bf46a`, default OFF, on one supporting event (§13.2.1) | **price it on 3067 events** — §3 |
| **3b** | *"examine idx 6, 7 … to improve"* (177536) | the muon is **split**, and the split invents a 105.7 MeV rest mass; 21 splits in the population, 6 pay (§14.2.1) | **name the escape** from a mechanism that already exists — §4 |
| **3a + 5** | *"… idx 6, 7"* (347890) and *"improve the hadronic shower reconstruction"* (137238) | **the same defect** — a track-like object typed EM (§14.1, §15.1) | **round 1 of one PID campaign** — §5 |

---

## 0 Repro block

```bash
cd /home/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin

# --- the binary, pinned twice: Round A and Round B run CONCURRENTLY on
# --- different libraries, so each pins its own (feedback_shared_tree_binary_pin)
#   /home/xqian/tmp/d145_libpin        7f4a718d9795f515e032d705f492e58b  (toolkit 7c4bf46a, as committed)
#   /home/xqian/tmp/d145_libpin_cont   d375814580ea68814b1ec041787a1f22  (+ the item-3b instrumentation)

# A. the epoch bridge -- 13 events, knob OFF, on the NEW pin (sec 2)
JOBS=13 ./scripts/pr145_arms.sh bridge
for s in mcp1k mcp2k nuecc48; do
  ./scripts/analysis/pr143/pr143_compare_arms.py work-$s-d145bridge work-$s-d144fixprod --jobs 8
done

# B. Round A -- the armed 3067-event arm, and its census (sec 3)
JOBS=16 ./scripts/pr145_arms.sh np
./scripts/pr145_pointing_census.py --arms work-{mcp1k,mcp2k,nuecc48,ncpi0}-d145np \
    --tsv docs/pr/pr145-pointing-census.tsv

# C. Round B -- the split census, then the instrumented probe (sec 4)
./scripts/pr145_split_census.py --tsv docs/pr/pr145-splitcensus.tsv
JOBS=8 ./scripts/pr145_cont_probe.sh
```

---

## 1 What was already true when this round opened

`7c4bf46a` had shipped item 4's fix behind `kine_near_pointing_impact`
(cm, `0` = no test) and `kine_near_pointing_miss_deg`, **default OFF**, with the
evidence standing on a single event.  Its own commit message says the bar:

> NOT FLIPPED.  It is a hypothesis with one supporting event; it needs its own
> 3067-event arm and its own negative control before it earns a default.

That is what §3 supplies.  Nothing in this doc flips a default; a production
default flip is CLAUDE.md §5.1 stop-and-ask territory and the recommendation
goes back to the owner with the numbers.

**Two gaps found while grounding the round, both closed here:**

- `clus/test/doctest_clus_knob_defaults.cxx` pinned the pr/129 siblings
  (`kine_guard_freed_impact`, `..._miss_deg`) but had **no entry for either
  pr/144 key**, so the default-OFF guarantee of the new pointing test was
  unasserted by the suite.  Added.
- `clus/inc/WireCellClus/NeutrinoPatternBase.h:2331-2332` declares the two
  pr/144 members **without** the `* units::cm` scaling its neighbours carry
  (`m_kine_near_gap{5*units::cm}`).  It is harmless today only because `0.0`
  scales to `0.0`.  **Reported, not fixed** — it is a pre-existing latent trap
  and belongs in its own change (CLAUDE.md §5 tie-breaker).

---

## 2 The epoch bridge — what licenses the free negative control

`work-*-d144fixprod` is doc 144's production arm and the obvious negative
control for §3: it is on disk, it is 3067 events, and it costs nothing.  But it
was produced by the library built at **`25baa8aa`**, and this round runs
**`7c4bf46a`**.  `7c4bf46a`'s committed T0 proof covers the compiled **config**;
it says nothing about the two **libraries**.  Using it as a control without
closing that gap is exactly the trap `feedback_check_the_cfg_epoch_between_arms`
and `feedback_stale_stage_a_baseline` record.

So: a **knob-off** arm on the new pin over the 13-event `d144np2` manifest.
That manifest is not arbitrary — it carries `494297` (doc 144's crash), `393505`
(item 4), `177536` and `98844` (item 3b's two payers), `347890` (item 3a) and
`137238` (item 5).

**Result — 13/13 `rc=0`, and 0 pointing log lines (the arm really is knob-off).**

| artefact | mcp1k (1) | mcp2k (10) | nuecc48 (2) |
|---|---|---|---|
| `nusel-evt*.tsv` | SAME | SAME | SAME |
| `tracking-pr.root` | SAME | SAME | SAME |
| `mabc-pr.zip` | SAME | SAME | SAME |
| `pctree-pr-evt*.tar.gz` | SAME | SAME | SAME |
| `calib-pr-evt*.json` | SAME | SAME | SAME |

by member-content hash (`pr143_compare_arms.py`), never `cmp`/`md5sum` on an
archive (M2).

The comparer additionally reports `nusel-table.tsv DIFF` / `nusel-events.tsv
DIFF` on all three samples.  **That is not a failure and must not be read as
one:** those two files are *arm-level* tables merged over every event in the
out_root, so a 13-event arm and a 3067-event arm necessarily differ in row set.
Checked properly — every row of the bridge arm found verbatim in the production
arm — they agree:

```
mcp1k:   header SAME (ws-normalised)  rowsA=13  rows-of-A-not-in-B=0
mcp2k:   header SAME (ws-normalised)  rowsA=92  rows-of-A-not-in-B=0
nuecc48: header SAME (ws-normalised)  rowsA=34  rows-of-A-not-in-B=0
```

The whitespace normalisation is load-bearing and worth recording: these tables
are **column-aligned with padding whose width depends on the widest value in the
arm**, so a 1-event arm pads narrower than a 1000-event arm and a raw string
compare reports a difference that is pure formatting.  On mcp1k the header
itself differs that way (`stmfit  lm  label` vs `stmfit     lm  label`).

**`d144fixprod` is therefore a licensed zero-cost negative control for §3.**

---

## 4 Item 3b — why `flag_reduce` misses, named from the data

### 4.1 The reframing

Doc 144 §14.2.1 recommended deciding "whether `rest_term_rules` should be
charged per *particle* rather than per *node*".  That reads as though no
per-particle rule exists.  **One does.**
`NeutrinoKinematics.cxx:331-347` carries `flag_reduce`, a particle-continuation
detector, and `:375-388` already undoes the rest term charged to the previous
segment when it fires.  So the question is not "design a predicate" but **"why
do 6 of 21 escape a mechanism that catches the others?"**

Five escapes are visible in the code, and all five are separable by log lines:

| escape | where | why it can miss |
|---|---|---|
| `sign` | `:344-346` | `curr_pdg == prev_pdg` is **signed**, so 13 vs −13 never matches, and the μ↔π clause covers only `+211`/`+13` |
| `pool` | `:230`, `:615`, `:784`, `:894` | the rest term is charged at **four** admission sites; the reduction exists at **one** (the BFS) |
| `visited` | `:329` | `used_vertices.count(curr_vtx)` skips the entire reduction block |
| `untyped` | `:344` | a parent segment with `pdg == 0` breaks the chain — found by hand-reading, not predicted |
| `genuine` | — | two real particles; no defect |

### 4.2 The instrumentation

`kine_continuation_debug` (toolkit, **default OFF**, key-suppressed ⇒
byte-identical) logs the **signed** pdg on both sides of every continuation
test, both segment graph indices, whether the reduction fired, the
already-visited early-continue, and — added after the first probe came back
incomplete — the rest term charged by `push_shower_kine`, which the first pass
could not see.

It is **log-only**: no arithmetic reads it.  Proven, not asserted — the probe
arm reproduces `d144on` exactly on 177536
(`type=[2212,13,11,11,13]`, `add=219.92`, `Enu=1339.8`, identical to the
decimal).

Gates: **T0** — knob-off compiled config `cmp` rc 0 against the committed
`7c4bf46a`.  **T1** — arming adds exactly one key,
`"kine_continuation_debug": true`.  `build/clus/wcdoctest-clus` 323 cases /
23067 assertions, 0 failed.

> A trap worth recording, because the first attempt at these gates passed
> vacuously: a compile without `pipeline_names` produces a config with **no
> kine block at all**, so the diff was empty and the "T1" looked like a
> byte-identical result.  The tell was that a known production-ON key
> (`kine_mainvtx_used_guard`) was also missing.  Always confirm a sibling key
> is present before reading an empty diff as proof (M6).

### 4.3 The answer

`work-{mcp1k,mcp2k}-d145cont2`, 21/21 `rc=0`, attributed by
`pr145_cont_attribute.py` (`docs/pr/pr145-contattr.tsv`):

| escape | of the 6 payers | of all 21 |
|---|---|---|
| **`pool`** | **4** | 4 |
| `untyped` | 1 | 1 |
| `reduced_ok` — no escape, no defect | 1 | 9 |
| `single` — only one rest term charged | 0 | 5 |
| `visited` | 0 | 2 |
| unattributed | **0** | **0** |

**The dominant escape is `pool`, and 177536 is its clearest case.** Its two
muon halves enter through *two different non-BFS paths* — the 276.0 MeV half as
a **long-muon shower** (`push_shower_kine`), the 644.3 MeV half through
**`kine_count_guard_freed`** — so the BFS never sees the pair and `flag_reduce`
is never even evaluated.  There is no `TEST` line on the event at all.  The
arithmetic closes exactly:

```
kine_cont: CHARGE seg=17 pdg=2212 rest_mev=8.60 ke_mev=191.17
kine_cont: CHARGE_SHOWER start_seg=18 pdg=13 rest_mev=105.66 ke_mev=276.00
kine_cont: SKIP_VISITED vtx=17 prev_seg=17 prev_pdg=2212
kine_cont: CHARGE seg=8 pdg=13 rest_mev=105.66 ke_mev=644.34
```
(the 644.34 charge is immediately followed by
`kine_count_guard_freed: COUNT seg idx=8 cluster=17 pdg=13 ke_mev=644.34`, which
is what attributes it to that pool)

    8.60 + 105.66 + 105.66 = 219.92 = kine_reco_add_energy

against the OFF arm's `8.60 + 105.66 = 114.26`.

### 4.4 Two corrections to doc 144 §14.2.1, both from primary source

1. **The "only two of the counting sites call `rest_term_rules`" explanation for
   the 15 non-payers is refuted.** They pay nothing because `flag_reduce`
   *fires* — 9 of 21 are `reduced_ok`, with a `REDUCE` line on the record — or
   because only one rest term was charged at all (5 `single`).
2. **Not all 6 payers are spurious.** mcp2k **78743** is `reduced_ok`: every
   μ/π continuation fired and both reductions applied.  Its +105.7 MeV is a
   genuinely *extra* muon chain the ON arm counts, not a double count.  So the
   defect count is **5 of 21, not 6**, and doc 144's "270.0 MeV" figure — which
   also could not be reproduced from the definition that section states (the sum
   over the six is **667.9 MeV**) — should not be quoted.

### 4.5 Why no physics fix ships in this round

The named escape does not hand over a safe fix.  Reducing the `pool` case means
detecting that a shower-path admission and a guard-freed-pool admission are *the
same particle* — a **cross-admission-path continuation test that does not exist
today**, not a relocation of `flag_reduce`.  It has to be built so that two
genuine muons from one vertex still pay twice, and that is its own round with
its own negative control.  Landing a speculative version here would be a
behaviour change on the strength of 5 events.

**What ships:** the instrumentation (default OFF), the attribution, and the
named fix shape.  **Recommended next step:** a cross-pool continuation test
keyed on the same predicate `flag_reduce` uses, evaluated once after all four
admission sites have run, behind its own default-OFF knob — and gated on the
`reduced_ok` and `single` events as negative controls, since those must not move.

### 4.6 An unrelated defect found on the way — reported, not fixed

Hand-reading mcp1k 407280 showed `seg=18 pdg=13 rest_mev=105.66 ke_mev=1.48`: a
1.48 MeV fragment typed as a muon, charged a full muon rest mass.  Across the
1435 production dumps, **1808 μ/π nodes carry 205 951 MeV of rest mass into
`Enu`**.

A caveat that has to come first, because the obvious census is misleading: 789
of those 1808 nodes (43.6 %) have a kinetic energy *below* their own rest term,
and **that is ordinary physics** — a stopping pion still carries 139.57 MeV of
rest mass that belongs in the neutrino energy.  It is not a defect and must not
be quoted as one.

What is anomalous is narrower: **9 nodes have kinetic energy exactly `0.000` and
are still charged a full rest mass**, worth **1120.5 MeV** (0.54 % of all μ/π
rest mass).

    mcp1k 277298 pdg= 211  139.57      mcp2k 350354 pdg= 211  139.57
    mcp1k 412208 pdg=  13  105.66      mcp2k  72940 pdg= 211  139.57
    mcp2k 400029 pdg= 211  139.57      mcp2k  99035 pdg=  13  105.66
    mcp2k 171572 pdg= 211  139.57      mcp2k 281567 pdg=  13  105.66
                                       mcp2k 179765 pdg=  13  105.66

This is doc 85's known "zero-energy degenerate rows" class arriving in the
kinematics rather than the score table.  **Reported, not fixed** — it is
unrelated to item 3b and belongs in its own change (CLAUDE.md §5 tie-breaker).

---

## 5 Item 3a + 5 — the PID round: PRE-REGISTRATION

*Written and committed **before** any blind object was scored.  Doc 141 §22
spent a full round on a pre-registered predictor that scored precision 0.500,
and the reason that round is still usable is that the prediction was on the
record first.  This section keeps that discipline.*

### 5.1 Why one round covers both items

347890's far half is a track whose **PID flips 211 → 11**, after which doc 84
r4's partner filter refuses it *by design* (`TaggerCheckNeutrino.cxx:1418-1431`
admits only `optype == 13`, or `211` when `track_partner`; EM is not admitted).
137238 is a hadronic shower **absorbed into an EM shower**.  Both are a
track-like object typed EM.  Doc 144 §15.1's census already ruled out the
exclusion-threshold reading — Σ`kine_n_excluded` moves −1.5 %, Σ excluded energy
−4.4 %, and 137238 sits in an **8-event tail**, not a systematic collapse.

### 5.2 The mechanism being pre-registered

> For a **real track**, the charge-derived and range-derived energies agree,
> because the range hypothesis is the right one.  For an **EM shower typed as a
> muon**, the range hypothesis is wrong and the two diverge.  So
> `kine_charge / kine_range` should separate TRACK from EM, high = EM.

This is registered as a **mechanism, not as a number** — see §5.4 for why the
number cannot be carried across.

### 5.3 What the mechanism scores on the training labels

`docs/pr/pr141-pid-score.tsv`, the owner's 18 verdicts, split by **his own
`weak` flag**:

| | n | `kine_charge / kine_range` |
|---|---|---|
| confident TRACK | 9 | 0.709, 0.731, 0.742, 0.760, 0.767, 0.782, 0.823, 0.842, **0.844** |
| confident EM | 6 | 0.771, **0.938**, 1.670, 2.081, 2.635, 6.213 |

A cut at **> 0.90** gives **5/6 EM caught, 0/9 TRACK contamination** — precision
1.000, recall 0.833.  Both TRACKs that contaminate at the pooled all-18 level
are `weak` labels (259542 → 2.676, 176502 → 1.158).

It is **not length in disguise**: a 54.7 cm confident TRACK sits at 0.844 while
an 8.7 cm confident EM sits at 2.081 and a 78.0 cm confident EM at 2.635.  Doc
141 §22.2 marked this column "overlaps" and moved on; splitting on the owner's
confidence flag is what separates it.

### 5.4 Why the threshold is provisional and must be re-fit on-epoch

**These labels were measured pre-flip, and `excl_t0_frame` is precisely a charge
re-attribution patch** — doc 144 §5.2's finding is "the charge changes owner,
and that is the whole effect".  So the ratio's **numerator moved systematically**
between the epoch that produced 0.90 and any epoch this round would test on.
Worse, **`work-pr140r2-off-*` is no longer on disk** — it was retired — so the
training arm cannot be re-read.

Carrying "0.90" forward and scoring a blind set with it would be doc 141 §22's
post-hoc trap one layer up: a number fitted on one epoch, presented as a
prediction on another.  So the pre-registration is:

1. the **mechanism** of §5.2, and
2. the threshold **re-fit on-epoch**, from the same 15 confident labels
   re-measured on `work-*-d144fixprod` through a positional (y,z) join,
3. and only then scored on a blind set.

**The (y,z) join is a step-1 dependency, not a port-forward nicety.** Object ids
renumber under any reconstruction change; doc 144 §7.2 is where that already
invalidated the π⁰ 66-set census, and the join has been owed since.

### 5.5 The blind set, and its one contamination

Selected **by mechanism, not by outcome**: doc 144 §15.1's 8-event
pool-empties tail, plus 347890's far half and 137238.

    mcp2k   321235   n  6-> 1   E   765.0 ->   2.0 MeV
    mcp1k   345633   n  6-> 1   E   588.3 ->   1.6 MeV
    nuecc48 137238   n  9-> 1   E   428.9 -> 124.5 MeV
    mcp2k   100222   n  5-> 1   E   359.0 -> 135.0 MeV
    nuecc48 235435   n  5-> 0   E   147.4 ->   0.0 MeV
    ncpi0    56982   n  5-> 1   E   142.6 ->   1.3 MeV
    mcp2k   171528   n  5-> 1   E   101.6 ->   1.4 MeV
    mcp2k    91917   n  5-> 1   E    83.1 ->   2.3 MeV

**Contamination, declared up front: `235435` is in BOTH sets.** It is the
fifth row of the tail *and* it carries a pr141 training label (obj `2024`,
confident EM, q/range 2.081).  That object is excluded from the blind score and
reported separately; it must not count as both training and test.

### 5.6 What round 1 delivers

**A measured precision on a blind set — a number, not a fix.**  If the
mechanism dies on the blind set, that is the deliverable and it gets written
down, the way doc 141 §22's 0.500 was.  The charge-profile work comes after, and
only if this survives, carrying the two traps already paid for: filter
zero-charge fit points before any dq/dx median, and use the electron template as
a **proton veto**, never a positive electron ID.

---

*Sections 3 (Round A) and 4 (Round B) are filled in as their arms land.*
