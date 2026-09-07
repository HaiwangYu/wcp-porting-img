# doc 101 — cleanup round 2026-09-06: sbnd_xin + pdvd + pdhd + ~/tmp

Owner, 2026-09-06: *"clean up a bit the disk like what we had before for
sbnd_xin, pdvd, pdhd, and ~/tmp. For each arm, we want to keep the input as well
as the latest production. For the rest intermediate debugging outputs we can
retire them."*

**STAGED. NOTHING IS DELETED.** 33 of 33 work-dir interlocks PASS, 0 FAIL; the
record layer of all 1559 releasing dirs is frozen; both dry runs are clean. The
`CONFIRM=yes` steps are the owner's, as every round since 09-01 records.

## 0. Repro

```bash
cd /home/xqian/toolkit-dev/wcp-porting-img/pdhd/scripts/retire

# 1. the citation census (~5 min; writes toks.json + cit_20260906.json)
python3 toks_20260906.py
python3 cit_20260906.py toks.txt cit_20260906.json

# 2. the plan -- retires nothing, writes tier{1,2}_{sbnd,pdvd,pdhd}_20260906.txt
python3 plan_20260906.py            # 33/33 PASS, exit 0

# 3. freeze the record layer BEFORE any deletion (the driver refuses without it)
python3 archive_records_20260906.py 1     #   97/97
python3 archive_records_20260906.py 2     # 1462/1462

# 4. dry runs
./retire_20260906.sh 1 ; ./retire_20260906.sh 2
./sweep_tmp_20260906.sh 1 ; ./sweep_tmp_20260906.sh 2 ; ./sweep_tmp_20260906.sh 3

# 5. execute -- OWNER ONLY.  Tier 1 and tier 2 are separate runs on purpose.
CONFIRM=yes ./retire_20260906.sh 1
CONFIRM=yes ./sweep_tmp_20260906.sh 1
# ... and, if the tier-2 cost below is accepted:
CONFIRM=yes ./retire_20260906.sh 2
CONFIRM=yes ./sweep_tmp_20260906.sh 2
CONFIRM=yes ./sweep_tmp_20260906.sh 3
```

## 1. What is staged

| tree | before | tier 1 | tier 2 | after (both) |
|---|---|---|---|---|
| `sbnd_xin` | 148 G (`work-*` 133.0 GiB, 227 arms) | 24 dirs / **0.42 GiB** | 22 dirs / **72.49 GiB** | ~75 G |
| `pdvd` | 54 G (3680 arm dirs, 122 arms) | 39 dirs / **0.27 GiB** | 1200 dirs / **12.11 GiB** | ~42 G |
| `pdhd` | 42 G (1191 arm dirs, 114 arms) | 34 dirs / **0.20 GiB** | 240 dirs / **5.86 GiB** | ~36 G |
| `~/tmp` | 98 G | **8.92 GiB** | 11.20 + 20.37 = **31.57 GiB** | ~57 G |
| | | **9.81 GiB** | **122.03 GiB** | |

**131.84 GiB total**, against 399 G free on `/home/xqian` at plan time.
(Corrected: the first cut of this table and commit `01fc606e`'s subject line
said 10.71 / 132.74 — the work-dir subtotal 0.90 had been added on top of its
own three components. Tier 2 was right.)

The split is deliberately lopsided and that is the honest shape of this tree:
almost everything worth releasing is a **closed round's A/B family**, and every
one of those rounds closed *today*. Tier 1 is what nothing anywhere references.
Tier 2 is named by hand, one ground and one stated cost per family, and takes a
separate `CONFIRM=yes` — agreeing to tier 1 is not agreeing to tier 2.

## 2. What "the input" and "the latest production" are, from primary source

Never the `prod` substring in a name — that is how a cleanup round deletes the
thing it was told to keep.

| tree | the INPUT | the LATEST PRODUCTION | primary source |
|---|---|---|---|
| sbnd | `work-*-grp0825` (imaging substrate; **2028 + 1377 + 96 + 57** inbound links measured this round) + `work-dbg25a-ql` | stage A `work-*-d97fv`; stage B `work-*-d144fixprod` | `pr144_arms.sh:52` and `pr145_prodarm.sh:48` both read `work-$s-d97fv`; doc pr/144 §16.3.1 names `d144fixprod` as the new production arm, 3067/3067 rc=0 |
| pdvd | `keep` → `d27fresh` (+ `d41prov`, `d39r2prov`, `d143pnew`) | `d48nu7` | `stage_pr_tag.sh:7,11` — *"src_tag defaults to d27fresh"*; doc pdvd/48 §11 — *"a fresh 120-event arm on the flipped default is NOT taken here: d48nu7 already is that"* |
| pdhd | the 38 bare `029107_<N>` dirs → `stm0` | `d03nu9` | symlink census: 471 inbound to the bare dirs, 2086 to `stm0`; doc pdhd/03 §2 marks `d03nu9`/`new11` **the shipped binary** |

