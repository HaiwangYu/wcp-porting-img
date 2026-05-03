# Signal Processing (SP) — ProtoDUNE-HD

This document covers the SP configuration used by the standalone
[`run_nf_sp_evt.sh`](../run_nf_sp_evt.sh) pipeline.
See also [nf.md](nf.md) and [nf_sp_workflow.md](nf_sp_workflow.md).

---

## Overview

Each of the four APAs gets its own `OmnibusSigProc` pnode returned by
`sp.make_sigproc(anode)` (`sp.jsonnet:21`).  The pnode is a 1-in / 1-out
node; it is **not** a pipeline of sub-nodes but a single C++ object that
internally runs the full deconvolution → ROI-finding → charge-extraction
sequence.

The caller in `wct-nf-sp.jsonnet:50` merges the override `{ sparse: false }`
so that output traces are stored densely (not as sparse ROI lists).

> **APA0 is special**: APA0 (ident 0) gets its own field-response file,
> filter-response objects, Wiener filter set, and `plane2layer` mapping.
> APAs 1–3 share the same configuration template.  The table below
> calls out APA0 differences explicitly.

---

## Per-anode branching

| Configuration element | APA 0 | APAs 1–3 |
|-----------------------|-------|----------|
| `field_response` | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` | `dune-garfield-1d565.json.bz2` |
| `filter_responses_tn` | `[FilterResponse:plane0, FilterResponse:plane2, FilterResponse:plane1]` (U↔V order swapped) | `[]` (none) |
| `r_th_factor` | `2.5` (slightly looser) | `3.0` |
| `plane2layer` | `[0, 2, 1]` (U=0, V=2, W=1) | `[0, 1, 2]` |
| `Wiener_tight_filters` | `_APA1` set (see filter catalogue) | default set |

The U↔V swap in `plane2layer` and `filter_responses_tn` for APA0 reflects
a hardware difference in wire orientation for that APA.  The `_APA1` suffix
on the Wiener filters is historical naming — it refers to the configuration
tuned for APA0.

---

## `make_sigproc` — OmnibusSigProc configuration

**Source**: `sp.jsonnet:21–91`

The full `data:` block of the `OmnibusSigProc` node:

### Response / detector geometry

| Knob | APA 0 | APAs 1–3 | Line | Effect |
|------|-------|----------|------|--------|
| `anode` | typename of this APA's `AnodePlane` | same | 29 | Selects wire geometry and channel map. |
| `dft` | `FftwDFT` | same | 30 | FFT implementation. |
| `field_response` | `tools.fields[0]` = np04hd-garfield fit | `tools.fields[N]` = dune 1d565 | 31 | Plane-impact response (PIR); controls the deconvolution kernel shape per plane. |
| `filter_responses_tn` | 3 `FilterResponse` objects from `protodunehd-field-response-filters.json.bz2` | `[]` | 32–35 | Extra per-plane frequency filter for field-response correction; APA0 only. |
| `elecresponse` | `ColdElec` from `params.elec` | same | 36 | Electronics shaping + gain response (shaping = 2.2 µs, gain from ext var `elecGain`). |
| `ftoffset` | `0.0` | same | 37 | Field-response time offset (µs). |
| `ctoffset` | `1.0 µs` | same | 38 | Cold-electronics time offset. Default in WCT is −8.0 µs; pdhd uses +1.0 µs. |
| `per_chan_resp` | no-op placeholder | same | 39 | Per-channel electronics response; disabled (`params.files.chresp = null`). |
| `isWrapped` | `false` | `false` | 81 | APA wires do not wrap between faces. |
| `plane2layer` | `[0, 2, 1]` | `[0, 1, 2]` | 83 | Maps plane index to Garfield layer (U, V, W). APA0 swaps U and V. |

### Deconvolution / gain

| Knob | Default | Line | Effect |
|------|---------|------|--------|
| `fft_flag` | `0` | 40 | `0` = lower memory, slightly slower; `1` = faster, more memory. |
| `postgain` | `1.0` | 41 | Post-deconvolution amplitude scale factor (WCT default is 1.2; pdhd uses 1.0). |
| `ADC_mV` | `4095 / 1400 mV` ≈ 2.925 | 42 | ADC-counts-per-mV conversion; derived from `adc.resolution=14` and `adc.fullscale=[0.2 V, 1.6 V]`. |

### Tight-ROI thresholds

Tight ROIs seed the initial signal regions from the deconvolved frame.

| Knob | Default | Line | Effect |
|------|---------|------|--------|
| `troi_col_th_factor` | `5.0` | 43 | Tight-ROI threshold for collection plane (W), in units of local noise RMS. Raise to suppress noise; lower to recover weak signals. |
| `troi_ind_th_factor` | `3.0` | 44 | Same for induction planes (U, V). Lower than collection because induction signals are bipolar. |

### Loose-ROI thresholds

Loose ROIs extend the tight ROIs in the rebinned domain.

| Knob | Default | Line | Effect |
|------|---------|------|--------|
| `lroi_rebin` | `6` | 45 | Number of ticks combined in the rebinned frame for loose-ROI search. |
| `lroi_th_factor` | `3.5` | 46 | Primary loose-ROI threshold (× noise RMS in rebinned frame). |
| `lroi_th_factor1` | `0.7` | 47 | Secondary loose-ROI threshold (lower wing). |
| `lroi_jump_one_bin` | `1` | 48 | Allow the loose ROI to cross a single below-threshold bin (1 = yes). |

### ROI refinement thresholds

After the initial ROI pass, a refinement stage rejects fake signals and
adjusts ROI boundaries.

| Knob | APA 0 | APAs 1–3 | Line | Effect |
|------|-------|----------|------|--------|
| `r_th_factor` | `2.5` | `3.0` | 50 | Main refinement threshold (× noise RMS). Lower for APA0 (looser). |
| `r_fake_signal_low_th` | `375` | `375` | 51 | Lower bound of fake-signal rejection window (charge units). WCT default is 500. |
| `r_fake_signal_high_th` | `750` | `750` | 52 | Upper bound of fake-signal window. WCT default is 1000. |
| `r_fake_signal_low_th_ind_factor` | `1.0` | `1.0` | 53 | Scale factor applied to `r_fake_signal_low_th` for induction planes. |
| `r_fake_signal_high_th_ind_factor` | `1.0` | `1.0` | 54 | Scale for `r_fake_signal_high_th` on induction planes. |
| `r_th_peak` | `3.0` | `3.0` | 55 | Threshold for peak detection within a refined ROI. |
| `r_sep_peak` | `6.0` | `6.0` | 56 | Minimum separation (ticks) between adjacent peaks. |
| `r_low_peak_sep_threshold_pre` | `1200` | `1200` | 57 | Pre-separation peak threshold (charge units). |

### Output frame tags

| Knob | Value | Line | Description |
|------|-------|------|-------------|
| `wiener_tag` | `'wiener{N}'` | 61 | Tag for Wiener-filtered output traces. |
| `decon_charge_tag` | `'decon_charge{N}'` | 63 | Tag for deconvolved-charge output. Not persisted to disk by the default sink. |
| `gauss_tag` | `'gauss{N}'` | 64 | Tag for Gaussian-filtered output traces (primary charge estimate, used by imaging). |

### Multi-plane protection

| Knob | Default | Line | Effect |
|------|---------|------|--------|
| `use_multi_plane_protection` | `false` | 75 | Enable three-plane (MP3) / two-plane (MP2) consistency check to suppress isolated fake ROIs. |
| `mp3_roi_tag` | `'mp3_roi{N}'` | 76 | Tag for MP3-qualified ROIs. |
| `mp2_roi_tag` | `'mp2_roi{N}'` | 77 | Tag for MP2-qualified ROIs. |

### Wiener filter selection

| Knob | APA 0 | APAs 1–3 | Line |
|------|-------|----------|------|
| `Wiener_tight_filters` | `[Wiener_tight_U_APA1, Wiener_tight_W_APA1, Wiener_tight_V_APA1]` | `[Wiener_tight_U, Wiener_tight_V, Wiener_tight_W]` | 85–87 |

Note the APA0 order is `U, W, V` (ind, ind, col) to match the `plane2layer=[0,2,1]` mapping.

---

## Debug mode

To inspect intermediate ROI stages, flip `use_roi_debug_mode: true` in
`sp.jsonnet:66`.  This emits seven additional frame tags:

| Tag | Stage |
|-----|-------|
| `tight_lf{N}` | Tight low-frequency ROI |
| `loose_lf{N}` | Loose LF ROI |
| `cleanup_roi{N}` | Post-cleanup ROI |
| `break_roi_1st{N}` | After first break-ROI pass |
| `break_roi_2nd{N}` | After second break-ROI pass |
| `shrink_roi{N}` | Shrunken ROI |
| `extend_roi{N}` | Extended ROI |

To also save these to disk, add the desired tag(s) to the `tags` list of
`spframesink{N}` in `wct-nf-sp.jsonnet:79`.

---

## Filter catalogue (`sp-filters.jsonnet`)

> **Warning** (`sp-filters.jsonnet:1–4`): the SP C++ code hard-codes
> these filter instance names.  Do **not** rename them.

**Source**: `sp-filters.jsonnet:9–85`

### Low-frequency (LF) filters

Used to suppress low-frequency baselines within ROIs.

| Name | Type | `tau` (MHz) | Role |
|------|------|-------------|------|
| `ROI_loose_lf` | `LfFilter` | `0.002` | Loose-ROI LF suppression (gentlest). |
| `ROI_tight_lf` | `LfFilter` | `0.016` | Tight-ROI LF suppression. |
| `ROI_tighter_lf` | `LfFilter` | `0.08` | Tightest LF suppression — used in refinement. |

Higher `tau` → stronger low-frequency rejection → less baseline ripple
but also less sensitivity to very-slow signals.

### Gaussian filters

Applied after deconvolution to suppress high-frequency noise.

| Name | Type | `sigma` (MHz) | `power` | Role |
|------|------|---------------|---------|------|
| `Gaus_tight` | `HfFilter` | `0.0` | `2` | Default Gaussian filter (zero sigma = purely transfer-function inverse). |
| `Gaus_wide` | `HfFilter` | `0.12` | `2` | Wider Gaussian; an alternative for noisier conditions. |

### Wiener filters (default — APAs 1–3)

Wiener-optimal filters matched to the signal+noise spectrum.

| Name | Type | `sigma` (MHz) | `power` | Plane |
|------|------|---------------|---------|-------|
| `Wiener_tight_U` | `HfFilter` | `0.221933` | `6.55413` | U (induction) |
| `Wiener_tight_V` | `HfFilter` | `0.222723` | `8.75998` | V (induction) |
| `Wiener_tight_W` | `HfFilter` | `0.225567` | `3.47846` | W (collection) |

### Wiener filters (APA0 — `_APA1` set)

These have slightly narrower `sigma` values, reflecting a different
noise spectrum for APA0.  Despite the `_APA1` suffix the name is
historical and these filters are used only for APA0.

| Name | Type | `sigma` (MHz) | `power` | Plane |
|------|------|---------------|---------|-------|
| `Wiener_tight_U_APA1` | `HfFilter` | `0.203451` | `5.78093` | U (induction, APA0) |
| `Wiener_tight_V_APA1` | `HfFilter` | `0.160191` | `3.54835` | V (induction, APA0) |
| `Wiener_tight_W_APA1` | `HfFilter` | `0.125448` | `5.27080` | W (collection, APA0) |

### Wide Wiener filters

An alternative set with wider bandwidths (not selected by default in
`wct-nf-sp.jsonnet`; available for testing).

| Name | Type | `sigma` (MHz) | `power` | Plane |
|------|------|---------------|---------|-------|
| `Wiener_wide_U` | `HfFilter` | `0.186765` | `5.05429` | U |
| `Wiener_wide_V` | `HfFilter` | `0.1936` | `5.77422` | V |
| `Wiener_wide_W` | `HfFilter` | `0.175722` | `4.37928` | W |

### Wire-domain (spatial) filters

Applied in the transverse wire direction to smooth across adjacent wires.

| Name | Type | `sigma` | `flag` | Plane |
|------|------|---------|--------|-------|
| `Wire_ind` | `HfFilter` | `0.75/√π ≈ 0.423` (unitless) | `false` | Induction (U, V) |
| `Wire_col` | `HfFilter` | `10.0/√π ≈ 5.64` (unitless) | `false` | Collection (W) |

`flag: false` puts the `HfFilter` into wire-domain mode (spatial rather
than frequency domain).  Collection wires use a much wider sigma because
collection signals are more localised in the wire direction.

---

## Response ingestion

SP does not load response files itself; it references objects built by
`tools.jsonnet` from paths in `params.jsonnet`:

| Response | Params field | File | Applies to |
|----------|-------------|------|------------|
| Field response (PIR) | `params.files.fields[0]` | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` | APA 0 |
| Field response (PIR) | `params.files.fields[1–3]` | `dune-garfield-1d565.json.bz2` | APAs 1–3 |
| Filter response | `params.files.fltresp` | `protodunehd-field-response-filters.json.bz2` | APA 0 only |
| Electronics | `params.elec.gain` (ext var `elecGain`), `params.elec.shaping = 2.2 µs` | — | All APAs |
| Per-channel | `params.files.chresp = null` | — | Disabled (no-op) |

