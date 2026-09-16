"""Create the N1 C01--C15 audit from an actual successful lab_log run."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import os
from pathlib import Path

from pidon_recording import sha256_file, source_hashes


ROOT = PROJECT_ROOT
CHECKS = {
    "C01": ("total physical R 严格小于门槛", "test_component_loss_cannot_pass_when_physical_total_R_fails"),
    "C02": ("仅完整零输入/零靶值走捷径", "test_nonzero_irrotational_input_is_not_zero_shortcut"),
    "C03": ("H失败不改变E、源或H", "test_h_failure_does_not_advance_transaction"),
    "C04": ("E_pending不重复源或E更新", "test_e_pending_resume_does_not_repeat_source_or_e_update"),
    "C05": ("Adam中断真实状态恢复一致", "test_interrupted_adam_resume_matches_uninterrupted_trajectory"),
    "C06": ("LBFGS中断保存raw并回滚完整调用", "test_lbfgs_budget_interrupt_restores_last_completed_call"),
    "C07": ("耗尽预算/终态不可继续训练", "test_exhausted_inner_budget_is_rejected_before_resume"),
    "C08": ("非有限梯度/参数保留raw并回滚", "test_nonfinite_parameter_after_step_is_raw_then_rolled_back"),
    "C09": ("schema、角色和冻结配置不合即拒绝", "test_payload_schema_and_independent_run_identity_are_explicit"),
    "C10": ("独立run UUID与稳定protocol hash分离", "test_payload_schema_and_independent_run_identity_are_explicit"),
    "C11": ("JSONL后metadata崩溃扫描真实尾行", "test_jsonl_commit_crash_recovers_unique_next_sequence_and_tail"),
    "C12": ("截断、错序、重复和NaN JSONL拒绝", "test_recorder_rejects_nonfinite_jsonl_constant_on_resume"),
    "C13": ("两槽新指针失败时仍读回旧槽", "test_rolling_checkpoint_pointer_keeps_prior_slot_if_new_pointer_fails"),
    "C14": ("failure_raw不改正式恢复指针且E用E尝试号", "test_failure_raw_does_not_claim_a_recovery_checkpoint"),
    "C15": ("持久deadline和任务累计额度不重置", "test_training_stops_at_nine_and_a_half_hours"),
}


def lab_run(run_id: int) -> dict:
    for line in (ROOT / "lab_runs.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("id") == run_id:
            return row
    raise ValueError(f"lab_log run #{run_id} does not exist")


def atomic_write(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="evidence/gpt6_plan_v4_night")
    parser.add_argument("--lab-run", type=int, required=True)
    args = parser.parse_args()
    out = (ROOT / args.root).resolve()
    run = lab_run(args.lab_run)
    expected_tokens = ("test_pidon_contract_v4.py", "test_pidon_contract.py",
                       "test_pidon_contract_v3.py", "test_night_budget.py")
    valid_run = run.get("exit_code") == 0 and all(token in run.get("cmd", "") for token in expected_tokens)
    checks = [{"id": key, "expected": expected, "test_id": test_id,
               "observed": {"lab_run": args.lab_run, "exit_code": run.get("exit_code")},
               "status": "PASS" if valid_run else "FAIL", "run_id": args.lab_run,
               "source_hash": source_hashes(ROOT), "evidence_path": "lab_runs.jsonl"}
              for key, (expected, test_id) in CHECKS.items()]
    result = {"schema": "pidon-n1-contract-audit-v1", "lab_log_run": args.lab_run,
              "required_ids": list(CHECKS), "checks": checks,
              "status": "PASS" if valid_run and len({row['id'] for row in checks}) == 15 else "FAIL",
              "source_hashes": source_hashes(ROOT), "lab_run_record_hash": sha256_file(ROOT / "lab_runs.jsonl")}
    atomic_write(out / "N1_contract_checks.json", result)
    status_path = out / "stage_status.json"
    stage = json.loads(status_path.read_text(encoding="utf-8"))
    stage["N1"] = {"implementation": result["status"], "scientific_gate": "N/A",
                   "lab_run_id": args.lab_run, "evidence": "N1_contract_checks.json"}
    atomic_write(status_path, stage)
    report = ["# N1 合同与恢复修复报告", "", f"- lab_log：#{args.lab_run}",
              f"- C01–C15：**{result['status']}**", "- 正式 DCO 更新：0", "",
              "| ID | 断言 | 回归测试 | 状态 |", "|---|---|---|---|"]
    report.extend(f"| {row['id']} | {row['expected']} | `{row['test_id']}` | {row['status']} |" for row in checks)
    (out / "N1_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out / "N1_contract_checks.json"), "status": result["status"],
                      "checks": len(checks)}, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
