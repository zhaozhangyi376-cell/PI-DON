"""Shared measurement and state contract for the stage-2 PI-DON solver.

The module contains no training loop.  Keeping the definitions here makes the
solver, its recorder, controls and tests use the same terminology instead of
retrofitting scientific claims from a trajectory JSON after the fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable, Sequence

import numpy as np
import torch


E0 = 1.0
Z0 = math.sqrt(4.0e-7 * math.pi / 8.8541878128e-12)
H0 = E0 / Z0


@dataclass
class FitRecord:
    """Result of one inner curl fit.

    ``n_updates`` counts actual ``optimizer.step`` calls.  ``n_evals`` counts
    complete forward residual evaluations, including the mandatory evaluation
    after the final update.  The residual fields are physical-unit SSE/MSE;
    ``loss_final`` is the registered stopping objective.
    """

    n_updates: int
    n_evals: int
    loss_initial: float
    loss_final: float
    sse: float
    mse: float
    target_ss: float
    passed: bool
    stop_reason: str
    elapsed_s: float
    prediction: list[torch.Tensor]
    loss_sum: float = 0.0
    target_count: int = 0
    n_lbfgs_steps: int = 0
    n_closures: int = 0

    def as_dict(self, include_prediction: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_prediction:
            data.pop("prediction", None)
        return data

    def __iter__(self):
        """Temporary compatibility with old diagnostic scripts.

        New code must use named fields.  The old fifth ``crop`` result was
        always ``None``.
        """
        yield self.n_updates
        yield self.loss_final
        yield self.loss_sum
        yield self.prediction
        yield None


@dataclass
class StepRecord:
    time_layer: int
    accepted: bool
    phase: str
    fit_H: FitRecord | None
    fit_E: FitRecord | None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("fit_H", "fit_E"):
            if data[key] is not None:
                data[key].pop("prediction", None)
        return data


def finite_scalar(value: float | torch.Tensor) -> bool:
    if isinstance(value, torch.Tensor):
        return bool(torch.isfinite(value).all().item())
    return math.isfinite(float(value))


def reached(final_loss: float, tolerance: float) -> bool:
    return finite_scalar(final_loss) and float(final_loss) < float(tolerance)


def all_finite(tensors: Iterable[torch.Tensor]) -> bool:
    return all(bool(torch.isfinite(t).all().item()) for t in tensors)


def component_offsets(kind: str) -> tuple[float, float, float]:
    """Yee locations in units of cell size for x/y/z components.

    This follows the array convention in ``fdtd.py``: normal components lie
    on the corresponding coordinate face, and tangential coordinates are at
    cell centres.  It is used for dual volumes and explicit probe alignment.
    """
    table = {
        "Ex": (0.5, 0.0, 0.0), "Ey": (0.0, 0.5, 0.0), "Ez": (0.0, 0.0, 0.5),
        "Hx": (0.0, 0.5, 0.5), "Hy": (0.5, 0.0, 0.5), "Hz": (0.5, 0.5, 0.0),
    }
    return table[kind]


def dual_volumes(shape: Sequence[int], offsets: Sequence[float], dxyz: Sequence[float]) -> np.ndarray:
    """Yee dual control volumes with half weights only on physical faces."""
    weights = np.ones(tuple(shape), dtype=np.float64)
    for axis, (size, offset) in enumerate(zip(shape, offsets)):
        if offset == 0.0 and size > 1:
            sl = [slice(None)] * 3
            sl[axis] = 0
            weights[tuple(sl)] *= 0.5
            sl[axis] = size - 1
            weights[tuple(sl)] *= 0.5
    return weights * float(np.prod(dxyz))


def component_metric(
    pred: torch.Tensor,
    ref: torch.Tensor,
    *,
    scale: float,
    dxyz: Sequence[float],
    offsets: Sequence[float],
) -> dict[str, float]:
    p = pred.detach().cpu().double().numpy() / scale
    r = ref.detach().cpu().double().numpy() / scale
    vol = dual_volumes(r.shape, offsets, dxyz)
    delta = p - r
    ref_ss = float(np.sum(vol * r * r))
    err_ss = float(np.sum(vol * delta * delta))
    denom_max = float(np.max(np.abs(r)))
    return {
        "weighted_l2_error": math.sqrt(err_ss),
        "weighted_ref_l2": math.sqrt(ref_ss),
        "relative_l2": math.sqrt(err_ss / ref_ss) if ref_ss > 0 else float("nan"),
        "nmae": float(np.mean(np.abs(delta)) / denom_max) if denom_max > 0 else float("nan"),
        "absolute_mae": float(np.mean(np.abs(delta))),
        "reference_max": denom_max,
    }


def six_component_metrics(
    E_pred: Sequence[torch.Tensor], H_pred: Sequence[torch.Tensor],
    E_ref: Sequence[torch.Tensor], H_ref: Sequence[torch.Tensor], dxyz: Sequence[float],
) -> dict[str, Any]:
    result: dict[str, Any] = {"components": {}}
    total_err = total_ref = 0.0
    for prefix, pred_group, ref_group, scale in (
        ("E", E_pred, E_ref, E0), ("H", H_pred, H_ref, H0),
    ):
        for index, (pred, ref) in enumerate(zip(pred_group, ref_group)):
            name = prefix + "xyz"[index]
            metric = component_metric(
                pred, ref, scale=scale, dxyz=dxyz, offsets=component_offsets(name)
            )
            result["components"][name] = metric
            total_err += metric["weighted_l2_error"] ** 2
            total_ref += metric["weighted_ref_l2"] ** 2
    result["global_weighted_relative_l2"] = (
        math.sqrt(total_err / total_ref) if total_ref > 0 else float("nan")
    )
    return result


def trilinear_sample(
    values: torch.Tensor, xyz_m: Sequence[float], dxyz: Sequence[float], offsets: Sequence[float]
) -> float:
    """Sample a staggered component at a physical coordinate without snapping.

    Points outside the component support are rejected rather than silently
    clamped, which prevents a source probe from becoming a boundary probe.
    """
    grid = [(x / d) - off for x, d, off in zip(xyz_m, dxyz, offsets)]
    lo = [math.floor(q) for q in grid]
    hi = [q + 1 for q in lo]
    shape = values.shape
    if any(a < 0 or b >= shape[i] for i, (a, b) in enumerate(zip(lo, hi))):
        raise ValueError(f"probe {tuple(xyz_m)} lies outside staggered support {tuple(shape)}")
    frac = [q - a for q, a in zip(grid, lo)]
    total = 0.0
    cpu = values.detach().cpu()
    for ix in (0, 1):
        for iy in (0, 1):
            for iz in (0, 1):
                weight = (frac[0] if ix else 1 - frac[0])
                weight *= (frac[1] if iy else 1 - frac[1])
                weight *= (frac[2] if iz else 1 - frac[2])
                total += weight * float(cpu[hi[0] if ix else lo[0], hi[1] if iy else lo[1], hi[2] if iz else lo[2]])
    return total


SOURCE_OUTSIDE_PROBES_CELLS = ((12.0, 12.0, 13.0), (8.0, 10.0, 12.0), (21.0, 19.0, 18.0))
