"""Auditable, no-training evaluation of the registered DCO initialization."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

import dco as D
import paper_protocol as PP
from pidon_recording import atomic_json_save, sha256_file


ROOT = PROJECT_ROOT
OUT = ROOT / "evidence" / "mechanism_decision_v1"


def draw_shared_direction(rng: np.random.Generator) -> np.ndarray:
    phi = rng.uniform(-np.pi, np.pi)
    while True:
        theta = rng.uniform(0.0, np.pi)
        if abs(np.cos(theta)) >= 0.15:
            break
    return np.array([np.cos(phi) * np.sin(theta), np.sin(phi) * np.sin(theta), np.cos(theta)])


def make_specs(seed: int, count: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    specs = []
    for sample_id in range(count):
        waves = int(rng.integers(4, 17))
        direction = draw_shared_direction(rng)
        k = rng.uniform(1.0, 1048.0, size=waves)
        amp = np.empty((waves, 3))
        amp[:, 0:2] = rng.uniform(0.0, 5.0, size=(waves, 2))
        amp[:, 2] = -(direction[0] * amp[:, 0] + direction[1] * amp[:, 1]) / direction[2]
        specs.append({"sample_id": sample_id, "n_waves": waves, "direction": direction.tolist(),
                      "k_rad_per_m": k.tolist(), "amplitude": amp.tolist(), "phase_rad": [0.0] * waves,
                      "theta_singularity_rejection_abs_cos_min": 0.15})
    return specs


def wave_numbers(spec: dict) -> list[float]:
    """Read the declared rad/m wave-number array from either registered schema."""
    values = spec.get("k_rad_per_m", spec.get("k"))
    if values is None:
        raise KeyError("wave specification needs k_rad_per_m or k")
    return values


def sample_spec(spec: dict, shape: tuple[int, int, int], extent_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample a continuous analytic field at declared E and curl locations.

    The convention is explicit: shape is a number of cells, d=extent/shape,
    coordinates span [0,(N-1)d].  It follows paper_protocol.py and is kept
    separate from the n=31 cavity interval reconstruction.
    """
    h = np.asarray([extent_m / n for n in shape], dtype=np.float64)
    xyz = np.meshgrid(*[np.arange(n, dtype=np.float64) * d for n, d in zip(shape, h)],
                      indexing="ij", sparse=True)
    e = np.zeros((3, *shape), dtype=np.float64)
    c = np.zeros_like(e)
    direction = np.asarray(spec["direction"], dtype=np.float64)
    # `make_specs` records units in the key.  The existing paper reconstruction
    # records the same rad/m values as `k`; accept both declared schemas.
    for k, amp, phase0 in zip(wave_numbers(spec), spec["amplitude"], spec["phase_rad"]):
        kv, amp = k * direction, np.asarray(amp, dtype=np.float64)
        phase = phase0 + sum(kv[q] * xyz[q] for q in range(3))
        cross = np.cross(kv, amp)
        for component in range(3):
            e_phase = phase + np.dot(kv * h, PP.E_OFFSETS[component])
            c_phase = phase + np.dot(kv * h, PP.H_OFFSETS[component])
            e[component] += amp[component] * np.cos(e_phase)
            c[component] -= cross[component] * np.sin(c_phase)
    return e, c, h


def predict(net: D.DCO, e: np.ndarray, h_m: np.ndarray, device: str) -> tuple[np.ndarray, np.ndarray]:
    dtype = torch.float32
    e_t = torch.as_tensor(e[None], dtype=dtype, device=device)
    d_mm = torch.as_tensor((h_m * 1e3)[None], dtype=dtype, device=device)
    coords = D.make_coords(e.shape[1:], d_mm[0], "cellsize", device=device, dtype=dtype)
    eh, _, scale, lc = D.normalise(e_t, None, d_mm, "rms")
    h_t = torch.as_tensor(h_m[None], dtype=dtype, device=device)
    with torch.no_grad():
        pred = D.denormalise(net(eh, coords, D.d_rel_of(d_mm, lc)), scale, lc)[0]
        yee = D.curl_periodic(e_t, h_t)[0]
    return pred.detach().cpu().double().numpy(), yee.detach().cpu().double().numpy()


