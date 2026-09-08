# Doc 103 — cleanup round 2026-09-08: retire the campaign the latest one replaced

Owner ask: *"with the latest production, I think we can clean up a bit the disk
space for sbnd_xin, pdhd, pdvd, and ~/tmp to recover some disk. For the
sbnd_xin, we want to keep the most recent campaign, but we can retire some
earlier campaign results to save space."*

**Status: STAGED, NOTHING DELETED.** 13 interlocks PASS / 0 FAIL across three
trees, three clean dry runs, the CONFIRM-only write path exercised end-to-end on
a throwaway stub with a causal negative control, and the record layer frozen —
67 522 files hashed, manifests verified 12/12 against the live tree. The
`CONFIRM=yes` steps are the owner's; the permission gate declines them for me,
as every round since 09-01 records.

## Repro

```bash
cd wcp-porting-img/pdhd/scripts/retire

# the census this round's decisions rest on
python3 toks_20260908.py                              # 5558 dirs -> 5907 tokens
python3 cit_20260908.py toks.txt cit_20260908.json    # 1024 cited, 453356 hits
python3 plan_20260908.py                              # 13 interlocks, writes tier files

# the ~/tmp half -- deletes NOTHING, hardlinks identical pin files
python3 dedup_pins_20260906.py                        # dry run: 5.22 GiB recoverable

# the sbnd_xin half, in this order and no other
python3 archive_records_20260908.py 2                 # DONE: record layer frozen
CONFIRM=yes python3 materialise_20260908.py           # 138 links, 0.608 GiB
CONFIRM=yes ./retire_20260908.sh 2 sbnd               # 12 dirs, 35.85 GiB
```

Pre-state, 2026-09-08 11:41 PDT: `/home/xqian` **454 G free**; sbnd_xin 125 G,
pdvd 52 G, pdhd 64 G, `~/tmp` 46 G.

## 0. The short answer

| action | frees | risk | who runs it |
|---|---:|---|---|
| `~/tmp` pin dedup (hardlink, **nothing deleted**) | **5.22 GiB** | none by construction | owner |
| sbnd_xin tier 2 — the prod-2026-09-04 chain | **35.24 GiB** net | one owner decision, 3 PROTECTED.txt lines | owner |
| pdvd work dirs | **0** | — | — |
| pdhd work dirs | **0** | — | — |
| *(open question)* `pdhd/l1sp_wf_v9` | *11 GiB* | owner call, §5 | owner |

**40.46 GiB is staged and ready.** The two big findings are that sbnd_xin is the
only tree with anything to give, and that pdvd and pdhd genuinely have nothing —
that is a measurement, not a tier I failed to write (§4).

## 1. The latest campaign is self-contained, and that is what made this round easy

Doc 102 produced `work-*-d102m` (stage A) + `work-*-d102mpr` (stage B) — 3067
events at toolkit `eacacafe` = master, `ref/prod-2026-09-08`.

The first thing to establish was not "what is old" but **what the new campaign
depends on**. A symlink census over the whole tree, resolving *both* target
spellings — absolute, and the relative `../<evt>/…` form whose omission made the
09-04 census wrong by 3× — found **28 415 links**, and of the eight d102m/d102mpr
dirs:

```
cross-arm edges out of the new campaign ......... 0
links inside it .............................. 12 268   all `ql_evt<N>/x -> ../evt<N>/x`
broken .......................................... 0
```

`work-*-d102mpr` holds **zero** symlinks at all. Stage A re-imaged all 3067
events itself from the Reco1 art files. So **no earlier campaign is substrate
for the new one**, and nothing released below can reach it. That is written into
`PROTECTED.txt` as a measurement, not an assumption, because the next round will
want to know it without re-deriving it.

## 2. What is retired: the prod-2026-09-04 chain, whole

sbnd_xin's campaigns are a three-link chain — imaging → stage A Q/L → stage B PR:

```
work-*-grp0825  (imaging, doc 81 epoch, 3261 evt dirs)
   ^-- 3067 directory symlinks
work-*-d97fv    (stage A Q/L, ref/prod-2026-09-04)
work-*-d144fixprod (stage B PR tail, 3067/3067 rc=0, doc pr/144 §16.3.1)
```

Every link of it is superseded by doc 102, and **all three are named in
`PROTECTED.txt` today** — as `LATEST PRODUCTION stage A`, `LATEST PRODUCTION
stage B`, and the imaging substrate. That is precisely why this is one tier-2
decision with three grounds rather than a mechanical sweep: it edits the
protection list, not only the disk.

| family | dirs | GiB | superseded by | cost, stated |
|---|---:|---:|---|---|
| `grp0825` | 4 | 15.59 | `d102m` re-images itself from Reco1 | the 08-25-epoch imaging stops being re-readable; a future A/B against that epoch must regenerate from `input_files_reco1/` |
| `d97fv` | 4 | 10.02 | `d102m` (newer toolkit, same 3067 events) | doc 97's per-event Q/L products at the 09-04 point become text-only; `products/prod0902/` and `prod0904/` stay committed |
| `d144fixprod` | 4 | 10.23 | `d102mpr` | doc pr/144 §7's `d144on`-vs-`d144fixprod` byte gate becomes text-only; the sentinel suite loses its pre-pr/145 knob-off control |
| **total** | **12** | **35.85** | | |

**The d144fixprod cost was checked, not asserted.** The worry is that retiring it
strands the sentinel registry. It does not — the suite runs clean at the new
operating point:

```
$ python3 scripts/pr127_sentinels.py --arms 'work-*-d102mpr'
21 PASS, 0 FAIL, 2 OPEN, 7 INERT, 0 SKIP
```

Read a d144-era FAIL as an arm mismatch, never as a regression — doc 101 §8.9
learned that the hard way when pr/145 lifted 393505's waiver.

### What was deliberately *not* retired, each for a measured reason

- **`work-*-d145np` (10.4 GiB).** doc pr/148 §16.2 is a plan for a session that
  has not happened, and it names this arm: *"a **fresh** work dir (M13 — nothing
  under an existing `work-*-d145np` is touched)"*, i.e. it reads it. An open
  round's named input stays, campaign or no.
- **`work-vtx105-base-*` (4.0 GiB).** 1786 citations, 1756 of them from
  `vertex_labels/`. M13.
- **the `s144pos/neg/posleg` 2×2 (0.14 GiB).** The sentinel suite's negative
  control layer — the only on-disk proof it *can* fail.
- **the per-flip arms** `d145prod`, `d146sv25`, `d147-tailflip/flipchk/c8/tail8`.
  Doc 102 §0 lists 8 keys that entered production between master and `eacacafe`;
  these carry one flip's evidence each, and total under 0.5 GiB.

## 3. grp0825 needed a step that did not exist before, and the dry run earned its keep

sbnd_xin's Q/L arms do not hold their own imaging — they hold **directory**
symlinks into it (`work-mcp2k-d97fv/evt281325 -> work-mcp2k-grp0825/evt281325`).
Releasing grp0825 naively is a choice between two bad options: keep 16.7 GiB to
serve a handful of borrows, or break a PROTECTED arm.

Measuring turned that into no choice at all. Once `d97fv` goes, the only
remaining borrowers are five PROTECTED arms —
`work-d97prodchk-{mcp1k,mcp2k,ncpi0,nuecc48}` and `work-ncpi0-d99r3prod` — and
between them they pin **119 distinct event dirs = 0.608 GiB**. So
`materialise_20260908.py` copies those 119 in, verifies, and only then is the
16.7 GiB substrate releasable. Net cost of releasing 35.85 GiB: 0.61 GiB of
copies.

**INTERLOCK 12 (new)** exists because this is the only place in the machinery
where a still-borrowed directory can legally reach a tier. It refuses the round
unless every exempted name is in a tier, the driver implements the step, and the
copy cost has been *measured* — and it independently re-derives the 119 dirs /
0.608 GiB rather than reading it from the script it is checking. It FAILed on the
first plan run, correctly, because the driver did not exist yet.

