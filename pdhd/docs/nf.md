# Noise Filtering (NF) — ProtoDUNE-HD

This document covers the NF configuration used by the standalone
[`run_nf_sp_evt.sh`](../run_nf_sp_evt.sh) pipeline.
See also [sp.md](sp.md) and [nf_sp_workflow.md](nf_sp_workflow.md).

---

## Overview

Each of the four APAs gets its own independent `OmnibusNoiseFilter` pnode.
Inside that pnode the noise filtering is a two-step composition:

1. **PDHDOneChannelNoise** — per-channel operations (baseline; adaptive
   baseline and partial/RC-undershoot detection, both disabled by default).
2. **PDHDCoherentNoiseSub** — grouped coherent subtraction (per-FEMB
   median with signal protection and per-channel scaling).

> **pdhd vs pdvd**: the pdhd NF has no Resampler step (pdhd is already
> uniformly at 500 ns from DAQ) and no ShieldCouplingSub step (there is
> no shield-coupling in the APA design).  All tunables for per-channel
> behaviour live in the channel DB (`chndb-base.jsonnet`), not in the
> node definitions.

The NF is assembled in `wct-nf-sp.jsonnet:39–47` and the node factory
lives in `nf.jsonnet`.

---

## Step 1 — PDHDOneChannelNoise (per-channel filter)

**Source**: `nf.jsonnet:9–18`

```jsonnet
local single = {
    type: 'PDHDOneChannelNoise',
    name: name,          // e.g. 'nf0'
    uses: [dft, chndbobj, anode],
    data: {
        noisedb: wc.tn(chndbobj),
        anode:   wc.tn(anode),
        dft:     wc.tn(dft),
        // adaptive_baseline left at C++ default (false): PDHD cold
        // electronics is DC-coupled, so the IS_RC partial-RC gate that
        // fronts the adaptive baseline (see Microboone.cxx:963-1047) has
        // no physical meaning here. Side effect: the lf_noisy mask
        // emitted under is_partial in ProtoduneHD.cxx is no longer
        // produced; any bad-channel info will be supplied separately.
    },
};
```

**What it actually does (in order)** (`ProtoduneHD.cxx:808–875`):