def interior_metrics(pred: np.ndarray, analytic: np.ndarray) -> dict:
    # The periodic helper is an exact forward Yee stencil only away from its
    # wrapped high faces.  A common (N-1)^3 support avoids confusing its
    # artificial periodic closure with the analytic free-space field.
    return PP.vector_metrics(pred[:, :-1, :-1, :-1], analytic[:, :-1, :-1, :-1])


def evaluate_net(net: D.DCO, specs: list[dict], groups: list[tuple[str, tuple[int, int, int]]],
                 device: str) -> list[dict]:
    rows = []
    for label, shape in groups:
        for spec in specs:
            e, c, h = sample_spec(spec, shape, 19.2e-3)
            pred, yee = predict(net, e, h, device)
            rows.append({"group": label, "shape": list(shape), "sample_id": spec["sample_id"],
                         "d_m": h.tolist(), "max_k_rad_per_m": max(wave_numbers(spec)),
                         "dco": interior_metrics(pred, c), "yee_discrete": interior_metrics(yee, c)})
            if device == "cuda":
                torch.cuda.empty_cache()
    return rows


def _subset_spec(spec: dict, indices: list[int]) -> dict:
    """A spec holding only the listed plane waves, keeping their own phases."""
    out = dict(spec)
    out["k_rad_per_m"] = [spec["k_rad_per_m"][i] for i in indices]
    out["amplitude"] = [spec["amplitude"][i] for i in indices]
    if "phase_rad" in spec:
        out["phase_rad"] = [spec["phase_rad"][i] for i in indices]
    return out


