# PDHD light data: flash-statistics comparison across runs (+x vs −x)

A cross-run comparison of the **optical-flash content** of the PDHD light-data
files we currently have, separating the **+x** wall from the **−x** wall. It
answers the practical questions: how many events per run, how many flashes per
event per side, how many photon detectors (PDs) light up per flash, and what the
total-PE and per-PD PE distributions look like.

> Companion docs: `pdhd-light-raw-data.md` (raw waveforms, SPE kernels, OpHit
> formation — see its **§7** for the −x PD coverage and the full-stream readout),
> `pdhd-fullstream-light-reco.md` (the all-PD WCT chain), `which-pd-side-lights.md`,
> `photon-detector-chain.md`. Plots live in `pdhd/pics/` (git-ignored); regenerate
> the toolkit plots (§4) with `pdhd/pd_plot/make_flash_stats_wct.py` and the LArSoft
> reference plots (§5) with `/home/xqian/tmp/flashstats/make_flash_stats.py`.

---

## 1. Data sources

This doc now leads with the **toolkit (WCT-native) flashes** — our own reco — in
**§4**, and keeps the **LArSoft flash trees** as the uniform cross-run reference in
**§5**.

**Toolkit (§4, primary).** Our reconstructed opflash products, by run-appropriate
chain:
- **27980** — the **all-PD** chain (`pdhd-fullstream-light-reco.md` §9: self-trigger
  snippets 0–119 + full-stream 120–159 merged into one `OpFlashFinder`), all 31
  events → −x flashes over the **full 80–159 wall**.
- **29107** — the **all-PD** chain too, all 30 events → the full 80–159 −x wall,
  exactly like 27980. The file was **re-extracted with a full `rawdump` (all 160
  channels)**, so the −x (and full +x) self-trigger snippets and the −x full-stream
  waveforms our chain needs are all present now. (The earlier 89 MB extract carried
  only a sparse `decoana` of ch 0–39 and **no `rawdump`**, so WCT reco then reached
  only ch 0–39 and the all-PD chain aborted with `not found: 'rawdump'`; that
  limitation is gone.)
- **27305** — +x self-trigger (the −x wall is dark this run; its raw file has the
  full-stream channels but no −x light).

**LArSoft (§5, reference).** `flashopdet/flash_opdet` (one row per
`(event, flash_id, opdet)`). We keep it as the **uniform** single-source cross-run
picture. In the LArSoft trees "−x" means the snippet PDs 80–119 only (the
full-stream 120–159 are absent), so a −x flash there caps at one half-wall; the full
−x wall appears only in the toolkit §4.

**Side mapping** (verified against `flashopdet/opdet_geo`, x in mm):

| opdet range | wall | x position | in flash trees? |
|---|---|---|---|
| 0–79 | **+x** | ≈ +356 mm | yes (all runs) |
| 80–119 | **−x** (snippet PDs) | ≈ −356 mm | yes (27980, 29107 only) |
| 120–159 | **−x** (full-stream PDs) | ≈ −356 mm | **not in the LArSoft trees** (reconstructed WCT-natively — see `pdhd-fullstream-light-reco.md` §8) |

So throughout this doc the **"−x" side means channels 80–119**. The full-stream
−x PDs 120–159 are absent **from these LArSoft trees** by construction; they are
now reconstructed WCT-natively (`pdhd-fullstream-light-reco.md`), but that is a
different source and is not mixed into the LArSoft cross-run tables below.

---

## 2. Runs available

| run | light ROOT file | events | −x present |
|---|---|---|---|
| **27305** | `run027305/np04hd_raw_run027305_0001_…_final.root` | 24 | **no** (+x only; −x dark this run) |
| **27980** | `run027980/np04hd_raw_run027980_0000_…_final.root` | 31 | yes (full 80–159 wall) |
| **29107** | `run029107/np04hd_raw_run029107_0004_…_final.root` (re-extracted, full `rawdump`) | 30 | yes (full 80–159 wall) |
| **28084** | `run028084/np04hd_raw_run028084_0300_…_final.root` (re-extracted, full `rawdump`) | 31 | yes (full 80–159 wall) |

