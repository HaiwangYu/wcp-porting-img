# Wire-Cell Track Response Tool: FR ⊗ ER + Line-Source Sum

## Purpose

`wirecell-sigproc plot-garfield-track-response` convolves a field response (FR) with the
cold/warm electronics response (ER) and sums across all impact positions on a wire. The result
is the expected ADC waveform from a **perpendicular line source** — a long ionization track lying
parallel to the wire plane and running perpendicular to the wires (crossing many wire pitches).
By translation symmetry, the sum-over-impacts on a central wire equals the response that track
induces on a wire it passes directly over.

## Basic usage

```bash
wirecell-sigproc plot-garfield-track-response \
    -g garfield_field_response.tar.gz \
    -o output.pdf \
    --elec-type cold          # cold (default) or warm
```

Example driver scripts:
- `wire-cell-python/test/track-response.sh` — runs both DUNE and uBooNE tarballs
- `wire-cell-python/test/test_dune_track_response.sh` — DUNE only

## What it does internally

1. **Load FR** — reads a Garfield tarball (e.g. `dune_4.71.tar.gz`).
2. **Line-source sum** — `wirecell.sigproc.response.line(rflist, normalization)` sums the
   per-impact responses across all impact positions, yielding one waveform per plane (U/V/W)
   representing the perpendicular-track response.
3. **Convolve with electronics** — `wirecell.sigproc.plots.plot_digitized_line(uvw_rfs, gain,
   shaping, tick, elec_type)` convolves each plane response with the shaping filter, resamples
   to the ADC tick (default 0.5 µs), and digitizes with nominal ADC gain/voltage.

Default electronics parameters: **gain = 14 mV/fC, shaping = 2 µs** (cold electronics).

## Source locations

| Component | File | Symbol |
|-----------|------|--------|
| CLI entry | `wirecell/sigproc/__main__.py:231` | `plot_garfield_track_response` |
| Impact sum | `wirecell/sigproc/response/__init__.py:744` | `line(rflist, normalization)` |
| ER + ADC pipeline | `wirecell/sigproc/plots.py:351` | `plot_digitized_line(...)` |
| Electronics waveform | `wirecell/sigproc/response/__init__.py:83` | `electronics(time, gain, shaping, elec_type)` |
| Convolution helper | `wirecell/sigproc/response/__init__.py:108` | `convolve(f1, f2)` |

All paths are relative to the `wire-cell-python` repository.

## Reusable building blocks

If you need a variant (different ER, output as arrays, custom normalization), these functions
are directly importable from `wirecell.sigproc.response` and `wirecell.sigproc.plots`:

```python
from wirecell.sigproc import response, plots
from wirecell.units import mV, fC, us

# Load FR
rflist = response.load("my_field_response.json.bz2")

# Electronics response waveform
times = ...
er = response.electronics(times, peak_gain=14*mV/fC, shaping=2*us, elec_type="cold")

# Sum over all impact positions → perpendicular line-source response per plane
uvw = response.line(rflist, normalization=1.0)

# Convolve FR × ER (generic)
fr_er = response.convolve(uvw[0], er)

# Or let plot_digitized_line do FR × ER + ADC in one shot
plots.plot_digitized_line(uvw, gain=14*mV/fC, shaping=2*us, tick=0.5*us, elec_type="cold")
```

## Related tools (partial pipelines)

| Tool | FR | ER conv. | Multi-impact sum | Notes |
|------|----|----------|------------------|-------|
| `wirecell-resp compare` | yes | optional | no | Single-impact FR×ER spectrum comparison |
| `wirecell-resp lmn-fr-plots` | yes | yes (cold) | no | Single-impact; LMN resampling study |
| `toolkit/root/test/test_impactresponse.cxx` | yes | yes (ColdElec + RC²) | no | Per-impact PIR heatmaps |
| `wirecell-gen depo-line` / `linegen.py` | no | no | — | Generates depos; needs full C++ sim for waveforms |
| `toolkit/gen/test/test-lmn-fr-pdsp.bats` | yes | yes | yes | Diagonal track through full C++ sim chain |

## Further reading

- `toolkit/gen/docs/talks/lmn-fr/lmn-fr.org` — slides on FR ⊗ ER and line-track tests
- `toolkit/gen/docs/examination/response-and-convolution.md` — `PlaneImpactResponse` + `ImpactTransform` internals
- `wirecell/sigproc/response/__init__.py` docstring on `line()` — translation-invariance argument

---

## L1SP fit kernel and `track_response_uboone.py` overlay

`track_response_uboone.py` (same directory) overlays three curves on each plane:

1. **FR ⊗ ER (red, 500 ns tick)** — MIP perpendicular-track response at ADC readout tick.
2. **chndb-resp.jsonnet (blue, 500 ns tick)** — the reference waveform stored in the chndb, scaled and aligned at the trough.
3. **L1SP kernel × N_MIP (green, 100 ns)** — the response function used inside `L1SPFilter::L1_fit()`, scaled to MIP units for direct comparison.

Curves 1 and 3 are constructed from the same FR and ER; they differ only in the final resampling step (red is resampled to 500 ns, green stays at 100 ns). The green curve's sharper peaks show the information lost by ADC digitization.

### Three L1SP response objects (keep them distinct)

