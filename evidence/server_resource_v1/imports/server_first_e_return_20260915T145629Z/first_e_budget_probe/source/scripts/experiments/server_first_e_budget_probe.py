"""Fixed first-E budget probe after SR-FAIL-AUDIT."""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from project_paths import PROJECT_DIR, configure
configure()

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes


ROOT = PROJECT_DIR
BASE = ROOT / "evidence/server_resource_v1"
OUT_NAME = "first_e_budget_probe"
PLAN = ROOT / "docs/plans/2026-09-15-first-e-budget-probe-protocol.md"
MASTER = ROOT / "assets/models/dco_lr1e3_300.pt"
SCHEMA = "pidon-server-first-e-budget-probe-v1"


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(S._json_safe(data), path)


def prepare_output(name: str) -> Path:
    out = BASE / name
    out.mkdir(parents=True, exist_ok=False)
    return out


def copy_source_snapshot(out: Path) -> dict[str, str | None]:
    source = out / "source"
    source.mkdir(exist_ok=True)
    copied = {}
    for rel in (
        "scripts/experiments/server_first_e_budget_probe.py",
        "scripts/experiments/server_short_tol_probe.py",
        "scripts/experiments/server_failure_mechanism_audit.py",
        "src/pidon/pidon_solve.py",
        "src/pidon/pidon_recording.py",
        "src/pidon/dco.py",
        "src/pidon/fdtd.py",
        "docs/plans/2026-09-15-first-e-budget-probe-protocol.md",
        "tools/server_first_e_queue.py",
        "project_paths.py",
    ):
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied[rel] = sha256_file(path)
    return copied


def make_config(out: Path, args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        config="",
        steps=1,
        n=31,
        side=0.05,
        dt=3.075e-12,
        init=display(MASTER),
        tol=1e-5,
        tol_mode="rel",
        max_inner=int(args.max_inner),
        lr=float(args.lr),
        head_lstsq_once=False,
        head_rcond=1e-12,
        levels=4,
        base=32,
        coords="cellsize",
        norm="rms",
        separate_nets=True,
        reset_opt_each_step=True,
        grad_clip=0.0,
        h_scale=1.0,
        component_rel=False,
        h_output_scale=1.0,
        h_shift=True,
        strict_stop=True,
        inner_time_budget_s=0.0,
        lbfgs_closures=0,
        lbfgs_lr=1.0,
        lbfgs_history=10,
        lbfgs_time_budget_s=0.0,
        source_mode="hard",
        torch_dtype="float32",
        out_dir=str(out),
        resume="",
        checkpoint_every=1,
        seed=int(args.seed),
        device=args.device,
        fmax=15e9,
        calib=[],
        calib_iters=[],
        out=str(out / "summary.json"),
    )


def row_cost(row: dict[str, Any]) -> dict[str, int]:
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    for key in ("fit_H", "fit_E"):
        fit = row.get(key) or {}
        total["adam"] += int(fit.get("n_updates", 0) or 0)
        total["closures"] += int(fit.get("n_closures", 0) or 0)
        total["lbfgs_steps"] += int(fit.get("n_lbfgs_steps", 0) or 0)
    return total


def trace_wrapper(solver: S.Solver) -> dict[str, list[dict[str, Any]]]:
    original = solver.inner_train
    traces: dict[str, list[dict[str, Any]]] = {}

    def wrapped(field, target, which="shared"):
        record = original(field, target, which)
        traces[which] = copy.deepcopy(getattr(solver, "last_fit_trace", []))
        return record

    solver.inner_train = wrapped
    return traces


