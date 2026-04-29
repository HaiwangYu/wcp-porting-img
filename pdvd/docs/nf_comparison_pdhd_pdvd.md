# NF Chain Comparison — ProtoDUNE-HD vs ProtoDUNE-VD

This document is mirrored at `pdhd/docs/nf_comparison_pdhd_pdvd.md` and
`pdvd/docs/nf_comparison_pdhd_pdvd.md`. For per-detector detail see
[`pdhd/docs/nf.md`](../../pdhd/docs/nf.md) and
[`pdvd/docs/nf.md`](../../pdvd/docs/nf.md).

All claims below are validated against the actual C++
(`sigproc/src/Protodune{HD,VD}.cxx`) and the jsonnet configs
(`cfg/pgrapher/experiment/{pdhd,protodunevd}/`).

---

## 1. Pipeline shape

| Aspect | PDHD | PDVD |
|--------|------|------|
| Anodes per pipeline | 4 (APAs) | 8 (4 bottom CRPs + 4 top CRPs) |
| Channels per anode | 2560 (800 U + 800 V + 960 W) | 3072 |
| Resampler step | None — DAQ already at 500 ns | **Bottom anodes only** (`ident < 4`), resample to 500 ns (`wct-nf-sp.jsonnet:111`) |
| Pre-NF channel selection | ChannelSelector in art (Part 1) | ChannelSelector in art (Part 1) |
| NF passes inside `OmnibusNoiseFilter` | 2 — per-channel + coherent group | 3 — per-channel + coherent group + **shield coupling** (top anodes only) |
| OmnibusNoiseFilter wiring | `channel_filters` + `grouped_filters` | `channel_filters` + `multigroup_chanfilters` (needed to attach two distinct group sets: coherent + shield) |
| Per-anode NF builder | `cfg/pgrapher/experiment/pdhd/nf.jsonnet` | `cfg/pgrapher/experiment/protodunevd/nf.jsonnet` |
| Per-channel filter | `PDHDOneChannelNoise` | `PDVDOneChannelNoise` |
| Coherent filter | `PDHDCoherentNoiseSub` | `PDVDCoherentNoiseSub` |
| Shield coupling filter | — (none) | `PDVDShieldCouplingSub`, top-U strips only (`nf.jsonnet:60-65`, `ident > 3`) |

**Validation:**
- PDHD channel-per-anode: `chndb-base.jsonnet:20–22` uses `n×2560 + ...` for U/V/W groups (40/40/48 ch per FEMB × 20 FEMBs).
- PDVD channel-per-anode: `funcs.jsonnet:24–29` `anode_channels :: function(n) { ret: [x + 3072 * crp for x in channels] }`.
- PDVD bottom-only resampler: `wct-nf-sp.jsonnet:111` `if use_resampler && n < 4 then [resamplers[n]]` (where `use_resampler = (reality == 'data')`; pass `-r sim` to skip).
- PDVD shield coupling restriction: `nf.jsonnet:60` `if anode.data.ident > 3 then [{...shieldcoupling_grouped}] else []`.

---

## 2. Per-channel filter — what *actually runs*

`OneChannelNoise::apply` body in each detector:

| Step | PDHD (`ProtoduneHD.cxx:808–875`) | PDVD (`ProtoduneVD.cxx:807–878`) |
|------|----------------------------------|-----------------------------------|
| FFT + DC bin kill | ✅ live (829) | ✅ live (827) |
| 6σ-clipped median baseline | ✅ live | ✅ live |
| RC-RC undershoot correction | **commented out** (`ProtoduneHD.cxx:819–822`) | **commented out** (`ProtoduneVD.cxx:820–823`) |
| `m_check_partial(spectrum)` (RC heuristic) | ⚙ **config-gated**: `bool is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false` (`ProtoduneHD.cxx:817`); `adaptive_baseline` defaults to `false` and is left at default in `pdhd/nf.jsonnet` — PDHD cold electronics is DC-coupled so the IS_RC branch has no physical meaning | ⚙ **config-gated**: `bool is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false` (`ProtoduneVD.cxx:819`); `adaptive_baseline` defaults to `false` and is left at default in `protodunevd/nf.jsonnet` — PDVD hardware is DC-coupled so the IS_RC branch has no physical meaning |
| Adaptive baseline (`SignalFilter` + `RawAdaptiveBaselineAlg` + `RemoveFilterFlags`) | **Never runs** — disabled by config (`adaptive_baseline=false`; PDHD is DC-coupled, see `Microboone.cxx:963-1047` for the IS_RC/adaptive-baseline pairing) | **Never runs** — disabled by config (`adaptive_baseline=false`; PDVD is DC-coupled, see `Microboone.cxx:963-1047` for the IS_RC/adaptive-baseline pairing) |
| `lf_noisy` tag on induction planes | **Never emitted** — push at `ProtoduneHD.cxx:853` not taken while `adaptive_baseline=false` | **Never emitted** — push at `ProtoduneVD.cxx:857` not taken while `adaptive_baseline=false` |
| `NoisyFilterAlg` (`min_rms_cut`/`max_rms_cut` test → `noisy` tag) | **Commented out** (`ProtoduneHD.cxx:861–872`) — `min_rms_cut: 1.0` / `max_rms_cut: 30.0` are dead | ✅ **Live** (`ProtoduneVD.cxx:862–887`) — per-anode-group, per-plane cuts active (see RMS threshold table in `pdvd/docs/nf.md`) |
| `SignalFilter` + `RemoveFilterFlags` around the noisy test | n/a (block commented) | ✅ live (PDVD lines 867, 869) |

