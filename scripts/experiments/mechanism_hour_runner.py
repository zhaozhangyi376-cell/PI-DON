# -*- coding: utf-8 -*-
"""One-hour adaptive P/R mechanism runner.

This module deliberately keeps the existing Solver transaction loop.  It adds
only a persistent wall clock, independent arm identities, a heartbeat callback,
and rolling checkpoint/report plumbing.
"""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import copy
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import torch

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes

ROOT = PROJECT_ROOT
OUT = ROOT / "evidence" / "mechanism_1h_v2"
OLD_PROTOCOL = ROOT / "evidence" / "mechanism_decision_v1" / "protocol.json"
MASTER = ROOT / "dco_lr1e3_300.pt"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat()


def parse(t: str) -> datetime:
    return datetime.fromisoformat(t).astimezone(timezone.utc)


def make_manifest(start: datetime, plan_path: Path, plan_hash: str, master_hash: str) -> dict:
    return {
        "schema": "pidon-mechanism-1h-v2",
        "experiment_id": hashlib.sha256(f"{iso(start)}|{plan_hash}|{master_hash}".encode()).hexdigest()[:24],
        "started_at": iso(start),
        "training_deadline": iso(start + timedelta(minutes=54)),
        "deadline": iso(start + timedelta(minutes=60)),
        "plan_path": str(plan_path), "plan_sha256": plan_hash,
        "master": str(MASTER), "master_sha256": master_hash,
        "source_hashes": source_hashes(ROOT),
        "config": {"n": 31, "side": 0.05, "dt": 3.075e-12, "levels": 4,
                   "base": 32, "coords": "cellsize", "norm": "rms",
                   "separate_nets": True, "h_shift": True, "strict_stop": True,
                   "fmax": 15e9, "max_inner": 3000, "inner_time_budget_s": 240.0,
                   "lbfgs_closures": 0, "head_lstsq_once": False,
                   "grad_clip": 0.0, "h_scale": 1.0, "h_output_scale": 1.0,
                   "component_rel": False, "reset_opt_each_step": False,
                   "torch_dtype": "float32", "source_mode": "hard"},
        "arms": {name: arm_spec(name) for name in ("S-P", "S-R", "X-P", "X-R", "S-R2", "D-LR")},
        "status": {name: "NOT_RUN" for name in ("S-P", "S-R", "X-P", "X-R", "S-R2", "D-LR")},
        "updates_this_experiment": 0,
    }


def arm_spec(name: str) -> dict:
    retry_suffix = name.endswith("-retry")
    base_name = name[:-6] if retry_suffix else name
    if base_name not in {"S-P", "S-R", "X-P", "X-R", "S-R2", "D-LR"}:
        raise ValueError(name)
    explore = base_name.startswith("X-")
    lr = 1e-3 if base_name == "D-LR" else 3e-4
    return {"init": "random" if base_name in {"S-R", "X-R", "S-R2"} else str(MASTER),
            "seed": 20260915 if base_name == "S-R2" else 20260914,
            "lr": lr, "tol": 1e-3 if explore else 1e-4,
            "strict": not explore, "target_steps": 128,
            "purpose": "infrastructure_retry" if retry_suffix else "explore" if explore else "strict" if base_name.startswith("S-") else "diagnostic"}


def seconds_left(manifest: dict, now: datetime | None = None) -> float:
    return max(0.0, (parse(manifest["deadline"]) - (now or utc_now())).total_seconds())


def load_manifest() -> dict:
    p = OUT / "manifest.json"
    if not p.is_file():
        raise FileNotFoundError("run mechanism_hour_runner.py init first")
    m = json.loads(p.read_text(encoding="utf-8"))
    if sha256_file(ROOT / m["plan_path"]) != m["plan_sha256"]:
        raise RuntimeError("plan hash changed after one-hour registration")
    if sha256_file(MASTER) != m["master_sha256"]:
        raise RuntimeError("master checkpoint hash changed")
    if source_hashes(ROOT) != m["source_hashes"]:
        raise RuntimeError("core source changed after one-hour registration")
    return m


