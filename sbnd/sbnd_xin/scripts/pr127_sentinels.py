#!/usr/bin/env python3
"""doc pr/127 sec 5 -- sentinel assertions for shipped, owner-approved fixes.

Why this exists: doc pr/127 found that the pr/93 round-4 fix for SBND
18264-137238 (straight_cont_cross_cluster) stopped firing ~2026-08-21 when
the Q/L era changed under it, and stayed dead in production for ~10 days.
NOTHING in the standing validation bar could see it: a knob A/B compares two
arms that both have the fix on, the event carries no vtx105 label, and in the
pr/125 Bee pair its row read "no-op verified" (true of the flip, silent about
the event).

A sentinel is the missing check: for each shipped fix, the named event it was
shipped for, and a property of the CURRENT production arm that must still
hold.  Cheap (reads arms already on disk), and it fails loudly.

Assertion kinds (energy-valued ones read the PF node text "name  NNN MeV",
so they tolerate the few-MeV drift every round produces and still catch the
structural loss a dead fix causes):
  pf_node_ge   <name> <MeV>  some PF node of that particle name is >= MeV
  pf_node_lt   <name> <MeV>  EVERY PF node of that name is < MeV
  pf_contains  <text>        PF node text contains this substring
  pf_absent    <text>        ... does not
  log_absent   <text>        the per-event run log does NOT contain <text>
  shower_max_ge <|pdg|> <MeV>  max kine_best over calib showers of that |pdg|
  enu_between  <lo> <hi>     kine_reco_Enu in [lo, hi] MeV
  nshowers     <lo> <hi>     len(calib showers) in [lo, hi]
  log_contains <text>        any per-event log in the arm contains this text

Usage:
  ./scripts/pr127_sentinels.py --arms 'work-pr127r1-flipS98-*' 'work-pr127r1-flipS141-*'
  ./scripts/pr127_sentinels.py --arms 'work-pr125r1-flipK5*'          # expect the 137238 FAIL
  ./scripts/pr127_sentinels.py --list

Exit code: 0 = every applicable sentinel PASSed, 1 = at least one FAILed.
A sentinel whose event is not present in the given arms is reported SKIP and
does not fail the run.

RE-BASELINE WARNING: the energy thresholds below are absolute MeV, so a round
that changes the ENERGY SCALE rather than the structure will move them all.
The queued `kine_shower_fudge_factor` 0.80 -> 0.84 flip (doc pr/126) is
exactly that: ~5% on every EM energy.  52693's `pf_node_lt e- 175` sits at
158 today (166 after), and 69314's shower count is exposed from the other
side because K5's own gate is `kine < 10 MeV` -- a 5% bump pushes borderline
crumbs over the cap and the count rises.  When that flip lands, re-measure
and re-baseline these numbers; a FAIL in that round is churn, not regression.
"""
import argparse
import glob
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SX = os.path.dirname(HERE)

