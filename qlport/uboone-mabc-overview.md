# Overview: `uboone-mabc.jsonnet`

This Wire-Cell Toolkit configuration file implements the **Multi-Algorithm Blob Clustering (MABC)** pipeline for the MicroBooNE (uBooNE) liquid argon TPC detector. It reads uBooNE ROOT files (containing pre-reconstructed TC/blob data), runs the full MABC reconstruction chain, and outputs results to the [Bee](https://www.phy.bnl.gov/wire-cell/bee/) event display format.

## Usage

```bash
wire-cell -l stderr -L debug \
  -A kind=live \
  -A infiles=nuselEval_5384_137_6852.root \
  uboone-mabc.jsonnet
```

### Entry-Point Parameters

| Parameter | Default | Description |
|---|---|---|
| `infiles` | `"uboone.root"` | Input ROOT file path |
| `beezip` | `"bee.zip"` | Output Bee zip archive |
| `kind` | `"live"` | Data mode: `"live"`, `"dead"`, or `"both"` |
| `datapath` | `"pointtrees/%d"` | TDM datapath template for point trees |
| `initial_index` | `"0"` | Starting event index (string, parsed to int) |
| `initial_runNo` | `"1"` | Run number |
| `initial_subRunNo` | `"1"` | Subrun number |
| `initial_eventNo` | `"1"` | Event number |

---

## File Structure

The file is 1419 lines and is organized into three major parts:

### 1. Imports and Preamble (lines 1–40)

```jsonnet
local wc   = import "wirecell.jsonnet";
local pg   = import "pgraph.jsonnet";
local params = import "pgrapher/experiment/uboone/simparams.jsonnet";
local tools  = tools_maker(params);
local clus   = import "pgrapher/common/clus.jsonnet";
```

The `anode` and `anodes` objects are extracted from `tools`. A shared `pointtree_datapath = "pointtrees/%d"` string coordinates several nodes.

---

### 2. The `ub` Object — Component Library (lines 41–1336)

All pipeline components are methods and data members of a single `local ub = { ... }` object. The major sub-sections are:

#### a. BlobSampler Configurations

| Name | Purpose |
|---|---|
| `bs_live` | Live-blob sampler using `charge_stepped` strategy with dead-cell mixing disabled |
| `bs_live_no_dead_mix` | Variant with dead-cell mixing enabled (used for `improve_cluster_2`) |
| `bs_dead` | Dead-blob sampler using `center` strategy, retaining all extra fields |

Key physics parameters shared by live samplers:
- Drift speed: **1.101 mm/µs**
- Time offset: **−1600 µs + 6 mm / drift_speed**

#### b. Detector Configuration

- **`DetectorVolumes`**: Defines the uBooNE TPC active and fiducial volume geometry. Encodes per-APA/face drift parameters (tick = 0.5 µs, 4 live ticks per slice) and overall fiducial box (x: 1–255 cm, y: −99.5–101.5 cm, z: 15–1022 cm).
- **`PCTransformSet`**: Wraps `DetectorVolumes` for point-cloud coordinate transforms.

#### c. Particle Physics Lookup Tables (`LinterpFunction`)

Linear-interpolation functions (tabulated from NIST/PDG data) for five particle species:

| Function | Species | X-axis | Y-axis |
|---|---|---|---|
| `muon_dEdx_function` | Muon | Residual range (cm), 0.5–60 | dE/dx (eV/cm) |
| `electron_dEdx_function` | Electron | Residual range (cm), −0.5–59 | dE/dx (eV/cm) |
| `pion_dEdx_function` | Pion | Residual range (cm), 0.5–60 | dE/dx (eV/cm) |
| `kaon_dEdx_function` | Kaon | Residual range (cm), 0.5–60 | dE/dx (eV/cm) |
| `proton_dEdx_function` | Proton | Residual range (cm), 0.5–60 | dE/dx (eV/cm) |
| `muon_range_function` | Muon | Range (cm), 0–1101 | KE (MeV) |
| `pion_range_function` | Pion | Range (cm), ~0–1054 | KE (MeV) |
| `kaon_range_function` | Kaon | Range (cm) | KE (MeV) |
| `proton_range_function` | Proton | Range (cm), 0–1108 | KE (MeV) |
| `electron_range_function` | Electron | Range (cm) | KE (MeV) |

#### d. `ParticleDataSet`

Aggregates all dEdx and range functions into a single `ParticleDataSet` node, referenced by the MABC tagger algorithms.

#### e. `BoxRecombination` Model

uBooNE-specific recombination model used during charge-to-energy conversion:

```
A = 1.0,  B = 0.255,  E_field = 0.273 kV/cm,  ρ = 1.38 g/cm³,  Wi = 23.6 eV
```

#### f. Fiducial Volume Definitions

Two sets of polygon-based fiducial volumes (one for data, one for MC), each composed of two planar cuts combined with logical AND:

| Object | Geometry |
|---|---|
| `uboone_data_fid_xy` | `PolyFiducial` in X-Y plane (Z slabs 0–1037 cm) |
| `uboone_data_fid_zx` | `PolyFiducial` in Z-X plane (Y slabs ±115 cm) |
| `uboone_data_fid` | `CompositeFiducial` (AND of the two above) |
| `uboone_mc_fid_xy` | MC variant of the X-Y polygon (slightly tighter) |
| `uboone_mc_fid_zx` | MC variant of the Z-X polygon |
| `uboone_mc_fid` | `CompositeFiducial` (MC AND) — used by MABC |

#### g. Pipeline Node Constructors

These are Pgraph node factory functions used to build the data-flow graph:

| Constructor | Type | Description |
|---|---|---|
| `UbooneBlobSource(fname, kind, views)` | source | Reads blobs from ROOT file for a given view combination (uvw, uv, vw, wu) |
| `UbooneClusterSource(fname, sampler, datapath, optical, kind)` | transform | Builds cluster point trees from blob sets; attaches optical flash data when `optical=true` |
| `multiplex_blob_views(iname, kind, views)` | subgraph | Creates one `UbooneBlobSource` per view and merges them with `BlobSetMerge` |
| `BlobSetMerge(kind, multiplicity)` | merge | Merges N blob-set streams into one |
| `TensorSetFanin(multiplicity, tensor_order)` | merge | Merges N tensor streams (used to combine live+dead) |
| `ClusterFlashDump(datapath, kind)` | sink | Dumps cluster-flash association data |
| `BlobClustering(name)` | transform | Initial blob clustering with uBooNE policy |
| `ProjectionDeghosting(name)` | transform | Projection-based deghosting |
| `InSliceDeghosting(name, round)` | transform | In-slice deghosting (rounds 1/2/3) |
| `BlobGrouping(name)` | transform | Groups blobs into clusters |
| `ChargeSolving(name, weighting)` | transform | Solves for 3D charge with given weighting strategy |
| `LocalGeomClustering(name)` | transform | Local geometry-based clustering |
| `GlobalGeomClustering(name, policy)` | transform | Global geometry-based clustering (uBooNE policy) |
| `ClusterFileSource(fname)` | source | Reads clusters from file |
| `ClusterFileSink(fname)` | sink | Writes clusters to NumPy file |
| `BeeBlobSink(fname, sampler)` | sink | Writes blob data to Bee zip format |
| `BeeBlobTap(fname)` | tap | Fan-out: passes clusters downstream while also writing to Bee |
| `TensorFileSink(fname)` | sink | Writes tensors to file with "clustering_" prefix |
| `MultiAlgBlobClustering(...)` | transform | The complete MABC node (see below) |
| `main(graph, app, extra_plugins)` | config | Assembles the final `wire-cell` JSON configuration |

#### h. `MultiAlgBlobClustering` (MABC) — Core Algorithm

This is the central processing node. It runs an ordered pipeline of clustering visitor algorithms:

```
tagger_flag_transfer  →  clustering_recovering_bundle  →  switch_scope
  →  steiner (with improve_cluster_2 retiler)  →  fiducialutils
  →  tagger_check_neutrino  [→  UbooneMagnifyTrackingVisitor (optional)]
```

Key MABC parameters:

| Parameter | Default / Notes |
|---|---|
| `beezip` | Output Bee zip path |
| `trackfitting_config` | `"uboone_track_fitting.json"` |
| `tracking_output` | `"track_com_<run>_<event>.root"` (optional, triggers ROOT visitor) |
| `dl_weights` | Path to DL vertex weights `.pth` file |
| `dQdx_scale` | `0.1` |
| `dQdx_offset` | `-1000` |
| `save_deadarea` | `true` |
| `use_config_rse` | `true` (uses configured run/subrun/event numbers) |

**Bee output point sets** produced by MABC:

| Name | Visitor | Description |
|---|---|---|
| `regular` | `CreateSteinerGraph` | Standard 3D cluster points (x_t0cor, y, z); scope-filtered |
| `steiner` | `CreateSteinerGraph` | Steiner tree point cloud (`steiner_pc` scope) |
| `track_fit` | `TaggerCheckNeutrino` | Track-fitted points with dQ/dx coloring |
| `shower_track` | `TaggerCheckNeutrino` | Points colored by shower/track classification |
| `vertices` | `TaggerCheckNeutrino` | PR graph vertices (primary vertex q=15000) |
| `mc` (bee_pf) | `TaggerCheckNeutrino` | Particle-flow tree in Bee `mc` format |

---

### 3. Top-Level Graph Assembly (lines 1337–1419)

Three named graphs are defined:

| Graph | Input pipeline | Description |
|---|---|---|
| `live` | `ingraph_live → outgraph` | Processes live-blob views only |
| `dead` | `ingraph_dead → outgraph` | Processes dead-blob views only |
| `both` | `(live + dead) → TensorSetFanin → outgraph` | Merges live and dead streams |

**`ingraph_live`**: reads 4 view combinations — `uvw`, `uv`, `vw`, `wu`  
**`ingraph_dead`**: reads 3 view combinations — `uv`, `vw`, `wu`

The final entry-point function selects the appropriate graph based on `kind` and calls `ub.main(...)` to produce the complete `wire-cell` application configuration, loading plugins:
```
WireCellSio, WireCellAux, WireCellGen, WireCellSigProc,
WireCellImg, WireCellClus, WireCellRoot, WireCellApps, WireCellPgraph
```

---

## Data Flow Diagram

```
[ROOT file]
    |
    +--[UbooneBlobSource × N views]--[BlobSetMerge]
                                          |
                                   [UbooneClusterSource]   (+ optical if live)
                                          |
                                   [TensorSetFanin]  <-- dead stream (if kind=both)
                                          |
                                [MultiAlgBlobClustering]
                                  (MABC pipeline)
                                          |
                                  [ClusterFlashDump]
                                          |
                                      [bee.zip]
```
