"""
Make the four slide figures.  Run AFTER run_fdtd_cavity.py / train_dco.py /
test_dco.py -- it just reads what they saved.

    py -3.11 make_figs.py

Outputs 300 dpi PNGs into figs/ :

    fig1_cavity_spectrum.png   -> slide 2, block (1)  physics baseline
    fig2_training.png          -> slide 2, block (2)  DCO learns the operator
    fig3_curl_slices.png       -> slide 2, block (2)  what it actually predicts
    fig4_dimension.png         -> slide 2, block (3)  dimension invariance
    fig6_gap.png               -> slide 3, the two gap_analysis findings
    fig7_manifold.png          -> slide 3, made by manifold_check.py
    fig8_rollout.png           -> slide 3, iterated stability (stage 5)

Any missing input is skipped with a message rather than crashing, so you can
run it at any point and get whatever is ready.

Fonts: matplotlib has no Chinese font by default and will render boxes.  All
labels here are English/ASCII on purpose -- put the Chinese in the PowerPoint
text box, not in the figure.
"""

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

OUT = "figs"
ACC = "#0e5f75"      # teal   -> reference / truth
SIG = "#b84b10"      # orange -> prediction / DCO
BAD = "#9c2c35"
GOOD = "#1a6f4c"
MUTED = "#5f6b78"
plt.rcParams.update({
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
})

PAPER_MODES = {"110": 4.243, "211": 7.348, "221": 9.000,
               "310": 9.487, "321": 11.225}


def have(f):
    if os.path.exists(f):
        return True
    print(f"  [skip] {f} not found")
    return False


# --------------------------------------------------------------------------- #
def fig1():
    if not have("fdtd_cavity.npz"):
        return
    z = np.load("fdtd_cavity.npz")
    rec, dt, f, X = z["rec"], float(z["dt"]), z["f"], z["X"]

    fig, ax = plt.subplots(1, 2, figsize=(7.6, 2.7),
                           gridspec_kw={"width_ratios": [1, 1.35]})

    # only the first couple of ns -- the full 8192-step record of a lossless
    # cavity is a dense multi-mode ring that just reads as noise on a slide
    t_ns = np.arange(len(rec)) * dt * 1e9
    nshow = int(np.searchsorted(t_ns, 2.0))
    ax[0].plot(t_ns[:nshow], rec[:nshow] * 1e3, color=ACC, lw=0.7)
    ax[0].set_xlabel("time (ns)")
    ax[0].set_ylabel(r"$E_z$ at $(12\Delta,12\Delta,13\Delta)$  (mV/m)")
    ax[0].set_title(f"(a) probe, first 2 ns of {len(rec)} steps", loc="left")

    m = (f > 2e9) & (f < 12.5e9)
    Xn = X[m] / X[m].max()
    ax[1].plot(f[m] / 1e9, Xn, color=ACC, lw=0.8)
    # 221 (9.000) and 310 (9.487) are close -- stagger the labels vertically
    tiers = {"110": 1.04, "211": 1.04, "221": 1.04, "310": 1.11, "321": 1.04}
    for name, fa in PAPER_MODES.items():
        ax[1].axvline(fa, color=SIG, ls="--", lw=0.7, alpha=0.8)
        ax[1].text(fa, tiers[name], name, ha="center", va="bottom",
                   fontsize=7.5, color=SIG)
    ax[1].set_xlabel("frequency (GHz)")
    ax[1].set_ylabel("normalised |FFT|")
    ax[1].set_ylim(0, 1.26)
    ax[1].set_title("(b) spectrum vs analytic modes (dashed)", loc="left")

    fig.savefig(f"{OUT}/fig1_cavity_spectrum.png")
    plt.close(fig)
    print("  fig1_cavity_spectrum.png")


