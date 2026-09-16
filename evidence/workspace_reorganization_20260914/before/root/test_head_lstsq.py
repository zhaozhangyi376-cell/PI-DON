"""H01--H08 checks for the one-shot direct-head optimization variant."""
from __future__ import annotations

import copy
import unittest

import torch

import head_lstsq
import pidon_solve as S
from test_pidon_contract_v3 import tiny_args


class HeadLeastSquaresTests(unittest.TestCase):
    def test_h01_full_rank_recovers_affine_coefficients(self):
        torch.manual_seed(1)
        feature = torch.randn(4, 3, 4, 5, dtype=torch.float64)
        beta = torch.tensor([.5, -1., 2., .25, -.75], dtype=torch.float64)
        target = (feature.flatten(1).T @ beta[:-1] + beta[-1]).reshape(3, 4, 5)
        solved, info = head_lstsq.solve_component_head(feature, target)
        self.assertLess(torch.linalg.vector_norm(solved - beta).item(), 1e-10)
        self.assertEqual(info["rank"], 5)
        self.assertLess(info["normalized_sse"], 1e-20)

    def test_h02_rank_deficient_and_zero_target_are_finite_and_recomputed(self):
        feature = torch.ones(2, 2, 2, 2)
        target = torch.zeros(2, 2, 2)
        solved, info = head_lstsq.solve_component_head(feature, target)
        self.assertTrue(torch.isfinite(solved).all())
        self.assertLess(info["rank"], info["columns"])
        self.assertEqual(info["normalized_sse"], 0.0)

    def test_h03_h04_production_hook_padding_and_component_support(self):
        args = tiny_args(); args.n = 7; args.levels = 2; args.base = 2; args.max_inner = 0
        args.head_lstsq_once, args.head_rcond = True, 1e-12
        solver = S.Solver(args, "cpu")
        solver.H = [torch.randn_like(part) for part in solver.H]
        record = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        progress = solver.fit_progress["H"]
        self.assertEqual(progress["head_commit_count"], 1)
        self.assertEqual(progress["linear_solve_calls"], 3)
        self.assertEqual(progress["head_diagnostics"].__len__(), 3)
        self.assertEqual(progress["head_feature_shape"][0], 2)
        self.assertLessEqual(record.n_updates, 0)

    def test_h05_h08_one_commit_and_adam_state_reset_only_for_head(self):
        args = tiny_args(); args.head_lstsq_once, args.head_rcond = False, 1e-12
        args.max_inner = 1
        solver = S.Solver(args, "cpu")
        solver.H = [torch.randn_like(part) for part in solver.H]
        # Establish state for all parameters, then a one-shot head replacement
        # must clear only the named head entries.
        first = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        self.assertLessEqual(first.n_updates, 1)
        solver._clear_fit_progress("H")
        solver.a.head_lstsq_once, solver.a.max_inner = True, 0
        solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        state_names = {id(param): name for name, param in solver.net_H.named_parameters()}
        present = {state_names[id(param)] for param in solver.opt_H.state}
        self.assertNotIn("head.weight", present)
        self.assertNotIn("head.bias", present)
        self.assertTrue(any(name != "head.weight" and name != "head.bias" for name in present))
        self.assertEqual(solver.fit_progress["H"]["head_commit_count"], 1)

    def test_h06_terminal_checkpoint_does_not_repeat_head_commit(self):
        args = tiny_args(); args.head_lstsq_once, args.head_rcond, args.max_inner = True, 1e-12, 0
        solver = S.Solver(args, "cpu"); solver.H = [torch.randn_like(part) for part in solver.H]
        solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        payload = solver.state_payload()
        with self.assertRaisesRegex(ValueError, "terminal"):
            S.Solver(args, "cpu").load_state_payload(payload)

    def test_h07_replaced_head_does_not_cache_target_for_other_input(self):
        args = tiny_args(); args.head_lstsq_once, args.head_rcond, args.max_inner = True, 1e-12, 0
        solver = S.Solver(args, "cpu"); solver.H = [torch.randn_like(part) for part in solver.H]
        solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        other = [torch.randn_like(part) for part in solver.H]
        with torch.no_grad():
            output = solver.predict(solver.extract_input_core(other, "H"), "H")
        self.assertTrue(torch.isfinite(output).all())

    def test_h08_interrupted_adam_resumes_without_a_second_head_commit(self):
        args = tiny_args(); args.head_lstsq_once, args.head_rcond, args.max_inner = True, 1e-12, 2
        torch.manual_seed(20260913)
        direct = S.Solver(args, "cpu"); field = [torch.randn_like(part) for part in direct.H]
        direct.H = [part.clone() for part in field]
        direct.inner_train(direct.H, direct.yee_curl_H(), "H")
        torch.manual_seed(20260913)
        interrupted = S.Solver(args, "cpu"); interrupted.H = [part.clone() for part in field]
        interrupted.on_inner_update = lambda _which, progress: progress["updates"] >= 1
        first = interrupted.inner_train(interrupted.H, interrupted.yee_curl_H(), "H")
        self.assertEqual(first.stop_reason, "interrupt")
        self.assertEqual(interrupted.fit_progress["H"]["head_commit_count"], 1)
        payload = interrupted.state_payload()
        resumed = S.Solver(args, "cpu"); resumed.load_state_payload(payload)
        resumed.inner_train(resumed.H, resumed.yee_curl_H(), "H")
        self.assertEqual(resumed.fit_progress["H"]["head_commit_count"], 1)
        self.assertEqual(resumed.fit_progress["H"]["updates"], 2)
        for lhs, rhs in zip(direct.net_H.parameters(), resumed.net_H.parameters()):
            self.assertTrue(torch.equal(lhs, rhs))


if __name__ == "__main__": unittest.main(verbosity=2)
