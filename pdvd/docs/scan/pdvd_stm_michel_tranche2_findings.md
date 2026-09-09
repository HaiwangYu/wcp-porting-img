# Tranche-2 round: found, reported, not fixed

## 0. How good are these labels? A double scan says: exactly as good as the confidence flag claims

The first scan wave was discarded because the rubric moved under it, and the
same 60 items were re-scanned by **different agents against the frozen rubric**.
That accident is the most informative measurement in the round: 57 items scanned
twice, independently, with no scanner able to see the other's verdicts.

| | agreement |
|---|---|
| verdict | **53/57 (93 %)** |
| `michel_kind` | 52/57 (91 %) |
| per-object tag | 350/387 (90 %) |

Stratified by the scanners' **own** confidence, which is the part that matters:

| both scanners said | verdict agreement |
|---|---:|
| `high` | **24/24 (100 %)** |
| at least one `medium` | 29/31 (94 %) |
| either `low` | **0/2 (0 %)** |

Every one of the four disagreements is on an item at least one scanner flagged
`medium` or `low`; not one high-confidence call moved. So the confidence field
is not decoration — it is a calibrated reliability estimate, and a reader can
use it directly: **the `high` rows are reproducible, the `low` rows are
coin-flips and are meant to be read as such.**

The four that moved, with both readings, are the rows worth the owner's eye:

| item | first scan | re-scan |
|---|---|---|
| `039252_13/66` | THRU (medium) | MESSY (medium) |
| `039252_17/91` | STM_ONLY (medium) | THRU (low) |
| `039252_3/45` | STM_MICHEL (medium) | THRU (low) |
| `039252_6/100` | STM_MICHEL (medium) | STM_ONLY (medium) |

`039252_6/100` is the instructive one: both scans agree the chain's own Michel
object sits across a **9.4 cm clean gap** that `f_meas` shows is not dead in any
plane; they disagree only on whether a 4.8 MeV piece that far out is the
electron or a capture gamma. That single rubric sentence — the attachment
tie-break — is what separates `STM_MICHEL` from `STM_ONLY` here.

A caveat on reading this as a general number: these 57 items are the first
sequential slice of the sheet, not a random sample of the 509, and the first
scan was taken under a rubric that was still moving. It is a lower bound on the
frozen-rubric reproducibility, and it is measured on 11 % of the round.

### The pin is the least reproducible thing in the scan

Verdicts agree 93 %, but on the same 57 items the two scans placed a pin on six
and **agreed on three**:

| item | first scan | re-scan | |
|---|---|---|---|
| `039252_16/32` | rr 3.3 | rr 3.3 | exact |
| `039252_16/98` | rr 2.9 | rr 3.4 | 0.5 cm |
| `039252_16/110` | rr 3.0 | rr 3.6 | 0.6 cm |
| `039252_0/75` | rr 2.4 | **none** | re-scan withdrew it (clustering split, not a gap) |
| `039252_15/81` | none | **rr 2.2** | first scan did not see it |
| `039252_2/39` | rr 7.2 | rr 11.1 | 3.9 cm apart |

So *where* a stop gets corrected is a much softer judgement than *whether* the
item is a stopper: when both scanners agree a pin belongs, they place it within
0.6 cm, but they disagree about whether one belongs at all on half the cases.

This bears directly on doc 55 §7, which publishes three pinned rows and their
distances as a measurement of the fit's stopping error. Those distances should
be read as one scanner's placement, not as a reproducible quantity — the
verdict-level claim ("the fit's stop is wrong here") is far more robust than the
centimetre value attached to it.

**Reported, not fixed.** The obvious remedy — two scanners on every pinned row —
was not affordable at 509 items in this round.

## 1. Five concurrent headless browsers silently lose the WebGL context

**Symptom.** Two of the five parallel `scan_harness.py shots` processes ended
with `JS ERRORS: ['(regl) context lost', ...]`. The harness prints that summary
only when the run *finishes*, so it names no item.

**Effect.** 21 of 2036 3-D frames, over **10 of the 509 items**, came out as an
empty canvas. This is the dangerous class of failure for a hand scan, because a
blank 3-D panel is not obviously broken — *"no charge near the stop"* is itself
a meaningful reading, and a scanner handed a blank `c_3d_stop.png` would record
`STM_ONLY` with high confidence and never know.

**Why file size does not detect it.** A genuinely sparse cloud also compresses
to ~7 kB: `039252_15/81`'s `b_3d_wide.png` is 7079 bytes and shows a real, faint
track. A size threshold at 12 kB flags 158 items, of which 148 are fine.

**The blank canvas is only the visible tip.** The first detector keyed on the
fact that every *fully empty* lost-context frame is the same canvas, so it is
byte-identical to every other one; that separated 21 blank frames from 2015 with
no false positives, and 10 items were re-shot.

**That test was insufficient, and a scan-wave scanner caught it.** The same
context loss also produces a *degraded* render — a smeared solid wedge and a
filled grey plane where the point cloud should be (confirmed by eye on
`039252_12/114`). Those frames are **unique per item**, so no byte-identity test
can see them, and they are not unusually small either, so the size heuristic
misses them too. The scanner found 5 such items among its 12.

