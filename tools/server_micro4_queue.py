"""Install-time runner for the SR-MICRO4 server probe."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_state import ensure_task as ensure_plan_task

ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-MICRO4"
PROTOCOL = "docs/plans/2026-09-15-server-micro4-protocol.md"
OUTPUT = "evidence/server_resource_v1/micro4_strict_probe"


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
    if TASK not in tasks:
        plan["tasks"].append({
            "id": TASK,
            "goal_id": plan["goal"]["id"],
            "title": "4步严格在线微型推进",
            "status": "READY",
            "depends": ["SR-E1-BUDGET"],
            "reason": "检验9000 Adam半步预算能否从首个E推广到2到4个完整严格步",
            "evidence": [],
            "kind": "delivery",
            "scientific_result": "NOT_RUN",
            "execution_plan": PROTOCOL,
            "summary": "tol=1e-5, per-fit cap=9000, target=4 steps; no 64/128/1024 unlock.",
        })
    else:
    # F17: an existing task keeps its recorded status, scientific result and
    # evidence; only a task with no recorded outcome may be reset to READY.
        ensure_plan_task(plan, {"id": TASK, "status": "READY", "depends": ["SR-E1-BUDGET"],
                                "execution_plan": PROTOCOL})
    plan["current_task"] = plan.get("current_task") or TASK
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
            "--question", "SR-MICRO4: can a strict tol=1e-5 online trajectory complete 4 full steps with 9000 Adam per half-step?",
            "--expected", "Run only 4 full steps from the old lr1e3 DCO checkpoint; write field metrics and failure现场; do not start 64/128/1024",
            "--success", "4 accepted steps plus step-4 micro field gate pass, or a preserved FAIL/RESOURCE_LIMIT/INCOMPLETE现场",
            "--failure", "Stop this branch, keep raw failure/checkpoint evidence, and do not alter old thresholds or rerun failed actions",
            "--protocol", PROTOCOL,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action()
    if action is None:
        print("Could not resolve active SR-MICRO4 action.", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-MICRO4 strict 4-step online probe",
        "--", sys.executable, "run.py", "--action", action,
        "server_short_tol_probe", "--action-id", action,
        "--device", "cuda",
        "--tol", "1e-5",
        "--target-steps", "4",
        "--output-name", "micro4_strict_probe",
        "--per-fit-cap", "9000",
        "--overall-adam-cap", "72000",
        "--micro-gate-steps", "4",
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
            f"SR-MICRO4 delivery {status}; scientific_result={summary.get('scientific_result')}; "
            f"accepted_steps={summary.get('accepted_steps')}; adam={summary.get('new_adam_updates')}; "
            "long_run_unlocked=False."
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
