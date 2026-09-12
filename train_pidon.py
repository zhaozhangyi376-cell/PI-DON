"""
Stage 6 -- PI-DON step 1: put PHYSICS in the loss.

    py -3.11 train_pidon.py --init dco_L3d.pt --target yee --lam-div 1.0 \
                            --epochs 200 --out pidon_A.pt

WHAT THIS ADDS OVER train_dco.py, AND WHY

  The DCO trained in stage 4 predicts the curl well in ONE shot (rel L2 ~4e-2)
  but blows up when it is put inside the leapfrog loop (EXP 3b, ~step 78).
  gap_analysis.py section C says why, in numbers:

      RMS div / scale     Yee curl of the discrete E   ~2e-16   (exact identity)
                          ANALYTIC curl, our target    ~1e-3    (NOT zero)
                          DCO prediction               (worse still)

  The leapfrog is stable partly because div(B) is conserved EXACTLY, and that
  holds only because the Yee curl is exactly solenoidal -- div(curl(.)) = 0 is
  a discrete identity for those particular difference stencils.  The paper
  trains against the ANALYTIC curl (section III-B), which on a discrete grid is
  solenoidal only to O(k^2 d^2).  So a network that fits its training target
  PERFECTLY still injects a little magnetic charge on every step, and that
  accumulates.  Two independent fixes follow, and this script implements both
  so they can be turned on separately and attributed:

  (1) --target yee     Train against the Yee curl of the same discrete E rather
                       than the analytic curl.  Costs nothing (it is computed
                       from the E already in the dataset), and makes the learnt
                       operator consistent with the scheme it is dropped into.
                       Deviates from the paper on purpose -- that is the point.

  (2) --lam-div L      Add  L * ||div(pred)||^2 / ||pred||^2  to the loss.  This
                       term needs NO LABELS: it is a differential identity, not
                       data.  That is what makes this the physics-informed step
                       rather than more supervised learning, and it is the same
                       idea as the paper's PI-DON loss, applied to the one
                       constraint that the failure mode points at.

  Both are cheap.  Neither requires regenerating data or retraining from
  scratch -- warm-start from the stage-4 checkpoint with --init.

  (3) --roll K       STAGE 3.  Run the DCO inside the leapfrog for K steps
                     INSIDE the training loop and penalise the drift from the
                     exact-curl rollout.  This is the only term that optimises
                     what we actually care about -- iterated stability -- and
                     it is what the paper's time-domain PI-DON is really doing.
                     (1) and (2) are single-step constraints; a network can
                     satisfy both and still be unusable after fifty steps.

                     Costs K forward+backward passes per rollout sample, so
                     memory grows linearly in K.  Defaults are sized for a 6 GB
                     card: --roll 8 --roll-batch 1 --roll-n 32.

                     The rollout runs on a PERIODIC box, not the PEC cavity --
                     see rollout.py's module docstring for why (uniform shapes,
                     no source, nothing accumulates, and k*d is in band by
                     construction).  rollout.py --selftest verifies the scheme:
                     div(curl)=0 and adjointness to 2e-16, energy conserved to
                     twelve decimals over 2000 steps, dispersion within 0.001%
                     of the Yee relation.
"""

import argparse
import json
import time

import numpy as np
import torch

SCRIPT_VERSION = "2026-09-09e"

import dco as D
import rollout as R

NORM = "max"


# --------------------------------------------------------------------------- #
#  the two physics pieces, in torch so they are differentiable
# --------------------------------------------------------------------------- #
def yee_curl_t(E, d_m):
    """Yee curl of the discrete E, on the gen_data core layout.

    E    (B,3,n,n,n), components at their own Yee nodes (see gen_data.py)
    d_m  (B,3) cell sizes in METRES
    returns (B,3,n-1,n-1,n-1) at exactly the nodes gen_data's curl targets use.

    Each component's two terms shrink DIFFERENT axes, so each is cropped to the
    component's own node set before subtracting -- getting this wrong gives a
    silently mis-registered target that still trains to a plausible-looking
    loss.
    """
    dx, dy, dz = (d_m[:, k].view(-1, 1, 1, 1) for k in range(3))
    Ex, Ey, Ez = E[:, 0], E[:, 1], E[:, 2]
    cx = ((Ez[:, :, 1:, :] - Ez[:, :, :-1, :])[:, :, :, :-1] / dy
          - (Ey[:, :, :, 1:] - Ey[:, :, :, :-1])[:, :, :-1, :] / dz)
    cy = ((Ex[:, :, :, 1:] - Ex[:, :, :, :-1])[:, :-1, :, :] / dz
          - (Ez[:, 1:, :, :] - Ez[:, :-1, :, :])[:, :, :, :-1] / dx)
    cz = ((Ey[:, 1:, :, :] - Ey[:, :-1, :, :])[:, :, :-1, :] / dx
          - (Ex[:, :, 1:, :] - Ex[:, :, :-1, :])[:, :-1, :, :] / dy)
    return torch.stack([cx[:, :-1], cy[:, :, :-1], cz[:, :, :, :-1]], dim=1)


