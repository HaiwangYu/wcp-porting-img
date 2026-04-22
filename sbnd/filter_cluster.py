#!/usr/bin/env python3
"""
Filter cluster JSON files by cluster_id while preserving metadata.

Example:
    python filter_cluster.py sbnd/data-sep/2/2-img-apa1.json 3 7 \\
        --output sbnd/data-sep/2/2-img-apa1-cid3-7.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

FIELDS_TO_FILTER = ("cluster_id", "x", "y", "z", "q")


def parse_cluster_ids(values: Iterable[str]) -> List[int]:
    """Return unique cluster IDs in the order provided."""
    seen = set()
    result: List[int] = []
    for raw in values:
        cid = int(raw)
        if cid not in seen:
            result.append(cid)
            seen.add(cid)
    return result


def build_output_path(input_path: Path, cluster_ids: List[int]) -> Path:
    cid_suffix = "-".join(str(cid) for cid in cluster_ids)
    return input_path.with_name(f"{input_path.stem}-cid{cid_suffix}{input_path.suffix}")


def validate_lengths(data: dict) -> None:
    base = len(data.get("cluster_id", []))
    for field in FIELDS_TO_FILTER:
        if field not in data:
            raise KeyError(f"Missing '{field}' in input JSON")
        if not isinstance(data[field], list):
            raise TypeError(f"Field '{field}' is expected to be a list")
        if len(data[field]) != base:
            raise ValueError(f"Length mismatch for '{field}': {len(data[field])} vs {base} cluster_id entries")


def filter_data(data: dict, cluster_ids: List[int]) -> dict:
    validate_lengths(data)
    keep = set(cluster_ids)
    mask = [cid in keep for cid in data["cluster_id"]]

    filtered = {}
    for key, value in data.items():
        if key in FIELDS_TO_FILTER:
            filtered[key] = [entry for entry, flag in zip(value, mask) if flag]
            print(f"Filtered field '{key}': {len(value)} -> {len(filtered[key])} entries")
        else:
            filtered[key] = value

    if not filtered["cluster_id"]:
        raise ValueError("No entries matched the requested cluster_id values")

    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter cluster JSON files on cluster_id while keeping metadata intact.")
    parser.add_argument("input", type=Path, help="Input JSON file (e.g. data-sep/2/2-img-apa1.json)")
    parser.add_argument("cluster_id", nargs="+", help="One or more cluster_id values to keep")
    parser.add_argument("-o", "--output", type=Path, help="Optional output path; defaults to adding -cid<ids> next to input")
    args = parser.parse_args()

    cluster_ids = parse_cluster_ids(args.cluster_id)
    input_path: Path = args.input
    output_path: Path = args.output or build_output_path(input_path, cluster_ids)

    with input_path.open() as fin:
        data = json.load(fin)

    filtered = filter_data(data, cluster_ids)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fout:
        json.dump(filtered, fout, indent=4)

    print(f"Wrote filtered file to {output_path}")


if __name__ == "__main__":
    main()
