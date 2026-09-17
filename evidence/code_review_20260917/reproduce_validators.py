"""Negative-control tests of scientific validators, with synthetic CPU data."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure
configure()

import numpy as np
import torch
import phase1_full_run as phase1
import direct_m2_audit as m2

torch.set_num_threads(1)
OBS = {}


class BatchDependentFixture(torch.nn.Module):
    """Intentionally violates microbatch equivalence to challenge the checker."""

    def __init__(self, **kwargs):
        super().__init__()
        self.head = torch.nn.Conv3d(3, 3, 1)

    def forward(self, field, coords):
        return self.head(field) * len(field)


class ValidatorReview(unittest.TestCase):
    def test_equivalence_checker_passes_unequal_gradients(self):
        field = torch.ones((32, 3, 2, 2, 2))
        target = torch.ones_like(field)
        spacing = torch.full((32, 3), 0.0005)
        with patch.object(phase1.D, "DCO", BatchDependentFixture), patch.object(phase1, "GRID", (2, 2, 2)):
            result = phase1.full_batch_equivalence(field, target, spacing, torch.device("cpu"), 4)
        self.assertEqual(result["status"], "PASS")
        self.assertGreater(result["loss_abs_diff"], 1e-2)
        self.assertGreater(result["max_checked_grad_rel_diff"], 0.1)
        OBS["equivalence_checker"] = result

    def test_s1_gate_checks_average_not_every_sample(self):
        target = np.ones((100, 3, 2, 2, 2), dtype=np.float64)
        prediction = target.copy()
        prediction[0] += 0.02
        result = phase1.metric_summary(prediction, target)
        self.assertTrue(result["gate"]["pass"])
        self.assertGreater(result["macro_nmae_max"], 0.01)
        OBS["s1_sample_gate"] = {key: result[key] for key in (
            "macro_nmae_mean", "macro_nmae_max", "global_rel_l2_p90", "gate")}

    def test_m2_gate_ignores_q_weak_failure_and_nonfinite_component(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arm = root / "A_P"
            arm.mkdir()
            summary = {"status": "PASS", "accepted_steps": 128,
                       "last_accepted_step": {"six_component_metrics": {
                           "components": {"Ex": {"weak_reference": False, "nmae": 0.0},
                                          "Ey": {"weak_reference": False, "nmae": float("nan")},
                                          "Hz": {"weak_reference": True, "absolute_mae": 10.,
                                                 "weak_absolute_pass": False}},
                           "global_weighted_relative_l2": 9.0, "fixed_amplitude_error": 0.0}},
                       "probe_timeseries": [{"source_outside_probes": [
                           {"dut_Ez": 1., "ref_Ez": 1.}, {"dut_Ez": 1., "ref_Ez": 1.}]}]}
            (arm / "summary.json").write_text(json.dumps(summary))
            with patch.object(m2, "RUNS", root):
                result = m2.summarize_arm("A-P")
            self.assertTrue(result["field_gate_pass"])
            OBS["m2_gate"] = {"field_gate_pass": result["field_gate_pass"],
                               "Q": result["global_weighted_relative_l2"],
                               "weak_Hz_absolute_error": 10., "Ey_nmae_is_nan": True,
                               "components_present": ["Ex", "Ey", "Hz"],
                               "probe_timeseries_length": 1}


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ValidatorReview))
    with Path(__file__).with_name("validator_counterexamples.json").open("x", encoding="utf-8") as handle:
        json.dump({"review_only": True, "production_updates": 0, "tests": result.testsRun,
                   "errors": len(result.errors), "failures": len(result.failures),
                   "observations": OBS}, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