**Net effect — what tags each per-channel filter actually produces:**

| Tag | PDHD | PDVD |
|-----|------|------|
| `lf_noisy` | ❌ never produced (`adaptive_baseline=false`) | ❌ never produced |
| `noisy` | ❌ never produced | ✅ produced when channel RMS is outside per-plane cut (see RMS threshold table in `pdvd/docs/nf.md`) |
| `sticky` / `ledge` | ❌ neither implemented | ❌ neither implemented |

Both detectors disable IS_RC + adaptive baseline by config (DC-coupled hardware). The only live per-channel tag difference is that **PDVD tags `noisy`** (via `NoisyFilterAlg`) while **PDHD produces no per-channel tags at all** in the current build.

**Validation:**
```
$ grep -n "is_partial\|m_check_partial\|NoisyFilterAlg\|adaptive_baseline" sigproc/src/Protodune{HD,VD}.cxx
ProtoduneHD.cxx:796: m_adaptive_baseline = get<bool>(cfg, "adaptive_baseline", m_adaptive_baseline);
ProtoduneHD.cxx:804: cfg["adaptive_baseline"] = false;
ProtoduneHD.cxx:817: bool is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false;
ProtoduneHD.cxx:865: // bool is_noisy = PDHD::NoisyFilterAlg(signal, min_rms, max_rms);
ProtoduneVD.cxx:798: m_adaptive_baseline = get<bool>(cfg, "adaptive_baseline", m_adaptive_baseline);
ProtoduneVD.cxx:806: cfg["adaptive_baseline"] = false;
ProtoduneVD.cxx:819: bool is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false;
ProtoduneVD.cxx:820: // bool is_partial = m_check_partial(spectrum);  // Xin's "IS_RC()"
ProtoduneVD.cxx:871: bool is_noisy = PDVD::NoisyFilterAlg(signal, min_rms, max_rms);
```

---

## 3. `maskmap` (OmnibusNoiseFilter)

| Detector | `maskmap` | Keys actually emitted | Inert keys |
|----------|-----------|----------------------|------------|
| PDHD | `{noisy: "bad", lf_noisy: "bad"}` (`pdhd/nf.jsonnet:42`; alt with sticky/ledge commented out at line 41) | **none** (both dormant — `NoisyFilterAlg` commented out, `lf_noisy` not emitted while `adaptive_baseline=false`) | `noisy`, `lf_noisy` |
| PDVD | `{sticky: "bad", ledge: "bad", noisy: "bad"}` (`protodunevd/nf.jsonnet:47`) | `noisy` only | `sticky`, `ledge` (no PDVD code emits them) |

In both detectors the `maskmap` lists keys that the present C++ never produces — PDHD's `noisy` slot is unused (`NoisyFilterAlg` commented out), PDVD's `sticky`/`ledge` slots are unused (no `StickyCodeMitig` analogue for PDVD).

---

## 4. Coherent noise subtraction — group structure

| Aspect | PDHD | PDVD |
|--------|------|------|
| Group definition style | Formulaic ranges (`std.range(n*2560+u*40, ...)`) | Hard-coded explicit channel lists (`chndb-base.jsonnet:30–391`) |
| Groups per anode | 60 (20 U + 20 V + 20 W FEMBs) | Variable — explicit per-conduit lists |
| Channels per group | 40 (U/V), 48 (W) | 16–48 (varies per conduit) |
| Re-orderings inside group | None (sequential ranges) | Yes — many groups list channels in non-sequential order, reflecting CRP routing |
| `rms_threshold` (group skip) | `0.0` (`pdhd/nf.jsonnet:27`) | `0.0` (`protodunevd/nf.jsonnet:22`) |

