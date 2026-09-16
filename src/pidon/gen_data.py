"""
Stage 2 -- DCO training data: superposed plane waves + ANALYTIC curl.

Paper section III-B, eqs. (2)(3)(4).  MVP reductions vs. the paper are marked
[MVP]; everything else follows the paper exactly.

    grid            32^3            -> 16^3          [MVP]
    samples         1000            -> 300           [MVP]
    cell size       0.3 - 0.8 mm    same
    phi             U(-pi, pi)      same
    theta           U(0, pi)        same + rejection (see below)
    k               (0, 1048]       same  (0 - 50 GHz)
    Ex0, Ey0        U(0, 5)         same
    Ez0             eq. (4)         same

REAL-VALUED FIELDS
    The paper writes eq. (2) with a complex exponential but works with real
    time-domain fields, so we take the real part:
        E      = sum_i  E0_i cos(k_i . r)
        curl E = sum_i -sin(k_i . r) (k_i x E0_i)
    The second line is exact (analytic), which is what the paper means by
    "The corresponding curl E was computed analytically".

EQ. (4) IS SINGULAR AT theta -> 90 deg
        Ez = -(cos(phi) sin(theta) Ex + sin(phi) sin(theta) Ey) / cos(theta)
    theta ~ U(0, pi) WILL draw values near pi/2, where Ez blows up.  The paper
    never mentions this.  We reject |cos(theta)| < COS_MIN and redraw.

STAGGERING
    Each of the six arrays is (N,N,N) and is evaluated at its own Yee position
    (see fdtd.py).  Free-space plane waves have no boundary, so all six arrays
    can share one shape.

SEEDS ARE NOT COMPARABLE ACROSS THE 2026-09-09 REFACTOR
    Adding --dirs moved the n_waves and ks draws AHEAD of the phi/theta draws,
    so the SAME seed now yields a different sample set than it did before.
    Both are valid draws from the same distribution, but numbers measured
    across that boundary are not directly comparable -- e.g. dco_L3d's EXP 2
    read 5.23 / 6.29 / 7.43e-2 before and 3.60 / 5.11 / 6.32e-2 after, on
    identical weights.

    That spread is also a warning about EXP 2 itself: it averages only FOUR
    samples per grid size, so differences under ~2x between checkpoints are
    within sampling noise and must not be reported as a ranking.  The large
    effects (17.3x for absolute coordinates, 16.7x for L=4) are far outside it
    and stand.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import numpy as np
import argparse

COS_MIN = 0.15          # theta rejection threshold (see above)
K_MAX = 1048.0          # rad/m  -> ~50 GHz, paper III-B
AMP_MAX = 5.0


def _draw_khat(rng):
    """One unit propagation direction, with the eq. (4) singularity rejected."""
    phi = rng.uniform(-np.pi, np.pi)
    while True:
        theta = rng.uniform(0.0, np.pi)
        if abs(np.cos(theta)) >= COS_MIN:
            break
    return np.array([np.cos(phi) * np.sin(theta),
                     np.sin(phi) * np.sin(theta),
                     np.cos(theta)])


def _shape3(n):
    """n may be an int (cubic) or a 3-tuple.  Paper III-D uses 64x96x16."""
    return (n, n, n) if isinstance(n, (int, np.integer)) else tuple(n)


def one_sample(rng, n, d, dirs="shared"):
    """Return E (3,n,n,n), curlE (3,n,n,n) for one random plane-wave stack.

    dirs="shared"   ONE (phi, theta) for the whole sample -- the literal
                    reading of eqs. (2)(3)(4), and what the paper describes.
    dirs="per-wave" an independent direction for every wave in the stack.

    WHY THIS SWITCH EXISTS
      With "shared", every wave in a sample travels the same way, so

          E(r) = sum_i E0_i cos(k_i khat.r)

      is a function of the single scalar khat.r -- a 1-D profile extruded along
      the other two axes.  EVERY training sample has that shape.  The network
      therefore never sees a field that varies genuinely in three directions,
      and a cavity mode (a superposition of 8 plane waves travelling in 8
      different directions) is off the training manifold entirely.  That is
      what EXP 3a measures: relative L2 ~19 on a warmed-up cavity field, i.e.
      the prediction is 20x larger than the truth, open loop, on step 1.

      It also explains why the paper's own dimension-invariance tests all pass:
      they resample the SAME distribution at a different grid size, so the test
      set never leaves the manifold either.

      "per-wave" costs nothing (same number of waves, same k range, same eq.(4)
      constraint applied per wave) and spans the full 3-D variation.
    """
    dx, dy, dz = d
    nx, ny, nz = _shape3(n)

    n_waves = int(rng.integers(4, 17))
    ks = rng.uniform(1.0, K_MAX, size=n_waves)
    if dirs == "shared":
        khats = np.repeat(_draw_khat(rng)[None, :], n_waves, axis=0)
    elif dirs == "per-wave":
        khats = np.stack([_draw_khat(rng) for _ in range(n_waves)])
    else:
        raise ValueError(f"unknown dirs {dirs!r}")

    # --- amplitudes: Ex, Ey random; Ez forced by k . E0 = 0, eq. (3)(4) -----
    E0 = np.empty((n_waves, 3))
    E0[:, 0] = rng.uniform(0.0, AMP_MAX, n_waves)
    E0[:, 1] = rng.uniform(0.0, AMP_MAX, n_waves)
    E0[:, 2] = -(khats[:, 0] * E0[:, 0] + khats[:, 1] * E0[:, 1]) / khats[:, 2]

    # --- Yee positions, all (n,n,n) ----------------------------------------
    X, Y, Z = np.meshgrid(np.arange(nx) * dx, np.arange(ny) * dy,
                          np.arange(nz) * dz, indexing="ij")
    hx, hy, hz = 0.5 * dx, 0.5 * dy, 0.5 * dz
    pos = {                                   # (component) -> (x, y, z)
        "Ex": (X + hx, Y, Z),
        "Ey": (X, Y + hy, Z),
        "Ez": (X, Y, Z + hz),
        "Cx": (X, Y + hy, Z + hz),            # curl components sit at H nodes
        "Cy": (X + hx, Y, Z + hz),
        "Cz": (X + hx, Y + hy, Z),
    }

    E = np.zeros((3, nx, ny, nz))
    C = np.zeros((3, nx, ny, nz))
    for w in range(n_waves):
        k_vec = ks[w] * khats[w]
        kxE = np.cross(k_vec, E0[w])          # curl amplitude
        for c, comp in enumerate(("Ex", "Ey", "Ez")):
            px, py, pz = pos[comp]
            E[c] += E0[w, c] * np.cos(k_vec[0] * px + k_vec[1] * py + k_vec[2] * pz)
        for c, comp in enumerate(("Cx", "Cy", "Cz")):
            px, py, pz = pos[comp]
            C[c] += -kxE[c] * np.sin(k_vec[0] * px + k_vec[1] * py + k_vec[2] * pz)
    return E, C


def build(n_samples, n, seed=0, d_lo=0.3e-3, d_hi=0.8e-3, dirs="shared"):
    rng = np.random.default_rng(seed)
    nx, ny, nz = _shape3(n)
    E = np.empty((n_samples, 3, nx, ny, nz), dtype=np.float32)
    C = np.empty((n_samples, 3, nx, ny, nz), dtype=np.float32)
    D = np.empty((n_samples, 3), dtype=np.float32)
    for s in range(n_samples):
        d = rng.uniform(d_lo, d_hi, 3)        # anisotropic: makes the trunk earn its keep
        e, c = one_sample(rng, n, d, dirs)
        E[s], C[s], D[s] = e, c, d
        if (s + 1) % 50 == 0:
            print(f"  {s + 1}/{n_samples}")
    return E, C, D


def coords_mm(n, d):
    """Trunk input: NODE coordinates in MILLIMETRES, (3,n,n,n).

    Must NOT be normalised to [0,1] -- the trunk learns the cell size from the
    spacing between coordinate values (paper: "decodes coordinate information
    into cell sizes").  Normalising destroys that.  mm rather than m only to
    keep the numbers O(1)-O(10) for the network.
    """
    i = np.arange(n)
    X, Y, Z = np.meshgrid(i * d[0], i * d[1], i * d[2], indexing="ij")
    return np.stack([X, Y, Z]).astype(np.float32) * 1e3


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16, help="grid size [MVP: 16]")
    ap.add_argument("--samples", type=int, default=300, help="[MVP: 300]")
    ap.add_argument("--out", default="data_16.npz")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--d-lo", type=float, default=0.3, help="min cell size, mm")
    ap.add_argument("--d-hi", type=float, default=0.8, help="max cell size, mm")
    ap.add_argument("--dirs", choices=["shared", "per-wave"], default="shared",
                    help="shared = the paper's eq.(2), one direction per "
                         "sample (every sample is then a 1-D profile extruded "
                         "in 3-D); per-wave = an independent direction per "
                         "wave.  See one_sample.__doc__.")
    a = ap.parse_args()

    print(f"generating {a.samples} samples at {a.n}^3, dirs={a.dirs} ...")
    E, C, D = build(a.samples, a.n, a.seed, a.d_lo * 1e-3, a.d_hi * 1e-3, a.dirs)
    np.savez_compressed(a.out, E=E, C=C, D=D, n=a.n, dirs=a.dirs)
    print(f"saved {a.out}")
    print(f"  E    : {E.shape}  |E|max={np.abs(E).max():.3g}")
    print(f"  curlE: {C.shape}  |C|max={np.abs(C).max():.3g}")
    print(f"  ratio |curl|/|E| ~ {np.abs(C).max() / np.abs(E).max():.1f}"
          f"   (should be of order k ~ {K_MAX:.0f})")
