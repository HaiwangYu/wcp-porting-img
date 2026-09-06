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
blind scan of the four unadjudicated refusals.  **§3.8 is that scan, and it
changed the answer: do not ship 20/30.**

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

### 3.8 The scan came back — and it inverts §3.5's recommendation

The owner's verdicts, 2026-09-06, verbatim:

> *"the only event that the energy should be included is the first event 392009,
> this is supposed to be one long muon, but was broken to pieces due to signal
> processing failure and cathode plane. But the energy should be counted. The
> other four are all overclustering, so the energy should not be counted."*

So **4 of 5 refusals are right and one is wrong** — and the wrong one is the
event §3.5 named in advance as the likeliest false refusal.

**The two clauses separate very differently:**

| | keep (392009) | refuse (the other four) | margin |
|---|---|---|---|
| `impact` | 54.30 cm | 69.10 … 110.22 cm | **14.80 cm** |
| `miss_deg` | **12.5°** | 90.8 … 113.6° | **78.3°** |

**The 20 cm impact cut is on the wrong side of its own gap.** And the clause
§3.6 reported as *inert* — `miss_deg` — is the one that actually discriminates,
by a factor of five more margin.  It read as inert only because the impact cut
refused every candidate before `miss_deg` was ever consulted.

**The owner's mechanism explains exactly why**, and it is the part worth keeping:
a long muon broken up by signal-processing failure and the cathode plane has its
fragments **displaced** — so the piece's line misses the vertex by 54 cm — but
their **direction is preserved**, so it still points back at the vertex within
12.5°.  Over-clustering attaches an unrelated cosmic, which has neither.
**Displacement survives fragmentation; direction does not survive
over-clustering.**  That is why direction is the robust discriminator and
proximity-to-vertex is not.

### 3.8.1 The corrected operating point

Scored on the census (which carries every candidate the test examines, so any
threshold pair can be evaluated with no new arm):

    impact <= 20    miss <= 30    4/5   WRONG: 392009      <- what was priced
    impact <= 20    miss <= 90    4/5   WRONG: 392009
    impact <= 60    miss <= 30    5/5
    impact <= 200   miss <= 30    5/5   <- recommended
    impact <= inf   miss <= 30    5/5

Recommended: **`kine_near_pointing_impact = 200`, `kine_near_pointing_miss_deg = 30`.**
The impact value only has to be > 0 to arm the test; at 200 cm it places no
effective bound on this population and lets the 78°-margin clause decide.
`impact = 60` also scores 5/5 but sits just 5.7 cm above 392009's 54.30 — brittle
where the direction clause is not.

Effect against today's production:

| event | verdict | Enu prod | Enu new | Δ |
|---|---|---|---|---|
| 392009 | **keep** | 1391.0 | 1391.0 | **0.0** |
| 101828 | refuse | 1571.7 | 1190.7 | −381.0 |
| 393505 | refuse | 858.2 | 574.8 | −283.4 |
| 395610 | refuse | 1013.5 | 761.0 | −252.5 |
| 350935 | refuse | 1001.4 | 752.0 | −249.4 |
| | | | **total** | **−1166.3 MeV** |

against the 20/30 point's −1553.3 MeV, of which −387.1 was the muon that must
be kept.

**What this rests on, stated plainly: n = 5, with exactly one "keep".** The
threshold was chosen *after* seeing the labels, so 30° is **fitted, not
predicted** — the honest status is the same one §5.4 insists on for item 5.  What
is *not* fitted is the mechanism: fragmentation preserves direction and destroys
proximity, and that is a physical statement that would have predicted this
result.  A second keep-class event would be worth more than any amount of
re-tuning on these five.

### 3.8.2 The owner's follow-up: why segment 58014 is missing entirely

He asked why a *second* piece of the same muon — cluster 58 segment **58014**,
23.67 cm, `pdg = 211` — is absent from the particle flow.  The answer is that
**58014 appears in ZERO log lines in the entire event**: not declined, not
scanned, not excluded by name.  Two independent gates drop it, and **neither
asks whether it belongs to the muon**.

**The chain, from the calib dump's shared vertex ids:**

    58014 (23.67 cm, pi)  --[v58019]--  58015 (114.13 cm, mu)  --[v58018]--  58013 (13.82 cm, EM shower)
                                    also at v58019: 58016 (4.55 cm)

That is ~156 cm of one object, in four pieces — exactly the shattering the owner
attributes to signal-processing failure and the cathode plane.  **Only 58015 has
any route into the PF tree or into `Enu`.**

