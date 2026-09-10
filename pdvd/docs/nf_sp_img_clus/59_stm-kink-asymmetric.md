# 59 — T1b: the asymmetric kink in `find_first_kink`

**Status (2026-09-09). Behavior change, confirmed and flipped ON for PDVD
production (`stm_kink_asym_enable: true`, `stm_kink_asym_entry_mip: 1.2`,
`stm_kink_asym_far_mip: 0.5`, alongside T1a's `stop_retreat_max: 2` and T1c's
`stop_split_max: 1`, all in `pdvd/wct-pr-perevt.jsonnet`). PDHD and SBND stay
OFF — no PDHD STM/Michel hand-scan record exists to confirm it there, and
SBND is out of scope this round. Both byte-identical gates PASS (PDVD
579/579 vs `d58v`, PDHD 325/325 vs `d53h`); the feature arm is scored
against the frozen 569-item scan record.**

Doc pdvd/56 §2.2 found the fall-through to `find_first_kink`'s no-kink
sentinel is the normal path, not the exception (74 of 131 accepted stoppers,
29 of 51 collapse-shaped misses), because both of `find_first_kink`'s charge
gates require **both** arms of a candidate kink to carry >= 0.6 MIP -- the
two-track kink the prototype was ported to find. A muon stopping into a
Michel is the asymmetric case: Bragg on one side, 0.1-0.4 MIP on the other
(doc 54 §1.2's own example, `039349_18/36`: `sum_fQ` 1.77, `sum_bQ` 0.09,
sentinel). T1a and T1c (docs 57/58) both fix this downstream, in
`CheckSTM_Michel`, after the tagger has already produced its wrong stop; T1b
is the chance to fix it upstream, in the tagger's own kink search, before
`CheckSTM_Michel` ever sees the wrong stop.

Provenance: toolkit `f4980b08` before this round's edit; wcp-porting-img
`6038d466` (doc 58 + the T1a/T1c flip). Arms this round: `d58v`/`d53h`
(existing, the current production candidates), `d59vleg`/`d59hleg` (knob
off, new binary) vs `d59v` (knob on, PDVD only).

---

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/toolkit
wcbuild && ./build/clus/wcdoctest-clus            # 357 cases (354 -> 357)

cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
# the offline sizing probe, run BEFORE any C++ changed (section 1 below)
python3 pdvd/docs/nf_sp_img_clus/scripts/d59_kink_asym_probe.py

# the arms (PIN = a private snapshot of local/lib; feedback_shared_tree_binary_pin)
SPLIT='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0,stop_retreat_max:2,stop_split_max:1,split_kink_min_deg:15}'
SURVEY='-S stm_michel_extra={survey_enable:true,survey_radius_cm:60.0,survey_max_len_cm:25.0}'
KINK='-S stm_kink_asym_enable=true'
ARM=d59vleg DET=pdvd SRC=d16vnu JOBS=8 PIN=<pin> PR_TLA="$SPLIT" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
ARM=d59hleg DET=pdhd SRC=d16hnu JOBS=8 PIN=<pin> PR_TLA="$SURVEY" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh
ARM=d59v    DET=pdvd SRC=d16vnu JOBS=8 PIN=<pin> PR_TLA="$SPLIT $KINK" pdvd/docs/nf_sp_img_clus/scripts/d53_run_arms.sh

# byte-identical gates: d59vleg against d58v (the current PDVD production
# candidate, T1a+T1c both on) and d59hleg against d53h (PDHD's own baseline)
python3 pdvd/docs/nf_sp_img_clus/scripts/d51g_branch_census.py \
    --before 'pdvd/work/*_d58v'  --after 'pdvd/work/*_d59vleg' --before-arm d58v --after-arm d59vleg --pts --out /tmp/g1
python3 pdvd/docs/nf_sp_img_clus/scripts/d51g_branch_census.py \
    --before 'pdhd/work/*_d53h' --after 'pdhd/work/*_d59hleg' --before-arm d53h --after-arm d59hleg --pts --out /tmp/g2

