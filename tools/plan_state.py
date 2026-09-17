"""Idempotent plan-state installation for server queue installers.

Code review 20260917, finding F17.

Every ``server_*_queue.py`` installer called ``ensure_task`` BEFORE checking
whether the output already existed, and the existing-task branch was an
unconditional ``tasks[TASK].update(task)`` with a freshly built dictionary
holding ``status="READY"``, ``scientific_result="NOT_RUN"`` and
``evidence=[]``.  Re-running an installer therefore rewrote an audited task --
"delivery PASS, science FAIL, evidence here" became "READY, NOT_RUN, no
evidence" -- and the later "summary.json already exists, not rerunning" guard
came too late to undo it.  No training was repeated, but the plan stopped
describing what had actually been reviewed.

The rules here:

* a task that does not exist yet is inserted exactly as declared;
* a task that exists keeps its terminal status, its scientific result, its
  evidence list and its registered protocol;
* only descriptive fields (title, reason, depends, kind, summary) are
  refreshed, and only when the installer actually declares them;
* re-installing is a no-op that reports what it protected, so an installer can
  be run twice without laundering an audited verdict into READY.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: A status that records an OUTCOME.  It is never replaced by a fresh install.
#: BLOCKED and READY are scheduling states, not outcomes, so an installer may
#: still stage them -- but a BLOCKED task that already carries evidence or a
#: scientific result is protected by the evidence test below all the same.
TERMINAL_STATUS = frozenset({"PASS", "FAIL", "INCOMPLETE"})
#: Fields an installer may refresh even on a task that already has a result.
#: These describe INTENT, so restating them cannot falsify an outcome.
DESCRIPTIVE_FIELDS = ("title", "reason", "kind", "goal_id")
#: Fields that belong to the audited outcome and are never overwritten once
#: one exists.  ``summary`` is in here because after an audit it states the
#: RESULT ("returned PASS; scientific_result=FAIL; adam=261209"), and an
#: installer's pre-run blurb would erase that.  ``depends`` is in here because
#: clearing it would detach the task from the prerequisite it was gated on.
PROTECTED_FIELDS = ("status", "scientific_result", "evidence", "execution_plan",
                    "summary", "depends")


def unmet_dependencies(plan: dict[str, Any], task: dict[str, Any]) -> list[str]:
    """Declared prerequisites that are not audited PASS."""
    by_id = {item.get("id"): item for item in plan.get("tasks", [])}
    depends = task.get("depends")
    if not isinstance(depends, list):
        return []
    return [dep for dep in depends
            if not isinstance(dep, str) or by_id.get(dep, {}).get("status") != "PASS"]


def ensure_task(plan: dict[str, Any], task: dict[str, Any], *,
                set_current: bool = True) -> dict[str, Any]:
    """Insert or idempotently refresh one task.  Returns what happened."""
    task_id = task["id"]
    tasks = plan.setdefault("tasks", [])
    existing = next((item for item in tasks if item.get("id") == task_id), None)
    # F17: resetting a task to READY must not be a way around its prerequisite.
    # Fall back to BLOCKED and say so, rather than staging work whose
    # precondition has not been audited.
    blocked_by = []
    if task.get("status") == "READY":
        merged = dict(existing or {})
        merged.update(task)
        blocked_by = unmet_dependencies(plan, merged)
        if blocked_by:
            task = dict(task)
            task["status"] = "BLOCKED"
    if existing is None:
        tasks.append(dict(task))
        if set_current and not blocked_by:
            plan["current_task"] = task_id
        return {"task_id": task_id, "action": "inserted", "protected": {},
                "blocked_by": blocked_by}

    protected = {field: existing.get(field) for field in PROTECTED_FIELDS
                 if field in existing}
    has_outcome = (existing.get("status") in TERMINAL_STATUS
                   or (existing.get("scientific_result") not in (None, "NOT_RUN"))
                   or bool(existing.get("evidence")))
    updated: dict[str, Any] = {}
    for field in DESCRIPTIVE_FIELDS:
        if field in task and existing.get(field) != task[field]:
            existing[field] = task[field]
            updated[field] = task[field]
    if not has_outcome:
        # Nothing has been recorded for this task yet, so the installer may
        # (re)declare the run-time fields it owns.
        for field in PROTECTED_FIELDS:
            if field in task and existing.get(field) != task[field]:
                existing[field] = task[field]
                updated[field] = task[field]
    if set_current and not has_outcome and not blocked_by:
        plan["current_task"] = task_id
    return {"task_id": task_id,
            "action": "refreshed" if updated else "unchanged",
            "updated_fields": sorted(updated),
            "protected": protected if has_outcome else {},
            "protected_outcome": has_outcome,
            "blocked_by": blocked_by}


def install_task(plan_path: Path, task: dict[str, Any], *,
                 set_current: bool = True) -> dict[str, Any]:
    """Read, ensure and write a plan file, then report the outcome."""
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    report = ensure_task(plan, task, set_current=set_current)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["action"] != "inserted" and report.get("protected_outcome"):
        print(f"  计划状态保护：{report['task_id']} 已有终态/证据，"
              f"保留 {report['protected']}；本次只刷新 {report.get('updated_fields')}")
    if report.get("blocked_by"):
        print(f"  前置未通过：{report['task_id']} 保持 BLOCKED，"
              f"等待 {report['blocked_by']} 审核为 PASS；不以重置 READY 绕过前置。")
    return report
