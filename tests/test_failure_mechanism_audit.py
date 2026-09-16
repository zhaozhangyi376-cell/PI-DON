import unittest

from project_paths import configure
configure()

import server_failure_mechanism_audit as audit


class FailureMechanismAuditTests(unittest.TestCase):
    def test_trace_crossing_reports_first_update(self):
        trace = [{"updates": 0, "loss": 2e-4}, {"updates": 10, "loss": 9e-5}]
        self.assertEqual(audit.trace_crossing(trace, 1e-4), {"updates": 10, "loss": 9e-5})

    def test_same_first_target_requires_scale_and_initial_loss(self):
        a = {"target_ss": 1.0, "target_count": 2, "loss_initial": 3.0}
        b = {"target_ss": 1.0, "target_count": 2, "loss_initial": 3.0}
        c = {"target_ss": 2.0, "target_count": 2, "loss_initial": 3.0}
        self.assertTrue(audit.same_first_target(a, b))
        self.assertFalse(audit.same_first_target(a, c))

    def test_component_summary_separates_weak_components(self):
        row = {"six_component_metrics": {"global_weighted_relative_l2": .2,
                                         "fixed_amplitude_error": .001,
                                         "components": {
                                             "Ex": {"weak_reference": False, "nmae": .03},
                                             "Hz": {"weak_reference": True, "absolute_mae": 2e-5,
                                                    "weak_absolute_pass": False,
                                                    "reference_max": 0.0},
                                         }}}
        result = audit.component_summary(row)
        self.assertEqual(result["max_effective_component_nmae"], .03)
        self.assertEqual(result["weak_failed"], ["Hz"])


if __name__ == "__main__":
    unittest.main()

