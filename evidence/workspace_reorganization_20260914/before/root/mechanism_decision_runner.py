"""Run one registered P/R sequential arm without changing solver source."""
from __future__ import annotations

import argparse
import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

import fdtd
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hashes


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "mechanism_decision_v1"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_protocol() -> dict:
    path = OUT / "protocol.json"
    if not path.is_file():
        raise FileNotFoundError("run mechanism_decision_init.py first")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if source_hashes(ROOT) != protocol["source_hashes"]:
        raise RuntimeError("solver source changed after protocol registration; register a new experiment instead")
    if now_utc() >= datetime.fromisoformat(protocol["training_deadline_utc"]):
        raise RuntimeError("registered training deadline has elapsed")
    return protocol


def config_for(protocol: dict, arm: str, target_steps: int, out_dir: Path) -> argparse.Namespace:
    values = dict(protocol["common_config"])
    values.update({"init": protocol["arms"][arm]["init"], "seed": protocol["arms"][arm]["seed"],
                   "steps": target_steps, "out_dir": str(out_dir), "out": str(out_dir / "summary.json"),
                   "checkpoint_every": 64, "device": "cuda" if torch.cuda.is_available() else "cpu",
                   "resume": "", "calib": [], "calib_iters": []})
    return argparse.Namespace(**values)


def trace_wrapper(solver: S.Solver):
    original = solver.inner_train
    traces: dict[str, list[dict]] = {}
    def wrapped(field, target, which="shared"):
        record = original(field, target, which)
        traces[which] = copy.deepcopy(getattr(solver, "last_fit_trace", []))
        return record
    solver.inner_train = wrapped
    return traces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("P", "R"), required=True)
    parser.add_argument("--target-steps", choices=(64, 128), type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    protocol = load_protocol()
    run_dir = OUT / "runs" / args.arm
    if args.resume != run_dir.exists():
        raise ValueError("new arm requires absent directory; --resume requires its existing directory")
    config = config_for(protocol, args.arm, args.target_steps, run_dir)
    np.random.seed(config.seed); torch.manual_seed(config.seed)
    device = config.device
    resume_payload = None
    if args.resume:
        checkpoint = run_dir / "checkpoint_latest.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        resume_payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        S.assert_resume_compatible(config, resume_payload["frozen_config"])
    solver = S.Solver(config, device)
    ref = fdtd.PECCavity(side=config.side, n=config.n, dt=config.dt)
    if resume_payload is not None:
        solver.load_state_payload(resume_payload)
        S._restore_reference(ref, resume_payload["reference"])
        if config.steps < solver.accepted_steps:
            raise ValueError("target steps precede the persisted accepted count")
    existing_run_id = None
    if args.resume:
        existing_run_id = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))["run_id"]
    identity = S.formal_run_identity(config, run_id=existing_run_id)
    recorder = RunRecorder(run_dir, {"schema": "pidon-mechanism-run-v1", "config": vars(config),
                                     "protocol_sha256": sha256_file(OUT / "protocol.json"), **identity},
                           mode="resume" if args.resume else "new")
    waveform = fdtd.source_waveform(config.steps, solver.dt, config.fmax, "hard")
    source_cell = config.n // 2
    traces = trace_wrapper(solver)
    rows = []
    started = time.perf_counter()
    stop = None
    while solver.accepted_steps < config.steps:
        if now_utc() >= datetime.fromisoformat(protocol["training_deadline_utc"]):
            stop = {"reason": "global_training_deadline"}
            break
        layer = solver.current_time_layer
        record = solver.step(float(waveform[layer]))
        if record.accepted:
            ref.step_e_source_h(src_value=waveform[layer], src_idx=(source_cell, source_cell, source_cell))
        row = S._json_safe(S._step_summary(solver, ref, record))
        row["fit_traces"] = S._json_safe(copy.deepcopy(traces))
        row["protocol_arm"] = args.arm
        recorder.append(row)
        rows.append(row)
        if record.accepted and solver.accepted_steps in {64, 128}:
            recorder.checkpoint(S._checkpoint_payload(solver, ref, requested_steps=config.steps, source_index=layer + 1))
        if not record.accepted:
            payload = S._checkpoint_payload(solver, ref, requested_steps=config.steps, source_index=layer)
            recorder.failure_raw(payload)
            recorder.checkpoint(payload)
            stop = row
            break
    recorder.checkpoint(S._checkpoint_payload(solver, ref, requested_steps=config.steps,
                                               source_index=solver.current_time_layer))
    result = {
        "schema": "pidon-mechanism-run-summary-v1", "protocol_sha256": sha256_file(OUT / "protocol.json"),
        "arm": args.arm, "target_steps": config.steps, "resume": args.resume,
        "accepted_steps": solver.accepted_steps, "elapsed_s": time.perf_counter() - started,
        "stop": stop, "recovery_eligible": stop is None,
        "source_hashes": source_hashes(ROOT), "rows": rows,
    }
    atomic_json_save(result, run_dir / "mechanism_summary.json")
    print(json.dumps({"arm": args.arm, "accepted_steps": solver.accepted_steps, "target_steps": config.steps,
                      "elapsed_s": result["elapsed_s"], "stop": stop}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
