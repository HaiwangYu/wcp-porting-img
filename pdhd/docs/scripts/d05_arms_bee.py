#!/usr/bin/env python3
"""doc pdhd/05 sec 8 -- build a FULL-LAYER Bee set for a few events of one arm.

This is the opposite of `d04_movers_scan.py`, deliberately.  That script built a
BLIND set (clustering + dead area only) because the scan it fed was testing the
tagger's answer.  That scan is over (doc pdhd/04 sec 11.7).  What is left is a
diagnostic -- *why* did two stopping muons lose their STM tag -- and for that you
need exactly the layers the blind set withheld: `stm`, `stm_fit`, `stm_tagged`,
`steiner_graph`, `steiner_terminals`.  So this script keeps every layer.

One set per ARM, not one set with both arms interleaved: two slots that both say
"event 1" are indistinguishable inside Bee, so the arm has to be in the URL.

Usage:
  d05_arms_bee.py --dirs work/029107_1_d05mON work/029107_12_d05mON \\
                  --out pdhd/bee-pr-run029107-d05lostON [--highlight 1:113,12:108]
"""
import os, re, json, zipfile, argparse, collections

RE_EVT = re.compile(r'_(\d+)_[^/]*$')


def evtnum(d):
    m = RE_EVT.search(d.rstrip('/'))
    if not m:
        raise SystemExit("cannot read an event number out of %r" % d)
    return int(m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', nargs='+', required=True, help='per-event work dirs of ONE arm')
    ap.add_argument('--out', required=True, help='output prefix (writes <p>.zip, <p>.index.txt)')
    ap.add_argument('--highlight', default='',
                    help='comma-separated evt:cluster to duplicate into a "scan" layer')
    a = ap.parse_args()

    hi = collections.defaultdict(set)
    for tok in filter(None, a.highlight.split(',')):
        e, c = tok.split(':')
        hi[int(e)].add(int(c))

    dirs = sorted(a.dirs, key=evtnum)
    stage, index = {}, []
    for idx, d in enumerate(dirs):
        e = evtnum(d)
        zp = os.path.join(d, 'mabc-pr.zip')
        layers, npts = [], {}
        with zipfile.ZipFile(zp) as zf:
            for n in sorted(zf.namelist()):
                base = os.path.basename(n)
                if not base.endswith('.json'):
                    continue
                suffix = base.split('-', 1)[1]
                stage['data/%d/%d-%s' % (idx, idx, suffix)] = zf.read(n)
                layers.append(suffix.rsplit('-global.json', 1)[0].rsplit('.json', 1)[0])
                if suffix != 'clustering-global.json' or not hi[e]:
                    continue
                j = json.loads(zf.read(n))
                cid = j['cluster_id']
                cnt = collections.Counter(cid)
                sel = [i for i, c in enumerate(cid) if c in hi[e]]
                scan = {k: v for k, v in j.items() if not isinstance(v, list)}
                scan['type'] = 'scan'
                for k, v in j.items():
                    if isinstance(v, list) and len(v) == len(cid):
                        scan[k] = [v[i] for i in sel]
                stage['data/%d/%d-scan-global.json' % (idx, idx)] = json.dumps(scan).encode()
                layers.append('scan')
                npts = {c: cnt.get(c, 0) for c in sorted(hi[e])}
        index.append((idx, e, os.path.basename(d.rstrip('/')), sorted(set(layers)), npts))

    outzip = a.out + '.zip'
    with zipfile.ZipFile(outzip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(stage):
            zf.writestr(name, stage[name])

    with open(a.out + '.index.txt', 'w') as fh:
        fh.write("# bee_idx -> event.  FULL-LAYER set (doc pdhd/05 sec 9): the tagger layers\n")
        fh.write("# ARE included -- this is a diagnostic, not a blind scan.\n")
        for idx, e, d, layers, npts in index:
            # the run comes from the work dir, not a literal: this script was
            # written for 029107 and doc pdhd/11 runs it on 028084, where a
            # hard-coded run number silently mislabels the record.
            run = os.path.basename(d.rstrip("/")).split("_")[0]
            fh.write("%d\t%s evt %d\t%s\t%s%s\n"
                     % (idx, run, e, d, ",".join(layers),
                        ("\thighlighted: " + ", ".join("cl %d (%d pts)" % (c, n)
                                                       for c, n in npts.items())) if npts else ""))
    print("%s  (%d event slots, %.1f MB)" % (outzip, len(dirs), os.path.getsize(outzip) / 1e6))
    for idx, e, d, layers, npts in index:
        print("  %d  evt %-3d %-24s %s%s" % (idx, e, d, ",".join(layers),
              ("   highlight " + ",".join("cl%d/%dpts" % (c, n) for c, n in npts.items()))
              if npts else ""))


if __name__ == '__main__':
    main()
