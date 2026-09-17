"""Review-only synthetic records for historical validator edge cases."""
from __future__ import annotations

import copy
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

import direct_m1_diagnosis as m1
import mechanism_hour_runner as hour
import g0_verifier as g0

OBS = {}


def synthetic_control():
    component = {key: 0.0 for key in (
        "nmae", "volume_nmae", "mre_eq5_physical", "mre_nonzero", "relative_l2",
        "sse", "reference_energy", "support_count", "strict_zero_reference_count")}
    rows = [{"step": i, "accepted": True, "accepted_steps": i + 1,
             "accepted_field_metrics": {"components": {k: dict(component) for k in (
                 "Ex", "Ey", "Ez", "Hx", "Hy", "Hz")}, "global_weighted_relative_l2": 0.0,
                                        "fixed_amplitude_error": 0.0},
             "source_outside_probes": [{"dut_Ez": 0.0, "ref_Ez": 0.0} for _ in range(3)]}
            for i in range(128)]
    return {"rows": rows, "identity": {"run_id": "review-only", "protocol_hash": "synthetic"},
            "support": {"uncovered": 0}, "reference_dtype": "float64", "control_only": True}


class HistoricalValidatorReview(unittest.TestCase):
    def test_finalize_overwrites_failed_status_from_pointer_existence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arm = root / "runs/S_R"
            arm.mkdir(parents=True)
            row = {"step": 1, "accepted_steps": 1, "accepted": False, "reason": "max_updates",
                   "fit_E": {"n_updates": 7, "target_ss": 1.0, "residual_ratio": 1.0}}
            (arm / "steps.jsonl").write_text(json.dumps(row) + "\n")
            (arm / "summary.json").write_text(json.dumps({"status": "FAIL", "recovery_eligible": False}))
            (arm / "checkpoint_pointer.json").write_text("{}")
            (root / "stage_status.json").write_text(json.dumps({"status": {"S-R": "FAIL"}}))
            manifest = {"status": {"S-R": "FAIL"}, "updates_this_experiment": 0}
            with patch.object(hour, "OUT", root):
                hour.finalize_arm(manifest, "S-R")
            result = json.loads((arm / "summary.json").read_text())
        self.assertEqual(result["status"], "RESOURCE_LIMIT")
        self.assertTrue(result["recovery_eligible"])
        self.assertEqual(manifest["updates_this_experiment"], 0)
        self.assertEqual(manifest["runs"]["S-R"]["total_actual_updates"], 7)
        OBS["finalize"] = {"before_status": "FAIL", "after_status": result["status"],
                            "recovery_eligible_with_empty_pointer": result["recovery_eligible"],
                            "top_level_updates": manifest["updates_this_experiment"],
                            "per_arm_updates": 7}

    def test_g0_does_not_compare_summary_numbers_to_disk_rows(self):
        control = synthetic_control()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run_metadata.json").write_text(json.dumps(control["identity"]))
            rows = [{"sequence_id": i, "accepted": False, "wrong_field": 1000.0} for i in range(128)]
            (root / "steps.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            integrity = g0.control_integrity(control, root)
        numeric, observed = g0.control_numeric(control, threshold=1e-10, should_pass=True)
        self.assertTrue(integrity)
        self.assertTrue(numeric)
        OBS["g0_binding"] = {"integrity_pass": integrity, "summary_numeric_pass": numeric,
                              "raw_disk_all_accepted": False, "source_snapshot_hashes_present": False}

    def test_g0_negative_control_can_pass_for_missing_probe_instead_of_wrong_physics(self):
        control = synthetic_control()
        control["rows"][0]["source_outside_probes"] = []
        accepted, observed = g0.control_numeric(control, threshold=1e-10, should_pass=False)
        self.assertTrue(accepted)
        self.assertEqual(observed["max_Q"], 0.0)
        OBS["g0_negative"] = {"negative_test_pass": accepted, "Q": observed["max_Q"],
                               "missing_probe_is_only_change": True}

    def test_m1_missing_residual_writes_interpretation_on_previous_case(self):
        first = {"case_id": "first", "readback_E": {"residual_ratio": 0.1},
                 "recorded_fit_E": {"residual_ratio": 0.1},
                 "head_projection_E": {"best_physical": {"residual_ratio": 0.01}}}
        second = copy.deepcopy(first)
        second.update(case_id="second", recorded_fit_E={"residual_ratio": None},
                      head_projection_E={"best_physical": {"residual_ratio": 1e-8}})
        result = m1.interpretation([first, second])["case_interpretations"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["case_id"], "first")
        self.assertEqual(result[0]["head_best_R"], 1e-8)
        OBS["m1_case_association"] = {"input_case_count": 2, "output_notes": result}


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(HistoricalValidatorReview))
    with Path(__file__).with_name("historical_validator_counterexamples.json").open("x", encoding="utf-8") as handle:
        json.dump({"review_only": True, "production_updates": 0, "toy_updates": 0,
                   "tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
                   "observations": OBS}, handle, indent=2)
        handle.write("\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
