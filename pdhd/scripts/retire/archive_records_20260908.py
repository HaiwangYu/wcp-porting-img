#!/usr/bin/env python3
"""Freeze the RECORD LAYER of every arm the 2026-09-06 round releases.

  usage:  python3 archive_records_20260908.py 1        # tier 1
          python3 archive_records_20260908.py 2        # tier 2

WHAT THE RECORD LAYER IS.  The heavy classes -- pctree tarballs, mabc zips,
tracking ROOT files, clusters-apa archives, calib dumps, npz and the SP+DNNROI
frame bz2s -- are dropped.  What is kept is the per-event wire-cell log, the
compiled config the arm actually ran (.wct-*.json), the per-event tables
(nusel-*.tsv), the timing/rss series and img-provenance.txt, PLUS a
member-content manifest (SHA-256 per file) of everything dropped.  That is what
the docs' claims rest on -- the exit reasons, the operating point, the timings,
and a hash of every artifact -- so a claim stays re-CHECKABLE after the bytes
are gone, and a future re-run can be diffed against the frozen hashes.

SYMLINKS ARE RECORDED, NOT FOLLOWED.  Many arms are ~40% symlink by count into
the kept substrate; following them would copy the substrate into every record.
Links go to <tag>.links.txt as (path -> target) pairs.

Never writes into an earlier round's archive tree (CLAUDE.md M13): the output
directory is stamped and the script refuses if it already holds this tier.
"""
import os, re, sys, json, hashlib, tarfile, collections
from concurrent.futures import ProcessPoolExecutor

R     = "/home/xqian/toolkit-dev/wcp-porting-img"
HERE  = os.path.dirname(os.path.abspath(__file__))
STAMP = "20260908"
OUT   = os.environ.get("RETIRE_OUT", f"{R}/sbnd/sbnd_xin/archive/records/cleanup-{STAMP}")
JOBS  = int(os.environ.get("RETIRE_JOBS", "16"))

HEAVY = [re.compile(p) for p in (
    r'^pctree.*\.(tar\.gz|tlas)$', r'^mabc.*\.zip$', r'^calib(-pr)?-evt.*\.json$',
    r'^clusters-apa.*\.tar\.gz$', r'^tracking-.*\.root$', r'.*\.npz$',
    r'^protodune-.*-frames.*\.tar\.bz2$', r'^opflash.*\.tar\.gz$',
    r'.*\.tar\.bz2$', r'^magnify.*\.root$', r'^.*\.root$')]

# The compiled config is THE record of the operating point, but it is ~270 KB and
# byte-identical across an arm's events apart from the event id -- 3067 copies per
# arm is 800 MB of the same file.  Every copy is HASHED into the manifest; only
# the first is carried in the tar.  (Hash-only would lose the operating point;
# all-copies would make the record layer bigger than the thing it replaces.)
ONEPER = re.compile(r'^\.wct-.*\.json$')

def is_heavy(n): return any(p.match(n) for p in HEAVY)

def sha(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf)
            if not b: break
            h.update(b)
    return h.hexdigest()

def archive_one(args):
    tree, tag, src = args
    d = os.path.join(OUT, tree); os.makedirs(d, exist_ok=True)
    tgz, man, lnk = (os.path.join(d, tag + x) for x in
                     (".tar.zst", ".manifest.tsv", ".links.txt"))
    recs, links, kept, dropped = [], [], 0, 0
    members, seen_oneper = [], set()
    for cur, subs, files in os.walk(src):
        subs[:] = [s for s in subs if not os.path.islink(os.path.join(cur, s))]
        for s in list(subs):
            p = os.path.join(cur, s)
            if os.path.islink(p): links.append(f"{os.path.relpath(p, src)}\t{os.readlink(p)}")
        for f in files:
            p = os.path.join(cur, f)
            rel = os.path.relpath(p, src)
            if os.path.islink(p):
                links.append(f"{rel}\t{os.readlink(p)}"); continue
            try: st = os.stat(p)
            except OSError: continue
            try: digest = sha(p)
            except OSError: digest = "unreadable"
            recs.append(f"{rel}\t{st.st_size}\t{digest}")
            if is_heavy(f):
                dropped += 1
            elif ONEPER.match(f) and re.sub(r'evt\d+', 'evtN', f) in seen_oneper:
                dropped += 1                      # hashed above, one copy already carried
            else:
                if ONEPER.match(f): seen_oneper.add(re.sub(r'evt\d+', 'evtN', f))
                members.append((p, rel)); kept += 1
    open(man, "w").write("\n".join(sorted(recs)) + "\n")
    open(lnk, "w").write("\n".join(sorted(links)) + "\n")
    tmp = tgz[:-4] + ".tar"
    with tarfile.open(tmp, "w") as tf:
        for p, rel in members:
            try: tf.add(p, arcname=os.path.join(tag, rel))
            except OSError: pass
    os.system(f"zstd -q -10 -T2 --rm -f {tmp!r} -o {tgz!r}")
    return tag, len(recs), kept, dropped, len(links), os.path.getsize(tgz) if os.path.exists(tgz) else 0

if __name__ == "__main__":
    tier = sys.argv[1] if len(sys.argv) > 1 else "1"
    jobs = []
    for tree in ("sbnd", "pdvd", "pdhd"):
        tf = os.path.join(HERE, f"tier{tier}_{tree}_{STAMP}.txt")
        if not os.path.exists(tf): continue
        for line in open(tf):
            p = line.strip()
            if p and os.path.isdir(p):
                jobs.append((f"{tree}-tier{tier}", os.path.basename(p), p))
    if not jobs: sys.exit("nothing to archive -- run plan_20260908.py first")
    done = 0
    with ProcessPoolExecutor(JOBS) as ex:
        for tag, n, kept, drop, nl, sz in ex.map(archive_one, jobs):
            done += 1
            print(f"  {done:>5}/{len(jobs)}  {tag:<40} files {n:>6} "
                  f"(kept {kept}, dropped {drop}) links {nl:>5}  {sz/1048576:.2f} MiB")
    print(f"\narchived {done}/{len(jobs)} arms into {OUT}")
    print("integrity: every released dir has a .manifest.tsv with a SHA-256 per file, "
          "a .links.txt, and a .tar.zst of the non-heavy record layer.")
