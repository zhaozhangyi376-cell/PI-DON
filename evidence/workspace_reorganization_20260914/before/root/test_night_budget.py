from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from night_budget import (BudgetError, NightPaths, append_ledger, assert_can_start,
                          assert_task_budget, init_or_load, read_ledger)


class NightBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = self.root / 'plan.md'; self.plan.write_text('plan', encoding='utf-8')
        self.weight = self.root / 'weight.pt'; self.weight.write_bytes(b'weight')
        self.paths = NightPaths(self.root / 'night')
        self.now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        self.manifest = init_or_load(self.paths, plan_path=self.plan, master_weight=self.weight,
                                     source_hashes={'solver': 'hash'}, now=self.now)

    def tearDown(self):
        self.temp.cleanup()

    def test_second_initialization_keeps_original_deadline(self):
        loaded = init_or_load(self.paths, plan_path=self.plan, master_weight=self.weight,
                              source_hashes={'solver': 'different'}, now=self.now + timedelta(hours=1))
        self.assertEqual(loaded['started_at'], self.manifest['started_at'])
        self.assertEqual(loaded['deadline'], self.manifest['deadline'])

    def test_plan_change_cannot_reopen_window(self):
        self.plan.write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(BudgetError, 'plan hash'):
            init_or_load(self.paths, plan_path=self.plan, master_weight=self.weight,
                         source_hashes={}, now=self.now)

    def test_training_stops_at_nine_and_a_half_hours(self):
        with self.assertRaisesRegex(BudgetError, 'training deadline'):
            assert_can_start(self.manifest, training=True, now=self.now + timedelta(hours=9, minutes=30))
        assert_can_start(self.manifest, training=False, now=self.now + timedelta(hours=9, minutes=30))

    def test_ledger_never_reuses_sequence_or_task_budget(self):
        append_ledger(self.paths, {'task_id': 'same', 'adam_updates': 499, 'head_commits': 1,
                                   'linear_solve_calls': 3, 'training_s': 359.0})
        self.assertEqual(read_ledger(self.paths)[0]['sequence_id'], 0)
        for kwargs in ({'add_adam': 1}, {'add_head': 1}, {'add_solve': 1}, {'add_training_s': 2.0}):
            with self.assertRaises(BudgetError):
                assert_task_budget(self.paths, 'same', **kwargs)

    def test_duplicate_ledger_sequence_is_rejected(self):
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.ledger.write_text('{"sequence_id": 0}\n{"sequence_id": 0}\n', encoding='utf-8')
        with self.assertRaisesRegex(BudgetError, 'duplicate'):
            read_ledger(self.paths)


if __name__ == '__main__':
    unittest.main(verbosity=2)
