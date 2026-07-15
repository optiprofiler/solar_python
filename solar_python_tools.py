from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
import csv
import inspect
import json
import math
import os
from pathlib import Path
import shutil
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


def solar_validate_options(library_options):
    """Validate SOLAR library-specific options.

    SOLAR currently has no library-specific configuration. The function exists
    for direct-call hygiene only; the OptiProfiler plugin intentionally omits
    get_default_options/validate_options so core rejects nonempty
    ``plib_options['solar']`` before benchmark execution.
    """

    if library_options is None:
        return {}
    if not isinstance(library_options, Mapping):
        raise TypeError("SOLAR library options must be a mapping.")
    options = dict(library_options)
    if options:
        raise ValueError(
            "SOLAR does not define library-specific options; pass an empty mapping."
        )
    return {}


def solar_check_available():
    """Raise an informative exception if the SOLAR executable cannot be used."""

    _ensure_executable()


def solar_python_collect_info():
    """
    Return the SOLAR problem information table.

    This is the Python-specific implementation used by the public entry point
    ``solar_collect_info``. Users should normally call ``solar_collect_info``,
    whose name matches the OptiProfiler problem library name ``solar``.

    Returns
    -------
    list of dict
        Rows with the same compact fields used by OptiProfiler custom problem
        libraries: ``name``, ``ptype``, ``dim``, ``mb``, ``mlcon``,
        ``mnlcon``, and ``mcon``.
    """

    with PROBINFO_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def solar_python_select(options=None, library_options=None):
    """
    Select SOLAR problems satisfying OptiProfiler-style criteria.

    This is the Python-specific implementation used by the public entry point
    ``solar_select``. Users should normally call ``solar_select``, whose name
    matches the OptiProfiler problem library name ``solar``.

    Parameters
    ----------
    options : dict, optional
        Selection criteria with the same keys accepted by ``solar_select``.

    Returns
    -------
    list of str
        Names of enabled scalar SOLAR problems satisfying the criteria.
    """

    solar_validate_options(library_options)
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

    enabled_names = {
        problem["name"]
        for problem in _load_metadata()
        if problem.get("enabled", False)
    }
    selected = []
    for row in solar_python_collect_info():
        if row["name"] not in enabled_names:
            continue
        if row["name"] in options["excludelist"]:
            continue
        if row["ptype"] not in options["ptype"]:
            continue
        dim = int(row["dim"])
        mb = int(row["mb"])
        mlcon = int(row["mlcon"])
        mnlcon = int(row["mnlcon"])
        mcon = int(row["mcon"])
        if not (options["mindim"] <= dim <= options["maxdim"]):
            continue
        if not (options["minb"] <= mb <= options["maxb"]):
            continue
        if not (options["minlcon"] <= mlcon <= options["maxlcon"]):
            continue
        if not (options["minnlcon"] <= mnlcon <= options["maxnlcon"]):
            continue
        if not (options["mincon"] <= mcon <= options["maxcon"]):
            continue
        selected.append(row["name"])
    return selected


def solar_python_load(problem_name, library_options=None):
    """
    Convert a SOLAR problem name to an OptiProfiler ``Problem`` instance.

    This is the Python-specific implementation used by the public entry point
    ``solar_load``. Users should normally call ``solar_load``, whose name
    matches the OptiProfiler problem library name ``solar``.

    Parameters
    ----------
    problem_name : str
        Name of an enabled scalar SOLAR problem.

    Returns
    -------
    optiprofiler.Problem
        A ``Problem`` instance whose objective is available through ``fun`` and
        whose nonlinear inequality constraints, when present, are available
        through ``cub``.
    """

    solar_validate_options(library_options)
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
        solar_x = _prepare_solar_input(self.metadata, x)
        if self._last_x is not None and np.array_equal(solar_x, self._last_x):
            return self._last_eval
        result = _run_solar(
            self.executable,
            self.metadata["pb_id"],
            solar_x,
            self.metadata["m_objectives"],
            self.metadata["m_constraints"],
        )
        self._last_x = solar_x.copy()
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
    mb = int(problem.mb)
    return {
        "name": problem.name,
        "ptype": problem.ptype,
        "dim": int(problem.n),
        "mb": mb,
        "mlcon": int(problem.mlcon),
        "mnlcon": int(problem.mnlcon),
        "mcon": int(problem.mcon),
    }


def _bounds(values, *, lower):
    fallback = -np.inf if lower else np.inf
    return np.asarray([fallback if value is None else value for value in values], dtype=float)


