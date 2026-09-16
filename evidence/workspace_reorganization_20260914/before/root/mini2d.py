"""
The mechanism, end to end, small enough to train to convergence.  ~10 min CPU.

    python mini2d.py

WHY THIS EXISTS
    The 3-D work answers "how close to the paper's numbers did we get".  It
    does NOT answer the prior question: does the idea work at all?  There the
    operator is accurate in one shot (4.6e-2 on a cavity) and the closed loop
    still blows up around step 150, and it is impossible to tell whether that
    is a limit of the IDEA or a limit of our training budget -- 16^3, 400
    epochs, L=3, on a 6 GB card, against the paper's 32^3, 1000 epochs, L=4.

    So: shrink the problem until the budget stops mattering.  2-D TMz on a
    periodic square is small enough to train the operator to 1e-4 or better in
    minutes, which is far past anything the 3-D runs reached.  Then run the
    learned operator in the leapfrog for thousands of steps and see what
    happens.  Whatever it does, it is no longer confounded by "we did not
    train it enough".

2-D TMz, the whole physics
    fields      Ez(x,y), Hx(x,y), Hy(x,y)
    curl E      (dEz/dy, -dEz/dx)          -> updates H     [what we LEARN]
    curl H      dHy/dx - dHx/dy            -> updates Ez    [kept exact]
    leapfrog    H -= dt/mu * curlE(Ez);  Ez += dt/eps * curlH(H)

    Learning curl E and keeping curl H exact is the paper's own arrangement
    (its DCO replaces one of the two curls), so the miniature is faithful.

THE TWO HEADS, which is the other thing this settles
    direct     the net outputs the 2 components of curl E.
    potential  the net outputs ONE scalar and the exact rotated gradient
               (d/dy, -d/dx) is applied to it.
    In 2-D, (dEz/dy, -dEz/dx) is divergence free identically, so "potential"
    here is the exact miniature of the 3-D vector-potential idea: it makes
    div(curl) = 0 structural instead of penalised.  Same question, one tenth
    the compute.
"""

import numpy as np
import torch
import torch.nn as nn
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_VERSION = "2026-09-09a"
C0, EPS0, MU0 = 2.99792458e8, 8.8541878128e-12, 4.0e-7 * np.pi


# --------------------------------------------------------------------------- #
#  exact operators, periodic, 2-D
# --------------------------------------------------------------------------- #
def curl_E_2d(Ez, d):
    """Ez (B,1,n,n) -> (B,2,n,n) = (dEz/dy, -dEz/dx), at the H nodes."""
    return torch.cat([(torch.roll(Ez, -1, 3) - Ez) / d,
                      -(torch.roll(Ez, -1, 2) - Ez) / d], 1)


def curl_H_2d(H, d):
    """H (B,2,n,n) -> (B,1,n,n) = dHy/dx - dHx/dy, at the Ez nodes."""
    Hx, Hy = H[:, 0:1], H[:, 1:2]
    return ((Hy - torch.roll(Hy, 1, 2)) - (Hx - torch.roll(Hx, 1, 3))) / d


def div_2d(V, d):
    """Divergence of an H-node vector field, at the cell centres.

    FORWARD differences, not backward: Hx sits at (i, j+1/2) and Hy at
    (i+1/2, j), so only dHx/dx and dHy/dy taken forward land on the same point
    (i+1/2, j+1/2) and cancel.  An earlier version used backward differences,
    which evaluate the two terms at DIFFERENT points; it then reported 2.4e-1
    for the exact operator -- whose divergence is identically zero -- and the
    same 2.4e-1 for every network, that agreement being the tell that the
    measurement, not the field, was what it was reading.
    """
    return ((torch.roll(V[:, 0:1], -1, 2) - V[:, 0:1])
            + (torch.roll(V[:, 1:2], -1, 3) - V[:, 1:2])) / d


# --------------------------------------------------------------------------- #
#  the operator, both heads
# --------------------------------------------------------------------------- #
class MiniOp(nn.Module):
    def __init__(self, width=32, depth=4, head="direct"):
        super().__init__()
        self.head_mode = head
        c_out = 2 if head == "direct" else 1
        layers, c = [], 1
        for _ in range(depth):
            layers += [nn.Conv2d(c, width, 3, padding=1, padding_mode="circular"),
                       nn.GELU()]
            c = width
        layers += [nn.Conv2d(c, c_out, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, Ez, d_rel):
        out = self.net(Ez)
        if self.head_mode == "direct":
            return out / d_rel
        # exact rotated gradient of a learnt scalar -> divergence free by
        # construction, the 2-D miniature of the vector-potential head
        return curl_E_2d(out, d_rel)


# --------------------------------------------------------------------------- #
def band_limited(B, n, kmax, gen, device="cpu"):
    """Random periodic fields with |m| <= kmax on the reciprocal lattice."""
    F = torch.zeros(B, n, n, dtype=torch.complex64)
    for b in range(B):
        for _ in range(6):
            mx = int(torch.randint(-kmax, kmax + 1, (1,), generator=gen))
            my = int(torch.randint(-kmax, kmax + 1, (1,), generator=gen))
            if mx == 0 and my == 0:
                continue
            amp = torch.randn(1, generator=gen).item()
            ph = torch.rand(1, generator=gen).item() * 2 * np.pi
            F[b, mx, my] += amp * np.exp(1j * ph)
    E = torch.fft.ifft2(F).real
    E = E / E.abs().amax(dim=(1, 2), keepdim=True).clamp_min(1e-12)
    return E.unsqueeze(1).to(device)


def train(head, n=64, kmax=6, epochs=400, width=32, depth=4, ntr=512,
          device="cpu", seed=0):
    gen = torch.Generator().manual_seed(seed)
    d_rel = 1.0                                    # work in cells; scale-free
    Etr = band_limited(ntr, n, kmax, gen, device)
    Ete = band_limited(128, n, kmax, gen, device)
    Ttr, Tte = curl_E_2d(Etr, d_rel), curl_E_2d(Ete, d_rel)

    net = MiniOp(width, depth, head).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=2e-3)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs, eta_min=1e-5)
    npar = sum(p.numel() for p in net.parameters())
    print(f"\n[{head}]  {npar/1e3:.0f}k params, {ntr} samples at {n}^2, "
          f"{epochs} epochs")
    for ep in range(1, epochs + 1):
        perm = torch.randperm(ntr)
        for i in range(0, ntr, 64):
            j = perm[i:i + 64]
            loss = ((net(Etr[j], d_rel) - Ttr[j]).pow(2).mean()
                    / Ttr[j].pow(2).mean())
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
        sch.step()
        if ep % 100 == 0 or ep == 1:
            with torch.no_grad():
                P = net(Ete, d_rel)
                r = ((P - Tte).pow(2).sum() / Tte.pow(2).sum()).sqrt()
            print(f"   ep {ep:4d}   test rel L2 = {float(r):.3e}")
    with torch.no_grad():
        P = net(Ete, d_rel)
        rel = float(((P - Tte).pow(2).sum() / Tte.pow(2).sum()).sqrt())
        dv = float(div_2d(P, d_rel).pow(2).mean().sqrt()
                   / P.pow(2).mean().sqrt())
        dv0 = float(div_2d(Tte, d_rel).pow(2).mean().sqrt()
                    / Tte.pow(2).mean().sqrt())
    print(f"   FINAL rel L2 {rel:.3e}    relative div {dv:.2e}   "
          f"(exact operator: {dv0:.2e})")
    return net, rel, dv, dv0


