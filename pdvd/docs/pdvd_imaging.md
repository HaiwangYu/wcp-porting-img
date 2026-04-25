# ProtoDUNE-VD Imaging Pipeline Internals

See `pdvd.md` for directory layout, helper-script usage, and Bee upload
procedures. This file explains what the imaging jsonnet configs actually do —
per-APA/face structure, run/event metadata, dead-channel handling, and output
file labelling.

---

## Key source files

| File | Role |
|------|------|
| `run_img_evt.sh` | Shell driver: resolves input dir, sets `WIRECELL_PATH`, calls `wire-cell` |
| `wct-img-all.jsonnet` | Top-level entry point; builds per-APA graph, instantiates `Pgrapher` |
| `img.jsonnet` | Imaging pipeline library: pre_proc, slicing, tiling, solving, dump |
| `wcls-nf-sp-out.jsonnet` | Upstream NF+SP step (not run here, but produces the input frames) |

---

## Q1. How the code runs for different APAs and faces

### Top-level: 8 independent per-APA chains

`wct-img-all.jsonnet:37-93` builds one `FrameFileSource → img_maker.per_anode`
pipeline per selected anode, then hands them all to a single `Pgrapher`.

```
wire-cell (one invocation)
│
├── FrameFileSource(anode0) ──┐
│   protodune-sp-frames-anode0.tar.bz2
│                             └── per_anode(anode0) ── active sink (anode0)
│                                                   └── masked sink (anode0)
├── FrameFileSource(anode1) ──── per_anode(anode1) ── ...
│   ...
└── FrameFileSource(anode7) ──── per_anode(anode7) ── ...
```

Each chain is a **separate connected component**; `Pgrapher` runs all of them
without any inter-APA communication. The `anode_indices` TLA
(`wct-img-all.jsonnet:41`) selects which subset to run (default = `[0..7]`).
The APA identity number (`anode.data.ident`, values 0–7) determines which
input filename is read and tags the output filename.

### Per-APA pipeline structure (`img.jsonnet:304-355`)

Inside `per_anode(anode, pipe_type="multi")`:

```
FrameFileSource
     │
  pre_proc (CMMModifier → FrameMasking → ChargeErrorFrameEstimator)
     │
  FrameFanout (multiplicity=2)
     ├── active fork ──── multi_active_slicing_tiling ─── solving("full") ─── dump → clusters-...-ms-active.tar.gz
     └── masked fork ──── multi_masked_2view_slicing_tiling ─ clustering ─── dump → clusters-...-ms-masked.tar.gz
```

### Per-face split inside tiling (`img.jsonnet:122-157`)

Each slicing/tiling sub-pipeline runs `img.tiling()`, which internally splits
by face:

```
  MaskSlices (one slice stream)
       │
  SliceFanout (multiplicity=2)
    ├── GridTiling(face=0)
    └── GridTiling(face=1)
         │
  BlobSetSync (multiplicity=2)     ← merges face-0 and face-1 blobs
       │
  (on to solving / clustering)
```

`GridTiling` builds 2D wire-intersection tiles independently for each APA
face. `BlobSetSync` merges both faces back into a single `IBlobSet` stream.
This means **face 0 and face 1 are tiled in parallel within each slice**, but
there is no separate per-face output file — both faces contribute to the same
per-APA cluster tarball.

### Summary

| Axis | Mechanism | Granularity |
|------|-----------|-------------|
| Per-APA | Separate `FrameFileSource` + pipeline per anode ident | One per anode (0–7) |
| Per-face | `SliceFanout` → `GridTiling(face)` → `BlobSetSync` inside each tiling | Two faces merged per APA |
| Active / masked | `FrameFanout` → two separate forks with different slicing configs | Two output tarballs per APA |

---

## Q2. Run and event number propagation

### Evidence from actual files

Input frame tarball (`protodune-sp-frames-anode0.tar.bz2`) contains:

```
frame_gauss0_339870.npy
channels_gauss0_339870.npy
tickinfo_gauss0_339870.npy
frame_wiener0_339870.npy
channels_wiener0_339870.npy
tickinfo_wiener0_339870.npy
summary_wiener0_339870.npy
chanmask_bad_339870.npy
```

