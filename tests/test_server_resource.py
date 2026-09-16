import copy
import contextlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch

from project_paths import configure
configure()
from server_local_review import cost_of_rows, receipt_diagnosis
from server_resource_queue import merge_tasks
from server_phase1_compare import require_metadata
import server_compute_probe as probe


class ServerResourceTests(unittest.TestCase):
    def test_failed_candidate_cost_is_included(self):
        fit = {'n_updates': 3, 'n_closures': 2, 'n_lbfgs_steps': 1, 'n_evals': 4}
        rows = [{'accepted': True, 'fit_H': fit, 'fit_E': fit},
                {'accepted': False, 'fit_H': fit, 'fit_E': fit}]
        self.assertEqual(cost_of_rows(rows), dict(adam=12, closures=8, lbfgs_steps=4, evaluations=16))

    def test_missing_cost_is_not_silently_zero(self):
        with self.assertRaises(ValueError):
            cost_of_rows([{'fit_H': {}, 'fit_E': {}}])

    def test_mean_pass_does_not_imply_every_sample_pass(self):
        items = [{'macro_nmae': v, 'global_rel_l2': .02, 'macro_mre_eq5': .1} for v in (0, .018)]
        s = {'status': 'PASS', 'scientific_result': 'FAIL', 'updates': 25000, 'elapsed_s': 1,
             'action_id': 'a', 'lab_run_id': 1, 'blind_metrics': {'32': {
                 'individual': items, 'components': {}, 'macro_nmae_mean': .009}}}
        grid = receipt_diagnosis(s)['grids']['32']
        self.assertTrue(grid['mean_gate_pass'])
        self.assertFalse(grid['all_sample_gate_pass'])
        self.assertEqual(grid['sample_gate_pass_count'], 1)

    def test_install_is_idempotent_and_preserves_existing_failures(self):
        task = {'id': 'SR-COMPARE', 'status': 'FAIL', 'evidence': ['failure.json']}
        plan = {'tasks': [copy.deepcopy(task)], 'goal': {'id': 'G-REPRO'}}
        self.assertEqual(merge_tasks(plan), ['SR-PERF'])
        self.assertEqual(plan['tasks'][0], task)
        self.assertEqual(merge_tasks(plan), [])

    def test_checkpoint_normalization_cannot_be_silently_changed(self):
        with self.assertRaises(ValueError):
            require_metadata({'coords': 'cellsize', 'norm': 'max', 'levels': 4, 'base': 32})

    def test_missing_head_metadata_is_not_guessed(self):
        with self.assertRaises(ValueError):
            require_metadata({'coords': 'cellsize', 'norm': 'rms', 'levels': 4, 'base': 32})

    def test_checkpoint_save_failure_keeps_committed_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'output'
            out.mkdir()
            (root / 'train_dev_data.npz').touch()
            arrays = {'E': np.zeros((32, 3, 32, 32, 32), dtype=np.float32),
                      'C': np.zeros((32, 3, 32, 32, 32), dtype=np.float32),
                      'D': np.ones((32, 3), dtype=np.float32)}
            original_save = torch.save

            def save(value, path):
                if Path(path).name == 'micro4_last.pt':
                    raise OSError('injected checkpoint write failure')
                original_save(value, path)

            def train(net, optimizer, *args):
                optimizer.zero_grad()
                loss = net(torch.ones(1, 1)).square().sum()
                loss.backward()
                optimizer.step()
                return loss.item()

            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(probe, 'S1R', root))
                stack.enter_context(patch.object(probe, 'new_output', return_value=out))
                stack.enter_context(patch.object(probe.np, 'load', return_value=contextlib.nullcontext(arrays)))
                stack.enter_context(patch.object(probe.D, 'DCO', side_effect=lambda **kw: torch.nn.Linear(1, 1)))
                stack.enter_context(patch.object(probe.F, 'train_microbatch', side_effect=train))
                stack.enter_context(patch.object(torch, 'set_num_interop_threads'))
                stack.enter_context(patch.object(torch, 'save', side_effect=save))
                probe.run(SimpleNamespace(action_id='test', device='cpu'))
            import json
            result = json.loads((out / 'summary.json').read_text())
            self.assertEqual(result['new_adam_updates'], 15)
            self.assertEqual(result['arms'][0]['updates'], 5)
            self.assertIn('save_error', result['arms'][0])
            self.assertEqual(result['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
