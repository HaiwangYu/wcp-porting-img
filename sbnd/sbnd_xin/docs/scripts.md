# Script Reference (`sbnd_xin/`)

All scripts are run from `sbnd_xin/`. Each sets `WIRECELL_PATH` to include
`toolkit/cfg` and `wire-cell-data` — no manual export needed.

> For the end-to-end pipeline overview, quick start, and common conventions
> (no-arg listing, `IDX=all` parallel mode, `SBND_MAX_JOBS`) see **[sbnd.md](sbnd.md)**.

---

## Shell scripts (pipeline order)

### `_runlib.sh`

Shared helper library sourced by every `run_*.sh` script. Provides:

| Function | Description |
|---|---|
| `list_events` | Print the 10 idx→EVT_ID mappings; called on no-arg invocation |
| `lookup_evt_id <idx>` | Resolve 1-based index to event ID; error + table on bad input |
| `discover_event_indices` | Print `1 2 … 10`; used in `all`-mode loops |
| `batch_init` | Initialise counters and `BATCH_PIDS` assoc array |
| `batch_wait_slot` | Block until fewer than `SBND_MAX_JOBS` (default `nproc`) jobs are running |
| `batch_drain` | Wait for all remaining background jobs |
| `batch_summary` | Print ok/failed counts; returns 0 if at least one event succeeded |

Not invoked directly.

---

### `run_sp_to_magnify_evt.sh`

**Purpose:** Convert SP frames for one event to per-anode Magnify ROOT files
(for visual validation) and per-anode `gauss<N>`-tagged frame archives (input
for `run_select_evt.sh` / Woodpecker).

```
Usage: ./run_sp_to_magnify_evt.sh [-s sel_tag] <idx|all> [run] [subrun]
  (no args)  list available events
  idx:       1-based event index (1..10)
  all:       process all 10 events in parallel
  run:       run number stored in ROOT Trun tree (default 0)
  subrun:    subrun number (default 0)
  -s:        use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2 instead of work/evt<ID>/
```

**Input:** `input_files/2025f-mc-sp-frames.tar.bz2` (extracted to
`work/evt<ID>/sp-frames.tar.bz2` on first call). With `-s`, reads
`work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2`.

**Output** (in `work/evt<ID>[_<SEL_TAG>]/`):

| File | Description |
|---|---|
| `magnify-evt<ID>-anode{0,1}.root` | Magnify ROOT (T_bad, T_charge, …) |
| `sbnd-sp-frames-anode{0,1}.tar.bz2` | per-anode `gauss<N>`-tagged archives for Woodpecker |

**Jsonnet driven:** `wct-sp-to-magnify.jsonnet`

**Log:** `work/evt<ID>/wct_magnify_evt<ID>.log`; in `all` mode `work/.batch_magnify_evt<ID>.log`

---

### `run_select_evt.sh`

**Purpose:** Open the Woodpecker browser GUI to select a tick/channel ROI,
then merge the masked per-anode archives back into a combined `dnnsp`-tagged
archive that downstream pipeline scripts consume via `-s <sel_tag>`.

```
Usage: ./run_select_evt.sh [-a anode] <idx> <sel_tag>
  idx:      1-based event index
  sel_tag:  short label for this selection (e.g. sel1, tight, track5)
  -a:       restrict to one anode (0 or 1)
```

**Requires:** `run_sp_to_magnify_evt.sh` run first (produces
`work/evt<ID>/sbnd-sp-frames-anode*.tar.bz2`).

**External commands:**
1. `woodpecker select <archive> --detector sbnd --outdir <SELDIR> --prefix sbnd-sp-frames` (per anode)
2. `python3 merge_sel_archives.py <orig> <out> <evt_id> <masked...>`

Sets `MPLBACKEND=WebAgg`; prints SSH port-forward instructions.

**Output** (in `work/evt<ID>_<SEL_TAG>/input/`):

