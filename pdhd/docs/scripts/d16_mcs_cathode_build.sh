#!/bin/bash
# doc pdhd/16 sec 9 -- compile the offline MCS cathode sweeper against the
# INSTALLED WireCellMcs library.  Deliberately NOT a toolkit app or waf target:
# this is analysis code in the analysis repo, and mcs/ is not modified by this
# round at all (the two counters it reads already exist in McsResult).
set -e
TD=${TOOLKIT_DEV:-/nfs/data/1/xqian/toolkit-dev}
HERE=$(cd "$(dirname "$0")" && pwd)
g++ -O2 -std=c++17 -o "$HERE/d16_mcs_cathode_sweep" "$HERE/d16_mcs_cathode_sweep.cxx" \
    -I"$TD/toolkit/mcs/inc" -I"$TD/toolkit/util/inc" \
    -L"$TD/local/lib" -lWireCellMcs -Wl,-rpath,"$TD/local/lib"
echo "built $HERE/d16_mcs_cathode_sweep"
