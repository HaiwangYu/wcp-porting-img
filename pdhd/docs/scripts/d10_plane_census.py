#!/usr/bin/env python3
"""doc pdhd/10 sec 4.0 and 4.1 -- the collection plane, with no trajectory
involved.

Reads the SP gauss frames straight out of the per-anode archives and reports,
per APA, over the imaging collection face only:

  sec 4.0  charge per OCCUPIED (wire, imaging slice) cell, and the occupancy.
           This is the discriminator between "the trajectory is misplaced" and
           "less charge was collected there": every other number in doc 10 is
           measured at the fitted trajectory and cannot tell them apart.
  sec 4.1  charge per wire in 48-wire blocks, and the count of quiet channels.

Imaging-face collection channels: 2080-2559 / 4160-4639 / 7200-7679 / 9280-9759
(from protodunehd-wires-larsoft-v1.json.bz2, and confirmed against the compiled
OmnibusSigProc channel map in the run log).
"""
import argparse, glob, io, os, sys, tarfile
import numpy as np

IMG = ((2080, 2560), (4160, 4640), (7200, 7680), (9280, 9760))
NTPS = 4


def mem(arch, pref):
    with tarfile.open(arch, "r:bz2") as t:
        for m in t.getmembers():
            if m.name.startswith(pref):
                return np.load(io.BytesIO(t.extractfile(m).read()))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="work dirs holding the SP archives")
    ap.add_argument("--quiet-thresh", type=float, default=1e5,
                    help="mean charge per event below which a wire counts as quiet")
    ap.add_argument("--out")
    args = ap.parse_args()

    dirs = []
    for pat in args.dirs:
        dirs.extend(sorted(glob.glob(pat)) if any(c in pat for c in "*?[") else [pat])

    acc = {a: np.zeros(3) for a in range(4)}          # occ cells, charge, total cells
    perwire = {a: None for a in range(4)}
    nev = 0
    for spd in dirs:
        fr = {}
        ok = True
        for a in range(4):
            p = os.path.join(spd, "protodunehd-sp-dnnroi-frames-anode%d.tar.bz2" % a)
            if not os.path.exists(p):
                ok = False
                break
            fr[a] = mem(p, "frame_gauss%d" % a)
            if fr[a] is None:
                ok = False
                break
        if not ok:
            print("# skip %s" % spd, file=sys.stderr)
            continue
        nev += 1
        for a in range(4):
            lo, hi = IMG[a]
            sub = np.clip(fr[a][lo - 2560 * a:hi - 2560 * a], 0, None)
            n = sub.shape[1] // NTPS * NTPS
            sl = sub[:, :n].reshape(sub.shape[0], -1, NTPS).sum(axis=2)
            occ = sl > 0
            acc[a][0] += occ.sum(); acc[a][1] += sl[occ].sum(); acc[a][2] += sl.size
            q = sub.sum(axis=1)
            perwire[a] = q if perwire[a] is None else perwire[a] + q

    if not nev:
        print("no events", file=sys.stderr); return 1
    qs = {a: acc[a][1] / max(acc[a][0], 1) for a in range(4)}
    ref = 0.5 * (qs[1] + qs[3])
    lines = ["# doc pdhd/10 d10_plane_census.py events=%d" % nev,
             "apa\tocc_cells_per_evt\tq_per_occupied_cell\toccupancy\tratio_to_mean_apa13"]
    for a in range(4):
        lines.append("%d\t%.0f\t%.0f\t%.4f\t%.3f"
                     % (a, acc[a][0] / nev, qs[a], acc[a][0] / acc[a][2], qs[a] / ref))
    lines.append("")
    lines.append("# per-wire charge on the imaging collection face, 48-wire blocks, 1e6 e/event")
    lines.append("block\tapa0\tapa1\tapa2\tapa3")
    for k in range(10):
        sl = slice(k * 48, (k + 1) * 48)
        lines.append("%d-%d\t" % (k * 48, (k + 1) * 48 - 1)
                     + "\t".join("%.2f" % (perwire[a][sl].sum() / nev / 1e6) for a in range(4)))
    lines.append("")
    lines.append("# quiet wires (mean charge per event < %g e)" % args.quiet_thresh)
    lines.append("apa\tnquiet\tof\tindices")
    for a in range(4):
        bad = np.where(perwire[a] / nev < args.quiet_thresh)[0]
        lines.append("%d\t%d\t%d\t%s" % (a, len(bad), len(perwire[a]),
                                         ",".join(str(int(x)) for x in bad) or "-"))
    txt = "\n".join(lines)
    print(txt)
    if args.out:
        open(args.out, "w").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
