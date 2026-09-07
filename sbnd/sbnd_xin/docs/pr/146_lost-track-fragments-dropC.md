# doc sbnd_xin/pr/146 — track fragments lost from BOTH ledgers by the `drop:C` satellite arm

**Status 2026-09-06:** diagnosed, population measured, owner-scanned, fixed
behind a default-OFF knob, gated. **No production default is flipped in this
round** (CLAUDE.md §5.1); §12 carries the recommendation with the numbers.

---

## 0 Repro

The census (§5) needs **no new processing** — the classifier already logs every
decision into arms that were finished before this round began.

```bash
cd sbnd/sbnd_xin

# the population: 3000 numu events, read-only, ~20 s
scripts/pr146_sat_census.py --arm work-mcp1k-d145np --arm work-mcp2k-d145np \
    --tsv docs/pr/pr146-sat-census.tsv

# the two objects the owner named first
grep -h "kine_sat DROP" work-mcp2k-d145prod/pr_evt94392/wct_pr_evt94392.log
grep -h "kine_sat DROP" work-mcp2k-d145prod/pr_evt392009/wct_pr_evt392009.log

# the gate arms (41 events each; pin /home/xqian/tmp/d146_libpin2)
JOBS=16 PIN=/home/xqian/tmp/d146_libpin2 TAG=d146sv0  ./scripts/pr146_satarm.sh
JOBS=16 PIN=/home/xqian/tmp/d146_libpin2 TAG=d146sv25 \
    TLA=docs/pr/pr146-satkeep25.tla ./scripts/pr146_satarm.sh
for s in ncpi0 nuecc48 mcp1k mcp2k; do
  python3 scripts/analysis/pr143/pr143_compare_arms.py work-$s-d145prod work-$s-d146sv0
  python3 scripts/analysis/pr143/pr143_compare_arms.py work-$s-d146sv0 work-$s-d146sv25
done
```

**Log-file convention.** `wct_pr_evt<ID>.log` **only**. `stdout.log` beside it
carries byte-identical lines, so a `*.log` glob double-counts every drop — the
trap `pr145_pointing_census.py` documents. Both were checked: 70 drops, 8 arm-C,
either way.

Binary pins (M13, never reused): `d146_libpin_pre` = exact-HEAD baseline
(`aa03c8fc163c66fd13aeda999773f713`), `d146_libpin2` = the fix
(`be61345449fa764184c3679315937066`).

---

## 1 What the owner reported

> *"I saw these two cases `(x, y, z) = (-102.8, -11.6, 246.3)` cluster 4 in evt
> 94392, `(x, y, z) = (13.8, 131.3, 347.2)` cluster = 58014 in evt 392009, both
> of them are short track, which should be part of a long muon, but not included.
> The key issue is that they were totally lost from the PF and neutrino energy
> accounting."*

Identified **by coordinate** from `calib-pr-evt<ID>.json` `segments[].points[]`:

| coordinate | object | cluster | length | pdg | KE |
|---|---|---|---|---|---|
| `(-102.8, -11.6, 246.3)` evt **94392** | segment **45029** | PR 45 | 29.62 cm | 13 | **98.14 MeV** |
| `(13.8, 131.3, 347.2)` evt **392009** | segment **58014** | PR 58 | 23.67 cm | 211 | **59.35 MeV** |

**"cluster 4" is a display id**, not a PR cluster id — for 94392
`bee/pr129gf/pr129gf-base.prid-map.txt:29` maps img 4 → PR cluster 5, while the
named object lives in PR cluster 45. Every identification here is by coordinate.

Both are fragments of a longer object whose **neighbouring fragment is counted**:

- **94392** — 45029 (29.62 cm) shares vertex 45030 with **45030** (47.31 cm,
  138.25 MeV), counted via the guard-freed pool. Endpoint gap **0.00 cm**,
  kink **5.8°**. The near half of one 77 cm muon is dropped, the far half kept.
- **392009** — 58014 sits **3.32 cm** from the far end of main-cluster muon
  **6001** (225.82 cm) at **7.0°**, and shares vertex 58019 with **58015**
  (114.13 cm, 281.41 MeV), counted since the pr/145 pointing flip. ~377 cm of one
  muon in four pieces; two counted, two not.

---

## 2 The mechanism: `kine_drop_stray_satellites`, arm `drop:C`

Both are `Shower` objects with `start_connection_type = 2`, removed by the doc
pr/92 stray-satellite classifier (`clus/src/NeutrinoKinematics.cxx:467-570`):

