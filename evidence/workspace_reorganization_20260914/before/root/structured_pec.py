"""
三明治结构的前提在 PEC 边界下还成不成立？

    py -3.11 structured_pec.py        # 纯 CPU，几秒钟

为什么这是下一个该验的
    成对替换之所以能保证 rho <= 1，全靠一条恒等式：
        curl_H = curl_E^T            （curl_H 是 curl_E 的伴随）
    有了它，M' = curl_H o T^T o T o curl_E 才等于 curl_E^T (T^T T) curl_E，
    才是对称半正定的三明治。

    但 structured_scale.py 和 structured_material.py 全部跑在【周期盒】上，
    而论文的腔体是【六面 PEC】。周期边界下这条恒等式是精确的（循环卷积的
    转置就是反向循环卷积）；PEC 下边界项会不会破坏它，我们从没验过。

    这不是锦上添花：如果 PEC 下伴随关系不成立，整条成对替换的路线在腔体里
    就用不了，必须先补边界修正。所以先验这一条，再谈别的。

怎么验
    把 PEC 腔体的两个旋度都建成显式矩阵：
      * E 的自由度 = 会被更新的那些（PEC 面上的切向 E 恒为零，不是自由度）
      * H 的自由度 = 全部 Hx, Hy, Hz
    然后直接比较 curl_H 的矩阵与 curl_E 矩阵的转置。
    若相等，再用一个随机稠密的 T 演示三明治确实对称半正定，并跑蛙跳。
"""

import numpy as np

import fdtd

SCRIPT_VERSION = "2026-09-11a"


def spaces(n):
    """(E 自由度形状, H 自由度形状)，E 已去掉 PEC 面。"""
    e = [(n, n - 1, n - 1), (n - 1, n, n - 1), (n - 1, n - 1, n)]
    h = [(n + 1, n, n), (n, n + 1, n), (n, n, n + 1)]
    return e, h


def pack(arrs):
    return np.concatenate([a.ravel() for a in arrs])


def unpack(v, shapes):
    out, i = [], 0
    for s in shapes:
        k = int(np.prod(s))
        out.append(v[i:i + k].reshape(s))
        i += k
    return out


def matrices(n, d):
    """curl_E : 自由 E -> H ；curl_H : H -> 自由 E。都不含 dt。"""
    es, hs = spaces(n)
    NE = sum(int(np.prod(s)) for s in es)
    NH = sum(int(np.prod(s)) for s in hs)

    def full_E(free):
        """把自由度放回完整 Yee 数组，PEC 面填零。"""
        fx, fy, fz = unpack(free, es)
        Ex = np.zeros((n, n + 1, n + 1)); Ex[:, 1:-1, 1:-1] = fx
        Ey = np.zeros((n + 1, n, n + 1)); Ey[1:-1, :, 1:-1] = fy
        Ez = np.zeros((n + 1, n + 1, n)); Ez[1:-1, 1:-1, :] = fz
        return Ex, Ey, Ez

    AE = np.zeros((NH, NE))
    for j in range(NE):
        v = np.zeros(NE); v[j] = 1.0
        AE[:, j] = pack(fdtd.curl_E(*full_E(v), d, d, d))

    AH = np.zeros((NE, NH))
    for j in range(NH):
        v = np.zeros(NH); v[j] = 1.0
        AH[:, j] = pack(fdtd.curl_H(*unpack(v, hs), d, d, d))
    return AE, AH, NE, NH


