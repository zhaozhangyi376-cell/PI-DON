"""N1 regressions reproduced from the v4 pre-night audit."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

import pidon_recording as recording
import pidon_solve as S
from pidon_recording import RunRecorder
from test_pidon_contract_v3 import tiny_args


class NightContractRegressionTests(unittest.TestCase):
    def test_jsonl_commit_crash_recovers_unique_next_sequence_and_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {'run_id': 'crash-test', 'protocol_hash': 'protocol'}
            recorder = RunRecorder(directory, metadata, mode='new')
            with patch.object(recording, 'atomic_json_save', side_effect=OSError('metadata crash')):
                with self.assertRaisesRegex(OSError, 'metadata crash'):
                    recorder.append({'kind': 'durable-before-crash'})
            resumed = RunRecorder(directory, metadata, mode='resume')
            self.assertEqual(resumed.metadata['recovery_tail_sequence_ids'], [0])
            resumed.append({'kind': 'after-resume'})
            rows = [json.loads(line) for line in (Path(directory) / 'steps.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([row['sequence_id'] for row in rows], [0, 1])

    def test_recorder_rejects_truncated_or_duplicate_jsonl_on_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {'run_id': 'crash-test', 'protocol_hash': 'protocol'}
            recorder = RunRecorder(directory, metadata, mode='new')
            recorder.append({'kind': 'one'})
            path = Path(directory) / 'steps.jsonl'
            path.write_text(path.read_text(encoding='utf-8') + '{not-json}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid JSONL'):
                RunRecorder(directory, metadata, mode='resume')

    def test_recorder_rejects_nonfinite_jsonl_constant_on_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {'run_id': 'crash-test', 'protocol_hash': 'protocol'}
            recorder = RunRecorder(directory, metadata, mode='new')
            recorder.append({'kind': 'one'})
            path = Path(directory) / 'steps.jsonl'
            path.write_text(path.read_text(encoding='utf-8') + '{"sequence_id": 1, "x": NaN}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid JSONL'):
                RunRecorder(directory, metadata, mode='resume')

    def test_failure_raw_does_not_claim_a_recovery_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {'run_id': 'raw-test', 'protocol_hash': 'protocol'}
            recorder = RunRecorder(directory, metadata, mode='new')
            recorder.append({'kind': 'before'})
            recorder.checkpoint({'value': 1})
            recorder.append({'kind': 'after'})
            recorder.failure_raw({'fit_progress': {'E': {'attempt_id': 7}}, 'failed_role': 'E'})
            saved = json.loads((Path(directory) / 'run_metadata.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['last_checkpoint_sequence_id'], 0)
            self.assertTrue((Path(directory) / 'failure_raw_000002_attempt_7.pt').is_file())

    def test_terminal_state_is_rejected_but_diagnostic_load_is_read_only(self):
        args = tiny_args()
        solver = S.Solver(args, 'cpu')
        solver.H = [torch.randn_like(part) for part in solver.H]
        solver.fit_progress['H'].update(stop_reason='nonfinite', resumable=False)
        payload = solver.state_payload()
        restored = S.Solver(args, 'cpu')
        with self.assertRaisesRegex(ValueError, 'terminal'):
            restored.load_state_payload(payload)
        restored.load_state_payload(payload, diagnostic_only=True)
        before = [part.detach().clone() for part in restored.net_H.parameters()]
        with torch.no_grad():
            restored.predict(restored.extract_input_core(restored.H, 'H'), 'H')
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(before, restored.net_H.parameters())))

    def test_payload_schema_and_independent_run_identity_are_explicit(self):
        args = tiny_args()
        solver = S.Solver(args, 'cpu')
        payload = solver.state_payload()
        payload.pop('state_schema')
        with self.assertRaisesRegex(ValueError, 'required solver fields'):
            S.Solver(args, 'cpu').load_state_payload(payload)
        one, two = S.formal_run_identity(args), S.formal_run_identity(args)
        self.assertNotEqual(one['run_id'], two['run_id'])
        self.assertEqual(one['protocol_hash'], two['protocol_hash'])

    def test_rolling_checkpoint_pointer_keeps_prior_slot_if_new_pointer_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {'run_id': 'rolling-test', 'protocol_hash': 'protocol'}
            recorder = RunRecorder(directory, metadata, mode='new')
            recorder.append({'kind': 'first'})
            recorder.rolling_checkpoint({'value': 1})
            recorder.append({'kind': 'second'})
            real_json = recording.atomic_json_save
            with patch.object(recording, 'atomic_json_save', side_effect=OSError('pointer crash')):
                with self.assertRaisesRegex(OSError, 'pointer crash'):
                    recorder.rolling_checkpoint({'value': 2})
            resumed = RunRecorder(directory, metadata, mode='resume')
            self.assertEqual(resumed.load_rolling_checkpoint()['value'], 1)

    def test_component_loss_cannot_pass_when_physical_total_R_fails(self):
        args = tiny_args()
        args.max_inner, args.component_rel, args.tol = 0, True, 1e-4
        solver = S.Solver(args, 'cpu')
        solver.H = [torch.ones_like(part) for part in solver.H]
        target = [torch.full((3, 3, 3), value) for value in (100., 1., 1.)]
        predicted = torch.stack([torch.full((3, 3, 3), value) for value in (101.5, 1., 1.)])
        with patch.object(solver, 'predict', return_value=predicted):
            fit = solver.inner_train(solver.H, target, 'H')
        self.assertGreater(fit.residual_ratio, 1e-4)
        self.assertFalse(fit.passed)
        self.assertEqual(fit.stop_reason, 'max_updates')

    def test_nonfinite_gradient_is_terminal_before_optimizer_step(self):
        args = tiny_args()
        args.max_inner, args.tol = 1, 0.0
        solver = S.Solver(args, 'cpu')
        solver.H = [torch.randn_like(part) for part in solver.H]
        before = [part.detach().clone() for part in solver.net_H.parameters()]
        original_backward = torch.Tensor.backward

        def poison(tensor, *args_, **kwargs):
            original_backward(tensor, *args_, **kwargs)
            next(solver.net_H.parameters()).grad.fill_(float('nan'))

        with patch.object(torch.Tensor, 'backward', poison):
            fit = solver.inner_train(solver.H, solver.yee_curl_H(), 'H')
        self.assertEqual(fit.stop_reason, 'nonfinite')
        self.assertEqual(fit.n_updates, 0)
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(before, solver.net_H.parameters())))

    def test_nonfinite_parameter_after_step_is_raw_then_rolled_back(self):
        args = tiny_args()
        args.max_inner, args.tol = 1, 0.0
        solver = S.Solver(args, 'cpu')
        solver.H = [torch.randn_like(part) for part in solver.H]
        before = [part.detach().clone() for part in solver.net_H.parameters()]
        real_step = solver.opt_H.step

        def poison(*args_, **kwargs):
            real_step(*args_, **kwargs)
            with torch.no_grad():
                next(solver.net_H.parameters()).fill_(float('nan'))

        with patch.object(solver.opt_H, 'step', poison):
            record = solver.step(0.0)
        self.assertFalse(record.accepted)
        self.assertEqual(record.reason, 'nonfinite')
        self.assertTrue(torch.isnan(next(iter(solver.last_failure_raw['net_H'].values()))).any())
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(before, solver.net_H.parameters())))


if __name__ == '__main__':
    unittest.main(verbosity=2)
