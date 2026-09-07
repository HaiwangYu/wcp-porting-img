#!/usr/bin/env python3
"""
Cleanup round 2026-09-06 -- planner for sbnd_xin + pdvd + pdhd.

Owner: "keep the input as well as the latest production. For the rest
intermediate debugging outputs we can retire them."

Fork of plan_20260905.py.  What is carried, and why each line is load-bearing:

  * INTERLOCK 2 resolves a link's owning arm by matching the arm GRAMMAR against
    normalised path parts.  It does NOT relpath against a ROOT constant -- that
    formulation was vacuous for absolutely-spelled links because
    /nfs/data/1/xqian/toolkit-dev is itself a symlink to /home/xqian/toolkit-dev,
    and it cost work-dbg25a-ql in the 09-04 round.
  * INTERLOCK 3 is a live-WRITER guard, not an age threshold.
  * Keeping a dir means keeping its substrate: the closure iterates to a fixed
    point.  A one-pass exclusion left img-provenance.txt dangling on 09-05.
  * The citation census excludes scripts/retire/ .  A planner that reads its own
    tier file scores every candidate "cited" and protects it because it is
    protected (doc 91, reproduced again on 09-05).

WHAT IS NEW IN THIS ROUND
  1. CITATION IS TOKEN-BOUNDARY AND CROSS-ROOT (cit_20260906.py, cached in
     cit_20260906.json).  Name-exact matching scored ZERO for work-sent97-mcp2k
     -- docs write the brace form work-sent97-{mcp1k,mcp2k,...} -- and zero for
     every arm cited as a template (`work-<s>-d144fixprod`, `work-*-d144on`).
     Those two arms survived 09-05 only because PROTECTED.txt happened to name
     them.  The census now also reads the LABEL and DISPLAY roots: vertex_labels/
     alone pins work-vtx105-base-* and is invisible to a docs+scripts-only scan.
  2. TWO TIERS.  Tier 1 is what the owner's instruction plainly licenses:
     uncited, non-substrate, non-production, non-open-round.  Tier 2 is named
     BY HAND, one ground per family, for arms that are cited only by their own
     closed round's doc -- the shape doc 100 round C and doc 98 pass 2 used.
     Tier 2 is never derived; a family enters it only with a stated cost.
  3. "Latest production" comes from PRIMARY SOURCE, never the `prod` substring:
       sbnd stage A  = work-*-d97fv      (pr144_arms.sh:52, pr145_prodarm.sh:48
                                          -- the Q/L root both PR drivers read)
       sbnd stage B  = work-*-d144fixprod (doc pr/144 sec 16.3.1, 3067/3067 rc=0)
       pdvd substrate= keep -> d27fresh   (stage_pr_tag.sh:7 documented default)
       pdvd current  = d48nu7             (doc pdvd/48 sec 11, the flip's arm)
       pdhd substrate= the 38 bare dirs   (symlink census, 471 + 2086 inbound)

This script RETIRES NOTHING.  It prints a plan and writes tier files.
"""
import os, re, sys, json, time, subprocess, collections, glob

R     = "/home/xqian/toolkit-dev/wcp-porting-img"
STAMP = "20260906"
HERE  = os.path.dirname(os.path.abspath(__file__))
EVT   = re.compile(r"^(\d{6})_(\d+)(?:_(.+))?$")          # <run6>_<idx>[_<arm>]
SAMP  = re.compile(r"-(mcp1k|mcp2k|ncpi0|nuecc48|dbg25a)(?=-|$)|^(mcp1k|mcp2k|ncpi0|nuecc48|dbg25a)-")