To point at a new Garfield calculation, edit `params.files.fields[...]`
(`params.jsonnet:152–157`) and rebuild.  The filter response
(`params.files.fltresp`) should also be regenerated if the field response
changes significantly.

The gain is injected at runtime as a `wire-cell` external variable:
```bash
wire-cell -V elecGain=14 ...    # 14 mV/fC
wire-cell -V elecGain=7.8 ...   # 7.8 mV/fC
```
The noise-spectrum file (`params.jsonnet:165–166`) is selected
automatically to match the gain.

---

## Output archive

**Source**: `wct-nf-sp.jsonnet:69–84`

```jsonnet
FrameFileSink  'spframesink{N}'
  outname:  '{sp_prefix}-anode{N}.tar.bz2'
  tags:     ['gauss{N}', 'wiener{N}']
  digitize: false   // float traces, deconvolved charge scale
  masks:    true    // channel masks + ROI masks included
```

Only `gauss{N}` and `wiener{N}` are persisted.  `decon_charge{N}` and
all debug-ROI tags are computed in memory but dropped at serialization.

**Downstream consumption**: imaging (`run_img_evt.sh`) reads `gauss{N}`
as the primary charge estimate.  Magnify (`run_sp_to_magnify_evt.sh`) reads
both `gauss{N}` and `wiener{N}` for visual inspection.  With
`digitize: false` the values are already in physical charge units, ready
for pattern recognition.

