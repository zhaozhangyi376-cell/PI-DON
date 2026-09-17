"""
3-D Yee FDTD reference solver (PEC box) + the shared curl operators.

Everything downstream (data generation, DCO loss, the DCO-in-the-loop demo)
reuses the curl functions defined here, so there is exactly one place where the
staggering convention lives.

Yee convention used throughout (N cells per direction, N+1 nodes):
    Ex[i,j,k] at ((i+1/2)dx,  j dy,      k dz     )   shape (N,   N+1, N+1)
    Ey[i,j,k] at ( i dx,     (j+1/2)dy,  k dz     )   shape (N+1, N,   N+1)
    Ez[i,j,k] at ( i dx,      j dy,     (k+1/2)dz )   shape (N+1, N+1, N  )
    Hx[i,j,k] at ( i dx,     (j+1/2)dy, (k+1/2)dz )   shape (N+1, N,   N  )
    Hy[i,j,k] at ((i+1/2)dx,  j dy,     (k+1/2)dz )   shape (N,   N+1, N  )
    Hz[i,j,k] at ((i+1/2)dx, (j+1/2)dy,  k dz     )   shape (N,   N,   N+1)

NOTE ON THE PAPER'S EQ. (7)
    As printed, eq. (7) of Qi & Sarris (T-MTT 73(7), 2025) has two typesetting
    problems that will silently wreck a reproduction:

    (a) The x-component bracket reads  dEy/dz - dEz/dy, which is -(curl E)_x.
        The y and z brackets read +(curl E)_y and +(curl E)_z.  The x sign is
        flipped relative to the other two.
    (b) The (grad_D x E) terms carry the *E-field* half-index positions
        (i+1/2,j,k), (i,j+1/2,k), (i,j,k+1/2), but the differences inside each
        bracket evaluate at the *H-field* positions.

    The intended meaning is unambiguous, so this file implements the standard,
    self-consistent Yee curl (components at the H positions, all three signs
    positive).  Flag this in the report -- it is a real, checkable finding.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import numpy as np

C0 = 2.99792458e8          # physical speed of light, used for the solver
C_PAPER = 3.0e8            # the paper's Table II analytical column uses 3e8 exactly
EPS0 = 8.8541878128e-12
MU0 = 4.0e-7 * np.pi


# --------------------------------------------------------------------------- #
#  curl operators (the single source of truth for staggering)
# --------------------------------------------------------------------------- #
def curl_E(Ex, Ey, Ez, dx, dy, dz):
    """(curl E) evaluated at the H positions.  Returns (cx, cy, cz)."""
    cx = (Ez[:, 1:, :] - Ez[:, :-1, :]) / dy - (Ey[:, :, 1:] - Ey[:, :, :-1]) / dz
    cy = (Ex[:, :, 1:] - Ex[:, :, :-1]) / dz - (Ez[1:, :, :] - Ez[:-1, :, :]) / dx
    cz = (Ey[1:, :, :] - Ey[:-1, :, :]) / dx - (Ex[:, 1:, :] - Ex[:, :-1, :]) / dy
    return cx, cy, cz


def curl_H(Hx, Hy, Hz, dx, dy, dz):
    """(curl H) evaluated at the interior E positions.  Returns (cx, cy, cz)
    shaped to match Ex[:,1:-1,1:-1], Ey[1:-1,:,1:-1], Ez[1:-1,1:-1,:]."""
    cx = ((Hz[:, 1:, 1:-1] - Hz[:, :-1, 1:-1]) / dy
          - (Hy[:, 1:-1, 1:] - Hy[:, 1:-1, :-1]) / dz)
    cy = ((Hx[1:-1, :, 1:] - Hx[1:-1, :, :-1]) / dz
          - (Hz[1:, :, 1:-1] - Hz[:-1, :, 1:-1]) / dx)
    cz = ((Hy[1:, 1:-1, :] - Hy[:-1, 1:-1, :]) / dx
          - (Hx[1:-1, 1:, :] - Hx[1:-1, :-1, :]) / dy)
    return cx, cy, cz


def cfl_dt(dx, dy, dz, c=C0, safety=0.99):
    """Courant limit for 3-D Yee.

    The paper quotes dt = 3.075e-12 s for a 50 mm air cavity "discretized into
    32 cells in each direction".

    Treating the nominal 32 cells as 31 intervals gives dx = 1.6129 mm and
    0.99*CFL = 3.0751 ps, which matches the paper's quoted dt to four figures.
    This is a useful reconstruction hypothesis, not author-confirmed mesh
    metadata.  In this implementation n=32 with dt=3.075 ps is above CFL.

    ``c`` must be the FASTEST local wave speed in the mesh.  In a filled
    cavity that is ``C0 / sqrt(min(eps_r))``, not ``C0``; see
    :func:`material_max_speed`.
    """
    return safety / (c * np.sqrt(1.0 / dx**2 + 1.0 / dy**2 + 1.0 / dz**2))


# --------------------------------------------------------------------------- #
#  material support contract (code review 20260917 F01)
# --------------------------------------------------------------------------- #
#  Before the 20260917 review the constructor accepted ``eps_r`` and threw it
#  away: ``self.eps`` was filled with EPS0 whatever the argument said, and both
#  E updates divided by the bare EPS0 constant.  eps_r=1 and eps_r=4 therefore
#  produced bit-identical trajectories.  The contract below makes the material
#  explicit instead:
#
#      eps_r=None or 1.0      vacuum.  Scalar coefficients, so a vacuum run is
#                             bit-identical to the pre-fix solver.
#      eps_r=<float>          uniform relative permittivity.
#      eps_r=<callable>       inhomogeneous medium, sampled INDEPENDENTLY on
#                             each of the three staggered E supports at that
#                             component's own physical coordinate.
#
#  Sampling on the E supports (not on the nodes) is the part that a "just fill
#  one array" fix gets wrong: Ex, Ey and Ez live at three different places in
#  the Yee cell, so one node array cannot serve all three without an averaging
#  rule that nobody declared.
E_COMPONENT_OFFSETS = ((0.5, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.5))


def _component_coordinates(shape, offsets, dxyz):
    """Physical coordinates of one staggered E component's own support."""
    axes = [(np.arange(size) + off) * d
            for size, off, d in zip(shape, offsets, dxyz)]
    return np.meshgrid(*axes, indexing="ij")


