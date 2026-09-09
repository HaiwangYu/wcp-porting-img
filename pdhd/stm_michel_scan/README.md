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
  - **the drag rotates about the stopping point** (2026-09-08), not about the
    middle of the track, so zooming into the Bragg end and turning it keeps it
    on screen. Turn on `tap sets the 3-D rotation centre` and a tap puts the
    centre on any drawn point instead of moving the pin; `centre on the stop`
    puts it back, and moving to another item turns the toggle off again. The price: a centre at one end of the track needs a framing
    radius equal to the whole track, so the starting view is about twice as
    wide as it was — one wheel-scroll, paid once per item, because
  - **your zoom survives everything but a new item.** Labelling, tagging a PF
    segment, moving the pin and switching bundles all repaint without touching
    a range. `reset the view` and the two zoom toggles reframe on demand; so
    does moving to another item.
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
    coordinates, with the Michel / delta / dot points on it.
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
cosmic tagger's own fit (irregular, median 0.610 cm) is the grey `tagfit` layer,
and is not drawn in the measurement panels at all.

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

Clicking a label **saves immediately** — the verdict, the pin and the segment
tags together.
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

### The object table (doc pdvd/53)

Below the toggle is a **grouped table of every object near this stop**, not a
flat list. It replaced a dropdown that stopped scaling: over the 153 PDVD
`is_stm` candidates of the d51gv arm a candidate carries a mean of 4.6 PF
segments, p90 9 and **max 23** — `039253_12` cluster 41 is 8 muon pieces and 15
EM ones. A muon broken into eight pieces and a Michel into fifteen is not a
list, it is two groups.

Each row is an **object**:

| row | what it is |
|---|---|
| `S<id>` | a fitted PR segment |
| `C<id>` | a whole cluster the PR produced **no** segment for — charge on screen and nothing else, so it can only be grouped as a whole |

and the columns say how many points, how long, the median dQ/dx, how far the
piece is from the stop, and **what the chain says about it** — including, for a
piece the chain fitted and then dropped, the gate that dropped it.

The table opens in the **chain's own grouping**, so what you are looking at is
the reconstruction's answer and your job is to move what is wrong. Pick a row
and it lights up amber everywhere; then move it:

| button | |
|---|---|
| `→ muon` | part of the stopping muon |
| `→ Michel` | part of the Michel electron |
| `→ gamma` | an isolated gamma near the stopping point — muon capture, not decay |
| `→ unassigned` | remove your grouping (back to the chain's) |
| `delta / other` | a delta ray or anything else hanging off the track |
| `straddles` | the object genuinely covers both sides — the honest answer, not a coin flip |

Your tags are drawn as **hollow squares**, a marker nothing else on the page
uses, so they can never be confused with the reconstruction's colours. Only
3.5 % (PDHD) / 6.6 % (PDVD) of segments really straddle the muon/Michel
boundary, so the question is well posed nearly always — but not always, which is
why the fourth button exists.

**`bundle only` now governs the table too** (owner, 2026-09-08; doc pdvd/53
§8). Only pieces inside this stop's own Q-L bundle are objects *of* this stop,
so with the control on — the default — a `C<id>` row from another flash is not
listed at all, and the head line says how many were dropped. It is not a trim:
**97 % of the PDVD `C` rows and 96 % of the PDHD ones were foreign** (1292 of
1331, 559 of 583). Untick the control and they come back, marked `OTHER FLASH`.

The reason is doc pdhd/13 §4: the Bee image layer draws every cluster at its
*own* Q-L bundle's t0-corrected x, so a cluster from another flash lands
wherever its own drift correction puts it. On `039252_15` cluster 77 the two
blobs 6 and 16 cm from the stop are flash 134 at t0 2542 µs against the muon's
flash 298 at 6199 µs — 573 cm away in drift, one of them a 434 cm through-going
track. On `039253_14` eight of the blobs within 60 cm of cluster 49's stop are
the same artifact. The chain never fits them: the survey admits same-bundle
clusters only, and **every `S` row is in the bundle by construction** (3888 PF
segments over 569 PDVD payloads, 0 foreign).

**Stepping between items repaints the table** (doc pdvd/53 §9). Until
2026-09-08 it did not when the next item happened to have the same *number* of
rows — the previous item's objects stayed on screen beside the new item's
picture. If you scanned before that date and a table ever looked wrong for the
event, that is why.

**A row you have already tagged is never hidden**, whatever the control says: it
stays marked `OTHER FLASH` so you can move it, and it stays for the rest of the
item even after `→ unassigned` — which pops the tag, and would otherwise make
the row evict itself half way through a correction.

The panel also prints what the chain calls the segment: its particle type and
whether it called it a track or a shower. That *is* the chain's answer —
`CheckSTM_Michel` sets the Michel arm's type to electron — and since 2026-09-08
it is shown rather than hidden (see *The blind is gone* below).

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

A `particle flow` block prints the chain's `mu -> e` relation:

    mu   pdg 13   112.5 cm   278.0 MeV (range 278.0 / dQ/dx 222.1)   1 chain seg
      └─ attached at the shared stop vertex 77003
           e   pdg 11   seg 77009   8.4 cm   31.2 MeV   2 shower segs, kink 47 deg

That shared vertex is the parentage the chain writes on the attached side.

## The Michel as ONE object (doc pdhd/15)

A Michel is usually a track, but the 3-D clustering routinely breaks pieces off
it, and through doc pdhd/14 those pieces were added to the shower and then left
out of its energy. Since doc pdhd/15 the object is assembled first and energised
once, so the panel reads:

    mu   pdg 13   180.5 cm   424.1 MeV (range 424.1 / dQ/dx 330.2)   1 chain seg
      └─ attached at the shared stop vertex 91002
           e   pdg 11   core seg 91002   2 pieces in the object   29.2 MeV = dQ/dx 29.2 + unfitted charge 0.0
                  core alone 16.2 · pieces 13.0 · core range 36.5 · chain kine_charge 0.0
                  core 11.2 cm, kink 36 deg · 1 dot (0 unfitted clusters carrying 0 e)

Read it as: **29.2 MeV is the object**, 16.2 of it the core arm and 13.0 the
piece 4.3 cm past its tip. `core alone` is exactly what `michel_ke_best` reported
through doc pdhd/14, so an older number is still recoverable from the tree.

A **bridged** item (`michel_conn_type == 2`) is one whose electron the 3-D
clustering split off the muon entirely. It now carries the same parentage — the
muon's stop vertex — plus the measured gap:

      └─ bridged to the same stop vertex 77002 across 0.38 cm of empty space

A **charge-only** item (`michel_conn_type == 3`) is one where the companion
passed every admission test but the fitter produced no segment for it, so there
is no shape, no `michel_seg_id` and no dQ/dx — only charge:

      └─ charge only, 6.31 cm from the stop vertex 43002 — …

`chain kine_charge` is the chain's own charge-based estimate of the same object.
It is **0 by construction** on these arms and the panel says so: the estimator
projects the 2-D charge map with no t0, while the point cloud is t0-corrected,
so on a cosmic hundreds of cm off the beam frame nothing matches. Doc pdhd/15 §6
has the diagnosis; the charge route that *does* work here is `unfitted charge`,
which converts the blob charge of a companion cluster the fitter never reached.

If the panel tells you the arm predates doc pdhd/14 or pdhd/15, the PR arm needs
re-running — that output has no muon energy, or no object breakdown, to show.

## Am I sure it saved?

Yes, in two places, and you can check without leaving the page.

**Top right, the scan table** (2026-09-08): every row the label file on disk
actually holds — scan number, `event/cluster`, label, Michel kind, how far the
pin was moved, how many PF segments are tagged — with the item you are on
marked `▶`. It is built from the same read of the file that fills the green
banner, so the two cannot disagree. The line above it says what is *not* saved:
`this item is not saved; 2 PF tags held in memory only` is the case that used to
be invisible.

**And the copy box** beside the navigation buttons carries this item's
`event/cluster` key as selectable text — click it, copy it. Pasting another
item's key into it jumps there.
 Labels are written atomically
on every click, and every write is **read back from the file**: the green banner
under the buttons says how many labels the file on disk actually holds, its size
and when it was written. `what is saved on disk?` re-reads on demand and prints
this item's own row — label, Michel kind, pin, segment tags.

- a file that does not exist yet says *nothing saved yet* — not an error;
- a file that will not parse says **NOT SAVED** in red;
- segment tags placed **before** you click a label are held, not saved, and the
  banner says so in amber. Tagging an item that already has a label writes
  through immediately.

### `SAVE this item` (2026-09-08)

The green **SAVE this item** button beside the notes box writes the item on
screen — **the stopping point, the segment tags and the notes** — into its row
and prints what the file then holds. It is not a new persistence path: every
control already writes through. It is the one place that does all three at once,
for when you want to be sure rather than to reason about which control wrote
what.

It **refuses** on an item you have not given a verdict yet, and says so. That is
deliberate: `score_stm_michel_scan.py` reads `rec["label"]` unguarded, so a row
without one would not enlarge the scan, it would stop the scorer. Click a label
first — the label click writes the pin and the tags with it.

### What used to be lost, and is not any more

Until 2026-09-08 the pin was the one hand-placed datum with **no write-through
and no restore**. Three consequences, all silent:

- moving the pin *after* labelling an item never reached the file, unless you
  happened to click a label again;
- coming back to an item redrew it on the fit's own end, so a pin you had placed
  looked as though it had never been saved;
- and because the pin was rebuilt from that cleared state, **re-labelling an
  item replaced a placed pin with `placed=false, moved_cm=0.0`** — the file is
  written atomically over itself and keeps no history, so the placement was
  gone with no trace.

The pin now behaves exactly as the segment tags do: every move writes through
when the item has a row, returning to an item restores it (matched back to the
nearest chain point, or kept at its stored x/y/z and flagged in red if the
payload no longer has a point there), and a re-label can no longer downgrade
one. `unset pin` is the only way back to the fit end, and it persists too.

## The pin, and two honest limits

**The restore's own limit.** A pin comes back matched to the nearest point of
the drawn chain. If the payload no longer has a point there — a re-prepped arm,
a changed fit — it is restored at the exact x/y/z you placed instead, the
distance is printed in red beside the item line, and from that moment the row
records it as `source: "manual"` with `rr: null`. The **coordinates**, `placed`
and `moved_cm` are preserved, which is everything `score_stm_michel_scan.py`
reads; what is lost is the provenance saying it once sat on a chain point.

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

## The blind is gone (2026-09-08), and what that costs

The `REVEAL the reconstruction` toggle has been **removed** at the owner's
request: the Michel / delta / dot segments, the entry and stop markers, the
tagger's own STM fit, `is_stm`, the reject bits and the Michel energy and kink
are all on screen from the first paint.

**Read the agreement number accordingly.** A label taken with the answer on
screen cannot measure agreement with the answer — this is why the toggle existed.
Every label still records `revealed_before_label` and `score_stm_michel_scan.py`
still scores the two strata separately and never merges them; what changed is
that the field is now always `true`. **The four labels taken before 2026-09-08
are the only unbiased rows in the file.** Anything quoted from this scan from
here on is *the chain's reconstruction reviewed by a physicist*, not an
independent verdict, and must be reported as that.

This is now the opposite of the sibling `../stm_scan` app, whose blind is
structural (it refuses to open the layers).

The **key file's** blind is unaffected and is not structural:
`../docs/scan/<det>_stm_michel_scan_key.tsv` is committed beside the sheet,
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
| `selftest_stm_michel_scan.py` | 45624 (PDVD) / 26509 (PDHD) headless checks: that the chain's answer reaches the screen (by poisoning the verdict), the view — the rotation centre, the framing bound, and that nothing but a new item reframes — every label, the pin against brute force, the wire→unit map against the production wire file, the prep's near/far split against brute force, the scorer end to end on synthetic labels, and the measurement panel: the plane split gated against the fitter's own wire coordinate, ticks→slices gated against the files, the residual recomputed, and the click landing on the same point in all thirteen views, the particle flow (its row selector, its tagging and backward compatibility), the save read-back, the copy box and the saved-labels table |
| `selftest_pin_persistence.py` | 28 checks (PDVD) / 21 (PDHD, check 10 skipped): that a pin placed before a label is held and *said* to be held, that the label click stores it, that **moving it after the label writes through**, that leaving an item and returning restores it as `source='pin'` at the same point, that a re-label cannot downgrade a placed pin, that `unset pin` still un-pins and persists that, that a PF tag on a labelled item writes through and is restored, that `SAVE this item` writes all three and its confirmation survives the repaint, and that it refuses an item with no verdict. Check 10 replays the live `smx1` row `039349_18/36` — the only one with a hand-placed pin — out of a copy. Run the same file against the pre-2026-09-08 viewer and checks 1, 3, 4 and 5 fail: that negative control is what makes it a test of the fix |
| `selftest_smx3d_browser.py` | 77 checks per detector in headless chromium: a real drag reaches the CustomJS, every layer moves with it, the pin stays exactly at the rotation centre, no point projects outside its own distance from the camera, **the drag survives a label click** — the camera the scanner drags to lives only in the browser, so this is the one gate that can see the server pushing a stale angle back — the nine measurement panels paint on the heaviest item of the arm (with the causal control that emptying the cell sources changes the pixels), the click link survives the websocket round trip, and the particle-flow toggle and the grouped object table are pressed as real widgets |
| `score_stm_michel_scan.py` | scores against the key, stratum-reweighted, revealed labels separately |
| `../docs/scan/<det>_stm_michel_scan_sheet.tsv` | the item list — no verdict, no stratum |
| `../docs/scan/<det>_stm_michel_scan_key.tsv` | the answer key — committed as the record; its blind is an honour rule, see above |
| `../work/stm_michel_labels/<tag>/labels.json` | your labels; a sibling of the per-event dirs, so re-running an arm cannot delete them |
| `prep-<det>/` | the sidecars, gitignored (338 MB — they carry the 2-D measurement and the particle flow); rebuild with `prep_stm_michel_scan.py` |

## Rebuild and re-check

```bash
# --pin-tranche: keep the 60-item tranche 1 of a scan ALREADY UNDER WAY.  The
# draw is stratified on `michel_found`, so without the pin an algorithm change
# re-draws the sample under the scanner -- it moved 41 of 60 PDVD and 32 of 60
# PDHD items between doc 14 and doc 15 (doc pdhd/15 sec 10).  The argument is a
# sheet path or `<rev>:<path>`, read with `git show`, so a superseded sheet
# stays usable as a pin.  Omit it only for a genuinely new scan under a new tag.
./prep_stm_michel_scan.py --det pdhd \
    --pin-tranche 86d78116:pdhd/docs/scan/pdhd_stm_michel_scan_sheet.tsv
./prep_stm_michel_scan.py --det pdvd \
    --pin-tranche 86d78116:pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
./selftest_stm_michel_scan.py            # both detectors; group [N] checks the draw
./selftest_smx3d_browser.py --det pdhd --port 5093
./selftest_smx3d_browser.py --det pdvd --port 5091
./score_stm_michel_scan.py --det pdhd --tag smx1
```

### The three muon energy scales (doc pdhd/16)

Since the `d16*nu` arms `T_stm_michel` carries **three** energies for the same
stopping muon, and the flow panel shows all three side by side rather than
combining them:

| branch | what it reads | note |
|---|---|---|
| `muon_ke_range` | the track's length through the CSDA table | the **baseline**; charge-blind except through where the track ends. `muon_ke_best` is still this above 4 cm |
| `muon_ke_dqdx` | the fitted charge, through the recombination model's inverse | the only one carrying the gain x lifetime x recombination normalization |
| `muon_ke_mcs` | multiple Coulomb scattering off the trajectory | reads **no charge at all**; `-1` = the engine refused the path |

`muon_p_range` / `_dqdx` / `_mcs` are the same three as momenta,
`sqrt((KE+m)^2 - m^2)`.  **`muon_ke_mcs = -1` means "not computed"** (trim
failed, fewer than 20 trimmed points, the trimmed end nearer than 28 cm to the
stop, or fewer than two fitted 14 cm segments) and must never be read as
0 MeV; `muon_mcs_amb` is the fit's ambiguity, 1 = maximally ambiguous, and
doc 84 R3.5 only trusts the scale below 0.2.

On these arms `check_stm_michel` alone gets a recombination model that carries
the measured normalization `C` -- 0.7941 on PDVD, 0.8120 on PDHD -- so
`muon_ke_dqdx` now sits **on** `muon_ke_range` instead of 24 % below it.  The
STM and neutrino taggers keep the uncalibrated instance, and no verdict moves.
Group `[O]` of the self-test closes that loop on the chain's own output.

`prep` **refuses to draw** while any `../work/stm_michel_labels/*/labels.json`
exists for that detector — pass `--pin-tranche`, or `--redraw` if you really are
starting a new scan (and then serve it under a new `--scan-tag`).

The item **set** never moves with the arm — 302 PDHD / 568 PDVD keys, and
`scan_id` is identical across every arm so far — but `scan_id` is a positional
index over the `(event, cluster)` sort, so one candidate more or fewer would
shift every id after it. Group `[N]` of the self-test re-derives it, and checks
that the tranche column is either pinned to the source its header names or
reproduces `prep`'s own draw.