def make_heartbeat_callback(path: Path, remaining_ok, *, interval: float = 10.0):
    last = [0.0]
    def callback(which, progress):
        now = time.monotonic()
        if now - last[0] >= interval or not path.exists():
            payload = {"updated_at": iso(utc_now()), "which": which, **copy.deepcopy(progress)}
            atomic_json_save(payload, path)
            last[0] = now
        return bool(remaining_ok())
    return callback


def classify_row(row: dict, arm: str) -> dict:
    spec = arm_spec(arm)
    fits = [row.get("fit_H"), row.get("fit_E")]
    nonzero = [f for f in fits if f and float(f.get("target_ss", 0.0)) > 0.0]
    passed = bool(row.get("accepted"))
    if nonzero:
        passed = passed and all(float(f["residual_ratio"]) < spec["tol"] for f in nonzero)
    updates = sum(int(f.get("n_updates", 0)) for f in fits if f)
    return {"status": "PASS" if passed else "FAIL", "tol": spec["tol"],
            "advance": passed, "budget_consumed_updates": updates}


def _config(manifest: dict, arm: str, out_dir: Path) -> argparse.Namespace:
    a = dict(manifest["config"])
    s = arm_spec(arm)
    a.update(s)
    a.update({"init": s["init"], "seed": s["seed"], "lr": s["lr"], "tol": s["tol"],
              "tol_mode": "rel", "device": "cuda" if torch.cuda.is_available() else "cpu",
              "out_dir": str(out_dir), "out": str(out_dir / "summary.json"),
              "steps": 128, "checkpoint_every": 1, "resume": "", "calib": [],
              "calib_iters": [], "head_rcond": 1e-12, "lbfgs_lr": 1.0,
              "lbfgs_history": 10, "lbfgs_time_budget_s": 0.0})
    return argparse.Namespace(**a)


def _metadata(manifest: dict, arm: str, config: argparse.Namespace) -> dict:
    protocol_hash = sha256_file(OUT / "manifest.json")
    run_id = hashlib.sha256(f"{manifest['experiment_id']}|{arm}".encode()).hexdigest()[:24]
    return {"schema": "pidon-mechanism-1h-run-v1", "arm": arm,
            "run_id": run_id, "protocol_hash": protocol_hash,
            "config": vars(config), "arm_spec": arm_spec(arm),
            "created_at_utc": iso(utc_now())}


def _checkpoint_payload(solver, ref, requested_steps):
    payload = S._checkpoint_payload(solver, ref, requested_steps=requested_steps,
                                    source_index=solver.current_time_layer)
    payload["arm_protocol"] = "mechanism-1h-v2"
    return payload