def sample_eps(eps_r, shapes, dxyz):
    """Return (eps_x, eps_y, eps_z) for the three staggered E supports.

    Each entry is a float for a uniform medium and an ndarray otherwise.  A
    uniform medium deliberately stays scalar: that keeps the vacuum path free
    of three (n+1)^3 arrays and bit-identical to the pre-fix coefficient.
    """
    if eps_r is None:
        return (EPS0, EPS0, EPS0), {"kind": "vacuum", "eps_r_min": 1.0, "eps_r_max": 1.0}
    if callable(eps_r):
        out, lo, hi = [], np.inf, -np.inf
        for shape, offsets in zip(shapes, E_COMPONENT_OFFSETS):
            grid = _component_coordinates(shape, offsets, dxyz)
            values = np.asarray(eps_r(*grid), dtype=float)
            if values.shape != tuple(shape):
                raise ValueError(
                    f"eps_r callable returned {values.shape}, expected {tuple(shape)}")
            if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
                raise ValueError("eps_r must be finite and strictly positive everywhere")
            out.append(EPS0 * values)
            lo, hi = min(lo, float(values.min())), max(hi, float(values.max()))
        return tuple(out), {"kind": "inhomogeneous", "eps_r_min": lo, "eps_r_max": hi}
    if isinstance(eps_r, np.ndarray):
        raise TypeError(
            "eps_r as a bare array has no declared staggering rule; pass a callable "
            "eps_r(x, y, z) so each E component samples its own support")
    value = float(eps_r)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("eps_r must be finite and strictly positive")
    return ((EPS0 * value,) * 3,
            {"kind": "vacuum" if value == 1.0 else "uniform",
             "eps_r_min": value, "eps_r_max": value})


