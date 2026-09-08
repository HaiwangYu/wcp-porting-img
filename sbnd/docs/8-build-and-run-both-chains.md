# Build WCT/larwirecell, and run BOTH chains (ours 1-step, Xin's 2-step)

Written 2026-09-08 from the ap-2026-09-05 validation (ai-helper issues 22/23).
Companion to — not a replacement for — `0-build-wct-larwirecell-sl7-sbnd.md`
(the base build recipe) and `1-run-tests-sl7-local-builds-sbnd.md` (running the
1-step). This doc records what those two do **not** say: the spdlog/fmt
resolution, the gate items that catch a *useless* green build, and how to drive
Xin's chain on this machine.

Everything runs inside the SL7 apptainer via
`/exp/sbnd/app/users/yuhw/claude-utilities/in-gpvm-sl7.sh`.

---

## 1. Build wire-cell-toolkit

Reproducible configure: `wire-cell-toolkit-ai-helper/issues/23-*/scripts/configure-wct.sh`.

    ./wcb clean && rm -rf build          # NEVER hand-patch build/c4che/_cache.py
    <configure-wct.sh>                   # inside SL7
    CXXFLAGS="-DSPDLOG_FMT_EXTERNAL" ./wcb -p --notests install -j16   # ~13 min, ~180 min CPU

### The spdlog/fmt question, settled

| product | version / flavor | role |
|---|---|---|
| spdlog | **v1_14_1**, `Linux64bit+3.10-2.17-e26-prof` — the **external-fmt** build | runtime shared lib |
| fmt | **v11_0_2**, same flavor (`libfmt.a`) | **build time only** — static, no `NEEDED` entry |

Five things that cost a day between them:

1. **The ambient ups spdlog is v1_9_2, a bundled-fmt build** that `Spdlog.h`
   rejects outright. It must be overridden explicitly; the default environment
   can never satisfy WCT.
2. **`v1_14_1` and `v1_14_1b` share a SONAME** (`libspdlog.so.1.14`) and differ
   *only* in bundled vs external fmt. A build wrongly configured against
   `v1_14_1b` still satisfies its runtime soname — there is no loader error.
   The only place the difference shows is `Spdlog.h`'s `#error` at compile time.
   **Check `INCLUDES_SPDLOG` in `_cache.py` names `v1_14_1`.**
3. **Libraries live in `lib64`, not `lib`.** `-L…/lib` finds nothing.
4. **wcb has no `--with-fmt`.** `waft/generic.py:140,146` splits
   `--with-X-include` / `--with-X-lib` on commas (`:104` for `--with-X-libs`),
   so fmt rides *inside* the spdlog options:
   `--with-spdlog-include=$SPD/include,$FMT/include`,
   `--with-spdlog-lib=$SPD/lib64,$FMT/lib64`, `--with-spdlog-libs=spdlog,fmt`.
5. **`-DSPDLOG_FMT_EXTERNAL` must reach the CONFIGURE CHECK, via `CXXFLAGS`.**
   waf does **not** read a `DEFINES` env var here. Without the define, spdlog's
   `fmt/fmt.h` includes `spdlog/fmt/bundled/core.h`, which an external-fmt
   build does not ship, and the check fails with "No such file or directory".

`spdlog/v1_14_1`'s own `.pc` carries both the define and `Requires: fmt` — but
pkg-config is unusable here: every `.pc` `prefix` is a build-machine path
(`/scratch/workspace/...`) and this pkg-config predates `--define-prefix`.

### Post-build gate — 9 items, and two of them matter most

| check | why |
|---|---|
| `rc=0`, 0 error lines | — |
| 19 `libWireCell*.so` installed, incl. `libWireCellMcs.so` | `mcs` is a newer subpackage; its absence means a stale configure |
| **undefined `__libc_single_threaded` = 0** in Util and Clus | non-zero ⇒ built on the HOST, not in SL7. Fails at plugin LOAD, not at build |
| RUNPATH → `spdlog/v1_14_1/…/lib64` | proves the right spdlog got linked |
| `NEEDED fmt` = 0 | fmt is static, as expected |
| `miniz.h` in `opt/include/WireCellUtil/custard/` | `wcb install` does not install it; larwirecell needs it |
| **the binary knows the config keys it will be handed** | see below |

