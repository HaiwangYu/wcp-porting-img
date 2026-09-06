# doc pdhd/07 — the retiler's ghost census: how a fabricated Steiner cloud gets past the 20 cm bound

Owner question (2026-09-06): *"What is your recommendation to improve and remove this ghost Steiner
Graph edges for PDHD?"*, and before that the R0 measurement doc 06 §8.7 asked for. This document is
that measurement and the recommendation it forces.

Companion to **doc 06 §8.5–8.7** (the gap-filling mechanism and the config audit). Doc 06 explains
*why* the Steiner cloud contains points that are not measured charge; this one counts them.

---

## 0. Repro

```bash
cd wcp-porting-img/pdhd
# the four census arms -- log-only, outputs byte-identical to the doc-06 arms
export PDHD_PR_TLA="-S retile_bad_blob_report=true"
./run_pr_evt.sh            -s d07bb    029107 1     # evt 991,  baseline
./run_pr_evt.sh            -s d07bb    029107 12    # evt 1079, baseline
./run_pr_evt.sh -unmerge   -s d07bbum  029107 1     # evt 991,  unmerge_assoc
./run_pr_evt.sh -unmerge   -s d07bbum  029107 12    # evt 1079, unmerge_assoc

# the census
python3 docs/scripts/d07_badblob_census.py work/029107_{1,12}_d07bb{,um}/wct_pr_029107_*.log \
        --tsv docs/d07_badblob_census.tsv
python3 docs/scripts/d07_badblob_census.py work/029107_1_d07bb/wct_pr_029107_1.log \
        --cid 42 --near 12.3,450.1,12          # the owner's cluster

# the control: the knob changes no output
python3 ../abtest/hash_archive.py pdhd/work/029107_1_d07bb/mabc-pr.zip
python3 ../abtest/hash_archive.py pdhd/work/029107_1_d06base/mabc-pr.zip
```

Inputs are the doc-06 pctrees, symlinked (`work/029107_{1,12}_d07bb{,um}/pctree-evt*.tar.gz` →
`_d06base` / `_d06um`); byte-identical md5 across the two arms of each event, so baseline and
unmerge differ only by the `-unmerge` flag.

**Binary pin.** `local/lib/libWireCellClus.so` 2026-09-06T12:43:59,
md5 `7f4a718d9795f515e032d705f492e58b`. The doc-06 arms ran *before* that rebuild and these ran
after; the control below shows the retile/Steiner path is unaffected by it.

**Control — the census knob is log-only, and so is the rebuild.** `hash_archive.py` member-content
hash of `mabc-pr.zip`, census arm vs its doc-06 twin:

| arm | vs | member hash | |
|---|---|---|---|
| `029107_1_d07bb` | `_d06base` | `ce10012d44ce689e…` | SAME |
| `029107_12_d07bb` | `_d06base` | `504efac55d4787af…` | SAME |
| `029107_1_d07bbum` | `_d06um` | `9a9437dee2b1a630…` | SAME |
| `029107_12_d07bbum` | `_d06um` | `e042c95968a15674…` | SAME |

---

## 1. The answer in one paragraph

The 20 cm bound is **not** being defeated by the support test, and it is **not** inert — it removes
a quarter of all unsupported blobs on its own (7 240 of 27 671 in evt 991), including a **100.8 cm
fabricated column** in the owner's own cluster. The older legacy component vote removes most of the
rest (16 207); the two sets are disjoint by construction, so they add. What leaks is
the **run decomposition**: the bound is applied per connected *run* of unsupported blobs, one
physical fabrication breaks into several runs, and the survivors pile up **just under the
threshold** — 18.5, 18.4, 18.3, 17.1, 16.4 cm against a 20 cm bound. In cluster 42 the removed
100.8 cm column and a kept 18.5 cm run sit at the *same* (y, z) — they are the same ghost, cut in
two by the run graph. Across the four arms **14.5 – 19.0 % of the blobs that survive both filters
still have no support in the original cluster**, and in cluster 42 it is **61.6 %** (baseline) /
**76.3 %** (unmerge).

This is reading **(b)** of doc 06 §8.7 R0, and it **contradicts the assumption PDHD inherited from
PDVD**. The PDVD driver comment (`wct-pr-perevt.jsonnet:139-142`) says *"Do NOT read the residual as
a reason to lower it: what survives is class (c), blobs that overlap an original blob in WIRE space
but sample far from it in 3D"*. On PDHD the dominant survivor is not class (c): those blobs are
correctly classified **unsupported** — they are counted in runs — and they survive only because
their run is shorter than the bound.

