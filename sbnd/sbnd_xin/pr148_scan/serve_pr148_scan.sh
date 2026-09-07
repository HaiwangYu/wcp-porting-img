#!/bin/bash
# doc sbnd_xin/pr/148 -- serve the blind EM / HADRONIC / MIXED scan display.
#
#   ./pr148_scan/serve_pr148_scan.sh [PORT] [--scan-tag NAME]
#
# PORT defaults to 5017, which the owner asked for.
#
# ***  5017 IS SHARED WITH pr_display  ***  (pr_display/serve_pr_display.sh:33
# defaults to it).  Run one or the other, never both.  This matters because a
# second bokeh on a busy port DOES NOT FAIL LOUDLY: it logs
# "Cannot start Bokeh server, port 5017 is already in use" and leaves the OLD
# app answering, which is exactly how a stale display gets hand-scanned.
# Check first:
#     ss -ltnp | grep 5017
#
# The rest of the SBND port table (the serve scripts are authoritative, not the
# comment in pr_display/README.md): 5008 ql_scan, 5013 img_plot, 5014 pd_plot,
# 5016 wf_scan, 5017 pr_display, 5018-5020 overclustering, 5021 em_display,
# 5022 split_display.
#
# From a laptop:
#   ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6 \
#       -L 5017:localhost:5017 <user>@wcgpu1.phy.bnl.gov
#   then open http://localhost:5017/pr148_scan_viewer
#
# The keepalives are not decoration (doc pr/88): a bare `ssh -L` is reaped by an
# idle timeout during exactly the long pauses a hand scan is made of, and
# Bokeh's JS does NOT auto-reconnect -- the tab shows "Client connection was
# lost" and keeps showing it after the tunnel is back.
#
# --session-token-expiration 86400 for the same class of reason: bokeh's default
# is 300 s, a scan session routinely outlives it, and THE SYMPTOM IS A HANG --
# the page never finishes loading and shows no error, so it reads as "the viewer
# is broken" rather than "reload me".  Safe here: the server is bound behind an
# ssh tunnel, so token lifetime is not a security boundary.
#
# --scan-tag names work/pr148_scan_labels/<tag>/.  A fresh tag per pass; never
# write into an existing one (M13).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PORT=${1:-5017}
shift || true

if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    echo "REFUSING: something is already listening on ${PORT}." >&2
    echo "  ss -ltnp | grep ${PORT}   -- bokeh would fail SOFT and leave the" >&2
    echo "  old app answering, so this script refuses instead." >&2
    exit 3
fi

python3 "$HERE/prep_pr148_scan.py" >/dev/null

BOKEH=/nfs/data/1/xqian/toolkit-dev/.direnv/python-3.11.9/bin/bokeh

exec "$BOKEH" serve --port "$PORT" \
    --session-token-expiration "${SESSION_TOKEN_EXPIRATION:-86400}" \
    --allow-websocket-origin="localhost:${PORT}" \
    --allow-websocket-origin="127.0.0.1:${PORT}" \
    --allow-websocket-origin="wcgpu1.phy.bnl.gov:${PORT}" \
    --allow-websocket-origin="wcgpu1:${PORT}" \
    "$HERE/pr148_scan_viewer.py" --args "$@"