The last one exists because of a real failure: a build on `origin/master`
`e88f364d` passed **every other check** and was still useless — `flash_by_gid`
and `merge_flash_pcs` appear in **0 files** at that commit, so it could not
honour `ref/prod-2026-09-05`. Verifying a build *succeeded* is not verifying it
can run the config:

    strings opt/lib/libWireCell{Clus,Root,Match}.so | grep -c '^flash_by_gid$'

### Choosing the commit to build

Do it by **measurement**, not by date. Compile the candidate's cfg tree and diff
the artifact against the pin:

    scripts/cfg/compile_prjob_cfg.sh <cfgtree> /tmp/p.json && cmp /tmp/p.json ref/prod-2026-09-05/prod_prjob.json

`ref/prod-<date>` is a **generation counter, not a commit date** —
`prod-2026-09-05` was cut 2026-09-03. Of five plausible candidates only
`94590129` and `5d0b4e77` compiled byte-identically; `origin/master`,
`eb6e57f3` (adds the knobs, default OFF) and `6365aa00` all differ by
`flash_by_gid`. The flip commit is what matters, and `git log -S` **cannot find
a flip** — a `false`→`true` edit does not change occurrence counts. Use
`git log -G`.

---

## 2. Build larwirecell

    # after WCT is installed
    export WIRECELL_FQ_DIR=/exp/sbnd/app/users/yuhw/opt
    export CMAKE_PREFIX_PATH=/exp/sbnd/app/users/yuhw/opt:$CMAKE_PREFIX_PATH
    source .../localProducts_larsoft_v10_14_02_02_e26_prof/setup && mrbsetenv
    cd $MRB_BUILDDIR/larwirecell && make -j12          # NOT `make install`

`make install` **always fails here**: `CMAKE_INSTALL_PREFIX` is the read-only
`/usr/local`, so it dies copying `README.md` *after* a successful compile. Build
only, then hand-copy from `$MRB_BUILDDIR/larwirecell/lib/` to
`opt/larwirecell/v10_01_28/slf7.x86_64.e26.prof/lib/` (back the deployed set up
first). Verify with `ldd`: every `libWireCell*.so` must resolve under
`/exp/.../opt/lib`, never cvmfs.

**Expect byte-identical libraries.** Twice now (Sep 2 and Sep 8) a full
recompile against a changed WCT produced libs byte-identical to the previous
build. That is informative, not suspicious: it means the WCT change touched no
header larwirecell depends on. If they *do* differ, that is worth understanding
before deploying.

Use the MRB tree at `larsoft-wct036/v10_14_02/srcs/larwirecell`. The tree at
`/exp/sbnd/app/users/yuhw/larwirecell` is source-only and is NOT the one built.

---

## 3. Run OUR 1-step chain (LArSoft, artROOT in)

One `lar` process per event, via the per-event harness:

    <harness> <manifest> <outdir> <nworkers> <cores-per-worker> <fcl>

    e.g. run-harness.sh ncpi0.manifest out 10 1 wcls-img-clus-matching-xin-data.fcl

- fcl is **required, no default**: `wcls-img-clus-matching-xin.fcl` (MC,
  `simtpc2d` tags) vs `-data.fcl` (data, `sptpc2d`). A default that is silently
  wrong for half the callers once cost 3h16m and 13 217 failed events.
- Manifest lines are `<file>\t<nskip>\t<run>\t<subrun>\t<event>`. **`--nskip k`
  counts in art's FileIndex (RSE-sorted) order, not Events-tree order** — assign
  `k` over the RSE sort, or every output is mislabelled in a merged file.
