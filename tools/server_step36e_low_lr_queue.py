"""Install-time runner for SR-36E low-learning-rate diagnostics."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK = "SR-36E-LOWLR"
PROTOCOL = "docs/plans/2026-09-16-step36e-low-lr-probe-protocol.md"
OUTPUTS = [
    ("step36e_lr1e4_probe", "1e-4"),
    ("step36e_lr5e5_probe", "5e-5"),
]


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
        "title": "第36步低学习率诊断",
        "status": "READY",
        "depends": [],
        "reason": "SR-36E-BUDGET在1e-5门槛附近震荡，检验是否学习率敏感而非单纯预算不足",
        "evidence": [],
        "kind": "diagnostic",
        "scientific_result": "NOT_RUN",
        "execution_plan": PROTOCOL,
        "summary": "从strict64_probe干净checkpoint重放step36；低学习率单步诊断，不解锁长程。",
    }
    if TASK not in tasks:
        plan["tasks"].append(task)
    else:
        tasks[TASK].update(task)
    plan["current_task"] = TASK
    write_json(plan_path, plan)


def run(cmd, *, env=None):
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False, env=env)


def start_action() -> str | None:
    action = active_action()
    if action is not None:
        return action
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    start = subprocess.run([
        sys.executable, "run.py", "project_harness", "start", TASK,
        "--question", "SR-36E-LOWLR: can the same step-36 replay pass tol=1e-5 with a lower pre-registered Adam learning rate?",
        "--expected", "Run one-step diagnostics from the clean SR-64 checkpoint at lr=1e-4, then lr=5e-5 only if needed; preserve all failure evidence",
        "--success", "A diagnostic PASS/FAIL with summaries, reports, manifests, and lab_log records for each attempted arm",
        "--failure", "Do not modify thresholds, do not continue failed weights, and do not start 64/128/1024/8192 from this action",
        "--protocol", PROTOCOL,
    ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
    print(start.stdout or "", end="")
    if start.returncode:
        print(start.stderr or "", end="", file=sys.stderr)
        return None
    return active_action()


def main() -> int:
    os.chdir(ROOT)
    ensure_task()
    run([sys.executable, "run.py", "project_harness", "check"]).check_returncode()
    action = start_action()
    if action is None:
        print("Could not resolve active SR-36E-LOWLR action.", file=sys.stderr)
        return 2

    attempted = []
    final_summary = None
    rc_total = 0
    for output, lr in OUTPUTS:
        out_dir = ROOT / "evidence/server_resource_v1" / output
        if out_dir.exists() and not (out_dir / "summary.json").exists():
            print(f"{output} exists without summary.json; preserve现场 and inspect before retrying.", file=sys.stderr)
            rc_total = 2
            break
        if not (out_dir / "summary.json").exists():
            cmd = [
                sys.executable, "lab_log.py", "run",
                "-m", f"SR-36E-LOWLR {output}",
                "--", sys.executable, "run.py", "--action", action,
                "server_step36e_budget_probe", "--action-id", action,
                "--device", "cuda",
                "--source-run", "evidence/server_resource_v1/strict64_probe",
                "--max-inner", "60000",
                "--lr", lr,
                "--fit-progress-every", "500",
                "--output-name", output,
                "--protocol", PROTOCOL,
            ]
            rc = run(cmd).returncode
            rc_total = rc_total or rc
        summary_path = out_dir / "summary.json"
        if not summary_path.exists():
            final_summary = None
            break
        summary = read_json(summary_path)
        attempted.append((output, summary))
        final_summary = summary
        if summary.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36":
            break

    status = "INCOMPLETE"
    scientific = "INCOMPLETE"
    summary_text = f"process exit {rc_total}; summary missing"
    evidence = [PROTOCOL]
    if attempted:
        best = next((s for _, s in attempted if s.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"), attempted[-1][1])
        status = "PASS" if best.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36" else "FAIL"
        scientific = best.get("scientific_result", "INCOMPLETE")
        summary_text = (
            f"SR-36E-LOWLR delivery {status}; scientific_result={scientific}; "
            f"attempts={len(attempted)}; best/new_accepted_steps={best.get('new_accepted_steps')}; "
            f"adam={best.get('new_adam_updates')}; E_R={best.get('e_residual_ratio')}; long_run_unlocked=False."
        )
        for output, _summary in attempted:
            evidence += [
                f"evidence/server_resource_v1/{output}/summary.json",
                f"evidence/server_resource_v1/{output}/REPORT.md",
                f"evidence/server_resource_v1/{output}/manifest.json",
            ]
    finish_status = status if status in {"PASS", "FAIL", "RESOURCE_LIMIT", "INCOMPLETE"} else "INCOMPLETE"
    finish = [sys.executable, "run.py", "project_harness", "finish", action,
              "--status", finish_status, "--summary", summary_text]
    for item in evidence:
        finish += ["--evidence", item]
    run(finish).check_returncode()
    return rc_total


if __name__ == "__main__":
    raise SystemExit(main())

