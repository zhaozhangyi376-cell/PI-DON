"""Replay the SR-64 first failing step from the last clean checkpoint."""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import torch

from project_paths import PROJECT_DIR, configure
configure()

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes


ROOT = PROJECT_DIR
BASE = ROOT / "evidence/server_resource_v1"
PLAN = ROOT / "docs/plans/2026-09-16-step36e-budget-probe-protocol.md"
DEFAULT_SOURCE = BASE / "strict64_probe"
OUT_NAME = "step36e_budget_probe"
SCHEMA = "pidon-server-step36e-budget-probe-v1"


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
        "scripts/experiments/server_step36e_budget_probe.py",
        "scripts/experiments/server_short_tol_probe.py",
        "src/pidon/pidon_solve.py",
        "src/pidon/pidon_contract.py",
        "src/pidon/pidon_recording.py",
        "src/pidon/fdtd.py",
        "src/pidon/dco.py",
        "docs/plans/2026-09-16-step36e-budget-probe-protocol.md",
        "tools/server_step36e_queue.py",
        "project_paths.py",
    ):
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied[rel] = sha256_file(path)
    return copied


def make_config(payload: dict[str, Any], out: Path, args: argparse.Namespace) -> argparse.Namespace:
    saved = dict(payload["frozen_config"])
    # This value must initially match the checkpoint for the compatibility
    # check.  The registered diagnostic cap is applied after loading.
    saved.update({
        "config": "",
        "steps": int(payload.get("requested_steps", 64)),
        "out_dir": str(out),
        "resume": "",
        "checkpoint_every": 1,
        "device": args.device,
        "calib": [],
        "calib_iters": [],
        "out": str(out / "summary.json"),
    })
    return argparse.Namespace(**saved)


def load_payload(path: Path) -> dict[str, Any]:
    return torch.load(path, map_location="cpu", weights_only=False)


