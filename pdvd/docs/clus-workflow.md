# Clustering workflow deep-dive

This document traces what happens inside `./run_clus_evt.sh <run> <evt>` — from input tarballs to output Bee zips — covering the graph topology, run/event metadata, dead-channel handling, and how to restrict processing to a single APA or face.

For a higher-level overview of all scripts and input/output paths see [pdvd.md](pdvd.md).

---

## 1. Graph topology — how APAs and faces are processed

The entry-point configuration is `wct-clustering.jsonnet` (imported library: `clus.jsonnet`).

### Top level (`wct-clustering.jsonnet:34-60`)

For each anode index `N` in `anode_indices` (default `[0,1,2,3,4,5,6,7]`):

- One `ClusterFileSource` reads `<input>/clusters-apa-anode{N}-ms-active.tar.gz`  → "live" cluster stream.
- One `ClusterFileSource` reads `<input>/clusters-apa-anode{N}-ms-masked.tar.gz` → "dead" cluster stream.

Both streams feed a per-APA pipeline.  All per-APA pipelines then feed `clus_all_apa`.

```
active[0] ─┐           active[7] ─┐
masked[0] ─┤ per_apa   masked[7] ─┤ per_apa
           │  (anode0)             │  (anode7)
           ▼                       ▼
        mabc-                   mabc-              ← per-face + per-APA zips
        anode0.zip               anode7.zip
           │                       │
           └───────────┬───────────┘
                       ▼
                 clus_all_apa
                       │
                       ▼
               mabc-all-apa.zip
```

### Per-APA pipeline (`clus.jsonnet:271-370`)

```
live stream ──► ClusterFanout(×2) ──► face 0 ──► clus_per_face(anode, face=0)
                                  └──► face 1 ──► clus_per_face(anode, face=1)
dead stream ──► ClusterFanout(×2) ──► face 0 ─┘
                                  └──► face 1 ─┘
                                               │
                                    PointTreeMerging(×2)
                                               │
                                    MABC "protect_overclustering"
                                               │
                                    mabc-<anode>.zip
```

- `ClusterFanout multiplicity=2` (`clus.jsonnet:281,288`) copies each input cluster to both face pipelines.
- `PointTreeMerging multiplicity=2` (`clus.jsonnet:296-304`) unions the two face point-trees into one per-APA tree.
- The per-APA MABC (`clus.jsonnet:318-340`) runs only `protect_overclustering`.
- Output: `mabc-<anode>.zip` (e.g. `mabc-anode0.zip`).

### Per-face pipeline (`clus.jsonnet:139-269`)

```
live ──► ClusterScopeFilter(face_index=N) ──► BlobSampler "live" (stepped)  ──┐
dead ──► ClusterScopeFilter(face_index=N) ──► BlobSampler "dead" (center)   ──┤
                                                                               ▼
                                                                  PointTreeBuilding
                                                              tags=["live","dead"]
                                                                               │
                                                                  MABC per-face pipeline
                                                                               │
                                                              mabc-<anode>-faceN.zip
```

- **`ClusterScopeFilter`** (`img/src/ClusterScopeFilter.cxx:61-66`): keeps a blob vertex iff `blob->face()->which() == face_index`; all non-blob vertices pass through.  This splits the full APA cluster graph into face-0 and face-1 sub-graphs.
- **`BlobSampler`** "live" uses `strategy:["stepped"]`, extras `[".*wire_index",".*charge_val",".*charge_unc","wpid"]`; "dead" uses `strategy:["center"]`, `extra:[".*"]`.  C++: `clus/src/BlobSampler.cxx`.
- **`PointTreeBuilding`** (`clus/src/PointTreeBuilding.cxx:53-95,179,219`) calls `sample_live()` and `sample_dead()` to build the point-cloud tree for the MABC pipeline.  The two samplers are keyed `"3d"` (live) and `"dead"`.
- **Per-face MABC algorithm pipeline** (`clus.jsonnet:203-217`):
  ```
  pointed → live_dead(overlap=2) → extend(flag=4, num_dead_try=1) →
  regular(-one, 60 cm) → regular(_two, 30 cm) → parallel_prolong(35 cm) →
  close(1.2 cm) → extend_loop(×3) → separate → connect1
  ```
