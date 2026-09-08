# SBND `work-*` tag index

Repro:

```bash
cd sbnd_xin
ls -1 | wc -l                    # 228 top-level entries after the 2026-08-29 round;
                                 # 74 after the 2026-08-03 TIDY round
                                 #   (216 before it) -- see that section below
# COUNT work* DIRS THROUGH THE REAL PATH, NOT THE SYMLINK -- see the 2026-08-13
# section's "defect 4": toolkit/sbnd_xin is a symlink, and neither find nor du
# descends a symlink argument, so both silently report 0 from there.
# the 2026-09-01b round (doc 91): COUNT-driven, not byte-driven -- 101 -> 52
# work* dirs.  Owner: "do we need all of them? ... it is just difficult to look
# at them" + "Peer is done" + "We want to keep the latest production though".
# EDIT scripts/retire/PROTECTED.txt BY HAND FIRST -- ASSERT 7 trips otherwise.
./scripts/pr127_sentinels.py --arms 'work-*-prod0901b'    # 27 PASS, 6 FAIL -- doc 91 sec 7, OPEN
python3 scripts/retire/sentinel_guard_20260901b.py \
        scripts/retire/state-20260901b/plan.json "$PWD"   # per-arm; 5 regressions, 2 single-witness
python3 scripts/retire/verify_group_dupes_20260901b.py
python3 scripts/retire/plan_20260901b.py                  # 16 asserts, "OVERALL: PASS"
RETIRE_JOBS=32 python3 scripts/retire/archive_records_20260901b.py   # integrity PASS 49/49
./scripts/retire/retire_20260901b.sh A                    # DRY RUN -- check dirs=/bytes= vs the plan
RETIRE_REPLAN=1 python3 scripts/retire/plan_20260901b.py  # re-stamp planned_at (interlock 6)
CONFIRM=yes ./scripts/retire/retire_20260901b.sh A        # 47 dirs, refused=0
#   (2 more were empty shells left by the git mv above and went by plain rmdir,
#    which refuses a non-empty dir -- see doc 91 sec 9.1)
#
# the 2026-09-01 round (doc 89): the CLOSED pr/136-142 campaigns + doc 77 r3/r4,
# and production REBASED onto the pinned operating point.  150G -> 66G.
# EDIT scripts/retire/PROTECTED.txt BY HAND FIRST -- ASSERT 7 trips otherwise.
./scripts/doc89_prod0901b_arms.sh                       # Phase 1: 3067 evts at ref/prod-2026-09-01b
python3 scripts/doc89_successor_gate.py --jobs 32       # Phase 2: 3067/3067 OK -- licenses the prod0901 release
python3 scripts/retire/verify_group_dupes_20260901.py   # PASS 1259176/1259176 members, 193/193 archives
python3 scripts/retire/plan_20260901.py                 # 14 asserts, "OVERALL: PASS"
RETIRE_JOBS=32 python3 scripts/retire/archive_records_20260901.py
./scripts/retire/retire_20260901.sh A                   # DRY RUN -- check dirs=/bytes= vs the plan
RETIRE_REPLAN=1 python3 scripts/retire/plan_20260901.py # re-stamp planned_at (interlock 6)
CONFIRM=yes ./scripts/retire/retire_20260901.sh A       # 218 dirs
python3 scripts/retire/recompress_archive_20260901.py --apply --jobs 6 --min-mb 1.0
CONFIRM=yes ./scripts/retire/sweep_tmp_20260901.sh      # after the round, never before
# the 2026-08-31 and 08-31b rounds are recorded in docs/pr/135 sec 11 and 11.2,
# NOT here: 169G -> 91G (439 arms) then 91G -> 73G (24 arms, prod0825 released).
find /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin \
     -maxdepth 1 -name 'work*' -type d | wc -l
                                 # 121 after the 2026-08-29 round -- 120 KEEP plus
                                 #   work-pr130-flipchk-mcp2k, which the PEER created
                                 #   after the plan ran.  That is the design, not a
                                 #   miss: the driver iterates the tier list, so an arm
                                 #   born after the plan is invisible to it.  552
                                 #   before it, 432 removed, 81 GiB -- see that section;
                                 # 26 after the 2026-08-25b round retired the
                                 #   stage-A reference side (work-img-* for the
                                 #   4 data samples + work-*-ql0819) and the
                                 #   pre-flip work-*-prod0823; 38 before it,
                                 #   12 removed, 39 GiB (~36 G net) -- see that
                                 #   section below and doc 81 sec 11;
                                 # 42 after the 2026-08-23 prod0823 campaign
                                 #   added its four PR arms (72G);
                                 # 38 after the 2026-08-23 minimal-state round
                                 #   (418 before it, regrown from 08-20's 36 in
                                 #   three days by docs pr/98-111); 380 removed,
                                 #   148 GiB, all 10 asserts PASS -- see that
                                 #   section below;
                                 # 36 after the 2026-08-20 pr/97 crash-sweep round
                                 #   (520 before it: the 484 work-pr97* arms from
                                 #   doc pr/97's gojsonnet-crash investigation,
                                 #   closed and gated -- see that section); GiB
                                 #   unchanged to the du tool's rounding (54G before
                                 #   and after -- the 484 dirs held only ~1.5 GiB);
                                 # 51 after the 2026-08-19 PASS 1 (362 before it,
                                 #   regrown from 08-17's 30 in 54 hours); the
                                 #   ql0819/prod0819 campaign then added 8 arms
                                 #   (+ 5 gate/probe arms and the other session's
                                 #   5 pr96 arms) taking it to 67 / 71G, and
                                 #   PASS 2 took it to 36 / 54G -- see that section;
                                 # 30 after the 2026-08-17 round (178 before it,
                                 #   regrown from 08-16's 18); 18 after the
                                 #   2026-08-16 round + its same-day follow-up
                                 #   (216 before it, regrown from 08-13's 13);
                                 #   13 after 2026-08-13 (401 before it; 18
                                 #   after 2026-08-11, 471 before it; 32 after
                                 #   2026-08-05, 233 before it; 19 after the
                                 #   2026-08-03 tidy round, 27 after the
                                 #   retirement round the same day, 138 before
                                 #   it; 23 after 2026-08-02, 254 / 155 GiB
                                 #   before that, 15 after 2026-07-30)
du -sh /nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
                                 # 75G after the 2026-08-29 round (152G before it);
                                 #   the floor is now ~21G of non-work* (archive/ 15G
                                 #   incl. this round's 1.5G record layer, input_files*
                                 #   6.9G, bee/ 2.2G) + ~54G of KEEP, of which
                                 #   work-mcp2k-grp0825 alone is 16G;
                                 # 72G after the 2026-08-23 prod0823 campaign
                                 #   (+15G of PR product for 3067 events);
                                 # 57G after the 2026-08-23 minimal-state round
                                 #   (203G before it); the floor is ~18G of
                                 #   non-work* (archive/ 11G incl. this round's
                                 #   2.7G record layer, input_files* 6.9G, bee/
                                 #   1.8G) + 38G of KEEP;
                                 # 54G after PASS 2 (71G before it, i.e. the
                                 #   campaign's own +17G came back out);
                                 # 54G after the 2026-08-19 PASS 1 (149G before
                                 #   it); 52G after the 2026-08-17 round (164G before
                                 #   it; 23G after the 2026-08-16 round +
                                 #   follow-up, 158G before it; 20G after
                                 #   2026-08-13, 74G before it; 23G after
                                 #   2026-08-11, 103G before it)

# the 2026-08-29 round: eleven closed doc families, the pi0 epoch stays.
# EDIT scripts/retire/PROTECTED.txt BY HAND FIRST -- ASSERT 7 trips otherwise.
python3 scripts/retire/verify_group_dupes_20260829.py   # 188/188, 1231656 members
python3 scripts/retire/plan_20260829.py                 # 120-name KEEP + 14 asserts
RETIRE_JOBS=12 python3 scripts/retire/archive_records_20260829.py  # integrity PASS 432/432
./scripts/retire/retire_20260829.sh A                   # dry run of the removal list
RETIRE_REPLAN=1 python3 scripts/retire/plan_20260829.py # re-stamp planned_at (interlock 6)
CONFIRM=yes ./scripts/retire/retire_20260829.sh A       # the deletion
cat scripts/retire/state-20260829/removed.tsv           # what was ACTUALLY removed
# verify AFTER, not only before: survivors must equal KEEP exactly, and every
# live manifest must still resolve on disk (the pi0 one is 50/50).

# the 2026-08-23 minimal-state retirement (see that section below):
# EDIT scripts/retire/PROTECTED.txt BY HAND FIRST -- ASSERT 7 trips otherwise,
# which is the point of it.
python3 scripts/retire/plan_20260823.py             # 38-name KEEP + 10 asserts (10 is new)
RETIRE_JOBS=16 python3 scripts/retire/archive_records_20260823.py  # integrity PASS 380/380
./scripts/retire/retire_20260823.sh A               # dry run of the removal list
CONFIRM=yes ./scripts/retire/retire_20260823.sh A   # the deletion
cat scripts/retire/state-20260823/removed.tsv       # what was ACTUALLY removed

# the 2026-08-20 pr/97 crash-sweep retirement (see that section below):
python3 scripts/retire/archive_records_20260820_pr97.py  # integrity PASS 484/484
rm -rf work-pr97*                                         # what was ACTUALLY removed (all of it)

# the 2026-08-19 retirement round, PASS 1 (see that section below):
python3 scripts/retire/plan_20260819.py            # explicit 51-name KEEP + 9 asserts
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260819.py  # integrity PASS 311/311
scripts/retire/retire_20260819.sh A                # dry run of the removal list
cat scripts/retire/state-20260819/removed.tsv      # what was ACTUALLY removed
# NO thin_dlruns this round -- dl_vtx_training already holds 0 *.pth (67 M)

# the 2026-08-19 retirement round, PASS 2 -- releases what prod0819 supersedes:
python3 scripts/retire/plan_20260819b.py           # 36-name KEEP, assert 9 also checks the new arms
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260819b.py
scripts/retire/retire_20260819b.sh A               # dry run
cat scripts/retire/state-20260819b/removed.tsv

# the 2026-08-17 retirement round (see that section below):
python3 scripts/retire/plan_20260817.py            # explicit 30-name KEEP + 8 asserts
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260817.py  # integrity PASS 148/148
scripts/retire/retire_20260817.sh A                # dry run of the removal list
python3 scripts/retire/thin_dlruns_20260817.py      # dl_vtx_training/runs *.pth sweep, dry run
cat scripts/retire/state-20260817/removed.tsv       # work* sweep, what was ACTUALLY removed
cat scripts/retire/state-20260817/dlruns-removed.tsv  # dl_vtx_training *.pth, what went

# the 2026-08-16 retirement round + same-day follow-up (see that section below):
python3 scripts/retire/plan_20260816.py           # explicit 27-name KEEP + 7 asserts
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260816.py  # integrity PASS 189/189
scripts/retire/retire_20260816.sh A               # dry run of the removal list
python3 scripts/retire/thin_dlruns_20260816.py    # dl_vtx_training/runs *.pth sweep, dry run
python3 scripts/retire/preserve_and_drop_campaigns_20260816.py  # 3 old archives, dry run
python3 scripts/retire/followup2_20260816.py      # same-day "latest+input only" trim, dry run
cat scripts/retire/state-20260816/removed.tsv          # work* sweep, what was ACTUALLY removed
cat scripts/retire/state-20260816/dlruns-removed.tsv    # dl_vtx_training *.pth, what went
cat scripts/retire/state-20260816/followup2-removed.tsv # follow-up trim, what went

# the 2026-08-13 retirement round (see that section below):
python3 scripts/retire/plan_20260813.py           # explicit 13-name KEEP + 6 asserts
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260813.py  # integrity PASS 388/388
scripts/retire/retire_20260813.sh A               # dry run of the removal list
cat scripts/retire/state-20260813/removed.tsv     # what was ACTUALLY removed
# NO Phase 4 this round -- the five -cb0805 hubs are the prod0813 campaign's INPUT

# the 2026-08-11 retirement round (see that section below):
python3 scripts/retire/plan_20260811.py           # explicit 18-name KEEP + 6 asserts
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260811.py  # integrity PASS 454/454
scripts/retire/retire_20260811.sh A               # dry run of the removal list
python3 scripts/retire/thin_hubs_20260811.py      # Phase 4: hub-internal thinning, dry run
cat scripts/retire/state-20260811/removed.tsv     # what was ACTUALLY removed
diff <(awk -F'\t' 'NR>1{print $1"\t"$2}' docs/pr/nuecc48-prod0811.index.txt) \
     <(awk -F'\t' 'NR>1{print $1"\t"$2}' docs/pr/nuecc48-cb0805.index.txt)  # bee_idx alignment proof

# the 2026-08-05 retirement round (see that section below):
python3 scripts/retire/plan_20260805.py       # 2 tier lists + 7 safety asserts
python3 scripts/retire/lightcheck_20260805.py # light/SP coverage proof (BLOCKING)
RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260805.py
scripts/retire/retire_20260805.sh A,D         # dry run of the removal list
cat scripts/retire/state-20260805/removed.tsv # what was ACTUALLY removed (new this round)
cat scripts/README.md            # where every non-interface script now lives
ls archive/*/ -d                 # 3 campaign archives + records/, 79 dirs
find . -xtype l | wc -l          # 0 -- MUST stay 0, see "the symlink hazard" below.
                                 #   MEASURE IT BEFORE A ROUND, NOT ONLY AFTER: it was
                                 #   284 going into 2026-08-03 and nobody had noticed.
python3 relink_tags.py           # dry-run repair after any move

# the 2026-08-03 retirement round (see that section below):
python3 scripts/retire/plan_20260803.py       # 3 tier lists + 4 safety asserts
python3 scripts/retire/lightcheck_20260803.py # light/SP coverage proof (BLOCKING)
python3 scripts/retire/archive_records_20260803.py  # archive/records/pr23-25-era-20260803/
scripts/retire/retire_20260803.sh V,1,2       # dry run of the removal list

# the 2026-08-02 retirement round (see that section below):
scripts/retire/materialize_20260802.sh        # pr/22 exhibit chain self-contained (dry run)
python3 scripts/retire/plan_20260802.py       # removal set + footprint + dangling-link dry run
python3 scripts/retire/lightcheck_20260802.py # SP+light coverage proof / exceptions
python3 scripts/retire/archive_records_20260802.py  # archive/records/pr-era-20260802/ (additive)
scripts/retire/retire_20260802.sh 1           # dry run of the removal list

# the 2026-07-30 retirement round (see that section below):
python3 scripts/retire/inventory.py       # size / symlink-dep / citation inventory
python3 scripts/retire/plan.py            # removal set + dangling-link dry run
python3 scripts/retire/archive_records.py # write archive/records/  (additive)
scripts/retire/retire_20260730.sh 1,2     # dry run of the removal list
```

Every tagged output dir is one arm of one A/B or one hand scan, produced by
`run_ql_evt.sh` / `run_pr_evt.sh` / `run_nusel_evt.sh -t <tag>` over one of four
event manifests:

| manifest prefix | what it is |
|---|---|
| `work-mcp10-<tag>` | the 10/30-event hand-scan set (imaging from `work-mcp10`) |
| `work-mcp1000-<tag>` | 30 events drawn from the 1000-event MC set (imaging from `work-mcp1000`) |
| `work-mcp1000b-<tag>` | a second 30-event draw from the same 1000-event set |
| `work-mcp1kall-<tag>` | **all 1000** events of that set, not a draw (doc 59; imaging from `work-mcp1000`) |
| `work-mcsim-<tag>` | the MC-truth sim set (truth dQ/dx, delta rays) |
| `work-nuecc48-<tag>` | the 48-event Lynn nueCC data candidate set (`samples/lynn-nuecc-rse.csv`; input `input_files_reco1/extracted-2025fall-48evt-fsprod`; imaging in the shared `work/`) |
| `work-vf<sample>-<tag>` | a **valfast** PR out-root over the 629-event `nu_evaluated=1` subset (`valfast/README.md`; sample ∈ mcp1k/nuecc48/r1qlmc/r2mc). TRANSIENT by contract — delete after the gate report. `-full` arms also create nusel roots `work-mcp1kall-vf<tag>`, `work-nuecc48-vf<tag>`, `work-r1qlmc-vf<tag>`, `work-r2mc-vf<tag>` |

**These arms are not reproducible.** A tag names a *config*, not a build. The
binary has moved many commits since most of them were written, and the SBND PR
chain is ASLR-non-deterministic on top of that. Re-running `-t <tag>` today
produces a *different* arm, so retiring a directory permanently retires the
ability to re-check the doc table it backs — the doc's stated PASS becomes the
only surviving record. That is why the classification below is by **who names
the directory**, not by age or size.

## The symlink hazard — read before moving anything

A tag dir does **not** hold a private copy of every event. Any stage the run did
not redo is an **absolute symlink** into an earlier tag's dir, often chained two
deep:

```
work-mcp10-dq48v3/ql_evt284349
    -> /nfs/.../sbnd_xin/work-mcp10-fvxy/ql_evt284349
    -> /nfs/.../sbnd_xin/work-mcp10-mainreal/ql_evt284349
```

So the tags form a dependency graph and **moving a tag breaks every dependent**.
Archiving the doc-29..49 tags below broke 1536 links. It failed silently in the
worst way: `scripts/analysis/stm/stm_fv_census.py` reported `0 "contained" clusters` instead of 147,
because a missing pctree is a `continue`, not an error. `relink_tags.py`
rewrites broken links to wherever the tag now lives; run it after ANY move and
confirm `find . -xtype l | wc -l` is 0.

Verification that the move was faithful: `python3 scripts/analysis/stm/stm_fv_census.py` after the
repair reproduces doc 49 §4 line for line (147 contained / 96 outside / 65 %,
median 2.88, p90 3.54, max 3.77, walls 23/61/4/8, agree 96/96), and
`scripts/analysis/stm/stmon_stats.py` reproduces 30 events / 36 fitted clusters / 18561 fit points.

## RETIREMENT ROUND 2026-09-01c (doc 91 sec 13) — the superseded control layer, 59 → 47 work dirs

Follows the sec-12 sentinel re-baseline directly. Released `work-sent130neg*` (6,
the negative controls at the 2026-08-29 operating point, now bracketing
thresholds nobody uses) and `work-pr125r1-flipK5*` (6, the "worked failing case"
for 137238, whose assertion direction flipped in the re-baseline). 12 dirs /
1 GiB, integrity 12/12, refused=0.

NOT released, correcting an over-promise in sec 7.4: `work-pr134-f086-*` (4) and
`work-pr130r1-probe*` (6) are pinned by LIVE display manifests ASSERT 11
enforces. The "~36 dirs" estimate was wrong; 47 is the honest figure.

New guard: each re-baselined sentinel must keep a NAMED surviving control in
which it still FAILS. Its first formulation ("some arm makes it fail") stayed
clean with every control deleted — old-operating-point arms fail the new
thresholds too, which is drift detection, not knob detection. Second time this
session a guard's first formulation was too weak and its own control caught it.

## RETIREMENT ROUND 2026-09-01b (doc 91) — count-driven: 101 → 52 work dirs, 65.8G → 58.6G

Full write-up: `docs/91_work-dir-minimisation.md`. The metric was **directory
count**, not bytes — the owner's complaint was legibility, not disk. 7.08 GiB
freed is a side effect.

**Released, 49 dirs.** doc 90's 9 peer arms (owner released them by name); 19
doc-87 arms (12 gate arms whose §6.1/§1.4 claims the doc-89 successor gate
re-established at 3067 events instead of 482, plus the 7-arm `SBND_PR_CALIB`
matrix, 21 MB — the worst count-per-byte in the tree); the r1qlmc/r2mc sim
chain in full, 10 dirs; `work-sent130-{mcp1k,mcp2k}`; `pr117r1-onK1-*` and
`em114c-prodnow-*`, 6; and 4 that were not really arms.

**Kept, 52.** Production `prod0901b` ×4 and its `grp0825` input ×4; the label
backing (`vtx105-base` ×4 for 878 label files, `em114`/`em114c` ×6 for 251,
`pr130r1-probe*` ×6); `pr134-f086` ×4 and `pr125r1-flipK5*` ×6 and
`sent130neg*` ×6 — all three held by §7 below; doc 87's remaining 9; and 3
record dirs.

**Three protections did not survive checking** (doc 91 §2): the old citation
census counted previous retire *planners* as consumers, so an arm was protected
because it had been protected; it was name-exact, so it scored `docs=0` for all
28 doc-87 arms, which cite themselves as templates; and two "hardcoded default
arm" protections were docstring **usage lines**, not argparse defaults.

**Two dirs were not arms.** `work-nuecc48-prsmoke2` held 3 tracked runner
scripts (→ `scripts/legacy/`) and its one consumer already pointed at a
subdirectory that no longer existed. `work-stmcamp-d66new` held the tree's ONLY
nusel label store (→ `./nusel_labels/d66flip/`, 22 tracked files, `git mv`) and
its comparison partner had been retired rounds earlier.

**OWNER VERDICT 2026-09-01, after scanning the production Bee set:** *"The scan
of the 6 events are good for the production batch."* So the six FAILs are a
STALE SENTINEL REGISTRY, not a physics regression — the operating point moved
under the thresholds (0.86 EM scale, doc 77 r3/r4's 17 retired TLAs, the master
merge), exactly the RE-BASELINE WARNING `pr127_sentinels.py`'s own header
carries. **Top next action: re-baseline the suite against `work-*-prod0901b`**;
until then it reports 6 FAIL on a good batch and will be ignored, which
re-creates the doc pr/127 exposure. Once re-baselined, the 16 witness arms
(`pr134-f086-*`, `pr130r1-probe*`, `pr125r1-flipK5*`) become releasable —
52 → ~36. Retire interlock 8 by re-baselining, never by deleting the evidence.

**The finding as measured, before the scan closed it.**
`./scripts/pr127_sentinels.py --arms 'work-*-prod0901b'` is **27 PASS, 6 FAIL**.
Five are regressions with a surviving witness arm; 393505 is red everywhere
(a 0.1 MeV Enu miss, i.e. drift). For 406125 the knob is still ON and the C++
log line still exists — the fix simply no longer fires, which is the doc pr/127
failure mode recurring. **137238 and 292643 have exactly ONE passing arm each**
(`pr130r1-probe98-nuecc48` and `pr134-f086-mcp1k`), so those two arms are single
points of failure for an open regression.

**Methodological trap worth remembering:** `pr127_sentinels.py:find_arm()`
evaluates each event in the FIRST arm (sorted glob order) that holds it. A
combined run over all non-production arms reports all six FAIL; per-arm
evaluation finds five passing somewhere. A guard built on the combined run
would have released the witness arms.

**New machinery.** `scripts/retire/sentinel_guard_20260901b.py`, one
implementation shared by plan ASSERT 15+16 and driver interlock 8. Interlock 7
degenerates this round (no production released), so interlock 8 was proven able
to FAIL before being trusted: drop `pr134-f086-*` → refuses on 292643; drop
`pr130r1-probe-*` → refuses on 137238. Also verified idempotent across the
deletion boundary, so it cannot trip on a re-run of its own successful round.

## RETIREMENT ROUND 2026-09-01 (doc 89) — the closed campaigns released and production rebased, 150G → 66G

**218 arms, 86.13 GiB removed; 98 kept (50.44 GiB).**
`work*` dirs 306 → 101. Full write-up:
`docs/89_cleanup-and-production-rebase.md`.

The owner's premise — *"we have been testing the results with minimal outputs"* —
was **measured and does not hold**: every production arm is maximal-output
(`pr142_arms.sh` sets `PR_EXTRA_STAGES=pr_display`, which *adds* the calib
dump), and the only minimal-mode arms in the tree are doc 87's own 67-event
`work-87knob-{min,sup}-*`. Nothing had been dropped, so there was nothing to
save back. What *was* wrong: `prod0901` predated the `save_in_scope` flip by 8 h
and so carried no `T_cluster` tree. The owner chose to re-run all 3067 events at
`ref/prod-2026-09-01b` (`work-*-prod0901b`) and gate the new arm against the old
before releasing it — the first end-to-end check, at full sample scale, of the
five-link chain doc 77 r3 → doc 77 r4 → master merge → doc 87 knobs →
`save_in_scope`, each previously gated only on 308 events.

Released: the CLOSED pr/136, pr/138-142 campaigns (186 arms) and doc 77 r3/r4
(20), plus `work-*-prod0830` (superseded twice), `work-*-empre0901` (doc pr/142
COMPLETE, tables in `products/empre0901/`) and `work-*-prod0901` (on the
successor gate and nothing else).

**Refused, deliberately:** doc 87's 28 gate arms (4.9 G). Doc 87 shipped the
same day and they are the acceptance evidence for a knob that moved the
production operating point; the successor gate is a *different* comparison.
Their release condition is now written into `PROTECTED.txt`. Same shape as the
08-31 round's `prod0825` refusal.

### Six things the guards caught
1. The fork **dropped the `KEEP_PREFIX` loop** — `work-87*`, `work-sent130*` and
   `work-pr134-f086-*` (40 arms, 4.9 G, incl. the sentinel negative controls)
   silently entered the removal set. ASSERT 7 and ASSERT 11 both refused, and
   the dry run showed 258 dirs where 218 was expected.
2. `em_labels` had drifted **298 → 540**; ASSERT 6b refused. Repaired additively
   (0 archive-only files, 0 content differences) and `git add -f`'d.
3. Interlock 2 refused on a **substring**: `work-mcp2k-prod0901` ⊂
   `…-prod0901b`. Safe direction; recorded so nobody "fixes" it carelessly.
4. `verify_group_dupes` **could not name a production arm's sample** — it only
   handled the `-<sample>` suffix form, not `work-<sample>-prod0830`. First
   round with a group-mode production arm in the removal set. Once fixed:
   **1259176/1259176 members across 193/193 archives** proven duplicates of a
   surviving grp0825 root, which is what lets the `groupin` class be dropped.
5. `zstd --long=31` wrote frames needing a 2 GB window to **decode** — caught by
   the recompression's own verification, not by inspection.
6. The bare `work/` dir matches `d.startswith('work')` and holds
   `work/nusel_labels/` (M13). Now named in KEEP, not rescued by a safety net.

### Archive record layer re-encoded
`archive/records` 16500MB → 6848MB by re-encoding the
record tarballs gzip → `zstd -19`, each verified member-for-member on
`(name, size, sha256)` before its `.gz` was removed. Two already-compressed
imaging bases and everything under 1 MB stay `.gz`.

## RETIREMENT ROUND 2026-08-29 — eleven closed doc families; the pi0 epoch stays, 152G → 75G

**432 arms, 81 GiB removed.** `work*` dirs 552 → 120. Record layer 10.73 GiB raw
→ **1.43 GiB gz** in `archive/records/em-pr-era-20260829/`. Owner scope, given
directly: *"the sbnd_xin directory now grow to 152 G, we should plan for a clean
up round again before going to the next step. We can keep the latest PR
results. … our next major move is to improve the pi0 reconstruction. We need to
use the hand scan results for pi0 to do this. … we also do not want to delete
the files related to the other running session."* Asked about the one
discretionary block — the doc-84 long-muon/MCS product layer — the owner chose
**"Release all three"** (`work-d84r3-cens-{mcp1k,mcp2k}` 14.2 G +
`work-mcp1k-mcs80on` 3.0 G).

Released: **pr/117, pr/118, pr/119, pr/120, pr/121, pr/123, pr/124, pr/125,
pr/127, pr/128** (all SHIPPED), **doc 84 rounds 1-4** + **doc 80's MCS arms**,
and **doc 114's** display arms. Kept: the doc 81 production pair, the vtx105
label epoch, the two SIM samples, **the pi0 epoch** and **the whole open pr/130
prefix**.

### Three things this round found rather than assumed

**1. `em_labels/` — the pi0 hand-scan record — was completely unprotected.**
249 label JSONs (2.0 MB): the 141-set, the 98-set and the pi0 pairings, i.e. the
literal input to the owner's stated next move. `git ls-files` returned **zero**
for it — the repo `.gitignore` has `*.json` at line 2, and
`overclustering_labels/`'s 230 files are tracked only because an earlier round
ran `git add -f` (M9). Nobody had done that for `em_labels`, and there was no
`archive/records/labels/` copy either. So the labels were one `rm -rf` from
unrecoverable while every arm around them was being carefully preserved. Both
halves are closed now and **ASSERT 6b** checks them on every future round. No
byte of `em_labels` is retired by this round.

**2. `HEAVY` had a hole, and the 08-25 census that "proved" it did not is a
lesson worth keeping.** That round justified reusing `HEAVY` unchanged with a
census of its 66 arms: *"ZERO unclassified file above 5 MiB, so nothing heavy
can slip into the record tar."* That was **true of its removal set and false of
this one** — none of its arms was group-mode and doc 84 round 3's census arms
are. This round's census found **242** unclassified files above 5 MiB, all
`.groups/g<N>.tar.gz`: 188 files, **4.96 GiB** of group *input* archives
(bundles of Q/L pctrees fed to a group-mode run). Left unclassified they would
have tripled the record layer to 16.06 GiB for nothing. **The durable lesson:
a census is evidence about the set it ran on, never a property of the tool.**
Dropped only after proof, not argument — `verify_group_dupes_20260829.py`
checked all 188 member by member against the surviving `grp0825` Q/L roots:
**1231656/1231656 byte-identical** (`state-20260829/group-dupes.tsv`).

**3. Two kept arms record no provenance at all.**
`work-{ncpi0,nuecc48}-prod0825` have neither the `group provenance: ql_root=`
line (their `.groups/g*-build.log` predate it; `mcp1k`'s and `mcp2k`'s have it)
nor a surviving `g*.tar.gz` for the byte-identity fallback. Pre-existing, not
caused by this round. ASSERT 8 reports them **UNVERIFIED** rather than FAIL —
but only because the round-level fact is *checked*: the removal set contains
**0 Q/L roots and 0 imaging roots**, so no kept arm's input can be deleted,
verified or not. With any root in the removal set, unverifiable stays a hard
FAIL.

### The pi0 carve-out — the load-bearing part

`work-pr124r1` (39 arms) and `work-pr125r1` (84 arms) were the two fattest sweep
candidates and the pi0 inputs sit **inside** them. Ten arms out of 123 were
carved out and named individually in KEEP:

| manifest | arms kept | rows |
|---|---|---|
| `em_display/pr126-pi0-manifest.tsv` | `work-pr124r1-onA98-*`, `-onA141v2-*` | 50 hand-paired π⁰ |
| `em_display/em117-125flipchk98-manifest.tsv` | `work-pr125r1-flipchk98-*` | 98 |
| `em_display/em114c-125flipchk141-manifest.tsv` | `work-pr125r1-flipchk141-*` | 141 |

The tempting alternative — sweep both families, re-run a fresh arm at current
HEAD — was **considered and rejected**: today's HEAD is a different operating
point, so doc pr/126's `kine_shower_fudge_factor` 0.80 → **0.84** PEAK fit would
stop being re-checkable the moment those dumps went. A fresh arm is *additive*
work for the pi0 round, never a substitute for the dumps the fit was made on.
Verified **after** deletion, not just before: all 12 live manifests resolve
on disk, π⁰ **50/50**.

### The concurrent writer — interlock 2 refined, interlock 6 added

First round ever to run against a tree with **another session writing to it**
(doc pr/130, a live 239-event knob-off gate). Every prior round's interlock 2
refused on *any* live sbnd_xin `wire-cell` process (M5). Here that would not
have made the round safer — it would have made it impossible, and the
predictable next step is `ALLOW_LIVE_JOBS=yes`, which disarms the interlock
completely. So:

