# ref/prod-2026-09-08 — SBND production operating point

**Why this generation exists.** Doc 102: the owner asked for SBND PR validation
samples for colleagues, produced from Reco1 and from the **master** branch of
the toolkit. Master (`e88f364d`, 2026-09-02) was 104 commits behind
`apply-pointcloud`, so the round fast-forwards master to `eacacafe` and produces
there. `ref/prod-2026-09-05` was cut on 2026-09-03; four SBND rounds have
shipped flips since without cutting a generation. This generation records the
operating point those samples were actually produced at.

`prod-2026-09-05` is left **byte-untouched** (M13). This is a new generation
because the compiled config is not identical to it.

Toolkit commit: `eacacafe25bbed37613f2c99b73b59911e355e33` (= `master` after the
doc-102 fast-forward). Gate: `scripts/cfg/prod_cfg_gate.py --ref
ref/prod-2026-09-08` → **PASS, 21/21 artifacts**.

## The drift from `prod-2026-09-05` — 10 of 21 artifacts

```
DRIFT : bare_prjob.json, pdhd_clus.json, pdvd_clus.json, pdvd_img.json,
        pdvd_nfsp.json, pdvd_simcheck.json, pdvd_simtrack.json,
        prod_prjob.json, sbnd_pr.json, uboone.json
```

The 11 that did NOT move: the five other pdhd jobs, `prod.wcls`,
`prod.standalone`, `sbnd_clus.json`, `sbnd_img.json`, `sbnd_ql.json` and
`sbnd_simcheck.json`.

### SBND — `prod_prjob.json` / `sbnd_pr.json` / `bare_prjob.json`, key by key

| key | value | round, and on whose word |
|---|---|---|
| `[21].excl_t0_frame` | `true` | doc pr/144 — SBND production 2026-09-06. `-A excl_t0_frame=false` restores the legacy biased-frame path exactly. |
| `[21].kine_dqdx_skip_zero_dx` | `true` | doc pr/144 — stands between a coincident fit-point pair and a NaN reconstructed Enu. C++ default false. |
| `[21].kine_near_pointing_impact` | `200` (cm) | doc pr/145 item 4 — SBND production 2026-09-06. `0` = off. |
| `[21].kine_near_pointing_miss_deg` | `30` (deg) | doc pr/145 item 4 — the clause that decides at impact = 200. |
| `[21].long_muon_cathode_bridge_track_types` | `true` | doc pr/147. C++ default false; key omitted when off ⇒ byte-identical. |
| `[21].long_muon_cathode_bridge_tail_min_len` | `20` (cm) | doc pr/147 round 2. C++ default 0.0 cm = off. |
| `[13].wrapped_channel_activity` | `true` | **inert — see below.** |

`sbnd_ql.json` does **not** move from `prod-2026-09-05`: doc 99 round 3's
`merge_flash_pcs` was already in that generation. (It *is* the SBND difference
against master — see "What the fast-forward publishes".)

### `wrapped_channel_activity` is a config-text change, not a behaviour change

The key appears on the `ImproveCluster_2` node of `prod_prjob.json`,
`sbnd_pr.json`, `bare_prjob.json` **and `uboone.json`**, because
`cfg/pgrapher/common/clus.jsonnet:1470` now emits it unconditionally instead of
leaving it to the C++ default. The C++ default is already `true`
(`clus/src/retile_cluster.h:131`), so the emitted value equals the default and
nothing moves. The header states the stronger fact as well: the path is
"unreachable on a detector with no segment>0 wire (SBND, uBooNE), so
byte-identity there is structural". **uBooNE — a frozen reference (owner
decision 2026-09-01) — is therefore unaffected in behaviour by this generation.**

### PDVD — a wires-geometry swap, not a knob

`pdvd_img.json`, `pdvd_nfsp.json`, `pdvd_simcheck.json`, `pdvd_simtrack.json`
differ from master in exactly one key repeated per anode, `.data.filename`:
`protodunevd-wires-larsoft-v6.json.bz2` → `protodunevd-wires-larsoft-v7-uvwfit.json.bz2`
(0 keys added, 0 removed; 1 / 8 / 1 / 1 changed). `pdvd_clus.json` and
`pdhd_clus.json` do not compile against master's cfg tree at all — their job
entry points live in `wcp-porting-img/{pdhd,pdvd}/` and reference knobs added on
the branch — so they can only be compared within this generation. None of this
touches SBND or uBooNE.

## What the fast-forward publishes — master (`e88f364d`) → `eacacafe`

Compiling the same 21 artifacts from master's cfg tree
(`git archive origin/master cfg`) and diffing against this generation:

```
MOVED     : bare_prjob.json, pdvd_img.json, pdvd_nfsp.json, pdvd_simcheck.json,
            pdvd_simtrack.json, prod_prjob.json, sbnd_pr.json, sbnd_ql.json,
            uboone.json
IDENTICAL : pdhd_img, pdhd_nfsp, pdhd_simcheck, pdhd_simnoise, pdhd_simtrack,
            prod.standalone, prod.wcls, sbnd_clus.json, sbnd_img.json,
            sbnd_simcheck.json
(no master build: pdhd_clus.json, pdvd_clus.json)
```

The SBND half of that is exactly the doc-99 / pr-144 / pr-145 / pr-147 flips:
`sbnd_ql.json` gains `QLMatching:matching_joint.merge_flash_pcs = true`,
`prod_prjob.json` gains `SbndPrMagnifyTrackingVisitor.flash_by_gid = true` plus
the seven keys tabled above — eight ADDED keys, 0 removed, 0 changed. **`sbnd_clus.json` and `sbnd_img.json` are
byte-identical across the fast-forward**: neither clustering nor imaging moves.

## Reproduce

```bash
cd wcp-porting-img/sbnd/sbnd_xin
scripts/cfg/prod_cfg_gate.py --ref ref/prod-2026-09-08          # PASS 21/21
scripts/cfg/prod_cfg_gate.py --ref ref/prod-2026-09-05          # the drift above
git -C ../../../toolkit archive origin/master cfg | tar -x -C <scratch>
scripts/cfg/prod_cfg_gate.py --ref ref/prod-2026-09-05 --cfg <scratch>/cfg --keep <scratch>/cfg-master
```

The `gate308-*.txt` event lists are carried forward from `prod-2026-09-04`
unchanged.
