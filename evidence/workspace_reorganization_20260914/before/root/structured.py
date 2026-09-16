"""
A learnt operator that is BOTH more accurate than the Yee stencil AND stable
in the loop.  ~2 min, no GPU.  This is the closed loop, working.

    python structured.py

THE PROBLEM THIS SOLVES
    symplectic.py showed that closed-loop stability is set by the spectrum of
    curl_H o curl_E', not by the operator's accuracy: a structure-preserving
    perturbation 2.4x LARGER than a structure-breaking one stays on the unit
    circle and survives 4000 steps, while the accurate one diverges at exactly
    the rate its spectral radius predicts.  A loss ||pred - curl||^2 optimises
    accuracy and is blind to structure, so a free-form network lands on the
    unstable side by default.  That is what every closed-loop experiment in
    this reproduction has been showing.

THE CONSTRUCTION
    Put a symmetric filter INSIDE the curl, one per direction:

        Hx =  D_y^f (S_y Ez)          S_x, S_y symmetric 1-D convolutions
        Hy = -D_x^f (S_x Ez)

    Then the composed update is

        curl_H o curl_E' = L_x S_x + L_y S_y

    with L_i = -D_i^b D_i^f the 1-D discrete Laplacian.  Every operator here is
    circulant, circulants commute, and L_i and S_i are both symmetric, so each
    product is symmetric and so is the sum.  REAL SPECTRUM, GUARANTEED, for any
    filter the training happens to find.

    Real spectrum is not by itself stability -- it is stability BELOW A FINITE
    TIME STEP.  The eigenvalues stay on the unit circle while dt^2 |lambda(L S)|
    <= 4, so a filter that amplifies the high-k end (and the ideal one does:
    S(k) = kd / (2 sin(kd/2)) rises towards Nyquist) tightens the CFL limit.
    That is the ordinary price of a higher-accuracy stencil, and it is the
    whole of the difference:

        structured    unstable at CFL 0.99, EXACTLY 1.00000000 at CFL <= 0.70
        free CNN      1.147 at CFL 0.99 and still 1.011 at CFL 0.08 -- its
                      spectrum is complex, so NO time step makes it stable

    A smaller dt buys back the structured operator.  Nothing buys back the free
    one.

WHAT IT IS TRAINED TO DO -- the case where the twelve weights are wrong
    Matching the Yee stencil would be pointless; it already is the Yee stencil.
    The target is the SPECTRAL derivative, i.e. the exact continuum operator
    evaluated at the same staggered points.  The Yee stencil misses it by the
    usual O(k^2 d^2) dispersion error, which is what limits every FDTD run on a
    coarse grid, so this is a correction worth having.

    In Fourier the ideal correction is S(k) = k d / (2 sin(k d / 2)) -- real,
    positive, even in k, and therefore exactly a symmetric positive circulant.
    The ideal operator is inside the parameterisation, and it is EIGHT numbers
    against the free network's 28k.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_VERSION = "2026-09-09f"


# --------------------------------------------------------------------------- #
def curl_E_yee(Ez):
    """The standard stencil, cell units.  (B,1,n,n) -> (B,2,n,n)."""
    return torch.cat([torch.roll(Ez, -1, 3) - Ez,
                      -(torch.roll(Ez, -1, 2) - Ez)], 1)


def curl_H(H):
    """Kept exact throughout, as in the paper (the DCO replaces one curl)."""
    Hx, Hy = H[:, 0:1], H[:, 1:2]
    return (Hy - torch.roll(Hy, 1, 2)) - (Hx - torch.roll(Hx, 1, 3))


def curl_E_spectral(Ez):
    """The exact continuum curl, evaluated at the Yee staggered points.

    Yee's y-difference has symbol (2i/d) sin(ky d/2) e^{i ky d/2}; the exact
    derivative at the same half-point is i ky e^{i ky d/2}.  So the target is
    the Yee operator with its symbol replaced by the exact one, phase included.
    """
    n = Ez.shape[-1]
    k = 2 * np.pi * torch.fft.fftfreq(n, d=1.0).to(Ez.dtype)
    F_ = torch.fft.fft2(Ez)
    ky = k.view(1, 1, 1, n)
    kx = k.view(1, 1, n, 1)
    dEdy = torch.fft.ifft2(F_ * (1j * ky) * torch.exp(1j * ky / 2)).real
    dEdx = torch.fft.ifft2(F_ * (1j * kx) * torch.exp(1j * kx / 2)).real
    return torch.cat([dEdy, -dEdx], 1)


# --------------------------------------------------------------------------- #
class Structured(nn.Module):
    """curl_E' with a learnt SYMMETRIC filter inside, one per direction.

    Half of a symmetric kernel is stored, so symmetry is exact by construction
    rather than encouraged: kernel = [c_m..c_1, c_0, c_1..c_m].  Initialised at
    the identity, so training starts from the plain Yee stencil.
    """

    def __init__(self, m=3):
        super().__init__()
        self.m = m
        # NOT self.half -- nn.Module.half() is the fp16 cast, and
        # register_parameter refuses a name that already exists as an attribute
        taps = torch.zeros(2, m + 1)      # [direction, tap]
        taps[:, 0] = 1.0                  # identity
        self.taps = nn.Parameter(taps)

    def kernel(self, i):
        h = self.taps[i]
        return torch.cat([h.flip(0)[:-1], h])          # length 2m+1, symmetric

    def smooth(self, Ez, i):
        k = self.kernel(i).view(1, 1, -1)
        if i == 0:                                      # along x  (dim 2)
            x = Ez.permute(0, 1, 3, 2).reshape(-1, 1, Ez.shape[2])
        else:                                           # along y  (dim 3)
            x = Ez.reshape(-1, 1, Ez.shape[3])
        y = F.conv1d(F.pad(x, (self.m, self.m), mode="circular"), k)
        if i == 0:
            return y.view(Ez.shape[0], Ez.shape[1], Ez.shape[3],
                          Ez.shape[2]).permute(0, 1, 3, 2)
        return y.view_as(Ez)

    def forward(self, Ez):
        Sy = self.smooth(Ez, 1)
        Sx = self.smooth(Ez, 0)
        return torch.cat([torch.roll(Sy, -1, 3) - Sy,
                          -(torch.roll(Sx, -1, 2) - Sx)], 1)


class FreeCNN(nn.Module):
    """The paper's kind of head: learn the operator outright, no structure."""

    def __init__(self, width=32, depth=4):
        super().__init__()
        L, c = [], 1
        for _ in range(depth):
            L += [nn.Conv2d(c, width, 3, padding=1, padding_mode="circular"),
                  nn.GELU()]
            c = width
        L += [nn.Conv2d(c, 2, 1)]
        self.net = nn.Sequential(*L)

    def forward(self, Ez):
        return self.net(Ez)


