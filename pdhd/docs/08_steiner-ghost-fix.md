# doc pdhd/08 — capping the retiler's fabrication: what the bridge census decided

Owner ask (2026-09-06): *"follow your planned step to improve this Steiner Graph building situation."*
The plan is doc 07 §5–§6: **R2** cap the fabrication at source, **R2b** stop the run decomposition from
letting a long ghost through in pieces. This document is the measurement that chose the *form* of both
knobs, and then the knobs.

Companion to **doc 07** (the census that found the leak) and **doc 06 §8.5–8.7** (the mechanism and the
config audit).

---

## 0. Repro

```bash
cd wcp-porting-img/pdhd
export LD_LIBRARY_PATH=/home/xqian/tmp/d08_libpin/new        # pin; see below
export PDHD_PR_TLA="-S retile_bad_blob_report=true"
./run_pr_evt.sh          -s d08bb    029107 1     # evt 991,  baseline
./run_pr_evt.sh          -s d08bb    029107 12    # evt 1079, baseline
./run_pr_evt.sh -unmerge -s d08bbum  029107 1     # evt 991,  unmerge_assoc
./run_pr_evt.sh -unmerge -s d08bbum  029107 12    # evt 1079, unmerge_assoc
# the two controls: same pin, census OFF
PDHD_PR_TLA= ./run_pr_evt.sh          -s d08off   029107 1
PDHD_PR_TLA= ./run_pr_evt.sh -unmerge -s d08offum 029107 1

# stage 1a -- does a bridge fabricate, or ride on activity that already exists?
python3 docs/scripts/d08_bridge_census.py work/029107_1_d08bb/wct_pr_029107_1.log
# stage 1d -- which repair closes the run-fragmentation escape?
python3 docs/scripts/d08_run_merge_sim.py work/029107_1_d08bbum/wct_pr_029107_1.log --cid 42

# ---- stage 3: gates (pin new2 = the stage-2 build) ----
./build/clus/wcdoctest-clus                                    # 328/328
# compiled-config zero-diff, current cfg/ vs a pristine tree:
git -C ../../toolkit archive HEAD cfg | tar -x -C /home/xqian/tmp/d08/cfgproof/head
PDHD_PR_COMPILE_ONLY=1 PDHD_KEEP_CFG=1 PDHD_PR_TLA= ./run_pr_evt.sh -s d08cfgA 029107 1
#   ... and the same with WIRECELL_PATH=<pristine>/cfg for the "before" side; diff the two JSONs.
# the 30-event binary gate:
ARM=d08gref PIN=/home/xqian/tmp/d08_libpin/ref  JOBS=10 ./docs/scripts/run_d08_arms.sh
ARM=d08goff PIN=/home/xqian/tmp/d08_libpin/new2 JOBS=10 ./docs/scripts/run_d08_arms.sh
python3 docs/scripts/d02_hash_gate.py d08gref d08goff        # PASS 30 FAIL 0

# ---- stage 4: the scan (one arm per knob value) ----
ARM=d08cap10 PIN=/home/xqian/tmp/d08_libpin/new2 JOBS=6 \
    EXTRA="-S retile_hack_max_bridge=10" ./docs/scripts/run_d08_arms.sh
#   ... likewise cap20b/cap40, mrg1/mrg3/mrg5, both, and the add-on mr10/mr15/mr30
./docs/scripts/d08_grade.sh d08goff d08cap10 d08cap20b d08cap40 d08mrg1 d08mrg3 d08mrg5 \
                            d08both d08mr10 d08mr15 d08mr30
python3 docs/scripts/d08_tag_flips.py d08goff d08cap10        # the STM set census of sec 8

# ---- the C++-vs-model cross-check (sec 5) ----
PDHD_PR_TLA="-S retile_bad_blob_report=true -S retile_bad_blob_run_merge=3" \
    ./run_pr_evt.sh -s d08xval 029107 1
python3 docs/scripts/d08_run_merge_sim.py work/029107_1_d08bb/wct_pr_029107_1.log \
    --pass first --predict 3                                  # 501, == the arm's first-pass merge_rm

# ---- the PDVD add-on (sec 7), log-only ----
cd ../pdvd && PDVD_PR_TLA="-S retile_bad_blob_report=true" ./run_pr_evt.sh -s d08pv 039252 0
```

Inputs are the doc-06 pctrees, symlinked into each arm dir (never copied, never regenerated).

**Binary pin.** `/home/xqian/tmp/d08_libpin/`: `ref` = `local/lib` as of 2026-09-06T15:07,
md5 `863e55d6895ea1b085aead9717c73ae4`; `new` = `ref` with `libWireCellClus.so` replaced by the
stage-1 (census-only) build, md5 `14cea650bebb93cd48b860dbdae8adff`; **`new2`** = `ref` with the
stage-2 (census + both knobs) build, md5 `aa03c8fc163c66fd13aeda999773f713` — every gate and scan arm
below uses `new2`. `local/lib` was **not** touched, and was not even installed to: a peer's SBND
campaign was live throughout, so the build stopped at `./wcb build` and the library was copied from
`build/clus/` into the pin. Freshness (M1): the pinned library is 15:37:39, the last source edit
15:35:51. Arms resolve every WireCell library from the pin (`ldd` check inside the runner).

**Control — the census is log-only, and so was the peer's 15:07 rebuild.** `hash_archive.py`
member-content hash of `mabc-pr.zip`:

| arm | member hash | |
|---|---|---|
| `029107_1_d08bb` (census ON) | `ce10012d44ce689e…` | |
| `029107_1_d08off` (census OFF, same pin) | `ce10012d44ce689e…` | **SAME** — the instrumentation changes nothing |
| `029107_1_d07bb` (doc 07, old pin) | `ce10012d44ce689e…` | SAME |
| `029107_1_d06base` (doc 06) | `ce10012d44ce689e…` | SAME — the 12:43 and 15:07 rebuilds miss this path |
| `029107_1_d08bbum` / `_d08offum` / `_d07bbum` / `_d06um` | `9a9437dee2b1a630…` | all SAME |
| `029107_12_d08bb` / `_d07bb` | `504efac55d4787af…` | SAME |

---

## 1. What the census added

Two report lines, both inside the **existing** `bad_blob_report` knob (C++ default `false`, already
proven output-neutral in doc pdvd/40 r3):

```
BRIDGE     cid= ident= apa= face= which= npath= npath_face= nbridge= capped=
           new_cells= skip_real= skip_dead= skip_prior=  [| seg k: gap_cm= ncount= new= sprior= sreal= sdead= new_frac=]*
BADBLOBRUN cid= ident= apa= face= k= comp= nb= nslices= span_cm= bb=(x0,x1,y0,y1,z0,z1)
```

