# PDVD coherent-NF dump + viewer

Validation tool for `PDVDCoherentNoiseSub` (jsonnet `data.debug_dump_path`).
Mirrors the PDHD setup; the viewer code is **shared** with PDHD —
`serve_coherent_viewer.sh` invokes
`../../pdhd/nf_plot/coherent_dump_viewer.py` with the PDVD dump
directory.

PDVD top (anodes 4–7) and bottom (0–3) are typically run as separate
jobs but can share one viewer instance: the dump tree is keyed on
`apa<N>` so all 8 anodes land in one Bokeh dropdown.

---

## Quick start

```bash
# 1. Run NF+SP for one event with the dump turned on:
./run_nf_sp_evt.sh 039324 0 -a 0 -d work/dbg     # bottom anode 0
./run_nf_sp_evt.sh 039324 0 -a 4 -d work/dbg     # top anode 4 (same dump dir)

# 2. Start the viewer on the workstation:
cd nf_plot
./serve_coherent_viewer.sh ../work/dbg

# 3. From your laptop, port-forward over SSH:
ssh -L 5006:localhost:5006 user@workstation

# 4. Open in laptop's browser:
http://localhost:5006/coherent_dump_viewer
```

The dump path layout, NPZ schema, viewer panels, and tuning workflow
are identical to PDHD's — see [`../../pdhd/nf_plot/README.md`](../../pdhd/nf_plot/README.md)
for the full reference.

---

## PDVD-specific notes

- `decon_limit1` defaults to **0.07 / 0.07 / 0.09** for U/V/W (vs 0.07 / 0.07 / 0.09 on PDHD APA0; both detectors use the same chndb defaults but their RMS scales differ).
- `ROI_tighter_lf` τ = **0.06 MHz** on PDVD vs 0.08 MHz on PDHD; that
  shifts the deconv-stage low-frequency cutoff and is one of the
  things visible in the viewer's bottom-panel waveform shape.
- The PDVD jsonnet has a per-CRP dispatch hook
  (`if anode.data.ident < 4`) that currently routes both
  bottom-CRP and top-CRP groups to the same `Wiener_tight_*` set;
  if that ever diverges the viewer will simply show different
  filters in the header bar — no viewer change needed.

---

## L1SP filter workflow (PDVD)

PDVD's nf+sp graph wires `L1SPFilterPD` after `OmnibusSigProc` with per-region
parameters (bottom = anodes 0–3, top = anodes 4–7).  See
[`../../sigproc/docs/l1sp/L1SPFilterPD.md`](../../sigproc/docs/l1sp/L1SPFilterPD.md)
for the algorithm.

The default mode is `process`: the LASSO fit replaces gauss/wiener for
triggered ROIs on bottom anodes (0–3).  Top anodes (4–7) auto-fall to
dump (tagger-only) per the cap in `protodunevd/sp.jsonnet`, since the
top-CRP electronics are not yet validated for the LASSO writeback.
Pass `-c <dir>` to force dump (tagger-only) mode if you only want the
calibration NPZs.

```bash
# A) Smearing-kernel sanity check (already validated; rerun any time):
cd ../sp_plot
python plot_l1sp_smearing_kernel.py
# Produces l1sp_smearing_kernel_validation.png.

# B) Default run — L1SP fit replaces gauss/wiener on bottom anodes:
cd ..
./run_nf_sp_evt.sh 039324 0
# SP tar.bz2 in work/039324_0/ now contains L1SP-modified gauss/wiener.
# Convert to magnify ROOT via run_sp_to_magnify_evt.sh to inspect.

# C) Tagger validation only (no LASSO writeback):
./run_nf_sp_evt.sh 039324 0 -c work/calib
# Calib NPZs land under work/calib/039324_0/apa<N>_<run>_<evt>.npz.
# Inspect ROI asymmetry distributions per plane per region (np.load).

# D) Process mode + per-ROI waveform dump (for the bokeh viewer):
./run_nf_sp_evt.sh 039324 0 -w work/wf
# Triggered-ROI NPZs (raw/decon/lasso/smeared) land under
# work/wf/039324_0/<dump_tag>_<frame_ident>/.

# E) Event-display ROI point-check:
cd nf_plot
./serve_l1sp_roi_viewer.sh ../work/wf
ssh -L 5007:localhost:5007 user@workstation     # from laptop
# open http://localhost:5007/l1sp_roi_viewer
```

The viewer started as a verbatim copy of
`pdhd/nf_plot/l1sp_roi_viewer.py`; the PDVD copy has since added the
auto-plane-switch and LASSO-declined handling described below and is
the canonical version (port the changes back to PDHD when next
needed).  It discovers APA index from the `apa<N>_<run>_<evt>`
dump-tag prefix and so handles the full PDVD anode range (0–7)
without further changes.

