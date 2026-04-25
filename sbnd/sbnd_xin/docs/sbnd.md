# SBND Standalone Imaging, Clustering, and Bee (`sbnd_xin/`)

> For per-script details see **[scripts.md](scripts.md)**.
> For geometry / timing constants see **[geometry-and-timing.md](geometry-and-timing.md)**.

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
├── run_sp_to_magnify_evt.sh   # stage 1: SP frames → Magnify ROOT + per-anode archives
├── run_select_evt.sh          # stage 1b (optional): Woodpecker GUI tick/channel selection
├── run_img_evt.sh             # stage 2: SP frames → imaging cluster .npz files
├── run_clus_evt.sh            # stage 3: imaging clusters → blob clustering .zip files
├── run_bee_img_evt.sh         # stage 4: imaging clusters → Bee display upload
│
├── wct-sp-to-magnify.jsonnet  # wire-cell config: stage 1 pipeline
├── wct-img-all.jsonnet        # wire-cell config: stage 2 pipeline
├── wct-clustering.jsonnet     # wire-cell config: stage 3 pipeline
├── clus.jsonnet               # helper: per-APA / all-APA clustering subgraphs
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
LArSoft's DNN signal-processing dump (`wcls-sp-dump.fcl`). The master
multi-event tarball lives at:

```
input_files/2025f-mc-sp-frames.tar.bz2
```

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

**Event index mapping** (defined in each shell script):

| idx | Event ID |
|---|---|
| 1 | 2 |
| 2 | 9 |
| 3 | 11 |
| 4 | 12 |
| 5 | 14 |
| 6 | 18 |
| 7 | 31 |
| 8 | 35 |
| 9 | 41 |
| 10 | 42 |

The first call to `run_sp_to_magnify_evt.sh` (or any script that needs
`sp-frames.tar.bz2`) extracts the per-event subset into `work/evt<ID>/`
automatically.

---

## Pipeline (end-to-end)

```
input_files/2025f-mc-sp-frames.tar.bz2
   │  (extracted on first use)
   ▼
work/evt<ID>/sp-frames.tar.bz2
   │
   ▼  run_sp_to_magnify_evt.sh  →  wct-sp-to-magnify.jsonnet
   │     magnify-evt<ID>-anode{0,1}.root         (Magnify ROOT for validation)
   │     sbnd-sp-frames-anode{0,1}.tar.bz2       (per-anode, for Woodpecker)
   │
   ├─ (optional) run_select_evt.sh -s <tag>
   │     woodpecker GUI → masked per-anode archives
   │     merge_sel_archives.py → sp-frames.tar.bz2 with selection applied
   │
   ▼  run_img_evt.sh  →  wct-img-all.jsonnet
   │     icluster-apa{0,1}-active.npz
   │     icluster-apa{0,1}-masked.npz
   │
   ▼  run_clus_evt.sh  →  wct-clustering.jsonnet + clus.jsonnet
   │     mabc-apa<N>-face0.zip    (per-APA clustering, Bee points included)
   │     mabc-all-apa.zip         (all-APA combined clustering)
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

### Quick start — event 2 (idx=1), full pipeline

```sh
cd /nfs/data/1/xqian/toolkit-dev/toolkit/sbnd_xin   # or wcp-porting-img/sbnd/sbnd_xin

./run_sp_to_magnify_evt.sh 1          # produces work/evt2/magnify-evt2-anode{0,1}.root
./run_img_evt.sh 1                    # produces work/evt2/icluster-apa{0,1}-*.npz
./run_clus_evt.sh 1                   # produces work/evt2/mabc-*.zip
./run_bee_img_evt.sh 1                # uploads Bee display for imaging result
```

Outputs land in `work/evt2/`. Logs are `work/evt2/wct_<stage>_evt2.log`.

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

`MultiAlgBlobClustering` in `clus.jsonnet` writes Bee-format zip files
directly (`mabc-apa<N>-face0.zip`, `mabc-all-apa.zip`). These can be uploaded
to Bee manually or via `upload-to-bee.sh <zipfile>`.

---

## Known gotchas

- **5638 vs 5632 per-APA channels** — the shared `cfg/pgrapher/experiment/sbnd/img.jsonnet`
  hardcodes `5632` per APA, dropping 6 W-plane wires. `wct-img-all.jsonnet` inserts
  a corrective `ChannelSelector` (5638-wide) to work around this. This is a known
  upstream bug tracked separately.

- **Bee x0 / speed / t0 sign** — `wct-img-2-bee.py` uses `--t0 "200*us"` (positive)
  even though `clus.jsonnet` defines `time_offset = -200*us`. The sign flip is
  intentional: `BlobSampler` (C++) **adds** `time_offset` while `wirecell-img bee-blobs`
  (Python) **subtracts** `--t0`. See [geometry-and-timing.md](geometry-and-timing.md)
  for the full derivation.

- **Empty-cluster .npz files** — a run with no active blobs produces a 22-byte
  zip header (no arrays inside). Both `run_clus_evt.sh` and `run_bee_img_evt.sh`
  detect and skip these files so downstream stages do not stall.

- **trash-\*.tar.gz** — `TensorFileSink` writes small (~29-byte) placeholder
  archives during clustering. These are harmless and can be deleted.

- **Woodpecker WebAgg backend** — `run_select_evt.sh` exports `MPLBACKEND=WebAgg`
  and prints the SSH port-forwarding command needed to reach the browser GUI
  from a remote machine.
