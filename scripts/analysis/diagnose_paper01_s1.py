from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
PAPER01_SRC = ROOT / "_01" / "src"
if str(PAPER01_SRC) not in sys.path:
    sys.path.insert(0, str(PAPER01_SRC))

from paper01.data import sample_from_spec, spatial_coordinates  # noqa: E402
from paper01.metrics import eq5_mre, nmae, rel_l2  # noqa: E402
from paper01.model import DCO, component_local_max_normalize  # noqa: E402


DEFAULT_RUN = ROOT / "evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def safe_corr(xs: list[float], ys: list[float]) -> float | None:
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 3:
        return None
    x = x[mask]
    y = y[mask]
    if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def percentile(values: list[float], q: float) -> float:
    arr = np.asarray(values, dtype=np.float64)
    return float(np.percentile(arr, q)) if arr.size else float("nan")


def summarize_values(values: list[float]) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)) if values else float("nan"),
        "median": percentile(values, 50),
        "p90": percentile(values, 90),
        "max": max(values) if values else float("nan"),
    }


def group_by_bins(rows: list[dict[str, Any]], feature: str, bins: list[float]) -> list[dict[str, Any]]:
    result = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        selected = [row for row in rows if lo <= float(row[feature]) < hi or (hi == bins[-1] and float(row[feature]) == hi)]
        result.append({
            "feature": feature,
            "lo": lo,
            "hi": hi,
            "count": len(selected),
            "macro_nmae": summarize_values([float(row["macro_nmae"]) for row in selected]),
            "global_rel_l2": summarize_values([float(row["global_rel_l2"]) for row in selected]),
        })
    return result


