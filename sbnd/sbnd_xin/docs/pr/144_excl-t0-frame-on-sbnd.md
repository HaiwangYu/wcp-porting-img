# 144 — The `fit_exclusion` T0 frame patch on SBND: what turning it on actually changes

**Status: FLIPPED — SBND PRODUCTION ON since 2026-09-06.**  Two 3067-event arms
(`d144off` vs `d144on`) were measured, 12 top movers went to two order-matched
Bee sets, and the owner scanned them and ruled the fix better overall.  Both
knobs are now `true` by default in the SBND PR driver.

Owner's question: *"we have identified a T0 bug in the fit_exclusion for the PR
chain during the implementation of PDVD … the reason that we did not see this in
the SBND case is that the SBND's neutrino T0 is close to zero.  Nevertheless,
the fact that we did not have this in SBND was an overlook. … we want to
understand if we have this patch (correctly) turned on, what would be the impact
on SBND chain and results."*

**This is a bug fix, so improvements are the expected outcome** (owner,
2026-09-06).  The null hypothesis is NOT "nothing should change": the exclusion
tournament has been arbitrating SBND's boundary cells in the wrong drift frame
since pr/98 shipped it, and correcting that SHOULD move charge attribution.  So
this doc does not grade movement as risk to be excused — it grades **direction**.
The questions are whether the moves go the right way (does the nue selection gain
on the nue sample without buying background; does the numu point gain on the numu
samples), whether anything is lost that should not be (selection churn, crashes,
NaN), and whether the labelled subsets that carry a right answer improve.

**Scope.** This round began as a measurement, not a flip: SBND's PR chain was
concluded for production, and the two knobs were added to the SBND driver as
**default-OFF** TLAs so the arms would be reproducible from config.  The
measurement ran, the movers went to Bee, and the owner's scan (§8) turned it
into a flip.  Both defaults are now `true` (§2), which is **not** byte-identical
to pre-2026-09-06 production — §4 is the before/after over all 3067 events.

**The owner's decision, verbatim (2026-09-06), after scanning the 12 Bee pairs:**

> "Overall, I feel the fix is better, expect for the index 6 and 7, where the two
> cathode-bridge mions are lost.  idx 3, not sure why the extra muon were added
> to the energy.  idx 8, the hadronic shower made to an EM shower.  Here is what
> I think we should do: 1. turn on this, since it is a bug fix 2. Fix the
> crashing event 3. examine the event idx 6, 7 for the cathode bridge muon to
> improve 4. understand why the energy was added for idx 3, improve, 5. improve
> the hadronic shower reconstruction."

That quote is the authorisation of record for the flip: changing a default so
production output moves unconditionally is CLAUDE.md §5.1 stop-and-ask
territory, and this is the answer to that ask.  The five-item programme it opens
is tracked in §11.

## 0 Repro block

```bash
cd wcp-porting-img/sbnd/sbnd_xin
# pin: /home/xqian/tmp/d144_libpin  libWireCellClus.so b46179b20533eacc9cf7cf85430e7a81
#      (toolkit 70c23cc7 = the doc-143 build; libWireCellRoot.so 4a9efb7f52d22d93f2d9fcc9df394222)
# arms built at toolkit 70c23cc7; the flip is toolkit 4c84855c (cfg only).
# Peer commit ef995685 (2026-09-06 10:08) closed the cfg epoch behind the arms -- sec 3.2.

# A. config proofs (no runs).  T0: knobs off compiles byte-identically to pre-change.
export WIRECELL_PATH=$TK/cfg:$TKDEV/wire-cell-data
PT="pipeline_names=['switch_scope','unmerge_bundle','unmerge_assoc','steiner','fiducialutils','tagger_check_tgm','tagger_check_stm','tagger_check_fc','protect_bundle','steiner_refresh','tagger_check_neutrino','numu_bdt_scorer','nue_bdt_scorer','tracking_visitor','tagger_output','pr_display']"
wcsonnet --tla-code "$PT" -o t0_after.json $TK/cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet
cmp t0_before.json t0_after.json            # rc 0; md5 3bfd2a80d0201d22e9a1b5db37c774eb
wcsonnet --tla-code "$PT" --tla-code excl_t0_frame=true --tla-code kine_dqdx_skip_zero_dx=true -o t1_on.json ...

# A2. the FLIP-epoch proofs (sec 2).  Both copies live in the sbnd cfg dir because
# the driver does `import "clus.jsonnet"` relative to its own directory; compile all
# four from ONE tree state so the peer's ef995685 key is on both sides and cancels.
D=$TK/cfg/pgrapher/experiment/sbnd
cp $D/wct-pr-perevt.jsonnet $D/.d144proof_flip.jsonnet
sed -e 's/^    excl_t0_frame = true,$/    excl_t0_frame = false,/' \
    -e 's/^    kine_dqdx_skip_zero_dx = true,$/    kine_dqdx_skip_zero_dx = false,/' \
    $D/.d144proof_flip.jsonnet > $D/.d144proof_base.jsonnet
wcsonnet --tla-code "$PT" -o P_base_default.json $D/.d144proof_base.jsonnet
wcsonnet --tla-code "$PT" -A excl_t0_frame=true  -A kine_dqdx_skip_zero_dx=true  -o P_base_on.json      $D/.d144proof_base.jsonnet
wcsonnet --tla-code "$PT" -o P_flip_default.json $D/.d144proof_flip.jsonnet
wcsonnet --tla-code "$PT" -A excl_t0_frame=false -A kine_dqdx_skip_zero_dx=false -o P_flip_off.json     $D/.d144proof_flip.jsonnet
cmp P_base_default.json P_flip_off.json     # T0' rc 0, md5 a6ee2d3490dde6b58d74f8fc6bcf46bf, 246 keys
cmp P_base_on.json      P_flip_default.json # T1' rc 0, md5 15cfad8cda4ccf0f895aa86c8fb1f384, 248 keys
rm -f $D/.d144proof_base.jsonnet $D/.d144proof_flip.jsonnet
./build/clus/wcdoctest-clus                 # 323 cases / 23061 assertions, 0 failed

# B. fire proof: doc pdvd/45 sec 5.3's 6 exclusion-active nueCC48 events must MOVE
export LD_LIBRARY_PATH=/home/xqian/tmp/d144_libpin
EV="10550 46363 81597 360535 256587 433451"
PR_EXTRA_STAGES=pr_display PR_JOBS=6 ./run_pr_chain_batch.sh work-nuecc48-d97fv work-d144fire-off data $EV
PR_EXTRA_STAGES=pr_display PR_JOBS=6 PR_EXTRA_TLA=$PWD/docs/pr/pr144-on.tla \
   ./run_pr_chain_batch.sh work-nuecc48-d97fv work-d144fire-on data $EV
python3 scripts/analysis/pr143/pr143_compare_arms.py work-d144fire-off work-d144fire-on

# C. the two population arms (3067 events each, per-event mode, 16 jobs each = the 32 licence)
./scripts/pr144_arms.sh off &   ./scripts/pr144_arms.sh on &

# D. score tables, then the systematic physics A/B
for t in d144off d144on; do mkdir -p products/$t
  for s in nuecc48 ncpi0 mcp1k mcp2k; do
    python3 pr_scores_table.py --root work-$s-$t --sample $s --out products/$t/$s-scores-$t.tsv
  done
done
python3 scripts/pr142_campaign_ab.py --a products/d144off/*.tsv --b products/d144on/*.tsv \
    --label-a d144off --label-b d144on \
    --movers-tsv docs/pr/pr144-movers.tsv --summary-tsv docs/pr/pr144-population.tsv

# E. per-sample byte gate and leaf attribution
for s in nuecc48 ncpi0 mcp1k mcp2k; do
  python3 scripts/analysis/pr143/pr143_compare_arms.py work-$s-d144off work-$s-d144on
done

# F. the doc-144 mover classes and the Bee pick
python3 scripts/pr144_pick_movers.py --movers docs/pr/pr144-movers.tsv \
    --a products/d144off/*.tsv --b products/d144on/*.tsv --n 12 \
    --pick-tsv docs/pr/pr144-beepick.tsv

# G. the crash fix (sec 6.4) and the arms that gate it.  d144_libpin4 = the
#    build carrying clus/src/PRGraph.cxx's degree guard (toolkit 25baa8aa).
LD_LIBRARY_PATH=/home/xqian/tmp/d144_libpin4 PR_EXTRA_STAGES=pr_display PR_JOBS=1 \
  ./run_pr_chain_batch.sh work-mcp2k-d97fv work-mcp2k-d144fix data 494297   # rc=0, guard fires once
PIN=/home/xqian/tmp/d144_libpin4 TAG=d144fix JOBS=12 ./scripts/pr144_arms.sh prod &
PIN=/home/xqian/tmp/d144_libpin4 TAG=d144fix JOBS=12 ./scripts/pr144_arms.sh frameonly &
# then, per sample: pr143_compare_arms.py work-<s>-d144on work-<s>-d144fixprod
#                   pr143_compare_arms.py work-<s>-d144fixprod work-<s>-d144fixframeonly

# H. the sentinel 2x2 (sec 16).  Negative controls at BOTH frames, one binary.
PIN=/home/xqian/tmp/d144_libpin4 JOBS=4 ./scripts/pr144_sentinel_neg.sh
PIN=/home/xqian/tmp/d144_libpin4 JOBS=4 TLA=docs/pr/pr144-legacyframe.tla SUF=leg \
    ./scripts/pr144_sentinel_neg.sh
# the two positive cells, same binary, same 9 events:
#   no TLA                              -> work-s144pos-{mcp2k,mcp1k,nuecc48}
#   PR_EXTRA_TLA=pr144-legacyframe.tla  -> work-s144posleg-{mcp2k,mcp1k,nuecc48}
# prove every control is CAUSAL before believing it -- diff the per-event
# .wct-cfg-evt<N>.json TaggerCheckNeutrino block, pos vs neg; exactly one key
# may differ.  Then:
python3 scripts/analysis/pr143/pr143_compare_arms.py work-s144pos-mcp2k work-s144neg-<knob>
./scripts/pr127_sentinels.py --arms 'work-*-d144fixprod' 'work-s144pos-*'
```

---

## 1 The defect, and why SBND hid it

Cited from doc `pdvd/45`, not re-derived here.

`TrackFitting::update_association` builds each candidate 2-D cell's test point
with the geometric `(time - offset_t)/slope_t` — the **raw, t0 = 0 drift
frame** — and compares it against the per-segment `fit`/`main` point clouds,
which are built from **t0-corrected** fit points.  Every distance in the
exclusion tournament is therefore off by the cluster's own drift offset.

The compute site is `form_map_graph` (`TrackFitting.cxx:4176-4208`), which fills
`m_excl_x_shift` per fit point and `(apa, face)`; the consume site is
`update_association` (`:3242`, `:3294`, `:3348`), which subtracts it from the
raw `x` before the cloud query.  The offset is **measured** — the fit point is
run through the cells' own two conversions and subtracted from itself — because
the first cut, `dirx * t0 * v_drift`, was wrong by a constant 365 cm: the
geometric `offset_t` and `Grouping::convert_3Dpoint_time_ch` do not share a time
origin (doc 45 §4.1).  With the knob off, `m_excl_x_shift` stays empty and the
legacy path is byte-identical.

