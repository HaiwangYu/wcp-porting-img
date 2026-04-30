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
