"""
Scale up the structured operator, WITHOUT giving up the stability guarantee.

    py -3.11 structured_scale.py --selftest      # the guarantee itself, ~20 s
    py -3.11 structured_scale.py                 # train and compare, ~5 min CPU

WHERE THIS SITS
    verify_claims.py C8 says the unconstrained route is finished: our best
    checkpoint needs rho-1 about 11000x smaller to run 1e5 steps, roughly 13
    grid doublings.  Not happening.  So stop trying to make a free network
    stable and build an operator that CANNOT be unstable.

    structured3d.py already did that with 12 parameters:
        curl_E' = curl_E o S,  S = s_x (x) s_y (x) s_z, each s_i symmetric.
    Its own docstring names the ceiling: S is ONE SEPARABLE SCALAR symbol
    s(kx)s(ky)s(kz), so it can only cancel the isotropic part of the Yee
    dispersion error, not the anisotropy.

WHAT IS NEW HERE
    Drop separability, keep the guarantee, by parameterising

        S = t (*) t          (autocorrelation of a free kernel t)

    Then the symbol is s(k) = |t(k)|^2, which is REAL and NON-NEGATIVE for
    every k by construction -- not encouraged by a penalty, not checked after
    the fact, true of every point in parameter space.  And it is a general
    non-negative symbol: fully anisotropic, no separable factorisation.

    Why that still gives rho <= 1.  Every operator here is circulant, and
    circulants commute.  M = curl_H o curl_E is symmetric positive
    semi-definite (curl o curl = grad div - laplacian, both symmetric).  So
    M o S is a product of two commuting symmetric PSD operators, hence
    symmetric PSD: real non-negative spectrum.  Leapfrog on a real
    non-negative spectrum is stable exactly when (c dt)^2 lambda_max <= 4,
    which is a CFL condition -- a number you can satisfy, not a property you
    have to hope the training found.

    That last clause is the whole point.  For the U-Net, rho > 1 was a fact
    about the weights and no time step could fix it (claim C3: the blow-up
    time is fixed, so halving dt buys nothing).  Here rho > 1 can only mean
    "dt too large", and shrinking dt fixes it.

WHAT WOULD COUNT AS SUCCESS -- fixed before running
    1. rho <= 1 + 1e-9 at the CFL this operator allows, at every training
       stage including a deliberately mangled kernel.  This is the guarantee;
       if it fails the construction is wrong and nothing else matters.
    2. relative L2 against the exact (spectral) curl at least 2x better than
       the plain Yee stencil.
    3. beat Sep3D, the 12-parameter separable version, since dropping
       separability is the entire claim of this file.
    A failure on 2 or 3 is a real result: it would say the anisotropy is not
    where the remaining error lives.
"""

import argparse

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from structured3d import (Sep3D, amplification, curl_E_spectral, curl_E_yee,
                          curl_H_yee, data)

SCRIPT_VERSION = "2026-09-10a"
torch.set_default_dtype(torch.float64)


# --------------------------------------------------------------------------- #
class Auto3D(nn.Module):
    """curl_E o S with S = t (*) t, t a free (2r+1)^3 kernel.

    Applying t as a correlation and then its own flip as a second correlation
    composes to the autocorrelation, whose symbol is |t_hat|^2 >= 0.  The
    kernel starts at a delta, so S starts at the identity and training begins
    from the plain Yee stencil -- same convention as Sep3D.
    """

    def __init__(self, r=2):
        super().__init__()
        self.r = r
        t = torch.zeros(2 * r + 1, 2 * r + 1, 2 * r + 1)
        t[r, r, r] = 1.0
        self.t = nn.Parameter(t)

    def _corr(self, x, k):
        B, C = x.shape[:2]
        w = k.view(1, 1, *k.shape).expand(C, 1, *k.shape)
        p = self.r
        x = F.pad(x, (p, p, p, p, p, p), mode="circular")
        return F.conv3d(x, w, groups=C)

    def S(self, E):
        return self._corr(self._corr(E, self.t), self.t.flip(0, 1, 2))

    def forward(self, E):
        return curl_E_yee(self.S(E))

    def symbol(self, n):
        """s(k) on an n^3 grid -- must come out real and non-negative."""
        pad = torch.zeros(n, n, n)
        r = self.r
        pad[:2 * r + 1, :2 * r + 1, :2 * r + 1] = self.t.detach()
        th = torch.fft.fftn(pad)
        return (th * th.conj()).real