**Why SBND did not show it.** The beam candidate's t0 is the beam flash time,
0.8–2.0 µs, so the frame offset is `v_drift * t0` = **1.2–3 mm** against a 3 mm
pitch and the 0.3 cm unconditional-keep floor.  Doc 45 §5.3 measured the SBND
own-distance distribution moving from quantiles 0.19/0.32/**0.55**/0.87/1.23 cm
to 0.19/0.33/**0.55**/0.86/1.20, with the floored fraction 23 % → 21 %.  On PDVD
every cosmic candidate carries a flash time of 2–6.5 ms against a −2.5 ms
trigger offset, i.e. 0.6–6 m of drift; there one segment's cloud reached farther
in x than every other and won every cell, and 51 % of all PR trajectory points
on 120 events were dropped as "zero charge".

That is the whole reason this shipped: **no gate on a t0 ≈ 0 detector can see
it.**  pr/98, pr/108 and pr/109 measured the exclusion fit "parity-exact"
through the association stage and it went to SBND production.  uBooNE sits in
between and its qlport chain folds the beam t0 so the two frames coincide.

**But SBND is not exempt, and that is the point of this round.**  SBND runs
`fit_exclusion = true` in production (`cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet:210`,
owner flip 2026-08-20), so the biased tournament is live on every SBND neutrino
candidate today.  A millimetre near a 0.3 cm floor is not nothing: it
re-arbitrates the boundary cells, and pr/109 §9 measured that exclusion strips
30 % of SBND's associated cells and half of the near-vertex ones.  Doc 45 §11
measured the consequence on 67 labelled events — selection rows identical, but
`kine_reco_Enu` moving by more than 50 MeV on 23 of 48 and 15 of 20 candidates —
and deferred the question this doc answers:

> **Recommendation:** an SBND flip needs its own round with truth Enu on the MC
> sets, the pi0 66-set census and the doc 91 sentinel suite; nothing here is
> evidence for or against it.

**So the question here is not whether SBND moves.  It is whether the changed
charge attribution is better.**

---

## 2 The wiring, and its proofs

Two TLAs added to `cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet`, declared
beside `dqdx_fit_keep_all_points` and emitted into the `tcn_knobs` bag with the
key-suppression idiom, copying `pdvd/wct-pr-perevt.jsonnet:3014-3034` and
`:3794-3796` verbatim:

```jsonnet
excl_t0_frame = true,           // false while the arms ran; flipped 2026-09-06
kine_dqdx_skip_zero_dx = true,  //   "
...
[if excl_t0_frame then 'excl_t0_frame']: true,
[if kine_dqdx_skip_zero_dx then 'kine_dqdx_skip_zero_dx']: true,
```

They shipped **default-OFF**, which is how both arms ran (the ON arm forced them
through `PR_EXTRA_TLA=docs/pr/pr144-on.tla`), and were flipped to `true` in the
same file after the owner's scan.  The key-suppression idiom does not change:
with the default `true` both keys are always emitted, and
`-A excl_t0_frame=false` restores the pre-fix key set exactly.

**Why TLAs and not doc 45's runtime-JSON route.**  Doc 45's SBND arms set
`excl_t0_frame` through a copy of the runtime `TrackFitting` JSON
(`SBND_TRACKFIT_JSON`).  That route is a **one-way latch**:

```cpp
// TaggerCheckNeutrino.cxx:2785-2791
if (m_excl_t0_frame) track_fitter->set_parameter("excl_t0_frame", 1.0);
```

There is no `else`, and `configure()` loads the JSON *before* `visit()` runs, so
a value set by the JSON cannot be turned back off by any TLA — deliberately, so
that a diagnostic arm's JSON is not stomped.  The config-bool route is
reversible and byte-identical when off.  It is also the only route for the
second knob at all: `kine_dqdx_skip_zero_dx` is a `TaggerCheckNeutrino` config
key (`:649 → :2566 → NeutrinoPatternBase.h:167`), **not** a `TrackFitting`
parameter, so no JSON can carry it.

Proofs at the **measurement** epoch (knobs added, defaults still `false`):

| proof | result |
|---|---|
| **T0** — knobs off, compiled config before vs after the edit | **byte-identical**, `cmp` rc 0, md5 `3bfd2a80d0201d22e9a1b5db37c774eb` |
| **T1** — knobs on, standalone `wcsonnet` | each key exactly once; `TaggerCheckNeutrino.data` 246 → 248 keys, both `true` |
| **T1a** — the *runtime* config the jobs actually consumed | `work-d144fire-on/pr_evt10550/.wct-cfg-evt10550.json` carries both as `true`; the OFF arm's carries neither key at all |
| scope | only `cfg/pgrapher/experiment/sbnd/` touched; no C++ change this round |

Proofs at the **flip** epoch.  On a flip the obligations invert: byte-identity
when off is no longer the default path, so what has to be shown is that the
legacy path is still reachable *and* that the new default is exactly the thing
that was measured.  All four compiles below are made from **one tree state**
(two copies of the driver differing only in the two literals, both compiled in
place so the sibling `import "clus.jsonnet"` resolves), because a peer's commit
landed between the arms and the flip and moved an unrelated key — see §3.2.

| proof | result |
|---|---|
| **T0′** — flipped driver with `-A excl_t0_frame=false -A kine_dqdx_skip_zero_dx=false` vs the unflipped driver's default | **byte-identical**, `cmp` rc 0, md5 `a6ee2d3490dde6b58d74f8fc6bcf46bf`, 246 keys. The legacy biased-frame path is still reachable and unchanged. |
| **T1′** — flipped driver's **default** vs the unflipped driver with both TLAs `true` | **byte-identical**, `cmp` rc 0, md5 `15cfad8cda4ccf0f895aa86c8fb1f384`, 248 keys. The flip is exactly a default swap; nothing else moved. |
| **T1″** — flipped driver's default vs the config the **ON arm actually ran** (`work-nuecc48-d144on/pr_evt10550/.wct-cfg-evt10550.json`) | `TaggerCheckNeutrino.data` identical on every shared key, both knobs `true`; the arm carries one extra key, `vertex_scoreboard`, which the runner auto-enables for `pr_display` and which is not part of this change. **The committed default is the configuration the 3067-event measurement was made under.** |
| **T2** — one knob each way, `-A excl_t0_frame=true -A kine_dqdx_skip_zero_dx=false` | 247 keys: `excl_t0_frame` present, the guard key suppressed. This is the `d144frameonly` configuration of §4.5. |
| tests | `./build/clus/wcdoctest-clus` **323 cases / 23061 assertions, 0 failed** (`doctest_clus_knob_defaults.cxx:363,365` still pin both **C++** defaults to `false`; only the SBND cfg moved) |
| scope | only `cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet`; binder count 1 — `clus.jsonnet` names `tagger_check_neutrino` but only as the module that receives the job's `tcn_knobs` bag (`:1895 → :2360`), and its own comment at `:1291` records that the stage is not in the clustering job's `pipeline_names` |

`doctest_clus_knob_defaults.cxx:363,365` already pin both C++ defaults to
`false`, so the knob-off path is locked by a test that predates this round.

**Deliberately out of scope: `proj_skip_unmapped_face`.**  The third doc-45 knob
has no config-bool route at all — the only way on is a key in
`sbnd_track_fitting.json`, which is read at *runtime*, so a byte-identical
compiled jsonnet would not prove the fit unchanged.  Bundling it would also make
the OFF→ON delta un-attributable.  It is reported separately in §12, not put in
the ON arm.

---

## 3 The arms, and the proof they are what they claim

Both arms run on **one pin**, `/home/xqian/tmp/d144_libpin`,
`libWireCellClus.so b46179b20533eacc9cf7cf85430e7a81` — the doc-143 build,
toolkit `70c23cc7`.  Per-event mode (`PR_GROUP_SIZE` unset) so `wall_s` and
`maxrss_kb` are per event; `PR_EXTRA_STAGES=pr_display` for the calib dumps.
16 jobs each, 32 concurrent wire-cell processes — exactly the owner's licence.

Reality is **`data` for all four samples**, which is what the production arms
`work-*-d97fvpr2` carry.  Doc 45 block I used `sim` for `ncpi0`; production does
not, so this doc's NCπ⁰ numbers are **not** directly comparable to doc 45 §11's
NCπ⁰ numbers.

### 3.1 Fire proof — the route is live

Doc 45 §5.3 is a known-positive control: with the frame knob on, SBND fits move
on 6/6 of the exclusion-active nueCC48 events.  Run before spending the arm
time, `work-d144fire-off` vs `work-d144fire-on` (10550 46363 81597 360535
256587 433451):

| class | result |
|---|---|
| `tracking-pr.root`, `mabc-pr.zip`, calib dump | **DIFF 6/6** |
| `nusel-evt<ID>.tsv`, `nusel-{table,events}.tsv` | SAME |
| `pctree-pr-evt<ID>.tar.gz` | SAME 6/6 |

Exactly doc 45 §5.3's result.  A SAME here would have meant the route was dead
and the population arms worthless.

### 3.2 Non-comparability to the committed product tables

