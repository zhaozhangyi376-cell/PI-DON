"""
Stage 2 of the paper: Algorithm 1.  THIS IS THE PART WE HAD NEVER BUILT.

    py -3.11 pidon_solve.py --steps 200 --init dco_paper32.pt
    py -3.11 pidon_solve.py --steps 200 --init random      # the Fig 8 control

WHAT ALGORITHM 1 ACTUALLY IS  (paper IV-A, and see PAPER_NOTES.md)
    Not "run the trained DCO inside a leapfrog".  That is what test_dco.py's
    EXP 3 does, and it diverges at 158 steps -- but the paper never claims it
    works, because the paper does something else entirely:

        while N < Nmax:
            Train  grad x H   using the physics-informed loss
            Update E          using eps and dt
            Implement excitation
            Train  grad x E   using eq. (7), with boundary conditions
            Update H          using mu and dt

    The DCO's WEIGHTS ARE RE-OPTIMISED AT EVERY TIME STEP, by backprop, until
    the loss drops below 1e-4 (paper's own stopping rule).  And eq. (7), the
    "physics-informed loss", is literally the squared difference between the
    network's output and the Yee finite-difference stencil written out term by
    term.  So each step drives the network back onto the exact discrete curl.

    That is why it does not blow up.  It is not a learnt operator evolving
    freely; it is an optimisation that re-fits the exact curl every step.
    The paper pays for it in time: 583 s on an A6000 versus 6.47 s for FDTD on
    a CPU, for the same cavity -- about 90x slower.

WHAT THIS SCRIPT REPRODUCES
    * Fig 7(b)(c) / Table II : the 50 mm cavity, 32 cells, centre Gaussian
      source, PEC on all six faces, compared against our own FDTD.
    * Fig 8 : cumulative training loss per time step, pretrained-DCO
      initialisation versus random initialisation.  Note what that figure
      actually plots -- "the total loss summed over all training epochs at
      each time step", i.e. HOW MUCH OPTIMISATION EACH STEP COSTS, not
      whether the field diverges.  Reproducing it means reproducing the
      optimisation cost curve.

ONE DOCUMENTED DEVIATION
    Our DCO maps (3, n, n, n) -> (3, n, n, n), while the cavity's Yee arrays
    have a different shape per component (Hx is (n+1, n, n) and so on).  As in
    EXP 3, the network supplies the first n slices of each component and the
    remaining boundary slice keeps its exact Yee value.  The physics-informed
    loss is therefore computed over the region the network actually predicts.
"""

import argparse
import json
import os
import time

import numpy as np
import torch

import dco as D
import fdtd

SCRIPT_VERSION = "2026-09-10a"


# --------------------------------------------------------------------------- #
def to_t(a, dev):
    return torch.from_numpy(np.ascontiguousarray(a)).float().to(dev)


def core_of(Fx, Fy, Fz, n):
    """The (3, n, n, n) block the network sees, from three Yee arrays."""
    return torch.stack([Fx[:n, :n, :n], Fy[:n, :n, :n], Fz[:n, :n, :n]])


