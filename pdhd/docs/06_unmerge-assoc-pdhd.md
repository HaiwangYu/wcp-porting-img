# PDHD doc 06 — `unmerge_assoc` on PDHD: it was never wired, and the reason on file was wrong

**Owner, 2026-09-06:** *"For the PDHD chain, I wonder if you have the unmerge implemented already?
… if not, it should be added, like what we did for PDVD, and then regenerate the bee link for me."*

Short answer: **no, it was not**, and the comment in `run_pr_evt.sh` explaining why was **factually
wrong**. It is now added, default-OFF and gated, with runner flags on both jobs. What it does on
PDHD is substantial — 40–46 main clusters split per event — but it does **not** recover the two
stopping muons of [doc 04](04_stm-tagger-scan.md) §12 item 0.

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd

# clustering must record the provenance; PR consumes it
./run_clus_evt.sh -q -save-pctree -save-assoc -s <tag> 029107 <evt>
./run_pr_evt.sh   -stm-fit -unmerge          -s <tag> 029107 <evt>

# the arms this doc is measured on (binary pinned, libWireCellClus md5 495ed07e…,
# toolkit ef995685 + this change; events 1 and 12 of run 029107)
#   d06um    -save-assoc clustering + -unmerge PR
#   d06base  the SAME pctree, PR without -unmerge   (the control)

python3 docs/scripts/d05_arms_bee.py --dirs work/029107_{1,12}_d06um \
        --out bee-pr-run029107-d06um --highlight 1:113,12:108
```

## 1. The answer, in three parts

**The C++ exists and is detector-agnostic.** `ClusteringUnmergeBundle` (`clus/src/`) is the same
component SBND and PDVD use.

**The PDHD config already carried the visitor definition** — `cfg/pgrapher/experiment/pdhd/pr.jsonnet`
defines `unmerge_assoc` — because that block was forked from PDVD together with its comments. It
was in no PDHD pipeline, so it never ran.

**And it could not have worked if it had been named**, because the prerequisite was missing: the
PDHD clustering job wrote no `assoc_cluster_id` / `assoc_cluster_main` perblob arrays, so the
visitor had nothing to undo and would have been **silently inert**.

## 2. The reason on file was wrong, and the wrong reason hid a real defect

`run_pr_evt.sh` said:

> *"unmerge_assoc is DELIBERATELY absent: PDHD's clustering runs no `cm.isolated()` merge (the
> defect doc pdvd/39 round 2 undoes on PDVD), so there is no isolated grouping to split and the
> stage would be inert."*

The first clause is false. From the **compiled** PDHD clustering config, not the jsonnet source:

| | |
|---|---|
| `ClusteringIsolated` instances | **2** — `group02`, `group13` |
| where | the per-drift-group MABC pipelines (`clus_per_group-group02/13`), 12 visitors each |
| `save_assoc_cluster_id` keys | **0** |

And `cm.isolated()` **merges**. `clustering_isolated.cxx` is explicit that `save_assoc_id` gates
only the *recording*: *"Default false => `merge_clusters()` is called exactly as before and no
[provenance]"*. So PDHD has been physically absorbing detached clumps into main clusters all along
— the same defect doc pdvd/39 round 2 found on PDVD, where it made the STM endpoint finder and the
Steiner build walk across empty space into a clump that is not part of the track.

The conclusion "the stage would be inert" was right; the reason was not. The distinction is not
pedantic: the wrong reason says *there is nothing to undo*, and there is quite a lot to undo (§5).

## 3. What was added

Mirrors PDVD exactly (`protodunevd/clus.jsonnet` `save_assoc_id`, doc pdvd/39 r2).

| file | change |
|---|---|
| `cfg/pgrapher/experiment/pdhd/clus.jsonnet` | `save_assoc_id` arg on `clus_per_group` and `clus_all_tpc` (+ both public wrappers); threaded into `cm.isolated(save_assoc_id=…)` and into the `save_assoc_cluster_id` key on all three MABCs |
| `pdhd/wct-clustering.jsonnet` | `clus_save_assoc_id = false` TLA, passed to `per_group` and both `all_tpc` branches |
| `pdhd/run_clus_evt.sh` | `-save-assoc` (env `PDHD_SAVE_ASSOC`); records `save_assoc_id=` in the pctree `.tlas` sidecar, read out of the **compiled** config |
| `pdhd/run_pr_evt.sh` | `-unmerge` / `-nounmerge`; inserts `unmerge_assoc` after `flag_mains`, before `steiner`; **plus the guard below**; and the wrong comment replaced by what is true |

**Ordering** is PDVD's (doc pdvd/39 §11): after `flag_mains` so the split-off fragments are removed
from the main's Steiner build and STM fit *without* being promoted to mains and given cosmic
verdicts of their own; before `steiner` because `separate()` does not carry node-local PCs, so the
split must precede `steiner_pc` creation.

**The guard.** On a pctree written without `-save-assoc`, `unmerge_assoc` finds no provenance and
is silently inert — the run looks normal and is not. That silence is the exact failure this whole
doc is about, so `run_pr_evt.sh` now refuses:

```
ERROR: … the pipeline contains unmerge_assoc but this pctree carries no isolated-merge
       provenance (save_assoc_id=absent).
       Re-run clustering with: ./run_clus_evt.sh -q -save-pctree -save-assoc -s <tag> 029107 1
