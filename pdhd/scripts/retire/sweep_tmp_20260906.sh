#!/bin/bash
# ~/tmp sweep, cleanup round 2026-09-06.  DRY RUN unless CONFIRM=yes.
#
#   ./sweep_tmp_20260906.sh <tier>        tier = 1 | 2 | 3
#
# THE RULE, carried from doc 100 and refined on 09-05: this sweep removes only
# whole lib*/ snapshot dirs and dead session scratchpads.  It never removes a
# *.log/.txt/.md/.json/.tsv/.npy on its own -- a libsnap is regenerable from the
# commit its doc records, a gate log is not, and a file is a record by FUNCTION
# not by extension (the 09-05 draft would have taken d44sp's 64 .npy frames,
# which doc 44's repro block names as an INPUT).
#
# MEASURED THIS ROUND, and it is why tiers 1 and 2 are clean: every pin subdir
# below is 100.0% *.so by bytes.  Dropping one removes zero record bytes by
# construction -- there is nothing else in it.
#
# LIVENESS IS FROM ps, NEVER FROM AGE (doc 100: an 18 GiB scratchpad untouched
# for two days belonged to a running session).  At plan time, 2026-09-06 21:2x:
#   PID 3039074  claude --resume b48747db...   -> this session               KEEP
#   PID 2727386  claude (bare, cwd toolkit/)   -> a peer that started during
#                                                 this round; its session id is
#                                                 not in argv, so tier 3 also
#                                                 refuses on a RECENT MTIME.
#   PID 3026100  claude --resume 1f022d51...   -> EXITED during this round
# M1 SHAPE, stated once: a missing LD_LIBRARY_PATH directory is SILENTLY
# ignored and falls back to live local/lib.  Every path dropped here was grepped
# for across BOTH repos first; tier 1's are named by nothing at all.
set -u
T=/home/xqian/tmp
R=/home/xqian/toolkit-dev/wcp-porting-img
TIER=${1:?tier (1, 2 or 3)}
CONFIRM=${CONFIRM:-no}

# Refuse on an already-gone target: that is the signature of pointing at a
# previous round's list (doc 100 catch 2), and it is also what a second
# CONFIRM=yes run of this script looks like.
run() {
  for p in "$@"; do
    [ -e "$p" ] || { echo "   REFUSING: $p is already gone -- which round's list is this?"; exit 3; }
  done
  if [ "$CONFIRM" = yes ]; then rm -rf "$@"; else echo "   would remove: $*"; fi
}
# A pin must be 100% .so before it is treated as the regenerable class.
pure_so() {
  local d=$1
  local n; n=$(find "$d" -type f ! -name '*.so*' | wc -l)
  local kb; kb=$(find "$d" -type f ! -name '*.so*' -printf '%k\n' | awk '{s+=$1}END{print s+0}')
  [ "$kb" -lt 1024 ] || { echo "   REFUSING $d: $n non-.so files, ${kb} KiB -- not the regenerable class"; exit 4; }
}
# How many places name this exact path.  Scoped to the doc / script / gate roots
# rather than the whole 266 GiB tree: grepping the arm outputs takes hours, and a
# citation only counts where a human or a runner wrote it.
CITROOTS="$R/pdhd/docs $R/pdhd/scripts $R/pdvd/docs $R/pdvd/scripts
          $R/sbnd/sbnd_xin/docs $R/sbnd/sbnd_xin/scripts $R/qlport/scripts
          $R/pdvd/stm $R/pdhd/stm_scan $R/pdhd/ql_scan
          /home/xqian/toolkit-dev/toolkit/clus/docs"
# EXCLUDE THIS ROUND'S OWN DOC.  doc 101 sec 5 lists these paths in order to say
# that nothing names them, and grep -F then finds `d45_libpin/dbg` there and
# refuses the tier -- after two entries have already gone.  That is doc 91's
# "protected because protected" defect recurring on a new artifact: the round's
# own RECORD instead of its own tier file.  What the guard checks is therefore
# "nothing OUTSIDE this round's own record names them".
named() {
  grep -rlI --exclude-dir=.git --exclude-dir=retire \
       --exclude=101_cleanup-four-tree-retire.md \
       -F "${1#$T/}" $CITROOTS 2>/dev/null | wc -l
}

case "$TIER" in
1)
  echo "=== TMP TIER 1: pin subdirs NOTHING names, in either repo ==="
  echo "    (an un-named pin cannot even be invoked -- and a missing"
  echo "     LD_LIBRARY_PATH entry is silently ignored, so it is already inert)"
  for p in "$T/d144_libpin3" "$T/d144_libpin5" "$T/d45_libpin/dbg" \
           "$T/d41_libpin/new2" "$T/d41_libpin/new3" "$T/d41_libpin/new4" \
           "$T/d41_libpin/new5" "$T/d41_libpin/ref"; do
    [ -d "$p" ] || { echo "   (absent) $p"; continue; }
    n=$(named "$p")
    if [ "$n" != 0 ]; then
      echo "   REFUSING $p: $n files name it now -- it was 0 at plan time. Re-plan."; exit 5
    fi
    pure_so "$p"
    printf '   %-34s %8s  named_by=0  100%% .so\n' "$p" "$(du -sh "$p"|cut -f1)"
    run "$p"
  done
  ;;
