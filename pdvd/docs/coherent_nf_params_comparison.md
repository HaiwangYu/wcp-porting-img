# Coherent-noise removal parameters: PDVD vs MicroBooNE vs SBND vs PDHD

Reference for tuning PDVD coherent-NF parameters. Lists the parameters
read by `<Experiment>::CoherentNoiseSub::apply()` from the chndb
configuration, plus the front-end electronics gain and ADC scale that
set the absolute-magnitude meaning of the ADC-domain thresholds.

Wireup notes:

- All four experiments wire `OmnibusNoiseFilter.multigroup_chanfilters`
  with a per-experiment subclass of the same coherent-NF algorithm:
  `MicroBooNE::CoherentNoiseSub`, `SBND::CoherentNoiseSub` (uses the
  Microboone implementation), `PDVD::CoherentNoiseSub`,
  `PDHD::CoherentNoiseSub`. The C++ flow is the same:
  `CalcMedian → SignalProtection(median) → Subtract_WScaling`.
- Per-channel parameters are pulled from
  `OmniChannelNoiseDB::ChannelInfo` via the `coherent_nf_*` accessors.
  Anything not set in the experiment's `chndb-base.jsonnet` falls back
  to the C++ `ChannelInfo` defaults (column "C++ default" below).

---

## 1. Per-channel coherent-NF parameters

### Defaults in C++ (`OmniChannelNoiseDB::ChannelInfo`)

Source: `sigproc/src/OmniChannelNoiseDB.cxx:46`

| field | C++ default |
|---|---|
| `nominal_baseline` | 0.0 |
| `gain_correction` | 1.0 |
| `response_offset` | 0.0 ticks |
| `pad_window_front` | 0 ticks |
| `pad_window_back` | 0 ticks |
| `decon_limit` | 0.02 |
| `decon_lf_cutoff` | **0.08** |
| `adc_limit` | 0.0 |
| `decon_limit1` | 0.08 |
| `protection_factor` | **5.0** |
| `min_adc_limit` | **50** |
| `roi_min_max_ratio` | 0.8 |
| `min_rms_cut` | 0.5 |
| `max_rms_cut` | 10.0 |

### Default-block values (channels: full anode)

| parameter | uBooNE U | uBooNE V | uBooNE W | SBND U | SBND V | SBND W | PDVD bottom U | PDVD bottom V | PDVD bottom W | PDVD top U | PDVD top V | PDVD top W | PDHD U | PDHD V | PDHD W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `nominal_baseline` (ADC) | 2048 | 2048 | **400** | 2001 | 2001 | **650** | 2048 | 2048 | 2048 | 2048 | 2048 | 2048 | 2048 | 2048 | **400** |
| `response_offset` (ticks) | **79** | **82** | 0 | **120** | **124** | 0 | **239** | **245** | 0 | **240** | **243** | 0 | **127** | **132** | 0 |
| `pad_window_front` (ticks) | **20** | 10 | 10 | **20** | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| `pad_window_back` (ticks) | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| `decon_limit` | 0.02 | **0.025** | **0.05** | 0.02 | **0.01** | **0.05** | **0.01** | **0.01** | **0.05** | 0.02 | 0.02 | **0.05** | **0.01** | **0.01** | **0.05** |
| `decon_limit1` | 0.09 | **0.08** | **0.08** | **0.07** | 0.08 | 0.08 | **0.07** | **0.07** | 0.08 | **0.07** | **0.07** | 0.08 | **0.07** | **0.07** | 0.08 |
| `decon_lf_cutoff` | 0.08 | **0.06** | 0.08 | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) | (C++ 0.08) |
| `adc_limit` (ADC) | 15 | 15 | 15 | 15 | 15 | 15 | **60** *gs* | **60** *gs* | **60** *gs* | **60** | **60** | **60** | **60** *gs†* | **60** *gs†* | **60** *gs†* |
| `protection_factor` | **5** | 5 | 5 | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) | (C++ 5) |
| `min_adc_limit` (ADC) | **50** | 50 | 50 | (C++ 50) | (C++ 50) | (C++ 50) | **200** *gs* | **200** *gs* | **200** *gs* | **200** | **200** | **200** | **200** *gs†* | **200** *gs†* | **200** *gs†* |
| `roi_min_max_ratio` | 0.8 | 0.8 | 0.8 | **3.0** | **1.5** | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 |

