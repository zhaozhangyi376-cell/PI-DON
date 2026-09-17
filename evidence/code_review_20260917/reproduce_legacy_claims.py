"""Negative fixtures for legacy claims; no historical generator is run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import mock_open, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure
configure()
import verify_claims as vc

OBSERVATIONS = {}


class LegacyClaimTests(unittest.TestCase):
    def test_material_claim_accepts_missing_or_contradictory_second_marker(self):
        spec = next(row for row in vc.RUN_CLAIMS if row[0] == "R5")
        outputs = ["RESULT material_pair_ok 1\n",
                   "RESULT material_pair_ok 1\nRESULT material_onesided_ok 1\n"]
        results = []
        for stdout in outputs:
            process = subprocess.CompletedProcess([], 0, stdout, "")
            with patch.object(vc.subprocess, "run", return_value=process):
                result = vc.run_claim(*spec)
            self.assertEqual(result[0], "PASS")
            results.append({"stdout": stdout, "reported": result})
        OBSERVATIONS["material_marker_completeness"] = results

    def test_empty_fixed_state_tasks_pass(self):
        with patch.object(vc.os.path, "exists", return_value=True), patch("builtins.open", mock_open(read_data='{"tasks": []}')):
            result = vc.n3_p3_gate(None)
        self.assertEqual(result[0], "PASS")
        OBSERVATIONS["empty_fixed_state_tasks"] = result

    def test_zero_step_exact_control_summary_claims_128(self):
        value = {"finite": True, "global_relative_l2": 0.0,
                 "classification": "not a DCO", "steps": 0, "rows": []}
        fixture = json.dumps({"float64": value, "float32": value})
        with patch.object(vc.os.path, "exists", return_value=True), patch("builtins.open", mock_open(read_data=fixture)):
            result = vc.n2_p2_control(None)
        self.assertEqual(result[0], "PASS")
        OBSERVATIONS["zero_step_control"] = {"fixture": json.loads(fixture), "reported": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="legacy_claim_counterexamples.json")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LegacyClaimTests))
    payload = {"review_only": True, "production_updates": 0, "toy_optimizer_updates": 0,
               "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "observations": OBSERVATIONS}
    with (Path(__file__).parent / args.output).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    raise SystemExit(not result.wasSuccessful())