def main():
    n, d = 5, 1.0e-3
    print(f"[structured_pec.py  version {SCRIPT_VERSION}]")
    print(f"  {n}^3 PEC 腔体，dx = {d * 1e3:.3f} mm\n")

    AE, AH, NE, NH = matrices(n, d)
    print(f"  自由度：E {NE}　H {NH}")

    err = np.abs(AH - AE.T).max() / max(np.abs(AE).max(), 1e-300)
    ok_adj = err < 1e-12
    print(f"\n  1. 伴随恒等式  curl_H =?= curl_E^T")
    print(f"     |curl_H - curl_E^T| / |curl_E| = {err:.3e}   "
          f"-> {'成立' if ok_adj else '【不成立】'}")
    if not ok_adj:
        print("     PEC 下伴随关系被破坏，成对替换在腔体里需要先补边界修正。")
        print("     这是个真结果，后面的演示无意义，停。")
        raise SystemExit(1)

    rng = np.random.default_rng(7)
    T = rng.standard_normal((NH, NH)) * (0.6 / np.sqrt(NH))
    T += np.eye(NH)                       # 从恒等附近出发，但绝非对称
    print(f"\n  2. 取一个随机稠密的 T（{NH}x{NH}，非对称、不与 M 对易）")
    print(f"     |T - T^T| / |T| = "
          f"{np.abs(T - T.T).max() / np.abs(T).max():.3e}   （确认它不对称）")

    M = AE.T @ (T.T @ T) @ AE
    asym = np.abs(M - M.T).max() / max(np.abs(M).max(), 1e-300)
    ev = np.linalg.eigvals(M)
    im, lo, hi = np.abs(ev.imag).max(), ev.real.min(), ev.real.max()
    lim = 2.0 / np.sqrt(max(hi, 1e-30))
    ok_sw = asym < 1e-10 and im < 1e-8 and lo > -1e-6 * max(hi, 1.0)
    print(f"\n  3. 三明治 M' = curl_E^T (T^T T) curl_E")
    print(f"     |M-M^T|/|M| = {asym:.3e}   max|Im lam| = {im:.3e}")
    print(f"     lam in [{lo:+.3e}, {hi:.4g}]   -> "
          f"{'对称半正定' if ok_sw else '【不成立】'}")
    print(f"     允许的 dt <= {lim:.4g} s")

    print(f"\n  4. 对照：同一个 T 只用在一侧")
    M1 = AH @ T @ AE
    a1 = np.abs(M1 - M1.T).max() / max(np.abs(M1).max(), 1e-300)
    e1 = np.linalg.eigvals(M1)
    print(f"     |M-M^T|/|M| = {a1:.3e}   max|Im lam| = "
          f"{np.abs(e1.imag).max():.3e}   最小实部 {e1.real.min():+.3e}")
    print(f"     -> {'对称' if a1 < 1e-10 else '【不对称，保证不成立】'}")

    print(f"\n  5. 真的跑蛙跳（20000 步）")
    for tag, pair in (("成对替换", True), ("只用一侧", False)):
        dt = 0.99 * (lim if pair else 2.0 / np.sqrt(
            max(np.abs(e1.real).max(), 1e-30)))
        E = rng.standard_normal(NE)
        E /= np.abs(E).max()
        H = np.zeros(NH)
        a0, peak, surv = 1.0, 0.0, 20000
        for i in range(1, 20001):
            H = H - dt * (T @ (AE @ E))
            E = E + dt * (AE.T @ (T.T @ H) if pair else AH @ H)
            m = np.abs(E).max()
            peak = max(peak, m)
            if not np.isfinite(m) or m > 1e6 * a0:
                surv = i
                break
        print(f"     {tag:<10s} 存活 {surv:>6d} 步   "
              + (f"峰值 x{peak:.3f}" if surv == 20000 else "发散"))

    # one ASCII line a claim checker can match without regexing prose
    print(f"\nRESULT pec_adjoint_err {err:.3e}")
    print(f"RESULT pec_sandwich_asym {asym:.3e}")
    print("\n" + "=" * 62)
    if ok_adj and ok_sw:
        print("  结论：PEC 边界下伴随恒等式仍然精确成立，三明治结构因此照样")
        print("  对称半正定。成对替换可以直接用在论文的腔体上，不需要边界修正。")


if __name__ == "__main__":
    main()
