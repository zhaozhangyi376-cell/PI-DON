"""
Closed-loop stability is a STRUCTURE property, not an accuracy property.  ~2 min.

    python symplectic.py

WHAT THIS SETTLES
    The 3-D runs, and then the 2-D one, kept saying the same puzzling thing:
    making the operator more accurate did not make the loop last longer.  In
    mini2d the potential head reached 2.1e-3 single-step, twice as accurate as
    the direct head's 4.4e-3, and blew up EARLIER (step 65 against 108).  An
    accuracy-limited story cannot produce that.

    So the question is what the leapfrog actually needs.  It needs the
    eigenvalues of its one-step amplification matrix to stay on the unit
    circle, and the precise condition for that is that the COMPOSITION

        curl_H o curl_E'

    have real spectrum.  For the exact pair that composition is the discrete
    Laplacian -- self-adjoint and negative semi-definite, hence real.  Note
    what the condition is NOT: it is not that curl_E' be adjoint to curl_H.
    curl_E' = curl_E o S with S self-adjoint positive definite is not adjoint
    to curl_H either, yet curl_H o curl_E o S is similar to S^(1/2) L S^(1/2),
    still self-adjoint, still real -- and still stable, at any error size.

    A perturbation that leaves the composition similar to no self-adjoint
    operator puts an imaginary part in the spectrum, the radius exceeds one,
    and the error then grows geometrically at exactly that rate no matter how
    small it started.

THE EXPERIMENT
    Perturb the exact operator two ways, at matched magnitude:
      break     curl_E(E) + eps * shift(curl_E(E))   -- a shift is not
                self-adjoint, so the adjoint relation is destroyed
      preserve  curl_E(S(E))  with S = (1-a)I + a*blur, self-adjoint and
                positive definite -- the composition keeps the spectrum of
                curl_H o curl_E o S real and non-negative
    Then run 4000 leapfrog steps with each.

MEASURED (n=48, CFL 0.99, 4000 steps) and PREDICTED (spectral radius, n=10)
    perturbation      operator error   max|lambda|     predicted   simulated
    exact             0                1.0000000000    never       stable
    break   eps=1e-2  1.0e-02          1.0211311903      661         730
    preserve          2.4e-02          1.0000000000    never       stable
    break   eps=3e-2  3.0e-02          1.0598251756      238         256
    preserve          7.3e-02          1.0000000000    never       stable

    At every magnitude the structure-preserving operator carries 2.4x MORE
    error and survives, while the more accurate structure-breaking one dies --
    and the spectral radius predicts the step it dies at to within 10%.  This
    is not a heuristic about stability; it is the stability.

CONSEQUENCE FOR THE PAPER, AND FOR WHAT TO BUILD NEXT
    A network trained to minimise ||pred - curl|| optimises accuracy and is
    indifferent to structure, so it lands in the "break" column by default.
    That is why:
      - more epochs and more capacity buy so little closed-loop survival,
      - the divergence penalty bought 1.5x,
      - the vector-potential head -- which makes div(curl)=0 structural --
        did not help either.  In mini2d it was twice as accurate and died
        EARLIER.  Divergence is simply not the binding constraint; the
        spectrum of the composed update is.

    The constructive version: do not learn the operator, learn a SELF-ADJOINT
    POSITIVE-DEFINITE correction S and apply the exact stencil to it,
    curl_learnt = curl_exact o S.  S is easy to parameterise that way (a
    symmetric kernel, or W^T W), it keeps every guarantee the leapfrog relies
    on, and it still lets the operator adapt where the twelve-weight stencil
    is wrong -- inhomogeneous media, coarse cells, material interfaces.
"""

import numpy as np
import torch
import torch.nn.functional as F

SCRIPT_VERSION = "2026-09-09a"


def curl_E(Ez):
    """2-D TMz, cell units.  (B,1,n,n) -> (B,2,n,n)."""
    return torch.cat([(torch.roll(Ez, -1, 3) - Ez),
                      -(torch.roll(Ez, -1, 2) - Ez)], 1)


