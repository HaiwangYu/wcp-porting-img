# The STM + Michel hand-scan rubric — apply this exactly

> **FROZEN 2026-09-09 after two calibration waves and one scan wave.**
> Everything below is final for all 509 tranche-2 items. It is not amended
> again mid-round: a rubric that moves while scanners work splits the sample
> into populations that cannot be counted together, which is exactly what
> happened to the first wave and why that wave was discarded and re-scanned.
> Residual ambiguity is recorded in the evidence and confidence fields, not
> fixed by changing this file.

You are hand-scanning reconstructed particle-physics events from the ProtoDUNE
vertical-drift detector (PDVD). Each item is one reconstructed object: a fitted
track plus every other charge cluster the display draws near it.

The question, in the detector owner's own words, is three things:

1. identify the **STM** — the stopping muon, and where it stopped,
2. identify the **Michel electron** clustering — the electron from the muon's
   decay at rest,
3. leave the clusters associated with **neither**.

## Hard rules — violating any of these invalidates the round

1. **NEVER open `pdvd/docs/scan/pdvd_stm_michel_scan_key.tsv`.** That file is
   the answer key for this scan. Do not read it, grep it, list it, or open any
   file with `_key` in its name under `pdvd/docs/scan/`. Reading it destroys
   the blindness of the whole 509-item round with no way to recover. Do not
   read any `labels.json` either — those are other people's verdicts.
2. **NEVER run `scan_harness.py apply`.** Without `--labeldir` it writes into
   the owner's live label file. Your only write is one verdict record per item,
   written through `mkv.py`. Nothing else.
3. **Write the record for an item as soon as you have judged it**, before
   moving to the next. If you run out of room mid-chunk, everything already
   written is kept and someone else finishes the rest — but only if you wrote
   as you went.

## What you look at, per item

Each item has a directory `<SHOTS>/<event>_<cluster>/` holding seven PNGs and a
`context.json`. **Read all seven images.** They are not redundant:

| file | what it is for |
|---|---|
| `a_proj_full.png` | the three 2-D projections at full detector extent — overall topology |
| `b_3d_wide.png` | the 3-D point cloud, whole object, coloured per object |
| `c_3d_stop.png`, `d_3d_stop.png`, `e_3d_stop.png` | the 3-D cloud zoomed on the stop at three azimuths — *along the Michel direction* vs *close and backward* is a 3-D judgement and one view can fake either |
| `f_meas.png` | nine measured / predicted / difference panels with dead channels — did it really stop, or leave through a dead region, and is that Michel real charge or a fit artefact |
| `g_dqdx.png` | **dQ/dx vs signed arc length** through the stop, with the muon (solid) and electron (dashed) reference curves overlaid — this is the Bragg evidence |

### Six display traps — every one has caught a scanner already

1. **`g_dqdx.png` ships at 514×338.** At that size a peak-then-collapse is
   invisible, and both fit-failure modes live in the last few centimetres.
   **Crop and upscale the plot ~4× before judging it.**
2. **Colour means two different things at once in the 3-D frames, so never read
   charge off them.** The base point cloud is coloured by dQ/dx (turbo), but the
   shots are taken with *show particle flow* ON, so the particle-flow layers
   draw on top with **categorical** colours — a fixed amber selection band, a
   per-segment palette, and opaque brown vertex squares. Turbo near 1–1.5e5 is
   also orange, so an amber flow band is easily misread as a Bragg peak.
   **Charge comes only from `g_dqdx.png` and the `dqdx` column**; the 3-D frames
   are for geometry.
3. **The orange entry circle is not always at the far end** — it can sit
   mid-track. Do not read it as the track's start.
4. **The 3-D frames draw the detector box in perspective**, so a far box edge
   projects right next to the stop and makes a deeply contained track look
   wall-adjacent. **Never read containment off a 3-D frame** — use
   `ends.stop.d_face`.
5. **`cos_fwd` is measured against the local tangent at the stop, not the
   track's overall chord.** On a curved track it therefore lies: a piece sitting
   *on* the muon line can table at `cos_fwd −0.94` as though it were 12 cm
   off-axis. On any visibly curved track, judge the off-axis distance from the
   3-D azimuths and treat `cos_fwd` as advisory.
6. **`g_dqdx.png` is not a complete census of the drawn objects.** Objects
   totalling dozens of points can be absent from the panel while small survey
   specks appear. Never conclude "there is nothing there" from the dQ/dx panel —
   the object table is the census.

