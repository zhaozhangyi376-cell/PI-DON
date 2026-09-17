from __future__ import annotations

import torch
from torch import nn


class ResidualBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.c1 = nn.Conv3d(c_in, c_out, 3, padding=1)
        self.c2 = nn.Conv3d(c_out, c_out, 3, padding=1)
        self.proj = nn.Conv3d(c_in, c_out, 1) if c_in != c_out else nn.Identity()
        self.act = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.c2(self.act(self.c1(x)))) + self.proj(x)


class DCO(nn.Module):
    """Two full encoders fused by Hadamard product, followed by a U-net decoder."""
    def __init__(self, levels: int = 4, base: int = 32):
        super().__init__()
        if levels < 1:
            raise ValueError("levels must be positive")
        channels = [base * (2 ** i) for i in range(levels)]
        self.levels = levels
        self.branch = nn.ModuleList()
        self.trunk = nn.ModuleList()
        c_in = 3
        for c_out in channels:
            self.branch.append(ResidualBlock(c_in, c_out))
            self.trunk.append(ResidualBlock(c_in, c_out))
            c_in = c_out
        self.pool = nn.MaxPool3d(2)
        self.up = nn.ModuleList()
        self.decoder = nn.ModuleList()
        for i in range(levels - 1, 0, -1):
            self.up.append(nn.ConvTranspose3d(channels[i], channels[i - 1], 2, stride=2))
            self.decoder.append(ResidualBlock(2 * channels[i - 1], channels[i - 1]))
        self.head = nn.Conv3d(channels[0], 3, 1)

    def forward(self, field: torch.Tensor, coords: torch.Tensor) -> torch.Tensor:
        branch, trunk = field, coords
        fused: list[torch.Tensor] = []
        for i in range(self.levels):
            if i:
                branch = self.pool(branch)
                trunk = self.pool(trunk)
            branch = self.branch[i](branch)
            trunk = self.trunk[i](trunk)
            fused.append(branch * trunk)
        x = fused[-1]
        for j, i in enumerate(range(self.levels - 1, 0, -1)):
            x = self.up[j](x)
            x = self.decoder[j](torch.cat([x, fused[i - 1]], dim=1))
        return self.head(x)

    def n_parameters(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())


def component_local_max_normalize(target: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    scale = target.abs().amax(dim=(2, 3, 4), keepdim=True).clamp_min(1e-12)
    return target / scale, scale
