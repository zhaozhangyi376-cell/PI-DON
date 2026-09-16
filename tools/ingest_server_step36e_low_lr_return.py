"""Import and summarize returned SR-36E-LOWLR server evidence."""
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
TASK_ID = "SR-36E-LOWLR"
PROTOCOL = "docs/plans/2026-09-16-step36e-low-lr-probe-protocol.md"


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


def find_probes(base: Path) -> list[Path]:
    probes = []
    for name in ("step36e_lr1e4_probe", "step36e_lr5e5_probe"):
        matches = [p for p in base.rglob(name) if p.is_dir() and (p / "summary.json").exists()]
        probes.extend(matches)
    if not probes:
        raise SystemExit("Expected at least one step36e low-lr probe summary")
    return probes


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


def make_report(import_dir: Path, probe_dirs: list[Path], summaries: list[dict], rows_by_probe: dict[str, list[dict]]) -> Path:
    best = next((s for s in summaries if s.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"), summaries[-1])
    best_probe = probe_dirs[summaries.index(best)]
    row = best.get("step_row") or ((rows_by_probe.get(best_probe.name) or [{}])[-1])
    fit_h = fit_brief(row, "fit_H")
    fit_e = fit_brief(row, "fit_E")
    conclusion = (
        "lr=1e-4 单步诊断通过：第36步瓶颈主要表现为学习率/优化震荡敏感，"
        "不是单纯预算不足，也不是已证明的网络表示硬失败。该结论仍只是一阶诊断，"
        "不能改判SR-64，也不能解锁128/1024/8192。"
        if best.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"
        else
        "低学习率诊断仍未使第36步通过；下一步应转向目标尺度、分量残差和表示能力分析。"
    )
    lines = [
        "# SR-36E-LOWLR 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 尝试臂数：`{len(summaries)}`",
        f"- 最佳交付状态：`{best.get('status')}`",
        f"- 最佳诊断科学状态：`{best.get('scientific_result')}`",
        f"- 来源检查点：`{best.get('source_checkpoint')}`",
        f"- 来源已接受步：`{best.get('source_accepted_steps')}`",
        f"- 重放后已接受步：`{best.get('accepted_steps_after')}`",
        f"- 新接受步数：`{best.get('new_accepted_steps')}`",
        f"- 原学习率/诊断学习率：`{best.get('original_lr')}` / `{best.get('diagnostic_lr')}`",
        f"- Adam更新：`{best.get('new_adam_updates')}`；closure：`{best.get('new_closures')}`",
        f"- wall time：`{fmt(best.get('elapsed_s'), 4)} s`",
        f"- 结论边界：{conclusion}",
        "",
        "## 各臂汇总",
        "",
        "| 臂 | status | scientific | lr | accepted_after | new_steps | Adam | E_R | E_updates | crosses_1e-5 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for probe, summary in zip(probe_dirs, summaries):
        lines.append(
            f"| {probe.name} | {summary.get('status')} | {summary.get('scientific_result')} | "
            f"{summary.get('diagnostic_lr')} | {summary.get('accepted_steps_after')} | "
            f"{summary.get('new_accepted_steps')} | {summary.get('new_adam_updates')} | "
            f"{fmt(summary.get('e_residual_ratio'), 8)} | {summary.get('e_updates')} | "
            f"{summary.get('e_crosses_1e_minus_5')} |"
        )
    lines += [
        "",
        "## 最佳臂半步拟合",
        "",
        f"- H：R=`{fmt(fit_h.get('residual_ratio'), 8)}`，updates=`{fit_h.get('updates')}`，"
        f"target_ss=`{fmt(fit_h.get('target_ss'), 8)}`，stop=`{fit_h.get('stop_reason')}`，passed=`{fit_h.get('passed')}`",
        f"- E：R=`{fmt(fit_e.get('residual_ratio'), 8)}`，updates=`{fit_e.get('updates')}`，"
        f"target_ss=`{fmt(fit_e.get('target_ss'), 8)}`，stop=`{fit_e.get('stop_reason')}`，passed=`{fit_e.get('passed')}`",
        "",
        "## 证据",
        "",
    ]
    for probe in probe_dirs:
        lines += [
            f"- {probe.name} summary: `{relative(probe / 'summary.json')}`",
            f"- {probe.name} steps: `{relative(probe / 'steps.jsonl')}`",
            f"- {probe.name} report: `{relative(probe / 'REPORT.md')}`",
            f"- {probe.name} manifest: `{relative(probe / 'manifest.json')}`",
        ]
    report = ROOT / "step36e_low_lr_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def update_plan(probe_dirs: list[Path], report: Path, summaries: list[dict]):
    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    tasks = {task["id"]: task for task in plan["tasks"]}
    task = tasks.get(TASK_ID)
    if task is None:
        task = {
            "id": TASK_ID,
            "goal_id": plan["goal"]["id"],
            "title": "第36步低学习率诊断",
            "depends": [],
            "reason": "SR-36E失败点学习率敏感性诊断",
            "kind": "diagnostic",
            "execution_plan": PROTOCOL,
        }
        plan["tasks"].append(task)
    best = next((s for s in summaries if s.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"), summaries[-1])
    passed = best.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"
    task["status"] = "PASS" if passed else "FAIL"
    task["scientific_result"] = best.get("scientific_result", "INCOMPLETE")
    evidence = [PROTOCOL, relative(report)]
    for probe in probe_dirs:
        evidence += [
            relative(probe / "summary.json"),
            relative(probe / "REPORT.md"),
            relative(probe / "manifest.json"),
        ]
    task["evidence"] = evidence
    task["summary"] = (
        f"Low-lr step36 diagnostic {'passed' if passed else 'failed'}; "
        f"attempts={len(summaries)}; diagnostic_lr={best.get('diagnostic_lr')}; "
        f"new_accepted_steps={best.get('new_accepted_steps')}; "
        f"adam={best.get('new_adam_updates')}; E_R={best.get('e_residual_ratio')}; "
        "long_run_unlocked=False."
    )
    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "SR-64仍为FAIL；SR-36E-LOWLR显示第36步可由低学习率单步通过，下一步仅可登记局部连续窗口，不能启动128/1024/8192。"
                if passed else
                "SR-64仍为FAIL；低学习率第36步诊断未通过，需转向表示/尺度诊断。"
            )
            gap["status"] = "FAIL"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "服务器SR-36E低学习率诊断证据已回传；所有失败与诊断现场保留"
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

    probe_dirs = find_probes(import_dir)
    summaries = [read_json(probe / "summary.json") for probe in probe_dirs]
    rows_by_probe = {probe.name: read_jsonl(probe / "steps.jsonl") for probe in probe_dirs}
    report = make_report(import_dir, probe_dirs, summaries, rows_by_probe)
    update_plan(probe_dirs, report, summaries)
    best = next((s for s in summaries if s.get("scientific_result") == "DIAGNOSTIC_PASS_STEP36"), summaries[-1])

    print(json.dumps({
        "status": "PASS",
        "import_dir": str(import_dir),
        "report": str(report),
        "attempts": len(summaries),
        "best_status": best.get("status"),
        "scientific_result": best.get("scientific_result"),
        "diagnostic_lr": best.get("diagnostic_lr"),
        "new_accepted_steps": best.get("new_accepted_steps"),
        "adam": best.get("new_adam_updates"),
        "e_residual_ratio": best.get("e_residual_ratio"),
        "long_run_unlocked": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

