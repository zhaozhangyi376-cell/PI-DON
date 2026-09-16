import unittest

from phase1_pilot import update_segments
from phase1_ab_pilot import batch_schedule


class Phase1PilotTests(unittest.TestCase):
    def test_declared_escalation_counts_actual_cumulative_updates(self):
        self.assertEqual(update_segments(200, 500), (200, 500))
        self.assertEqual(update_segments(500, 500), (500,))

    def test_invalid_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            update_segments(0, 500)
        with self.assertRaises(ValueError):
            update_segments(500, 200)

    def test_paired_batch_schedule_is_seed_deterministic(self):
        first = batch_schedule(128, 4, 3, 20261012)
        second = batch_schedule(128, 4, 3, 20261012)
        self.assertEqual([row.tolist() for row in first], [row.tolist() for row in second])


if __name__ == "__main__":
    unittest.main()
