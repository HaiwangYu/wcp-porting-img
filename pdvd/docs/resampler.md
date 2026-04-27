# Resampler — ProtoDUNE-VD bottom anodes

This document covers the `Resampler` stage that precedes NF+SP for the
four bottom-drift anodes (idents 0–3).  For the overall workflow see
[nf_sp_workflow.md](nf_sp_workflow.md). For NF see [nf.md](nf.md).

## 1. Where it lives in the pipeline

```
run_nf_sp_evt.sh
  └─ wire-cell -c wct-nf-sp.jsonnet  (--tla-str reality="data")
       └─ per-anode pipeline  [wct-nf-sp.jsonnet:94-117]
            ├─ FrameFileSource          (orig frames)
            ├─ Resampler   ← only when reality=="data" AND n < 4
            ├─ OmnibusNoiseFilter       (NF)
            ├─ FrameFileSink tap        (raw NF frames)
            ├─ OmnibusSigProc           (SP)
            ├─ FrameFileSink tap        (SP frames)
            └─ DumpFrames
```

**Gate** (`wct-nf-sp.jsonnet:111`):

```jsonnet
local use_resampler = (reality == 'data');
// ...
+ (if use_resampler && n < 4 then [resamplers[n]] else [])
```

`reality` is a TLA defaulting to `"data"`; pass `--tla-str reality="sim"` (or `-r sim` via `run_nf_sp_evt.sh`) to skip resampling for simulated input.

Top-CRP anodes (idents 4–7) are already digitized at 500 ns and skip
this node entirely.

The pnode is defined in `cfg/pgrapher/common/resamplers.jsonnet` and
implemented in `aux/src/Resampler.cxx`.

## 2. Configuration

Source: `cfg/pgrapher/common/resamplers.jsonnet:4-17`

```jsonnet
g.pnode({
    type: 'Resampler',
    name: 'resmp%d' % n,
    data: {
        period:   500*wc.ns,
        time_pad: "linear",
    }
}, nin=1, nout=1,
   uses=[tools.dft, tools.anodes[n]])
```

| key | pdvd value | C++ default | meaning |
|-----|-----------|-------------|---------|
| `period` | `500 ns` | `0` (must set) | target output tick `Tr` |
| `time_pad` | `"linear"` | `"zero"` | how trailing pad samples are filled before the FFT (see §4) |
| `time_sizing` | _(not set)_ → `"duration"` | `"duration"` | trim output to original duration (`"duration"`) or keep padded length (`"padded"`) |
| `dft` | `tools.dft` | `"FftwDFT"` | DFT engine for forward/inverse FFT |

`tools.anodes[n]` is listed under `uses` only as a graph-dependency
hint to ensure ordering; the C++ `Resampler` class does not consume it
at runtime.

## 3. Do I need to provide the number of output ticks?

**No.** You only set `period` (the target `Tr`). The output tick count
is derived automatically from the input frame's tick (`Ts`) and its
sample count (`Ns_orig`).

Here is the full computation for the pdvd bottom anodes
(`Ts = 512 ns`, `Tr = 500 ns`, `Ns_orig = 6000`):

| step | formula | pdvd result |
|------|---------|-------------|
| LMN rationality size | `Nrat = LMN::rational(Ts, Tr)` | **125** |
| padded input size | `Ns_pad = LMN::nbigger(Ns_orig, Nrat)` | **6000** (no padding — 6000 ÷ 125 = 48) |
| output size from FFT | `Nr = Ns_pad × Ts / Tr` | **6144** |
| final size (`"duration"`) | `Nr_unpadded = int(Ns_orig × Ts / Tr)` | **6144** |

The rationality size `Nrat = 125` comes from:
- `|Ts − Tr| = 12 ns`
- `gcd(500 ns, 12 ns) = 4 ns`  →  `n = 12/4 = 3`
- `Nrat = 3 × 500/12 = 125`

So for 6000 ticks at 512 ns → **6144 ticks at 500 ns** (same total
duration: 3.072 ms).

## 4. What is special at the start and end of the waveform?

### Front — tbin constraint

The code raises a `ValueError` if any trace has `tbin ≠ 0`
(`Resampler.cxx:84-86`). No special treatment of the first samples
otherwise.

### End — time-domain padding before the FFT

The LMN method requires the input length to be a multiple of `Nrat`.
When `Ns_pad > Ns_orig`, the trailing samples `[Ns_orig … Ns_pad-1]`
must be filled before the FFT (`Resampler.cxx:96-118`).

With `time_pad: "linear"` (pdvd's choice), `LMN::fill_linear` writes a
straight ramp **from** `wave[Ns_orig-1]` **back to** `wave[0]`:

```
     ┌── original 6000 samples ──┐┌── pad (if any) ──┐
     wave[0] … wave[Ns_orig-1]   wave[Ns_orig] … wave[Ns_pad-1]
                                 ↕ linear ramp
                                 last → first
```

This closes the loop so the FFT's implicit periodic boundary is
continuous, avoiding ringing artifacts at the waveform edges.

Other available strategies (constant fills): `"zero"`, `"first"`,
`"last"`, `"median"`.

**For pdvd's standard 6000-sample frames, `Ns_pad = Ns_orig = 6000`, so
no padding actually occurs.** The linear strategy only activates for
frames whose length is not already a multiple of 125.

### End — interpolation normalization

After the inverse FFT, the waveform is scaled by
`wave.size() / Ns_pad` (`Resampler.cxx:125-126`). This is the
interpolation normalization that preserves signal amplitude (as opposed
to an energy-preserving DFT normalization).

### End — duration trim

With `time_sizing: "duration"` (the default), the output is truncated
to `Nr_unpadded = int(Ns_orig × Ts / Tr)` samples, ensuring the output
duration matches the input duration to within one output tick.

## 5. Initial and final tick length

| | tick | frames |
|--|------|--------|
| **Input** (`Ts`) | **512 ns** | per-anode `orig` frames from the bottom-CRP cold electronics |
| **Output** (`Tr`) | **500 ns** | matches the SP field-response grid assumed by all downstream NF/SP components |

The 512 ns input tick is set when saving the `orig` frames in the
LArSoft-side config:

```jsonnet
// cfg/pgrapher/experiment/protodunevd/wcls-nf-sp-out.jsonnet:81-82
// (LArSoft-side config — uses its own use_resampler extVar, set by FHiCL)
tick: if use_resampler == 'true' then 512*wc.ns else 500*wc.ns,
```

After resampling: **6000 ticks → 6144 ticks** (same 3.072 ms window).

## 6. Runtime confirmation

With `-L debug`, the log line from `Resampler.cxx:135-136` reports the
computed sizes for the first channel:

```
[Resampler] first ch=<N> Ts=512 Ns=6000 Ns_pad=6000 Nrat=125 Tr=500 Nr=6144 Nout=6144 padding:linear
```

You can grep for it in the wct log:

```bash
grep 'Resampler.*first ch' work/<run>_<evt>/wct_nfsp_*.log
```

## Cross-references

- [nf.md §Step 0](nf.md) — Resampler overview inside the NF doc
- [nf_sp_workflow.md](nf_sp_workflow.md) — full pipeline overview
- `cfg/pgrapher/common/resamplers.jsonnet` — jsonnet pnode definition
- `aux/inc/WireCellAux/Resampler.h` — C++ class and knob documentation
- `aux/src/Resampler.cxx` — algorithm implementation
- `util/inc/WireCellUtil/LMN.h`, `util/src/LMN.cxx` — LMN math
