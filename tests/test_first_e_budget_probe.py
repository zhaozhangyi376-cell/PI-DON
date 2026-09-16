import unittest

from project_paths import configure
configure()

import server_first_e_budget_probe as probe


class FirstEBudgetProbeTests(unittest.TestCase):
    def test_trace_crossing_uses_first_threshold_hit(self):
        trace = [{"updates": 0, "loss": 2e-4}, {"updates": 10, "loss": 8e-5}]
        self.assertEqual(probe.trace_crossing(trace, 1e-4), {"updates": 10, "loss": 8e-5})

    def test_classify_reports_remaining_factor(self):
        row = {"fit_E": {"passed": False, "residual_ratio": 1.5e-5, "n_updates": 9000},
               "fit_traces": {"E": [{"updates": 0, "loss": 1e-3}, {"updates": 1, "loss": 9e-5}]}}
        result = probe.classify(row, 9000)
        self.assertFalse(result["passed_1e_minus_5"])
        self.assertEqual(result["remaining_factor_to_1e_minus_5"], 1.5)
        self.assertEqual(result["crosses_1e_minus_4"], {"updates": 1, "loss": 9e-5})
        self.assertIsNone(result["crosses_1e_minus_5"])


if __name__ == "__main__":
    unittest.main()

