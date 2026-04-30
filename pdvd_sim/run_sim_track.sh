#!/bin/bash
# Run wire-cell simulation for the longest track in a tracks-vd-anode<N>-<P>.json file.
# Wraps wct-sim-check-track.jsonnet (ProtoDUNE-VD).
#
# Usage:
#   ./run_sim_track.sh                    # all anodes (0..7) x planes (U,V,W)
#   ./run_sim_track.sh -a 2               # all planes for anode 2
#   ./run_sim_track.sh -a 2 -p W          # single combo
#
# Tracks input:  tracks/tracks-vd-anode<N>-<P>.json
# Output:        work/anode<N>-<P>/protodune-sp-frames-sim-anode<N>.tar.bz2

set -e

PDVD_SIM_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${PDVD_SIM_DIR}:${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

ANODES_DEFAULT="0 1 2 3 4 5 6 7"
PLANES_DEFAULT="U V W"

usage() {
    cat <<EOF
Usage: $0 [-a anode] [-p plane]

Options:
  -a <anode>     Anode index 0..7 (default: all)
  -p <plane>     Wire plane U|V|W  (default: all)
  -h             Show this help

Tracks input:  tracks/tracks-vd-anode<N>-<P>.json
Output:        work/anode<N>-<P>/protodune-sp-frames-sim-anode<N>.tar.bz2
EOF
}

ANODE=""
PLANE=""
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -a) ANODE="$2"; shift 2 ;;
        -p) PLANE="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

ANODES=${ANODE:-$ANODES_DEFAULT}
PLANES=${PLANE:-$PLANES_DEFAULT}

run_one() {
    local n=$1 p=$2
    local tracks="$PDVD_SIM_DIR/tracks/tracks-vd-anode${n}-${p}.json"
    if [ ! -f "$tracks" ]; then
        echo "[skip] no $tracks" >&2; return 1
    fi
    local outdir="$PDVD_SIM_DIR/work/anode${n}-${p}"
    mkdir -p "$outdir"
    local prefix="$outdir/protodune-sp-frames-sim"
    local log="$outdir/wct.log"

    echo "=== VD anode=$n plane=$p ==="
    echo "  tracks : $tracks"
    echo "  output : ${prefix}-anode${n}.tar.bz2"
    echo "  log    : $log"

    cd "$PDVD_SIM_DIR"
    wire-cell \
        -l stderr \
        -l "${log}:debug" \
        -L debug \
        --tla-code "tracks_json=$(cat "$tracks")" \
        --tla-str  "output_prefix=${prefix}" \
        --tla-code "anode_indices=[${n}]" \
        -c wct-sim-check-track.jsonnet
}

for n in $ANODES; do
    for p in $PLANES; do
        run_one "$n" "$p" || true
    done
done

echo "All done."
