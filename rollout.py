"""
Stage 3 -- put the DCO inside the leapfrog and let it run.  Differentiable.

    py -3.11 rollout.py --ckpt dco_L3d.pt          # measure, no training
    (train_pidon.py --roll K trains through it)

WHY A PERIODIC BOX INSTEAD OF THE PEC CAVITY
    EXP 3 in test_dco.py runs the real thing: a PEC cavity with a point source.
    That is the right final demonstration, but it is a poor thing to TRAIN
    through:
      * six staggered arrays of five different shapes -- every crop is a place
        to get the registration silently wrong under autograd;
      * an additive point source, which is exactly what deposited the
        electrostatic blob that made the old EXP 3 meaningless (see
        fdtd.source_waveform.__doc__);
      * PEC walls, where the field is discontinuous in a way nothing in the
        training distribution is.

    Here all six arrays are (n,n,n) on the SAME staggered layout gen_data.py
    already uses, with periodic wrap.  No source, no walls, nothing
    accumulates, and k*d is set explicitly by choosing wavevectors on the
    reciprocal lattice, so the state handed to the network is guaranteed to sit
    inside its training band.  Everything is torch, so K steps are one
    autograd graph.

    This isolates the question rollout training is supposed to answer: does the
    LEARNED OPERATOR survive being iterated?  The cavity then stays as the
    end-to-end test, not the training loop.

STAGGERING (identical to gen_data.py; Cx/Cy/Cz are also the H positions)
    Ex (i+1/2, j,     k    )      Hx (i,     j+1/2, k+1/2)
    Ey (i,     j+1/2, k    )      Hy (i+1/2, j,     k+1/2)
    Ez (i,     j,     k+1/2)      Hz (i+1/2, j+1/2, k    )
"""

import argparse

import numpy as np
import torch

import dco as D
import fdtd

SCRIPT_VERSION = "2026-09-09b"


# --------------------------------------------------------------------------- #
#  the two curls, periodic, differentiable, on the gen_data layout
# --------------------------------------------------------------------------- #
def curl_E_p(E, d):
    """E (B,3,n,n,n) at the E nodes -> curl at the H nodes.  Same shape.

    Delegates to dco.curl_periodic so the operator has ONE definition: the
    same function is the reference here and the output layer of a
    head="potential" network, which is what makes that head's div(curl)=0
    exact rather than merely close.
    """
    return D.curl_periodic(E, d)


def curl_H_p(H, d):
    """H (B,3,n,n,n) at the H nodes -> curl at the E nodes.  The dual: backward
    differences, so that div(curl(.)) = 0 holds for BOTH operators exactly."""
    dx, dy, dz = (d[:, k].view(-1, 1, 1, 1) for k in range(3))
    Hx, Hy, Hz = H[:, 0], H[:, 1], H[:, 2]
    cx = (Hz - torch.roll(Hz, 1, 2)) / dy - (Hy - torch.roll(Hy, 1, 3)) / dz
    cy = (Hx - torch.roll(Hx, 1, 3)) / dz - (Hz - torch.roll(Hz, 1, 1)) / dx
    cz = (Hy - torch.roll(Hy, 1, 1)) / dx - (Hx - torch.roll(Hx, 1, 2)) / dy
    return torch.stack([cx, cy, cz], 1)


def div_p(C, d):
    """Divergence at the cell centres -- zero for anything curl_E_p returns."""
    dx, dy, dz = (d[:, k].view(-1, 1, 1, 1) for k in range(3))
    return ((torch.roll(C[:, 0], -1, 1) - C[:, 0]) / dx
            + (torch.roll(C[:, 1], -1, 2) - C[:, 1]) / dy
            + (torch.roll(C[:, 2], -1, 3) - C[:, 2]) / dz)


def dt_cfl(d, safety=0.99):
    """Courant limit for this grid, per sample.  d (B,3) in metres -> (B,)."""
    return safety / (fdtd.C0 * (d ** -2).sum(1).sqrt())


# --------------------------------------------------------------------------- #
#  initial states with k*d under our control
# --------------------------------------------------------------------------- #
BAND = (0.152, 0.491)          # the DCO training band, from diag_exp3.py