**Gate 1 — the PF tree is keyed on a guard's history, not on the object.**
The only path that renders these displaced cluster-58 objects is
`pf_orphan_guard_freed` (`MultiAlgBlobClustering.cxx:2576`), and its first test is

```cpp
if (!seg->flags_any(PR::SegmentFlags::kPass4GuardFreed)) continue;
```

so a segment is eligible **only if the pass-4 proximity guard previously
declined it**.  This event contains exactly one such decline:

    pr130 pass4_prox_guard: decline seg=58015 pdg=13 len=114.1cm

58015 was declined, so it is flagged, so it is emitted as the
`nu -> n -> mu-  281 MeV` pseudo-node the PF tree shows.  58014 was **never
declined by that guard**, so it never carries the flag, so the emitter never
sees it.  Nothing about 58014's length, PID or position is consulted — it is
invisible because of what happened to a *different* segment.

**Gate 2 — the energy pool has a 30 cm floor.** Independently, the
near-cross-cluster pool requires `m_kine_near_min_len{30*units::cm}`
(`NeutrinoPatternBase.h:2330`) and 58014 is **23.67 cm**.  So even with a PF node
it would not be counted.

**Consequence for §3.8.1, and it is not small.** The corrected operating point
recovers 58015's 281.4 MeV, but it does **not** recover 58014, 58013 or 58016.
Of the four pieces the PF sees one, and `kine_track_ctx` scanned only idx 1, 4,
13 and 15 — never 14.  58013's kinetic energy is on the record at **33.2 MeV**;
58014's is in no output at all, because nothing ever measured it.  The 7 excluded
objects on this event total 139.6 MeV, all outside the main cluster.

So the pointing-threshold question was the wrong scale of question for this
event: **tuning the guard decides whether one of four fragments is counted.**
The energy that is structurally unreachable is larger, and no threshold in this
component recovers it.

### 3.8.3 The upstream defect this exposes

392009's muon is **broken into pieces by signal-processing failure and the
cathode plane**.  The near-cross-cluster pool re-admitting its far half is a
*patch* for that fragmentation, not a fix — and the pointing test is then a
patch on the patch.  The real defect is upstream, in SP and in cathode-crossing
reconstruction, and it is the same family as doc 144 §14's split muon
(§4 here) and doc 84's cathode bridge.  **Reported, not fixed**; it is out of
scope for this round and belongs with the cathode-crossing work.

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
| **4** | **Priced and scanned.** 3067/3067 `rc=0`, 0 selection churn, 5 events move. The owner scanned all five: **4 refusals right, 1 wrong (392009)**. The priced 20/30 point is therefore **not shippable** — but `miss_deg` separates the same five by 78.3° where `impact` manages 14.8 cm, so **impact = 200 / miss_deg = 30** scores 5/5 for −1166.3 MeV (§3.8). | Owner's decision on the corrected operating point. It is fitted on n=5 with one keep, so a **second keep-class event** is worth more than further tuning. |
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
- **One blind scan is still owed.** §3.5's four refusals *were* scanned —
  §3.8 carries the owner's verdicts, and they inverted the recommendation.
  §5.9's 20-object PID sheet is prepared and **unscanned**; that is the human
  step item 5 is waiting on.

## 7 The pre-fix ("before") Bee sets

Owner ask, 2026-09-06: *"for events in [the doc-144 post-fix set], and events in
[the item-4 set], can you first provide me the bee links for the master branch
production, this is before the three fix that we put in to the apply point
cloud."*

Two new order-matched sets, uploaded 2026-09-06:

