"""
Stage 6 -- the spectral radius of the REAL DCO, not a toy operator.

    py -3.11 spectral_dco.py --selftest
    py -3.11 spectral_dco.py --ckpt pidon_R2_all.pt
    py -3.11 spectral_dco.py --ckpt pidon_R2_all.pt --cfl 0.99 0.7 0.5 0.3 0.15

WHY THIS SCRIPT EXISTS
    symplectic.py and structured3d.py established that the blow-up step of a
    leapfrog is set by the spectral radius rho of its one-step map, and they
    did it on operators small enough to build the 6n^3 matrix explicitly.
    Neither touched the 2.25M-parameter U-Net that the whole reproduction is
    actually about, so the argument had a hole in it: we claimed a mechanism
    for the DCO blow-up without ever measuring the DCO's rho.

    This closes that hole.  No matrix is built.  The one-step map is probed by
    finite-difference directional derivatives, which needs nothing but forward
    evaluations -- so it works on a nonlinear network (GELU, maxpool,
    transposed conv) where forward-mode autograd coverage is patchy.

WHAT IS BEING MEASURED
    Work in the normalised variables u = (E, Z0*H), Z0 = sqrt(mu0/eps0).  One
    leapfrog step is then symmetric in the two fields:

        Hs <- Hs - c*dt * curl_E(E)
        E  <- E  + c*dt * curl_H(Hs)

    Call that map F.  rho is the spectral radius of dF/du at the operating
    state.  Power iteration on the Jacobian gives it without the matrix:
    repeatedly apply J to a unit vector, record the growth factor, average the
    logs.  Complex eigenvalue pairs make the per-step factor oscillate; the
    running mean still converges to |lambda|max.

    A LINEAR operator (the exact Yee curl) has an exact finite-difference
    derivative, so --selftest is a real test: it must return 1.0000 to the
    fourth decimal, and it fails loudly if the harness has drifted.

READING THE OUTPUT
    rho <= 1 + few*1e-6   the scheme is neutral; error grows linearly, the
                          loop can run indefinitely.  This is what the exact
                          Yee curl and the structured operators do.
    rho  = 1 + g          error is multiplied by rho every step.  Starting
                          from the open-loop single-step error eps0, it
                          reaches O(1) at step  ln(1/eps0) / ln(rho).  That
                          predicted step is printed next to the measured
                          blow-up step from the same run, which is the actual
                          falsifiable claim.

    The CFL sweep answers the practical question: can a smaller time step
    rescue a trained DCO?  For the free 2-D CNN in structured.py the answer was
    no, all the way down to CFL 0.08.  Whether that holds for the 3-D U-Net is
    what this script is for.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import math
import os

import numpy as np
import torch

import dco as D
import fdtd
import rollout as R

SCRIPT_VERSION = "2026-09-10a"

Z0 = math.sqrt(fdtd.MU0 / fdtd.EPS0)
C0 = 1.0 / math.sqrt(fdtd.MU0 * fdtd.EPS0)


# --------------------------------------------------------------------------- #
#  the one-step map, in normalised variables
# --------------------------------------------------------------------------- #
def step_factory(curl_e, d, dt):
    """F(E, Hs) -> (E', Hs') for one leapfrog step.  dt is (B,)."""
    k = (C0 * dt).view(-1, 1, 1, 1, 1)

    def F(E, Hs):
        Hs = Hs - k * curl_e(E, d)
        E = E + k * R.curl_H_p(Hs, d)
        return E, Hs
    return F


def _norm(xs):
    return math.sqrt(sum(float(x.pow(2).sum()) for x in xs))


def _axpy(a, xs, b, ys):
    return [a * x + b * y for x, y in zip(xs, ys)]


def jvp_fd(F, x, v, h):
    """Central finite-difference directional derivative of F at x along v.

    Exact (up to round-off) when F is linear, which is what makes the
    --selftest number meaningful.
    """
    p = F(*_axpy(1.0, x, h, v))
    m = F(*_axpy(1.0, x, -h, v))
    return [(a - b) / (2 * h) for a, b in zip(p, m)]


def power_rho(F, x, iters=180, burn=60, eps_rel=1e-3, seed=0, verbose=False):
    """Spectral radius of dF/dx at x, by power iteration on FD-JVPs.

    Returns (rho, per_step_logs).  rho is exp(mean(log growth)) over the
    post-burn-in iterations -- averaging the logs is what makes a complex
    eigenvalue pair (whose per-step factor oscillates) converge instead of
    ringing forever.
    """
    g = torch.Generator(device="cpu").manual_seed(seed)
    v = [torch.randn(t.shape, generator=g, dtype=torch.float64).to(t) for t in x]
    nv = _norm(v)
    v = [t / nv for t in v]
    h = eps_rel * max(_norm(x), 1e-30)

    logs = []
    for i in range(iters):
        w = jvp_fd(F, x, v, h)
        gnorm = _norm(w)
        if not math.isfinite(gnorm) or gnorm == 0.0:
            return float("nan"), logs
        logs.append(math.log(gnorm))
        v = [t / gnorm for t in w]
        if verbose and (i + 1) % 40 == 0:
            print(f"      iter {i + 1:4d}  running rho = "
                  f"{math.exp(float(np.mean(logs[burn:] or logs))):.10f}")
    # slope of the CUMULATIVE log growth, not the mean of the tail.  A
    # symplectic map has every eigenvalue on the unit circle but is far from
    # normal, so ||J^k v|| carries an O(1) transient that a tail-mean only
    # decays as 1/k -- at 120 iterations that alone reads as rho = 0.9991 for
    # an operator whose rho is exactly 1.  Fitting a line to cumsum(logs)
    # absorbs the transient into the intercept and leaves the slope clean.
    k = np.arange(len(logs), dtype=float)
    cum = np.cumsum(logs)
    lo = burn if len(logs) > burn + 8 else 0
    slope = float(np.polyfit(k[lo:], cum[lo:], 1)[0])
    return math.exp(slope), logs


# --------------------------------------------------------------------------- #
#  empirical growth rate -- the nonlinear loop's own answer
# --------------------------------------------------------------------------- #
def empirical_rho(F_dut, F_ref, x, steps=400, seed=0):
    """Run both loops from the same state; fit ln||E_dut - E_ref|| vs step.

    The slope is ln(rho_effective).  This includes every nonlinearity the
    linearised number leaves out, so agreement between the two is itself
    evidence the linear picture is the right one.
    Returns (rho, blowup_step, err_curve).
    """
    a = [t.clone() for t in x]
    b = [t.clone() for t in x]
    ref0 = _norm([x[0]])
    errs = []
    blow = -1
    for s in range(steps):
        a = list(F_dut(*a))
        b = list(F_ref(*b))
        e = _norm([a[0] - b[0]]) / max(ref0, 1e-30)
        if not math.isfinite(e) or e > 1e3:
            blow = s
            break
        errs.append(e)
        if e > 1.0 and blow < 0:
            blow = s
    errs = np.array(errs)
    lo = max(3, len(errs) // 4)
    hi = len(errs)
    rho = float("nan")
    if hi - lo > 5:
        y = np.log(np.maximum(errs[lo:hi], 1e-300))
        good = np.isfinite(y)
        if good.sum() > 5:
            k = np.arange(lo, hi)[good]
            rho = float(np.exp(np.polyfit(k, y[good], 1)[0]))
    return rho, blow, errs


def predicted_blowup(rho, eps0):
    """Step at which eps0 * rho^N reaches 1."""
    if not (rho > 1.0) or not (0 < eps0 < 1):
        return float("inf")
    return math.log(1.0 / eps0) / math.log(rho)


# --------------------------------------------------------------------------- #
#  self-test -- the exact operator must come back neutral
# --------------------------------------------------------------------------- #
def selftest(n=16, d_mm=0.55, dtype=torch.float64):
    print("\n=== self-test: the exact Yee curl must give rho = 1 ==========")
    dev = torch.device("cpu")
    d = torch.full((1, 3), d_mm * 1e-3, device=dev, dtype=dtype)
    ok = True
    for cfl in (0.99, 0.70, 0.30):
        dt = R.dt_cfl(d, safety=cfl)
        E = R.lattice_ic(1, n, d.cpu().double(), m_max=2, seed=1,
                         device=dev).to(dtype)
        Hs = torch.zeros_like(E)
        F = step_factory(R.curl_E_p, d, dt)
        rho, _ = power_rho(F, (E, Hs), iters=200, burn=60, eps_rel=1e-4)
        bad = abs(rho - 1.0) > 2e-4
        ok &= not bad
        print(f"  CFL {cfl:4.2f}   rho = {rho:.10f}   {'FAIL' if bad else 'ok'}")

    # a deliberately non-symmetric perturbation must come back > 1
    def skewed(E, dd):
        c = R.curl_E_p(E, dd)
        return c + 0.02 * torch.roll(c, 1, 2)
    dt = R.dt_cfl(d, safety=0.99)
    E = R.lattice_ic(1, n, d.cpu().double(), m_max=2, seed=1,
                     device=dev).to(dtype)
    rho, _ = power_rho(step_factory(skewed, d, dt), (E, torch.zeros_like(E)),
                       iters=200, burn=60, eps_rel=1e-4)
    bad = not (rho > 1.0 + 1e-5)
    ok &= not bad
    print(f"  skewed curl (+2% shifted copy)   rho = {rho:.10f}   "
          f"{'FAIL -- should exceed 1' if bad else 'ok, detects instability'}")
    print("  self-test", "PASSED" if ok else "FAILED")
    return ok


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="")
    ap.add_argument("--n", type=int, default=32,
                    help="grid for the probe.  MUST be 32 or more: at n=16 the "
                         "reciprocal lattice offers exactly ONE in-band k*d "
                         "(2*pi/16 = 0.393), so the probe state collapses to a "
                         "single-wavelength axis-aligned superposition that is "
                         "harder than the test set and barely varies with the "
                         "seed.  See rollout.allowed_m.")
    ap.add_argument("--d-mm", type=float, default=0.55)
    ap.add_argument("--m-max", type=int, default=4)
    ap.add_argument("--warm", type=int, default=40,
                    help="exact leapfrog steps before the probe, quoted at CFL "
                         "0.99 and scaled by 0.99/cfl so every CFL hands over "
                         "at the same physical time.  With a fixed step count "
                         "the handover lands at a different point of the "
                         "standing-wave cycle and rms|E| swings 6x across the "
                         "sweep, which makes the rows incomparable.")
    ap.add_argument("--warm-mode", choices=["time", "steps"], default="time")
    ap.add_argument("--samples", type=int, default=3,
                    help="independent probe states per CFL.  One state is a "
                         "knife edge: the E/H split oscillates, so a single "
                         "handover phase is not a property of the operator. "
                         "The spread across seeds is reported and is part of "
                         "the result.")
    ap.add_argument("--cfl", type=float, nargs="+", default=[0.99],
                    help="one spectral radius per CFL number")
    ap.add_argument("--iters", type=int, default=180)
    ap.add_argument("--burn", type=int, default=60)
    ap.add_argument("--eps-rel", type=float, default=1e-3,
                    help="finite-difference step, relative to ||state||")
    ap.add_argument("--emp-steps", type=int, default=400,
                    help="0 to skip the nonlinear growth-rate fit")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default="",
                    help="json summary; defaults to spectral_<ckpt>.json")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available()
                    else "cpu")
    a = ap.parse_args()

    print(f"[spectral_dco.py  version {SCRIPT_VERSION}]")
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not a.ckpt:
        raise SystemExit("give --ckpt, or --selftest")

    dev = torch.device(a.device)
    ck = torch.load(a.ckpt, map_location=dev, weights_only=False)
    net = D.DCO(levels=ck["levels"], base=ck["base"],
                head=ck.get("head", "direct")).to(dev)
    net.load_state_dict(ck["state"]); net.eval()
    cm, nm = ck.get("coords", "abs"), ck.get("norm", "max")
    npar = sum(p.numel() for p in net.parameters())
    print(f"loaded {a.ckpt}: L={ck['levels']} base={ck['base']} "
          f"coords={cm} norm={nm} target={ck.get('target', 'analytic')} "
          f"head={ck.get('head', 'direct')}  {npar / 1e6:.2f}M params")

    d = torch.full((1, 3), a.d_mm * 1e-3, device=dev)
    curl_dut = R.dco_curl(net, cm, nm)
    out = {"ckpt": a.ckpt, "n": a.n, "d_mm": a.d_mm, "params": npar,
           "version": SCRIPT_VERSION, "rows": []}

    with torch.no_grad():
      for cfl in a.cfl:
        dt = R.dt_cfl(d, safety=cfl)
        warm = a.warm if a.warm_mode == "steps" \
            else max(1, int(round(a.warm * 0.99 / cfl)))
        print(f"\n  CFL {cfl:4.2f}   handover after {warm} exact steps"
              f"   ({a.samples} probe states)")
        for si in range(a.samples):
            seed = a.seed + 1000 * si
            E0 = R.lattice_ic(1, a.n, d.cpu(), m_max=a.m_max, seed=seed,
                              device=dev)
            Hs0 = torch.zeros_like(E0)
            F_ref = step_factory(R.curl_E_p, d, dt)
            for _ in range(warm):                      # settle, exact operator
                E0, Hs0 = F_ref(E0, Hs0)
            rmsE = float(E0.pow(2).mean().sqrt())

            Cx = R.curl_E_p(E0, d)
            kd = float(R.k_eff_d(E0, Cx, d).mean())
            eps0 = float(D.rel_l2(curl_dut(E0, d), Cx))

            F_dut = step_factory(curl_dut, d, dt)
            rho, _ = power_rho(F_dut, (E0, Hs0), iters=a.iters, burn=a.burn,
                               eps_rel=a.eps_rel, seed=seed)
            rho_ex, _ = power_rho(F_ref, (E0, Hs0), iters=80, burn=30,
                                  eps_rel=a.eps_rel, seed=seed)

            emp, blow = float("nan"), -1
            if a.emp_steps > 0:
                emp, blow, _ = empirical_rho(F_dut, F_ref, (E0, Hs0),
                                             steps=a.emp_steps, seed=seed)
            pred = predicted_blowup(rho, max(eps0, 1e-12))

            warn = ""
            if eps0 > 0.5:
                warn = "   *** eps0 > 0.5: the network is more wrong than the "\
                       "field is large; this checkpoint cannot be probed"
            print(f"    [{si}] k*d {kd:.4f}  rms|E| {rmsE:.4f}  "
                  f"eps0 {eps0:.3e}  rho {rho:.8f}  rho_nl "
                  f"{emp:.8f}  pred {pred:8.1f}  meas "
                  f"{'none' if blow < 0 else blow:>6}{warn}")
            if abs(rho_ex - 1.0) > 1e-3:
                print(f"        *** control (exact curl) = {rho_ex:.8f}, not 1 "
                      f"-- this row is not trustworthy")
            out["rows"].append({"cfl": cfl, "seed": seed, "warm": warm,
                                "rmsE": rmsE, "kd": kd, "eps0": eps0,
                                "rho": rho, "rho_exact": rho_ex,
                                "rho_emp": emp,
                                "pred_blowup": None if math.isinf(pred) else pred,
                                "blowup": blow})

    if len(a.cfl) > 1:
        print("\n  can a smaller time step rescue it?  (mean over probe states)")
        for cfl in a.cfl:
            v = [r["rho"] for r in out["rows"] if r["cfl"] == cfl]
            if not v:
                continue
            mu = float(np.mean(v))
            print(f"    CFL {cfl:4.2f}   rho = {mu:.8f}  "
                  f"(spread {max(v) - min(v):.2e} over {len(v)} states)   "
                  f"{'stable' if mu <= 1 + 1e-6 else 'UNSTABLE'}")

    tag = os.path.splitext(os.path.basename(a.ckpt))[0]
    path = a.out or f"spectral_{tag}.json"
    json.dump(out, open(path, "w"), indent=1)
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
