"""Isolated CPU reproductions of recording/deployment review findings.

OK means the specified observed behavior was reproduced, not scientific PASS.
All writes by tested functions target temporary fixtures. No real plan changed.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure
configure()

import numpy as np
import torch
import lab_log
import pidon_solve as solve
import server_clean_low_lr128_queue as queue
import ingest_paper01_return as ingest

torch.set_num_threads(1)
OBS = {}


class IntegrityReview(unittest.TestCase):
    def test_reinstall_resets_completed_task_before_rerun_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project").mkdir()
            path = root / "project/plan.json"
            task = {"id": queue.TASK, "status": "PASS", "evidence": ["kept.json"],
                    "scientific_result": "FAIL", "summary": "audited old result"}
            path.write_text(json.dumps({"goal": {"id": "review"}, "tasks": [task]}))
            with patch.object(queue, "ROOT", root):
                queue.ensure_task()
            after = json.loads(path.read_text(encoding="utf-8"))["tasks"][0]
            self.assertEqual(after["status"], "READY")
            self.assertEqual(after["scientific_result"], "NOT_RUN")
            self.assertEqual(after["evidence"], [])
            OBS["queue_reset"] = {"before": task, "after": after}

    def test_lab_output_manifest_silently_drops_small_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = []
            for index in range(26):
                path = root / f"output_{index:02}.txt"
                path.write_text("x" * (index + 1))
                files.append(path)
            fake = SimpleNamespace(stdout=iter(["fixture only\n"]), wait=lambda: 0)
            args = SimpleNamespace(cmd=["review-fixture"], message="review only")
            env = {"git_commit": "fixture", "git_dirty": False, "git_untracked": 0}
            ledger = root / "ledger.jsonl"
            with patch.object(lab_log, "JSONL", str(ledger)), \
                 patch.object(lab_log, "environment", return_value=env), \
                 patch.object(lab_log, "snapshot", side_effect=[{}, {str(p): 1 for p in files}]), \
                 patch.object(lab_log, "launch", return_value=fake), \
                 patch.object(lab_log, "append_markdown"), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(lab_log.do_run(args), 0)
            saved = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["outputs"]), 25)
            self.assertNotIn("output_00.txt", [Path(p["path"]).name for p in saved["outputs"]])
            OBS["lab_truncation"] = {"actual_outputs": 26, "recorded_outputs": 25,
                                     "dropped": "output_00.txt", "explicit_truncation_field": False}

    def test_lab_start_ids_are_not_reserved(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            ledger.write_text('{"id": 1}\n')
            with patch.object(lab_log, "JSONL", str(ledger)):
                first = lab_log.next_id()
                second = lab_log.next_id()
            self.assertEqual(first, second)
            OBS["lab_ids"] = {"two_starts_before_finish": [first, second],
                               "scope": "no reservation; concurrent wrappers can share id"}

    def test_lab_verify_missing_artifact_still_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            missing = Path(directory) / "absent.pt"
            ledger.write_text(json.dumps({"id": 1, "outputs": [
                {"path": str(missing), "sha256": "0" * 64, "bytes": 1}]}) + "\n")
            captured = io.StringIO()
            with patch.object(lab_log, "JSONL", str(ledger)), contextlib.redirect_stdout(captured):
                rc = lab_log.do_verify(SimpleNamespace())
            self.assertEqual(rc, 0)
            self.assertIn("absent.pt", captured.getvalue())
            OBS["lab_verify"] = {"missing_outputs": 1, "returncode": rc}

    def test_history_counter_accepts_duplicate_update_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text('{"update": 25000}\n' * 25000)
            count, last = ingest.count_history(path)
            self.assertEqual((count, last), (25000, 25000))
            OBS["history_counter"] = {"rows": count, "last": last, "unique_updates": 1,
                                       "passes_history_complete_expression": count == last == 25000}

    def test_formal_resume_accepts_old_snapshot_and_replays_logged_step(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "run"
            original_summary = solve._step_summary

            def zero_display_summary(*args):
                result = original_summary(*args)
                # The zero-source fixture has undefined nMAE. Avoid the unrelated
                # CLI final-print formatting error so only resume logic is tested.
                for component in result.get("six_component_metrics", {}).get("components", {}).values():
                    if component.get("nmae") is None or not np.isfinite(component["nmae"]):
                        component["nmae"] = 0.0
                return result

            def call(argv):
                with patch.object(sys, "argv", ["pidon_solve.py", *argv]), \
                     patch.object(solve.fdtd, "source_waveform", side_effect=lambda n, *a: np.zeros(n)), \
                     patch.object(solve, "SOURCE_OUTSIDE_PROBES_CELLS", [(1., 1., 1.)]), \
                     patch.object(solve, "_step_summary", side_effect=zero_display_summary), \
                     patch.object(solve, "diagnose"), contextlib.redirect_stdout(io.StringIO()):
                    solve.main()

            call(["--n", "3", "--levels", "2", "--base", "2", "--init", "random",
                  "--max-inner", "0", "--steps", "2", "--device", "cpu",
                  "--out-dir", str(out), "--checkpoint-every", "1", "--separate-nets"])
            snapshot = out / "snapshot_step_0001.pt"
            old = torch.load(snapshot, map_location="cpu", weights_only=False)
            current = torch.load(out / "checkpoint_latest.pt", map_location="cpu", weights_only=False)
            self.assertEqual(old["accepted_steps"], 1)
            self.assertEqual(current["accepted_steps"], 2)
            config = root / "config.json"
            config.write_text(json.dumps(old["frozen_config"]))
            resume_args = ["--config", str(config), "--resume", str(snapshot), "--out-dir", str(out),
                           "--steps", "3", "--device", "cpu", "--checkpoint-every", "1"]
            with self.assertRaisesRegex(NameError, "Path"):
                call(resume_args)
            OBS["resume_missing_import"] = {"exception": "NameError: name 'Path' is not defined",
                                             "production_resume_reached": False}
            # Isolate the deeper consistency check, not a production edit.
            with patch.object(solve, "Path", Path, create=True):
                call(resume_args)
            rows = [json.loads(line) for line in (out / "steps.jsonl").read_text().splitlines()]
            layers = [r["time_layer"] for r in rows]
            self.assertEqual(len(layers), 4)
            self.assertEqual(layers[1], layers[2])
            OBS["stale_snapshot_resume"] = {
                "old_checkpoint_accepted": old["accepted_steps"],
                "durable_checkpoint_accepted_before_resume": current["accepted_steps"],
                "time_layers_in_log_after_resume": layers,
                "sequence_ids": [r["sequence_id"] for r in rows],
                "conditional_on_test_only_Path_import": True,
                "fixture": "zero source, exact-zero fast path, 0 Adam; nMAE display substituted; interior tiny-grid probe",
            }

    def test_known_snapshot_code_differences_are_newlines_only(self):
        snapshot = ROOT / "evidence/server_resource_v1/dco_value_review_20260916_r1/returned/random_low_lr128/source"
        if not snapshot.exists():
            self.skipTest("historical snapshot not available locally")
        result = {}
        for name in ("fdtd.py", "pidon_solve.py"):
            matches = list(snapshot.rglob(name))
            if len(matches) != 1:
                self.skipTest(f"expected one snapshot for {name}, got {len(matches)}")
            current = (ROOT / "src/pidon" / name).read_bytes()
            old = matches[0].read_bytes()
            result[name] = {"raw_equal": current == old,
                            "lf_equal": current.replace(b"\r\n", b"\n") == old.replace(b"\r\n", b"\n")}
        OBS["current_vs_random128_snapshot"] = result


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(IntegrityReview))
    output = Path(__file__).with_name("integrity_counterexamples_r3.json")
    with output.open("x", encoding="utf-8") as handle:
        json.dump({"review_only": True, "production_updates": 0, "tests": result.testsRun,
                   "failures": len(result.failures), "errors": len(result.errors),
                   "skipped": [(str(test), reason) for test, reason in result.skipped],
                   "observations": OBS}, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