def diagnostics(net: D.DCO, spec: dict, device: str) -> dict:
    """Additivity and homogeneity controls.

    E01: the superposition test used to compare ``D(e)`` -- the network on ALL
    of the sampled waves -- against ``D(e1) + D(e2)``, the network on the first
    TWO waves only.  A generator that draws 4 to 16 waves therefore charged
    every wave it left out to "nonlinearity": a strictly linear identity
    operator scores 0.829798 on that comparison and 0 on the real one.  The
    same-input test below splits the SAME wave set into two halves whose sum
    is the full input, and the historical partial-sum quantity is kept under a
    name that says what it was.
    """
    shape = (32, 32, 32)
    e, _, h = sample_spec(spec, shape, 19.2e-3)
    p, _ = predict(net, e, h, device)
    p2, _ = predict(net, 2.0 * e, h, device)
    zero, _ = predict(net, np.zeros_like(e), h, device)

    count = len(spec["k_rad_per_m"])
    half = max(1, count // 2)
    spec_a = _subset_spec(spec, list(range(half)))
    spec_b = _subset_spec(spec, list(range(half, count)))
    e_a, _, _ = sample_spec(spec_a, shape, 19.2e-3)
    e_b, _, _ = sample_spec(spec_b, shape, 19.2e-3)
    # The split must reconstruct the original input exactly, otherwise the
    # additivity number is measuring the split and not the operator.
    split_residual = float(np.max(np.abs(e_a + e_b - e)))
    p_a, _ = predict(net, e_a, h, device)
    p_b, _ = predict(net, e_b, h, device)
    additivity = float(np.linalg.norm((p - p_a - p_b).ravel()) /
                       max(np.linalg.norm(p.ravel()), 1e-30))

    # The historical (incorrect) comparison, reproduced so old and new numbers
    # can be lined up.  It is NOT a nonlinearity measurement.
    first = _subset_spec(spec, [0])
    second = _subset_spec(spec, [1]) if count > 1 else _subset_spec(spec, [0])
    e1, _, _ = sample_spec(first, shape, 19.2e-3)
    e2, _, _ = sample_spec(second, shape, 19.2e-3)
    p1, _ = predict(net, e1, h, device)
    p_2, _ = predict(net, e2, h, device)
    legacy = float(np.linalg.norm((p - p1 - p_2).ravel()) / max(np.linalg.norm(p.ravel()), 1e-30))
    return {
        "zero_output_max_abs": float(np.max(np.abs(zero))),
        "positive_amplitude_homogeneity_max_abs": float(np.max(np.abs(p2 - 2.0 * p))),
        "superposition_defect_relative_l2": additivity,
        "superposition_wave_count": count,
        "superposition_split": [half, count - half],
        "superposition_split_input_residual_max_abs": split_residual,
        "legacy_partial_sum_defect_relative_l2": legacy,
        "legacy_partial_sum_note": (
            "E01：旧字段把全部波的输出与前两束波输出之和比较，漏掉的波会被计入"
            "“非线性”；严格线性算子也会得到较大值。它不是非线性度量，只保留作对照。"),
        "note": "幅值齐次性受输入RMS归一化和可逆反归一化强烈约束，只作控制，不计泛化成绩。",
    }


def summarize(rows: list[dict]) -> dict:
    out = {}
    for key in sorted({row["group"] for row in rows}):
        dco = [row["dco"] for row in rows if row["group"] == key]
        yee = [row["yee_discrete"] for row in rows if row["group"] == key]
        nmae = [x["macro_nmae"] for x in dco]
        rel = [x["global_rel_l2"] for x in dco]
        out[key] = {
            "samples": len(dco), "dco_macro_nmae_max": float(max(nmae)),
            "dco_global_rel_l2_p90": float(np.quantile(rel, .9)),
            "yee_macro_nmae_median": float(np.median([x["macro_nmae"] for x in yee])),
            "S1_pass_for_cube_only": bool(key == "cube32" and max(nmae) <= .01 and np.quantile(rel, .9) <= .05),
        }
    return out


def plot(rows: list[dict], destination: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
    for group in sorted({r["group"] for r in rows}):
        group_rows = [r for r in rows if r["group"] == group]
        ax.scatter([r["max_k_rad_per_m"] for r in group_rows],
                   [r["dco"]["macro_nmae"] for r in group_rows], label=f"DCO {group}", s=20)
    ax.set_yscale("log"); ax.set_xlabel("sample max k (rad/m)"); ax.set_ylabel("macro nMAE (separate from MRE)")
    ax.grid(True, which="both", alpha=.25); ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(destination); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    protocol_path = OUT / "protocol.json"
    if not protocol_path.is_file():
        raise FileNotFoundError("run mechanism_decision_init.py first")
    if (OUT / "phase1_raw.json").exists():
        raise FileExistsError("phase1 evidence already exists; refusing to overwrite")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if sha256_file(ROOT / "dco_lr1e3_300.pt") != protocol["master"]["sha256"]:
        raise RuntimeError("registered master checkpoint hash differs")
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto": device = "cpu"
    master_ck = torch.load(ROOT / "dco_lr1e3_300.pt", map_location=device, weights_only=False)
    master = D.DCO(levels=master_ck["levels"], base=master_ck["base"], head=master_ck.get("head", "direct")).to(device).eval()
    master.load_state_dict(master_ck["state"])
    torch.manual_seed(20260914)
    random_net = D.DCO(levels=master_ck["levels"], base=master_ck["base"], head=master_ck.get("head", "direct")).to(device).eval()
    specs = make_specs(20260914, 16)
    groups = [("cube32", (32, 32, 32)), ("cube64", (64, 64, 64)),
              ("rect64x96x16", (64, 96, 16)), ("rect32x64x16", (32, 64, 16))]
    master_rows = evaluate_net(master, specs, groups, device)
    random_rows = evaluate_net(random_net, specs, [("cube32", (32, 32, 32))], device)
    fig_spec = PP.wave_spec(20260914)
    paper_rows = evaluate_net(master, [dict(fig_spec, sample_id="paper_fixed")], groups, device)
    result = {
        "schema": "pidon-mechanism-phase1-v1", "protocol_sha256": sha256_file(protocol_path),
        "device": device, "sampling": {"extent_m": .0192, "cell_count_convention": "d=extent/N; coordinates i*d"},
        "specs": specs, "master_rows": master_rows, "random_rows": random_rows, "paper_fixed_rows": paper_rows,
        "master_summary": summarize(master_rows), "random_summary": summarize(random_rows),
        "master_diagnostics": diagnostics(master, specs[0], device),
        "status": {"S1_cube": "PASS" if summarize(master_rows)["cube32"]["S1_pass_for_cube_only"] else "FAIL",
                   "S1_migration": "REPORTED_SEPARATELY", "dco_score_excludes_yee": True},
    }
    atomic_json_save(result, OUT / "phase1_raw.json")
    (OUT / "wave_specs.json").write_text(json.dumps(specs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot(master_rows, OUT / "phase1_macro_nmae.png")
    print(json.dumps({"S1_cube": result["status"]["S1_cube"], "master_summary": result["master_summary"],
                      "diagnostics": result["master_diagnostics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
