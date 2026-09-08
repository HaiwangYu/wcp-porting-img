# SBND Standalone Imaging, Clustering, and Bee (`sbnd_xin/`)

> **Production running condition + validation checklist (for the LArSoft integration): [92_production-running-and-validation-guide.html](92_production-running-and-validation-guide.html)** (self-contained HTML, doc 92).
> Refreshed 2026-09-08 onto the **prod0908** epoch, produced at the head of `master` — see [102_master-branch-pr-samples.md](102_master-branch-pr-samples.md).
> For per-script details see **[3_scripts.md](3_scripts.md)**.
> For geometry / timing constants see **[2_geometry-and-timing.md](2_geometry-and-timing.md)**.
> For the imaging algorithm deep-dive see **[4_imaging.md](4_imaging.md)**.
> For the clustering algorithm deep-dive see **[5_clustering.md](5_clustering.md)**.

## Common conventions

Every `run_*.sh` script shares a set of ergonomic features provided by
`_runlib.sh`:

**`-h` / `--help`** — every script prints its usage, the resolved input/work-dir
scheme, and the available input sets:
```bash
./run_img_evt.sh -h
```

**`-N <n>` sample size** — choose which input set to run:
`input_files/input-<n>evt-<mode>/` (default `10`). Equivalent to exporting
`SBND_SAMPLE=<n>`. Available sets: `input-{10,100}evt-{mc,data}`.
```bash
./run_img_evt.sh mc -N 100 all     # image all events of the 100-event mc sample
./run_ql_evt.sh  data -N 100 1     # Q/L-match idx 1 of the 100-event data sample
```
> The **mc 100-event set is malformed upstream**: 100 frame members but only 41
> unique event ids (duplicated frames). `load_events` dedups, so it resolves to
> 41 events. The **data 100-event set is clean** (100 events, 1:1 with opflash).

**No-arg listing** — run any script with no `<idx>` to list valid events for the
chosen sample & mode:
```bash
./run_img_evt.sh           # default 10evt mc
# Sample: input-10evt-<mode>   (10 events)
# Available SBND events (1-based index → event ID):
#   idx 1   → evt 2
#   ...
#   idx 10  → evt 42
./run_img_evt.sh data -N 100   # lists the 100 data events
```

**`IDX=all` parallel mode** — pass `all` as the event index to process every
event in parallel:
```bash
./run_sp_to_magnify_evt.sh all
./run_img_evt.sh all
./run_clus_evt.sh all
./run_bee_img_evt.sh all
```
Jobs run concurrently up to `$(nproc)` (override with `SBND_MAX_JOBS=N`).
Per-event logs go to `work/.batch_<stage>_evt<ID>.log`. A summary at the end
shows ok / failed counts.

**Skip-on-missing** — in `all` mode, an event whose required inputs are absent
is skipped with a one-line note instead of aborting the whole batch. In
single-event mode the same condition exits non-zero.

**Concurrency cap:**
```bash
SBND_MAX_JOBS=4 ./run_img_evt.sh all   # cap at 4 simultaneous jobs
```

---

## Provenance

Ported from the LArSoft-coupled configuration in `wcp-porting-img/sbnd/`.
"Standalone" means no LArSoft: input is a tarball of numpy arrays produced
by the DNN-SP signal-processing chain (dumped from LArSoft via
`wcls-sp-dump.fcl`). This directory does **not** run noise filtering or signal
processing — those steps are already done.

Reference configs used as a template are in `input_files/` (symlink to
`../standalone-sample/`).

---

## Directory layout

```
sbnd_xin/
├── _runlib.sh                 # shared helpers: list_events, lookup_evt_id, batch_*
├── run_sp_to_magnify_evt.sh   # stage 1: SP frames → Magnify ROOT + per-anode archives
├── run_select_evt.sh          # stage 1b (optional): Woodpecker GUI tick/channel selection
├── run_img_evt.sh             # stage 2: SP frames → imaging cluster .npz files
├── run_clus_evt.sh            # stage 3: imaging clusters → blob clustering .zip files
├── run_ql_evt.sh             # stage 3b: imaging clusters + opflash → charge-light (Q/L) matching .zip (self-contained, per-event; see docs/8_ql-chain.md)
├── run_bee_img_evt.sh         # stage 4: imaging clusters → Bee display upload
│
├── wct-sp-to-magnify.jsonnet  # wire-cell config: stage 1 pipeline
├── wct-img-all.jsonnet        # wire-cell config: stage 2 pipeline
├── wct-clustering.jsonnet     # wire-cell config: stage 3 pipeline
├── wct-clus-matching-perevt.jsonnet # wire-cell config: stage 3b (per-event Q/L matching)
├── clus.jsonnet               # helper: re-exports canonical cfg/pgrapher/experiment/sbnd/clus.jsonnet (per-APA / all-APA clustering subgraphs)
├── magnify-sinks.jsonnet      # helper: per-anode MagnifySink pipelines
│
├── wct-img-2-bee.py           # Python: invoke wirecell-img bee-blobs per anode
├── merge_sel_archives.py      # Python: merge masked per-anode archives after Woodpecker
├── upload-to-bee.sh           # symlink → ../../upload-to-bee.sh
│
├── input_files/               # symlink → ../standalone-sample/ (LArSoft-dumped inputs)
├── work/                      # per-event scratch: evt2/, evt2_sel1/, …
├── data/                      # staging dir for Bee JSON (built by wct-img-2-bee.py)
└── docs/                      # this documentation
```

