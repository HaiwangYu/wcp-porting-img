#!/bin/bash
# doc pdhd/12 -- serve the STM + Michel hand-scan display.
#
#   ./serve_stm_michel_scan.sh [PORT] --det pdhd|pdvd [--scan-tag NAME]
#                              [--manifest TSV] [--prepdir DIR]
#
# PORT defaults to 5023.  Everything from 5006 to 5022 is already a default
# somewhere in this tree (img_plot 5012/5013, pd_plot 5014, ql_scan 5008/5015/5016,
# wf_scan 5016, d05/d08/stm_scan/pr_display/pr148 5017, overclustering 5018,
# em_display 5021, split_display 5022), so 5023 is the next free one.
#
# From a laptop:
#   ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
#       -L 5023:localhost:5023 <user>@wcgpu1.phy.bnl.gov
#   then open  http://localhost:5023/stm_michel_viewer
#
# The keepalive options are not decoration: a bare `ssh -L` is reaped by an idle
# timeout during exactly the long pauses a hand scan is made of, and Bokeh's JS
# does NOT auto-reconnect -- the tab shows "Client connection was lost" and keeps
# showing it after the tunnel is back.
#
# --session-token-expiration is 86400 for the same class of reason: bokeh's
# default is 300 s, a scan session routinely outlives it, and THE SYMPTOM IS A
# HANG -- the page never finishes loading and shows no error.  Safe here because
# the server is bound behind an ssh tunnel.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PORT=${1:-5023}
shift || true

# `bokeh serve` on a busy port logs ONE line and exits, and the previous server
# keeps the socket -- so curl returns 200, the page title is right, and every
# check you make describes the OLD code.  Refuse instead of failing softly.
if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    echo "REFUSING: port ${PORT} is already in use; a second bokeh serve would" >&2
    echo "exit and leave the OLD app answering.  Kill it or pick another port." >&2
    ss -ltnp 2>/dev/null | grep ":${PORT} " >&2 || true
    exit 2
fi

VIEWER_OPTS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --det)        VIEWER_OPTS+=(--det "$2"); shift 2 ;;
        --det=*)      VIEWER_OPTS+=(--det "${1#*=}"); shift ;;
        --scan-tag)   VIEWER_OPTS+=(--tag "$2"); shift 2 ;;
        --scan-tag=*) VIEWER_OPTS+=(--tag "${1#*=}"); shift ;;
        --manifest)   VIEWER_OPTS+=(--manifest "$2"); shift 2 ;;
        --prepdir)    VIEWER_OPTS+=(--prepdir "$2"); shift 2 ;;
        *)            echo "unknown option: $1" >&2; exit 3 ;;
    esac
done

BOKEH=/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/bokeh

exec "$BOKEH" serve --port "$PORT" \
    --session-token-expiration "${SESSION_TOKEN_EXPIRATION:-86400}" \
    --allow-websocket-origin="localhost:${PORT}" \
    --allow-websocket-origin="127.0.0.1:${PORT}" \
    --allow-websocket-origin="wcgpu1.phy.bnl.gov:${PORT}" \
    --allow-websocket-origin="wcgpu1:${PORT}" \
    "$HERE/stm_michel_viewer.py" --args "${VIEWER_OPTS[@]+"${VIEWER_OPTS[@]}"}"