Output cluster tarball (`clusters-apa-anode0-ms-active.tar.gz`) contains:

```
cluster_339870_graph.json
```

The number `339870` is the **WCT frame ident**, which is inherited from
`art::Event::id().event()` by the upstream `wclsRawFrameSource`
(`wcls-nf-sp-out.jsonnet:76-86`). It flows unchanged through:

```
art::Event
    → wclsRawFrameSource  (frame.ident = event number)
    → NF → SP → FrameFileSink (embeds ident in .npy filenames)
    → FrameFileSource (reads ident back from filename)
    → imaging pipeline
    → ClusterFileSink (uses ident in cluster_<ident>_graph.json)
```

### What is and is not embedded

| Information | In frame tar `.npy` names | In cluster tar `.json` name | In tarball filename |
|-------------|--------------------------|------------------------------|---------------------|
| Event number | **Yes** (`_339870`) | **Yes** (`cluster_339870_`) | No |
| APA index | **Yes** (`gauss0`, `wiener0`) | — | **Yes** (`anode0`) |
| Run number | **No** | **No** | **No** |
| Sub-run number | **No** | **No** | **No** |

**Run number is never embedded in any WCT payload.** WCT treats the frame
ident as an opaque integer (typically = event number). Run and sub-run are
ART/LArSoft concepts that are not forwarded through `FrameFileSink`.

**Practical consequence:** a cluster tarball found in isolation identifies
its event (from the JSON filename inside) but not its run. The run is
traceable only via the directory path that `run_img_evt.sh` creates:
`work/<run_padded>_<evt>/clusters-apa-*.tar.gz`.

---

## Q3. Dead-channel handling

Dead-channel handling is implemented at three layers.

### Layer 1 — Upstream: `bad` channel mask production (in `wcls-nf-sp-out.jsonnet`)

`wcls-nf-sp-out.jsonnet:141-150` constructs one `OmniChannelNoiseDB`
(`chndb-base.jsonnet`) per anode, which feeds the noise-filter (`nf_maker`).
The noise filter identifies dead/noisy channels and records them as a `"bad"`
channel mask map. The downstream `FrameFileSink:208-223` writes this mask as
`chanmask_bad_<evt>.npy` into the SP frame tarball.

This mask is the starting point for all dead-channel-aware processing in the
imaging step.

### Layer 2 — Pre-processing in `img.jsonnet:11-96`

`img.pre_proc()` is a 3-node pipeline applied to every anode before any
slicing:

```
CMMModifier  ("bad" tag)
    │   Reorganizes dead-channel ranges using org_llimit/org_hlimit boundaries.
    │   Many additional veto parameters (cont_ch, veto_ch, dead_ch) exist but
    │   are currently commented out — available knobs for future tuning.
    │
FrameMasking  (cm_tag="bad", trace_tags=["gauss<N>","wiener<N>"])
    │   Zeros out gauss and wiener traces on all channels flagged as "bad".
    │
ChargeErrorFrameEstimator
        Computes per-channel charge uncertainty (gauss_error<N>) using
        microboone-charge-error.json.bz2 (fudge factors per plane: [2.31, 2.31, 1.1]).
        This uncertainty feeds MaskSlices' nthreshold threshold.
```

### Layer 3 — Multi-variant slicing/tiling (`img.jsonnet:160-184, 336-348`)

The `"multi"` pipeline mode (the default) creates **two parallel forks** after
`pre_proc`, each covering a different class of dead-plane scenarios:

#### Active fork — `multi_active_slicing_tiling` (span=4 ticks)

Handles regions with **≤1 dead wire plane per time slice**:

| Sub-pipeline | `active_planes` | `masked_planes` | Scenario |
|:---:|---|---|---|
| 0 | [0,1,2] | [] | All 3 planes live |
| 1 | [0,1] | [2] | Plane 2 (collection) dead |
| 2 | [1,2] | [0] | Plane 0 (induction-U) dead |
| 3 | [0,2] | [1] | Plane 1 (induction-V) dead |

