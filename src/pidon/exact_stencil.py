"""
The exact curl is ONE convolution with twelve weights.  ~5 s, no GPU.

    python exact_stencil.py

WHY THIS MATTERS MORE THAN ANY OTHER NUMBER HERE
    Every difficulty this reproduction ran into -- the operator plateauing at
    3-5%, depth helping the metric while destroying dimension invariance, the
    divergence identity missing by five orders of magnitude, the closed loop
    dying around step 150 -- reads as a capacity or training-budget problem
    until you notice this:

        the exact Yee curl is a SINGLE 3x3x3 convolution with 12 non-zero
        weights, linear, no activation.

    It is not merely representable by the architecture, it is a strict subset
    of its very first layer.  So the exact answer sits inside the hypothesis
    space, and a 2.25M-parameter, three-level, GELU U-Net trained for hours
    lands 3-5% away from it.

    That is not a capacity problem and no amount of data or epochs fixes it in
    kind.  It says the machinery is aimed at the wrong target: on a uniform
    vacuum grid a learnt curl is strictly worse than the twelve numbers it is
    approximating.

WHERE A LEARNT OPERATOR COULD ACTUALLY EARN ITS KEEP
    Exactly where the twelve-weight stencil is NOT the right answer:
    inhomogeneous or dispersive media, subgridding and material interfaces,
    cells too coarse for the standard stencil, curved boundaries staircased
    onto a Cartesian grid.  There the correct local operator varies cell by
    cell and nobody has a closed form for it.  The constructive version of
    this critique is therefore not "don't learn operators" but "learn the
    CORRECTION to the exact stencil, not the operator" -- which also keeps
    div(curl) = 0 structural, because a correction that preserves the
    antisymmetry of the stencil preserves the identity.

CONVENTION
    Same staggering as gen_data.py, periodic wrap, so the comparison is
    against exactly the operator the rest of the code uses.
    PyTorch's conv3d is a CORRELATION: out[x] = sum_k W[k] * in[x + k - centre],
    so an offset of +1 in the difference is an index of centre+1 in W.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import numpy as np
import torch
import torch.nn as nn

SCRIPT_VERSION = "2026-09-09a"


def curl_exact(E, d):
    """The reference: gen_data's staggering, periodic.  (B,3,n,n,n) in/out."""
    Ex, Ey, Ez = E[:, 0], E[:, 1], E[:, 2]
    cx = (torch.roll(Ez, -1, 2) - Ez) / d - (torch.roll(Ey, -1, 3) - Ey) / d
    cy = (torch.roll(Ex, -1, 3) - Ex) / d - (torch.roll(Ez, -1, 1) - Ez) / d
    cz = (torch.roll(Ey, -1, 1) - Ey) / d - (torch.roll(Ex, -1, 2) - Ex) / d
    return torch.stack([cx, cy, cz], 1)


def yee_conv(d, dtype=torch.float64):
    """The same operator as a single Conv3d.  Returns the layer."""
    conv = nn.Conv3d(3, 3, 3, padding=1, padding_mode="circular",
                     bias=False).to(dtype)
    W = torch.zeros(3, 3, 3, 3, 3, dtype=dtype)
    c = 1                                            # kernel centre

    def w(c_out, c_in, off, val):
        W[c_out, c_in, c + off[0], c + off[1], c + off[2]] = val

    # cx = (Ez[j+1] - Ez[j])/d - (Ey[k+1] - Ey[k])/d
    w(0, 2, (0, 1, 0), 1 / d); w(0, 2, (0, 0, 0), -1 / d)
    w(0, 1, (0, 0, 1), -1 / d); w(0, 1, (0, 0, 0), 1 / d)
    # cy = (Ex[k+1] - Ex[k])/d - (Ez[i+1] - Ez[i])/d
    w(1, 0, (0, 0, 1), 1 / d); w(1, 0, (0, 0, 0), -1 / d)
    w(1, 2, (1, 0, 0), -1 / d); w(1, 2, (0, 0, 0), 1 / d)
    # cz = (Ey[i+1] - Ey[i])/d - (Ex[j+1] - Ex[j])/d
    w(2, 1, (1, 0, 0), 1 / d); w(2, 1, (0, 0, 0), -1 / d)
    w(2, 0, (0, 1, 0), -1 / d); w(2, 0, (0, 0, 0), 1 / d)
    conv.weight.data = W
    return conv


def main():
    print(f"[exact_stencil.py  version {SCRIPT_VERSION}]")
    torch.set_default_dtype(torch.float64)
    n, d = 12, 0.55e-3
    conv = yee_conv(d)
    W = conv.weight.data

    E = torch.randn(4, 3, n, n, n, dtype=torch.float64)
    with torch.no_grad():
        A, B = conv(E), curl_exact(E, d)
        rel = float((A - B).pow(2).sum().sqrt() / B.pow(2).sum().sqrt())

    nz = int((W != 0).sum())
    print(f"\n  one Conv3d(3,3,kernel=3) vs the exact Yee curl")
    print(f"    relative L2            {rel:.3e}")
    print(f"    non-zero weights       {nz} of {W.numel()}")
    print(f"    layers / activations   1 / none")

    dco_params = 2_251_000        # L=3, base=32, the net actually trained
    print(f"\n  the network we trained instead")
    print(f"    parameters             {dco_params/1e6:.2f}M  "
          f"({dco_params/nz:.0f}x the exact solution)")
    print(f"    best relative L2       ~1.7e-2 .. 5.2e-2 depending on the run")

    print(f"""
  READING
    The exact operator is not merely inside the hypothesis space, it is a
    subset of the FIRST LAYER.  A {dco_params/1e6:.2f}M-parameter non-linear network
    trained for hours settles {1.7e-2/rel if rel > 0 else float('inf'):.0e} times further from it than
    machine precision.

    So the plateau is not capacity and not data.  Every downstream symptom
    follows from it:
      depth hurts dimension invariance   the exact answer is ONE layer, so
                                         deeper is further away
      div(curl) misses by 1e5            the exact operator satisfies the
                                         identity structurally; a smooth
                                         approximation of it does not
      the closed loop dies near step 150 a 3% operator error applied 150 times
      more epochs help only slowly       SGD is approaching a point it cannot
                                         reach exactly

    On a uniform vacuum grid, a learnt curl is strictly worse than the twelve
    numbers it approximates.  A learnt operator can only pay for itself where
    those twelve numbers are NOT the right answer -- inhomogeneous or
    dispersive media, subgridding, material interfaces, cells too coarse for
    the standard stencil, staircased curved boundaries.  Hence: learn the
    CORRECTION to the stencil, not the operator.
""")


if __name__ == "__main__":
    main()