**The reliable predictor is the process, not the frame.** All 5 degraded items
came from `chunk_0` or `chunk_3` — the only two of the five parallel shots
processes whose logs contain `(regl) context lost`. The other 7 items came from
chunks 1, 2 and 4 and all rendered correctly: 5 of 5 against 0 of 7. Every one
of the 10 already-known blank items is also in chunk_0 or chunk_3.

So **a lost context degrades much of the losing process's output**, and only the
fully-empty subset is detectable frame-by-frame. chunk_0 + chunk_3 is **204 of
the 509 items**, of which only 10 had been re-shot.

### The measurement that settles it

A degraded frame is a *smeared* render — solid wedges and filled planes instead
of a resolved point cloud — so it has far fewer distinct colours than a real
one. Counting unique colours in `c_3d_stop.png` across all 509 items separates
the two populations completely:

| shots processes | items | min | p10 | median | p90 | below 1000 |
|---|---:|---:|---:|---:|---:|---:|
| clean (1, 2, 4) | 305 | 1168 | 2674 | 3877 | 5484 | **0** |
| context-lost (0, 3) | 204 | 381 | 474 | **722** | 902 | **187** |

Zero false positives over 305 clean items, 187 of 204 caught, and every one of
the 187 is in process 0 or 3 (95 and 92). The 17 remaining lost-process items
sit above the threshold — presumably rendered before their context was lost —
which is why the *process* rule is the one to act on and the colour count is the
confirmation.

Re-shooting the same items with two concurrent processes restores them: on four
independently-reported bad items the unique-colour count goes from 522–724 to
3136–5838, and the smear resolves into points.

This also absorbs a failure that was reported separately as "3-D zoom-to-stop
silently failed on ~194 items". It is the same defect: a smeared render of a
zoomed view is indistinguishable from an unzoomed one, the three items named
were all from processes 0 and 3, and re-shooting fixed them.

**Why it matters beyond those items.** The rubric makes the three 3-D azimuths
*the* instrument for the transverse-offset judgement that separates `michel`
from `delta / other`. On 42 % of the sample that instrument was silently
degraded. The scanner's own verdicts did not turn on it — four of its five were
flat-profile `THRU` resolved on the dQ/dx panel — but on a contained stop with
an ambiguous blob it would produce a wrong tag with no visible symptom.

**Handled here** by re-shooting all 204 items from both affected processes in
two concurrent processes rather than five, and by replacing the frame-level test
with the process-level rule: *if a shots process logged `(regl) context lost`,
every item it produced is suspect.* Records already written against degraded
frames are discarded and those items re-scanned.

**Not fixed, and now the more serious version of the same gap:**
`scan_harness.py` reports `(regl) context lost` only in an end-of-run summary
that names no item, and writes the degraded PNG without complaint. A harness
that aborted the item — or even just recorded which items were rendered after
the first context loss — would make this self-detecting instead of something a
downstream reader has to infer from a log-to-chunk correlation.

**Not fixed:** `scan_harness.py` itself neither detects the loss nor retries the
frame, and it reports the error too late and too anonymously to act on. A
`do_shots` that checked the canvas for content before writing the PNG — or that
simply retried once on `context lost` — would close this. That is a harness
change and is not made in this round.

**Bearing on the human scanner:** the owner runs one browser, so they will not
hit the context budget. This is a harness-parallelism defect, not a display
defect.

## 2. The fit also stops SHORT, and that manufactures false STM+Michel

Doc 55 §7 records one direction of stopping-point error: the fit **overshoots**,
bridging a gap between the muon's stop and the Michel, so the profile peaks
several cm early and then collapses. Three of 60 tranche-1 items were pinned for
it.

The first calibration pass found the **opposite** case, twice in twelve items:

> the Bragg peak sits 1–3 cm **past** the fit's last point, in a short
> high-charge piece lying straight ahead (`cos_fwd` +0.87 and +0.97, `dstop` a
> couple of cm) at 0.9–1.2e5 e/cm — and **the chain types that piece `pdg 11`
> and offers it as the Michel**.

A ~2 cm piece at 1e5 e/cm is not an electron: an electron's first centimetres
sit at or below MIP, and 1e5 is four to six times that. It is what the muon's
own last centimetres look like. So the fit ended early, the tip is the muon, and
an item that is really `STM_ONLY` is presented by the chain as `STM + Michel`.

**This is a false-`STM_MICHEL` generator**, and it is the direction that inflates
the flag's efficiency while destroying its purity — the opposite of the
overshoot, which loses real Michels. At 2 of 12 it would fire on the order of
85 times in 509; the round counts them (`--notes` beginning `UNDERSHOOT:`) and
the count is reported in the doc rather than estimated from twelve items.

**Not fixed, and one limitation is structural:** `--pin-rr` slides the pin along
the fit and **cannot move it past the fit's last point**, so the corrected stop
cannot be recorded at all. The scan works around it by tagging the tip `muon`
and noting where the true stop is, but the label file has no field that carries
it. A pin that can sit past the fit end — or an "extend the fit" affordance —
would be a display change and is not made in this round.

## 3. `michel_kind` is inconsistent within the tranche-1 record

The calibration compared a blind rescan of 12 frozen rows to the rows
themselves. Verdicts agreed 11/12 and per-object tags 94/95, but `michel_kind`
agreed only 7/12 — and the disagreement was systematic, not noise.