**CORRECTION 2026-09-07 (doc pdhd/09):** the exclusion below is stale. The file
was re-extracted — it is now **1,495,632,331 B (1.5 GB), mtime 2026-06-16**, and
uproot reads it end to end: `rawdump/raw_waveform` 75,145 entries,
`decodump/deco_waveform` 73,899, `trigoff/trigger_offset`, each covering **all 31
DAQ events 74408–74648**. All 31 events have since been reconstructed through the
all-PD light chain and Q/L-matched (doc pdhd/09 sec 4). The row above is updated;
the paragraph below is kept for provenance.

> ~~**Run 28084 is excluded:** its light ROOT is truncated/corrupt (723 MB, uproot
> read error mid-file). The 31 `evt_*` subdirectories under `run028084/` hold
> **charge** data (orig/SP wire frames per anode), not optical data, so the run
> contributes no flash statistics. If the file is re-extracted intact it slots
> straight into the comparison.~~

The −x wall is **run-dependent**: it is dark in 27305 and lit (snippet PDs) in
27980 and 29107. This matches `which-pd-side-lights.md`.

---

## 3. Method

For each run we read `flashopdet/flash_opdet`, group rows into flashes by
`(event, flash_id)`, and for every flash compute its PD count, total PE, and the
PE on each wall. **Side assignment:** a flash is `+x` if all its PE sits on
ch 0–79, `−x` if all on ch 80–119, and `mixed` if both walls have PE.

Flashes are mostly **wall-pure**: mixed flashes are only **11.1 %** in 27980
(1067 / 9593) and **12.6 %** in 29107 (1641 / 13027). We keep `mixed` as its own
category rather than forcing a side, and report it alongside +x and −x.

---

## 4. Comparisons — toolkit (WCT-native) flashes

These are **our own** reconstructed flashes (see §1): **27980** and **29107** both
via the all-PD chain (full −x wall, all events), **27305** +x self-trigger (−x dark
this run). Regenerate with `pd_plot/make_flash_stats_wct.py`. The LArSoft cross-run
tables (the uniform snippet-only source) are kept below in §5 as a cross-check.

> **No-cut population.** §4 reports the **full** flash population with the
> `OpFlashFinder` multiplicity/PE quality cut **disabled** (`min_fired_pds = 0`,
> `min_total_pe = 0`), so the per-flash nPD/PE spectra are visible end-to-end. The
> production config restores the **5-PD / 20-PE** cut — that cut is for Q/L matching
> (it would erase most of the nPD≈1–2 population), not for characterization.

### 4.1 Summary table (toolkit)

| run | events | flashes | flashes/evt | +x | −x | mixed | tot-PE med | tot-PE p90 | tot-PE max | nPD med | nPD p90 | nPD max | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 27305 | 23 | 707 | **30.7** | 707 | 0 | 0 | 178 | 4071 | 30357 | 3 | 10 | 18 | +x only (−x dark) |
| 27980 | 31 | 24276 | **783.1** | 6263 | 18013 | 0 | 6 | 130 | 27605 | 2 | 12 | **58** | all-PD (full −x wall) |
| 29107 | 30 | 31333 | **1044.4** | 9623 | 21710 | 0 | 8 | 150 | 1327058 | 2 | 28 | **80** | all-PD (full −x wall) |

