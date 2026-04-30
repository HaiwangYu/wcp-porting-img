#!/bin/bash
# Serve the coherent-NF dump viewer over HTTP for remote browser viewing.
#
# Usage: ./serve_coherent_viewer.sh <dump_dir> [port]
#   dump_dir   The root passed to run_nf_sp_evt.sh -d
#              (i.e. parent of <RUN_PADDED>_<EVT>/apa<N>/<plane>_g<gid>.npz)
#   port       (optional, default 5006)
#
# To view from a remote laptop, set up SSH port forwarding first:
#   ssh -L 5006:localhost:5006 user@workstation
# then open http://localhost:5006/coherent_dump_viewer in the laptop's browser.

set -e
HERE=$(cd "$(dirname "$0")" && pwd)

if [ $# -lt 1 ]; then
    echo "Usage: $0 <dump_dir> [port]" >&2
    exit 1
fi

DUMP_DIR=$1
PORT=${2:-5006}

# Resolve to absolute path so bokeh isn't sensitive to cwd.
case "$DUMP_DIR" in
    /*) ABS="$DUMP_DIR" ;;
    *)  ABS="$(cd "$DUMP_DIR" && pwd)" ;;
esac

exec bokeh serve --port "$PORT" \
    --allow-websocket-origin="localhost:${PORT}" \
    --allow-websocket-origin="127.0.0.1:${PORT}" \
    "$HERE/coherent_dump_viewer.py" --args "$ABS"