**Validation** — PDHD ranges:
```
chndb-base.jsonnet:20: groups: [std.range(n * 2560 + u * 40, n * 2560 + (u+1) * 40 - 1) for u in std.range(0, 19)]
                             + [std.range(n * 2560 + 800 + v * 40, ...) for v in std.range(0, 19)]
                             + [std.range(n * 2560 + 1600 + w * 48, ...) for w in std.range(0, 19)]
```
PDVD explicit lists at lines 30–391 (sample line 32:
`[5537, 5540, 5543, 5546, 5549, 5552, ..., 5534]` — 48 ch in non-monotonic order).

---

## 5. Coherent noise subtraction — what *actually runs*

`SignalProtection` and `Subtract_WScaling` both have an ADC-domain branch
(always active) and a deconvolution-domain branch (gated by
`respec.size() > 0 && respec[0] != (1,0) && res_offset != 0`).

| Plane | PDHD `respec` | PDHD `res_offset` | Decon branch | PDVD `respec` | PDVD `res_offset` | Decon branch |
|-------|---------------|-------------------|---------------|---------------|-------------------|---------------|
| U | `handmade.u_resp` (200-sample 1D) (`chndb-base.jsonnet:79`) | 120 | ✅ active | empty `{}` (no per-plane override) | 0 | ❌ bypassed |
| V | `handmade.v_resp` (`chndb-base.jsonnet:98`) | 124 | ✅ active | empty `{}` | 0 | ❌ bypassed |
| W (collection) | `{}` (inherited default, `chndb-base.jsonnet:64`) | 0 | ❌ bypassed | empty `{}` | 0 | ❌ bypassed |

So in **PDHD**, U and V get full deconvolution-based signal protection +
ROI-replace before subtraction; W gets only the ADC-domain protection
and direct median subtraction.

In **PDVD**, every plane (U, V, W) gets only the ADC-domain protection —
the deconvolution branch is dormant code on **all channels**.

**Validation:**
```
$ grep -n "response:\|response_offset" cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet
   42:        response_offset: 0.0,        # default
   64:        response: {},                # default
   79:        response: { waveform: handmade.u_resp, waveformid: wc.Ulayer },
   80:        response_offset: 120,
   98:        response: { waveform: handmade.v_resp, waveformid: wc.Vlayer },
   99:        response_offset: 124,
```
PDVD now wires U/V FR⊗ER kernels per anode: `n < 4` (bottom CRP) uses
`chndb-resp-bot.jsonnet`; `n >= 4` (top CRP) uses `chndb-resp-top.jsonnet`.
The `response_offset` values are 239/245 (bottom U/V) and 240/243 (top U/V).
The kernel is scaled by `gain_scale = if n >= 4 then 1.0 else params.elec.gain
/ (7.8 * wc.mV / wc.fC)` to propagate runtime FE gain overrides.

---

## 6. Coherent-noise default knob values

Compared at `chndb-base.jsonnet` default block (W values) and per-plane U/V overrides:

| Knob | PDHD default | PDHD U override | PDHD V override | PDHD W override | PDVD default/W | PDVD U/V override |
|------|--------------|-----------------|-----------------|-----------------|----------------|-------------------|
| `nominal_baseline` (ADC) | 2048 | — | — | 400 | 2048 | — |
| `decon_limit` | 0.02 | 0.02 | **0.01** | **0.05** | **0.05** | **0.01** (bot) / 0.02 (top) |
| `decon_limit1` | 0.09 | **0.07** | 0.08 | 0.08 | 0.08 | **0.07** (both) |
| `adc_limit` (ADC) | **60** (raised from 15) | — | — | — | **60** *gs* (bot) / **60** (top) | — |
| `min_adc_limit` (ADC) | **200** (raised from 50) | — | — | — | **200** *gs* (bot) / **200** (top) | — |
| `roi_min_max_ratio` | 0.8 | **3.0** | **1.5** | 0.8 | 0.8 | — |
| `pad_window_front` (ticks) | 10 | 20 | 10 | 10 | 10 | — |
| `pad_window_back` (ticks) | 10 | 10 | 10 | 10 | 10 | — |
| `min_rms_cut` (ADC) | 1.0 *(dead)* | — | — | — | per-plane: top all planes 8.0; bottom W 5.0; bottom U/V linear-in-wirelength [2.6→6.3] *(live)* | — |
| `max_rms_cut` (ADC) | 30.0 *(dead)* | — | — | — | 15.0 all planes *(live)* | — |
| `rcrc` | 1.1 ms *(dead)* | — | — | — | 1.1 ms *(dead)* | — |
| `rc_layers` | 1 *(dead)* | — | — | — | 0 *(dead)* | — |
| `freqmasks` | `[]` default; **U/V notches at bins 169–173, 513–516** *(but dead — `noise(ch)` never called)* | — | — | — | `[]` *(dead — never called)* | — |

