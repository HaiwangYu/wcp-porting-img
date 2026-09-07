# PDVD doc-08 STM hand scan (`d08pv_scan`)

Twelve objects, port 5017. Forked **by duplication** from `pdhd/d08_scan/`, which is untouched.

```bash
cd wcp-porting-img/pdvd/d08_scan && ./serve_d08pv_scan.sh 5017
ssh -L 5017:localhost:5017 user@wcgpu1      # then
#   http://localhost:5017/d08pv_scan_viewer
python3 score_d08pv_scan.py                 # after labelling
python3 selftest_d08pv_scan.py              # 65 checks
```

## What is being judged

`retile_hack_max_bridge = 10 cm` is PDVD production since 2026-09-06. On 30 events (run 039349,
144 matched clusters) it takes Steiner points more than 10 cm from live charge **22 → 0** and the
worst ghost **13.0 → 7.6 cm**, with TGM (494) and FC (522) completely unmoved. Its whole STM cost is
**four objects in 147**, and doc pdhd/08 §9.2 shows all four have an essentially unchanged fit — one
of them, evt 8 cluster 55, has *identical* kink, `exit_L` and `npts` in both arms with only its
status moving. So the question is not whether the cap reshaped the track. It did not. The question is
whether the tag was right before or after.

## Why 12 items and not 4

Four items, all of them flips, tells the scanner before they look that something changed on every
one — and then they hunt for a difference. So the sheet carries **eight controls**: four clusters
tagged STM in *both* arms and four tagged in *neither*, from the same events and size band. You are
not told which is which. The controls also measure your own agreement rate, which four items cannot;
`score_d08pv_scan.py` gates the flip verdict on that calibration (C0) before reading C1.

## Two PDVD-specific things the app handles

- **Unresolved-t0 points.** About 0.4 % of points carry `|x| ~ 1.5e8 cm` — the drift coordinate of a
  cluster whose t0 was never resolved. They are dropped from every panel; drawing them collapses the
  axes. `x` is drift and is **cathode-centred**: drift distance is `x_anode − |x|`.
- **The STM Bee layers are scoped to the tagged set** (doc pdvd/39 r3). Under REVEAL, an arm that did
  not tag the object draws **nothing** — an empty overlay is that arm's verdict, not a missing file.
  The banner says so explicitly. (On PDHD both arms always had something to draw; here they do not.)

## Blinding

The sheet has no verdict, no direction, and no `is_flip`. The key is separate and the viewer never
names it. Anything labelled with REVEAL on is saved with `revealed_before_label`, and the scorer
reports blind and revealed labels apart (C3).

## Files

| | |
|---|---|
| `make_d08pv_scan_sheet.py` | builds `../docs/scan/d08pv_stm_flip_{sheet,key}.tsv`, fixed seed 20260906 |
| `d08pv_scan_viewer.py` | the Bokeh app |
| `serve_d08pv_scan.sh` | refuses to start if 5017 is busy — a second server there does not fail loudly, it leaves the OLD app answering |
| `selftest_d08pv_scan.py` | 65 headless checks |
| `score_d08pv_scan.py` | the bar, fixed before any label existed |

Labels land in `../work/d08pv_scan_labels/<tag>/labels.json` on every click.
