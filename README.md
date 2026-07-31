# SOLAR Python Adapter

Python OptiProfiler wrapper for the SOLAR black-box optimization benchmark.

This repository carries a slim SOLAR runtime under `runtime/solar/`. It keeps
the executable source, license, upstream manifest, and OptiProfiler metadata,
but intentionally excludes upstream SOLAR's large `tests/` directory.

The repository should stay lightweight. Commit the runtime source, metadata,
license, and provenance files; do not commit upstream `.git`, upstream `tests/`,
`runtime/solar/bin/solar`, `runtime/solar/bin/solar.exe`, or
`runtime/solar/src/*.o`.

## Package and Plugin

This package definition is a development build for the API-v1 protocol. The
corresponding OptiProfiler release and this plugin distribution have not been
published yet. The protocol-enabled OptiProfiler development branch currently
reports version `1.3.4`; the published `v1.3.4` tag predates the plugin protocol,
so use the checked-out `python` branch until a protocol-enabled core is released.
The `0.1.0` package value is build metadata, not a release announcement.

The Python distribution name is `optiprofiler-solar`. It installs the adapter
package `optiprofiler_solar` and registers the problem-library entry point

```toml
[project.entry-points."optiprofiler.problem_libraries"]
solar = "optiprofiler_solar:get_problem_library"
```

SOLAR currently has no library-specific configuration. The plugin therefore
uses an empty options mapping: `benchmark(..., plib_options={"solar": {}})` is
valid, while nonempty SOLAR-specific options are rejected by OptiProfiler before
the benchmark starts.

For local development against a checked-out OptiProfiler core:

```bash
python -m pip install -e /path/to/optiprofiler
python -m pip install -e . --no-build-isolation
```

## Build Runtime

```bash
make -C runtime/solar/src
```

For a source checkout, this command generates `runtime/solar/bin/solar` (or
`solar.exe` on Windows), and that file is ignored by git. The Python wrapper
uses a source-checkout binary when present. Otherwise, including after a wheel
installation, it copies the packaged source to a versioned user cache and
builds there; it never writes generated files into `site-packages`. Set
`SOLAR_CACHE_DIR` to choose the cache root or `SOLAR_EXECUTABLE` to use an
existing binary. First build is protected by a local directory lock, so
parallel OptiProfiler workers do not compile and link the same runtime at the
same time.

The build requires `make` and a C++ compiler compatible with upstream SOLAR.
On Linux and macOS this is usually the system `make` plus `g++`/Clang. On
Windows, use MSYS2/MinGW or an equivalent environment that exposes `make` and
`g++` on `PATH`.

## Automation

`scripts/collect_info.py` regenerates
`runtime/solar/metadata/probinfo.csv` by loading each enabled SOLAR problem
through `solar_load` and reading the resulting OptiProfiler `Problem` fields.
The vendored metadata is still needed to construct each problem, but the
selection index is derived from the wrapper contract that users actually call.
The CI workflow checks that this generated file is committed, runs wrapper
tests, and verifies that local build artifacts stay ignored.

`Prepare SOLAR Runtime Candidate` is a manual review tool. It requires an exact
adapter revision and exact upstream SOLAR commit, exports a slim runtime, runs
the wrapper tests, and uploads a candidate archive. It never commits the
candidate. `Collect Info` is also manual and uploads regenerated metadata
without changing the repository.

The daily random smoke runs at 07:00 Beijing time. It records a reproducible
seed, samples two metadata-reviewed fast problems, evaluates the complete
wrapper at each initial point, and uses at most two worker processes.

## Usage

```python
from optiprofiler_solar import solar_load, solar_select

names = solar_select({"ptype": "n", "maxdim": 20})
problem = solar_load(names[0])
print(problem.fun(problem.x0))
```

The installed plugin is discoverable without compiling or importing the SOLAR
runtime:

```python
from optiprofiler import list_problem_libraries

assert "solar" in list_problem_libraries()
```

Select it with `benchmark(..., plibs=["solar"])`; an installed plugin needs no
filesystem path.

## Update and Uninstall

For the unpublished development distribution, update the compatible feature
branch and reinstall it explicitly:

```bash
git pull --ff-only
python -m pip install -e . --no-build-isolation
```

The OptiProfiler core repository records its tested adapter commit in
`problem_libraries.lock`. Updating the adapter source and updating the compiled
runtime cache are separate operations: the wrapper selects a versioned cache
directory from the packaged runtime manifest and rebuilds there when needed.

