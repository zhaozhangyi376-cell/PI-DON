"""
把 T 做深：多层线性卷积堆叠，伴随精确可求。

    py -3.11 structured_deep.py --selftest        # 先验伴随对不对，几秒
    py -3.11 structured_deep.py --depth 1 2 3     # 训练并对比，CPU 几分钟

为什么不是「把 U-Net 塞进 T」
    三明治 M' = curl_E^T (T^T T) curl_E 要求 T 是【线性】算子 —— T^T 才有定义。
    论文的 U-Net 带 GELU，是非线性的，**它没有转置**。所以「把 U-Net 放进 T」
    这句话我此前说得太随意，直接做是做不了的。

    但这不是损失，反而是这条路线的一个优点：
    **我们要逼近的东西（旋度）本身就是线性算子。** 精确 Yee 旋度就是一个
    3x3x3 卷积、12 个非零权重（exact_stencil.py，相对误差 1.18e-16）。用非线性
    网络去拟合一个线性算子，多出来的表达力全部用在了它不需要的地方 —— 而且
    正是那部分自由度破坏了对称性。

    深度线性卷积堆叠的表达类 = 所有支撑半径 ≤ ΣR 的线性平移不变算子，
    这恰好就是「修正后的旋度」所在的类。层数买到的是更大的等效核（更大的
    感受野、更高阶的色散修正），不是更多的非线性。

    代价要说清楚：多层线性卷积在数学上可以塌缩成一个大核，所以它的表达力
    不超过「一个半径 ΣR 的卷积」。深度在这里买的是**优化路径**（更容易训）
    和**参数效率**，不是新的函数类。下面的对比就是要量出它到底值多少。

伴随怎么求
    单层：卷积的转置 = 用翻转核做相关，并交换输入/输出通道（AdjPair 已在用）。
    多层：(A_k ... A_1)^T = A_1^T ... A_k^T —— 逆序逐层取转置。
    --selftest 用随机向量直接验 <T x, y> = <x, T^T y>，不靠推导。
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from structured3d import curl_E_yee, curl_H_yee, curl_E_spectral, data
from structured_scale import cfl_exact, rel_l2, rho_pair, rho_of, spectral_check

SCRIPT_VERSION = "2026-09-11b"
torch.set_default_dtype(torch.float64)

# CPU 上默认只用了两三个线程，大 batch 的 conv3d 因此慢得没必要。
# 让它用上物理核（留一个给系统和同时在跑的 GPU 任务喂数据）。
try:
    import os as _os
    _n = max((_os.cpu_count() or 4) - 1, 1)
    torch.set_num_threads(_n)
except Exception:
    _n = None


class DeepT(nn.Module):
    """T = A_k o ... o A_1，每个 A 是 3-D 卷积，无激活函数。

    从恒等映射出发：第一层是 delta 核、通道恒等，其余层同理，于是训练起点
    就是原样的 Yee 旋度 —— 和 Sep3D / AdjPair 的约定一致。
    """

    def __init__(self, depth=2, r=1, ch=8):
        super().__init__()
        self.r, self.depth = r, depth
        dims = [3] + [ch] * (depth - 1) + [3]
        self.w = nn.ParameterList()
        for i in range(depth):
            cin, cout = dims[i], dims[i + 1]
            k = torch.zeros(cout, cin, 2 * r + 1, 2 * r + 1, 2 * r + 1)
            for c in range(min(cin, cout)):
                k[c, c, r, r, r] = 1.0
            self.w.append(nn.Parameter(k))

    def _c(self, x, k):
        p = self.r
        return F.conv3d(F.pad(x, (p,) * 6, mode="circular"), k)

    def _ct(self, x, k):
        p = self.r
        return F.conv3d(F.pad(x, (p,) * 6, mode="circular"),
                        k.flip(2, 3, 4).transpose(0, 1))

    def T(self, x):
        for k in self.w:
            x = self._c(x, k)
        return x

    def Tadj(self, x):
        for k in reversed(self.w):
            x = self._ct(x, k)
        return x

    def forward(self, E):
        return self.T(curl_E_yee(E))

    def sandwich(self, E):
        return curl_H_yee(self.Tadj(self.T(curl_E_yee(E))))


# --------------------------------------------------------------------------- #
def selftest():
    print(f"[structured_deep.py  version {SCRIPT_VERSION}]  self-test\n")
    ok = True
    g = torch.Generator().manual_seed(4)

    print("  1. 伴随关系 <T x, y> = <x, T^T y>，用随机向量直接验")
    for depth in (1, 2, 3):
        m = DeepT(depth, r=1, ch=6)
        with torch.no_grad():
            for p in m.w:
                p.add_(torch.randn(p.shape, generator=g) * 0.3)
        x = torch.randn(1, 3, 6, 6, 6, generator=g)
        y = torch.randn(1, 3, 6, 6, 6, generator=g)
        with torch.no_grad():
            a = float((m.T(x) * y).sum())
            b = float((x * m.Tadj(y)).sum())
        rel = abs(a - b) / max(abs(a), abs(b), 1e-30)
        good = rel < 1e-12
        ok &= good
        print(f"     depth={depth}  <Tx,y> = {a:+.10e}   <x,T^Ty> = {b:+.10e}"
              f"   相对差 {rel:.2e}  {'ok' if good else 'FAIL'}")

    print("\n  2. 三明治对称半正定，且 rho <= 1")
    for depth in (1, 2, 3):
        m = DeepT(depth, r=1, ch=6)
        with torch.no_grad():
            for p in m.w:
                p.add_(torch.randn(p.shape, generator=g) * 0.3)
        asym, im, lo, hi = spectral_check(m, n=6)
        lim = 2.0 / np.sqrt(max(hi, 1e-30))
        r = rho_pair(m, n=6, dt=0.99 * lim)
        good = asym < 1e-12 and im < 1e-10 and lo > -1e-9 and r <= 1 + 1e-7
        ok &= good
        print(f"     depth={depth}  asym {asym:.1e}  |Im| {im:.1e}  "
              f"lam_min {lo:+.1e}  c*dt<={lim:.4f}  rho={r:.10f}  "
              f"{'ok' if good else 'FAIL'}")

    print("\n  3. 反向对照：故意只用一侧，rho 必须 > 1")
    m = DeepT(2, r=1, ch=6)
    with torch.no_grad():
        for p in m.w:
            p.add_(torch.randn(p.shape, generator=g) * 0.3)
    one = type("OneSided", (DeepT,), {"Tadj": lambda self, x: x})(2, 1, 6)
    one.w = m.w
    rb = rho_of(one, n=6, dt=0.99 * cfl_exact(one, n=6))
    good = rb > 1 + 1e-6
    ok &= good
    print(f"     只用一侧  rho = {rb:.6f}   "
          f"{'ok，能检出' if good else 'FAIL -- 自检是瞎的'}")

    print(f"\nRESULT deep_selftest {1 if ok else 0}")
    print(f"  self-test {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


def lmax_power(m, n, iters=120, seed=1):
    """幂迭代估 M o S 在【实际网格】上的最大特征值。

    2026-09-11：这个函数是补出来的。此前 CFL 上限取自 spectral_check(n=6)，
    却拿去在 n=16 上跑蛙跳 —— 网格越大能分辨的波矢越多，lambda_max 更大，
    于是 dt 越界。r=1 时差得不多没暴露，r=2 直接 85 步发散，看上去像构造失效，
    其实是我把一个网格的 CFL 用到了另一个网格上。
    在 n=16 上建 12288x12288 的矩阵不现实，幂迭代不建矩阵，几十次就够。
    """
    g = torch.Generator().manual_seed(seed)
    v = torch.randn(1, 3, n, n, n, generator=g)
    v /= v.norm()
    lam = 0.0
    with torch.no_grad():
        for _ in range(iters):
            w = curl_H_yee(m.Tadj(m.T(curl_E_yee(v))))
            lam = float((v * w).sum())
            nw = w.norm()
            if float(nw) < 1e-300:
                return 0.0
            v = w / nw
    return abs(lam)


def train(m, n, kmax, steps, seed, batch, quiet=True):
    E = data(batch, n, kmax, seed)
    C = curl_E_spectral(E)
    Ev = data(max(4, batch // 2), n, kmax, seed + 500)
    Cv = curl_E_spectral(Ev)
    opt = torch.optim.Adam(m.parameters(), lr=3e-3)
    import time as _t
    t0 = _t.time()
    for i in range(steps):
        opt.zero_grad()
        ((m(E) - C) ** 2).mean().backward()
        opt.step()
        # 心跳。大 batch 时一个配置要跑一小时，中途没有任何输出的话，
        # 从外面根本分不清「在算」和「卡死」—— 2026-09-11 就为此白等过一次。
        if (i + 1) % 50 == 0:
            el = _t.time() - t0
            print(f"      {i + 1:4d}/{steps}  train {rel_l2(m(E), C):.3e}"
                  f"  val {rel_l2(m(Ev), Cv):.3e}"
                  f"  {el:.0f}s 已用，约 {el / (i + 1) * steps:.0f}s 总计",
                  flush=True)
    return rel_l2(m(Ev), Cv), rel_l2(m(E), C)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--depth", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--r", type=int, nargs="+", default=[1],
                    help="kernel radius. depth is only worth 1.03x "
                         "(a stack of linear convs collapses to one "
                         "larger kernel), so radius is the thing to "
                         "sweep: it widens the effective stencil, i.e. "
                         "a higher-order dispersion correction")
    ap.add_argument("--ch", type=int, default=12)
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--kmax", type=int, default=5)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--loop", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())

    print(f"[structured_deep.py  version {SCRIPT_VERSION}]")
    print(f"  {a.n}^3，波数 <= {a.kmax}，{a.steps} 步 Adam，{a.batch} 个训练场"
          + (f"，{_n} 个 CPU 线程" if _n else "") + "\n", flush=True)
    print("  正在生成训练数据…", flush=True)
    Ev = data(max(4, a.batch // 2), a.n, a.kmax, a.seed + 500)
    base = rel_l2(curl_E_yee(Ev), curl_E_spectral(Ev))
    print(f"  基线 plain Yee   relL2 {base:.4e}\n")

    rows = []
    for d, rr in [(d, rr) for d in a.depth for rr in a.r]:
        m = DeepT(d, rr, a.ch)
        npar = sum(p.numel() for p in m.parameters())
        print(f"  depth={d}  半径 {rr}  通道 {a.ch}  参数 {npar}")
        v, tr = train(m, a.n, a.kmax, a.steps, a.seed, a.batch)
        asym, im, lo, hi = spectral_check(m, n=6)
        lim = 2.0 / np.sqrt(max(hi, 1e-30))
        rows.append((f"{d}/r{rr}", npar, tr, v, asym, lim, m))
        print(f"      train {tr:.4e}   val {v:.4e}   "
              f"vs Yee {base / v:.2f}x   三明治 asym {asym:.1e}")

    print("\n" + "=" * 74)
    print(f"  {'深度/半径':>9s} {'参数':>7s} {'train':>11s} {'val':>11s} "
          f"{'vs Yee':>8s} {'asym':>10s} {'蛙跳':>12s}")
    print("  " + "-" * 72)
    print(f"  {'Yee':>9s} {0:>7d} {base:>11.3e} {base:>11.3e} "
          f"{1.0:>7.2f}x {'-':>10s} {'稳定(精确)':>12s}")
    for d, npar, tr, v, asym, lim, m in rows:
        surv = "—"
        if a.loop:
            E = data(1, a.n, a.kmax, 99)
            H = torch.zeros_like(E)
            lim_n = 2.0 / np.sqrt(max(lmax_power(m, a.n), 1e-30))
            a0, dt, s = float(E.abs().max()), 0.99 * lim_n, a.loop
            with torch.no_grad():
                for i in range(1, a.loop + 1):
                    H = H - dt * m.T(curl_E_yee(E))
                    E = E + dt * curl_H_yee(m.Tadj(H))
                    x = float(E.abs().max())
                    if not np.isfinite(x) or x > 1e6 * a0:
                        s = i
                        break
            surv = f"{s}" + ("" if s == a.loop else " 发散")
        print(f"  {d:>9s} {npar:>7d} {tr:>11.3e} {v:>11.3e} "
              f"{base / v:>7.2f}x {asym:>10.1e} {surv:>12s}")
    print("=" * 74)

    best = min(rows, key=lambda r: r[3])
    print(f"\n  最好：{best[0]}，比 Yee 好 {base / best[3]:.2f}x，"
          f"三明治非对称度 {best[4]:.1e}")
    print(f"RESULT deep_best_gain {base / best[3]:.4f}")
    print(f"RESULT deep_best_asym {best[4]:.3e}")
    if len(rows) > 1:
        d1 = rows[0][3]
        print(f"\n  相对第一档：{rows[0][0]} val {d1:.3e} -> "
              f"{best[0]} val {best[3]:.3e}，{d1 / best[3]:.2f}x")
        print("  多层线性卷积在数学上可塌缩为单个大核，所以这里买到的是优化")
        print("  路径与参数效率，不是新的函数类 —— 上面这个倍数就是它的实际价值。")


if __name__ == "__main__":
    main()