# (event, doc, what shipped, [(kind, *args), ...])
# Thresholds are set from the measured post-fix value and the measured
# pre-fix value, and placed between them -- so the sentinel fails when the
# fix dies, not when the number drifts a few MeV.
SENTINELS = [
    (137238, "pr/93 r4 + pr/127", "sccc demote+bridge: the cross-cluster muon body joins PF",
     # RE-BASELINED 2026-09-01 (doc 91 sec 12) -- AND THE DIRECTION FLIPPED.
     # The 08-29 baseline read: pre-fix no mu- at all under the stem, post-fix
     # mu- 207 (body) + mu- 66 (continuation), so the assertion was
     # pf_node_ge mu- 150.
     # Re-measured at the pinned prod0901b point, both sides, same binary+cfg:
     #   production (sccc_max_gap = 10, shipped by pr/127)   mu- [88, 60, 58]
     #   work-91neg-scccgap-nuecc48 (SBND_SCCC_MAX_GAP=6)    mu- [207, 88, 58]
     # The mu- 207 body node now appears with the knob at its PRE-pr/127 value
     # and is ABSENT from production -- i.e. pr/127's own 6 -> 10 flip removed
     # the signature that pr/93 r4 was asserted on.  The owner hand-scanned the
     # production tree on 2026-09-01 and judged it GOOD, so production is the
     # reference and the assertion is inverted to match it.
     # RECORD THIS, do not read it as a threshold move: the shipped pr/93 r4
     # signature is not what production emits any more.
     # SBND_SCCC_BRIDGE_BODY=0 was tried first and is NOT a discriminator here
     # (mu- identical to production); the gap knob is the live one.
     [("pf_node_lt", "mu-", 150.0), ("log_contains", "sccc demote")]),
    (37112, "pr/125 K3", "samevtx track-frag absorb: gamma + proton stem = ONE shower",
     # pre-fix: gamma 549 + a separate 469 MeV proton-typed shower.
     [("shower_max_ge", 11, 700.0), ("pf_node_lt", "proton", 400.0)]),
    (69314, "pr/125 K5", "satellite absorb: the vertex-connected crumbs fold in",
     # pre-fix 25 showers, post-fix 18.
     [("nshowers", 14, 20)]),
    (94392, "pr/125 guard", "pass3_cone track guard: the 305 MeV fake electron is gone",
     [("pf_node_lt", "e-", 250.0)]),
    (52693, "pr/125 guard", "pass3_cone track guard: 183 -> 153 MeV e- + released muon",
     [("pf_node_lt", "e-", 175.0)]),
    (77328, "pr/125 guard", "pass3_cone track guard: 180 MeV EM shower -> re-rooted proton",
     [("pf_node_lt", "e-", 130.0)]),
    (171572, "pr/123 r2", "pf_orphan_guard_freed: the guard-freed muon returns as a PF root",
     [("log_contains", "pf-orphan-guard-freed"), ("pf_node_ge", "mu-", 250.0)]),
    (393505, "pr/123 r2", "pf_orphan_guard_freed: same, second firing event",
     [("log_contains", "pf-orphan-guard-freed")]),
    (348471, "pr/93 r4 + pr/121", "detach_track_stem: no 719 MeV proton-typed aggregate",
     [("pf_node_lt", "proton", 600.0), ("shower_max_ge", 11, 300.0)]),
    (315167, "pr/93 r4", "orphan confident track: the 150.7cm proton is counted + shown",
     [("pf_node_ge", "proton", 500.0)]),   # not in the standard manifests -> SKIP
    # ---- doc pr/128 (PF/kine completeness).  Both knobs carry a distance or
    # angle threshold tuned to measured geometry, the exposure class this
    # registry exists for -- and pr/128's own census found a pr/123 knob had
    # started overlapping a new pool, so overlap is watched here too.
    # (105074, "pr/128 class B", ...) RETIRED 2026-09-02 -- see RETIRED_SENTINELS.
    (55740, "pr/128 class A", "near cross-cluster track: the 123.1cm muon joins PF + kine",
     # pre-fix: absent from both (cross-cluster, score 100, so neither the pr/93
     # confident-track class nor the pr/123 flag class reaches it).
     # post-fix mu- 300 MeV under a pseudo-neutron; Enu 488.5 -> 894.7.
     # RE-SCOPED to OUTCOME-ONLY, doc pr/130: with the pr/130 guard seats ON,
     # `pr128 pf-orphan-near-cross-cluster` is no longer emitted here while the
     # PF output stays BYTE-IDENTICAL (mu- = [111, 300] both ways; 55740 is not
     # among the 10 events the flip changes) -- the 123.1 cm muon now joins PF
     # by a different route.  Same shape as 66366: the knob is masked on its
     # own target event, so the log assertion would fail for a reason that is
     # not a regression.  The outcome assertion still catches a regression of
     # the RESULT from any cause.  pr/128 class A therefore has no event that
     # guards its knob being alive -- see doc pr/130 Part 4.
     [("pf_node_ge", "mu-", 250.0)]),
    (72786, "pr/128 class A", "CONTROL: the continuation terms keep the cosmics OUT",
     # This event's four candidates come from two large off-vertex clusters
     # (148 and 102 cm extent, 35 and 77 cm off the vertex).  On proximity
     # alone they were admitted and put +1151 MeV on a 701 MeV candidate.  A
     # future loosening that re-admits them fires this line.
     # RE-BASELINED doc pr/130 (owner flip 2026-08-29, bee/pr130r3 idx 0).
     # The original second assertion was `pf_node_lt mu- 250` -- the legit
     # maximum mu- here is 238.8 and the four cosmics are 268.9 / 281.7 /
     # 344.0, so 250 separated them.  With shower_pass4_prox_guard_len ON the
     # guard now pulls those four (segs 9004 143.5cm, 9006 114.3cm, 45038
     # 108.3cm, 9008 64.7cm) OUT of the shower and they render as standalone
     # PF mu- 344/281/268.  Owner ruled that correct ("these two are OK"),
     # consistent with the pr/129 ruling on 393505 ("OK to be in PR"): a
     # guard-freed cosmic may be a PF track as long as it is not inside the
     # candidate.  So `pf_node_lt mu- 250` now asserts the OLD, wrong state
     # and is retired.  What still has to hold is that the cosmics are kept
     # out of the shower -- if a future change re-absorbs them the guard stops
     # declining and the log line below vanishes.
     # RE-EXPRESSED doc pr/144 sec 16.  The second clause named a SEGMENT ID,
     # and segment ids renumber whenever the fit changes.  With excl_t0_frame
     # on the guard still declines the same four objects -- OFF declines
     # {45038, 9004, 9006, 9008}, ON declines {45038, 9003, 9006, 9008} -- so
     # the clause failed on a renumbering, not a regression.  The count is the
     # property that survives a renumber; 4 is the shipped value and any
     # re-absorption drops it.
     [("log_absent", "pr128 pf-orphan-near-cross-cluster"),
      ("log_count_ge", "pr130 pass4_prox_guard: decline seg=", 4)]),

    # ---- doc pr/129: the pointing test on the guard-freed kine pool.
    # kine_guard_freed_impact = 20 cm / miss 30 deg, SBND PRODUCTION ON
    # 2026-08-29.  The owner ruled on the pool's ENTIRE population (3 objects,
    # 710.66 MeV, all 239 events of both manifests), so these three assertions
    # cover the whole knob -- there is nothing else it can touch.
    (393505, "pr/129", "cosmic cluster 15 no longer counted into Enu",
     # The DROP.  268.70 MeV of a 295.0 cm end-to-end chain that never comes
     # within 68.9 cm of the nu vertex; impact 68.67 cm, miss 67.4 deg.
     # Enu 940.4 -> 566.1.  The muon must STAY in the PF tree (owner: "OK to
     # be in PR"), so this is deliberately an Enu assertion, not a pf_absent.
     # RE-BASELINED 2026-09-01 (doc 91 sec 12).  A genuine threshold move, and
     # the only one of the six that was: production drifted to Enu 559.9, which
     # missed the [560, 572] window by 0.1 MeV.  Re-measured both sides:
     #   production (pointing test ON)                   Enu  559.9
     #   work-91neg-gfimpact-mcp2k (SBND_KINE_GF_IMPACT=0) Enu 1638.8
     # The knob is worth 1079 MeV here, so the window can absorb ordinary drift
     # and still fail loudly when the fix dies.  [540, 600] leaves 40 MeV of
     # headroom on each side and is 1038 MeV clear of the fix-dead value.
     # RE-BASELINED 2026-09-06 (doc 145 sec 3.4), both sides measured at the
     # d145 pin.  The literal was "mu-  268" and the node reads "mu-  267 MeV" --
     # ONE MeV of ordinary drift.  Note what that clause is and is not: it reads
     # IDENTICALLY on the armed arm (work-*-d145np) and the knob-off control
     # (work-*-d144fixprod), so it never discriminated the pr/129 fix at all; it
     # only asserts the owner's "OK to be in PR", that the muon is not deleted
     # from the PF tree.  pf_contains takes a raw substring, so unlike
     # pf_node_ge/pf_node_lt it does NOT tolerate the few-MeV drift every round
     # produces, and it will need re-baselining again whenever the energy scale
     # moves.  The clause that actually discriminates is enu_between, and it is
     # causal: knob off Enu=858.2 (FAIL), knob armed at 20 cm / 30 deg
     # Enu=574.8 (PASS) -- 283.4 MeV on this one event.
     [("enu_between", 540.0, 600.0), ("pf_contains", "mu-  267")]),
    (171572, "pr/129", "real daughter KEPT by the pointing test",
     # The KEEP, and the negative control for the DROP above: impact 4.16 cm,
     # miss 11.8 deg.  Owner: "784.9 MeV should be the right energy."  A
     # future tightening that loses this fires here.
     [("enu_between", 779.0, 791.0), ("pf_contains", "mu-  304")]),
    (94392, "pr/129", "guard-freed/continuation hand-off costs nothing",
     # With the guard-freed pool bounded, the identical segment is counted by
     # pr/128's kine_count_near_cross_cluster instead, so Enu must NOT move.
     # Owner: "is OK".  Guards the mutual exclusivity of the two pools.
     [("enu_between", 1136.0, 1149.0)]),

    # ---- doc pr/130: pr/120's backward-stem guard, which had no sentinel.
    # stem_backfill_back_guard SBND PRODUCTION ON 2026-08-28.  Registered
    # ONE-SIDED on purpose -- see the note below the registry.
    (47212, "pr/120", "stem_backfill_back_guard: the backward stem stays OUT of the shower",
     # Both sides measured at TODAY's baseline (2026-08-29), not read off
     # pr/120's doc -- the 347890 lesson was that a threshold taken from a
     # stale table passes the negative control on a dead knob.
     #   guard ON  (work-pr129r1-on98-mcp2k, production): seg 2103 renders as
     #             its own `pi+ 53 MeV` track; big EM shower `gamma 614`; 19 nodes.
     #   guard OFF (work-pr130-47212-guardoff, one-event arm): NO pi+ node at
     #             all -- the shower ate it; `gamma 688`, pi0 119 -> 150; 18 nodes.
     # Exactly one pi+ exists in the ON tree, so pf_contains cannot pass
     # trivially.  650 sits between the two gamma values.
     # RE-BASELINED 2026-09-01 (doc 91 sec 12).  The old assertion looked for a
     # `pi+` node and FAILED against production -- but the fix is fine; the
     # backward stem is simply TYPED differently now.  Re-measured both sides at
     # the pinned prod0901b point:
     #   production (guard ON)                          mu- [53.0]
     #   work-91neg-backguard-mcp2k (guard OFF)         mu- []       <- absorbed
     # So the stem is still a separate track when the guard is on and is still
     # eaten by the shower when it is off -- exactly the structural property
     # pr/120 shipped.  Asserting the TYPE LABEL (pi+) rather than the structure
     # is what went stale.  40 MeV sits well under the 53 seen and well over the
     # nothing-at-all of the guard-off arm.
     # pf_node_lt gamma 650 is KEPT as a sanity bound but is NOT a
     # discriminator: 571 (on) vs 576 (off), both far below 650.
     [("pf_node_ge", "mu-", 40.0), ("pf_node_lt", "gamma", 650.0)]),

    # ---- doc pr/130: the doc-84 long-muon / MCS family.  Every one of these
    # is a shipped, SBND-PRODUCTION-ON fix whose target event is in NO standard
    # manifest (em114 / em114c), so before this round the whole family was
    # invisible to every gate we run -- the exact exposure doc pr/127 was
    # written about.  These events only execute if the arm list includes
    # work-sent<TAG>-mcp{1,2}k from scripts/pr130_sentinel_arm.sh; otherwise
    # they report SKIP, which reads like a pass.
    # Post-fix values measured 2026-08-29 in work-sent130-*; pre-fix values are
    # doc 84's own, and each threshold sits between the two.
    (497311, "doc 84 r1", "long-muon range fallback: the 332.8 cm unbroken muon gets a range KE",
     # pre-fix 508.5, post-fix 766.3 -- and note this is the SHOWER kine_best,
     # not the PF node (which reads 473 MeV here; they are different quantities).
     [("shower_max_ge", 13, 700.0),
      ("log_contains", "long_muon_range_empty_chain_fallback: recomputed kinematics")]),
    (66366, "doc 84 r1", "OUTCOME ONLY -- the 300.6 cm chain / 692.2 MeV result",
     # CAVEAT, measured doc pr/130: this entry does NOT guard
     # long_muon_stub_bridge_len.  Re-run with the knob at its legacy 6.0
     # (compiled-config proof: 7.5 in prod vs 6 in work-sent130neg2-*, and
     # members_geometry / cathode_bridge / range_fallback all off as well) the
     # event STILL reads nseg_chain=4 L_cm=300.6 range=692.2 -- identical.  So
     # doc 84 r1's P3 rescue is now produced by another route on its own target
     # event, and no event currently guards that knob.  Kept as an outcome
     # sentinel (it still catches a regression of the RESULT from any cause);
     # see doc pr/130 Part 2 "the masked knob".
     # RE-EXPRESSED doc pr/144 sec 16.  With excl_t0_frame on the chain is still
     # assembled but from 3 segments instead of 4 and at 299.5 cm instead of
     # 300.6, so an exact-literal clause failed on a 1.1 cm move.  The chain
     # being FOUND at all is the outcome this entry exists for; its length is
     # already guarded by the mu- energy clause beside it.
     [("pf_node_ge", "mu-", 650.0), ("log_contains", "nseg_chain=")]),
    (313847, "doc 84 r2", "long_muon_members_geometry: out-of-chain muon members join the range",
     # pre-fix 547.5, post-fix 602.2.
     [("pf_node_ge", "mu-", 575.0)]),
    (281595, "doc 84 r2", "members_geometry: the 221 cm continuation beats the 13.9 cm stub",
     # pre-fix 750.1, post-fix 808.5.
     [("pf_node_ge", "mu-", 780.0)]),
    (53793, "doc 84 r2", "long_muon_cathode_bridge: two half-showers become one muon",
     # pre-fix two halves 367 + 528, post-fix 912.9 -- 700 is above the larger half.
     [("pf_node_ge", "mu-", 700.0), ("log_contains", "long_muon_cathode_bridge:")]),
    (177536, "doc 84 r2.1", "cathode bridge + BFS main-vertex guard + start re-seat",
     # pre-fix 679, post-fix 907.0.  The proton line guards round 2.1 itself:
     # before the guard the bridge BFS walked THROUGH the main vertex and ate
     # the proton prong.
     [("pf_node_ge", "mu-", 800.0), ("pf_node_ge", "proton", 100.0)]),
    (77978, "doc 84 r2.1", "same, the owner's scan event (proton prong must survive)",
     # pre-fix 337.5, post-fix 388.2.
     [("pf_node_ge", "mu-", 365.0), ("pf_node_ge", "proton", 100.0)]),
    (172794, "doc 84 r4", "long_muon_cathode_bridge_lever 5 -> 15 cm",
     # The accept line is the primary assertion -- it is binary and exact.
     # post-fix chain 298.7 cm / range 687.8 MeV.
     [("log_contains", "long_muon_cathode_bridge: absorb bare chain into sid=1"),
      ("pf_node_ge", "mu-", 600.0)]),
    (347890, "doc 84 r4", "long_muon_cathode_bridge_track_partner (far half mis-PID'd 211)",
     # pre-fix 429.0 (measured in the knobs-off control), post-fix 488.7.
     # The first draft used 400 here and the negative control PASSED it at
     # 429 -- only the log line caught the dead knob.  460 sits between.
     [("log_contains", "long_muon_cathode_bridge: merge shower sid=5"),
      ("pf_node_ge", "mu-", 460.0)]),
    (67026, "doc 84 r4", "long_muon_cathode_bridge_short_gap 8 cm (gap-angle waived, gap>0)",
     # post-fix chain 325.2 cm / range 748.6 MeV.
     [("log_contains", "long_muon_cathode_bridge: absorb bare chain into sid=0"),
      ("pf_node_ge", "mu-", 650.0)]),

    # ---- doc pr/130 item B: stem_backfill_back_dvtx = 45 cm, SBND PRODUCTION
    # ON 2026-08-29 (owner: "For B, flip on for SBND production").  These two
    # events were the guard's only errors and were DELIBERATELY UNASSERTED
    # until this fix shipped -- see the note below the registry, now updated.
    # The flip changes exactly these 2 of 239 events, and on both the PF tree
    # it produces is IDENTICAL to the guard-OFF shape the owner reviewed in
    # bee/pr130r2 and preferred.  Both assertions are binary, not thresholds
    # on a drifting energy.
    (292643, "pr/130 B", "back-guard dvtx escape: the declined stem is absorbed",
     # pre-flip: mu- 59 + mu- 441, no pi0 and no pi+ at all, e- max 227, 10 nodes.
     # post-flip: mu- 441, pi0 150, pi+ 91 + pi+ 65, e- max 154, 13 nodes.
     # RE-BASELINED 2026-09-01 (doc 91 sec 12) -- the pi0 side REVERSED.
     # The 08-29 baseline recorded post-flip pi0 150 and asserted pi0 >= 100.
     # Re-measured at the pinned prod0901b point:
     #   production (back_dvtx = 45)                     pi0 [] -- none
     #   work-91neg-backdvtx-mcp1k (SBND_..._BACK_DVTX=0) pi0 [159.0]
     # The pi0 now appears with the escape DISABLED and is absent from
     # production, the opposite of 08-29.  That matches this event's twin,
     # 179369 below, whose shipped assertion is pf_absent pi0 ("the spurious
     # pi0 is gone") -- so the two entries of the same fix now agree instead of
     # contradicting.  Owner scanned production GOOD on 2026-09-01.
     # The log assertion needs no change: it is True in production and False in
     # the knob-off arm, i.e. it was already a working discriminator.
     [("pf_absent", "pi0"), ("pf_node_lt", "e-", 200.0),
      ("log_contains", "pr130 stem_backfill_back_dvtx: suppress decline seg=18008")]),
    (179369, "pr/130 B", "back-guard dvtx escape: the spurious pi0 is gone",
     # pre-flip: pi0 138 + pi+ 56 fabricated by the decline (+376.0 MeV the
     # owner ruled against), 43 nodes.  post-flip: NO pi0 and NO pi+ anywhere
     # in the tree, 39 nodes -- so pf_absent is exact here, not a threshold.
     # RE-BASELINED doc pr/144 sec 16, both sides measured at the flipped point
     # (work-s144pos-mcp2k vs work-s144neg-dvtx, one binary, one cfg):
     #   frame OFF, fix ON  (pre-flip production)  33 nodes, NO pi0
     #   frame ON,  fix ON                         46 nodes, pi0 130
     #   frame ON,  fix OFF                        49 nodes, pi0 112 + pi0 130
     # The fix is ALIVE and still removes its own pi0 (112), together with the
     # e- 201 / gamma 201 pair and pi+ 54.  What broke the old assertion is a
     # DIFFERENT pi0 at 130 MeV that appears in the corrected drift frame, on
     # an event the owner scanned and ruled better (doc 144 sec 8, Bee idx 0).
     # So the entry now asserts what pr/130 B actually does, and the arrival of
     # the 130 MeV pi0 is tracked as item 5, not as a dead fix here.
     [("pf_absent", "pi0  112"),
      ("log_contains", "pr130 stem_backfill_back_dvtx: suppress decline seg=17002")]),

    # ---- doc pr/130 item 1b: the two guard seats, SBND PRODUCTION ON
    # 2026-08-29 (owner flip on bee/pr130r3).  Both thresholds are the SIBLING
    # seat's own shipped value, not a refit, so a future change to pr/123's 50
    # or pr/124's 15 should be mirrored here or these will drift apart.
    (100222, "pr/130 prox", "shower_pass4_prox_guard_len: the 110cm muon leaves the EM shower",
     # pre-flip: e- 2523 with seg 14003 (110.3 cm pdg-13) inside it and no
     # standalone muon.  post-flip: e- 2203, mu- 271 appears.  This one
     # segment is 34.5% of the labelled over-clustering charge on the 141-set.
     [("pf_node_ge", "mu-", 250.0), ("pf_node_lt", "e-", 2400.0),
      ("log_contains", "pr130 pass4_prox_guard: decline seg=14003")]),
    (175896, "pr/130 backfill", "shower_pass3_backfill_guard_len: the declined proton is not re-adopted",
     # pre-flip: e- 256 with seg 66041 re-adopted by the pass3 sibling backfill
     # after pr/124's guard had declined it, and force-relabelled pdg 11 (no
     # proton node at all).  post-flip: e- 114, proton 159 appears.
     [("pf_node_ge", "proton", 100.0), ("pf_node_lt", "e-", 200.0),
      ("log_contains", "pr130 pass3_backfill_guard: decline seg=66041")]),

    # ---- doc pr/130: pr/124's headline win had no sentinel either.  It is in
    # em114c, so unlike the doc-84 family it does execute under the standard
    # 141 arms -- it was simply never registered.
]

