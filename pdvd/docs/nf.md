# Noise Filtering (NF) — ProtoDUNE-VD

This document describes the NF stage driven by `run_nf_sp_evt.sh` →
`wct-nf-sp.jsonnet`. For the overall workflow see
[nf_sp_workflow.md](nf_sp_workflow.md). For SP see [sp.md](sp.md).

## Overview

The NF stage is a single WireCell `OmnibusNoiseFilter` pnode that hosts
three successive filter passes run per anode:

1. **Per-channel** — baseline subtraction + noisy-channel detection
2. **Coherent group** — common-mode noise subtraction
3. **Shield coupling** (top anodes only) — capacitive coupling from the
   shield plane on the top U-plane

**Input tag**: `orig` (raw ADC from art, written by `wcls-nf-sp-out.jsonnet`)
**Output tag**: `raw<N>` where N = anode ident (0–7)

The output frame is written to `protodune-sp-frames-raw-anode<N>.tar.bz2`
by a `FrameFileSink` tap (`wct-nf-sp.jsonnet:61–73`), then the same frame
continues downstream to SP.

## Step 0 — Resampler (bottom anodes 0–3 only)

| Parameter | Value |
|-----------|-------|
| Type | `Resampler` |
| When | `use_resampler == "true"` AND anode index `n < 4` |
| `period` | `500 ns` |
| `time_pad` | `"linear"` |

Bottom-drift (TDE) CRPs are digitized at a tick slightly different from
500 ns. The Resampler resamples to the 500 ns grid that the SP field
response files assume. Top-CRP anodes (ident ≥ 4) are already at 500 ns
and skip this node.

Source: `toolkit/cfg/pgrapher/common/resamplers.jsonnet:6–16`
Condition: `wct-nf-sp.jsonnet:111`

## Step 1 — PDVDOneChannelNoise (per-channel)

**Type**: `PDVDOneChannelNoise`
**C++ class**: `WireCell::SigProc::PDVD::OneChannelNoise`
**Source**: `toolkit/sigproc/src/ProtoduneVD.cxx` (~lines 780–883)
**Config in**: `toolkit/cfg/pgrapher/experiment/protodunevd/nf.jsonnet:8–15`

### What it does (in order)

1. **FFT → kill DC bin** — sets `spectrum.front() = 0` to remove any
   constant offset in frequency domain.
2. **6σ-clipped median baseline** — computes the median of the waveform
   after iteratively excluding samples more than 6σ from the running
   median. Subtracts the result to pedestal-centre the trace.
3. **Adaptive baseline for partial channels** — for channels flagged as
   `is_partial` (stuck-RC / RC-coupling artefact), runs
   `SignalFilter` + `RawAdaptiveBaselineAlg` + `RemoveFilterFlags` to
   robustly subtract a slowly-varying baseline.
4. **Noisy-channel tagging** via `NoisyFilterAlg`:
   computes the per-channel RMS after baseline subtraction; if
   `rms < min_rms_cut` or `rms > max_rms_cut` the channel is tagged
   `noisy`.

### Tunable knobs

These live in `chndb-base.jsonnet` `channel_info` defaults
(`chndb-base.jsonnet:406–442`) and can be overridden per channel:

| Knob | Default | Effect |
|------|---------|--------|
| `nominal_baseline` | `2048.0` ADC | Starting baseline value; the algorithm corrects away from this |
| `min_rms_cut` | `1.0` | Channels with RMS below this → flagged `noisy` (dead-channel proxy) |
| `max_rms_cut` | `60.0` | Channels with RMS above this → flagged `noisy` (high-noise proxy) |
| `rcrc` | `1.1 ms` | RC-RC time constant used to build the spectral correction filter (1.1 for collection, 3.3 for induction; RC correction is currently commented out in ProtoduneVD.cxx:820–823) |
| `rc_layers` | `0` | Number of RC filter layers (0 = disabled) |
| `reconfig` | `{}` | Override per-channel spectral masking |
| `freqmasks` | `[]` | List of frequency-band masks to zero out (e.g., narrow-band noise lines) |

To tighten or relax noisy-channel cuts: edit `min_rms_cut` / `max_rms_cut`
in `chndb-base.jsonnet:424–425`.

## Step 2 — PDVDCoherentNoiseSub (group coherent subtraction)

**Type**: `PDVDCoherentNoiseSub`
**C++ class**: `WireCell::SigProc::PDVD::CoherentNoiseSub`
**Source**: `toolkit/sigproc/src/ProtoduneVD.cxx` (~line 885)
**Config in**: `nf.jsonnet:16–24`, groups from `chndb-base.jsonnet:30–391`

### What it does

For each channel group (typically one FEMB or one CRP conduit):
1. Computes the **median waveform** across all channels in the group
   (a sample-by-sample median to capture the common-mode shape).
2. Runs **signal protection** (`SignalProtection`): a low-frequency
   deconvolution step that identifies samples likely to contain real
   charge signals and excludes them from the common-mode estimate,
   preventing signal subtraction.
3. Subtracts the scaled common-mode median from every channel in the
   group (`Subtract_WScaling`).

### Tunable knobs

| Knob | Set in | Default | Effect |
|------|--------|---------|--------|
| `rms_threshold` | `nf.jsonnet:22` | `0.0` | Groups whose overall RMS is below this are skipped |
| `decon_limit` | `chndb-base.jsonnet:421` | `0.02` | Signal-protection deconvolution low threshold |
| `decon_limit1` | `chndb-base.jsonnet:422` | `0.09` | Signal-protection deconvolution high threshold |
| `adc_limit` | `chndb-base.jsonnet:423` | `15` | ADC amplitude threshold in signal protection |
| `roi_min_max_ratio` | `chndb-base.jsonnet:423` | `0.8` | Ratio used in ROI protection logic |

