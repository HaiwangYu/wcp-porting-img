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
JOBS=8 ./scripts/pr145_cont_probe.sh                    # TAG=d145cont2 (M13: fresh tag per run)
./scripts/pr145_cont_attribute.py --tag d145cont2 --tsv docs/pr/pr145-contattr.tsv

# D. the gate and the sentinels, both arms (secs 3.2, 3.4)
for s in ncpi0 nuecc48 mcp1k mcp2k; do
  ./scripts/analysis/pr143/pr143_compare_arms.py work-$s-d145np work-$s-d144fixprod --jobs 8
done
./scripts/pr127_sentinels.py --arms 'work-*-d144fixprod'   # 19 PASS / 0 FAIL / 4 OPEN / 7 INERT
./scripts/pr127_sentinels.py --arms 'work-*-d145np'        # 20 PASS / 0 FAIL / 3 OPEN / 7 INERT

# E. Round C -- the join, then the on-epoch set and its blind sheet (sec 5)
./scripts/pr145_yz_join.py --tsv docs/pr/pr145-labels-onepoch.tsv
./scripts/pr145_pidset.py --tsv docs/pr/pr145-pidset.tsv \
    --manifest docs/pr/pr145-pidscan-manifest.tsv
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

### 2.1 The bridge licenses ONE binary, and §4 needed its own

Stated precisely, because it is easy to over-read: the bridge above licenses
`d144fixprod` against **`7f4a718d…`**, the Round A pin, and nothing else.  §4's
instrumentation was built and installed *after* that snapshot, so it is a
different binary (`863e55d6…`) and inherits none of the bridge's authority.

That matters because §4's patch is not purely additive.  Alongside the guarded
log statements it refactors the live `flag_reduce` condition into
`const bool cont_hit = (...); if (cont_hit) flag_reduce = true;`.  That should be
byte-identical by inspection — and "should be by inspection" is not this
codebase's bar.

So the bridge was **run a second time** on the instrumented binary at HEAD
(`work-*-d145bridge2`, `863e55d6…` = current `local/lib`, knob off, same 13
events):

| | mcp1k (1) | mcp2k (10) | nuecc48 (2) |
|---|---|---|---|
| `tsv` / `root` / `zip` / `tar` / `calib` | SAME | SAME | SAME |

13/13 `rc = 0`, and **0 log files contain a `kine_cont:` line**, which is the
knob-off proof for the instrumentation itself.  `8c14185a`'s inertness claim
therefore rests on a byte gate over 13 events, not on one event plus a reading
of the diff.

---

## 3 Item 4 — the pointing test priced on 3067 events

`7c4bf46a` shipped the fix behind `kine_near_pointing_impact` with the bar
written into its own commit message: *"it needs its own 3067-event arm and its
own negative control before it earns a default."*  This is that arm.

`work-*-d145np`, all four samples, **3067/3067 `rc = 0`**, 35 minutes wall on
the `d145_libpin` pin, armed at **20 cm / 30°** via the existing
`docs/pr/pr144-nearpoint.tla`.  Negative control `work-*-d144fixprod`, licensed
by §2's epoch bridge.

**Proof the arms are what they claim** (not assumed — sampled): 200 of 200
compiled configs from the armed arm carry `kine_near_pointing_impact : 20` **and**
`kine_near_pointing_miss_deg : 30`; 50 of 50 control configs carry neither key.

### 3.1 The refusal census — the guard does not trim this pool, it empties it

`pr145_pointing_census.py` over every `wct_pr_evt<ID>.log`
(`docs/pr/pr145-pointing-census.tsv`):

| | |
|---|---|
| events in the arm | 3067 |
| events reaching the test at all | **5** (0.16 %) |
| candidates examined | **5** |
| → COUNT (admitted) | **0** |
| → SKIP (refused) | **5** |
| refused KE | **1025.0 MeV** |

**Cross-checked against the control arm, because a census this small is exactly
the shape a broken parser produces.** The control's own
`kine_count_near_cross_cluster: COUNT` lines number **5** across the same 3067
events, on the same five events, and the armed arm has **0**.  So the pool
really is this rare, and the pointing test refuses **100 %** of what it admits.

