# doc pdvd/55 — the PDVD STM + Michel hand scan, the complete arm

**Sections 1–12 are tranche 1** (60 items, scanned 2026-09-08/09 and
reviewed by the owner). **Sections 13–18 are tranche 2** (the other 509),
which completes the arm: together they are a **census** of every
`CheckSTM_Michel` candidate in d53v, not a sample of one. The headline
numbers are in §14, the two failure mechanisms and the recommended cut in
§15, what the labels are worth in §16.

**Repro.**

    cd wcp-porting-img/pdhd/stm_michel_scan
    W=$HOME/tmp/smx1a            # scratch, never /tmp (M16)
    mkdir -p $W/blank
    # the 60 items of tranche 1, in sheet order
    awk -F'\t' '!/^#/ && $2=="1" {print $3"/"$4}' \
        ../../pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv > $W/items.txt
    # the pictures the scan was taken from (own scratch port; :5017 untouched)
    ./scan_harness.py --det pdvd --tag blank --labeldir $W/blank \
        shots --items-file $W/items.txt --out $W/shots
    # the labels, written by clicking the real widgets, from the scan record
    # committed beside the sheet (verdict, michel kind, pin, every object tag,
    # and the evidence sentence for each item)
    ./scan_harness.py --det pdvd --tag smx1a \
        apply --verdicts ../../pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json
    # the artifact on disk says what the record says
    ./verify_scan_record.py --det pdvd --tag smx1a \
        --record ../../pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json
    # the comparison against the owner's tag
    ./compare_scan_tags.py --det pdvd --a smx1 --b smx1a
    # and the scorer's own schema gate
    ./score_stm_michel_scan.py --det pdvd --tag smx1a

    # ---- tranche 2 (sections 13-18): the other 509 items, same commands ----
    awk -F'\t' '!/^#/ && $2=="2" {print $3"/"$4}' \
        ../../pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv > $W/items_t2.txt
    # shots: five processes is what loses the WebGL context (section 13.2) --
    # two at a time, then check, then re-shoot whatever the check names
    ./scan_harness.py --det pdvd --tag blank --labeldir $W/blank \
        shots --items-file $W/items_t2.txt --out $W/shots_t2
    python3 check_shots.py $W/shots_t2 $W/reshoot.txt
    # the frozen rubric the 509 were scanned against
    less ../../pdvd/docs/scan/pdvd_stm_michel_scan_rubric.md
    # every number in sections 14 and 15, re-derived from the committed record,
    # and diffed against the literals published here
    python3 mkstats.py --check

Sheet `pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv` (tranche 1 = 60 items),
payloads `pdhd/stm_michel_scan/prep-pdvd/`, labels
`pdvd/work/stm_michel_labels/smx1a/labels.json` — which, like every label dir
under `work/`, is **not committed** (`.gitignore:36`), the same as `smx1`.
What *is* committed is the scan record that regenerates it,
`pdvd/docs/scan/pdvd_stm_michel_smx1a_verdicts.json` (60 records: verdict,
Michel kind, confidence, pin, every object tag and the evidence sentence),
following the precedent of `pdvd/docs/scan/d08pv_stm_flip_labels.json`.  Every
number in §4 and §5 and every row of the table in §12 is read back out of
`labels.json` **on disk**, not out of that record; `verify_scan_record.py` asserts the
two agree on every published field, and it is green.  The owner's tag `smx1`
is **read only** throughout and is byte-identical before and after
(`sha256 8fc76b33…`).

## 1. What this round is

Doc pdhd/12 built the hand-scan display and doc pdvd/53 gave it the grouped
object table.  The owner scanned 32 of the 60 tranche-1 PDVD items into tag
`smx1` and asked (2026-09-08) for the scan to be carried to completion, with
their 32 used to calibrate it, so they can validate before a larger round.
Their three goals, in their words: **identify the STM (the stopping point);
identify the Michel electron clustering; leave the clusters associated with
neither.**

Doc [pdvd/54](54_michel-lost-at-the-stop-two-mechanisms.md) is the companion
written the same day: it takes two items out of the owner's own scan and gives
the mechanism behind them.  This doc is the other half — the whole tranche,
scanned.

This doc records **all 60 tranche-1 items scanned into a new tag `smx1a`** —
the 28 the owner had not done, and a re-scan of their 32 — with an explicit
attribution on **every object the display draws**, 465 tags in all.

Owner decisions taken before scanning: all 60 rather than only the 28; a new
tag rather than writing into `smx1`; tag every drawn object rather than only
the overrides.

**2026-09-09**: the owner reviewed the ten rows this scan had flagged as
uncertain, on the display, serving `smx1a` on :5017.  Nine stand and one is
corrected; three rules came out of their comments and are folded into the
rubric in §3, which is the part that will outlive this tranche.  §9 has their
words, row by row.

## 2. How the scan was taken — and the one thing to know about it

`pdhd/stm_michel_scan/scan_harness.py` (new) starts **the app itself** —
`stm_michel_viewer.py`, same document, same glyphs — on its own scratch port,
opens it in headless chromium, and reads pixels back.  It is not a second
renderer: a matplotlib script over the same sidecars would be a second
instrument whose agreement with what the scanner sees on :5017 would itself
need gating.  The viewer is not modified, and port 5017 is never touched.