- Output: `mabc-<anode>-face0.zip` and `mabc-<anode>-face1.zip`.

### All-APA pipeline (`clus.jsonnet:372-493`)

- `PointTreeMerging multiplicity=nanodes` unions all per-APA trees.
- Coordinate system switches from `(x,y,z)` to `(x_t0cor,y,z)` for the all-APA algorithms.
- Algorithm pipeline: `switch_scope → extend → regular×2 → parallel_prolong → close → extend_loop(×3) → separate → neutrino → isolated → examine_bundles`.
- Output: `mabc-all-apa.zip`.

---

## 2. Run/subrun/event (RSE) propagation

### RSE is not in the cluster tarballs

`ClusterFileSource` (`sio/src/ClusterFileSource.cxx:139-257,320-358`) only reads the cluster graph and arrays from the tarball.  There is no frame-level run/subrun/event header.  The only numeric context it extracts is an integer `ident` from the filename convention.

### RSE is hard-coded in `clus.jsonnet`

```jsonnet
// clus.jsonnet lines 11-18
local initial_runNo    = "1";
local initial_subRunNo = "1";
local initial_eventNo  = "1";
local LrunNo    = std.parseInt(initial_runNo);
local LsubRunNo = std.parseInt(initial_subRunNo);
local LeventNo  = std.parseInt(initial_eventNo);
```

These constants are forwarded to each of the three `MultiAlgBlobClustering` nodes (`clus.jsonnet:233-235,332-334,445-447`) via:
```jsonnet
use_config_rse: true,
runNo:    LrunNo,
subRunNo: LsubRunNo,
eventNo:  LeventNo,
```

### C++ branch controlled by `use_config_rse`

`clus/src/MultiAlgBlobClustering.cxx:110-121`:

- `use_config_rse: true` (current pdvd config): MABC takes `runNo/subRunNo/eventNo` from the jsonnet config and calls `m_sink.set_rse(...)`.  RSE is therefore fixed at whatever the jsonnet says.
- `use_config_rse: false` (alternative): MABC derives RSE from the tensor-set `ident` using bit-packing: `run = (ident>>16)&0x7fff; evt = ident&0xffff` (`MultiAlgBlobClustering.cxx:628-635`).  `subRunNo` defaults to 0 in this path.

Even with `use_config_rse: true`, `m_eventNo` is auto-incremented by 1 each time a new tensor-set ident is seen (`MultiAlgBlobClustering.cxx:1618-1625`).  For a single event per `wire-cell` invocation (the current script) this is fine; in a multi-event batch the event counter drifts from the configured starting value.

### RSE in the output files

RSE appears only as **JSON fields inside each Bee-zip entry**.  The path inside the zip is `data/<index>/<index>-<name>.json` (`util/src/Bee.cxx:305-308`), where `<index>` is a sequence counter (starting from `initial_index=0`).  The fields `runNo`, `subRunNo`, `eventNo` are injected into every JSON object by `Bee.cxx:344-346`.

The **zip filename itself** (`mabc-anode0.zip`, `mabc-all-apa.zip`, etc.) and the **internal directory name** do not encode RSE — they use anode/face names and a sequence index.  This is what the Bee viewer expects: `index` selects the event slot; `runNo/subRunNo/eventNo` are display labels.

### How to plumb real RSE from the shell script (future option)

No C++ changes are needed — MABC already reads `runNo/subRunNo/eventNo` from its jsonnet config.  The required changes are:

1. Turn the three hard-coded `local` strings in `clus.jsonnet:11-18` into arguments on the top-level `function (output_dir='')` (line 496):
   ```jsonnet
   function (output_dir='', runNo=1, subRunNo=1, eventNo=1)
   ```
2. Add matching TLAs to `wct-clustering.jsonnet:15-21` and forward them into the `clus(...)` import call.
3. Add two TLA flags to `run_clus_evt.sh:70-77` (both variables already exist in the script):
   ```sh
   --tla-code "runNo=${RUN_STRIPPED}" \
   --tla-code "eventNo=${EVT}" \
   ```

