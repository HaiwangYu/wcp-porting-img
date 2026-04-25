#!/usr/bin/env python3
# Merge per-anode woodpecker-masked archives back into a combined dnnsp-tagged
# sp-frames.tar.bz2 matching the upstream format consumed by wct-sp-to-magnify.jsonnet
# / wct-img-all.jsonnet / clus.jsonnet.
#
# Starts from the original combined archive, then overwrites the rows for each
# masked anode's channels with the masked frame/summary values. Channels for
# anodes that were not selected keep their original (unmasked) values.
#
# Usage: merge_sel_archives.py <orig_archive> <out_archive> <evt_id> <masked1> [masked2 ...]

import io
import os
import sys
import tarfile

import numpy as np


def load_tar(path):
    out = {}
    with tarfile.open(path, "r:bz2") as tf:
        for m in tf.getmembers():
            if m.name.endswith(".npy"):
                out[m.name[:-4]] = np.load(io.BytesIO(tf.extractfile(m).read()))
    return out


def add_npy(tf, name, arr):
    buf = io.BytesIO()
    np.save(buf, arr)
    data = buf.getvalue()
    info = tarfile.TarInfo(name=name + ".npy")
    info.size = len(data)
    tf.addfile(info, io.BytesIO(data))


def main():
    if len(sys.argv) < 5:
        print("usage: merge_sel_archives.py <orig> <out> <evt_id> <masked1> [masked2 ...]",
              file=sys.stderr)
        sys.exit(2)

    orig_path = sys.argv[1]
    out_path  = sys.argv[2]
    evt_id    = int(sys.argv[3])
    masked    = sys.argv[4:]

    orig = load_tar(orig_path)
    frame    = orig[f"frame_dnnsp_{evt_id}"].copy()
    channels = orig[f"channels_dnnsp_{evt_id}"]
    tickinfo = orig[f"tickinfo_dnnsp_{evt_id}"]
    summary  = orig.get(f"summary_dnnsp_{evt_id}")
    if summary is not None:
        summary = summary.copy()
    chanmask = orig.get(f"chanmask_bad_{evt_id}")

    ch_to_row = {int(c): i for i, c in enumerate(channels)}

    for mpath in masked:
        m = load_tar(mpath)
        frame_keys = [k for k in m if k.startswith("frame_gauss")]
        if not frame_keys:
            print(f"warning: no frame_gauss* in {mpath}, skipping", file=sys.stderr)
            continue
        fk = frame_keys[0]
        aid = int(fk[len("frame_gauss"):].split("_")[0])
        m_frame = m[f"frame_gauss{aid}_{evt_id}"]
        m_chans = m[f"channels_gauss{aid}_{evt_id}"]
        for i, c in enumerate(m_chans):
            row = ch_to_row[int(c)]
            frame[row] = m_frame[i]
        if summary is not None:
            sk = f"summary_gauss{aid}_{evt_id}"
            if sk in m:
                m_sum = m[sk]
                for i, c in enumerate(m_chans):
                    row = ch_to_row[int(c)]
                    summary[row] = m_sum[i]
        print(f"merged anode {aid} from {os.path.basename(mpath)} ({len(m_chans)} channels)")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with tarfile.open(out_path, "w:bz2") as tf:
        add_npy(tf, f"frame_dnnsp_{evt_id}",    frame)
        add_npy(tf, f"channels_dnnsp_{evt_id}", channels)
        add_npy(tf, f"tickinfo_dnnsp_{evt_id}", tickinfo)
        if summary is not None:
            add_npy(tf, f"summary_dnnsp_{evt_id}", summary)
        if chanmask is not None:
            add_npy(tf, f"chanmask_bad_{evt_id}", chanmask)

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
