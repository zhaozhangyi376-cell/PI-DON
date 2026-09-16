"""
Stage 5 -- the three acceptance experiments, in increasing order of risk.

  EXP 1  single-shot curl accuracy on held-out plane waves      (will work)
  EXP 2  dimension invariance: trained at 16^3, run at 32^3     (should work)
  EXP 3  DCO-in-the-loop cavity: swap the Yee curl for the DCO  (may not work)

EXP 3 is the money shot -- it is the paper's central claim ("replace the spatial
curl operator with a learned one") demonstrated WITHOUT any physics-informed
training loop.  It may well diverge after some number of steps.  That is a
legitimate result, not a failure: report the step count at which it departs and
say why (the DCO was trained on free-space plane waves, the cavity has PEC walls
and standing waves -- an out-of-distribution input).

CAVITY CHOICE
  Cavity A  50 mm / 32 cells -> dx = 1.5625 mm.  Matches the paper and Table II,
            but dx is 2x OUTSIDE the DCO's 0.3-0.8 mm training range, so the DCO
            has to extrapolate.  Use run_fdtd_cavity.py for the pure-physics
            validation against Table II.
  Cavity B  22.4 mm / 32 cells -> dx = 0.70 mm, INSIDE the training range, and
            32^3 != the 16^3 the net was trained on, so it doubles as the
            dimension-invariance demo.  This is the default here.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import os
import time

import numpy as np
import torch

SCRIPT_VERSION = "2026-09-09g"

import dco as D
import fdtd
from gen_data import build as build_data
from train_pidon import yee_curl_t


def load_net(path, device):
    ck = torch.load(resolve_legacy(path), map_location=device, weights_only=False)
    net = D.DCO(levels=ck["levels"], base=ck["base"],
                head=ck.get("head", "direct")).to(device)
    net.load_state_dict(ck["state"])
    net.eval()
    return net, ck


COORD_MODE = "centered"          # overwritten from the checkpoint in main()
NORM_MODE = "max"                # ditto
TARGET = "analytic"              # ditto -- see train_pidon.py --target
DIRS = "shared"                  # ditto -- see gen_data.py --dirs


def score(pred, C_ana, E_np, d_mm):
    """relative L2 against BOTH candidate ground truths, plus nMAE.

    A stage-6 checkpoint trained with --target yee is fitting a slightly
    different operator (the two differ by ~8e-3 relative L2 at these
    resolutions), so scoring it only against the analytic curl would charge it
    for a difference it was told to have.  Report both, always, so numbers from
    every checkpoint stay comparable.
    """
    r_ana = float(D.rel_l2(torch.from_numpy(pred), torch.from_numpy(C_ana)))
    cy = yee_curl_t(torch.from_numpy(np.ascontiguousarray(E_np)).float()[None],
                    torch.tensor(d_mm).float().view(1, 3) * 1e-3)[0].numpy()
    # crop each axis by its OWN length - 1: the grid need not be cubic
    # (paper III-D tests 64x96x16), and using shape[-1] for all three axes
    # silently mis-slices anisotropic grids
    nx, ny, nz = pred.shape[1:]
    r_yee = float(D.rel_l2(torch.from_numpy(pred[:, :nx - 1, :ny - 1, :nz - 1]),
                           torch.from_numpy(cy)))
    # nMAE against the SAME target.  The paper's Table I and III-D are both
    # in MAE/max (that is the only reading that makes its own two tables
    # agree), so relative L2 is NOT comparable to either of them.  How big the
    # gap is depends on the checkpoint -- roughly 3x on pidon_R2_all, roughly
    # 36x on dco_paper32 -- so do not carry a remembered factor around; exp2()
    # measures and prints it.  Either way it is large enough to turn "we are
    # 10x worse than the paper" into its opposite.  Report both, and compare
    # like with like.
    pt = torch.from_numpy(pred)
    if TARGET == "yee":
        nm = float(D.nmae(torch.from_numpy(pred[:, :nx - 1, :ny - 1, :nz - 1]),
                          torch.from_numpy(cy)))
    else:
        nm = float(D.nmae(pt, torch.from_numpy(C_ana)))
    # eq. (5) MRE -- the paper's own metric, and the ONLY one its Table I and
    # section III-D numbers are in.  Computing relL2 or nMAE and comparing
    # those to the paper is a cross-metric error; we made it twice.
    if TARGET == "yee":
        mre = float(D.mre_eq5(
            torch.from_numpy(pred[:, :nx - 1, :ny - 1, :nz - 1]),
            torch.from_numpy(cy)))
    else:
        mre = float(D.mre_eq5(pt, torch.from_numpy(C_ana)))
    return (r_yee if TARGET == "yee" else r_ana), r_ana, r_yee, nm, mre


def coords_for(n, d_mm, device):
    """(1,3,n,n,n) trunk input -- encoding taken from the checkpoint."""
    return D.make_coords(n, d_mm, COORD_MODE, device=device)


def predict(net, E_np, d_mm, device):
    """E_np (3,nx,ny,nz) numpy -> curl, physical units.  Handles non-cubic."""
    shp = tuple(E_np.shape[1:])
    e = torch.from_numpy(np.ascontiguousarray(E_np)).float().unsqueeze(0).to(device)
    x = coords_for(shp, d_mm, device)
    dd = torch.tensor(d_mm, dtype=torch.float32).view(1, 3).to(device)
    with torch.no_grad():
        eh, _, a, Lc = D.normalise(e, None, dd, NORM_MODE)
        return D.denormalise(net(eh, x, D.d_rel_of(dd, Lc)),
                             a, Lc)[0].cpu().numpy()


def report(tag, pred, true):
    p = torch.from_numpy(pred).float()
    t = torch.from_numpy(true).float()
    print(f"  {tag:<34s} relL2 {D.rel_l2(p, t):.3e}   "
          f"nMAE {D.nmae(p, t):.3e}   eq5 {D.mre_eq5(p, t):.2e}")
    return float(D.rel_l2(p, t))


# --------------------------------------------------------------------------- #
def exp1(net, device, n, samples, seed, store=None):
    print(f"\n[EXP 1] single-shot curl on {samples} unseen {n}^3 plane-wave "
          f"samples, dirs={DIRS}")
    E, C, Dd = build_data(samples, n, seed=seed, dirs=DIRS)
    rs, preds, ra, ry, nm, mr = [], [], [], [], [], []
    for s in range(samples):
        pr = predict(net, E[s], (Dd[s] * 1e3).tolist(), device)
        preds.append(pr)
        r, a_, y_, m_, q_ = score(pr, C[s], E[s],
                                  (Dd[s] * 1e3).tolist())
        rs.append(r); ra.append(a_); ry.append(y_)
        nm.append(m_); mr.append(q_)
    print(f"  relative L2 over {samples} samples:  mean {np.mean(rs):.3e}   "
          f"median {np.median(rs):.3e}   worst {np.max(rs):.3e}   "
          f"[target = {TARGET}]")
    print(f"    vs analytic curl {np.mean(ra):.3e}   vs Yee curl "
          f"{np.mean(ry):.3e}   (the two targets differ by ~8e-3)")
    print(f"  nMAE (MAE/max) mean {np.mean(nm):.3e}")
    print(f"  MRE  (eq. 5, THE PAPER'S metric) mean {np.mean(mr):.3e}"
          f"   <- this is what compares to Table I / III-D")
    if store is not None:
        # keep the MEDIAN sample -- not the best, not the worst: an honest one
        k = int(np.argsort(rs)[len(rs) // 2])
        store["exp1_rs"] = np.array(rs)
        store["exp1_E"] = E[k]
        store["exp1_true"] = C[k]
        store["exp1_pred"] = preds[k]
        store["exp1_d_mm"] = Dd[k] * 1e3
        store["exp1_relL2"] = rs[k]
        store["exp1_nmae"] = np.array(nm)
    return np.mean(rs)


def _parse_size(t):
    """'48' -> 48 ;  '64x96x16' -> (64, 96, 16).  Paper III-D uses the latter."""
    if isinstance(t, str) and "x" in t.lower():
        return tuple(int(v) for v in t.lower().split("x"))
    return int(t)


def exp2(net, device, sizes, seed, store=None, train_n=None):
    tn = f"{train_n}^3" if train_n else "its training grid"
    print(f"\n[EXP 2] dimension invariance -- net was trained at {tn} only")
    out, nmae_out, mre_out = {}, {}, {}
    for n in [_parse_size(t) for t in sizes]:
        sd = seed + (n if isinstance(n, int) else sum(n))
        E, C, Dd = build_data(4, n, seed=sd, dirs=DIRS)
        rs, ms, qs = [], [], []
        for s in range(4):
            pr = predict(net, E[s], (Dd[s] * 1e3).tolist(), device)
            r, _, _, m, q = score(pr, C[s], E[s],
                                  (Dd[s] * 1e3).tolist())
            rs.append(r); ms.append(m); qs.append(q)
        key = f"{n}^3" if isinstance(n, int) else "x".join(map(str, n))
        out[key] = float(np.mean(rs))
        nmae_out[key] = float(np.mean(ms))
        mre_out[key] = float(np.mean(qs))
        print(f"  {key:>12s}   relative L2 = {out[key]:.3e}"
              f"   nMAE = {nmae_out[key]:.3e}   MRE = {mre_out[key]:.3e}")
    print("\n  paper III-D (32^3-trained, MRE eq.5): 64^3 4.1e-3, 64x96x16 3.8e-3, "
          "32x64x16 4.7e-3")
    print("  WHICH COLUMN?  The paper calls its metric MRE and defines it in")
    print("  eq. (5) as a MEAN POINTWISE relative error.  Taken literally that")
    print("  cannot be what its numbers are: a curl field crosses zero, the")
    print("  pointwise ratio blows up there, and the mean is dominated by")
    print("  those points -- measured on this checkpoint it gives 0.16-0.77,")
    print("  i.e. 40-200x the paper's 4e-3.  Reaching 4e-3 pointwise would")
    print("  mean 0.4% accuracy even where the true curl is zero.")
    print("  But III-B says the output is 'normalized by the local maximum for")
    print("  each component'.  Normalise first and the denominator becomes the")
    print("  local max, not the pointwise value -- which IS MAE/max.  Under")
    print("  that reading our numbers land at 0.7-1.5x of the paper's, a")
    print("  plausible reproduction.  So: compare the nMAE column, and treat")
    print("  the MRE column as the literal-eq.(5) control that shows why.")
    rat = [out[k] / nmae_out[k] for k in out if nmae_out[k] > 0]
    if rat:
        print(f"  (relative L2 runs {min(rat):.1f}-{max(rat):.1f}x larger than "
              f"nMAE here -- measured, not hard-coded.)")
    if store is not None:
        store["exp2_sizes"] = np.array(list(out.keys()))
        store["exp2_rel"] = np.array(list(out.values()))
        store["exp2_nmae"] = np.array(list(nmae_out.values()))
        store["exp2_mre"] = np.array(list(mre_out.values()))
        store["train_n"] = np.array(train_n if train_n else 0)
    return out


# the waveform itself lives in fdtd.py, next to gaussian_pulse -- see
# fdtd.source_waveform.__doc__ for why its DC content decides the experiment
def source_waveform(nsteps, dt, f_max, mode="diff"):
    return fdtd.source_waveform(nsteps, dt, f_max=f_max, mode=mode)


def k_eff_d(cav, n):
    """rms|curl E| / rms|E| * cell size -- the one axis the network sees."""
    cx, cy, cz = fdtd.curl_E(cav.Ex, cav.Ey, cav.Ez, cav.dx, cav.dy, cav.dz)
    E = np.stack([cav.Ex[:, :n, :n], cav.Ey[:n, :, :n], cav.Ez[:n, :n, :]])
    C = np.stack([cx[:n], cy[:, :n], cz[:, :, :n]])
    return float(np.sqrt((C ** 2).mean() / (E ** 2).mean()) * cav.dx)


def exp3(net, device, side, n, steps, warm, probe, src, src_mode="diff"):
    print(f"\n[EXP 3] DCO-in-the-loop cavity  {side * 1e3:.1f} mm / {n} cells "
          f"-> dx = {side / n * 1e3:.3f} mm   source={src_mode}")
    d_mm = [side / n * 1e3] * 3

    def make():
        c = fdtd.PECCavity(side=side, n=n)
        return c

    ref = make()
    dut = make()
    g = source_waveform(warm + steps, ref.dt,
                        0.55 * fdtd.C_PAPER / (2 * side / n) / 3, src_mode)
    rec_ref = np.zeros(warm + steps)
    rec_dut = np.zeros(warm + steps)

    # ---- identical FDTD warm-up so both start from the same state ---------
    # A LONG warm-up matters.  Right after injection the cavity field is a
    # single hot cell -- a delta, nothing like the smooth plane waves the DCO
    # was trained on, and the prediction is meaningless.  Let the pulse fill
    # the cavity first (a few hundred steps) so the input is a superposition of
    # standing waves, which is at least in the same family as the training data.
    for t in range(warm):
        if src_mode == "hard":
            ref.step(src_value=0.0, src_idx=src); ref.Ez[src] = g[t]
        else:
            ref.step(src_value=g[t], src_idx=src)
        rec_ref[t] = ref.Ez[probe]
    for k in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
        setattr(dut, k, getattr(ref, k).copy())
    rec_dut[:warm] = rec_ref[:warm]
    kd = k_eff_d(ref, n)
    print(f"  warm-up {warm} FDTD steps done, |Ez|max = "
          f"{np.abs(rec_ref[:warm]).max():.3e}")
    print(f"  handover state: k_eff*d = {kd:.4f}   "
          f"(training band 0.152 .. 0.491, clean TE101 mode 0.167)")
    if not 0.10 <= kd <= 0.70:
        print("  *** OUT OF BAND -- the network is being asked for a curl it was\n"
              "  *** never trained to produce, so whatever EXP 3 reports below is\n"
              "  *** a property of this test, not of the operator.  See\n"
              "  *** source_waveform.__doc__ and diag_exp3.py.")

    # ---- EXP 3a: OPEN LOOP -- just measure how well the DCO predicts the
    #      curl of a real cavity field.  No feedback, so this always returns a
    #      number, and it is the honest measure of "does the operator transfer
    #      from free-space plane waves to a PEC cavity".
    core = np.stack([ref.Ex[:, :n, :n], ref.Ey[:n, :, :n], ref.Ez[:n, :n, :]])
    pred0 = predict(net, core, d_mm, device)
    cx0, cy0, cz0 = fdtd.curl_E(ref.Ex, ref.Ey, ref.Ez, ref.dx, ref.dy, ref.dz)
    true0 = np.stack([cx0[:n], cy0[:, :n], cz0[:, :, :n]])
    print("  [3a] open loop -- DCO vs Yee curl on the warmed-up cavity field:")
    r_open = report("      cavity field, all 3 components", pred0, true0)

    # ---- EXP 3b: CLOSED LOOP -- ref keeps using Yee, dut uses the DCO ------
    curl_err = []
    t0 = time.time()
    for t in range(warm, warm + steps):
        if src_mode == "hard":
            ref.step(src_value=0.0, src_idx=src); ref.Ez[src] = g[t]
        else:
            ref.step(src_value=g[t], src_idx=src)
        rec_ref[t] = ref.Ez[probe]

        # --- the one substitution that IS the paper's idea -----------------
        core = np.stack([dut.Ex[:, :n, :n], dut.Ey[:n, :, :n], dut.Ez[:n, :n, :]])
        pred = predict(net, core, d_mm, device)
        cx, cy, cz = fdtd.curl_E(dut.Ex, dut.Ey, dut.Ez, dut.dx, dut.dy, dut.dz)
        curl_err.append(float(D.rel_l2(torch.from_numpy(pred[0]).float(),
                                       torch.from_numpy(cx[:n]).float())))
        cx[:n], cy[:, :n], cz[:, :, :n] = pred[0], pred[1], pred[2]
        # -------------------------------------------------------------------

        kh = dut.dt / dut.mu
        dut.Hx -= kh * cx
        dut.Hy -= kh * cy
        dut.Hz -= kh * cz
        hx, hy, hz = fdtd.curl_H(dut.Hx, dut.Hy, dut.Hz, dut.dx, dut.dy, dut.dz)
        ke = dut.dt / fdtd.EPS0
        dut.Ex[:, 1:-1, 1:-1] += ke * hx
        dut.Ey[1:-1, :, 1:-1] += ke * hy
        dut.Ez[1:-1, 1:-1, :] += ke * hz
        if src_mode == "hard":
            dut.Ez[src] = g[t]
        else:
            dut.Ez[src] += g[t]
        dut.apply_pec()
        rec_dut[t] = dut.Ez[probe]

        if not np.isfinite(rec_dut[t]) or abs(rec_dut[t]) > 1e3 * max(
                np.abs(rec_ref[:warm]).max(), 1e-30):
            print(f"  [3b] blew up at step {t - warm} -- stopping early")
            rec_dut[t:] = np.nan
            break

    seg = slice(warm, warm + steps)
    a, b = rec_ref[seg], rec_dut[seg]
    denom = np.abs(a).max() if np.abs(a).max() > 0 else 1.0
    err = np.abs(b - a) / denom
    err = err[np.isfinite(err)]
    if len(err) == 0:
        err = np.array([np.inf])
    print(f"  {steps} DCO-driven steps in {time.time() - t0:.1f}s "
          f"({(time.time() - t0) / steps * 1e3:.0f} ms/step)")
    print(f"  curl relL2 per step: first {curl_err[0]:.3e}  "
          f"median {np.median(curl_err):.3e}  last {curl_err[-1]:.3e}")
    print(f"  Ez waveform error vs FDTD: mean {err.mean():.3e}  max {err.max():.3e}")
    for thr in (0.01, 0.05, 0.20):
        bad = np.argmax(err > thr) if (err > thr).any() else -1
        print(f"    exceeds {thr * 100:4.0f}% of peak at step "
              f"{'never' if bad < 0 else bad}")
    np.savez("exp3_waveform.npz", ref=rec_ref, dut=rec_dut, warm=warm,
             dt=ref.dt, curl_err=np.array(curl_err))
    print("  saved exp3_waveform.npz  (plot rec_ref vs rec_dut for the slide)")
    return err.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="dco_L3.pt")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--exp1-samples", type=int, default=20)
    ap.add_argument("--exp2-sizes", nargs="*", default=["16", "32", "48"],
                    help="cubic '48' or anisotropic '64x96x16'. Every axis "
                         "must be divisible by 2**(L-1).")
    ap.add_argument("--cavity-side", type=float, default=22.4e-3)
    ap.add_argument("--cavity-n", type=int, default=32)
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--warm", type=int, default=300,
                    help="FDTD steps before the DCO takes over; needs to be "
                         "long enough for the pulse to fill the cavity")
    ap.add_argument("--dirs", choices=["shared", "per-wave", "auto"],
                    default="auto",
                    help="distribution for EXP 1/2. 'auto' takes it from the "
                         "checkpoint. Testing a per-wave-trained net on shared "
                         "data (or the reverse) measures transfer, not "
                         "accuracy -- do that on purpose, not by accident.")
    ap.add_argument("--src-mode", choices=["diff", "hard", "gauss"],
                    default="diff",
                    help="EXP 3 excitation. 'gauss' is the old behaviour and "
                         "leaves an electrostatic blob that makes the test "
                         "meaningless -- see source_waveform.__doc__.")
    ap.add_argument("--skip3", action="store_true")
    a = ap.parse_args()

    print(f"[{__file__.split(chr(92))[-1].split(chr(47))[-1]}  version {SCRIPT_VERSION}]")
    dev = torch.device(a.device)
    net, ck = load_net(a.ckpt, dev)
    global COORD_MODE, NORM_MODE, TARGET
    COORD_MODE = ck.get("coords", "abs")   # old checkpoints predate the flags
    NORM_MODE = ck.get("norm", "max")
    TARGET = ck.get("target", "analytic")
    global DIRS
    DIRS = ck.get("dirs", "shared") if a.dirs == "auto" else a.dirs
    print(f"  trunk coord encoding: {COORD_MODE}   input scaling: {NORM_MODE}"
          f"   training target: {TARGET}   test dirs: {DIRS}"
          f"   head: {ck.get('head', 'direct')}"
          + (f"   lam_div={ck['lam_div']}" if "lam_div" in ck else ""))
    print(f"loaded {a.ckpt}: L={ck['levels']} base={ck['base']} "
          f"trained at {ck['grid']}^3, {sum(p.numel() for p in net.parameters()) / 1e6:.2f}M params")

    store = {}
    exp1(net, dev, ck["grid"], a.exp1_samples, seed=9999, store=store)
    exp2(net, dev, a.exp2_sizes, seed=7777, store=store,
         train_n=ck.get('grid'))
    if not a.skip3:
        exp3(net, dev, a.cavity_side, a.cavity_n, a.steps, a.warm,
             probe=(12, 12, 13), src=(15, 14, 13), src_mode=a.src_mode)
    store["label"] = f"{os.path.splitext(os.path.basename(a.ckpt))[0]}" \
                     f" [{COORD_MODE}/{NORM_MODE}" \
                     + (f"/{TARGET}]" if TARGET != "analytic" else "]")
    out = f"test_results_{os.path.splitext(os.path.basename(a.ckpt))[0]}.npz"
    np.savez(out, **store)
    np.savez("test_results.npz", **store)          # keep the generic name too
    print(f"\nsaved {out}  ->  now run:  py -3.11 make_figs.py")


if __name__ == "__main__":
    main()
