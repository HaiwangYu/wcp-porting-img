# doc pdhd/03 -- CheckSTM_Michel on PDHD: the stopping-muon + Michel stage becomes the PDHD `-nu` chain, and what PDHD taught the algorithm

**Status (2026-09-05, one night).** The doc pdvd/48 stage `CheckSTM_Michel` is wired into the
PDHD PR driver and runner exactly as on PDVD (`-nu` = the new chain, `-nu-legacy` = the never-graded
neutrino tail, default `-stm` untouched and byte-identical).  Five 30-event arms on run 029107
found and fixed, in order: (1) the doc pdvd/45 exclusion-frame defect was live on PDHD (the PR
fit kept 0.1-0.6 of the tagger's fit points; `excl_t0_frame` now ON in the PDHD `-nu` driver);
(2) zero-charge stretches in the fit profile faked Bragg contrasts of 5 and handed the template
PID to the electron on every candidate (new knob `profile_min_dqdx_frac`, new verdict bit
`profile_sparse`); (3) the template PID's electron test rejected textbook Bragg muons (new knob
`pid_require_beats_electron`); (4) the stop-unmatched fallback stopped at the first junction
(farthest-vertex walk); (5) collinear 20 cm MIP arms flagged "shower" were called 43-57 MeV
Michels (continuation test no longer consults the shower flag).  Every production chain gates
byte-identical (sec 8).  Thresholds are NOT tuned; the PDHD operating point is two knob values
carried by the runner's TLA and recorded here.

Companion of doc pdvd/48 (`pdvd/docs/nf_sp_img_clus/48_check-stm-michel-chain.md`); the component
itself is documented there.  This doc records the PDHD adoption and the algorithm changes it forced.

## 0. Repro

```
cd /home/xqian/toolkit-dev/toolkit/pdhd
# one event, the new chain (check_stm_michel + tracking_visitor + pr_display), STM fits kept
./run_pr_evt.sh -s mytag -nu -stm-fit 29107 0
# the PDHD operating point of this doc (sec 6) -- the C++ defaults are the doc pdvd/48 behaviour
PDHD_PR_TLA='-S stm_michel_knobs={"profile_min_dqdx_frac":0.15,"pid_require_beats_electron":false}' \
    ./run_pr_evt.sh -s mytag2 -nu -stm-fit 29107 0
# the 30-event arms of this doc (pin = a libWireCell*.so directory; fresh tags only)
ARM=d03nu5 PIN=/home/xqian/tmp/d47_libpin/new7 MODE=-nu JOBS=8 \
    EXTRA='-S stm_michel_knobs={"profile_min_dqdx_frac":0.15,"pid_require_beats_electron":false}' ./docs/scripts/run_d03_arms.sh
python3 docs/scripts/d03_stm_michel_census.py d03nu5 --tsv docs/figs/d03_stm_michel_d03nu5.tsv
python3 docs/scripts/d03_render_candidates.py d03nu5 --out /home/xqian/tmp/d03_render   # one PNG per candidate
python3 docs/scripts/d03_trackfit_vs_stmfit.py work/029107_{0,1,2,3,6,10}_d03nu5           # PR-fit coverage of the STM fit
# compiled-config proofs: PDHD_PR_COMPILE_ONLY=1 ./run_pr_evt.sh -s d03cfg {-stm -stm-fit | -nu -stm-fit | -nu-legacy -stm-fit} 29107 0
```
Inputs: the 30 pctrees `work/029107_<evt>_stm0` (doc pdhd/stm-tagger-chain, our own imaging + Q/L).
Verdict lines: `grep 'CheckSTM_Michel: cluster' work/<dir>/wct_pr_*.log`.

## 1. Wiring (config + runner, PDHD only)

| file | change |
|---|---|
| `cfg/pgrapher/experiment/pdhd/pr.jsonnet` | `pr()` gains `stm_michel_knobs={}`; `cm_by_name.check_stm_michel` after `tagger_check_stm` (same partition-key filter of `tcn_knobs` as PDVD, `pdhd_recomb`, `pdhd_pr_fv` + margins under `stm_consistent_fv`, `mip_dqdx 56000 / mip_dqdx_median 48000`); `tagger_uses` names the recomb model and `pdhd_pr_fv` for the stage; the four PR Bee layers + `bee_pf` read `pr_visitor` / `pr_tail_on` (4 visitor names, 8 gates) |
| `pdhd/wct-pr-perevt.jsonnet` | TLA `stm_michel_knobs = {}`; TLA `excl_t0_frame = true` (sec 4) emitted into `tcn_knobs`; the default `pipeline_names` (production `-stm`) is unchanged |
| `pdhd/run_pr_evt.sh` | `PIPE_NU` = `...,steiner_refresh,check_stm_michel,tracking_visitor,pr_display`; the old tail is `PIPE_NU_LEGACY` behind `-nu-legacy`; header |
| `pdhd/docs/scripts/` | `run_d03_arms.sh` (arm launcher), `d03_stm_michel_census.py`, `d03_render_candidates.py` (static per-candidate panels, the hand-scan substitute), `d03_trackfit_vs_stmfit.py` (fork of pdvd d45) |

