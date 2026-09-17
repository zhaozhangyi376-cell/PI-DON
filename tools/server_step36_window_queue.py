"""Install-time runner for the SR-36-48 low-lr local window."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_state import ensure_task as ensure_plan_task

ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-36-48-LOWLR"
PROTOCOL = "docs/plans/2026-09-16-step36-window-low-lr-protocol.md"
OUTPUT = "evidence/server_resource_v1/step36_48_low_lr_window"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_actions():
    path = ROOT / "project/actions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def active_action() -> str | None:
    events = read_actions()
    finished = {event.get("action_id") for event in events if event.get("event") == "finish"}
    for event in reversed(events):
        if event.get("event") == "start" and event.get("task_id") == TASK and event.get("action_id") not in finished:
            return event.get("action_id")
    return None


def ensure_task():
    plan_path = ROOT / "project/plan.json"
    plan = read_json(plan_path)
    tasks = {task["id"]: task for task in plan["tasks"]}
    task = {
        "id": TASK,
        "goal_id": plan["goal"]["id"],
        "title": "第36到48步低学习率局部窗口",
        "status": "READY",
        "depends": [],
        "reason": "验证第36步低学习率修复是否能连续维持一小段，而不是只救单步",
        "evidence": [],
        "kind": "diagnostic",
        "scientific_result": "NOT_RUN",
        "execution_plan": PROTOCOL,
        "summary": "从strict64_probe干净checkpoint重放35→48；lr=1e-4；不解锁长程。",
    }
    # F17: an unconditional update rewrote an audited task back to
    # READY/NOT_RUN/evidence=[].  Installing is now idempotent and protects a
    # recorded outcome; see tools/plan_state.py.
    del tasks
    ensure_plan_task(plan, task)
    write_json(plan_path, plan)


def run(cmd, *, env=None):
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False, env=env)


def main() -> int:
    os.chdir(ROOT)
    ensure_task()
    run([sys.executable, "run.py", "project_harness", "check"]).check_returncode()
    out = ROOT / OUTPUT
    if (out / "summary.json").exists():
        print(f"{OUTPUT} already has summary.json; not rerunning.")
        return 0
    if out.exists():
        print(f"{OUTPUT} exists without summary.json; preserve现场 and inspect before retrying.", file=sys.stderr)
        return 2
    action = active_action()
    if action is None:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        start = subprocess.run([
            sys.executable, "run.py", "project_harness", "start", TASK,
            "--question", "SR-36-48-LOWLR: does the lr=1e-4 repair carry from accepted step 35 through accepted step 48?",
            "--expected", "Run a bounded local continuation from the clean SR-64 checkpoint; preserve failure evidence; do not claim formal 64/128 pass",
            "--success", "Diagnostic PASS/FAIL with summary/report/manifest/steps/checkpoint/failure evidence",
            "--failure", "Stop at first failure; do not widen the window or start 64/128/1024/8192 from this action",
            "--protocol", PROTOCOL,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action()
    if action is None:
        print("Could not resolve active SR-36-48-LOWLR action.", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-36-48-LOWLR local continuation from step35",
        "--", sys.executable, "run.py", "--action", action,
        "server_step36_window_probe", "--action-id", action,
        "--device", "cuda",
        "--source-run", "evidence/server_resource_v1/strict64_probe",
        "--target-accepted-steps", "48",
        "--max-inner", "60000",
        "--lr", "1e-4",
        "--fit-progress-every", "500",
        "--output-name", "step36_48_low_lr_window",
    ]
    rc = run(cmd).returncode
    summary_path = ROOT / OUTPUT / "summary.json"
    status = "INCOMPLETE"
    summary_text = f"process exit {rc}; summary missing"
    evidence = [PROTOCOL]
    if summary_path.exists():
        summary = read_json(summary_path)
        status = summary.get("status", "INCOMPLETE")
        summary_text = (
            f"SR-36-48-LOWLR delivery {status}; scientific_result={summary.get('scientific_result')}; "
            f"accepted_after={summary.get('accepted_steps_after')}; new_steps={summary.get('new_accepted_steps')}; "
            f"adam={summary.get('new_adam_updates')}; long_run_unlocked=False."
        )
        evidence += [f"{OUTPUT}/summary.json", f"{OUTPUT}/REPORT.md", f"{OUTPUT}/manifest.json"]
    finish_status = status if status in {"PASS", "FAIL", "RESOURCE_LIMIT", "INCOMPLETE"} else "INCOMPLETE"
    finish = [sys.executable, "run.py", "project_harness", "finish", action,
              "--status", finish_status, "--summary", summary_text]
    for item in evidence:
        finish += ["--evidence", item]
    run(finish).check_returncode()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

