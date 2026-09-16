"""Numerical raw checks for the exact path used by mechanism_decision_v1."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import json
from pathlib import Path

import numpy as np

import fdtd
from pidon_recording import atomic_json_save, sha256_file, source_hashes


ROOT = PROJECT_ROOT
OUT = ROOT / "evidence" / "mechanism_decision_v1"


def linear_curl_checks(n: int = 5, d: float = 0.25) -> dict:
    # Ex=z, Ey=x, Ez=y gives curl(E)=(1,1,1) at the three H locations.
    x_e = np.arange(n + 1)[:, None, None] * d
    y_e = np.arange(n + 1)[None, :, None] * d
    z_e = np.arange(n + 1)[None, None, :] * d
    ex = np.broadcast_to(z_e, (n, n + 1, n + 1)).copy()
    ey = np.broadcast_to(x_e, (n + 1, n, n + 1)).copy()
    ez = np.broadcast_to(y_e, (n + 1, n + 1, n)).copy()
    ce = fdtd.curl_E(ex, ey, ez, d, d, d)
    # Hx=z, Hy=x, Hz=y gives curl(H)=(1,1,1) on interior E positions.
    hx = np.broadcast_to(z_e[:, :, :n], (n + 1, n, n)).copy()
    hy = np.broadcast_to(x_e[:n, :, :], (n, n + 1, n)).copy()
    hz = np.broadcast_to(y_e[:, :n, :], (n, n, n + 1)).copy()
    ch = fdtd.curl_H(hx, hy, hz, d, d, d)
    constant = fdtd.curl_E(np.ones_like(ex), np.ones_like(ey), np.ones_like(ez), d, d, d)
    return {
        "curl_E_linear_max_abs_error": [float(np.max(np.abs(x - 1.0))) for x in ce],
        "curl_H_linear_max_abs_error": [float(np.max(np.abs(x - 1.0))) for x in ch],
        "curl_E_constant_max_abs": [float(np.max(np.abs(x))) for x in constant],
    }


def plane_wave_symbol_check(n: int = 32, d: float = 1.0e-3, k: float = 300.0) -> dict:
    # Ey=cos(kx): curl(E)_z must have the analytic negative sign.  The Yee
    # amplitude has its known 2sin(kd/2)/d discrete symbol.
    x = np.arange(n + 1)[:, None, None] * d
    ex = np.zeros((n, n + 1, n + 1))
    ey = np.broadcast_to(np.cos(k * x), (n + 1, n, n + 1)).copy()
    ez = np.zeros((n + 1, n + 1, n))
    cz = fdtd.curl_E(ex, ey, ez, d, d, d)[2]
    xh = (np.arange(n) + 0.5)[:, None, None] * d
    expected_discrete = -(2.0 * np.sin(k * d / 2.0) / d) * np.sin(k * xh)
    expected_analytic = -k * np.sin(k * xh)
    return {
        "k_rad_per_m": k,
        "yee_symbol_rad_per_m": float(2.0 * np.sin(k * d / 2.0) / d),
        "analytic_symbol_rad_per_m": k,
        "max_abs_against_discrete_symbol": float(np.max(np.abs(cz - expected_discrete))),
        "max_abs_against_analytic_derivative": float(np.max(np.abs(cz - expected_analytic))),
        "sign_at_first_nonzero": float(np.sign(cz[1, 0, 0])),
    }


def main() -> None:
    if not (OUT / "protocol.json").is_file():
        raise FileNotFoundError("run mechanism_decision_init.py first")
    result = {
        "schema": "pidon-mechanism-path-check-v1",
        "source_hashes": source_hashes(ROOT),
        "protocol_sha256": sha256_file(OUT / "protocol.json"),
        "linear": linear_curl_checks(),
        "plane_wave": plane_wave_symbol_check(),
        "interpretation": {
            "analytic_and_yee_are_distinct": True,
            "exact_yee_is_interface_control_not_dco_score": True,
            "all_reported_values_are_raw_operator_checks": True,
        },
    }
    if any(value > 1e-12 for value in result["linear"]["curl_E_linear_max_abs_error"] + result["linear"]["curl_H_linear_max_abs_error"] + result["linear"]["curl_E_constant_max_abs"]):
        raise AssertionError("Yee linear/constant path check failed")
    if result["plane_wave"]["max_abs_against_discrete_symbol"] > 1e-10:
        raise AssertionError("discrete plane-wave symbol check failed")
    if result["plane_wave"]["sign_at_first_nonzero"] >= 0.0:
        raise AssertionError("plane-wave curl sign is not the expected negative sign")
    atomic_json_save(result, OUT / "path_check_raw.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