def select_clean_checkpoint(source: Path) -> tuple[Path, dict[str, Any]]:
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for name in ("checkpoint_A.pt", "checkpoint_B.pt"):
        path = source / name
        if not path.is_file():
            continue
        payload = load_payload(path)
        if payload.get("phase") == "before_H" and int(payload.get("accepted_steps", -1)) >= 0:
            candidates.append((int(payload["accepted_steps"]), path, payload))
    if not candidates:
        raise FileNotFoundError(f"no clean before_H checkpoint in {source}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, path, payload = candidates[0]
    return path, payload


def attach_progress_printer(solver: S.Solver, every: int, started: float) -> None:
    if every <= 0:
        return
    seen: dict[str, int] = {}

    def callback(which, progress):
        updates = int(progress.get("updates", 0) or 0)
        if updates <= 0 or updates % every != 0 or seen.get(which) == updates:
            return False
        seen[which] = updates
        trace = getattr(solver, "last_fit_trace", [])
        loss = trace[-1].get("loss") if trace else None
        loss_text = "-" if loss is None else f"{float(loss):.3e}"
        print(
            f"[fit step {solver.current_time_layer + 1:03d}] {which} "
            f"updates={updates}/{solver.a.max_inner} residual~{loss_text} "
            f"elapsed={time.perf_counter() - started:.1f}s",
            flush=True,
        )
        return False

    solver.on_inner_update = callback


def trace_wrapper(solver: S.Solver) -> dict[str, list[dict[str, Any]]]:
    original = solver.inner_train
    traces: dict[str, list[dict[str, Any]]] = {}

    def wrapped(field, target, which="shared"):
        record = original(field, target, which)
        traces[which] = copy.deepcopy(getattr(solver, "last_fit_trace", []))
        return record

    solver.inner_train = wrapped
    return traces


def row_cost(row: dict[str, Any]) -> dict[str, int]:
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    for key in ("fit_H", "fit_E"):
        fit = row.get(key) or {}
        total["adam"] += int(fit.get("n_updates", 0) or 0)
        total["closures"] += int(fit.get("n_closures", 0) or 0)
        total["lbfgs_steps"] += int(fit.get("n_lbfgs_steps", 0) or 0)
    return total


def trace_crossing(trace: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    for item in trace:
        loss = item.get("loss")
        if loss is not None and float(loss) <= threshold:
            return {"updates": int(item.get("updates", 0)), "loss": float(loss)}
    return None


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = (ROOT / args.source_run).resolve() if not Path(args.source_run).is_absolute() else Path(args.source_run)
    protocol = ROOT / args.protocol
    out = prepare_output(args.output_name)
    checkpoint_path, payload = select_clean_checkpoint(source)
    config = make_config(payload, out, args)
    solver = S.Solver(config, args.device)
    solver.load_state_payload(payload, diagnostic_only=True)
    ref = fdtd.PECCavity(side=solver.a.side, n=solver.a.n, dt=solver.a.dt)
    S._restore_reference(ref, payload["reference"])

    original_max_inner = int(solver.a.max_inner)
    original_lr = float(solver.a.lr)
    solver.a.max_inner = int(args.max_inner)
    if args.lr is not None:
        solver.a.lr = float(args.lr)
    solver.a.out_dir = str(out)
    solver.a.out = str(out / "summary.json")
    solver.a.device = args.device

    metadata = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "protocol": display(protocol),
        "protocol_sha256": sha256_file(protocol),
        "source_run": display(source),
        "source_checkpoint": display(checkpoint_path),
        "source_checkpoint_sha256": sha256_file(checkpoint_path),
        "source_failure_raw": display(source / "failure_raw_000036_attempt_1.pt"),
        "source_failure_raw_sha256": sha256_file(source / "failure_raw_000036_attempt_1.pt"),
        "original_max_inner": original_max_inner,
        "diagnostic_max_inner": int(args.max_inner),
        "original_lr": original_lr,
        "diagnostic_lr": float(solver.a.lr),
        "config": vars(solver.a).copy(),
        "source_hashes": source_hashes(ROOT),
        **S.formal_run_identity(solver.a),
    }
    recorder = RunRecorder(out, metadata, mode="new")
    metadata["source_snapshot_hashes"] = copy_source_snapshot(out)
    write_json(out / "manifest.json", metadata)

    started = time.perf_counter()
    traces = trace_wrapper(solver)
    attach_progress_printer(solver, int(args.fit_progress_every), started)
    waveform = fdtd.source_waveform(int(payload.get("requested_steps", 64)), solver.dt, solver.a.fmax, "hard")
    layer = int(solver.current_time_layer)
    source_cell = int(solver.n // 2)

    print(
        f"[SR-36E] replay layer={layer} physical_step={layer + 1} "
        f"from={display(checkpoint_path)} max_inner={solver.a.max_inner}",
        flush=True,
    )
    record = solver.step(float(waveform[layer]))
    if record.accepted:
        ref.step_e_source_h(src_value=float(waveform[layer]),
                            src_idx=(source_cell, source_cell, source_cell))
    row = S._json_safe(S._step_summary(solver, ref, record))
    row.update({
        "probe": "SR-36E-BUDGET",
        "source_run": display(source),
        "source_checkpoint": display(checkpoint_path),
        "original_max_inner": original_max_inner,
        "diagnostic_max_inner": int(args.max_inner),
        "original_lr": original_lr,
        "diagnostic_lr": float(solver.a.lr),
        "fit_traces": S._json_safe(copy.deepcopy(traces)),
        "row_cost": row_cost(row),
        "actual_wall_s": time.perf_counter() - started,
        "no_trajectory_unlock": True,
    })
    recorder.append(row)
    recorder.rolling_checkpoint(S._checkpoint_payload(
        solver, ref, requested_steps=int(payload.get("requested_steps", 64)),
        source_index=solver.current_time_layer))
    if not record.accepted:
        raw = getattr(solver, "last_failure_raw", None)
        recorder.failure_raw(raw if raw is not None else S._checkpoint_payload(
            solver, ref, requested_steps=int(payload.get("requested_steps", 64)),
            source_index=layer))
    else:
        recorder.snapshot(solver.accepted_steps, S._checkpoint_payload(
            solver, ref, requested_steps=int(payload.get("requested_steps", 64)),
            source_index=solver.current_time_layer))

    fit_e = row.get("fit_E") or {}
    trace_e = (row.get("fit_traces") or {}).get("E", [])
    status = "PASS" if record.accepted else "FAIL"
    summary = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "status": status,
        "scientific_result": "DIAGNOSTIC_PASS_STEP36" if record.accepted else "DIAGNOSTIC_FAIL_STEP36",
        "source_run": display(source),
        "source_checkpoint": display(checkpoint_path),
        "source_accepted_steps": int(payload.get("accepted_steps", -1)),
        "source_current_time_layer": int(payload.get("current_time_layer", -1)),
        "original_lr": original_lr,
        "diagnostic_lr": float(solver.a.lr),
        "diagnostic_max_inner": int(args.max_inner),
        "accepted_steps_after": int(solver.accepted_steps),
        "new_accepted_steps": int(solver.accepted_steps) - int(payload.get("accepted_steps", 0)),
        "new_adam_updates": row["row_cost"]["adam"],
        "new_closures": row["row_cost"]["closures"],
        "elapsed_s": time.perf_counter() - started,
        "step_row": row,
        "e_residual_ratio": fit_e.get("residual_ratio"),
        "e_updates": fit_e.get("n_updates"),
        "e_crosses_1e_minus_4": trace_crossing(trace_e, 1e-4),
        "e_crosses_1e_minus_5": trace_crossing(trace_e, 1e-5),
        "long_run_unlocked": False,
        "recovery_eligible": False,
        "interpretation": (
            "budget_sensitive_candidate_not_trajectory_validation"
            if record.accepted else
            "still_fails_under_registered_budget"
        ),
        "run_dir": display(out),
    }
    write_json(out / "summary.json", summary)
    lines = [
        "# SR-36E-BUDGET step-36 diagnostic",
        "",
        "This is a one-step diagnostic from the last clean SR-64 checkpoint, not a 64-step validation.",
        "",
        f"- Status: `{status}`; scientific_result: `{summary['scientific_result']}`",
        f"- Source checkpoint: `{summary['source_checkpoint']}`",
        f"- Source accepted steps: `{summary['source_accepted_steps']}`",
        f"- Original lr / diagnostic lr: `{summary['original_lr']}` / `{summary['diagnostic_lr']}`",
        f"- Diagnostic max_inner: `{summary['diagnostic_max_inner']}`",
        f"- Accepted steps after replay: `{summary['accepted_steps_after']}`",
        f"- New Adam updates: `{summary['new_adam_updates']}`",
        f"- Step-36 E residual: `{summary['e_residual_ratio']}`",
        f"- Step-36 E updates: `{summary['e_updates']}`",
        f"- E crosses 1e-4: `{summary['e_crosses_1e_minus_4']}`",
        f"- E crosses 1e-5: `{summary['e_crosses_1e_minus_5']}`",
        f"- Long run unlocked: `{summary['long_run_unlocked']}`",
        "",
        "The old SR-64 failure raw is preserved and is not continued as a formal trajectory.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "scientific_result": summary["scientific_result"],
        "new_accepted_steps": summary["new_accepted_steps"],
        "updates": summary["new_adam_updates"],
        "e_residual_ratio": summary["e_residual_ratio"],
        "output": str(out),
    }, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--source-run", default=display(DEFAULT_SOURCE))
    parser.add_argument("--max-inner", type=int, default=30000)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--fit-progress-every", type=int, default=500)
    parser.add_argument("--output-name", default=OUT_NAME)
    parser.add_argument("--protocol", default=display(PLAN))
    run(parser.parse_args())