# --------------------------------------------------------------------------- #
def fig2():
    cand = [f for f in os.listdir(".") if f.endswith("_hist.json")]
    if not cand:
        print("  [skip] no *_hist.json found")
        return
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6))
    cols = [ACC, SIG, GOOD, BAD]
    any_div = False
    for i, c in enumerate(sorted(cand)):
        h = json.load(open(c))
        tag = c.replace("_hist.json", "")
        # train_dco.py logs train/test; train_pidon.py logs data (+div, div_rms).
        # Take whichever this run wrote rather than assuming one schema.
        tr = h.get("train", h.get("data"))
        if tr is not None:
            ax[0].semilogy(h["epoch"], tr, color=cols[i % 4], lw=1.1,
                           label=f"{tag} train")
        if "test" in h:
            ax[0].semilogy(h["epoch"], h["test"], color=cols[i % 4], lw=1.1,
                           ls="--", label=f"{tag} test")
        if "div_rms" in h:          # the physics term, stage 6 only
            any_div = True
            ax[0].semilogy(h["epoch"], h["div_rms"], color=cols[i % 4], lw=1.1,
                           ls=":", label=f"{tag} RMS div")
        if "relL2" in h:
            ax[1].semilogy(h["epoch"], h["relL2"], color=cols[i % 4], lw=1.3,
                           label=tag)
            ax[1].annotate(f'{h["relL2"][-1]:.2e}',
                           (h["epoch"][-1], h["relL2"][-1]),
                           textcoords="offset points", xytext=(-4, 6),
                           ha="right", fontsize=7.5, color=cols[i % 4])
    ax[0].set_xlabel("epoch")
    ax[0].set_ylabel("relative MSE loss" + ("  /  RMS div" if any_div else ""))
    ax[0].set_title("(a) training loss" + ("  (dotted = physics term)"
                                           if any_div else " / testing loss"),
                    loc="left")
    ax[0].legend(fontsize=6.5, frameon=False)
    ax[1].set_xlabel("epoch"); ax[1].set_ylabel(r"relative $L_2$ error")
    ax[1].set_title(r"(b) test relative $L_2$ on physical $\nabla\times E$",
                    loc="left")
    ax[1].legend(fontsize=7, frameon=False)
    fig.savefig(f"{OUT}/fig2_training.png")
    plt.close(fig)
    print("  fig2_training.png")


# --------------------------------------------------------------------------- #
def fig3():
    if not have("test_results.npz"):
        return
    z = np.load("test_results.npz")
    if "exp1_E" not in z:
        print("  [skip] test_results.npz has no exp1 slices")
        return
    E, T, P = z["exp1_E"], z["exp1_true"], z["exp1_pred"]
    n = E.shape[-1]
    k = n // 2                                   # mid slice
    comp = ["x", "y", "z"]

    fig, axes = plt.subplots(3, 4, figsize=(7.6, 5.4))
    for r in range(3):
        e, t, p = E[r, :, :, k], T[r, :, :, k], P[r, :, :, k]
        d = p - t
        vt = np.abs(t).max() or 1.0
        panels = [(e, "input $E_%s$" % comp[r], np.abs(e).max() or 1.0, "RdBu_r"),
                  (t, r"true $(\nabla\times E)_%s$" % comp[r], vt, "RdBu_r"),
                  (p, r"DCO $(\nabla\times E)_%s$" % comp[r], vt, "RdBu_r"),
                  (d, "difference", vt, "RdBu_r")]
        for c, (arr, ttl, v, cm) in enumerate(panels):
            ax = axes[r, c]
            im = ax.imshow(arr.T, origin="lower", cmap=cm, vmin=-v, vmax=v)
            ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
            if r == 0:
                ax.set_title(ttl.split("$")[0].strip() or ttl, fontsize=8.5)
            ax.set_xlabel(ttl, fontsize=7.5)
            if c == 3:
                rel = np.abs(d).max() / v * 100
                ax.text(0.97, 0.03, f"max {rel:.1f}%", transform=ax.transAxes,
                        ha="right", va="bottom", fontsize=7, color=BAD)
    rl = float(z["exp1_relL2"]) if "exp1_relL2" in z else float("nan")
    fig.suptitle(f"mid-plane slice, held-out sample "
                 f"(relative $L_2$ = {rl:.2e}); colour scale shared per row",
                 fontsize=8.5, y=1.005)
    fig.savefig(f"{OUT}/fig3_curl_slices.png")
    plt.close(fig)
    print("  fig3_curl_slices.png")


