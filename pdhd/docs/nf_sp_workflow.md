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
| `-g <elecGain>` | FE amplifier gain in mV/fC (default: `14`). Use `7.8` for low-gain data. Automatically selects the matching noise-spectrum file (`params.jsonnet:165–166`). |

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

| Parameter | CLI flag | Value set by script | Role |
|-----------|----------|---------------------|------|
| `elecGain` | `-V` (extVar) | `-g` flag value (default `14`) | FE gain in mV/fC; selects noise-spectrum file automatically |
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
  sp_pipe{N}            ← OmnibusSigProc → L1SPFilterPD → FrameMerger
                          [sp.jsonnet; L1SP ON by default]
       │  tags: gauss{N}, wiener{N}   (both carry the L1SP-fitted waveform)
       ├──► spframesink{N}
       │      → protodunehd-sp-frames-anode{N}.tar.bz2
       │        tags=[gauss{N}, wiener{N}], digitize=false, masks=true
       ▼
  DumpFrames{N}
```

Source: `wct-nf-sp.jsonnet:87–106`.  L1SP defaults to `process` mode
(`sp.jsonnet:29`, `wct-nf-sp.jsonnet:43`); see [sp.md](sp.md#l1spfilterpd--unipolar-induction-correction)
for override flags (`-c` calibration dump, `-w` waveform dump, or
`--tla-str l1sp_pd_mode=''` to bypass).  The tap nodes (`raw_frame_tap`,
`frame_tap`) are `FrameFanout`-based — the main data stream passes through
while a copy is written to disk.

The cross-channel adjacency expansion runs by default.  It promotes a
sub-threshold ROI's LASSO eligibility to that of an originally-triggered
neighbour (±1 channel, same plane) when their tick windows overlap,
lengths are similar, and the candidate's own raw asymmetry / decon
`gmax` look L1SP-shaped.  Pass `--tla-code l1sp_pd_adj_enable=false` to
disable it and recover the pre-2026-05-02 output.  See
[`sigproc/docs/l1sp/L1SPFilterPD.md`](https://github.com/WireCell/wire-cell-toolkit/blob/apply-pointcloud/sigproc/docs/l1sp/L1SPFilterPD.md#cross-channel-adjacency-expansion)
for the gate criteria and the verification on event 027409:0 APA0.

---

## Trace tags in the output archives

| Archive | Tag(s) | Encoding | Description |
|---------|--------|----------|-------------|
| `protodunehd-sp-frames-raw-anode{N}.tar.bz2` | `raw{N}` | float (no digitize) | NF-output waveforms with channel masks |
| `protodunehd-sp-frames-anode{N}.tar.bz2` | `gauss{N}` | float (no digitize) | SP charge estimate.  With L1SP default-on (`l1sp_pd_mode='process'`), the L1SP-fitted waveform is emitted under this tag for L1SP-processed planes (APA0 U; APA1-3 U+V). |
| | `wiener{N}` | float (no digitize) | SP SNR-weighted output.  With L1SP default-on, also carries the L1SP fit (byte-identical to `gauss{N}` on processed planes). |

`digitize: false` means traces are stored as 32-bit floats, preserving
the deconvolved-charge scale.  `masks: true` means channel-status and ROI
masks are included, enabling downstream imaging to skip dead/noisy channels.

The `decon_charge{N}` and all intermediate ROI-debug tags produced by SP
are **not** in the sink's `tags` list and are therefore dropped.

---

## Quick-start examples

```bash
# Process all four APAs for run 27409, event 1 (14 mV/fC gain, default)
./run_nf_sp_evt.sh 27409 1

# Explicitly specify gain (required; default is 14 mV/fC)
./run_nf_sp_evt.sh -g 14 27409 1       # high-gain
./run_nf_sp_evt.sh -g 7.8 027409 1    # low-gain data

# Process only APA 0 (faster for iteration)
./run_nf_sp_evt.sh -a 0 27409 1