`BRIDGE` is one line per `hack_activity_improved` call — `which=orig` and `which=temp`, the two calls
`ImproveCluster_2::mutate` makes into the **same** activity map. Cells are classified at write time:

| field | meaning |
|---|---|
| `new` | the cell was empty; the bridge painted it — **the fabricated footprint** |
| `sprior` | a bridge had already painted it. Includes a bridge re-covering **itself** (interpolated points are 0.3 cm apart and each paints a 7×7 disc), so read it as re-paint effort, not extra footprint |
| `sreal` | already held charge — the bridge's write was a no-op |
| `sdead` | already held the `:441` dead sentinel — dead admission had covered it |

That three-way split of the skip is what makes the number honest. Without it, the `temp` pass
retracing the `orig` pass's ghost reports "nothing new" and a ghost reads as harmless.

`BADBLOBRUN` is the run list the human `BADBLOB` line already prints, but **untruncated** (that line
stops at 12 entries / 3 cm) and carrying `comp` — `BadBlobRuns::Run` already computed it
(`BadBlobRuns.h:50`), it was simply never reported. **The x range is new too, and it changes doc 07's
reading of cluster 42 (§3).**

---

## 2. Stage 1a — a length cap on the bridge IS the right knob

The worry was mechanical: `improvecluster_1.cxx:591` paints only into cells that are still empty, and
`get_activity_improved:398-409` has already admitted dead channels within 20 cm of the cluster's own
2-D points on *both* sides of a gap. If long bridges mostly land on already-admitted cells, a length
cap would sever legitimate dead-region bridging and buy nothing.

**It does not. The fabrication is concentrated in a tiny minority of very long bridges.**

| | evt 991 base | evt 991 um | evt 1079 base | evt 1079 um |
|---|---|---|---|---|
| bridges | 25 701 | 28 776 | 27 689 | 26 742 |
| cells **newly painted** | 209 537 | 189 060 | 227 179 | 182 383 |
| cells re-painted (`sprior`) | 884 835 | 705 667 | 941 419 | 729 431 |
| cells already holding charge | 589 050 | 629 304 | 566 742 | 595 209 |
| cells already holding a dead sentinel | 12 870 | 13 242 | 10 555 | 5 452 |
| bridges **> 20 cm** | 185 (**0.72 %**) | 120 (0.42 %) | 147 (0.53 %) | 83 (0.31 %) |
| …their share of all new cells | **54 %** | 49 % | **62 %** | 53 % |

**0.3 – 0.7 % of bridges create half to two-thirds of everything the retiler invents.**

And the share of a bridge's touched cells that did not already exist rises with its length (evt 991
baseline; `new / (new + sreal + sdead)`). The rise is not strictly monotone — the 30–60 cm band sits
below the 20–30 cm band — so the claim rests on the two ends, 0.15 at 1–3 cm against 0.88 above 60 cm:

| gap band (cm) | 1–3 | 3–5 | 5–10 | 10–20 | 20–30 | 30–60 | > 60 |
|---|---|---|---|---|---|---|---|
| new cells | 3 540 | 1 324 | 1 924 | 12 927 | 13 960 | 35 419 | **63 703** |
| `new_frac` | 0.154 | 0.226 | 0.203 | 0.406 | 0.480 | 0.428 | **0.878** |

Short bridges are mostly redundant — they run along real charge and their writes are no-ops. Long
bridges create. The longest single gap in evt 991 is **480.5 cm**.

Note the dead sentinel column: `sdead` is 0.3–0.8 % of all cells touched. **Bridging a wide dead
region is essentially not what these bridges are doing**, so the feared cost of a length cap is not
there. The real cost of a cap is downstream connectivity, which cells cannot measure — that is what
the Stage 4 scan grades.

> **Decision: R2 is a cap on the gap length**, `hack_max_bridge`, C++ default 0 = uncapped =
> the prototype (`ImprovePR3DCluster.cxx:973-990`, identical uncapped loop).

---

## 3. Stage 1d — the fragmentation is intra-component, and it is a CHAIN

Doc 07 §4 reported cluster 42's removed 100.8 cm run and kept 18.5 cm run at "the same y and the same
z" and called them one ghost. With `comp` and the **x** range now in the log, both halves of that are
confirmed and sharpened.

**Cluster 42, unmerge arm, apa 2 face 0 — all four runs are in `comp=0`:**

| k | comp | nb | span | x | y | z | verdict |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 324 | 100.8 cm | −27.9 … **72.6** | 11.7–15.9 | 450.1–456.3 | removed |
| 2 | 0 | 11 | 3.2 cm | **74.8** … **78.0** | 12.3–12.7 | 450.1–450.6 | KEPT |
| 1 | 0 | 59 | 18.5 cm | **80.2** … 98.5 | 13.1–15.6 | 450.4–451.7 | KEPT |
| 3 | 0 | 1 | 0.0 cm | 99.7 | 17.5 | 452.1 | KEPT |

It is **one column along drift**, at fixed (y, z), broken into four pieces by gaps of 2.2, 2.2 and
1.2 cm. Only the first piece exceeds 20 cm, so only the first dies.

Across the whole arm, of the adjacent run pairs (both > 3 cm, boxes within 1 cm), **95.4 %** (evt 991,
62 of 65, in both arms) and **83.6 / 84.9 %** (evt 1079: 117/140 and 101/119) sit in the **same**
component. So a component-independent merge is not needed.

*(The two evt-991 arms giving the identical 62/3 was checked rather than assumed: the two pair **sets**
differ — 65 pairs each, but drawn from different clusters, e.g. cid 111 contributes 8 pairs in the
baseline arm and cid 285 contributes 14 in the unmerge arm. The equal totals are a coincidence, not a
keying collapse.)*

Four repairs were simulated offline from `BADBLOBRUN`, all applied *on top of* the production 20 cm
per-run bound, and scored as the extra share of surviving unsupported blobs removed:

Survivors of the production 20 cm per-run bound: 4 198 / 4 036 / 7 153 / 6 506 blobs.