# ---------------------------------------------------------------------------
# RETIRED 2026-09-01 (doc 91 sec 12.4) -- owner: "We do not need to track
# these, we are good."  Kept as a record, not as a check: nothing below runs.
#
# Each guarded a shipped, SBND-PRODUCTION-ON fix whose knob still changes
# tracking-pr.root, but whose SENTINEL EVENT no longer separates fix-alive from
# fix-dead.  A threshold cannot be re-baselined onto a pair of equal values: it
# would be green and unable to fail, the dead safety net doc pr/127 exists to
# prevent.  Re-targeting each onto an event where its knob still bites was
# offered and DECLINED by the owner, so they are retired rather than carried.
#
# CONSEQUENCE, stated once and not argued: shower_pass3_cone_guard_len and
# shower_pass4_prune_gap2 are shipped SBND-ON knobs that now have NO sentinel.
# If either dies the way pr/93 r4 did, nothing here will see it.  That is the
# owner's call, recorded so a later round does not rediscover it as a surprise.
#
# The measurement is kept so nobody re-derives it.  Taken at the pinned
# prod0901b point, both sides, same binary+cfg:
#
#   173819  pr/125 pass3_cone track guard
#           production (guard_len = 15)                    e- [283, 18, 16]
#           work-91neg-p3cone-mcp2k (GUARD_LEN=0)          e- [288, 16]
#           The shipped effect was "301 MeV EM shower -> re-rooted proton".
#           There is no proton on either side now and the whole difference is
#           5 MeV plus one 18 MeV node -- inside ordinary drift, so no threshold
#           can separate them honestly.
#
#   406125  pr/124 shower_pass4_prune_gap2 = 25
#           production and work-91neg-prune2-mcp2k have IDENTICAL PF trees
#           (14 nodes, zero symmetric difference).  The knob still changes
#           tracking-pr.root, so the code path is live somewhere -- but it is
#           completely inert on this event, and the two log_contains assertions
#           fail on BOTH sides.
#
# IF ANYONE REVIVES THESE: re-targeting means running the knob off across a
# sample, diffing PF trees per event, and picking one where the fix still fires.
# A search, not a threshold edit.  Do NOT simply move the numbers until they go
# green -- that is what made this registry stale in the first place.
# ---------------------------------------------------------------------------
# RETIRED 2026-09-02 (doc 98) -- owner: "feel free to retire".
#
# 105074 is a DIFFERENT retirement from the two below and the difference
# matters.  Those two were inert-but-present: the event still had a PF tree, the
# knob simply no longer moved it.  105074 has NO PF TREE AT ALL in production.
# Measured on work-mcp2k-d97fvpr2 (ref/prod-2026-09-04):
#
#   mabc-pr.zip carries THREE members -- 0-clustering-global.json and two
#   channel-deadarea maps -- and no data/0/0-mc.json.  nusel says one bundle,
#   878 pts / 92.4 cm, flash at -981.6 us, in_beam=0, not-tagged.
#
# So TaggerCheckNeutrino selects no candidate here any more and the event is not
# even in-beam.  `pf_node_ge mu- 180` cannot be re-baselined onto that: there is
# no PF output to assert against, at any threshold.  This is not a stale number,
# it is a vanished subject.
#
# WHY PRODUCTION LOOKS LIKE THIS, and why it is not a regression: sep_fv_point
# went SBND-ON on 2026-09-02 (doc 97) and 105074 is one of the events it moves.
# The owner scanned that arm's flips and ruled them improvements, which is what
# licensed the flip.  The sentinel was written against the pre-flip world.
#
# CONSEQUENCE, stated once and not argued: `pr128 pf-conn4-near` is a shipped
# SBND-ON code path that now has NO sentinel.  pr/128 class A (55740) is a
# different knob and does not cover it.  If conn4_near dies the way pr/93 r4
# did, nothing here will see it.  Recorded so a later round does not rediscover
# it as a surprise.
#
# Re-targeting it means finding an event where conn4_near still fires and the
# guard still bites -- a search across the sample, not a threshold edit.
# ---------------------------------------------------------------------------
# doc sbnd_xin/pr/144 sec 16 -- the excl_t0_frame flip (2026-09-06) epoch.
#
# INERT_AT_D144.  A sentinel exists to catch a shipped fix dying silently.  It
# can only do that if removing the fix changes the event.  These entries were
# measured as a 2x2 -- {frame on, frame off} x {fix on, fix off}, one binary
# (b46179b2 + the pr/144 remove_vertex guard), one cfg, per-knob negative
# controls whose compiled config was proven to differ from production in
# EXACTLY the one intended key (scripts/pr144_sentinel_neg.sh):
#
#   knob                              event(s)        legacy frame  new frame
#   stem_backfill_back_dvtx           179369          DIFF          DIFF   live
#   sccc_max_gap 10 -> 6              137238          DIFF          DIFF   live
#   stem_backfill_back_guard          47212           DIFF          SAME   inert
#   shower_pass3_cone_guard_len       52693           DIFF          SAME   inert
#   shower_pass4_prox_guard_len       100222          DIFF          SAME   inert
#   shower_pass3_backfill_guard_len   175896          DIFF          SAME   inert
#   long_muon_members_geometry        281595          DIFF          SAME   inert
#   kine_guard_freed_impact           94392, 171572   SAME          SAME   ALREADY inert
#
# Five knobs stopped biting ON THEIR OWN SENTINEL EVENT when the drift frame
# was corrected.  That is not "the fix died" and it is not a threshold that
# wants nudging -- the event simply no longer exercises the knob.  Reporting
# them FAIL would say something false; reporting them PASS after a re-baseline
# would be worse, because the entry would then be green and unable to fail --
# the dead safety net doc pr/127 exists to prevent.  They report INERT.
#
# kine_guard_freed_impact is different in kind: it was ALREADY inert on 94392
# and 171572 before this round, in both frames.  pr/129's own footprint note
# says so -- "exactly ONE event's kine_reco_Enu moves (393505)" -- so those two
# entries never discriminated and this 2x2 is what exposed it.
#
# CONSEQUENCE, stated once and not argued: stem_backfill_back_guard,
# shower_pass3_cone_guard_len, shower_pass4_prox_guard_len,
# shower_pass3_backfill_guard_len, long_muon_members_geometry and
# kine_guard_freed_impact are shipped SBND-ON knobs with no event in this
# registry that can catch them dying.  Retargeting each onto an event where it
# still bites is the fix, it is a population scan per knob, and the owner
# DECLINED the same offer in doc pr/130 -- so it is recorded here rather than
# done unasked.  doc pr/144 sec 16 prices it.
INERT_AT_D144 = {
    (47212,  "pr/120"):          "stem_backfill_back_guard on/off byte-identical at this epoch",
    (52693,  "pr/125 guard"):    "shower_pass3_cone_guard_len on/off byte-identical at this epoch",
    (100222, "pr/130 prox"):     "shower_pass4_prox_guard_len on/off byte-identical at this epoch",
    (175896, "pr/130 backfill"): "shower_pass3_backfill_guard_len on/off byte-identical at this epoch",
    (281595, "doc 84 r2"):       "long_muon_members_geometry on/off byte-identical at this epoch",
    (94392,  "pr/129"):          "kine_guard_freed_impact on/off byte-identical in BOTH frames -- never discriminated",
    (171572, "pr/129"):          "kine_guard_freed_impact on/off byte-identical in BOTH frames -- never discriminated",
}

