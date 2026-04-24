# NF + SP Standalone Workflow (`run_nf_sp_evt.sh`)

This document covers the end-to-end flow of running standalone
Noise Filtering (NF) and Signal Processing (SP) for one event
without LArSoft, using the script `run_nf_sp_evt.sh` and the
WireCell configuration `wct-nf-sp.jsonnet`.

For the NF internals see [nf.md](nf.md).
For the SP internals see [sp.md](sp.md).

## Context: two-part split

The full pipeline from raw data to SP frames is split across two steps:

| Step | Driver | Runs in | What it does |
|------|--------|---------|--------------|
| 1 | `wcls-nf-sp-out.jsonnet` | art / LArSoft | Reads `RawDigits`, runs `ChannelSelector`, saves per-anode **orig** frames: `protodune-orig-frames-anode{N}.tar.bz2` |
| 2 | `wct-nf-sp.jsonnet` | standalone `wire-cell` CLI | Reads orig frames, runs `[Resampler →] NF → SP`, saves **NF raw** and **SP** frames |

`run_nf_sp_evt.sh` drives step 2.

## Usage

```
./run_nf_sp_evt.sh [-a anode] <run> <evt>
```

Options:
- `-a N` — process only anode `N` (default: all 0–7).

The script sets `WIRECELL_PATH` to include `toolkit/cfg` and
`wire-cell-data`, then calls `wire-cell` with `wct-nf-sp.jsonnet`.

## Input / output locations

| Path | Description |
|------|-------------|
| `input_data/<run_dir>/<evt_dir>/protodune-orig-frames-anode{N}.tar.bz2` | Input: pre-NF ADC waveforms (step 1 output) |
| `work/<RUN_PADDED>_<EVT>/protodune-sp-frames-raw-anode{N}.tar.bz2` | Output: NF-filtered waveforms (tag `raw<N>`) |
| `work/<RUN_PADDED>_<EVT>/protodune-sp-frames-anode{N}.tar.bz2` | Output: SP-deconvolved frames (tags `gauss<N>`, `wiener<N>`) |
| `work/<RUN_PADDED>_<EVT>/wct_nfsp_<RUN_PADDED>_<EVT>.log` | Debug log |

The script searches `input_data/` for run/event directories with the same
naming flexibility used by `run_img_evt.sh` (leading-zero variants, underscore
separators, flat run-root layout). See `run_nf_sp_evt.sh:36-51` for the
`find_evtdir()` logic.

## TLA parameters forwarded to `wire-cell`

These are the top-level arguments (`--tla-*`) that `run_nf_sp_evt.sh`
passes to `wct-nf-sp.jsonnet` (`run_nf_sp_evt.sh:84-93`):

| TLA | Default | Meaning |
|-----|---------|---------|
| `orig_prefix` | `<evtdir>/protodune-orig-frames` | Input archive prefix (reads `{prefix}-anode{N}.tar.bz2`) |
| `raw_prefix` | `<workdir>/protodune-sp-frames-raw` | Output prefix for NF frames |
| `sp_prefix` | `<workdir>/protodune-sp-frames` | Output prefix for SP frames |
| `use_resampler` | `"true"` | Whether to resample bottom-drift anodes 0–3 before NF |
| `anode_indices` | `[0,1,2,3,4,5,6,7]` or `[N]` if `-a N` | Which anodes to process |
| `sigoutform` | `"dense"` | SP output format: `"sparse"` or `"dense"` |

## Per-anode pipeline

`wct-nf-sp.jsonnet:94–117` builds one independent pipeline per anode:

```
FrameFileSource  (orig frames, tag 'orig')
  │
  ├─ [Resampler]        only when use_resampler=="true" AND anode index n < 4
  │
  ├─ OmnibusNoiseFilter (NF pipe)
  │     PDVDOneChannelNoise
  │     PDVDCoherentNoiseSub
  │     PDVDShieldCouplingSub   (top anodes ident > 3 only)
  │     → output tag: raw<N>
  │
  ├─ FrameFanout tap → FrameFileSink  (writes protodune-sp-frames-raw-anode<N>.tar.bz2)
  │                                    tags: [raw<N>],  digitize:false, masks:false
  │
  ├─ OmnibusSigProc  (SP: deconvolution + ROI finding)
  │     → output tags: gauss<N>, wiener<N>  (+ threshold summary on wiener<N>)
  │
  ├─ FrameFanout tap → FrameFileSink  (writes protodune-sp-frames-anode<N>.tar.bz2)
  │                                    tags: [gauss<N>, wiener<N>], digitize:false, masks:true
  │
  └─ DumpFrames
```

Files:
- Pipeline construction: `wct-nf-sp.jsonnet:94–117`
- NF pipe returned by: `nf.jsonnet` in `toolkit/cfg/pgrapher/experiment/protodunevd/`
- SP pnode returned by: `sp.jsonnet` in `toolkit/cfg/pgrapher/experiment/protodunevd/`

## Why only anodes 0–3 get the Resampler

ProtoDUNE-VD has two CRP technologies:
- **Bottom drift** (anodes 0–3, TDE): native readout tick ≠ 500 ns.
- **Top drift** (anodes 4–7): already at 500 ns.

The WireCell field-response files and SP deconvolution assume a uniform
500 ns tick (`params.daq.tick = 0.5 µs`). The `Resampler` node
(`period=500 ns, time_pad=linear`) brings bottom-drift waveforms to the
common grid before any filtering.

## Trace tags in the output archives

| Archive | Tags in the `.tar.bz2` | Contains |
|---------|------------------------|---------|
| `protodune-sp-frames-raw-anode<N>.tar.bz2` | `raw<N>` | NF-filtered ADC (pedestal subtracted, in ADC counts) |
| `protodune-sp-frames-anode<N>.tar.bz2` | `gauss<N>`, `wiener<N>` | Deconvolved charge in electrons; `wiener<N>` also carries per-channel threshold summaries |

The tag names carry the per-anode integer **ident** (0–7 for pdvd).
The `gauss<N>` and `wiener<N>` traces are what downstream tools
(`run_img_evt.sh`, `run_sp_to_magnify_evt.sh`) expect.

## Quick-start examples

```bash
# All anodes, run 039324, event 1
./run_nf_sp_evt.sh 039324 1

# Only anode 3
./run_nf_sp_evt.sh -a 3 039324 1
```

After completion, verify:
```bash
ls work/039324_1/protodune-sp-frames*.tar.bz2
# Should see raw-anode{0..7} and sp-anode{0..7} archives
```
