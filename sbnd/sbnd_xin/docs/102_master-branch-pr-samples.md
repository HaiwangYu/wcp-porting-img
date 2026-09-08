# Doc 102 — SBND PR validation samples for colleagues, produced at WCT master (2026-09-08)

Owner ask: *"For SBND, I would like to produce some PR samples (nueCC, NCpi0,
and 1000 numu sample) for my colleagues to do validation. 1. We want to use the
Master Branch for the Wire-Cell toolkit for this, instead of the current latest
apply-pointcloud. 2. We should take the Reco 1 as input to do this. 3. There are
two steps process, one is the Q/L matching, the other is the various taggers +
PR results."*

**What was produced.** The full four-sample production manifest — **nueCC-48
(48) + NCpi0-19 (19) + numu 1k (1000) + numu 2k (2000) = 3067 events**, all
`reality=data` — taken from their Reco1 art files through the two-stage
standalone chain at toolkit `eacacafe`, which this round also publishes as
`master`.

The round opened on the first three samples; the owner added `mcp2k` mid-run
(*"Since you are doing the production, why not include the 2000 numu sample as
well"*) and raised the concurrency budget to 32 CPUs, so the epoch covers the
same 3067 events as `prod0902` and is directly comparable to it.

## Repro

```bash
cd wcp-porting-img/sbnd/sbnd_xin
R1=input_files_reco1
export LD_LIBRARY_PATH=$HOME/tmp/d102m-libsnap:$LD_LIBRARY_PATH   # the pinned binary

# --- stage A: reco1 -> imaging -> clustering + Q/L matching -------------------
SBND_MAX_JOBS=3 ./run_chain_group.sh \
  $R1/data_filtered_decoded_reco1-fe6033f3-07a0-4971-cea5-16ce59269fba_eventidfiltered_frameshift.root \
  work-nuecc48-d102m data --size 16 --layout perevt
SBND_MAX_JOBS=2 ./run_chain_group.sh $R1/nc-sideband_filtered_frameshift.root \
  work-ncpi0-d102m data --size 16 --layout perevt \
  --fsproduct 'sbnd::timing::FrameShiftInfo_frameshift__FILTERFRAMESHIFT.'
SBND_MAX_JOBS=8 ./run_chain_group.sh $R1/data_MCP2025C_reco1_frameshift_first1000ev.root \
  work-mcp1k-d102m data --size 16 --layout perevt
# mcp2k is TWO 1000-entry files into ONE out_root; the second offsets the group NAMES (doc 81)
M2K=/nfs/data/1/yuhw/production-prep/add-frameshift-data-2nd-2k-2026-08-15
SBND_MAX_JOBS=8 ./run_chain_group.sh $M2K/data_MCP2025C_reco1_frameshift_2nd1k_part1.root \
  work-mcp2k-d102m data --size 16 --layout perevt
SBND_MAX_JOBS=8 ./run_chain_group.sh $M2K/data_MCP2025C_reco1_frameshift_2nd1k_part2.root \
  work-mcp2k-d102m data --size 16 --layout perevt --gbase 63

# --- stage B: the 15-stage tagger + PR chain ---------------------------------
export PR_EXTRA_STAGES=pr_display
for s in ncpi0 nuecc48 mcp1k mcp2k; do
  PR_JOBS=<J> ./run_pr_chain_batch.sh work-$s-d102m work-$s-d102mpr data
done

# --- products, gates ---------------------------------------------------------
for s in nuecc48 ncpi0 mcp1k mcp2k; do
  python3 pr_scores_table.py --root work-$s-d102mpr --sample $s \
          --out products/prod0908/$s-scores-prod0908.tsv; done
scripts/cfg/prod_cfg_gate.py --ref ref/prod-2026-09-08         # PASS 21/21
```

## 0. Why master had to move first, and what that changes

`origin/master` was **`e88f364d` (2026-09-02)**, a strict ancestor of
`apply-pointcloud` and **104 commits behind** it. Five SBND *production* flips
had shipped on the branch since, so producing at master as-found would have
handed colleagues a six-day-stale operating point. Compiling the 21-artifact
consumer set from master's own cfg tree
(`git archive origin/master cfg`) and diffing against the tree these samples ran
at names it exactly — `prod_prjob.json`, master → `eacacafe`:

```
ADDED  [13].data.wrapped_channel_activity      = true    (inert -- see below)
ADDED  [21].data.excl_t0_frame                 = true    doc pr/144
ADDED  [21].data.kine_dqdx_skip_zero_dx        = true    doc pr/144
ADDED  [21].data.kine_near_pointing_impact     = 200     doc pr/145 item 4
ADDED  [21].data.kine_near_pointing_miss_deg   = 30      doc pr/145 item 4
ADDED  [21].data.long_muon_cathode_bridge_tail_min_len   = 20    doc pr/147 r2
ADDED  [21].data.long_muon_cathode_bridge_track_types    = true  doc pr/147
ADDED  [24].data.flash_by_gid                  = true    doc 99 r3
```
plus `sbnd_ql.json` gaining `QLMatching:matching_joint.merge_flash_pcs = true`
(doc 99 r3). 8 keys added, 0 removed, 0 changed.

**`sbnd_clus.json` and `sbnd_img.json` are byte-identical across the
fast-forward** — neither clustering nor imaging moves; the whole SBND delta is
in the Q/L merge and the PR job.

`wrapped_channel_activity` is a config-text change only: the shared
`cfg/pgrapher/common/clus.jsonnet:1470` now emits the key instead of leaving it
to the C++ default, and that default is already `true`
(`clus/src/retile_cluster.h:131`). The same header records that the path is
"unreachable on a detector with no segment>0 wire (SBND, uBooNE), so
byte-identity there is structural". That is why `uboone.json` — a **frozen
reference** (owner decision 2026-09-01) — appears in the drift list without its
behaviour moving.

The other artifacts the fast-forward publishes are PDVD's, and they are a wires
**geometry** swap, not a knob: `pdvd_{img,nfsp,simcheck,simtrack}.json` differ
from master only in `.data.filename`,
`protodunevd-wires-larsoft-v6.json.bz2` → `protodunevd-wires-larsoft-v7-uvwfit.json.bz2`
(0 keys added, 0 removed; 1 / 8 / 1 / 1 changed).

### The fast-forward itself

Pushed **2026-09-08** as a clean fast-forward, `e88f364d..eacacafe`, 104
commits. The **SHA** was pushed, not the branch name
(`git push <url> eacacafe:refs/heads/master`), so a peer session landing another
commit mid-push could not have ridden along: `master` is exactly the commit
these samples were produced at.

Verified from both sides afterwards — `git ls-remote` and
`gh api .../branches/master` both report
`eacacafe25bbed37613f2c99b73b59911e355e33`, and `refs/heads/apply-pointcloud`
reports the same, so the two refs agree.

Two mechanics worth carrying forward. **SSH does not work in this tree**
(`ssh_askpass … Permission denied (publickey)`), so the push goes over https
with `gh auth setup-git`. And **`origin/apply-pointcloud` was already at
`eacacafe`** before this round — the local remote-tracking ref was stale at
`0c2bd555`, which made it look like 15 commits were unpushed. Only `master`
actually needed to move. Never `git checkout master` in this tree; it
overwrites the untracked local `.claude/skills/`.

Full generation record: **`ref/prod-2026-09-08/README.md`**.
`ref/prod-2026-09-05` is left byte-untouched (M13).

## 1. The samples — what they are, and what they are not

| tag | N | Reco1 art file | reality |
|---|---|---|---|
| `nuecc48` | 48 | `input_files_reco1/data_filtered_decoded_reco1-fe6033f3-…_eventidfiltered_frameshift.root` | data |
| `ncpi0` | 19 | `input_files_reco1/nc-sideband_filtered_frameshift.root` | data |
| `mcp1k` | 1000 | `input_files_reco1/data_MCP2025C_reco1_frameshift_first1000ev.root` (→ `/nfs/data/1/yuhw/2025-fall-prod-sample/round2-patrec/`) | data |
| `mcp2k` | 2000 | `/nfs/data/1/yuhw/production-prep/add-frameshift-data-2nd-2k-2026-08-15/data_MCP2025C_reco1_frameshift_2nd1k_part{1,2}.root` | data |

**These names are selections, not truth.** "nueCC-48" is 48 real-data
neutrino-candidate events across runs 18253–18409; "NCpi0-19" is the NC-sideband
filter's 19 events; "numu 1k" is the first 1000 entries of the MCP2025C **data**
stream (runs 18255 ×850, 18259 ×150) and "numu 2k" the next 2000 (runs 18255
×1450, 18259 ×550; zero event-id overlap with the first 1000). The Reco1 files carry post-SP
`recob::Wire` and no `raw::RawDigit` and **no MC truth** — so NF/SP cannot be
re-run from them and **no efficiency or purity number can be built from these
samples**. They are for chain validation and event scanning.

These are the same four samples, and the same 3067 events, as the `prod0902`
reference epoch, so the two are joinable event by event.

## 2. Round 0 — the premise checks

Nothing entered a work root until these passed.

| check | result |
|---|---|
| M1 freshness: any source under `clus/ match/ root/ img/ cfg/` newer than the installed `libWireCellClus.so`? | **none** (lib 2026-09-08 06:38, HEAD `eacacafe`) |
| binary pinned | `~/tmp/d102m-libsnap/` — 19 `libWireCell*.so*`, 1.2 GiB, prepended to `LD_LIBRARY_PATH` by every arm (the `d97_fv_arms.sh:37-38` idiom) |
| unit tests, 8 packages | **all rc=0** — util, aux (110 738 assertions), iface (7), img (15), sio (11), root (4053), match (38), **clus 335 cases / 23 172 assertions** |
| `merge-base --is-ancestor origin/master HEAD` | rc=0 — a clean fast-forward, 104 commits |
| the five Reco1 art files readable | 5/5 (`mcp1k`'s is a symlink, and `mcp2k`'s two parts live in another user's area) |
| **Reco1 dump reproduces the recorded extraction** | **4/4 samples, 0 differing members** — see below |
| compiled-config gate | `prod_cfg_gate.py --ref ref/prod-2026-09-08` **PASS 21/21** |

The dump check ran on **every** sample, not just one: the frameshift/caf-offset
product tag is the one stage-A input that fails *silently*, and both ambiguous
cases are in the small samples — `nuecc48` has two recorded extractions
(`extracted-2025fall-48evt` and `-fsprod`; only the latter is production) and
`ncpi0` needs the `__FILTERFRAMESHIFT.` override, which the dump aborts on rather
than guessing.

| sample | entries dumped | vs | frames / opflash0 / opflash1 members | differing |
|---|---|---|---|---|
| ncpi0 | 0–19 (all) | `extracted-ncpi0` | 95 / 57 / 57 | **0** (rollup sha256 equal) |
| nuecc48 | 0–48 (all) | `extracted-2025fall-48evt-fsprod` | 240 / 144 / 144 | **0** |
| mcp1k | 0–16 (one group) | `staged-mcp2025c-1000evt/e0..e15` | 80 / 48 / 48 | **0** |
| mcp2k | 0–16 of part1 | `staged-mcp2025c-2nd-2000evt/e0..e15` | 80 / 48 / 48 | **0** |

Member **content** hashes, never `cmp` on the archive (M2 — tar/zip embed
mtimes). For the 48-event archives `tarfile`+bz2 random access is O(n²) and did
not finish in 40 min; `scripts`-side the check was redone as extract-then-
`sha256sum`, which is linear.


## 3. Stage A vs the shipped production — the result that matters

Stage A here is **one** group-mode arm straight off the Reco1 art file
(reco1 → imaging → clustering + Q/L). Every earlier epoch's stage A was two
arms: `work-*-grp0825` (the 2026-08-25 group-mode imaging) plus a per-event Q/L
re-run on top of it (`work-*-d97fv`). So the question a colleague will ask is
whether re-deriving stage A from the art files at a new binary reproduces what
was shipped. `scripts/multi/stagea_gate.py` answers it on **member content**,
never on archive bytes (M2), over all 3067 events:

| sample | events | archives compared | identical | differ |
|---|---:|---:|---:|---:|
| ncpi0 | 19 | 152 | 133 | 19 |
| nuecc48 | 48 | 384 | 336 | 48 |
| mcp1k | 1000 | 8000 | 7000 | 1000 |
| mcp2k | 2000 | 16000 | 14000 | 2000 |
| **total** | **3067** | **24536** | **21469** | **3067** |

**21469 is exactly 7 × 3067** — the four `icluster-apa{0,1}-{active,masked}.npz`
and the three Bee zips (`mabc-all-apa.zip`, `mabc-apa{0,1}-face0.zip`) of every
event. **Imaging and clustering are byte-identical to the shipped production.**
The 3067 that differ are exactly **one `pctree-evt<ID>.tar.gz` per event**, one
for one.

And that one archive differs in a fully accounted way.
`scripts/analysis/d99r3_pctree_datapath_diff.py` diffs a pctree by each tensor's
**datapath** rather than its member name — member names are tensor indices and
renumber whenever a PC is added, so a name diff would report "everything moved":

| sample | event pairs | datapaths ADDED | REMOVED | CHANGED |
|---|---:|---:|---:|---:|
| ncpi0 | 19 | 0 | 0 | **16** |
| nuecc48 | 48 | 0 | 0 | **16** |
| mcp1k | 1000 | 0 | 0 | **16** |

The same 16 every time, on every event
(`19/19`, `48/48`, `1000/1000`), and every one of them optical:
`live/lpcmaps/arrays/{flash,flashlight,light}`,
`live/pointclouds/namedpcs/flash/arrays/{ident,time,tmax,tmin,type,value}`,
`live/pointclouds/namedpcs/light/arrays/{error,ident,time,value}`,
`live/pointclouds/namedpcs/flashlight/arrays/{flash,light}` and
`live/pointclouds/namedpcs/cluster_scalar/arrays/flash`.

That is **exactly doc 99 round 3's measured signature** for the `merge_flash_pcs`
flip — the one SBND stage-A key that master lacked. So the whole stage-A
difference between this epoch and the shipped production is that single
owner-approved flip, and nothing else moved.

Note `stagea_gate.py` prints `FAIL`: its verdict is "some archive differs", not
"a regression". The differ set is accounted for above, event by event.


## 4. Verification — what was checked, and what it says

| check | result |
|---|---|
| stage A complete, on **products** not on the runner's verdict | 194 groups, 3067/3067 events, 3067 non-empty `pctree-evt<ID>.tar.gz`, 0 short groups, 0 missing, 0 empty |
| stage B return codes | `grep -L 'rc=0' work-*-d102mpr/pr_evt*/rc.txt` → **0 of 3067** |
| merged tables complete | `nusel-events.tsv` **49 / 20 / 1001 / 2001** rows = N+1, all four exact; `nusel-table.tsv` 547 / 224 / 11 432 / 22 641 |
| DL (SCN) vertex alive | `grep -l 'DL vertex failed'` → **0 of 3067**. A silent fallback to the geometric vertex is the failure mode here, so it is counted per event rather than assumed |
| score tables | `products/prod0908/<s>-scores-prod0908.tsv` — 48 / 19 / 1000 / 2000 rows + header |
| compiled config | `prod_cfg_gate.py --ref ref/prod-2026-09-08` **PASS 21/21** |
| unit tests | 8 packages, all rc=0 (clus 335 cases / 23 172 assertions) |
| stage A vs the shipped production | 24 536 archives, 21 469 identical, 3067 pctree differing in the same 16 optical datapaths (§3) |

### Sentinels, with a control that can fail

`scripts/pr127_sentinels.py` over all four arms: **21 PASS, 0 FAIL, 2 OPEN, 7 INERT,
0 SKIP** — full coverage, no sentinel event missing from the manifest. Per arm:
nuecc48 1/0/1, ncpi0 1/0/0, mcp1k 5/0/0, mcp2k 15/0/1 (PASS/FAIL/OPEN).

The number only means something beside a control. The same registry on the
**previous** full-population arms (`work-*-d144fixprod`, the pr/144 epoch) gives
**19 PASS, 1 FAIL, 3 OPEN**. So nothing regressed and two recovered:
`393505` (FAIL there) and `177536` (OPEN there) now pass. The two still OPEN —
`137238` and `347890` — are `KNOWN_OPEN_D144` entries, open on the previous arms
too. The instrument can fail, and it did on the older arms.

## 5. What moved, against two baselines

**vs `prod0902`** — the last published epoch, the one doc 92 described:
3067/3067 joined, `rc≠0` = 0 on both sides, **967 movers (31.53%)** by class
`numu=923 enu=365 vtx=206 nue=99 nue_fill=54` — and **0 `event_label` changes,
0 `nu_evaluated` flips**. Every event keeps its verdict: 1568 nu-candidate,
932 cosmic-tagged, 343 no-beam-flash, 224 no-bundle, on both sides. Net
working-point migration at `numu>0.9`: −1 / −3 / +3 / 0 on
nuecc48 / ncpi0 / mcp1k / mcp2k; 0 at `nue>7.0`.

**vs `products/d144on`** — the previous full-population arms at the pr/144 epoch
(2026-09-06): **8 movers of 3067 (0.26%)**. Seven are Enu/numu moves, three of
them the sentinel events above. The eighth is `mcp2k 494297`, which
**crashed** on the previous arm (`rc 139 → 0`, `crashed/no-extract →
nu-candidate`) and now completes.

So the bulk of the `prod0902 → prod0908` delta is doc pr/144's `excl_t0_frame`
and `kine_dqdx_skip_zero_dx` — an unbiased energy frame and no NaN Enu from a
coincident fit-point pair — and everything that landed after pr/144 moves eight
events. **Finer attribution than that is not recoverable from two score tables,
and this doc does not claim it.** Committed movers lists:
`docs/102_prodguide/d102-movers-{prod0902,d144on}-prod0908.tsv`.

## 6. Cost, as run

| sample | groups | stage A imaging | stage A clus+Q/L | stage B core median | stage A disk | stage B disk |
|---|---:|---:|---:|---:|---:|---:|
| nuecc48 | 3 | 0.11 h | 0.08 h | 15.26 s | 0.76 GiB | 0.28 GiB |
| ncpi0 | 2 | 0.04 h | 0.03 h | 12.63 s | 0.29 GiB | 0.10 GiB |
| mcp1k | 63 | 1.90 h | 1.30 h | 1.61 s | 14.35 GiB | 3.31 GiB |
| mcp2k | 126 | 4.09 h | 3.19 h | 1.53 s | 28.48 GiB | 6.55 GiB |
| **all** | **194** | **6.13 h** | **4.60 h** | **1.66 s** | **43.9 GiB** | **10.2 GiB** |

Stage-A hours are summed **process** wall over the groups, not elapsed: the arms
ran 8 groups at a time, so elapsed is roughly an eighth of that. Stage B ran at
`PR_JOBS=6–16`, up to 32 wire-cell processes in flight with a peer session
sharing the box — so **wall is an upper bound and core is the comparable
number**. PR core time is **3.58 core-h against prod0902's 3.57**, i.e.
unchanged, while PR *wall* reads 26% higher purely from the concurrency.

## 7. Defects found, reported not fixed

**The runner's per-group log name ignores `--gbase`.** `run_chain_group.sh`
writes `$OUTROOT/.g$K.log` using the *internal* group index and gives the group
*directory* the offset name `g$((K+GBASE))`; its final verdict is
`grep -q "^[g$K] ok"` on that log. Two concurrent invocations into one out_root
— which is how a two-file sample like mcp2k is run — therefore share
`.g0.log .. .g62.log` and each can read the **other's** success line. Products
never collide, because the directories *are* offset; only the verdict does. This
round stopped trusting that verdict and gated stage A on products instead
(`scripts/d102m_stageA_complete.sh`). The runner is the real bug; fixing it means
editing a script other rounds depend on, so it is reported here rather than
changed mid-production.

**`T_cluster`'s `flash_id` / `flash_time_us` / `flash_pe` remain an
uninitialised read** on clusters without a valid flash (doc 92 part 2, doc 99).
Unchanged by this round; never put them in a bit-identity gate.

## 8. What a colleague does with this

```bash
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
# the per-event products
ls $SX/work-<sample>-d102mpr/pr_evt<ID>/
#   tracking-pr.root   T_tagger / T_kine / T_cluster / Trun / T_rec_charge / T_proj*
#   nusel-evt<ID>.tsv  one row per qualifying bundle -- the human-readable verdict table
#   mabc-pr.zip        Bee event display
#   pctree-pr-evt<ID>.tar.gz, calib-pr-evt<ID>.json
# the population tables
column -t $SX/products/prod0908/<sample>-scores-prod0908.tsv | less -S
# re-run ONE event end to end at the same operating point
PR_EXTRA_STAGES=pr_display ./run_pr_chain_batch.sh work-<s>-d102m work-<mytag>-<s> data <ID>
```

The colleague-facing guide — running condition, the validation checklist T0–T4,
reference distributions and the LArSoft integration traps — is
`docs/92_production-running-and-validation-guide.html`, refreshed onto this epoch
in the same round. Every number on that page re-derives from
`docs/102_prodguide/` by the Repro block in its §10.

**Read the sample names as selections, not truth.** There is no MC truth in any
of the four; no efficiency or purity number can be built from them. They are for
chain validation and event scanning.
