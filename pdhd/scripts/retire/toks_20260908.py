#!/usr/bin/env python3
"""Emit every token an arm dir can legitimately be cited BY.

  usage:  python3 toks_20260908.py     # writes toks.txt (flat) + toks.json (per dir)

WHY MORE THAN THE DIR NAME.  Docs and runners name an arm in at least four
shapes, and a census that knows only one silently scores the others zero:

  work-mcp2k-d144fixprod        the dir itself
  work-<s>-d144fixprod          a TEMPLATE  (pr144_arms.sh:117)
  work-sent97-{mcp1k,mcp2k,...} a BRACE set (doc 98)
  work-stmcamp-d42gate{old,new} a brace set on the TAIL segment
  d48gatenew                    the bare tail token (doc pdhd/03)

So each dir emits every contiguous hyphen-segment RANGE of its name after the
`work-` prefix, plus the sample-stripped arm and the round prefix.  Ranges that
are only a sample name or a bare English/role word are dropped -- `mcp2k`,
`on`, `off`, `ref`, `new` match everywhere and mean nothing.

Over-emitting is the SAFE direction here: an extra token can only pull a dir
OUT of the release.  Under-emitting is what cost work-sent97-* and
work-vtx105-base-* their citations on 09-05, where PROTECTED.txt happened to
catch them and nothing else would have.
"""
import os, re, json
R = "/home/xqian/toolkit-dev/wcp-porting-img"
EVT  = re.compile(r"^(\d{6})_(\d+)(?:_(.+))?$")
SAMP = re.compile(r"-(mcp1k|mcp2k|ncpi0|nuecc48|dbg25a)(?=-|$)|^(mcp1k|mcp2k|ncpi0|nuecc48|dbg25a)-")
# A range consisting only of these is not a citation of anything.
GENERIC = {"mcp1k","mcp2k","ncpi0","nuecc48","dbg25a","on","off","new","old","ref",
           "base","prod","final","probe","dump","gate","all","fix","keep","work",
           "bare","(bare)","full","pr","t0","cont","np","sat","sv","g1","g2","g3"}
TREES = {"sbnd": (f"{R}/sbnd/sbnd_xin", "siblingdir"),
         "pdvd": (f"{R}/pdvd/work",     "armsuffix"),
         "pdhd": (f"{R}/pdhd/work",     "armsuffix")}

ROUNDONLY = re.compile(r"^(pr|d|vtx|s)\d+$")     # the round itself, not an arm
ROUNDMARK = re.compile(r"^(pr|d|vtx|s)\d+")      # a segment that carries a round

def ranges(name):
    """Every contiguous hyphen-segment range, minus the ones that name nothing.

    Two exclusions, both measured:
      * all-generic ranges -- `off`, `mcp2k`, `new` appear everywhere.
      * the bare ROUND token.  `d147` alone is cited 552 times; letting it stand
        as a citation of work-d147-off1-mcp1k makes every arm of every round
        "cited" and INTERLOCK 6 then keeps the whole tree.  A round is not an
        arm.  It is still emitted when it IS the arm's whole name.
    """
    seg = name.split("-")
    out = set()
    for i in range(len(seg)):
        for j in range(i + 1, len(seg) + 1):
            r = seg[i:j]
            if all(s in GENERIC or s.isdigit() for s in r):   # "off2b" kept; "off" dropped
                continue
            tok = "-".join(r)
            if ROUNDONLY.match(tok) and tok != name:
                continue
            # A proper sub-range only counts as an ARM NAME if some segment is
            # ROUND-MARKED (d48gatenew, s144neg, vtx105, pr143-on).  Measured
            # over-matches without this: `cone` from work-s144neg-cone scores
            # 57017 -- an ordinary physics word -- and `off1-mcp1k` scores 132
            # from a different round's arm entirely.  The whole arm and the
            # whole dir are always emitted, so short real names (`stm0`) and
            # unmarked family names (`sent97`, `grp0825`) are not lost.
            if tok != name and not any(ROUNDMARK.match(x) for x in r):
                continue
            out.add(tok)
    return out

out = {}
for t, (W, unit) in TREES.items():
    for d in sorted(os.listdir(W)):
        p = os.path.join(W, d)
        if not os.path.isdir(p) or os.path.islink(p): continue
        if unit == "armsuffix":
            m = EVT.match(d)
            if not m: continue
            arm = m.group(3) or "(bare)"
            toks = {d, arm} | ranges(arm)
        else:
            if not d.startswith("work-"): continue
            arm  = SAMP.sub("", d[5:]).strip("-")
            toks = {d, arm} | ranges(d[5:]) | ranges(arm)
        rnd = re.match(r"^(pr\d+|d\d+|vtx\d+|s\d+)", arm)
        out[f"{t}\t{d}"] = dict(dir=d, arm=arm, round=rnd.group(1) if rnd else "",
                                toks=sorted(x for x in toks if x and x not in GENERIC))
json.dump(out, open("toks.json", "w"), indent=0)
allt = set()
for v in out.values():
    allt |= set(v["toks"]) | {v["dir"], v["arm"]} | ({v["round"]} if v["round"] else set())
allt = {x for x in allt if x and x not in GENERIC}
open("toks.txt", "w").write("\n".join(sorted(allt)) + "\n")
print(len(out), "dirs", len(allt), "tokens")
