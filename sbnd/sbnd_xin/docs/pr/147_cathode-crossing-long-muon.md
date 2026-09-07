# 147 — The cathode-crossing long muon, broken in two: the bridge's PID guards

**Status.** Round 1 CLOSED. One new knob family shipped **default OFF**
(`long_muon_cathode_bridge_track_types` + three value knobs), OFF gate
**PASS 44/44 byte-identical**, ON over-reach measured at **exactly 2 archives
in 22 events** — the two target events and nothing else. **Nothing is flipped
for SBND production**; the flip needs the owner's scan.

Owner report, 2026-09-06, on the doc-145 §7 master-vs-branch Bee pairs: on
SBND **18259-177536** and **18255-347890** a long muon crossing the cathode is
no longer one particle. Owner's proposed shape, quoted because it is what got
built: *"1. go through cathode, 2. the track from each side are highly aligned,
3. … some code in the Q/L matching side … 4. … form them as long muon
independent from the original PID"*.

## 0 Repro

```
# binary: toolkit 03a23405, libWireCellClus.so md5 d5558074d5b72d3e36557c0d1f5f99e1
#         (freshness: local/lib 19:22:13 > last source edit 19:21:27)
# WORKDIR = wcp-porting-img/sbnd/sbnd_xin ; Q/L roots work-{mcp1k,mcp2k}-d97fv

# A. census (read-only, no arm spent).  Production arms as AFTER, the
#    knob-off d144 arms as the free BEFORE.
python3 scripts/pr147_cathode_census.py \
  --arms work-mcp1k-d144fixprod:mcp1k work-mcp2k-d144fixprod:mcp2k \
         work-ncpi0-d144fixprod:ncpi0 work-nuecc48-d144fixprod:nuecc48 \
  --out docs/pr/147_cathode/after
python3 scripts/pr147_cathode_census.py --xcut 12 --min-len 2 --gap 30 \
  --arms ... --out docs/pr/147_cathode/after_wide
python3 scripts/pr147_adjudicate.py docs/pr/147_cathode/after --min-long 0 --min-short 0
python3 scripts/pr147_adjudicate.py docs/pr/147_cathode/after_wide

# B. config proofs (no runs).  PT = the 16-name pipeline_names list of doc 144 sec 0.
git show HEAD:$D/wct-pr-perevt.jsonnet > $D/.d147proof_before.jsonnet
wcsonnet --tla-code "$PT" -o t0_before.json $D/.d147proof_before.jsonnet
wcsonnet --tla-code "$PT" -o t0_after.json  $D/wct-pr-perevt.jsonnet
cmp t0_before.json t0_after.json      # rc 0; md5 881862ad794f1d66188616b340686642
wcsonnet --tla-code "$PT" --tla-code long_muon_cathode_bridge_track_types=true -o t1_on.json ...
#   NB --tla-code, not -A: -A passes a STRING and the key-suppression `if`
#   then aborts the compile with "Unexpected type string, expected boolean".

# C. the arms (22 events; PR_JOBS=8)
./run_pr_chain_batch.sh work-mcp2k-d97fv work-d147-off2-mcp2k data $M2K   # 13 evts
./run_pr_chain_batch.sh work-mcp1k-d97fv work-d147-off2-mcp1k data $M1K   #  9 evts
SBND_LONG_MUON_CATHODE_BRIDGE_TRACK_TYPES=1 ./run_pr_chain_batch.sh ... work-d147-on1-{mcp2k,mcp1k}
python3 scripts/pr85_hash_gate.py work-mcp2k-d144fixprod work-d147-off2-mcp2k   # OFF gate
python3 scripts/pr85_hash_gate.py work-d147-off2-mcp2k   work-d147-on1-mcp2k    # over-reach

# D. the continuation trace behind sec 4 (kine_continuation_debug, already
#    committed default-OFF at 8c14185a; log-only)
printf 'kine_continuation_debug=true\n' > /tmp-scratch/d147cont.tla
PR_EXTRA_TLA=... PR_EXTRA_STAGES=pr_display ./run_pr_chain_batch.sh \
  work-mcp2k-d97fv work-d147-cont1-mcp2k data 177536 168448 347890
```

