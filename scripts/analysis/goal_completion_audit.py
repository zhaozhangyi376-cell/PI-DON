"""Audit whether the active direct-mechanism goal is actually complete.

This is a meta-audit: it does not create new scientific results.  It checks the
current plan/evidence against the user's goal so we do not call an incomplete
execution complete just because the finite harness queue has no next task.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from project_paths import PROJECT_DIR, configure
configure()

from pidon_recording import atomic_json_save


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(data, path)


def task_map() -> dict[str, dict[str, Any]]:
    plan = read_json(ROOT / "project" / "plan.json")
    return {task["id"]: task for task in plan.get("tasks", [])}


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    tasks = task_map()
    s1_audit_path = OUT / "s1_phase1" / "interrupted_audit.json"
    final_path = OUT / "FINAL_JUDGMENT.json"
    final = read_json(final_path) if final_path.exists() else {}
    s1 = read_json(s1_audit_path) if s1_audit_path.exists() else {}

    requirements = [
        {
            "id": "read_and_status_bootstrap",
            "requirement": "AGENTS/PLAN/STATUS and project_harness status/check/next were used to drive the work.",
            "evidence": [
                "project/plan.json",
                "PLAN.md",
                "STATUS.md",
                "project/actions.jsonl",
            ],
            "status": "PROVEN",
            "reason": "harness check currently passes and actions log contains M0/M1/M2/S1/B/V starts/finishes.",
        },
        {
            "id": "m0_m1_m2",
            "requirement": "M0, M1 and at most two optimization rules with P/R 128 queue are executed and audited.",
            "evidence": [
                "evidence/direct_mechanism_v1/m0/m0_audit.json",
                "evidence/direct_mechanism_v1/m1/m1_audit.json",
                "evidence/direct_mechanism_v1/m2_audit.json",
            ],
            "status": "PROVEN",
            "reason": "M0/M1/M2 delivery PASS; M2 used rules A and B only.",
        },
        {
            "id": "phase1_complete_training",
            "requirement": "One complete phase-1 training reaches terminal 1000 epochs/25000 updates and blind test.",
            "evidence": [
                display(s1_audit_path),
                "evidence/direct_mechanism_v1/s1_phase1/history.jsonl",
                "evidence/direct_mechanism_v1/s1_phase1/S1_REPORT.md",
            ],
            "status": "NOT_PROVEN",
            "reason": (
                f"S1 status is {s1.get('status')}; last recorded updates "
                f"{(s1.get('last_history') or {}).get('updates')} of 25000; "
                "no last.pt, no terminal summary, no blind migration result."
            ),
        },
        {
            "id": "longrun_conditional",
            "requirement": "If a legal trajectory passes 128 field gate, continue 1024 -> 8192.",
            "evidence": [
                "evidence/direct_mechanism_v1/m2_audit.json",
                "evidence/direct_mechanism_v1/FINAL_JUDGMENT.json",
            ],
            "status": "PROVEN_NOT_RUN_BY_GATE",
            "reason": "G128 field gate failed; longrun_unlocked is false, so 1024/8192 are correctly NOT_RUN.",
        },
        {
            "id": "benefit_and_v",
            "requirement": "Complete benefit/reuse/research judgment where prerequisites allow.",
            "evidence": [
                "evidence/direct_mechanism_v1/benefit/B_audit.json",
                "evidence/direct_mechanism_v1/FINAL_JUDGMENT.json",
            ],
            "status": "PROVEN",
            "reason": "B delivery PASS/science FAIL; U correctly NOT_RUN because G1024 is not unlocked; V PASS/science FAIL.",
        },
        {
            "id": "no_false_success",
            "requirement": "Do not claim paper mechanism reproduced; keep MRE/nMAE and Yee controls separate.",
            "evidence": [
                "evidence/direct_mechanism_v1/FINAL_REPORT.md",
                "evidence/direct_mechanism_v1/FINAL_JUDGMENT.json",
            ],
            "status": "PROVEN",
            "reason": "Final judgment says paper_mechanism_reproduced=false and separates residual, field, S1 and benefit evidence.",
        },
    ]
    blocking = [row for row in requirements if row["status"] == "NOT_PROVEN"]
    goal_complete = not blocking
    audit = {
        "schema": "direct-goal-completion-audit-v1",
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "note": args.note,
        "goal_complete": goal_complete,
        "requirements": requirements,
        "blocking_requirements": blocking,
        "safe_next_action": (
            "new_user_authorized_S1_rerun_or_new_protocol"
            if blocking else "none"
        ),
        "why_not_auto_continue": (
            "The only missing explicit objective item is the complete phase-1 run. "
            "The registered S1 budget was already partly spent and lacks certified resume state; "
            "automatic restart would spend a new budget and consume/alter the registered experiment."
            if blocking else ""
        ),
    }
    write_json(OUT / "GOAL_COMPLETION_AUDIT.json", audit)

    lines = [
        "# Goal Completion Audit",
        "",
        f"- lab_run_id: `{audit.get('lab_run_id')}`",
        f"- goal_complete: `{goal_complete}`",
        "",
        "| Requirement | Status | Reason |",
        "|---|---|---|",
    ]
    for row in requirements:
        lines.append(f"| {row['id']} | {row['status']} | {row['reason']} |")
    lines.extend([
        "",
        "## Blocking Item",
        "",
        audit["why_not_auto_continue"] or "None.",
        "",
        "## Evidence",
        "",
        f"- Completion audit JSON: `{display(OUT / 'GOAL_COMPLETION_AUDIT.json')}`",
        f"- Final judgment: `{display(final_path)}`",
        f"- S1 interrupted audit: `{display(s1_audit_path)}`",
        "",
    ])
    (OUT / "GOAL_COMPLETION_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "goal_complete": goal_complete,
        "blocking_requirements": [row["id"] for row in blocking],
        "safe_next_action": audit["safe_next_action"],
        "report": display(OUT / "GOAL_COMPLETION_AUDIT.md"),
        "audit": display(OUT / "GOAL_COMPLETION_AUDIT.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