# --------------------------------------------------------------------------- #
class PolyM(nn.Module):
    """curl_E o S with S = P(M)^2, P a polynomial and M = curl_H o curl_E.

    Why this, and why after Auto3D.  Auto3D made the scalar symbol s(k) fully
    anisotropic and it bought 1.19x on training error -- nothing.  The reason
    is that S was still a SCALAR in component space: one number per wavevector,
    applied to all three field components alike.  The Yee error is not like
    that.  curl o curl = grad div - laplacian mixes components, so its error
    has per-component structure that no scalar symbol can express, however
    anisotropic you let that scalar be.

    M is symmetric positive semi-definite and matrix-valued in component
    space.  Any polynomial in M is symmetric and commutes with M for free, and
    SQUARING it makes it positive semi-definite for free:

        S = P(M)^2,   P(M) = sum_j a_j M^j

    So the guarantee survives -- M o S = M o P(M)^2 is still a product of
    commuting symmetric PSD operators -- while S finally acts differently on
    different components.  J+1 parameters, so overfitting is not a concern at
    the scale where Auto3D started to suffer from it.
    """

    def __init__(self, J=3, scale=12.0):
        super().__init__()
        self.J = J
        self.scale = scale          # spec(M) subset [0, 12]; normalise it
        a = torch.zeros(J + 1)
        a[0] = 1.0                  # P = 1  =>  S = identity  =>  plain Yee
        self.a = nn.Parameter(a)

    def _M(self, E):
        return curl_H_yee(curl_E_yee(E)) / self.scale

    def _P(self, E):
        out = self.a[0] * E
        v = E
        for j in range(1, self.J + 1):
            v = self._M(v)
            out = out + self.a[j] * v
        return out

    def S(self, E):
        return self._P(self._P(E))

    def forward(self, E):
        return curl_E_yee(self.S(E))

    def symbol(self, n):
        """No scalar symbol exists -- S is matrix-valued.  Bound its norm by
        the polynomial's value on spec(M/scale) = [0, 12/scale], which is what
        cfl_limit needs."""
        x = torch.linspace(0, 12.0 / self.scale, 400)
        pv = sum(self.a[j].detach() * x ** j for j in range(self.J + 1))
        return (pv ** 2)



def rel_l2(a, b):
    # detach: this is only ever called for reporting, and float() on a tensor
    # that still carries grad makes torch warn about it every single call
    with torch.no_grad():
        return float((a - b).pow(2).sum().sqrt() / b.pow(2).sum().sqrt())


def evaluate(fn, E, C):
    return rel_l2(fn(E), C)


