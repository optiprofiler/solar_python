#!/usr/bin/env python3
"""Regenerate SOLAR Python probinfo from runtime metadata."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def finite_count(values):
    return sum(value is not None and math.isfinite(float(value)) for value in values)


def row(problem):
    mb = finite_count(problem["xl"]) + finite_count(problem["xu"])
    ptype = "n" if int(problem["m_constraints"]) > 0 else ("b" if mb > 0 else "u")
    return {
        "name": problem["name"],
        "ptype": ptype,
        "dim": int(problem["n"]),
        "mb": int(mb),
        "mlcon": 0,
        "mnlcon": int(problem["m_constraints"]),
        "mcon": int(problem["m_constraints"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("runtime/solar/metadata/problems.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime/solar/metadata/probinfo.csv"),
    )
    args = parser.parse_args()

    problems = json.loads(args.metadata.read_text(encoding="utf-8"))
    rows = [row(problem) for problem in problems]

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
