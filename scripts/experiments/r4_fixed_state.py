"""R4 v2 development-state diagnostic using the repaired Solver contract."""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import math
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

import fdtd
from pidon_contract import SOURCE_OUTSIDE_PROBES_CELLS, six_component_metrics, trilinear_sample
from pidon_recording import sha256_file, source_hashes
from pidon_solve import Solver, to_t


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def fields(cavity):
    return {name: getattr(cavity, name).copy() for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")}


def fixed_pairs(n, side, dt, selected):
    """Capture exact FDTD states immediately before H fit and after E/source."""
    cavity = fdtd.PECCavity(side=side, n=n, dt=dt)
    source = fdtd.source_waveform(max(selected), dt, 15e9, "gauss")
    c, result = n // 2, {}
    for source_index, value in enumerate(source):
        before = fields(cavity)
        curl_h = fdtd.curl_H(before["Hx"], before["Hy"], before["Hz"], cavity.dx, cavity.dy, cavity.dz)
        # Capture E after precisely the E/source part of the independent Yee update.
        after_e_cavity = fdtd.PECCavity(side=side, n=n, dt=dt)
        for name, array in before.items():
            setattr(after_e_cavity, name, array.copy())
        hx, hy, hz = curl_h
        ke = dt / fdtd.EPS0
        after_e_cavity.Ex[:, 1:-1, 1:-1] += ke * hx
        after_e_cavity.Ey[1:-1, :, 1:-1] += ke * hy
        after_e_cavity.Ez[1:-1, 1:-1, :] += ke * hz
        after_e_cavity.Ez[c, c, c] = value
        after_e_cavity.apply_pec()
        after_e = fields(after_e_cavity)
        curl_e = fdtd.curl_E(after_e["Ex"], after_e["Ey"], after_e["Ez"], cavity.dx, cavity.dy, cavity.dz)
        cavity.step_e_source_h(src_value=float(value), src_idx=(c, c, c))
        after_h = fields(cavity)
        human_step = source_index + 1
        if human_step in selected:
            result[human_step] = {"source_index": source_index, "source": float(value),
                                  "before": before, "after_e": after_e, "after_h": after_h,
                                  "curl_H": curl_h, "curl_E": curl_e}
    return result


def solver_args(a, *, max_inner=None):
    return SimpleNamespace(n=a.n, side=a.side, dt=a.dt, init=a.init, coords="cellsize", norm="rms",
                           levels=4, base=32, lr=a.lr, separate_nets=True, reset_opt_each_step=False,
                           grad_clip=0.0, h_scale=1.0, h_output_scale=1.0, h_shift=False,
                           tol=a.tol, tol_mode="rel", component_rel=False,
                           max_inner=a.max_inner if max_inner is None else max_inner,
                           inner_time_budget_s=a.per_task_budget_s, strict_stop=True,
                           lbfgs_closures=0, lbfgs_lr=1.0, lbfgs_history=10, lbfgs_time_budget_s=0.0,
                           fmax=15e9, seed=20260913)


def set_state(solver, source):
    solver.E = [to_t(source[name], solver.dev) for name in ("Ex", "Ey", "Ez")]
    solver.H = [to_t(source[name], solver.dev) for name in ("Hx", "Hy", "Hz")]


def probes(solver, ref):
    dxyz = (solver.cav.dx, solver.cav.dy, solver.cav.dz)
    output = []
    for cells in SOURCE_OUTSIDE_PROBES_CELLS:
        xyz = tuple(cell * spacing for cell, spacing in zip(cells, dxyz))
        output.append({"cells": cells,
                       "dut_Ez": trilinear_sample(solver.E[2], xyz, dxyz, (0, 0, 0.5)),
                       "ref_Ez": trilinear_sample(to_t(ref["Ez"], solver.dev), xyz, dxyz, (0, 0, 0.5))})
    return output


def run_development(a):
    pairs = fixed_pairs(a.n, a.side, a.dt, tuple(a.states))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for step, pair in pairs.items():
        torch.save(pair, out / f"state_{step:04d}_complete.pt")
    tasks, started = [], time.perf_counter()
    for step in a.states:
        pair = pairs[step]
        if time.perf_counter() - started >= a.total_budget_s:
            break
        baseline_solver = Solver(solver_args(a, max_inner=0), a.device)
        # Baselines use fixed FDTD inputs/targets and do not train.
        set_state(baseline_solver, pair["before"])
        baseline_h = baseline_solver.inner_train(baseline_solver.H, baseline_solver.yee_curl_H(), "H")
        set_state(baseline_solver, pair["after_e"])
        baseline_e = baseline_solver.inner_train(baseline_solver.E, baseline_solver.yee_curl_E(), "E")
        # Sequential candidate: curl-H is trained and applied before curl-E target is formed.
        solver = Solver(solver_args(a), a.device)
        set_state(solver, pair["before"])
        solver._clear_fit_progress("H"); solver._clear_fit_progress("E")
        fit_h = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
        solver._record_fit_attempt("H", fit_h)
        trace_h = list(solver.last_fit_trace)
        if fit_h.passed:
            solver._update_E_and_source(fit_h.prediction, pair["source"])
            fit_e = solver.inner_train(solver.E, solver.yee_curl_E(), "E")
            solver._record_fit_attempt("E", fit_e)
            trace_e = list(solver.last_fit_trace)
        else:
            fit_e = None
            trace_e = []
        if fit_e is not None and fit_e.passed:
            solver._update_H(fit_e.prediction)
        ref_e = [to_t(pair["after_h"][name], solver.dev) for name in ("Ex", "Ey", "Ez")]
        ref_h = [to_t(pair["after_h"][name], solver.dev) for name in ("Hx", "Hy", "Hz")]
        metrics = six_component_metrics(solver.E, solver.H, ref_e, ref_h, (solver.cav.dx,) * 3,
                                       source_ez_index=(a.n // 2,) * 3)
        payload = solver.state_payload()
        payload["fixed_state_step"] = step
        torch.save(payload, out / f"candidate_step_{step:04d}.pt")
        tasks.append({"step": step, "split": "development", "source_index": pair["source_index"],
                      "baseline_H": baseline_h.as_dict(), "baseline_E": baseline_e.as_dict(),
                      "fit_H": fit_h.as_dict(), "fit_E": fit_e.as_dict() if fit_e else None,
                      "fixed_amplitude_error": metrics["fixed_amplitude_error"],
                      "instantaneous_Q": metrics["global_weighted_relative_l2"],
                      "six_component_metrics": metrics["components"], "source_outside_probes": probes(solver, pair["after_h"]),
                      "phase": "completed" if fit_e and fit_e.passed else ("E_pending" if fit_h.passed else "before_H"),
                      "waveform_status": "N/A_fixed_single_time", "elapsed_s": time.perf_counter() - started,
                      "fit_H_trace": trace_h, "fit_E_trace": trace_e})
    result = {"schema": "pidon-r4-v2-development", "classification": "sequential fixed-state diagnostic; not closed-loop rollout",
              "config": vars(a), "source_hashes": source_hashes(PROJECT_ROOT), "init_sha256": sha256_file(a.init),
              "tasks": tasks, "elapsed_s": time.perf_counter() - started,
              "g1_development_pass": bool(tasks) and all(x["fit_H"]["passed"] and x["fit_E"] and x["fit_E"]["passed"]
                                                          and x["fixed_amplitude_error"] <= 1e-3 for x in tasks)}
    result = json_safe(result)
    (out / "R4_development.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "tasks": len(tasks), "g1_development_pass": result["g1_development_pass"],
                      "elapsed_s": result["elapsed_s"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/gpt6_plan_v2/R4_development")
    parser.add_argument("--init", default="dco_lr1e3_300.pt")
    parser.add_argument("--n", type=int, default=31); parser.add_argument("--side", type=float, default=.05)
    parser.add_argument("--dt", type=float, default=3.075e-12); parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--tol", type=float, default=1e-4); parser.add_argument("--max-inner", type=int, default=500)
    parser.add_argument("--per-task-budget-s", type=float, default=360); parser.add_argument("--total-budget-s", type=float, default=3600)
    parser.add_argument("--states", type=int, nargs="+", default=[43, 96]); parser.add_argument("--device", default="cuda")
    run_development(parser.parse_args())


if __name__ == "__main__":
    main()
