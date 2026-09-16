"""Import and summarize server_resource_v1 evidence returned from the server."""
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
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_members(zf: zipfile.ZipFile):
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise SystemExit(f"Unsafe zip member: {info.filename}")
        yield info


def find_dir(base: Path, name: str) -> Path:
    matches = [p for p in base.rglob(name) if p.is_dir() and (p / "summary.json").exists()]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {name}/summary.json in imported evidence, found {len(matches)}")
    return matches[0]


def metric(row, key):
    value = row.get("metrics", {}).get(key)
    return "N/A" if value is None else f"{value:.6g}"


def update_task(plan, task_id: str, status: str, evidence, summary: str):
    for task in plan["tasks"]:
        if task["id"] == task_id:
            task["status"] = status
            task["evidence"] = evidence
            task["summary"] = summary
            return
    raise SystemExit(f"Task not found: {task_id}")


def task_status(plan, task_id: str) -> str:
    for task in plan["tasks"]:
        if task["id"] == task_id:
            return task["status"]
    raise SystemExit(f"Task not found: {task_id}")


def make_report(import_dir: Path, compare_dir: Path, perf_dir: Path, compare, perf):
    lines = [
        "# 服务器首批证据回传审阅",
        "",
        f"导入目录：`{import_dir.relative_to(PROJECT_DIR).as_posix()}`。",
        "",
        "## 结论",
        "",
        f"- SR-COMPARE 交付状态：{compare.get('status')}；科学结论：{compare.get('scientific_result')}",
        f"- SR-PERF 交付状态：{perf.get('status')}；推荐 microbatch：{perf.get('recommended_microbatch')}",
        "- 这两项都是诊断/工程证据，不解锁1024/8192，也不把旧G128失败改判。",
        "",
        "## S1R完整性",
        "",
    ]
    audit = compare.get("s1r_audit", {})
    lines.append(f"- audit status：{audit.get('status')}")
    for key, value in sorted(audit.get("checks", {}).items()):
        lines.append(f"- {key}: {value}")
    if audit.get("missing"):
        lines.append(f"- missing: {audit['missing']}")
    lines += [
        "",
        "## 三模型同题诊断",
        "",
        "| 模型 | 网格 | 状态 | global nMAE | 宏nMAE | relL2 p90 | Eq5 MRE | 逐样本<=1% |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in compare.get("diagnostic_scores", []):
        m = row.get("metrics", {})
        gate = m.get("per_sample_gate_count", "N/A")
        lines.append(
            "| "
            + " | ".join(
                [
                    row.get("model", "N/A"),
                    row.get("grid", "N/A"),
                    row.get("status", "N/A"),
                    metric(row, "global_nmae_mean"),
                    metric(row, "macro_nmae_mean"),
                    metric(row, "global_rel_l2_p90"),
                    metric(row, "macro_mre_eq5_mean"),
                    str(gate),
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## GV100吞吐诊断",
        "",
        "| microbatch | 状态 | 已提交更新 | 中位计时更新(s) | peak allocated GiB | 一步等价 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in perf.get("arms", []):
        peak = row.get("peak_allocated_bytes")
        peak_gib = "N/A" if peak is None else f"{peak / (1024**3):.3f}"
        timed = row.get("median_timed_update_s")
        timed_s = "N/A" if timed is None else f"{timed:.6g}"
        eq = row.get("first_step_equivalence", {}).get("pass")
        lines.append(
            f"| {row.get('microbatch')} | {row.get('status')} | {row.get('updates')} | "
            f"{timed_s} | {peak_gib} | {eq} |"
        )
    lines += [
        "",
        "## 后续动作",
        "",
        "SR-DESIGN现在可以进入只读设计阶段：基于上述指标只冻结一个S1干预和一个在线干预。"
        "在新协议冻结前，不启动新的长训练；即便之后SR-SHORT通过128，也必须按首次更新前登记的累计预算进入长程。",
        "",
        "原始服务器证据保存在导入目录；本报告只做本地索引和摘要，不修改服务器原始记录。",
    ]
    report = ROOT / "server_return_review.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", help="Zip created on the server from evidence/server_resource_v1 and records/project ledgers")
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
        members = list(safe_members(zf))
        zf.extractall(import_dir, members=members)

    compare_dir = find_dir(import_dir, "phase1_compare")
    perf_dir = find_dir(import_dir, "compute_probe")
    compare = read_json(compare_dir / "summary.json")
    perf = read_json(perf_dir / "summary.json")
    report = make_report(import_dir, compare_dir, perf_dir, compare, perf)

    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    evidence_compare = [
        compare_dir.relative_to(PROJECT_DIR).as_posix() + "/summary.json",
        compare_dir.relative_to(PROJECT_DIR).as_posix() + "/REPORT.md",
        report.relative_to(PROJECT_DIR).as_posix(),
    ]
    evidence_perf = [
        perf_dir.relative_to(PROJECT_DIR).as_posix() + "/summary.json",
        perf_dir.relative_to(PROJECT_DIR).as_posix() + "/REPORT.md",
        report.relative_to(PROJECT_DIR).as_posix(),
    ]
    update_task(
        plan,
        "SR-COMPARE",
        "PASS" if compare.get("status") == "PASS" else "INCOMPLETE",
        evidence_compare,
        "Server returned phase1 comparison evidence; delivery reviewed locally. Scientific result remains diagnostic/not applicable.",
    )
    update_task(
        plan,
        "SR-PERF",
        "PASS" if perf.get("status") == "PASS" else "INCOMPLETE",
        evidence_perf,
        f"Server returned compute probe evidence; recommended_microbatch={perf.get('recommended_microbatch')}. Scientific result remains diagnostic/not applicable.",
    )
    if task_status(plan, "SR-COMPARE") == "PASS" and task_status(plan, "SR-PERF") == "PASS":
        for task in plan["tasks"]:
            if task["id"] == "SR-DESIGN" and task["status"] == "TODO":
                task["status"] = "READY"
                task["summary"] = "SR-COMPARE and SR-PERF delivery evidence imported; ready for a zero-update design decision."
        plan["current_task"] = "SR-DESIGN"
    write_json(plan_path, plan)

    print(json.dumps({
        "status": "PASS",
        "import_dir": str(import_dir),
        "report": str(report),
        "compare_status": compare.get("status"),
        "perf_status": perf.get("status"),
        "recommended_microbatch": perf.get("recommended_microbatch"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
