#!/usr/bin/env python3
"""doc pdhd/10 sec 2 -- the stage ladder, sampled at the fitted trajectory's own
(collection wire, time) cells, per APA.

Same muons, four stages, all read from files already on disk:

  pre-NF ADC   input_data_*/run<R>/evt_<E>/protodunehd-orig-frames-anode<N>.tar.bz2
  post-NF ADC  frame_raw<N>   inside the SP archive
  SP gauss     frame_gauss<N> inside the SP archive
  ctpc cell    T_proj_data    inside tracking-stm.root

The pre-NF frame is on the 512 ns raw clock (5859 ticks) and everything after is
on the resampled 500 ns clock (5999 ticks), so the pre-NF window is scaled by
500/512.  ADC stages are judged against each channel's own 4.5-sigma-clipped
noise RMS (the WCT Derivations::CalcRMS recipe), so a noisier APA is not
penalised: the question is "is there signal on this wire at this time", not
"how many ADC".
"""
import argparse, io, os, sys, tarfile
import numpy as np
import uproot

BASE = (0, 3200, 6400); PER = (800, 800, 960)
W_RAW_BASE = (1600, 4160, 6720, 9280)
NTPS = 4                      # ticks per imaging slice
RAW_OVER_SP = 500.0 / 512.0   # pre-NF clock / SP clock


def members(arch, prefix):
    with tarfile.open(arch, "r:bz2") as t:
        for m in t.getmembers():
            if m.name.startswith(prefix):
                return np.load(io.BytesIO(t.extractfile(m).read()))
    return None


def calc_rms(wf, nsig=4.5, niter=6):
    """WCT Derivations::CalcRMS -- iterated nsig clip about the mean."""
    x = wf.astype(np.float64)
    m, s = x.mean(), x.std()
    for _ in range(niter):
        k = np.abs(x - m) < nsig * s
        if k.sum() < 10:
            break
        nm, ns = x[k].mean(), x[k].std()
        if abs(ns - s) < 1e-6:
            m, s = nm, ns
            break
        m, s = nm, ns
    return m, max(s, 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events", nargs="+")
    ap.add_argument("--run", default="028084")
    ap.add_argument("--input-root", default="input_data_7p8_new_coh_grouping")
    ap.add_argument("--work", default="work")
    ap.add_argument("--stm-tag", default="_d30hpost")
    ap.add_argument("--sp-tag", default="_d09")
    ap.add_argument("--nsig", type=float, default=3.0)
    ap.add_argument("--q-thresh", type=float, default=1000.0)
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--out")
    args = ap.parse_args()

    tot = np.zeros((4, 6))
    for ev in args.events:
        idx = ev.split("_")[1]
        stm = os.path.join(args.work, ev + args.stm_tag, "tracking-stm.root")
        spd = os.path.join(args.work, ev + args.sp_tag)
        evd = os.path.join(args.input_root, "run" + args.run, "evt_" + idx)
        if not os.path.exists(stm):
            print("# no %s" % stm, file=sys.stderr); continue
        st = {}
        try:
            for a in range(4):
                sp = os.path.join(spd, "protodunehd-sp-dnnroi-frames-anode%d.tar.bz2" % a)
                og = os.path.join(evd, "protodunehd-orig-frames-anode%d.tar.bz2" % a)
                g = members(sp, "frame_gauss%d" % a)
                rw = members(sp, "frame_raw%d" % a)
                o = members(og, "frame_")
                st[a] = (o, rw, g)
        except Exception as e:
            print("# %s: %s" % (ev, e), file=sys.stderr); continue

        f = uproot.open(stm)
        r = f["T_rec_charge"].arrays(["pw", "pt", "ndf", "status"], library="np")
        pj = f["T_proj_data"].arrays(["cluster_id", "channel", "time_slice", "charge"],
                                     library="np")
        cid = list(pj["cluster_id"][0]) if len(pj["cluster_id"]) else []
        blocks = r["ndf"].astype(np.int64)
        rmscache = {}
        for b in np.unique(blocks):
            m = blocks == b
            if m.sum() < args.min_points or int(r["status"][m][0]) != 0:
                continue
            if int(b) not in cid:
                continue
            i = cid.index(int(b))
            ch = np.asarray(pj["channel"][0][i]); ts = np.asarray(pj["time_slice"][0][i])
            q = np.asarray(pj["charge"][0][i]); live = q > 0
            cells = set(zip(ch[live].tolist(), ts[live].tolist()))
            w = np.floor(r["pw"][m]).astype(np.int64)
            tt = np.rint(r["pt"][m]).astype(np.int64)
            rank = w - BASE[2]; apa = rank // PER[2]
            for a, rk, wi, ti in zip(apa, rank, w, tt):
                a = int(a)
                if a < 0 or a > 3:
                    continue
                row = W_RAW_BASE[a] + int(rk) % PER[2] - 2560 * a
                o, rw, g = st[a]
                t0 = int(ti) * NTPS
                if t0 < 0 or t0 + NTPS > g.shape[1]:
                    continue
                ro0 = int(round(t0 * RAW_OVER_SP))
                ro1 = max(ro0 + 1, int(round((t0 + NTPS) * RAW_OVER_SP)))
                if ro1 > o.shape[1]:
                    continue
                key = (a, row)
                if key not in rmscache:
                    rmscache[key] = (calc_rms(o[row]), calc_rms(rw[row]))
                (om, osd), (rm, rsd) = rmscache[key]
                pre = float(np.max(o[row, ro0:ro1]) - om)
                post = float(np.max(rw[row, t0:t0 + NTPS]) - rm)
                gq = float(np.clip(g[row, t0:t0 + NTPS], 0, None).sum())
                cq = any((int(wi), int(ti + d)) in cells for d in (-2, -1, 0, 1, 2))
                v = tot[a]
                v[0] += 1
                v[1] += pre > args.nsig * osd
                v[2] += post > args.nsig * rsd
                v[3] += gq > args.q_thresh
                v[4] += cq
                v[5] += (pre > args.nsig * osd) and not (gq > args.q_thresh)

    hdr = ("apa   npts   pre-NF   post-NF   SP-gauss   ctpc     preNF-yes/SP-no")
    print("nsig=%g q_thresh=%g" % (args.nsig, args.q_thresh))
    print(hdr)
    for a in range(4):
        n = tot[a][0]
        if not n:
            continue
        print("%3d %6d %8.3f %9.3f %10.3f %8.3f %15.3f"
              % (a, n, tot[a][1] / n, tot[a][2] / n, tot[a][3] / n, tot[a][4] / n,
                 tot[a][5] / n))
    if args.out:
        np.savetxt(args.out, tot, fmt="%.6g", delimiter="\t",
                   header="npts\tprenf\tpostnf\tgauss\tctpc\tprenf_not_gauss")
    return 0


if __name__ == "__main__":
    sys.exit(main())