| | events | BEFORE (new) | AFTER (already scanned) |
|---|---|---|---|
| doc 144 post-fix set | 13 | [`6bb7bf54`](https://www.phy.bnl.gov/twister/bee/set/6bb7bf54-1af3-4bcb-887f-81f6a378c3d6/event/list/) | [`42a635f6`](https://www.phy.bnl.gov/twister/bee/set/42a635f6-475b-4a17-9e5d-913fdb355bab/event/list/) |
| item-4 refusal set | 5 | [`41b6421d`](https://www.phy.bnl.gov/twister/bee/set/41b6421d-7995-4c87-985d-21b7d9744d35/event/list/) | [`c1529fd5`](https://www.phy.bnl.gov/twister/bee/set/c1529fd5-d4f6-42f0-b182-71aa7974cdd6/event/list/) |

Indices are 1:1 with the AFTER sets: idx N here is idx N there.  Sidecars:
`docs/pr/pr145-before-d144fixed.index.txt`, `docs/pr/pr145-before-item4.index.txt`.

### 7.1 What "before" is, precisely — and what it is not

Both sets are built from **`work-{mcp1k,mcp2k,nuecc48}-d144off`**: SBND PR
production as it stood on 2026-09-05, toolkit **70c23cc7**, with both doc-144
knobs at their then-default `false`.  Its compiled config is byte-identical to
pre-flip production (§0 of doc 144, T0 md5 `3bfd2a80d0201d22e9a1b5db37c774eb`).

It is **not literally `origin/master`**, which is ~78 commits back (merge-base
`e88f364d`).  Naming the gap rather than hiding it:

- **in the driver**, the SBND PR job's `master`→`HEAD` diff carries exactly
  **three** production flips — `flash_by_gid` (`94590129`), `excl_t0_frame` and
  `kine_dqdx_skip_zero_dx` (both `4c84855c`).  That is a claim about *config
  flips only*; unconditional code changes in the same window are the next two
  bullets.  `flash_by_gid` writes diagnostic tree columns only; its own comment
  records the PR archives and nusel verdict TSVs byte-identical across it (308
  events).  So on the **pictures**, the OFF arm is the master-branch state.
- doc pr/143's `break_segment` vertex stamp (`70c23cc7`) **is** in these
  pictures — it is the pin the arms were built on.
- the peer's `ef995685` (wrapped-channel lookup defaults ON, 2026-09-06 10:08)
  is **not** — it landed after the pin, and is in the AFTER sets.  Wrapped
  channels do not reach SBND.
- the 494297 `remove_vertex` crash guard (`25baa8aa`) is not needed here: that
  event crashed only with `excl_t0_frame` **on**, so it reconstructs cleanly in
  the OFF arm and idx 12 of `6bb7bf54` is its genuine "before" picture — the
  first one that has ever existed for it.

If a literally-`origin/master` build is wanted it is a separate isolated-prefix
build; it must not `wcbuild` into the shared `local/lib`.

### 7.2 Construction and the checks that back the two links

```bash
cd wcp-porting-img/sbnd/sbnd_xin
python3 scripts/bee/make_pr_bee.py \
  -q work-mcp2k-d97fv -q work-mcp1k-d97fv -q work-nuecc48-d97fv \
  -p work-mcp2k-d144off -p work-mcp1k-d144off -p work-nuecc48-d144off \
  -o d145_setA_before.zip \
  179369 47212 175896 393505 94392 171572 177536 347890 137238 111412 98844 100135 494297
python3 scripts/bee/make_pr_bee.py \
  -q work-mcp2k-d97fv -q work-mcp1k-d97fv \
  -p work-mcp2k-d144off -p work-mcp1k-d144off \
  -o d145_setB_before.zip \
  392009 101828 393505 395610 350935
BROWSER=echo ./upload-to-bee.sh d145_setA_before.zip   # -> 6bb7bf54-...
BROWSER=echo ./upload-to-bee.sh d145_setB_before.zip   # -> 41b6421d-...
```

Three checks, because an index shift here would be silent and would misalign
every comparison the owner makes:

1. **No event can be dropped.** `make_pr_bee.py` refuses an event with no
   selected neutrino candidate, and a refusal shifts every later index with no
   error.  All 17 distinct events were checked first for
   `TaggerCheckNeutrino: selected main cluster` in their OFF-arm logs — present
   on every one (179369 twice, the rest once).
2. **Presence proved from the set's own `event/list/` page**, not from layer
   URLs (a Bee layer URL 200s when the layer is missing): 13 events, indices
   0–12; 5 events, indices 0–4.
3. **The shared event agrees across the two sets.** 393505 is idx 3 of the
   13-event set and idx 2 of the 5-event set; all **9 of 9** layer members are
   byte-identical between them (member-content md5, the bee-index basename
   prefix excluded).

The Q/L layers (`img-global`, `clustering-global`, `op`, `channel-deadarea-*`)
come from the **same** `work-<s>-d97fv` imaging arm as the AFTER sets, so every
visible difference between a before/after pair is attributable to the PR stage
alone.

## 8 Item 4 SHIPPED — `kine_near_pointing_impact` 200 / `miss_deg` 30, SBND PRODUCTION 2026-09-06

**Status: FLIPPED.**  Owner decision, 2026-09-06, verbatim:

> *"Let's first flip `kine_near_pointing_impact = 200` … `kine_near_pointing_miss_deg = 30` for SBND production following the earlier suggestions."*

That is the authorisation of record for a CLAUDE.md §5.1 default flip: production
output now moves unconditionally on four events.  §3.8.1 is the recommendation
this executes; **the shipped point is 200/30, not the 20/30 §3–3.6 priced**, and
the difference is not cosmetic — at 20 cm the impact clause also refused 392009,
the one real daughter in the population.

### 8.1 Why the gate is 35 events and not 3067

A full 3067-event arm was launched and then **stopped on purpose** when the owner
asked whether it was needed.  It is not, and the reason is structural rather
than statistical:

`near_cands`, the pool the pointing test judges, is filled at
`NeutrinoKinematics.cxx:892-915` — **before** the admission loop — from
`kine_near_gap`, `kine_near_end_tol`, `kine_near_kink_deg` and
`kine_near_min_len`.  **No pointing threshold is read there.**  The pointing test
lives inside the loop that follows (`:919-947`) and only decides admission.  So
no threshold can enlarge the pool, and the already-complete 3067-event armed arm
`work-*-d145np` enumerated that pool over the whole population: **5 candidates in
5 events**.  Every other event runs identical code on identical data and cannot
move.

That is a stronger statement than a population arm would have made — an arm shows
that nothing else moved *this time*; the pool argument shows nothing else *can*.
The partial arm is left on disk carrying an `ABORTED.txt` in each sample dir so
it can never be mistaken for a complete one (M13: nothing deleted).

The gate manifest is therefore **the 5 candidate events ∪ the pr127 sentinel
registry** = 35 events across all four samples.

### 8.2 The config proofs

Both compiled from one tree state; numeric TLAs throughout, because `-A` passes a
**string** and `"0" != 0` in jsonnet defeats the key-suppression idiom — an `-A`
proof silently emits the keys it is trying to prove absent.

    T0  flipped driver + --tla-code impact=0,miss_deg=90  ==  pre-flip default
        cmp rc 0, md5 15cfad8cda4ccf0f895aa86c8fb1f384
    T1  flipped driver's DEFAULT  ==  pre-flip driver + --tla-code impact=200,miss_deg=30
        cmp rc 0, md5 881862ad794f1d66188616b340686642

M6 compiled-config proof: pre-flip production carries **neither** key (839 keys);
the flipped default carries `kine_near_pointing_impact: 200` and
`kine_near_pointing_miss_deg: 30` on node 21, `TaggerCheckNeutrino:pr` — exactly
+2 keys.  And T1″, the proof a forced-TLA arm cannot give: the config
`work-mcp2k-d145prod/pr_evt392009/.wct-cfg-evt392009.json` that the **no-TLA** arm
actually ran carries `{'kine_near_pointing_impact': 200,
'kine_near_pointing_miss_deg': 30}`.

**Binder count = 1.**  `kine_near_pointing_*` appears in exactly one config file
in the whole tree — the SBND PR driver.  Unlike the doc-99 flash flip (four files,
because the LArSoft chain calls `clus_maker.pr()` without the keys) there is no
second entry point to keep in sync.

### 8.3 The arm and the gate

`scripts/pr145_prodarm.sh` → `work-*-d145prod`, **no `PR_EXTRA_TLA` at all**, on
the same pin `d145_libpin` (toolkit `7c4bf46a`, `libWireCellClus.so`
`7f4a718d9795f515e032d705f492e58b`) the §3 census ran on, so `work-*-d144fixprod`
stays licensed as the negative control by §2's epoch bridge.  35/35 rc=0, 76 s
wall.

Gate, `pr143_compare_arms.py` per sample against `work-*-d144fixprod`
(member-content hashes, M2):

| sample | events | tsv | root | zip | tar | calib |
|---|---|---|---|---|---|---|
| ncpi0 | 1 | SAME | SAME | SAME | SAME | SAME |
| nuecc48 | 2 | SAME | SAME | SAME | SAME | SAME |
| mcp1k | 9 | SAME | **DIFF 350935, 395610** | SAME | SAME | **DIFF 350935, 395610** |
| mcp2k | 23 | SAME | **DIFF 101828, 393505** | SAME | SAME | **DIFF 101828, 393505** |

**Exactly four events move, and they are the four the owner called cosmics.**
Two facts in that table are worth reading twice:

- **Every `zip` and `tar` is SAME, on all 35 events.**  The refused objects stay
  in the PF picture and the Bee display; only the kine accounting moves.  That is
  what pr/123 r2 requires and it is why the item-4 scan set (§3.7) was one set
  rather than an OFF/ON pair.
- **392009 is SAME on every class.**  It was predicted as a *check*, not claimed:
  at 200/30 the test examines it and votes COUNT, the same outcome as today's
  no-test path, so if any artefact had moved the test would not be
  decision-neutral on an admitted candidate and that would have been a finding.
  It is neutral.

**Selection-label churn: 0.**  `nusel-table.tsv` and `nusel-events.tsv` compare
DIFF at file level, but that is an artefact of comparing a 1/2/9/23-event arm's
table against a 3067-event one — the tables are column-aligned and the `event`
column is one space narrower when every id has five digits.  Row-by-row on the 35
common events, whitespace-normalised: **0 differing rows in either file**,
including `event_label`, `label`, `tgm`, `stm`, `fc` and `stmfit`.

### 8.4 What it costs

Read off the calib dumps of both arms:

| event | verdict | Enu prod | Enu new | Δ |
|---|---|---|---|---|
| 392009 | **COUNT** (keep) | 1391.0 | 1391.0 | **0.0** |
| 101828 | SKIP | 1571.7 | 1190.7 | −381.0 |
| 393505 | SKIP | 858.2 | 574.8 | −283.4 |
| 395610 | SKIP | 1013.5 | 761.0 | −252.5 |
| 350935 | SKIP | 1001.4 | 752.0 | −249.4 |
| | | | **total** | **−1166.3 MeV** |

Exactly §3.8.1's prediction, to the decimal.  Census on the shipped arm
(`docs/pr/pr145-census-prod.tsv`): 5 candidates examined, 1 COUNT (281.4 MeV
admitted), 4 SKIP (743.6 MeV refused), no impact anywhere near the 200 cm bound
(max 110.22 cm).

### 8.5 Sentinels — and the waiver that came off

`pr127_sentinels.py` against `work-*-d145prod`: **20 PASS, 0 FAIL, 3 OPEN, 7
INERT**, against §3.4's 19 PASS / 0 FAIL / 4 OPEN / 7 INERT baseline.  The event
that moved is 393505:

    PASS 393505   pr/129   cosmic cluster 15 no longer counted into Enu
            [ok] Enu=574.8 want [540, 600]
            [ok] pf_contains 'mu-  267' (14 PF nodes)

Its `KNOWN_OPEN_D144` waiver is **lifted** — the defect it tracked is fixed in
production, and it was measured fixed on an arm that forced nothing.  The comment
replacing it records the one thing a future round must not lose: **this is the
suite's only live assertion on the entire pr/129 feature.**  The other two pr/129
sentinels (94392, 171572) are INERT — the knob is byte-identical on/off for them
in both frames, so they have never discriminated it.  If 393505 goes red, read it
as the pointing test dying, not as drift.

The three remaining OPEN entries (137238, 177536, 347890) are items 3a and 5 and
are untouched by this flip, as expected.

`./build/clus/wcdoctest-clus` after a rebuild: **328 cases / 23096 assertions, 0
failed**.  The two `CHECK_KNOB_NUM` entries still pin the **C++** defaults 0.0 and
90.0 — that is what keeps pdhd, pdvd and the uBooNE chain on the legacy no-test
path — and they now carry a comment saying out loud that a green run there does
**not** mean SBND runs the test disarmed.

### 8.6 What is being shipped, stated against itself

- **The threshold is fitted, not predicted.**  n = 5 with exactly one keep, and
  30° was chosen after seeing the owner's labels.  §3.8.1 says this and shipping
  does not make it less true.  What is *not* fitted is the mechanism —
  fragmentation preserves direction and destroys proximity — and a second
  keep-class event is worth more than any re-tuning on these five.
- **`miss_deg` has changed role.**  §3.6 measured it **inert** at 20 cm, where
  impact refused all five on its own.  At 200 cm it is the only live clause.  A
  future reader must not carry §3.6's "inert on SBND" forward.
- **It does not recover the energy 392009 actually loses.**  §3.8.2: segment
  58014 and two more pieces of that same muon are unreachable from this
  component at any threshold.  This flip decides whether *one* of four fragments
  is counted.
- **The LArSoft 1-step chain does not get this** (or `excl_t0_frame`, or
  `kine_dqdx_skip_zero_dx`, or `flash_by_gid`).
  `wcp-porting-img/sbnd/pr-operating-point.jsonnet` is a **generated** mirror of
  the driver's TLA defaults, last regenerated at toolkit `14f0aeeb2` with 151
  knobs, and it carries none of them.  Found while counting binders for this
  flip; **reported, not fixed** — it is a resync round of its own, and it is owed.
