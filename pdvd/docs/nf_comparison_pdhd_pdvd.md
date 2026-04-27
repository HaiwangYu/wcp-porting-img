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

| Step | PDHD (`ProtoduneHD.cxx:806–873`) | PDVD (`ProtoduneVD.cxx:807–878`) |
|------|----------------------------------|-----------------------------------|
| FFT + DC bin kill | ✅ live (827) | ✅ live (827) |
| 6σ-clipped median baseline | ✅ live | ✅ live |
| RC-RC undershoot correction | **commented out** (`ProtoduneHD.cxx:817–820`) | **commented out** (`ProtoduneVD.cxx:820–823`) |
| `m_check_partial(spectrum)` (RC heuristic) | ✅ **live**: `bool is_partial = m_check_partial(spectrum)` (`ProtoduneHD.cxx:815`) | ⚙ **config-gated**: `bool is_partial = m_adaptive_baseline ? m_check_partial(spectrum) : false` (`ProtoduneVD.cxx:819`); `adaptive_baseline` defaults to `false` and is left at default in `protodunevd/nf.jsonnet` — PDVD hardware is DC-coupled so the IS_RC branch has no physical meaning |
| Adaptive baseline (`SignalFilter` + `RawAdaptiveBaselineAlg` + `RemoveFilterFlags`) | Runs on partial channels (PDHD lines 853–856) | **Never runs** — disabled by config (`adaptive_baseline=false`; PDVD is DC-coupled, see `Microboone.cxx:963-1047` for the IS_RC/adaptive-baseline pairing) |
| `lf_noisy` tag on induction planes | Emitted when `is_partial && iplane != 2` (PDHD line 851) | **Never emitted** — push at `ProtoduneVD.cxx:857` not taken while `adaptive_baseline=false` |
| `NoisyFilterAlg` (`min_rms_cut`/`max_rms_cut` test → `noisy` tag) | **Commented out** (`ProtoduneHD.cxx:859–870`) — `min_rms_cut: 1.0` / `max_rms_cut: 30.0` are dead | ✅ **Live** (`ProtoduneVD.cxx:862–875`) — `min_rms_cut: 1.0` / `max_rms_cut: 60.0` actively flag noisy channels |
| `SignalFilter` + `RemoveFilterFlags` around the noisy test | n/a (block commented) | ✅ live (PDVD lines 867, 869) |

**Net effect — what tags each per-channel filter actually produces:**

| Tag | PDHD | PDVD |
|-----|------|------|
| `lf_noisy` | ✅ produced on induction-plane partial channels | ❌ never produced |
| `noisy` | ❌ never produced | ✅ produced when channel RMS is outside `[1.0, 60.0]` ADC |
| `sticky` / `ledge` | ❌ neither implemented | ❌ neither implemented |

So although PDHD and PDVD share an almost-identical per-channel apply body, **the live tagging is mutually exclusive**: PDHD tags `lf_noisy` only, PDVD tags `noisy` only.

**Validation:**
```
$ grep -n "is_partial\|m_check_partial\|NoisyFilterAlg\|adaptive_baseline" sigproc/src/Protodune{HD,VD}.cxx
ProtoduneHD.cxx:815: bool is_partial = m_check_partial(spectrum);  // Xin's "IS_RC()"
ProtoduneHD.cxx:863: // bool is_noisy = PDHD::NoisyFilterAlg(signal, min_rms, max_rms);
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
| PDHD | `{noisy: "bad", lf_noisy: "bad"}` (`pdhd/nf.jsonnet:42`; alt with sticky/ledge commented out at line 41) | `lf_noisy` only | `noisy` (block dead) |
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
```
$ grep -n "response:\|response_offset" cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet
   417:        response_offset: 0.0,
   438:        response: {},
   # no per-plane override anywhere in the file