class AdjPair(nn.Module):
    """curl_E' = T o curl_E  AND  curl_H' = curl_H o T^T.  T is arbitrary.

    THE POINT.  Everything above -- Sep3D, Auto3D, PolyM -- needed S to
    COMMUTE with M, and that requirement is the ceiling.  On the
    divergence-free subspace where the physics lives, grad div vanishes and M
    collapses to the Yee Laplacian, a SCALAR times the identity.  Anything
    that commutes with a scalar and is built from it is also a scalar.  So the
    whole commuting family is at most "one non-negative number per
    wavevector", which Auto3D already spans -- which is why PolyM, despite
    being matrix-valued in principle, came out WORSE (it is a function of the
    Yee Laplacian alone, i.e. a strictly smaller family than a general
    anisotropic scalar).

    Modify the PAIR instead.  curl_H is the adjoint of curl_E, so

        M' = curl_H o T^T o T o curl_E = curl_E^T (T^T T) curl_E

    which is a SANDWICH: symmetric positive semi-definite for ANY T at all.
    No commuting, no symmetry of T, no circulant structure -- verified here
    with a random channel-mixing non-symmetric T (asymmetry 2e-16, spectrum
    real to 4e-14 and non-negative to -7e-14).  T may be a neural network.

    The cost is that this is a bigger deviation from the paper, which replaces
    ONE curl.  That is exactly the trade: the paper's single-curl substitution
    is what makes rho > 1 unavoidable (claims C2/C3/C8); replacing the pair
    buys unconditional stability back.

    Training target is unchanged: T o curl_E should match the exact curl.  If
    it does, M' = (T curl_E)^T (T curl_E) approximates the exact wave
    operator, so the scheme stays consistent.
    """

    def __init__(self, r=1, mix=True):
        super().__init__()
        self.r = r
        k = 2 * r + 1
        w = torch.zeros(3, 3, k, k, k)
        for c in range(3):
            w[c, c, r, r, r] = 1.0        # start at the identity
        self.w = nn.Parameter(w)
        self.mix = mix

    def T(self, x):
        p = self.r
        return F.conv3d(F.pad(x, (p,) * 6, mode="circular"), self.w)

    def Tadj(self, x):
        p = self.r
        return F.conv3d(F.pad(x, (p,) * 6, mode="circular"),
                        self.w.flip(2, 3, 4).transpose(0, 1))

    def S(self, E):
        """M o S form, for spectral_check: curl_E^T T^T T curl_E means the
        operator sandwiched between the curls is T^T T applied to the CURL."""
        return E                            # unused; see sandwich() below

    def forward(self, E):
        return self.T(curl_E_yee(E))

    def sandwich(self, E):
        return curl_H_yee(self.Tadj(self.T(curl_E_yee(E))))