| variant | 991 base | 991 um | 1079 base | 1079 um | verdict |
|---|---|---|---|---|---|
| **A** per-component union bbox of *all* its unsupported blobs, bound 20 cm | 93.5 % | 90.6 % | 86.2 % | 85.8 % | **too blunt.** Raising the bound to 40 cm barely moves it (90.3 / 85.9 / 79.5 / 78.6 %) — it is condemning components whose unsupported content is merely *spread out*, not one ghost |
| **B** transitive proximity merge, component-**independent**, d = 3 cm | 38.4 % | 30.4 % | 49.0 % | 47.9 % | works, but the extra reach over E is 1–4 points and it can join two components that the blob graph says are separate |
| **D** remove a run only if it touches a run the bound *already* removed (non-transitive), d = 3 cm | 17.9 % | 14.2 % | 21.4 % | 17.8 % | **too weak** — non-transitive, so it stops at the first link of a chain. On cluster 42 it catches run 2 and misses runs 1 and 3 |
| **E** transitive merge **within a component**, then the **same** 20 cm bound, d = 3 cm | 37.3 % | 29.1 % | 44.9 % | 43.6 % | **chosen** — within 1–4 points of B while never crossing a component boundary |

Variant E on cluster 42 unmerge at d = 3 cm merges k = 0, 1, 2, 3 into one **127.9 cm** group and
removes all **71** surviving unsupported blobs — the whole ghost, in one piece. On the baseline arm it
forms four groups, the largest 106.0 cm over 8 runs.

E's sensitivity to `d` is the thing to scan, and it turns over quickly:

| merge_d (cm) | 1 | 2 | 3 | 5 | 8 |
|---|---|---|---|---|---|
| 991 base | 12.2 % | 25.3 % | 37.3 % | 51.7 % | 74.0 % |
| 991 um | 14.7 % | 24.7 % | 29.1 % | 40.3 % | 67.9 % |
| 1079 base | 20.0 % | 33.1 % | 44.9 % | 60.8 % | 74.2 % |
| 1079 um | 19.1 % | 33.4 % | 43.6 % | 62.0 % | 73.4 % |

At d = 5 cm cluster 42's baseline groups fuse into a single **254 cm** chain of 12 runs — visibly
over-merging, two objects joined. **d = 3 cm is the operating point to scan around (1 / 2 / 3 / 5).**

> **Decision: R2b is a transitive same-component merge of runs before the existing bound**,
> `bad_blob_run_merge` (a length, 0 = OFF = today). It reuses the existing 20 cm bound rather than
> introducing a second one — but `merge_d` **is itself a new length threshold, and a sensitive one**:
> the result swings from 12 % to 74 % as it goes 1 → 8 cm, more leverage than the 20 cm bound it
> feeds. It is not a detail to be defaulted and forgotten. The operating point to scan around is
> **3 cm**, chosen because 5 cm demonstrably fuses two objects (cluster 42 baseline: a single 254 cm
> chain of 12 runs) and 1 cm recovers only a third of what 3 cm does. By construction R2b requires
> `bad_blob_max_run > 0`, which PDHD production already sets.

---

## 4. The two knobs

Both default OFF, both leave the legacy path textually intact, and the prototype is cited at the one
place where this tree deliberately diverges from it.

| | R2 | R2b |
|---|---|---|
| C++ key (`ImproveCluster_1`) | `hack_max_bridge` | `bad_blob_run_merge` |
| jsonnet arg (`pdhd/pr.jsonnet`, cm) | `retile_hack_max_bridge` | `retile_bad_blob_run_merge` |
| C++ default | `0.0` = uncapped = the prototype | `0.0` = judge each run alone |
| site | `improvecluster_1.cxx` `hack_activity_improved` | `BadBlobRuns.h` `analyze`, step 4 |
| precondition | none | `bad_blob_max_run > 0` (PDHD production sets 20 cm) |

**R2** adds one branch to the interpolation loop: when the gap exceeds the cap, the real path point is
kept and the invented interior is dropped. Two honest caveats, both in the code comment: the kept
point carries `wpid_p` rather than the interpolated `get_wireplaneid`, and `path_pts` gets shorter,
which shifts the `i±1` coverage test below it — **the knob-on path is not a subset of the knob-off
path**, so the scan grades tag flips as a set, not a count.

**R2b** adds step 4 to `BadBlobRuns::analyze`: transitively merge same-component runs whose
center-boxes lie within `run_merge`, then apply the *existing* `max_run` to each merged group's union
box. A run already over `max_run` is its own group and still dies, so the merged path subsumes the
plain one. `Run` gains `lo`/`hi` (the bbox it already computed and threw away) and `Result` gains
`removed_by_merge` — **census only**; `removed_by_run` stays the single authoritative removal list, so
there is no way to half-wire the knob.

**Threading** (Explore-verified, four layers): C++ `get(cfg, …)` ← key-suppressed `data` entry in
`cfg/pgrapher/common/clus.jsonnet:1454` ← `cm.improve_cluster_2(… * wc.cm)` at
`cfg/pgrapher/experiment/pdhd/pr.jsonnet:1275` ← `pr()` arg ← job TLA in
`pdhd/wct-pr-perevt.jsonnet`. **PDHD only**; `protodunevd/pr.jsonnet` is deliberately untouched this
round and PDVD inherits the C++ zeros.

### Tests

`./build/clus/wcdoctest-clus`: **328 cases / 23 096 assertions, all pass.** New:

- `doctest_bad_blob_runs.cxx` +4 cases — `run_merge = 0` reproduces the pre-doc-08 `Result` field for
  field; a 26 cm column cut into 12/6/3 cm runs by supported blobs survives a 20 cm bound and dies
  once merged at 3 cm but not at 1 cm (the 2 cm gap); the merge never crosses a component boundary;
  a run over the bound still dies on its own span and is *not* credited to the merge.
- `doctest_retile_knob_defaults.cxx` (new file) pins all four `default_configuration()` values —
  including `bad_blob_max_run` and `bad_blob_report`, which **no test pinned before**.

---

## 5. Gates

**Compiled-config proof** (M6), current `cfg/` against a pristine `git archive HEAD cfg` tree:

| job | knobs unset | knobs set |
|---|---|---|
| PDHD PR (`wct-pr-perevt.jsonnet`, evt 991) | **zero diff** — the only differences are the four path strings carrying the arm tag | exactly two added keys: `"hack_max_bridge": 200`, `"bad_blob_run_merge": 30` (internal mm) |
| PDVD PR (`039252/0`) | **identical**, 273 831 bytes | n/a — PDVD passes no knob |
| a caller passing anodes+samplers only (= `sbnd/clus.jsonnet:1984`, `clus/test/uboone-mabc.jsonnet:310` and the four `test-porting` configs) | **identical**; the compiled `ImproveCluster_2` data block is still exactly `anodes, detector_volumes, pc_transforms, samplers, verbose, wrapped_channel_activity` | n/a |