```
94392   kine_sat DROP id=1 arm=drop:C E=98.1 conn=2 d_sv=16.3  ang_sv=4.5  in_main=true d_mv=16.3  ang_mv=4.5  cont=true track=true
392009  kine_sat DROP id=0 arm=drop:C E=59.4 conn=2 d_sv=221.6 ang_sv=14.8 in_main=true d_mv=226.9 ang_mv=6.5  cont=true track=true
```

**The drop record already carries the owner's discriminator** — the angle
(`ang_sv` to the attachment vertex, `ang_mv` to the main vertex), the distance
(`d_sv`, `d_mv`), a continuation flag and a track-likeness flag. It finds every
one of them favourable and drops the object anyway.

`NeutrinoKinematics.cxx:529-537`:

```cpp
if (track_like) {
    if (ang_sv > m_kine_sat_angle_bad)          { verdict = "drop:A"; break; }  // direction-aware
    if ((d_sv > m_kine_sat_far_dis || !in_main) &&
        ang_mv >= m_kine_sat_angle_main)        { verdict = "drop:B"; break; }  // direction-aware
    if (straight_cont)                          { verdict = "drop:C"; break; }  // NO direction test
}
else if (d_mv > m_kine_sat_em_far_dis &&
         ang_mv_fold >= m_kine_sat_angle_main)  { verdict = "drop:E"; break; }  // direction-aware
```

**Three of the four arms ask where the object points. Arm C does not.** It drops
a satellite purely for *being* a straight continuation of a known track — the
property that makes it a fragment of the candidate's own muon rather than a
stray.

`straight_cont` is `shower_start_is_track_continuation`
(`clus/src/PRShowerFunctions.cxx:189-230`): the shower's start segment has a
**same-cluster, non-shower sibling across a shared graph vertex** within
`m_kine_sat_cont_kink = 25°`, where the sibling or the two-segment chain is
straight-long. Arm C's own precondition is therefore already *"collinear with a
known track, at zero distance from it."*

Why the keep-guards missed these two: `d_sv < prox_max && in_main` exempts a
satellite within **8 cm** of its attachment vertex; 94392 sits at 16.3 cm and
392009 at 221.6 cm.

---

## 3 One cause, both ledgers — which is why the owner saw it in both

The kine side computes the drop set and **exports** it
(`NeutrinoKinematics.cxx:560-561`, out-param `dropped_satellites`); the PF tree
**consumes** it (`MultiAlgBlobClustering.cxx:1365` `sat_dropped`, applied `:1772`,
parent fallback `:1818`, `:1861`). The energy side reads the same set at `:585`.

The object's absence from the PF tree and from `kine_reco_Enu` are **not two
defects** — one decision, read twice. §9 confirms this empirically: every event
the fix moves gains a PF node *and* energy.

---

## 4 Two corrections doc 145 §3.8.2 owes

1. **The named gates are not the operative ones.** §3.8.2 attributed 58014's PF
   absence to `pf_orphan_guard_freed`'s `kPass4GuardFreed` predicate and its
   energy absence to `kine_near_min_len = 30 cm`. Both gates are real and both
   would reject 58014 — but **neither is reached**: the satellite dropper removes
   the shower at `:560`, and the leftover-shower loop, the guard-freed pool and
   the near-cross-cluster pool all run after it. (§10.3 shows `kine_near_min_len`
   *is* the operative gate — for two **different** objects.)
2. **58014's kinetic energy was never missing.** §3.8.2 says it *"is in no output
   at all, because nothing ever measured it."* It is **59.35 MeV**, in
   `showers[]` (`shower_id 0`, `id 58014`, `kine_best 59.35`) and in the log at
   `kine_hadronic: shower id=0 pdg=211 conn=2 nseg=2 ... best 103.4 -> 59.4 MeV`.

---

## 5 The population: 8 cases in the 3000 numu events, 727.7 MeV

`scripts/pr146_sat_census.py` over `work-{mcp1k,mcp2k}-d145np` — **3000 events,
70 drops**. Full table: `docs/pr/pr146-sat-census.tsv`.

| arm | n | Σ KE (MeV) | direction-aware? |
|---|---|---|---|
| `drop:A` | 18 | 4117.0 | yes (`ang_sv > 60°`) |
| `drop:B` | 10 | 2542.8 | yes (`ang_mv ≥ 45°` when far / not in main) |
| **`drop:C`** | **8** | **727.7** | **no** |
| `drop:E` | 34 | 1800.5 | yes (folded `ang_mv ≥ 45°`) |

