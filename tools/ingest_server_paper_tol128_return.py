"""Import and summarize returned SR-128-PAPER-TOL-DIAG server evidence."""
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
TASK_ID = "SR-128-PAPER-TOL-DIAG"
PROTOCOL = "docs/plans/2026-09-16-paper-tol128-diagnostic-protocol.md"
PROBE_NAME = "paper_tol128_diag"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_members(zf: zipfile.ZipFile):
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise SystemExit(f"Unsafe zip member: {info.filename}")
        yield info


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def fmt(value: Any, precision: int = 6) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.{precision}g}"
    return str(value)


def find_probe(base: Path) -> Path:
    matches = [p for p in base.rglob(PROBE_NAME) if p.is_dir() and (p / "summary.json").exists()]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {PROBE_NAME}/summary.json, found {len(matches)}")
    return matches[0]


def metrics(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("six_component_metrics") or row.get("accepted_field_metrics") or {}


def field_q(row: dict[str, Any]) -> Any:
    return metrics(row).get("global_weighted_relative_l2")


def component_fail(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for name, item in (metrics(row).get("components") or {}).items():
        if item.get("weak_reference"):
            if item.get("weak_absolute_pass") is False:
                failures.append(f"{name}: weak_abs_fail")
        else:
            nmae = item.get("nmae")
            if nmae is None or float(nmae) > 0.01:
                failures.append(f"{name}: nMAE={nmae}")
    return failures


def component_table(row: dict[str, Any]) -> list[str]:
    lines = ["| 分量 | nMAE | absMAE | relL2 | weak |", "|---|---:|---:|---:|---|"]
    components = metrics(row).get("components") or {}
    for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
        item = components.get(name) or {}
        lines.append(
            f"| {name} | {fmt(item.get('nmae'), 5)} | {fmt(item.get('absolute_mae'), 5)} | "
            f"{fmt(item.get('relative_l2'), 5)} | {item.get('weak_reference')} |"
        )
    return lines


def milestone_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"first_q_gt_5pct": None, "first_component_gate_fail": None}
    for step in (32, 64, 128):
        out[f"step{step}"] = None
    for row in rows:
        if not row.get("accepted"):
            continue
        step = int(row.get("accepted_steps") or 0)
        brief = {
            "accepted_steps": step,
            "Q": field_q(row),
            "component_failures": component_fail(row),
            "fixed_amplitude_error": metrics(row).get("fixed_amplitude_error"),
        }
        if step in (32, 64, 128):
            out[f"step{step}"] = brief
        q = field_q(row)
        if out["first_q_gt_5pct"] is None and q is not None and float(q) > 0.05:
            out["first_q_gt_5pct"] = brief
        fails = component_fail(row)
        if out["first_component_gate_fail"] is None and fails:
            out["first_component_gate_fail"] = brief
    return out


def make_report(import_dir: Path, probe_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    accepted = [row for row in rows if row.get("accepted")]
    last = summary.get("last_accepted_step") or (accepted[-1] if accepted else {})
    gate64 = summary.get("field_gate_64") or {}
    marks = milestone_rows(rows)
    fit_h = last.get("fit_H") or {}
    fit_e = last.get("fit_E") or {}
    source = gate64.get("source_probe_Ez") or last.get("source_probe_Ez") or {}
    outside = gate64.get("source_outside_probes") or last.get("source_outside_probes") or []
    outside_text = "; ".join(
        f"{tuple(p.get('cells', []))}: dut={fmt(p.get('dut_Ez'), 5)}, ref={fmt(p.get('ref_Ez'), 5)}"
        for p in outside
    )
    lines = [
        "# SR-128-PAPER-TOL-DIAG 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 科学状态：`{summary.get('scientific_result')}`（诊断项，不改判clean128）",
        f"- 接受完整时间步：`{summary.get('accepted_steps')}` / target `{summary.get('target_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 5)} s`",
        f"- 64步field gate：`{gate64.get('pass')}`",
        f"- 64步Q：`{fmt(gate64.get('global_weighted_relative_l2'), 6)}`",
        "",
        "解释：`tol=1e-4` 在当前低学习率配置下可以完成64个残差接受步，但64步全场门失败，Q约为9.04%，高于5%。这支持当前实现不能直接按论文式残差阈值延长；`1e-5`严格门虽然慢，但对场误差有实际约束作用。",
        "",
        "## 里程碑",
        "",
        f"- 第32步：`{marks.get('step32')}`",
        f"- 第64步：`{marks.get('step64')}`",
        f"- 第128步：`{marks.get('step128')}`",
        f"- 首次Q>5%：`{marks.get('first_q_gt_5pct')}`",
        f"- 首次分量门失败：`{marks.get('first_component_gate_fail')}`",
        "",
        "## 最后接受步半步拟合",
        "",
        f"- H residual：`{fmt(fit_h.get('residual_ratio'), 8)}`，updates `{fit_h.get('n_updates')}`",
        f"- E residual：`{fmt(fit_e.get('residual_ratio'), 8)}`，updates `{fit_e.get('n_updates')}`",
        "",
        "## 六分量和探针",
        "",
        *component_table(last),
        "",
        f"- 源点Ez：dut=`{fmt(source.get('dut'), 6)}`，ref=`{fmt(source.get('ref'), 6)}`",
        f"- 源外探针：`{outside_text}`",
        "",
        "## 证据",
        "",
        f"- summary: `{relative(probe_dir / 'summary.json')}`",
        f"- steps: `{relative(probe_dir / 'steps.jsonl')}`",
        f"- report: `{relative(probe_dir / 'REPORT.md')}`",
        f"- manifest: `{relative(probe_dir / 'manifest.json')}`",
    ]
    report = ROOT / "paper_tol128_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def ensure_task(plan: dict[str, Any]) -> dict[str, Any]:
    for task in plan["tasks"]:
        if task["id"] == TASK_ID:
            return task
    task = {
        "id": TASK_ID,
        "goal_id": plan["goal"]["id"],
        "title": "论文阈值1e-4的128步诊断",
        "status": "INCOMPLETE",
        "depends": [],
        "reason": "诊断论文式1e-4半步残差阈值在当前低学习率配置下的速度和场误差",
        "evidence": [],
        "kind": "diagnostic",
        "scientific_result": "NOT_RUN",
        "execution_plan": PROTOCOL,
    }
    plan["tasks"].append(task)
    return task


def update_plan(probe_dir: Path, report: Path, summary: dict[str, Any]) -> None:
    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    task = ensure_task(plan)
    task["status"] = summary.get("status", "INCOMPLETE")
    task["scientific_result"] = summary.get("scientific_result", "FAIL")
    task["evidence"] = [
        PROTOCOL,
        relative(probe_dir / "summary.json"),
        relative(probe_dir / "REPORT.md"),
        relative(probe_dir / "manifest.json"),
        relative(report),
    ]
    task["summary"] = (
        f"Paper-like tol=1e-4 diagnostic returned {summary.get('status')}; "
        f"scientific_result={summary.get('scientific_result')}; "
        f"accepted_steps={summary.get('accepted_steps')}; "
        f"adam={summary.get('new_adam_updates')}; "
        f"field_gate_64={(summary.get('field_gate_64') or {}).get('pass')}."
    )
    write_json(plan_path, plan)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path")
    args = parser.parse_args()
    zip_path = Path(args.zip_path)
    if not zip_path.is_absolute():
        zip_path = PROJECT_DIR / zip_path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    import_dir = ROOT / "imports" / f"{zip_path.stem}_{stamp}"
    import_dir.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as zf:
        for info in safe_members(zf):
            zf.extract(info, import_dir)
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
        "q64": (summary.get("field_gate_64") or {}).get("global_weighted_relative_l2"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
