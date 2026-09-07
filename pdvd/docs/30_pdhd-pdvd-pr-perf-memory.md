# 30 — PDHD and PDVD PR jobs: where the running time and the 7 GB go

**Status (2026-09-07).** The owner asked why the cosmic-tagger / STM-Michel jobs peak near
7 GB. Measured both detectors and both chains, attributed the peak to one stage and one
line, and shipped the fix. PDHD's worst event went **7.51 → 5.00 GB** and no event on the
61-event arm is above 6 GB any more (4 were); the arm's node core-s is unchanged
(2083.3 → 2072.8). Gates in §7: **362 events x 4 products, all identical** — PDHD 61/61 and
PDVD 120/120 in both `-stm` and `-nu`, including the ROOT tree the change writes.

**One-line cause.** Every STM fit pass's 2-D charge map was held in **three** live copies
at once. Two of the three were copies of a container that was dead on the next line. Two
`std::move`s remove them, and the output is byte-identical by construction.

**Scope.** The "cosmic tagger job" and the "STM_Michel job" are one job:
`{pdhd,pdvd}/run_pr_evt.sh`, flag `-stm` (cosmic taggers only, both detectors' default)
vs `-nu` (appends `CheckSTM_Michel`). Every stage runs as an `IEnsembleVisitor` inside a
single `MultiAlgBlobClustering` node, so per-stage attribution comes from MABC's own
`Perf` (`perf: true`, already on in production), not from the pgraph timer.

## 0. Repro

```bash
# Pins.  PRE  = /home/xqian/tmp/d30_libpin      libWireCellClus.so md5 b3495810c15b
#        POST = /home/xqian/tmp/d30_libpin_post libWireCellClus.so md5 a315be6b7b24
# Operating point for EVERY number below: PDHD curved_fv=true profile=p90 margin_y/z=3
# (production since 2026-09-07), save_stm_fit=true, nu_per_bundle_stm_only=true,
# protect_stm_only_bundles=true.  Sequential arms are marked; the rest ran at JOBS<=6
# and therefore publish memory only, never node_core_s.
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img

# 1. the accumulator bracket, sequential, two 8 GB events  (sec 3)
#    a1 = production, a2 = no ROOT writer, a3 = save_stm_fit off
for t in a1 a2 a3; do for e in "029107 18 d09ctl2" "028084 2 d09"; do set -- $e
  pdhd/stm/perf/d30_stage.sh $1 $2 $3 d30$t; done; done
pdhd/stm/perf/d30_run_a.sh          # PIN=/home/xqian/tmp/d30_libpin, PDHD_MAX_JOBS=1

# 1b. the instrument check of sec 1 (reported peak vs the job's own ladder, every job)
pdhd/stm/perf/d30_c1_scan.sh pdhd/work > c1_pdhd.txt   # and pdvd/work

# 2. live heap: jemalloc sampling, then the converter (jeprof is not on PATH)  (sec 4)
cd pdhd/work/029107_18_d30hp
env LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2 \
    MALLOC_CONF=prof:true,prof_prefix:$H/je,lg_prof_sample:19,lg_prof_interval:31,prof_final:true \
    GOGC=off wire-cell -l stderr -l wct_heap.log:debug -L debug -c .wct-pr_d30hp.json
python3 pdhd/stm/perf/je2pprof.py $H/je.<pid>.29.i29.heap $H/i29.pprof.heap
google-pprof --text --cum --inuse_space $(which wire-cell) $H/i29.pprof.heap | head -35

# 3. the 61-event PDHD arms and the 120-event PDVD arms, pre vs post
ARM=d30hpre  PIN=/home/xqian/tmp/d30_libpin      JOBS=6 pdhd/docs/scripts/d30_run_pr_arm.sh
ARM=d30hpost PIN=/home/xqian/tmp/d30_libpin_post JOBS=6 pdhd/docs/scripts/d30_run_pr_arm.sh
ARM=d30vpre  PIN=/home/xqian/tmp/d30_libpin      JOBS=5 pdhd/stm/perf/d30_run_pdvd_arm.sh
ARM=d30vpost PIN=/home/xqian/tmp/d30_libpin_post JOBS=5 pdhd/stm/perf/d30_run_pdvd_arm.sh
#    ... and the same four with MODE=-nu (arms d30{h,v}nu{pre,post})

# 4. census and the scaling law
python3 pdhd/stm/perf/d30_pr_census.py --tsv pdvd/docs/perf/doc30_pdhd_stm.tsv pdhd/work d30hpre d30hpost
python3 pdhd/stm/perf/d30_pr_census.py --tsv pdvd/docs/perf/doc30_pdvd_stm.tsv pdvd/work d30vpre d30vpost
python3 pdhd/stm/perf/d30_law.py pdvd/docs/perf/doc30_pdhd_stm.tsv

# 5. gates (member content / ROOT TREE content, never md5 on an archive -- M2)
python3 pdhd/stm/perf/d30_hash_gate.py pdhd/work d30hpre d30hpost
python3 pdhd/stm/perf/d30_hash_gate.py pdvd/work d30vpre d30vpost
```

## 1. The instrument, and a bug in it

Two numbers are available per job and they disagree:

- `pr_resource_<run>_<evt>.txt` `peak_rss_gb` — the max over **2 s samples** of `VmHWM`,
  taken by a loop that dies with the job. The last ~2 s (writers + teardown) can be
  unobserved.
- the `MEM:` ladder in the log — `/proc/self/statm` resident, read once per stage.

On jobs whose sampler covered the tail the two agree **exactly** (doc-30 arms: 5.99/5.99,
7.35/7.35, 1.91/1.92 GB). On the rest the sampled value is **lower than the job's own
ladder**. Scanned with `pdhd/stm/perf/d30_c1_scan.sh` over every PR job on disk:

| | n jobs | sampler under-reports | mean deficit | worst | p50 as reported | p50 corrected |
|---|---|---|---|---|---|---|
| PDHD | 1132 | 243 (21.5 %) | 0.20 GB | 1.16 GB | 2.79 | 2.82 |
| PDVD | 1832 | 1037 (56.6 %) | 0.17 GB | 0.44 GB | 1.25 | **1.36** |

**Everything below publishes `peak = max(sampled VmHWM, max ladder res)`**
(`d30_pr_census.py`). Percentiles taken from a naive read of `pr_resource` are biased low
by this; PDVD's p50 is 1.36 GB, not 1.25. The harness fix — read `VmHWM` once after
`wait`, on both detectors — is named in §9 and was **not** taken here (it is a runner
change, not a toolkit one, and it would change no physics).

A second question the same data answers: **there is no transient spike above the plateau.**
`VmHWM` is a kernel high-water mark, so any instantaneous peak before the last sample is
captured. Over 2964 jobs, PDHD has **0** where it exceeds the ladder plateau by >10 MB and
PDVD has 8, all of them 0.01–0.06 GB (i.e. rounding). The STM stage's peak *is* its
plateau; the growth is monotone accumulation (~0.1 GB/s), not a burst on top of it.

## 2. Where the peak is

Existing logs, all tags (cross-tag, so this characterises the instrument and sets the
question — no delta is published from it):

| | peak p50 | p90 | p99 | max | n |
|---|---|---|---|---|---|
| PDVD | 1.36 GB | 2.32 | 3.21 | 3.93 | 1832 |
| **PDHD** | **2.82 GB** | **5.54** | **8.27** | **8.52** | 1132 |

PDHD is the detector the owner is seeing. The `MEM:` ladder names one stage, and every
stage after it returns nothing:

```
PDHD 028084/2  -stm -stm-fit  (99 clusters, 36 persisted fit passes, 74 s; arm d30a1)
  loaded live                    res 0.81   +0.60 GB
  CreateSteinerGraph             res 1.19   +0.38
  TaggerCheckTGM                 res 1.29   +0.10
  TaggerCheckSTM                 res 7.35   +6.06   <-- and FC / protect / refresh /
  PdvdMagnifyTrackingVisitor     res 7.50   +0.16       pr_display / bee: +0.00 each
  done                           res 7.50   -0.00
```

CPU splits differently between the detectors, which is worth stating on its own:

| arm, PRE pin | CreateSteinerGraph | TaggerCheckSTM | CheckSTM_Michel | arm node core-s |
|---|---|---|---|---|
| PDHD 61 ev `-stm` | 632 s | **1132 s (54 %)** | — | 2083 s |
| PDHD 61 ev `-nu` | 660 | **1176 (38 %)** | **868 (28 %)** | 3074 |
| PDVD 120 ev `-stm` | **1080 s (53 %)** | 539 | — | 2028 |
| PDVD 120 ev `-nu` | **1115 (41 %)** | 564 | 546 (20 %) | 2703 |

The two detectors' CPU is dominated by *different* stages: PDHD by `TaggerCheckSTM`, PDVD by
`CreateSteinerGraph`. Memory is dominated by the same stage on both.

## 3. The carrier: one TLA settles it

`save_stm_fit` (a top-level arg of both drivers, `true` on PDHD and PDVD, `false` on SBND)
gates the persisted STM fits. Three arms, one pinned PRE binary, sequential, both
pathological events:

| arm | what | 029107/18 | 028084/2 |
|---|---|---|---|
| `d30a1` | production, `-stm-fit` | 6.14 GB / 71 s | 7.51 GB / 74 s |
| `d30a2` | same, no ROOT writer | 5.99 / 70 | 7.35 / 71 |
| `d30a3` | `-S save_stm_fit=false` | **1.92 / 62** | **1.76 / 62** |

TaggerCheckSTM stage delta 4.63 / 6.06 GB → **0.36 / 0.44 GB**. So `save_stm_fit` carries
~92 % of the stage and ~75 % of the job's peak; the `-stm-fit` ROOT writer is only 0.15 GB.
`d30a3` is a **diagnostic, never a proposal** — it drops the Bee `stm_fit` layer and
`tracking-stm.root`, which are products.

## 4. Live, not allocator: the heap profile

RSS cannot distinguish a retained live structure from allocator-retained free memory, and
the two have different fixes. jemalloc sampling on 029107/18 (`lg_prof_sample:19`,
dump `i29`):

**`jeprof` is not on `PATH` and is in none of the usual prefixes** (`/usr/bin`,
`/usr/local/bin`, `local/bin`), and **`google-pprof` rejects the `heap_v2` header
outright** — and reading the dump without jeprof's sampling correction understates it by
four orders of magnitude. `pdhd/stm/perf/je2pprof.py` (committed with this doc) converts
the dump and applies jeprof's own `1/(1-exp(-s/R))` per-record correction.

**Cross-checked against the reference.** A working `jeprof` does exist on the machine,
inside a CVMFS container image, and being a perl script it runs from the host:

```bash
/cvmfs/icarus.opensciencegrid.org/containers/tritonserver/nugraph-v0/usr/bin/jeprof     --text --cum --inuse_space $(which wire-cell) $H/je.<pid>.29.i29.heap
```

It reports **Total: 5791.5 MB** — identical to the converter's, and every frame value below
matches it to the decimal (2059.7, 1965.2, 5641.5, 5782.6). It prints raw addresses rather
than symbols, which is why the converter + `google-pprof` route is still the one to use, but
the number this section rests on is validated against the reference implementation, not
merely self-consistent.

Scaled live heap **5.79 GB** against that run's 4.81 GB resident plateau — the correction
overestimates by ~17 % at this sample rate, but the conclusion does not depend on the
17 %: essentially all of the resident increment is **live objects**. An allocator lever
(`TCMALLOC_RELEASE_RATE`, `ReleaseFreeMemory`) has nothing to release, and was not taken.

| frame | MB | % of live |
|---|---|---|
| `TaggerCheckSTM::visit` | 4519 | 78.0 |
| `std::_Rb_tree::_M_copy` — whole-map **copy construction** | 4117 | 71.1 |
| `TaggerCheckSTM::persist_stm_fit` | 2060 | 35.6 |
| `TrackFitting::add_fitted_charge_2d_snapshot` | 1965 | 33.9 |
| `FittedCharge2D::FittedCharge2D` → its `std::set` | 1190 | 20.5 |

Two leaf sites, ~2 GB each, and 71 % of the live heap is *map copy construction*.

## 5. Root cause

One STM pass's cell map is
`std::map<APAFacePlane, std::map<WireTime, FittedCharge2D>>`, and `FittedCharge2D` itself
holds a `std::set`. At the hand-off, each pass's map was live in **three** places:

| # | container | lifetime | was |
|---|---|---|---|
| 1 | `m_pass_records[i].cells` | one cluster (cleared at the top of the next) | copy of the fitter's map |
| 2 | `m_acc_pass_snapshots[k].cells` | whole event | **copy of (1)** — `TaggerCheckSTM.cxx:969` |
| 3 | the parked `"stm"` `TrackFitting`'s `m_cluster_fitted_charge_2d[k].cells` | whole event | **copy of (2)** — `TaggerCheckSTM.cxx:631` |

(Line numbers are pre-fix, i.e. at `0c9ef501`; after `c61de88a` they are `:982` and `:637`.)

(2) and (3) are live simultaneously at the hand-off — that instant is the job's peak, and
it is where the two ~2 GB leaf sites of §4 sit. Both copies are avoidable, because both
sources are provably dead on the next line:

- `m_pass_records` is cleared at the top of the next cluster, and the second loop over it
  (the `stm_pass` arrays) reads `pass`/`status`/`kink`/`segment`, never `cells`.
- `m_acc_pass_snapshots.clear()` runs three lines after the hand-off loop, and nothing
  reads `snap.cells` in between.

`m_acc_pass_snapshots` entered on **2026-09-05** with `86c0d4fd` (doc pdvd/42, per-pass
snapshots for `T_proj_data`); the merged `m_acc_fitted_charge` on 2026-07-24 with
`3db191e93` (doc 41, `save_stm_fit`). Neither was wrong — the product is needed. Only the
copies were.

## 6. What shipped

Two `std::move`s and an rvalue overload to receive them:

| file | change |
|---|---|
| `clus/inc/WireCellClus/TrackFitting.h` | an **rvalue overload** of `add_fitted_charge_2d_snapshot` (additive: the `const&` overload and every existing caller are untouched) |
| `clus/src/TrackFitting.cxx` | its body — `push_back({cluster, ident, std::move(cells), pass})` |
| `clus/src/TaggerCheckSTM.cxx` | `persist_stm_fit`: `std::move(rec.cells)` into `m_acc_pass_snapshots` (and the loop binds non-const) |
| `clus/src/TaggerCheckSTM.cxx` | the hand-off loop: `std::move(snap.cells)` into the holder |

The same event's ladder after the fix (arm `d30b1`, identical output):

```
PDHD 028084/2  -stm -stm-fit  (arm d30b1, POST pin)
  loaded live                    res 0.81   +0.60 GB
  CreateSteinerGraph             res 1.20   +0.38
  TaggerCheckTGM                 res 1.30   +0.10
  TaggerCheckSTM                 res 4.64   +3.34      (was +6.06)
  PdvdMagnifyTrackingVisitor     res 4.84   +0.20
  done                           res 5.00   +0.16
```

The STM stage's own increment halves — from three live copies of each pass's map to one —
which is exactly what removing two of three predicts. What remains in that stage is the one
copy the product needs, plus the merged `m_acc_fitted_charge` map (§9).

**This is not behind a knob, and that is deliberate.** A `std::move` whose source is
provably dead has no meaningful "off" state — the knob would be "keep the redundant copy".
This is the same class as doc 28 §6's S1/S2/T1/D1/T2, which shipped as byte-identical
levers with no knob and a hash gate as the proof. The gate is §7.

## 7. Gates

Member-content hashes, never `md5`/`cmp` on an archive (M2). Four products per event:
`mabc-pr.zip` (per member), `calib-pr-evt*.json` (with the `*_ms` timer keys stripped),
and `tracking-stm.root` / `tracking-pr.root` **by TREE content**.

**The tree list is explicit, and that matters.** The default list in
`qlport/scripts/hash_root_trees.py` covers `T_rec_charge`, `T_kine`, `T_tagger` — it does
**not** include `T_proj_data`, which is exactly the tree this change writes. Run with the
default list the gate is green while being blind to the thing it gates. `d30_hash_gate.py`
passes `--trees T_rec_charge,T_proj_data,T_stm_pass,T_stm_eval,T_stm_michel,T_stm_michel_pts,T_tagger,T_kine`.

| gate | arms | result | record |
|---|---|---|---|
| PDHD `-stm`, 61 events (028084×31 + 029107×30) | `d30hpre` (PRE pin) / `d30hpost` (POST pin) | **PASS 61 / FAIL 0**, 4 products each | `docs/perf/doc30_gate_pdhd_stm_61.txt` |
| PDVD `-stm`, 120 events (`d48nu7` pctrees) | `d30vpre` / `d30vpost` | **PASS 120 / FAIL 0** | `docs/perf/doc30_gate_pdvd_stm_120.txt` |
| PDHD `-nu` (CheckSTM_Michel), 61 events | `d30hnupre` / `d30hnupost` | **PASS 61 / FAIL 0** | `docs/perf/doc30_gate_pdhd_nu_61.txt` |
| PDVD `-nu`, 120 events | `d30vnupre` / `d30vnupost` | **PASS 120 / FAIL 0** | `docs/perf/doc30_gate_pdvd_nu_120.txt` |

**362 events x 4 products = 1448 comparisons, every one identical.**

Pin fingerprints printed before **and** after every arm and unchanged across all of them
(`libWireCellClus.so,libWireCellRoot.so`): PRE `b3495810c15b,4a9efb7f52d2`,
POST `a315be6b7b24,23f5e6d0e686`. No rebuild happened between arms.
Freshness proof (M1) before each pin: no `clus/` source newer than the `.so`.
`./build/clus/wcdoctest-clus`: **328/328 test cases, 23108/23108 assertions, 1 skipped**,
including the three doc-pdvd/42 snapshot tests that exercise the changed API.

### SBND and uBooNE

`TaggerCheckSTM` is bound by PDHD, PDVD and **SBND** (`cfg/pgrapher/experiment/sbnd/`);
uBooNE does not bind it at all. SBND is nonetheless **unaffected**, by two independent
proofs rather than by an arm:

1. Both edited lines sit inside `if (m_save_stm_fit)` — the `persist_stm_fit` call
   (`TaggerCheckSTM.cxx:614`) and the hand-off block (`:620`).
2. Compiled-config proof: SBND's `TaggerCheckSTM` node **omits** `save_stm_fit`
   (key-suppression; C++ default `false`), while PDHD's carries `save_stm_fit = true`.

The `TrackFitting.h` change is purely additive — a new rvalue overload; the `const&`
overload and every existing caller are untouched, and the only non-test caller is the one
line changed here.

**Trigger for a future reader:** the SBND argument rests entirely on `save_stm_fit = false`.
**If SBND ever flips it true, this change becomes ungated on SBND** and needs the §7 gate
run there before that flip ships.

**Stated limitation:** no SBND PR arm was run. SBND's staged PR inputs were retired in the
2026-09-05/06 cleanup rounds (0 `pctree-evt*.tar.gz` under `sbnd_xin/work`), so an SBND
gate would mean regenerating imaging + clustering first. Given the two proofs above that
was judged out of scope for this round; it is the one gap in the coverage.

## 8. Result

61-event PDHD arm and 120-event PDVD arm, PRE vs POST pin, same inputs, same operating
point. `peak` is `max(sampled VmHWM, ladder max)` per §1. These arms ran at `JOBS<=6`, so
**memory is quotable and wall is not**; `node_core_s` is contention-free by construction
(it is the MABC node's own core-seconds) and is quoted to show the fix costs no CPU.

### PDHD `-stm` (61 events)

| | p50 | p90 | max | sum |
|---|---|---|---|---|
| peak RSS, pre | 2.69 GB | 4.75 | **7.51** | 186.2 |
| peak RSS, post | **2.17** | **3.50** | **5.00** | **141.9** |
| TaggerCheckSTM stage, pre | 1.69 | 3.37 | 6.06 | 125.9 |
| TaggerCheckSTM stage, post | 1.00 | 1.90 | 3.34 | 72.1 |
| node core-s, pre | 30.84 | 57.58 | 94.48 | 2083.3 |
| node core-s, post | 31.19 | 54.25 | 97.51 | **2072.8** |

Per-event peak reduction: median **22 %**, best 33.7 %, worst 2.6 %.
Events above 6 GB: **4 → 0**. Above 4 GB: 10 → 4. CPU: −0.5 % on the arm (noise).

### PDVD `-stm` (120 events)

| | p50 | p90 | max | sum |
|---|---|---|---|---|
| peak RSS, pre | 1.22 GB | 2.02 | 3.08 | 158.6 |
| peak RSS, post | 1.15 | 1.97 | **2.75** | 153.8 |
| TaggerCheckSTM stage, pre | 0.34 | 0.72 | 1.41 | 47.3 |
| TaggerCheckSTM stage, post | 0.22 | 0.44 | 0.82 | **29.7** |
| node core-s, pre/post | 13.76 / 13.07 | 34.36 / 34.95 | 73.98 / 73.91 | 2028.2 / 2012.8 |

PDVD's **stage** drops by the same 37 %, but its **peak** barely moves (median 0.6 %):
on most PDVD events the peak is not set by the STM stage at all — it is set by
`CreateSteinerGraph` or by the writers. That is the honest cross-detector statement:
one mechanism, but it only dominates on PDHD.

### The STM_Michel chain (`-nu`), same arms with `MODE=-nu`

`-nu` appends `CheckSTM_Michel` + `tracking_visitor` after the same cosmic taggers, so the
memory fix applies unchanged and the extra stage is pure CPU:

| | PDHD `-nu` (61) | PDVD `-nu` (120) |
|---|---|---|
| peak RSS p50, pre → post | 2.69 → **2.48** GB | 1.43 → 1.42 GB |
| peak RSS max, pre → post | 7.51 → **5.54** | 3.44 → 3.44 |
| events > 6 GB, pre → post | 4 → **0** | 0 → 0 |
| TaggerCheckSTM stage sum, pre → post | 125.9 → **72.1** GB | 47.3 → **29.7** GB |
| arm node core-s, pre → post | 3074.5 → 3019.6 | 2703.4 → 2676.7 |
| `CheckSTM_Michel` stage: p50 / p90 / max / arm sum | 6.6 / 29.3 / 174.3 s / **868 s** | 3.5 / 10.1 / 25.6 s / **546 s** |

So `CheckSTM_Michel` is **28 % of the PDHD `-nu` arm's CPU and 20 % of PDVD's**, and costs
essentially no memory — it reuses the fits `TaggerCheckSTM` already parked in the `"stm"`
slot. Going `-stm` → `-nu` costs +48 % core-s on PDHD (2083 → 3075) and +33 % on PDVD
(2028 → 2703).

**On PDVD `-nu` the peak does not move at all** (median 0.0 %), even though the STM stage
drops the same 37 %. In that mode PDVD's peak is set by `CheckSTM_Michel` and the writers,
not by the STM stage. Stating it plainly: this fix is a PDHD win and a PDVD stage-level win
that does not reach PDVD's peak.

### Why PDHD and not PDVD — the scaling law

The original puzzle was that PDHD 029107/9 has **more** clusters than 028084/2 and uses
12× less memory in the same stage. Cluster count is not the variable. Log-log fits of the
STM-stage resident against each candidate, on the 61-event `d09prod` arm (one binary):

| variable | exponent | R² |
|---|---|---|
| cluster count | 1.39 | **0.062** |
| STM-tagged cluster count | 0.29 | 0.099 |
| longest fitted track's points | 1.20 | 0.139 |
| loaded-tree size (`load_gb`) | 1.27 | 0.638 |
| persisted fit passes (`nfit`) | 1.68 | 0.732 |
| total fitted points (`sum_npts`) | 1.60 | 0.807 |
| `nfit × load_gb` | 0.86 | 0.807 |
| **`sum_npts × load_gb`** | **0.85** | **0.854** |

So the cost is (how many trajectory points were fitted) × (how big the event is) —
0.72 MB per fitted point per GB of loaded tree, spread 1.7×. The event-size factor is the
mechanism named in §9: `fill_fitted_charge_2d` walks the **whole** plane map, not the cells
the track touches, so each fit's map scales with the event rather than with the track.

Applied to the two events that started this:

| | clusters | fit passes | fitted points | load | STM stage |
|---|---|---|---|---|---|
| 028084/2 | 99 | 36 | 14931 | 0.60 GB | **6.06 GB** |
| 029107/9 | **106** | 15 | 4987 | 0.19 GB | **0.70 GB** |

Predicted ratio from the law 9.5×, measured 8.7×. The cluster-count ratio is 0.93.
PDHD costs more than PDVD because it fits more passes on bigger events, not because its
clusters are worse.


## 9. Ranked levers still on the table (measured, NOT taken)

| lever | site | expected | risk to output | gate it would need |
|---|---|---|---|---|
| `fill_fitted_charge_2d` stores a cell for **every** entry of the fit's charge map, dead ones included | `TrackFitting.cxx:1313-1345` — `process_plane` writes an entry even when `charge <= 0 \|\| flag == 0` (it just sets `pred_charge = 0`) | the structural win: it is why per-fit cost tracks the event's charge extent, not the track's length (the §8 law, R² 0.854 against `sum_npts × load_gb`, is the measurement of that) | **high**: changes which cells exist in every downstream product | default-OFF knob + full A/B on every binder |
| drop the per-cell `std::set<Cluster*>` for consumers that never read it | `TrackFitting.h:614`, filled `TrackFitting.cxx:1345` | the set is 20.5 % of live heap (§4) | changes `T_proj_data` / `PrDisplayDump::dump_proj` | default-OFF knob |
| **move the merged map too** — the third and last copy | `TaggerCheckSTM.cxx:628` → `merge_fitted_charge_2d` | not sized; it is the de-duplicated union of every pass's cells, so smaller than the snapshots but not small | **none — verified free.** The merge is a per-cell insert into `m_fitted_charge_2d`, a *different* member from the snapshots; the `saved` holder is freshly constructed at `:621` and `add_segment` never touches that member, so the target is empty and a whole-map move is exactly equivalent | byte-identical, same gate as §7 |
| `release_post_nu` in the production pipeline | declared at `pdhd/pr.jsonnet:1654`, in no pipeline | small. **Checked:** `release_fit_scratch()` clears 18 members and `m_cluster_fitted_charge_2d` / `m_fitted_charge_2d` are not among them, so with `slots:['stm']` it cannot reach the carrier at all; it would only take the per-cluster graphs and `GraphAlgorithms` caches | placement before `protect_bundle` would change output; after `pr_display` is safe | byte-identical at that position |
| `GraphAlgorithms` shortest-path LRU (50 entries × \|V\| per graph per cluster) | `Graphs.h:135` | inside the 0.36–0.44 GB residual of `d30a3` | recompute cost | byte-identical + no core-s regression |
| the harness `peak_rss_gb` bug (§1) | `run_pr_evt.sh`, both detectors | none — it is an instrument fix | none | n/a |

## 10. Files

**Toolkit** (`apply-pointcloud`, commit `c61de88a`):

| file | what |
|---|---|
| `clus/inc/WireCellClus/TrackFitting.h` | rvalue overload of `add_fitted_charge_2d_snapshot` (additive) |
| `clus/src/TrackFitting.cxx` | its body |
| `clus/src/TaggerCheckSTM.cxx` | the two `std::move`s + the non-const loop binding |

**wcp-porting-img** (`main`), all new:

| file | what |
|---|---|
| `pdvd/docs/30_pdhd-pdvd-pr-perf-memory.md` | this doc |
| `pdhd/stm/perf/d30_pr_census.py` | per-event CPU+memory census, either detector; publishes the corrected peak and asserts stage coverage |
| `pdhd/stm/perf/d30_hash_gate.py` | the byte-identity gate (zip members + calib + ROOT **tree** content, explicit tree list) |
| `pdhd/stm/perf/je2pprof.py` | jemalloc `heap_v2` → pprof, with jeprof's sampling correction (jeprof is not on PATH; output cross-checked against the CVMFS copy, §4) |
| `pdhd/stm/perf/d30_law.py` | the log-log scaling fits of §8 |
| `pdhd/stm/perf/d30_c1_scan.sh` | reported vs ladder peak, every job (§1) |
| `pdhd/stm/perf/d30_stage.sh`, `d30_run_a.sh`, `d30_run_pdvd_arm.sh` | staging + the §3 bracket + the PDVD arm driver |
| `pdhd/docs/scripts/d30_run_pr_arm.sh` | PDHD arm driver, forked by duplication from `d09_run_pr_arm.sh` (untouched) |
| `pdvd/docs/perf/doc30_*.{txt,tsv}` | gate records and the per-event TSVs behind every table here |

`pdvd/stm/perf/pr_perf_profile.py` was **not** forked: it answers doc 28's question (stage
shares of node core-s on a PDVD arm) and carries a PDVD-only stage list. `d30_pr_census.py`
is a new tool for doc 30's question. The PDVD script is untouched.

## 11. Recommended next step

**Take the third copy** — the §9 row above, now verified free rather than merely plausible.
It is the same `std::move` pattern shipped here, one more rvalue overload, and it reuses
this round's gate unchanged (`d30_hash_gate.py` on four fresh arms, ~1.5 h unattended). It
was not taken in this round only to keep one gated change per commit.

After that, the ranked list's top row is the structural one: restricting
`fill_fitted_charge_2d` to the cells a fit actually predicts. That one is knob-required and
is a round of its own — it changes which cells exist in every downstream product.

## Milestone log

- 2026-09-07 — instrument bias found and quantified (§1); the `save_stm_fit` bracket
  located the carrier (§3); jemalloc live-heap named the two copy sites (§4); root cause
  §5; two `std::move`s shipped as toolkit `c61de88a`; gates §7; scaling law §8;
  five levers measured and not taken §9.
