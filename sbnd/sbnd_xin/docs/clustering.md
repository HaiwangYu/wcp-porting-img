# Blob Clustering (`run_clus_evt.sh`)

> For pipeline overview see **[sbnd.md](sbnd.md)**.
> For per-script CLI reference see **[scripts.md](scripts.md)**.
> For geometry / timing constants see **[geometry-and-timing.md](geometry-and-timing.md)**.
> For the upstream imaging stage see **[imaging.md](imaging.md)**.

## Scope

This document covers the blob-clustering stage driven by `run_clus_evt.sh`.
It reads the per-anode imaging clusters produced by `run_img_evt.sh`
(`icluster-apa<N>-active.npz`, `icluster-apa<N>-masked.npz`) and produces
Bee-format `.zip` archives ready for direct upload — **no separate
`run_bee_*` step is needed for clustering output**.

The stage runs in two sequential phases:

1. **Per-APA (single-TPC) clustering** — for each anode: build a
   live+dead point-cloud tree, then run `MultiAlgBlobClustering` with a
   10-step algorithm pipeline in single-TPC geometry.
2. **All-APA (multi-TPC) clustering** — merge the per-APA trees via
   `PointTreeMerging`, apply a T0-coordinate correction (`switch_scope`),
   then run `MultiAlgBlobClustering` with a 10-step all-TPC pipeline
   including neutrino-candidate and isolated-cluster passes.

---

## Driver script: `run_clus_evt.sh`

```
./run_clus_evt.sh [-a anode] [-s sel_tag] <idx> [run] [subrun]
```

| idx | Event ID |
|-----|----------|
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

(`run_clus_evt.sh:18`)

**Input directory** (`run_clus_evt.sh:55-59`):
`work/evt<ID>[_<SEL_TAG>]/icluster-apa{0,1}-{active,masked}.npz`

**Empty-npz guard** (`run_clus_evt.sh:65-90`): before launching `wire-cell`,
the script calls `npz_has_content()` for each candidate anode.
`PointTreeMerging` is a multi-input fan-in — if any branch reaches EOS
at call 0 (as a 22-byte zero-array zip does), the fan-in stalls.
The guard drops that APA from `ANODE_CODE` and issues a `WARNING`; if
_all_ APAs are empty it exits with an error.

**`wire-cell` invocation** (`run_clus_evt.sh:111-126`):

```sh
wire-cell \
  -l stderr -l "${LOG}:debug" -L debug \
  --tla-str  "input=${WORKDIR}" \
  --tla-code "anode_indices=${ANODE_CODE}" \
  --tla-str  "output_dir=${WORKDIR}" \
  --tla-code "run=${RUN}" --tla-code "subrun=${SUBRUN}" --tla-code "event=${EVT_ID}" \
  --tla-str  "reality=sim" \
  --tla-code "DL=6.2" --tla-code "DT=9.8" \
  --tla-code "lifetime=10" --tla-code "driftSpeed=1.565" \
  -c wct-clustering.jsonnet
```

**Outputs** (in `work/evt<ID>[_<SEL_TAG>]/`):

| File | Stage | Description |
|---|---|---|
| `mabc-apa<N>-face0.zip` | per-APA | Bee zip: single `clustering` point set |
| `mabc-all-apa.zip` | all-APA | Bee zip: `img` + `clustering` point sets |
| `trash-apa<N>-face0.tar.gz` | per-APA | `TensorFileSink` placeholder (~29 B, harmless) |
| `trash-all-apa.tar.gz` | all-APA | same |
| `wct_clus_evt<ID>[_a<N>].log` | – | debug log |

---

## Top-level config: `wct-clustering.jsonnet`

### Physics TLA overlay (`wct-clustering.jsonnet:36-43`)

```jsonnet
local params = base {
    lar: super.lar {
        DL:          DL * wc.cm2 / wc.s,       // longitudinal diffusion
        DT:          DT * wc.cm2 / wc.s,       // transverse diffusion
        lifetime:    lifetime * wc.ms,
        drift_speed: driftSpeed * wc.mm / wc.us,
    },
};
```