# --------------------------------------------------------------------------- #
# checkpoints that carry the ablation story, in the order they should read.
# Everything else trained in this project is a variation that lands inside the
# sampling noise of EXP 2 (four samples per grid size), so plotting all
# thirteen produced a legend that covered the chart and thirty-nine bars whose
# differences were not real.
FIG4_PICK = [
    ("dco_L3b",  "L=3  absolute coords + max norm\n(literal reading; paper does\nnot specify either choice)"),
    ("dco_L3c",  "L=3  cellsize coords + max norm"),
    ("dco_L3d",  "L=3  cellsize coords + rms norm"),
    ("dco_L4b",  "L=4  cellsize coords + rms norm\n(same 400 epochs)"),
]


def fig4():
    """How far the error grows when the SAME weights meet a bigger grid.

    A line per checkpoint rather than grouped bars: the quantity of interest is
    the SLOPE (how fast the error grows with grid size), and a slope is what a
    line shows.  The degradation factor is printed at the right-hand end of
    each line, which is the number actually quoted in the text.
    """
    files = sorted(f for f in os.listdir(".")
                   if f.startswith("test_results_") and f.endswith(".npz"))
    if not files and have("test_results.npz"):
        files = ["test_results.npz"]
    if not files:
        return
    found = {}
    for f in files:
        z = np.load(f, allow_pickle=True)
        if "exp2_sizes" not in z:
            continue
        tag = f[len("test_results_"):-4] if f.startswith("test_results_") else "run"
        found[tag] = (str(z["label"]) if "label" in z else tag,
                      np.array(z["exp2_sizes"]), np.array(z["exp2_rel"]))
    if not found:
        print("  [skip] no exp2 results in any test_results_*.npz")
        return

    runs = [(lbl, ) + found[t][1:] for t, lbl in FIG4_PICK if t in found]
    if not runs:                       # fall back to whatever is there
        runs = [(v[0], v[1], v[2]) for v in list(found.values())[:4]]
        print("    (none of the ablation checkpoints found; showing the first "
              "few available)")

    cols = [BAD, "#a8761a", GOOD, SIG]
    marks = ["s", "D", "o", "^"]
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    # Align on the size LABEL, not on position.  Checkpoints are now tested on
    # different size lists (dco_paper32 gets 64^3, the 16^3-trained ones do
    # not), and indexing by position paired a 3-entry run against a 5-entry
    # axis -- "x and y must have same first dimension".
    order, seen = [], set()
    for _, sz, _ in runs:
        for t in [str(x) for x in sz]:
            if t not in seen:
                seen.add(t)
                order.append(t)
    pos = {t: i for i, t in enumerate(order)}
    xs = np.arange(len(order))
    for i, (lab, sz, rel) in enumerate(runs):
        c = cols[i % len(cols)]
        px = [pos[str(t)] for t in sz]
        ax.semilogy(px, rel, marks[i % 4] + "-", color=c, lw=1.6, ms=6,
                    label=lab)
        fac = rel[-1] / rel[0]
        ax.annotate(f"×{fac:.1f}", (px[-1], rel[-1]),
                    textcoords="offset points", xytext=(9, -3),
                    fontsize=10, color=c, weight="bold", va="center")

    ax.set_xticks(xs)
    ax.set_xticklabels([(t if "x" in t else f"${t}$")
                        + ("\ntrained on this" if k == 0 else "\nnever seen")
                        for k, t in enumerate(order)], fontsize=9)
    ax.set_xlim(-0.25, len(xs) - 1 + 0.75)
    ax.set_ylabel(r"relative $L_2$ error")
    ax.set_title("same weights, larger grid — how fast does the error grow?",
                 loc="left", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="center left",
              bbox_to_anchor=(1.06, 0.5), handlelength=1.6,
              labelspacing=1.0)
    ax.grid(alpha=0.25); ax.set_axisbelow(True)
    ax.set_xlabel(r"$\times$N at the right-hand end = how many times the error "
                  "grew from the trained grid  (smaller is better)",
                  fontsize=8, color=MUTED)
    fig.savefig(f"{OUT}/fig4_dimension.png")
    plt.close(fig)
    print("  fig4_dimension.png")


