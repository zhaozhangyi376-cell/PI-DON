from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPORT_ROOT = ROOT / "evidence" / "paper01_s1" / "imports"
REVIEW_JSON = ROOT / "evidence" / "paper01_s1" / "paper01_theta_full_return_review.json"
REVIEW_MD = ROOT / "evidence" / "paper01_s1" / "paper01_theta_full_return_review.md"
TASK_ID = "PAPER01-S1-THETA-FULL"
PROTOCOL = "docs/plans/2026-09-17-paper01-theta-full-protocol.md"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def safe_members(archive: zipfile.ZipFile):
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise SystemExit(f"Unsafe zip member: {info.filename}")
        yield info


def find_summary(import_dir: Path) -> Path:
    matches = list(import_dir.rglob("_01/evidence/paper01_theta_full_v1/summary.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one theta-full summary, found {len(matches)}")
    return matches[0]


def review(summary_path: Path, import_dir: Path) -> dict[str, Any]:
    summary = read_json(summary_path)
    variants = summary.get("variants", [])
    variant = variants[0] if variants else {}
    metrics = variant.get("final_metrics", {})
    stats = variant.get("contract_stats", {})
    return {
        "schema": "pidon-paper01-theta-full-return-review-v1",
        "status": "PASS" if summary.get("status") == "PASS" and len(variants) == 1 else "INCOMPLETE",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "import_dir": str(import_dir),
        "summary_path": str(summary_path),
        "parameter_updates": summary.get("parameter_updates"),
        "variant": variant.get("variant"),
        "best_test_mse": variant.get("best_test_mse"),
        "best_update": variant.get("best_update"),
        "macro_nmae_mean": metrics.get("macro_nmae_mean"),
        "rel_l2_p90": metrics.get("global_rel_l2_p90"),
        "mre_eq5_mean": metrics.get("macro_mre_eq5_mean"),
        "ez_amplification_p90": stats.get("ez_amplification_p90"),
        "diagnostic_not_paper_literal": stats.get("diagnostic_not_paper_literal"),
        "long_run_unlocked": False,
    }


def write_report(data: dict[str, Any]) -> None:
    lines = [
        "# PAPER01 theta_min_0p5 完整第一阶段回传审计",
        "",
        f"- 状态：`{data['status']}`；科学含义：`{data['scientific_result']}`",
        f"- 变体：`{data.get('variant')}`",
        f"- 参数更新：`{data.get('parameter_updates')}`",
        f"- best test MSE：`{data.get('best_test_mse')}` at update `{data.get('best_update')}`",
        f"- macro nMAE：`{data.get('macro_nmae_mean')}`",
        f"- relL2 p90：`{data.get('rel_l2_p90')}`",
        f"- Eq.(5) MRE：`{data.get('mre_eq5_mean')}`",
        f"- Ez amp p90：`{data.get('ez_amplification_p90')}`",
        "",
        "## 判读边界",
        "",
        "- 这是受控过滤诊断，不是论文原始配置成功。",
        "- 不改变`PAPER01-S1`科学FAIL，不解锁第二阶段、1024或8192。",
        "- 若结果显著改善，下一步也应先登记盲测/同场换网格评估，而不是直接进入Algorithm 1。",
    ]
    REVIEW_MD.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_plan_update(plan: dict[str, Any], data: dict[str, Any], evidence: list[str]) -> None:
    task = next((item for item in plan.get("tasks", []) if item.get("id") == TASK_ID), None)
    if task is None:
        task = {
            "id": TASK_ID,
            "goal_id": plan["goal"]["id"],
            "title": "PAPER01角度过滤完整第一阶段诊断",
            "depends": ["PAPER01-ABLATION-SMOKE"],
            "reason": "theta_min_0p5短预算优于baseline后登记完整25000 Adam诊断",
            "kind": "diagnostic",
            "execution_plan": PROTOCOL,
        }
        plan.setdefault("tasks", []).append(task)
    task["status"] = data.get("status", "INCOMPLETE")
    task["scientific_result"] = data.get("scientific_result", "DIAGNOSTIC_ONLY")
    task["evidence"] = evidence
    task["summary"] = (
        f"PAPER01 theta full returned {data.get('status')}; updates={data.get('parameter_updates')}; "
        f"macro_nMAE={data.get('macro_nmae_mean')}; relL2_p90={data.get('rel_l2_p90')}; "
        f"Eq5_MRE={data.get('mre_eq5_mean')}; no stage-two or long-run unlock."
    )
    if plan.get("current_task") == TASK_ID:
        plan["current_task"] = None


def update_plan(data: dict[str, Any]) -> None:
    plan_path = ROOT / "project" / "plan.json"
    plan = read_json(plan_path)
    evidence = [PROTOCOL, relative(Path(data["summary_path"])), relative(REVIEW_JSON), relative(REVIEW_MD)]
    apply_plan_update(plan, data, evidence)
    write_json(plan_path, plan)


def ingest(zip_path: Path) -> dict[str, Any]:
    zip_path = zip_path.resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    import_dir = IMPORT_ROOT / f"{zip_path.stem}_{stamp}"
    import_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(zip_path, import_dir / zip_path.name)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(import_dir, members=list(safe_members(archive)))
    summary_path = find_summary(import_dir)
    data = review(summary_path, import_dir)
    write_json(REVIEW_JSON, data)
    write_report(data)
    update_plan(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    data = ingest(args.zip_path)
    print(json.dumps({
        "status": data["status"],
        "import_dir": data["import_dir"],
        "report": str(REVIEW_MD),
        "macro_nmae_mean": data.get("macro_nmae_mean"),
        "rel_l2_p90": data.get("rel_l2_p90"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
