#!/usr/bin/env python3
"""Cut the PROTECTED arms loose from grp0825 before grp0825 is released.

  usage:  python3 materialise_20260908.py                  # report only
          CONFIRM=yes python3 materialise_20260908.py       # do the copies
          STUB=<dir> python3 materialise_20260908.py        # exercise the
                                                           # CONFIRM path on a
                                                           # throwaway tree

WHY THIS EXISTS.  sbnd_xin's Q/L arms do not hold their own imaging; they hold
DIRECTORY symlinks into it:

    work-mcp2k-d97fv/evt281325        -> work-mcp2k-grp0825/evt281325
    work-d97prodchk-mcp2k/evt281325   -> work-mcp2k-grp0825/evt281325

work-*-d97fv pins 3067 of grp0825's 3261 event dirs and is itself released this
round.  What is left borrowing are five PROTECTED arms -- work-d97prodchk-{mcp1k,
mcp2k,ncpi0,nuecc48} and work-ncpi0-d99r3prod -- and between them they pin only
119 distinct event dirs, 0.608 GiB.  Copying those 119 in turns a 16.7 GiB
substrate into a 0.608 GiB one with no protected arm losing a byte.

Without this step the round is a choice between two bad options: keep 16.7 GiB
to serve 0.6 GiB of borrows, or break a PROTECTED arm.  With it there is no
choice to make.

SAFETY, in order:
  * refuse unless every source still exists and every destination is currently a
    SYMLINK (never overwrite real data);
  * copy to a temporary sibling and os.replace() the link, so an interruption
    leaves either the link or the copy, never nothing;
  * dereference on copy (`copytree(symlinks=False)`) -- the point is to stop
    depending on the target;
  * VERIFY afterwards, before the caller is allowed to delete: same file count,
    same total bytes, and SHA-256 equality on a sample, per destination;
  * refuse to touch anything outside wcp-porting-img.

THE STUB.  Five clean dry runs on 09-06 hid three defects that lived only in the
CONFIRM=yes branch, and the fix for one of them introduced a fourth.  A dry run
proves nothing about the branch that writes.  STUB=<dir> builds a miniature of
the real shape -- an arm with a directory symlink into a substrate arm -- and
runs the REAL code path over it, so the writing branch is exercised before it is
pointed at sbnd_xin.
"""
import os, sys, shutil, hashlib, subprocess, collections

R    = "/home/xqian/toolkit-dev/wcp-porting-img"
ROOT = os.environ.get("STUB") or f"{R}/sbnd/sbnd_xin"
CONFIRM = os.environ.get("CONFIRM", "no") == "yes"
STUB    = bool(os.environ.get("STUB"))

# The arms whose bytes are about to go.  Must match plan_20260908.py's
# TREES["sbnd"]["materialise"], and INTERLOCK 12 checks that it does.
SUBSTRATE = ["work-mcp1k-grp0825", "work-mcp2k-grp0825",
             "work-ncpi0-grp0825", "work-nuecc48-grp0825"]
if STUB:
    SUBSTRATE = ["work-stub-grp0825"]

# THE DEFECT THE FIRST DRY RUN CAUGHT, and it is worth stating because it would
# not have failed loudly.  work-*-d97fv holds 3067 of the 3205 borrows -- and
# d97fv is in the SAME tier as grp0825.  Materialising for it would have copied
# 14.736 GiB into three directories that the very next step deletes: a round
# that ADDS 14.7 GiB, does 20 minutes of I/O, and then frees it again, with no
# error anywhere.  Only the SURVIVORS need cutting loose, and they pin 119 dirs
# = 0.608 GiB.  So the release set is read from the tier file rather than
# assumed, and a destination inside it is skipped.
def release_set():
    if STUB:
        return set()
    tf = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "tier2_sbnd_20260908.txt")
    if not os.path.exists(tf):
        sys.exit(f"REFUSING: {tf} missing -- run plan_20260908.py first.  "
                 "Without it this cannot tell a surviving borrower from a "
                 "doomed one, and would copy 14.7 GiB into dirs about to go.")
    return {os.path.basename(l.strip()) for l in open(tf) if l.strip()}

RELEASING = release_set()


def sha(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(buf), b""):
            h.update(b)
    return h.hexdigest()


def find_borrows():
    """[(dest_link_path, src_dir)] -- every symlink OUTSIDE the substrate arms
    that resolves into one of them.  Directory links and file links both."""
    out = []
    subs = set(SUBSTRATE)
    for d in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, d)
        if d in subs or not os.path.isdir(p) or os.path.islink(p):
            continue
        if d in RELEASING:      # a doomed borrower needs nothing copied into it
            continue
        for cur, sd, files in os.walk(p):
            # do not descend THROUGH a symlink; a dir link is itself an entry
            sd[:] = [s for s in sd if not os.path.islink(os.path.join(cur, s))]
            for e in list(sd) + files + [s for s in os.listdir(cur)
                                         if os.path.islink(os.path.join(cur, s))]:
                fp = os.path.join(cur, e)
                if not os.path.islink(fp):
                    continue
                full = os.path.normpath(os.path.join(cur, os.readlink(fp)))
                parts = full.split(os.sep)
                for i, seg in enumerate(parts):
                    if seg in subs:
                        out.append((fp, full))
                        break
    # dedupe: os.walk + the explicit link listing can both see one link
    return sorted(set(out))