---

## 3. Dead-channel handling

### The `-ms-masked.tar.gz` tarball is a real dead-channel product

`img.jsonnet:162-184` defines `multi_masked_2view_slicing_tiling` using:
```jsonnet
masked_planes = [[0,1],[1,2],[0,2]]
dummy_planes  = [[2],[0],[1]]
```
This is the standard 2-view dead-region tiling (e.g. as in MicroBooNE): for each of three wire-plane-pair combinations, two planes are active-but-masked and the third is a dummy.  The output is written to `-ms-masked.tar.gz` via the masked fork in `img.jsonnet:289-301,337-349`.  It is not a placeholder.

### Routing into the clustering pipeline

`wct-clustering.jsonnet:34-49` feeds:
- `-ms-active.tar.gz` → input port 0 of each per-APA pipeline (live stream).
- `-ms-masked.tar.gz` → input port 1 of each per-APA pipeline (dead stream).

Inside `clus_per_apa` the dead stream passes through `ClusterFanout(×2)` (once per face) → `ClusterScopeFilter` → `BlobSampler "dead"` → `PointTreeBuilding` tag `"dead"` (`clus.jsonnet:179`).  The resulting `"dead"` scope in the point-tree tensor is what the algorithms consume.

### Algorithms that use dead-channel information

| Algorithm | How it uses dead channels | Config in pdvd |
|---|---|---|
| `ClusteringLiveDead` | `live->is_connected(*dead, dead_live_overlap_offset_)` — merges live clusters that touch a dead region (`clus/src/clustering_live_dead.cxx:82-116`) | `dead_live_overlap_offset=2` (`clus.jsonnet:206`) |
| `ClusteringExtend` | Runs `Clustering_4th_dead(...)` for `num_dead_try` additional passes (`clus/src/clustering_extend.cxx:401,819`) | `num_dead_try=1` (per face: `clus.jsonnet:207`; all-APA: `clus.jsonnet:407`) |
| `MultiAlgBlobClustering` | `save_deadarea:true` writes Bee dead-area patch overlays (`MultiAlgBlobClustering.cxx:1639-1646`, flush at `:352-359`) | `save_deadarea:true` (`clus.jsonnet:236,335,448`) |
| `ClusteringExtendLoop`, `ClusteringSeparate`, `ClusteringConnect1`, `ClusteringExamineBundles` | Operate on the merged live+dead ensemble produced by `PointTreeBuilding`, so they implicitly see dead-region geometry | (no extra parameter) |

In summary: dead channels are present and active throughout the clustering pipeline.

---

## 4. Running a subset of APAs or faces

### Select APAs — already supported, no code change needed

Pass `anode_indices` as a `--tla-code` argument to `run_clus_evt.sh`, or modify the `wire-cell` call directly:

```sh
# Process only anode 0:
wire-cell ... --tla-code 'anode_indices=[0]' -c wct-clustering.jsonnet

# Process anodes 0 and 4 (one per drift volume):
wire-cell ... --tla-code 'anode_indices=[0,4]' -c wct-clustering.jsonnet
```

The jsonnet restricts the `anodes` list to the chosen indices (`wct-clustering.jsonnet:23`), and `clus_all_apa`'s `PointTreeMerging multiplicity=nanodes` (`clus.jsonnet:382`) accepts `nanodes=1` — the C++ merge loop is a no-op for a single input (`clus/src/PointTreeMerging.cxx:121`).

Outputs produced: `mabc-<anode>-face0.zip`, `mabc-<anode>-face1.zip`, `mabc-<anode>.zip` for each chosen anode, plus `mabc-all-apa.zip` covering only those anodes.

To make this easy from the shell script, edit `run_clus_evt.sh:75` to replace the hard-coded
```sh
--tla-code 'anode_indices=[0,1,2,3,4,5,6,7]'
```
with a variable, or simply call `wire-cell` directly with the desired subset.

### Geometry reference — which anode is which

