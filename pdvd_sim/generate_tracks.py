#!/usr/bin/env python3
"""Generate per-(anode, plane) track JSON files for ProtoDUNE-VD.

For each anode and each wire plane (U, V, W) the track is:
  - parallel to the wire plane (constant x = x_plane shifted toward the cathode)
  - perpendicular to that plane's wires (along pitch_dir = wire_dir x x-hat)
  - centered at the geometric center of that face's plane bbox
  - extends to the bbox edges in the pitch direction (full length, no margin)

Geometry coordinates in the wires JSON are in mm; track JSON is in cm.

Output:
  tracks/tracks-vd-anode<N>-<P>.json   (8x3 = 24 files)

Adapted from /nfs/data/1/xning/wirecell-working/generate_tracks.py — specialised
for VD and parameterised so the geometry path and output dir are configurable.
"""
from __future__ import annotations

import argparse
import bz2
import json
import os
from pathlib import Path

import numpy as np


PLANE_LABELS = ['U', 'V', 'W']

# Drift offset (mm): see params.jsonnet (pgrapher/experiment/protodunevd).
# ~500 mm keeps the track clear of the anode plane and inside the field-response region.
DRIFT_OFFSET_MM = 500.0


def load_geom(path):
    with bz2.open(path) as f:
        data = json.load(f)
    s = data['Store']
    anodes = [a['Anode'] for a in s['anodes']]
    faces = [f['Face'] for f in s['faces']]
    planes = [p['Plane'] for p in s['planes']]
    wires = [w['Wire'] for w in s['wires']]
    points = [p['Point'] for p in s['points']]
    return anodes, faces, planes, wires, points


def plane_geometry(plane_idx, planes, wires, points):
    pl = planes[plane_idx]
    wlist = pl['wires']
    tails, heads = [], []
    for wid in wlist:
        w = wires[wid]
        tails.append(points[w['tail']])
        heads.append(points[w['head']])
    tails = np.array([[p['x'], p['y'], p['z']] for p in tails])
    heads = np.array([[p['x'], p['y'], p['z']] for p in heads])
    dirs = heads - tails
    lengths = np.linalg.norm(dirs, axis=1)
    udirs = dirs / lengths[:, None]
    wire_dir = udirs.mean(axis=0)
    wire_dir /= np.linalg.norm(wire_dir)

    allpts = np.vstack([tails, heads])
    bbox_min = allpts.min(axis=0)
    bbox_max = allpts.max(axis=0)
    centers = (tails + heads) / 2
    x_plane = float(centers[:, 0].mean())

    xhat = np.array([1.0, 0.0, 0.0])
    pitch_dir = np.cross(wire_dir, xhat)
    pn = np.linalg.norm(pitch_dir)
    pitch_dir = np.array([0.0, 1.0, 0.0]) if pn < 1e-9 else pitch_dir / pn

    return wire_dir, pitch_dir, x_plane, bbox_min, bbox_max


def chord_through_center(center_yz, pitch_dir_yz, ymin, ymax, zmin, zmax):
    cy, cz = center_yz
    dy, dz = pitch_dir_yz
    pos, neg = [], []
    eps = 1e-12
    if abs(dy) > eps:
        for edge in (ymin, ymax):
            t = (edge - cy) / dy
            (pos if t > 0 else neg).append(t) if t != 0 else None
    if abs(dz) > eps:
        for edge in (zmin, zmax):
            t = (edge - cz) / dz
            (pos if t > 0 else neg).append(t) if t != 0 else None
    return (max(neg) if neg else 0.0), (min(pos) if pos else 0.0)