- The harness re-reads the true RSE from each job's own `Trun` and renames from
  that, so a wrong prediction is loud rather than silent. Watch the
  `rse_check` column.
- Outputs per event: `bee_r<run>_s<sub>_e<evt>.zip`, `tracking-pr_*.root`,
  `nugraph_*.h5`, plus `summary.csv` (rc, wall, peak RSS, sizes, audit).
- Budget ~2 GB peak RSS and 40–110 s per event; size worker count on sampled
  concurrent RSS, not the sum of peaks.

`setup-ap.sh` **prepends the WCT checkout's `cfg/`** to `WIRECELL_PATH`. So a
`git checkout` in the toolkit silently changes what a `lar` job runs, with
nothing rebuilt. Two failure modes seen: `unknown graph flavor relaxed_fast`
and `function has no parameter assoc_clear_on_merge` — both were config from one
branch meeting binaries from another. **Pin the branch, not just the build.**

---

## 4. Run XIN's 2-step chain

Two routes. Pick by what you need.

### 4a. In-tree canonical jsonnets (no sbnd_xin drivers)

`issues/20-campaign-summary/scripts/run-twostep.sh <file> <nskip> <run> <sub> <evt> <outdir>`
— three stages per event:

| stage | what |
|---|---|
| A | `lar -c wcls-img-dump.fcl` / `wcls-flash-dump.fcl` → `icluster-apa*.npz`, `opflash_apa*.tar.gz` |
| B | `wire-cell -c pgrapher/experiment/sbnd/wct-clus-matching-perevt.jsonnet` → `pctree.tar.gz` |
| C | `wire-cell -c pgrapher/experiment/sbnd/wct-pr-perevt.jsonnet` → `tracking-pr.root` |

**Method trap:** stage C must be given the production `pipeline_names` TLA. Its
in-signature default is the 10-stage pre-adoption list, so compiling bare
defaults reports a phantom 10-vs-15 stage difference that exists in neither real
chain.

### 4b. Xin's own driver, on his staged stage-A products

`sbnd_xin/run_pr_chain_batch.sh <ql_root> <out_root> data|sim [evt ...]`, reading
`ql_evt<ID>/` from an existing Q/L arm. This is what reproduces a production arm
byte-for-byte. Golden reference on this machine:
`/exp/sbnd/data/users/yuhw/sbnd_xin/work-ncpi0-d99r3prod{,pr}` (19 events at
plain `ref/prod-2026-09-05` defaults).

    export PR_JOBS=8 PR_EXTRA_STAGES=pr_display
    : > empty-tla.txt                     # EMPTY file, not unset -- deliberate
    PR_EXTRA_TLA=$PWD/empty-tla.txt ./run_pr_chain_batch.sh <ql_root> <out> data $(cat ref/prod-2026-09-05/gate308-ncpi0.txt)

Env needed here, because lines 56–57 hardcode Xin's `WCT_BASE`. No copy needed
for this part — the script appends what you pre-set, and its nonexistent paths
are skipped:

    export PR_CFG_TREE=/exp/sbnd/app/users/yuhw/wire-cell-toolkit/cfg
    export WIRECELL_PATH=/exp/sbnd/app/users/yuhw/wire-cell-data:/exp/sbnd/app/users/yuhw/wire-cell-data/sbnd/photodet:${WIRECELL_PATH:-}
    export PYTHONPATH=/exp/sbnd/app/users/yuhw/wire-cell-toolkit/pyutil/python:${PYTHONPATH:-}
    export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

**Three SL7 portability blockers.** The driver assumes a newer host than the
apptainer provides. Fix in **scratch copies** — `sbnd_xin` is read/run-only —
patch at `issues/23-*/scripts/sl7-runner-portability.patch`:

1. `run_pr_chain_batch.sh:1848` hardcodes `libpython3.11.so.1.0` while taking
   `LIBDIR` from the running python. SL7 is 3.9.15 ⇒
   `ERROR: libpython not found`. Derive `sysconfig.get_config_var('INSTSONAME')`.
