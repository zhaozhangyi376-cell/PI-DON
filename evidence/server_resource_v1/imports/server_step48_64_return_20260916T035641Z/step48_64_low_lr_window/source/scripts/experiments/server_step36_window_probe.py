"""Low-lr local continuation from SR-64's last clean checkpoint."""
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
PLAN = ROOT / "docs/plans/2026-09-16-step36-window-low-lr-protocol.md"
DEFAULT_SOURCE = BASE / "strict64_probe"
OUT_NAME = "step36_48_low_lr_window"
SCHEMA = "pidon-server-step36-window-low-lr-v1"


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
        "scripts/experiments/server_step36_window_probe.py",
        "scripts/experiments/server_step36e_budget_probe.py",
        "scripts/experiments/server_short_tol_probe.py",
        "src/pidon/pidon_solve.py",
        "src/pidon/pidon_contract.py",
        "src/pidon/pidon_recording.py",
        "src/pidon/fdtd.py",
        "src/pidon/dco.py",
        "docs/plans/2026-09-16-step36-window-low-lr-protocol.md",
        "tools/server_step36_window_queue.py",
        "project_paths.py",
    ):
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied[rel] = sha256_file(path)
    return copied


def load_payload(path: Path) -> dict[str, Any]:
    return torch.load(path, map_location="cpu", weights_only=False)


def select_clean_checkpoint(source: Path) -> tuple[Path, dict[str, Any]]:
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for name in ("checkpoint_A.pt", "checkpoint_B.pt"):
        path = source / name
        if not path.is_file():
            continue
        payload = load_payload(path)
        if payload.get("phase") == "before_H":
            candidates.append((int(payload.get("accepted_steps", -1)), path, payload))
    if not candidates:
        raise FileNotFoundError(f"no clean before_H checkpoint in {source}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, path, payload = candidates[0]
    return path, payload


def make_config(payload: dict[str, Any], out: Path, args: argparse.Namespace) -> argparse.Namespace:
    saved = dict(payload["frozen_config"])
    saved.update({
        "config": "",
        "steps": int(args.target_accepted_steps),
        "out_dir": str(out),
        "resume": "",
        "checkpoint_every": 1,
        "device": args.device,
        "calib": [],
        "calib_iters": [],
        "out": str(out / "summary.json"),
    })
    return argparse.Namespace(**saved)


def trace_wrapper(solver: S.Solver) -> dict[str, list[dict[str, Any]]]:
    original = solver.inner_train
    traces: dict[str, list[dict[str, Any]]] = {}

    def wrapped(field, target, which="shared"):
        record = original(field, target, which)
        traces[which] = copy.deepcopy(getattr(solver, "last_fit_trace", []))
        return record

    solver.inner_train = wrapped
    return traces


def attach_progress_printer(solver: S.Solver, every: int, started: float) -> None:
    if every <= 0:
        return
    seen: dict[str, int] = {}

    def callback(which, progress):
        updates = int(progress.get("updates", 0) or 0)
        key = f"{solver.current_time_layer}:{which}:{updates}"
        if updates <= 0 or updates % every != 0 or seen.get(key):
            return False
        seen[key] = 1
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


def row_cost(row: dict[str, Any]) -> dict[str, int]:
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    for key in ("fit_H", "fit_E"):
        fit = row.get(key) or {}
        total["adam"] += int(fit.get("n_updates", 0) or 0)
        total["closures"] += int(fit.get("n_closures", 0) or 0)
        total["lbfgs_steps"] += int(fit.get("n_lbfgs_steps", 0) or 0)
    return total


def sum_cost(rows: list[dict[str, Any]]) -> dict[str, int]:
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    for row in rows:
        cost = row_cost(row)
        for key in total:
            total[key] += cost[key]
    return total


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3e}"
    return str(value)


