from __future__ import annotations

import csv
import inspect
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

import numpy as np
from optiprofiler.opclasses import Problem


CURRENT_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = CURRENT_DIR / "runtime" / "solar"
METADATA_PATH = RUNTIME_DIR / "metadata" / "problems.json"
PROBINFO_PATH = RUNTIME_DIR / "metadata" / "probinfo.csv"


class SolarExecutionError(RuntimeError):
    pass


def solar_python_collect_info():
    """Return the SOLAR problem metadata rows used by `solar_python_select`."""

    with PROBINFO_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def solar_python_select(options=None):
    """Select SOLAR problems satisfying OptiProfiler-style criteria."""

    if options is None:
        options = {}
    options = dict(options)
    defaults = {
        "ptype": "ubln",
        "mindim": 1,
        "maxdim": math.inf,
        "minb": 0,
        "maxb": math.inf,
        "minlcon": 0,
        "maxlcon": math.inf,
        "minnlcon": 0,
        "maxnlcon": math.inf,
        "mincon": 0,
        "maxcon": math.inf,
        "excludelist": [],
    }
    for key, value in defaults.items():
        options.setdefault(key, value)

    metadata = _load_metadata()
    selected = []
    for problem in metadata:
        if not problem.get("enabled", False):
            continue
        row = _row(problem)
        if row["name"] in options["excludelist"]:
            continue
        if row["ptype"] not in options["ptype"]:
            continue
        if not (options["mindim"] <= row["dim"] <= options["maxdim"]):
            continue
        if not (options["minb"] <= row["mb"] <= options["maxb"]):
            continue
        if not (options["minlcon"] <= row["mlcon"] <= options["maxlcon"]):
            continue
        if not (options["minnlcon"] <= row["mnlcon"] <= options["maxnlcon"]):
            continue
        if not (options["mincon"] <= row["mcon"] <= options["maxcon"]):
            continue
        selected.append(row["name"])
    return selected


def solar_python_load(problem_name):
    """Load one SOLAR problem as an OptiProfiler `Problem`."""

    metadata = _problem_by_name(problem_name)
    if not metadata.get("enabled", False):
        raise ValueError(f"SOLAR problem is disabled: {problem_name}")

    executable = _ensure_executable()
    state = _SolarProblemState(metadata, executable)
    cub = state.cub if metadata["m_constraints"] > 0 else None

    return Problem(
        state.fun,
        np.asarray(metadata["x0"], dtype=float),
        name=metadata["name"],
        xl=_bounds(metadata["xl"], lower=True),
        xu=_bounds(metadata["xu"], lower=False),
        cub=cub,
    )


class _SolarProblemState:
    def __init__(self, metadata, executable):
        self.metadata = metadata
        self.executable = executable
        self._last_x = None
        self._last_eval = None

    def _eval(self, x):
        x = np.asarray(x, dtype=float).reshape(-1)
        if self._last_x is not None and np.array_equal(x, self._last_x):
            return self._last_eval
        result = _run_solar(
            self.executable,
            self.metadata["pb_id"],
            x,
            self.metadata["m_objectives"],
            self.metadata["m_constraints"],
        )
        self._last_x = x.copy()
        self._last_eval = result
        return result

    def fun(self, x):
        return float(self._eval(x)["objectives"][0])

    def cub(self, x):
        if _is_problem_constructor_probe():
            return np.full(self.metadata["m_constraints"], np.nan)
        return np.asarray(self._eval(x)["constraints"], dtype=float)


def _load_metadata():
    with METADATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _problem_by_name(problem_name):
    for problem in _load_metadata():
        if problem["name"] == problem_name:
            return problem
    raise KeyError(f"Unknown SOLAR problem: {problem_name}")


def _row(problem):
    mb = sum(
        value is not None and math.isfinite(float(value))
        for value in problem["xl"] + problem["xu"]
    )
    ptype = "n" if problem["m_constraints"] > 0 else ("b" if mb > 0 else "u")
    return {
        "name": problem["name"],
        "ptype": ptype,
        "dim": int(problem["n"]),
        "mb": int(mb),
        "mlcon": 0,
        "mnlcon": int(problem["m_constraints"]),
        "mcon": int(problem["m_constraints"]),
    }


def _bounds(values, *, lower):
    fallback = -np.inf if lower else np.inf
    return np.asarray([fallback if value is None else value for value in values], dtype=float)


def _ensure_executable():
    configured = os.environ.get("SOLAR_EXECUTABLE")
    executable = Path(configured) if configured else RUNTIME_DIR / "bin" / "solar"
    if executable.exists():
        return executable

    subprocess.run(["make", "-C", str(RUNTIME_DIR / "src")], check=True)
    if not executable.exists():
        raise SolarExecutionError(f"SOLAR executable was not built: {executable}")
    return executable


def _run_solar(executable, problem_id, x, n_objectives, n_constraints, timeout_sec=300.0):
    with tempfile.TemporaryDirectory(prefix="solar-python-") as tmp:
        input_path = Path(tmp) / "x.txt"
        input_path.write_text(_format_point(x), encoding="utf-8")
        cmd = [
            str(executable),
            str(problem_id),
            str(input_path),
            "-seed=0",
            "-fid=1.0",
            "-rep=1",
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        elapsed = time.perf_counter() - started

    if completed.returncode != 0:
        raise SolarExecutionError(
            f"SOLAR failed with return code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    values = _parse_numeric_output(completed.stdout)
    expected = n_objectives + n_constraints
    if len(values) != expected:
        raise SolarExecutionError(
            f"SOLAR returned {len(values)} numeric values, expected {expected}"
        )
    return {
        "objectives": tuple(values[:n_objectives]),
        "constraints": tuple(values[n_objectives:]),
        "elapsed_sec": elapsed,
        "raw_stdout": completed.stdout,
    }


def _parse_numeric_output(stdout):
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return [float(token) for token in line.split()]
        except ValueError:
            continue
    raise SolarExecutionError(f"SOLAR output could not be parsed: {stdout!r}")


def _format_point(x):
    return " ".join(f"{float(value):.17g}" for value in x) + "\n"


def _is_problem_constructor_probe():
    for frame in inspect.stack(context=0):
        if frame.function == "__init__" and frame.filename.endswith("opclasses.py"):
            return True
    return False


solar_collect_info = solar_python_collect_info
solar_select = solar_python_select
solar_load = solar_python_load
