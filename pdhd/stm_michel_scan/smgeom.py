#!/usr/bin/env python3
"""doc pdhd/12 -- detector geometry for the STM + Michel hand-scan display.

The ONE shared module of this app (sibling-import pattern of
pdvd/docs/nf_sp_img_clus/scripts/d47_peakedness.py:21-23).  Everything else in
this directory is a fork by duplication.

It answers two questions the display asks on every item:

  1. what box do I draw          -> ENVELOPE[det]
  2. where did the muon stop     -> unit_from_wire() / unit_from_geometry()

WHY THE WIRE ROUTE IS THE PRIMARY ONE
  T_rec_charge stores pw = ChanScheme::globalf(2, apa, face, wire)
  (root/src/PdvdMagnifyTrackingVisitor.cxx:601), i.e. base[2] + the rank of the
  channel among the COLLECTION plane's channels over every anode and face.  That
  is a readout fact: it needs no T0 and no drift model.

  sign(x) is NOT a safe substitute on PDVD.  cfg/pgrapher/experiment/protodunevd/
  clus.jsonnet:80-84 says it outright -- the two drift volumes overlap in the
  pre-T0 apparent-x frame, and PDVD runs with time_offset = 0.  Out-of-time
  cosmics are exactly the population a stopping-muon scan looks at.  On PDHD the
  two agree (doc pdvd/50 sec 4.2b: 78867/78867) because imaging runs per APA
  there, so a wrong T0 slides x WITHIN one APA rather than across volumes.

THE RANK BLOCKS, RE-DERIVED FROM THE PRODUCTION WIRE FILES (doc pdhd/12 sec 4)
  Both files were re-read here and every block is EXACTLY contiguous, so integer
  division is not an approximation:

    pdhd  protodunehd-wires-larsoft-v1.json.bz2
          nch=[3200,3200,3840] base=[0,3200,6400]
          apa  = (pw - 6400) // 960          960 W channels per APA
          face blocks of 480; face 1 is the LOWER half on all four APAs
    pdvd  protodunevd-wires-larsoft-v7-uvwfit.json.bz2
          nch=[3808,3808,4672] base=[0,3808,7616]
          anode = (pw - 7616) // 584         584 W channels per anode
          cru   = (pw - 7616) // 292         16 CRUs, anode-major then y-ascending
          face 1 is the LOWER half on anodes 0,1,4,5 (y<0 CRPs) and the UPPER
          half on anodes 2,3,6,7 (y>0 CRPs) -- which is what makes the sub-block
          monotone in y in BOTH, so `cru` alone orders the detector in y.

  This settles the "the per-anode channel run is not verified contiguous"
  caveat that d51_dqdx_rr_apa.py:96-98 refused to act on, and is why this app
  can label a PDVD stopping point by CRU rather than by drift volume.

ENVELOPES
  The sensvol union, NOT `dvm.overall` from clus.jsonnet -- that one already
  carries a 15 cm space-charge inset (pdhd/clus.jsonnet:63-66,
  protodunevd/clus.jsonnet:102-105) and would draw a box inside the charge.
  Sources: pdhd/curved_fiducial.jsonnet:72-77, protodunevd/crp_gap_fiducial.jsonnet,
  cross-checked against the AnodePlane sensvol lines in the production PR logs.
"""

ENVELOPE = {
    "pdhd": dict(x=(-357.985, 357.985), y=(7.61, 606.0), z=(0.234345, 462.297),
                 cathode=2.54),
    "pdvd": dict(x=(-339.91, 339.91), y=(-336.39, 336.39), z=(0.813, 298.435),
                 cathode=3.0),
}

# Collection-plane channel scheme.  Both rows are the runtime
# 'channel scheme nch=... base=...' line of the production job logs AND the
# re-derivation from the wire file (doc pdhd/12 sec 4).
CHAN = {
    "pdhd": dict(base_w=6400, per_unit=960, per_face=480, nunit=4),
    "pdvd": dict(base_w=7616, per_unit=584, per_face=292, nunit=8),
}