Notes:

- *gs* = `gain_scale = params.elec.gain / (7.8 mV/fC)` for PDVD bottom
  electronics (anodes 0–3); identically `1.0` for top (anodes 4–7).
  When `params.elec.gain = 7.8 mV/fC` (the default), gain_scale = 1.0
  and all the bottom values match the table without the *gs* multiplier.
- *gs†* = `gain_scale = params.elec.gain / (14.0 mV/fC)` for PDHD.
  At `params.elec.gain = 14.0 mV/fC`, gs† = 1.0 and the table values
  equal the numeric coefficient.  At 7.8 mV/fC, gs† = 0.557.
  Note: the 14 mV/fC anchor in PDHD differs from the 7.8 mV/fC anchor
  in PDVD bottom — a gs = 1.0 means different things in each context.
- "(C++ X)" means the chndb does not set the field, so the C++
  ChannelInfo default applies.
- Where uBooNE, SBND, and PDHD override per-plane values, the override
  is in the per-plane `channel_info[]` entries; PDVD now also applies
  per-plane U/V overrides for `decon_limit` and `decon_limit1`
  (see PDVD U/V override column above).
- PDHD and PDVD both set `adc_limit = 60·gs` (PDVD bottom uses *gs*
  anchored to 7.8 mV/fC; PDVD top gain_scale=1 so the value is 60
  directly), reflecting that the finer ADC step of the 14-bit DUNE
  electronics requires a raised raw-ADC threshold to stay at a similar
  charge floor (see Section 3). `min_adc_limit` is likewise raised to
  200·gs (bottom) / 200 (top) for PDVD, matching PDHD.
- **PDHD APA 0 V-plane hardware override**: in PDHD APA 0 the V plane
  is hardware-faulty and behaves as a collection plane.  The chndb
  function in `cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet` sets
  `response: {}` and `response_offset: 0` for the V channels of APA 0
  only (`n == 0`), which causes `PDHD::SignalProtection`'s
  deconvolution gate to fall through (`respec.size()>0 &&
  respec[0]!=(1,0) && res_offset!=0` becomes false).  The other
  thresholds (`decon_limit`, `decon_limit1`, `roi_min_max_ratio`,
  RMS cuts) remain at the V-plane values.
- **PDVD FR⊗ER convolution window**: the PDVD FR file
  (`protodunevd_FR_norminal_260324.json.bz2`) has a native length of
  ~132.5 µs, shorter than the bipolar induction tail of either PDVD
  electronics set.  Without padding, the FFT-based convolution in
  `wirecell-sigproc track-response` wraps the slow recovery tail back
  into the early bins.  Both `pdvd-bottom` and `pdvd-top` defaults set
  `output_window: "160*us"` (in `track_response_defaults.jsonnet`),
  which zero-pads FR/ER to 320 ADC ticks (160 µs / 500 ns) before
  convolving.  The negative-peak position is unaffected by padding,
  so the table `response_offset` values (bot 239/245, top 240/243)
  hold for both the original 132.5 µs and the new 160 µs kernels;
  only the kernel content (especially the slow tail) is corrected.

### `roi_min_max_ratio` — what it controls

In `Subtract_WScaling` (e.g. `ProtoduneHD.cxx:212`) each ROI from the
per-channel signal-protection mask is examined in the
**deconvolved** waveform `signal_roi_decon` (with `res_offset` applied
so ADC bin `i` is read at deconv bin `i − res_offset`).  Within that
ROI window the code computes `max_val` and `min_val` of the
deconvolved trace, and tags the ROI as "real signal — protect the
median, do not subtract" when:

```
max_val > decon_limit1            // amplitude threshold
&& |min_val| < max_val * roi_min_max_ratio    // shape (uni-polarity) cut
```

Physical reading: a real charge deposit, after dividing the ADC
spectrum by the FR⊗ER kernel, should appear as a (mostly) unipolar
peak.  Coherent noise and induction-plane bipolar artifacts have
larger negative excursions relative to the positive peak.  The cut
asks: "is the deconvolved ROI sufficiently unipolar?"

