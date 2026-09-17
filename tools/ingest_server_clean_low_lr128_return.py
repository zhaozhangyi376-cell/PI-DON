"""Import and summarize returned SR-128-LOWLR-CLEAN server evidence."""
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
TASK_ID = "SR-128-LOWLR-CLEAN"
PROTOCOL = "docs/plans/2026-09-16-clean-low-lr-128-protocol.md"


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
        for p in base.rglob("clean_low_lr128")
        if p.is_dir() and (p / "summary.json").exists()
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one clean_low_lr128/summary.json, found {len(matches)}")
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


def field_q(row: dict[str, Any]):
    return metrics(row).get("global_weighted_relative_l2")


def component_fail(row: dict[str, Any]) -> list[str]:
    failures = []
    for name, item in (metrics(row).get("components") or {}).items():
        if item.get("weak_reference"):
            if item.get("weak_absolute_pass") is False:
                failures.append(f"{name}: weak_abs_fail")
        else:
            nmae = item.get("nmae")
            if nmae is None or float(nmae) > 0.01:
                failures.append(f"{name}: nMAE={nmae}")
    return failures


def milestone_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "first_q_gt_5pct": None,
        "first_component_gate_fail": None,
    }
    wanted = {57, 58, 64, 66, 96, 128}
    for step in wanted:
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
        if step in wanted:
            out[f"step{step}"] = brief
        q = field_q(row)
        if out["first_q_gt_5pct"] is None and q is not None and float(q) > 0.05:
            out["first_q_gt_5pct"] = brief
        fails = component_fail(row)
        if out["first_component_gate_fail"] is None and fails:
            out["first_component_gate_fail"] = brief
    return out


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


def make_report(import_dir: Path, probe_dir: Path, summary: dict, rows: list[dict]) -> Path:
    accepted = [row for row in rows if row.get("accepted")]
    last = summary.get("last_accepted_step") or (accepted[-1] if accepted else {})
    gate64 = summary.get("field_gate_64") or {}
    gate128 = summary.get("field_gate_128") or {}
    manifest = read_json(probe_dir / "manifest.json") if (probe_dir / "manifest.json").exists() else {}
    marks = milestone_rows(rows)
    source = gate128.get("source_probe_Ez") or last.get("source_probe_Ez") or {}
    outside = gate128.get("source_outside_probes") or last.get("source_outside_probes") or []
    outside_text = "; ".join(
        f"{tuple(p.get('cells', []))}: dut={fmt(p.get('dut_Ez'), 4)}, ref={fmt(p.get('ref_Ez'), 4)}"
        for p in outside
    )
    fit_h = last.get("fit_H") or {}
    fit_e = last.get("fit_E") or {}
    conclusion = (
        "clean low-lr128 从0到128通过，且128步场门PASS。可在本地审计后另行登记1024步验证，仍不能直接启动8192。"
        if summary.get("scientific_result") == "PASS_128"
        else "clean low-lr128 未通过或未完成；停止该分支，不启动1024/8192。"
    )
    lines = [
        "# SR-128-LOWLR-CLEAN 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 科学状态：`{summary.get('scientific_result')}`（128步门；不是1024/8192门）",
        f"- 接受完整时间步：`{summary.get('accepted_steps')}` / target `{summary.get('target_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 4)} s`",
        f"- 64步field gate：`{gate64.get('pass') if gate64 else None}`",
        f"- 128步field gate：`{gate128.get('pass') if gate128 else None}`",
        f"- 结论边界：{conclusion}",
        "",
        "## 里程碑检查",
        "",
        f"- 第57步：`{marks.get('step57')}`",
        f"- 第58步：`{marks.get('step58')}`",
        f"- 第64步：`{marks.get('step64')}`",
        f"- 第66步：`{marks.get('step66')}`",
        f"- 第96步：`{marks.get('step96')}`",
        f"- 第128步：`{marks.get('step128')}`",
        f"- 首次Q>5%：`{marks.get('first_q_gt_5pct')}`",
        f"- 首次分量门失败：`{marks.get('first_component_gate_fail')}`",
        "",
        "## 最后/停止步半步拟合",
        "",
        f"- H residual：`{fmt(fit_h.get('residual_ratio'), 8)}`，updates `{fit_h.get('n_updates')}`，target_ss `{fmt(fit_h.get('target_ss'), 8)}`",
        f"- E residual：`{fmt(fit_e.get('residual_ratio'), 8)}`，updates `{fit_e.get('n_updates')}`，target_ss `{fmt(fit_e.get('target_ss'), 8)}`",
        "",
        "## 六分量和探针",
        "",
        *component_lines(last),
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
        f"- protocol in manifest: `{manifest.get('protocol')}`",
    ]
    report = ROOT / "clean_low_lr128_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def ensure_task(plan: dict) -> dict:
    for task in plan["tasks"]:
        if task["id"] == TASK_ID:
            return task
    task = {
        "id": TASK_ID,
        "goal_id": plan["goal"]["id"],
        "title": "从0开始的低学习率128步验证",
        "status": "INCOMPLETE",
        "depends": ["SR-64-LOWLR-CLEAN"],
        "reason": "验证clean low-lr64通过后同配置能否从0到128并通过128场门",
        "evidence": [],
        "kind": "delivery",
        "scientific_result": "NOT_RUN",
        "execution_plan": PROTOCOL,
    }
    plan["tasks"].append(task)
    return task


def update_plan(probe_dir: Path, report: Path, summary: dict):
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
        f"Clean low-lr128 returned {summary.get('status')}; "
        f"scientific_result={summary.get('scientific_result')}; "
        f"accepted_steps={summary.get('accepted_steps')}; adam={summary.get('new_adam_updates')}; "
        "no 1024/8192 unlock without local audit."
    )

    pass128 = summary.get("scientific_result") == "PASS_128"
    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "clean low-lr128 回传PASS_128：128步严格场门通过；仍需另行登记1024。"
                if pass128
                else "clean low-lr128 回传未达PASS_128；不得启动1024/8192。"
            )
            gap["status"] = "PASS" if pass128 else "FAIL"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
        elif gap.get("id") == "LONG":
            gap["current"] = "clean low-lr128不自动解锁1024/8192；本地审计后才可登记1024"
            gap["status"] = "NOT_RUN"
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "服务器clean low-lr128证据已回传；新旧失败现场保留"
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
        "field_gate_128": (summary.get("field_gate_128") or {}).get("pass"),
        "long_run_unlocked": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
