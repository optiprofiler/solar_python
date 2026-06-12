# SOLAR Python Adapter

Python OptiProfiler wrapper for the SOLAR black-box optimization benchmark.

This repository carries a slim SOLAR runtime under `runtime/solar/`. It keeps
the executable source, license, upstream manifest, and OptiProfiler metadata,
but intentionally excludes upstream SOLAR's large `tests/` directory.

The repository should stay lightweight. Commit the runtime source, metadata,
license, and provenance files; do not commit upstream `.git`, upstream `tests/`,
`runtime/solar/bin/solar`, or `runtime/solar/src/*.o`.

## Build Runtime

```bash
make -C runtime/solar/src
```

The binary is generated at `runtime/solar/bin/solar` and is ignored by git.

## Usage

```python
from solar_python import solar_load, solar_select

names = solar_select({"ptype": "n", "maxdim": 20})
problem = solar_load(names[0])
print(problem.fun(problem.x0))
```

SOLAR 8 and 9 are multiobjective and are not returned by the first scalar
OptiProfiler selector. SOLAR 11 is disabled for now because upstream SOLAR
v1.0.8 returns an empty output at the documented initial point.

## Evaluation Accounting

SOLAR returns objective and constraint values from one executable call. This
wrapper may cache that raw executable result inside one loaded problem object,
but it does not call OptiProfiler-visible `cub` from `fun`, or `fun` from
`cub`. This preserves OptiProfiler's separate objective and constraint
evaluation histories.
