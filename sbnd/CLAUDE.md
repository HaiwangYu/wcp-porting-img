- base knowledge: /exp/sbnd/app/users/yuhw/claude-utilities
  - especially how to run things in sl7: /exp/sbnd/app/users/yuhw/claude-utilities/wct-in-sl7.md
- in sl7, use a setup sript to setup ups products, LD_LIBRARY_PATH, WIRECELL_PATH etc.
- local WCT: /exp/sbnd/app/users/yuhw/wire-cell-toolkit (branch `ap-yuhw`, forked from `apply-pointcloud` at 0442bc27 so we have full control; use `ap-yuhw` from now on. `ap-yuhw` tracks the `fork` remote = git@github.com:HaiwangYu/wire-cell-toolkit.git; `origin` = WireCell/wire-cell-toolkit. do NOT commit/push on my own — keep edits local for review)
- local larwirecell: /exp/sbnd/app/users/yuhw/larsoft-wct036/v10_14_02/srcs/larwirecell (MRB tree; the ONLY larwirecell tree to use — do NOT use /exp/sbnd/app/users/yuhw/larwirecell)
- delete transient "status marker" files (e.g. `SMOKE_STATUS`, exit-code/lar-exit stamps) after a run unless they contain important debug information; do not leave them in the tree.

## Running in SL7

Everything runs inside the apptainer; non-interactive shells need `.bashrc` first:
```
/cvmfs/oasis.opensciencegrid.org/mis/apptainer/current/bin/apptainer exec \
  -B /cvmfs,/exp,/nashome,/pnfs /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-dev-sl7:latest bash -c '
  source /nashome/y/yuhw/.bashrc
  source <setup script>
  cd /exp/sbnd/app/users/yuhw/wcp-porting-img/sbnd
  <lar / wire-cell ...> '
```
- `setup-local-opt.sh` — legacy `opt` install; sbndcode cfg wins (use for sim and the OLD matching chain).
- `setup-ap.sh` — AP matching/imaging env: setup-local-opt.sh + prepend toolkit cfg (so toolkit img/clus/qlmatching/simparams win, Xin's env) + sbnd_xin + wire-cell-data/sbnd/photodet. Use ONLY for the AP chain, not sim.

### samweb / SAM queries

`samweb` works **only inside SL7 with the ups environment set up**:
```
in-gpvm-sl7.sh bash -c '
  source /nashome/y/yuhw/.bashrc
  source .../sbnd/setup-local-opt.sh
  setup sam_web_client
  export SAM_EXPERIMENT=sbnd EXPERIMENT=sbnd
  samweb describe-definition <def>'
```
- `setup sam_web_client` (gives v3_6) is required. A hand-prepended PATH to the
  cvmfs v3_3 client fails, and so does running from the bare build node.
- **Do NOT test reachability with `getent hosts samweb.fnal.gov`** — that fails
  even where `samweb` itself works, so it reports a blocker that isn't there.
  Run the real command. (Diagnosed the wrong way round 2026-08-21, which cost a
  round trip asking the owner to run a query the agent could run itself.)

## Imaging+clustering+QL-matching chains

- OLD (obsolete): `obsolete/wcls-img-clus-matching.{fcl,jsonnet}` — larwirecell `wclsQLMatching`, sbndcode `img.jsonnet`
  (`img_config` e.g. `active2view+masked2view` / `active3view+masked1view`). Run with setup-local-opt.sh.
  Output: per-node `mabc-*.zip` + `data-sep/`; upload via `./bee-upload.sh` (merges -> combined.zip).
  Superseded by the XIN-faithful chain below.
- XIN-faithful: `wcls-img-clus-matching-xin.{fcl,jsonnet}` — artROOT input but toolkit `img` multi-3view+full_deghost,
  toolkit `clus` per_apa, joint `QLMatching` (FlashTensorToOpticalPCs + WireCellMatch), single shared `mabc.zip`.
  Run with setup-ap.sh; upload via `BROWSER=echo bash sbnd_xin/upload-to-bee.sh mabc.zip`.
  Downstream pattern-rec toggle: `enable_downstream_pr` (top of toolkit `pgrapher/experiment/sbnd/clus.jsonnet`):
  true = full patrec (tagger/steiner/vertices/mc); false = matching-only. Bulk runs: use false — full patrec has
  data-dependent crashes on some events (no main_cluster; missing steiner_pc). Do NOT modify anything in sbnd_xin.

## Where details live

- `docs/0-build-wct-larwirecell-sl7-sbnd.md` — HOW TO BUILD wire-cell-toolkit + larwirecell and install to
  `/exp/sbnd/app/users/yuhw/opt` (SL7 recipe, hand-copy step, landmines). Read before building either.
- `docs/1-run-tests-sl7-local-builds-sbnd.md` — HOW TO RUN `wcls-img-clus-matching-xin.fcl` (MC + data) with
  the local builds: env, commands, toggles, log greps, validation, BEE upload, wcsonnet check.
- `docs/8-build-and-run-both-chains.md` — the spdlog/fmt build resolution (external-fmt spdlog v1_14_1 +
  fmt v11_0_2, `lib64`, `-DSPDLOG_FMT_EXTERNAL` via CXXFLAGS, no `--with-fmt`), the post-build gate that
  catches a green-but-useless build, the larwirecell `make install` prefix trap, HOW TO RUN **Xin's 2-step**
  chain here (incl. the three SL7 bash-4.2/python-3.9 portability fixes his driver needs), and the tooling +
  legitimate exclusions for comparing the two chains. Read with doc 0 before building or comparing.
  §7 = round-2 (prod0908) summary and lessons.
- **The procedure** (gates + traps, ordered): ai-helper
  `docs/sbnd-1step-build-run-validate.md`
  (https://github.com/HaiwangYu/wire-cell-toolkit-ai-helper/blob/main/docs/sbnd-1step-build-run-validate.md).
  Non-negotiables: strip wcb's build-tree `DT_RPATH` after every install; run
  `resync-operating-point.sh` after every toolkit merge BEFORE any event runs.
- `cm-2606/STATUS-xin-chain.md` — full status: chains, toggle, all local WCT edits, known issues, BEE uploads.
- Quick CPU/mem profiling: `/exp/sbnd/app/users/yuhw/activity_logger/top.sh <pattern>` (run concurrently); plot example in `cm-2606/activity/`.
- w-gap study (SP rebaseline, DNNROI truncation, charge bias): `standalone-sample/w-gap/W-GAP-STUDY.md`.
