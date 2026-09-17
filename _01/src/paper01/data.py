from __future__ import annotations

from typing import Any

import numpy as np


def spatial_coordinates(shape: tuple[int, int, int], cell_size_m: np.ndarray) -> np.ndarray:
    """Return physical point coordinates in millimetres, shaped (3,nx,ny,nz)."""
    d = np.asarray(cell_size_m, dtype=np.float64)
    axes = [np.arange(int(n), dtype=np.float64) * d[i] * 1e3 for i, n in enumerate(shape)]
    return np.stack(np.meshgrid(*axes, indexing="ij"), axis=0).astype(np.float32)


def draw_spec(rng: np.random.Generator, n_waves: int = 20,
              theta_cos_min: float = 0.15) -> dict[str, Any]:
    """Draw one documented plane-wave superposition.

    The direction is shared within a sample. That is an explicit project assumption,
    not a claim about unavailable author code.
    """
    cell = rng.uniform(0.3e-3, 0.8e-3, size=3)
    theta = float(rng.uniform(0.0, np.pi))
    while abs(np.cos(theta)) < theta_cos_min:
        theta = float(rng.uniform(0.0, np.pi))
    phi = float(rng.uniform(-np.pi, np.pi))
    khat = np.array([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta),
    ], dtype=np.float64)
    ks = rng.uniform(0.0, 1048.0, size=int(n_waves))

    # Preserve the paper's Ex/Ey draw and compute Ez from its Eq. (4). The
    # unreported rejection around cos(theta)=0 is frozen in the contract.
    amplitudes = np.empty((int(n_waves), 3), dtype=np.float64)
    amplitudes[:, :2] = rng.uniform(0.0, 5.0, size=(int(n_waves), 2))
    amplitudes[:, 2] = -(
        khat[0] * amplitudes[:, 0] + khat[1] * amplitudes[:, 1]
    ) / khat[2]
    return {
        "cell_size_m": cell.tolist(),
        "theta": theta,
        "phi": phi,
        "khat": khat.tolist(),
        "ks_rad_per_m": ks.tolist(),
        "amplitudes": amplitudes.tolist(),
        "n_waves": int(n_waves),
        "amplitude_construction": "paper_eq4_Ez_from_Ex_Ey_draw",
        "theta_rejection_abs_cos_min": float(theta_cos_min),
    }


def sample_from_spec(spec: dict[str, Any], shape: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate E and its analytic curl for a real cosine plane-wave sum."""
    d = np.asarray(spec["cell_size_m"], dtype=np.float64)
    coords_m = spatial_coordinates(shape, d).astype(np.float64) * 1e-3
    khat = np.asarray(spec["khat"], dtype=np.float64)
    ks = np.asarray(spec["ks_rad_per_m"], dtype=np.float64)
    amplitudes = np.asarray(spec["amplitudes"], dtype=np.float64)
    field = np.zeros((3, *shape), dtype=np.float64)
    curl = np.zeros_like(field)
    for k, amplitude in zip(ks, amplitudes):
        kvec = k * khat
        phase = np.einsum("i,ixyz->xyz", kvec, coords_m)
        field += amplitude[:, None, None, None] * np.cos(phase)[None]
        curl += -np.cross(kvec, amplitude)[:, None, None, None] * np.sin(phase)[None]
    return field.astype(np.float32), curl.astype(np.float32)


def generate_dataset(samples: int, shape: tuple[int, int, int], seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    fields = np.empty((samples, 3, *shape), dtype=np.float32)
    curls = np.empty_like(fields)
    coords = np.empty_like(fields)
    specs: list[dict[str, Any]] = []
    for i in range(samples):
        spec = draw_spec(rng)
        fields[i], curls[i] = sample_from_spec(spec, shape)
        coords[i] = spatial_coordinates(shape, np.asarray(spec["cell_size_m"]))
        specs.append(spec)
    return fields, curls, coords, specs
