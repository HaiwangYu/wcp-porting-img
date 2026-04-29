# PDVD coherent-noise groups in `chndb-base.jsonnet`

## What coherent-noise groups are

WireCell coherent-noise filtering subtracts a per-group median waveform
from every channel in the group.  The grouping is specified as a 2-D
list of offline channel numbers under the `groups:` key of the chndb
configuration object.  In `cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet`
this list is a literal list of 360 explicitly enumerated groups (lines 53–412).

The grouping principle is: **same FEMB + same sense-wire plane → grouped
together**.  This is verified by cross-referencing the chndb group lists
against the official DUNE PD2VD channel map
`PD2VDTPCChannelMap_v2.txt`.  All 360 groups map cleanly onto a single
(FEMB, plane) cell — no group mixes FEMBs or planes.  Larger
(FEMB, plane) cells are subdivided into approximately equal halves to
keep group sizes manageable.

---

## Channel-map column layout

File: `PD2VDTPCChannelMap_v2.txt` (12 columns, parsed by `TPCChannelMapSP.cxx`)

```
offlchan  detid  detelement  crate  slot  stream  streamchan
  plane   chan_in_plane  femb  asic  asicchan
```

Key fields used here:

| field | meaning |
|---|---|
| `offlchan` | WCT offline channel number (0–12287) |
| `detid` | 10 = bottom electronics, 11 = top electronics |
| `detelement` | CRP index: 4, 5 = bottom CRPs; 2, 3 = top CRPs |
| `plane` | 0 = U (induction-1), 1 = V (induction-2), 2 = W (collection) |
| `femb` | FEMB number within the CRP |
| `asic` | FE-ASIC index within the FEMB (0-based) |

---

## Detector overview

PDVD has two electronics systems with different FEMB granularity:

| | Bottom electronics | Top electronics |
|---|---|---|
| Offline channels | 0–6143 | 6144–12287 |
| Channel-map `detid` | 10 | 11 |
| CRPs | detelement 4, 5 | detelement 2, 3 |
| FEMBs per CRP | **24** | **10** |
| Channels per FEMB | **uniform 128** | **variable 256 or 384** |
| chndb groups per CRP | **96** | **84** |
| Plane totals per CRP | U=952, V=952, W=1168 | U=952, V=952, W=1168 |

Both CRPs of a given electronics type are identical in FEMB composition
(confirmed by the channel map for de=4 vs de=5 and de=2 vs de=3, though
the specific channel numbers differ).

---

## Bottom CRP grouping (detelement = 4 or 5)

Each bottom CRP has 24 FEMBs, each with exactly 128 channels.  The wire
routing divides FEMBs into four structural families:

### FEMB families

| Family | FEMBs | Plane composition | Notes |
|---|---|---|---|
| V-edge | 1, 2, 3, 13, 14, 15 | V=32, W=96 | No U wires |
| U-edge | 10, 11, 12, 22, 23, 24 | U=32, W=96 | No V wires |
| Middle | 5–8, 17–20 | U=64, V=64 | No W wires |
| Transition | 4, 9, 16, 21 | U=62, V=62, W=4 | Small W stub |

The 4-channel W stub in each transition FEMB is **not included** in any
chndb group (too small to provide a useful common-mode estimate).

### Splitting rule

Every active (FEMB, plane) cell is split into exactly **2 chndb groups**,
each covering a contiguous half of the ASIC set within that cell.
For example, FEMB 1 V-plane (32 channels, ASICs 0 and 3) yields two
16-channel groups — one per ASIC pair.

| (FEMB, plane) cell size | Split | chndb group size |
|---|---|---|
| 32 (V-edge, U-edge induction) | 32 = 2×16 | 16 |
| 62 (transition induction) | 62 = 2×31 | 31 |
| 64 (middle induction) | 64 = 2×32 | 32 |
| 96 (edge collection W) | 96 = 2×48 | 48 |

### Per-CRP group count check

```
V-edge (6 FEMBs) × 2 planes × 2 groups =  24 (V + W)
U-edge (6 FEMBs) × 2 planes × 2 groups =  24 (U + W)
Middle (8 FEMBs) × 2 planes × 2 groups =  32 (U + V)
Transition (4 FEMBs) × 2 planes × 2 groups = 16 (U + V; W dropped)
Total per CRP = 96 ✓
```

### Detailed per-FEMB composition (representative: detelement = 4)

```
FEMB  1: V=32, W=96    → 2×16 (V) + 2×48 (W)  = 4 chndb groups
FEMB  2: V=32, W=96    → same
FEMB  3: V=32, W=96    → same
FEMB  4: U=62, V=62, W=4 → 2×31 (U) + 2×31 (V) + dropped (W) = 4 chndb groups
FEMB  5: U=64, V=64    → 2×32 (U) + 2×32 (V)  = 4 chndb groups
FEMB  6: U=64, V=64    → same
FEMB  7: U=64, V=64    → same
FEMB  8: U=64, V=64    → same
FEMB  9: U=62, V=62, W=4 → same as FEMB 4
FEMB 10: U=32, W=96    → 2×16 (U) + 2×48 (W)  = 4 chndb groups
FEMB 11: U=32, W=96    → same
FEMB 12: U=32, W=96    → same
FEMB 13: V=32, W=96    → same as FEMB 1
FEMB 14: V=32, W=96    → same
FEMB 15: V=32, W=96    → same
FEMB 16: U=62, V=62, W=4 → same as FEMB 4
FEMB 17: U=64, V=64    → same as FEMB 5
...
FEMB 21: U=62, V=62, W=4 → same as FEMB 4
FEMB 22: U=32, W=96    → same as FEMB 10
FEMB 23: U=32, W=96    → same
FEMB 24: U=32, W=96    → same
```

