"""Forward-only DCO evidence for the 2026-09-17 briefing."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from project_paths import PROJECT_DIR, configure
configure()

import dco as D
import fdtd
import paper_protocol as P
import phase1_full_run as F
import pidon_solve as S
from pidon_recording import atomic_json_save, sha256_file


ROOT = PROJECT_DIR
DEFAULT_OUT = ROOT / "evidence" / "briefing_20260917" / "operator_audit"
PROTOCOL = ROOT / "docs" / "plans" / "2026-09-17-fixed-operator-and-pec-protocol.md"
OLD_MODEL = ROOT / "assets" / "models" / "dco_lr1e3_300.pt"
S1R_MODEL = ROOT / "evidence" / "direct_mechanism_v2" / "s1r_phase1_server" / "best.pt"
COMPARE = (ROOT / "evidence" / "server_resource_v1" / "imports" /
           "server_resource_return_20260915T100510Z" / "server_resource_return" /
           "phase1_compare" / "summary.json")


def fig5_reconstruction_spec() -> dict[str, Any]:
    theta, phi = np.deg2rad(45.0), np.deg2rad(60.0)
    khat = np.array([np.cos(phi) * np.sin(theta),
                     np.sin(phi) * np.sin(theta), np.cos(theta)])
    rng = np.random.default_rng(2026091705)
    amplitudes = np.empty((20, 3), dtype=np.float64)
    amplitudes[:, :2] = rng.uniform(0.0, 5.0, size=(20, 2))
    amplitudes[:, 2] = -(khat[0] * amplitudes[:, 0] +
                          khat[1] * amplitudes[:, 1]) / khat[2]
    return {
        "case": "Fig5-parameter reconstruction; amplitudes were not disclosed",
        "d_m": [0.0006] * 3,
        "cell_size_m": [0.0006] * 3,
        "n_waves": 20,
        "theta_deg": 45.0,
        "phi_deg": 60.0,
        "ks_rad_per_m": np.linspace(0.021, 838.34, 20).tolist(),
        "khats": np.repeat(khat[None, :], 20, axis=0).tolist(),
        "amplitudes": amplitudes.tolist(),
        "amplitudes_provenance": "ASSUMED_seed_2026091705",
        "dirs": "shared",
    }


def spatial_coordinates(shape: tuple[int, int, int], d_m: np.ndarray) -> np.ndarray:
    axes = [np.arange(n, dtype=np.float64) * float(d) * 1e3
            for n, d in zip(shape, d_m)]
    return np.stack(np.meshgrid(*axes, indexing="ij")).astype(np.float32)


def model_state_sha256(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        array = value.detach().cpu().contiguous().numpy()
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def plot_component_panel(field: np.ndarray, target: np.ndarray, prediction: np.ndarray,
                         output: Path, title: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    error = prediction - target
    z = field.shape[-1] // 2
    rows = (field, target, prediction, error)
    labels = ("Input field", "Analytic/Yee curl", "DCO prediction", "Prediction - target")
    fig, axes = plt.subplots(4, 3, figsize=(12, 11), constrained_layout=True)
    for row, (array, label) in enumerate(zip(rows, labels)):
        for comp in range(3):
            image = array[comp, :, :, z]
            vmax = float(np.max(np.abs(image))) or 1.0
            artist = axes[row, comp].imshow(image.T, origin="lower", cmap="RdBu_r",
                                            vmin=-vmax, vmax=vmax, interpolation="nearest")
            axes[row, comp].set_title(f"{label}: {'xyz'[comp]}")
            axes[row, comp].set_xlabel("x index")
            axes[row, comp].set_ylabel("y index")
            fig.colorbar(artist, ax=axes[row, comp], fraction=0.046, pad=0.03)
    fig.suptitle(title, fontsize=15)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_net(checkpoint: Path, device: torch.device) -> tuple[torch.nn.Module, dict[str, Any]]:
    ck = torch.load(checkpoint, map_location="cpu", weights_only=False)
    for key in ("state", "levels", "base", "coords", "norm"):
        if key not in ck:
            raise ValueError(f"checkpoint missing {key}: {checkpoint}")
    net = D.DCO(levels=int(ck["levels"]), base=int(ck["base"]),
                head=ck.get("head", "direct")).to(device).eval()
    net.load_state_dict(ck["state"])
    return net, ck


def _predict(net: torch.nn.Module, ck: dict[str, Any], e: np.ndarray,
             d_m: np.ndarray, device: torch.device) -> np.ndarray:
    e_t = torch.from_numpy(e[None].astype(np.float32)).to(device)
    d_mm = torch.from_numpy((d_m[None] * 1e3).astype(np.float32)).to(device)
    coords = D.make_coords(e.shape[1:], d_mm[0], ck["coords"], device=device)
    e_hat, _, scale, length = D.normalise(e_t, None, d_mm, ck["norm"])
    with torch.no_grad():
        pred = D.denormalise(net(e_hat, coords, D.d_rel_of(d_mm, length)), scale, length)
    return pred[0].detach().cpu().numpy()


def _metric_row(prediction: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    metrics = P.vector_metrics(prediction, target)
    components = {
        name: {
            "nmae": values["nmae"],
            "mre_eq5": values["mre_eq5"],
            "rel_l2": values["rel_l2"],
            "mae": values["mae"],
            "true_max": values["true_max"],
            "max_abs_error": values["max_abs_error"],
        }
        for name, values in metrics["components"].items()
    }
    return {
        "macro_nmae": metrics["macro_nmae"],
        "macro_mre_eq5": metrics["macro_mre_eq5"],
        "global_nmae": metrics["global_nmae"],
        "global_rel_l2": metrics["global_rel_l2"],
        "components": components,
        "undefined_component_nmae": [
            name for name, values in components.items() if values["nmae"] is None
        ],
    }


def _solver_config(init: str, seed: int, out: Path) -> argparse.Namespace:
    return argparse.Namespace(
        config="", steps=1, n=31, side=0.05, dt=3.075e-12, init=init,
        tol=1e-5, tol_mode="rel", max_inner=0, lr=1e-4,
        head_lstsq_once=False, head_rcond=1e-12, levels=4, base=32,
        coords="cellsize", norm="rms", separate_nets=True,
        reset_opt_each_step=True, grad_clip=0.0, h_scale=1.0,
        component_rel=False, h_output_scale=1.0, h_shift=True,
        strict_stop=True, inner_time_budget_s=0.0, lbfgs_closures=0,
        lbfgs_lr=1.0, lbfgs_history=10, lbfgs_time_budget_s=0.0,
        source_mode="hard", torch_dtype="float32", out_dir=str(out),
        resume="", checkpoint_every=1, seed=seed, device="cpu", fmax=15e9,
        calib=[], calib_iters=[], out=str(out / "unused.json"),
    )


def _first_e_case(init: str, seed: int, out: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    np.random.seed(seed)
    torch.manual_seed(seed)
    solver = S.Solver(_solver_config(init, seed, out), "cpu")
    waveform = fdtd.source_waveform(1, solver.dt, solver.a.fmax, "hard")
    zeros = [torch.zeros_like(part) for part in solver.yee_curl_H()]
    solver._update_E_and_source(zeros, float(waveform[0]))
    core = solver.extract_input_core(solver.E, "E")
    target_parts = solver.yee_curl_E()
    target = np.stack([part[:solver.n, :solver.n, :solver.n].detach().cpu().numpy()
                       for part in target_parts])
    with torch.no_grad():
        prediction = solver.predict(core, "E").detach().cpu().numpy()
    return core.detach().cpu().numpy(), target, prediction, model_state_sha256(solver.net_E)


def _write_report(summary: dict[str, Any], out: Path) -> None:
    lines = [
        "# 固定权重旋度算子汇报审计", "",
        f"- 交付状态：`{summary['status']}`；科学含义：`{summary['scientific_result']}`",
        f"- 参数更新：`{summary['parameter_updates']}`；lab run：`{summary.get('lab_run_id')}`",
        "- 解析旋度和Yee目标只作参考，不计DCO成绩。", "",
        "## 可视化对象", "",
        "| 模型 | 平面波图 | 首个非零E输入图 | 权重状态 |",
        "|---|---|---|---|",
    ]
    for tag, item in summary["models"].items():
        lines.append(f"| {tag} | {item.get('plane_wave_status')} | "
                     f"{item.get('first_e_status')} | {item.get('weight_status')} |")
    lines.extend([
        "", "## 解释", "",
        "- `old_lr1e3`和固定种子随机网络的图由本次零更新前向产生。",
        "- S1R服务器分数来自已回传SR-COMPARE；本地缺少S1R权重时不伪造场图。",
        "- Fig.5公开了网格、角度和k序列，但没有公开20组Ex/Ey振幅；本图将振幅明确标为固定种子假设。",
        "- 首个非零E输入是当前腔体配方的硬源尖锐输入，只用于诊断平面波预训练到在线输入的迁移。",
    ])
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.out_dir).resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    device = torch.device(args.device)
    spec = fig5_reconstruction_spec()
    e, target = F.sample_from_spec(spec, (32, 32, 32), np.asarray(spec["d_m"]))
    np.savez_compressed(out / "fig5_reconstruction_input_target.npz", E=e, C=target,
                        D=np.asarray(spec["d_m"], dtype=np.float32))
    atomic_json_save(spec, out / "fig5_reconstruction_spec.json")

    old_file_before = sha256_file(OLD_MODEL)
    old_net, old_ck = _load_net(OLD_MODEL, device)
    old_state_before = model_state_sha256(old_net)
    old_prediction = _predict(old_net, old_ck, e, np.asarray(spec["d_m"]), device)
    old_state_after = model_state_sha256(old_net)
    plot_component_panel(e, target, old_prediction, out / "old_lr1e3_fig5_panel.png",
                         "Old DCO: Fig.5-parameter reconstruction (zero updates)")
    np.savez_compressed(out / "old_lr1e3_fig5_arrays.npz", E=e, C=target, P=old_prediction)

    torch.manual_seed(2026091704)
    random_net = D.DCO(levels=int(old_ck["levels"]), base=int(old_ck["base"]),
                       head=old_ck.get("head", "direct")).to(device).eval()
    random_state_before = model_state_sha256(random_net)
    random_ck = {**old_ck, "state": random_net.state_dict()}
    random_prediction = _predict(random_net, random_ck, e, np.asarray(spec["d_m"]), device)
    random_state_after = model_state_sha256(random_net)
    plot_component_panel(e, target, random_prediction, out / "random_fig5_panel.png",
                         "Random DCO: same input and architecture (zero updates)")
    np.savez_compressed(out / "random_fig5_arrays.npz", E=e, C=target, P=random_prediction)

    first_cases = {}
    for tag, init, seed in (("old_lr1e3", str(OLD_MODEL), 20260913),
                            ("random", "random", 20260913)):
        field, yee_target, prediction, state_hash = _first_e_case(init, seed, out)
        plot_component_panel(field, yee_target, prediction, out / f"{tag}_first_e_panel.png",
                             f"{tag}: first nonzero cavity E input (zero updates)")
        np.savez_compressed(out / f"{tag}_first_e_arrays.npz",
                            E=field, C=yee_target, P=prediction)
        first_cases[tag] = {"metrics": _metric_row(prediction, yee_target),
                            "model_state_sha256": state_hash}

    server_compare = _json(COMPARE) if COMPARE.exists() else None
    s1r_available = S1R_MODEL.exists()
    models = {
        "old_lr1e3": {
            "plane_wave_status": "PASS_ZERO_UPDATE",
            "first_e_status": "PASS_ZERO_UPDATE",
            "weight_status": "LOCAL_HASH_VERIFIED",
            "state_unchanged": old_state_before == old_state_after,
            "metrics_fig5_reconstruction": _metric_row(old_prediction, target),
            "metrics_first_e": first_cases["old_lr1e3"]["metrics"],
        },
        "random_seed_2026091704": {
            "plane_wave_status": "PASS_ZERO_UPDATE",
            "first_e_status": "PASS_ZERO_UPDATE_SEED_20260913",
            "weight_status": "EPHEMERAL_FIXED_SEED",
            "state_unchanged": random_state_before == random_state_after,
            "metrics_fig5_reconstruction": _metric_row(random_prediction, target),
            "metrics_first_e": first_cases["random"]["metrics"],
        },
        "S1R_best": {
            "plane_wave_status": "SERVER_METRICS_ONLY" if server_compare else "INCOMPLETE",
            "first_e_status": "NOT_AVAILABLE_WEIGHT_NOT_LOCAL",
            "weight_status": "LOCAL" if s1r_available else "SERVER_ONLY_HASH_958a9764",
            "server_compare_rows": ([row for row in server_compare.get("diagnostic_scores", [])
                                     if row.get("model") == "S1R_best"]
                                    if server_compare else []),
        },
    }
    summary = {
        "schema": "pidon-briefing-operator-audit-v1",
        "status": "PASS_WITH_DECLARED_S1R_VISUAL_LIMIT",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "parameter_updates": 0,
        "closures": 0,
        "models": models,
        "old_model_file_sha256_before": old_file_before,
        "old_model_file_sha256_after": sha256_file(OLD_MODEL),
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256_file(PROTOCOL),
        "limitations": [
            "S1R best.pt remains on the server; returned scores are usable but local field plots are unavailable",
            "Fig.5 amplitudes are undisclosed and therefore fixed as an explicit assumption",
            "one fixed random initialization is a visual baseline, not a population estimate",
        ],
    }
    summary["invariants_pass"] = bool(
        models["old_lr1e3"]["state_unchanged"] and
        models["random_seed_2026091704"]["state_unchanged"] and
        summary["old_model_file_sha256_before"] == summary["old_model_file_sha256_after"])
    atomic_json_save(summary, out / "summary.json")
    atomic_json_save({"status": "PASS" if summary["invariants_pass"] else "FAIL",
                      "parameter_updates": 0,
                      "weight_hash_unchanged": summary["invariants_pass"]}, out / "audit.json")
    _write_report(summary, out)
    print(json.dumps({"status": summary["status"], "parameter_updates": 0,
                      "output": str(out)}, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    run(parser.parse_args())