def allowed_m(n, band=BAND, m_max=4):
    """Integer triples whose lattice wavenumber lands in the training band.

    On a periodic box, k = 2*pi*m/(n*d), so

        k * d = 2*pi*|m| / n

    which does NOT depend on the cell size at all -- only on |m|/n.  That is
    the whole reason this function exists: at n=16 the smallest non-zero value
    is 2*pi/16 = 0.393 and anything but a single axis-aligned unit vector
    overshoots the band, so a 16^3 rollout box cannot be excited in band.  At
    n=32 the step is 0.196 and |m| = 1, sqrt(2), sqrt(3), 2 all fit.  Hence the
    default --n 32 (which also makes the rollout a dimension-invariance test,
    since the net was trained at 16^3).
    """
    out = []
    for mx in range(-m_max, m_max + 1):
        for my in range(-m_max, m_max + 1):
            for mz in range(-m_max, m_max + 1):
                if mx == my == mz == 0:
                    continue
                kd = 2 * np.pi * float(np.sqrt(mx * mx + my * my + mz * mz)) / n
                if band[0] <= kd <= band[1]:
                    out.append((mx, my, mz))
    return out


def lattice_ic(B, n, d_m, n_waves=6, m_max=4, seed=0, device="cpu"):
    """Superposed plane waves whose wavevectors lie ON the reciprocal lattice,
    so the field is exactly periodic and no discontinuity is injected.

    Wavevectors are drawn only from allowed_m(), i.e. only those whose k*d
    falls inside the DCO's training band -- the state handed to the network is
    in band BY CONSTRUCTION rather than by hope.  Raises if the grid admits no
    such wavevector, which is the honest outcome at n=16.
    """
    cand = allowed_m(n, m_max=m_max)
    if not cand:
        raise SystemExit(
            f"no lattice wavevector puts k*d inside {BAND} at n={n}: the "
            f"spacing is 2*pi/n = {2 * np.pi / n:.3f}.  Use a larger --n "
            f"(32 works).")
    g = torch.Generator(device="cpu").manual_seed(seed)
    i = torch.arange(n, dtype=torch.float64)
    E = torch.zeros(B, 3, n, n, n, dtype=torch.float64)
    for b in range(B):
        dx, dy, dz = (float(d_m[b, k]) for k in range(3))
        # each component at its own Yee node
        pos = {0: (i + 0.5, i, i), 1: (i, i + 0.5, i), 2: (i, i, i + 0.5)}
        for _ in range(n_waves):
            m = torch.tensor(cand[int(torch.randint(len(cand), (1,),
                                                    generator=g))]).double()
            k_vec = 2 * np.pi * m / torch.tensor([n * dx, n * dy, n * dz])
            # E0 perpendicular to k: a x k is transverse for any a, and
            # redrawing (rather than skipping) keeps the wave count exact
            for _try in range(16):
                a = torch.randn(3, generator=g).double()
                E0 = torch.cross(a, k_vec, dim=0)
                if E0.norm() > 1e-12:
                    break
            E0 = E0 / E0.norm() * torch.rand(1, generator=g).double().item()
            ph = torch.rand(1, generator=g).double().item() * 2 * np.pi
            for c in range(3):
                px, py, pz = pos[c]
                X, Y, Z = torch.meshgrid(px * dx, py * dy, pz * dz, indexing="ij")
                E[b, c] += E0[c] * torch.cos(k_vec[0] * X + k_vec[1] * Y
                                             + k_vec[2] * Z + ph)
    return E.to(device).float()


def k_eff_d(E, C, d):
    """rms|curl| / rms|E| * cell size, per sample -- the axis the net sees."""
    Lc = (d[:, 0] * d[:, 1] * d[:, 2]).pow(1 / 3)
    num = C.pow(2).flatten(1).mean(1).sqrt()
    den = E.pow(2).flatten(1).mean(1).sqrt().clamp_min(1e-30)
    return num / den * Lc