def div_t(C, d_rel):
    """Discrete divergence of a curl-like field at cell centres, (B,n-1,n-1,n-1).

    d_rel is the cell size in whatever units C is expressed per; pass d/Lc when
    C is the normalised curl, which makes the result dimensionless and
    grid-size invariant (Lc = (dx dy dz)^(1/3), the same length the curl was
    normalised by in dco.normalise).
    """
    dx, dy, dz = (d_rel[:, k].view(-1, 1, 1, 1) for k in range(3))
    return ((C[:, 0, 1:, :-1, :-1] - C[:, 0, :-1, :-1, :-1]) / dx
            + (C[:, 1, :-1, 1:, :-1] - C[:, 1, :-1, :-1, :-1]) / dy
            + (C[:, 2, :-1, :-1, 1:] - C[:, 2, :-1, :-1, :-1]) / dz)


def div_penalty(C_hat, d_m, Lc):
    """||div||^2 / ||C||^2 on the normalised curl -- dimensionless, no labels.

    Zero for the exact Yee curl (the identity), ~1e-6 for the analytic curl at
    our resolutions, and whatever the network manages otherwise.
    """
    d_rel = d_m / (Lc.view(-1, 1) * 1e3)          # d_mm / Lc_mm -> O(1)
    dv = div_t(C_hat, d_rel)
    return dv.pow(2).mean() / C_hat.pow(2).mean().clamp_min(1e-20)


