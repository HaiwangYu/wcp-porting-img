# 30 — PDHD and PDVD PR jobs: where the running time and the 7 GB go

**Status (2026-09-07).** The owner asked why the cosmic-tagger / STM-Michel jobs peak near
7 GB. Measured both detectors and both chains, attributed the peak to one stage and one
line, and shipped the fix. PDHD's worst event went **7.51 → 5.00 GB** and no event on the
61-event arm is above 6 GB any more (4 were); the arm's node core-s is unchanged
(2083.3 → 2072.8). Gates in §7: **362 events x 4 products, all identical** — PDHD 61/61 and
PDVD 120/120 in both `-stm` and `-nu`, including the ROOT tree the change writes.

**Round 2 (2026-09-07, §12).** Asked whether there is more. Profiled the CPU for the first
time, tried the three byte-identical levers the profile suggested, and **measured all three
at noise (−0.2 % core-s, 0.00 GB)** — none shipped, with the census that says why (PDHD's
wrapped wires falsify both preconditions). The one large room left is a 40–45× over-storage
in `fill_fitted_charge_2d`, sized in §12.4 and referred to the owner because taking it would
change `T_proj_data`. Only a log-only sizing census shipped (gated PASS 6/6).

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

**Round 3 adds** (toolkit `TrackFitting.{h,cxx}` — the `proj_pad_wire`/`proj_pad_time` knob
and its filter; `clus/test/doctest_doc30_proj_pad.cxx`; a case in
`doctest_clus_knob_defaults.cxx`) and, in wcp-porting-img:

| file | what |
|---|---|
| `pdhd/stm/perf/d30_hash_proj.py` | **new** — a `T_proj_data` content hash that is not vacuous (§13.2) |
| `pdhd/stm/perf/d30_tree_diff.py` | **new** — per-tree diff: *which* product changed, for the knob-ON arm (§13.7) |
| `pdhd/stm/perf/d30_hash_gate.py` | **edited** — carries `T_proj_data` as a fifth product; earlier runs reported four |
| `pdhd/stm/perf/d30r3_{scan,busy6,scan_pdvd,retro_proj}.sh` | the round-3 arm drivers |
| `pdvd/docs/perf/doc30r3_*.{txt,tsv}` | the pad scan, both A/B TSVs, both gates, the 362-event retro-check |

## 11. Recommended next step

**Take the third copy** — the §9 row above, now verified free rather than merely plausible.
It is the same `std::move` pattern shipped here, one more rvalue overload, and it reuses
this round's gate unchanged (`d30_hash_gate.py` on four fresh arms, ~1.5 h unattended). It
was not taken in this round only to keep one gated change per commit.

After that, the ranked list's top row is the structural one: restricting
`fill_fitted_charge_2d` to the cells a fit actually predicts. That one is knob-required and
is a round of its own — it changes which cells exist in every downstream product.

## 12. Round 2 (2026-09-07): is there more? The CPU profile, and three levers that measure as noise

**Answer up front: no further byte-identical headroom was found.** Round 1 took PDHD's worst
event 7.51 -> 5.00 GB. Round 2 profiled the CPU for the first time, tried the three
byte-identical levers the profile suggested, and **measured all three at noise (-0.2 % core-s,
0.00 GB)**. None shipped. The one large room that remains is real and is sized in §12.4 --
but it changes `T_proj_data`, so it is an owner question, not a lever.

### 12.0 Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
# pins: r1-post a315be6b7b24 ; census build 22f909f771c0 (this round's only code)
# CPU profile (precompiled cfg -- SIGPROF corrupts gojsonnet, M17; tcmalloc, never setarch -R)
pdhd/stm/perf/d30_stage.sh 029107 18 d09ctl2 d30r2p
LD_LIBRARY_PATH=/home/xqian/tmp/d30_libpin_post TAG=d30r2p pdhd/profile_pr.sh 029107 18 out.prof
google-pprof --text --cum $(which wire-cell) out.prof | head -45   # docs/perf/doc30r2_prof_029107_18.txt