| `roi_min_max_ratio` | meaning |
|---|---|
| **smaller** (e.g. 0.8) | strict — `|min|` must be < 80 % of max → only highly unipolar pulses are protected; more ROIs get their median subtracted |
| **larger** (e.g. 3.0) | permissive — almost any shape passes the cut → most ROIs are protected as "real signal" and the median is not subtracted on top of them |

So a higher value is *less* aggressive about removing coherent noise
inside the ROI.  Per-plane tuning reflects how unipolar the
post-deconv signal actually is for that plane: collection planes
naturally sit at 0.8 (default), induction planes can need looser values (SBND uses 3.0 for U and
1.5 for V) when the deconvolved induction signal is not unipolar
enough to pass the strict 0.8 cut.  PDHD induction planes were
tested at 3.0 / 1.5 but are now run at 0.8 across all three planes.

### Component-level filter parameter

| key | uBooNE | SBND | PDVD | PDHD |
|---|---|---|---|---|
| `rms_threshold` | 0.0 | 0.0 | 0.0 | 0.0 |

`rms_threshold = 0` means the per-channel veto in
`Subtract_WScaling` (skip subtraction if the channel's residual RMS
exceeds `rms_threshold * baseline_rms`) is disabled in all four
configurations.

---

## 2. Front-end electronics gain (mV/fC)

| experiment | `params.elec.gain` (mV/fC) | `params.elec.shaping` (μs) | `params.elec.postgain` |
|---|---|---|---|
| uBooNE | **14.0** | 2.2 | 1.2 |
| SBND | **14.0** (common-params default; not overridden) | 2.0 | 1.0 |
| PDVD bottom (anodes 0–3) | **7.8** (overridable) | 2.2 | 1.1365 |
| PDVD top (anodes 4–7) | n/a (uses `JsonElecResponse` waveform; effective FE gain ≈ 11 mV/fC × postgain 1.52 ≈ 16.7 mV/fC) | n/a (response built into JSON) | 1.52 |
| PDHD | external (`std.extVar("elecGain")`; typical 7.8 or 14.0) | 2.2 | (none in default block) |
| PDSP | (uses common defaults) | 2.2 | 1.1365 |

The "FE gain in ADC at the conventional unit charge" is

```
ADC_per_fC  =  elec.gain  ×  postgain  ×  (ADC counts per mV)
```

so every doubling of `elec.gain` halves the *charge* equivalent of a
fixed ADC threshold like `adc_limit = 60`. PDVD's `gain_scale`
multiplier on bottom-anode chndb thresholds re-anchors them to a
constant *charge* threshold when `params.elec.gain` is varied away
from the 7.8 mV/fC reference. PDHD uses the same technique anchored
to 14.0 mV/fC.

---

## 3. ADC scale (mV → ADC conversion)

ADC LSB = (`fullscale.max` − `fullscale.min`) / (2^`resolution` − 1).

| experiment | `adc.fullscale` (V) | `adc.resolution` (bits) | mV per ADC | ADC per mV | `adc.baselines` (mV, U/V/W) |
|---|---|---|---|---|---|
| uBooNE | 0.0 – 2.0 | 12 | 0.4884 | 2.048 | 999.3 / 999.3 / 231.0 |
| SBND | 0.0 – 1.8 | 12 | 0.4396 | 2.275 | 879.5 / 879.5 / 286.0 |
| PDVD (bottom CRP) | 0.2 – 1.6 | 14 | 0.08545 | 11.70 | 1003.4 / 1003.4 / 507.7 |
| PDVD (top CRP) | 0.0 – 2.0 | 14 | 0.1221 | 8.192 | ~1000 / ~1000 / ~1000 (rewritten in sim/digitizer; see `params.jsonnet:114`) |
| PDHD | 0.2 – 1.6 | 14 | 0.08545 | 11.70 | 1003.4 / 1003.4 / 507.7 |
| PDSP | 0.2 – 1.6 | 14 | 0.08545 | 11.70 | 1003.4 / 1003.4 / 507.7 |

