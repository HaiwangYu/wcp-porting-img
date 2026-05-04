# pdvd/sp_plot — PDVD signal-processing inspection scripts

Five families of scripts live here; each is documented below.

| Script | Purpose |
|---|---|
| `find_long_decon_artifacts_pdvd.py` | Offline reference detector for L1SP induction-plane artifacts (clustered output) |
| `eval_l1sp_trigger_pdvd.py` | Compare the L1SP tagger output (Python CSV or C++ NPZ) against the hand-scan ground truth |
| `cmd_plot_frames.py` | U/V/W frame views from a `FrameFileSink` archive |
| `track_response_l1sp_pdvd.py` | Validator for the PDVD L1SPFilterPD kernel JSONs (top + bottom) |
| `illustrate_pdvd_w_sentinel_path_bug.py` | Diagnostic plot for the all-zero sentinel-path bug in the PDVD W FR |

Reference data:

| File | Purpose |
|---|---|
| `handscan_039324_anode0.csv` | Hand-scan ground truth for run 39324 events 0-5, PDVD bottom anode 0.  Schema mirrors `pdhd/nf_plot/handscan_27409.csv` plus a `real ∈ {Yes, No, Missing}` column (Yes = real artifact must fire; No = real prolonged track that must NOT fire; Missing = real artifact the gate currently misses).  Consumed by `--validate` mode of `find_long_decon_artifacts_pdvd.py` and the default ground truth of `eval_l1sp_trigger_pdvd.py`. |
| `pdvd_l1sp_rois_039324_evt{0..5}_anode0.csv` | Per-event clustered-ROI tables emitted by `find_long_decon_artifacts_pdvd.py --csv`.  Refresh after any defaults / algorithm change. |

---

## `find_long_decon_artifacts_pdvd.py` — offline reference detector

Reads the per-event Magnify ROOT file (`magnify-runRRRRRR-evtN-anodeA.root`)
and applies the same multi-arm gate as the C++ `L1SPFilterPD`, then
clusters per-channel sub-window candidates into per-cluster ROIs.

Three differences vs the C++ tagger (Python is the offline detector,
C++ is the production filter; both are tuned against the same hand-scan):

