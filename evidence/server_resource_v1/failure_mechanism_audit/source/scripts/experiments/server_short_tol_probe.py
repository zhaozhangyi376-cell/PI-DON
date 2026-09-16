"""Bounded online tolerance probe using the best existing DCO checkpoint."""
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
PLAN = ROOT / "docs/plans/2026-09-15-server-batch2-protocol.md"
MASTER = ROOT / "assets/models/dco_lr1e3_300.pt"
SCHEMA = "pidon-server-short-tol-probe-v1"
ADAM_CAP = 150_000
PER_FIT_CAP = 3000


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(data, path)


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def prepare_empty_output(name: str) -> Path:
    out = BASE / name
    out.mkdir(parents=True, exist_ok=False)
    return out


def copy_source_snapshot(out: Path) -> dict[str, str | None]:
    source = out / "source"
    source.mkdir(exist_ok=True)
    copied = {}
    for rel in (
        "scripts/experiments/server_short_tol_probe.py",
        "scripts/experiments/server_local_review.py",
        "src/pidon/pidon_solve.py",
        "src/pidon/pidon_recording.py",
        "src/pidon/dco.py",
        "src/pidon/fdtd.py",
        "docs/plans/2026-09-15-server-batch2-protocol.md",
        "docs/plans/2026-09-15-server-batch2-recorder-fix.md",
        "tools/server_batch2_queue.py",
        "project_paths.py",
    ):
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied[rel] = sha256_file(path)
    return copied