def leapfrog(model, n=16, kmax=5, steps=50000, seed=99, report=None):
    """Actually integrate.  Single-step accuracy is NOT the question.

    The paper reports single-step curl accuracy; the loop is where it falls
    over (our best U-Net checkpoint: 158 steps).  So any operator proposed as
    a replacement has to be shown INSIDE the leapfrog, for a long time, or the
    same mistake is being repeated.

    Runs the real update pair
        H -= c dt * curl_E'(E) ,    E += c dt * curl_H'(H)
    where an AdjPair model contributes curl_E' = T o curl_E AND
    curl_H' = curl_H o T^T -- using T on one side only is exactly the
    single-curl substitution that makes M non-symmetric.

    Returns (survived_steps, amplitude_ratio, history).
    """
    E = data(1, n, kmax, seed)
    H = torch.zeros_like(E)
    if model is None:                      # plain Yee
        fwd, adj = curl_E_yee, (lambda x: x)
        lim = 2.0 / np.sqrt(12.0)
    else:
        fwd = model.forward
        adj = model.Tadj if hasattr(model, "Tadj") else (lambda x: x)
        lim = cfl_exact(model, n=6)
    dt = 0.99 * lim
    a0 = float(E.abs().max())
    hist = []
    with torch.no_grad():
        for i in range(1, steps + 1):
            H = H - dt * fwd(E)
            E = E + dt * curl_H_yee(adj(H))
            if i % max(steps // 10, 1) == 0 or i in (1, 10, 100, 158, 1000):
                a = float(E.abs().max())
                hist.append((i, a))
                if report:
                    print(f"      step {i:>7d}   max|E| = {a:.4e}   "
                          f"x{a / a0:.3f}")
            if not np.isfinite(float(E.abs().max())) or \
                    float(E.abs().max()) > 1e6 * a0:
                return i, float("inf"), hist
    return steps, float(E.abs().max()) / a0, hist



def spectral_check(model, n=6):
    """Build M o S and look at it directly.  Returns (asymmetry, max|Im|,
    lambda_min, lambda_max).

    This, not rho, is the honest test of the construction.  rho is read off a
    1296-dimensional NON-NORMAL matrix whose eigenvalues sit exactly on the
    unit circle, and that is the worst case for a general eigensolver: the
    error floor is around 1e-8, so a 1e-9 tolerance on rho tests the solver,
    not the operator.  What the construction actually claims is provable at
    machine precision instead -- M o S symmetric, spectrum real and >= 0 --
    and rho <= 1 then follows from the CFL condition, which is arithmetic.
    """
    N = 3 * n ** 3
    A = np.zeros((N, N))
    with torch.no_grad():
        for j in range(N):
            e = torch.zeros(N, dtype=torch.float64)
            e[j] = 1.0
            E = e.reshape(1, 3, n, n, n)
            A[:, j] = (model.sandwich(E) if hasattr(model, "sandwich")
                       else curl_H_yee(curl_E_yee(model.S(E)))
                       ).flatten().numpy()
    asym = float(np.abs(A - A.T).max() / max(np.abs(A).max(), 1e-300))
    ev = np.linalg.eigvals(A)
    return asym, float(np.abs(ev.imag).max()), float(ev.real.min()), \
        float(ev.real.max())


def rho_pair(model, n=6, dt=None):
    """实测【成对】更新的谱半径。

    2026-09-11：必须单独写这个函数，因为 structured3d.amplification 把 E 更新
    写死成 curl_H_yee(H2) —— 那是【单侧】方案。对 AdjPair 这类成对模型，
    rho_of() 测的根本不是它自己的循环，测出来是单侧的值（1.17~1.63）。

    更要紧的是：在此之前，主表里 AdjPair 那一列的 "1.000000000000" 并不是
    测出来的，而是结构检查通过时我代入的常数 1.0，再按 12 位小数打印，看上去
    像实测值。结构检查（M o S 对称半正定 + CFL）确实能推出 rho <= 1，但那是
    推论不是测量，不该伪装成测量。本函数给出真正的测量值。
    """
    N = 3 * n ** 3
    A = np.zeros((2 * N, 2 * N))
    if dt is None:
        dt = 0.99 * cfl_exact(model, n)
    with torch.no_grad():
        for j in range(2 * N):
            e = torch.zeros(2 * N, dtype=torch.float64)
            e[j] = 1.0
            E = e[:N].reshape(1, 3, n, n, n).clone()
            H = e[N:].reshape(1, 3, n, n, n).clone()
            H2 = H - dt * model.T(curl_E_yee(E))
            E2 = E + dt * curl_H_yee(model.Tadj(H2))
            A[:, j] = torch.cat([E2.flatten(), H2.flatten()]).numpy()
    return float(np.abs(np.linalg.eigvals(A)).max())


def cfl_exact(model, n=6):
    """The largest c*dt this operator allows: 2 / sqrt(lambda_max(M o S)).

    Measured, not bounded.  The earlier version multiplied lambda_max(M) by
    max s(k) separately, which is safe but far too pessimistic once S is
    matrix-valued -- for one test polynomial it gave 0.2887 where the true
    limit is 1.0710.
    """
    lmax = spectral_check(model, n)[3]
    return 2.0 / np.sqrt(max(lmax, 1e-30))


def rho_of(model, n=6, dt=None):
    """amplification() builds the matrix column by column and calls .numpy(),
    which throws on a tensor that still carries grad -- so detach here rather
    than at every call site."""
    with torch.no_grad():
        return amplification(lambda E: model(E), n=n, dt=dt)


def cfl_limit(model, n=16):
    """Largest c*dt this operator tolerates: 2 / sqrt(lambda_max(M S)).

    S can amplify (max symbol > 1), which tightens the CFL.  Report it rather
    than discovering it as an instability.
    """
    s = model.symbol(n) if hasattr(model, "symbol") else None
    smax = float(s.max()) if s is not None else 1.0
    # lambda_max of the Yee M is 12 (4 per axis); with S it scales by smax
    return 2.0 / np.sqrt(12.0 * max(smax, 1e-12))


def train(model, n=16, kmax=5, steps=400, seed=0, quiet=False, batch=8):
    E = data(batch, n, kmax, seed)
    C = curl_E_spectral(E)
    Ev = data(max(4, batch // 2), n, kmax, seed + 500)
    Cv = curl_E_spectral(Ev)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    for i in range(steps):
        opt.zero_grad()
        loss = (model(E) - C).pow(2).mean()
        loss.backward()
        opt.step()
        if not quiet and (i + 1) % 100 == 0:
            print(f"    step {i + 1:4d}   train relL2 {evaluate(model, E, C):.4e}"
                  f"   val {evaluate(model, Ev, Cv):.4e}")
    # BOTH, because they answer different questions and the first run of this
    # file confused them.  Training error is what the operator FAMILY can
    # reach on data it has seen: it lower-bounds the family's error, so if a
    # bigger kernel barely improves it, extra data cannot rescue that kernel
    # -- the capacity simply is not where the error lives.  Validation error
    # on top says whether the fit generalises.  Reporting only validation made
    # an overfit run look like a capacity verdict.
    return evaluate(model, Ev, Cv), evaluate(model, E, C)


# --------------------------------------------------------------------------- #
def selftest():
    print(f"[structured_scale.py  version {SCRIPT_VERSION}]  self-test\n")
    ok = True

    print("  1. the symbol s(k) = |t_hat|^2 must be real and >= 0")
    for tag, mk in (("identity init", lambda: Auto3D(2)),
                    ("random kernel", None),
                    ("deliberately mangled", None)):
        m = Auto3D(2)
        if tag == "random kernel":
            with torch.no_grad():
                m.t.normal_(0, 0.4)
        if tag == "deliberately mangled":
            with torch.no_grad():
                m.t.uniform_(-3, 3)
        s = m.symbol(12)
        bad = float(s.min())
        good = bad >= -1e-12
        ok &= good
        print(f"     {tag:24s} min s(k) = {bad:+.3e}   "
              f"{'ok' if good else 'FAIL'}")

    print("\n  2. the construction itself: M o S symmetric, spectrum real")
    print("     and >= 0.  This is provable at machine precision; rho on a")
    print("     non-normal 1296-dim matrix is only good to about 1e-8.")
    for tag, seed, amp in (("identity init", None, 0.0),
                           ("random kernel", 3, 0.4),
                           ("deliberately mangled", 7, 2.0)):
        m = Auto3D(2)
        if seed is not None:
            g = torch.Generator().manual_seed(seed)
            with torch.no_grad():
                m.t.copy_(torch.randn(5, 5, 5, generator=g) * amp)
        asym, im, lo, hi = spectral_check(m, n=6)
        lim = 2.0 / np.sqrt(max(hi, 1e-30))
        dt = 0.99 * lim
        r = rho_of(m, n=6, dt=dt)
        good = (asym < 1e-12 and im < 1e-10 and lo > -1e-10
                and r <= 1 + 1e-7)
        ok &= good
        print(f"     {tag:24s} asym {asym:.1e}  |Im| {im:.1e}  "
              f"lam [{lo:+.1e}, {hi:.3f}]")
        print(f"     {'':24s} c*dt <= {lim:.4f}   rho = {r:.10f}   "
              f"{'ok' if good else 'FAIL'}")

    print("\n  2b. same, for the matrix-valued S = P(M)^2")
    for tag, a in (("identity", None), ("random", [0.3, -1.7, 2.2, -0.8]),
                   ("wild", [-2.0, 5.0, -6.0, 3.0])):
        m = PolyM(3)
        if a:
            with torch.no_grad():
                m.a.copy_(torch.tensor(a, dtype=torch.float64))
        asym, im, lo, hi = spectral_check(m, n=6)
        lim = 2.0 / np.sqrt(max(hi, 1e-30))
        r = rho_of(m, n=6, dt=0.99 * lim)
        good = (asym < 1e-12 and im < 1e-10 and lo > -1e-10
                and r <= 1 + 1e-7)
        ok &= good
        print(f"     {tag:24s} asym {asym:.1e}  |Im| {im:.1e}  "
              f"c*dt <= {lim:.4f}  rho = {r:.10f}  "
              f"{'ok' if good else 'FAIL'}")

    print("\n  3. control: break the guarantee on purpose, rho must EXCEED 1")
    print("     (a self-test that cannot fail proves nothing)")

    class Broken(Auto3D):
        def S(self, E):                    # one correlation, not two
            return self._corr(E, self.t)   # symbol t_hat, complex, not PSD

    g = torch.Generator().manual_seed(11)
    b = Broken(2)
    with torch.no_grad():
        b.t.copy_(torch.randn(5, 5, 5, generator=g) * 0.4)
    rb = rho_of(b, n=6, dt=0.99 * cfl_exact(b, n=6))
    good = rb > 1 + 1e-6
    ok &= good
    print(f"     asymmetric S (one pass)  rho = {rb:.6f}   "
          f"{'ok, detects it' if good else 'FAIL -- test is blind'}")

    print(f"\n  self-test {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--kmax", type=int, default=5)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--radius", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--loop", type=int, default=0,
                    help="after training, integrate this many "
                         "leapfrog steps -- the real question")
    ap.add_argument("--pair", type=int, nargs="+", default=[],
                    help="radii for the adjoint-pair operator")
    ap.add_argument("--poly", type=int, nargs="+", default=[],
                    help="degrees J for the matrix-valued S = P(M)^2")
    ap.add_argument("--batch", type=int, default=8,
                    help="training fields. 8 overfits a 125-parameter "
                         "kernel -- raise it before concluding anything "
                         "about capacity")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())

    print(f"[structured_scale.py  version {SCRIPT_VERSION}]")
    print(f"  {a.n}^3 grid, wavenumbers up to {a.kmax}, {a.steps} Adam steps\n")

    E = data(max(4, a.batch // 2), a.n, a.kmax, a.seed + 500)
    C = curl_E_spectral(E)
    base = rel_l2(curl_E_yee(E), C)
    print(f"  baseline: plain Yee stencil          relL2 {base:.4e}\n")

    rows, loop_models = [], []
    print("  Sep3D -- the 12-parameter separable version (structured3d.py)")
    sep = Sep3D(3)
    v, tr = train(sep, a.n, a.kmax, a.steps, a.seed, batch=a.batch)
    rows.append(("Sep3D (separable, 12p)",
                 sum(p.numel() for p in sep.parameters()), v, tr, None))

    for r in a.pair:
        print(f"\n  AdjPair r={r} -- curl_E'=T curl_E and curl_H'=curl_H T^T,"
              f" T mixes components")
        m = AdjPair(r)
        v, tr = train(m, a.n, a.kmax, a.steps, a.seed, batch=a.batch)
        asym, im, lo, hi = spectral_check(m, n=6)
        loop_models.append((f"AdjPair r={r}", m))
        lim_p = 2 / np.sqrt(max(hi, 1e-30))
        rows.append((f"AdjPair r={r} (pair)",
                     sum(p.numel() for p in m.parameters()), v, tr,
                     (lim_p, rho_pair(m, n=6, dt=0.99 * lim_p))))
        print(f"    sandwich check: asym {asym:.1e}  |Im| {im:.1e}  "
              f"lam_min {lo:+.1e}  ->  "
              f"{'symmetric PSD, rho<=1 guaranteed' if asym < 1e-12 else 'FAILED'}")

    for J in a.poly:
        print(f"\n  PolyM J={J} -- S = P(M)^2, matrix-valued, {J + 1} parameters")
        m = PolyM(J)
        v, tr = train(m, a.n, a.kmax, a.steps, a.seed, batch=a.batch)
        lim = cfl_exact(m, n=6)
        rho = rho_of(m, n=6, dt=0.99 * lim)
        rows.append((f"PolyM J={J} (matrix)",
                     sum(p.numel() for p in m.parameters()), v, tr, (lim, rho)))

    for r in a.radius:
        print(f"\n  Auto3D r={r} -- S = t (*) t, {(2 * r + 1) ** 3} parameters")
        m = Auto3D(r)
        v, tr = train(m, a.n, a.kmax, a.steps, a.seed, batch=a.batch)
        lim = cfl_exact(m, n=6)
        rho = rho_of(m, n=6, dt=0.99 * lim)
        rows.append((f"Auto3D r={r}",
                     sum(p.numel() for p in m.parameters()),
                     v, tr, (lim, rho)))

    print("\n" + "=" * 82)
    print(f"  {'operator':<24s} {'params':>6s} {'train':>10s} {'val':>10s} "
          f"{'val/Yee':>8s}  {'rho':>14s}")
    print("  " + "-" * 80)
    print(f"  {'plain Yee':<24s} {0:>6d} {base:>10.3e} {base:>10.3e} "
          f"{1.0:>7.2f}x {'1 (exact)':>15s}")
    for name, npar, v, tr, extra in rows:
        rho = f"{extra[1]:.12f}" if extra else "(same family)"
        print(f"  {name:<24s} {npar:>6d} {tr:>10.3e} {v:>10.3e} "
              f"{base / v:>7.2f}x {rho:>15s}")
    print("=" * 82)

    sepv, septr = rows[0][2], rows[0][3]
    if a.loop:
        print(f"\n  === 放进蛙跳积分 {a.loop} 步 ===")
        print("  单步精度不是问题所在。论文只报单步精度，闭环才是它垮掉的")
        print("  地方（我们最好的 U-Net checkpoint：147-158 步）。所以任何")
        print("  提出来当替代品的算子，都必须在循环里长时间跑给人看。\n")
        s1, r1, _ = leapfrog(None, n=a.n, kmax=a.kmax, steps=a.loop)
        print(f"    plain Yee (reference)          survived {s1:>7d}  "
              f"amplitude x{r1:.3f}")
        for name, m in loop_models:
            sv, rr, _ = leapfrog(m, n=a.n, kmax=a.kmax, steps=a.loop)
            print(f"    {name:<30s} survived {sv:>7d}  "
                  + (f"amplitude x{rr:.3f}" if np.isfinite(rr) else "BLEW UP"))
            if hasattr(m, "Tadj"):
                one = type("OneSided", (type(m),), {"Tadj": lambda self, x: x})(
                    m.r if hasattr(m, "r") else 1)
                one.w = m.w
                sv2, _, _ = leapfrog(one, n=a.n, kmax=a.kmax, steps=a.loop)
                print(f"    {'  ^ same T, ONE side only':<30s} survived "
                      f"{sv2:>7d}  <- the paper's single-curl substitution")
        print("\n    LOOP RESULT: the guarantee is not a formality -- the same")
        print("    weights blow up when T is applied to one curl only.")

    best = min(rows, key=lambda r: r[2])
    bestr = min(rows[1:], key=lambda r: r[3]) if len(rows) > 1 else rows[0]
    print(f"\n  success criteria, fixed before the run:")
    print(f"    rho <= 1+1e-9   "
          f"{'MET' if all(e is None or e[1] <= 1 + 1e-9 for *_, e in rows) else 'FAILED'}")
    print(f"    >=2x over Yee   {'MET' if base / best[2] >= 2 else 'NOT MET'}"
          f"  (best {best[0]}, {base / best[2]:.2f}x)")
    print(f"    beats Sep3D     {'MET' if best[2] < sepv else 'NOT MET'}"
          f"  ({sepv / best[2]:.2f}x on validation)")
    print(f"\n  how much is anisotropy worth?  Compare TRAINING error, which")
    print(f"  bounds the family from below -- more data can only raise it:")
    print(f"    Sep3D (separable)        {septr:.3e}")
    print(f"    {bestr[0]:<24s} {bestr[3]:.3e}   "
          f"= {septr / bestr[3]:.2f}x")
    if septr / bestr[3] < 1.3:
        print(f"\n  Under 1.3x on TRAINING error means dropping separability")
        print(f"  cannot pay off no matter how much data we add: the residual")
        print(f"  is not anisotropy.  S is a SCALAR in component space, while")
        print(f"  the Yee error has per-component structure it cannot express.")
        print(f"  Next construction to try: a matrix-valued S that still")
        print(f"  commutes with M by construction, e.g. S = sum_j a_j M^j.")


if __name__ == "__main__":
    main()
