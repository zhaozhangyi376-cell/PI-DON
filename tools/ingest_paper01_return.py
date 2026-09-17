"""Import and independently audit a PAPER01-S1 server return archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_paths import PROJECT_DIR, configure


configure()

ROOT = PROJECT_DIR / "evidence/paper01_s1"
TASK_ID = "PAPER01-S1"
PROTOCOL = "docs/plans/2026-09-17-paper01-s1-r1-protocol.md"
EXPECTED_OUTPUT = "paper01_s1_v1"
REQUIRED = (
    "manifest.json",
    "paper_contract.json",
    "sample_specs.json",
    "history.jsonl",
    "summary.json",
    "audit.json",
    "REPORT.md",
    "best.pt",
    "last.pt",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_members(archive: zipfile.ZipFile):
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise SystemExit(f"Unsafe zip member: {info.filename}")
        yield info


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def find_output(base: Path) -> Path:
    matches = [
        path.parent
        for path in base.rglob("summary.json")
        if path.parent.name == EXPECTED_OUTPUT
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {EXPECTED_OUTPUT}/summary.json, found {len(matches)}")
    return matches[0]


def count_history(path: Path) -> tuple[int, int | None]:
    count = 0
    last_update = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        count += 1
        last_update = int(row["update"])
    return count, last_update


def audit_output(output: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED if not (output / name).is_file()]
    if missing:
        return {
            "engineering_pass": False,
            "scientific_result": "INCOMPLETE",
            "missing": missing,
            "checks": {},
        }

    summary = read_json(output / "summary.json")
    manifest = read_json(output / "manifest.json")
    recorded = read_json(output / "audit.json")
    contract = read_json(output / "paper_contract.json")
    local_contract_hash = sha256(PROJECT_DIR / "_01/paper_contract.json")
    returned_contract_hash = sha256(output / "paper_contract.json")
    history_rows, history_last_update = count_history(output / "history.jsonl")
    config = manifest.get("config") or {}
    rates = summary.get("learning_rates") or []
    checks = {
        "summary_schema": summary.get("schema") == "pidon-paper01-s1-summary-v1",
        "manifest_schema": manifest.get("schema") == "pidon-paper01-s1-run-v1",
        "contract_schema": contract.get("schema") == "pidon-paper01-contract-v1",
        "mode_train": summary.get("mode") == "train" and manifest.get("mode") == "train",
        "complete_25000_updates": summary.get("status") == "COMPLETE"
        and summary.get("updates") == 25000
        and summary.get("parameter_updates") == 25000,
        "history_complete": history_rows == 25000 and history_last_update == 25000,
        "constant_lr_1e4": len(rates) == 25000
        and all(float(rate) == 1e-4 for rate in rates)
        and recorded.get("constant_lr") is True,
        "paper_scale_config": config.get("grid") == 32
        and config.get("samples") == 1000
        and config.get("effective_batch") == 32
        and config.get("updates") == 25000
        and config.get("levels") == 4
        and float(config.get("learning_rate", -1)) == 1e-4,
        "fresh_random_initialization": manifest.get("initial_checkpoint") is None
        and manifest.get("old_evidence_reused") is False
        and summary.get("old_checkpoint_loaded") is False,
        "contract_matches_local": returned_contract_hash == local_contract_hash
        and summary.get("contract_sha256") == local_contract_hash
        and manifest.get("contract_sha256") == local_contract_hash,
        "best_checkpoint_hash": sha256(output / "best.pt") == recorded.get("best_checkpoint_sha256"),
        "last_checkpoint_hash": sha256(output / "last.pt") == recorded.get("last_checkpoint_sha256"),
        "sample_specs_1000": len(read_json(output / "sample_specs.json")) == 1000,
    }
    engineering_pass = all(checks.values())

    metrics = summary.get("final_metrics") or {}
    individuals = metrics.get("individual") or []
    macro_nmae = metrics.get("macro_nmae_mean")
    rel_l2_p90 = metrics.get("global_rel_l2_p90")
    individual_pass = bool(individuals) and all(
        row.get("macro_nmae") is not None and float(row["macro_nmae"]) <= 0.01
        for row in individuals
    )
    gates = {
        "macro_nmae_le_1pct": macro_nmae is not None and float(macro_nmae) <= 0.01,
        "rel_l2_p90_le_5pct": rel_l2_p90 is not None and float(rel_l2_p90) <= 0.05,
        "every_sample_macro_nmae_le_1pct": individual_pass,
    }
    if not engineering_pass:
        scientific = "INCOMPLETE"
    elif all(gates.values()):
        scientific = "PASS_REGISTERED_S1_GATES"
    else:
        scientific = "FAIL_REGISTERED_S1_GATES"
    return {
        "engineering_pass": engineering_pass,
        "scientific_result": scientific,
        "missing": [],
        "checks": checks,
        "gates": gates,
        "history_rows": history_rows,
        "history_last_update": history_last_update,
        "metrics": {
            "best_test_mse": summary.get("best_test_mse"),
            "best_update": summary.get("best_update"),
            "final_test_mse": summary.get("final_test_mse"),
            "macro_nmae_mean": macro_nmae,
            "global_rel_l2_p90": rel_l2_p90,
            "macro_mre_eq5_mean": metrics.get("macro_mre_eq5_mean"),
            "elapsed_seconds": summary.get("elapsed_seconds"),
        },
        "checkpoint_sha256": {
            "best": sha256(output / "best.pt"),
            "last": sha256(output / "last.pt"),
        },
    }


def make_report(import_dir: Path, output: Path, result: dict[str, Any], zip_hash: str) -> Path:
    values = result.get("metrics") or {}
    checks = result.get("checks") or {}
    gates = result.get("gates") or {}
    lines = [
        "# PAPER01-S1 服务器回传审计",
        "",
        f"- 原始回传SHA256：`{zip_hash}`",
        f"- 不可变导入目录：`{relative(import_dir)}`",
        f"- 工程完整性：`{'PASS' if result['engineering_pass'] else 'INCOMPLETE'}`",
        f"- 科学判定：`{result['scientific_result']}`",
        "- 声明：这是论文显式配置参考线，不宣称作者源码逐位同一。",
        "",
        "## 训练合同",
        "",
        f"- history行数/末更新：`{result.get('history_rows')}` / `{result.get('history_last_update')}`",
        f"- 缺失文件：`{result.get('missing')}`",
        "",
        "| 完整性检查 | 结果 |",
        "|---|---|",
        *[f"| {name} | {passed} |" for name, passed in checks.items()],
        "",
        "## 第一阶段结果",
        "",
        f"- best normalized test MSE：`{values.get('best_test_mse')}`（update `{values.get('best_update')}`）",
        f"- final normalized test MSE：`{values.get('final_test_mse')}`",
        f"- 开发集宏nMAE：`{values.get('macro_nmae_mean')}`",
        f"- relL2 p90：`{values.get('global_rel_l2_p90')}`",
        f"- Eq.(5) MRE均值：`{values.get('macro_mre_eq5_mean')}`",
        f"- 训练墙钟：`{values.get('elapsed_seconds')}` 秒",
        "",
        "| 登记门槛 | 结果 |",
        "|---|---|",
        *[f"| {name} | {passed} |" for name, passed in gates.items()],
        "",
        "## 解释边界",
        "",
        "该审计只回答独立第一阶段参考线是否按冻结合同执行，以及固定测试集指标是否过登记门。它不自动证明第二阶段预训练收益，也不解锁1024/8192。Eq.(5) MRE、nMAE和relL2继续分栏，不能互相替代。",
        "",
        "## 原始证据",
        "",
        *[f"- `{relative(output / name)}`" for name in REQUIRED],
    ]
    report = ROOT / "server_return_review.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def update_plan(output: Path, report: Path, result: dict[str, Any]) -> None:
    plan_path = PROJECT_DIR / "project/plan.json"
    plan = read_json(plan_path)
    task = next((task for task in plan["tasks"] if task["id"] == TASK_ID), None)
    if task is None:
        raise SystemExit(f"Missing registered task {TASK_ID}")
    task["status"] = "PASS" if result["engineering_pass"] else "INCOMPLETE"
    task["scientific_result"] = result["scientific_result"]
    task["evidence"] = [
        PROTOCOL,
        *[relative(output / name) for name in REQUIRED],
        relative(report),
    ]
    values = result.get("metrics") or {}
    task["summary"] = (
        f"PAPER01-S1 engineering={'PASS' if result['engineering_pass'] else 'INCOMPLETE'}; "
        f"scientific={result['scientific_result']}; updates={result.get('history_last_update')}; "
        f"macro_nMAE={values.get('macro_nmae_mean')}; relL2_p90={values.get('global_rel_l2_p90')}; "
        f"Eq5_MRE={values.get('macro_mre_eq5_mean')}."
    )
    write_json(plan_path, plan)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path")
    args = parser.parse_args()
    zip_path = Path(args.zip_path)
    if not zip_path.is_absolute():
        zip_path = PROJECT_DIR / zip_path
    if not zip_path.is_file():
        raise SystemExit(f"Return archive does not exist: {zip_path}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    import_dir = ROOT / "imports" / f"{zip_path.stem}_{stamp}"
    import_dir.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        for info in safe_members(archive):
            archive.extract(info, import_dir)
    output = find_output(import_dir)
    result = audit_output(output)
    result["return_zip_sha256"] = sha256(zip_path)
    result["import_dir"] = relative(import_dir)
    result["output_dir"] = relative(output)
    write_json(ROOT / "server_return_audit.json", result)
    report = make_report(import_dir, output, result, result["return_zip_sha256"])
    update_plan(output, report, result)
    print(json.dumps({
        "status": "PASS" if result["engineering_pass"] else "INCOMPLETE",
        "scientific_result": result["scientific_result"],
        "import_dir": str(import_dir),
        "report": str(report),
        "metrics": result.get("metrics"),
    }, ensure_ascii=False))
    return 0 if result["engineering_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
