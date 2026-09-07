#!/usr/bin/env python3
"""doc 30: convert a jemalloc heap_v2 dump to the gperftools heap format that
google-pprof reads (jeprof is not installed on this host), applying jeprof's
own sampling correction.

jemalloc samples an allocation of size s with probability ~ s/R, R = 2**lg_prof_sample
(the number in the 'heap_v2/<R>' header).  A record holding n sampled objects of
total b bytes therefore stands for n/(1-exp(-s/R)) objects and b/(1-exp(-s/R))
bytes, with s = b/n -- this is jeprof's ScaleProfile / AddEntries correction.
Without it the dump reads ~4 orders of magnitude low.
"""
import math, re, sys

src, dst = sys.argv[1], sys.argv[2]
tstar = re.compile(r"^\s*t\*:\s*(\d+):\s*(\d+)\s*\[(\d+):\s*(\d+)\]")

def scale(n, b):
    n, b = int(n), int(b)
    if n == 0 or b == 0:
        return 0, 0
    s = b / n
    ratio = s / R
    # guard the tail: for s >> R the correction is 1
    f = 1.0 / (1.0 - math.exp(-ratio)) if ratio < 30 else 1.0
    return int(round(n * f)), int(round(b * f))

lines = open(src).read().splitlines()
R = 524288
m = re.match(r"heap_v2/(\d+)", lines[0])
if m:
    R = int(m.group(1))

recs, stack, head, mapped = [], None, None, []
for i, ln in enumerate(lines):
    if ln.startswith("MAPPED_LIBRARIES"):
        mapped = lines[i:]
        break
    m = tstar.match(ln)
    if m:
        if stack is None and head is None:
            head = m.groups()
        elif stack is not None:
            recs.append((m.groups(), stack))
            stack = None
    elif ln.startswith("@"):
        stack = ln[1:].strip()

tot_o = tot_b = 0
out = []
for (a, b, c, d), st in recs:
    so, sb = scale(a, b)
    co, cb = scale(c, d)
    tot_o += so
    tot_b += sb
    out.append("%d: %d [%d: %d] @ %s" % (so, sb, co, cb, st))

with open(dst, "w") as o:
    o.write("heap profile: %d: %d [%d: %d] @ heapprofile\n" % (tot_o, tot_b, tot_o, tot_b))
    for ln in out:
        o.write(ln + "\n")
    o.write("\n")
    for ln in mapped:
        o.write(ln + "\n")
print("%s: R=%d, %d stacks, live %.2f MB" % (src.split("/")[-1], R, len(recs), tot_b / 1048576.0))