**THE DEFECT THE DRY RUN CAUGHT.** The first version materialised for *every*
borrower, including `work-*-d97fv` — which this same tier deletes. It would have
copied **14.736 GiB** into three directories that the next step removes: a round
that adds 14.7 GiB, spends twenty minutes of I/O, and then frees it again, with
no error anywhere and a correct-looking final number. The fix reads the release
set from the tier file instead of assuming it, and refuses outright if that file
is missing. After the fix: 138 links, 119 sources, 0.608 GiB — matching
INTERLOCK 12's independent count exactly.

**THE CONFIRM PATH WAS EXERCISED, NOT JUST DRY-RUN.** Five clean dry runs on
09-06 hid three defects that lived only in the `CONFIRM=yes` branch, and the fix
for one of them introduced a fourth. So `materialise_20260908.py` carries a
`STUB=<dir>` mode that builds a miniature of the real shape — a substrate arm, a
borrower with a **directory** link and a borrower with a **file** link, both
forms the tree actually uses — and runs the real writing branch over it:

```
materialised 2 links
VERIFY OK: 0 links left into the substrate, 2 files SHA-256-identical, every destination whole.
```

with three checks that a passing run alone would not give:

1. **A causal negative control.** Delete the stub's substrate afterwards and the
   borrower still reads its data byte-for-byte, 0 broken symlinks. That is the
   thing the step exists to guarantee, tested by doing the exact damage it
   protects against.
2. **The refusal fires.** Pointed at a stub with a dangling source, it exits
   non-zero with *"REFUSING: 1 sources already missing — that is what pointing at
   an executed round looks like"*. A guard that has never been seen to refuse is
   not known to work.
3. **Idempotence.** A second `CONFIRM=yes` run reports "nothing borrows" and
   writes nothing — which is also what a re-run after a partial interruption
   looks like.

**INTERLOCK M** in the retire driver then re-derives the same fact from the tree
at confirm time rather than trusting that the step ran: if any link still
resolves into grp0825, it refuses and prints the command to fix it.

## 4. pdvd and pdhd release nothing, and that is the answer

Both trees were planned with the same machinery and both come back empty. This
is not a tier I failed to write:

- **Every arm family in both trees carries at least one doc citation.** Measured
  over 33 families by hand and 5907 tokens by census.
- **The largest families are the newest.** pdhd `d09` is 10.18 GiB / 61 dirs and
  belongs to `docs/09_pdhd-space-charge-fiducial.md`, dated **09-07**. pdvd
  `d51vclus` is 3.29 GiB and belongs to doc pdvd/50, edited **today**. An arm
  backing yesterday's decision is not superseded — the 08-31 prod0825 doctrine.