def field_gate(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("six_component_metrics") or {}
    components = metrics.get("components") or {}
    component_rows = {}
    component_pass = True
    for name, item in components.items():
        weak = bool(item.get("weak_reference"))
        if weak:
            passed = bool(item.get("weak_absolute_pass"))
            reason = f"weak_absolute_pass={passed}"
        else:
            nmae = item.get("nmae")
            passed = nmae is not None and float(nmae) <= 0.01
            reason = f"nmae={nmae}"
        component_rows[name] = {"pass": passed, "weak_reference": weak, "reason": reason}
        component_pass = component_pass and passed
    q = metrics.get("global_weighted_relative_l2")
    fixed = metrics.get("fixed_amplitude_error")
    q_pass = q is not None and float(q) <= 0.05
    fixed_pass = fixed is not None and float(fixed) <= 1e-3
    return {
        "pass": bool(component_pass and q_pass and fixed_pass),
        "global_weighted_relative_l2": q,
        "global_weighted_relative_l2_le_5pct": q_pass,
        "fixed_amplitude_error": fixed,
        "fixed_amplitude_error_le_1e_minus_3": fixed_pass,
        "component_pass": component_pass,
        "components": component_rows,
        "source_outside_probes": row.get("source_outside_probes"),
        "source_probe_Ez": row.get("source_probe_Ez"),
    }


def make_config(out: Path, args: argparse.Namespace, steps: int) -> argparse.Namespace:
    return argparse.Namespace(
        config="",
        steps=steps,
        n=31,
        side=0.05,
        dt=3.075e-12,
        init=display(MASTER),
        tol=float(args.tol),
        tol_mode="rel",
        max_inner=PER_FIT_CAP,
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
    adam = closures = lbfgs_steps = 0
    for key in ("fit_H", "fit_E"):
        fit = row.get(key) or {}
        adam += int(fit.get("n_updates", 0) or 0)
        closures += int(fit.get("n_closures", 0) or 0)
        lbfgs_steps += int(fit.get("n_lbfgs_steps", 0) or 0)
    return {"adam": adam, "closures": closures, "lbfgs_steps": lbfgs_steps}


def sum_cost(rows: list[dict[str, Any]]) -> dict[str, int]:
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    for row in rows:
        cost = row_cost(row)
        for key in total:
            total[key] += cost[key]
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


def budget_wrapper(solver: S.Solver, rows: list[dict[str, Any]]) -> dict[str, Any]:
    original = solver.inner_train
    state: dict[str, Any] = {"caps": {}, "resource_limited": False, "events": []}

    def wrapped(field, target, which="shared"):
        before = sum_cost(rows)
        if which == "E" and getattr(solver, "pending_fit_H", None) is not None:
            fit = solver.pending_fit_H
            before["adam"] += int(fit.n_updates or 0)
            before["closures"] += int(fit.n_closures or 0)
            before["lbfgs_steps"] += int(fit.n_lbfgs_steps or 0)
        remaining = max(0, ADAM_CAP - before["adam"])
        cap = min(PER_FIT_CAP, remaining)
        prior = solver.a.max_inner
        solver.a.max_inner = cap
        info = {"which": which, "time_layer": int(solver.current_time_layer),
                "cost_before": before, "cap_adam": int(cap),
                "resource_cap_limited": cap < PER_FIT_CAP}
        state["caps"][which] = info
        try:
            record = original(field, target, which)
        finally:
            solver.a.max_inner = prior
        if info["resource_cap_limited"] and not record.passed:
            state["resource_limited"] = True
            state["events"].append({**info, "stop_reason": record.stop_reason})
        return record

    solver.inner_train = wrapped
    return state


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = prepare_empty_output(args.output_name)
    requested_steps = 128 if args.continue_to_128_if_pass64 else int(args.target_steps)
    config = make_config(out, args, requested_steps)
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
    write_json(out / "manifest.json", S._json_safe(metadata))
    rows: list[dict[str, Any]] = []
    traces = trace_wrapper(solver)
    budget_state = budget_wrapper(solver, rows)
    waveform = fdtd.source_waveform(requested_steps, solver.dt, config.fmax, "hard")
    source_cell = config.n // 2
    started = time.perf_counter()
    stop: dict[str, Any] | None = None
    gate64: dict[str, Any] | None = None
    gate128: dict[str, Any] | None = None
    snapshot_steps = {32, 64, 128}
    while solver.accepted_steps < requested_steps:
        layer = solver.current_time_layer
        record = solver.step(float(waveform[layer]))
        if record.accepted:
            ref.step_e_source_h(src_value=waveform[layer],
                                src_idx=(source_cell, source_cell, source_cell))
        row = S._json_safe(S._step_summary(solver, ref, record))
        row.update({
            "arm": "TOL1E5-P",
            "arm_spec": {
                "init": display(MASTER),
                "tol": config.tol,
                "lr": config.lr,
                "reset_opt_each_step": config.reset_opt_each_step,
                "target_steps": args.target_steps,
                "conditional_target_steps": requested_steps,
                "adam_cap": ADAM_CAP,
                "per_fit_cap": PER_FIT_CAP,
            },
            "fit_traces": S._json_safe(copy.deepcopy(traces)),
            "budget_caps": S._json_safe(copy.deepcopy(budget_state.get("caps", {}))),
            "actual_wall_s": time.perf_counter() - started,
        })
        row["row_cost"] = row_cost(row)
        recorder.append(row)
        rows.append(row)
        recorder.rolling_checkpoint(S._checkpoint_payload(
            solver, ref, requested_steps=requested_steps, source_index=solver.current_time_layer))
        if record.accepted and solver.accepted_steps in snapshot_steps:
            recorder.snapshot(solver.accepted_steps, S._checkpoint_payload(
                solver, ref, requested_steps=requested_steps, source_index=layer + 1))
        if not record.accepted:
            if budget_state.get("resource_limited"):
                stop = {"reason": "RESOURCE_LIMIT", "row": row,
                        "budget_events": budget_state.get("events", [])}
            else:
                stop = {"reason": "FIT_FAIL", "row": row}
            raw = getattr(solver, "last_failure_raw", None)
            recorder.failure_raw(raw if raw is not None else S._checkpoint_payload(
                solver, ref, requested_steps=requested_steps, source_index=layer))
            break
        if solver.accepted_steps == 64:
            gate64 = field_gate(row)
            if not args.continue_to_128_if_pass64 or not gate64["pass"]:
                stop = {"reason": "STOP_AT_64", "field_gate_64": gate64}
                break
        if solver.accepted_steps == 128:
            gate128 = field_gate(row)
        cost = sum_cost(rows)
        if cost["adam"] >= ADAM_CAP:
            stop = {"reason": "RESOURCE_LIMIT", "detail": "adam_cap_exhausted_after_accepted_step"}
            break
    accepted_rows = [row for row in rows if row.get("accepted")]
    last = accepted_rows[-1] if accepted_rows else None
    if last and gate64 is None and int(last.get("accepted_steps", 0)) >= 64:
        gate64 = field_gate(last)
    if last and int(last.get("accepted_steps", 0)) >= 128 and gate128 is None:
        gate128 = field_gate(last)
    budget = sum_cost(rows)
    reached64 = int(solver.accepted_steps) >= 64
    status = "PASS" if reached64 else ("RESOURCE_LIMIT" if (stop or {}).get("reason") == "RESOURCE_LIMIT" else "FAIL")
    scientific = "PASS_64" if gate64 and gate64["pass"] else "FAIL"
    summary = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "status": status,
        "scientific_result": scientific,
        "accepted_steps": int(solver.accepted_steps),
        "target_steps": int(args.target_steps),
        "conditional_target_steps": int(requested_steps),
        "stop": stop,
        "budget": budget,
        "new_adam_updates": budget["adam"],
        "new_closures": budget["closures"],
        "elapsed_s": time.perf_counter() - started,
        "field_gate_64": gate64,
        "field_gate_128": gate128,
        "last_accepted_step": last,
        "recovery_eligible": status == "RESOURCE_LIMIT" and stop is not None and not stop.get("row"),
        "run_dir": display(out),
        "checkpoint_pointer": display(out / "checkpoint_pointer.json"),
    }
    write_json(out / "summary.json", S._json_safe(summary))
    lines = [
        "# SR-SHORT tolerance probe",
        "",
        "This is a bounded diagnostic online run, not a long-run unlock.",
        "",
        f"- Status: `{status}`; scientific_result: `{scientific}`",
        f"- Accepted steps: `{summary['accepted_steps']}`",
        f"- Adam updates: `{budget['adam']}`; closures: `{budget['closures']}`",
        f"- 64-step field gate: `{None if gate64 is None else gate64['pass']}`",
        f"- Recovery eligible: `{summary['recovery_eligible']}`",
        "",
        "Original G128 failure remains unchanged. 1024/8192 require a separate SR-G128 review.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "scientific_result": scientific,
        "accepted_steps": summary["accepted_steps"],
        "updates": budget["adam"],
        "output": str(out),
    }, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--tol", type=float, default=1e-5)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=2026091508)
    parser.add_argument("--target-steps", type=int, default=64)
    parser.add_argument("--output-name", default="short_tol_probe")
    parser.add_argument("--continue-to-128-if-pass64", action="store_true")
    run(parser.parse_args())
