#!/bin/bash
# Serve the L1SP ROI waveform viewer over HTTP for remote browser viewing.
#
# Usage: ./serve_l1sp_roi_viewer.sh <wf_dir> [port]
#   wf_dir   The root passed to run_nf_sp_evt.sh -w
#            (i.e. parent of <RUN_PADDED>_<EVT>/<dump_tag>_<frame_ident>/wf_*.npz)
#   port     (optional, default 5007)
#
# To view from a remote laptop, set up SSH port forwarding first:
#   ssh -L 5007:localhost:5007 user@workstation
# then open http://localhost:5007/l1sp_roi_viewer in the laptop's browser.

set -e
HERE=$(cd "$(dirname "$0")" && pwd)

if [ $# -lt 1 ]; then
    echo "Usage: $0 <wf_dir> [port]" >&2
    exit 1
fi

WF_DIR=$1
PORT=${2:-5007}

# Resolve to absolute path so bokeh isn't sensitive to cwd.
case "$WF_DIR" in
    /*) ABS="$WF_DIR" ;;
    *)  ABS="$(cd "$WF_DIR" && pwd)" ;;
esac

exec bokeh serve --port "$PORT" \
    --allow-websocket-origin="localhost:${PORT}" \
    --allow-websocket-origin="127.0.0.1:${PORT}" \
    "$HERE/l1sp_roi_viewer.py" --args "$ABS"
