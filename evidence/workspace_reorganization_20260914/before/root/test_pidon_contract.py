"""P1 contract tests: stop decisions, Yee measurement and transaction recovery."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import fdtd
from pidon_exact_control import run
from pidon_contract import (FitRecord, component_offsets, dual_volumes, reached,
                            trilinear_sample)
from pidon_recording import RunRecorder
from pidon_solve import Solver


def fit(*, passed, reason, updates=1):
    return FitRecord(updates, updates + 1, 2e-4, 5e-5 if passed else 2e-4,
                     1.0, 1.0, 1.0, passed, reason, 0.0,
                     [torch.zeros((2, 2, 2))] * 3, 1.0, 24)


class TransactionFake:
    """Small transactional solver used to test P1 control flow, not physics."""

    step = Solver.step

    def __init__(self, records):
        self.a = argparse.Namespace(strict_stop=True, reset_opt_each_step=False)
        self.phase, self.accepted_steps, self.current_time_layer = "before_H", 0, 0
        self.H, self.E = [], []
        self.records = list(records)
        self.e_updates = self.h_updates = self.sources = 0

    def _network_state(self, which):
        return {"which": which}

    def _restore_network_state(self, which, state):
        self.restored = (which, state)

    def state_payload(self):
        return {"phase": self.phase}

    def inner_train(self, field, target, which):
        return self.records.pop(0)

    def yee_curl_H(self):
        return []

    def yee_curl_E(self):
        return []

    def _update_E_and_source(self, prediction, g_t):
        self.e_updates += 1
        self.sources += 1

    def _update_H(self, prediction):
        self.h_updates += 1


class PidonContractTests(unittest.TestCase):
    @staticmethod
    def _tiny_args(tol):
        return argparse.Namespace(
            n=3, side=0.05, dt=3.075e-12, init="random", coords="cellsize",
            norm="rms", levels=2, base=2, lr=1e-4, separate_nets=True,
            h_scale=1.0, h_output_scale=1.0, h_shift=False, tol_mode="rel",
            component_rel=False, tol=tol, max_inner=0, grad_clip=0.0,
            inner_time_budget_s=0.0, strict_stop=True, reset_opt_each_step=False,
        )

    def test_reached_is_strict_and_finite(self):
        self.assertTrue(reached(9.9e-5, 1e-4))
        self.assertFalse(reached(1e-4, 1e-4))
        self.assertFalse(reached(float("nan"), 1e-4))

    def test_e_pending_resume_does_not_repeat_source_or_e_update(self):
        fake = TransactionFake([fit(passed=True, reason="tol_met"),
                                fit(passed=False, reason="max_updates"),
                                fit(passed=True, reason="tol_met")])
        first = fake.step(1.0)
        self.assertFalse(first.accepted)
        self.assertEqual(first.phase, "E_pending")
        self.assertEqual((fake.e_updates, fake.sources, fake.h_updates), (1, 1, 0))
        resumed = fake.step(99.0)
        self.assertTrue(resumed.accepted)
        self.assertEqual((fake.e_updates, fake.sources, fake.h_updates), (1, 1, 1))
        self.assertEqual(fake.accepted_steps, 1)

    def test_h_failure_does_not_advance_transaction(self):
        fake = TransactionFake([fit(passed=False, reason="max_updates")])
        result = fake.step(1.0)
        self.assertFalse(result.accepted)
        self.assertEqual(result.phase, "before_H")
        self.assertEqual((fake.e_updates, fake.sources, fake.h_updates), (0, 0, 0))

    def test_nonzero_irrotational_input_is_not_zero_shortcut(self):
        args = self._tiny_args(1e-12)
        solver = Solver(args, "cpu")
        field = [torch.ones_like(x) for x in solver.H]
        target = solver.yee_curl_H()
        result = solver.inner_train(field, target, "H")
        self.assertNotEqual(result.stop_reason, "zero_input")
        self.assertEqual(result.stop_reason, "max_updates")
        self.assertEqual(result.n_updates, 0)
        self.assertGreater(result.n_evals, 0)
        self.assertIsNone(result.residual_ratio)
        self.assertEqual(result.residual_rule, "zero_target_fixed_scale")

    def test_terminal_e_pending_checkpoint_is_not_resumable(self):
        torch.manual_seed(7)
        pending_solver = Solver(self._tiny_args(0.0), "cpu")
        pending = pending_solver.step(1.0)
        self.assertFalse(pending.accepted)
        self.assertEqual(pending_solver.phase, "E_pending")
        payload = pending_solver.state_payload()
        # An exhausted E attempt is a terminal evidence state.  It can be
        # loaded only for diagnosis; production resume must not manufacture a
        # second chance by re-entering the optimizer.
        with self.assertRaisesRegex(ValueError, "terminal"):
            pending_solver.step(123.0)
        restored = Solver(self._tiny_args(0.0), "cpu")
        with self.assertRaisesRegex(ValueError, "terminal"):
            restored.load_state_payload(payload)

    def test_resume_rejects_changed_frozen_configuration(self):
        solver = Solver(self._tiny_args(0.0), "cpu")
        solver.step(1.0)
        incompatible = self._tiny_args(1e-4)
        with self.assertRaisesRegex(ValueError, "tol"):
            Solver(incompatible, "cpu").load_state_payload(solver.state_payload())

    def test_exhausted_inner_budget_is_rejected_before_resume(self):
        args = self._tiny_args(0.0)
        args.max_inner = 1
        solver = Solver(args, "cpu")
        first = solver.step(1.0)
        self.assertFalse(first.accepted)
        self.assertEqual(first.phase, "E_pending")
        self.assertEqual(first.fit_E.n_updates, 1)
        payload = solver.state_payload()
        restored = Solver(args, "cpu")
        with self.assertRaisesRegex(ValueError, "terminal"):
            restored.load_state_payload(payload)

    def test_nonfinite_raw_state_precedes_safe_rollback(self):
        solver = Solver(self._tiny_args(0.0), "cpu")
        original = [part.detach().clone() for part in solver.net_H.parameters()]

        def poison(field, target, which):
            with torch.no_grad():
                next(solver.net_H.parameters()).fill_(float("nan"))
            return FitRecord(0, 1, float("nan"), float("nan"), float("nan"), float("nan"),
                             1.0, False, "nonfinite", 0.0,
                             [torch.zeros_like(t) for t in target], 0.0, 1)

        solver.inner_train = poison
        record = solver.step(1.0)
        self.assertFalse(record.accepted)
        self.assertEqual(record.reason, "nonfinite")
        raw = solver.last_failure_raw
        self.assertTrue(torch.isnan(next(iter(raw["net_H"].values()))).any())
        for before, after in zip(original, solver.net_H.parameters()):
            self.assertTrue(torch.equal(before, after))

    def test_staggered_probe_and_dual_boundary_volume(self):
        values = torch.zeros((3, 3, 3))
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    values[i, j, k] = i + 10 * j + 100 * k
        # Ez z offset is half a cell: (1,1,1.5) lands exactly on [1,1,1].
        self.assertEqual(trilinear_sample(values, (1.0, 1.0, 1.5), (1.0, 1.0, 1.0), component_offsets("Ez")), 111.0)
        volumes = dual_volumes((3, 3, 3), component_offsets("Ez"), (1.0, 1.0, 1.0))
        self.assertEqual(volumes[0, 0, 1], 0.25)  # x/y face, z centre
        self.assertEqual(volumes[1, 1, 1], 1.0)

    def test_atomic_recorder_keeps_jsonl_and_latest_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RunRecorder(directory, {"case": "unit", "run_id": "unit", "protocol_hash": "unit"})
            recorder.append({"step": 0, "accepted": False})
            recorder.checkpoint({"value": 1})
            recorder.checkpoint({"value": 2})
            self.assertTrue((Path(directory) / "checkpoint_previous.pt").is_file())
            self.assertEqual(torch.load(Path(directory) / "checkpoint_latest.pt", weights_only=False)["value"], 2)
            self.assertIn('"accepted": false', (Path(directory) / "steps.jsonl").read_text(encoding="utf-8"))

    def test_yee_constant_and_linear_curls_have_expected_sign_and_support(self):
        n, d = 5, 0.2
        cavity = fdtd.PECCavity(n=n, side=n * d)
        # E=(y,z,x) at staggered E locations gives curl E=(-1,-1,-1).
        _, iy, _ = np.indices(cavity.Ex.shape)
        cavity.Ex[...] = iy * d
        _, _, iz = np.indices(cavity.Ey.shape)
        cavity.Ey[...] = iz * d
        ix, _, _ = np.indices(cavity.Ez.shape)
        cavity.Ez[...] = ix * d
        curl_e = fdtd.curl_E(cavity.Ex, cavity.Ey, cavity.Ez, d, d, d)
        for part in curl_e:
            self.assertLess(np.max(np.abs(part + 1.0)), 1e-12)
        # The same linear expression on staggered H positions verifies curl-H.
        _, iy, _ = np.indices(cavity.Hx.shape)
        cavity.Hx[...] = (iy + 0.5) * d
        _, _, iz = np.indices(cavity.Hy.shape)
        cavity.Hy[...] = (iz + 0.5) * d
        ix, _, _ = np.indices(cavity.Hz.shape)
        cavity.Hz[...] = (ix + 0.5) * d
        curl_h = fdtd.curl_H(cavity.Hx, cavity.Hy, cavity.Hz, d, d, d)
        self.assertEqual([part.shape for part in curl_h], [(n, n - 1, n - 1), (n - 1, n, n - 1), (n - 1, n - 1, n)])
        for part in curl_h:
            self.assertLess(np.max(np.abs(part + 1.0)), 1e-12)

    def test_pec_normal_curl_e_faces_are_explicitly_zero(self):
        args = self._tiny_args(1e-4)
        solver = Solver(args, "cpu")
        exact = [torch.ones_like(part) for part in solver.yee_curl_E()]
        for axis, part in enumerate(exact):
            high = [slice(None)] * 3; high[axis] = part.shape[axis] - 1
            part[tuple(high)] = 0.0
        predicted = [torch.ones((args.n, args.n, args.n)) for _ in range(3)]
        inserted = solver._insert_prediction(exact, predicted, "E")
        for axis, part in enumerate(inserted):
            low = [slice(None)] * 3; low[axis] = 0
            high = [slice(None)] * 3; high[axis] = part.shape[axis] - 1
            self.assertTrue(torch.equal(part[tuple(low)], torch.zeros_like(part[tuple(low)])))
            self.assertTrue(torch.equal(part[tuple(high)], torch.zeros_like(part[tuple(high)])))

    def test_three_axis_discrete_plane_wave_symbols_and_div_curl(self):
        n, d, k = 7, 0.1, 3.0
        cases = (("x", "Ez", 1), ("y", "Ex", 2), ("z", "Ey", 0))
        for axis, component, curl_index in cases:
            cavity = fdtd.PECCavity(n=n, side=n * d)
            array = getattr(cavity, component)
            coordinate = np.indices(array.shape)["xyz".index(axis)] * d
            array[...] = np.sin(k * coordinate)
            curl = fdtd.curl_E(cavity.Ex, cavity.Ey, cavity.Ez, d, d, d)
            actual = curl[curl_index]
            # Forward Yee difference of sin(kq) carries the discrete symbol
            # 2*sin(kd/2)/d; the sign is negative for these polarizations.
            idx = np.indices(actual.shape)["xyz".index(axis)]
            expected_1d = -(np.sin(k * (idx + 1) * d) - np.sin(k * idx * d)) / d
            self.assertLess(np.max(np.abs(actual - expected_1d)), 1e-12, axis)
        rng = np.random.default_rng(4)
        cavity = fdtd.PECCavity(n=n, side=n * d)
        for name in ("Ex", "Ey", "Ez"):
            getattr(cavity, name)[...] = rng.normal(size=getattr(cavity, name).shape)
        cx, cy, cz = fdtd.curl_E(cavity.Ex, cavity.Ey, cavity.Ez, d, d, d)
        divergence = ((cx[1:] - cx[:-1]) / d + (cy[:, 1:] - cy[:, :-1]) / d +
                      (cz[:, :, 1:] - cz[:, :, :-1]) / d)
        self.assertLess(np.max(np.abs(divergence)), 1e-11)

    def test_exact_control_128_steps_is_not_dco_and_meets_precision_gates(self):
        double = run(np.float64, n=31, steps=128)
        single = run(np.float32, n=31, steps=128)
        self.assertEqual(double["classification"], "exact Yee control; not a DCO result")
        self.assertTrue(double["finite"] and single["finite"])
        self.assertLessEqual(double["max_global_relative_l2"], 1e-10)
        self.assertLessEqual(single["max_global_relative_l2"], 1e-4)
        self.assertEqual(double["support"]["uncovered"], 0)
        self.assertEqual(len(double["rows"]), 128)

    def test_zero_curl_control_is_rejected_after_propagation(self):
        zero = run(np.float64, n=31, steps=128, mode="zero")
        self.assertTrue(zero["finite"])
        self.assertGreater(zero["max_global_relative_l2"], 0.05)

    def test_production_control_serializes_weak_component_metrics_as_null(self):
        result = run(np.float64, n=31, steps=2)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