`context.json` carries the numbers the display shows the human scanner:
`ends.entry` / `ends.stop` with `d_face` (distance to the nearest active face,
cm), `ends.is_stm` and `ends.reject_names` (the *chain's* own verdict — this is
the reconstruction you are checking, not truth), and one row per drawn object
with its `key`, `group`, `npts`, `size` (cm), `dqdx` (electrons/cm), `dstop`,
`chain` (the chain's particle guess), and geometry: `d_min`/`d_max` (cm from
the stop) and `cos_fwd` (+1 = straight ahead of the muon, −1 = back along the
muon's own body).

**Containment is a numbers call, backed by the picture.** The projections are
locked at full detector extent, where 10 cm from a face is about seven pixels.
Use `ends.stop.d_face`; do not try to eyeball it.

## Verdict — pick exactly one

* **`STM_MICHEL`** — the track ends inside the volume **and** there is decay
  activity past the end. This holds *even when the Bragg peak is unclear*: a
  Michel topology is sufficient on its own.
* **`STM_ONLY`** — ends inside the volume with a Bragg rise, and nothing past
  the end that reads as an electron. Isolated compact pieces judged to be
  muon-capture gammas do **not** promote this to `STM_MICHEL`.
* **`THRU`** — **no Bragg rise at the fit end.** This is the operative test,
  *not* "does it reach a face". A track can end 148 cm from every face and
  still be a through-goer, if its dQ/dx is flat on the MIP plateau to its last
  point — a stopping muon cannot do that. (Charge that continues past the fit
  end also means `THRU`.)

  **A flat profile is enough on its own.** You do *not* need to see where the
  track went: no visible continuation, no face, and no dead-region exit still
  gives `THRU` if the profile is flat to the last point. The cluster simply
  ended where the imaging ran out. Do not reach for `UNCLEAR` to avoid saying
  this — but do say so in `--notes`.
* **`FRAG_STM_MICHEL` / `FRAG_STM_ONLY` / `FRAG_THRU`** — the drawn cluster is
  visibly only a fragment of a larger object; the verdict still describes the
  **full** object.
* **`MESSY`** — not one track at all (an EM blob broken into many pieces, no
  coherent spine).
* **`UNCLEAR`** — you genuinely cannot tell. Say why in `--notes`.

## Bragg — how to read `g_dqdx.png`

**The sign on this plot does NOT tell you which side of the stop something is
on.** Read this carefully, because the obvious reading is wrong and it will flip
your tags (`stm_michel_viewer.py:658`, `:2450`):

* points **on the muon chain** are plotted at `rr − rr(origin)` — a real signed
  arc length, positive going back up the muon;
* **every other object** — delta, michel, dots, gamma — is plotted at
  **minus its 3-D distance from the origin**, whatever direction it lies in.

So a delta ray sitting 21 cm *back along the muon body* appears at s ≈ −21,
exactly where a Michel dot 21 cm *past the stop* would appear. On the negative
axis, only the **magnitude** is information; the sign just means "not on the
muon chain". Never infer "past the stop" from a negative s.

To decide which side something is on, use the object's `d_min`/`d_max` (distance
from the stop) together with `cos_fwd` and the three 3-D azimuths — never the
dQ/dx panel's x sign.

The test is a rise **above the track's own MIP plateau, following the shape of
the muon reference curve** over the last 10–20 cm. It is *not* "the data must
cross the reference curve": the overlaid muon curve asymptotes to ~1.6e5 at
s = 0 and real stoppers here top out at 1.2–1.35e5, so nothing ever crosses it.
Read shape and the rise off the plateau, never an absolute number.

A muon at its own Bragg peak cannot continue at MIP, so an arm leaving the stop
at MIP is a *second particle*.

* **A ragged rise still counts.** The owner: *"the Bragg peak is not as
  consistent, but I feel the scan is OK."* The test is whether the profile
  climbs above the muon curve towards the end, not whether it climbs
  monotonically. Point-to-point scatter of a factor of two is normal at these
  charges and is **not** a reason to call a stopper a through-goer.
* Ignore zero-charge points; they are fit points with no measured charge and
  they fake contrasts.

## The stopping point — when to move the pin

The pin defaults to the fit's last point and is right ~98 % of the time, so
move it only when the picture says the fit is wrong. **The signature that says
so is specific: the profile peaks several cm before the fit's last point and
then collapses.**

The mechanism, in the owner's words: *"there might be a small gap between the
stopping STM and the Michel electron leading to low dQ/dx fit."* The fit
bridges the muon's true stop and the Michel, and the interpolated points across
that gap carry little charge. **So the diagnostic is the collapse, not the
height of the peak.**

When it is there, the segment past the peak is the **Michel** even when the
chain types it `muon`. **The collapse is the diagnostic; the depth of it is
not a threshold.** Segments seen so far run from 0.15 to 0.5 of MIP — what
matters is that the charge falls far below the muon's own plateau where a muon
at its Bragg peak would be far above it, not that it lands in any particular
band. Set `--pin-rr <cm>` to the arc length of the junction between the last
real muon segment and that one, and tag that segment `michel`.