| File | Description |
|---|---|
| `sbnd-sp-frames-anode<N>.tar.bz2` | Woodpecker-masked per-anode archive |
| `selection-anode<N>.json` | tick/channel sidecar |
| `sp-frames.tar.bz2` | combined `dnnsp`-tagged archive for all downstream `-s <sel_tag>` runs |

---

### `run_img_evt.sh`

**Purpose:** Run 3D imaging on one event, producing per-anode active and masked
cluster `.npz` files.

```
Usage: ./run_img_evt.sh [-a anode] [-s sel_tag] <idx|all>
  (no args)  list available events
  all:       process all 10 events in parallel
  -a:        restrict to one anode (0 or 1)
  -s:        use work/evt<ID>_<SEL_TAG>/input/sp-frames.tar.bz2
```

**Input:** `work/evt<ID>[_<SEL_TAG>]/sp-frames.tar.bz2`

**Output** (in `work/evt<ID>[_<SEL_TAG>]/`):

| File | Description |
|---|---|
| `icluster-apa<N>-active.npz` | live-channel cluster arrays |
| `icluster-apa<N>-masked.npz` | dead-channel cluster arrays |

**Jsonnet driven:** `wct-img-all.jsonnet`

**TLAs forwarded:**

| TLA | Type | Value |
|---|---|---|
| `input` | str | path to `sp-frames.tar.bz2` |
| `anode_indices` | code | `[0,1]` or `[<N>]` with `-a` |
| `output_dir` | str | `work/evt<ID>[_<SEL_TAG>]/` |

**Log:** `work/evt<ID>/wct_img_evt<ID>[_a<N>].log`; in `all` mode `work/.batch_img_evt<ID>.log`

---

### `run_clus_evt.sh`

**Purpose:** Per-APA and all-APA blob clustering using `MultiAlgBlobClustering`.
Pre-validates `.npz` files and skips anodes with no active clusters so
`PointTreeMerging` does not stall.

```
Usage: ./run_clus_evt.sh [-a anode] [-s sel_tag] <idx|all> [run] [subrun]
  (no args)      list available events
  all:           process all 10 events in parallel
  run / subrun:  stored in Bee RSE metadata (default 0)
  -a:            restrict to one anode; skips all-APA stage
  -s:            use work/evt<ID>_<SEL_TAG>/ as working directory
```

**Input:** `work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-{active,masked}.npz`

**Output** (in `work/evt<ID>[_<SEL_TAG>]/`):

| File | Description |
|---|---|
| `mabc-apa<N>-face0.zip` | per-APA clustering Bee zip (includes point cloud) |
| `mabc-all-apa.zip` | all-APA combined clustering |
| `trash-*.tar.gz` | TensorFileSink dump (~29 bytes, harmless) |

**Jsonnet driven:** `wct-clustering.jsonnet`

**TLAs forwarded:**

| TLA | Type | Default | Description |
|---|---|---|---|
| `input` | str | — | directory with `icluster-apa*.npz` |
| `anode_indices` | code | `[0,1]` | anodes to process |
| `output_dir` | str | — | output directory |
| `run` / `subrun` / `event` | code | 0 / 0 / EVT_ID | Bee RSE metadata |
| `reality` | str | `'sim'` | `'sim'` or `'data'` |
| `DL` | code | 6.2 | longitudinal diffusion (cm²/s) |
| `DT` | code | 9.8 | transverse diffusion (cm²/s) |
| `lifetime` | code | 10 | electron lifetime (ms) |
| `driftSpeed` | code | 1.565 | drift speed (mm/µs) |

**Log:** `work/evt<ID>/wct_clus_evt<ID>[_a<N>].log`; in `all` mode `work/.batch_clus_evt<ID>.log`

---

### `run_bee_img_evt.sh`

**Purpose:** Convert imaging `.npz` cluster files to Bee JSON (one file per
anode), package as a zip, and upload to the Bee event-display server.

