# CheckSTM_Michel — the failure register from the doc pdvd/55 hand scan

Every failure the 569-item census turned up, as a **starting point for work on
the package** rather than a narrative. Each class is a query, so the list
regenerates and can be re-run after a fix to see whether the class shrank:

    cd wcp-porting-img
    python3 pdhd/stm_michel_scan/mkfailures.py     # rewrites the TSV below

The item-level data is `pdvd/docs/scan/pdvd_stm_michel_failures.tsv` — one row
per (item, failure class), with the chain's own `is_stm` / `reject_names` and a
detail string carrying the numbers. **445 rows over 251 distinct items.**

Scope: arm d53v, every `CheckSTM_Michel` candidate with ≥ 20 profile points and
≥ 10 cm of muon (`prep_stm_michel_scan.py:104-105`) — 569 items, all scanned.
The scan is *the chain's reconstruction reviewed by a physicist*, not blind
truth: see doc pdvd/55 §16.3 before using classes A–D as ground truth.

| class | rows | items | what it is |
|---|---:|---:|---|
| `A_is_stm_false_positive` | 9 | 9 | chain says stopping muon, scan disagrees |
| `B_is_stm_false_negative` | 125 | 125 | **scan says stopping muon, chain rejects** |
| `C_michel_false_positive` | 39 | 39 | chain reports a Michel, scan disagrees |
| `D_michel_false_negative` | 41 | 41 | scan sees a Michel, chain reports none |
| `E_michel_range_energy_impossible` | 32 | 32 | the reported Michel cannot be an electron |
| `F_fit_stops_short` | 5 | 5 | the Bragg peak lies past the fit's last point |
| `G_coiled_fit_end` | 18 | 18 | fit arc ≫ 3-D span at the end; dQ/dx denominator wrong |
| `H_fit_unsupported_by_charge` | 40 | 20 | a fitted segment ≥ 20 cm carrying < 0.25× plateau |
| `I_d_stop_wrong` | 15 | 9 | `seg_rej.d_stop` disagrees with the geometry by > 5 cm |
| `I_d_stop_sentinel` | 1 | 1 | a raw `1e8` reaches a display column |
| `J_not_a_muon` | 1 | 1 | `not_muon_pid`, yet a clean contained stopper |
| `K_stop_moved_by_scan` | 36 | 36 | the scan moved the stopping point |
| `L_plateau_off_mip` | 50 | 50 | charge scale not trustworthy |
| `L_profile_sparse` | 33 | 33 | charge scale not trustworthy |

---

## 1. The Michel admission gate has no energy test — classes C, E

**Where.** `clus/src/CheckSTM_Michel.cxx:1692-1719`, the loop that admits pieces
into the Michel object. Three gates, all geometric:

| gate | line | knob | default |
|---|---|---|---|
| `d_stop > michel_dot_radius_cm + companion_max_len_cm` | :1703 | both | 15 + 25 = **40 cm** |
| `segment_track_length > dot_max_len_cm` | :1706 | `dot_max_len_cm` | 25 cm |
| `d_body < d_stop` (a body fragment) | :1715 | `dot_body_exclusion_cm` | 5 cm |

**Nothing tests the piece's energy, or its energy against its distance.** A
40 cm acceptance radius is why pieces 9–15 cm from the stop are admitted, and
with no energy gate a 0.2 MeV speck at 14.9 cm is admitted on the same footing
as a 21 MeV arm at the vertex.

**What the census shows.** `michel_conn_type` already separates the two
populations cleanly:

| `conn_type` | n | `michel_dis_cm` median | `michel_len` median | KE median |
|---|---:|---:|---:|---:|
| 1 — attached (`:1551`, `dis` set to 0) | 113 | **0.00** | 6.49 cm | **21.4 MeV** |
| 2 — bridged (`:1748`) | 45 | **9.11** | 1.20 cm | **4.1 MeV** |

An electron born at the stop cannot travel 5 cm through liquid argon and deposit
under 10 MeV — range and energy contradict each other:

| | fails `dis > 5 cm` **and** `KE < 10 MeV` |
|---|---|
| `conn_type == 1` | **0 of 113** |
| `conn_type == 2` | **26 of 45** |

**Suggested change.** A fourth gate beside the existing three, after the
`d_body` test at `:1715`, rejecting a piece whose distance and energy are
mutually inconsistent — behind a default-OFF knob per the house rule, e.g.
`michel_range_energy_gate` with `michel_min_ke_beyond_cm` / `michel_min_ke_MeV`:

    // a Michel is born AT the stop: a piece several cm away carrying only a
    // few MeV cannot be the electron that made the journey.
    if (m_michel_range_energy_gate
        && d_stop > m_michel_min_ke_beyond_cm * units::cm
        && segment_cal_kine_dQdx(seg, m_recomb_model) < m_michel_min_ke_MeV * units::MeV) {
        note_seg(sid, <new reject code>, d_stop, d_body); continue;
    }

