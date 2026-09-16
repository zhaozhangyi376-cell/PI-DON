"""P3 fixed Yee-state inner-fit diagnosis (not a closed-loop rollout)."""

from __future__ import annotations

import argparse
import copy
import json
import os
import time
from pathlib import Path

import numpy as np
import torch

import fdtd
from pidon_contract import six_component_metrics
from pidon_recording import sha256_file, source_hashes
from pidon_solve import Solver, to_t


STATES = (16, 43, 96, 300, 600)
DEVELOPMENT = {43, 96}


def copy_state(a):
    return {key: value.copy() for key, value in a.items()}


def arrays(n, dtype=np.float64):
    return {
        "Ex": np.zeros((n, n + 1, n + 1), dtype=dtype), "Ey": np.zeros((n + 1, n, n + 1), dtype=dtype),
        "Ez": np.zeros((n + 1, n + 1, n), dtype=dtype), "Hx": np.zeros((n + 1, n, n), dtype=dtype),
        "Hy": np.zeros((n, n + 1, n), dtype=dtype), "Hz": np.zeros((n, n, n + 1), dtype=dtype),
    }


def pec(a):
    a["Ex"][:, 0, :] = a["Ex"][:, -1, :] = 0; a["Ex"][:, :, 0] = a["Ex"][:, :, -1] = 0
    a["Ey"][0, :, :] = a["Ey"][-1, :, :] = 0; a["Ey"][:, :, 0] = a["Ey"][:, :, -1] = 0
    a["Ez"][0, :, :] = a["Ez"][-1, :, :] = 0; a["Ez"][:, 0, :] = a["Ez"][:, -1, :] = 0


def insert_prediction(exact, prediction, n, which):
    result = [x.copy() for x in exact]
    for k in range(3):
        p = prediction[k].detach().cpu().numpy()
        shape = tuple(min(result[k].shape[d], p.shape[d]) for d in range(3))
        result[k][tuple(slice(0, z) for z in shape)] = p[tuple(slice(0, z) for z in shape)]
        if result[k].size > int(np.prod(shape)):
            if which != "E" or result[k].shape[k] != n + 1:
                raise RuntimeError("P2 support contract violated in fixed-state diagnostic")
            high = [slice(None)] * 3; high[k] = n
            if not np.all(result[k][tuple(high)] == 0):
                raise RuntimeError("nonzero uncovered curl-E support")
            result[k][tuple(high)] = 0.0
    return result


def e_source_update(a, curl_h, *, dt, dx, source):
    result = copy_state(a)
    ke = dt / fdtd.EPS0
    result["Ex"][:, 1:-1, 1:-1] += ke * curl_h[0]
    result["Ey"][1:-1, :, 1:-1] += ke * curl_h[1]
    result["Ez"][1:-1, 1:-1, :] += ke * curl_h[2]
    c = result["Ez"].shape[2] // 2
    result["Ez"][c, c, c] = source
    pec(result)
    return result


def h_update(a, curl_e, *, dt):
    result = copy_state(a)
    kh = dt / fdtd.MU0
    for name, curl in zip(("Hx", "Hy", "Hz"), curl_e):
        result[name] -= kh * curl
    return result


def fixed_pairs(n, side, dt, selected):
    dx = side / n
    fields = arrays(n)
    g = fdtd.source_waveform(max(selected), dt, 15e9, "gauss")
    pairs = {}
    for index, source in enumerate(g, start=1):
        before = copy_state(fields)
        curl_h = fdtd.curl_H(before["Hx"], before["Hy"], before["Hz"], dx, dx, dx)
        after_e = e_source_update(before, curl_h, dt=dt, dx=dx, source=source)
        curl_e = fdtd.curl_E(after_e["Ex"], after_e["Ey"], after_e["Ez"], dx, dx, dx)
        after_h = h_update(after_e, curl_e, dt=dt)
        if index in selected:
            pairs[index] = {
                "H_field": [before[key] for key in ("Hx", "Hy", "Hz")], "curl_H": list(curl_h),
                "E_field": [after_e[key] for key in ("Ex", "Ey", "Ez")], "curl_E": list(curl_e),
                "before": before, "after_e": after_e, "after_h": after_h, "source": float(source),
            }
        fields = after_h
    return pairs


def args_for_fit(base, *, max_inner):
    return argparse.Namespace(
        n=base.n, side=base.side, dt=base.dt, init=base.init, coords="cellsize", norm="rms",
        levels=4, base=32, lr=base.lr, separate_nets=True, reset_opt_each_step=False,
        grad_clip=0.0, h_scale=1.0, h_output_scale=1.0, h_shift=False,
        tol=base.tol, tol_mode="rel", component_rel=False, max_inner=max_inner,
        inner_time_budget_s=base.per_task_budget_s, strict_stop=True,
        lbfgs_closures=getattr(base, "lbfgs_closures", 0), lbfgs_lr=getattr(base, "lbfgs_lr", 1.0),
        lbfgs_history=getattr(base, "lbfgs_history", 10), lbfgs_time_budget_s=getattr(base, "lbfgs_time_budget_s", 0.0),
    )


def fit_once(base, device, field, target, which, max_inner):
    solver = Solver(args_for_fit(base, max_inner=max_inner), device)
    tensors = [[to_t(value, device) for value in field], [to_t(value, device) for value in target]]
    record = solver.inner_train(tensors[0], tensors[1], which)
    return record