# the sizing census (log-only, env-gated, byte-neutral when unset)
WCT_D30_FILL_CENSUS=1 PDHD_MAX_JOBS=1 pdhd/run_pr_evt.sh -s <tag> -stm-fit 29107 18
grep -o 'd30_fill_census: .*' pdhd/work/029107_18_<tag>/wct_pr_*.log | tail -1

# sequential A/B of two pins on the busy set of 6 (JOBS=1: a 3 % claim is inside
# batch-contention noise at JOBS=6)
/home/xqian/tmp/d30r2/ab_seq.sh d30r2a=<pinA> d30r2b=<pinB>
python3 pdhd/stm/perf/d30_pr_census.py --tsv docs/perf/doc30r2_ab_busy6.tsv pdhd/work d30r2a d30r2b
```

### 12.1 The CPU profile (PDHD 029107/18, `-stm -stm-fit`, 16744 samples)

The first CPU profile of the PR job in this campaign. Full text:
`docs/perf/doc30r2_prof_029107_18.txt`.

| region | % of job |
|---|---|
| `TaggerCheckSTM::visit` | **58.2** |
| &nbsp;&nbsp;`TrackFitting::do_single_tracking` | 48.5 |
| &nbsp;&nbsp;&nbsp;&nbsp;`dQ_dx_fit` | 42.8 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**`fill_fitted_charge_2d`** | **19.9** |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`build_dqdx_rows` | 4.5 |
| &nbsp;&nbsp;`search_other_tracks` | 14.2 |
| `CreateSteinerGraph::visit` | **26.4** |
| &nbsp;&nbsp;`ImproveCluster_2::mutate` | 18.7 (spread over graph build + sampling; no local win) |
| &nbsp;&nbsp;`make_graph_ctpc_pid` | 8.8 |
| `record_cluster_fitted_charge_2d` | **0.0** — `m_cluster_filter` is unset in the STM path, so the copy there never runs. One candidate killed for free. |

Flat profile: **~40 % of the whole job is container machinery, not physics** — red-black-tree
ops 14.3 %, `std::operator<` 6.1 % + `__memcmp_evex_movbe` 2.9 % (the tuple/pair keys),
hashtable 10.3 %, tcmalloc 9.6 %. That is what made the three levers below look attractive.

### 12.2 Three byte-identical levers, all measured at noise — NOT shipped

Sequential (`JOBS=1`) A/B on the PDHD busy set of 6, r1-post pin vs a pin carrying levers
(a) and (b). TSV: `docs/perf/doc30r2_ab_busy6.tsv`.

| event | r1 core-s | with levers | delta |
|---|---|---|---|
| 028084/18 | 78.7 | 79.5 | +1.0 % |
| 028084/2 | 65.7 | 65.3 | −0.6 |
| 029107/12 | 46.2 | 46.3 | +0.2 |
| 029107/15 | 44.5 | 44.1 | −1.1 |
| 029107/18 | 64.9 | 64.2 | −1.0 |
| 029107/9 | 13.2 | 13.3 | +0.5 |
| **sum** | **313.2** | **312.6** | **−0.2 %** |

Peak RSS unchanged on all six. **Why they don't pay — the census says both preconditions
are false on PDHD, and the reason is the same in each case: wrapped wires.**

| lever | precondition it needs | measured |
|---|---|---|
| (a) cache the outer-map (`APAFacePlane`) pointer instead of walking the tuple-keyed tree per cell | `afp` repeats consecutively | **hit rate 40 %** (029107/18 0.4047, 028084/2 0.3937). Rows arrive in `CoordReadout` (apa, time, channel) order and one channel maps to wires on both faces, so `face` alternates. The added compare on every cell roughly cancels the walks saved on 40 %. |
| (b) `std::move` the cluster set on a row's last `Coord2D` instead of copying it | rows are mostly single-`Coord2D` | **only 30–33 %** are (0.3252 / 0.2995) — wrapped wires again. |
| (c) `std::move` `m_acc_fitted_charge` into the holder — the "third copy", verified free in §9 | the merged map is a meaningful share of the peak | peak **4.29 → 4.31** and **5.00 → 5.00 GB**. It is small next to the snapshots, and the peak has already passed by the hand-off. §9's row was right that it is free; it was wrong that it was worth anything. |

All three were reverted. A byte-identical change that buys noise still costs a review and a
gate.

### 12.3 What did ship: the sizing census only

`WCT_D30_FILL_CENSUS` (log-only, off unless set), matching the existing `WCT_*_CENSUS`
idiom. Three counters and one DEBUG line; when the env is unset the cost is one
`static const bool` read.

**Gate:** PDHD busy set of 6, census binary with the env **unset** vs the r1 binary —
**PASS 6/6**, 4 products each (`docs/perf/doc30r2_gate_census_busy6.txt`), and zero
`d30_fill_census` lines in the gate arm's logs. Four full arms were not re-run for a log
line. Note this round's file is `TrackFitting.cxx`, which **SBND and uBooNE do reach** —
r1 §7's "SBND is exempt" argument does *not* carry over, and does not need to: the code is
inert when the env is unset.
`./build/clus/wcdoctest-clus` 328/328, 23108/23108. Freshness proof done; pin `22f909f771c0`.

### 12.4 The one large room, sized — and why it was not taken

`fill_fitted_charge_2d` stores an entry for **every** cell of the fit's charge map, whether
or not the fit predicts anything there (`pred_charge` just stays 0). The census, per event
(counters are process-cumulative over all `fill_fitted_charge_2d` calls, not per fit):

| event | calls | cells summed | **per call** | cells with a prediction | share | ratio |
|---|---|---|---|---|---|---|
| 029107/18 | 103 | 37.27 M | **362 k** | 902 722 | **2.42 %** | 41× |
| 028084/2 | 103 | 45.91 M | **446 k** | 1 029 846 | **2.24 %** | 45× |

(103 calls, not 34/36: the persisted passes each run a round-1 and a round-2 fit. The
`stored_this_fit=20` in the log line is the number of `APAFacePlane` groups in the outer
map, not a cell count.)

So each fit builds a ~400 k-cell structure of which **~2 %** carries a prediction, and does
it 103 times. That is the 19.9 % of CPU and the bulk of the remaining memory carrier — a
40–45× ratio, by far the largest room left.

**It was not taken, and this is a question for the owner rather than a lever.** Those ~98 %
of cells are the *measured*-charge context: doc pdvd/42 validated the STM fit by comparing
measured against predicted 2-D charge, and seeing charge the fit does **not** explain is the
point of that display. Restricting the fill to predicted cells would change `T_proj_data`
and `PrDisplayDump::dump_proj` — a knob could keep the default byte-identical, but whether
the ON path is *useful* is a physics call, not a performance one.

**Owner question:** is the off-fit (unpredicted) charge load-bearing for your 2-D scan, or
is it context you could accept losing on the STM fit dump in exchange for ~20 % of the PR
job's CPU and most of what remains of its memory?

A narrower version of the same question, and the better next round either way: cells with
`pred_charge == 0` still each carry a `std::set<Facade::Cluster*>` — 20.5 % of live heap in
§4's profile. If `dump_proj` does not read `clusters` on unpredicted cells, dropping it
there may be **byte-identical** to the products, and is a much smaller change than
restricting the fill.


## 13. Round 3 (2026-09-07): the owner's question answered, and the large room taken

Round 2 closed with a question for the owner: is the off-fit (unpredicted) charge in the
2-D display load-bearing? The owner's answer set this round's task:

> "for this fill_fitted_charge_2d, I think we only need the actual fitted charge and their
> nearby one, no need to include everything ... This one is only for debugging, and does not
> really have an impact on the results, right?"

Both halves are confirmed below — the second from primary source and then empirically —
and the lever is shipped behind a default-OFF knob. **On the PDHD busy set of 6 the knob at
pad 3 takes 329.4 -> 234.6 core-s (-28.8 %) and the peak RSS of the worst event 5.00 -> 2.19
GB (-56 %), with every physics product byte-identical.** Round 2's three levers measured at
-0.2 %; this one is 140x that, because it removes work rather than reorganising it.

### 13.0 Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
# pin: r3 binary f1ba2956d921 (/home/xqian/tmp/d30_libpin_r3); freshness proof done
# arm files: a byte-identical copy of the detector's *_track_fitting.json plus the 2 keys
sed 's|^\( *\)"div_sigma": \(.*\)$|\1"proj_pad_wire": 3,\n\1"proj_pad_time": 3,\n\1"div_sigma": \2|' \
    ../toolkit/cfg/pgrapher/experiment/pdhd/pdhd_track_fitting.json > /home/xqian/tmp/d30r3/pdhd_tf_pad3.json

# OFF arm (knob absent = production) and ON arm, sequential, JOBS=1
LD_LIBRARY_PATH=/home/xqian/tmp/d30_libpin_r3 PDHD_MAX_JOBS=1 WCT_D30_FILL_CENSUS=1 \
    pdhd/run_pr_evt.sh -s d30r3off -stm-fit 29107 18
LD_LIBRARY_PATH=/home/xqian/tmp/d30_libpin_r3 PDHD_MAX_JOBS=1 WCT_D30_FILL_CENSUS=1 \
    PDHD_PR_TLA="-A trackfitting_config=/home/xqian/tmp/d30r3/pdhd_tf_pad3.json" \
    pdhd/run_pr_evt.sh -s d30r3p3 -stm-fit 29107 18

python3 pdhd/stm/perf/d30_pr_census.py --tsv pdvd/docs/perf/doc30r3_busy6.tsv pdhd/work d30r3off d30r3p3
python3 pdhd/stm/perf/d30_hash_gate.py  pdhd/work d30r2a    d30r3off   # gate A, 5 products
python3 pdhd/stm/perf/d30_tree_diff.py  pdhd/work d30r3off  d30r3p3    # gate B, per tree
python3 pdhd/stm/perf/d30_hash_proj.py  pdhd/work/029107_18_d30r3{off,p3}/tracking-stm.root
```

