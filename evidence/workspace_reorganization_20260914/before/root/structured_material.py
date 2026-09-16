"""
Does the pair-substitution guarantee survive a material interface?

    py -3.11 structured_material.py

    CPU only, float64, a few minutes.  Safe to run while a GPU job is going.

WHY THIS IS THE NEXT THING TO CHECK
    structured_scale.py showed that replacing the curl PAIR --
        curl_E' = T o curl_E ,  curl_H' = curl_H o T^T
    -- makes the wave operator M' = curl_E^T (T^T T) curl_E symmetric positive
    semi-definite for ANY T, so rho <= 1 becomes a CFL condition rather than
    something training has to stumble into.  But every test so far was in
    HOMOGENEOUS VACUUM.  That is the largest unverified claim we have, and the
    paper's own Fig 8 includes an inhomogeneous cavity (a 5x5x5 block of
    eps_r = 4), so it is also the next thing a reader would ask about.

THE ALGEBRA, BEFORE THE MEASUREMENT
    With material the E update carries 1/eps:
        H -= dt * curl_E'(E) ,      E += dt * (1/eps) * curl_H'(H)
    so the wave operator becomes  A = D M' ,  D = diag(1/eps) > 0.
    A is NOT symmetric once eps varies -- but a product of a positive diagonal
    and a symmetric matrix is SIMILAR to a symmetric one:
        D^(-1/2) A D^(1/2) = D^(1/2) M' D^(1/2)   (symmetric PSD)
    Similar matrices share eigenvalues, so A still has a real, non-negative
    spectrum and rho <= 1 still reduces to a CFL condition -- now
    dt <= 2 / sqrt(lambda_max(A)), which is tighter because 1/eps_min scales
    lambda_max.  This is the same energy argument that makes ordinary Yee FDTD
    stable in inhomogeneous lossless media.

    One expectation of mine was BACKWARDS, and the measurement corrects it.
    I wrote above that lambda_max is scaled by 1/eps_min and so the CFL gets
    tighter.  But eps_min is the VACUUM value: adding eps_r > 1 only lowers
    1/eps inside the block, i.e. slows the wave there and RELAXES the local
    limit.  lambda_max stays governed by the vacuum cells, so the CFL barely
    moves -- measured 0.1121 (vacuum) versus 0.1147 (with the block), a
    ratio of 0.977, not the sqrt(eps_r) = 2 I first expected.  Material makes
    the problem easier for stability, not harder.

    That is the prediction.  Below it is measured, together with the
    single-curl control, which should fail.
"""

import numpy as np
import torch

from structured3d import curl_E_yee, curl_H_yee, data
from structured_scale import AdjPair

SCRIPT_VERSION = "2026-09-11a"
torch.set_default_dtype(torch.float64)


