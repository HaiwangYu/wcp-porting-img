# PDHD doc-08 STM-flip hand scan — `retile_hack_max_bridge`

The scan doc pdhd/08 §8 says is the next step, as a display rather than a TSV.

## Why this scan exists

Capping the retiler's path bridge at 10 cm removes **every** Steiner ghost beyond
30 cm (worst 39.2 → 11.3 cm over 30 events, doc §6) and leaves the **TGM tagged
set identical**. The whole cost is that **45 of 174 STM tags move** — 21 gained,
24 lost. Nothing in those numbers says whether the cap removed support that was
*real* or support that was *fabricated*. That is a physics judgement on the
charge, and this is where it gets made.

## Start it

```bash
cd wcp-porting-img/pdhd/d08_scan
./serve_d08_scan.sh 5017                 # --tag NAME to namespace a second pass
```

From a laptop:

```bash
ssh -L 5017:localhost:5017 user@wcgpu1
# then open  http://localhost:5017/d08_scan_viewer
```

Port 5017 is **shared** with `pdhd/stm_scan` and `pdhd/d05_scan` (img_plot owns
5013, pd_plot 5014, ql_scan 5015, wf_scan / pdvd ql_scan 5016). Bokeh does not
fail loudly on a busy port — it logs a warning and leaves the *old* app
answering, which is how a stale display gets scanned. **`serve_d08_scan.sh`
refuses to start if 5017 is taken** and prints the offender.

## What you see, and what to answer

Identical to the `stm_scan` app, deliberately: three projections at full detector
extent with the active boundary drawn, the cluster coloured by its charge, and
**all other charge in the event** in grey (every grey point within 40 cm of the
cluster with `Dense context` on). Judge the **whole object** — cluster plus any
grey charge continuing along the same trajectory. Does it enter and **stop**
inside the active volume?

| button | the cluster is… | and the full object… |
|---|---|---|
| `STM` | the whole object | stops inside |
| `THRU` | the whole object | crosses / exits a face |
| `FRAG → STM` | only **part** of the object | stops inside |
| `FRAG → THRU` | only **part** of the object | exits |
| `MESSY` | not one track at all | *ill-posed* |
| `UNCLEAR` | — | you cannot tell |

Clicking a label saves immediately and advances. `next unlabelled >>` resumes.

## The before/after REVEAL — read this before using it

You asked to see before and after, so the button exists. **It is the answer key**,
and it is **off by default**:

- Orange dots = the **before** Steiner cloud, cyan = **after**.
- Red **×** = the **before** STM fit, blue **+** = **after**.
- A banner prints both arms' verdicts and their Steiner / fit point counts.

The direction of a flip is the single most biasing fact available — "this one
*lost* its tag" invites the answer. So: the sheet does not carry direction, the
UI does not show it, and anything you label while REVEAL is on is saved with
`revealed_before_label: true`. `score_d08_scan.py` reports blind and revealed
labels **separately**; if they disagree in direction the blind set governs.

Suggested use: label blind first, then switch REVEAL on to understand *why* the
verdict moved. That way you get both without spending the scan's validity.

## Why the charge panels cannot leak the arm

`clustering-global` has the **identical point set and charges** in all 30 events
between the two arms — asserted event-by-event by `selftest_d08_scan.py`, not
assumed. In 9 of 30 events a handful of points (0.005–2.3 %) change *which
cluster* they belong to; for the **2** scan items where that touches the item's
own cluster the sheet sets `partition_moved=1`, the header says so in red, and
the scorer excludes them from the headline (clause 4). The panels always draw the
**base** arm's partition.

## The sample

45 items — every object whose STM verdict differs between `d08goff` (knobs off)
and `d08cap10` (`retile_hack_max_bridge = 10 cm`): 21 gained, 24 lost. Ordered by
a fixed-seed shuffle (`seed 20260906`), tranche 1 = the first 20. The shuffle is
deliberate: putting the 6 objects that lose their tag under *every* cap value at
the top would announce their direction.

Cluster identity across arms was checked, not assumed: 43 of the 45 have a
**Jaccard overlap of exactly 1.000** between arms, and the two that do not are the
`partition_moved` pair.

## Scoring, and the bar fixed before any label exists

```bash
python3 score_d08_scan.py                # --tag NAME for another pass
```

1. The cap arm must agree with you on **strictly more** scored items than the
   baseline. A tie is not a reason to change production.
2. Of the **6** objects that lose their tag under every cap value, a **majority**
   must be `THRU` / `FRAG → THRU` — the cap removing tags that were wrong. If
   most are real stoppers, the cap is destroying genuine support and the value
   must come down even if clause 1 passes.
3. Blind and revealed labels reported apart; the blind set governs.
4. The 2 `partition_moved` items are reported separately and excluded from
   clause 1 — for those the two arms do not agree on which points the cluster
   owns, so "the same object" is not well defined.

`MESSY` + `UNCLEAR` are unscored and reported as a rate; a high rate is itself a
result, because it means the sample cannot decide.

## Files

| file | |
|---|---|
| `d08_scan_viewer.py` | the app; fork by duplication of `../stm_scan/stm_scan_viewer.py`, which is untouched |
| `serve_d08_scan.sh` | fork of `../stm_scan/serve_stm_scan.sh`, plus the busy-port refusal |
| `selftest_d08_scan.py` | 40 headless checks: the sheet carries no direction, the reveal layers are unreachable outside the reveal path, the charge layers are identical across arms in all 30 events, `partition_moved` is honest, label round-trip, and the reveal rendered in-process |
| `score_d08_scan.py` | scores labels against both arms; reads the key |
| `make_d08_scan_sheet.py` | regenerates the sheet + key from the arms |
| `../docs/scan/d08_stm_flip_sheet.tsv` | the item list (no verdicts, **no direction**) |
| `../docs/scan/d08_stm_flip_key.tsv` | the answer key |
| `../work/d08_scan_labels/<tag>/labels.json` | your labels; a sibling of the per-event dirs so re-running an arm cannot delete them |

`work/d08_scan_labels/_selftest*/`, `_scorertest/`, `_inproc/` and `_smoketest/`
are throwaway fixtures from the test scripts, not scan records.

## Two notes for whoever maintains this

**The toggles bind on `on_change("active", ...)`, not `on_click`.** `on_click` is
wired to a browser button event, so a programmatic change of `active` does
nothing — and a binding only a human can exercise is a binding nothing tests.
`on_change` fires for both, which is what makes check 9 of the self-test possible.

**Do not test this app with `bokeh.client.pull_session`.** It hands back a
*detached* document; pushing a property change from it does not round-trip a
server callback, so it reports every binding as broken. Verified with a control
on `item_select` — the same widget pattern the sibling `stm_scan` app has scanned
224 items with — which "failed" identically. The self-test therefore drives the
app **in-process** via `runpy`, which exercises the real callbacks.