def trace_crossing(trace: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    for item in trace:
        loss = item.get("loss")
        if loss is not None and float(loss) <= threshold:
            return {"updates": int(item.get("updates", 0)), "loss": float(loss)}
    return None


def classify(row: dict[str, Any], max_inner: int) -> dict[str, Any]:
    fit_e = row.get("fit_E") or {}
    trace = (row.get("fit_traces") or {}).get("E", [])
    residual = fit_e.get("residual_ratio")
    passed = bool(fit_e.get("passed"))
    return {
        "passed_1e_minus_5": passed,
        "residual_ratio": residual,
        "updates": fit_e.get("n_updates"),
        "max_inner": max_inner,
        "crosses_1e_minus_4": trace_crossing(trace, 1e-4),
        "crosses_1e_minus_5": trace_crossing(trace, 1e-5),
        "remaining_factor_to_1e_minus_5": None if residual is None else float(residual) / 1e-5,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = prepare_output(args.output_name)
    config = make_config(out, args)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if config.device == "cuda" and torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    solver = S.Solver(config, args.device)
    ref = fdtd.PECCavity(side=config.side, n=config.n, dt=config.dt)
    metadata = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "protocol": display(PLAN),
        "protocol_sha256": sha256_file(PLAN),
        "config": vars(config).copy(),
        "master": display(MASTER),
        "master_sha256": sha256_file(MASTER),
        "source_hashes": source_hashes(ROOT),
        **S.formal_run_identity(config),
    }
    recorder = RunRecorder(out, metadata, mode="new")
    metadata["source_snapshot_hashes"] = copy_source_snapshot(out)
    write_json(out / "manifest.json", metadata)
    traces = trace_wrapper(solver)
    waveform = fdtd.source_waveform(1, solver.dt, config.fmax, "hard")
    source_cell = config.n // 2
    started = time.perf_counter()
    record = solver.step(float(waveform[0]))
    if record.accepted:
        ref.step_e_source_h(src_value=waveform[0], src_idx=(source_cell, source_cell, source_cell))
    row = S._json_safe(S._step_summary(solver, ref, record))
    row.update({
        "probe": "SR-E1-BUDGET",
        "fit_traces": S._json_safe(copy.deepcopy(traces)),
        "arm_spec": {
            "init": display(MASTER),
            "tol": config.tol,
            "lr": config.lr,
            "max_inner": config.max_inner,
            "target": "first_E_pending_only",
            "no_trajectory_unlock": True,
        },
        "row_cost": row_cost(row),
        "actual_wall_s": time.perf_counter() - started,
    })
    recorder.append(row)
    recorder.rolling_checkpoint(S._checkpoint_payload(
        solver, ref, requested_steps=1, source_index=solver.current_time_layer))
    if record.accepted:
        recorder.snapshot(1, S._checkpoint_payload(solver, ref, requested_steps=1, source_index=1))
    else:
        raw = getattr(solver, "last_failure_raw", None)
        recorder.failure_raw(raw if raw is not None else S._checkpoint_payload(
            solver, ref, requested_steps=1, source_index=0))
    evidence_class = classify(row, config.max_inner)
    status = "PASS" if record.accepted and evidence_class["passed_1e_minus_5"] else "FAIL"
    summary = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "status": status,
        "scientific_result": "DIAGNOSTIC_PASS" if status == "PASS" else "DIAGNOSTIC_FAIL",
        "accepted_steps": int(solver.accepted_steps),
        "new_adam_updates": row["row_cost"]["adam"],
        "new_closures": row["row_cost"]["closures"],
        "elapsed_s": time.perf_counter() - started,
        "classification": evidence_class,
        "row": row,
        "long_run_unlocked": False,
        "recovery_eligible": False,
        "run_dir": display(out),
    }
    write_json(out / "summary.json", summary)
    lines = [
        "# SR-E1-BUDGET first-E budget probe",
        "",
        "This is a fixed first-half-step diagnostic, not a trajectory validation.",
        "",
        f"- Status: `{status}`; scientific_result: `{summary['scientific_result']}`",
        f"- Accepted steps: `{summary['accepted_steps']}`",
        f"- Adam updates: `{summary['new_adam_updates']}`; closures: `{summary['new_closures']}`",
        f"- First E residual: `{evidence_class['residual_ratio']}`",
        f"- Crosses 1e-4: `{evidence_class['crosses_1e_minus_4']}`",
        f"- Crosses 1e-5: `{evidence_class['crosses_1e_minus_5']}`",
        f"- Long run unlocked: `{summary['long_run_unlocked']}`",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "scientific_result": summary["scientific_result"],
        "accepted_steps": summary["accepted_steps"],
        "updates": summary["new_adam_updates"],
        "residual_ratio": evidence_class["residual_ratio"],
        "output": str(out),
    }, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=2026091509)
    parser.add_argument("--max-inner", type=int, default=9000)
    parser.add_argument("--output-name", default=OUT_NAME)
    run(parser.parse_args())

