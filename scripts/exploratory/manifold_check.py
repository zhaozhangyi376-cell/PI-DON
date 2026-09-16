"""
Stage 5c -- is the EXP-3 cavity field even ON the training manifold?  ~20 s.

    py -3.11 manifold_check.py

WHY THIS EXISTS
    EXP 3a measures the DCO's curl on a warmed-up cavity field, OPEN LOOP -- no
    feedback, so nothing can accumulate.  It still comes out at relative L2
    ~19, i.e. the prediction is twenty times larger than the truth on step one.
    A stability argument (divergence, magnetic charge, super-CFL) cannot explain
    that: the operator is simply wrong on this input.  So the question is
    whether the input resembles anything the network was trained on.

THE MEASUREMENT
    Take grad(Ez) at every voxel, stack it into a 3 x N matrix and look at its
    singular values.  The share taken by the largest one says how directional
    the field's variation is:

        1.000   every gradient points the same way -- the field is a 1-D
                profile extruded along the other two axes
        0.333   the three directions carry equal variance -- fully isotropic

    Run it on the paper's training distribution and on the cavity, and the two
    land at opposite ends of that axis.

WHAT IT FINDS
    gen_data.py implements eqs. (2)(3)(4) as written: ONE (phi, theta) per
    sample, then 4-16 waves of DIFFERENT WAVENUMBER along that one direction.
    So E(r) = sum_i E0_i cos(k_i khat.r) is a function of the single scalar
    khat.r.  Every training sample is 1-D.  A cavity mode is a superposition of
    eight plane waves travelling in eight directions and is not.

    This also explains why the paper's own dimension-invariance tests (III-D)
    all pass: they resample the SAME distribution at a different grid size, so
    the test never leaves the manifold either.  Grid size is varied; field
    structure is not.

    --dirs per-wave in gen_data.py draws an independent direction per wave.  It
    costs nothing and moves the training distribution most of the way towards
    the cavity.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fdtd
from gen_data import build

SCRIPT_VERSION = "2026-09-09a"
OUT = "figs"


def dir_share(F):
    """Share of grad(F)'s variance carried by its dominant direction."""
    g = np.stack(np.gradient(np.asarray(F, dtype=float)))
    sv = np.linalg.svd(g.reshape(3, -1), compute_uv=False)
    return float(sv[0] / sv.sum())


def cavity_field(side=22.4e-3, n=32, warm=300, src=(15, 14, 13)):
    """Exactly the EXP-3 set-up in test_dco.py, warmed up the same way."""
    c = fdtd.PECCavity(side=side, n=n)
    g, _, _ = fdtd.gaussian_pulse(warm + 150, c.dt,
                                  f_max=0.55 * fdtd.C_PAPER / (2 * side / n) / 3)
    for t in range(warm):
        c.step(src_value=g[t], src_idx=src)
    return c.Ez[:n, :n, :]


def main():
    print(f"[manifold_check.py  version {SCRIPT_VERSION}]")
    rows = []
    for dirs, label in (("shared", "training data, dirs=shared\n(the paper's eq.(2))"),
                        ("per-wave", "training data, dirs=per-wave\n(one line changed)")):
        E, _, _ = build(8, 16, seed=7, dirs=dirs)
        v = [dir_share(E[s, 2]) for s in range(8)]
        rows.append((label, float(np.mean(v)), float(np.std(v))))
        print(f"  {dirs:9s}  {np.mean(v):.3f} +- {np.std(v):.3f}")
    cav = dir_share(cavity_field())
    rows.append(("EXP-3 cavity field\n(what we ask it to predict)", cav, 0.0))
    print(f"  cavity     {cav:.3f}")
    print("\n  1.000 = the field varies along ONE direction only")
    print("  0.333 = fully isotropic (the floor)")
    print(f"\n  The training distribution sits at {rows[0][1]:.2f} and the test "
          f"input at {cav:.2f}.\n  EXP 3a is an extrapolation across the whole "
          "axis, which is why it fails\n  open loop, before any accumulation "
          "can occur.")

    import os
    os.makedirs(OUT, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.6, 2.4))
    cols = ["#b84b10", "#c8a415", "#0e5f75"]
    ys = np.arange(len(rows))[::-1]
    for y, (lab, m, sd), c in zip(ys, rows, cols):
        ax.barh(y, m - 1 / 3, left=1 / 3, height=0.5, color=c,
                xerr=(sd if sd else None), error_kw=dict(ecolor="0.3", lw=1))
        ax.text(m + 0.012, y, f"{m:.3f}", va="center", fontsize=9,
                color=c, weight="bold")
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(1 / 3, 1.06)
    # the end-of-axis labels go BELOW the bars: at the top they collide with
    # the title, which is a long line starting at the left spine
    ax.axvline(1 / 3, color="0.55", lw=0.9)
    ax.text(1 / 3 + 0.006, ys[-1] - 0.42, "isotropic (0.333)", fontsize=7.5,
            color="0.4", va="top")
    ax.axvline(1.0, color="0.55", lw=0.9, ls="--")
    ax.text(1.0 - 0.006, ys[-1] - 0.42, "1-D (1.000)", fontsize=7.5,
            color="0.4", ha="right", va="top")
    ax.set_ylim(ys[-1] - 0.75, ys[0] + 0.45)
    ax.set_xlabel(r"share of $\nabla E_z$ variance in its dominant direction")
    ax.set_title("the training set and the test input sit at opposite ends",
                 loc="left", fontsize=9.5)
    ax.grid(axis="x", alpha=0.25); ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    fig.savefig(f"{OUT}/fig7_manifold.png", dpi=300, bbox_inches="tight")
    print(f"\nsaved {OUT}/fig7_manifold.png")
    np.savez("manifold_check.npz",
             labels=np.array([r[0] for r in rows]),
             mean=np.array([r[1] for r in rows]),
             std=np.array([r[2] for r in rows]))


if __name__ == "__main__":
    main()