Remove the adapter distribution with:

```bash
python -m pip uninstall optiprofiler-solar
```

This removes the adapter, entry point, and the slim runtime source installed
inside that distribution. It preserves `SOLAR_CACHE_DIR`, the default
`~/.cache/optiprofiler/solar/<commit>` cache, any executable selected through
`SOLAR_EXECUTABLE`, and user benchmark output. Removing the OptiProfiler core
also leaves this independently installed adapter and its cache in place; the
adapter becomes usable again after a compatible core is installed.

## Public API

The public problem-library name is `solar`. User-facing code should normally
use the following entry points:

- `solar_load(problem_name)` loads one enabled scalar SOLAR problem as an
  OptiProfiler `Problem` instance.
- `solar_select(options)` returns enabled scalar SOLAR problem names satisfying
  OptiProfiler-style selection criteria.
- `solar_collect_info()` returns the committed problem-information table used
  by `solar_select`.

This repository also keeps `solar_python_load`, `solar_python_select`, and
`solar_python_collect_info` as Python-specific implementation and compatibility
entry points. They are not the preferred names for user code.

In OptiProfiler, use this adapter as the problem library `solar`, for example
`benchmark(solvers, plibs=["solar"], ...)`. The GitHub source repository name is
language-specific, but the public problem-library name is `solar`.

SOLAR 8 and 9 are multiobjective and are not returned by the first scalar
OptiProfiler selector. SOLAR 11 is disabled for now because upstream SOLAR
v1.0.8 returns an empty output at the documented initial point.

## License and Provenance

The Python adapter, plugin integration, generated metadata, and wrapper
documentation are licensed under the [BSD 3-Clause License](LICENSE). The
distribution also contains a slim upstream SOLAR source subset, so its complete
license metadata is recorded conservatively as
`BSD-3-Clause AND LGPL-2.1-only AND LGPL-3.0-or-later`.

The runtime manifest records the exact upstream SOLAR commit and the file-level
license mapping. All 49 distributed C++ source and header files retain their
explicit LGPL-3.0-or-later notices. The unheaded upstream makefile and README
are recorded as LGPL-2.1-only based on the upstream repository license. The
original LGPL-2.1 text is preserved unchanged, and the official GPLv3 and
LGPLv3 texts are included for the LGPLv3-covered source files. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the complete component
boundaries and paths.

## Runtime Expectations

SOLAR problems call an external C++ solar-plant simulator. Some instances are
substantially more expensive than ordinary algebraic test problems: a single
objective or constraint evaluation can keep one CPU core busy for many seconds
or longer. In local OptiProfiler tests, `SOLAR5_MAXCOMP_HTF1` has been the
clearest slow case. `SOLAR3_MINCOST_C1` and `SOLAR4_MINCOST_C2` can also be
noticeably slower than the small storage/receiver instances, depending on the
trial point and solver behavior.

Solver choice can multiply this cost. Finite-difference methods and
model-based DFO solvers may call the SOLAR executable many times per iteration
or poll step, so a run may appear quiet while the simulator is still using CPU.
For smoke tests, start with `SOLAR6_MINCOST_TS` or
`SOLAR10_MINCOST_UNCONSTRAINED`, use `n_jobs=1`, and keep
`max_eval_factor` small.

## Integer Variables

Several scalar SOLAR instances include integer or categorical variables. Before
calling the SOLAR executable, this wrapper rounds every `I` coordinate to the
nearest integer and clips it to the integer bounds recorded in the metadata.
This avoids upstream SOLAR rejecting noninteger trial points generated by
continuous solvers.

This is a wrapper-level mixed-integer handling rule, not a claim that those
instances are native continuous problems. For a strictly continuous DFO
benchmark, use the pure-continuous SOLAR instances, currently SOLAR 6 and
SOLAR 10, or report the rounding policy explicitly.

## Evaluation Accounting

SOLAR returns objective and constraint values from one executable call. This
wrapper may cache that raw executable result inside one loaded problem object,
but it does not call OptiProfiler-visible `cub` from `fun`, or `fun` from
`cub`. This preserves OptiProfiler's separate objective and constraint
evaluation histories.

SOLAR may return a nonzero process status for a simulation point while still
printing a complete numeric output vector, usually with `1e20` penalty values.
The wrapper treats a complete numeric vector as the SOLAR evaluation result and
raises an execution error only when the process fails without a complete output
vector.
