"""P2 exact-Yee control for the PI-DON time-layer and support adapter.

It contains no neural network.  Its purpose is to prove that the selected
grid, source timing and predicted-support insertion can reproduce an exact
Yee trajectory in the *same* E→source→H ordering used by ``pidon_solve``.
The result must never be reported as a DCO result.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import fdtd


def _arrays(n: int, dtype):
    return {
        "Ex": np.zeros((n, n + 1, n + 1), dtype=dtype),
        "Ey": np.zeros((n + 1, n, n + 1), dtype=dtype),
        "Ez": np.zeros((n + 1, n + 1, n), dtype=dtype),
        "Hx": np.zeros((n + 1, n, n), dtype=dtype),
        "Hy": np.zeros((n, n + 1, n), dtype=dtype),
        "Hz": np.zeros((n, n, n + 1), dtype=dtype),
    }


def apply_pec(a):
    a["Ex"][:, 0, :] = a["Ex"][:, -1, :] = 0
    a["Ex"][:, :, 0] = a["Ex"][:, :, -1] = 0
    a["Ey"][0, :, :] = a["Ey"][-1, :, :] = 0
    a["Ey"][:, :, 0] = a["Ey"][:, :, -1] = 0
    a["Ez"][0, :, :] = a["Ez"][-1, :, :] = 0
    a["Ez"][:, 0, :] = a["Ez"][:, -1, :] = 0


def step_e_source_h(a, *, dx, dt, source):
    """One explicit E→hard-source→H step, matching current pidon_solve."""
    ch = fdtd.curl_H(a["Hx"], a["Hy"], a["Hz"], dx, dx, dx)
    ke = dt / fdtd.EPS0
    a["Ex"][:, 1:-1, 1:-1] += ke * ch[0]
    a["Ey"][1:-1, :, 1:-1] += ke * ch[1]
    a["Ez"][1:-1, 1:-1, :] += ke * ch[2]
    c = (a["Ez"].shape[2]) // 2
    a["Ez"][c, c, c] = source
    apply_pec(a)
    ce = fdtd.curl_E(a["Ex"], a["Ey"], a["Ez"], dx, dx, dx)
    kh = dt / fdtd.MU0
    a["Hx"] -= kh * ce[0]
    a["Hy"] -= kh * ce[1]
    a["Hz"] -= kh * ce[2]


def adapter_curl_E(a, *, dx):
    """Exact curl passed through the current network-cube support contract.

    Curl-E component k has one high-side plane outside the n-cube.  PEC makes
    that specific tangential-E difference exactly zero.  We check it before
    assigning the analytic boundary plane, so this is an explicit boundary
    condition rather than an implicit exact-Yee fallback.
    """
    exact = list(fdtd.curl_E(a["Ex"], a["Ey"], a["Ez"], dx, dx, dx))
    n = a["Ez"].shape[2]
    result = [part.copy() for part in exact]
    boundary_max = []
    for k, part in enumerate(exact):
        # network cube supplies only [:n,:n,:n]; remaining plane is physical PEC boundary.
        cube = part[:n, :n, :n]
        result[k][:n, :n, :n] = cube
        high = [slice(None)] * 3
        high[k] = n
        boundary = part[tuple(high)]
        boundary_max.append(float(np.max(np.abs(boundary))))
        if not np.allclose(boundary, 0.0, rtol=0.0, atol=0.0):
            raise AssertionError(f"curl-E high {k} plane is not a PEC-zero boundary")
        result[k][tuple(high)] = 0.0
    return result, boundary_max


def step_adapter(a, *, dx, dt, source):
    """Production-support equivalent of exact control, without a DCO."""
    ch = fdtd.curl_H(a["Hx"], a["Hy"], a["Hz"], dx, dx, dx)
    ke = dt / fdtd.EPS0
    a["Ex"][:, 1:-1, 1:-1] += ke * ch[0]
    a["Ey"][1:-1, :, 1:-1] += ke * ch[1]
    a["Ez"][1:-1, 1:-1, :] += ke * ch[2]
    c = a["Ez"].shape[2] // 2
    a["Ez"][c, c, c] = source
    apply_pec(a)
    ce, boundary = adapter_curl_E(a, dx=dx)
    kh = dt / fdtd.MU0
    a["Hx"] -= kh * ce[0]
    a["Hy"] -= kh * ce[1]
    a["Hz"] -= kh * ce[2]
    return boundary


def run(dtype, n=31, steps=128, side=0.05, dt=3.075e-12):
    dx = side / n
    control = _arrays(n, dtype)
    reference = _arrays(n, dtype)
    g = fdtd.source_waveform(steps, dt, 15e9, "gauss").astype(dtype)
    boundary_max = 0.0
    for value in g:
        boundary_max = max(boundary_max, *step_adapter(control, dx=dx, dt=dt, source=value))
        step_e_source_h(reference, dx=dx, dt=dt, source=value)
    errors = {name: float(np.max(np.abs(control[name] - reference[name]))) for name in control}
    ref_norm = math.sqrt(sum(float(np.sum(reference[name].astype(np.float64) ** 2)) for name in reference))
    err_norm = math.sqrt(sum(float(np.sum((control[name] - reference[name]).astype(np.float64) ** 2)) for name in control))
    return {
        "dtype": np.dtype(dtype).name,
        "steps": steps,
        "ordering": "E_update -> hard_source -> H_update",
        "classification": "exact Yee control; not a DCO result",
        "max_abs_error_per_component": errors,
        "global_relative_l2": err_norm / max(ref_norm, 1e-300),
        "max_analytic_pec_boundary_curl": boundary_max,
        "finite": all(np.isfinite(value).all() for value in control.values()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=128)
    parser.add_argument("--n", type=int, default=31)
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/p2_exact_control.json")
    args = parser.parse_args()
    result = {"schema": "pidon-p2-exact-control-v1", "float64": run(np.float64, args.n, args.steps),
              "float32": run(np.float32, args.n, args.steps)}
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