PDHD has **per-plane tuning** (different decon thresholds, different
`roi_min_max_ratio`, wider U front pad). PDVD now also applies **per-plane
U/V overrides** for `decon_limit` and `decon_limit1`, in addition to the
**per-anode-group RMS cuts** (see table in `pdvd/docs/nf.md`).
`roi_min_max_ratio` and `pad_window_front/back` remain uniform.

PDVD's `adc_limit` and `min_adc_limit` have been raised to match PDHD's
signal-protection floor (**60**/**200** *gs* for bottom, **60**/**200** for
top CRP), now that U/V deconvolution is active.

**Validation:** see `pdhd/chndb-base.jsonnet:38–118` and
`protodunevd/chndb-base.jsonnet:413–440`.

---

## 7. Bad-channel list

| Detector | Count | Source line |
|----------|-------|-------------|
| PDHD | 36 IDs | `pdhd/chndb-base.jsonnet:26` |
| PDVD | 19 IDs | `protodunevd/chndb-base.jsonnet:399–401` |

Both are static, hand-curated lists. Different magnitudes reflect both
the larger PDHD channel count (4×2560 = 10240) and operational
experience.

---

## 8. Field-response file

| Detector | File | Used by |
|----------|------|---------|
| PDHD | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` (`pdhd/params.jsonnet:153`) | SP **and indirectly NF** (it backs `Diagnostics::Partial` only via the spectrum check; `u_resp`/`v_resp` in NF are *baked-in* arrays in `chndb-resp.jsonnet`, not reread) |
| PDVD | `protodunevd_FR_norminal_260324.json.bz2` (`protodunevd/params.jsonnet:165–166`) | SP and NF (NF U/V `response` kernels derived via `wirecell-sigproc track-response` with `output_window=160 µs`; native FR length ~132.5 µs) |

PDHD bakes the U/V wire-region-averaged 1D response into `chndb-resp.jsonnet`
as `u_resp` (200 samples, line 19) and `v_resp` (line 61). PDVD now has the
analogous arrays split across `chndb-resp-bot.jsonnet` and
`chndb-resp-top.jsonnet` (320 samples each, reflecting the 160 µs
convolution window). The 160 µs window is required because the PDVD FR file
native length (~132.5 µs) is shorter than the bipolar induction tail; without
zero-padding the FFT-based convolution wraps the tail into the early bins.

---

## 9. Step 3 — Shield coupling (PDVD only)

PDHD: not applicable (APA design has no exposed shield plane coupling
to the U strips).

PDVD: `PDVDShieldCouplingSub`, run via `multigroup_chanfilters` with
`top_u_groups` (`chndb-base.jsonnet:393–396`) and per-strip lengths
loaded from `PDVD_strip_length.json.bz2` (`params.jsonnet:158`).
Algorithm adapted from `lardon`. Only attached for anodes with
`ident > 3` (top CRPs).

**Validation:**
- `protodunevd/nf.jsonnet:25–35` (filter definition), 60–65 (conditional attachment).
- `params.jsonnet:158`: `strip_length: "PDVD_strip_length.json.bz2"`.
- No equivalent class in `pdhd/nf.jsonnet`.

---

## 10. OmnibusNoiseFilter wiring API

| Field | PDHD | PDVD |
|-------|------|------|
| `channel_filters` | `[PDHDOneChannelNoise]` | `[PDVDOneChannelNoise]` |
| `grouped_filters` | `[PDHDCoherentNoiseSub]` | `[]` (empty) |
| `multigroup_chanfilters` | not used | `[{groups, [PDVDCoherentNoiseSub]}, +(top only) {top_u_groups, [PDVDShieldCouplingSub]}]` |

PDHD uses the standard `grouped_filters` slot (one filter, one group
set). PDVD uses the more flexible `multigroup_chanfilters` slot to
attach two filter+group pairs (coherent + shield) — needed because the
two stages operate on different channel partitions.

---

## 11. Quick-reference summary

| Question | PDHD | PDVD |
|----------|------|------|
| Sticky / ledge tagging? | No | No |
| Adaptive baseline (partial channels)? | No (`adaptive_baseline=false` in `nf.jsonnet` — PDHD cold electronics is DC-coupled, so IS_RC gate has no physical meaning; see `Microboone.cxx:963-1047`) | No (`adaptive_baseline=false` in `nf.jsonnet` — intentional; PDVD is DC-coupled so IS_RC gate has no physical meaning) |
| `lf_noisy` tag emitted? | No (not emitted while `adaptive_baseline=false`) | No |
| `noisy` tag (RMS cut) emitted? | No (block commented) | Yes |
| RMS-cut wire-length dependence? | n/a (cuts are dead) | Yes for bottom U/V — `linear_in_wirelength` mode in `OmniChannelNoiseDB` (`OmniChannelNoiseDB.cxx:cache_wire_lengths`) |
| RC-RC correction applied? | No (commented out) | No (commented out) |
| Top vs bottom electronics branch in NF? | n/a | Only for *resampler* (n<4) and *shield coupling* (ident>3); not in per-channel or coherent algos |
| `reconfig` consumed by per-channel filter? | No | No |
| `freqmasks` consumed by per-channel filter? | No | No |
| 1D field response source for coherent sub | Hard-coded `u_resp`/`v_resp` arrays (active U/V) | FR⊗ER kernels from `chndb-resp-{bot,top}.jsonnet` (active U/V; W still empty `{}`) |
| `adc_limit` role | ADC-floor of signal-protection threshold (used mostly on W) | ADC-floor for W; decon branch now active on U/V |
| `decon_limit` / `decon_limit1` active? | Yes on U/V; W only via `decon_limit1` if `respec` were set (it isn't on W) | Active on U/V with per-plane thresholds (U/V: 0.01/0.07 bot, 0.02/0.07 top; W: 0.05/0.08); W `respec` still empty |
| Shield coupling? | No | Yes — top anodes, U-plane only |
| Resampler? | No | Yes — bottom anodes only |

---

## 12. Implications

- **Output mask semantics differ.** Downstream code that consumes the
  `bad` channel mask will see different populations: in PDHD, `bad`
  comes only from the hand-curated `bad` list (the `lf_noisy` path is
  dormant now that `adaptive_baseline=false`; any bad-channel info for
  partial channels must be supplied separately); in PDVD it comes from
  the `noisy` RMS-cut flag plus the hand-curated `bad` list.
- **Different sensitivity to wire-region-average response.** PDHD's
  coherent sub on U/V is response-aware: it deconvolves before
  protection and ROI replacement. PDVD now also has per-plane `decon_limit`
  and `decon_limit1` tuned for each CRP type; `roi_min_max_ratio` tuning
  is a deferred follow-up step.
- **Shield coupling is a PDVD-specific stage.** Any tool that processes
  both detectors must be aware that the third NF pass exists only on
  PDVD top anodes.
- **Resampling exists only on PDVD bottom anodes.** PDHD does not need
  the 500 ns alignment step; SP field-response files are uniform.
- **Tuning surfaces partially portable.** PDHD's `roi_min_max_ratio`
  overrides (3.0/1.5 U/V) have no PDVD equivalents yet. PDVD's per-plane
  U/V `decon_limit`/`decon_limit1` splits now mirror PDHD's structure;
  `roi_min_max_ratio` per-plane tuning is deferred.

---

## 13. Source cross-reference

| File | PDHD | PDVD |
|------|------|------|
| Top-level NF+SP driver | `pdhd/wct-nf-sp.jsonnet` | `pdvd/wct-nf-sp.jsonnet` |
| NF pnode factory | `cfg/pgrapher/experiment/pdhd/nf.jsonnet` | `cfg/pgrapher/experiment/protodunevd/nf.jsonnet` |
| Channel DB | `cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet` | `cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet` |
| FR⊗ER kernel (bottom CRP) | `cfg/pgrapher/experiment/pdhd/chndb-resp.jsonnet` (live) | `cfg/pgrapher/experiment/protodunevd/chndb-resp-bot.jsonnet` (live) |
| FR⊗ER kernel (top CRP) | — | `cfg/pgrapher/experiment/protodunevd/chndb-resp-top.jsonnet` (live) |
| Detector params | `cfg/pgrapher/experiment/pdhd/params.jsonnet` | `cfg/pgrapher/experiment/protodunevd/params.jsonnet` |
| C++ NF impl | `sigproc/src/ProtoduneHD.cxx` | `sigproc/src/ProtoduneVD.cxx` |
| Field-response file | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` | `protodunevd_FR_norminal_260324.json.bz2` |
| OmnibusNoiseFilter driver | `sigproc/src/OmnibusNoiseFilter.cxx` (shared) | same |
| Channel-noise DB driver | `sigproc/src/OmniChannelNoiseDB.cxx` (shared) | same |