2)
  echo "=== TMP TIER 2: the pins of the arms work-tier 2 releases ==="
  echo "    A pin goes WITH its arms (doc 98).  Each line names the arms it"
  echo "    backs and the commit its doc records, which is the rebuild path."
  # doc pdhd/03 sec 2 is an explicit pin<->arm<->commit ledger:
  #   new5 1af4cbbf -> d03nu1,d03nu2   new6 3482ded8 -> d03nu3,d03nu4
  #   new7 b4bd5aca -> d03nu5          new8 c557f0ff -> d03nu6
  #   new9 ea8d5540 -> d03nu7          new10 425577d6 -> d03nu8
  #   new11 a4ff5439 -> d03nu9  == THE SHIPPED BINARY, KEPT
  for s in new5 new6 new7 new8 new9 new10; do
    p="$T/d47_libpin/$s"; [ -d "$p" ] || continue
    pure_so "$p"; printf '   %-34s %8s  backs d03nu* (pdhd tier 2); doc pdhd/03 sec 2 records its commit\n' "$p" "$(du -sh "$p"|cut -f1)"
    run "$p"
  done
  # doc pr/143 sec 6.1 records both md5s and toolkit 5d0b4e77 / the new build.
  for s in final final2 new; do
    p="$T/d143_libpin/$s"; [ -d "$p" ] || continue
    pure_so "$p"; printf '   %-34s %8s  backs work-pr143-* (sbnd tier 2); doc pr/143 sec 6.1 records its md5\n' "$p" "$(du -sh "$p"|cut -f1)"
    run "$p"
  done
  # doc pr/144 line 51 records libWireCellClus.so b46179b20533eacc9cf7cf85430e7a81.
  p="$T/d144_libpin"
  if [ -d "$p" ]; then
    pure_so "$p"; printf '   %-34s %8s  backs work-*-d144on/off (sbnd tier 2); doc pr/144:51 records its md5\n' "$p" "$(du -sh "$p"|cut -f1)"
    run "$p"
  fi
  echo
  echo "   NOT dropped, deliberately: d47_libpin/new11 (the SHIPPED pdhd/03 +"
  echo "   pdvd/48 binary, backs d03nu9 and d48nu7), d144_libpin4 (the current"
  echo "   sbnd production arm d144fixprod), d144_libpin2, d145_libpin*,"
  echo "   d146_libpin*, d08_libpin, d97b-libsnap (the stage-A production"
  echo "   binary behind work-*-d97fv) and pdhdstm_libpin (pdhd PROTECTED.txt)."
  ;;
3)
  echo "=== TMP TIER 3: scratchpads of DEAD sessions ==="
  echo "    Frozen at plan time; each is re-verified against ps AND against a"
  echo "    recent mtime, because the peer that started mid-round runs a bare"
  echo "    'claude' whose session id is not in its argv."
  S="$T/claude-25225/-home-xqian-toolkit-dev-toolkit"
  # NOT listed, deliberately: 1f022d51 (its session, PID 3026100, exited DURING
  # this round and its scratchpad was written minutes before the plan -- a
  # just-exited session is next round's decision, not this one's); 217ba691 and
  # c66ec729 (61 MB and 3.6 MB, not worth a deletion decision).
  for id in 7117f9b1-c512-4158-8c4b-eb56f686d997 \
            790e6df6-e027-4fa3-904f-970589be627f; do
    d="$S/$id"; [ -d "$d" ] || { echo "   (absent) $id"; continue; }
    # MATCH ONLY REAL claude PROCESSES, by comm, never by a raw args scan: an
    # args scan matches THIS script's own invocation (and any grep/ugrep the
    # harness is running) the moment the id appears anywhere on a command line,
    # and it did -- a self-match that refuses the round for no reason.
    if ps -u "$USER" -o comm=,args= | awk -v id="$id" '$1=="claude" && index($0,id)>0' | grep -q .; then
      echo "   REFUSING $id: ps says a claude process holds this session."; exit 6
    fi
    if [ -n "$(find "$d" -newermt '-60 minutes' -print -quit 2>/dev/null)" ]; then
      echo "   SKIP $id: written within the last 60 min -- treat as a live writer."; continue
    fi
    if grep -rlqI --exclude-dir=.git --exclude-dir=retire -F "$id" $CITROOTS 2>/dev/null; then
      echo "   REFUSING $id: a doc or script names it."; exit 8
    fi
    printf '   %-40s %8s  ps: dead, mtime > 60 min, cited by nothing\n' "$id" "$(du -sh "$d"|cut -f1)"
    # Every work dir this round releases keeps a SHA-256 per file.  A scratchpad
    # holding 111578 non-.so files should not be held to a lower standard just
    # because it lives under ~/tmp: record the listing before the bytes go.
    L="$R/sbnd/sbnd_xin/archive/records/cleanup-20260906/tmp-tier3-$id.listing.txt"
    if [ "$CONFIRM" = yes ]; then
      mkdir -p "$(dirname "$L")"
      find "$d" -printf '%y\t%s\t%p\n' > "$L" 2>/dev/null
      echo "      listing -> $L ($(wc -l < "$L") entries)"
    fi
    run "$d"
  done
  echo
  echo "   KEPT: b48747db (this session) and af86aedf (its scratchpad), plus"
  echo "   claude-25225/pr33..pr36f, which doc pr/33-36 name by path."
  ;;
*) echo "tier must be 1, 2 or 3"; exit 1;;
esac

echo
df -h /home/xqian | tail -1
[ "$CONFIRM" = yes ] || echo -e "\nDRY RUN.  Re-run with CONFIRM=yes to execute."