def material_max_speed(eps_r_min, mu_r=1.0):
    """Fastest wave speed in the mesh, which is what the Courant limit uses."""
    return C0 / np.sqrt(float(eps_r_min) * float(mu_r))


def _co(coefficient, region):
    """Slice a per-support coefficient; a uniform medium stays a plain float."""
    return coefficient if np.isscalar(coefficient) else coefficient[region]


# --------------------------------------------------------------------------- #
#  PEC cavity solver
# --------------------------------------------------------------------------- #
class PECCavity:
    """Rectangular cavity, PEC on all six faces, point Ez source.

    ``eps_r`` defaults to vacuum.  A scalar fills the cavity uniformly and a
    callable ``eps_r(x, y, z)`` is sampled on each staggered E support; see
    :func:`sample_eps`.  ``mu_r`` is uniform only -- no magnetic material
    contract has been declared, so a non-unit value is accepted but recorded,
    and an inhomogeneous mu is refused rather than silently averaged.
    """

    def __init__(self, side=50e-3, n=32, dt=None, eps_r=None, mu_r=1.0,
                 allow_super_cfl=False):
        self.n = n
        self.dx = self.dy = self.dz = side / n
        self.side = side

        shapes = ((n, n + 1, n + 1), (n + 1, n, n + 1), (n + 1, n + 1, n))
        dxyz = (self.dx, self.dy, self.dz)
        (self.eps_x, self.eps_y, self.eps_z), self.material = sample_eps(eps_r, shapes, dxyz)
        if callable(mu_r) or isinstance(mu_r, np.ndarray):
            raise TypeError("inhomogeneous mu_r has no declared H-support contract")
        mu_r = float(mu_r)
        if not np.isfinite(mu_r) or mu_r <= 0.0:
            raise ValueError("mu_r must be finite and strictly positive")
        self.mu = MU0 * mu_r
        self.material["mu_r"] = mu_r
        # Kept for callers that only want "the permittivity the solver used".
        # A uniform medium keeps a plain float so a vacuum run is bit-identical
        # to the pre-20260917 coefficient dt/EPS0.
        self.eps = self.eps_x

        # F12: the Courant limit is a stability contract, not a hint.  A run
        # above it is not a reference solution, so the formal constructor
        # refuses it; a deliberately super-Courant study must say so.
        self.cfl_limit = cfl_dt(self.dx, self.dy, self.dz,
                                c=material_max_speed(self.material["eps_r_min"], mu_r),
                                safety=1.0)
        self.dt = cfl_dt(self.dx, self.dy, self.dz,
                         c=material_max_speed(self.material["eps_r_min"], mu_r)) if dt is None else dt
        self.super_cfl = bool(self.dt > self.cfl_limit)
        if self.super_cfl and not allow_super_cfl:
            raise ValueError(
                f"dt={self.dt:.6e} s exceeds the Courant limit {self.cfl_limit:.6e} s "
                f"(ratio {self.dt / self.cfl_limit:.6f}); a super-Courant FDTD reference "
                "diverges by construction.  Use n=31 for the 50 mm / 3.075 ps cavity, or "
                "pass allow_super_cfl=True from a labelled diagnostic entry point.")
        self.allow_super_cfl = bool(allow_super_cfl)

        self.Ex = np.zeros((n, n + 1, n + 1))
        self.Ey = np.zeros((n + 1, n, n + 1))
        self.Ez = np.zeros((n + 1, n + 1, n))
        self.Hx = np.zeros((n + 1, n, n))
        self.Hy = np.zeros((n, n + 1, n))
        self.Hz = np.zeros((n, n, n + 1))

    # -- material coefficients --------------------------------------------- #
    def e_coefficients(self):
        """(dt/eps) on each of the three staggered E supports.

        A uniform medium returns three floats, so the vacuum arithmetic is
        exactly the historical ``dt / EPS0``.
        """
        return (self.dt / self.eps_x, self.dt / self.eps_y, self.dt / self.eps_z)

    def is_vacuum(self):
        return (self.material["kind"] == "vacuum" and self.material.get("mu_r", 1.0) == 1.0)

    # -- boundaries -------------------------------------------------------- #
    def apply_pec(self):
        """Tangential E = 0 on all six faces."""
        self.Ex[:, 0, :] = self.Ex[:, -1, :] = 0.0
        self.Ex[:, :, 0] = self.Ex[:, :, -1] = 0.0
        self.Ey[0, :, :] = self.Ey[-1, :, :] = 0.0
        self.Ey[:, :, 0] = self.Ey[:, :, -1] = 0.0
        self.Ez[0, :, :] = self.Ez[-1, :, :] = 0.0
        self.Ez[:, 0, :] = self.Ez[:, -1, :] = 0.0

    # -- one leapfrog step ------------------------------------------------- #
    def step(self, src_value=None, src_idx=None, src_mode="add"):
        d = (self.dx, self.dy, self.dz)

        # 4/8.  H update from curl E
        cx, cy, cz = curl_E(self.Ex, self.Ey, self.Ez, *d)
        k = self.dt / self.mu
        self.Hx -= k * cx
        self.Hy -= k * cy
        self.Hz -= k * cz

        # 5.  E update from curl H  (interior only; PEC faces stay zero)
        hx, hy, hz = curl_H(self.Hx, self.Hy, self.Hz, *d)
        kx, ky, kz = self.e_coefficients()
        self.Ex[:, 1:-1, 1:-1] += _co(kx, (slice(None), slice(1, -1), slice(1, -1))) * hx
        self.Ey[1:-1, :, 1:-1] += _co(ky, (slice(1, -1), slice(None), slice(1, -1))) * hy
        self.Ez[1:-1, 1:-1, :] += _co(kz, (slice(1, -1), slice(1, -1), slice(None))) * hz

        # 6.  excitation -- written AFTER the E update, exactly as Algorithm 1
        if src_value is not None:
            i, j, k_ = src_idx
            if src_mode == "hard":
                self.Ez[i, j, k_] = src_value
            else:
                self.Ez[i, j, k_] += src_value

        self.apply_pec()

    def step_e_source_h(self, src_value=None, src_idx=None):
        """Algorithm-1 ordering on this independent Yee state.

        The ordinary :meth:`step` starts with the H half-step.  PI-DON's
        Algorithm 1 instead begins from the already available H half-layer,
        updates E, inserts its hard source, then forms the next H half-layer.
        Keeping this method on ``PECCavity`` makes the reference use the same
        tested Yee stencils without importing the PI-DON solver.
        """
        d = (self.dx, self.dy, self.dz)
        hx, hy, hz = curl_H(self.Hx, self.Hy, self.Hz, *d)
        kx, ky, kz = self.e_coefficients()
        self.Ex[:, 1:-1, 1:-1] += _co(kx, (slice(None), slice(1, -1), slice(1, -1))) * hx
        self.Ey[1:-1, :, 1:-1] += _co(ky, (slice(1, -1), slice(None), slice(1, -1))) * hy
        self.Ez[1:-1, 1:-1, :] += _co(kz, (slice(1, -1), slice(1, -1), slice(None))) * hz
        if src_value is not None:
            i, j, k_ = src_idx
            self.Ez[i, j, k_] = src_value
        self.apply_pec()
        cx, cy, cz = curl_E(self.Ex, self.Ey, self.Ez, *d)
        kh = self.dt / self.mu
        self.Hx -= kh * cx
        self.Hy -= kh * cy
        self.Hz -= kh * cz