def fig11():
    """Three panels, one message each.  Reads every spectral_*.json.

    The first version of this figure plotted predicted step vs measured step
    against the diagonal.  That was the wrong picture twice over: every point
    sits ~4.5x ABOVE the diagonal (a known formula constant), so the reference
    line was not the thing being claimed and the figure read as "the
    prediction fails"; and it asked the viewer to hold ln(1/eps0)/ln(rho) in
    their head before they could read anything at all.

    What is actually being claimed is simpler, so plot it directly:
      (a) smaller rho, proportionally longer life.  For rho near 1,
          N ~ ln(1/eps0)/(rho-1), so on log-log this is a slope of -1.
      (b) accuracy alone does not order the checkpoints -- and the trend the
          raw correlation reports is carried by two checkpoints whose
          single-step error is already 36-42%.
      (c) the loop dies at a fixed physical TIME.  Left cloud: raw step count,
          which spreads 2x across the CFL sweep.  Right cloud: steps x CFL,
          which collapses onto a line.  Nothing else in this study is this
          clean, and it is the panel that says a smaller time step cannot help.
    """
    files = sorted(f for f in os.listdir(".")
                   if f.startswith("spectral_") and f.endswith(".json"))
    if not files:
        print("  [skip] no spectral_*.json (run spectral_dco.py first)")
        return
    rows = []
    for f in files:
        j = json.load(open(f))
        tag = os.path.splitext(f)[0][len("spectral_"):]
        for r in j.get("rows", []):
            if r.get("eps0", 0) > 0.5 or not r.get("blowup", -1) \
                    or r.get("blowup", -1) < 0 or r["rho"] <= 1:
                continue
            rows.append((tag, r["cfl"], r["rho"] - 1.0, float(r["blowup"]),
                         r["eps0"]))
    if len(rows) < 6:
        print("  [skip] too few usable rows in spectral_*.json")
        return
    tag = np.array([r[0] for r in rows])
    cfl = np.array([r[1] for r in rows])
    rm1 = np.array([r[2] for r in rows])
    life = np.array([r[3] for r in rows])
    eps = np.array([r[4] for r in rows])

    fig, ax = plt.subplots(1, 3, figsize=(11.4, 3.3))
    fig.subplots_adjust(wspace=0.42, bottom=0.24)
    cf = sorted(set(cfl), reverse=True)
    # zip() against a fixed five-colour list silently dropped any CFL beyond
    # the fifth -- run_meal.bat's denser sweep has six, so CFL 0.30 raised a
    # KeyError.  Take as many colours as there are CFLs.
    _base = [ACC, SIG, GOOD, BAD, MUTED]
    cmap = {c: (_base[i] if i < len(_base)
                else plt.cm.viridis(0.15 + 0.7 * i / max(len(cf) - 1, 1)))
            for i, c in enumerate(cf)}

    # ---- (a) rho vs lifetime --------------------------------------------
    for c in cf:
        m = cfl == c
        ax[0].loglog(rm1[m], life[m], "o", ms=4.5, color=cmap[c], alpha=0.85,
                     mec="white", mew=0.4, label=f"CFL {c:.2f}")
    xs = np.array([rm1.min() * 0.8, rm1.max() * 1.25])
    k = np.exp(np.mean(np.log(life) + np.log(rm1)))         # fit N*(rho-1)
    ax[0].loglog(xs, k / xs, "-", color="0.55", lw=1.1, zorder=0)
    ax[0].text(xs[1], k / xs[1], "  slope $-1$\n  (life $\\propto 1/(\\rho-1)$)",
               fontsize=7, color="0.4", va="center", ha="left")
    ax[0].set_xlabel(r"$\rho - 1$   (how much each step amplifies)")
    ax[0].set_ylabel("steps until the loop blows up")
    ax[0].set_title("(a) smaller $\\rho$, proportionally longer life",
                    loc="left", fontsize=9)
    ax[0].legend(fontsize=7, frameon=False, loc="lower left")

    # ---- (b) accuracy ----------------------------------------------------
    bad = eps > 0.25
    ax[1].loglog(eps[~bad], life[~bad], "o", ms=4.5, color=SIG, alpha=0.8,
                 mec="white", mew=0.4)
    if bad.any():
        ax[1].loglog(eps[bad], life[bad], "s", ms=5, color=BAD, alpha=0.9,
                     mec="white", mew=0.4)
        ax[1].annotate("already 36-42% wrong\nin ONE step: these two\ncarry the whole\n"
                       "raw correlation",
                       xy=(eps[bad].min(), life[bad].max()),
                       xytext=(0.03, 0.06), textcoords="axes fraction",
                       fontsize=7, color=BAD, ha="left", va="bottom",
                       arrowprops=dict(arrowstyle="->", color=BAD, lw=0.8,
                                       connectionstyle="arc3,rad=-0.25"))
    good = ~bad
    c_all = np.corrcoef(np.log(eps), np.log(life))[0, 1]
    c_good = np.corrcoef(np.log(eps[good]), np.log(life[good]))[0, 1] \
        if good.sum() > 4 else float("nan")
    ax[1].set_xlabel(r"single-step error  $\epsilon_0$")
    ax[1].set_ylabel("steps until blow-up")
    ax[1].set_title(f"(b) accuracy alone does not order them\n"
                    f"     corr {c_all:+.2f} with them, {c_good:+.2f} without",
                    loc="left", fontsize=9)

    # ---- (c) fixed step count or fixed physical time? --------------------
    raw, scaled = [], []
    for t in sorted(set(tag)):
        m = tag == t
        if len(set(cfl[m])) < 2:
            continue
        raw.append(life[m] / life[m].mean())
        scaled.append((life[m] * cfl[m]) / (life[m] * cfl[m]).mean())
    if raw:
        raw = np.concatenate(raw); scaled = np.concatenate(scaled)
        rng = np.random.default_rng(0)
        for i, (v, lab, col) in enumerate(((raw, "step count", BAD),
                                           (scaled, "steps $\\times$ CFL\n"
                                            "(physical time)", GOOD))):
            x = i + rng.uniform(-0.13, 0.13, len(v))
            ax[2].plot(x, v, "o", ms=4, color=col, alpha=0.6, mec="white",
                       mew=0.3)
            sp = v.max() / v.min()
            ax[2].text(i, 1.62, f"spread\n{sp:.2f}x", ha="center",
                       fontsize=8, color=col, weight="bold")
        ax[2].axhline(1.0, color="0.7", lw=0.9, ls="--", zorder=0)
        ax[2].set_xticks([0, 1])
        ax[2].set_xticklabels(["step count", "steps $\\times$ CFL\n"
                               "(physical time)"], fontsize=8)
        ax[2].set_xlim(-0.5, 1.5); ax[2].set_ylim(0.5, 1.85)
        ax[2].set_ylabel("value / its own checkpoint mean")
        ax[2].set_title("(c) what is actually constant across the\n"
                        "     CFL sweep? — physical time, not steps",
                        loc="left", fontsize=9)
    for a_ in ax[:2]:
        for axis in (a_.xaxis, a_.yaxis):
            axis.set_major_locator(mticker.LogLocator(numticks=5))
            axis.set_minor_locator(mticker.NullLocator())
            axis.set_major_formatter(mticker.FuncFormatter(
                lambda v, _: (f"{v:,.0f}" if v >= 1 else
                              f"{v:.3g}".rstrip("0").rstrip("."))))
    for a_ in ax:
        a_.grid(alpha=0.22); a_.set_axisbelow(True)

    fig.savefig(f"{OUT}/fig11_spectral.png")
    plt.close(fig)
    print(f"  fig11_spectral.png   ({len(rows)} rows from {len(files)} "
          f"checkpoints)")