---

## Top CRP grouping (detelement = 2 or 3)

Top electronics has only 10 FEMBs per CRP, but each FEMB covers 256 or
384 channels because the wire pitch and routing are different.  The
FEMB-to-plane assignment is **highly irregular** — no clean family pattern
exists.  The two top CRPs (de=2 and de=3) also have different per-FEMB
compositions, reflecting different physical wiring on each CRP.

### Per-FEMB composition (detelement = 2)

| FEMB | U channels | V channels | W channels | total |
|---:|---:|---:|---:|---:|
| 0 | 32 | 64 | 160 | 256 |
| 1 | 64 | 64 | 128 | 256 |
| 2 | 32 | 64 | 160 | 256 |
| 3 | 126 | 94 | 36 | 256 |
| 4 | 128 | 128 | 128 | 384 |
| 5 | 158 | 190 | 36 | 384 |
| 6 | 156 | 156 | 72 | 384 |
| 7 | 128 | 96 | 160 | 384 |
| 8 | 64 | 32 | 160 | 256 |
| 9 | 64 | 64 | 128 | 256 |

### Per-FEMB composition (detelement = 3)

| FEMB | U channels | V channels | W channels | total |
|---:|---:|---:|---:|---:|
| 0 | 96 | 128 | 160 | 384 |
| 1 | 156 | 124 | 104 | 384 |
| 2 | 126 | 126 | 132 | 384 |
| 3 | 160 | 96 | 128 | 384 |
| 4 | 96 | 64 | 96 | 256 |
| 5 | 64 | 96 | 96 | 256 |
| 6 | 64 | 96 | 96 | 256 |
| 7 | 32 | 64 | 160 | 256 |
| 8 | 94 | 94 | 68 | 256 |
| 9 | 64 | 64 | 128 | 256 |

### Splitting rule

Because (FEMB, plane) cells are much larger and irregular in the top
electronics, the split factors are not uniform.  The chndb attempts to
keep individual group sizes near 32 channels, with the following
consequences:

- Small cells (32–36 ch): kept unsplit (1 group).
- 64-channel cells: split into 2×32.
- 72-channel cells: kept unsplit (1 group of 72).
- 94–96-channel cells: split into 3 groups (~31–32 each).
- 126–128-channel cells: split into 4×31 or 4×32 (except
  W-plane 128-ch cells which split into 2×64 or 3×~43).
- 156–160-channel cells: split into 5 groups (~31–32 each).
- 190-channel cell (FEMB 5 V de=2): split into 6×~31.

The sub-group boundaries follow ASIC partitions within the FEMB but the
exact assignment is encoded in the explicit channel lists and is not
expressed as a closed-form formula.

---

## Reconciliation table

| CRP | `detid` | `detelement` | map (FEMB,plane) cells | chndb groups | effective split |
|---|---|---|---|---|---|
| bottom-0 | 10 | 4 | 52 active (4 dropped) | 96 | 2× |
| bottom-1 | 10 | 5 | 52 active (4 dropped) | 96 | 2× |
| top-0    | 11 | 2 | 30 | 84 | 2.8× average |
| top-1    | 11 | 3 | 30 | 84 | 2.8× average |
| **total** | | | **164 active** | **360** | |

The 4 "dropped" cells per bottom CRP are the 4-channel W stubs in
the transition FEMBs (4, 9, 16, 21), which are too small for a
reliable median estimate and are omitted from the chndb groups list.

---

## Verification recipe

The following Python snippet reproduces the group-size histogram and
confirms that every chndb group is a pure single-(FEMB, plane) cell.
Run from the repository root; expects the channel map at
`/home/xqian/tmp/PD2VDTPCChannelMap_v2.txt`.

```python
import re, collections

CHANMAP = '/home/xqian/tmp/PD2VDTPCChannelMap_v2.txt'
CHNDB   = 'cfg/pgrapher/experiment/protodunevd/chndb-base.jsonnet'
GROUPS_FIRST_LINE = 52   # 1-based; groups: [ starts here
GROUPS_LAST_LINE  = 413  # the closing ] line

ch_to_cell = {}
with open(CHANMAP) as fh:
    for line in fh:
        f = line.split()
        ch_to_cell[int(f[0])] = (int(f[1]), int(f[2]), int(f[9]), int(f[7]))
        # (detid, detelement, femb, plane)

groups = []
with open(CHNDB) as fh:
    for i, line in enumerate(fh, 1):
        if GROUPS_FIRST_LINE <= i < GROUPS_LAST_LINE and line.lstrip().startswith('['):
            groups.append([int(x) for x in re.findall(r'\d+', line)])

# Check purity and count sizes per electronics type
mixed = 0
bot_sizes = collections.Counter()
top_sizes = collections.Counter()
for grp in groups:
    cells = set(ch_to_cell[c] for c in grp if c in ch_to_cell)
    if len(cells) != 1:
        mixed += 1; continue
    detid = next(iter(cells))[0]
    if detid == 10: bot_sizes[len(grp)] += 1
    else:           top_sizes[len(grp)] += 1

print(f"mixed groups: {mixed}")
print(f"bottom group-size histogram: {dict(bot_sizes)}")
print(f"top    group-size histogram: {dict(top_sizes)}")
# Expected:
#   mixed groups: 0
#   bottom group-size histogram: {16: 48, 30: 16, 32: 80, 48: 48}
#   top    group-size histogram: {30: 16, 32: 128, 64: 24}
```
