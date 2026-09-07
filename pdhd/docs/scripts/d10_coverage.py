#!/usr/bin/env python3
"""doc pdhd/10 §1 -- wire coverage of the fitted trajectory, per APA per plane.

Doc pdvd/50 §4.2c decomposed the PDHD x<0 charge deficit as

    charge per cm = (channels per cm) x (slices per channel) x (charge per pixel)

and measured the last two flat across APAs (5.5-6.8 ke, 17-19 slices).  The
whole factor therefore lives in channels-per-cm -- the one factor doc 50
normalised wrongly (by sum(nq), ~2x the step) and set aside.

This script redoes it exactly, and normalises it so track angle cannot fake the
effect.  The trick is that the fit already carries its own wire coordinate:
T_rec_charge's pu/pv/pw are ChanScheme::globalf(plane, apa, face, wire) --
the SAME integer numbering as T_proj_data's `channel`
(PdvdMagnifyTrackingVisitor.cxx:414 vs :599-601).  So

    expected wires = every integer the trajectory's own wire coordinate crosses
    observed wires = those that carry a T_proj_data cell
    coverage       = observed / expected

needs no geometry file and no angle model: it is exact per track.

Outputs <out>_blocks.tsv (one row per accepted STM pass) and <out>_summary.tsv.
"""
import argparse, glob, math, os, sys
import numpy as np
import uproot

# ChanScheme layout: base[p] + rank of channel among that plane's channels over
# ALL anodes.  Verified for PDHD in doc pdvd/50 sec 4.2b (78867/78867).
DET = {
    "pdhd": dict(base=(0, 3200, 6400), per_apa=(800, 800, 960), napa=4,
                 nch=(3200, 3200, 3840)),
}


def plane_of(det, ch):
    b = DET[det]["base"]
    return 0 if ch < b[1] else (1 if ch < b[2] else 2)


def apa_of(det, plane, ch):
    d = DET[det]
    return (ch - d["base"][plane]) // d["per_apa"][plane]


