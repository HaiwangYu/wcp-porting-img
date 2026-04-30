#!/bin/bash
# Plot every simulation frame archive under work/.
# Produces, for each work/anode<N>-<P>/protodune-sp-frames-sim-anode<N>.tar.bz2:
#   *.tar.bz2.png                 # full U/V/W frame view (woodpecker plot-frames)
#   *.tar.bz2.<plane>-waveform.png + .npy  # peak-aligned mean waveform on the
#                                            target plane (extract_track_waveform.py)
#
# Usage:
#   ./run_plot.sh              # plot every existing combo
#   ./run_plot.sh -a 2         # only anode 2
#   ./run_plot.sh -a 2 -p W    # one combo
#   ./run_plot.sh --frames-only        # skip the waveform extraction
#   ./run_plot.sh --waveform-only      # skip the full-frame PNG

set -e

PDVD_SIM_DIR=$(cd "$(dirname "$0")" && pwd)

ANODE=""
PLANE=""
DO_FRAMES=1
DO_WAVE=1

usage() {
    cat <<EOF
Usage: $0 [-a anode] [-p plane] [--frames-only|--waveform-only]

Options:
  -a <anode>       Anode index 0..7 (default: all matching dirs)
  -p <plane>       Wire plane U|V|W   (default: all matching dirs)
  --frames-only    Skip waveform extraction
  --waveform-only  Skip full-frame PNG
  -h               Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -a) ANODE="$2"; shift 2 ;;
        -p) PLANE="$2"; shift 2 ;;
        --frames-only)   DO_WAVE=0; shift ;;
        --waveform-only) DO_FRAMES=0; shift ;;
        *) echo "unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

GLOB_ANODE="${ANODE:-*}"
GLOB_PLANE="${PLANE:-?}"

shopt -s nullglob
dirs=( "$PDVD_SIM_DIR"/work/anode${GLOB_ANODE}-${GLOB_PLANE} )
shopt -u nullglob
if [ ${#dirs[@]} -eq 0 ]; then
    echo "no work dirs match anode${GLOB_ANODE}-${GLOB_PLANE} under $PDVD_SIM_DIR/work/" >&2
    exit 1
fi

for d in "${dirs[@]}"; do
    [ -d "$d" ] || continue
    files=( "$d"/protodune-sp-frames-sim-anode*.tar.bz2 )
    [ -f "${files[0]}" ] || { echo "[skip] no frame archive in $d" >&2; continue; }
    f="${files[0]}"

    echo "=== $(basename "$d") :: $(basename "$f") ==="
    if [ "$DO_FRAMES" = "1" ]; then
        woodpecker plot-frames "$f" --detector vd --out "${f}.png"
    fi
    if [ "$DO_WAVE" = "1" ]; then
        "$PDVD_SIM_DIR/extract_track_waveform.py" "$f"
    fi
done

echo "All plots done."