When a triggered ROI's LASSO is declined (the cxx writes back zeros
because `sum_beta` did not pass the admit threshold), the dump still
saves the entry with an empty `lasso` array.  The viewer pads it back
to ROI length, draws the "LASSO fit" panel as zeros, annotates the
header with *"LASSO declined — sum_beta below threshold"*, and zeroes
the smeared panel.  This is the expected display for tagger-fired
but solver-rejected ROIs (e.g. negative-polarity dips with no
in-window basis1 coverage in older kernel files).  The viewer also
auto-switches the U/V/W radio button if the currently selected plane
has no ROIs for the chosen event/APA.

**First-time process-mode sanity check.**  After step C above, before
trusting the L1SP-modified output, run the same event with `-x` to get
an L1SP-disabled baseline, then compare the `gauss<N>`/`wiener<N>` tags
between the two runs.  If L1SP truly fired, the diff should be non-zero
on at least the channels reported as triggered in step B's calib NPZs;
if the diff is empty, the final-merger wiring is wrong (regression
on `cfg/pgrapher/experiment/protodunevd/sp.jsonnet`'s `final_merger`).

---

## Track response + sim overlay

`track_response_{pdhd,pdvd_top,pdvd_bottom}.py` compute the analytic
FR ⊗ ER perpendicular-line-track response for U and V planes and overlay
a WireCell simulation waveform from
`/nfs/data/1/xning/wirecell-working/data/sim/`.

### Scripts and detector mapping

| Script | Detector | FR file | Electronics | Sim anode |
|--------|----------|---------|-------------|-----------|
| `track_response_pdhd.py` | PDHD APAs 1/2/3 | `dune-garfield-1d565.json.bz2` | cold 14 mV/fC, 2.2 µs | HD anode 1 |
| `track_response_pdvd_bottom.py` | PDVD bottom CRP (anodes 0–3) | `protodunevd_FR_norminal_260324.json.bz2` | cold 7.8 mV/fC, 2.2 µs, postgain 1.0 | VD anode 0 |
| `track_response_pdvd_top.py` | PDVD top CRP (anodes 4–7) | `protodunevd_FR_norminal_260324.json.bz2` | `JsonElecResponse` (peak ≈ 7.2 mV/fC), postgain 1.36 | VD anode 4 |

> **`postgain` history.**  Both PDVD postgains were originally calibrated
> through the W (collection) plane against an FR file that shipped an
> all-zero "sentinel" path at pp=0 on W (see
> `pdvd/sp_plot/illustrate_pdvd_w_sentinel_path_bug.py`), which
> under-normalised the W line-source integral by ~12% (0.823 e → 0.920 e
> per electron after the in-software fix).  The calibration absorbed that
> deficit into postgain (PDVD-bottom 1.1365, PDVD-top 1.52).  The FR has
> since been corrected (`FR_xn_boost_3.json.bz2`, copied over the same
> filename in `wire-cell-data/`) and the postgains have been
> de-compensated: bottom 1.1365 → 1.0 (PDHD-equivalent; same chip),
> top 1.52 → 1.36 (= 1.52 / 1.117).

### How to run

```bash
cd pdvd/nf_plot
/nfs/data/1/xning/wirecell-working/.direnv/python-3.11.9/bin/python3 track_response_pdhd.py
/nfs/data/1/xning/wirecell-working/.direnv/python-3.11.9/bin/python3 track_response_pdvd_bottom.py
/nfs/data/1/xning/wirecell-working/.direnv/python-3.11.9/bin/python3 track_response_pdvd_top.py
```

Each script writes two PNGs in this directory: `track_response_<det>_U.png` and
`track_response_<det>_V.png`.  Each PNG has two panels:

- **Top** — ADC waveform vs. time.  Three overlaid lines:
  - **Red solid** — analytic FR ⊗ ER model (digitised at 500 ns).
  - **Blue dashed** — `chndb-resp.jsonnet` reference (SBND placeholder; shape only, rescaled to model trough).
  - **Green dashed** — simulation waveform from the npy file (rescaled to the model's dominant extremum; scaling factor shown in legend).
- **Bottom** — |FFT| of all three waveforms.

### Sim overlay details

The sim npy files are 400-sample mean-ADC traces (500 ns/tick) produced by
`wct-sim-check-track.jsonnet` — a perpendicular MIP track at 50 cm drift,
averaged over channels above 5·RMS.  The dominant extremum (largest |ADC|)
sits at sample 200.  The overlay aligns that extremum to the same-sign
extremum of the analytic model and rescales to match its amplitude;
the scaling factor printed in the legend and on stdout reflects the
model-vs-sim amplitude ratio at that extremum.

Expected scale factors are 1.0–1.15.  The model is at the response plane
(no drift), so it is slightly larger than the sim, which accumulates
binomial lifetime attenuation (< 0.1%), transverse diffusion smearing, and
upward channel-selection bias from the 5·RMS threshold.  See
`/nfs/data/1/xning/wirecell-working/data/sim/sim-assumptions.md` for a
full breakdown.  Discrepancies beyond ~20% warrant investigation.