- **interlock 2 is narrowed, not bypassed**: it refuses only if a live process
  names a dir in the **removal** set (the shape interlock 1 always used for
  Bokeh viewers). `ALLOW_LIVE_JOBS` is no longer honoured — there is nothing
  left for it to unlock that would be safe.
- **interlock 6 is new**: plan-time evidence expires, so the live-process and
  mtime checks are **re-derived immediately before the first `rm`**. The mtime
  half is the stronger one — a writer can exit between the two checks, but the
  mtime it left cannot un-happen.
- **A late-created arm cannot be swept by construction**: the loop iterates the
  *tier list*, not the directory. `work-pr130r1-gs1on-*` and
  `work-pr130r1-g1off141-*` were created between this round's first census and
  its plan, and were never at risk.

The peer session was asked directly and answered with a grep-verified
dependency list, encoded as **ASSERT 13** (31 arms) rather than trusted as
prose. Four of its names were in the planned sweep and moved to KEEP:
`work-em114c-prodnow-{mcp1k,mcp2k}`, `work-pr117r1-onK1-mcp1k`,
`work-pr125r1-flipK5*` (the sentinel registry's negative control) and
`work-pr128r1-on{98,141}-*` (the gate label doc pr/130 item 1 cites).
**Its fifth name, `work-pr127r1-flipS{98,141}-*`, does not exist on disk** —
`scripts/pr127_sentinels.py:30`'s docstring reference was already stale before
today. Recorded, not silently repaired; the peer owns that file.

### Stated costs

- **30 closed-round `em_display/*manifest*.tsv` stop resolving** — pr/117
  K-arms, pr/118 dbg, pr/119 dbgA, pr/120 on2/dbgon, pr/123 on1/dbgA2, pr/124
  dbgv2/onC/flipchk98, pr/125 dbg/onM, and `em114c-114cnow`. Every verdict is a
  table in its own doc. The 12 that survive are exactly the ones the pi0 round
  and the peer's scorers read.
- **doc 84's whole long-muon/MCS product layer** (23 G + 3.8 G). Deferred item 1
  (MCS absolute scale vs truth) is unaffected in practice — it needs a
  truth-level numu sample that does not exist here.
- **pr/121's family goes entirely** (34 arms, 6.0 G): zero script literals, zero
  surviving manifests, 305 doc mentions — all narrative.
- 12 script literals ACKed in `ACK_BROKEN_REFS` (pr/118-120 census defaults).

### FLAG for the next round, not acted on here

`work-<s>-prod0825` is now **six flips behind production** — pr/123 pass4,
pr/124 gap-band, pr/125 pass3+samevtx, pr/127 K5+sccc, pr/128 PF-kine and
pr/129 pointing all landed after it. It is kept because it is the named
production baseline and `grp0825` is the campaign input for any re-run. A fresh
full-coverage campaign at today's HEAD would supersede it — that is a decision
for the next round, and the precedent for making it is the 08-23 round.

## RETIREMENT ROUND 2026-08-25b — the stage-A reference side and the pre-flip PR baseline, 144G → 108G

**12 arms, 39 GiB removed, ~36 G net.** `work*` dirs 38 → 26. Full write-up:
`docs/81_group-mode-production.md` §11. Owner scope, given directly: *"I assume
we can safely retire [`work-img-{4 samples}`, `work-*-ql0819`,
`work-*-prod0823`], and recover the disk"*.

| released | why | frozen as |
|---|---|---|
| `work-img-{nuecc48,ncpi0,mcp1k,mcp2k}` | doc 81 §7: byte-identical to the imaging half of `work-<s>-grp0825` (24536/24536) | `state-20260825b/hashes/stagea-<s>.tsv` |
| `work-{nuecc48,ncpi0,mcp1k,mcp2k}-ql0819` | the Q/L half of that same gate | same file |
| `work-{nuecc48,ncpi0,mcp1k,mcp2k}-prod0823` | PRE-flip (doc 81 §4), superseded by `prod0825` | `state-20260825b/hashes/work-<s>-prod0823.tsv` |

**NOT released:** `work-img-{r1qlmc,r2mc}`. No `grp0825` arm exists for either
sim sample, so these are the only copy, not duplicates.

### The substitution rule — read this before re-running any older repro block

Every repro block in docs 71/74/76/77/78/79, pr/102 and pr/108, and the five
closed-round arm scripts (`pr107_arms.sh`, `pr108_testA.sh`,
`pr109_sbnd_arms.sh`, `pr112_arms.sh`, `pr112_dual_arms.sh`), still name the
retired arms. They were deliberately **not** repointed: a script that records
how a finished round was run should keep naming the arm that round actually
read. To re-run one:

* `work-<s>-ql0819` → **`work-<s>-grp0825`** (its `ql_evt<N>/` carries every
  product `ql0819`'s did except `calib-evt*.json` and `wct_ql_evt*.log`)
* `work-img-<s>` → **`work-<s>-grp0825`** (its `evt<N>/` layer, same layout)

The two *live* tools were repointed instead, and a new ASSERT 12 + interlock 5
verify it: `scripts/multi/repro_ql_nondet.sh` (doc 82's reproducer — its
command #10 passed `REF=work-mcp2k-ql0819` explicitly, which would have been
`exit 1`) and `scripts/multi/ql_legacy_gate.sh`.

### What the round proved before it deleted anything

`verify_frozen_stagea_20260825b.py` reproduces doc 81 §7's gate from the frozen
manifest against the surviving `grp0825` arms — **24536/24536**, run once before
the deletion and again after it, with both reference arms gone. `prod0823`'s
9201 rollups are frozen the same way, but that one is **insurance, not gate
preservation**: `prod0825` is at a different operating point, so no byte-identity
claim existed between them.

### Costs, stated rather than absorbed

* **docs pr/104–pr/111's A/B references against the pr/104 production epoch are
  now text-only** — `prod0823` was that epoch's last on-disk carrier.
* `work-{nuecc48,ncpi0}-ql0819`'s `ql_evt*/calib-evt*.json` (146 + 53 MB) are
  gone; `grp0825` does not carry them. Precedent: `thin_hubs_20260811.py`
  dropped mcp1k's and mcp2k's for the same reason in the 08-11 round.
* **NOT a cost, checked rather than assumed:** `sp-frames.tar.bz2` (2067 files)
  is preserved verbatim in `archive/records/stagea-refside-20260825b/` —
  `archive_records`' `HEAVY` list has no pattern matching it, so it lands in the
  record tar. That is also most of the 2.9 G archive, hence ~36 G net vs 39 GiB
  gross.

### Two catches worth carrying forward

* **`work-probe178410a` was about to be silently broken.** Its `evt178410/` was
  a symlink into `work-img-mcp2k` with four npz linking through it. ASSERT 4
  caught it; the link was replaced with the real bytes (`cp -rL`) before any
  deletion. 6.7 MB → 17 MB, now self-contained. It is PROTECTED precisely
  because a non-deterministic crash cannot be re-captured on demand.
* **A shared freeze tool would have failed silently.**
  `hash_manifest_20260825.py` matches `pr_evt(\d+)$`; stage-A arms are
  `evt<N>`/`ql_evt<N>`, so it would have written a header-only `.tsv` that
  passes `[ -s ]`. Hence a second tool, and hence interlock 4 / ASSERT 11 check
  **row counts** summing to 24536, never existence.

### `grp0825` is now load-bearing alone

`work-<s>-grp0825` is the **sole** on-disk carrier of stage A — imaging and Q/L
— for all four data samples. No second copy exists anywhere in the tree; there
is only the frozen manifest. A future round releasing a `grp0825` arm deletes
the product itself, not one copy of two. `PROTECTED.txt` says so at that entry.

## CAMPAIGN 2026-08-23 — `prod0823`, the full-coverage PR re-run the retirement round was gated on

**STATUS: COMPLETE.**  3067 events across all four data samples, **every one
`rc=0`**, bare production (no `SBND_*` overrides), `PR_EXTRA_STAGES=pr_display`,
toolkit `b5c9f43a`, `libWireCellClus.so` md5
`628444a7de4f9d224288b0ebf7c34e20`, `./build/clus/wcdoctest-clus` 228/228 /
2381 assertions.  Each arm reads its own sample's `-ql0819` Q/L root; **Q/L and
imaging are NOT regenerated** (M11 — `ql0819` IS the latest production Q/L).

```bash
cd sbnd_xin
# provenance BEFORE anything ran (M1): tree clean at b5c9f43a, and the lib
# (Aug 22 16:43) is NEWER than the newest source (TrackFitting.cxx, 16:42),
# so nothing needed rebuilding and no shared binary was touched.
for s in nuecc48 ncpi0 mcp1k mcp2k; do
  PR_JOBS=32 PR_EXTRA_STAGES=pr_display \
      ./run_pr_chain_batch.sh work-$s-ql0819 work-$s-prod0823 data
done
```

| sample | pr_evt | rc=0 | wall |
|---|---|---|---|
| nueCC48 | 48 | 48 | 2 min 24 s |
| NC π⁰ | 19 | 19 | 28 s |
| mcp1k | 1000 | 1000 | 22 min |
| mcp2k | 2000 | 2000 | 3 min + 20 min (see the interruption below) |

### It is a same-epoch continuation of the pr/104 arms, not a new epoch

Production last moved at the pr/104 flip (toolkit a07222e2 + c550541f), but
**three unknobbed commits landed after those arms were produced** — `a46b0ddb`,
`dd4d1373`, `56683366`, the doc pr/109 `T_proj_data` fix — so "a fresh run at
HEAD reproduces the pr/104 arms" was an open question, not an assumption.
Measured, `scripts/pr85_hash_gate.py`:

| gate | result |
|---|---|
| `work-pr104-on4-nuecc48` vs `work-nuecc48-prod0823` | **PASS 96/96** |
| `work-pr104-on4-ncpi0` vs `work-ncpi0-prod0823` | **PASS 38/38** |
| `work-pr104-on4-mcp1k` vs `work-mcp1k-prod0823` | **PASS 2000/2000** |
| `work-pr104-on4-mcp2k` vs `work-mcp2k-prod0823` (15-evt overlap) | **PASS 30/30** |
| `work-pr104-flipchk-{nuecc48,ncpi0}` vs `prod0823` | **PASS 96/96 + 38/38** |
| `nusel-{table,events}.tsv`, both small samples | identical |

**2164 archives byte-identical.**  So every A/B a doc took against
`work-pr104-on4-*` remains valid against these arms.

**The control that makes the PASS mean something (M1).**  A byte-identical
result is also exactly what a stale binary produces.  `tracking-pr.root`
**DIFFERS on 10/10** nueCC48 events checked — the pr/109 commits *are* in the
running binary, and their effect is confined to the `T_proj_data` ROOT dump.
Had that come back identical too, the gate would have been vacuous.

### The interruption, and what it says about this box

The first mcp2k attempt was **SIGKILLed at 01:10:55**, 3 min in — 136 events
started, 104 finished `rc=0`, 32 truncated (zero-byte `mabc-pr.zip`, deleted
before the resume).  Diagnosis, corrected once:

* It is **not** an OOM or a run failure: every completed event across all four
  samples exited `rc=0`, and memory was 25 G used of 251 with no swap.
* The first read was "a peer session cleared the box" — a concurrent session's
  `work-pr112-*` arms were created at 01:10, seconds before the kill.  **That
  is wrong.**  Those four `pr112` mcp1k arms *also* stopped writing at 01:10,
  at 195/437/439/443 of 1000 events.  Everything on the machine died within
  the same few seconds — a box-wide kill, not one session evicting another.
* **A `pr_evt<ID>/` directory is not evidence the event ran.**  The peer's arms
  look complete by directory count and are ~44 % populated.  Count `rc.txt`
  with `rc=0`, never `ls -d pr_evt*` — this round's own coverage table above
  is built that way.

The resume ran only the 1896 missing ids (`comm -23` of the `ql_evt` list
against the completed `rc=0` list) into the same arm — same binary, same
config, so the arm stays single-epoch.

### Cost of a harness bug, recorded so it is not repeated

The resume was supposed to start as soon as the box freed.  Its watcher used
`n=$(pgrep -c -f 'wire-cell ' || echo 0)`; `pgrep -c` prints `0` **and** exits
non-zero when nothing matches, so `n` became the two-line string `"0\n0"`,
`[ "$n" -eq 0 ]` errored every minute, the idle streak never advanced, and the
watcher sat until its 8-hour timeout.  The box was free from **01:28**; mcp2k
actually restarted at **09:20**.  ~8 h lost, no data affected.  *Use
`pgrep -f … | wc -l`, and make a watcher log the value it is testing.*

### What this changes for the next round

`work-pr104-{on4,flipchk}-*` (8 arms, 4.3 G) are now **redundant** — prod0823
covers every sample at least as widely and is byte-identical on every
overlapping event.  They are the obvious release candidate, deliberately NOT
taken here: the round that creates a baseline should not also destroy the
arms it was gated against.  `PROTECTED.txt` carries them with that note.

## RETIREMENT ROUND 2026-08-23 — back to a minimal state at the latest production, 203G → 57G

**STATUS: EXECUTED.** `python3 scripts/retire/plan_20260823.py` — universe
**418**, KEEP **38** / remove **380**, all **10** asserts PASS (9 carried + a
new ASSERT 10, see below).  `RETIRE_JOBS=16 python3
scripts/retire/archive_records_20260823.py` — integrity **PASS 380/380**,
16254.8 MiB raw → 2.7 G gz.  `CONFIRM=yes scripts/retire/retire_20260823.sh A`
— 380 dirs / 148 GiB removed, refused=0, **broken symlinks 0 before and
after**, no git-tracked file deleted, survivor census 38 == `len(KEEP)`,
manifest 380 rows.  `work-*` **418 → 38**, `sbnd_xin` **203G → 57G**,
`/nfs/data/1` free 824G → 970G.  wcp HEAD `feb839c`, toolkit HEAD `b5c9f43a`.

Labels: `scripts/retire/state-20260823/{plan.json,removed.tsv}`,
`scripts/retire/tierA_20260823.txt`,
`archive/records/prod0823-minimal-20260823/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`.

### Why this round exists

Owner, 2026-08-23: *"the sbnd_xin directory now goes to 203 G … what we want
is to go back to a minimal state with the latest production available
(QLMatching, and PR)."*  Since 08-20's 36 survivors / 54 G, docs pr/98–104
(four production flips) and pr/105–111 (vertex-strategy, dQ/dx, exclusion and
DL-vertex studies) regrew the tree to 418 `work-*` dirs / 188 G, plus 15 G
outside `work-*`.

### The one gap the owner's reading exposes, and the answer

"Latest production PR" is `work-pr104-on4-*` — doc pr/104 shipped SBND
production ON 2026-08-21 (`vertex_junction_snap` + `vjs_override_kink_snap`,
toolkit a07222e2 + cfg flip c550541f), and pr/105–106 then left production
UNCHANGED while pr/107–111 are studies.  But the pr/104 round validated mcp2k
on a **15-event subset**, so at the production epoch mcp2k has no
full-coverage PR product; only the released `work-mcp2k-prod0819` (2000 evts,
08-19, pre-flip) had one.  Coverage as it stood:

| arm family | nueCC48 | NCpi0 | mcp1k | mcp2k |
|---|---|---|---|---|
| `work-*-ql0819` (Q/L) | 48 | 19 | 1000 | 2000 |
| `work-pr104-on4-*` | 48 | 19 | 1000 | **15** |
| `work-pr104-flipchk-*` | 48 | 19 | 26 | 15 |
| `work-*-prod0819` (released) | 48 | 19 | 1000 | 2000 |
| `work-vtx105-base-*` | 47 | 19 | 407 | 581 |

Owner, asked directly before anything ran: *"we can drop this, and redo the
production for the samples, so we keep the latest PR production for all
samples."*  So the four `prod0819` **PR** arms are released and a fresh
full-coverage PR re-run at current HEAD replaces them — **the four `-ql0819`
Q/L roots are NOT released**, they are that re-run's input.  That makes this a
sweep *before* a campaign again, the 08-19 pass-1 shape, so ASSERT 9 (KEEP
closed FORWARD over the campaign input set) applies and is re-pointed at this
round's arms.

### KEEP — 38 names, 38.42 GiB, in seven groups

| group | n | what |
|---|---|---|
| campaign INPUT | 8 | six `work-img-*` hubs (19.2 G) + the two **SIM** `cb0805` Q/L hubs |
| latest production Q/L | 4 | `work-{nuecc48,ncpi0,mcp1k,mcp2k}-ql0819`, 48/19/1000/2000 |
| latest production PR | 8 | `work-pr104-on4-*` (the product) + `work-pr104-flipchk-*` (the shipped-cfg proof) |
| current vertex-label epoch | 4 | `work-vtx105-base-*` — 1756 `vertex_labels/vtxscan-vtx105-*` `source` entries resolve here |
| doc pr/111 live inputs | 4 | `work-vtx106-harv-{base,nofitx}-nuecc48` + `work-vtx106-cne-{on,off}-nuecc48` |
| the two SIM samples | 6 | `work-{r1qlmc,r2mc}-{prod0813,vfcbr3on}` + `work-vf{r1qlmc,r2mc}-cbr3on` |
| git-tracked / not reproducible | 4 | `work-tfix388-r9`, `work-stmcamp-d66new`, `work-nuecc48-prsmoke2`, `work-probe178410a` |

`work-pr104-flipchk-*` is kept for the reason `PROTECTED.txt` records twice
(`work-pr87-postflip-*`, `work-cbr3-bare2evt`): it is the only on-disk evidence
that the shipped post-flip jsonnet reproduces `-on4` with no env, and dropping
the bare-config arm turns that claim into text the same day.  **Both pr/104
families are superseded the moment the re-run lands with full coverage** —
release them in that follow-up pass, not before.

### ASSERT 10 (new) — every script literal into the removal set is acknowledged

Two prior rounds discovered *after* the fact that a script hardcoded an arm
they had just deleted (`vtx_rules/baselines.py:deployed_dump_path()`,
`scripts/analysis/pr57/oc56_truth.py:DEFAULT_ARMS`).  The standing safety net
is a citation check over `docs/`, which cannot see a path literal in a `.py`.
ASSERT 10 greps `scripts/`, `vtx_rules/`, `dl_vtx_training/` and the top-level
`*.py`/`*.sh` (1128 files) for every `work-*` literal and **refuses** if a
removal-set name is not in `ACK_BROKEN_REFS`.  It is not there to save the arm
— it is to make every broken reference a cost written down before the round,
never a surprise weeks later.  This round: **24 names acknowledged**, the
heaviest being `work-vtx100-base-mcp2k` (114 refs) and `-mcp1k` (50).

### What the citation-and-script checks did NOT catch, and what did

`work-vtx106-cne-{on,off}-nuecc48` are in **doc pr/111's own arm table**
(§2) — the OPEN round — but no script hardcodes them, so ASSERT 10 was blind
to them and the first plan listed them for removal.  They were caught by
reading the open doc's arm table by hand.  This is the 08-19 pass-2 lesson in
a new costume: *a dated rule protects yesterday*.  **Do this next round: read
the newest `docs/pr/*.md`'s arm table before trusting any automated check.**
(The `ncpi0` legs of the same pair are NOT in that table and were released.)

### Known cost, stated rather than silently absorbed

* **doc pr/95's single-epoch baseline is gone.**  Every pr/98–104 A/B that
  cites `work-*-prod0819` is text-only from here.  mcp2k has **no**
  2000-event PR product until the re-run lands.
* **`work-pr96gate-{mcp2k,nuedisp}`** — the mixed-binary equivalence proof for
  the mid-campaign relink (doc pr/95 §4b) — released with its subject.
* **The three DATA `cb0805` Q/L hubs are gone.**
  `scripts/analysis/pr48/backtoback_census.py`'s 445-dump census and
  `scripts/runners/run_pr_geom_arm_dl.sh`'s pctree pin stop resolving; doc
  pr/48's numbers survive as text.
* **The whole pr/102 family (45 dirs, 21.7 G)** including the eight arms
  `PROTECTED.txt` still marked "owner scan pending" on 08-20 — discharged:
  r2 shipped `len_admit=30` ON and production has flipped twice since.
* **The `vtx100` label epoch's dumps are gone** (the `vtx105` epoch is kept in
  its place, one epoch deep — same precedent as the 08-16 `prod0813` and 08-17
  `harv3` drops).  `vertex_labels/` JSON is self-contained and survives.
* **Every pr/98, pr/99, pr/101, pr/103, pr/107, pr/108, pr/109 arm** — all
  those rounds are closed and their gates are text in their docs.

### What was NOT touched

`dl_vtx_training` (67 M, still 0 `*.pth` — no `thin_dlruns` needed),
`vertex_labels/`, `overclustering_labels/`, `archive/` (the record layer,
M13), `input_files*/` (ASSERT 1's SP sources), `bee/` (backs uploaded doc
links).  Those are ~15 G and are the floor below which this tree does not go;
this round's own 2.7 G record layer takes `archive/` to 11 G.

### Gate labels for future re-checks

`scripts/retire/state-20260823/plan.json` (KEEP + KEEP_WHY + PR_PROVENANCE +
ACK_BROKEN_REFS + the full script-reference map),
`scripts/retire/state-20260823/removed.tsv` (380 rows, each with its archive
tarball name, size and pre-removal mtime),
`scripts/retire/tierA_20260823.txt`.

## RETIREMENT ROUND 2026-08-20 — the doc pr/97 gojsonnet-crash sweep, 484 arms, ~1.5 GiB

**STATUS: EXECUTED.** All 484 `work-pr97*` dirs from doc pr/97's investigation
(`97_address_dependent_pr_chain.md`, status "TWO DEFECTS FOUND, BOTH FIXED,
GATED") retired in one shot — a single closed, self-contained investigation,
not a multi-doc campaign sweep, so no KEEP/PROTECTED tier logic was needed:

* **Named nowhere else.** Checked before removal: absent from `PROTECTED.txt`,
  absent from every other section of this file, and no doc besides pr/97 itself
  cites a `work-pr97*` tag by name. No symlink anywhere in the tree (inside or
  outside the removal set) resolves into one of these dirs (`find . -xtype l`
  cross-check, 0 hits touching `work-pr97*`).
* **Every load-bearing number is already text in the doc, not a pointer to
  these dirs.** The crash-rate table (§5.5, 108→4/3.7% then the padding/gdb/
  precompile arms' 0-vs-2-in-48 tallies), both gdb backtraces (`work-pr97g-r7`,
  `-r32`, quoted verbatim), and every byte-identical gate PASS (§7: 96/96,
  38/38, plus the uBooNE 35/35) are already quoted in the doc as tables/text.
* **This round's removal set does include the doc's own gate arms**
  (`work-pr97gate-{nuecc48,ncpi0}`, `work-pr97L-{prgate,prod1}`,
  `work-pr97on-nuecc48b`) — per the standing rule above ("retiring a directory
  permanently retires the ability to re-check the doc table it backs"), the
  doc's stated PASS numbers for those arms are now the only surviving record;
  they cannot be regenerated identically (binary has moved, PR chain is
  ASLR-non-deterministic on top of that).
* Archiver: `scripts/retire/archive_records_20260820_pr97.py` (forked from
  `archive_records_20260819b.py`'s HEAVY classification, group/KEEP logic
  dropped as unneeded for a single-investigation sweep). Drops reproducible
  heavy blobs (`mabc-*.zip` 828.9 MiB, `pctree-*.tar.gz` 441.8 MiB,
  `opflash_apa*.tar.gz` 7.2 MiB, `tracking-pr.root` 57.4 MiB — 1.30 GiB total,
  all regeneratable from the repro block at the top of doc pr/97) and archives
  only the small record layer (logs, `.status`, compiled config — 218.5 MiB
  raw) as one integrity-checked `.tar.gz` per arm.
* **Integrity gate: PASS 484/484** (tar member count == manifest record-file
  count, every arm) — `archive/records/pr97-crash-sweep-20260820/sweep/`,
  30 MiB gzipped.
* No core files or unexamined crash logs existed in the set at removal time —
  the only two `.log.log` files carrying a live SIGSEGV (`work-pr97g-r7`,
  `-r32`) were already backtraced and quoted in the doc; nothing was lost that
  wasn't already captured as text.

`work*` dirs 520 → 36; disk unchanged to `du`'s rounding (54G before and
after — this set held ~1.5 GiB against a 54 GiB tree). Deletion executed by
the owner directly (`rm -rf work-pr97*`) after the archive integrity gate
passed.

## RETIREMENT ROUND 2026-08-19 — the pr/40+83+84+91-94 sweep, 149G → 54G (pass 1 of 2)

**STATUS: PASS 1 EXECUTED.** `python3 scripts/retire/plan_20260819.py` — KEEP
51 / remove 311, all **9** asserts PASS (8 carried + a new ASSERT 9, see
below). `RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260819.py` —
integrity **PASS 311/311**, 4762.7 MiB raw → 565 MB gz. `CONFIRM=yes
scripts/retire/retire_20260819.sh A` — 311 dirs / 94 GiB removed, refused=0,
**broken symlinks 0 before and after**, no git-tracked file deleted, survivor
census 51 == `len(KEEP)`, manifest 311 rows. `work-*` **362 → 51**, `sbnd_xin`
**149G → 54G**, `/nfs/data/1` free 880G → 975G. Started 22:23:54, finished
22:24:15 — 21 seconds. wcp HEAD `efed08b`, toolkit HEAD `fd6a116d`.

**No `thin_dlruns_20260819.py`.** `dl_vtx_training` holds **0 `*.pth`** and is
67 M — the 08-17 round already took it 18 G → 67 M. Nothing to thin. Do not
fork one unless `.pth` files reappear.

Pass 2 (`*_20260819b`) releases what the new `prod0819` baseline supersedes;
see its own section below once it runs. Full campaign account: **doc pr/95**.

### Why this round exists, and why it is different from every prior round

pr/40 rounds 7+9, pr/83 rounds 2-4, pr/84 rounds 2-3, pr/91 rounds 1-4, pr/92
rounds 1-2, pr/93 rounds 1-4 and pr/94 phases 1-6 regrew the tree from the
08-17 round's 30 survivors / 52 G to **362 dirs / 149 G in 54 hours**, and
production moved twice inside that window (pr/93 round-4 flip, then pr/94
Phase 6 at toolkit `fd6a116d`, four knobs ON).

**This is the first round that runs BEFORE a campaign rather than only after
one.** The owner's sequence was: clean the tree, *then* re-run Q/L + the full
PR chain for nueCC48 / NCpi0 / mcp1k / mcp2k at current production (doc pr/95,
tags `ql0819` → `prod0819`). Every prior round only ever had to prove KEEP was
closed **backward** — that a kept PR arm's Q/L input was also kept (ASSERT 8).
Here KEEP must also be closed **forward**, over the input set of a campaign
that has not run yet. That is ASSERT 9, new this round.

`docs/work-tags.md` was **again one campaign generation stale** going into the
round: its newest retirement section was 2026-08-17, with zero mentions
anywhere of `pr91`, `pr92`, `pr93`, `pr94`, `pr83r3/r4`, `pr84r2/r3`, `pr40r9`
or `-latestcheck`. Same trap the 08-17 round documented as its reusable
finding, two rounds running. KEEP was derived from **disk evidence** — live
`ls -1d work-*`, `git ls-files`, and grepping each retained arm's own log for
its `ql_evt` provenance — not from this file.

### ASSERT 9 (new) — KEEP is closed FORWARD over the campaign input set

The failure it catches is **silent, not loud**: `run_ql_batch.sh:51-53` writes
`rc=91 ... no-imaging` and **exits 0** when `$IMGBASE/evt<N>` is absent, so a
missing or thinned imaging hub degrades the arm to a short one instead of
erroring, and a downstream count gate then compares 900 events to 900.
ASSERT 9 requires, with counts:

```
work-img-nuecc48   48   work-img-mcp1k   1000   work-img-r1qlmc  10
work-img-ncpi0     19   work-img-mcp2k   2000   work-img-r2mc    13
input_files_reco1/staged-mcp2025c-1000evt      entry_event_map.tsv 1001 lines
input_files_reco1/staged-mcp2025c-2nd-2000evt  entry_event_map.tsv 2001 lines
input_files_reco1/extracted-2025fall-48evt-fsprod, extracted-ncpi0
```

All PASS. The pass-2 fork extends it to require the eight `ql0819`/`prod0819`
arms with their own event counts, so pass 2 cannot sweep the baseline it exists
to protect.

ASSERT 8 was **widened from 7 edges to 24** — the 7 inherited `cbr3`/valfast
edges plus 17 for the retained pr/94 r3 PR arms. All 24 re-derived from each
arm's own log and confirmed in KEEP. The four `work-pr94r3-ql*` arms are Q/L
**producers**, not PR arms, and are deliberately absent from the table:
`work-pr94r3-ql22disp` has no `wct_*` log at all, so including it would make
the provenance regex **fail** rather than skip.

### KEEP — 51 names, 39.21 GiB

- **Campaign input, 11** (22.3 GiB): the 6 `work-img-*` hubs + the 5
  `work-*-cb0805` Q/L hubs (still `run_valfast.sh`'s only PR-tail pins).
- **Git-tracked / not reproducible, 3**: `work-tfix388-r9`,
  `work-stmcamp-d66new`, `work-nuecc48-prsmoke2`. Verified this round: **zero**
  git-tracked files and **zero** label dirs anywhere in the 332 new dirs.
- **`PROTECTED.txt` active, 17**: the 4 `work-cbr3-*`, 5 `-vfcbr3on`, 5
  `vf*-cbr3on`, `work-{r1qlmc,r2mc}-prod0813`, `work-tfix388-r9`. All kept in
  pass 1 even though today's flip supersedes some — releasing them is pass 2's
  job, after the replacement exists.
- **doc pr/94 Phase 6 flip evidence, 21** (1.39 GiB): the
  `work-pr94r3*`/`r3b*` family. Kept in pass 1 as the only on-disk proof of a
  production flip that was hours old; **released in pass 2 at owner request**
  (see that section).

### Two findings recorded so the next round does not re-discover them

1. **`PRnnAUDIT knobs[...]` log lines cannot attribute pr/9x arm role.** They
   are round-30s-era instrumentation (PR30/31/32/33/36) and a full `diff` of
   the unique `knobs[...]` lines between `work-pr94r3-on-nuecc48` and
   `work-pr94r3-off-nuecc48` on the same event (137238) is **empty** — the
   pr/91-94 knobs emit no audit line at all. Any future assert that infers arm
   role from log knob state will silently pass on garbage. What the logs *do*
   give reliably is the provenance edge `reading file=<qlroot>/ql_evt<N>/...`,
   which is what ASSERT 8 uses.
2. **`work-cbr3-census-on` is no longer purely a Q/L hub.** It acquired six
   `pr_evt*` dirs on 2026-08-18 18:09 (`pr_evt{70084,279955,283713,316025,395148,405707}`).
   Its 3000 `ql_evt*` are pristine at 08-17 13:57, so doc 73 §12.9's 4/4
   member-hash claim still holds — but a "thin the hub to `ql_evt*` only" pass
   would eat them. Do not write one.

### The bokeh viewer pin, released

**`PROTECTED.txt`'s ":5017/:5018 LIVE on bokeh" justification was stale, and is
now released.** `pgrep -af 'bokeh|serve_pr_display'` returns nothing and
`ss -ltnp` shows nothing listening on 5013-5019 — so the ground recorded on
2026-08-13 had lapsed some time before this round with nobody noticing. Owner,
asked directly during the round: *"you can turn off display in 5017 5018"* —
there was nothing to turn off. Do not re-derive a protection from that line.

`work-{r1qlmc,r2mc}-prod0813` survive on their *other* stated ground, which
still holds: the only **full-coverage** PR product for either sim sample (10
and 13 `pr_evt` vs the `cbr3on` arms' `nu_evaluated` subset of 4 and 6),
neither sim sample is in the pr/95 campaign, and the pair costs **30 MB**. A
later round wanting them gone is now a one-line decision with no viewer to
check first.

### The dependency graph was a flat star, not a chain

Unlike the chained-symlink hazard this file warns about at the top, every one
of the 332 new dirs read one of just four Q/L roots —
`work-{mcp1k,ncpi0,nuecc48}-cb0805` or `work-cbr3-census-on` — all four in
KEEP. 23336 symlinks were walked by ASSERT 4 (hidden dirs included) and **0**
pointed into the removal set. That is why this round could remove 311 dirs in
21 seconds with zero repair work: `relink_tags.py` reported
`repaired=0 unresolved=0`.

### Known cost, stated rather than silently absorbed

- **Three cross-doc byte-identity anchors retire.** doc pr/91's knob-off gate
  is anchored on `work-pr84r3-dedup-*`; doc pr/93's on
  `work-pr92r2-bare-{ncpi0,nuecc48}`; doc pr/94 cites `work-pr83r4-m2kon` 4×.
  All three anchors are gone, so those PASSes become **text-only**. Accepted:
  all three rounds are closed with their verdicts in their docs, and the
  replacement anchor for everything going forward is `prod0819`.
- **147 of the 362 dirs (40 GiB) had no citation anywhere** in `docs/` or
  `scripts/`. That signal was trusted for pr/83 and pr/84 only — the pr/94
  arms were uncited *because the round closed two hours before the sweep*,
  which is exactly the failure mode `PROTECTED.txt:26-28` records ("ten of the
  seventeen arms listed here were zero-citation"). KEEP is the explicit dict,
  full stop; no citation-driven tier rule was used.
- The 62 pr/94 **intermediate** arms (`p2 p3 p4 f g h i j k m n n2 p5`,
  40.72 GiB) retire. They are superseded *within their own round* by the `r3`
  family, and doc pr/94's own §9.12/§9.13 gate tables name the `r3` arms as
  final. Note the letter generations are **not alphabetical in time**:
  chronological order is p2, p4, p3, f, g, h, i, p5, j, k, m, n, n2, r3, r3b.
- `work-*-latestcheck` (3 arms) and `work-prod0819-{mcp1k,ncpi0}` (2 arms, a
  4-event post-pr/93-flip spot check, cited once and never) retire. The name
  collision between `work-prod0819-*` (spot check, 08-19 05:11) and this
  campaign's `work-*-prod0819` arms is why the campaign puts the tag **last**.

### Gate labels for future re-checks

`scripts/retire/state-20260819/{plan.json,removed.tsv}`,
`scripts/retire/tierA_20260819.txt`,
`archive/records/pr40-94-era-20260819/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`
(311 arms across 9 groups: latestcheck-arms, pr40-family, pr83-family,
pr84-family, pr91-family, pr92-family, pr93-family, pr94-intermediate,
prod0819-spotcheck).

## RETIREMENT ROUND 2026-08-19 — PASS 2, release what `prod0819` supersedes, 71G → 54G

**STATUS: EXECUTED.** `python3 scripts/retire/plan_20260819b.py` — universe 67,
KEEP **36** / remove **31**, all 9 asserts PASS.
`RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260819b.py` — integrity
**PASS 31/31**, 1021.0 MiB raw → 137 MB gz.
`CONFIRM=yes scripts/retire/retire_20260819b.sh A` — 31 dirs / 17 GiB removed,
refused=0, **broken symlinks 0 before and after**, no git-tracked file deleted,
survivors 36 == `len(KEEP)`, manifest 31 rows. `work-*` **67 → 36**, `sbnd_xin`
**71G → 54G**, `/nfs/data/1` free 958G → 975G. Labels:
`scripts/retire/state-20260819b/{plan.json,removed.tsv}`,
`scripts/retire/tierA_20260819b.txt`,
`archive/records/prod0819-era-20260819b/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`.

**What was released, and what it cost.** The 21 `work-pr94r3*` arms (owner,
asked directly: retire all 21), the 4 `work-cbr3-*` production-reference arms,
and the 6 *data*-sample valfast arms (`work-{mcp1kall,ncpi0,nuecc48}-vfcbr3on`,
`work-vf{mcp1k,ncpi0,nuecc48}-cbr3on`). Dropping the two mcp2k `pr94r3` arms is
what unpinned `work-cbr3-census-on` (9.6 GiB, the largest pass-1 survivor), so
the owner's "retire all 21" was worth ~11 GiB, not the arms' own 1.4. Cost,
stated before running: doc pr/94's flip-equivalence gates (96/96+48/48,
16/16+8/8, 28/28+14/14) and doc 73 §12.9's bare-run 4/4 member-hash proof are
now **text-only**. Taken deliberately, because `prod0819` is the production
reference from here on — unlike the `work-pr87-postflip-*` loss at 08-16, which
happened by oversight.

`PROTECTED.txt` was edited **by hand first** — ASSERT 7 trips otherwise, which
is the point of it. Active names 17 → **15**: the released families moved to
RETIRED with cost notes, the eight `ql0819`/`prod0819` arms were added as real
tab-delimited lines, and the two `work-{r1qlmc,r2mc}-prod0813` MC arms had their
stale ":5017/:5018 LIVE" ground annotated as released (see the pass-1 section).

### The finding this pass exists to record: a dated sweep does not protect *this evening's* work

The first pass-2 plan listed **36** removals. Five were
`work-pr96-dbg{1,2,3}-mcp2k`, `work-pr96-fx1-mcp2k` and `work-pr96gate-disp` —
written **23:00–23:27 the same evening** by the *other* Claude session, the one
whose commit `f0e69780` relinked `libWireCellClus.so` at 23:04 mid-campaign
(doc pr/95 §4b). `docs/pr/96_uncovered-vertex-prongs.md` cites them and
`work-pr96-dbg1-mcp2k` holds exactly evts 70084 and 279955, the two events that
doc is about. **That round is open, with a residual unresolved.**

Every prior round's KEEP was built from "latest product per sample + inputs +
current-flip evidence", and every prior round's safety net was the citation
check. Neither catches this: the arms were minutes old and the citing doc was
written hours earlier by someone else. All five went into KEEP with the reason
in `plan_20260819b.py`; `work-pr96gate-disp` on ambiguity alone (evts
47036/47982/49657 at 23:27:50, between this session's own two `pr96gate` arms —
unprovable either way, so kept). Cost: **43 MB**.

**Do this next round, before `CONFIRM=yes`:**

```bash
# anything in the removal set touched in the last 6 hours is suspect
while read d; do
  find "$d" -type f -newermt '-6 hours' -printf '%T+ %p
' 2>/dev/null | sort | tail -1
done < scripts/retire/tierA_<date>.txt | sort | tail -20
git -C ../../../toolkit log --since='12 hours ago' --oneline     # whose work is live?
ls -t docs/pr/*.md | head -3                                     # whose doc is open?
```

A tier rule dated yesterday protects yesterday. Two sessions share this tree
(see "Two Claude sessions can share this tree"), and the newest arms are exactly
the ones no citation rule and no supersession rule can classify.

## RETIREMENT ROUND 2026-08-17 — the pr/88-90 + cathode-rescue sweep, 164G → 52G

**STATUS: EXECUTED.** `python3 scripts/retire/plan_20260817.py` — KEEP 30 /
remove 148, all **8** asserts PASS (7 carried unchanged + a new ASSERT 8, see
below). `RETIRE_JOBS=24 python3 scripts/retire/archive_records_20260817.py`
— integrity **PASS 148/148**. `CONFIRM=yes scripts/retire/retire_20260817.sh
A` — 148 dirs / 95 GiB removed, refused=0, broken symlinks 0 before-and-after
the round (see "the 08-17 broken-symlink defect" below), no git-tracked file
deleted, `work-*` **178 → 30**. `CONFIRM=yes python3
scripts/retire/thin_dlruns_20260817.py` — 648/648 `*.pth` removed, 17.36 GiB
freed, `dl_vtx_training` 18G → 67M. `sbnd_xin` **164G → 52G**, `/nfs/data/1`
free 838G → 949G. Full campaign account: docs **pr/88, pr/89, pr/90**, and
**doc 73** (the seven-knob cathode-rescue production flip, toolkit
`2d8c9e5a`) — this round is housekeeping, not a new investigation.

### Why this round exists

Doc pr/89 (DL-vertex round 4: topo term NET NEGATIVE live, swap-guard killed
`-36`, Arm B retrain CLOSED NEGATIVE), doc pr/90 (unbroken kink, rounds 1-4,
only the D4 `teb_bragg_veto_turn=30` scope shipped) and docs 72/73 (cathode
rescue rounds 2+3, **seven knobs flipped into SBND production the same day**
at toolkit `2d8c9e5a`) regrew the tree from the 08-16 round's 18 survivors /
23G to 178 `work-*` dirs / 164G in **one day**. `dl_vtx_training/runs`
regrew 26M → 18G on top of that — 648 `.pth` checkpoints, all from doc
pr/89's Arm B, created 2026-08-16 17:09–20:44.

**`docs/work-tags.md` was one whole campaign generation stale going into
this round** — zero mentions anywhere of `cb0816`, `harv3`, `mcp2k`, `pr89`,
`pr90`, `cbr2`, `cbr3`. A straight fork of `plan_20260816.py` would have
classified all of those — including what is now production — as sweepable.
This round's KEEP dict was derived from **disk evidence** (grepping
`wct_pr_evt*.log`/`wct_ql_evt*.log` for provenance, independently
re-verifying doc 73 §12.9's hash-match claim), not from the doc, and this
section closes the gap the doc had.

### KEEP — 30 names, 37.85 GiB, driven by two owner requirements

1. **DL-vertex training**: retire the unsuccessful arms (handled separately
   by `thin_dlruns_20260817.py` — `dl_vtx_training` is not a `work-*` dir).
2. **Keep the latest Q/L result for nueCC / NCpi0 / mcp1k (1000-evt data) /
   mcp2k (2000-evt data), and the PR result built on it; retire the rest.**
   Owner's explicit reading of "latest" (2026-08-17, asked directly): the
   **post-flip** arms from today's seven-knob production flip, not the
   pre-flip `cb0805`/`cb0816` + `harv3` family. `work-{mcp1k,nuecc48,ncpi0}
   -pr87ion3` — yesterday's "latest" — is explicitly superseded and released
   from `PROTECTED.txt` this round.

- **Infrastructure / input** (11 names, 22.3 GiB): `work-img-{mcp1k,mcp2k,
  nuecc48,ncpi0,r1qlmc,r2mc}` (imaging hubs; `work-img-mcp2k` is **new since
  08-16**, had no KEEP_WHY entry in any prior plan) + `work-{mcp1k,nuecc48,
  ncpi0,r1qlmc,r2mc}-cb0805` (the Q/L roots `run_valfast.sh` pins for
  PR-tail mode — its own `[ -d "$QL" ]` check refuses every sample without
  them, exactly how the 2026-08-05 round mechanically killed PR-tail mode
  before).
- **Git-tracked / not reproducible** (3 names, 6.5 MiB): `work-tfix388-r9`
  (doc pr/28 §15.9), `work-stmcamp-d66new` (22 git-tracked
  `nusel_labels/d66flip/*.json`, M13), `work-nuecc48-prsmoke2` (3 git-tracked
  runner scripts) — unchanged since 08-11.
- **PROTECTED, live on the bokeh viewers** (2 names, 28 MiB):
  `work-{r1qlmc,r2mc}-prod0813` — ports :5017/:5018. **Not** released this
  round (the owner released only the `pr87ion3` line).
- **Post-flip production, the "latest"** (14 names, 15.9 GiB):
  `work-cbr3-census-on` (9.5 GiB, Q/L over 3000 events — mcp1k 1000 + mcp2k
  2000 — all seven flip knobs ON; doc 73 §12.9 proves it *is* production: a
  **bare** `run_ql_batch.sh` with no envs reproduces its `mabc-all-apa.zip` +
  `pctree` member hashes **4/4 MATCH**) + `work-cbr3-census-pr-on` (the PR
  chain on the 40 behavior-changed events; **verified** reads
  `work-cbr3-census-on/ql_evt`) + `work-cbr3-bare2evt` + `-bare2evt-pr` (the
  **only on-disk evidence** the shipped jsonnet reproduces `census-on` — the
  same role `work-pr87-postflip-*` played at 08-16, and the same lesson:
  that arm was dropped the same day it was created and its claim became
  text-only) + `work-{mcp1kall,ncpi0,nuecc48,r1qlmc,r2mc}-vfcbr3on`
  (post-flip Q/L, valfast `-full` nusel roots with the tagger tail
  `census-on` lacks) + `work-vf{mcp1k,ncpi0,nuecc48,r1qlmc,r2mc}-cbr3on`
  (post-flip PR out-roots — **each individually verified** to read its
  matching `-vfcbr3on/ql_evt`, not inferred by naming convention).

Note: the valfast contract (`run_valfast.sh` header) declares
`work-vf*`/`work-*-vf<tag>` **transient — delete after the gate report**.
Keeping the `cbr3on` arms is a **deliberate exception**: they are the only
post-flip product for four of the six samples. The tag `cbr3on` is now
burned (`run_valfast.sh` refuses an existing root, M13) — a future round
reusing it must pick a fresh tag.

### ASSERT 8 (new) — KEEP is closed under PR-arm provenance

No prior round checked whether a KEEP *PR* arm's own Q/L input was itself
in KEEP — a KEEP name could stop being usable the moment the round ran.
`plan_20260817.py` re-derives each of the 7 PR-arm→Q/L-root edges from the
arm's own log (not a hardcoded table) and fails if the discovered source is
missing or outside KEEP. All 7 passed cleanly; re-verified again after the
sweep completed (all 7 sources still resolve on disk).

### The 08-17 broken-symlink defect, found and fixed in the fork

Pre-flight found **360 broken symlinks**, all self-contained inside four
dirs already in this round's own removal set: `work-{r1qlmc,r2mc,nuecc48,
ncpi0}-vfcbr3off` (the doc 73 §12.5 "harness fix that rode along" —
`run_valfast.sh`'s `nusel_root()` returned RELATIVE roots on the first OFF
attempt, so `ql_evt<N>/*.npz` symlinks resolved against the wrong
directory). The real data those broken links pointed at lives in
`work-img-<sample>/evt<N>/` — a KEEP imaging hub — via a **separate,
working** symlink one level up; nothing was ever lost, only a spurious
convenience symlink inside a dir already condemned. `retire_20260817.sh`'s
interlock 0 was changed from an unconditional refuse to: refuse only if a
broken link's containing top-level dir is **outside** the removal set;
warn-and-proceed if every one is inside it (verified 0/360 were outside).
Post-round: 0 broken symlinks, confirming the fix was correct, not a
loophole.

### Known cost, stated rather than silently absorbed

- **`work-mcp2k-cb0816` (17G) + the four `work-*-harv3` arms (9.5G)
  retire.** `vtx_rules/baselines.py`'s `deployed_dump_path()` (which
  rewrites `-prod0813` → `-harv3`) stops resolving **again**, and
  `vtx_rules/scankit.py:858`'s three named harv3 arms are gone. The **1543
  `vertex_labels/` hand-scan labels** (13 tags, self-contained JSON) survive
  — same precedent as `uitest75`/`vtxscan1` and the 08-16 `-prod0813` drop —
  but the calib dumps they were scanned against do not.
- **mcp2k has no complete PR product after this round** — only the 40
  events in `work-cbr3-census-pr-on`.
- `work-cbr3-census-offfull` (9.6G) + `work-cbr3-census-pr-off` retire: doc
  73 §12.6's both-directions census becomes **one-sided on disk**; the
  numbers survive in the doc text only.
- Doc pr/89 / pr/90 A/B off-arms retire (`pr89-family` 16G, `pr90-family`
  24.5G); a pairwise gate is not re-runnable from these arms
  (`PROTECTED.txt`'s own "a floor is a PAIR" caution applies — accepted
  because both rounds are **closed**: pr/89 topo REJECTED live, pr/90's
  D1+D3 rounds A vetoed, only D4 shipped).
- `work-{mcp1k,nuecc48,ncpi0}-pr87ion3` (3.3G) **released** from
  `PROTECTED.txt`, superseded by today's flip; owner-confirmed 2026-08-17.
- `work-cbr2-*` (40 dirs, 3.2G, doc 73 round-2 cathode rescue — **reverted**,
  §11.9) retires with no loss beyond what doc 73 already absorbed.

### Families this round documents for the first time

`docs/work-tags.md` never named these; decoded here so 148 dirs are not
swept with zero textual record beyond this line:

| pattern | meaning | doc |
|---|---|---|
| `work-mcp2k-<tag>` | a SIXTH sample, the 2000-event data set (mcp2k) — extends the manifest-prefix table above | docs 72, 73, pr/82, pr/88, pr/89 |
| `-cb0816` | the 2026-08-16 Q/L reprocessing root for mcp2k (mirrors `-cb0805` for the other five samples) | docs 72, 73, pr/88 |
| `-harv3` | the `dl_vtx_harvest`-generation-3 PR arm (min_accept 10.0, top_k 5, harvest recording ON) | pr/88, pr/89 |
| `-pr89*` | doc pr/89 round-4 DL-vertex arms: `base`/`swap`/`topo` (A/B legs), `-d2-{base,t310,w825,w1240}` (center/scale sweep) | pr/89 |
| `-pr90*` / `-pr90r4*` | doc pr/90 unbroken-kink rounds 1-4; `bare`/`off`/`on` legs, `r4` = round 4, `smoke1-3` = smoke arms | pr/90 |
| `-kink90*` | doc pr/90's earlier hand-scan probe arms (`kink90`, `kink90c`, `kink90d`) | pr/90 |
| `cbr2` / `cbr3` | cathode-bundle-rescue rounds **2** and **3** (docs 72/73) — a DIFFERENT, later campaign than the 2026-08-02 `cbr` census; note `work-cbr2-*`/`work-cbr3-*` put the **campaign name in the sample slot**, breaking the `work-<sample>-<tag>` shape every prior convention assumed — any sample-keyed regex mis-keys these 68 dirs | docs 72, 73 |
| `-off2` / `-on2` (and `-off3`) | second/third iteration of an off/on A/B gate leg, same convention as `d52on/d52off` etc. | docs 72, 73, pr/90 |
| `-vfcbr3on/off/off2` | valfast `-full` nusel roots for the cbr3 rounds (Q/L side); `work-vf<sample>-cbr3<leg>` is the matching PR out-root | doc 73 §12.5 |

### The measured 52G arithmetic

`work-*` 38.3G (30 dirs) + `dl_vtx_training` 67M (18G before) + `archive/`
7.9G (7.3G before + the new era's 0.65G) + `input_files_reco1` 4.5G
(untouched) + `bee/` 728M (untouched) + `input_files` (symlink, 0) + misc =
**52G**, measured, not projected.

### `PROTECTED.txt` — rewritten for the new state

The `pr87ion3` line moved from active to **RETIRED** (superseded by today's
flip); a RETIRED note added for `work-mcp2k-cb0816` + the four `-harv3`
arms; the post-flip family added as **real tab-delimited lines** (not a
comment block — the 2026-08-11 failure mode this file's own history
records) so the *next* round's ASSERT 7 sees `work-cbr3-census-on`,
`-census-pr-on`, `-bare2evt`, `-bare2evt-pr`, the five `-vfcbr3on` Q/L roots
and the five `vf*-cbr3on` PR roots. `work-tfix388-r9` and
`work-{r1qlmc,r2mc}-prod0813` stay active, unchanged.

### Gate labels for future re-checks

`scripts/retire/state-20260817/{plan.json,removed.tsv,dlruns-removed.tsv}`,
`scripts/retire/tierA_20260817.txt`,
`archive/records/pr88-90-era-20260817/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`
(148 arms).

## RETIREMENT ROUND 2026-08-16 — the pr/79-86 campaign sweep, 158G → 23G

**STATUS: EXECUTED, in two stages.** Stage 1 (the planned round):
`CONFIRM=yes retire_20260816.sh A` — 189 dirs / 69.76 GiB removed from
`work-*`, archive integrity **PASS 189/189**; `thin_dlruns_20260816.py`
dropped 2195 `.pth` / 58.81 GiB from `dl_vtx_training/runs`;
`preserve_and_drop_campaigns_20260816.py` preserved 22 `nusel_labels/` trees
(verified byte-identical) then dropped the three old campaign archives, 3.2
GiB. Stage 2, same day, owner-requested follow-up: `followup2_20260816.py`
archived-then-dropped 9 more `work-*` dirs, 3.98 GiB. **Broken symlinks 0
before and after every step; no git-tracked file deleted; every deletion
archived and integrity-checked first.** `sbnd_xin` **158G → 23G**, `work-*`
**216 → 18** dirs. Full campaign account: **doc pr/86** (this round is
housekeeping, not a new investigation — no new doc number spent).

### Why this round exists

The pr/79 (dl_vtx_harvest deployment), pr/83 (`break_seg_orient`), pr/85
(interposed stub) and pr/86 (interposed splice, two rounds — §14 and §15)
campaigns regrew the tree from the 08-13 round's 13 survivors / 20G to 216
`work-*` dirs / 158G in three days, and the pr/77-81 DL-vertex fine-tune
campaign left 2194 per-epoch checkpoints (59G) that 08-13 never had to
account for.

### Stage 1 — the same three-requirement shape as every prior round

KEEP started at 27 names (17.0 GiB), driven by three owner requirements
(hand-scan results, the live display, latest production), not just
infrastructure:

- **Infrastructure** (13 names, unchanged rationale from 08-13): 5 imaging
  hubs + 5 `-cb0805` Q/L hubs (**verified this round**: every existing PR
  arm, including the newest, reads
  `reading file=.../work-<s>-cb0805/ql_evt<N>/pctree-evt<N>.tar.gz` — the
  hubs remain the PR chain's live input) + `work-tfix388-r9` +
  `work-stmcamp-d66new` + `work-nuecc48-prsmoke2`.
- **Hand scan + live display** (8 names): `vertex_labels/` (483 labels, 6
  tags) records `source` inside a `-prod0813` arm for every label;
  `baselines.py:36 deployed_dump_path()` resolves exactly 473 dumps
  (407+47+19) through the three *plain* `-ma10` arms (the 12
  `-ma10ft2u`/`-ma10-k20`/`-ma10k20-harv*` variants are unreachable from the
  label loader and were never kept); `work-r1qlmc-prod0813` +
  `work-r2mc-prod0813` are **live on bokeh :5017/:5018**.
- **Latest production** (6 names): `work-{mcp1k,nuecc48,ncpi0}-pr87ion3` =
  doc pr/86 §15 knobs-on at the config that became SBND production (toolkit
  `771f075b`); `work-pr87-postflip-{mcp1k,nuecc48,ncpi0}` (21 events) is the
  **only physical evidence** the shipped jsonnet reproduces `pr87ion3` — §15.4
  asserts "42/42 archives ≡ pr87ion3" but never names the arm. Verified
  independently this round: the round-2 sentinel `mvga: op3
  splice-straighten cluster=9 carried=2 straightened=2 reach=10.65cm`
  appears identically in `work-nuecc48-pr87ion3` and
  `work-pr87-postflip-nuecc48`, absent from `pr87off7`/`pr86ion`/`prod0813`.

**The `PROTECTED.txt` near-miss.** `plan_20260813.py` parsed `PROTECTED.txt`
into `PROT_LISTED` but only ever printed it (`RELEASED = PROT_LISTED - KEEP`)
or intersected it with `KEEP` for the driver's interlock 3 — `tier()` never
consulted it. `PROTECTED.txt` was edited *after* the 08-13 round ran, adding
five `prod0813` lines; a straight fork of that plan script would have printed
all five as "RELEASED" and swept them. Fix: `plan_20260816.py` adds **ASSERT
7**, a read-only check that `PROT_LISTED - KEEP` is empty — deliberately not
a `tier()` refactor, so the script deleting 189 dirs wasn't also exercising a
rewritten classifier for the first time. All 7 asserts PASSed; ASSERT 7
specifically: `0 -- PASS (6 PROTECTED.txt names, all in KEEP)`.

**`dl_vtx_training/runs` — every trained arm checked against its doc verdict,
all rejected.** 20 large training arms (2.9–4.9 GiB each) span the whole
pr/77-81 campaign. Checked each: `ft0/ft1/ft1hn/ft1ps` (round 1, pr/77 §8e —
"ft1hn ≡ ft1 on every out-of-fold metric", hard-negative machinery inert);
`ft2/ft2m3/ft2c9b*/ft2hn/ft2w` (round 3, pr/78 — "ft2 is bit-inert: every one
of the 378 events identical to baseline"); `ft2u`/`ft2u-deploy` (the one arm
staged for deployment; pr/79 §3: "REJECTED, −40/473 marginal live");
`hft1`/`hft1-deploy` (pr/79 §11: "NEGATIVE, no live A/B, no flip");
`hr1`/`hr2`/`hr3`/`hr3-deploy` (pr/81 round 2 — hr1 FAIL, hr2 FAIL, hr3 "pass
(marginal)" on OOF but deploy screen −3, "nothing ships now"). **Nothing from
the entire fine-tune campaign is in SBND production** — what shipped is two
knobs (`dl_vtx_min_accept_score` 4→10, `dl_vtx_harvest` recording-only),
neither reads a checkpoint. Owner-confirmed: dropped **all** 2195 `.pth`
files (58.81 GiB), kept every `config.json`/`*.log`/`*.tsv`/`*.json` (2.3
MiB) — every number the docs quote survives; only the ability to reload a
rejected net without retraining is lost, and nothing rejected needs
reloading.

**The three old campaign archives** (`tgm-docs29-39`, `aborted-d54`,
`stm-docs40-49`, 1.25 GiB after Stage 1's `work-*` sweep) held 22
`nusel_labels/` trees with no other copy. `preserve_and_drop_campaigns_20260816.py`
copied all 22 to `archive/records/labels/<campaign>/<tag>/`, verified
byte-identity with `filecmp.dircmp` on every one, **then and only then**
removed the three archives.

### Stage 2 — same-day follow-up: "only the latest one, plus input to achieve it"

After Stage 1 landed at 27G, the owner asked to reduce `work-*` further:
keep, per sample, only the single latest production arm and the Q/L/imaging
input that built it — narrower than Stage 1's three-requirement KEEP.
`work-{mcp1k,nuecc48,ncpi0}-pr87ion3`'s input is the `-cb0805`/`-img` hubs
(already KEEP), which makes three families no longer "latest or input":

```
work-{mcp1k,nuecc48,ncpi0}-prod0813        the prior production reference
work-{mcp1k,nuecc48,ncpi0}-ma10            DL-vertex deployed-baseline arm
work-pr87-postflip-{mcp1k,nuecc48,ncpi0}   the byte-identity proof arm
```

`work-{r1qlmc,r2mc}-prod0813` are **unchanged** — `-prod0813` *is* their
latest (no pr83/85/86/87 arm exists for either), and both are live on the
bokeh viewers.

**Trade-off, confirmed with the owner before running:** 481 of 483 vertex
hand-scan labels have `source` inside a `-prod0813` dump for these three
samples. The label JSON itself is self-contained (`main_vertex`, `picks[]`,
scores — the same precedent already established when `uitest75`/`vtxscan1`'s
arm, `work-prdisp-vtx48`, was lost earlier) and **survives**, but the
underlying calib dump those scans were made against does not — no more
re-rendering `pr85_panels2d.py` / `pr86_kink_census.py` against those
events. `baselines.deployed_dump_path()` stops resolving, so the 473-event
DL-vertex analysis set (docs pr/77-81) is no longer re-derivable; the
already-built `dl_vtx_training/data/*` snapshots (kept, 20M) still back
every number those docs quote.

Safety checks run and PASSed before `followup2_20260816.py` touched
anything: 0 git-tracked files inside the 9 dirs, 0 `nusel_labels`/`ql_labels`
dirs inside them, 0 symlinks anywhere in the tree pointing into them, and
both live viewers reference only `r1qlmc`/`r2mc-prod0813` (confirmed by
reading the actual `pgrep` process lines, not a substring match against the
shell's own command). Same archive-then-delete pattern as Stage 1: record
layer archived to `archive/records/pr79-86-era-20260816/<group>/` and
integrity-verified before `rm -rf`.

### The measured 23G arithmetic

`work-*` 88G → **13G** (18 dirs) + `dl_vtx_training` 59G → **26M** +
`archive/` 8.1G → **7.3G** (three old campaigns dropped, `records/` kept
whole and grew by the new era's 401M) + `input_files_reco1` 1.9G (untouched,
input data) + `bee/` 0.7G (untouched) + misc 0.2G = **23G**, measured, not
projected.

### Known cost, stated rather than silently absorbed

- **~78 arms have no textual record anywhere** beyond doc pr/86's
  collective/ledger prose (set-diff of the pre-round `ls -1d work-*` against
  every mention in `docs/`, `scripts/`, `*.sh`, `*.py`): the 15
  `work-*-pr87off{2..6}` v2–v6 knobs-off gates, the 36 `work-pr86r2{a..l}-*`
  round-2 iteration arms, the 9 `work-pr86b{1s5,2s8,3c10}-*` and 12
  `work-pr86b-l{5,10}a{130,150}-*` sweep grids, plus assorted pr83/pr85
  probes. Doc pr/86 §15.3's "iteration ledger (8 binaries; every intermediate
  arm left in place)" names no per-binary label, so the ledger's rows lose
  their arms — accepted, the verdicts are in the doc and the adopted point
  (5/15/1.0) survives as `pr87ion3`.
- `work-*-pr86ioff` (2 dirs, aborted partial arms — doc pr/86 §14.7 says to
  ignore them) and the five `work-*-pr85ion2` arms (doc pr/85's epoch, its
  gate PASS is now the only surviving record) retired with no loss beyond
  what the docs already absorbed.
- **Stage 2's cost** (vertex-scan dumps and the DL-vertex analysis set for
  mcp1k/nuecc48/ncpi0) is above, and is a deliberate narrowing of Stage 1's
  KEEP, not an oversight.
- `scripts/analysis/pr57/oc56_truth.py`'s `DEFAULT_ARMS` situation
  (unresolved since 08-13) is unchanged by this round.

### `PROTECTED.txt` — rewritten for the new state

`work-{mcp1k,nuecc48,ncpi0}-prod0813` and `work-{r1qlmc,r2mc}-prod0813` moved
from the RETIRED-eligible set to a **RETIRED** note (mcp1k/nuecc48/ncpi0, now
actually gone) vs kept live (r1qlmc/r2mc, still current). `pr87ion3` and
`pr87-postflip-*` (mcp1k/nuecc48/ncpi0 only) added as real tab-delimited
lines so the *next* round's ASSERT 7 sees them too — closing the exact gap
this round's ASSERT 7 was written to catch.

### Gate labels for future re-checks

`scripts/retire/state-20260816/{plan.json,removed.tsv,dlruns-removed.tsv,followup2-removed.tsv}`,
`scripts/retire/tierA_20260816.txt`,
`archive/records/pr79-86-era-20260816/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`
(198 arms total across both stages), `archive/records/labels/{tgm-docs29-39,stm-docs40-49}/<tag>/nusel_labels/`
(22 trees, verified byte-identical to their pre-removal originals).

## RETIREMENT ROUND 2026-08-13 — the pr/66-75 campaign sweep, 74G → 20G

**STATUS: EXECUTED.** `CONFIRM=yes retire_20260813.sh A` — 388 dirs / 53 GiB
removed, refused=0, **401 → 13** `work-*` dirs, `sbnd_xin` **74G → 20G**,
`/nfs/data/1` free 493G → 546G. Broken symlinks 0 before and after; no
git-tracked file deleted; archive integrity **PASS 388/388**. Repro block at the
top of this file. Full campaign account: **doc pr/76**.

### Why this round exists

The pr/51, pr/64, pr/66, pr/67, pr/72, pr/73, pr/74 and pr/75 campaigns regrew
the tree from the 08-11 round's 18 survivors / 23 G to **401 dirs / 74 G** in
two days. Every one of those arms is a leg of an A/B whose verdict already lives
in its doc, and production has moved **82 clus/cfg commits** since the cb0805
campaign, so none of them is comparable to anything current. The round cleared
the disk for the **prod0813** campaign (doc pr/76), which then re-ran the PR
stage over all five samples at the current operating point.

### KEEP — 13 names (9.45 GiB), and why it is smaller than 08-11's 18

Five `work-img-*` imaging hubs + five `work-*-cb0805` Q/L hubs + `work-tfix388-r9`
(the sole active `PROTECTED.txt` line) + `work-stmcamp-d66new` and
`work-nuecc48-prsmoke2` (git-tracked). The three `work-pr64r4-on*` reference arms
and two `work-pr64r4-scan*` oc56 arms that 08-11 kept are **superseded** by the
prod0813 arms and retire here.

**The five `-cb0805` hubs changed role.** For 08-11 they were a record layer that
Phase 4 could thin. The owner chose a **PR-stage-only** reprocessing for
prod0813, so they are now the campaign's **INPUT** — their
`ql_evt*/pctree-evt*.tar.gz` feed the PR chain and their
`ql_evt*/mabc-all-apa.zip` feed the Bee builder. Hence:

> **NO PHASE 4 THINNING THIS ROUND.** `thin_hubs_20260811.py` must not be
> re-run. `work-img-mcp1k`'s remaining `icluster-apa*-masked.npz` (1.7 GiB) is a
> genuine imaging input and is likewise out of scope.

### The measured 20 G arithmetic

`work*` 63.41 GiB + non-`work*` 10.02 GiB = the 74 G. KEEP 9.45 + floor 10.02 +
~0.46 of new tarballs ⇒ **20 G**, measured, not projected. Note `input_files` is
a **symlink** into `/nfs/data/1/yuhw/` — it shows as 2.4 G under `du -sh */`
because the trailing slash dereferences it, but it is not this tree's footprint.

### Four defects in the inherited machinery, fixed in the forks

1. **`$BASE` was the symlink path, making three checks vacuous** — the one that
   matters. Every prior round did `cd "$(dirname "$0")/../.." ; BASE=$PWD`.
   Invoked through `toolkit/sbnd_xin` (a symlink, and the normal way in), `$PWD`
   is the logical path, so `find "$BASE" …` descends nothing and `du -sh "$BASE"`
   measures the link. Observed in this round's own execution log: **interlock 0
   reported "0 broken symlinks" having scanned nothing** — it would report 0 with
   the tree on fire — the survivor census printed `work* DIRS remaining: 0
   (expect 13)` after a fully successful round, and `du` wrote `0` into
   `removed.tsv`'s footer. `rm -rf "$BASE/$d"` was unaffected (only the final
   component matters), so the deletion was correct and the *verification* was
   blind. Fixed with `cd -P`; a corrected footer is appended to `removed.tsv`.
2. **The driver-log block was dead and dangerous.** 08-11 tarred all 118
   `work-*.driver.log` orphans and none returned, so the block matches nothing —
   but with `$dlogs` empty, `du -cm $dlogs` degrades to `du -cm .` and reports
   the whole 74 GB tree as the driver-log footprint. Deleted, not carried.
3. **The `scan-d59k/bee` block was dead** (stripped to 2 MB in 08-11; its guard
   now compares 0 zips to 0 urls). Deleted.
4. **Interlock 2 self-trips.** `pgrep -f 'wire-cell |run_(ql|pr|nusel)_evt'`
   matches any shell whose command line merely *contains* the pattern, including
   the exploration shells used to prepare the round. Reproduced: 2 phantom
   matches with no job running. The documented workaround
   (`ALLOW_LIVE_JOBS=yes`) defeats the real M5 check, so a false positive here
   trains the operator to disable the interlock. `grep -v` widened.

Also: `plan_20260813.py`'s ASSERT 4 no longer skips hidden top-level entries
(`.nutmp/`, `.tracetmp/`, created since 08-11; both hold 0 symlinks today, so
this closes a blind spot rather than fixing a live break), and the KEEP table is
now **sized** — 08-11 walked only the removal set, so every survivor printed
`0 MB`, and the survivor sizes are exactly what the disk-target arithmetic rests
on. A directory-mtime histogram is printed as a **sanity report that gates
nothing**: the tree was fully regenerated after 08-11, so 382 of 401 dirs are
under 48 h old and any cutoff coarse enough to be safe protects nearly the whole
universe. The gate is the explicit KEEP dict, full stop.

### Assert results

All six PASS. ASSERT 2 is trivially clean this round — the tree's only label dir
is `work-stmcamp-d66new/nusel_labels`, which is in KEEP, so **no
archive-and-commit of hand-scan labels was owed** (unlike 08-11's
`overclustering_labels` phase). `sbnd_xin/vertex_labels/` (tags `vtxscan1`,
`uitest75`) and `overclustering_labels/` live outside `work-*` and were never at
risk. ASSERT 4 walked 6958 symlinks, hidden dirs included, and found 0 pointing
into the removal set.

### Known cost, stated rather than discovered later

`scripts/analysis/pr57/oc56_truth.py:54 DEFAULT_ARMS` loses **all three** of its
arms: `work-pr64r4-scan48`/`scan19` retire here, and its third name
`work-pr64-scan1k` was *already* stale (the disk had `work-pr64r4-scan1k`). The
08-11 round justified reclassifying `oc56scan-evt*.jsonl` as HEAVY — dropped,
not archived — precisely on the grounds that "the two arms `oc56_truth.py` cites
are KEPT whole". That justification does not survive this round, so the oc56
truth table is not recomputable until someone runs a fresh
`PR_OC56_SCAN_DUMP=1` arm. Owner-confirmed.

`PROTECTED.txt` housekeeping was done: the 2026-08-11 reference family moved to
RETIRED, and the prod0813 arms added as **real tab-delimited lines**. The 08-11
entry was a *comment* block, so the parser (field 1 of each non-comment line)
never saw any of those five names — they were never actually protected.

### Gate labels for future re-checks

`scripts/retire/state-20260813/{plan.json,removed.tsv}`,
`scripts/retire/tierA_20260813.txt`,
`archive/records/pr66-75-era-20260813/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`
(388 arms, 3395 MiB raw → 474 MB gz).

## RETIREMENT ROUND 2026-08-11 — the pr/38-65 campaign sweep, 103G → 23G

**STATUS: EXECUTED.** `CONFIRM=yes retire_20260811.sh A` (454 dirs, 69 GiB) +
`thin_hubs_20260811.py` (Phase 4, 9.84 GiB inside 6 surviving hubs) — 471 → **18**
`work-*` dirs, `sbnd_xin` **103G → 23G**, `/nfs/data/1` free 464G → 544G. Broken
symlinks 0 before and after; no git-tracked file deleted; archive integrity
**PASS 454/454**. Repro block at the top of this file.

### Why this round exists

The pr/38 through pr/65 campaign regrew the tree from the 2026-08-05
clean-slate baseline (5 survivors) to 471 `work-*` dirs / 92 GiB, and current
production moved three times in one day (2026-08-11: pr/62 S7 corridor flip
`10063f4e`, pr/65 orphan-fix flip `2df05519`, pr/64 round-4 W-track flip
`b38127a0`), making the whole pre-08-11 arm population non-comparable — every
arm is one leg of an A/B whose verdict already lives in its doc. Two things
rode along: archiving the overclustering hand-scan labels (untracked and
`.gitignore`d — disk was their only copy) before any deletion, and delivering
three fresh Bee scan sets at current production afterward.

### M1 gate on the Bee sources

Before building anything: `local/lib/libWireCellClus.so` was built **14:39:45**;
7 `clus/`+`cfg/` files carried mtime **15:13:36** (after the build, before the
15:15 pr/64 commit) — the reflog showed three bare `reset: moving to HEAD` at
15:11-15:13, working-tree content already equal to HEAD. Ran `wcbuild` as the
actual gate rather than trust the mtime read: **0 objects recompiled, rc=0** —
confirms the 14:39 binary is genuinely `b38127a0`, so `work-pr64r4-on48/on19/on1k`
(which ran 14:56-15:08, entirely after the build) are valid current-production
Bee sources.

### The KEEP set — 18 explicit names, not a dependency-graph inference

Same shape as the 2026-08-05 clean-slate round: with imaging already
regenerated and current production baked into `wct-pr-perevt.jsonnet`, the
pre-08-11 arm population is a record layer, not an input set. `plan_20260811.py`
(fork of `plan_20260805cs.py`) uses an explicit `KEEP_WHY` dict instead of hub
inference — 5 `-img-` hubs (1090 inbound symlinks total, runner-pinned), 5
`-cb0805` Q/L hubs (runner-pinned, **thinned**, see Phase 4), 3 current-production
reference arms `work-pr64r4-{on48,on19,on1k}` (the Bee sources), 2 oc56
scan-dump arms `work-pr64r4-{scan48,scan19}`, and 3 git-tracked/M13 arms
(`work-stmcamp-d66new`, `work-nuecc48-prsmoke2`, `work-tfix388-r9`). The pr/33
knob-off gate pair (`work-pr33-{base48,off48}`, `PROTECTED.txt` survivors of
the cs round) was retired this round — superseded by the cb0805 campaign and
every flip since; `PROTECTED.txt`'s active section was reconciled, moving the
16-already-gone + 2-now-retired entries into its RETIRED section (it had drifted
stale by 16 since the cs round and was never updated, contrary to its own
housekeeping rule).

### Two extra removal classes invisible to every prior round's `work*` glob

- **`VOID-pr32-round1/`** (0.83 GiB, 6 dead pr/32 arms bundled under a
  non-`work`-prefixed name) — added directly to `plan_20260811.py`'s universe
  (verified: real dir, 0 symlinks inside, 0 git-tracked files), flows through
  the normal archive-then-delete path.
- **118 orphan `work-*.driver.log` files** (1.1 MiB) — records of arms deleted
  by earlier rounds, not directories, invisible to every prior `plan_*.py`.
  Tarred as one bundle (`scripts/retire/state-20260811/driver-logs.tar.gz`)
  then removed.

`scan-d59k/bee/` (694 MB, 9 Bee zips) is a third special case, dropped without
archiving: all 9 already have a saved `.url` (checked — unlike the 2026-08-03
round, which found only 12/44), so the sets are still live on the BNL twister
server; the record layer and the hand-scan `.tsv`/`.txt` tables were separately
copied to `archive/records/labels/scan-d59k/`.

### Two inherited driver defects fixed, found live during exploration

1. **Survivor census.** `retire_20260805.sh:188` / `retire_20260805cs.sh:195`
   count `ls -d work* | wc -l`, which in this tree also counts the 118 orphan
   `.driver.log` **files** and can never match the expected directory count.
   `retire_20260811.sh` uses `find -maxdepth 1 -type d`.
2. **Brace-expansion no-op.** `retire_20260805cs.sh:85` iterates
   `tier{A}_20260805cs.txt` — bash leaves a single-element brace literal, so
   the `cat` silently matches nothing and the Bokeh interlock unconditionally
   prints "safe to proceed" even when a live viewer names a removal-set
   directory. `retire_20260811.sh` iterates the real tier-list files built from
   `$TIERS`, shared with the removal loop.

### Phase 2 — overclustering hand-scan labels archived + committed

`overclustering_labels/` (899 labels / 233 files across 230 events — owner
round-1 + `claude-scan223` + `claude-scan50`, backing doc pr/57's 899-label
gate) was untracked and `.gitignore`d (`*.json`), so disk was its only copy.
Preserved two ways before any deletion: byte-identical copy to
`archive/records/labels/overclustering_labels/` (`filecmp.dircmp` verified),
and 230 files (scratch tags `battest`/`battest3`/`unittest`/`floortest`/
`smoketest` excluded) committed to `wcp-porting-img` — `5fa6037`. The
scan-d59k hand-scan `.tsv`/`.txt` tables were copied the same way.

### Phase 3 — the sweep

`plan_20260811.py`, 6 asserts, all PASS: SP-frame source survival (5/5 OK, only
`work-img-mcp1k`'s SP layer actually drops, in Phase 4), hand-scan record
archive-copy verification, no git-tracked file in the removal set, dangling-link
dry run (0 of 6958 outside-set symlinks point into it), every KEEP name present,
and (**new this round**) `overclustering_labels` archive-copy + git-tracked
verification. `archive_records_20260811.py` (fork of the 08-05 script,
24-way): **HEAVY gains two classes** — `tracking-pr.root` (its only consumer,
`pr33_cmp.py`'s comparison families, is entirely retired this round) and
`oc56scan-evt*.jsonl` (see the regression below) — archived 3.5 GiB raw → 406
MiB gz, **integrity PASS 454/454**. `retire_20260811.sh A` (dry run, then
`CONFIRM=yes`): 454 removed, 0 refused, 0 broken symlinks before or after, 0
git-tracked deletions, 18 survivors (matches KEEP).

### Phase 4 — hub thinning, 9.84 GiB

`thin_hubs_20260811.py`, hard-refuses any path outside the 6 named roots, any
`ql_evt*/` path other than `calib-evt*.json`, and any symlink. Inside the five
`-cb0805` roots: the `pr_evt*/`+`nusel_evt*/` layers (stale 2026-08-05 PR/nusel
output, superseded by the pr64r4 reference arms — 5.45+0.62 GiB heavy) and
every `ql_evt*/calib-evt*.json` dump (2.74 GiB — never read by the PR chain or
Bee builder) removed after archiving the record layer
(`wct_pr_evt*.log`/`wct_nusel_evt*.log`/`nusel-evt*.tsv`/`tracking-stm.root`/
`rc.txt`/`stdout.log`; 5 tarballs, **integrity PASS 5/5**, 167 MiB raw). Then
`work-img-mcp1k/evt*/sp-frames*.tar.bz2` (1.23 GiB) after confirming
`input_files_reco1/staged-mcp2025c-1000evt` covers all 1000 source events
(1004 entries present).

### A self-inflicted regression, found by the post-round verification, and its fix

`oc56_truth.py`'s current `DEFAULT_ARMS` (comment dated 2026-08-11, i.e.
written the same day as this round) is
`['work-pr64r4-scan48', 'work-pr64r4-scan19', 'work-pr64-scan1k']` — **three**
arms, not the two this round's KEEP set carried forward. `work-pr64-scan1k`
(the full-1000-event oc56 population dump, superset of the old scan50+scan395
events) was retired, and its `oc56scan-evt*.jsonl` dumps were dropped as HEAVY
(not archived) by the very same-round `archive_records_20260811.py` reclass —
so the content was gone, not just relocated. Post-round verification
(`python3 scripts/analysis/pr57/oc56_truth.py --out ...`) caught it: `GATE
orphan labels: 358 FAIL` (of 899 loaded), overwhelmingly the mcp1k-sample
`claude-scan50` tag.

Fix: regenerated the dump as a fresh, consistently-named arm —
`work-pr64r4-scan1k` (matching the `-scan48`/`-scan19` naming already kept) —
via `PR_JOBS=6 PR_OC56_SCAN_DUMP=1 ./run_pr_chain_batch.sh work-mcp1k-cb0805
work-pr64r4-scan1k data`, bare (current production is the default compiled
config, so no `SBND_*` override needed — same as how `on1k`/`scan48`/`scan19`
were produced). [FILL IN: rc, event count, GATE result once complete —
see the addendum below / commit history for the follow-up.]

### Bee sets delivered — three links at current production (toolkit `b38127a0`)

Built from the KEPT hubs, using the **frozen doc-71 event lists** so `bee_idx`
stays comparable to the doc-71 scan (`diff` against
`docs/pr/{nuecc48,ncpi0,mcp1k-50}-cb0805.index.txt`: **identical** on all
three). `nu_evaluated` moved slightly since doc 71 across the pr/62+pr/64+pr/65
flips:

| sample | doc 71 | now | change |
|---|---:|---:|---|
| nueCC48 | 47/48 | 47/48 | none |
| NCpi0 | 19/19 | 18/19 | lost 285567 |
| mcp1k | 445/1000 | 444/1000 | lost 280853, 52613, 59723 · gained 281953, 48895 |

285567 and 52613 (the only two of those inside the three frozen Bee lists) were
included via `--allow-unevaluated`: 285567 unexpectedly still carries full PR
layers (`shower_track-global`/`track_fit-global`/`vertices-global`/`mc`, just
no selected-candidate marker); 52613 has image+clustering only (5 layers, no
PR). Both probed as single-event zips (rc=0) before building the full sets.

| set | events | source (ql × pr) | URL |
|---|---:|---|---|
| nueCC48 | 47/48 | `work-nuecc48-cb0805` × `work-pr64r4-on48` | `https://www.phy.bnl.gov/twister/bee/set/9e2a1a1e-b637-4be5-99b7-f49bf8c04c57/event/list/` |
| NCpi0 | 18/19 evaluated, 19 built | `work-ncpi0-cb0805` × `work-pr64r4-on19` | `https://www.phy.bnl.gov/twister/bee/set/13900b8c-e48c-4ebb-8daa-da19e2e989b6/event/list/` |
| mcp1k-50 | 49/50 evaluated, 50 built | `work-mcp1k-cb0805` × `work-pr64r4-on1k` | `https://www.phy.bnl.gov/twister/bee/set/f8203fcd-8f16-4aac-8576-cca0c7086d79/event/list/` |

Record files: `bee/prod0811/{nuecc48,ncpi0,mcp1k50}-prod0811.{zip,index.txt,prid-map.txt,url}`
(local only, `archive/`-style — the small `.index.txt`/`.prid-map.txt` records are
git-tracked at `docs/pr/{nuecc48,ncpi0,mcp1k50}-prod0811.{index,prid-map}.txt`,
following the `docs/pr/pr65-bee.index.txt` precedent).

### Post-round checks

`find . -xtype l` 0 before and after · `relink_tags.py` repaired=0 unresolved=0
· `git status --short | grep '^ D'` empty · survivors 18 == KEEP · `du -sh` 23G
· all four `run_{ql,nusel,pr,img}_evt.sh data` interfaces list correctly once
`SBND_WORK_ROOT` is supplied (the bare-invocation M13 refusal when unset is
pre-existing since 2026-08-05, not a regression — `work/` has not existed since
before this round).

### Gate labels for future re-checks

`scripts/retire/state-20260811/{plan.json,removed.tsv,driver-logs.tar.gz}`,
`archive/records/pr38-65-era-20260811/<group>/<tag>.{tar.gz,links.txt,manifest.tsv}`
(454 arms + `cb0805-hubs/` for the Phase-4 record layer), `bee/prod0811/`.

## TIDY ROUND 2026-08-03 — the directory itself: 216 → 74 top-level entries

**STATUS: EXECUTED 2026-08-03**, immediately after the retirement round below.
That round took the *space*; this one took the *tree*. Motivation: the next task
is a PR-tuning campaign over the 572 valfast mcp1k events, and `sbnd_xin` had
**216 top-level entries** (56 dirs, 34 `*.sh`, 95 `*.py`, 34 misc).

| | before | after |
|---|---|---|
| top-level entries | 216 | **74** |
| `work*` dirs | 27 | **19** |
| `bee-*` dirs | 8 | **1** (`bee/`) |
| top-level `*.py` / `*.sh` | 95 / 34 | **5 / 14** |
| `sbnd_xin` | 28 GB | **25 GB** |

Tooling in `scripts/retire/tidy_*_20260803.{py,sh}`; the authoritative
name → new-path map is `tidy_map_20260803.tsv`, and `scripts/README.md` is the
human index.

```bash
python3 scripts/retire/tidy_map_20260803.py       # build the map (STAY vs MOVE)
python3 scripts/retire/tidy_refscan_20260803.py   # who references whom; INVOCATION vs MENTION
scripts/retire/tidy_move_20260803.sh              # dry run of the moves
python3 scripts/retire/tidy_rootfix_20260803.py   # repoint $0/__file__ roots
python3 scripts/retire/tidy_docfix_20260803.py    # rewrite doc citations
python3 scripts/retire/tidy_citegate_20260803.py  # GATE: every cited path resolves
```

### What moved, and what deliberately did not

**Stayed** (36 entries): the 12 `run_*_evt.sh` + `_runlib.sh`, the 12 jsonnet job
configs, the four symlinks, and five cross-campaign tools (`nusel_extract.py` —
28 doc citations and imported by `scripts/analysis/stm/stm_fv_census.py` — `pr_scores_table.py`,
`relink_tags.py`, plus `wct-img-2-bee.py` / `merge_sel_archives.py` /
`upload-to-bee.sh`, which belong in `scripts/bee/` by topic but are **invoked by
runners that stay**; moving them would have meant editing production runners
immediately before a campaign).

**Moved** (127) into `scripts/{analysis/{pr11,pr20,pr23,pr24,pr25,stm,ql,light,cathode,geom,misc},runners,bee,cfg,perf,root}/`
and `products/`.

### Three traps this round hit — read before attempting a similar move

1. **The self-locating root.** 21 of 34 `*.sh` resolve their root as
   `SBND_DIR=$(cd "$(dirname "$0")" && pwd)` and 23 of 95 `*.py` as
   `os.path.dirname(os.path.abspath(__file__))`. Moving a file into a subdir
   silently repoints `$SBND_DIR/work`, `$SBND_DIR/input_files` and every
   `HERE/"work-…"`. `tidy_rootfix` walks each up by the depth of its new dir.
   **Not a blanket rewrite**: `scripts/runners/geom_ab_batch.sh` sets `SC` and dereferences it
   only against `scripts/runners/run_pr_geom_arm.sh`, which moved into the *same* directory — a
   blanket `../..` would have broken it.
2. **Non-idempotent rewriters.** `tidy_rootfix`'s python substitution emits text
   that still matches its own pattern, so a second run nested the expression and
   the root climbed two levels too far. It hit 22 files and had to be restored
   from the git index. Both rewriters now carry an explicit idempotence guard
   and are verified by re-running to a 0-change result.
3. **`csv.writer` defaults to CRLF.** The stray `\r` made
   `awk -F'\t' '$3=="MOVE"'` in the move script match nothing — a silent
   zero-move "success". Use `lineterminator="\n"`.

### Gates

- **Citation gate `tidy_citegate_20260803.py`: PASS** — all **551** path-shaped
  citations of the 118 moved scripts, across 251 files, resolve on disk. Scoped
  to the move set on purpose: an unscoped version reported 142 "failures" that
  were all pre-existing (`abtest/hash_archive.py`, `qlport/scripts/ab_check.sh`,
  `convert.C`, …) and would have buried the real signal.
- **Reference gate `tidy_refscan_20260803.py`: 0 INVOCATIONs** left in buckets A
  (staying runners → moved scripts) and B (moved → moved across destinations).
- **Root-resolution gate**: all 22 fixed `.py` and all fixed `.sh` compute
  `sbnd_xin` exactly (`scripts/runners/geom_ab_batch.sh` correctly computes its own dir).
- **Syntax**: `python3 -m py_compile` on all 103 moved `.py`, `bash -n` on all
  moved and all top-level `.sh` — 0 failures.
- **Interface regression**: `run_{ql,nusel,pr,img}_evt.sh data` all list events,
  `rc=0`. Those files are byte-identical, so this proves nothing they depend on
  moved out from under them.
- **valfast intact**: `events-mcp1k.txt` still 572, all six pinned hubs present,
  d59k still holds 2000 `pctree-*.tar.gz`. Only `valfast/README.md` changed
  (prose paths); no executable valfast content was touched.
- **Symlinks**: `find . -xtype l` = **0** before and after.

### Tier W — 9 `work*` arms, 673 MB (archived, then removed)

`work-mrgB-post` (superseded by `work-nuecc48-prod0803` at 48/48),
`work-nuecc48-base`, `work-nuecc48-prsmoke`, `work-nuecc48-prsmoke2`,
`work-mcp1kall-cath01`, `work-nuecc48-cath01`, and
`work-r1ql-{f1,f2}-nobw` + `work-r2patrec-f1-nobw` (doc 67 closed; the non-`nobw`
arms are valfast hubs and stay). Records in
`archive/records/tidy-20260803/` (71.1 MiB raw → 33 MB gz, integrity 9/9).
`prsmoke2` leaves a git-tracked stub (three `run_*.sh`), like `d66new` in July.

**Of the 27 arms, only 9 were retirable**: 8 arms hold 18.9 GB (97 % of the
bytes) and are all load-bearing for the 572-event campaign — `run_valfast.sh`
pins `work-mcp1kall-d59k` (572), `work-nuecc48-nuf` (47), `work-r1ql-first10`
(5) and `work-r2patrec-f1` (5), and those hubs symlink into `work-mcp1000`,
`work` and `work-r1ql-f1/f2`.

### Tier C — 1000 `calib-evt*.json` deleted from `work-mcp1kall-d59k`, 2.43 GiB

Larger than all of tier W combined; d59k 8.5 → 5.9 GB. The PR chain and valfast
never read these — `-calib` is passed only when the Q/L step *re-runs*
(`run_nusel_evt.sh:643`), and PR-tail mode reads pinned pctrees. Owner decision
2026-08-03: drop, archive nothing.

**What this costs**, plainly: eight Q/L-tuning scripts can no longer run against
the mcp1k sample — `scripts/analysis/ql/{ql_pe_error,ql_beam_pref_score,
ql_beam_pref_tune,ql_prefilter_tune,ql_prefilter_parity,ql_recipe_compare}.py`,
`scripts/analysis/light/pmt_health_study.py`,
`scripts/analysis/cathode/cathode_distortion.py`. They still work on any sample
whose calib dumps survive. Regenerable only by re-running a 1000-event Q/L
campaign with `-calib`, so treat it as permanent.

### Bee — 8 `bee-*` dirs → `bee/<campaign>/`, 44 zips dropped (313 MB)

Record layer kept in full (120 files: `.url`, `.index.txt`, `.prid-map.txt`,
build/upload logs, scan keys). Owner decision: drop the zips, "we can
regenerate". **Caveat for the record**: only **12 of 44** had a saved `.url` on
the BNL twister server, and the source `work-*` arms for `pr20` and `pr23` were
already deleted in the retirement round below — so those particular sets cannot
actually be rebuilt. Five zips were git-tracked and are recoverable from history;
the other 39 are not.

---

## RETIREMENT ROUND 2026-08-05 (LIGHT) — the stale-binary sweep, 201 arms, 19.5 GiB

**STATUS: EXECUTED 2026-08-05 (`CONFIRM=yes retire_20260805.sh A,D`) — 201 dirs
/ 19.5 GiB removed, refused=0, 233 → 32 survivors.** `sbnd_xin` 49 G → 30 G;
`/nfs/data/1` free 532 G → 547 G. Broken symlinks 0 before and 0 after; no
git-tracked file deleted; `removed.tsv` has 201 rows.

### Why this round exists

doc pr/33 §11.2: **every binary built before 2026-08-05 06:32 carried stale
objects in `build/clus`** (a waf dependency miss, cured when pr/33's header edits
forced the include-cone to recompile) and is **not reproducible from committed
source**. Three independent clean builds of `2457320d` agree byte-for-byte; the
Aug-4 library does not, and it was overwritten in place so it cannot be
autopsied.

That makes ~200 arms records of a build nothing future can be compared against.
The owner's decision (2026-08-05) was to archive the record layer of every
pre-cutoff **non-hub** arm and delete the arm. Not a disk-pressure round —
532 G was free — a **structure** round: 233 flat `work-*` entries was the
complaint, and the stale-binary finding is what made most of them safe to drop.

### The partition — ordered priority, first match wins

`HUB → POSTBUILD → PROTECTED → tier D → tier A`. **Order matters**: the classes
are *not* disjoint. `work-nuecc48-prod0803` and `work-vfnuecc48-prod0803` are
both input hubs *and* `PROTECTED.txt` entries, so an unordered five-predicate
partition sums to 234 against a universe of 233. `plan_20260805.py` prints the
multi-match set rather than absorbing it, and asserts the sum exactly.

| class | dirs | disposition |
|---|---|---|
| HUB | 15 | keep — inbound symlinks, runner pins, or git-tracked |
| POSTBUILD (`mtime ≥ 06:32`) | 14 | keep — the clean-source `work-pr33-*` family |
| PROTECTED | 3 | keep — `work-pr37b-repeat{A,B}`, `work-tfix388-r9` |
| **tier D** | **19** | **delete, no archive** — 12 released `vf37*` + 7 void/smoke/probe |
| **tier A** | **182** | **archive record layer, then delete** |

Archive: `archive/records/pr28-37-era-20260805/`, **1808.4 MiB raw → 810 MB on
disk**, integrity gate **PASS 182/182**. `tracking-pr.root` is kept (~1.15 GiB of
it) because it is one of the five families `pr33_cmp.py` compares and doc pr/37
§2.2/§2.5's numbers are ROOT-leaf numbers; `pctree`, `mabc`, `calib-pr-evt*` and
`*.npz` are dropped.

### Four defects in the inherited machinery, fixed in the forks

Each was live and each would have cost something:

1. **`PROTECTED.txt` was never read by any script.** Its header claimed to be the
   carry-forward registry a new round "must union"; `retire_20260803.sh:30`
   hardcoded two names independently. And its documented `<arm> TAB why TAB who`
   format is violated by its own three `vf37` lines, which pack **four**
   whitespace-separated names into field 1 — a parser taking field 1 as one name
   protects nothing. **Ten of its seventeen arms were zero-citation**, so a
   citation-driven tier rule would have swept the pr/37 §2.5 floor. Now parsed,
   field 1, word-split, by both the plan script and the driver.
2. **A naive citation census deletes the new reference family.** doc pr/33
   `:1352` writes the clean-binary labels brace-expanded *and wrapped across a
   line break inside the braces*, so `work-pr33-f{1a,…}on48` scan as
   zero-citation — 8 of the 14 arms that are now the only clean baseline. The
   mtime cutoff is what actually saves them; ASSERT 5 makes it explicit and
   ASSERT 6 brace-expands before counting.
3. **The archive regex missed this era's calib dumps.** `plan_20260803.py:156`
   and `archive_records_20260803.py:41` match `^calib-evt.*\.json$`, but pr/28–37
   writes `calib-pr-evt<N>.json`. Unfixed, ~1 GiB of calib dumps would have been
   **archived** contrary to `archive/records/README.md`. Verified after the fix:
   `work-pr36-prod48`'s manifest shows 47 calib files `DROPPED`.
4. **The broken-symlink check ran only *after* the `rm`.** `retire_20260803.sh:114`
   fires after `:98`, and `relink_tags.py` cannot repair a link whose target is
   gone — a tripwire, not an interlock. New **interlock 0** requires 0 before.

Two more improvements: the Bokeh interlock now checks whether the viewer's
command line **names a dir in the removal set** (the blanket refusal was both too
strict — an owner with a viewer open could never run the round — and too loose,
since a viewer on an unrelated tag was never the hazard); and
`RETIRE_FRESH_HOURS` defaults to **0** rather than 6, because at 6 h this round
would have silently auto-PROTECTED arms and masked a classification gap.

### `removed.tsv` — the artifact no previous round produced

Three rounds have deleted 484 directories and the only surviving record is the
**pre-execution** `tier*.txt` intent files. `state-20260805/removed.tsv` records
what actually happened: `iso_ts, dir, tier, MB, archive_tarball, dir_mtime,
citations`, plus a header block with both repos' HEADs and pre/post
`find -xtype l`, `du -sh` and `df`.

### The mtime cutoff is a KEEP rule only — read this before reusing it

**No arm in this tree carries a build fingerprint.** `grep -rl libWireCellClus`
over the arms returns nothing, so directory mtime is the only proxy for which
binary family produced an arm — and it is a proxy for *last touched*, not for run
time. A post-rebuild `touch` would promote a stale arm; an arm whose content
predates its dir mtime would be misclassified the other way.

So the cutoff class **only ever KEEPs**. Every deletion is by explicit tier-list
membership, reviewed in the dry run. Do not invert this into a "delete everything
older than X" rule.

Process item for the next round: have the runner write the `libWireCellClus.so`
md5 into each arm. `scripts/runners/s4_nuecc48.sh:24` already computes it and
prints it to stdout — writing it into the arm would make the next occurrence
*detectable* instead of inferable.

### Also: the cutoff is a TIMESTAMP, not a date

06:32 is the first clean rebuild. `work-vfnuecc48-vf37c` ran at **06:24** and was
stale-family. A date-granular rule would have misclassified all twelve `vf37`
arms into the clean class — i.e. kept them for the wrong reason and, worse,
offered them as a valid reference.

---

## THE HEAVY ROUND — standing plan, PARTIALLY SUPERSEDED 2026-08-05

> **CORRECTED 2026-08-05 (doc 71 campaign).** Two different things happened to
> the plan below, not one.
>
> **The DAG-ordered hub retirement (H0/H1/H2, the inbound-symlink table) never
> ran as written.** A separate **clean-slate round**, same day, took a
> different path to a similar end state: instead of retiring hubs in DAG order
> while other arms still referenced them, it kept only 5 explicit survivors
> (git-tracked scripts, hand-scan state, the pr/33 knob-off gate pair, one
> non-reproducible doc-28 arm) and retired everything else, including every hub
> named in the table below (`work-mcp1000`, `work`, `work-nuecc48-prod0803`,
> `work-r1ql-f1/f2`, `work-oc19scan-old`) — 233 → 32 → 5 `work-*` dirs across
> the light + clean-slate rounds. The table and DAG are kept below as planning
> record; do not treat them as a log of what happened.
>
> **The "Prerequisites for the re-processing campaign" subsection below DID
> run, and is now DONE** — see **doc 71** for the full account: five samples,
> 1090 events, 100% success, new valfast manifest (521 events), P3
> re-established (both arms PASS), three Bee links. `24 CPUs` below became
> **32** (owner raised the cap before the campaign started). The prerequisite
> edit list below is superseded by doc 71 §"Files touched" — three items
> differ from the guess made here: `frameshift_product`/`-fsproduct` was the
> actual NCpi0 fix (not a flag-only fix — the file needed a NEW jsonnet TLA,
> doc 71 §3), `dqdx_rr_sample/collect_proton_sample.py` was deliberately **not**
> repointed (its CONTROL cross-check root has no successor), and
> `pr37_regate.sh` was already marked historical and correctly left alone.

The 2026-08-05 round was deliberately the *light* half. What it left, and the
conditions for taking it:

**Preconditions.** Note first that *"the re-run's gate passed"* is **not a
checkable condition**: every pre-cutoff arm is stale-binary, `work-pr33-base48`
is a 48-event nueCC arm, and the re-run is 1090 events at a future HEAD with
regenerated imaging and a new sample. There is nothing to gate it against —
**the re-run is a new baseline, not a gated change.**

* **P1** — fresh imaging roots exist, real (not symlinked) npz, expected counts
* **P2** — fresh nusel/QL/PR roots at 1000 / 48 / 19 / 10 / 13, `rc=0`
* **P3** — **a repeat-run A/A′ pair on the clean binary has re-established the
  determinism floor on the widened seven-tree gate**, and both it and the product
  inventory are written into a doc — **DONE 2026-08-05, doc 71 §6: three arms
  (vf0805a/b/c), both matched-layout and cross-layout comparisons PASS,
  47/47 events identical on every gate.**
* **P4** — `find -xtype l | wc -l` == 0 *before* the round
* **P5** — ASSERT 4 passes **with the hub inside the removal set**
* **P6** — archive integrity PASS · **P7** — no live batch, no bokeh viewer

**P3 is owed, and it is the real cost of the vf37 release.** Those twelve arms
were the only A/A′ measurement on the widened gate, and the 2026-08-05 round
deleted them without a successor. The campaign must include a repeat pair — two
arms, same clean binary, no rebuild between, `setarch x86_64 -R`, plus one
ASLR-on leg for the cross-layout question (the `pr37_a2_floor.sh` shape) — or
this tree has no determinism floor at all.

**Order is forced by the symlink DAG** — leaf arms before hubs. **Recomputed
after the 2026-08-05 round, not carried over from the pre-round shape**, because
the round changed it: `work-pr22gap-{a,b,c,input}` were tier A and are gone, and
they were the **only** inbound links to `work-oc19scan-old`. Measured now:

| hub | inbound symlinks | from |
|---|---:|---|
| `work-mcp1000` | **1045** | `work-mcp1kall-d59k` (1000) + `work-oc19scan-old` (45) |
| `work` | 53 | `work-nuecc48-nuf`, `work-oc19scan-old` |
| `work-nuecc48-prod0803` | 48 | `work-nuecc48-0804` |
| `work-r1ql-f1` / `-f2` | 16 / 4 | `work-r1ql-first10` |
| **`work-oc19scan-old`** | **0** | — **no longer a hub**; keep-by-citation only (2 docs) |

```
H0: work-oc19scan-old (0 inbound, retirable NOW -- drops mcp1000 1045 -> 1000)
    work-r1ql-first10  ->  releases work-r1ql-f1/f2
    work-nuecc48-0804  ->  releases work-nuecc48-prod0803
    work-mcp1kall-d59k ->  drops mcp1000 to 0
    work-nuecc48-nuf   ->  drops work/ toward 0
    [re-run ASSERT 4 here -- every H1 target must read 0]
H1: work-mcp1000 (7.0 G)  ->  work (2.8 G)
H2: work-nuecc48-prod0803 + work-vfnuecc48-prod0803;  then work-pr33-*
```

**Re-measure this table before the heavy round rather than trusting it** — the
2026-08-05 round is the proof that a retire round rewrites its own successor's
DAG. The one-liner is in `plan_20260805.py`'s `inbound_targets()`.

`work-mcp10` is **not** retirable — the 10/30-event hand-scan imaging is not in
the re-run's sample list. `work-r1ql-f1/f2` and `work-r2patrec-f1` go only for
whichever MC sample the re-run actually covers (owner 2026-08-05: **both**).

**Hazard at H1 step 8.** `work/` is also the default `SBND_WORK_ROOT`
(`_runlib.sh:18`), so after deletion any bare run silently recreates it. Either
leave an empty `work/` with a README tombstone, or make `_runlib.sh` refuse when
`SBND_WORK_ROOT` is unset.

**The arm move (`arms/pr<NN>/`) belongs here, not in the light round.** Two
reasons: (a) the light round already took the top level to 32 dirs — re-judge
whether the move is still worth it; (b) `tidy_map_20260803.py:97-98` filters to
`isfile or islink`, so **directories are excluded by construction** — the 08-03
tidy suite cannot be reused as-is, and only `tidy_move_20260803.sh` transfers
verbatim. And **do not rewrite the arm-name citations in `docs/`** — M13 protects
the record, and `tidy_docfix`'s rules are script-path shaped so most citations
would be missed anyway. Extend this file's index with a moved-arms table instead.

### Prerequisites for the re-processing campaign (not this round)

Owner decisions 2026-08-05: **all imaging regenerated**; five samples — mcp1k
(1000 data) + nuecc48 (48) + **ncpi0 (19, new)** + r1qlmc (10) + r2mc (13) = 1090
events; 24 CPUs available.

Because imaging is regenerated, the campaign must write to **fresh roots**
(`work-img-<sample>-cb0805`, `work-<sample>-cb0805`). Runner lines that hardcode
an old root and need a new value:

| file:line | what |
|---|---|
| `run_full1k_nusel.sh:43` | `IMGBASE=$SBND_DIR/work-mcp1000` — **hardcoded with no env override**, unlike `TAG`/`ROOT` at `:40-41`. The single most important edit |
| `run_full1k_nusel.sh:6-7` | its *"imaging is NEVER regenerated"* comment becomes false |
| `valfast/run_valfast.sh:77-82` | `pinned_qlroot()` — all four samples |
| `valfast/run_valfast.sh:116-118` | nuecc48 manifest source **and** imaging source both move |
| `scripts/runners/run_pr_geom_arm{,_dl}.sh`, `geom_ab_batch.sh:14` | `work-nuecc48-nuf` |
| `pr37_regate.sh:67`, `dqdx_rr_sample/collect_proton_sample.py:54` | prod0803 / d59k |

Two hazards to fix **before** the campaign:

* **M13** — `_runlib.sh:18` defaults `SBND_WORK_ROOT` to `$SBND_DIR/work`, so any
  imaging invocation that forgets the variable writes on top of 708 existing evt
  dirs (53 inbound symlinks, 503 doc citations). Apply the `refuse_existing()`
  idiom that already exists at `valfast/run_valfast.sh:92-94`.
* **Naming** — `plan_20260803.py:85` classifies `work-<sample>-vf*` as tier V
  (dropped whole, **no archive**). **Forbid the `-vf` infix for production
  roots.** `plan_20260805.py` ASSERT 7 checks this and currently reports one
  survivor matching it (`work-vfnuecc48-prod0803`), which is a legitimate
  long-lived root — but a future round reusing that regex would drop it.

Adding **ncpi0** as a fifth sample costs ~11 case statements / default lists
across `valfast/run_valfast.sh` (`:52`, `:57`, `:59`, `:66-82`, `:83-90`,
`:103-155`) and `valfast/valfast_compare{,_par}.sh`. The comparators
(`vf_scores_diff.py`, `vf_tree_compare*.py`, `nusel_hash_compare.py`) are
sample-agnostic — zero hits. Note the manifest cannot be derived the usual way:
ncpi0 has no row in `docs/pr/11_scores-table.tsv`, and at N=19 the valfast
subsetting has no point — just run all of them. Input is already staged at
`input_files_reco1/nc-sideband_filtered_frameshift.root` (19 data events, runs
18255/18259/18261/18345/18364) and wired to nothing.

Noted, not fixed (pre-existing): **`scripts/runners/s4_nuecc48.sh` is broken** —
`:9` `SRC=$R/work-nuecc48-oc19on` no longer exists and `:21` copies with
`cp -n … 2>/dev/null`, so it would silently seed 48 empty event dirs and run an
arm on nothing.

---

## CLEAN-SLATE ROUND 2026-08-05 — 32 → 5 dirs, 27 arms retired

**STATUS: EXECUTED** (`retire_20260805cs.sh`, wcp-porting-img `01106cd` →
committed here). Took a different path from the DAG-ordered hub retirement the
heavy-round plan above describes: rather than retire hubs in dependency order
while other arms still pointed at them, this round decided the **five
survivors explicitly** — `work-nuecc48-prsmoke2` (3 git-tracked runner
scripts), `work-pr33-base48`/`work-pr33-off48` (the knob-off gate pair, kept
as the interim pre-campaign baseline), `work-stmcamp-d66new` (git-tracked
hand-scan state, M13), `work-tfix388-r9` (doc pr/28 §15.9, not reproducible
from any surviving input) — and retired everything else: 27 arms / archived to
`archive/clean-slate-20260805/`, integrity PASS 27/27. `find -xtype l` == 0
before and after; `du -sh sbnd_xin` and `df /nfs/data/1` both clean
(`scripts/retire/state-20260805cs/removed.tsv`).

Two asserts failed and were discharged before deletion, not bypassed (M13):
three hand-scan label dirs (`work-mcp1kall-d59k/nusel_labels`, `work/ql_labels`,
`work-mcp10/nusel_labels` — 10+3+5 tags) copied verbatim to
`archive/records/labels/`; 351 archive symlinks resolving into `work-mcp10`/
`work-mcp1000` materialized as hardlinks (`cp -al` — the 351 links resolve to
only 40 distinct event dirs, so hardlinking cost 0 extra bytes vs. 1.75 GiB for
byte copies) via `preserve_20260805cs.sh`.

This is the state the 2026-08-05 reprocessing campaign (doc 71, below) built
on: five pre-existing survivors, everything else generated fresh into
`work-img-<sample>/` and `work-<sample>-cb0805/`.

---

## REPROCESSING CAMPAIGN 2026-08-05 — five samples, 1090 events, doc 71

**STATUS: EXECUTED.** Toolkit `a1ea3789`. Imaging → Q/L → tagger tail → PR
chain on **mcp1k (1000) + nuecc48 (48) + ncpi0 (19, new) + r1qlmc (10) +
r2mc (13) = 1090 events, 100% success, 0 failures at any stage.** New valfast
manifest (521 events, `nu_evaluated=1`, replacing the deleted-arm 629-event
one). P3 determinism floor re-established (three arms, both matched- and
cross-layout comparisons PASS). Three Bee links (nueCC48, NCpi0, mcp1k-50).
Full account, repro block, and file-by-file diff list: **doc 71**.

This closes precondition P3 from the heavy-round plan above and supersedes
that plan's "Prerequisites for the re-processing campaign" subsection — see
the CORRECTED blockquote at the top of that section.

---

## RETIREMENT ROUND 2026-08-03 — the pr/23..pr/25 era + valfast, 111 arms, 27 GiB

**STATUS: EXECUTED 2026-08-03 (`CONFIRM=yes ALLOW_LIVE_JOBS=yes
retire_20260803.sh V,1,2`) — 111 dirs / 27 GiB removed, refused=0.**
Post-checks: relink `repaired=0 unresolved=0`; `find . -xtype l` = **0** (it was
**284** before the round — see "the 284" below); no git-tracked deletion;
`work*` 138 → **27** dirs; `sbnd_xin` 55 GB → **28 GB**; `/nfs/data/1` free
485 → **512 GB**. Exhibit check: `scripts/analysis/misc/gapjump_probe.py` on
`work-pr22gap-b/pr_evt386948/mabc-pr.zip` reproduces doc pr/22 §6 exactly
(634 fit pts, 50/634 = 7.9 % uncovered, 33.3 cm across 7 stretches).

State at the start: **138 top-level `work*` dirs, 48 GB**, `/nfs/data/1` at
87 % with 485 GB free — **no disk pressure**; this round was preparation for the
next campaign, not an emergency. The tree regrew from the post-08-02 23 dirs /
19.5 GiB in ~24 hours: docs pr/23, pr/24 and pr/25 plus their valfast gate arms,
the master-merge gate (doc 69) and the test round (doc 70) all ran back to back
and none were retired in flight.

Round tooling (all in `scripts/retire/`, forked from the 08-02 round; state in
`state-20260803/`, lists in `tier{V,1,2}_20260803.txt`). **Do not re-run the
08-02 scripts for a later round** — `plan_20260802.py` hardcodes that round's
survivor list and would treat everything added since (`work-r1ql-*`,
`work-r2patrec-*`, the cath01 pair, `work-mrgB-post`, the live prod0803
campaign) as a removal candidate. Fork instead.

1. **`plan_20260803.py`** — three tiers with **different dispositions** (the
   08-02 round had one), an explicit PROTECTED set, a hard error on any
   unclassified dir, and four safety asserts. All four PASSed: **0** real SP
   frames, **0** `nusel_labels`/`ql_labels`/`decisions*` dirs, **0** git-tracked
   files, and **0** of the 13 029 symlinks outside the removal set resolve into
   it. Every cross-directory edge from a candidate points *outward* into a KEEP
   hub; the big inbound counts (`work-mcp1kall-vfprodoff` 2288,
   `work-nuecc48-poc0` 192) are self-referential.
2. **`lightcheck_20260803.py`** — the blocking pre-flight. **1270/1270** real
   `opflash_apa*.tar.gz` in the removal set are byte-identical to a surviving
   copy: `missing=0 differs=0`, and 0 matches needed the cross-family fallback.
   (The 08-02 round found 8 differing out of 25 112, so a clean sweep was not
   assumed.) It also refuses outright if an exception lands in a DROP-whole
   tier-V arm, which has no archive to fall back on.
3. **`archive_records_20260803.py`** — record layer of the 80-arm ARCHIVE set
   into `archive/records/pr23-25-era-20260803/<group>/<tag>.tar.gz` +
   `.links.txt` + `.manifest.tsv`: **818.4 MiB raw → 362 MB gz**. HEAVY
   (dropped) = pctree / mabc zips / calib / npz / clusters **+ opflash** (per 2).
   Integrity gate — tar members == manifest record count — **PASS 80/80**.
4. **`retire_20260803.sh V,1,2`** — dry run by default. Guards: tier-aware
   archive-present refusal, Bokeh interlock, PROTECTED-in-tier-file refusal, and
   a **new** live-batch interlock (below).

### The 284 — a pre-existing invariant violation this round fixed

`find . -xtype l` was **284**, not 0, when the round started. All 284 were
inside three tier-V roots (`work-nuecc48-vfprodoff` 192, `work-r2mc-vfprodoff`
52, `work-r1qlmc-vfprodoff` 40) — relative links to `evt*` dirs that were never
created there. That made "0 after the round" a *sharper* post-check than
`relink_tags.py`'s own `repaired=0`: a nonzero result would have meant something
outside the plan's model broke. It came back 0.

### Two things the round changed about the tooling

- **The live-batch interlock (new).** A `wire-cell`/runner batch was writing
  into `work-nuecc48-prod0803` throughout, and 26 GB of NFS deletes alongside it
  is exactly M5. The script refuses while such a batch runs, **scoped to
  `sbnd_xin` command lines** — this box is shared and an unrelated user's
  `wire-cell` (one was running out of `/nfs/data/1/xning`) must not be able to
  block our housekeeping. `ALLOW_LIVE_JOBS=yes` overrides; used here because the
  live jobs touched only PROTECTED arms and loadavg was 1.19 on 64 cores.
- **Work in flight is auto-PROTECTED.** `work-pr116962-nocosmicveto` appeared
  *during* the round, created by a runner reading `work-nuecc48-prod0803`. So an
  unclassified dir is not necessarily a classification bug. Rule now: unclassified
  **and** touched within `RETIRE_FRESH_HOURS` (default 6) ⇒ auto-PROTECT and say
  so loudly; unclassified and stale ⇒ hard error, classify by hand.

### PROTECTED — 3 dirs, never listed, never walked

`work-nuecc48-prod0803` and `work-vfnuecc48-prod0803` (the owner's 2026-08-03
campaign, named explicitly so no glob change can pull them in), plus the
auto-protected `work-pr116962-nocosmicveto`.

**Add to this list next round: the 2026-08-04 arms below.** They are the
current old-vs-new pair with prod0803 and must not be retired while prod0803 is
protected — a baseline with no counterpart is not a comparison.

### 2026-08-04 — the nueCC48 re-processing round *(docs pr/28 §16, pr/29 §14)*

| dir | GiB | what |
|---|---|---|
| `work-nuecc48-0804` | 0.33 | clustering + Q/L hub at toolkit `6206c46b`. **`evt<ID>/` are symlinks into `work-nuecc48-prod0803`** — imaging was not re-run (config-inert, and the 96/96 hash gate in pr/28 §16.3 proves the QL products are identical anyway). Retiring prod0803 would gut this dir. |
| `work-vfnuecc48-0804` | 0.17 | PR arm, **production** (bare). The "new" side of the owner's Bee pair. |
| `work-vfnuecc48-0804-rep` | 0.17 | byte-for-byte repeat of the above — the noise-floor arm. **0/48 events differ**; keep it, it is the evidence that every other number this round is attributable. |
| `work-vfnuecc48-0804-pr29off` | 0.17 | `SBND_STEINER_{WIRE_TOL,ADJ_SLICE,EDGE_DEAD_MIX}=0` — the pr/29 attribution arm. |

Bee assets: `bee/nuecc48-0804/nuecc48_0804.{zip,index.txt,prid-map.txt,url}`.
The index map `diff`s clean against `bee/nuecc48-prod0803/nuecc48_prod0803.index.txt`,
so Bee index *n* is the same event in the old and new sets.

### KEEP — 24 dirs, 20.2 GiB

BASE/HUB `work`, `work-mcp10`, `work-mcp1000`, `work-mcp1kall-d59k` (18.6 GiB,
never touched); the pr/22 exhibit chain `work-oc19scan-old` +
`work-pr22gap-{a,b,c,input}`; `work-mcp1kall-cath01` + `work-nuecc48-cath01`
(pr/12); `work-nuecc48-{base,nuf,prsmoke,prsmoke2}`; `work-r1ql-*` +
`work-r2patrec-*` (doc 67); the git-tracked `work-stmcamp-d66new` label stub;
and `work-mrgB-post`.

**`work-mrgB-post` is held deliberately** (168 MB) — it is the current-production
48-event baseline until `work-nuecc48-prod0803` completes, at which point
prod0803 supersedes it. Revisit next round.

### TIER V — valfast, 34 dirs, 20.19 GiB — DROPPED whole, no archive

`valfast/README.md` states the contract: *"valfast arms are transient. Record
the `valfast_compare.sh` summary (with tags) in the round doc, then DELETE the
`work-vf*-<tag>` and `work-*-vf<tag>` roots."* Every arm's compare summary is in
docs pr/23, pr/24 or pr/25. Largest: `work-mcp1kall-vfprodoff` 4.9 GB, then
eight ~1.68 GB `work-vfmcp1k-*` arms.

The old production baseline pair `work-vfmcp1k-prod{off,on}` (3.4 GB) went with
them, on the owner's 2026-08-03 call: the pr/24 `iso_endpoint` and pr/25 trio
defaults flipped ON that day, so as an A-side it was already pre-flip and stale.

**Exception — 3 arms were ARCHIVED instead of dropped**, because a citation scan
across `docs/`, `valfast/`, `*.py`, `*.sh` found **zero** references, so their
gate result existed nowhere else: `work-vfmcp1k-pr24i0` (1123 MB),
`work-vfnuecc48-pr24r3a` (71 MB), `work-vfmcp1k-pr24r3a` (49 MB).

### TIER 1 — docs pr/23–pr/25, 73 dirs, 6.27 GiB — archived, then removed

All three campaigns are CLOSED and **shipped with the SBND production default
ON** (pr/23 §9 flip 2026-08-02; pr/24 `iso_endpoint` 2026-08-03; pr/25 all three
2026-08-03).

| group | dirs | GiB | what it was |
|---|---|---|---|
| `pr25` | 22 | 4.26 | doc pr/25 cathode-rejoin / TGM-veto / shower-topo gates, incl. the two 1.66 GB `pr25s3r2-{dbgall,on50b}` arms |
| `poc48` | 6 | 1.26 | the pr/23+24 48-event PR baseline hub `work-nuecc48-poc0` + the `poc48*` protect-over-clustering arms |
| `pr23` | 24 | 0.60 | doc pr/23 protect-over-clustering pilot / cathode / v1 arms + the two `mcp1kall-pr23*` subsets |
| `pr24` | 21 | 0.16 | doc pr/24 isochronous-shower-trunk rounds a/b/c, r2 and r3 incl. the flip arms |

`work-nuecc48-poc0` was cited by three docs and was the 48-event hub, but it is
superseded by `work-nuecc48-prod0803` — a fresh run over the same manifest at
current defaults, fully self-contained (48 of its own SP frames, 100 self-links,
no outward dependency on poc0).

### TIER 2 — merge / test gate arms, 4 dirs, 0.34 GiB — archived, then removed

`work-mrgA-pre`, `work-mrgdet-r1`, `work-mrgdet-r2` (doc 69 master merge) and
`work-d70-eb` (doc 70 test round). Both gates are recorded in their docs.

### What survives, what is lost

**Survives**: every doc-quoted number (tsv, logs, `tracking-*.root` are in the
record tarballs), all 1270 light files (proven byte-identical to surviving
copies), all SP frames (none were ever in the removal set), and doc-table
re-checkability.

**Lost**: pctree/Bee-level re-analysis of these arms — the same class of loss as
the two prior rounds, and permanent, since a tag names a *config*, not a build
(see "These arms are not reproducible" above). For tier V it is total: those 31
arms leave no record layer at all, by the valfast contract.

### Totals

| | dirs | GiB |
|---|---|---|
| start | 138 | 48 (du) |
| KEEP | 24 | 20.2 |
| PROTECTED | 3 | ~1.0 and growing |
| TIER V dropped | 34 | 20.19 |
| TIER 1 archived + removed | 73 | 6.27 |
| TIER 2 archived + removed | 4 | 0.34 |
| archive added | — | +0.35 |
| **sbnd_xin after** | **27 work\*** | **28 GB total incl. `archive/` 4.2 GB** |

---

## RETIREMENT ROUND 2026-08-02 — the pr/11..pr/22 era, 231 arms, 127 GiB

**STATUS: EXECUTED 2026-08-02 (`CONFIRM=yes retire_20260802.sh 1`) — 231 dirs
/ 135 GiB removed, refused=0.** Post-checks: relink repaired=0 unresolved=0;
`find . -xtype l` = 0; no git-tracked deletions; `scripts/analysis/misc/gapjump_probe.py` on
`work-pr22gap-b/pr_evt386948/mabc-pr.zip` reproduces doc pr/22 §6 exactly
(634 fit pts, 50/634 = 7.9 % uncovered, 33.3 cm across 7 stretches) — the
materialized exhibits are faithful.

State at the start: **254 top-level `work*` dirs, 155.1 GiB** (`du` 158.8 GB;
sbnd_xin 160 GB total), `/nfs/data/1` at 90 %. The tree regrew from the
post-2026-07-30 20 GB in ~62 hours (07-31 → 08-02): the doc pr/11–pr/22
campaigns ran roughly ten back-to-back generations of validation arms and
none were retired in flight. Eleven ~8.5 GB full-chain 1000-event arms alone
(`u17on1k(b)`, `cbron/off1k`, `vveto1k`, `isog1k`, `oc19on1k`, `cathA12*`,
`pi5cens`) hold 83 GiB. Everything from `rescue01` onward was never indexed
in this file — the tier table below is its only documentation.

Round tooling (all in `scripts/retire/`, forked from the July round;
state + tier list in `scripts/retire/state-20260802/` and
`tier1_20260802.txt`):

1. **`materialize_20260802.sh`** — made `work-oc19scan-old` self-contained so
   the doc pr/22 exhibits (`work-pr22gap-{a,b,c,input}`) survive: 10 `ql_evt*`
   symlinks into removal-set hubs replaced by `cmp`-verified copies (inner
   npz links repointed to their `readlink -f` targets in `work-mcp1000`/`work`)
   and `evt444187` repointed to its physical target `work/evt444187`.
   Executed 2026-08-02: repoint=1 copy=10 fail=0, 0 broken links after.
2. **`plan_20260802.py`** — survivors = the documented KEEP set + the pr/22
   exhibit chain; removal set = the other **231 dirs, 133.9 GiB real bytes**
   (owner decision: ALL pr-era arms retire, incl. the four pr11v3 census
   arms). Dangling-link dry run walks every symlink outside the removal set
   (12 837): **0** point into it. SP-data safety scan found 144 real
   `sp-frames.tar.bz2` in `work-nuecc48-{cathA12off,cathA12on,pi5wm}` — all
   144 verified byte-identical to the surviving `work/evt*` copies.
3. **`lightcheck_20260802.py`** — proves the round may DROP (not archive)
   `opflash_apa*.tar.gz` (new in this round's HEAVY class; the July round
   archived them): of 25 112 SP/light files in the removal set, 25 104 are
   byte-identical to surviving copies (hubs `d59k`/`nuf`/BASE); the **8**
   that differ (unique light variants in `work-cbr-det{1,2}`,
   `work-oc444187-{off,trace}`, evts 437699/444187) are force-ARCHIVED via
   `state-20260802/light_exceptions.txt`.
4. **`archive_records_20260802.py`** — record layer of all 231 arms into
   `archive/records/pr-era-20260802/<group>/<tag>.tar.gz` + `.links.txt` +
   `.manifest.tsv`: **6804 MiB raw → 2.1 GiB gz**. HEAVY (dropped) =
   pctree/mabc zips/calib/npz/clusters **+ opflash** (per 3). Integrity gate:
   tar members == manifest records, **159 251 == 159 251, 231/231 arms**.
   No `nusel_labels`/hand-scan/decision dir exists in any removal candidate
   (verified); the only labels under `work*` are in KEEP dirs and the
   `work-stmcamp-d66new` git-tracked stub.
5. **`retire_20260802.sh 1`** — dry run: **231 dirs, 135 GiB (du), refused=0**.
   Same guards as the July script (refuse-without-archive, Bokeh interlock,
   post-checks incl. `git status` for deleted tracked files).

### KEEP — 23 dirs, ~19.5 GiB

The 15 dirs of the July KEEP table, plus `work-mcp1kall-cath01` +
`work-nuecc48-cath01` (added 2026-08-01, doc pr/12), the
`work-stmcamp-d66new` label stub, and the pr/22 exhibit chain
`work-oc19scan-old` (37 MB, now self-contained) + `work-pr22gap-{a,b,c,input}`
(13 MB, cited by `docs/pr/22_track-fit-gap-jumping.md`).

### TIER 1 — 231 dirs, 133.9 GiB real (135 GiB du)

All campaigns are CLOSED (docs pr/11–pr/22 shipped/pushed). Grouped as in
`archive/records/pr-era-20260802/`; full list `scripts/retire/tier1_20260802.txt`.

| group | dirs | GiB | what it was |
|---|---|---|---|
| `pr11-census` | 20 | 7.5 | doc pr/11 1071-event population census v1→v3 + the crash-fix arms (`all73*`, `failfix`, `badallocfix`, `*-fix`) incl. the four `pr11v3` reference arms |
| `pr11-audit` | 46 | 1.6 | doc pr/11 latent-pattern audit + determinism/DL arms (`ab30*`, `audit*`, `det*`, the 21 single-event `469665`/`389538`/`52672` repeats) |
| `cath13-ccfeat` | 10 | 5.1 | docs pr/13–14 cathode-crossing Bee sets, `cath13` Q/L arms, `ccfeat300*` connector-feature census |
| `rescue01` | 4 | 0.1 | doc pr/14 cathode-bundle-rescue gate arms |
| `cbr` | 32 | 17.6 | docs pr/14+17 cathode-bundle-rescue 1k census (`cbron/off1k`) + the 16 `cbr286191*`/`cbr56463*` determinism probes |
| `vveto` | 4 | 8.7 | doc pr/15 separate() vertex_veto 1k census + `vv*rr` repeats |
| `nsc` | 6 | 0.6 | doc pr/16 nu_skip_cosmic size-guard arms (`nscon/off/base/rep`) |
| `isog-u17` | 26 | 27.8 | doc pr/17 unmerge (`u17*` incl. the two 8.5 GB 1k hubs) + isolated-grouping arms (`isog*`, `iso10550*`) |
| `nbl` | 5 | 0.5 | doc pr/18 iso-band nu guard arms (`nbl15`, `nbloff`, `nblrep`) |
| `oc19` | 13 | 9.5 | doc pr/19 isolated-absorb (`oc19*`, `oc444187-*`) + `work-oc19scan-new` (the OLD scan dir is KEEP) |
| `cathA12-b0` | 27 | 32.6 | doc pr/20 Part II: `cathA12*` A1/A2 census (three 8.5 GB 1k arms) + `b0*` cathode-kink-veto gates |
| `pi-partI` | 30 | 22.1 | doc pr/20 Part I: `pi0..pi5` demoted-main census/gates incl. the 8.5 GB `pi5cens` and four 2.7 GB `pi5cens-pr*` arms |
| `pr20x` | 5 | 0.04 | doc pr/20 Part X production-default determinism arms |
| `probes` | 3 | 0.1 | `d68smoke` (doc 68), `nuecc48-probe`, `rpg-ab31` |

**Survives removal**: every doc-quoted number (tsv, logs, `tracking-*.root`
are in the record tarballs), the 8 unique light files, and doc-table
re-checkability. **Lost**: pctree/Bee-level re-analysis of these arms (the
same class of loss as the July round; arms are not reproducible — a tag
names a config, not a build). The `pr11v3` retirement additionally idles
`scripts/analysis/pr11/pr11_br_filled_census.py`, `scripts/analysis/cathode/cathode_nu_census.py` and `scripts/analysis/misc/stub_census.py`
until pointed at a future census arm.

### Totals (final, post-execution)

| | dirs | GiB |
|---|---|---|
| start | 254 | 155.1 real (158.8 du) |
| KEEP | 23 | ~19.5 |
| TIER 1 removed | 231 | 133.9 real (135 du) |
| archive added | — | +2.1 |
| sbnd_xin after | 23 work* | 26 total incl. archive (transient `work-vf*` A/A′ arms deleted separately per the valfast disposal rule) |

---

## RETIREMENT ROUND 2026-07-30 — 134 arms REMOVED, 35.9 GiB reclaimed

State at the start of the round: **149 top-level `work*` dirs, 54.9 GiB of real
bytes** (`du` says 56 GB; the difference is directory overhead — 208499 entries
under `work*`). `sbnd_xin` as a whole was 58.5 GB (60 GB after the archive was
written); `/nfs/data/1` was 87 % full, 481 GB free.

The round was **archive-then-remove**: the record layer of every retiring arm
was first copied into `archive/records/` (additive — nothing under `work-*` was
moved or rewritten), the removal list was reviewed, and then
`CONFIRM=yes scripts/retire/retire_20260730.sh 1,2` deleted tiers 1+2 on the
owner's approval. The script refuses to delete any arm whose `<tag>.tar.gz` is
not present in the archive, and refuses to run at all while a `bokeh serve`
viewer is up.

One arm survives as a stub: `work-stmcamp-d66new/nusel_labels/d66flip/` is
**git-tracked** (22 label json force-added past the `*.json` ignore rule), so
`git checkout` restored it in place after the removal — the directory now holds
nothing but those 152 K of hand-scan labels. No other removed arm held a tracked
file (`git status` showed 22 deletions, all of them that one dir).

**Result** (`scripts/retire/retire_20260730.sh 1,2`, `CONFIRM=yes`):
134 dirs removed, 0 refused; `relink_tags.py` dry run `repaired=0
unresolved=0`; `find . -xtype l | wc -l` = **0**; `work*` 149 dirs / 56 GB →
**15 dirs + the d66new label stub / 20 GB**, `sbnd_xin` 60 GB → **24 GB**; `/nfs/data/1` free
481 GB → **517 GB**. SP + light after the round: 6158 files / 1765 MB, intact.

### What was archived, and what removal costs

`archive/records/` (731 MB gz, 1587.9 MiB raw, 68856 files, README there) holds
per arm: a `<tag>.tar.gz` of every real file **except** `pctree-*.tar.gz`,
`mabc*.zip`, `calib-evt*.json`, `*.npz`; a `<tag>.links.txt` symlink map; a
`<tag>.manifest.tsv` of kept-vs-dropped bytes; and — verbatim as directories,
never tarred — the ten `nusel_labels/` hand-scan record dirs that live inside
removal candidates:

`work-mcp10-{d49son,d52on,d52ron,d55ton,d56bw}`,
`work-mcp1000-{d55ton,d56bw}`, `work-mcp1000b-{d55ton,d56bw}`,
`work-stmcamp-d66new` → `archive/records/labels/<tag>/nusel_labels/`.

Integrity gate: tar member count == manifest record-file count, 68856 == 68856,
all 134 arms.

**Survives removal**: doc-table re-checkability. Every number the docs quote
from these arms comes from `nusel-evt*.tsv`, the run logs or `tracking-stm.root`
— `scripts/analysis/stm/bwgate_report.py`, `scripts/analysis/stm/d60_ab_report.py`, `scripts/analysis/stm/d66_flip_report.py`,
`scripts/analysis/stm/d66_proton_sweep.py`, `scripts/perf/p54_ab_report.py`, `scripts/analysis/misc/mabc_step_totals.py`,
`scripts/analysis/stm/stmon_stats.py` read only those.

**Lost on removal**, precisely — the loss depends on whether the arm re-ran the
Q/L stage or shared it:

- **91 of the 134 arms symlink their `ql_evt*` into `work-mcp1kall-d59k` or
  `work-mcp1000`** (every `stmcamp` and `d60` arm). For those, the Q/L-side
  products — `mabc-all-apa.zip`, the per-face Bee zips, the Q/L pctrees,
  `opflash_apa*.tar.gz`, `calib-evt*.json` — **survive in the kept hub**. What
  goes is only the PR side: `nusel_evt*/pctree-pr-evt*.tar.gz` and
  `nusel_evt*/mabc-pr.zip`.
- **43 arms own their `ql_evt*`** (the 10-event `mcp10`/`mcp1000`/`mcp1000b`
  `d52*`/`d53*`/`d55*` arms plus `trace51`, `m66*sb`, `d55pv` — 371 Q/L Bee
  zips). Those re-ran clustering, so their Q/L products are unique and go too.

So after removal `scripts/analysis/stm/stm_fv_census.py`, `scripts/analysis/misc/unmerge_crosser_audit.py`,
`scripts/analysis/stm/stm_main_connectivity.py` and `nusel_extract.py`'s archive mode cannot be
re-run against any removed arm, and the scan viewer cannot display one.
Combined with "these arms are not reproducible" above, removal is permanent:
the doc's stated numbers, the tsv/logs/`tracking-stm.root` and the labels become
the only surviving record.

### SP and light data are untouched

The owner's one constraint. SP = `sp-frames.tar.bz2` and
`sbnd-sp-frames-anode{0,1}.tar.bz2`; light = `opflash_apa{0,1}.tar.gz`. Both
live in the BASE `evt*` / `ql_evt*` dirs (`work`, `work-mcp1000`, `work-mcp10`
— 4062 files, 1752 MB) and in the kept hub `work-mcp1kall-d59k` and the current
`work-nuecc48-*` arms. **No removal candidate holds an SP frame at all**, and
the per-arm `opflash_apa*.tar.gz` copies that some 30-event arms carry are
included in the archive tarballs, so no light product is lost either.
`input_files`, `input_files_reco1/` (1.7 GB) and `scan-d59k/` are not in scope.

### Dangling-link dry run — 0

The scar this file documents (1536 broken links, `scripts/analysis/stm/stm_fv_census.py` silently
reporting 0 instead of 147) was checked mechanically, not argued: every symlink
under every **surviving** dir (`work`, `work-mcp1000`, `work-mcp10`,
`work-mcp1kall-d59k`, the `work-nuecc48-*` / `work-r1ql-*` / `work-r2patrec-*`
arms, plus `archive/`, `scan-*`, `nusel_display/`, `ql_scan/`, `docs/`,
`stm_campaign/`, `bee-*`, `showcase-*`) was resolved and none points into the
removal set. The removal set is closed under the dependency graph: the only
in-set arms with dependents are `work-mcp10-d55ton`, `work-mcp1000-d55ton`,
`work-mcp1000b-d55ton` (11 dependents each) and `work-mcp10-d49son` (1), and
every one of those dependents is itself in the set. After deletion, run
`python3 relink_tags.py` and confirm `find . -xtype l | wc -l` is 0 anyway —
`retire_20260730.sh` does both.

### KEEP — 15 dirs, 19.05 GiB (all that remains)

| dir | size | why |
|---|---|---|
| `work` | 2792 MB | BASE: data-sample imaging + **SP frames** + light + `ql_labels/` |
| `work-mcp1000` | 7127 MB | BASE: 1000-event MC imaging + SP frames; 14372 inbound links |
| `work-mcp10` | 96 MB | BASE: 10/30-event hand-scan set + `nusel_labels/` |
| `work-mcp1kall-d59k` | 8383 MB → **5.9 GB** | HUB + LIVE: doc 59 production scan (`s59k`, labels), **18462 inbound links** — every `stmcamp`/`d60` arm's `ql_evt*` is a symlink into it. ~~Its 2.5 GiB of `calib-evt*.json` is the largest non-BASE block deliberately not touched~~ **SUPERSEDED: those 1000 calib dumps (2.43 GiB) were DELETED in the 2026-08-03 tidy round** — see "TIDY ROUND" below for what that costs |
| `work-nuecc48-{base,nuf,prsmoke,prsmoke2}` | 745 MB | CURRENT: the 48-event Lynn nueCC campaign behind docs `pr/1`–`pr/10` |
| `work-r1ql-{f1,f1-nobw,f2,f2-nobw,first10}` | 173 MB | CURRENT: round-1 Q/L arms (doc 67), created 2026-07-30 |
| `work-r2patrec-{f1,f1-nobw}` | 191 MB | CURRENT: round-2 pattern-rec arms (doc 67), created 2026-07-30 |

Optional additions the owner may want to retire too, listed but **not** in the
tiers: `work-nuecc48-base` (151 MB, the partial earlier arm superseded by
`-nuf`) and `work-nuecc48-prsmoke` (8 MB, superseded by `prsmoke2`).

### TIER 1 — REMOVED 2026-07-30: 125 dirs, 25.14 GiB

Campaigns that shipped and closed. Full per-dir listing with sizes:
`scripts/retire/tier1.txt`.

| group | dirs | size | status |
|---|---|---|---|
| doc-63 STM improvement rounds — `work-stmcamp-{r0,r1,r1b,r2,r2full,r2fullb,r3full,r3fullb,r4afull,r4bfull,r5full,r5fullb,r5fullc,r5off,r5offb,r5offc,r1off,r2off,r3off,r3offb,r4aoff,r4boff,d64tf,d64lt,d64smoke}` | 25 | **20.30 GiB** | doc 63 SHIPPED + default ON, closed. Eight near-duplicate 883/1000-event `*full` arms at 2.3 GiB each are 19.5 GiB of the total |
| doc-60 TrackFitting single-point abort — `work-mcp1kall-d60{base,bw1,bw2,sr1,sr2,sfix,nr1,nr2,nfix,fix,fixchk,crash}` | 12 | 2.09 GiB | doc 60 FIXED + pushed (`2a821fd2`); determinism repeats and gate arms |
| docs 52–57 30-event arms — `work-mcp{10,1000,1000b}-{d49son,d52*,d53*,d55*,p54*,p55opt,p56off,d56bw,d57mip*,m66*,p65fin}`, `work-mcp10-{trace51,d52chk,d52trace,d53leg,m66*sb}`, `work-smoke-d55pv` | 78 | 2.67 GiB | docs 52/53/54/55/56/57/65 all closed; includes the four `nusel_labels` arms (labels archived) |
| `work-stmcamp-dbg1..9` | 9 | 0.08 GiB | ad-hoc debug probes of the doc-63 campaign |

### TIER 2 — REMOVED 2026-07-30 (owner approved): 9 dirs, 10.76 GiB

The doc-66 diffusion-revert campaign (`work-stmcamp-d66{old,new,fix,fixoff,oldtrace,newtrace,newtrace0,newtrace0b,newtrace5}`; list in
`scripts/retire/tier2.txt`). Closed and shipped like tier 1, but two reasons to
pause before deleting:

- `d66fix` / `d66fixoff` are the validation **pair** for the doc-66 §12 STM cut
  package (toolkit `c0501d7e`) which is **currently default ON**. If that
  default ever has to be re-validated at pctree level, this pair is the arm that
  did it.
- `d66new` is the shipped-revert arm and carries the largest surviving
  `nusel_labels/` (148 K, archived).

Keeping the `d66fix`/`d66fixoff` pair whole would have cost 5.27 GiB; the owner
chose to remove all nine (10.76 GiB). Their record layer — including `d66new`'s
148 K `nusel_labels/` — is in `archive/records/doc66-diffusion/` and
`archive/records/labels/work-stmcamp-d66new/`.

### TIER 3 — optional, not scripted: ~0.9 GiB

The three existing `archive/` campaign trees still hold their heavy layer:
`stm-docs40-49` 553 MB, `tgm-docs29-39` 229 MB, `aborted-d54` 132 MB of
pctree/mabc/calib/npz against 137 MB of records. Applying the same record-only
rule to them reclaims ~0.9 GiB. Not scripted here because they were already
curated once (2026-07-25) with the whole-directory convention.

### Totals

| | dirs | GiB |
|---|---|---|
| start | 149 | 54.9 |
| KEEP | 15 | 19.05 |
| TIER 1 | 125 | 25.14 |
| TIER 2 | 9 | 10.76 |
| archive added | — | +0.71 |
| **after tiers 1+2 (actual)** | **15** | **19.05** (`work*` 20 GB by `du`; sbnd_xin 24 GB incl. `input_files_reco1` 1.7 GB, `scan-d59k` 694 MB, `archive/` 1.8 GB) |

---

*Sections below describe the state at the 2026-07-25 consolidation. The BASE /
LIVE / CURRENT tables are superseded by the KEEP and TIER tables above; the
`archive/` and RETIRED tables remain current.*

## BASE — 3 dirs, 10026 MB (as of 2026-07-25; still current, see KEEP above)

**base input** — the imaging / PR products every tagged arm links into. Never delete: regenerating `work-mcp1000` alone is a 2000-event imaging run.

| dir | entries | size | referenced by |
|---|---|---|---|
| `work` | 715 | 2795M | — |
| `work-mcp10` | 63 | 96M | — |
| `work-mcp1000` | 2000 | 7136M | — |

## LIVE — 7 dirs, 8.5 GB (as of 2026-07-25 — SUPERSEDED, retained for the "referenced by" columns)

> Currency warning: this table's "live" claims are from 2026-07-25. Every arm
> listed here except `work-mcp1kall-d59k` was **removed** on 2026-07-30 (tiers
> 1/2 above); its record layer is in `archive/records/`. Use the KEEP table for
> what exists; use this table only for the per-dir reference lists.

**wired into a running viewer** — the port-5011 `nusel_scan_viewer.py` command line names these as its current tag or as a `--prev` baseline. Deleting or moving one blanks the live scan.

The doc-56 `work-*-d56bw` arms are also live as `--prev` baselines of the doc-59
scan; they are listed under CURRENT below.

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-mcp1kall-d59k` | 2999 | 8.3G | `59_full1k-production-scan.md`, `scripts/analysis/misc/nusel_scan_filter.py`, `run_full1k_nusel.sh`, `scripts/bee/make_scan_bee.sh` — the port-5011 `s59k` scan (648 of its 999 tables) |
| `work-mcp1kall-d60crash` | 9 | 88K | `60_trackfitting-single-point-abort.md` — 1-event repro root for the evt 278794 abort (entry 618 only; only the pctree *tarball* is symlinked in, never the `ql_evt278794` dir, so a from-scratch Q/L rerun cannot write into the d59k record) |
| `work-mcp1kall-d60base` | 2728 | 1.2G | doc 60 §7 — pre-fix PR-only re-run of entries 0-430 + 618, used as the pinned determinism arm vs `d59k`. **Bee zips carry `runNo="0"`**: its `ql_evt*` hold only the pctree tarball, so `nusel_extract.py` could not run (rc=1 on every entry by construction, not a failure) — compare it `--archives-only` |
| `work-mcp1kall-d60nr1` / `-d60nr2` | 102 | 47M each | doc 60 §7 — two **un-pinned** (no `setarch`) repeats, entries 0-19, production config |
| `work-mcp1kall-d60sr1` / `-d60sr2` | 302 | 170M each | doc 60 §7 — two un-pinned repeats over the 60 STM-tagged entries; `d60sr1` doubles as the pre-fix arm of §6 gate 1 |
| `work-mcp1kall-d60bw1` / `-d60bw2` | 302 | 198M each | doc 60 §7 — two un-pinned repeats of the same 60 events with **pre-doc-56 `-no-bwonly`** (146 STM / 256 TGM tags), and the negative control against `d60sr1` |
| `work-mcp1kall-d60sfix` | 302 | 170M | doc 60 §6 gate 1 — **post-fix** arm, 60 STM-tagged events, byte-identical to `d60sr1` |
| `work-mcp1kall-d60nfix` | 102 | 47M | doc 60 §6 gate 2 — **post-fix** arm, entries 0-19, byte-identical to `d60nr1` |
| `work-mcp1kall-d60fixchk` | 5 | 2.0M | doc 60 §6.1 — evt 278794 with the fix in: `rc=0`, 8-bundle table, in-beam bundle tagged STM |
| `work-stmcamp-d66old` / `-d66new` | 1000 events each | — | `66_diffusion-revert-validation.md`, `55_dqdx-vs-rr-three-bundles.md` §12, `scripts/analysis/stm/d66_flip_report.py` — the diffusion A/B: `d66old` = `DL/DT` 6.5781/13.1349, `d66new` = 4.0/8.8 (the shipped revert). **Same binary, same d59k pctrees, differing only in the runtime fit JSON** — arm identified by `SBND_TRACKFIT_JSON` and recoverable from each event log's `trackfitting_config=` line. Both 1000/1000 `rc=0`. Built with `stm_campaign/run_round.sh` + `STM_EVENTS`, so they carry the `work-stmcamp-` prefix despite being the full 1000-event manifest |
| `work-stmcamp-d66oldtrace` / `-d66newtrace` / `-d66newtrace0` / `-d66newtrace0b` / `-d66newtrace5` | 6 / 6 / 141 / 13 / 9 events | — | `66_diffusion-revert-validation.md` §12, `scripts/analysis/stm/d66_proton_sweep.py` — TRACE-level (`SBND_WCT_LOGLEVEL=trace`) reruns for the STM cut-fixability study: the 6 scan-mistake events in both diffusion arms, every event with an accepted-STM (status-0) bundle, the torn-log redo, and the 9 proton-vetoed (status-5) events. Same arms as `d66old`/`d66new`, extra logging only — statuses verified identical. detect_proton TRACE lines must be read from the batch stderr sink `.log_<evt>.log` (the per-event file sink tears them deterministically) |
| `work-stmcamp-d66fixoff` / `-d66fix` | 1000 events each | — | `66_diffusion-revert-validation.md` §12.5 — validation arms for the doc-66 §12 STM cut package (toolkit `c0501d7e`): `d66fixoff` = package OFF (`-no-stm-d66cuts`, the byte-identical gate vs `d66new`, PASS all 1000), `d66fix` = package ON (production default; exactly the 4 target STM flips, plus 2 tsv-only `stmfit`-column diffs from log tearing — pctrees identical). Same binary and d59k inputs as `d66new` |
| `work-mcp10-d49son` | 43 | 29M | `50_stm-fit-scope-and-unmerge.md`, `51_clustering-merge-attribution.md`, `52_isolated-grouping-fix-design.md`, `scripts/analysis/stm/d52_ab_report.py`, `scripts/analysis/stm/stm_main_connectivity.py`, `scripts/analysis/stm/stm_merge_attribution.py` |
| `work-mcp10-d52ron` | 53 | 60M | `52_isolated-grouping-fix-design.md`, `53_unmerge-vs-cathode-crossers.md`, `scripts/analysis/misc/unmerge_crosser_audit.py` |
| `work-mcp1000-d49son` | 32 | 23M | `50_stm-fit-scope-and-unmerge.md`, `51_clustering-merge-attribution.md`, `scripts/analysis/stm/d52_ab_report.py`, `scripts/analysis/stm/stm_main_connectivity.py` |
| `work-mcp1000-d52ron` | 30 | 46M | `52_isolated-grouping-fix-design.md`, `53_unmerge-vs-cathode-crossers.md`, `scripts/analysis/misc/unmerge_crosser_audit.py` |
| `work-mcp1000b-d49son` | 32 | 23M | `50_stm-fit-scope-and-unmerge.md`, `51_clustering-merge-attribution.md`, `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp1000b-d52ron` | 30 | 44M | `52_isolated-grouping-fix-design.md`, `53_unmerge-vs-cathode-crossers.md`, `scripts/analysis/misc/unmerge_crosser_audit.py` |

## CURRENT — 52 dirs, 2109 MB (as of 2026-07-25 — SUPERSEDED, retained for the "referenced by" columns)

> Currency warning: every arm in this table was **removed** on 2026-07-30
> (TIER 1 above) except the `work-nuecc48-*` roots at the end, which are KEEP.
> Records in `archive/records/docs52-57-arms/`.

the campaigns still in flight: docs 52 (isolated grouping) and 53 (`real_cluster_id`), plus the `d55b`/`d55t` arms of doc 52 §13, the doc-54 perf A/B arms and the doc-56 beam-window-gate arms (`p56off` knob-off gate, `d56bw` = the new production default, served on :5011).

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-mcp10-d52chk` | 12 | 4M | `52_isolated-grouping-fix-design.md` |
| `work-mcp10-d52off` | 52 | 60M | `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp10-d52on` | 53 | 60M | `52_isolated-grouping-fix-design.md`, `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp10-d52roff` | 52 | 60M | `52_isolated-grouping-fix-design.md` |
| `work-mcp10-d52rpoff` | 52 | 60M | `52_isolated-grouping-fix-design.md` |
| `work-mcp10-d52trace` | 2 | 2M | `52_isolated-grouping-fix-design.md` |
| `work-mcp10-d53beeoff` | 52 | 60M | `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp10-d53beeon` | 52 | 60M | `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp10-d53dflt` | 52 | 60M | `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp10-d53leg` | 30 | 30M | `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp10-d53off` | 52 | 60M | `52_isolated-grouping-fix-design.md`, `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp10-d53on` | 52 | 60M | `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp10-d53r` | 52 | 60M | `52_isolated-grouping-fix-design.md` |
| `work-mcp10-d55boff` | 52 | 60M | — |
| `work-mcp10-d55bon` | 52 | 60M | — |
| `work-mcp10-d55toff` | 52 | 60M | — |
| `work-mcp10-d55ton` | 53 | 60M | — |
| `work-mcp10-p54base` | 30 | 30M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp10-p54opt` | 30 | 30M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp10-p55opt` | 30 | 30M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp10-p56off` | 30 | 30M | `56_beam-window-tagger-gate.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp10-d56bw` | 30 | 25M | `56_beam-window-tagger-gate.md`, `scripts/analysis/stm/bwgate_report.py`, `scripts/analysis/misc/mabc_step_totals.py`, `nusel_display/serve_nusel_scan.sh` |
| `work-mcp10-p65fin` | 30 | 26M | `65_tgm-stm-perf-final.md`, `scripts/analysis/misc/mabc_step_totals.py`, `scripts/perf/profile_pr65.sh` |
| `work-mcp10-trace51` | 6 | 36M | `51_clustering-merge-attribution.md`, `scripts/analysis/stm/stm_merge_attribution.py` |
| `work-mcp1000-d52off` | 30 | 47M | `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp1000-d52on` | 30 | 47M | `52_isolated-grouping-fix-design.md`, `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp1000-d52roff` | 30 | 47M | `52_isolated-grouping-fix-design.md` |
| `work-mcp1000-d52rpoff` | 30 | 47M | `52_isolated-grouping-fix-design.md` |
| `work-mcp1000-d53off` | 30 | 47M | `52_isolated-grouping-fix-design.md`, `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp1000-d55boff` | 30 | 47M | — |
| `work-mcp1000-d55bon` | 30 | 46M | — |
| `work-mcp1000-d55toff` | 30 | 47M | — |
| `work-mcp1000-d55ton` | 30 | 46M | — |
| `work-mcp1000-p54base` | 30 | 24M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000-p54opt` | 30 | 24M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000-p55opt` | 30 | 24M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000-p56off` | 30 | 24M | `56_beam-window-tagger-gate.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000-d56bw` | 30 | 20M | `56_beam-window-tagger-gate.md`, `scripts/analysis/stm/bwgate_report.py`, `scripts/analysis/misc/mabc_step_totals.py`, `nusel_display/serve_nusel_scan.sh` |
| `work-mcp1000-p65fin` | 30 | 21M | `65_tgm-stm-perf-final.md`, `scripts/analysis/misc/mabc_step_totals.py`, `scripts/perf/profile_pr65.sh` |
| `work-mcp1000b-d52off` | 30 | 44M | `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp1000b-d52on` | 30 | 44M | `52_isolated-grouping-fix-design.md`, `scripts/analysis/stm/d52_ab_report.py` |
| `work-mcp1000b-d52roff` | 30 | 44M | `52_isolated-grouping-fix-design.md` |
| `work-mcp1000b-d52rpoff` | 30 | 44M | `52_isolated-grouping-fix-design.md` |
| `work-mcp1000b-d53off` | 30 | 44M | `52_isolated-grouping-fix-design.md`, `53_unmerge-vs-cathode-crossers.md` |
| `work-mcp1000b-d55boff` | 30 | 44M | — |
| `work-mcp1000b-d55bon` | 30 | 44M | — |
| `work-mcp1000b-d55toff` | 30 | 44M | — |
| `work-mcp1000b-d55ton` | 30 | 44M | — |
| `work-mcp1000b-p54base` | 30 | 24M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000b-p54opt` | 30 | 24M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000b-p55opt` | 30 | 24M | `54_tgm-stm-perf-round1.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000b-p56off` | 30 | 23M | `56_beam-window-tagger-gate.md`, `scripts/perf/p54_ab_report.py` |
| `work-mcp1000b-d56bw` | 30 | 19M | `56_beam-window-tagger-gate.md`, `scripts/analysis/stm/bwgate_report.py`, `scripts/analysis/misc/mabc_step_totals.py`, `nusel_display/serve_nusel_scan.sh` |
| `work-mcp1000b-p65fin` | 30 | 19M | `65_tgm-stm-perf-final.md`, `scripts/analysis/misc/mabc_step_totals.py`, `scripts/perf/profile_pr65.sh` |
| `work-smoke-d55pv` | 12 | 5M | — |

### Added 2026-07-29 — nueCC48 campaign roots (docs `pr/1_`, `pr/2_`)

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-nuecc48-base` | 92 | 154M | `pr/2_uboone-chain-gap-analysis-and-validation-plan.md` §5 — partial earlier arm of the 48-event Lynn nueCC candidate set (48 evt, 24 ql_evt, 20 nusel_evt) |
| `work-nuecc48-nuf` | 146 | 485M | `pr/1_beam-window-cosmic-vs-nu-division.md` (the run that created it, 48/48 rc=0), `pr/2_…` §5 — **complete** cosmic-tagger-tail arm: 48 evt (symlinks into shared `work/` imaging) + 48 ql_evt (with pctrees) + 48 nusel_evt + merged `nusel-table.tsv`/`nusel-events.tsv`; production NUF flags (unmerge_assoc in-log). 45 nu-candidate / 3 cosmic-tagged. The planned Track C PR arm symlinks from here |
| `work-nuecc48-prsmoke` | 2 | 8M | `pr/2_…` §5.3 — 2-event smoke of the PR neutrino stage (evt 172230, 444187; production tail + `tagger_check_neutrino`, rc=0, full PR Bee layers) |
| `work-nuecc48-prsmoke2` | 2 | ~5M | `pr/3_pr-skip-cosmic-and-outputs.md` §6 — single-event validation of the full PR output chain (evt 172230 nu-candidate + 444187 TGM skip-demo; 13-stage pipeline with `nu_skip_cosmic`, Bee prototype-parity knobs, BDT scorers, `tracking-pr.root` T_tagger/T_kine); runner `run_pr3_evt.sh` in the root.  Also holds the `pr/4` DL-vertex adoption arms: `nupr_evt172230_dl{,_rep}` (explicit SCN weights + determinism repeat), `nupr_evt172230_defaultdl` (inherits the new config default), `nupr_evt172230_dl_importfail` (the silent-fallback failure, kept as the exhibit); runner `run_pr3_evt_dl.sh`.  `pr/5` investigation arms: `nupr_evt172230_dl_trace2` (per-logger trace used to pin the PID/vertex chain; `_dl_trace` is the clobbered-log first attempt, kept), `nupr_evt172230_pufix` (verifies the SbndPrMagnifyTrackingVisitor fractional-channel fix, mabc bit-identical to the DL arm).  `pr/6` arms: `nupr_evt172230_dirweak{,_geo}`, `nupr_evt444187_dirweak` (dir_weak_use_score knob-on runs, all bit-identical to their pr/4 counterparts) |

### Added 2026-08-01 — cathode-crossing PR arms (doc `pr/12_`)

Both are subset re-runs of the doc pr/11 population arms at HEAD `3fe65876`, made only
so every number in `pr/12` comes from one binary (md5 `07a78447…` verified before and
after both). Selection came from `work-mcp1kall-pr11v3` / `work-nuecc48-pr11v3`, which
stay the population reference.

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-mcp1kall-cath01` | 54 | ~150M | `pr/12_cathode-crossing-neutrino-pr.md` — the 54 mcp1k candidates whose fitted trajectory and/or charge crosses the cathode, full 13-stage PR chain, 54/54 rc=0. Source of `docs/pr/12_cathode-census.tsv` and the `cath_spanned`/`cath_broken` Bee sets |
| `work-nuecc48-cath01` | 3 | ~10M | `pr/12_…` — the 3 nueCC48 cathode-crossing candidates (214469 spanned, 267597 the single genuine split, 437699 fit-stops-at-cathode), 3/3 rc=0 |

## `archive/tgm-docs29-39/` — 30 dirs, 257 MB

**TGM / LM / FV campaign.** every arm whose newest citation is doc ≤39 — the merge-aware TGM chain (docs 29-33), the LM tagger (34), interior FV and main-component-pairs (35-36), pctree provenance (38) and the FC/TGM x-y margins (39).

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-mcp10-chord` | 43 | 3M | `29_tgm-chord-charge.md`, `30_matched-mains-main-flag.md`, `31_tgm-chord-path-mode.md`, `32_tgm-component-rescue-fvz.md`, `35_tgm-interior-fv.md`, `nusel_display/README.md`, `run_nusel_evt.sh`, `wct-pr-perevt.jsonnet` |
| `work-mcp10-ctpcfix` | 43 | 33M | `32_tgm-component-rescue-fvz.md`, `33_tgm-rescue-chord.md`, `34_lm-tagger.md`, `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md` |
| `work-mcp10-fvxy` | 43 | 3M | `39_tgm-fc-fv-xy-margins.md` |
| `work-mcp10-lm` | 53 | 37M | `34_lm-tagger.md`, `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `scripts/analysis/ql/lm_tune.py`, `nusel_display/nusel_scan_viewer.py`, `nusel_extract.py`, `qlmatching.jsonnet`, `run_ql_evt.sh`, `wct-clus-matching-perevt.jsonnet` |
| `work-mcp10-lm-offgate` | 2 | 2M | `34_lm-tagger.md` |
| `work-mcp10-lm2-offgate` | 2 | 2M | `34_lm-tagger.md` |
| `work-mcp10-mainflag` | 43 | 30M | `30_matched-mains-main-flag.md`, `31_tgm-chord-path-mode.md`, `32_tgm-component-rescue-fvz.md`, `33_tgm-rescue-chord.md` |
| `work-mcp10-merge` | 42 | 3M | `15_overclustering-evt11-gamma.md`, `23_nusel-tgm-stm-chain.md`, `29_tgm-chord-charge.md`, `30_matched-mains-main-flag.md`, `31_tgm-chord-path-mode.md`, `51_clustering-merge-attribution.md`, `52_isolated-grouping-fix-design.md`, `nusel_display/README.md`, `nusel_display/nusel_scan_viewer.py`, `nusel_display/serve_nusel_scan.sh`, `scripts/analysis/stm/stm_main_connectivity.py` |
| `work-mcp10-merge2` | 43 | 3M | `29_tgm-chord-charge.md`, `30_matched-mains-main-flag.md`, `31_tgm-chord-path-mode.md`, `nusel_display/README.md`, `nusel_display/serve_nusel_scan.sh` |
| `work-mcp10-offgate` | 42 | 3M | `29_tgm-chord-charge.md` |
| `work-mcp10-offgate2` | 42 | 3M | `29_tgm-chord-charge.md` |
| `work-mcp10-pathchord` | 33 | 3M | `31_tgm-chord-path-mode.md` |
| `work-mcp10-rcidoff` | 30 | 34M | `38_pctree-provenance-tgm-main-real.md` |
| `work-mcp10-rcoff` | 42 | 3M | `33_tgm-rescue-chord.md` |
| `work-mcp10-reschord` | 43 | 3M | `33_tgm-rescue-chord.md`, `34_lm-tagger.md`, `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md` |
| `work-mcp10-tgmfv` | 43 | 3M | `32_tgm-component-rescue-fvz.md`, `33_tgm-rescue-chord.md`, `34_lm-tagger.md` |
| `work-mcp10-tgmfv-offgate` | 2 | 233K | `32_tgm-component-rescue-fvz.md` |
| `work-mcp1000-ctpcfix` | 33 | 25M | `32_tgm-component-rescue-fvz.md`, `33_tgm-rescue-chord.md`, `34_lm-tagger.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md` |
| `work-mcp1000-fvxy` | 33 | 2M | `39_tgm-fc-fv-xy-margins.md` |
| `work-mcp1000-lm` | 33 | 28M | `34_lm-tagger.md`, `35_tgm-interior-fv.md`, `38_pctree-provenance-tgm-main-real.md`, `scripts/analysis/ql/lm_tune.py`, `nusel_display/nusel_scan_viewer.py`, `nusel_extract.py`, `qlmatching.jsonnet`, `run_ql_evt.sh`, `wct-clus-matching-perevt.jsonnet` |
| `work-mcp1000-mainflag` | 32 | 22M | `30_matched-mains-main-flag.md`, `31_tgm-chord-path-mode.md` |
| `work-mcp1000-pathchord` | 22 | 2M | `31_tgm-chord-path-mode.md` |
| `work-mcp1000-rcoff` | 30 | 2M | `33_tgm-rescue-chord.md` |
| `work-mcp1000-reschord` | 32 | 2M | `33_tgm-rescue-chord.md`, `34_lm-tagger.md`, `36_tgm-main-component-pairs.md` |
| `work-mcp1000-tgmfv` | 33 | 2M | `32_tgm-component-rescue-fvz.md`, `33_tgm-rescue-chord.md`, `34_lm-tagger.md` |
| `work-mcp1000b-fvxy` | 33 | 2M | `39_tgm-fc-fv-xy-margins.md` |
| `work-mcp1000b-fvzi-offgate` | 3 | 131K | `35_tgm-interior-fv.md` |
| `work-mcp1000b-nucdbg` | 2 | 109K | `36_tgm-main-component-pairs.md` |
| `work-mcp1000b-smoke38` | 3 | 1M | `38_pctree-provenance-tgm-main-real.md` |
| `work-mcp1000b-smoke38c` | 3 | 1M | `38_pctree-provenance-tgm-main-real.md` |

## `archive/stm-docs40-49/` — 43 dirs, 622 MB

**STM track-fit campaign.** arms whose newest citation is doc 40-49 — the STM fit dump and showcase (41-43), truth dQ/dx and delta rays (44,46), the un-merge into main+associated (45), the Bragg reference retune (47-48) and the STM containment FV fix (49). Also the three `stmon` arms, named only by `scripts/analysis/stm/stmon_stats.py`.

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-mcp10-dq48` | 42 | 3M | `48_sbnd-dqdx-tables-and-mip.md`, `49_stm-containment-fv-inconsistency.md`, `scripts/analysis/stm/stm_fv_census.py` |
| `work-mcp10-dq48base` | 42 | 3M | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp10-dq48tab` | 42 | 3M | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp10-dq48v3` | 45 | 28M | `45_unmerge-bundle-main-associated.md`, `49_stm-containment-fv-inconsistency.md`, `scripts/analysis/stm/stm_fv_census.py` |
| `work-mcp10-dq49off` | 42 | 28M | `49_stm-containment-fv-inconsistency.md` |
| `work-mcp10-dq49off2` | 42 | 27M | `49_stm-containment-fv-inconsistency.md` |
| `work-mcp10-fvzi` | 43 | 3M | `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp10-lm2` | 43 | 37M | `34_lm-tagger.md`, `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp10-mainpair` | 42 | 3M | `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp10-mainreal` | 42 | 37M | `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp10-stmon` | 43 | 4M | `41_stm-fit-dump.md`, `42_stm-fit-showcase-evt286241.md`, `43_magnify-tracking-sbnd-bugs.md`, `47_stm-bragg-reference-sbnd-retune.md`, `scripts/bee/make_stmfit_bee.py`, `scripts/analysis/stm/stmfit_showcase.py`, `scripts/analysis/stm/stmon_stats.py` |
| `work-mcp10-unm45` | 43 | 27M | `45_unmerge-bundle-main-associated.md` |
| `work-mcp1000-dq48` | 32 | 2M | `48_sbnd-dqdx-tables-and-mip.md`, `scripts/analysis/stm/stm_fv_census.py` |
| `work-mcp1000-dq48base` | 32 | 2M | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp1000-dq48tab` | 32 | 2M | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp1000-dq48v3` | 35 | 22M | `45_unmerge-bundle-main-associated.md`, `49_stm-containment-fv-inconsistency.md`, `scripts/analysis/stm/stm_fv_census.py` |
| `work-mcp1000-dq49off` | 32 | 22M | `49_stm-containment-fv-inconsistency.md` |
| `work-mcp1000-dq49off2` | 32 | 21M | `49_stm-containment-fv-inconsistency.md` |
| `work-mcp1000-fvzi` | 32 | 2M | `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000-lm2` | 33 | 28M | `34_lm-tagger.md`, `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000-mainpair` | 32 | 2M | `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000-mainreal` | 32 | 28M | `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000-stmon` | 32 | 4M | `scripts/analysis/stm/stmon_stats.py` |
| `work-mcp1000-unm45` | 30 | 21M | `45_unmerge-bundle-main-associated.md` |
| `work-mcp1000b-dq48` | 32 | 2M | `48_sbnd-dqdx-tables-and-mip.md`, `scripts/analysis/stm/stm_fv_census.py` |
| `work-mcp1000b-dq48base` | 32 | 2M | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp1000b-dq48tab` | 32 | 2M | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp1000b-dq48v3` | 34 | 20M | `45_unmerge-bundle-main-associated.md`, `49_stm-containment-fv-inconsistency.md`, `scripts/analysis/stm/stm_fv_census.py` |
| `work-mcp1000b-dq49off` | 32 | 20M | `49_stm-containment-fv-inconsistency.md` |
| `work-mcp1000b-dq49off2` | 32 | 20M | `49_stm-containment-fv-inconsistency.md` |
| `work-mcp1000b-evnew` | 6 | 394K | `48_sbnd-dqdx-tables-and-mip.md` |
| `work-mcp1000b-fvzi` | 32 | 2M | `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000b-lm2` | 33 | 27M | `35_tgm-interior-fv.md`, `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000b-mainpair` | 32 | 2M | `36_tgm-main-component-pairs.md`, `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000b-mainreal` | 32 | 27M | `38_pctree-provenance-tgm-main-real.md`, `39_tgm-fc-fv-xy-margins.md`, `41_stm-fit-dump.md` |
| `work-mcp1000b-stmon` | 32 | 3M | `scripts/analysis/stm/stmon_stats.py` |
| `work-mcp1000b-unm45` | 30 | 20M | `45_unmerge-bundle-main-associated.md` |
| `work-mcsim-diffusion` | 1 | 5K | `run_ql_evt.sh` |
| `work-mcsim-stmon` | 52 | 109M | `42_stm-fit-showcase-evt286241.md`, `44_stm-fit-truth-dqdx.md`, `45_unmerge-bundle-main-associated.md`, `46_stm-fit-deltarays-and-gui.md` |
| `work-mcsim-unmcomp` | 21 | 397K | `45_unmerge-bundle-main-associated.md` |
| `work-mcsim-unmoff` | 42 | 3M | `45_unmerge-bundle-main-associated.md` |
| `work-mcsim-unmon` | 42 | 3M | `45_unmerge-bundle-main-associated.md` |
| `work-stmbadch` | 2 | 344K | `42_stm-fit-showcase-evt286241.md`, `43_magnify-tracking-sbnd-bugs.md` |

## `archive/aborted-d54/` — 6 dirs, 145 MB

**SBND `d54off`/`d54on` pair — off-arm complete, on-arm empty.** What is
observable: each `d54off` holds a full run (20 `.batch_nusel_*.log`, `ql_evt*`,
`nusel_evt*`), while each `d54on` holds ten event dirs that are empty and **no
batch log at all** — so the on-arm never wrote anything. Whether it was killed,
never launched, or is queued for relaunch is not recorded here, so treat
"aborted" as a description of the output, not of intent. No doc cites either
arm; doc 52's `d54base`/`d54opt2` are `abtest/snap/` labels, a different thing.
Kept rather than deleted because the off-arm is a complete 30-event run.

**If that campaign is relaunched** with `-t d54on`, the runner will create a
fresh dir at the *top level* while its sibling sits here — move the pair back
out (and re-run `relink_tags.py`) rather than leaving the arms split.

| dir | entries | size | referenced by |
|---|---|---|---|
| `work-mcp10-d54off` | 52 | 60M | — |
| `work-mcp10-d54on` | 10 | 5K | — |
| `work-mcp1000-d54off` | 29 | 41M | — |
| `work-mcp1000-d54on` | 10 | 5K | — |
| `work-mcp1000b-d54off` | 30 | 44M | — |
| `work-mcp1000b-d54on` | 10 | 5K | — |

## RETIRED 2026-07-25 — 44 dirs, 307 MB, deleted

Every entry here was verified to be named by no committed doc, no analysis
script, no running viewer, and no `abtest/`/`sweep/` gate snapshot, using a
**bare-tag** search (`dq48tab`, `d53leg`, …) across `docs/`, `nusel_display/`,
`ql_scan/`, `*.py`, `*.sh`, `*.jsonnet`. A full-directory-name search is NOT
sufficient — the docs cite tags without the manifest prefix, and that mistake
initially mislabelled `d53dflt`/`d53leg` (evidence for a gate committed the same
day) as unreferenced.

Group A is the ad-hoc probe class: 2-5 event runs made while chasing one number.
Group B is full-manifest arms that nothing names — mostly gate off-arms and
superseded variants whose partner arm survives. No link anywhere pointed into
any of them, so the deletion broke nothing. Nothing inside `work/` was touched.

| dir | group | entries | size | what it was |
|---|---|---|---|---|
| `work-d49diag-nofit` | A | 3 | 866K | doc 49 STM-containment FV diagnostic probe |
| `work-d49diag-off` | A | 3 | 928K | doc 49 STM-containment FV diagnostic probe |
| `work-d49diag-rep1` | A | 3 | 1M | doc 49 STM-containment FV diagnostic probe |
| `work-d49diag-rep2` | A | 3 | 1M | doc 49 STM-containment FV diagnostic probe |
| `work-det287517-fit1` | A | 3 | 762K | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-det287517-fit2` | A | 3 | 762K | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-det287517-flagtest2` | A | 3 | 4M | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-det287517-nofit3` | A | 3 | 329K | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-det287517-nofit4` | A | 3 | 329K | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-det287517-oldfit` | A | 3 | 762K | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-det287517-oldnofit` | A | 3 | 329K | doc 41/42 STM track-fit probe on data evt 287517 |
| `work-mcp10-d49soff` | B | 42 | 27M | doc 49/50 STM-scope gate off-arm |
| `work-mcp10-d53chk` | A | 2 | 2M | doc 53 Bee-layer spot check, evt 284349 |
| `work-mcp10-dq48fit` | B | 43 | 4M | doc 48 dQ/dx fit intermediate |
| `work-mcp10-dq48v2` | B | 42 | 28M | doc 48 dQ/dx table v2 (superseded by v3) |
| `work-mcp10-dq49` | B | 42 | 29M | doc 49 first pass (superseded by dq49off2) |
| `work-mcp10-mp36off` | B | 42 | 3M | doc 36 main-component-pairs off-arm |
| `work-mcp10-mpoff` | B | 42 | 3M | doc 36 main-component-pairs off-arm |
| `work-mcp10-prodoff` | B | 42 | 3M | production-default off-arm |
| `work-mcp10-stmoff` | B | 42 | 3M | STM-tagger off-arm |
| `work-mcp1000-d49soff` | B | 32 | 21M | doc 49/50 STM-scope gate off-arm |
| `work-mcp1000-dq48fit` | B | 33 | 4M | doc 48 dQ/dx fit intermediate |
| `work-mcp1000-dq48v2` | B | 32 | 22M | doc 48 dQ/dx table v2 (superseded by v3) |
| `work-mcp1000-dq49` | B | 32 | 23M | doc 49 first pass (superseded by dq49off2) |
| `work-mcp1000-mp36off` | B | 30 | 2M | doc 36 main-component-pairs off-arm |
| `work-mcp1000-mpoff` | B | 32 | 2M | doc 36 main-component-pairs off-arm |
| `work-mcp1000-prodoff` | B | 30 | 2M | production-default off-arm |
| `work-mcp1000-stmoff` | B | 30 | 2M | STM-tagger off-arm |
| `work-mcp1000-tgmfv-dbg3` | A | 2 | 325K | doc 32 TGM FV debug |
| `work-mcp1000-tgmfv-dbg5` | A | 2 | 330K | doc 32 TGM FV debug |
| `work-mcp1000b-d49soff` | B | 32 | 20M | doc 49/50 STM-scope gate off-arm |
| `work-mcp1000b-dq48fit` | B | 32 | 3M | doc 48 dQ/dx fit intermediate |
| `work-mcp1000b-dq48v2` | B | 32 | 20M | doc 48 dQ/dx table v2 (superseded by v3) |
| `work-mcp1000b-dq49` | B | 32 | 23M | doc 49 first pass (superseded by dq49off2) |
| `work-mcp1000b-evbase` | A | 6 | 394K | doc 48 dQ/dx table pre-check |
| `work-mcp1000b-mp36off` | B | 30 | 2M | doc 36 main-component-pairs off-arm |
| `work-mcp1000b-mpoff` | B | 32 | 2M | doc 36 main-component-pairs off-arm |
| `work-mcp1000b-nucoffdbg` | A | 2 | 109K | doc 36 nu-candidate off-arm debug |
| `work-mcp1000b-prodoff` | B | 30 | 2M | production-default off-arm |
| `work-mcp1000b-sa1` | B | 32 | 20M | doc 49 scope-alignment trial |
| `work-mcp1000b-sa2` | B | 32 | 20M | doc 49 scope-alignment trial |
| `work-mcp1000b-stmoff` | B | 30 | 2M | STM-tagger off-arm |
| `work-mcsim-unmerge` | A | 20 | 6K | doc 45 empty stub (run produced no output) |
| `work-why285185` | A | 15 | 740K | one-off "why is evt 285185 like this" probe |

## 2026-08-20 — doc pr/98 arms (fit_exclusion port fix + nueCC48 re-evaluation)

All on the nueCC48 manifest, Q/L root `work-nuecc48-ql0819`, baseline
`work-nuecc48-prod0819`.  Round doc: `docs/pr/98_fit-exclusion-port-fix.md`.

| arm | role | keep? |
|---|---|---|
| `work-pr98-off-nuecc48` | knob-off gate arm, first post-fix binary (gate PASS 96/96 vs prod0819) | until round closes |
| `work-pr98-off2-nuecc48` | knob-off gate arm, FINAL binary incl. perf helper (gate PASS 96/96) | until round closes |
| `work-pr98-fx-nuecc48` | THE measurement: SBND_FIT_EXCLUSION=true, fixed binary; Bee ON set 6f30f958 | KEEP while pr/98 open |
| `work-pr98-fx2-smoke` | evts 54095+196649 perf-helper identity (hash PASS) + timing | releasable after doc |
| `work-pr98-fx3-smoke` | evt 256587 perf-helper identity (hash PASS) + timing | releasable after doc |

Addendum (same day, perf rounds 2-3 + PRODUCTION FLIP): `work-pr98-fx4-nuecc48`
(round-2 identity 96/96 + timing), `work-pr98-off3-nuecc48` (round-2 off gate),
`work-pr98-flip-nuecc48` (**post-flip bare = new production baseline on
nueCC48**, round-3 identity 96/96, KEEP), `work-pr98-floff-nuecc48`
(SBND_FIT_EXCLUSION=false == pre-flip prod0819, 96/96).  fit_exclusion is SBND
PRODUCTION ON as of toolkit flip commit (doc pr/98 §10); `work-nuecc48-prod0819`
remains the pre-flip reference.

## doc pr/99 (2026-08-20) — owner scan triage, log-only probe arms

| arm | what | keep? |
|---|---|---|
| `work-pr99-probe-mcp2k` | evts 279955+70084, all diag env probes, hash PASS 4/4 vs work-pr96-prodflip-mcp2k | releasable after doc |
| `work-pr99-probe-mcp1k` | evts 395148+315167, same probes, hash PASS 4/4 vs work-scan-prodflip-mcp1k | releasable after doc |
| `work-pr99-probe-ncpi0` | evt 285567, same probes, hash PASS 2/2 vs work-scan-prodflip-ncpi0 | releasable after doc |
| `work-pr99-t70084` | evt 70084 at trace level + WCT_SHOWER_CREATE_DEBUG (the op1-post 0.87-overlap decline evidence) | releasable after doc |

The `*-prodflip-*` arms this round reads (pr96-prodflip-mcp2k,
scan-prodflip-{mcp1k,ncpi0}) belong to the concurrent session's round — not
tagged here, never written to.

## doc pr/99 round 2 (2026-08-20)
- work-pr99r2-base-{ncpi0,mcp1k,mcp2k} -- pre-edit baselines at f4b4d0ec (19+35+15 evts), proven ≡ prodflip arms; **KEEP: standing numu50/ncpi0 comparison baselines**
- work-pr99r2-off-{nuecc48,ncpi0,mcp1k,mcp2k} / -off2-* / -off3-* -- knob-off gate arms (3 binary iterations, all gates PASS); off/off2 releasable now, off3 releasable after next round
- work-pr99r2-on-{...} / -on2-* -- campaign iterations 1-2 (veto-radius adverse / pre-span-guard); releasable now
- work-pr99r2-on3-{nuecc48,ncpi0,mcp1k,mcp2k} -- FINAL knob-on arms (production operating point); **KEEP until owner scan done**
- work-pr99r2-smoke-*, -smoke2-*, -smoket-*, -probe285567 -- single-event smokes/probes; releasable after doc
- work-pr99r2-flip-*, -floff-* -- flip proofs (13 evts x2); releasable after doc
- work-pr99r3-off-{nuecc48,ncpi0,mcp1k,mcp2k} -- round-3 knob-off gate arms (234 archives PASS vs on3); releasable after next round
- work-pr99r3-on-* -- first knob-on pass (no display, stem 3.0, superseded by onf); releasable now
- work-pr99r3-ond-{ncpi0,nuecc48} -- PARTIAL arms aborted at the stem 3.0->2.8 correction; releasable now
- work-pr99r3-onf-{nuecc48,ncpi0,mcp1k,mcp2k} -- FINAL round-3 knob-on arms (production operating point + pr_display); **KEEP until owner scan done**
- work-pr99r3-dduponly-ncpi0 -- 4-evt dedup-only attribution probe (pi0-pair losses); keep with doc
- work-pr99r3-flip-*, -floff-* -- flip proofs (8 evts x2); releasable after doc

## doc pr/101 Enu accounting round (2026-08-20)
- work-pr101-off-{nuecc48,ncpi0,mcp1k,mcp2k} / -all-* -- first binary (pre K2-gate/K3-scope refinement); releasable now
- work-pr101-off2-* / -all2-* / -b-* -- second binary (before the K2 leftover mu/pi rule); gate PASS 234; releasable now
- work-pr101-off3-{nuecc48,ncpi0,mcp1k,mcp2k} -- FINAL-binary knob-off gate arms vs work-pr99r3-onf-*; releasable after next round
- work-pr101-all3-{nuecc48,ncpi0,mcp1k,mcp2k} -- FINAL all-five-knobs arms (K1-K5, long-muon mode 2); **KEEP until owner scan done**
- work-pr101-flip-*, -floff-* -- flip proofs (8 evts x2, 16/16 PASS both ways); releasable after doc
- work-pr101-{a,b2,c,d}-* -- single-knob attribution arms (a=K1 track_ctx, b2=K2+K5 mass rules+guard, c=K3 hadronic dQ/dx, d=K4 long-muon mode 2); releasable after doc

## doc pr/102 missing-orphan-segment audit (2026-08-20)
- work-pr102-head-mcp1k -- fresh full 1000-evt mcp1k PR arm at HEAD (post pr/98+99+101 flips), PR_EXTRA_STAGES=pr_display + SBND_TRAJ_COVER_PROBE=1 (log-only); the round's "after" epoch; **KEEP until doc pr/102 closes**
- work-pr102-dbg-mcp1k -- reserved for targeted probe reruns (WCT_PR96_REMSEG_DEBUG etc.) of pr/102 exhibits; may stay unused
- This round READS work-{mcp1k,mcp2k}-prod0819 as its "before" epoch and as the relocated pr/96 6-event calibration source (cbr3 arms retired) -- do not release them while pr/102 is open.

## doc pr/102 round 2 -- P1+P2 knobs (2026-08-20)
- work-pr102r2-base-{nuecc48,ncpi0,mcp1k,mcp2k} -- pre-edit baselines at toolkit 2979bd26 (48/19/35/15 evts, numu50 manifest for the mc samples); Gate-1 reference; releasable after next round
- work-pr102r2-off-{nuecc48,ncpi0,mcp1k,mcp2k} -- knob-off gate arms, new binary; Gate 1 PASS 234/234 vs base; releasable after next round
- work-pr102r2-onA-{mcp1k,mcp2k} -- Stage A exhibit smoke (12+2 evts, min_nnf=4 len_admit=30 uncover_3d=3.0); keep with doc
- work-pr102r2-offfull-mcp1k / -onfull-mcp1k -- full 1000-evt census before/after at the operating point; **KEEP until owner scan done**
- work-pr102r2-on-{nuecc48,ncpi0} -- knob-on physics-ledger arms; **KEEP until owner scan done**

## doc 75 -- tagger-family FV + main-flag audit, two knobs (2026-08-20)
- work-d75r1-bare-{nuecc48,ncpi0,mc50,enriched} -- pre-edit baselines (peer pr/102r2 WIP binary, no doc-75 source edits); Gate reference; releasable after next round
- work-d75r1-off1-{nuecc48,ncpi0,mc50,enriched} -- knob-off gate arms, new binary; PASS 286/286 archives + 143/143 events vs bare; releasable after next round
- work-d75r1-onfv-{nuecc48,ncpi0,mc50} -- `nue_sp_consistent_fv` ON census arms; SBND PRODUCTION ON, owner flip 2026-08-20; **KEEP**
- work-d75r1-onflag-{nuecc48,mc50,enriched} -- `nu_selected_as_main_snapshot_all` ON census arms (round 2: the flip-equivalence check found this fires on 16/143 standard-sample events, not just the enriched manifest); SBND PRODUCTION ON; **KEEP**
- work-d75r1-flipchk-ncpi0 -- post-flip config, no env; flip-equivalence PASS (same 8/19 archives as onflag-ncpi0 alone); **KEEP**
- enriched manifest = union of promoted-main (21) + multi-candidate (8) events read from the peer's `work-pr102-head-mcp1k` (read-only; unique ids listed in doc 75 §Repro)
- work-pr102r2-beq-mcp1k -- DEAD (wrong event list, 0-archive gate); work-pr102r2-beq2-mcp1k -- peer-binary equivalence proof (6/6 archives vs off arm)
- work-pr102r2-off2-{nuecc48,ncpi0,mcp1k,mcp2k} -- knob-off gate arms on the SHIPPING binary (post UAF fix); Gate 1 PASS 234/234 vs base; releasable after next round
- work-pr102r2-{offfullp,onfullp,onfull2p}-mcp1k -- patch arms for the peer build-race / cfg-collision failures; members of the merged arms below
- work-pr102r2-{offmerged,onmerged}-mcp1k -- SYMLINK-MERGED 1000-evt census arms (offfull+offfullp / onfull2+onfull2p); derived, keep while pr/102 r2 open
- work-pr102r2-onfull-mcp1k / -on-{nuecc48,ncpi0} -- pre-UAF-fix ON arms, superseded by onfull2/on2; releasable now
- work-pr102r2-dbgp1/dbgp2/dbgp2b-mcp1k -- 399998 crash factorization (P1-only ok / P2-only rc=135 / P2-only after fix ok); keep with doc
- work-pr102r2-{kA,kB,kC}-mcp1k -- single-knob attribution on the 28 ADVERSE events (kA=min_nnf 1 ADVERSE, kB=len_admit ZERO movers, kC=uncover_3d 23 ADVERSE); keep with doc
- work-pr102r2-p1full-mcp1k / -p1-{nuecc48,ncpi0} -- P1-only (min_nnf=4 len_admit=30) full validation arms; **KEEP until owner scan done**
- work-pr102r2-{nnf4,nnf8,len30,n8l30}-nuecc48 -- P1 disjunct sweep (nue ledger: -4/+1, -1/+1, 0/0, -1/+1); keep with doc
- work-pr102r2-l30full-mcp1k / -l30-ncpi0 -- len_admit=30-only operating-point arms (the flip candidate); **KEEP until owner scan done**

## doc pr/103 -- near-vertex busy-vertex revisit: mvga op0 pass-through + interposed fallback (2026-08-20/21)
- work-pr103-bare-mcp1k -- full 1000-evt HEAD b4670d9b baseline, pr_display; 204 events FAILED (plugin-load race with a concurrent wcbuild, rc=1) -- read through work-pr103-baremerged-mcp1k only; **KEEP until pr/103 closes**
- work-pr103-bare2-{mcp1k(204),nuecc48,ncpi0,mcp2k(15)} -- legacy-binary (stash-restored HEAD) baselines; Gate-1 reference; **KEEP**
- work-pr103-baremerged-mcp1k -- SYMLINK-MERGED bare(796 rc=0)+bare2(204); derived; keep while pr/103 open
- work-pr103-off-{mcp1k,nuecc48,ncpi0,mcp2k} -- knob-off gate arms, new binary; Gate 1 PASS 2000/2000 + 96/96 + 38/38 + 30/30; releasable after next round
- work-pr103-off2-{nuecc48,ncpi0} -- final-binary knob-off re-gate; releasable after next round
- work-pr103-on-{mcp1k,nuecc48,ncpi0,mcp2k} -- knob-on arms (mvga_passthru=4 + mvga_interposed_fallback); the round's census/mover/Bee "after"; **KEEP until owner scan done**
- work-pr103-tr-{mcp1k(283713),mcp2k(405707)}, work-pr103-tr2-mcp1k (6 shortcut evts) -- trace-level diagnosis arms; keep with doc
- work-pr103-on{A,B,C,D}-mcp2k -- FAILED/partial op0 iterations on 405707 (nearest-wcpt test; op1 re-deleting the connector); dead, releasable now
- work-pr103-onE-{mcp2k,mcp1k} -- Stage A smoke (fallback WITHOUT the degree-2 restriction); keep with doc (sec 4.2 table)
- work-pr103-on2-{mcp1k,nuecc48,ncpi0,mcp2k} -- knob-on ROUND 2 on the shipping binary (passthru=4 + fallback + fallback_min_angle=45): the round's adjudicated "after"; **KEEP until owner scan done**
- work-pr103-off3-{nuecc48,ncpi0} -- shipping-binary knob-off re-gate; releasable after next round
- work-pr103-flipchk-{mcp1k(14),nuecc48,ncpi0,mcp2k} -- post-flip config no env; flip-equivalence PASS 28/28+96/96+38/38+30/30 vs on2; **KEEP**
- work-pr103-floff-{nuecc48,ncpi0} -- post-flip forced-off == legacy bare, PASS 96/96+38/38; releasable after next round

## doc pr/104 -- junction snap (2026-08-21)
- work-pr104-bare-{mcp1k(1000),nuecc48,ncpi0,mcp2k(15)} -- HEAD 5b6b289c binary + post-pr/103-flip config baselines, pr_display; **KEEP until pr/104 closes** (mcp1k nusel-table merged by hand: runner edited mid-batch)
- work-pr104-off-{mcp1k,nuecc48,ncpi0,mcp2k} -- binary #1 knob-off gate, PASS 2000/96/38/30; releasable after next round
- work-pr104-on-mcp2k -- binary #1 ON, KILLED mid-run (partial, do not read); releasable
- work-pr104-smoke{,2,3,4,5,6,7}-{mcp2k,mcp1k,nuecc48} -- trace-level probe arms on the exhibit events per binary iteration (doc sec 3.0/3.0.1); releasable after next round
- work-pr104-off2-mcp2k -- binary #2 partial (batch killed); releasable
- work-pr104-off3-{mcp1k,nuecc48,ncpi0,mcp2k} -- binary #5 knob-off gate, PASS 2000/96/38/30; releasable after next round
- work-pr104-on3-{mcp1k,nuecc48,ncpi0,mcp2k} -- binary #5 ON (before min_move + ambiguity veto): the round-3 ledger with the 2 adverse cases (281837, 400474); keep with doc (sec 3.1, Bee round3 set)
- work-pr104-off4-{mcp1k,nuecc48,ncpi0,mcp2k} -- FINAL-binary knob-off gate, PASS 2000/2000 + 96/96 + 38/38 + 30/30; releasable after next round
- work-pr104-on4-{mcp1k,nuecc48,ncpi0,mcp2k} -- FINAL-binary knob-on (vertex_junction_snap + vjs_override_kink_snap): the round's adjudicated arm, Bee "after" set e87695c6; **KEEP**
- work-pr104-flipchk-{mcp1k(28),nuecc48,ncpi0,mcp2k} -- post-flip config no env; flip-equivalence vs on4; **KEEP**
- work-pr104-floff-{nuecc48,ncpi0} -- post-flip forced-off == bare; releasable after next round

## doc pr/105 -- neutrino-vertex strategy comparison + re-rank re-optimization (2026-08-21)
- work-vtx105-base-{nuecc48(47),ncpi0(19),mcp1k(407),mcp2k(581)} -- SBND production (toolkit c550541f) over the 1054-label universe ONLY, pr_display; the carry target of vtxscan-vtx105-*; **KEEP**
- work-vtx105-{nofitx,dlonly,ma4,topo3,topk10,trad,pre103}-<sample> -- selection-strategy / attribution arms, same universe (doc sec 2 table rows); keep with doc until a later vertex round supersedes them
- work-vtx100-{base,topo}-<sample> -- pr/100 epoch reference rows (doc pr/105 sec 1); **KEEP** (previously untagged here)

## doc pr/106 -- target-anchored re-optimization of the DL vertex selection (2026-08-21)
- work-vtx106-harv-base-{nuecc48(47),ncpi0(19),mcp1k(407),mcp2k(581)} -- production config + dl_vtx_harvest over the 1054-label universe: the pre-DL candidate cloud (hv_cloud) every pr/106 target is defined on; hash-gate PASS vs work-vtx105-base-*; **KEEP**
- work-vtx106-harv-topo3-<sample> -- same + dl_vtx_topo_weight=3: the rows source (only a topo arm emits s_topo/topo_frac/votes); row set asserted identical to harv-base; **KEEP** with the doc
- work-vtx106-ma20-<sample> -- live validation arm, SBND_DL_VTX_MIN_ACCEPT=20 (doc sec 6); keep until the owner decision on the flip is recorded
- work-vtx106-harv-nofitx-<sample> / work-vtx106-nofitx-trad-<sample> -- fit_exclusion=false harvest (own pre-DL cloud) + no-DL fallback arms (doc sec 9: the OFF gain is real, heat-map channel); **KEEP** with the doc
- work-vtx106-cne-{off,on}-{nuecc48,ncpi0} -- dl_vtx_cloud_no_exclusion OFF gate (PASS vs vtx105 base) and ON trial with harvest (doc sec 10); keep until the owner decision
## doc pr/107 -- dqdx_fit_keep_all_points (2026-08-21)
- work-pr107-off-{nuecc48,ncpi0} -- new binary, no env: OFF gate PASS 94/94, 38/38 vs work-vtx106-cne-off-*; keep until the owner decision
- work-pr107-on-{nuecc48,ncpi0} -- SBND_DQDX_FIT_KEEP_ALL_POINTS=true + harvest (doc sec 3-6); keep until the owner decision
## doc pr/108 -- exclusion-fit parity, prototype vs toolkit (2026-08-21)
- work-pr108-off1-nuecc48 (10550) -- Test A OFF gate vs work-pr107-off: PASS 2/2; disposable
- work-pr108-assoccheck-nuecc48 (10550 46363 81597) -- WCT_DQDX_ASSOC_CHECK=1: 382 fits max|dQ|=0; keep the logs with the doc
- qlport/scripts/sweep/pr108_{wct_off,wct_on,wct_onkeep,wcp_on,wcp_off} -- uBooNE 5384 six-event four-arm set (WCP arms from the patched prototype build); **KEEP** with the doc

## doc 81 -- group-mode re-baseline of the four production samples (2026-08-25)
- work-{nuecc48,ncpi0,mcp1k,mcp2k}-grp0825 -- stage A run in GROUP mode from reco1: `evt<ID>/` imaging + `ql_evt<ID>/` Q/L per event, 3067 events; member-content gate PASS 24536/24536 vs work-img-* and work-*-ql0819; **KEEP** (the input the MCS and PR rounds consume)
- work-{nuecc48,ncpi0,mcp1k,mcp2k}-prod0825 -- stage B, `PR_GROUP_SIZE=16 PR_JOBS=8 PR_EXTRA_STAGES=pr_display`; pr85 6134/6134 archives + pr94 3067/3067 ROOT files byte-identical vs work-pr112i-snapD2-*; **KEEP** (current production at the shipped operating point)
- work-*-prod0823 -- **PRE-flip** (before `fast_xgb_forest` and the pr/112 dual chain / snapD2 went ON); NOT current production, kept as the prior epoch's reference; see doc 81 sec 4
- released this round: the 54-arm pr/112 + pr/112i option scan, work-pr104-on4-*, work-pr104-flipchk-*, and the four work-vtx106-*-nuecc48 pr/111 arms -- 66 dirs, 72 GiB removed 2026-08-25, records in archive/records/prod0825-groupmode-20260825 (1.4 G, integrity 66/66); plus 20 G of g<K>/ group scratch pruned from the four grp0825 roots. sbnd_xin 236 G -> 144 G, 104 work* dirs -> 38, broken symlinks 0
- `scripts/retire/state-20260825/hashes/*.tsv` -- the frozen reference side of doc 81 sec 8.1 (9402 rollups: pr85 archive rollups + a pr94 per-branch rollup of every tracking-pr.root) for the six retiring arms the gate is taken against, since work-pr112i-snapD2-* was the ONLY per-event arm at the current operating point; **KEEP** (git-tracked, 888K)

## doc 98 -- cleanup: retire the middle, keep the latest production (2026-09-02)
- work-{mcp1k,mcp2k,ncpi0,nuecc48}-d97fv -- **LATEST PRODUCTION stage A (Q/L)**, ref/prod-2026-09-04 (sep_fv_point ON), 3067 evts, complete + rc=0 verified; **KEEP**
- work-{mcp1k,mcp2k,ncpi0,nuecc48}-d97fvpr2 -- **LATEST PRODUCTION stage B (PR tail)** on it, 3067 evts; **KEEP**
- work-sent97-{mcp1k,mcp2k,ncpi0,nuecc48} -- NEW: the 31/31 sentinel witness (28 distinct events) carved out of d97off2pr before it was retired, 165 MB. Production itself is 30/31 (105074 pr/128 class B is an open owner call), so this is the ONLY arm that can adjudicate it and it is NOT rebuildable from production; **KEEP**
- work-*-grp0825 -- now **IMAGING-ONLY**: evt<N> is the substrate 10478 symlinks resolve into and stays; ql_evt<N> was two operating points stale and was retired in place after state-20260902/grp0825-ql-rollup.tsv froze its 18402-member hash rollup
- work-*-doc25new{,2..7} / -doc25old -- a LIVE PEER round's SBND regression-gate arms (PDVD doc 25, gate round 7 in flight); protected by PREFIX until that round closes
- retired this round: 62 dirs / 125.0 GiB -- 9 superseded stage-B PR epochs (prod0901b, d94probe, d94hadron, r2probe, r2entry, r3probe, r3entry, d97onpr, d97off2pr), 2 stage-A (d97on, d97off2), the doc-97 identity-gate probes (d97idg*), 5 small dead probes, plus the grp0825 ql half. Records in archive/records/campaign-close-20260902/ (integrity 62/62)
- ~/tmp swept of 30.4 GiB: 5 closed-round libsnaps (doc94/doc94b/doc94r3/d97/pr142), doc87/lib-knob (re-measured 790/790 md5-identical to lib-flip), 3 regenerable cmake trees, dbg25/groupbuild, 5 old scratch dirs. KEPT: doc25gate + pinlib* (live peer), d97b-libsnap (the production binary), doc94c/doc94r3b/prod0901b-libsnap (each backs a surviving arm)
- **d97on/d97onpr were released deliberately** though sep_track_recarve is still default OFF and its Bee idx 9/10 are unadjudicated -- doc 97 sec 4-5 carry the measurements, Bee set ce2b4924 is uploaded, and the arm re-runs in ~25 min from kept imaging (scripts/d97_on_arms.sh). See doc 98 sec 5.

## doc 98 addendum -- two owner verdicts (2026-09-02)
- **sep_track_recarve REJECTED.** Owner scanned the recarve arm (Bee ce2b4924): "this arm is not as good as my production default. There are several cases, things were not separated properly." No production change was needed -- the knob was always default OFF, so the shipped point (sep_fv_point ON, sep_track_recarve OFF) already is the scanned-good configuration. The eye and the suite agreed: recarve independently broke 2 of 31 sentinels (94392 pr/129 Enu 822 vs want 1136-1149; 53793 doc 84 r2, the 808 MeV cathode-bridged muon returning as 237+32 MeV -- i.e. exactly "not separated/merged properly"). doc 97's recarve arms are retired; records in archive/records/campaign-close-20260902/doc97-separation/.
- **pr/128 class B sentinel (mcp2k 105074) RETIRED** on owner authorization. Not a stale threshold: production emits NO PF tree for that event (mabc-pr.zip = 3 members, no 0-mc.json; in_beam=0, not-tagged), so nothing could be asserted at any threshold. scripts/pr127_sentinels.py is now **30 PASS / 0 FAIL** against work-*-d97fvpr2. `pr128 pf-conn4-near` consequently has no sentinel -- recorded in the file.

## doc 92 refresh -- the production guide re-based on prod0902 (2026-09-02)
- **products/prod0902/** = the reference tables of the CURRENT epoch: `work-{nuecc48,ncpi0,mcp1k,mcp2k}-d97fvpr2` (stage B) on `work-*-d97fv` (stage A Q/L) at `ref/prod-2026-09-04`, toolkit `e88f364d`. 3067 rows, rc=0 everywhere, `pr_scores_table.py`. **The tag is deliberately not the arm name** -- the arm keeps its round label (`d97fv*`) because it is doc 97's validated arm, while the products tag follows the `prod<MMDD>` convention of prod0825/prod0830/prod0901/prod0901b.
- `products/prod0901b/` stays committed as the previous epoch and is what the refresh A/Bs against; its arms are retired (records in `archive/records/campaign-close-20260902/prod-epoch/`).
- **prod0901b -> prod0902, measured** (`scripts/pr142_campaign_ab.py`, both committed table sets): 34 movers of 3067 (1.11%), 11 `event_label` changes, 8 `nu_evaluated` flips, net working-point migration 0 at every nue point and -1 at numu>0.9. Attribution of the 11: 8 are the owner-adjudicated flips the ref READMEs name (doc 94 -- mcp1k 64475, mcp1k 350099, mcp2k 164466; doc 97 -- mcp2k 95911/105074/290654/318703/392901); 1 is mcp2k 74190, one of doc 97 sec 8's three stage-A epoch-drift events; the last 2 (mcp2k 51153, mcp1k 278266) are Q/L flash-match changes where a different bundle wins the in-beam slot -- doc 97 sec 5.1's "an in-beam bundle appears or disappears" class. mcp2k 104172 and 290476 flip `nu_evaluated` without changing label (re-partition of an already-tagged main). Nothing unattributed.
  - Worth knowing for a future round: doc 97's headline "6 in-beam verdict flips" was measured against a FRESH knob-off arm. Against the shipped previous production the count is 11, and 2 of those are not in doc 97's flip list because they are in-beam-slot swaps rather than tagger verdict changes.
- new committed inputs: `docs/92_prodguide/d92-pr-steps-{mcp1k,nuecc48}.tsv` (per-step MABC medians of the prod0902 arms, so figure 8 is not an epoch stale). `docs/pr/pr142-perf-*.tsv` is left untouched as the pr/142 record.
- `docs/92_prodguide/d92-stageA-timing.tsv` verified to ROUND-TRIP to a zero diff: `work-*-grp0825/g<K>/.{img,ql}.time.meta` still exist (194 groups), so the script regenerates the same 388 rows it would otherwise fall back to reading. It is the only surviving record of the imaging half's cost -- check the diff before committing.
- `scripts/analysis/d92_prodguide_plots.py` gained `--cfg` (counts the entry points' TLAs, 501/318 -- the rule is stated in `count_tlas`) and `--qlarm` (per-event Q/L wall from `work-*-d97fv/.status/<evt>`, the current epoch's stage A being per-event rather than group mode).
- MEASURED, not assumed: the production stage-B arm ran at **PR_JOBS=6 (ncpi0, nuecc48) and 8 (mcp1k, mcp2k)** -- `d97_fv_arms.sh` exports 16 but the runner logs say otherwise, so the wall axis is labelled `6-8`. A peer session held loadavg at 26-36 throughout; wall is an upper bound, core is the comparable number.

## doc 92 refresh, part 2 -- the EPOCH GATE: does the current tree still reproduce prod0902? (2026-09-02)
- **Why it was needed.** `prod0902` was produced by `~/tmp/d97b-libsnap` (libWireCellClus.so 2026-09-02 10:59). NINE toolkit commits landed after that, FIVE touching clus/ sources SBND shares with PDVD (TaggerCheckSTM, DynamicPointCloud, Facade_Cluster, TrackFitting, CreateSteinerGraph, SteinerGrapher, NeutrinoTaggerNuE, NeutrinoPatternBase, improvecluster_2, clustering_flag_matched_mains) -- all PDVD crash-path fixes, all *expected* to be no-ops on SBND. `prod_cfg_gate.py` 21/21 covers the CONFIG only and says nothing about the binary. Doc 92 was claiming the epoch was at e88f364d; it was not, and "expected" is not a gate.
- **work-{ncpi0,nuecc48,mcp1k}-d92gate / -d92gatepr** -- the 308-event manifest re-run at e88f364d, BOTH stages (the changed sources run in the Q/L job too) and with NO `-sep-fv-point` flag, so it re-tests the flip as a default at the same time. Driver `scripts/d92_epoch_gate.sh`. 2.3 GiB; releasable once a later round supersedes it, but re-run the driver after ANY master merge -- it is the only check that covers the binary.
- **Result:** stage A **PASS 308/308 events, 1232 products**; stage B archives **PASS 616/616** (38+96+482, 0 unpaired); per-event `nusel-evt<ID>.tsv` **308/308 byte-identical**; `Trun/T_tagger/T_kine/T_rec_charge/T_proj/T_proj_data/T_bad_ch` every branch identical. The PDVD fixes are no-ops on SBND, now measured rather than assumed.
- **The one divergence, and why it is not physics.** 48 cells on 15 events, of 20175 T_cluster rows, confined to `flash_id`/`flash_time_us`/`flash_pe`. Every differing value on BOTH sides is uninitialised memory -- denormal doubles ~1e-310 (pointer bit patterns read as double) and ints like 21845=0x5555. **Cause:** `SbndPrMagnifyTrackingVisitor` writes those three under `if (const auto flash = cl->get_flash())`, but `Facade::Flash::operator bool` returns `m_valid` and that header states outright *"A 'true' does not guarantee all values are valid."* 88 of 20175 rows have flash_time==0, flash_pe==0 and flash_id != -1. **REPORTED, NOT FIXED** (shared component, and `PdvdPrMagnifyTrackingVisitor` has the same shape). Consequence: never put T_cluster's flash_* in a bit-identity gate, and read them only when the cluster has a flash; `nusel-evt<ID>.tsv` is authoritative and was byte-identical on all 308.
- **Second defect found, NOT repaired -- owner call.** `work-nuecc48-d97fvpr2/nusel-events.tsv` holds **2 rows, not 49**, and `nusel-table.tsv` 10 rows instead of 547: a one-event re-run (evt 256587, `fv-nuecc48-pr-fix.log`, jobs=1) re-merged over the full merge, because `run_pr_chain_batch.sh` merges the events of ITS BATCH, not of the arm. All 48 per-event tables are intact, so nothing is lost and no doc-92 number is affected (`pr_scores_table.py` reads per-event files; the nuecc48 score table has all 48 rows). But doc 92's own T1 check `wc -l nusel-events.tsv == N+1` FAILS on the shipped reference arm. Repairing means writing into an existing label (CLAUDE.md sec 5.2) so it is left for the owner to authorise. The runner behaviour is the real bug.
- concurrency corrections shipped with this: `d97_fv_arms.sh` defaults 12/16 -> 8/8 (the M5 cap; the shipped arm ran at 6/6 and 8/8 and the old defaults were dead text that misdescribed it), and `d97_ql_arm.sh`'s log line said "toolkit HEAD" while printing the **wcp-porting-img** HEAD -- it now prints both, named correctly. Chasing 0fce23d4 in the toolkit (it is a wcp doc-96 commit) is how that was found.

## doc 99 -- the two epoch-gate defects fixed, and the residual underneath (2026-09-02)
- **work-{ncpi0,nuecc48,mcp1k}-d99fix / -d99fixpr** -- the same 308-event manifest re-run at toolkit `dc0cc9af` (the flash_at range guard) against the pre-fix `work-*-d92gate{,pr}` baseline. Driver `scripts/d99_flash_gate.sh`; binary pinned at `~/tmp/d99-libsnap` (19:32:54, i.e. BEFORE a peer's TaggerCheckNeutrino edits landed in the shared tree at 19:39, so neither arm contains them). Releasable once superseded.
- **Defect A FIXED (`dc0cc9af`).** `Grouping::flash_at()` set `m_valid=true` on the mere existence of the "flash" PC and then read the row through `get_element()` -> `Array::element()`, an unchecked pointer offset. `Facade_Grouping.h` had ALREADY documented the range check; only the implementation was missing it. Bound is taken on the `"time"` array -- the same one `flashes()` sizes its loop with -- so the QLMatching enumeration path cannot move by construction, and the stage-A gate confirms it.
- **Gate:** stage A **PASS 308/308** (1232 products); stage B archives **PASS 616/616**; **236 280 ROOT branch instances** compared exhaustively with exactly **3** differing (tree, branch) pairs, all `T_cluster` flash columns; `nusel-evt` 308/308; `calib-pr` json 177/177. `d99_flash_ab.py`: 158 rows moved, **0 sentinel violations, 0 census mismatches** -- the moved set equals, per event, the set an independent archive-side census predicted. `wcdoctest-clus` 255/255; the new 6-case test fails 3 cases / 5 assertions with the guard disabled.
- **NOT bit-identical and cannot be:** the changed cells held out-of-bounds reads. Everything outside those three columns is byte-identical.
- **THE BIG ONE — reported not fixed in round 1, FIXED behind two default-OFF knobs in round 2.** The archive keeps only ONE input's canonical flash PC while `QLMatching` stores the PER-INPUT row id on the cluster. Production `T_cluster`, 3067 events, 171 664 matched rows: **50.6% CORRECT, 48.6% resolve to a different REAL flash, 0.8% were out-of-range**. The matching itself is fine -- each input matched against its own list while it was live; only the read-back after the fact is wrong. `flash.time() == cluster_t0` is the bit-exact discriminator.
  - **MECHANISM CORRECTED 2026-09-02.** Round 1 blamed `FlashTensorToOpticalPCs`' `lpcs["flash"] = ...` assign and said the LAST APA's list survives. Wrong on both counts: each of those nodes builds its OWN pctree (`as_pctree`) and clobbers nothing, and production runs `joint=true` so there is no `PointTreeMerging` either. The list is dropped by **`QLMatching`'s own merge** (`QLMatching.cxx:1109-1116`), which concatenates only `root_pcs_to_merge` (`['opflash']`) and drops every other root PC of the non-primary inputs -- so the survivor is the **FIRST** input's list. Every measurement stands (all were taken from the archives); only the reading changes, and it moved the write fix into a different file.
- **work-{ncpi0,nuecc48,mcp1k}-d99r2off / -d99r2offpr / -d99r2rdpr / -d99r2wr / -d99r2wrpr / -d99r2bothpr** -- round 2's six arms on the same 308-event manifest. `d99r2off{,pr}` = both knobs OFF (the inertness gate, vs `d99fix{,pr}`); `d99r2rdpr` = READ knob on, same Q/L root; `d99r2wr{,pr}` = WRITE knob on at stage A, read OFF; `d99r2bothpr` = write-ON archive read by gid, the two-paths-agree cross-check. Driver `scripts/d99r2_flash_gate.sh`; binary pinned at `~/tmp/d99r2-libsnap`. `work-ncpi0-d99r2smoke` is a 1-event write-ON probe, releasable immediately. Releasable once superseded.
- **For any future gate:** production `work-*-d97fvpr2` was written pre-fix, so a fresh arm will differ from it in those three columns on ~1348 rows / ~3066 events. That is expected. Pass them to `d99_root_branch_census.py --expect` or exclude them.
- **Defect B FIXED.** `run_pr_chain_batch.sh` merged the events of ITS INVOCATION into arm-scoped filenames; it now enumerates `pr_evt*/` (same `ls|sed|sort -n` idiom as EVENT_IDS discovery, so row order is unchanged for a full run) and logs both counts. Idempotent and monotone: a partial re-run can only refresh rows.
- **REPAIR APPLIED 2026-09-02 20:22, owner-authorized.** `CONFIRM=yes ./scripts/d99_repair_nuecc48_merge.sh` restored `work-nuecc48-d97fvpr2`'s tables to 49 / 547 rows from the 48 intact per-event files; all three interlocks passed, including "every row of the current truncated files is reproduced verbatim". Truncated originals kept at `work-nuecc48-d97fvpr2/merge-truncated-20260902/` (2 and 10 rows) with a README. **Verified independently:** doc 92's T1 check (`wc -l nusel-events.tsv == N+1`) now PASSES on all four production arms -- nuecc48 49/49, ncpi0 20/20, mcp1k 1001/1001, mcp2k 2001/2001. No per-event file touched; no published number moves.
- new tools: `scripts/analysis/d99_flash_index_census.py` (`--stage ql|pr`), `d99_flash_ab.py`, `d99_root_branch_census.py` (exhaustive: `pr87_root_tree_diff.py` breaks at the first differing branch, so it cannot support a "nothing moved except X" claim), `scripts/d99_flash_gate.sh`, `scripts/d99_repair_nuecc48_merge.sh`.

## doc 99 round 3 -- both knobs FLIPPED to SBND production (2026-09-03)
- **work-ncpi0-d99r3prod / -d99r3prodpr** -- the flip gate's arm: 19 events run with the knobs ON **in the jsonnet defaults** and `QL_EXTRA_TLA`/`PR_EXTRA_TLA` empty, i.e. the path production actually takes. Driver `scripts/d99r3_flip_gate.sh`; binary pinned at `~/tmp/d99r2-libsnap` (a peer landed clus commits `19830863`/`c27ec4b1` after round 2's arms, so an unpinned run would compare a config change against a moving binary). **Small on purpose:** the compiled-config proof shows pre-flip-tree + explicit TLA == post-flip-tree with no TLA, byte-identical JSON for both jobs, so a 308-event re-run would test wcsonnet determinism; what it cannot show is that the *runner* reaches the flipped default, and that is all this arm tests. Releasable once superseded -- but see the ref README: it is `prod-2026-09-05`'s source evidence.
- **Gate PASS:** stage A `d99r3prod == d99r2wr` 19/19 events / 76 products; stage B archives `d99r3prodpr == d99r2bothpr` 38/38; **every ROOT branch with `--expect ""`** -- 152 tree instances, 24 985 branch instances, **0** differing; `T_cluster` **1871/1871 = 100.0%**; negative control (same 19 events pre-flip) **47.8%**, so the instrument can fail.
- **The flip's real before/after, computed on round 2's arms** (`d99r2off{,pr}` = production vs `d99r2wr`/`d99r2bothpr` = flipped), all 308 events: every `mabc-*.zip`, `opflash_apa*.tar.gz`, `mabc-pr.zip`, `nusel-evt<ID>.tsv` (308/308) and `calib-pr` json (177/177, 131 absent in both) **byte-identical**; 236 280 ROOT branch instances with exactly **3** differing pairs (the `T_cluster` flash columns); the pctree archives move in exactly **16 optical datapaths, 0 added, 0 removed**. The matching scalars -- `cluster_t0`, `matched_flash_gid`, `flag_main_cluster`, `flag_associated_cluster`, `lm_flag` -- do **not** move, which is what licenses "no reconstruction changed" rather than inferring it from the knob's intent.
- new tool: `scripts/analysis/d99r3_pctree_datapath_diff.py` -- diffs a pctree tarball by each tensor's `datapath` instead of its member name. Member names are tensor INDICES and renumber whenever a PC is added, so a name diff reports "everything moved"; this is the only way to say which point clouds actually changed.
- **`ref/prod-2026-09-05` cut** (`prod-2026-09-04` left byte-untouched, M13): two ADDED keys, `SbndPrMagnifyTrackingVisitor:pr.flash_by_gid` in `prod_prjob.json` and `QLMatching:matching_joint.merge_flash_pcs` in `sbnd_ql.json`. The other 19 artifacts -- every pdhd, every pdvd, uboone, `prod.wcls`, `prod.standalone` -- byte-identical.
- **`flash_id` now carries the GID in production**, not a per-input row id. `ql_scan/ql_scan_viewer.py` is unaffected (it reads `flash_id` from the calib dump, which `dump_calib` writes at `QLMatching.cxx:1089`, BEFORE the merge at `:1109`, from the per-APA runs). Any arm recorded before 2026-09-03 differs from a fresh one in those three columns and the 16 optical datapaths -- expected, not a regression.

## doc 100 -- cleanup round: sbnd_xin retired, pdvd planned, ~/tmp swept (2026-09-04)
- Owner: *"retire some work* file in ./sbnd_xin and ./pdvd ... keep the latest production result as well as their input ... clean up a bit the ~/tmp directory"*, plus, asked the depth question, **"honour PROTECTED.txt"** for sbnd_xin, **option A** for pdvd and **plan-now-execute-later** for pdvd.
- **sbnd_xin 84 G / 199 dirs -> 71 G / 122 dirs.** Released 77 dirs / 12.6 GiB; records in `archive/records/campaign-close-20260904/` (1.41 GiB raw -> 0.24 GiB, integrity 77/77, then recompressed to zstd: 35 tarballs 0.22 -> 0.07 GiB).
- **KEEP is unchanged from doc 98** -- `work-*-d97fv` (stage A, `ref/prod-2026-09-04`), `work-*-d97fvpr2` (stage B), `work-*-grp0825` (imaging substrate), `work-sent97-*` -- **plus** `work-ncpi0-d99r3prod{,pr}`, now recorded in PROTECTED.txt as the `ref/prod-2026-09-05` flip arm (the newest operating point on disk; production itself is still at prod-2026-09-04).
- released: three superseded gate EPOCHS of the doc 92 -> doc 99 chain (`d92gate{,pr}`, `d99fix{,pr}`, `d99r2*` x7 = 11.3 GiB), doc 95's `dbg25a/b-*`, doc 93/94's `stmfb8-*`, doc 91's `91neg-*`, the `r2scan*` pair. **`d99r2wr`/`d99r2bothpr` are the SOURCE side of doc 99 r3's flip gate**, so a new INTERLOCK 8 refuses the round unless their member hashes are frozen into the archive first.
- **INTERLOCK 5 vetoed two arms on the first draft**: `work-probe178410a` (the only on-disk proof mcp2k 178410's SIGSEGV is nondeterministic) and `work-dbg25a-d97prodchk` (doc 97 sec 9). Both KEEP.
- **A DEFECT THIS ROUND CAUSED, doc 100 sec 4.** `INTERLOCK 3` had been vacuous for absolutely-spelled symlinks in every planner since at least 09-02: it compared `realpath(link)` against `ROOT` written with the `/nfs/data/1/...` alias, and that path is itself a symlink to `/home/xqian/...`, so `relpath(...).split(os.sep)[0]` was always `'..'`. `work-dbg25a-d97prodchk` lost its imaging input when `work-dbg25a-ql` was deleted under it. **Fixed** (realpath both sides, full depth) and proven against the exact missed link. The arm's `ql_evt<N>` outputs -- what doc 97 sec 9 measures -- are intact; the input is regenerable from the surviving reco1 art file + `staged-dbg25/` + manifest. Not rebuilt: owner call (M13).
- the driver's keep-guard also used `work-*-d97fv`, which matches `work-dbg25a-d97fv`; it is now anchored on the four sample names and tested **both** ways (12/12 REFUSE on protected, 7/7 ALLOW on real targets).
- **two sentinel scripts answer different questions and both are correct**: `pr127_sentinels.py` 30/0 on production (doc 98 retired 105074 there), `d97_sentinels.py` 30/1 on production and 31/0 on `work-sent97-*`, which is that witness's whole job. Production unchanged at 30/0 after the round.
- **pdvd: PLANNED, NOT EXECUTED** -- doc pdvd/29. 3661 dirs / 47.19 GiB staged, 7 interlocks PASS, records 3661/3661. A peer session is live in `pdvd/work`; `retire_20260904.sh` interlock A re-runs the whole plan at confirm time so it refuses rather than deletes under them.
- **~/tmp 132 G -> 66 G** in two passes. Pass 1 (`sweep_tmp_20260904.sh`, 56.7 GiB): closed-round lib snapshots + two cmake trees, applying doc 98's "a pin goes with its arms" per pin. Pass 2 (`sweep_tmp_20260904b.sh`, 9.7 GiB, owner-selected): `pinlib2..7` (zero citations) + `doc27`/`doc35`. **The sweep never removes a `*.log`/`*.txt`/`*.md`/`*.json`/`*.zip`** -- only whole `lib*/` snapshot dirs and build trees; a libsnap is regenerable from the commit its doc records, a gate log is not.
- **AGE IS NOT LIVENESS, again**: `claude-25225/.../7117f9b1-...` is 18 GiB, untouched since 09-03 05:49, and its session is **running**. The sweep derives live sessions from `ps`.
- **doc 89's archive recompression is nearly spent on sbnd_xin** -- 4.68 of the 7.16 GiB was already `.tar.zst`, so this round's re-encode freed only 0.16 GiB there. The fresh pdvd record tree is where the remaining win is.

## doc 102 -- the master-branch PR validation samples for colleagues (2026-09-08)
- **work-{nuecc48,ncpi0,mcp1k,mcp2k}-d102m** -- stage A, **reco1 -> imaging -> clustering + Q/L in ONE group-mode arm** (`run_chain_group.sh --size 16 --layout perevt`), unlike every earlier epoch, whose stage A was two arms (`work-*-grp0825` imaging + a per-event Q/L re-run). 3067/3067 events, 0 short groups, 0 missing or empty `pctree-evt<ID>.tar.gz`. mcp2k is TWO invocations into one out_root (`--gbase 63` on the second), so it holds 126 group dirs.
- **work-{nuecc48,ncpi0,mcp1k,mcp2k}-d102mpr** -- stage B, the 15-stage PR chain at the arm defaults, `PR_EXTRA_STAGES=pr_display`, full output (no `PR_MINIMAL_OUTPUT`) so a colleague gets the Bee zip, the pctree and the calib dump per event.
- Binary: toolkit `eacacafe`, pinned at `~/tmp/d102m-libsnap`; **this is the commit this round published as `master`** (`e88f364d..eacacafe`, 104 commits, fast-forward, verified by `ls-remote` and `gh api`). Operating point `ref/prod-2026-09-08` (21/21 PASS).
- Products tag `products/prod0908/`. The tag is not the arm name, as in prod0902.
- **KEEP**: this is the colleague-facing reference epoch and the newest full-population production on disk. Its inputs are the reco1 art files, not another arm, so unlike `work-*-d97fv` it does not pin `work-*-grp0825` -- but grp0825 and d97fv are still the A-side of doc 102's stage-A gate and must not be retired while that gate is the published evidence.
- **A runner defect this round exposed, reported not fixed.** `run_chain_group.sh` names its per-group runner log `$OUTROOT/.g$K.log` by the INTERNAL group index, not the `--gbase`-offset directory name, and its final verdict is `grep -q "^\[g$K\] ok"` on that file. Two concurrent invocations into one out_root -- which is how a two-file sample like mcp2k is run -- therefore share `.g0.log .. .g62.log` and can each read the OTHER's success line. The group DIRECTORIES are offset, so no product ever collides; only the verdict does. Doc 102 gates stage A on products instead (`scripts/d102m_stageA_complete.sh`).
