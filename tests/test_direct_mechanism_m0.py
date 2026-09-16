"""M0 direct-mechanism recording/recovery smoke tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import direct_mechanism_runner as D


class DirectMechanismM0Tests(unittest.TestCase):
    def test_none_metric_case_is_json_reportable(self):
        result = D.none_metric_case()
        self.assertTrue(result["json_serializable"])
        self.assertIsNone(result["ez_nmae"])

    def test_m0_core_checks_pass_in_temp_evidence(self):
        original_out = D.OUT
        with tempfile.TemporaryDirectory() as directory:
            D.OUT = Path(directory) / "direct_mechanism_v1"
            try:
                audit = D.run_m0()
            finally:
                D.OUT = original_out
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["checks"]["pending_resume_matches_uninterrupted"])
        self.assertTrue(audit["checks"]["pending_checkpoint_saved"])
        self.assertTrue(audit["checks"]["terminal_budget_not_production_resumable"])
        self.assertTrue(audit["checks"]["closure_budget_counted"])
        self.assertGreaterEqual(audit["total_m0_engineering_budget"]["adam"], 1)
        self.assertGreaterEqual(audit["total_m0_engineering_budget"]["closures"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
