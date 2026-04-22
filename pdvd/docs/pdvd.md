# ProtoDUNE-VD Imaging and Clustering (`pdvd/`)

## Provenance

Configs and scripts imported from
[HaiwangYu/wcp-porting-img `xn_vd_debug` branch](https://github.com/HaiwangYu/wcp-porting-img/tree/xn_vd_debug/pdvd).
Original author: Xin Ning (`xning`).

## Directory layout

```
pdvd/
├── docs/                    ← this documentation
├── data/                    ← Bee JSON staging area (written by wct-img-2-bee.py)
├── work/                    ← per-event scratch dirs (created by helper scripts)
│   └── <run>_<evt>/         ← imaging + clustering outputs for one event
├── input_data               → /nfs/data/1/xning/wirecell-working/data/
│                               symlink to Xin Ning's sample data tree
├── upload-to-bee.sh         → ../upload-to-bee.sh
│
├── wct-img-all.jsonnet      ← top-level imaging driver
├── img.jsonnet              ← imaging pipeline library (imported by wct-img-all)
├── wct-clustering.jsonnet   ← top-level clustering driver
├── clus.jsonnet             ← clustering pipeline library (imported by wct-clustering)
├── clus-new.jsonnet         ← older PDHD-derived variant (reference only)
├── wcls-nf-sp-out.jsonnet   ← ART/LArSoft NF+SP → frame tarballs (upstream step)
├── wct-sim-check-track.jsonnet  ← single-track simulation check
│
├── run_evt.pl               ← main per-(run,event) dispatcher
├── run_img_evt.sh           ← imaging only
├── run_clus_evt.sh          ← clustering only
├── run_bee_img_evt.sh       ← Bee conversion + upload, from IMAGING output (no clustering)
├── run_img.sh               ← original manual recipe (commented examples)
├── unzip.pl                 ← extract mabc*.zip into data/ (Path B Bee upload)
├── wct-img-2-bee.py         ← convert cluster tarballs → Bee JSON
├── wct-img-2-bee-only.py    ← single-anode debug variant
├── plot_frames.py           ← visualise SP frame archives as PNG
├── select_frames.py         ← interactive crop of frame archives (Qt UI)
│
└── protodune-sp-frames-anode{0..7}.tar.bz2  ← SAMPLE INPUT (see Q1 below)
```

## Input data under `input_data/`

`input_data` symlinks to `/nfs/data/1/xning/wirecell-working/data/`.
Run/event naming is **not uniform**:

| Run dir       | Event subdir(s)          | Notes                                      |
|---------------|--------------------------|--------------------------------------------|
| `run039324/`  | `evt1/`                  | Has SP frames + cluster tarballs           |
| `run040475/`  | `evt_0/` (empty), `evt_1/` | Underscore naming; `evt_0` has no data   |
| `run41189/`   | *(none — flat layout)*   | No leading zeros; data files at run root  |

Each event directory (or run root for flat layout) contains:

- `protodune-sp-frames-anode{0..7}.tar.bz2` — per-anode SP frames (imaging input)
- `protodune-sp-frames-raw-anode{0..7}.tar.bz2` — raw frames before SP (~47 MB each)
- `clusters-apa-anode{0..7}-ms-{active,masked}.tar.gz` — pre-computed imaging output
- `woodpecker_img_clus/` — sometimes a second copy of cluster tarballs from a later run

The helper scripts accept the run number with or without leading zeros and try all
candidate directory names automatically.

---

## Q1. Are the `protodune-sp-frames-anode*.tar.bz2` files here input or output?

They are **input** to the imaging step — staged sample data.

They are per-anode signal-processing (SP) output frames produced upstream by
`wcls-nf-sp-out.jsonnet` running inside LArSoft/ART.  The eight files staged in
this directory come from `input_data/run039324/evt1/` so that the imaging step can
be run standalone without LArSoft.

---

## Q2. Imaging

**Purpose:** convert per-anode SP frames → per-anode imaging cluster tarballs.

**Config:** `wct-img-all.jsonnet` (imports `img.jsonnet`)

**Input:** `<input_prefix>-anode{0..7}.tar.bz2`

**Output:** `<output_dir>/clusters-apa-anode{N}-ms-active.tar.gz`
          + `<output_dir>/clusters-apa-anode{N}-ms-masked.tar.gz` per anode

**Command:**
```sh
wire-cell -l stdout -L debug \
  --tla-str input_prefix=protodune-sp-frames \
  --tla-code 'anode_indices=[0,1,2,3,4,5,6,7]' \
  --tla-str output_dir=. \
  -c wct-img-all.jsonnet
```

TLA reference:

| TLA | Type | Default | Meaning |
|-----|------|---------|---------|
| `input_prefix` | `--tla-str` | `protodune-sp-frames` | Path prefix before `-anodeN.tar.bz2` |
| `anode_indices` | `--tla-code` | `[0..7]` | Anodes to process |
| `output_dir` | `--tla-str` | `""` (current dir) | Directory for output cluster tarballs |

**Required `WIRECELL_PATH`** (set automatically by the helper scripts):
```sh
WCT_BASE=/nfs/data/1/xning/wirecell-working
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/dunereco/dunereco/DUNEWireCell/protodunevd:${WIRECELL_PATH}
```

---

## Q3. Clustering

> For a deep-dive on graph topology, RSE propagation, dead-channel handling, and per-APA/face selection see **[clus-workflow.md](clus-workflow.md)**.

**Purpose:** convert per-anode imaging cluster tarballs → multi-algorithm blob clustering → Bee zips.

**Config:** `wct-clustering.jsonnet` (imports `clus.jsonnet`)

**Input:** `<input>/clusters-apa-anode{N}-ms-active.tar.gz`
         + `<input>/clusters-apa-anode{N}-ms-masked.tar.gz`

**Output:** `<output_dir>/mabc-anode{N}.zip`, `<output_dir>/mabc-all-apa.zip`
           (plus `trash-*.tar.gz` debug sinks)

**Command:**
```sh
wire-cell -l stdout -L debug \
  --tla-str input=. \
  --tla-code 'anode_indices=[0,1,2,3,4,5,6,7]' \
  --tla-str output_dir=. \
  -c wct-clustering.jsonnet
```

TLA reference:

| TLA | Type | Default | Meaning |
|-----|------|---------|---------|
| `input` | `--tla-str` | `"."` | Directory containing the 16 cluster tarballs |
| `anode_indices` | `--tla-code` | `[0..7]` | Anodes to process |
| `output_dir` | `--tla-str` | `""` (current dir) | Directory for Bee zips |

---

## Q4. Single config doing both imaging and clustering?

No — the two steps are separate `wire-cell` invocations.  Use
`perl run_evt.pl <run> <evt> chain` (see below) to run them in sequence.

---

## Helper scripts

All scripts are run from the `pdvd/` directory.  Outputs go to
`work/<run>_<evt>/` (6-digit zero-padded run, e.g. `work/039324_1/`).

### `perl run_evt.pl [-a anode] <run> <evt> [stage]`

Main dispatcher.  `stage` is one of:
- `img` — imaging only
- `clus` — clustering only
- `bee` — Bee conversion + upload from imaging output (no clustering)
- `chain` — img → clus → bee (**default**)

```sh
perl run_evt.pl 039324 1          # full chain
perl run_evt.pl 039324 1 img      # imaging only
perl run_evt.pl 039324 1 clus     # clustering only (uses imaging output if present)
perl run_evt.pl 039324 1 bee      # upload to Bee
perl run_evt.pl -a 3 039324 1 img # imaging for anode 3 only
```

The optional `-a N` (0–7) is forwarded to each underlying script, restricting
all processing to that single anode.  The flag may appear anywhere in the
argument list (before or after `<run>`, `<evt>`, etc.).

Logs: `work/039324_1/wct_img_039324_1.log`, `work/039324_1/wct_clus_039324_1.log`

### `./run_img_evt.sh [-a anode] <run> <evt>`

Reads SP frames from `input_data/` event dir, writes cluster tarballs to
`work/<run>_<evt>/`.  Use `-a N` (0–7) to process only anode `N`; without it
all 8 are processed.

### `./run_clus_evt.sh [-a anode] <run> <evt>`

Reads cluster tarballs from `work/<run>_<evt>/` (after imaging) or falls back
to the pre-computed tarballs in `input_data/` event dir.  Writes Bee zips to
`work/<run>_<evt>/`.  Use `-a N` (0–7) to restrict to a single anode; without
it all 8 are processed.

### `./run_bee_img_evt.sh [-a anode] <run> <evt>`

Converts imaging cluster tarballs (`clusters-apa-anode{N}-ms-active.tar.gz`,
produced by `run_img_evt.sh`) directly to Bee JSON via `wirecell-img bee-blobs`
— does **not** run clustering/MABC.  Reads from `work/<run>_<evt>/` if imaging
has been run, otherwise from `input_data/` event dir.  Produces
`upload_<run>_<evt>.zip` and prints the Bee URL.  Use `-a N` (0–7) to convert
only that anode; the resulting zip contains a single `0-apa{N}.json`.

---

## Bee upload

### Path A — imaging → Bee directly (used by `run_bee_img_evt.sh`)

Reads the per-anode imaging cluster tarballs
(`clusters-apa-anode{N}-ms-active.tar.gz`) and calls
`wirecell-img bee-blobs -g protodunevd` on each, writing `data/0/0-apa{N}.json`.
No clustering is performed — the Bee display shows the raw imaging blobs.
The drift speed and x-offset sign differ by TPC half:

| Anodes 0–3 (bottom drift) | Anodes 4–7 (top drift) |
|---|---|
| `--speed "-1.56*mm/us"` | `--speed "1.56*mm/us"` |
| `--x0 "-341.5*cm"` | `--x0 "341.5*cm"` |

After conversion: `zip -r upload data`, then `./upload-to-bee.sh upload.zip`.

### Path B — clustering → Bee via MABC's built-in writer (used by `run_clus_evt.sh`)

`wct-clustering.jsonnet` / `clus.jsonnet` run MABC on the imaging tarballs and
produce `mabc-anode{N}.zip` / `mabc-all-apa.zip` via
`MultiAlgBlobClustering`'s built-in Bee writer — the Bee display here shows
**clustered** blobs, in contrast to Path A's raw imaging blobs.  To upload:
```sh
./unzip.pl        # expands mabc*.zip into data/
./zip-upload.sh   # rezips data/ → upload.zip, calls ../upload-to-bee.sh
```

### Upload mechanism

`upload-to-bee.sh` authenticates against `https://www.phy.bnl.gov/twister/bee`
and POSTs the zip.  On success it prints:
```
https://www.phy.bnl.gov/twister/bee/set/<UUID>/event/list/
```

---

## Known gotchas

- **RSE hard-coded in `clus.jsonnet`**: `initial_runNo`, `initial_subRunNo`,
  `initial_eventNo` are hard-coded locals (lines 11–18), not TLAs.  Bee event
  metadata will not reflect the actual run/event.  For visualisation this is
  usually fine.

- **`run41189` vs `run039324` naming**: `run41189` has no leading zeros and stores
  data files directly at the run root with no `evt*/` subdir.  The helper scripts
  handle this automatically.

- **`run040475/evt_0/` is empty**: that directory exists but contains no data.
  Use `evt_1` instead.

- **`clus-new.jsonnet`**: 4-anode PDHD-style variant with hard-coded
  `detector: "protodunehd"` / `bee_detector: "sbnd"`.  Not used by current entry
  points; kept for reference.

- **`wct-img-2-bee.py` clears `data/` on each run**: running multiple events
  sequentially overwrites the previous event's Bee JSON.  Each run produces a
  persistent `upload_<run>_<evt>.zip` file.

- **`run_clus_evt.sh -a N` shrinks the clustering topology to a single APA**:
  detector volumes, `PointTreeMerging` multiplicity, and MABC's anode list all
  become single-APA.  Cross-APA clustering steps are a no-op in this mode.
  Use this for debugging a single anode, not for production.