**The 30-event byte-identity gate.** `d08gref` (pin `ref`, the pre-doc-08 `libWireCellClus.so`) vs
`d08goff` (pin `new2`, this round's build), both `-stm -stm-fit`, knobs unset, 30 events:
**`d02_hash_gate.py` → PASS 30, FAIL 0, MISSING 0 of 30.**

That gate is the **binary-only** half, and it is deliberately reported as half. `run_pr_evt.sh:61`
*prepends* the live `toolkit/cfg` to `WIRECELL_PATH`, so an arm cannot be made to compile an older
cfg tree from outside — a `CFG=` option that tried was silently shadowed and has been removed from
`run_d08_arms.sh` with the reason recorded in its header. The config half is the compiled-config
zero-diff above; the two compose into the full claim, and they compose soundly precisely because key
suppression means the old binary is handed a config with no new key in it.

**PDVD smoke gate** — the second `improve_cluster_2` binder, 3 events (`039252/{0,10,11}`), same
TLAs, only the binary differs (`d08pvref` pin `ref` vs `d08pv` pin `new2`): **SAME 3/3**
(`b07c0f88…`, `f279f6fc…`, `11c69b5b…`). PDVD passes no doc-08 knob, so this exercises exactly the
guarded legacy branch.

**SBND smoke gate — NOT RUN, and here is what stands in its place.** The tree holds no QL pctree for
SBND's default sample, and its `run_pr_evt.sh` does `rm -rf "$PRDIR"` inside a work root that
otherwise belongs to a peer's campaign; reconstructing another experiment's sample selection to gain
one more instance of an already-gated branch was not worth the risk. What is proven instead:
SBND's compiled `ImproveCluster_2` block is byte-identical and carries **neither new key** (the
no-knob probe above), so its C++ reads the `0.0` defaults and takes the same guarded branch that the
PDHD 30-event gate and the PDVD 3-event gate both show byte-identical. Stated as a gap, not as a pass.

**Single-event identity and the knob-fires control** (evt 991, `hash_archive.py` member content):

| arm | pin | cfg | knobs | member hash | |
|---|---|---|---|---|---|
| `d08off` | `new` (stage 1) | pre-doc-08 | — | `ce10012d44ce689e…` | reference |
| `d08v1` | `new2` (stage 2) | current | unset | `ce10012d44ce689e…` | **SAME** |
| `d08von` | `new2` | current | bridge 20, merge 3 | `603616f72663d304…` | **DIFFERS** — the knobs fire |

**The C++ merge reproduces the model that chose it.** The offline simulation of §3 and the shipped
`BadBlobRuns::analyze` step 4 must agree, or §3's decision table was computed with the wrong model.
They are compared on the **first** retile pass, the only one whose input is identical in a knob-off
and a knob-on arm (once pass 1 removes different blobs, pass 2 is retiling a different intermediate
cluster). On evt 991 at `merge_d = 3 cm`, over the same 101 `(cid, apa, face)` passes:

| | blobs removed by the merge |
|---|---|
| `d08_run_merge_sim.py --pass first --predict 3` on the knob-off arm | **501** |
| `merge_rm=` summed over the first pass of arm `d08xval` (knob on) | **501** |

Exact. The *last*-pass totals differ (model 1 564, C++ 1 551) — as they must, and that difference is
itself the sign that pass 1's extra removals propagate into pass 2's retile.

**The effect, quoted from `d08von`'s own log** (CLAUDE.md §4 "visible in a log line"):

```
capped=   187 bridges refused across 74 hack_activity_improved calls
new_cells 209 537 -> 94 887      (-55 % of everything the retiler invents)
merge_rm= 1 694 blobs removed by the run merge, across 21 retile passes
cluster 42:  nnew 1340 -> 728,  maxrun_cm 43.6 -> 25.6,  merge_rm=285
```

**And the owner's actual question — ghost Steiner graph points** (`d08_steiner_ghost.py --pair`,
evt 991). doc 07 counted retiled *blobs*; this counts points of the Steiner cloud the owner sees in
Bee, by distance to the nearest live-charge point (the doc pdvd/40 statistic).

*The confound, and its control.* That Bee layer carries only the **STM-fitted** clusters, and these
knobs change which clusters get a fit (20 fitted off, 18 on). A raw arm-vs-arm count would mix "less
fabrication" with "two fewer clusters drawn". `--pair` therefore matches layer clusters between arms
by centroid (the layer's `cluster_id` is a per-drawing index, not the tagger's) and reports only the
**matched** set. FRAME control: median `steiner_terminals` → live distance 0.000 cm, PASS.

| evt 991, 18 matched clusters | Steiner pts | > 3 cm from live | > 10 cm | > 30 cm | worst |
|---|---|---|---|---|---|
| knobs off | 24 397 | 649 | **67** | 0 | 22.0 cm |
| bridge 20 + merge 3 | 23 706 | 358 (−44.8 %) | **0** | 0 | **8.6 cm** |

2 base clusters were drawn but unmatched and are excluded — that is the population change the raw
numbers (690 → 358, 80 → 0) would have hidden. The centroid tolerance is a matching parameter, not a
physics one, and the conclusion does not depend on it: over the 30-event `d08goff → d08cap10` pair,
points > 10 cm from live go 263 → 4 (tol 2 cm), 876 → 6 (5), 1 205 → 6 (20), 1 419 → 6 (50), while
unmatched clusters fall 233 → 7 per arm. Default 20 cm. The unmatched counts stay **equal on the two
sides at every tolerance**, which is the check that the matcher pairs symmetrically instead of
dropping one arm.

---

## 6. The 30-event scan

Baseline `d08goff` (knobs unset, pin `new2`), 30 events, production `-stm -stm-fit`, all arms on the
same pin and the same `stm0` pctrees. Ghost columns are the matched-cluster metric of §5; **the
matched-cluster count is printed because it is the denominator** and a metric that silently drops
clusters is not comparable across arms.

*Why the tolerance is 50 cm.* A cluster fails to match when its centroid moved, and the centroid
moves precisely when its Steiner cloud changed — so a tight tolerance drops the **most affected**
clusters and understates the arms with the largest effect. On `d08cap10` the measured improvement in
"> 3 cm" rises monotonically as the exclusion shrinks: −66 % (tol 2 cm, 233 unmatched per arm), −74 %
(5, 114), −78 % (20, 20), −79 % (50, 7). At 50 cm the denominators agree across arms (774–781 of
~790) and the rows are comparable; at 20 cm they did not.

