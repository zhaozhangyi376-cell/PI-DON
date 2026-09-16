"""Stream the registered 8192-step double-precision Yee reference cache."""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import fdtd
from pidon_contract import (E0, H0, SOURCE_OUTSIDE_PROBES_CELLS, component_offsets,
                            dual_volumes)
from pidon_recording import sha256_file, source_hashes


ROOT = PROJECT_ROOT
NAMES = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")


def _sample_numpy(values, xyz_m, dxyz, offsets):
    grid = [(x / d) - off for x, d, off in zip(xyz_m, dxyz, offsets)]
    lo = [int(np.floor(q)) for q in grid]
    hi = [q + 1 for q in lo]
    if any(a < 0 or b >= values.shape[i] for i, (a, b) in enumerate(zip(lo, hi))):
        raise ValueError(f"probe {xyz_m} lies outside {values.shape}")
    frac = [q - a for q, a in zip(grid, lo)]
    result = 0.0
    for ix in (0, 1):
        for iy in (0, 1):
            for iz in (0, 1):
                weight = (frac[0] if ix else 1 - frac[0])
                weight *= frac[1] if iy else 1 - frac[1]
                weight *= frac[2] if iz else 1 - frac[2]
                result += weight * float(values[hi[0] if ix else lo[0], hi[1] if iy else lo[1], hi[2] if iz else lo[2]])
    return result


def protocol(n, side, dt, steps, fmax):
    document = {"n": n, "side": side, "dt": dt, "steps": steps, "fmax": fmax,
                "source_mode": "hard", "source_index": (n // 2, n // 2, n // 2),
                "source_hashes": source_hashes(ROOT)}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"protocol": document, "protocol_hash": hashlib.sha256(encoded).hexdigest()}


def build(n=31, side=0.05, dt=3.075e-12, steps=8192, fmax=15e9):
    if (n, side, dt, steps) != (31, 0.05, 3.075e-12, 8192):
        raise ValueError("reference cache is registered only for n=31, side=.05, dt=3.075e-12, steps=8192")
    reference = fdtd.PECCavity(n=n, side=side, dt=dt)
    dxyz = (reference.dx, reference.dy, reference.dz)
    source = fdtd.source_waveform(steps, dt, fmax, "gauss")
    weights = {name: dual_volumes(getattr(reference, name).shape, component_offsets(name), dxyz)
               for name in NAMES}
    scales = {name: E0 if name[0] == "E" else H0 for name in NAMES}
    peaks = {name: 0.0 for name in NAMES}
    group_energy_peaks = {"E": 0.0, "H": 0.0, "all_six": 0.0}
    probes = np.zeros((steps, len(SOURCE_OUTSIDE_PROBES_CELLS)), dtype=np.float64)
    snapshots = {}
    for step, amplitude in enumerate(source, start=1):
        reference.step_e_source_h(src_value=float(amplitude), src_idx=(n // 2, n // 2, n // 2))
        energy = {"E": 0.0, "H": 0.0}
        for name in NAMES:
            values = getattr(reference, name)
            peaks[name] = max(peaks[name], float(np.max(np.abs(values))))
            energy[name[0]] += float(np.sum(weights[name] * (values / scales[name]) ** 2))
        group_energy_peaks["E"] = max(group_energy_peaks["E"], energy["E"])
        group_energy_peaks["H"] = max(group_energy_peaks["H"], energy["H"])
        group_energy_peaks["all_six"] = max(group_energy_peaks["all_six"], energy["E"] + energy["H"])
        for i, cells in enumerate(SOURCE_OUTSIDE_PROBES_CELLS):
            probes[step - 1, i] = _sample_numpy(reference.Ez, tuple(q * d for q, d in zip(cells, dxyz)),
                                                 dxyz, component_offsets("Ez"))
        if step in (128, 1024, 8192):
            for name in NAMES:
                snapshots[f"step{step:04d}_{name}"] = getattr(reference, name).copy()
    return {
        "schema": "pidon-reference-cache-v3", "classification": "double_precision_Yee_reference_not_DCO",
        **protocol(n, side, dt, steps, fmax), "component_abs_peaks": peaks,
        "group_weighted_energy_peaks": group_energy_peaks,
        "Ez_spacetime_abs_peak": peaks["Ez"], "probe_cells": SOURCE_OUTSIDE_PROBES_CELLS,
        "probe_abs_peaks": [float(np.max(np.abs(probes[:, i]))) for i in range(probes.shape[1])],
        "probes": probes, "snapshots": snapshots,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/gpt6_plan_v3/reference_cache.json")
    parser.add_argument("--snapshots", default="evidence/gpt6_plan_v3/reference_cache_snapshots.npz")
    args = parser.parse_args()
    result = build()
    snapshots = result.pop("snapshots")
    probes = result.pop("probes")
    snapshot_path = Path(args.snapshots)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(snapshot_path, probes=probes, **snapshots)
    result["snapshot_npz"] = str(snapshot_path).replace("\\", "/")
    result["snapshot_sha256"] = sha256_file(snapshot_path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out": str(out), "protocol_hash": result["protocol_hash"],
                      "snapshot_sha256": result["snapshot_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