1. **FFT** the waveform; evaluate `is_partial = m_adaptive_baseline ?
   m_check_partial(spectrum) : false` — the IS_RC check
   (`Diagnostics::Partial`) runs only when `adaptive_baseline=true`
   (see §[Partial / RC-undershoot detection](#partial--rc-undershoot-detection)).
   With the current configuration the field is omitted from `nf.jsonnet`,
   leaving `is_partial` permanently `false`.
2. **Kill the DC bin** (`spectrum[0] = 0`) and inverse-FFT back to time
   domain.
3. **Compute a dynamic baseline**: clip the signal at ±6 σ, take the
   binned median, subtract it from the waveform.
4. **If `is_partial`** (dormant by default — requires `adaptive_baseline=true`):
   - For induction planes (U, V): tag the channel `lf_noisy`.
   - Run `PDHD::SignalFilter` (mark ±4 σ bins with a large sentinel).
   - Run `PDHD::RawAdapativeBaselineAlg` (sliding-window median, 512-tick
     window, skipping flagged bins).
   - Run `PDHD::RemoveFilterFlags`.

### What is *not* applied here

Several chndb fields are configured but the corresponding code paths in
`PDHDOneChannelNoise::apply()` are **commented out** in the current build:

| Field | Status | Reference |
|-------|--------|-----------|
| `adaptive_baseline` | **Disabled by config** (C++ default `false`, omitted from `nf.jsonnet`): PDHD cold electronics is DC-coupled so the IS_RC partial-RC gate has no physical meaning — see `Microboone.cxx:963-1047` where IS_RC selects between RCRC dec and the adaptive-baseline fallback for broken-RC channels | `ProtoduneHD.cxx:817` |
| `nominal_baseline` | **Unused** — subtraction commented out | `ProtoduneHD.cxx:813` |
| `rcrc` / `rc_layers` | **Unused** — RC undershoot correction commented out | `ProtoduneHD.cxx:819–822` |
| `freqmasks` (→ `noise` spectrum) | **Unused** — `noise(ch)` is never called | `PDHDOneChannelNoise::apply` does not query it |
| `min_rms_cut` / `max_rms_cut` | **Unused** — `NoisyFilterAlg` block commented out | `ProtoduneHD.cxx:861–872` |
| Sticky-bit / ledge detection | **Not implemented** in the PDHD class | `nf.jsonnet:41` (commented-out `maskmap` alternative) |

Consequence: the `maskmap: {noisy: "bad", lf_noisy: "bad"}` entry in
`nf.jsonnet:42` acts on `lf_noisy` only — the `noisy` key fires only if
some other upstream component (e.g. a simulation noise generator) injects
that mask; `PDHDOneChannelNoise` never produces it.

---

## Partial / RC-undershoot detection

**Source**: `sigproc/src/Diagnostics.cxx:15–32`, `ProtoduneHD.cxx:817`

The IS_RC check is now config-gated: `ProtoduneHD.cxx:817` evaluates

```cpp
bool is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false;
```

`Diagnostics::Partial` (default constructor: `nfreqs=4`,
`maxpower=6000`) returns `true` iff **both** conditions hold on the
frequency-domain spectrum `spec`:

1. `|spec[1]|` strictly dominates each of `|spec[2]|...|spec[5]|`.
2. The mean of `|spec[1]|...|spec[5]|` exceeds `maxpower` (= 6000).

This is a heuristic for the spectral signature of an RC-undershoot
waveform — the original "IS_RC()" diagnostic by Xin Qian.  IS_RC is
meaningful only on detectors with AC-coupled cold electronics, because
it detects channels where the RC coupling capacitor has degraded; see
`Microboone.cxx:963-1047` where IS_RC is the if/else that selects
between RCRC deconvolution (intact RC) and the adaptive-baseline
fallback (broken RC).  **PDHD cold electronics is DC-coupled; the IS_RC
heuristic has no physical meaning here**, so `adaptive_baseline` is
left at its C++ default (`false`) and `is_partial` is always `false`.

**Consequence**: the whole `if (is_partial)` block at
`ProtoduneHD.cxx:842–859` is dormant.  In particular:

- `lf_noisy` is **not emitted** by `PDHDOneChannelNoise` (induction-plane
  partial channels will not be tagged; any bad-channel info must be
  supplied by a separate mechanism).
- `RawAdapativeBaselineAlg` does **not run**.

The code block is intentionally left in place so that `adaptive_baseline`
can be set to `true` in future configurations where IS_RC is meaningful.

---

## Step 2 — PDHDCoherentNoiseSub (grouped coherent subtraction)

**Source**: `nf.jsonnet:19–29`, `ProtoduneHD.cxx:889–964`

```jsonnet
local sp_filters = import 'pgrapher/experiment/pdhd/sp-filters.jsonnet';
// ...
local grouped = {
    type: 'PDHDCoherentNoiseSub',
    name: name,
    uses: [dft, chndbobj, anode] + sp_filters,  // registers HfFilter/LfFilter instances
    data: {
        noisedb:           wc.tn(chndbobj),
        anode:             wc.tn(anode),
        dft:               wc.tn(dft),
        rms_threshold:     0.0,
        // Per-plane SP Wiener filter for deconvolution; APA 0 uses _APA1 variants.
        time_filters:
          if anode.data.ident == 0
          then ['Wiener_tight_U_APA1', 'Wiener_tight_V_APA1', 'Wiener_tight_W_APA1']
          else ['Wiener_tight_U', 'Wiener_tight_V', 'Wiener_tight_W'],
        lf_tighter_filter: 'ROI_tighter_lf',  // SignalProtection (median deconv)
        lf_loose_filter:   'ROI_loose_lf',    // Subtract_WScaling (per-channel deconv)
    },
};
```

Per FEMB group (40 ch on U/V, 48 ch on W; see `chndb-base.jsonnet:20–22`)
the algorithm runs three sub-steps:

### Sub-step A — CalcMedian

Compute the per-tick **median** across all channels in the group.

### Sub-step B — SignalProtection (`ProtoduneHD.cxx:281–467`)

Identify bins in the median that likely contain real physics signal and
must not be subtracted:

**ADC-domain pass:**

```
limit = max(protection_factor × rms_of_median, adc_limit)
limit = min(limit, min_adc_limit)
```

Mark every bin where `|median[j] − mean| > limit`, padded by
`pad_window_{front,back}` ticks on each side.  With the chndb-base
defaults this gives `limit = min(max(5·rms, 60), 200)`.

**Deconvolution-domain pass** (U/V only — W has `response:{}`):

- Deconvolve the median by `respec` (the hard-coded 1D field response;
  see §[Per-channel response waveforms](#per-channel-response-waveforms)).
- Apply `HfFilter Wiener_tight_{U,V,W}(freq) × LfFilter ROI_tighter_lf(freq)`.
  On APA 0 (`anode.data.ident == 0`) the Wiener instances are the `_APA1`
  variants (`Wiener_tight_U_APA1`, etc.), matching the SP filter used on that
  anode.  The plane index is resolved via `m_anode->resolve(ch).index()`
  (0=U, 1=V, 2=W).  Both filter waveforms are fetched from the SP
  `IFilterWaveform` factory — the same shared instances already used by
  `OmnibusSigProc`.  **The four hardcoded MicroBooNE-era notch bands
  (≈107 / 178 / 214 / 250 kHz) previously zero-ed in `filter_low` are
  removed**; if specific lines appear in PDHD data they should be handled via
  per-channel `freqmasks_phys` entries in `chndb-base.jsonnet`.
- IFFT; mark bins where the deconvolved height exceeds
  `max(protection_factor·rms, decon_limit)`, shifted by `res_offset` and
  padded as above.

Inside detected ROIs the median is replaced by a linear interpolation
between the samples just outside each ROI boundary.

### Sub-step C — Subtract_WScaling (`ProtoduneHD.cxx:58–279`)

For each channel in the group:

1. Compute a per-channel **scaling coefficient**:
   `coef = Σ(s·m) / Σ(m²)` over "quiet" bins (`|s| < 4σ`).
   Renormalize to the group-mean `ave_coef`.  Clip to `[0, 1.5]`.

2. For U/V (non-empty `respec`): repeat the deconvolution on the
   channel-local signal using `HfFilter Wiener_tight_{U,V,W}(freq) ×
   LfFilter ROI_loose_lf(freq)` (same SP factory instances, plane-resolved
   as in Sub-step B).  An ROI is deemed
   "real signal" if `max_val > decon_limit1 && |min_val| < max_val ×
   roi_min_max_ratio`.  The median is replaced by linear interpolation
   across such ROIs before subtraction.

3. Subtract `scaling × (modified median)` from the channel.

4. When `rms_threshold > 0` (currently `0.0`): an adaptive per-channel
   `decon_limit1` is computed from the per-channel decon RMS.  At `0.0`
   the fixed chndb value is used.

### Tunable knobs

| Knob | Set in | Value | Effect |
|------|--------|-------|--------|
| `rms_threshold` | `nf.jsonnet` `data.rms_threshold` | `0.0` | Channels whose RMS exceeds this are excluded from the group-median computation. `0.0` = no exclusion; also disables adaptive `decon_limit1`. |
| `time_filters` | `nf.jsonnet` `data.time_filters` | `['Wiener_tight_U[_APA1]', 'Wiener_tight_V[_APA1]', 'Wiener_tight_W[_APA1]']` | Per-plane SP `HfFilter` instance names [U, V, W] for the coherent-sub deconvolution filter. APA 0 (`ident==0`) uses the `_APA1` variants. Defined in `sp-filters.jsonnet`. |
| `lf_tighter_filter` | `nf.jsonnet` `data.lf_tighter_filter` | `'ROI_tighter_lf'` | SP `LfFilter` instance for `SignalProtection` (median deconvolution pass; τ=0.08 MHz). Replaces the old `filter_low(freq, decon_lf_cutoff)` helper. |
| `lf_loose_filter` | `nf.jsonnet` `data.lf_loose_filter` | `'ROI_loose_lf'` | SP `LfFilter` instance for `Subtract_WScaling` (per-channel ROI deconvolution pass; τ=0.002 MHz). Replaces the old `filter_low_loose`. |
| `debug_dump_path` | `nf.jsonnet` `data.debug_dump_path` (TLA `debug_dump_path` on `wct-nf-sp.jsonnet`) | `''` | When non-empty, `PDHDCoherentNoiseSub::apply()` emits one `.npz` per group under `<path>/apa<N>/<plane>_g<gid>.npz` capturing `median`, `medians_decon_aligned`, `signal_bool`, ROI list, per-ROI median scalars (`max/min/ratio_obs/accepted`), per-(channel, ROI) accept matrix, and every knob in scope. Default `''` is **bit-identical** to the pre-instrumentation hot path (one `.empty()` check per group). |
| `debug_dump_groups` | `nf.jsonnet` `data.debug_dump_groups` | `[]` | Optional whitelist of group ids (= first-channel idents); `[]` = all groups. |

### Validation: opt-in NPZ dump + Bokeh viewer

Run with `-d <dump_root>`:

```bash
./run_nf_sp_evt.sh 027409 0 -a 1 -d work/dbg
# → work/dbg/027409_0/apa1/{U,V,W}_g<gid>.npz
```

then serve the browser viewer (`pdhd/nf_plot/serve_coherent_viewer.sh
work/dbg`) and SSH-tunnel to the workstation. Each group's dump
includes the chosen ADC threshold, the `decon_threshold_chosen`, the
`decon_limit1` line, the `roi_min_max_ratio` test, and the per-ROI
accept distribution across channels — the data needed to judge
whether the chosen knobs are well tuned. See
[`../nf_plot/README.md`](../nf_plot/README.md) for usage, NPZ schema,
and tuning workflow.

---

## OmnibusNoiseFilter wrapper

**Source**: `nf.jsonnet:31–60`

```jsonnet
local obnf = g.pnode({
    type: 'OmnibusNoiseFilter',
    name: name,
    data: {
        nticks:                 0,
        maskmap:                {noisy: "bad", lf_noisy: "bad"},
        channel_filters:        [wc.tn(single)],
        grouped_filters:        [wc.tn(grouped)],
        channel_status_filters: [],
        noisedb:                wc.tn(chndbobj),
        intraces:               '',
        outtraces:              'raw%d' % n,
    },
}, uses=[chndbobj, anode, single, grouped], nin=1, nout=1);
```

### Tunable knobs

| Knob | Set in | Default | Effect |
|------|--------|---------|--------|
| `nticks` | `nf.jsonnet:37` | `0` | Force waveform length in ticks. `0` = inherit from input frame. |
| `maskmap` | `nf.jsonnet:42` | `{noisy:"bad", lf_noisy:"bad"}` | In the current build (with `adaptive_baseline=false`) neither `lf_noisy` nor `noisy` is produced by `PDHDOneChannelNoise`; the maskmap entry is effectively inert. A richer alternative `{sticky:"bad", ledge:"bad", noisy:"bad"}` is commented out. |
| `intraces` | `nf.jsonnet:54` | `''` (wildcard) | Input frame tag selector. |
| `outtraces` | `nf.jsonnet:55` | `'raw%d' % n` | Tag written on the output traces (e.g. `raw0`). Must match `rawframesink{N}` in `wct-nf-sp.jsonnet:62`. |

---

## OmniChannel Noise DB (`chndb-base.jsonnet`)

Instantiated once per anode as `OmniChannelNoiseDB` named
`ocndbperfect{N}` (`wct-nf-sp.jsonnet:39–44`).  Built by the
`base(params, anode, field, n)` factory in `chndb-base.jsonnet`.

**Source**: `chndb-base.jsonnet:8–121`

### Header fields

| Field | Source | Value | Role |
|-------|--------|-------|------|
| `tick` | `params.daq.tick` | `0.5 µs` | Sampling interval; sets the frequency axis. |
| `nsamples` | `params.nf.nsamples` (= `params.daq.nticks`) | `6000` | Frequency-domain bins. Freqmask notch bins (169–173, 513–516) are expressed in this binning — **must be recomputed if `nsamples` changes**. |

### Coherent groups

**Source**: `chndb-base.jsonnet:27–39`

60 groups per anode, one per FEMB:

| Plane | Groups | Channels per group | Global channel range (anode `n`) |
|-------|--------|--------------------|----------------------------------|
| U | 20 | 40 | cyclic: `n×2560 + (40u + shift + j) mod 800` for `j ∈ [0,39]` |
| V | 20 | 40 | cyclic: `n×2560 + 800 + (40v + shift + j) mod 800` for `j ∈ [0,39]` |
| W | 20 | 48 | `n×2560 + 1600 + w×48 .. n×2560 + 1600 + (w+1)×48 − 1` |

`shift` is controlled by the `coh_group_shift` parameter (default **3**).
The +3 offset corrects a FEMB-edge channel misassignment identified in
the run-027409 evt-0 APA-0 coherent-noise audit: the first 3 offline
channels of each FEMB block carry the bulk common mode of the
*previous* block, not their own.  Setting `coh_group_shift=0` recovers
the original (pre-fix) grouping.  W is unchanged (audit confirmed W is
clean).  The cyclic `mod 800` wrap is only active for group `u=19`
(offline channels 763–799 and 0–2); all other groups are contiguous and
identical to the shift=0 case for those group indices.

### Hard-coded bad channels

**Source**: `chndb-base.jsonnet:26`

36 channels permanently masked as `bad`:

```
2297, 5379, 5472, 5556, 5607, 5608, 5920, 5921, 6072, 7679,
2580, 2940, 3347, 3758, 3805, 3866, 4722, 9956, 9986, 9987,
9988, 7876, 9120, 9125, 9126, 9127, 9306, 9307, 9309, 9310,
9534, 10016, 10018, 10020, 10022, 10024
```

These are global channel IDs (not per-anode) and are the most
frequently updated field.

### Per-channel configuration (`channel_info`)

Entries processed in order; **last mention wins** per channel.

#### Default block (all 2560 channels of anode `n`)
**Source**: `chndb-base.jsonnet:38–66`

| Knob | Default | Consumed by | Notes |
|------|---------|-------------|-------|
| `nominal_baseline` | `2048.0` ADC | **Unused in current build** | Call site commented out (`ProtoduneHD.cxx:811`). |
| `gain_correction` | `1.0` | — | Not consumed by PDHD NF in practice. |
| `response_offset` | `0.0` ticks | `PDHDCoherentNoiseSub` | Time offset of `respec` waveform; per-plane values set in plane overrides. |
| `pad_window_front` | `10` ticks | `PDHDCoherentNoiseSub` | Pre-ROI padding in signal protection. |
| `pad_window_back` | `10` ticks | `PDHDCoherentNoiseSub` | Post-ROI padding. |
| `decon_limit` | `0.02` | `PDHDCoherentNoiseSub` | Threshold for median-deconv ROI detection in `SignalProtection`. |
| `decon_limit1` | `0.09` | `PDHDCoherentNoiseSub` | Threshold for per-channel deconv ROI gate in `Subtract_WScaling`. |
| `adc_limit` | `60` (was `15`) | `PDHDCoherentNoiseSub` | Upper bound on signal-protection limit (ADC domain). |
| `min_adc_limit` | `200` (was `50`) | `PDHDCoherentNoiseSub` | Hard cap on signal-protection limit. |
| `roi_min_max_ratio` | `0.8` | `PDHDCoherentNoiseSub` | `|min|/max` ratio gate for per-channel ROI qualification. |
| `min_rms_cut` | `1.0` | **Unused in current build** | `NoisyFilterAlg` block commented out (`ProtoduneHD.cxx:859–870`). |
| `max_rms_cut` | `30.0` | **Unused in current build** | Same — no `noisy` tag is generated by `PDHDOneChannelNoise`. |
| `rcrc` | `1.1 ms` | **Unused in current build** | RC+RC time constant; call site commented out (`ProtoduneHD.cxx:817–820`). Note: the comment "1.1 for collection, 3.3 for induction" is informational only — there is no per-plane override so all planes get 1.1 ms. |
| `rc_layers` | `1` | **Unused in current build** | Same — dead configuration. |
| `reconfig` | `{}` | — | Empty; no electronics-response reconfiguration is set. |
| `freqmasks` | `[]` | **Unused by PDHDOneChannelNoise** | Populates the `noise` spectrum in chndb, but `PDHDOneChannelNoise::apply()` never calls `noise(ch)`. |
| `response` | `{}` | `PDHDCoherentNoiseSub` | Per-channel field-response waveform; overridden per plane below. Empty on W → no deconvolution branch in coherent sub. |

#### U-plane override (channels `n×2560` .. `n×2560+799`)
**Source**: `chndb-base.jsonnet:68–85`

| Knob | Value | Notes |
|------|-------|-------|
| `freqmasks` | `[{value:1.0, lobin:0, hibin:5999}, {value:0.0, lobin:169, hibin:173}, {value:0.0, lobin:513, hibin:516}]` | Two notch bands: ≈56.3–57.7 kHz and ≈171.0–172.0 kHz. **Configured but not applied by `PDHDOneChannelNoise`** (see above). |
| `response` | `{waveform: handmade.u_resp, waveformid: wc.Ulayer}` | Hard-coded 200-sample U-plane average field response from `chndb-resp.jsonnet:19`. |
| `response_offset` | `120` ticks | Negative-peak offset of the U response; used in `SignalProtection` and `Subtract_WScaling`. |
| `pad_window_front` | `20` ticks | Wider front pad than default 10. |
| `decon_limit` | `0.02` | Same as default. |
| `decon_limit1` | `0.07` | Slightly lower than default (0.09). |
| `roi_min_max_ratio` | `3.0` | Stricter ROI qualification on U (default 0.8). |

#### V-plane override (channels `n×2560+800` .. `n×2560+1599`)
**Source**: `chndb-base.jsonnet:87–103`

| Knob | Value | Notes |
|------|-------|-------|
| `freqmasks` | Same two notch bands as U. | **Configured but not applied by `PDHDOneChannelNoise`**. |
| `response` | `{waveform: handmade.v_resp, waveformid: wc.Vlayer}` | Hard-coded 200-sample V-plane response from `chndb-resp.jsonnet:61`. |
| `response_offset` | `124` ticks | |
| `decon_limit` | `0.01` | Lower than U — V is more sensitive. |
| `decon_limit1` | `0.08` | |
| `roi_min_max_ratio` | `1.5` | Between U (3.0) and default (0.8). |

#### W-plane override (channels `n×2560+1600` .. `n×2560+2559`)
**Source**: `chndb-base.jsonnet:111–118`

| Knob | Value | Notes |
|------|-------|-------|
| `nominal_baseline` | `400.0` ADC | Collection wires have a lower pedestal. Unused in current build (see above). |
| `decon_limit` | `0.05` | Higher than induction planes. |
| `decon_limit1` | `0.08` | |
| `response` | `{}` (inherited default) | No deconvolution in coherent sub for W — only the median-only subtraction path runs. |
| `freqmasks` | `[]` (inherited default, inactive) | A commented-out harmonic-notch template (`chndb-base.jsonnet:105–109`) is available if coherent harmonics appear on W. |

### Per-channel response waveforms

**Source**: `chndb-resp.jsonnet`

`u_resp` (line 19) and `v_resp` (line 61) are **hard-coded numerical
arrays of 200 samples** — the 1D average induction-plane field-response
waveforms used by `PDHDCoherentNoiseSub` for deconvolution-based signal
protection and per-channel ROI qualification.

**Origin**: the header comment in `chndb-resp.jsonnet:1–17` documents
how they were derived: by summing all Garfield path currents for the
target plane in the `FieldResponse` object (`fravg.planes[2]` for V)
over 6000 ticks in `OmnibusSigproc.cxx`.  **They are not recomputed
from any runtime input file**; the values are baked into the
configuration.

If the field-response file (`np04hd-garfield-6paths-mcmc-bestfit.json.bz2`,
`params.jsonnet:152`) is updated, `u_resp` / `v_resp` must be
re-derived, and the corresponding `response_offset` values (120/U,
124/V in `chndb-base.jsonnet`) must be re-checked.

W-plane uses `response: {}` → `PDHDCoherentNoiseSub` skips the
deconvolution branch entirely and falls back to the simpler
median-subtraction path.

---

## Decon limits summary

All knobs below are consumed by `PDHDCoherentNoiseSub` only.

| Knob | Used in | chndb-base value | C++ fallback | Effect |
|------|---------|------------------|--------------|--------|
| `decon_limit` | `SignalProtection` | U:0.02, V:0.01, W:0.05 | 0.02 | Threshold on deconvolved median height to flag a bin as "signal" in the ADC→ROI pass. |
| `decon_limit1` | `Subtract_WScaling` | U:0.07, V:0.08, W:0.08 (default: 0.09) | 0.08 | Per-channel deconv ROI gate — peak must exceed this to be deemed real signal. |
| `decon_lf_cutoff` | ~~`SignalProtection`~~ | *(not set — C++ default 0.08, unused)* | 0.08 | **No longer consumed by `PDHDCoherentNoiseSub`** after the `IFilterWaveform` refactor. The low-frequency cutoff is now encoded in `LfFilter ROI_tighter_lf` (τ=0.08 MHz in `sp-filters.jsonnet`). The chndb field and C++ accessor remain for MicroBooNE/SBND compatibility. |
| `adc_limit` | `SignalProtection` | 60 (raised from default 0) | 0.0 | Upper bound on the ADC-domain protection limit: `max(protection_factor·rms, adc_limit)`. |
| `min_adc_limit` | `SignalProtection` | 200 (raised from 50) | 50 | Hard cap: `limit = min(limit, min_adc_limit)`. |
| `protection_factor` | `SignalProtection` | not set (C++ fallback) | 5.0 | Multiplier on median RMS for the ADC-domain threshold. |
| `roi_min_max_ratio` | `Subtract_WScaling` | U:3.0, V:1.5, W:0.8 (default: 0.8) | 0.8 | Max allowed `|min|/max` ratio for a per-channel ROI to qualify as real signal. |

---

## Output

**Source**: `wct-nf-sp.jsonnet:54–66`

```jsonnet
FrameFileSink  'rawframesink{N}'
  outname:   '{raw_prefix}-anode{N}.tar.bz2'
  tags:      ['raw{N}']
  digitize:  false   // float traces, not re-quantized
  masks:     true    // channel masks included
```

The NF output frame then flows directly into the SP pipeline.

---

## Tuning hot-spots

### Live (actually active) knobs

| Priority | Knob | Location | When to touch |
|----------|------|----------|---------------|
| 1 | `bad` channel list | `chndb-base.jsonnet:26` | Every new run; channels that are dead, shorted, or stuck. |
| 2 | `decon_limit` | `chndb-base.jsonnet:45, 83, 100, 115` | If coherent-sub over/under-protects real signal in the median deconv pass. |
| 3 | `decon_limit1` | `chndb-base.jsonnet:46, 83, 101, 116` | If per-channel ROI qualification is too tight or loose. |
| 4 | `roi_min_max_ratio` | per-plane blocks | If bipolar coherent noise leaks through (lower) or asymmetric signals are mis-flagged (raise). |
| 5 | `pad_window_front/back` | `chndb-base.jsonnet:43–44, 81` | If signal edges are clipped or noise bleeds into ROI pad. |
| 6 | `adc_limit` / `min_adc_limit` | `chndb-base.jsonnet:47–48` | If signal-protection thresholds need adjusting for gain changes. |
| 7 | `rms_threshold` on CoherentNoiseSub | `nf.jsonnet:27` | Raise (e.g. 5.0) when large-signal events corrupt the group median; also enables adaptive `decon_limit1`. |
| 8 | `maskmap` | `nf.jsonnet:42` | Uncomment `sticky`/`ledge` mappings if those artefact types are enabled in the future. |
| 9 | Response waveforms (`u_resp`, `v_resp`) | `chndb-resp.jsonnet:19, 61` | Re-derive when a new field-response calculation is adopted. |
| 10 | `response_offset` | `chndb-base.jsonnet:80, 99` | Must be re-tuned with new response waveforms. |
| 11 | `coh_group_shift` | `chndb-base.jsonnet` (function signature) | Controls the cyclic offset of U/V FEMB group boundaries. Default 3 (corrected); set to 0 to revert to the original grouping. |

### Configured but currently inert

These fields are present in `chndb-base.jsonnet` and will take effect
*if* the corresponding code paths are un-commented in
`ProtoduneHD.cxx`, but are **not active** in the current build:

| Knob | Location | Would do |
|------|----------|----------|
| `nominal_baseline` | `chndb-base.jsonnet:40, 114` | ADC pedestal subtracted before FFT. |
| `rcrc` / `rc_layers` | `chndb-base.jsonnet:54–55` | RC+RC undershoot correction filter. |
| `freqmasks` (U/V notches at bins 169–173, 513–516) | `chndb-base.jsonnet:71–75, 90–94` | Notch-filter ≈57 kHz and ≈171 kHz noise per channel. |
| `min_rms_cut` / `max_rms_cut` | `chndb-base.jsonnet:50–51` | Tag channels as `noisy` by waveform RMS. |

---

## Source file index

| File | Role | Key lines |
|------|------|-----------|
| `pdhd/run_nf_sp_evt.sh` | Shell driver | L110–119 (wire-cell invocation) |
| `pdhd/wct-nf-sp.jsonnet` | Jsonnet entry point | L39–47 (chndb + NF assembly); L54–66 (raw-frame sink) |
| `cfg/pgrapher/experiment/pdhd/nf.jsonnet` | NF pnode factory | L9–18 (`PDHDOneChannelNoise`); L19–29 (`PDHDCoherentNoiseSub`); L31–60 (`OmnibusNoiseFilter`) |
| `cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet` | Channel DB content | L20–22 (groups); L26 (bad list); L38–66 (default); L68–85 (U); L87–103 (V); L111–118 (W) |
| `cfg/pgrapher/experiment/pdhd/chndb-resp.jsonnet` | Hard-coded response waveforms | L19 (`u_resp`, 200 samples); L61 (`v_resp`, 200 samples) |
| `cfg/pgrapher/experiment/pdhd/params.jsonnet` | Detector parameters | L96 (`nticks=6000`); L150 (wires file); L163–166 (noise spectrum, gain-dependent) |
| `cfg/pgrapher/common/params.jsonnet` | Inherited defaults | `nf.nsamples = daq.nticks`; `daq.tick = 0.5 µs` |
| `sigproc/src/ProtoduneHD.cxx` | **Implementation** | L808–875 (`OneChannelNoise::apply`); L891–966 (`CoherentNoiseSub::apply`); L281–467 (`SignalProtection`); L58–279 (`Subtract_WScaling`); L514–641 (adaptive-baseline helpers) |
| `sigproc/src/Diagnostics.cxx` | Partial/RC detector | L15–32 (`Partial::operator()`) |
| `sigproc/inc/WireCellSigProc/Diagnostics.h` | Partial API | L27–37 (default `nfreqs=4`, `maxpower=6000`) |