```

Verified: rc **4**, nothing written. It is keyed on the **selected pipeline**, not on the
`-unmerge` flag — a guard keyed on the flag that used to select a behaviour goes blind the moment
the behaviour becomes a default (`project_doc38_39_unmerge_flip`).

## 4. Gates

| gate | result |
|---|---|
| compiled clustering config, knob **off**, vs before the change | **byte-identical** (md5 `0806645a169b2768f9c0d4130c2abb11`) |
| compiled clustering config, knob **on** | 3 × `save_assoc_cluster_id`, 2 × `save_assoc_id` — the compiled-config proof |
| clustering Bee `mabc-all-apa.zip`, `-save-assoc` vs `d05mON` | **identical member content** both events (`1d762209…`, `f5f864cb…`) |
| **control**: same pctree, PR *without* `-unmerge`, vs `d05mON` | **identical member content** both events (`ce10012d…`, `504efac5…`) |
| guard: `-unmerge` on a provenance-less pctree | rc 4, refused |

The control is the one that matters: writing the three provenance arrays changes **nothing** in the
PR output, so everything in §5 is `unmerge_assoc`'s doing and not a side effect of recording. The
pctree file itself is *not* byte-identical — it gains the arrays — which is why `-save-assoc` is a
flag and not a default.

## 5. What it does on PDHD

Events 1 and 12 of run 029107, one binary, the same pctree in both arms:

```
ClusteringUnmergeBundle:prassoc  unmerged 40 main cluster(s) into 323 associated cluster(s)
                                 (40 exact/provenance, 0 proxy/component)     [evt 1]
                                 46 -> 243   (46 exact, 0 proxy)              [evt 12]
