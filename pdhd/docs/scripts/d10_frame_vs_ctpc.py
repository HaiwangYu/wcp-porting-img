#!/usr/bin/env python3
"""doc pdhd/10 sec 2 -- the same fitted trajectory, sampled in the SP frame and
in the ctpc (T_proj_data), per APA.

Answers "is the missing charge missing in the SP output, or lost between SP and
the fitter?".  Both are read from files already on disk; nothing is re-run.

Mapping (verified against the compiled config and the wire file):
  global W channel  pw = 6400 + rank,  rank = pw-6400,  apa = rank//960
  raw LArSoft channel = [1600,4160,6720,9280][apa] + rank%960
  SP frame row        = raw - 2560*apa          (rows 1600..2559 are W)
  imaging-face W raw  = 2080-2559 / 4160-4639 / 7200-7679 / 9280-9759
  time slice s        <-> ticks [4s, 4s+4)      (nticks_per_slice = 4)
"""
import argparse, glob, io, os, sys, tarfile
import numpy as np
import uproot

BASE = (0, 3200, 6400)
PER = (800, 800, 960)
W_RAW_BASE = (1600, 4160, 6720, 9280)
NTICKS_PER_SLICE = 4


def load_frame(arch, tag):
    fr = ch = None
    with tarfile.open(arch, "r:bz2") as t:
        for m in t.getmembers():
            if m.name.startswith("frame_%s" % tag):
                fr = np.load(io.BytesIO(t.extractfile(m).read()))
            elif m.name.startswith("channels_%s" % tag):
                ch = np.load(io.BytesIO(t.extractfile(m).read()))
    return fr, ch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events", nargs="+", help="e.g. 028084_0")
    ap.add_argument("--work", default="work")
    ap.add_argument("--stm-tag", default="_d30hpost")
    ap.add_argument("--sp-tag", default="_d09")
    ap.add_argument("--frame-tag", default="gauss", choices=["gauss", "wiener", "raw"])
    ap.add_argument("--thresh", type=float, default=0.0,
                    help="charge threshold on the summed frame ticks of a slice")
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--out")
    args = ap.parse_args()

    tot = np.zeros((4, 5))
    for ev in args.events:
        stm = os.path.join(args.work, ev + args.stm_tag, "tracking-stm.root")
        spd = os.path.join(args.work, ev + args.sp_tag)
        if not os.path.exists(stm):
            print("# no stm %s" % stm, file=sys.stderr); continue
        frames = {}
        ok = True
        for a in range(4):
            arch = os.path.join(spd, "protodunehd-sp-dnnroi-frames-anode%d.tar.bz2" % a)
            if not os.path.exists(arch):
                ok = False; break
            fr, ch = load_frame(arch, "%s%d" % (args.frame_tag, a))
            frames[a] = (fr, ch)
        if not ok:
            print("# no sp frames for %s" % ev, file=sys.stderr); continue

        f = uproot.open(stm)
        r = f["T_rec_charge"].arrays(["pw", "pt", "ndf", "status"], library="np")
        pj = f["T_proj_data"].arrays(["cluster_id", "channel", "time_slice", "charge"],
                                     library="np")
        cid = list(pj["cluster_id"][0]) if len(pj["cluster_id"]) else []
        blocks = r["ndf"].astype(np.int64)
        for b in np.unique(blocks):
            m = blocks == b
            if m.sum() < args.min_points or int(r["status"][m][0]) != 0:
                continue
            if int(b) not in cid:
                continue
            i = cid.index(int(b))
            ch = np.asarray(pj["channel"][0][i]); ts = np.asarray(pj["time_slice"][0][i])
            q = np.asarray(pj["charge"][0][i])
            live = q > 0
            cells = set(zip(ch[live].tolist(), ts[live].tolist()))
            w = np.floor(r["pw"][m]).astype(np.int64)
            tt = np.rint(r["pt"][m]).astype(np.int64)
            rank = w - BASE[2]
            apa = rank // PER[2]
            raw = np.array([W_RAW_BASE[a] + (rk % PER[2]) if 0 <= a < 4 else -1
                            for a, rk in zip(apa, rank)])
            for a, rw, wi, ti in zip(apa, raw, w, tt):
                if a < 0 or a > 3 or rw < 0:
                    continue
                fr, chan = frames[int(a)]
                row = rw - 2560 * int(a)
                if row < 0 or row >= fr.shape[0]:
                    continue
                t0 = ti * NTICKS_PER_SLICE
                if t0 < 0 or t0 + NTICKS_PER_SLICE > fr.shape[1]:
                    continue
                fq = float(np.clip(fr[row, t0:t0 + NTICKS_PER_SLICE], 0, None).sum())
                cq = any((int(wi), int(ti + d)) in cells for d in (-2, -1, 0, 1, 2))
                g = tot[int(a)]
                g[0] += 1
                g[1] += (fq > args.thresh)          # SP frame has charge here
                g[2] += cq                          # ctpc has a cell here
                g[3] += (fq > args.thresh) and not cq   # SP yes, ctpc no  -> lost downstream
                g[4] += (not (fq > args.thresh)) and cq

    print("frame_tag=%s thresh=%g" % (args.frame_tag, args.thresh))
    print("apa   npts   SP-has-charge   ctpc-has-cell   SP-yes/ctpc-no   SP-no/ctpc-yes")
    for a in range(4):
        n = tot[a][0]
        if not n:
            continue
        print("%3d %7d %14.3f %15.3f %16.3f %16.3f"
              % (a, n, tot[a][1] / n, tot[a][2] / n, tot[a][3] / n, tot[a][4] / n))
    if args.out:
        np.savetxt(args.out, tot, fmt="%.6g", delimiter="\t",
                   header="npts\tsp_has\tctpc_has\tsp_only\tctpc_only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