* operates at the **clustered** level (max-feature aggregation across a
  cluster's per-channel ROIs), while the C++ gate is per-sub-window;
* implements an additional **multi-channel-track veto** at the cluster
  level (`--multi-ch-min` / `--multi-ch-asym-esc`) that the C++ side
  realises differently via `l1_pdvd_track_veto_enable` (per-sub-window);
* defaults are tuned for PDVD bottom anode 0 against
  `handscan_039324_anode0.csv` (l_combo=90, ff_thr=0.30, fwhm_thr=0.25,
  len_long=180, asym_mod=0.50; multi-ch-min=4, multi-ch-asym-esc=0.85).

```bash
# Single event, print clusters and validate against the hand-scan
python find_long_decon_artifacts_pdvd.py --run 39324 --evt 0 --anode 0 --validate

# Save clusters to CSV (used by eval_l1sp_trigger_pdvd.py --source csv)
python find_long_decon_artifacts_pdvd.py --run 39324 --evt 0 --anode 0 \
    --csv pdvd_l1sp_rois_039324_evt0_anode0.csv
```

---

## `eval_l1sp_trigger_pdvd.py` — hand-scan evaluator

Compares the L1SP tagger output to `handscan_039324_anode0.csv` with
channel ∩ time overlap matching.  Two input sources:

* `--source csv` (default): reads
  `pdvd_l1sp_rois_039324_evt*_anode0.csv` (Python script's clustered
  output).
* `--source npz`: reads the C++ tagger's per-event NPZ dumps under
  `pdvd/work/<RUN>_<EVT>/l1sp_calib/apa<APA>_*.npz` and uses
  `flag_l1_adj` (the post-adjacency polarity that actually drives the
  LASSO; pass `--trigger-only` for the un-promoted `flag_l1`).  This
  mode also lets you re-apply the gate offline with overridden
  thresholds via CLI flags so you can probe what each threshold movement
  costs without rebuilding C++.

```bash
# Eval the Python script's current output
python eval_l1sp_trigger_pdvd.py --source csv

# Eval the C++ tagger's live output
python eval_l1sp_trigger_pdvd.py --source npz --use-cpp-flag

# Sweep one threshold offline against the C++ NPZ data
python eval_l1sp_trigger_pdvd.py --source npz --asym-mod 0.55
```

Mirrors the PDHD pattern at `pdhd/nf_plot/eval_l1sp_trigger.py`.

---

## `track_response_l1sp_pdvd.py` — kernel validator

Loads `pdvd_top_l1sp_kernels.json.bz2` and `pdvd_bottom_l1sp_kernels.json.bz2`
(via `WIRECELL_PATH`) and produces five inspection PNGs in this directory:

```
track_response_l1sp_pdvd_top_U.png
track_response_l1sp_pdvd_top_V.png
track_response_l1sp_pdvd_bottom_U.png
track_response_l1sp_pdvd_bottom_V.png
track_response_l1sp_pdvd_compare.png    # top vs bottom overlay
```

Each per-plane PNG has two stacked panels: positive ROI (bipolar +
W shifted to land at the bipolar zero crossing) on top, negative ROI
(bipolar + neg-half(bipolar), no shift) on bottom.  The compare PNG
overlays top and bottom on a shared time axis (relative to each
detector's V-plane zero crossing) so the relative W shift between
the two CRPs is visible at a glance.

```bash
python track_response_l1sp_pdvd.py
# --top-file / --bottom-file override the defaults
```

Mirrors the PDHD validator at
`pdhd/nf_plot/track_response_l1sp_kernels.py`; uses the PDVD U/V wire
pitch (7.65 mm) for the `×N_MIP` ADC scaling.

---

## `illustrate_pdvd_w_sentinel_path_bug.py` — sentinel-path diagnostic

Documents an all-zero "sentinel" path at `pp=0` on the W plane of
`protodunevd_FR_imbalance3p_260501.json.bz2`.  Before the fix in
`wire-cell-python` commit `b1249b8`, `wirecell.sigproc.{l1sp,
track_response}.line_source_response` treated this entry as
legitimate data and pinned the trapezoidal integrator's central
weight to zero, under-normalising the W collection peak by ~12%
(integral −0.823 e → −0.920 e per electron, closer to the canonical
−1).  PDHD/uBooNE/SBND/PDVD-U/PDVD-V are unaffected.

The fix is one line: skip identically-zero paths in the input
loop.  No interpolation, no per-detector special case — the
trapezoidal weights at the surviving samples (pp=±0.51 mm here)
naturally widen to fill the gap.

```bash
python illustrate_pdvd_w_sentinel_path_bug.py
# writes pdvd_w_sentinel_path_bug.png — 3×3 grid:
#   row 0: PDVD U/V/W central-wire path currents (W column flagged ← SENTINEL)
#   row 1: PDHD U/V/W central-wire path currents (control: pp=0 always real)
#   row 2: line_source_response buggy vs fixed; U/V identical, W shows Δ
```

### Resolution: postgain values updated after FR fix

The all-zero sentinel path was **also in the upstream Garfield FR file**
(`protodunevd_FR_imbalance3p_260501.json.bz2`).  The FR has since been
regenerated (`FR_xn_boost_3.json.bz2`, copied over the same filename in
`wire-cell-data/`); re-running this script confirms the buggy/fixed
integrators agree (`peak ×1.0000`, `∫ ×1.0000`), so the W-plane
under-normalisation is gone.  The detector-calibration `postgain` values
that absorbed the deficit have been de-compensated accordingly:

- **PDVD-bottom: `postgain` 1.1365 → 1.0.**  PDVD-bottom shares cold
  electronics with PDHD (gain = 7.8 mV/fC vs PDHD's 14 mV/fC; everything
  else is the same chip).  PDHD has `postgain = 1.0`; the 1.1365 / 1.0 ≈
  1.137 excess closely tracked the W-plane line-source-integrator deficit
  (peak ×1.124, integral ×1.117).  After the FR fix the bottom postgain
  drops to PDHD-equivalent 1.0.
- **PDVD-top: `postgain` 1.52 → 1.36** (= 1.52 / 1.117).  Same calibration
  path (collection plane), same W under-normalisation, but with the
  top-CRP `JsonElecResponse` layered on top.

Updates landed in:

1. `wirecell/sigproc/track_response_defaults.jsonnet` —
   `pdvd-bottom.postgain = 1.0`, `pdvd-top.postgain = 1.36`.
2. `pdvd/nf_plot/track_response_pdvd_{bottom,top}.py` —
   `POSTGAIN` module constants updated.
3. `cfg/pgrapher/experiment/protodunevd/params.jsonnet` —
   `elecs[0].postgain = 1.0`, `elecs[1].postgain = 1.36`.
4. L1SP kernel JSONs regenerated in `wire-cell-data/`:

   ```
   wirecell-sigproc gen-l1sp-kernels -d pdvd-bottom  pdvd_bottom_l1sp_kernels.json.bz2
   wirecell-sigproc gen-l1sp-kernels -d pdvd-top     pdvd_top_l1sp_kernels.json.bz2
   ```

The coherent-noise removal kernels (`chndb-resp-bot.jsonnet`,
`chndb-resp-top.jsonnet`) were **not** regenerated — the NF thresholds
were tuned against those response shapes and re-tuning is deferred to a
later NF re-calibration pass.  See the headers of those files for the
generation-time postgain (1.1365 / 1.52).

---

## `cmd_plot_frames.py` — frame viewer

Draws U, V, W wire-plane views from a WireCell `FrameFileSink` archive (`.tar.bz2`).
Each output is a single PNG with three stacked panels — one per plane.

## Requirements

```
pip install numpy matplotlib
```

## Usage

Run the script directly — no woodpecker installation needed:

```bash
python cmd_plot_frames.py data/protodune-sp-frames-anode2.tar.bz2
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `frame_file` | yes | Path to a `*-anode<N>.tar.bz2` archive |
| `--tag TAG` | no | Frame tag to load (`raw`, `gauss`, `wiener`, …). Defaults to auto-detect. |
| `--out PATH` | no | Output PNG path. Defaults to `<frame_file>.png` beside the input. |
| `--tick-range T0 T1` | no | Restrict displayed ticks to `[T0, T1)` (relative, 0-based). |
| `--zrange ZMIN ZMAX` | no | Fix color-scale range. Otherwise auto-scaled per plane. |
| `--dpi N` | no | Output image resolution (default 150). |

## Examples

```bash
# Basic — auto-detect tag, output next to input file
python cmd_plot_frames.py data/protodune-sp-frames-anode2.tar.bz2

# Explicit tag
python cmd_plot_frames.py data.tar.bz2 --tag raw2

# Custom output path
python cmd_plot_frames.py data.tar.bz2 --out my_frames.png

# Zoom into ticks 1000–3000
python cmd_plot_frames.py data.tar.bz2 --tick-range 1000 3000

# Fix color scale to ±50 ADC
python cmd_plot_frames.py data.tar.bz2 --zrange -50 50

# High-res export
python cmd_plot_frames.py data.tar.bz2 --dpi 300
```

## Input archive format

The archive must contain `.npy` files produced by WireCell's `FrameFileSink`:

| Key pattern | Content |
|---|---|
| `frame_<tag>_<N>.npy` | 2-D array `(nchannels, nticks)` of ADC values |
| `channels_<tag>_<N>.npy` | 1-D array of channel IDs |
| `tickinfo_<tag>_<N>.npy` | `[start_tick, nticks, tick_period]` |
| `chanmask_bad_<N>.npy` | Optional bad-channel mask `(M, 3)` |

The anode index `N` is inferred from the filename (`anode<N>`).

## Color scale logic

| Plane / tag | Color map | Range |
|---|---|---|
| Any `gauss` tag | `hot_r` (white→black) | Fixed `0–1000` |
| W (collection), default | `hot_r` | `0 … 10×plane RMS` |
| U, V (induction), default | `RdBu_r` (blue–white–red) | `±10×plane RMS` |
| Any plane, `--zrange` | `RdBu_r` | User-supplied |

Bad channels are drawn as thin blue vertical lines on each panel.

## Tick axis

The y-axis shows **relative** ticks (0-based index into the stored frame), not the
absolute simulation clock tick. The absolute start tick is printed to stdout but not
shown on the plot, since it is typically a large simulation offset with no visual value.