```

Every split came from **exact provenance**, none from the component-mode fallback. The 38 / 42
`no flash-merge provenance … not split` warnings are the cosmetic ones (clusters
`clustering_isolated` never touched, so there is nothing to undo) — doc pdvd/39 §14.

| | evt 1 base → um | evt 12 base → um |
|---|---|---|
| clusters in the PR Bee | 86 → **418** | 126 → **360** |
| 3-D points (unchanged: membership is redistributed, nothing lost) | 153 706 | 161 854 |
| TGM evaluated | 82 → 82 | 92 → 92 |
| TGM = true | 35 → **36** | 23 → **24** |
| STM evaluated | 47 → 46 | 69 → 68 |
| **STM tagged** (a count — the *set* changes, see below) | 4 → 4 | 8 → 8 |
| STM fitted | 20 → 16 | 26 → 22 |

> **CORRECTION 2026-09-06 (see §8.4).** The "STM tagged 4 → 4 / 8 → 8" row above is a **count**,
> and reading it as "the STM tags do not move" was wrong. Matched by point set rather than by
> ident, event 1 replaces **all four** tags (zero overlap: 46/57/92/104 out, 32/42/82/85 in) and
> event 12 changes six of eight (25/112/125 out, 32/95/129 in) — **14 tag changes behind an
> unchanged count**, `feedback_count_vs_set_census` walked straight into. One of the new tags is a
> false positive with a named mechanism (§8.4).

TGM-evaluated is unchanged because the split-off fragments are **not** promoted to mains — that is
what the `flag_mains`-before-`unmerge_assoc` ordering buys. So the defect is real and large in
cluster count (40–46 mains per event were carrying detached clumps) while the tagger verdicts move
little **in aggregate** on these two events: +1 TGM each, the same number of STM tags on a largely
different set of objects, 8 fewer STM fits.

**Sign unknown — this is not graded.** Two events is not a measurement, and doc pdvd/39 made the
same point about PDVD: fewer fits may be correct (a clump dragging a main into a fit should stop
doing so) or may be a loss. Do not flip the default on this.

## 6. It does **not** recover the two lost stoppers

That was the hypothesis worth testing — both are multi-component clusters, which is the signature
of an isolated-merge. Unmerge cleans them up and the verdict does not move.

| | evt 1 cluster 113 | evt 12 cluster 108 |
|---|---|---|
| components, base → um | **8 → 1** | **6 → 2** |
| points in the main | 1 955 → 1 866 | 6 714 → 6 670 |
| STM | 0 → 0 | 0 → 0 |
| fit | status 7, kink 453 → status 7, kink 452 | status 2 → **no STM fit at all** |
| FC | false → false | false → **true** |

**Cluster 113 is now a single component and is still rejected by the same accept guard** (status 7,
`accept_guards_reject`), with a fit that did not move (kink 453 → 452). So the merge was not what
was wrong with it: the desert/spike guard is, and doc 04 §12 item 0 stands unchanged for this one.

**Cluster 108** loses its STM fit entirely and is now called fully contained. Its kink relocation
(doc 05 §8.1) is not explained by the merge either.

Reading these two out is what the Bee links below are for.

## 7. Bee links

| | link |
|---|---|
| **without** unmerge (`d06base`; identical to `d05mON` by the §4 control) | https://www.phy.bnl.gov/twister/bee/set/e2793916-8704-4a70-b41e-27c17509990d/event/list/ |
| **with** unmerge (`d06um`) | https://www.phy.bnl.gov/twister/bee/set/93edc720-18d1-4cd2-9dfb-11fb985c2dc1/event/list/ |

Slot 0 = event 1 (cluster 113), slot 1 = event 12 (cluster 108), both sets. All layers —
`clustering`, `stm`, `stm_fit`, `stm_tagged`, `steiner_graph`, `steiner_terminals`,
`channel-deadarea-*` — plus a `scan` layer holding just the highlighted cluster. Verified from the
server: 7 layers × 2 events listed in each set.

The earlier pair from doc 05 §8 (pre-fix vs fixed) stays valid and is a different comparison.

## 8. Owner 2026-09-06: event 991, (119.2, 96.2, 379.6), cluster 290 "strange for the Steiner-Graph"

Two answers: cluster 290 has **no Steiner graph at all** and that is the display scope, not a bug —
but checking it turned up something that does matter for this feature.

### 8.1 Which set, and what cluster 290 is

That coordinate is cluster 290 in **exactly one** arm on disk. Every other event-991 arm (27 of
them, `stm0` / `d02*` / `d03*` / `d04bee` / `d05m*` / `d06base` …) calls it **cluster 83**:

| | |
|---|---|
| `d06um` (the with-unmerge link, §7) | cluster **290**, 11 points |
| everything else | cluster **83**, 12 289 points |

So cluster 290 is an 11-point clump that `unmerge_assoc` split off cluster 83 — and cluster 83 is
one of the `TGM_gained` movers of doc 04 §10.3, hand-labelled **THRU**. The clump has **nothing
within 50 cm**; the muon's body passes 50–80 cm away (1 032 points of cluster 83 within 80 cm, none
within 50). That is the isolated-merge signature doc pdvd/39 r2 describes almost exactly ("a
938-point body plus nine 5–19 point fragments at 16–76 cm"), so splitting it off is the intended
behaviour, not the anomaly.

### 8.2 Why it has no Steiner graph — and neither does its 12 289-point parent

`pr.jsonnet` scopes the three layers with **`require_pc: 'stm_fit'`**, so `stm`, `steiner_graph`
and `steiner_terminals` cover exactly the clusters `TaggerCheckSTM` recorded a fit for. Proof, not
inference — the layer's cluster set equals the `persist_stm_fit` set exactly, both arms:

| arm | clusters | `steiner_graph` clusters | `persist_stm_fit` clusters |
|---|---|---|---|
| `d06base` | 86 | 20: `29 34 36 37 40 45 46 50 57 73 82 85 88 92 95 99 100 101 104 113` | the same 20 |
| `d06um` | 418 | 15: `29 32 36 37 40 42 50 73 82 85 88 95 101 104 113` | the same 15 |

Cluster 290 is a fragment, never promoted to a main, never evaluated — no fit, no layer. **And
cluster 83 has no Steiner graph either**, in any arm: it is `TGM=true`, so `TaggerCheckSTM: cluster
83 already TGM; skipping`. Measured: **zero** Steiner, terminal, `stm` or `stm_fit` points within
80 cm of that coordinate, in both arms. Nothing is drawn there because nothing is meant to be.

### 8.3 The thing that does matter: the retile undoes the split

Looking at the Steiner layer for the rest of the event, one cluster stands out. Cluster **36**:

| | `d06base` | `d06um` |
|---|---|---|
| charge points | 2 650 | 1 581 (unmerge split off 442 / 439 / 444 / 446 …) |
| Steiner nodes | 2 848 | 2 834 |
| nodes on **its own** charge | 2 848 / 2 848 | 1 759 / 2 834 |
| nodes on **another cluster's** charge | **0** | **1 075** → 521 on cl 442, 173 on cl 439, 112 on cl 444, 80 on cl 446 |

Every one of those four clusters was part of cluster 36 before the split (verified point-for-point,
max match distance 0.000 cm). **So the Steiner build puts 38 % of cluster 36's nodes back on the
charge `unmerge_assoc` had just removed from it.**

The mechanism is in the code, not a guess. `steiner: cm.steiner(retiler=improve2, …)`, and
`ImproveCluster_1::get_activity_improved` (`improvecluster_1.cxx:256`) takes the cluster's
**(u, v, w, t) bounding box** — `get_uvwt_min/max` — and asks the *Grouping* for every good channel's
charge inside it:

```cpp
map_u_tcc = grouping->get_overlap_good_ch_charge(min_time, max_time, min_uch, max_uch, apa, face, 0);
```

There is **no cluster-membership filter**. Any charge inside the box is retiled back in, whoever
owns it. Unmerge removes the fragments in 3-D; the main's bounding box still contains them; they
return in 2-D.

**This is pre-existing and not caused by unmerge** — that had to be checked before blaming the new
feature. Over event 12 the fraction of Steiner nodes sitting on another cluster's charge is
**7.9 % in both arms** (4 242 / 53 585 vs 4 024 / 50 728); the mechanism is simply how the retiler
has always worked. What unmerge changes is *whose* charge it is: a main's own split-off fragments
now count as "another cluster", so on event 1 the fraction goes 0.1 % → 4.8 %, essentially all of
it cluster 36.

**The consequence for this feature is the one worth stating: the unmerge split does not reach the
Steiner build.** Whatever it removes in 3-D comes back through the 2-D bounding-box retile, so the
STM fit still walks over the fragments' charge. PDVD carries the identical wiring
(`protodunevd/pr.jsonnet:1410`, `cm.steiner(retiler=improve2, …)`), so the same limitation presumably
applies to the shipped PDVD unmerge — **measured here on PDHD only**, and worth checking there
before anyone leans on either.

### 8.4 Owner 2026-09-06: (-41.9, 12.3, 450.1), cluster 42 — a gutted main, and a false STM tag

This one is a defect of the feature, not of the display. Cluster 42's Steiner graph draws a
continuous 27 cm track through charge that is three dots.

**What the cluster is.** In `d06base` cluster 42 is 293 points / **180 blobs**, 36 components,
sprawling x −325…−1.6, y 7.6…85.6, z 394…462 — junk along the detector floor (y floor 7.61) near
the z+ edge. The tagger handled it correctly: **TGM=true**, and `TaggerCheckSTM: cluster 42 already
TGM; skipping`.

**What unmerge does to it.**

```
ClusteringUnmergeBundle:prassoc> cluster 42: 180 blobs -> main 16 + 36 associated cluster(s)
                                 holding 164 (real mode)
