"""Isolated CPU checks of bookkeeping and interrupt paths, not science runs."""
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

import torch
import direct_mechanism_runner as m0
import direct_m2_runner as m2
import direct_benefit_runner as benefit
import pidon_solve as solve

torch.set_num_threads(1)
OBS = {}
TOY_COST = {"adam": 0, "closures": 0, "lbfgs_steps": 0}


class RuntimeReview(unittest.TestCase):
    def test_m0_resume_sums_cumulative_updates_twice(self):
        calls = []
        original_step = torch.optim.Adam.step

        def counted_step(optimizer, *args, **kwargs):
            result = original_step(optimizer, *args, **kwargs)
            calls.append(1)
            TOY_COST["adam"] += 1
            return result

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"experiment_id": "isolated-code-review", "action_id": None}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(m0, "OUT", root), patch.object(torch.optim.Adam, "step", counted_step):
                _, _, uninterrupted = m0.run_uninterrupted(manifest, root / "uninterrupted")
                interrupted = m0.run_interrupted_resume(manifest, root / "interrupted")
            rows = uninterrupted + interrupted["first_rows"] + interrupted["second_rows"]
            recorded = m0.budget_from_rows(rows)
        self.assertEqual(len(calls), 4)
        self.assertEqual(recorded["adam"], 5)
        OBS["m0_count"] = {"observed_adam_step_calls": len(calls),
                            "summed_fit_n_updates": recorded["adam"],
                            "interrupted_fit_counts": [r["fit_E"]["n_updates"] for r in rows[1:]],
                            "accepted_steps": recorded["accepted_steps"]}

    def test_adam_interrupt_still_enters_lbfgs(self):
        torch.manual_seed(91)
        solver = solve.Solver(m0.tiny_args(max_inner=2, lbfgs_closures=2), "cpu")
        solver.on_inner_update = lambda which, progress: True
        record = solver.step(1e-4)
        fit = record.fit_E
        TOY_COST["adam"] += fit.n_updates
        TOY_COST["closures"] += fit.n_closures
        TOY_COST["lbfgs_steps"] += fit.n_lbfgs_steps
        self.assertEqual(fit.n_updates, 1)
        self.assertGreater(fit.n_closures, 0)
        OBS["interrupt"] = {"adam": fit.n_updates, "closures_after_interrupt": fit.n_closures,
                            "lbfgs_steps": fit.n_lbfgs_steps, "final_reason": fit.stop_reason}

    def test_exception_at_target_is_classified_as_pass(self):
        result = m2.classify_stop({"reason": "EXCEPTION", "error": "checkpoint write failed"}, 128, 128)
        self.assertEqual(result, "PASS")
        OBS["terminal_exception"] = {"accepted_steps": 128, "reason": "EXCEPTION", "classified": result}

    def test_existing_cost_ignores_unfinished_logged_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arm = root / "A_P"
            arm.mkdir()
            (arm / "steps.jsonl").write_text(json.dumps({"fit_E": {"n_updates": 123}}) + "\n")
            with patch.object(m2, "RUNS", root):
                result = m2.existing_m2_cost()
            self.assertEqual(result["adam"], 0)
        OBS["missing_summary_cost"] = {"committed_row_updates": 123, "reported_cost": result}

    def test_field_benefit_flag_ignores_cost_and_second_random(self):
        summaries = {
            "B-P": {"status": "PASS", "accepted_steps": 128, "elapsed_s": 200, "budget": {"adam": 200}},
            "B-R": {"status": "PASS", "accepted_steps": 128, "elapsed_s": 100, "budget": {"adam": 100}},
            "B-R2": {"status": "FAIL", "accepted_steps": 2, "elapsed_s": 50, "budget": {"adam": 50}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "m2_audit.json").write_text(json.dumps({"field_gate_pass_arms": ["B-P", "B-R"]}))
            with patch.object(benefit, "OUT", root), patch.object(benefit, "load_arm_summary", side_effect=summaries.get), \
                 patch.object(benefit, "write_json"), patch.object(benefit, "write_report"), \
                 patch.object(benefit, "update_stage_status"):
                result = benefit.audit_benefit("review-only-no-action")
        self.assertTrue(result["field_gate_benefit_pass"])
        self.assertFalse(result["residual_cost_benefit_pass"])
        self.assertEqual(result["scientific_result"], "FAIL")
        OBS["benefit_flags"] = {key: result[key] for key in (
            "comparable_residual_128", "field_gate_benefit_pass", "residual_cost_benefit_pass", "scientific_result")}


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeReview))
    with Path(__file__).with_name("runtime_counterexamples.json").open("x", encoding="utf-8") as handle:
        json.dump({"review_only": True, "production_updates": 0, "toy_cost": TOY_COST,
                   "tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
                   "observations": OBS}, handle, indent=2)
        handle.write("\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