def _run_arm(manifest: dict, arm: str) -> dict:
    s = arm_spec(arm)
    out = OUT / "runs" / arm.replace("-", "_")
    out.mkdir(parents=True, exist_ok=True)
    config = _config(manifest, arm, out)
    np.random.seed(config.seed); torch.manual_seed(config.seed)
    dev = config.device
    solver = S.Solver(config, dev)
    ref = fdtd.PECCavity(side=config.side, n=config.n, dt=config.dt)
    metadata = _metadata(manifest, arm, config)
    recorder = RunRecorder(out, metadata, mode="new")
    # inner_train treats a truthy callback result as "interrupt now".  The
    # callback therefore becomes true only after the registered deadline;
    # returning true while time remains would abort on the first update.
    heartbeat = make_heartbeat_callback(out / "heartbeat.json",
                                        lambda: seconds_left(manifest) <= 0 or
                                        (parse(manifest["training_deadline"]) - utc_now()).total_seconds() <= 0)
    solver.on_inner_update = heartbeat
    waveform = fdtd.source_waveform(config.steps, solver.dt, config.fmax, "hard")
    src = config.n // 2
    rows = []
    started = time.perf_counter()
    stop = None
    while solver.accepted_steps < config.steps:
        if seconds_left(manifest) <= 0 or (parse(manifest["training_deadline"]) - utc_now()).total_seconds() <= 0:
            stop = {"reason": "RESOURCE_LIMIT", "detail": "registered wall/training deadline"}
            break
        layer = solver.current_time_layer
        try:
            rec = solver.step(float(waveform[layer]))
        except Exception as exc:
            stop = {"reason": "EXCEPTION", "type": type(exc).__name__, "message": str(exc)[:300]}
            break
        if rec.accepted:
            ref.step_e_source_h(src_value=waveform[layer], src_idx=(src, src, src))
        row = S._json_safe(S._step_summary(solver, ref, rec))
        row["arm"] = arm; row["threshold"] = s["tol"]
        row["actual_wall_s"] = time.perf_counter() - started
        row["classification"] = classify_row(row, arm)
        recorder.append(row); rows.append(row)
        recorder.rolling_checkpoint(_checkpoint_payload(solver, ref, config.steps))
        if not rec.accepted:
            raw = solver.last_failure_raw if getattr(solver, "last_failure_raw", None) is not None else _checkpoint_payload(solver, ref, config.steps)
            recorder.failure_raw(raw)
            stop = {"reason": "FIT_FAIL", "row": row}
            break
        if arm == "D-LR" and solver.accepted_steps >= 1:
            stop = {"reason": "DIAGNOSTIC_COMPLETE"}; break
    status = "PASS" if solver.accepted_steps >= config.steps else "FAIL" if stop and stop.get("reason") == "FIT_FAIL" else "RESOURCE_LIMIT" if stop and stop.get("reason") == "RESOURCE_LIMIT" else "INCOMPLETE"
    summary = {"schema": "mechanism-1h-summary-v1", "arm": arm,
               "status": status, "threshold": s["tol"], "accepted_steps": solver.accepted_steps,
               "target_steps": config.steps, "elapsed_s": time.perf_counter()-started,
               "stop": stop, "rows": rows, "source_hashes": source_hashes(ROOT),
               "recovery_eligible": stop is None or stop.get("reason") == "RESOURCE_LIMIT",
               "total_actual_updates": sum(classify_row(r, arm)["budget_consumed_updates"] for r in rows),
               "device": dev, "checkpoint_pointer": str(out / "checkpoint_pointer.json")}
    atomic_json_save(summary, out / "summary.json")
    return summary


def init():
    if OUT.exists():
        raise FileExistsError(f"refusing to replace {OUT}")
    plan = ROOT / "docs" / "superpowers" / "plans" / "2026-09-14-pidon-one-hour-adaptive-mechanism-plan.md"
    start = utc_now()
    OUT.mkdir(parents=True)
    manifest = make_manifest(start, plan, sha256_file(plan), sha256_file(MASTER))
    atomic_json_save(manifest, OUT / "manifest.json")
    atomic_json_save({"schema": "mechanism-1h-stage-status-v1", "started_at": manifest["started_at"],
                      "deadline": manifest["deadline"], "training_deadline": manifest["training_deadline"],
                      "status": manifest["status"]}, OUT / "stage_status.json")
    (OUT / "source_hashes_at_start.json").write_text(json.dumps(manifest["source_hashes"], indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"started_at": manifest["started_at"], "training_deadline": manifest["training_deadline"],
                      "deadline": manifest["deadline"], "experiment_id": manifest["experiment_id"]}, ensure_ascii=False, indent=2))


#: Verdicts that are the end of an arm's story and must never be overwritten
#: by a later bookkeeping pass.
TERMINAL_ARM_STATUS = ("FAIL", "PASS")


def update_status(manifest, arm, summary):
    status = json.loads((OUT / "stage_status.json").read_text(encoding="utf-8"))
    status["status"][arm] = summary["status"]
    fields = ("status", "accepted_steps", "total_actual_updates", "elapsed_s", "recovery_eligible")
    status.setdefault("runs", {})[arm] = {k: summary.get(k) for k in fields}
    atomic_json_save(status, OUT / "stage_status.json")
    manifest.setdefault("status", {})[arm] = summary["status"]
    manifest.setdefault("runs", {})[arm] = {k: summary.get(k) for k in fields}
    # F28: only the per-arm cost was maintained, so the manifest's own
    # ``updates_this_experiment`` stayed at 0 while arms were consuming
    # updates.  Recompute the top-level total from the same per-arm numbers
    # and mark it a lower bound whenever any arm's cost is unknown.
    totals, unknown = 0, []
    for name, row in manifest.get("runs", {}).items():
        value = row.get("total_actual_updates")
        if isinstance(value, int):
            totals += value
        else:
            unknown.append(name)
    manifest["updates_this_experiment"] = totals
    manifest["updates_accounting"] = {
        "sum_of_arm_totals": totals,
        "arms_with_unknown_cost": unknown,
        "status": "LOWER_BOUND" if unknown else "SUM_OF_ARMS",
        "note": "逐臂求和不等于完整实际更新总数；未结算臂保留 UNKNOWN/下界。",
    }
    atomic_json_save(manifest, OUT / "manifest.json")


