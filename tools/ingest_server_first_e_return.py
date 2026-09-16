"""Import and summarize returned SR-E1-BUDGET server evidence."""
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
TASK_ID = "SR-E1-BUDGET"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
        for p in base.rglob("first_e_budget_probe")
        if p.is_dir() and (p / "summary.json").exists()
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one first_e_budget_probe/summary.json, found {len(matches)}")
    return matches[0]


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def fmt(value, precision=6):
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.{precision}g}"
    return str(value)


def make_report(import_dir: Path, probe_dir: Path, summary: dict) -> Path:
    cls = summary.get("classification") or {}
    row = summary.get("row") or {}
    fit_e = row.get("fit_E") or {}
    field = row.get("accepted_field_metrics") or {}
    components = field.get("components") or {}
    source = row.get("source_probe_Ez") or {}
    outside = row.get("source_outside_probes") or []
    outside_text = "; ".join(
        f"{tuple(p.get('cells', []))}: dut={fmt(p.get('dut_Ez'), 4)}, ref={fmt(p.get('ref_Ez'), 4)}"
        for p in outside
    )
    comp_line = ", ".join(
        f"{name}: nMAE={fmt(metrics.get('nmae'), 4)}, absMAE={fmt(metrics.get('absolute_mae'), 4)}"
        for name, metrics in components.items()
    )

    lines = [
        "# SR-E1-BUDGET 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 科学状态：`{summary.get('scientific_result')}`（诊断通过，不是连续轨迹通过）",
        f"- 接受完整时间步：`{summary.get('accepted_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 4)} s`",
        f"- 首个E残差比：`{fmt(cls.get('residual_ratio'), 8)}`",
        f"- 1e-4过门：`{fmt((cls.get('crosses_1e_minus_4') or {}).get('updates'))}` Adam；"
        f"1e-5过门：`{fmt((cls.get('crosses_1e_minus_5') or {}).get('updates'))}` Adam",
        f"- long_run_unlocked：`{summary.get('long_run_unlocked')}`；恢复资格：`{summary.get('recovery_eligible')}`",
        "",
        "解释：同一个首个 `E_pending` 目标在3000 Adam时未过 `1e-5`，但在9000上限内于3769 Adam过门。"
        "这说明第一处严格失败至少包含预算/优化收敛速度问题；它不说明后续H/E半步、场传播或64/128门已经合格。",
        "",
        "## 首个E拟合",
        "",
        f"- 初始loss：`{fmt(fit_e.get('loss_initial'), 8)}`",
        f"- 最终loss：`{fmt(fit_e.get('loss_final'), 8)}`",
        f"- target_ss：`{fmt(fit_e.get('target_ss'), 8)}`；target_count：`{fit_e.get('target_count')}`",
        f"- stop_reason：`{fit_e.get('stop_reason')}`；n_evals：`{fit_e.get('n_evals')}`",
        "",
        "## 场与探针（仅第1步诊断）",
        "",
        f"- 六分量：`{comp_line}`",
        f"- global_weighted_relative_l2：`{fmt(field.get('global_weighted_relative_l2'), 6)}`",
        f"- 源点Ez：dut=`{fmt(source.get('dut'), 6)}`，ref=`{fmt(source.get('ref'), 6)}`",
        f"- 源外探针：`{outside_text}`",
        "",
        "## 证据",
        "",
        f"- summary: `{relative(probe_dir / 'summary.json')}`",
        f"- report: `{relative(probe_dir / 'REPORT.md')}`",
        f"- manifest: `{relative(probe_dir / 'manifest.json')}`",
        f"- checkpoint: `{relative(probe_dir / 'checkpoint_A.pt')}`",
        f"- snapshot: `{relative(probe_dir / 'snapshot_step_0001.pt')}`",
        "",
        "## 后续建议",
        "",
        "下一步最多登记一个极小连续严格推进：同一旧lr1e3初始化、tol=1e-5、每半步9000 Adam上限，"
        "只跑2到4个完整步并复算全场/源外探针。若2到4步失败，停止该分支；若通过，再单独登记8到16步，仍不直接启动64/128/1024/8192。",
    ]
    report = ROOT / "first_e_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def update_plan(probe_dir: Path, report: Path, summary: dict):
    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    for task in plan["tasks"]:
        if task["id"] == TASK_ID:
            task["status"] = summary.get("status", "INCOMPLETE")
            task["scientific_result"] = summary.get("scientific_result", "DIAGNOSTIC_PASS")
            task["evidence"] = [
                "docs/plans/2026-09-15-first-e-budget-probe-protocol.md",
                relative(probe_dir / "summary.json"),
                relative(probe_dir / "REPORT.md"),
                relative(probe_dir / "manifest.json"),
                relative(report),
            ]
            cls = summary.get("classification") or {}
            task["summary"] = (
                "First E target reached 1e-5 with "
                f"{summary.get('new_adam_updates')} Adam under 9000 cap; "
                f"residual_ratio={cls.get('residual_ratio')}; diagnostic only; no long unlock."
            )
            break
    else:
        raise SystemExit(f"Task {TASK_ID} not found in plan")

    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "SR-E1-BUDGET回传PASS：同一首个E目标在3769 Adam达到1e-5；"
                "说明首步严格失败含预算/优化因素，但连续轨迹和场传播仍未合格"
            )
            gap["status"] = "FAIL"
            if relative(report) not in gap.get("evidence", []):
                gap.setdefault("evidence", []).append(relative(report))
        elif gap.get("id") == "LONG":
            gap["current"] = "SR-E1-BUDGET只验证首个E半步；仍无合格64/128轨迹，1024/8192不得启动"
            gap["status"] = "NOT_RUN"
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "S1R、服务器首批/第二批、SR-E1-BUDGET证据已回传；新旧失败现场保留"
            if relative(report) not in gap.get("evidence", []):
                gap.setdefault("evidence", []).append(relative(report))
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
    report = make_report(import_dir, probe_dir, summary)
    update_plan(probe_dir, report, summary)

    cls = summary.get("classification") or {}
    print(json.dumps({
        "status": "PASS",
        "import_dir": str(import_dir),
        "report": str(report),
        "probe_status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "accepted_steps": summary.get("accepted_steps"),
        "adam": summary.get("new_adam_updates"),
        "residual_ratio": cls.get("residual_ratio"),
        "long_run_unlocked": summary.get("long_run_unlocked"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