That is a stronger statement than "the guard is narrow".  On SBND, at 20 cm /
30°, `kine_near_pointing_impact` does not tune `kine_count_near_cross_cluster`
— **it switches it off**.  Anyone reading this as a threshold to tune should
know there is nothing left on the other side of it to keep.

### 3.2 The gate — 5 events move, and they are the 5 the census named

`pr143_compare_arms.py` against the control, member-content hashes (M2):

| | ncpi0 (19) | nuecc48 (48) | mcp1k (1000) | mcp2k (2000) |
|---|---|---|---|---|
| `nusel-evt*.tsv` | SAME | SAME | SAME | SAME |
| `mabc-pr.zip` | SAME | SAME | SAME | SAME |
| `pctree-*.tar.gz` | SAME | SAME | SAME | SAME |
| `tracking-pr.root` | SAME | SAME | **DIFF 2** | **DIFF 3** |
| `calib-*.json` | SAME | SAME | **DIFF 2** | **DIFF 3** |
| **`nusel-table.tsv`** | **SAME** | **SAME** | **SAME** | **SAME** |
| **`nusel-events.tsv`** | **SAME** | **SAME** | **SAME** | **SAME** |

    mcp1k  DIFF: 350935 395610
    mcp2k  DIFF: 101828 392009 393505

**Exactly the five the census named, and no sixth.** Nothing to explain away.

**Zero selection-label churn** on all four samples — the tagger/BDT selection is
untouched; only the kinematics move.  And only `root` + `calib` move: the
display and imaging products are byte-identical, so nothing downstream of the
picture changes.

### 3.3 What it costs, per event

| sample | event | `Enu` off | `Enu` on | ΔEnu | refused KE | `n_excluded` |
|---|---|---|---|---|---|---|
| mcp1k | 350935 | 1001.4 | 752.0 | **−249.4** | 146.9 | 3 → 4 |
| mcp1k | 395610 | 1013.5 | 761.0 | **−252.5** | 143.7 | 5 → 6 |
| mcp2k | 101828 | 1571.7 | 1190.7 | **−381.0** | 275.3 | 0 → 1 |
| mcp2k | 392009 | 1391.0 | 1003.9 | **−387.1** | 281.4 | 7 → 8 |
| mcp2k | 393505 | 858.2 | 574.8 | **−283.4** | 177.8 | 4 → 5 |
| | **total** | | | **−1553.3** | **1025.1** | |

Each ΔEnu is **larger** than the refused kinetic energy by about one muon rest
mass — exactly 105.7 MeV on 101828, 392009 and 393505, and 102.5 / 108.8 on the
other two — because refusing the segment also drops the rest term
`push_segment_kine` would have charged it.  And `kine_n_excluded` rises by
**exactly 1** on every one of the five: the refused segment is not lost, it is
moved into the excluded pool, which is the correct bookkeeping.

### 3.4 The sentinels — and 393505 is the only live one for this feature

`pr127_sentinels.py`, both arms, against doc 144 §16's baseline:

| arm | result |
|---|---|
| control `work-*-d144fixprod` | **19 PASS, 0 FAIL, 4 OPEN, 7 INERT** |
| armed `work-*-d145np` | **20 PASS, 0 FAIL, 3 OPEN, 7 INERT** |

**No new FAIL.**  The one moved sentinel is 393505, from OPEN to PASS, and it is
causal:

    knob off    [XX] Enu=858.2 want [540, 600]
    knob armed  [ok] Enu=574.8 want [540, 600]

That matters more than one row suggests: `pr127_sentinels.py`'s own
`INERT_AT_D144` block records that the other two pr/129 sentinels (94392,
171572) are *"on/off byte-identical in BOTH frames — never discriminated"*.  So
**393505 is the only event in the registry that can catch the pr/129 pointing
feature dying**, and until this arm it was waived.