```

**164 of 180 blobs leave. The main keeps 8 % of itself — 19 points — and keeps the main flag**,
because `flag_mains` ran *before* `unmerge_assoc`. The ordering that stops fragments being promoted
to mains does nothing to stop a main being hollowed out and staying one.

The remnant is four dots along the drift axis:

| | x [cm] | y | z | pts |
|---|---|---|---|---|
| dot 1 | −145.6…−144.7 | 15.6 | 456.3 | 4 |
| dot 2 | −42.9…−41.9 | 12.3–14.7 | 450.1 | 7 |
| dot 3 | −37.5…−36.6 | 12.9 | 450.6 | 4 |
| dot 4 | −17.0…−16.1 | 14.3–15.1 | 451.5 | 4 |

Gaps of **103, 5 and 20 cm**; `component_extreme_wcps: cluster 42 4 component(s), **0 above 10.0
cm**`.

**Then the verdict flips.** With the connecting charge gone, the TGM chord test can no longer walk
it —

```
check_tgm: cluster 42 CASE-A pair (0,1) rejected: no 30.0 cm-step charge path between the ends
           (129.6 cm chord)
```

— so **TGM goes true → false**, the cluster falls through to `TaggerCheckSTM`, and the Steiner build
fabricates a track to fit: **84 of its 88 Steiner nodes fill x −42.86…−16.07 continuously** (26.8 cm)
where the charge is three dots totalling 15 points; 7 terminals. STM then fits **220 points** —
eleven times the real charge — and returns **STM=1**, `exit_L 131.6 cm`.

**A junk cluster that was correctly tagged through-going becomes a false stopping-muon tag.**

It is the only case of its kind in event 1: of the four new STM tags, 42 is the one where unmerge
gutted the main (16/180 = 8 %) and flipped TGM. The other three (32, 82, 85) kept 77–91 % of their
blobs and were TGM=false in both arms, so their 0→1 flip is the cleanup working as intended. Four
objects also *lost* their tag (46, 57, 92, 104).

**What this says about the feature.** Two things, both unaddressed:

1. `flag_mains` before `unmerge_assoc` protects against fragment→main promotion but not against
   main→remnant. A main reduced to 8 % of its blobs should arguably be re-tested for main-ness, or
   dropped.
2. Losing TGM by losing the charge path is a **mechanical** consequence of the split, not a physics
   re-judgement: the object did not change, only which points are labelled as belonging to it. Any
   cluster whose TGM verdict rests on a charge path that unmerge is about to remove will flip the
   same way. Ordering `unmerge_assoc` *after* the cosmic taggers would avoid it, at the cost of the
   Steiner/STM cleanup the feature exists for — the trade PDVD's §11 ordering decision made without
   this case in view.

### 8.5 Owner 2026-09-06: "why can the Steiner graph jump through gaps?" — and what PDVD/SBND are missing

Because it is built to. The Steiner cloud is **not** the cluster's measured charge: `steiner:
cm.steiner(retiler=improve2, …)` on all three detectors, and `ImproveCluster_2::mutate` assembles
the activity it tiles from three sources, two of which reach past the charge.

**(1) A hard-coded 20 cm reach over real activity.** `ImproveCluster_1::get_activity_improved`
takes the cluster's (u, v, w, t) bounding box, pulls every good channel's charge and every
dead-channel range inside it from the *Grouping* — the whole event's 2-D activity, no
cluster-membership filter — and admits each one whose 2-D (drift, wire) point is within

```cpp
const double dis_cut = 20 * units::cm;            // improvecluster_1.cxx:378
… if (sqrt(ret_matches[0].second) > dis_cut) continue;   // :419  (good)   :405 (dead)
```

of the cluster's own 2-D projection, **independently per plane**. Faithful port — the prototype has
the same constant three times (`ImprovePR3DCluster.cxx:209, 750, 1433`). **It is not reachable from
jsonnet on any detector.** On PDHD 20 cm is ≈ 63 time slices and ≈ 43 wires at the 4.67 mm pitch.

**(2) Synthetic activity painted along the cluster's own path, with no length limit.**
`hack_activity_improved` (`improvecluster_1.cxx:454`) takes the shortest path between the cluster's
two boundary points, interpolates it at `low_dis_limit = 0.3 cm` (`ncount = int(dis/0.3) + 1`,
**uncapped**), and wherever the path is not already covered by activity in all three planes, it
**invents** some:

```cpp
for (int dt = -3; dt <= 3; dt++)
  for (size_t plane = 0; plane < 3; plane++)
    for (int dw = -3; dw <= 3; dw++) {
      if (… || pow(dw,2) + pow(dt,2) > 3*3) continue;
      if (measures.at(wire) > 0.0) continue;
      measures.at(wire) = 1.0e-3;                 // Set activity
    }
