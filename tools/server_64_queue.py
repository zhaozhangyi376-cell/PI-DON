"""Install-time runner for the SR-64 server probe."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-64"
PROTOCOL = "docs/plans/2026-09-15-server-64-protocol.md"
OUTPUT = "evidence/server_resource_v1/strict64_probe"


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
            "title": "64步严格在线场门验证",
            "status": "READY",
            "depends": ["SR-MICRO16"],
            "reason": "验证9000 Adam半步预算能否越过旧57-58步场门瓶颈并通过64步场门",
            "evidence": [],
            "kind": "delivery",
            "scientific_result": "NOT_RUN",
            "execution_plan": PROTOCOL,
            "summary": "tol=1e-5, per-fit cap=9000, target=64 steps; no 128/1024 unlock.",
        })
    else:
        tasks[TASK].update({"status": "READY", "depends": ["SR-MICRO16"], "execution_plan": PROTOCOL})
    plan["current_task"] = TASK
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
            "--question", "SR-64: can a strict tol=1e-5 online trajectory complete 64 full steps and pass the step-64 field gate?",
            "--expected", "Run 64 full steps from the old lr1e3 DCO checkpoint; write field metrics and failure现场; do not start 128/1024",
            "--success", "64 accepted steps plus step-64 field gate pass, or a preserved FAIL/RESOURCE_LIMIT/INCOMPLETE现场",
            "--failure", "Stop this branch, keep raw failure/checkpoint evidence, and do not alter old thresholds or rerun failed actions",
            "--protocol", PROTOCOL,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action()
    if action is None:
        print("Could not resolve active SR-64 action.", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-64 strict 64-step online field gate",
        "--", sys.executable, "run.py", "--action", action,
        "server_short_tol_probe", "--action-id", action,
        "--device", "cuda",
        "--tol", "1e-5",
        "--target-steps", "64",
        "--output-name", "strict64_probe",
        "--per-fit-cap", "9000",
        "--overall-adam-cap", "150000",
        "--protocol", PROTOCOL,
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
            f"SR-64 delivery {status}; scientific_result={summary.get('scientific_result')}; "
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
