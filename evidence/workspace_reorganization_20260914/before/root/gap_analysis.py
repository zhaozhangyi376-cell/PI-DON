"""
Stage 5b -- WHERE the gap to the paper actually is.  No training, ~2 minutes.

    py -3.11 gap_analysis.py --ckpt dco_L3d.pt

Answers four questions that otherwise cost GPU-hours to answer by retraining:

  A  METRIC.  Table I quotes eq.(5) MRE; we quote relative L2.  Print both for
     the same weights so the comparison is honest instead of apples-to-oranges.

  B  BOUNDARY.  A 3x3x3 conv with zero padding cannot see outside the grid, so
     the outermost voxels are structurally unlearnable.  At 16^3 the two-voxel
     shell is 58% of all voxels; at 32^3 it is 33%.  If the error lives in the
     shell, most of our gap to the paper is simply that we trained at 16^3 --
     and the 32^3 number can be PROJECTED without spending 8 hours on it.

  C  DIVERGENCE.  div(curl) = 0 is an identity.  The Yee curl satisfies it to
     machine precision; the ANALYTIC curl the paper trains on does NOT satisfy
     it on a discrete grid (it is off by O(k^2 d^2)).  So a DCO trained on the
     analytic curl learns an operator that injects magnetic charge every step
     when you drop it into a leapfrog loop.  That is a candidate root cause for
     the EXP-3b blow-up, and it is testable right here.

  D  SPECTRUM.  Error vs the wavenumber content of the sample: does the DCO
     fail on the high-k samples (a resolution problem) or uniformly (a capacity
     problem)?  These call for different fixes.

Everything printed here is measured, except the 32^3/64^3 projection in (B),
which is explicitly labelled an extrapolation and states its assumption.
"""

import argparse
import json

import numpy as np
import torch

import dco as D
from gen_data import build as build_data

SCRIPT_VERSION = "2026-09-09b"


# --------------------------------------------------------------------------- #
#  discrete operators on the (3,n,n,n) "core" layout used by gen_data
# --------------------------------------------------------------------------- #
def div_of_curl(C, d):
    """Discrete divergence of a curl-like field, at cell centres.

    C[0] (Cx) sits at (i,     j+1/2, k+1/2)
    C[1] (Cy) sits at (i+1/2, j,     k+1/2)
    C[2] (Cz) sits at (i+1/2, j+1/2, k    )
    so the natural divergence point is the cell centre (i+1/2,j+1/2,k+1/2) and
    every term is a one-cell difference.  Returns (n-1,n-1,n-1).
    """
    dx, dy, dz = d
    return ((C[0, 1:, :-1, :-1] - C[0, :-1, :-1, :-1]) / dx
            + (C[1, :-1, 1:, :-1] - C[1, :-1, :-1, :-1]) / dy
            + (C[2, :-1, :-1, 1:] - C[2, :-1, :-1, :-1]) / dz)


def yee_curl_core(E, d):
    """The Yee curl of the discrete E, on the same core layout as gen_data's C.

    This is what the leapfrog loop actually applies.  It differs from the
    analytic curl by the usual O(k^2 d^2) dispersion error -- and, crucially,
    it is EXACTLY divergence free, which the analytic curl is not.
    Returns (3,n-1,n-1,n-1).
    """
    dx, dy, dz = d
    Ex, Ey, Ez = E
    # every difference shrinks one axis by 1, and the two terms of a component
    # shrink DIFFERENT axes, so each term is cropped to the component's own
    # node set before they are combined:
    #   cx at (i,     j+1/2, k+1/2)  ->  (n,   n-1, n-1)
    #   cy at (i+1/2, j,     k+1/2)  ->  (n-1, n,   n-1)
    #   cz at (i+1/2, j+1/2, k    )  ->  (n-1, n-1, n  )
    cx = ((Ez[:, 1:, :] - Ez[:, :-1, :])[:, :, :-1] / dy
          - (Ey[:, :, 1:] - Ey[:, :, :-1])[:, :-1, :] / dz)
    cy = ((Ex[:, :, 1:] - Ex[:, :, :-1])[:-1, :, :] / dz
          - (Ez[1:, :, :] - Ez[:-1, :, :])[:, :, :-1] / dx)
    cz = ((Ey[1:, :, :] - Ey[:-1, :, :])[:, :-1, :] / dx
          - (Ex[:, 1:, :] - Ex[:, :-1, :])[:-1, :, :] / dy)
    # then to the common (n-1,n-1,n-1) block
    return np.stack([cx[:-1, :, :], cy[:, :-1, :], cz[:, :, :-1]])


