#!/usr/bin/env python3
"""
Cleanup round 2026-09-08 -- planner for sbnd_xin + pdvd + pdhd.

Owner: "with the latest production, I think we can clean up a bit the disk space
for sbnd_xin, pdhd, pdvd, and ~/tmp to recover some disk.  For the sbnd_xin, we
want to keep the most recent campaign, but we can retire some earlier campaign
results to save space."

Fork of plan_20260906.py.  EVERYTHING load-bearing in that file is carried
unchanged -- the 11 interlocks, the alias-safe owner_of(), the transitive
substrate closure, the live-writer guard, --exclude-dir=retire on the census.
Read that file's header for why each exists.  What follows is what THIS round
changes and why.

WHAT IS NEW IN THIS ROUND

  1. "THE LATEST CAMPAIGN" MOVED, AND IT IS SELF-CONTAINED.  Doc 102
     (2026-09-08) produced the four-sample validation set at WCT master
     eacacafe: work-*-d102m (stage A) + work-*-d102mpr (stage B), 3067 events,
     ref/prod-2026-09-08.  MEASURED, not assumed: a symlink census over both
     target spellings (28415 links in the tree) finds ZERO cross-arm edges out
     of those eight dirs.  The 12268 links inside them are all intra-arm
     `ql_evt<N>/x -> ../evt<N>/x`, 0 broken.  So no earlier campaign is
     substrate for the new one, and INTERLOCK 2's closure has nothing to pull
     back on the sbnd side.

  2. THE SBND TIER 2 IS ONE THING: THE SUPERSEDED prod-2026-09-04 CHAIN.
     grp0825 (imaging, doc 81 epoch) -> d97fv (stage A Q/L) -> d144fixprod
     (stage B).  All three are named LATEST PRODUCTION or SUBSTRATE in
     sbnd_xin/scripts/retire/PROTECTED.txt, so all three edit that file rather
     than only disk -- which is exactly what made work-*-d97fvpr2 a tier-2 line
     on 09-06 instead of a tier-1 one.  One CONFIRM, three grounds, three costs.

  3. grp0825 NEEDS A MATERIALISE STEP AND IT IS CHEAP.  Its evt<N> dirs are
     borrowed as DIRECTORY symlinks: work-*-d97fv/evt<N> -> grp0825/evt<N>.
     Measured this round: 3067 of grp0825's 3261 event dirs are pinned by
     work-*-d97fv alone.  Once d97fv is released the only remaining borrowers
     are work-d97prodchk-* (119 links) and work-ncpi0-d99r3prod (19), both
     PROTECTED, and together they pin 119 distinct event dirs = 0.608 GiB.
     Copying those 119 in first turns a 16.7 GiB substrate into a 0.608 GiB one
     with no protected arm losing anything.  The retire driver does that copy
     and re-verifies before it deletes; see retire_20260908.sh, step MATERIALISE.

  4. pdvd AND pdhd RELEASE ALMOST NOTHING, AND THAT IS THE ANSWER.  Measured
     2026-09-08: EVERY arm family in both trees carries at least one doc
     citation, and the two largest (pdhd d09 10.18 GiB, pdvd d51vclus 3.29 GiB)
     belong to rounds dated 09-07/09-08.  An arm backing yesterday's decision is
     not superseded (the 08-31 prod0825 doctrine).  The d51v*/d51h* families had
     NO doc when this round opened -- doc pdvd/50 was still being edited -- which
     is the exact shape a citation census scores zero, so they were written into
     both PROTECTED.txt files by PREFIX before the first plan run.

  5. THE REAL pdhd LEVER IS NOT A WORK DIR.  l1sp_wf_v9 is 11 GiB, 889589 npz,
     zero citations -- which is the trap, not the licence (09-05).  It is put to
     the owner as a question in doc 103, not staged here.

This script RETIRES NOTHING.  It prints a plan and writes tier files.
"""
import os, re, sys, json, time, subprocess, collections, glob

R     = "/home/xqian/toolkit-dev/wcp-porting-img"
STAMP = "20260908"
HERE  = os.path.dirname(os.path.abspath(__file__))
EVT   = re.compile(r"^(\d{6})_(\d+)(?:_(.+))?$")          # <run6>_<idx>[_<arm>]
SAMP  = re.compile(r"-(mcp1k|mcp2k|ncpi0|nuecc48|dbg25a)(?=-|$)|^(mcp1k|mcp2k|ncpi0|nuecc48|dbg25a)-")

