from pathlib import Path
import math
import multiprocessing as mp
import shutil
import sys
import unittest
import numpy as np

op_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(op_root / "optiprofiler" / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_python import solar_load, solar_python_load, solar_python_select, solar_select


def _parallel_load_and_eval(problem_name):
    problem = solar_python_load(problem_name)
    return problem.name, problem.n, math.isfinite(problem.fun(problem.x0))


class SolarPythonTests(unittest.TestCase):
    def test_select(self):
        names = solar_python_select({"ptype": "n", "maxdim": 10})
        self.assertIn("SOLAR1_MAXNRG_H1", names)
        self.assertIn("SOLAR6_MINCOST_TS", names)
        self.assertIn("SOLAR7_MAXEFF_RE", names)
        self.assertNotIn("SOLAR11_MINCOST_CH", names)
        self.assertEqual(names, solar_select({"ptype": "n", "maxdim": 10}))

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

    def test_parallel_cold_build_is_locked(self):
        runtime_dir = Path(__file__).resolve().parents[1] / "runtime" / "solar"
        shutil.rmtree(runtime_dir / "bin", ignore_errors=True)
        for object_file in (runtime_dir / "src").glob("*.o"):
            object_file.unlink()
        lock_file = runtime_dir / ".build.lock"
        if lock_file.exists():
            lock_file.unlink()

        problem_names = [
            "SOLAR1_MAXNRG_H1",
            "SOLAR2_MINSURF_H1",
            "SOLAR3_MINCOST_C1",
            "SOLAR4_MINCOST_C2",
        ]
        with mp.get_context("spawn").Pool(4) as pool:
            results = pool.map(_parallel_load_and_eval, problem_names)

        self.assertTrue((runtime_dir / "bin" / "solar").exists())
        self.assertEqual([name for name, _, _ in results], problem_names)
        self.assertTrue(all(is_finite for _, _, is_finite in results))


if __name__ == "__main__":
    unittest.main()