Per item it captures seven frames: the three projections at full detector
extent (containment), the 3-D cloud whole and then at **three azimuths 90°
apart zoomed on the stop** (topology and attribution — "along the Michel
direction" versus "close and backward" is a 3-D judgement one view can fake),
the nine measured / predicted / difference panels around the stop (is the
charge real, is there a dead region), and dQ/dx versus signed arc length with
the muon and electron reference curves (the Bragg evidence).  Alongside it
writes a text sidecar: the object table, the chain's own answer, and — added
because the picture cannot resolve it — **both endpoints and each one's
distance to the nearest active face**.

Labels are written by **clicking the real widgets**, never by a JSON writer,
and every row is read back off disk before the harness moves on.

**The pictures were taken against an EMPTY label directory.** So the two pins
the owner had placed, and all their tags, were absent from every frame; the
stop judgements below are independent of them.

## 3. The rubric that was applied

Written down before scanning and reported here so the *rule* can be validated,
not only the calls.  It is the owner's own instruction turned into something
checkable.

**Verdict.**

* `STM_MICHEL` — the track ends inside the volume **and** there is decay
  activity past the end.  Per the owner this holds even when the Bragg peak is
  unclear: a Michel topology is sufficient on its own.
* `STM_ONLY` — ends inside the volume with a Bragg rise, and nothing past the
  end that reads as an electron.  Isolated compact pieces judged capture gammas
  do **not** promote this.
* `THRU` — no Bragg rise at the fit end.  This is the operative test, not
  "does it reach a face": of the eight non-stoppers here exactly **one**
  reaches one (`039349_63/48`, 0.1 cm from the y wall).  The other seven end
  11.6 to 148 cm from every active face — five of them more than 35 cm in —
  with a profile flat on the MIP plateau to its last point, and a stopping muon
  cannot do that.  (Stop-to-nearest-face, cm: 0.1, 11.6, 19.0, 35.3, 61.3,
  111.7, 139.2, 148.0.)
* `FRAG_*` — the drawn cluster is visibly a fragment; `label` still carries the
  full object's verdict.
* `MESSY` — not one track.  Used 5 times, where the owner used it 0 times in
  32; see §6.

**Bragg** is read on the dQ/dx panel against the overlaid reference curves,
not against a number: a rise above the muon curve over the last 10–20 cm.
A muon at its own Bragg peak cannot continue at MIP, so an arm that does is a
second particle.  **A ragged rise still counts.**  The owner's reading of
`039349_66/78` — *"the Bragg peak is not as consistent, but I feel the scan is
OK"* — settles that: the test is whether the profile climbs above the muon
curve towards the end, not whether it climbs monotonically.  Scatter of a
factor of two point-to-point is normal at these charges and is not a reason to
call a stopper a through-goer.

**Stopping point.** The pin is a *confirmation* (doc pdhd/12 §6.2): the chain
end equals `stop_*` to <0.01 cm on 97.7 % of items, so it is moved only when
the picture says the fit is wrong.  The signature that says so is specific:
**the profile peaks several cm before the fit's last point and then collapses**.
Moved on 3 of 60.

  *Read the last few centimetres before accepting the fit end as the stop.*
  The mechanism, in the owner's words on `039349_26/40`, is a **gap**: *"there
  is might be a small gap between the stopping STM and the Michel electron
  leading to low dQ/dx fit"* — the fit bridges the muon's true stop and the
  Michel, and the interpolated points across the gap carry little charge.  So
  the diagnostic is the collapse, not the height of the peak.  When it is
  there, the segment past the peak is the Michel even when **the chain types it
  `muon`**: that happened on `039349_18/36` and again on `039349_67/78`, 2 of
  60, and in both the segment sits at a third to a half of MIP where a muon at
  its Bragg peak would be far above it.  The pin goes to the junction between
  the last real muon segment and that one, and the segment is tagged `michel`.

  *Moving the stop moves the attribution with it.*  A small isolated piece that
  reads as a lone capture gamma beside an `STM_ONLY` can become part of the
  Michel once the stop moves back to where it belongs — `225015` on
  `039349_67/78` went from `gamma` to `michel` on exactly that account, without
  a single pixel of it changing.

**Attribution**, per object, settled at the end of the fresh pass and applied
to all 60:

| tag | rule |
|---|---|
| `muon` | on the muon side of the stop, including a stub carrying straight on past a fit end that is not a stop |
| `michel` | attached at the stop, or a piece past it consistent with the electron.  Within ~10 cm of the stop **direction does not discriminate** — a Michel is emitted isotropically, so a piece there is part of the decay whichever way it points |
| `gamma` | isolated, past the stop, clear of the muon body line, within ~60 cm.  Charge is not a criterion: a faint speck 40 cm out is an uncertain gamma, not a confident delta |
| `delta / other` | lies **ON** the muon body line (cos_fwd ≤ −0.85) at any distance; or is within ~10 cm of the stop, backward, and body-excluded by the chain — the owner's own "close to the track and backward" case; or belongs to a different object |
| `straddles the stop` | used 0 times, as in `smx1` |

**What the owner's review changed** (§9, 2026-09-09): the three paragraphs above
in *italic emphasis* — the ragged-Bragg allowance, the gap mechanism and the
"the chain's last `muon` segment may be the Michel" rule — are theirs, folded in
after they reviewed the ten uncertain rows.  One row moved as a result
(`039349_67/78`); the rubric change is the part that will matter on tranche 2.

**The vocabulary gap, reported not fixed.** The owner's "leave the clusters
associated with neither" has no value in the alphabet.  `delta / other` is
doing double duty here for real delta rays *and* for unrelated neighbours, and
on the five `MESSY` items it carries every row.  A sixth value — `unrelated`,
or `not this object` — would separate them; that is a display change and is not
made in this round.

## 4. What the scan says

**60 items, 465 object tags, 3 pin corrections** — after the owner's review of
2026-09-09 (§9), which moved one row.

| verdict | all 60 | the owner's 32 | the 28 new |
|---|---:|---:|---:|
| `STM_MICHEL` | 34 | 18 | 16 |
| `STM_ONLY` | 13 | 9 | 4 |
| `THRU` | 7 | 4 | 3 |
| `FRAG_THRU` | 1 | 1 | 0 |
| `MESSY` | 5 | 0 | 5 |

| `michel_kind` | n |
|---|---:|
| `attached` | 18 |
| `both` | 16 |
| `detached dots` | 8 |
| `none` | 18 |

Tags: **muon 143, michel 64, gamma 60, delta / other 198, straddles 0**.
`pf_tagged == n_pf_objects` on every row, which is the point of tagging the
agreements too: in `smx1a`, "I agree with the chain" and "I never looked" are
distinguishable, and `pf_chain_group` rides alongside so the override rate is
recoverable.  Of the 198 `delta / other`, **136 are on the five `MESSY` items**
and the other 62 are spread over 21 rows — see the vocabulary gap in §3.

**The chain's own flag against the hand scan, on all 60.**  `is_stm` is
`reject_bits == 0`; a Michel is deliberately not one of its criteria.

| | hand: a stopper | hand: not a stopper |
|---|---:|---:|
| `is_stm = 1` | **35** | 1 |
| `is_stm = 0` | **12** | 12 |

Of the 36 the chain calls STM, 35 are stoppers by eye.  The single
disagreement is **`039349_38/60`**, and it is not a clean win for the scan:
it is exactly the row §8.6 and §9 carry as unresolved — 119 cm ending abruptly
110 cm in from the anode (35.3 cm from the nearest face, the z wall) with no
Bragg rise and nothing drawn past the end, which is why I recorded `THRU` at
**medium** confidence.  So the chain's one false positive
is also the hand scan's least certain rejection, and the purity number carries
that caveat rather than resolving it.

But **12 of the 24 it rejects are stoppers too**: eleven of them fail on
`shape_flat` and/or `no_bragg` while the profile plainly rises, and the twelfth
(`039349_27/41`) fails `stop_near_boundary` with its stop 66.7 cm from the
nearest active face.  One of the eleven, `039349_66/78`, is the other row §9
lists as genuinely undecided (`STM_ONLY` vs `STM_MICHEL` — a stopper either
way, so it does not move this cell).  That is the efficiency side of the
purity/efficiency question doc pdvd/48 §11 left open, and producing it is what
this scan is for.

The eleven no_bragg / shape_flat stoppers, for whoever tunes that cut:
`039349_29/45`, `039349_3/46`, `039349_66/78`, `039349_67/78`, `039252_9/52`,
`039253_15/105`, `039349_18/36`, `039349_2/38`, `039349_21/51`,
`039349_26/18`, `039349_26/40`.  Several are low-energy muons whose whole
length sits above MIP, which is exactly the population a flat-shape test
mistakes for a through-goer.

**The scorer's own read of the same 60 rows.**  `score_stm_michel_scan.py
--det pdvd --tag smx1a` runs clean — it refuses an unrecognised `label`
outright, so this doubles as the schema gate on all 60 rows — and scores
against the committed key, stratum-reweighted:

    --- labels taken with the reconstruction REVEALED (55 scored) ---
      STM + Michel   purity     raw  25/25  = 1.000   reweighted = 1.000
      STM + Michel   efficiency raw  25/34  = 0.735   reweighted = 0.457
      is_stm alone   purity     raw  35/36  = 0.972   efficiency raw  35/47 = 0.745
    under-clustering (FRAG) rate: S3 1/12

The `is_stm` line is the 2×2 above, arrived at independently: 35/36 purity is
the one false positive, 35/47 efficiency the twelve missed stoppers.  The
STM+Michel efficiency splits raw from reweighted by a factor of 1.6 because the
draw is stratified and S4 — the stratum the chain calls neither — carries a
weight of 32.8; the reweighted 0.457 is the population number and the raw 0.735
is this sample's.  Five `MESSY` rows are unscored (2 in S3, 3 in S4), which is
what that column is for.  All 60 rows are labelled, `pf_tagged ==
n_pf_objects` on every one, and both pins carry a `moved_cm`.

## 5. Agreement with the owner's 32 — and what it is worth

`./compare_scan_tags.py --det pdvd --a smx1 --b smx1a`

* **Verdict: 32/32 (100 %).**  Every one of the owner's calls is reproduced,
  including all 5 of the THRU family and all 9 `STM_ONLY`.  The matrix the tool
  prints has three columns rather than four because `label` carries the full
  object's verdict on a fragment; the `choice` field, which keeps the fragment
  form, also agrees 32/32 — `039349_12/45` is `FRAG_THRU` on both sides.
* **`michel_kind`: 24/32 (75 %), and 24/24 on the rows where they set it.**
  All eight differences are rows where they left the `— not set —` sentinel and
  I recorded an observation (`none` ×7, `detached dots` ×1 on `039349_26/18`).
* **Attribution: 154/210 objects on the effective group (73 %).**  The 56
  differences are three different things, and the tool now separates them:
  * **48** are `unassigned → delta / other` (41) and `unassigned → gamma` (7):
    the chain had no grouping for the object, they left it that way and I
    tagged it, which is the round's own instruction and not a disagreement.
  * **3 are genuine scanner-vs-scanner disagreements**, the only objects both
    of us tagged and tagged differently: `224013` (`039252_2/83`) they michel /
    I gamma — a 0.9 cm 9.6 ke/cm speck 30 cm out, perpendicular; and `225041`
    (`039252_3/74`) and `185007` (`039253_14/49`) they gamma / I delta / other,
    both sitting behind the stop beside the muon body (`cos_fwd` −0.57 and
    −0.86).
  * **5 are me overriding the chain where they left it**, which says something
    about the chain rather than about them — see below.
* **The five chain overrides are one story.**  On four items *both* of us call
  the track a non-stopper (`THRU` ×3, `FRAG_THRU` ×1) and the chain
  nevertheless carries **"the Michel object"** attached to it: `114002` on
  `039252_6/114`, `68011` on `039349_0/68`, `27016` on `039349_10/27`,
  `45020` on `039349_12/45` — each 1.1–2.5 cm, sitting *on* the fit end.  A
  track that does not stop has no Michel, so I tagged them muon / delta-other.
  The fifth is the mirror image and the most consequential row in this scan:
  on `039349_18/36` the chain types `36018` **muon**, and it is the Michel
  (§7).  These four-plus-one are worth an eye from whoever owns the Michel
  attachment: they are cases where the chain's own object typing survives a
  verdict that should have removed it.
* **Both of their pins reproduced, on the two rows they had pinned.**  Their
  two placed pins in `smx1` are on `039349_18/36` and `039349_26/40`, and both
  are pinned here.  On `039349_18/36` the slider snapped to the same chain
  point they used — `rr 9.56`, `moved_cm 8.32`, the same (x, y, z) to the
  centimetre.  On `039349_26/40` I landed one point further out (`rr 4.2`,
  moved 4.07 cm, against their `rr 3.0` and 2.88 cm), a 1.2 cm difference on a
  correction §7 calls good to no better than ±3 cm.  This scan pins a **third**
  row they had not scanned, `039349_67/78`, and that one came out of their
  review rather than out of the first pass (§7, §9).  In the live tag they have
  since moved the `039349_26/40` pin to `rr 0.60` and placed one on
  `039349_12/45` (§11).

**What this number is and is not.**  It is **not blind.**  The owner asked for
their 32 to be used as calibration, so their per-item labels were in front of
me before I scanned; treat 32/32 as a *consistency* check on the display, the
rubric and the harness, not as an independent benchmark of either scanner.
The 28 new items carry no such caveat.  A blind number is a separate round and
the harness supports it: run `shots`, hand the frames to a scanner who has not
seen `smx1`.

A second limit is inherited and applies to both tags: every row in `smx1` and
`smx1a` has `revealed_before_label: true`, so per doc pdhd/12 §13.2 these are
"the chain's reconstruction, reviewed by a physicist" — the chain's answer is
on screen from the first paint.

## 6. Five MESSY, where the owner used none

The owner's 32 contain no `MESSY`; five of the 28 new items are, and they are
one population, not five judgements:

`039349_28/52`, `039349_40/49`, `039349_46/58`, `039349_75/72`, `039349_81/54`

Each is an electromagnetic blob or a broken sparse knot rather than a track.
The numbers, read off each item's own object table:

| item | objects | farthest object from the stop | objects behind the stop | the chain's own `muon` segments, dQ/dx |
|---|---:|---:|---:|---|
| `039349_28/52` | 26 | 65.5 cm | 26/26 | 11.1–59.8 ke/cm, scattered over 0.20–1.09 MIP |
| `039349_40/49` | 21 | 61.2 cm | 14/21 | 1.4–22.7 ke/cm (**0.02–0.41 MIP**) |
| `039349_46/58` | 19 | 35.5 cm | 11/19 | 8.9–45.4 ke/cm (0.16–0.83 MIP) |
| `039349_75/72` | 17 | 88.8 cm | 17/17 | 3.3–34.4 ke/cm (0.06–0.62 MIP) |
| `039349_81/54` | 53 | 51.4 cm | 51/53 | 4.2–24.3 ke/cm (0.08–0.44 MIP) |

Most of the objects are the chain's own pdg-11 shower pieces and they sit
**behind** the fit end, not past it.  On three of the five the spine itself
carries segments below a tenth of MIP — 1374 and 2202 e/cm on `039349_40/49`,
3280 on `039349_75/72`, 4222 on `039349_81/54`.  MCS returns `amb 1.00` on four
of the five (`039349_46/58` returns no MCS at all).  These are not stopping
muons with messy neighbourhoods; the fitted "muon" is not a muon.

That they land only in the owner's unscanned half is worth a look before the
sample is used for a rate: it may be a real feature of where their scan stopped
(they worked the sheet in order and this is the tail), or it may be that they
would have called some of these `THRU`.  Either way `MESSY` is unscored, so
this shows up as a 5/60 unjudgeable rate on tranche 1 rather than a bias.

## 7. The three stopping points the fit got wrong

3 of 60 pins moved, still consistent with doc pdhd/12's 97.7 % figure.  Two of
the three are the owner's own two; the third (`039349_67/78`) came out of their
review of 2026-09-09 (§9) and is the reason this section is no longer titled
"two".  **The signature is one signature**, and the owner named the mechanism
behind it when they looked at `039349_26/40`:

> *"there is might be a small gap between the stopping STM and the Michel
> electron leading to low dQ/dx fit"*

That is what the profile shows in all three: the fit does not stop where the
muon does, it carries on across the gap into the Michel, and the interpolated
points across the gap carry little charge.  So the thing to look for is **the
collapse after the peak, not the height of the peak** — dQ/dx rising to a real
Bragg maximum several centimetres before the fit's last point and then falling
back to a fraction of MIP.  Two of the three rows the chain calls `no_bragg`
for exactly that reason: it measures the flat tail past the true stop.

**`039349_18/36`, pin snapped to residual range 9.56 cm, 8.32 cm off the fit
end.**  The profile runs 5e4
on the plateau, climbs through 7–12e4 at 12–20 cm, **peaks at 1.05–1.45e5
between 5 and 12 cm, then collapses to 1–3e4 over the last 5 cm**.  A muon's
Bragg peak is its last centimetre, so the fit runs ~9 cm past the stop.  What it
runs into is object `36018` — 9.0 cm at 2.5e4 e/cm (0.45 MIP) leaving the peak
at a large angle, which **the chain types `muon`**.  A muon cannot fall from
its own Bragg peak to half MIP and keep going: that is the Michel, and it is
tagged so.  The chain calls the whole item `no_bragg`; the peak is there, just
not where its last point is.  The slider snapped to the same chain point the
owner had used — same (x, y, z) to the centimetre, same `moved_cm` 8.32 —
which is as close to an independent reproduction as a snapping control allows.
**And the chain's typing of `36018` is the one thing in this scan the owner
also left alone**: their row carries no tag on it, so the chain's `muon`
stands in `smx1` and `michel` in `smx1a` (§5).

Doc [pdvd/54](54_michel-lost-at-the-stop-two-mechanisms.md) §1, written the same
day from the owner's report on this item, has the mechanism behind the picture:
`TaggerCheckSTM::find_first_kink` passes every geometry gate at the true stop
(96.0° reflection angle) and fails both charge gates — `sum_bQ` 0.09 MIP against
a 0.6 bar, the arm 8.36 cm against a 10 cm bar — so it returns the no-kink
sentinel, the stop falls through to the trajectory's far end, and the chain is
built through `36018` with `chain_role 1`.  The two arrive at the same object
from opposite ends: that doc from the tagger's own arithmetic, this scan from
the dQ/dx profile and the 3-D picture with the label directory empty.  Its §1
quotes the PR's own fit of `36018` at 0.45 MIP — the number read off the
display here.

**`039349_26/40`, pin snapped to residual range 4.2 cm, 4.07 cm off the fit
end.**  The same signature, much smaller: the profile peaks at 9.2e4 five to
eight centimetres before the fit end and falls to ~6e4 over the last two.  At
this contrast the correction is good to no better than ±3 cm, and the owner's
own pin sits one chain point closer in (`rr 3.0`, 2.88 cm) — inside that.

**`039349_67/78`, pin moved to residual range 4.8 cm, 3.57 cm off the fit end
— the owner's correction of 2026-09-09**, in their words: *"the S78013 is
likely part of a Michel electron, and the end point should be at S78010."*  The
first pass had read the rise as running to the fit's last point and called the
row `STM_ONLY`.  It does not: dQ/dx climbs off a 5–6e4 plateau to 0.9–1.15e5
between +3 and +12 cm and the **last ~4 cm collapse to 1–4.5e4**.  What the fit
runs into is `S78013` — 8.8 cm at 1.9e4 e/cm (0.35 MIP), spanning 0 to 4.8 cm
from the old end, typed **muon** by the chain — and a muon at its own Bragg peak
cannot continue at a third of MIP.  The row is now `STM_MICHEL` / `both`:
`78013` michel, and `225015` (the chain's own 0.3 cm pdg-11 seed, 3.9 cm from
the old end and so ~0.8 cm from the new stop) michel with it.  **This is the
second instance of the `039349_18/36` failure — the chain typing the Michel as
the muon's own last segment — and it was found by the owner, not by the first
pass.**  Two in 60 is a rate worth carrying into tranche 2.

Both were judged from frames taken with an empty label directory, so neither
pin was on screen — but their `moved_cm` values were known to me from the
calibration step, so §5's caveat applies here too.

**This is a reportable defect in the fit, not in the scan.**  Three of 60 is
small, but on two of them the chain's own `no_bragg` verdict is a *consequence*
of the overshoot — it measures the flat tail past the real stop and concludes
there is no peak — and the third is rejected on `shape_flat` for the same
reason.  Anything that trims a fit end on falling dQ/dx would recover all
three.  Doc [pdvd/54](54_michel-lost-at-the-stop-two-mechanisms.md) §1 has the
upstream cause for `039349_18/36`; whether `find_first_kink` fails the same way
on `039349_67/78` is not checked here.

## 8. Open items, found and not fixed

1. **`Zoom to object` does nothing to the three projection panels in a
   browser** (`stm_michel_viewer.py:1591`).  The toggle reaches the server
   (`cam3.seq` bumps) and `render` does assign the ranges — driving the same
   app in process through `runpy`, the side panel goes from (−19.2, 318.4) to
   (199.4, 318.0).  In a browser the ranges never move, from a real DOM click
   as much as from an assignment, and a *client* assignment is reverted within
   about a second.  Root cause: `figure(...)` is called without `x_range=` /
   `y_range=` (`:455`), so these panels carry **`DataRange1d`**, whose
   start/end are an output of auto-ranging and not an input — and what it
   auto-ranges over includes the full-detector boundary box drawn at `:489`,
   so it always lands on the whole detector.  The nine measurement panels take
   their server-set ranges correctly, and they are built with explicit shared
   ranges (`:782`, `:803`) — that is the control.  **The fix is to give the
   three panels real `Range1d`s; it is not made here.**  The scan did not need
   them: containment is what full extent is for, and the zooming was done in
   3-D, whose ranges are real `Range1d`.
2. **The alphabet has no "unrelated"** (§3).  `delta / other` carries 198 of
   465 tags because it is doing two jobs.
3. **Two of the owner's tags name segment ids their own row's
   `pf_chain_group` does not carry** — `309009` on `039252_15/91` and `226014`
   on `039252_2/83` — tags written against an earlier arm.  They are reported
   by `compare_scan_tags.py` rather than silently scored.  (An unfitted-cluster
   row, keyed `C<id>`, is absent from `pf_chain_group` **by construction** —
   that carries fitted segments only — so the tool lists those separately and
   does not call them stale.  One exists: `C36` on `039252_6/114` in `smx1a`.)
4. **The object table re-sorts on every tag** (`stm_michel_viewer.py:2040`,
   `object_rows` sorts by `GROUP_ORDER` then id), and a DataTable selection has
   no handle but the row index.  So a tag applied from an index computed before
   the repaint lands on a *different* object.  The harness hit this hard: on
   `039253_14/49` it scrambled four of eight rows, and four corrective passes
   would not converge because each pass mis-tagged about as many rows as it
   fixed.  It is fixed in the harness (address a row only from a table read
   that two consecutive polls agree on, then poll until the row carries the
   tag), but the underlying behaviour is the display's, and a scanner clicking
   quickly down a long list can be bitten by the same re-sort.  Worth
   considering a stable sort, or a selection addressed by object id.
5. **`score_stm_michel_scan.py`'s pin percentiles are wrong on a small
   sample** (`:166-169`): `p90` indexes `int(0.9 * (n - 1))`, which on n = 2
   is element 0, so it printed `median 8.32 cm, p90 4.07 cm, max 8.32 cm` —
   a p90 below the median.  The two values themselves (4.07 and 8.32) are
   right; only the order statistics are.  Reported, not fixed — it is an
   existing tool and not what this round changes.
6. **`039349_38/60`** ends abruptly 110 cm inside the anode with no Bragg, no
   dead channels at the end, and no charge past it.  Recorded `THRU`, but the
   track runs only 24° off the drift axis — the hardest case for the 2-D charge
   attribution the profile is built from — and MCS returns 1076 MeV against
   293 MeV from range.  Worth an eye.

## 9. The owner's review of the ten uncertain rows (2026-09-09)

Ten of the 60 were recorded at `medium` confidence and put to the owner on the
display, on :5017, serving `smx1a`.  They went through all ten.  **Nine stand;
one is corrected**, and the correction is the interesting one.

| scan | item | my call | the owner |
|---:|---|---|---|
| 474 | `039349_66/78` | STM_ONLY / detached dots | ✓ *"474 is OK, the Bragg peak is not as consistent, but I feel the scan is OK"* |
| 329 | `039349_38/60` | THRU | ✓ *"329 and 194 is clearly not STM"* — and this is the row the chain flags `is_stm = 1`, so the chain's one false positive is now confirmed by both scanners |
| 194 | `039349_12/45` | FRAG_THRU | ✓ *"clearly not STM"* |
| 266 | `039349_26/40` | STM_MICHEL / both, pin back 4 cm | ✓ *"266 looks good, I feel there is might be a small gap between the stopping STM and the Michel electron leading to low dQ/dx fit"* — the mechanism, now in §7 |
| 529 | `039349_76/75` | STM_ONLY | ✓ *"529 probably OK"* |
| 139 | `039253_2/89` | STM_MICHEL / attached | ✓ *"139 looks OK"* |
| 498 | `039349_7/67` | STM_MICHEL / attached | ✓ *"498 Looks good"* |
| 285 | `039349_3/46` | STM_MICHEL / attached | ✓ *"285 Looks good"* |
| 270 | `039349_27/41` | STM_MICHEL / attached | ✓ *"270 looks good"* |
| 481 | `039349_67/78` | ~~STM_ONLY / detached dots~~ | **corrected** — *"the S78013 is likely part of a Michel electron, and the end point should be at S78010"*.  Now `STM_MICHEL` / `both` with the pin back 4.8 cm; see §7 |

**What that is worth as a number, and what it is not.**  9 of 10 confirmed is
9 of the 10 rows I was *least* sure of — it is not a 90 % accuracy figure for
the scan, because the 50 `high` rows were not reviewed.  What it does say is
that the medium bucket was drawn around the right rows: the one correction came
out of it, and it came out of the row whose evidence sentence itself said the
Bragg ran to the last point when it does not.

**And it is a rate, not an anecdote.**  The corrected row is the *second*
instance in 60 of the chain typing the Michel as the muon's own last segment
(`039349_18/36` is the first, doc pdvd/54 §1).  One was found by the owner's
scan, one by this one, and neither by the chain — which is the argument for
scanning tranche 2 rather than trusting the flag.

## 10. What this does not do

No knob moves, no configuration changes, no C++ is touched.  The scan is a
record; the numbers in §4 are the input to whoever sets the `shape_flat` /
`no_bragg` cuts, and §7 is the input to whoever trims the fit end.  Tranche 2
(509 items) is untouched, and PDHD is still unscanned by design (doc pdhd/12
§12).

## 11. Gates

The viewer is not modified in this round — `stm_michel_viewer.py` is unchanged
since `67a0d02b`, before this scan started — so any move in its own tests would
be the harness's fault.  Run after the scan, all green:

| gate | result |
|---|---|
| `selftest_stm_michel_scan.py` (both detectors) | **81314 checks passed, 0 failed** |
| `selftest_pin_persistence.py --det pdvd` / `--det pdhd` | **34/34** and **27/27** (check 10 skipped on PDHD: no `smx1` there) |
| `selftest_smx3d_browser.py --det pdvd --port 5091` / `--det pdhd --port 5093` | **102/102** each |
| `verify_scan_record.py --det pdvd --tag smx1a --record …` | 60/60 rows; every verdict, kind and tag matches, and it names the **two pins the owner has since moved in the live tag** — see below |
| `score_stm_michel_scan.py --det pdvd --tag smx1a` | clean (it refuses an unknown `label`), §4 |
| `compare_scan_tags.py --det pdvd --a smx1 --b smx1a` | §5 |
| the owner's `smx1` | byte-identical, `sha256 8fc76b3368c3f6fb473b9ed3debe0923c6c1a95c9e74a38cac9c93ec4b3e9bd1`, 28310 bytes, unchanged throughout |
| :5017 | serving `smx1a` since 2026-09-09 05:06 at the owner's request (it served `smx1` during the scan; the harness never used it, then or now — it runs on its own scratch port) |

**`smx1a` is a live tag, and the record is this scan only.**  The owner edits it
through the app while validating, so `labels.json` can hold placements this
document does not describe.  As of the run above it carries **two pins that are
not in the scan record**, both made in their own session on 2026-09-09:
`039349_12/45` at `rr 58.78` (the record asks for none) and `039349_26/40` at
`rr 0.60` (the record asks for `rr 4.00`, §7).  `verify_scan_record.py` names
exactly those two and nothing else, which is the intended behaviour: the record
is what *this scan* found, the file is what the tag currently holds, and the
tool is what keeps the difference visible instead of silent.  The rows are
marked **†** in §12.

## 12. The 60 rows (tranche 1)

`‡` marks the 32 the owner had already scanned in `smx1`.  `chain` is the
chain's own verdict: `STM` when `is_stm = 1`, otherwise its reject names.
`mu/mi/ga/ot` counts the tags: muon / michel / gamma / delta-other.  `owner` is
their review of 2026-09-09 (§9): ✓ confirmed, **corrected** where it moved,
blank where it was not reviewed.  Verdict, kind, tags and pin are read out of
`labels.json`; a pin marked **†** is one the file holds and this scan did not
place (§11).

| scan | item | len | chain | my verdict | kind | conf | owner | mu/mi/ga/ot | pin |
|---:|---|---:|---|---|---|---|---|---|---|
| 4 ‡ | `039252_0/77` | 126 | STM | **STM_ONLY** | detached dots | high |  | 1/0/1/0 | - |
| 27 ‡ | `039252_15/77` | 113 | STM | **STM_MICHEL** | attached | high |  | 1/2/0/0 | - |
| 30 ‡ | `039252_15/91` | 180 | STM | **STM_MICHEL** | both | high |  | 1/2/2/0 | - |
| 34 ‡ | `039252_16/88` | 305 | STM | **STM_MICHEL** | attached | high |  | 1/1/0/0 | - |
| 47 ‡ | `039252_2/83` | 30 | STM | **STM_MICHEL** | both | high |  | 1/3/3/0 | - |
| 52 ‡ | `039252_3/40` | 265 | STM | **STM_MICHEL** | attached | high |  | 1/1/0/0 | - |
| 55 ‡ | `039252_3/74` | 88 | STM | **STM_MICHEL** | both | high |  | 5/1/1/15 | - |
| 66 ‡ | `039252_6/114` | 225 | no_bragg,shape_flat | **THRU** | none | high |  | 4/0/0/4 | - |
| 81 ‡ | `039252_9/52` | 28 | no_bragg,shape_flat | **STM_MICHEL** | both | high |  | 1/3/4/0 | - |
| 112 ‡ | `039253_13/102` | 630 | STM | **STM_ONLY** | detached dots | high |  | 6/0/1/0 | - |
| 115 ‡ | `039253_14/49` | 269 | STM | **STM_MICHEL** | both | high |  | 1/2/4/1 | - |
| 117 ‡ | `039253_14/110` | 380 | STM | **STM_ONLY** | detached dots | high |  | 4/0/5/2 | - |
| 119 ‡ | `039253_15/36` | 322 | STM | **STM_ONLY** | none | high |  | 1/0/0/0 | - |
| 124 ‡ | `039253_15/105` | 578 | no_bragg,shape_flat | **STM_MICHEL** | both | high |  | 5/1/3/2 | - |
| 136 | `039253_2/34` | 22 | STM | **STM_MICHEL** | attached | high |  | 1/2/0/0 | - |
| 139 ‡ | `039253_2/89` | 257 | STM | **STM_MICHEL** | attached | medium | ✓ | 3/3/0/0 | - |
| 141 ‡ | `039253_2/117` | 71 | STM | **STM_MICHEL** | both | high |  | 1/2/1/0 | - |
| 144 ‡ | `039253_3/66` | 162 | STM | **STM_MICHEL** | attached | high |  | 3/1/0/1 | - |
| 152 ‡ | `039253_5/107` | 26 | STM | **STM_ONLY** | detached dots | high |  | 1/0/2/0 | - |
| 170 ‡ | `039253_8/59` | 281 | STM | **STM_MICHEL** | both | high |  | 2/2/2/1 | - |
| 171 ‡ | `039253_8/62` | 275 | STM | **STM_MICHEL** | both | high |  | 7/2/3/5 | - |
| 178 ‡ | `039349_0/68` | 279 | no_bragg,shape_flat | **THRU** | none | high |  | 4/0/0/3 | - |
| 181 ‡ | `039349_10/27` | 238 | shape_flat | **THRU** | none | high |  | 8/0/0/5 | - |
| 194 ‡ | `039349_12/45` | 120 | profile_sparse | **FRAG_THRU** | none | medium | ✓ | 5/0/0/1 | rr 58.8 † |
| 210 ‡ | `039349_15/59` | 254 | no_bragg,shape_flat | **THRU** | none | high |  | 1/0/0/0 | - |
| 221 ‡ | `039349_18/36` | 147 | no_bragg,shape_flat | **STM_MICHEL** | attached | high |  | 7/1/0/0 | rr 9.6 |
| 229 ‡ | `039349_2/38` | 71 | shape_flat | **STM_ONLY** | none | high |  | 4/0/0/3 | - |
| 241 ‡ | `039349_21/51` | 199 | no_bragg,shape_flat | **STM_MICHEL** | both | high |  | 3/1/2/1 | - |
| 249 ‡ | `039349_22/64` | 477 | STM | **STM_ONLY** | detached dots | high |  | 7/0/1/1 | - |
| 261 ‡ | `039349_25/47` | 243 | STM | **STM_ONLY** | none | high |  | 2/0/0/1 | - |
| 264 ‡ | `039349_26/18` | 74 | no_bragg,shape_flat | **STM_ONLY** | detached dots | high |  | 3/0/1/1 | - |
| 266 ‡ | `039349_26/40` | 27 | no_bragg,shape_flat | **STM_MICHEL** | both | medium | ✓ | 1/1/2/0 | rr 0.6 † |
| 270 ‡ | `039349_27/41` | 71 | stop_near_boundary | **STM_MICHEL** | attached | medium | ✓ | 1/1/0/0 | - |
| 273 | `039349_28/36` | 348 | STM | **STM_MICHEL** | both | high |  | 5/4/3/0 | - |
| 275 | `039349_28/52` | 92 | shape_flat,plateau_off_mip | **MESSY** | none | high |  | 0/0/0/26 | - |
| 281 | `039349_29/45` | 232 | shape_flat | **STM_MICHEL** | both | high |  | 1/1/5/0 | - |
| 285 | `039349_3/46` | 17 | shape_flat | **STM_MICHEL** | attached | medium | ✓ | 1/1/0/0 | - |
| 314 | `039349_35/62` | 220 | STM | **STM_MICHEL** | attached | high |  | 1/3/0/0 | - |
| 317 | `039349_36/41` | 52 | STM | **STM_MICHEL** | attached | high |  | 3/2/0/0 | - |
| 329 | `039349_38/60` | 119 | STM | **THRU** | none | medium | ✓ | 1/0/0/0 | - |
| 337 | `039349_4/47` | 45 | no_bragg,shape_flat | **THRU** | none | high |  | 2/0/0/0 | - |
| 342 | `039349_40/49` | 56 | plateau_off_mip | **MESSY** | none | high |  | 0/0/0/21 | - |
| 352 | `039349_43/54` | 87 | STM | **STM_MICHEL** | attached | high |  | 1/2/1/0 | - |
| 368 | `039349_46/58` | 30 | shape_flat,profile_sparse | **MESSY** | none | high |  | 0/0/0/19 | - |
| 376 | `039349_48/49` | 186 | STM | **STM_ONLY** | detached dots | high |  | 1/0/2/0 | - |
| 410 | `039349_54/54` | 181 | STM | **STM_MICHEL** | attached | high |  | 3/1/2/0 | - |
| 436 | `039349_59/61` | 267 | STM | **STM_MICHEL** | attached | high |  | 1/1/1/0 | - |
| 444 | `039349_61/18` | 99 | STM | **STM_MICHEL** | attached | high |  | 2/1/0/0 | - |
| 460 | `039349_63/48` | 365 | no_bragg,shape_flat,stop_near_boundary | **THRU** | none | high |  | 2/0/0/5 | - |
| 470 | `039349_64/71` | 257 | STM | **STM_MICHEL** | both | high |  | 2/2/1/1 | - |
| 474 | `039349_66/78` | 209 | no_bragg,shape_flat | **STM_ONLY** | detached dots | medium | ✓ | 5/0/3/3 | - |
| 481 | `039349_67/78` | 84 | shape_flat | **STM_MICHEL** | both | medium | **corrected** | 1/2/1/0 | rr 4.8 |
| 498 | `039349_7/67` | 58 | STM | **STM_MICHEL** | attached | medium | ✓ | 4/2/1/0 | - |
| 514 | `039349_72/65` | 267 | STM | **STM_MICHEL** | attached | high |  | 3/2/0/0 | - |
| 524 | `039349_75/72` | 163 | shape_flat,profile_sparse | **MESSY** | none | high |  | 0/0/0/17 | - |
| 529 | `039349_76/75` | 181 | STM | **STM_ONLY** | none | medium | ✓ | 2/0/0/1 | - |
| 554 | `039349_81/54` | 105 | shape_flat,plateau_off_mip | **MESSY** | none | high |  | 0/0/0/53 | - |
| 558 | `039349_82/52` | 103 | STM | **STM_ONLY** | none | high |  | 3/0/0/5 | - |
| 564 | `039349_83/60` | 173 | STM | **STM_MICHEL** | attached | high |  | 1/4/0/0 | - |
| 568 | `039349_9/47` | 231 | STM | **STM_MICHEL** | both | high |  | 1/4/2/0 | - |

### Per-item evidence

**`039252_0/77`** (scan 4, 126 cm) — **STM_ONLY** / detached dots / high confidence  
126 cm, enters 0.2 cm from the y face, stops 35.2 cm from the z wall. Bragg to 1.3e5 on the muon curve. Nothing attached at the stop -- no arm on the profile at all. One 0.6 cm two-point dot 27 cm out, forward and isolated, which the chain already types a capture gamma. Dots seen, judged gamma, so STM_ONLY.

**`039252_15/77`** (scan 27, 113 cm) — **STM_MICHEL** / attached / high confidence  
113 cm, enters 0.5 cm from the z face, stops 79 cm inside. Bragg to 1.6e5, straight up the muon reference curve. A contiguous 17.8 cm two-piece arm leaves the stop forward (cos_fwd 0.41/0.46) at 4.6-5.5e4 e/cm with profile charge to -20 cm -- a full Michel; the second piece starts exactly where the first ends, so it is one object, not a detached dot.

**`039252_15/91`** (scan 30, 180 cm) — **STM_MICHEL** / both / high confidence  
181 cm, enters at the anode face, stops 49.8 cm from the z wall. Bragg to 1.2e5 on the muon curve. A 14 cm two-piece arm covers 0-13.8 cm past the stop (cos_fwd 0.59/0.82) with dense profile charge to -17 cm. Two isolated specks further out, 33.5 cm (4.8e4 e/cm) and 40.4 cm (7.5e3), both forward and clear of the muon body: gamma.

**`039252_16/88`** (scan 34, 305 cm) — **STM_MICHEL** / attached / high confidence  
305 cm, enters 0.3 cm from the z face, stops 94 cm inside. Bragg to 1.35e5 on the muon curve, MCS amb 0.00. An 8.2 cm arm at 4.3e4 e/cm leaves the stop forward (cos_fwd 0.41) with profile charge to -10 cm. Nothing else drawn.

**`039252_2/83`** (scan 47, 30 cm) — **STM_MICHEL** / both / high confidence  
30 cm, enters 0.3 cm from the anode face, stops 27 cm inside. Bragg to 1.2e5 on the muon curve. A three-piece arm covers 0-9.1 cm past the stop with profile charge to -10 cm. Three isolated specks at 16.4, 30.0 and 45.6 cm, all past the stop and clear of the 30 cm muon body: gamma. Note 31 blobs from another flash are hidden here, the most in this tranche, so the neighbourhood is busy.

**`039252_3/40`** (scan 52, 265 cm) — **STM_MICHEL** / attached / high confidence  
265 cm, enters 10.2 cm from the y face, stops 73.8 cm from the z wall. Bragg to 1.3e5 on the muon curve, MCS amb 0.00. A 14.3 cm arm at 3.9e4 e/cm leaves the stop sideways-back (cos_fwd -0.57) with profile charge to -12 cm; the charge and range are a Michel's, and at 14 cm it is far too long to be a delta from a stopping muon.

**`039252_3/74`** (scan 55, 88 cm) — **STM_MICHEL** / both / high confidence  
88 cm, enters 0.1 cm from the anode face, stops 42.2 cm inside. Bragg to 1.1e5 on the muon curve. A 12.2 cm arm at 2.7e4 e/cm leaves the stop (cos_fwd -0.48) with profile charge to -12 cm. One 0.1 cm speck 36 cm out and FORWARD (cos_fwd 0.32): gamma. The other fourteen objects all sit 20-67 cm BACK along the muon body at cos_fwd -0.83 to -0.99, most of them under 0.2 MIP (778 to 13010 e/cm) -- body activity beside the track, which is the owner's own not-the-Michel case, so delta / other. That includes 225041 (7.2 cm, 4.9e4 e/cm, 24-29 cm out at cos_fwd -0.57), the one substantial piece; it is behind the stop, not past it.

**`039252_6/114`** (scan 66, 225 cm) — **THRU** / none / high confidence  
225 cm whose fit ends 148 cm from every face -- it cannot have exited -- and whose dQ/dx is FLAT on the 5-6.5e4 MIP plateau right to the last point, with no rise at all. A stopping muon cannot end without a Bragg peak, so this fit end is not a stop. 114002 is 1.7 cm sitting 0-1.7 cm STRAIGHT AHEAD (cos_fwd 0.91) at 4.4e4 e/cm: the track carrying on, so muon rather than Michel. A separate 157.7 cm cluster (C36, 290 points) sits 47-60 cm away and shows in the wide view as a faint trail leaving at a large angle -- tagged delta / other because it is a different object, not this one's continuation.

**`039252_9/52`** (scan 81, 28 cm) — **STM_MICHEL** / both / high confidence  
28 cm, enters 0.6 cm from the z face, stops 9.5 cm from the anode face -- close, but the muon is only 95 MeV and its whole length sits above the MIP curve, ending at 1.15e5. A three-piece arm covers 0-14.5 cm past the stop, all forward (cos_fwd 0.49-0.79), with profile charge to -16 cm. Four small dots at 18.6-32 cm, every one forward (cos_fwd 0.47-0.94) and clear of the short muon body: gamma.

**`039253_13/102`** (scan 112, 630 cm) — **STM_ONLY** / detached dots / high confidence  
630 cm -- the longest in the tranche -- entering 0.2 cm from the anode face and stopping 75.8 cm from the y wall. The profile climbs the muon reference curve to 1.65e5, as clean a Bragg as this sample has, and MCS amb 0.00. NOTHING is attached at the stop. One 0.6 cm two-point dot sits 33 cm out at 2.7e4 e/cm, essentially perpendicular to the muon (cos_fwd -0.18) and therefore ~33 cm clear of the body line: isolated, so gamma. Dot seen, judged gamma, so STM_ONLY.

**`039253_14/49`** (scan 115, 269 cm) — **STM_MICHEL** / both / high confidence  
269 cm, enters 2.2 cm from the y face, stops 104 cm from the z wall. Bragg to 1.25e5 on the muon curve. A contiguous 15 cm two-piece arm covers 0-12.1 cm past the stop with profile charge to -14 cm. Four specks at 34.6, 36.4, 49.0 and 55.0 cm are all near-perpendicular or forward and well clear of the body: gamma. 185007 is different -- 14.5 cm out at cos_fwd -0.86, i.e. 12 cm BACK along the muon and 7 cm off it, which is the owner's own 'close to the track and backward' case, so delta / other.

**`039253_14/110`** (scan 117, 380 cm) — **STM_ONLY** / detached dots / high confidence  
380 cm, enters at the anode face, stops 59.2 cm from the z wall. Bragg to 1.27e5 on the muon curve, MCS amb 0.06. NOTHING attached at the stop -- the profile has no arm at all. Five small dots sit 18.6-55.7 cm out, forward or perpendicular and clear of the body; the chain already types three of them capture gammas. 110007 and 110009 lie 245 and 330 cm back ON the muon body line (cos_fwd -0.98): body activity, delta / other.

**`039253_15/36`** (scan 119, 322 cm) — **STM_ONLY** / none / high confidence  
322 cm, enters 15.8 cm from the z face, stops 21.2 cm from the anode face. The profile climbs the muon reference curve to 1.58e5 -- an unmistakable Bragg -- and MCS amb 0.01. The display draws exactly ONE object: nothing past the stop, no arm, no dots, nothing on the negative side of the profile at all.

**`039253_15/105`** (scan 124, 578 cm) — **STM_MICHEL** / both / high confidence  
578 cm, enters at the anode face, stops 106 cm from the z wall. The chain calls this no_bragg, but the profile does rise -- 5.5e4 plateau to 9e4 over the last 3 cm. A 9.5 cm arm at 5.0e4 e/cm leaves the stop with profile charge to -10 cm. Three specks at 33, 54.7 and 55.2 cm are forward or perpendicular and clear of the body: gamma. 105009 and 105013 sit 242 and 457 cm back ON the body line: delta / other.

**`039253_2/34`** (scan 136, 22 cm) — **STM_MICHEL** / attached / high confidence  
22.4 cm, entry 0.5 cm from the z face, stop 10.7 cm inside it. Clear Bragg rise, 6e4 at 20 cm to 1.0e5 at the last cm, on the muon reference curve. A 12.8 cm two-piece arm leaves the stop at 43 deg at MIP dQ/dx -- a muon at its own Bragg peak cannot continue at MIP, so the arm is a second particle, and 12.8 cm is the right range for a ~31 MeV electron. No dead region at the stop in any plane.

**`039253_2/89`** (scan 139, 257 cm) — **STM_MICHEL** / attached / medium confidence  
*owner review: CONFIRMED -- "139 looks OK"*  
257 cm, enters at the anode face, stops 118 cm from the z wall. The Bragg is modest -- 4.5e4 plateau to 8.5e4 -- but the last chain segment runs 7.0e4 e/cm against 4.4e4 for the body, so it is real. The 3-D view at the stop shows a compact spray rather than a single arm: 89014 (7.1 cm, 5.3e4) plus 89009 and 89015, all of them within 8 cm of the stop. Their cos_fwd is negative, but at that distance direction says nothing -- a Michel is emitted isotropically, and the owner's 'close and backward' exclusion is about activity beside the muon BODY, which none of these is (the chain types them pdg 11 shower, not body-excluded). All three tagged michel.

**`039253_2/117`** (scan 141, 71 cm) — **STM_MICHEL** / both / high confidence  
71 cm, enters 0.2 cm from the z face, stops 19.9 cm inside. Bragg to 1.1e5 on the muon curve. A contiguous 8.4 cm two-piece arm covers 0-6.8 cm past the stop (cos_fwd 0.42/0.66) with profile charge to -8 cm. A separate 5.4 cm piece at 5.7e4 e/cm sits 26-29 cm out, perpendicular and clear of the body: gamma.

**`039253_3/66`** (scan 144, 162 cm) — **STM_MICHEL** / attached / high confidence  
162 cm, enters 0.6 cm from the y face, stops 83 cm from the z wall. The profile climbs the reference curve to 1.6e5 -- textbook Bragg -- and the last chain segment runs 8.0e4 e/cm against 4.9e4 for the body. A 15 cm arm at 5.0e4 e/cm leaves the stop forward (cos_fwd 0.62) with profile charge to -15 cm. 66008 is 3.6 cm of shower charge lying ON the muon body line (cos_fwd -1.0) 10-13 cm back: a delta ray beside the track, not part of the decay, so delta / other.

**`039253_5/107`** (scan 152, 26 cm) — **STM_ONLY** / detached dots / high confidence  
26 cm, enters 0.2 cm from the anode face, stops 23 cm inside. Short and low energy (89 MeV) so the whole track sits above MIP, and it still climbs the reference curve to 1.3e5. NOTHING attached at the stop. Two dots at 24.4 and 31.7 cm, both clear of the 26 cm body -- the chain already types the far one a capture gamma. Dots seen, judged gamma, so STM_ONLY.

**`039253_8/59`** (scan 170, 281 cm) — **STM_MICHEL** / both / high confidence  
281 cm, enters 1.4 cm from the anode face, stops 105 cm from the y wall. Bragg to 1.15e5 on the muon curve. A 9.8 cm arm at 5.1e4 e/cm leaves the stop forward (cos_fwd 0.61) with profile charge to -11 cm, and a further 0.5 cm piece the chain also calls Michel sits 16 cm out on the same side. Two dots at 40 and 51 cm, perpendicular and forward, clear of the body: gamma. 59005 lies 45-50 cm back ON the body line at 0.1 MIP: delta / other.

**`039253_8/62`** (scan 171, 275 cm) — **STM_MICHEL** / both / high confidence  
275 cm, enters 1.1 cm from the z face, stops 70.9 cm from the anode face. Bragg to 1.07e5 on the muon curve, MCS amb 0.02. A short two-piece arm covers 0-4.1 cm past the stop (6.6e4 and 2.5e4 e/cm) with profile charge to -3 cm -- a low-energy Michel. Three dots at 22.5, 30.6 and 31.2 cm, clear of the body: gamma. Five further objects lie 38-220 cm back along the body line (cos_fwd -0.96 to -1.0), including a 59 cm pdg-4 piece: delta / other.

**`039349_0/68`** (scan 178, 279 cm) — **THRU** / none / high confidence  
279 cm whose fit ends 61 cm from every face, and whose dQ/dx is FLAT on the 5e4 MIP plateau to the very last point with no rise at all -- a stopping muon cannot do that. MCS returns 3243 MeV against 644 MeV from range (amb 0.96), which is what a fit through a track that does not end there looks like. 68009 is 1.6 cm sitting straight ahead of the fit end (cos_fwd 0.87): the track carrying on, so muon. With no stop there is no Michel, so 68011 and the two shower pieces 200 cm back are delta / other.

**`039349_10/27`** (scan 181, 238 cm) — **THRU** / none / high confidence  
238 cm whose fit ends 139 cm from every face -- the deepest end in this tranche -- with dQ/dx FLAT on the 5-6e4 plateau to the last point and no rise. A muon that stops 139 cm inside the detector must show a Bragg peak; this one shows none, so the fit end is not the track's end. 27016 is 1.1 cm at the stop pointing 48 deg off the muon line, too little to call anything; the four shower pieces lie 197-211 cm back ON the body line. All delta / other.

**`039349_12/45`** (scan 194, 120 cm) — **FRAG_THRU** / none / medium confidence  
*owner review: CONFIRMED -- "329 and 194 is clearly not STM"*  
*the drawn cluster is two disconnected pieces with a ~22 cm gap; the full object cannot be judged from what is drawn*  
The wide 3-D view shows TWO disconnected pieces with a clear gap, and the profile has a matching 22 cm hole between 20 and 42 cm. So this is a fragment, and the FRAG buttons are what that is for. On the fragment itself the evidence for a stop is weak: the profile is sparse, reaches 9.5e4 at the end against a 1.6e5 reference, and both ends sit close to the same z face (16.9 and 19.0 cm). I record the full object as a through-goer, at medium confidence -- with a 22 cm hole in the middle this is the row where FRAG_STM_ONLY is the live alternative. 45020, 2.5 cm at 7.6e4 e/cm pointing straight ahead (cos_fwd 0.87), reads as the track carrying on: muon.

**`039349_15/59`** (scan 210, 254 cm) — **THRU** / none / high confidence  
254 cm whose fit ends 112 cm from every face, dQ/dx flat at 4-6e4 to the last point with no rise, and MCS returning its 4000 MeV ceiling at amb 1.00 against 586 MeV from range. The display draws ONE object and nothing at all past the end. No Bragg and no decay activity is the owner's TGM case.

**`039349_18/36`** (scan 221, 147 cm) — **STM_MICHEL** / attached / high confidence  
*the fit OVERSHOOTS the stop by ~9 cm: the Bragg peak is at residual range 8-12 cm and the last 9 cm is the Michel; pin moved back to rr 9.5*  
147 cm, enters 0.4 cm from the anode face, ends 52 cm from the y wall. The chain calls it no_bragg -- and the peak is there, just not where the fit's last point is. The profile runs 5e4 on the plateau, climbs through 7-12e4 at 12-20 cm, PEAKS at 1.05-1.45e5 between 5 and 12 cm, and then COLLAPSES to 1-3e4 over the last 5 cm. A muon's Bragg peak is its last centimetre, so the real stop is at residual range ~9-10 cm and the fit runs 9 cm past it. What it runs into is object 36018: 9.0 cm at 2.5e4 e/cm (0.45 MIP) leaving the peak at a large angle -- the chain types it muon, but a muon cannot fall from its own Bragg peak to half MIP and keep going. That is the Michel. Pin moved to rr 9.5, which the slider snapped to the chain point at rr 9.56 -- 8.32 cm off the fit end, the same point the owner picked; 36018 tagged michel, the other seven segments muon.

**`039349_2/38`** (scan 229, 71 cm) — **STM_ONLY** / none / high confidence  
71 cm, enters 3.4 cm from the z face, stops 57.1 cm inside. Bragg to 1.2e5 on the muon curve. NOTHING attached at the stop -- no arm on the profile. The three extra objects sit 34-65 cm back ON the muon body line (cos_fwd -1.0), which is body activity beside the track: delta / other.

**`039349_21/51`** (scan 241, 199 cm) — **STM_MICHEL** / both / high confidence  
199 cm, enters 0.3 cm from the z face, stops 37.8 cm inside. The chain calls it no_bragg; the rise is modest but real, 4.5e4 plateau to 8e4 over the last 5 cm, which is where the reference curve is at 5 cm. A 12 cm arm at 3.3e4 e/cm leaves the stop forward (cos_fwd 0.50) with profile charge to -12 cm. Two dots at 32 and 52 cm, forward and clear of the body: gamma. 51011 lies 141-147 cm back on the body line: delta / other.

**`039349_22/64`** (scan 249, 477 cm) — **STM_ONLY** / detached dots / high confidence  
477 cm, enters 1.4 cm from the anode face, stops 79 cm from the y wall. The profile climbs the reference curve to 1.62e5 -- an unmistakable Bragg -- and MCS amb 0.03. NOTHING attached at the stop. One 2.0 cm dot 22 cm out, ~18 cm clear of the body: gamma. 64007 lies 360 cm back ON the body line: delta / other.

**`039349_25/47`** (scan 261, 243 cm) — **STM_ONLY** / none / high confidence  
243 cm, enters 1.8 cm from the anode face, stops 82.3 cm from the z wall. Bragg to 1.5e5 on the muon curve. Nothing past the stop at all. The one extra object is 4.7 cm of shower charge lying ON the muon body line (cos_fwd -1.0) 21 cm back: a delta ray beside the track, delta / other.

**`039349_26/18`** (scan 264, 74 cm) — **STM_ONLY** / detached dots / high confidence  
74 cm, enters 21.1 cm from the y face, stops 47.2 cm inside. Bragg to 1.2e5 on the muon curve -- the chain calls this no_bragg and its MCS returns the 3948 MeV ceiling at amb 1.00, but the profile is clear. Nothing attached. One 0.3 cm dot 58.5 cm out, perpendicular and therefore ~58 cm clear of the body: gamma. 18006 sits on the body line 57-60 cm back: delta / other.

**`039349_26/40`** (scan 266, 27 cm) — **STM_MICHEL** / both / medium confidence  
*owner review: CONFIRMED -- "266 looks good, I feel there is might be a small gap between the stopping STM and the Michel electron leading to low dQ/dx fit"*  
*profile peaks 5-8 cm before the fit end, so the fit slightly overshoots; pin moved to rr 4.0, uncertain at the +-3 cm level*  
27 cm, enters 0.6 cm from the z face, ends 16.8 cm inside. The muon is only 93 MeV so its whole length sits above MIP, and the profile peaks at 9.2e4 five to eight centimetres BEFORE the fit end, falling to ~6e4 over the last two -- the same overshoot signature as 039349_18/36, much smaller. Pin moved back to rr 4.0, snapped to the chain point at rr 4.2 (4.07 cm off the fit end; the owner's sits one point closer in at rr 3.0); at this contrast the correction is good to no better than +-3 cm. A 12.1 cm arm at 3.2e4 e/cm leaves the stop forward (cos_fwd 0.53) with profile charge to -17 cm. Two dots at 47 and 50 cm, both forward and clear of the 27 cm body: gamma.  [owner 2026-09-09, on reviewing this row: "there is might be a small gap between the stopping STM and the Michel electron leading to low dQ/dx fit" -- i.e. the fit bridges the gap between the muon's true stop and the Michel, and the interpolated points carry little charge.  That is the mechanism behind the peak-then-collapse signature, and it is why the collapse is the thing to look for rather than the peak's height.]

**`039349_27/41`** (scan 270, 71 cm) — **STM_MICHEL** / attached / medium confidence  
*owner review: CONFIRMED -- "270 looks good"*  
71 cm, enters 0.2 cm from the anode face, ends 66.7 cm inside it. Modest Bragg: 5e4 plateau to 9e4 over the last 5 cm, which is where the reference curve is at 5 cm. A 3.5 cm arm at 5.0e4 e/cm leaves the stop forward (cos_fwd 0.59) with profile charge to -3 cm -- short, so medium confidence. Worth the owner's eye: the chain rejects this on stop_near_boundary and sets in_fv 0, yet the stop is 66.7 cm from the nearest ACTIVE face, so the call comes from the tighter curved fiducial map, not from the envelope the display draws.

**`039349_28/36`** (scan 273, 348 cm) — **STM_MICHEL** / both / high confidence  
348 cm, enters at the anode face, stops 54.5 cm from the nearest (y) wall. Bragg rise 5e4 -> 9e4 over the last 20 cm along the muon curve. Attached 4-piece Michel out to 12 cm past the stop, cos_fwd 0.6-0.82. Three further isolated pieces at 21.7, 32.7 and 55.4 cm, all forward (cos_fwd 0.04-0.59) and none on the muon's own line, so they are shower gammas, not a continuation.

**`039349_28/52`** (scan 275, 92 cm) — **MESSY** / none / high confidence  
*not one track: a 55 cm EM-like blob broken into 26 objects, no Bragg, spine well below MIP*  
A compact diffuse spray at the z face, not a track: the 91.7 cm fit wanders inside a ~55 cm blob, and the chain splits it into 10 spine segments plus 16 pdg-11 shower pieces, ALL behind the stop (cos_fwd -0.84 to -0.99). dQ/dx is chaotic with no rise at the stop and four spine segments at 11-18 ke/cm, a third of MIP. MCS amb 1.00. Chain agrees (shape_flat, plateau_off_mip).

**`039349_29/45`** (scan 281, 232 cm) — **STM_MICHEL** / both / high confidence  
232 cm, enters 1.9 cm from the z face, stops 70.4 cm inside. Bragg rise 4e4 -> 9.5e4 over the last 20 cm on the muon curve. A 5.6 cm arm at a 36 deg kink leaves the stop vertex at 8.1e4 e/cm. Five isolated pieces at 21-54 cm, cos_fwd 0.4-0.61, i.e. forward and roughly along the Michel axis -- checked at two azimuths, they do NOT lie on the muon's own line, so they are the Michel's gammas and not a broken continuation. The chain calls this not-an-STM on shape_flat; the profile plainly rises.

**`039349_3/46`** (scan 285, 17 cm) — **STM_MICHEL** / attached / medium confidence  
*owner review: CONFIRMED -- "285 Looks good"*  
16.8 cm, enters 0.5 cm from the anode face and stops 17.1 cm inside it. Short and low energy (67 MeV), so the whole track sits high on the muon curve; the profile still climbs from 6e4 at 15 cm to 9e4 in the last 3 cm. A 7.7 cm arm leaves the stop at a sharp angle. At 67 MeV the muon cannot make a 7.7 cm delta ray, so the arm is a decay product; its 3.2e4 e/cm is low but that is normal for a sparse few-MeV electron. Medium only because the track is short and the Bragg contrast is modest.

**`039349_35/62`** (scan 314, 220 cm) — **STM_MICHEL** / attached / high confidence  
220 cm, enters 1.2 cm from the anode face, stops 79.8 cm from the nearest wall. Clean Bragg: 5e4 plateau rising to 9e4 in the last 3 cm along the muon curve. A three-piece 9.6 cm arm leaves the stop roughly perpendicular to the muon (cos_fwd -0.11 to -0.26) at 2.7-6.4e4 e/cm. Sideways rather than forward, which is what a Michel does and what a broken continuation does not.

**`039349_36/41`** (scan 317, 52 cm) — **STM_MICHEL** / attached / high confidence  
51.8 cm, enters 1.0 cm from the z face, stops 21.9 cm inside. Textbook Bragg -- 5e4 plateau to 1.45e5 in the last centimetre, sitting on the muon reference curve the whole way. An 11.3 cm two-piece arm leaves the stop forward (cos_fwd 0.70/0.73) at 3.5-7.8e4 e/cm; range and charge are right for a ~25 MeV Michel.

**`039349_38/60`** (scan 329, 119 cm) — **THRU** / none / medium confidence  
*owner review: CONFIRMED -- "329 and 194 is clearly not STM"*  
*fit ends abruptly with no Bragg, no dead channels and no charge past it -- worth a look; the track runs 24 deg from the drift axis*  
119 cm, enters at the anode face, fit ends 110 cm inside it. NO Bragg: dQ/dx is flat at 4e4, BELOW the 5.5e4 MIP reference, from 100 cm right down to the last 2 cm, and nothing at all is drawn past the stop -- no arm, no dots. A stopping muon cannot end without a rise. The measurement panels show clean charge in all three planes ending at the same time slice with no dead region there, so the end is not an escape through unresponsive channels either. Flagged rather than resolved: the track runs only 24 deg off the drift axis, the hardest case for the 2-D charge attribution the dQ/dx is built from, and MCS (1076 MeV) disagrees violently with range (293 MeV).

**`039349_4/47`** (scan 337, 45 cm) — **THRU** / none / high confidence  
45 cm, enters 0.6 cm from the z face and the fit ends 11.6 cm from the SAME face -- it skims that wall rather than stopping in the bulk. dQ/dx is flat at 4-5e4 over the whole length with no rise at the end, and there is nothing past the stop in any view. No Bragg and no decay activity is the owner's TGM case.

**`039349_40/49`** (scan 342, 56 cm) — **MESSY** / none / high confidence  
*not one track: a 56 cm fit through a busy region, spine dQ/dx 0.03-0.4 MIP*  
21 objects around a 56 cm fit, and the fit is not a muon: its own spine segments run 1374, 2202, 9629, 21313 and 22713 e/cm, i.e. 0.03 to 0.4 of the 5.5e4 MIP. The profile never rises -- most of the length sits under 1e4 -- and the 3-D view is a knot of short segments in several directions with vertices scattered over 60 cm, not one track with one end. MCS amb 1.00 and range 157 MeV against dQ/dx 48 MeV say the same. Every row is tagged 'delta / other' meaning 'drawn here, but part of neither a stopping muon nor a Michel'.

**`039349_43/54`** (scan 352, 87 cm) — **STM_MICHEL** / attached / high confidence  
87 cm, enters 0.3 cm from the anode face, stops 71.6 cm inside. Clean Bragg on the muon curve, 5e4 plateau to 1.35e5 at the last point. A 14 cm two-piece arm leaves the stop sideways-forward (cos_fwd 0.17/0.36) at ~5e4 e/cm, and one further 0.2 cm piece sits 16 cm out at cos_fwd 0.70 -- isolated, forward, along the arm's direction, so a shower gamma.

**`039349_46/58`** (scan 368, 30 cm) — **MESSY** / none / high confidence  
*not one track: 29.6 cm of fit through a 19-object knot*  
A compact busy blob: 19 objects inside ~35 cm, 13 of them the chain's own pdg-11 shower pieces, with vertices in every direction and no single spine. The 29.6 cm fit has no Bragg -- dQ/dx runs 1-6e4 and falls toward the end -- and its segments disagree wildly (8894, 37307, 45440 e/cm). Chain agrees it is neither (shape_flat, profile_sparse) and cannot even compute MCS.

**`039349_48/49`** (scan 376, 186 cm) — **STM_ONLY** / detached dots / high confidence  
186 cm, enters at the anode face, stops 40.8 cm from the z wall. Strong Bragg: 4e4 plateau to 1.2e5 at the last point, on the muon curve. NOTHING attached at the stop -- no arm at all -- so this is a stopping muon without a visible Michel. Two 2-point dots sit 24.5 and 36.2 cm out (cos_fwd -0.05 and 0.12, i.e. sideways), isolated from the muon body; the chain already calls the nearer one a capture gamma. Dots seen, judged gamma, so the verdict stays STM_ONLY.

**`039349_54/54`** (scan 410, 181 cm) — **STM_MICHEL** / attached / high confidence  
181 cm, enters at the anode face, stops 33.8 cm from the y wall. Bragg rise 5e4 -> 9e4 on the muon curve. A 12.8 cm arm at 4.8e4 e/cm leaves the stop sideways (cos_fwd -0.07) -- range and charge of a ~25 MeV Michel. Two isolated dots: 139007 sits 14 cm out, just past the arm's tip and ~15 deg off its axis; 138006 is 50 cm out on the same side, clear of the muon body in the wide view. Both tagged gamma; the 50 cm one is the weakest call in this row.

**`039349_59/61`** (scan 436, 267 cm) — **STM_MICHEL** / attached / high confidence  
267 cm, enters 15.4 cm from the z face, stops 64.9 cm inside. Textbook Bragg to 1.35e5 on the muon curve. A 14.7 cm arm at 4.6e4 e/cm leaves the stop forward (cos_fwd 0.42) with charge out to -15 cm on the profile -- a full-energy Michel. One 1.1 cm dot 58 cm out, forward and isolated, tagged gamma; at 58 cm that is the weakest call in the row.

**`039349_61/18`** (scan 444, 99 cm) — **STM_MICHEL** / attached / high confidence  
99 cm, enters 8.8 cm from the y face, stops 45.6 cm inside. Bragg to 1.2e5 on the muon curve. An 11.3 cm arm at 3.6e4 e/cm leaves the stop (cos_fwd 0.11) with profile charge out to -12 cm. Nothing else drawn near the stop.

**`039349_63/48`** (scan 460, 365 cm) — **THRU** / none / high confidence  
365 cm, and the fit END sits 0.1 cm from the y wall -- it leaves the detector, which the side view shows directly with the last point on the red boundary. in_fv 0. Nothing to judge as a stop. The five extra objects all lie 246-330 cm back along the muon body, not at the end, so they are body activity (the chain types three of them pdg 4) and not a Michel; tagged delta / other. The drawn track also breaks into two pieces between z 110 and 150.

**`039349_64/71`** (scan 470, 257 cm) — **STM_MICHEL** / both / high confidence  
257 cm, enters 7.7 cm from the anode face, stops 52.7 cm from the z wall. Bragg to 1.35e5 on the muon curve. A 25 cm two-piece arm leaves the stop forward (cos_fwd 0.39/0.42), contiguous (the second piece starts where the first ends), with profile charge out to -22 cm -- a full-energy Michel. One 0.3 cm dot 33 cm out, forward, isolated: gamma. 71008 (pdg 211, 11.7 cm) sits 247-258 cm back at the ENTRY end, nothing to do with this stop: delta / other.

**`039349_66/78`** (scan 474, 209 cm) — **STM_ONLY** / detached dots / medium confidence  
*owner review: CONFIRMED -- "474 is OK, the Bragg peak is not as consistent, but I feel the scan is OK"*  
*no attached arm; a detached 17 cm MIP-like clump sits 24-31 cm out, perpendicular -- if that is read as a detached Michel this row becomes STM_MICHEL*  
209 cm ending 68 cm from the nearest wall with nothing continuing in the muon's own direction, so it stopped -- there is no other option at that distance from every face. But the Bragg is weak: dQ/dx sits on the 5e4 plateau to within 5 cm and reaches only 6-8e4, where the reference is 1.6e5. The likely reason is object 78041, 1.8 cm of 1.2e5 e/cm sitting 0-1.7 cm straight ahead of the fit end: the tip is clustered separately, so the fit stops ~2 cm short and never sees its own peak. I tag 78041 muon for that reason though the chain types it pdg 11. NOTHING is attached at the stop. Three pieces 24-31 cm out carry ~17 cm of 5-6e4 e/cm, perpendicular to the muon (cos_fwd 0.08-0.18) and clear of it in two azimuths. Following the owner's 5 STM_ONLY + detached-dots rows I record dots seen, judged not a Michel; but 17 cm of MIP charge is a lot for a capture gamma, and 24 cm is a long gap for a Michel, so this is the row to open first.

**`039349_67/78`** (scan 481, 84 cm) — **STM_MICHEL** / both / medium confidence  
*owner review: CORRECTED -- "481, the S78013 is likely part of a Michel electron, and the end point should be at S78010"*  
*owner 2026-09-09: S78013 is part of the Michel and the stop is at the end of S78010; pin moved back 4.8 cm*  
84 cm, enters 0.8 cm from the y face, fit ends 58.5 cm inside.  OWNER CORRECTION 2026-09-09, and re-reading the profile against it shows the first pass had the stop in the wrong place: the rise does not run to the fit's last point.  dQ/dx climbs off a 5-6e4 plateau to 0.9-1.15e5 between +3 and +12 cm and the LAST ~4 cm collapse to 1-4.5e4, which is the same overshoot signature as 039349_18/36 and 039349_26/40.  What the fit runs into is S78013 -- 8.8 cm at 1.9e4 e/cm (0.35 MIP), spanning 0 to 4.8 cm from the old end at cos_fwd -0.47, and typed muon by the chain.  A muon at its own Bragg peak cannot continue at a third of MIP: that is the Michel.  Pin moved back to the S78010/S78013 junction at rr 4.8; S78013 tagged michel.  225015, the chain's own 0.3 cm pdg-11 seed, sits 3.9-4.1 cm from the old end and so ~0.7-0.9 cm from the NEW stop -- inside the radius where direction does not discriminate -- so it is michel too, and the kind is both rather than attached because it is drawn as its own piece.  224014 stays gamma: 53 cm out, forward, clear of the body line.

**`039349_7/67`** (scan 498, 58 cm) — **STM_MICHEL** / attached / medium confidence  
*owner review: CONFIRMED -- "498 Looks good"*  
58 cm, enters 1.1 cm from the z face, stops 15.7 cm inside. Bragg to 1.25e5 at the last point on the muon curve. An 8.4 cm two-piece arm leaves the stop forward (cos_fwd 0.20/0.25) with profile charge to -8 cm; its 1.8e4 e/cm is low for an electron, which is why this is medium and not high. 246011 sits 56 cm out at 1.1e4 e/cm (0.2 MIP) -- too far and too faint to attribute -- but see below.  [REVISED at the end of the pass: 246011 is tagged **gamma**, not delta / other. The rule settled on charge NOT being a criterion -- any isolated object past the stop and clear of the muon body line is a gamma, however faint. The reasoning above is left as written so the change is visible.]

**`039349_72/65`** (scan 514, 267 cm) — **STM_MICHEL** / attached / high confidence  
267 cm, enters 0.1 cm from the z face, stops 54.2 cm inside. Bragg to 1.25e5 on the muon curve, MCS amb 0.00. A 13.3 cm arm at 3.5e4 e/cm leaves the stop sideways with profile charge to -12 cm; the 0.3 cm piece 7.6 cm out lies inside that arm's own extent, so it is the same object rather than a separate dot.

**`039349_75/72`** (scan 524, 163 cm) — **MESSY** / none / high confidence  
*not one track: a broken, sparse zig-zag of 17 objects, spine 0.06-0.6 MIP*  
A 163 cm fit threaded through a sparse, disconnected zig-zag: 15 'muon' segments whose dQ/dx runs 3280 to 34354 e/cm, most of them under 0.3 MIP, with vertices scattered in every direction and visible gaps between the pieces in the wide 3-D view. Only 436 image points over 163 cm. MCS amb 1.00 and range 386 MeV against dQ/dx 115 MeV. Neither end is at a face (63.6 and 112.5 cm), so this is not a containment question -- it is simply not one track.

**`039349_76/75`** (scan 529, 181 cm) — **STM_ONLY** / none / medium confidence  
*owner review: CONFIRMED -- "529 probably OK"*  
181 cm ending 84 cm from the nearest face with nothing continuing, so it stopped. The Bragg is modest -- 4.5e4 plateau to 7.8e4 at the last point, a factor 1.7 -- but it is a rise, and the last segment runs 6.8e4 e/cm against 4.9e4 for the body. Nothing electron-like past the stop. The one extra object is 1.5 cm at 7 cm out with cos_fwd -0.39, i.e. close to the track and BACKWARD, which is the owner's own counter-example for 'not part of the Michel': delta / other.

**`039349_81/54`** (scan 554, 105 cm) — **MESSY** / none / high confidence  
*not one track: a full EM shower, 53 objects, 3806 image points in ~50 cm*  
An electromagnetic shower, not a track: 53 objects and 3806 image points packed into ~50 cm, 41 of them the chain's own pdg-11 shower pieces, and every single one BEHIND the fit end (cos_fwd -0.72 to -0.99). The 12 segments the chain calls muon run 4222-24254 e/cm, 0.08 to 0.44 MIP. MCS amb 1.00 with 39.9 MeV against 262 MeV from range. The 3-D view is a dense blue cloud with about fifty vertices in it.

**`039349_82/52`** (scan 558, 103 cm) — **STM_ONLY** / none / high confidence  
103 cm, enters 0.6 cm from the anode face, stops 32.9 cm from the z wall. Textbook Bragg to 1.38e5 on the muon curve. NOTHING past the stop: the profile has two faint survey crosses at -6 and -9 cm (0.5-2.3e4) and no arm. All five extra objects sit 8-29 cm BACK along the muon body (cos_fwd -0.78 to -1.0) -- body activity, not a decay product, so delta / other.

**`039349_83/60`** (scan 564, 173 cm) — **STM_MICHEL** / attached / high confidence  
173 cm, enters at the anode face, stops 71.5 cm from the z wall. Bragg to 1.15e5 on the muon curve. A four-piece arm covering 0-11 cm past the stop, all forward (cos_fwd 0.70-0.82), at 3.3-6.4e4 e/cm, with dense profile charge out to -13 cm -- a well-reconstructed Michel.

**`039349_9/47`** (scan 568, 231 cm) — **STM_MICHEL** / both / high confidence  
231 cm, enters 0.1 cm from the z face, stops 45.3 cm from the y wall. The profile hugs the muon reference curve all the way to 1.5e5 -- as clean a Bragg as this sample has. A four-piece arm covers 0-12 cm past the stop (cos_fwd 0.13-0.68) with profile charge to -14 cm. 122009 is a 0.7 cm dot 42 cm out, forward and at 8.5e4 e/cm: gamma. 124016 is 52 cm out, sideways-backward and 0.3 MIP -- too far, too faint and off-axis to attribute -- but see below.  [REVISED at the end of the pass: 124016 is tagged **gamma**, not delta / other. The rule settled on charge NOT being a criterion -- any isolated object past the stop and clear of the muon body line is a gamma, however faint. The reasoning above is left as written so the change is visible.]

---

## 13. Tranche 2 — the remaining 509 items, and how they were scanned

The owner asked (2026-09-09) for the improved method to be carried over the rest
of the PDVD sample, with up to five subagents. Tranche 2 is the **other 509** of
the 569 items on the sheet, so with tranche 1 the scan now covers **every
`CheckSTM_Michel` candidate in arm d53v** that carries ≥ 20 profile points and
≥ 10 cm of muon (`prep_stm_michel_scan.py:104-105`). That is the whole
population, not a sample of it — §14 is a **census**, and no stratum
re-weighting applies.

**Why tranche 2 is the round that answers doc pdvd/48 §11.** Tranche 1 was drawn
stratified on the chain's own flags and is enriched: 36 of its 60 items carry
`is_stm`. Tranche 2 carries 117 of 509 (23 %). The efficiency and purity of the
STM+Michel flag only mean something on the unenriched population, and §14 shows
how far the two differ.

### 13.1 The method

Same instrument as tranche 1 — the real Bokeh app driven headless, seven frames
per item plus the object table — at the same fidelity, with three changes forced
by scale:

* **Five scanners in parallel**, each with a **private output directory**. A
  shared one leaked: a scanner listed it mid-chunk and saw ~50 other verdicts.
  Its own items were already written so nothing of its work was contaminated,
  but that was luck, and the fix is structural.
* **The rubric was frozen** (`pdvd/docs/scan/pdvd_stm_michel_scan_rubric.md`,
  sha recorded) after two calibration waves. It had moved four times during the
  first scan wave; a scanner pointed out that rows scanned under different text
  cannot be pooled, so **that wave was discarded and re-scanned** — 60 items,
  12 % of the round, deliberately spent to keep one population.
* **Per-item persistence.** Each scanner writes its record through `mkv.py`
  before moving on, and the parent recomputes the remaining list by diffing
  against what is on disk. A scanner that runs out of room loses nothing.

`mkv.py` enforces what the rubric asserts: the verdict alphabet, the
`michel_kind` derivation, a tag on **every** drawn object, and a real evidence
paragraph. A record that contradicts itself is refused rather than shipped.

### 13.2 What the scan cost, and what the frames cost

509 items × 7 frames = 3563 renders, ~200 MB, ~50 min over five browsers; the
scanning itself ran 9 waves of 5 agents at ~12 items each.

**A defect worth knowing before anyone repeats this.** Two of the five shots
processes lost their WebGL context (`(regl) context lost`), which the harness
reports only in an end-of-run summary naming no item. The effect is not a clean
failure: 187 of their 204 items came back with **smeared** 3-D frames — solid
wedges where the point cloud should be — which are unique per item and normal in
size, so neither an md5 test nor a size test sees them.

Counting unique colours in `c_3d_stop.png` separates the populations completely:

| shots processes | items | median colours | below 1000 |
|---|---:|---:|---:|
| clean (1, 2, 4) | 305 | 3877 | **0** |
| context-lost (0, 3) | 204 | 722 | **187** |

All 204 were re-shot with two concurrent browsers instead of five (min 1421,
median 4069, zero smeared) and swapped in before the scan began. The predictor
to act on is the **process**, not the frame: if a shots process logged the error,
every item it produced is suspect. `check_shots.py` now applies both tests.

---

## 14. What the scan says — the census

509 tranche-2 verdicts, and the combined 569:

| verdict | tranche 2 | tranche 1 | census |
|---|---:|---:|---:|
| `THRU` | 267 | 7 | 274 |
| `STM_MICHEL` | 117 (+1 `FRAG_`) | 34 | 152 |
| `STM_ONLY` | 103 (+1 `FRAG_`) | 13 | 117 |
| `MESSY` | 14 | 5 | 19 |
| `FRAG_THRU` | 5 | 1 | 6 |
| `UNCLEAR` | 1 | 0 | 1 |

`michel_kind`: none 340, both 67, detached dots 56, attached 46.
Confidence: **269 high, 227 medium, 13 low**.
Attribution: **3462 tags** over the 509 — muon 1560, delta / other 1420,
gamma 254, michel 228, straddles the stop **0**.
Pins moved on **33**; 6 rows carry an `UNDERSHOOT:` note.

### 14.1 The chain's stopping-muon flag

Scoring `is_stm` against the scan, `MESSY`/`UNCLEAR` excluded:

| | scored | TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|
| tranche 1 (enriched) | 55 | 35 | 1 | 12 | 7 | 0.972 | 0.745 |
| tranche 2 | 494 | 109 | 8 | 113 | 264 | 0.932 | 0.491 |
| **census (569)** | **549** | **144** | **9** | **125** | **271** | **0.941** | **0.535** |

**Purity holds up; efficiency does not.** What the chain calls a stopping muon
almost always is one (0.941). But it finds only **half** the stopping muons the
scan sees — 125 missed against 144 found — and tranche 1's 0.745 was an artefact
of the enrichment, not a property of the detector.

### 14.2 The chain's Michel flag

| | scored | TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|
| tranche 1 (enriched) | 55 | 33 | 4 | 1 | 17 | 0.892 | 0.971 |
| tranche 2 | 494 | 78 | 35 | 40 | 341 | 0.690 | 0.661 |
| **census (569)** | **549** | **111** | **39** | **41** | **358** | **0.740** | **0.730** |

Tranche 1's 0.971 Michel efficiency was the enrichment speaking. On the whole
arm the flag is **0.740 pure and 0.730 efficient**.

---

## 15. The two failure modes, with mechanisms — and a cut that fixes half of it

Both mechanisms below are established from **payload arithmetic over all 569
items**, independent of any scanner's judgement.

### 15.1 Purity: proximity-connected "Michels" that cannot be electrons

`michel_conn_type` already separates the chain's two ways of finding a Michel:

| `conn_type` | n | distance to stop (median) | length | KE |
|---|---:|---:|---:|---:|
| **1** — graph edge | 113 | **0.00 cm** (all 113) | 6.49 cm | **21.4 MeV** |
| **2** — proximity | 45 | **9.11 cm** | 1.20 cm | **4.1 MeV** |

Type 1 is a textbook Michel population, sitting on the decay spectrum. Type 2 is
9 cm away, 1 cm long, 4 MeV. The kinematic test is decisive — an electron born
at the stop cannot travel 5 cm through liquid argon and deposit under 10 MeV:

| | fails `dis > 5 cm` **and** `KE < 10 MeV` |
|---|---|
| `conn_type == 1` | **0 of 113** |
| `conn_type == 2` | **26 of 45** |

Five scanners independently demoted these to `gamma` on the attachment
tie-break, in almost the same words, before the field was examined.

**The recommended cut**, scored on the census:

| | TP | FP | FN | purity | efficiency | F1 |
|---|---:|---:|---:|---:|---:|---:|
| as shipped | 111 | 39 | 41 | 0.740 | 0.730 | 0.735 |
| require `conn_type == 1` | 99 | 10 | 53 | 0.908 | 0.651 | 0.759 |
| drop `dis > 5 cm` & `KE < 10 MeV` | 109 | 18 | 43 | 0.858 | 0.717 | 0.781 |
| **drop `dis > 3 cm` & `KE < 10 MeV`** | **108** | **13** | **44** | **0.893** | **0.711** | **0.791** |

**Take the last row.** Dropping Michels more than 3 cm from the stop carrying
under 10 MeV lifts purity **0.740 → 0.893** for two points of efficiency
(0.730 → 0.711). It uses only fields the payload already writes — no new
reconstruction, no retuning. Requiring `conn_type == 1` buys slightly more
purity but discards a tenth of the real Michels.

### 15.2 Efficiency: the Michel suppresses the signature the flag tests for

A scanner defined its decision rule as the **terminal-to-plateau charge ratio** —
median of the last five live fit points over the median of the body. Applied to
every scanned item it reproduces **81 %** of the scanners' verdicts as a single
cut at 1.35, so it is a fair proxy for what the eye was doing. The distribution
is the finding:

| verdict | n | median ratio |
|---|---:|---:|
| `THRU` | 152 | 0.91 |
| `STM_ONLY` | 65 | **1.86** |
| `STM_MICHEL` | 73 | **1.32** |

**An item with a Michel has a systematically weaker measured Bragg rise.** When
decay charge sits past the stop, the fit runs into it and the terminal points
that define the rise are diluted. Crossing the ratio with the chain's flag shows
what the chain is actually measuring: among scanner-called stoppers, the ones it
accepts score 1.98 and the **72 it rejects score 1.11**.

So the chain is not erring arbitrarily — its shape test measures the terminal
rise, and on the items it misses that rise genuinely is weak *in the fitted
profile*. **The flag loses efficiency because a Michel degrades the very
quantity it tests for.** That is structural, and it is why `shape_flat` is the
dominant rejection reason (354 of 509 tranche-2 items).

### 15.3 The fit stops SHORT — a false-negative mechanism, and scan 474

Doc pdvd/54 records the fit **overshooting**. The opposite happens too, and the
census is exact. Asking for a segment that is forward (`cos_fwd ≥ 0.85`), short
(≤ 6 cm), at the fit end (`d_min ≤ 2 cm`) and above 1.67 × MIP returns **5
objects in 569**, with a clean gap to the next candidate at 1.48 MIP:

| item | chain verdict | segment | dQ/dx | × MIP |
|---|---|---|---:|---:|
| `039252_5/73` | rejected `shape_flat` | 73013 | 131326 | 2.43 |
| `039349_66/78` | rejected `no_bragg`, `shape_flat` | 78041 | 120416 | 2.23 |
| `039253_13/39` | rejected `shape_flat` | 39009 | 119207 | 2.21 |
| `039349_18/33` | rejected `shape_flat` | 33010 | 118139 | 2.19 |
| `039253_0/110` | rejected `stop_near_boundary` | 110007 | 99976 | 1.85 |

**The chain rejected all five.** When the fit stops a centimetre or two short,
the Bragg peak lands outside the fitted trajectory and the shape test sees a
profile flat to its last point.

**`039349_66/78` is scan 474**, which the owner reviewed:

> *"474 is OK, the Bragg peak is not as consistent, but I feel the scan is OK"*

The structure explains the reading. The muon body (`78040`) runs 84 cm at
53228 e/cm — flat on the plateau — to the fit's last point. The Bragg peak is
not ragged: it is a **1.8 cm piece at 120416 e/cm (2.23 × MIP) sitting 0.0 cm
past the fit end at `cos_fwd +0.97`**, which the fit excluded. 474 is not a
stopper with a poor Bragg peak; it is a stopper whose fit ended 1.8 cm early,
and the chain's `no_bragg` on it is a false negative with an identified cause.
No label changes — the tranche-1 record already tags `78041` as `muon`.

The census counts tips whose charge is high *throughout* (`dqdx_med`, verified
to be exactly the median of live points on 1279/1279 segments). Admitting
single-sample spikes would give 15 and would be counting delta rays.

---

## 16. How good are these labels?

### 16.1 Reproducibility, measured twice

The discarded first wave and its re-scan covered the same 57 items with
different agents, and a wave-list race scanned 4 more twice under the frozen
rubric — 61 items double-scanned, neither scanner able to see the other.

| | agreement |
|---|---|
| verdict | 53/57 and 3/4 |
| `michel_kind` | 52/57 |
| per-object tag | 350/387 (90 %) |

Stratified by the scanners' **own** confidence:

| both scanners said | verdict agreement |
|---|---:|
| `high` | **24/25 (96 %)** |
| at least one `medium` | 30/32 (94 %) |
| either `low` | **0/4 (0 %)** |

**The confidence field is a calibrated reliability key**, and it should be read
as one: the `high` rows reproduce, the `low` rows are coin-flips and say so. The
single `high`/`high` disagreement (`039349_62/63`) is the round's recurring
question — whether a forward MIP-charge arm at the stop is the Michel or the
muon carrying on.

### 16.2 The pin is the least reproducible measurement

Where both scans placed a pin they agreed to 0.6 cm, but they disagreed about
*whether* one belonged on half the cases (3 of 6). Doc 55 §7's pin distances,
and tranche 2's 33, should be read as one scanner's placement — the
verdict-level claim ("the fit's stop is wrong here") is far more robust than the
centimetre attached to it.

**The pins are not resting on dead wires.** Testing each pinned item's fit points
between the stop and the moved pin against the payload's dead-channel lists:
**9 of 33 have any dead-channel coverage, and none in more than one plane.**
Charge is reconstructed from three planes, so no pin in the round rests on a
collapse that dead wires could manufacture.

### 16.3 The limit on every number above

Scanners read `context.json` — which carries `is_stm` and `reject_names` —
before opening a frame. **Every scanner saw the chain's answer before looking at
the picture.** This is inherited by design (the display shows the verdict in its
header, and doc pdhd/12 §13.2 records tranche 1 the same way), which is what
makes the two tranches comparable, but it makes this:

> **the chain's reconstruction reviewed by a physicist — not an unbiased
> benchmark of the chain.**

The bias pulls **toward agreement**, so §14's purity and efficiency are if
anything optimistic and the disagreement classes are conservative. The §15
mechanisms are untouched by it: they are payload arithmetic over all 569 items.

**A blind round is cheap** — suppressing those two fields in `context_of()` is a
one-line change plus regenerating the shots — and it is what would *measure* the
flag rather than review it.

### 16.4 Gates on the census

| gate | result |
|---|---|
| every one of the 509 written by clicking the real widgets | 509 saved, **0 retries**, no `SystemExit` in any apply log |
| the five private label dirs merge disjointly | 102+102+102+102+101 = **509**, no key written twice |
| the 60 tranche-1 rows survive the merge | **all 60 byte-identical** to the pre-round snapshot `7456ee89` |
| the owner's two live pins survive | `039349_12/45` rr 58.78, `039349_26/40` rr 0.60 — **preserved as found** |
| `pdvd/work/stm_michel_labels/smx1/` untouched (M13) | sha `8fc76b33…` unchanged start to end |
| `verify_scan_record.py … --record …` | **569 records over 569 rows**; every verdict, kind and tag matches. Two mismatches remain **by design** — the owner's pins above, which the record does not claim |
| `score_stm_michel_scan.py --det pdvd --tag smx1a` | clean, rc 0 (it refuses an unknown `label`) |
| `mkstats.py --check` | **0 of 4** published tables differ from the recomputed values |
| `mkfailures.py` regenerated deterministically | reproduces the committed `failures.tsv` **byte-identically** |
| every drawn object carries a tag | `allow_partial` on **0** of 509; **3462** tags over the 509, **3927** over all 569 |

The label file went `7456ee89` (60 rows) → `724693b3` (569) → `afa025be` after
the one-row correction of §17.6. Those shas are recorded so a later clobber is
detectable rather than silent.

---

## 17. Found and not fixed

Full detail, with the measurements behind each, is in
`pdvd/docs/scan/pdvd_stm_michel_tranche2_findings.md`. Summarised here because
several are cheap to act on and none was fixed in this round.

**For work on the package itself, start from the failure register:**

* `pdvd/docs/scan/pdvd_stm_michel_failures.md` — every failure class with the
  `CheckSTM_Michel.cxx` line it lives at, the knob involved, and a suggested
  change;
* `pdvd/docs/scan/pdvd_stm_michel_failures.tsv` — **445 rows over 251 items**,
  one per (item, failure class), so each class is a concrete starting set;
* `pdhd/stm_michel_scan/mkfailures.py` regenerates both, so a class can be
  re-counted after a fix to see whether it shrank.

### 17.1 Chain / payload

| # | what | scale |
|---|---|---|
| 1 | **`michel_conn_type == 2` admits impossible Michels.** 26 of 45 fail the range-energy test. A field that already exists is a working quality flag and is not used as one. | 45 of 158 |
| 2 | **`reject_names` inverts on every accepted item.** It contains the literal `STM` **only** when `is_stm == 1` — on all 153 accepted items and nowhere else. A reader taking the field at its name reads the verdict backwards on exactly the items that matter. | 153 |
| 3 | **`seg_rej.d_stop` is wrong on a tail.** 16 of 854 segments disagree with the true 3-D distance by > 5 cm, two by > 100 cm; one carries an unfiltered **`1e8` sentinel** that the display would render in a column. | 16 of 854 |
| 4 | **The fit spans ground the imaging never covered.** 40 fitted segments ≥ 20 cm carry < 0.25× their item's plateau, over 20 items — the longest **208.6 cm** at 0.114. This is the class scanners could place in neither `THRU` nor `MESSY`. | 20 items |
| 5 | **The coiled fit end.** 18 items pack ≥ 1.5× more fit arc than 3-D span into their last 20 cm (max 3.41). dQ/dx is charge ÷ path length, so a coil corrupts the denominator in **both** directions. | 18 items |
| 6 | **`seams_at_stop.cathode` is not a face distance.** It is `|stop_x| − 3.0`, verified 120/120. Three records were written against a misreading of it before the formula was established. | all |
| 7 | **One scanned item is probably not a muon** (`039253_1/98`: chain reject `not_muon_pid`, energies disagreeing 60 %). The alphabet cannot say "stopping particle, not stopping muon". | 1 |

Items 4 and 5 are both computable from fields the payload already carries, and
would let an item be flagged *"profile unreliable, geometry only"* before anyone
reads its dQ/dx — joining `plateau_off_mip` (47 tranche-2 items) and
`profile_sparse` (30) as named classes where the charge scale is not to be
trusted.

### 17.2 Display

1. **`g_dqdx` omits objects the table lists.** Verified by zooming the exact
   arc-length band and finding it blank — `039252_5/73`'s 8-point, 1.31e5 e/cm
   object at `d_min 0.0` is simply not plotted. The class dropped is fitted
   daughter segments, which is **precisely what the undershoot check hunts for**.
   The object table, not the panel, had to be made the census.
2. **`g_dqdx` cannot distinguish "no charge" from "low charge"**, and ships at
   514×338 — every scanner cropped and upscaled 4–7× to read the last few cm.
   A per-point live/dead marker was the single change scanners most wanted.
3. **The particle-flow overlay is drawn over both the 3-D frames and `f_meas`**,
   in categorical colours, and its *extent* varies per item — so the boundary
   where the amber band ends reads as a physical change in the object. That
   caused the round's clearest self-caught error, later corrected by its scanner.
4. **The amber band is not a stop marker.** It sat at the entry end on some
   items and mid-track on others. The star at the centre of the three
   `*_3d_stop` frames is the only reliable stop marker.

### 17.3 The rubric — three calibration errors of mine

Recorded because the rubric is part of the committed record, and because the
scanners caught all three by trusting shape over my numbers:

1. *"Real stoppers top out at 1.2–1.35e5."* Measured over 186 scanner-called
   stoppers: **47 % peak below 1.2e5 and 35 % above 1.35e5** — fewer than one in
   five falls inside the band.
2. *"1e5 is four to six times MIP."* MIP is ~5.4e4 from the display's own
   reference curve, so 1e5 is 1.9× — the clause and the absolute band it sits
   beside can never both be satisfied.
3. *"Nothing ever crosses the muon curve."* **86 % of items** have at least one
   point above it within 25 cm of the stop. The guidance (read shape, not
   crossing) was right; the justification was false, and it cost scanner time.

All three are the same shape: a statement true in one narrow situation,
generalised into a rule. **Delete the absolute charge anchors** and quote the
plateau ratio (§15.2) and the shape tests, which are scale-free and survive
`plateau_off_mip`.

### 17.4 The label schema

1. **A moved pin can force `STM_MICHEL`** even when nothing is past the gap, and
   the mirror case ships a verdict/kind contradiction — 3 of 509 records carry
   an `STM_MICHEL` verdict with no object tagged `michel`. `mkv.py` enforces
   kind-against-tags but nothing enforces kind-against-verdict.
2. **The rubric already had the answer and contradicted itself.** It says "the
   tag alphabet is per-object and cannot split one" and separately offers
   `straddles the stop` — *"one object genuinely spanning the stop"*, which is
   exactly the split-row tag. Every scanner followed the first sentence:
   **`straddles the stop` was used 0 times in 509 items**, as in tranche 1's 60.
3. **The `gamma` tag conflates two mutually exclusive processes** — a
   Michel-shower gamma (coexists with a Michel) and a muon-capture gamma
   (excludes one). A capture-to-decay ratio is **not recoverable** from this
   round's `michel_kind` distribution.
4. **The far-speck rule reads backwards on the items it is most needed for.** It
   sends specks "scattered in unrelated directions" to `delta / other` — but on
   an `STM_ONLY` the gammas are capture gammas, and a nuclear de-excitation
   cascade **is** isotropic.
5. **`THRU` conflates "no Bragg rise" with "no measurement"**, and its tag
   convention forces every non-chain object to `delta / other` — so tag counts
   are not comparable across verdicts, and `gamma`/`detached dots` counts are
   depressed exactly where scanner and chain disagree. Bounded: only 13 items
   (2.6 %) fall below 1.0 image points per cm.

### 17.5 The harness

**Five concurrent headless browsers exhaust the WebGL context budget**, and the
harness neither detects the loss per-item nor retries — it reports
`(regl) context lost` in an end-of-run summary naming nothing, and writes the
degraded PNG without complaint. §13.2 has the measurement and the workaround.

**`do_apply` could add a pin but never take one away** — *fixed in this round.*
The spec is the whole statement of an item's state, but the pin branch only had
`pin_rr` and `pin` arms: an item whose spec declines a pin left whatever pin was
already saved. That made `apply` non-idempotent, so re-running it over a
corrected spec silently kept the old stop. `scan_harness.py` now clicks
**`unset pin`** in the else branch; `clear_pin()` is a no-op when nothing is
pinned, so the other 508 items are unaffected. §17.6 is the case that found it.

### 17.6 Two defects of mine in the round's own tooling

Both were caught by `verify_scan_record.py` over the merged 569 rows, which
named **three** mismatches where only the owner's two live pins were expected.

1. **A spec cut from a wave that was still writing.** `mkspec.py` snapshotted
   `spec_1.json` at 13:03:29; the scanner's record for `039349_82/60` was
   rewritten at **13:09:16**, six minutes later. The captured version asked for
   `pin_rr = 4.0`; the scanner's final record declines it, opening *"Declined
   overshoot candidate, and this is the hard call."* Both versions call the item
   `STM_ONLY / none` — they differ **only** on whether to move the stop — so the
   app placed a pin (rr 4.2, stop moved 3.86 cm) the scanner had decided
   against.

   Measured over all 509 applied items against the final records: **verdict 0,
   `michel_kind` 0, tags 0** differ; `pin_rr` **1**; notes 5. The physics content
   of every row is intact. The item was re-applied through the real widgets from
   the corrected record (pin now `placed: false`, `source: fit-end`, moved
   0.00 cm) and the patch proved the other 568 rows byte-identical.

   *Why the earlier check missed it:* the per-row check compared the label on
   disk against **the spec**, proving the apply was faithful — which it was. It
   could not see that the spec itself was stale. The comparison that matters is
   spec-against-record, and it now runs over all 509.

2. **Non-deterministic duplicate resolution.** `v_parts/` holds **517 files for
   509 items** — eight were scanned twice, when a re-spawned wave covered items
   another scanner had already banked. Seven pairs agree exactly; one does not
   (`039349_62/63`: `STM_MICHEL/attached` in wave 7, `STM_ONLY/none` in wave 8 —
   a genuine inter-scanner disagreement, and the one quoted in §16.1). Three
   scripts read that tree with `os.walk` + `recs[key] = r`, i.e. **last-writer-
   wins in filesystem order**, so two runs could publish different rows.

   That mattered concretely: the chain has `is_stm=1, michel_found=0` here, so
   `STM_ONLY` yields no failure row while `STM_MICHEL` yields a
   `D_michel_false_negative`. `t2/resolve.py` now collapses the 517 to 509 once,
   breaking the tie to **whichever record matches the label the app actually
   wrote** — not a judgement about which scan is better — and refusing rather
   than guessing when it cannot. `mkfailures.py` reads only the committed record
   and no longer touches the scratch tree, so anyone can regenerate it.

   The pushed register was checked, not assumed: regenerating it deterministically
   reproduces the committed `pdvd_stm_michel_failures.tsv` **byte-identically**,
   so the non-determinism never reached published output — but it was correct by
   walk order, not by construction.

   Both readings of all eight pairs are kept in
   `pdvd/docs/scan/pdvd_stm_michel_duplicate_scans.tsv`, with the one `resolve.py`
   selected marked. They are worth reading as free repeat measurements: beyond
   `039349_62/63`, two pairs agree on verdict, kind and every tag but disagree on
   **confidence** (`039349_71/43` high vs medium, `039349_71/51` medium vs low) —
   which is the §16.2 point about the softer fields, arrived at independently.

---

## 18. What to do next

1. **Apply the §15.1 cut.** Purity 0.740 → 0.893 for two points of efficiency,
   using fields that already exist. This is the cheapest real improvement the
   round found.
2. **Run one blind tranche.** Suppressing `is_stm`/`reject_names` from
   `context.json` is a one-line change; it converts §14 from a review into a
   measurement.
3. **Fix the rubric's charge anchors** (§17.3) and state the plateau ratio, the
   coexistence test, the destination test and the ramp test — four scale-free
   discriminators the scanners built and independently reproduced.
4. **Decide `straddles the stop`** (§17.4.2) before tranche 3: either it is the
   split-row tag or it is not, but the rubric must not say both.
5. **Adjudicate the queue.** `pdvd/docs/scan/pdvd_stm_michel_owner_queue.md`
   lists every moved pin, every undershoot, every chain disagreement and every
   low-confidence row — the rows where a second opinion changes something.
