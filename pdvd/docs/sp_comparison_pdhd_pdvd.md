# SP Chain Comparison — ProtoDUNE-HD vs ProtoDUNE-VD

For per-detector detail see [`pdhd/docs/sp.md`](../../pdhd/docs/sp.md) and
[`pdvd/docs/sp.md`](../../pdvd/docs/sp.md).  For the NF chain comparison see
[`pdvd/docs/nf_comparison_pdhd_pdvd.md`](nf_comparison_pdhd_pdvd.md).

All claims below are validated against
`cfg/pgrapher/experiment/{pdhd,protodunevd}/sp{,-filters}.jsonnet` and
`cfg/pgrapher/experiment/protodunevd/params.jsonnet`.

---

## 1. Pipeline shape

| Aspect | PDHD | PDVD |
|--------|------|------|
| Anodes per pipeline | 4 (APAs) | 8 (4 bottom CRPs + 4 top CRPs) |
| Per-anode SP factory | `make_sigproc(anode)` (`pdhd/sp.jsonnet:29`) | same function name (`protodunevd/sp.jsonnet:25`) |
| Sub-graph composition | `OmnibusSigProc` → optional L1SP merger | same |
| Per-anode branching axis | APA0 vs APA1–3 (geometry / wire orientation) | bottom (`ident<4`) vs top (`ident≥4`) (electronics + ADC fullscale) |
| `use_multi_plane_protection` default | `false` | `true` |
| L1SP default mode | `'process'` (live) | `'dump'` (calibration phase — kernels not yet validated) |

---

## 2. Per-anode branching — what splits and on what axis

### PDVD: top vs bottom (electronics, not geometry)

PDVD splits on electronics, not wire-orientation anomalies.  The filter
name suffixes `_b` (ident 0–3) and `_t` (ident 4–7) exist throughout
`sp-filters.jsonnet` and `sp.jsonnet`, but **the numerical values in every
`_b` and `_t` filter are currently byte-identical**.  The top/bottom split
is a structural hook for future independent tuning, not an active
parameter difference.  The only knobs that truly differ between top and
bottom today are electronics-derived:

| Knob | Bottom (ident 0–3) | Top (ident 4–7) | Why |
|------|--------------------|-----------------|-----|
| `elecresponse` | `tools.elec_resps[0]` — `ColdElecResponse`, 7.8 mV/fC, 2.2 µs shaping (`params.jsonnet:124–126`) | `tools.elec_resps[1]` — `JsonElecResponse` from `dunevd-coldbox-elecresp-top-psnorm_400.json.bz2`, postgain 1.52 (`params.jsonnet:129–132`) | Physically distinct front-end electronics on the two drift faces |
| `fullscale` (→ `ADC_mV`) | `params.adc.fullscale[1] − [0]` = 1.4 V → `ADC_mV` ≈ 11.71 / mV | hard-overridden to 2.0 V → `ADC_mV` ≈ 8.19 / mV (`sp.jsonnet:66–69`) | Top ADC spans 0–2 V; bottom 0.2–1.6 V |
| L1SP `kernels_file` | `pdvd_bottom_l1sp_kernels.json.bz2` | `pdvd_top_l1sp_kernels.json.bz2` | Per-region response kernels generated offline |
| L1SP `gain_scale` | `elec.gain / 7.8 mV/fC` | `1.0` (top gain is JSON-fixed; no runtime knob) | Reference electronics differ by region |
| L1SP `gauss_filter` | `'HfFilter:Gaus_wide_b'` | `'HfFilter:Gaus_wide_t'` | Picks the same-region Gaus_wide instance |

Everything else in the SP stage — all ROI threshold knobs, filter parameters,
multi-plane protection — is **the same for top and bottom**.

### PDHD vs PDVD per-anode branching compared