Compiled-config proofs (`/home/xqian/tmp/d03_cfg/`, event 029107/0 staged as `d03cfg`):

| proof | result |
|---|---|
| T0 production `-stm -stm-fit`, `-stm`, `-empty`: before vs after every edit of this doc | `cmp` IDENTICAL x3 (md5 a1f231fc / 93e8b228 / 10dc526c) |
| T1 new `-nu -stm-fit` | `CheckSTM_Michel:pr` x5 (pipeline + 3 Bee layers + bee_pf), 0 `TaggerCheckNeutrino:pr`; node carries 49 keys incl. `mip_dqdx 56000`, `mip_dqdx_median 48000`, `fiducial BoxFiducial:pdhd_pr_fv`, `fv_tolerance [-20,-20,-175,-175,-180,-180]` mm, `fit_blob_coverage 0`, `excl_t0_frame true`, `pdhd_track_fitting.json`, `PracticalBoxRecombination:pdhd_box_recomb`; the final driver emits 58 keys incl. the whole sec-6 bag (`profile_min_dqdx_frac 0.15`, `pid_mode 2`, `plateau_mip_lo/hi 0.6/1.6`, `stop_extend_max 3`, `michel_guards_stop`, `michel_shower_min_kink_deg 15`, `stop_fv_use_config_tolerance`, `dead_volume_check`) |
| T2 `-nu-legacy -stm-fit` vs the pre-doc-03 `-nu -stm-fit` | IDENTICAL before the `excl_t0_frame` TLA; after it, identical only with `-S excl_t0_frame=false` (the knob also reaches `tagger_check_neutrino`; the diff is otherwise the work-dir path alias only) -- see gate D |

## 2. Arms (run 029107, 30 events, `work/029107_<evt>_<tag>`, all 30/30 rc=0)

| arm | pin (libWireCellClus.so) | config | purpose |
|---|---|---|---|
| d03nu1 | new5 `1af4cbbf` (the doc-48 binary) | PDHD driver as of doc 48 | baseline: PDVD's stage on PDHD unchanged |
| d03nu2 | new5 | + `excl_t0_frame = true` | the exclusion-frame fix alone |
| d03nu3 | new6 `3482ded8` | knobs at C++ defaults | code changes alone (sparse bit, farthest-vertex fallback) |
| d03nu4 | new6 | `profile_min_dqdx_frac 0.15`, `pid_require_beats_electron false` | the PDHD operating point |
| d03nu5 | new7 `b4bd5aca` | same knobs | + continuation-vs-shower fix |
| d03nu6 | new8 `c557f0ff` | + `pid_mode 2`, plateau window [0.6,1.6], `stop_extend_max 3`, `dead_volume_check`, `min_chain_coverage 0.6` | the full bag, first cut |
| d03nu7 | new9 `ea8d5540` | the driver's default bag as of that pin (coverage off, `michel_guards_stop`) | second cut |
| d03nu8 | new10 `425577d6` | the driver's bag incl. `michel_shower_min_kink_deg 15`, `stop_fv_use_config_tolerance`, Bragg-stub absorption | third cut |
| d03nu9 | **new11 `a4ff5439`** (the shipped binary) | the driver's DEFAULT bag (sec 6; stub absorption knobbed OFF) | THE CENSUS ARM |

Wall per event (median): d03nu1 62.6 s, d03nu5 68.7 s, d03nu7 73.7 s, d03nu8 74.9 s (p90 125 s).

## 3. Baseline: PDVD's stage on PDHD (d03nu1)

The doc pdvd/48 stage ran unchanged on PDHD (arm d03nu1, pin new5, 30 events, 166 STM-tagged
candidates, 62.6 s median wall).  **0 of 166 passed every check.**  `not_muon_pid` was set on 165,
`no_bragg` on 154, and the Bragg contrast was *computable* on only 30 chains.  The per-candidate
panels (`d03_render_candidates.py`) showed why: the PR fit had almost no points.  On the same
clusters the STM tagger's own fit had 5-10x more:

| 029107 evt / cluster | STM-tagger fit points (accepted pass) | PR `T_rec_charge` points | muon-chain profile points |
|---|---|---|---|
| 0 / 56 | 213 | 22 | 6 |
| 1 / 32 | 133 | 61 | 8 |
| 1 / 104 | 360 | 223 | 2 |
| 3 / 25 | 214 | 25 | 10 |
| 3 / 109 | 782 | 162 | 73 |