---

## 2. What the census reports, and the one trap in reading it

`retile_bad_blob_report=true` emits three DEBUG lines from `ImproveCluster_1`:

```
BADBLOB     cid= ident= apa= face= nnew= norig= ncomp= ncomp_ss= nsup= legacy_rm= run_rm=
            nruns= maxrun_cm=   [| run i: nb= nslices= span_cm= craw=(x,y,z) bb=(…)]*
BADBLOBRM   ident= apa= face= removed= npts A -> B nblobs N
BADBLOBSKIP ident= apa= face= cached_nnew= children_on_face=
```

**The trap: there are two retile passes per (cluster, apa, face), and both emit a census line.**
`ImproveCluster_2::mutate` first calls `ImproveCluster_1::mutate` (`improvecluster_2.cxx:144`) to
build an intermediate cluster whose only purpose is to give the *second* `hack_activity_improved`
a retiled path, then retiles again itself. Only the second pass is followed by `BADBLOBRM`
(`improvecluster_2.cxx:281`), and only the second produces the cloud the Steiner build sees.
Summing over both **double-counts by ~2×**. `d07_badblob_census.py` binds each `BADBLOBRM` to the
most recent census line with the same `(ident, apa, face)`, marks that record `final`, and reports
final passes only. A first cut of this analysis summed both and had to be redone.

Two more reading notes: run centres and boxes are in the **raw drift frame** (`Blob::center_pos`),
not `x_t0cor` — join to a 3-D dump on **(y, z)** within a cluster, never on x. And the per-run list
in the log is capped at 12 entries and stops at the first run below 3 cm; `nruns` is the true count
(1 732 – 2 972 runs per arm), so run statistics below are over the reported subset.

---

## 3. The whole-event picture

Final passes only. Support = `Blob::overlap_fast` against an original blob within ±1 slice.

| | evt 991 base | evt 991 unmerge | evt 1079 base | evt 1079 unmerge |
|---|---|---|---|---|
| clusters × faces censused | 110 | 481 | 150 | 406 |
| original blobs → retiled | 26 776 → 52 529 (**×2.0**) | 27 874 → 46 995 (×1.7) | 35 648 → 84 884 (**×2.4**) | 35 725 → 76 575 (×2.1) |
| retiled blobs **unsupported** | 27 671 (**52.7 %**) | 21 237 (45.2 %) | 50 570 (**59.6 %**) | 42 486 (55.5 %) |
| removed — legacy vote | 16 207 | 11 455 | 28 555 | 24 659 |
| removed — 20 cm run bound | 7 240 | 5 661 | 13 985 | 10 377 |
| removed — union | 23 447 | 17 116 | 42 540 | 35 036 |
| points in the retiled cloud | 439 660 → 335 087 (−23.8 %) | 407 155 → 327 988 (−19.4 %) | 580 849 → 410 912 (−29.3 %) | 526 554 → 386 263 (−26.6 %) |
| **surviving blobs with NO support** | 4 224 / 29 082 = **14.5 %** | 4 121 / 29 879 = 13.8 % | 8 030 / 42 344 = **19.0 %** | 7 450 / 41 539 = 17.9 % |
| reported runs > 20 cm (removed) | 62 | 40 | 92 | 63 |
| reported runs 15–20 cm (**kept**) | 22 | 19 | 37 | 33 |
| longest run seen | 239.9 cm | 239.9 cm | 262.7 cm | 262.7 cm |

Three things to take from this table.

1. **The retile roughly doubles the blob count**, and *half to sixty percent* of what it makes has
   no support in the cluster it is improving. That is the scale of the fabrication, and it is not a
   pathology of one cluster.
2. **The filters do real work, and the two must be credited separately.** In evt 991 baseline the
   **legacy component vote** — the historical path, always on — removes 16 207 unsupported blobs
   (58.6 %) and the **20 cm run bound** — the doc pdvd/40 r3 knob — removes a further 7 240
   (26.2 %), for 84.7 % between them and about a quarter of all retiled *points*. Evt 1079 is the
   same shape (56.5 % / 27.7 % / 84.1 %). The two sets are **disjoint by construction**
   (`BadBlobRuns.h:118-127`: a vote-removed component contains no supported blob, and runs are
   formed only inside kept components), which is why the union is exactly additive and why
   `kept − nsup` below is an exact count of surviving unsupported blobs rather than a bound.
   Doc 06's earlier claim that the bound was off everywhere was wrong; its own quarter of the
   removal would otherwise still be in the cloud.