def progress_line(row: dict[str, Any], target: int, total: dict[str, int], started: float) -> str:
    fit_h = row.get("fit_H") or {}
    fit_e = row.get("fit_E") or {}
    metrics = row.get("six_component_metrics") or {}
    q = metrics.get("global_weighted_relative_l2")
    status = "OK" if row.get("accepted") else f"FAIL:{row.get('phase')}:{row.get('reason')}"
    shown = int(row.get("accepted_steps") or 0) if row.get("accepted") else int(row.get("step") or 0) + 1
    return (
        f"[step {shown:03d}/{target:03d}] {status} | "
        f"H R={fmt(fit_h.get('residual_ratio'))} u={fit_h.get('n_updates')} | "
        f"E R={fmt(fit_e.get('residual_ratio'))} u={fit_e.get('n_updates')} | "
        f"Q={fmt(q)} | total_adam={total.get('adam')} | "
        f"elapsed={time.perf_counter() - started:.1f}s"
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = (ROOT / args.source_run).resolve() if not Path(args.source_run).is_absolute() else Path(args.source_run)
    out = prepare_output(args.output_name)
    checkpoint_path, payload = select_clean_checkpoint(source)
    config = make_config(payload, out, args)
    solver = S.Solver(config, args.device)
    solver.load_state_payload(payload, diagnostic_only=True)
    ref = fdtd.PECCavity(side=solver.a.side, n=solver.a.n, dt=solver.a.dt)
    S._restore_reference(ref, payload["reference"])

    original_lr = float(solver.a.lr)
    original_max_inner = int(solver.a.max_inner)
    solver.a.lr = float(args.lr)
    solver.a.max_inner = int(args.max_inner)
    solver.a.out_dir = str(out)
    solver.a.out = str(out / "summary.json")
    solver.a.device = args.device

    metadata = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "protocol": display(PLAN),
        "protocol_sha256": sha256_file(PLAN),
        "source_run": display(source),
        "source_checkpoint": display(checkpoint_path),
        "source_checkpoint_sha256": sha256_file(checkpoint_path),
        "original_lr": original_lr,
        "diagnostic_lr": float(solver.a.lr),
        "original_max_inner": original_max_inner,
        "diagnostic_max_inner": int(solver.a.max_inner),
        "target_accepted_steps": int(args.target_accepted_steps),
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
    waveform = fdtd.source_waveform(int(args.target_accepted_steps), solver.dt, solver.a.fmax, "hard")
    source_cell = int(solver.n // 2)
    rows: list[dict[str, Any]] = []
    stop: dict[str, Any] | None = None
    source_accepted = int(payload.get("accepted_steps", -1))
    print(
        f"[SR-36-48] start accepted={source_accepted} target={args.target_accepted_steps} "
        f"lr={solver.a.lr} max_inner={solver.a.max_inner}",
        flush=True,
    )
    while int(solver.accepted_steps) < int(args.target_accepted_steps):
        layer = int(solver.current_time_layer)
        record = solver.step(float(waveform[layer]))
        if record.accepted:
            ref.step_e_source_h(src_value=float(waveform[layer]),
                                src_idx=(source_cell, source_cell, source_cell))
        row = S._json_safe(S._step_summary(solver, ref, record))
        row.update({
            "probe": "SR-36-48-LOWLR",
            "source_run": display(source),
            "source_checkpoint": display(checkpoint_path),
            "source_accepted_steps": source_accepted,
            "target_accepted_steps": int(args.target_accepted_steps),
            "original_lr": original_lr,
            "diagnostic_lr": float(solver.a.lr),
            "diagnostic_max_inner": int(solver.a.max_inner),
            "fit_traces": S._json_safe(copy.deepcopy(traces)),
            "row_cost": row_cost(row),
            "actual_wall_s": time.perf_counter() - started,
            "no_trajectory_unlock": True,
        })
        recorder.append(row)
        rows.append(row)
        total = sum_cost(rows)
        print(progress_line(row, int(args.target_accepted_steps), total, started), flush=True)
        recorder.rolling_checkpoint(S._checkpoint_payload(
            solver, ref, requested_steps=int(args.target_accepted_steps),
            source_index=solver.current_time_layer))
        if record.accepted and int(solver.accepted_steps) in {36, 40, 44, 48}:
            recorder.snapshot(solver.accepted_steps, S._checkpoint_payload(
                solver, ref, requested_steps=int(args.target_accepted_steps),
                source_index=solver.current_time_layer))
        if not record.accepted:
            stop = {"reason": "FIT_FAIL", "row": row}
            raw = getattr(solver, "last_failure_raw", None)
            recorder.failure_raw(raw if raw is not None else S._checkpoint_payload(
                solver, ref, requested_steps=int(args.target_accepted_steps),
                source_index=layer))
            break
    accepted_rows = [row for row in rows if row.get("accepted")]
    last = accepted_rows[-1] if accepted_rows else None
    cost = sum_cost(rows)
    passed = int(solver.accepted_steps) >= int(args.target_accepted_steps)
    status = "PASS" if passed else "FAIL"
    summary = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "status": status,
        "scientific_result": "DIAGNOSTIC_PASS_WINDOW" if passed else "DIAGNOSTIC_FAIL_WINDOW",
        "source_run": display(source),
        "source_checkpoint": display(checkpoint_path),
        "source_accepted_steps": source_accepted,
        "accepted_steps_after": int(solver.accepted_steps),
        "new_accepted_steps": int(solver.accepted_steps) - source_accepted,
        "target_accepted_steps": int(args.target_accepted_steps),
        "original_lr": original_lr,
        "diagnostic_lr": float(solver.a.lr),
        "diagnostic_max_inner": int(solver.a.max_inner),
        "new_adam_updates": cost["adam"],
        "new_closures": cost["closures"],
        "elapsed_s": time.perf_counter() - started,
        "stop": stop,
        "last_accepted_step": last,
        "long_run_unlocked": False,
        "recovery_eligible": False,
        "interpretation": "local_window_diagnostic_not_formal_gate",
        "run_dir": display(out),
    }
    write_json(out / "summary.json", summary)
    lines = [
        "# SR-36-48-LOWLR local window",
        "",
        "This is a local continuation diagnostic from SR-64's clean step-35 checkpoint, not a paper-level gate.",
        "",
        f"- Status: `{status}`; scientific_result: `{summary['scientific_result']}`",
        f"- Source accepted steps: `{source_accepted}`",
        f"- Accepted steps after: `{summary['accepted_steps_after']}`",
        f"- New accepted steps: `{summary['new_accepted_steps']}`",
        f"- lr: `{summary['diagnostic_lr']}`; max_inner: `{summary['diagnostic_max_inner']}`",
        f"- Adam updates: `{summary['new_adam_updates']}`; closures: `{summary['new_closures']}`",
        f"- Long run unlocked: `{summary['long_run_unlocked']}`",
    ]
    if last:
        fit_h = last.get("fit_H") or {}
        fit_e = last.get("fit_E") or {}
        metrics = last.get("six_component_metrics") or {}
        lines += [
            "",
            "## Last accepted step",
            "",
            f"- accepted_steps: `{last.get('accepted_steps')}`",
            f"- H R: `{fit_h.get('residual_ratio')}`; updates: `{fit_h.get('n_updates')}`",
            f"- E R: `{fit_e.get('residual_ratio')}`; updates: `{fit_e.get('n_updates')}`",
            f"- Q/global relL2: `{metrics.get('global_weighted_relative_l2')}`",
        ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "scientific_result": summary["scientific_result"],
        "accepted_steps_after": summary["accepted_steps_after"],
        "new_accepted_steps": summary["new_accepted_steps"],
        "updates": summary["new_adam_updates"],
        "output": str(out),
    }, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--source-run", default=display(DEFAULT_SOURCE))
    parser.add_argument("--target-accepted-steps", type=int, default=48)
    parser.add_argument("--max-inner", type=int, default=60000)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--fit-progress-every", type=int, default=500)
    parser.add_argument("--output-name", default=OUT_NAME)
    run(parser.parse_args())

