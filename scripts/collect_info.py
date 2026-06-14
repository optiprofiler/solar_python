#!/usr/bin/env python3
"""Regenerate SOLAR Python probinfo from the OptiProfiler wrapper."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime/solar/metadata/probinfo.csv"),
    )
    parser.add_argument(
        "--optiprofiler-src",
        type=Path,
        default=None,
        help="Optional path containing the optiprofiler Python package.",
    )
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parents[1]
    if args.optiprofiler_src is not None:
        sys.path.insert(0, str(args.optiprofiler_src.resolve()))
    local_op_src = repo_dir.parents[1] / "optiprofiler" / "python"
    if local_op_src.exists():
        sys.path.insert(0, str(local_op_src))
    sys.path.insert(0, str(repo_dir))

    from solar_python_tools import _load_metadata, _row, solar_python_load

    rows = []
    for metadata in _load_metadata():
        if not metadata.get("enabled", False):
            continue
        rows.append(_row(solar_python_load(metadata["name"])))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["name", "ptype", "dim", "mb", "mlcon", "mnlcon", "mcon"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {args.output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