# --------------------------------------------------------------- per tree --
TREES = {
 "sbnd": dict(
   root=f"{R}/sbnd/sbnd_xin", work=f"{R}/sbnd/sbnd_xin", unit="siblingdir",
   # THE INPUT.  grp0825's evt<N> half is the doc-81-epoch imaging that the
   # prod-2026-09-04 Q/L arms borrow.  It is listed here as substrate AND named
   # in tier 2: the tier-2 line is the deliberate override, and INTERLOCK 10 +
   # the driver's MATERIALISE step are what make that override safe.
   # dbg25a-ql was regenerated 09-05 and 100 links resolve through it.
   substrate=["work-mcp2k-grp0825","work-mcp1k-grp0825",
              "work-ncpi0-grp0825","work-nuecc48-grp0825","work-dbg25a-ql"],
   # THE LATEST PRODUCTION -- doc 102, ref/prod-2026-09-08, from primary source
   # (the doc's own repro block and ref/prod-2026-09-08/README.md), never the
   # `prod` substring.  Stage A does its own imaging from the reco1 art files,
   # which is why it is self-contained where d97fv was not.
   production=["work-mcp1k-d102m","work-mcp2k-d102m","work-ncpi0-d102m","work-nuecc48-d102m",
               "work-mcp1k-d102mpr","work-mcp2k-d102mpr",
               "work-ncpi0-d102mpr","work-nuecc48-d102mpr"],
   # The per-flip arms.  Doc 102 sec 0 lists the 8 keys that entered production
   # between master and eacacafe; each of these is one of those flips' evidence,
   # they total under 0.5 GiB, and doc 101 kept them for that reason.
   flip_evidence=["work-mcp1k-d145prod","work-mcp2k-d145prod",
                  "work-ncpi0-d145prod","work-nuecc48-d145prod",
                  "work-mcp1k-d146sv25","work-mcp2k-d146sv25",
                  "work-ncpi0-d146sv25","work-nuecc48-d146sv25",
                  "work-d147-tailflip-mcp1k","work-d147-tailflip-mcp2k",
                  "work-d147-flipchk-mcp1k","work-d147-flipchk-mcp2k",
                  "work-d147-c8-mcp1k","work-d147-c8-mcp2k",
                  "work-d147-tail8-mcp1k","work-d147-tail8-mcp2k"],
   # An open round's arms are protected by PREFIX, never by enumeration.
   open_prefix=("work-d149","work-d150","work-d151","work-d152",
                "work-mcp1k-d149","work-mcp2k-d149","work-ncpi0-d149","work-nuecc48-d149",
                "work-d103","work-d104"),
   keep_arms=[
     # doc pr/148 sec 16 names work-*-d145np as the arm the NEXT round reads
     # (item 2's WCT_SHOWER_SPLIT_DEBUG re-run on 137238 and 100222, and item 3's
     # bisect).  That section is a plan for a session that has not happened:
     # pr/148 is an OPEN round and its named input stays, campaign or no.
     "work-mcp1k-d145np","work-mcp2k-d145np","work-ncpi0-d145np","work-nuecc48-d145np",
     # the 2x2 negative-control layer of the sentinel suite and the 31/31
     # witness -- doc 98's lesson, kept explicitly on 09-06 and unchanged here.
     "work-s144pos-mcp1k","work-s144pos-mcp2k","work-s144pos-nuecc48",
     "work-s144posleg-mcp1k","work-s144posleg-mcp2k","work-s144posleg-nuecc48",
     "work-s144neg-dvtx","work-s144neg-prox","work-s144neg-gf","work-s144neg-sccc",
     "work-s144neg-memgeo","work-s144neg-backg","work-s144neg-cone","work-s144neg-bfill",
   ],
   # ------------------------------------------------------------------------
   # TIER 2.  Named BY HAND, one ground and one stated cost per family.  Nothing
   # here is derived, and every line edits PROTECTED.txt, so the whole tier is a
   # single explicit owner decision.  This IS the owner's "retire some earlier
   # campaign results": it is the complete prod-2026-09-04 chain and nothing else.
   # ------------------------------------------------------------------------
   tier2={
     "work-mcp1k-d97fv":
       "**PREVIOUS PRODUCTION stage A**, ref/prod-2026-09-04 (sep_fv_point ON, 3067 evts), superseded by work-*-d102m at ref/prod-2026-09-08 -- a NEWER toolkit (eacacafe = master), the SAME 3067 events, and self-contained rather than borrowing its imaging.  Its own bytes are the 3067 ql_evt<N> Q/L outputs; its evt<N> entries are directory symlinks into grp0825 and free nothing themselves.  COST, stated: doc 97's per-event Q/L products at the 09-04 operating point become text-only; products/prod0902/ and products/prod0904/ stay committed, and doc 102's score tables are the 09-08 replacement.  EDITS PROTECTED.txt (the 'LATEST PRODUCTION stage A' line), so it needs an explicit owner yes.",
     "work-mcp2k-d97fv":   "as work-mcp1k-d97fv.",
     "work-ncpi0-d97fv":   "as work-mcp1k-d97fv.",
     "work-nuecc48-d97fv": "as work-mcp1k-d97fv.",

     "work-mcp1k-d144fixprod":
       "**PREVIOUS PRODUCTION stage B (PR tail)**, 3067/3067 rc=0, doc pr/144 sec 16.3.1, superseded by work-*-d102mpr: the same 3067 events through the same 15-stage chain at the operating point doc 102 sec 0 enumerates (it ADDS pr/145 item 4, pr/146, pr/147 r2 and doc 99 r3 on top of the d144 point).  COST, stated: doc pr/144 sec 7's byte gate d144on-vs-d144fixprod becomes text-only, and the sentinel suite loses its pre-pr/145 knob-off control -- run it against work-*-d102mpr, which IS the current operating point, and read a d144-era FAIL as an arm mismatch and not a regression (doc 101 sec 8.9).  EDITS PROTECTED.txt, so it needs an explicit owner yes.",
     "work-mcp2k-d144fixprod":   "as work-mcp1k-d144fixprod.",
     "work-ncpi0-d144fixprod":   "as work-mcp1k-d144fixprod.",
     "work-nuecc48-d144fixprod": "as work-mcp1k-d144fixprod.",

     "work-mcp1k-grp0825":
       "**THE doc-81-EPOCH IMAGING SUBSTRATE**, 3261 event dirs / 16.7 GiB across the four samples.  It exists to be borrowed: 3067 of its event dirs are pinned by work-*-d97fv alone, which this tier releases.  The five surviving borrowers -- work-d97prodchk-{mcp1k,mcp2k,ncpi0,nuecc48} and work-ncpi0-d99r3prod, both PROTECTED -- pin 119 distinct event dirs totalling 0.608 GiB, and the retire driver COPIES those 119 in and re-verifies before deleting anything (step MATERIALISE).  The new campaign does not need it: work-*-d102m re-imaged all 3067 events itself from the reco1 art files, which are on disk in input_files_reco1/.  COST, stated: the 08-25-epoch imaging stops being re-readable, so any future A/B against that epoch has to regenerate it from reco1 rather than read it.  EDITS PROTECTED.txt (the 'doc 81 stage A IMAGING' line), so it needs an explicit owner yes.",
     "work-mcp2k-grp0825":   "as work-mcp1k-grp0825.",
     "work-ncpi0-grp0825":   "as work-mcp1k-grp0825.",
     "work-nuecc48-grp0825": "as work-mcp1k-grp0825.",
   },
   tier3={},
   tier4={},
 ),

 "pdvd": dict(
   root=f"{R}/pdvd", work=f"{R}/pdvd/work", unit="armsuffix",
   substrate=["keep","d27fresh","d41prov","d39r2prov","d143pnew","d28dlfp","d34base"],
   production=["d48nu7","d48nu3","d48flipcfg","d45prod"],
   flip_evidence=["d43p90c5","d43prod","d42fit","d44sig","d44sigb","d44sign6",
                  "d44ref","d41prod","d44prod","d38qnewprod"],
   # d51v is doc pdvd/50 round 2, still being edited on 2026-09-08; d30v/d14-16v
   # are 09-07 rounds.  Prefixes, not names: on 09-04 a live round created seven
   # new families between plan and confirm.
   # WIDENED after the first plan run.  The narrow form left d15trace, d16smoke,
   # d14chk and d11vprod (5 dirs, 0.04 GiB) in tier 1 because they carry no
   # citation -- but docs pdhd/14, 15, 16 and pdvd/30 are all dated 09-07/09-08
   # and a probe of a round that closed yesterday is not superseded (the 08-31
   # prod0825 doctrine).  0.04 GiB is not worth reaching into a live round for.
   open_prefix=("d51v","d30","d16","d15","d14","d11v","d146","d08","d143f",
                "d48leg","d48stm","d48smoke","d48cfg","d52","d53"),
   keep_arms=["d31r6e2e","magnify","d37off1","d37on05","d39stm2","d40rep",
              "d40aniso0","d40trace","d42fitnew2","d46base","d15leg",
              "ql_scores","ql_labels","stm_michel_labels"],
   # NOTHING.  Every remaining family is cited by a doc dated 09-05 or later, or
   # is substrate.  Measured, not asserted -- see doc 103 sec 4.
   tier2={}, tier3={}, tier4={},
 ),

 "pdhd": dict(
   root=f"{R}/pdhd", work=f"{R}/pdhd/work", unit="armsuffix",
   substrate=["(bare)","stm0","stmwc","d06base","d06um","d02prod","wcc","d05mON"],
   production=["d03nu9","d08cap10","d08both","d08gref","d08goff","stmw"],
   flip_evidence=["stmc4000","stmc2000","stmc1000","stmc250",
                  "phdump","phdumpw","phdumpx","phdumpwc","wccdump","wccdumpw",
                  "qlt","perfslide"],
   # WIDENED for the same reason: d30r2cen/d30r2c2/d30r2mv/d30r3goff/d30r3gp3/
   # d30b2 (12 dirs, 0.11 GiB) are doc pdvd/30's PDHD-side probes, dated 09-07.
   open_prefix=("d51h","d09","d30","d16","d15","d14","d11","d02",
                "d146","d08","d143f","d48","d46","ql","d17","d18"),
   keep_arms=["d05prod","d05wc","d05p","d04bee","d02fix","d02ref","d02sig","d02sigb",
              "d05mOFF","d46skip"],
   # NOTHING.  Same measurement as pdvd: every family carries a citation and the
   # largest (d09, 10.18 GiB) is doc pdhd/09, dated 2026-09-07.
   tier2={}, tier3={}, tier4={},
 ),
}