3. **The residual is not small and it is not class (c).** 4 224 – 8 030 unsupported blobs survive
   per event, and the 15–20 cm band — runs that would die under a slightly tighter bound — holds
   19 to 37 of the reported runs in every arm.

`BADBLOBSKIP` fired 4 – 38 times per arm and in **zero** cases did the face have more children than
the cached map showed: the doc pdvd/40 r3 stale-`ClusterCache` blind spot is closed on PDHD.

---

## 4. Cluster 42 — the owner's cluster, (−41.9, 12.3, 450.1)

**Baseline arm** (`d07bb`, apa 2 face 0), final pass:

```
nnew=1340  norig=180  nsup=219 (16.3 %)  ncomp=82  legacy_rm=189  run_rm=580  nruns=28  maxrun=43.6 cm
removed 769 -> kept 571 blobs, 352 of them unsupported (61.6 %);  points 10 425 -> 5 454
```

180 original blobs become **1 340** — ×7.4, against ×2.0 for the event as a whole — and only 16.3 %
of them are supported. The reported runs:

| run | blobs | span | y | z | verdict |
|---|---|---|---|---|---|
| 0 | 137 | 43.6 cm | 12.4–19.8 | 458.2–461.6 | removed |
| 1 | 112 | 38.4 cm | 30.3–38.7 | 436.1–449.4 | removed |
| 2 | 67 | 29.4 cm | 19.9–28.3 | 430.1–449.1 | removed |
| 3 | 14 | 25.6 cm | 30.5–55.9 | 462.1 | removed |
| 4 | 75 | 24.7 cm | 9.4–16.7 | 429.4–433.4 | removed |
| 5 | 63 | 23.3 cm | 10.5–23.9 | 449.6–454.9 | removed |
| 6 | 49 | 21.0 cm | 10.0–20.9 | 441.2–452.2 | removed |
| 7 | 63 | 20.5 cm | 25.5–38.3 | 429.4–435.4 | removed |
| **8** | 45 | **18.4 cm** | 14.7–20.3 | 450.4–461.2 | **KEPT** |
| **9** | 57 | **18.3 cm** | 13.1–14.7 | 450.4–455.0 | **KEPT** |
| **10** | 50 | **17.1 cm** | 30.7–31.9 | 435.7–442.9 | **KEPT** |
| **11** | 17 | **16.4 cm** | 16.2–26.6 | 437.4–449.0 | **KEPT** |

Runs 8 and 9 sit at **z ≈ 450–455, y ≈ 13–20** — the owner's (y, z) — and are kept for one reason:
18.4 and 18.3 are less than 20.

**Unmerge arm** (`d07bbum`) makes the mechanism unmistakable. There cluster 42 is the gutted main of
doc 06 §8.4 — **16** original blobs:

```
nnew=435  norig=16  nsup=22 (5.1 %)  ncomp=6  legacy_rm=18  run_rm=324  nruns=4  maxrun=100.8 cm
removed 342 -> kept 93 blobs, 71 of them unsupported (76.3 %);  points 3 263 -> 718
```

16 blobs become **435** — ×27 — and 94.9 % of them are unsupported. The runs:

| run | blobs | span | y | z | verdict |
|---|---|---|---|---|---|
| 0 | 324 | **100.8 cm** | 11.7–15.9 | 450.1–456.3 | **removed** |
| 1 | 59 | **18.5 cm** | 13.1–15.6 | 450.4–451.7 | **KEPT** |
| 2 | 11 | 3.2 cm | 12.3–12.7 | 450.1–450.6 | KEPT |

Run 0 and run 1 are at the **same y and the same z**. They are one fabricated column; the run graph
split it, the 100.8 cm piece died and the 18.5 cm piece lived. This is the R0 answer, in one
cluster, with no inference: **the bound works on what it sees as one run, and the run decomposition
is what lets a long ghost through in pieces.**