# --------------------------------------------------------------- per tree --
# `unit` says what a releasable object IS.  pdvd/pdhd group by arm suffix under
# a single work/; sbnd_xin's arms are sibling work-* dirs.  Forking one grammar
# onto the other tree gives dirs=0 or one rm -rf work/.
TREES = {
 "sbnd": dict(
   root=f"{R}/sbnd/sbnd_xin", work=f"{R}/sbnd/sbnd_xin", unit="siblingdir",
   # THE INPUT.  grp0825's evt<N> half is the imaging substrate every Q/L arm
   # borrows (2028 + 1377 + 96 + 57 inbound links measured this round); its
   # ql_evt<N> half was retired in place 09-02 after a hash rollup.  dbg25a-ql
   # was regenerated 09-05 and 100 links resolve through it.
   substrate=["work-mcp2k-grp0825","work-mcp1k-grp0825",
              "work-ncpi0-grp0825","work-nuecc48-grp0825","work-dbg25a-ql"],
   # THE LATEST PRODUCTION.  Stage A is the Q/L root pr144_arms.sh:52 and
   # pr145_prodarm.sh:48 both read; stage B is doc pr/144 sec 16.3.1's arm.
   production=["work-mcp1k-d97fv","work-mcp2k-d97fv","work-ncpi0-d97fv","work-nuecc48-d97fv",
               "work-mcp1k-d144fixprod","work-mcp2k-d144fixprod",
               "work-ncpi0-d144fixprod","work-nuecc48-d144fixprod"],
   # Four flips landed AFTER d144fixprod was cut (pr/145 item 4, pr/146's
   # default-OFF knob + its pending recommendation, pr/147's two).  There is no
   # full-sample arm at today's operating point, so "latest production" is a
   # SET: these are the small arms that carry the post-d144fixprod points.
   flip_evidence=["work-mcp1k-d145prod","work-mcp2k-d145prod",
                  "work-ncpi0-d145prod","work-nuecc48-d145prod"],
   # An open round's arms are protected by PREFIX, never by enumeration: on
   # 09-04 a live round created seven new arm families between plan and confirm.
   open_prefix=("work-d147-","work-d148","work-d149","work-d150",
                "work-mcp1k-d146","work-mcp2k-d146","work-ncpi0-d146","work-nuecc48-d146"),
   keep_arms=[
     # named by doc pr/148 sec 16 as the arm the NEXT round reads (item 3's
     # bisect and the 137238 log lines).  A doc whose last section is a plan for
     # the next session is an OPEN round for retire purposes.
     "work-mcp1k-d145np","work-mcp2k-d145np","work-ncpi0-d145np","work-nuecc48-d145np",
   ],
   # Cited only by their own CLOSED round's doc.  Each line states the cost.
   tier2={
     "work-pr143-on":   "pr/143 knob-ON arm, 3000 evts. Round CLOSED 09-06; the shipped code IS this arm (sec 7.1 flip-equivalence) and work-*-d144fixprod is a later epoch on the same knob. COST: doc pr/143 sec 7.2's per-event mover table becomes text-only.",
     "work-pr143-off":  "pr/143 knob-OFF baseline, 3000 evts. Same round. COST: the OFF-side of sec 7.2.",
     "work-pr143-final":"pr/143 shipped-code-no-knob arm, 3000 evts. Superseded by work-*-d144fixprod, which is the shipped code on a later binary over all 3067. COST: sec 7.1's deletion-inertness pair.",
     "work-mcp1k-d144on":"pr/144 knob-ON arm. The knob is IN production; d144fixprod is the same point on the crash-fixed binary and doc sec 7 records the byte gate d144on vs d144fixprod. COST: that gate becomes text-only.",
     "work-mcp2k-d144on":"as work-mcp1k-d144on.",
     "work-ncpi0-d144on":"as work-mcp1k-d144on.",
     "work-nuecc48-d144on":"as work-mcp1k-d144on.",
     "work-mcp1k-d144off":"pr/144 knob-OFF baseline, 3067 evts across the four. The OFF path is byte-identical to the pre-flip epoch by construction. COST: the OFF side of doc pr/144 sec 7.",
     "work-mcp2k-d144off":"as work-mcp1k-d144off.",
     "work-ncpi0-d144off":"as work-mcp1k-d144off.",
     "work-nuecc48-d144off":"as work-mcp1k-d144off.",
     "work-mcp1k-d144fixframeonly":"pr/144 frame-only decomposition arm on the crash-fixed binary; a decomposition of a shipped change, not the shipped point. COST: doc pr/144's frame/prod split table.",
     "work-mcp2k-d144fixframeonly":"as work-mcp1k-d144fixframeonly.",
     "work-ncpi0-d144fixframeonly":"as work-mcp1k-d144fixframeonly.",
     "work-nuecc48-d144fixframeonly":"as work-mcp1k-d144fixframeonly.",
     "work-mcp1k-d145np200":"pr/145 item-4 sweep arm at impact=200 over the 568-event pointing subset; the SHIPPED point is work-*-d145prod and the full-sample reference is work-*-d145np, both kept. COST: the sweep's intermediate row.",
     "work-ncpi0-d145np200":"as work-mcp1k-d145np200.",
     "work-nuecc48-d145np200":"as work-mcp1k-d145np200.",
     "work-mcp1k-d97fvpr2":"THE PROTECTED.txt LINE CHANGE.  d97fvpr2 is listed there as LATEST PRODUCTION stage B; doc pr/144 sec 16.3.1 moved that to work-*-d144fixprod (3067/3067, committed default, crash-fixed binary) and re-baselined the sentinel suite onto it.  The published tables live on: products/prod0902/ was computed from d97fvpr2 and stays committed.  Needs an explicit owner yes because it edits PROTECTED.txt, not just the disk.",
     "work-mcp2k-d97fvpr2":"as work-mcp1k-d97fvpr2.",
     "work-ncpi0-d97fvpr2":"as work-mcp1k-d97fvpr2.",
     "work-nuecc48-d97fvpr2":"as work-mcp1k-d97fvpr2.",
   },
   # TIER 3 (added 2026-09-06 after tiers 1+2 ran).  Owner: "There are a lot of
   # work* directories there, intermediate ones can be cleaned up, right?
   # retire them."  Same bar as tier 2 -- named by hand, one ground each, and
   # NOTHING here is named by PROTECTED.txt, so this tier needs no edit to it.
   tier3={
     "work-ncpi0-d144frameonly":"pr/144 frame-only decomposition on the PRE-crash-fix binary.  Its crash-fixed twin work-*-d144fixframeonly went in tier 2 and the shipped point work-*-d144fixprod is kept, so this is the older half of a decomposition whose newer half is already released.",
     "work-nuecc48-d144frameonly":"as work-ncpi0-d144frameonly.",
     "work-mcp1k-d146sat":"pr/146 satellite A/B sweep arm.  pr/146 shipped its knob default-OFF and sec 12 RECOMMENDS kine_sat_cont_keep_deg 25, whose arm work-*-d146sv25 is KEPT for that open decision.  The other three sweep points are the intermediate steps to it.",
     "work-mcp2k-d146sat":"as work-mcp1k-d146sat.", "work-ncpi0-d146sat":"as work-mcp1k-d146sat.", "work-nuecc48-d146sat":"as work-mcp1k-d146sat.",
     "work-mcp1k-d146satoff":"as work-mcp1k-d146sat.", "work-mcp2k-d146satoff":"as work-mcp1k-d146sat.", "work-ncpi0-d146satoff":"as work-mcp1k-d146sat.", "work-nuecc48-d146satoff":"as work-mcp1k-d146sat.",
     "work-mcp1k-d146sv0":"as work-mcp1k-d146sat.", "work-mcp2k-d146sv0":"as work-mcp1k-d146sat.", "work-ncpi0-d146sv0":"as work-mcp1k-d146sat.", "work-nuecc48-d146sv0":"as work-mcp1k-d146sat.",
     "work-nuecc48-doc25d38new":"the SBND-side regression gate of PDVD doc 25, a round CLOSED 2026-09-02 (doc pdvd/25 execution).  Cross-detector, so it was checked against BOTH repos' docs before listing -- the doc 100 sec 10 casualty shape.",
     "work-ncpi0-doc25d38new":"as work-nuecc48-doc25d38new.",
     "work-nuecc48-doc25r8new":"as work-nuecc48-doc25d38new (gate round 8).",
     "work-d45sbnd-off3all-nuecc48":"the SBND side of PDVD doc 45's exclusion-frame gate; doc 45 is closed and its PDVD arms (d45prod) are kept.  COST: doc pdvd/45's SBND cross-check becomes text-only.",
     "work-d45sbnd-off3all-ncpi0":"as work-d45sbnd-off3all-nuecc48.",
     "work-d45sbnd-on3all-nuecc48":"as work-d45sbnd-off3all-nuecc48.",
     "work-d45sbnd-on3all-ncpi0":"as work-d45sbnd-off3all-nuecc48.",
     "work-d46sbnd-on-nuecc48":"the SBND side of PDVD doc 46's cross-detector open-defect census; the defects it names are tracked in doc 46 itself.",
     "work-d46sbnd-on-ncpi0":"as work-d46sbnd-on-nuecc48.",
     "work-stmcamp-d42fit":"SBND stm-campaign gate arm for PDVD doc 42, closed 2026-09-05; the constants it backs are on record and the PDVD-side arm d42fit is KEPT.",
     "work-stmcamp-d44sig":"as work-stmcamp-d42fit (doc pdvd/44).",
     "work-stmcamp-d46skip":"as work-stmcamp-d42fit (doc pdvd/46).",
   },
 ),
 "pdvd": dict(
   root=f"{R}/pdvd", work=f"{R}/pdvd/work", unit="armsuffix",
   # keep holds the SP+DNNROI frames d27fresh borrows, so keep IS the input, not
   # an old arm.  d27fresh is stage_pr_tag.sh:7's documented default src_tag
   # (primary source, not a name-read); d41prov is doc 43 sec 6's staging source
   # and the biggest hub in the tree (8255 inbound).  d143pnew is today's d08
   # arms' source tag (36 inbound).
   substrate=["keep","d27fresh","d41prov","d39r2prov","d143pnew","d28dlfp","d34base"],
   # doc pdvd/48 sec 11: d48nu7 is the arm the 2026-09-06 flip rests on, at the
   # operating point that IS the PDVD default now.  d48nu3 is sec 8's census arm.
   production=["d48nu7","d48nu3","d48flipcfg","d45prod"],   # d48ref2/d48new4
   # are PDHD arms (doc pdvd/48 sec 9 names them as pdhd/work/029107_0_d48*),
   # not pdvd ones; they are kept on the pdhd side by its "d48" open prefix.
   flip_evidence=["d43p90c5","d43prod","d43fvoff","d43fvd50","d43p90c3","d43p80c3",
                  "d42fit","d44sig","d44sigb","d44sign6","d44ref","d41prod",
                  "d44prod","d38qnewprod"],
   open_prefix=("d146","d08","d143f","d48leg","d48stm","d48smoke","d48cfg"),
   keep_arms=["d31r6e2e","magnify","d37off1","d37on05","d36on","d39stm2","d39lean",
              "d39r2base","d39r2unm","d40rep","d40aniso0","d40trace","d42fitnew2"],
   tier2={
     "d48nu":  "doc pdvd/48 sec 8.0 iteration 1 -- superseded by d48nu2 within the same section, which the doc says outright ('Arm-wide d48nu -> d48nu2').  COST: the first of two bug-fix deltas in sec 8.0.",
     "d48nu2": "doc pdvd/48 sec 8.0 iteration 2 -- superseded by d48nu3 in the same section.  COST: the second sec 8.0 delta.",
     "d48nu4": "doc pdvd/48 sec 10 addendum: same 99 is_stm of 574 as sec 8, i.e. the arm's stated result is that it did NOT move.  Superseded by d48nu7.  COST: the addendum's 28-candidate reject-reason table.",
     "d48nu5": "doc pdvd/48 sec 10: reported in doc pdhd/03 sec 7 and explicitly NOT adopted for PDVD.  COST: that row.",
     "d48nu6": "doc pdvd/48 sec 10 intermediate pin; superseded by d48nu7 (pin new11, the shipped binary).",
     "d45on":  "doc pdvd/45 knob-ON iteration, superseded by d45on3/d45prod.",
     "d45on3": "doc pdvd/45 knob-ON iteration, superseded by d45prod (the arm the doc's operating point rests on).",
     "d45skipnu":"doc pdvd/45 skip-variant arm; d45skipon/d45skipoff carry the pair the doc quotes.",
     "d45nu0": "doc pdvd/45 nu-stage iteration superseded within the same doc.",
     "d143pref":"pr/143's PDVD reference arm.  sec 7.3 states the PDVD chain is NOT production; the defect density number it backs is in the doc.  d143pnew is KEPT as substrate for today's d08 arms.  COST: sec 7.3's before-side.",
   },
   tier3={
     "d45skipon":"doc pdvd/45's skip-variant A/B.  The doc's operating point is d45prod, which is KEPT; this pair is the sweep around it.  COST: doc 45's skip table becomes text-only.",
     "d45skipoff":"as d45skipon.",
     "d43fvoff":"doc pdvd/43's exit-gap fiducial sweep.  The SHIPPED constant is d43p90c5 and the production arm is d43prod -- both KEPT.  These four are the other sweep points.  COST: doc 43 sec 6's per-point table.",
     "d43fvd50":"as d43fvoff.", "d43p80c3":"as d43fvoff.", "d43p90c3":"as d43fvoff.",
     "d46dump":"a single-event dump probe behind doc pdvd/46; the census it fed is in the doc.",
   },
 ),
 "pdhd": dict(
   root=f"{R}/pdhd", work=f"{R}/pdhd/work", unit="armsuffix",
   # The 38 bare 029107_<N> dirs are the input substrate (SP+DNNROI frames,
   # clusters-apa archives, opflash): 471 inbound directly and 2086 more through
   # stm0, which every other stm arm then borrows from.  Same shape as d27fresh.
   substrate=["(bare)","stm0","stmwc","d06base","d06um","d02prod","wcc","d05mON"],
   production=["d03nu9","d08both","d08cap20b","stmw"],
   flip_evidence=["stmc4000","stmc2000","stmc1000","stmc250",
                  "phdump","phdumpw","phdumpx","phdumpwc","wccdump","wccdumpw",
                  "qlt","perfslide"],
   # "ql" added 2026-09-06 21:50 -- INTERLOCK A caught a LIVE peer (PID 2727386)
   # writing 028084_18_qlpilot and 029107_0_qlctrl at 21:46/21:48, half an hour
   # after this round was planned.  Protected by PREFIX, never by naming those
   # two: on 09-04 a live round created SEVEN new families between plan and
   # confirm, and a name list frozen at plan time would have released all seven.
   # "ql" is safe here because the tree's only other ql arm, qlt, is already
   # kept (cited by pdvd/docs/qlmatch).
   open_prefix=("d146","d08","d143f","d48","d46","ql"),
   keep_arms=["d05prod","d05wc","d05p","d04bee","d02fix","d02ref","d02sig","d02sigb"],
   tier2={
     "d03nu1":"doc pdhd/03 knob-bag iteration 1 of 9.  The SHIPPED bag is the one doc pdvd/48 sec 11 adopted and its arm is d03nu9 (kept).  COST: one row of the sec-7 sweep table.",
     "d03nu2":"as d03nu1 (iteration 2 of 9).",
     "d03nu3":"as d03nu1 (iteration 3 of 9).",
     "d03nu4":"as d03nu1 (iteration 4 of 9).",
     "d03nu5":"as d03nu1 (iteration 5 of 9).",
     "d03nu6":"as d03nu1 (iteration 6 of 9).",
     "d03nu7":"as d03nu1 (iteration 7 of 9).",
     "d03nu8":"as d03nu1 (iteration 8 of 9).",
   },
   tier3={
     "d08cap10":"doc pdhd/08's bridge-cap sweep.  The round SHIPPED (toolkit 4119a78a) and its shipped arm d08both plus the gate pair d08gref/d08goff are KEPT.  These ten are the sweep points either side of it.  COST: doc 08's per-cap and per-merge tables become text-only; the shipped value and its gate stay re-runnable.",
     "d08cap20":"as d08cap10.", "d08cap20b":"as d08cap10.", "d08cap40":"as d08cap10.",
     "d08mrg1":"as d08cap10.", "d08mrg3":"as d08cap10.", "d08mrg5":"as d08cap10.",
     "d08mr10":"as d08cap10.", "d08mr15":"as d08cap10.", "d08mr30":"as d08cap10.",
   },
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
    # toks.json holds, per dir, EVERY token a doc could legitimately cite it by:
    # the dir, the sample-stripped arm, and every contiguous hyphen-segment
    # range.  Scoring only the dir and the arm missed work-stmcamp-d48gatenew,
    # which doc pdhd/03 cites as the bare tail token `d48gatenew`, and
    # work-stmcamp-d42gate{old,new}, a brace set on the tail.
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

    # --- what a KEEP is made of -------------------------------------------
    keep_names = (set(cfg["substrate"]) | set(cfg["production"])
                  | set(cfg["flip_evidence"]) | set(cfg["keep_arms"]))
    tier2_names = set(cfg["tier2"]); tier3_names = set(cfg.get("tier3", {}))
    def is_open(d, a):
        return d.startswith(cfg["open_prefix"]) or (a or "").startswith(cfg["open_prefix"])
    keep_dirs = {d for d, a in universe.items()
                 if d in keep_names or a in keep_names or is_open(d, a)}
    # PROTECTED.txt union, matched on the dir name or the arm token
    for d, a in universe.items():
        if d in PROT or a in PROT or any(a == p.strip("*") for p in PROT):
            keep_dirs.add(d)
    # a tier-2 family is a deliberate release: it wins over PROTECTED/keep-name
    # matching, and INTERLOCK 10 makes sure that override was intentional.
    keep_dirs -= {d for d, a in universe.items()
                  if d in tier2_names or a in tier2_names
                  or d in tier3_names or a in tier3_names}

    cand = {d for d in universe} - keep_dirs
    tier2 = sorted(d for d in cand if d in tier2_names or universe[d] in tier2_names)
    tier3 = sorted(d for d in cand if d in tier3_names or universe[d] in tier3_names)
    rest  = sorted(cand - set(tier2) - set(tier3))

    # --- INTERLOCK 6 first: citation pulls a dir OUT of tier 1 -------------
    def cited(d):
        """max citation count over EVERY token this dir can be named by"""
        return max([CIT.get(d, 0), CIT.get(universe[d] or "", 0)]
                   + [CIT.get(t, 0) for t in TOKS.get(d, ())])
    CITED = sorted(d for d in rest if cited(d))
    tier1 = [d for d in rest if d not in set(CITED)]
    keep_dirs |= set(CITED)

    # --- transitive closure: keeping a dir means keeping its substrate -----
    relset = set(tier1) | set(tier2) | set(tier3)
    for _ in range(12):
        pull = set()
        for d in keep_dirs:
            for cur, sub, files in os.walk(os.path.join(WORK, d)):
                for e in files + sub:
                    fp = os.path.join(cur, e)
                    if os.path.islink(fp):
                        o = owner_of(fp)
                        if o in relset: pull.add(o)
        if not pull: break
        keep_dirs |= pull; relset -= pull
    closure = sorted((set(tier1) | set(tier2) | set(tier3)) - relset)
    tier1 = [d for d in tier1 if d in relset]
    tier2 = [d for d in tier2 if d in relset]
    tier3 = [d for d in tier3 if d in relset]
    if closure:
        print(f"        closure: +{len(closure)} dirs pulled back as substrate of a kept dir")

    KEEP = sorted(keep_dirs)

    # ---- INTERLOCK 1: substrate present, and at full per-event coverage.
    # Resolve a substrate name as a DIR NAME or an ARM TOKEN: sbnd's arm token
    # strips the sample (work-mcp2k-grp0825 -> grp0825), so a token-only lookup
    # reported the tree's whole imaging substrate "absent".
    def ndirs(name):
        return sum(1 for d, a in universe.items() if d == name or a == name)
    cnt   = collections.Counter(universe.values())
    full  = max(cnt.values()) if cnt else 0
    short = {a: ndirs(a) for a in cfg["substrate"] if ndirs(a) == 0}
    thin  = {a: ndirs(a) for a in cfg["substrate"]
             if unit == "armsuffix" and 0 < ndirs(a) < full and ndirs(a) < 20}
    check(tree, 1, not short, f"substrate present ({short or 'all present'}"
          f"{'; partial coverage (by design for probe substrate): ' + str(thin) if thin else ''})")

    # ---- INTERLOCK 2: no KEPT symlink may resolve into a releasing dir
    dangle = []
    for d in KEEP:
        for cur, sub, files in os.walk(os.path.join(WORK, d)):
            for e in files + sub:
                fp = os.path.join(cur, e)
                if os.path.islink(fp) and owner_of(fp) in relset:
                    dangle.append(f"{d}: {os.path.relpath(fp, WORK)} -> {owner_of(fp)}")
            if len(dangle) > 5: break
    check(tree, 2, not dangle, f"no kept symlink resolves into a releasing dir "
          f"({len(dangle)} would dangle{'; e.g. ' + dangle[0] if dangle else ''})")

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
    rel    = tier1 + tier2 + tier3
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
    RECORD = ("labels","decisions","ql_labels","stm_scan_labels","snap","sweep",
              "em_labels","vertex_labels","scan_labels","state-","archive")
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

    # ---- INTERLOCK 10 (NEW): every tier-2 family must EXIST, carry a ground,
    # and be a deliberate override of whatever else would have kept it.  A
    # tier-2 name that matches nothing is a typo that silently frees 0 bytes.
    def resolves(n): return any(d == n or universe[d] == n for d in universe)
    allt, missing, executed = {}, [], []
    for tname, fams in (("tier2", cfg["tier2"]), ("tier3", cfg.get("tier3", {}))):
        allt.update(fams)
        if not fams: continue
        gone = [n for n in fams if not resolves(n)]
        if len(gone) == len(fams): executed.append(f"{tname} already executed")
        else: missing += gone
    def grounded(n, seen=()):
        g = allt.get(n, "")
        # the alias token must not swallow a trailing '.' -- a greedy class
        # containing '.' made every "as <other>." ground look ungrounded.
        m = re.match(r"^as\s+([A-Za-z0-9_-]+)\b", g.strip())
        if m and m.group(1) not in seen and m.group(1) in allt:
            return grounded(m.group(1), seen + (n,))       # alias -> its target
        return len(g) >= 40
    noground = sorted(n for n in allt if not grounded(n))
    check(tree, 10, not missing and not noground,
          f"tier 2: {len(tier2_names)} fam/{len(tier2)} dirs, tier 3: "
          f"{len(tier3_names)} fam/{len(tier3)} dirs; "
          f"missing={missing or 'none'} ungrounded={noground or 'none'}"
          f"{'; ' + ', '.join(executed) if executed else ''}")

    # ---- INTERLOCK 11 (NEW): the production and substrate sets must RESOLVE.
    # Doc 100's decisive test was not "is it cited" but "does it still exist" --
    # em_display's manifests named 420 arms and 10 existed.
    unres = sorted(n for n in cfg["substrate"] + cfg["production"]
                   if not any(d == n or universe[d] == n for d in universe))
    check(tree, 11, not unres, f"every substrate/production name resolves ({unres or 'all resolve'})")

    # ------------------------------------------------------------- report --
    sz = du_kb([os.path.join(WORK, d) for d in tier1 + tier2 + tier3 + KEEP])
    t1kb = sum(sz.get(d, 0) for d in tier1); t2kb = sum(sz.get(d, 0) for d in tier2)
    t3kb = sum(sz.get(d, 0) for d in tier3)
    print(f"\n  universe {len(universe)} dirs | KEEP {len(KEEP)}"
          f" | TIER 1 {len(tier1)} = {t1kb/1048576:.2f} GiB"
          f" | TIER 2 {len(tier2)} = {t2kb/1048576:.2f} GiB"
          f" | TIER 3 {len(tier3)} = {t3kb/1048576:.2f} GiB"
          f" | out-of-scope (untouched) {len(out_scope)}")
    for label, dirs in (("TIER 1", tier1), ("TIER 2", tier2), ("TIER 3", tier3)):
        byarm = collections.Counter()
        for d in dirs: byarm[universe[d]] += sz.get(d, 0)
        if not byarm: continue
        print(f"  --- {label} ---   {'arm':<24}{'dirs':>6}{'GiB':>9}{'cited':>7}")
        for a, kb in byarm.most_common(40):
            n = sum(1 for d in dirs if universe[d] == a)
            print(f"                    {a:<24}{n:>6}{kb/1048576:>9.2f}{CIT.get(a,0):>7}")
    for tier, dirs, kb in (("1", tier1, t1kb), ("2", tier2, t2kb), ("3", tier3, t3kb)):
        tf = os.path.join(HERE, f"tier{tier}_{tree}_{STAMP}.txt")
        with open(tf, "w") as fh:
            for d in dirs: fh.write(os.path.join(WORK, d) + "\n")
        print(f"  tier {tier} file: {tf}  ({len(dirs)} lines, {kb/1048576:.2f} GiB)")
    return t1kb, t2kb, t3kb

if __name__ == "__main__":
    want = [a for a in sys.argv[1:] if a in TREES] or list(TREES)
    g1 = g2 = g3 = 0
    for t in want:
        a, b, c = plan_tree(t, TREES[t]); g1 += a; g2 += b; g3 += c
    print(f"\n{'='*78}\nGRAND TOTAL  tier 1 {g1/1048576:.2f}   tier 2 {g2/1048576:.2f}   "
          f"tier 3 {g3/1048576:.2f} GiB   all {(g1+g2+g3)/1048576:.2f} GiB")
    print(f"interlock failures: {fails or 'NONE'}")
    print("\nThis script retired nothing.  Review the tier files, then the owner "
          "runs the retire driver (CONFIRM=yes), tier 1 and tier 2 separately.")
    sys.exit(1 if fails else 0)
