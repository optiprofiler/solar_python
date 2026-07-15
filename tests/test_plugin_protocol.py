from __future__ import annotations

from importlib import metadata
import multiprocessing
import unittest

IMPORT_ERROR = None
try:
    import optiprofiler_solar
    from optiprofiler.problem_libraries import (
        PROBLEM_LIBRARY_ENTRY_POINT_GROUP,
        ProblemLibraryRef,
        _resolve_problem_library_options,
        load_problem_library,
    )
except Exception as exc:  # pragma: no cover - exercised before editable install.
    IMPORT_ERROR = exc


def _spawn_select_solar(problem_options, library_options):
    import optiprofiler_solar

    return optiprofiler_solar.get_problem_library().select(
        problem_options,
        library_options,
    )


@unittest.skipIf(IMPORT_ERROR is not None, f"Plugin package is not installed: {IMPORT_ERROR}")
class SolarPluginProtocolTests(unittest.TestCase):
    def test_entry_point_metadata_is_installed(self):
        entry_points = metadata.entry_points()
        if hasattr(entry_points, "select"):
            selected = entry_points.select(group=PROBLEM_LIBRARY_ENTRY_POINT_GROUP)
        else:
            selected = entry_points.get(PROBLEM_LIBRARY_ENTRY_POINT_GROUP, [])
        values = {entry_point.name: entry_point.value for entry_point in selected}
        self.assertEqual(values.get("solar"), "optiprofiler_solar:get_problem_library")

    def test_factory_returns_api_v1_plugin_with_empty_options_contract(self):
        plugin = optiprofiler_solar.get_problem_library()
        self.assertEqual(plugin.name, "solar")
        self.assertEqual(plugin.api_version, 1)
        self.assertIsNotNone(plugin.check_available)
        self.assertIsNone(plugin.get_default_options)
        self.assertIsNone(plugin.validate_options)
        self.assertEqual(_resolve_problem_library_options(plugin), {})
        with self.assertRaises(ValueError):
            _resolve_problem_library_options(plugin, {"unknown": 1})

    def test_entry_point_reference_loads_plugin(self):
        reference = ProblemLibraryRef(
            "solar",
            "entry_point",
            "optiprofiler_solar:get_problem_library",
            distribution="optiprofiler-solar",
        )
        plugin = load_problem_library(reference)
        selected = plugin.select({"ptype": "n", "maxdim": 10}, {})
        self.assertIn("SOLAR1_MAXNRG_H1", selected)

    def test_empty_options_are_isolated_between_select_and_load(self):
        selected = optiprofiler_solar.solar_select(
            {"ptype": "b", "maxdim": 5},
            library_options={},
        )
        self.assertEqual(selected, ["SOLAR10_MINCOST_UNCONSTRAINED"])
        problem = optiprofiler_solar.solar_load(selected[0], library_options={})
        self.assertEqual(problem.name, "SOLAR10_MINCOST_UNCONSTRAINED")
        with self.assertRaises(ValueError):
            optiprofiler_solar.solar_select({}, library_options={"unknown": 1})

    def test_api_v1_callbacks_work_in_spawned_process(self):
        with multiprocessing.get_context("spawn").Pool(1) as pool:
            selected = pool.apply(
                _spawn_select_solar,
                ({"ptype": "b", "maxdim": 5}, {}),
            )
        self.assertEqual(selected, ["SOLAR10_MINCOST_UNCONSTRAINED"])


if __name__ == "__main__":
    unittest.main()