# ------------------------------------------------------------ inventories --
def load_citations():
    p = os.path.join(HERE, f"cit_{STAMP}.json")
    t = os.path.join(HERE, "toks.json")
    for f in (p, t):
        if not os.path.exists(f):
            sys.exit(f"missing {f} -- run:  python3 toks_{STAMP}.py && "
                     f"python3 cit_{STAMP}.py toks.txt cit_{STAMP}.json")
    d = json.load(open(p))
    toks = {k.split("\t", 1)[1]: v["toks"] for k, v in json.load(open(t)).items()}
    return d["count"], d.get("who", {}), toks

def protected_lines():
    """Union of every PROTECTED.txt in the tree (field 1, whitespace-split)."""
    names = set()
    for p in (f"{R}/sbnd/sbnd_xin/scripts/retire/PROTECTED.txt",
              f"{R}/pdhd/scripts/retire/PROTECTED.txt",
              f"{R}/pdvd/scripts/retire/PROTECTED.txt"):
        if not os.path.exists(p): continue
        for line in open(p):
            line = line.strip()
            if not line or line.startswith("#"): continue
            names.update(line.split("\t")[0].split())
    return names

CIT, WHO, TOKS = load_citations()
PROT     = protected_lines()
fails    = []

def check(tree, n, ok, msg):
    print(f"  {'PASS' if ok else 'FAIL'}  INTERLOCK {n}: {msg}")
    if not ok: fails.append((tree, n))