def history_trend(history_path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    checks = []
    for row in rows:
        if row.get("test_mse") is not None:
            checks.append({"update": int(row["update"]), "test_mse": float(row["test_mse"])})
    lookup = {item["update"]: item["test_mse"] for item in checks}
    anchors = [u for u in [1, 1000, 5000, 10000, 15000, 20000, 25000] if u in lookup]
    last_5k_drop = None
    if 20000 in lookup and 25000 in lookup:
        last_5k_drop = (lookup[20000] - lookup[25000]) / lookup[20000]
    last_10k_drop = None
    if 15000 in lookup and 25000 in lookup:
        last_10k_drop = (lookup[15000] - lookup[25000]) / lookup[15000]
    return {
        "validation_points": checks,
        "anchors": [{"update": update, "test_mse": lookup[update]} for update in anchors],
        "last_5k_relative_drop": last_5k_drop,
        "last_10k_relative_drop": last_10k_drop,
    }


def kd_features(spec: dict[str, Any]) -> tuple[float, float]:
    cell = np.asarray(spec["cell_size_m"], dtype=np.float64)
    khat = np.asarray(spec["khat"], dtype=np.float64)
    ks = np.asarray(spec["ks_rad_per_m"], dtype=np.float64)
    axis_kd = np.abs(ks[:, None] * khat[None, :] * cell[None, :])
    return float(axis_kd.max()), float(np.mean(axis_kd.max(axis=1)))


@torch.no_grad()
def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir)
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"output directory is non-empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    manifest = load_json(run_dir / "manifest.json")
    summary = load_json(run_dir / "summary.json")
    specs = load_json(run_dir / "sample_specs.json")
    checkpoint_path = run_dir / "best.pt"
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = ckpt["config"]
    grid = int(config["grid"])
    train_n = max(1, int(0.8 * int(config["samples"])))
    test_indices = list(range(train_n, int(config["samples"])))
    if args.limit:
        test_indices = test_indices[: int(args.limit)]

    device = torch.device(args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu"))
    model = DCO(int(config["levels"]), int(config["base"])).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    rows: list[dict[str, Any]] = []
    comp_values: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    comp_rell2: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    comp_mre: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    shape = (grid, grid, grid)
    for index in test_indices:
        spec = specs[index]
        field, curl = sample_from_spec(spec, shape)
        coords = spatial_coordinates(shape, np.asarray(spec["cell_size_m"], dtype=np.float64))
        field_t = torch.from_numpy(field[None]).to(device)
        curl_t = torch.from_numpy(curl[None]).to(device)
        coords_t = torch.from_numpy(coords[None]).to(device)
        normalized, scale = component_local_max_normalize(curl_t)
        prediction = model(field_t, coords_t).detach().cpu().numpy()[0]
        target = normalized.detach().cpu().numpy()[0]
        field_np = field
        component_rows = {}
        component_nmae = []
        component_rel = []
        component_eq5 = []
        for ci, name in enumerate(("x", "y", "z")):
            c_nmae = nmae(prediction[ci], target[ci])
            c_rel = rel_l2(prediction[ci], target[ci])
            c_mre = eq5_mre(prediction[ci], target[ci])
            component_nmae.append(c_nmae)
            component_rel.append(c_rel)
            component_eq5.append(c_mre)
            comp_values[name].append(c_nmae)
            comp_rell2[name].append(c_rel)
            comp_mre[name].append(c_mre)
            component_rows[name] = {
                "nmae": c_nmae,
                "rel_l2": c_rel,
                "mre_eq5": c_mre,
                "target_max": float(np.max(np.abs(target[ci]))),
                "physical_curl_max": float(scale.cpu().numpy()[0, ci, 0, 0, 0]),
            }
        kd_max, kd_mean = kd_features(spec)
        amplitudes = np.asarray(spec["amplitudes"], dtype=np.float64)
        cell = np.asarray(spec["cell_size_m"], dtype=np.float64)
        khat = np.asarray(spec["khat"], dtype=np.float64)
        row = {
            "sample_index": index,
            "macro_nmae": float(np.mean(component_nmae)),
            "global_rel_l2": rel_l2(prediction, target),
            "macro_mre_eq5": float(np.mean(component_eq5)),
            "x_nmae": component_rows["x"]["nmae"],
            "y_nmae": component_rows["y"]["nmae"],
            "z_nmae": component_rows["z"]["nmae"],
            "x_rel_l2": component_rows["x"]["rel_l2"],
            "y_rel_l2": component_rows["y"]["rel_l2"],
            "z_rel_l2": component_rows["z"]["rel_l2"],
            "x_mre_eq5": component_rows["x"]["mre_eq5"],
            "y_mre_eq5": component_rows["y"]["mre_eq5"],
            "z_mre_eq5": component_rows["z"]["mre_eq5"],
            "x_curl_max": component_rows["x"]["physical_curl_max"],
            "y_curl_max": component_rows["y"]["physical_curl_max"],
            "z_curl_max": component_rows["z"]["physical_curl_max"],
            "field_rms": float(np.sqrt(np.mean(field_np ** 2))),
            "curl_rms": float(np.sqrt(np.mean(curl ** 2))),
            "theta": float(spec["theta"]),
            "phi": float(spec["phi"]),
            "abs_cos_theta": float(abs(math.cos(float(spec["theta"])))),
            "k_max": float(np.max(spec["ks_rad_per_m"])),
            "k_mean": float(np.mean(spec["ks_rad_per_m"])),
            "kd_axis_max": kd_max,
            "kd_axis_mean": kd_mean,
            "cell_min_m": float(cell.min()),
            "cell_max_m": float(cell.max()),
            "cell_anisotropy": float(cell.max() / cell.min()),
            "max_abs_amp": float(np.max(np.abs(amplitudes))),
            "max_abs_ez_amp": float(np.max(np.abs(amplitudes[:, 2]))),
            "mean_abs_ez_amp": float(np.mean(np.abs(amplitudes[:, 2]))),
            "khat_z_abs": float(abs(khat[2])),
        }
        rows.append(row)

    csv_path = out / "per_sample.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    trend = history_trend(run_dir / "history.jsonl")
    correlations = {
        feature: safe_corr([float(row[feature]) for row in rows], [float(row["macro_nmae"]) for row in rows])
        for feature in [
            "abs_cos_theta", "khat_z_abs", "k_max", "k_mean", "kd_axis_max",
            "kd_axis_mean", "cell_anisotropy", "max_abs_amp", "max_abs_ez_amp",
            "mean_abs_ez_amp", "field_rms", "curl_rms",
        ]
    }
    worst_macro = sorted(rows, key=lambda row: float(row["macro_nmae"]), reverse=True)[:10]
    worst_rel = sorted(rows, key=lambda row: float(row["global_rel_l2"]), reverse=True)[:10]
    component_summary = {
        name: {
            "nmae": summarize_values(values),
            "rel_l2": summarize_values(comp_rell2[name]),
            "mre_eq5": summarize_values(comp_mre[name]),
        }
        for name, values in comp_values.items()
    }
    bins = {
        "abs_cos_theta": group_by_bins(rows, "abs_cos_theta", [0.15, 0.25, 0.5, 0.75, 1.0]),
        "kd_axis_max": group_by_bins(
            rows,
            "kd_axis_max",
            [float(np.min([r["kd_axis_max"] for r in rows])), *np.percentile([r["kd_axis_max"] for r in rows], [25, 50, 75]).tolist(), float(np.max([r["kd_axis_max"] for r in rows]))],
        ),
    }
    result = {
        "schema": "pidon-paper01-s1-failure-diagnosis-v1",
        "status": "PASS",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "parameter_updates": 0,
        "run_dir": str(run_dir),
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": sha256(checkpoint_path),
        "manifest_contract_sha256": manifest.get("contract_sha256"),
        "summary_scientific_result": summary.get("scientific_result"),
        "device": str(device),
        "test_sample_count": len(rows),
        "history_trend": trend,
        "overall": {
            "macro_nmae": summarize_values([float(row["macro_nmae"]) for row in rows]),
            "global_rel_l2": summarize_values([float(row["global_rel_l2"]) for row in rows]),
            "macro_mre_eq5": summarize_values([float(row["macro_mre_eq5"]) for row in rows]),
        },
        "components": component_summary,
        "correlations_with_macro_nmae": correlations,
        "bins": bins,
        "worst_macro_nmae": worst_macro,
        "worst_global_rel_l2": worst_rel,
        "interpretation": {
            "last_5k_drop_small": trend["last_5k_relative_drop"] is not None and trend["last_5k_relative_drop"] < 0.05,
            "dominant_component_by_mean_nmae": max(component_summary, key=lambda name: component_summary[name]["nmae"]["mean"]),
            "strongest_abs_correlation": max(
                [(k, v) for k, v in correlations.items() if v is not None],
                key=lambda item: abs(item[1]),
                default=(None, None),
            ),
        },
    }
    write_json(out / "summary.json", result)
    make_plots(out, trend, rows)
    write_report(out / "REPORT.md", result)
    return result


def make_plots(out: Path, trend: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    validations = trend["validation_points"]
    plt.figure(figsize=(7.0, 4.0))
    plt.plot([v["update"] for v in validations], [v["test_mse"] for v in validations], marker="o", ms=2)
    plt.xlabel("Adam update")
    plt.ylabel("normalized test MSE")
    plt.title("PAPER01-S1 validation trend")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out / "history_curve.png", dpi=180)
    plt.close()

    data = [[row[f"{name}_nmae"] * 100.0 for row in rows] for name in ["x", "y", "z"]]
    plt.figure(figsize=(6.0, 4.0))
    plt.boxplot(data, tick_labels=["curl-x", "curl-y", "curl-z"], showfliers=True)
    plt.ylabel("component nMAE (%)")
    plt.title("PAPER01-S1 component error on held-out samples")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out / "component_error_box.png", dpi=180)
    plt.close()


