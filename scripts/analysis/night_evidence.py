"""Read-only, numeric N0--N5 evidence recomputation for the 10-hour run.

This module deliberately separates engineering/control certification from a DCO
result.  It returns a structured record even when G1 is a scientific FAIL;
FAIL is the expected gate outcome here, not a parser failure.
"""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import hashlib
import json
import math
from pathlib import Path

import torch

import night_fixed_state as fixed
from pidon_solve import Solver

ROOT = PROJECT_ROOT
DEFAULT_ROOT = ROOT / "evidence" / "gpt6_plan_v4_night"
R_TOL = 1e-4


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def finite(value):
    return isinstance(value, (float, int)) and math.isfinite(float(value))


def remeasure_checkpoint(path: Path, role: str) -> dict:
    """Reload a terminal checkpoint diagnostically and recompute physical R."""
    payload = torch.load(path, map_location="cpu", weights_only=False)
    expected_key = "fit_input_" + role
    target_key = "fit_target_" + role
    if expected_key not in payload or target_key not in payload:
        raise ValueError(f"{path.name}: diagnostic checkpoint input/target mismatch")
    solver = Solver(fixed.args_for(20260913), "cpu")
    solver.load_state_payload(payload, diagnostic_only=True)
    field = [item.to(solver.dev) for item in payload[expected_key]]
    target = [item.to(solver.dev) for item in payload[target_key]]
    result = fixed.residual(solver, field, target, role)
    return {key: value for key, value in result.items() if key not in ("prediction", "target")} | {
        "checkpoint": str(path.relative_to(ROOT)).replace("\\", "/"),
        "checkpoint_sha256": sha256(path),
        "role": role,
        "input_hash": fixed.tensor_hash(field),
        "target_hash": fixed.tensor_hash(target),
        "diagnostic_only": True,
        "parameter_updates": 0,
    }


def task_row(task: dict, role: str, disk: dict | None, *, classification: str) -> dict:
    block = task[role] if role in task else task
    fit = block["fit"]
    progress = block.get("progress", {})
    final = block["final"]
    return {
        "status": "PASS" if fit.get("passed") else "FAIL",
        "classification": classification,
        "origin": task.get("origin", "fixed_reference_state"),
        "phase": task.get("phase", role),
        "source_index": task.get("source_index"),
        "task_id": block.get("task_id"),
        "checkpoint": None if disk is None else disk["checkpoint"],
        "checkpoint_sha256": None if disk is None else disk["checkpoint_sha256"],
        "adam_updates": fit.get("n_updates"),
        "head_commits": progress.get("head_commit_count"),
        "linear_solve_calls": progress.get("linear_solve_calls"),
        "closures": fit.get("n_closures", progress.get("closures")),
        "loss_objective": fit.get("loss_final"),
        "R_recorded": final.get("R"),
        "R_disk": None if disk is None else disk["R"],
        "physical_sse": final.get("physical_sse"),
        "physical_mse": final.get("physical_mse"),
        "stop_reason": fit.get("stop_reason"),
        "recovery_eligible": progress.get("resumable", task.get("recovery_eligible")),
        "six_components": task.get("accepted_field_metrics") or "NOT_RUN",
        "source_outside_probes": task.get("source_outside_probes") or "NOT_RUN",
    }