### Channel groups

`chndb-base.jsonnet:30–391` contains a hardcoded 2-D list of channel
groups (`groups`). Each sub-list is one coherent-noise group (16–48
channels corresponding to a FEMB/CRP conduit). These groups are the
primary place to update if hardware changes alter which channels share
common-mode noise.

## Step 3 — PDVDShieldCouplingSub (top anodes only)

**Type**: `PDVDShieldCouplingSub`
**C++ class**: `WireCell::SigProc::PDVD::ShieldCouplingSub`
**Source**: `toolkit/sigproc/src/ProtoduneVD.cxx` (~line 1207)
**Config in**: `nf.jsonnet:25–35`
**Applies to**: anodes with `ident > 3` (top CRPs) only (`nf.jsonnet:60–65`)

### What it does

Removes capacitive coupling pickup from the shield plane onto the
**top U-plane** strips. The algorithm is adapted from the `lardon`
noise filter and uses per-strip physical lengths (loaded from
`PDVD_strip_length.json.bz2`, `params.jsonnet:158`) to weight the
subtraction correctly for strips of different geometry.

### Tunable knobs

| Knob | Set in | Default | Effect |
|------|--------|---------|--------|
| `rms_threshold` | `nf.jsonnet:33` | `0.0` | Skip group if RMS below threshold |
| `strip_length` | `nf.jsonnet:32` / `params.jsonnet:158` | `PDVD_strip_length.json.bz2` | Per-strip length weighting file |
| `top_u_groups` | `chndb-base.jsonnet:393–396` | Two channel ranges per top anode | Which channels form the top-U groups subject to shield coupling removal |

`top_u_groups` at `chndb-base.jsonnet:393–396`:
```jsonnet
top_u_groups:
  [std.range(n*3072, n*3072+475) for n in std.range(2,3)]
  +[std.range(n*3072+476, n*3072+951) for n in std.range(2,3)]
```

## OmnibusNoiseFilter wrapper

The three filter passes are hosted by a single `OmnibusNoiseFilter` pnode
(`nf.jsonnet:37–76`). Key configuration:

| Key | Value | Meaning |
|-----|-------|---------|
| `nticks` | `0` | Don't force waveform length; inherit from incoming frame |
| `maskmap` | `{sticky:"bad", ledge:"bad", noisy:"bad"}` | Merge all per-channel flag types into unified `bad` mask consumed by SP |
| `channel_filters` | `[PDVDOneChannelNoise]` | Per-channel pass runs first |
| `multigroup_chanfilters` | `[{grouped, groups}, ...]` + shield (top only) | Group passes run after per-channel |
| `grouped_filters` | `[]` | Unused; coherent sub is wired via `multigroup_chanfilters` |
| `intraces` | `'orig'` | Input frame tag |
| `outtraces` | `'raw<N>'` | Output frame tag |

## OmniChannelNoiseDB (`chndb-base.jsonnet`)

The `OmniChannelNoiseDB` instance (`chndbperfect<N>` in
`wct-nf-sp.jsonnet:42–46`) supplies per-channel metadata to all three
filter modules. Key content:

| Field | Location | Description |
|-------|----------|-------------|
| `tick` | `params.daq.tick` = 500 ns | Sampling period |
| `nsamples` | `params.nf.nsamples` = 6000 | FFT size (must equal waveform length) |
| `groups` | `chndb-base.jsonnet:30–391` | Coherent-noise groupings (2-D list of channel IDs) |
| `top_u_groups` | `chndb-base.jsonnet:393–396` | Shield-coupling groups for top U plane |
| `bad` | `chndb-base.jsonnet:398–401` | Hard-coded bad channels (19 IDs) |
| `channel_info` | `chndb-base.jsonnet:406–442` | Per-channel defaults + optional per-channel overrides |

To add a new bad channel: append its ID to the `bad` list at
`chndb-base.jsonnet:399–401`.

To override an individual channel's RMS cuts or decon limits: add an
entry to `channel_info` after the default block at line 441 with
`channels: [<id>]` and the override values.

## Output

After the NF stage the frame carries trace tag `raw<N>`.
A `FrameFileSink` tap writes it to disk (`wct-nf-sp.jsonnet:61–73`):

```jsonnet
{
  type: 'FrameFileSink',
  name: 'rawframesink<N>',
  data: {
    outname: '<raw_prefix>-anode<N>.tar.bz2',
    tags: ['raw<N>'],
    digitize: false,   // floating-point ADC, not re-digitized
    masks: false,      // no channel-mask metadata in this file
  }
}
```

`digitize: false` means the values are floating-point ADC counts
(pedestal subtracted), not integers. The SP stage picks up the frame
on the main path after the tap.

## Source file index

| File | Purpose |
|------|---------|
| `wct-nf-sp.jsonnet` (pdvd/) | Top-level pipeline: builds per-anode graphs |
| `toolkit/cfg/pgrapher/experiment/protodunevd/nf.jsonnet` | Returns OmnibusNoiseFilter pnode per anode |
| `toolkit/cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet` | Channel DB: groups, bad channels, per-channel defaults |
| `toolkit/cfg/pgrapher/experiment/protodunevd/params.jsonnet` | Detector parameters (tick, nticks, strip_length file) |
| `toolkit/cfg/pgrapher/common/resamplers.jsonnet` | Resampler pnode construction |
| `toolkit/sigproc/src/ProtoduneVD.cxx` | C++ impl of PDVD NF modules |
| `toolkit/sigproc/inc/WireCellSigProc/ProtoduneVD.h` | PDVD NF class declarations |
| `toolkit/sigproc/src/OmnibusNoiseFilter.cxx` | OmnibusNoiseFilter driver |