def write_report(path: Path, result: dict[str, Any]) -> None:
    strongest = result["interpretation"]["strongest_abs_correlation"]
    lines = [
        "# PAPER01-S1 第一阶段失败诊断",
        "",
        f"- 状态：`{result['status']}`；科学含义：`{result['scientific_result']}`",
        f"- 参数更新：`{result['parameter_updates']}`",
        f"- 测试样本：`{result['test_sample_count']}`",
        f"- checkpoint SHA256：`{result['checkpoint_sha256']}`",
        "",
        "## 收敛趋势",
        "",
        f"- 最后5000更新 test MSE 相对下降：`{result['history_trend']['last_5k_relative_drop']}`",
        f"- 最后10000更新 test MSE 相对下降：`{result['history_trend']['last_10k_relative_drop']}`",
        "",
        "## 总体误差",
        "",
        "| 指标 | mean | median | p90 | max |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in [("macro_nmae", "macro nMAE"), ("global_rel_l2", "global relL2"), ("macro_mre_eq5", "Eq.(5) MRE")]:
        row = result["overall"][key]
        lines.append(f"| {label} | {row['mean']:.6g} | {row['median']:.6g} | {row['p90']:.6g} | {row['max']:.6g} |")
    lines.extend([
        "",
        "## 分量误差",
        "",
        "| 分量 | nMAE mean | nMAE p90 | relL2 mean | Eq.(5) MRE mean |",
        "|---|---:|---:|---:|---:|",
    ])
    for name in ["x", "y", "z"]:
        row = result["components"][name]
        lines.append(
            f"| curl-{name} | {row['nmae']['mean']:.6g} | {row['nmae']['p90']:.6g} | "
            f"{row['rel_l2']['mean']:.6g} | {row['mre_eq5']['mean']:.6g} |"
        )
    lines.extend([
        "",
        "## 特征相关性",
        "",
        f"- 与macro nMAE绝对相关性最大的特征：`{strongest[0]}` = `{strongest[1]}`",
        "",
        "## 最差样本",
        "",
        "| sample | macro nMAE | relL2 | abs(cos theta) | kd_axis_max | max |Ez amp| |",
        "|---:|---:|---:|---:|---:|---:|",
    ])
    for row in result["worst_macro_nmae"][:8]:
        lines.append(
            f"| {row['sample_index']} | {row['macro_nmae']:.6g} | {row['global_rel_l2']:.6g} | "
            f"{row['abs_cos_theta']:.4f} | {row['kd_axis_max']:.4f} | {row['max_abs_ez_amp']:.4g} |"
        )
    lines.extend([
        "",
        "## 初步判读",
        "",
        "- 最后5000更新下降幅度若很小，说明单纯原样延长训练优先级较低。",
        "- 若某一分量显著更差，下一步应优先检查该分量的幅值构造、归一化和输出支撑。",
        "- 若误差与`abs(cos theta)`、`kd_axis_max`或Ez幅值强相关，说明失败可能集中在角度奇异、波数/网格尺度或Eq.(4)幅值放大区域。",
        "- 本诊断不改变`PAPER01-S1`科学FAIL，不授权第二阶段或长程。",
        "",
        "## 图",
        "",
        "- `history_curve.png`",
        "- `component_error_box.png`",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose PAPER01-S1 held-out error without training.")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN))
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--limit", type=int, default=0, help="debug/test only")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = evaluate(args)
    print(json.dumps({
        "status": result["status"],
        "scientific_result": result["scientific_result"],
        "parameter_updates": result["parameter_updates"],
        "output": str(Path(args.out)),
        "test_sample_count": result["test_sample_count"],
        "dominant_component": result["interpretation"]["dominant_component_by_mean_nmae"],
        "last_5k_relative_drop": result["history_trend"]["last_5k_relative_drop"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