---

## Tuning hot-spots (ranked)

| Priority | Knob | Location | When to touch |
|----------|------|----------|---------------|
| 1 | `troi_col_th_factor` / `troi_ind_th_factor` | `sp.jsonnet:43–44` | Primary noise/signal trade-off knob. Raise to suppress noise; lower to recover weak signals. |
| 2 | `lroi_th_factor` / `lroi_th_factor1` / `lroi_rebin` | `sp.jsonnet:45–47` | Loose-ROI sensitivity; adjust if ROIs are too sparse or too extended. |
| 3 | `r_fake_signal_low_th` / `r_fake_signal_high_th` | `sp.jsonnet:51–52` | Fake-signal rejection window; tighten if isolated noise spikes survive ROI refinement. |
| 4 | Wiener filter `sigma` / `power` | `sp-filters.jsonnet:48–67` | Retune when the noise spectrum changes (new gain, new electronics). APA0 uses the `_APA1` triplet. |
| 5 | LF filter `tau` values | `sp-filters.jsonnet:41–43` | Adjust low-frequency baseline suppression if long-range signal distortions appear. |
| 6 | `r_th_factor` | `sp.jsonnet:50` | Per-APA refinement threshold; APA0 uses 2.5, others 3.0. |
| 7 | `Wire_ind` / `Wire_col` sigma | `sp-filters.jsonnet:83–84` | Spatial smoothing across wires; widen if isolated single-wire noise survives. |
| 8 | `ctoffset` / `ftoffset` | `sp.jsonnet:37–38` | Adjust if deconvolved pulses are mis-timed relative to truth. |
| 9 | `postgain` | `sp.jsonnet:41` | Post-deconvolution amplitude rescaling; adjust if absolute charge scale is off. |
| 10 | `use_multi_plane_protection` | `sp.jsonnet:75` | Enable MP3/MP2 to suppress isolated fake ROIs that appear in only one plane. |
| 11 | `use_roi_debug_mode` | `sp.jsonnet:66` | Flip to `true` to expose intermediate ROI tags for diagnosing any of the above. |
| 12 | `field_response` files | `params.jsonnet:152–157` | Replace when a new Garfield calculation is available; regenerate `fltresp` too. |

