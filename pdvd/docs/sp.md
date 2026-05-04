# Signal Processing (SP) — ProtoDUNE-VD

This document describes the SP stage driven by `run_nf_sp_evt.sh` →
`wct-nf-sp.jsonnet`. For the overall workflow see
[nf_sp_workflow.md](nf_sp_workflow.md). For NF see [nf.md](nf.md).

## Overview

The SP stage is a single `OmnibusSigProc` pnode returned by
`sp.jsonnet::make_sigproc(anode)`. It performs:

1. **2-D deconvolution** using the pre-computed field + electronics response
2. **ROI finding** (tight + loose) to locate signal regions
3. **ROI refinement** (break, shrink, extend, multi-plane protection)
4. **Charge extraction** via Gaussian and Wiener optimal filters

**Input**: NF-filtered frame with tag `raw<N>` (from `OmnibusNoiseFilter`)
**Output tags**: `gauss<N>` (Gaussian charge), `wiener<N>` (Wiener-optimal charge)

The SP frame is written to `protodune-sp-frames-anode<N>.tar.bz2` by
a `FrameFileSink` tap (`wct-nf-sp.jsonnet:76–91`).

## make_sigproc — sp.jsonnet

File: `toolkit/cfg/pgrapher/experiment/protodunevd/sp.jsonnet`

`make_sigproc(anode, name=null)` returns a single `OmnibusSigProc` pnode
(`nin=1, nout=1`). No internal fans or retaggers — all logic is inside
the C++ node.

### Per-anode branching

ProtoDUNE-VD has two drift technologies with different electronics:

| Anode ident | Drift | Electronics response | Full-scale |
|-------------|-------|---------------------|-----------|
| 0–3 | Bottom (TDE) | `ColdElecResponse` 7.8 mV/fC, shaping 2.2 µs | 0.2–1.6 V (1.4 V range, `params.adc.fullscale`) |
| 4–7 | Top | `JsonElecResponse` from `dunevd-coldbox-elecresp-top-psnorm_400.json.bz2`, postgain 1.36 | Forced 2.0 V |

Config in `sp.jsonnet:43–55` and `params.jsonnet:113–125`.
The `ADC_mV` ratio (`(2^resolution - 1) / fullscale`, `sp.jsonnet:43–47`)
is the key digitizer-inverse scaling knob; it differs between top and
bottom anodes.

### Common parameters (`sp.jsonnet:56–99`)

| Parameter | pdvd value | Note |
|-----------|-----------|------|
| `ftoffset` | `0.0` | Fine time offset (µs) |
| `ctoffset` | `4.0 µs` | Coarse time offset, must match field-response file `protodunevd_FR_norminal_260324.json.bz2` |
| `postgain` | `1.0` | Post-decon gain (default 1.2; pdvd uses 1.0) |
| `fft_flag` | `0` | 0 = lower memory; 1 = slightly faster but higher memory |
| `isWrapped` | `false` | CRP channels do not wrap across planes |
| `use_roi_debug_mode` | `false` | Set to `true` to emit intermediate ROI tags (see below) |
| `use_multi_plane_protection` | `true` | Enable 2- and 3-plane coincidence veto |

## OmnibusSigProc — the engine

Source: `toolkit/sigproc/src/OmnibusSigProc.cxx`
Config read at lines 54–213.

### Step 1 — Response deconvolution

The node first deconvolves the field response and the electronics response
from every waveform. Key inputs:

| Config key | pdvd value | Meaning |
|------------|-----------|---------|
| `field_response` | `protodunevd_FR_norminal_260324.json.bz2` (both faces) | 2-D field response functions |
| `elecresponse` | per-anode (see above) | Electronics shaping + gain |
| `per_chan_resp` | `""` (disabled) | Per-channel response correction (disabled, `params.files.chresp=null` at `params.jsonnet:175`) |
| `ctoffset` | `4.0 µs` | Shifts decon output to align with true t=0; must be re-tuned if the FR file changes |

`nticks` is **ignored** in the config (`OmnibusSigProc.cxx:67–69`); the
node uses the waveform length from the incoming frame. The `Resampler`
upstream of NF ensures bottom-anode frames are already at 500 ns.

### Step 2 — Tight ROI finding

A first pass identifies narrow signal regions ("tight ROIs") where the
deconvolved charge is clearly above noise:

| Knob | pdvd value | Meaning |
|------|-----------|---------|
| `troi_ind_th_factor` | `3.0` | Threshold for induction planes = `troi_ind_th_factor × noise_RMS` |
| `troi_col_th_factor` | `5.0` | Threshold for collection plane |
| `troi_pad` | (default) | Symmetric tick padding around tight ROIs |
| `troi_asy` | (default) | Asymmetric padding (pre/post) |

### Step 3 — Loose ROI finding

A complementary wider search for extended MIP tails and long signals:

