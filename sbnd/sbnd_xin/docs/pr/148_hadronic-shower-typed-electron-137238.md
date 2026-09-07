# doc sbnd_xin/pr/148 — evt 137238: the tag that was supposed to fix it is right about half the time, and its energy effect is not the one it was designed for

**Status: BOTH SCANS DONE — 24/24 and 12/12, 2026-09-06, 36 labels.
THE ROUND INVERTED, THEN THE FIX WAS REFUTED BY THE SECOND SCAN.
No knob is proposed. §12 is what was measured; §13 is the recommendation.**

The round was chartered to recover 137238's 555 MeV object from EM to hadronic.
Scan 0 (§6.1) called that object **EM** and found the opposite defect —
`shower_hadronic_tag` re-typing real EM cascades. §8 designed a segment-count
guard for that. **Scan 2 (§11.3) labelled the guard's entire cut set and
refuted it**: 5 EM / 2 HADRONIC, Fisher *p* = 0.37. §8 is kept, marked refuted.

What survives is a measurement and two findings the owner can act on:

- on **18 labelled re-types** the tag is right **8 times** — 44 %, 95 % Wilson CI
  **[0.25, 0.66]**. **Fifty percent is inside that interval**, so the data cannot
  distinguish harmful from neutral, and ~100+ labels would be needed to try.
  **The precision question is closed as unanswerable at achievable scan cost.**
- **A5's effect on `Enu` is 11 : 1 rest-mass over estimator** (§12.2) — the
  estimator is the only thing it was designed to change.
- **A5 has drifted off its own calibration** (§12.3): 395148, the sole design
  object of the proton-stem branch, no longer fires it. No code changed, no default flipped.

The round was chartered to recover 137238's 555 MeV object from EM to hadronic.
**The owner's own blind scan calls it EM** — and calls every one of the twelve
suspects EM or MIXED. What the scan did find is the opposite defect: of the six
already-re-typed control objects, **three are EM**, i.e. `shower_hadronic_tag`
is firing on real electron showers in production today. §8 designs the guard
for that. §6.1 has the verdicts; §6.2 is the question this leaves for the
owner.

*Numbered 148, not 147: a concurrent session claimed `docs/pr/147_cathode/` and
`scripts/pr147_cathode_*.py` while this round was being written. 147 was free
when this round started and is not free now; taking 148 is cheaper than a
collision in the numbered record.*

Owner, 2026-09-06: *"Now we can deal with Evt 137238 hadronic shower misided as
Electron Shower issue. 1. You want me to scan something? 2. We must have deal
with this evnet in the past (search the md file please), you may find other
similar cases 3. We should try to use the similar idea as we did before to
recover this from an EM shower to an hadronic shower."* And, later in the same
round: *"For this scan, you should build a display like stm_display one, with
X-Y, Y-Z, Z-X projection view, and then ask me to put in the answer. Please use
port 5017."*

Answers, in order: **yes — §6, 24 objects, scanned; §7 is the display**;
**§1 — this is the owner's own item 5, open since doc pr/144 §8**; **§2 — the
idea is A5 `shower_hadronic_tag` (doc pr/99 round 3), §4 is why it does not
fire here, and §6.1 is why that turns out not to be the defect.**

§§1-5 are the diagnosis as it stood before the scan and are left as written;
they are still the answer to *why* A5 does not fire on 137238, which remains
correct and remains useful. §5.5 says what the scan later did to their
premise.

---

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin

# The census.  READ-ONLY over the finished 3067-event production arms -- the
# A5 tag already logs one line per evaluated shower, so this costs no
# reprocessing at all.
./scripts/pr148_a5_census.py \
    --arm work-mcp1k-d145np --arm work-mcp2k-d145np \
    --arm work-nuecc48-d145np --arm work-ncpi0-d145np \
    --tsv docs/pr/pr148-a5-census.tsv
#   -> A5 census: 313 shower(s) in 259 event(s); 68 re-typed; 300 joined to a dump

# The one object, bin by bin (sec 4.1, 4.2)
./scripts/pr148_profile.py --arm work-nuecc48-d145np --event 137238 \
    --shower 0 --body 51

# The blind sheet + its key (sec 6)
./scripts/pr148_pidset.py --census docs/pr/pr148-a5-census.tsv \
    --sheet docs/pr/pr148-pidscan-manifest.tsv \
    --key   docs/pr/pr148-pidscan.KEY.tsv

# The scan, once it is labelled (sec 6.1, sec 8) -- reproduces every table
./scripts/pr148_score_scan.py
#   -> EM 19  MIXED 2  HADRONIC 3;  guard at nseg>10 declines 7, dEnu -790.5 MeV

# Both scans pooled -- reproduces every table in sec 12
./scripts/pr148_scan_combined.py
#   -> 18 labelled re-types, precision 0.444 CI [0.25,0.66]; sec 8 bar Fisher
#      p=0.367 REFUTED; rest-mass:estimator 11:1; 395148 no longer fires

# Scan 2 -- the 12-object sheet (sec 11)
./scripts/pr148_pidset2.py --census docs/pr/pr148-a5-census.tsv \
    --labelled docs/pr/pr148-pidscan.KEY.tsv \
    --sheet docs/pr/pr148-pidscan2-manifest.tsv \
    --key   docs/pr/pr148-pidscan2.KEY.tsv

# The display (sec 7)
/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/python \
    pr148_scan/selftest_pr148_scan.py --expect 12      # rc 0 or do not serve
./pr148_scan/serve_pr148_scan.sh 5017 --scan-tag scan1 \
    --sheet docs/pr/pr148-pidscan2-manifest.tsv
#   ssh -o ServerAliveInterval=30 -L 5017:localhost:5017 <user>@wcgpu1.phy.bnl.gov
#   http://localhost:5017/pr148_scan_viewer
#   labels land in work/pr148_scan_labels/<tag>/; the committed copy of the
#   2026-09-06 pass is docs/pr/pr148-pidscan-verdicts.tsv

# The raw log line this doc is built on
grep "A5 hadronic" work-nuecc48-d145np/pr_evt137238/wct_pr_evt137238.log
```

Arms: `work-{mcp1k,mcp2k,nuecc48,ncpi0}-d145np` = 1000 + 2000 + 48 + 19 = 3067
events at the doc-145 production point. Displays read the same arm.

---

## 1. This event's history — it is item 5, and it has been open since doc 144

Searched, as asked. 137238 appears in eleven docs. The chain that matters:

| doc | what it said about 137238 |
|---|---|
| pr/36 §11.4 | first appearance — a FiducialUtils containment bug; `nue_score` +0.007 → −1.063 |
| pr/67 §3.1 | the owner's *"why is the fitted track trajectory missing this piece"* — answered: *"the charge at that point IS associated to segment 143061, and every associated point carries q = 15000. That is the shower marker."* **The chain has been calling part of this event a shower since August.** |
| pr/74 r1 | on the **shape B** roster — *"`e-` PF node ≥50 cm, transverse RMS <3 cm — a pencil, i.e. a track"* |
| pr/93 §7 | owner: *"the 152 MeV electron is actually a muon … it is really long, so clearly a muon."* Fixed by `straight_cont_cross_cluster` + `sccc_bridge_body` |
| pr/127 | that fix **died silently for ~10 days** when the geometry moved; restored by `sccc_max_gap` 6 → 10. The sentinel registry is created in this doc with 137238 as entry 1 |
| doc 91 §12.3 | re-baselined and the assertion **inverted** to `pf_node_lt mu- 150`, after the owner scanned production and said it was good |
| **pr/144 §8** | the owner's 12-event scan, idx 8: **_"the hadronic shower made to an EM shower"_**. `Enu` 736 → 1161 |
| pr/144 §15.1 | the census says the cause is **PID, not the exclusion threshold** |
| pr/145 §5 | round 1 of that PID item — **reported as a miss** |
| pr/146 §9 | carried unchanged; 137238 is one of `20 PASS / 0 FAIL / 3 OPEN / 7 INERT` |

`scripts/pr127_sentinels.py`, `KNOWN_OPEN_D144`, on disk today:

```python
    (137238, "pr/93 r4 + pr/127"):
        "doc 144 sec 15 -- the exclusion pool empties (n_excluded 9 -> 1) and the EM "
        "shower absorbs it; item 5, a PID round",
