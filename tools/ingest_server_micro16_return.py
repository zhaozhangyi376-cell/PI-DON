"""Import and summarize returned SR-MICRO16 server evidence."""
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
TASK_ID = "SR-MICRO16"
PROTOCOL = "docs/plans/2026-09-15-server-micro16-protocol.md"


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
        for p in base.rglob("micro16_strict_probe")
        if p.is_dir() and (p / "summary.json").exists()
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one micro16_strict_probe/summary.json, found {len(matches)}")
    return matches[0]


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def fmt(value, precision=6):
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.{precision}g}"
    return str(value)


def component_lines(row: dict) -> list[str]:
    metrics = row.get("six_component_metrics") or row.get("accepted_field_metrics") or {}
    components = metrics.get("components") or {}
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
    last = summary.get("last_accepted_step") or {}
    gate = summary.get("field_gate_micro") or {}
    manifest = read_json(probe_dir / "manifest.json") if (probe_dir / "manifest.json").exists() else {}
    source = gate.get("source_probe_Ez") or last.get("source_probe_Ez") or {}
    outside = gate.get("source_outside_probes") or last.get("source_outside_probes") or []
    outside_text = "; ".join(
        f"{tuple(p.get('cells', []))}: dut={fmt(p.get('dut_Ez'), 4)}, ref={fmt(p.get('ref_Ez'), 4)}"
        for p in outside
    )
    fit_h = last.get("fit_H") or {}
    fit_e = last.get("fit_E") or {}
    accepted = [row for row in rows if row.get("accepted")]
    step_costs = [
        {
            "step": row.get("accepted_steps"),
            "H": (row.get("fit_H") or {}).get("n_updates"),
            "E": (row.get("fit_E") or {}).get("n_updates"),
        }
        for row in accepted
    ]
    lines = [
        "# SR-MICRO16 回传审计",
        "",
        f"导入目录：`{relative(import_dir)}`。",
        "",
        "## 结论",
        "",
        f"- 交付状态：`{summary.get('status')}`",
        f"- 科学状态：`{summary.get('scientific_result')}`（16步微型门；不是64/128门）",
        f"- 接受完整时间步：`{summary.get('accepted_steps')}` / target `{summary.get('target_steps')}`",
        f"- Adam更新：`{summary.get('new_adam_updates')}`；closure：`{summary.get('new_closures')}`",
        f"- wall time：`{fmt(summary.get('elapsed_s'), 4)} s`",
        f"- 第16步全局Q：`{fmt(gate.get('global_weighted_relative_l2'), 6)}`；固定源幅误差：`{fmt(gate.get('fixed_amplitude_error'), 6)}`",
        f"- micro field gate：`{gate.get('pass')}`；64/128 field gate：`{summary.get('field_gate_64')}` / `{summary.get('field_gate_128')}`",
        "",
        "解释：这证明当前严格方案可从4步扩展到16步，并且第16步微型场门通过。"
        "它仍不是64/128轨迹认证，也不能启动1024/8192；下一步最多登记32或64步有界验证。",
        "",
        "## 第16步半步拟合",
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
        "## 每步更新数",
        "",
        f"`{step_costs}`",
        "",
        "## 证据",
        "",
        f"- summary: `{relative(probe_dir / 'summary.json')}`",
        f"- steps: `{relative(probe_dir / 'steps.jsonl')}`",
        f"- report: `{relative(probe_dir / 'REPORT.md')}`",
        f"- manifest: `{relative(probe_dir / 'manifest.json')}`",
        f"- protocol in manifest: `{manifest.get('protocol')}`",
    ]
    report = ROOT / "micro16_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def update_plan(probe_dir: Path, report: Path, summary: dict):
    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    for task in plan["tasks"]:
        if task["id"] == TASK_ID:
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
                f"16-step strict micro probe returned {summary.get('status')}; "
                f"scientific_result={summary.get('scientific_result')}; "
                f"accepted_steps={summary.get('accepted_steps')}; adam={summary.get('new_adam_updates')}; "
                "no 64/128/1024 unlock."
            )
            break
    else:
        raise SystemExit(f"Task {TASK_ID} not found in plan")

    for gap in plan.get("gaps", []):
        if gap.get("id") == "SHORT":
            gap["current"] = (
                "SR-MICRO16回传PASS_MICRO：tol=1e-5、每半步9000 Adam下16个完整严格步通过微型场门；"
                "仍未到64/128，长时场传播未认证"
            )
            gap["status"] = "FAIL"
            gap.setdefault("evidence", [])
            if relative(report) not in gap["evidence"]:
                gap["evidence"].append(relative(report))
        elif gap.get("id") == "LONG":
            gap["current"] = "SR-MICRO16只到16步；仍无合格64/128轨迹，1024/8192不得启动"
            gap["status"] = "NOT_RUN"
        elif gap.get("id") == "PROVENANCE":
            gap["current"] = "S1R、服务器首批/第二批、SR-E1-BUDGET、SR-MICRO4、SR-MICRO16证据已回传；新旧失败现场保留"
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
        "micro_gate": (summary.get("field_gate_micro") or {}).get("pass"),
        "long_run_unlocked": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