# With zero-padded run number (equivalent)
./run_nf_sp_evt.sh -a 2 027409 1
```

Output in `work/027409_1/`.

---

## Run-to-run reproducibility

Two consecutive runs with identical inputs now produce **bit-identical**
NF and SP archives. This workflow was the primary reproducer for the
bug: NF output drifted at the ULP level (≈ 0.1 ADC rms, max ≈ 26 ADC)
and SP output showed structural differences up to ≈ 434 ADC between
runs — even with ASLR disabled (`setarch x86_64 -R`), SP would still
diverge.

Root cause was in `aux/src/FftwDFT.cxx`: the FFTW plan-cache key
included a `bool aligned = (src&15)|(dst&15)` bit derived from runtime
heap addresses. Heap addresses vary between processes (under ASLR, and
even without it due to allocator-state variance after NF finishes),
toggling that bit between cached plans → different FFTW codelets
(SIMD vs scalar) → ULP drift in NF and amplified differences through
SP deconvolution FFTs.

Fix (toolkit commit `47d16673`): add `FFTW_UNALIGNED` to all
plan-creation calls and remove `aligned` from the cache key — a single
plan now serves any buffer alignment. No config or jsonnet change.

### L1SPFilterPD re-verification (2026-05-02)

After `L1SPFilterPD` was added to the SP graph (with the
`FrameSplitter`/`FrameMerger` wiring that routes the LASSO-fit gauss
into both the `gauss{N}` and `wiener{N}` output tags), reproducibility
was re-verified on event 027409:0 with `setarch -R`.  Two consecutive
runs each on APA0 and APA1 produced **bit-identical** inner `.npy`
arrays (`frame_gauss{N}`, `frame_wiener{N}`, `frame_raw0`,
`channels_*`, `tickinfo_*`).  L1SP was confirmed active in every run
(`Timer: WireCell::SigProc::L1SPFilterPD ≈ 0.14 s` on APA0, ≈ 0.29 s
on APA1).  Tarball byte sizes still differ by tens of bytes between
runs — that is bz2/tar metadata, not data.

The L1SP-side path has no internal source of run-to-run drift.  Static
read of `sigproc/src/L1SPFilterPD.cxx`, `util/src/LassoModel.cxx`, and
`util/src/ElasticNetModel.cxx` shows: no RNG, no threading, no hash-
keyed containers (only `std::map<int,…>` / `std::set<int>` keyed on
channel/tick), a fresh `LassoModel` constructed per ROI, and Eigen
running single-threaded (no MKL / OpenBLAS / TBB / `libgomp` linked
into `libWireCellSigProc.so` or `libWireCellUtil.so`, no `-fopenmp`
in the build flags).  The FFTW inside L1SP rides on the same
`FFTW_ESTIMATE | FFTW_UNALIGNED` settings that the 2026-04-29 fix
established.

To verify reproducibility on this workflow:
```bash
WORK=/tmp/repro && mkdir -p $WORK/r1 $WORK/r2
rm -rf work/027409_0
./run_nf_sp_evt.sh -a 0 027409 0
cp work/027409_0/protodunehd-sp-frames*.tar.bz2 $WORK/r1/
rm -rf work/027409_0
./run_nf_sp_evt.sh -a 0 027409 0
cp work/027409_0/protodunehd-sp-frames*.tar.bz2 $WORK/r2/
# Compare inner .npy arrays (tarball bytes always differ — timestamps):
python3 /home/xqian/tmp/wct_nondet/pdhd_diff.py $WORK/r1 $WORK/r2
# Both NF(raw) and SP rows should report equal=True.
```

---

## Downstream

After `run_nf_sp_evt.sh` completes, the SP frames in `work/` are consumed by:

- **`run_sp_to_magnify_evt.sh`** — converts SP frames to Magnify ROOT files
  for visual inspection (`wct-sp-to-magnify.jsonnet`).
- **`run_img_evt.sh`** — runs imaging/clustering on the SP frames.

See [pdhd-pipeline-plan.md](pdhd-pipeline-plan.md) for the full pipeline
context.