```

So this round is item 5, attempt 2. Nothing below re-opens the pr/93 r4 /
pr/127 fix, which is alive in this event and unaffected — §9.2.

## 1.1 The similar cases already have a name

The owner asked for the *same idea as before*. It exists and it is
**A5 = `shower_hadronic_tag`**, doc pr/99 round 3, shipped SBND-ON 2026-08-20
for exactly this complaint — the owner's words then were *"many of the hadronic
shower, or particle flow are still labeled as electrons."*

It re-types a conn-1 |pdg|=11 shower to **pdg 211**, stamps mass and 4-momentum
on the start segment, and calls `apply_hadronic_dqdx_best` so the energy
estimator follows the new type
(`clus/src/NeutrinoShowerClustering.cxx:9955-9975`). SBND operating point
(`cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet:2255-2264`):
`tag = true`, `growth_max = 0.7`, `stem_ratio = 2.8`, everything else at the
C++ default (`min_len 10 / scan_len 30 / bin 3 / r_cyl 8 / r_core 1.2 /
growth_bragg 1.2 / bragg_ratio 3.0`).

**The finding of this round is that A5 already runs on 137238, evaluates it,
and votes EM.** This is not a gap in coverage. It is three separable failures
of the discriminants themselves.

---

## 2. The object

`work-nuecc48-d145np/pr_evt137238/calib-pr-evt137238.json`, `showers[]`
`shower_id = 0`:

| field | value |
|---|---|
| `id` (start segment) | **144050** |
| `particle_id` | **11** |
| `kine_best` = `kine_charge` | **555.35 MeV** |
| `kine_dQdx` | 478.38 MeV |
| `kine_range` | 0.0 |
| `num_segments` | 20 |
| `total_length` | 142.85 cm |
| `start_connection_type` | **1** (at the main vertex) |

Event: `kine_reco_Enu = 1161.2 MeV`, `nue_score = −4.312`,
`numu_score = −0.261`. The object is **48 % of the event's neutrino energy.**

### 2.1 It is EM for exactly one reason

Its start segment 144050 is 26.97 cm long and carries `particle_id = 11` with
`flag_shower = false` — **neither** `kShowerTrajectory` **nor**
`kShowerTopology` is set on it. `PRShower.cxx:1619-1621` makes the shower's
`flag_shower` the disjunction

```cpp
bool flag_shower = m_start_segment->flags_any(SegmentFlags::kShowerTrajectory) ||
                 m_start_segment->flags_any(SegmentFlags::kShowerTopology) ||
                 (m_start_segment->has_particle_info() && std::abs(...pdg()) == 11);
```

so with both flags clear, **the pdg field alone types a 555 MeV object EM**,
and with it the energy estimator, the recombination pair and the rest-mass
term (§5).

And that pdg cannot have come from the PID. `segment_do_track_pid` only ever
proposes the electron hypothesis below 20 cm —
`clus/src/PRSegmentFunctions.cxx:2743` and `:2755`:

```cpp
if (result_forward.at(3) < min_forward_val && length < 20*units::cm) {
    forward_particle_type = 11; // electron
}
```

144050 is 26.97 cm. **Its pdg 11 was written by a reclassification site, not
measured.** Its `particle_score` is 0.20, which those sites do not overwrite.
§5.2 tests whether that pair of facts is a usable discriminator. It is not.

---

## 3. What the object physically is

Member segments, distance from the main vertex, median dQ/dx normalised by
`mip_dqdx_median = 48000` (§5.3 on why not 43000):

| seg | cluster | len cm | d start → end | MIP | |
|---|---|---|---|---|---|
| **144050** | 144 | 26.97 | 25.0 → **0.0** | 1.53 | the stem, running into the main vertex |
| 144041 | 144 | 19.75 | 24.6 → 43.3 | 1.17 | |
| 144048 | 144 | 18.82 | 27.7 → 38.0 | 0.95 | |
| **144051** | 144 | 12.67 | 27.7 → 25.0 | **2.30** | short, heavily ionising |
| **144054** | 144 | 5.74 | 27.7 → 32.7 | **2.96** | short, heavily ionising |
| 146065/146066/146067 | **146** | 12.1 / 16.4 / 11.0 | 72 → 99 | 1.96/1.05/1.05 | **a detached blob 70+ cm away** |
| 11 more | 38-51 | ≤ 4.4 each | 16 → 108 | | crumbs |

Not a member, at the same place: **144049**, 11.45 cm, **pdg 2212**, 1.85 MIP,
d = 25.0 → 18.1.

The topology is: **main vertex → a 27 cm single MIP-ish stem → a star of short
prongs at 25-32 cm**, two of which are 2.3 and 3.0 MIP, with a proton-typed
neighbour at the same place — plus a detached blob at 72-108 cm that the shower
has absorbed.

That reads as a charged hadron that travelled 27 cm from the neutrino vertex
and interacted. It is what the owner called it.

---

## 4. Why A5 votes EM — three failures, three distinct causes

The production log, verbatim
(`work-nuecc48-d145np/pr_evt137238/wct_pr_evt137238.log`):

```
A5 hadronic census: shower id=0 pdg=11 conn=1 nseg=14 smax=99.3cm growth=7.13
  n_early=644 n_late=2097 dqdx_trunk=5922 dqdx_term=5035 bragg=0.85 stem=1.54 verdict=0
```

against `NeutrinoShowerClustering.cxx:9942-9948`:

```cpp
const bool verdict = has_growth
    && (growth < m_shower_hadronic_growth_max                       // 7.13 vs 0.7
        || (bragg >= m_shower_hadronic_bragg_ratio                  // 0.85 vs 3.0
            && growth < m_shower_hadronic_growth_bragg)
        || (m_shower_hadronic_stem_ratio > 0
            && stem_med >= m_shower_hadronic_stem_ratio             // 1.54 vs 2.8
            && growth < m_shower_hadronic_growth_bragg));
```

### 4.1 `growth 7.13` — the ends-ratio is blind to WHERE the growth happens

`growth` is the mean of the last two bins over the mean of the first two, over a
30 cm window (`:9877-9886`). The profile
(`scripts/pr148_profile.py --event 137238 --shower 0`), member multiplicity per
3 cm bin:

```
  bin (cm)   npts  nseg  med dQ/dx
    0-3         6     1      72259      <- one segment, 5-7 points, for 24 cm
    3-6         5     1      73269
    6-9         5     1      62970
    9-12        5     1      83741
   12-15        5     1      78104
   15-18        7     2      66462
   18-21        7     1      59222
   21-24        6     1      33506
   24-27       31     4      91527      <- the star, in the LAST TWO BINS of
   27-30       30     5      43022         A5's 30 cm window
   30-33       16     3      57867      <- and then it falls away
   33-36       11     2      51652
   ...