The clause that was *not* passing was `pf_contains "mu-  268"`, and it is a
stale literal, not a physics failure: the node reads **`mu-  267 MeV`** — one MeV
of ordinary drift — and it reads **identically on both arms**, so it never
discriminated this knob at all.  It only asserts the owner's *"OK to be in PR"*,
that the muon is not deleted from the PF tree.  Re-baselined to `mu-  267` with
both sides measured at the d145 pin (doc 91 §12 discipline), and the file now
records that `pf_contains` takes a raw substring and therefore — unlike
`pf_node_ge`/`pf_node_lt` — does **not** tolerate drift, so it will need
re-baselining whenever the energy scale moves.

### 3.5 Verdict on item 4 — and what is NOT being claimed

The fix does what `7c4bf46a` predicted, at population scale, for free:

- 3067/3067 `rc = 0`, cost unchanged;
- **0 selection-label changes**; only 5 events move at all, and they are named;
- the only live pr/129 sentinel goes green, causally;
- 1553.3 MeV of `Enu` removed, of which 1025.1 MeV is refused kinetic energy.

**This does not establish that the five refusals are right.** The arm measures
**exposure**, not correctness: it says how much energy the guard takes and from
where, and truth-level `Enu` is not available at population scale to say whether
taking it was correct.  On **393505** the owner has already adjudicated cluster
15 a cosmic, so that one refusal is known-good.  The other four —
**392009 (281.4 MeV), 101828 (275.3), 395610 (146.9), 350935 (143.7)** — have
never been looked at.  Note their `miss_deg`: 101828 at 113.6°, 395610 at
103.8°, 350935 at 90.8° are all pointing *away* from the vertex, which is the
signature the test was built for; **392009 at 12.5° with a 54.3 cm impact is the
one that fails on impact alone** and is the likeliest false refusal of the five.

### 3.6 The working point: only `impact` binds, and by a wide margin

Checking which clause actually refuses each candidate — because the plan for
this round assumed `miss_deg` would matter and it does not:

    mcp1k 350935  impact= 94.49  miss_deg= 90.8   refused by IMPACT (and miss_deg)
    mcp1k 395610  impact=110.22  miss_deg=103.8   refused by IMPACT (and miss_deg)
    mcp2k 101828  impact= 98.47  miss_deg=113.6   refused by IMPACT (and miss_deg)
    mcp2k 392009  impact= 54.30  miss_deg= 12.5   refused by IMPACT ONLY
    mcp2k 393505  impact= 69.10  miss_deg=112.2   refused by IMPACT (and miss_deg)

**Every one of the five fails the impact cut**, and the smallest impact in the
population is **54.30 cm** against a 20 cm threshold.  So:

- `kine_near_pointing_miss_deg` is **inert on SBND at this epoch** — arming at
  20 cm / **90°**, the jsonnet's own armed default, gives the *identical* result,
  and the working-point mismatch this round was written to guard against does
  not exist.  A flip therefore need not carry the 30° value.
- the impact threshold is robust: **any** value in `[0, 54.3)` cm produces
  exactly this outcome, so 20 cm is not a tuned number sitting near a cliff.

**No default is flipped here** (CLAUDE.md §5.1).  The recommendation, with the
numbers above, is that this is a strong candidate for production **after** a
blind scan of the four unadjudicated refusals.

### 3.7 The scan set (uploaded 2026-09-06)

    https://www.phy.bnl.gov/twister/bee/set/c1529fd5-d4f6-42f0-b182-71aa7974cdd6/event/list/

Index and per-event geometry: `docs/pr/pr145-item4-bee.index.txt`.

**ONE set, not an OFF/ON pair, and that is a measurement not a shortcut.** The
display files are **byte-identical between the two arms on all five events**
(member-content hash, path-summary line excluded — the naive whole-listing
`md5sum` reports a false DIFF because that line embeds the archive's own
directory).  Only `root` and `calib` move.  So an order-matched pair would have
shipped two identical pictures and asked the owner to spot a difference that is
not in them.

The question per event is not "which arm is better" but **"is this object a
cosmic or a daughter"** — all five were admitted on `gap_cm = 0.00`, proximity
with no direction test.  Index 2 (393505) is the owner's already-adjudicated
cosmic and is included as calibration, marked as such.

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

### 5.7 What the join actually returned — the ported-label route is dead

`pr145_yz_join.py` carried the 18 labels onto `work-*-d144fixprod`.  It did not
survive the epoch, and the failure is worth more than the success would have
been:

| | |
|---|---|
| labels | 18 |
| matched into the current arm | **14** |
| **object id survived the epoch** | **4 / 14 = 29 %** |
| matches with a residual so large they are plainly a different object | 2 (170098: length 16.9 → 0.6 cm; 176502: 19.5 → 0.5 cm) |
| **confident-EM labels surviving a clean match** | **2** |

**29 % id stability is the number doc 144 §7.2 wanted** and it settles that open
item: a cross-epoch join keyed on object id is wrong more often than it is
right, and the π⁰ census that used one was correctly declared invalid.

With **two** clean confident-EM survivors, a threshold cannot be re-fit from
these labels.  The route the pre-registration named in §5.4 step 2 is therefore
**closed**, and it is closed by measurement rather than by opinion.

### 5.7.1 Why four labels vanished — and it is good news

Three of the four unmatchable objects were owner-labelled **EM**, and in the
current epoch the nearest object at that position **is typed `particle_id = 11`**:

    286681  owner EM   ->  id 69032  pid=11  len 131.5 (was 109.2)
    282979  owner EM   ->  id 45036  pid=11  len  22.7 (was  27.9)
    235435  owner EM   ->  (no clean counterpart; 2 showers left on the event)
    392901  owner TRACK->  no mu-typed shower remains at all

**The reconstruction has already re-typed several of the objects the owner
called mis-typed.**  That is item 5's defect being repaired by intervening work,
not by anything in this round — and it is also why `235435`, declared in §5.5 as
the training/blind contamination, is moot: the object is gone.

### 5.8 But the defect has not shrunk, and the population sets the threshold

Individual objects churn; the **population does not**:

| | pr141 epoch (`work-pr140r2-off-*`) | current (`work-*-d144fixprod`) |
|---|---|---|
| events read | 239 | 1435 |
| μ-typed showers > 50 MeV | 35 | **222** |
| rate per event | 0.1464 | **0.1547** |

Ratio **1.06** — unchanged inside any reasonable error.  So doc 141's closing
finding stands: this is still the open front, worth **73 059 MeV** of
`kine_charge` across 222 objects.

And the unlabelled population supplies what the labels could not — a threshold:

```
q/range      count      (219 usable objects; 3 degenerate excluded -- §5.8.1)
   <0.5      7
0.5-0.6     12
0.6-0.7     48
0.7-0.8    106   <- the track peak
0.8-0.9     23
0.9-1.0      3
1.0-1.2      0   <- EMPTY
1.2-1.5      5
1.5-2.0      4
2.0-3.0      9   <- the second population
3.0-5.0      1
    >5       1
```

**The distribution is bimodal with an empty bin at 1.0–1.2.** The plateau is
exact — thresholds of 1.0, 1.1 and 1.2 all select the same **20 objects**, and
only at 1.3 does the count move (to 17).  So the choice is not a fit; it is the
low edge of a gap, and it uses **no labels at all**, which is precisely what
makes it immune to the post-hoc trap §5.4 was guarding against.  The predictor
for the next round is therefore

> **`kine_charge / kine_range > 1.0` ⇒ EM**, 20 of 219 usable objects (9.1 %),
> **2600 MeV** of `Enu` at stake if every one of them is really EM.

### 5.8.1 Three objects the ratio selects but the mechanism does not

The ratio is only a measurement while its denominator is one.  Three of the 222
have a `kine_range` small enough that `q/range` is a **division artifact**:

    mcp2k 179048 obj 17013   q=560.1  kine_range=0.0001 MeV  len=364.9 cm
    mcp2k 294174 obj 16030   q=327.9  kine_range=3.81   MeV  len=148.9 cm
    ncpi0 259542 obj 83055   q=141.1  kine_range=5.71   MeV  len=41.1  cm

A 364.9 cm object cannot have a range energy of 10⁻⁴ MeV; that is a failed range
computation, and the ratio turns it into 5.6 × 10⁶.  Left unguarded it **topped
the blind sheet** — the owner would have scanned the predictor's loudest
selection on an object the predictor never really selected.  `pr145_pidset.py`
now floors `kine_range` at 10 MeV and classes these **DEGENERATE**, in neither
class.  It is the same failure family as §4.6's zero-KE nodes, seen from the
other side.

