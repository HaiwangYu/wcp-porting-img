#!/bin/bash
# gperftools CPU-profile (or tcmalloc heap-profile) one event's PDHD PR job (doc pdvd/30 r2).
#   Usage: ./profile_pr.sh <run> <idx> [out.prof]
#
# Forked BY DUPLICATION from pdvd/profile_pr.sh (untouched).  What differs:
#   * PDVD_* -> PDHD_* env names;
#   * WCT_PYLIB defaults OFF -- PDHD sets dl_weights='' so there is no SCN net to
#     load, and a straight copy would preload libpython for nothing;
#   * PDHD has no scripts/stage_pr_tag.sh, so the tag dir must already exist
#     (stm/perf/d30_stage.sh makes one);
#   * MODE/STMFIT are parameters, since -stm and -nu profile differently.
#
# Steps: compile the job config through the runner (PDHD_PR_COMPILE_ONLY=1 keeps
# every TLA right and leaves .wct-pr_<tag>.json; wcsonnet precompile because
# SIGPROF corrupts the gojsonnet GC, CLAUDE.md M17), then run wire-cell on that
# JSON under libtcmalloc_and_profiler (production preloads tcmalloc, so a glibc
# profile would overstate allocator cost).  Never under setarch -R (SIGPROF dies).
# Env: TAG, PROFLIB, HEAPOUT (tcmalloc HEAPPROFILE prefix instead of CPU),
#      FREQ (CPUPROFILE_FREQUENCY, default 250), MODE (-stm|-nu), STMFIT,
#      LD_LIBRARY_PATH honoured (pin the binary).
set -e
PDHD_DIR=$(cd "$(dirname "$0")" && pwd)
WCT_BASE=/nfs/data/1/xqian/toolkit-dev
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/wire-cell-data:${WIRECELL_PATH}
RUN=${1:?run} IDX=${2:?idx}
RUN_PADDED=$(printf '%06d' "$((10#$RUN))")
TAG=${TAG:-profpr_${RUN_PADDED}_${IDX}}
OUT=${3:-/home/xqian/tmp/d30r2/pr_${RUN_PADDED}_${IDX}.prof}
MODE=${MODE:--stm}
FITFLAG=""; [ "${STMFIT:-1}" = 1 ] && FITFLAG="-stm-fit"
WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${IDX}_${TAG}"
CFG_JSON="$WORKDIR/.wct-pr_${TAG}.json"
[ -d "$WORKDIR" ] || { echo "no tag dir $WORKDIR (stage it: stm/perf/d30_stage.sh)" >&2; exit 1; }
mkdir -p "$(dirname "$OUT")"
( cd "$PDHD_DIR" && env PDHD_PR_COMPILE_ONLY=1 PDHD_KEEP_CFG=1 ./run_pr_evt.sh $MODE $FITFLAG -s "$TAG" "$RUN" "$IDX" )
[ -s "$CFG_JSON" ] || { echo "no compiled cfg at $CFG_JSON" >&2; exit 1; }
PROFLIB=${PROFLIB:-/usr/lib/x86_64-linux-gnu/libtcmalloc_and_profiler.so.4}
if [ "${WCT_PYLIB:-off}" != "off" ]; then
    PYLIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")/libpython3.11.so.1.0
    PROFLIB="$PROFLIB:$PYLIB"
fi
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1} MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
LOG="$WORKDIR/wct_pr_${RUN_PADDED}_${IDX}.log"
cd "$WORKDIR"
if [ -n "$HEAPOUT" ]; then
    env LD_PRELOAD="$PROFLIB" HEAPPROFILE="$HEAPOUT" GOGC=off \
        wire-cell -l stderr -l "$LOG:debug" -L debug -c "$CFG_JSON"
    OUT="$HEAPOUT"
else
    env LD_PRELOAD="$PROFLIB" CPUPROFILE="$OUT" CPUPROFILE_FREQUENCY=${FREQ:-250} GOGC=off \
        wire-cell -l stderr -l "$LOG:debug" -L debug -c "$CFG_JSON"
fi
echo "profile -> $OUT"
echo "view: google-pprof --text --cum $(which wire-cell) $OUT | head -40"