**What it buys**, scored on the census (549 judged items):

| | TP | FP | FN | purity | efficiency | F1 |
|---|---:|---:|---:|---:|---:|---:|
| as shipped | 111 | 39 | 41 | 0.740 | 0.730 | 0.735 |
| require `conn_type == 1` | 99 | 10 | 53 | 0.908 | 0.651 | 0.759 |
| gate at 5 cm / 10 MeV | 109 | 18 | 43 | 0.858 | 0.717 | 0.781 |
| **gate at 3 cm / 10 MeV** | **108** | **13** | **44** | **0.893** | **0.711** | **0.791** |

The 3 cm / 10 MeV row is the recommendation: **purity 0.740 → 0.893 for two
points of efficiency.** Refusing `conn_type == 2` outright is blunter — more
purity, but it discards a tenth of the real Michels, so some bridged Michels are
genuine.

Start from the 32 rows of class `E` in the TSV; they are the ones the gate
removes.

---

## 2. The 1e8 sentinel escapes into the record — class I

**Where.** `clus/src/CheckSTM_Michel.cxx:1693-1704`. The code already documents
this exactly:

> *"`segment_get_closest_point` returns a 1e9 sentinel when the segment carries
> no usable point, and the body test below cannot catch it: on a chain shorter
> than `dot_body_exclusion_cm` the body distance is the same sentinel, so
> `d_body < d_stop` is false and the piece is kept with `michel_dis_cm = 1e8`
> cm (PDHD 028084_12 cluster 3, a 1.0 cm 3-point chain)."*

**The census confirms it reaches PDVD too**, and further than the comment
suggests: `039349_10/54` segment `214040` carries `d_stop = 1e8` into
`seg_rej`, from where the hand-scan display renders it as `100000000.0` in the
object table's `d_stop` column. The true distance is 24.7 cm.

**Suggested change.** Reject on the sentinel explicitly before the body test,
rather than relying on `d_body < d_stop` to catch it:

    if (d_stop >= 1e8 * units::cm) { note_seg(sid, <code>, d_stop, -1); continue; }

**And separately, `seg_rej.d_stop` is wrong on a tail** even without the
sentinel: 15 segments over 9 items disagree with the true 3-D distance to
`stop_pt` by more than 5 cm, two of them by over 100 cm (`039349_33/66` seg
`243040` reads 32.5 where the points are at 160.1 cm). Worth tracing what
reference that value is measured against — it does not look like the final stop.

---

## 3. The fit's stopping point — classes F, K, G

### 3.1 The fit stops SHORT, and it is a false-negative generator (F)

Exactly **5 items in 569** carry a forward (`cos_fwd ≥ 0.85`), short (≤ 6 cm)
segment at the fit end (`d_min ≤ 2 cm`) above 1.67 × MIP, with a clean gap to
the next candidate at 1.48 MIP:

| item | chain verdict | segment | dQ/dx | × MIP |
|---|---|---|---:|---:|
| `039252_5/73` | rejected `shape_flat` | 73013 | 131326 | 2.43 |
| `039349_66/78` | rejected `no_bragg`, `shape_flat` | 78041 | 120416 | 2.23 |
| `039253_13/39` | rejected `shape_flat` | 39009 | 119207 | 2.21 |
| `039349_18/33` | rejected `shape_flat` | 33010 | 118139 | 2.19 |
| `039253_0/110` | rejected `stop_near_boundary` | 110007 | 99976 | 1.85 |

**The chain rejected all five.** When the fit ends a centimetre or two short, the
Bragg peak lands outside the fitted trajectory and the shape test measures a
profile flat to its last point. `039349_66/78` is the owner's scan 474, whose
"Bragg peak is not as consistent" has exactly this cause (doc 55 §15.3).

**Suggested check.** Before `no_bragg` / `shape_flat` are set, look for a short
high-charge segment forward of the fit end; if one is there, the profile being
tested is the wrong profile. Cheap, and it is 5 items of pure false negative.

### 3.2 The scan moved the stop on 36 items (K)

Independent of F: on 36 items the scan judged the chain's own fit end wrong and
moved the pin back along the fit. **Caveats before treating these as truth** —
doc 55 §16.2 measures pin placement as the *least* reproducible thing in the
round (two scans agreed a pin belonged on only 3 of 6 shared items, though they
placed it within 0.6 cm when they agreed). Use the class as a candidate list,
not as a corrected-stop dataset.

Two quality checks were run over all 36 and both come back clean:

* **dead wires** — 9 have any dead-channel coverage over the collapsed stretch,
  **none in more than one plane**, so no pin rests on a collapse that dead
  channels could manufacture;
* **coiled ends** — only 1 of 36 sits on a coiled fit end.

### 3.3 The coiled fit end corrupts dQ/dx in both directions (G)

**18 items** pack ≥ 1.5× more fit *arc* than 3-D *span* into their last 20 cm
(max 3.41 — `039349_48/21`, 19.9 cm of arc inside a 5.8 cm ball). dQ/dx is
charge ÷ path length, so a coil inflates charge where the fit runs on and
suppresses it where it folds. **Both** fit-failure diagnostics read that
profile, so neither is reliable on these items.

