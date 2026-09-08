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

**Left, three tabs.**

- **3-D** (the default) — drag rotates, shift+drag pans, wheel zooms, a tap pins.
  The four preset buttons in the toolbar-less corner are reached from the 2-D
  tab instead; three of the presets reproduce the 2-D panels exactly, so if you
  lose your bearings you can step back to a view you already trust.
- **2-D projections** — Z-Y (side), Z-X (top), X-Y (end), at **full detector
  extent** with the active boundary as a red dashed box and the APA / CRP seams
  as purple dotted lines. Full extent is deliberate: a track auto-zoomed to its
  own extent looks contained in every projection, which inverts STM/THRU calls.
  `Zoom to object` is there when you want it.
- **2-D measurement** — what the wires actually saw. Nine panels: U, V, W down
  the rows, and across the columns the **measured** charge in each (channel,
  time slice) cell, the charge the fitted track **predicts** there, and their
  **difference**. This is the content of a Magnify tracking display, from the
  same tree (`T_proj_data`).
  - **grey hatched bands are dead channels.** They are drawn under the cells
    too, so a gap with nothing in it still reads as *dead* rather than as
    *nothing was there*. **Inside one, `measured` is the imaging model's filler,
    not a reading — the residual there means nothing.**
  - the thin black line is the CheckSTM_Michel PR fit in its own wire
    coordinates; the Michel / delta / dot points join it under REVEAL.
  - the colour scales are **fixed per plane**, so two items are comparable. The
    `×0.5 … ×4` buttons move all six together; `cell size` sets the marker in
    screen pixels; `window` switches between the whole cluster and ± 150
    channels / slices around the stop, which is where the Michel is.
  - the residual map is white-centred on purpose: where the fit agrees, the cell
    disappears, so only disagreement draws the eye.

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

**Click a point in this panel** and a cyan cursor marks the same point in the
3-D view, in all three projections and in all nine measurement panels, with its
arc length, dQ/dx, x/y/z, U/V/W wire, time slice and readout unit printed under
the plot. Click empty space to clear it. The link is one-directional on purpose:
taps on the other panels place the pin, and one tap should not do two things.

The colour is Turbo on a **fixed** 0 – 1.5 × 10⁵ e/cm scale, and every marker is
outlined. It used to be Viridis on a per-item scale, which put the Bragg peak —
the thing you are here to judge — in bright yellow on a white page, and made the
colour mean something different on every item.

**The fit you see is the CheckSTM_Michel PR fit**, a uniform 0.600 cm step. The
cosmic tagger's own fit (irregular, median 0.610 cm) is the grey `tagfit` layer
behind REVEAL, and is not drawn in the measurement panels at all.

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

## Only the muon's own bundle

**`bundle only` is ON by default.** It restricts the image-charge layers and the
three 2-D projections to the clusters that share the muon's matched Q-L bundle —
same `flash_id` *and* same `cluster_t0_us`. The **2-D measurement panels are not
filtered and should not be**: they show what the wires measured against what the
fit predicts, and that is exactly where an unreconstructed Michel shows up.

You want this on, because the Bee layer the display reads places **every**
cluster at its **own** bundle's t0-corrected position. Two cosmics thousands of
microseconds apart in drift time can therefore land centimetres apart on screen.
On `039252_15 / 77` that drew a 434 cm through-going muon (cluster 103, t0
2542 µs) 5.6 cm from a 107 cm stopping muon (cluster 77, t0 6200 µs) — 541 cm
apart in drift, and it reads as an over-clustered track. It is not; they are
different objects at different times. See doc pdhd/13 §4.

Turn it **off** and nothing is lost: the out-of-bundle charge reappears in
<span style="color:#b07aa1">mauve</span>, a colour no other layer uses, so you
can see what is nearby without ever mistaking it for the muon's own. The line
under the toggles always says how many points are being hidden.

One thing this does *not* do: it says nothing about whether the bundle is
**right**. If the Q-L matching put the wrong cluster in, `bundle only` will
faithfully draw the wrong cluster. It removes a known confusion; it is not a
truth filter.

## The particle flow

`show particle flow` draws the PR graph this chain actually walked — the
segments, each in its own colour, and the junction vertices — in the 3-D view,
the projections and the measurement panels. The toggle starts **off**, so the
view you already know is unchanged until you ask for the graph.

The dropdown lists every segment with its point count, length and median dQ/dx.
Pick one and it lights up amber everywhere. Then say what it is:

| button | |
|---|---|
| `muon` | part of the stopping muon |
| `Michel` | part of the Michel electron |
| `delta / other` | a delta ray or anything else hanging off the track |
| `straddles the stop` | the segment genuinely covers both sides — the honest answer, not a coin flip |
| `untag` | remove the tag |