## 1 The two events are two different defects

Both are already registered `OPEN` in the doc-144 sentinel suite (§16.3). What
this round adds is that they are **not the same failure**, and only one of them
is a bridge problem. Re-verified on `work-mcp2k-d144fixprod`:

| | 177536 | 347890 |
|---|---|---|
| bridge log | **fires** (`absorb bare chain … len=98.7cm gap=9.4cm`) | **silent** — no accept line, no reject line |
| `kine_particle_type` | `[2212, 13, 11, 11, 13]` — two muon nodes, 276.0 + 644.3 | `[2212, 11, 11, 13]` — muon 429.4 + the far half as two EM showers |
| `Enu` / `add_energy` | 1339.8 / 219.9 | 658.9 / 8.6 |
| defect | the far half is **not joined**, so it is counted as a second particle and charged a second muon rest mass (§4) | the far half's **PID flipped 211 → 11** and the partner-type guard refuses EM by design (§2) |

**Cause of the regression**: `excl_t0_frame` ON for SBND (`4c84855c`), with
`70c23cc7` making a segment break visible in PF. No cluster-level cathode
machinery moved on this branch; the joining algorithm is intact, its *input*
changed.

**The algorithm the owner asked about** is `long_muon_cathode_bridge_pass`
(`clus/src/TaggerCheckNeutrino.cxx:1350`, docstring `:1298`), doc 84 rounds 2
and 4, SBND production ON since 2026-08-28/29. It is a PR-stage pass, not a
clustering merge.

## 2 A third event, and the two guards

Scanning both arms for "bridge fired BEFORE, silent AFTER" over the 3000 numu
events (1435 with a calib dump) returns **two** events, and one was not in the
owner's scan:

| sample | event | bridge | muon E | `Enu` |
|---|---|---|---|---|
| mcp2k | **168448** | 1 → 0 | 236.1 → **34.9** MeV | 652.2 → **444.9** |
| mcp2k | 347890 | 1 → 0 | 488.7 → 429.4 MeV | 632.3 → 658.9 |

168448 is the worse of the two — 201 MeV of muon energy, 207 MeV of `Enu`,
against 347890's 59 MeV — and it is a **doc 84 R4.6a fire-set sentinel**, so a
gate that was PASS 20/20 on 2026-08-29 had gone red unnoticed. No event gained
a bridge.

**This closes doc 84 R4.10 deferred item 2, and it reconciles exactly.** R4.10
predicted "10 → 13 whenever a full census next runs; a different number means
something is off." The OFF arm fires in **13**; production fires in **11** =
13 − these 2. The prediction was right and the whole deficit is attributed.

The two events die at **different guards**, which is what the fix has to cover:

- **347890 — the partner guard** (`:1431`). Its far half is a 17.5 cm shower
  typed 11; `optype == 13 || (track_partner && optype == 211)` refuses it.
- **168448 — the receiver guard** (`:1404`). Its *near* half lost its own type:
  pdg 13 / 94.2 cm / x −15.0→+61.2 (itself a cathode crosser) became pdg 11 /
  20.2 cm / x −15.3→−4.2. The pass never reaches a partner at all.

A fix that only widens the partner guard — the obvious reading of the owner's
item 3a, and doc 144 §14.1's own recommendation — recovers 347890 and leaves
168448 broken.

## 3 What shipped, and why it is a veto and not an identification

`long_muon_cathode_bridge_track_types` (C++ default **false**) admits either
side on **track-likeness** instead of PID, leaving every geometry gate in
force. A receiver admitted this way is retyped to 13 *before* the keeper
contest, whose second rank key is `muon_member_length` and would otherwise read
the shower as carrying zero muon.

