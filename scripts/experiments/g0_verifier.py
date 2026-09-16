"""Numeric, input-driven G0 verifier for the v4 night evidence package."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

from pidon_recording import sha256_file, source_hashes

ROOT = PROJECT_ROOT
C_IDS = [f"C{i:02d}" for i in range(1, 16)]
M_IDS = [f"M{i:02d}" for i in range(1, 14)]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(path)}


def check(identifier: str, expected: str, observed: dict[str, Any], passed: bool, path: Path | None = None) -> dict[str, Any]:
    return {"id": identifier, "expected": expected, "observed": observed,
            "status": "PASS" if passed else "FAIL", "evidence": evidence(path) if path else None}


def lab_record(run_id: int) -> dict[str, Any] | None:
    path = ROOT / "lab_runs.jsonl"
    if not path.is_file(): return None
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("id") == run_id: return row
    return None


def control_integrity(result: dict[str, Any], run_dir: Path) -> bool:
    metadata_path, steps_path = run_dir / "run_metadata.json", run_dir / "steps.jsonl"
    if not metadata_path.is_file() or not steps_path.is_file(): return False
    metadata = load_json(metadata_path)
    identity = result.get("identity", {})
    if any(metadata.get(key) != identity.get(key) for key in ("run_id", "protocol_hash")): return False
    snapshot_hashes = result.get("source_snapshot_hashes") or {}
    for name, digest in snapshot_hashes.items():
        if sha256_file(run_dir / "source_snapshot" / name) != digest: return False
    for name, digest in identity.get("source_hashes", {}).items():
        if sha256_file(run_dir / "source_snapshot" / name) != digest: return False
    try:
        rows = [json.loads(line) for line in steps_path.read_text(encoding="utf-8").splitlines()]
    except json.JSONDecodeError:
        return False
    return [row.get("sequence_id") for row in rows] == list(range(len(rows))) == list(range(128))


def control_numeric(result: dict[str, Any], *, threshold: float, should_pass: bool) -> tuple[bool, dict[str, Any]]:
    rows = result.get("rows", [])
    steps = [row.get("step") for row in rows]
    accepted = all(row.get("accepted") is True and row.get("accepted_steps") == i + 1
                   for i, row in enumerate(rows))
    six = all(len(row.get("accepted_field_metrics", {}).get("components", {})) == 6 for row in rows)
    metric_fields = {"nmae", "volume_nmae", "mre_eq5_physical", "mre_nonzero", "relative_l2",
                     "sse", "reference_energy", "support_count", "strict_zero_reference_count"}
    fields = all(metric_fields <= set(component) for row in rows
                 for component in row.get("accepted_field_metrics", {}).get("components", {}).values())
    rel = [row.get("accepted_field_metrics", {}).get("global_weighted_relative_l2", float("nan")) for row in rows]
    fixed = [row.get("accepted_field_metrics", {}).get("fixed_amplitude_error", float("nan")) for row in rows]
    probe = [abs(probe.get("dut_Ez", float("nan")) - probe.get("ref_Ez", float("nan")))
             for row in rows for probe in row.get("source_outside_probes", [])]
    values = rel + fixed + probe
    finite = all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in values)
    max_rel = max(rel) if finite and rel else None
    max_fixed = max(fixed) if finite and fixed else None
    max_probe = max(probe) if finite and probe else None
    numeric_ok = (len(rows) == 128 and steps == list(range(128)) and accepted and six and fields and
                  len(probe) == 384 and finite and max_rel <= threshold and max_fixed <= threshold and
                  max_probe <= threshold and result.get("support", {}).get("uncovered") == 0 and
                  result.get("reference_dtype") == "float64" and result.get("control_only") is True)
    return (numeric_ok if should_pass else not numeric_ok), {
        "rows": len(rows), "step_sequence_ok": steps == list(range(128)), "accepted_rows": accepted,
        "six_components": six, "metric_fields": fields, "finite": finite, "max_Q": max_rel,
        "max_A_fixed": max_fixed, "max_probe_abs": max_probe,
        "threshold": threshold, "numeric_ok": numeric_ok, "restored_at": result.get("restored_at_accepted_step"),
        "control_only": result.get("control_only"), "reference_dtype": result.get("reference_dtype")}


def negative_self_tests(exact_result: dict[str, Any], run_dir: Path) -> dict[str, bool]:
    missing = copy.deepcopy(exact_result); missing["rows"] = missing["rows"][:1]
    duplicated = copy.deepcopy(exact_result); duplicated["rows"][1]["step"] = 0
    bad_numeric = copy.deepcopy(exact_result)
    bad_numeric["rows"][0]["accepted_field_metrics"]["global_weighted_relative_l2"] = 1.0
    no_probe = copy.deepcopy(exact_result); no_probe["rows"][0]["source_outside_probes"] = []
    bad_hash = copy.deepcopy(exact_result); bad_hash["identity"]["source_hashes"]["dco.py"] = "spoofed"
    disguised = copy.deepcopy(exact_result); disguised["control_only"] = False
    return {"missing_rows_rejected": not control_numeric(missing, threshold=1e-10, should_pass=True)[0],
            "duplicate_step_rejected": not control_numeric(duplicated, threshold=1e-10, should_pass=True)[0],
            "bad_numeric_rejected": not control_numeric(bad_numeric, threshold=1e-10, should_pass=True)[0],
            "missing_probe_rejected": not control_numeric(no_probe, threshold=1e-10, should_pass=True)[0],
            "hash_tamper_rejected": not control_integrity(bad_hash, run_dir),
            "empty_required_set_rejected": bool(C_IDS + M_IDS) and set() != set(C_IDS + M_IDS),
            "control_disguised_as_dco_rejected": not control_numeric(disguised, threshold=1e-10, should_pass=True)[0]}


def verify(root: Path, *, contract_run: int, n1_path: Path | None = None) -> dict[str, Any]:
    n1_path = n1_path or root / "N1_contract_checks.json"
    controls_path, cache_path = root / "controls.json", root / "reference_cache.json"
    n1, controls, cache = load_json(n1_path), load_json(controls_path), load_json(cache_path)
    record = lab_record(contract_run)
    required_modules = ("test_pidon_contract.py", "test_pidon_contract_v3.py", "test_pidon_contract_v4.py", "test_night_budget.py")
    unit_run_valid = bool(record and record.get("exit_code") == 0 and
                          all(name in record.get("cmd", "") for name in required_modules))
    checks: list[dict[str, Any]] = []
    c_actual = {row.get("id") for row in n1.get("checks", []) if row.get("status") == "PASS"}
    for identifier in C_IDS:
        checks.append(check(identifier, "N1真实回归通过且ID唯一", {"present": identifier in c_actual,
                      "lab_run": n1.get("lab_log_run"), "contract_status": n1.get("status")},
                            identifier in c_actual and n1.get("status") == "PASS", n1_path))
    for identifier, key, threshold, should_pass in (
        ("M06", "float64", 1e-10, True), ("M07", "float32", 1e-4, True),
        ("M08", "zero_curl_negative", 1e-10, False), ("M09", "hard_source_only_negative", 1e-10, False),
        ("M10", "wrong_h_half_negative", 1e-10, False)):
        passed, observed = control_numeric(controls[key], threshold=threshold, should_pass=should_pass)
        run_name = {"float64": "float64_exact", "float32": "float32_exact",
                    "zero_curl_negative": "zero_curl_negative", "hard_source_only_negative": "hard_source_only_negative",
                    "wrong_h_half_negative": "wrong_h_half_negative"}[key]
        integrity = control_integrity(controls[key], root / "control_runs" / run_name)
        observed["identity_and_jsonl_integrity"] = integrity
        passed = passed and integrity
        if identifier in {"M06", "M07"}:
            passed = passed and controls[key].get("restored_at_accepted_step") == 64
        checks.append(check(identifier, "逐行、六分量、探针和数值门槛从原始行重算", observed, passed, controls_path))
    for identifier, expected in {
        "M01": "常量/线性curl双路径double断言", "M02": "三轴平面波与div(curl)断言",
        "M03": "learned/PEC boundary/uncovered支撑断言", "M04": "双体积、硬源mask和插值断言",
        "M05": "nMAE、volume_nMAE、严格零MRE手算断言"}.items():
        checks.append(check(identifier, expected, {"lab_run": contract_run, "valid_lab_record": unit_run_valid}, unit_run_valid, n1_path))
    restored = all(controls[key].get("restored_at_accepted_step") == 64 for key in ("float64", "float32"))
    rolling = all((root / "control_runs" / name / "checkpoint_pointer.json").is_file()
                  for name in ("float64_exact", "float32_exact"))
    checks.append(check("M11", "128行来自第64步真实磁盘两槽恢复", {"restored": restored, "rolling_pointer": rolling},
                        restored and rolling, controls_path))
    snapshot = ROOT / cache.get("snapshot_npz", "")
    cache_pass = (cache.get("protocol", {}).get("steps") == 8192 and cache.get("protocol", {}).get("source_mode") == "hard"
                  and snapshot.is_file() and sha256_file(snapshot) == cache.get("snapshot_sha256")
                  and len(cache.get("probe_cells", [])) == 3)
    checks.append(check("M12", "8192步double参考、峰值、探针和hash齐全", {"snapshot": str(snapshot),
                        "hash_match": sha256_file(snapshot) == cache.get("snapshot_sha256") if snapshot.is_file() else False,
                        "steps": cache.get("protocol", {}).get("steps")}, cache_pass, cache_path))
    selftest = negative_self_tests(controls["float64"], root / "control_runs" / "float64_exact")
    checks.append(check("M13", "缺行、重复、坏数值、漏probe和控制伪装全部被拒绝", selftest, all(selftest.values()), controls_path))
    required = set(C_IDS + M_IDS)
    actual = {row["id"] for row in checks}
    return {"schema": "pidon-g0-v4", "contract_lab_run": contract_run, "required_ids": sorted(required),
            "required_g0_checks": checks,
            "input_hashes": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                             for path in (n1_path, controls_path, cache_path)}, "source_hashes": source_hashes(ROOT),
            "G0": "PASS" if actual == required and all(row["status"] == "PASS" for row in checks) else "FAIL",
            "interpretation": "精确Yee控制只认证测量/恢复链路，control_only=true，绝不计为DCO成绩。"}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", default="evidence/gpt6_plan_v4_night")
    parser.add_argument("--contract-run", type=int, required=True); parser.add_argument("--n1", default="")
    args = parser.parse_args(); root = (ROOT / args.root).resolve()
    result = verify(root, contract_run=args.contract_run, n1_path=Path(args.n1).resolve() if args.n1 else None)
    output = root / "G0.json"; output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (root / "required_g0_checks.json").write_text(json.dumps(result["required_g0_checks"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(output), "G0": result["G0"], "checks": len(result["required_g0_checks"])}, ensure_ascii=False))
    if result["G0"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