Committed artifacts, all regenerable by the commands above:
`pdhd/stm/perf/d30r3_{scan,busy6,scan_pdvd,retro_proj}.sh` (the arm drivers),
`pdvd/docs/perf/doc30r3_{padscan.txt,busy6.tsv,pdvd7.tsv,gateA_busy6.txt,gateB_ON_vs_OFF.txt,retro_proj_362.txt}`.

### 13.1 "Only for debugging" — the consumer census

Every reader of the two accessors, repo-wide (`grep -rn 'get_fitted_charge_2d\|get_cluster_fitted_charge_2d'`,
no `head`, which is how the last one below was nearly missed):

| reader | what it writes |
|---|---|
| `root/src/{Pdvd,PdvdPr,Sbnd,SbndPr,Uboone}MagnifyTrackingVisitor.cxx` | the `T_proj_data` tree |
| `clus/src/PrDisplayDump.cxx:1182` (`dump_proj`) | the calib JSON's `proj` block |
| `clus/src/TaggerCheckSTM.cxx:917,922` | *writes* the accumulators; reads only its own |
| `clus/test/doctest_pr109_*.cxx`, `doctest_trackfitting_snapshot_pass.cxx` | tests |

Nothing in `clus/` reads either map to reach a decision, and nothing downstream of the
`fill_fitted_charge_2d` call inside `dQ_dx_fit` touches `m_fitted_charge_2d` — the reduced-chi2
loop that follows works off `RU/RV/RW` and `pred_data_*`. `PrDisplayDump.cxx:1173` says it
in the code's own words:

> "Blast radius is diagnostic-only: the merged map is read by this dumper, the Magnify
> writers' fallback path and TaggerCheckSTM's stm_fit record. **No tagger verdict, Bee layer
> or pctree tensor depends on it.**"

That is the grep-level answer. §13.6's Gate B is the empirical one, and it is stronger.

### 13.2 A gate blindness, found here and applying to rounds 1-2

`d30_hash_gate.py`'s docstring made a point of passing `--trees ...,T_proj_data` because
`hash_root_trees.py`'s default list omits it. **Naming the tree was necessary and not
sufficient.** `hash_root_trees.py`'s row-sorted hash drops every branch of dtype `object`,
and when that leaves no columns it returns `sha256("")`. Every branch of `T_proj_data` is
jagged (one entry holding N per-block vectors), so its per-tree digest was the constant
`e3b0c442...b7852b855` — sha256 of the empty string — in every file ever hashed. Rounds 1
and 2 ran a gate that named the display tree and could not read it.

Fixed with `pdhd/stm/perf/d30_hash_proj.py`: the sorted multiset of
`(cluster_id, channel, time_slice, charge, charge_err, charge_pred)` cell tuples, which is
order-insensitive and value-sensitive. `d30_hash_gate.py` now carries it as a **fifth
product**.