That the STM fit of doc 06 §8.4 was built on 220 points of which most are fabricated is consistent
with this: 718 points survive here where 3 263 were tiled, from 16 blobs of real charge.

---

## 5. What this changes in the doc 06 §8.7 recommendation

**R2 (cap the painting at source) moves to first, and the reason is different from the one given
there.** The census shows the leak is a *decomposition* artefact: bounding the length of what
already exists will always be fought by however the run graph happens to cut it. Refusing to paint
the bridge in the first place — `hack_activity_improved` has no length cap at all — is upstream of
the whole argument and cannot be fragmented.

**R1 (a 3-D support test) stays, but its motivation is now measured, not assumed.** It is *not*
where most of the residual is on PDHD. It remains right on its own terms — `overlap_fast` is a
wire-space proxy for a 3-D question — and it is the only item that also improves the *classification*
the census reports, which everything else is graded against.

**New: R2b — bound the total, not just the run.** The cheapest single change that closes what this
census found is to judge a *component's* unsupported content, not each run separately: a component
whose unsupported blobs sum to more than N cm of span, or exceed some fraction of the component,
loses them all. That is one extra reduction over the run list `BadBlobRuns::analyze` already builds
and it removes the fragmentation escape entirely. It needs its own default-OFF knob and a scan.

**Lowering the 20 cm bound is *not* the recommendation.** It would catch the 18.5/18.4/18.3 cm runs
and miss the next fragmentation at 14 cm, and 20 cm was chosen on PDVD to sit above SBND's longest
legitimate unsupported group (19.2 cm). Fragmentation is the defect; the threshold is not.

**Unchanged:** R4 — `steiner_gap_penalty = 2.0` is set in the PDHD driver but the penalised
`steiner_graph_gap` flavour is read only by `TaggerCheckNeutrino` / `CheckSTM_Michel`, neither in
this pipeline, while `TaggerCheckSTM` reads plain `"steiner_graph"` at all six sites. R5 — `dis_cut`
unreachable from config.

---

## 6. Next steps, in order

1. **Scan `retile_bad_blob_max_run` on PDHD before anything is built.** The census TSV
   (`docs/d07_badblob_census.tsv`, 1 147 final passes) already holds every run's span; the sweep
   can be done offline from the existing logs for the *classification*, but the STM/TGM effect
   needs arms. 10 / 15 / 20 / 30 cm on the 30-event PDHD manifest, graded on tag flips and on the
   surviving-unsupported fraction above. This is the number doc 06 §8.6 item 3 says PDHD never
   measured for itself.
2. **Implement R2 (`retile_hack_max_bridge`, default 0 = uncapped = byte-identical)** and scan it
   on the same manifest. Grade on: surviving-unsupported %, STM/TGM tag flips, and the two lost
   stoppers of doc 04 §12.
3. **Implement R2b (component-level unsupported bound), default-OFF**, and compare against R2 on
   the same arms — they may be redundant, and if so R2 wins because it prevents.
4. **Re-read doc 06 §8.4's false STM tag** against this census: cluster 42's fit is built on a cloud
   that is 76 % fabricated in the unmerge arm. That is the physics consequence, and it is the thing
   the owner actually cares about.
5. **Take the finding to PDVD.** The "class (c)" claim in the PDVD driver comment is not what PDHD
   measures; PDVD deserves the same census (`retile_bad_blob_report=true`, log-only, free) before
   its 20 cm is treated as settled.
6. **Expose the knob path on SBND** (`sbnd/clus.jsonnet:1984` passes only anodes+samplers). Config
   only, byte-identical at the C++ defaults.
7. **Per-blob trace, if a specific ghost needs naming.** `PDHD_LOG_LEVEL=trace` adds `BADBLOBPT`
   (one line per new blob: `sup`, `comp`, `voted`, `run`, raw centre), which labels every Steiner
   point by its blob's verdict. Not needed for the conclusion above; needed to draw the ghost.

## 7. Not done

- No knob was written and no default was changed. This document is a measurement.
- Only two events. The fabrication rates in §3 are consistent across four arms but two events is not
  a distribution.
- The census counts *blobs*, not Steiner graph *edges*. A blob-level ghost implies ghost nodes and
  therefore ghost edges, but the edge count itself is not measured here.
- `dis_cut = 20 cm` and the uncapped path painting remain unreachable from config on all three
  detectors.