Not every terminal dip is this. A last point 20–30 % low, or a single
partial-charge point at the very end, is ordinary scatter — leave the pin alone
and say so in the evidence. The signature is a *sustained* collapse over
several cm into something the fit then bridges.

**When the collapse falls inside a single segment**, there is no separate row to
retag: the tag alphabet is per-object and cannot split one. Move the pin anyway
— that is the measurement that matters — tag the segment for what most of it is,
and say in the evidence that the row is split and which part is which. This is a
known limitation of the label schema, not something to solve by picking a tag
that misdescribes the whole row.

**Moving the stop moves the attribution with it.** A small isolated piece that
reads as a lone capture gamma beside an `STM_ONLY` can become part of the
Michel once the stop moves back to where it belongs.

### The opposite case: the fit stops SHORT

The overshoot above is one direction. The other happens too, and it manufactures
**false `STM_MICHEL`**, so check for it on every item:

*The Bragg peak sits 1–3 cm **past** the fit's last point*, in a short
high-charge piece lying straight ahead (`cos_fwd` ≳ +0.85, `dstop` a couple of
cm) at 0.9–1.2e5 e/cm — and the chain types that piece `pdg 11` and offers it as
the Michel.

**The charge is the load-bearing clause** — not the angle, not the chain's
`pdg 11`. A ~2 cm piece at 1e5 e/cm is not an electron: an electron's first
centimetres are at or below MIP, and 1e5 is four to six times that, which is
exactly what the muon's own last centimetres look like. So that tip is the
**muon**, the true stop is at its far end, and the item is `STM_ONLY` unless
there is *other* decay activity further out.

A partial match is not a match. A short forward piece **at or below MIP**, and
especially one whose charge *falls* as it goes out, is a real Michel — that is
the ordinary `STM_MICHEL` case, not this one. Do not invoke the undershoot
unless the charge is several times MIP.

`--pin-rr` slides the pin along the fit and **cannot move it past the fit's last
point**, so you cannot record the corrected stop. Do this instead:

* tag the tip `muon` (not `michel`, whatever the chain says),
* judge the verdict from what is left past the tip,
* start `--notes` with `UNDERSHOOT:` and say where the real stop is.

This was seen twice in the first twelve items scanned, so expect it often. It is
being counted across the round and reported.

## `michel_kind` — mechanical, derived from your own tags

`michel_kind` describes **the topology of the decay-related charge past the
stop**. It is *not* "is there a Michel" — an `STM_ONLY` item with capture
gammas past the stop is `detached dots`, not `none`.

Derive it mechanically from the tags you just assigned:

| you tagged | `michel_kind` |
|---|---|
| a `michel` piece and a `gamma` piece | `both` |
| a `michel` piece, no `gamma` | `attached` |
| a `gamma` piece, no `michel` | `detached dots` |
| neither | `none` |

`muon` and `delta / other` never affect it. `mkv.py` **enforces** this rule and
refuses a record that breaks it, so you cannot get it wrong by accident.

This is a real rule, not bookkeeping: it makes the field mean the same thing on
every row, which is what lets the 569 rows be counted together afterwards.
Never leave it `— not set —`.

## Attribution — every drawn object gets exactly one tag

| tag | rule |
|---|---|
| `muon` | on the muon side of the stop, including a stub carrying straight on past a fit end that is not a stop |
| `michel` | attached at the stop, or a piece past it consistent with the electron. **Within ~10 cm of the stop, direction does not discriminate** — a Michel is emitted isotropically, so a piece there is part of the decay whichever way it points |
| `gamma` | isolated, past the stop, clear of the muon body line, within ~60 cm. **Charge is not a criterion**: a faint speck 40 cm out is an uncertain gamma, not a confident delta |
| `delta / other` | lies **ON** the muon body line (`cos_fwd` ≤ −0.85) at any distance; or is within ~10 cm of the stop, backward, and body-excluded by the chain; or belongs to a different object entirely |
| `straddles the stop` | one object genuinely spanning the stop. Rare — used 0 times in 60 items. Only on clear evidence. |

**When any two of the rules above collide, off-axis separation and attachment
decide.** They collide in both directions, and this paragraph governs *every*
such case, not just the one it illustrates:

* *michel vs delta* — a piece 3 cm behind the stop but 6 cm out to the side
  reads `cos_fwd −0.39`, which the michel rule claims (inside 10 cm, direction
  does not discriminate) and the delta rule also claims (close and backward);
* *michel vs gamma* — a piece 9.4 cm out is inside the michel rule's "direction
  does not discriminate" radius **and** satisfies the gamma rule's "isolated,
  past the stop, clear of the body". Here **attachment** breaks the tie: if
  there is a clean charge-free gap between it and the stop, it is a detached
  dot — `gamma` — however close it sits. A 0.3 cm, 2-point speck across a 9 cm
  gap is not a 35 MeV electron.