**The round-1 arms were then re-checked with it, after the fact:**

| pair | mode | events | `T_proj_data` identical |
|---|---|---|---|
| `d30hpre` vs `d30hpost` | PDHD `-stm` | 61 | **61** |
| `d30hnupre` vs `d30hnupost` | PDHD `-nu` | 61 | **61** |
| `d30vpre` vs `d30vpost` | PDVD `-stm` | 120 | **120** |
| `d30vnupre` vs `d30vnupost` | PDVD `-nu` | 120 | **120** |

**362 of 362.** The blindness hid no defect — round 1's two `std::move`s really are
value-neutral on the display product too — but that was luck, not evidence, until now.
The general lesson is one step past `feedback_gate_tree_list_explicit`: an explicit tree
list does not help if the hasher cannot read that tree's branch type. Check that a gate can
see a *difference* before trusting it to report *no* difference; §13.6 uses the ON arm as
that negative control.

### 13.3 What shipped

`TrackFitting::Parameters::proj_pad_wire` (**C++ default -1 = OFF**) and `proj_pad_time`
(pad in *slices*), read by both `fill_fitted_charge_2d` flavours. When on, a cell is stored
only if it lies within `proj_pad_wire` wires **and** `proj_pad_time` slices of a seed cell,
in the same `(apa, face, plane)`.

Three design points worth keeping:

* **The seed is the RAW prediction** `pred_data(idx) != 0`, not `pred_charge != 0`.
  `pred_charge` is forced to 0 by the `charge > 0 && flag != 0` gate, so a dead or
  below-threshold channel crossed by the track would be dropped by the narrower test and
  the display would be holed exactly where the fit is most interesting. Measured, the two
  sets coincide on these events (`seed=902722 predicted=902722`) because the fit excludes
  dead rows from `R` — so this costs nothing and removes a trap.
* **OFF is byte-identical by construction, not by gate.** The filter is one predicate that
  short-circuits to `true` when the knob is off; the legacy loop keeps its exact row order
  and its last-writer-wins overwrite on cells two rows share. There is no separate OFF body.
* **The row-level skip.** With the filter on, a row none of whose cells survive is dropped
  *before* its `global_rb_map` probe — 10.3 % of the flat profile. This is why the CPU win
  (-28.8 %) exceeds `fill_fitted_charge_2d`'s own 19.9 % share.
* **The keep-set key is range-checked, not masked** (toolkit `59cf4c89`). The set is keyed
  by `(apa, face, plane, wire, time)` packed into 64 bits. A masked overflow would not fail
  — it would alias two cells onto one key and silently keep the wrong one, with a wrong 2-D
  display as the only symptom. Out of range now sets `overflow`, logs one WARN and makes the
  filter **fail open** (store everything), so the failure direction is "shows too much",
  never "shows the wrong cell". Verified to change nothing on PDHD: 2/2 events PASS against
  the pre-guard binary with the knob both off and on, zero WARN lines.

The time pad is in slices and converted per `(apa, face)` with
`Grouping::get_nticks_per_slice()`, the same map `PrDisplayDump` and the Magnify writers use;
stored times are slice-quantized (`floor(tick/n)*n`), so a pad in raw ticks would keep
nothing. Tests: `clus/test/doctest_doc30_proj_pad.cxx` (5 cases, incl. the raw-prediction
seed and the per-plane isolation) plus a knob-default case in `doctest_clus_knob_defaults.cxx`.

