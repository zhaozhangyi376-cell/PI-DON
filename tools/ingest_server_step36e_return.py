"""Import and summarize returned SR-36E-BUDGET server evidence."""
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
TASK_ID = "SR-36E-BUDGET"
PROTOCOL = "docs/plans/2026-09-16-step36e-budget-probe-protocol.md"


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
        for p in base.rglob("step36e_budget_probe")
        if p.is_dir() and (p / "summary.json").exists()
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one step36e_budget_probe/summary.json, found {len(matches)}")
    return matches[0]


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def fmt(value, precision=6):
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.{precision}g}"
    return str(value)


def fit_brief(row: dict[str, Any], key: str) -> dict[str, Any]:
    fit = row.get(key) or {}
    return {
        "residual_ratio": fit.get("residual_ratio"),
        "updates": fit.get("n_updates"),
        "target_ss": fit.get("target_ss"),
        "stop_reason": fit.get("stop_reason"),
        "passed": fit.get("passed"),
    }


def make_report(import_dir: Path, probe_dir: Path, summary: dict, rows: list[dict]) -> Path:
    row = summary.get("step_row") or (rows[-1] if rows else {})
    fit_h = fit_brief(row, "fit_H")
    fit_e = fit_brief(row, "fit_E")
    conclusion = (
        "第36步在30000 Adam半步预算下通过，说明SR-64的35步失败具有明显预算敏感性；"
        "但这只是单步诊断，不能自动改判SR-64，也不能启动1024/8192。"
        if summary.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"
        else
        "第36步在30000 Adam半步预算下仍未通过；下一步应分析loss曲线、目标能量和表示能力，"
        "不应继续盲目扩大64步。"
    )
    lines = [
        "# SR-36E-BUDGET 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 诊断科学状态：`{summary.get('scientific_result')}`",
        f"- 来源运行：`{summary.get('source_run')}`",
        f"- 来源检查点：`{summary.get('source_checkpoint')}`",
        f"- 来源已接受步：`{summary.get('source_accepted_steps')}`",
        f"- 重放后已接受步：`{summary.get('accepted_steps_after')}`",
        f"- 新接受步数：`{summary.get('new_accepted_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 4)} s`",
        f"- 结论边界：{conclusion}",
        "",
        "## 半步拟合",
        "",
        f"- H：R=`{fmt(fit_h.get('residual_ratio'), 8)}`，updates=`{fit_h.get('updates')}`，"
        f"target_ss=`{fmt(fit_h.get('target_ss'), 8)}`，stop=`{fit_h.get('stop_reason')}`，passed=`{fit_h.get('passed')}`",
        f"- E：R=`{fmt(fit_e.get('residual_ratio'), 8)}`，updates=`{fit_e.get('updates')}`，"
        f"target_ss=`{fmt(fit_e.get('target_ss'), 8)}`，stop=`{fit_e.get('stop_reason')}`，passed=`{fit_e.get('passed')}`",
        f"- E crosses 1e-4：`{summary.get('e_crosses_1e_minus_4')}`",
        f"- E crosses 1e-5：`{summary.get('e_crosses_1e_minus_5')}`",
        "",
        "## 证据",
        "",
        f"- summary: `{relative(probe_dir / 'summary.json')}`",
        f"- steps: `{relative(probe_dir / 'steps.jsonl')}`",
        f"- report: `{relative(probe_dir / 'REPORT.md')}`",
        f"- manifest: `{relative(probe_dir / 'manifest.json')}`",
        f"- checkpoint pointer: `{relative(probe_dir / 'checkpoint_pointer.json')}`",
    ]
    if (probe_dir / "failure_raw_000001_attempt_1.pt").exists():
        lines.append(f"- failure raw: `{relative(probe_dir / 'failure_raw_000001_attempt_1.pt')}`")
    report = ROOT / "step36e_return_review.md"
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
            "title": "第36步E半步预算诊断",
            "depends": [],
            "reason": "SR-64失败点预算敏感性诊断",
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
        f"Step36 diagnostic returned {summary.get('status')}; "
        f"scientific_result={summary.get('scientific_result')}; "
        f"new_accepted_steps={summary.get('new_accepted_steps')}; "
        f"adam={summary.get('new_adam_updates')}; E_R={summary.get('e_residual_ratio')}; "
        "long_run_unlocked=False."
    )
    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "SR-64仍为FAIL；SR-36E-BUDGET已回传，作为失败机理诊断，不改判64/128门。"
            )
            gap["status"] = "FAIL"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "服务器SR-36E诊断证据已回传；旧SR-64失败现场和新诊断现场均保留"
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
        "new_accepted_steps": summary.get("new_accepted_steps"),
        "adam": summary.get("new_adam_updates"),
        "e_residual_ratio": summary.get("e_residual_ratio"),
        "long_run_unlocked": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