# KNOWN_OPEN_D144.  These four DO fail for a real reason, each traced to a
# named defect that is open in doc pr/144.  They stay red on purpose: the suite
# must not go green over them, and it must not read them as unexplained either.
KNOWN_OPEN_D144 = {
    (137238, "pr/93 r4 + pr/127"):
        "doc 144 sec 15 -- the exclusion pool empties (n_excluded 9 -> 1) and the EM "
        "shower absorbs it; item 5, a PID round",
    (177536, "doc 84 r2.1"):
        "doc 144 sec 14.2 -- nothing is lost; the muon is SPLIT into two PF nodes "
        "(908.6 -> 276.0 + 644.3) and the split double-counts a 105.7 MeV rest mass",
    (347890, "doc 84 r4"):
        "doc 144 sec 14.1 -- the far half is still reconstructed but its PID flips "
        "211 -> 11, and doc 84 r4's partner filter refuses EM partners by design; item 5",
    # (393505, "pr/129") -- WAIVER LIFTED 2026-09-06, doc 145 sec 8.  The defect
    # it tracked (a cluster-15 cosmic admitted by kine_count_near_cross_cluster
    # on proximity alone, gap 0.00 cm) is FIXED IN SBND PRODUCTION: the owner
    # flipped kine_near_pointing_impact = 200 / kine_near_pointing_miss_deg = 30
    # in the SBND PR driver, and this event's clauses now read
    # Enu = 574.8 in [540, 600] and pf_contains 'mu-  267' on an arm run with NO
    # TLA at all (work-*-d145prod).  Note the operating point is NOT the 20/30
    # doc 145 sec 3 priced: at 20 cm the impact clause also refused 392009, a
    # real daughter, which is why 20/30 was not shipped (sec 3.8).
    #
    # THIS ENTRY IS THE SUITE'S ONLY LIVE ASSERTION ON THE WHOLE pr/129 FEATURE.
    # The other two pr/129 sentinels (94392, 171572) are INERT -- the knob was
    # measured byte-identical on/off for them in both frames, so they never
    # discriminated it.  If 393505 goes red, read it as the pointing test dying,
    # not as drift; the fix is worth 283.4 MeV here and the window has 40 MeV of
    # headroom each side.
}