def _prepare_solar_input(metadata, x):
    x = np.asarray(x, dtype=float).reshape(-1).copy()
    if x.size != int(metadata["n"]):
        raise SolarExecutionError(
            f"SOLAR input has dimension {x.size}, expected {metadata['n']}"
        )
    input_type = metadata.get("input_type", [])
    lower_bounds = metadata.get("xl", [None] * x.size)
    upper_bounds = metadata.get("xu", [None] * x.size)
    for i, variable_type in enumerate(input_type):
        if variable_type != "I" or not np.isfinite(x[i]):
            continue
        value = math.floor(float(x[i]) + 0.5)
        lower = lower_bounds[i]
        upper = upper_bounds[i]
        if lower is not None and math.isfinite(float(lower)):
            value = max(value, math.ceil(float(lower)))
        if upper is not None and math.isfinite(float(upper)):
            value = min(value, math.floor(float(upper)))
        x[i] = value
    return x


def _ensure_executable():
    configured = os.environ.get("SOLAR_EXECUTABLE")
    if configured:
        executable = Path(configured).expanduser().resolve()
        if executable.is_file():
            return executable
        raise SolarExecutionError(
            f"SOLAR_EXECUTABLE does not point to a file: {executable}"
        )

    executable = _default_executable()
    if executable.exists():
        return executable

    cache_dir = _runtime_cache_dir()
    with _build_lock(cache_dir):
        if executable.exists():
            return executable
        source_dir = cache_dir / "src"
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.copytree(RUNTIME_DIR / "src", source_dir)
        executable.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            _make_command(source_dir),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise SolarExecutionError(
                "Failed to build SOLAR executable: "
                f"{completed.stdout}{completed.stderr}"
            )
    if not executable.exists():
        raise SolarExecutionError(f"SOLAR executable was not built: {executable}")
    return executable


def _default_executable():
    suffix = ".exe" if os.name == "nt" else ""
    source_executable = RUNTIME_DIR / "bin" / f"solar{suffix}"
    if source_executable.is_file():
        return source_executable
    return _runtime_cache_dir() / "bin" / f"solar{suffix}"


def _runtime_cache_dir():
    configured = os.environ.get("SOLAR_CACHE_DIR")
    if configured:
        cache_root = Path(configured).expanduser()
    else:
        cache_root = Path(
            os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        ).expanduser() / "optiprofiler" / "solar"

    try:
        with (RUNTIME_DIR / "manifest.json").open(encoding="utf-8") as handle:
            cache_key = json.load(handle)["upstream"]["commit"][:12]
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        cache_key = "unversioned"
    return cache_root.resolve() / cache_key


def _make_command(source_dir):
    command = ["make", "-C", str(source_dir)]
    if os.name == "nt":
        command.append("EXEEXT=.exe")
        command.append("LIBS=-lm")
    return command


@contextmanager
def _build_lock(cache_dir, timeout_sec=600.0):
    lock_path = cache_dir / ".build.lock.d"
    cache_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_sec
    acquired = False
    while True:
        try:
            lock_path.mkdir()
            acquired = True
            break
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise SolarExecutionError(
                    "Timed out waiting for another process to build SOLAR"
                ) from exc
            time.sleep(0.1)
    try:
        yield
    finally:
        if acquired:
            try:
                lock_path.rmdir()
            except OSError:
                pass


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

    expected = n_objectives + n_constraints
    try:
        values = _parse_numeric_output(completed.stdout)
    except SolarExecutionError as exc:
        if completed.returncode != 0:
            raise SolarExecutionError(
                f"SOLAR failed with return code {completed.returncode}: "
                f"{completed.stderr.strip()}"
            ) from exc
        raise
    if len(values) != expected:
        if completed.returncode != 0:
            raise SolarExecutionError(
                f"SOLAR failed with return code {completed.returncode} and "
                f"returned {len(values)} numeric values, expected {expected}: "
                f"{completed.stderr.strip()}"
            )
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


def solar_collect_info():
    """
    Return the SOLAR problem information table used by `solar_select`.

    This is the public collect-info entry point for the OptiProfiler problem
    library named ``solar``. The returned rows are read from
    ``runtime/solar/metadata/probinfo.csv``. This file is generated by
    ``scripts/collect_info.py`` by loading each enabled SOLAR problem through
    ``solar_load`` and recording the resulting OptiProfiler ``Problem`` fields.

    Returns
    -------
    list of dict
        Problem information rows with keys ``name``, ``ptype``, ``dim``,
        ``mb``, ``mlcon``, ``mnlcon``, and ``mcon``.

    See Also
    --------
    solar_select : Select SOLAR problems using the generated table.
    solar_load : Load one SOLAR problem as an OptiProfiler ``Problem``.

    Examples
    --------
    .. code-block:: python

        from solar_tools import solar_collect_info

        rows = solar_collect_info()
        print(rows[0]["name"])
    """

    return solar_python_collect_info()


