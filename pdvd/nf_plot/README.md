# PDVD coherent-NF dump + viewer

Validation tool for `PDVDCoherentNoiseSub` (jsonnet `data.debug_dump_path`).
Mirrors the PDHD setup; the viewer code is **shared** with PDHD —
`serve_coherent_viewer.sh` invokes
`../../pdhd/nf_plot/coherent_dump_viewer.py` with the PDVD dump
directory.

PDVD top (anodes 4–7) and bottom (0–3) are typically run as separate
jobs but can share one viewer instance: the dump tree is keyed on
`apa<N>` so all 8 anodes land in one Bokeh dropdown.

---

## Quick start

```bash
# 1. Run NF+SP for one event with the dump turned on:
./run_nf_sp_evt.sh 039324 0 -a 0 -d work/dbg     # bottom anode 0
./run_nf_sp_evt.sh 039324 0 -a 4 -d work/dbg     # top anode 4 (same dump dir)

# 2. Start the viewer on the workstation:
cd nf_plot
./serve_coherent_viewer.sh ../work/dbg

# 3. From your laptop, port-forward over SSH:
ssh -L 5006:localhost:5006 user@workstation

# 4. Open in laptop's browser:
http://localhost:5006/coherent_dump_viewer
```

The dump path layout, NPZ schema, viewer panels, and tuning workflow
are identical to PDHD's — see [`../../pdhd/nf_plot/README.md`](../../pdhd/nf_plot/README.md)
for the full reference.

---

## PDVD-specific notes

- `decon_limit1` defaults to **0.07 / 0.07 / 0.09** for U/V/W (vs 0.07 / 0.07 / 0.09 on PDHD APA0; both detectors use the same chndb defaults but their RMS scales differ).
- `ROI_tighter_lf` τ = **0.06 MHz** on PDVD vs 0.08 MHz on PDHD; that
  shifts the deconv-stage low-frequency cutoff and is one of the
  things visible in the viewer's bottom-panel waveform shape.
- The PDVD jsonnet has a per-CRP dispatch hook
  (`if anode.data.ident < 4`) that currently routes both
  bottom-CRP and top-CRP groups to the same `Wiener_tight_*` set;
  if that ever diverges the viewer will simply show different
  filters in the header bar — no viewer change needed.