The OFF arm is **not** `prod0901`/`prod0902`.  It sits on the doc-143 build,
which changed SBND output on 44 of 3000 events for an unrelated reason
(`break_segment`'s clusterless vertex).  No table in this doc quotes a pr/142
number as its "before"; the OFF arm measured here is the only valid baseline for
the ON arm beside it.

**And the epoch closed behind this pair.**  Toolkit `ef995685` (a peer, the same
day, 10:08) flipped the wrapped-channel lookup fixes to C++ default ON and
edited the *shared* `cfg/pgrapher/common/clus.jsonnet`.  SBND is one of its
binders even though no SBND file was touched: the compiled SBND PR config gained
`ImproveCluster_2 "pr" → wrapped_channel_activity: true`, and the pinned d144
binary knows that key.  So a PR arm launched after 10:08 is **not** comparable to
`d144off`/`d144on` on the config either, quite apart from the binary.  Two
consequences, both load-bearing for the rest of this doc:

- every proof in §2's flip table is made from **one tree state**, so the peer's
  key is present on both sides and cancels;
- `work-*-d144frameonly` was launched at 12:05 to attribute the kine guard and
  was **aborted 8 minutes in** for exactly this reason.  Those directories
  (`ncpi0` complete, `nuecc48` partial) are **void — do not read them**.  The
  attribution is re-planned onto the next production arm in §4.5.


### 3.3 How to read the working points as efficiency and background

The four samples carry class labels, so a working-point migration is not just
"a number moved" — it has a sign that means something, and doc pr/142 §3.3 reads
them the same way:

| sample | n | what a **gain** at `numu > 0.9` means | what a **gain** at `nue > …` means |
|---|---:|---|---|
| `nuecc48` | 48 | νμ **background** on a νe sample — bad | νe **efficiency** — good |
| `ncpi0` | 19 | background on an NC sample — bad | NC π⁰ faking νe — bad |
| `mcp1k` | 1000 | νμ **efficiency** on the νμ beam — good | νe background — bad |
| `mcp2k` | 2000 | νμ **efficiency** — good | νe background — bad |

So the shape that says "this fix is an improvement" is: **νe passes up on
`nuecc48` and flat on everything else; νμ passes up on `mcp1k`/`mcp2k` and down
on `nuecc48`/`ncpi0`.**  That shape was fixed before the census was read; it is
not a pattern chosen after the fact.


---

## 4 The systematic comparison

`scripts/pr142_campaign_ab.py` on the four per-sample score tables, unchanged
from pr/142 so the format is the owner's.  The 50 doc-85 degenerate rows are cut
and `cosmict_flag` is used, never `cosmic_flag`.

### 4.1 Completeness, and the one failure

| | OFF | ON |
|---|---|---|
| rows | 3067 | 3067 |
| `rc = 0` | 3067 | 3066 |
| `rc = 139` (SIGSEGV) | 0 | **1** — mcp2k 494297 |

One event in 3067 crashes with the knob on.  It is a pre-existing use-after-free
that the knob only *reaches*; §6 has the full diagnosis and it is item 2 of the
owner's programme.  Every number below is on the 3066 events both arms produced,
except where a denominator is stated.

### 4.2 Selection is untouched

This is the strongest single fact in the round, and it is worth stating before
anything moves:

| | OFF | ON |
|---|---|---|
| `nu_evaluated` | 1435 | 1435 |
| degenerate (doc 85) | 50 | 50 |
| clean evaluated | 1385 | 1385 |
| `event_label` changes | — | **0** |
| `nu_evaluated` flips | — | **0** |
| `nu_sel_len_cm` distribution | — | **identical**, every sample, every percentile |

The only label transition in 3067 events is `nu-candidate → crashed/no-extract`,
which is 494297.  The patch does not change *which* clusters become neutrino
candidates or how long they are; it changes what charge is attributed to them
once they are.  That is exactly what a boundary-cell re-arbitration should do,
and it is why nothing upstream of the fit needs revalidating.

### 4.3 What moves: energy and the BDT scores

Own-arm distributions on the 1385 clean evaluated candidates:

| variable | sample | OFF | ON |
|---|---|---|---|
| `kine_reco_Enu` median | nuecc48 | 1501.9 MeV | 1502.8 MeV |
| | ncpi0 | 1322.7 | **1437.9** |
| | mcp1k | 578.4 | 583.2 |
| | mcp2k | 532.0 | 532.2 |
| | ALL | 571.5 | 569.5 |
| `numu_score` median | ALL | 1.504 | 1.457 |
| `nue_score` median | nuecc48 | 9.888 | 9.717 |

The medians barely move — the population is not being rescaled.  ncpi0's +115
MeV is 19 events and is not evidence of anything on its own.  What moves is the
*tail assignment*: `nue_score` on the nueCC sample gains at p10 (0.225 → 3.111)
while its median falls slightly, i.e. the events that were badly scored are
scored better and the already-good ones are unchanged.  That is the shape a
charge-attribution fix should have.

### 4.4 Working points

Doc 85 §7's points: `numu_score > 0.9` is uB's numu-CC point; the nue points are
a bracket — 7.0 (uB), 4.30103 (the removed toolkit clamp ceiling), 0.7 (loose).
§3.3 pre-registered how to read these as efficiency and background: **nuecc48
and ncpi0 are the signal samples for the nue points; mcp1k/mcp2k are the numu
samples, where a nue-point gain is background.**

| point | sample | OFF-only | ON-only | net |
|---|---|---|---|---|
| `numu > 0.9` | nuecc48 | 2 | 1 | −1 |
| | ncpi0 | 4 | 1 | −3 |
| | mcp1k | 8 | 11 | **+3** |
| | mcp2k | 24 | 22 | −2 |
| `nue > 7.0` | **nuecc48** | 2 | 3 | **+1** |
| | ncpi0 / mcp1k / mcp2k | 0 | 0 | 0 |
| `nue > 4.30103` | **nuecc48** | 1 | 3 | **+2** |
| | ncpi0 | 1 | 0 | −1 |
| | mcp2k | 0 | 1 | +1 |
| `nue > 0.7` | **nuecc48** | 0 | 2 | **+2** |
| | mcp2k | 0 | 1 | +1 |

**Read.** The νe side gains where it should and almost nowhere else: +1 / +2 / +2
on the nueCC sample at the three points, against +0 / +1 / +1 of background
admitted on 2000 mcp2k events.  At the uB point (7.0) the background admitted is
**zero**.  The νμ side is churn without direction — 38 candidates cross out and
35 cross in, net −3 across four samples — which is what a millimetre-scale
re-arbitration near a 0.3 cm keep floor looks like when the score is not near a
cliff.  There is no working point at which this patch costs the νe selection.

### 4.5 The kine dx ≤ 0 guard is not separately attributed yet

Doc 45 §11 measured `kine_dqdx_skip_zero_dx` **inert on SBND with the frame knob
off** (0 NaN `kine_reco_Enu` in production).  With the frame knob on, the ON arm
also carries **0 NaN** on its 1435 evaluated candidates (the single NaN in the
table is 494297, which has no output at all).

That is *consistent with* the guard being inert, but it does not prove it, and
the plan's original "count NaN on both arms" attribution was wrong on this
point: **the guard masks the very NaN that is its own fire signature.** A dx ≤ 0
pair produces a finite Enu with the guard on and a NaN with it off, so zero NaN
on a guarded arm says nothing.

The honest test is a byte gate between a frame-only arm and the ON arm, and it
was run: **`work-*-d144fixframeonly`** (`docs/pr/pr144-frameonly.tla`, which states
**both** keys explicitly so it means the same thing before and after the default
flip) against `work-*-d144fixprod`, one binary, one cfg, all 3067 events.

    ncpi0    tsv/root/zip/tar SAME=19    calib SAME=19    both nusel tables SAME
    nuecc48  tsv/root/zip/tar SAME=48    calib SAME=48    both nusel tables SAME
    mcp1k    tsv/root/zip/tar SAME=1000  calib SAME=462 (538 absent both)
    mcp2k    tsv/root/zip/tar SAME=2000  calib SAME=906 (1094 absent both)

**Byte-identical on every artefact of every event.**  `kine_dqdx_skip_zero_dx` is
**inert on SBND** with the frame knob on, exactly as doc 45 §11 measured it with
the frame knob off.  So the OFF→ON delta in this doc is attributable entirely to
`excl_t0_frame`; the guard ships with it as the PDVD production pair and costs
nothing here.  (It is not useless — it is what stands between a coincident
fit-point pair and a NaN `kine_reco_Enu`, which is 73 candidates on PDVD. SBND
simply has no such pair.)

### 4.6 The mover census

Classes fixed before the census was read (S selection, V vertex > 5 cm, E energy
> 200 MeV, N pathology); the script's own thresholds are looser (|ΔEnu| > 50 MeV
or 10 %, |Δscore| > 0.05, vertex > 1 cm, any label/eval/rc change).

**967 movers of 3067 events (31.5 %)** — far more than pr/142's 10.2 %, as doc 45
§11 predicted from 23/48 and 15/20 moving past 50 MeV on the labelled sets.

| class | n |
|---|---|
| `numu` score | 923 |
| `enu` | 364 |
| `vtx > 1 cm` | 206 |
| `nue` score | 99 |
| `nue_fill` | 55 |
| `label` | 1 |
| `rc` | 1 |

`docs/pr/pr144-movers.tsv` carries all 967 rows.  A third of the population
moving is not a red flag here — it is the measurement of how much of SBND's
charge attribution was sitting on a boundary that the biased frame decided.
What matters is that none of it reached the selection (§4.2) and that where it
reached a working point it went the right way (§4.4).

---

## 5 Mechanism: dropping and mis-attribution are two different symptoms

This is the section that keeps the doc honest, because the headline PDVD number
does **not** reproduce on SBND and it would be easy to imply that it does.

### 5.1 The point-dropping symptom is effectively absent on SBND

`WCT_DQDX_DROP_DEBUG=1` on the 19 NCπ⁰ events, both knob states
(`work-ncpi0-d144drop{off,on}`, a dedicated pair so the debug flag is on both
sides; 19/19 rc=0 each):

| arm | dropped / total trajectory points | fraction |
|---|---|---|
| `d144dropoff` | 78 / 10937 | **0.71 %** |
| `d144dropon` | 66 / 10045 | **0.66 %** |

against PDVD's **51 %** (doc 45 §1) and **64 % → 7 %** in production (doc 45
§9).  The denominators differ by 8 % because the trajectories themselves change,
so the numerators matter more than the ratio; either way **both SBND arms drop
well under 1 % of trajectory points, and the fix barely moves that.**

This is doc 45 §2.4's prediction, confirmed on the production population: with
t0 = 0.8–2.0 µs the frame offset is 1.2–3 mm, and no segment's cloud can reach
far enough in x to starve its competitors.

### 5.2 But the charge changes owner, and that is the whole effect

A cell awarded to the wrong segment is **not dropped** — it is mis-assigned.
`update_association`'s tournament decides *which* segment each 2-D cell belongs
to; the drop counter only sees cells that no segment claimed.  The two symptoms
scale differently with the offset:

* **PDVD, offset 0.6–6 m** — one segment's cloud reaches farther in x than every
  other, wins every cell, and the losers are reduced to their endpoints and
  dropped as "zero charge".  The *dropping* symptom dominates.
* **SBND, offset 1.2–3 mm** — nothing is starved.  What moves is the
  **boundary** cells, the ones sitting near the 0.3 cm keep-floor between two
  segments.  The charge is not lost; it changes hands.

That is why the SBND numbers look the way they do: the drop fraction is flat,
`track_fit` keeps only 1.5 % more points, ghosts do not move at all — and yet
`kine_reco_Enu` and the per-segment dQ/dx features move on **48 of 48** nueCC48
events.  Per-segment charge attribution is exactly what the shower energies,
`numu_cc_1_medium_dQ_dx` and the π⁰ masses are built from.

### 5.3 The `track_fit` census (`d45_trackfit_vs_stmfit.py --all-clusters`)

67 labelled events, 2597 clusters paired between the arms.  `cov`/`d50` are NaN
on a neutrino chain (no `stm_fit` to compare against); the gap metrics survive.

| metric | better = | ON better | ON worse | equal | net |
|---|---|---:|---:|---:|---|
| `tf` track_fit points | higher | 143 | 104 | 2350 | 49921 → **50693** (+772, +1.5 %) |
| `win` segments keeping > 2 points | higher | 69 | 50 | 2478 | 2855 → 2931 |
| `nseg` distinct segments | higher | 76 | 58 | 2463 | 4332 → 4403 |
| `ghost` points > 2 cm from raw charge | lower | 4 | 6 | 2587 | **9 → 9, flat** |
| `gap50` trajectory spacing | lower | 151 | 137 | 2309 | 315 → 312 |
| `raw` input cloud | — | — | — | 2597 | 511166 → 511166, identical |

**The recovered points are not ghosts.**  Of the 143 clusters that gain
`track_fit` points, only **3** also see their ghost fraction rise, and the total
ghost count is unchanged — so the fix is putting points back where there is
charge, not inventing trajectory.

But this is a **modest, non-uniform** improvement: 143 clusters better against
104 worse.  It is not PDVD's one-sided rescue, and this doc does not claim it
is.  On SBND the tournament was already arbitrating real proximity; the fix
removes a millimetric bias from it.


---

## 6 The defect this study surfaced: a use-after-free reached only with the knob on

**SBND mcp2k 494297 SIGSEGVs with `excl_t0_frame` on.**  1 event in 3067; the OFF
arm reconstructs it fine on the same binary.  This is the single most important
practical finding of the round, because `excl_t0_frame` is **PDVD production
since 2026-09-05**.

### 6.1 Bisected and reproducible

| arm | `rc` |
|---|---|
| `excl_t0_frame` alone (`work-mcp2k-d144bisframe`) | **139 (SIGSEGV)** |
| `kine_dqdx_skip_zero_dx` alone (`work-mcp2k-d144bisguard`) | 0 |
| both (`work-mcp2k-d144bisboth`) | **139** |
| knob off (`work-mcp2k-d144off`) | 0 |
| knob on, **pre-pr/143** binary `a4ff5439` (`work-mcp2k-d144prepr143`) | **139** |

