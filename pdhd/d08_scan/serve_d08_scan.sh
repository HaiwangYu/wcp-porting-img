#!/bin/bash
# Serve the PDHD doc-08 STM-flip hand-scan display (doc pdhd/08 sec 8).
#
# Forked BY DUPLICATION from pdhd/stm_scan/serve_stm_scan.sh; that script is untouched.
#
# Usage: ./serve_d08_scan.sh [port] [--tag NAME]
#   port        (optional, default 5017)
#   --tag NAME  (optional, default 'd08flip0') namespaces saved labels into
#               work/d08_scan_labels/NAME/labels.json, so a second pass or a
#               second scanner keeps its labels apart.  NEVER reuse a tag whose
#               labels you want to keep -- a scan record is a record (M13).
#
# PORT 5017 IS SHARED with pdhd/stm_scan and pdhd/d05_scan.  A second server on a
# busy port does NOT fail loudly: it logs "port 5017 is already in use" and leaves
# the OLD app answering, which is how a stale display gets scanned.  This script
# therefore refuses to start if 5017 is taken.  Check yourself with:
#     ss -ltnp | grep 5017
#
# From a laptop:
#   ssh -L 5017:localhost:5017 user@wcgpu1
# then open http://localhost:5017/d08_scan_viewer
#
# Labels are written on EVERY click to work/d08_scan_labels/<tag>/labels.json,
# a sibling of the per-event work dirs so re-running an arm cannot delete them.
#
# Score afterwards (this reads the answer key; the viewer only reads it when you
# press REVEAL, and records that it did):
#   python3 score_d08_scan.py

set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PORT=${1:-5017}
shift || true

TAG_ARGS=()
if [ "$1" = "--tag" ] || [ "$1" = "-t" ]; then
    TAG_ARGS=(--tag "$2"); shift 2 || true
fi

if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    echo "REFUSING: port ${PORT} is already in use -- bokeh would log a warning and leave" >&2
    echo "the OLD app answering, and you would scan a stale display.  Offender:" >&2
    ss -ltnp 2>/dev/null | grep ":${PORT} " >&2 || true
    exit 2
fi

BOKEH=/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/bokeh

exec "$BOKEH" serve --port "$PORT" \
    --allow-websocket-origin="localhost:${PORT}" \
    --allow-websocket-origin="127.0.0.1:${PORT}" \
    --allow-websocket-origin="wcgpu1.phy.bnl.gov:${PORT}" \
    --allow-websocket-origin="wcgpu1:${PORT}" \
    "$HERE/d08_scan_viewer.py" --args "${TAG_ARGS[@]}"