```

The interaction lands exactly in the numerator of the ends-ratio. A5 reads a
5-6× rise and calls it a developing cascade.

**This is not a near miss.** pr/99 §3 calibrated the bar so that all 36
νe-selected primaries read ≥ 2.32 and the mis-ID'd hadrons ≤ 0.7. 137238 reads
**7.13** — further into the electron population than most real electrons. A
threshold move cannot reach it; only a variable that sees SHAPE can.

Stated as a limit: a real 500 MeV electron shower also peaks near 24 cm
(≈ 1.75 X₀ in LAr) and falls after, so *"the population falls past the bloom"*
does **not** separate. What is distinctive here is the flatness before it —
eight bins at one segment — and that is a statement about multiplicity, not
about the ratio A5 computes.

### 4.2 `bragg 0.85` — measured on objects this shower absorbed

`nbins_full` runs over `smax = 99.3 cm` (`:9891`), and `dqdx_term` is the max of
the **last two bins** of that range (`:9910-9918`). Those bins are at 93-99 cm —
members of clusters 146, 42 and 45, more than 70 cm past this object's own
contiguous body, which ends near 51 cm (see the gap at 51-54 cm in the profile).

**The Bragg branch was never given this object's own terminus to look at.**

**This is a defect independent of 137238's verdict** and it is worth its own
line: any absorbed far fragment silently redefines where "the end" is for every
shower A5 evaluates.

Priced, so nobody mistakes it for the fix:

```
Bragg over the FULL window:              trunk 57867  term 23764  ratio 0.41
Bragg with the window cut at 51 cm:      trunk 62970  term 39035  ratio 0.62
```

0.62 is still nowhere near the 3.0 bar. **Fixing the window does not rescue
137238.** It should be fixed anyway, on its own merits, in its own round.

### 4.3 `stem 1.54` — the proton branch is for protons

`shower_hadronic_stem_ratio = 2.8` was calibrated on 395148, a proton stem at
~3 MIP, with pair-conversion gammas at ~2 MIP as the adverse control (pr/99 §3).
137238's stem is 1.54 MIP — MIP-like, consistent with a charged pion or muon,
and correctly below a proton bar. This branch is not wrong; it is answering a
different question.

---

## 5. The population, and three candidate discriminants — two dead, then all three

### 5.1 The population is free

The A5 census line is emitted for **every evaluated shower**, which the design
note calls *"the offline calibration channel"*
(`clus/inc/WireCellClus/NeutrinoPatternBase.h:2054-2055`). Over the 3067-event
production arms:

| | |
|---|---|
| conn-1 \|11\| showers evaluated | **313**, in 259 events |
| re-typed to 211 by A5 | **68** |
| joined to a calib dump (all 259 events have one) | 300 |

`docs/pr/pr148-a5-census.tsv`. **No reprocessing was needed for any number in
this doc.**

Control set for everything below: the **62** censused showers in events the νe
BDT selects (`nue_score ≥ 3`) — the same proxy pr/99 used for its 36 protected
primaries. Its circularity is stated in §10.

**And it is scored at the resolution pr/99 used, not one coarser.** pr/99 §5
found *"11 nuecc48 satellite hadrons in nue events — none a selected primary"*:
a νe event legitimately contains hadronic satellites that A5 should re-type,
so firing on *a* shower in a selected event is not automatically a false
positive. Only firing on the event's **primary** — its highest-energy censused
shower — is. Of the 62 controls, **47** are their event's primary. Both counts
are given below.

### 5.2 Candidate 1 — the single-segment stem run. DEAD.

*Hypothesis:* a hadronic object has a long single-prong stem before its
interaction; an EM cascade develops from the vertex.

*Measured:* 137238's run is **15 cm** (the multiplicity is 1 in every bin from 0
to 24 cm except 15-18). νe-selected primaries run **3-33 cm** — 256587 at 18,
214469 at 27, 90055 at 33. Median identical between kept and re-typed
(12 cm both).

**Dead. No cut on this variable contains 137238 and excludes real electrons.**

### 5.3 Candidate 2 — a confident non-electron PID above 20 cm. DEAD.

*Hypothesis:* §2.1's pair of facts is a discriminator. The tree already
believes it: `segment_bragg_spares_electron_reclass`
(`clus/src/PRSegmentFunctions.cxx:1612`) is exactly `length > 20 cm &&
particle_score < 1.0`, with the header reasoning *"above 20 cm that PID's own
template competition never considers electron, so a real good score there is
unambiguous muon-or-proton evidence."*

*Measured over the 300:* the predicate fires on **27** showers — and on **15 of
the 62 νe-selected controls**, of which **15 of 15 are their event's primary**,
including `nue_score` 11.93 (214469, 1699 MeV), 12.46 (172230), 12.86 (246579)
and 14.06 (489330). Not a satellite among them. Of the 39 controls whose start
segment is over 20 cm, **15 carry a score below 1.0** (0.11 … 0.45); the other
24 carry the 100.0 "PID not performed" sentinel.

**Dead — and the premise is wrong, not just the threshold.** A real electron
stem fits the muon template well, because it *is* a MIP before it radiates. A
low score means "some template fitted", not "not an electron". This is why
pr/93's `shower_pid_guard_min_len` is floored at **50 cm** and why lowering that
floor is not the move here — pr/93 §6 measured un-floored PID guards regressing
**23 of 48** νeCC48 events.

### 5.4 Candidate 3 — the heavily-ionising prong fraction. DEAD, and it took a bad MIP to look alive.

*Hypothesis:* a hadronic star is short prongs at ≥ 2 MIP; EM daughters are not.
`f_heavy` = their share of the member length.

**First a trap that changed the answer.** The calib dump's
`meta.mip_dqdx_median` writes **43000**, the C++ default. SBND production runs
`mip_dqdx_median = 48000` — confirmed in all 3067 per-event
`.wct-cfg-evt<ID>.json`. Normalising by the dump's own field inflates every MIP
ratio by **48/43 = 1.116**, which moves prongs across a 2.0 bar. On the dump's
number 137238 reads `n_heavy = 4`, `f_heavy = 0.229` against a control maximum
of 0.212 — a survivor with a one-object margin. On the number the job actually
ran with it reads **`n_heavy = 2`, `f_heavy = 0.129`**, and:

| `f_heavy` cut | new re-types | in νe-**selected** events | of those, the event **primary** | 137238 in? |
|---|---|---|---|---|
| > 0.10 | 34 | 12 | **10** | yes |
| > 0.15 | 17 | 3 | 3 | no |
| > 0.20 | 12 | 1 | 1 | no |

Above 0.10, ten νe-selected **primaries** come with it — 81597 at `nue` 16.26,
239794 at 14.81, 42280 at 14.07, 489330 at 14.06. Below, 137238 is gone. And
138009 (`nue` 6.75) sits at 0.212, *above* 137238.

**Dead.** `scripts/pr148_a5_census.py` now reads the MIP from the compiled
config and records the dump's claim beside it in the `mip_meta` column, so this
cannot be re-made.

### 5.5 What that adds up to

**Every discriminant computable offline from the dumps has now been
pre-registered and measured, and all three died against the control.**

*Written before the scan. After it (§6.1) there is a better explanation than
three unlucky variables: all three were searching for a population of mis-typed
hadronic showers among conn-1 pdg-11 showers, and the scan says that population
is not there — 12 of 12 suspects came back EM or MIXED. A discriminant cannot
separate a class with no members. The measurements below stand; their
interpretation changes from "these variables are weak" to "there was nothing
for them to find."*

Two consequences, as written at the time:

1. **The missing ingredient is labels, not cleverness.** The control is a
   proxy, and the proxy is what killed all three; a scan is what replaces it.
   Hence §6.
2. **The next real variable must be measured in C++.** The dumps' `points[]`
   are FIT points — near-evenly-spaced trajectory samples, not charge — which
   is why the leading-bin population reads ~11 for essentially every shower in
   the census. A5's own `growth` counts IMAGED points in an 8 cm cylinder with
   an ownership filter and has **no offline equivalent**. A shape or density
   discriminant cannot be prototyped from this file at all. Hence §9's round 2.

---

## 6. The scan — 24 objects, blind, four strata

`docs/pr/pr148-pidscan-manifest.tsv`; built by `scripts/pr148_pidset.py` with a
fixed seed so the order is reproducible and the strata are not readable off it.

**Question per object: is this an EM shower, a hadronic interaction, or both
clustered into one?** `EM` / `HADRONIC` / `MIXED`, plus `weak = 1` when not
confident, plus a free-text note.

| stratum | 6 objects each | why |
|---|---|---|
| S1 | highest energy, not re-typed, in events the νe BDT rejects | where a mis-type costs `Enu` accuracy with no selection consequence. **137238 is here, and is not marked.** |
| S2 | not re-typed, BDT-rejected, carrying a star (≥ 2 heavy prongs at a shared vertex away from the start) | what a hadronic interaction should look like. §5.4 says this does not separate — it is a **sampling stratum, not a proposed cut** |
| S3 | **control** — highest energy, not re-typed, in νe-**selected** events | expected EM. A rule that eats these is the pr/93 §6 regression class and is dead on arrival |
| S4 | **control** — objects A5 **already re-typed to 211** | expected HADRONIC. If they come back EM, production is over-firing today, and that is a finding in itself |

**`MIXED` is not padding.** §3 leaves a genuine fork open: either the whole
555 MeV object is hadronic (retype — the owner's instruction), or it is an
electron shower with a pion interaction swept into it, which would be the
pr/137-139 splitter's problem, not the tag's. pr/144 §15 records that this
shower *grew* from 354.3 MeV / 102.7 cm to 555.3 / 142.9 when the exclusion pool
emptied, and pr/145 §5.1 phrased it as *"a hadronic shower absorbed into an EM
shower."* That fork is put to the owner rather than resolved here.

**One completeness gate, and it excluded one object.** The dump records ONE
owner per segment in `segments[].shower_id`, while a shower's `num_segments`
counts a member list that legitimately overlaps other showers — so a shower can
be only partly drawable. Measured across the candidate pool, 23 of 24 objects
are exact and **396222 shower 0** reads 43 of 60 segments, 246.6 of 432.5 cm.
Judging an object at 57 % of its length is judging a different object, so
`pr148_pidset.py` now requires ≥ 90 % drawable and 396222 is off the sheet.
The self-test asserts the sheet it built.

The sheet carries only `sample run subrun event obj shower_id kine_charge
kine_best total_len nseg`. Withheld: `growth`, `bragg`, `stem`, `n_heavy`,
`f_heavy`, `star`, `nue_score`, A5's verdict, and the stratum — printing the
proxy's answer on the sheet you then judge makes the agreement circular. They
are written to `docs/pr/pr148-pidscan.KEY.tsv`, so the record exists; the
display and its self-test never open that file, and the self-test asserts it.

---

## 6.1 What came back — 24/24, and the round inverts

`work/pr148_scan_labels/scan0/filled_sheet.tsv`, 2026-09-06. All 24 labelled,
**no `weak` ticks and no notes** — the owner was confident on every object.

| stratum | EM | MIXED | HADRONIC |
|---|---|---|---|
| S1 suspects — top energy, νe-BDT rejected | **6** | 0 | 0 |
| S2 suspects — heavy-prong star | **5** | 1 | 0 |
| S3 control — νe-selected (expected EM) | **5** | 1 | 0 |
| S4 control — A5 already re-typed (expected HADRONIC) | **3** | 0 | **3** |
| **total** | 19 | 2 | 3 |

### 6.1.1 The scan validated itself before it is allowed to overturn anything

The obvious objection to "19 of 24 are EM" is that the display flatters EM. It
does not, and the controls are what prove it:

- **S3 behaved.** Five of six νe-selected primaries came back EM, which is what
  a real electron should look like.
- **S4 can say HADRONIC.** Three of six came back HADRONIC, so the vocabulary
  is reachable and the display is not painting everything into one class.
- **`MIXED` was used, twice**, on the two largest absorbed objects — so the
  owner had a middle option and spent it deliberately rather than defaulting.

That makes **12 of 12 on S1+S2 a measurement, not an instrument artifact.**

### 6.1.2 The direction this round was chartered to fix has no target

Every suspect — the six highest-energy not-re-typed objects in BDT-rejected
events, and the six carrying a heavy-prong star — came back EM or MIXED. There
is no reservoir of mis-typed hadronic showers among conn-1 pdg-11 showers
waiting to be recovered. **§5's three dead discriminants were not unlucky; they
were searching an empty class.**

### 6.1.3 The defect is the other direction, and it is live in production

`shower_hadronic_tag` re-typed **68** showers over the 3067-event production
set. Six were put in front of the owner and **three came back EM** — real
electron showers that production stamps pdg 211, values with the hadronic
dQ/dx estimator instead of the charge estimator, and charges a spurious
**+139.57 MeV** π rest term in `kine_reco_Enu` (`kine_mass_rules` and
`kine_hadronic_dqdx` are both SBND-ON; verified in the compiled config and in
evt 388's `kine_particle_type`, which carries a 211 row).

**The honest size of that claim, stated because it limits what §8 may argue.**
S4 was built as "the highest `kine_best` among the already-re-typed", and it is
literally the top six of sixty — 241.9 … 677.1 MeV against a population median
of **58.1**. So *"three of six"* is the precision of A5's **energy tail**, not
of A5. The supportable statement is the narrower one §8 rests on: of the seven
objects the proposed guard declines, four carry labels and **three of those
four are EM**.

## 6.2 The question the scan leaves open, and does not answer

**137238's own object came back EM.** The blind verdict on shower 0 — the only
candidate in the event, 555 MeV, 48 % of its `Enu` — is EM, from the same
person who wrote of this event in doc pr/144 §8: *"the hadronic shower made to
an EM shower."*

Those are not necessarily in conflict. pr/145 §5.1 already read the pr/144
comment as *"a hadronic shower **absorbed into** an EM shower"*, and pr/144 §15
measured the absorption: this shower grew 354.3 MeV / 102.7 cm → 555.3 /
142.9 when the exclusion pool emptied. Shown the merged object, the EM part
dominates and EM is the right word for it — while the complaint remains about
what was swallowed.

**Two more objects point the same way.** Both `MIXED` verdicts are large
absorbed objects — 100222 shower 2 at 81 segments / 489 cm, and 21073 shower 0
at 35 segments / 219 cm — and neither is re-typed. So three of the twenty-four
point at the splitter and **none point at the tag**.

This doc does not resolve it. The question for the owner is:

> On 137238, is the 555 MeV object itself wrong — or is the complaint that
> hadronic content was absorbed into a real EM shower, which is the splitter's
> problem and not the tag's?

The answer decides whether the follow-up is doc pr/137-139's splitter or
another typing round. §11 recommends the former on the evidence above, but it
is the owner's call.

---

## 7. The display — `pr148_scan/`, port 5017

Built as asked. Forked **by duplication** (M10) from
`em_display/em_display_viewer.py` — its three-panel block, the `Range1d` rule
and the detector box (`:57`, `:193-210`). `em_display/`, `split_display/` and
`pr_display/` are byte-untouched and still serve their own scans. Same shape as
the owner's own precedent, `pdhd/d05_scan` forked from `pdhd/stm_scan`
(pdhd doc 05).

| file | what |
|---|---|
| `pr148_scan/prep_pr148_scan.py` | per-object payload from the calib dumps |
| `pr148_scan/pr148_scan_viewer.py` | the Bokeh app |
| `pr148_scan/serve_pr148_scan.sh` | `bokeh serve` wrapper, port + `--scan-tag` |
| `pr148_scan/selftest_pr148_scan.py` | headless; **rc 0 or do not serve** |
| `work/pr148_scan_labels/<tag>/labels.json` | rewritten on every click |
| `work/pr148_scan_labels/<tag>/filled_sheet.tsv` | the manifest with the verdicts filled in |

**Three projections — X-Y, Y-Z (beam view), Z-X (top view) — at the full
detector volume**, with the SBND active boundary
(`x ±201.05, y ±199.312, z 0.85-500.15`) drawn dashed. Full volume is the
default deliberately: an object auto-zoomed to its own extent fills the frame
whatever it is, which flattens the "30 cm stub or 5 m cascade" judgement.
`Zoom to object` exists and is off by default.

- **coloured** — the object's own fit points, coloured by dQ/dx in MIP units on
  a **fixed 0.5-3.5 scale**. Fixed, not per-object: a per-object rescale makes
  every object contain its own reddest prong, so a 3 MIP proton and a 1 MIP
  electron stem paint identically and the colour stops carrying information.
- **grey** — every other segment in the event, so an absorbed far blob or a
  neighbouring muon is visible as context.
- **red X** the start vertex, **red O** the farthest member point from it.
- a neutral measured line: charge energy, best energy, total length, segments
  drawn (and what the dump claims), farthest-point distance. Arithmetic, not a
  verdict.

**The blind is proven, not asserted.** The payload deliberately omits every
segment's `particle_id`, `particle_score` and `flag_shower` as well as the A5
scalars — that trio is the reconstruction's *own typing answer*, and the scan
exists to check it. `selftest_pr148_scan.py` enumerates the keys of every
ColumnDataSource and every payload against an allow-list, checks the forbidden
names separately so an allow-list edit cannot re-admit one, greps the rendered
text, and wraps `open()` for the whole document build to prove the KEY file is
never read (while asserting the manifest *is* read, so the negative means
something). It does not use `bokeh.client.pull_session`, which hands back a
detached document and would pass on an app that is broken in the browser.

Verified live: `selftest` 22/22 checks pass; the server binds 5017, `HTTP 200`,
and a session pulls back 1 root, panels `f_xy/f_yz/f_zx`, 249 member points for
object 1, the three verdict buttons, and **no forbidden word in any served
Div**.

**Port 5017 is shared with `pr_display`** (`pr_display/serve_pr_display.sh:33`).
Run one or the other, never both — a second bokeh on a busy port **fails soft**:
it logs `port 5017 is already in use` and leaves the *old* app answering, which
is how a stale display gets hand-scanned. `serve_pr148_scan.sh` therefore
refuses to start if anything is already listening, rather than trusting the
operator to check.

---

## 8. The design of the fix — `shower_hadronic_max_nseg` — **REFUTED, §11.3**

> **Kept as written and marked dead.** Scan 2 labelled the whole of the cut set
> priced below: **5 EM / 2 HADRONIC, Fisher *p* = 0.37** against the objects the
> guard keeps. The bar does not separate. The empty bin argued for in §8.1 was
> not a class boundary — it is where a monotone tail thins out, unlike the
> genuinely bimodal one pr/145 §5.8 used, and reading it as a boundary was the
> error. §12 has the numbers. Nothing in this section ships.

Not "make A5 fire more". **Make A5 stop firing on EM cascades.** One new knob,
C++ default `0` = off, so the legacy path is byte-identical:

> **A5 declines to re-type a shower whose segment count at evaluation time
> exceeds `shower_hadronic_max_nseg`.** Recommended SBND value **10**.

### 8.1 Why the segment count, and why 10 *(the reasoning that failed)*

**The labels pick the variable.** Sorted by the shower's *final* segment count:

| verdict | `num_segments` |
|---|---|
| HADRONIC | 4, 4, **9** |
| EM | **11**, 17, 18, 19, 20, 27, 32, 33, 33, 33, 34, 38, 39, 43, 51, 84, 90, 115, 146 |
| MIXED | 35, 81 |

Clean, with an **empty bin at 10** across all 24 labels. Physically it is the
obvious statement: an EM cascade fragments into many segments; a pion or proton
that travels and interacts once does not.

**But the final count is not available where the decision is made.** A5 runs
mid-pipeline, before the shower has finished growing. On the *census-time*
count — the `nseg=` field A5 already logs, and the only one it can read — the
same three HADRONIC objects read **4, 4, 26**: 98844 was 26 segments when A5
judged it and 9 by the end. So the implementable variable is the imperfect one,
and the doc says so rather than quoting the clean number as if it were usable.
Same shape as pr/146's rejected "is the continuation partner counted?" rule:
the physically right variable is not readable at the seat.

**The bar is not fitted to four labels.** The census-time `nseg` histogram of
the 60 joined re-types is

```
nseg:  1   2   3   4   5   6   7   8   9  10  11  18  26  27
  n:   1  21  14   9   1   5   1   1   .   .   4   1   1   1