PDVD (d48nu3) for comparison: PR points = 1.1 x the tagger's on every cluster.  A muon chain with
2 fit points over 42 cm (1/104) is a segment whose fits collapsed to its endpoints -- the doc
pdvd/30 round-2 signature of trajectory-round-1 exclusion contention.  The doc pdvd/45 coverage
grader (`d03_trackfit_vs_stmfit.py`, fork of `d45_trackfit_vs_stmfit.py`) put the dropped fraction
at **42-66 %** of trajectory points per event (doc 45 on PDVD before its fix: 51 %) and the
stm_fit coverage of the PR fit at 0.09-0.51.


## 4. The exclusion frame was live on PDHD (d03nu1 -> d03nu2)

`excl_t0_frame` (doc pdvd/45) was PDVD production since 2026-09-05 and absent from the PDHD
driver: `TrackFitting::update_association` rebuilds each cell's 3-D point in the RAW drift frame and
queries t0-corrected clouds, so on a cosmic with a large t0 every distance is off by metres and one
segment wins every cell.  PDHD never ran a PR tail, so the knob was never wired.  Adding the TLA
(`pdhd/wct-pr-perevt.jsonnet`, emitted into `tcn_knobs`, so it reaches `tagger_check_neutrino` and
`check_stm_michel` and nothing in production) and re-running the same binary (arm d03nu2):

| | d03nu1 | d03nu2 |
|---|---|---|
| dropped trajectory points, 6 graded events | 0.42 / 0.66 / 0.50 / -- / -- / -- | 0.39 / 0.17 / 0.12 / 0.18 / 0.06 / 0.29 |
| stm_fit coverage of the PR fit (clusters with both) | 0.09-0.51 | 0.58-0.96 |
| chains with a computable Bragg contrast | 30 / 166 | 118 / 166 |
| pass every check | 0 | 7 |
| Michel found | 15 | 25 |

The seven passers (1/113, 11/18, 16/110, 20/61, 20/136, 22/119, 22/122) are the seven that
survive every later arm with the electron test on; five are clean stopping muons on the panels
(plateau 52-68 ke/cm, ks_mu << ks_flat, template score 0.06-0.22), 11/18 is an EM-shower core
(sec 6) and 20/61 a wire-parallel track with an oscillating charge profile (sec 9).


## 5. Dead stretches in the profile (d03nu2 -> knob `profile_min_dqdx_frac`)

With the fit points back, `not_muon_pid` still rejected 159/166, and the panels showed the
mechanism: **stretches of the chain with dQ/dx ~ 0** -- 10-30 cm where the fit trajectory follows
the cluster but the charge solve gives the cells nothing (APA edges at z ~ 460 cm, dead-channel
blocks, the anode-hugging x ~ +-351 cm tracks).  Left in the profile they (a) drag the plateau
median to 2-10 ke/cm and manufacture Bragg contrasts of 4-6 (029107/2 cluster 43: tail 45 /
plateau 8 = 5.3 against an expected 2.0), (b) lower the KS/ratio inputs so the near-flat electron
template beats the muon on every chain (electron score < muon score on 18 of 18 candidates that
failed PID alone).

The chain dQ/dx distribution on PDHD (26 936 plateau points, rr > 30 cm) has a median of 49.9
ke/cm = 0.89 x `mip_dqdx` (PDVD d48nu3: 49.6 = 0.90; so the absolute scale is fine) with a broad
low tail: 6.7 % of chain points below 0.15 MIP, 12 % below 0.20.  The knob
`profile_min_dqdx_frac` (C++ default 0 = keep everything) drops points below frac x mip from the
three verdict metrics only -- the persisted point list is untouched -- and a window that ends up
with < 3 live points is "cannot judge": the new bit `profile_sparse` (512) replaces `no_bragg` /
`shape_flat` / `not_muon_pid` there.  Doctest: a 30 cm flat track with its [10, 20] cm stretch at
5 % MIP reads contrast > 5 raw and *invalid* live.

PDHD operating point 0.15 (8.4 ke/cm; nothing physical sits there).  Effect (arm d03nu4 vs nu3,
same binary):

| | knob 0 (d03nu3) | knob 0.15 + pid_mode (d03nu4) |
|---|---|---|
| chains with dead_frac > 0.3 in the last 35 cm | -- | 46 / 166 |
| `profile_sparse` | 46 | 71 (16 as the only bit) |
| `no_bragg` | 80 | 66 |
| contrast >= 2 | 17 / 120 | 9 / 95 (the fakes gone) |


## 6. The template PID, the continuation rule and the unmatched-stop fallback

Four more findings from the panels, each turned into a default-OFF knob (the C++ defaults
reproduce doc pdvd/48 to the bit) or a verdict-only semantic change.