**Suggested change.** `arc/span` over the last 20 cm is two lines from arrays
the chain already has. Publishing it — or setting a `profile_unreliable` reject
bit from it — would let a consumer skip the charge tests and fall back to
geometry, the way `plateau_off_mip` and `profile_sparse` already do.

---

## 4. The fit spans ground the imaging never covered — class H

**40 fitted segments over 20 items** are ≥ 20 cm long and carry under a quarter
of their own track's plateau. The extreme is `039253_6/82` segment `82041`:
**208.6 cm at 4363 e/cm — 0.114 of the plateau**, and that object has three such
segments (208.6, 78.2, 49.2 cm).

Nothing here is a *dead* fit point: over all 569 payloads there is not one item
ending in a run of `q ≤ 0`. The charge is present but tiny, so the fit is not
interpolating across a hole in the data — it is following something that is not
a track.

**Why it matters downstream.** This is the class the hand scan could place in
neither `THRU` nor `MESSY`: `MESSY` requires "no coherent spine", and these
objects have one — a *fitted* spine drawn through empty space. They fall to
`THRU` on "no Bragg rise", and one scanner wrote the consequence plainly:
*"my THRU bucket therefore contains objects that are not through-going muons."*
Any efficiency number computed against this scan inherits that.

**Suggested change.** Same shape as §3.3 — a per-segment
`charge_supported = dqdx_med / plateau_med` is already computable, and a segment
at 0.1 for two metres is a statement about the reconstruction, not about a muon.

---

## 5. `reject_names` inverts its meaning on every accepted item

**Where.** `clus/src/CheckSTM_Michel.cxx:747-751` builds the name list, and
`:953` sets `is_stm = (reject_bits == 0)`.

Over all 569 payloads, `reject_names` contains the literal string `STM` **only**
when `is_stm == 1` — on all 153 accepted items and nowhere else. Everywhere else
it lists genuine rejection reasons (`no_bragg`, `shape_flat`,
`plateau_off_mip`, `stop_near_boundary`, `profile_sparse`).

So on every item the chain **accepted**, the field named "reject_names" carries
the accept tag. A reader taking the field at its name reads the verdict
backwards on exactly the 153 items that matter most. The hand scan was not
affected — the rubric points scanners at `is_stm` — but this is a live trap for
anyone else analysing these payloads, and a rename or a doc line would close it.

---

## 6. The two flag-level error classes — A, B, C, D

These are the scored disagreements, and they are the reason for §1 and §3.1.
Scored over the 549 judged items (`MESSY` / `UNCLEAR` excluded):

| flag | TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|
| `is_stm` | 144 | 9 | 125 | 271 | **0.941** | **0.535** |
| `michel_found` | 111 | 39 | 41 | 358 | **0.740** | **0.730** |

**`B_is_stm_false_negative` is the big one: 125 items.** The mechanism is
measured in doc 55 §15.2 — the Michel *suppresses the signature the flag tests
for*. Among scanner-called stoppers, those the chain accepts score a
terminal-to-plateau charge ratio of 1.98; the 72 it rejects score **1.11**. The
chain is not erring arbitrarily: on those items the terminal rise genuinely is
weak *in the fitted profile*, which is why `shape_flat` is the dominant
rejection (354 of 509 tranche-2 items).

That points the fix at the **profile**, not the threshold: §3.1's short-stop
check, §3.3's coil flag and §4's unsupported-fit flag all attack the same root —
the profile being tested is not always a measurement of the muon.

**Read A–D with doc 55 §16.3 in hand.** Scanners saw `is_stm` and
`reject_names` before the frames, so agreement is anchored and these figures are
*optimistic*; the disagreement classes are correspondingly conservative. A blind
tranche — one line in `context_of()` plus regenerated shots — would turn them
from a review into a measurement.

---

## 7. Smaller items

* **`J_not_a_muon`** (1 item) — `039253_1/98` is a clean contained stopper the
  scan labels `STM_ONLY`, but the chain's own reject is `not_muon_pid` and its
  dQ/dx- and range-based energies disagree by 60 %. The verdict alphabet cannot
  say "stopping *particle*, not stopping muon"; anyone counting **muon**
  stoppers should treat it as contamination.
* **`L_plateau_off_mip` (50) and `L_profile_sparse` (33)** — not defects, but
  named classes where the absolute charge scale is not usable. The hand scan had
  no rule for them and scanners invented one (judge shape against the track's
  own plateau). Worth stating in whatever consumes these flags.
* **The object `size` field exceeds the whole track on 9 rows**, one by 4.9×
  (`039349_43/62` seg `188002`, 111.9 cm on a 22.8 cm track). `size` is honest —
  that row has two points 111.9 cm apart — so the defect is upstream, in whatever
  grouped two unrelated points into one object.
