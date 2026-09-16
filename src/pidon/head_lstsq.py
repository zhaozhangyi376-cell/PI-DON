"""One-shot CPU float64 least-squares fit for a direct DCO output head."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


from typing import Any

import torch


RCOND = 1e-12


def solve_component_head(feature: torch.Tensor, target_normalized: torch.Tensor) -> tuple[torch.Tensor, dict[str, Any]]:
    """Solve one `[channels, nx, ny, nz]` affine output map in CPU float64."""
    if feature.ndim != 4 or target_normalized.ndim != 3 or tuple(feature.shape[1:]) != tuple(target_normalized.shape):
        raise ValueError("feature/target support shapes differ")
    x = feature.detach().to(device="cpu", dtype=torch.float64).flatten(1).T.contiguous()
    y = target_normalized.detach().to(device="cpu", dtype=torch.float64).reshape(-1, 1).contiguous()
    x = torch.cat((x, torch.ones((x.shape[0], 1), dtype=x.dtype)), dim=1)
    fit = torch.linalg.lstsq(x, y, rcond=RCOND, driver="gelsd")
    residual = x @ fit.solution - y
    return fit.solution[:, 0], {"rank": int(fit.rank),
                                 "singular_values": fit.singular_values.detach().cpu().tolist(),
                                 "normalized_sse": float(residual.square().sum()),
                                 "samples": int(x.shape[0]), "columns": int(x.shape[1]), "rcond": RCOND}


def solve_head(feature: torch.Tensor, targets_normalized: list[torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor, list[dict[str, Any]]]:
    """Return direct-head weight/bias without mutating the production network."""
    if len(targets_normalized) != 3: raise ValueError("direct DCO head has exactly three components")
    beta, diagnostics = zip(*(solve_component_head(feature[:, :target.shape[0], :target.shape[1], :target.shape[2]], target)
                              for target in targets_normalized))
    weight = torch.stack([item[:-1] for item in beta]).reshape(3, feature.shape[0], 1, 1, 1)
    bias = torch.stack([item[-1] for item in beta])
    return weight, bias, list(diagnostics)


def clear_head_adam_state(optimizer: torch.optim.Optimizer, head: torch.nn.Conv3d) -> list[str]:
    """Remove all local Adam state for replaced head parameters only."""
    cleared = []
    for name, parameter in (("head.weight", head.weight), ("head.bias", head.bias)):
        if parameter in optimizer.state:
            optimizer.state.pop(parameter, None)
            cleared.append(name)
    return cleared