2. `_runlib.sh:_batch_reap_one` uses `wait -n -p VARNAME`, needing **bash ≥ 5.1**
   (`wait -n` alone needs 4.3); the container has **4.2.46**, so `_pid` is never
   assigned and `set -u` aborts: `line 179: _pid: unbound variable`.
3. `"${ARR[@]}"` on an **empty** array trips `set -u` before bash 4.4 —
   `TFJSON_TLA[@]: unbound variable` at line 1918. This fires *only* on the
   no-TLA-override path, which is exactly the plain-defaults case a gate needs.
   Guard with `${ARR[@]+"${ARR[@]}"}` (25 sites).

A scratch copy must keep the layout: the driver resolves `$SX/_runlib.sh`,
`$SX/nusel_extract.py`, `$SX/wct-pr-perevt.jsonnet`,
`$SX/scripts/multi/*.py`, and `$SX/../../abtest`. Point `QL` at the **real**
`qlport` (the copy holds only the rewritten script) and keep
`compile_ub_cfg.sh` at `$QL/scripts/`.

---

## 5. Comparing the two chains

| tool | what it answers |
|---|---|
| `issues/20-*/scripts/deep_compare.py <W> <arm> <label>` | every `T_kine`/`T_tagger` branch hashed + every `T_rec_charge` point |
| `sbnd_xin/scripts/analysis/d99_root_branch_census.py A B --samples s --root R --expect ''` | **exhaustive**, no early exit — use for "nothing moved except X" |
| `sbnd_xin/scripts/pr87_root_tree_diff.py` | quick "did anything move?" — **truncates at 12 lines**, not an exhaustive claim |
| `cmp nusel-evt<ID>.tsv` | the authoritative per-event selection table |
| `issues/17-*/scripts/audit-config-diff.py a.json b.json` | compiled config, component-by-component |
| `sbnd_xin/pr_scores_table.py` + `scripts/pr142_campaign_ab.py` | population / movers vs `products/prod0902/` |

Exclusions that are legitimate, and why: `T_cluster.{flash_id,flash_time_us,flash_pe}`
on clusters with no valid flash (uninitialised-memory defect on both sides);
`off_ms`/`on_ms`/`elapsed_ms` in calib JSONs; `T_rec_charge.reduced_chi2` has
NaNs, so a naive `!=` reports every one. **Never compare archive bytes** — zip
and gzip carry timestamps; compare members.

Cross-machine reality: reproducing wcgpu1 on FNAL gave
`nusel-evt<ID>.tsv` **byte-identical 19/19** but `T_rec_charge:{q,reduced_chi2}`
differing at ~1e-13 relative, with per-event charge sums agreeing to 1e-16.
Different OS/compiler/libm legitimately breaks FP bit-identity; when it does,
population comparison (T3) becomes the primary tier, not the fallback.

---

## 6. What only an end-to-end run finds

Three tiers of gate passed — compiled-config diff at 0 keys, Xin's chain at 0 of
24 985 branch instances, population at 0 movers — while our 1-step could not
configure at all. Two merge defects, both one dropped token in a file upstream
had restructured:

- `per_apa()` stopped forwarding `pre_mabc`. The parameter stayed in the
  signature, so the call type-checks and the value goes nowhere ⇒
  `NamedFactory: Failed to find instance "rse_apa0"`, rc=66 on every event.
- the `clus_pr` node stopped emitting `rse_from_metadata` ⇒ `Trun` reports
  `0/0/<evt>`, the issue-13 G3 bug.

Why the gates were blind, and the general rule: a per-event config diff compares
only components present on **both** sides, so a component missing from ours and
absent by design from the reference is structurally invisible. And counting
occurrences of a feature name catches deletions but **never** a dropped argument
or a changed value — `pre_mabc` went 5 → 6 sites and `save_deadarea` 3 → 3 while
both were broken. Run the workflow.
