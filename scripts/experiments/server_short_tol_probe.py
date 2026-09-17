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


def copy_source_snapshot(out: Path, protocol_rel: str | None = None) -> dict[str, str | None]:
    source = out / "source"
    source.mkdir(exist_ok=True)
    copied = {}
    rels = [
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
    ]
    if protocol_rel and protocol_rel not in rels:
        rels.append(protocol_rel)
    for rel in rels:
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied[rel] = sha256_file(path)
    return copied


#: Every component the registered field gate claims to cover.  F02: the gate
#: started from ``component_pass = True`` and then iterated over whatever
#: components happened to be present, so an empty or three-component record
#: passed the component half of the gate outright.
REQUIRED_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
COMPONENT_NMAE_GATE = 0.01
Q_GATE = 0.05
FIXED_AMPLITUDE_GATE = 1e-3
#: Relative L2 of the whole source-outside Ez probe waveform, DUT vs reference.
SOURCE_OUTSIDE_REL_L2_GATE = 0.05


def _finite(value: Any) -> float | None:
    """A float that is present and finite, else None.  NaN never passes a gate."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def field_gate(row: dict[str, Any]) -> dict[str, Any]:
    """Endpoint field gate.

    Three things changed after the 20260917 review:
    absent components are INCOMPLETE instead of silently passing, a non-finite
    metric can no longer be read as "small enough", and the source-outside
    probes take part in the verdict instead of being copied into the result.
    """
    metrics = row.get("six_component_metrics") or {}
    components = metrics.get("components") or {}
    component_rows: dict[str, Any] = {}
    missing = [name for name in REQUIRED_COMPONENTS if name not in components]
    unexpected = sorted(set(components) - set(REQUIRED_COMPONENTS))
    component_pass = not missing and not unexpected
    for name in REQUIRED_COMPONENTS:
        item = components.get(name)
        if not isinstance(item, dict):
            component_rows[name] = {"pass": False, "weak_reference": None,
                                    "reason": "component_absent"}
            continue
        weak = bool(item.get("weak_reference"))
        if weak:
            absolute = _finite(item.get("absolute_mae"))
            declared = item.get("weak_absolute_pass")
            gate = _finite(item.get("weak_absolute_gate")) or 1e-5
            passed = bool(declared) and absolute is not None and absolute <= gate
            reason = f"weak_absolute_mae={item.get('absolute_mae')} gate={gate} declared={declared}"
        else:
            nmae = _finite(item.get("nmae"))
            passed = nmae is not None and nmae <= COMPONENT_NMAE_GATE
            reason = f"nmae={item.get('nmae')}"
        component_rows[name] = {"pass": passed, "weak_reference": weak, "reason": reason}
        component_pass = component_pass and passed
    q = _finite(metrics.get("global_weighted_relative_l2"))
    fixed = _finite(metrics.get("fixed_amplitude_error"))
    q_pass = q is not None and q <= Q_GATE
    fixed_pass = fixed is not None and fixed <= FIXED_AMPLITUDE_GATE
    probe = source_outside_probe_check(row.get("source_outside_probes"))
    complete = not missing and not unexpected and probe["complete"]
    status = "PASS" if (complete and component_pass and q_pass and fixed_pass and probe["pass"]) \
        else ("INCOMPLETE" if not complete else "FAIL")
    return {
        "pass": status == "PASS",
        "status": status,
        "complete": complete,
        "missing_components": missing,
        "unexpected_components": unexpected,
        "global_weighted_relative_l2": metrics.get("global_weighted_relative_l2"),
        "global_weighted_relative_l2_le_5pct": q_pass,
        "fixed_amplitude_error": metrics.get("fixed_amplitude_error"),
        "fixed_amplitude_error_le_1e_minus_3": fixed_pass,
        "component_pass": component_pass,
        "components": component_rows,
        "source_outside_probe_check": probe,
        "source_outside_probes": row.get("source_outside_probes"),
        "source_probe_Ez": row.get("source_probe_Ez"),
    }


def source_outside_probe_check(probes: Any) -> dict[str, Any]:
    """Score the registered source-outside probes instead of only copying them.

    F02: the probes existed in the record but never entered the verdict, so a
    gate could pass while the field away from the hard source disagreed with
    the reference.
    """
    if not isinstance(probes, list) or not probes:
        return {"complete": False, "pass": False, "reason": "no_source_outside_probes",
                "probe_count": 0}
    error_ss = reference_ss = 0.0
    worst = None
    for item in probes:
        if not isinstance(item, dict):
            return {"complete": False, "pass": False, "reason": "malformed_probe",
                    "probe_count": len(probes)}
        dut = _finite(item.get("dut_Ez"))
        ref = _finite(item.get("ref_Ez"))
        if dut is None or ref is None:
            return {"complete": False, "pass": False, "reason": "non_finite_probe",
                    "probe_count": len(probes)}
        error_ss += (dut - ref) ** 2
        reference_ss += ref * ref
        worst = max(worst if worst is not None else 0.0, abs(dut - ref))
    relative = float(np.sqrt(error_ss / reference_ss)) if reference_ss > 0 else None
    passed = relative is not None and relative <= SOURCE_OUTSIDE_REL_L2_GATE
    return {
        "complete": True,
        "pass": bool(passed),
        "probe_count": len(probes),
        "relative_l2": relative,
        "max_abs_error": worst,
        "reference_energy": reference_ss,
        "gate": SOURCE_OUTSIDE_REL_L2_GATE,
        "reason": "zero_reference_energy" if relative is None else "relative_l2",
    }


def window_field_gate(rows: list[dict[str, Any]], through_step: int) -> dict[str, Any]:
    """The whole-window gate the plan asks for, not just the endpoint.

    Endpoint metrics cannot see a trajectory that is good at step 64 and bad
    at step 40, and they cannot see the source-outside waveform at all.  This
    scores every accepted layer up to ``through_step`` and, separately, the
    full source-outside Ez waveform as one relative L2.
    """
    accepted = [row for row in rows
                if row.get("accepted") and int(row.get("accepted_steps") or 0) <= through_step]
    if not accepted:
        return {"status": "INCOMPLETE", "pass": False, "reason": "no_accepted_rows",
                "through_step": through_step, "rows_scored": 0}
    if int(accepted[-1].get("accepted_steps") or 0) != through_step:
        return {"status": "INCOMPLETE", "pass": False, "reason": "window_not_reached",
                "through_step": through_step, "rows_scored": len(accepted)}
    seen = sorted(int(row.get("accepted_steps") or 0) for row in accepted)
    if seen != list(range(1, through_step + 1)):
        return {"status": "INCOMPLETE", "pass": False, "reason": "window_has_gaps",
                "through_step": through_step, "rows_scored": len(accepted)}
    worst_q = worst_q_step = None
    worst_component: dict[str, Any] = {}
    incomplete_steps: list[int] = []
    error_ss = reference_ss = 0.0
    probe_steps = 0
    for row in accepted:
        step = int(row.get("accepted_steps") or 0)
        gate = field_gate(row)
        if not gate["complete"]:
            incomplete_steps.append(step)
        q = _finite((row.get("six_component_metrics") or {}).get("global_weighted_relative_l2"))
        if q is None:
            incomplete_steps.append(step)
        elif worst_q is None or q > worst_q:
            worst_q, worst_q_step = q, step
        for name, item in gate["components"].items():
            if not item["pass"] and name not in worst_component:
                worst_component[name] = {"step": step, "reason": item["reason"]}
        probes = row.get("source_outside_probes")
        if isinstance(probes, list) and probes:
            probe_steps += 1
            for entry in probes:
                dut = _finite((entry or {}).get("dut_Ez"))
                ref = _finite((entry or {}).get("ref_Ez"))
                if dut is None or ref is None:
                    incomplete_steps.append(step)
                    continue
                error_ss += (dut - ref) ** 2
                reference_ss += ref * ref
        else:
            incomplete_steps.append(step)
    waveform_relative = float(np.sqrt(error_ss / reference_ss)) if reference_ss > 0 else None
    incomplete = sorted(set(incomplete_steps))
    q_pass = worst_q is not None and worst_q <= Q_GATE
    component_pass = not worst_component
    waveform_pass = waveform_relative is not None and waveform_relative <= SOURCE_OUTSIDE_REL_L2_GATE
    if incomplete:
        status = "INCOMPLETE"
    elif q_pass and component_pass and waveform_pass:
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "status": status,
        "pass": status == "PASS",
        "through_step": through_step,
        "rows_scored": len(accepted),
        "incomplete_steps": incomplete,
        "worst_global_weighted_relative_l2": worst_q,
        "worst_global_weighted_relative_l2_step": worst_q_step,
        "worst_global_weighted_relative_l2_le_5pct": q_pass,
        "first_failing_component_step": worst_component,
        "component_pass_all_steps": component_pass,
        "source_outside_waveform_relative_l2": waveform_relative,
        "source_outside_waveform_pass": waveform_pass,
        "source_outside_waveform_steps": probe_steps,
        "gates": {"component_nmae": COMPONENT_NMAE_GATE, "global_relative_l2": Q_GATE,
                  "source_outside_relative_l2": SOURCE_OUTSIDE_REL_L2_GATE},
    }


def recovery_eligible(recorder: Any, solver: Any, status: str, stop: dict[str, Any] | None) -> dict[str, Any]:
    """Recovery eligibility from verified state, not from "we stopped nicely".

    A resumable claim needs a committed checkpoint that actually loads, a
    non-terminal fit state, and a stop that was a resource limit rather than a
    fit failure.  Each condition is reported so a reader can see WHICH one
    failed instead of a bare boolean.
    """
    reasons: dict[str, Any] = {
        "status_is_resource_limit": status == "RESOURCE_LIMIT",
        "stopped_without_failed_row": stop is not None and not stop.get("row"),
    }
    try:
        payload = recorder.load_rolling_checkpoint()
        reasons["committed_checkpoint_loads"] = True
        reasons["checkpoint_sequence_id"] = payload.get("last_committed_sequence_id")
    except Exception as error:                                  # noqa: BLE001
        reasons["committed_checkpoint_loads"] = False
        reasons["checkpoint_error"] = f"{type(error).__name__}: {error}"
    progress = getattr(solver, "fit_progress", {}) or {}
    terminal = [which for which, item in progress.items()
                if not bool((item or {}).get("resumable", True))
                or (item or {}).get("stop_reason") in S.TERMINAL_FIT_REASONS]
    reasons["terminal_fit_roles"] = terminal
    reasons["eligible"] = bool(
        reasons["status_is_resource_limit"] and reasons["stopped_without_failed_row"]
        and reasons.get("committed_checkpoint_loads") and not terminal)
    return reasons


def fmt_progress(value: Any, precision: int = 3) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{precision}e}"
    return str(value)


def progress_line(row: dict[str, Any], requested_steps: int, total_cost: dict[str, int], started: float) -> str:
    fit_h = row.get("fit_H") or {}
    fit_e = row.get("fit_E") or {}
    metrics = row.get("six_component_metrics") or {}
    q = metrics.get("global_weighted_relative_l2")
    accepted = bool(row.get("accepted"))
    shown_step = int(row.get("accepted_steps") or 0)
    if not accepted:
        shown_step += 1
    status = "OK" if accepted else f"FAIL:{row.get('phase')}:{row.get('reason')}"
    return (
        f"[step {shown_step:03d}/{requested_steps:03d}] {status} | "
        f"H R={fmt_progress(fit_h.get('residual_ratio'))} u={fit_h.get('n_updates')} | "
        f"E R={fmt_progress(fit_e.get('residual_ratio'))} u={fit_e.get('n_updates')} | "
        f"Q={fmt_progress(q)} | total_adam={total_cost.get('adam')} | "
        f"elapsed={time.perf_counter() - started:.1f}s"
    )


def make_config(out: Path, args: argparse.Namespace, steps: int) -> argparse.Namespace:
    init = getattr(args, "init", None) or display(MASTER)
    return argparse.Namespace(
        config="",
        steps=steps,
        n=31,
        side=0.05,
        dt=3.075e-12,
        init=init,
        tol=float(args.tol),
        tol_mode="rel",
        max_inner=int(args.per_fit_cap),
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


def budget_wrapper(solver: S.Solver, rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    original = solver.inner_train
    state: dict[str, Any] = {"caps": {}, "resource_limited": False, "events": []}

    def wrapped(field, target, which="shared"):
        before = sum_cost(rows)
        if which == "E" and getattr(solver, "pending_fit_H", None) is not None:
            fit = solver.pending_fit_H
            before["adam"] += int(fit.n_updates or 0)
            before["closures"] += int(fit.n_closures or 0)
            before["lbfgs_steps"] += int(fit.n_lbfgs_steps or 0)
        remaining = max(0, int(args.overall_adam_cap) - before["adam"])
        cap = min(int(args.per_fit_cap), remaining)
        prior = solver.a.max_inner
        solver.a.max_inner = cap
        info = {"which": which, "time_layer": int(solver.current_time_layer),
                "cost_before": before, "cap_adam": int(cap),
                "resource_cap_limited": cap < int(args.per_fit_cap)}
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
        "protocol": args.protocol,
        "protocol_sha256": sha256_file(ROOT / args.protocol),
        "config": vars(config).copy(),
        "master": display(MASTER),
        "master_sha256": sha256_file(MASTER),
        "source_hashes": source_hashes(ROOT),
        **S.formal_run_identity(config),
    }
    recorder = RunRecorder(out, metadata, mode="new")
    metadata["source_snapshot_hashes"] = copy_source_snapshot(out, args.protocol)
    write_json(out / "manifest.json", S._json_safe(metadata))
    rows: list[dict[str, Any]] = []
    traces = trace_wrapper(solver)
    budget_state = budget_wrapper(solver, rows, args)
    waveform = fdtd.source_waveform(requested_steps, solver.dt, config.fmax, "hard")
    source_cell = config.n // 2
    started = time.perf_counter()
    attach_progress_printer(solver, int(args.fit_progress_every), started)
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
                "init": getattr(args, "init", None) or display(MASTER),
                "tol": config.tol,
                "lr": config.lr,
                "reset_opt_each_step": config.reset_opt_each_step,
                "target_steps": args.target_steps,
                "conditional_target_steps": requested_steps,
                "adam_cap": int(args.overall_adam_cap),
                "per_fit_cap": int(args.per_fit_cap),
                "micro_gate_steps": int(args.micro_gate_steps),
            },
            "fit_traces": S._json_safe(copy.deepcopy(traces)),
            "budget_caps": S._json_safe(copy.deepcopy(budget_state.get("caps", {}))),
            "actual_wall_s": time.perf_counter() - started,
        })
        row["row_cost"] = row_cost(row)
        recorder.append(row)
        rows.append(row)
        print(progress_line(row, requested_steps, sum_cost(rows), started), flush=True)
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
        if cost["adam"] >= int(args.overall_adam_cap):
            stop = {"reason": "RESOURCE_LIMIT", "detail": "adam_cap_exhausted_after_accepted_step"}
            break
    accepted_rows = [row for row in rows if row.get("accepted")]
    last = accepted_rows[-1] if accepted_rows else None
    if last and gate64 is None and int(last.get("accepted_steps", 0)) >= 64:
        gate64 = field_gate(last)
    if last and int(last.get("accepted_steps", 0)) >= 128 and gate128 is None:
        gate128 = field_gate(last)
    micro_gate: dict[str, Any] | None = None
    if last and int(args.micro_gate_steps) > 0 and int(last.get("accepted_steps", 0)) >= int(args.micro_gate_steps):
        micro_gate = field_gate(last)
    budget = sum_cost(rows)
    # The endpoint gate is one snapshot.  The registered protocol asks for the
    # whole active window plus the source-outside waveform, so score that too
    # and let a scientific PASS require BOTH.  A window that is not complete
    # reports INCOMPLETE and never a PASS.
    def verdict(label: str, window_step: int, endpoint: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
        window = window_field_gate(rows, window_step)
        if endpoint is None:
            return "FAIL" if window["status"] == "FAIL" else "INCOMPLETE", window
        if endpoint["status"] == "INCOMPLETE" or window["status"] == "INCOMPLETE":
            return "INCOMPLETE", window
        return (label if (endpoint["pass"] and window["pass"]) else "FAIL"), window

    if int(args.micro_gate_steps) > 0:
        reached_micro = int(solver.accepted_steps) >= int(args.micro_gate_steps)
        status = "PASS" if reached_micro else ("RESOURCE_LIMIT" if (stop or {}).get("reason") == "RESOURCE_LIMIT" else "FAIL")
        scientific, window_gate = verdict("PASS_MICRO", int(args.micro_gate_steps), micro_gate)
    elif int(requested_steps) >= 128:
        reached128 = int(solver.accepted_steps) >= 128
        status = "PASS" if reached128 else ("RESOURCE_LIMIT" if (stop or {}).get("reason") == "RESOURCE_LIMIT" else "FAIL")
        scientific, window_gate = verdict("PASS_128", 128, gate128)
    else:
        reached64 = int(solver.accepted_steps) >= 64
        status = "PASS" if reached64 else ("RESOURCE_LIMIT" if (stop or {}).get("reason") == "RESOURCE_LIMIT" else "FAIL")
        scientific, window_gate = verdict("PASS_64", 64, gate64)
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
        "field_gate_micro": micro_gate,
        "field_gate_window": window_gate,
        "last_accepted_step": last,
        "recovery_eligible": recovery_eligible(recorder, solver, status, stop),
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
        f"- Micro-step field gate: `{None if micro_gate is None else micro_gate['status']}`",
        f"- 64-step field gate: `{None if gate64 is None else gate64['status']}`",
        f"- Whole-window field gate: `{window_gate['status']}` "
        f"(worst Q `{window_gate.get('worst_global_weighted_relative_l2')}`, "
        f"source-outside waveform relL2 `{window_gate.get('source_outside_waveform_relative_l2')}`)",
        f"- Recovery eligible: `{summary['recovery_eligible']['eligible']}` "
        f"({S._json_safe(summary['recovery_eligible'])})",
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
    parser.add_argument("--init", default=display(MASTER))
    parser.add_argument("--continue-to-128-if-pass64", action="store_true")
    parser.add_argument("--per-fit-cap", type=int, default=PER_FIT_CAP)
    parser.add_argument("--overall-adam-cap", type=int, default=ADAM_CAP)
    parser.add_argument("--micro-gate-steps", type=int, default=0)
    parser.add_argument("--protocol", default=display(PLAN))
    parser.add_argument("--fit-progress-every", type=int, default=0)
    run(parser.parse_args())