This overlays four physics parameters onto `pgrapher/experiment/sbnd/simparams.jsonnet`
at instantiation time, so every downstream component that imports `params`
uses the TLA values.

### Graph structure

```
icluster-apa0-active.npz  ─►  ClusterFileSource ──┐
icluster-apa0-masked.npz  ─►  ClusterFileSource ──┘─► clus_per_face (APA 0) ──┐
                                                                                │
icluster-apa1-active.npz  ─►  ClusterFileSource ──┐                           ├─► PointTreeMerging
icluster-apa1-masked.npz  ─►  ClusterFileSource ──┘─► clus_per_face (APA 1) ──┘        │
                                                                                         ▼
                                                                              clus_all_apa (all-APA)
                                                                                         │
                                                         mabc-apa0-face0.zip  ◄──────────┤
                                                         mabc-apa1-face0.zip  ◄──────────┤
                                                         mabc-all-apa.zip     ◄──────────┘
```

Two `ClusterFileSource` nodes per APA (`wct-clustering.jsonnet:49-61`) read
the active and masked `.npz` files. Each is wired via `g.intern`
(`wct-clustering.jsonnet:72-80`) as port 0 (active = live) and port 1
(masked = dead) of `PointTreeBuilding` inside `clus_per_face`.
Each per-APA pipeline's output is then forwarded to `PointTreeMerging`
in `clus_all_apa` (`wct-clustering.jsonnet:84-89`).

**Plugins** (`wct-clustering.jsonnet:99-100`):
`WireCellGen`, `WireCellPgraph`, `WireCellSio`, `WireCellSigProc`,
`WireCellImg`, `WireCellRoot`, `WireCellTbb`, `WireCellClus`.

---

## Per-APA stage — `clus_per_face` (single-TPC clustering)

Defined in `clus.jsonnet:96-176`. One pipeline per APA; uses
`face=0` always because SBND has one face per APA (`clus.jsonnet:270`).

```
ClusterFileSource(active) ──┐
                            ├──► PointTreeBuilding ──► MultiAlgBlobClustering ──► mabc-apa<N>-face0.zip
ClusterFileSource(masked) ──┘   (multiplicity=2,     (10-step per-APA pipeline)
                                 tags=['live','dead'])
```

### BlobSamplers (`clus.jsonnet:77-94`)

`PointTreeBuilding` takes two sampler references that convert 2D blobs
into 3D point clouds before clustering begins.

| Field | Sampler | C++ strategy | What it produces | Used for |
|---|---|---|---|---|
| `'3d'` | `bs_live_face` | `stepped` | Sub-grid of wire-crossing points (step ≈ N_wire/12, min 3); extras: `wire_index`, `charge_val`, `charge_unc`, `wpid` | Live (active) blobs |
| `'dead'` | `bs_dead_face` | `center` | Single point at geometric center of blob's wire-crossing polygon | Dead (masked) blobs |

(`BlobSampler.cxx`: Center @ line 452, Stepped @ line 703)

`drift_speed = 1.56 mm/µs` and `time_offset = -200 µs` (`clus.jsonnet:12-13`)
drive the t→x conversion inside `bs_live_face`. These values are
**hard-coded in `clus.jsonnet`** and are not overridden by the `driftSpeed`
TLA — see [geometry-and-timing.md § "Drift speed"](geometry-and-timing.md)
for the three-value discrepancy story.

### `PointTreeBuilding` (`clus.jsonnet:101-112`)

`IClusterFaninTensorSet` (multiplicity=2, tags `['live','dead']`):
runs both samplers over the respective input ICluster sets and builds a
hierarchical point-cloud tree:

```
Grouping
  └─ Cluster (per WCT cluster ID)
       └─ Blob (each imaging blob)
            └─ Sampled 3D PC (stepped for live, center for dead)
                 + charge projections, wire-index ranges
```

The tree is serialized to `ITensorSet` at `inpath/outpath: 'pointtrees/%d'`.
`anode` and `detector_volumes` (FV bounds for `a0f0pA` or `a1f0pA`)
are attached for downstream spatial filtering.