| Anode indices | Drift direction | Anode-face x | Cathode x |
|---|---|---|---|
| 0 – 3 | +x (bottom drift) | ~−3358 mm | ~−25 mm |
| 4 – 7 | −x (top drift)    | ~+3358 mm | ~+25 mm |

Anodes 0–3 each cover the same (x,y,z) range as the others in that group; they differ in y/z position (4 CRPs per drift volume).

### Select a single face — requires a small jsonnet change

The per-APA pipeline in `clus.jsonnet:271-370` hard-codes two faces.  To make it parametric:

1. Add a `faces=[0,1]` argument to `clus_per_apa` (line 271) and to `clus_maker.per_apa` (line 499).
2. Compute `local nfaces = std.length(faces)`.
3. Set `cfout_live.multiplicity = nfaces` and `cfout_dead.multiplicity = nfaces` (currently `2` at lines 281, 288).
4. Replace the two-element fixed list at lines 291-294 with:
   ```jsonnet
   local per_face_pipes = [clus_per_face(anode, face=f, dump=false, bee_dir=bee_dir) for f in faces],
   ```
5. Set `pcmerging.multiplicity = nfaces` (line 300).
6. Replace the four hard-coded edges (lines 361-366) with a comprehension:
   ```jsonnet
   edges = [
       g.edge(cfout_live,       per_face_pipes[i], i, 0) for i in std.range(0, nfaces-1)
   ] + [
       g.edge(cfout_dead,       per_face_pipes[i], i, 1) for i in std.range(0, nfaces-1)
   ] + [
       g.edge(per_face_pipes[i], pcmerging,         0, i) for i in std.range(0, nfaces-1)
   ],
   ```
7. Add a `faces` TLA to `wct-clustering.jsonnet` and thread it through.

No C++ changes are needed: `ClusterFanout multiplicity=1` is legal (`img/src/ClusterFanout.cxx:30-34`), and `PointTreeMerging multiplicity=1` is a no-op.

---

## 5. Quick-reference: key source files

| Component | File | Key lines |
|---|---|---|
| Top-level clustering config | `pdvd/wct-clustering.jsonnet` | 15-60 |
| Clustering pipeline library | `pdvd/clus.jsonnet` | 139-501 |
| Run script | `pdvd/run_clus_evt.sh` | 70-77 |
| Imaging pipeline library | `pdvd/img.jsonnet` | 162-184, 289-349 |
| Clustering methods factory (jsonnet) | `cfg/pgrapher/common/clus.jsonnet` | 54, 231-374 |
| `MultiAlgBlobClustering` config intake | `clus/src/MultiAlgBlobClustering.cxx` | 85-145 |
| RSE config read (`use_config_rse`) | `clus/src/MultiAlgBlobClustering.cxx` | 110-121 |
| RSE fallback via ident bit-packing | `clus/src/MultiAlgBlobClustering.cxx` | 628-635 |
| Auto-increment eventNo | `clus/src/MultiAlgBlobClustering.cxx` | 1618-1625 |
| RSE injection into Bee JSON | `util/src/Bee.cxx` | 305-308, 344-346 |
| Bee sink class | `util/inc/WireCellUtil/Bee.h` | 190-256 |
| `ClusterFileSource` (no RSE in tarballs) | `sio/src/ClusterFileSource.cxx` | 139-257, 320-358 |
| `ClusterScopeFilter` | `img/src/ClusterScopeFilter.cxx` | 38-78 |
| `ClusterFanout` | `img/src/ClusterFanout.cxx` | 28-55 |
| `PointTreeBuilding` | `clus/src/PointTreeBuilding.cxx` | 53-95, 179, 219 |
| `PointTreeMerging` | `clus/src/PointTreeMerging.cxx` | 78-152 |
| `ClusteringLiveDead` | `clus/src/clustering_live_dead.cxx` | 27-162 |
| `ClusteringExtend` / `num_dead_try` | `clus/src/clustering_extend.cxx` | 31-65, 401, 819 |

All toolkit paths are relative to `/nfs/data/1/xqian/toolkit-dev/toolkit/`.