def make_track(face_idx, plane_idx_in_face, planes, wires, points, faces, drift_offset_mm):
    face = faces[face_idx]
    pi = face['planes'][plane_idx_in_face]
    wire_dir, pitch_dir, x_plane, bbox_min, bbox_max = plane_geometry(
        pi, planes, wires, points
    )

    sign_to_cathode = -1.0 if x_plane > 0 else 1.0
    x_track = x_plane + sign_to_cathode * drift_offset_mm

    cy = 0.5 * (bbox_min[1] + bbox_max[1])
    cz = 0.5 * (bbox_min[2] + bbox_max[2])

    t_neg, t_pos = chord_through_center(
        (cy, cz), (pitch_dir[1], pitch_dir[2]),
        bbox_min[1], bbox_max[1], bbox_min[2], bbox_max[2],
    )

    p_neg_mm = np.array([x_track, cy + t_neg * pitch_dir[1], cz + t_neg * pitch_dir[2]])
    p_pos_mm = np.array([x_track, cy + t_pos * pitch_dir[1], cz + t_pos * pitch_dir[2]])

    start_cm = (p_neg_mm / 10.0).tolist()
    end_cm = (p_pos_mm / 10.0).tolist()
    length_cm = float(np.linalg.norm(p_pos_mm - p_neg_mm) / 10.0)

    return {
        'start': start_cm,
        'end': end_cm,
        'length_cm': round(length_cm, 4),
        'centroid': ((p_neg_mm + p_pos_mm) / 20.0).tolist(),
        'direction': pitch_dir.tolist(),
        'wire_dir': wire_dir.tolist(),
        'x_plane_mm': x_plane,
        'x_track_mm': x_track,
        'dot_dir_wire': float(np.dot(pitch_dir, wire_dir)),
    }


def build_record(track_info, anode, plane_label, source_label):
    direction = np.array(track_info['direction'])
    dx, dy, dz = direction
    theta = float(np.degrees(np.arccos(np.clip(dz, -1.0, 1.0))))
    phi = float(np.degrees(np.arctan2(dy, dx)))
    return {
        'cluster_id': 0,
        'n_points': 2,
        'source_file': f'generated/{source_label}-anode{anode}-{plane_label}',
        'total_charge': 1.0,
        'centroid': track_info['centroid'],
        'direction': track_info['direction'],
        'length_cm': track_info['length_cm'],
        'start': track_info['start'],
        'end': track_info['end'],
        'linearity': 1.0,
        'theta_deg': round(theta, 4),
        'phi_deg': round(phi, 4),
    }


def main():
    here = Path(__file__).resolve().parent
    default_geom = Path('/nfs/data/1/xqian/toolkit-dev/wire-cell-data/'
                        'protodunevd-wires-larsoft-v3.json.bz2')
    default_out = here / 'tracks'

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--geom', type=Path, default=default_geom,
                    help=f'wires JSON.bz2 (default: {default_geom})')
    ap.add_argument('--outdir', type=Path, default=default_out,
                    help=f'output dir (default: {default_out})')
    ap.add_argument('--drift-offset-mm', type=float, default=DRIFT_OFFSET_MM,
                    help='mm into the drift volume from the wire plane '
                         f'(default: {DRIFT_OFFSET_MM})')
    args = ap.parse_args()

    if not args.geom.is_file():
        raise SystemExit(f'ERROR: geometry file not found: {args.geom}')

    args.outdir.mkdir(parents=True, exist_ok=True)
    anodes, faces, planes, wires, points = load_geom(args.geom)

    if len(anodes) != 8:
        raise SystemExit(
            f'ERROR: {args.geom} has {len(anodes)} anodes; ProtoDUNE-VD '
            f'expects 8. Wrong wires file? Default is '
            f'protodunevd-wires-larsoft-v3.json.bz2.'
        )

    print(f'=== ProtoDUNE-VD: {args.geom} -> {args.outdir} ===')
    # VD: face 0 in each anode's face list (both faces share x; convention).
    for ai in range(8):
        face_idx = anodes[ai]['faces'][0]
        for plane_idx_in_face, plane_label in enumerate(PLANE_LABELS):
            ti = make_track(face_idx, plane_idx_in_face, planes, wires, points,
                            faces, args.drift_offset_mm)
            rec = build_record(ti, ai, plane_label, 'vd')
            out = args.outdir / f'tracks-vd-anode{ai}-{plane_label}.json'
            with open(out, 'w') as f:
                json.dump([rec], f, indent=2)
            print(f'  wrote {out.name}  '
                  f'len={rec["length_cm"]:.2f} cm  '
                  f'x_wire={ti["x_plane_mm"]/10:+.2f} cm  '
                  f'x_track={ti["x_track_mm"]/10:+.2f} cm  '
                  f'dot_with_wire={ti["dot_dir_wire"]:+.2e}')


if __name__ == '__main__':
    main()