```

A 7×7 disc of fake activity in **all three planes**, every 0.3 cm along the path.
`ImproveCluster_2::mutate` calls it **twice** — once on the original cluster's path, once on the
retiled cluster's path. RayGrid then tiles blobs out of that, they are sampled, and the Steiner
tree is built on the result.

So the answer to "how can it jump a gap" is: it does not jump one — **it fills it in first**. The
reach is not a distance parameter at all, it is *whatever the cluster's own graph connects*, and
the painting has no cap.

Cluster 42 shows both limits at once. Its 84 nodes fill x −42.86…−16.07 at a median spacing of
**0.315 cm — exactly one time slice** — straight across the 5 cm and 20 cm gaps. The **103 cm gap
is not filled**, because the graph never connected that component, so no path ran through it.

### 8.6 The guard for this exists; it is ARMED on PDHD and PDVD, absent on SBND

> **CORRECTION (2026-09-06).** The first version of this section said `bad_blob_max_run` was OFF on
> all three detectors. That was wrong, and wrong in a way this tree has a named rule against
> (`feedback_cpp_default_governs_only_silent_configs`): it read the **binding's** default
> (`retile_bad_blob_max_run=null` in `cfg/.../pdhd/pr.jsonnet:128` and `protodunevd/pr.jsonnet:118`)
> instead of the **driver** that production actually runs. PDHD and PDVD both set the bound to
> **20 cm**, and it was armed in the very arm cluster 42 came from. The section below is the
> corrected version; the two tables replace the earlier ones entirely.

`ImproveCluster_1::remove_bad_blobs` is, in the header's own words, *"its only anti-ghost filter"*.
The historical form (a faithful port, kept byte-for-byte when the knobs are off) votes per
connected component, keeps a component iff ANY of its blobs is supported, and *"ONLY when that
graph has more than one connected component"* — so a fabricated run inside a single-component
cluster is never tested at all. Doc pdvd/40 round 3 added the real test:

> `bad_blob_max_run` (length; C++ default **0 = OFF**): when > 0 every new blob is tested for
> support (overlap with an ORIGINAL blob within one slice), a component is kept iff ANY blob is
> supported, and a connected run of UNSUPPORTED blobs inside a kept component whose bounding-box
> diagonal exceeds this length is removed whole.

**Proof of the production state**, from the arm's own compiled config (not from the cfg tree):

```
python3 -c "
import json
for o in json.load(open('work/029107_1_d04bee/.wct-pr_d04bee.json')):
    if o['type'] in ('ImproveCluster_2','CreateSteinerGraph'): print(o['type'], o['name'], o['data'])"