def gaussian_pulse(n_steps, dt, f_max=15e9, level=0.1):
    """Unit-amplitude Gaussian whose spectrum falls to `level` at f_max."""
    tau = 2.0 * np.sqrt(-np.log(level)) / (2.0 * np.pi * f_max)
    t0 = 4.0 * tau
    t = np.arange(n_steps) * dt
    return np.exp(-(((t - t0) / tau) ** 2)), tau, t0


def source_waveform(n_steps, dt, f_max=15e9, mode="diff", level=0.1):
    """Excitation for a cavity driven by an ADDITIVE E-field source.

    The DC content of this waveform decides whether the experiment is valid.
    An additive source, Ez[src] += g[t], integrates its own waveform: whatever
    net area g has is deposited at the source cell as a permanent,
    non-radiating electrostatic blob.  That blob is CURL FREE -- it adds
    nothing to curl E while completely dominating |E|.

    Measured on the EXP-3 set-up (22.4 mm / 32 cells, 300 warm-up steps):

        mode     area of g     rms|E|      k_eff*d
        gauss    +1.63e+01     3.007e-02   0.0060   <- 99% electrostatic
        diff     -6.49e-07     1.225e-03   0.4135
        hard     (assigned)    4.443e-04   0.4307

    where k_eff*d = rms|curl E| / rms|E| * cell size is the only axis a
    normalised network sees, and the DCO training band is 0.152 .. 0.491.
    With "gauss" the network is handed a field whose curl is 25x smaller than
    anything it trained on; with "diff" the handover state lands in the band.

        gauss   the plain Gaussian.  Kept only to reproduce the fault.
        diff    its first derivative -- zero area, so nothing accumulates.
        hard    the plain Gaussian, but ASSIGNED rather than added by the
                caller (Ez[src] = g[t]), which also avoids accumulation.
    """
    g, tau, t0 = gaussian_pulse(n_steps, dt, f_max=f_max, level=level)
    if mode in ("gauss", "hard"):
        return g
    if mode == "diff":
        t = np.arange(n_steps) * dt
        return -2.0 * ((t - t0) / tau) * g
    raise ValueError(f"unknown source mode {mode!r}")