### `MultiAlgBlobClustering` — per-APA (`clus.jsonnet:120-164`)

**Key insight**: MABC is a single C++ `ITensorSetFilter` component
(`MultiAlgBlobClustering.cxx:1663-1712`). Its `pipeline:` array names
`IEnsembleVisitor` instances; MABC calls `visit()` on each in sequence
over the same in-memory `Grouping`/`Cluster`/`Blob` tree — **not** as
separate WCT pnodes. Each `cm.*(...)` call in `clus.jsonnet` produces one
config node (`Clustering*`) that MABC loads at configure time.

**Per-APA `cm_pipeline`** (`clus.jsonnet:120-131`), in execution order:

| # | jsonnet call | C++ class | Key params | Purpose |
|---|---|---|---|---|
| 1 | `cm.pointed()` | `ClusteringPointed` | – | Mark/select "pointed" clusters within named groupings. |
| 2 | `cm.live_dead(dead_live_overlap_offset=2)` | `ClusteringLiveDead` | overlap=2 ticks | Merge live blobs with overlapping dead-channel regions. |
| 3 | `cm.extend(flag=4, length_cut=60cm, length_2_cut=15cm, num_dead_try=1)` | `ClusteringExtend` | flag=4 | Extend cluster trajectories along their direction; dead-region-aware. |
| 4 | `cm.regular(name='-one', length_cut=60cm, flag_enable_extend=false)` | `ClusteringRegular` | – | Pairwise merging within 60 cm, no extension. |
| 5 | `cm.regular(name='_two', length_cut=30cm, flag_enable_extend=true)` | `ClusteringRegular` | with extend | Tighter pairwise merging with extension. |
| 6 | `cm.parallel_prolong(length_cut=35cm)` | `ClusteringParallelProlong` | – | Merge parallel/prolonged track segments. |
| 7 | `cm.close(length_cut=1.2cm)` | `ClusteringClose` | – | Merge spatially adjacent clusters. |
| 8 | `cm.extend_loop(num_try=3)` | `ClusteringExtendLoop` | – | Iteratively re-run extension until convergence. |
| 9 | `cm.separate(use_ctpc=true)` | `ClusteringSeparate` | use CT-pc | Split over-merged clusters via charge/time point cloud. |
| 10 | `cm.connect1()` | `ClusteringConnect1` | – | First-pass connectivity using detector-volume info. |

(Source line numbers in `cfg/pgrapher/common/clus.jsonnet`:
`pointed`=231, `live_dead`=253, `extend`=262, `regular`=276,
`parallel_prolong`=286, `close`=295, `extend_loop`=303,
`separate`=312, `connect1`=321.)

**Bee output** (`clus.jsonnet:154-161`): one `bee_points_sets` entry:

| `name` | `algorithm` | `coords` | `individual` |
|---|---|---|---|
| `clustering` | `clustering` | `['x', 'y', 'z']` | `true` (per-cluster files) |

MABC writes `mabc-apa<N>-face0.zip` directly; a `TensorFileSink`
with `dump_mode=true` follows to drain the output stream into
`trash-apa<N>-face0.tar.gz` (discardable placeholder).

---

## All-APA stage — `clus_all_apa` (multi-TPC clustering)

Defined in `clus.jsonnet:178-263`.

```
clus_per_face[apa0] ──┐
                      ├──► PointTreeMerging ──► MultiAlgBlobClustering ──► mabc-all-apa.zip
clus_per_face[apa1] ──┘    (multiplicity=2)     (10-step all-APA pipeline)
```

### `PointTreeMerging` (`clus.jsonnet:180-188`)

`ITensorSetFanin` with `multiplicity=nanodes`: receives one serialized
PC tree per APA (each already containing live+dead clusters) and concatenates
them into a single `ITensorSet` so MABC can see all TPCs as one global event.
This is what enables cross-APA cluster merging — without `PointTreeMerging`
the all-APA MABC would process each TPC independently.

