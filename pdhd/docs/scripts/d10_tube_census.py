#!/usr/bin/env python3
"""doc pdhd/10 sec 2 -- charge in a tube around the fitted trajectory, per APA,
measured in the SP gauss frame and in the ctpc (T_proj_data), normalised by the
trajectory's true 3-D path length.

The tube is the set of distinct (collection wire, imaging slice) cells within
+-HW wires of the trajectory's own wire at each fit point, de-duplicated, so a
track that lingers on one wire is not counted twice and the number is a genuine
charge-per-cm.

Gate built in: every ctpc W cell must be reproducible from the gauss frame at
the same (channel, tick) -- see --selftest.
"""
import argparse, glob, io, os, sys, tarfile
import numpy as np
import uproot

BASE = (0, 3200, 6400); PER = (800, 800, 960)
W_RAW_BASE = (1600, 4160, 6720, 9280)
NTPS = 4


def mem(arch, pref):
    with tarfile.open(arch, "r:bz2") as t:
        for m in t.getmembers():
            if m.name.startswith(pref):
                return np.load(io.BytesIO(t.extractfile(m).read()))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events", nargs="+", help="work-dir stems, e.g. 028084_0")
    ap.add_argument("--work", default="work")
    ap.add_argument("--stm-tag", default="_d30hpost")
    ap.add_argument("--sp-tag", default="_d09")
    ap.add_argument("--halfwidth", type=int, default=3)
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--adc", action="store_true",
                    help="also sample the pre-NF (orig) and post-NF (raw) ADC frames")
    ap.add_argument("--input-root", default="input_data_7p8_new_coh_grouping")
    ap.add_argument("--run", default="028084")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    HW = args.halfwidth
    rows = []
    for ev in args.events:
        stm = os.path.join(args.work, ev + args.stm_tag, "tracking-stm.root")
        spd = os.path.join(args.work, ev + args.sp_tag)
        if not os.path.exists(stm):
            print("# no %s" % stm, file=sys.stderr); continue
        try:
            g = {a: mem(os.path.join(spd, "protodunehd-sp-dnnroi-frames-anode%d.tar.bz2" % a),
                        "frame_gauss%d" % a) for a in range(4)}
        except Exception as e:
            print("# %s frames: %s" % (ev, e), file=sys.stderr); continue
        if any(g[a] is None for a in range(4)):
            print("# %s: missing gauss frame" % ev, file=sys.stderr); continue
        pre = post = None
        if args.adc:
            evd = os.path.join(args.input_root, "run" + args.run, "evt_" + ev.split("_")[1])
            try:
                post = {a: mem(os.path.join(spd,
                        "protodunehd-sp-dnnroi-frames-anode%d.tar.bz2" % a),
                        "frame_raw%d" % a) for a in range(4)}
                pre = {a: mem(os.path.join(evd,
                        "protodunehd-orig-frames-anode%d.tar.bz2" % a),
                        "frame_") for a in range(4)}
            except Exception as e:
                print("# %s adc: %s" % (ev, e), file=sys.stderr); pre = post = None
            if pre is not None and any(pre[a] is None or post[a] is None for a in range(4)):
                pre = post = None

        f = uproot.open(stm)
        r = f["T_rec_charge"].arrays(["x", "y", "z", "q", "nq", "pw", "pt", "ndf", "status"],
                                     library="np")
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
            live = (q > 0) & (ch >= BASE[2])
            cmap = dict(zip(zip(ch[live].tolist(), ts[live].tolist()), q[live].tolist()))

            x, y, z = r["x"][m], r["y"][m], r["z"][m]
            step = np.sqrt(np.diff(x)**2 + np.diff(y)**2 + np.diff(z)**2)
            L = float(step.sum())
            if L <= 1.0:
                continue
            dl = np.concatenate([[step[0]], (step[:-1] + step[1:]) / 2.0, [step[-1]]])[:len(x)]
            w = np.floor(r["pw"][m]).astype(np.int64)
            tt = np.rint(r["pt"][m]).astype(np.int64)
            rank = w - BASE[2]; apa = rank // PER[2]
            fitq = (r["q"][m] + 1000.0) * 10.0        # dQdx decode: (q-offset)/scale

            cells = {a: set() for a in range(4)}
            length = {a: 0.0 for a in range(4)}
            fq_fit = {a: 0.0 for a in range(4)}
            npt = {a: 0 for a in range(4)}
            for a, rk, wi, ti, dli, fqi in zip(apa, rank, w, tt, dl, fitq):
                a = int(a)
                if a < 0 or a > 3:
                    continue
                length[a] += float(dli); npt[a] += 1; fq_fit[a] += float(fqi)
                for d in range(-HW, HW + 1):
                    cells[a].add((int(wi) + d, int(ti)))
            for a in range(4):
                if not cells[a] or length[a] <= 1.0:
                    continue
                fq = cq = 0.0
                preq = postq = 0.0
                arr = g[a]
                for (wi, ti) in cells[a]:
                    rk = wi - BASE[2] - a * PER[2]
                    if rk < 0 or rk >= PER[2]:
                        continue
                    row = W_RAW_BASE[a] + rk - 2560 * a
                    t0 = ti * NTPS
                    if row < 0 or row >= arr.shape[0] or t0 < 0 or t0 + NTPS > arr.shape[1]:
                        continue
                    fq += float(np.clip(arr[row, t0:t0 + NTPS], 0, None).sum())
                    cq += float(cmap.get((wi, ti), 0.0))
                    if pre is not None:
                        pw_ = post[a][row]
                        pm = float(np.median(pw_))
                        postq += float(np.clip(pw_[t0:t0 + NTPS] - pm, 0, None).sum())
                        ow = pre[a][row]
                        om = float(np.median(ow))
                        r0 = int(round(t0 * 500.0 / 512.0))
                        r1 = max(r0 + 1, int(round((t0 + NTPS) * 500.0 / 512.0)))
                        if r1 <= ow.shape[0]:
                            preq += float(np.clip(ow[r0:r1] - om, 0, None).sum())
                rows.append(dict(event=ev, block=int(b), apa=a, npts=npt[a],
                                 L=length[a], ncell=len(cells[a]),
                                 frame_q=fq, ctpc_q=cq, fit_q=fq_fit[a],
                                 pre_q=preq, post_q=postq))

    if not rows:
        print("no rows", file=sys.stderr); return 1
    cols = list(rows[0].keys())
    with open(args.out + "_tracks.tsv", "w") as fh:
        fh.write("# doc pdhd/10 d10_tube_census.py hw=%d events=%d\n" % (HW, len(args.events)))
        fh.write("\t".join(cols) + "\n")
        for rr in rows:
            fh.write("\t".join(("%.6g" % rr[c]) if isinstance(rr[c], float) else str(rr[c])
                               for c in cols) + "\n")
    print("apa  ntrk    npts" + ("    preNF/cm  postNF/cm" if args.adc else "")
          + "   frame_q/cm   ctpc_q/cm   fit_q/cm   ctpc/frame  fit/ctpc")
    lines = []
    for a in range(4):
        sub = [rr for rr in rows if rr["apa"] == a and rr["L"] > 5.0]
        if not sub:
            continue
        Ls = sum(rr["L"] for rr in sub)
        fq = sum(rr["frame_q"] for rr in sub); cq = sum(rr["ctpc_q"] for rr in sub)
        tq = sum(rr["fit_q"] for rr in sub)
        pq = sum(rr.get("pre_q", 0.0) for rr in sub)
        oq = sum(rr.get("post_q", 0.0) for rr in sub)
        if args.adc:
            line = ("%3d %5d %7d %9.1f %10.1f %12.0f %11.0f %10.0f %11.3f %9.3f"
                    % (a, len(sub), sum(rr["npts"] for rr in sub), pq / Ls, oq / Ls,
                       fq / Ls, cq / Ls, tq / Ls, cq / max(fq, 1), tq / max(cq, 1)))
        else:
            line = ("%3d %5d %7d %12.0f %11.0f %10.0f %11.3f %9.3f"
                    % (a, len(sub), sum(rr["npts"] for rr in sub),
                       fq / Ls, cq / Ls, tq / Ls, cq / max(fq, 1), tq / max(cq, 1)))
        print(line); lines.append(line)
    with open(args.out + "_summary.tsv", "w") as fh:
        fh.write(("apa\tntrk\tnpts\tpreNF_per_cm\tpostNF_per_cm\t" if args.adc else "apa\tntrk\tnpts\t")
                 + "frame_q_per_cm\tctpc_q_per_cm\tfit_q_per_cm\tctpc_over_frame\tfit_over_ctpc\n")
        for line in lines:
            fh.write("\t".join(line.split()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
