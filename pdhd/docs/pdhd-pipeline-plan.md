# PDHD event-processing pipeline port plan

Status: **Phase A complete; Phase B blocked on upstream data format**
(see "Open issue — PDHD SP-frame format" below).

## Goal

Mirror the PDVD per-event processing scripts for PDHD:

    pdvd/run_sp_to_magnify_evt.sh
    pdvd/run_img_evt.sh
    pdvd/run_clus_evt.sh
    pdvd/run_bee_img_evt.sh
    pdvd/run_select_evt.sh

so that from `pdhd/` we can take an event under
`pdhd/input_data/<run>/<evt>/protodunehd-sp-frames-anode*.tar.bz2`
and run the same sp→magnify, imaging, clustering, bee-upload,
and Woodpecker selection flow as PDVD.

## Decisions

1. **Cluster-file naming.** Use `clusters-apa-apa{N}-ms-*.tar.gz`
   (PDHD convention), not `anode{N}` as PDVD uses. This matches the
   existing PDHD `1event/`, `10events/` data and the
   `pdhd/wct-clustering.jsonnet` currently in the tree. It also comes
   from `params.jsonnet` where `anode.name = "apa%d" % n`, so the
   stock `img.jsonnet`'s `"clusters-apa-" + aname + ".tar.gz"` pattern
   already produces the right names without any patching.
2. **Obsolete files** go to `pdhd/old/` when phases require replacing
   existing scripts or configs (so we can recover them if needed).
3. **Keep `pdhd/clus.jsonnet` untouched.** The PDHD clustering config
   is already tuned for the 4-anode geometry and should not be
   replaced with PDVD's 8-anode version.
4. **Local forks over cfg edits.** When the cfg tree
   (`cfg/pgrapher/experiment/pdhd/*.jsonnet`) needs a surgical change
   (e.g. adding `output_dir` to `img.jsonnet`), fork into `pdhd/` and
   leave cfg/ untouched. Import resolution picks the local copy
   automatically because jsonnet `import 'img.jsonnet'` resolves
   relative to the importer.

## Phases

### Phase A — sp → magnify ✅ DONE

**Artifacts** (added by this phase):
- `pdhd/magnify-sinks.jsonnet` — clone of `pdvd/magnify-sinks.jsonnet`,
  unchanged in logic. Per-anode MagnifySink pipelines (first sink
  RECREATE, rest UPDATE; Trun written once with runinfo from anode0).
- `pdhd/wct-sp-to-magnify.jsonnet` — clone of
  `pdvd/wct-sp-to-magnify.jsonnet` with `protodunevd` → `pdhd` params.
  Reads `FrameFileSource` → Retagger → MagnifySink per anode; optional
  raw pass is UPDATE. `nticks` is TLA (default 6000) but only drives
  Trun's `total_time_bin`; TH2F binning is data-driven.
- `pdhd/run_sp_to_magnify_evt.sh` — 4-anode loop (`0..3`),
  `protodunehd-sp-frames` input prefix, output `magnify-run<RUN>-evt<EVT>-apa<N>.root`.
  Extracts the real frame tick count from
  `frame_gauss0_<EVENT>.npy` (via `np.load(..., mmap_mode='r')` —
  reads only the header) and passes it as `--tla-code nticks=...`,
  so Trun's `total_time_bin` matches the archive.

**Verified on `pdhd/input_data/run027409/evt_1/` (art evt 40896):**
- 4 ROOT files written to `pdhd/work/027409_1/`, ~63 MB each.
- `TFile::ls()` confirms `hu/hv/hw_{gauss,wiener,threshold}0` +
  `T_bad0` + `Trun` + `hu/hv/hw_raw0`.
- Trun: `runNo=27409, subRunNo=0, eventNo=40896, anodeNo=0, total_time_bin=5859`
  (5859 is the actual PDHD frame tick count, not the 6000 readout
  constant).

### Phase B — imaging ⚠️ BLOCKED (upstream data-format issue)

