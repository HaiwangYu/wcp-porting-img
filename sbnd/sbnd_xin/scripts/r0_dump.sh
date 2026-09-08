#!/bin/bash
# doc 102 round-0: dump a Reco1 entry range with the SAME command run_chain_group.sh
# uses (lines 203-217), into a scratch dir, so it can be hash-compared against the
# recorded extraction.  Read-only w.r.t. every input tree.
#
# Usage: r0_dump.sh <reco1.root> <outdir> <entry_begin> <entry_count> [fsproduct]
set -u
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
TK=$WCT_BASE/toolkit
SBND_RECO1=${SBND_RECO1:-$WCT_BASE/wire-cell-sbnd-reco1/install}
export LD_LIBRARY_PATH=$SBND_RECO1/lib:$HOME/tmp/d102m-libsnap:${LD_LIBRARY_PATH:-}
export WIRECELL_PATH=$SBND_RECO1/share/wirecell:$SX:$TK/cfg:$WCT_BASE/wire-cell-data:$WCT_BASE/wire-cell-data/sbnd/photodet:${WIRECELL_PATH:-}
export PYTHONPATH=$TK/pyutil/python:$WCT_BASE/local/python:$WCT_BASE/wire-cell-python:${PYTHONPATH:-}

IN=$1; OUT=$2; BEG=$3; CNT=$4; FSP=${5:-}
mkdir -p "$OUT"
TLA=(--tla-str "input=$IN" --tla-str "output_dir=$OUT"
     --tla-str "caf_offset_mode=product" --tla-str "caf_offset_override=0"
     --tla-str "entry=-1" --tla-str "entry_begin=$BEG" --tla-str "entry_count=$CNT")
[ -n "$FSP" ] && TLA+=(--tla-str "frameshift_product=$FSP")
wire-cell -l stderr -l "$OUT/wct_dump.log:info" -L info \
    "${TLA[@]}" -c "$SX/wct-reco1-dump.jsonnet" > "$OUT/dump.stdout" 2>&1
rc=$?
echo "dump rc=$rc  -> $OUT"
[ $rc -eq 0 ] && tar tjf "$OUT/frames-dnn.tar.bz2" 2>/dev/null | grep -c '^frame_dnnsp_'
exit $rc
