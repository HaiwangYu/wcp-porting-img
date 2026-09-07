# Stopping muon + Michel electron — hand scan (PDHD and PDVD)

One Bokeh app for both detectors. Full write-up:
[`../docs/12_stm-michel-handscan-display.md`](../docs/12_stm-michel-handscan-display.md).
The chain it scans: doc [pdvd/48](../../pdvd/docs/nf_sp_img_clus/48_check-stm-michel-chain.md)
and doc [pdhd/03](../docs/03_check-stm-michel-pdhd.md).

## Start it

```bash
cd wcp-porting-img/pdhd/stm_michel_scan
./serve_stm_michel_scan.sh 5023 --det pdhd --scan-tag smx1
# or, from the PDVD tree, the same app on the PDVD sample:
cd wcp-porting-img/pdvd/stm_michel_scan
./serve_stm_michel_scan.sh 5024 --scan-tag smx1
```

From a laptop:

```bash
ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
    -L 5023:localhost:5023 <user>@wcgpu1.phy.bnl.gov
# then open  http://localhost:5023/stm_michel_viewer
```

The keepalive flags are not decoration: a bare `ssh -L` is reaped during exactly
the long pauses a hand scan is made of, and Bokeh's JS does not auto-reconnect.

Ports already taken in this tree: img_plot 5012/5013, pd_plot 5014,
ql_scan 5008/5015/5016, wf_scan 5016, d05/d08/stm_scan/pr_display/pr148 5017,
overclustering 5018, em_display 5021, split_display 5022. **This app owns 5023
(PDHD) and 5024 (PDVD)**, and `serve_*.sh` **refuses** a busy port rather than
letting a second `bokeh serve` exit and leave the old app answering.

## What is on the screen

**Left, two tabs.**

- **3-D** (the default) — drag rotates, shift+drag pans, wheel zooms, a tap pins.
  The four preset buttons in the toolbar-less corner are reached from the 2-D
  tab instead; three of the presets reproduce the 2-D panels exactly, so if you
  lose your bearings you can step back to a view you already trust.
- **2-D projections** — Z-Y (side), Z-X (top), X-Y (end), at **full detector
  extent** with the active boundary as a red dashed box and the APA / CRP seams
  as purple dotted lines. Full extent is deliberate: a track auto-zoomed to its
  own extent looks contained in every projection, which inverts STM/THRU calls.
  `Zoom to object` is there when you want it.

**Both draw the same layers.**

| | |
|---|---|
| grey | all other charge in the event, thinned |
| colour | every imaged point within **20 cm of the fitted muon** and within **40 cm of its stopping end**, at **full density**, coloured by charge |
| dark points | the fitted muon chain, coloured by its own dQ/dx |
| magenta star | your pin |

The colour and grey sets are chosen **purely geometrically** over all the charge
in the event. Neither is "the points the reconstruction assigned to this
cluster" — that would draw the clustering decision, which is part of what you
are judging.

**Right — dQ/dx vs signed arc length.** The muon sits at positive arc length
(its own residual range, re-anchored on your pin); anything on the far side of
the pin sits at **minus** its distance from the pin. The detector's own muon
(solid) and electron (dashed) reference curves are overlaid, in absolute e/cm —
nothing is normalised to a MIP, so what you see is the measurement.

Only the muon chain carries a residual range at all: `CheckSTM_Michel.cxx:682`
writes `rr = L = -1` for every Michel, delta and dot point. That is why the
panel's axis is signed arc length through your pin rather than `rr`.

## What to answer

| button | |
|---|---|
| `STM + MICHEL` | it stops inside, and there is a Michel electron at the stop |
| `STM, no Michel` | it stops inside, no Michel visible (µ⁻ capture is real, and so is a Michel out of time or out of the volume) |
| `THRU` | it does not stop — it crosses or exits a face (anode and cathode both count) |
| `FRAG → …` | the coloured chain is only **part** of the object; the verdict is still for the **full** object |
| `MESSY` | not one track — fused tracks, a shower. "Does it stop" is ill-posed |
| `UNCLEAR` | you genuinely cannot tell |

Then set **the Michel, if any, is:** `none` / `attached` / `detached dots` /
`both`. It starts at *not set* on every item and a `STM + MICHEL` label is
**refused** until you answer it — that radio is what the downstream separation
needs, and the chain's `michel_conn_type` only guesses at it.

**Why `FRAG` is three buttons and not one.** "The chain ends but grey charge
continues" holds two opposite physics truths: a fragment of a through-goer (an
STM tag is wrong) and a fragment of a stopper (the tag is right, on a
wrong-sized object). A `FRAG` button records the *same* verdict as its plain
counterpart plus `partial: true`, so under-clustering costs the scan **no**
statistical power and the under-clustering rate falls out as its own number.

Keep the escape hatches distinct: `FRAG` is about the **cluster**, `MESSY` about
the **object**, `UNCLEAR` about **your confidence**. Do not spend a fragment on
`UNCLEAR` — that is the one substitution the scan cannot recover.