| arm | knob | matched | > 3 cm | > 10 cm | > 30 cm | worst | TGM ± | STM ± | FC ± |
|---|---|---|---|---|---|---|---|---|---|
| `d08cap10` | bridge cap **10 cm** | 774 | 17 583 → **3 719** (−79 %) | 1 419 → **6** | 17 → **0** | 39.2 → **11.3** | 0/0 | 21/24 | 4/4 |
| `d08cap20b` | bridge cap **20 cm** | 774 | 17 583 → 12 922 (−27 %) | 1 419 → **22** | 17 → **0** | 39.2 → **13.5** | 0/0 | 18/21 | 3/4 |
| `d08cap40` | bridge cap **40 cm** | 779 | 17 724 → 16 265 (−8 %) | 1 433 → 748 | 17 → **0** | 39.2 → **20.1** | 0/0 | 10/11 | 2/2 |
| `d08mrg1` | run merge **1 cm** | 781 | 17 724 → 16 161 (−9 %) | 1 433 → 1 370 | 17 → 16 | 39.2 → 39.2 | 0/0 | 7/7 | 0/0 |
| `d08mrg3` | run merge **3 cm** | 781 | 17 724 → 10 118 (−43 %) | 1 433 → 1 275 | 17 → 16 | 39.2 → 39.2 | 0/0 | 13/13 | 0/0 |
| `d08mrg5` | run merge **5 cm** | 781 | 17 724 → 8 514 (−52 %) | 1 433 → 1 207 | 17 → 16 | 39.2 → 39.2 | 0/0 | 17/18 | 0/0 |
| `d08both` | cap **20** + merge **3 cm** | 774 | 17 583 → 7 933 (−55 %) | 1 419 → **21** | 17 → **0** | 39.2 → **13.5** | 0/0 | 22/23 | 3/4 |
| `d08mr10` | *add-on* `max_run` 20 → **10 cm** | 780 | 17 698 → 9 317 (−47 %) | 1 433 → 1 085 | 17 → 16 | 39.2 → 39.2 | 0/0 | 7/6 | 0/0 |
| `d08mr15` | *add-on* `max_run` 20 → **15 cm** | 780 | 17 698 → 13 037 (−26 %) | 1 433 → 1 225 | 17 → 16 | 39.2 → 39.2 | 0/0 | 8/3 | 0/0 |
| `d08mr30` | *add-on* `max_run` 20 → **30 cm** | 781 | 17 724 → **27 282 (+54 %)** | 1 433 → **3 930** | 17 → 17 | 39.2 → 39.2 | 0/0 | 3/5 | 0/0 |

Six things follow, and the first is the whole point of the round.

1. **Only the bridge cap removes the FAR ghosts.** Every cap arm takes points > 30 cm from live
   charge to **zero** and pulls the worst ghost in the 30 events from 39.2 cm to 11–20 cm. Every
   arm that instead moves the run bound leaves them: > 30 cm stays at 16–17 and **the worst ghost
   does not move at all, 39.2 → 39.2 cm**, at any threshold. This is doc 07 §5's prediction —
   *fragmentation is the defect, the threshold is not* — now measured on 30 events. A ghost that
   survives in pieces is invisible to any bound on a piece.
2. **The run bound is a near-field instrument at every value, and 20 cm is a sensible point on that
   curve.** Doc 07 §6 item 1 asked PDHD to scan the threshold for itself; it now has, at 10 / 15 /
   20 / 30 cm. Tightening it improves only the near field (> 3 cm −47 % at 10 cm) and tightening or
   loosening it leaves the far field untouched (> 30 cm 17 → 16/16/17, worst 39.2 → 39.2 at every
   value). Loosening to 30 cm costs 54 % on the near field, so the bound is doing real work and
   should not be relaxed. **This is not a claim that 20 is optimal** — the four values were graded on
   one metric and their STM costs are all small and undifferentiated (7/6, 8/3, —, 3/5), so nothing
   here picks between 10, 15 and 20. What it does establish is that no setting of this knob
   addresses the ghosts the owner asked about.
3. **The TGM tagged SET is identical in every single arm** — the same objects, not merely the same
   count (these are knob-ON arms, so their archives are of course not byte-identical). The cosmic
   tagger, the stage PDHD production exists for, does not notice any of these knobs. That is the
   strongest cost result in the table.
4. **The run merge cleans the near field and cannot reach the far field**, at every value tested.
   `mrg1/3/5` take "> 3 cm" down by 9 / 43 / 52 % while "> 10 cm" barely moves (1 433 → 1 370 /
   1 275 / 1 207) and the worst ghost never moves at all. That is not a disappointment, it is the
   comparison this round was built to make, and it is forced by the mechanism: **every run the merge
   joins is by construction shorter than the 20 cm bound**, so the merge can only ever remove short
   fabrications. A 39 cm ghost is made by a bridge, and only a cap on the bridge prevents it. Doc 07
   §5's "if they are redundant, R2 wins because it prevents" is answered: they are not redundant,
   they act on different things, and R2 is the one that answers the owner's question.
5. **Combining them does not beat the tighter cap alone.** `d08both` (cap 20 + merge 3) reaches
   > 3 cm = 7 933 and worst 13.5 cm for 22/23 STM flips; `d08cap10` alone reaches **3 719** and
   **11.3 cm** for 21/24. The merge's near-field contribution is real (`cap20b` alone leaves 12 922)
   but it is bought more cheaply by tightening the cap. Untested and worth one arm: cap 10 **+**
   merge 3.
6. **The cost is STM churn, and it scales with the cap's aggressiveness.** See §8.

**Wall and memory** (median over 30 events): baseline 50.0 s / 3.94 GB; every arm 49.0–49.5 s /
3.94–3.97 GB. These arms ran at different times on a shared box, so read this as *no blow-up*, not as
a speed-up.

---

## 7. Add-on: the same census on PDVD

doc 07 §6 item 5. Log-only, no config or code change — `retile_bad_blob_report` already exists on
PDVD. Three events, arm `d08pv` (`pdvd/work/039252_{0,10,11}_d08pv`, pctrees symlinked from
`_d143pnew`, pin `new2`).

**PDVD has the same defect and its long bridges are even more concentrated:**

| | 039252/0 | 039252/10 | 039252/11 | (PDHD 991 base, for scale) |
|---|---|---|---|---|
| bridges | 49 210 | 59 542 | 55 052 | 25 701 |
| cells newly painted | 369 699 | 486 845 | 438 525 | 209 537 |
| bridges > 20 cm | 65 (**0.13 %**) | 114 (0.19 %) | 127 (0.23 %) | 185 (0.72 %) |
| …their share of all new cells | **55 %** | **66 %** | **58 %** | 54 % |
| unsupported blobs in kept components | 10 805 | 13 101 | 12 572 | 11 435 |
| removed by the 20 cm run bound | 73.0 % | 69.3 % | 51.6 % | 63.3 % |
| **survivors** | **2 917** | **4 025** | **6 079** | 4 198 |
| same-component share of adjacent run pairs | 100 % (2/2) | 77.8 % | 65.6 % | 95.4 % |
| variant E at d = 3 cm recovers | 14.1 % | 9.9 % | 22.1 % | 37.3 % |