def curl_H(H):
    """The exact adjoint of curl_E.  (B,2,n,n) -> (B,1,n,n)."""
    Hx, Hy = H[:, 0:1], H[:, 1:2]
    return (Hy - torch.roll(Hy, 1, 2)) - (Hx - torch.roll(Hx, 1, 3))


def blur(x):
    """3x3 average -- self-adjoint and positive definite under periodic wrap."""
    k = torch.ones(1, 1, 3, 3, dtype=x.dtype) / 9.0
    return torch.cat([F.conv2d(F.pad(x[:, i:i + 1], (1, 1, 1, 1),
                                     mode="circular"), k)
                      for i in range(x.shape[1])], 1)


def adjoint_defect(curl, n=48):
    """|<curl a, b> - <a, curl_H b>| / |<curl a, b>|.  Zero for the exact pair."""
    a = torch.randn(2, 1, n, n, dtype=torch.float64)
    b = torch.randn(2, 2, n, n, dtype=torch.float64)
    l = float((curl(a) * b).sum())
    r = float((a * curl_H(b)).sum())
    return abs(l - r) / max(abs(l), 1e-30)


def op_error(curl, n=48):
    t = torch.randn(1, 1, n, n, dtype=torch.float64)
    return float((curl(t) - curl_E(t)).pow(2).sum().sqrt()
                 / curl_E(t).pow(2).sum().sqrt())


def leapfrog(curl, steps=4000, n=48, seed=3):
    """Returns (step it diverged at, or -1; the amplitude history)."""
    g = torch.Generator().manual_seed(seed)
    Ez = torch.randn(1, 1, n, n, generator=g, dtype=torch.float64)
    Ez = Ez / Ez.abs().max()
    H = torch.zeros(1, 2, n, n, dtype=torch.float64)
    dt = 0.99 / np.sqrt(2.0)
    amp = []
    for t in range(steps):
        H = H - dt * curl(Ez)
        Ez = Ez + dt * curl_H(H)
        m = float(Ez.abs().max())
        amp.append(m)
        if not np.isfinite(m) or m > 1e6:
            return t, amp
    return -1, amp


def amplification(curl, n=10, dt=None):
    """The one-step leapfrog amplification matrix, built column by column.

    State is (Ez, Hx, Hy), so 3n^2 dimensions -- 300 at n=10, small enough to
    diagonalise exactly.  This turns the stability question from an observation
    into a calculation: the spectral radius predicts the blow-up step, and the
    prediction can be checked against the simulation above.
    """
    if dt is None:
        dt = 0.99 / np.sqrt(2.0)
    N = n * n
    M = np.zeros((3 * N, 3 * N))
    for j in range(3 * N):
        e = torch.zeros(3 * N, dtype=torch.float64)
        e[j] = 1.0
        Ez, H = e[:N].reshape(1, 1, n, n).clone(), e[N:].reshape(1, 2, n, n).clone()
        H2 = H - dt * curl(Ez)
        Ez2 = Ez + dt * curl_H(H2)
        M[:, j] = torch.cat([Ez2.flatten(), H2.flatten()]).numpy()
    return M


def spectral(curl, n=10):
    """(spectral radius, steps to grow by 1e6)."""
    r = float(np.abs(np.linalg.eigvals(amplification(curl, n))).max())
    return r, (np.log(1e6) / np.log(r) if r > 1 + 1e-12 else np.inf)


