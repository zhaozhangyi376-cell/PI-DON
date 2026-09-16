"""
Reconstruct last night's campaign from what it left on disk.

    py -3.11 night_report.py

WHY THIS EXISTS
    run_night.bat printed everything to the screen and nothing to a file.  The
    machine rebooted, so the scrollback is gone -- but every stage wrote its
    real output to disk (that is why stage 2 emits json rather than only
    printing).  This reads all of it back and prints the report the terminal
    would have shown, plus the verdict the numbers actually support.

    Nothing here recomputes anything.  If a file is missing, the stage did not
    finish, and the report says so instead of guessing.

    (For next time: in PowerShell,  .\\run_night.bat 2>&1 | Tee-Object night.log
     keeps the screen AND writes the log.)
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import glob
import json
import os
import time

import numpy as np

SCRIPT_VERSION = "2026-09-10a"


def age(path):
    t = os.path.getmtime(path)
    h = (time.time() - t) / 3600.0
    return time.strftime("%m-%d %H:%M", time.localtime(t)), h


def rule(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


# --------------------------------------------------------------------------- #
def timeline():
    rule("0. what actually ran, and when")
    marks = [
        ("data_32.npz", "stage 0  dataset"),
        ("dco_paper32.pt", "stage 3  32^3 parity training"),
        ("dco_paper32_hist.json", "stage 3  history"),
        ("pidon_paper32.pt", "stage 4  PINN at 32^3"),
        ("pidon_paper32_hist.json", "stage 4  history"),
        ("exp3_waveform.npz", "stage 5  cavity closed loop"),
        ("figs/fig11_spectral.png", "stage 6  figures"),
    ]
    sp = sorted(glob.glob("spectral_*.json"))
    rows = []
    if sp:
        t0 = min(os.path.getmtime(f) for f in sp)
        t1 = max(os.path.getmtime(f) for f in sp)
        rows.append((t0, f"stage 2  spectral radius, {len(sp)} checkpoints "
                         f"(first written)"))
        rows.append((t1, "stage 2  (last written)"))
    for f, what in marks:
        if os.path.exists(f):
            rows.append((os.path.getmtime(f), what))
    if not rows:
        print("  nothing found -- did the batch file run in this directory?")
        return
    for t, what in sorted(rows):
        print(f"  {time.strftime('%m-%d %H:%M', time.localtime(t))}   {what}")
    span = (max(r[0] for r in rows) - min(r[0] for r in rows)) / 3600.0
    print(f"\n  campaign spanned {span:.1f} h")
    missing = [w for f, w in marks if not os.path.exists(f)]
    if missing:
        print("  did NOT finish:")
        for m in missing:
            print(f"    - {m}")


# --------------------------------------------------------------------------- #
def stage2():
    rule("2. spectral radius of the real network   <== the one that matters")
    files = sorted(glob.glob("spectral_*.json"))
    if not files:
        print("  no spectral_*.json -- stage 2 never ran.")
        print("  Run it now, it only takes about an hour:")
        print("    for %F in (dco_*.pt pidon_*.pt) do py -3.11 spectral_dco.py "
              "--ckpt %F --n 16 --cfl 0.99 0.70 0.50 0.30 0.15")
        return []

    allrows = []
    for f in files:
        j = json.load(open(f))
        tag = os.path.splitext(os.path.basename(f))[0][len("spectral_"):]
        print(f"\n  {tag}    ({j.get('params', 0) / 1e6:.2f}M params, "
              f"probe grid {j.get('n', '?')}^3)")
        print("    CFL    eps0        rho (linear)    rho (nonlin)   "
              "pred step   measured")
        for r in j.get("rows", []):
            pb = r.get("pred_blowup")
            pb_s = "   never" if pb is None else f"{pb:8.0f}"
            bl = r.get("blowup", -1)
            bl_s = "    none" if bl is None or bl < 0 else f"{bl:8d}"
            emp = r.get("rho_emp")
            emp_s = "     nan" if emp is None or not np.isfinite(emp) \
                else f"{emp:.8f}"
            print(f"    {r['cfl']:4.2f}   {r['eps0']:.3e}   {r['rho']:.8f}   "
                  f"{emp_s}   {pb_s}   {bl_s}")
            rr = dict(r); rr["tag"] = tag
            allrows.append(rr)

        # per-checkpoint verdict on the CFL sweep
        sweep = sorted(j.get("rows", []), key=lambda r: -r["cfl"])
        if len(sweep) > 1:
            neutral = [r["cfl"] for r in sweep if r["rho"] <= 1 + 1e-6]
            lowest = min(r["cfl"] for r in sweep)
            if neutral:
                print(f"    -> becomes neutral at CFL {max(neutral):.2f} "
                      f"-- a smaller time step DOES rescue this one")
            else:
                print(f"    -> still rho > 1 at CFL {lowest:.2f} "
                      f"-- no time step rescues it; the fix must be structural")

        # sanity: the control must be 1
        bad = [r for r in j.get("rows", [])
               if abs(r.get("rho_exact", 1.0) - 1.0) > 1e-3]
        if bad:
            print("    *** control (exact Yee curl) drifted from 1.0 at "
                  f"CFL {[b['cfl'] for b in bad]} -- treat this file's numbers "
                  "with suspicion")
    return allrows


def verdict(rows):
    """Judge the mechanism properly, which means three things the pooled
    correlation alone gets wrong:

      * a row whose eps0 > 0.5 is not a measurement -- the network is more
        wrong than the field is large.  Drop it.
      * rows from one checkpoint's CFL sweep are NOT independent samples, so
        the per-checkpoint correlation has to be reported alongside the pooled
        one; a mechanism can hold inside every sweep and still pool badly.
      * the prediction ln(1/eps0)/ln(rho) treats the single-step CURL error as
        the initial STATE error, but the curl error enters the state times
        c*dt.  So a constant offset is expected and is not a failure -- what
        matters is whether the offset is CONSTANT.  meas*ln(rho)/ln(1/eps0)
        is that constant; its spread is the real figure of merit.
    """
    rule("2b. does the spectral radius actually predict the lifetime?")
    usable, dropped = [], []
    for r in rows:
        if r.get("eps0", 0) > 0.5:
            dropped.append(r); continue
        if not r.get("pred_blowup") or not r.get("blowup", -1) \
                or r.get("blowup", -1) < 0:
            continue
        usable.append(r)
    if dropped:
        tags = sorted({r["tag"] for r in dropped})
        print(f"  dropped {len(dropped)} row(s) with eps0 > 0.5 "
              f"(network more wrong than the field): {', '.join(tags)}")

    # -- was the handover state comparable across each sweep? ---------------
    # Group by (checkpoint, SEED).  Different seeds are different random
    # superpositions and are SUPPOSED to give different rms|E|; comparing
    # across them made this check fire on every checkpoint of the 2026-09-10
    # n=32 run even though the fixed-physical-time warm-up had worked
    # perfectly (eps0 varied by 0.1% across CFL at fixed seed).
    bad_state = []
    for tag in sorted({r["tag"] for r in rows}):
        for seed in sorted({r.get("seed", 0) for r in rows if r["tag"] == tag}):
            rs = [r for r in rows if r["tag"] == tag
                  and r.get("seed", 0) == seed and "rmsE" in r]
            if len(rs) > 2:
                v = [r["rmsE"] for r in rs]
                if max(v) / max(min(v), 1e-30) > 2.0:
                    bad_state.append((f"{tag} seed{seed}", min(v), max(v)))
    if bad_state:
        print(f"\n  *** the handover state was NOT comparable across the sweep "
              f"in {len(bad_state)} checkpoint(s):")
        for tag, lo, hi in bad_state[:3]:
            print(f"        {tag}: rms|E| ranged {lo:.4f} .. {hi:.4f}")
        print("      Rows measured at different points of the standing-wave "
              "cycle\n      are not comparable.  Re-run with --warm-mode time "
              "(the default\n      since 2026-09-10b) and --samples 3.")
    elif any("rmsE" in r for r in rows):
        print("\n  handover state comparable across each sweep: ok")
    else:
        print("\n  (this run predates the rms|E| check -- cannot verify the "
              "handover states were comparable)")

    if len(usable) < 4:
        print(f"\n  only {len(usable)} usable point(s) -- not enough to judge.")
        return

    def block(rs, label):
        p = np.array([r["pred_blowup"] for r in rs], float)
        m = np.array([r["blowup"] for r in rs], float)
        e = np.array([r["eps0"] for r in rs], float)
        rho = np.array([r["rho"] for r in rs], float)
        c = np.corrcoef(np.log(p), np.log(m))[0, 1]
        inv = m * np.log(rho) / np.log(1.0 / e)
        print(f"\n  {label}   n={len(rs)}")
        print(f"    corr(log predicted, log measured) = {c:+.3f}")
        print(f"    measured / predicted   median {np.median(m / p):.2f}"
              f"   spread {10 ** np.std(np.log10(m / p)):.2f}x")
        print(f"    offset constant  meas*ln(rho)/ln(1/eps0)   "
              f"median {np.median(inv):.2f}   spread "
              f"{10 ** np.std(np.log10(np.maximum(inv, 1e-9))):.2f}x")
        return c, float(np.median(m / p)), \
            float(10 ** np.std(np.log10(m / p)))

    c_all, _, _ = block(usable, "all usable rows (pooled)")
    hi = [r for r in usable if r["cfl"] >= 0.5]
    c_hi, ratio_hi, spread_hi = (block(hi, "CFL >= 0.50 only")
                                 if len(hi) >= 4 else (None, None, None))

    # -- per checkpoint, which is the fair unit ----------------------------
    print("\n  per checkpoint, inside its own CFL sweep:")
    good = tot = 0
    for tag in sorted({r["tag"] for r in usable}):
        rs = [r for r in usable if r["tag"] == tag]
        if len(rs) < 3:
            continue
        p = np.log([r["pred_blowup"] for r in rs])
        m = np.log([r["blowup"] for r in rs])
        c = np.corrcoef(p, m)[0, 1]
        tot += 1; good += c > 0.8
        print(f"    {tag:20s} corr {c:+.3f}   ({len(rs)} points)")
    if tot:
        print(f"\n    {good}/{tot} checkpoints have corr > 0.8 within their "
              f"own sweep")

    # -- the reading -------------------------------------------------------
    best_c = c_hi if c_hi is not None else c_all
    print()
    if best_c > 0.8 and spread_hi is not None and spread_hi < 1.6:
        print(f"  READING: rho predicts the lifetime on the real network, up to\n"
              f"  a constant factor of {ratio_hi:.1f}x with only {spread_hi:.2f}x "
              f"spread.\n"
              f"  The constant is expected -- see this function's docstring --\n"
              f"  and a constant offset is a formula constant, NOT a failed\n"
              f"  mechanism.  Say it exactly that way: 'rho predicts the\n"
              f"  blow-up step to within a factor that is the same for every\n"
              f"  checkpoint'.  Do not claim the absolute step count.")
    elif best_c > 0.5:
        print("  READING: rho orders the checkpoints correctly but the offset\n"
              "  is not constant.  Report the ordering, not the step count.")
    else:
        print("  READING: rho does NOT predict the lifetime in this data.\n"
              "  Before reporting that as a result, check the two lines above:\n"
              "  a non-comparable handover state or eps0 > 0.5 rows will\n"
              "  produce exactly this signature without the mechanism being\n"
              "  wrong.  If both are clean, it is a real falsification.")

    if c_hi is not None and c_all is not None and c_hi - c_all > 0.3:
        print(f"\n  NOTE: pooled corr {c_all:+.3f} but CFL>=0.5 corr "
              f"{c_hi:+.3f}.  The low-CFL rows are\n"
              f"  carrying the disagreement -- suspect the probe setup there, "
              f"not the mechanism.")

    control(usable)


def control(usable):
    """Is the lifetime explained by rho, or by plain accuracy?

    The naive answer -- corr(eps0, lifetime) -- is not enough, and gave the
    wrong reading twice.  On 14 checkpoints it was -0.116 and read as "no
    relation"; adding dco_L3/L3b (single-step error 36-42%) moved it to -0.706
    and read as "related".  Both readings are artefacts:

      * a checkpoint with eps0 near 1 has almost no room to grow, because the
        prediction is ln(1/eps0)/ln(rho) and the numerator collapses.  There,
        accuracy obviously matters -- the mechanism's own formula says so, so
        it is not a counterexample.
      * dco_L3 and dco_L3b are simultaneously the LEAST accurate and the LEAST
        stable, so the two variables are confounded and no raw correlation can
        separate them.

    Partial correlations can.  Aggregate to one point per checkpoint first --
    the CFL rows within a checkpoint are not independent samples.
    """
    hi = max(r["cfl"] for r in usable)
    rho, life, eps = [], [], []
    for t in sorted({r["tag"] for r in usable}):
        rs = [r for r in usable if r["tag"] == t and r["cfl"] == hi]
        if not rs:
            continue
        rho.append(float(np.mean([r["rho"] for r in rs])) - 1.0)
        life.append(float(np.mean([r["blowup"] for r in rs])))
        eps.append(float(np.mean([r["eps0"] for r in rs])))
    if len(rho) < 5:
        print("\n  control: too few checkpoints for a partial correlation")
        return
    rho, life, eps = (np.log(np.asarray(v, float)) for v in (rho, life, eps))

    def resid(x, z):
        return x - np.polyval(np.polyfit(z, x, 1), z)

    c_eps = np.corrcoef(eps, life)[0, 1]
    c_rho = np.corrcoef(rho, life)[0, 1]
    p_eps = np.corrcoef(resid(eps, rho), resid(life, rho))[0, 1]
    p_rho = np.corrcoef(resid(rho, eps), resid(life, eps))[0, 1]
    print(f"\n  control, over {len(rho)} checkpoints at CFL {hi:.2f}:")
    print(f"    raw      corr(log eps0,  log lifetime) = {c_eps:+.3f}")
    print(f"             corr(log rho-1, log lifetime) = {c_rho:+.3f}")
    print(f"    partial  eps0  with rho-1 held fixed   = {p_eps:+.3f}")
    print(f"             rho-1 with eps0  held fixed   = {p_rho:+.3f}")
    if abs(p_rho) > 0.6 and abs(p_eps) < 0.5:
        print("\n    READING: accuracy acts ONLY through rho -- once rho is "
              "known,\n    accuracy adds nothing.  Say exactly that.  Do NOT "
              "say 'accuracy\n    and lifetime are uncorrelated': that is "
              "false as soon as a\n    checkpoint with eps0 near 1 is in the "
              "set.")
    elif abs(p_eps) > 0.6:
        print("\n    READING: accuracy explains the lifetime even at fixed "
              "rho.\n    The single-variable story does not hold; report both.")
    else:
        print("\n    READING: neither variable dominates cleanly -- report "
              "the four\n    numbers and do not pick a story.")


def blowup_time(rows):
    """Does the loop die after a fixed number of STEPS, or after a fixed
    physical TIME?

    dt is proportional to the CFL number, so steps*CFL is proportional to the
    elapsed physical time.  If that product is constant across the CFL sweep,
    then halving the time step buys exactly nothing: you take twice as many
    steps and each grows half as much, and you blow up at the same instant.

    That distinction decides what can possibly fix the instability.  A fixed
    STEP count would mean the time discretisation is at fault and a smaller dt
    (or a better integrator) would help.  A fixed TIME means the learnt
    operator is a bad approximation to the curl in a way that acts like a
    continuous-time anti-damping term -- the integrator only samples it.  Then
    no time step and no integrator helps, and the operator itself has to
    change.
    """
    rule("2c. does it die after a fixed step count, or a fixed physical time?")
    tags = sorted({r["tag"] for r in rows})
    keep = []
    for tag in tags:
        rs = [r for r in rows if r["tag"] == tag
              and r.get("blowup", -1) and r.get("blowup", -1) > 0
              and r.get("eps0", 0) <= 0.5]
        cfls = sorted({r["cfl"] for r in rs}, reverse=True)
        if len(cfls) < 2:
            continue
        t = []
        for c in cfls:
            m = [r["blowup"] for r in rs if r["cfl"] == c]
            if m:
                t.append(float(np.mean(m)) * c)
        if len(t) >= 2:
            keep.append((tag, cfls, t, max(t) / min(t)))
    if not keep:
        print("  needs at least two CFL values per checkpoint -- nothing to say")
        return
    hdr = "  ".join(f"t@{c:.2f}" for c in keep[0][1])
    print(f"  steps x CFL  (proportional to elapsed physical time)\n")
    print(f"  {'checkpoint':20s} {hdr}   spread")
    for tag, cfls, t, sp in keep:
        cells = "  ".join(f"{v:6.1f}" for v in t)
        print(f"  {tag:20s} {cells}   {sp:.3f}x")
    worst = max(k[3] for k in keep)
    print(f"\n  worst spread over {len(keep)} checkpoints: {worst:.3f}x")
    if worst < 1.15:
        print("\n  READING: the blow-up happens at a fixed physical TIME, not a\n"
              "  fixed number of steps.  A smaller time step buys nothing at\n"
              "  all -- more steps, each growing proportionally less, same\n"
              "  instant of failure.  So the instability is a property of the\n"
              "  LEARNT OPERATOR as an approximation to the curl, not of the\n"
              "  time discretisation.  Changing dt or the integrator cannot fix\n"
              "  it; only changing the operator can.  Say 'the operator has a\n"
              "  characteristic time', not 'no CFL rescues it' -- the second is\n"
              "  true but much weaker.")
    else:
        print("\n  READING: the product is NOT constant, so the step count and\n"
              "  the physical time are not equivalent here.  Report the raw\n"
              "  numbers and do not claim either framing.")


def rank_rho(rows):
    """Which training recipe actually produced the most stable operator?"""
    rule("2d. ranking by rho -- which recipe bought stability?")
    hi = max((r["cfl"] for r in rows), default=None)
    if hi is None:
        return
    out = []
    for tag in sorted({r["tag"] for r in rows}):
        rs = [r for r in rows if r["tag"] == tag and r["cfl"] == hi
              and r.get("eps0", 0) <= 0.5]
        if not rs:
            continue
        out.append((float(np.mean([r["rho"] for r in rs])),
                    float(np.mean([r["blowup"] for r in rs
                                   if r.get("blowup", -1) > 0] or [float("nan")])),
                    float(np.mean([r["eps0"] for r in rs])), tag))
    if not out:
        return
    print(f"  at CFL {hi:.2f}, averaged over probe states\n")
    print(f"  {'checkpoint':20s} {'rho':>9s} {'rho-1':>8s} {'steps':>7s} "
          f"{'eps0':>10s}")
    for rho, st, eps, tag in sorted(out):
        print(f"  {tag:20s} {rho:9.5f} {rho - 1:8.4f} {st:7.0f} {eps:10.3e}")
    best = sorted(out)[0]
    eps_rank = sorted(out, key=lambda r: r[2])
    pos = [t[3] for t in eps_rank].index(best[3]) + 1
    tail = ("so here the most stable operator is also the most accurate one"
            if pos == 1 else
            "so the most stable operator is NOT the most accurate one")
    print(f"\n  lowest rho: {best[3]} (rho-1 = {best[0] - 1:.4f}); its "
          f"single-step\n  accuracy ranks {pos}/{len(out)}, {tail}.\n"
          f"  Either way it is section 2b's partial correlations that settle "
          f"which\n  variable drives the lifetime -- a rank comparison cannot.")


# --------------------------------------------------------------------------- #
def training():
    rule("3 / 4. the two long trainings")
    for pt, what in (("dco_paper32.pt", "stage 3  supervised, 32^3, L=4"),
                     ("pidon_paper32.pt", "stage 4  PINN (Yee + div + rollout)")):
        h = pt.replace(".pt", "_hist.json")
        if not os.path.exists(pt) and not os.path.exists(h):
            print(f"\n  {what}: did not run")
            continue
        print(f"\n  {what}")
        if os.path.exists(pt):
            stamp, _ = age(pt)
            try:
                import torch
                ck = torch.load(pt, map_location="cpu", weights_only=False)
                ep = ck.get("epoch", "?")
                print(f"    {pt}   last written {stamp}   at epoch {ep}")
            except Exception as e:                       # torch may be busy
                print(f"    {pt}   last written {stamp}   (could not open: {e})")
        if os.path.exists(h):
            j = json.load(open(h))
            e = j.get("epoch", [])
            if e:
                print(f"    epochs recorded: {e[0]} .. {e[-1]}")
                for k, lab, ref in (("relL2", "relative L2", None),
                                    ("nmae", "nMAE", None)):
                    v = j.get(k)
                    if v:
                        best = min(v)
                        print(f"    {lab:12s} final {v[-1]:.3e}   "
                              f"best {best:.3e} (ep {e[int(np.argmin(v))]})")
                v = j.get("relL2")
                if v and len(v) > 3:
                    tail = v[-3:]
                    trend = "still improving" if tail[-1] < tail[0] * 0.98 \
                        else "flat -- more epochs would not have helped much"
                    print(f"    trend over the last 3 records: {trend}")
    print("\n  paper Table I for reference (32^3, 1000 samples):"
          "  L=3 5.3e-3   L=4 7.7e-4")


# --------------------------------------------------------------------------- #
def stage5():
    rule("5. test suite on the new checkpoints")
    files = sorted(glob.glob("test_results_*.npz"))
    if not files:
        print("  no test_results_*.npz -- stage 5 never ran")
    for f in files:
        stamp, hrs = age(f)
        z = np.load(f, allow_pickle=True)
        lab = str(z["label"]) if "label" in z else f
        print(f"\n  {lab}   ({stamp})")
        if "exp1_relL2" in z:
            rs = z["exp1_rs"] if "exp1_rs" in z else None
            print(f"    EXP 1 single-step relL2 = {float(z['exp1_relL2']):.3e}"
                  + (f"   (mean over {len(rs)} samples "
                     f"{float(np.mean(rs)):.3e})" if rs is not None else ""))
        if "exp2_sizes" in z:
            print("    EXP 2 dimension invariance:")
            for s, r in zip(z["exp2_sizes"], z["exp2_rel"]):
                print(f"       {str(s):>12s}   {float(r):.3e}")
    if os.path.exists("exp3_waveform.npz"):
        z = np.load("exp3_waveform.npz")
        n = len(z["curl_err"]) if "curl_err" in z else 0
        stamp, _ = age("exp3_waveform.npz")
        print(f"\n  EXP 3 cavity closed loop ({stamp}): the loop recorded "
              f"{n} steps")
        print("    (test_dco.py stops early on blow-up, so this length IS the "
              "blow-up step when it is shorter than --steps)")


def figures():
    rule("6. figures")
    fs = sorted(glob.glob("figs/*.png"))
    if not fs:
        print("  none")
        return
    for f in fs:
        stamp, hrs = age(f)
        fresh = "  <- regenerated last night" if hrs < 24 else ""
        print(f"  {os.path.basename(f):28s} {stamp}{fresh}")


# --------------------------------------------------------------------------- #
def main():
    print(f"[night_report.py  version {SCRIPT_VERSION}]")
    print(f"reading {os.path.abspath('.')}")
    timeline()
    rows = stage2()
    verdict(rows)
    blowup_time(rows)
    rank_rho(rows)
    training()
    stage5()
    figures()
    rule("what to paste back")
    print("  Sections 2b (partial correlations), 2c (fixed time vs fixed\n  step count) and 2d (ranking) carry the conclusions.  Section 2 is\n  the raw table behind them.")


if __name__ == "__main__":
    main()