**6.1 The template PID (`pid_mode`).**  With live profiles, 18 candidates were rejected by
`not_muon_pid` *alone*.  Among them 029107/18 cluster 143: a 269 cm muon, plateau 51 ke/cm, tail
104, contrast 2.04 against the tabulated 1.95, ks_mu 0.10 < ks_flat 0.16 -- a textbook stopping
muon -- with `do_track_comp` scores mu 0.40 / p 1.35 / e 0.32 and direction gate 0.  Two things
in the doc pdvd/48 criterion (gate AND mu < p AND mu < e) work against a real muon: the electron
table is near-flat at ~MIP, so it scores within 20 % of the muon on any chain whose Bragg rise the
fit smears; and the gate's ratio term compares the last 35 cm of the DATA (rise confined to the
last ~10 cm) with the table (rise over 35 cm), giving ratio_mu 1.40 on cluster 143.  On the PDVD
census the same criterion held is_stm at 99/574; recomputed from the persisted scores, "gate AND
mu < p" would give 151, and every candidate that passed the gate also beat the proton (178/178) --
the electron test was the only thing the PID bit added.  `pid_mode` 0 = doc pdvd/48; 1 = gate
AND mu < p; 2 = mu < p only (the proton veto; the shape verdict is already carried by
`no_bragg` / `shape_flat`).  PDHD operating point 2.

**6.2 A plateau far from MIP (`plateau_mip_lo` / `plateau_mip_hi`).**  Dropping the electron
test admitted 8 candidates whose plateau reads 15-25 ke/cm (0.27-0.45 MIP) -- five of them in
the x < 0 drift volume, one against the anode at x = +344 cm, one a track 0.2 deg from the
vertical collection wires (sec 9).  Their relative Bragg contrast is real (1.7-3.4) but the charge
is not trustworthy, and the seven that survived the electron test all sit at 52-68 ke/cm.  The
window flags `plateau_med / mip_dqdx` outside [lo, hi] as `plateau_off_mip` (1024); the C++
default `hi <= lo` is off.  PDHD operating point [0.6, 1.6].

**6.3 The tagger's stop is often early (`stop_extend_max`, `michel_guards_stop`).**  doc pdvd/42 sec 4.4 measured a
collinear ~0.9 MIP leftover past the tagger's stop on 26 % of PDVD passes; doc pdvd/48 answered
with the `continuation` bit, which only *rejects*.  On PDHD the continuation arm at the stop was
in three cases the muon itself going on 10-25 cm before its real stop -- 029107/12 cluster 112,
where the Michel (108 deg, 12.7 MeV) is attached one segment past the tagger's kink.  With
`stop_extend_max` > 0 the chain is extended along the longest continuation arm and the stop
re-judged at its far vertex, up to that many times; `n_ext` / `ext_len` record it.  0 = doc
pdvd/48.  PDHD operating point 3.  The first cut (arm d03nu6) walked cluster 112's stop 11 cm to
the anode face and lost its Michel -- the 11 cm arm sat beside a 108-deg Michel at a stop whose
profile already showed the Bragg rise.  `michel_guards_stop` (default false; PDHD on) therefore
(a) stops the extension when the stop vertex has a Michel-class arm or the live profile to it is
already Bragg-confirmed, and (b) reclassifies a collinear arm no longer than `michel_max_len`
beside a Michel at a Bragg-confirmed stop as stop debris (neither continuation nor extension).
On d03nu6, 7 chains were extended (median 21 cm, the stop moved a median 18 cm); with the guard
see sec 7.  Related fix, knob-free: the continuation test no longer
consults the track/shower flag -- 20-24 cm arms at 2-3 deg and 1.2-1.3 MIP carried it on PDHD
(029107/21 cluster 116, 029107/28 cluster 35) and were being called 43-57 MeV Michels.

**6.4 A stop that walks into a dead region (`dead_volume_check`).**  Three PDHD tracks
(029107/14 cluster 116, /25 cluster 54, /27 cluster 118) end on the same line, y = 493 cm at z =
300-340 cm, and the STM tagger's single-track fit bridges 40-60 cm from there to a detached
fragment where it records the "stop".  The muon did not stop; the detector stopped seeing it.
`FiducialUtils::check_dead_volume` (the prototype's ToyFiducial dead-volume walk, already used
by TaggerCheckSTM for one TGM case) is applied from the last LIVE profile point and from the stop
along the chain's last 10 cm; a dead walk sets `stop_into_dead` (2048) and `dead_ahead` = 1.
Default off (needs the fiducialutils stage).  PDHD operating point on.

**6.5 A cluster that is not a track (`min_chain_coverage`).**  029107/11 cluster 18 passed every
check with contrast 3.2: a 65 cm chain threaded through a 1591-point EM blob 40 cm wide, the
"Bragg tail" being the shower core.  `chain_coverage` = the fraction of the main cluster's own 3-D
points within `coverage_radius_cm` (3) of any reconstructed point (chain, deltas, Michel, dots);
below `min_chain_coverage` the candidate gets `cluster_not_track` (4096).  Default 0 = off.
**Measured (arm d03nu6, 0.6): it does not separate.**  Coverage is 0.46 on the EM blob but
0.30 (029107/20 cluster 136) and 0.58 (029107/18 cluster 143) on two clean stopping muons whose
clusters carry wide debris clouds; 37/166 candidates fell below 0.6 (p10 of the distribution
0.48, median 0.91).  The PDHD driver leaves it OFF; `chain_coverage` and `n_cluster_pts` are
persisted so the next scan can look for a discriminator that works.

