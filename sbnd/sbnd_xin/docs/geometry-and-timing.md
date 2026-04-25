# Geometry, Timing, and Detector Constants (`sbnd_xin/`)

The local jsonnets in `sbnd_xin/` are thin pipeline wrappers. Most detector
knowledge is imported from the shared `cfg/pgrapher/experiment/sbnd/` tree.
This document lists every physics constant used by the standalone pipeline:
its canonical source, any local override, and the reason for the override.

> For how the constants affect the Bee display see the **time offset** and
> **BEE undrift convention** sections below.

---

## SBND detector geometry summary

| Property | Value |
|---|---|
| APAs | 2 (APA0 and APA1) |
| Faces per APA | 2 |
| APA0 anode plane X | −201.45 cm |
| APA1 anode plane X | +201.45 cm |
| Cathode X (APA0 side) | −0.45 cm |
| Cathode X (APA1 side) | +0.45 cm |
| Max drift distance | ≈ 201 cm |
| Channels per APA (real) | 5638 |
| Frame length | 3400 ticks |
| Tick period | 0.5 µs |

---

## Anode-plane X positions

**Source of truth:** `cfg/pgrapher/experiment/sbnd/params.jsonnet:20-25`

```jsonnet
uplane_left  =  201.45*wc.cm    // APA1 anode (positive-x drift volume)
uplane_right = -201.45*wc.cm    // APA0 anode (negative-x drift volume)
cpa_left     =   0.45*wc.cm     // cathode, APA1 side
cpa_right    =  -0.45*wc.cm     // cathode, APA0 side
```

Verification: `wirecell-util wires-info <wires-sbnd.json.bz2>` reports
`anode:0 face:0` at X ≈ [−2020.5, −2014.5] mm and `anode:1 face:1` at
X ≈ [+2014.5, +2020.5] mm.

**Local uses:**

| File | Line | Value | Context |
|---|---|---|---|
| `clus.jsonnet` | 22 | `FV_xmax: 201.45*wc.cm` | overall fiducial volume |
| `clus.jsonnet` | 49 | `FV_xmax: 201.45*wc.cm` | `a1f0pA` drift-volume block |
| `wct-img-2-bee.py` | 19, 21 | `--x0 "-201.45*cm"` / `"201.45*cm"` | bee-blobs undrift origin |

---

## Drift speed

**Source of truth (simulation):** `cfg/pgrapher/experiment/sbnd/simparams.jsonnet:16`

```jsonnet
drift_speed : 1.563*wc.mm/wc.us
```

**Local copies / overrides:**

| File | Line | Value | Context |
|---|---|---|---|
| `clus.jsonnet` | 13 | `1.56 mm/us` | `BlobSampler` drift speed; `time_offset` scaling |
| `wct-clustering.jsonnet` | 32 | TLA default `1.565` | overlaid onto `simparams.lar.drift_speed` |
| `run_clus_evt.sh` | 125 | `--tla-code "driftSpeed=1.565"` | explicit TLA forwarded to above |
| `wct-img-2-bee.py` | 19, 21 | `±1.563 mm/us` | bee-blobs `--speed` arg |

The three values (1.56, 1.563, 1.565) differ by < 0.3 % and are historical
hand-me-downs from different calibration passes. Over 201 cm of drift the
largest discrepancy (1.56 vs 1.565) produces ≈ 1 mm of position error.
Not a correctness issue today; worth aligning in a future cleanup.

---

## Time offset

**Local definition:** `clus.jsonnet:12`

```jsonnet
local time_offset = -200 * wc.us;
```

Used by:
- `clus.jsonnet:40` (`dvm.a0f0pA.time_offset`) — passed into `BlobSampler`
- `clus.jsonnet:82` (`bs_live_face data.time_offset`) — applied when sampling blob points into (x,y,z) space

### BEE undrift convention — why `wct-img-2-bee.py` uses `--t0 "200*us"` (positive)

There is a **sign-convention mismatch** between the C++ `BlobSampler` and the
Python `wirecell-img bee-blobs` converter.

`BlobSampler` (C++, `pgrapher/common/clus.jsonnet:82`) **adds** `time_offset`:

```
x = anode_x + drift_sign * drift_speed * (t + time_offset)
```

