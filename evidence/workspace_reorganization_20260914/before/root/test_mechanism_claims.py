# -*- coding: utf-8 -*-
"""Read-only regression checks for the bounded mechanism-decision ledger."""

import unittest

import verify_claims as vc


class MechanismDecisionClaimTests(unittest.TestCase):
    def test_reader_preserves_failed_and_incomplete_statuses(self):
        data = vc.mechanism_decision_claims_data()
        self.assertFalse(data["s1_cube32_pass"])
        self.assertFalse(data["p_passed"])
        self.assertEqual(data["p_updates"], 500)
        self.assertEqual(data["r_partial_rows"], 26)
        self.assertTrue(data["r_all_accepted"])
        self.assertEqual(data["r_status"], "PARTIAL_ABORTED_BY_AGENT")
        self.assertTrue(data["first_failure_recomputed"])


if __name__ == "__main__":
    unittest.main()
