#!/usr/bin/env python3
"""doc pdhd/10 -- hand-scan display for the APA2 corner tracks.

Three layers per plane, so the scan can separate the two readings that doc 10
cannot separate on its own:

  grey   every SP gauss charge the detector recorded in this APA (the truth)
  blue   the ctpc cells this fit's block actually holds (what imaging kept)
  red    the fitted STM trajectory

Read it as:
  grey but no blue  -> imaging/clustering dropped real charge
  blue but no red   -> the fit ignored charge it was given
  red on empty grey -> the trajectory is in a place nothing was recorded

Channel arithmetic (verified in doc 10 sec 2, 100.0% self-test):
  pu:  rank = pu        ; apa = rank//800 ; frame row =        rank%800
  pv:  rank = pv - 3200 ; apa = rank//800 ; frame row =  800 + rank%800
  pw:  rank = pw - 6400 ; apa = rank//960 ; frame row = 1600 + rank%960
  time slice s <-> frame ticks [4s, 4s+4)
"""
import argparse, io, os, sys, tarfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import uproot

BASE = (0, 3200, 6400); PER = (800, 800, 960)
ROW0 = (0, 800, 1600)
NTPS = 4


def mem(arch, pref):
    with tarfile.open(arch, "r:bz2") as t:
        for m in t.getmembers():
            if m.name.startswith(pref):
                return np.load(io.BytesIO(t.extractfile(m).read()))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event", help="work-dir stem, e.g. 028084_9")
    ap.add_argument("block", type=int)
    ap.add_argument("--apa", type=int, default=2)
    ap.add_argument("--work", default="work")
    ap.add_argument("--stm-tag", default="_d30hpost")
    ap.add_argument("--sp-tag", default="_d09")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    a = args.apa
    spd = os.path.join(args.work, args.event + args.sp_tag)
    arch = os.path.join(spd, "protodunehd-sp-dnnroi-frames-anode%d.tar.bz2" % a)
    fr = mem(arch, "frame_gauss%d" % a)
    if fr is None:
        print("# no frame for %s" % args.event, file=sys.stderr); return 1

    f = uproot.open(os.path.join(args.work, args.event + args.stm_tag, "tracking-stm.root"))
    r = f["T_rec_charge"].arrays(["x", "y", "z", "q", "nq", "rr", "pu", "pv", "pw", "pt",
                                  "ndf", "status"], library="np")
    pj = f["T_proj_data"].arrays(["cluster_id", "channel", "time_slice", "charge"],
                                 library="np")
    m = r["ndf"].astype(np.int64) == args.block
    if not m.sum():
        print("# no block %d" % args.block, file=sys.stderr); return 1
    cid = list(pj["cluster_id"][0]) if len(pj["cluster_id"]) else []
    i = cid.index(args.block) if args.block in cid else None
    ch = ts = cq = None
    if i is not None:
        ch = np.asarray(pj["channel"][0][i]); ts = np.asarray(pj["time_slice"][0][i])
        cq = np.asarray(pj["charge"][0][i])
        keep = cq > 0
        ch, ts = ch[keep], ts[keep]

    # rebin the frame to imaging slices for display
    n = fr.shape[1] // NTPS * NTPS
    sl = np.clip(fr[:, :n], 0, None).reshape(fr.shape[0], -1, NTPS).sum(axis=2)

    fig, ax = plt.subplots(1, 5, figsize=(25, 5.6),
                           gridspec_kw=dict(width_ratios=[1, 1, 1, 1, 0.72]))
    names = "UVW"
    tmin = max(0, int(np.rint(r["pt"][m]).min()) - 120)
    tmax = min(sl.shape[1], int(np.rint(r["pt"][m]).max()) + 120)
    for p in range(3):
        axp = ax[p]
        lo = ROW0[p]; hi = lo + PER[p]
        sub = sl[lo:hi, tmin:tmax]
        axp.imshow(np.log10(sub + 1), aspect="auto", origin="lower", cmap="Greys",
                   extent=[tmin, tmax, 0, PER[p]], vmin=0, vmax=4.5,
                   interpolation="nearest")
        if ch is not None:
            s = (ch >= BASE[p] + a * PER[p]) & (ch < BASE[p] + (a + 1) * PER[p])
            axp.plot(ts[s], (ch[s] - BASE[p] - a * PER[p]), ".", ms=1.6,
                     color="#1f77b4", alpha=0.55,
                     label="ctpc cells in this block (n=%d)" % int(s.sum()))
        key = ("pu", "pv", "pw")[p]
        rank = np.floor(r[key][m]).astype(np.int64) - BASE[p]
        wl = rank - a * PER[p]
        ok = (wl >= 0) & (wl < PER[p])
        axp.plot(r["pt"][m][ok], wl[ok], "-", color="#d62728", lw=1.4,
                 label="fitted STM trajectory")
        axp.set_xlim(tmin, tmax); axp.set_ylim(0, PER[p])
        axp.set_xlabel("imaging time slice")
        axp.set_ylabel("wire index within APA%d plane %s" % (a, names[p]))
        ttl = "plane %s" % names[p]
        if p == 2:
            ttl += "  (imaging face = upper 480 for APA0/APA2)"
        axp.set_title(ttl, fontsize=10)
        axp.legend(fontsize=7, loc="upper right", framealpha=0.85)

    # zoom on the collection plane, +-40 wires about the trajectory, so the
    # question "is there charge under the red line" is answerable by eye
    rankw = np.floor(r["pw"][m]).astype(np.int64) - BASE[2] - a * PER[2]
    w0 = max(0, int(rankw.min()) - 40); w1 = min(PER[2], int(rankw.max()) + 41)
    azm = ax[3]
    azm.imshow(np.log10(sl[ROW0[2] + w0:ROW0[2] + w1, tmin:tmax] + 1), aspect="auto",
               origin="lower", cmap="Greys", extent=[tmin, tmax, w0, w1],
               vmin=0, vmax=4.5, interpolation="nearest")
    if ch is not None:
        s2 = (ch >= BASE[2] + a * PER[2]) & (ch < BASE[2] + (a + 1) * PER[2])
        azm.plot(ts[s2], ch[s2] - BASE[2] - a * PER[2], ".", ms=3.5,
                 color="#1f77b4", alpha=0.8, label="ctpc cells")
    azm.plot(r["pt"][m], rankw, "-", color="#d62728", lw=1.4, label="trajectory")
    azm.set_xlim(tmin, tmax); azm.set_ylim(w0, w1)
    azm.set_xlabel("imaging time slice"); azm.set_ylabel("wire index, plane W")
    azm.set_title("plane W, zoom +-40 wires", fontsize=10)
    azm.legend(fontsize=7, loc="upper right", framealpha=0.85)

    dq = (r["q"][m] + 1000.0) * 10.0 / np.maximum(r["nq"][m], 1e-6)
    ax[4].plot(r["rr"][m], dq / 1e3, ".", ms=3, color="0.25")
    ax[4].axhline(54.6, color="C2", lw=1.2, ls="--", label="muon plateau 54.6 ke/cm")
    ax[4].axhline(0, color="C3", lw=1.0)
    ax[4].set_xlabel("residual range [cm]"); ax[4].set_ylabel("dQ/dx [ke/cm]")
    ax[4].set_title("fitted dQ/dx (%.0f%% negative)" % (100 * np.mean(dq < 0)), fontsize=10)
    ax[4].legend(fontsize=7); ax[4].grid(alpha=0.3)

    x, y, z = r["x"][m], r["y"][m], r["z"][m]
    L = float(np.sum(np.sqrt(np.diff(x)**2 + np.diff(y)**2 + np.diff(z)**2)))
    fig.suptitle("%s  block %d  APA%d   %d points, L = %.0f cm   "
                 "x %.0f..%.0f   y %.0f..%.0f   z %.0f..%.0f cm"
                 % (args.event, args.block, a, int(m.sum()), L,
                    x.min(), x.max(), y.min(), y.max(), z.min(), z.max()),
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(args.out, dpi=95)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
