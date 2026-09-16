"""Install-time runner for the SR-128 server probe."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-128"
DEP = "SR-64"
PROTOCOL = "docs/plans/2026-09-16-server-128-protocol.md"
OUTPUT = "evidence/server_resource_v1/strict128_probe"
DEP_SUMMARY = "evidence/server_resource_v1/strict64_probe/summary.json"


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


def ensure_dependency(plan: dict) -> None:
    dep_summary = ROOT / DEP_SUMMARY
    if not dep_summary.exists():
        return
    summary = read_json(dep_summary)
    if summary.get("scientific_result") != "PASS_64":
        return
    for task in plan["tasks"]:
        if task["id"] == DEP:
            task["status"] = "PASS"
            task["scientific_result"] = "PASS_64"
            task["evidence"] = [
                "docs/plans/2026-09-15-server-64-protocol.md",
                "evidence/server_resource_v1/strict64_probe/summary.json",
                "evidence/server_resource_v1/strict64_probe/REPORT.md",
                "evidence/server_resource_v1/strict64_probe/manifest.json",
            ]
            task["summary"] = (
                f"Server strict64 evidence present: accepted_steps={summary.get('accepted_steps')}; "
                f"scientific_result={summary.get('scientific_result')}; adam={summary.get('new_adam_updates')}; "
                "does not unlock 1024/8192."
            )
            return


def ensure_task():
    plan_path = ROOT / "project/plan.json"
    plan = read_json(plan_path)
    ensure_dependency(plan)
    tasks = {task["id"]: task for task in plan["tasks"]}
    if TASK not in tasks:
        plan["tasks"].append({
            "id": TASK,
            "goal_id": plan["goal"]["id"],
            "title": "128步严格在线场门验证",
            "status": "READY",
            "depends": [DEP],
            "reason": "验证64步通过后同配置能否继续到128步并通过128场门",
            "evidence": [],
            "kind": "delivery",
            "scientific_result": "NOT_RUN",
            "execution_plan": PROTOCOL,
            "summary": "tol=1e-5, per-fit cap=9000, target=128 steps; no 1024/8192 unlock.",
        })
    else:
        tasks[TASK].update({"status": "READY", "depends": [DEP], "execution_plan": PROTOCOL})
    plan["current_task"] = TASK
    write_json(plan_path, plan)


def run(cmd, *, env=None):
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False, env=env)


def main() -> int:
    os.chdir(ROOT)
    ensure_task()
    run([sys.executable, "run.py", "project_harness", "check"]).check_returncode()
    dep_summary = ROOT / DEP_SUMMARY
    if not dep_summary.exists() or read_json(dep_summary).get("scientific_result") != "PASS_64":
        print("SR-64 PASS_64 evidence is required before SR-128.", file=sys.stderr)
        return 2
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
            "--question", "SR-128: can a strict tol=1e-5 online trajectory complete 128 full steps and pass the 128-step field gate?",
            "--expected", "Run 128 full steps only after SR-64 PASS_64; write field metrics and failure现场; do not start 1024",
            "--success", "128 accepted steps plus 64/128 field gates pass, or a preserved FAIL/RESOURCE_LIMIT/INCOMPLETE现场",
            "--failure", "Stop this branch, keep raw failure/checkpoint evidence, and do not alter old thresholds or rerun failed actions",
            "--protocol", PROTOCOL,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action()
    if action is None:
        print("Could not resolve active SR-128 action.", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-128 strict 128-step online field gate",
        "--", sys.executable, "run.py", "--action", action,
        "server_short_tol_probe", "--action-id", action,
        "--device", "cuda",
        "--tol", "1e-5",
        "--target-steps", "128",
        "--output-name", "strict128_probe",
        "--per-fit-cap", "9000",
        "--overall-adam-cap", "320000",
        "--continue-to-128-if-pass64",
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
            f"SR-128 delivery {status}; scientific_result={summary.get('scientific_result')}; "
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
