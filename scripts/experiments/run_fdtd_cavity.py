"""
Stage 1 -- FDTD reference cavity, and the pure-physics validation slide.

Reproduces the paper's section IV-A cavity (50 mm cube, 32 cells, air, PEC on
all six faces, Gaussian Ez point source) and checks the resonant frequencies
against Table II.  No machine learning here at all -- this is the ground truth
everything else is measured against, so run it first and make sure it passes.

TWO THINGS THE PAPER GETS WRONG / LEAVES OUT, BOTH FOUND BY RUNNING THIS:

 1. dt = 3.075e-12 s (quoted in section IV-A) EXCEEDS the Courant limit.
    dx = 50/32 = 1.5625 mm  ->  dt_CFL = dx/(c*sqrt3) = 3.009e-12 s.
    The quoted value is 1.022 x the limit, i.e. marginally unstable.
    We use 0.99 * dt_CFL = 2.979e-12 s.

 2. A source at the EXACT centre of the cavity cannot excite TE211, TE221 or
    TE321 -- the centre is a node of every mode with an even index.  Yet all
    three appear in Table II.  Put the source slightly off-centre (we use cell
    (15,14,13)) and all five modes show up.  The paper says only "placed at the
    center of the cube".

 3. Frequency resolution: 8192 steps x 2.98 ps = 24 ns -> 41 MHz per raw FFT
    bin, far too coarse for the 3-decimal GHz figures in Table II.  We
    zero-pad to 2^20 and parabolic-interpolate the peak.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import time

import numpy as np

import fdtd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", type=float, default=50.0, help="cavity side, mm")
    ap.add_argument("--n", type=int, default=32, help="cells per direction")
    ap.add_argument("--steps", type=int, default=8192, help="paper: 8192")
    ap.add_argument("--src", type=int, nargs=3, default=[15, 14, 13],
                    help="source cell (OFF-centre on purpose, see docstring)")
    ap.add_argument("--probe", type=int, nargs=3, default=[12, 12, 13],
                    help="probe cell (paper samples Ez at 12,12,13)")
    ap.add_argument("--src-mode", choices=["hard", "add"], default="hard",
                    help="paper: 'setting Ez' = hard")
    ap.add_argument("--fmax", type=float, default=15.0, help="pulse bandwidth, GHz")
    ap.add_argument("--out", default="fdtd_cavity.npz")
    a = ap.parse_args()

    side = a.side * 1e-3
    cav = fdtd.PECCavity(side=side, n=a.n)
    dx = side / a.n
    dt_paper = 3.075e-12
    dt_cfl = fdtd.cfl_dt(dx, dx, dx, safety=1.0)

    print(f"cavity {a.side} mm / {a.n} cells   dx = {dx * 1e3:.4f} mm")
    print(f"  dt used      = {cav.dt * 1e12:.4f} ps   (0.99 x CFL)")
    print(f"  dt CFL limit = {dt_cfl * 1e12:.4f} ps")
    print(f"  dt in paper  = {dt_paper * 1e12:.4f} ps  "
          f"-> {dt_paper / dt_cfl:.3f} x CFL  <-- UNSTABLE as quoted")

    g, tau, t0 = fdtd.gaussian_pulse(a.steps, cav.dt, f_max=a.fmax * 1e9)
    rec = np.zeros(a.steps)
    src, prb = tuple(a.src), tuple(a.probe)

    t_start = time.time()
    for n in range(a.steps):
        cav.step(src_value=g[n], src_idx=src, src_mode=a.src_mode)
        rec[n] = cav.Ez[prb]
    wall = time.time() - t_start
    print(f"  {a.steps} steps in {wall:.1f} s   "
          f"({wall / a.steps * 1e3:.2f} ms/step)   |Ez|max = {np.abs(rec).max():.3e}")
    if not np.isfinite(rec).all() or np.abs(rec).max() > 1e6:
        print("  *** DIVERGED -- check dt ***")
        return

    # ---- resonances -------------------------------------------------------
    kept, f, X = fdtd.spectrum_peaks(rec, cav.dt, f_lo=3e9, f_hi=12.5e9,
                                     pad=1 << 20, n_peaks=14, min_sep=250e6)

    ana = fdtd.analytic_modes(side=side)
    paper_fdtd = {(1, 1, 0): 4.242, (2, 1, 1): 7.344, (2, 2, 1): 8.997,
                  (3, 1, 0): 9.482, (3, 2, 1): 11.223}

    print("\n  mode      analytic     this FDTD    err %     paper FDTD")
    print("  " + "-" * 58)
    for mode, fa in ana.items():
        near = min(kept, key=lambda p: abs(p - fa))
        err = 100.0 * (near - fa) / fa
        pf = paper_fdtd.get(mode, float("nan"))
        print(f"  {''.join(map(str, mode))}       {fa / 1e9:8.3f}    "
              f"{near / 1e9:9.3f}   {err:+7.2f}     {pf:8.3f}")
    print("\n  (analytic column uses c = 3e8 exactly -- that is what reproduces"
          "\n   the paper's Table II analytic row to 3 decimals; 2.998e8 does not)")

    np.savez(a.out, rec=rec, dt=cav.dt, f=f[:len(f) // 4], X=X[:len(X) // 4],
             peaks=np.array(kept), side=side, n=a.n)
    print(f"\n  saved {a.out}  (time signal + spectrum, for the slide)")


if __name__ == "__main__":
    main()
