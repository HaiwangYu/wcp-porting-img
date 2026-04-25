# pdhd — ProtoDUNE-HD per-event scripts

Scripts and jsonnet configs for running per-event imaging and clustering on
ProtoDUNE-HD signal-processed data.

## Common conventions

Every `run_*.sh` script (except `run_select_evt.sh`, which is interactive)
shares three ergonomic features provided by `_runlib.sh`:

**No-arg listing** — run any script with no arguments to list available runs:
```bash
./run_img_evt.sh
# Available runs under .../pdhd/input_data:
#   run027409     events: 1 2 3 4 5 6 7
```

**`EVT=all` parallel mode** — pass `all` as the event number to process every
discovered event for that run in parallel:
```bash
./run_img_evt.sh 027409 all
./run_clus_evt.sh 027409 all
```
Events are discovered from `input_data/run<N>/evt_*` subdirectories and from
existing `work/<RUN_PADDED>_<EVT>/` directories.  Jobs run concurrently up to
`$(nproc)` (override with `PDHD_MAX_JOBS=N`).  Per-event logs go to
`work/.batch_<stage>_<run>_<evt>.log`.  A summary at the end shows ok / failed
counts and the failed event ids.

**Skip-on-missing** — in `all` mode, an event whose required inputs are absent
(no SP frames, no cluster tarballs, or a `-s sel_tag` directory that doesn't
exist) is skipped with a one-line note instead of aborting the whole batch.
In single-event mode the same condition exits non-zero (exit 2 = skip, 1 =
hard failure).

**Concurrency cap** — controlled by `PDHD_MAX_JOBS` (default `nproc`):
```bash
PDHD_MAX_JOBS=4 ./run_img_evt.sh 027409 all   # cap at 4 simultaneous jobs
```

## NF + SP

Standalone Noise Filter + Signal Processing chain (no art/LArSoft).
```bash
./run_nf_sp_evt.sh [-a ANODE] <run> <evt|all>
```
**Input**: `input_data/<run>/<evt>/protodunehd-orig-frames-anode{0..3}.tar.bz2`
**Output**: `work/<run>_<evt>/protodunehd-sp-frames{,-raw}-anode{N}.tar.bz2`

See `docs/nf.md`, `docs/sp.md`, `docs/nf_sp_workflow.md` for details.

## Imaging

Reads per-anode SP frame archives and produces cluster archives for each APA.

```bash
./run_img_evt.sh [-I] [-a ANODE] [-S] [-s SEL_TAG] <run> <evt|all>
```

**Options**

| Flag | Meaning |
|------|---------|
| `-I` | Force loading SP frames from `input_data/` even if `work/` has them |
| `-a N` | Process only anode N (default: all four, 0–3) |
| `-S` | Force-prefer sparse archives (`*-sparseon.tar.bz2`) for every anode that has one |
| `-s TAG` | Use a pre-selected input from `work/<run>_<evt>_<TAG>/input/` (produced by `run_select_evt.sh`) |

**Input** (auto-discovered under `input_data/`):

```
protodunehd-sp-frames-anode{N}.tar.bz2          # dense (default)
protodunehd-sp-frames-anode{N}-sparseon.tar.bz2 # sparse variant
```

**Archive selection logic** (per anode):

1. Dense archive present → use dense (default, no staging overhead).
2. Dense archive missing, sparse present → use sparse automatically.
3. `-S` flag given, sparse present → use sparse (force override).
4. Neither present → error.

When any anode needs a sparse archive, the script creates a small staging
directory (`work/.../sp_stage/`) with symlinks so all archives share the
filename pattern that `FrameFileSource` expects.

**Sparse format note**: sparse archives omit zero rows per tag independently
(e.g. `gauss0` and `wiener0` can have different row counts).  A `Reframer`
node in `wct-img-all.jsonnet` densifies each tag to the full anode channel
set before the imaging pipeline, so downstream components that require
uniformly-sized trace vectors work transparently with both formats.

**Output**: `work/<RUN>_<EVT>[_<SEL_TAG>]/clusters-apa-apa{N}-ms-{active,masked}.tar.gz`

**Examples**

```bash
# All anodes, dense archives (default)
./run_img_evt.sh 027409 1

# Single anode
./run_img_evt.sh -a 0 027409 1

# Force sparse for anode 0 (anodes 1–3 fall back to dense automatically)
./run_img_evt.sh -S -a 0 027409 1
./run_img_evt.sh -S 027409 1

# Use a pre-selected input set
./run_img_evt.sh -s sel1 027409 1
```

## Clustering

```bash
./run_clus_evt.sh [-a ANODE] [-s SEL_TAG] <run> <evt|all> [subrun]
```

Reads cluster archives from `work/<run>_<evt>[_<SEL_TAG>]/` and runs the full
clustering chain, producing output under the same work directory.

## Signal-processing frames → Magnify ROOT file

```bash
./run_sp_to_magnify_evt.sh [-I] [-s SEL_TAG] <run> <evt|all> [subrun]
```

Converts per-anode SP frame archives into per-anode Magnify ROOT files
(`magnify-run<RUN>-evt<EVT>-apa<N>.root`) containing TH2F waveform
histograms and a `Trun` metadata tree.  Frame tick count is auto-extracted
from the SP archive.

## Bee upload

```bash
./run_bee_img_evt.sh [-a ANODE] [-s SEL_TAG] <run> <evt|all> [subrun]
```

Single-event mode produces `upload_<run>_<evt>[_sel<TAG>].zip` and uploads
to Bee, printing the URL.

`all` mode combines every event into one `upload-batch-run<RUN_PADDED>.zip`
(layout `data/<i>/<i>-apa<N>.json`) and does a single upload.  The filename
prefix matches the directory index because Bee groups events by the leading
number of the filename stem (see `wirecell/bee/data.py:parse_pathname`);
naming every file `0-apa<N>.json` would collapse all events into one Bee
slot.

## Selection (optional pre-processing)

```bash
./run_select_evt.sh <run> <evt> <sel_tag>
```

Applies a channel/time selection and writes filtered SP frames to
`work/<run>_<evt>_<sel_tag>/input/`.  Interactive (Woodpecker GUI); not
batch-capable, so `EVT=all` is unsupported here.  Pass the resulting tag
with `-s` to the imaging or clustering scripts.
