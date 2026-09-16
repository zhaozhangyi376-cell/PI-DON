"""Import and summarize returned server batch2 short tolerance probe evidence."""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from project_paths import PROJECT_DIR, configure


configure()


ROOT = PROJECT_DIR / "evidence/server_resource_v1"


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
    matches = [p for p in base.rglob("short_tol_probe_r2") if p.is_dir() and (p / "summary.json").exists()]
    if len(matches) != 1:
        raise SystemExit(f"Expected one short_tol_probe_r2/summary.json, found {len(matches)}")
    return matches[0]


def ensure_task(plan, task_id, title):
    for task in plan["tasks"]:
        if task["id"] == task_id:
            return task
    task = {
        "id": task_id,
        "goal_id": plan["goal"]["id"],
        "title": title,
        "status": "INCOMPLETE",
        "depends": ["SR-DESIGN"],
        "reason": "服务器短程容差探针回传审计",
        "evidence": [],
        "kind": "delivery",
        "scientific_result": "NOT_RUN",
        "execution_plan": "docs/plans/2026-09-15-server-batch2-recorder-fix.md",
    }
    plan["tasks"].append(task)
    return task


def fit_brief(row, name):
    fit = row.get(name) or {}
    return {
        "n_updates": fit.get("n_updates"),
        "n_evals": fit.get("n_evals"),
        "loss_initial": fit.get("loss_initial"),
        "loss_final": fit.get("loss_final"),
        "residual_ratio": fit.get("residual_ratio"),
        "passed": fit.get("passed"),
        "stop_reason": fit.get("stop_reason"),
        "elapsed_s": fit.get("elapsed_s"),
    }


def make_report(import_dir: Path, probe_dir: Path, summary, rows):
    first = rows[0] if rows else {}
    stop_row = summary.get("stop", {}).get("row") or first
    lines = [
        "# SR-SHORT-R2 回传审计",
        "",
        f"导入目录：`{import_dir.relative_to(PROJECT_DIR).as_posix()}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 科学状态：`{summary.get('scientific_result')}`",
        f"- 接受完整时间步：`{summary.get('accepted_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- 恢复资格：`{summary.get('recovery_eligible')}`",
        f"- 停止原因：`{(summary.get('stop') or {}).get('reason')}`",
        "",
        "解释：`tol=1e-5` 在第一完整时间步前即失败，不能进入64/128，也不能解锁1024/8192。"
        "这否定的是“简单收紧单步残差门即可救场”这条工程路线，不改判旧G128失败。",
        "",
        "## 首个/停止行",
        "",
        f"- row accepted: `{stop_row.get('accepted')}`；phase: `{stop_row.get('phase')}`；reason: `{stop_row.get('reason')}`",
        f"- H fit: `{fit_brief(stop_row, 'fit_H')}`",
        f"- E fit: `{fit_brief(stop_row, 'fit_E')}`",
        f"- row cost: `{stop_row.get('row_cost')}`",
        "",
        "## 证据",
        "",
        f"- summary: `{(probe_dir / 'summary.json').relative_to(PROJECT_DIR).as_posix()}`",
        f"- steps: `{(probe_dir / 'steps.jsonl').relative_to(PROJECT_DIR).as_posix()}`",
        f"- report: `{(probe_dir / 'REPORT.md').relative_to(PROJECT_DIR).as_posix()}`",
        "",
        "## 后续建议",
        "",
        "停止继续容差收紧或长程运行。下一步应只读审计失败现场和旧M2第57-58步场门越线机制，"
        "优先检查边界/插入预测/弱参考/场门定义，而不是再开并行训练。",
    ]
    report = ROOT / "batch2_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


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

    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    task = ensure_task(plan, "SR-SHORT-R2", "记录器修复后的TOL1E5-P短程重试R2")
    task["status"] = summary.get("status", "INCOMPLETE")
    task["scientific_result"] = summary.get("scientific_result", "FAIL")
    task["evidence"] = [
        (probe_dir / "summary.json").relative_to(PROJECT_DIR).as_posix(),
        (probe_dir / "REPORT.md").relative_to(PROJECT_DIR).as_posix(),
        report.relative_to(PROJECT_DIR).as_posix(),
    ]
    task["summary"] = (
        f"TOL1E5-P returned {summary.get('status')}; accepted_steps={summary.get('accepted_steps')}; "
        f"adam={summary.get('new_adam_updates')}; no 64/128/1024 unlock."
    )
    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = "TOL1E5-P tol=1e-5 已回传FAIL：0个完整接受步，3000 Adam；简单收紧残差门不能救场"
            gap["status"] = "FAIL"
        if gap.get("id") == "LONG":
            gap["current"] = "无新合格64/128轨迹；1024/8192仍不得启动"
            gap["status"] = "NOT_RUN"
    plan["current_task"] = None
    write_json(plan_path, plan)
    print(json.dumps({
        "status": "PASS",
        "report": str(report),
        "probe_status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "accepted_steps": summary.get("accepted_steps"),
        "adam": summary.get("new_adam_updates"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