### 13.4 The pad is nearly free — measured, not assumed

The worry going in was that a pad would re-admit most of what pad 0 removes: if the seeds
formed a thin 1-D band, dilating by p would grow the kept set roughly like (3+2p)/3, i.e.
~2.3x at pad 3. **It does not**, because the seed set is a thick region, not a curve:

| `proj_pad_wire`/`_time` | kept cells, 029107/18 | 028084/2 | stored in `T_proj_data`, 029107/18 | ratio vs OFF |
|---|---|---|---|---|
| **OFF** | 37 271 207 (100 %) | 45 906 889 (100 %) | 917 331 | 1.0x |
| 0 | 902 722 (**2.42 %**) | 1 029 846 (**2.24 %**) | 157 212 | **5.8x** |
| 1 | 959 719 (2.57 %) | 1 080 276 (2.35 %) | 164 359 | 5.6x |
| 2 | 997 388 (2.68 %) | 1 116 457 (2.43 %) | 168 419 | 5.4x |
| 3 | 1 027 958 (2.76 %) | 1 148 629 (2.50 %) | 171 567 | 5.3x |
| 5 | 1 079 910 (2.90 %) | 1 207 978 (2.63 %) | 176 214 | 5.2x |

Going from **no** context band to a **five**-cell one costs 0.5 percentage points of the
map and 12 % of the stored cells. Peak RSS and wall are flat across the whole column
(2.17 / 2.18 / 2.18 / 2.18 / 2.05 GB on 029107/18). **So be generous: pad 3 is the
recommendation, and pad 5 would also be affordable.**

**A correction to §12.4 while we are here.** That section's "40-45x over-storage" is the
ratio of *cell writes*, which is the CPU-side quantity. The *stored* map is smaller than the
write count because `m_fitted_charge_2d` is keyed by `(afp, wire, time)` and many writes
collapse onto one key: OFF stores 917 331 cells from 37.3 M writes. The memory-side ratio is
therefore **~5x, not 40x**. Both numbers are real; they answer different questions, and §12.4
should have said which.

### 13.5 Result — PDHD busy set of 6, sequential (`JOBS=1`), pad 3

`pdvd/docs/perf/doc30r3_busy6.tsv`. `d30r3off` is the same binary with the knob absent, so this
isolates the knob and not the build.

| event | core-s OFF | core-s pad 3 | delta | peak GB OFF | peak GB pad 3 | delta | `TaggerCheckSTM` res delta OFF -> pad 3 |
|---|---|---|---|---|---|---|---|
| 028084/2 | 68.1 | 42.9 | **-37.1 %** | 5.00 | 2.19 | **-56.2 %** | 3.35 -> 0.50 GB |
| 028084/18 | 84.8 | 63.0 | -25.7 % | 4.58 | 2.41 | -47.4 % | 2.05 -> 0.03 |
| 029107/9 | 13.3 | 12.5 | -6.0 % | 1.39 | 1.10 | -20.8 % | 0.43 -> 0.14 |
| 029107/12 | 50.2 | 35.0 | -30.4 % | 3.17 | 1.73 | -45.3 % | 1.76 -> 0.32 |
| 029107/15 | 47.2 | 34.2 | -27.5 % | 3.51 | 1.94 | -44.6 % | 1.90 -> 0.32 |
| 029107/18 | 65.7 | 47.0 | -28.5 % | 4.31 | 2.18 | -49.4 % | 2.59 -> 0.46 |
| **sum / max** | **329.4** | **234.6** | **-28.8 %** | **5.00** | **2.41** | **-51.8 %** | |

029107/9 is the light event (13 s, 1.4 GB) and moves least, as it should: it has little
2-D map to not build. The census reports `nclus 102, nfit 29, sum_npts 10819` identically
in both arms — the fits themselves are untouched.