RETIRED_SENTINELS = [
    (105074, "pr/128 class B", "conn4_near: the two main-cluster pdg-13 showers",
     "no PF tree in production at all (mabc-pr.zip has 3 members, no 0-mc.json); "
     "event is not in-beam; nothing to assert against at any threshold"),
    (173819, "pr/125 guard", "pass3_cone track guard",
     "guard on/off differ by 5 MeV on e- max (283 vs 288); shipped proton re-root gone from both"),
    (406125, "pr/124 A", "shower_pass4_prune_gap2 gap-band tier-2 prune",
     "PF trees IDENTICAL with the knob on and off; both log assertions fail on both sides"),
]

# ---------------------------------------------------------------------------
# DELIBERATELY UNASSERTED -- do not "complete" these without reading why.
#
# RESOLVED 2026-08-29.  292643 and 179369 were held unasserted because a
# sentinel written for either would have pinned a production state the owner
# had just condemned.  doc pr/130 item B shipped the fix
# (stem_backfill_back_dvtx = 45, SBND ON) and both are now registered above,
# so stem_backfill_back_guard's whole 8-candidate population is adjudicated
# AND correct: 47212 + 281567 guard the declines, 292643 + 179369 guard the
# escapes.  Nothing about this knob is unasserted any more.
#
# long_muon_stub_bridge_len has NO guarding event at all: its only target
# (66366) still produces the identical result with the knob at its legacy 6.0,
# so the knob is masked by another route.  See doc pr/130 Part 2.
# ---------------------------------------------------------------------------


