"""
把成对替换的算子放进【真正的腔体】，用论文 Table II 的口径评判。

    py -3.11 structured_cavity.py          # 纯 CPU，几分钟

为什么必须做这一条
    此前成对替换的所有证据都是「周期盒 + 随机场 + 跑 N 步不发散」。那只证明
    【稳定】，没证明【准确】—— 一个恒等于零的算子也很稳定。所以它不能和论文
    的 8192 步并列：论文那 8192 步是带精度验证的（Fig 7b 波形、Fig 7c 频谱、
    Table II 谐振频率）。

    本脚本补上可比的那一项：同一个 50 mm PEC 腔体、同样的中心高斯源，
    比【谐振频率对解析解的误差】—— 正是 Table II 的口径。

    数值色散是这里的物理量：Yee 格式在粗网格上会把谐振频率算低一点点
    （我们实测 -0.10% ~ -0.30%）。一个「更准的旋度」如果名副其实，就应该把
    这个偏差压小。压不小，就说明它在平面波上学到的东西没有迁移到腔体。

为什么 T 取逐分量卷积而不是混合分量的
    腔体里 Hx/Hy/Hz 三个数组形状互不相同（Yee 交错），混合分量需要先裁到同一
    形状，会把边界那一层弄脏。逐分量卷积没有这个问题，而三明治的保证对【任意】
    线性 T 都成立，逐分量当然也算。
    padding 用零填充而不是 replicate：零填充的伴随就是「翻转核再做一次零填充
    卷积」，精确可算；replicate 的伴随不是这个形式。下面用随机向量直接验。
"""

import argparse

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import fdtd

SCRIPT_VERSION = "2026-09-11a"
torch.set_default_dtype(torch.float64)


class CompT(nn.Module):
    """逐分量的 3-D 卷积，零填充；伴随 = 翻转核再卷一次。"""

    def __init__(self, r=2):
        super().__init__()
        self.r = r
        k = torch.zeros(3, 1, 2 * r + 1, 2 * r + 1, 2 * r + 1)
        k[:, 0, r, r, r] = 1.0                    # 从恒等出发
        self.k = nn.Parameter(k)

    def _one(self, x, w):
        """接受 (nx,ny,nz) 或 (B,nx,ny,nz)，形状原样返回。"""
        sh = x.shape
        v = x.reshape(-1, 1, *sh[-3:])
        return F.conv3d(v, w.unsqueeze(0), padding=self.r).reshape(sh)

    def T(self, comps):
        return [self._one(c, self.k[i]) for i, c in enumerate(comps)]

    def Tadj(self, comps):
        return [self._one(c, self.k[i].flip(1, 2, 3))
                for i, c in enumerate(comps)]


def adjoint_check(m, shapes, g):
    """<T x, y> =?= <x, T^T y>，不靠推导。"""
    x = [torch.randn(s, generator=g) for s in shapes]
    y = [torch.randn(s, generator=g) for s in shapes]
    with torch.no_grad():
        a = sum(float((p * q).sum()) for p, q in zip(m.T(x), y))
        b = sum(float((p * q).sum()) for p, q in zip(x, m.Tadj(y)))
    return abs(a - b) / max(abs(a), abs(b), 1e-30)


# --------------------------------------------------------------------------- #
def plane_wave_batch(n, d, B, g):
    """周期盒里的无散平面波叠加，以及它的解析旋度。训练 T 用。"""
    i = torch.arange(n, dtype=torch.float64)
    X, Y, Z = torch.meshgrid(i, i, i, indexing="ij")
    E = torch.zeros(B, 3, n, n, n)
    C = torch.zeros(B, 3, n, n, n)
    for b in range(B):
        for _ in range(6):
            mvec = torch.randint(-4, 5, (3,), generator=g).double()
            if mvec.abs().sum() == 0:
                continue
            k = 2 * np.pi * mvec / (n * d)
            a = torch.randn(3, generator=g).double()
            E0 = torch.cross(a, k, dim=0)
            if E0.norm() < 1e-12:
                continue
            E0 = E0 / E0.norm()
            ph = float(torch.rand(1, generator=g)) * 2 * np.pi
            arg = k[0] * X * d + k[1] * Y * d + k[2] * Z * d + ph
            cs, sn = torch.cos(arg), torch.sin(arg)
            for c in range(3):
                E[b, c] += E0[c] * cs
            kxE = torch.cross(k, E0, dim=0)
            for c in range(3):
                C[b, c] += -kxE[c] * sn
    return E, C


