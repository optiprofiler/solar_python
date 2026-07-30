#!/usr/bin/env python3
"""Evaluate a reproducible, bounded SOLAR sample with at most two workers."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import date
import math
import os
from pathlib import Path
import random
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
LOCAL_CORE = ROOT.parents[1] / "optiprofiler" / "python"
if LOCAL_CORE.is_dir():
    sys.path.insert(0, str(LOCAL_CORE))

FAST_PROBLEMS = (
    "SOLAR1_MAXNRG_H1",
    "SOLAR2_MINSURF_H1",
    "SOLAR6_MINCOST_TS",
    "SOLAR7_MAXEFF_RE",
    "SOLAR10_MINCOST_UNCONSTRAINED",
)


def _evaluate(name: str) -> tuple[str, float, float]:
    try:
        from optiprofiler_solar import solar_load
    except ModuleNotFoundError:
        # Source-checkout fallback; installed CI uses the entry-point package.
        from solar_python import solar_load

    started = time.monotonic()
    problem = solar_load(name)
    objective = float(problem.fun(problem.x0))
    cub = np.asarray(problem.cub(problem.x0), dtype=float)
    ceq = np.asarray(problem.ceq(problem.x0), dtype=float)
    values = np.concatenate(([objective], cub.reshape(-1), ceq.reshape(-1)))
    if not all(math.isfinite(value) or math.isnan(value) for value in values):
        raise RuntimeError(f"{name} returned an invalid value at x0: {values}")
    return name, objective, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.max_workers <= 2:
        raise SystemExit("SOLAR random smoke permits one or two workers only.")
    if not 1 <= args.count <= len(FAST_PROBLEMS):
        raise SystemExit(f"count must be between 1 and {len(FAST_PROBLEMS)}")

    seed = int(os.environ.get("OP_RANDOM_SEED", date.today().strftime("%Y%m%d")))
    chosen = random.Random(seed).sample(list(FAST_PROBLEMS), args.count)
    print(f"SOLAR Python random sample seed={seed}: {chosen}", flush=True)
    if args.max_workers == 1:
        results = map(_evaluate, chosen)
        for name, objective, elapsed in results:
            print(f"{name}: f(x0)={objective:.16g}, elapsed={elapsed:.3f}s", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            for name, objective, elapsed in executor.map(_evaluate, chosen):
                print(f"{name}: f(x0)={objective:.16g}, elapsed={elapsed:.3f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