**What I tried.** Local files created:
- `pdhd/img.jsonnet` — surgical fork of
  `cfg/pgrapher/experiment/pdhd/img.jsonnet` that
  - adds `output_dir=''` to the top-level `function()`
  - adds `output_dir` plumbing to `img.dump()` so cluster tarballs can
    be written to a specific directory
  - adds `summary_tag: 'wiener%d' % anode.data.ident` to the MaskSlices
    config (fixes a bug where the cfg omits it; see below).
- `pdhd/wct-img-all.jsonnet` — clone of `pdvd/wct-img-all.jsonnet`
  with `protodunevd` → `pdhd` params.
- `pdhd/run_img_evt.sh` — 4-anode loop, `protodunehd-sp-frames`
  prefix, drops cluster tarballs into `work/<RUN_PADDED>_<EVT>/`.

**Config bug uncovered (already fixed in the local fork).**
`cfg/pgrapher/experiment/pdhd/img.jsonnet` line 105 has
`wiener_tag: "wiener%d" % ident` but omits the matching
`summary_tag: "wiener%d" % ident`. PDVD's cfg has both (line 106).
Without `summary_tag`, WCT's config merging preserves the
`default_configuration()` value `"wiener"`, so `MaskSlice` looks up
tag `"wiener"` (not `"wiener3"`), finds no summary, throws
`size unmatched`. The local fork adds the missing line; the cfg file
could be upstreamed later.

**Blocker — upstream SP-frame data shape (being chased with Xuyang).**
Even with the config bug fixed, MaskSlice then errors with
`trace size mismatch: gauss0: 2398 and wiener0: 2435`, which is a
property of the input archives, not of our config.

See `pdhd/docs/sp-frame-format-comparison.md` for the detailed
PDVD-vs-PDHD per-file diff that was sent to Xuyang.

In short, PDHD's
`input_data/run027409/evt_1/protodunehd-sp-frames-anode0.tar.bz2`:
- has `gauss0` with 2398 traces but `wiener0` with 2435 (37 extra
  wiener-only channels, no gauss counterpart — WCT requires 1:1)
- has `summary_wiener0` with 14962 entries instead of 2435 (per-ROI
  repetition with run-length ≈ median 6, matching the 2435 channels);
  WCT requires one summary per channel.

PDVD archives have gauss=wiener=summary=channels all at the same
count (1536 for run039324/evt1). WCT's standalone `MaskSlice` assumes
per-channel gauss/wiener/summary.

Resolution options (pick after Xuyang replies):
1. Ask Xuyang to regenerate PDHD SP-frame archives in the PDVD shape
   (per-channel summary, matched gauss/wiener trace lists). Cleanest.
2. Add a preprocessing node upstream of MaskSlice that collapses
   per-ROI wiener summaries to per-channel values and aligns gauss to
   wiener. Not yet known whether one exists.
3. If the per-ROI summary is a deliberate, newer convention, adapt
   the PDHD imaging pipeline (not just the standalone WCT
   `MaskSlice` path) to consume it. This may be a larger effort.

### Phase C — clustering (planned, not started)

1. Refactor `pdhd/wct-clustering.jsonnet` from the current
   `std.extVar('input')` form to the PDVD-style TLA signature
   `function(input, anode_indices, output_dir, run, subrun, event)`.
   Keep the PDHD `params.jsonnet` / `clus.jsonnet` imports.
   Move the current `wct-clustering.jsonnet` to `pdhd/old/` first.
2. Create `pdhd/run_clus_evt.sh` modelled on
   `pdvd/run_clus_evt.sh`:
   - 4-anode default (`[0,1,2,3]`)
   - prefer `work/<RUN_PADDED>_<EVT>/` cluster tarballs; fall back to
     `input_data/<run>/<evt>/` when re-imaging isn't possible
   - parse art event number from
     `clusters-apa-apa{N}-ms-active.tar.gz` entries
   - pass TLAs `input`, `anode_indices`, `output_dir`, `run`, `subrun`, `event`.

Verification: `mabc-*.zip` appear in `work/<RUN_PADDED>_<EVT>/`.

### Phase D — bee upload (planned, not started)

1. Refactor `pdhd/wct-img-2-bee.py` from its current hard-coded
   4-positional-argument form into the variadic `<idx>:<path>` form
   that `pdvd/wct-img-2-bee.py` uses. Move the old version to
   `pdhd/old/`.
