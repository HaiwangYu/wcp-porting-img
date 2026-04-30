# PDHD coherent-NF dump + viewer

Validation tool for `PDHDCoherentNoiseSub` (jsonnet `data.debug_dump_path`).
Produces one `.npz` per channel-group, viewable in a browser via Bokeh.

The C++ side is **opt-in, default OFF, bit-identical when off** — when
`debug_dump_path` is the empty string the toolkit hot path is unchanged.
The Python viewer is detector-agnostic and is **shared with PDVD**
(`../../pdvd/nf_plot/serve_coherent_viewer.sh` invokes the same module).

---

## Quick start

```bash
# 1. Run NF+SP for one event with the dump turned on:
./run_nf_sp_evt.sh 027409 0 -a 1 -d work/dbg
# → work/dbg/027409_0/apa1/{U,V,W}_g<gid>.npz  (60 files for one anode)

# 2. Start the viewer on the workstation:
cd nf_plot
./serve_coherent_viewer.sh ../work/dbg          # default port 5006
#   or specify a port:
./serve_coherent_viewer.sh ../work/dbg 5099

# 3. From your laptop, port-forward over SSH:
ssh -L 5006:localhost:5006 user@workstation

# 4. Open in laptop's browser:
http://localhost:5006/coherent_dump_viewer
```

The dump path layout is:

```
<dump_root>/<RUN_PADDED>_<EVT>/apa<N>/{U,V,W}_g<gid>.npz
```

`gid` is the first-channel ident in the group (e.g. `U_g2923` is the
U-plane group whose lowest channel is 2923). `apa<N>` matches the
anode ident — for PDVD bottom anodes are 0–3 and top are 4–7; the
viewer keys on `apa<N>`, so a single dump root containing both top
and bottom dumps just shows up as more entries in the dropdown.

---

## What the viewer shows

Two stacked panels with shared x-axis (tick number):

- **Top — median waveform.** The medianed ADC across all channels in
  the group. Red dashed lines mark the chosen ADC-stage protection
  threshold (`mean_adc ± adc_threshold_chosen`). Pink shaded bands
  mark the final `signal_bool` (post-`pad_window_{front,back}`)
  protection windows.
- **Bottom — deconvolved median, aligned in original time.**
  `medians_decon` is circular-shifted by `+res_offset` before storage
  so features line up with the top panel. Red dashed line is
  `decon_threshold_chosen` (the `protection_factor × rms_decon`
  clamp); purple dotted lines mark `±decon_limit1` (the per-ROI
  acceptance threshold) and `−decon_limit1 × roi_min_max_ratio`.
  Rectangles for each ROI are **green** if the median's
  `(max>decon_limit1) ∧ (|min| < max·ratio)` test passes,
  **red** otherwise. Hover any ROI rectangle to see:

  - `start..end` (bin range)
  - `max(median_decon)`, `min(median_decon)`
  - `|min|/max` observed
  - whether the **median** accepts (the bottom-panel decision)
  - **ch accept count** — how many of the group's channels voted
    accept on their *own* `signal_roi_decon` (the per-channel
    decision actually used by `Subtract_WScaling`)

The header bar shows the full set of knobs in scope — `protection_factor`,
`min_adc_limit`, `upper_adc_limit`, `upper_decon_limit`, `decon_limit1`,
`roi_min_max_ratio`, `pad_front`, `pad_back`, the `adc_threshold_chosen`
and `decon_threshold_chosen` actually selected, RMS, mean, and the SP
filter names (`Wiener_tight_*`, `ROI_tighter_lf`, `ROI_loose_lf`).

Controls (top row, left to right):

- `Run/Event/APA` dropdown — selects a `<RUN_EVT>/apa<N>` from the dump
  tree.
- `[U|V|W]` plane radio.
- `Group (gid)` dropdown — first-channel ident.
- `◀ Prev` / `Next ▶` — step through groups within the selected plane.

---

## NPZ schema (per group)

`np.load(<plane>_g<gid>.npz)` exposes:

| key                          | dtype  | shape       | meaning |
|------------------------------|--------|-------------|---------|
| `apa`, `gid`, `plane`        | int32  | (1,)        | group identity (plane: 0=U,1=V,2=W) |
| `nbin`, `res_offset`         | int32  | (1,)        | waveform length, deconv→time offset |
| `channels`                   | int32  | (nch,)      | per-channel idents |
| `decon_limit`, `decon_limit1`, `roi_min_max_ratio`, `min_adc_limit`, `upper_adc_limit`, `upper_decon_limit`, `protection_factor` | float32 | (1,) | knobs from chndb |
| `pad_front`, `pad_back`      | int32  | (1,)        | pad-window in ticks |
| `time_filter_name`, `lf_tighter_filter_name`, `lf_loose_filter_name` | int8 | (n,) | filter component names (raw bytes; `bytes(arr).decode()`) |
| `median`                     | float32| (nbin,)     | medianed ADC waveform |
| `medians_decon_aligned`      | float32| (nbin,)     | deconvolved median, **time-aligned** by `res_offset` (zeros if `decon_stage_ran=0`) |
| `signal_bool_raw`            | uint8  | (nbin,)     | threshold crossings only (no pad) |
| `signal_bool`                | uint8  | (nbin,)     | final protection mask (after pad_window expansion) |
| `adc_threshold_chosen`, `decon_threshold_chosen` | float32 | (1,) | clamped/chosen thresholds actually used |
| `rms_adc`, `rms_decon`, `mean_adc`, `mean_decon` | float32 | (1,) | per-stage statistics |
| `decon_stage_ran`            | uint8  | (1,)        | 1 if respec gate enabled the deconv stage |
| `roi_starts`, `roi_ends`     | int32  | (nrois,)    | inclusive bin ranges, original time |
| `roi_max_median`, `roi_min_median`, `roi_ratio_median` | float32 | (nrois,) | computed on `medians_decon` |
| `roi_accepted_median`        | uint8  | (nrois,)    | per-ROI accept on the median (test: `max>decon_limit1` ∧ `|min|<max·ratio`) |
| `scaling_coef`               | float32| (nch,)      | per-channel scaling applied in `Subtract_WScaling` (parallel to `channels`) |
| `ave_coef`                   | float32| (1,)        | group-average coef |
| `roi_max_per_ch`, `roi_min_per_ch`, `roi_accepted_per_ch` | float32/uint8 | (nch×nrois,) | row-major (nch, nrois) decision matrix from per-channel `signal_roi_decon` |

The per-channel decision matrix is what `Subtract_WScaling` actually
acts on; the per-ROI median scalars are the comparison view that
makes the threshold cuts (`decon_limit1`, `roi_min_max_ratio`)
visible.

---

## Tuning workflow

The viewer is built around a specific question: **are
`decon_limit1` and `roi_min_max_ratio` set sensibly?**

Indicators a ROI's accept decision is on a knife edge:

- ROI rectangle is red (median rejects) but `ch accept count` is high
  → the per-channel decisions are accepting; either the median is
  drowning real signal in noise (consider **lowering** `decon_limit1`)
  or the ROI shouldn't be subtracted in the first place.
- ROI rectangle is green but the `|min|/max` ratio is close to
  `roi_min_max_ratio` → the asymmetry test is barely passing; consider
  whether the chosen `roi_min_max_ratio` is too lenient.
- The `decon_threshold_chosen` line on the bottom panel is at
  `upper_decon_limit` rather than `protection_factor × rms_decon` →
  the noise level is below the clamp, the clamp is doing the work.

The C++ writer is in `sigproc/inc/WireCellSigProc/CoherentNoiseDump.h`.
The dump-fill call sites are in `sigproc/src/ProtoduneHD.cxx` (and
the symmetric PDVD). Per-channel `signal_roi_decon` arrays are
*not* dumped in v1 (they would be ~1 MB/group); add a separate
toggle if drilling into individual channels becomes useful.

---

## Off-state guarantee

When `debug_dump_path == ""` the only added cost is one `.empty()`
check per `apply()` group; no `CoherentNoiseDump` is constructed and
`SignalProtection` / `Subtract_WScaling` receive a `nullptr`
out-pointer. Verified: dump-OFF and dump-ON inner `*.npy` are
`np.array_equal` true across adjacent toolkit runs (the toolkit's
own run-to-run drift, ≈ rms 0.11 ADC, is the entire delta and
unchanged by the toggle).