def compute(root: Path = DEFAULT_ROOT) -> dict:
    root = root.resolve()
    manifest = load(root / "night_manifest.json")
    stage = load(root / "stage_status.json")
    acceptance_path = root / "acceptance.json"
    n1 = load(root / "N1_contract_checks.json")
    g0 = load(root / "g0_after_head_integration" / "G0.json")
    n3 = load(root / "n3_fixed" / "N3_fixed.json")
    n5 = load(root / "n5_diagnostics_attempt05" / "N5_diagnostics.json")

    assets = []
    for rel, expected in stage["historical_asset_hashes"].items():
        path = ROOT / rel if rel.startswith("evidence/") else ROOT / rel
        actual = sha256(path) if path.is_file() else None
        assets.append({"path": rel, "expected_sha256": expected, "actual_sha256": actual,
                       "status": "PASS" if actual == expected else "FAIL"})

    n1_ok = {item["id"] for item in n1["checks"] if item["status"] == "PASS"} == set(n1["required_ids"])
    required = g0["required_g0_checks"]
    g0_ok = g0.get("G0") == "PASS" and len(required) == 28 and all(x["status"] == "PASS" for x in required)
    control_rows = {x["id"]: x["observed"] for x in required if x["id"].startswith("M")}

    ledgers = [json.loads(line) for line in (root / "resource_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line]
    ledger_by_task = {row.get("task_id"): row for row in ledgers}
    by_step = {item["step"]: item for item in n3["tasks"]}
    h43_disk = remeasure_checkpoint(root / "n3_fixed" / "step_0043_H.pt", "H")
    h96_disk = remeasure_checkpoint(root / "n3_fixed" / "step_0096_H.pt", "H")
    e96_disk = remeasure_checkpoint(root / "n3_fixed" / "step_0096_E_sequential.pt", "E")
    h43 = task_row(by_step[43], "H", h43_disk, classification="registered_G1_development")
    h96 = task_row(by_step[96], "H", h96_disk, classification="registered_G1_development")
    e96 = task_row(by_step[96]["E_sequential_registered"], "E", e96_disk,
                   classification="registered_G1_development_sequential")
    h43["phase"] = "before_H"; h96["phase"] = "before_H"
    for row in (h43, h96, e96):
        ledger = ledger_by_task.get(row["task_id"], {})
        row["recorded_at_utc"] = ledger.get("recorded_at")
        row["input_hash"] = (h43_disk if row is h43 else h96_disk if row is h96 else e96_disk)["input_hash"]
        row["target_hash"] = (h43_disk if row is h43 else h96_disk if row is h96 else e96_disk)["target_hash"]
    # A disk reread is part of the gate.  It cannot revive a recorded failed task.
    g1 = all(row["status"] == "PASS" and row["R_disk"] < R_TOL for row in (h43, h96, e96))

    old_grad = n5["old_sample_gradients"]["samples"]
    n5_gradient_ok = all(row.get("status") == "PASS" for row in old_grad)
    n5_fd_ok = all(row["pass"] for row in n5["labels_and_gradients"]["gradient_direction_checks"])
    labels_incomplete = all("INCOMPLETE" in row.get("label_provenance", "")
                            for row in n5["labels_and_gradients"]["old_label_assets"])

    registered = [row for row in ledgers if row["kind"] in ("N3_fixed_H", "N3_fixed_E_sequential")]
    oracle = [row for row in ledgers if row["kind"] == "N3_oracle_E"]
    result = {
        "schema": "pidon-v4-night-evidence-v1",
        "experiment_id": manifest["experiment_id"],
        "manifest": {key: manifest[key] for key in ("started_at", "deadline", "training_deadline", "plan_sha256", "master_weight_sha256")},
        "acceptance_file": {"path": str(acceptance_path.relative_to(ROOT)).replace("\\", "/"),
                            "exists": acceptance_path.is_file()},
        "asset_integrity": assets,
        "N0": {"status": "PASS" if all(x["status"] == "PASS" for x in assets) else "FAIL",
               "disk_free_initial_bytes": stage["resource_baseline"]["disk_free_bytes"],
               "cleanup_bytes": 0},
        "N1": {"status": "PASS" if n1_ok else "FAIL", "checks_passed": sum(x["status"] == "PASS" for x in n1["checks"]),
               "checks_required": len(n1["required_ids"]), "lab_run_id": n1["lab_log_run"]},
        "G0": {"status": "PASS" if g0_ok else "FAIL", "checks_passed": sum(x["status"] == "PASS" for x in required),
               "checks_required": len(required), "lab_run_id": 204, "control_measurements": control_rows,
               "classification": "exact Yee/control and measurement certification; not DCO score"},
        "N3": {"implementation": "PASS", "candidate": "head_lstsq_once_adam499 (optimization variant; not paper-confirmed)",
               "config": vars(fixed.args_for(20260913)), "source_hashes": n3["source_hashes"],
               "threshold_R_strict": R_TOL, "registered_rows": [h43, h96, e96],
               "oracle_rows_excluded": oracle, "G1": "PASS" if g1 else "FAIL",
               "stop_reason": n3["stop_reason"], "workflow_deviations": [
                   "#205 JSON report serialization failed after H43 checkpoint; H43 was remeasured from disk without a new update.",
                   "#206 ran oracle-E diagnostics with parameter updates; they are preserved in the ledger and excluded from G1. The E96 oracle is explicitly a flow defect because H96 had passed.",
               ]},
        "N4": {"status": "NOT_RUN", "reason": "G1_development_failed; no validated accepted trajectory may enter 64/128/1024/8192",
               "G2": "NOT_RUN", "G3": "NOT_RUN"},
        "N5": {"status": "PASS" if n5_gradient_ok and n5_fd_ok else "INCOMPLETE", "lab_run_id": 212,
               "formal_dco_updates": n5["formal_dco_updates"], "analytic_n7_fd": n5["labels_and_gradients"]["gradient_direction_checks"],
               "old_sample_gradient_status": [dict(path=x["path"], status=x.get("status"), loss=x.get("loss"), zero_gradient_parameter_ratio=x.get("zero_gradient_parameter_ratio")) for x in old_grad],
               "label_provenance": "INCOMPLETE" if labels_incomplete else "CHECK_REQUIRED",
               "frozen_feature": [{key: item[key] for key in ("asset", "role", "stored_R", "forward_R", "frozen_feature_lstsq_R", "rank", "parameter_updates")} for item in n5["frozen_feature"]]},
        "resource": {"ledger_rows": len(ledgers), "registered_g1_adam_updates": sum(x["adam_updates"] for x in registered),
                     "registered_g1_head_commits": sum(x["head_commits"] for x in registered),
                     "registered_g1_linear_solve_calls": sum(x["linear_solve_calls"] for x in registered),
                     "oracle_excluded_adam_updates": sum(x["adam_updates"] for x in oracle),
                     "cleanup_performed": False,
                     "artifact_used_bytes": sum(path.stat().st_size for path in root.rglob("*") if path.is_file()),
                     "disk_free_final_bytes": __import__("shutil").disk_usage(root).free},
        "gates": {"G0": "PASS" if g0_ok else "FAIL", "G1": "PASS" if g1 else "FAIL", "G2": "NOT_RUN", "G3": "NOT_RUN",
                  "paper_reproduction": "NOT_REPRODUCED"},
        "night_goal": "COMPLETE" if all(x["status"] == "PASS" for x in assets) and n1_ok and g0_ok and not g1 and n5_gradient_ok and n5_fd_ok else "INCOMPLETE",
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT.relative_to(ROOT)))
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = compute((ROOT / args.root) if not Path(args.root).is_absolute() else Path(args.root))
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.out:
        out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
