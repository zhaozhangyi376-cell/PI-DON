"""验证登记与调度边界，不认证任何 PI-DON 科学结论。"""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


_SPEC = importlib.util.spec_from_file_location(
    "project_harness", Path(__file__).resolve().parents[1] / "tools" / "project_harness.py"
)
harness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(harness)


class ProjectHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "project").mkdir()
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "audit.md").write_text("真实证据占位", encoding="utf-8")
        (self.root / "protocol.md").write_text("登记门槛：固定，不因失败更改", encoding="utf-8")
        self.plan = {
            "schema": 1,
            "goal": {"id": "G-REPRO", "objective": "验证论文两阶段机理与收益"},
            "current_task": "M1",
            "gaps": [{"id": "stage2", "target": "严格连续推进", "current": "尚未通过", "evidence": ["evidence/audit.md"]}],
            "tasks": [
                self.task("M0", "PASS", [], ["evidence/audit.md"]),
                self.task("M1", "READY", ["M0"]),
                self.task("M2", "TODO", ["M1"]),
                self.task("S1", "TODO", ["M0"]),
            ],
        }
        self.save_plan()

    @staticmethod
    def task(task_id, status, depends, evidence=None):
        return {"id": task_id, "goal_id": "G-REPRO", "title": task_id,
                "status": status, "depends": depends, "evidence": evidence or [],
                "reason": "通过有区分力的证据缩小目标差距"}

    def save_plan(self):
        (self.root / "project" / "plan.json").write_text(
            json.dumps(self.plan, ensure_ascii=False), encoding="utf-8"
        )

    def command(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = harness.main(list(args), root=self.root)
        return code, output.getvalue(), error.getvalue()

    def start(self, task="M1"):
        return self.command("start", task, "--question", "失败是优化还是接口造成的？",
                            "--expected", "得到可区分证据", "--success", "固定判据通过",
                            "--failure", "保存现场，进入独立任务", "--protocol", "protocol.md")

    def test_unknown_dependency_and_cycles_rejected(self):
        self.plan["tasks"][1]["depends"] = ["UNKNOWN"]
        self.assertTrue(any("前置不存在" in error for error in harness.validate_plan(self.plan, self.root)))
        self.plan["tasks"][1]["depends"] = ["M2"]
        self.assertTrue(any("依赖存在环" in error for error in harness.validate_plan(self.plan, self.root)))

    def test_ready_and_start_cannot_bypass_unreviewed_predecessor(self):
        self.plan["tasks"][2]["status"] = "READY"
        self.assertTrue(any("尚未审核" in error for error in harness.validate_plan(self.plan, self.root)))
        self.plan["tasks"][2]["status"] = "TODO"
        self.save_plan()
        self.assertEqual(self.start("M2")[0], 2)
        self.assertFalse((self.root / "project" / "actions.jsonl").exists())

    def test_failure_is_append_only_and_does_not_stop_independent_task(self):
        plan_before = (self.root / "project" / "plan.json").read_bytes()
        self.assertEqual(self.start()[0], 0)
        events = harness.read_events(self.root)
        action = events[0]["action_id"]
        first_line = (self.root / "project" / "actions.jsonl").read_bytes()
        self.assertEqual(self.command("finish", action, "--status", "FAIL", "--evidence",
                                      "evidence/audit.md", "--summary", "预登记实验失败")[0], 0)
        ledger = (self.root / "project" / "actions.jsonl").read_bytes()
        self.assertTrue(ledger.startswith(first_line))
        self.assertEqual((self.root / "project" / "plan.json").read_bytes(), plan_before)
        pending = harness.available_tasks(self.plan, harness.read_events(self.root))
        self.assertEqual([task["id"] for task in pending], ["S1"])
        self.assertEqual(self.start()[0], 2)
        self.assertEqual(self.command("finish", action, "--status", "PASS", "--evidence",
                                      "evidence/audit.md", "--summary", "试图改判")[0], 2)
        self.assertEqual(len(harness.read_events(self.root)), 2)

    def test_reported_pass_does_not_certify_or_unlock_dependency(self):
        self.assertEqual(self.start()[0], 0)
        action = harness.read_events(self.root)[0]["action_id"]
        self.assertEqual(self.command("finish", action, "--status", "PASS", "--evidence",
                                      "evidence/audit.md", "--summary", "待证据审核")[0], 0)
        result = harness.read_events(self.root)[-1]
        self.assertFalse(result["scientific_certification"])
        self.assertFalse(result["plan_updated"])
        self.assertEqual(self.start("M2")[0], 2)

    def test_reject_missing_evidence_protocol_and_blank_reason(self):
        self.plan["tasks"][1]["evidence"] = ["does_not_exist.md"]
        self.assertTrue(any("证据不存在" in error for error in harness.validate_plan(self.plan, self.root)))
        self.plan["tasks"][1]["evidence"] = []
        self.plan["tasks"][1]["reason"] = "   "
        self.assertTrue(any("reason" in error for error in harness.validate_plan(self.plan, self.root)))
        (self.root / "protocol.md").unlink()
        self.assertEqual(self.start()[0], 2)

    def test_goal_binding_and_unique_ids(self):
        invalid = copy.deepcopy(self.plan)
        invalid["tasks"][1]["goal_id"] = "UNRELATED"
        invalid["tasks"].append(copy.deepcopy(invalid["tasks"][0]))
        errors = harness.validate_plan(invalid, self.root)
        self.assertTrue(any("唯一目标" in error for error in errors))
        self.assertTrue(any("重复" in error for error in errors))

    def test_migration_lookup_and_exact_historical_evidence(self):
        target = self.root / "assets" / "models" / "original.pt"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"preserved")
        (self.root / "project" / "migration_map.json").write_text(json.dumps({"files": [
            {"old": "original.pt", "new": "assets/models/original.pt", "sha256": "historical"}
        ]}), encoding="utf-8")
        self.assertEqual(harness.evidence_path("original.pt", self.root), target.resolve())
        self.assertEqual(harness.resolve_migrations("original", self.root)[0]["old"], "original.pt")
        self.assertEqual(self.command("resolve", "original.pt")[0], 0)
        self.assertEqual(harness.validate_evidence(["original.pt"], "证据", self.root), [])
        self.assertFalse(harness.evidence_path("wrong/original.pt", self.root).exists())

    def test_corrupt_log_preserved_and_blocks_new_action(self):
        path = self.root / "project" / "actions.jsonl"
        original = b'{"event":"start"\n'
        path.write_bytes(original)
        self.assertEqual(self.start()[0], 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.root / "project" / ".actions.lock").exists())


if __name__ == "__main__":
    unittest.main()
