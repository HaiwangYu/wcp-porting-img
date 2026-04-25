#!/usr/bin/env python
# Convert SBND imaging cluster npz files to Bee JSON and zip for upload.
#
# Usage: python wct-img-2-bee.py <run> <subrun> <event> <idx0>:<path0> [<idx1>:<path1> ...]
#   idx: anode index (0 = bottom drift, 1 = top drift)
#   path: path to icluster-apa<N>-active.npz

import sys
import os


def anode_args(idx):
    # SBND anode planes: APA0 at x=-201.45 cm, APA1 at x=+201.45 cm
    # (params.jsonnet uplane_right/uplane_left). Drift speed 1.563 mm/us
    # (simparams.jsonnet). t0 sign is flipped from clus.jsonnet's
    # time_offset=-200us because BlobSampler adds time_offset while
    # `wirecell-img bee-blobs` subtracts --t0.
    if idx == 0:
        return '--speed "-1.563*mm/us" --t0 "200*us" --x0 "-201.45*cm"'
    else:
        return '--speed "1.563*mm/us" --t0 "200*us" --x0 "201.45*cm"'


def main(run, subrun, event, pairs):
    if os.path.exists('data/0'):
        print('found old data, removing ...')
        os.system('rm -rf data')
    if os.path.exists('upload.zip'):
        os.system('rm -f upload.zip')
    os.system('mkdir -p data/0')

    rse = '--rse %s %s %s' % (run, subrun, event)
    for idx, fp in pairs:
        cmd = ('wirecell-img bee-blobs -g sbnd -s center %s %s'
               ' -o data/0/0-apa%d.json %s'
               % (rse, anode_args(idx), idx, fp))
        print(cmd)
        os.system(cmd)

    os.system('zip -r upload data')


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print('usage: python wct-img-2-bee.py <run> <subrun> <event> <idx0>:<path0> [<idx1>:<path1> ...]')
        sys.exit(1)
    run_arg, subrun_arg, event_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    pair_list = []
    for arg in sys.argv[4:]:
        idx_str, fp = arg.split(':', 1)
        pair_list.append((int(idx_str), fp))
    main(run_arg, subrun_arg, event_arg, pair_list)
