"""The single registered A3 h_shift=True fixed-state candidate.

This is deliberately not a rollout and never resumes v1/v2 optimizer state.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from pidon_contract import six_component_metrics
from pidon_recording import RunRecorder, sha256_file, source_hashes
from pidon_solve import Solver, formal_run_identity, to_t
from r4_fixed_state import fixed_pairs


ROOT = Path(__file__).resolve().parent
OUT_DEFAULT = ROOT / "evidence" / "gpt6_plan_v3" / "h_layout_candidate"
SOURCE_FILES = ("h_layout_candidate.py", "pidon_solve.py", "pidon_contract.py", "pidon_recording.py",
                "fdtd.py", "dco.py", "r4_fixed_state.py")


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    return value


def solver_args(config):
    return SimpleNamespace(
        n=config["n"], side=config["side"], dt=config["dt"], init=config["init"],
        coords=config["coords"], norm=config["norm"], levels=config["levels"], base=config["base"],
        lr=config["lr"], separate_nets=config["separate_nets"], reset_opt_each_step=False,
        grad_clip=0.0, h_scale=config["h_scale"], h_output_scale=config["h_output_scale"],
        h_shift=config["h_shift"], tol=config["tol"], tol_mode=config["tol_mode"],
        component_rel=False, max_inner=config["max_inner"], inner_time_budget_s=config["inner_time_budget_s"],
        strict_stop=True, lbfgs_closures=config["lbfgs_closures"], lbfgs_lr=1.0,
        lbfgs_history=10, lbfgs_time_budget_s=0.0, fmax=config["fmax"], seed=config["seed"],
        torch_dtype="float32", source_mode="hard",
    )


def set_state(solver, source):
    solver.E = [to_t(source[name], solver.dev, solver.dtype) for name in ("Ex", "Ey", "Ez")]
    solver.H = [to_t(source[name], solver.dev, solver.dtype) for name in ("Hx", "Hy", "Hz")]


def residual(solver, which, field=None, target=None, *, store_prediction=False):
    field = field if field is not None else (solver.H if which == "H" else solver.E)
    target = target if target is not None else (solver.yee_curl_H() if which == "H" else solver.yee_curl_E())
    core = solver.extract_input_core(field, which)
    h_scale = solver.a.h_scale if which == "H" else 1.0
    out_scale = solver.a.h_output_scale if which == "H" else 1.0
    core = core * h_scale
    with torch.no_grad():
        output = solver.predict(core, which)
    prediction, physical_target = [], []
    for index, item in enumerate(target):
        shape = tuple(min(size, solver.n) for size in item.shape)
        prediction.append(output[index, :shape[0], :shape[1], :shape[2]])
        physical_target.append(item[:shape[0], :shape[1], :shape[2]])
    physical_prediction = [item / out_scale / h_scale for item in prediction]
    sse = float(sum((p - t).pow(2).sum() for p, t in zip(physical_prediction, physical_target)))
    target_ss = float(sum(t.pow(2).sum() for t in physical_target))
    result = {"R": sse / target_ss if target_ss > 0 else None, "sse": sse, "target_ss": target_ss,
              "mse": sse / max(sum(t.numel() for t in physical_target), 1),
              "target_count": sum(t.numel() for t in physical_target),
              "prediction": [item.detach().cpu() for item in physical_prediction] if store_prediction else None,
              "target": [item.detach().cpu() for item in physical_target] if store_prediction else None}
    return result


def metric_summary(row):
    return {key: value for key, value in row.items() if key not in ("prediction", "target")}


def div_curl_max(curl, dxyz):
    cx, cy, cz = [part.detach().cpu() for part in curl]
    div = ((cx[1:, :, :] - cx[:-1, :, :]) / dxyz[0] +
           (cy[:, 1:, :] - cy[:, :-1, :]) / dxyz[1] +
           (cz[:, :, 1:] - cz[:, :, :-1]) / dxyz[2])
    return float(div.abs().max())


def snapshot_sources(out, config_path):
    snapshot = out / "source_snapshot"
    snapshot.mkdir(exist_ok=False)
    hashes = {}
    for name in SOURCE_FILES:
        shutil.copy2(ROOT / name, snapshot / name)
        hashes[name] = sha256_file(snapshot / name)
    shutil.copy2(config_path, snapshot / "candidate_config.json")
    hashes["candidate_config.json"] = sha256_file(snapshot / "candidate_config.json")
    return hashes


def legacy_h_baselines():
    old = json.loads((ROOT / "evidence" / "gpt6_plan_v2" / "R4_development_corrected" /
                      "R4_development.json").read_text(encoding="utf-8"))
    return {task["step"]: task["fit_H"] for task in old["tasks"]}


def make_task_payload(solver, step, pair, fit, check, *, role):
    state = solver.state_payload()
    state.update({"schema": "pidon-h-layout-task-v3", "role": role, "time_layer": step,
                  "source_index": pair["source_index"], "source": pair["source"],
                  "fit": fit.as_dict(), "saved_parameter_R": check["R"],
                  "prediction": check["prediction"], "target": check["target"]})
    return state


def run(config_path, out, device):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    g0 = json.loads((ROOT / "evidence" / "gpt6_plan_v3" / "G0.json").read_text(encoding="utf-8"))
    if g0.get("G0") != "PASS":
        raise RuntimeError("A3 requires a machine G0=PASS")
    if not config.get("h_shift") or config.get("lbfgs_closures") != 0:
        raise RuntimeError("candidate config must be the registered h_shift=True, Adam-only branch")
    if sha256_file(ROOT / config["init"]) != config["init_sha256"]:
        raise RuntimeError("main initialization checkpoint hash differs from the registered candidate")
    out = Path(out)
    args = solver_args(config)
    identity = formal_run_identity(args)
    recorder = RunRecorder(out, {"schema": "pidon-h-layout-candidate-v3", "config": config,
                                 "g0_sha256": sha256_file(ROOT / "evidence" / "gpt6_plan_v3" / "G0.json"),
                                 "classification": config["classification"], **identity}, mode="new")
    source_snapshot = snapshot_sources(out, config_path)
    pairs = fixed_pairs(config["n"], config["side"], config["dt"], tuple(config["development_states"]))
    baselines = legacy_h_baselines()
    started, tasks = time.perf_counter(), []
    for step in config["development_states"]:
        if time.perf_counter() - started >= config["total_budget_s"]:
            tasks.append({"step": step, "status": "NOT_RUN", "reason": "registered_total_budget_exhausted"})
            continue
        pair = pairs[step]
        torch.manual_seed(config["seed"])
        np.random.seed(config["seed"])
        solver = Solver(args, device)
        set_state(solver, pair["before"])
        before = residual(solver, "H", store_prediction=True)
        amplitude = {}
        if step == 43:
            for factor in (1e-3, 1.0, 1e3):
                factor_field = [part * factor for part in solver.H]
                factor_target = [part * factor for part in solver.yee_curl_H()]
                amplitude[str(factor)] = residual(solver, "H", factor_field, factor_target)
        fit_h = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        solver._record_fit_attempt("H", fit_h)
        trace_h = list(solver.last_fit_trace)
        checked_h = residual(solver, "H", store_prediction=True)
        task = {"step": step, "split": "development", "input_layout": "h_shift=True",
                "source_index": pair["source_index"], "source": pair["source"],
                "init_sha256": config["init_sha256"], "before_H": metric_summary(before), "fit_H": fit_h.as_dict(),
                "saved_parameter_R_H": checked_h["R"], "fit_H_trace": trace_h,
                "H_div_curl_max": div_curl_max(checked_h["prediction"], (solver.cav.dx,) * 3),
                "legacy_H500_baseline": baselines.get(step), "amplitude_diagnostics": amplitude or None,
                "actual_adam_updates_H": fit_h.n_updates, "actual_lbfgs_closures_H": fit_h.n_closures,
                "accepted_field_metrics": None, "source_outside_probes": None,
                "recovery_eligible": solver.fit_progress["H"]["resumable"],
                "phase": "before_H"}
        torch.save(make_task_payload(solver, step, pair, fit_h, checked_h, role="H"), out / f"H_step_{step:04d}.pt")
        if fit_h.passed:
            solver._update_E_and_source(fit_h.prediction, pair["source"])
            fit_e = solver.inner_train(solver.E, solver.yee_curl_E(), "E")
            solver._record_fit_attempt("E", fit_e)
            checked_e = residual(solver, "E", store_prediction=True)
            task.update({"fit_E": fit_e.as_dict(), "saved_parameter_R_E": checked_e["R"],
                         "actual_adam_updates_E": fit_e.n_updates, "fit_E_trace": list(solver.last_fit_trace),
                         "phase": "E_pending", "recovery_eligible": solver.fit_progress["E"]["resumable"]})
            torch.save(make_task_payload(solver, step, pair, fit_e, checked_e, role="E_sequential"),
                       out / f"E_sequential_step_{step:04d}.pt")
            if fit_e.passed:
                solver._update_H(fit_e.prediction)
                ref_e = [to_t(pair["after_h"][name], solver.dev, solver.dtype) for name in ("Ex", "Ey", "Ez")]
                ref_h = [to_t(pair["after_h"][name], solver.dev, solver.dtype) for name in ("Hx", "Hy", "Hz")]
                task["accepted_field_metrics"] = six_component_metrics(
                    solver.E, solver.H, ref_e, ref_h, (solver.cav.dx,) * 3,
                    source_ez_index=(config["n"] // 2,) * 3)
                task["phase"] = "completed"
        else:
            # One and only one E diagnostic from the exact reference-E state;
            # it does not substitute for a sequential Algorithm-1 E fit.
            torch.manual_seed(config["seed"])
            oracle = Solver(args, device)
            set_state(oracle, pair["after_e"])
            before_e = residual(oracle, "E", store_prediction=True)
            fit_e = oracle.inner_train(oracle.E, oracle.yee_curl_E(), "E")
            oracle._record_fit_attempt("E", fit_e)
            checked_e = residual(oracle, "E", store_prediction=True)
            task["oracle_E"] = {"classification": "oracle_only_not_G1", "before": metric_summary(before_e),
                                "fit": fit_e.as_dict(), "saved_parameter_R": checked_e["R"],
                                "trace": list(oracle.last_fit_trace), "actual_adam_updates": fit_e.n_updates,
                                "recovery_eligible": oracle.fit_progress["E"]["resumable"]}
            torch.save(make_task_payload(oracle, step, pair, fit_e, checked_e, role="E_oracle_only"),
                       out / f"E_oracle_step_{step:04d}.pt")
            recorder.failure_raw(make_task_payload(solver, step, pair, fit_h, checked_h, role="H_failed_raw"))
        task["elapsed_s"] = time.perf_counter() - started
        tasks.append(task)
        recorder.append(safe({"kind": "development_task", **task}))
        recorder.checkpoint(make_task_payload(solver, step, pair, fit_h, checked_h, role="latest_H_state"))
    g1_development_pass = (len(tasks) == len(config["development_states"]) and all(
        task.get("fit_H", {}).get("passed") and task.get("fit_E", {}).get("passed") and
        task.get("accepted_field_metrics", {}).get("fixed_amplitude_error", float("inf")) <= 1e-3
        for task in tasks if task.get("status") != "NOT_RUN"))
    result = safe({"schema": "pidon-h-layout-candidate-v3", "classification": "DCO fixed-state candidate; not rollout",
                   "config": config, "identity": identity, "source_snapshot": source_snapshot,
                   "g0_sha256": sha256_file(ROOT / "evidence" / "gpt6_plan_v3" / "G0.json"),
                   "tasks": tasks, "elapsed_s": time.perf_counter() - started,
                   "g1_development_pass": g1_development_pass,
                   "validation_status": "NOT_RUN until both development states pass sequential H/E and A_fixed"})
    (out / "A3_development.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "g1_development_pass": g1_development_pass,
                      "tasks": len(tasks), "elapsed_s": result["elapsed_s"]}, ensure_ascii=False))
    return 0 if g1_development_pass else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="evidence/gpt6_plan_v3/candidate_config.json")
    parser.add_argument("--out", default=str(OUT_DEFAULT))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu", choices=("cpu", "cuda"))
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.out, args.device))


if __name__ == "__main__":
    main()
