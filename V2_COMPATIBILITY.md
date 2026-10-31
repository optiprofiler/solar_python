# OptiProfiler 2.0 compatibility

This line is the reviewed SOLAR adapter for OptiProfiler 2.0.0. Provider API
version remains **1**. Upstream problem definitions, selection metadata and the
manual review of upstream updates are unchanged.

The adapter supplies selection and public Problem callbacks. Ordered feature
composition, counters and histories, scores, save/load, and eval_report/2 are
owned by core, not duplicated in adapters. No core-private class is accessed.
Python loaders return the exact public Problem class, not a subclass.

No trusted reference has been promoted for these wrapped instances, so
Problem.reference remains None and profiles keep the empirical default target.
Initial values, history minima, upstream solution vectors and metadata fbest
are not converted into references. A future fact needs raw `fun` and `maxcv`,
one of the two kinds `feasible` or `merit`, and a verifiable source under the
core reference contract.

The distribution version is 0.1.0 and it requires `optiprofiler>=2.0.0`, the
first core with the API-v1 plugin host; there is no upper cap. Neither is on
PyPI until it is released. Stable 1.3.5 is not an API-v1 plugin host, and the
earlier `>=1.4.0` was a placeholder, never a verified compatibility range.

Normal installation acceptance uses the full dependency resolver and pip
check. `--no-deps` or PYTHONPATH overrides do not pass that gate. Uninstall
removes this distribution only; separately managed runtime, cache and user data
remain untouched.

SOLAR retains its reviewed compiled-on-first-use sources and internal oracle
cache. Integer-coordinate rounding is unchanged. Use small validation budgets;
successful execution is not a solver ranking or a convergence assertion.
