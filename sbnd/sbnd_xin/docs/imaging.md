# 3D Imaging Stage — `run_img_evt.sh` (`sbnd_xin/`)

> For per-script CLI options see **[scripts.md](scripts.md)**.
> For geometry / timing constants see **[geometry-and-timing.md](geometry-and-timing.md)**.
> For the full pipeline overview see **[sbnd.md](sbnd.md)**.

This document explains the imaging stage of the SBND standalone pipeline:
what algorithm runs, how the configuration drives it, and what the output
files contain. The imaging stage runs **no signal processing** — input is
already DNN-SP–deconvolved frames dumped from LArSoft.

---

## Driver script: `run_img_evt.sh`

```
./run_img_evt.sh [-a anode] [-s sel_tag] <idx>
```

| Option | Meaning |
|---|---|
| `<idx>` | 1-based event index (1–10); maps to event IDs below |
| `-a 0\|1` | restrict to one anode; omit for both `[0,1]` |
| `-s <tag>` | use Woodpecker-masked input from `run_select_evt.sh` |

Event mapping (`run_img_evt.sh:16`):

| idx | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| EVT_ID | 2 | 9 | 11 | 12 | 14 | 18 | 31 | 35 | 41 | 42 |

**Input path** (`run_img_evt.sh:50–56`):

| Mode | SP archive path |
|---|---|
| Normal | `work/evt<ID>/sp-frames.tar.bz2` |
| Selection (`-s <tag>`) | `work/evt<ID>_<tag>/input/sp-frames.tar.bz2` |

Both are produced upstream by `run_sp_to_magnify_evt.sh` (normal) or
`run_select_evt.sh` + `merge_sel_archives.py` (selection).

**`wire-cell` invocation** (`run_img_evt.sh:83–90`):

```sh
wire-cell \
    -l stderr \
    -l "${LOG}:debug" \
    -L debug \
    --tla-str  "input=${SP_ARCHIVE}" \
    --tla-code "anode_indices=${ANODE_CODE}" \
    --tla-str  "output_dir=${WORKDIR}" \
    -c wct-img-all.jsonnet
```

**Outputs**: `work/evt<ID>[_<tag>]/icluster-apa{0,1}-{active,masked}.npz`
**Log**: `work/evt<ID>[_<tag>]/wct_img_evt<ID>[_a<N>].log` (debug level)

---

## Top-level config: `wct-img-all.jsonnet`

### Function signature

```jsonnet
function(
  input         = 'sp-frames.tar.bz2',   // --tla-str
  anode_indices = [0, 1],                // --tla-code
  output_dir    = '',                    // --tla-str
)
```
(`wct-img-all.jsonnet:26–30`)

### Graph structure

```
FrameFileSource(tag='dnnsp')                    // reads sp-frames.tar.bz2 directly
    │
    ▼ FrameFanout  (one branch per anode)
    │   rule N: {frame: '.*'→'origN', trace: dnnsp→['gaussN','wienerN']}
    │
    ├─ [APA 0] chsel_correct0 → img_maker.per_anode(anode0, 'multi-3view')
    │               ├─ port 0 → ClusterFileSink → icluster-apa0-active.npz
    │               └─ port 1 → ClusterFileSink → icluster-apa0-masked.npz
    │
    └─ [APA 1] chsel_correct1 → img_maker.per_anode(anode1, 'multi-3view')
                    ├─ port 0 → ClusterFileSink → icluster-apa1-active.npz
                    └─ port 1 → ClusterFileSink → icluster-apa1-masked.npz
```

### The FrameFanout retag trick

(`wct-img-all.jsonnet:86–92`) SBND DNN-SP produces a single `dnnsp` trace
tag. The shared `experiment/sbnd/img.jsonnet` imaging graph was written for
the uboone-style pipeline that expects distinct `gauss<N>` (charge) and
`wiener<N>` (quality/threshold reference) traces per anode. The FrameFanout
rule aliases the same DNN-SP trace under both names:

```jsonnet
trace: { dnnsp: ['gauss0', 'wiener0'] }   // for APA 0
trace: { dnnsp: ['gauss1', 'wiener1'] }   // for APA 1
```

This is not needed in PDHD/PDVD, where separate noise-filtering and
signal-processing steps produce distinct gauss/wiener tags.

### The `g.intern` two-port wiring

(`wct-img-all.jsonnet:74–82`) `per_anode(...)` ends in a `g.fan.fanout`
that emits port 0 (active clusters) and port 1 (masked clusters). A plain
`g.pipeline` can only attach a single tail node, so `g.intern` is used to
wire both ports explicitly to their respective `ClusterFileSink` nodes.

### Defensive `chsel_correct<N>`