def eps_block(n, eps_r=4.0, half=None):
    """eps_r inside a centred block, 1 outside.  (3, n, n, n)."""
    e = torch.ones(3, n, n, n)
    h = half if half is not None else max(n // 4, 1)
    c = n // 2
    s = slice(max(c - h, 0), min(c + h + 1, n))
    e[:, s, s, s] = eps_r
    return e


def build(op, n):
    """Dense matrix of a linear operator on (3, n, n, n)."""
    N = 3 * n ** 3
    A = np.zeros((N, N))
    with torch.no_grad():
        for j in range(N):
            v = torch.zeros(N)
            v[j] = 1.0
            A[:, j] = op(v.reshape(1, 3, n, n, n)).flatten().numpy()
    return A


def report(tag, A, D):
    """D = diag(1/eps) as a flat vector; A = D M'."""
    d = np.sqrt(D)
    B = (A / d[:, None]) * d[None, :]          # D^(-1/2) A D^(1/2)
    asym = np.abs(B - B.T).max() / max(np.abs(B).max(), 1e-300)
    ev = np.linalg.eigvals(A)
    im, lo, hi = (np.abs(ev.imag).max(), ev.real.min(), ev.real.max())
    lim = 2.0 / np.sqrt(max(hi, 1e-30))
    ok = asym < 1e-10 and im < 1e-8 and lo > -1e-8
    print(f"  {tag:<34s} 对称化后 |B-B^T|/|B| = {asym:.2e}")
    print(f"  {'':<34s} max|Im lam| = {im:.2e}   lam in "
          f"[{lo:+.2e}, {hi:.3f}]")
    print(f"  {'':<34s} 允许的 c*dt <= {lim:.4f}   -> "
          f"{'对称半正定，rho<=1 有保证' if ok else '不成立'}")
    return ok, lim


def rollout(step, E, H, steps, a0):
    """Return (survived, final ratio, peak ratio, trace).

    Reporting only the final amplitude cannot distinguish "bounded
    oscillation" from "growing slowly": the field is oscillating, so any
    single snapshot lands wherever the cycle happens to be.  Track the
    running peak and a few checkpoints so boundedness is shown, not asserted.
    """
    peak, trace = 0.0, []
    for i in range(1, steps + 1):
        E, H = step(E, H)
        m = float(E.abs().max())
        peak = max(peak, m)
        if i in (100, 1000, 5000, 10000, 20000):
            trace.append((i, peak / a0))
        if not np.isfinite(m) or m > 1e6 * a0:
            return i, float("inf"), float("inf"), trace
    return steps, float(E.abs().max()) / a0, peak / a0, trace


def main():
    n, eps_r = 6, 4.0
    print(f"[structured_material.py  version {SCRIPT_VERSION}]")
    print(f"  {n}^3 周期盒，中心放一块 eps_r = {eps_r} 的介质"
          f"（论文 Fig 8 的 inhomogeneous cavity 同款设定）\n")

    eps = eps_block(n, eps_r)
    D = (1.0 / eps).flatten().numpy()
    g = torch.Generator().manual_seed(17)
    m = AdjPair(1)
    with torch.no_grad():                      # 非平凡、混合分量的随机 T
        m.w.copy_(torch.randn(3, 3, 3, 3, 3, generator=g) * 0.35)

    print("  --- 均匀真空（对照，已知成立）---")
    ok_v, lim_v = report("成对替换 · eps 均匀",
                         build(lambda E: curl_H_yee(m.Tadj(m.T(curl_E_yee(E)))),
                               n), np.ones_like(D))

    print(f"\n  --- 有介质界面（本次要验的）---")
    invE = 1.0 / eps
    ok_m, lim_m = report(
        "成对替换 · eps 不均匀",
        build(lambda E: invE * curl_H_yee(m.Tadj(m.T(curl_E_yee(E)))), n), D)

    print(f"\n  --- 对照：同一个 T 只用在一侧（= 论文的单旋度替换）---")
    ok_1, lim_1 = report(
        "只换一个旋度 · eps 不均匀",
        build(lambda E: invE * curl_H_yee(m.T(curl_E_yee(E))), n), D)

    print("\n  --- 真的跑一遍蛙跳（20000 步）---")
    E0 = data(1, n, 2, 99)
    a0 = float(E0.abs().max())

    def mk(pair):
        dt = 0.99 * (lim_m if pair else lim_1)

        def step(E, H):
            with torch.no_grad():
                H = H - dt * m.T(curl_E_yee(E))
                c = m.Tadj(H) if pair else H
                return E + dt * invE * curl_H_yee(c), H
        return step

    for tag, pair in (("成对替换", True), ("只换一侧", False)):
        s, r, pk, tr = rollout(mk(pair), E0.clone(), torch.zeros_like(E0),
                               20000, a0)
        print(f"  {tag:<12s} 存活 {s:>6d} 步   "
              + (f"末值 x{r:.3f}   峰值 x{pk:.3f}" if np.isfinite(r)
                 else "发散"))
        if tr and np.isfinite(pk):
            print(f"  {'':<12s} 累计峰值随步数： "
                  + "　".join(f"{i}:x{v:.3f}" for i, v in tr)
                  + "　（不再上升即为有界）")

    print(f"\nRESULT material_pair_ok {1 if ok_m else 0}")
    print(f"RESULT material_onesided_ok {1 if ok_1 else 0}")
    print("\n" + "=" * 66)
    if ok_m and not ok_1:
        print("  结论：介质界面下，成对替换的保证依然成立；单旋度替换依然不成立。")
        print(f"  CFL 几乎不变：均匀真空 c*dt <= {lim_v:.4f}，"
              f"有介质 <= {lim_m:.4f}（比值 {lim_v / lim_m:.3f}）。")
        print("  原因：lambda_max 由 1/eps 最大处即真空区决定，介质只是把块内")
        print("  的波速降下来、局部限制放宽。加介质让稳定性更容易，不是更难。")
    elif not ok_m:
        print("  结论：介质界面下保证【不成立】—— 这是个真结果，说明三明治结构")
        print("  只在均匀介质里对，必须重新推导带材料的版本。")
    else:
        print("  结论异常：单旋度替换居然也通过了，检查测试本身。")


if __name__ == "__main__":
    main()