---

## L1SPFilterPD — unipolar-induction correction

`L1SPFilterPD` is wired downstream of `OmnibusSigProc` inside `make_sigproc`
when `l1sp_pd_mode != ''`.  It applies a per-ROI LASSO fit using pre-built
bipolar + unipolar response bases to correct induction-plane channels that
carry unipolar signals from anode-induction or collection-on-induction physics.

### Enabling

L1SP is **ON by default** across the PDHD configuration chain:
`sp.jsonnet:make_sigproc` defaults `l1sp_pd_mode='process'`, and
`wct-nf-sp.jsonnet:43` mirrors that default.  Plain
`./run_nf_sp_evt.sh 27409 0` runs L1SP and emits the L1SP-fitted waveform
under both `gauss{N}` and `wiener{N}`.

To override:
- `-c <dir>` switches L1SP to `'dump'` (scalar bypass) mode and writes
  per-ROI feature NPZs to `<calib_dir>/<RUN>_<EVT>/apa<N>_*.npz`.
- `-w <dir>` keeps `'process'` mode and adds per-triggered-ROI waveform
  NPZs under `<wf_dir>/<RUN>_<EVT>/<dump_tag>_<frame_ident>/`.
- Pass `--tla-str l1sp_pd_mode=''` to `wire-cell` for a bypass run that
  emits the bare `OmnibusSigProc` gauss/wiener (no L1SP, no merger).

