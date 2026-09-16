# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mechanism_hour_runner as M


class MechanismHourTests(unittest.TestCase):
    def test_budget_is_monotonic_and_separates_strict_explore(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        manifest = M.make_manifest(start, Path("plan.md"), "abc", "def")
        self.assertEqual(manifest["training_deadline"], "2026-01-01T00:54:00+00:00")
        self.assertEqual(manifest["deadline"], "2026-01-01T01:00:00+00:00")
        self.assertLess(M.seconds_left(manifest, start + timedelta(minutes=10)), 3241)
        self.assertGreater(M.arm_spec("S-P")["tol"], 0)
        self.assertLess(M.arm_spec("S-P")["tol"], M.arm_spec("X-P")["tol"])

    def test_failure_does_not_become_success_or_reset_budget(self):
        row = {"accepted": False, "accepted_steps": 0, "fit_E": {"residual_ratio": 5e-4, "n_updates": 500}}
        state = M.classify_row(row, "S-P")
        self.assertEqual(state["status"], "FAIL")
        self.assertEqual(state["tol"], 1e-4)
        self.assertFalse(state["advance"])
        self.assertEqual(state["budget_consumed_updates"], 500)

    def test_interrupt_callback_does_not_depend_on_stdout(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "heartbeat.json"
            cb = M.make_heartbeat_callback(p, lambda: True)
            self.assertTrue(cb("E", {"updates": 7}))
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["updates"], 7)


if __name__ == "__main__":
    unittest.main()
