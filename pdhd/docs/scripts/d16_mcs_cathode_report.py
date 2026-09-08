#!/usr/bin/env python3
"""doc pdhd/16 sec 9 -- read the xcut sweep and print every number sec 9 quotes.

Input: the TSV written by d16_mcs_cathode_sweep (one row per muon per xcut).

Strata are formed on the CLOUD, not on the endpoints, because a muon can graze
the cathode without either end being near it:
  A  never reaches |x| < 5 cm  -- the excision is provably inert here; the
                                 engine's angle mask stays empty and the answer
                                 is bit-identical to xcut = 0 (MuonMCS.cxx:1181)
  B  reaches the band, no sign change (grazes / stops near the cathode)
  C  sign change (a true cathode crosser)

Usage: d16_mcs_cathode_report.py pdvd.sweep.tsv pdhd.sweep.tsv
"""
import csv
import sys

import numpy as np

BAND = 5.0     # the shipped mcs_cathode_xcut, used only to define stratum A
AMB = 0.2      # doc 84 R3.5's quantitative-use cut


def load(path):
    rows = list(csv.DictReader(open(path), delimiter='\t'))
    for r in rows:
        for k in ('len', 'ke_range', 'ke_mcs_ref', 'xcut', 'ke_mcs', 'amb',
                  'tracklen', 'minabsx'):
            r[k] = float(r[k])
        for k in ('cid', 'is_stm', 'nsegs_ref', 'nsegs', 'bad_path',
                  'cath_segs', 'cath_angles', 'crosses'):
            r[k] = int(r[k])
    return rows


def stratum(r):
    if r['minabsx'] >= BAND:
        return 'A never reaches |x|<5'
    return 'C crosser' if r['crosses'] else 'B grazes, no crossing'


def med(v):
    return float(np.median(v)) if len(v) else float('nan')


def report(path):
    rows = [r for r in load(path) if r['is_stm'] == 1]
    det = rows[0]['det']
    xcuts = sorted({r['xcut'] for r in rows})
    by = {}
    for r in rows:
        by.setdefault((r['tag'], r['cid']), {})[r['xcut']] = r
    muons = list(by.values())
    print('\n' + '=' * 78)
    print('%s  --  %d is_stm muons with muon_len >= 40 cm' % (det, len(muons)))
    print('=' * 78)

    # ---- exposure ------------------------------------------------------
    print('\n-- exposure (stratum on the cloud, band = %.0f cm) --' % BAND)
    for s in ('A never reaches |x|<5', 'B grazes, no crossing', 'C crosser'):
        n = sum(1 for m in muons if stratum(m[BAND]) == s)
        print('   %-24s n=%4d  (%5.1f %%)' % (s, n, 100.0 * n / len(muons)))

    # ---- the negative control: what does the band actually change? -----
    print('\n-- negative control: xcut = 0 (off) vs the shipped 5 cm --')
    movers = [m for m in muons if m[0.0]['ke_mcs'] != m[BAND]['ke_mcs']]
    print('   muons whose ke_MCS moves at all : %d of %d' % (len(movers), len(muons)))
    fired = [m for m in muons if m[BAND]['cath_segs'] > 0]
    print('   muons where the band fires      : %d  (segs dropped / angles masked'
          ' median %d / %d)' % (len(fired),
                                med([m[BAND]['cath_segs'] for m in fired]) if fired else 0,
                                med([m[BAND]['cath_angles'] for m in fired]) if fired else 0))
    inert = [m for m in muons if stratum(m[BAND]) == 'A never reaches |x|<5']
    nbit = sum(1 for m in inert if m[0.0]['ke_mcs'] == m[BAND]['ke_mcs'])
    print('   stratum A bit-identical to off  : %d of %d' % (nbit, len(inert)))
    if movers:
        r0 = [m[0.0]['ke_mcs'] / m[0.0]['ke_range'] for m in movers
              if m[0.0]['ke_mcs'] > 0 and 0 <= m[0.0]['amb'] < AMB]
        r5 = [m[BAND]['ke_mcs'] / m[BAND]['ke_range'] for m in movers
              if m[BAND]['ke_mcs'] > 0 and 0 <= m[BAND]['amb'] < AMB]
        print('   movers, ke_MCS/ke_range at amb<%.1f : off %.3f (n=%d) -> on %.3f (n=%d)'
              % (AMB, med(r0), len(r0), med(r5), len(r5)))

    # ---- the sweep -----------------------------------------------------
    print('\n-- sweep: cost and effect vs band half-width --')
    print('   %6s %8s %8s %9s %9s %9s %9s' % (
        'xcut', 'computed', 'amb<0.2', 'ratioALL', 'ratioA', 'ratioBC', 'segsdrop'))
    for xc in xcuts:
        sub = [m[xc] for m in muons]
        comp = [r for r in sub if r['ke_mcs'] > 0]
        good = [r for r in comp if 0 <= r['amb'] < AMB and r['ke_range'] > 0]
        gA = [r['ke_mcs'] / r['ke_range'] for r in good
              if stratum(by[(r['tag'], r['cid'])][BAND]) == 'A never reaches |x|<5']
        gBC = [r['ke_mcs'] / r['ke_range'] for r in good
               if stratum(by[(r['tag'], r['cid'])][BAND]) != 'A never reaches |x|<5']
        gall = [r['ke_mcs'] / r['ke_range'] for r in good]
        print('   %6.1f %7.1f%% %7.1f%% %9.3f %9.3f %9s %9d' % (
            xc, 100.0 * len(comp) / len(sub), 100.0 * len(good) / len(sub),
            med(gall), med(gA),
            ('%.3f (n=%d)' % (med(gBC), len(gBC))) if gBC else '   --',
            sum(r['cath_segs'] for r in sub)))

    # ---- geometry that prices any future widening ----------------------
    dxl = [abs(m[BAND]['tracklen']) for m in muons]
    print('\n   (cost scale: median trimmed path %.1f cm; a 14 cm segment is'
          ' the excision quantum)' % med(dxl))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        report(p)