| Object                          | Units                         | Where built              |
|---------------------------------|-------------------------------|--------------------------|
| `resp_l1` raw buffer            | ADC / single electron, 100 ns | `l1sp_response()` in .py / `init_resp()` in C++ |
| `lin_V(t)` continuous eval      | ADC / single electron         | `linterp` around `resp_l1` |
| `G(i, j)` matrix entry          | ADC × 250 / single electron   | inside `L1_fit()` with ×250 conditioning |

The ×250 in G is `l1_scaling_factor (500) × l1_resp_scale (0.5)` — a numerical conditioning constant, not physics. It is compensated by the output weights `l1_col_scale=1.15` (W/collection) and `l1_ind_scale=0.50` (V/induction).

### Normalization chain

```
fr_line(t) [WC current / electron]    = line-source FR (1/pitch × ∫ I dX)
ewave(t)   [ADC / (WC current)]       = -POSTGAIN × (ADC_PER_MV / units.mV) × ER(t)
kernel(t)  [ADC / electron]           = IFFT(FFT(fr_line) × FFT(ewave) × period_ns)
```

Numerical values (uBooNE):
- `POSTGAIN = 1.2`
- `ADC_PER_MV = 2.048`  (12-bit, 0–2 V fullscale)
- `units.mV = 1e-9`  (WC voltage unit = 1 MV, so 1 mV = 1e-9 WC units)
- `ADC_MV_WC = 2.048 / 1e-9 = 2.048e9`  count / WC-mV
- `period_ns = 100`  (the dt factor converting discrete conv → integral)
- V-plane: kernel peak = 0.002234 ADC/e → ×N_MIP ≈ 35.8 ADC (matches fine-period trough)
- U-plane: kernel peak = 0.002836 ADC/e → ×N_MIP ≈ 45.4 ADC

Numerical identity verified: `max_abs_diff(kernel × N_MIP, wave_adc_fine) = 1.4e-14 ADC`.

### Time-offset chain

`linterp` is constructed with `x0 = -intrinsic_toff - coarse_toff + fine_toff`:

```
fr.origin  = 100 mm   (reference drift distance in WC length units)
fr.speed   = 0.001114 mm/ns   (drift velocity ≈ 1.1 mm/µs in LAr)
intrinsic_toff = origin/speed = 89.77 µs

coarse_time_offset = -8.0 µs  (hardware readout latency correction)
fine_time_offset   =  0.0 µs

x0 = -89.77 - (-8.0) + 0.0 = -81.77 µs
```

`lin_V(t)` is queried at `t = (tick_i - tick_j) × tick_size + overall_time_offset`.
When `t = 0`, the charge arrived at the wire at the same tick as the response sample.
The W-basis is queried with `t + collect_time_offset (+3 µs)` — this shifts the W
response *shape* inside the matrix, but does not displace the output signal in time.
Output: `l1_signal[start_tick + j]` — placed directly at `j`, no further shift.

### PDHD extension — parameter swap table

To build an L1SP kernel for PDHD or PDVD, replace these parameters:

| Parameter              | uBooNE (reference)                      | PDHD/PDVD (to fill in)               |
|------------------------|-----------------------------------------|---------------------------------------|
| FR file                | `ub-10-half.json.bz2`                    | PDHD/PDVD field-response file         |
| `gain`                 | 14.0 mV/fC                              | per-detector FE gain                  |
| `shaping`              | 2.2 µs                                  | per-detector FE shaping               |
| `postgain`             | 1.2                                     | per-detector postgain ‡               |
| `ADC_PER_MV`           | 2.048  (12-bit, 0–2 V)                  | per-detector ADC fullscale            |
| `coarse_time_offset`   | −8.0 µs                                 | tune from PDHD/PDVD hardware timing   |
| basis 0 (induction)    | bipolar V  (V-plane FR, `lin_V`)         | bipolar induction (any induction plane)|
| basis 1 (collection)   | W with `collect_time_offset = +3 µs`    | unipolar ± with `unipolar_time_offset` (default +3 µs, `L1SPFilterPD.h:114`) |
| output basis weights   | `l1_col_scale=1.15`, `l1_ind_scale=0.50` | `l1_basis0_scale`, `l1_basis1_scale`  |

> **‡ PDVD `postgain` is provisional — revisit when the PDVD FR is
> fixed.**  The current values
> (PDVD-bottom = 1.1365, PDVD-top = 1.52) were calibrated through the
> W (collection) plane against an FR file that under-normalises the
> W-plane line-source integrand by ~12% (an all-zero "sentinel" path
> at pp=0 on W; see `pdvd/sp_plot/illustrate_pdvd_w_sentinel_path_bug.py`).
> The calibration absorbs that deficit into `postgain`, so when the
> corrected FR lands the postgain values are expected to drop:
> PDVD-bottom → 1.0 (matches PDHD, with which it shares electronics);
> PDVD-top → ≈ 1.36 (re-derive from the new calibration).  Update the
> `POSTGAIN` constants in `track_response_pdvd_{bottom,top}.py`, the
> `postgain` entries in
> `wire-cell-python/wirecell/sigproc/track_response_defaults.jsonnet`,
> and regenerate `wire-cell-data/pdvd_{bottom,top}_l1sp_kernels.json.bz2`
> via `wirecell-sigproc gen-l1sp-kernels -d pdvd-{bottom,top}`.

The `l1sp_response()` function in `track_response_uboone.py` is detector-agnostic — pass
the PDHD FR line, PDHD ER, and period; the rest is the same FFT product.