- **The bulk is substrate.** pdhd: 11 GiB of 38 bare `029107_<N>` dirs + 3.6 GiB
  `allpd*`. pdvd: `keep` (6.91 GiB, the SP+DNNROI frames) + `d27fresh` (8.44 GiB,
  `stage_pr_tag.sh:7`'s documented default).

**A live round with no doc yet is the shape a citation census scores zero.**
`d51v*` (480 dirs) and `d51h*` (366 dirs) were written 09-07 and doc pdvd/50 was
still being edited when this round opened. Nothing would have protected them.
They went into both `PROTECTED.txt` files **by prefix** before the first plan
run, together with `d30*`, `d14/d15/d16*`, `d11*`, `d02*` and the live
`stm_michel_labels/smx1` hand scan (a bokeh server was serving it two hours
earlier — M13).

The first plan run still put 17 dirs / 0.15 GiB of `d15trace`, `d16smoke`,
`d14chk`, `d11vprod`, `d30r2*`, `d30r3*` into tier 1 on zero citations. Those are
single-event probes of rounds dated 09-07 and 09-08. **0.15 GiB is not worth
reaching into a live round for**, so the prefixes were widened and both trees
now release nothing. The bytes were never the point in these two trees.

## 5. Open questions for the owner

1. **`pdhd/l1sp_wf_v9`, 11 GiB, 889 589 npz, zero citations.** Named only by the
   two previous cleanup docs — never by an analysis doc. The 09-05 round declined
   to stage it and the reasoning stands: `v5` has a regeneration path on record
   and **no regeneration path was found for `v9`**. Zero citations on an
   11 GiB tree with no way to rebuild it is the trap, not the licence. Decidable
   in one sentence by whoever knows whether v9 is still wanted.
2. **`~/tmp` pin deletion is poor value and the naive number is misleading.**
   Dropping the eight pr/144–146 pins looks like 8.96 GiB by `du`; after the
   dedup it frees **2.41 GiB**, because a pin is ~19 shared objects of which a
   round rebuilds one. The doc pdvd/30 pins are 5.60 GiB naive → **1.82 GiB**
   real. And pr/148 is open and reads `d145np`, whose pin is `d145_libpin`.
   Recommendation: **run the dedup, delete no pins.** (Doc 100 over-quoted an
   archive re-encode by 10× for exactly this reason; this is that lesson applied
   before quoting rather than after.)

## 6. Interlocks, and the record layer

13 checks per tree, 0 FAIL. Carried unchanged from the 09-06 machinery:
substrate presence (1), no kept symlink into a releasing dir (2), live-writer
guard by `ps`+mtime double-sample (3), pre-existing broken symlinks recorded
*before* the round so the post-state number means something (4 — 0/0/0), tier 1
clear of PROTECTED.txt (5), token-boundary cross-repo citation (6), no
record/label dir released (7), never delete through a symlink (8), manifest
resolution (9), every tier family exists and carries a ground (10), every
substrate/production name resolves (11). New this round: **12**, the
materialise-is-priced-and-implemented check, and **M**, the driver's confirm-time
re-derivation that the copies actually happened.

Record layer frozen **before** any deletion (M13), in a fresh directory —
`archive/records/cleanup-20260908/sbnd-tier2/`, 119 MiB for 35.85 GiB released.
Per released arm: a `.manifest.tsv` with a SHA-256 and size for every file, a
`.links.txt` recording symlinks rather than following them, and a `.tar.zst` of
the non-heavy record layer (logs, compiled configs, per-event tables, timing
series). Verified: **manifest line count equals the live file count on all 12
arms** — 67 522 files, no short file.

## 7. What is committed here

```
pdhd/scripts/retire/plan_20260908.py             the planner (13 interlocks)
pdhd/scripts/retire/materialise_20260908.py      the cut-loose step + its STUB mode
pdhd/scripts/retire/retire_20260908.sh           the deletion driver (+ INTERLOCK M)
pdhd/scripts/retire/archive_records_20260908.py  the record freeze (already run)
pdhd/scripts/retire/{toks,cit}_20260908.py       the citation census
pdhd/scripts/retire/tier{1,2,3,4}_{sbnd,pdvd,pdhd}_20260908.txt
pdhd/scripts/retire/{plan_20260908.out,retire_dry_t{1,2}_20260908.log,
                     materialise_dry_20260908.log,archive_t2_20260908.log}
{sbnd/sbnd_xin,pdvd,pdhd}/scripts/retire/PROTECTED.txt   live-round + campaign protections
```

Every log this round wrote carries the `20260908` stamp. The first pass did not
— it reused `retire_dry_t{1,2}.log`, which are the **09-06 round's** committed
dry-run records, and overwrote them. Caught by `git status` before the commit and
restored from HEAD; the new logs were re-cut under stamped names. A round's log
filename is part of the record layer, not scratch (M13).

`PROTECTED.txt` gained the new campaign and the live rounds, and a **STAGED FOR
RETIREMENT** block naming the three families this round releases. Those three
lines still protect exactly as before; they move to `RETIRED` only after the
owner's `CONFIRM=yes`.