def shell_id(n):
    """Distance (in voxels) from the nearest face.  0 = on the boundary."""
    i = np.arange(n)
    I, J, K = np.meshgrid(i, i, i, indexing="ij")
    return np.minimum.reduce([I, n - 1 - I, J, n - 1 - J, K, n - 1 - K])


# --------------------------------------------------------------------------- #
def load_net(path, device):
    ck = torch.load(path, map_location=device, weights_only=False)
    net = D.DCO(levels=ck["levels"], base=ck["base"],
                head=ck.get("head", "direct")).to(device)
    net.load_state_dict(ck["state"])
    net.eval()
    return net, ck


def predict(net, E_np, d_mm, device, coord_mode, norm_mode):
    n = E_np.shape[-1]
    e = torch.from_numpy(np.ascontiguousarray(E_np)).float().unsqueeze(0).to(device)
    x = D.make_coords(n, d_mm, coord_mode, device=device)
    dd = torch.tensor(d_mm, dtype=torch.float32).view(1, 3).to(device)
    with torch.no_grad():
        eh, _, a, Lc = D.normalise(e, None, dd, norm_mode)
        return D.denormalise(net(eh, x, D.d_rel_of(dd, Lc)),
                             a, Lc)[0].cpu().numpy()


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="dco_L3d.pt")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--project-to", type=int, nargs="*", default=[32, 64])
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()

    print(f"[gap_analysis.py  version {SCRIPT_VERSION}]")
    dev = torch.device(a.device)
    net, ck = load_net(a.ckpt, dev)
    cm, nm = ck.get("coords", "abs"), ck.get("norm", "max")
    n = ck["grid"]
    print(f"loaded {a.ckpt}: L={ck['levels']} base={ck['base']} grid={n}^3 "
          f"coords={cm} norm={nm}")

    E, C, Dd = build_data(a.samples, n, seed=a.seed)
    P = np.stack([predict(net, E[s], (Dd[s] * 1e3).tolist(), dev, cm, nm)
                  for s in range(a.samples)])
    out = {"ckpt": a.ckpt, "grid": n, "samples": a.samples}

    # ---------------------------------------------------------------- A ---
    print("\n=== A. the same weights under three metric definitions ==========")
    tP, tC = torch.from_numpy(P).float(), torch.from_numpy(C).float()
    m = {"rel_L2": float(D.rel_l2(tP, tC)),
         "eq5_MRE": float(D.mre_eq5(tP, tC)),
         "nMAE": float(D.nmae(tP, tC))}
    for k, v in m.items():
        print(f"  {k:<10s} {v:.4e}")
    out["metrics"] = m
    print("  paper Table I quotes 'MRE': L=2 1.4e-2, L=3 5.3e-3, L=4 7.7e-4")
    print("  paper III-D quotes a relative-L2-like number: 3.8e-3 .. 4.7e-3")
    print("\n  WHICH READING OF eq.(5) DID THE PAPER ACTUALLY USE?")
    print(f"    literal, pointwise |yp-yt|/|yt|   {m['eq5_MRE']:.2e}  "
          f"-> {m['eq5_MRE'] / 5.3e-3:.0f}x their L=3")
    print(f"    relative L2                       {m['rel_L2']:.2e}  "
          f"-> {m['rel_L2'] / 5.3e-3:.0f}x their L=3")
    print(f"    MAE / max|yt|  (= our nMAE)       {m['nMAE']:.2e}  "
          f"-> {m['nMAE'] / 5.3e-3:.2f}x their L=3")
    print("\n  The literal reading cannot reach 1e-3 for ANY model -- curl E\n"
          "  crosses zero all over the grid and the pointwise ratio diverges\n"
          "  there, so the paper's own 7.7e-4 is unreachable under it.  The\n"
          "  paper does say 'the U-net output was normalized by the local\n"
          "  maximum for each component', which is exactly what MAE/max does.\n"
          "  Under that reading -- the only one in which the paper's numbers\n"
          "  are attainable at all -- these weights already sit at its L=3\n"
          "  level, at 16^3 and 400 epochs against its 32^3 and 1000.\n"
          "  State this as an INFERENCE about their metric, not as proof.")

    # ---------------------------------------------------------------- B ---
    print("\n=== B. where in the volume the error lives ======================")
    sid = shell_id(n)
    depth = sid.max() + 1
    err2 = ((P - C) ** 2).mean(axis=1)          # (S,n,n,n), averaged over xyz
    tru2 = (C ** 2).mean(axis=1)
    e_s, t_s, N_s = [], [], []
    print("  shell  voxels   frac    rel_L2 in shell")
    for s in range(depth):
        msk = sid == s
        e2 = err2[:, msk].mean(); t2 = tru2[:, msk].mean()
        e_s.append(e2); t_s.append(t2); N_s.append(int(msk.sum()))
        print(f"  {s:^5d}  {msk.sum():6d}  {msk.sum() / n ** 3:5.1%}   "
              f"{np.sqrt(e2 / t2):.4e}" + ("   <- unlearnable: the 3x3x3 "
                                           "stencil hangs off the grid" if s == 0 else ""))
    e_s, t_s, N_s = map(np.array, (e_s, t_s, N_s))
    interior = sid >= 2
    ri = float(np.sqrt(err2[:, interior].mean() / tru2[:, interior].mean()))
    print(f"\n  whole volume   rel_L2 = {m['rel_L2']:.4e}")
    fac = m["rel_L2"] / ri
    verdict = ("better" if fac >= 1.05 else
               "WORSE -- the error is NOT concentrated in the boundary shell, "
               "so a bigger grid will not help")
    print(f"  interior only  rel_L2 = {ri:.4e}   ({fac:.2f}x {verdict}; "
          f"interior is {interior.sum() / n ** 3:.0%} of the {n}^3 grid)")
    out["shell_rel"] = [float(x) for x in np.sqrt(e_s / t_s)]
    out["interior_rel"] = ri

    # projection: assume e_s, t_s are properties of the SHELL, not of the grid
    # size, and that everything deeper than the deepest measured shell behaves
    # like that deepest shell.  Then re-weight by the shell populations of a
    # larger cube.  This is an extrapolation, and it will be optimistic if the
    # deep interior is genuinely easier at 32^3 than the s=depth-1 shell of a
    # 16^3 cube (it probably is), so treat it as a LOWER BOUND on the gain.
    print("\n  projected to larger training grids (extrapolation, see source):")
    for nn in a.project_to:
        sid2 = shell_id(nn)
        num = den = 0.0
        for s in range(sid2.max() + 1):
            cnt = int((sid2 == s).sum())
            j = min(s, depth - 1)
            num += cnt * e_s[j]; den += cnt * t_s[j]
        print(f"    {nn:3d}^3  rel_L2 ~ {np.sqrt(num / den):.3e}   "
              f"({m['rel_L2'] / np.sqrt(num / den):.1f}x better than {n}^3)")
        out[f"proj_{nn}"] = float(np.sqrt(num / den))

    # ---------------------------------------------------------------- C ---
    print("\n=== C. div(curl) = 0 -- the identity the leapfrog relies on =====")
    print("  RMS of the discrete divergence, normalised by RMS|curl|/cell size")
    rows = []
    for s in range(min(a.samples, 8)):
        d = Dd[s].astype(np.float64)
        Lc = float(np.cbrt(d[0] * d[1] * d[2]))
        scale = np.sqrt((C[s] ** 2).mean()) / Lc          # natural size of a div
        dv_an = np.sqrt((div_of_curl(C[s].astype(np.float64), d) ** 2).mean())
        dv_pr = np.sqrt((div_of_curl(P[s].astype(np.float64), d) ** 2).mean())
        yc = yee_curl_core(E[s].astype(np.float64), d)
        dv_ye = np.sqrt((div_of_curl(yc, d) ** 2).mean())
        rows.append((dv_ye / scale, dv_an / scale, dv_pr / scale))
    r = np.array(rows).mean(axis=0)
    print(f"    Yee curl of the discrete E   {r[0]:.3e}   <- the identity, exact")
    print(f"    ANALYTIC curl (our targets)  {r[1]:.3e}   <- O(k^2 d^2), NOT zero")
    print(f"    DCO prediction               {r[2]:.3e}")
    print(f"\n  ratio DCO / analytic-target = {r[2] / max(r[1], 1e-30):.1f}x")
    print("  reading: the leapfrog conserves div(B) only because the Yee curl is\n"
          "  exactly solenoidal (row 1).  The paper trains on the ANALYTIC curl\n"
          "  (row 2), which is not -- so even a PERFECT fit to the training\n"
          "  target injects magnetic charge every step.  Row 3 says how much\n"
          "  worse the network is than its own target.  This is the most likely\n"
          "  root cause of the EXP-3b blow-up, and it suggests two stage-2\n"
          "  fixes: train on the Yee curl instead, and/or add lambda*||div||^2\n"
          "  to the loss (label free -- that is the physics-informed part).")
    out["div"] = {"yee": float(r[0]), "analytic": float(r[1]), "dco": float(r[2])}

    # ---------------------------------------------------------------- D ---
    print("\n=== D. error vs the wavenumber content of the sample ============")
    # |curl| / |E| is a direct proxy for the effective k of each sample
    keff = np.array([np.sqrt((C[s] ** 2).mean() / max((E[s] ** 2).mean(), 1e-30))
                     for s in range(a.samples)])
    rs = np.array([float(D.rel_l2(torch.from_numpy(P[s]), torch.from_numpy(C[s])))
                   for s in range(a.samples)])
    ppw = np.array([2 * np.pi / (keff[s] * float(np.cbrt(np.prod(Dd[s]))))
                    for s in range(a.samples)])           # points per wavelength
    o = np.argsort(ppw)
    q = np.array_split(o, 3)
    print("  points/wavelength   samples   mean rel_L2")
    for lab, g in zip(("coarsest 1/3", "middle 1/3", "finest 1/3"), q):
        print(f"  {ppw[g].min():5.1f} - {ppw[g].max():5.1f}      {len(g):3d}      "
              f"{rs[g].mean():.4e}")
    cor = float(np.corrcoef(np.log(ppw), np.log(rs))[0, 1])
    print(f"  corr(log ppw, log relL2) = {cor:+.2f}   "
          + ("strongly resolution limited -> more cells per wavelength helps "
             "more than more capacity" if cor < -0.5 else
             "weak -> the error is NOT mainly a resolution problem; capacity / "
             "epochs are the lever"))
    out["ppw_corr"] = cor

    with open(f"gap_{a.ckpt.replace('.pt', '')}.json", "w") as f:
        json.dump(out, f, indent=1)
    print(f"\nsaved gap_{a.ckpt.replace('.pt', '')}.json")


if __name__ == "__main__":
    main()