def solar_select(options=None, library_options=None):
    """
    Select SOLAR problems satisfying OptiProfiler-style criteria.

    SOLAR is a black-box solar-plant simulation benchmark. More details about
    the upstream benchmark can be found at
    ``https://github.com/bbopt/solar``.

    Parameters
    ----------
    options : dict, optional
        Selection criteria. Supported keys:

        - ``ptype`` : str
            Problem types to select. Use any combination of ``'u'``
            (unconstrained), ``'b'`` (bound constrained), ``'l'`` (linearly
            constrained), and ``'n'`` (nonlinearly constrained). Default is
            ``'ubln'``.
        - ``mindim`` : int
            Minimum dimension. Default is ``1``.
        - ``maxdim`` : int or float
            Maximum dimension. Default is ``math.inf``.
        - ``minb`` : int
            Minimum number of bound constraints. Default is ``0``.
        - ``maxb`` : int or float
            Maximum number of bound constraints. Default is ``math.inf``.
        - ``minlcon`` : int
            Minimum number of linear constraints. Default is ``0``.
        - ``maxlcon`` : int or float
            Maximum number of linear constraints. Default is ``math.inf``.
        - ``minnlcon`` : int
            Minimum number of nonlinear constraints. Default is ``0``.
        - ``maxnlcon`` : int or float
            Maximum number of nonlinear constraints. Default is ``math.inf``.
        - ``mincon`` : int
            Minimum total number of linear and nonlinear constraints. Default
            is ``0``.
        - ``maxcon`` : int or float
            Maximum total number of linear and nonlinear constraints. Default
            is ``math.inf``.
        - ``excludelist`` : list of str
            Problem names to exclude. Default is ``[]``.

    Returns
    -------
    list of str
        Names of enabled scalar SOLAR problems satisfying the criteria.

    Notes
    -----
    SOLAR 8 and 9 are multiobjective and are not returned by this first scalar
    OptiProfiler integration. SOLAR 11 is disabled because the current upstream
    snapshot returns an empty output at the documented initial point.

    Some SOLAR instances contain integer or categorical variables. Before
    calling the SOLAR executable, this wrapper rounds every ``I`` coordinate to
    the nearest integer and clips it to the recorded integer bounds.

    See Also
    --------
    solar_load : Load one selected SOLAR problem.
    solar_collect_info : Return the problem information table used here.

    Examples
    --------
    .. code-block:: python

        from solar_tools import solar_select

        names = solar_select({"ptype": "n", "maxdim": 20})
    """

    return solar_python_select(options, library_options=library_options)


def solar_load(problem_name, library_options=None):
    """
    Convert a SOLAR problem name to an OptiProfiler ``Problem`` instance.

    Parameters
    ----------
    problem_name : str
        Name of an enabled scalar SOLAR problem. Use ``solar_select`` to obtain
        names satisfying dimension and constraint criteria.

    Returns
    -------
    optiprofiler.Problem
        A ``Problem`` instance for the named SOLAR problem. The instance
        provides the objective through ``fun`` and, when present, nonlinear
        inequality constraints through ``cub``. SOLAR does not provide
        derivatives in this wrapper.

    Notes
    -----
    The SOLAR C++ executable is built on first use if it is missing. This first
    build can take noticeably longer than an ordinary load call.

    SOLAR returns objective and constraint values from one executable call. The
    wrapper may cache that raw executable result inside one loaded problem
    object, but it does not call OptiProfiler-visible ``cub`` from ``fun`` or
    ``fun`` from ``cub``. This preserves OptiProfiler's separate evaluation
    histories.

    Some SOLAR instances contain integer or categorical variables. The wrapper
    rounds every ``I`` coordinate before calling the SOLAR executable, as
    described in the repository README.

    See Also
    --------
    solar_select : Select SOLAR problem names by criteria.
    solar_collect_info : Return the generated SOLAR problem information table.

    Examples
    --------
    .. code-block:: python

        from solar_tools import solar_load

        problem = solar_load("SOLAR6_MINCOST_TS")
        print(problem.fun(problem.x0))
    """

    return solar_python_load(problem_name, library_options=library_options)