(`wct-img-all.jsonnet:44–52`) Each branch adds a `ChannelSelector` that
keeps only channels `5638*N .. 5638*(N+1)-1` with tags `gauss<N>` and
`wiener<N>`. This is redundant with the same selector inside the shared
imaging graph (fixed in the 5632→5638 patch) but prevents any future
regression of the shared constant from silently corrupting the branch.

### Plugins

(`wct-img-all.jsonnet:111–119`)
`WireCellGen, WireCellPgraph, WireCellSio, WireCellSigProc,
WireCellImg, WireCellClus, WireCellRoot`

---

## Per-anode imaging algorithm

Defined in `cfg/pgrapher/experiment/sbnd/img.jsonnet`. Called as
`img_maker.per_anode(anode, 'multi-3view', add_dump=false)` which
resolves to (`img.jsonnet:361–364`):

```
pre_proc(anode)  →  imgpipe(anode, 'multi-3view', add_dump=false)
```

### Pre-processing (`pre_proc`) — IFrame → IFrame

(`img.jsonnet:16–130`) Sequence of four IFrame-to-IFrame components:

```
ChannelSelector (chsel_pipes)
    → CMMModifier (cmm_mod)
    → FrameMasking (frame_masking)
    → ChargeErrorFrameEstimator (charge_err)
```

**1. `ChannelSelector` (chsel_pipes)** (`img.jsonnet:41–51`)

Keeps only the 5638 channels belonging to this APA and the two trace tags:

```jsonnet
channels: std.range(5638 * anode.data.ident, 5638 * (anode.data.ident + 1) - 1),
tags: ['gauss<N>', 'wiener<N>'],
```

See [geometry-and-timing.md §"Per-APA channel count"](geometry-and-timing.md)
for the history of the 5632 production bug.

**2. `CMMModifier`** (`img.jsonnet:67–91`)

Organises the `bad` channel-mask map (CMM) by expanding bad-channel ranges
using the `gauss<N>` charge frame. The boundary `org_hlimit: [3427]` ensures
the full readout window is covered (`img.jsonnet:89`).

**3. `FrameMasking`** (`img.jsonnet:118–127`)

Zeros out waveform samples on `bad` channels for both `gauss<N>` and
`wiener<N>`. Prevents bad-channel charge from leaking into the slicer.

**4. `ChargeErrorFrameEstimator`** (`img.jsonnet:26–38`)

Produces `gauss_error<N>` from `gauss<N>` using a pre-computed
`WaveformMap` loaded from `sbnd-charge-error.json.bz2`:

```jsonnet
rebin: 4,                         // rebin factor before applying waveform map
fudge_factors: [2.31, 2.31, 1.1], // per-plane (U, V, W) scale factors
time_limits: [12, 800],           // in rebin-4 ticks ≈ raw ticks 48–3200
```

The error estimate is consumed by `MaskSlices` as `error_tag` during
slicing.

> **Note**: A `MagnifySink` debug node (`img.jsonnet:53–65`) and a
> `FrameQualityTagging` node (`img.jsonnet:93–116`) are defined in the
> file but are **not part of the active pipeline** (`img.jsonnet:129`).

---

### Imaging fork — `multi-3view` mode

After pre-processing, `imgpipe` with `multi_slicing='multi-3view'` splits
into two parallel branches via `g.fan.fanout('FrameFanout', ...)`:
(`img.jsonnet:341–358`)

```
pre_proc output (IFrame)
    │
    ├─ active_fork → port 0 (ICluster, with solved charge)
    └─ masked_fork → port 1 (ICluster, geometry only)
```

---

### Active fork — `multi-3view` slicing + tiling + solving

(`img.jsonnet:347–351`, `multi_active_slicing_tiling` at line 178)

**Step 1 — slicing fanpipe** (4 branches, merged by `BlobSetMerge`)

Each branch runs one `MaskSlices` → `GridTiling` with a different plane
combination:

| Branch | `active_planes` | `masked_planes` | Coverage |
|---|---|---|---|
| 0 | [0,1,2] | [] | all three planes active |
| 1 | [0,1] | [2] | U+V only, W masked |
| 2 | [1,2] | [0] | V+W only, U masked |
| 3 | [0,2] | [1] | U+W only, V masked |

(`img.jsonnet:179–180`)

`MaskSlices` parameters (shared across all 4 branches, `img.jsonnet:133–155`):

```jsonnet
tick_span:    4,           // 4 ticks × 0.5 µs/tick = 2 µs per slice
min_tbin:     0,
max_tbin:     3427,        // full SBND readout window (was 3400)
nthreshold:   [3.6, 3.6, 3.6],   // per-plane signal threshold
wiener_tag:   'wiener<N>',
summary_tag:  'wiener<N>',
charge_tag:   'gauss<N>',
error_tag:    'gauss_error<N>',
```

