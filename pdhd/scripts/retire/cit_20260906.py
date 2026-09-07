#!/usr/bin/env python3
"""Token-boundary citation census over ALL trees' docs / scripts / labels / displays.

  usage:  python3 toks_20260906.py            # writes toks.txt + toks.json
          python3 cit_20260906.py toks.txt cit_20260906.json

WHAT A CITATION IS HERE.  A token is cited when it appears bounded by anything
that is not [A-Za-z0-9] -- so `d45on` does NOT match inside `d45on3`, and
`em114` does not match inside `em114c` (doc 91's false protection, which a
substring census manufactured).

THREE DEFECTS THIS FIXES, all previously measured:
  * NAME-EXACT SCORED ZERO for arms cited in brace or template form.
    work-sent97-mcp2k is written `work-sent97-{mcp1k,mcp2k,ncpi0,nuecc48}` in
    doc 98, and pr144_arms.sh:117 writes `work-<s>-d144fixprod`.  Both scored 0
    on 09-05 and survived only because PROTECTED.txt happened to name them.
    Scoring the ARM token as well as the dir name finds them.
  * THE LABEL AND DISPLAY ROOTS WERE NEVER SCANNED.  vertex_labels/ alone
    references the vtx105 arms 1724 times (doc 100); em_display/, pr148_scan/,
    nusel_labels/ and products/ are the same shape.
  * --exclude-dir=retire.  A planner that reads its own tier file scores every
    candidate "cited" and protects it because it is protected (doc 91, and again
    on 09-05 where 11 of 12 pdhd dirs came back cited and none of them were).

Two stages, because one 5.5k-alternative regex over 5 GB does not finish:
grep -F (Aho-Corasick) pulls the candidate LINES, then each line is decomposed
into its separator-bounded substrings and looked up in a set.  That is exact
token-boundary semantics, not an approximation of it.
"""
import os, re, sys, json, collections, subprocess

R  = "/home/xqian/toolkit-dev/wcp-porting-img"
TK = "/home/xqian/toolkit-dev/toolkit"
ROOTS = [f"{R}/pdhd/docs", f"{R}/pdhd/scripts", f"{R}/pdhd/stm_scan", f"{R}/pdhd/ql_scan",
         f"{R}/pdvd/docs", f"{R}/pdvd/scripts",
         f"{R}/sbnd/sbnd_xin/docs", f"{R}/sbnd/sbnd_xin/scripts",
         f"{R}/sbnd/sbnd_xin/vertex_labels", f"{R}/sbnd/sbnd_xin/em_labels",
         f"{R}/sbnd/sbnd_xin/nusel_labels", f"{R}/sbnd/sbnd_xin/overclustering_labels",
         f"{R}/sbnd/sbnd_xin/pr148_scan", f"{R}/sbnd/sbnd_xin/vtx_rules",
         f"{R}/sbnd/sbnd_xin/runs", f"{R}/sbnd/sbnd_xin/products",
         f"{R}/sbnd/sbnd_xin/em_display", f"{R}/sbnd/sbnd_xin/pr_display",
         f"{R}/sbnd/sbnd_xin/nusel_display", f"{R}/sbnd/sbnd_xin/split_display",
         f"{R}/sbnd/sbnd_xin/overclustering_display", f"{R}/sbnd/sbnd_xin/ql_scan",
         f"{R}/sbnd/sbnd_xin/stm_campaign", f"{R}/sbnd/sbnd_xin/ref",
         f"{R}/sbnd/sbnd_xin/scan-r1ql", f"{R}/sbnd/sbnd_xin/scan-r2patrec",
         f"{R}/sbnd/sbnd_xin/scan-d59k", f"{R}/sbnd/sbnd_xin/mcs_upstream",
         f"{R}/qlport/scripts", f"{TK}/clus/docs"]
ROOTS = [p for p in ROOTS if os.path.isdir(p)]

# A bare "work" matched 2006 times on 09-05 and means nothing; "keep" and "ref"
# are ordinary English in these docs as well as pdvd arm names -- the pdvd
# planner protects those two by name, not by citation.
JUNK = {"work","(bare)","new","ref","prod","bee","data","logs","docs","scripts"}
RUN  = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

def count(tokens):
    toks = {t for t in tokens if t and t not in JUNK}
    pf = os.path.abspath(f".cit_pat_{os.getpid()}")
    open(pf, "w").write("\n".join(sorted(toks)) + "\n")
    c   = collections.Counter()
    who = collections.defaultdict(collections.Counter)
    try:
        for root in ROOTS:
            r = subprocess.run(
                ["grep","-rhFI","--exclude-dir=retire","--exclude-dir=.git",
                 "--exclude=tier_*.txt","--exclude=tier?_*.txt","--exclude=*.log",
                 "-f", pf, root],
                capture_output=True, text=True, errors="ignore")
            tag = os.path.basename(root)
            for line in r.stdout.splitlines():
                for m in RUN.finditer(line):
                    s = m.group(0)
                    starts = [0] + [i+1 for i, ch in enumerate(s) if ch in "._-"]
                    ends   = [len(s)] + [i for i, ch in enumerate(s) if ch in "._-"]
                    for a in starts:
                        for b in ends:
                            if b > a:
                                t = s[a:b]
                                if t in toks:
                                    c[t] += 1; who[t][tag] += 1
    finally:
        os.unlink(pf)
    return c, who

if __name__ == "__main__":
    toks = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    c, who = count(toks)
    json.dump({"count": dict(c), "who": {k: dict(v) for k, v in who.items()}},
              open(sys.argv[2], "w"), indent=0)
    print(f"{len(toks)} tokens -> {sum(1 for t in set(toks) if c.get(t,0))} cited, "
          f"{sum(c.values())} hits")