```

**Nothing at 9 or 10.** The bar sits in an empty bin of the very population it
cuts, which is the pr/145 §5.8 label-free-threshold argument and is independent
of the verdicts. That is most of what makes n=4 tolerable.

### 8.2 What it does, and what it costs

At `> 10` the guard declines **7 of the 60** joined re-types (68 total), one
per event:

| evt | shower | nseg (census / final) | branch that fired | `kine_best` now | `kine_charge` | ΔEnu if spared | label |
|---|---|---|---|---|---|---|---|
| 388 | 0 | 27 / 27 | growth | 677.1 | 724.5 | **−92.2** | **EM** |
| 163543 | 0 | 11 / 11 | growth | 414.2 | 394.6 | **−159.2** | **EM** |
| 98844 | 0 | 26 / 9 | growth | 241.9 | 326.9 | −54.5 | HADRONIC |
| 98294 | 0 | 18 / 18 | **stem** | 286.0 | 315.6 | **−110.0** | **EM** |
| 406125 | 0 | 11 / 11 | growth | 139.7 | 180.2 | −99.1 | — |
| 318769 | 0 | 11 / 7 | growth | 107.4 | 107.4 | −139.6 | — |
| 321015 | 16 | 11 / 11 | growth | 96.5 | 100.1 | −136.0 | — |
| | | | | | | **−790.5 MeV** | 3 EM removed, 1 HADRONIC lost |

**Four of the seven carry labels and three of those four are EM.** The guard
removes three wrong re-types and one right one. That is the whole evidential
claim; it is not a precision figure for A5 (§6.1.3).

`ΔEnu = (kine_charge − kine_best_now) − 139.57` per object — the re-typed
object reverts from the hadronic dQ/dx estimate to its EM charge estimate and
gives back the π rest term. **The assumption, stated:** that a spared object's
`kine_best` reverts to its `kine_charge`. That holds exactly for **204 of the
240** EM-typed showers in the census (85 %); on the other 36 the median gap is
20.7 MeV. So −790.5 is a pre-registration to be scored against the knob-on arm,
not a measurement.

**137238 is untouched.** It is not re-typed and would not be.

### 8.3 What this design does NOT cover

- **The stem branch.** It fired 5 of the 68 times. Its only label — 98294,
  stem 5.06 MIP — came back **EM**, so its measured precision is **0 / 1**, and
  the guard catches that one only incidentally (its census `nseg` is 18). The
  other four stem fires sit at `nseg` 1-3, below any bar this guard could set.
  **The stem branch is untested and unguarded and needs its own round.**
- **The bragg branch**: 2 fires, `nseg` 2 and 3, no labels.
- **§4.2's Bragg window** — `dqdx_term` measured on absorbed members up to
  70 cm past the object's body. Unchanged, still its own round.
- **The absorption / splitter question** of §6.2. Nothing here touches it.

### 8.4 Implementation sketch (round 2 — not done in this doc)

| file | change |
|---|---|
| `clus/inc/WireCellClus/TaggerCheckNeutrino.h` | `int m_shower_hadronic_max_nseg{0};   // doc pr/148; 0 = off` |
| `clus/inc/WireCellClus/NeutrinoPatternBase.h` | the mirror member, same default |
| `clus/src/TaggerCheckNeutrino.cxx` | `configure()`, `default_configuration()`, and the copy — **unscaled**, it is a count, not a length |
| `clus/src/NeutrinoShowerClustering.cxx` | in the A5 loop, **after** the census line and **before** the stamp (§9.1) |
| `clus/test/doctest_clus_knob_defaults.cxx` | `CHECK_KNOB_NUM(cfg, "shower_hadronic_max_nseg", 0)` |
| `cfg/pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet` | **SBND only**, `= null` plus the key-suppression idiom |