### Coordinate-scope switch — why two `clustering_methods` factories

`clus.jsonnet:191-194` instantiates two separate factories:

```jsonnet
local cm_old = clus.clustering_methods(
    prefix='all', detector_volumes=dv, pc_transforms=pcts, coords=common_coords);
    // common_coords = ['x', 'y', 'z']

local cm = clus.clustering_methods(
    prefix='all', detector_volumes=dv, pc_transforms=pcts, coords=common_corr_coords);
    // common_corr_coords = ['x_t0cor', 'y', 'z']
```

Step 1 of the pipeline is `cm_old.switch_scope()` (`ClusteringSwitchScope`),
which applies the `PCTransformSet` (`clus.jsonnet:70-75`) to insert a
T0-corrected x coordinate `x_t0cor` into the point cloud. All subsequent
steps use `cm.*`, which reads `x_t0cor` as the primary x axis.

**Why this matters**: APA0 and APA1 have opposite drift directions, so each
APA's local `x` is anode-plane-relative and the two ranges overlap
significantly (both span ≈ 0..201 cm in magnitude). `x_t0cor` applies the
T0 correction so that the two APAs occupy non-overlapping global x ranges
(APA0: negative-x volume, APA1: positive-x volume), enabling cross-APA
distance metrics to be physically meaningful. See
[geometry-and-timing.md § "BEE undrift convention"](geometry-and-timing.md)
for the sign derivation.

**Critical**: `switch_scope` must use `cm_old` (the `x` factory) because
it reads from the existing `x` scope; the subsequent `cm.*` steps must use
the `x_t0cor` factory. Passing either factory to the wrong step produces
silently shifted clusters.

### `MultiAlgBlobClustering` — all-APA (`clus.jsonnet:195-246`)

**All-APA `cm_pipeline`** (`clus.jsonnet:195-206`), in execution order:

| # | jsonnet call | C++ class | Note |
|---|---|---|---|
| 1 | `cm_old.switch_scope()` | `ClusteringSwitchScope` | Insert `x_t0cor`; switch active PC scope. |
| 2 | `cm.extend(flag=4, length_cut=60cm, length_2_cut=15cm, num_dead_try=1)` | `ClusteringExtend` | Re-run extension in T0-corrected scope. |
| 3 | `cm.regular(name='1', length_cut=60cm, flag_enable_extend=false)` | `ClusteringRegular` | Pairwise merging, 60 cm. |
| 4 | `cm.regular(name='2', length_cut=30cm, flag_enable_extend=true)` | `ClusteringRegular` | Tighter pairwise merging with extension. |
| 5 | `cm.parallel_prolong(length_cut=35cm)` | `ClusteringParallelProlong` | Parallel/prolonged track merging. |
| 6 | `cm.close(length_cut=1.2cm)` | `ClusteringClose` | Merge spatially adjacent clusters. |
| 7 | `cm.extend_loop(num_try=3)` | `ClusteringExtendLoop` | Iterative extension to convergence. |
| 8 | `cm.separate(use_ctpc=true)` | `ClusteringSeparate` | Split over-merged clusters. |
| 9 | `cm.neutrino()` | `ClusteringNeutrino` | Neutrino-candidate clustering pass. |
| 10 | `cm.isolated()` | `ClusteringIsolated` | Flag isolated (unconnected) clusters. |

(Source line numbers in `cfg/pgrapher/common/clus.jsonnet`:
`switch_scope`=374, `neutrino`=365, `isolated`=338.)

**Bee output** (`clus.jsonnet:226-243`): two `bee_points_sets` entries:

| `name` | `algorithm` | `coords` | `individual` | What it shows |
|---|---|---|---|---|
| `img` | `img` | `['x', 'y', 'z']` | `false` | Input imaging blobs before clustering |
| `clustering` | `clustering` | `['x_t0cor', 'y', 'z']` | `false` | Output clusters in T0-corrected space |

Both sets cover all APAs together (no per-cluster individual files).

---

## Per-APA vs all-APA — comparison

