# Noise Filtering (NF) — ProtoDUNE-HD

This document covers the NF configuration used by the standalone
[`run_nf_sp_evt.sh`](../run_nf_sp_evt.sh) pipeline.
See also [sp.md](sp.md) and [nf_sp_workflow.md](nf_sp_workflow.md).

---

## Overview

Each of the four APAs gets its own independent `OmnibusNoiseFilter` pnode.
Inside that pnode the noise filtering is a two-step composition:

1. **PDHDOneChannelNoise** — per-channel operations (baseline, freq-masks, RMS tagging).
2. **PDHDCoherentNoiseSub** — grouped coherent subtraction (per-FEMB median).

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
    },
};
```

**What it does (in order)**:
- Reads per-channel parameters from `OmniChannelNoiseDB` (`chndbobj`).
- Fixes partial-ADC / sticky-bit artefacts (using `adc_limit`, `min_adc_limit`).
- Subtracts the per-channel `nominal_baseline` (ADC counts).
- Applies FFT-based frequency-domain masking (`freqmasks`) per channel.
- Applies the per-channel deconvolution-based response correction using the
  `response` waveform and `response_offset`.
- Tags channels whose waveform RMS falls outside `[min_rms_cut, max_rms_cut]`
  as `noisy` or `lf_noisy`.

All tunable knobs for this step are in the channel-DB `channel_info` entries
(see §[OmniChannelNoiseDB](#omnichannel-noise-db-chndb-basejsonnet) below).

---

## Step 2 — PDHDCoherentNoiseSub (grouped coherent subtraction)

**Source**: `nf.jsonnet:19–29`

```jsonnet
local grouped = {
    type: 'PDHDCoherentNoiseSub',
    name: name,
    uses: [dft, chndbobj, anode],
    data: {
        noisedb:       wc.tn(chndbobj),
        anode:         wc.tn(anode),
        dft:           wc.tn(dft),
        rms_threshold: 0.0,
    },
};
```

**What it does**: computes the per-tick median across channels in each
coherent group and subtracts it from every channel in that group.  Groups
follow FEMB boundaries (see `groups` in §chndb).

### Tunable knobs

| Knob | Set in | Default | Effect |
|------|--------|---------|--------|
| `rms_threshold` | `nf.jsonnet:27` | `0.0` | Channels whose RMS exceeds this value are excluded from the coherent-median computation. `0.0` = no exclusion. Raise (e.g. 5.0) to protect high-signal channels from biasing the group median. |

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
| `nticks` | `nf.jsonnet:37` | `0` | Force waveform length in ticks. `0` = inherit from input frame. Set nonzero to truncate or extend. |
| `maskmap` | `nf.jsonnet:42` | `{noisy:"bad", lf_noisy:"bad"}` | Remaps channel-status categories. Channels mapped to `"bad"` have their data zeroed. A richer alternative `{sticky:"bad", ledge:"bad", noisy:"bad"}` is commented out in the file. |
| `intraces` | `nf.jsonnet:54` | `''` (wildcard) | Input frame tag selector. `''` accepts all traces. Set to e.g. `'orig%d' % n` if orig frames carry a numbered tag. |
| `outtraces` | `nf.jsonnet:55` | `'raw%d' % n` | Tag written on the output traces (e.g. `raw0`). Must match the `tags` list of `rawframesink{N}` in `wct-nf-sp.jsonnet:62`. |

---

## OmniChannel Noise DB (`chndb-base.jsonnet`)

The channel DB is instantiated once per anode in `wct-nf-sp.jsonnet:39–44`
as `OmniChannelNoiseDB` named `ocndbperfect{N}`.  Its contents are produced
by the `base(params, anode, field, n)` factory in
`chndb-base.jsonnet`.

**Source**: `chndb-base.jsonnet:8–121`

### Header fields

| Field | Source | Value | Role |
|-------|--------|-------|------|
| `tick` | `params.daq.tick` | `0.5 µs` | Sampling interval; sets the frequency axis for FFT filters. |
| `nsamples` | `params.nf.nsamples` | `6000` | Number of FFT bins. Freqmask notch bins (169–173, 513–516) are expressed in this binning — **must be recomputed if `nsamples` changes**. |

### Coherent groups

**Source**: `chndb-base.jsonnet:20–22`

Each anode has 60 coherent-subtraction groups corresponding to FEMB
boundaries:

| Plane | Groups | Channels per group | Global channel range (anode `n`) |
|-------|--------|--------------------|----------------------------------|
| U | 20 | 40 | `n×2560 + u×40 .. n×2560 + (u+1)×40 − 1` |
| V | 20 | 40 | `n×2560 + 800 + v×40 .. n×2560 + 800 + (v+1)×40 − 1` |
| W | 20 | 48 | `n×2560 + 1600 + w×48 .. n×2560 + 1600 + (w+1)×48 − 1` |

U and V planes have 40 wires per FEMB; W has 48.  These groups are the only
operands of `PDHDCoherentNoiseSub`.  Change them only if the FEMB-to-channel
mapping changes.

### Hard-coded bad channels

**Source**: `chndb-base.jsonnet:26`

36 channels are permanently masked as `bad` regardless of run:

```
2297, 5379, 5472, 5556, 5607, 5608, 5920, 5921, 6072, 7679,
2580, 2940, 3347, 3758, 3805, 3866, 4722, 9956, 9986, 9987,
9988, 7876, 9120, 9125, 9126, 9127, 9306, 9307, 9309, 9310,
9534, 10016, 10018, 10020, 10022, 10024
```

These are global channel IDs (not per-anode).  This is the most
frequently updated field — new runs commonly need additions or removals.

### Per-channel configuration (`channel_info`)

Entries are processed in order; **last mention wins** for each channel.
`chndb-base.jsonnet:31–120`

#### Default block (all 2560 channels of anode `n`)
**Source**: `chndb-base.jsonnet:38–66`

| Knob | Default | Effect |
|------|---------|--------|
| `nominal_baseline` | `2048.0` ADC | Subtracted from every waveform before FFT processing. Must reflect the actual ADC pedestal. |
| `gain_correction` | `1.0` | Amplitude scaling applied per channel. |
| `response_offset` | `0.0` ticks | Time offset of the per-channel response waveform. |
| `pad_window_front` | `10` ticks | Number of ticks to pad before each identified signal region. |
| `pad_window_back` | `10` ticks | Number of ticks to pad after each identified signal region. |
| `decon_limit` | `0.02` | Lower threshold for deconvolution-based ROI identification (primary). |
| `decon_limit1` | `0.09` | Upper threshold for deconvolution-based ROI identification (secondary). |
| `adc_limit` | `60` | Max ADC deviation considered non-saturated (was `15`; raised for HD). |
| `min_adc_limit` | `200` | Min ADC range for saturation/partial-ADC detection (was `50`; raised for HD). |
| `roi_min_max_ratio` | `0.8` | Ratio of ROI minimum to maximum used in ROI qualification. |
| `min_rms_cut` | `1.0` | Channels with waveform RMS below this are tagged `lf_noisy`. |
| `max_rms_cut` | `30.0` | Channels with waveform RMS above this are tagged `noisy`. |
| `rcrc` | `1.1 ms` | RC+RC time constant used to build the `rcrc` spectrum; `1.1 ms` for collection, `3.3 ms` for induction. |
| `rc_layers` | `1` | Number of RC filter layers (default in common code is `2`). |
| `reconfig` | `{}` | Empty — no additional frequency reconfiguration. |
| `freqmasks` | `[]` | No per-channel FFT masks at the default level; overridden per plane below. |
| `response` | `{}` | No per-channel response waveform at the default level; overridden per plane below. |

#### U-plane override (channels `n×2560` .. `n×2560+799`)
**Source**: `chndb-base.jsonnet:68–85`

| Knob | Value | Notes |
|------|-------|-------|
| `freqmasks` | `[{value:1.0, lobin:0, hibin:5999}, {value:0.0, lobin:169, hibin:173}, {value:0.0, lobin:513, hibin:516}]` | Pass-all floor + two notch bands. Bin 169–173 and 513–516 in a 6000-bin FFT (0.5 µs tick) correspond to frequencies ≈56 kHz and ≈171 kHz. |
| `response` | `{waveform: handmade.u_resp, waveformid: wc.Ulayer}` | Hard-coded average U-plane response from `chndb-resp.jsonnet:19`. |
| `response_offset` | `120` ticks | Negative-peak offset of the U response. |
| `pad_window_front` | `20` ticks | Wider front pad than the default 10. |
| `decon_limit` | `0.02` | Same as default. |
| `decon_limit1` | `0.07` | Slightly lower than default (0.09). |
| `roi_min_max_ratio` | `3.0` | Much higher than default (0.8) — stricter ROI qualification on U. |

#### V-plane override (channels `n×2560+800` .. `n×2560+1599`)
**Source**: `chndb-base.jsonnet:87–103`

| Knob | Value | Notes |
|------|-------|-------|
| `freqmasks` | Same two notch bands as U (bins 169–173, 513–516) | |
| `response` | `{waveform: handmade.v_resp, waveformid: wc.Vlayer}` | From `chndb-resp.jsonnet:61`. |
| `response_offset` | `124` ticks | |
| `decon_limit` | `0.01` | Lower than U and default — V is more sensitive. |
| `decon_limit1` | `0.08` | |
| `roi_min_max_ratio` | `1.5` | Between U (3.0) and default (0.8). |

#### W-plane override (channels `n×2560+1600` .. `n×2560+2559`)
**Source**: `chndb-base.jsonnet:111–118`

| Knob | Value | Notes |
|------|-------|-------|
| `nominal_baseline` | `400.0` ADC | Collection wires have a much lower pedestal than induction. |
| `decon_limit` | `0.05` | Higher than induction planes. |
| `decon_limit1` | `0.08` | |
| `freqmasks` | *(not set — uses default empty list)* | A commented-out harmonic notch list (`chndb-base.jsonnet:105–109`) provides a template if coherent harmonics appear on W in future data. |

### Per-channel response waveforms

**Source**: `chndb-resp.jsonnet`

The `u_resp` (line 19) and `v_resp` (line 61) fields are hard-coded
average induction-plane response waveforms used by `PDHDOneChannelNoise`
for deconvolution-based ROI identification.  If the field-response model
is updated (e.g. new Garfield calculation), these waveforms should be
re-derived and replaced in `chndb-resp.jsonnet`.

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

## Tuning hot-spots (ranked)

| Priority | Knob | Location | When to touch |
|----------|------|----------|---------------|
| 1 | `bad` channel list | `chndb-base.jsonnet:26` | Every new run; channels that are dead, shorted, or stuck. |
| 2 | `min_rms_cut` / `max_rms_cut` | `chndb-base.jsonnet:50–51` | After a gain change (noise level scales with gain); must stay consistent with the chosen noise-spectrum file. |
| 3 | `freqmasks` bin ranges | `chndb-base.jsonnet:71–75, 90–94` | If new coherent noise frequencies appear; recompute bins as `f × nsamples × tick` (e.g. 56 kHz × 6000 × 0.5 µs ≈ bin 168). |
| 4 | `nominal_baseline` | `chndb-base.jsonnet:40` (2048), `:114` (400 for W) | If ADC pedestals shift (e.g. new FEMB firmware or temperature change). |
| 5 | `decon_limit` / `decon_limit1` / `roi_min_max_ratio` | per-plane blocks | If NF ROI identification is too aggressive (cuts signal) or too loose (lets noise through). |
| 6 | `rms_threshold` on CoherentNoiseSub | `nf.jsonnet:27` | Raise (e.g. 5.0) when large-signal events corrupt the coherent median. |
| 7 | `maskmap` | `nf.jsonnet:42` | Uncomment `sticky`/`ledge` mappings if those artefact types are significant. |
| 8 | `pad_window_front/back` | `chndb-base.jsonnet:43–44, 81` | Widen if signal is being clipped at ROI edges. |
| 9 | `adc_limit` / `min_adc_limit` | `chndb-base.jsonnet:47–48` | Adjust saturation/clipping thresholds if large-signal channels are mishandled. |
| 10 | Response waveforms (`u_resp`, `v_resp`) | `chndb-resp.jsonnet:19, 61` | Re-derive when a new field-response calculation is adopted. |
| 11 | `groups` | `chndb-base.jsonnet:20–22` | Only if FEMB-to-channel mapping changes in hardware. |
| 12 | `rcrc` / `rc_layers` | `chndb-base.jsonnet:54–55` | Only if electronics RC-filter assumptions change. |

---

## Source file index

| File | Role | Key lines |
|------|------|-----------|
| `wcp-porting-img/pdhd/run_nf_sp_evt.sh` | Shell driver | L84–93 (wire-cell invocation) |
| `wcp-porting-img/pdhd/wct-nf-sp.jsonnet` | Jsonnet entry point | L39–47 (chndb + NF assembly); L54–66 (raw-frame sink) |
| `toolkit/cfg/pgrapher/experiment/pdhd/nf.jsonnet` | NF pnode factory | L9–18 (`PDHDOneChannelNoise`); L19–29 (`PDHDCoherentNoiseSub`); L31–60 (`OmnibusNoiseFilter`) |
| `toolkit/cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet` | Channel DB content | L20–22 (groups); L26 (bad list); L38–66 (default); L68–85 (U); L87–103 (V); L111–118 (W) |
| `toolkit/cfg/pgrapher/experiment/pdhd/chndb-resp.jsonnet` | Hard-coded response waveforms | L19 (`u_resp`); L61 (`v_resp`) |
| `toolkit/cfg/pgrapher/experiment/pdhd/params.jsonnet` | Detector parameters | L96 (`nticks=6000`); L150 (wires file); L163–166 (noise spectrum, gain-dependent) |
| `toolkit/cfg/pgrapher/common/params.jsonnet` | Inherited defaults | `nf.nsamples = daq.nticks`; `daq.tick = 0.5 µs` |
