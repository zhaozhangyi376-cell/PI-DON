"""Regression guards for old evidence and goal-bound numerical entrypoints."""
from __future__ import annotations
import os
import sys
import unittest
import json
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import run


class EntryPointTests(unittest.TestCase):
    def invoke(self, *argv):
        with patch.object(sys, 'argv', ['run.py', *argv]):
            run.main()

    def test_old_weight_cannot_be_an_output(self):
        with self.assertRaisesRegex(SystemExit, 'evidence'):
            self.invoke('train_dco', '--out', 'dco_L3.pt')

    def test_historical_report_entry_is_blocked_before_execution(self):
        with patch('run.runpy.run_path') as execute:
            with self.assertRaisesRegex(SystemExit, '历史入口'):
                self.invoke('audit_mechanism_2h', '--help')
            execute.assert_not_called()

    def test_only_explicit_inputs_are_migrated(self):
        observed = {}
        with patch('run.runpy.run_path') as execute, patch('run.require_action'):
            execute.side_effect = lambda *a, **kw: observed.update(argv=list(sys.argv))
            self.invoke('train_dco', '--init', 'dco_L3.pt', '--out', 'evidence/new_layout_test_not_created/model.pt')
            execute.assert_called_once()
            argv = observed['argv']
            self.assertEqual(argv[argv.index('--out') + 1], 'evidence/new_layout_test_not_created/model.pt')
            self.assertIn('assets', argv[argv.index('--init') + 1])

    def test_without_logger_or_action_cannot_train(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, 'lab_log'):
                run.require_action(None)

    def test_registered_action_requires_unchanged_protocol_and_cannot_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'project').mkdir()
            protocol = root / 'protocol.md'
            protocol.write_text('fixed', encoding='utf-8')
            event = {'event': 'start', 'action_id': 'A-test', 'task_id': 'M0', 'goal_id': 'G',
                     'protocol': 'protocol.md', 'protocol_sha256': hashlib.sha256(protocol.read_bytes()).hexdigest()}
            (root / 'project/plan.json').write_text(json.dumps({'goal': {'id': 'G'}, 'tasks': [{'id': 'M0'}]}), encoding='utf-8')
            ledger = root / 'project/actions.jsonl'
            ledger.write_text(json.dumps(event) + '\n', encoding='utf-8')
            with patch('run.PROJECT_DIR', root), patch.dict(os.environ, {'PIDON_LAB_RUN_ID': 'test'}):
                run.require_action('A-test')
                protocol.write_text('changed', encoding='utf-8')
                with self.assertRaisesRegex(SystemExit, '协议已改变'):
                    run.require_action('A-test')
                with ledger.open('a', encoding='utf-8') as f:
                    f.write(json.dumps({'event': 'finish', 'action_id': 'A-test'}) + '\n')
                with self.assertRaisesRegex(SystemExit, '已结束'):
                    run.require_action('A-test')
        with patch.dict(os.environ, {'PIDON_LAB_RUN_ID': 'test'}):
            with self.assertRaisesRegex(SystemExit, '预登记'):
                run.require_action(None)


if __name__ == '__main__':
    unittest.main()