`wirecell-img bee-blobs` (`wirecell/img/converter.py:undrift_blobs`) **subtracts** `--t0`:

```
x = x0 - speed * (t - t0)
```

To make the two formulas consistent, `--t0` must be the **negative** of
`time_offset`. Since `time_offset = -200 us`, the correct argument is
`--t0 "+200*us"`.

Passing `--t0 "-200*us"` (i.e. the same sign as `time_offset`) shifts every
blob by 2 × 200 us × 1.563 mm/us ≈ 63 cm — that was the bug fixed on this
branch.

**APA-specific drift direction** (`clus.jsonnet:27`):

```jsonnet
local drift_sign = if anode.data.ident%2 == 0 then 1 else -1;
```

- APA0 (`drift_sign = +1`): drift is from anode (−201.45 cm) toward cathode (−0.45 cm), i.e. toward **+x**. `--speed` must be negative so that `x0 - speed*dt` increases toward the cathode.
- APA1 (`drift_sign = −1`): drift is from anode (+201.45 cm) toward cathode (+0.45 cm), i.e. toward **−x**. `--speed` must be positive.

Final `wct-img-2-bee.py` arguments (correct values on this branch):

| APA | `--x0` | `--speed` | `--t0` |
|---|---|---|---|
| 0 | `-201.45*cm` | `-1.563*mm/us` | `200*us` |
| 1 | `+201.45*cm` | `+1.563*mm/us` | `200*us` |

---

## Per-APA channel count

**Real value:** 5638 channels per APA (confirmed by wire geometry file).

**Upstream bug:** `cfg/pgrapher/experiment/sbnd/img.jsonnet` uses 5632
(off by 6 W-plane wires per APA). This is a production-affecting bug tracked
separately — the shared config is not modified here.

**Local workaround:**

| File | Line | Fix |
|---|---|---|
| `wct-img-all.jsonnet` | 48–49 | `ChannelSelector` with `std.range(5638*N, 5638*(N+1)-1)` inserted before `img.per_anode` |
| `wct-sp-to-magnify.jsonnet` | 118 | Same `ChannelSelector` before `MagnifySink` |

Without the corrective selector, APA1's imaging branch would receive 6 channels
that belong to APA0, causing `ChargeErrorFrameEstimator` to crash.

---

## Frame length and tick

| Constant | Value | Source |
|---|---|---|
| `nticks` | 3400 | `wct-sp-to-magnify.jsonnet:45` TLA default; passed to `MagnifySink` `runinfo.total_time_bin` |
| tick period | 0.5 µs | `clus.jsonnet:38` `tick: 0.5 * wc.us` |
| `tick_drift` | `drift_speed * tick` | `clus.jsonnet:39` (= 0.78 µm per tick at 1.56 mm/µs) |

---

## Clustering physics knobs (TLAs)

Passed by `run_clus_evt.sh:121-125` and applied in `wct-clustering.jsonnet:36-43`
as an overlay on `simparams.lar`:

| Knob | Value | Units | Description |
|---|---|---|---|
| `DL` | 6.2 | cm²/s | longitudinal diffusion coefficient |
| `DT` | 9.8 | cm²/s | transverse diffusion coefficient |
| `lifetime` | 10 | ms | electron lifetime |
| `driftSpeed` | 1.565 | mm/µs | overrides `simparams.lar.drift_speed` for clustering |
| `reality` | `'sim'` | — | `'sim'` or `'data'`; controls dead-channel treatment |

---

## Shared config file map

| Local file | Imported shared config |
|---|---|
| `wct-sp-to-magnify.jsonnet` | `pgrapher/experiment/sbnd/simparams.jsonnet` |
| `wct-img-all.jsonnet` | `pgrapher/experiment/sbnd/simparams.jsonnet`, `pgrapher/experiment/sbnd/img.jsonnet` |
| `wct-clustering.jsonnet` | `pgrapher/experiment/sbnd/simparams.jsonnet` (with TLA overlay) |
| `clus.jsonnet` | `pgrapher/common/clus.jsonnet` |
| `magnify-sinks.jsonnet` | *(no sbnd-specific imports)* |

All shared configs live under `$WIRECELL_PATH` → `toolkit/cfg/pgrapher/...`.