### Per-APA plane selection

APA0 V-plane is anomalous; L1SP is restricted to U only there.  APAs 1–3
process both U and V.  This is the default in `sp.jsonnet:make_sigproc`;
no override is needed.

### Kernel file

Response kernels are pre-built and loaded from `wire-cell-data`:

```
wire-cell-data/pdhd_l1sp_kernels.json.bz2
```

Contains per-plane (U=0, V=1) bipolar + positive/negative unipolar kernels
with W peak shifts calibrated to each plane's bipolar zero crossing, plus
a global `meta.frame_origin_us` (= V-plane bipolar zero-crossing) used as
the LASSO frame origin so that β LASSO output is in the same time frame as
the gauss decon it replaces.  Regenerate with PDHD calibration
(`postgain=1.0`, `adc-per-mv=16384/1400`) if the field response or
electronics parameters change — see
`toolkit/sigproc/docs/l1sp/L1SPFilterPD.md` for the `gen-l1sp-kernels`
invocation.

### Output wiring: gauss and wiener both carry the L1SP result

After the LASSO solve, a `FrameMerger` (`l1spfinal{N}`) replaces the
`gauss{N}` and `wiener{N}` traces in the final SP frame with the L1SP-
modified gauss waveform.  Both tags carry identical, post-L1SP traces;
the untouched `OmnibusSigProc` gauss/wiener are routed only into the
merger as the second input and are never persisted.  This means the
magnify file (`spframesink{N}`) shows the L1SP result on both
`gauss{N}` and `wiener{N}` panels.

### Key config knobs (in `sp.jsonnet`)

| Key | Value | Meaning |
|-----|-------|---------|
| `kernels_file` | `"pdhd_l1sp_kernels.json.bz2"` | Pre-built response kernels (WIRECELL_PATH-resolved) |
| `kernels_scale` | `gain_scale` | Amplitude multiplier on loaded kernels; corrects for FE gain ≠ 14 mV/fC |
| `process_planes` | `[0]` (APA0) / `[0,1]` (APA1-3) | Induction planes in scope |
| `gauss_filter` | `'HfFilter:Gaus_wide'` | Smearing kernel source (auto-derived by C++) |
| `l1_raw_asym_eps` / `raw_ROI_th_adclimit` / `adc_sum_threshold` | scaled by `gain_scale` | Raw-ADC knobs at the 14 mV/fC reference; auto-scaled at runtime |

---

## Source file index

| File | Role | Key lines |
|------|------|-----------|
| `wcp-porting-img/pdhd/wct-nf-sp.jsonnet` | Jsonnet entry point | L49–51 (SP maker); L69–84 (SP frame sink) |
| `toolkit/cfg/pgrapher/experiment/pdhd/sp.jsonnet` | `make_sigproc` factory | L21–91 (full data block) |
| `toolkit/cfg/pgrapher/experiment/pdhd/sp-filters.jsonnet` | Filter definitions | L41–43 (LF); L45–46 (Gauss); L48–67 (Wiener); L70–84 (Wide Wiener + wire filters) |
| `toolkit/cfg/pgrapher/experiment/pdhd/params.jsonnet` | Detector parameters | L96 (`nticks=6000`); L99–104 (`adc`); L106–116 (`elecs`); L152–157 (`fields`); L159 (`fltresp`); L165–166 (noise, gain-dependent) |
| `toolkit/cfg/pgrapher/common/tools.jsonnet` | Builds `tools.fields`, `tools.elec_resp`, `tools.dft`, `tools.fltrespuses`, `tools.perchanresp_nameuses` from `params` | — |
