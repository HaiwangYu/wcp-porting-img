#!/usr/bin/env bash
# doc pdhd/09 -- imaging into a TAGGED work dir.
#
# Why this exists: run_img_evt.sh has no -O, and its -s SEL_TAG path is
# mutually exclusive with -d on (line 166: the "SP frames in WORKDIR" branch is
# guarded by [ -z "$SEL_TAG" ], so a tagged run with DNN-ROI on always falls to
# the "[skip] no ...-anode*.tar.bz2" return).  Run 28084 idx 18 already has a
# work dir holding a traditional-chain record (clusters-apa-*, mabc-*), which
# M13 forbids overwriting, so the whole campaign runs under a uniform tag.
#
# This replicates run_img_evt.sh's PER-ANODE DNN-ROI invocation verbatim
# (lines 214-271): same nticks probe, same four TLAs, same tcmalloc preload and
# GOGC=off, same per-anode log names.  It deliberately does NOT re-implement the
# sparse-fallback / input_data staging branches -- they are unreachable when the
# DNN-ROI frames are already in the work dir, which is the only case here.
#
# Usage: d09_img_tagged.sh <run> <evt_idx> <tag>
set -euo pipefail

PDHD_DIR=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/pdhd
TCMALLOC_SO=/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4
WC_PRELOAD=""
[ "${WCT_TCMALLOC:-on}" = "on" ] && [ -f "$TCMALLOC_SO" ] && WC_PRELOAD="LD_PRELOAD=$TCMALLOC_SO"

RUN=$1; EVT=$2; TAG=$3
RUN_STRIPPED=$(echo "$RUN" | sed 's/^0*//'); [ -z "$RUN_STRIPPED" ] && RUN_STRIPPED=0
RUN_PADDED=$(printf '%06d' "$RUN_STRIPPED")
WORKDIR="$PDHD_DIR/work/${RUN_PADDED}_${EVT}_${TAG}"
BASENAME=protodunehd-sp-dnnroi-frames
INPUT_PREFIX="${WORKDIR}/${BASENAME}"

[ -d "$WORKDIR" ] || { echo "ERROR: no work dir $WORKDIR" >&2; exit 2; }
for ai in 0 1 2 3; do
    [ -f "${INPUT_PREFIX}-anode${ai}.tar.bz2" ] || {
        echo "ERROR: missing ${INPUT_PREFIX}-anode${ai}.tar.bz2 (run NF/SP DNN-ROI first)" >&2; exit 2; }
done

# nticks probe -- run_img_evt.sh:214-231.  The Reframer must match the readout
# length exactly; too short truncates real activity.
PROBE_TAR="${INPUT_PREFIX}-anode0.tar.bz2"
# NOTE: `tar tjf ... | grep -m1` under `set -o pipefail` inverts this guard --
# grep exits at the first match, tar takes SIGPIPE, the pipeline reports failure
# even though the match was found.  List once into a variable, then match.
TAR_LIST=$(tar tjf "$PROBE_TAR")
FRAME_NPY=$(printf '%s\n' "$TAR_LIST" | grep -m1 "^frame_gauss0_" || true)
[ -n "$FRAME_NPY" ] || { echo "ERROR: no frame_gauss0_* in $PROBE_TAR" >&2; exit 2; }
SHAPE_TMP=$(mktemp -d /home/xqian/tmp/d09imgnticks.XXXXXX)
tar xjf "$PROBE_TAR" -C "$SHAPE_TMP" "$FRAME_NPY"
NTICKS=$(python3 -c "
import numpy as np
a = np.load('${SHAPE_TMP}/${FRAME_NPY}', mmap_mode='r')
print(a.shape[1])
")
rm -rf "$SHAPE_TMP"
echo "$NTICKS" | grep -qE '^[0-9]+$' || { echo "ERROR: bad nticks '$NTICKS'" >&2; exit 2; }
echo "[d09img] $RUN_PADDED evt=$EVT tag=$TAG nticks=$NTICKS workdir=$WORKDIR"

cd "$PDHD_DIR"
for ai in 0 1 2 3; do
    wcsonnet \
        -A "input_prefix=${INPUT_PREFIX}" \
        -S "anode_indices=[$ai]" \
        -A "output_dir=${WORKDIR}" \
        -S "nticks=${NTICKS}" \
        -o "$WORKDIR/.wct-img-a${ai}.json" wct-img-all.jsonnet &
done
wait
for ai in 0 1 2 3; do
    [ -s "$WORKDIR/.wct-img-a${ai}.json" ] || { echo "ERROR: wcsonnet failed anode${ai}" >&2; exit 1; }
done
for ai in 0 1 2 3; do
    CFG_JSON="$WORKDIR/.wct-img-a${ai}.json"
    ALOG="$WORKDIR/wct_img_${RUN_PADDED}_${EVT}_a${ai}.log"
    rm -f "$ALOG"; t0=$SECONDS
    env $WC_PRELOAD GOGC=off wire-cell -l stderr -l "${ALOG}:debug" -L debug -c "$CFG_JSON"
    echo "[d09img] anode${ai}: $((SECONDS - t0)) s"
    rm -f "$CFG_JSON"
done
# completion marker -- a log file exists from job start, so never gate on the log
touch "$WORKDIR/.d09-img-done"
echo "[d09img] DONE $RUN_PADDED evt=$EVT"