`MaskSlices` handles the masked planes by excluding those wire hits from the
tiling constraint. All 4 sub-pipelines run through `img.tiling()` (per-face
split, see Q1) and their blobs are merged by `BlobSetMerge`. The merged set
proceeds to `img.solving("full")`:
`BlobClustering → GlobalGeomClustering → 3× (BlobGrouping → ChargeSolving →
LocalGeomClustering)` with two rounds of `ProjectionDeghosting` and
`InSliceDeghosting`. Output: **`clusters-apa-<aname>-ms-active.tar.gz`**.

#### Masked fork — `multi_masked_2view_slicing_tiling` (span=100 ticks)

Handles regions with **2 dead wire planes per time slice** (2-view imaging):

| Sub-pipeline | `dummy_planes` | `masked_planes` | Active plane |
|:---:|---|---|---|
| 0 | [2] | [0,1] | Plane 2 only |
| 1 | [0] | [1,2] | Plane 0 only |
| 2 | [1] | [0,2] | Plane 1 only |

`dummy_planes` inserts a synthetic parallel wire hit so `GridTiling` can still
form rectangular tile intersections in 2D. The coarser span (100 ticks ≈
50 mm) reflects that 2-view blobs are inherently less precise. No charge
solving is applied; only `BlobClustering` runs. Output:
**`clusters-apa-<aname>-ms-masked.tar.gz`**.

#### Overall coverage

Combined, the 7 slicing configurations (4 active + 3 masked) cover every
possible 0/1/2-dead-plane combination. Three-dead-plane cases are not
recoverable from SP data and are not attempted.

**Conclusion: YES**, the configuration comprehensively accounts for dead
channels using a multi-variant strategy that is specifically designed for the
ProtoDUNE-VD wire geometry.

---

## Q4. Run number in output files

### Current state

The output tarball name is formed in `img.jsonnet:289-301` (`dump()` function):

```jsonnet
local outname = if output_dir == '' then "clusters-apa-"+aname+".tar.gz"
                else output_dir+"/clusters-apa-"+aname+".tar.gz"
```

For the `"multi"` mode, `aname` is `anode.name + "-ms-active"` or
`"-ms-masked"`, giving e.g. `clusters-apa-anode0-ms-active.tar.gz`.

**Neither the tarball filename nor any file inside it contains the run
number.** The event number appears only inside the tarball as the suffix on
`cluster_<evt>_graph.json`.

### How run attribution works today

`run_img_evt.sh` creates a per-event work directory:

```
work/<run_padded>_<evt>/
    clusters-apa-anode0-ms-active.tar.gz
    clusters-apa-anode0-ms-masked.tar.gz
    ...
```

The six-digit padded run number and event are encoded in the **directory
name**, not the filenames. This is sufficient for traceability as long as the
files remain under `work/`.

### How to add run/event to the output filename (optional, not yet implemented)

The minimum-invasive approach requires changes to three files:

**1. `wct-img-all.jsonnet` — add TLAs**

```jsonnet
function(
  input_prefix = 'protodune-sp-frames',
  anode_indices = std.range(0, std.length(tools_all.anodes) - 1),
  output_dir = '',
  run = '',     // new: e.g. "039324"
  evt = '',     // new: e.g. "1"
)
  ...
  local img_maker = img(output_dir=output_dir, run=run, evt=evt);
```

**2. `img.jsonnet` — thread into `dump()`**

Change the outer function signature and `dump()`:

```jsonnet
function(output_dir='', run='', evt='') {
  ...
  dump :: function(anode, aname, drift_speed, output_dir='', run='', evt='') {
    local rse_tag = if run == '' then '' else '-run%s-evt%s' % [run, evt],
    local outname = if output_dir == ''
                    then 'clusters' + rse_tag + '-apa-' + aname + '.tar.gz'
                    else output_dir + '/clusters' + rse_tag + '-apa-' + aname + '.tar.gz',
    ...
```

When `run=''` (default), the filename is unchanged — backward compatible.

**3. `run_img_evt.sh` — pass the TLAs**

Add two `--tla-str` flags to the `wire-cell` call:

```sh
wire-cell \
    ...
    --tla-str "run=${RUN_PADDED}" \
    --tla-str "evt=${EVT}" \
    -c wct-img-all.jsonnet
```

With this in place, output files would be named e.g.
`clusters-run039324-evt1-apa-anode0-ms-active.tar.gz` — self-describing even
if moved out of `work/`.

### Alternative: keep current naming, rely on directory layout

If modifying the jsonnet configs is undesirable, the work-dir convention
(`work/<run>_<evt>/`) already provides run attribution and the clustering
helper (`run_clus_evt.sh`) knows how to find files by that layout. This is
simpler and requires no code changes.

The decision is left for a follow-up once the pipeline is validated end-to-end.

---

## Shared cfg vs workspace — active-fork design difference

The **workspace** `pdvd/img.jsonnet` and the **shared toolkit cfg**
`cfg/pgrapher/experiment/dune-vd/img.jsonnet` implement the same
conceptual pipeline but differ in how `imgpipe()` selects the active fork:

**Workspace `pdvd/img.jsonnet` (lines 333–344)** — bug-free design:
```jsonnet
else {
    local active_fork = g.pipeline([
        img.multi_active_slicing_tiling(...),   // always 4-branch
        img.solving(...),
        ...
    ]),
    ...
```
Any `pipe_type` value that does not match `"single"`, `"pdhd1"`,
`"active"`, or `"masked"` falls to the `else` and unconditionally runs
`multi_active_slicing_tiling`. The default `"multi"` always lands here.
No string comparison gates the 4-branch active fork.

**Shared `cfg/pgrapher/experiment/dune-vd/img.jsonnet` (line 324,
fixed 2026-04-25)** — was buggy:
```jsonnet
// BEFORE (buggy):
local st = if multi_slicing == "multi-2view"
    then img.multi_active_slicing_tiling(...)
    else g.pipeline([img.slicing(..., active_planes=[0,1,2]), img.tiling(...)]),
```
The call site `cfg/pgrapher/experiment/dune-vd/wct-depo-sim-img-fans.jsonnet:102`
passes `"multi-3view"`, which failed the `== "multi-2view"` test and
silently fell through to the single 3-plane `else` branch. All 2-plane
active variants (U+V, V+W, U+W) were never built, so tracks crossing a
dead-wire region were absent from the active cluster output.

**Fix**: condition extended to
`if multi_slicing == "multi-2view" || multi_slicing == "multi-3view"`.
Unaffected call sites in `wct-sim-fans.jsonnet` and
`wcls-sim-drift-simchannel-nf-sp-img.jsonnet` use the default
`"single"` mode and were not affected.

The identical bug and fix were applied to
`cfg/pgrapher/experiment/sbnd/img.jsonnet:342` in the same commit.

---

## Quick reference: key file/line index

| What | File | Lines |
|------|------|-------|
| TLA definitions (input_prefix, anode_indices, output_dir) | `wct-img-all.jsonnet` | 37–44 |
| Per-APA pipeline construction loop | `wct-img-all.jsonnet` | 52–66 |
| `pre_proc` (CMMModifier + FrameMasking + ChargeErrorEstimator) | `img.jsonnet` | 11–96 |
| `tiling` with per-face SliceFanout/GridTiling/BlobSetSync | `img.jsonnet` | 122–157 |
| `multi_active_slicing_tiling` (4-variant, span=4) | `img.jsonnet` | 160–170 |
| `multi_masked_2view_slicing_tiling` (3-variant, span=100…500) | `img.jsonnet` | 173–184 |
| `solving("full")` pipeline definition | `img.jsonnet` | 198–287 |
| `dump()` — output tarball naming | `img.jsonnet` | 289–301 |
| Default pipe_type selection (`"multi"`) | `img.jsonnet` | 336–355 |
| Upstream FrameFileSink (writes SP frames + bad mask) | `wcls-nf-sp-out.jsonnet` | 208–223 |
| Upstream OmniChannelNoiseDB / nf_maker | `wcls-nf-sp-out.jsonnet` | 141–150 |