`kine_best` is quoted throughout because that is the quantity the leftover-shower
loop pushes (`NeutrinoKinematics.cxx:598`); it agrees with the log's rounded `E=`
to 2 dp on all eight.

---

## 6 The owner's scan of all eight (2026-09-06)

All 8 were uploaded as one blind set — no angle, no arm label, no verdict on the
object being judged, and the two already-adjudicated events left unmarked as
calibration:

    https://www.phy.bnl.gov/twister/bee/set/5e3e9deb-43e9-4097-bb93-0de121575cbe/event/list/

and the same eight **after the fix**, in the **same index order** (idx N is the
same event in both, so the two step side by side):

    https://www.phy.bnl.gov/twister/bee/set/7c7e1168-2c0f-4126-a539-fb57aa8ddceb/event/list/

Sheets: `docs/pr/pr146-dropC-bee.index.txt` (blind),
`docs/pr/pr146-dropC.url` (both links + the per-index verdict and delta).
The verdicts, verbatim:

> *"Evt 54341 missing (76.5, 82.3, 169.0) cluster = 34015; Evt 74336 missing
> (-121.8, -57.6, 132.2) cluster 22002; Evt 94392 missing (-105.3, -19.8, 247.9)
> cluster 45029; Evt 170098 missing (-106.1, 126.1, 335.9) cluster 72030;
> Evt 320667 missing (-25.8, 78.6, 417.6) cluster 88040; Evt 392009 missing
> (11.5, 130.1, 350.4) cluster 58014; Evt 408534 missing (92.4, 109.9, 252.8)
> cluster 23012; Evt 321371 overclustering neutron 590 MeV"*
>
> *"as far as I can tell only 321371 has overclustering situation (neutron), for
> the rest, we should all count the energies."*
>
> *"The piece connected to that neutron is also not part of the neutrino in evt
> 321371"*

**7 of 8 are neutrino energy; 321371 is over-clustering.**

Resolving each coordinate against the calib dump — the objects he names are not
always the arm-C start segment, so this matters:

| evt | owner's coordinate → segment | is it the arm-C shower's? |
|---|---|---|
| 74336 | 22002 (103.85 cm, µ) | **yes**, the start segment |
| 94392 | 45029 (29.62 cm, µ) | **yes**, the start segment |
| 392009 | 58014 (23.67 cm, π) | **yes**, the start segment |
| 170098 | 72031 (3.23 cm, π) | yes — a *member* of shower 72030 |
| 320667 | 88040 (4.12 cm, e) | yes — a *member* of shower 88039 |
| 54341 | 34015 (16.38 cm, µ) | **no** — `shower_id = -1`, see §10.3 |
| 408534 | 23012 (25.57 cm, p) | **no** — `shower_id = -1`, see §10.3 |

So five of the seven "count it" objects are recovered by fixing arm C. The other
two are a **different** missing object in the same event; §10.3 names their gate.

---

## 7 The operating point — and the pre-registration that failed

Before the scan this doc pre-registered a waiver keyed on **`ang_mv`** (the angle
to the main vertex) at 45°, on the reasoning that the two then-known keeps sat at
4.5°/6.5° and the two events that *looked* over-clustered sat at 72.7°/107.8°.

**The scan refuted it.** 320667, at `ang_mv = 107.8°`, is one the owner says to
count; 321371, at 72.7°, is the one to refuse. `ang_mv` therefore puts the single
true refusal on the *good* side of the true keep — it does not separate.

Scored on the six events whose arm-C object the owner adjudicated directly:

| rule | correct | wrong |
|---|---|---|
| `ang_mv ≤ 45` (pre-registered) | 5/6 | 320667 |
| `ang_mv ≤ 90` | 4/6 | 320667, 321371 |
| `ang_mv ≤ 120` | 5/6 | 321371 |
| **`ang_sv ≤ 20`** | **6/6** | — |
| **`ang_sv ≤ 25`** | **6/6** | — |
| `ang_sv ≤ 30` | 5/6 | 321371 |
| `ang_sv ≤ 60` (= arm A today) | 5/6 | 321371 |

Sorted by `ang_sv`, the population separates cleanly:

| evt | verdict | KE | `d_sv` | **`ang_sv`** | `ang_mv` | start len |
|---|---|---|---|---|---|---|
| 320667 | keep | 35.64 | 18.7 | **2.1** | 107.8 | 2.88 |
| 408534 | keep (other obj) | 98.65 | 105.8 | **2.2** | 2.2 | 29.84 |
| 94392 | keep | 98.14 | 16.3 | **4.5** | 4.5 | 29.62 |
| 170098 | keep | 23.46 | 62.1 | **12.1** | 12.1 | 3.39 |
| 74336 | keep | 267.48 | 71.6 | **14.3** | 6.8 | 103.85 |
| 392009 | keep | 59.35 | 221.6 | **14.8** | 6.5 | 23.67 |
| 54341 | keep (other obj) | 46.92 | 96.7 | **19.6** | 20.1 | 2.63 |
| **321371** | **refuse** | 98.08 | 80.3 | **28.5** | 72.7 | 25.21 |

Keeps span 2.1 … 19.6°; the single refusal is 28.5°. **The gap is 8.9°.**

### 7.1 Why `ang_sv` and not `ang_mv` — the mechanism, after the fact

`ang_sv` is the angle between the satellite's own axis and the direction from its
attachment vertex to its start point: *does the piece continue in the direction
it attaches?* A fragment of a shattered track does; an over-clustered object
attached at a corner does not. The main-vertex angle fails because a genuine
fragment can sit far downstream of a curving parent and still be its own track —
320667 is exactly that.

This also makes the change coherent with the arm it sits next to: **`ang_sv` is
arm A's own variable**. Arm A drops a generic track-like satellite above 60°.
Arm C today drops a *continuation* unconditionally — an effective bar of 0°. The
fix gives a continuation a bar of **25°**: tighter than a generic satellite's 60,
looser than today's 0.

**The honest status is that 25° is fitted, not predicted** — n = 6 adjudicated
with exactly one refusal, and the threshold was chosen after seeing the labels.
Two things reduce the arbitrariness but do not remove it: 25 is not a new number
(it is `m_kine_sat_cont_kink`, already in this classifier), and any value in
(19.6, 28.5] scores the same. A **second refusal-class event** would be worth
more than any further tuning on these eight.

### 7.2 The deeper rule `ang_sv` is standing in for

321371's arm-C object (18009, 25.21 cm) is a straight continuation of **18006**,
a 255.8 cm muon that the pass-4 proximity guard declined and that
`kine_guard_freed_impact` then **refused** (`impact_cm=35.90 miss_deg=30.0 ->
SKIP`). It continues a track the reconstruction had already thrown out. In all
seven keeps, the partner is a track the reconstruction keeps.

So the *correct* predicate is **"is the continuation partner counted?"** — and it
is **not implementable at this site**: the classifier runs at `:467-570`, before
the guard-freed pool (`:793`) and the near-cross-cluster pool (`:872`), so no
partner's fate is known when the verdict is taken. `ang_sv` is the available
proxy, and §7.1's mechanism is why the proxy tracks the truth. Making the real
rule available means moving the classifier after the admission pools — a larger
change, recorded here and not attempted.

---

## 8 The fix

New knob **`kine_sat_cont_keep_deg`** (double, degrees, **C++ default `0.0` =
off**), armed with the `> 0` idiom already used by `kine_near_pointing_impact`:

```cpp
if (straight_cont) {
    // doc sbnd_xin/pr/146: arm C drops a satellite for BEING a straight
    // continuation of a known track.  ... Waive C when the axis still runs
    // along the ATTACHMENT direction ... 0 => no waiver => byte-identical.
    if (!(m_kine_sat_cont_keep_deg > 0 &&
          ang_sv <= m_kine_sat_cont_keep_deg)) {
        verdict = "drop:C"; break;
    }
}
```

Touched: `clus/src/NeutrinoKinematics.cxx`,
`clus/inc/WireCellClus/{TaggerCheckNeutrino,NeutrinoPatternBase}.h`,
`clus/src/TaggerCheckNeutrino.cxx` (configure / default_configuration / the
unscaled angle copy at `:2631`), `clus/test/doctest_clus_knob_defaults.cxx`,
and **SBND only** `cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet`
(key-suppression idiom; `null` ⇒ key omitted ⇒ C++ default).

**Rejected: raising `kine_sat_prox_max`** (8 cm; 94392 is at 16.3). A production
default flip, useless for 392009 at 221.6 cm, and not direction-aware.

---

## 9 The gate

Manifest: the 8 arm-C events ∪ the 30-event pr127 sentinel registry = 41 events.
Arms `d146sv0` (no TLA) and `d146sv25` (`docs/pr/pr146-satkeep25.tla`, via
`--tla-code`; an `-A` passes a **string** and silently defeats key suppression).

