"""Generate the reproducible long-run Algorithm-1 comparison figure."""
import json
from pathlib import Path
import matplotlib.pyplot as plt

RUNS = {
    "L4 tol=1e-4 (128)": "evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json",
    "L4 tol=1e-5 (64)": "evidence/pidon_stage2_64_component_lr3e4_tol1e5.json",
    "L4 H-shift tol=1e-5 (64)": "evidence/pidon_stage2_64_hshift_tol1e5.json",
    "L3 tol=1e-5 (64)": "evidence/pidon_stage2_64_L3_tol1e5.json",
}

def main():
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4), constrained_layout=True)
    for label, path in RUNS.items():
        p = Path(path)
        if not p.exists():
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
        x = [r["step"] for r in rows]
        y = [r["nmae"] for r in rows]
        ax[0].plot(x, y, lw=1.8, label=label)
        ax[1].plot(x, [max(r["lossH"], r["lossE"]) for r in rows], lw=1.5, label=label)
    ax[0].set_yscale("log"); ax[1].set_yscale("log")
    ax[0].set(xlabel="physical time step", ylabel="nMAE vs Yee FDTD",
              title="Field error: long-run drift")
    ax[1].set(xlabel="physical time step", ylabel="max(relative curl loss)",
              title="Inner fit quality")
    for a in ax:
        a.grid(True, which="both", alpha=.25)
        a.legend(fontsize=8)
    out = Path("figs/stage2_longrun_comparison.png")
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=180)
    print(out)

if __name__ == "__main__":
    main()