The rule that reproduces **56 of the 60** frozen rows is mechanical:

| tagged | kind |
|---|---|
| `michel` and `gamma` | `both` |
| `michel` only | `attached` |
| `gamma` only | `detached dots` |
| neither | `none` |

Note what that says: an `STM_ONLY` item with capture gammas past the stop is
`detached dots`, **not** `none` — the field describes the topology of the
decay-related charge, not "is there a Michel". Eight tranche-1 `STM_ONLY` rows
use it that way.

The 4 rows that break the rule are not a subtler rule, they are the same
configuration labelled two ways:

* `039349_54/54` — attached arm plus dots at 14 cm and 50 cm → `attached`
* `039253_14/49` — attached arm plus specks at 34–55 cm → `both`

**Reported, not fixed.** The 60 rows are the owner's validated record and one of
the four (`039349_7/67`, scan 498) carries their explicit *"498 Looks good"*, so
they are left exactly as they are. Tranche 2 applies the mechanical rule, which
`t2/mkv.py` now **enforces at write time** — it refuses a record whose kind
contradicts its own tags. The consequence for anyone counting the field across
all 569 rows is that 4 tranche-1 rows say `attached` where the tranche-2
convention would say `both`.

## 2b. The undershoot is a chain FALSE-NEGATIVE mechanism — and it explains the owner's scan 474

The undershoot census can be closed exactly, because the signature is a table
query, not an impression. Over all 569 payloads, asking for a segment that is
**forward** (`cos_fwd ≥ 0.85`), **short** (≤ 6 cm), **at the fit end**
(`d_min ≤ 2 cm`) and **above 1.67 × MIP** returns **5 objects**, and the
population is cleanly bimodal — the next candidate below them sits at 1.48 MIP,
so the boundary is the data's, not a threshold anyone chose:

| item | chain verdict | segment | dQ/dx | × MIP | len |
|---|---|---|---|---:|---:|
| `039252_5/73` | rejected `shape_flat` | 73013 | 131326 | 2.43 | 4.2 cm |
| `039349_66/78` | rejected `no_bragg`, `shape_flat` | 78041 | 120416 | 2.23 | 1.8 cm |
| `039253_13/39` | rejected `shape_flat` | 39009 | 119207 | 2.21 | 2.4 cm |
| `039349_18/33` | rejected `shape_flat` | 33010 | 118139 | 2.19 | 1.3 cm |
| `039253_0/110` | rejected `stop_near_boundary` | 110007 | 99976 | 1.85 | 3.0 cm |

**The chain rejected all five.** That is the finding: when the fit stops a
centimetre or two short, the Bragg peak lands *outside* the fitted trajectory,
so the chain's shape tests measure a profile that is flat at MIP to its last
point and reject a genuine stopping muon. Four of the five are rejected on
`shape_flat`, which is exactly the symptom that mechanism predicts.

Scanners reached three of these independently and blind (`039252_5/73`,
`039253_13/39`, `039253_0/110` all carry `UNDERSHOOT:` notes), and a calibration
scanner flagged `039349_66/78` as the same thing before the frozen round began.

### It explains the owner's own reading of scan 474

`039349_66/78` **is scan 474**, which the owner reviewed on 2026-09-09:

> *"474 is OK, the Bragg peak is not as consistent, but I feel the scan is OK"*

The structure says why. The muon body (`78040`) runs 84 cm at 53228 e/cm — flat
on the MIP plateau — right up to the fit's last point. The Bragg peak is not
ragged or inconsistent: it is a **1.8 cm piece at 120416 e/cm (2.23 × MIP)
sitting 0.0 cm past the fit end at `cos_fwd +0.97`**, which the fit excluded.
The owner read "the rise is there but the profile doesn't show it cleanly", and
the mechanical reason is that most of the rise is not in the fitted profile at
all.

The tranche-1 record already tags `78041` as `muon`, which is the correct
attribution under the undershoot rule, so no label changes. What changes is the
*interpretation*: 474 is not a stopper with a poor Bragg peak, it is a stopper
whose fit ended 1.8 cm early — and the chain's `no_bragg` on it is a false
negative with an identified cause.

### This closes the audit opened in §3e5

The rubric's contradictory "four to six times MIP" clause **could not have
suppressed any undershoot**. The entire candidate population above the correct
absolute band is these 5 objects; every scanner that met one flagged it; and the
gap to the next candidate (1.85 → 1.48 MIP) means no borderline case was
decided by the wrong multiplier. The census stands at **5 in 569 (0.9 %)**.

## 2c. The hot last point is real charge, not a step-length artefact

A scanner flagged a shape it was uneasy about — a single very high **last** fit
point on an otherwise dead-flat profile — noting that three of its `THRU` rows
would move together if it had read it wrongly. The worry is fair, because the
obvious mechanism is arithmetic: dQ/dx is charge per unit length, so a final
step whose length is under-measured inflates the last point with no extra
charge.

That mechanism is **ruled out**. Comparing the final step's arc length against
the typical step on the same track:

| terminal point | items | last step ÷ typical (median) | p10 | p90 |
|---|---:|---:|---:|---:|
| hot (≥ 2× the preceding median) | 79 | **1.00** | 0.88 | 1.27 |
| ordinary (< 1.2×) | 331 | **1.00** | 0.92 | 1.27 |