# --------------------------------------------------------------------------- #
def load(path, device, coord_mode):
    z = np.load(path)
    E = torch.from_numpy(z["E"]).to(device)
    C = torch.from_numpy(z["C"]).to(device)
    d = (torch.from_numpy(z["D"]) * 1e3).to(device)          # metres -> mm
    n = int(z["n"])
    dirs = str(z["dirs"]) if "dirs" in z else "shared"
    X = torch.cat([D.make_coords(n, d[s], coord_mode) for s in range(len(d))]).to(device)
    return E, C, X, d, n, dirs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data_16.npz")
    ap.add_argument("--init", default="", help="warm-start from a stage-4 DCO "
                                               "checkpoint (strongly recommended)")
    ap.add_argument("--levels", type=int, default=3)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4,
                    help="fine-tuning, so 1/3 of the stage-4 lr")
    ap.add_argument("--target", choices=["analytic", "yee"], default="analytic",
                    help="analytic = the paper's choice; yee = the operator the "
                         "leapfrog actually applies (see module docstring)")
    ap.add_argument("--lam-div", type=float, default=0.0,
                    help="weight of the label-free div(curl)=0 penalty")
    ap.add_argument("--coords", choices=["abs", "centered", "cellsize"],
                    default="cellsize")
    ap.add_argument("--norm", choices=["max", "rms"], default="rms")
    ap.add_argument("--head", choices=["direct", "potential"], default="direct",
                    help="direct = the paper's output layer, which cannot "
                         "satisfy div(curl)=0 (measured 6.7e5x the exact "
                         "operator's numerical zero; an explicit penalty "
                         "bought 1.5x). potential = output a vector potential "
                         "and apply the EXACT discrete curl, making the "
                         "identity structural. See dco.DCO.__init__.")
    ap.add_argument("--roll", type=int, default=0,
                    help="stage 3: unroll K DCO-in-the-leapfrog steps and "
                         "penalise the drift. 0 disables. 8 is a sane start.")
    ap.add_argument("--lam-roll", type=float, default=1.0)
    ap.add_argument("--roll-n", type=int, default=32,
                    help="rollout box. 16 cannot be excited inside the "
                         "training band -- see rollout.allowed_m.__doc__.")
    ap.add_argument("--roll-batch", type=int, default=1,
                    help="rollout samples per step. Memory ~ roll * roll-batch.")
    ap.add_argument("--roll-samples", type=int, default=8,
                    help="how many initial states to precompute")
    ap.add_argument("--roll-warm", type=int, default=40)
    ap.add_argument("--ckpt-every", type=int, default=50,
                    help="save every N epochs so a long run is never lost")
    ap.add_argument("--out", default="pidon.pt")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()

    print(f"[train_pidon.py  version {SCRIPT_VERSION}]")
    global NORM
    NORM = a.norm
    dev = torch.device(a.device)
    E, C, X, d, n, dirs = load(a.data, dev, a.coords)
    S = len(E)
    ntr = int(0.8 * S)

    net = D.DCO(levels=a.levels, base=a.base, head=a.head).to(dev)
    if a.init:
        ck = torch.load(a.init, map_location=dev, weights_only=False)
        if (ck["levels"], ck["base"]) != (a.levels, a.base):
            raise SystemExit(f"--init {a.init} is L={ck['levels']} base={ck['base']}, "
                             f"but you asked for L={a.levels} base={a.base}")
        net.load_state_dict(ck["state"])
        if ck.get("coords") != a.coords or ck.get("norm") != a.norm:
            print(f"  WARNING: {a.init} was trained with coords="
                  f"{ck.get('coords')} norm={ck.get('norm')}, you asked for "
                  f"coords={a.coords} norm={a.norm}.  The warm start will be "
                  f"close to useless -- match them.")
        print(f"  warm-started from {a.init}")

    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs,
                                                       eta_min=a.lr * 0.05)
    print(f"device={dev}  grid={n}^3  train/test={ntr}/{S - ntr}  "
          f"L={a.levels} base={a.base}  params={net.n_params() / 1e6:.2f}M "
          f"dirs={dirs} head={a.head}")
    print(f"target={a.target}  lam_div={a.lam_div}  coords={a.coords} norm={a.norm}")

    crop = (slice(None), slice(None), slice(0, n - 1), slice(0, n - 1), slice(0, n - 1))

    def targets(e_raw, c_raw, dd):
        """FULL-SIZE (B,3,n,n,n) target in normalised units.

        The Yee curl is only defined on the inner (n-1)^3 block -- a one-cell
        difference eats the last plane in each direction.  An earlier version
        cropped the PREDICTION to that block and trained only there, which left
        the outermost face of the output completely UNSUPERVISED: its values
        were whatever initialisation happened to give, and since EXP 3 and the
        relative-L2 scores use the full n^3 output, that untrained face then
        dominated them (it is what produced the nonsensical "vs analytic 5.16"
        for a network sitting at 2.1e-2 against its own target, when the two
        targets differ by only 6e-3).

        So the target is built full size: the analytic curl everywhere, with
        the inner block overwritten by the Yee curl.  Every output voxel is
        supervised, and the two targets agree to ~6e-3 anyway, so the seam
        costs nothing.
        """
        _, c_hat, a_sc, Lc = D.normalise(e_raw, c_raw, dd, NORM)
        if a.target == "analytic":
            return c_hat, a_sc, Lc
        t = c_hat.clone()
        cy = yee_curl_t(e_raw, dd * 1e-3)                  # mm -> m
        t[crop] = cy * Lc / a_sc
        return t, a_sc, Lc

    def losses(e_raw, c_raw, x, dd):
        e_hat, _, a_sc, Lc = D.normalise(e_raw, None, dd, NORM)
        p_hat = net(e_hat, x, D.d_rel_of(dd, Lc))
        t_hat, _, _ = targets(e_raw, c_raw, dd)
        num = (p_hat - t_hat).pow(2).flatten(1).mean(1)
        den = t_hat.pow(2).flatten(1).mean(1).clamp_min(1e-20)
        l_data = (num / den).mean()
        l_div = (div_penalty(p_hat, dd, Lc) if a.lam_div > 0
                 else p_hat.new_zeros(()))
        return l_data, l_div

    @torch.no_grad()
    def evaluate():
        net.eval()
        ps, ts = [], []
        for i in range(0, S - ntr, 8):
            j = slice(ntr + i, min(ntr + i + 8, S))
            e_hat, _, a_sc, Lc = D.normalise(E[j], None, d[j], NORM)
            p_hat = net(e_hat, X[j], D.d_rel_of(d[j], Lc))
            t_hat, _, _ = targets(E[j], C[j], d[j])
            ps.append(p_hat); ts.append(t_hat)
        P, T = torch.cat(ps), torch.cat(ts)
        r = float(D.rel_l2(P, T))
        # divergence of the prediction, in the SAME normalised measure that
        # gap_analysis.py reports, so the two are directly comparable
        e_hat, _, a_sc, Lc = D.normalise(E[ntr:], None, d[ntr:], NORM)
        dvs = []
        for i in range(0, S - ntr, 8):
            j = slice(i, min(i + 8, S - ntr))
            ph = net(e_hat[j], X[ntr:][j], D.d_rel_of(d[ntr:][j], Lc[j]))
            dvs.append(float(div_penalty(ph, d[ntr:][j], Lc[j].view(-1)).sqrt()))
        net.train()
        return r, float(np.mean(dvs))

    # ---- stage 3: precompute rollout initial states and their exact futures
    roll_E0 = roll_H0 = roll_ref = roll_d = roll_dt = None
    if a.roll > 0:
        with torch.no_grad():
            rn, rb = a.roll_n, a.roll_samples
            roll_d = torch.full((rb, 3), float(d[:, 0].mean()) * 1e-3, device=dev)
            roll_dt = R.dt_cfl(roll_d)
            e = R.lattice_ic(rb, rn, roll_d.cpu(), seed=1234, device=dev)
            h = torch.zeros_like(e)
            # settle into a proper leapfrog state with the EXACT operator
            e, h = R.leapfrog(e, h, roll_d, roll_dt, a.roll_warm, R.curl_E_p)
            kd = R.k_eff_d(e, R.curl_E_p(e, roll_d), roll_d)
            roll_E0, roll_H0 = e, h
            roll_ref, _ = R.leapfrog(e, h, roll_d, roll_dt, a.roll,
                                     R.curl_E_p, keep=True)   # (rb,K,3,n,n,n)
        print(f"rollout: {rb} states at {rn}^3, K={a.roll}, "
              f"k*d = {float(kd.min()):.3f} .. {float(kd.max()):.3f} "
              f"(band {R.BAND})")
        if not R.BAND[0] <= float(kd.mean()) <= R.BAND[1]:
            print("  *** rollout states are OUT OF BAND -- fix --roll-n first")

    def roll_loss():
        """Relative L2 against the exact-curl rollout, averaged over K steps."""
        j = torch.randint(len(roll_E0), (a.roll_batch,), device=dev)
        dut, _ = R.leapfrog(roll_E0[j], roll_H0[j], roll_d[j], roll_dt[j],
                            a.roll, R.dco_curl(net, a.coords, NORM), keep=True)
        ref = roll_ref[j]
        num = (dut - ref).pow(2).flatten(2).mean(2)
        den = ref.pow(2).flatten(2).mean(2).clamp_min(1e-20)
        return (num / den).mean()

    hist = {"epoch": [], "data": [], "div": [], "relL2": [], "div_rms": []}
    t0 = time.time()
    for ep in range(1, a.epochs + 1):
        perm = torch.randperm(ntr, device=dev)
        rd = rv = rr = 0.0
        for i in range(0, ntr, a.batch):
            j = perm[i:i + a.batch]
            l_data, l_div = losses(E[j], C[j], X[j], d[j])
            loss = l_data + a.lam_div * l_div
            if a.roll > 0:
                l_roll = roll_loss()
                loss = loss + a.lam_roll * l_roll
                rr += l_roll.detach().item() * len(j)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            rd += l_data.item() * len(j); rv += l_div.detach().item() * len(j)
        sched.step()

        if ep % 10 == 0 or ep == 1 or ep == a.epochs:
            r, dv = evaluate()
            hist["epoch"].append(ep); hist["data"].append(rd / ntr)
            hist["div"].append(rv / ntr); hist["relL2"].append(r)
            hist["div_rms"].append(dv)
            hist.setdefault("roll", []).append(rr / ntr)
            print(f"ep {ep:4d}  data {rd / ntr:.3e}  div {rv / ntr:.3e}"
                  + (f"  roll {rr / ntr:.3e}" if a.roll > 0 else "")
                  + f"  | test relL2 {r:.3e}  div_rms {dv:.3e}   "
                  f"{time.time() - t0:6.1f}s")
        if a.ckpt_every and ep % a.ckpt_every == 0:
            torch.save({"state": net.state_dict(), "levels": a.levels,
                        "base": a.base, "grid": n, "hist": hist,
                        "coords": a.coords, "norm": a.norm,
                        "target": a.target, "lam_div": a.lam_div,
                        "dirs": dirs, "roll": a.roll, "head": a.head}, a.out)

    torch.save({"state": net.state_dict(), "levels": a.levels, "base": a.base,
                "grid": n, "hist": hist, "coords": a.coords, "norm": a.norm,
                "target": a.target, "lam_div": a.lam_div,
                "dirs": dirs, "roll": a.roll, "head": a.head}, a.out)
    with open(a.out.replace(".pt", "_hist.json"), "w") as f:
        json.dump(hist, f)
    print(f"\nsaved {a.out}   total {time.time() - t0:.1f}s")
    print(f"FINAL  test relL2 (vs the {a.target} target) = {hist['relL2'][-1]:.3e}")
    print(f"       RMS div of the prediction            = {hist['div_rms'][-1]:.3e}")
    print("  compare div against gap_analysis.py section C: the analytic curl\n"
          "  itself sits at ~1e-3 and the exact Yee curl at ~1e-16.  Then re-run\n"
          "  test_dco.py on this checkpoint -- EXP 3b is the number that matters.")


if __name__ == "__main__":
    main()
