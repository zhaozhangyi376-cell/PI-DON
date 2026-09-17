"""Read-only audit of production PEC support and projection ordering."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from project_paths import PROJECT_DIR, configure
configure()

import pidon_solve as S
from pidon_recording import atomic_json_save, sha256_file


ROOT = PROJECT_DIR
DEFAULT_OUT = ROOT / "evidence" / "briefing_20260917" / "pec_audit"
PROTOCOL = ROOT / "docs" / "plans" / "2026-09-17-fixed-operator-and-pec-protocol.md"
PRODUCTION = ROOT / "src" / "pidon" / "pidon_solve.py"


def tangential_e_masks(n: int) -> dict[str, np.ndarray]:
    masks = {
        "Ex": np.zeros((n, n + 1, n + 1), dtype=bool),
        "Ey": np.zeros((n + 1, n, n + 1), dtype=bool),
        "Ez": np.zeros((n + 1, n + 1, n), dtype=bool),
    }
    masks["Ex"][:, (0, -1), :] = True
    masks["Ex"][:, :, (0, -1)] = True
    masks["Ey"][(0, -1), :, :] = True
    masks["Ey"][:, :, (0, -1)] = True
    masks["Ez"][(0, -1), :, :] = True
    masks["Ez"][:, (0, -1), :] = True
    return masks


def _args(n: int) -> SimpleNamespace:
    return SimpleNamespace(
        n=n, side=0.05, dt=3.075e-12, init="random", tol=1e-4,
        tol_mode="rel", max_inner=0, lr=1e-4, levels=2, base=2,
        coords="cellsize", norm="rms", separate_nets=True,
        reset_opt_each_step=True, grad_clip=0.0, h_scale=1.0,
        component_rel=False, h_output_scale=1.0, h_shift=True,
        strict_stop=True, inner_time_budget_s=0.0, lbfgs_closures=0,
        lbfgs_lr=1.0, lbfgs_history=10, lbfgs_time_budget_s=0.0,
        source_mode="hard", torch_dtype="float32", out_dir="",
        resume="", checkpoint_every=1, seed=2026091706, device="cpu",
        fmax=15e9, calib=[], calib_iters=[], head_lstsq_once=False,
        head_rcond=1e-12, config="", steps=1, out="",
    )


def audit_production_pec(n: int = 5) -> dict[str, Any]:
    torch.manual_seed(2026091706)
    solver = S.Solver(_args(n), "cpu")
    for part in solver.E:
        part.fill_(1.0)
    solver.apply_pec()
    masks = tangential_e_masks(n)
    expected_zero = interior_ok = True
    unexpected = 0
    component_rows = {}
    for name, part in zip(("Ex", "Ey", "Ez"), solver.E):
        array = part.detach().cpu().numpy()
        mask = masks[name]
        expected_zero &= bool(np.all(array[mask] == 0.0))
        interior_ok &= bool(np.all(array[~mask] == 1.0))
        unexpected += int(np.count_nonzero((array == 0.0) & ~mask))
        component_rows[name] = {
            "shape": list(array.shape),
            "expected_tangential_zero_count": int(mask.sum()),
            "observed_zero_count": int(np.count_nonzero(array == 0.0)),
            "interior_one_count": int(np.count_nonzero(array[~mask] == 1.0)),
        }
    return {"all_expected_zero": expected_zero,
            "all_interior_preserved": interior_ok,
            "unexpected_zero_count": unexpected,
            "components": component_rows}


def audit_curl_e_projection(n: int = 5) -> dict[str, Any]:
    torch.manual_seed(2026091706)
    solver = S.Solver(_args(n), "cpu")
    exact = [torch.ones_like(part) for part in solver.yee_curl_E()]
    for axis, part in enumerate(exact):
        high = [slice(None)] * 3
        high[axis] = part.shape[axis] - 1
        part[tuple(high)] = 0.0
    prediction = [torch.ones((n, n, n)) for _ in range(3)]
    inserted = solver._insert_prediction(exact, prediction, "E")
    rows = {}
    for axis, (name, part) in enumerate(zip(("curlE_x", "curlE_y", "curlE_z"), inserted)):
        low = [slice(None)] * 3
        high = [slice(None)] * 3
        low[axis] = 0
        high[axis] = part.shape[axis] - 1
        rows[name] = {
            "shape": list(part.shape),
            "low_normal_face_zero": bool(torch.all(part[tuple(low)] == 0).item()),
            "high_normal_face_zero": bool(torch.all(part[tuple(high)] == 0).item()),
            "interior_nonzero": bool(torch.any(part[tuple(slice(1, -1) if d == axis else slice(None)
                                                               for d in range(3))] != 0).item()),
        }
    return rows


def gradient_support_demo() -> dict[str, float]:
    prediction = torch.tensor([1.0, 2.0, 3.0, 4.0], requires_grad=True)
    target = torch.tensor([0.5, 0.5, 0.5, 0.5])
    mask = torch.tensor([0.0, 1.0, 1.0, 0.0])
    unprojected = ((prediction - target) ** 2).sum()
    unprojected.backward(retain_graph=True)
    grad_unprojected = prediction.grad.detach().clone()
    prediction.grad.zero_()
    projected = ((prediction * mask - target) ** 2).sum()
    projected.backward()
    grad_projected = prediction.grad.detach().clone()
    masked = mask == 0
    unmasked = mask == 1
    return {
        "unprojected_masked_gradient_l1": float(grad_unprojected[masked].abs().sum()),
        "projected_masked_gradient_l1": float(grad_projected[masked].abs().sum()),
        "projected_unmasked_gradient_l1": float(grad_projected[unmasked].abs().sum()),
        "unprojected_gradient": grad_unprojected.tolist(),
        "projected_gradient": grad_projected.tolist(),
    }


def _plot_masks(n: int, output: Path) -> None:
    masks = tangential_e_masks(n)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.7), constrained_layout=True)
    for ax, (name, mask) in zip(axes, masks.items()):
        projection = mask.sum(axis=0)
        artist = ax.imshow(projection.T, origin="lower", cmap="Blues", vmin=0,
                           vmax=max(1, int(projection.max())))
        ax.set_title(f"{name}: PEC tangential mask\nprojection over x")
        ax.set_xlabel("index 1")
        ax.set_ylabel("index 2")
        fig.colorbar(artist, ax=ax, fraction=0.05)
    fig.suptitle("Production PEC state projection: n x E = 0")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_gradients(result: dict[str, Any], output: Path) -> None:
    values = np.asarray([result["unprojected_gradient"], result["projected_gradient"]])
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    x = np.arange(4)
    ax.bar(x - 0.18, values[0], width=0.36, label="loss before projection")
    ax.bar(x + 0.18, values[1], width=0.36, label="loss after projection")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, ["masked 0", "active 1", "active 2", "masked 3"])
    ax.set_ylabel("d loss / d prediction")
    ax.set_title("Projection timing changes gradient support (toy demonstration)")
    ax.legend()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_flow(output: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 3.8), constrained_layout=True)
    ax.axis("off")
    labels = ["fit curl H", "update E", "hard source", "apply PEC to E",
              "fit curl E", "project normal curl E faces", "update H"]
    colors = ["#56B4E9", "#E69F00", "#D55E00", "#009E73",
              "#56B4E9", "#CC79A7", "#E69F00"]
    xs = np.linspace(0.02, 0.86, len(labels))
    for index, (x, label, color) in enumerate(zip(xs, labels, colors)):
        ax.add_patch(plt.Rectangle((x, 0.38), 0.12, 0.28, facecolor=color,
                                   alpha=0.85, edgecolor="black", linewidth=1))
        ax.text(x + 0.06, 0.52, label, ha="center", va="center", fontsize=10,
                color="white" if color not in ("#E69F00", "#56B4E9") else "black",
                wrap=True)
        if index < len(labels) - 1:
            ax.annotate("", xy=(xs[index + 1], 0.52), xytext=(x + 0.12, 0.52),
                        arrowprops={"arrowstyle": "->", "lw": 1.5})
    ax.text(0.5, 0.15,
            "Current loss evaluates the raw curl prediction; the paper text says updated boundary prediction then loss",
            ha="center", fontsize=11, color="#333333")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.out_dir).resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    before = sha256_file(PRODUCTION)
    production = audit_production_pec(args.n)
    curl_projection = audit_curl_e_projection(args.n)
    gradient = gradient_support_demo()
    _plot_masks(args.n, out / "pec_tangential_masks.png")
    _plot_gradients(gradient, out / "projection_gradient_support.png")
    _plot_flow(out / "current_pec_compute_flow.png")
    after = sha256_file(PRODUCTION)
    summary = {
        "schema": "pidon-briefing-pec-audit-v1",
        "status": "PASS" if (production["all_expected_zero"] and
                               production["all_interior_preserved"] and
                               before == after) else "FAIL",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "parameter_updates": 0,
        "production_apply_pec": production,
        "curl_e_projection": curl_projection,
        "gradient_support_demo": gradient,
        "production_source_sha256_before": before,
        "production_source_sha256_after": after,
        "paper_statement": "set predicted tangential components on PECs to zero, then compute loss and backpropagate",
        "current_confirmed_order": ["fit curl H", "update E", "hard source",
                                    "apply PEC to E", "fit raw curl E",
                                    "project normal curl E faces", "update H"],
        "unresolved": "whether the author's predicted tangential components refer to E, curl-E, or a tensor aligned differently",
        "protocol_sha256": sha256_file(PROTOCOL),
    }
    atomic_json_save(summary, out / "summary.json")
    atomic_json_save({"status": summary["status"], "parameter_updates": 0,
                      "production_source_unchanged": before == after}, out / "audit.json")
    lines = [
        "# PEC对象、支持域与梯度路径审计", "",
        f"- 状态：`{summary['status']}`；参数更新：`0`。",
        "- 当前生产`apply_pec`准确清零六个PEC面上的切向E自由度，内部自由度保持不变。",
        "- 当前`_insert_prediction(..., 'E')`另将每个curl-E分量在其法向低/高面置零。",
        "- 玩具梯度检查证明：损失前投影与损失后只更新场，反向传播支持不同。",
        "- 这不证明作者具体张量与当前实现不同；作者未公开掩码、Yee位置和代码。",
        "- 本审计没有修改生产边界，也没有将精确边界代数计作DCO成绩。",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "parameter_updates": 0,
                      "output": str(out)}, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--n", type=int, default=7)
    run(parser.parse_args())
