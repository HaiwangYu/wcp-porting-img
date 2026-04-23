# PDVD vs PDHD SP-frame archive comparison

Both archives compared at anode 0, event level.

- PDVD: `/nfs/data/1/xning/wirecell-working/data/run039324/evt1/protodune-sp-frames-anode0.tar.bz2`
  (art event 339870)
- PDHD: `/nfs/data/1/xning/wirecell-working/data/hd/run027409/evt_1/protodunehd-sp-frames-anode0.tar.bz2`
  (art event 40896)

## Per-file shapes and dtypes

### PDVD (works end-to-end with WCT standalone imaging)

| file                        | shape         | dtype   |
|-----------------------------|---------------|---------|
| `channels_gauss0`           | (1536,)       | int32   |
| `channels_wiener0`          | (1536,)       | int32   |
| `frame_gauss0`              | (1536, 6400)  | float32 |
| `frame_wiener0`             | (1536, 6400)  | float32 |
| `summary_wiener0`           | **(1536,)**   | float64 |
| `tickinfo_*` `[0, 500, 0]`  | (3,)          | float64 |
| `chanmask_bad`              | (19, 3)       | int32   |

### PDHD (breaks WCT standalone imaging)

| file                        | shape         | dtype   |
|-----------------------------|---------------|---------|
| `channels_gauss0`           | (2398,)       | int32   |
| `channels_wiener0`          | (2435,)       | int32   |
| `frame_gauss0`              | (2398, 5859)  | float32 |
| `frame_wiener0`             | (2435, 5859)  | float32 |
| `summary_wiener0`           | **(14962,)**  | float64 |
| `tickinfo_*` `[0, 500, 0]`  | (3,)          | float64 |
| `chanmask_bad`              | (37, 3)       | int32   |

## Incompatibilities with WCT standalone imaging (`MaskSlice`)

### 1. `gauss` and `wiener` have different channel counts

- PDVD: both 1536; identical channel lists.
- PDHD: gauss has 2398 channels; wiener has 2435. The 37 wiener-only
  channels (e.g. 1604, 1608, 1637, 1640, 1660, 1683, …) have no
  matching gauss trace.

WCT source check (`img/src/MaskSlice.cxx:272`):
```cpp
if (charge_traces.size() != wiener_traces.size()) {
    THROW(RuntimeError() << errmsg{"charge_traces.size()!=wiener_traces.size()"});
}
```

### 2. `summary_wiener0` is per-ROI, not per-channel

- PDVD: 1536 entries = 1 per channel.
- PDHD: 14962 entries = 2435 runs of repeated values.
  - run lengths: min 1, max 21, median 6, mean 6.14
  - 2435 distinct "run values" ↔ 2435 wiener channels, 1:1
  - first 10 run lengths: `[8, 3, 6, 4, 3, 2, 10, 3, 7, 4]`
  - looks like one threshold per ROI, with variable ROI count per channel.

WCT source check (`img/src/MaskSlice.cxx:281`):
```cpp
if (summary.size() != wiener_traces.size()) {
    THROW(RuntimeError() << errmsg{"size unmatched"});
}
```

### 3. Frame tick length

- PDVD: 6400 ticks per frame (500 ns tick).
- PDHD: 5859 ticks per frame (same 500 ns tick).

This is benign for WCT imaging but flagged here because it's a
difference between the two productions. `run_sp_to_magnify_evt.sh`
now extracts the real tick count from the frame shape and writes it
into the Trun tree's `total_time_bin`.

## What's needed from Xuyang (for PDHD imaging to run)

For `protodunehd-sp-frames-anode*.tar.bz2` to feed WCT standalone
imaging the way the PDVD archives do, the LArSoft producer should
write:

1. One `gauss` trace per channel, matched 1:1 by channel (and tbin)
   with one `wiener` trace per channel — same channel list in
   `channels_gauss0` and `channels_wiener0`.
2. `summary_wiener` as a flat `(N_channels,)` array — one threshold
   per channel (e.g., per-channel RMS), not the per-ROI expansion.

If the per-ROI summary is a deliberate, newer convention for a
different downstream path, the standalone imaging pipeline needs a
different config than the PDVD one — but #1 (mismatched gauss/wiener
channel counts) is still a blocker even in that case.
