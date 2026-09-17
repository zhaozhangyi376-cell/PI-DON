"""Measurement-only fixtures. No forward network or optimizer is used."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure
configure()
import fdtd
import pidon_solve as solver_module
from pidon_contract import trilinear_sample

OBSERVATIONS = {}


class MeasurementEdgeTests(unittest.TestCase):
    def test_legal_upper_grid_node_is_rejected(self):
        data = torch.arange(27, dtype=torch.float64).reshape(3, 3, 3)
        xyz = (2.0, 1.0, 1.0)
        with self.assertRaises(ValueError) as caught:
            trilinear_sample(data, xyz, (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
        OBSERVATIONS["upper_node"] = {"xyz": xyz, "correct_node_value": float(data[2, 1, 1]),
                                      "exception": str(caught.exception)}

    def test_identical_float64_arrays_have_nonzero_reported_error(self):
        reference = fdtd.PECCavity(n=31)
        names = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
        for name in names:
            getattr(reference, name).fill(1.0 + 2.0 ** -30)
        tensors = [torch.from_numpy(getattr(reference, name).copy()) for name in names]
        self.assertTrue(all(np.array_equal(t.numpy(), getattr(reference, name)) for t, name in zip(tensors, names)))
        solver = SimpleNamespace(n=31, E=tensors[:3], H=tensors[3:], dev="cpu", dtype=torch.float64,
                                 cav=reference, accepted_steps=1, fit_progress={})
        record = SimpleNamespace(time_layer=0, phase="after_E", accepted=True, reason="fixture",
                                 fit_H=None, fit_E=None)
        result = solver_module._step_summary(solver, reference, record)
        q = result["six_component_metrics"]["global_weighted_relative_l2"]
        self.assertGreater(q, 0.0)
        OBSERVATIONS["identical_float64_arrays"] = {
            "true_error": 0.0, "reported_Q": q,
            "fixture": "Constant arrays for measurement, not a PEC physical trajectory",
            "reference_conversion_dtype": str(solver_module.to_t(reference.Ex, "cpu").dtype),
            "DUT_dtype": str(tensors[0].dtype),
        }


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MeasurementEdgeTests))
    payload = {"review_only": True, "production_updates": 0, "toy_optimizer_updates": 0,
               "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "observations": OBSERVATIONS}
    with (Path(__file__).parent / "metric_edge_counterexamples.json").open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    raise SystemExit(not result.wasSuccessful())