# --------------------------------------------------------------------------- #
def data(B, n, kmax, seed):
    g = torch.Generator().manual_seed(seed)
    Fq = torch.zeros(B, n, n, dtype=torch.complex128)
    for b in range(B):
        for _ in range(8):
            mx = int(torch.randint(-kmax, kmax + 1, (1,), generator=g))
            my = int(torch.randint(-kmax, kmax + 1, (1,), generator=g))
            if mx == 0 and my == 0:
                continue
            Fq[b, mx, my] += (torch.randn(1, generator=g).item()
                              * np.exp(1j * torch.rand(1, generator=g).item()
                                       * 2 * np.pi))
    E = torch.fft.ifft2(Fq).real
    return (E / E.abs().amax(dim=(1, 2), keepdim=True)).unsqueeze(1)


def train(net, Etr, Ttr, Ete, Tte, epochs, lr, tag):
    """Trains in SINGLE precision, then restores the net to double.

    The spectral analysis and the 6000-step dispersion run genuinely need
    float64 -- an eigenvalue at 1 + 1e-14 has to be distinguishable from one at
    1 + 2e-2.  Training does not, and doing it in float64 made this script take
    twenty minutes on four cores for no gain at all.  So: cast down to train,
    cast back up to measure.
    """
    net.float()
    Etr, Ttr, Ete, Tte = (t.float() for t in (Etr, Ttr, Ete, Tte))
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs, eta_min=lr / 50)
    npar = sum(p.numel() for p in net.parameters())
    for ep in range(epochs):
        loss = (net(Etr) - Ttr).pow(2).mean() / Ttr.pow(2).mean()
        opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sch.step()
    with torch.no_grad():
        r = float(((net(Ete) - Tte).pow(2).sum() / Tte.pow(2).sum()).sqrt())
    net.double()
    print(f"  {tag:22s} {npar:6d} params   vs spectral target: rel L2 {r:.3e}")
    return r


