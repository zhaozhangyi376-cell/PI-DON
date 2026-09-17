"""Install-time runner for the random-init clean low-lr 128-step diagnostic."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_state import ensure_task as ensure_plan_task

ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-128-LOWLR-RANDOM"
PROTOCOL = "docs/plans/2026-09-16-random-low-lr-128-protocol.md"
OUTPUT = "evidence/server_resource_v1/random_low_lr128"


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
        "title": "随机初始化低学习率128步对照",
        "status": "READY",
        "depends": [],
        "reason": "检验随机初始化同规则64步通过后能否到128，以及是否复现clean128的Ex/Ey分量门失败",
        "evidence": [],
        "kind": "diagnostic",
        "scientific_result": "NOT_RUN",
        "execution_plan": PROTOCOL,
        "summary": "random init; lr=1e-4, tol=1e-5, max_inner=60000, target=128.",
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
            "--question", "SR-128-LOWLR-RANDOM: can random init reach 128 and pass the 128 field gate?",
            "--expected", "Run one random-init 128-step trajectory with lr=1e-4 and tol=1e-5; write all evidence; do not start 1024 automatically",
            "--success", "128-step diagnostic evidence with cost and field gates, or preserved FAIL/RESOURCE_LIMIT/INCOMPLETE evidence",
            "--failure", "Stop this branch, keep raw failure/checkpoint evidence, and do not alter thresholds or rerun failed actions",
            "--protocol", PROTOCOL,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action()
    if action is None:
        print("Could not resolve active SR-128-LOWLR-RANDOM action.", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-128-LOWLR-RANDOM random-init strict 128-step field diagnostic",
        "--", sys.executable, "run.py", "--action", action,
        "server_short_tol_probe", "--action-id", action,
        "--device", "cuda",
        "--init", "random",
        "--tol", "1e-5",
        "--lr", "1e-4",
        "--target-steps", "128",
        "--output-name", "random_low_lr128",
        "--per-fit-cap", "60000",
        "--overall-adam-cap", "1000000",
        "--fit-progress-every", "500",
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
            f"SR-128-LOWLR-RANDOM delivery {status}; scientific_result={summary.get('scientific_result')}; "
            f"accepted_steps={summary.get('accepted_steps')}; adam={summary.get('new_adam_updates')}; "
            f"field_gate_64={(summary.get('field_gate_64') or {}).get('pass')}; "
            f"field_gate_128={(summary.get('field_gate_128') or {}).get('pass')}; long_run_unlocked=False."
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