**On the "class (c)" claim.** `pdvd/wct-pr-perevt.jsonnet:139-142` says *"Do NOT read the residual as
a reason to lower it: what survives is class (c), blobs that overlap an original blob in WIRE space
but sample far from it in 3D."* That is a statement about **supported** blobs. The census shows it is
not the whole story: **2 917 – 6 079 blobs per event survive that are classified UNSUPPORTED**, sit
in runs, and live only because their run is shorter than 20 cm. Both populations are real — class (c)
blobs never enter a run at all — but the driver comment reads as if the unsupported residual were
empty, and it is not. PDVD deserves the same knobs; this round does not touch its config.

*(Sample caveat: three cosmic events, and the same-component share ranges 66–100 % over them, so the
merge's reach on PDVD is less well pinned than on PDHD's four arms.)*

---

## 8. The cost, and what blocks a flip

**Start with what does not move.** `TaggerCheckTGM` produces the **identical tagged set** in every
one of the seven arms — not the same count, the same objects. PDHD production is a cosmic-tagger
chain, and it does not notice these knobs. `TaggerCheckFC` moves by 0–4 objects.

**The cost is STM churn.** `TaggerCheckSTM`'s tagged set is 174 objects over 30 events; the arms move
it like this (a **set** census — a count census would report a benign net of −3 and hide all of it,
the failure doc pdvd/100 recorded):

| arm | STM gained | STM lost | net | events with any flip |
|---|---|---|---|---|
| `d08cap10` | 21 | 24 | −3 | 24 / 30 |
| `d08cap20b` | 18 | 21 | −3 | — |
| `d08cap40` | 10 | 11 | −1 | — |
| `d08mrg3` | 13 | 13 | 0 | — |
| `d08mrg1` | 7 | 7 | 0 | — |
| `d08mr10` (add-on) | 7 | 6 | +1 | — |

45 of 174 STM objects change under `cap10`. **That is what blocks a default flip, and it is not
resolved here.** Two things make it tractable rather than open-ended:

- **The losses have a small stable core.** 6 objects lose their tag under *every* cap value — 10, 20
  and 40 cm alike (evt/cluster 12/48, 13/116, 14/45, 15/37, 16/111, 21/116) — and `cap10` and
  `cap20b` share 16 of their 24 and 21 losses. The union over all seven arms is 40 objects. A hand
  scan of those **6** decides whether the cap is removing support that was real or fabricated; the
  rest are cap-value tuning on top of that answer.
- **The two knobs move largely different objects**: only 4 of `cap10`'s 24 losses are also lost by
  `mrg3`. They are not substitutes and their costs do not simply add.

**The two objects doc 04 §12 named** — evt 1 cluster 113 and evt 12 cluster 108 — remain `STM=1` in
the baseline and in `cap10` and `cap20b`. They were already tagged before this round; the point is
only that the cap does not take them away.

**The scan is built and running: `pdhd/d08_scan/`, port 5017.**

```bash
cd wcp-porting-img/pdhd/d08_scan && ./serve_d08_scan.sh 5017
ssh -L 5017:localhost:5017 user@wcgpu1     # then http://localhost:5017/d08_scan_viewer
python3 score_d08_scan.py                  # after labelling
```

Forked by duplication from `pdhd/stm_scan/` (untouched). 45 items — every object whose STM verdict
moves — in a fixed-seed shuffle. The sheet (`docs/scan/d08_stm_flip_sheet.tsv`) carries **no verdict
and no direction**: knowing an object *lost* its tag is the most biasing fact available, so it is not
on the sheet, not in the UI, and not in the item label. The key is separate.

A **REVEAL** toggle draws both arms' Steiner cloud (orange = before, cyan = after) and STM fit
(magenta × = before, blue + = after; the red dashed box is the active boundary, so no marker uses
that red) and prints both verdicts — the before/after view, off by default, with
`revealed_before_label` recorded on anything labelled while it is on so `score_d08_scan.py` can
report blind and revealed labels apart.

**The banner also prints each arm's `persist_stm_fit` line, and that is what makes a flip legible.**
The tag does not turn on the fit's point count; it turns on `status / kink / exit_L / left_L`. Two of
the first three items show why the overlays alone are not enough — item 3 (evt 14, cluster 119) is
`status=3 kink=904 exit_L=584.2` before and `status=0 kink=953 exit_L=618.1` after, and item 1 gains
its tag while the fit *shrinks* 174 → 171 points. doc pdvd/40 r3 found 3 of 13 flips were kink
relocation with the trajectory essentially unchanged; without these fields a scanner sees two
near-identical fits and an inverted verdict with nothing to explain it
(`feedback_status_code_is_not_a_mechanism`).

Three facts were checked rather than assumed, by `selftest_d08_scan.py` (47 checks, all passing):

- `clustering-global` has the **identical point set and charges** in all 30 events across the two
  arms, so the charge panels cannot encode which arm produced them;
- in 9 of 30 events a handful of points (0.005–2.3 %) change *which cluster* they belong to; for the
  **2** scan items where that touches the item's own cluster the sheet flags `partition_moved=1` and
  the scorer excludes them from the headline. The other **43 have a Jaccard overlap of exactly
  1.000** — the same object in both arms. The panels always draw the base partition, so for those two
  the header now names the *other* arm's size as well — evt 3 cluster 48 is 10 points here and **4**
  in the cap arm; evt 26 cluster 36 is 17 here and **37** there. Half the object, or twice it, is
  more than a footnote to a scanner judging containment;
- the Bee `stm_tagged` layer's verdict differs between arms for **all 45** items, an independent
  confirmation of the flip list built from the tagger log.

**Acceptance bar, fixed in `score_d08_scan.py` before any label exists:** (1) the cap arm must agree
with the scanner on strictly more scored items than the baseline; (2) of the 6 core objects, a
majority must be `THRU`/`FRAG → THRU`, i.e. tags correctly removed — if most are real stoppers the cap
value must come down even if (1) passes; (3) blind labels govern where blind and revealed disagree;
(4) the 2 moved-partition items are reported apart.

**Precedent for the adjudication.** doc pdvd/40 r3's flip needed the owner to rule on 13 verdict
flips, and that scan produced a correction: 3 of them were kink relocation near a track end, not lost
crossings. The same care applies here.

### 8.1 The scan result (2026-09-06, tag `d08flip0`, 45/45 labelled, 0 revealed)

`work/d08_scan_labels/d08flip0/labels.json`; `python3 d08_scan/score_d08_scan.py`.