2. Preserve PDHD's Bee geometry (`-g protodunehd`) and existing
   drift-speed / `t0` / `x0` values:
   - apa 0 and 2: `--speed "-1.6*mm/us" --t0 "250*us" --x0 "-358*cm"`
   - apa 1 and 3: `--speed "1.6*mm/us" --t0 "250*us" --x0 "358*cm"`
   (Confirm pattern from the current `pdhd/wct-img-2-bee.py` when
   doing the refactor — different faces of PDHD alternate drift
   direction rather than being split top/bottom the way PDVD anodes
   0-3 vs 4-7 are.)
3. Create `pdhd/run_bee_img_evt.sh` modelled on
   `pdvd/run_bee_img_evt.sh`:
   - 4-anode default
   - build `<idx>:<path>` pairs pointing at
     `clusters-apa-apa{N}-ms-active.tar.gz`
   - emit `upload_<RUN_PADDED>_<EVT>[...].zip` and push via
     `./upload-to-bee.sh`.

### Phase E — selection (planned, not started)

1. Create `pdhd/run_select_evt.sh` modelled on
   `pdvd/run_select_evt.sh`:
   - same Woodpecker invocation (GUI is generic)
   - input prefix `protodunehd-sp-frames`
   - 4-anode default in the archive glob
   - emits masked archives into
     `work/<RUN_PADDED>_<EVT>_<TAG>/input/` which the other scripts
     already know how to pick up via `-s <TAG>`.

### Optional — per-event dispatcher

Port `pdvd/run_evt.pl` at the end (`run | img | clus | chain | bee`
stage switch) once A-E are working.

## File parity expected after all phases

| PDVD file                          | PDHD equivalent                                |
|------------------------------------|------------------------------------------------|
| `run_sp_to_magnify_evt.sh`         | same name, 4-anode, `protodunehd-sp-frames`    |
| `wct-sp-to-magnify.jsonnet`        | same name, pdhd params                         |
| `magnify-sinks.jsonnet`            | same name, identical                           |
| `wct-img-all.jsonnet`              | same name, pdhd params                         |
| `img.jsonnet` (local fork)         | same name, pdhd cfg + surgical patches         |
| `run_img_evt.sh`                   | same name, 4-anode                             |
| `wct-clustering.jsonnet`           | refactor existing (keep pdhd clus.jsonnet)     |
| `run_clus_evt.sh`                  | new                                            |
| `wct-img-2-bee.py`                 | refactor existing, variadic; `-g protodunehd`  |
| `run_bee_img_evt.sh`               | new                                            |
| `run_select_evt.sh`                | new                                            |
| `run_evt.pl`                       | optional port at the end                       |

## Current tree state (checkpoint)

Added by Phase A (committed to working tree, not git):

    pdhd/magnify-sinks.jsonnet
    pdhd/wct-sp-to-magnify.jsonnet
    pdhd/run_sp_to_magnify_evt.sh

Added by Phase B attempt (files exist but blocked until data format
is resolved; safe to leave in place since they only run when invoked):

    pdhd/img.jsonnet
    pdhd/wct-img-all.jsonnet
    pdhd/run_img_evt.sh

Outputs from verification runs (can be deleted freely):

    pdhd/work/027409_1/magnify-run027409-evt1-apa{0..3}.root
    pdhd/work/027409_1/wct_magnify_027409_1_apa{0..3}.log
    pdhd/work/027409_1/wct_img_027409_1.log
    pdhd/work/027409_1/wct_img_027409_1_a0.log
    pdhd/work/027409_1/clusters-apa-apa{0..3}-ms-{active,masked}.tar.gz  (empty — blocked)

Unchanged (still the pre-existing PDHD setup):

    pdhd/wct-clustering.jsonnet   (std.extVar('input') form)
    pdhd/clus.jsonnet
    pdhd/clus-new.jsonnet
    pdhd/wct-img-2-bee.py         (hard-coded 4-arg form)
    pdhd/1event/, pdhd/10events/  (pre-computed cluster tarballs)
