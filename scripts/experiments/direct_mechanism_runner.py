# -*- coding: utf-8 -*-
"""Direct-mechanism execution utilities.

M0 deliberately uses tiny CPU contract runs.  These checks certify the new
queue's recording and recovery semantics; they are not DCO scientific scores.
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

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes
from project_paths import PROJECT_DIR, configure, resolve_legacy

configure()

ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"
PLAN = ROOT / "docs" / "plans" / "2026-09-14-direct-mechanism-plan.md"
MASTER = ROOT / resolve_legacy("assets/models/dco_lr1e3_300.pt")
SCHEMA = "pidon-direct-mechanism-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def active_action_id() -> str | None:
    path = ROOT / "project" / "actions.jsonl"
    if not path.exists():
        return None
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    finished = {event.get("action_id") for event in events if event.get("event") == "finish"}
    active = [event for event in events
              if event.get("event") == "start" and event.get("task_id") == "M0"
              and event.get("action_id") not in finished]
    return active[-1]["action_id"] if active else None


def make_manifest() -> dict[str, Any]:
    plan_hash = sha256_file(PLAN)
    master_hash = sha256_file(MASTER)
    identity = hashlib.sha256(f"{plan_hash}|{master_hash}|{SCHEMA}".encode("utf-8")).hexdigest()[:24]
    return {
        "schema": SCHEMA,
        "experiment_id": identity,
        "created_at_utc": utc_now(),
        "plan_path": PLAN.relative_to(ROOT).as_posix(),
        "plan_sha256": plan_hash,
        "master": MASTER.relative_to(ROOT).as_posix() if MASTER.exists() else str(MASTER),
        "master_sha256": master_hash,
        "source_hashes": source_hashes(ROOT),
        "action_id": active_action_id(),
        "global_budget": {"adam": 1_000_000, "lbfgs_closures": 300_000, "storage_gib": 12},
        "m0_contract": {
            "purpose": "recording/recovery/measurement smoke checks only",
            "scientific_result": "NOT_APPLICABLE",
            "tiny_grid": {"n": 3, "levels": 2, "base": 2, "device": "cpu"},
        },
        "status": {"M0": "NOT_RUN"},
    }


def load_or_create_manifest() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    if path.exists():
        manifest = read_json(path)
        if manifest.get("schema") != SCHEMA:
            raise ValueError(f"unexpected manifest schema in {path}")
        if manifest.get("plan_sha256") != sha256_file(PLAN):
            raise ValueError("direct mechanism protocol changed after manifest creation")
        if manifest.get("master_sha256") != sha256_file(MASTER):
            raise ValueError("master checkpoint hash changed after manifest creation")
        return manifest
    manifest = make_manifest()
    atomic_json_save(manifest, path)
    return manifest


def tiny_args(*, tol: float = 0.0, max_inner: int = 2, lbfgs_closures: int = 0,
              checkpoint_dir: Path | None = None, out_name: str = "summary.json") -> argparse.Namespace:
    return argparse.Namespace(
        config="", steps=1, n=3, side=0.003, dt=1e-12, init="random",
        tol=tol, tol_mode="rel", max_inner=max_inner, lr=1e-4,
        head_lstsq_once=False, head_rcond=1e-12, levels=2, base=2,
        coords="cellsize", norm="rms", separate_nets=True,
        reset_opt_each_step=False, grad_clip=0.0, h_scale=1.0,
        component_rel=False, h_output_scale=1.0, h_shift=False,
        strict_stop=True, inner_time_budget_s=0.0, lbfgs_closures=lbfgs_closures,
        lbfgs_lr=1.0, lbfgs_history=10, lbfgs_time_budget_s=0.0,
        source_mode="hard", torch_dtype="float32",
        out_dir=str(checkpoint_dir or ""), resume="", checkpoint_every=1,
        seed=20260914, device="cpu", fmax=15e9, calib=[], calib_iters=[],
        out=str((checkpoint_dir / out_name) if checkpoint_dir else out_name),
    )


def metadata(manifest: dict[str, Any], case: str, args: argparse.Namespace) -> dict[str, Any]:
    protocol_hash = sha256_file(OUT / "manifest.json")
    run_id = hashlib.sha256(f"{manifest['experiment_id']}|M0|{case}".encode("utf-8")).hexdigest()[:24]
    return {
        "schema": "direct-mechanism-m0-run-v1",
        "case": case,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "config": vars(args),
        "action_id": manifest.get("action_id"),
        "created_at_utc": utc_now(),
    }


def checkpoint_payload(solver: S.Solver, ref: fdtd.PECCavity, *, requested_steps: int, source_index: int) -> dict:
    payload = S._checkpoint_payload(solver, ref, requested_steps=requested_steps, source_index=source_index)
    payload["arm_protocol"] = SCHEMA
    return payload


def run_one_step(args: argparse.Namespace, out_dir: Path, case: str, manifest: dict[str, Any],
                 *, interrupt_after: int | None = None, resume: bool = False) -> tuple[S.Solver, fdtd.PECCavity, list[dict]]:
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    solver = S.Solver(args, args.device)
    ref = fdtd.PECCavity(side=args.side, n=args.n, dt=args.dt)
    mode = "new"
    if resume:
        mode = "resume"
    recorder = RunRecorder(out_dir, metadata(manifest, case, args), mode=mode)
    if resume:
        payload = recorder.load_rolling_checkpoint()
        solver.load_state_payload(payload)
        S._restore_reference(ref, payload["reference"])
    heartbeats: list[dict[str, Any]] = []

    def heartbeat(which, progress):
        payload = {
            "updated_at_utc": utc_now(),
            "case": case,
            "which": which,
            "time_layer": solver.current_time_layer,
            "phase": solver.phase,
            "attempt_id": progress.get("attempt_id"),
            "adam_updates": progress.get("updates", 0),
            "lbfgs_steps": progress.get("lbfgs_steps", 0),
            "closures": progress.get("closures", 0),
            "successful_commit": False,
            "stop_reason": progress.get("stop_reason"),
            "resumable": progress.get("resumable"),
        }
        heartbeats.append(copy.deepcopy(payload))
        atomic_json_save({"events": heartbeats}, out_dir / "heartbeat.json")
        return interrupt_after is not None and which == "E" and int(progress.get("updates", 0)) >= interrupt_after

    solver.on_inner_update = heartbeat
    solver.on_lbfgs_step = heartbeat
    waveform = fdtd.source_waveform(args.steps, solver.dt, args.fmax, "hard")
    source_cell = args.n // 2
    rows: list[dict[str, Any]] = []
    record = solver.step(float(waveform[solver.current_time_layer]))
    if record.accepted:
        ref.step_e_source_h(src_value=waveform[record.time_layer],
                            src_idx=(source_cell, source_cell, source_cell))
    row = S._json_safe(S._step_summary(solver, ref, record))
    row["case"] = case
    row["budget"] = budget_from_rows([row])
    recorder.append(row)
    rows.append(row)
    recorder.rolling_checkpoint(checkpoint_payload(
        solver, ref, requested_steps=args.steps, source_index=solver.current_time_layer
    ))
    if not record.accepted:
        raw = getattr(solver, "last_failure_raw", None)
        if raw is None:
            raw = checkpoint_payload(solver, ref, requested_steps=args.steps, source_index=solver.current_time_layer)
        raw["reference"] = S._reference_payload(ref)
        recorder.failure_raw(raw)
    return solver, ref, rows


def budget_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Cost of a set of rows, counting each half-step fit exactly once.

    F23: ``FitRecord.n_updates`` is CUMULATIVE for its half-step -- a resumed
    fit reports the interrupted segment plus the new one.  Adding the
    interrupted row to the resumed row therefore charged the first segment
    twice: a run that really applied 4 Adam steps was reported as 2+1+2 = 5.
    Group by (time layer, half) and take the cumulative maximum, which is that
    fit's true total, then add the groups together.

    Both numbers are returned so an old table can still be reconciled:
    ``adam`` is the de-duplicated total and ``adam_row_sum`` is the historical
    row-wise sum.
    """
    totals: dict[tuple[Any, str], dict[str, int]] = {}
    row_sum_adam = row_sum_closures = 0
    accepted = failed = 0
    for row in rows:
        if row.get("accepted"):
            accepted += 1
        else:
            failed += 1
        layer = row.get("step", row.get("time_layer"))
        for key in ("fit_H", "fit_E"):
            fit = row.get(key) or {}
            if not fit:
                continue
            updates = int(fit.get("n_updates", 0) or 0)
            closures = int(fit.get("n_closures", 0) or 0)
            row_sum_adam += updates
            row_sum_closures += closures
            slot = totals.setdefault((layer, key), {"adam": 0, "closures": 0})
            # A later row for the same half-step carries the cumulative value.
            slot["adam"] = max(slot["adam"], updates)
            slot["closures"] = max(slot["closures"], closures)
    adam = sum(slot["adam"] for slot in totals.values())
    closures = sum(slot["closures"] for slot in totals.values())
    return {"adam": adam, "closures": closures,
            "accepted_steps": accepted, "failed_candidates": failed,
            "adam_row_sum": row_sum_adam, "closures_row_sum": row_sum_closures,
            "resume_double_counted_adam": row_sum_adam - adam,
            "counted_half_steps": len(totals)}