def error_metrics(pred_state, ref_state, n, side):
    return six_component_metrics(
        [to_t(pred_state[name], "cpu") for name in ("Ex", "Ey", "Ez")],
        [to_t(pred_state[name], "cpu") for name in ("Hx", "Hy", "Hz")],
        [to_t(ref_state[name], "cpu") for name in ("Ex", "Ey", "Ez")],
        [to_t(ref_state[name], "cpu") for name in ("Hx", "Hy", "Hz")],
        (side / n,) * 3,
    )


def one_step_errors(pair, fit_h, fit_e, n, side, dt):
    dx = side / n
    exact_h = fdtd.curl_H(pair["before"]["Hx"], pair["before"]["Hy"], pair["before"]["Hz"], dx, dx, dx)
    h_prediction = insert_prediction(exact_h, fit_h.prediction, n, "H")
    h_only = e_source_update(pair["before"], h_prediction, dt=dt, dx=dx, source=pair["source"])
    # H-only is judged on E while holding exact H, to make the replacement local.
    h_only.update({key: pair["after_h"][key] for key in ("Hx", "Hy", "Hz")})
    exact_e = fdtd.curl_E(pair["after_e"]["Ex"], pair["after_e"]["Ey"], pair["after_e"]["Ez"], dx, dx, dx)
    e_prediction = insert_prediction(exact_e, fit_e.prediction, n, "E")
    e_only = h_update(pair["after_e"], e_prediction, dt=dt)
    e_only.update({key: pair["after_h"][key] for key in ("Ex", "Ey", "Ez")})
    both_e = e_source_update(pair["before"], h_prediction, dt=dt, dx=dx, source=pair["source"])
    both = h_update(both_e, e_prediction, dt=dt)
    return {
        "curl_H_only": error_metrics(h_only, pair["after_h"], n, side),
        "curl_E_only": error_metrics(e_only, pair["after_h"], n, side),
        "both_single_step": error_metrics(both, pair["after_h"], n, side),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixed"], default="fixed")
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/fixed_states")
    parser.add_argument("--init", default="dco_paper32.pt")
    parser.add_argument("--n", type=int, default=31)
    parser.add_argument("--side", type=float, default=0.05)
    parser.add_argument("--dt", type=float, default=3.075e-12)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--tol", type=float, default=1e-4)
    parser.add_argument("--max-inner", type=int, default=500)
    parser.add_argument("--baseline-updates", type=int, default=0,
                        help="separate no-LBFGS baseline budget; P3 uses 0, P4-A uses 200")
    parser.add_argument("--lbfgs-closures", type=int, default=0)
    parser.add_argument("--lbfgs-lr", type=float, default=1.0)
    parser.add_argument("--lbfgs-history", type=int, default=10)
    parser.add_argument("--lbfgs-time-budget-s", type=float, default=0.0)
    parser.add_argument("--per-task-budget-s", type=float, default=360.0)
    parser.add_argument("--total-budget-s", type=float, default=3600.0)
    parser.add_argument("--device", default="", choices=["", "cpu", "cuda"])
    parser.add_argument("--states", type=int, nargs="+", default=list(STATES))
    parser.add_argument("--subproblems", choices=["H", "E"], nargs="+", default=["H", "E"])
    a = parser.parse_args()
    device = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pairs = fixed_pairs(a.n, a.side, a.dt, tuple(a.states))
    started = time.perf_counter(); tasks = []; live_fits = {}; stopped_for_budget = False
    for step in a.states:
        pair = pairs[step]
        torch.save({key: value for key, value in pair.items() if key not in ("before", "after_e", "after_h")}, out / f"state_{step:04d}_targets.pt")
        for which, field_key, target_key in (("H", "H_field", "curl_H"), ("E", "E_field", "curl_E")):
            if which not in a.subproblems:
                continue
            if time.perf_counter() - started >= a.total_budget_s:
                stopped_for_budget = True; break
            baseline_args = copy.copy(a)
            baseline_args.lbfgs_closures = 0
            baseline = fit_once(baseline_args, device, pair[field_key], pair[target_key], which, a.baseline_updates)
            result = fit_once(a, device, pair[field_key], pair[target_key], which, a.max_inner)
            live_fits[(step, which)] = result
            tasks.append({"step": step, "split": "development" if step in DEVELOPMENT else "validation",
                          "which": which, "baseline": baseline.as_dict(), "fit": result.as_dict()})
        if stopped_for_budget:
            break
    by_step = {}
    for step in a.states:
        found = {x["which"]: x for x in tasks if x["step"] == step}
        if set(found) == {"H", "E"}:
            by_step[str(step)] = one_step_errors(pairs[step], live_fits[(step, "H")],
                                                  live_fits[(step, "E")],
                                                  a.n, a.side, a.dt)
    payload = {
        "schema": "pidon-p3-fixed-state-v1", "classification": "fixed FDTD state diagnostic; not a closed-loop DCO trajectory",
        "config": vars(a), "device": device, "source_hashes": source_hashes(Path(__file__).parent),
        "init_sha256": sha256_file(a.init), "tasks": tasks, "single_step_errors": by_step,
        "elapsed_s": time.perf_counter() - started, "stopped_for_total_budget": stopped_for_budget,
    }
    (out / "fixed_state_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "tasks": len(tasks), "elapsed_s": payload["elapsed_s"],
                      "stopped_for_total_budget": stopped_for_budget}, ensure_ascii=False))
if __name__ == "__main__":
    main()