| config key | C++ default | what it does |
|---|---|---|
| `long_muon_cathode_bridge_track_types` | `false` | master switch; false == doc 84 rounds 2-4 exactly |
| `long_muon_cathode_bridge_trk_dqdx_lo` | `0.8` | × `mip_dqdx_median`; below = dead / mis-attributed charge |
| `long_muon_cathode_bridge_trk_dqdx_hi` | `2.0` | × `mip_dqdx_median`; **the load-bearing veto** |
| `long_muon_cathode_bridge_trk_straight` | `0.90` | chord / track length |

**The charge does not identify a muon, and the doc must not pretend it does.**
Over the 225 segments within 12 cm of the cathode carrying a usable dQ/dx:

| segment pdg | n | median dQ/dx ×MIP | median chord/len |
|---|---|---|---|
| 13 | 70 | 1.227 | 0.964 (p10 0.933) |
| 211 | 13 | 1.348 | 0.943 |
| **11** | 120 | **1.242** | 0.895 (p10 0.693) |
| 2212 | 22 | **3.386** (p10 2.279) | 0.978 |

|13| and |11| sit on top of each other in charge. So this is a **veto**, the
same discipline the `do_track_comp` electron template needs, and what it vetoes
is measurable: protons (`trk_dqdx_hi`) and low-charge/kinked objects
(`trk_dqdx_lo`, `trk_straight`). The selection is done by the geometry that was
already there.

Also shipped: a **`reject partner_type` log line**. Doc 84 R4 added a reject
line for candidates reaching the angle tests, but the type guards sit above
them — over 1435 production events exactly **one** emitted a reject line, which
is why this class was invisible. It is now audible on both arms.

## 4 The candidate population, and the one negative control

The census re-implements the pass offline from `segments[].points[]` — it
cannot be read from the logs, per the silence above — with the type guards
relaxed so the killed class is visible, then names the first guard that
rejects each pair. In the **shipped admission window**, over 1435 events:

| sample | event | binding cut | recv | partner | gap | a_gap | a_tan |
|---|---|---|---|---|---|---|---|
| mcp2k | **347890** | `partner_type` | 182.9 cm, 1.276 MIP | shower pdg 11, 17.5 cm, 1.255 MIP | 14.3 | 14.7 | 7.1 |
| mcp2k | **168448** | `receiver_type` | pdg 11, 15.5 cm, 1.238 MIP | bare pdg 13, 75.1 cm, 1.370 MIP | 11.2 | 10.5 | 8.4 |
| mcp1k | 289559 | `receiver_type` | **3.480 MIP** (proton), 19.3 cm | bare, 12.6 cm | 9.5 | 21.5 | 11.4 |

**Three pairs in three events, and the third is the negative control.** 289559
is owner-confirmed a correct reject (doc 84 R4.2) and its geometry would admit
it — `trk_dqdx_hi` is the only thing that refuses it. It stays refused, and
the new reject line says why.

> **The control this round expected to use is gone.** Doc 84's named EM
> exclusion, **392901**, no longer forms a candidate pair on this epoch at all:
> its 44.1 cm bare pdg-13 partner is absent and only a 6.1 cm EM segment
> remains near the seam, both ends at x ≈ +2. It cannot be used as a live
> control and is not claimed as one. 289559 replaces it, on measurement.

Two census bugs worth recording because both were caught by the C++ refusing to
agree, not by inspection:

1. **De-duplication must mirror the production minimiser.** Among the four
   end-orientations of one segment pair, keeping the longest-receiver row
   dropped 347890 entirely — its good orientation (gap 14.3, a_tan 7.1) loses
   to its bad one (gap 30.6, a_tan 171.5). `pr147_adjudicate.py` ranks
   angle-passing first, then smallest gap, which is what `:1456` does.