```cpp
// doc sbnd_xin/pr/148 sec 8: the owner's blind scan found A5 re-typing real
// EM cascades (3 of the 4 labelled objects above this bar came back EM).  An
// EM cascade fragments into many segments; a hadron that interacts once does
// not.  The bar sits in an empty bin of the re-typed population's own nseg
// histogram (nothing at 9 or 10 across 60 re-types), so it is not fitted to
// the four labels.  0 => no guard => byte-identical legacy.
if (verdict && m_shower_hadronic_max_nseg > 0 &&
    shower->get_num_segments() > m_shower_hadronic_max_nseg) {
    SPDLOG_LOGGER_DEBUG(s_log,
        "A5 hadronic decline: shower id={} nseg={} > max_nseg={} "
        "(growth={:.2f} bragg={:.2f} stem={:.2f})",
        shower->get_shower_id(), shower->get_num_segments(),
        m_shower_hadronic_max_nseg, growth, bragg, stem_med);
    continue;
}
```

**The census line must keep firing on every evaluated shower** — it is the
calibration channel this whole doc is built on, and a guard placed before it
would blind the next round. Hence the decline is logged separately and placed
after.

---

## 9. What happens next

### 9.1 Round 2 — implement §8, gate it, and score the pre-registration

Build `shower_hadronic_max_nseg` per §8.4 (**default OFF**), then:

- **Knob-off byte-identical** on the standard manifest of every detector that
  binds `NeutrinoShowerClustering` — SBND, PDVD, PDHD and the uBooNE chain —
  member-content hashes only, never `cmp`/`md5sum` on an archive (M2).
- **M1 freshness** and the **M6 compiled-config proof** (the key absent when
  off, present at 10) on the arm-produced `.wct-cfg-evt<ID>.json`, not a bare
  `wcsonnet` — doc pr/146 records why the standalone compile proves nothing.
- **`./build/clus/wcdoctest-clus`** with the new default asserted.
- **Sentinels** no worse than `20 PASS / 0 FAIL / 3 OPEN / 7 INERT`. 137238 is
  one of the 3 OPEN and this change does not touch it.

**Pre-registered, so it cannot be adjusted afterwards:**

1. Exactly **7** showers stop being re-typed, in 7 events, and they are the
   seven named in §8.2. The `A5 hadronic decline:` line fires 7 times.
2. **ΔEnu = −790.5 MeV** in total, under §8.2's stated counterfactual. Anything
   outside roughly ±100 MeV of that means the counterfactual is wrong and the
   36-of-240 exception class is the first place to look.
3. **137238 is byte-identical.**
4. **Selection risk, flagged rather than predicted.** Two of the seven sit in
   νe-selected events — 388 (`nue_score` 9.69, ΔEnu −92) and 163543 (3.11,
   ΔEnu −159). 163543 is 0.11 above the acceptance threshold of 3, so a flip
   there is plausible. This is a number to *measure*, not one to predict; if
   it flips, that is a real cost of the guard and belongs in the owner's
   decision, not in a footnote.

The knob ships **OFF**. Turning it on for SBND is a CLAUDE.md §5.1 production
default flip and is the owner's call, with these numbers in front of them.

### 9.2 Two things reported, not fixed

1. **A guard fires and is defeated.** In this event
   `pr130 pass3_backfill_guard: decline seg=146066 pdg=13 len=16.4cm` fires —
   and segment 146066 is a **member of shower 144050** in the same run's dump.
   The guard declined the absorb and something downstream took the segment
   anyway. The entry route is not established. Shape of pr/125 §3.1, where the
   pass-3 cone guard was defeated by the sibling backfill 40 lines later.
2. **§4.2's Bragg window.** `dqdx_term` is measured on absorbed members up to
   70 cm past the object's contiguous body, for every shower A5 evaluates. It
   is not what rescues 137238 (§4.2 prices it: 0.85 → 0.62, bar 3.0), so it
   belongs in its own round rather than being smuggled into this one.

Untouched and verified alive in this event: the pr/93 r4 + pr/127 fix —
`sccc demote: ... cluster=144 len_cm=14.5 pdg 11 -> 13 sib_cluster=7
sib_len_cm=81.6`, then `sccc bridge: cluster 7 -> main 144 ... bridge=OK`.
Nothing proposed here touches the sentinel's inverted `pf_node_lt mu- 150`
assertion (doc 91 §12.3).

---

## 10. Honest limits

- **Two designs of mine were refuted by the owner's scans, in sequence** — the
  charter (recover 137238 to hadronic) by scan 0, and §8's `nseg` guard by
  scan 2. Both are kept and marked rather than deleted; a doc that only shows
  what survived cannot be audited.
- **The §8.1 empty-bin argument was wrong, and the error is nameable.**
  pr/145 §5.8's empty bin sat between two **modes** of a bimodal distribution.
  §8.1's sat where a monotone tail thins out — mass at `nseg` 2-4, then
  sparsity. That is not a class boundary, and reading it as one is how n=4
  got promoted to a design.
- **The round's own charter was refuted by the round's own scan.** It was
  opened to re-type 137238 from EM to hadronic; the owner's blind verdict on
  that object is EM. §§1-5 are kept as written, and §5.5 carries the note that
  their three dead discriminants were searching a class the scan says is empty.
  Erasing the refuted half would make the record useless.
- **§8's four labels became seven and the guard died.** The direction it rested
  on — that A5 re-types real EM cascades — survives and is now measured on 18
  (§12.1); the *variable* did not.
- **S4 is the energy tail, not a sample of A5.** It is literally the top six
  re-types by `kine_best` out of sixty whose median is 58.1 MeV. "Three of six
  are EM" is a statement about the tail. Do not quote it as A5's precision.
- **The control is a proxy and is partly circular.** 137238's `nue_score` is
  −4.31 in part *because* the BDT sees a hadronic-looking object, so "not
  selected" is not independent evidence that the object is hadronic. The νe-
  selected side is the sound half — a real electron in a selected event is a
  real electron — which is why S3 is on the sheet and why every candidate above
  was killed by its **false positives on controls**, never by a miss.
- **`f_heavy` looked alive for an afternoon** because the calib dump's
  `meta.mip_dqdx_median` is not the value the job ran with (§5.3). Any earlier
  MIP-normalised number of mine from a dump should be re-derived.
