"""One pre-registered bounded P4-A comparison on the first R4 failure."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import torch

from pidon_recording import sha256_file
from pidon_solve import Solver, to_t
from r4_fixed_state import fixed_pairs, solver_args


def p4a_args():
    return SimpleNamespace(n=31, side=.05, dt=3.075e-12, init="dco_lr1e3_300.pt", lr=3e-4,
                           tol=1e-4, max_inner=200, per_task_budget_s=60.0, fmax=15e9,
                           lbfgs_closures=200, lbfgs_lr=1.0, lbfgs_history=10,
                           lbfgs_time_budget_s=60.0, device="cuda")


def fit(base, pair, *, use_lbfgs):
    args = solver_args(base, max_inner=200)
    args.lbfgs_closures = 200 if use_lbfgs else 0
    args.lbfgs_lr, args.lbfgs_history, args.lbfgs_time_budget_s = 1.0, 10, 60.0
    solver = Solver(args, base.device)
    solver.H = [to_t(pair["before"][name], solver.dev) for name in ("Hx", "Hy", "Hz")]
    record = solver.inner_train(solver.H, solver.yee_curl_H(), "H")
    raw = getattr(solver, "last_failure_raw", None)
    return record, solver.state_payload(), raw


def main():
    base = p4a_args()
    pair = fixed_pairs(base.n, base.side, base.dt, (43,))[43]
    root = Path("evidence/gpt6_plan_v2/R4_p4a_step0043"); root.mkdir(parents=True, exist_ok=True)
    adam, adam_state, _ = fit(base, pair, use_lbfgs=False)
    refined, refined_state, raw = fit(base, pair, use_lbfgs=True)
    torch.save(adam_state, root / "adam200_final.pt")
    torch.save(refined_state, root / "adam200_lbfgs_final.pt")
    if raw is not None:
        torch.save(raw, root / "adam200_lbfgs_trial_raw.pt")
    payload = {"schema": "pidon-r4-p4a-v2", "classification": "one registered development optimizer comparison; not rollout",
               "step": 43, "which": "H", "init_sha256": sha256_file(base.init), "config": vars(base),
               "adam200": adam.as_dict(), "adam200_lbfgs": refined.as_dict(),
               "raw_trial_saved": raw is not None,
               "pass": bool(refined.passed)}
    (root / "P4A.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(root), "adam_R": adam.residual_ratio,
                      "refined_R": refined.residual_ratio, "closures": refined.n_closures,
                      "pass": refined.passed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