**Stacked on round 1**, PDHD's worst observed event goes 7.51 GB (pre-round-1) -> 5.00
(round 1) -> **2.19 GB** (round 3 at pad 3), and the two rounds together take about a third
of the CPU out of the heavy events.

### 13.6 PDVD — smaller, and that is the expected shape

Same knob, same pin, PDVD `-nu -stm-fit` on the doc-28 busy set of 7 (`d48nu7` pctrees),
sequential. `pdvd/docs/perf/doc30r3_pdvd7.tsv`.

| event | core-s OFF | core-s pad 3 | delta | peak GB OFF | peak GB pad 3 | delta | STM res delta |
|---|---|---|---|---|---|---|---|
| 039252/5 | 45.7 | 41.4 | -9.4 % | 2.28 | 2.03 | -10.9 % | 0.18 -> 0.01 |
| 039252/8 | 72.3 | 64.6 | -10.6 % | 2.73 | 2.39 | -12.5 % | 0.26 -> 0.00 |
| 039252/15 | 25.0 | 22.4 | -10.5 % | 2.38 | 2.08 | -12.6 % | 0.45 -> 0.17 |
| 039253/11 | 42.3 | 36.8 | -13.1 % | 2.85 | 2.39 | -16.2 % | 0.48 -> 0.03 |
| 039253/15 | 27.6 | 25.1 | -9.1 % | 2.08 | 1.87 | -10.1 % | 0.36 -> 0.16 |
| 039349/6 | 12.4 | 11.3 | -9.1 % | 1.15 | 1.04 | -9.7 % | 0.21 -> 0.10 |
| 039349/7 | 21.2 | 20.1 | -5.5 % | 1.94 | 1.68 | -13.2 % | 0.38 -> 0.14 |
| **sum / max** | **246.6** | **221.6** | **-10.1 %** | **2.85** | **2.39** | **-16.2 %** | |