```
Usage: ./run_bee_img_evt.sh [-a anode] [-s sel_tag] <idx|all> [run] [subrun]
  (no args)  list available events
  all:       combine all events into one upload zip and do a single Bee upload
  -a:        restrict to one anode
  -s:        use work/evt<ID>_<SEL_TAG>/ as working directory
```

**Input:** `work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-active.npz` (skips
empty/22-byte files automatically).

**Single-event path** (`idx` is a number):
1. `python wct-img-2-bee.py <run> <subrun> <evt> <N>:<path> ...` → `data/0/0-apa<N>.json` + `upload.zip`
2. `mv upload.zip upload_evt<ID>[_<SEL>][_a<N>].zip`
3. `./upload-to-bee.sh <zipname>`

**`all`-mode path**:
- Invokes `wirecell-img bee-blobs` directly for each anode in parallel.
- Writes `data/<bee_idx>/<bee_idx>-apa<N>.json` (filename prefix matches
  directory index — required by Bee's `parse_pathname` to distinguish events).
- Produces `upload-batch.zip` and does a single upload.

**Output:**
- Single-event: `upload_evt<ID>[_<SEL_TAG>][_a<N>].zip` in `sbnd_xin/`
- All-mode: `upload-batch.zip` in `sbnd_xin/`

---

### `upload-to-bee.sh`

Symlink to `../../upload-to-bee.sh`. Uploads the given zip to the Bee server.
Called automatically by `run_bee_img_evt.sh`.

---

## Jsonnet entry-points

### `wct-sp-to-magnify.jsonnet`

Converts a `dnnsp`-tagged SP frame archive into per-anode Magnify ROOT files
and per-anode `gauss<N>`-tagged frame archives for Woodpecker.

**Imports:** `pgrapher/experiment/sbnd/simparams.jsonnet`,
`pgrapher/common/tools.jsonnet`, `magnify-sinks.jsonnet`

**TLAs:**

| TLA | Type | Default | Description |
|---|---|---|---|
| `input` | str | `'sp-frames.tar.bz2'` | input frame archive |
| `anode_indices` | code | `[0,1]` | anodes to process |
| `output_file_prefix` | str | `'magnify'` | prefix for `.root` outputs |
| `sp_frame_prefix` | str | `'sbnd-sp-frames'` | prefix for `.tar.bz2` outputs |
| `run` / `subrun` / `event` | code | 0 / 0 / 0 | stored in ROOT Trun tree |
| `nticks` | code | 3427 | total ticks (matches actual SP-frame readout); written to `Trun.total_time_bin` |

**Pipeline per anode:**
```
FrameFileSource(dnnsp)
  → FrameFanout (rename dnnsp→dnnsp<N> per anode)
  → ChannelSelector (5638-wide, keeps only anode N's channels)
  → tap: Retagger(dnnsp<N>→gauss<N>) → FrameFileSink(sbnd-sp-frames-anode<N>.tar.bz2)
  → Retagger(dnnsp<N>→[dnnsp<N>, threshold<N>])
  → MagnifySink(magnify-evt<ID>-anode<N>.root)
  → DumpFrames
```

---

### `wct-img-all.jsonnet`

Runs 3D imaging on both anodes, writing active and masked cluster arrays.

**Imports:** `pgrapher/experiment/sbnd/simparams.jsonnet`,
`pgrapher/experiment/sbnd/img.jsonnet`

**TLAs:**

| TLA | Type | Default | Description |
|---|---|---|---|
| `input` | str | `'sp-frames.tar.bz2'` | input frame archive |
| `anode_indices` | code | `[0,1]` | anodes to process |
| `output_dir` | str | `''` | directory for output `.npz` files |

**Pipeline per anode:**
```
FrameFileSource(dnnsp)
  → FrameFanout (rename dnnsp→gauss<N> and wiener<N>)
  → ChannelSelector(5638*N .. 5638*(N+1)-1)   ← defensive per-anode filter
  → img.per_anode(anode, 'multi-3view')
    ├─ port 0 → ClusterFileSink(icluster-apa<N>-active.npz)
    └─ port 1 → ClusterFileSink(icluster-apa<N>-masked.npz)
```

---

### `wct-clustering.jsonnet`

Runs per-APA and all-APA blob clustering using `MultiAlgBlobClustering`.

**Imports:** `pgrapher/experiment/sbnd/simparams.jsonnet` (with `lar` block
overlaid by TLAs), `clus.jsonnet`

**TLAs:** see `run_clus_evt.sh` table above.

**Pipeline:**
```
ClusterFileSource(icluster-apa<N>-active.npz)  ─┐
ClusterFileSource(icluster-apa<N>-masked.npz)  ─┤ clus.per_apa(anode<N>)
                                                  │   (PointTreeBuilding → MABC → per-APA zip)
                                                  ▼
                                          PointTreeMerging
                                                  │
                                          clus.all_apa(anodes)
                                                  │   (MABC → all-APA zip)
```

---

## Jsonnet helpers

### `clus.jsonnet`

Defines per-face, per-APA, and all-APA clustering subgraphs.
Imported by `wct-clustering.jsonnet`.

**Exposes:** `per_face(anode, face, dump)`, `per_apa(anode, dump)`,
`all_apa(anodes, dump)`, `detector_volumes(anodes, face)`

**Imports:** `pgrapher/common/clus.jsonnet` (provides clustering algorithms:
`pointed`, `live_dead`, `extend`, `regular`, `parallel_prolong`, `close`,
`extend_loop`, `separate`, `connect1`, `switch_scope`, `neutrino`, `isolated`)

Key locals: `time_offset = -200 us` (`clus.jsonnet:12`),
`drift_speed = 1.56 mm/us` (`clus.jsonnet:13`).
See [geometry-and-timing.md](geometry-and-timing.md).

### `magnify-sinks.jsonnet`

Builds per-anode `MagnifySink` pipeline nodes. Imported by
`wct-sp-to-magnify.jsonnet`. Returns `{ decon_pipe: [pipe_anode0, pipe_anode1] }`.
No `pgrapher/experiment/sbnd/` imports.

---

## Python helpers

### `wct-img-2-bee.py`

Called by `run_bee_img_evt.sh`. Constructs and executes `wirecell-img bee-blobs`
for each anode, then zips the output JSON files.

```
Usage: python wct-img-2-bee.py <run> <subrun> <event> <idx0>:<path0> [<idx1>:<path1> ...]
  idx:  anode index (0 = APA0 at x=-201.45 cm, 1 = APA1 at x=+201.45 cm)
  path: path to icluster-apa<N>-active.npz
```

Geometry arguments passed to `wirecell-img bee-blobs`:

| APA | `--x0` | `--speed` | `--t0` |
|---|---|---|---|
| 0 (x=-201.45 cm) | `-201.45*cm` | `-1.563*mm/us` | `200*us` |
| 1 (x=+201.45 cm) | `201.45*cm` | `+1.563*mm/us` | `200*us` |

Note `--t0 "200*us"` is the **positive** value even though `clus.jsonnet`
defines `time_offset = -200*us`. See [geometry-and-timing.md](geometry-and-timing.md).

**Output:** `data/0/0-apa<N>.json` (one per anode), then `upload.zip`. Used only
by the single-event path of `run_bee_img_evt.sh`; the `all`-mode path calls
`wirecell-img bee-blobs` directly to achieve correct per-event filename prefixes.

### `merge_sel_archives.py`

Called by `run_select_evt.sh` after Woodpecker selection. Loads the original
combined `sp-frames.tar.bz2`, overwrites rows for masked-anode channels with
the Woodpecker-masked values, and writes a new combined archive.

```
Usage: python3 merge_sel_archives.py <orig_archive> <out_archive> <evt_id> <masked1> [masked2 ...]
```

Channels for anodes that were not selected keep their original unmasked values.