def du_kb(paths):
    out = {}
    for i in range(0, len(paths), 400):
        r = subprocess.run(["du","-sk"]+paths[i:i+400], capture_output=True, text=True).stdout
        for l in r.splitlines():
            kb, p = l.split("\t", 1); out[os.path.basename(p)] = int(kb)
    return out

def arm_token(d, unit):
    if unit == "armsuffix":
        m = EVT.match(d)
        return None if not m else (m.group(3) or "(bare)")
    return SAMP.sub("", d[5:]).strip("-") if d.startswith("work-") else None

def owner_of(linkpath):
    """Owning arm dir of a symlink TARGET, by grammar match on the normalised
    path parts.  Never relpath against a ROOT constant -- that was vacuous for
    absolutely-spelled links because /nfs/data/1/... is itself a symlink."""
    full = os.path.normpath(os.path.join(os.path.dirname(linkpath),
                                         os.readlink(linkpath)))
    own = None
    for part in full.split(os.sep):
        if EVT.match(part) or part.startswith("work-"): own = part
    return own

# ------------------------------------------------------------------ plan ---
def plan_tree(tree, cfg):
    print(f"\n{'='*78}\n== {tree}   ({cfg['work']})\n{'='*78}")
    WORK, unit = cfg["work"], cfg["unit"]
    entries = sorted(d for d in os.listdir(WORK)
                     if os.path.isdir(os.path.join(WORK, d))
                     and not os.path.islink(os.path.join(WORK, d)))
    parsed    = {d: arm_token(d, unit) for d in entries}
    universe  = {d: a for d, a in parsed.items() if a is not None}
    out_scope = sorted(d for d, a in parsed.items() if a is None)

    keep_names = (set(cfg["substrate"]) | set(cfg["production"])
                  | set(cfg["flip_evidence"]) | set(cfg["keep_arms"]))
    tier2_names = set(cfg["tier2"]); tier3_names = set(cfg.get("tier3", {})); tier4_names = set(cfg.get("tier4", {}))
    def is_open(d, a):
        return d.startswith(cfg["open_prefix"]) or (a or "").startswith(cfg["open_prefix"])
    keep_dirs = {d for d, a in universe.items()
                 if d in keep_names or a in keep_names or is_open(d, a)}
    for d, a in universe.items():
        if d in PROT or a in PROT or any(a == p.strip("*") for p in PROT):
            keep_dirs.add(d)
    keep_dirs -= {d for d, a in universe.items()
                  if d in tier2_names or a in tier2_names
                  or d in tier3_names or a in tier3_names
                  or d in tier4_names or a in tier4_names}

    cand = {d for d in universe} - keep_dirs
    tier2 = sorted(d for d in cand if d in tier2_names or universe[d] in tier2_names)
    tier3 = sorted(d for d in cand if d in tier3_names or universe[d] in tier3_names)
    tier4 = sorted(d for d in cand if d in tier4_names or universe[d] in tier4_names)
    rest  = sorted(cand - set(tier2) - set(tier3) - set(tier4))

    def cited(d):
        return max([CIT.get(d, 0), CIT.get(universe[d] or "", 0)]
                   + [CIT.get(t, 0) for t in TOKS.get(d, ())])
    CITED = sorted(d for d in rest if cited(d))
    tier1 = [d for d in rest if d not in set(CITED)]
    keep_dirs |= set(CITED)

    # --- transitive closure: keeping a dir means keeping its substrate -----
    # THE ONE DELIBERATE EXEMPTION, and why it is safe.  grp0825 is released
    # while work-d97prodchk-* and work-ncpi0-d99r3prod still borrow 138 links
    # from it, so a blind closure would pull it straight back and free 0.  The
    # driver's MATERIALISE step copies those 119 target dirs (0.608 GiB) into
    # the borrowers and re-verifies BEFORE any delete; INTERLOCK 12 below
    # asserts that step exists and is priced.  Nothing else is exempt.
    MATERIALISE = set(cfg.get("materialise", ()))
    relset = set(tier1) | set(tier2) | set(tier3) | set(tier4)
    for _ in range(12):
        pull = set()
        for d in keep_dirs:
            for cur, sub, files in os.walk(os.path.join(WORK, d)):
                for e in files + sub:
                    fp = os.path.join(cur, e)
                    if os.path.islink(fp):
                        o = owner_of(fp)
                        if o in relset and o not in MATERIALISE: pull.add(o)
        if not pull: break
        keep_dirs |= pull; relset -= pull
    closure = sorted((set(tier1) | set(tier2) | set(tier3) | set(tier4)) - relset)
    tier1 = [d for d in tier1 if d in relset]
    tier2 = [d for d in tier2 if d in relset]
    tier3 = [d for d in tier3 if d in relset]
    tier4 = [d for d in tier4 if d in relset]
    if closure:
        print(f"        closure: +{len(closure)} dirs pulled back as substrate of a kept dir")

    KEEP = sorted(keep_dirs)

    # ---- INTERLOCK 1: substrate present, at full per-event coverage
    def ndirs(name):
        return sum(1 for d, a in universe.items() if d == name or a == name)
    cnt   = collections.Counter(universe.values())
    full  = max(cnt.values()) if cnt else 0
    subs_live = [a for a in cfg["substrate"] if a not in MATERIALISE]
    short = {a: ndirs(a) for a in subs_live if ndirs(a) == 0}
    thin  = {a: ndirs(a) for a in subs_live
             if unit == "armsuffix" and 0 < ndirs(a) < full and ndirs(a) < 20}
    check(tree, 1, not short, f"substrate present ({short or 'all present'}"
          f"{'; partial coverage (by design for probe substrate): ' + str(thin) if thin else ''})")

    # ---- INTERLOCK 2: no KEPT symlink may resolve into a releasing dir
    #      (a MATERIALISE target is exempt only because step MATERIALISE runs
    #       first; INTERLOCK 12 is what makes that exemption honest)
    dangle, dangle_mat = [], []
    for d in KEEP:
        for cur, sub, files in os.walk(os.path.join(WORK, d)):
            for e in files + sub:
                fp = os.path.join(cur, e)
                if os.path.islink(fp) and owner_of(fp) in relset:
                    o = owner_of(fp)
                    (dangle_mat if o in MATERIALISE else dangle).append(
                        f"{d}: {os.path.relpath(fp, WORK)} -> {o}")
            if len(dangle) > 5: break
    check(tree, 2, not dangle, f"no kept symlink resolves into a releasing dir "
          f"({len(dangle)} would dangle{'; e.g. ' + dangle[0] if dangle else ''}"
          f"{f'; {len(dangle_mat)} covered by step MATERIALISE' if dangle_mat else ''})")

    # ---- INTERLOCK 3: live-WRITER guard (mtime double-sample + scoped ps)
    def snap(dirs):
        out = {}
        for d in dirs:
            acc = []
            for cur, sub, files in os.walk(os.path.join(WORK, d)):
                for f in files:
                    try: acc.append(os.path.getmtime(os.path.join(cur, f)))
                    except OSError: pass
                if len(acc) > 3000: break
            out[d] = (len(acc), max(acc) if acc else 0)
        return out
    rel    = tier1 + tier2 + tier3 + tier4
    sample = rel[::max(1, len(rel)//120)] if rel else []
    before = snap(sample)
    ps  = subprocess.run(["ps","-eo","cmd"], capture_output=True, text=True).stdout
    busy = [l for l in ps.splitlines()
            if re.search(r"wire-cell|run_pr_evt|run_clus_evt|run_img_evt|wcsonnet", l)
            and cfg["root"] in l and f"plan_{STAMP}" not in l and "grep" not in l]
    time.sleep(12)
    moved = [d for d in sample if before[d] != snap([d])[d]]
    check(tree, 3, not moved and not busy,
          f"no live writer ({len(moved)} of {len(sample)} sampled dirs moved, "
          f"{len(busy)} tree-scoped wire-cell procs)")

    # ---- INTERLOCK 4: pre-existing broken symlinks recorded BEFORE the round
    pre = subprocess.run(["find", cfg["root"], "-xtype", "l"],
                         capture_output=True, text=True).stdout.split()
    check(tree, 4, True, f"pre-existing broken symlinks recorded: {len(pre)} "
                         f"(the post-state number only means something against this)")

    # ---- INTERLOCK 5: PROTECTED.txt names nothing in TIER 1
    hit = sorted({d for d in tier1 if d in PROT or universe[d] in PROT})
    check(tree, 5, not hit, f"PROTECTED.txt clear of tier 1 ({hit or 'clear'})")

    # ---- INTERLOCK 6: cross-repo, token-boundary citation resolution
    still = [d for d in tier1 if cited(d)]
    check(tree, 6, not still,
          f"{len(CITED)} cited dirs pulled from tier 1 and KEPT; "
          f"{len(still)} cited dirs remain in it (must be 0)")

    # ---- INTERLOCK 7: nothing being released is a record/label dir
    RECORD = ("labels","decisions","ql_labels","stm_scan_labels","stm_michel_labels",
              "snap","sweep","em_labels","vertex_labels","scan_labels","state-","archive")
    bad = [d for d in rel if any(k in d for k in RECORD)]
    check(tree, 7, not bad, f"no record/label dir in the release ({bad or 'clear'})")

    # ---- INTERLOCK 8: never delete THROUGH a symlink
    thru = [d for d in rel if os.path.islink(os.path.join(WORK, d))]
    check(tree, 8, not thru, f"no target is itself a symlink ({thru or 'clear'})")

    # ---- INTERLOCK 9: no arm a LIVE manifest still RESOLVES into
    man = set()
    for pat in ("em_display/*.tsv","em_display/*.txt","*/manifest*.tsv","docs/scan/*.tsv",
                "*_scan/*.tsv","*_labels/*.json","*_labels/*/*.json"):
        for f in glob.glob(os.path.join(cfg["root"], pat)):
            try: t = open(f, errors="ignore").read()
            except OSError: continue
            for mm in re.finditer(r"work-[A-Za-z0-9_.-]+|[0-9]{6}_[0-9]+_[A-Za-z0-9-]+", t):
                man.add(mm.group(0))
    resolved = {a for a in man if os.path.isdir(os.path.join(WORK, a))}
    inrel    = sorted(resolved & relset)
    check(tree, 9, not inrel, f"manifests name {len(man)} arms, {len(resolved)} exist, "
          f"{len(inrel)} in the release ({inrel or 'none'})")

    # ---- INTERLOCK 10: every tier family EXISTS and carries a ground
    def resolves(n): return any(d == n or universe[d] == n for d in universe)
    allt, missing, executed = {}, [], []
    for tname, fams in (("tier2", cfg["tier2"]), ("tier3", cfg.get("tier3", {})),
                        ("tier4", cfg.get("tier4", {}))):
        allt.update(fams)
        if not fams: continue
        gone = [n for n in fams if not resolves(n)]
        if len(gone) == len(fams): executed.append(f"{tname} already executed")
        else: missing += gone
    def grounded(n, seen=()):
        g = allt.get(n, "")
        m = re.match(r"^as\s+([A-Za-z0-9_-]+)\b", g.strip())
        if m and m.group(1) not in seen and m.group(1) in allt:
            return grounded(m.group(1), seen + (n,))
        return len(g) >= 40
    noground = sorted(n for n in allt if not grounded(n))
    check(tree, 10, not missing and not noground,
          f"t2 {len(tier2_names)}f/{len(tier2)}d, t3 {len(tier3_names)}f/{len(tier3)}d, "
          f"t4 {len(tier4_names)}f/{len(tier4)}d; "
          f"missing={missing or 'none'} ungrounded={noground or 'none'}"
          f"{'; ' + ', '.join(executed) if executed else ''}")

    # ---- INTERLOCK 11: the production and substrate sets must RESOLVE
    unres = sorted(n for n in cfg["substrate"] + cfg["production"]
                   if not any(d == n or universe[d] == n for d in universe))
    check(tree, 11, not unres, f"every substrate/production name resolves ({unres or 'all resolve'})")

    # ---- INTERLOCK 12 (NEW): a MATERIALISE exemption must be PRICED, and the
    # driver must implement it.  The closure exemption above is the only way a
    # still-borrowed dir can reach a tier, so if the copy step were missing or
    # unbudgeted the round would silently break a PROTECTED arm.  Assert: every
    # exempted name is in a tier, the driver names it, and the copy cost is
    # measured rather than assumed.
    if MATERIALISE:
        rel_all = set(tier1) | set(tier2) | set(tier3) | set(tier4)
        notrel  = sorted(n for n in MATERIALISE if n not in rel_all)
        drv     = os.path.join(HERE, f"retire_{STAMP}.sh")
        drvtxt  = open(drv).read() if os.path.exists(drv) else ""
        has     = "MATERIALISE" in drvtxt and all(n in drvtxt or "grp0825" in drvtxt
                                                  for n in MATERIALISE)
        # price it: distinct target dirs the SURVIVORS still pin
        tgt = set()
        for d in KEEP:
            for cur, sub, files in os.walk(os.path.join(WORK, d)):
                for e in files + sub:
                    fp = os.path.join(cur, e)
                    if os.path.islink(fp) and owner_of(fp) in MATERIALISE:
                        full = os.path.normpath(os.path.join(cur, os.readlink(fp)))
                        parts = full.split(os.sep)
                        for i, p in enumerate(parts):
                            if p in MATERIALISE:
                                tgt.add(os.sep.join(parts[:i+2])); break
        tgt = {t for t in tgt if os.path.exists(t)}
        kb = 0
        for i in range(0, len(tgt), 300):
            r = subprocess.run(["du","-sk"] + sorted(tgt)[i:i+300],
                               capture_output=True, text=True).stdout
            for l in r.splitlines():
                kb += int(l.split("\t")[0])
        check(tree, 12, not notrel and has and drvtxt,
              f"MATERIALISE {sorted(MATERIALISE)}: {len(tgt)} target dirs = "
              f"{kb/1048576:.3f} GiB to copy; driver implements it: {bool(has and drvtxt)}"
              f"{'; NOT IN ANY TIER: ' + str(notrel) if notrel else ''}")

    # ------------------------------------------------------------- report --
    sz = du_kb([os.path.join(WORK, d) for d in tier1 + tier2 + tier3 + tier4 + KEEP])
    t1kb = sum(sz.get(d, 0) for d in tier1); t2kb = sum(sz.get(d, 0) for d in tier2)
    t3kb = sum(sz.get(d, 0) for d in tier3); t4kb = sum(sz.get(d, 0) for d in tier4)
    print(f"\n  universe {len(universe)} dirs | KEEP {len(KEEP)}"
          f" | TIER 1 {len(tier1)} = {t1kb/1048576:.2f} GiB"
          f" | TIER 2 {len(tier2)} = {t2kb/1048576:.2f} GiB"
          f" | TIER 3 {len(tier3)} = {t3kb/1048576:.2f} GiB"
          f" | TIER 4 {len(tier4)} = {t4kb/1048576:.2f} GiB"
          f" | out-of-scope (untouched) {len(out_scope)}")
    for label, dirs in (("TIER 1", tier1), ("TIER 2", tier2), ("TIER 3", tier3), ("TIER 4", tier4)):
        byarm = collections.Counter()
        for d in dirs: byarm[universe[d]] += sz.get(d, 0)
        if not byarm: continue
        print(f"  --- {label} ---   {'arm':<24}{'dirs':>6}{'GiB':>9}{'cited':>7}")
        for a, kb in byarm.most_common(40):
            n = sum(1 for d in dirs if universe[d] == a)
            print(f"                    {a:<24}{n:>6}{kb/1048576:>9.2f}{CIT.get(a,0):>7}")
    for tier, dirs, kb in (("1", tier1, t1kb), ("2", tier2, t2kb), ("3", tier3, t3kb), ("4", tier4, t4kb)):
        tf = os.path.join(HERE, f"tier{tier}_{tree}_{STAMP}.txt")
        with open(tf, "w") as fh:
            for d in dirs: fh.write(os.path.join(WORK, d) + "\n")
        print(f"  tier {tier} file: {tf}  ({len(dirs)} lines, {kb/1048576:.2f} GiB)")
    return t1kb, t2kb, t3kb, t4kb

# grp0825 is released while two PROTECTED arms still borrow from it; the driver
# copies the 119 dirs they pin (0.608 GiB) in first.  Declared here, next to the
# tier that needs it, so INTERLOCK 12 can price and check it.
TREES["sbnd"]["materialise"] = ["work-mcp1k-grp0825","work-mcp2k-grp0825",
                                "work-ncpi0-grp0825","work-nuecc48-grp0825"]

if __name__ == "__main__":
    want = [a for a in sys.argv[1:] if a in TREES] or list(TREES)
    g1 = g2 = g3 = g4 = 0
    for t in want:
        a, b, c, d4 = plan_tree(t, TREES[t]); g1 += a; g2 += b; g3 += c; g4 += d4
    print(f"\n{'='*78}\nGRAND TOTAL  tier 1 {g1/1048576:.2f}   tier 2 {g2/1048576:.2f}   "
          f"tier 3 {g3/1048576:.2f}   tier 4 {g4/1048576:.2f} GiB   "
          f"all {(g1+g2+g3+g4)/1048576:.2f} GiB")
    print(f"interlock failures: {fails or 'NONE'}")
    print("\nThis script retired nothing.  Review the tier files, then the owner "
          "runs the retire driver (CONFIRM=yes).")
    sys.exit(1 if fails else 0)