# The FULL per-plane channel scheme, needed by the 2-D measurement panel (doc
# pdhd/12 sec 5.4).  T_proj_data.channel and T_bad_ch.chid are written with
# ChanScheme::global(), pu/pv/pw with ChanScheme::globalf() -- the SAME
# coordinate, so `base` splits all three into planes.
#
# THIS SPLIT IS THE ONE THING HERE THAT FAILS SILENTLY.  A channel-to-plane map
# that is wrong but self-consistent yields no error, no empty bin and no NaN; it
# answers a different question (feedback_magnify_channel_is_a_plane_rank, which
# is exactly this trap on exactly these files).  So it is gated CAUSALLY, by two
# code paths that were written independently having to agree: the fitter's own
# wire coordinate must land on a cell the projection writer emitted.  Measured
# over every chain point of both arms (doc pdhd/12 sec 5.4a):
#     pdhd  U 0.9485  V 0.9439  W 0.9101   of fit points land on a T_proj_data
#     pdvd  U 0.9222  V 0.9243  W 0.9492   cell of the same channel, +-2 slices
# and every plane's fit-wire range lies strictly inside its own base block.
# A wrong `base` would put a whole plane's fit wires in a neighbour's block.
BASE = {"pdhd": (0, 3200, 6400), "pdvd": (0, 3808, 7616)}
NCH = {"pdhd": (3200, 3200, 3840), "pdvd": (3808, 3808, 4672)}
PLANE_NAMES = ("U", "V", "W")

# T_bad_ch carries start_time/end_time in TICKS while T_proj_data.time_slice and
# T_rec_charge's pt are in SLICES -- the asymmetry is real, not a bug to fix:
# write_bad_channels clamps against m_nticks (PdvdPrMagnifyTrackingVisitor.cxx
# :274-277) while write_proj_data divides by nticks_per_slice (:559).
# nticks_live_slice is 4 in both production configs (pdhd/clus.jsonnet:82,
# protodunevd/clus.jsonnet:123) -- but a config is not a measurement
# (feedback_dump_meta_is_not_the_config), so the self-test gates it on the FILES:
# max(T_bad_ch.end_time) / (max(T_proj_data.time_slice) + 1) = 6000/1500 = 4.000
# on PDHD and 10000/2507 = 3.989 on PDVD.  At /1 the dead bands would sit at a
# quarter of their true time and visibly miss every gap.
# LIMIT: the C++ reads nticks_per_slice per (apa, face); this is one number for
# the whole detector.  Both production configs set it globally, so the two agree
# today -- a config that varied it per face would break this.
TICKS_PER_SLICE = {"pdhd": 4, "pdvd": 4}

# Seams a stopping point can sit on.  x is the drift axis on both detectors.
SEAMS = {
    "pdhd": dict(y=[], z=[231.0], x=[0.0]),
    "pdvd": dict(y=[-168.50, 0.0, 168.50], z=[149.65], x=[0.0]),
}

# PDVD: which face ident is the LOWER (more negative y) half of each anode.
# From the wire file; see the module docstring.
_PDVD_LOW_FACE = {0: 1, 1: 1, 2: 0, 3: 0, 4: 1, 5: 1, 6: 0, 7: 0}

# The writer's DEFAULT wire coordinate, and the only value on which the wire and
# geometric routes are ever seen to disagree.  globalf(2, apa=0, face=0, wire=0)
# is base + per_face -- 6880 on PDHD, 7908 on PDVD -- so a fit point whose
# (apa, face, wire) was never filled lands there while its x/y/z say something
# else entirely.  Measured over the whole d51hnu/d51vnu chain-point population:
# 3 of 97 721 points on PDHD and 6 of 166 037 on PDVD (doc pdhd/12 sec 4.3).
# Every other point agrees, which is what earns the wire route on BOTH detectors.
SENTINEL_PW = {"pdhd": 6880, "pdvd": 7908}


def plane_from_chan(det, ch):
    """0 (U) / 1 (V) / 2 (W) for a global channel rank, or None if out of range.

    Applies to T_proj_data.channel, T_bad_ch.chid and the floor of pu/pv/pw
    alike -- one coordinate, one split.  See BASE above for how it is gated.
    """
    if ch is None:
        return None
    b, n = BASE[det], NCH[det]
    c = int(ch)
    if c < 0 or c >= b[2] + n[2]:
        return None
    return 0 if c < b[1] else (1 if c < b[2] else 2)