def yee_curl_periodic(E, d):
    Ex, Ey, Ez = E[:, 0], E[:, 1], E[:, 2]
    cx = (torch.roll(Ez, -1, 2) - Ez) - (torch.roll(Ey, -1, 3) - Ey)
    cy = (torch.roll(Ex, -1, 3) - Ex) - (torch.roll(Ez, -1, 1) - Ez)
    cz = (torch.roll(Ey, -1, 1) - Ey) - (torch.roll(Ex, -1, 2) - Ex)
    return torch.stack([cx, cy, cz], 1) / d


def train_T(m, n, d, steps, B, g, quiet=True):
    """在平面波上训 T。损失只取内部，不取边界壳层。

    2026-09-11：训练数据是【周期】平面波，靶子用 roll 算的周期旋度；而腔体里
    的 T 用【零填充】卷积。边界那一层训练和使用的假设不一致，r=2 时那是每个
    面 12.5% 的格点，会把学到的核往错误的方向拽。把损失限制在内部（去掉 r+1
    层壳）之后，学到的核只反映体内的行为，搬到腔体里才说得通。
    """
    E, C = plane_wave_batch(n, d, B, g)
    q = m.r + 1
    sl = (slice(None), slice(None), slice(q, -q), slice(q, -q), slice(q, -q))
    opt = torch.optim.Adam(m.parameters(), lr=3e-3)
    y = yee_curl_periodic(E, d)
    base = float(((y - C)[sl] ** 2).mean())
    for it in range(steps):
        opt.zero_grad()
        p = torch.stack(m.T([y[:, k] for k in range(3)]), 1)
        ((p - C)[sl] ** 2).mean().backward()
        opt.step()
    with torch.no_grad():
        p = torch.stack(m.T([y[:, k] for k in range(3)]), 1)
        return float(((p - C)[sl] ** 2).mean()), base


# --------------------------------------------------------------------------- #
def cavity_lmax(m, cav, pair, iters=80, seed=2):
    """幂迭代估腔体里 M' = curl_E^T (T^T T) curl_E 的最大特征值。

    2026-09-11：这是同一类 bug 第二次出现。腔体默认的 dt 是【plain Yee】的
    0.99xCFL，但 T 会放大旋度，lambda_max 因此变大，同一个 dt 就越界 ——
    成对替换在腔体里 28 步「发散」，其实是我没有按它自己的算子重算 CFL。
    structured_deep 里已经栽过一次（r=2 假性发散 85 步），这里必须一并修。
    """
    rng = np.random.default_rng(seed)
    d = (cav.dx, cav.dy, cav.dz)
    E = [rng.standard_normal(v.shape) for v in (cav.Ex, cav.Ey, cav.Ez)]
    nrm = max(np.abs(v).max() for v in E)
    E = [v / nrm for v in E]
    lam = 0.0
    for _ in range(iters):
        cx, cy, cz = fdtd.curl_E(*E, *d)
        if m is not None:
            with torch.no_grad():
                cx, cy, cz = [v.numpy() for v in m.T(
                    [torch.from_numpy(np.ascontiguousarray(v))
                     for v in (cx, cy, cz)])]
        Hs = (cx, cy, cz)
        if m is not None and pair:
            with torch.no_grad():
                Hs = tuple(v.numpy() for v in m.Tadj(
                    [torch.from_numpy(np.ascontiguousarray(v)) for v in Hs]))
        hx, hy, hz = fdtd.curl_H(*Hs, *d)
        W = [np.zeros_like(v) for v in E]
        W[0][:, 1:-1, 1:-1] = hx
        W[1][1:-1, :, 1:-1] = hy
        W[2][1:-1, 1:-1, :] = hz
        num = sum(float((a * b).sum()) for a, b in zip(E, W))
        den = sum(float((a * a).sum()) for a in E)
        lam = abs(num / max(den, 1e-300))
        nw = np.sqrt(sum(float((a * a).sum()) for a in W))
        if nw < 1e-300:
            return 0.0
        E = [v / nw for v in W]
    return lam