The frame knob alone is sufficient; the kine guard is innocent; and the last row
**exonerates doc 143** — the crash reproduces on the binary that predates the
`break_segment` cluster stamp, so it is not an interaction with that change even
though `break_segment` allocates the object involved.

### 6.2 Root cause, from valgrind (`--track-origins=yes`, 1827 errors / 179 contexts)

A `PR::Vertex` is used after it is freed.  Its whole lifecycle:

| stage | site |
|---|---|
| **allocated** | `PR::make_vertex` (`PRGraph.h:203`) ← `PR::break_segment` (`PRSegmentFunctions.cxx:1173`) ← `snap_main_vertex_to_kink` (`NeutrinoVertexFinder.cxx:2858`) ← `TaggerCheckNeutrino::visit:3048` |
| **freed** | the last `shared_ptr` dies with a `std::set<shared_ptr<Vertex>>` destructing at the end of `eliminate_short_vertex_activities` (`NeutrinoVertexFinder.cxx:2480`) ← `improve_vertex:3555` |
| **written after free** | `TrackFitting::organize_segments_path` (`TrackFitting.cxx:9107`) — *"Invalid write of size 1 … 184 bytes inside a block of size 200 free'd"* |
| **read after free** | `TrackFitting::form_map_graph` (`:4115`) ← `do_multi_tracking:9174` → SIGSEGV |

At the fault, gdb shows the corrupted graph bundle directly:

```
v_bundle1 = {vertex = {_M_ptr = 0x555500000000}, index = 93825124875408}
v_bundle2 = {vertex = {_M_ptr = 0x55555c3e3740}, index = 4}
```

`v_bundle1.vertex` is non-null — so the existing `if (v_bundle1.vertex && ...)`
guard passes — but points at reclaimed memory, and `index` holds a pointer-sized
value where its sibling holds `4`.

**So the fitter is holding graph state across a graph mutation it was not told
about**: `eliminate_short_vertex_activities` removes a vertex and drops the last
reference while `TrackFitting`'s `m_graph` view still refers to it.  The knob's
role is only to change the trajectory enough that `snap_main_vertex_to_kink`
fires and produces a vertex that then gets eliminated — the ordering that
exposes the bug.  The knob's own write is to a `std::map<int,double>`; it cannot
corrupt anything.

### 6.3 Not fixed in the first pass, and why two guesses failed

Two one-line guards were tried and **both failed**, because this is not a missing
guard — no test at the read site can repair a pointer that was already freed:

1. a null check on `pc_transform()`'s result (which *can* return `nullptr`,
   `PCTransforms.cxx:288`, and is guarded at every other call site —
   `connect_graph_relaxed.cxx:135`, `NeutrinoSteinerGapGraph.cxx:132` — so it is
   worth hardening on its own merits, but it is not this bug);
2. an empty-`wcpts()` fallback at `:4115` (a real latent UB — `PRGraph.cxx:89`
   and `doctest_prsegment.cxx:36` both say a segment may carry fits and no
   wcpts, and the guard there tests only `fits.empty()` — but again not this bug).

Both were reverted; the tree carries neither.  Fixing the real defect means
correcting object lifetime between `eliminate_short_vertex_activities` and
`TrackFitting`'s cached graph view, which is a change to shared production code
on its own evidence and belongs in its own round.  **Owed, and it is owed on
PDVD's behalf more than SBND's**: PDVD runs this knob in production today.

**Scheduled.**  This is item 2 of the owner's programme (§11), and §6.5 closes
it.  The method note for whoever takes it, so the two failed attempts are not repeated: the sites
above are attributed by an `-O2` build, and `TrackFitting.cxx:9107` / `:4115` are
*inlined call sites* inside `do_multi_tracking`, not the writing and reading
statements.  Build `clus` at `-Og -g` into its own pin and re-run 494297 under
valgrind before naming a line.  Two candidate shapes to distinguish first:
`TrackFitting::set_graph` (`TrackFitting.cxx:572`) early-returns when handed the
*same* `shared_ptr<Graph>` and so skips `sync_from_graph()` after an in-place
mutation; and `boost::remove_vertex` (`PRGraph.cxx:45`) invalidating descriptors
cached in `m_all_edges` / `m_cluster_edges`.  Read the values before naming a
site.  And gate it as a **shared-code** change — `TrackFitting` binds on PDVD,
PDHD and the uBooNE chain, so knob-off byte-identity is owed on each affected
detector's standard manifest, not only SBND's 3067.


### 6.4 Root cause, named: a vertex is removed while its edges are still attached

The `-Og` rebuild the method note above asks for turned out to be unnecessary —
the existing valgrind log already carries the full lifecycle, and reading the
*graph type* rather than the line numbers settles it.

`PR::Graph` is `boost::adjacency_list<setS, setS, undirectedS, NodeBundle,
EdgeBundle, GraphBundle, listS>`.  **`setS` vertex storage means descriptors are
stable** — removing a vertex does not renumber or invalidate the others.  That
kills one of the two candidate shapes outright: this is not descriptor
invalidation in `m_all_edges`, and it is not a missed `sync_from_graph()`.

What is left is the BGL contract on `remove_vertex`:

> Removes vertex *u* from the vertex set of the graph.  **It is assumed that
> there are no edges to or from vertex u when it is removed.**  To ensure this,
> `clear_vertex()` should be called first.

`PR::remove_vertex` (`PRGraph.cxx:41-49`) does not clear:

```cpp
bool remove_vertex(Graph& graph, VertexPtr vtx)
{
    if (! vtx->descriptor_valid()) { return false; }
    auto desc = vtx->get_descriptor();
    boost::remove_vertex(desc, graph);      // <-- no clear_vertex(desc, graph)
    vtx->invalidate_descriptor();
    return true;
}
```

So if the removed vertex still has an incident edge, the *node* is deleted while
the *edge* survives in the graph's edge set.  The next consumer walks that edge
and dereferences a freed node:

```cpp
// TrackFitting::get_ordered_segment_vertices, TrackFitting.cxx:1631-1636
vd1 = boost::source(ed, *m_graph);
auto& v1_bundle = (*m_graph)[vd1];       // freed node
start_v = v1_bundle.vertex;              // shared_ptr copied out of freed memory
...
// TrackFitting::organize_segments_path, TrackFitting.cxx:2119-2121
PR::Fit start_fit = start_v->fit();
start_fit.point = start_p;
start_v->fit(start_fit);                 // the "Invalid write of size 1 ... 184
                                         // bytes inside a block of size 200"
```

