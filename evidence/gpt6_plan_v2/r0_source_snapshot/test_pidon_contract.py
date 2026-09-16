"""P1 contract tests: stop decisions, Yee measurement and transaction recovery."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import fdtd
from pidon_exact_control import adapter_curl_E, apply_pec, run
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

    def test_cpu_checkpoint_e_pending_resume_is_deterministic(self):
        torch.manual_seed(7)
        pending_solver = Solver(self._tiny_args(0.0), "cpu")
        pending = pending_solver.step(1.0)
        self.assertFalse(pending.accepted)
        self.assertEqual(pending_solver.phase, "E_pending")
        payload = pending_solver.state_payload()
        torch.manual_seed(99)
        first = Solver(self._tiny_args(1e6), "cpu")
        first.load_state_payload(payload)
        torch.manual_seed(101)
        second = Solver(self._tiny_args(1e6), "cpu")
        second.load_state_payload(payload)
        self.assertTrue(first.step(123.0).accepted)
        self.assertTrue(second.step(-456.0).accepted)
        for lhs, rhs in zip(first.E + first.H, second.E + second.H):
            self.assertTrue(torch.equal(lhs, rhs))

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
            recorder = RunRecorder(directory, {"case": "unit"})
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

    def test_pec_high_curl_e_planes_are_explicitly_zero(self):
        n = 5
        cavity = fdtd.PECCavity(n=n, side=1.0)
        cavity.Ez[n // 2, n // 2, n // 2] = 1.0
        arrays = {name: getattr(cavity, name) for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")}
        apply_pec(arrays)
        adapted, boundaries = adapter_curl_E(arrays, dx=cavity.dx)
        self.assertEqual(len(adapted), 3)
        self.assertEqual(boundaries, [0.0, 0.0, 0.0])

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
        self.assertLessEqual(double["global_relative_l2"], 1e-10)
        self.assertLessEqual(single["global_relative_l2"], 1e-4)
        self.assertEqual(double["max_analytic_pec_boundary_curl"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