**6.6 Unmatched stop (knob-free).**  When the tagger's stop has no reachable graph vertex (13 of
166 on PDHD: the tagger bridged into a fragment), doc pdvd/48 walked greedily with
`find_cont_muon_segment`, which on PDHD stopped at the first junction (1-segment, 2-point chains
on 8 of the 13).  The chain is now the shortest route from the entry to the reachable vertex
farthest from it within the main cluster (`stm_michel_farthest_vertex`); `stop_unmatched` stays
set.

**6.8 The muon's own Bragg stub is not a Michel (`michel_shower_min_kink_deg`).**  029107/1
cluster 113, a clean 285 cm stopping muon (tail 121 ke/cm), carried a "Michel" of 5.5 cm at 4 deg
and 1.64 MIP: the partition had split the last 5 cm of the Bragg peak into its own segment and
the track/shower separation flagged it, and the doc pdvd/48 rule admits any shower-flagged arm.
With `michel_shower_min_kink_deg` >= 0 (PDHD 15; -1 = doc pdvd/48) a shower-flagged arm whose kink
is measurable must also turn by that much.  A second idea -- absorbing such a collinear stub (kink <
`continuation_max_angle_deg`, length <= `delta_max_len_cm`, hotter than `continuation_mip_hi`) into
the chain as the true end -- was tried on arm d03nu8 and **failed its one test**: on cluster 113 the
tail window moved onto the fading tip and a clean STM (contrast 1.76) became `no_bragg`; it ships
behind `absorb_bragg_stub`, default off, off in the PDHD bag.

