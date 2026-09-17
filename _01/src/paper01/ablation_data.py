from __future__ import annotations

from typing import Any

import numpy as np

from .data import draw_spec, sample_from_spec, spatial_coordinates


VARIANTS = ("baseline", "theta_min_0p5", "ez_cap3", "projected_amp")


def ez_amplification(spec: dict[str, Any]) -> float:
    amplitudes = np.asarray(spec["amplitudes"], dtype=np.float64)
    xy = max(float(np.max(np.abs(amplitudes[:, :2]))), 1e-30)
    return float(np.max(np.abs(amplitudes[:, 2])) / xy)


def projected_amplitude_spec(rng: np.random.Generator, n_waves: int = 20, theta_cos_min: float = 0.15) -> dict[str, Any]:
    spec = draw_spec(rng, n_waves=n_waves, theta_cos_min=theta_cos_min)
    khat = np.asarray(spec["khat"], dtype=np.float64)
    raw = rng.uniform(0.0, 5.0, size=(int(n_waves), 3))
    amplitudes = raw - (raw @ khat)[:, None] * khat[None, :]
    spec["amplitudes"] = amplitudes.tolist()
    spec["amplitude_construction"] = "diagnostic_project_full_vector_perpendicular_to_k"
    spec["diagnostic_not_paper_literal"] = True
    return spec


def draw_variant_spec(rng: np.random.Generator, variant: str) -> dict[str, Any]:
    if variant == "baseline":
        spec = draw_spec(rng, theta_cos_min=0.15)
        spec["ablation_variant"] = variant
        return spec
    if variant == "theta_min_0p5":
        spec = draw_spec(rng, theta_cos_min=0.5)
        spec["ablation_variant"] = variant
        return spec
    if variant == "ez_cap3":
        attempts = 0
        while True:
            attempts += 1
            spec = draw_spec(rng, theta_cos_min=0.15)
            if ez_amplification(spec) <= 3.0:
                spec["ablation_variant"] = variant
                spec["ez_cap"] = 3.0
                spec["rejection_attempts"] = attempts
                return spec
    if variant == "projected_amp":
        spec = projected_amplitude_spec(rng, theta_cos_min=0.15)
        spec["ablation_variant"] = variant
        return spec
    raise ValueError(f"unknown ablation variant {variant!r}")


def generate_variant_dataset(
    samples: int,
    shape: tuple[int, int, int],
    seed: int,
    variant: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown ablation variant {variant!r}")
    rng = np.random.default_rng(seed)
    fields = np.empty((samples, 3, *shape), dtype=np.float32)
    curls = np.empty_like(fields)
    coords = np.empty_like(fields)
    specs: list[dict[str, Any]] = []
    for i in range(samples):
        spec = draw_variant_spec(rng, variant)
        fields[i], curls[i] = sample_from_spec(spec, shape)
        coords[i] = spatial_coordinates(shape, np.asarray(spec["cell_size_m"]))
        specs.append(spec)
    return fields, curls, coords, specs


def variant_contract_stats(specs: list[dict[str, Any]]) -> dict[str, Any]:
    if not specs:
        return {}
    abs_cos = [abs(float(np.cos(float(spec["theta"])))) for spec in specs]
    ez = [ez_amplification(spec) for spec in specs]
    attempts = [int(spec.get("rejection_attempts", 1)) for spec in specs]
    return {
        "abs_cos_theta_min": float(np.min(abs_cos)),
        "abs_cos_theta_mean": float(np.mean(abs_cos)),
        "ez_amplification_mean": float(np.mean(ez)),
        "ez_amplification_p90": float(np.percentile(ez, 90)),
        "ez_amplification_max": float(np.max(ez)),
        "rejection_attempts_mean": float(np.mean(attempts)),
        "diagnostic_not_paper_literal": bool(any(spec.get("diagnostic_not_paper_literal") for spec in specs)),
    }
