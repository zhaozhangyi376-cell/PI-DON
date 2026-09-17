"""CPU-only counterexamples for diagnostic logic; no production updates."""
from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure
configure()
import mechanism_decision_eval as md
import stage2_shared_interference as shared

OBSERVATIONS = {}


def expression_from_source(relative, assignment=None, dictionary_key=None):
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if assignment and isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == assignment for t in node.targets):
                return compile(ast.Expression(node.value), relative, "eval")
        if dictionary_key and isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == dictionary_key:
                    return compile(ast.Expression(value), relative, "eval")
    raise AssertionError("expression not found")


class DiagnosticLogicTests(unittest.TestCase):
    def test_superposition_compares_different_input_sums(self):
        spec = md.make_specs(20260914, 1)[0]
        # Identity is exactly linear. Only inference is replaced; data and
        # the diagnostic's splitting/aggregation remain production code.
        with patch.object(md, "predict", side_effect=lambda net, e, h, device: (e, e)):
            result = md.diagnostics(None, spec, "cpu")
        OBSERVATIONS["linear_identity_operator"] = {
            "n_waves": spec["n_waves"], **result,
            "actual_additivity_defect": 0.0,
        }
        self.assertGreater(spec["n_waves"], 2)
        self.assertGreater(result["superposition_defect_relative_l2"], 0.01)

    def test_all_not_run_can_pass_a3_development(self):
        code = expression_from_source("scripts/experiments/h_layout_candidate.py", assignment="g1_development_pass")
        tasks = [{"step": 43, "status": "NOT_RUN"}, {"step": 96, "status": "NOT_RUN"}]
        result = eval(code, {}, {"tasks": tasks, "config": {"development_states": [43, 96]}})
        self.assertTrue(result)
        OBSERVATIONS["a3_all_not_run"] = {"tasks": tasks, "g1_development_pass": result}

    def test_partial_task_list_can_pass_r4_development(self):
        code = expression_from_source("scripts/experiments/r4_fixed_state.py", dictionary_key="g1_development_pass")
        tasks = [{"step": 43, "fit_H": {"passed": True}, "fit_E": {"passed": True}, "fixed_amplitude_error": 0.0}]
        result = eval(code, {}, {"tasks": tasks})
        self.assertTrue(result)
        OBSERVATIONS["r4_one_of_two"] = {"requested_states": [43, 96], "completed_states": [43], "g1_development_pass": result}

    def test_shared_interference_changes_reference_target(self):
        observed = []

        class FakeSolver:
            def __init__(self, args, device):
                self.dt = args.dt
                self.E = [torch.zeros((1, 3, 3)), torch.zeros((3, 1, 3)), torch.zeros((3, 3, 1))]
                self.H = [torch.zeros((1, 1, 1)) for _ in range(3)]

            def step(self, source):
                return None

            def yee_curl_H(self):
                return [torch.ones((1, 1, 1)) for _ in range(3)]

            def yee_curl_E(self):
                return [torch.ones((1, 1, 1)) for _ in range(3)]

            def inner_train(self, field, target):
                return 0, 0.0, 0.0, [torch.full((1, 1, 1), 2.0) for _ in range(3)], (1, 1, 1)

        def inspect_target(solver, field, target):
            observed.append({"which": "H" if field is solver.H else "E", "target_value": float(target[0].flatten()[0])})
            return 1.0

        with tempfile.TemporaryDirectory() as tmp:
            argv = ["stage2_shared_interference", "--out", str(Path(tmp) / "result.json")]
            with patch.object(shared.S, "Solver", FakeSolver), patch.object(shared, "rel_loss", side_effect=inspect_target), patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                shared.main()
        h_calls = [x for x in observed if x["which"] == "H"]
        self.assertEqual([x["target_value"] for x in h_calls], [1.0, 1.0, 2.0])
        OBSERVATIONS["shared_H_targets"] = h_calls


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="diagnostic_logic_counterexamples.json")
    args = parser.parse_args()
    torch.set_num_threads(1)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticLogicTests))
    payload = {"review_only": True, "production_updates": 0, "toy_optimizer_updates": 0,
               "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "observations": OBSERVATIONS}
    with (Path(__file__).parent / args.output).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    raise SystemExit(not result.wasSuccessful())