| Knob | pdvd value | Meaning |
|------|-----------|---------|
| `lroi_rebin` | `6` | Rebin factor for the loose-filter waveform |
| `lroi_th_factor` | `3.5` | Main noise threshold factor |
| `lroi_th_factor1` | `0.7` | Secondary (lower) threshold for peak extension |
| `lroi_jump_one_bin` | `1` | Allow ROIs to merge across a single empty bin |
| `lroi_max_th` | (default) | Absolute ADC ceiling |
| `lroi_short_length` | (default) | Minimum ROI length before merging |

### Step 4 — ROI refinement

The tight + loose ROIs are refined to suppress residual noise:

| Knob | pdvd value | Meaning |
|------|-----------|---------|
| `r_th_factor` | `3.0` | Amplitude threshold in σ for keeping a ROI |
| `r_fake_signal_low_th` | `375 e-` | Charge below this in induction ROIs → kill (noise proxy) |
| `r_fake_signal_high_th` | `750 e-` | Upper band for fake-signal suppression |
| `r_fake_signal_low_th_ind_factor` | `1.0` | Multiplicative factor for induction low threshold |
| `r_fake_signal_high_th_ind_factor` | `1.0` | Multiplicative factor for induction high threshold |
| `r_th_peak` | `3.0` | Peak detection threshold (σ) |
| `r_sep_peak` | `6.0` | Minimum peak separation (ticks) for peak splitting |
| `r_low_peak_sep_threshold_pre` | `1200` | Pre-splitting charge threshold (e-) |
| `r_pad` | (default) | Padding after break/shrink loop |
| `r_break_roi_loop` | (default) | Iterations for the ROI break loop |
| `r_max_npeaks` | (default) | Max peaks to fit per ROI |
| `r_sigma` | (default) | Gaussian peak-fit σ |
| `r_th_percent` | (default) | ROI boundary fraction |

### Step 5 — Multi-plane protection

With `use_multi_plane_protection: true`, the node runs a 2-D coincidence
check across U, V, W planes and vetoes ROIs that appear in only one plane
without matching activity in the others:

| Knob | Meaning |
|------|---------|
| `mp_th1` | Single-plane charge threshold for veto |
| `mp_th2` | 2-plane coincidence threshold |
| `mp_tick_resolution` | Tick tolerance for coincidence matching |

Outputs intermediate traces `mp3_roi<N>` and `mp2_roi<N>` (3-plane and
2-plane coincidence maps) — useful for debugging but not written to disk
unless explicitly tapped.

### Step 6 — Charge extraction (Gaussian + Wiener filters)

Final deconvolution through two optimal filter chains produces the two
output trace sets:

| Output tag | Filter | Physical meaning |
|-----------|--------|-----------------|
| `gauss<N>` | `Gaus_wide` (σ=0.12 MHz) | Charge-preserving Gaussian-smoothed signal — use for charge measurement |
| `wiener<N>` | Per-plane `Wiener_tight_{U,V,W}` | Wiener-optimal (noise-matched) — better S/N for track finding |

The `wiener<N>` tag also carries a **per-channel threshold summary**
(a `vector<double>` attached as a trace-tag summary). This is what
`MagnifySink` later reads as `h[uvw]_threshold<N>` TH1F histograms.
Source: `OmnibusSigProc.cxx:1865`, summary populated from `perwire_rmses`
at `:1492`.

## Filter catalog — `sp-filters.jsonnet`

File: `toolkit/cfg/pgrapher/experiment/protodunevd/sp-filters.jsonnet`

**Warning**: Filter component names are looked up by literal string in C++
(`OmnibusSigProc.cxx:116–137`). Do not rename them.

### Low-frequency filters (`LfFilter`)

Used to isolate signal regions before ROI finding by suppressing
long-baseline wander.

| Name | τ (MHz) | Role |
|------|---------|------|
| `ROI_tight_lf` | 0.014 | Tight-ROI shaping — line 80 |
| `ROI_tighter_lf` | 0.06 | Even tighter version used in refinement path — line 81 |
| `ROI_loose_lf` | 0.002 | Loose-ROI (wider time support for extended MIP tails) — line 82 |

Larger τ → narrower time-domain envelope → tighter ROI boundaries.

### High-frequency / Gaussian filters (`HfFilter`, `flag:true`)

Applied in frequency domain to smooth the deconvolved waveform.

| Name | σ (MHz) | Role |
|------|---------|------|
| `Gaus_tight` | 0 (unit) | Used with tight-ROI decon path — line 84 |
| `Gaus_wide` | 0.12 | Charge output (`gauss<N>`) — line 85 |

Larger σ → more smoothing → lower noise but slightly broader peaks.

### Wiener filters (`HfFilter`, `flag:true`) — per-plane

Noise-matched optimal filters for the Wiener-deconvolved output.