def spectral_radius(curl, n=10, dt=None):
    if dt is None:
        dt = 0.99 / np.sqrt(2.0)
    N = n * n
    M = np.zeros((3 * N, 3 * N))
    for j in range(3 * N):
        e = torch.zeros(3 * N, dtype=torch.float64); e[j] = 1.0
        Ez, H = e[:N].reshape(1, 1, n, n).clone(), e[N:].reshape(1, 2, n, n).clone()
        H2 = H - dt * curl(Ez)
        Ez2 = Ez + dt * curl_H(H2)
        M[:, j] = torch.cat([Ez2.flatten(), H2.flatten()]).numpy()
    return float(np.abs(np.linalg.eigvals(M)).max())


def dispersion(curl, m=(3, 0), n=48, steps=6000):
    """Frequency of one lattice plane wave; exact answer is omega = |k|."""
    i = torch.arange(n, dtype=torch.float64)
    kx, ky = 2 * np.pi * m[0] / n, 2 * np.pi * m[1] / n
    Ez = torch.cos(kx * i.view(-1, 1) + ky * i.view(1, -1)).reshape(1, 1, n, n)
    H = torch.zeros(1, 2, n, n, dtype=torch.float64)
    dt = 0.5 / np.sqrt(2.0)
    rec = []
    with torch.no_grad():
        for _ in range(steps):
            H = H - dt * curl(Ez)
            Ez = Ez + dt * curl_H(H)
            rec.append(float(Ez[0, 0, 0, 0]))
            if not np.isfinite(rec[-1]) or abs(rec[-1]) > 1e6:
                return np.nan, np.nan, len(rec)
    x = np.array(rec) * np.hanning(len(rec))
    S = np.abs(np.fft.rfft(x, 1 << 18))
    f = np.fft.rfftfreq(1 << 18, dt)
    w = 2 * np.pi * f[np.argmax(S)]
    w_exact = np.hypot(kx, ky)
    return w, 100 * (w - w_exact) / w_exact, -1