def report():
    manifest = load_manifest(); status = json.loads((OUT / "stage_status.json").read_text(encoding="utf-8"))
    summaries = {}
    for arm in manifest["arms"]:
        p = OUT / "runs" / arm.replace("-", "_") / "summary.json"
        if p.exists(): summaries[arm] = json.loads(p.read_text(encoding="utf-8"))
    report_lines = ["# 1小时机制与收益验证报告", "", f"- 实验ID：`{manifest['experiment_id']}`",
                    f"- 起点：`{manifest['started_at']}`；训练截止：`{manifest['training_deadline']}`；最终截止：`{manifest['deadline']}`", "",
                    "| 臂 | 类型 | 状态 | 接受步 | 实际更新 | 耗时(s) | 恢复资格 |", "|---|---|---|---:|---:|---:|---|"]
    for arm, spec in manifest["arms"].items():
        x = summaries.get(arm)
        if not x:
            report_lines.append(f"| {arm} | {spec['purpose']} | NOT_RUN | — | — | — | — |")
        else:
            report_lines.append(f"| {arm} | {spec['purpose']} | {x['status']} | {x['accepted_steps']} | {x['total_actual_updates']} | {x['elapsed_s']:.1f} | {x['recovery_eligible']} |")
    report_lines += ["", "严格臂阈值为R<1e-4；探索臂阈值为R<1e-3。探索结果不改判严格FAIL或旧证据。", "", "## 分支结果", ""]
    for arm,x in summaries.items():
        last = x["rows"][-1] if x["rows"] else {}
        report_lines += [f"### {arm}", "", f"- 状态：`{x['status']}`；停止原因：`{(x.get('stop') or {}).get('reason')}`；最终接受步：`{x['accepted_steps']}`。",
                         f"- 最后记录的H/E残差：`{(last.get('fit_H') or {}).get('residual_ratio')}` / `{(last.get('fit_E') or {}).get('residual_ratio')}`。",
                         "- 六分量、源外探针和场质量保存在该臂的steps.jsonl；不接受的半步不计作完整场成绩。", ""]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report_lines)+"\n", encoding="utf-8")
    print("\n".join(report_lines))


