from pathlib import Path
import math
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
import unittest
import numpy as np

op_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(op_root / "optiprofiler" / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_python import (
    solar_collect_info,
    solar_load,
    solar_python_load,
    solar_python_select,
    solar_select,
)
from solar_python import solar_python_tools


def _parallel_load_and_eval(problem_name):
    problem = solar_python_load(problem_name)
    return problem.name, problem.n, math.isfinite(problem.fun(problem.x0))


def _solar_executable_path(runtime_dir):
    suffix = ".exe" if os.name == "nt" else ""
    return runtime_dir / "bin" / f"solar{suffix}"


class SolarPythonTests(unittest.TestCase):
    def test_select(self):
        names = solar_python_select({"ptype": "n", "maxdim": 10})
        self.assertIn("SOLAR1_MAXNRG_H1", names)
        self.assertIn("SOLAR6_MINCOST_TS", names)
        self.assertIn("SOLAR7_MAXEFF_RE", names)
        self.assertNotIn("SOLAR11_MINCOST_CH", names)
        self.assertEqual(names, solar_select({"ptype": "n", "maxdim": 10}))

    def test_select_enabled_scalar_problem_set(self):
        names = solar_python_select(
            {
                "ptype": "bn",
                "maxdim": 100,
                "maxb": 100,
                "maxnlcon": 100,
                "maxcon": 100,
            }
        )
        self.assertEqual(
            names,
            [
                "SOLAR1_MAXNRG_H1",
                "SOLAR2_MINSURF_H1",
                "SOLAR3_MINCOST_C1",
                "SOLAR4_MINCOST_C2",
                "SOLAR5_MAXCOMP_HTF1",
                "SOLAR6_MINCOST_TS",
                "SOLAR7_MAXEFF_RE",
                "SOLAR10_MINCOST_UNCONSTRAINED",
            ],
        )
        self.assertNotIn("SOLAR8_MAXHF_MINCOST", names)
        self.assertNotIn("SOLAR9_MAXNRG_MINPAR", names)

    def test_collect_info_matches_loaded_problem_contract(self):
        rows = solar_collect_info()
        names = [row["name"] for row in rows]
        self.assertEqual(
            names,
            [
                "SOLAR1_MAXNRG_H1",
                "SOLAR2_MINSURF_H1",
                "SOLAR3_MINCOST_C1",
                "SOLAR4_MINCOST_C2",
                "SOLAR5_MAXCOMP_HTF1",
                "SOLAR6_MINCOST_TS",
                "SOLAR7_MAXEFF_RE",
                "SOLAR10_MINCOST_UNCONSTRAINED",
            ],
        )
        self.assertNotIn("SOLAR8_MAXHF_MINCOST", names)
        self.assertNotIn("SOLAR9_MAXNRG_MINPAR", names)
        self.assertNotIn("SOLAR11_MINCOST_CH", names)

        for row in rows:
            problem = solar_python_load(row["name"])
            self.assertEqual(row["ptype"], problem.ptype)
            self.assertEqual(int(row["dim"]), problem.n)
            self.assertEqual(int(row["mb"]), problem.mb)
            self.assertEqual(int(row["mlcon"]), problem.mlcon)
            self.assertEqual(int(row["mnlcon"]), problem.mnlcon)
            self.assertEqual(int(row["mcon"]), problem.mcon)

    def test_load_and_evaluate_fast_problem(self):
        problem = solar_python_load("SOLAR1_MAXNRG_H1")
        self.assertEqual(problem.name, "SOLAR1_MAXNRG_H1")
        self.assertEqual(problem.n, 9)
        self.assertEqual(problem.m_nonlinear_ub, 5)
        self.assertAlmostEqual(problem.fun(problem.x0), -122505.5978)
        cubx = problem.cub(problem.x0)
        self.assertEqual(cubx.size, 5)
        self.assertFalse(any(math.isnan(float(value)) for value in cubx))
        self.assertEqual(solar_load("SOLAR10_MINCOST_UNCONSTRAINED").n, 5)

    def test_integer_variables_are_projected_before_solar_call(self):
        problem = solar_python_load("SOLAR1_MAXNRG_H1")
        x = np.asarray(problem.x0, dtype=float).copy()
        x[5] = 250.5
        self.assertTrue(math.isfinite(problem.fun(x)))
        self.assertFalse(any(math.isnan(float(value)) for value in problem.cub(x)))

    def test_solar_penalty_output_with_nonzero_return_code_is_usable(self):
        problem = solar_python_load("SOLAR1_MAXNRG_H1")
        x = np.array([
            11.5151099,
            11.7130879,
            152.111131,
            10.8030550,
            10.8979273,
            250.610792,
            46.2980097,
            0.0,
            6.24313876,
        ])
        self.assertEqual(problem.fun(x), 1e20)
        cubx = problem.cub(x)
        self.assertEqual(cubx.size, 5)
        self.assertFalse(any(math.isnan(float(value)) for value in cubx))
        self.assertTrue(np.any(cubx == 1e20))

    def test_parallel_cold_build_is_locked(self):
        runtime_dir = Path(__file__).resolve().parents[1] / "runtime" / "solar"
        shutil.rmtree(runtime_dir / "bin", ignore_errors=True)
        for object_file in (runtime_dir / "src").glob("*.o"):
            object_file.unlink()
        problem_names = [
            "SOLAR1_MAXNRG_H1",
            "SOLAR6_MINCOST_TS",
            "SOLAR7_MAXEFF_RE",
            "SOLAR10_MINCOST_UNCONSTRAINED",
        ]
        previous_cache = os.environ.get("SOLAR_CACHE_DIR")
        try:
            with tempfile.TemporaryDirectory(prefix="solar-build-test-") as tmp:
                os.environ["SOLAR_CACHE_DIR"] = tmp
                with mp.get_context("spawn").Pool(4) as pool:
                    results = pool.map(_parallel_load_and_eval, problem_names)

                executable = solar_python_tools._runtime_cache_dir() / "bin" / (
                    "solar.exe" if os.name == "nt" else "solar"
                )
                self.assertTrue(executable.exists())
                self.assertEqual([name for name, _, _ in results], problem_names)
                self.assertTrue(all(is_finite for _, _, is_finite in results))
                self.assertFalse(any((runtime_dir / "src").glob("*.o")))
        finally:
            if previous_cache is None:
                os.environ.pop("SOLAR_CACHE_DIR", None)
            else:
                os.environ["SOLAR_CACHE_DIR"] = previous_cache


if __name__ == "__main__":
    unittest.main()