**35 of 45 items came back MESSY or UNCLEAR**, and they are the small objects — median **125 points /
89.5 cm**, against **4 581 points / 386 cm** for the 10 that could be judged. Three-quarters of the
flip population is not decidable from charge, so this scan cannot certify the STM cost in either
direction. On the 10 that are decidable:

| arm | correct | on tags the cap GAINED | on tags the cap LOST |
|---|---|---|---|
| `d08goff` (knobs off) | **5/10** | 2/5 | 3/5 |
| `d08cap10` | **5/10** | 3/5 | 2/5 |
| `d08cap20b` | 2/10 | 1/5 | 1/5 |
| `d08cap40` | 2/10 | 0/5 | 2/5 |
| `d08mrg1` | 6/10 | 2/5 | 4/5 |
| `d08mrg3` | 6/10 | 3/5 | 3/5 |
| `d08mrg5` | 4/10 | 2/5 | 2/5 |
| `d08both` | 3/10 | 1/5 | 2/5 |

(`docs/scripts/d08_score_arms.py`. The item list is `d08cap10`-selected, so an arm that flips fewer of
these items looks more like the baseline by construction; this is not each arm's score on a population
chosen for it. At n = 10 nothing here separates.)

**The cap and the baseline are tied at 5/10.** `score_d08_scan.py`'s clause 1 asked the cap to do
strictly better, which was a stricter bar than the round's own criterion — *"the primary metric moves
materially with no net tag loss the owner rejects"*. The primary metric is the ghost distance, and the
scan's job was to catch a cost worth rejecting. It found a tie.

**The 6-object core came back 4 UNCLEAR, 1 MESSY, 1 STM**, so clause 2 is neither passed nor triggered.
The one verdict is adverse: real event 1095 cluster 45, labelled **STM**, lost its tag.

### 8.2 Why the tags move: it is mostly not lost support

Reading each lost tag's `persist_stm_fit` line in both arms (§8's reveal banner prints it):

| status 0 becomes | n | meaning |
|---|---|---|
| 3 | 7 | `flag_pass` false — the kink/geometry test |
| 2 | 6 | leftover past the kink too long or too heavy (`left_L > 40 cm`, or > 7.5 cm at > 2× MIP) |
| 4 | 3 | `check_other_tracks` finds mid-point tracks |
| 5 | 3 | `detect_proton` fires |
| 7 | 1 | a guard rejected |
| (no comparable pass) | 4 | |

**6 of the 20 have an essentially unchanged fit** (|Δkink| ≤ 5 and |Δnpts| ≤ 10) — same trajectory,
inverted verdict. Real event 1151 cluster 116 is kink 462 → 457 over 462 → 457 points and loses the
tag to `detect_proton`; 1087/116 is 165 → 166 points and loses it to `flag_pass`. That is tagger
sensitivity around an unchanged muon, the doc pdvd/40 r3 pattern, not support the cap removed. The
6-object core splits the same way: three unchanged fits (1087/116, 1095/45, 1151/116), two where the
fit got *longer* and the kink moved to the front (1079/48 125 → 224 points, kink 125 → 81; 1103/37
196 → 233, kink 196 → **9**), and one that produces no fit at all under the cap (1111/111).

---

## 9. Recommendation

1. **`retile_hack_max_bridge` is the fix for what the owner asked about.** It is the only knob tested
   that removes the *far* ghosts: > 30 cm from live charge goes to zero and the worst ghost in 30
   events drops from 39.2 cm to 11–20 cm. Nothing that moves the run bound touches them at all.
2. **Do not lower `retile_bad_blob_max_run`, and do not raise it.** Lowering it to 10 or 15 cm trims
   the near field and leaves the worst ghost exactly where it was; raising it to 30 cm makes the
   metric 54 % worse. 20 cm is the right value, now measured on PDHD rather than inherited.
3. **`retile_bad_blob_run_merge` is a complement, not the fix.** At 3 cm it removes 43 % of the near
   ghosts and 29–45 % of the surviving unsupported blobs, but it cannot reach a 39 cm ghost, because
   every run it merges is by construction shorter than 20 cm. Worth having; not what closes the
   owner's complaint.
4. **The arm taken to the hand scan, and now to production: `retile_hack_max_bridge = 10`, merge off.** It is the
   strongest configuration measured on every ghost column (> 3 cm −79 %, > 10 cm 1 419 → 6, worst
   39.2 → 11.3 cm) and it costs no more than the alternatives (24 STM losses against 21 for cap 20
   and 23 for cap 20 + merge 3, with 16 of them shared). Combining a looser cap with the merge is
   strictly worse on every column. The remaining choice — is 10 cm too aggressive? — is a physics
   judgement about the **6 objects of §8**, not a number this document can settle. One further arm
   is worth having before that scan: cap 10 **+** merge 3, the one combination not run.
5. **PDVD should get both knobs** once PDHD's operating point is chosen — its long bridges are even
   more concentrated (§7) and its driver comment currently understates the unsupported residual.

---

## 9.1 FLIPPED — `retile_hack_max_bridge = 10 cm`, PDHD **and** PDVD production, owner 2026-09-06

The owner's decision, after the §8.1 scan, on the criterion **"are we creating ghosts"** rather than
on the STM tag census:

- **We are.** `new_frac` is **0.878** for gaps over 60 cm — nearly nine of every ten cells such a
  bridge paints did not exist before — while cells already flagged dead are **0.3–0.8 %** of what any
  bridge touches (§2). These bridges are inventing, not crossing dead regions, which was the one
  mechanism that would have made a length cap harmful.
- The cap removes exactly that: **> 30 cm from live charge 17 → 0, > 10 cm 1 419 → 6, worst ghost
  39.2 → 11.3 cm**, TGM tagged set unchanged, wall time 50.0 → 49.0 s (§6).
- The STM churn is a downstream proxy and the scan scored it a **tie** (5/10 both arms), with 6 of 20
  lost tags showing an unchanged fit (§8.2).

### What changed

| file | change |
|---|---|
| `cfg/pgrapher/experiment/protodunevd/pr.jsonnet` | **new** `retile_hack_max_bridge=null` arg + key-suppression pass-through — PDVD had no knob path at all before this |
| `wcp-porting-img/pdhd/wct-pr-perevt.jsonnet` | `retile_hack_max_bridge = null` → **10** |
| `wcp-porting-img/pdvd/wct-pr-perevt.jsonnet` | **new** TLA + pass-through, set to **10** |

`retile_bad_blob_run_merge` stays `null` on both: every run it can merge is by construction shorter
than `retile_bad_blob_max_run`, so it never reaches a far ghost (worst 39.2 → 39.2 cm at 1/3/5 cm).
`retile_bad_blob_max_run` stays at 20 cm on both.

