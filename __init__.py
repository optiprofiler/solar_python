from .solar_python_tools import (
    solar_collect_info,
    solar_check_available,
    solar_load,
    solar_python_collect_info,
    solar_python_load,
    solar_python_select,
    solar_select,
    solar_validate_options,
)


def _plugin_select(problem_options, library_options):
    return solar_select(problem_options, library_options=library_options)


def _plugin_load(problem_name, library_options):
    return solar_load(problem_name, library_options=library_options)


def get_problem_library():
    """Return the OptiProfiler problem-library plugin for SOLAR."""

    from optiprofiler import ProblemLibraryPlugin

    return ProblemLibraryPlugin(
        name="solar",
        api_version=1,
        select=_plugin_select,
        load=_plugin_load,
        collect_info=solar_collect_info,
        check_available=solar_check_available,
    )


__version__ = "0.1.0"

__all__ = [
    "get_problem_library",
    "solar_collect_info",
    "solar_check_available",
    "solar_load",
    "solar_python_collect_info",
    "solar_python_load",
    "solar_python_select",
    "solar_select",
    "solar_validate_options",
]