*(tot-PE = total PE per flash; nPD = photon detectors per flash; p90 = 90th
percentile. 27305 shows 23 events here vs 24 in the LArSoft §5 — the toolkit script
counts one opflash per clean numeric work dir and drops a duplicate `…jjo` variant
dir; not a missing event.)* 27980 and 29107 both have a high flashes/event because
the all-PD count is dominated by the **full-stream** −x PDs, which scan the
continuous 5.5 ms stream and legitimately catch ~25× the live-time of the
self-trigger snippets (see `pdhd-fullstream-light-reco.md` §8). 29107's even higher
rate (1044/evt vs 27980's 783) and its PE_max of 1.3 M come from event **1015**, a
bright wall-spanning outlier (nPD up to 80; see `pdhd-pd-activity-per-event.md` §6).
27305 has no −x light.

### 4.2 Flashes per event by wall (toolkit)

![flashes per event (WCT)](../pics/light_runcmp_wct_flashes_per_event.png)

In 27980 and 29107 the −x wall (now the **full** 80–159) carries the bulk of the
flashes — expected, since the full-stream half reads continuously. 27305 is
+x-only (−x dark this run).

### 4.3 Photon detectors per flash (toolkit) — the full −x wall

![PDs per flash (WCT)](../pics/light_runcmp_wct_pds_per_flash.png)

This panel is the toolkit answer to "why did −x top out at half of +x". With the
all-PD chain, run 27980's −x flashes now span the **whole 80-PD wall** and reach
**~58 PDs** — with a high-PD bump near 50 (wall-spanning cosmics) that the
half-wall snippet view could never show — comparable to (here above) the +x
ceiling of ~40. 29107 behaves the same — its all-PD −x flashes span the full wall,
reaching nPD up to **80** in the bright event 1015. 27305 +x reaches ~18 (dim +x
light this run).

**Background — why −x looked like ~half of +x.** Both walls physically have **80
PDs** (8 z-rows × 10); on −x they are split by **readout** into two half-walls
tiling **disjoint z-halves**: snippet 80–119 (z ≈ 267–427) and full-stream
120–159 (z ≈ 35–195). The LArSoft `flash_opdet` trees and the per-stream WCT reco
both see only one half per −x flash (~20 PDs), while +x is one 80-PD wall. The
all-PD single processing (`pdhd-fullstream-light-reco.md` §9: snippet +
full-stream OpHits merged into one `OpFlashFinder`) restores the full −x wall;
+x is byte-identical to the per-stream reco.

### 4.4 Total PE per flash (toolkit)

![total PE per flash (WCT)](../pics/light_runcmp_wct_total_pe.png)

27305 keeps its bright, bimodal +x population (median ~178 PE). 27980 and 29107 are
both dominated by many low-PE flashes (median ~6–8) — the full-stream −x adds a
large population of small flashes; the bright tail extends to ~28k PE in 27980 and
to ~1.3 M PE in 29107 (event 1015).

### 4.5 Per-PD PE (toolkit)

![per-PD PE (WCT)](../pics/light_runcmp_wct_pe_per_pd.png)

Per-PD PE (median / p90 / max):

| run | +x | −x |
|---|---|---|
| 27305 | 138 / 488 / 30357 | — (dark) |
| 27980 | 5 / 87 / 14314 | 6 / 97 / 12166 |
| 29107 | 1 / 59 / 25696 | 4 / 83 / 52850 |

In both 27980 and 29107 the +x and full −x walls sit at SPE-scale medians (27980
5 vs 6, 29107 1 vs 4) and have comparable p90/max — the full −x wall behaves like
+x, no anomaly. 27305's +x spectrum sits much higher (median ~138), consistent with
its bright bimodal flash population.

## 5. LArSoft cross-run reference (uniform source)

Kept as the **uniform** single-source cross-run picture. "−x" here = snippet PDs
80–119 only (the full-stream 120–159 are absent from these trees, so a −x flash
caps at one half-wall — the full wall is the toolkit §4). Source:
`flashopdet/flash_opdet`. Regenerate with
`/home/xqian/tmp/flashstats/make_flash_stats.py`.

### 5.1 LArSoft summary table

| run | events | flashes | flashes/evt | +x | −x | mixed | tot-PE med | tot-PE p90 | tot-PE max | nPD med | nPD p90 | nPD max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 27305 | 24 | 683 | **28.5** | 683 | 0 | 0 | 399 | 4177 | 72299 | 3 | 9 | 15 |
| 27980 | 31 | 9593 | **309.5** | 5446 | 3080 | 1067 | 17 | 573 | 21755 | 1 | 14 | 52 |
| 29107 | 30 | 13027 | **434.2** | 7211 | 4175 | 1641 | 34 | 855 | 415688 | 1 | 26 | 113 |

![flashes per event](../pics/light_runcmp_flashes_per_event.png)
![overview](../pics/light_runcmp_summary.png)
![PDs per flash](../pics/light_runcmp_pds_per_flash.png)
![total PE per flash](../pics/light_runcmp_total_pe.png)
![per-PD PE](../pics/light_runcmp_pe_per_pd.png)

In the LArSoft view a −x flash tops out at ~20 PDs (half the +x ceiling) because
only the snippet half (80–119) is in these trees — see §4.3 for the full-wall
toolkit result. 29107's much larger mixed/PE tail (max 113 PDs, 415k PE) is a
run-condition difference (bigger events / trigger config), not a reco effect.

The per-PD PE spectrum is **bimodal** — a low ~1-PE (SPE-scale) bump plus a
broader high-PE population — and the **+x and −x walls track each other closely**
(medians within ~1 PE). The +x wall sits marginally higher in normalization. The
27305 per-PD spectrum is shifted up (median ~150 PE) consistent with its
higher-PE flash population.

---

## 6. Caveats

- **§4 is the no-cut population** (OpFlashFinder `min_fired_pds`/`min_total_pe` = 0);
  the production config restores the 5-PD / 20-PE cut, which removes most of the
  nPD≈1–2 flashes — so §4 rates are *not* the rates a Q/L-matching run sees.
- **Methodology across runs in §4**: 27980 and 29107 are both all-PD (full −x wall,
  from `rawdump`) and directly comparable; 27305 is +x self-trigger (−x dark this
  run). The LArSoft §5 is the single-source cross-run cross-check.
- The **~10× spread in flashes/event** and **~20× spread in PE scale** between
  27305 and 27980/29107 most likely reflect different **trigger / readout
  configuration** (and the presence of −x instrumentation), not a physics
  difference between the runs.
- 27980's high toolkit flashes/event (~783) is dominated by the **full-stream** −x
  PDs scanning the continuous 5.5 ms stream (~25× the snippet live-time); it is not
  comparable to the snippet-only LArSoft 309/evt.
- In the **LArSoft §5** tables "−x" is the snippet PDs 80–119 only, so the −x wall
  is under-counted there relative to its full instrumentation; the full −x wall
  appears only in the toolkit all-PD §4.

---

## Appendix — provenance

| item | source |
|---|---|
| toolkit flashes (§4) | `work/0<run>_allpd<evt>_nocut/opflash_pdhd-allpd-wct.tar.gz` (no-cut all-PD); 27305 from `work/027305_<evt>/opflash_pdhd-wct.tar.gz` |
| toolkit analysis + plots (§4) | `pdhd/pd_plot/make_flash_stats_wct.py` |
| LArSoft flash records (§5) | `flashopdet/flash_opdet` (event, flash_id, opdet, pe, flash_total_pe) |
| side / geometry | `flashopdet/opdet_geo` (x sign: 0–79 = +x, 80–159 = −x) |
| LArSoft analysis + plots (§5) | `/home/xqian/tmp/flashstats/make_flash_stats.py` |
| run 29107 re-extraction | full `rawdump` (160 ch): `/nfs/data/1/jjo/data/PDHD/np04hd_raw_run029107_0004_…_final.root` (1.8 GB) |
| run 28084 status | light ROOT truncated (723 MB, uproot read error); `evt_*` dirs are charge frames |
