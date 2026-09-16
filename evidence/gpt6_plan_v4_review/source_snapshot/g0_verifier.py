"""Machine verifier for the complete A1/A2 G0 evidence set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pidon_recording import sha256_file


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "gpt6_plan_v3"


def load(name):
    path = OUT / name
    return path, json.loads(path.read_text(encoding="utf-8"))


def check(name, observed, expected, passed, evidence):
    return {"name": name, "observed": observed, "expected": expected,
            "status": "PASS" if passed else "FAIL", "evidence": evidence}


def full_control(name, result, exact):
    rows = result.get("rows", [])
    component_rows = rows and rows[-1].get("accepted_field_metrics", {}).get("components", {})
    required_metric_fields = {"nmae", "mre_nonzero", "relative_l2", "sse", "reference_energy",
                              "support_count", "strict_zero_reference_count", "weak_absolute_pass"}
    all_six = len(component_rows) == 6 and all(required_metric_fields <= set(row) for row in component_rows.values())
    expected_pass = bool(exact)
    actual_gate = bool(result.get("field_gate_pass"))
    return check(
        name,
        {"steps": result.get("steps"), "gate": actual_gate, "restored_at": result.get("restored_at_accepted_step"),
         "uncovered": result.get("support", {}).get("uncovered"), "six_component_metrics": all_six,
         "control_only": result.get("control_only"), "reference_dtype": result.get("reference_dtype")},
        {"steps": 128, "field_gate": expected_pass, "control_only": True,
         "uncovered": 0, "six_component_metrics": True, "reference_dtype": "float64"},
        (result.get("steps") == 128 and actual_gate is expected_pass and result.get("control_only") is True and
         result.get("support", {}).get("uncovered") == 0 and all_six and
         result.get("reference_dtype") == "float64" and (result.get("restored_at_accepted_step") == 64 if exact else True)),
        result.get("identity", {}).get("source_hashes"),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-run", type=int, required=True)
    args = parser.parse_args()
    contract_path, contract = load("contract_test_results.json")
    exact_path, exact = load("A2_exact_control.json")
    zero_path, zero = load("A2_zero_curl_negative.json")
    cache_path, cache = load("reference_cache.json")
    required = []
    required.append(check(
        "A1_contract_recovery_identity_fault_suite",
        contract.get("observed"), contract.get("expected"), contract.get("status") == "PASS" and
        contract.get("observed", {}).get("failures") == 0 and contract.get("observed", {}).get("errors") == 0,
        {"path": str(contract_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(contract_path)},
    ))
    required.append(full_control("A2_float64_exact_128_with_restore", exact["float64"], True))
    required.append(full_control("A2_float32_exact_128_with_restore", exact["float32"], True))
    required.append(full_control("A2_hard_source_only_negative", exact["hard_source_only_negative"], False))
    required.append(full_control("A2_wrong_H_half_negative", exact["wrong_h_half_negative"], False))
    required.append(full_control("A2_zero_curl_negative", zero, False))
    snap = ROOT / cache.get("snapshot_npz", "")
    required.append(check(
        "A2_reference_cache_8192",
        {"steps": cache.get("protocol", {}).get("steps"), "source_mode": cache.get("protocol", {}).get("source_mode"),
         "snapshot_exists": snap.is_file(), "snapshot_hash": sha256_file(snap) if snap.is_file() else None,
         "probe_count": len(cache.get("probe_cells", []))},
        {"steps": 8192, "source_mode": "hard", "snapshot_hash": cache.get("snapshot_sha256"), "probe_count": 3},
        cache.get("protocol", {}).get("steps") == 8192 and cache.get("protocol", {}).get("source_mode") == "hard" and
        snap.is_file() and sha256_file(snap) == cache.get("snapshot_sha256") and len(cache.get("probe_cells", [])) == 3,
        {"path": str(cache_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(cache_path)},
    ))
    for entry in required:
        entry.setdefault("run_id", None)
    result = {
        "schema": "pidon-g0-v3", "lab_log_run": args.lab_run,
        "G0": "PASS" if all(row["status"] == "PASS" for row in required) else "FAIL",
        "required_g0_checks": required,
        "inputs": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                   for path in (contract_path, exact_path, zero_path, cache_path)},
        "interpretation": "G0 certifies engineering/measurement controls only; exact Yee controls are not DCO scores.",
    }
    (OUT / "G0.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# A2 完整 G0 报告", "", f"- lab_log：#{args.lab_run}", f"- G0：**{result['G0']}**", "",
             "G0 认证合同、测量、参考时层和负对照。精确 Yee 结果只证明这条控制链路；不计入 DCO 成绩。", "",
             "| 检查 | observed | 状态 |", "|---|---|---|"]
    for row in required:
        lines.append(f"| {row['name']} | `{json.dumps(row['observed'], ensure_ascii=False)}` | {row['status']} |")
    (OUT / "A2_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT / "G0.json"), "G0": result["G0"],
                      "checks": len(required)}, ensure_ascii=False))
    if result["G0"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