@torch.no_grad()
def closed_loop(net, steps=4000, n=64, kmax=6, seed=99, device="cpu"):
    """Run the leapfrog twice from one state: exact curl vs the learnt one."""
    gen = torch.Generator().manual_seed(seed)
    Ez0 = band_limited(1, n, kmax, gen, device)
    d_rel, dt = 1.0, 0.99 / np.sqrt(2.0)           # CFL in cell units, c = 1
    def run(curl):
        Ez, H = Ez0.clone(), torch.zeros(1, 2, n, n, device=device)
        rec = []
        for _ in range(steps):
            H = H - dt * curl(Ez, d_rel)
            Ez = Ez + dt * curl_H_2d(H, d_rel)
            rec.append(Ez.clone())
        return torch.cat(rec)
    ref = run(curl_E_2d)
    dut = run(lambda E, d: net(E, d))
    num = (dut - ref).flatten(1).pow(2).mean(1).sqrt()
    den = ref.flatten(1).pow(2).mean(1).sqrt().clamp_min(1e-30)
    return (num / den).cpu().numpy(), ref, dut


def main():
    print(f"[mini2d.py  version {SCRIPT_VERSION}]")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device {dev}")
    res = {}
    for head in ("direct", "potential"):
        net, rel, dv, dv0 = train(head, device=dev)
        err, ref, dut = closed_loop(net, device=dev)
        res[head] = dict(net=net, rel=rel, div=dv, div0=dv0, err=err,
                         ref=ref, dut=dut)
        print(f"   closed loop, {len(err)} steps:")
        for thr in (0.01, 0.10, 1.00):
            i = int(np.argmax(err > thr)) if (err > thr).any() else -1
            print(f"     exceeds {thr*100:5.0f}%  at step "
                  f"{'never' if i < 0 else i}")
        print(f"     error at the last step: {err[-1]:.3e}")

    np.savez("mini2d.npz",
             **{f"{h}_err": res[h]["err"] for h in res},
             **{f"{h}_rel": res[h]["rel"] for h in res},
             **{f"{h}_div": res[h]["div"] for h in res})

    import os
    os.makedirs("figs", exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.1),
                           gridspec_kw={"width_ratios": [1.25, 1]})
    for h, c in (("direct", "#b84b10"), ("potential", "#0e5f75")):
        e = np.maximum(res[h]["err"], 1e-16)
        ax[0].semilogy(e, color=c, lw=1.3,
                       label=f'{h}  (1-step {res[h]["rel"]:.1e}, '
                             f'div {res[h]["div"]:.0e})')
    ax[0].axhline(1.0, color="0.5", lw=0.8, ls=":")
    ax[0].text(len(res["direct"]["err"]), 1.0, " 100% ", fontsize=7.5,
               color="0.4", ha="right", va="bottom")
    ax[0].set_xlabel("leapfrog step"); ax[0].set_ylabel("relative error vs exact")
    ax[0].set_title("(a) learnt curl inside the loop, 2-D TMz",
                    loc="left", fontsize=9.5)
    ax[0].legend(fontsize=7.5, frameon=False, loc="lower right")

    k = len(res["potential"]["err"]) - 1
    a_ = res["potential"]["ref"][k, 0].cpu().numpy()
    b_ = res["potential"]["dut"][k, 0].cpu().numpy()
    v = np.abs(a_).max() or 1.0
    ax[1].imshow(np.concatenate([a_, b_], 1), cmap="RdBu_r", vmin=-v, vmax=v)
    ax[1].set_xticks([]); ax[1].set_yticks([]); ax[1].grid(False)
    ax[1].set_title(f"(b) $E_z$ at step {k}: exact | learnt (potential head)",
                    loc="left", fontsize=9.5)
    fig.savefig("figs/fig9_mini2d.png", dpi=300, bbox_inches="tight")
    print("\nsaved figs/fig9_mini2d.png and mini2d.npz")


if __name__ == "__main__":
    main()