**`work-*-d97fvpr2` is no longer stage B.** `PROTECTED.txt` still called it
"LATEST PRODUCTION stage B"; doc pr/144 §16.3.1 moved that to `d144fixprod` and
re-baselined the sentinel suite onto it. The line is rewritten and the arms are
in tier 2 — *because* releasing them edits `PROTECTED.txt`, not only the disk,
which is exactly the class of decision that needs an explicit yes.

**"Latest production" is a SET, not one arm.** Four flips landed *after*
`d144fixprod` was cut — pr/145 item 4 (`kine_near_pointing_impact` 200 /
`miss_deg` 30), pr/146's default-OFF `ang_sv` plus its still-open
`kine_sat_cont_keep_deg 25` recommendation, and pr/147's two. There is no
full-sample arm at today's operating point, so `d145prod`, `d147-tailflip`,
`d147-flipchk` and `d146sv25` are all kept as the on-disk evidence for one flip
each, and are now named in `PROTECTED.txt`.

## 3. The defect this round found and fixed: the citation census scored real arms ZERO

The 09-05 census matched arm names **exactly**. Measured today, that missed three
whole shapes:

| shape | example | scored | actually |
|---|---|---|---|
| brace set | doc 98 writes `work-sent97-{mcp1k,mcp2k,ncpi0,nuecc48}` | **0** | 11 |
| template | `pr144_arms.sh:117` writes `work-<s>-d144fixprod` | **0** | 273 |
| bare tail token | doc pdhd/03 writes `d48gatenew` for `work-stmcamp-d48gatenew` | **0** | 1 |
| label roots never scanned | `vertex_labels/` references the vtx105 arms | **0** | **1782**, 1756 of them in `vertex_labels/` |

`work-sent97-*` (the 31/31 sentinel witness, explicitly **not** rebuildable from
production) and `work-vtx105-base-*` survived 09-05 **only because
`PROTECTED.txt` happened to name them**. Nothing else would have caught them.

`cit_20260906.py` now matches on **token boundary** (anything not `[A-Za-z0-9]`,
so `d45on` does not match inside `d45on3` and `em114` does not match inside
`em114c` — doc 91's manufactured protection), over the label/display/product
roots as well as docs and scripts, in two stages so it finishes: `grep -F`
(Aho-Corasick, 5.7k patterns over ~5 GB) pulls candidate lines, then each line is
decomposed into its separator-bounded substrings and looked up in a set.

**Three over-matches had to be killed as well, each measured:**

- the bare **round** token — `d147` alone scores 552, so letting it count as a
  citation of `work-d147-off1-mcp1k` marks every arm of every round "cited" and
  INTERLOCK 6 then keeps the whole tree. A round is not an arm.
- an ordinary **word** — `cone`, from `work-s144neg-cone`, scores **57 017**.
- a **cross-round tail collision** — `off1-mcp1k` scores 132 from a different
  round's arm entirely.

The surviving rule: a proper sub-range counts only if some segment is
round-marked (`d48gatenew`, `s144neg`, `vtx105`, `pr143-on`); the whole dir name
and the whole arm are always emitted, so short real names (`stm0`) and unmarked
family names (`sent97`, `grp0825`) are not lost. **Negative control run each
time**: the fixed census returns non-zero for `sent97`, `vtx105-base`,
`d144fixprod`, `d48nu7`, `stm0`, `d27fresh`, `grp0825`, `probe178410a`,
`tfix388-r9` — and **0** for `d144fix2`, `d144fixchk`, `d147-off1-mcp1k`,
`d45ptdbg`, `d04pgate`, `s144negleg-cone`.

Effect on the plan: 81 sbnd dirs, 264 pdvd dirs and 30 pdhd dirs were **pulled
out of tier 1 by their citations**. sbnd tier 1 fell from 46 dirs to 24 when the
tail-token shape was added — those 22 were the `stmcamp-*` and `d45sbnd-*`
cross-detector gate arms, which the old census could not see.

## 4. The eleven interlocks, and the four that fired

All 33 (11 × 3 trees) PASS in the final plan. Four failed on the first run and
**all four were real defects in my keep lists, not false alarms**:

1. **sbnd INTERLOCK 1 FAIL.** Substrate was resolved against the *arm token*
   only, and sbnd's arm token strips the sample (`work-mcp2k-grp0825` →
   `grp0825`), so the tree's entire imaging substrate reported "absent". Resolve
   by dir name **or** token.
2. **sbnd/pdhd INTERLOCK 10 FAIL.** The tier-2 "every family carries a ground"
   check scored the alias form `as work-mcp1k-d144on.` ungrounded, because the
   greedy character class swallowed the trailing `.`. Fixed and unit-tested with
   a negative control (an alias to a non-existent key, and a too-short ground,
   both still fail).