# the feature arm, scored against the frozen scan record
cd pdhd/stm_michel_scan
./prep_stm_michel_scan.py --det pdvd --arm d59v --outdir $W/prep_d59v --sheetdir $W/sheet_d59v \
    --pin-tranche ../../pdvd/docs/scan/pdvd_stm_michel_scan_sheet.tsv
python3 census_score.py --prep $W/prep_d59v --arm d59v --json $W/d59v.json
python3 census_score.py --check   # baseline still 0 of 14 differ
```

---

## 1. Two charge gates, not one, and the offline sizing probe

`find_first_kink` (`TaggerCheckSTM.cxx:1570`) sweeps candidate rows twice.
Sweep 1's charge test (`:1821-1823`):

```cpp
if ((sum_fQ > 0.6 && sum_bQ > 0.6) ||
    (sum_fQ + sum_bQ > 1.4 && (sum_fQ > 0.8 || sum_bQ > 0.8) &&
    v10.magnitude() > 10*units::cm && v20.magnitude() > 10*units::cm)) {
```

and sweep 2's (the fallback if sweep 1's loop never returns), strict only
(`:1926`):

```cpp
if (sum_fQ > 0.6 && sum_bQ > 0.6 ){
```

`sum_fQ`/`sum_bQ` are 10-point charge-weighted MIP-fraction sums on either
side of a candidate row (10 points before, 10 after, point itself excluded),
normalized by `m_mip_dqdx`. Both `0.6`, `0.8`, `1.4` are bare literals, not
config members -- the file's own convention comment (beside `m_mip_dqdx`)
requires any new constant take the form `x * m_mip_dqdx`, which the existing
normalization already satisfies for a MIP-fraction threshold.

Sweep 1's OR-branch is a magnitude relaxation, not an asymmetry admission --
it still needs `sum_fQ > 0.8` (or `sum_bQ`), so a genuine Bragg-into-Michel
junction (hot side ~1.7 MIP, cold side ~0.1 MIP) can satisfy the `> 0.8`
half but is never *guaranteed* past the geometry gates that run first
(`refl_angles`/`ave_angles`/`angle3`), which is exactly why doc 54's own
cited example (`039349_18/36`) still sentinels today.

The offline probe (`d59_kink_asym_probe.py`) reproduces the CHARGE test only
-- not the geometry gates, and not the exact charge-weighted-mean arithmetic
(the prep payload carries only the already-computed per-point dQ/dx, so the
probe averages a 10-live-point window rather than summing dQ then dividing
by summed dx). This is a population **size** bound, the same caveat T1a's
own proxy carried:

```
population: missed 125, found 144, THRU 271, THRU_fp 9

=== operating point: entry >= 1.2 MIP, far <= 0.5 MIP, window 10, min_live 3 ===
missed     n=125   fires=25   (collapse 14, rise-to-end 10, flat 1)
found      n=144   fires=22   (rise-to-end 19, collapse 2, flat 1)
THRU       n=271   fires=55   (rise-to-end 14, flat 17, collapse 24)
THRU_fp    n=9     fires=2    (collapse 1, rise-to-end 1)
```

25 of the 125 missed stoppers show a candidate asymmetric row somewhere in
their profile, including `039349_18/36` itself -- confirming the probe finds
the known target. The coarse charge-only proxy over-fires heavily on THRU
(55 of 271), same pattern T1a's own proxy showed (7 -> 2 real); the real
gates (geometry + the downstream shape verdict) are expected to suppress
most of that exposure, and the real arm decides the actual count. This sizes
the population as worth building the knob for; it is not a prediction of the
recovered count.

---

## 2. The mechanism

Two new members on `TaggerCheckSTM`, read the same way every other guard in
this file is (`get<bool>`/`get<double>` against a member holding the C++
default, echoed in `default_configuration()`):

```cpp
bool   m_kink_asym_enable{false};
double m_kink_asym_entry_mip{1.2};
double m_kink_asym_far_mip{0.5};
```

A third, additive OR-clause in **both** charge gates, checked in either
direction (the "forward"/"backward" arm labels are a path-traversal
artifact, not muon-side vs Michel-side):

```cpp
|| (m_kink_asym_enable &&
    ((sum_fQ >= m_kink_asym_entry_mip && sum_bQ <= m_kink_asym_far_mip) ||
     (sum_bQ >= m_kink_asym_entry_mip && sum_fQ <= m_kink_asym_far_mip)))
```

Every existing geometry precondition -- `refl_angles > 20 && ave_angles >
10`, the `angle3` turn tests, `i <= 4`, the shorted-wire/dead-region guards
-- is untouched; only the charge acceptance changes. Both sweeps get the
identical clause and the identical two knobs, so a candidate sweep 1's
looser geometry admits is not lost to sweep 2's tighter one.

Jsonnet: three new named args on `cm.tagger_check_stm()`
(`cfg/pgrapher/common/clus.jsonnet`), key-suppression idiom (`if
kink_asym_enable then {...} else {}`), threaded through the three experiment
bags that bind `tagger_check_stm` (`protodunevd/pr.jsonnet`,
`pdhd/pr.jsonnet`, `sbnd/clus.jsonnet`) as a new variable
`stm_kink_asym_enable` (default `false` in all three). **SBND is the only
detector where `TaggerCheckSTM`'s OTHER guards are actually on in
production** (`stm_accept_guards`/`stm_vertex_kink_guard`/etc. are `true`
there, `false` on both ProtoDUNEs) -- but `find_first_kink` runs regardless
of those guard booleans, so this knob is a live lever on SBND too if ever
turned on. It ships default OFF everywhere including SBND, and SBND's own
`wct-pr-perevt.jsonnet` (in-tree) was left completely untouched -- it never
references `stm_kink_asym_enable` at all, so there is no TLA path to reach
it there; verified by compiling it and grepping for the key (0 occurrences).
This round makes no SBND production claim.

Both `pdvd/wct-pr-perevt.jsonnet` and `pdhd/wct-pr-perevt.jsonnet` were
edited to expose the three keys as top-level TLA-overridable parameters
(the same idiom `stm_vertex_kink_guard` already uses), each defaulting to
the legacy value. Compiled-config proofs, both directions:

* OFF path: compiling `pdvd/wct-pr-perevt.jsonnet` with no override is
  byte-identical to before this round's edit (`grep -c kink_asym` = 0).
* ON path: `-S stm_kink_asym_enable=true` reaches exactly the one
  `TaggerCheckSTM` node's `data` block and adds exactly the three expected
  keys, diffed against the OFF-path compile -- nothing else moves.
* Both proofs repeated on `pdhd/wct-pr-perevt.jsonnet`, same result.

---

## 3. Tests

`clus/test/doctest_tagger_check_stm_kink_asym_defaults.cxx` (new, 1 case):
factory-instantiate `TaggerCheckSTM`, pull `default_configuration()`, assert
`kink_asym_enable == false`, `kink_asym_entry_mip == 1.2`,
`kink_asym_far_mip == 0.5`. `find_first_kink` has no header and is not
independently unit-testable without exposing internals -- consistent with
every other guard in this file (`vertex_kink_guard`, `entry_rise_guard`, …),
none of which has a logic-level doctest either; correctness here is
established by the byte-identical OFF-path gate plus the real-arm census,
which is what actually decided this task (§5).

`./build/clus/wcdoctest-clus`: 357 cases (354 before this round -- +1 for
this knob, +2 for T4's `PR::Fit` struct tests, doc 60), 0 failed.

---

## 4. Byte-identical gates (knob off)

`d59vleg` (PDVD, `d58v`'s exact config, new binary) vs `d58v`:

```
d58v -> d59vleg
  matched candidates      : 579  (before 579, after 579)
  branches shared / new / dropped : 116 / 0 / 0
  candidates BIT-IDENTICAL on all 116 shared branches : 579 / 579
  NO shared branch moved on any candidate.
  is_stm FLIPS : 0

d58v -> d59vleg  (T_stm_michel_pts)
  candidates with IDENTICAL point geometry (seg_id,x,y,z,q) : 579 / 579
  of those, role labels moved on : 0
```

`d59hleg` (PDHD, `d53h`'s legacy `SURVEY`-only config, new binary) vs `d53h`:

```
d53h -> d59hleg
  matched candidates      : 325  (before 325, after 325)
  branches shared / new / dropped : 111 / 5 / 0
  NEW branches   : n_retreat, n_split, retreat_len, split_kink_deg, split_len
  candidates BIT-IDENTICAL on all 111 shared branches : 325 / 325
  is_stm FLIPS : 0

d53h -> d59hleg  (T_stm_michel_pts)
  candidates with IDENTICAL point geometry (seg_id,x,y,z,q) : 325 / 325
  of those, role labels moved on : 0
```

(The 5 "new" branches on the PDHD side are T1a/T1c's own fields, expected
since `d53h` predates both -- not this round's change; T4's `reg_flag_u/v/w`
are new on `stm_fit`/`T_rec_charge`, not on `T_stm_michel`, so they do not
appear in this branch list.) Both gates confirm the T1b code addition and
T4's writer-only persistence perturb nothing when `kink_asym_enable` is off,
on both detectors.

---

## 5. The feature arm: what `stm_kink_asym_enable = true` actually recovers

`d59v` (PDVD, `d58v`'s config + `stm_kink_asym_enable=true`) scored against
the frozen record, beside `d58v`'s own re-scored baseline:

| | scored | TP | FP | FN | TN | purity | efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `d58v` (before) | 549 | 147 | 9 | 122 | 271 | 0.942 | 0.546 |
| `d59v` (after)  | 547 | 149 | 9 | 119 | 271 | 0.943 | 0.556 |

**2 of the missed stoppers recovered, 0 new `is_stm` false positives** (the
9-item FP set is identical, item for item, before and after -- verified by
name, not just count). Pin residual over the 36 scan pins: 3.16 -> **2.78
cm**, within 2 cm 10 -> 12. Role 3 (Michel object) attachment: 186 -> 192.

**The two recoveries, named:**

| item | scan verdict | kink_num before -> after | reject bits cleared |
|---|---|---:|---|
| `039349_52/36` | STM_MICHEL | 319 -> 303 | `no_bragg`, `shape_flat` |
| `039349_67/78` | STM_MICHEL | 121 -> 110 | `shape_flat` |

Both are genuine, item-by-item confirmed via the persisted `T_stm_pass`
`kink_num` moving to an earlier row and the corresponding `CheckSTM_Michel`
reject bits clearing -- the mechanism doing exactly what it was built to do.
Neither item had `n_retreat` or `n_split` fire in either arm, so these are
T1b's own recoveries, not a relabeling of T1a/T1c's.

**Cost: 3 `michel_found` flips**, one of them a genuine gain on a real
stopper and one a new spurious attachment:

| item | scan verdict | michel_found before -> after | note |
|---|---|---:|---|
| `039349_52/36` | STM_MICHEL | 0 -> 1 | same item as the `is_stm` recovery above |
| `039253_17/77` | STM_MICHEL | 0 -> 1 | `is_stm` stays 0 (still `no_bragg`+`shape_flat`) -- named in doc 56 T2's target list already; Michel attaches correctly even though the stop verdict doesn't clear |
| `039349_81/54` | MESSY (not judged) | 0 -> 1 | new spurious attachment on an ambiguous item -- feeds T2, on top of T1a/T1c's own 5 |

**Subsumption: T1b preempts T1a/T1c on 3 items** (advisor-flagged risk,
checked directly against the real arm, not assumed):

| item | `n_retreat` before->after | `n_split` before->after | `is_stm` before->after | verdict |
|---|---:|---:|---:|---|
| `039349_18/36` | 1 -> 0 | 0 -> 0 | 1 -> 1 | unchanged -- T1b now finds the real kink directly (kink_num 228->213) where T1a's retreat used to walk back to it; credit reassigned, no regression |
| `039349_7/4` | 1 -> 0 | 0 -> 0 | 0 -> 0 | unchanged -- T1a's retreat used to fire here without ever flipping `is_stm`; still doesn't |
| `039253_17/77` | 0 -> 0 | 1 -> 0 | 0 -> 0 | unchanged -- T1c's split used to fire without flipping `is_stm`; T1b's kink now finds the row directly instead, `michel_found` still flips (see above) |

Aggregate: `n_retreat` fires 11 -> 9, `n_split` fires 10 -> 9 across the 566
common candidates. No item's `is_stm` verdict moved as a result of this
preemption -- every case above is either a still-correct recovery
(`039349_18/36`) or a still-correct non-recovery, reached by a different
upstream mechanism.

**3 items drop out of `CheckSTM_Michel`'s candidate population entirely**
(a real behavior this knob introduces that neither T1a nor T1c has: changing
`kink_num` can change whether `check_stm_conditions` tags the cluster
`Flags::STM` at all, upstream of `CheckSTM_Michel`, so the item never
produces a `T_stm_michel` row and `census_score.py` reports it UNMATCHED
rather than scoring it):

| item | scan verdict | `d58v` state | effect |
|---|---|---|---|
| `039252_16/91` | MESSY | `is_stm=0` | not judged anyway, no scoring effect |
| `039252_9/49` | STM_ONLY | `is_stm=0` (an existing miss) | drops out of the FN denominator rather than being recovered -- the 549 -> 547 scored-count drop is this item plus the next |
| `039349_81/21` | THRU | `is_stm=0` (a correct TN) | drops out of the TN denominator |

**Methodological note, stated rather than glossed over:** because these two
judged items leave the denominator instead of being reclassified, the
549 -> 547 scored-count drop mechanically nudges purity and efficiency by
less than 0.002 in the reported direction (removing one known FN and one
known TN from otherwise-unchanged totals) -- negligible here, but the effect
exists and a future round with a larger drop should check it explicitly
rather than read purity/efficiency across an arm boundary where the
denominator moved.

`census_score.py --check` on the committed baseline: still 0 of 14 differ.

---

## 6. Gates

| gate | result |
|---|---|
| `./build/clus/wcdoctest-clus` | 357/357 (354 -> 357), 0 failed |
| `d59vleg` vs `d58v` (PDVD) | 579/579 bit-identical, 0 `is_stm` flips |
| `d59hleg` vs `d53h` (PDHD) | 325/325 bit-identical, 0 `is_stm` flips |
| SBND compiled-config grep | `kink_asym` absent (0 occurrences) -- SBND's driver never references the key |
| flip-equivalence / OFF-ON compiled-JSON diff | both PDVD and PDHD: exactly the 3 expected keys appear on override, nothing else |
| `census_score.py --check` | 0 of 14 differ |

---

## 7. Found on the way, not fixed

1. `vertex_kink_reject` (`TaggerCheckSTM.cxx:2474`) still evaluates at `n-1`
   under the no-kink sentinel -- a real kink from this round's clause
   corrects that automatically wherever it fires, but the guard itself is
   untouched, and `m_vertex_kink_guard` is off on PDVD anyway (only SBND
   runs it), so this round has no effect on it there.
2. The `find_first_kink` early-return guard `if (i + 2 < dq_size)` (both
   sweeps) has no `else`: a candidate passing every other clause but sitting
   within 2 rows of the fit's end is silently skipped, not counted. Not
   changed this round; noted for whoever tunes the sentinel rate next (T7).
3. `039253_17/77`'s `michel_found` recovery without an `is_stm` recovery is
   exactly the case doc 56 T2 was scoped to decide: whether a Michel arm at
   a *kink-relocated* stop needs a stronger admission gate than one at the
   tagger's original stop. This round adds one more concrete instance to
   that list, alongside the 5 from T1a/T1c.

---

## 8. Update to doc 56

Doc 56's T1b row is marked done: knob `stm_kink_asym_enable` is PDVD
production. The "Order." paragraph is updated to reflect that T1a, T1b and
T1c are all now done.
