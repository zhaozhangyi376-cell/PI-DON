"""B benefit pairing for the direct-mechanism plan.

Runs the registered second random seed under rule B, then audits whether the
pretrained B-P arm has a cost benefit against B-R/B-R2.  Field-gate failure is
kept separate from residual-window cost comparisons.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from project_paths import PROJECT_DIR, configure
configure()

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes
import direct_m2_runner as M2


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"
BENEFIT = OUT / "benefit"
PLAN = ROOT / "docs" / "plans" / "2026-09-14-direct-mechanism-plan.md"
SCHEMA = "direct-benefit-v1"
R2_ARM = "B-R2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(data, path)


def r2_spec() -> dict[str, Any]:
    spec = M2.arm_rule("B-R")
    spec.update({
        "arm": R2_ARM,
        "seed": 20260915,
        "purpose": "benefit_second_random_seed_128",
    })
    return spec


def existing_benefit_cost(exclude: str | None = None) -> dict[str, int]:
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    for summary_path in BENEFIT.glob("*/summary.json"):
        if exclude and summary_path.parent.name == exclude:
            continue
        try:
            summary = read_json(summary_path)
        except Exception:
            continue
        if summary.get("schema") != "direct-benefit-arm-summary-v1":
            continue
        budget = summary.get("budget", {})
        for key in total:
            total[key] += int(budget.get(key, 0) or 0)
    return total


def run_b_r2(action_id: str, device: str) -> dict[str, Any]:
    manifest = M2.load_manifest()
    spec = r2_spec()
    BENEFIT.mkdir(parents=True, exist_ok=True)
    out_dir = BENEFIT / "B_R2"
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"benefit output already exists: {display(out_dir)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    config = M2.common_config(spec, out_dir, device)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    global_base = M2.existing_m2_cost()
    benefit_base = existing_benefit_cost(exclude="B_R2")
    combined_base = {
        "adam": global_base["adam"] + benefit_base["adam"],
        "closures": global_base["closures"] + benefit_base["closures"],
        "lbfgs_steps": global_base["lbfgs_steps"] + benefit_base["lbfgs_steps"],
    }
    solver = S.Solver(config, device)
    ref = fdtd.PECCavity(side=config.side, n=config.n, dt=config.dt)
    run_id = hashlib.sha256(f"{manifest['experiment_id']}|{SCHEMA}|{R2_ARM}".encode()).hexdigest()[:24]
    identity = S.formal_run_identity(config, run_id=run_id)
    metadata = {
        "schema": "direct-benefit-run-v1",
        "arm": R2_ARM,
        "action_id": action_id,
        "config": vars(config).copy(),
        "arm_spec": spec,
        "manifest_sha256": sha256_file(OUT / "manifest.json"),
        "plan_sha256": sha256_file(PLAN),
        "created_at_utc": utc_now(),
        **identity,
    }
    recorder = RunRecorder(out_dir, metadata, mode="new")
    rows: list[dict[str, Any]] = []
    traces = M2.trace_wrapper(solver)
    budget_state = M2.budget_wrapper(solver, rows, spec, R2_ARM, combined_base)

    waveform = fdtd.source_waveform(config.steps, solver.dt, config.fmax, "hard")
    source_cell = config.n // 2
    started = time.perf_counter()
    stop: dict[str, Any] | None = None
    snapshot_steps = {64, 128}
    try:
        while solver.accepted_steps < config.steps:
            layer = solver.current_time_layer
            record = solver.step(float(waveform[layer]))
            if record.accepted:
                ref.step_e_source_h(src_value=waveform[layer],
                                    src_idx=(source_cell, source_cell, source_cell))
            row = S._json_safe(S._step_summary(solver, ref, record))
            row["arm"] = R2_ARM
            row["arm_spec"] = spec
            row["fit_traces"] = S._json_safe(copy.deepcopy(traces))
            row["budget_caps"] = S._json_safe(copy.deepcopy(budget_state.get("caps", {})))
            row["actual_wall_s"] = time.perf_counter() - started
            row["row_cost"] = M2.row_cost(row)
            recorder.append(row)
            rows.append(row)
            recorder.rolling_checkpoint(S._checkpoint_payload(
                solver, ref, requested_steps=config.steps, source_index=solver.current_time_layer))
            if record.accepted and solver.accepted_steps in snapshot_steps:
                recorder.snapshot(solver.accepted_steps, S._checkpoint_payload(
                    solver, ref, requested_steps=config.steps, source_index=layer + 1))
            if not record.accepted:
                if budget_state.get("resource_limited"):
                    stop = {"reason": "RESOURCE_LIMIT", "row": row,
                            "budget_events": budget_state.get("events", [])}
                else:
                    stop = {"reason": "FIT_FAIL", "row": row}
                raw = getattr(solver, "last_failure_raw", None)
                if raw is not None:
                    raw = dict(raw)
                    raw["reference"] = S._reference_payload(ref)
                    recorder.failure_raw(raw)
                else:
                    recorder.failure_raw(S._checkpoint_payload(
                        solver, ref, requested_steps=config.steps, source_index=layer))
                break
            cost = M2.sum_cost(rows)
            if cost["adam"] >= M2.ARM_ADAM_CAP or cost["closures"] >= M2.ARM_CLOSURE_CAP:
                stop = {"reason": "RESOURCE_LIMIT", "detail": "arm budget exhausted after accepted step"}
                break
            if combined_base["adam"] + cost["adam"] >= M2.GLOBAL_ADAM_CAP or combined_base["closures"] + cost["closures"] >= M2.GLOBAL_CLOSURE_CAP:
                stop = {"reason": "RESOURCE_LIMIT", "detail": "global budget exhausted after accepted step"}
                break
    except Exception as exc:
        stop = {"reason": "EXCEPTION", "type": type(exc).__name__, "message": str(exc)[:500]}

    budget = M2.sum_cost(rows)
    accepted_rows = [row for row in rows if row.get("accepted")]
    final_accepted = accepted_rows[-1] if accepted_rows else None
    stop_row = (stop or {}).get("row") if isinstance(stop, dict) else None
    probes = [{
        "step": row.get("step"),
        "source_probe_Ez": row.get("source_probe_Ez"),
        "source_outside_probes": row.get("source_outside_probes"),
    } for row in accepted_rows]
    status = M2.classify_stop(stop, solver.accepted_steps, config.steps)
    summary = {
        "schema": "direct-benefit-arm-summary-v1",
        "arm": R2_ARM,
        "action_id": action_id,
        "status": status,
        "target_steps": config.steps,
        "accepted_steps": int(solver.accepted_steps),
        "elapsed_s": time.perf_counter() - started,
        "stop": stop,
        "budget": budget,
        "combined_budget_before": combined_base,
        "combined_budget_after": {
            "adam": combined_base["adam"] + budget["adam"],
            "closures": combined_base["closures"] + budget["closures"],
            "lbfgs_steps": combined_base["lbfgs_steps"] + budget["lbfgs_steps"],
        },
        "recovery_eligible": status == "RESOURCE_LIMIT" and stop is not None and not stop.get("row"),
        "arm_spec": spec,
        "source_hashes": source_hashes(ROOT),
        "last_accepted_step": final_accepted,
        "stop_row": stop_row,
        "probe_timeseries": probes,
        "checkpoint_pointer": display(out_dir / "checkpoint_pointer.json"),
        "run_dir": display(out_dir),
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
    }
    write_json(out_dir / "summary.json", S._json_safe(summary))
    audit_benefit(action_id)
    return summary


def load_arm_summary(name: str) -> dict[str, Any] | None:
    if name == "B-R2":
        path = BENEFIT / "B_R2" / "summary.json"
    else:
        path = OUT / "runs" / name.replace("-", "_") / "summary.json"
    return read_json(path) if path.exists() else None


def arm_cost(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {"status": "NOT_RUN"}
    last = summary.get("last_accepted_step") or {}
    row = last or summary.get("stop_row") or {}
    fit_h = row.get("fit_H") or {}
    fit_e = row.get("fit_E") or {}
    metrics = (last.get("six_component_metrics") or {})
    return {
        "status": summary.get("status"),
        "accepted_steps": summary.get("accepted_steps"),
        "elapsed_s": summary.get("elapsed_s"),
        "budget": summary.get("budget"),
        "final_H_R": fit_h.get("residual_ratio"),
        "final_E_R": fit_e.get("residual_ratio"),
        "global_weighted_relative_l2": metrics.get("global_weighted_relative_l2"),
        "fixed_amplitude_error": metrics.get("fixed_amplitude_error"),
        "run_dir": summary.get("run_dir"),
        "recovery_eligible": summary.get("recovery_eligible"),
    }


def audit_benefit(action_id: str) -> dict[str, Any]:
    arms = {name: arm_cost(load_arm_summary(name)) for name in ("B-P", "B-R", "B-R2")}
    p = arms["B-P"]
    randoms = [arms["B-R"], arms["B-R2"]]
    comparable = (
        p.get("status") == "PASS" and
        all(r.get("status") == "PASS" for r in randoms) and
        p.get("accepted_steps") == 128 and
        all(r.get("accepted_steps") == 128 for r in randoms)
    )
    p_budget = p.get("budget") or {}
    random_adam = [int((r.get("budget") or {}).get("adam", 0) or 0) for r in randoms]
    random_elapsed = [float(r.get("elapsed_s", 0.0) or 0.0) for r in randoms]
    p_adam = int(p_budget.get("adam", 0) or 0)
    p_elapsed = float(p.get("elapsed_s", 0.0) or 0.0)
    adam_savings = [None if r == 0 else (r - p_adam) / r for r in random_adam]
    time_savings = [None if r == 0 else (r - p_elapsed) / r for r in random_elapsed]
    residual_cost_pass = bool(
        comparable and
        all(v is not None and v >= 0.20 for v in adam_savings) and
        all(v is not None and v >= 0.20 for v in time_savings)
    )
    m2_audit_path = OUT / "m2_audit.json"
    m2_audit = read_json(m2_audit_path) if m2_audit_path.exists() else {}
    field_gate_pass_arms = m2_audit.get("field_gate_pass_arms", [])
    field_valid_benefit = bool("B-P" in field_gate_pass_arms and "B-R" in field_gate_pass_arms)
    audit = {
        "schema": "direct-benefit-audit-v1",
        "action_id": action_id,
        "audit_lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "arms": arms,
        "comparable_residual_128": comparable,
        "p_vs_random_adam_savings": adam_savings,
        "p_vs_random_time_savings": time_savings,
        "residual_cost_benefit_pass": residual_cost_pass,
        "field_gate_benefit_pass": field_valid_benefit,
        "scientific_result": "FAIL",
        "reason": (
            "No benefit can support the paper mechanism because G128 field gate failed. "
            "Residual-window cost savings are reported separately."
        ),
        "recommendation": "do_not_use_benefit_to_unlock_longrun",
    }
    write_json(BENEFIT / "B_audit.json", S._json_safe(audit))
    write_report(audit)
    update_stage_status(audit)
    return audit


def write_report(audit: dict[str, Any]) -> None:
    lines = [
        "# B Report - Pretraining Benefit Pair",
        "",
        f"- Action: `{audit.get('action_id')}`; lab_run_id: `{audit.get('audit_lab_run_id')}`",
        "- Strict interpretation: field gate already failed in G128, so this B result cannot unlock 1024/8192.",
        "- Residual-window cost comparison is reported as engineering/diagnostic evidence only.",
        "",
        "| Arm | Status | Accepted | Adam | Closures | Elapsed s | H R | E R | Recovery |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name in ("B-P", "B-R", "B-R2"):
        arm = audit["arms"][name]
        budget = arm.get("budget") or {}
        lines.append(
            f"| {name} | {arm.get('status')} | {arm.get('accepted_steps')} | "
            f"{budget.get('adam')} | {budget.get('closures')} | {arm.get('elapsed_s')} | "
            f"{arm.get('final_H_R')} | {arm.get('final_E_R')} | {arm.get('recovery_eligible')} |"
        )
    lines.extend([
        "",
        "## Benefit Judgment",
        "",
        f"- Comparable residual-128 window: `{audit.get('comparable_residual_128')}`.",
        f"- P-vs-random Adam savings: `{audit.get('p_vs_random_adam_savings')}`.",
        f"- P-vs-random time savings: `{audit.get('p_vs_random_time_savings')}`.",
        f"- Residual cost benefit PASS: `{audit.get('residual_cost_benefit_pass')}`.",
        f"- Field-gate benefit PASS: `{audit.get('field_gate_benefit_pass')}`.",
        "- Conclusion: even if residual-window cost differs, it is not evidence of a useful PI-DON long-run solver while field/probe gates fail.",
        "",
        "## Files",
        "",
        f"- Audit JSON: `{display(BENEFIT / 'B_audit.json')}`",
        f"- R2 run: `{display(BENEFIT / 'B_R2')}`",
        "",
    ])
    (BENEFIT / "B_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def update_stage_status(audit: dict[str, Any]) -> None:
    path = OUT / "stage_status.json"
    stage = read_json(path) if path.exists() else {"schema": "direct-mechanism-stage-status-v1"}
    stage["B"] = {
        "schema": "direct-benefit-audit-v1",
        "status": "PASS",
        "scientific_result": audit.get("scientific_result"),
        "residual_cost_benefit_pass": audit.get("residual_cost_benefit_pass"),
        "field_gate_benefit_pass": audit.get("field_gate_benefit_pass"),
        "report": display(BENEFIT / "B_REPORT.md"),
        "audit": display(BENEFIT / "B_audit.json"),
        "updated_at_utc": utc_now(),
    }
    write_json(path, stage)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run-r2")
    run.add_argument("--action-id", required=True)
    run.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    audit = sub.add_parser("audit")
    audit.add_argument("--action-id", required=True)
    args = parser.parse_args()
    if args.cmd == "run-r2":
        summary = run_b_r2(args.action_id, args.device)
        print(json.dumps({
            "arm": summary["arm"],
            "status": summary["status"],
            "accepted_steps": summary["accepted_steps"],
            "budget": summary["budget"],
            "elapsed_s": summary["elapsed_s"],
            "run_dir": summary["run_dir"],
            "report": display(BENEFIT / "B_REPORT.md"),
        }, ensure_ascii=False, indent=2))
    elif args.cmd == "audit":
        audit_payload = audit_benefit(args.action_id)
        print(json.dumps({
            "scientific_result": audit_payload["scientific_result"],
            "residual_cost_benefit_pass": audit_payload["residual_cost_benefit_pass"],
            "field_gate_benefit_pass": audit_payload["field_gate_benefit_pass"],
            "report": display(BENEFIT / "B_REPORT.md"),
            "audit": display(BENEFIT / "B_audit.json"),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
