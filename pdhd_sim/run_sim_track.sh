#!/bin/bash
# Run wire-cell simulation for the longest track in a tracks-hd-anode<N>-<P>.json file.
# Wraps wct-sim-check-track.jsonnet (ProtoDUNE-HD).
#
# Usage:
#   ./run_sim_track.sh                    # all anodes (0..3) x planes (U,V,W)
#   ./run_sim_track.sh -a 0               # all planes for anode 0
#   ./run_sim_track.sh -a 0 -p W          # single combo
#   ./run_sim_track.sh -g 7.8             # low-gain (default 14 mV/fC)
#
# Tracks input:  tracks/tracks-hd-anode<N>-<P>.json
# Output:        work/anode<N>-<P>/protodunehd-sp-frames-sim-anode<N>.tar.bz2

set -e

PDHD_SIM_DIR=$(cd "$(dirname "$0")" && pwd)

WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${PDHD_SIM_DIR}:${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}

ANODES_DEFAULT="0 1 2 3"
PLANES_DEFAULT="U V W"

usage() {
    cat <<EOF
Usage: $0 [-a anode] [-p plane] [-g elecGain]

Options:
  -a <anode>     Anode index 0..3 (default: all)
  -p <plane>     Wire plane U|V|W  (default: all)
  -g <elecGain>  FE amplifier gain in mV/fC (default: 14; use 7.8 for low-gain)
  -h             Show this help

Tracks input:  tracks/tracks-hd-anode<N>-<P>.json
Output:        work/anode<N>-<P>/protodunehd-sp-frames-sim-anode<N>.tar.bz2
EOF
}

ANODE=""
PLANE=""
ELEC_GAIN="14"
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -a) ANODE="$2"; shift 2 ;;
        -p) PLANE="$2"; shift 2 ;;
        -g) ELEC_GAIN="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

ANODES=${ANODE:-$ANODES_DEFAULT}
PLANES=${PLANE:-$PLANES_DEFAULT}

run_one() {
    local n=$1 p=$2
    local tracks="$PDHD_SIM_DIR/tracks/tracks-hd-anode${n}-${p}.json"
    if [ ! -f "$tracks" ]; then
        echo "[skip] no $tracks" >&2; return 1
    fi
    local outdir="$PDHD_SIM_DIR/work/anode${n}-${p}"
    mkdir -p "$outdir"
    local prefix="$outdir/protodunehd-sp-frames-sim"
    local log="$outdir/wct.log"

    echo "=== HD anode=$n plane=$p ==="
    echo "  tracks : $tracks"
    echo "  output : ${prefix}-anode${n}.tar.bz2"
    echo "  log    : $log"

    cd "$PDHD_SIM_DIR"
    wire-cell \
        -l stderr \
        -l "${log}:debug" \
        -L debug \
        -V "elecGain=${ELEC_GAIN}" \
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
