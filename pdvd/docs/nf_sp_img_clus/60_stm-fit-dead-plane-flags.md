# 60 — T4: persist the fit's per-plane dead-channel flags

**Status (2026-09-09). Writer-only, no verdict path, no knob to flip.**
`reg_flag_u/v/w` (per fit point, "this plane had no live cell here so the
regulariser filled it") now flow from `TrackFitting::dQ_dx_fit`'s own
already-computed booleans out to `PR::Fit`, `TaggerCheckSTM`'s `stm_fit`
point cloud, and `T_rec_charge` (both PDVD and SBND Magnify visitors). Every
existing branch is bit-identical (verified as part of doc 59's byte-identical
gates, which ran on the same binary); three new branches are added. The
dead-plane/Bragg-contrast correlation this was built to measure turns out
weak/inconclusive on the sample checked -- reported as measured, not tuned
to look better.

---

## 0. Repro

```bash
cd /nfs/data/1/xqian/toolkit-dev/toolkit
wcbuild && ./build/clus/wcdoctest-clus -tc="*T4*,*reg_flag*"

cd /nfs/data/1/xqian/toolkit-dev/wcp-porting-img
python3 -c "
import uproot
f = uproot.open('pdvd/work/039253_3_d59v/tracking-stm.root')
rc = f['T_rec_charge'].arrays(library='np')
print(list(rc.keys())[-6:])
print(rc['reg_flag_u'].sum(), rc['reg_flag_v'].sum(), rc['reg_flag_w'].sum())
"
```

---

## 1. Correction to doc 56's own premise: the STM fit path is `dQ_dx_fit`

Doc 56 §5 named `reg_flag_u/v/w` as computed but never persisted. There are
**two** declaration sites in `TrackFitting.cxx`, not one: `dQ_dx_multi_fit`
(`:7361`, reused across two different index spaces -- per-3D-point, then
per-vertex, in the same three vectors) and `dQ_dx_fit` (`:8509`, the
single-segment path). Confirmed via the call chain that STM uses only the
second: `check_stm_conditions` (`TaggerCheckSTM.cxx:3699`, `:3718`) calls
`do_single_tracking`, whose `flag_dQ_dx_fit` parameter defaults `true`
(`TrackFitting.h:859`) and branches to `dQ_dx_fit` (`TrackFitting.cxx:10344`).
The existing debug dump (`WCT_DQDX_DUMP`, env-gated) sits inside
`dQ_dx_multi_fit`, which STM never calls -- so there was no free measurement
shortcut here; the flags had to be wired through the real path to be seen at
all. `dQ_dx_multi_fit`'s own locals are left untouched: STM doesn't call it,
and resolving its dual-index reuse would serve no STM purpose.

---

## 2. The persistence chain

`PR::Fit` (`clus/inc/WireCellClus/PRCommon.h`) gains three fields, appended
at the end of the struct (no positional/aggregate-brace construction of
`Fit` exists anywhere in the tree, so this is a safe append):

```cpp
bool reg_flag_u{false}, reg_flag_v{false}, reg_flag_w{false};
```

`TrackFitting` gains three carrier member vectors beside `dQ`/`dx`/`pu`/
`pv`/`pw`/`pt`/`paf`/`reduced_chi2` (`TrackFitting.h:1299-1308`). `dQ_dx_fit`'s
local declaration of `reg_flag_u/v/w` (`:8514` originally) becomes a
`.assign()` onto these members instead of a fresh local -- every existing
fill site in the function is otherwise untouched. `dQ_dx_fill` (the
placeholder path when no real fit ran) resizes them to all-zero, matching
its existing treatment of `dQ`/`dx`/`reduced_chi2`. `do_single_tracking`'s
`PR::Fit`-construction loop reads them back with a bounds guard (`if (i <
reg_flag_u.size())`), not `.at(i)`, so a caller that populates neither
`dQ_dx_fit` nor `dQ_dx_fill` correctly leaves the flags at `Fit`'s own
`false` default ("no information") rather than reading out of range.

`TaggerCheckSTM::persist_stm_fit` (`:1020` originally) gains three arrays
(`reg_flag_u/v/w`, cast `int` from the `Fit` booleans) on the `stm_fit`
point cloud, populated the same way every other array there already is
(`f.dQ`, `f.pu`, …). Every `stm_fit` consumer (`MultiAlgBlobClustering.cxx`,
`CheckSTM_Michel.cxx`, both Magnify visitors) fetches columns **by name**, so
adding columns breaks no reader.

`root/src/SbndMagnifyTrackingVisitor.cxx` and
`root/src/PdvdMagnifyTrackingVisitor.cxx` (`write_t_rec_data`): three new
`/I` branches on `T_rec_charge`, read from the three new `stm_fit` columns
the same way `pu`/`pv`/`pw` already are.

**No knob.** This is purely additive: no comparison, threshold, or
accept/reject decision anywhere reads these fields. There is no alternate
behavior to gate default-OFF because there is no alternate behavior -- the
bar is "every existing branch unchanged," which doc 59's byte-identical
gates (same binary, same commit) already prove directly (116 shared
`T_stm_michel` branches PDVD, 111 PDHD, all bit-identical; `T_rec_charge`
carries only additive new columns, never checked against the shared set
since `d51g_branch_census.py` reads `T_stm_michel`, not `T_rec_charge` --
verified separately below).

---

## 3. Tests

`clus/test/doctest_pr_fit_reg_flags.cxx` (new, 2 cases): `PR::Fit` defaults
`reg_flag_u/v/w` to `false` (and every existing field is unchanged by the
addition); the three fields are independently settable. `TrackFitting`'s own
carrier vectors are `private`, so no direct member-level test is possible
without exposing internals no other test exposes either; there is no
existing unit harness that exercises `dQ_dx_fit` itself (it needs a real
fitted segment, the same limitation T1b's `find_first_kink` has) -- the
real-arm measurement in §4 is the functional check, as it is for T1b.

`./build/clus/wcdoctest-clus`: 357/357 (see doc 59).

---

## 4. Verification: existing branches unchanged, new ones present

Confirmed directly on a real file rather than assumed: `T_rec_charge` of
`d59v`'s `039253_3` carries `reg_flag_u/v/w` with real, non-trivial data
(299/233/144 flagged points of 3130 in this one file -- not an
always-zero placeholder). Doc 59's byte-identical gates (`d59vleg` vs
`d58v`, `d59hleg` vs `d53h`) ran on the exact same binary as this addition
and found 0 shared-branch movement on `T_stm_michel`/`T_stm_michel_pts` --
the tree this task did NOT touch. `T_rec_charge` itself is not part of that
gate's tree list (it compares `T_stm_michel`), so as a direct check: the six
pre-existing `T_rec_charge` branches (`x,y,z,q,nq,...`) were spot-checked
identical in value between `d58v` (predates this change) and `d59v` (has
it) for `039253_3`'s rows, confirming the addition is purely additive there
too.

---

## 5. The dead-plane / Bragg-contrast correlation (doc 56 §5's own question)

Doc 56 §5 measured that dead channels near the stop do **not** separate
missed from found stoppers in aggregate (11% vs 10% of items with >= 20% of
their last-15cm points on a dead band), and asked whether the mechanism that
WOULD explain a correlation -- the fitter's regulariser flattening the Bragg
peak where a plane is dead -- is visible point-by-point now that the flags
are persisted. Re-deriving the same population against the current (T1a+
T1b+T1c) arm gives 13 candidates (doc 56 named 14 against the pre-T1a
population; the shift is expected -- some items this population depended on
have since been recovered by T1a/T1b/T1c and are no longer "missed"):

| item | dead frac (max plane, last 15cm) | dead frac (rr<=5cm) | q(rr 0-3) | q(rr 20-40, plateau) |
|---|---:|---:|---:|---:|
| `039349_82/54` | 1.00 | 66.7% | 3179 | 3121 |
| `039253_0/44` | 0.72 | 44.4% | -202 | 4124 |
| `039349_5/54` | 0.69 | 0.0% | 6273 | 2633 |
| `039349_5/65` | 0.69 | 80.0% | -383 | 3766 |
| `039349_55/24` | 0.52 | 62.5% | 8139 | 3294 |
| `039349_11/19` | 0.50 | 100.0% | 2887 | 2753 |
| `039253_17/77` | 0.44 | 0.0% | 53 | 2617 |
| `039253_3/29` | 0.38 | 100.0% | 2495 | 2383 |
| `039349_15/23` | 0.36 | 33.3% | 5155 | 3102 |
| `039253_8/27` | 0.31 | 0.0% | 2265 | 1766 |
| `039349_61/21` | 0.31 | 0.0% | 6971 | 2541 |
| `039349_27/41` | 0.27 | 77.8% | 4059 | 2496 |
| `039349_22/41` | 0.24 | 33.3% | 5784 | 2972 |

**The correlation is weak/mixed, not confirmed.** Some high-dead-density
items show clear flattening (`039349_5/65`: 80% of the last 5cm dead, q(0-3)
negative i.e. essentially zero against a 3766 plateau) or a merely-flat
ratio near 1.0 (`039349_11/19`, `039253_3/29`, both 100% dead in the last
5cm). But `039349_5/54` is 0% dead in the last 5cm and shows the strongest
Bragg RISE in the whole table (q(0-3)/plateau = 2.4), and `039253_17/77` is
also 0% dead there yet is the FLATTEST item in the sample (q(0-3) = 53,
essentially collapsed) -- the same item T1b's arm (doc 59) could not clear
`no_bragg`/`shape_flat` for. A dead plane is present on some flattened items
and absent on both the most-Bragg-like and the most-flattened items in this
small sample. This reinforces, rather than overturns, doc 56 §5's own
finding: dead channels are not a reliable predictor of the collapse shape.
Reported as measured; no threshold was tuned to make this look more
conclusive than it is.

---

## 6. Gates

| gate | result |
|---|---|
| `./build/clus/wcdoctest-clus` | 357/357 (part of doc 59's build) |
| Existing `T_stm_michel`/`T_stm_michel_pts` branches, same binary | bit-identical (doc 59 §4's gates, same commit) |
| `T_rec_charge` pre-existing columns, `d58v` vs `d59v`, spot-checked | unchanged |
| New `reg_flag_u/v/w` present with real (non-placeholder) data | confirmed on `039253_3_d59v` |

---

## 7. Found on the way, not fixed

1. `dQ_dx_multi_fit`'s own `reg_flag_u/v/w` locals remain function-local and
   unpersisted -- out of scope, since STM's fit path never calls that
   function. A future task that DOES need multi-fit's dead-plane flags
   (e.g. a full-pattern-recognition consumer) would need to resolve the
   dual-index reuse (per-point then per-vertex, same three vectors) this
   doc's scoping deliberately avoided.
2. The correlation this task was built to enable is measured, not
   established -- §5's 13-item sample is too small and too mixed to decide
   whether the smoother's dead-plane handling is a real contributor to any
   individual item's collapse shape. A larger, systematic sweep (all ~125
   missed stoppers, not just the >= 20% dead-band subset) is the natural
   next step if this question is revisited.

---

## 8. Update to doc 56

Doc 56's T4 row is marked done: the flags are persisted (`stm_fit` PC and
`T_rec_charge`), writer-only, no knob. The dead-plane/Bragg-contrast
correlation is measured and found weak on the checked sample -- doc 56 §5's
own conclusion (dead channels don't separate missed from found) stands,
now with a point-by-point look rather than only the aggregate table.
