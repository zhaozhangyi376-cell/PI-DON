"""
Diagnose why EXP 2 / EXP 3 failed -- WITHOUT retraining.  Takes ~2 minutes.

HYPOTHESIS
    The trunk is fed ABSOLUTE coordinates in mm.  Training at 16^3 with
    dx in [0.3, 0.8] mm means the trunk never sees a coordinate above
    15 * 0.8 = 12.0 mm.  Every failing test asked it to extrapolate:

        EXP 2 at 32^3, dx in [0.3,0.8]   -> up to 24.8 mm   (2.1x)
        EXP 2 at 48^3, dx in [0.3,0.8]   -> up to 37.6 mm   (3.1x)
        EXP 3 cavity 22.4 mm / 32 cells  ->      21.7 mm    (1.8x)

    If this is the cause, then holding the PHYSICAL EXTENT inside the training
    range while changing the number of cells should work fine, and pushing the
    extent out should fail -- independently of the cell count.

    That is exactly what this script separates.  It also explains why the paper
    did not hit the problem: it trained at 32^3 (extent 9.6-25.6 mm) and tested
    at a fixed 19.2 mm total extent, which sits inside that range.

USAGE
    py -3.11 diag_coords.py --ckpt dco_L3.pt
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse

import numpy as np
import torch

import dco as D
from gen_data import build as build_data


def run(net, device, n, d_mm, coord_mode, samples=3, seed=1234):
    """relative L2 at grid size n with a FIXED cell size d_mm (mm, isotropic)."""
    d_m = d_mm * 1e-3
    E, C, _ = build_data(samples, n, seed=seed, d_lo=d_m, d_hi=d_m)
    rs = []
    for s in range(samples):
        e = torch.from_numpy(E[s]).float().unsqueeze(0).to(device)
        x = D.make_coords(n, [d_mm] * 3, coord_mode, device=device)
        dd = torch.tensor([[d_mm] * 3], dtype=torch.float32, device=device)
        with torch.no_grad():
            eh, _, a, Lc = D.normalise(e, None, dd)
            pr = D.denormalise(net(eh, x), a, Lc)[0].cpu()
        rs.append(float(D.rel_l2(pr, torch.from_numpy(C[s]))))
    return float(np.mean(rs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="dco_L3.pt")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()

    dev = torch.device(a.device)
    ck = torch.load(a.ckpt, map_location=dev, weights_only=False)
    net = D.DCO(levels=ck["levels"], base=ck["base"]).to(dev)
    net.load_state_dict(ck["state"])
    net.eval()
    mode = ck.get("coords", "abs")
    ntr = ck["grid"]
    print(f"{a.ckpt}: trained at {ntr}^3, trunk coord encoding = {mode}")
    print(f"training cell sizes 0.3-0.8 mm  ->  trunk saw coordinates up to "
          f"{(ntr - 1) * 0.8:.1f} mm\n")

    print("A) FIX the cell size, VARY the grid  (extent grows -> extrapolation)")
    print("   n     dx(mm)   extent(mm)   relative L2")
    for n in (16, 24, 32, 48):
        r = run(net, dev, n, 0.6, mode)
        print(f"  {n:3d}     0.60     {(n - 1) * 0.6:6.1f}      {r:.3e}")

    print("\nB) FIX the extent near training, VARY the grid  (paper's protocol)")
    print("   the paper held total length at 19.2 mm and changed n; here we hold")
    print(f"   it at {(ntr - 1) * 0.6:.1f} mm, inside what this net was trained on")
    target = (ntr - 1) * 0.6
    print("   n     dx(mm)   extent(mm)   relative L2")
    for n in (16, 24, 32, 48):
        dx = target / (n - 1)
        flag = "" if 0.3 <= dx <= 0.8 else "   <- dx outside training range too"
        r = run(net, dev, n, dx, mode)
        print(f"  {n:3d}     {dx:.3f}    {(n - 1) * dx:6.1f}      {r:.3e}{flag}")

    print("\nC) FIX the grid at 32, VARY the extent  (isolates extent from n)")
    print("   n     dx(mm)   extent(mm)   relative L2")
    for dx in (0.20, 0.30, 0.40, 0.60, 0.80):
        r = run(net, dev, 32, dx, mode)
        print(f"   32     {dx:.2f}     {31 * dx:6.1f}      {r:.3e}")

    print("\nREAD IT LIKE THIS")
    print("  If B is much better than A at the same n, the grid COUNT was never")
    print("  the problem -- the physical EXTENT was, i.e. the trunk was being")
    print("  asked to extrapolate in absolute position.")
    print("  C should then show the error climbing monotonically with extent,")
    print("  with the knee near the training limit.")
    print("\n  Fix: retrain with  --coords centered  or  --coords cellsize")
    print("  (see dco.make_coords).  'cellsize' is exactly grid-size invariant.")


if __name__ == "__main__":
    main()