```

```
ImproveCluster_2  pr         bad_blob_max_run: 200   terminal_charge_threshold: 500  wrapped_channel_activity: true
CreateSteinerGraph pr        terminal_charge_threshold: 500  terminal_min_separation: 5  terminal_wire_tol: 1  terminal_adjacent_slice: true
CreateSteinerGraph prrefresh (same)
```

`200` is WCT internal length units (mm) = **20 cm**; `5` = 0.5 cm (doc 37). Same for the `d06base`
and `d06um` arms of §5.

**PDHD and PDVD are the same detector here — same args and same values.** PDHD's driver is a
fork-by-duplication of PDVD's and inherited the whole tuned point:

| driver TLA (`wcp-porting-img/<det>/wct-pr-perevt.jsonnet`) | PDHD | PDVD | SBND |
|---|---|---|---|
| `retile_bad_blob_max_run` | **20 cm** (`:142`) | **20 cm** (`:143`) | **no such TLA** |
| `retile_bad_blob_report` | `false` | `false` | — |
| `retile_wrapped_channel_activity` | `true` | `true` | — |
| `retile_steiner_terminal_charge` | `= steiner_terminal_charge` = 500 e | idem | — |
| `steiner_terminal_charge` | 500 e | 500 e | — |
| `steiner_terminal_wire_tol` / `_adjacent_slice` | 1 / `true` | 1 / `true` | 1 / `true` |
| `steiner_edge_charge_forward_dead_mix` | `true` | `true` | `true` |
| `steiner_terminal_min_sep_cm` | 0.5 | 0.5 | **no such TLA** |
| `steiner_skip_flags` | `[]` | `[]` | **no such TLA** |

The SBND column is empty for a structural reason, not an unset value: `sbnd/clus.jsonnet:1984`
calls `cm.improve_cluster_2(anodes=…, samplers=…)` and **passes nothing else**, so there is no
argument for a driver to set. `grep -rn bad_blob sbnd_xin/ cfg/.../sbnd/` returns nothing. Same for
`cm.steiner` there (`:2071`, `:2087`): no `terminal_min_separation`, no `skip_flags`, and no
`+ { data+: { terminal_charge_threshold } }` suffix.

**What is actually missing:**

1. **The bound is armed and the cluster-42 stretch went through it.** 26.8 cm of fabricated cloud
   survived a 20 cm run bound. Two readings, and they imply different fixes:
   (a) the blobs were classified **supported** — `Blob::overlap_fast` (`Facade_Blob.cxx:151`) is a
   pure u/v/w **wire-index-range** overlap with ±1 wire of slack and **no 3-D distance term**, so a
   fabricated blob that shares wire ranges with a real one is "supported" however far its sampled
   3-D position is. This is the residual class doc pdvd/40 named in the driver comment: *"blobs
   that overlap an original blob in WIRE space but sample far from it in 3D, and it needs a 3D
   support test instead"*; or
   (b) the stretch was **split into sub-20 cm runs** by intervening supported blobs — the bound is
   per *run*, not per cluster span, so a long fabrication punctuated by support is never one run.
   `retile_bad_blob_report=true` on evt 991 discriminates in one line: `nsup` answers (a),
   `nruns` / `maxrun_cm` answer (b). **Do not pick between them in prose — measure.**
2. **SBND cannot arm it at all.** Not "left off": there is no jsonnet parameter. Adding the four
   args to `sbnd/clus.jsonnet:1984` and `:2071`/`:2087` is a config-only change, byte-identical
   while the values stay at the C++ defaults (the key-suppression idiom already lives in
   `cm.improve_cluster_2`). Doc pdvd/40 r2 found SBND clean for the *metric* defect (P1), which is
   a different finding from "SBND needs no anti-ghost bound".
3. **PDHD's 20 cm was never censused on PDHD.** The driver comment at `:128-142` cites doc pdvd/40
   §15.6 — *21 PDVD events*, SBND's longest unsupported group (19.2 cm) and *PDVD's* p95 group span
   (22.3 cm). `grep -rn bad_blob pdhd/docs/` finds only this document, and no PDHD log carries a
   `BADBLOB` line. The number is inherited from another detector's distribution.
4. **`dis_cut = 20 cm` is unreachable from config on all three.** It is the one number deciding how
   far `get_activity_improved` reaches for real charge, and it cannot be varied to find out what it
   costs. It is also a coincidence of value, not of meaning, that it equals the run bound.
5. **`hack_activity_improved` has no length cap at all** on any detector — no knob, no constant to
   raise. The bound in item 1 removes fabricated blobs *after* the fact; nothing limits how far the
   path is painted in the first place.
6. **SBND's two terminal thresholds are consistent, not divergent.** Both the retiler and
   `CreateSteinerGraph` sit at the C++ default 4000 e there. Doc pdvd/31 r6's "two thresholds in one
   stage" was about them **drifting apart** (500 vs 4000) — that is not SBND's condition. SBND's
   defect is that neither is lowerable, so the doc-25 §13.6 census (4000 → 500 turns no-steiner
   exits 39 → 14) cannot be repeated there.
7. **A third `remove_bad_blobs` exists with no knob.** `RetileCluster::remove_bad_blobs`
   (`retile_cluster.cxx:498`, called from `:702`) is the pre-fork copy: no `bad_blob_max_run`, no
   cache refresh. It is dead in production — no detector instantiates a bare `RetileCluster`
   (`cm.retile` is commented out in both `clus.jsonnet` files, and `CreateSteinerGraph` /
   `ClusteringRetile` only *default* to it) — but it is a live divergence risk for anyone who wires
   the default retiler.

Items 1 and 3 are the measurements; the rest is a config and code audit. The first experiment is
`-S retile_bad_blob_report=true` on the two events here, which is log-only and changes no output.

### 8.7 Recommendation: how to remove the ghost Steiner edges on PDHD

Ranked. Every item except R0 changes reconstruction output, so each ships as a default-OFF knob
with a byte-identical gate (`abtest/hash_archive.py`), and the two thresholds below must be scanned
on the 30-event PDHD arm, not on the two events here.

**R0. Census first — free, log-only, and it decides everything below.**
`-S retile_bad_blob_report=true` on evt 991 (idx 1) and evt 1079 (idx 12). One `BADBLOB` line per (cluster, apa,
face): `nnew norig ncomp ncomp_ss nsup legacy_rm run_rm nruns maxrun_cm` plus the boxes of the 12
longest runs; `PDHD_LOG_LEVEL=trace` adds `BADBLOBPT` per blob (`sup`, `comp`, `voted`, `run`, raw
centre) so every Steiner point in cluster 42's 26.8 cm stretch can be labelled by its blob's
verdict. Three readings, and the line separates them:
(a) the fabricated blobs were called **supported** by the wire-space test → `nsup` high;
(b) the run graph **fragmented** into sub-20 cm runs → `nruns` large, `maxrun_cm` < 20 (adjacency
is adjacent-slice + same-slice *wire overlap*, so a path steep in wire space has no edges between
consecutive painted blobs and never forms one long run);
(c) they were removed and the gap was refilled → `run_rm` > 0 yet the points persist.
Do not choose between these in prose. They imply different fixes.

**R1. Give the bound the 3-D support test its own doc asks for — recommended primary.**
Support today is `Blob::overlap_fast` (`Facade_Blob.cxx:151`): u/v/w wire-index-range overlap with
±1 wire of slack, within ±1 slice. No 3-D distance. The test that is wanted **already exists and is
shipped**: `Grouping::test_good_point(p, apa, face, radius, ch_range)` returns
`[live u,v,w | dead u,v,w]` against the real ctpc lattice, and `classify_point`
(`NeutrinoSteinerGapGraph.cxx:67`, duplicated from `NeutrinoRoughPathProbe`) already uses it to mean
exactly *live / dead / unsupported*. Add `retile_bad_blob_support_3d` (default OFF ⇒ key omitted ⇒
byte-identical): a new blob is supported iff its centre classifies live-or-dead. Use it **AND**ed
with the existing wire test, never instead of it — the conjunction is strictly stricter, so the
knob can only ever remove more, which is what makes the gate readable.
*Caveat to carry:* `test_good_point` queries the whole-event lattice, so a ghost lying across
another track's charge still classifies live. That is the same charge `get_activity_improved`
admitted within its 20 cm reach, so the two stages stay consistent — but it means R1 bounds the
class, it does not eliminate it.

**R2. Cap the painting at source — the only item that prevents rather than removes.**
`hack_activity_improved` interpolates the boundary-to-boundary shortest path at
`low_dis_limit = 0.3 cm` with `ncount = int(dis/0.3)+1` and **no length limit**, and writes only
where `measures.at(wire) == 0.0` — so it never overwrites admitted charge and never overwrites the
dead sentinel (1e-3 > 0). It paints exclusively into cells the retiler's own activity map left
empty, which makes a cap well defined: refuse a contiguous empty stretch longer than N.
Knob `retile_hack_max_bridge` (default 0 = uncapped = byte-identical). **N comes from the scan, not
from cluster 42** — that cluster only says the interesting range brackets its bridged 5 cm and
20 cm gaps against its unbridged 103 cm one. R1 and R2 are a pair: R1 asks *is this real*, R2 asks
*should we have bridged that far*, and neither answers the other's question.

**R3. Provenance, only if R1+R2 leave a residual.** `1e-3` is written by two sites for two
meanings — `improvecluster_1.cxx:441` for a genuinely dead/forced channel (*"sentinel: dead/forced
channel, converted to (0, large_err) in make_iblobs_improved"*) and `hack_activity_improved:596`
for an invented cell. At write time they are exactly separable; afterwards they are not. Recording
the invented (slice, plane, wire) set would make the census exact and the support test a fact
rather than an inference. It is more plumbing than R1 for a strictly smaller gain, so it is
conditional on R1's whole-event caveat actually biting.

**R4. Know that `steiner_gap_penalty = 2.0` buys PDHD nothing today.** The driver sets it
(`wct-pr-perevt.jsonnet:3069`), but the penalised `steiner_graph_gap` flavour is built by
`NeutrinoSteinerGapGraph` and read only by `TaggerCheckNeutrino` and `CheckSTM_Michel` — neither is
in the pipeline this arm ran (`switch_scope, flag_mains, steiner, fiducialutils, TGM, STM, FC,
protect_bundle, steiner_refresh`). `TaggerCheckSTM` reads plain `"steiner_graph"` at all six sites
(`:1102, :1416, :1420, :3015, :3207`). Its `bad_fraction` *would* fire on these ghosts —
`classify_point` returns 2 (unsupported) where there is neither charge nor a dead channel — but it
**re-weights, it does not remove**: where the fabricated bridge is the only connection across the
gap, which is cluster 42's case, the shortest path still crosses it, merely at higher cost. So it
protects path *choice* where a real alternative exists and is not the fix here. Worth a decision on
whether PDHD should keep setting an inert knob.

**R5. Expose `dis_cut` — measurement infrastructure, not a fix.** `20 * units::cm`
(`improvecluster_1.cxx:378`) is the reach for admitting real whole-event activity into a cluster's
tiling, and it is unreachable from jsonnet on all three detectors. A knob makes its cost
measurable. No reason to move the value blind.

**Order:** R0 now; R1 + R2 together as the mechanism fix; R4 as a decision; R3 and R5 conditional.

> **R0 was run — see [doc pdhd/07](07_steiner-ghost-census.md).** The answer is reading (b): the
> 20 cm bound removes a great deal (including a 100.8 cm fabricated column in cluster 42) but the
> run decomposition splits one ghost into several runs and the survivors sit just under the
> threshold (18.5 / 18.4 / 18.3 cm). 14.5–19.0 % of the blobs that survive both filters have no
> support; in cluster 42 it is 61.6 % (baseline) / 76.3 % (unmerge). Doc 07 §5 re-orders this
> ladder: **R2 first**, and adds R2b (bound a component's total unsupported content, not each run).

## 9. Not done / next

0. **Census the armed guard, and expose it on SBND (§8.6).** The bound is ON at 20 cm on PDHD and
   PDVD and 26.8 cm of fabricated cloud still survived it (cluster 42), so the question is not
   "arm it" but *which* hole it left: `-S retile_bad_blob_report=true` on evt 991 and evt 1079 is
   log-only, costs nothing, and its one `BADBLOB` line separates "counted as supported by a
   wire-space test" from "split into sub-20 cm runs". Separately, SBND has no knob path at all
   (`sbnd/clus.jsonnet:1984` passes only anodes+samplers) and PDHD's 20 cm is inherited from the
   PDVD study, never measured on PDHD. This is upstream of everything below — §8.4's false STM tag
   is fitted on 220 points that mostly do not exist.
1. **The false STM tag of §8.4** is the next thing to settle: a main gutted to 8 % of its blobs
   keeps its main flag, loses TGM mechanically, and is tagged STM on a fabricated 220-point fit
   built from 19 points of charge. Until that is addressed `unmerge_assoc` should not be considered
   for a PDHD default, whatever the aggregate counts say.
2. **Grading.** Two events, no hand scan, sign unknown. Before anyone proposes making this a PDHD
   default it needs the 30-event arm and a scan of what the 40-odd splits per event did to the
   objects — the PDVD flip (doc pdvd/38+39) came *after* that work, not before.
2. **The accept guard on cluster 113** is now the sole remaining explanation for that lost stopper
   and is unread: `accept_guards_reject`'s desert + spike tests (`TaggerCheckSTM.cxx:3798-3857`)
   read the charge profile, which is exactly what the wrapped-channel fix changed.
3. **Cluster 108's kink relocation** is unexplained by either the fix or the merge.
4. `-save-assoc` changes the pctree, so a run that wants `-unmerge` cannot reuse an existing
   pctree. Every historical PDHD arm needs re-clustering to be usable with it.
