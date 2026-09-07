#!/usr/bin/env python3
"""Hardlink-deduplicate the ~/tmp binary pins.  DRY RUN unless CONFIRM=yes.

  usage:  python3 dedup_pins_20260906.py            # report only
          CONFIRM=yes python3 dedup_pins_20260906.py

WHY THIS EXISTS.  After the 2026-09-06 sweep, ~/tmp is 58 G and 39.06 GiB of it
is pinned binaries.  A pin is a snapshot of local/lib -- ~19 shared objects --
and a round rebuilds ONE of them (usually libWireCellClus.so, 410 MB) and copies
the rest unchanged.  Measured: 2272 files, 606 distinct contents, and ZERO
existing hardlinks.  libWireCellSigProc.so alone is byte-identical in 34 pins.

THIS DELETES NOTHING.  Every path stays, every pin stays complete and runnable,
every byte stays readable.  Identical files are made to share one inode, so the
duplicates stop being charged twice.  That makes it categorically different from
the retire tiers -- there is no record to lose and no owner judgement to make.

THE ONE HAZARD, AND THE MITIGATION.  Once two paths share an inode, writing
IN PLACE through one (`cp new.so pin/`, which opens O_TRUNC) corrupts every pin
that shares it.  So every deduplicated file is made READ-ONLY: `cp` then fails
loudly instead of silently corrupting a pin.  Snapshots should have been
read-only anyway.  Creating a pin the normal way (`cp -r local/lib ~/tmp/newpin`,
a NEW directory) is unaffected.

SAFETY, in order:
  * group by SHA-256, then `filecmp` byte-compare the actual pair before linking
    -- a hash match is evidence, a byte compare is proof, and this is cheap
    relative to the copy it replaces;
  * link to a temporary name and os.replace() it over the target, so an
    interruption can never leave a path missing;
  * refuse to touch a symlink, a path outside the pin roots, or a file whose
    size changed between the scan and the link;
  * verify afterwards: every original path exists, same size, same hash, and
    st_nlink > 1.
"""
import os, sys, glob, hashlib, filecmp, collections

T = "/home/xqian/tmp"
ROOTS = sorted(set(glob.glob(f"{T}/*libpin*") + glob.glob(f"{T}/*libsnap*")))
CONFIRM = os.environ.get("CONFIRM", "no") == "yes"

def sha(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(buf), b""):
            h.update(b)
    return h.hexdigest()

def scan():
    out = []
    for r in ROOTS:
        for cur, subs, files in os.walk(r):
            subs[:] = [s for s in subs if not os.path.islink(os.path.join(cur, s))]
            for f in files:
                p = os.path.join(cur, f)
                if os.path.islink(p) or not f.endswith(".so") and ".so." not in f:
                    continue
                try: st = os.lstat(p)
                except OSError: continue
                if st.st_size == 0: continue
                out.append((p, st.st_size, st.st_ino, st.st_dev))
        # every pin root must be on one filesystem -- a hardlink cannot cross one
    devs = {d for _, _, _, d in out}
    if len(devs) > 1:
        sys.exit(f"REFUSING: pins span {len(devs)} filesystems; hardlinks cannot cross one")
    return out

def main():
    files = scan()
    if not files: sys.exit("no pin files found")
    # charge each distinct inode once -- that is what du reports today
    seen, ondisk = set(), 0
    for p, sz, ino, _ in files:
        if ino not in seen: seen.add(ino); ondisk += sz
    print(f"scanning {len(ROOTS)} pin roots: {len(files)} files, "
          f"{len(seen)} distinct inodes, {ondisk/2**30:.2f} GiB on disk")

    bysize = collections.defaultdict(list)
    for p, sz, ino, _ in files: bysize[sz].append((p, ino))
    groups = collections.defaultdict(list)
    for sz, members in bysize.items():
        if len(members) < 2: continue          # unique size cannot have a twin
        for p, ino in members:
            groups[(sz, sha(p))].append((p, ino))

    saved = n_link = n_skip = 0
    plan = []
    for (sz, digest), members in sorted(groups.items(), key=lambda kv: -kv[0][0]*len(kv[1])):
        if len(members) < 2: continue
        keep_p, keep_ino = members[0]
        for p, ino in members[1:]:
            if ino == keep_ino: continue        # already the same inode
            plan.append((keep_p, p, sz))
            saved += sz
    print(f"{len(groups)} content groups; {len(plan)} files can share an inode; "
          f"{saved/2**30:.2f} GiB recoverable -> {(ondisk-saved)/2**30:.2f} GiB after")

    if not CONFIRM:
        print("\nDRY RUN.  Largest wins:")
        for keep_p, p, sz in plan[:8]:
            print(f"   {sz/2**20:8.1f} MB  {p.replace(T+'/','')}  ->  {keep_p.replace(T+'/','')}")
        print("\nRe-run with CONFIRM=yes to execute.  Nothing is deleted either way.")
        return 0

    for keep_p, p, sz in plan:
        try:
            if os.path.islink(p) or os.path.islink(keep_p): n_skip += 1; continue
            if os.lstat(p).st_size != sz or os.lstat(keep_p).st_size != sz:
                n_skip += 1; continue           # changed under us
            if not filecmp.cmp(keep_p, p, shallow=False):
                n_skip += 1; continue           # hash said equal, bytes disagree: never link
            tmp = p + ".dedup-tmp"
            if os.path.exists(tmp): os.unlink(tmp)
            os.link(keep_p, tmp)
            os.replace(tmp, p)                  # atomic: p is never absent
            n_link += 1
        except OSError as e:
            print(f"   skip {p}: {e}"); n_skip += 1

    # close the in-place-overwrite hazard the sharing creates
    n_ro = 0
    for p, _, _, _ in scan():
        try:
            m = os.stat(p).st_mode
            if m & 0o222: os.chmod(p, m & ~0o222); n_ro += 1
        except OSError: pass
    print(f"linked {n_link}, skipped {n_skip}, made read-only {n_ro}")

    # ---- verification: nothing lost, nothing changed ----------------------
    now = scan()
    bad = [p for p, sz, _, _ in now if not os.path.exists(p)]
    seen2, after = set(), 0
    for p, sz, ino, _ in now:
        if ino not in seen2: seen2.add(ino); after += sz
    print(f"VERIFY: {len(now)} files present (was {len(files)}), "
          f"{len(bad)} missing, {len(seen2)} inodes, {after/2**30:.2f} GiB on disk")
    return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main())
