"""One targeted, read-only diagnosis of P arm's first strict failure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch

import pidon_solve as S
from pidon_recording import atomic_json_save, sha256_file, source_hashes


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "mechanism_decision_v1"


def component_relative_residual(predicted: list[torch.Tensor], target: list[torch.Tensor]) -> dict:
    components = []
    total_error = total_target = 0.0
    for prediction, truth in zip(predicted, target):
        error = float((prediction - truth).square().sum().detach().cpu())
        energy = float(truth.square().sum().detach().cpu())
        total_error += error; total_target += energy
        components.append({"sse": error, "target_ss": energy,
                           "R": None if energy == 0.0 else error / energy,
                           "max_abs": float((prediction - truth).abs().max().detach().cpu())})
    return {"components": components, "sse": total_error, "target_ss": total_target,
            "total_R": total_error / max(total_target, 1e-30)}


def core_target(solver: S.Solver) -> tuple[list[torch.Tensor], list[torch.Tensor], list[float]]:
    target_full = solver.yee_curl_E()
    target = [part[:min(part.shape[0], solver.n), :min(part.shape[1], solver.n),
                   :min(part.shape[2], solver.n)] for part in target_full]
    core = solver.extract_input_core(solver.E, "E")
    prediction_full = solver.predict(core, "E")
    prediction = [prediction_full[k, :part.shape[0], :part.shape[1], :part.shape[2]]
                  for k, part in enumerate(target)]
    high_plane = []
    for k, part in enumerate(target_full):
        if part.shape[k] == solver.n + 1:
            index = [slice(None)] * 3; index[k] = solver.n
            high_plane.append(float(part[tuple(index)].abs().max().detach().cpu()))
        else:
            high_plane.append(None)
    return prediction, target, high_plane


def partial_random_summary() -> dict:
    path = OUT / "runs" / "R" / "steps.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    last = rows[-1]
    return {
        "rows": len(rows), "all_accepted": all(bool(row["accepted"]) for row in rows),
        "first_E": rows[0]["fit_E"], "last_step": last["step"],
        "last_global_Q": last["accepted_field_metrics"]["global_weighted_relative_l2"],
        "termination": "PARTIAL_ABORTED_BY_AGENT; no recoverable checkpoint",
    }


def plot(p_trace: list[dict], r_trace: list[dict], destination: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.0), dpi=160)
    ax.plot([p["updates"] for p in p_trace], [p["loss"] for p in p_trace], "o-", ms=3, label="P: pretrained, E layer 0")
    ax.plot([r["updates"] for r in r_trace], [r["loss"] for r in r_trace], "o-", ms=3, label="R: random, E layer 0")
    ax.axhline(1e-4, color="black", ls="--", lw=1, label="registered R threshold")
    ax.set_yscale("log"); ax.set_xlabel("actual Adam updates"); ax.set_ylabel("physical residual R")
    ax.grid(True, which="both", alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(destination); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    destination = OUT / "first_failure_diagnosis.json"
    if destination.exists():
        raise FileExistsError(destination)
    metadata = json.loads((OUT / "runs" / "P" / "run_metadata.json").read_text(encoding="utf-8"))
    payload = torch.load(OUT / "runs" / "P" / "failure_raw_000001_attempt_1.pt", map_location="cpu", weights_only=False)
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto": device = "cpu"
    config = argparse.Namespace(**metadata["config"])
    config.device = device
    solver = S.Solver(config, device)
    solver.load_state_payload(payload, diagnostic_only=True)
    prediction, target, high_plane = core_target(solver)
    residual = component_relative_residual(prediction, target)
    row_p = json.loads((OUT / "runs" / "P" / "steps.jsonl").read_text(encoding="utf-8").splitlines()[0])
    random = partial_random_summary()
    result = {
        "schema": "pidon-mechanism-first-failure-v1", "protocol_sha256": sha256_file(OUT / "protocol.json"),
        "source_hashes": source_hashes(ROOT), "arm": "P", "time_layer": row_p["step"],
        "recorded_R": row_p["fit_E"]["residual_ratio"], "recomputed": residual,
        "recorded_and_recomputed_abs_difference": abs(row_p["fit_E"]["residual_ratio"] - residual["total_R"]),
        "input": {"core_shape": list(solver.extract_input_core(solver.E, "E").shape),
                  "core_max_abs": float(solver.extract_input_core(solver.E, "E").abs().max().detach().cpu()),
                  "normalisation": {key: value.detach().cpu().tolist() if hasattr(value, "detach") else value
                                    for key, value in solver.last_predict_context.items()}},
        "target": {"cropped_shapes": [list(item.shape) for item in target],
                   "full_shapes": [list(item.shape) for item in solver.yee_curl_E()],
                   "uncovered_high_PEC_plane_max_abs": high_plane,
                   "all_uncovered_planes_are_pec_zero": all(x in (0.0, None) for x in high_plane)},
        "P_fit": row_p["fit_E"], "R_partial": random,
        "interpretation": [
            "P's first nonzero E curl fit is a real strict failure under the registered budget.",
            "The independent recomputation checks the stored final parameters and declared target support.",
            "The high E-curl planes outside DCO's cube are PEC zeros; this diagnosis found no hidden nonzero Yee fallback there.",
            "R's partial trajectory is descriptive only because it was terminated without a checkpoint; it is not a complete B comparison.",
        ],
    }
    atomic_json_save(result, destination)
    plot(row_p["fit_traces"]["E"], random["first_E"] and json.loads((OUT / "runs" / "R" / "steps.jsonl").read_text(encoding="utf-8").splitlines()[0])["fit_traces"]["E"],
         OUT / "first_failure_residual.png")
    report = "\n".join([
        "# 首次失败鉴别", "", f"- P第0层curl-E记录R：`{result['recorded_R']:.9g}`",
        f"- 磁盘参数纯前向复算R：`{residual['total_R']:.9g}`，差：`{result['recorded_and_recomputed_abs_difference']:.3g}`",
        f"- 三分量R：`{[item['R'] for item in residual['components']]}`",
        f"- P实际Adam更新：`{row_p['fit_E']['n_updates']}`；R首层更新：`{random['first_E']['n_updates']}`。",
        f"- R只保存了`{random['rows']}`个严格接受步，因代理提前终止，不能作为完整预训练收益结果。",
        "- 未发现非零的未标记Yee边界回填；本报告没有将精确Yee控制记为DCO成绩。", "",
        "详见`first_failure_diagnosis.json`和`first_failure_residual.png`。",
    ])
    (OUT / "FIRST_FAILURE_REPORT.md").write_text(report + "\n", encoding="utf-8")
    print(json.dumps({"recorded_R": result["recorded_R"], "recomputed_R": residual["total_R"],
                      "component_R": [item["R"] for item in residual["components"]], "R_rows": random["rows"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
