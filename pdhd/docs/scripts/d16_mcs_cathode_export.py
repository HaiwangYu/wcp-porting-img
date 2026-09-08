#!/usr/bin/env python3
"""doc pdhd/16 sec 9 -- export every STM muon's MCS INPUT from an arm on disk.

The point of this script is that no new arm is needed to re-run the MCS engine
at a different cathode band.  `CheckSTM_Michel::fill_mcs` hands the engine
`prof.pts` (CheckSTM_Michel.cxx:847-850) and `add_points(..., role=1, &prof)`
persists that SAME vector, in the same order, in cm
(CheckSTM_Michel.cxx:808-812 + :961-969).  So the role-1 rows of
T_stm_michel_pts ARE the engine's input cloud, and entry_*/stop_* are the two
vertices.  Everything the engine needs is already on disk.

Emitted alongside each cloud are the arm's OWN persisted muon_ke_mcs /
muon_mcs_amb / muon_mcs_nsegs, so the replay can be gated against the binary
that produced them before any swept number is believed.

Text, not JSON, on purpose: `strtod` parses Python's float repr exactly (repr
is the shortest round-tripping form), so the cloud crosses the language
boundary bit-for-bit with no library on either side.

Usage:
  d16_mcs_cathode_export.py PDVD 'pdvd/work/*_d16vnu' > pdvd.mcsin
  d16_mcs_cathode_export.py PDHD 'pdhd/work/*_d16hnu' > pdhd.mcsin
"""
import glob
import os
import sys

import numpy as np
import uproot

# CheckSTM_Michel.cxx:844-846 -- the gates fill_mcs applies before it calls the
# engine.  mcs_min_len_cm rides the C++ 40 on both drivers.
MIN_LEN_CM = 40.0
ROLE_MUON = 1

SCALARS = ['cluster_id', 'is_stm', 'muon_len', 'muon_ke_range', 'muon_ke_dqdx',
           'muon_ke_mcs', 'muon_mcs_amb', 'muon_mcs_nsegs', 'muon_mcs_bad_path',
           'muon_mcs_tracklen', 'entry_x', 'entry_y', 'entry_z',
           'stop_x', 'stop_y', 'stop_z']


def emit(det, pattern, out):
    nmuon = 0
    for d in sorted(glob.glob(pattern)):
        path = os.path.join(d, 'tracking-pr.root')
        if not os.path.exists(path):
            continue
        f = uproot.open(path)
        if 'T_stm_michel;1' not in f.keys():
            continue
        m = f['T_stm_michel'].arrays(SCALARS, library='np')
        p = f['T_stm_michel_pts'].arrays(['cluster_id', 'role', 'x', 'y', 'z'],
                                         library='np')
        sel = p['role'] == ROLE_MUON
        pc = p['cluster_id'][sel]
        px, py, pz = p['x'][sel], p['y'][sel], p['z'][sel]
        tag = os.path.basename(d)
        for i in range(len(m['cluster_id'])):
            cid = int(m['cluster_id'][i])
            if m['muon_len'][i] < MIN_LEN_CM:      # fill_mcs gate 1
                continue
            k = pc == cid
            n = int(k.sum())
            if n < 2:                              # fill_mcs gate 2
                continue
            out.write('MUON %s %s %d %d %.17g %.17g %.17g %.17g %d %d %.17g\n' % (
                det, tag, cid, int(m['is_stm'][i]),
                m['muon_len'][i], m['muon_ke_range'][i], m['muon_ke_mcs'][i],
                m['muon_mcs_amb'][i], int(m['muon_mcs_nsegs'][i]),
                int(m['muon_mcs_bad_path'][i]), m['muon_mcs_tracklen'][i]))
            out.write('VTX %r %r %r %r %r %r\n' % (
                float(m['entry_x'][i]), float(m['entry_y'][i]), float(m['entry_z'][i]),
                float(m['stop_x'][i]), float(m['stop_y'][i]), float(m['stop_z'][i])))
            out.write('PTS %d\n' % n)
            xs, ys, zs = px[k], py[k], pz[k]
            for j in range(n):
                out.write('%r %r %r\n' % (float(xs[j]), float(ys[j]), float(zs[j])))
            nmuon += 1
    sys.stderr.write('%s: %d muons exported from %s\n' % (det, nmuon, pattern))
    return nmuon


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    emit(sys.argv[1], sys.argv[2], sys.stdout)