```

The PDVD file `chndb-resp.jsonnet:19,61` does define `u_resp`/`v_resp`
arrays, but no jsonnet imports them (verified by grep). They are dead
code, in contrast to PDHD where the same-named arrays are live.

---

## 6. Coherent-noise default knob values

Compared at `chndb-base.jsonnet` default block (W and global defaults):

| Knob | PDHD default | PDHD U override | PDHD V override | PDHD W override | PDVD (single block) |
|------|--------------|-----------------|-----------------|-----------------|---------------------|
| `nominal_baseline` (ADC) | 2048 | — | — | 400 | 2048 |
| `decon_limit` | 0.02 | 0.02 | 0.01 | 0.05 | 0.02 |
| `decon_limit1` | 0.09 | 0.07 | 0.08 | 0.08 | 0.09 |
| `adc_limit` (ADC) | **60** (raised from 15) | — | — | — | **15** |
| `min_adc_limit` (ADC) | **200** (raised from 50) | — | — | — | **50** (C++ default) |
| `roi_min_max_ratio` | 0.8 | **3.0** | **1.5** | 0.8 | 0.8 |
| `pad_window_front` (ticks) | 10 | 20 | 10 | 10 | 20 |
| `pad_window_back` (ticks) | 10 | 10 | 10 | 10 | 20 |
| `min_rms_cut` (ADC) | 1.0 *(dead)* | — | — | — | 1.0 *(live)* |
| `max_rms_cut` (ADC) | 30.0 *(dead)* | — | — | — | 60.0 *(live)* |
| `rcrc` | 1.1 ms *(dead)* | — | — | — | 1.1 ms *(dead)* |
| `rc_layers` | 1 *(dead)* | — | — | — | 0 *(dead)* |
| `freqmasks` | `[]` default; **U/V notches at bins 169–173, 513–516** *(but dead — `noise(ch)` never called)* | — | — | — | `[]` *(dead — never called)* |

PDHD has **per-plane tuning** (different decon thresholds, different
`roi_min_max_ratio`, wider U front pad). PDVD applies a **single global
default to all 3072 channels of all 8 anodes** — no per-plane override.

PDHD's higher `adc_limit`/`min_adc_limit` (60/200 vs 15/50) reflect the
*raised* signal-protection floor needed because PDHD's U/V deconvolution
branch is active and the ADC-floor only matters for W. In PDVD, since
the deconvolution branch is dormant for all planes, the ADC-domain
threshold is the *only* signal-protection threshold and it stays at the
lower default.

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
| PDVD | `protodunevd_FR_norminal_260324.json.bz2` (`protodunevd/params.jsonnet:165–166`) | SP only — NF never consumes it (since `response: {}` everywhere) |

PDHD also bakes the U/V wire-region-averaged 1D response into
`chndb-resp.jsonnet` as `u_resp` (200 samples, line 19) and `v_resp`
(line 61). The header comment at `chndb-resp.jsonnet:1–17` documents
that these were derived from `fravg.planes[2]` of `np04hd-garfield-...`
in `OmnibusSigproc.cxx`; they must be re-derived if the field-response
file is updated. PDVD has the analogous arrays in
`protodunevd/chndb-resp.jsonnet:19,61` but they are unused.

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
| Adaptive baseline (partial channels)? | Yes (live `is_partial`) | No (`adaptive_baseline=false` in `nf.jsonnet` — intentional; PDVD is DC-coupled so IS_RC gate has no physical meaning) |
| `lf_noisy` tag emitted? | Yes (induction partial channels) | No |
| `noisy` tag (RMS cut) emitted? | No (block commented) | Yes |
| RMS-cut wire-length dependence? | n/a (cuts are dead) | No (uniform `[1, 60]` ADC) |
| RC-RC correction applied? | No (commented out) | No (commented out) |
| Top vs bottom electronics branch in NF? | n/a | Only for *resampler* (n<4) and *shield coupling* (ident>3); not in per-channel or coherent algos |
| `reconfig` consumed by per-channel filter? | No | No |
| `freqmasks` consumed by per-channel filter? | No | No |
| 1D field response source for coherent sub | Hard-coded `u_resp`/`v_resp` arrays (active U/V) | Empty `{}` everywhere — decon branch dormant |
| `adc_limit` role | ADC-floor of signal-protection threshold (used mostly on W) | ADC-floor of signal-protection threshold (sole active path) |
| `decon_limit` / `decon_limit1` active? | Yes on U/V; W only via `decon_limit1` if `respec` were set (it isn't on W) | Configured but unused — `respec` empty everywhere |
| Shield coupling? | No | Yes — top anodes, U-plane only |
| Resampler? | No | Yes — bottom anodes only |

---

## 12. Implications

- **Output mask semantics differ.** Downstream code that consumes the
  `bad` channel mask will see different populations: in PDHD, `bad`
  comes from `lf_noisy` (induction RC-undershoot heuristic) plus the
  hand-curated `bad` list; in PDVD it comes from the `noisy` RMS-cut
  flag plus the hand-curated `bad` list.
- **Different sensitivity to wire-region-average response.** PDHD's
  coherent sub on U/V is response-aware: it deconvolves before
  protection and ROI replacement. PDVD's is response-blind: only ADC
  amplitudes drive signal protection. Consequently, PDVD's `adc_limit`
  is the dominant tuning lever, while PDHD's per-plane decon thresholds
  are.
- **Shield coupling is a PDVD-specific stage.** Any tool that processes
  both detectors must be aware that the third NF pass exists only on
  PDVD top anodes.
- **Resampling exists only on PDVD bottom anodes.** PDHD does not need
  the 500 ns alignment step; SP field-response files are uniform.
- **Tuning surfaces are not portable.** PDHD's per-plane overrides
  (`u_resp`, `v_resp`, `response_offset 120/124`, `roi_min_max_ratio
  3.0/1.5`) have no PDVD equivalents in current production. Adding
  PDVD per-plane response would require populating
  `protodunevd/chndb-base.jsonnet` and re-deriving response waveforms.

---

## 13. Source cross-reference

| File | PDHD | PDVD |
|------|------|------|
| Top-level NF+SP driver | `pdhd/wct-nf-sp.jsonnet` | `pdvd/wct-nf-sp.jsonnet` |
| NF pnode factory | `cfg/pgrapher/experiment/pdhd/nf.jsonnet` | `cfg/pgrapher/experiment/protodunevd/nf.jsonnet` |
| Channel DB | `cfg/pgrapher/experiment/pdhd/chndb-base.jsonnet` | `cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet` |
| Hard-coded 1D response | `cfg/pgrapher/experiment/pdhd/chndb-resp.jsonnet` (live) | `cfg/pgrapher/experiment/protodunevd/chndb-resp.jsonnet` (unused) |
| Detector params | `cfg/pgrapher/experiment/pdhd/params.jsonnet` | `cfg/pgrapher/experiment/protodunevd/params.jsonnet` |
| C++ NF impl | `sigproc/src/ProtoduneHD.cxx` | `sigproc/src/ProtoduneVD.cxx` |
| Field-response file | `np04hd-garfield-6paths-mcmc-bestfit.json.bz2` | `protodunevd_FR_norminal_260324.json.bz2` |
| OmnibusNoiseFilter driver | `sigproc/src/OmnibusNoiseFilter.cxx` (shared) | same |
| Channel-noise DB driver | `sigproc/src/OmniChannelNoiseDB.cxx` (shared) | same |