class Solver:
    def __init__(self, a, dev):
        self.a, self.dev = a, dev
        self.n = a.n
        self.cav = fdtd.PECCavity(side=a.side, n=a.n, dt=a.dt)
        self.dt = self.cav.dt
        self.d_mm = [self.cav.dx * 1e3] * 3

        self.E = [torch.zeros(s, device=dev) for s in
                  ((a.n, a.n + 1, a.n + 1), (a.n + 1, a.n, a.n + 1),
                   (a.n + 1, a.n + 1, a.n))]
        self.H = [torch.zeros(s, device=dev) for s in
                  ((a.n + 1, a.n, a.n), (a.n, a.n + 1, a.n),
                   (a.n, a.n, a.n + 1))]

        self.net, self.tag = self._make_net()
        self.opt = torch.optim.Adam(self.net.parameters(), lr=a.lr)
        # The U-net halves the grid at each level, so the side must be a
        # multiple of 2^(levels-1) or the skip connection meets a tensor one
        # cell short on the way back up.  The paper's cavity is 31 intervals
        # (see --n), which is odd, so pad up to the next multiple and crop the
        # prediction back.  Padding is replicate: the slab is cropped away
        # again and only reaches the outermost predicted cell through the
        # convolution's receptive field.
        q = 2 ** (self.levels - 1)
        self.np_ = ((a.n + q - 1) // q) * q
        self.pad = self.np_ - a.n
        self.coords = D.make_coords((self.np_,) * 3, self.d_mm,
                                    self.coord_mode, device=dev)
        self.d_t = torch.tensor(self.d_mm).float().view(1, 3).to(dev)

    def _make_net(self):
        a = self.a
        if a.init in ("random", "rand", "scratch"):
            self.coord_mode, self.norm_mode = a.coords, a.norm
            self.levels = a.levels
            net = D.DCO(levels=a.levels, base=a.base).to(self.dev)
            return net, "random"
        ck = torch.load(a.init, map_location=self.dev, weights_only=False)
        self.coord_mode = ck.get("coords", a.coords)
        self.norm_mode = ck.get("norm", a.norm)
        self.levels = ck["levels"]
        net = D.DCO(levels=ck["levels"], base=ck["base"],
                    head=ck.get("head", "direct")).to(self.dev)
        net.load_state_dict(ck["state"])
        return net, os.path.splitext(os.path.basename(a.init))[0]

    # -- the network's curl, in physical units ----------------------------- #
    def predict(self, core):
        e = core.unsqueeze(0)
        if self.pad:
            e = torch.nn.functional.pad(e, (0, self.pad) * 3, mode="replicate")
        eh, _, sc, Lc = D.normalise(e, None, self.d_t, self.norm_mode)
        out = D.denormalise(self.net(eh, self.coords,
                                     D.d_rel_of(self.d_t, Lc)), sc, Lc)[0]
        n = self.n
        return out[:, :n, :n, :n] if self.pad else out

    # -- eq. (7): the target IS the Yee stencil ---------------------------- #
    def yee_curl_E(self):
        cx, cy, cz = fdtd.curl_E(*[t.cpu().numpy() for t in self.E],
                                 self.cav.dx, self.cav.dy, self.cav.dz)
        return [to_t(c, self.dev) for c in (cx, cy, cz)]

    def yee_curl_H(self):
        cx, cy, cz = fdtd.curl_H(*[t.cpu().numpy() for t in self.H],
                                 self.cav.dx, self.cav.dy, self.cav.dz)
        return [to_t(c, self.dev) for c in (cx, cy, cz)]

    def inner_train(self, field, target):
        """Optimise the DCO until eq.(7)'s loss < tol.  Returns
        (iters, final_loss, summed_loss, prediction, crop) -- the summed loss
        is Fig 8's y-axis.

        The three Yee curl components do not share a shape: curl_E gives
        (n+1,n,n)/(n,n+1,n)/(n,n,n+1) and curl_H gives
        (n,n-1,n-1)/(n-1,n,n-1)/(n-1,n-1,n).  The network emits one cube, so
        the loss is taken on the largest block all three share, and the slices
        outside it keep their exact Yee value (the deviation documented at the
        top of this file).
        """
        n = self.n
        core = core_of(*field, n)
        m = tuple(min(t.shape[k] for t in target) for k in range(3))
        m = tuple(min(v, n) for v in m)
        tgt = torch.stack([t[:m[0], :m[1], :m[2]] for t in target])
        # Step 1 has H identically zero, so its curl is zero: the relative
        # denominator would be 0 and, worse, rms normalisation of an all-zero
        # input divides by zero and poisons the weights with NaN.  A zero
        # field has a zero curl exactly -- no network needed, nothing to
        # learn from, so return it and leave the weights untouched.
        if float(core.abs().max()) == 0.0 or float(tgt.abs().max()) == 0.0:
            return 0, 0.0, 0.0, torch.zeros_like(tgt), m
        # Scale.  Eq. (7) is written as a plain SUM of squares and IV-A stops
        # the inner training below 1e-4.  Taken literally that threshold is
        # scale-dependent, and at the start of a cavity run the fields are
        # ~0, so the sum is ~1e-9 and the rule is satisfied on iteration 1 --
        # even by a randomly initialised network.  The run then trains
        # nothing and the Fig 8 control would be meaningless.
        # Fig 8's own axis is labelled "Cumulative M.S.E." and starts near
        # 1.0, which an untrained network reaches only if the quantity is
        # NORMALISED.  So the default here is the relative form; --tol-mode
        # abs gives the literal reading of eq. (7) for comparison.
        den = tgt.pow(2).sum().clamp_min(1e-30)
        tot, it, last = 0.0, 0, float("inf")
        for it in range(1, self.a.max_inner + 1):
            self.opt.zero_grad()
            pred = self.predict(core)[:, :m[0], :m[1], :m[2]]
            sq = (pred - tgt).pow(2).sum()
            loss = sq / den if self.a.tol_mode == "rel" else sq
            last = float(loss.detach())
            tot += last
            if last < self.a.tol:
                break
            loss.backward()
            self.opt.step()
        with torch.no_grad():
            out = self.predict(core)[:, :m[0], :m[1], :m[2]]
        return it, last, tot, out, m

    def step(self, g_t):
        n, rec = self.n, {}

        # 4-5.  train curl H, then update E
        ch = self.yee_curl_H()
        it, l, tot, pred, m = self.inner_train(self.H, ch)
        rec["itH"], rec["lossH"], rec["cumH"] = it, l, tot
        ke = self.dt / fdtd.EPS0
        for k in range(3):
            ch[k][:m[0], :m[1], :m[2]] = pred[k]
        self.E[0][:, 1:-1, 1:-1] += ke * ch[0]
        self.E[1][1:-1, :, 1:-1] += ke * ch[1]
        self.E[2][1:-1, 1:-1, :] += ke * ch[2]

        # 6.  excitation -- hard source at the centre cell, as in IV-A
        c = n // 2
        self.E[2][c, c, c] = g_t
        self.apply_pec()

        # 7-8.  train curl E, then update H
        ce = self.yee_curl_E()
        it, l, tot, pred, m = self.inner_train(self.E, ce)
        rec["itE"], rec["lossE"], rec["cumE"] = it, l, tot
        kh = self.dt / self.cav.mu
        for k in range(3):
            ce[k][:m[0], :m[1], :m[2]] = pred[k]
        for k in range(3):
            self.H[k] -= kh * ce[k]
        return rec

    def apply_pec(self):
        """Tangential E = 0 on all six faces.

        The paper says PECs are "modeled in the PI-DON by setting the
        predicted tangential components on PECs to zero" -- that is a
        condition on E, not on the curl components, so it belongs here after
        the E update rather than inside the curl loss.  (First version of this
        file masked faces of the predicted CURL instead, which is a different
        and wrong constraint.)
        """
        Ex, Ey, Ez = self.E
        Ex[:, 0, :] = Ex[:, -1, :] = Ex[:, :, 0] = Ex[:, :, -1] = 0.0
        Ey[0, :, :] = Ey[-1, :, :] = Ey[:, :, 0] = Ey[:, :, -1] = 0.0
        Ez[0, :, :] = Ez[-1, :, :] = Ez[:, 0, :] = Ez[:, -1, :] = 0.0


# --------------------------------------------------------------------------- #
def diagnose(hist, a):
    """把一次发散跑成一个定量结论，而不是只报一个 nan。

    2026-09-11 的发现：在正确的网格（n=31，dt = 0.99xCFL）上参考 FDTD 完好，
    而 PI-DON 的解仍指数增长 —— 但内层损失一直很小（1e-3~1e-2）。两者并不
    矛盾：若网络输出相对真值有系统性的 eps 偏差，闭环每步放大 (1+eps)，而
    相对损失只有 eps^2 量级，看上去「很小」。

    实测：nMAE 轨迹拟合出每步增益 1.0156（+1.56%），而 sqrt(损失) = 5.5%，
    同量级 —— 【每步的拟合残差直接充当了放大率】。

    于是得到与 C8 同一条定律：闭环要跑 N 步，每步相对误差必须 <= 1/N。
    冻结算子时它表现为 rho-1 <= 1/N；每步重训时它表现为拟合残差 <= 1/N。
    两条路殊途同归。
    """
    ok = [r for r in hist if np.isfinite(r["nmae"]) and r["nmae"] > 0]
    if len(ok) < 8:
        return
    x = np.array([r["step"] for r in ok], float)
    y = np.log(np.array([r["nmae"] for r in ok], float))
    m = x > x.max() * 0.15
    if m.sum() < 5:
        return
    k = float(np.polyfit(x[m], y[m], 1)[0])
    g = float(np.exp(k))
    ls = [r["lossE"] for r in ok if np.isfinite(r["lossE"])]
    loss = float(np.median(ls)) if ls else float("nan")
    print("\n  --- 误差增长诊断 ---")
    print(f"  每步增益 g = {g:.5f}（每步 {100 * (g - 1):+.2f}%），"
          f"等效 rho-1 = {g - 1:.3e}")
    print(f"  内层损失中位数 {loss:.2e}  ->  每步相对误差 {np.sqrt(loss):.3f}")
    if g > 1 and k > 0:
        need = 1.0 / a.steps
        print(f"  误差翻倍需 {np.log(2) / k:.0f} 步")
        print(f"  要跑完 {a.steps} 步，每步相对误差需 <= 1/N = {need:.2e}，"
              f"即损失 <= {need ** 2:.2e}")
        print(f"  当前差 {loss / need ** 2:.1e} 倍 —— 瓶颈是每步拟合的精度，"
              f"不是时间步、也不是网格")
    print(f"RESULT stepgain {g:.6f}")


def calibrate(a, dev):
    """Sweep the inner learning rate.  Algorithm 1 is only Algorithm 1 if the
    inner training actually reaches the stopping tolerance; otherwise it is
    just "N gradient steps per time step" and the paper's stability argument
    does not apply.

    2026-09-11, first GPU run: every step used the full 20 inner iterations
    and the loss sat at 0.04-0.27, never near 1e-4.  lr was 1e-4 -- copied
    from the paper's STAGE-1 setting, where it runs for 1000 epochs.  The
    paper does not state a stage-2 inner learning rate, so it is ours to
    choose, and 1e-4 over a handful of iterations is simply too slow.
    """
    print("  lr sweep: does the inner training reach the tolerance at all?")
    print(f"  {a.steps} time steps each, tol {a.tol:.0e}, "
          f"max {a.max_inner} inner iters\n")
    print(f"  {'lr':>8s} {'max it':>7s} {'reached tol':>12s} "
          f"{'mean iters':>11s} {'mean loss':>11s} {'s/step':>8s}  "
          f"{'nMAE@end':>10s}")
    print("  " + "-" * 76)
    best = None
    grid = [(lr, it) for lr in (a.calib or [a.lr])
            for it in (a.calib_iters or [a.max_inner])]
    for lr, mi in grid:
        b = argparse.Namespace(**vars(a))
        b.lr, b.max_inner = lr, mi
        s = Solver(b, dev)
        g = fdtd.source_waveform(a.steps, s.dt, a.fmax, "gauss")
        c = a.n // 2
        ref = fdtd.PECCavity(side=a.side, n=a.n, dt=a.dt)
        hit, its, ls, t0 = 0, [], [], time.time()
        for t in range(a.steps):
            r = s.step(float(g[t]))
            ref.step(src_value=0.0, src_idx=(c, c, c))
            ref.Ez[c, c, c] = g[t]
            ref.apply_pec()
            for k in ("H", "E"):
                # Step 1's curl H is the zero field: inner_train returns
                # (0 iters, 0 loss) without training.  Counting it as
                # "reached the tolerance" reported 2% when the true answer
                # was 0% -- one trivial sub-step out of forty.  Skip it.
                if r["it" + k] == 0:
                    continue
                its.append(r["it" + k])
                ls.append(r["loss" + k])
                hit += r["it" + k] < b.max_inner
        dt_s = (time.time() - t0) / a.steps
        e = s.E[2].detach().cpu().numpy()
        nm = float(np.abs(e - ref.Ez).mean() / (np.abs(ref.Ez).max() + 1e-30))
        frac = hit / len(its)
        print(f"  {lr:>8.0e} {mi:>7d} {frac:>11.0%} {np.mean(its):>11.1f} "
              f"{np.mean(ls):>11.2e} {dt_s:>7.2f}s {nm:>10.2e}")
        if best is None or np.mean(ls) < best[1]:
            best = (lr, float(np.mean(ls)), frac, mi)
    print(f"\n  best mean loss at lr = {best[0]:.0e}, max_inner = {best[3]} "
          f"({best[1]:.2e}, reached tol on {best[2]:.0%} of real sub-steps)")
    if best[2] < 0.5:
        print("  STILL not reaching the tolerance on most sub-steps.  Then the")
        print("  bottleneck is not the learning rate -- raise --max-inner, or")
        print("  the network cannot represent the cavity curl that closely and")
        print("  that is itself the finding.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--n", type=int, default=31,
                    help="网格【间隔】数。论文说 50 mm 腔体 'discretized into "
                         "32 cells'，那是 32 个网格【点】= 31 个间隔："
                         "dx = 1.6129 mm 时 0.99xCFL = 3.0751 ps，正是论文给的"
                         " 3.075 ps。用 32 会让 dt 越过 Courant 限，"
                         "连参考 FDTD 都会溢出。")
    ap.add_argument("--side", type=float, default=50e-3)
    ap.add_argument("--dt", type=float, default=3.075e-12,
                    help="论文 IV-A 的值。配合 --n 31 时它就等于 0.99xCFL；"
                         "传 0 则直接用 0.99xCFL（两者一致）。")
    ap.add_argument("--init", default="dco_paper32.pt",
                    help="pretrained checkpoint, or 'random' for the Fig 8 "
                         "control")
    ap.add_argument("--tol", type=float, default=1e-4,
                    help="paper IV-A: stop the inner training below this")
    ap.add_argument("--tol-mode", choices=["rel", "abs"], default="rel",
                    help="rel = |pred-yee|^2 / |yee|^2 (scale free, default); "
                         "abs = eq.(7)'s literal sum of squares")
    ap.add_argument("--max-inner", type=int, default=50)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--levels", type=int, default=4)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--coords", default="cellsize")
    ap.add_argument("--norm", default="rms")
    ap.add_argument("--fmax", type=float, default=15e9)
    ap.add_argument("--calib", type=float, nargs="+", default=[],
                    help="sweep these inner learning rates instead of doing a "
                         "full run, and report whether the tolerance is ever "
                         "reached")
    ap.add_argument("--calib-iters", type=int, nargs="+", default=[],
                    help="sweep these --max-inner values too; the cross "
                         "product with --calib is run")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.dt == 0:
        a.dt = None
    if a.calib:
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[pidon_solve.py  version {SCRIPT_VERSION}]  calibration\n")
        raise SystemExit(calibrate(a, dev))

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[pidon_solve.py  version {SCRIPT_VERSION}]  Algorithm 1")
    s = Solver(a, dev)
    print(f"  cavity {a.side * 1e3:.1f} mm / {a.n} cells  dx = "
          f"{s.cav.dx * 1e3:.4f} mm   dt = {s.dt * 1e12:.4f} ps")
    cfl = fdtd.cfl_dt(s.cav.dx, s.cav.dy, s.cav.dz, safety=1.0)
    print(f"  CFL limit {cfl * 1e12:.4f} ps  ->  dt / CFL = {s.dt / cfl:.4f}"
          + ("   *** 超出 Courant 限，连参考 FDTD 都会发散，"
             "腔体请用 --n 31" if s.dt > cfl else "   ok"))
    print(f"  init = {s.tag}   coords={s.coord_mode} norm={s.norm_mode}   "
          f"{sum(p.numel() for p in s.net.parameters()) / 1e6:.2f}M params")
    print(f"  inner training: stop below {a.tol:.0e}, at most {a.max_inner} "
          f"iters, lr {a.lr:g}   device {dev}\n")

    ref = fdtd.PECCavity(side=a.side, n=a.n, dt=a.dt)
    g = fdtd.source_waveform(a.steps, s.dt, a.fmax, "gauss")
    c = a.n // 2
    hist, t0 = [], time.time()
    for t in range(a.steps):
        rec = s.step(float(g[t]))
        ref.step(src_value=0.0, src_idx=(c, c, c))
        ref.Ez[c, c, c] = g[t]
        ref.apply_pec()
        e_dut = s.E[2].detach().cpu().numpy()
        e_ref = ref.Ez
        den = np.abs(e_ref).max() + 1e-30
        rec["step"] = t
        rec["probe_dut"] = float(e_dut[c, c, c])
        rec["probe_ref"] = float(e_ref[c, c, c])
        rec["nmae"] = float(np.abs(e_dut - e_ref).mean() / den)
        rec["cum"] = rec["cumH"] + rec["cumE"]
        hist.append(rec)
        if t < 5 or (t + 1) % max(a.steps // 20, 1) == 0:
            print(f"  step {t + 1:>5d}  inner {rec['itH']:>3d}/{rec['itE']:>3d}"
                  f"  loss {rec['lossH']:.2e}/{rec['lossE']:.2e}"
                  f"  cum {rec['cum']:.3e}  nMAE {rec['nmae']:.3e}"
                  f"  {(time.time() - t0) / (t + 1):.2f}s/step")

    diagnose(hist, a)
    out = a.out or f"pidon_solve_{s.tag}.json"
    json.dump({"version": SCRIPT_VERSION, "init": s.tag, "n": a.n,
               "side": a.side, "dt": s.dt, "tol": a.tol, "lr": a.lr,
               "steps": a.steps, "rows": hist}, open(out, "w"))
    tot = time.time() - t0
    print(f"\n  {a.steps} steps in {tot:.0f} s  ({tot / a.steps:.2f} s/step)")
    print(f"  mean inner iters: curlH {np.mean([r['itH'] for r in hist]):.1f}"
          f"   curlE {np.mean([r['itE'] for r in hist]):.1f}")
    print(f"  final nMAE vs FDTD {hist[-1]['nmae']:.3e}")
    print(f"  saved {out}")
    print("\n  Fig 8's y-axis is the 'cum' column -- the loss summed over all"
          "\n  inner epochs at each time step.  Run this again with "
          "--init random\n  to get the control curve.")


if __name__ == "__main__":
    main()
