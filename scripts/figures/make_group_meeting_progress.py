"""Build traceable group-meeting figures from immutable PI-DON evidence.

This script is read-only with respect to experiment evidence.  It does not
load checkpoints, update parameters, or make scientific gate decisions.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figs" / "group_meeting_20260916"
EVIDENCE = ROOT / "evidence" / "server_resource_v1" / "imports"

RUNS = {
    "first_E": EVIDENCE / "server_first_e_return_20260915T145629Z" / "first_e_budget_probe",
    "micro4": EVIDENCE / "server_micro4_return_20260915T152352Z" / "micro4_strict_probe",
    "micro16": EVIDENCE / "server_micro16_return_20260915T154708Z" / "micro16_strict_probe",
    "strict64_lr3e4": EVIDENCE / "server_64_return_20260916T011046Z" / "strict64_probe",
    "clean64_lr1e4": EVIDENCE / "server_clean_low_lr64_return_20260916T061148Z" / "clean_low_lr64",
}

COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#666666",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(fig, stem: str):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def configure():
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )


def clean64_stepwise():
    rows = [r for r in load_jsonl(RUNS["clean64_lr1e4"] / "steps.jsonl") if r.get("accepted")]
    step = np.array([r["accepted_steps"] for r in rows])
    h_updates = np.array([r["fit_H"]["n_updates"] for r in rows])
    e_updates = np.array([r["fit_E"]["n_updates"] for r in rows])
    h_res = np.array([r["fit_H"].get("residual_ratio") or np.nan for r in rows], dtype=float)
    e_res = np.array([r["fit_E"].get("residual_ratio") or np.nan for r in rows], dtype=float)
    q = np.array([r["accepted_field_metrics"]["global_weighted_relative_l2"] for r in rows])
    cumulative = np.cumsum(h_updates + e_updates)

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.2), sharex=True)

    axes[0].bar(step, h_updates, color=COLORS["blue"], width=0.86, label="curl H fit")
    axes[0].bar(step, e_updates, bottom=h_updates, color=COLORS["orange"], width=0.86, label="curl E fit")
    axes[0].set_ylabel("Adam updates / step")
    axes[0].legend(frameon=False, ncol=2)
    axes[0].set_title("Clean low-LR trajectory: optimization cost and physical error")

    axes[1].semilogy(step, h_res, color=COLORS["blue"], marker="o", ms=2.5, lw=1, label="H residual ratio")
    axes[1].semilogy(step, e_res, color=COLORS["orange"], marker="s", ms=2.5, lw=1, label="E residual ratio")
    axes[1].axhline(1e-5, color=COLORS["red"], ls="--", lw=1, label="registered tolerance")
    axes[1].set_ylabel("Residual ratio")
    axes[1].legend(frameon=False, ncol=3)

    axes[2].plot(step, 100 * q, color=COLORS["green"], lw=1.5, label="global field relL2 (Q)")
    axes[2].axhline(5, color=COLORS["red"], ls="--", lw=1, label="5% field gate")
    axes[2].set_ylabel("Field error Q (%)")
    axes[2].set_xlabel("Accepted physical time step")
    axes[2].set_ylim(bottom=0)
    axes[2].legend(frameon=False)
    axes[2].text(
        0.99,
        0.04,
        f"Total Adam updates = {cumulative[-1]:,}",
        transform=axes[2].transAxes,
        ha="right",
        va="bottom",
        color=COLORS["gray"],
    )

    for label, ax in zip("ABC", axes):
        ax.text(-0.09, 1.03, label, transform=ax.transAxes, fontweight="bold", fontsize=11)
        ax.grid(axis="y", alpha=0.18, lw=0.6)

    fig.tight_layout()
    save(fig, "clean_low_lr64_stepwise")


def optimizer_vs_physical_steps():
    order = ["first_E", "micro4", "micro16", "strict64_lr3e4", "clean64_lr1e4"]
    labels = ["First-E\ndiagnostic", "Strict\n4-step", "Strict\n16-step", "LR=3e-4\n64 attempt", "LR=1e-4\nclean 64"]
    summaries = [load_json(RUNS[key] / "summary.json") for key in order]
    updates = np.array([s.get("new_adam_updates", 0) for s in summaries])
    accepted = np.array([s.get("accepted_steps", 0) for s in summaries])
    status = [s.get("scientific_result", s.get("status", "UNKNOWN")) for s in summaries]
    colors = [COLORS["purple"], COLORS["blue"], COLORS["blue"], COLORS["red"], COLORS["green"]]

    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    x = np.arange(len(order))
    bars = ax.bar(x, updates, color=colors, width=0.66)
    ax.set_ylabel("Total Adam parameter updates")
    ax.set_xticks(x, labels)
    ax.set_title("Why 3,769 updates, 4 steps, and 64 steps are different quantities")
    ax.set_ylim(0, max(updates) * 1.22)
    ax.grid(axis="y", alpha=0.18, lw=0.6)

    for bar, n_step, stat in zip(bars, accepted, status):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(updates) * 0.025,
            f"{int(n_step)} physical step(s)\n{stat}",
            ha="center",
            va="bottom",
            fontsize=7.5,
        )

    ax.text(
        0.01,
        0.98,
        "One physical step contains up to two independent inner optimization fits (curl H and curl E).",
        transform=ax.transAxes,
        ha="left",
        va="top",
        color=COLORS["gray"],
        fontsize=8,
    )
    fig.tight_layout()
    save(fig, "optimizer_updates_vs_physical_steps")


def write_manifest():
    manifest = {
        "schema": "pidon-group-meeting-figures-v1",
        "read_only": True,
        "figures": {
            "clean_low_lr64_stepwise": {
                "source": str((RUNS["clean64_lr1e4"] / "steps.jsonl").relative_to(ROOT)),
                "meaning": "Per accepted physical step: H/E Adam updates, registered residual ratios, and global field error Q.",
            },
            "optimizer_updates_vs_physical_steps": {
                "sources": [str((RUNS[key] / "summary.json").relative_to(ROOT)) for key in RUNS],
                "meaning": "Separates optimizer parameter updates from accepted physical time steps across registered runs.",
            },
        },
    }
    (OUT / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    configure()
    clean64_stepwise()
    optimizer_vs_physical_steps()
    write_manifest()
    print(json.dumps({"status": "PASS", "output": str(OUT), "figures": 2}))


if __name__ == "__main__":
    main()