| Knob | PDHD APA0 | PDHD APA1–3 | PDVD (bottom = top for these) |
|------|-----------|-------------|-------------------------------|
| `field_response` | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` | `dune-garfield-1d565.json.bz2` | `protodunevd_FR_imbalance3p_260501.json.bz2` (uniform; top = bottom) |
| `filter_responses_tn` | 3 `FilterResponse` objects (U↔V order swap) | `[]` | not used |
| `plane2layer` | `[0, 2, 1]` (U↔V swap) | `[0, 1, 2]` | not configured (default `[0,1,2]`) |
| `r_th_factor` | `2.5` (looser) | `3.0` | `3.0` (uniform) |
| Wiener tight filter set | `_APA1` triplet (narrower σ) | default triplet | single triplet, `_b` == `_t` (identical values) |
| L1SP `process_planes` | `[0]` (APA0 V anomalous) | `[0, 1]` | `[0, 1]` for all anodes |

PDHD branches to handle a known APA0 wire-orientation anomaly; PDVD branches
to handle physically distinct electronics.  PDVD has no equivalent of PDHD's
APA0 U↔V correction or its loosened refinement threshold.

---

## 3. `OmnibusSigProc` knobs that are the same in both detectors

These knobs are set to the same literal value in `pdhd/sp.jsonnet` and
`protodunevd/sp.jsonnet`.  Where both override a WCT built-in default that
differs from the configured value, it is strong evidence the PDVD numbers
were copied from PDHD without independent tuning.

| Knob | Common value | WCT built-in default | Notes |
|------|-------------|----------------------|-------|
| `ftoffset` | `0.0` µs | `0.0` | field-response time offset |
| `fft_flag` | `0` | `0` | low-memory FFT path |
| `postgain` | `1.0` | `1.2` | **both override the default** — strong copy signal |
| `isWrapped` | `false` | — | wires/strips do not wrap |
| `troi_col_th_factor` | `5.0` | `5.0` | tight-ROI collection threshold (× noise RMS) |
| `troi_ind_th_factor` | `3.0` | `3.0` | tight-ROI induction threshold |
| `lroi_rebin` | `6` | `6` | rebin factor for loose-ROI search |
| `lroi_th_factor` | `3.5` | `3.5` | loose-ROI primary threshold |
| `lroi_th_factor1` | `0.7` | `0.7` | loose-ROI secondary (lower wing) |
| `lroi_jump_one_bin` | `1` | `0` | **both override the default** — allows ROI to bridge 1 empty bin |
| `r_fake_signal_low_th` | `375` | `500` | **both override the default** fake-signal rejection lower bound (e⁻) |
| `r_fake_signal_high_th` | `750` | `1000` | **both override the default** fake-signal upper bound (e⁻) |
| `r_fake_signal_low_th_ind_factor` | `1.0` | `1.0` | induction scale factor (lower) |
| `r_fake_signal_high_th_ind_factor` | `1.0` | `1.0` | induction scale factor (upper) |
| `r_th_peak` | `3.0` | `3.0` | peak detection threshold within refined ROI |
| `r_sep_peak` | `6.0` | `6.0` | minimum peak separation (ticks) |
| `r_low_peak_sep_threshold_pre` | `1200` | `1200` | pre-split charge threshold (e⁻) |

The three overrides of WCT defaults (`postgain`, `lroi_jump_one_bin`,
`r_fake_signal_*`) appear verbatim in both configs with identical numeric
values — the PDVD numbers were almost certainly carried forward from PDHD,
not independently retuned for the VD geometry.

---

## 4. `OmnibusSigProc` knobs that differ

| Knob | PDHD | PDVD | Why / status |
|------|------|------|--------------|
| `ctoffset` | `1.0 µs` (`pdhd/sp.jsonnet:61`) | `4.0 µs` (`protodunevd/sp.jsonnet:97`) | Must align the deconvolved output with the field-response reference time; determined by the FR file used. PDVD comment: "consistent with FR: `protodunevd_FR_imbalance3p_260501.json.bz2`" |
| `field_response` | per-APA (APA0 vs APA1–3; two files) | uniform — one file for all 8 anodes | PDVD uses a single simulated response for both drift faces |
| `filter_responses_tn` | APA0 only, 3 entries | not used at all | PDHD-only per-plane frequency correction; no PDVD equivalent |
| `r_th_factor` | `2.5` (APA0) / `3.0` (APA1–3) | `3.0` uniform | PDHD loosens refinement on APA0 to compensate for the V-plane anomaly; no PDVD analogue |
| `use_multi_plane_protection` | `false` | `true` | Real algorithmic difference: PDVD enables MP3/MP2 coincidence vetoes to suppress single-plane fake ROIs; PDHD leaves it off. Origin not documented; likely enabled during PDVD commissioning to reduce isolated induction-plane noise artefacts. |
| `plane2layer` | `[0,2,1]` (APA0) / `[0,1,2]` (APA1–3) | not set (uses default `[0,1,2]`) | U↔V swap is an APA0-specific geometry detail; not applicable to CRP strip geometry |
| `wiener_threshold_tag` | commented out in PDHD (deprecated) | still set (`'threshold%d'`) in PDVD | Minor: PDVD still emits the per-channel threshold summary trace tag under that name |
| `Wiener_tight_filters` list | APA0: `_APA1` set; APA1–3: default set | bottom/top: `_b` / `_t` sets respectively (values identical) | Structural split only on PDVD |

---

## 5. Filter catalogue — `sp-filters.jsonnet`

### Key observation: PDVD `_b` == PDVD `_t`

Every filter in `protodunevd/sp-filters.jsonnet` is registered twice under
the `_b` (bottom) and `_t` (top) suffixes.  **All numerical values are
currently byte-identical between the two**.  The table below therefore lists
a single PDVD column; where it says "PDVD `_b`" read it as equally applying
to `_t`.

### Low-frequency (LF) filters

| Name | PDHD τ (MHz) | PDVD `_b`/`_t` τ (MHz) | Same? | Notes |
|------|-------------|------------------------|-------|-------|
| `ROI_loose_lf` | `0.002` | `0.002` | ✅ | identical |
| `ROI_tight_lf` | `0.016` | `0.014` | ❌ slight | PDVD ~13% lower — marginally broader time support for tight ROIs |
| `ROI_tighter_lf` | `0.08` | `0.06` | ❌ | PDVD ~25% lower — broader LF envelope in the refinement path |

Higher τ → stronger low-frequency rejection → tighter ROI boundary.

### Gaussian (HF) filters

| Name | PDHD σ (MHz) | PDVD σ (MHz) | Same? |
|------|-------------|--------------|-------|
| `Gaus_tight` | `0.0` | `0.0` | ✅ |
| `Gaus_wide` | `0.12` | `0.12` | ✅ — identical; also seeds the L1SP smearing kernel |

### Wiener tight filters (primary output path)

| Plane | PDHD APA1–3 σ / power | PDHD APA0 (`_APA1`) σ / power | PDVD `_b`/`_t` σ / power | Same as PDHD APA1–3? | Notes |
|-------|----------------------|-------------------------------|---------------------------|----------------------|-------|
| U | `0.221933` / `6.55413` | `0.203451` / `5.78093` | `0.148788` / `3.76194` | ❌ | PDVD σ is narrower than both PDHD sets |
| V | `0.222723` / `8.75998` | `0.160191` / `3.54835` | `0.1596568` / `4.36125` | ❌ | PDVD σ close to PDHD APA0 V but not identical |
| W | `0.225567` / `3.47846` | `0.125448` / `5.27080` | `0.13623` / `3.35324` | ❌ | PDVD σ close to PDHD APA0 W range |

The PDVD Wiener-tight values match neither PDHD's current APA1–3 set
nor its APA0 `_APA1` set.  They are consistent with the May-2019
commented-out WCT default block that appears at the top of both
`sp-filters.jsonnet` files — suggesting PDVD inherited an older
pre-PDHD-tuning snapshot rather than copying PDHD's calibrated values.
This is worth verifying with the author: it may have been an intentional
conservative starting point, or an accidental inheritance from a stale
copy.

### Wiener wide filters (alternative path; not selected by default)

| Plane | PDHD σ / power | PDVD `_b`/`_t` σ / power | Same? |
|-------|---------------|---------------------------|-------|
| U | `0.186765` / `5.05429` | `0.186765` / `5.05429` | ✅ byte-exact |
| V | `0.1936` / `5.77422` | `0.1936` / `5.77422` | ✅ byte-exact |
| W | `0.175722` / `4.37928` | `0.175722` / `4.37928` | ✅ byte-exact |

The wide Wiener set is copied exactly from PDHD (neither is selected by
default in either detector's `wct-nf-sp.jsonnet`).

### Wire-domain (spatial) filters

| Name | PDHD σ (wire units) | PDVD `_b`/`_t` σ | Same? | Notes |
|------|---------------------|------------------|-------|-------|
| `Wire_ind` | `0.75/√π` ≈ `0.423` | `5.0/√π` ≈ `2.82` | ❌ **6.7× wider** | CRP induction strips subtend more wires per track width than PDHD APA wires; narrow smoothing would underweight adjacent-strip signal. This appears to be an intentional PDVD-specific choice. |
| `Wire_col` | `10.0/√π` ≈ `5.64` | `10.0/√π` ≈ `5.64` | ✅ | identical |

---

## 6. L1SP — unipolar-induction correction

`L1SPFilterPD` runs downstream of `OmnibusSigProc` inside `make_sigproc`
when `l1sp_pd_mode != ''`.

| Knob | PDHD | PDVD bottom | PDVD top |
|------|------|-------------|---------|
| `l1sp_pd_mode` default | `'process'` (live; replaces gauss/wiener) | `'dump'` (tagger only; SP output unchanged) | `'dump'` |
| `kernels_file` | `pdhd_l1sp_kernels.json.bz2` | `pdvd_bottom_l1sp_kernels.json.bz2` | `pdvd_top_l1sp_kernels.json.bz2` |
| `gain_scale` | `elec.gain / 14 mV/fC` | `elec.gain / 7.8 mV/fC` | `1.0` |
| `process_planes` default | APA0: `[0]` (V anomalous); APA1–3: `[0,1]` | `[0,1]` | `[0,1]` |
| `l1_len_very_long` / `l1_asym_very_long` | `140` / `0.35` (5th arm enabled) | C++ default (OFF) | C++ default (OFF) |
| `gauss_filter` | `'HfFilter:Gaus_wide'` | `'HfFilter:Gaus_wide_b'` | `'HfFilter:Gaus_wide_t'` |
| `l1_adj_enable` / `l1_adj_max_hops` | `true` / `3` | `true` / `3` | `true` / `3` |
| Raw-ADC thresholds at reference gain | `l1_raw_asym_eps=20`, `raw_ROI_th_adclimit=10`, `adc_sum_threshold=160` | same × gain_scale | same |

PDVD copies PDHD's raw-threshold numerical defaults and scales them to the
per-region reference electronics via `gain_scale`.  PDVD does not apply
PDHD's "very-long" 5th arm (`l1_len_very_long`, calibrated for run 027409
in 2026) or PDHD's APA0-specific V-plane suppression — those are
PDHD-specific calibration outcomes.

PDVD is currently in `dump` mode because the per-region kernels
(`pdvd_bottom_l1sp_kernels.json.bz2`, `pdvd_top_l1sp_kernels.json.bz2`)
have not yet been validated end-to-end.  Once validation passes, flipping
the default to `'process'` will activate the L1SP fit.

---

## 7. Output frame and downstream consumption

Identical between detectors:

- Output tags: `gauss{N}` (Gaussian charge), `wiener{N}` (Wiener-optimal)
- `FrameFileSink` with `digitize: false` and `masks: true`
- Per-channel threshold summary attached to `wiener{N}`
- Both `gauss{N}` and `wiener{N}` carry the L1SP result when L1SP is in
  `'process'` mode (the `FrameMerger` at the end of `make_sigproc` replaces
  both tags with the L1SP-modified gauss)

---

## 8. Quick-reference summary

| Question | PDHD | PDVD |
|----------|------|------|
| Multi-plane protection on by default? | No | Yes |
| Per-anode field-response file? | Yes (2 files) | No (1 file, shared) |
| Per-anode `r_th_factor`? | Yes (APA0=2.5) | No (uniform 3.0) |
| `filter_responses_tn` used? | APA0 only | No |
| `plane2layer` U↔V swap? | APA0 only | No |
| Top vs bottom electronics branching? | n/a | Yes (`elecresponse`, `fullscale`, L1SP) |
| Top vs bottom *filter parameters* differ? | n/a | **No** — `_b` == `_t` numerically |
| L1SP enabled by default? | Yes (`'process'`) | No (`'dump'`, calibration phase) |
| L1SP per-region kernel files? | Single file | Yes (bottom + top) |
| Wiener-tight tuning origin? | PDHD calibration (run 027409) | Appears to be a pre-2019 WCT baseline |
| Wiener-wide tuning? | PDHD calibration | Byte-exact copy from PDHD |
| Wire-domain induction smoothing | Narrow (`0.75/√π`) | Wide (`5.0/√π`, ~6.7× PDHD) |
| `lroi_jump_one_bin`, `postgain`, `r_fake_signal_*` | Override WCT defaults | Same overrides — likely copied from PDHD |

---

## 9. Implications

- **Most OmnibusSigProc knobs are shared.** The long list of matching values
  in section 3 means PDVD's deconvolution, ROI finding, and charge-extraction
  thresholds are essentially the PDHD numbers.  Any PDHD SP tuning study is a
  useful starting point for PDVD, modulo differences in noise level and
  detector geometry.

- **Multi-plane protection is a real algorithmic difference.** With
  `use_multi_plane_protection: true`, PDVD vetoes ROIs that appear in only
  one plane without matching activity elsewhere.  PDHD keeps those ROIs.
  This will produce systematically fewer but cleaner ROIs on PDVD, and
  any direct gauss-output comparison between the two detectors must account
  for this.

- **Wiener-tight filters on PDVD are likely stale.** They do not match
  PDHD's calibrated APA1–3 set (which is significantly wider), and they
  appear to match the pre-2019 WCT baseline that was commented out.  The
  Wiener-tight path affects the `wiener{N}` output (and through it, track
  finding); a re-tuning pass against PDVD data should be planned.

- **Wire-domain induction smoothing was independently tuned for CRP
  geometry.**  The `Wire_ind` change from `0.75/√π` to `5.0/√π` is one
  clear deliberate VD-specific choice, acknowledging that CRP induction
  strips span more channels per track than PDHD APA wires.

- **Top/bottom split is a structural hook, not a tuning.**  When
  VD-specific per-region SP calibration becomes available, the `_b`/`_t`
  suffix infrastructure is already in place.  No code changes needed — only
  new numerical values in `sp-filters.jsonnet`.

- **ctoffset encodes the FR reference time.**  The 3 µs difference between
  PDHD and PDVD is not a physics difference but a field-response file
  convention; if the FR file is replaced, `ctoffset` must be re-verified.

---

## 10. Source cross-reference

| File | PDHD | PDVD |
|------|------|------|
| SP pnode factory | `cfg/pgrapher/experiment/pdhd/sp.jsonnet` | `cfg/pgrapher/experiment/protodunevd/sp.jsonnet` |
| Filter catalogue | `cfg/pgrapher/experiment/pdhd/sp-filters.jsonnet` | `cfg/pgrapher/experiment/protodunevd/sp-filters.jsonnet` |
| Detector parameters | `cfg/pgrapher/experiment/pdhd/params.jsonnet` | `cfg/pgrapher/experiment/protodunevd/params.jsonnet` |
| Top-level NF+SP driver | `pdhd/wct-nf-sp.jsonnet` | `pdvd/wct-nf-sp.jsonnet` |
| C++ SP engine | `sigproc/src/OmnibusSigProc.cxx` (shared) | same |
| L1SP C++ | `sigproc/src/L1SPFilterPD.cxx` (shared) | same |
| L1SP docs | `sigproc/docs/l1sp/L1SPFilterPD.md` | same |
| Field-response file | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` (APA0) / `dune-garfield-1d565.json.bz2` (APA1–3) | `protodunevd_FR_imbalance3p_260501.json.bz2` (all anodes) |