def run_cavity(m, side, n, steps, fmax, pair=True, T_total=None):
    """腔体推进。m=None 表示原样 Yee。返回探针时间序列。"""
    cav = fdtd.PECCavity(side=side, n=n)
    if m is not None:
        # 稳定条件是 (c*dt)^2 * lambda_max <= 4，即 dt <= 2/(c*sqrt(lambda))。
        # 第一版漏了 c，算出来的上限大了 3e8 倍，min() 永远取原值，保护形同虚设。
        lam = cavity_lmax(m, fdtd.PECCavity(side=side, n=n), pair)
        if lam > 0:
            cav.dt = min(cav.dt, 0.99 * 2.0 / (fdtd.C0 * np.sqrt(lam)))
    if T_total:
        steps = max(int(round(T_total / cav.dt)), 16)
    g = fdtd.source_waveform(steps, cav.dt, fmax, "gauss")
    c = n // 2
    probe = (min(12, n - 1), min(12, n - 1), min(13, n - 1))
    rec = np.zeros(steps)
    kh, ke = cav.dt / cav.mu, cav.dt / fdtd.EPS0
    d = (cav.dx, cav.dy, cav.dz)
    for t in range(steps):
        cx, cy, cz = fdtd.curl_E(cav.Ex, cav.Ey, cav.Ez, *d)
        if m is not None:
            with torch.no_grad():
                o = m.T([torch.from_numpy(np.ascontiguousarray(v))
                         for v in (cx, cy, cz)])
            cx, cy, cz = [v.numpy() for v in o]
        cav.Hx -= kh * cx
        cav.Hy -= kh * cy
        cav.Hz -= kh * cz
        Hs = (cav.Hx, cav.Hy, cav.Hz)
        if m is not None and pair:
            with torch.no_grad():
                o = m.Tadj([torch.from_numpy(np.ascontiguousarray(v))
                            for v in Hs])
            Hs = tuple(v.numpy() for v in o)
        hx, hy, hz = fdtd.curl_H(*Hs, *d)
        cav.Ex[:, 1:-1, 1:-1] += ke * hx
        cav.Ey[1:-1, :, 1:-1] += ke * hy
        cav.Ez[1:-1, 1:-1, :] += ke * hz
        cav.Ez[c, c, c] = g[t]
        cav.apply_pec()
        rec[t] = cav.Ez[probe]
        if not np.isfinite(rec[t]) or abs(rec[t]) > 1e8:
            return rec[:t + 1], t + 1, cav.dt
    return rec, steps, cav.dt


