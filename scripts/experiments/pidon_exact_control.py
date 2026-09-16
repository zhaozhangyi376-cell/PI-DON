"""Production-path exact-Yee controls for the PI-DON stage-2 transaction.

These controls certify measurement, ordering and recovery plumbing. They do
not use a DCO output and are deliberately labelled ``control_only``.
"""

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
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

import fdtd
from pidon_contract import (FitRecord, StepRecord, SOURCE_OUTSIDE_PROBES_CELLS,
                            six_component_metrics, trilinear_sample)
from pidon_recording import RunRecorder, sha256_file
from pidon_solve import (Solver, _checkpoint_payload, _restore_reference,
                         formal_run_identity, to_t)


ROOT = PROJECT_ROOT
CONTROL_SOURCE_FILES = ("pidon_exact_control.py", "pidon_solve.py", "pidon_contract.py",
                        "pidon_recording.py", "fdtd.py", "dco.py")


def json_safe(value):
    """JSON has no NaN; undefined weak-field ratios are explicitly null."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def control_args(dtype: torch.dtype, mode: str = "exact") -> SimpleNamespace:
    dtype_name = "float64" if dtype == torch.float64 else "float32"
    return SimpleNamespace(
        n=31, side=0.05, dt=3.075e-12, init="random", coords="cellsize", norm="rms",
        levels=2, base=2, lr=1e-4, separate_nets=True, h_scale=1.0, h_output_scale=1.0,
        h_shift=False, tol_mode="rel", component_rel=False, tol=1e-4, max_inner=0,
        grad_clip=0.0, inner_time_budget_s=0.0, strict_stop=True,
        reset_opt_each_step=False, lbfgs_closures=0, lbfgs_lr=1.0, lbfgs_history=10,
        lbfgs_time_budget_s=0.0, torch_dtype=dtype_name, source_mode="hard",
        fmax=15e9, seed=20260913, control_mode=mode,
    )


class ProductionControlSolver(Solver):
    """Exact/negative curl replacement while retaining the real Solver.step path."""

    def inner_train(self, field, target, which="shared"):
        prediction = []
        support_rows = []
        for part in target:
            shape = tuple(min(size, self.n) for size in part.shape)
            if self.a.control_mode == "exact":
                prediction.append(part[:shape[0], :shape[1], :shape[2]].clone())
            elif self.a.control_mode in ("zero", "hard_source_only"):
                prediction.append(torch.zeros(shape, dtype=self.dtype, device=self.dev))
            else:
                raise ValueError(f"unknown control mode {self.a.control_mode}")
        for index, (part, pred) in enumerate(zip(target, prediction)):
            boundary_extra = int(part.numel() - pred.numel())
            invalid_uncovered = 0
            if boundary_extra:
                # Only the normal high PEC face is outside the DCO cube.
                permitted = which == "E" and part.shape[index] == self.n + 1
                high = [slice(None)] * 3
                high[index] = self.n
                zero_on_boundary = bool(torch.all(part[tuple(high)] == 0).item()) if permitted else False
                if not permitted or not zero_on_boundary or boundary_extra != part[tuple(high)].numel():
                    invalid_uncovered = boundary_extra
            support_rows.append({"component": index, "target_count": int(part.numel()),
                                 "learned_count": int(pred.numel()), "boundary_extra_count": boundary_extra,
                                 "uncovered_nonboundary_count": invalid_uncovered})
        self.last_control_support = getattr(self, "last_control_support", {})
        self.last_control_support[which] = support_rows
        target_ss = float(sum(part.pow(2).sum() for part in target))
        error = float(sum((p - t[:p.shape[0], :p.shape[1], :p.shape[2]]).pow(2).sum()
                          for p, t in zip(prediction, target)))
        return FitRecord(0, 1, error, error, error,
                         error / max(sum(part.numel() for part in prediction), 1), target_ss,
                         True, "exact_yee_control", 0.0, prediction, 0.0,
                         sum(part.numel() for part in prediction),
                         residual_ratio=(error / target_ss if target_ss else None),
                         residual_rule="exact_yee_control")

    def step(self, g_t):
        """Keep the hard-source-only negative independent from zero curl.

        It still invokes both production fitting roles so the audit can count
        the transaction interface, but constructs its six fields afresh from
        the hard source instead of reusing the zero-curl update branch.
        """
        if self.a.control_mode != "hard_source_only":
            return super().step(g_t)
        fit_h = self.inner_train(self.H, self.yee_curl_H(), "H")
        fit_e = self.inner_train(self.E, self.yee_curl_E(), "E")
        self.E = [torch.zeros_like(part) for part in self.E]
        self.H = [torch.zeros_like(part) for part in self.H]
        c = self.n // 2
        self.E[2][c, c, c] = g_t
        self.apply_pec()
        record = StepRecord(self.current_time_layer, True, "hard_source_only", fit_h, fit_e)
        self.accepted_steps += 1
        self.current_time_layer += 1
        return record


def _reference_tensors(ref, solver, h_override=None):
    h_arrays = h_override if h_override is not None else (ref.Hx, ref.Hy, ref.Hz)
    # A float32 control is deliberately compared with the independent float64
    # reference.  Casting it down would make the check a float32-vs-float32
    # self-comparison and hide its roundoff error.
    return ([to_t(getattr(ref, name), solver.dev, torch.float64) for name in ("Ex", "Ey", "Ez")],
            [to_t(array, solver.dev, torch.float64) for array in h_arrays])


def _probes(solver, reference_e):
    dxyz = (solver.cav.dx, solver.cav.dy, solver.cav.dz)
    rows = []
    for cells in SOURCE_OUTSIDE_PROBES_CELLS:
        xyz = tuple(c * d for c, d in zip(cells, dxyz))
        rows.append({"cells": cells, "xyz_m": xyz,
                     "dut_Ez": trilinear_sample(solver.E[2], xyz, dxyz, (0, 0, 0.5)),
                     "ref_Ez": trilinear_sample(reference_e[2], xyz, dxyz, (0, 0, 0.5))})
    return rows


def _copy_source_snapshot(out_dir: Path):
    snapshot = out_dir / "source_snapshot"
    snapshot.mkdir(exist_ok=False)
    hashes = {}
    for name in CONTROL_SOURCE_FILES:
        source = ROOT / name
        destination = snapshot / name
        shutil.copy2(source, destination)
        hashes[name] = sha256_file(destination)
    return hashes


def _metric_gate(result, threshold):
    return (result["finite"] and result["max_global_relative_l2"] <= threshold and
            result["max_probe_abs_error"] <= threshold and
            result["max_fixed_amplitude_error"] <= threshold)


def run(dtype, n=31, steps=128, side=0.05, dt=3.075e-12, mode="exact", *,
        out_dir: str | Path | None = None, resume_after: int | None = None,
        wrong_h_half: bool = False):
    """Run production transactions with optional checkpoint/recovery.

    The FDTD reference remains float64.  A wrong-H-half diagnostic compares
    current E to H from the preceding reference half step.
    """
    if n != 31 or side != 0.05 or dt != 3.075e-12:
        raise ValueError("A2 exact control is frozen at n=31, side=.05, dt=3.075e-12")
    is_float64 = dtype in (torch.float64, np.float64, np.dtype(np.float64))
    torch_dtype = torch.float64 if is_float64 else torch.float32
    args = control_args(torch_dtype, mode)
    solver = ProductionControlSolver(args, "cpu")
    reference = fdtd.PECCavity(side=side, n=n, dt=dt)  # independent double reference
    source = fdtd.source_waveform(steps, dt, args.fmax, "gauss")
    c = n // 2
    recorder = None
    identity = formal_run_identity(args)
    source_snapshot_hashes = None
    if out_dir is not None:
        out_path = Path(out_dir)
        recorder = RunRecorder(out_path, {
            "schema": "pidon-production-control-v3", "classification": "control_only",
            "control_mode": mode, "wrong_h_half": wrong_h_half, "config": vars(args).copy(),
            "reference_dtype": "float64", **identity,
        }, mode="new")
        source_snapshot_hashes = _copy_source_snapshot(out_path)
    rows, worst_rel, worst_fixed, worst_step, max_probe_abs = [], 0.0, 0.0, 0, 0.0
    restored_at = None
    for step, value in enumerate(source):
        old_h = (reference.Hx.copy(), reference.Hy.copy(), reference.Hz.copy())
        record = solver.step(float(value))
        if not record.accepted:
            raise RuntimeError(f"control stopped at {step}: {record.reason}")
        reference.step_e_source_h(src_value=float(value), src_idx=(c, c, c))
        ref_e, ref_h = _reference_tensors(reference, solver, old_h if wrong_h_half else None)
        metric = six_component_metrics(solver.E, solver.H, ref_e, ref_h,
                                       (reference.dx, reference.dy, reference.dz),
                                       source_ez_index=(c, c, c))
        probes = _probes(solver, ref_e)
        probe_error = max((abs(row["dut_Ez"] - row["ref_Ez"]) for row in probes), default=0.0)
        relative = metric["global_weighted_relative_l2"]
        fixed = metric["fixed_amplitude_error"]
        if math.isfinite(relative) and relative > worst_rel:
            worst_rel, worst_step = relative, step
        worst_fixed = max(worst_fixed, fixed)
        max_probe_abs = max(max_probe_abs, probe_error)
        row = {
            "sequence_kind": "accepted_step", "step": step, "accepted_steps": solver.accepted_steps,
            "phase": record.phase, "accepted": True,
            "fit_H": record.fit_H.as_dict(), "fit_E": record.fit_E.as_dict(),
            "accepted_field_metrics": metric, "source_outside_probes": probes,
            "source_probe_Ez": {"dut": float(solver.E[2][c, c, c]), "ref": float(reference.Ez[c, c, c])},
            "recovery_eligible": True,
        }
        rows.append(row)
        if recorder is not None:
            recorder.append(json_safe(row))
        if recorder is not None and resume_after is not None and solver.accepted_steps == resume_after:
            payload = _checkpoint_payload(solver, reference, requested_steps=steps, source_index=step + 1)
            checkpoint_path = recorder.rolling_checkpoint(payload)
            # Destroy the in-memory objects and restore the actual bytes that
            # made it to disk; an in-memory payload is not recovery evidence.
            disk_payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            solver = ProductionControlSolver(args, "cpu")
            solver.load_state_payload(disk_payload)
            reference = fdtd.PECCavity(side=side, n=n, dt=dt)
            _restore_reference(reference, disk_payload["reference"])
            recorder = RunRecorder(out_dir, {
                "schema": "pidon-production-control-v3", "classification": "control_only",
                "control_mode": mode, "wrong_h_half": wrong_h_half, "config": vars(args).copy(),
                "reference_dtype": "float64", **identity,
            }, mode="resume")
            restored_at = step + 1
    if recorder is not None:
        recorder.rolling_checkpoint(_checkpoint_payload(solver, reference, requested_steps=steps, source_index=steps))
    finite = all(bool(torch.isfinite(part).all()) for part in solver.E + solver.H)
    result = json_safe({
        "schema": "pidon-production-control-v3", "dtype": "float64" if is_float64 else "float32",
        "steps": steps, "mode": mode, "wrong_h_half": wrong_h_half,
        "classification": "exact Yee control; not a DCO result", "control_only": True,
        "ordering": "Solver.step: curl-H -> E update -> hard source -> curl-E -> H update",
        "reference_dtype": "float64", "finite": finite, "restored_at_accepted_step": restored_at,
        "max_global_relative_l2": worst_rel, "max_fixed_amplitude_error": worst_fixed,
        "max_probe_abs_error": max_probe_abs, "worst_step": worst_step, "rows": rows,
        "support": {"from_real_masks": True, "curl_support": solver.last_control_support,
                    "uncovered": sum(row["uncovered_nonboundary_count"]
                                      for group in solver.last_control_support.values() for row in group),
                    "last_step_components": rows[-1]["accepted_field_metrics"]["components"],
                    "hard_source_excluded": True},
        "identity": identity, "source_snapshot_hashes": source_snapshot_hashes,
    })
    threshold = 1e-10 if torch_dtype == torch.float64 else 1e-4
    result["field_gate_threshold"] = threshold
    result["field_gate_pass"] = _metric_gate(result, threshold)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=128)
    parser.add_argument("--out", default="evidence/gpt6_plan_v3/A2_exact_control.json")
    parser.add_argument("--runs-dir", default="evidence/gpt6_plan_v3/A2_control_runs")
    args = parser.parse_args()
    base = Path(args.runs_dir)
    result = {
        "float64": run(np.float64, steps=args.steps, out_dir=base / "float64_exact", resume_after=64),
        "float32": run(np.float32, steps=args.steps, out_dir=base / "float32_exact", resume_after=64),
        "hard_source_only_negative": run(np.float64, steps=args.steps, mode="hard_source_only",
                                           out_dir=base / "hard_source_only"),
        "wrong_h_half_negative": run(np.float64, steps=args.steps, mode="exact",
                                      out_dir=base / "wrong_h_half", wrong_h_half=True),
    }
    result["negative_controls_rejected"] = all(not result[key]["field_gate_pass"] for key in
                                               ("hard_source_only_negative", "wrong_h_half_negative"))
    result["exact_controls_pass"] = result["float64"]["field_gate_pass"] and result["float32"]["field_gate_pass"]
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out": str(output), "float64_pass": result["float64"]["field_gate_pass"],
                      "float32_pass": result["float32"]["field_gate_pass"],
                      "negative_rejected": result["negative_controls_rejected"]}, ensure_ascii=False))
    if not (result["exact_controls_pass"] and result["negative_controls_rejected"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
