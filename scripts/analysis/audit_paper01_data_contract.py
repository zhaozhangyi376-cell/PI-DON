from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[2]
PAPER01_SRC = ROOT / "_01" / "src"
if str(PAPER01_SRC) not in sys.path:
    sys.path.insert(0, str(PAPER01_SRC))

from paper01.data import sample_from_spec  # noqa: E402
from paper01.model import component_local_max_normalize  # noqa: E402


DEFAULT_RUN = ROOT / "evidence" / "paper01_s1" / "imports" / "server_paper01_return_20260917T015828Z" / "_01" / "evidence" / "paper01_s1_v1"
DEFAULT_ERROR_CSV = ROOT / "evidence" / "paper01_s1" / "failure_diagnosis_v1" / "per_sample.csv"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def summarize(values: list[float]) -> dict[str, float | int | None]:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    if not finite:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    arr = np.asarray(finite, dtype=np.float64)
    return {
        "count": int(arr.size),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p90": float(np.percentile(arr, 90)),
        "max": float(np.max(arr)),
    }


def safe_corr(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return None
    x = np.asarray([p[0] for p in pairs], dtype=np.float64)
    y = np.asarray([p[1] for p in pairs], dtype=np.float64)
    if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def bins(rows: list[dict[str, Any]], feature: str, edges: list[float]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        chosen = [r for r in rows if lo <= float(r[feature]) < hi or (hi == edges[-1] and float(r[feature]) == hi)]
        out.append({
            "range": [lo, hi],
            "count": len(chosen),
            "macro_nmae": summarize([r.get("macro_nmae", float("nan")) for r in chosen]),
            "z_nmae": summarize([r.get("z_nmae", float("nan")) for r in chosen]),
            "z_active_fraction_0p1": summarize([r["z_active_fraction_0p1"] for r in chosen]),
            "max_abs_ez_ratio": summarize([r["max_abs_ez_over_xy"] for r in chosen]),
        })
    return out


def load_error_rows(path: Path) -> dict[int, dict[str, float]]:
    if not path.exists():
        return {}
    rows: dict[int, dict[str, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sample = int(row["sample_index"])
            rows[sample] = {
                key: float(value)
                for key, value in row.items()
                if key != "sample_index" and value not in {"", "None", "nan"}
            }
    return rows


def transversality(spec: dict[str, Any]) -> dict[str, float]:
    khat = np.asarray(spec["khat"], dtype=np.float64)
    amp = np.asarray(spec["amplitudes"], dtype=np.float64)
    dots = amp @ khat
    denom = np.linalg.norm(amp, axis=1) * max(float(np.linalg.norm(khat)), 1e-30)
    rel = np.abs(dots) / np.maximum(denom, 1e-30)
    return {
        "k_dot_e0_abs_max": float(np.max(np.abs(dots))),
        "k_dot_e0_rel_max": float(np.max(rel)),
        "k_dot_e0_rel_mean": float(np.mean(rel)),
    }


def component_stats(array: np.ndarray) -> dict[str, dict[str, float]]:
    names = ["x", "y", "z"]
    out: dict[str, dict[str, float]] = {}
    for ci, name in enumerate(names):
        part = array[ci]
        abs_part = np.abs(part)
        out[name] = {
            "max": float(np.max(abs_part)),
            "rms": float(np.sqrt(np.mean(part ** 2))),
            "mean_abs": float(np.mean(abs_part)),
            "active_fraction_0p1": float(np.mean(abs_part >= 0.1)),
            "active_fraction_0p01": float(np.mean(abs_part >= 0.01)),
        }
    return out


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir)
    specs = read_json(run_dir / "sample_specs.json")
    config = read_json(run_dir / "summary.json").get("config") or read_json(run_dir / "manifest.json")["config"]
    shape = (int(config["grid"]),) * 3
    train_n = max(1, int(0.8 * int(config["samples"])))
    indices = list(range(train_n, int(config["samples"])))
    if args.limit:
        indices = indices[: int(args.limit)]
    error_rows = load_error_rows(Path(args.error_csv))

    rows: list[dict[str, Any]] = []
    for index in indices:
        spec = specs[index]
        field, curl = sample_from_spec(spec, shape)
        normalized, scales = component_local_max_normalize(torch.from_numpy(curl[None]))
        norm_np = normalized.numpy()[0]
        scale_np = scales.numpy()[0, :, 0, 0, 0]
        amp = np.asarray(spec["amplitudes"], dtype=np.float64)
        abs_cos = abs(float(math.cos(float(spec["theta"]))))
        xy_amp = max(float(np.max(np.abs(amp[:, :2]))), 1e-30)
        row: dict[str, Any] = {
            "sample_index": index,
            "theta": float(spec["theta"]),
            "phi": float(spec["phi"]),
            "abs_cos_theta": abs_cos,
            "theta_rejection_margin": abs_cos - float(spec.get("theta_rejection_abs_cos_min", args.theta_cos_min)),
            "max_abs_exey_amp": xy_amp,
            "max_abs_ez_amp": float(np.max(np.abs(amp[:, 2]))),
            "mean_abs_ez_amp": float(np.mean(np.abs(amp[:, 2]))),
            "max_abs_ez_over_xy": float(np.max(np.abs(amp[:, 2])) / xy_amp),
            "field_rms": float(np.sqrt(np.mean(field.astype(np.float64) ** 2))),
            "curl_rms": float(np.sqrt(np.mean(curl.astype(np.float64) ** 2))),
            **transversality(spec),
        }
        raw = component_stats(curl.astype(np.float64))
        normed = component_stats(norm_np.astype(np.float64))
        for name, ci in [("x", 0), ("y", 1), ("z", 2)]:
            row[f"{name}_scale"] = float(scale_np[ci])
            row[f"{name}_raw_rms"] = raw[name]["rms"]
            row[f"{name}_raw_mean_abs"] = raw[name]["mean_abs"]
            row[f"{name}_norm_rms"] = normed[name]["rms"]
            row[f"{name}_active_fraction_0p1"] = normed[name]["active_fraction_0p1"]
            row[f"{name}_active_fraction_0p01"] = normed[name]["active_fraction_0p01"]
        row["z_scale_over_xy_mean"] = float(row["z_scale"] / max((row["x_scale"] + row["y_scale"]) / 2.0, 1e-30))
        row.update(error_rows.get(index, {}))
        rows.append(row)

    correlations: dict[str, float | None] = {}
    if error_rows:
        for feature in [
            "abs_cos_theta",
            "theta_rejection_margin",
            "max_abs_ez_over_xy",
            "z_scale_over_xy_mean",
            "z_norm_rms",
            "z_active_fraction_0p1",
            "x_active_fraction_0p1",
            "y_active_fraction_0p1",
            "k_dot_e0_rel_max",
        ]:
            correlations[f"{feature}_vs_macro_nmae"] = safe_corr(
                [r[feature] for r in rows],
                [r.get("macro_nmae", float("nan")) for r in rows],
            )
            correlations[f"{feature}_vs_z_nmae"] = safe_corr(
                [r[feature] for r in rows],
                [r.get("z_nmae", float("nan")) for r in rows],
            )

    result = {
        "schema": "pidon-paper01-data-contract-audit-v1",
        "status": "PASS",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "parameter_updates": 0,
        "run_dir": str(run_dir),
        "error_csv": str(args.error_csv),
        "sample_count": len(rows),
        "transversality": {
            "k_dot_e0_abs_max": summarize([r["k_dot_e0_abs_max"] for r in rows]),
            "k_dot_e0_rel_max": summarize([r["k_dot_e0_rel_max"] for r in rows]),
        },
        "angle_bins": bins(rows, "abs_cos_theta", [0.15, 0.25, 0.5, 0.75, 1.0]),
        "ez_amplification": summarize([r["max_abs_ez_over_xy"] for r in rows]),
        "z_scale_over_xy_mean": summarize([r["z_scale_over_xy_mean"] for r in rows]),
        "active_fraction_0p1": {
            "x": summarize([r["x_active_fraction_0p1"] for r in rows]),
            "y": summarize([r["y_active_fraction_0p1"] for r in rows]),
            "z": summarize([r["z_active_fraction_0p1"] for r in rows]),
        },
        "correlations": correlations,
        "worst_z_samples": sorted(
            [r for r in rows if "z_nmae" in r],
            key=lambda r: float(r["z_nmae"]),
            reverse=True,
        )[:8],
        "rows": rows,
    }
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def make_plots(out: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    abs_cos = [r["abs_cos_theta"] for r in rows]
    z_err = [r.get("z_nmae", float("nan")) for r in rows]
    z_active = [r["z_active_fraction_0p1"] for r in rows]
    ez_ratio = [r["max_abs_ez_over_xy"] for r in rows]

    plt.figure(figsize=(7.0, 4.2))
    plt.scatter(abs_cos, z_err, s=16, alpha=0.7)
    plt.xlabel("|cos(theta)|")
    plt.ylabel("curl-z nMAE")
    plt.title("PAPER01-S1 z error vs Eq.(4) angle")
    plt.tight_layout()
    plt.savefig(out / "z_error_vs_angle.png", dpi=180)
    plt.close()

    plt.figure(figsize=(7.0, 4.2))
    plt.scatter(z_active, z_err, s=16, alpha=0.7)
    plt.xlabel("curl-z normalized active fraction >= 0.1")
    plt.ylabel("curl-z nMAE")
    plt.title("PAPER01-S1 z error vs target support")
    plt.tight_layout()
    plt.savefig(out / "z_error_vs_support.png", dpi=180)
    plt.close()

    plt.figure(figsize=(7.0, 4.2))
    plt.hist(ez_ratio, bins=30)
    plt.xlabel("max |Ez amplitude| / max |Ex,Ey amplitude|")
    plt.ylabel("held-out sample count")
    plt.title("Eq.(4) Ez amplitude amplification")
    plt.tight_layout()
    plt.savefig(out / "ez_amplification_hist.png", dpi=180)
    plt.close()


def report(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# PAPER01-S1 数据/公式合同审计",
        "",
        "- 状态：`PASS`；科学含义：`DIAGNOSTIC_ONLY`",
        "- 参数更新：`0`",
        f"- 样本数：`{result['sample_count']}`",
        "",
        "## 公式自洽性",
        "",
        f"- `k dot E0` 相对残差最大值的最大值：`{result['transversality']['k_dot_e0_rel_max']['max']}`",
        f"- Ez放大比 `max|Ez|/max|Ex,Ey|` 均值：`{result['ez_amplification']['mean']}`，p90：`{result['ez_amplification']['p90']}`，最大：`{result['ez_amplification']['max']}`",
        f"- z分量curl尺度 / xy平均尺度 均值：`{result['z_scale_over_xy_mean']['mean']}`",
        "",
        "## 归一化后目标支撑",
        "",
        "| 分量 | active>=0.1 mean | active>=0.1 p90 |",
        "|---|---:|---:|",
    ]
    for name in ["x", "y", "z"]:
        row = result["active_fraction_0p1"][name]
        lines.append(f"| curl-{name} | {row['mean']:.6g} | {row['p90']:.6g} |")
    lines += [
        "",
        "## 角度分组",
        "",
        "| |cos(theta)|区间 | count | macro nMAE mean | z nMAE mean | Ez放大比mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for group in result["angle_bins"]:
        lo, hi = group["range"]
        macro = group["macro_nmae"]["mean"]
        z = group["z_nmae"]["mean"]
        ez = group["max_abs_ez_ratio"]["mean"]
        lines.append(
            f"| {lo:.2f}-{hi:.2f} | {group['count']} | "
            f"{macro if macro is not None else 'N/A'} | {z if z is not None else 'N/A'} | "
            f"{ez if ez is not None else 'N/A'} |"
        )
    lines += [
        "",
        "## 判读",
        "",
        "- `k dot E0`若接近机器精度，说明Eq.(4)横向条件本身是自洽的；问题不应归咎于没有满足平面波横向性。",
        "- 若Ez放大比、z尺度比或z目标支撑与误差相关，优先诊断幅值构造、角度拒绝阈值和分量归一化，而不是直接原样重训。",
        "- 本审计不改变`PAPER01-S1`科学FAIL，不授权第二阶段或长程。",
        "",
        "## 图",
        "",
        "- `z_error_vs_angle.png`",
        "- `z_error_vs_support.png`",
        "- `ez_amplification_hist.png`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN))
    parser.add_argument("--error-csv", default=str(DEFAULT_ERROR_CSV))
    parser.add_argument("--out", required=True)
    parser.add_argument("--theta-cos-min", type=float, default=0.15)
    parser.add_argument("--limit", type=int, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = evaluate(args)
    write_csv(out / "per_sample_contract.csv", result.pop("rows"))
    write_json(out / "summary.json", result)
    rows = []
    with (out / "per_sample_contract.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    numeric_rows = [{k: (float(v) if v not in {"", "None"} and k != "sample_index" else v) for k, v in row.items()} for row in rows]
    make_plots(out, numeric_rows)
    report(out / "REPORT.md", result)
    print(json.dumps({
        "status": result["status"],
        "scientific_result": result["scientific_result"],
        "sample_count": result["sample_count"],
        "ez_amplification_p90": result["ez_amplification"]["p90"],
        "z_active_fraction_mean": result["active_fraction_0p1"]["z"]["mean"],
        "output": str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