def pf_texts(arm, event):
    z = os.path.join(arm, "pr_evt%d" % event, "mabc-pr.zip")
    if not os.path.exists(z):
        return None
    out = []

    def walk(n):
        out.append(n.get("text", ""))
        for c in n.get("children", []):
            walk(c)

    with zipfile.ZipFile(z) as zf:
        for root in json.loads(zf.read("data/0/0-mc.json")):
            walk(root)
    return out


def calib(arm, event):
    p = os.path.join(arm, "pr_evt%d" % event, "calib-pr-evt%d.json" % event)
    return json.load(open(p)) if os.path.exists(p) else None


def find_arm(arms, event):
    for pat in arms:
        for root in sorted(glob.glob(os.path.join(SX, pat)) or glob.glob(pat)):
            if os.path.isdir(os.path.join(root, "pr_evt%d" % event)):
                return root
    return None


def pf_energies(arm, event, name):
    """MeV values of every PF node rendered as '<name>  <NNN> MeV'."""
    out = []
    for t in pf_texts(arm, event) or []:
        m = re.match(r"(\S+)\s+(-?\d+(?:\.\d+)?)\s+MeV\s*$", t.strip())
        if m and m.group(1) == name:
            out.append(float(m.group(2)))
    return out


def check(arm, event, assertion):
    kind = assertion[0]
    if kind in ("pf_node_ge", "pf_node_lt"):
        vals = pf_energies(arm, event, assertion[1])
        hit = any(v >= assertion[2] for v in vals)
        ok = hit if kind == "pf_node_ge" else not hit
        return ok, "%s %s %.0f MeV (seen: %s)" % (
            kind, assertion[1], assertion[2],
            ", ".join("%.0f" % v for v in sorted(vals, reverse=True)[:4]) or "none")
    if kind == "shower_max_ge":
        j = calib(arm, event)
        vals = [s["kine_best"] for s in (j or {}).get("showers", [])
                if abs(s.get("particle_id", 0)) == assertion[1]]
        mx = max(vals) if vals else None
        ok = mx is not None and mx >= assertion[2]
        return ok, "max |pdg|=%d shower %s want >= %.0f MeV" % (
            assertion[1], "%.1f" % mx if mx is not None else "none", assertion[2])
    if kind in ("pf_contains", "pf_absent"):
        texts = pf_texts(arm, event) or []
        hit = any(assertion[1] in t for t in texts)
        ok = hit if kind == "pf_contains" else not hit
        return ok, "%s '%s' (%d PF nodes)" % (kind, assertion[1], len(texts))
    if kind == "enu_between":
        j = calib(arm, event)
        e = j["kine"]["kine_reco_Enu"] if j else None
        ok = e is not None and assertion[1] <= e <= assertion[2]
        return ok, "Enu=%s want [%.0f, %.0f]" % (
            "%.1f" % e if e is not None else "?", assertion[1], assertion[2])
    if kind == "nshowers":
        j = calib(arm, event)
        n = len(j["showers"]) if j else None
        ok = n is not None and assertion[1] <= n <= assertion[2]
        return ok, "showers=%s want [%d, %d]" % (n, assertion[1], assertion[2])
    if kind in ("log_contains", "log_absent"):
        pat = os.path.join(arm, "pr_evt%d" % event, "*.log")
        hit = any(assertion[1] in open(f, errors="replace").read()
                  for f in glob.glob(pat))
        ok = hit if kind == "log_contains" else not hit
        return ok, "%s '%s'" % (kind, assertion[1])
    if kind == "log_count_ge":
        # doc pr/144 sec 16.  Count DISTINCT lines carrying a prefix, for
        # guards whose log line names a segment id: ids renumber whenever the
        # fit changes, so "seg=9004" is not a property of the reconstruction
        # but the NUMBER of objects the guard declined is.
        pat = os.path.join(arm, "pr_evt%d" % event, "*.log")
        lines = set()
        for f in glob.glob(pat):
            for line in open(f, errors="replace"):
                i = line.find(assertion[1])
                if i >= 0:
                    lines.add(line[i:].strip())
        n = len(lines)
        return n >= assertion[2], "log_count_ge '%s' want >= %d (seen: %d)" % (
            assertion[1], assertion[2], n)
    return False, "unknown assertion %s" % kind


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["work-pr127r1-flipS98-*",
                                                  "work-pr127r1-flipS141-*"])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="evaluate INERT_AT_D144 entries too (doc pr/144 sec 16); "
                         "use when re-testing whether a knob bites again")
    args = ap.parse_args()

    if args.list:
        for ev, doc, what, _ in SENTINELS:
            print("%-8d %-18s %s" % (ev, doc, what))
        return 0

    nfail = nskip = npass = ninert = nopen = 0
    for ev, doc, what, assertions in SENTINELS:
        key = (ev, doc)
        # doc pr/144 sec 16: an entry whose knob no longer bites on its own
        # event cannot report PASS or FAIL honestly.  Say so, and say why.
        if key in INERT_AT_D144 and not args.all:
            print("INERT %-7d %-18s %s" % (ev, doc, what))
            print("        %s" % INERT_AT_D144[key])
            ninert += 1
            continue
        arm = find_arm(args.arms, ev)
        if not arm:
            print("SKIP %-8d %-18s (no arm has this event)" % (ev, doc))
            nskip += 1
            continue
        verdicts = [check(arm, ev, a) for a in assertions]
        ok = all(v[0] for v in verdicts)
        tag = "PASS" if ok else ("OPEN" if key in KNOWN_OPEN_D144 else "FAIL")
        print("%s %-8d %-18s %s" % (tag, ev, doc, what))
        print("        arm=%s" % os.path.basename(arm))
        for (v, msg), a in zip(verdicts, assertions):
            print("        [%s] %s" % ("ok" if v else "XX", msg))
        if tag == "OPEN":
            print("        OPEN: %s" % KNOWN_OPEN_D144[key])
        if ok and key in KNOWN_OPEN_D144:
            print("        NOTE: this KNOWN_OPEN entry now PASSES -- the defect it "
                  "tracks may be fixed; re-read doc pr/144 sec 16 before removing it.")
        npass += 1 if ok else 0
        if not ok:
            if tag == "OPEN":
                nopen += 1
            else:
                nfail += 1
    print("\n%d PASS, %d FAIL, %d OPEN, %d INERT, %d SKIP"
          % (npass, nfail, nopen, ninert, nskip))
    # OPEN entries are tracked defects, not regressions: they do not fail the
    # run.  A bare FAIL still does.
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