`GridTiling` (`img.jsonnet:158–175`): sets `face = anode.data.ident`
(SBND-specific — one face per anode, unlike some multi-face detectors).

**Step 2 — solving** (`img.jsonnet:216–301`, active pipeline at line 300)

The "simple-solving" pipeline (the richer multi-round chain on line 299 is
commented out):

```
BlobClustering (policy='uboone')
    → BlobGrouping
    → ChargeSolving (weighting='uniform', solve_config='uboone', whiten=true)
    → LocalGeomClustering
    → ChargeSolving (weighting='uboone', solve_config='uboone', whiten=true)
    → InSliceDeghosting (config_round=1)
    → GlobalGeomClustering (policy='uboone')
```

The commented-out richer chain includes multiple rounds of
`ProjectionDeghosting` and `InSliceDeghosting` — this is a tuning knob
for future refinement.

---

### Masked fork — 2-view dummy slicing

(`img.jsonnet:352–356`, `multi_masked_2view_slicing_tiling` at line 191)

**Step 1 — slicing fanpipe** (3 branches, merged by `BlobSetMerge`)

Each branch uses one plane as a `dummy` (geometry scaffold only) and the
other two as `masked`:

| Branch | `dummy_planes` | `masked_planes` |
|---|---|---|
| 0 | [2] (W dummy) | [0,1] (U+V masked) |
| 1 | [0] (U dummy) | [1,2] (V+W masked) |
| 2 | [1] (V dummy) | [0,2] (U+W masked) |

(`img.jsonnet:192–193`)