**M1 freshness** — `local/lib/libWireCellClus.so` 18:10:55 vs last edit 18:10:09.
**Unit tests** — `./build/clus/wcdoctest-clus` 328 cases / 23098 assertions, 0
failed, with the new default asserted at 0.0.

**M6 compiled-config proof** (node 21, `TaggerCheckNeutrino:pr`):

| config | keys at node 21 | `kine_sat_cont_keep_deg` |
|---|---|---|
| `d145prod` (pre-fix committed default) | 251 | absent |
| `d146sv0` (post-fix, no TLA) | 251 | **absent** |
| `d146sv25` (post-fix, armed) | 252 | **= 25** |

A full leaf diff of the pre-fix and post-fix **off** configs on evt 94392 shows
**5 differing leaves, all output-path renames** — the fix adds no key and changes
no value when off.

**Knob-off byte identity** — `d146sv0` vs `work-*-d145prod`, all 35 common
events: `tsv/root/zip/tar/calib` **SAME** on every one (member-content hashes via
`pr143_compare_arms.py`; never `cmp`/`md5sum` on archives — M2). The whole-arm
`nusel-*.tsv` report DIFF because the new manifest has 6 extra events; compared
row-by-row on the 64 shared rows with whitespace normalised, **0 differ**.

**Knob-on effect** — `d146sv25` vs `d146sv0`, 41 events:

| evt | owner | Enu off | Enu on | Δ | new PF nodes |
|---|---|---|---|---|---|
| 74336 | keep | 426.4 | 693.9 | **+267.48** | `neutron 267 MeV` → `mu- 267 MeV` |
| 408534 | keep (other obj) | 591.1 | 689.8 | **+98.65** | `neutron 98 MeV` → `mu- 98 MeV` |
| 94392 | keep | 1040.2 | 1138.4 | **+98.14** | `neutron 98 MeV` → `mu- 98 MeV` |
| 392009 | keep | 1391.0 | 1450.3 | **+59.35** | `neutron 59 MeV` → `pi+ 59 MeV` |
| 54341 | keep (other obj) | 789.6 | 836.5 | **+46.92** | `gamma 46 MeV` → `e- 46 MeV` |
| 320667 | keep | 652.0 | 687.6 | **+35.64** | `gamma 35 MeV` → `e- 35 MeV` |
| 170098 | keep | 809.7 | 833.1 | **+23.46** | `neutron 23 MeV` → `proton 23 MeV` |
| **321371** | **refuse** | 757.0 | 757.0 | **+0.00** | **(none)** |
| | | | **total** | **+629.63** | |

- **Exactly the 7 the owner says to count move; the 1 he calls over-clustering
  does not.** No other event in the 41 moves on any class.
- **Every mover gains a PF node as well as energy** — §3's single-cause claim,
  confirmed rather than asserted.
- **0 selection-label churn**: `nusel-table.tsv` and `nusel-events.tsv` SAME on
  all four samples.
- The candidate pool is untouched: `kine_sat census: candidates=N` is identical
  in both arms on all 8; only `dropped=` moves 1 → 0.

**Sentinels** — `20 PASS / 0 FAIL / 3 OPEN / 7 INERT` on **both** arms, identical
to the pr/145 baseline. 94392's pr/129 clause asserts
`enu_between(1136.0, 1149.0)`; the fix takes 94392 from 1040.2 to **1138.4**,
inside that window — but the sentinel is short-circuited to INERT for an
unrelated reason (`kine_guard_freed_impact` is byte-identical on/off there), so
it does **not** flip to PASS. The window check is a measurement, not a sentinel
transition, and is reported as such.

**Cross-detector knob-off.** `NeutrinoKinematics` binds on PDVD and PDHD, and —
correcting an assumption made while planning this round — **both arm the
classifier**: `wcp-porting-img/{pdvd,pdhd}/wct-pr-perevt.jsonnet:1924/:1944` set
`kine_drop_stray_satellites = true` (the toolkit-side `pr.jsonnet` files mention
it only in comments). The code path is therefore live on both, and the gate is
substantive, not formal. Baseline `d146_libpin_pre` is an **exact-HEAD** build;
one event each, `-nu-legacy` (the mode that binds TaggerCheckNeutrino):

| | `mabc-pr.zip` members | `calib` | ROOT trees |
|---|---|---|---|
| PDVD 039252/0 evt 298567 | SAME | SAME | 7 SAME, `T_proj_data` DIFF |
| PDHD 029107/0 evt 983 | SAME | n/a | 7 SAME, `T_proj_data` DIFF |