That is exactly the `Address … is 184 bytes inside a block of size 200 free'd`
record, the `D3Vector.h:77` frame, and gdb's `v_bundle1.vertex._M_ptr =
0x555500000000` with a pointer-sized value in `index` — a node bundle read out
of reclaimed memory.

**Which call site removes a non-isolated vertex.**  Of the five cases in
`eliminate_short_vertex_activities`, four guard the degree of the vertex they
delete (case 2 by its branch condition `num_segs_v2 == 1`, case 4 and case 5
explicitly).  **Case 3 does not:**

```cpp
if ((v1 == main_vertex && num_segs_v1 > 1) || (v2 == main_vertex && num_segs_v2 > 1)) {
    if (length < 0.1*units::cm) {
        to_be_removed_segments.insert(sg);
        VertexPtr to_remove = (v1 == main_vertex) ? v2 : v1;
        to_be_removed_vertices.insert(to_remove);   // degree unconstrained
```

The knob's whole role is upstream of this: it changes the trajectory enough that
`snap_main_vertex_to_kink` fires, `break_segment` allocates a vertex, and that
vertex reaches case 3 with more than one segment attached.

**The prototype does the same thing and gets away with it.**
`NeutrinoID_improve_vertex.h:411-419` has the identical unguarded case-3 removal,
and `del_proto_vertex` (`NeutrinoID_proto_vertex.h:2002`) erases the vertex from
each of its segments' vertex sets:

```cpp
for (auto it = map_vertex_segments[pv].begin(); it != map_vertex_segments[pv].end(); it++)
    map_segment_vertices[*it].erase(map_segment_vertices[*it].find(pv));
map_vertex_segments.erase(pv);
```

A prototype segment can legally end up with **one** vertex.  A BGL edge cannot —
it has two endpoints or it does not exist.  **This is an undocumented
prototype/toolkit divergence** (CLAUDE.md §5.4) and it is why the port inherited
a memory-corruption bug from a construct that is merely untidy in the original.

**Two fixes, and the recommendation.**

| | change | what it does when the removed vertex has other segments | divergence from the prototype |
|---|---|---|---|
| **(a)** | `PR::remove_vertex` **refuses** and returns `false` (with a log line) when `boost::degree(desc, graph) > 0` | the short segment is still removed; the vertex survives with its other segments intact | the vertex stays where the prototype detached it — the port does **less** |
| **(b)** | `PR::remove_vertex` calls `boost::clear_vertex(desc, graph)` first | the vertex goes **and so do its other segments' edges**, while those `Segment` objects stay registered elsewhere | strictly **more** destructive than the prototype |

**Recommended: (a).**  It is one guard in one function; it protects every one of
`remove_vertex`'s call sites rather than only case 3; it converts a silent
memory-corruption path into a no-op with a log line; and callers already have to
tolerate a `false` return, because the function already returns `false` on an
invalid descriptor.  (b) invents a deletion the prototype never performs.

Either way it is a **shared production code** change — `TrackFitting` and
`PRGraph` bind on PDVD, PDHD and the uBooNE chain — so it is owed a knob-off
byte-identity gate on each affected detector's standard manifest, not only
SBND's 3067.  Since the guard only fires where the current behaviour is
undefined, the expectation is byte-identity everywhere except 494297.

### 6.5 FIXED — toolkit `25baa8aa`, and gated on the 3067

`PR::remove_vertex` now refuses a vertex that still has incident edges, returning
`false` (which callers already handle, for the invalid-descriptor case) and
logging the vertex's graph index and degree at WARN.  §6.4's table (a) — the
owner's choice over `clear_vertex`, which would delete the other segments' edges,
a deletion the prototype never performs.

| | |
|---|---|
| 494297 on the config that SIGSEGV'd | **`rc = 0`**, guard fires **once** |
| the whole arm, `work-*-d144fixprod` (committed default, crash-fixed binary) | **3067 / 3067 `rc = 0`** — ncpi0 19, nuecc48 48, mcp1k 1000, mcp2k 2000 |
| guard fires across those 3067 events | **exactly 1** — 494297, and nothing else |
| `wcdoctest-clus` | 323 cases / 23061 assertions, 0 failed |
| freshness (M1) | `libWireCellClus.so` 12:28:48 newer than `PRGraph.cxx` 12:28:19, `wcbuild rc=0` |

**Byte gate, `work-*-d144on` vs `work-*-d144fixprod`, all 3067 events:**

    ncpi0    tsv/root/zip/tar/calib  SAME=19    both nusel tables SAME
    nuecc48  tsv/root/zip/tar/calib  SAME=48    both nusel tables SAME
    mcp1k    tsv/root/zip/tar        SAME=1000  calib SAME=462 (538 absent both)
    mcp2k    tsv/root/zip            SAME=1999  calib SAME=905 (1094 absent both)
             the one non-SAME event is 494297

On mcp2k the comparison reports `MISSING_A` / "File is not a zip file" / a tar
error on exactly one event.  That event is **494297**, and the reason is the
crash itself: the pre-fix arm's directory holds `rc=139` and **zero-byte**
`mabc-pr.zip` and `pctree-pr-evt494297.tar.gz`.  The two `nusel` tables DIFF for
the same reason — `nusel-events.tsv` is 2000 lines on the pre-fix arm and 2001 on
the fixed one, the extra row being the event that now reconstructs.

**So the guard is byte-identical on every event where the old behaviour was
defined, and the only difference in 3067 events is the one that used to crash.**
The fire count is the stronger statement: the guard is a no-op unless it fires,
and it fires once.

The same argument is what the **other detectors** are owed — PDVD, PDHD and the
uBooNE chain all bind `TrackFitting` and `PRGraph`.  Their gate is cheap for the
same reason: run each detector's standard manifest and grep for
`pr144 remove_vertex: refusing`.  Zero fires ⇒ byte-identical by construction.
**That is still owed** and is the one piece of this fix not yet discharged.

**Item 2 of the owner's programme (§11) is closed on SBND.**

---

## 7 The labelled-set adjudication

### 7.1 The sentinel suite: 30 PASS / 0 FAIL → 16 PASS / 14 FAIL

`scripts/pr127_sentinels.py` is 30 assertions, each pinned to one event and one
*shipped* fix, with thresholds placed between the measured pre-fix and post-fix
values so the sentinel fails when the fix dies, not when a number drifts.

    OFF arm  30 PASS   0 FAIL   0 SKIP
    ON arm   16 PASS  14 FAIL   0 SKIP

**Carry the caveat with the number.**  Every one of these sentinels was written
and validated against the OFF reconstruction — the one built on the biased drift
frame.  A sentinel breaking is evidence, not a verdict; §8 is where the owner
adjudicated nine of them by eye.

| event | sample | shipped fix | what failed on ON |
|---|---|---|---|
| 179369 | mcp2k | pr/130 B back-guard | `pf_absent 'pi0'` — a spurious π⁰ is back among 46 PF nodes |
| 47212 | mcp2k | pr/120 stem_backfill | `pf_node_ge mu- 40` — **no** `mu-` node at all |
| 175896 | mcp1k | pr/130 backfill | `pf_node_ge proton 100` (seen 31); also the seg-ID log clause |
| 393505 | mcp2k | pr/129 cosmic | `Enu=858.2` vs window [540,600]; a `mu- 268` node appears among 14 |
| 94392 | mcp2k | pr/129 guard-freed | `Enu=1040.2` vs window [1136,1149] |
| 171572 | mcp2k | pr/129 real daughter | `pf_contains 'mu- 304'` — the daughter is gone (but `Enu=780.8` is still inside [779,791]) |
| 177536 | mcp2k | doc 84 r2.1 cathode bridge | `pf_node_ge mu- 800` (seen 644, plus a second node at 276) |
| 347890 | mcp2k | doc 84 r4 track partner | `pf_node_ge mu- 460` (seen 429) and the bridge's own log line |
| 137238 | nuecc48 | pr/93 r4 + pr/127 sccc | `pf_node_lt mu- 150` (seen 212, 63, 60) |
| 52693 | mcp2k | pr/125 pass3_cone guard | `pf_node_lt e- 175` — **seen exactly 175** |
| 281595 | mcp1k | doc 84 r2 members_geometry | `pf_node_ge mu- 780` — **seen 779** |
| 72786 | mcp2k | pr/128 class A **CONTROL** | only `log_contains 'pr130 pass4_prox_guard: decline seg=9004'`; the outcome clause `log_absent 'pr128 pf-orphan-near-cross-cluster'` **passes** |
| 100222 | mcp2k | pr/130 prox guard | only `log_contains '… decline seg=14003'`; both physics clauses pass |
| 66366 | mcp2k | doc 84 r1 (OUTCOME ONLY) | only `log_contains 'nseg_chain=4 L_cm=300.6'`; `pf_node_ge mu- 650` passes at 689 |

**Three things this table says that the raw 16/14 does not.**

1. **Three of the fourteen fail only on a `log_contains` clause — but they are
   not the same case, and the logs had to be read to tell them apart.**

   | event | the clause | what the logs actually show |
   |---|---|---|
   | 72786 | `decline seg=9004` | the guard **still fires on the same objects**; OFF declines `{45038, 9004, 9006, 9008}`, ON declines `{45038, **9003**, 9006, 9008}`. Pure segment-id renumbering — the clause was never a discriminator. |
   | 66366 | `nseg_chain=4 L_cm=300.6` | the chain is **still assembled**, from 3 segments instead of 4 and at 299.5 cm instead of 300.6. Outcome intact (`pf_node_ge mu- 650` passes at 689); the literal is stale. |
   | 100222 | `decline seg=14003` | **no `pass4_prox_guard: decline` line at all on ON.** The guard stops firing on this event. Its two physics clauses still pass, so the outcome pr/130 shipped it for — the 110 cm muon leaving the EM shower — still holds, *by some other route*. |

   Only 72786 is purely brittle.  100222 is the "zero fires is not dead code"
   case: **pre-empted, not superseded**, and it must not be quietly re-baselined
   as brittleness — its negative control (`SBND_SHOWER_PASS4_PROX_GUARD_LEN=0`)
   is the thing that says whether the outcome still depends on the guard at all.

   And 100222 is not an isolated coincidence: it is **one of the eight
   candidates whose excluded pool empties** (§15.1, `n_excluded` 5 → 1,
   359.0 → 135.0 MeV).  A guard that declines objects has nothing to decline
   once the objects are no longer in the pool, which is a coherent account of
   both the silence and the surviving outcome — and a reason to read this
   sentinel together with item 5 rather than on its own.
2. **The background-admission control holds.**  72786 is the pr/128 CONTROL
   sentinel — "the continuation terms keep the cosmics OUT" — and its outcome
   assertion passes on the ON arm.  Together with §4.4's zero background admitted
   at the uB νe point, that is the reason this patch is not a background risk.
3. **Two are one-unit grazes.**  52693 wants `e- < 175` and sees 175; 281595
   wants `mu- ≥ 780` and sees 779.  A one-unit margin cannot discriminate a dead
   fix from a live one, which is a defect in the sentinel, not in the arm.

**And the cathode-bridge family is not dead.**  Of the five doc-84 cathode-bridge
sentinels, **three pass** — 53793 (`mu- 913` want ≥ 700), 172794 (`mu- 689` want
≥ 600, bridge log line present) and 67026 (`mu- 714` want ≥ 650) — and so does
77978, the owner's own r2.1 scan event, whose proton prong survives.  The two
failures (177536, 347890) are specific events, not a broken mechanism.  That
matters for item 3 of the programme: the question is why *these two* lose the far
half, not why the bridge stopped working.

### 7.2 The π⁰ 66-set census is INVALID for this comparison

`scripts/pr141_pi0_census2.py` reports:

| | OFF | ON |
|---|---|---|
| exact (of 66 hand π⁰) | 27 (40.9 %) | 7 (10.6 %) |
| `absent-on-arm` | 26 | **93** |

**Do not read 27 → 7 as physics.**  Two independent signs say the join, not the
reconstruction, moved:

- The **OFF** arm should read production's number.  pr/141 measured 36/66 on
  production; the OFF arm here differs from production only by doc-143's 44
  events in 3000, which cannot cost 9 of 66 π⁰.  27 is already wrong before the
  patch is applied.
- `absent-on-arm` more than triples, to 93 of 132 labelled γ.  These events all
  reconstruct; their showers are simply not *found*.

The cause is the join key.  The census matches hand labels to reconstruction by
**shower ID**:

```python
by = {int(s["id"]): s for s in (dump.get("showers") or ())}
s1, s2 = by.get(int(g["1"]["shower"])), by.get(int(g["2"]["shower"]))
...
if s is None: reasons.append(name + ":absent-on-arm")
```

`id` is a per-run graph index.  It renumbers under **any** reconstruction change,
so an integer-ID join is only valid within the epoch the labels were taken in —
which is exactly what a before/after study violates.  This is the same class of
mistake as "a retile ident is not the Bee cluster id": join to a label by
**position**, never by number.

**Owed:** a positional (y, z) join — match a labelled γ to the nearest
reconstructed shower start within a stated tolerance, and report the match rate
against a chance floor.  Until that exists the π⁰ census cannot grade this or any
other reconstruction change, and no π⁰ number appears in this doc's verdict.

---

## 8 The Bee handover, and the owner's scan

Twelve events, two order-matched Bee sets — Bee addresses an event only by its
index within a set, so both zips carry the identical list in the identical order
and the owner steps two tabs to the same index.

    OFF  https://www.phy.bnl.gov/twister/bee/set/a6027cd7-14e8-43fa-a16a-d5b10fe166ba/event/list/
    ON   https://www.phy.bnl.gov/twister/bee/set/2455120d-016d-40bc-8b23-96e4db8c8f07/event/list/

Rows 0–8 are the sentinel regressions that carry a physics clause; rows 9–11 are
the largest movers.  `docs/pr/pr144-bee.index.txt` has the annotated index with
one line of quantitative evidence per row.

| idx | event | what changed | owner's reading |
|---|---|---|---|
| 0 | 179369 | spurious π⁰ back; Enu +130 MeV | better |
| 1 | 47212 | muon PF node gone; Enu −101 MeV | better |
| 2 | 175896 | proton 100 → 31 MeV; vtx 11.7 cm | better |
| 3 | 393505 | Enu 560 → 858 MeV, a `mu- 268` node appears | **"not sure why the extra muon were added to the energy"** |
| 4 | 94392 | Enu 1040 vs window [1136,1149] | better |
| 5 | 171572 | `mu- 304` daughter missing (Enu unchanged) | better |
| 6 | 177536 | cathode-bridge muon 800 → 644 MeV (+ a 276 node) | **worse — "the two cathode-bridge mions are lost"** |
| 7 | 347890 | bridged partner's muon 460 → 429 MeV | **worse — same** |
| 8 | 137238 | `mu-` 212 where the sentinel wants < 150; Enu 736 → 1161 | **"the hadronic shower made to an EM shower"** |
| 9 | 111412 | `nue_score` 0.23 → **9.04**, vertex moved 42.3 cm | better |
| 10 | 98844 | largest vertex move in 3067 events, 52.4 cm | better |
| 11 | 100135 | largest energy move, Enu 144 → 1369 MeV | better |

**Verdict returned: "Overall, I feel the fix is better"** — 9 of 12 judged
improvements, 2 judged worse (idx 6, 7), 1 unexplained (idx 3) and 1 named as a
different defect (idx 8).  This is a hand scan of before/after images, which is
the only instrument in this round that can answer "is the new attribution the
right one"; it is not blinded, deliberately, because the owner asked for
before/after pairs.

---

## 9 Runtime

Per-event mode, `core_s` from the job's own `Timer: Total`; wall under
concurrency is contention-dominated and is reported beside it, not compared.

| arm | n | core sum | core median | wall sum | peak RSS median |
|---|---|---|---|---|---|
| d144off | 3067 | **3.53 h** | 1.6 s | 13.14 h | 0.44 GiB |
| d144on | 3066 | **3.54 h** | 1.6 s | 13.14 h | 0.45 GiB |

**The flip is free** — 0.3 % on core time, inside run-to-run noise, and the
medians and p90s are identical to the decimal.  (PDVD measured +4 % wall for the
same knob; SBND does not pay it because the offset it removes is millimetric and
the tournament re-runs the same number of queries.)  The one p90 outlier is
mcp2k's 3.11 GiB max RSS, which is 494297 on its way to the SIGSEGV.

---

## 10 Verdict

**FLIP.  Both knobs are SBND production defaults as of 2026-09-06.**

The pre-scan draft of this section said *do not flip*, on the metrics alone: nine
shipped-fix sentinels with a physics clause had stopped holding, the νμ working
point churned with no net direction, and the patch had surfaced a use-after-free.
That recommendation was wrong in its framing, and the owner's scan is what
changed it.  Recording why, because the reasoning is the transferable part:

1. **This is a bug fix, and the burden of proof runs the other way.**  With the
   knob off, every SBND neutrino candidate's exclusion tournament is arbitrated
   in the wrong drift frame.  "Nine sentinels moved" is not an argument for
   keeping a known-wrong comparison; it is a statement that nine shipped fixes
   were tuned against it.  The only question a sentinel can answer is *did the
   fix's structural property survive* — and for three of the fourteen the answer
   is "the property survived, a segment id changed" (§7.1).
2. **The owner scanned the images and 9 of 12 are better** (§8), including the
   two largest movers in the population and the strongest single case — 111412,
   `nue_score` 0.23 → 9.04 with the vertex moving 42.3 cm onto the charge.
3. **Nothing upstream moves.**  0 label changes, 0 `nu_evaluated` flips,
   identical `nu_sel_len_cm` (§4.2).  The patch cannot change what is selected,
   only what is attributed to it.
4. **The νe side gains and buys no background.**  +1 / +2 / +2 on nueCC at the
   three νe points against +0 / +1 / +1 on 2000 mcp2k events, and **zero**
   background admitted at the uB point (§4.4).  The pr/128 background control
   sentinel still passes (§7.1).
5. **The recovered charge is real.**  143 clusters gain `track_fit` points
   against 104 that lose them, total 49921 → 50693, and the ghost count is
   **flat at 9** — only 3 of the 143 gaining clusters gain any ghost (§5.3).
   The fix puts points back where there is charge; it does not invent trajectory.
6. **It costs nothing** (§9).

**What the flip does not settle**, and is owed as follow-up rather than as a
reason to wait: the crash (§6, item 2), the two cathode-bridge regressions the
owner judged worse (item 3), the unexplained +298 MeV on 393505 (item 4), the
hadronic-shower typing on 137238 (item 5), the sentinel re-baseline (§13), and
the guard attribution (§4.5).

---

## 11 The owner's five-item programme

| # | item | status |
|---|---|---|
| 1 | **turn on this, since it is a bug fix** | **DONE** — both defaults flipped, §2's T0′/T1′/T1″ proofs, this commit |
| 2 | **fix the crashing event** | **DONE on SBND** — toolkit `25baa8aa`, the owner's option (a): `PR::remove_vertex` refuses a vertex whose degree is > 0 (§6.4). Gated on all 3067 (§6.5): every artefact byte-identical to `d144on` except 494297 itself, which recovers from `rc=139` + zero-byte outputs; the guard fires on **exactly 1 event of 3067**. **Owed:** the same knob-off gate on PDVD, PDHD and the uBooNE chain, which also bind `TrackFitting`/`PRGraph` — cheap, because zero refusal lines ⇒ byte-identical |
| 3 | **examine idx 6, 7 for the cathode-bridge muon to improve** | **diagnosed, §14** — and they are TWO defects, not one. 347890: the far half is still reconstructed but its PID flips 211 → 11, and doc 84 r4's partner filter refuses EM partners *by design*, so this merges into item 5. 177536: nothing is lost — the muon is split into two PF nodes, which double-counts a 105.7 MeV rest mass (21 splits in the population, 6 pay it) |
| 4 | **understand why the energy was added for idx 3** | **answered AND fixed behind a default-OFF knob, §13** — 393505's +298 MeV is a 177.8 MeV cluster-15 cosmic segment admitted by `kine_count_near_cross_cluster` (proximity only, `gap_cm = 0.00`, no direction test) plus one muon rest mass. `kine_near_pointing_impact` (toolkit `7c4bf46a`) brings Enu back to 574.8 and restores the pr/129 sentinel's energy clause. Owed: its own 3067-event arm before it is flipped |
| 5 | **improve the hadronic shower reconstruction** | **scoped, §15** — on 137238 the exclusion pool empties (`kine_n_excluded` 9 → 1, 316.4 → 0.0 MeV) and the EM shower absorbs it (354 → 555 MeV, 103 → 143 cm). **The deciding census has run** (§15.1, 1434 candidates on both arms): the pool does NOT collapse — Σ`kine_n_excluded` −1.5 %, Σ excluded energy −4.4 %, 108 fell / 92 rose / 1234 unchanged — so 137238 sits in an **8-event tail**, and this is a **PID / shower-building round, not an exclusion-threshold round**. Working set = those 8 events; reading list docs 127, 93, 125, 133, 136, 141. **No code changed** |
| — | **update the sentinels** | §16, on the `d144fixprod` arm |

**Items 3, 4 and 5 are carried forward in [doc 145](145_items-3-4-5-improvement-round.md)**,
which prices item 4's fix on 3067 events, names the escape behind item 3b's
rest-mass double count, and opens items 3a + 5 as one PID round.

**A shared-mechanism check comes before items 3 and 4 are opened as two
investigations.**  The fourteen failures cluster: two cathode-bridge sentinels
fail together, and three are the pr/129 pointing-guard family (393505, 171572,
94392).  `excl_t0_frame` repaired the raw-vs-corrected frame mix *only inside*
`TrackFitting::update_association`.  Any other site that does its own
`time → x` conversion still has the original defect and now has it against
changed input — and cathode-crossing is where that bites hardest, because x
changes sign across the cathode and |x| is not drift distance.  Grep
`long_muon_cathode_bridge*` (`TaggerCheckNeutrino.cxx`, `MuonMCSDriver.cxx`) and
the pointing-guard code for their own drift arithmetic first.  If either computes
x in the raw frame, items 3 and 4 are one defect of the same class as doc 45.

**ANSWERED — and it is not a shared frame defect.**  It was settled by
measurement rather than by the grep, which is the stronger form: on **347890**
the calib dumps show the bridged muon's ends *unchanged* at x = (106.91, 4.95)
between the arms (§14.1), so no second `time → x` site moved them; what moved is
the far half's PID, 211 → 11.  On **393505** §13.2 traces the new muon to
`kine_count_near_cross_cluster`'s proximity-only admission, not to drift
arithmetic.  So items 3 and 4 are **not** one defect: 3a merges into item 5
(typing), 3b is a segment split (§14.2), and 4 has its own fix (§13.2.1).  What
is still *not* done is the generic sweep — no exhaustive audit of every site
outside `TrackFitting::update_association` that does its own drift conversion.
That remains open for any future round.

---

## 12 What this does not certify

- **Truth.**  There is no truth-level Enu at population scale on these samples;
  `scan-r2patrec/list_truth_nu_vertices.txt` is 104 keys of a different, older
  population.  Every "better" in this doc is either a labelled-set assertion or
  the owner's eye.
- **The π⁰ census** (§7.2) — invalid until it joins by position.
- **The kine dx ≤ 0 guard's separate contribution** (§4.5) — unmeasured, not zero.
- **`proj_skip_unmapped_face`**, doc 45's third knob.  It has no config-bool
  route: the only way on is a key in the runtime `sbnd_track_fitting.json`, so a
  byte-identical compiled jsonnet would not prove the fit unchanged, and bundling
  it would make this doc's OFF→ON delta un-attributable.  Doc 46 measured it at
  0 fires on 231 SBND events.  It stays out.
- **The two hardening candidates from §6.3** — the `pc_transform()` null check
  (which `PCTransforms.cxx:288` can return and which every other call site
  guards) and the empty-`wcpts()` fallback at `TrackFitting.cxx:4115` (which
  `PRGraph.cxx:89` and `doctest_prsegment.cxx:36` both say is reachable).  Both
  are real latent defects on their own merits and neither is this bug; the tree
  carries neither.
- **Any arm launched after 2026-09-06 10:08** is on a different cfg epoch than
  `d144off`/`d144on` (§3.2).

---

## 13 Item 4 — why 393505 gained 298 MeV, and the rest-mass double count behind it

The owner's idx-3 question — *"not sure why the extra muon were added to the
energy"* — is answered from the arms already on disk.  No re-run.

### 13.1 The accounting, exactly

`calib-pr-evt393505.json`, `kine` block:

| | OFF | ON |
|---|---|---|
| `kine_reco_Enu` | 559.9 | **858.2** |
| counted particles (pdg, MeV, info) | 13 / 371.6 / 1 · 11 / 66.9 / 2 · 11 / 9.0 / 2 · 11 / 1.5 / 2 · 11 / 5.2 / 2 | the same five **plus 13 / 177.8 / 1** |
| `kine_n_excluded` | 5 | **4** |
| `kine_energy_excluded_other` | 772.7 | 592.1 |
| `kine_reco_add_energy` | 105.7 | **211.3** |

The +298.3 MeV decomposes with no remainder:

    +177.8   the new mu- node's kinetic energy
    + 14.9   the 66.9 -> 81.8 MeV shower
    +105.7   kine_reco_add_energy, which DOUBLED
    -------
    +298.4

### 13.2 Where the new muon came in — and it is not the pr/129 pool

The pointing test pr/129 shipped is still doing its job.  Its per-candidate log
line is present on **both** arms and SKIPs every cluster-15 candidate on both:

    OFF  kine_guard_freed_impact: seg idx=13 cluster=15 ke_mev=268.70 d_vtx_cm=74.37 impact_cm=68.67 miss_deg=67.4 -> SKIP
    ON   kine_guard_freed_impact: seg idx=14 cluster=15 ke_mev=177.78 d_vtx_cm=68.91 impact_cm=69.10 miss_deg=112.2 -> SKIP

The segment came in through a **different pool**, which logs it plainly:

    ON   kine_count_near_cross_cluster: COUNT seg idx=14 cluster=15 pdg=13 score=0.159 ke_mev=177.78 len_cm=65.5 gap_cm=0.00
    OFF  (no such line — the pool counted nothing)

So a 65.5 cm segment of **cluster 15 — the cosmic pr/129 was written to keep
out** — is admitted by `kine_count_near_cross_cluster`, the pr/128 class-A
near-cross-cluster pool, whose test is **proximity only**: the gap collapsed to
`0.00 cm` once the fit points moved into the corrected frame, and that pool has
no direction test at all.  The pointing guard that would have refused it
(`miss_deg = 112.2` — it aims *away* from the vertex) is wired to the
guard-freed pool only.

This is the failure mode doc pr/128 predicted in its own words — proximity alone
admits cosmics — arriving for real.

### 13.2.1 The fix, built and measured (toolkit `7c4bf46a`, default OFF)

The same three-clause test pr/129 already ships for the guard-freed pool is now
offered to this one, behind its own knob:

| knob | meaning |
|---|---|
| `kine_near_pointing_impact` | cm; **0 = no test = byte-identical** (C++ default) |
| `kine_near_pointing_miss_deg` | deg; only read when the impact cut is armed |

On 393505, one-event arm `work-mcp2k-d144np` at 20 cm / 30° — pr/129's own SBND
production values:

| | Enu | `add_energy` | `n_excluded` |
|---|---|---|---|
| OFF (pre-flip) | 559.9 | 105.7 | 5 |
| ON (flip, knob off) | **858.2** | 211.3 | 4 |
| ON + pointing test armed | **574.8** | 105.7 | 5 |

    kine_near_pointing_impact: seg idx=14 cluster=15 ke_mev=177.78 d_vtx_cm=68.91
                               impact_cm=69.10 miss_deg=112.2 -> SKIP

**The test removes the contamination and keeps the improvement.**  The residual
+14.9 MeV over the pre-flip arm is the shower going 66.9 → 81.8 MeV, which is
the genuine charge re-attribution `excl_t0_frame` exists to make.  It also
restores the pr/129 sentinel's energy clause — `Enu = 574.8` is back inside the
shipped window [540, 600] where the unguarded ON arm read 858.2.  (That
sentinel's other clause, `pf_contains 'mu-  268'`, still fails on a **stale
literal**: the segment's KE is 177.8 now, not 268.70.  Re-expressing it belongs
to §16, not here.)

Gates: compiled-config T0 — knob off compiles **byte-identical** to the committed
`4c84855c`, knob on adds exactly two keys (248 → 250); `wcdoctest-clus` 323 /
23061, 0 failed; freshness proof done.

**NOT flipped.**  It is a hypothesis with one supporting event.  Before it earns
a default it needs its own 3067-event arm — to price how often the test refuses
a segment that *should* have been counted — and its own negative control.  That
is the named next step for item 4.

### 13.3 The other half of the +298 is arithmetic, not physics

`kine_reco_add_energy` accumulates `rest_term_rules(pdg, mass)` **once per
counted particle** (`NeutrinoKinematics.cxx:230, 274`), and a muon's rest mass is
105.658 MeV.  It doubled here because a second `mu-` node was counted.  That is
correct behaviour *if* the second node is a second muon.  §14 shows a case where
it is not.

---

## 14 Item 3 — the two "lost cathode-bridge muons" are two different defects

The owner read idx 6 and 7 as one failure.  The logs say they are not.

### 14.1 347890 — the bridge really does stop firing

| | OFF | ON |
|---|---|---|
| bridge log | `merge shower sid=5 (mu_len=182.9cm) <- sid=0 (mu_len=27.1cm) gap=14.3cm ends x=(4.9,-4.2)cm` | **nothing** |
| bridge *reject* log | — | **nothing** |
| MCS chain | `nseg=6 npoints=356 len=210.0cm ... cathode_drop=2/3` → `ke_range_toolkit=488.7` | `nseg=1 npoints=306 len=182.9cm ... cathode_drop=1/1` → `ke_range_toolkit=429.4` |
| counted particles | `2212 133.7 (1)` · `11 1.2 (2)` · **`13 488.7 (1)`** | `2212 135.9 (2)` · `11 59.0 (2)` · `11 26.0 (1)` · **`13 429.4 (1)`** |

429.4 is exactly the sentinel's `seen: 429`.  The far half — the 27.1 cm partner
— never joins, and the muon is the 182.9 cm near half alone.

**And there is no reject line**, which localises it.  Doc 84 round 4 added
`long_muon_cathode_bridge: reject …` for every *geometrically reachable*
candidate precisely so a non-firing bridge could be diagnosed.  Silence means the
pair never became a candidate at all — it was filtered above the angle tests.

The `calib` dumps say which filter, and it is **not** a geometric one:

| | OFF | ON |
|---|---|---|
| shower list | `(4000, pdg 13, 210.0 cm)` + 4 tiny e⁻ | `(4000, pdg 13, **182.9 cm**)` + **`(8017, pdg 11, 18.9 cm)`** + **`(8018, pdg 11, 8.8 cm)`** + 3 tiny e⁻ |
| the far half | one 27.1 cm partner, **typed 211 (π⁺)** | two showers totalling ≈ 27.7 cm, **typed 11 (EM)** |
| bridged muon | 210.0 cm | 182.9 cm (near half only) |

The far half **is still reconstructed**.  What changed is its **PID**: 211 → 11.
And doc 84 round 4's partner filter refuses EM partners *on purpose*
(`TaggerCheckNeutrino.cxx:1418-1431`), naming this very event:

```cpp
// doc 84 round 4 (G2): a cathode-split muon's near-seam stub is often
// mis-PID'd -- 347890's far half is a |13| shower but its facing
// partner is a 27cm shower typed 211 (pi+) ... track_partner admits
// |211| as well.  EM (11/22) is NOT admitted and must not be:
// absorbing a genuine EM shower across the seam is the failure mode
// this guard exists for (392901's far half is a 106 MeV electron
// shower with comparably good geometry).
const int optype = std::abs(osh->get_particle_type());
const bool ok = (optype == 13) || (cfg.track_partner && optype == 211);
if (!ok) continue;
```

`continue` — before `collect_ends`, which is why nothing is logged.

**So the guard is doing exactly what it was built to do; its input changed.**
This is *not* a threshold that needs widening at the cathode seam (an earlier
draft of this section guessed the `xcut` pre-filter, and the dumps say
otherwise — the ends are unchanged at x = (106.91, 4.95) for the muon).  It is a
**PID flip on the far half of a cathode-split muon**, π⁺ → EM.

**That merges item 3a into item 5.**  Both are the same failure: a track-like
object typed EM after the frame correction (§15's 137238 is the same shape at a
larger scale).  Widening the bridge's partner filter to admit EM would defeat the
guard doc 84 round 4 shipped it for — 392901's far half really is a 106 MeV
electron.  **The fix belongs upstream, in the typing**, and doc 84's five
cathode-bridge sentinels are the negative control set for it: three still pass
(53793, 172794, 67026) plus 77978, so any change has to hold those.

### 14.2 177536 — the muon is not lost; it is split, and the split invents 105.7 MeV

| | OFF | ON |
|---|---|---|
| bridge log | `absorb bare chain into sid=1 nseg=1 len=98.8cm gap=9.4cm ends x=(-2.5,3.3)cm reseat=1` | **identical** (`len=98.7cm`, same gap, same ends, same reseat) |
| MCS chain | `nseg=2 npoints=654 len=391.2cm tracklen=398.5cm ke_range=902.5` | `nseg=2 npoints=632 len=378.3cm tracklen=398.2cm ke_range=901.7` |
| counted muons | **one, `13 908.6`** | **two, `13 276.0` + `13 644.3` = 920.3** |
| `kine_reco_add_energy` | 114.3 | **219.9** |
| `kine_reco_Enu` | 1222.4 | 1339.8 |

**The bridge fires identically and the muon's range is intact** — `tracklen`
398.5 → 398.2 cm, `ke_range` 902.5 → 901.7 MeV.  What changed is that the PF
tree renders that one muon as **two nodes**.  Total muon energy even rises
slightly, 908.6 → 920.3.  Nothing is lost.

But `kine_reco_add_energy` gains **105.6 MeV — one muon rest mass** — because
`rest_term_rules` is applied per counted node.  Splitting one muon into two nodes
therefore **double-counts its rest mass into `kine_reco_Enu`**, and that is the
whole of this event's +117 MeV.

**This is a defect independent of the T0 patch.**  Any reconstruction change that
splits a muon can inflate Enu by 105.658 MeV, silently
(`rest_term_rules`, `NeutrinoKinematics.cxx:102-111`: `pdg 13 → mass/MeV`).  It
is also the same term that supplies a third of §13's +298.

### 14.2.1 How often it happens — measured

Over the 1434 candidates carrying a `calib` dump on both arms, counting the
**split-muon signature** (more `pdg == 13` counted nodes on ON, with total muon
energy preserved to within 5 %):

| | |
|---|---|
| candidates showing the signature | **21 of 1434** |
| of those, paying a spurious rest mass | **6** |
| total spurious `kine_reco_add_energy` | **270.0 MeV** across the population |

    mcp2k    98844   nmu 1->2  Emu  174.2->  176.8  d_add= +139.6   <- Bee idx 10
    mcp1k   407280   nmu 4->5  Emu  907.6->  910.9  d_add= +105.7
    mcp1k    55595   nmu 1->2  Emu  470.6->  464.6  d_add= +105.7
    mcp2k   177536   nmu 1->2  Emu  908.6->  920.3  d_add= +105.7   <- Bee idx 6
    mcp2k    78743   nmu 2->3  Emu  305.9->  311.6  d_add= +105.7
    mcp2k    97260   nmu 1->2  Emu  820.2->  849.1  d_add= +105.7
    mcp1k   279256   nmu 1->3  Emu  677.8->  667.6  d_add=   +0.0
    ... (15 more at +0.0)

**The charge is conditional, which is itself the finding.**  Fifteen of the 21
splits pay nothing, because only two of the counting sites call
`rest_term_rules` (`:230`, `:274`); others add only `ave_binding_energy`.  So the
rest-mass term is charged **per counted node at some admission paths and not at
others** — the same physical muon is priced differently depending on which pool
admitted its second half.

In aggregate this is small (270 MeV over 1434 candidates) and it is **not** a
reason to hold the flip.  Per event it is material: 105.7 MeV on 177536 and
139.6 on 98844, the owner's own Bee rows 6 and 10.

**Recommended next step for item 3b:** decide whether `rest_term_rules` should be
charged per *particle* rather than per *node*, and make the charge uniform across
admission paths.  The 21-candidate list above is the working set and the
negative control is free — the OFF arm.

### 14.3 What to tell the owner

His reading of idx 6/7 as "the two cathode-bridge muons are lost" holds for
**347890** and not for **177536**:

- 347890 — real loss of the far half's 59 MeV, but **not** at a geometric filter:
  the ends are unchanged at x = (106.91, 4.95) and the bridge never sees the
  pair because the far half's **PID flips 211 → 11** and doc 84 r4's partner
  filter refuses EM by design (§14.1).  An earlier draft of this line said
  "bridge pre-filter at the cathode seam"; the calib dumps refuted it.
- 177536 — no loss at all; the muon is split in two and the *energy goes up* by a
  spurious rest mass.

Both are worth fixing, and neither is a reason to keep the biased frame.

---

## 15 Item 5 — what actually happens on 137238, and where the campaign should start

The owner's idx-8 reading is *"the hadronic shower made to an EM shower"*.  The
`kine` block says what that looks like in numbers, and it points somewhere more
specific than "PID is hard".

| | OFF | ON |
|---|---|---|
| `kine_reco_Enu` | 735.7 | **1161.2** |
| `kine_n_excluded` | **9** | **1** |
| `kine_energy_excluded_other` | **316.4 MeV** | **0.0 MeV** |
| main EM shower | `id 144056`, pdg 11, **354.3 MeV**, **102.7 cm** | `id 144050`, pdg 11, **555.3 MeV**, **142.9 cm** |
| counted muons | `13 / 88.1`, `13 / 60.0` | `13 / 212.2`, `13 / 63.3`, `13 / 60.3` |
| counted particles | 7 | 13 |
| `kine_reco_add_energy` | 211.3 | 211.3 (unchanged — no rest-mass double count here) |

**The exclusion pool empties.**  Nine excluded objects worth 316 MeV become one
worth nothing, and the main EM shower grows by 201 MeV and 40 cm.  That is not a
PID flip in the first instance — it is the **exclusion tournament**, the thing
this patch changes, ceasing to exclude anything on this event, after which the
shower-building stage sweeps the freed objects into the electron.

That reframes item 5's entry point.  The question to ask first is not "why is
this hadronic shower typed EM" but **"is `kine_n_excluded` 9 → 1 the right
answer here, and how often does the exclusion pool empty across the 3067?"** —
a population measurement on arms that already exist (`kine_n_excluded` and
`kine_energy_excluded_other` are columns in the score tables).  If the pool
empties broadly, the exclusion thresholds are the lever; if it is rare, this
event is a PID case after all.

Note also that the ON arm's muon list `[212.2, 63.3, 60.3]` is close to doc
127's measured **pre**-pr/127 state, `mu- [207, 88, 58]`, against production's
`[88, 60, 58]`.  The 207/212 body node returning is the specific thing pr/127's
`sccc_max_gap` 6 → 10 flip removed, so the sentinel is reporting something real
and named, not drift.

**Reading list the owner pointed at** (*"we have a lot of md files before that
can be used to do the tuning"*), in the order they help here: doc 127 (this
event's own doc), doc 93 (`electron-really-tracks-and-pi0`), doc 125 (fake-e →
tracks), doc 133 (π⁰ muon showers, the NC signature), doc 136 (the EM
charge-attribution charter) and doc 141, whose closing finding is that **PID,
not clustering, is the next front — ≥ 29 % of μ-typed objects are EM showers**.

Two traps already paid for, to carry into the round: a near-flat electron
template beats real muons at MIP, so the template comparison is usable as a
**proton veto** and not as a positive electron ID; and zero-charge fit points
corrupt dq/dx medians, so live points must be filtered before any template is
evaluated or a dead stretch will hand PID to the flattest candidate.

### 15.1 The census that decides it — run, and it says PID

The population comparison off `products/d144{off,on}/*.tsv`, 1434 evaluated
candidates carrying an excluded census on both arms:

| | OFF | ON |
|---|---|---|
| Σ `kine_n_excluded` | 3172 | 3124 (−1.5 %) |
| Σ excluded energy | 50 416 MeV | 48 223 MeV (−4.4 %) |
| candidates with an empty pool | 454 | 456 |
| `n_excluded` fell / rose / unchanged | — | 108 / 92 / **1234** |
| "pool empties" (≥ 5 excluded OFF → ≤ 1 ON) | — | **8 of 1434** |

    mcp2k   321235   n  6-> 1   E   765.0 ->   2.0 MeV
    mcp1k   345633   n  6-> 1   E   588.3 ->   1.6 MeV
    nuecc48 137238   n  9-> 1   E   428.9 -> 124.5 MeV
    mcp2k   100222   n  5-> 1   E   359.0 -> 135.0 MeV
    nuecc48 235435   n  5-> 0   E   147.4 ->   0.0 MeV
    ncpi0    56982   n  5-> 1   E   142.6 ->   1.3 MeV
    mcp2k   171528   n  5-> 1   E   101.6 ->   1.4 MeV
    mcp2k    91917   n  5-> 1   E    83.1 ->   2.3 MeV

**The exclusion pool does not empty broadly.**  Across the population it barely
moves — 1.5 % on the count, 4.4 % on the energy, two more empty pools out of 454
— and it falls on 108 candidates while rising on 92.  137238 sits in an
**8-event tail**, not in a systematic collapse.

So the first question is answered and it points the other way: **item 5 is a PID
/ shower-building round, not an exclusion-threshold round.**  The exclusion
tournament is arbitrating sensibly; on this handful of events it hands the
shower stage objects it did not hand it before, and the shower stage absorbs
them into an electron.  That is where the tuning belongs.

**Named next step:** take the 8-event tail above as the working set — it is
small enough to hand-scan and it is *selected by the mechanism*, not by the
outcome — and ask on each whether the objects the shower absorbed belong to the
electron.  137238 has a hand label already (doc 127).  Only then go to the
template work, with the two traps above in hand.

---

## 16 The sentinel re-baseline

Fourteen of the thirty pr/127 sentinels stopped holding (§7.1).  The doc 91 §12
discipline is not to move a threshold onto the new number — it is to **measure
both sides at the new pinned point** and assert the structural property the fix
shipped, with the threshold between them.  This round adds a step to that,
because the epoch changed twice over: it measures the full **2 × 2**.

### 16.1 The design, and proving the controls are causal

One negative-control arm per knob (`scripts/pr144_sentinel_neg.sh`), each
running its event with that fix's own knob off.  **Before believing any of them**,
every control's compiled config was diffed against production's for the same
event: each differs in **exactly the one intended key and nothing else**
(`sccc_max_gap` 10 → 6; the other seven key-suppressed to their C++ default).
A control that silently failed to disable anything would report "the fix is
inert" for free, which is the trap this check exists for.

Then the same nine events were run again in the **legacy** frame
(`docs/pr/pr144-legacyframe.tla`), giving all four cells on one binary
(`d144_libpin4`) and one cfg.  Both positive cells are anchored to the real
production arms: `work-s144posleg-mcp2k` is byte-identical to `work-mcp2k-d144off`
on 6/6, and `work-s144pos-mcp2k` to `work-mcp2k-d144on` on 6/6.

### 16.2 The result

| knob | event(s) | legacy frame | new frame | reading |
|---|---|---|---|---|
| `stem_backfill_back_dvtx` | 179369 | DIFF | **DIFF** | live in both |
| `sccc_max_gap` 10 → 6 | 137238 | DIFF | **DIFF** | live in both |
| `stem_backfill_back_guard` | 47212 | DIFF | **SAME** | inert at the new epoch |
| `shower_pass3_cone_guard_len` | 52693 | DIFF | **SAME** | inert |
| `shower_pass4_prox_guard_len` | 100222 | DIFF | **SAME** | inert |
| `shower_pass3_backfill_guard_len` | 175896 | DIFF | **SAME** | inert |
| `long_muon_members_geometry` | 281595 | DIFF | **SAME** | inert |
| `kine_guard_freed_impact` | 94392, 171572 | **SAME** | SAME | **already** inert |

**Five shipped fixes stopped biting on their own sentinel event when the drift
frame was corrected.**  Not "the fix died" — the event simply no longer
exercises the knob.  And one, `kine_guard_freed_impact`, was already inert on
both its events **before** this round, in both frames: pr/129's own footprint
note says as much ("exactly ONE event's `kine_reco_Enu` moves, 393505"), and this
2 × 2 is what exposed that those two entries never discriminated.

Note what this does **not** say.  A knob inert *on its sentinel event* is not a
knob inert everywhere — §13 shows `kine_guard_freed_impact` still doing real work
on 393505.  The claim is about the registry's coverage, not the knobs' value.

### 16.3 What was changed

| action | entries | why |
|---|---|---|
| **INERT** (new state) | 47212, 52693, 100222, 175896, 281595, 94392, 171572 | Reporting FAIL would say something false; re-baselining to PASS would be worse — green and unable to fail, the dead safety net doc pr/127 exists to prevent. They report `INERT` with the measurement attached. |
| **OPEN** (new state) | 137238, 177536, 347890, 393505 | They fail for a real, named reason (§§13–15). The suite must neither go green over them nor read them as unexplained. `OPEN` does not fail the run; a bare `FAIL` still does. |
| **re-expressed** | 72786 (`decline seg=9004` → `log_count_ge 'decline seg=' 4`), 66366 (`nseg_chain=4 L_cm=300.6` → `nseg_chain=`) | Both named something that is not a property of the reconstruction. The guard still declines the same four objects on 72786 — one id renumbered, 9004 → 9003 — and 66366's chain is still assembled, from 3 segments at 299.5 cm. |
| **re-baselined** | 179369 (`pf_absent 'pi0'` → `pf_absent 'pi0  112'`) | Measured on both sides: pr/130 B is **alive** and still removes its own π⁰ (112) plus the `e- 201` / `gamma 201` pair and `pi+ 54`. A *different* π⁰ at 130 MeV appears in the corrected frame — on the event the owner scanned and ruled better (Bee idx 0). |
| **new assertion kind** | `log_count_ge` | For guards whose log line names a segment id: ids renumber whenever the fit changes, the count does not. |

### 16.3.1 The suite on the new production arm

Run against the full `work-*-d144fixprod` (3067 events, the committed default on
the crash-fixed binary), no events skipped:

    19 PASS, 0 FAIL, 4 OPEN, 7 INERT, 0 SKIP        rc = 0

The four OPEN are exactly the events the owner flagged or that §§13–15 name as
open defects — 137238, 177536, 347890, 393505 — and nothing else is red.  The
three edited entries pass on assertions that still discriminate:

    PASS 72786   [ok] log_absent 'pr128 pf-orphan-near-cross-cluster'
                 [ok] log_count_ge 'pr130 pass4_prox_guard: decline seg=' want >= 4 (seen: 4)
    PASS 66366   [ok] pf_node_ge mu- 650 MeV (seen: 689)
                 [ok] log_contains 'nseg_chain='
    PASS 179369  [ok] pf_absent 'pi0  112' (46 PF nodes)
                 [ok] log_contains 'pr130 stem_backfill_back_dvtx: suppress decline seg=17002'

Before this round the same suite read **16 PASS / 14 FAIL** on the ON arm and
**30 PASS / 0 FAIL** on the OFF arm.  The 30/0 was not the healthier number: it
included the seven entries this 2 × 2 has now shown could not fail.

### 16.4 The consequence, stated once

Six shipped SBND-ON knobs — `stem_backfill_back_guard`,
`shower_pass3_cone_guard_len`, `shower_pass4_prox_guard_len`,
`shower_pass3_backfill_guard_len`, `long_muon_members_geometry` and
`kine_guard_freed_impact` — now have **no event in this registry that can catch
them dying**.  If one of them dies the way pr/93 r4 did, nothing here will see it.

The fix is to retarget each onto an event where it still bites.  That is a
population scan per knob: run the 3067 with the knob off, diff against
production, take any event that moves.  It is affordable — one arm per knob at
≈ 3.5 core-hours, or one combined arm with all six off to find the union of
affected events and then one small arm per knob to attribute — but it is six
arms of work and the owner **declined the same offer** in doc pr/130 ("re-targeting
each onto an event where its knob still bites was offered and DECLINED"), so it
is priced here rather than done unasked.

`./scripts/pr127_sentinels.py --all` re-evaluates the INERT entries, for whoever
takes that round.

---

## 17 The post-fix scan set, and why 11 of 12 pictures are unchanged

The owner asked for the 12 Bee events again "after the fix and upgrade".  Built
from `work-*-d144fixprod` — the committed default on the crash-fixed binary —
with the same 12 events in the same order plus **494297 appended at index 12**:

    FIXED  https://www.phy.bnl.gov/twister/bee/set/42a635f6-475b-4a17-9e5d-913fdb355bab/event/list/
    OFF    https://www.phy.bnl.gov/twister/bee/set/a6027cd7-14e8-43fa-a16a-d5b10fe166ba/event/list/
    ON     https://www.phy.bnl.gov/twister/bee/set/2455120d-016d-40bc-8b23-96e4db8c8f07/event/list/

**Indices 0–11 are byte-identical to the ON set already scanned** — member-content
hash of `mabc-pr.zip`, all 12 events, `work-*-d144on` vs `work-*-d144np2` and vs
`work-*-d144fixprod`.  Saying so is the point of this section: handing over a set
that looks identical without saying it invites a wasted scan.

Neither thing that landed since touches those pictures:

- the **crash fix** is byte-identical on 3066 of 3067 events and the exception is
  494297 itself (§6.5);
- **`kine_near_pointing_impact`** is default OFF, and even armed
  (`work-*-d144np2`, the 12 events + 494297 on the knob) it changes exactly one
  event, 393505, and only its `root` and `calib` — **the `mabc-pr.zip` is
  unchanged**.  The cosmic it removes from the ENERGY stays in the PF picture,
  which is what pr/123 r2 requires ("OK to be in PR").  So **item 4's fix is not
  scannable**; it is a number, and the number is §13.2.1's Enu 858.2 → 574.8.

**Index 12 is the only new content.**  494297 has no picture in either earlier
set — the crashed arm wrote a zero-byte `mabc-pr.zip` — so this is its first
reconstruction, and nothing has ever adjudicated it.

`docs/pr/pr144-bee-fixed.index.txt` carries the annotated index, and it repeats
per row what §§13–15 found, so the scan sheet stands alone.