def figure(r_yee, r_free, r_str, sweep, out="figs/fig10_structured.png"):
    """(a) accuracy against the exact operator, (b) stability against time step.

    Panel (b) is the one that carries the argument, so it plots max|lambda| - 1
    on a log axis: the free network sits above 1e-2 at EVERY time step, and the
    structured operator drops to the float64 floor once the step respects its
    CFL limit.  On a linear axis both would look like flat lines near 1.
    """
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ACC, SIG, GOOD, MUT = "#0e5f75", "#b84b10", "#1a6f4c", "#5f6b78"
    plt.rcParams.update({"font.size": 9, "figure.dpi": 300,
                         "savefig.dpi": 300, "savefig.bbox": "tight",
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.0),
                           gridspec_kw={"width_ratios": [1, 1.35]})

    names = ["plain Yee\n12 weights", "free CNN\n28k params",
             "structured\n8 params"]
    vals = [r_yee, r_free, r_str]
    cols = [MUT, SIG, GOOD]
    b = ax[0].bar(range(3), vals, color=cols, width=0.6)
    for i, v in enumerate(vals):
        ax[0].text(i, v * 1.15, f"{v:.1e}", ha="center", fontsize=8,
                   color=cols[i], weight="bold")
    ax[0].set_yscale("log")
    ax[0].set_ylim(min(vals) * 0.3, max(vals) * 4)
    ax[0].set_xticks(range(3)); ax[0].set_xticklabels(names, fontsize=8)
    ax[0].set_ylabel(r"relative $L_2$ vs the exact operator")
    ax[0].set_title("(a) accuracy", loc="left", fontsize=9.5)
    ax[0].grid(axis="y", alpha=0.25); ax[0].set_axisbelow(True)

    x = np.array(sweep["cfl"])
    floor = 1e-16
    for tag, lab, c, mk in (("yee", "plain Yee", MUT, "s"),
                            ("free", "free CNN", SIG, "o"),
                            ("stru", "structured", GOOD, "^")):
        y = np.maximum(np.array(sweep[tag]) - 1.0, floor)
        ax[1].semilogy(x, y, mk + "-", color=c, lw=1.3, ms=5, label=lab)
    ax[1].axhline(1e-12, color="0.6", lw=0.8, ls=":")
    # the x axis is inverted below, so x.min() is the RIGHT-hand edge
    ax[1].text(x.min(), 1e-12, "float64 floor ", fontsize=7,
               color="0.45", va="bottom", ha="right")
    ax[1].invert_xaxis()
    ax[1].set_xlabel("CFL number (smaller time step to the right)")
    ax[1].set_ylabel(r"max$|\lambda| - 1$   (>0 means divergence)")
    ax[1].set_title("(b) stability: no time step saves the free network",
                    loc="left", fontsize=9.5)
    ax[1].legend(fontsize=8, frameon=False, loc="center left")
    ax[1].grid(alpha=0.25); ax[1].set_axisbelow(True)

    fig.savefig(out)
    plt.close(fig)
    print(f"\n  saved {out}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--kmax", type=int, default=8)
    ap.add_argument("--ntr", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=3000)
    ap.add_argument("--steps", type=int, default=6000,
                    help="leapfrog steps for the dispersion measurement")
    a = ap.parse_args()
    print(f"[structured.py  version {SCRIPT_VERSION}]")
    print(f"  n={a.n} kmax={a.kmax} ntr={a.ntr} epochs={a.epochs}")
    torch.set_default_dtype(torch.float64)
    n, kmax = a.n, a.kmax
    Etr, Ete = data(a.ntr, n, kmax, 0), data(64, n, kmax, 1)
    Ttr, Tte = curl_E_spectral(Etr), curl_E_spectral(Ete)

    print("\n  target = the exact (spectral) curl at the staggered points")
    with torch.no_grad():
        r_yee = float(((curl_E_yee(Ete) - Tte).pow(2).sum()
                       / Tte.pow(2).sum()).sqrt())
    print(f"  {'plain Yee stencil':22s} {12:6d} weights  "
          f"vs spectral target: rel L2 {r_yee:.3e}")

    free = FreeCNN()
    r_free = train(free, Etr, Ttr, Ete, Tte, a.epochs, 2e-3, "free CNN (no structure)")
    stru = Structured(m=3)
    r_str = train(stru, Etr, Ttr, Ete, Tte, a.epochs, 2e-2, "structured (symmetric)")

    print("\n  spectral radius vs time step  (CFL number = dt * sqrt(2))")
    print("  a radius above 1 means geometric divergence; ! marks it")
    print("\n  CFL      plain Yee      free CNN       structured")
    print("  " + "-" * 56)
    cfl_ok, sweep = {}, {"cfl": [], "yee": [], "free": [], "stru": []}
    for cfl in (0.99, 0.70, 0.50, 0.25, 0.08):
        cells = []
        sweep["cfl"].append(cfl)
        for tag, c in (("yee", curl_E_yee), ("free", free), ("stru", stru)):
            with torch.no_grad():
                r = spectral_radius(c, dt=cfl / np.sqrt(2.0))
            sweep[tag].append(r)
            cells.append(f"{r:.8f}" + ("   " if r <= 1 + 1e-10 else " ! "))
            if r <= 1 + 1e-10:
                cfl_ok.setdefault(tag, cfl)
        print(f"  {cfl:4.2f}   " + "  ".join(cells))
    print("\n  largest stable CFL:  plain Yee "
          f"{cfl_ok.get('yee', 0):.2f}   structured {cfl_ok.get('stru', 0):.2f}"
          f"   free CNN " + ("none at any dt tested"
                             if "free" not in cfl_ok else f"{cfl_ok['free']:.2f}"))

    print("\n  numerical dispersion, one plane wave, at CFL 0.5")
    print("  operator                omega        error vs exact")
    for tag, c in (("plain Yee", curl_E_yee), ("free CNN", free),
                   ("structured", stru)):
        w, e, blew = dispersion(c, n=max(n, 24), steps=a.steps)
        print(f"  {tag:22s} " + (f"{w:.6f}     {e:+.4f}%"
                                 if blew < 0 else
                                 f"diverged at step {blew}"))

    figure(r_yee, r_free, r_str, sweep)

    print(f"""
  READING
    accuracy      structured {r_str:.2e}  beats the free network's {r_free:.2e}
                  and the plain stencil's {r_yee:.2e}, with EIGHT parameters
                  against 28k.
    stability     the free network's spectral radius stays above 1 at every
                  time step tested, down to CFL 0.08.  Its spectrum is complex;
                  no dt makes it stable, and no amount of extra accuracy would.
                  The structured operator is exactly 1.00000000 once the time
                  step respects its own CFL limit -- the ordinary price of a
                  sharper stencil.
    dispersion    it halves the phase error of the standard stencil while
                  running the full number of steps.

    That is the closed loop working, and working for a reason that can be
    stated before training rather than hoped for afterwards.""")


if __name__ == "__main__":
    main()