### Gates for the flip

| check | result |
|---|---|
| PDVD compiled config, knob unset, vs the pre-flip compile (`039252_0_d08cfgA` → `_d08cfgC`) | **identical** but for the arm-tag path strings; the `ImproveCluster_2` block still carries no `hack_max_bridge` |
| PDHD + PDVD compiled config with the flip in place (`_d08cfgD`) | both `"hack_max_bridge": 100` (mm = 10 cm), `"bad_blob_max_run": 200`, `bad_blob_run_merge` **absent** |
| **installed** `local/lib/libWireCellClus.so` | was **15:07, without the knob** — the whole campaign ran off the `d08_libpin/new2` pin, so a config-only flip would have been a silent no-op. Re-installed; now `aa03c8fc…` = the pinned, tested binary, and newer than the last source edit |
| PDVD knob-ON smoke, 3 events, installed lib | rc=0 ×3; member hashes **DIFFER** on evt 0 and 10 (`b07c0f88…`→`ee16d8e6…`, `f279f6fc…`→`33ce636a…`), identical on evt 11 (no `steiner_graph` layer in either arm) |
| PDVD wall time | 18/24/25 s → **11/16/16 s** — the cap is cheaper, there is less invented cloud to carry |

### 9.2 The PDVD 30-event grade — run after the flip, and it holds

```bash
ARM=d08pv30off TLA="-S retile_hack_max_bridge=null" JOBS=12 bash run_pdvd30.sh
ARM=d08pv30on  TLA=""                                JOBS=12 bash run_pdvd30.sh
python3 pdhd/docs/scripts/d08_steiner_ghost.py d08pv30off d08pv30on --pair \
        --run6 039349 --work ../pdvd/work
python3 pdhd/docs/scripts/d08_tag_flips.py d08pv30off d08pv30on 039349 ../pdvd/work
```

Run 039349, events 0–29 (the sample docs 45 and 48 grade on), both arms 30/30 rc=0. The knob-off arm
is the *same* build with `-S retile_hack_max_bridge=null`, which was verified to compile the key away
before the arms were launched.

| PDVD, 144 matched clusters | knobs off | cap 10 cm |
|---|---|---|
| Steiner points | 134 163 | 133 610 |
| > 3 cm from live charge | 688 | **374 (−45.6 %)** |
| **> 10 cm** | **22** | **0** |
| > 30 cm | 0 | 0 |
| worst ghost | 13.0 cm | **7.6 cm** |
| wall time, 30 events | 630 s (median 22) | 633 s (median 22) |

**PDVD had ghosts of its own and the cap removes all of them.** The 3-event smoke of §9.1 saw none
(> 10 cm = 0 in both arms) and understated the case; at 30 events the defect is there — milder than
PDHD's, worst 13.0 cm against 39.2 cm, but real, and the cap takes the > 10 cm population to zero.

**The cost is far smaller than PDHD's:**

| tag | base | arm | gained | lost | events touched |
|---|---|---|---|---|---|
| TGM | 494 | 494 | 0 | 0 | none |
| FC | 522 | 522 | 0 | 0 | none |
| STM | 147 | 145 | **1** | **3** | 4 of 30 |

**And all four STM flips have an essentially unchanged fit** — the §8.2 pattern, cleaner here because
there are only four to read:

| evt | cluster | | status | kink | exit_L |
|---|---|---|---|---|---|
| 5 | 54 | gained | **5 → 0** (`detect_proton` stops firing) | 492 → 488 | 310.3 → 311.2 |
| 2 | 41 | lost | 0 → 3 | 167 → 162 | 103.2 → 100.3 |
| 8 | 55 | lost | 0 → 3 | **114 → 114** | **74.0 → 74.0** |
| 18 | 44 | lost | 0 → 3 (pass 1) | 78 → 77 | 49.0 → 49.5 |

Event 8 cluster 55 is the clean case: **every fit number is identical** and only the status moves. On
PDVD the whole STM cost of this flip is 4 objects in 147, and not one of them is a track the cap
reshaped. That is a tagger-sensitivity question (`flag_pass`, `detect_proton`), and it is the same one
PDHD's §8.2 raises.

### The limit that remains on the PDVD half

PDVD now has its own 30-event grade (§9.2) and it supports the flip on PDVD's own data. What it does
**not** have is a **hand scan**: the four STM objects that move have not been looked at by a person,
and PDVD's consumer (`CheckSTM_Michel`, doc pdvd/48) is not PDHD's. With TGM and FC both at zero
flips and all four fits unchanged, the residual risk is small and named; it is not zero.

---

## 10. Not done

- ~~No default was flipped~~ — **`retile_hack_max_bridge = 10` is PDHD and PDVD production as of
  2026-09-06 (§9.1).** `retile_bad_blob_run_merge` is still `null` everywhere and remains ungraded in
  production; the C++ defaults of both are still 0.
- **PDVD is graded now** (§9.2, 30 events on run 039349): > 10 cm 22 → 0, worst 13.0 → 7.6 cm, TGM and
  FC unmoved, 4 STM flips in 147 and all four with an unchanged fit. What is still missing there is a
  **hand scan** — nobody has looked at those four objects, and PDVD's consumer is `CheckSTM_Michel`,
  not PDHD's tagger.
- **The SBND runtime gate was not run** (§5): no QL pctree for its default sample, and its runner
  `rm -rf`s a PR dir inside a peer's live work root. Substituted by the compiled-config proof that
  SBND's `ImproveCluster_2` block is byte-identical and carries neither key. This is a gap.
- **PDVD got `retile_hack_max_bridge` only.** `retile_bad_blob_run_merge` was not wired into
  `protodunevd/pr.jsonnet`, so PDVD has no path to it; PDHD has the path with the value `null`.
- **The 6 objects of §8 are still unjudged.** The blind scan returned 4 UNCLEAR, 1 MESSY and 1 STM on
  them (§8.1). §8.2 shows three of the six lose the tag with an unchanged fit, which points at
  `detect_proton` and the kink test rather than at the cap — a separate round.
- **One combination was not run**: cap 10 + merge 3.
- **`sprior` conflates** a bridge re-covering itself with the `temp` pass retracing the `orig` pass's
  ghost. Separating them needs a per-call cell map as well as the shared one. It was not needed for
  the decision — the decision rests on `new` against `sreal + sdead` — and is not measured.
- **Two events for §2/§3, three for §7.** The 30-event evidence is the scan and the gate; the census
  rates that *chose the knob forms* rest on four arms over two PDHD events and three PDVD events.
- **The census counts blobs and Steiner points, never Steiner graph EDGES.** A ghost node implies
  ghost edges, but the edge count itself is still not measured.