---

## Input

The pipeline consumes a **per-event tarball of numpy arrays** produced by
LArSoft's DNN signal-processing dump (`wcls-sp-dump.fcl`). Imaging and clustering
are **mode-aware** (`mc` | `data`); each mode has its own master multi-event
tarball provided upstream:

```
input_files/input-10evt-mc/frames-dnn.tar.bz2      # mc   10-event set: 2 9 11 12 14 18 31 35 41 42
input_files/input-10evt-data/frames-dnn.tar.bz2    # data 10-event set: 659242 … 660892
input_files/input-100evt-mc/frames-dnn.tar.bz2     # mc   100-event set → 41 unique (duplicated upstream)
input_files/input-100evt-data/frames-dnn.tar.bz2   # data 100-event set: 100 events, clean
```

Pass `mc` (default) or `data` as the first argument, and `-N <n>` to choose the
sample size (default 10; e.g. `-N 100`); the event list is derived from the chosen
archive (`run_*.sh <mode> [-N n]` with no index lists it). MC and data event IDs are
disjoint, so `work/evt<ID>/` never collides between modes. (The legacy
`input_files/2025f-mc-sp-frames.tar.bz2` is no longer referenced.)

Arrays inside the tarball (one set per event ID `<EVT>`):

| File | Shape | Description |
|---|---|---|
| `frame_dnnsp_<EVT>.npy` | (nchan, nticks) | DNN-SP ADC traces, tag `dnnsp` |
| `channels_dnnsp_<EVT>.npy` | (nchan,) | global channel indices for each row |
| `tickinfo_dnnsp_<EVT>.npy` | (3,) | tick0, tick_period, nticks |
| `summary_dnnsp_<EVT>.npy` | (nchan,) | per-channel summary (optional) |
| `chanmask_bad_<EVT>.npy` | varies | bad-channel mask |

The loose `*_2.npy` files at the top of `sbnd_xin/` are sample copies for
event 2; they are not consumed directly by the pipeline.

**Event index mapping** (mc mode; derived at run time from the mode archive —
`./run_img_evt.sh <mode>` with no index prints the live table):

| idx | mc Event ID | data Event ID |
|---|---|---|
| 1 | 2 | 659242 |
| 2 | 9 | 659286 |
| 3 | 11 | 659374 |
| 4 | 12 | 659484 |
| 5 | 14 | 659572 |
| 6 | 18 | 659704 |
| 7 | 31 | 659924 |
| 8 | 35 | 660496 |
| 9 | 41 | 660826 |
| 10 | 42 | 660892 |

`run_img_evt.sh` (and `run_sp_to_magnify_evt.sh`) self-extract the per-event
subset from the mode archive into `work/evt<ID>/sp-frames.tar.bz2` on use, so
imaging is a complete entry point — no manual extraction step.

---

## Pipeline (end-to-end)

```
input_files/input-10evt-<mode>/frames-dnn.tar.bz2     (mode = mc | data)
   │  (per-event subset self-extracted on use)
   ▼
work/evt<ID>/sp-frames.tar.bz2
   │
   ▼  run_sp_to_magnify_evt.sh <mode>  →  wct-sp-to-magnify.jsonnet
   │     magnify-evt<ID>-anode{0,1}.root         (Magnify ROOT for validation)
   │     sbnd-sp-frames-anode{0,1}.tar.bz2       (per-anode, for Woodpecker)
   │
   ├─ (optional) run_select_evt.sh -s <tag>
   │     woodpecker GUI → masked per-anode archives
   │     merge_sel_archives.py → sp-frames.tar.bz2 with selection applied
   │
   ▼  run_img_evt.sh <mode>  →  wct-img-all.jsonnet
   │     icluster-apa{0,1}-active.npz
   │     icluster-apa{0,1}-masked.npz
   │
   ▼  run_clus_evt.sh <mode>  →  wct-clustering.jsonnet + clus.jsonnet
   │     mabc-apa<N>-face0.zip    (per-APA clustering, Bee points included)
   │     mabc-all-apa.zip         (all-APA combined clustering)
   │
   ├─ (charge–light) run_ql_evt.sh  →  wct-clus-matching-perevt.jsonnet
   │     + input-10evt-<mode>/opflash_apa{0,1}.tar.gz
   │     work/ql_evt<ID>/mabc-all-apa.zip  (img + clustering + 2-view dead + op/Q-L)
   │     self-contained per-event matching; see docs/8_ql-chain.md
   │
   ▼  run_bee_img_evt.sh  →  wct-img-2-bee.py  →  wirecell-img bee-blobs
         data/0/0-apa{0,1}.json
         upload_evt<ID>[_<SEL>][_a<N>].zip  →  upload-to-bee.sh → Bee server
```

