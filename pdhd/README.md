# pdhd — ProtoDUNE-HD per-event scripts

Scripts and jsonnet configs for running per-event imaging and clustering on
ProtoDUNE-HD signal-processed data.

## Imaging

Reads per-anode SP frame archives and produces cluster archives for each APA.

```bash
./run_img_evt.sh [-a ANODE] [-S] [-s SEL_TAG] <run> <evt>
```

**Options**

| Flag | Meaning |
|------|---------|
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
./run_clus_evt.sh [-s SEL_TAG] <run> <evt>
```

Reads cluster archives from `work/<run>_<evt>[_<SEL_TAG>]/` and runs the full
clustering chain, producing output under the same work directory.

## Signal-processing frames → Magnify ROOT file

```bash
./run_sp_to_magnify_evt.sh <run> <evt> [anode_indices] [output_file]
```

Converts per-anode SP frame archives into a single Magnify ROOT file
containing TH2F waveform histograms and a `Trun` metadata tree.

## Selection (optional pre-processing)

```bash
./run_select_evt.sh <run> <evt> <sel_tag>
```

Applies a channel/time selection and writes filtered SP frames to
`work/<run>_<evt>_<sel_tag>/input/`.  Pass the resulting tag with `-s` to
the imaging or clustering scripts.
