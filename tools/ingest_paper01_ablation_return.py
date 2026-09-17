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
REVIEW_JSON = ROOT / "evidence" / "paper01_s1" / "paper01_ablation_return_review.json"
REVIEW_MD = ROOT / "evidence" / "paper01_s1" / "paper01_ablation_return_review.md"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def unique_import_dir(zip_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return IMPORT_ROOT / f"{zip_path.stem}_{stamp}"


def find_summary(import_dir: Path) -> Path:
    matches = list(import_dir.rglob("_01/evidence/paper01_ablation_v1/summary.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one ablation summary, found {len(matches)}")
    return matches[0]


def review(summary_path: Path, import_dir: Path) -> dict[str, Any]:
    summary = read_json(summary_path)
    variants = summary.get("variants", [])
    rows = []
    for item in variants:
        metrics = item.get("final_metrics", {})
        stats = item.get("contract_stats", {})
        rows.append({
            "variant": item.get("variant"),
            "updates": item.get("parameter_updates"),
            "best_test_mse": item.get("best_test_mse"),
            "macro_nmae_mean": metrics.get("macro_nmae_mean"),
            "rel_l2_p90": metrics.get("global_rel_l2_p90"),
            "mre_eq5_mean": metrics.get("macro_mre_eq5_mean"),
            "ez_amplification_p90": stats.get("ez_amplification_p90"),
            "diagnostic_not_paper_literal": stats.get("diagnostic_not_paper_literal"),
        })
    baseline = next((row for row in rows if row["variant"] == "baseline"), None)
    best = min((row for row in rows if row.get("macro_nmae_mean") is not None),
               key=lambda row: float(row["macro_nmae_mean"]), default=None)
    return {
        "schema": "pidon-paper01-ablation-return-review-v1",
        "status": "PASS" if summary.get("status") == "PASS" and len(rows) == 4 else "INCOMPLETE",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "import_dir": str(import_dir),
        "summary_path": str(summary_path),
        "parameter_updates": summary.get("parameter_updates"),
        "variant_count": len(rows),
        "variants": rows,
        "baseline": baseline,
        "best_macro_nmae_variant": best,
        "long_run_unlocked": False,
    }


def write_report(data: dict[str, Any]) -> None:
    lines = [
        "# PAPER01 消融回传审计",
        "",
        f"- 状态：`{data['status']}`；科学含义：`{data['scientific_result']}`",
        f"- 参数更新：`{data.get('parameter_updates')}`",
        f"- 变体数：`{data.get('variant_count')}`",
        "",
        "| 变体 | updates | best test MSE | macro nMAE | relL2 p90 | Eq.(5) MRE | Ez amp p90 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["variants"]:
        lines.append(
            f"| {row['variant']} | {row['updates']} | {row['best_test_mse']} | "
            f"{row['macro_nmae_mean']} | {row['rel_l2_p90']} | {row['mre_eq5_mean']} | "
            f"{row['ez_amplification_p90']} |"
        )
    best = data.get("best_macro_nmae_variant") or {}
    lines += [
        "",
        f"- macro nMAE 最低短训变体：`{best.get('variant')}`；该结果只用于判断是否值得完整重训。",
        "- 本审计不改变`PAPER01-S1`科学FAIL，不解锁第二阶段、1024或8192。",
    ]
    REVIEW_MD.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ingest(zip_path: Path) -> dict[str, Any]:
    zip_path = zip_path.resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    import_dir = unique_import_dir(zip_path)
    import_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(zip_path, import_dir / zip_path.name)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(import_dir)
    summary_path = find_summary(import_dir)
    data = review(summary_path, import_dir)
    write_json(REVIEW_JSON, data)
    write_report(data)
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
        "best_macro_nmae_variant": (data.get("best_macro_nmae_variant") or {}).get("variant"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