---

## How to run

### Environment

Each shell script sets `WIRECELL_PATH` automatically:

```sh
export WIRECELL_PATH=/nfs/data/1/xqian/toolkit-dev/toolkit/cfg:\
/nfs/data/1/xqian/toolkit-dev/wire-cell-data:$WIRECELL_PATH
```

No manual export is needed before calling the scripts.

### Quick start — imaging + clustering (mc idx=1 → evt 2)

```sh
cd /nfs/data/1/xqian/toolkit-dev/toolkit/sbnd_xin   # or wcp-porting-img/sbnd/sbnd_xin

./run_img_evt.sh  mc 1                # self-extracts SP frames → work/evt2/icluster-apa{0,1}-*.npz
./run_clus_evt.sh mc 1                # produces work/evt2/mabc-*.zip
./run_bee_img_evt.sh 1                # uploads Bee display for imaging result
```

`run_img_evt.sh` is a complete entry point — it self-extracts the per-event SP
frames, so the `run_sp_to_magnify_evt.sh` step is only needed for Magnify ROOT
validation or Woodpecker selection.

### Data mode (idx=1 → evt 659242)

```sh
./run_img_evt.sh  data 1              # work/evt659242/icluster-apa{0,1}-*.npz
./run_clus_evt.sh data 1              # work/evt659242/mabc-*.zip  (reality=data)
# all events in parallel:
./run_img_evt.sh  data all
./run_clus_evt.sh data all
```

Outputs land in `work/evt<ID>/`. Logs are `work/evt<ID>/wct_<stage>_evt<ID>.log`.

### With Woodpecker selection

Select a region of interest before imaging:

```sh
./run_sp_to_magnify_evt.sh 1          # need per-anode SP archives first
./run_select_evt.sh 1 sel1            # opens GUI; produces work/evt2_sel1/input/
./run_img_evt.sh   1 -s sel1          # uses masked SP archive
./run_clus_evt.sh  1 -s sel1
./run_bee_img_evt.sh 1 -s sel1
```

### Single-anode runs

Pass `-a 0` or `-a 1` to `run_img_evt.sh`, `run_clus_evt.sh`, and
`run_bee_img_evt.sh` to process one anode only. Logs and outputs gain the
`_a<N>` suffix.

---

## Bee upload

### Path A — imaging → Bee directly

`run_bee_img_evt.sh` reads `icluster-apa*-active.npz`, calls
`wct-img-2-bee.py` (which invokes `wirecell-img bee-blobs` per anode), zips
the resulting JSON files into `upload_evt<ID>.zip`, and passes it to
`upload-to-bee.sh`.

### Path B — clustering → Bee (no separate step needed)

`MultiAlgBlobClustering` in `clus.jsonnet` (which re-exports the canonical
`cfg/pgrapher/experiment/sbnd/clus.jsonnet`) writes Bee-format zip files
directly (`mabc-apa<N>-face0.zip`, `mabc-all-apa.zip`). These can be uploaded
to Bee manually or via `upload-to-bee.sh <zipfile>`.

---

## Known gotchas

- **5638 vs 5632 per-APA channels** — the shared
  `cfg/pgrapher/experiment/sbnd/img.jsonnet:47` previously used `5632*ident`, dropping
  the last 6 W-plane wires of APA0 and the last 12 of APA1. Patched to `5638*ident`
  in the local toolkit clone. The per-anode 5638-channel restriction is now done
  solely by `img.jsonnet`'s internal `chsel_pipes` (which select
  `5638*ident .. 5638*(ident+1)-1`); the previously redundant `chsel_correct`
  ChannelSelector pre-filter in `wct-img-all.jsonnet` has been removed.

- **Imaging tick clipping** — `cfg/pgrapher/experiment/sbnd/img.jsonnet` previously
  hardcoded `MaskSlices.max_tbin: 3400` (line 145) and `CMMModifier.org_hlimit: [3400]`
  (line 89), silently dropping the last 27 ticks of every event. Both raised to 3427
  to match the actual SP-frame readout window (input frames are 11276 × 3427).

- **Bee x0 / speed / t0 sign** — `wct-img-2-bee.py` uses `--t0 "205*us"` (positive)
  even though `clus.jsonnet` defines `time_offset = -205*us`. The sign flip is
  intentional: `BlobSampler` (C++) **adds** `time_offset` while `wirecell-img bee-blobs`
  (Python) **subtracts** `--t0`. See [2_geometry-and-timing.md](2_geometry-and-timing.md)
  for the full derivation.

- **Empty-cluster .npz files** — a run with no active blobs produces a 22-byte
  zip header (no arrays inside). Both `run_clus_evt.sh` and `run_bee_img_evt.sh`
  detect and skip these files so downstream stages do not stall.

- **trash-\*.tar.gz** — `TensorFileSink` writes small (~29-byte) placeholder
  archives during clustering. These are harmless and can be deleted.

- **Woodpecker WebAgg backend** — `run_select_evt.sh` exports `MPLBACKEND=WebAgg`
  and prints the SSH port-forwarding command needed to reach the browser GUI
  from a remote machine.