Indistinguishable. The hot last point is genuine charge, so reading it as Bragg
evidence is legitimate.

What stays ambiguous is the different question of whether **one point** is a
*rise*. The rubric asks for a rise over the last 10–20 cm, and a single elevated
sample is not that however real its charge. Fifteen items show the extreme form
(last point ≥ 2× the median of the ten before it, those ten flat within a factor
of two) and they split across verdicts — uncontroversial on scanner-called
stoppers, load-bearing on the `THRU`s. Worth reading as a group; the list is
enumerable, not impressionistic.

## 3b. `g_dqdx` omits objects the object table lists — and they are the ones the undershoot check needs

Two scanners found, independently, that objects present in `context.json` do not
appear on the dQ/dx panel at all. Verified by zooming the exact arc-length band
where the points must fall and finding it blank:

* `039252_5/73` — `73013`, 8 points at **1.31e5 e/cm**, `d_min 0.0`: the band
  `s = 0…−4` is empty at 6× magnification;
* `039253_13/39` — `39009` (1.19e5, `s = 0…−2.3`) and `39005` (27 points,
  5.4e4, `s = −2…−13`), both bands empty.

The absentees look to be **fitted daughter segments** (empty `dstop`, a chain
`pdg` type), while unfitted clusters were drawn everywhere either scanner
looked — but two fitted segments *did* appear, so that rule is a hypothesis, not
established, and `39005` is backward at `cos_fwd −0.81` and still missing.

**Why this one bites hardest.** The undershoot check (§2) is precisely a search
for a short, very-high-charge object just past the fit end — and that is the
class being dropped from the panel. A scanner reading charge off `g_dqdx` alone
is blind to the exact object the check depends on. Across the 509, **24 items
carry a non-muon object at `d_min < 0.5` and `cos_fwd > +0.85`, of which 4 carry
more than 9e4 e/cm** (`039252_5/73`, `039253_0/110`, `039253_13/39`,
`039349_18/33`) — a small, checkable list rather than an estimate.

Handled in the round by making the object table, not the panel, the census: the
frozen rubric says so explicitly. **Not fixed** in the display.

## 3c. `THRU` conflates "no Bragg rise" with "no measurement" — a limitation, bounded

The frozen rubric makes `THRU` turn on a flat profile to the last point, and
explicitly warns scanners off reaching for `UNCLEAR` to avoid saying it. A
scanner objected, correctly, that on charge-starved items *"no Bragg rise"* and
*"the profile is unmeasurable"* are the **same items**, and the record has no
field that separates them: a `THRU` called on a track with 5 points/cm and a
clean declining profile sits in the same bucket as one called on a track whose
wire plane is 40 % dead.

**The rubric was not changed** — it is frozen mid-round, and moving it again
would split the sample the way the discarded first wave was split. Instead the
class is bounded after the fact from data already in the scan sheet.

Image points per centimetre of track, over all 509 tranche-2 items:

| min | p05 | p10 | median | p90 | max |
|---:|---:|---:|---:|---:|---:|
| 0.49 | 1.36 | 1.57 | **1.67** | 1.70 | 1.82 |

The distribution is tight, and only **13 items (2.6 %) fall below 1.0 points per
centimetre**. So the ambiguous class is small and enumerable rather than
pervasive, and the sparsest items can be listed in the doc and excluded from any
number that depends on the profile being readable.

The scanner's own judgement is corroborated by this: the item it named as
charge-starved, `039252_13/74`, is the **second sparsest of all 509** at 0.53
points/cm. It reached that from the picture, without the sheet.

**Recommended for the next round, not done here:** a `THRU_UNMEASURED` verdict,
or a required "profile readable?" flag, so the two cases are separable in the
record rather than only in free text.

## 3e. `cos_fwd` becomes meaningless the moment a pin moves

`cos_fwd` is measured against the track's tangent **at the fit's last point**.
After an overshoot correction that tangent is inside what has just been
reclassified as the electron, so every `cos_fwd` in the table now refers to an
axis the scan has rejected.

Concretely, on `039252_2/39` (pin moved to rr 11.1): segment `39003` tables at
`cos_fwd −0.91`, which the delta rule condemns outright as body activity — but
re-derived from the corrected stop it sits 3.1 cm out, squarely inside the
michel radius. A scanner following the letter of the tag table after moving a
pin will mis-tag the very objects the pin move was about.

The frozen rubric's trap 5 warns that `cos_fwd` misleads on *curved* tracks; it
does not cover this case. The scanner who hit it re-derived all tags from the
corrected stop by hand and reported that none changed — but that was its own
initiative, not something the rubric asked for.

**Reported, not fixed.** The clean solution is for the harness to recompute the
object geometry against the moved pin and re-emit `context.json`; `context_of()`
already takes the pin as an argument, so this is a small change, but it is a
harness change and this round does not make it.

## 3e2. Scanners resolved the same pin ambiguity by different tests

The frozen rubric's collapse clauses do not compose into a decision procedure.
It says the depth "is not a threshold", that the charge must fall "far below the
muon's own plateau", quotes an observed 0.15–0.5-of-MIP band, and separately
calls a last point 20–30 % low "ordinary scatter". A decline landing at ~0.7 of
plateau falls in none of those buckets, and that case is common.

Scanners closed the gap, but **not with the same test**:

* *sustained sub-plateau extent* — a decline that passes back up through the
  plateau is not a bridge (used on four items in one chunk);
* *the destination test* — is there an object row at `dstop ≈ 0` for the fit to
  have bridged **to**? (used to withdraw a pin on `039252_3/75`);
* *gap confirmation in the 3-D azimuths* — is the collapsed stretch actually
  empty, or is it a clustering split with the charge held by an overlapping
  segment? (used to withdraw a pin on `039252_0/75`).

All three are defensible and all three are absent from the rubric. This is the
mechanism behind §0's pin irreproducibility (agreement on 3 of 6): scanners
agree closely on *where* a stop is once they agree one moved, and disagree on
*whether* it moved because they are applying different tests to decide it.

**Reported, not fixed.** The next round should name one test — the destination
test is the most objective of the three, since it reads a table column rather
than a picture.

## 3e3. The THRU tag rule couples the verdict to the tag counts

The frozen rubric's THRU convention (fitted chain segments `muon`, everything
else `delta / other`) exists so that `gamma`/`michel` cannot assert decay charge
past a stop that does not exist. But it has a consequence worth stating before
anyone reads the round's tag totals: where the **chain itself** identified a
capture gamma and the scanner called `THRU`, that object is recorded
`delta / other`.

So the round's `gamma` tag count and its `detached dots` kind count are
systematically depressed exactly on the items where scanner and chain disagree
about whether there is a stop at all. The verdict and the tag are not
independent, and the tag totals must not be read as an unconditional census of
capture gammas.

## 3e4. `reject_names` inverts its meaning on every accepted item

A scanner flagged this and it checks out across all 569 payloads:

| `is_stm` | `reject_names` | items |
|---|---|---|
| 1 | `('STM',)` | **153** |
| 0 | `('no_bragg', 'shape_flat')` | 246 |
| 0 | `('shape_flat',)` | 56 |
| 0 | … real rejection reasons … | rest |

`reject_names` contains the literal string `STM` **only** when `is_stm == 1`, on
all 153 accepted items and nowhere else. So on every item the chain *accepted*,
the field named "reject_names" carries the accept tag; everywhere else it lists
genuine rejection reasons (`no_bragg`, `shape_flat`, `plateau_off_mip`,
`stop_near_boundary`, `profile_sparse`).

A reader who takes the field at its name reads the chain's verdict **backwards
on exactly the items that matter most** — the 153 it flagged as stopping muons.
The scan is unaffected: `is_stm` is the field the rubric points at, and the one
scanner who noticed said so explicitly. But this is a live trap for anyone
analysing the payloads, and it is worth a rename or a doc line.

## 3e5. The undershoot rule states its charge threshold two ways, and one is wrong

The frozen rubric describes the undershoot tip as *"four to six times MIP"* and
also as *"0.9–1.2e5 e/cm"*. Those are not the same test. Measured from the
display's own reference curve (`dqdx_ref_pdvd.json`), the muon MIP plateau is
**~5.4e4 e/cm** (54928 at 50 cm residual range, 53966 at 80 cm). So:

* the absolute band 0.9–1.2e5 is **1.7–2.2× MIP** — which is the real signature,
  and matches every tip actually found (`039252_5/73` at 1.31e5 = 2.4× its own
  plateau; `039253_13/39` at 1.19e5 against a 7e4 plateau);
* *"four to six times MIP"* demands **2.2–3.2e5**, which no real tip reaches.

A scanner applying the multiplier literally would find **zero** undershoots.
The error was inherited from the wave-1 calibration write-up and frozen with the
rest of the rubric.

**Not corrected mid-round** — the rubric is frozen and the correct absolute band
is stated alongside, so the two clauses disagree only in a region no candidate
has yet occupied (a tip between 1.2e5 and 2.2e5 would pass one and fail the
other). Every rejection recorded so far was made on grounds that fail *both*
tests. **The audit is owed at the end of the round**: re-examine every item
carrying a forward, near-stop object above 0.9e5 and confirm no undershoot was
dismissed on the multiplier alone.

## 3e6. The undershoot's `pdg 11` expectation is too narrow

The rubric's template says the chain types the mis-attributed tip `pdg 11` and
offers it as the Michel. On `039253_13/39` the chain typed it **`pdg 2212`** (a
proton). A census keyed on `pdg 11` would have missed that item entirely — the
load-bearing evidence is the charge and the geometry, not the chain's type.

## 3e7. The object table's `d_stop` column is wrong on 1.9 % of segments, and carries a raw sentinel on one

A scanner noticed that on `039253_0/87` the row for segment `287009` showed
`dstop 52.4` while the object's own centroid and the harness's `d_min`/`d_max`
put it at 159 cm. It used the geometry and flagged the column. It was right.

The segment rows' `dstop` is read straight from the payload's
`pf.seg_rej[<id>].d_stop` (`stm_michel_viewer.py:2058`) — the chain's own
rejection bookkeeping — while the harness's `d_min`/`d_max` are computed from
the actual points against the pin. Checking every segment that has both, over
all 569 payloads:

* **854 segments checked, 16 (1.9 %) disagree by more than 5 cm**;
* two are catastrophic: `039349_33/66` seg `243040` reads `d_stop 32.5` where
  the points are at **160.1 cm**, and `039253_0/87` seg `287009` reads 52.4
  against **159.0 cm**;