`MaskSlices` is called with `active_planes=[]` and `span=500`
(500 ticks × 0.5 µs/tick = 250 µs per slice — much coarser than the
active fork's 4-tick span).

**Step 2 — clustering only** (`img.jsonnet:207–213`)

```
BlobClustering (spans=1.0, policy='uboone')
```

No charge solving. Output blobs carry geometry (wire-pair intersections) but
no calibrated charge.

---

## Active vs masked outputs — what they mean

| | Active (`-active.npz`) | Masked (`-masked.npz`) |
|---|---|---|
| Signal requirement | ≥2 planes with real signal above threshold | one plane treated as geometric dummy; other two "masked" |
| Slice span | 4 ticks (2 µs) | 500 ticks (250 µs) |
| Charge values | Yes — full solve including deghosting | No — geometric blobs only |
| Downstream use | Primary clustering input; Bee display | Supplements active in dead/noisy regions |

The downstream clustering step (`run_clus_evt.sh` → `MultiAlgBlobClustering`)
consumes both files together.

---

## Tags reference

| Tag | Producer | Consumer | Role |
|---|---|---|---|
| `dnnsp` | upstream `wcls-sp-dump.fcl` | `FrameFileSource`, `FrameFanout` | raw input traces from DNN-SP |
| `gauss<N>` | FrameFanout retag of `dnnsp` | `chsel_pipes`, `CMMModifier`, `FrameMasking`, `ChargeErrorFrameEstimator`, `MaskSlices.charge_tag` | per-anode charge waveforms |
| `wiener<N>` | FrameFanout retag of `dnnsp` | `chsel_pipes`, `FrameMasking`, `MaskSlices.wiener_tag`/`summary_tag` | per-anode quality/threshold reference |
| `gauss_error<N>` | `ChargeErrorFrameEstimator` | `MaskSlices.error_tag` | per-tick charge uncertainty |
| `bad` | upstream (`chanmask_bad_<EVT>`) | `CMMModifier`, `FrameMasking` | bad-channel mask (CMM) |
| `orig<N>` | FrameFanout frame rename | — | frame-level tag (not used by any component) |

---

## TLA and embedded constants

| Parameter | Value / TLA | Where set | Effect |
|---|---|---|---|
| `input` | `--tla-str input=<path>` | `wct-img-all.jsonnet:27` | SP frame archive path |
| `anode_indices` | `--tla-code anode_indices=[0,1]` | `wct-img-all.jsonnet:28` | which APAs to process |
| `output_dir` | `--tla-str output_dir=<path>` | `wct-img-all.jsonnet:29` | directory for output `.npz` files |
| channels per APA | `5638` (hard-coded) | `img.jsonnet:47`, `wct-img-all.jsonnet:48` | SBND: 1984 U + 1984 V + 1670 W |
| `max_tbin` | `3427` | `img.jsonnet:145` | SBND DAQ readout window (was 3400) |
| active `tick_span` | `4` | `img.jsonnet:178`, `multi_active…` default | 2 µs per slice |
| masked `span` | `500` | `img.jsonnet:191`, `multi_masked…` default | 250 µs per slice |
| `nthreshold` | `[3.6, 3.6, 3.6]` | `img.jsonnet:150` | per-plane ADC threshold for active slicing |
| `fudge_factors` | `[2.31, 2.31, 1.1]` | `img.jsonnet:34` | U/V/W charge-error scale |
| `time_limits` | `[12, 800]` (rebin-4 ticks) | `img.jsonnet:35` | charge-error estimator tick range |

---

## Input format — `sp-frames.tar.bz2`

`FrameFileSource` reads the archive directly (no prior extraction needed).
See [sbnd.md §"Input"](sbnd.md#input) for the canonical table; summary:

| File inside archive | Shape | Tag |
|---|---|---|
| `frame_dnnsp_<EVT>.npy` | (11276, 3427) | `dnnsp` |
| `channels_dnnsp_<EVT>.npy` | (11276,) | channel IDs |
| `tickinfo_dnnsp_<EVT>.npy` | (3,) | tick0, period, nticks |
| `summary_dnnsp_<EVT>.npy` | (11276,) | per-channel SP summary |
| `chanmask_bad_<EVT>.npy` | varies | `bad` CMM |

Selection-mode archives (`work/evt<ID>_<tag>/input/sp-frames.tar.bz2`) have
the same schema with tick/channel masking already applied by
`merge_sel_archives.py`.

---

## Output format — `icluster-apa<N>-*.npz`

Produced by `ClusterFileSink` with `format: 'numpy'`
(`wct-img-all.jsonnet:62–66`). Each `.npz` is a flattened dump of the
ICluster graph for one APA, one pass (active or masked).

### Structure

The file contains one pair of arrays per cluster index `i`:

```
cluster_<i>_nodes.npy   — node descriptor table
cluster_<i>_edges.npy   — directed edge pairs (src_idx, dst_idx)
```

### Node codes and per-code columns

| Code | Meaning | Key data columns |
|---|---|---|
| `s` | slice | start tick, tick span, total charge |
| `b` | blob | face, slice index, wire-pair bounds per plane; charge value + uncertainty (active) or zero (masked) |
| `m` | measure | per-plane charge measurement (active only) |
| `w` | wire | plane index, wire index |
| `c` | channel | channel ident |

Edges encode the cluster graph: blob↔slice, blob↔measure (active),
measure↔wire, wire↔channel.

Authoritative column layout:
`<toolkit>/aux/inc/WireCellAux/ClusterArrays.h`

### Quick inspection

```python
import numpy as np
d = np.load('work/evt2/icluster-apa0-active.npz')
print(list(d.keys())[:10])   # e.g. ['cluster_0_nodes', 'cluster_0_edges', ...]
```

> **Empty file**: a run with no blobs produces a 22-byte `.npz` (zip header
> only, no arrays). Downstream scripts detect and skip these.
> See [sbnd.md §"Known gotchas"](sbnd.md#known-gotchas).

---

## Notable details and gotchas

- **`add_dump=false`** — `per_anode` is called with `add_dump=false`
  (`wct-img-all.jsonnet:37`). This suppresses the inner `img.dump` node
  (`img.jsonnet:303–313`, which writes `clusters-apa-*.tar.gz` in JSON
  format). Only the top-level numpy `ClusterFileSink` nodes fire.

- **`experiment/sbnd/img.jsonnet` is self-contained** — it does not import
  `pgrapher/common/img.jsonnet` (unlike some PDHD/PDVD configs). All
  slicing, tiling, solving, and clustering helper functions are defined
  locally in that file.

- **`face = anode.data.ident`** (`img.jsonnet:167`) — SBND uses one face per
  anode (`GridTiling` face = 0 for APA0, 1 for APA1). The generic
  multi-face loop used in other detectors is commented out.

- **Richer deghosting chain commented out** (`img.jsonnet:299`) — the
  active pipeline today is "simple-solving" (one round of `BlobClustering →
  BlobGrouping → ChargeSolving → LocalGeomClustering → ChargeSolving →
  InSliceDeghosting → GlobalGeomClustering`). The multi-round
  `ProjectionDeghosting` chain is in the file for future use.

- **`FrameQualityTagging` not in pipeline** (`img.jsonnet:93–116`) — the
  node is defined (with `min_time: 3180`, `max_time: 7870`) but is not
  connected in the active pre_proc pipeline (`img.jsonnet:129`).

- **Geometry constants** — 5638 channels per APA and 3427-tick frame
  length were both production bugs in the shared configs that have been
  fixed on this branch. See
  [geometry-and-timing.md](geometry-and-timing.md) for details.
