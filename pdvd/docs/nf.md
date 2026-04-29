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
| When | `reality == "data"` AND anode index `n < 4` (pass `-r sim` to skip) |
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
**Source**: `toolkit/sigproc/src/ProtoduneVD.cxx` (apply body: lines 810–881)
**Config in**: `toolkit/cfg/pgrapher/experiment/protodunevd/nf.jsonnet:8–15`

### What it does (in order)

1. **FFT → kill DC bin** — sets `spectrum.front() = 0` to remove any
   constant offset in frequency domain.
2. **6σ-clipped median baseline** — computes the median of the waveform
   after iteratively excluding samples more than 6σ from the running
   median. Subtracts the result to pedestal-centre the trace.
3. **Adaptive baseline for partial channels** — the code block
   (`ProtoduneVD.cxx:846–862`) that calls
   `SignalFilter` + `RawAdaptiveBaselineAlg` + `RemoveFilterFlags` is
   gated by `is_partial` which is evaluated as
   `m_adaptive_baseline ? m_check_partial(spectrum) : false`
   (line 819). The `adaptive_baseline` config field defaults to `false`
   in C++ and is intentionally left at that default in PDVD's
   `nf.jsonnet`: PDVD hardware is **DC-coupled** (no RC capacitors),
   so the IS_RC heuristic (`m_check_partial`) has no physical meaning
   here. In MicroBooNE (`Microboone.cxx:963-1047`) IS_RC is the
   central gate that picks between RCRC deconvolution (intact RC) and
   adaptive baseline as a fallback (broken RC); both branches presuppose
   RC exists. Therefore no adaptive baseline runs and no `lf_noisy` tag
   is emitted (see [lf_noisy section](#lf_noisy-tagging) below).
4. **Noisy-channel tagging** via `NoisyFilterAlg`:
   `PDVD::SignalFilter(signal)` + `PDVD::NoisyFilterAlg(signal, min_rms, max_rms)`
   + `PDVD::RemoveFilterFlags(signal)` run at lines 867–869 (these are live).
   If `rms < min_rms_cut` or `rms > max_rms_cut` the channel is tagged
   `noisy` (line 874).

### Tunable knobs

These live in `chndb-base.jsonnet` `channel_info` defaults
(`chndb-base.jsonnet:466–500`) and can be overridden per channel:

| Knob | Default | Effect |
|------|---------|--------|
| `nominal_baseline` | `2048.0` ADC | Starting baseline value |
| `min_rms_cut` | per-plane (see below) | Channels with RMS below this → flagged `noisy` (dead-channel proxy) |
| `max_rms_cut` | per-plane (see below) | Channels with RMS above this → flagged `noisy` (high-noise proxy) |
| `adaptive_baseline` | `false` | When `true`, enables the IS_RC (`m_check_partial`) partial-RC heuristic to gate the adaptive baseline per channel. **Left at default `false` for PDVD**: hardware is DC-coupled, so the IS_RC test is physically meaningless (compare `Microboone.cxx:963-1047`) |
| `rcrc` | `1.1 ms` | RC-RC time constant — **not applied**: the `m_noisedb->rcrc(ch)` call is commented out (`ProtoduneVD.cxx:823–826`) |
| `rc_layers` | `0` | Number of RC filter layers — `0` would suppress it even if the call were live |
| `reconfig` | `{}` | Parsed by `OmniChannelNoiseDB` but **never consumed** by `PDVDOneChannelNoise` (no `m_noisedb->config(ch)` call in the PDVD per-channel filter; ignored silently) |
| `freqmasks` | `[]` | Per-channel frequency-domain notch filter. Multiplied into the channel spectrum at `ProtoduneVD.cxx:835–854` via `m_noisedb->noise(ch)` (skipped silently when the channel's mask is empty, the default). Use `wc.freqmasks_phys([f...], delta)` in jsonnet to specify physical frequencies; bins are resolved at runtime from `m_tick`/`m_nsamples` and conjugate-mirrored automatically. With `WIRECELL_LOG_LEVEL=debug`, emits `PDVDfreqmask ch=N zeroed K/N bins` per masked channel. |

#### RMS thresholds (PDVD-specific)

`chndb-base.jsonnet` emits per-anode-group, per-plane `channel_info` overrides
on top of the fallback global entry (`min_rms_cut: 1.0`, `max_rms_cut: 60.0`).
The overrides are appended at `chndb-base.jsonnet:513–529` and are last-mention-wins:

| Anode group | Plane | `min_rms_cut` | `max_rms_cut` |
|-------------|-------|---------------|---------------|
| Top (4–7) | U | 8.0 ADC (flat) | 30.0 ADC |
| Top (4–7) | V | 8.0 ADC (flat) | 30.0 ADC |
| Top (4–7) | W | 8.0 ADC (flat) | 30.0 ADC |
| Bottom (0–3) | W | 5.0 ADC (flat) | 15.0 ADC |
| Bottom (0–3) | U | linear in wire length (see below) | 15.0 ADC |
| Bottom (0–3) | V | linear in wire length (see below) | 15.0 ADC |

**Gain scaling**: ADC-domain thresholds (`min_rms_cut`, `max_rms_cut`,
`adc_limit`, `min_adc_limit`) are tuned for the **bottom** FE amplifier gain of
7.8 mV/fC and scaled by `gain_scale = params.elec.gain / (7.8 mV/fC)` for
bottom anodes (0–3). Deconvolved-domain thresholds (`decon_limit`,
`decon_limit1`) operate on the gain-normalised deconvolved output and are not
gain-scaled. Top electronics (anodes 4–7) use an external response file
(`elecs[1]`, `JsonElecResponse`); `gain_scale ≡ 1.0` for top anodes
(`chndb-base.jsonnet:27`).

**Linear-in-wire-length mode** (`type: 'linear_in_wirelength'`): a new
`OmniChannelNoiseDB` feature that resolves `min_rms_cut` per channel from
the channel's total summed wire length in cm. The formula is:

```
min_rms_cut(ch) = v0 + clamp((L_ch - l0) / (l1 - l0), 0, 1) * (v1 - v0)
```

with anchor points `(l0=0 cm, v0=2.6 ADC)` and `(l1=180 cm, v1=6.3 ADC)`,
clamped at both endpoints. Wire length `L_ch` is the sum of
`ray_length(wire->ray())` in cm over all wire segments for the channel,
computed from `m_anode->wires(ch)` and cached once per
`OmniChannelNoiseDB` instance (`OmniChannelNoiseDB.cxx:cache_wire_lengths`).
The cache is built lazily so detectors that use only scalar RMS cuts
(PDHD, MicroBooNE, ICARUS) pay no overhead.

**Channel selection**: PDVD uses explicit channel-ID lists (`u_chans` / `v_chans` /
`w_chans`) in the `channel_info` overrides, not the `wpid:` selector. This is
necessary because each PDVD anode lives in its own APA index, so the simple
`{wpid: wc.WirePlaneId(wc.Ulayer)}` form (apa=0) matches no channels at runtime.
The per-plane ID ranges are computed from the known per-CRP layout at the top of
`chndb-base.jsonnet` (lines 14–21: `crp`, `offset`, `u/v/w_local`, `u/v/w_chans`).

**Debug logging**: with `WIRECELL_LOG_LEVEL=debug`, `PDVDOneChannelNoise` emits
one line per channel:
```
PDVDOneChannelNoise ch=N rms=X.XX min_rms=Y.YY max_rms=Z.ZZ wire_length=L.Lcm noisy=true/false
```
This is useful for verifying cut values before and after a config change
(`ProtoduneVD.cxx:880–887`).

**RC-RC correction is not applied** to either bottom (TDE) or top
electronics. There is no top-vs-bottom anode branch for RC correction;
the single commented-out call (`ProtoduneVD.cxx:821`) would have applied
the same `rcrc(ch)` spectrum to all channels.

#### Frequency masks (PDVD-specific)

Per-channel notch filters are emitted by `chndb-base.jsonnet` and applied
to the channel FFT in `ProtoduneVD.cxx:835–854` (see `freqmasks` knob
above). They are gated by the `use_freqmask` TLA (default `true`) and by
anode index so each block fires only on the anodes that need it:

| Anode group | Channels | Notches |
|-------------|----------|---------|
| Anode 0 (bottom CRP-0) | W chans `2188–2195` + `2480–2485` | 47, 70.5, 94, 117.5, 141, 164.5, 188, 211.5, 235, 258.5, 282 kHz (ΔF = ±1 kHz) |
| Anodes 4–7 (all top CRPs) | all U+V+W of each anode | 23.5 kHz (±0.5 kHz) and 711 kHz (±2 kHz) |
| Anodes 1, 2, 3 | — | (none) |

Frequencies are specified in physical units via the
`wc.freqmasks_phys([f…], delta)` helper (`cfg/wirecell.jsonnet:422`) and
resolved to FFT bins at runtime, so the same config works for the 6400-
and 8000-tick frame sizes both seen in PDVD data. Each notch is
auto-mirrored onto the conjugate (negative-frequency) bins so the inverse
real-FFT stays real-valued.

The lines were diagnosed from `magnify-…orig.rms.root` FFT histograms
on run 040475 evt 0; see `chndb-base.jsonnet:505–551` for the
diagnosis-to-config trail.

### What is NOT done (compare with ProtoDUNE-SP / MicroBooNE)

- **Sticky-ADC code mitigation** — no `StickyCodeMitig` class exists for
  PDVD; the strings "sticky" and "ledge" do not appear anywhere in
  `ProtoduneVD.cxx`.
- **Ledge identification** — same: no helper, no tag.
- **RC-RC spectral correction** — commented out at `ProtoduneVD.cxx:820–823`.
- **Adaptive baseline** (`RawAdaptiveBaselineAlg`) — disabled by config (`adaptive_baseline=false` in `nf.jsonnet`). PDVD hardware is DC-coupled so the IS_RC gate that fronts this algorithm (`Microboone.cxx:963-1047`) has no physical meaning.
- **Electronics reconfiguration** — `m_noisedb->config(ch)` never called.
- **Top/bottom electronics split** at the per-channel level — no `ident`
  test inside `OneChannelNoise::apply`. The `adaptive_baseline` field in
  `nf.jsonnet` could be set differently per anode (e.g., `anode.data.ident < 4`),
  but both groups are left at `false` because PDVD is uniformly DC-coupled.
  The only top/bottom branch lives in `nf.jsonnet:60–66` (shield coupling, Step 3).
- **`lf_noisy` tagging** — see [below](#lf_noisy-tagging).

The `maskmap: {sticky: "bad", ledge: "bad", noisy: "bad"}` in
`nf.jsonnet:47` declares routing for `sticky` and `ledge` keys that the
PDVD C++ code never produces. Only the `noisy` key is exercised.

## Step 2 — PDVDCoherentNoiseSub (group coherent subtraction)

**Type**: `PDVDCoherentNoiseSub`
**C++ class**: `WireCell::SigProc::PDVD::CoherentNoiseSub`
**Source**: `toolkit/sigproc/src/ProtoduneVD.cxx` (apply body: ~lines 885–990)
**Config in**: `nf.jsonnet:16–24`, groups from `chndb-base.jsonnet:49–410`

### What it does

For each channel group (typically one FEMB or one CRP conduit):

1. Computes the **median waveform** across all channels in the group
   (sample-by-sample median to capture the common-mode shape).
2. Runs **`SignalProtection`** (`ProtoduneVD.cxx:938–940`) which has two
   internal stages:
   - **Time-domain ADC stage** (`ProtoduneVD.cxx:319–353`, always active):
     computes the per-channel RMS and marks bins where
     `|median - mean| > limit` as signal-bearing, then pads those ROIs.
     `limit = clamp_above(max(protection_factor × rms, adc_limit), min_adc_limit)`.
   - **Deconvolution stage** (`ProtoduneVD.cxx:357–411`, gated):
     divides the median spectrum by `respec`, applies Gaussian +
     low-frequency filter, then thresholds positive excursions against
     `decon_limit`. **Active on U and V planes** — the guard at line 357
     requires `respec.size() > 0` and `res_offset != 0`, both of which
     are satisfied by the per-plane U/V `channel_info` entries in
     `chndb-base.jsonnet`. W plane remains bypassed (`response: {}`
     and `response_offset: 0.0` in the default block).
3. Runs **`Subtract_WScaling`** (`ProtoduneVD.cxx:982–985`) to subtract
   the scaled common-mode median from each channel. This also has a
   deconvolution branch gated by the same `respec` condition
   (`ProtoduneVD.cxx:144`); it is likewise bypassed in PDVD's current
   config. The active path is a straightforward
   `signal[i] -= scaling × median[i]` (`ProtoduneVD.cxx:259`).

### Tunable knobs

| Knob | Set in | Default | Effect |
|------|--------|---------|--------|
| `rms_threshold` | `nf.jsonnet:22` | `0.0` | Groups whose overall RMS is below this are skipped |
| `adc_limit` | `chndb-base.jsonnet:495` | `60 * gain_scale` | **Floor of the time-domain signal-veto threshold** (raw ADC counts) in `SignalProtection`. Not a saturation cut. Effective threshold = `clamp_above(max(protection_factor × rms, adc_limit), min_adc_limit)`. The currently-active signal-protection path uses this (`ProtoduneVD.cxx:319–328`) |
| `protection_factor` | `OmniChannelNoiseDB.cxx:43` | `5.0` | Multiplier on per-channel RMS to form the baseline signal-veto threshold |
| `min_adc_limit` | `chndb-base.jsonnet:496` | `200 * gain_scale` | Ceiling on the time-domain threshold |
| `decon_limit` | `chndb-base.jsonnet:493` | W: `0.05`; U/V: `0.01` (bot) / `0.02` (top) | Floor threshold on the **deconvolved median** waveform (positive excursions) in `SignalProtection`. Units: dimensionless amplitude in deconvolved space (not gain-scaled). **Active on U/V** via per-plane `channel_info` entries; W bypassed (`respec` empty) |
| `decon_limit1` | `chndb-base.jsonnet:494` | W: `0.08`; U/V: `0.07` (both) | Threshold on the deconvolved per-channel ROI peak in `Subtract_WScaling` (`ProtoduneVD.cxx:228`); combined with `roi_min_max_ratio` to decide whether to interpolate-replace the median before subtraction. Same units as `decon_limit`. **Active on U/V**; W bypassed — same guard |
| `roi_min_max_ratio` | `chndb-base.jsonnet:483` | `0.8` | Ratio used in ROI protection logic (min/max asymmetry test) |

### 1D field response for signal protection

`SignalProtection` and `Subtract_WScaling` both receive a 1D response
spectrum `respec` fetched via `m_noisedb->response(achannel)`
(`ProtoduneVD.cxx:910`). It is **not synthesised analytically** inside
`ProtoduneVD.cxx`; the class makes no direct call to `IFieldResponse` or
`Response::ColdElec`.

`OmniChannelNoiseDB::parse_response` (`OmniChannelNoiseDB.cxx:302–355`)
builds `respec` by one of three paths (first match wins):

| Condition in channel JSON | What happens |
|---------------------------|--------------|
| `wpid` key present | Reads field-response file → `Response::wire_region_average` → sums currents of the named plane → FFT |
| `waveform` + `waveformid` keys present | FFT of the explicit waveform array |
| Neither (empty `{}`) | Returns an **empty** spectrum (lines 351–354) |

**PDVD now uses the second path** for U and V planes via per-plane
`channel_info` entries in `chndb-base.jsonnet` that wire FR⊗ER kernels from
two split files:

- `chndb-resp-bot.jsonnet` — bottom CRP (cold ER, gain 7.8 mV/fC, postgain
  1.1365, ADC/mV 11.70): `response_offset` = 239 (U) / 245 (V).
- `chndb-resp-top.jsonnet` — top CRP (JsonElecResponse, postgain 1.52,
  ADC/mV 8.192): `response_offset` = 240 (U) / 243 (V).

The selection is gated on the anode index `n`: `n < 4` ⇒ bottom, `n >= 4`
⇒ top. The kernel is scaled by `gain_scale = if n >= 4 then 1.0 else
params.elec.gain / (7.8 * wc.mV / wc.fC)` so a runtime FE gain override
propagates correctly (top uses a fixed JsonElecResponse with no scalar gain
knob). The field-response file `protodunevd_FR_norminal_260324.json.bz2`
(`params.jsonnet:165–167`) is consumed by SP; the NF kernels were derived
from it via `wirecell-sigproc track-response` with a 160 µs convolution
window (the FR native length of ~132.5 µs is shorter than the bipolar
induction tail, so zero-padding is required to avoid FFT circular wraparound).

### Channel groups

`chndb-base.jsonnet:49–410` contains a hardcoded 2-D list of channel
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
| `top_u_groups` | `chndb-base.jsonnet:412–417` | Two channel ranges per top anode | Which channels form the top-U groups subject to shield coupling removal |

`top_u_groups` at `chndb-base.jsonnet:412–417`:
```jsonnet
top_u_groups:
  [std.range(n*3072, n*3072+475) for n in std.range(2,3)]
  +[std.range(n*3072+476, n*3072+951) for n in std.range(2,3)]
```
Each top anode (n = 2, 3 corresponding to ident 6, 7) contributes two
half-groups of ~476 channels each (the two halves of the U-plane strip
layout).

## lf_noisy tagging

`lf_noisy` appears in `ProtoduneVD.cxx` exactly once — at line 857,
inside the `if (is_partial)` block:

```cpp
if (iplane != 2) {  // not collection
    ret["lf_noisy"][ch].push_back(temp_bin_range);
}
```

Because `is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false`
(line 819) and `adaptive_baseline` is left at its default `false` in
`nf.jsonnet`, this line is **currently never taken** in PDVD. `PDVD::NoisyFilterAlg` (`ProtoduneVD.cxx:684–698`)
only emits `noisy`. No coherent- or shield-stage code emits `lf_noisy`.
PDVD therefore **never produces an `lf_noisy` mask** in production, and the
`OmnibusNoiseFilter` `maskmap` (`nf.jsonnet:47`) has no `lf_noisy` entry.

For comparison:
- ProtoDUNE-SP (`Protodune.cxx:772,880–893`) has the same block but with
  `is_partial = m_check_partial(spectrum)` *live*, so it does emit
  `lf_noisy` on non-collection partial channels.
- MicroBooNE has additional `lf_noisy` paths: a chirping-channel branch
  (`Microboone.cxx:954`) and a dedicated `OneChannelStatus::ID_lf_noisy`
  (`Microboone.cxx:1299–1346`). PDVD has neither.

## OmnibusNoiseFilter wrapper

The three filter passes are hosted by a single `OmnibusNoiseFilter` pnode
(`nf.jsonnet:37–76`). Key configuration:

| Key | Value | Meaning |
|-----|-------|---------|
| `nticks` | `0` | Don't force waveform length; inherit from incoming frame |
| `maskmap` | `{sticky:"bad", ledge:"bad", noisy:"bad"}` | Merge per-channel flag types into unified `bad` mask consumed by SP. Note: PDVD only ever produces the `noisy` key; the `sticky` and `ledge` entries are inert (PDVD has no code that emits those tags) |
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
| `groups` | `chndb-base.jsonnet:49–410` | Coherent-noise groupings (2-D list of channel IDs) |
| `top_u_groups` | `chndb-base.jsonnet:412–417` | Shield-coupling groups for top U plane |
| `bad` | `chndb-base.jsonnet:420–461` | Hard-coded bad channels |
| `channel_info` | `chndb-base.jsonnet:466–529` | Per-channel defaults + per-anode-group/per-plane RMS overrides + optional caller overrides |

To add a new bad channel: append its ID to the `bad` list at
`chndb-base.jsonnet:420–461`.

To override an individual channel's RMS cuts or decon limits: pass an
entry via the `rms_cuts=[]` argument to `chndb-base.jsonnet` (caller-supplied
entries are appended last and take highest precedence), or add an entry
directly after the per-plane overrides block at line 513.

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
| `toolkit/cfg/pgrapher/experiment/protodunevd/chndb-resp-bot.jsonnet` | FR⊗ER kernel for bottom CRP (cold ER, gain 7.8 mV/fC); wired into `chndb-base.jsonnet` |
| `toolkit/cfg/pgrapher/experiment/protodunevd/chndb-resp-top.jsonnet` | FR⊗ER kernel for top CRP (JsonElecResponse, postgain 1.52); wired into `chndb-base.jsonnet` |
| `toolkit/cfg/pgrapher/experiment/protodunevd/params.jsonnet` | Detector parameters (tick, nticks, strip_length file) |
| `toolkit/cfg/pgrapher/common/resamplers.jsonnet` | Resampler pnode construction |
| `toolkit/sigproc/src/ProtoduneVD.cxx` | C++ impl of PDVD NF modules |
| `toolkit/sigproc/inc/WireCellSigProc/ProtoduneVD.h` | PDVD NF class declarations |
| `toolkit/sigproc/src/OmnibusNoiseFilter.cxx` | OmnibusNoiseFilter driver |
| `toolkit/sigproc/src/OmniChannelNoiseDB.cxx` | Channel noise DB: parses `response`, `reconfig`, `freqmasks` |