Note: 12-bit experiments (uBooNE, SBND) have ~5× coarser ADC steps
than the 14-bit DUNE experiments, so an ADC-domain threshold of
`15 ADC` represents very different mV / charge across experiments:

| experiment | 15 ADC = mV | at this gain → 15 ADC = fC | 15 ADC = ke- |
|---|---|---|---|
| uBooNE | 7.32 mV | 0.523 fC (gain 14 mV/fC) | **3.27 ke-** |
| SBND | 6.59 mV | 0.471 fC (gain 14) | **2.94 ke-** |
| PDVD bottom (gain 7.8) | 1.28 mV | 0.165 fC | **1.03 ke-** |
| PDVD top (effective ~11 mV/fC × postgain 1.52) | 1.83 mV | 0.110 fC | **0.69 ke-** |
| PDHD (gain 14 mV/fC) | 1.28 mV | 0.0916 fC | **0.57 ke-** |

(1 fC ≈ 6242 e-)

PDHD and PDVD both set `adc_limit = 60·gs` (PDHD: *gs†* anchored to
14.0 mV/fC; PDVD bottom: *gs* anchored to 7.8 mV/fC; PDVD top: 60
directly since gain_scale=1).  At the reference gain for each:
60 ADC × 0.08545 mV/ADC (PDHD) = **5.13 mV** = 0.366 fC = **2.29 ke-**
60 ADC × 0.08547 mV/ADC (PDVD bottom) = **5.13 mV** = 0.658 fC = **4.11 ke-**
60 ADC × 0.1221 mV/ADC (PDVD top) = **7.32 mV** ≈ **2.73 ke-**

PDHD and PDVD both set `min_adc_limit = 200·gs` (anchored to 14 mV/fC
and 7.8 mV/fC respectively; PDVD top gain_scale=1 so the value is 200
directly). At reference gain for each:
200 × 0.08545 mV/ADC (PDHD) = 17.1 mV, close to uBooNE's
50 × 0.4884 mV = 24.4 mV.  uBooNE/SBND use 50 (C++ default).

---

## 4. Wire pitch (U / V / W)

Wire pitch determines the spatial density of induced charge per ionisation
track segment and therefore the expected induction-signal amplitude. A
larger pitch means fewer induced electrons per wire per unit track length
(all else equal), so induction signals are weaker relative to a fixed ADC
noise floor.

| experiment | U pitch (mm) | V pitch (mm) | W pitch (mm) | notes |
|---|---|---|---|---|
| uBooNE | 3.00 | 3.00 | 3.00 | |
| SBND | 3.00 | 3.00 | 3.00 | |
| PDHD | 4.67 | 4.67 | 4.79 | wires at ±35.7° / 0° |
| PDVD | 7.65 | 7.65 | 5.10 | strip geometry; no wire crossings on induction planes |

Source: `wirecell-util wires-info` on the respective wires JSON files
(see Section 6 for filenames).

The induction pitch ordering uBooNE ≈ SBND (3 mm) < PDHD (4.67 mm) < PDVD
(7.65 mm) implies progressively weaker induction signals in PDHD and
especially PDVD for the same deposited charge. This has direct
implications for `decon_limit` and `roi_min_max_ratio` tuning:
tighter limits that protect the median in uBooNE may over-protect in PDVD
if its induction signals are weaker per unit noise. The PDHD values
(response_offset, per-plane roi_min_max_ratio, response waveforms) are
a reasonable intermediate reference for PDVD tuning.

---

## 5. Quick observations for tuning PDVD

The points below are pattern observations against uBooNE/SBND/PDHD, not
recommendations — pick the ones worth investigating.

1. **Per-plane tuning is missing from PDVD**. uBooNE, SBND, and PDHD
   override `decon_limit`, `decon_limit1`, `roi_min_max_ratio`,
   `pad_window_front`, and `response_offset` per induction/collection
   plane. PDVD uses a single default block. At minimum:
   - `roi_min_max_ratio`: SBND uses 3.0 (U) / 1.5 (V) / 0.8 (W).
     PDVD's 0.8 across all planes matches the latest PDHD setting and
     lets more induction-plane "noise ROIs" through into the
     median-protection step than the SBND-style induction tuning would.
   - `decon_limit` for W is 0.05 across PDVD/PDHD/uBooNE W, matching
     uBooNE's collection-plane setting. U/V use 0.01 (bot) / 0.02 (top),
     aligned with PDHD's induction setting of 0.01.
   - `response_offset`: uBooNE sets 79/82 ticks (U/V); PDHD sets 127/132;
     PDVD now sets 239/245 (bottom) and 240/243 (top), derived from the
     argmin of the respective FR⊗ER kernels in `chndb-resp-bot.jsonnet`
     and `chndb-resp-top.jsonnet`.