| Aspect | Per-APA (`clus_per_face`) | All-APA (`clus_all_apa`) |
|---|---|---|
| Scope | Single TPC (one anode) | Full detector (all anodes merged) |
| Input | active + masked `.npz` per APA | Merged PC tree from all per-APA stages |
| Coord scope | local `x` (anode-relative) | `x_t0cor` (T0-corrected) after `switch_scope` |
| First step | `pointed` | `switch_scope` |
| `live_dead` step | yes (overlap_offset=2) | no |
| `connect1` step | yes | no |
| `neutrino` step | no | yes |
| `isolated` step | no | yes |
| Detector volumes | `a0f0pA` / `a1f0pA` (single-APA FV) | `overall` + per-APA blocks |
| Bee point sets | 1 set: `clustering` (`['x','y','z']`, individual) | 2 sets: `img` + `clustering` (`x_t0cor`) |
| Output zip | `mabc-apa<N>-face0.zip` | `mabc-all-apa.zip` |

---

## Detector-volume metadata (`clus.jsonnet:19-51`)

The `DetectorVolumes` config carries fiducial-volume bounds and drift
parameters for each stage.

| Block | x range | Purpose |
|---|---|---|
| `overall` | −202.5..+201.45 cm | Full-detector FV for all-APA MABC |
| `a0f0pA` | −202.5..−0.45 cm | APA0 face 0, single-APA MABC |
| `a1f0pA` | +0.45..+201.45 cm | APA1 face 0, single-APA MABC |

`a0f0pA` also carries the BlobSampler physics constants (`clus.jsonnet:37-41`):
`drift_speed=1.56 mm/µs`, `tick=0.5 µs`, `time_offset=-200 µs`,
`nticks_live_slice=4`. `a1f0pA` inherits these from `a0f0pA` via Jsonnet
`+` extension and overrides only the x bounds (`clus.jsonnet:47-50`).

The overall block has per-axis margins: x ±2 cm, y ±2.5 cm, z ±3 cm
(`clus.jsonnet:27-32`). These margins are used by clustering algorithms
to decide whether a cluster is near a detector boundary.

---

## TLA reference

| TLA | Default | Units | Where it lands | Effect |
|---|---|---|---|---|
| `input` | `.` | – | `wct-clustering.jsonnet:58-59` | Directory containing the four `.npz` input files |
| `anode_indices` | `[0,1]` | – | `wct-clustering.jsonnet:46` | Which APAs to process (set by empty-npz guard) |
| `output_dir` | `.` | – | passed to `clus_maker(...)` | Directory for `mabc-*.zip` outputs |
| `run` / `subrun` / `event` | 0/0/0 | – | MABC RSE fields | Stamped into Bee zip metadata |
| `reality` | `'sim'` | – | consumed by `Clustering*` | Dead-channel treatment: `'sim'` or `'data'` |
| `DL` | 6.2 | cm²/s | `params.lar.DL` | Longitudinal diffusion coefficient |
| `DT` | 9.8 | cm²/s | `params.lar.DT` | Transverse diffusion coefficient |
| `lifetime` | 10 | ms | `params.lar.lifetime` | Electron lifetime |
| `driftSpeed` | 1.565 | mm/µs | `params.lar.drift_speed` | Drift speed for MABC topology (not BlobSampler) |

`clus.jsonnet`'s `drift_speed = 1.56 mm/µs` (line 13) is used by
`BlobSampler` for t→x in point-cloud construction and is **not** overridden
by the `driftSpeed` TLA. The 0.3 % discrepancy produces ≈ 0.6 mm position
error at 201 cm drift — documented in
[geometry-and-timing.md § "Drift speed"](geometry-and-timing.md).

---

## Input format — `icluster-apa<N>-{active,masked}.npz`

Each `.npz` is a flattened ICluster graph dump written by `ClusterFileSink`
in the imaging stage. For schema details see
[imaging.md § "Output format"](imaging.md). Key points here:

- Read by `ClusterFileSource` (`sio/src/ClusterFileSource.cxx`), which
  reconstructs the ICluster graph by reading per-cluster `cluster_<i>_nodes.npy`
  and `cluster_<i>_edges.npy` arrays and attaching the configured `anodes`
  for geometry lookups.