| Name | σ (MHz) | power | Lines |
|------|---------|-------|-------|
| `Wiener_tight_U` | 0.1488 | 3.76 | 89–92 |
| `Wiener_tight_V` | 0.1597 | 4.36 | 93–95 |
| `Wiener_tight_W` | 0.1362 | 3.35 | 96–100 |
| `Wiener_wide_U` | 0.1868 | 5.05 | 102–105 |
| `Wiener_wide_V` | 0.1936 | 5.77 | 106–109 |
| `Wiener_wide_W` | 0.1758 | 4.38 | 110–114 |

The filter shape is `exp(-(f/σ)^power)`. Larger σ → more aggressive
noise suppression but more charge loss on narrow peaks. The `power`
controls how sharply the filter rolls off.

Tuning guide: if you see residual noise in `wiener` output, try
decreasing σ; if charge peaks are too narrow/cut, increase σ. Rerun
NF+SP and check with Magnify.

### Wire-domain smoothing filters (`HfFilter`, `flag:false`)

Applied along the wire-index dimension (transverse to drift) rather than
time.

| Name | σ (wire units) | Lines |
|------|---------------|-------|
| `Wire_ind` | `5 / √π ≈ 2.82` | 116 |
| `Wire_col` | `10 / √π ≈ 5.64` | 117 |

Collection gets wider wire smoothing than induction because collection
strips are narrower relative to typical track widths.

## Debug mode

Setting `use_roi_debug_mode: true` in `sp.jsonnet:86` causes
`OmnibusSigProc` to emit additional trace tags per anode:

| Tag | Content |
|-----|---------|
| `tight_lf<N>` | Tight low-frequency filtered waveform |
| `loose_lf<N>` | Loose LF filtered waveform |
| `decon_charge<N>` | Raw deconvolved charge before ROI masking |
| `cleanup_roi<N>` | ROI map after cleanup pass |
| `break_roi_1st<N>`, `break_roi_2nd<N>` | ROI after 1st/2nd break iterations |
| `shrink_roi<N>` | ROI after shrink pass |
| `extend_roi<N>` | ROI after extend pass |

These are not written to the SP archive by default. To capture them,
add the tags to the `FrameFileSink` in `wct-nf-sp.jsonnet:76–91`.

## Output archive

```jsonnet
FrameFileSink {
  outname: '<sp_prefix>-anode<N>.tar.bz2',
  tags: ['gauss<N>', 'wiener<N>'],
  digitize: false,   // floating-point electrons
  masks: true,       // channel mask metadata included
}
```

`masks: true` means the bad-channel mask (built by the NF `maskmap`) is
saved alongside the waveforms — imaging nodes use this to skip bad channels.

## Downstream consumption

| Consumer | Tags used |
|----------|----------|
| `run_img_evt.sh` → `wct-img-all.jsonnet` | `gauss<N>`, `wiener<N>` |
| `run_sp_to_magnify_evt.sh` → `wct-sp-to-magnify.jsonnet` | `gauss<N>`, `wiener<N>`, threshold summary on `wiener<N>` |

## Tools wired into SP

`pgrapher/common/tools.jsonnet` builds:

| Tool | Description |
|------|-------------|
| `anodes[n]` | `AnodePlane` nodes, one per detector volume (8 for pdvd) |
| `dft` | `FftwDFT` — FFT backend for all deconvolutions |
| `field` | `FieldResponse` loaded from `protodunevd_FR_norminal_260324.json.bz2` |
| `elec_resps[0]` | `ColdElecResponse` (bottom anodes 0–3) |
| `elec_resps[1]` | `JsonElecResponse` (top anodes 4–7) |
| `perchanresp` | Disabled (`chresp: null`) — no per-channel response correction currently |

The `perchanresp` slot is the hook for per-channel calibration corrections.
When a calibration file becomes available, set `params.files.chresp` to the
file path and remove the `null` at `params.jsonnet:175`.

## Source file index

| File | Purpose |
|------|---------|
| `wct-nf-sp.jsonnet` (pdvd/) | Top-level pipeline; wires SP pnode into per-anode graph |
| `toolkit/cfg/pgrapher/experiment/protodunevd/sp.jsonnet` | Returns OmnibusSigProc pnode; per-anode elec response branching |
| `toolkit/cfg/pgrapher/experiment/protodunevd/sp-filters.jsonnet` | All filter component definitions (LF, Gaus, Wiener, Wire) |
| `toolkit/cfg/pgrapher/experiment/protodunevd/params.jsonnet` | Detector params: adc resolution/fullscale, elec response files, field response file, chresp |
| `toolkit/cfg/pgrapher/common/tools.jsonnet` | Builds anode, dft, field, elec_resps, perchanresp tools |
| `toolkit/sigproc/src/OmnibusSigProc.cxx` | C++ engine: deconvolution, ROI finding, charge extraction |
| `toolkit/sigproc/inc/WireCellSigProc/OmnibusSigProc.h` | OmnibusSigProc class + config schema |