def tree_stats(path):
    n = b = 0
    for cur, sd, files in os.walk(path):
        for f in files:
            fp = os.path.join(cur, f)
            if os.path.islink(fp):
                continue
            try:
                b += os.stat(fp).st_size
                n += 1
            except OSError:
                pass
    return n, b


def build_stub(d):
    """A miniature of the real shape: a substrate arm with two event dirs, one
    PROTECTED borrower holding a DIRECTORY symlink to one of them, and one
    borrower holding a FILE symlink -- both forms the tree actually uses."""
    shutil.rmtree(d, ignore_errors=True)
    sub = os.path.join(d, "work-stub-grp0825")
    for ev, payload in (("evt1", b"A" * 4096), ("evt2", b"B" * 8192)):
        os.makedirs(os.path.join(sub, ev), exist_ok=True)
        open(os.path.join(sub, ev, "icluster-apa0-active.npz"), "wb").write(payload)
        open(os.path.join(sub, ev, "img-provenance.txt"), "w").write(ev + "\n")
    bor = os.path.join(d, "work-stub-borrower")
    os.makedirs(bor, exist_ok=True)
    os.symlink(os.path.join(sub, "evt1"), os.path.join(bor, "evt1"))       # dir link
    os.makedirs(os.path.join(bor, "ql_evt2"), exist_ok=True)
    os.symlink(os.path.join(sub, "evt2", "icluster-apa0-active.npz"),      # file link
               os.path.join(bor, "ql_evt2", "icluster-apa0-active.npz"))
    return d


def main():
    if STUB and not os.path.isdir(ROOT):
        build_stub(ROOT)
        print(f"built stub tree at {ROOT}")

    borrows = find_borrows()
    if not borrows:
        print("nothing borrows from the substrate arms -- nothing to materialise")
        return 0

    # ---- preconditions, all of them, before anything is written -----------
    bad = [d for d, s in borrows if not d.startswith((R, ROOT))]
    if bad:
        sys.exit(f"REFUSING: {len(bad)} destinations outside the tree, e.g. {bad[0]}")
    gone = [s for d, s in borrows if not os.path.exists(s)]
    if gone:
        sys.exit(f"REFUSING: {len(gone)} sources already missing, e.g. {gone[0]} "
                 "-- that is what pointing at an executed round looks like")
    notlink = [d for d, s in borrows if not os.path.islink(d)]
    if notlink:
        sys.exit(f"REFUSING: {len(notlink)} destinations are not symlinks, e.g. "
                 f"{notlink[0]} -- refusing to overwrite real data")

    bysrc = collections.Counter()
    byarm = collections.Counter()
    for d, s in borrows:
        bysrc[s] += 1
        byarm[os.path.relpath(d, ROOT).split(os.sep)[0]] += 1
    kb = 0
    srcs = sorted(bysrc)
    for i in range(0, len(srcs), 300):
        r = subprocess.run(["du", "-sk"] + srcs[i:i + 300],
                           capture_output=True, text=True).stdout
        for l in r.splitlines():
            kb += int(l.split("\t")[0])
    print(f"{len(borrows)} links from {len(byarm)} arms pin {len(srcs)} sources, "
          f"{kb / 2**20:.3f} GiB to copy")
    for a, n in byarm.most_common():
        print(f"   {n:6d} links   {a}")

    if not CONFIRM:
        print("\nDRY RUN.  Re-run with CONFIRM=yes to materialise.")
        return 0

    # ---- do it -----------------------------------------------------------
    done = 0
    for dest, src in borrows:
        tmp = dest + ".materialising"
        shutil.rmtree(tmp, ignore_errors=True)
        if os.path.isdir(src):
            shutil.copytree(src, tmp, symlinks=False)
        else:
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            shutil.copy2(src, tmp, follow_symlinks=True)
        os.unlink(dest)          # the link, never its target
        os.replace(tmp, dest)
        done += 1
    print(f"materialised {done} links")

    # ---- VERIFY before the caller is allowed to delete --------------------
    fail = []
    for dest, src in borrows:
        if os.path.islink(dest):
            fail.append(f"{dest} is still a symlink"); continue
        if os.path.isdir(src):
            ns, bs = tree_stats(src)
            nd, bd = tree_stats(dest)
            if (ns, bs) != (nd, bd):
                fail.append(f"{dest}: {nd} files/{bd} B vs source {ns}/{bs}")
        else:
            if os.path.getsize(dest) != os.path.getsize(src):
                fail.append(f"{dest}: size differs from source")
    # content sample: hash equality on up to 40 files, both forms
    sample, i = [], 0
    for dest, src in borrows:
        if os.path.isdir(src):
            for cur, sd, files in os.walk(src):
                for f in files:
                    sample.append((os.path.join(cur, f),
                                   os.path.join(dest, os.path.relpath(
                                       os.path.join(cur, f), src))))
                    break
                break
        else:
            sample.append((src, dest))
        i += 1
        if len(sample) >= 40:
            break
    for s, d in sample:
        try:
            if sha(s) != sha(d):
                fail.append(f"{d}: SHA-256 differs from {s}")
        except OSError as e:
            fail.append(f"{d}: unreadable ({e})")
    left = find_borrows()
    if left:
        fail.append(f"{len(left)} links still resolve into the substrate, "
                    f"e.g. {left[0][0]}")

    if fail:
        print("\nVERIFY FAILED -- do NOT delete the substrate:")
        for f in fail[:20]:
            print("   " + f)
        return 2
    print(f"VERIFY OK: 0 links left into the substrate, {len(sample)} files "
          f"SHA-256-identical, every destination whole.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