def crossed(coords, times):
    """The (wire, time) cells the trajectory crosses.

    Fills the gaps between consecutive fit points (the fit step ~0.6 cm can
    exceed a pitch) and carries the interpolated time with each filled wire, so
    a cell is only "expected" where the track actually is -- T_proj_data spans
    the bounding box of main + associated clusters, so a channel-only match
    counts charge that belongs to a different part of the event.
    """
    out = {}
    f = np.floor(coords).astype(np.int64)
    for j in range(len(f)):
        a, ta = f[j], times[j]
        out.setdefault(int(a), ta)
        if j + 1 >= len(f):
            break
        b, tb = f[j + 1], times[j + 1]
        if abs(int(b) - int(a)) > 4000:      # a point that jumped anodes
            continue
        lo, hi = (a, b) if a <= b else (b, a)
        n = int(hi) - int(lo)
        if n <= 0:
            continue
        for k in range(n + 1):
            w = int(lo) + k
            frac = (w - a) / (b - a) if b != a else 0.0
            out.setdefault(w, ta + frac * (tb - ta))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--det", default="pdhd", choices=sorted(DET))
    ap.add_argument("--status", type=int, default=0)
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--tol", type=int, default=2,
                    help="time-slice tolerance for a cell match")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    files = []
    for pat in args.files:
        files.extend(sorted(glob.glob(pat)) if any(c in pat for c in "*?[") else [pat])
    rows = []

    for fn in files:
        evt = os.path.basename(os.path.dirname(fn))
        try:
            f = uproot.open(fn)
            rec = f["T_rec_charge"].arrays(
                ["x", "y", "z", "q", "nq", "pu", "pv", "pw", "pt", "rr",
                 "ndf", "status"], library="np")
            pj = f["T_proj_data"].arrays(
                ["cluster_id", "channel", "time_slice", "charge"], library="np")
            # T_proj_data is ONE entry holding vector branches; unwrap it.
            proj = {k: (pj[k][0] if len(pj[k]) else []) for k in pj}
        except Exception as e:
            print(f"# skip {fn}: {e}", file=sys.stderr)
            continue

        pmap = {int(b): i for i, b in enumerate(proj["cluster_id"])}
        blocks = rec["ndf"].astype(np.int64)
        for blk in np.unique(blocks):
            m = blocks == blk
            if m.sum() < args.min_points:
                continue
            st = int(rec["status"][m][0])
            if st != args.status:
                continue
            x, y, z = rec["x"][m], rec["y"][m], rec["z"][m]
            L = float(np.sum(np.sqrt(np.diff(x)**2 + np.diff(y)**2 + np.diff(z)**2)))
            if L <= 1.0:
                continue
            i = pmap.get(int(blk))
            if i is None:
                continue
            ch = np.asarray(proj["channel"][i], dtype=np.int64)
            ts = np.asarray(proj["time_slice"][i], dtype=np.int64)
            q = np.asarray(proj["charge"][i], dtype=np.float64)

            live = q > 0
            cells, qof = {}, {}
            for c, t, qq0 in zip(ch[live], ts[live], q[live]):
                cells.setdefault(int(c), []).append(int(t))
                qof[(int(c), int(t))] = qq0

            wapa = apa_of(args.det, 2, np.floor(rec["pw"][m]).astype(np.int64))
            per = {}
            for p, key in enumerate(("pu", "pv", "pw")):
                tag = "uvw"[p]
                wires = np.floor(rec[key][m]).astype(np.int64)
                tt = rec["pt"][m]
                hit = np.zeros(len(wires), dtype=bool)
                pres = np.zeros(len(wires), dtype=bool)
                qq = np.zeros(len(wires))
                for j, (w, t) in enumerate(zip(wires, tt)):
                    tl = cells.get(int(w))
                    if tl is None:
                        continue
                    pres[j] = True
                    best = min(tl, key=lambda u: abs(u - t))
                    if abs(best - t) <= args.tol:
                        hit[j] = True
                        qq[j] = float(qof.get((int(w), best), 0.0))
                per[tag] = (hit, pres, qq)
            # within-anode collection wire index (0..959); PDHD's imaging face
            # is the UPPER half for APA0/APA2 and the LOWER half for APA1/APA3
            d = DET[args.det]
            wloc = (np.floor(rec["pw"][m]).astype(np.int64) - d["base"][2]
                    - wapa * d["per_apa"][2])
            step = L / max(len(wapa) - 1, 1)
            for a in np.unique(wapa):
                k = wapa == a
                row = dict(det=args.det, event=evt, run=evt.split("_")[0],
                           block=int(blk), apa=int(a), npts=int(k.sum()),
                           L=float(k.sum()) * step, status=st,
                           wire_med=float(np.median(wloc[k])),
                           frac_hi96=float(np.mean(wloc[k] >= 864)))
                for tag in "uvw":
                    hit, pres, qq = per[tag]
                    row[f"hit_{tag}"] = int(hit[k].sum())
                    row[f"pres_{tag}"] = int(pres[k].sum())
                    row[f"cov_{tag}"] = float(hit[k].mean())
                    row[f"covch_{tag}"] = float(pres[k].mean())
                    row[f"qhit_{tag}"] = float(qq[k].sum())
                    row[f"qpt_{tag}"] = float(qq[k].sum()) / max(int(hit[k].sum()), 1)
                    row[f"qpcm_{tag}"] = float(qq[k].sum()) / max(row["L"], 1e-9)
                rows.append(row)

    if not rows:
        print("no blocks", file=sys.stderr)
        return 1
    cols = list(rows[0].keys())
    with open(args.out + "_blocks.tsv", "w") as fh:
        fh.write("# doc pdhd/10 d10_coverage.py det=%s status=%d files=%d\n"
                 % (args.det, args.status, len(files)))
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(("%.6g" % r[c]) if isinstance(r[c], float) else str(r[c])
                               for c in cols) + "\n")

    # summary per APA per plane -- weighted by points, not by track
    apas = sorted({r["apa"] for r in rows})
    runs = sorted({r["run"] for r in rows})
    lines = ["apa\tplane\trun\tntrk\tnpts\tcov\tcov_ch\tq_per_hit\tq_per_cm"]
    for a in apas:
        for tag in "uvw":
            for run in ["ALL"] + runs:
                sub = [r for r in rows if r["apa"] == a and (run == "ALL" or r["run"] == run)]
                if not sub:
                    continue
                n = sum(r["npts"] for r in sub)
                h = sum(r[f"hit_{tag}"] for r in sub)
                pr = sum(r[f"pres_{tag}"] for r in sub)
                q = sum(r[f"qhit_{tag}"] for r in sub)
                ll = sum(r["L"] for r in sub)
                lines.append("%d\t%s\t%s\t%d\t%d\t%.4f\t%.4f\t%.0f\t%.0f"
                             % (a, tag.upper(), run, len(sub), n, h / n, pr / n,
                                q / max(h, 1), q / max(ll, 1e-9)))
    with open(args.out + "_summary.tsv", "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
