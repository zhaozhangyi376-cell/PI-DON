"""Install-time runner for the SR-36E-BUDGET server diagnostic."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_state import ensure_task as ensure_plan_task

ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-36E-BUDGET"
PROTOCOL = "docs/plans/2026-09-16-step36e-budget-probe-protocol.md"
OUTPUT = "evidence/server_resource_v1/step36e_budget_probe"


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
        "title": "第36步E半步预算诊断",
        "status": "READY",
        "depends": [],
        "reason": "SR-64在35步后第36步E半步9000 Adam未达1e-5；从最后合法检查点重放一步，判断是否预算敏感",
        "evidence": [],
        "kind": "diagnostic",
        "scientific_result": "NOT_RUN",
        "execution_plan": PROTOCOL,
        "summary": "从strict64_probe干净checkpoint重放step36；per-fit cap=30000；不解锁64/128/1024/8192。",
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
            "--question", "SR-36E-BUDGET: can SR-64 step 36 pass tol=1e-5 when the per-fit Adam cap is pre-registered at 30000?",
            "--expected", "Replay exactly one physical step from the last clean SR-64 checkpoint; preserve old failure raw; write traces and live progress; do not unlock long runs",
            "--success", "One-step diagnostic PASS or FAIL with summary/report/manifest/steps/checkpoint/failure evidence",
            "--failure", "Keep the new failure现场; do not modify thresholds, do not continue failed weights, and do not start 64/128/1024/8192 from this action",
            "--protocol", PROTOCOL,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action()
    if action is None:
        print("Could not resolve active SR-36E-BUDGET action.", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-36E-BUDGET replay strict64 step36 with larger registered budget",
        "--", sys.executable, "run.py", "--action", action,
        "server_step36e_budget_probe", "--action-id", action,
        "--device", "cuda",
        "--source-run", "evidence/server_resource_v1/strict64_probe",
        "--max-inner", "30000",
        "--fit-progress-every", "500",
        "--output-name", "step36e_budget_probe",
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
            f"SR-36E-BUDGET delivery {status}; scientific_result={summary.get('scientific_result')}; "
            f"new_accepted_steps={summary.get('new_accepted_steps')}; adam={summary.get('new_adam_updates')}; "
            f"E_R={summary.get('e_residual_ratio')}; long_run_unlocked=False."
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

