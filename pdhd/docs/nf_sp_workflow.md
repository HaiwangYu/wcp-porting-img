# NF + SP Standalone Workflow — ProtoDUNE-HD

This document describes the end-to-end workflow driven by
[`run_nf_sp_evt.sh`](../run_nf_sp_evt.sh).  Detailed configuration
references live in the companion docs:
[nf.md](nf.md) · [sp.md](sp.md).
See also [pdhd-pipeline-plan.md](pdhd-pipeline-plan.md) for the
broader porting context.

---

## Context: two-part split

The full NF+SP chain is split into two parts so that the noise-filtering
and signal-processing can be iterated without re-running LArSoft:

| Part | Runs in | Input | Output |
|------|---------|-------|--------|
| 1 | art/LArSoft (`wcls-nf-sp-out.jsonnet`) | `RawDigits` | `protodunehd-orig-frames-anode{N}.tar.bz2` |
| 2 | **standalone** (`run_nf_sp_evt.sh` + `wct-nf-sp.jsonnet`) | orig frames | NF frames + SP frames |

This document covers Part 2.  The orig-frame archives produced by Part 1
are checked into `input_data/` and are the fixed starting point.

---

## Usage

```bash
./run_nf_sp_evt.sh [-a <anode>] <run> <evt>
```

| Argument | Description |
|----------|-------------|
| `<run>` | Run number (any zero-padding accepted; internally normalized to 6-digit `RUN_PADDED`) |
| `<evt>` | Event identifier (as used in the `input_data/` directory layout) |
| `-a <anode>` | Optional — restrict processing to a single anode (0–3). Omit to process all four APAs. |

### Event-directory lookup (`find_evtdir`)

The script tries several naming conventions under `input_data/` so that
run/event directories with or without padding all work:

```
input_data/run<RUN>  /evt<EVT>
                      /evt_<EVT>
           run<RUN_PADDED>/...
           run<RUN_STRIPPED>/...
```

If the run directory itself contains `protodunehd-orig-frames-anode*.tar.bz2`
directly (no event subdirectory), that directory is used as-is.

---

## Environment

The script prepends two paths to `WIRECELL_PATH`:

```
/nfs/data/1/xqian/toolkit-dev/toolkit/cfg
/nfs/data/1/xqian/toolkit-dev/wire-cell-data
```

`wire-cell-data` is where the detector data files (noise spectra,
field-response, wires) are resolved by filename.

---

## Input and output locations

```
input_data/
  run<RUN>/evt<EVT>/
    protodunehd-orig-frames-anode0.tar.bz2
    protodunehd-orig-frames-anode1.tar.bz2
    protodunehd-orig-frames-anode2.tar.bz2
    protodunehd-orig-frames-anode3.tar.bz2

work/<RUN_PADDED>_<EVT>/
  protodunehd-sp-frames-raw-anode{N}.tar.bz2   ← NF output (raw frames)
  protodunehd-sp-frames-anode{N}.tar.bz2       ← SP output (signal frames)
  wct_nfsp_<RUN_PADDED>_<EVT>[_a<N>].log       ← full debug log
```

With `-a 0` only anode 0 archives are written; the log gets the
`_a0` suffix.

---

## TLA parameters passed to `wire-cell`

`run_nf_sp_evt.sh` invokes `wire-cell` with these top-level arguments (TLAs)
that configure `wct-nf-sp.jsonnet`:

| TLA | CLI flag | Value set by script | Role |
|-----|----------|---------------------|------|
| `orig_prefix` | `--tla-str` | `<EVTDIR>/protodunehd-orig-frames` | Prefix for reading orig-frame archives |
| `raw_prefix` | `--tla-str` | `<WORKDIR>/protodunehd-sp-frames-raw` | Prefix for writing NF output archives |
| `sp_prefix` | `--tla-str` | `<WORKDIR>/protodunehd-sp-frames` | Prefix for writing SP output archives |
| `anode_indices` | `--tla-code` | `[0,1,2,3]` or `[<N>]` | Which APAs to process |

The Jsonnet appends `-anode{N}.tar.bz2` to each prefix.

---

## Per-anode pipeline

One independent data-flow pipeline is built for each requested anode
and all run in parallel under the `Pgrapher` engine:

```
FrameFileSource
  (origframesrc{N})
       │  tag: * (all traces)
       ▼
  nf_pipe{N}            ← OmnibusNoiseFilter   [nf.jsonnet]
       │  tag: raw{N}
       ├──► rawframesink{N}
       │      → protodunehd-sp-frames-raw-anode{N}.tar.bz2
       │        tags=[raw{N}], digitize=false, masks=true
       ▼
  sp_pipe{N}            ← OmnibusSigProc       [sp.jsonnet]
       │  tags: gauss{N}, wiener{N}
       ├──► spframesink{N}
       │      → protodunehd-sp-frames-anode{N}.tar.bz2
       │        tags=[gauss{N}, wiener{N}], digitize=false, masks=true
       ▼
  DumpFrames{N}
```

Source: `wct-nf-sp.jsonnet:87–106`.  The tap nodes (`raw_frame_tap`,
`frame_tap`) are `FrameFanout`-based — the main data stream passes through
while a copy is written to disk.

---

## Trace tags in the output archives

| Archive | Tag(s) | Encoding | Description |
|---------|--------|----------|-------------|
| `protodunehd-sp-frames-raw-anode{N}.tar.bz2` | `raw{N}` | float (no digitize) | NF-output waveforms with channel masks |
| `protodunehd-sp-frames-anode{N}.tar.bz2` | `gauss{N}` | float (no digitize) | Gaussian-filter SP output (charge estimate used by imaging) |
| | `wiener{N}` | float (no digitize) | Wiener-filter SP output (SNR-weighted, used by ROI seeding) |

`digitize: false` means traces are stored as 32-bit floats, preserving
the deconvolved-charge scale.  `masks: true` means channel-status and ROI
masks are included, enabling downstream imaging to skip dead/noisy channels.

The `decon_charge{N}` and all intermediate ROI-debug tags produced by SP
are **not** in the sink's `tags` list and are therefore dropped.

---

## Quick-start examples

```bash
# Process all four APAs for run 27409, event 1
./run_nf_sp_evt.sh 27409 1

# Process only APA 0 (faster for iteration)
./run_nf_sp_evt.sh -a 0 27409 1

# With zero-padded run number (equivalent)
./run_nf_sp_evt.sh -a 2 027409 1
```

Output in `work/027409_1/`.

---

## Downstream

After `run_nf_sp_evt.sh` completes, the SP frames in `work/` are consumed by:

- **`run_sp_to_magnify_evt.sh`** — converts SP frames to Magnify ROOT files
  for visual inspection (`wct-sp-to-magnify.jsonnet`).
- **`run_img_evt.sh`** — runs imaging/clustering on the SP frames.

See [pdhd-pipeline-plan.md](pdhd-pipeline-plan.md) for the full pipeline
context.