# --------------------------------------------------------------------------- #
#  the leapfrog, with a swappable curl_E
# --------------------------------------------------------------------------- #
def leapfrog(E, H, d, dt, steps, curl_e, keep=False):
    """Standard Yee leapfrog with curl_E replaced by `curl_e(E, d)`.

    Returns the final (E, H), or the whole E trajectory if keep=True.
    dt is (B,), broadcast over the field.
    """
    kh = (dt / fdtd.MU0).view(-1, 1, 1, 1, 1)
    ke = (dt / fdtd.EPS0).view(-1, 1, 1, 1, 1)
    traj = []
    for _ in range(steps):
        H = H - kh * curl_e(E, d)
        E = E + ke * curl_H_p(H, d)
        if keep:
            traj.append(E)
    return (torch.stack(traj, 1) if keep else E), H


def dco_curl(net, coord_mode, norm_mode):
    """Wrap a DCO so it has the signature of curl_E_p."""
    def f(E, d):
        n = E.shape[-1]
        x = torch.cat([D.make_coords(n, d[b] * 1e3, coord_mode,
                                     device=E.device) for b in range(len(d))])
        e_hat, _, a, Lc = D.normalise(E, None, d * 1e3, norm_mode)
        return D.denormalise(net(e_hat, x, D.d_rel_of(d * 1e3, Lc)), a, Lc)
    return f