def plane_span(det, plane):
    """(first, last) global channel rank of a plane, inclusive."""
    b, n = BASE[det], NCH[det]
    return b[plane], b[plane] + n[plane] - 1


def ticks_to_slice(det, t):
    """T_bad_ch tick -> T_proj_data time slice.  See TICKS_PER_SLICE."""
    return t / float(TICKS_PER_SLICE[det])


def unit_from_wire(det, pw):
    """(unit, cru, face) from the stored collection-plane wire coordinate.

    `unit` is the APA on PDHD and the anode on PDVD.  `cru` is None on PDHD
    (an APA face is not a separate readout unit there) and 0..15 on PDVD.
    Returns (None, None, None) when pw is outside the collection block, which
    happens for a point whose fit landed on an induction wire only.
    """
    c = CHAN[det]
    if pw is None:
        return None, None, None
    k = int(pw) - c["base_w"]
    if k < 0 or k >= c["per_unit"] * c["nunit"]:
        return None, None, None
    unit = k // c["per_unit"]
    half = (k - unit * c["per_unit"]) // c["per_face"]      # 0 = lower in y
    if det == "pdhd":
        # face 1 is the lower half on every APA (wire-file derivation)
        return unit, None, (1 if half == 0 else 0)
    low = _PDVD_LOW_FACE[unit]
    return unit, k // c["per_face"], (low if half == 0 else 1 - low)


def unit_from_geometry(det, x, y, z):
    """(unit, cru, face) from position.  The CROSS-CHECK route, never the label.

    PDHD: APA0 x<0 z<231, APA1 x>0 z<231, APA2 x<0 z>=231, APA3 x>0 z>=231;
          face 0 is the -x drift (APA0, APA2), face 1 the +x drift.
    PDVD: anode = 4*(x>0) + 2*(y>0) + (z >= 149.65); cru adds |y| >= 168.50.
    """
    if det == "pdhd":
        unit = (2 if z >= 231.0 else 0) + (1 if x > 0 else 0)
        return unit, None, (1 if x > 0 else 0)
    unit = (4 if x > 0 else 0) + (2 if y > 0 else 0) + (1 if z >= 149.65 else 0)
    outer = abs(y) >= 168.50
    low = _PDVD_LOW_FACE[unit]
    # the lower-in-y half of a y<0 CRP is the OUTER one; of a y>0 CRP the inner
    lower_half = outer if y < 0 else (not outer)
    face = low if lower_half else 1 - low
    return unit, 2 * unit + (0 if lower_half else 1), face


def unit_label(det, unit, cru=None, face=None):
    """The badge string for the header."""
    if unit is None:
        return "unit unknown"
    if det == "pdhd":
        side = "x<0, face 0" if unit in (0, 2) else "x>0, face 1"
        return "APA%d  (%s, z%s231)" % (unit, side, "<" if unit < 2 else ">=")
    drift = "top drift (x>0)" if unit >= 4 else "bottom drift (x<0)"
    crp = "CRP y>0" if unit in (2, 3, 6, 7) else "CRP y<0"
    zh = "z>=149.65" if unit in (1, 3, 5, 7) else "z<149.65"
    return "anode %d / CRU %s  (%s, %s, %s, face %s)" % (
        unit, "?" if cru is None else cru, drift, crp, zh,
        "?" if face is None else face)


def seam_distances(det, x, y, z):
    """{axis: distance in cm to the nearest seam on that axis} plus the walls.

    A stopping point sitting 1 cm from a CRU seam is a different object from one
    in the middle of a CRU, and the display has to say which without the scanner
    doing arithmetic.
    """
    e, s = ENVELOPE[det], SEAMS[det]
    p = dict(x=x, y=y, z=z)
    out = {}
    for ax in ("x", "y", "z"):
        cand = [abs(p[ax] - v) for v in s[ax]]
        out["seam_" + ax] = min(cand) if cand else float("inf")
        out["wall_" + ax] = min(abs(p[ax] - e[ax][0]), abs(p[ax] - e[ax][1]))
    out["cathode"] = abs(abs(x) - e["cathode"])
    out["anode_face"] = abs(abs(x) - e["x"][1])
    return out