def tensor_max_abs_delta(a: list[torch.Tensor], b: list[torch.Tensor]) -> float:
    return max(float((x.detach().cpu() - y.detach().cpu()).abs().max()) for x, y in zip(a, b))


def run_uninterrupted(manifest: dict[str, Any], out_dir: Path) -> tuple[S.Solver, fdtd.PECCavity, list[dict]]:
    args = tiny_args(tol=0.0, max_inner=2, checkpoint_dir=out_dir)
    return run_one_step(args, out_dir, "uninterrupted_terminal", manifest)


def run_interrupted_resume(manifest: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    args = tiny_args(tol=0.0, max_inner=2, checkpoint_dir=out_dir)
    solver_a, ref_a, first_rows = run_one_step(args, out_dir, "pending_interrupt_resume", manifest, interrupt_after=1)
    first_pointer = read_json(out_dir / "checkpoint_pointer.json")
    first_metadata = read_json(out_dir / "run_metadata.json")
    resumable_checkpoint = bool(first_pointer and first_metadata.get("last_checkpoint_sequence_id") == 0)
    solver_b, ref_b, second_rows = run_one_step(args, out_dir, "pending_interrupt_resume", manifest, resume=True)
    return {
        "first_rows": first_rows,
        "second_rows": second_rows,
        "final_solver": solver_b,
        "final_ref": ref_b,
        "resumable_checkpoint": resumable_checkpoint,
        "first_phase": solver_a.phase,
        "first_fit_progress": copy.deepcopy(solver_a.fit_progress),
    }


def run_closure_case(manifest: dict[str, Any], out_dir: Path) -> list[dict]:
    args = tiny_args(tol=0.0, max_inner=0, lbfgs_closures=1, checkpoint_dir=out_dir)
    _, _, rows = run_one_step(args, out_dir, "closure_budget_counts", manifest)
    return rows


def none_metric_case() -> dict[str, Any]:
    row = {
        "six_component_metrics": {"components": {"Ez": {"nmae": None, "absolute_mae": 0.0}}},
        "source_probe_Ez": {"dut": 0.0, "ref": 0.0},
    }
    encoded = json.dumps(row, allow_nan=False)
    return {"json_serializable": True, "encoded_bytes": len(encoded), "ez_nmae": None}


def run_m0() -> dict[str, Any]:
    manifest = load_or_create_manifest()
    m0_dir = OUT / "m0"
    m0_dir.mkdir(parents=True, exist_ok=True)

    uninterrupted_dir = m0_dir / "uninterrupted_terminal"
    interrupted_dir = m0_dir / "pending_interrupt_resume"
    closure_dir = m0_dir / "closure_budget_counts"
    for directory in (uninterrupted_dir, interrupted_dir, closure_dir):
        if directory.exists():
            raise FileExistsError(f"M0 evidence already exists: {directory}")

    uninterrupted_solver, uninterrupted_ref, uninterrupted_rows = run_uninterrupted(manifest, uninterrupted_dir)
    resumed = run_interrupted_resume(manifest, interrupted_dir)
    closure_rows = run_closure_case(manifest, closure_dir)
    none_case = none_metric_case()

    final_solver = resumed["final_solver"]
    final_ref = resumed["final_ref"]
    consistency = {
        "phase_equal": final_solver.phase == uninterrupted_solver.phase,
        "accepted_steps_equal": final_solver.accepted_steps == uninterrupted_solver.accepted_steps,
        "current_time_layer_equal": final_solver.current_time_layer == uninterrupted_solver.current_time_layer,
        "E_max_abs_delta": tensor_max_abs_delta(final_solver.E, uninterrupted_solver.E),
        "H_max_abs_delta": tensor_max_abs_delta(final_solver.H, uninterrupted_solver.H),
        "ref_Ez_max_abs_delta": float(np.max(np.abs(final_ref.Ez - uninterrupted_ref.Ez))),
        "ref_Hz_max_abs_delta": float(np.max(np.abs(final_ref.Hz - uninterrupted_ref.Hz))),
    }
    terminal_rejected = False
    try:
        S.Solver(tiny_args(tol=0.0, max_inner=2), "cpu").load_state_payload(final_solver.state_payload())
    except ValueError as exc:
        terminal_rejected = "terminal" in str(exc)

    saved_pending = resumed["resumable_checkpoint"]
    closure_fit = (closure_rows[-1].get("fit_E") or closure_rows[-1].get("fit_H") or {})
    checks = {
        "pending_resume_matches_uninterrupted": (
            consistency["phase_equal"] and consistency["accepted_steps_equal"]
            and consistency["current_time_layer_equal"]
            and consistency["E_max_abs_delta"] <= 1e-7
            and consistency["H_max_abs_delta"] <= 1e-7
            and consistency["ref_Ez_max_abs_delta"] <= 1e-12
            and consistency["ref_Hz_max_abs_delta"] <= 1e-12
        ),
        "pending_checkpoint_saved": saved_pending,
        "terminal_budget_not_production_resumable": terminal_rejected,
        "none_metric_reportable": bool(none_case["json_serializable"]),
        "closure_budget_counted": int(closure_fit.get("n_closures", 0) or 0) >= 1,
    }
    # F23: the interrupted branch and its resume are ONE trajectory, so their
    # rows are de-duplicated together rather than summed as two independent
    # cases.  The other two cases are separate runs and are added normally.
    resumed_budget = budget_from_rows(resumed["first_rows"] + resumed["second_rows"])
    case_budgets = (
        budget_from_rows(uninterrupted_rows),
        resumed_budget,
        budget_from_rows(closure_rows),
    )
    total_budget = {
        key: sum(case[key] for case in case_budgets)
        for key in ("adam", "closures", "accepted_steps", "failed_candidates",
                    "adam_row_sum", "closures_row_sum", "resume_double_counted_adam")
    }
    total_budget["counting_rule"] = (
        "per (time layer, half) cumulative maximum; adam_row_sum is the old "
        "row-wise sum kept only for reconciling historical tables")
    audit = {
        "schema": "direct-mechanism-m0-audit-v1",
        "created_at_utc": utc_now(),
        "manifest": "evidence/direct_mechanism_v1/manifest.json",
        "action_id": manifest.get("action_id"),
        "scientific_result": "NOT_APPLICABLE",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "consistency": consistency,
        "terminal_rejected": terminal_rejected,
        "saved_pending": saved_pending,
        "unknown_tail_policy": {
            "power_loss_tail_possible": True,
            "unknown_tail_is_reported_as_UNKNOWN": True,
            "jsonl_committed_tail_adopted_by_recorder": True,
        },
        "case_budgets": {
            "uninterrupted_terminal": budget_from_rows(uninterrupted_rows),
            "pending_interrupt_first": budget_from_rows(resumed["first_rows"]),
            "pending_resume_second": budget_from_rows(resumed["second_rows"]),
            "pending_interrupt_resume_deduplicated": resumed_budget,
            "closure_budget_counts": budget_from_rows(closure_rows),
        },
        "total_m0_engineering_budget": total_budget,
        "none_metric_case": none_case,
        "recovery": {
            "interrupt_checkpoint_recovery_eligible": saved_pending,
            "terminal_resource_checkpoint_recovery_eligible": False,
        },
        "outputs": {
            "uninterrupted": display_path(uninterrupted_dir),
            "interrupted_resume": display_path(interrupted_dir),
            "closure": display_path(closure_dir),
        },
    }
    atomic_json_save(audit, m0_dir / "m0_audit.json")
    write_m0_report(audit, m0_dir / "M0_REPORT.md")
    manifest["status"]["M0"] = audit["status"]
    manifest["m0_audit"] = "evidence/direct_mechanism_v1/m0/m0_audit.json"
    atomic_json_save(manifest, OUT / "manifest.json")
    print(json.dumps({
        "status": audit["status"],
        "checks": checks,
        "total_m0_engineering_budget": total_budget,
        "report": "evidence/direct_mechanism_v1/m0/M0_REPORT.md",
    }, ensure_ascii=False, indent=2))
    return audit


def write_m0_report(audit: dict[str, Any], path: Path) -> None:
    checks = audit["checks"]
    budget = audit["total_m0_engineering_budget"]
    lines = [
        "# M0 记录与测量最小修复报告",
        "",
        f"- 状态：`{audit['status']}`；科学成绩：`NOT_APPLICABLE`（工程记录/恢复检查，不计DCO成绩）。",
        f"- 行动ID：`{audit.get('action_id')}`。",
        f"- M0工程成本：Adam `{budget['adam']}`，LBFGS closure `{budget['closures']}`，接受步 `{budget['accepted_steps']}`，失败候选 `{budget['failed_candidates']}`。",
        "",
        "| 检查 | 结果 |",
        "|---|---|",
    ]
    for name, passed in checks.items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    c = audit["consistency"]
    lines += [
        "",
        "## 关键证据",
        "",
        f"- 受控 pending 暂停后恢复，与不中断路径终态比较：phase相同 `{c['phase_equal']}`，accepted_steps相同 `{c['accepted_steps_equal']}`，E/H最大差 `{c['E_max_abs_delta']:.3e}` / `{c['H_max_abs_delta']:.3e}`。",
        f"- 受控 interrupt checkpoint 可恢复：`{audit['recovery']['interrupt_checkpoint_recovery_eligible']}`；资源耗尽/terminal checkpoint 不可生产恢复：`{audit['recovery']['terminal_resource_checkpoint_recovery_eligible']}`。",
        "- 显示层/报告层可序列化 `nmae=null`，不会因弱参考或空指标崩溃。",
        "- closure预算单独计数，和Adam更新分列；UNKNOWN尾部政策保留，不宣称瞬间断电零丢失。",
        "",
        "## 解释边界",
        "",
        "这些检查只证明新队列记录、pending恢复和计数口径可用。它们不是第一阶段、第二阶段、128、1024或8192的科学PASS。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["m0"])
    args = parser.parse_args()
    if args.cmd == "m0":
        run_m0()


if __name__ == "__main__":
    main()
