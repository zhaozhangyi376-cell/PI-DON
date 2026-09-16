"""
Stage 4 -- train the DCO.

Paper section III-C hyper-parameters (kept exactly where possible):
    optimiser   Adam
    lr          1e-4
    batch       32          -> 16 at 16^3 [MVP, smaller grid -> smaller batch is fine]
    epochs      1000        -> 300        [MVP]
    split       80 / 20     same

Acceptance target (paper Table I, at 32^3 with 1000 samples):
    L=2  MRE 1.4e-2      L=3  MRE 5.3e-3
    L=4  MRE 7.7e-4      L=5  MRE 7.9e-4
At the MVP settings (16^3, 300 samples) do NOT expect 7.7e-4.  Anything at or
below ~1e-2 already demonstrates the operator has been learnt; report the number
you actually get and say what was reduced.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import time

import numpy as np
import torch

SCRIPT_VERSION = "2026-09-09a"
NORM = "max"      # set from --norm in main()

import dco as D
from gen_data import coords_mm


def load(path, device, coord_mode="centered"):
    z = np.load(resolve_legacy(path))
    E = torch.from_numpy(z["E"])
    C = torch.from_numpy(z["C"])
    d = torch.from_numpy(z["D"]) * 1e3            # metres -> mm
    n = int(z["n"])
    # trunk input -- see dco.make_coords for why the encoding matters
    coords = torch.cat([D.make_coords(n, d[s], coord_mode) for s in range(len(d))])
    return E.to(device), C.to(device), coords.to(device), d.to(device), n


def evaluate(net, E, C, X, d, bs=8):
    """Three error metrics on the PHYSICAL, un-normalised curl.

    Returns (rel_l2, mre_eq5, nmae, per_component_rel_l2).
    See dco.py for why eq. (5) taken literally cannot reach the paper's numbers.
    """
    net.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(E), bs):
            e, x, dd = E[i:i + bs], X[i:i + bs], d[i:i + bs]
            eh, _, a, Lc = D.normalise(e, None, dd, NORM)
            preds.append(D.denormalise(net(eh, x), a, Lc))
        P = torch.cat(preds)
        r = D.rel_l2(P, C).item()
        m = D.mre_eq5(P, C).item()
        # nMAE 必须【逐样本】算再平均。整批一起算时，分母 true.abs().max()
        # 取的是全体样本的最大值，而样本幅度各不相同 —— 分母被最大的那个样本
        # 抬高，数字因此偏小约 6 倍（2026-09-11 实测：整批 6.6e-4 对逐样本
        # 4.4e-3，同一个网络）。论文式 (5) 是对单个测试算例定义的，逐样本才
        # 与它、以及与 test_dco 的 EXP1/EXP2 口径一致。
        na = float(torch.stack([D.nmae(P[k:k + 1], C[k:k + 1])
                                for k in range(len(C))]).mean())
        per = [D.rel_l2(P[:, k], C[:, k]).item() for k in range(3)]
    net.train()
    return r, m, na, per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data_16.npz")
    ap.add_argument("--levels", type=int, default=3)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4,
                    help="paper uses 1e-4 for 1000 epochs; 3e-4 + cosine is "
                         "faster at MVP scale")
    ap.add_argument("--loss", choices=["rel", "mse"], default="rel",
                    help="rel = per-sample relative MSE (scale invariant). "
                         "The curl magnitude spans ~1000x across samples "
                         "because k in (0,1048]; plain MSE lets the large-k "
                         "samples swamp the small-k ones and converges slowly.")
    ap.add_argument("--out", default="dco_L3.pt")
    ap.add_argument("--init", default="",
                    help="warm-start from an existing checkpoint, e.g. to "
                         "finish a run that was killed part-way.  levels/base/"
                         "coords/norm must match; the LR schedule restarts "
                         "from scratch, so pass a smaller --lr than the "
                         "original run used.")
    ap.add_argument("--ckpt-every", type=int, default=25,
                    help="write --out every N epochs so a long run that gets "
                         "killed still leaves usable weights.  0 disables.")
    ap.add_argument("--norm", choices=["max", "rms"], default="max",
                    help="input scaling. 'max' is not grid-size invariant "
                         "(the max of a random field grows with voxel count); "
                         "'rms' is. See dco.normalise.")
    ap.add_argument("--coords", choices=["abs", "centered", "cellsize"],
                    default="centered",
                    help="trunk input encoding. 'abs' is the literal reading of "
                         "the paper and does NOT transfer across grid sizes; "
                         "'cellsize' is exactly grid-size invariant. See dco.py.")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()

    print(f"[{__file__.split(chr(92))[-1].split(chr(47))[-1]}  version {SCRIPT_VERSION}]")
    global NORM
    NORM = a.norm
    dev = torch.device(a.device)
    E, C, X, d, n = load(a.data, dev, a.coords)
    S = len(E)
    ntr = int(0.8 * S)                                   # paper: 80 / 20
    Etr, Ctr, Xtr, dtr = E[:ntr], C[:ntr], X[:ntr], d[:ntr]
    Ete, Cte, Xte, dte = E[ntr:], C[ntr:], X[ntr:], d[ntr:]

    net = D.DCO(levels=a.levels, base=a.base).to(dev)
    if a.init:
        ck = torch.load(resolve_legacy(a.init), map_location=dev, weights_only=False)
        for k in ("levels", "base", "coords", "norm"):
            got, want = ck.get(k), getattr(a, k, None)
            if want is not None and got is not None and got != want:
                raise SystemExit(
                    f"--init {a.init} was trained with {k}={got}, but this run "
                    f"asks for {k}={want}.  Warm-starting across a different "
                    f"architecture or encoding silently produces nonsense; "
                    f"fix the flag or drop --init.")
        net.load_state_dict(ck["state"])
        print(f"warm-started from {a.init} (it had reached epoch "
              f"{ck.get('epoch', '?')})")
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs,
                                                       eta_min=a.lr * 0.02)

    def criterion(pred, targ):
        if a.loss == "mse":
            return torch.nn.functional.mse_loss(pred, targ)
        num = (pred - targ).pow(2).flatten(1).mean(1)
        den = targ.pow(2).flatten(1).mean(1).clamp_min(1e-20)
        return (num / den).mean()
    print(f"device={dev}  grid={n}^3  train/test={ntr}/{S - ntr}  "
          f"L={a.levels} base={a.base}  params={net.n_params() / 1e6:.2f}M  "
          f"coords={a.coords} norm={a.norm}")

    # config 随 hist 一起落盘：sweep_report 要靠 loss 这一项判断【测试损失】
    # 那一列能不能跨配置比大小 —— mse 与 rel 的量纲不同，混在一列排名会选错
    # 赢家（2026-09-12 真出过：按它排 mse 赢基线 11x，按 nMAE 只有 1.05x）。
    hist = {"epoch": [], "train": [], "test": [], "mre": [],
            "config": {"loss": a.loss, "lr": a.lr, "batch": a.batch,
                       "epochs": a.epochs, "levels": a.levels, "base": a.base,
                       "coords": a.coords, "norm": a.norm, "data": a.data,
                       "grid": n, "train_n": ntr}}

    def save(ep):
        torch.save({"state": net.state_dict(), "levels": a.levels,
                    "base": a.base, "grid": n, "hist": hist,
                    "coords": a.coords, "norm": a.norm,
                    "target": "analytic", "head": "direct", "epoch": ep}, a.out)

    t0 = time.time()
    for ep in range(1, a.epochs + 1):
        perm = torch.randperm(ntr, device=dev)
        run = 0.0
        for i in range(0, ntr, a.batch):
            j = perm[i:i + a.batch]
            eh, ch, _, _ = D.normalise(Etr[j], Ctr[j], dtr[j], NORM)
            loss = criterion(net(eh, Xtr[j]), ch)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            run += loss.item() * len(j)
        tr = run / ntr
        sched.step()

        if ep % 10 == 0 or ep == 1 or ep == a.epochs:
            with torch.no_grad():
                eh, ch, _, _ = D.normalise(Ete, Cte, dte, NORM)
                te = criterion(net(eh, Xte), ch).item()
            r, m, na, per = evaluate(net, Ete, Cte, Xte, dte)
            hist["epoch"].append(ep); hist["train"].append(tr)
            hist["test"].append(te); hist["mre"].append(m)
            hist.setdefault("relL2", []).append(r)
            hist.setdefault("nmae", []).append(na)
            print(f"ep {ep:4d}  train {tr:.3e}  test {te:.3e}  "
                  f"relL2 {r:.3e}  nMAE {na:.3e}  eq5 {m:.2e}"
                  f"   [x {per[0]:.2e} y {per[1]:.2e} z {per[2]:.2e}]"
                  f"  {time.time() - t0:6.1f}s")

        if a.ckpt_every and ep % a.ckpt_every == 0:
            save(ep)

    save(a.epochs)
    with open(a.out.replace(".pt", "_hist.json"), "w") as f:
        json.dump(hist, f)
    print(f"\nsaved {a.out}   total {time.time() - t0:.1f}s")
    print(f"\nFINAL  relative L2 = {hist['relL2'][-1]:.3e}   <-- report this one")
    print(f"       nMAE        = {hist['nmae'][-1]:.3e}")
    print(f"       eq.(5) MRE  = {hist['mre'][-1]:.3e}   (pathological, see dco.py)")
    print(f"Paper Table I (32^3, 1000 samples): L=3 5.3e-3, L=4 7.7e-4")


if __name__ == "__main__":
    main()