def verified_recovery_eligible(out: Path, rows: list) -> dict:
    """Recovery eligibility from a checkpoint that actually loads.

    F28: the old field was ``checkpoint_pointer.json exists``.  An empty
    pointer JSON with no checkpoint beside it therefore certified recovery.
    Load the pointer, verify it names a real slot whose hash matches, and
    check that it reaches the end of the durable log.
    """
    detail: dict = {"pointer_exists": (out / "checkpoint_pointer.json").is_file()}
    if not detail["pointer_exists"]:
        return {**detail, "eligible": False, "reason": "no checkpoint pointer"}
    try:
        pointer = json.loads((out / "checkpoint_pointer.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        return {**detail, "eligible": False, "reason": f"pointer unreadable: {error}"}
    if not isinstance(pointer, dict) or pointer.get("schema") != "pidon-rolling-checkpoint-v1":
        return {**detail, "eligible": False, "reason": "pointer schema is invalid"}
    slot_path = out / str(pointer.get("path", ""))
    detail["slot_exists"] = slot_path.is_file()
    if not detail["slot_exists"]:
        return {**detail, "eligible": False, "reason": "pointer names a checkpoint that is not there"}
    detail["hash_matches"] = sha256_file(slot_path) == pointer.get("sha256")
    if not detail["hash_matches"]:
        return {**detail, "eligible": False, "reason": "checkpoint hash differs from pointer"}
    committed = pointer.get("last_committed_sequence_id")
    detail["checkpoint_sequence_id"] = committed
    detail["durable_rows"] = len(rows)
    if committed is None or int(committed) != len(rows) - 1:
        return {**detail, "eligible": False,
                "reason": "checkpoint does not reach the end of the durable log"}
    return {**detail, "eligible": True, "reason": "verified pointer, slot and log tail",
            "note": "身份/模型/优化器/RNG 的逐项核对仍由恢复入口执行；本字段只认证磁盘提交点。"}


def finalize_arm(manifest: dict, arm: str):
    """Close a deliberately sliced process after its last durable row."""
    out = OUT / "runs" / arm.replace("-", "_")
    rows_path = out / "steps.jsonl"
    if not rows_path.exists():
        raise FileNotFoundError(rows_path)
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    accepted = int(rows[-1].get("accepted_steps", 0)) if rows else 0
    updates = sum(classify_row(row, arm)["budget_consumed_updates"] for row in rows)
    # F28: a terminal verdict is evidence, not a draft.  This entry point used
    # to write RESOURCE_LIMIT unconditionally, so calling it on an arm that had
    # already FAILED silently promoted an optimisation failure into a resource
    # interruption.  Read the existing summary first and refuse.
    existing_path = out / "summary.json"
    if existing_path.is_file():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            existing = {}
        if existing.get("status") in TERMINAL_ARM_STATUS:
            raise SystemExit(
                f"拒绝改写终态：{arm} 已记录 `{existing['status']}`。"
                "资源中断与优化失败是两件事，原 FAIL 不改判；"
                "如需记录新的中断事件，请写入独立的新文件。")
    recovery = verified_recovery_eligible(out, rows)
    summary = {"schema": "mechanism-1h-summary-v2", "arm": arm,
               "status": "RESOURCE_LIMIT", "threshold": arm_spec(arm)["tol"],
               "accepted_steps": accepted, "target_steps": 128,
               "elapsed_s": sum(float(row.get("actual_wall_s", 0.0)) for row in rows[-1:]),
               "stop": {"reason": "SLICE_END", "detail": "deliberate arm boundary after durable checkpoint"},
               "rows": rows, "source_hashes": source_hashes(ROOT),
               "recovery_eligible": recovery["eligible"],
               "recovery_check": recovery,
               "total_actual_updates": updates,
               "device": "cuda" if torch.cuda.is_available() else "cpu",
               "checkpoint_pointer": str(out / "checkpoint_pointer.json")}
    atomic_json_save(summary, out / "summary.json")
    update_status(manifest, arm, summary)
    print(json.dumps({"arm": arm, "status": summary["status"], "accepted_steps": accepted,
                      "total_actual_updates": updates, "recovery_eligible": summary["recovery_eligible"]}, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init"); r = sub.add_parser("run"); r.add_argument("--arm", choices=list(arm_spec.__annotations__) if False else ["S-P","S-R","X-P","X-R","S-R2","D-LR"])
    f = sub.add_parser("finalize"); f.add_argument("--arm", required=True)
    sub.add_parser("report"); a = ap.parse_args()
    if a.cmd == "init": init(); return
    manifest = load_manifest()
    if a.cmd == "report": report(); return
    if a.cmd == "finalize": finalize_arm(manifest, a.arm); return
    if seconds_left(manifest) <= 0: raise RuntimeError("one-hour deadline expired")
    existing = manifest["status"].get(a.arm)
    retry = a.arm + "-retry"
    if existing != "NOT_RUN":
        if not (a.arm == "S-P" and existing == "FAIL" and
                (OUT / "runs" / "S_P" / "summary.json").exists() and
                json.loads((OUT / "runs" / "S_P" / "summary.json").read_text(encoding="utf-8")).get("stop", {}).get("row", {}).get("reason") == "interrupt"):
            raise RuntimeError(f"arm already has status {existing}")
        # One infrastructure-only retry is permitted because the first run
        # interrupted before a scientific budget could be consumed.
        arm = retry
        manifest["arms"][arm] = dict(arm_spec(a.arm), purpose="infrastructure_retry")
        manifest["status"][arm] = "NOT_RUN"
        atomic_json_save(manifest, OUT / "manifest.json")
    else:
        arm = a.arm
    summary = _run_arm(manifest, arm); update_status(manifest, arm, summary)
    print(json.dumps({k: summary[k] for k in ("arm","status","accepted_steps","total_actual_updates","elapsed_s","recovery_eligible")}, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
