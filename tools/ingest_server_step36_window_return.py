"""Import and summarize returned SR-36-48-LOWLR server evidence."""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_paths import PROJECT_DIR, configure


configure()


ROOT = PROJECT_DIR / "evidence/server_resource_v1"
TASK_ID = "SR-36-48-LOWLR"
PROTOCOL = "docs/plans/2026-09-16-step36-window-low-lr-protocol.md"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_members(zf: zipfile.ZipFile):
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise SystemExit(f"Unsafe zip member: {info.filename}")
        yield info


def find_probe(base: Path) -> Path:
    matches = [
        p
        for p in base.rglob("step36_48_low_lr_window")
        if p.is_dir() and (p / "summary.json").exists()
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one step36_48_low_lr_window/summary.json, found {len(matches)}")
    return matches[0]


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def fmt(value, precision=6):
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.{precision}g}"
    return str(value)


def row_brief(row: dict[str, Any]) -> dict[str, Any]:
    fit_h = row.get("fit_H") or {}
    fit_e = row.get("fit_E") or {}
    metrics = row.get("six_component_metrics") or {}
    return {
        "accepted_steps": row.get("accepted_steps"),
        "H_R": fit_h.get("residual_ratio"),
        "H_updates": fit_h.get("n_updates"),
        "E_R": fit_e.get("residual_ratio"),
        "E_updates": fit_e.get("n_updates"),
        "Q": metrics.get("global_weighted_relative_l2"),
        "fixed_amplitude_error": metrics.get("fixed_amplitude_error"),
    }


def component_lines(row: dict[str, Any]) -> list[str]:
    metrics = row.get("six_component_metrics") or {}
    components = metrics.get("components") or {}
    lines = ["| 分量 | nMAE | absMAE | weak | relL2 |", "|---|---:|---:|---|---:|"]
    for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
        item = components.get(name) or {}
        lines.append(
            f"| {name} | {fmt(item.get('nmae'), 4)} | {fmt(item.get('absolute_mae'), 4)} | "
            f"{item.get('weak_reference')} | {fmt(item.get('relative_l2'), 4)} |"
        )
    return lines


def make_report(import_dir: Path, probe_dir: Path, summary: dict, rows: list[dict]) -> Path:
    accepted = [row for row in rows if row.get("accepted")]
    last = summary.get("last_accepted_step") or (accepted[-1] if accepted else {})
    step_briefs = [row_brief(row) for row in accepted]
    conclusion = (
        "35→48低学习率局部窗口通过，说明第36步低学习率修复能连续维持一小段；"
        "但这是从SR-64第35步检查点出发的混合历史诊断，不改判SR-64，也不解锁128/1024/8192。"
        if summary.get("scientific_result") == "DIAGNOSTIC_PASS_WINDOW"
        else
        "35→48低学习率局部窗口未通过；应审计失败现场，不应继续扩大窗口。"
    )
    lines = [
        "# SR-36-48-LOWLR 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 诊断科学状态：`{summary.get('scientific_result')}`",
        f"- 来源检查点：`{summary.get('source_checkpoint')}`",
        f"- 来源已接受步：`{summary.get('source_accepted_steps')}`",
        f"- 重放后已接受步：`{summary.get('accepted_steps_after')}`",
        f"- 新接受步数：`{summary.get('new_accepted_steps')}`",
        f"- 目标接受步：`{summary.get('target_accepted_steps')}`",
        f"- 学习率：`{summary.get('diagnostic_lr')}`；max_inner：`{summary.get('diagnostic_max_inner')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 4)} s`",
        f"- 结论边界：{conclusion}",
        "",
        "## 最后一步",
        "",
        f"`{row_brief(last)}`",
        "",
        *component_lines(last),
        "",
        "## 每步摘要",
        "",
        f"`{step_briefs}`",
        "",
        "## 证据",
        "",
        f"- summary: `{relative(probe_dir / 'summary.json')}`",
        f"- steps: `{relative(probe_dir / 'steps.jsonl')}`",
        f"- report: `{relative(probe_dir / 'REPORT.md')}`",
        f"- manifest: `{relative(probe_dir / 'manifest.json')}`",
        f"- checkpoint pointer: `{relative(probe_dir / 'checkpoint_pointer.json')}`",
    ]
    report = ROOT / "step36_window_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def update_plan(probe_dir: Path, report: Path, summary: dict):
    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    tasks = {task["id"]: task for task in plan["tasks"]}
    task = tasks.get(TASK_ID)
    if task is None:
        task = {
            "id": TASK_ID,
            "goal_id": plan["goal"]["id"],
            "title": "第36到48步低学习率局部窗口",
            "depends": [],
            "reason": "第36步低学习率修复局部连续性诊断",
            "kind": "diagnostic",
            "execution_plan": PROTOCOL,
        }
        plan["tasks"].append(task)
    task["status"] = summary.get("status", "INCOMPLETE")
    task["scientific_result"] = summary.get("scientific_result", "INCOMPLETE")
    task["evidence"] = [
        PROTOCOL,
        relative(probe_dir / "summary.json"),
        relative(probe_dir / "REPORT.md"),
        relative(probe_dir / "manifest.json"),
        relative(report),
    ]
    task["summary"] = (
        f"Low-lr local window returned {summary.get('status')}; "
        f"scientific_result={summary.get('scientific_result')}; "
        f"accepted_after={summary.get('accepted_steps_after')}; "
        f"new_steps={summary.get('new_accepted_steps')}; "
        f"adam={summary.get('new_adam_updates')}; long_run_unlocked=False."
    )
    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "SR-64仍为FAIL；SR-36-48-LOWLR局部窗口通过，下一步只允许登记35→64低学习率局部诊断，不能启动128/1024/8192。"
                if summary.get("scientific_result") == "DIAGNOSTIC_PASS_WINDOW"
                else
                "SR-64仍为FAIL；SR-36-48-LOWLR局部窗口失败，需审计新失败现场。"
            )
            gap["status"] = "FAIL"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "服务器SR-36-48低学习率局部窗口证据已回传；新旧现场保留"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
    plan["current_task"] = None
    write_json(plan_path, plan)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path")
    args = parser.parse_args()
    zip_path = Path(args.zip_path)
    if not zip_path.is_absolute():
        zip_path = (PROJECT_DIR / zip_path).resolve()
    if not zip_path.exists():
        raise SystemExit(f"Zip not found: {zip_path}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    import_dir = ROOT / "imports" / f"{zip_path.stem}_{stamp}"
    import_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(zip_path, import_dir / zip_path.name)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(import_dir, members=list(safe_members(zf)))

    probe_dir = find_probe(import_dir)
    summary = read_json(probe_dir / "summary.json")
    rows = read_jsonl(probe_dir / "steps.jsonl")
    report = make_report(import_dir, probe_dir, summary, rows)
    update_plan(probe_dir, report, summary)

    print(json.dumps({
        "status": "PASS",
        "import_dir": str(import_dir),
        "report": str(report),
        "probe_status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "accepted_steps_after": summary.get("accepted_steps_after"),
        "new_accepted_steps": summary.get("new_accepted_steps"),
        "adam": summary.get("new_adam_updates"),
        "long_run_unlocked": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

