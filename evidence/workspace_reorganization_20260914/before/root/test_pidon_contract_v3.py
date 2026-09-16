"""A1 regressions for a resumable, budgeted Algorithm-1 transaction."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

import pidon_solve as S
from pidon_recording import RunRecorder
from test_pidon_contract import PidonContractTests
from pidon_exact_control import run as run_exact_control
from pidon_contract import component_metric


def tiny_args():
    args = PidonContractTests._tiny_args(0.0)
    args.max_inner = 1
    args.lbfgs_closures = 0
    args.lbfgs_lr = 1.0
    args.lbfgs_history = 10
    args.lbfgs_time_budget_s = 60.0
    return args


class A1ContractRegressionTests(unittest.TestCase):
    def test_elapsed_budget_is_cumulative_across_resume(self):
        args = tiny_args()
        args.inner_time_budget_s = 1.0
        solver = S.Solver(args, "cpu")
        solver.H = [torch.randn_like(part) for part in solver.H]
        solver.fit_progress["H"]["elapsed_s"] = 2.0
        # Constant monotonic time removes machine speed from the assertion.
        with patch.object(S.time, "perf_counter", return_value=100.0):
            record = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        self.assertEqual(record.n_updates, 0)
        self.assertEqual(record.stop_reason, "time_budget")

    def test_resume_rejects_lbfgs_budget_change(self):
        args = tiny_args()
        solver = S.Solver(args, "cpu")
        payload = solver.state_payload()
        incompatible = copy.copy(args)
        incompatible.lbfgs_closures = 200
        with self.assertRaisesRegex(ValueError, "lbfgs_closures"):
            S.assert_resume_compatible(incompatible, payload["frozen_config"])

    def test_formal_config_rejects_explicit_cli_conflict(self):
        args = tiny_args()
        args.torch_dtype = "float32"
        args.source_mode = "hard"
        config = S.frozen_config(args)
        config["lr"] = 2e-4
        with self.assertRaisesRegex(ValueError, "CLI/config conflict for lr"):
            S.apply_frozen_config(args, config, {"lr"})

    def test_formal_config_requires_every_frozen_field(self):
        args = tiny_args()
        with self.assertRaisesRegex(ValueError, "lacks frozen fields"):
            S.apply_frozen_config(args, {"n": args.n}, set())

    def test_new_run_refuses_foreign_identity_in_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            RunRecorder(directory, {"run_id": "run-A", "protocol_hash": "p-A"}, mode="new")
            with self.assertRaisesRegex(ValueError, "run identity"):
                RunRecorder(directory, {"run_id": "run-B", "protocol_hash": "p-B"}, mode="new")

    def test_resume_accepts_only_same_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {"run_id": "run-A", "protocol_hash": "p-A"}
            RunRecorder(directory, metadata, mode="new")
            RunRecorder(directory, metadata, mode="resume")
            with self.assertRaisesRegex(ValueError, "run identity"):
                RunRecorder(directory, {"run_id": "run-A", "protocol_hash": "p-B"}, mode="resume")

    def test_recorder_commits_monotonic_sequence_to_durable_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RunRecorder(directory, {"run_id": "run-A", "protocol_hash": "p-A"}, mode="new")
            recorder.append({"kind": "first"})
            recorder.append({"kind": "second"})
            records = [__import__("json").loads(line) for line in
                       (Path(directory) / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
            metadata = __import__("json").loads((Path(directory) / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual([row["sequence_id"] for row in records], [0, 1])
            self.assertEqual(metadata["last_committed_sequence_id"], 1)

    def test_recorder_save_failure_keeps_the_prior_complete_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {"run_id": "run-A", "protocol_hash": "p-A"}
            recorder = RunRecorder(directory, metadata, mode="new")
            recorder.append({"kind": "first"})
            recorder.checkpoint({"value": 1})
            recorder.append({"kind": "second"})
            real_save = __import__("pidon_recording").atomic_torch_save

            def fail_new_commit(payload, destination):
                if "checkpoint_commit_000001_000001" in str(destination):
                    raise OSError("simulated temporary-file write failure")
                return real_save(payload, destination)

            with patch("pidon_recording.atomic_torch_save", side_effect=fail_new_commit):
                with self.assertRaisesRegex(OSError, "simulated"):
                    recorder.checkpoint({"value": 2})
            latest = torch.load(Path(directory) / "checkpoint_latest.pt", weights_only=False)
            self.assertEqual(latest["value"], 1)

    def test_recorder_classifies_uncheckpointed_jsonl_tail_on_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {"run_id": "run-A", "protocol_hash": "p-A"}
            recorder = RunRecorder(directory, metadata, mode="new")
            recorder.append({"kind": "checkpointed"})
            recorder.checkpoint({"value": 1})
            recorder.append({"kind": "tail"})
            resumed = RunRecorder(directory, metadata, mode="resume")
            self.assertEqual(resumed.metadata["recovery_tail_sequence_ids"], [1])

    def test_new_run_rejects_nonempty_directory_without_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-empty"):
                RunRecorder(directory, {"run_id": "run-A", "protocol_hash": "p-A"}, mode="new")

    def test_production_exact_control_records_and_restores_midrun(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_exact_control(torch.float64, steps=16, out_dir=Path(directory) / "control", resume_after=8)
            self.assertTrue(result["control_only"])
            self.assertTrue(result["field_gate_pass"])
            self.assertEqual(result["restored_at_accepted_step"], 8)
            self.assertEqual(len(result["rows"]), 16)
            self.assertTrue((Path(directory) / "control" / "checkpoint_pointer.json").is_file())
            self.assertTrue(any((Path(directory) / "control" / name).is_file()
                                for name in ("checkpoint_A.pt", "checkpoint_B.pt")))
            self.assertTrue((Path(directory) / "control" / "source_snapshot" / "pidon_solve.py").is_file())

    def test_mre_and_nmae_are_separate_with_strict_zero_reporting(self):
        ref = torch.tensor([[[0.0, 2.0]]])
        pred = torch.tensor([[[1.0, 4.0]]])
        metric = component_metric(pred, ref, scale=1.0, dxyz=(1.0, 1.0, 1.0), offsets=(0.5, 0.5, 0.5))
        self.assertEqual(metric["strict_zero_reference_count"], 1)
        self.assertEqual(metric["mre_nonzero_count"], 1)
        self.assertNotEqual(metric["nmae"], metric["mre_nonzero"])

    def test_failed_half_transaction_has_no_accepted_field_metric(self):
        solver = S.Solver(tiny_args(), "cpu")
        record = solver.step(1.0)
        self.assertFalse(record.accepted)
        reference = S.fdtd.PECCavity(side=solver.a.side, n=solver.a.n, dt=solver.a.dt)
        summary = S._step_summary(solver, reference, record)
        self.assertIsNone(summary["accepted_field_metrics"])
        self.assertIsNone(summary["six_component_metrics"])

    def test_production_h_shift_adapter_uses_registered_staggered_slices(self):
        args = tiny_args()
        args.h_shift = True
        solver = S.Solver(args, "cpu")
        fields = [torch.arange(part.numel(), dtype=solver.dtype).reshape_as(part) for part in solver.H]
        core = solver.extract_input_core(fields, "H")
        self.assertTrue(torch.equal(core[0], fields[0][1:args.n + 1, :args.n, :args.n]))
        self.assertTrue(torch.equal(core[1], fields[1][:args.n, 1:args.n + 1, :args.n]))
        self.assertTrue(torch.equal(core[2], fields[2][:args.n, :args.n, 1:args.n + 1]))

    def test_lbfgs_budget_interrupt_restores_last_completed_call(self):
        args = tiny_args()
        args.max_inner = 0
        args.lbfgs_closures = 2
        solver = S.Solver(args, "cpu")
        solver.H = [torch.randn_like(part) for part in solver.H]
        first_parameter = next(solver.net_H.parameters())
        initial = first_parameter.detach().clone()
        accepted = []

        class InterruptedLBFGS:
            def __init__(self, params, **_):
                self.params = list(params)
                self.calls = 0

            def zero_grad(self, **_):
                for parameter in self.params:
                    parameter.grad = None

            def state_dict(self):
                return {"state": {}, "param_groups": []}

            def load_state_dict(self, _state):
                return None

            def step(self, closure):
                self.calls += 1
                closure()
                with torch.no_grad():
                    self.params[0].add_(0.001)
                if self.calls == 1:
                    accepted.append(self.params[0].detach().clone())
                else:
                    closure()  # closure #3 must be refused by the budget.

        with patch.object(S.torch.optim, "LBFGS", InterruptedLBFGS):
            record = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        self.assertEqual(record.stop_reason, "closure_budget")
        self.assertEqual(record.n_closures, 2)
        self.assertTrue(torch.equal(first_parameter, accepted[0]))
        self.assertFalse(torch.equal(first_parameter, initial))
        self.assertTrue(hasattr(solver, "last_failure_raw"))

    def test_payload_has_explicit_attempt_identity_and_optimizer_phase(self):
        solver = S.Solver(tiny_args(), "cpu")
        payload = solver.state_payload()
        for which in ("H", "E"):
            self.assertIn("attempt_id", payload["fit_progress"][which])
            self.assertIn("optimization_phase", payload["fit_progress"][which])

    def test_interrupted_adam_resume_matches_uninterrupted_trajectory(self):
        args = tiny_args()
        args.max_inner = 3
        torch.manual_seed(20260913)
        direct = S.Solver(args, "cpu")
        field = [torch.randn_like(part) for part in direct.H]
        direct.H = [part.clone() for part in field]
        direct_result = direct.inner_train(direct.H, direct.yee_curl_H(), "H")

        torch.manual_seed(20260913)
        interrupted = S.Solver(args, "cpu")
        interrupted.H = [part.clone() for part in field]
        interrupted.on_inner_update = lambda _which, progress: progress["updates"] == 2
        first = interrupted.inner_train(interrupted.H, interrupted.yee_curl_H(), "H")
        self.assertEqual(first.stop_reason, "interrupt")
        self.assertEqual(first.n_updates, 2)
        payload = interrupted.state_payload()

        torch.manual_seed(999)  # restore must replace all stochastic state.
        resumed = S.Solver(args, "cpu")
        resumed.load_state_payload(payload)
        second = resumed.inner_train(resumed.H, resumed.yee_curl_H(), "H")
        self.assertEqual(second.n_updates, 3)
        self.assertEqual(direct_result.n_updates, 3)
        for lhs, rhs in zip(direct.net_H.parameters(), resumed.net_H.parameters()):
            self.assertTrue(torch.equal(lhs, rhs))
        direct_opt = direct.opt_H.state_dict()
        resumed_opt = resumed.opt_H.state_dict()
        self.assertEqual(direct_opt["param_groups"], resumed_opt["param_groups"])
        self.assertEqual(direct_opt["state"].keys(), resumed_opt["state"].keys())
        for key in direct_opt["state"]:
            self.assertEqual(direct_opt["state"][key].keys(), resumed_opt["state"][key].keys())
            for name, lhs in direct_opt["state"][key].items():
                rhs = resumed_opt["state"][key][name]
                if torch.is_tensor(lhs):
                    self.assertTrue(torch.equal(lhs, rhs), name)
                else:
                    self.assertEqual(lhs, rhs)

    def test_interrupted_lbfgs_resume_matches_uninterrupted_trajectory(self):
        args = tiny_args()
        args.max_inner = 1
        args.lbfgs_closures = 4
        args.lbfgs_time_budget_s = 0.0
        args.tol = 0.0
        torch.manual_seed(20260913)
        direct = S.Solver(args, "cpu")
        direct.H = [torch.randn_like(part) for part in direct.H]
        direct_result = direct.inner_train(direct.H, direct.yee_curl_H(), "H")

        torch.manual_seed(20260913)
        interrupted = S.Solver(args, "cpu")
        interrupted.H = [part.clone() for part in direct.H]
        interrupted.on_lbfgs_step = lambda _which, progress: progress["lbfgs_steps"] == 1
        first = interrupted.inner_train(interrupted.H, interrupted.yee_curl_H(), "H")
        self.assertEqual(first.stop_reason, "interrupt")
        self.assertGreaterEqual(first.n_closures, 1)
        payload = interrupted.state_payload()

        torch.manual_seed(999)
        resumed = S.Solver(args, "cpu")
        resumed.load_state_payload(payload)
        second = resumed.inner_train(resumed.H, resumed.yee_curl_H(), "H")
        self.assertEqual(second.n_updates, direct_result.n_updates)
        self.assertEqual(second.n_closures, direct_result.n_closures)
        for lhs, rhs in zip(direct.net_H.parameters(), resumed.net_H.parameters()):
            self.assertTrue(torch.equal(lhs, rhs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