- **A5's `growth` cannot be reproduced offline at all** — imaged points in a
  cylinder with an ownership filter. Everything in §5 is a *different* variable
  measured on fit points, not a reconstruction of A5's own.
- **The counterfactual in §8.2 is an assumption, not a measurement.** It holds
  for 204 of 240 EM-typed showers; the arm decides.
- **This is still a patch on fragmentation.** 137238's muon structure is
  scattered across clusters 7, 144 and 146, and the "shower" reaches 108 cm by
  absorbing a blob 70 cm away. Typing the object correctly is right; not
  scattering it is the upstream fix, and it is not in this doc — and §6.2 says
  the scan now points there.

## 11. Scan 2 — 12 objects, built and running

`docs/pr/pr148-pidscan2-manifest.tsv` (+ `pr148-pidscan2.KEY.tsv`), built by
`scripts/pr148_pidset2.py`, **forked by duplication** from `pr148_pidset.py`
(M10) — scan 0's builder produced a finished record and stays byte-untouched.

**Every object on this sheet is one the reconstruction already re-typed from
electron to pion. The question is whether it was right to.** Three strata,
each answering a different question:

| stratum | n | what it measures |
|---|---|---|
| **A** — all 3 remaining objects **above the bar** (census `nseg` > 10) | 3 | with scan 0's four, this labels the guard's **entire cut set**, so its **precision** stops being an estimate |
| **B** — all 4 remaining **stem-branch** fires | 4 | the stem branch has never been tested: 5 fires, one label, and it came back EM. 0 of 1 is not a measurement. This makes it 5 of 5 |
| **C** — 5 **growth-branch** fires **below the bar**, at `kine_best` quantiles (min / p25 / median / p75 / max) of the 45 unlabelled | 5 | the guard's **recall**. If these come back HADRONIC the guard is safe; if some come back EM then A5 mis-fires below the bar too and `nseg` is not the whole answer |

**Quantiles, not top-N, and that is a correction of scan 0's own method.** S4
was the top six by energy out of sixty whose median was 58 MeV, and §6.1.3 had
to spend a paragraph discounting its own headline because of it. Stratum C
spans the population instead.

**Still not covered, said rather than quietly dropped:** the **bragg branch**
— 2 fires in the whole population (25.2 and 173.7 MeV). Two of twelve slots is
a poor trade against 45 unlabelled growth fires, so it stays open.

### 11.1 The blind moved, because the proxy moved

Scan 0 withheld growth / bragg / stem / `f_heavy` / the stratum / `nue_score`.
§8's discriminant is the **segment count**, so scan 2 withholds that too — from
the sheet **and** from the screen. The display no longer prints
*"segments drawn N"*: a count shown next to a bar of 10 is the verdict shown.
Length and both energies stay, because they are what the object *is*, not what
the guard thinks of it.

`selftest_pr148_scan.py` now carries `nseg` in its forbidden set and takes
`--sheet` / `--expect`, so both sheets are checked by the same instrument:
**22/22 on the 12-object sheet and 22/22 on the 24-object one.** Live: 12
objects served on 5017, no forbidden word in any Div, no count on screen.

```bash
./pr148_scan/serve_pr148_scan.sh 5017 --scan-tag scan1 \
    --sheet docs/pr/pr148-pidscan2-manifest.tsv
#   ssh -o ServerAliveInterval=30 -L 5017:localhost:5017 <user>@wcgpu1.phy.bnl.gov
#   http://localhost:5017/pr148_scan_viewer
```

A **fresh tag** (`scan1`), never written into `scan0` (M13).

### 11.2 What was pre-registered, before the labels arrived

1. Re-score with `pr148_score_scan.py --labels work/pr148_scan_labels/scan1/filled_sheet.tsv`.
2. **Precision** = the labelled fraction of stratum A ∪ scan 0's four that is
   EM; that is the number the §8 guard is worth.
3. **Recall** = stratum C. Any EM verdict there means the guard is necessary
   but not sufficient, and §8 needs a second term.
4. **The stem branch** decides its own fate on stratum B: if it is 5/5 EM it
   should be turned off outright, not guarded.
5. Then implement §8.4 and score §9.1's pre-registration.

§11.4 scores these against what came back.

### 11.3 What came back — 12/12, and it kills §8

`docs/pr/pr148-pidscan2-verdicts.tsv` (committed before this analysis, so the
labels are a record independent of what I conclude from them). No `weak` ticks.

| idx | evt | shower | stratum | branch | census `nseg` | **verdict** |
|---|---|---|---|---|---|---|
| 3 | 321015 | 16 | A above bar | growth | 11 | HADRONIC |
| 7 | 406125 | 0 | A above bar | growth | 11 | **EM** |
| 10 | 318769 | 0 | A above bar | growth | 11 | **EM** |
| 0 | 30504 | 0 | B stem | stem | 3 | **EM** |
| 4 | 399328 | 0 | B stem | stem | 2 | **EM** |
| 8 | 174771 | 4 | B stem | stem | 1 | HADRONIC |
| 11 | 92904 | 0 | B stem | stem | 2 | HADRONIC |
| 1 | 177068 | 2 | C below bar | growth | 2 | **EM** |
| 2 | 315167 | 1 | C below bar | growth | 7 | HADRONIC |
| 5 | 355106 | 0 | C below bar | growth | 3 | **EM** |
| 6 | 163543 | 3 | C below bar | growth | 6 | **EM** |
| 9 | 165767 | 0 | C below bar | growth | 3 | HADRONIC |

**Stratum A closes the guard.** With scan 0's four, the seven objects
`shower_hadronic_max_nseg = 10` would decline are now **fully labelled**:

| | labelled | EM (the guard is right to remove) | HADRONIC (it is wrong to) |
|---|---|---|---|
| **above** the bar — what §8 removes | 7 | **5** | 2 |
| **below** the bar — what §8 keeps | 11 | **5** | 6 |

EM fraction 0.71 above against 0.45 below; **Fisher two-sided *p* = 0.37**.
On 18 labels the bar is indistinguishable from a coin. **§8 is refuted.**

**Stratum C is the reason it could never have worked.** Three of five
growth-branch fires *below* the bar came back EM. A5 mis-fires below the bar at
much the same rate as above it, so no cut on this variable was ever going to be
sufficient — and the guard's own removals are 2-in-7 wrong.

### 11.4 Scoring §11.2's pre-registered predictions

Written before the labels arrived, scored as written:

| # | prediction | outcome |
|---|---|---|
| 2 | stratum A gives the guard's precision | **delivered** — 5/7, and it kills the guard |
| 3 | "any EM verdict in stratum C means the guard is necessary but not sufficient" | **fired, and harder than the wording allows.** 3 of 5 are EM: the guard is not necessary either |
| 4 | "if stratum B is 5/5 EM the stem branch should be turned off outright" | **did not fire.** With scan 0's 98294 the stem branch is **3 EM / 2 HADRONIC** — indistinguishable from the growth branch's 7/6. No grounds to single it out |

Prediction 4 mattering is the point of writing it down: without it the temptation
would have been to retro-fit the stem branch as the villain on 2 of 5.


---

## 12. What the two scans measured, together

36 labels over two independently-designed samples — scan 0's by energy rank,
scan 2's by branch and by energy quantile. **18 of them are objects
`shower_hadronic_tag` re-typed**, which is the first labelled calibration set
this mechanism has ever had. `scripts/pr148_score_scan.py` reproduces
everything below.

### 12.1 The tag is right about half the time, and that question is now closed