def rho_minus1(rho):
    return np.maximum(np.asarray(rho, dtype=float) - 1.0, 1e-12)


def fig5():
    """Optional: EXP 3b waveform, only if the closed loop was run."""
    if not os.path.exists("exp3_waveform.npz"):
        return
    z = np.load("exp3_waveform.npz")
    ref, dut, warm, dt = z["ref"], z["dut"], int(z["warm"]), float(z["dt"])
    t = np.arange(len(ref)) * dt * 1e9
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    ax.plot(t, ref * 1e3, color=ACC, lw=1.0, label="FDTD (Yee curl)")
    ax.plot(t, dut * 1e3, color=SIG, lw=1.0, ls="--", label="DCO in the loop")
    ax.axvline(t[warm], color="0.4", lw=0.8, ls=":")
    ax.text(t[warm], ax.get_ylim()[1], " DCO takes over", fontsize=7.5,
            va="top", color="0.3")
    ax.set_xlabel("time (ns)"); ax.set_ylabel(r"$E_z$ (mV/m)")
    ax.legend(fontsize=7.5, frameon=False)
    fig.savefig(f"{OUT}/fig5_dco_in_loop.png")
    plt.close(fig)
    print("  fig5_dco_in_loop.png")


def fig6():
    """Slide 3: the two gap_analysis findings that carry the talk.

    (a) div(curl)=0 across three fields, log scale.  The whole argument for
        stage 2 is the distance between those bars.
    (b) error vs depth into the volume, with the voxel populations of a 16^3
        and a 32^3 cube overlaid -- this is why a bigger training grid buys
        only ~1.2x and is NOT where the gap to the paper lives.
    """
    cand = sorted(f for f in os.listdir(".")
                  if f.startswith("gap_") and f.endswith(".json"))
    if not cand:
        print("  [skip] no gap_*.json (run gap_analysis.py first)")
        return
    g = json.load(open(cand[0]))
    fig, ax = plt.subplots(1, 2, figsize=(7.6, 2.8),
                           gridspec_kw={"width_ratios": [1, 1.25]})

    # ---- (a) the divergence identity ------------------------------------
    names = ["Yee curl\n(the identity)", "analytic curl\n(paper's target)",
             "DCO\nprediction"]
    vals = [g["div"]["yee"], g["div"]["analytic"], g["div"]["dco"]]
    cols = [GOOD, ACC, BAD]
    ax[0].bar(range(3), vals, color=cols, width=0.62)
    for i, v in enumerate(vals):
        ax[0].text(i, v * 2.2, f"{v:.1e}", ha="center", fontsize=7.5,
                   color=cols[i], weight="bold")
    ax[0].set_yscale("log")
    ax[0].set_ylim(min(vals) * 0.2, max(vals) * 60)
    ax[0].set_xticks(range(3))
    ax[0].set_xticklabels(names, fontsize=7.5)
    ax[0].set_ylabel(r"RMS $\nabla\!\cdot\!(\nabla\times E)$ / scale")
    ax[0].set_title(r"(a) $\nabla\!\cdot\!(\nabla\times)\equiv 0$ — "
                    "who obeys it", loc="left", fontsize=9)
    ax[0].annotate("", xy=(0, vals[0] * 4), xytext=(0, vals[2]),
                   arrowprops=dict(arrowstyle="<->", color="0.45", lw=0.9))
    ax[0].text(0.12, np.sqrt(vals[0] * vals[2]),
               f"$10^{{{np.log10(vals[2] / vals[0]):.0f}}}$", fontsize=8,
               color="0.35", va="center")

    # ---- (b) error vs depth ---------------------------------------------
    sr = np.array(g["shell_rel"])
    n = int(g["grid"])
    xs = np.arange(len(sr))
    ax[1].plot(xs, sr, "o-", color=SIG, lw=1.4, ms=4, label="rel. $L_2$ in shell")
    ax[1].axhline(g["metrics"]["rel_L2"], color="0.5", ls="--", lw=0.9)
    ax[1].text(len(sr) - 1, g["metrics"]["rel_L2"], " whole volume",
               fontsize=7, va="bottom", ha="right", color="0.4")
    ax[1].set_xlabel("shell: voxels from the nearest face  (0 = on the boundary)")
    ax[1].set_ylabel(r"relative $L_2$")
    ax[1].set_ylim(0, sr.max() * 1.18)

    tw = ax[1].twinx()
    for nn, c, ls in ((n, ACC, "-"), (2 * n, GOOD, "--")):
        sid = np.minimum.reduce(np.meshgrid(*[np.minimum(np.arange(nn),
                                                         nn - 1 - np.arange(nn))] * 3,
                                            indexing="ij"))
        frac = [np.mean(sid == s) for s in xs]
        tw.plot(xs, frac, ls, color=c, lw=1.0, alpha=0.75,
                label=f"voxel fraction, ${nn}^3$")
    tw.set_ylabel("fraction of all voxels", fontsize=8)
    tw.set_ylim(0, 0.42); tw.grid(False)
    h1, l1 = ax[1].get_legend_handles_labels(); h2, l2 = tw.get_legend_handles_labels()
    ax[1].legend(h1 + h2, l1 + l2, fontsize=6.8, frameon=False, loc="lower left")
    ax[1].set_title(f"(b) error lives at the wall — but a ${2 * n}^3$ grid only "
                    f"buys {g['metrics']['rel_L2'] / g.get('proj_32', np.nan):.1f}x",
                    loc="left", fontsize=9)

    fig.savefig(f"{OUT}/fig6_gap.png")
    plt.close(fig)
    print("  fig6_gap.png")