**-10 % CPU and -10..16 % peak, against PDHD's -29 % and -56 %**, and the reason is the one
§2 already established: on PDVD the STM stage is a *small* part of the job (0.18-0.48 GB of
a 1.2-2.9 GB peak, vs PDHD's 2.0-3.4 GB of a 1.4-5.0 GB peak). The lever removes the same
fraction of the same thing; PDVD simply has less of it. Two-thirds of PDVD's remaining
peak is `CreateSteinerGraph` and the loaded tree, which this round does not touch.

Reported, not averaged away: pooling the two detectors would have advertised ~-20 % CPU,
which is true of neither.

### 13.7 Gates

**Gate A — knob OFF is byte-identical.** `d30r2a` (round-1/2 pin `a315be6b7b24`) vs
`d30r3off` (round-3 pin `f1ba2956d921`, knob absent from every `*_track_fitting.json`),
PDHD busy 6: **PASS 6/6, five products each** — `mabc-pr.zip` by member content, the calib
dump minus timers, both `tracking-*.root` by tree content, and `T_proj_data` by the new
cell hash. `pdvd/docs/perf/doc30r3_gateA_busy6.txt`; gate B's output is
`pdvd/docs/perf/doc30r3_gateB_ON_vs_OFF.txt` and the pad scan is
`pdvd/docs/perf/doc30r3_padscan.txt`.

**Gate B — knob ON changes the display product and nothing else.** This is the empirical
form of §13.1, and it doubles as the negative control that proves the instrument can see a
difference at all.

| arm pair | events | what changed |
|---|---|---|
| PDHD `-stm` `d30r3off` vs `d30r3p3` | 6 | `tracking-stm.root:T_proj_data` — **only** |
| PDVD `-nu` `d30r3voff` vs `d30r3vp3` | 7 | `T_proj_data` in both ROOT files, and the calib JSON **only when its `proj` block is included** (`calib(proj kept)`: identical with `proj` dropped) — **nothing else** |

Products verified *non-vacuously* identical (present and non-empty on both sides, per
`hash_root_trees.py --per-tree`): `mabc-pr.zip`; `T_rec_charge`, `T_stm_pass`, `T_stm_eval`
(PDHD and PDVD); `T_stm_michel`, `T_stm_michel_pts` and the non-`proj` calib dump (PDVD).
**Stated so it is not over-read:** `T_tagger` and `T_kine` are *absent* from the PR job's
ROOT files (the Q/L job writes them), and PDHD `-stm` writes no calib dump, so those
comparisons were `NONE == NONE` and prove nothing. What the gate does cover is the STM
verdicts, the Michel result, the fitted points and the Bee clustering output.

`./build/clus/wcdoctest-clus`: **334/334 test cases, 23144/23144 assertions** (328 before;
the 6 new cases are this round's). Freshness proof done before every arm (installed
`libWireCellClus.so` 08:48 vs last source edit 08:47); pin fingerprint `f1ba2956d921`
unchanged before and after.

### 13.8 How to turn it on, and what is left

The knob is **OFF in the shipped tree and in every detector's config** — the guarantee is
literally `grep -rn proj_pad_wire cfg/` returning nothing. `TrackFitting.cxx` is shared with
SBND and uBooNE, and this is what keeps them still: not an argument about their code paths,
but the absence of the key from `sbnd_track_fitting.json` and the uBooNE presets.

`TrackFittingPresets::create_with_current_values()` does **not** assign these two fields —
same as `proj_skip_unmapped_face` and `good_point_pitch_frac`, and unlike
`skip_revert_iso_xext_cut` — so they keep the C++ default through the preset, and
`load_trackfitting_config` (which runs *after* construction) can still set them. The knob is
therefore reachable from any detector's `*_track_fitting.json`, including SBND's and
uBooNE's; nothing about their code paths keeps them still, only the absent key.

To turn it on for one detector, add two lines to that detector's file — nothing else:

```json
    "proj_pad_wire": 3,
    "proj_pad_time": 3,
```

That is an owner decision, not a performance one, and it is deliberately not done here: it
changes what the 2-D scan displays. The evidence for making it is §13.4 (a five-cell context
band costs 12 % of the stored cells) and §13.7 (nothing but the display moves).

**The next lever, and it needs no knob at all.** `check_stm_conditions` fits each pass
twice: a round-1 fit on the rough path (`TaggerCheckSTM.cxx:3606`) and a round-2 fit on the
adjusted path (`:3622`), and `begin_pass_record` captures the 2-D map only after the round-2
fit (`:3624`). The round-1 fit's `fill_fitted_charge_2d` output is therefore built in full
and then thrown away by the next fill's `m_fitted_charge_2d.clear()` — **about half of the
103 fills per event are never read by anyone.** A `want_2d` flag threaded through
`do_single_tracking` would drop them, byte-identically, with no knob. It is worth less now
than it was before this round (each fill is ~5x cheaper), which is why it is named here and
not built: measure it before believing a number, per round 2.

Still untouched and still the largest remaining block on PDVD: `CreateSteinerGraph` (26.4 %
of CPU in §12.1, spread with no local win) and the loaded live tree.

## Milestone log

- 2026-09-07 (round 3) — the owner answered §12.4's question; `proj_pad_wire`/`proj_pad_time`
  shipped default-OFF (toolkit, doctest_doc30_proj_pad.cxx); the pad measured nearly free
  (§13.4); PDHD busy 6 −28.8 % core-s and −51.8 % peak, PDVD busy 7 −10.1 %/−16.2 % (§13.5,
  §13.6); a gate blindness to `T_proj_data` found and the 362 round-1 arms re-checked (§13.2).
- 2026-09-07 (round 2) — first CPU profile (§12.1); three byte-identical levers tried,
  all measured at noise, none shipped (§12.2); the sizing census shipped and gated (§12.3);
  the 40–45x over-storage in `fill_fitted_charge_2d` sized and referred to the owner (§12.4).
- 2026-09-07 — instrument bias found and quantified (§1); the `save_stm_fit` bracket
  located the carrier (§3); jemalloc live-heap named the two copy sites (§4); root cause
  §5; two `std::move`s shipped as toolkit `c61de88a`; gates §7; scaling law §8;
  five levers measured and not taken §9.
