"""Import and summarize returned SR-64-LOWLR-CLEAN server evidence."""
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
TASK_ID = "SR-64-LOWLR-CLEAN"
PROTOCOL = "docs/plans/2026-09-16-clean-low-lr-64-protocol.md"


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
        for p in base.rglob("clean_low_lr64")
        if p.is_dir() and (p / "summary.json").exists()
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one clean_low_lr64/summary.json, found {len(matches)}")
    return matches[0]


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def fmt(value, precision=6):
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.{precision}g}"
    return str(value)


def metrics(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("six_component_metrics") or row.get("accepted_field_metrics") or {}


def component_lines(row: dict[str, Any]) -> list[str]:
    components = (metrics(row).get("components") or {})
    lines = ["| 分量 | nMAE | absMAE | weak | gate依据 | relL2 |", "|---|---:|---:|---|---|---:|"]
    for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
        item = components.get(name) or {}
        weak = item.get("weak_reference")
        reason = "weak_abs" if weak else "nMAE<=1%"
        lines.append(
            f"| {name} | {fmt(item.get('nmae'), 4)} | {fmt(item.get('absolute_mae'), 4)} | "
            f"{weak} | {reason} | {fmt(item.get('relative_l2'), 4)} |"
        )
    return lines


def row_brief(row: dict[str, Any]) -> dict[str, Any]:
    fit_h = row.get("fit_H") or {}
    fit_e = row.get("fit_E") or {}
    met = metrics(row)
    return {
        "accepted_steps": row.get("accepted_steps"),
        "H_R": fit_h.get("residual_ratio"),
        "H_updates": fit_h.get("n_updates"),
        "E_R": fit_e.get("residual_ratio"),
        "E_updates": fit_e.get("n_updates"),
        "Q": met.get("global_weighted_relative_l2"),
        "fixed_amplitude_error": met.get("fixed_amplitude_error"),
    }


def make_report(import_dir: Path, probe_dir: Path, summary: dict, rows: list[dict]) -> Path:
    accepted = [row for row in rows if row.get("accepted")]
    last = summary.get("last_accepted_step") or (accepted[-1] if accepted else {})
    gate64 = summary.get("field_gate_64") or {}
    conclusion = (
        "clean low-lr64 从0到64通过，且64步场门PASS。可以登记clean low-lr128；仍不能直接启动1024/8192。"
        if summary.get("scientific_result") == "PASS_64"
        else
        "clean low-lr64 未通过64科学门；需要审计失败现场，不能启动128。"
    )
    lines = [
        "# SR-64-LOWLR-CLEAN 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 科学状态：`{summary.get('scientific_result')}`",
        f"- 接受完整时间步：`{summary.get('accepted_steps')}` / target `{summary.get('target_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 4)} s`",
        f"- 64步field gate：`{gate64.get('pass')}`",
        f"- Q/global relL2：`{fmt(gate64.get('global_weighted_relative_l2'), 6)}`",
        f"- fixed amplitude error：`{fmt(gate64.get('fixed_amplitude_error'), 6)}`",
        f"- 结论边界：{conclusion}",
        "",
        "## 最后一步",
        "",
        f"`{row_brief(last)}`",
        "",
        *component_lines(last),
        "",
        "## 探针",
        "",
        f"- 源点Ez：`{gate64.get('source_probe_Ez')}`",
        f"- 源外探针：`{gate64.get('source_outside_probes')}`",
        "",
        "## 证据",
        "",
        f"- summary: `{relative(probe_dir / 'summary.json')}`",
        f"- steps: `{relative(probe_dir / 'steps.jsonl')}`",
        f"- report: `{relative(probe_dir / 'REPORT.md')}`",
        f"- manifest: `{relative(probe_dir / 'manifest.json')}`",
        f"- snapshot64: `{relative(probe_dir / 'snapshot_step_0064.pt')}`",
    ]
    report = ROOT / "clean_low_lr64_return_review.md"
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
            "title": "从0开始的低学习率64步验证",
            "depends": [],
            "reason": "clean low-lr 64 validation",
            "kind": "delivery",
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
        f"Clean low-lr64 returned {summary.get('status')}; scientific_result={summary.get('scientific_result')}; "
        f"accepted_steps={summary.get('accepted_steps')}; adam={summary.get('new_adam_updates')}; "
        f"field_gate_64={(summary.get('field_gate_64') or {}).get('pass')}; long_run_unlocked=False."
    )
    pass64 = summary.get("scientific_result") == "PASS_64"
    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "clean low-lr64 已从0到64通过并过64场门；下一步允许登记clean low-lr128，仍不能启动1024/8192。"
                if pass64 else
                "clean low-lr64 未通过；不能启动128/1024/8192。"
            )
            gap["status"] = "INCOMPLETE" if pass64 else "FAIL"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
        elif gap.get("id") == "LONG":
            gap["current"] = "64通过后仍需128验证；128通过前1024/8192不得启动"
            gap["status"] = "NOT_RUN"
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "服务器clean low-lr64证据已回传并审计；新旧现场保留"
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
        "accepted_steps": summary.get("accepted_steps"),
        "adam": summary.get("new_adam_updates"),
        "field_gate_64": (summary.get("field_gate_64") or {}).get("pass"),
        "recommended_next": "clean_low_lr128" if summary.get("scientific_result") == "PASS_64" else "failure_audit",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

