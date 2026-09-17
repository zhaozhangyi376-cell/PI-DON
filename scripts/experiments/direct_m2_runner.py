"""M2 bounded 128-step direct mechanism runner.

Runs one pre-registered arm at a time under the direct-mechanism budget:
A-R, A-P, then conditionally B-R/B-P.  This module is a thin budget and
reporting layer around pidon_solve.Solver; it does not change the DCO, target,
field update, or metric definitions.
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

from project_paths import PROJECT_DIR, configure, resolve_legacy
configure()

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"
RUNS = OUT / "runs"
PLAN = ROOT / "docs" / "plans" / "2026-09-14-direct-mechanism-plan.md"
MASTER = ROOT / resolve_legacy("assets/models/dco_lr1e3_300.pt")
SCHEMA = "direct-mechanism-m2-v1"
ARM_ADAM_CAP = 150_000
ARM_CLOSURE_CAP = 60_000
GLOBAL_ADAM_CAP = 1_000_000
GLOBAL_CLOSURE_CAP = 300_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(data, path)


def manifest_path() -> Path:
    return OUT / "manifest.json"


def load_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.exists():
        raise FileNotFoundError("direct mechanism manifest missing; run M0 first")
    manifest = read_json(path)
    if manifest.get("schema") != "pidon-direct-mechanism-v1":
        raise ValueError("unexpected direct mechanism manifest schema")
    if manifest.get("plan_sha256") != sha256_file(PLAN):
        raise ValueError("direct mechanism plan hash changed after manifest creation")
    if manifest.get("master_sha256") != sha256_file(MASTER):
        raise ValueError("master checkpoint hash changed after manifest creation")
    return manifest


def arm_rule(arm: str) -> dict[str, Any]:
    if arm not in {"A-R", "A-P", "B-R", "B-P"}:
        raise ValueError(arm)
    rule = arm.split("-", 1)[0]
    init_kind = arm.split("-", 1)[1]
    if rule == "A":
        max_inner, closures, reset = 3000, 1200, False
    else:
        max_inner, closures, reset = 3000, 0, True
    return {
        "arm": arm,
        "rule": rule,
        "init_kind": init_kind,
        "init": "random" if init_kind == "R" else MASTER.relative_to(ROOT).as_posix(),
        "seed": 20260914,
        "target_steps": 128,
        "tol": 1e-4,
        "lr": 3e-4,
        "per_fit_adam_cap": max_inner,
        "per_fit_closure_cap": closures,
        "reset_opt_each_step": reset,
        "lbfgs_lr": 1.0,
        "lbfgs_history": 10,
        "purpose": "strict_short_128",
    }


def common_config(spec: dict[str, Any], out_dir: Path, device: str) -> argparse.Namespace:
    return argparse.Namespace(
        config="",
        steps=int(spec["target_steps"]),
        n=31,
        side=0.05,
        dt=3.075e-12,
        init=spec["init"],
        tol=float(spec["tol"]),
        tol_mode="rel",
        max_inner=int(spec["per_fit_adam_cap"]),
        lr=float(spec["lr"]),
        head_lstsq_once=False,
        head_rcond=1e-12,
        levels=4,
        base=32,
        coords="cellsize",
        norm="rms",
        separate_nets=True,
        reset_opt_each_step=bool(spec["reset_opt_each_step"]),
        grad_clip=0.0,
        h_scale=1.0,
        component_rel=False,
        h_output_scale=1.0,
        h_shift=True,
        strict_stop=True,
        inner_time_budget_s=0.0,
        lbfgs_closures=int(spec["per_fit_closure_cap"]),
        lbfgs_lr=float(spec["lbfgs_lr"]),
        lbfgs_history=int(spec["lbfgs_history"]),
        lbfgs_time_budget_s=0.0,
        source_mode="hard",
        torch_dtype="float32",
        out_dir=str(out_dir),
        resume="",
        checkpoint_every=1,
        seed=int(spec["seed"]),
        device=device,
        fmax=15e9,
        calib=[],
        calib_iters=[],
        out=str(out_dir / "summary.json"),
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


def jsonl_cost(run_dir: Path) -> dict[str, int] | None:
    """Recover a lower bound on an arm's cost from its committed step log.

    An arm that died before writing summary.json still has every committed
    row on disk.  Reading them is what makes a missing summary an UNKNOWN
    tail instead of a zero.
    """
    steps_path = run_dir / "steps.jsonl"
    if not steps_path.is_file():
        return None
    rows: list[dict[str, Any]] = []
    try:
        for line in steps_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return sum_cost(rows)


def existing_m2_cost(exclude_arm: str | None = None) -> dict[str, int]:
    """Cost already spent by the other arms, with an explicit unknown tail.

    F26: this used to walk only well-formed summaries and ``continue`` past
    everything else, so an arm whose summary was missing or unparsable counted
    as ZERO -- and the next arm then started against a budget that had already
    been spent.  A committed steps.jsonl is now read as a lower bound, and an
    arm whose cost cannot be established at all is listed under
    ``unknown_arms``.  Callers must treat a non-empty ``unknown_arms`` as "the
    remaining budget is not known", never as "nothing was spent".
    """
    total = {"adam": 0, "closures": 0, "lbfgs_steps": 0}
    unknown: list[str] = []
    lower_bound_only: list[str] = []
    seen: set[str] = set()
    for run_dir in sorted(path for path in RUNS.glob("*") if path.is_dir()):
        if exclude_arm and run_dir.name == exclude_arm.replace("-", "_"):
            continue
        seen.add(run_dir.name)
        summary_path = run_dir / "summary.json"
        summary = None
        if summary_path.is_file():
            try:
                candidate = read_json(summary_path)
            except Exception:                                     # noqa: BLE001
                candidate = None
            if isinstance(candidate, dict) and candidate.get("schema") == "direct-mechanism-m2-arm-summary-v1":
                summary = candidate
        if summary is not None:
            budget = summary.get("budget", {})
            total["adam"] += int(budget.get("adam", 0) or 0)
            total["closures"] += int(budget.get("closures", 0) or 0)
            total["lbfgs_steps"] += int(budget.get("lbfgs_steps", 0) or 0)
            continue
        recovered = jsonl_cost(run_dir)
        if recovered is None:
            unknown.append(run_dir.name)
            continue
        lower_bound_only.append(run_dir.name)
        for key in total:
            total[key] += recovered[key]
    total["unknown_arms"] = unknown
    total["lower_bound_arms"] = lower_bound_only
    total["is_lower_bound"] = bool(unknown or lower_bound_only)
    total["cost_accounting_status"] = "UNKNOWN" if unknown else (
        "LOWER_BOUND" if lower_bound_only else "COMPLETE")
    return total


def classify_stop(stop: dict[str, Any] | None, accepted_steps: int, target_steps: int) -> str:
    """Numerical progress and engineering delivery are two different verdicts.

    F25: reaching the target step count was tested FIRST, so an arm whose final
    checkpoint write raised was still classified PASS.  Physics that advanced
    but could not be persisted is not a deliverable result -- an exception
    outranks the step count.
    """
    if stop and stop.get("reason") == "EXCEPTION":
        return "EXCEPTION"
    if accepted_steps >= target_steps:
        if stop and stop.get("reason") not in (None, "TARGET_REACHED"):
            return "INCOMPLETE"
        return "PASS"
    if not stop:
        return "INCOMPLETE"
    if stop.get("reason") == "RESOURCE_LIMIT":
        return "RESOURCE_LIMIT"
    if stop.get("reason") == "FIT_FAIL":
        return "FAIL"
    return "INCOMPLETE"


def trace_wrapper(solver: S.Solver) -> dict[str, list[dict[str, Any]]]:
    original = solver.inner_train
    traces: dict[str, list[dict[str, Any]]] = {}

    def wrapped(field, target, which="shared"):
        record = original(field, target, which)
        traces[which] = copy.deepcopy(getattr(solver, "last_fit_trace", []))
        return record

    solver.inner_train = wrapped
    return traces


def budget_wrapper(solver: S.Solver, rows: list[dict[str, Any]], spec: dict[str, Any],
                   arm: str, global_base: dict[str, int]) -> dict[str, Any]:
    original = solver.inner_train
    state: dict[str, Any] = {"caps": {}, "resource_limited": False, "events": []}

    def consumed_before(which: str) -> dict[str, int]:
        cost = sum_cost(rows)
        if which == "E" and getattr(solver, "pending_fit_H", None) is not None:
            cost["adam"] += int(solver.pending_fit_H.n_updates or 0)
            cost["closures"] += int(solver.pending_fit_H.n_closures or 0)
            cost["lbfgs_steps"] += int(solver.pending_fit_H.n_lbfgs_steps or 0)
        return cost

    def wrapped(field, target, which="shared"):
        prior_max_inner = solver.a.max_inner
        prior_closures = solver.a.lbfgs_closures
        cost = consumed_before(which)
        arm_remaining_adam = ARM_ADAM_CAP - cost["adam"]
        arm_remaining_closure = ARM_CLOSURE_CAP - cost["closures"]
        global_remaining_adam = GLOBAL_ADAM_CAP - global_base["adam"] - cost["adam"]
        global_remaining_closure = GLOBAL_CLOSURE_CAP - global_base["closures"] - cost["closures"]
        cap_adam = max(0, min(int(spec["per_fit_adam_cap"]), arm_remaining_adam, global_remaining_adam))
        cap_closure = max(0, min(int(spec["per_fit_closure_cap"]), arm_remaining_closure, global_remaining_closure))
        cap_info = {
            "which": which,
            "time_layer": int(solver.current_time_layer),
            "arm_cost_before": copy.deepcopy(cost),
            "global_cost_before": copy.deepcopy(global_base),
            "cap_adam": int(cap_adam),
            "cap_closures": int(cap_closure),
            "resource_cap_limited": (
                cap_adam < int(spec["per_fit_adam_cap"]) or
                cap_closure < int(spec["per_fit_closure_cap"])
            ),
        }
        state["caps"][which] = cap_info
        solver.a.max_inner = int(cap_adam)
        solver.a.lbfgs_closures = int(cap_closure)
        try:
            record = original(field, target, which)
        finally:
            solver.a.max_inner = prior_max_inner
            solver.a.lbfgs_closures = prior_closures
        if cap_info["resource_cap_limited"] and not record.passed:
            state["resource_limited"] = True
            state["events"].append({**cap_info, "stop_reason": record.stop_reason})
        return record

    solver.inner_train = wrapped
    return state


def run_arm(arm: str, action_id: str, device: str) -> dict[str, Any]:
    manifest = load_manifest()
    spec = arm_rule(arm)
    RUNS.mkdir(parents=True, exist_ok=True)
    out_dir = RUNS / arm.replace("-", "_")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"arm output already exists: {display_path(out_dir)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    config = common_config(spec, out_dir, device)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    global_base = existing_m2_cost(exclude_arm=arm)
    # F26: never start a new arm against a budget whose spent total is only a
    # lower bound.  An unresolved arm has to be audited or explicitly written
    # off before the remaining allowance means anything.
    if global_base.get("unknown_arms"):
        raise SystemExit(
            "拒绝开训：以下臂的成本无法确定，剩余预算是 UNKNOWN 而不是零："
            f"{global_base['unknown_arms']}。请先核对这些运行的 steps.jsonl/行动日志，"
            "或登记独立新实验，不要用重算出的“未消耗”重新领取总预算。")
    if global_base.get("lower_bound_arms"):
        print("  警告：以下臂只能由 steps.jsonl 复原成本下界，总预算按下界计算："
              f"{global_base['lower_bound_arms']}", flush=True)
    solver = S.Solver(config, device)
    ref = fdtd.PECCavity(side=config.side, n=config.n, dt=config.dt)
    run_id = hashlib.sha256(f"{manifest['experiment_id']}|{SCHEMA}|{arm}".encode()).hexdigest()[:24]
    identity = S.formal_run_identity(config, run_id=run_id)
    metadata = {
        "schema": "direct-mechanism-m2-run-v1",
        "arm": arm,
        "action_id": action_id,
        "config": vars(config).copy(),
        "arm_spec": spec,
        "manifest_sha256": sha256_file(manifest_path()),
        "created_at_utc": utc_now(),
        **identity,
    }
    recorder = RunRecorder(out_dir, metadata, mode="new")
    rows: list[dict[str, Any]] = []
    traces = trace_wrapper(solver)
    budget_state = budget_wrapper(solver, rows, spec, arm, global_base)

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
            row["arm"] = arm
            row["arm_spec"] = spec
            row["fit_traces"] = S._json_safe(copy.deepcopy(traces))
            row["budget_caps"] = S._json_safe(copy.deepcopy(budget_state.get("caps", {})))
            row["actual_wall_s"] = time.perf_counter() - started
            row["row_cost"] = row_cost(row)
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
            cost = sum_cost(rows)
            if cost["adam"] >= ARM_ADAM_CAP or cost["closures"] >= ARM_CLOSURE_CAP:
                stop = {"reason": "RESOURCE_LIMIT", "detail": "arm budget exhausted after accepted step"}
                break
            if global_base["adam"] + cost["adam"] >= GLOBAL_ADAM_CAP or global_base["closures"] + cost["closures"] >= GLOBAL_CLOSURE_CAP:
                stop = {"reason": "RESOURCE_LIMIT", "detail": "global budget exhausted after accepted step"}
                break
    except Exception as exc:
        stop = {"reason": "EXCEPTION", "type": type(exc).__name__, "message": str(exc)[:500]}

    # The rolling two-slot checkpoint and milestone/failure artifacts above are
    # the registered recovery evidence.  Avoid extra latest/previous/commit
    # copies here because LBFGS optimizer state can make each file ~1 GiB.
    budget = sum_cost(rows)
    accepted_rows = [row for row in rows if row.get("accepted")]
    final_accepted = accepted_rows[-1] if accepted_rows else None
    stop_row = (stop or {}).get("row") if isinstance(stop, dict) else None
    probes = []
    for row in accepted_rows:
        probes.append({
            "step": row.get("step"),
            "source_probe_Ez": row.get("source_probe_Ez"),
            "source_outside_probes": row.get("source_outside_probes"),
        })
    status = classify_stop(stop, solver.accepted_steps, config.steps)
    summary = {
        "schema": "direct-mechanism-m2-arm-summary-v1",
        "arm": arm,
        "action_id": action_id,
        "status": status,
        "scientific_status": "PASS" if status == "PASS" else status,
        "target_steps": config.steps,
        "accepted_steps": int(solver.accepted_steps),
        "elapsed_s": time.perf_counter() - started,
        "stop": stop,
        "budget": budget,
        "global_budget_before": global_base,
        "global_budget_accounting_status": global_base.get("cost_accounting_status"),
        "global_budget_after": {
            "adam": global_base["adam"] + budget["adam"],
            "closures": global_base["closures"] + budget["closures"],
            "lbfgs_steps": global_base["lbfgs_steps"] + budget["lbfgs_steps"],
        },
        "recovery_eligible": status == "RESOURCE_LIMIT" and stop is not None and not stop.get("row"),
        "arm_spec": spec,
        "source_hashes": source_hashes(ROOT),
        "last_accepted_step": final_accepted,
        "stop_row": stop_row,
        "probe_timeseries": probes,
        "checkpoint_pointer": display_path(out_dir / "checkpoint_pointer.json"),
        "run_dir": display_path(out_dir),
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
    }
    write_json(out_dir / "summary.json", S._json_safe(summary))
    update_stage_status(arm, summary)
    write_report()
    return summary


def update_stage_status(arm: str, summary: dict[str, Any]) -> None:
    manifest = load_manifest()
    m2 = manifest.setdefault("m2", {
        "schema": SCHEMA,
        "registered_at_utc": utc_now(),
        "arms": {name: arm_rule(name) for name in ("A-R", "A-P", "B-R", "B-P")},
        "status": {name: "NOT_RUN" for name in ("A-R", "A-P", "B-R", "B-P")},
        "arm_budget": {"adam": ARM_ADAM_CAP, "closures": ARM_CLOSURE_CAP},
        "global_online_budget": {"adam": GLOBAL_ADAM_CAP, "closures": GLOBAL_CLOSURE_CAP},
    })
    m2.setdefault("status", {})[arm] = summary["status"]
    m2.setdefault("runs", {})[arm] = {
        "status": summary["status"],
        "accepted_steps": summary["accepted_steps"],
        "adam": summary["budget"]["adam"],
        "closures": summary["budget"]["closures"],
        "elapsed_s": summary["elapsed_s"],
    }
    manifest.setdefault("status", {})["M2"] = "IN_PROGRESS"
    write_json(manifest_path(), manifest)
    stage_path = OUT / "stage_status.json"
    stage = read_json(stage_path) if stage_path.exists() else {"schema": "direct-mechanism-stage-status-v1"}
    stage["M2"] = m2
    write_json(stage_path, stage)


def should_run_arm(arm: str) -> tuple[bool, str]:
    manifest = load_manifest()
    status = manifest.get("m2", {}).get("status", {})
    if status.get(arm) and status.get(arm) != "NOT_RUN":
        return False, f"{arm} already has status {status.get(arm)}"
    if arm == "A-P" and status.get("A-R") in (None, "NOT_RUN"):
        return False, "A-R must run before A-P"
    if arm in {"B-R", "B-P"}:
        a_r = status.get("A-R")
        a_p = status.get("A-P")
        if a_r == "PASS" and a_p == "PASS":
            return False, "A arms both PASS; B precondition false"
        if arm == "B-R" and (a_r in (None, "NOT_RUN") or a_p in (None, "NOT_RUN")):
            return False, "A-R and A-P must finish before B-R"
        if arm == "B-P" and status.get("B-R") in (None, "NOT_RUN"):
            return False, "B-R must run before B-P"
    return True, "ready"


def write_report() -> None:
    manifest = load_manifest()
    m2 = manifest.get("m2", {})
    lines = [
        "# M2 Report - Bounded Direct 128 Queue",
        "",
        f"- Updated: `{utc_now()}`",
        "- Scientific rule: only a complete 128-step arm with residual and field gates can advance.",
        "- Exact Yee or fixed-state projections are not counted as DCO scores.",
        "",
        "| Arm | Status | Accepted | Adam | Closures | Elapsed s |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for arm in ("A-R", "A-P", "B-R", "B-P"):
        run = m2.get("runs", {}).get(arm)
        if not run:
            lines.append(f"| {arm} | NOT_RUN | 0 | 0 | 0 | 0 |")
        else:
            lines.append(
                f"| {arm} | {run['status']} | {run['accepted_steps']} | "
                f"{run['adam']} | {run['closures']} | {run['elapsed_s']:.1f} |"
            )
    lines.extend(["", "## Arm Details", ""])
    for summary_path in sorted(RUNS.glob("*/summary.json")):
        try:
            summary = read_json(summary_path)
        except Exception:
            continue
        if summary.get("schema") != "direct-mechanism-m2-arm-summary-v1":
            continue
        stop = summary.get("stop") or {}
        row = stop.get("row") or summary.get("last_accepted_step") or {}
        fit_h = row.get("fit_H") or {}
        fit_e = row.get("fit_E") or {}
        metrics = (summary.get("last_accepted_step") or {}).get("six_component_metrics")
        lines.extend([
            f"### {summary['arm']}",
            "",
            f"- Status: `{summary['status']}`; accepted `{summary['accepted_steps']}/{summary['target_steps']}`.",
            f"- Stop reason: `{stop.get('reason')}`.",
            f"- Budget: Adam `{summary['budget']['adam']}`, closures `{summary['budget']['closures']}`, LBFGS steps `{summary['budget']['lbfgs_steps']}`.",
            f"- Final/stop H R: `{fit_h.get('residual_ratio')}`; E R: `{fit_e.get('residual_ratio')}`.",
            f"- Recovery eligible: `{summary.get('recovery_eligible')}`.",
            f"- Six-component metrics present on last accepted step: `{metrics is not None}`.",
            "",
        ])
    (OUT / "M2_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def status() -> None:
    manifest = load_manifest()
    print(json.dumps(manifest.get("m2", {"status": "NOT_STARTED"}), ensure_ascii=False, indent=2))


def mark_not_run(arm: str, reason: str) -> None:
    manifest = load_manifest()
    m2 = manifest.setdefault("m2", {
        "schema": SCHEMA,
        "registered_at_utc": utc_now(),
        "arms": {name: arm_rule(name) for name in ("A-R", "A-P", "B-R", "B-P")},
        "status": {name: "NOT_RUN" for name in ("A-R", "A-P", "B-R", "B-P")},
        "arm_budget": {"adam": ARM_ADAM_CAP, "closures": ARM_CLOSURE_CAP},
        "global_online_budget": {"adam": GLOBAL_ADAM_CAP, "closures": GLOBAL_CLOSURE_CAP},
    })
    m2.setdefault("status", {})[arm] = "NOT_RUN"
    m2.setdefault("not_run_reasons", {})[arm] = reason
    write_json(manifest_path(), manifest)
    write_report()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=("A-R", "A-P", "B-R", "B-P"), required=True)
    r.add_argument("--action-id", required=True)
    r.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    s = sub.add_parser("status")
    m = sub.add_parser("mark-not-run")
    m.add_argument("--arm", choices=("B-R", "B-P"), required=True)
    m.add_argument("--reason", required=True)
    args = parser.parse_args()
    if args.cmd == "status":
        status()
        return
    if args.cmd == "mark-not-run":
        mark_not_run(args.arm, args.reason)
        return
    ready, why = should_run_arm(args.arm)
    if not ready:
        raise RuntimeError(why)
    summary = run_arm(args.arm, args.action_id, args.device)
    print(json.dumps({
        "arm": summary["arm"],
        "status": summary["status"],
        "accepted_steps": summary["accepted_steps"],
        "budget": summary["budget"],
        "elapsed_s": summary["elapsed_s"],
        "run_dir": summary["run_dir"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