Your tags are drawn as **hollow squares**, a marker nothing else on the page
uses, so they can never be confused with the reconstruction's colours. Only
3.5 % (PDHD) / 6.6 % (PDVD) of segments really straddle the muon/Michel
boundary, so the question is well posed nearly always — but not always, which is
why the fourth button exists.

Under REVEAL the panel also prints what the chain calls the segment: its
particle type and whether it called it a track or a shower. That is behind
REVEAL because `CheckSTM_Michel` sets the Michel arm's type to electron, so it
*is* the answer.

## Energies, and the mu -> e link (doc pdhd/14)

**Everything here is a `T_stm_michel` branch.** The display computes no energy
of its own, on purpose: a viewer that fills the chain's gaps with its own
arithmetic looks complete and measures nothing, and the point of this scan is to
find what `CheckSTM_Michel` is missing. Where the chain writes nothing, the
panel says so in red.

The **muon's energy rides un-blinded** on the status line beside the track
length the sheet already shows:

    ... 188 chain points over 112.5 cm — chain muon KE 278.0 MeV (range 278.0 / dQ/dx 222.1) ...

Both routes are named because they disagree — by 20 % on `039252_15 / 77` — and
you should see that rather than one number chosen for you. `muon_ke_best` is the
range estimate for every chain over 4 cm, which is the toolkit's own rule.

Under **REVEAL** a `particle flow` block prints the chain's `mu -> e` relation:

    mu   pdg 13   112.5 cm   278.0 MeV (range 278.0 / dQ/dx 222.1)   1 chain seg
      └─ attached at the shared stop vertex 77003
           e   pdg 11   seg 77009   8.4 cm   31.2 MeV   2 shower segs, kink 47 deg

That shared vertex is the **only** parentage the chain ever writes. On a
`detached` item there is no shared vertex and no link at all — the dots were
admitted on distance to the stop alone — and the panel says so instead of
drawing an edge that does not exist. On such an item it also warns that
`michel_found` is 0 even though a Michel *was* reconstructed: doc pdhd/13's
defect D1.

If the panel tells you the arm predates doc pdhd/14, the PR arm needs re-running
— there is no muon energy in that output to show.

## Am I sure it saved?

Yes, and you can check without leaving the page. Labels are written atomically
on every click, and every write is **read back from the file**: the green banner
under the buttons says how many labels the file on disk actually holds, its size
and when it was written. `what is saved on disk?` re-reads on demand and prints
this item's own row — label, Michel kind, pin, segment tags.

- a file that does not exist yet says *nothing saved yet* — not an error;
- a file that will not parse says **NOT SAVED** in red;
- segment tags placed **before** you click a label are held, not saved, and the
  banner says so in amber. Tagging an item that already has a label writes
  through immediately.

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
| `smgeom.py` | the one shared module: envelopes, seams, wire→unit, the plane split, ticks→slices |
| `serve_stm_michel_scan.sh` | starts it, refuses a busy port |
| `selftest_stm_michel_scan.py` | 6252 headless checks: the blind (by poisoning the verdict), every label, the pin against brute force, the wire→unit map against the production wire file, the prep's near/far split against brute force, the scorer end to end on synthetic labels, and the measurement panel: the plane split gated against the fitter's own wire coordinate, ticks→slices gated against the files, the residual recomputed, and the click landing on the same point in all thirteen views, the particle flow (its row selector, its blind, its tagging and backward compatibility) and the save read-back |
| `selftest_smx3d_browser.py` | 39 checks in headless chromium: a real drag reaches the CustomJS, every layer moves with it, no point projects outside its own distance from the camera, the nine measurement panels paint on the heaviest item of the arm (with the causal control that emptying the cell sources changes the pixels), the click link survives the websocket round trip, and the particle-flow toggle and segment picker are pressed as real widgets |
| `score_stm_michel_scan.py` | scores against the key, stratum-reweighted, revealed labels separately |
| `../docs/scan/<det>_stm_michel_scan_sheet.tsv` | the item list — no verdict, no stratum |
| `../docs/scan/<det>_stm_michel_scan_key.tsv` | the answer key — committed as the record; its blind is an honour rule, see above |
| `../work/stm_michel_labels/<tag>/labels.json` | your labels; a sibling of the per-event dirs, so re-running an arm cannot delete them |
| `prep-<det>/` | the sidecars, gitignored (338 MB — they carry the 2-D measurement and the particle flow); rebuild with `prep_stm_michel_scan.py` |

## Rebuild and re-check

```bash
./prep_stm_michel_scan.py --det pdhd     # 61 events  -> 302 items
./prep_stm_michel_scan.py --det pdvd     # 120 events -> 568 items
./selftest_stm_michel_scan.py            # both detectors
./selftest_smx3d_browser.py --det pdhd
./score_stm_michel_scan.py --det pdhd --tag smx1
```