| | n |
|---|---|
| labelled A5 re-types | **18** |
| the re-type was right (HADRONIC) | **8** |
| the re-type was wrong (EM) | **10** |

**Precision 8/18 = 0.444, 95 % Wilson score interval [0.25, 0.66].**
(Wilson, not the normal approximation, which is meaningless at n=18.)

**Fifty percent is inside that interval**, and at 50 % the tag is `Enu`-neutral
by construction (§12.2's terms cancel). So these labels cannot distinguish
*harmful* from *neutral* from *mildly helpful*, and the decomposition says the
same thing arithmetically: reverting the 18 would fix **1246.7 MeV** of error
and break **929.9 MeV** — a net of +317 MeV, which is one or two verdicts wide.

Establishing precision < 0.5 at any useful confidence needs on the order of
**100+ labels**. That is not an achievable scan. **The precision question is
therefore closed as unanswerable at achievable cost, and this doc does not
recommend a flip on it.** Recording that is worth more than a third scan of
the same population.

**And nothing measured separates the two classes.** Over the 18, every census
variable overlaps completely:

| variable | EM (n=10) | HADRONIC (n=8) |
|---|---|---|
| `growth` | 0.06 … 1.03 | 0.07 … 1.13 |
| `bragg` | 0.47 … 2.00 | 0.37 … 2.14 |
| `stem` | 0.61 … 5.06 | 0.32 … 4.22 |
| `nseg` (census) | 2 … 27 | 1 … 26 |
| `total_length` | 2.7 … 142.1 cm | 14.0 … 138.7 cm |
| `kine_best` | 7.8 … 677.1 MeV | 34.2 … 390.8 MeV |
| `start_len`, `f_heavy`, `max_mip`, `smax` | — all overlapping — | |

Twelve variables, no separation. Fishing for a thirteenth on n=18 is the
over-fitting this campaign has repeatedly refused, so this doc stops.

By branch: **growth 7 EM / 6 HADRONIC, stem 3 EM / 2 HADRONIC.** The two
branches are indistinguishable from each other as well as from a coin.

### 12.2 A5's energy effect is 11 : 1 rest-mass over estimator — and the estimator is the only thing it was designed to change

pr/99 §3 built A5 so that a re-typed object's *"best energy follows the hadronic
rule"* — `apply_hadronic_dqdx_best` swaps `kine_charge` for `kine_dQdx`. The
π rest term rides along afterwards, because `kine_mass_rules` keys on pdg 211;
pr/99 §5 mentioned it once as *"the existing non-EM kine convention"* and never
measured it. Measured now, over the 60 joined re-types:

| term | total | per object |
|---|---|---|
| π rest mass added to `kine_reco_add_energy` | **−8374.2 MeV** if reverted (60 × 139.57) | **139.57** |
| the estimator swap it was built for | **+942.3 MeV** if reverted | median **12.7** |
| net if the tag were switched off | **−7431.9 MeV** over 58 events | −123.9 |

**The thing A5 was designed to do moves the median object by 12.7 MeV. The
thing nobody calibrated moves it by 139.57.** And for **9 of the 60 (15 %)**
`apply_hadronic_dqdx_best` declines to write at all — `kine_best` is still
`kine_charge` — so for those objects the re-type's *entire* effect on `Enu` is
the rest term, 1256 MeV of it between them.

**A correction to how this was first phrased, because it matters.** The rest
term is not *wrong*: a real charged pion's contribution to the neutrino energy
budget genuinely includes its 139.57 MeV rest mass, so the term is correct
**conditional on the type being right**. "Strip the rest term" is therefore not
a fix — it would break the 44 % of firings that are correct.

The finding is about the **validation bar**, not the term:

> **A5 was calibrated as a 13 MeV decision and it is making a 140 MeV one.**

pr/99 §3 validated it the way a change to an *estimator* is validated —
selections did not flip, the re-typed objects' energies moved sensibly, and the
adverse controls held. What it never asked is whether the typing was good
enough to carry a term eleven times larger than the estimator swap. On 18
labels the answer is that the typing is roughly a coin flip, so the term is
right about half the time and wrong by 139.57 MeV the other half.

**The consequence is noise, not bias.** At 44 % (CI [0.25, 0.66], i.e.
statistically indistinguishable from 50 %) the errors very nearly cancel in the
mean — reverting the 18 labelled objects nets only **+317 MeV**, ~18 MeV per
object — while each individual event moves by **±125 MeV**. So A5 trades a
~13 MeV systematic improvement for a ~140 MeV random error on the 58 events
(1.9 % of the sample) where it fires.

Whether that trade is worth making is a CLAUDE.md §5.1 judgement and it is the
owner's. This doc does **not** recommend flipping it, because §12.1's interval
cannot exclude the possibility that the tag is helping.

### 12.3 A5 has drifted off its own calibration

pr/99 §3 named five design events. Checked against the current census:

| pr/99 design event | what pr/99 built it for | today |
|---|---|---|
| **395148** | **the entire proton-stem branch** — *"its ownership growth is 0.87 but its stem reads 3.0 MIP"* | **does not fire.** `growth 0.86` still, but `stem` reads **0.44**, not ~3. The branch that exists for this object no longer reaches it |
| 315167 | *"pdg 211 + numu 1.77 → 2.23"* on its 329 MeV object | shower 0 **no longer fires** (`bragg 4.97` clears the 3.0 bar but `growth 1.86` fails the 1.2 ceiling); showers 1 and 2 fire instead |
| 285567 | *"BOTH fakes 211"* | **one of two** fires |
| 70084 | re-typed 211 | still fires |
| 91653 | *"numu 0.03 → 0.65"* | still fires |

So two of five are intact, two fire on different objects than they were tuned
on, and **the stem branch's sole design object has fallen off it**. The stem
branch now fires 5 times on a population it was never calibrated against, and
those five label 3 EM / 2 HADRONIC.

**This is pr/127's story again** — a shipped, owner-approved fix quietly
stopped reaching the object it was built for, and nothing failed. It is a more
actionable finding than any precision figure, because it has a cause that can
be chased: what moved 395148's stem from ~3.0 MIP to 0.44 between 2026-08-20
and now.

Weak corroboration that the labels are sound rather than noisy: 315167's
re-typed shower came back **HADRONIC**, agreeing with pr/99's own verdict on
that event.

---

## 13. Recommended next step

**Stop the typing thread here and go to the splitter.** After 36 labels it has
produced a measurement, not a fix, and the measurement says the remaining
uncertainty cannot be bought at achievable scan cost (§12.1). Meanwhile three
of scan 0's twenty-four objects point at **absorption** — 137238 itself under
the §6.2 reading, plus both `MIXED` verdicts at 81 and 35 segments — and none
point at the tag. Doc pr/137-139 owns that machinery.

Two things go back to the owner, both §5.1 calls, neither taken here:

1. **§6.2** — on 137238, is the 555 MeV object itself wrong, or is the
   complaint that hadronic content was absorbed into a real EM shower? This
   decides whether the splitter is the right follow-up at all.
2. **§12.2** — A5 was calibrated as a 13 MeV decision and is making a 140 MeV
   one. **No change is proposed**: the rest term is correct when the type is
   correct, so stripping it would break the 44 % of firings that are right, and
   §12.1's interval cannot exclude the tag helping. This is recorded for
   whoever next touches the mechanism, and flagged as a §5.1 judgement if the
   owner wants to act on it anyway.

And one investigation that stands on its own, with a cause to chase rather than
a threshold to tune: **§12.3, why 395148's stem collapsed from ~3 MIP to 0.44**
and took the proton-stem branch's only calibration object with it.