def analytic_modes(side=50e-3, c=C_PAPER, modes=((1, 1, 0), (2, 1, 1), (2, 2, 1),
                                                 (3, 1, 0), (3, 2, 1))):
    """Rectangular-cavity resonances.  c defaults to 3e8 to match Table II."""
    out = {}
    for (m, n, p) in modes:
        out[(m, n, p)] = (c / 2.0) * np.sqrt((m / side) ** 2 + (n / side) ** 2
                                             + (p / side) ** 2)
    return out


def spectrum_peaks(sig, dt, f_lo=1e9, f_hi=13e9, pad=1 << 20, n_peaks=8,
                   min_sep=250e6, window=True):
    """FFT with zero padding + parabolic interpolation, amplitude-ranked.

    8192 steps at ~3 ps is 24 ns, i.e. 41 MHz per raw FFT bin -- far too coarse
    for the 3-decimal GHz figures in Table II.  Zero-padding plus a parabolic
    fit on the magnitude peak recovers ~1 MHz.

    `min_sep` suppresses the window's own shoulders, which otherwise show up as
    local maxima a couple of bins either side of every strong line.  Candidates
    are ranked by AMPLITUDE before the separation filter is applied -- rank by
    frequency instead and you keep the lower shoulder rather than the peak,
    which biases every mode low by ~100 MHz.
    """
    x = np.asarray(sig, dtype=float)
    x = x - x.mean()
    if window:
        x = x * np.hanning(len(x))
    X = np.abs(np.fft.rfft(x, n=pad))
    f = np.fft.rfftfreq(pad, dt)
    df = f[1] - f[0]
    lo, hi = np.searchsorted(f, f_lo), np.searchsorted(f, f_hi)
    seg = X[lo:hi]
    idx = [i for i in range(1, len(seg) - 1)
           if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]]
    idx.sort(key=lambda i: -seg[i])              # amplitude ranked
    peaks = []
    for i in idx:
        a, b, c_ = seg[i - 1], seg[i], seg[i + 1]
        denom = a - 2 * b + c_
        delta = 0.5 * (a - c_) / denom if denom != 0 else 0.0
        fp = ((i + lo) + delta) * df
        if all(abs(fp - q) > min_sep for q in peaks):
            peaks.append(fp)
        if len(peaks) >= n_peaks:
            break
    return sorted(peaks), f, X