# --------------------------------------------------------------------------- #
#  self-test -- the harness must be right before anything is trained through it
# --------------------------------------------------------------------------- #
def selftest(n=32, B=2, d_mm=0.55, steps=2000):
    """Four properties the discrete scheme must have EXACTLY, not approximately.

    Measured values on this implementation (float64):
        div(curl_E), div(curl_H)      2.8e-16   the identity, both operators
        <curl_E a, b> - <a, curl_H b> 1.6e-16   exact adjoints
        interleaved energy, 2000 st.  1.000000000000
        numerical dispersion          -0.001% vs the Yee relation

    The energy one is the reason for the interleaved form: E and H live half a
    time step apart, so the naive eps|E|^2 + mu|H|^2 OSCILLATES by ~15% and is
    not the invariant.  Pairing H^(n-1/2) with H^(n+1/2) is, and it holds to
    twelve decimals -- which is what says the leapfrog itself is not the source
    of any drift seen later.
    """
    torch.set_default_dtype(torch.float64)
    d = torch.full((B, 3), d_mm * 1e-3, dtype=torch.float64)
    ok = True

    E = torch.randn(B, 3, n, n, n, dtype=torch.float64)
    H = torch.randn(B, 3, n, n, n, dtype=torch.float64)
    Lc = d_mm * 1e-3
    cE = curl_E_p(E, d)
    r1 = float(div_p(cE, d).pow(2).mean().sqrt()
               / (cE.pow(2).mean().sqrt() / Lc))
    print(f"  div(curl_E) / scale            {r1:.2e}"); ok &= r1 < 1e-12

    l = float((curl_E_p(E, d) * H).sum()); r = float((E * curl_H_p(H, d)).sum())
    r2 = abs(l - r) / max(abs(l), 1e-30)
    print(f"  adjointness  |<Ca,b>-<a,C*b>|  {r2:.2e}"); ok &= r2 < 1e-12

    E0 = lattice_ic(B, n, d, seed=3).double()
    H0 = torch.zeros_like(E0)
    dt = dt_cfl(d)
    kh = (dt / fdtd.MU0).view(-1, 1, 1, 1, 1)
    ke = (dt / fdtd.EPS0).view(-1, 1, 1, 1, 1)
    Ec, Hc, U0 = E0.clone(), H0.clone(), None
    for t in range(steps + 1):
        Ep, Hp = Ec, Hc
        Hc = Hp - kh * curl_E_p(Ep, d)
        Ec = Ep + ke * curl_H_p(Hc, d)
        U = float((fdtd.EPS0 * Ep.pow(2).sum() + fdtd.MU0 * (Hp * Hc).sum()) / 2)
        if U0 is None:
            U0 = U
    r3 = abs(U / U0 - 1.0)
    print(f"  energy drift over {steps} steps  {r3:.2e}"); ok &= r3 < 1e-9

    kd = k_eff_d(E0, curl_E_p(E0, d), d)
    print(f"  lattice_ic k*d                 {float(kd.min()):.4f} .. "
          f"{float(kd.max()):.4f}   band {BAND}")
    ok &= BAND[0] <= float(kd.mean()) <= BAND[1]

    torch.set_default_dtype(torch.float32)
    print("  SELF-TEST PASSED" if ok else "  *** SELF-TEST FAILED ***")
    return ok


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="dco_L3d.pt")
    ap.add_argument("--n", type=int, default=32,
                    help="rollout box. 16 cannot be excited in band -- see "
                         "allowed_m.__doc__ -- and 32 doubles as a "
                         "dimension-invariance test for a 16^3-trained net.")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--warm", type=int, default=40)
    ap.add_argument("--m-max", type=int, default=4)
    ap.add_argument("--d-mm", type=float, default=0.55)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--selftest", action="store_true",
                    help="verify the discrete scheme, then exit")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()

    print(f"[rollout.py  version {SCRIPT_VERSION}]")
    if a.selftest:
        raise SystemExit(0 if selftest(n=a.n) else 1)
    dev = torch.device(a.device)
    ck = torch.load(a.ckpt, map_location=dev, weights_only=False)
    net = D.DCO(levels=ck["levels"], base=ck["base"],
                head=ck.get("head", "direct")).to(dev)
    net.load_state_dict(ck["state"]); net.eval()
    cm, nm = ck.get("coords", "abs"), ck.get("norm", "max")
    print(f"loaded {a.ckpt}: L={ck['levels']} base={ck['base']} "
          f"coords={cm} norm={nm} target={ck.get('target', 'analytic')} "
          f"head={ck.get('head', 'direct')}")

    d = torch.full((a.batch, 3), a.d_mm * 1e-3, device=dev)
    dt = dt_cfl(d)
    E0 = lattice_ic(a.batch, a.n, d.cpu(), m_max=a.m_max, seed=a.seed, device=dev)
    H0 = torch.zeros_like(E0)

    # settle into a proper leapfrog state with the exact operator
    E0, H0 = leapfrog(E0, H0, d, dt, a.warm, curl_E_p)
    C0 = curl_E_p(E0, d)
    kd = k_eff_d(E0, C0, d)
    print(f"\nhandover after {a.warm} exact steps: k*d = "
          f"{kd.min():.4f} .. {kd.max():.4f}   (training band 0.152 .. 0.491)")
    if not (0.10 <= float(kd.mean()) <= 0.70):
        print("  *** OUT OF BAND -- change --m-max or --d-mm before reading on")

    with torch.no_grad():
        p = dco_curl(net, cm, nm)(E0, d)
        print(f"open loop, curl on this state: rel L2 = "
              f"{float(D.rel_l2(p, C0)):.4e}")
        print(f"  div of the DCO curl / div of the exact curl = "
              f"{float(div_p(p, d).pow(2).mean().sqrt()):.3e} / "
              f"{float(div_p(C0, d).pow(2).mean().sqrt()):.3e}")

        ref_E, _ = leapfrog(E0, H0, d, dt, a.steps, curl_E_p, keep=True)
        dut_E, _ = leapfrog(E0, H0, d, dt, a.steps,
                            dco_curl(net, cm, nm), keep=True)
        num = (dut_E - ref_E).pow(2).flatten(2).mean(2).sqrt()
        den = ref_E.pow(2).flatten(2).mean(2).sqrt().clamp_min(1e-30)
        err = (num / den).mean(0).cpu().numpy()          # (steps,)

    print(f"\nclosed loop, {a.steps} steps, error vs the exact leapfrog:")
    for thr in (0.01, 0.05, 0.20, 1.00):
        i = int(np.argmax(err > thr)) if (err > thr).any() else -1
        print(f"  exceeds {thr * 100:6.0f}%  at step {'never' if i < 0 else i}")
    for s in (1, 10, 50, 100, 200, a.steps - 1):
        if s < len(err):
            print(f"  step {s:4d}   {err[s]:.4e}")
    import os
    tag = os.path.splitext(os.path.basename(a.ckpt))[0]
    out = f"rollout_err_{tag}.npz"
    for f in (out, "rollout_err.npz"):     # per-checkpoint AND a generic copy,
        np.savez(f, err=err, steps=a.steps, ckpt=a.ckpt,   # so make_figs can
                 label=tag, kd=kd.cpu().numpy())           # overlay every run
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