def modes_table(rec, dt, side, tag):
    ana = fdtd.analytic_modes(side=side)
    pk, _, _ = fdtd.spectrum_peaks(rec, dt, f_lo=3e9, f_hi=12.5e9,
                                   pad=1 << 20, n_peaks=14,
                                   min_sep=250e6)
    errs = []
    print(f"\n  {tag}")
    print("    mode   解析(GHz)    本次(GHz)     误差%")
    for mode, fa in ana.items():
        if not len(pk):
            print(f"    {''.join(map(str, mode))}     {fa/1e9:8.3f}      "
                  f"（无谱峰）")
            continue
        near = min(pk, key=lambda p: abs(p - fa))
        e = 100.0 * (near - fa) / fa
        if abs(e) > 1.0:
            # 中心点源激励不出偶数下标的模式（对称性），谱里根本没有这个峰，
            # 硬取最近峰会配到隔壁模式上去，把平均误差污染掉。
            print(f"    {''.join(map(str, mode))}     {fa/1e9:8.3f}        "
                  f"—        （未激励）")
            continue
        errs.append(abs(e))
        print(f"    {''.join(map(str, mode))}     {fa/1e9:8.3f}   "
              f"{near/1e9:9.3f}   {e:+7.3f}")
    return float(np.mean(errs)) if errs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=31)
    ap.add_argument("--train-n", type=int, default=24,
                    help="cube side used for training; must exceed "
                         "2*(r+1) to leave an interior")
    ap.add_argument("--side", type=float, default=50e-3)
    ap.add_argument("--steps", type=int, default=8192)
    ap.add_argument("--r", type=int, default=2)
    ap.add_argument("--train-steps", type=int, default=600)
    ap.add_argument("--batch", type=int, default=200,
                    help="training fields. 96 -> 300 improved the "
                         "r=2 validation error 6.8x in "
                         "structured_deep; data is the bottleneck")
    ap.add_argument("--fmax", type=float, default=13e9)
    a = ap.parse_args()

    print(f"[structured_cavity.py  version {SCRIPT_VERSION}]")
    print(f"  腔体 {a.side*1e3:.0f} mm / {a.n} 间隔，{a.steps} 步，"
          f"论文 Table II 口径\n")

    g = torch.Generator().manual_seed(3)
    d = a.side / a.n
    m = CompT(a.r)

    rel = adjoint_check(m, [(9, 10, 11)] * 3, g)
    print(f"  1. 伴随自检  |<Tx,y>-<x,T^Ty>| / |.| = {rel:.2e}   "
          f"{'ok' if rel < 1e-12 else 'FAIL'}")

    mse, base = train_T(m, a.train_n, d, a.train_steps, a.batch, g)
    print(f"  2. 在平面波上训 T：Yee 基线 MSE {base:.4e} -> "
          f"训练后 {mse:.4e}（好 {base/mse:.2f}x）")

    # 按【固定物理时间】比，不是固定步数。三个算子各自的 CFL 不同，dt 不同；
    # 若都跑同样步数，dt 小的那个覆盖的时间短、频率分辨率差，谱峰根本对不上 ——
    # 这和 C3 是同一条教训（发散发生在固定物理时间而非固定步数）。
    ref_dt = fdtd.PECCavity(side=a.side, n=a.n).dt
    T_total = a.steps * ref_dt
    print(f"\n  3. 腔体推进，固定物理时长 {T_total*1e9:.2f} ns"
          f"（参照 {a.steps} 步 x {ref_dt*1e12:.4f} ps）")
    res = {}
    for tag, mm, pair in (("plain Yee（参照）", None, True),
                          ("成对替换", m, True),
                          ("同一 T 只用一侧", m, False)):
        rec, surv, dt = run_cavity(mm, a.side, a.n, a.steps, a.fmax, pair,
                                   T_total)
        need = max(int(round(T_total / dt)), 16)
        res[tag] = (rec, surv, dt, need)
        print(f"     {tag:<20s} dt = {dt*1e12:.4f} ps   需 {need:>6d} 步   "
              f"存活 {surv:>6d}"
              + ("" if surv >= need else "   发散"))

    print(f"\n  4. 谐振频率对解析解（Table II 口径）")
    summary = {}
    for tag, (rec, surv, dt, need) in res.items():
        if surv < need:
            print(f"\n  {tag}：发散，无频谱")
            summary[tag] = float("nan")
            continue
        summary[tag] = modes_table(rec, dt, a.side, tag)

    print("\n" + "=" * 62)
    for tag, v in summary.items():
        print(f"  {tag:<20s} 平均 |误差| = "
              + (f"{v:.3f}%" if np.isfinite(v) else "—（发散）"))
    y, s = summary.get("plain Yee（参照）"), summary.get("成对替换")
    if y and s and np.isfinite(y) and np.isfinite(s):
        print(f"\n  成对替换 / plain Yee = {s/y:.3f}"
              + ("   -> 色散误差被压小了" if s < y else
                 "   -> 没有改善，平面波上学到的东西没迁移到腔体"))
        print(f"RESULT cavity_yee_err {y:.4f}")
        print(f"RESULT cavity_pair_err {s:.4f}")


if __name__ == "__main__":
    main()
