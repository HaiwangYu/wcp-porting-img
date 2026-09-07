# doc sbnd_xin/pr/148 — evt 137238: the hadronic shower typed electron, and why the A5 tag misses it

**Status: DIAGNOSIS COMPLETE, IMPROVEMENT NOT YET DESIGNED — a scan is
requested.** No code changed, no default flipped, nothing byte-identical to
prove. Two deliverables: this doc plus its census, and a hand-scan display on
port 5017.

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

Answers, in order: **yes — §6, 24 objects, and the display is built and
running**; **§1 — this is the owner's own item 5, open since doc pr/144 §8**;
**§2 — the idea is A5 `shower_hadronic_tag` (doc pr/99 round 3), and §4 is why
it does not fire here.**

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

# The display (sec 7)
/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/python \
    pr148_scan/selftest_pr148_scan.py          # rc 0 or do not serve
./pr148_scan/serve_pr148_scan.sh 5017 --scan-tag scan0
#   ssh -o ServerAliveInterval=30 -L 5017:localhost:5017 <user>@wcgpu1.phy.bnl.gov
#   http://localhost:5017/pr148_scan_viewer

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
pr/127 fix, which is alive in this event and unaffected — §8.2.

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
primaries. Its circularity is stated in §9.

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

*Measured over the 300:* the predicate fires on **27** showers — and **15 of
the 62 νe-selected controls**, including `nue_score` 11.93 (214469, 1699 MeV),
12.46 (172230), 12.86 (246579) and 14.06 (489330). Of the 39 controls whose
start segment is over 20 cm, **15 carry a score below 1.0** (0.11 … 0.45); the
other 24 carry the 100.0 "PID not performed" sentinel.

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

| `f_heavy` cut | new re-types | of which νe-**selected** | 137238 in? |
|---|---|---|---|
| > 0.10 | 34 | **12** | yes |
| > 0.15 | 17 | 3 | no |
| > 0.20 | 12 | 1 | no |

Above 0.10, twelve controls come with it — 239794 at `nue` 14.81, 42280 at
14.07, 489330 at 14.06. Below, 137238 is gone. And 138009 (`nue` 6.75) sits at
0.212, *above* 137238.

**Dead.** `scripts/pr148_a5_census.py` now reads the MIP from the compiled
config and records the dump's claim beside it in the `mip_meta` column, so this
cannot be re-made.

### 5.5 What that adds up to

**Every discriminant computable offline from the dumps has now been
pre-registered and measured, and all three died against the control.** That is
the honest state of the round. Two consequences:

1. **The missing ingredient is labels, not cleverness.** The control is a
   proxy, and the proxy is what killed all three; a scan is what replaces it.
   Hence §6.
2. **The next real variable must be measured in C++.** The dumps' `points[]`
   are FIT points — near-evenly-spaced trajectory samples, not charge — which
   is why the leading-bin population reads ~11 for essentially every shower in
   the census. A5's own `growth` counts IMAGED points in an 8 cm cylinder with
   an ownership filter and has **no offline equivalent**. A shape or density
   discriminant cannot be prototyped from this file at all. Hence §8's round 2.

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

The sheet carries only `sample run subrun event obj shower_id kine_charge
kine_best total_len nseg`. Withheld: `growth`, `bragg`, `stem`, `n_heavy`,
`f_heavy`, `star`, `nue_score`, A5's verdict, and the stratum — printing the
proxy's answer on the sheet you then judge makes the agreement circular. They
are written to `docs/pr/pr148-pidscan.KEY.tsv`, so the record exists; the
display and its self-test never open that file, and the self-test asserts it.

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

Verified live: `selftest` 21/21 checks pass; the server binds 5017, `HTTP 200`,
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

## 8. What happens next

### 8.1 Round 2 — after the verdicts

A **log-only** extension of the A5 census line (a DEBUG line changes no output;
the knob-off gate is byte-identical by construction and will still be run),
emitting the three quantities the C++ can measure and the dumps provably cannot
(§5.5): the per-bin profile **shape** rather than its ends-ratio, the
contiguous-body Bragg of §4.2, and an ownership-filtered heavy-prong count.
Run over the 259 candidate events only, not 3067. Then calibrate against the
owner's labels — S3 and S4 are the bar — then a new A5 branch, **default OFF**,
with the usual byte-identical knob-off gate on every detector that binds
`NeutrinoShowerClustering`.

**Pre-registered energy consequence for 137238, so it cannot be adjusted
later** — and note it goes **UP**, which may not be expected:

- `kine_best` 555.35 → `kine_dQdx` **478.38** via `apply_hadronic_dqdx_best`
  (`clus/src/NeutrinoEnergyReco.cxx:516-537`; `kine_hadronic_dqdx` is SBND-ON,
  `num_segments` 20 > 1, so it is eligible) — **−76.97 MeV**
- `kine_mass_rules` (SBND-ON) adds the π rest term **+139.57 MeV** where pdg 11
  contributes 0 (`clus/src/NeutrinoKinematics.cxx:102-112`, `:227-241`)
- first order: **`Enu` 1161.2 → ≈ 1223.8 MeV (+62.6)**

`nue_score` is −4.31, so **no selection flip in this event**. The aggregate
νeCC48 selection cost is what S3 must bound.

### 8.2 Two things reported, not fixed

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

## 9. Honest limits

- **The diagnosis is solid; the improvement is not yet designed.** Three
  candidates were pre-registered and all three died. Saying so is the point of
  measuring before building.
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
- **This is still a patch on fragmentation.** 137238's muon structure is
  scattered across clusters 7, 144 and 146, and the "shower" reaches 108 cm by
  absorbing a blob 70 cm away. Typing the object correctly is right; not
  scattering it is the upstream fix, and it is not in this doc.

## 10. Recommended next step

**Scan the 24 on port 5017.** Every threshold this round could have proposed
was killed by the proxy control, so the labels are the round's only route
forward — and S4 answers a question production has never been asked: is the
tag that already ships over-firing? Round 2 (§8.1) starts the moment
`work/pr148_scan_labels/scan0/filled_sheet.tsv` has verdicts in it.
