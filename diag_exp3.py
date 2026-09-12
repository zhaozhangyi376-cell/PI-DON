"""
Stage 5d -- is EXP 3 even a fair test?  ~10 s, no GPU.

    py -3.11 diag_exp3.py

WHY
    EXP 3a is OPEN loop: one forward pass on a warmed-up cavity field, no
    feedback, nothing can accumulate.  It scores relative L2 ~20 for every
    checkpoint we have trained -- baseline, +physics loss, +Yee target,
    +per-wave data.  A number that refuses to move under four different
    training changes is usually telling you about the test, not the model.

THE ONE AXIS THE NETWORK ACTUALLY SEES
    The DCO maps a normalised field to a normalised curl.  After
    dco.normalise, the target's magnitude is

        rms(curl_hat) = rms(curl) * Lc / rms(E) = k_eff * Lc

    where k_eff = rms|curl E| / rms|E| is an rms-weighted effective wavenumber.
    So k_eff * (cell size) is the ONLY combination that sets how large an
    output the network is being asked to produce.  Everything else -- grid
    size, field amplitude, units -- is normalised away.

WHAT THIS MEASURES
    that one number, for: the training distribution, a clean analytic cavity
    mode, and the actual state EXP 3 hands to the network.
"""

import numpy as np

import fdtd
from gen_data import build

SCRIPT_VERSION = "2026-09-09c"


def k_eff_d(E, C, d):
    """rms|curl| / rms|E| * cell size -- dimensionless, see module docstring."""
    return float(np.sqrt((C ** 2).mean() / (E ** 2).mean()) * d)


def main():
    print(f"[diag_exp3.py  version {SCRIPT_VERSION}]")
    print("\nk_eff * cell size -- the only axis the normalised network sees\n")

    for dirs in ("shared", "per-wave"):
        E, C, Dd = build(12, 16, seed=41, dirs=dirs)
        v = [k_eff_d(E[s], C[s], float(np.cbrt(np.prod(Dd[s])))) for s in range(12)]
        print(f"  training data, dirs={dirs:9s}   {min(v):.4f} .. {max(v):.4f}"
              f"   (median {np.median(v):.4f})")

    # a clean analytic TE101 standing wave on the EXP-3 grid: what a cavity
    # mode SHOULD look like on this axis
    side, n = 22.4e-3, 32
    d = side / n
    i = np.arange(n)
    X, _, Z = np.meshgrid(i * d, i * d, i * d, indexing="ij")
    k = np.pi / side
    Ey = np.sin(k * X) * np.sin(k * (Z + 0.5 * d))
    Em = np.stack([np.zeros_like(Ey)] + [Ey] + [np.zeros_like(Ey)])
    cx = -(Ey[:, :, 1:] - Ey[:, :, :-1]) / d
    cz = (Ey[1:, :, :] - Ey[:-1, :, :]) / d
    Cm = np.concatenate([cx.ravel(), cz.ravel()])
    kd_mode = float(np.sqrt((Cm ** 2).mean() / (Em ** 2).mean()) * d)
    print(f"\n  clean TE101 mode, 22.4 mm / 32          {kd_mode:.4f}"
          f"   (theory {np.sqrt(2) * k * d:.4f})")

    # and the state EXP 3 hands over, under each source waveform
    warm = 300
    print(f"\n  EXP-3 handover state after {warm} warm-up steps, by excitation:")
    res = {}
    for mode in ("gauss", "diff", "hard"):
        c = fdtd.PECCavity(side=side, n=n)
        g = fdtd.source_waveform(warm + 150, c.dt,
                                 f_max=0.55 * fdtd.C_PAPER / (2 * d) / 3,
                                 mode=mode)
        for t in range(warm):
            if mode == "hard":
                c.step(src_value=0.0, src_idx=(15, 14, 13))
                c.Ez[(15, 14, 13)] = g[t]
            else:
                c.step(src_value=g[t], src_idx=(15, 14, 13))
        cx, cy, cz = fdtd.curl_E(c.Ex, c.Ey, c.Ez, c.dx, c.dy, c.dz)
        E = np.stack([c.Ex[:, :n, :n], c.Ey[:n, :, :n], c.Ez[:n, :n, :]])
        C = np.stack([cx[:n], cy[:, :n], cz[:, :, :n]])
        res[mode] = (k_eff_d(E, C, d), float(g.sum()),
                     float(np.sqrt((E ** 2).mean())), float(np.abs(c.Ez).max()))
        kd, gs, re, mz = res[mode]
        print(f"    {mode:6s}  sum(source) {gs:+9.2e}   rms|E| {re:.3e}   "
              f"max|Ez| {mz:.3e}   k_eff*d {kd:.4f}"
              + ("   <-- IN BAND" if 0.152 <= kd <= 0.491 else "   <-- OUT OF BAND"))

    bad, good = res["gauss"][0], res["diff"][0]
    lo = 0.152
    print(f"""
  READING
    An ADDITIVE E-field source integrates its own waveform.  A plain Gaussian
    has area {res['gauss'][1]:.1f}, so it leaves a permanent electrostatic blob at
    the source cell.  That blob is CURL FREE: it adds nothing to curl E while
    dominating |E|.  Symptom: rms|E| is frozen at {res['gauss'][2]:.3e} from step
    100 to step 3000 and max|Ez| never moves off {res['gauss'][3]:.2f}.

    Result: the network was handed a field that is ~99% electrostatic and asked
    for a curl {lo / bad:.0f}x smaller than anything in its training band
    ({lo:.3f}..0.491).  A network that emits its habitual output magnitude then
    scores relative L2 ~ {lo / bad:.0f}; EXP 3a measured ~20 for EVERY
    checkpoint -- baseline, +physics loss, +Yee target, +per-wave data -- which
    is what a harness fault looks like, not a model property.

    Fix: use a zero-DC excitation.  The differentiated Gaussian has area
    {res['diff'][1]:+.1e} and lands the handover state at k_eff*d = {good:.4f},
    inside the band.  test_dco.py --src-mode diff is now the default.

    Everything EXP 3 reported before this fix -- the 3a values of ~20 and the
    3b step counts 78 / 88 / 100 / 12 -- must be re-run and must not be quoted.
""")


if __name__ == "__main__":
    main()