2. **Per-plane FR⊗ER response waveform now set for PDVD**. The U and V
   planes now have `response: { waveform: scale_resp(u/v_resp_arr), ... }`
   entries in `chndb-base.jsonnet`, selecting between `chndb-resp-bot.jsonnet`
   (bottom CRP, anodes 0–3) and `chndb-resp-top.jsonnet` (top CRP, anodes
   4–7) depending on `n`. W planes retain `response: {}` (collection plane,
   no deconvolution needed).

3. **`decon_lf_cutoff` not set**. uBooNE customises this (0.06 for V).
   PDVD and PDHD inherit the C++ default (0.08).

4. **`min_adc_limit` and `protection_factor`**. PDHD and PDVD both set
   `min_adc_limit = 200·gs` (PDHD: gs† anchored to 14 mV/fC; PDVD bottom:
   gs anchored to 7.8 mV/fC; PDVD top: 200 directly). At reference gain
   200 × 0.08545 mV/ADC ≈ 17 mV, matching uBooNE's 50 × 0.4884 mV ≈ 24 mV
   within a factor ≈ 1.4. uBooNE/SBND use the C++ default of 50.
   `protection_factor` remains at the C++ default (5) for all detectors.

5. **`adc_limit` in raw ADC** has very different mV/charge meaning across
   experiments (table above). PDVD's `gain_scale` multiplier helps for
   bottom anodes, but top anodes use a fixed scale and the threshold
   is the tightest of any experiment. PDHD raises the raw threshold to
   60·gs† for a charge equivalent closer to uBooNE/SBND (see Section 3).

6. **Wire pitch** (Section 4): PDVD induction strips are 7.65 mm wide
   (vs 3 mm for uBooNE/SBND, 4.67 mm for PDHD). Weaker induction
   signals suggest that `roi_min_max_ratio` and `decon_limit` may need
   to be *looser* (less protective) in PDVD than in uBooNE/SBND/PDHD,
   not tighter.

7. **`pad_window_front/back`**. PDVD uses 10 ticks symmetrically (same
   as the PDHD default). uBooNE and SBND bump *front* to 20 on induction
   to accommodate the bipolar pre-lobe; PDVD's wider-pitch induction
   response does not require this extra leading padding.

---

## 6. Source files

- uBooNE chndb: `cfg/pgrapher/experiment/uboone/chndb-base.jsonnet`
- SBND chndb: `cfg/pgrapher/experiment/sbnd/chndb-base.jsonnet`
- PDVD chndb: `cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet`
- PDHD chndb: `cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet`
- PDVD nf wiring: `cfg/pgrapher/experiment/protodunevd/nf.jsonnet`
- C++ defaults: `sigproc/src/OmniChannelNoiseDB.cxx:46` (ChannelInfo ctor)
- C++ apply(): `sigproc/src/Microboone.cxx:780` (uBooNE/SBND);
  `sigproc/src/ProtoduneVD.cxx:931` (PDVD); `sigproc/src/ProtoDuneHD.cxx` (PDHD)
- params: `cfg/pgrapher/experiment/{uboone,sbnd,protodunevd,pdhd,pdsp}/params.jsonnet`
- common-params defaults (for inheritance): `cfg/pgrapher/common/params.jsonnet`
- Wire geometry JSONs (for `wirecell-util wires-info`):
  - uBooNE: `microboone-celltree-wires-v2.1.json.bz2`
  - SBND: `sbnd-wires-larsoft-v1.json.bz2`
  - PDHD: `protodunehd-wires-larsoft-v1.json.bz2`
  - PDVD: `dunevdcrp2-wires-larsoft-v1.json.bz2`