* and one carries an unfiltered sentinel: `039349_10/54` seg `214040` has
  **`d_stop = 1e8`**, which the display would render as `100000000.0` in the
  `d_stop` column. True distance 24.7 cm.

Most segments are fine, so this is a tail defect rather than a broken column —
but it is a tail that lands exactly on the far-speck calls, which are the ones
the rubric already flags as flipping `michel_kind`. A scanner trusting `dstop`
over the geometry on one of those 16 would tag it from a distance that is wrong
by up to 128 cm.

**Reported, not fixed.** The scan is largely insulated because the rubric points
scanners at `d_min`/`d_max` and `cos_fwd` for geometry; `dstop` is shown but not
load-bearing. Two things are owed upstream: find why `seg_rej.d_stop` diverges
(it looks measured against a different reference than the final stop), and
filter the 1e8 sentinel before it reaches a display column.

## 3e8. One item in the scan is probably not a muon at all

`039253_1/98` is a clean contained stopper with nothing past the end, so
`STM_ONLY / none` is the correct label under the alphabet — but the scanner
flagged it as a likely **non-muon**: 1.35–1.60e5 e/cm over the last 10 cm on a
6–8e4 body level, the chain's own reject is `not_muon_pid`, and its dQ/dx-based
and range-based energies disagree by 60 % (377 vs 236 MeV).

The verdict alphabet has no way to say "stopping *particle*, not a stopping
muon", so the row is right and the sample is still contaminated. Anyone using
the scan to count **muon** stoppers should treat this row — and any future
`not_muon_pid` row — as a contaminant rather than a signal.

## 3e9. Moving an overshoot pin FORCES `STM_MICHEL`, even when nothing is past the gap

This one has a verdict consequence, not just a tagging one, and it needs the
owner's adjudication.

The overshoot recipe says: when the profile collapses, the segment past the peak
is the Michel — tag it `michel`. But `michel_kind` is mechanical from the tags,
so `michel` ⇒ `attached` ⇒ the item reads as `STM_MICHEL`. There is **no route
through the schema for "the collapse is real, but there is nothing past it"** —
which is a physically ordinary outcome: the fit overshot into a sparse tail with
no decay electron, i.e. `STM_ONLY / none`.

`039349_10/58` is exactly that case and is the round's clearest instance. The
collapse is unambiguous — segment `58001` runs 19 points over 10.9 cm at a mean
18555 e/cm against 48831 / 42323 / 44642 for the track's other three segments,
the 3-D azimuths show the fit band running on alone past the end of the point
cloud, and the cropped `f_meas` U panels show measured charge stopping where
that band begins. The scanner moved the pin to rr 9.65, was then forced by the
schema into `STM_MICHEL / attached`, and recorded the competing reading in the
evidence at `medium` confidence rather than letting the label stand unqualified.

**For the owner:** if `039349_10/58` reads as `STM_ONLY / none`, the alphabet
needs a "bridged gap, nothing past it" option before tranche 3 — and every
overshoot pin in the round should be re-read for the same forcing. It is the one
place in this round where the label schema cannot express what the scanner saw.

## 3h. The `gamma` tag conflates two mutually exclusive processes

A scanner objected that `michel_kind: both` can record a physically
contradictory configuration — a Michel electron *and* muon-capture gammas from
the same muon. For a negative muon stopping in argon those are competing fates:
it either captures on a nucleus (gammas and neutrons, **no** Michel) or decays
(a Michel, no capture gammas).

The objection is half right, and the half that is wrong is the more interesting
part: **the `gamma` tag covers both classes and cannot tell them apart.**

* a **Michel-shower gamma** — bremsstrahlung radiated by the decay electron,
  lying along the Michel's own direction — coexists with a Michel perfectly
  well, and `both` is then the correct and common record;
* a **muon-capture gamma** — the nuclear de-excitation class of doc pdvd/51,
  compact and at the stop — excludes a Michel from the same muon.

The frozen rubric's `gamma` row describes the first ("isolated, past the stop,
clear of the muon body line") while doc pdvd/51's capture gammas are the second,
and a scanner is given no way to record which one it judged. So `both` is
sometimes the right physical statement and sometimes an impossible one, and the
record cannot distinguish the cases.

**Reported, not fixed.** This matters for anyone using the round's
`michel_kind` distribution to estimate a capture-to-decay ratio: that number is
not recoverable from these labels. Splitting `gamma` into `michel gamma` and
`capture gamma` would make it recoverable, and it is a display change.

## 3i. Four scanners independently replaced the reference curve with the track's own plateau

Not a defect — a convergent correction worth promoting into the next rubric.

The frozen rubric asks for a rise "above the track's own MIP plateau, following
the shape of the muon reference curve", and separately quotes collapse depths as
fractions "of MIP". Scanners repeatedly found the reference curve unusable as a
yardstick — it asymptotes to ~1.6e5 at the stop where real stoppers top out at
1.2–1.35e5, and `plateau_off_mip` tracks never reach the MIP line at all — and
**four of them independently adopted the same substitute**: judge every rise and
every collapse against *this track's own plateau*, scale-free.

One flagged it explicitly as "an extension I invented, not an application". It
is the single most reproduced methodological improvement of the round, it came
from the scanning rather than from the rubric, and it should be the stated test
next time.

