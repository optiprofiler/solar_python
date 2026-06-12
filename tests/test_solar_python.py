from pathlib import Path
import math
import sys
import unittest

op_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(op_root / "optiprofiler" / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_python import solar_load, solar_python_load, solar_python_select, solar_select


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


if __name__ == "__main__":
    unittest.main()