def fig8():
    """Slide 3 / stage 5: how far the learned operator survives being iterated.

    One line per checkpoint from rollout.py.  Log y, because the interesting
    range spans machine precision to blow-up.  The horizontal guides are the
    thresholds rollout.py reports, so the figure and the printed table agree.
    """
    files = sorted(f for f in os.listdir(".")
                   if f.startswith("rollout_err_") and f.endswith(".npz"))
    if not files:
        print("  [skip] no rollout_err_*.npz (run rollout.py first)")
        return
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    cols = [ACC, SIG, GOOD, BAD]
    for i, f in enumerate(files):
        z = np.load(f, allow_pickle=True)
        e = z["err"]
        lab = str(z["label"]) if "label" in z else f[12:-4]
        c = cols[i % 4]
        ax.semilogy(np.arange(len(e)), np.maximum(e, 1e-12), color=c, lw=1.3,
                    label=lab)
        # mark where it first exceeds 20% -- the number quoted in the text
        bad = np.argmax(e > 0.20) if (e > 0.20).any() else -1
        if bad > 0:
            ax.plot([bad], [e[bad]], "o", ms=4.5, color=c)
            ax.annotate(f"step {bad}", (bad, e[bad]),
                        textcoords="offset points", xytext=(5, -2),
                        fontsize=7.5, color=c, va="top")
    for y, t in ((0.01, "1%"), (0.20, "20%")):
        ax.axhline(y, color="0.55", lw=0.7, ls=":")
        ax.text(0.995, y, " " + t, transform=ax.get_yaxis_transform(),
                fontsize=7, color="0.45", va="bottom", ha="right")
    ax.set_xlabel("leapfrog step after handover")
    ax.set_ylabel(r"relative $L_2$ vs the exact-curl rollout")
    ax.set_title("periodic box, DCO substituted for the Yee curl",
                 loc="left", fontsize=9.5)
    # curves start low-left and climb, so the upper-left corner is the free one
    ax.legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.savefig(f"{OUT}/fig8_rollout.png")
    plt.close(fig)
    print("  fig8_rollout.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(f"writing into {OUT}/ ...")
    for fn in (fig1, fig2, fig3, fig4, fig5, fig6, fig8, fig11):
        try:
            fn()
        except Exception as e:
            print(f"  [error] {fn.__name__}: {type(e).__name__}: {e}")
    print("done.")