## 3j. Two scanner claims that did NOT survive checking

Recorded because the round should be honest in both directions: scanners caught
several real defects, and they also produced two confident claims that the data
does not support.

**"`039349_0/28` sits above the reference curve, so the species may not be a
muon."** The first half is true — 18 of 40 points inside rr ≤ 23 exceed the muon
curve, running 1.2–1.3× above it between rr 4.8 and 14.4 cm. The inference is
not. Fitting the whole profile against each reference species over rr ≤ 25 gives
a median data/curve ratio of **0.92 for muon**, 0.88 electron, 0.87 pion, 0.65
kaon, 0.55 proton. The muon is by far the best match; the track sits *below* the
heavier-species curves throughout. The excursion is a localised feature, not a
species mismatch.

What is genuinely odd about that item is something the scanner did not name: a
**charge hole immediately before the fit end** — rr 1.2 to 3.6 cm collapses to
7 400–10 500 e/cm, a seventh of the surrounding level, with full charge on both
sides of it (1.0e5 at rr 0.0, 8.1e4 at rr 4.2). That is the gap signature, and
it belongs in the pin discussion rather than in a species argument.

**"These clusters are cut at the cathode, so they are fragments."** Three
scanners raised this on five items, citing `seams_at_stop.cathode` and quoting
distances of 0.3 to 2.2 cm. The field was misread: `seams_at_stop` is measured
at the **stop**, not at the track's start, and on those five items it reads
124.2, 60.4, 121.1, 315.5 and 16.0 cm.

The underlying observation is directionally right but smaller than claimed. The
actual entry-x values are **−3.3 to −7.2 cm**, so those tracks do begin a few
centimetres from the cathode. Across all 569 items the census is:

| entry within | items |
|---|---:|
| 1 cm of the cathode | **0** |
| 1–3 cm | 1 |
| 3–10 cm | 26 |
| > 10 cm | 542 |

So **27 items (4.7 %)** start within 10 cm of the cathode and none within 1 cm.
If the owner wants cathode-anchored clusters counted as `FRAG_*`, that is the
population it would affect — a bounded decision, not a pervasive one. No labels
were changed on this account, and the affected rows carry the observation in
their notes.

## 3k. The far-speck rule reads backwards on exactly the items it is needed for

A scanner found a logical inversion in the frozen rubric, and the physics is on
its side.

The far-speck paragraph says a distant speck is `gamma` when it lies **on the
Michel's side** and `delta / other` when specks are **scattered in unrelated
directions**. That is sound for *Michel-shower* gammas, which are radiated along
the electron's direction. But the paragraph is invoked most often on `STM_ONLY`
items — that is where `detached dots` lives — and an `STM_ONLY` has **no
Michel** to define a side. The gammas there are **muon-capture** gammas, and a
nuclear de-excitation cascade is **isotropic**: "scattered in unrelated
directions" is precisely what a real capture cascade looks like.

So on the class of items where the rule matters most, it assigns `delta / other`
to the signature it should be assigning `gamma` to. This compounds §3h: the tag
alphabet has one `gamma` value for two processes, and the disambiguating rule is
written only for one of them.

The scanner worked around it by falling back to the gamma rule's "past the stop"
clause — tagging a speck 1.7 cm behind the stop plane `gamma` and one 14.6 cm
behind `delta / other` — and said so in the record. Other scanners resolved the
same collision differently (§3e2), so this is a live source of tag disagreement,
not a settled convention.

## 3l. `plateau_off_mip` — 47 tranche-2 items the Bragg language does not describe

The frozen rubric's `THRU` test is "flat on the **MIP plateau** to its last
point", and its collapse depths are quoted as fractions of MIP. Both presuppose
the track reaches MIP. The chain itself says 50 of 569 items do not:

| chain reject reason | all 569 | tranche 2 |
|---|---:|---:|
| `shape_flat` | 375 | 354 |
| `no_bragg` | 294 | 282 |
| `STM` (= accepted) | 153 | 117 |
| **`plateau_off_mip`** | **50** | **47** |
| `profile_sparse` | 33 | 30 |
| `stop_near_boundary` | 27 | 25 |

On those **47 tranche-2 items (9.2 %)** the absolute charge scale is unusable,
and the rubric offers no clause. Scanners adopted a policy anyway — judge shape
only, against the track's own plateau, and say in the record that the level is
broken — and at least two flagged it explicitly as their own invention rather
than an application of the rubric. It is the same substitution as §3i, arrived
at independently again.

This is a bounded, named population: `plateau_off_mip` is a queryable field, so
those 47 rows can be separated at analysis time even though the rubric could not
separate them at scan time.

## 2d. The "high tip over a depleted stretch" shape is the overshoot, not an artefact

A scanner reported a recurring terminal shape — a high point at the very tip
with a *depleted* stretch a few centimetres behind it — on 4–5 of its 12 items,
and raised the possibility that it is reconstruction damage. If so it would
undercut the rubric's assumption that a terminal anomaly means a bridged Michel,
so it is worth settling.

Measured across all 566 items with enough live points, requiring the tip to be
≥ 1.5× the track's own plateau **and** the four points behind it to sit at
≤ 0.5× plateau:

**5 of 566 items (0.9 %)** — and they are:

| item | tip / plateau | points 2–5 back |
|---|---:|---:|
| `039253_13/73` | 2.50 | 0.40 |
| `039349_18/36` | 2.08 | 0.50 |
| `039349_81/45` | 1.92 | 0.44 |
| `039349_2/41` | 1.92 | 0.42 |
| `039349_0/28` | 1.75 | 0.20 |

That list is not a random sample of the round. `039349_18/36` is the tranche-1
overshoot the owner's doc pdvd/54 diagnoses and a blind scanner independently
pinned at rr 8.08; `039253_13/73` is an overshoot a scanner pinned at rr 8.2;
`039349_0/28` is the item whose pre-stop charge hole is described in §3j. **At
the strength where the shape is distinctive it selects the known overshoots**,
which is the opposite of an artefact hypothesis.

None of the scanner's own five items clears this threshold, so its 4-in-12 rate
is measuring a much milder version — and a mild terminal dip is exactly what the
frozen rubric already calls ordinary scatter. The conclusion is a threshold
statement rather than a yes/no: **the shape is real and diagnostic when strong
(≈1 % of items), and ordinary profile noise when weak.** The scanner's caution
was right; the artefact reading was not.

## 3f. The particle-flow overlay contaminates `f_meas` too, not just the 3-D frames

Display trap 2 (categorical particle-flow colours drawn over a charge-coloured
cloud) is written as a 3-D-frame problem. It is not: the same amber flow band is
drawn over the measured / predicted / difference panels, where it reads as high
measured charge. It is identifiable — it survives unchanged into the *difference*
panel, where genuine agreement goes white — but nothing tells a scanner that.

## 3g. The frame table's row count invites a false alarm

Every item directory holds **seven** PNGs (`a_proj_full`, `b_3d_wide`,
`c/d/e_3d_stop`, `f_meas`, `g_dqdx`), verified across all 509. The rubric's frame
table has **six rows**, because the three `*_3d_stop` azimuths share one. Two
independent scanners read the row count as a file count, concluded a seventh
frame had failed to generate, and spent time investigating a shot-generation
problem that does not exist.

Both read all seven frames regardless, so no verdict was affected — but a table
whose row count is mistakable for a file count cost two scanners real effort and
produced two confident, wrong defect reports. Worth splitting the row in any
future version.

## 3d. Residual rubric ambiguities, left in place deliberately

The rubric was frozen after two calibration waves and one discarded scan wave.
Scanners kept finding real gaps after that, and they were **not** fixed, because
a rubric that moves mid-round splits the sample into populations that cannot be
counted together. They are recorded here instead, with what each one actually
cost, and they are the agenda for the next round rather than this one.

**The 10–20 cm dead zone.** The michel rule's "direction does not discriminate"
radius stops at ~10 cm and the faint-far-speck rule starts at 20 cm, so a piece
at 13.7 cm is governed by neither and falls through to the general off-axis
paragraph — which was written for the michel-vs-gamma collision, not for "is
this decay-related at all". On `039252_10/103` that gap decided a `michel_kind`
value. One sentence covering 10–20 cm would close it.

**The overshoot's diagnostic and its mechanism can come apart.** The rule says
the collapse is the diagnostic and the mechanism is a gap the fit interpolates
across. On `039252_0/75` a scanner found the collapse *without* the gap: the last
2.4 cm fall to 0.09 of the peak, but at 7× magnification all three azimuths show
that region packed with image points, and two other segments occupy the same arc
range holding the charge the fit's points are missing. It is a clustering split,
not a bridged gap. The scanner had already written the pin, re-examined, and
rewrote the record without it — which is the behaviour wanted, but the rule as
worded ("the diagnostic is the collapse, not the height of the peak") invites the
error. **Next round: confirm the gap in the 3-D azimuths before moving a pin.**

**`ends.*.d_face` ignores the cathode.** `face_distances()` minimises over the
x/y/z envelope only, so an item anchored on the cathode reads as mid-volume:
`039252_12/44` enters 30 cm from the z face but **4.2 cm from the cathode**. The
cathode distance *is* available — `seams_at_stop.cathode` — just not folded into
`d_face`. Anyone using `d_face` alone to judge containment will misread
cathode-anchored items.

## 4. Display request: `g_dqdx` cannot distinguish "no charge" from "low charge"

Both calibration scanners independently named the same gap as the single change
that would have helped most. The dQ/dx panel plots fit points with **no measured
charge** identically to points with genuinely low charge, so the only way to tell
them apart is to cross-read `f_meas` looking for a bare fit line with no charge
under it. That is what made the hardest items hard — a 30–40 cm charge-free band
inside a "120 cm muon" reads as a real low-dQ/dx stretch until you check.

A per-point live/dead marker on `g_dqdx` would settle those items in one glance.
Display change; not made in this round.

## 5. Older tranche-1 shots carry no `ends` block

`shots2/` (the 60 tranche-1 items) has an empty `ends` in all 60 `context.json`
files; `shots_t2/` has it populated in all 509. So the calibration scanners
judged containment without `stop.d_face`, `is_stm` or `reject_names` and still
reproduced 11/12 verdicts. That makes the calibration agreement a **floor** on
what the tranche-2 waves can do, not a ceiling — they get strictly more
information. Harmless here, but worth knowing before anyone re-uses `shots2/`.
