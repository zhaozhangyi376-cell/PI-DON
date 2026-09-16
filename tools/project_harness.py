"""项目目标、预登记与证据路径检查；本工具不认证科学结果。

直接运行：py -3.11 tools/project_harness.py status
统一入口：py -3.11 run.py project_harness status

plan.json 是经过证据审核的唯一任务状态；actions.jsonl 仅记录行动事件。
finish 的 PASS 表示执行者报告交付完成，不会更改任务、科学结论或依赖门槛。
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
STATES = {
    "TODO", "READY", "RUNNING", "PASS", "FAIL", "RESOURCE_LIMIT",
    "NOT_RUN", "BLOCKED", "INCOMPLETE",
}
PENDING_STATES = {"TODO", "READY", "NOT_RUN"}
RESULT_STATES = {"PASS", "FAIL", "RESOURCE_LIMIT", "NOT_RUN", "BLOCKED", "INCOMPLETE"}


class HarnessError(ValueError):
    """登记、路径或调度约束失败；不代表科学判据失败。"""


def root_path(root=None):
    return Path(root if root is not None else ROOT).resolve()


def read_json(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise HarnessError(f"无法读取 JSON {path}: {exc}") from exc


def load_plan(root=None):
    plan = read_json(root_path(root) / "project" / "plan.json")
    if not isinstance(plan, dict):
        raise HarnessError("project/plan.json 必须是 JSON 对象")
    return plan


def migration_entries(root=None):
    path = root_path(root) / "project" / "migration_map.json"
    if not path.exists():
        return []
    entries = read_json(path).get("files", [])
    if not isinstance(entries, list):
        raise HarnessError("migration_map.json 的 files 必须是列表")
    return [entry for entry in entries if isinstance(entry, dict)
            and isinstance(entry.get("old"), str) and isinstance(entry.get("new"), str)]


def normalized_path(value):
    return str(value).replace("\\", "/").rstrip("/").casefold()


def relative_name(path, root):
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return str(Path(path).resolve())


def resolve_migrations(query, root=None):
    root = root_path(root)
    query = normalized_path(query)
    root_prefix = normalized_path(root) + "/"
    if query.startswith(root_prefix):
        query = query[len(root_prefix):]
    entries = migration_entries(root)
    exact = [entry for entry in entries
             if query in {normalized_path(entry["old"]), normalized_path(entry["new"])}]
    if exact:
        return exact
    by_name = [entry for entry in entries
               if query in {normalized_path(entry["old"]).split("/")[-1],
                            normalized_path(entry["new"]).split("/")[-1]}]
    if by_name:
        return by_name
    return [entry for entry in entries
            if query in normalized_path(entry["old"]) or query in normalized_path(entry["new"])]


def evidence_path(value, root=None):
    """历史路径只接受精确迁移映射，避免同名文件被误认为证据。"""
    root = root_path(root)
    path = Path(value)
    direct = path if path.is_absolute() else root / path
    if direct.exists():
        return direct.resolve()
    query = normalized_path(relative_name(direct, root))
    matches = [entry for entry in migration_entries(root)
               if normalized_path(entry["old"]) == query]
    if len(matches) == 1:
        migrated = Path(matches[0]["new"])
        return (migrated if migrated.is_absolute() else root / migrated).resolve()
    return direct.resolve()


def validate_evidence(value, label, root):
    if not isinstance(value, list):
        return [f"{label} 的 evidence 必须是路径列表"]
    errors = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            errors.append(f"{label} 包含空白或非字符串证据路径")
        elif not evidence_path(entry, root).exists():
            errors.append(f"{label} 的证据不存在：{entry}")
    return errors


def validate_plan(plan, root=None):
    root = root_path(root)
    errors = []
    goal = plan.get("goal")
    if not isinstance(goal, dict) or not str(goal.get("id", "")).strip() or not str(goal.get("objective", "")).strip():
        errors.append("goal 必须包含非空 id 和 objective，所有行动须绑定唯一工程目的")
        goal = {}
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return errors + ["tasks 必须是任务列表"]
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict):
            errors.append("tasks 包含非对象任务")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            errors.append("任务 id 不能为空")
            continue
        if task_id in by_id:
            errors.append(f"任务 id 重复：{task_id}")
        by_id[task_id] = task
        if task.get("goal_id") != goal.get("id") or not goal.get("id"):
            errors.append(f"{task_id} 未绑定唯一目标 {goal.get('id')}")
        if task.get("status") not in STATES:
            errors.append(f"{task_id} 状态非法：{task.get('status')}")
        if not isinstance(task.get("reason"), str) or not task["reason"].strip():
            errors.append(f"{task_id} 缺少 reason（行动如何缩小目标差距）")
        errors.extend(validate_evidence(task.get("evidence"), task_id, root))
        if task.get("status") in {"PASS", "FAIL"} and not task.get("evidence"):
            errors.append(f"{task_id} 标记 {task.get('status')} 但未提供证据")
    for task_id, task in by_id.items():
        depends = task.get("depends")
        if not isinstance(depends, list) or not all(isinstance(dep, str) for dep in depends):
            errors.append(f"{task_id} 的 depends 必须是任务 id 列表")
            continue
        for dep in depends:
            if dep not in by_id:
                errors.append(f"{task_id} 的前置不存在：{dep}")
            elif dep == task_id:
                errors.append(f"{task_id} 不能依赖自身")
            elif task.get("status") == "READY" and by_id[dep].get("status") != "PASS":
                errors.append(f"{task_id} 标记 READY 但前置 {dep} 尚未审核为 PASS")
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            errors.append(f"任务依赖存在环：{task_id}")
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        depends = by_id[task_id].get("depends", [])
        for dep in depends if isinstance(depends, list) else []:
            if isinstance(dep, str) and dep in by_id:
                visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id)
    current = plan.get("current_task")
    if current and current not in by_id:
        errors.append(f"current_task 指向未知任务：{current}")
    for index, gap in enumerate(plan.get("gaps", [])):
        if not isinstance(gap, dict):
            errors.append(f"gaps[{index}] 必须是对象")
        else:
            errors.extend(validate_evidence(gap.get("evidence", []), f"差距 {gap.get('id', index)}", root))
    return errors


def read_events(root=None):
    path = root_path(root) / "project" / "actions.jsonl"
    if not path.exists():
        return []
    events = []
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("事件必须是对象")
                events.append(event)
    except (OSError, ValueError) as exc:
        raise HarnessError(f"行动日志损坏，保留现场并修复，不覆盖日志：{path} 第 {locals().get('number', '?')} 行：{exc}") from exc
    return events


@contextmanager
def ledger_lock(root):
    directory = root / "project"
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".actions.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise HarnessError("另一个进程正在写行动日志；若进程已退出，先核实再删除 project/.actions.lock") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def append_event(event, root):
    with (root / "project" / "actions.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def available_tasks(plan, events):
    by_id = {task["id"]: task for task in plan["tasks"]}
    started = {event.get("task_id") for event in events if event.get("event") == "start"}
    return [task for task in plan["tasks"]
            if task["status"] in PENDING_STATES and task["id"] not in started
            and all(by_id.get(dep, {}).get("status") == "PASS" for dep in task["depends"])]


def checked_plan(root):
    plan = load_plan(root)
    errors = validate_plan(plan, root)
    if errors:
        raise HarnessError("计划检查未通过：\n- " + "\n- ".join(errors))
    return plan


def start_action(args, root):
    with ledger_lock(root):
        plan = checked_plan(root)
        task = next((task for task in plan["tasks"] if task["id"] == args.task), None)
        if task is None:
            raise HarnessError(f"未知任务：{args.task}")
        for name in ("question", "expected", "success", "failure", "protocol"):
            if not getattr(args, name).strip():
                raise HarnessError(f"预登记字段 {name} 不能为空")
        protocol = evidence_path(args.protocol, root)
        if not protocol.is_file():
            raise HarnessError(f"协议文件不存在：{args.protocol}")
        if task not in available_tasks(plan, read_events(root)):
            raise HarnessError(f"{args.task} 尚不具备执行条件，或已登记执行；不得重复执行失败臂或重置预算。先核对 plan 的前置与行动日志。")
        action_id = "A-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        event = {
            "event": "start", "action_id": action_id, "task_id": task["id"],
            "goal_id": plan["goal"]["id"], "at_utc": datetime.now(timezone.utc).isoformat(),
            "question": args.question.strip(), "reason": task["reason"],
            "expected": args.expected.strip(), "success": args.success.strip(), "failure": args.failure.strip(),
            "protocol": relative_name(protocol, root), "protocol_sha256": sha256(protocol),
            "plan_sha256": sha256(root / "project" / "plan.json"),
        }
        append_event(event, root)
    print(f"已预登记 {action_id}，任务 {task['id']}。行动必须回答：{event['question']}")
    print("登记不执行训练，不替代 lab_log，不授权修改科学门槛或恢复失败权重。")
    return action_id


def finish_action(args, root):
    with ledger_lock(root):
        events = read_events(root)
        matches = [event for event in events if event.get("action_id") == args.action]
        starts = [event for event in matches if event.get("event") == "start"]
        if len(starts) != 1:
            raise HarnessError(f"行动必须有且只有一次 start：{args.action}")
        if any(event.get("event") == "finish" for event in matches):
            raise HarnessError(f"行动已结束，保留原始结果；不得覆盖或改判：{args.action}")
        if not args.summary.strip():
            raise HarnessError("结果 summary 不能为空")
        evidence = [path for group in args.evidence for path in group]
        errors = validate_evidence(evidence, args.action, root)
        if not evidence or errors:
            raise HarnessError("结果必须引用存在的证据：" + "; ".join(errors))
        original = starts[0]
        event = {
            "event": "finish", "action_id": args.action, "task_id": original["task_id"],
            "goal_id": original["goal_id"], "at_utc": datetime.now(timezone.utc).isoformat(),
            "reported_status": args.status, "summary": args.summary.strip(),
            "evidence": [relative_name(evidence_path(path, root), root) for path in evidence],
            "scientific_certification": False, "plan_updated": False,
        }
        append_event(event, root)
    print(f"已记录 {args.action} 的报告状态 {args.status}；plan.json 保持不变。")
    print("执行者须审阅真实证据后更新任务状态；报告 PASS 不会自动认证科学门槛或解锁后续任务。")


def show_status(plan, events):
    goal = plan.get("goal", {})
    print(f"唯一工程目的 [{goal.get('id', '未登记')}]：{goal.get('objective', '未登记')}")
    print("目标差距：")
    for gap in plan.get("gaps", []):
        print(f"- [{gap.get('id', '?')}] {gap.get('status', '')} 当前：{gap.get('current', '未记录')}；目标：{gap.get('target', '未记录')}")
    current = plan.get("current_task")
    print(f"当前任务：{current or '未指定'}")
    for task in plan.get("tasks", []):
        print(f"- {task.get('id')} [{task.get('status')}] {task.get('title', '')}；目的：{task.get('reason', '')}")
    finished = {event.get("action_id") for event in events if event.get("event") == "finish"}
    active = [event for event in events if event.get("event") == "start" and event.get("action_id") not in finished]
    for event in active:
        print(f"未结束行动：{event['action_id']} / {event['task_id']} — {event['question']}")
    print("说明：任务 PASS 表示计划交付经审核；论文/科学成功须看独立判据与证据。此工具不做科学认证。")


def build_parser():
    parser = argparse.ArgumentParser(description="PI-DON 目标与行动登记；只管理证据和调度，不认证科学结果")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="显示目标、差距和当前任务")
    commands.add_parser("check", help="检查任务绑定、前置、证据路径和行动日志可读性")
    commands.add_parser("next", help="列出前置满足且未执行的独立任务")
    resolve = commands.add_parser("resolve", help="从迁移清单查询旧文件路径")
    resolve.add_argument("path", help="旧路径、新路径、文件名或子串")
    start = commands.add_parser("start", help="预登记行动；不运行训练")
    start.add_argument("task")
    for field in ("question", "expected", "success", "failure", "protocol"):
        start.add_argument("--" + field, required=True)
    finish = commands.add_parser("finish", help="追加结果事件；不更改计划状态")
    finish.add_argument("action")
    finish.add_argument("--status", choices=sorted(RESULT_STATES), required=True)
    finish.add_argument("--evidence", action="append", nargs="+", required=True)
    finish.add_argument("--summary", required=True)
    return parser


def main(argv=None, root=None):
    args = build_parser().parse_args(argv)
    root = root_path(root)
    try:
        if args.command == "resolve":
            matches = resolve_migrations(args.path, root)
            if not matches:
                raise HarnessError(f"迁移清单中未找到：{args.path}")
            for entry in matches:
                path = evidence_path(entry["new"], root)
                print(f"{entry['old']} -> {entry['new']} [{'存在' if path.exists() else '缺失'}]")
        elif args.command == "start":
            start_action(args, root)
        elif args.command == "finish":
            finish_action(args, root)
        elif args.command == "status":
            show_status(load_plan(root), read_events(root))
        elif args.command == "check":
            checked_plan(root)
            read_events(root)
            print("工程登记检查通过：目标、依赖、状态与证据路径有效；未认证任何科学门槛。")
        elif args.command == "next":
            plan = checked_plan(root)
            tasks = available_tasks(plan, read_events(root))
            for task in tasks:
                print(f"{task['id']} [{task['status']}] {task.get('title', '')} — {task['reason']}")
            if not tasks:
                print("当前无前置满足且未执行的任务；审核已完成行动、核对依赖或登记有独立问题的新任务，不自动重跑失败臂。")
        return 0
    except (HarnessError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
