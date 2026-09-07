#!/bin/bash
# doc pdhd/12 -- serve the PDVD side of the STM + Michel hand scan.
#
# One app serves both detectors (--det picks the geometry table in smgeom.py and
# the prep directory); this wrapper exists so the PDVD tree is not the only one
# without an entry point.  The app itself lives in pdhd/stm_michel_scan/ and is
# NOT duplicated here -- the two detectors differ by a geometry table, and a
# forked viewer would have to be fixed twice.
#
#   ./serve_stm_michel_scan.sh [PORT] [--scan-tag NAME]
#   ssh -o ServerAliveInterval=30 -L 5024:localhost:5024 <user>@wcgpu1.phy.bnl.gov
#   then open  http://localhost:5024/stm_michel_viewer
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
APP="$HERE/../../pdhd/stm_michel_scan/serve_stm_michel_scan.sh"
PORT=${1:-5024}
shift || true
exec "$APP" "$PORT" --det pdvd "$@"
