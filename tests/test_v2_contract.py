"""Installed-provider checks against OptiProfiler 2.0.

Set OP_TEST_V2=1 in an environment with core 2.0 and the runtime. Native provider
validation belongs on a supported test host, not in a source-only lint job.
"""
import os
import unittest
import numpy as np
from optiprofiler import Feature, FeaturedProblem, Problem


@unittest.skipUnless(os.environ.get("OP_TEST_V2") == "1", "Requires an OptiProfiler 2.0 environment")
class V2ContractTests(unittest.TestCase):
    def test_unknown_reference_and_core_owned_recording(self):
        from optiprofiler_solar import solar_load as load
        for specification in ("plain", "noisy+permuted"):
            with self.subTest(feature=specification):
                problem = load("SOLAR10_MINCOST_UNCONSTRAINED")
                self.assertIs(type(problem), Problem)
                self.assertIsNone(problem.reference)
                trial = FeaturedProblem(problem, Feature(specification), 5, 19)
                self.assertIsNone(trial.reference)
                before = (trial.n_eval_fun, trial.n_eval_cub, trial.n_eval_ceq)
                self.assertTrue(np.isfinite(trial.fun(trial.x0)))
                self.assertEqual(trial.n_eval_fun, before[0] + 1)
                self.assertEqual((trial.n_eval_cub, trial.n_eval_ceq), before[1:])
                self.assertEqual(len(trial.fun_hist), trial.n_eval_fun)


if __name__ == "__main__":
    unittest.main()