**6.9 Containment with the taggers' margins (`stop_fv_use_config_tolerance`).**  029107/7 cluster
109, a 746 cm muon from y = 8 to y = 597 cm, passed every check including containment: the stage
inset the sensitive volume by a flat `stop_fv_margin_cm` = 5 cm, while every PDHD cosmic tagger
uses `pdhd_pr_fv_margins` (2 / 17.5 / 18 cm in x / y / z).  The stage already receives the same
`fiducial` + `fv_tolerance` as the taggers; with the knob on it applies those per-wall margins to
the stop (PDVD's are 2.5 / 5 / 5 cm).  false = doc pdvd/48.

**6.7 `profile_sparse` (knob-free semantic).**  A Bragg window or compare range with fewer than
3 live points is "cannot judge" and gets bit 512 instead of `no_bragg` / `shape_flat` /
`not_muon_pid`.  `is_stm` is unchanged by this (both reject); the reject *reasons* on PDVD move.


## 7. The census (d03nu5)

Arm **d03nu9** (pin new11, the driver's default bag), 30 events, 166 STM-tagged candidates,
74.4 s median wall per event (p90 125 s; the legacy `-nu` on event 0: 43 s).  The census script's
full output is reproducible from `docs/figs/d03_stm_michel_d03nu9.tsv`.

| | d03nu1 (doc-48 stage as is) | d03nu2 (+ excl_t0_frame) | **d03nu9 (final)** |
|---|---|---|---|
| pass every check (`is_stm`) | 0 | 7 | **8** (4.8 %) |
| `not_muon_pid` / `no_bragg` / `shape_flat` | 165 / 154 / 73 | 159 / 127 / 95 | 1 / 65 / 97 |
| `profile_sparse` (cannot judge) | -- | -- | 71 (16 as the only bit) |
| `plateau_off_mip` | -- | -- | 31 (6 only) |
| `stop_near_boundary` (5 cm flat -> taggers' margins) | 45 | 45 | 67 |
| `continuation` / chains extended past the tagger's stop | 3 / -- | 3 / -- | 3 / 2 (20-25 cm) |
| Bragg contrast computable | 30 | 118 | 95 (live points only) |
| contrast >= 2 | 5 / 30 | 17 / 118 | 10 / 95 |
| Michel found (among passers) | 15 (0) | 25 (1) | 19 (0); kink p10 32 deg, KE p50 3.7 MeV, max 24.6 |
| delta rays / dots | 82 / 3 | 103 / 3 | 103 / 3 |
| PF roots with mu- first / empty | 153 / 0 | 159 / 0 | 159 / 0 |

**The eight passers** (panels under `/home/xqian/tmp/d03_render/d03nu9/`): seven are clean stopping
muons -- 029107/1 cluster 113 (285 cm, tail 121 ke/cm), /16 cluster 110 (378 cm, contrast 2.30, two
deltas), /18 cluster 143 (269 cm, contrast 2.04), /20 clusters 61 (108 cm) and 136 (302 cm), /22
clusters 119 (54 cm, tail 89) and 122 (275 cm, tail 103); plateaus 0.91-1.22 MIP, ks_mu 0.02-0.10 <
ks_flat 0.08-0.16.  The eighth, /11 cluster 18, is the EM blob of sec 6.5 -- the one known false
positive, kept because the coverage guard could not remove it without also removing two of the
seven.  None of the eight has a Michel: /1 cluster 113's 5.5 cm 1.6-MIP stub is now correctly not
one, and the one genuine mu + Michel of the sample (/12 cluster 112: 127 cm, Michel 11.5 cm at 108
deg, 12.7 MeV, one dot) sits at x = 344 cm against the anode where its plateau reads 0.44 MIP and
`plateau_off_mip` rejects it.  The 8/166 is therefore a floor set by charge quality, not by the
Michel search: 71 candidates could not be judged (dead stretches), 31 have untrustworthy charge,
67 stop within the taggers' margins.

**PDVD with the same bag** (arm d48nu7, 120 events, 574 candidates, pin new11) against the doc-48
census (d48nu3): `is_stm` 99 -> **148** (25.8 %): 50 gained (49 of them rejected before by the
electron test alone, 1 by the flat-inset containment), 1 lost (`plateau_off_mip`); Michels among
passers 39 -> 55, Michels overall 137 -> 123 (the collinear shower-flagged ones became
continuations / not-Michels; kink p10 21 -> 31 deg); 7 chains extended past the tagger's stop;
`dead_volume_check` fired on 2.  Wall 23.5 s median.  NOT adopted for PDVD: the 50 movers need the
owner's scan first (sec 10).

Bit relabels that leave `is_stm` unchanged (PDVD d48nu4, C++ defaults on the new binary): 28 of
574 -- 21 `no_bragg` -> `profile_sparse`, 6 shower-flagged collinear "Michels" -> `continuation`,
1 unmatched-stop chain re-walked; 0 `is_stm` flips.


## 8. Gates (byte identity of everything production)

Every production chain must not move.  Pins under `/home/xqian/tmp/d47_libpin/`: `ref`
(libWireCellClus e3304cb9, the pre-doc-48 binary), `new5` (1af4cbbf, doc 48 as shipped), `new6`
(3482ded8: live profile, sparse bit, farthest-vertex fallback, electron knob), `new7` (b4bd5aca:
+ continuation ignores the shower flag), `new8` (c557f0ff: + pid_mode, plateau window, chain
extension, dead-volume bit, coverage guard), `new9` (ea8d5540: + `michel_guards_stop`), `new10`
(425577d6: + `michel_shower_min_kink_deg`, Bragg-stub absorption, `stop_fv_use_config_tolerance`),
**`new11` (a4ff5439: the stub absorption behind `absorb_bragg_stub`, default off -- THE SHIPPED
BINARY)**.  libWireCellRoot 4a9efb7f and every other libWireCell*.so are identical across
new5..new11 (only `clus/` changed; checked pairwise at every pin).  Freshness (new11):
local/lib/libWireCellClus.so 22:22:39 > last source edit 22:22:13; doctests `wcdoctest-clus
-tc='*stm_michel*,*CheckSTM_Michel*'` 9 cases / 325 assertions SUCCESS (new: farthest vertex, live
profile, shower-flagged continuation and stub, the defaults of every new knob); the full
`wcdoctest-clus` suite 322 cases / 23036 assertions SUCCESS (on new9; every later edit touched
only knob-gated branches and the targeted doctests were re-run at each pin).

Comparer `/home/xqian/tmp/d03_arms/compare.py` (zip / tar members by content hash, calib JSON with
timers stripped, tsv bytes, ROOT trees via `hash_root_trees.py --per-tree`; a MISSING side fails
the pair -- never a vacuous SAME).  Launchers `launch_gates{1,2,3}.sh`, rc files `rc{1,2,3}.txt`
(every job rc=0).  Reference arms are doc 48 round 2 (ref pin): PDVD `d48stmref2` / `d48legref2`
(039252/2, 039349/23), PDHD `d48ref2` (029107/0, the old `-nu`), SBND `work-stmcamp-d48gateold2`
(284349 285999 286065); the PDHD `-stm -stm-fit` reference `d03stmref` (events 0, 6) was run
fresh on the ref pin in round 1.

| gate | chain | pairs | new6 (r1) | new7 (r2) | new8 (r3) | new9 (r4) | new10 (r5) | new11 (r6) |
|---|---|---|---|---|---|---|---|---|
| A | PDVD production `-stm -stm-fit`, zip + tracking-stm trees, 2 events | 4 | PASS | PASS | PASS | PASS | PASS | PASS |
| B | PDVD `-nu-legacy -stm-fit`: zip, calib, tracking-pr (T_kine T_tagger T_rec_charge), tracking-stm, 2 events | 8 | PASS | PASS | PASS | PASS | PASS | PASS |
| C | PDHD production `-stm -stm-fit`, zip + tracking-stm trees, events 0 and 6 | 4 | PASS | PASS | PASS | PASS | PASS | PASS |
| D | PDHD `-nu-legacy -stm-fit` with `-S excl_t0_frame=false`, zip + tracking-pr + tracking-stm, event 0 | 3 | PASS | PASS | PASS | PASS | PASS | PASS |
| E | SBND bare production (`run_d42_stmfit.sh`, `D42_NO_STMFIT=1`): zip, pctree tar, nusel tsv x 3 events | 9 | PASS | PASS | PASS | PASS | PASS | PASS |

Gate D as first run (round 1, without `-S excl_t0_frame=false`) DIFFERED on the zip's PR layers
and tracking-pr.root while tracking-stm.root stayed SAME: the new driver TLA reaches
`tagger_check_neutrino` too, so the PDHD legacy tail now runs with the exclusion-frame fix (a
deliberate config change, sec 4); the binary is inert on it (D passes with the old config).
T2 in sec 1 is the compiled-config form of the same statement.


## 9. What PDHD says about itself (observations, no action taken)

These came out of the panels and the TSVs; none was acted on beyond a verdict bit.

1. **Charge scale.**  Chain dQ/dx at rr > 30 cm: median 49.9 ke/cm = 0.89 x mip_dqdx (PDVD 0.90),
   flat in |x| from 0 to 320 cm (46.8-53.6), 34 ke/cm in the last 32 cm before the anode.  But
   **x < 0 reads 44.5 and x > 0 reads 53.5 ke/cm** (14 197 / 12 739 points): a 20 % difference
   between the two drift volumes that a per-TPC calibration would remove; 5 of the 8 low-plateau
   passers of sec 6.2 are in x < 0.
2. **Wire-parallel tracks.**  029107/18 cluster 41 (504 cm, 0.2 deg from the y axis = the
   collection-wire direction) and 029107/20 cluster 61 (14 deg) have dQ/dx profiles oscillating
   20-90 ke/cm with a 30-50 cm period and (cluster 61) a fit trajectory zig-zagging +-3 cm in x
   across a straight track that the PR partition cut into 7 segments.  The 2-D -> 3-D charge
   unfolding is degenerate when a track projects onto one collection wire; both pass the verdict
   on relative metrics.  A direction-to-wire angle bit is the obvious next guard; not added tonight
   because 2 of 30 events is not a population.
3. **The y = 493 cm line** (sec 6.4): three tracks in APA1 (z 300-340) end on it.  A dead block
   below y = 493 in apa1-face1 fits the Bee `channel-deadarea-apa1-face1` layer being the only
   APA1 dead-area file in the zip; the dead-volume bit now covers it, but the tagger's own fit
   still bridges 40-60 cm into fragments there.
4. **Zero-charge stretches** are concentrated at the APA boundaries (z ~ 230, 460) and along the
   anode faces (|x| > 345); 46/166 chains have > 30 % dead points in their last 35 cm.
5. **PR-fit point-to-point noise** (relative RMS of successive plateau dQ/dx): PDHD 0.13 (tagger
   fit 0.17), PDVD 0.20 (0.23) -- the PDHD fit is not noisier; the oscillations of item 2 are
   trajectory, not noise.
6. **Timing.**  With the exclusion frame on, the new chain runs 62.6 -> 68.7 s median per event
   (p90 109 -> 119 s) against 43 s for the legacy `-nu` on event 0; `CheckSTM_Michel` itself is
   0.3-27 s per event, dominated by the per-candidate fitter on 500-800 cm tracks.


## 10. Files, commits, next steps

**Toolkit (`apply-pointcloud`, commit `5d0b4e77`):** `clus/inc/WireCellClus/StmMichelFunctions.h`,
`clus/src/StmMichelFunctions.cxx`, `clus/src/CheckSTM_Michel.cxx`, `clus/test/doctest_stm_michel.cxx`,
`clus/test/doctest_check_stm_michel_defaults.cxx`, `cfg/pgrapher/experiment/pdhd/pr.jsonnet`.
**wcp-porting-img (`main`, the commit carrying this doc):** `pdhd/wct-pr-perevt.jsonnet`, `pdhd/run_pr_evt.sh`, this
doc, `pdhd/docs/scripts/{run_d03_arms.sh,d03_stm_michel_census.py,d03_render_candidates.py,d03_trackfit_vs_stmfit.py}`,
`pdhd/docs/figs/d03_stm_michel_{d03nu1,d03nu2,d03nu9}.tsv` (one row per candidate, every verdict input),
`pdhd/docs/figs/d03_stm_michel_d48nu7.tsv` (the PDVD arm with PDHD's bag), `pdhd/stm/gates/d03_stm_michel_gate.txt`,
`pdvd/docs/nf_sp_img_clus/48_check-stm-michel-chain.md` (sec 10 addendum) and its census script.

**Not done / owner decisions.**
1. ~~PDVD keeps the C++ defaults (= doc pdvd/48).~~  **DONE 2026-09-06 (owner flip):** the whole
   sec-6 bag is now the default of `stm_michel_knobs` in `pdvd/wct-pr-perevt.jsonnet`, so PDVD and
   PDHD share one operating point.  Sec 7's d48nu7 numbers (99 -> 148 `is_stm`, 39 -> 55
   Michel-carrying passers) are the pre-flip measurement; PDVD `-stm` and `-nu-legacy` compiled
   configs proven byte-identical, SBND untouched (it never instantiates the stage).  See
   `pdvd/docs/nf_sp_img_clus/48_check-stm-michel-chain.md` sec 11 -- which also carries the
   sole-bit census: `shape_flat` is now the dominant rejector (69 sole, 26 of them Michel-carrying)
   and is the next round's target.  The purity of the +49 is still un-scanned.
2. The PDHD operating point (sec 6) was chosen by reading ~40 panels of 166 candidates, not by a
   blind scan; the `d03_render_candidates.py` PNGs under `/home/xqian/tmp/d03_render/d03nu9/` are
   the scan sheet.  A Bee upload of `d03nu7` is ask-first and was not done.
3. `dead_volume_check` fired on 0 of 165 evaluated candidates although three tracks end on the
   y = 493 cm dead line (sec 6.4): either the PR job's FiducialUtils carries no dead-channel map
   for PDHD or the walk is satisfied by the first 4 cm.  Left ON in the bag for the record; needs a
   `WCT_..._DUMP`-style probe before it is trusted.
4. `min_chain_coverage` does not separate (sec 6.5); the persisted `chain_coverage` is the input
   for a better shape test (transverse width of the cluster about the chain?).

   > **2026-09-07** -- sec 10 item 2 of this doc noted that the PDHD operating point was chosen by
   > reading ~40 panels of 166 candidates, "not by a blind scan".  `doc pdhd/12`
   > (`pdhd/stm_michel_scan/`) is that scan, built as an interactive display for both detectors:
   > 3-D + X-Y / Y-Z / Z-X projections over the imaged charge, the fitted chain with its dQ/dx, a
   > hand-placed stopping point labelled by APA / CRU, and the chain's own answer behind a REVEAL
   > toggle that every label records.
5. Wire-parallel tracks (sec 9 item 2) need a direction-to-wire angle guard; the x < 0 / x > 0
   charge asymmetry (sec 9 item 1) is a calibration question for the detector.
6. The STM tagger itself still bridges its single-track fit 40-60 cm into detached fragments and
   records the fragment as the stop (sec 6.4, 6.6); the stage recovers the chain but the tagger's
   `stm_fit` layer and verdict carry the bridge.
7. `-nu-legacy` on PDHD now runs with `excl_t0_frame` (sec 4); `-S excl_t0_frame=false` restores the
   pre-doc-03 tail byte-for-byte (gate D).

8. **doc pdhd/13** measured three loss modes in the Michel search on the `d51hnu`/`d51vnu` arms:
   the companion admission gate is `dot_max_len_cm` (`:812`), so a detached Michel longer than
   10 cm never enters the PR at all; `michel_found` is set only by the attached path (`:1169`), so
   33 PDHD / 41 PDVD candidates carry a reconstructed Michel that is never reported; and on
   74 % (PDHD) / 67 % (PDVD) of the `is_stm & no Michel` set the PR fitted segments that the arm
   classifier then discarded.  Fixes specified there as default-OFF knobs; none applied yet.
9. **doc pdhd/14** persists the muon energy this module already computed and threw away, plus the
   daughter segment id that closes the `mu -> e` edge on the attached path.  Four new
   `T_stm_michel` branches, default on (owner 2026-09-07), 75 pre-existing branches bit-unchanged.
10. **doc pdhd/15** makes the Michel **one object** — the stop arm (or, when the 3-D clustering
   detached it, the nearest admitted piece), the shower completion, and every fitted segment of an
   admitted companion — energised once through `PatternAlgorithms::calculate_shower_kinematics`.
   Fixes doc pdhd/13's D1 and D2 and an energy-accounting bug that left the pieces out of
   `michel_ke_best` (PDVD 039252_15 cluster 91: 16.2 MeV reported for a 29.2 MeV Michel; 9 PDHD /
   17 PDVD candidates, missing fraction median 22.5 % / 12.2 %).  Nine new `T_stm_michel` branches;
   `dot_max_len_cm`'s default moves 10 -> 25 cm and `companion_max_len_cm` is new at 25.