- A 22-byte archive (no `.npy` entries inside) means zero clusters — the
  `run_clus_evt.sh:65-68` guard detects this before launching `wire-cell`.
- `active.npz` feeds port 0 of `PointTreeBuilding` (live/stepped sampler).
- `masked.npz` feeds port 1 (dead/center sampler).

---

## Output format — `mabc-*.zip`

`MultiAlgBlobClustering` writes Bee-format zip archives directly (not via a
separate Python step). Each zip contains a directory tree of JSON files:

```
<run>/<subrun>/<event>/
  ├─ <N>-<detector>-<algorithm>.json   (3D point clouds, one per bee_points_set)
  ├─ <N>-<detector>-dead.json          (dead-area patches, if save_deadarea=true)
  └─ index.json                        (metadata: RSE, detector, algorithm list)
```

The per-APA zip (`mabc-apa<N>-face0.zip`) has one point set with
`individual: true`, meaning each cluster gets its own JSON block.
The all-APA zip (`mabc-all-apa.zip`) has two point sets (`img` and
`clustering`) both with `individual: false` (all clusters combined in one
JSON block per set).

Zips are uploaded to the Bee event display via:
```sh
./upload-to-bee.sh work/evt<ID>/mabc-all-apa.zip
```

---

## Notable details / gotchas

- **Empty-npz guard is essential** — `PointTreeMerging` is a fan-in node
  with fixed `multiplicity`; if any branch delivers EOS at call=0 (as an
  empty `.npz` does), the C++ fan-in stalls waiting for data that never
  arrives. The shell-level guard (`run_clus_evt.sh:65-90`) is the only
  protection.

- **Single-APA runs** (`-a 0` or `-a 1`) — `wct-clustering.jsonnet` still
  builds `clus_all_apa` with `multiplicity=1`. The all-APA Bee zip is
  produced; it covers one TPC only. The log suffix gains `_a<N>`.

- **MABC is a single C++ component** — the `pipeline:` array in the jsonnet
  config is not a WCT pnode graph. MABC resolves each entry to an
  `IEnsembleVisitor` at configure time and calls `visit()` in a simple loop
  (`MultiAlgBlobClustering.cxx:1663-1712`). The `Clustering*` nodes in
  `g.uses(graph)` appear in the compiled config so WCT can find them by
  type+name, but no WCT edges connect them.

- **`trash-*.tar.gz` placeholders** — `TensorFileSink` with `dump_mode=true`
  drains the `ITensorSet` output of MABC into a small gzip archive where the
  data is discarded. The resulting file is ~29 bytes. See also
  [sbnd.md § "Known gotchas"](sbnd.md).

- **`face=0` hard-wired** — `clus.jsonnet:270` calls `clus_per_face` with
  `face=0` for SBND; the `per_face` wrapper (`clus.jsonnet:266`) exists for
  detectors with multiple faces but is unused in SBND.

- **Two-factory `cm`/`cm_old` pattern** — the `switch_scope` step must be
  created by the `x`-coord factory and all subsequent steps by the
  `x_t0cor`-coord factory. Swapping factories for any step produces silently
  misaligned clusters because the `coords` field names the key the algorithm
  reads from the point cloud.

- **Richer algorithm options not yet used** — the shared
  `cfg/pgrapher/common/clus.jsonnet` factory exposes many more methods
  (e.g. `tagger_*`, `numu_bdt_scorer`, `nue_bdt_scorer`,
  `protect_overclustering`, `steiner`, `improve_cluster_*`) that SBND's
  current pipelines do not invoke. These can be added to either
  `cm_pipeline` array in `clus.jsonnet` without changing any other file.

- **Imaging charge solving is upstream of MABC** — `MultiAlgBlobClustering`
  receives already-solved blob charges from imaging. MABC itself does not
  re-solve charges; it only uses the charge values from the point cloud for
  topology decisions (e.g. `use_ctpc=true` in `separate`).
