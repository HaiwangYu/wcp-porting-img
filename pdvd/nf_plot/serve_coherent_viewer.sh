#!/bin/bash
# Serve the coherent-NF dump viewer for PDVD.
#
# The viewer code is detector-agnostic and lives under pdhd/nf_plot/.
# This wrapper just invokes it with the PDVD dump_dir.
#
# Usage: ./serve_coherent_viewer.sh <dump_dir> [port]

set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PDHD_VIEWER="$HERE/../../pdhd/nf_plot/coherent_dump_viewer.py"

if [ ! -f "$PDHD_VIEWER" ]; then
    echo "Error: shared viewer not found at $PDHD_VIEWER" >&2
    exit 1
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 <dump_dir> [port]" >&2
    exit 1
fi

DUMP_DIR=$1
PORT=${2:-5006}

case "$DUMP_DIR" in
    /*) ABS="$DUMP_DIR" ;;
    *)  ABS="$(cd "$DUMP_DIR" && pwd)" ;;
esac

exec bokeh serve --port "$PORT" \
    --allow-websocket-origin="localhost:${PORT}" \
    --allow-websocket-origin="127.0.0.1:${PORT}" \
    "$PDHD_VIEWER" --args "$ABS"
