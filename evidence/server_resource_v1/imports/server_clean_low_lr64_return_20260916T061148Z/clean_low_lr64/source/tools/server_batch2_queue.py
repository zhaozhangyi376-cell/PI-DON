"""Install and run the second bounded server batch."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "docs/plans/2026-09-15-server-batch2-protocol.md"
REPAIR_PROTOCOL = "docs/plans/2026-09-15-server-batch2-recorder-fix.md"
REPORT = "evidence/server_resource_v1/SR_DESIGN_REPORT.md"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_actions():
    path = ROOT / "project/actions.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def active_action(task_id: str) -> str | None:
    events = read_actions()
    finished = {event.get("action_id") for event in events if event.get("event") == "finish"}
    for event in reversed(events):
        if event.get("event") == "start" and event.get("task_id") == task_id and event.get("action_id") not in finished:
            return event.get("action_id")
    return None


def ensure_tasks():
    plan_path = ROOT / "project/plan.json"
    plan = read_json(plan_path)
    tasks = {task["id"]: task for task in plan["tasks"]}
    if "SR-DESIGN" not in tasks:
        plan["tasks"].append({
            "id": "SR-DESIGN",
            "goal_id": plan["goal"]["id"],
            "title": "根据首批证据冻结一个有区分力的新干预",
            "status": "PASS",
            "depends": ["SR-COMPARE", "SR-PERF"],
            "reason": "根据首批证据冻结一个有区分力的新干预",
            "evidence": [REPORT],
            "kind": "delivery",
            "scientific_result": "NOT_APPLICABLE",
            "execution_plan": PROTOCOL,
        })
    else:
        tasks["SR-DESIGN"].update({
            "status": "PASS",
            "evidence": [REPORT],
            "scientific_result": "NOT_APPLICABLE",
            "execution_plan": PROTOCOL,
            "summary": "Batch2 design froze one tolerance probe; no long run unlocked.",
        })
    tasks = {task["id"]: task for task in plan["tasks"]}
    if "SR-SHORT" not in tasks:
        plan["tasks"].append({
            "id": "SR-SHORT",
            "goal_id": plan["goal"]["id"],
            "title": "条件化新在线干预P/R与64/128场验收",
            "status": "READY",
            "depends": ["SR-DESIGN"],
            "reason": "条件化新在线干预P/R与64/128场验收",
            "evidence": [],
            "kind": "delivery",
            "scientific_result": "NOT_RUN",
            "execution_plan": PROTOCOL,
        })
    elif tasks["SR-SHORT"]["status"] == "BLOCKED":
        tasks["SR-SHORT"].update({"status": "READY", "depends": ["SR-DESIGN"], "execution_plan": PROTOCOL})
    tasks = {task["id"]: task for task in plan["tasks"]}
    next_retry = None
    for retry in range(1, 6):
        previous = ROOT / ("evidence/server_resource_v1/short_tol_probe" if retry == 1 else f"evidence/server_resource_v1/short_tol_probe_r{retry - 1}")
        current = ROOT / f"evidence/server_resource_v1/short_tol_probe_r{retry}"
        if previous.exists() and not (previous / "summary.json").exists() and not current.exists():
            next_retry = retry
            break
    if next_retry is not None:
        task_id = f"SR-SHORT-R{next_retry}"
        if task_id not in tasks:
            plan["tasks"].append({
                "id": task_id,
                "goal_id": plan["goal"]["id"],
                "title": f"记录器修复后的TOL1E5-P短程重试R{next_retry}",
                "status": "READY",
                "depends": ["SR-DESIGN"],
                "reason": "修复记录器API错误后，在新输出目录重跑同一已冻结短程容差探针",
                "evidence": [],
                "kind": "delivery",
                "scientific_result": "NOT_RUN",
                "execution_plan": REPAIR_PROTOCOL,
            })
        elif tasks[task_id]["status"] == "BLOCKED":
            tasks[task_id].update({"status": "READY", "depends": ["SR-DESIGN"], "execution_plan": REPAIR_PROTOCOL})
        plan["current_task"] = task_id
    else:
        plan["current_task"] = "SR-SHORT"
    write_json(plan_path, plan)


def run(cmd):
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False)


def choose_attempt():
    base = ROOT / "evidence/server_resource_v1"
    for retry in range(0, 6):
        name = "short_tol_probe" if retry == 0 else f"short_tol_probe_r{retry}"
        task_id = "SR-SHORT" if retry == 0 else f"SR-SHORT-R{retry}"
        path = base / name
        if (path / "summary.json").exists():
            return {"done": True, "name": name, "task_id": task_id}
        if not path.exists():
            return {"done": False, "name": name, "task_id": task_id}
    raise RuntimeError("too many failed short tolerance probe attempts; inspect evidence before retrying")


def main():
    os.chdir(ROOT)
    ensure_tasks()
    run([sys.executable, "run.py", "project_harness", "check"]).check_returncode()
    attempt = choose_attempt()
    if attempt["done"]:
        print(f"{attempt['name']} already has summary.json; not rerunning.")
        return 0
    task_id = attempt["task_id"]
    output_name = attempt["name"]
    protocol = PROTOCOL if task_id == "SR-SHORT" else REPAIR_PROTOCOL
    action = active_action(task_id)
    if action:
        print(f"Reusing unfinished {task_id} action {action}", flush=True)
    else:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        start = subprocess.run([
            sys.executable, "run.py", "project_harness", "start", task_id,
            "--question", "TOL1E5-P: stricter per-step residual gate short online field test",
            "--expected", "Run one bounded pretrained online tolerance probe to 64 steps, continuing to 128 only if the 64-step field gate passes",
            "--success", "summary, report, steps, checkpoints, failure/raw现场 and field-gate values are written; no long run is started",
            "--failure", "Keep FAIL/RESOURCE_LIMIT现场 and do not alter old G128/S1R conclusions",
            "--protocol", protocol,
        ], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        print(start.stdout or "", end="")
        if start.returncode:
            print(start.stderr or "", end="", file=sys.stderr)
            return start.returncode
        action = active_action(task_id)
        if not action:
            print(f"{task_id} action was not found after registration.", file=sys.stderr)
            return 2
    cmd = [
        sys.executable, "lab_log.py", "run",
        "-m", "SR-SHORT TOL1E5-P bounded 64-step field probe",
        "--", sys.executable, "run.py", "--action", action,
        "server_short_tol_probe", "--action-id", action,
        "--device", "cuda", "--tol", "1e-5",
        "--target-steps", "64", "--output-name", output_name,
        "--continue-to-128-if-pass64",
    ]
    rc = run(cmd).returncode
    summary_path = ROOT / f"evidence/server_resource_v1/{output_name}/summary.json"
    status = "INCOMPLETE"
    summary_text = f"process exit {rc}; summary missing"
    evidence = [REPORT, PROTOCOL, protocol]
    if summary_path.exists():
        summary = read_json(summary_path)
        status = summary.get("status", "INCOMPLETE")
        summary_text = (
            f"TOL1E5-P delivery {status}; scientific_result={summary.get('scientific_result')}; "
            f"accepted_steps={summary.get('accepted_steps')}; adam={summary.get('new_adam_updates')}; "
            f"recovery_eligible={summary.get('recovery_eligible')}."
        )
        evidence += [
            f"evidence/server_resource_v1/{output_name}/summary.json",
            f"evidence/server_resource_v1/{output_name}/REPORT.md",
        ]
    finish_status = status if status in {"PASS", "FAIL", "RESOURCE_LIMIT", "INCOMPLETE"} else "INCOMPLETE"
    finish = [sys.executable, "run.py", "project_harness", "finish", action,
              "--status", finish_status, "--summary", summary_text]
    for item in evidence:
        finish += ["--evidence", item]
    run(finish).check_returncode()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
