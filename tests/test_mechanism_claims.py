# -*- coding: utf-8 -*-
"""Read-only regression checks for the bounded mechanism-decision ledger."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


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