Clicking a label **saves immediately** and jumps to the next unlabelled item.
Type a note *before* clicking. `next unlabelled >>` resumes where you left off.

## The pin, and one honest limit

You place the muon's **stopping point**: tap any panel to snap to the nearest
point of the fitted chain, drag the residual-range slider, or type an x/y/z if
you think the true stop is off the fit. The dQ/dx panel re-anchors live, so the
muon side and the Michel side separate exactly where you say.

**The limit, measured rather than assumed.** The reconstruction's own `stop_*`
is **not** hidden from you: it *is* the last point of the muon chain, which has
to be drawn, and it sits within 0.01 cm of that point on **97.7 %** of items on
both detectors. So the pin is not a blind independent placement and this scan
never claims it is — it measures whether you **agree**, and the label records
`placed` and `moved_cm` so "I looked and I agree" and "I moved it 4 cm" are
different rows. What the blind still withholds is what the scan is about: the
Michel verdict, the Michel / delta / dot segmentation, the reject bits, and the
cosmic tagger's own stop, which differs from `stop_*` by a median 0.64 cm and up
to 266 cm on PDHD (0.45 cm and up to 34 cm on PDVD).

## The blind, and why REVEAL exists anyway

`REVEAL the reconstruction` shows the Michel / delta / dot segments, the entry
and stop markers, the tagger's own STM fit, `is_stm`, the reject bits, the
Michel energy and kink. It starts **off**. Every label records
`revealed_before_label`, and `score_stm_michel_scan.py` scores revealed and
hidden labels **separately** and never merges them — a label taken with the
answer on screen cannot measure agreement with the answer.

This is the opposite of the sibling `../stm_scan` app, whose blind is structural
(it refuses to open the layers). Here the reconstruction's Michel *is* the thing
under test, so it has to be showable — the discipline moves from "cannot" to
"recorded".

The **display's** blind is structural and proved (the self-test poisons the
payload's verdict and looks for it in every data source). The **key file's** is
not: `../docs/scan/<det>_stm_michel_scan_key.tsv` is committed beside the sheet,
because a key that lives only next to a `work/` arm stops being scorable the day
that arm is retired. Its header says so — the blind on that file is an honour
rule, and that goes for an assistant asked to help with a scan too.

## Where the stopping point is

The header badge names the readout unit: `APA2 (x<0, face 0, z>=231)` on PDHD,
`anode 5 / CRU 11 (top drift (x>0), CRP y<0, z>=149.65, face 1)` on PDVD, plus
the distance to the nearest APA/CRP seam, to the cathode, to the anode face and
to the nearest wall.

The label comes from the **wire**, `pw = ChanScheme::globalf(2, apa, face, wire)`
— a readout fact that needs no T0. `sign(x)` is unsafe on PDVD, where the two
drift volumes overlap in the pre-T0 apparent-x frame and this scan looks at
exactly the out-of-time cosmics that lands on. When the wire and geometric
routes disagree the badge **says so** instead of picking silently; measured over
every chain point of both arms they agree 97 718/97 721 (PDHD) and
166 031/166 037 (PDVD), and every exception is one fit point carrying the
writer's default wire.

## Files

| file | |
|---|---|
| `prep_stm_michel_scan.py` | builds the blind sheet, the closed key and one JSON sidecar per item |
| `stm_michel_viewer.py` | the app; fork by duplication of `../stm_scan/stm_scan_viewer.py`, which is untouched |
| `smx3d.py` | the 3-D trackball; fork of `sbnd_xin/em_display/em3d.py`, which is untouched |
| `smgeom.py` | the one shared module: envelopes, seams, wire→unit |
| `serve_stm_michel_scan.sh` | starts it, refuses a busy port |
| `selftest_stm_michel_scan.py` | 171 headless checks: the blind (by poisoning the verdict), every label, the pin against brute force, the wire→unit map against the production wire file, the prep's near/far split against brute force, the scorer end to end on synthetic labels |
| `selftest_smx3d_browser.py` | 19 checks in headless chromium: a real drag reaches the CustomJS, every layer moves with it, and no point projects outside its own distance from the camera |
| `score_stm_michel_scan.py` | scores against the key, stratum-reweighted, revealed labels separately |
| `../docs/scan/<det>_stm_michel_scan_sheet.tsv` | the item list — no verdict, no stratum |
| `../docs/scan/<det>_stm_michel_scan_key.tsv` | the answer key — committed as the record; its blind is an honour rule, see above |
| `../work/stm_michel_labels/<tag>/labels.json` | your labels; a sibling of the per-event dirs, so re-running an arm cannot delete them |
| `prep-<det>/` | the sidecars, gitignored (205 MB); rebuild with `prep_stm_michel_scan.py` |

## Rebuild and re-check

```bash
./prep_stm_michel_scan.py --det pdhd     # 61 events  -> 302 items
./prep_stm_michel_scan.py --det pdvd     # 120 events -> 568 items
./selftest_stm_michel_scan.py            # both detectors
./selftest_smx3d_browser.py --det pdhd
./score_stm_michel_scan.py --det pdhd --tag smx1
```