3. **pdvd INTERLOCK 11 FAIL** (new this round: *does every production/substrate
   name resolve?*). `d48ref2` and `d48new4` were in pdvd's production list and
   **are PDHD arms** — doc pdvd/48 §9 names them as `pdhd/work/029107_0_d48*`.
   A cross-tree name read as a local one. This is the doc 100 §10 shape and
   INTERLOCK 11 exists because doc 100's decisive test was resolution, not
   citation (`em_display`'s manifests name 446 arms and **14** exist).
4. **sbnd INTERLOCK 10, second form.** `work-mcp2k-d145np200` does not exist —
   the pr/145 sweep ran that subset on mcp1k/ncpi0/nuecc48 only. A tier-2 name
   that matches nothing silently frees 0 bytes and looks like a plan.

**New in this round:**

- **INTERLOCK 10** — every tier-2 family must exist, and must carry a written
  ground of its own or an alias to one that does. Tier 2 is never derived.
- **INTERLOCK 11** — every substrate/production name must resolve to a real dir.
- **INTERLOCK A** (in the driver, at *confirm* time) — re-runs the whole plan and
  refuses if any interlock now fails or any tier file moved. A peer session
  started 11 minutes into this round's planning; on 09-04 a live round created
  **seven** new arm families between plan and confirm. A tier file frozen at plan
  time cannot see them, so the driver refuses rather than deletes under a peer.

  **Verified both ways, against a stub whose `rm -rf` is an `echo`** — a guard
  that has only ever been seen to pass is not a guard:

  | run | result |
  |---|---|
  | unperturbed | `OK: all interlocks still PASS and every tier file is unchanged` → reaches the stub, `would rm -rf 24 targets` |
  | one line appended to `tier1_sbnd_20260906.txt` | `CHANGED since plan time: tier1_sbnd_20260906.txt` → `REFUSING`, and the delete never runs |

  The re-plan also *restored* the perturbed tier file, so `git status` on it is
  clean afterwards — the guard corrects as well as refuses.

## 5. `~/tmp`: 98 G, and 51 GiB of it is pinned binaries

Measured at file granularity first, because the 09-05 draft would have deleted
`d44sp`'s 64 `.npy` frames, which doc 44's repro block names as an **input** — a
file is a record by *function*, not by extension.

The result here is unusually clean: **every pin subdir is 100.0 % `*.so` by
bytes**. Dropping one removes zero record bytes by construction, and
`pure_so()` re-checks that at run time rather than trusting this paragraph.

- **tier 1, 8.92 GiB** — `d144_libpin{3,5}`, `d45_libpin/dbg`,
  `d41_libpin/{new2,new3,new4,new5,ref}`. **Nothing outside this round's own
  record names them** — and that qualifier is load-bearing, see §7.1.
  An un-named pin cannot even be invoked, and a missing `LD_LIBRARY_PATH`
  directory is silently ignored (the M1 shape that bit `dbg25_run.sh`), so these
  are already inert. `named()` re-checks at run time and refuses if the count is
  no longer 0.
- **tier 2, 11.20 GiB** — the pins of the arms work-tier 2 releases. A pin goes
  *with* its arms. `d47_libpin/{new5..new10}` back `d03nu1..d03nu8` and doc
  pdhd/03 §2 is an explicit pin ↔ arm ↔ **commit** ledger, which is what makes
  them re-buildable; `d143_libpin/*` backs `work-pr143-*` (md5s in doc pr/143
  §6.1); `d144_libpin` backs `d144on/off` (md5 at doc pr/144 line 51).
  **Kept:** `d47_libpin/new11` (the shipped pdhd/03 + pdvd/48 binary),
  `d144_libpin4` (the current production arm), `d144_libpin2`, `d145_libpin*`,
  `d146_libpin*`, `d08_libpin`, `d97b-libsnap` (the stage-A production binary),
  `pdhdstm_libpin` (pdhd `PROTECTED.txt`).
- **tier 3, 20.37 GiB** — two dead session scratchpads. **Liveness is from `ps`,
  never from age.**

### The guard that matched itself

The first `ps` guard was `ps -o args= | grep -q "$id"`, and it **refused the
round** — because the session id appeared on *my own* command line (and in a
`ugrep` the harness was running). A self-match, the `pgrep` wait-loop shape.
Fixed to match on `comm` (`$1=="claude"`), and verified both ways: it still fires
on a synthetic real `claude --resume <id>` line and no longer fires on a `bash`
line containing the same id.

`1f022d51` came **off** the tier-3 list rather than being forced through: its
session (PID 3026100) exited *during* this round and its scratchpad was written
minutes before the plan. A just-exited session's scratchpad is next round's
decision. The recent-mtime check is now a loud per-item SKIP rather than a
round-level refusal, so one fresh entry no longer hides the verdict on the rest.

## 6. The record layer, frozen before anything is deleted

`archive_records_20260906.py`, **97/97** (tier 1) and **1462/1462** (tier 2),
into `sbnd_xin/archive/records/cleanup-20260906/{sbnd,pdvd,pdhd}-tier{1,2}/`.
**274 MiB for 91.36 GiB released — a 340× reduction.**

Per released dir: a `.manifest.tsv` with **a SHA-256 and a size for every file**
(heavy classes included), a `.links.txt` recording every symlink as
`path → target` (recorded, not followed — many arms are ~40 % symlink into the
kept substrate), and a `.tar.zst` of the non-heavy record layer: per-event
wire-cell logs, the compiled config the arm actually ran, the per-event
`nusel-*.tsv`, timing/rss series, `img-provenance.txt`.

`.wct-*.json` is ~270 KB and byte-identical across an arm's events apart from
the event id — 3067 copies per arm is 800 MB of the same file. **Every copy is
hashed into the manifest; only the first is carried in the tar.** Hash-only
would lose the operating point; all-copies would make the record bigger than the
thing it replaces.

**Verified, not asserted:** `work-mcp2k-d97fvpr2.manifest.tsv` holds 20 909 rows;
an independent `sha256sum` of a row picked out of it MATCHES; its `.tar.zst`
holds 12 004 members.

The record tree is **on disk only** — `sbnd/sbnd_xin/archive/` is excluded in
`.git/info/exclude`, so, as in every prior round, the tarballs and manifests are
not committed and live at 274 MiB in the tree. What *is* committed is the
machinery that produced them and this doc.

## 7.1 Four defects found reviewing the STAGED round, before handing it over

The dry runs were clean, all 33 interlocks passed, and three of these four would
still have destroyed part of the round. All three script bugs are reachable
**only under `CONFIRM=yes`**, which is exactly what a dry run cannot exercise.

1. **The driver would have deleted sbnd and pdvd, then aborted on pdhd.** The
   "record layer must be frozen first" precondition built its path relative to
   `pdhd/` (`$D/../../archive/...`) and resolved to a directory that never
   exists, *and* was gated on `[ "$t" = pdhd ]` — which is **last** in the
   default tree list. So under `CONFIRM=yes` it would have deleted two trees and
   then refused. Recovery would then have hit the "already gone" refusal and
   needed a re-plan. Now points at the real per-tree, per-tier output of
   `archive_records_20260906.py`, for every tree.
2. **The `~/tmp` tier-1 guard read this doc.** `named()` asserts "nothing names
   this path" — and §5 above lists the paths in order to say so, so `grep -F`
   found `d45_libpin/dbg` in §5 and refused the tier **after `d144_libpin{3,5}`
   had already gone**. Doc 91's *protected because protected* defect recurring on
   a new artifact: the round's own **record** instead of its own tier file. The
   round's doc is now excluded and the claim is stated as "nothing outside this
   round's own record".
3. **INTERLOCK A would have refused tier 2 because tier 1 had run.** It compared
   *every* tier file; once tier 1's 97 dirs are gone, the confirm-time re-plan
   regenerates `tier1_*.txt` as **empty** — legitimately — and the comparison
   reports CHANGED. The owner would have seen a peer-session alarm raised by the
   round's own first pass, and the only documented escape (`REPLAN=no`) disables
   the guard entirely. Scoped to the tier being run.
4. **The headline number was wrong.** 10.71 / 132.74 GiB double-counted the
   work-dir subtotal on top of its own three components; the correct figures are
   **9.81 / 131.84**. Corrected in §1 rather than by rewriting history.

**Each of the three script fixes re-verified against a stub whose `rm -rf` is an
`echo`, with a negative control**, because the whole point is that the dry run
could not see them:

| run | result |
|---|---|
| `1 pdhd`, archive present | reaches the stub, `would rm -rf 34 targets` |
| `1 pdhd`, archive path made unreachable | `REFUSING: ...NOSUCH-pdhd missing -- run 'python3 archive_records_20260906.py 1' first.` |
| `1` (all three trees), archive unreachable | refuses on **sbnd**, the FIRST tree — the old code refused on pdhd, the last, after deleting the other two |
| tier-1 sweep, unpatched `named()` | refused on `d45_libpin/dbg` after two entries had gone |
| tier-1 sweep, patched | 8 entries, `named_by=0`, `100% .so`, no refusal |

All five dry runs re-run clean afterwards (`retire_dry_t{1,2}.log`,
`sweep_dry_t{1,2,3}.log`).

Also raised, and taken: **tmp tier 3 held a lower standard than the rest of the
round.** Every released work dir keeps a SHA-256 per file, while tier 3 removed
a scratchpad containing **111 578 non-`.so` files** with no record at all. It now
writes `find`-listing to
`archive/records/cleanup-20260906/tmp-tier3-<id>.listing.txt` before deleting.

## 7.2 Tier 2 — the fat, with its cost stated

Every family below is cited **only by its own closed round's doc**. The full
grounds are in `plan_20260906.py`'s `tier2` dicts, one string per family.

| family | GiB | ground | what becomes text-only |
|---|---|---|---|
| `work-pr143-{on,off,final}` | 29.55 | round closed 09-06; the shipped code *is* the ON arm (§7.1) and `d144fixprod` is a later epoch on the same knob | §7.2's per-event mover table |
| `work-*-d144{on,off}` | 19.7 | the knob is in production; `d144fixprod` is the same point on the crash-fixed binary | doc pr/144 §7's byte gate |
| `work-*-d144fixframeonly` | 10.9 | a decomposition of a shipped change, not the shipped point | the frame/prod split table |
| `work-*-d97fvpr2` | 10.2 | superseded stage B (§2 above); `products/prod0902/` keeps the tables | — |
| `work-*-d145np200` | 2.03 | sweep intermediate; the shipped point (`d145prod`) and the full-sample reference (`d145np`) are both kept | the sweep's middle row |
| pdvd `d48nu{,2,4,5,6}`, `d45{on,on3,skipnu,nu0}`, `d143pref` | 12.11 | iterations the doc itself calls superseded (doc 48 §8.0 says "`d48nu` → `d48nu2`" outright) | the per-iteration deltas |
| pdhd `d03nu1..d03nu8` | 5.86 | the eight knob-bag iterations of doc pdhd/03 §2; `d03nu9` **is** the shipped bag | §§3–6's per-iteration deltas; §7's before/after survives (d03nu1's numbers are quoted there, d03nu9 is on disk) |

## 8. What is NOT staged, and why

- **`pdhd/l1sp_wf_v9`, 11 G, 889 589 npz, zero citations.** Zero citations is the
  *trap* here, not the licence — `v5` has a regeneration path on record and `v9`
  has none I could find. Owner call, carried from 09-05.
- **`/home/xqian/pdvd-frame-store`, 40 G.** doc pdvd/24:46 marks it
  regenerate-only; decidable by checking the raw still resolves. Not checked here.
- **Archive re-encode.** Doc 89/100 measured it at 0.16 GiB on sbnd_xin. Spent.
- **`work-*-d145np` (10.2 GiB) stays** — doc pr/148 §16 names it as the arm the
  next round reads. A doc whose last section is a plan for the next session is an
  **open** round for retire purposes; the same applies to pr/147 §15.3's three
  open items, whose working set is the `d147` prefix.
- **`work-vtx105-base-*` (4.2 GiB) stays** — 1782 references from
  `vertex_labels/`, M13.

## 8.5 EXECUTED 2026-09-06, and the two things execution taught

**Owner ran the `~/tmp` sweep (all three tiers) and then said "go ahead clean up
the directories."** State: `~/tmp` 98 G → 58 G; work tier 1 executed by me,
**97 dirs / 0.89 GiB, rc=0 on all three trees, broken symlinks still 0**
(against the 0 interlock 4 recorded, which is the only reason that means
anything). **Work tier 2 was declined by the permission gate** — as every round
since 09-01 records — so it is the owner's to run.

### A fifth CONFIRM-only defect, introduced by the fix for the third

`CONFIRM=yes ./retire_20260906.sh 1` died with **`line 36: TIER: unbound
variable`**. INTERLOCK A sits above the line that assigns `TIER`, and scoping it
to the running tier (§7.1 item 3) put `${TIER}` into it — the earlier `tier?_*`
glob needed no variable, so the fix created the bug. `set -u` caught it *before*
the loop, so nothing was deleted; all 97 tier-1 dirs were verified present
afterwards. The block now sits below the argument parsing. **The lesson is about
the fix, not the bug:** a correction to a `CONFIRM=yes`-only path is itself
reachable only under `CONFIRM=yes`, and re-running the dry run proves nothing
about it.

### INTERLOCK A then fired on real data, exactly as designed

The next confirm refused with `CHANGED since plan time: tier1_pdhd_20260906.txt`.
Cause: a live peer (PID 2727386) wrote **`028084_18_qlpilot`** and
**`029107_0_qlctrl`** at 21:46/21:48, half an hour *after* the plan — new,
uncited, and therefore swept straight into tier 1 by the re-plan. This is doc
100's seven-families-between-plan-and-confirm scenario, caught this time.
Protected by the **`ql` prefix**, never by naming those two (a name list frozen
at plan time is what fails here); `ql` is safe because the tree's only other
`ql` arm, `qlt`, is already kept. Tier files returned to the committed content
and the interlocks pass again.

## 8.6 `~/tmp`: 26.77 GiB more, with nothing deleted

After the sweep, `~/tmp` was 58 G and **39.06 GiB of it was pinned binaries**.
A pin is a snapshot of `local/lib` — 19 shared objects — and a round rebuilds
**one** of them (usually `libWireCellClus.so`, 410 MB) and copies the rest
unchanged. Measured: **2272 files, 606 distinct contents, and zero existing
hardlinks.** `libWireCellSigProc.so` is byte-identical in 34 pins.

`dedup_pins_20260906.py` makes identical files share an inode:

```
2272 files, 2272 distinct inodes, 39.06 GiB on disk
580 content groups; 1666 files can share an inode; 26.77 GiB recoverable
linked 1666, skipped 0, made read-only 606
VERIFY: 2272 files present (was 2272), 0 missing, 606 inodes, 12.29 GiB
```

**`~/tmp` 58 G → 31 G. Nothing was deleted**: every path stays, every pin stays
complete and runnable, every byte stays readable. That makes it categorically
different from the retire tiers — there is no record to lose and no owner
judgement to make, which is why it did not need a tier of its own.

Safety, in order: group by SHA-256, then `filecmp` **byte-compare the actual
pair** before linking (a hash match is evidence; a byte compare is proof);
`os.link` to a temp name and `os.replace` over the target, so an interruption
can never leave a path missing; refuse on a symlink, a size that moved, or pins
spanning two filesystems.

**The hazard sharing creates, and its mitigation.** Once two paths share an
inode, writing *in place* through one (`cp new.so pin/`, which opens `O_TRUNC`)
corrupts every pin that shares it. Every deduplicated file is therefore made
**read-only**, so `cp` fails loudly instead. Verified: `cp /dev/null` into the
shipped pin returns `Permission denied`. Building a pin the normal way
(`cp -r local/lib ~/tmp/newpin`, a *new* directory) is unaffected.

**Verified, not asserted:** 61 files across three pins — including
`d47_libpin/new11`, the shipped pdhd/03 + pdvd/48 binary, and `d144_libpin4`,
the current SBND production arm's pin — re-hash **identical** to the pre-dedup
record. 0 mismatches.

Disk: `/home/xqian` free **399 G → 466 G**, with work tier 2 still to run.

## 8.7 TIER 3, and where the remaining bytes actually are

Owner, after tiers 1-2 ran: *"there are a lot of work* directories there,
intermediate ones can be cleaned up, right? retire them."*

**Accounted first, because the answer changes what is worth doing.** After
tiers 1-2 the three trees held 109.3 GiB:

| GiB | what |
|---|---|
| 45.0 | **INPUT substrate** — sbnd `grp0825` 15.6, pdvd `keep`/`d27fresh`/`d41prov`/… 18.6, pdhd's 38 bare dirs 10.8 |
| 35.6 | **LATEST PRODUCTION** — `d97fv` 10.0, `d144fixprod` 10.2, `d145np` 10.2, pdvd `d48nu7`/`d48nu3`/`d45prod` 4.3, pdhd `d03nu9` 0.7 |
| 9.6 | **pinned by labels or live manifests** — `vtx105-base` (1782 label refs), the `em_display` arms, pdhd's hand-scan source and structural blind |
| 4.9 | arms backing constants shipped 09-05/06 |
| **14.2** | the residual — **and this figure is wrong, see below** |

So the ceiling was ~14 GiB, not another 90 — the trees are now what was asked
for. **Tier 3 took 7.39 GiB (963 dirs)**.

### CORRECTION: the 14.2 was a residual, not an inventory

That row was computed by **subtraction** (109.3 − 95.1 accounted), and the
accounting table above lists *representative* arms per category, not all of
them. So the residual silently absorbed real keeps — `d97prodchk`, `sent97`,
the `87flip`/`87knob`/`87grp` block, `d99r3prod`, the whole `d147` family. A
residual is not evidence about its own contents, and quoting one as "genuinely
intermediate" overstated what was releasable.

**Inventoried instead of subtracted, after tier 3 ran**, the arms outside every
keep category total **4.47 GiB in 191 arms**:

| GiB | what |
|---|---|
| 0.85 | named in a `PROTECTED.txt` (`87flip`, `87knob-*`, `87grp-*`, …) — releasing these needs an explicit edit to that file, which is the tier-2 class of decision |
| 0.64 | open rounds held by prefix — `d146` (pr/146's still-open `kine_sat_cont_keep_deg 25` recommendation), `d147` (pr/147 §15.3's three open items), `d08` (pdhd doc 08, shipped 09-06) |
| **2.98** | **unclassified tail — 164 of its arms are under 50 MB, median 10 MB** |

So the amount actually still available is **~3.0 GiB, not ~6.8**. Tier 3 stopped
where it did because tier 3 had a *rule* — release the sweep points around a
shipped value whose shipped arm and gate both survive — that could be stated
once and applied to a whole family. The 2.98 GiB tail has no such rule: it is
~164 separate arms at a median of 10 MB, and this project's bar is one written
ground and one stated cost per family. That is roughly **19 MB per judgement
call**, which is why it is priced here rather than done unasked — the same way
doc pr/130's per-knob sentinel retarget was priced and declined.

**If the motivation is tidiness rather than bytes, that changes the answer.**
Doc 91's round was explicitly about directory COUNT, not size — owner: *"they do
not take much disk space, but it is just difficult to look at them"* — and 191
arms is exactly that complaint. A count-driven tier 4 is a different, legitimate
round; it just should not be sold as a disk-space one.

Tier 3's rule is narrower than tier 2's and needs **no `PROTECTED.txt` edit at
all**: it releases the SWEEP POINTS around a shipped value whose shipped arm and
gate both survive. pdhd's ten `d08` cap/merge sweep arms (2.82 GiB) go while
`d08both` + `d08gref`/`d08goff` stay; pdvd's four non-shipped `d43` fiducial
points go while `d43p90c5` (the shipped constant) and `d43prod` stay; sbnd's
`d146` sweep goes while `d146sv25`, the still-open recommendation, stays.

**INTERLOCK 10 needed one more distinction.** With tiers 1-2 executed, every one
of their families reads as "missing" and the check failed on a finished round.
The rule that keeps it sharp: a tier must be **either fully executed (nothing
resolves) or fully resolvable** — a tier where some families resolve and others
do not is the typo case and still fails. It immediately earned that: it caught
`work-mcp1k-d144frameonly`, which never existed (pr/144 ran the frame-only
decomposition on ncpi0 + nuecc48 only).

## 8.8 Final state, verified

| | before | after |
|---|---|---|
| `sbnd_xin` | 148 G | **72 G** |
| `pdvd` | 54 G | **40 G** |
| `pdhd` | 42 G | **34 G** |
| `~/tmp` | 98 G | **31 G** |
| `/home/xqian` free | 399 G | **564 G** |

Remaining releasable after this round: **~3.0 GiB** (§8.7 correction), in 164
arms under 50 MB each.  Released: tier 1 97 dirs / 0.89 GiB, tier 2 1462 / 90.46, tier 3 963 / 7.39,
`~/tmp` sweep 40.49, `~/tmp` dedup 26.77 (nothing deleted). Record layer frozen
for all 2522 released dirs — **97/97 + 1462/1462 + 963/963** — a SHA-256 per
file, in `archive/records/cleanup-20260906/`.

**Post-state, checked rather than assumed:**

- broken symlinks **0 / 0 / 0**, against the 0 interlock 4 recorded beforehand —
  which is the only reason that number means anything;
- sbnd input `grp0825` **3067/3067**, stage A `d97fv` **3067/3067**, stage B
  `d144fixprod` **3067/3067**, current point `d145np` **3067/3067**;
- pdvd `keep` 240, `d27fresh` 120, `d48nu7` 120, `d45prod` 120; pdhd 38 bare
  substrate dirs, `d03nu9` 30, `d08both` 30;
- the paused peer's `qlpilot` + `qlctrl` **both intact**;
- `pr127_sentinels.py` on the current operating point (`work-*-d145np`):
  **20 PASS, 0 FAIL, 3 OPEN, 7 INERT**.

**One sentinel result that looks like a regression and is not.** The same suite
against `work-*-d144fixprod` reads **19 PASS / 1 FAIL / 3 OPEN**, where doc
pr/144 §16.3.1 recorded 19/0/4. The moved entry is 393505, and the cause is in
the registry, not the data: pr/145 **lifted its waiver on 09-06** (commit
`22c51ace`) because the defect it tracked was fixed by the
`kine_near_pointing_impact` flip. `d144fixprod` predates that flip and is the
knob-off control, so it now fails that entry **by design**. Run the suite against
`d145np` for the current point — it is 0 FAIL there.

## 8.9 TIER 4 — the count-driven round, and the arm it cost

Owner: *"I see many work* directories in sbnd_xin, do we need all of them there?
many of them seem to be intermediate files."* This is doc 91's round, not a disk
round. Grounds are written **per round**, not per arm, which turns 170 dirs into
about 12 decisions.

**Released 170 dirs / 2.36 GiB** (sbnd 72 / 1.70, pdvd 55 / 0.43, pdhd 43 /
0.22). **sbnd_xin: 155 → 83 work dirs**, and 227 → 83 across the whole round.

Two families were checked and **kept**, each for a measured reason:

- **`s144pos`/`s144neg`/`s144posleg`/`s144negleg` (14 dirs).**
  `pr127_sentinels.py:311` names `work-s144pos-mcp2k` vs `work-s144neg-dvtx` as
  the 2×2 that establishes which registry entries are INERT, and doc pr/144:131
  runs the suite *with* `'work-s144pos-*'`. They are the negative-control layer —
  the only on-disk proof the suite **can** fail, which is doc 98's lesson, where
  releasing the OFF baseline would have destroyed the only 31/31 arm. And
  `work-s144posleg-mcp2k` is now the sole surviving carrier of
  `work-mcp2k-d144off`'s bytes (byte-identical 6/6).
- **`d147-c8`, `d147-tail8`.** doc pr/147 §§13–14 and §15.3 item 3 — the
  *recommended* next step — read these two arms by name.

### THE ARM THIS ROUND COST: `029107_*_d08cap10`

**Tier 3 released the arm backing a value that shipped to PDHD *and* PDVD
production the same day.** doc pdhd/08 §9.1: *"FLIPPED — `retile_hack_max_bridge
= 10 cm`, PDHD **and** PDVD production, owner 2026-09-06"*, and line 616: *"the
arm taken to the hand scan, and now to production: `retile_hack_max_bridge = 10`,
merge off."* That arm is `d08cap10` (§6 table line 377: *bridge cap **10 cm***).
Tier 3's ground asserted the shipped arm was `d08both` and released the rest of
the sweep. It was wrong, and it violated the very doctrine this doc quotes
elsewhere — an arm backing a just-made decision is not superseded.

**How it was caught, and why not sooner.** INTERLOCK 11 flagged it on the *next*
plan: `d08cap20b` was in pdhd's `production` list and no longer resolved. That
was a contradiction I had written into the planner myself — `production` said one
arm, tier 3's ground said another — and the interlock could only see it after the
deletion, because before it, both names resolved.

**The audit instrument was the real failure.** My first check grepped for
ship/flip words *near* each arm name and returned "no ship/flip sentence" for all
17 tier-3 families, `d08cap10` included. It could not work: a doc names the
shipped **value** in its flip section and the **arm** in its sweep table, in
different sentences. **Audit value-first** — read the flip section for the value,
then find the arm that carries it. Re-audited that way, the other two shipped
constants were fine: pdvd `d43p90c5` (kept) and `d45prod` (kept); the released
`d45skip*` pair carries a null result the doc records (STM 594 = 594, TGM
2549 = 2549).

**Repair.** Owner: *"it is OK, we can reproduce the production run."* Everything
needed survived: the pin `~/tmp/d08_libpin/new2`, the 38-dir input substrate, the
hand-scan labels in `work/d08_scan_labels/`, and **30/30 frozen manifests** with
a SHA-256 per file. Regenerated with the doc's own repro line
(`ARM=d08cap10 PIN=… EXTRA="-S retile_hack_max_bridge=10"`) and checked against
the frozen record — see §8.10.

## 8.10 The repair, proven

`ARM=d08cap10 PIN=~/tmp/d08_libpin/new2 JOBS=8 EXTRA="-S retile_hack_max_bridge=10"
./docs/scripts/run_d08_arms.sh` — **30/30 rc=0**, from doc pdhd/08's own repro
block.

**Inventory:** 30/30 events, **0 mismatches**, 150 files compared against the
frozen manifests.

**Bytes, by class** — and the split is exactly what M2 predicts:

| class | n | same size as the frozen record |
|---|---|---|
| `mabc-pr.zip` | 30 | **30** |
| `tracking-stm.root` | 30 | **30** |
| `pr_resource` / `pr_rss` | 60 | 29 (timing and memory samples) |
| `wct_pr_*.log` | 30 | 0 (timestamps) |

0 of 150 files match by SHA-256, which is **not** evidence of a bad restoration:
zip and ROOT embed mtimes, so a whole-file hash of an archive cannot be equal —
CLAUDE.md M2, the timestamp mirage. Both physics products match to the exact byte
count on every event.

**The decisive check is the physics, not the bytes.** Re-running the doc's own
grader against the surviving `d08goff` reproduces **every column** of doc
pdhd/08's published row 377:

```
arm       matched          >3cm      >10cm    >30cm       worst  unmat | TGM +/-   STM +/-   FC +/-
d08cap10      774   17583->3719    1419->6    17->0  39.2->11.3    7/7 | TGM 0/0  STM 21/24  FC 4/4
doc row 377   774   17583->3719    1419->6    17->0  39.2->11.3          TGM 0/0  STM 21/24  FC 4/4
```

**Negative control, and it is free:** the `d08cap20b` row immediately below in the
same table reads 12 922 / 22 / 13.5 / 18-21 / 3-4. The grader plainly
discriminates operating points, so a regeneration at the wrong knob value could
not have produced this match.

`d08cap10` is back in the planner's `production` list and now has its own
`PROTECTED.txt` line — carrying the value-first audit rule, so the next round
cannot repeat this.

## 9. Files

Machinery (`pdhd/scripts/retire/`): `toks_20260906.py`, `cit_20260906.py`,
`plan_20260906.py`, `archive_records_20260906.py`, `retire_20260906.sh`,
`sweep_tmp_20260906.sh`, `tier{1,2}_{sbnd,pdvd,pdhd}_20260906.txt`,
`plan_20260906.out`, `sweep_dry_t{1,2,3}.log`, `retire_dry_t{1,2}.log`,
`dedup_pins_20260906.py`.

`PROTECTED.txt`: **pdvd gets its first one** (it had machinery since 09-04 but no
carry-forward list); sbnd's stage-B line is rewritten; pdhd gains the
CheckSTM_Michel block and its own RETIRED entries.