2. **First-failing-guard order means later gates were never applied.** A row
   whose verdict is `receiver_type` never had its gap, xcut *or far-side* test
   run. An earlier draft of the table above therefore listed **394796** as a
   candidate; the C++ refused to bridge it, and the reason is that it is not a
   cathode crosser at all — both halves span x = +1.7…+36.8, on one side. The
   adjudicator now re-applies the far-side test explicitly.

### 4a The split-muon population, re-derivable from the committed tables

`docs/pr/147_cathode/{before,after}/pr147-muon-nodes.tsv` carry one row per
event with a calib dump (1435 after, 1368 before). Joining them on
`(sample, evt)` and selecting "more `pdg == 13` nodes on AFTER with total muon
energy preserved to 5 %" returns **21 events, 6 of them paying a spurious rest
term** — `98844 (+139.5)`, `407280`, `55595`, `177536`, `78743`, `97260`
(`+105.7` each). That reproduces doc 144 §14.2.1's 21 / 1434 exactly, which is
what licenses the census script's arithmetic. pr/145 §4.4 further establishes
that only **5 of the 6** are real double counts (78743 is a genuinely extra
muon chain), and that doc 144's aggregate "270.0 MeV" does not reproduce and
should not be quoted.

## 5 Gates

| gate | arms / method | result |
|---|---|---|
| compiled config, knobs absent | `cmp` vs `HEAD` copy, full `pipeline_names` | **byte-identical**, md5 `881862ad794f1d66188616b340686642` |
| — sibling-key guard | `long_muon_cathode_bridge`, `_track_partner`, `mip_dqdx_median` all present in the compiled block | not a vacuous diff (doc 145 §4.2's trap) |
| compiled config, master switch on | diff vs above | exactly **one** new key |
| compiled config, all four on | diff vs above | exactly **four** new keys, nothing else moves |
| `build/clus/wcdoctest-clus` | — | **328 cases / 23106 assertions, 0 failed** (4 new default pins) |
| **OFF gate** | `work-{mcp2k,mcp1k}-d144fixprod` vs `work-d147-off2-*` | **PASS 26/26 + 18/18 = 44/44 byte-identical** |
| **over-reach** | `work-d147-off2-*` vs `work-d147-on1-*`, 22 events | **exactly 2 archives differ**: 168448 and 347890 `mabc-pr.zip`. Every `pctree` identical; all 9 mcp1k events identical |
| **determinism** | `work-d147-det1/det2-mcp2k`, knob ON, `setarch x86_64 -R` | **PASS 4/4 byte-identical** |

The over-reach arm deliberately carries the whole **doc 84 R4.6a fire set**
(53793, 77978, 177536, 281214, 287555, 321767, 391766, 398181, 478880, plus
172794 and 67026) because R4.6a warns that enlarging the pool feeds a best-gap
**minimiser** and an already-firing event could silently switch partner or
stop. None of them moves.

## 6 ON smoke — each event recovers at its own guard

```
347890  relaxed receiver sid=0 pdg=11 seg=17 len=17.5cm retyped to 13
        merge shower sid=0 (mu_len=18.9cm) <- sid=6 (mu_len=182.9cm) gap=14.3cm ends x=(-4.2,4.9)cm
168448  relaxed receiver sid=0 pdg=11 seg=10 len=15.5cm retyped to 13
        absorb bare chain into sid=0 nseg=1 len=75.1cm gap=11.2cm ends x=(-4.2,3.4)cm reseat=0
289559  reject partner_type seg=12 shower_pdg=2212 len=19.3cm ends x=(4.1,4.1)cm      <- control holds
```

| evt | | OFF | ON |
|---|---|---|---|
| 347890 | types / E | `[2212, 11, 11, 13]` / muon **429.4** | `[2212, 13, 11]` / muon **470.8** |
| | `add` / `Enu` | 8.6 / 658.9 | 114.3 / **746.9** |
| 168448 | types / E | `[2212, 13, 11]` / muon 34.9, EM 102.0 | `[2212, 13, 13]` / muon 34.9 + **241.2** |
| | `add` / `Enu` | 114.3 / 444.9 | 219.9 / **689.7** |

**Stated against itself:** both land *above* their pre-regression `Enu`
(347890 632.3, 168448 652.2), by close to one muon rest mass in each case,
because the rescued object is now charged a rest term it was not charged
before. That is the §4 defect showing up on the rescued events, and it is a
reason for the owner to scan these two pictures rather than read the `Enu`
alone.

## 7 177536 — what it actually needs, and it is not a rest-mass refund

pr/145 §4.5 named the fix shape for this class as "a cross-admission-path
continuation test". The instrumentation says something more specific and more
useful. `work-d147-cont1-mcp2k`, verbatim:

```
kine_cont: CHARGE seg=17 pdg=2212 rest_mev=8.60 ke_mev=191.17
kine_cont: CHARGE_SHOWER start_seg=18 pdg=13 rest_mev=105.66 ke_mev=276.00
kine_cont: SKIP_VISITED vtx=17 prev_seg=17 prev_pdg=2212
kine_cont: CHARGE seg=8 pdg=13 rest_mev=105.66 ke_mev=644.34
kine_count_guard_freed: COUNT seg idx=8 cluster=17 pdg=13 ke_mev=644.34 len_cm=279.6
```
`8.60 + 105.66 + 105.66 = 219.92 = kine_reco_add_energy`, reproducing pr/145
§4.3 exactly. **The protection is not missing** — `flag_reduce`
(`NeutrinoKinematics.cxx:366-382`, refund at `:425-444`) is a real
per-particle rule that fires on 9 of the 21 split candidates. It is *bypassed*:
the two halves enter through two different non-BFS pools, so it is never
evaluated (no `TEST` line on the event).

But the census locates the second node: **`seg 8`, 279.6 cm, is the unbridged
far half** — the same object, sitting in the census as a candidate pair at
gap 20.8 cm with `a_gap 11.4 / a_tan 8.0`, held out by **both** the 20 cm gap
cap and the 6 cm `xcut` (its end is at x = −9.41). So 177536's "double-counted
rest mass" is a *symptom of the same unjoined far half*, not an independent
accounting bug: join it and there is one muon node and one rest term.

**No knob is proposed for it here**, because joining it needs *two* geometry
cuts loosened at once on the strength of one event, which is tuning to fit.
Measured instead:

- raising only the gap cap to 30 does **not** move 177536 (its `xcut` still
  binds), and
- it **does** make **497311** — the worst broken chain in doc 84's table,
  332.8 cm with chain 0 — bridge at gap 27.0 … **and its kine scalars do not
  move at all** (nmu 1, Emu 476.0, `Enu` 581.7 both sides).

That last line is the reason no gap change is recommended: the one event it
demonstrably joins gains nothing measurable, and its over-reach across the
population is unmeasured.

## 8 What is NOT claimed

- **No production flip.** All four keys are default-OFF and SBND sets none of
  them. The ON numbers above come from an env-seeded arm.
- **No truth.** Every "should have been joined" rests on geometry, the owner's
  doc-84 adjudications, and the before/after arms — not MC truth.
- **The over-reach is measured on 22 events, not 3067.** The census says the
  shipped window holds exactly three candidate pairs in 1435 events and the
  arm covers all three, but a full-population ON arm has not been run.
- **No PDVD / PDHD / uBooNE gate.** `TaggerCheckNeutrino` binds on other
  detectors; the C++ default is `false` so they cannot reach the new code, but
  the standing bar wants each detector's own manifest and that is **owed**.
- **392901 is not a live control on this epoch** (§4).

## 9 Recommended next step

Scan the two rescued pictures (347890, 168448) before any flip — both change
`Enu` upward past their pre-regression value for the §7 reason, so the
pictures, not the scalars, are the thing to judge. If they hold, the flip is
`long_muon_cathode_bridge_track_types = true` alone; the three value knobs stay
at their C++ defaults.