The confident pr141 labels of §5.3 are **unaffected** — their smallest
`kine_range` is 19.7 MeV, above the floor — so that table stands as printed.

Two honest qualifications.  This shape is **corroboration, not validation**: a
valley shows the variable has structure, it does not show which side is EM, and
only labels can. And 9.1 % is well below doc 141's "≥ 29 % of μ-typed objects
are EM showers", so either this predictor is conservative or that estimate was
high — unresolved, and worth stating rather than reconciling by assertion.

### 5.9 What round 1 delivered, and what it did not

**It did not deliver the promised blind precision.**  The measurement that would
have produced it — re-fit the threshold on the ported labels, then score a
disjoint set — died at §5.7 when only 2 confident-EM labels survived the join.
Reporting that plainly is the point of having pre-registered.

What it did deliver:

- the **(y,z)/invariant join**, and with it doc 144 §7.2's number: **29 %** id
  stability across an epoch;
- the finding that the reconstruction has **already re-typed** three of the four
  labelled EM objects that vanished;
- the population measurement showing the defect is **the same size as at doc
  141** (rate ratio 1.06, 222 objects, 73 059 MeV);
- a **label-free threshold** from the population's own empty bin, with the
  stability argument for it, and a degeneracy floor that keeps three
  division artifacts out of the owner's scan (§5.8.1);
- `docs/pr/pr145-pidscan-manifest.tsv` — a **blind** 20-object sheet (14
  predicted-EM by highest energy at stake + 6 predicted-TRACK controls) with the
  predicted class and the discriminant deliberately absent.

**Named next step:** the sheet needs the owner's verdicts.  That is the human
step round 1 cannot do for itself, and it is what turns the corroborated
mechanism into a measured precision.


---

*Sections 3 (Round A) and 4 (Round B) are filled in as their arms land.*

---

## 6 Where this leaves items 3, 4 and 5

| item | state after this round | what it needs next |
|---|---|---|
| **4** | **Priced.** 3067/3067 `rc=0`, 0 selection churn, 5 events move and they are named, the only live pr/129 sentinel goes green causally, −1553.3 MeV of `Enu`. The guard **empties** the pool rather than trimming it, and only `impact` binds. | A **blind scan of the four unadjudicated refusals** — 392009, 101828, 395610, 350935. Then the flip is a §5.1 decision for the owner. |
| **3b** | **Answered.** The escape is named: the rest term is charged at four admission sites and reduced at one. 4 of 6 payers are that; 1 is an untyped parent; **1 is not a defect at all**. Two of doc 144 §14.2.1's statements are corrected. | A **cross-admission-path continuation test**, its own round, with the 9 `reduced_ok` and 5 `single` events as negative controls. |
| **3a + 5** | **Round 1 reported honestly as a miss.** The ported-label route died — 29 % id stability, only 2 confident-EM survivors. But the population is unchanged in size (rate ratio 1.06), and its own empty 1.0–1.2 bin gives a label-free threshold. | The **blind 20-object sheet** needs the owner's verdicts. That is the human step; it converts a corroborated mechanism into a measured precision. |

**Nothing in this round changes production.** Two default-OFF knobs exist
(`kine_near_pointing_impact` from `7c4bf46a`, `kine_continuation_debug` from
`8c14185a`), both proven byte-identical when off, and neither is flipped.

### 6.1 What this round did not do

- **No truth-level check.** Every correctness statement above rests on the
  owner's adjudications, not on MC truth, which is not available at population
  scale in this chain.
- **No PDVD / PDHD / uBooNE gate for `8c14185a`.** `NeutrinoKinematics` binds on
  all of them.  The knob-off byte-identity is proven on SBND (13 events, §2.1)
  and the C++ default is `false`, so those chains cannot reach the new code —
  but the standing bar wants the gate run on each detector's own manifest, and
  that is **owed**.
- **No blind scan.** Both §3.5's four refusals and §5.9's 20-object sheet are
  prepared and unscanned; Bee upload is ask-first.