`T_proj_data` is **not attributable to this change**: re-running each detector a
second time under the *same* baseline pin reproduces the identical 7-SAME /
`T_proj_data`-DIFF split (§10.2). uBooNE binds no `TaggerCheckNeutrino` config
and is unaffected.

---

## 10 Reported, not fixed

### 10.1 PF draws a 590 MeV object that Enu already refuses (321371)
The owner's *"overclustering neutron 590 MeV"* is **not** the arm-C object. It is
seg 18006, a 255.8 cm muon declined by the pass-4 proximity guard, which
`kine_guard_freed_impact` then **refused** (`impact_cm=35.90 miss_deg=30.0 ->
SKIP`) — so its energy is *already* outside `Enu` (757.0, with 803.5 MeV
excluded). It reaches the picture through `pf_orphan_guard_freed`
(`MultiAlgBlobClustering.cxx:2576-2634`), which **has no pointing test**. Since
pr/129 and pr/144 shipped the two kine-side pointing tests, **kine can refuse an
object PF still draws**, and 321371 is a live instance. The fix is a PF-side
pointing test mirroring the kine one; it is its own round.

### 10.2 `T_proj_data` is not run-to-run reproducible on PDVD or PDHD
Two runs of the *same* pinned binary on the same input give identical
`mabc-pr.zip` members and 7 identical ROOT trees, and a different `T_proj_data`
every time, on both detectors. This is an M4-family determinism defect that
predates this round. It also means any future gate on these detectors must
exclude `T_proj_data` or fix it first. Not investigated here.

### 10.3 A second missing object in 54341 and 408534 — and `kine_near_min_len` is its gate
The objects the owner named in these two events are **not** in the arm-C shower:

| evt | owner's segment | length | pdg | `shower_id` | graph neighbours |
|---|---|---|---|---|---|
| 54341 | 34015 | 16.38 cm | 13 | −1 | 34014 (the arm-C start), 34016 |
| 408534 | 23012 | 25.57 cm | 2212 | −1 | 23011 (the arm-C start) |

Each is a graph neighbour of the arm-C start segment, in a non-main cluster and
in no shower, so no shower-level decision reaches it. The pool that *should* take
it is the near-cross-cluster one — and both fail
`segment_near_candidate_track(seg, m_kine_near_min_len)` on length alone:
16.38 and 25.57 cm against a **30 cm** floor. So doc 145 §3.8.2's
`kine_near_min_len` finding was right about the gate and wrong about the object.
Lowering that floor is a production default change (§5.1) and a round of its own;
the numbers are here so it can be priced.

### 10.4 Upstream
Both of the owner's first two objects exist because one muon was shattered by
signal-processing failure and the cathode plane (doc 145 §3.8.3). Counting the
pieces is right; not shattering them is the real repair, upstream in SP and
cathode-crossing reconstruction.

---

## 11 Honest limits

- **25° is fitted.** n = 6 adjudicated arm-C objects with exactly **one**
  refusal, threshold chosen after the labels. Any value in (19.6, 28.5] is
  equivalent. What is *not* fitted is §7.1's mechanism and §7.2's finding that
  the one refusal is the one whose continuation partner the reconstruction had
  already thrown away.
- **My own pre-registration was wrong** (§7). `ang_mv ≤ 45` scored 5/6; the scan
  is what corrected it. The record is kept rather than rewritten.
- **The class is not homogeneous.** Start segments span 2.63 cm to 103.85 cm, and
  two of the seven keeps are EM-typed showers recovered as `gamma → e-`. The rule
  does not distinguish a 104 cm muon fragment from a 2.6 cm EM stub.
- **The census denominator is events with a main vertex.** 70 drops over 3000
  events; the classifier does not run where no neutrino candidate is selected.

---

## 12 Recommendation

Ship `kine_sat_cont_keep_deg = 25` as the SBND production default. It is the
owner's own discriminator, it reproduces his 8-object scan exactly (7 counted,
1 refused), it costs **+629.63 MeV** across 3000 numu events on 7 events, it
moves no other event on any class, it changes no selection label, and it is
byte-identical when off on SBND, PDVD and PDHD.

Two things are worth doing before or alongside that flip, both named above:
**§10.1** (PF draws what Enu refuses — the same 321371 event the owner flagged)
and **§10.3** (the 30 cm `kine_near_min_len` floor, which is what still hides the
objects he pointed at in 54341 and 408534).