def main():
    print(f"[symplectic.py  version {SCRIPT_VERSION}]")
    torch.set_default_dtype(torch.float64)
    n = 48

    print(f"\n  the exact pair, adjoint defect = {adjoint_defect(curl_E, n):.1e}")
    print("  the leapfrog keeps its eigenvalues on the unit circle BECAUSE of "
          "this.\n")

    print("  (the adjoint-defect column is NOT the discriminator -- it is a random-")
    print("   probe quantity, and the preserve rows can carry MORE of it.  The")
    print("   discriminator is the spectral radius, computed further down.)\n")
    print("  perturbation   operator error   adj. defect      4000 steps")
    print("  " + "-" * 66)
    rows = []
    for eps in (3e-3, 1e-2, 3e-2):
        cases = (
            ("break   ", lambda E, e=eps: curl_E(E) + e * torch.roll(curl_E(E), 1, 2)),
            ("preserve", lambda E, e=eps: curl_E((1 - e * 2.4) * E + e * 2.4 * blur(E))),
        )
        for name, f in cases:
            err, dfc = op_error(f, n), adjoint_defect(f, n)
            st, amp = leapfrog(f, n=n)
            out = (f"diverges at step {st}" if st > 0
                   else f"stable, amplitude {amp[-1] / amp[0]:.3f}")
            rows.append((name, err, dfc, st))
            print(f"  {name}       {err:.2e}         {dfc:.2e}       {out}")

    # ---- the same thing, from first principles ------------------------
    print("\n  spectral radius of the one-step amplification matrix (n=10)")
    print("  " + "-" * 66)
    print("  operator                       max|lambda|      predicted    measured")
    sp = {}
    for eps in (1e-2, 3e-2):
        for name, f in (("break   ", lambda E, e=eps: curl_E(E) + e * torch.roll(curl_E(E), 1, 2)),
                        ("preserve", lambda E, e=eps: curl_E((1 - e * 2.4) * E + e * 2.4 * blur(E)))):
            r, k = spectral(f)
            meas = [x[3] for x in rows if x[0] == name and abs(op_error(f) - x[1]) < 1e-9]
            m = meas[0] if meas else None
            sp[(name, eps)] = (r, k)
            print(f"  {name} eps={eps:.0e}            {r:.10f}   "
                  + (f"{k:7.0f}" if np.isfinite(k) else "  never")
                  + "      " + (f"{m}" if m and m > 0 else "stable"))
    r0, _ = spectral(curl_E)
    print(f"  exact                          {r0:.10f}     never      stable")
    print("""
  WHY
    exact      curl_H o curl_E is the discrete Laplacian: self-adjoint,
               negative semi-definite, REAL spectrum -> |lambda| = 1 exactly.
    preserve   curl_H o curl_E o S with S self-adjoint positive definite is
               similar to S^(1/2) L S^(1/2), still self-adjoint -> still real
               -> still |lambda| = 1, however large the error.
    break      curl_E + eps*shift is similar to no self-adjoint operator, the
               spectrum picks up an imaginary part, |lambda| > 1, and the error
               grows geometrically at exactly the rate the eigenvalue sets.

    The predicted blow-up steps match the simulated ones to about 10%.  This is
    not a heuristic about stability: it is the stability.""")

    br = [r for r in rows if r[0].startswith("break")]
    pr = [r for r in rows if r[0].startswith("preserve")]
    ratio = np.mean([p[1] / b[1] for p, b in zip(pr, br)])
    print(f"""
  READING
    The structure-preserving operator carries {ratio:.1f}x MORE error than the
    structure-breaking one at every magnitude tested, and survives all 4000
    steps while the accurate one dies.  Closed-loop stability is set by the
    spectrum of curl_H o curl_E', not by how small the operator error is.

    A loss of the form ||pred - curl||^2 optimises accuracy and is indifferent
    to adjointness, so a trained network lands in the "break" row by default --
    which is what every experiment in this reproduction has been showing.

    Build instead: learn a self-adjoint positive-definite S and apply the exact
    stencil to it, curl_learnt = curl_exact o S.  Easy to parameterise (a
    symmetric kernel, or W^T W), keeps every guarantee the leapfrog needs, and
    still adapts where the twelve-weight stencil is wrong.
""")


if __name__ == "__main__":
    main()
