"""Public SOLAR problem-library entry points.

This module exposes the names that OptiProfiler users should import directly:
``solar_load``, ``solar_select``, and ``solar_collect_info``.  The
language-specific implementation lives in ``solar_python_tools`` so that this
repository can keep compatibility wrappers without changing the public problem
library name, which is simply ``solar``.
"""

try:
    from .solar_python_tools import solar_collect_info, solar_load, solar_select
except ImportError:
    from solar_python_tools import solar_collect_info, solar_load, solar_select

__all__ = ["solar_collect_info", "solar_load", "solar_select"]