Resolve on **how far the piece sits off the muon's line**, and let that outrank
both the `cos_fwd` number and the chain's own exclusion label:

* **hugging the muon body** → `delta / other`, at any distance, whatever the
  chain says;
* **well clear of the body line** → `michel` if it is attached to or bridged to
  the stop, `gamma` if it is detached and compact.

`cos_fwd` alone cannot do this job: it mixes "behind the stop" with "on the
body", which are different questions. Use the three 3-D azimuths to judge the
transverse offset — that is what they are for. Say in the evidence which way you
went and why.

**On a `MESSY` item, tag every row `delta / other`.** The tag vocabulary
presupposes an identified stop, and a `MESSY` item has none — by construction
every object is "associated with neither", which is the owner's own third
category. This is the convention used on all five `MESSY` items in tranche 1;
follow it so the tag counts stay comparable.

**On a `THRU` item: fitted chain segments `muon`, everything else
`delta / other`, kind `none`.** `gamma` and `michel` are defined relative to a
stop, and a through-goer has none — tagging a speck `gamma` there would force
`michel_kind` to `detached dots` and assert decay charge past a stop that does
not exist. If you find yourself wanting `gamma` on a `THRU`, the real question
is whether the verdict is right.

**Faint far specks, 20–60 cm out with `cos_fwd` near 0.** These are common and
they flip `attached` ↔ `both` on their own, so decide them one way: a speck is
`gamma` when it lies **on the Michel's side** — roughly along the arm's
direction, or on the same side of the stop as the decay — and `delta / other`
when specks are **scattered in unrelated directions** around the 60 cm ring.
Charge is not a criterion (a faint speck is an uncertain gamma, not a confident
delta), but *isolation in a random direction* is. Say which case you judged it
to be.

Object **key shapes** are not uniform, and `mkv.py` checks them for you: a
fitted track segment's key is its bare id (`"35004"`), an unfitted cluster's
key is `C` plus its id (`"C218"`). Use the `key` field from `context.json`
verbatim.

## Confidence

`high` — the picture settles it. `medium` — you had to weigh two readings.
`low` — you are guessing; say why in `--notes`. Be honest: the medium/low rows
are the ones the owner will look at, and marking a genuinely uncertain call
`high` is worse than the uncertainty.

## Evidence — required, one real paragraph per item

Write what you actually saw, in the shape of the tranche-1 records, so the call
can be re-audited later without re-opening the pictures. Say: the length and
where it entered/stopped relative to the faces; what the dQ/dx profile did in
the last 10–20 cm and against which curve; what sits past the stop and where
(distance, direction) and why it reads as Michel / gamma / delta; and anything
that made the call hard. A worked example of the *shape* (the numbers are
invented — no real item is described here):

> 140 cm, enters 0.4 cm from the anode face, stops 63 cm from the nearest wall.
> Profile sits on a 5e4 plateau and climbs to 1.15e5 over the last 14 cm,
> following the muon curve; the rise is ragged, with one point back at 7e4, but
> it is a rise. A 9 cm two-piece arm leaves the stop at about 50 deg carrying
> 4e4 e/cm — a muon at its own Bragg peak cannot continue at MIP, so the arm is
> a second particle, and 9 cm is the right range for a ~20 MeV electron. One
> 0.4 cm speck 31 cm out, forward and well clear of the muon body line: gamma.
> The three pieces 25–60 cm back along the body at cos_fwd −0.9 or below are
> body activity, so delta / other. No dead region at the stop in any plane.

Do not write "looks good" or "clear STM". `mkv.py` refuses anything under 12
words, but the bar is the paragraph above, not the word count.

## How to write the record

One command per item, after you have looked at all seven frames:

```
python3 <T2>/mkv.py '<event>/<cluster>' <VERDICT> '<michel_kind>' <confidence> \
  --shots-dir '<SHOTS>' --out-dir '<OUT>' \
  --tags 'muon:35004,35005 michel:36001 gamma:140020' \
  --default 'delta / other' \
  --evidence '...one real paragraph...' \
  [--notes '...'] [--pin-rr 4.8]
```

**`--tags` splits on whitespace, so write `other:` for `delta / other`** —
`'delta / other:75021'` is rejected with a confusing "bad tag group
'delta'". The accepted aliases are `other:` and `straddle:`.

`--default` tags every row you did not name, so a forgotten object cannot ship
as a silent hole; `mkv.py` **refuses** a record with any untagged row. Name the
objects you are confident about in `--tags` and let `--default` catch the rest —
but only when `delta / other` is genuinely the right answer for them.

If `mkv.py` refuses, fix the record and re-run it. Never hand-write the JSON.
