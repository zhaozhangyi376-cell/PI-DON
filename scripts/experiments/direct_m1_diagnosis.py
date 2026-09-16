"""M1 fixed-state diagnosis for the direct mechanism queue.

This script is intentionally diagnostic-only.  It loads historical terminal
states with ``diagnostic_only=True``, recomputes the registered E-fit residuals,
solves a one-shot float64 output-head projection on frozen features, and checks
two deterministic head-gradient directions.  It never writes parameters back to
any production checkpoint.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

from project_paths import PROJECT_DIR, configure, resolve_legacy
configure()

import dco as D
import head_lstsq
import pidon_solve as S


ROOT = PROJECT_DIR
DEFAULT_OUT = ROOT / "evidence" / "direct_mechanism_v1" / "m1"
THRESHOLD = 1e-4


CASES = [
    {
        "case_id": "P_first_nonzero_E",
        "run_dir": ROOT / "evidence" / "mechanism_decision_v1" / "runs" / "P",
        "raw": ROOT / "evidence" / "mechanism_decision_v1" / "runs" / "P" / "failure_raw_000001_attempt_1.pt",
        "row_index": 0,
        "description": "pretrained P arm first nonzero E target",
    },
    {
        "case_id": "S_R_step34_E",
        "run_dir": ROOT / "evidence" / "mechanism_1h_v2" / "runs" / "S_R",
        "raw": ROOT / "evidence" / "mechanism_1h_v2" / "runs" / "S_R" / "failure_raw_000034_attempt_1.pt",
        "row_index": 33,
        "description": "random S-R arm 34th candidate E target after accepted H half-step",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        if not value.is_absolute():
            return value.as_posix()
        try:
            return value.relative_to(ROOT).as_posix()
        except ValueError:
            return str(value)
    if isinstance(value, torch.Tensor):
        if value.numel() == 1:
            return float(value.detach().cpu())
        return value.detach().cpu().tolist()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return str(value)
    return value


def args_from_metadata(run_dir: Path, device: str) -> argparse.Namespace:
    meta = read_json(run_dir / "run_metadata.json")
    cfg = copy.deepcopy(meta["config"])
    cfg["device"] = device
    if "out_dir" in cfg:
        cfg["out_dir"] = str(resolve_legacy(cfg["out_dir"]))
    if "out" in cfg:
        cfg["out"] = str(resolve_legacy(cfg["out"]))
    return argparse.Namespace(**cfg)


def load_solver(case: dict[str, Any], device: str) -> tuple[S.Solver, dict[str, Any]]:
    solver = S.Solver(args_from_metadata(case["run_dir"], device), device)
    payload = torch.load(case["raw"], map_location="cpu", weights_only=False)
    solver.load_state_payload(payload, diagnostic_only=True)
    return solver, payload


def feature_and_targets(solver: S.Solver, which: str) -> dict[str, Any]:
    field = solver.E if which == "E" else solver.H
    targets = solver.yee_curl_E() if which == "E" else solver.yee_curl_H()
    n = solver.n
    physical_tgt = [
        t[:min(t.shape[0], n), :min(t.shape[1], n), :min(t.shape[2], n)].detach()
        for t in targets
    ]
    core = solver.extract_input_core(field, which)
    h_scale = float(getattr(solver.a, "h_scale", 1.0)) if which == "H" else 1.0
    out_scale = float(getattr(solver.a, "h_output_scale", 1.0)) if which == "H" else 1.0
    if h_scale != 1.0:
        core = core * h_scale

    net = solver.net_H if which == "H" else solver.net_E
    captured: list[torch.Tensor] = []

    def capture(_module, inputs):
        captured.append(inputs[0].detach())

    hook = net.head.register_forward_pre_hook(capture)
    try:
        with torch.no_grad():
            out = solver.predict(core, which)
    finally:
        hook.remove()
    if len(captured) != 1:
        raise RuntimeError("head feature capture failed")
    pred_train = [
        out[k, :min(t.shape[0], n), :min(t.shape[1], n), :min(t.shape[2], n)]
        for k, t in enumerate(targets)
    ]
    pred_physical = [p.detach() / (h_scale * out_scale) for p in pred_train]
    context = solver.last_predict_context
    scale = context["input_scale"].reshape(-1)[0].detach()
    lc = context["Lc"].reshape(-1)[0].detach()
    train_tgt = [t * h_scale * out_scale for t in physical_tgt]
    normalized_tgt = [t * lc / (scale * out_scale) for t in train_tgt]
    return {
        "core": core,
        "feature": captured[0][0].detach(),
        "physical_target": physical_tgt,
        "train_target": train_tgt,
        "normalized_target": normalized_tgt,
        "prediction_physical": pred_physical,
        "scale": scale,
        "lc": lc,
        "h_scale": h_scale,
        "out_scale": out_scale,
    }


def ratio(pred: list[torch.Tensor], target: list[torch.Tensor]) -> dict[str, Any]:
    sse = sum((p.detach().double().cpu() - t.detach().double().cpu()).square().sum() for p, t in zip(pred, target))
    target_ss = sum(t.detach().double().cpu().square().sum() for t in target)
    count = sum(t.numel() for t in target)
    max_abs = max(float((p.detach().cpu() - t.detach().cpu()).abs().max()) for p, t in zip(pred, target))
    return {
        "sse": float(sse),
        "target_ss": float(target_ss),
        "target_count": int(count),
        "residual_ratio": float(sse / target_ss) if float(target_ss) > 0.0 else None,
        "mse": float(sse / max(count, 1)),
        "max_abs": max_abs,
        "passed_R_lt_1e_minus_4": bool(float(sse / target_ss) < THRESHOLD) if float(target_ss) > 0.0 else False,
    }


def head_projection(bundle: dict[str, Any]) -> dict[str, Any]:
    feature = bundle["feature"]
    weight, bias, diagnostics = head_lstsq.solve_head(feature, bundle["normalized_target"])
    physical_pred = []
    for k, target in enumerate(bundle["physical_target"]):
        f = feature[:, :target.shape[0], :target.shape[1], :target.shape[2]].to(dtype=torch.float64, device="cpu")
        w = weight[k, :, 0, 0, 0].to(dtype=torch.float64, device="cpu")
        b = bias[k].to(dtype=torch.float64, device="cpu")
        normalized = (f * w[:, None, None, None]).sum(dim=0) + b
        train_units = normalized * bundle["scale"].detach().cpu().double() * bundle["out_scale"] / bundle["lc"].detach().cpu().double()
        physical_pred.append(train_units / (bundle["h_scale"] * bundle["out_scale"]))
    best = ratio(physical_pred, bundle["physical_target"])
    return {
        "best_physical": best,
        "feature_shape": list(feature.shape),
        "diagnostics": [
            {
                "rank": d["rank"],
                "samples": d["samples"],
                "columns": d["columns"],
                "rcond": d["rcond"],
                "normalized_sse": d["normalized_sse"],
                "singular_min": min(d["singular_values"]) if d["singular_values"] else None,
                "singular_max": max(d["singular_values"]) if d["singular_values"] else None,
            }
            for d in diagnostics
        ],
    }


def differentiable_loss(solver: S.Solver, bundle: dict[str, Any], which: str) -> torch.Tensor:
    out = solver.predict(bundle["core"], which)
    target = bundle["physical_target"]
    pred = [
        out[k, :target[k].shape[0], :target[k].shape[1], :target[k].shape[2]] / (bundle["h_scale"] * bundle["out_scale"])
        for k in range(3)
    ]
    sse = sum((p - t).square().sum() for p, t in zip(pred, target))
    den = sum(t.square().sum() for t in target).clamp_min(1e-30)
    return sse / den


def head_gradient_check(solver: S.Solver, bundle: dict[str, Any], which: str, *, seed: int) -> dict[str, Any]:
    net = solver.net_H if which == "H" else solver.net_E
    net.zero_grad(set_to_none=True)
    loss = differentiable_loss(solver, bundle, which)
    loss.backward()
    grad_w = net.head.weight.grad.detach().clone()
    grad_b = net.head.bias.grad.detach().clone()
    grad_norm = float(torch.sqrt(grad_w.square().sum() + grad_b.square().sum()).detach().cpu())
    base_w = net.head.weight.detach().clone()
    base_b = net.head.bias.detach().clone()
    generator = torch.Generator(device="cpu").manual_seed(seed)
    checks = []
    for direction_index in range(2):
        dw = torch.randn(base_w.shape, generator=generator, dtype=torch.float32).to(base_w.device, base_w.dtype)
        db = torch.randn(base_b.shape, generator=generator, dtype=torch.float32).to(base_b.device, base_b.dtype)
        norm = torch.sqrt(dw.square().sum() + db.square().sum()).clamp_min(1e-30)
        dw, db = dw / norm, db / norm
        analytic = float((grad_w * dw).sum().detach().cpu() + (grad_b * db).sum().detach().cpu())
        eps = 1e-3
        with torch.no_grad():
            net.head.weight.copy_(base_w + eps * dw)
            net.head.bias.copy_(base_b + eps * db)
        plus = float(differentiable_loss(solver, bundle, which).detach().cpu())
        with torch.no_grad():
            net.head.weight.copy_(base_w - eps * dw)
            net.head.bias.copy_(base_b - eps * db)
        minus = float(differentiable_loss(solver, bundle, which).detach().cpu())
        with torch.no_grad():
            net.head.weight.copy_(base_w)
            net.head.bias.copy_(base_b)
        finite_diff = (plus - minus) / (2.0 * eps)
        checks.append({
            "direction_index": direction_index,
            "eps": eps,
            "analytic_directional_derivative": analytic,
            "finite_difference": finite_diff,
            "absolute_error": abs(analytic - finite_diff),
            "relative_error": abs(analytic - finite_diff) / max(abs(finite_diff), abs(analytic), 1e-30),
        })
    net.zero_grad(set_to_none=True)
    return {"loss": float(loss.detach().cpu()), "head_grad_norm": grad_norm, "directions": checks}


def diagnose_case(case: dict[str, Any], device: str) -> dict[str, Any]:
    solver, payload = load_solver(case, device)
    rows = read_jsonl(case["run_dir"] / "steps.jsonl")
    row = rows[case["row_index"]]
    e_bundle = feature_and_targets(solver, "E")
    current = ratio(e_bundle["prediction_physical"], e_bundle["physical_target"])
    projection = head_projection(e_bundle)
    gradient = head_gradient_check(solver, e_bundle, "E", seed=20260914 + int(case["row_index"]))
    h_bundle = feature_and_targets(solver, "H")
    h_current = ratio(h_bundle["prediction_physical"], h_bundle["physical_target"])
    recorded = row.get("fit_E") or {}
    trace = row.get("fit_traces", {}).get("E")
    result = {
        "case_id": case["case_id"],
        "description": case["description"],
        "source_raw": case["raw"],
        "source_raw_sha256": sha256(case["raw"]),
        "source_steps_sha256": sha256(case["run_dir"] / "steps.jsonl"),
        "payload_schema": payload.get("state_schema"),
        "checkpoint_schema": payload.get("checkpoint_schema"),
        "diagnostic_only": True,
        "accepted_steps": int(solver.accepted_steps),
        "current_time_layer": int(solver.current_time_layer),
        "phase": solver.phase,
        "recorded_fit_E": {
            "n_updates": recorded.get("n_updates"),
            "n_evals": recorded.get("n_evals"),
            "loss_initial": recorded.get("loss_initial"),
            "loss_final": recorded.get("loss_final"),
            "sse": recorded.get("sse"),
            "target_ss": recorded.get("target_ss"),
            "residual_ratio": recorded.get("residual_ratio"),
            "passed": recorded.get("passed"),
            "stop_reason": recorded.get("stop_reason"),
            "elapsed_s": recorded.get("elapsed_s"),
        },
        "readback_E": current,
        "head_projection_E": projection,
        "head_gradient_E": gradient,
        "readback_H_same_state": h_current,
        "trace_E": trace,
    }
    del solver
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def interpretation(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    for item in case_results:
        readback = item["readback_E"]["residual_ratio"]
        head_best = item["head_projection_E"]["best_physical"]["residual_ratio"]
        recorded = item["recorded_fit_E"]["residual_ratio"]
        if readback is not None and recorded is not None:
            notes.append({
                "case_id": item["case_id"],
                "readback_matches_recorded_within_5pct": abs(readback - recorded) / max(abs(recorded), 1e-30) <= 0.05,
            })
        support = "undetermined"
        if head_best is not None and head_best >= THRESHOLD:
            support = "frozen_features_head_projection_cannot_reach_strict_R"
        elif head_best is not None and readback is not None and head_best < THRESHOLD <= readback:
            support = "frozen_features_head_projection_can_reach_R_but_optimizer_did_not"
        elif head_best is not None and readback is not None and head_best < readback:
            support = "head_projection_improves_but_not_a_strict_pass"
        notes[-1]["primary_read"] = support
        notes[-1]["head_best_R"] = head_best
        notes[-1]["readback_R"] = readback
    return {
        "threshold": THRESHOLD,
        "case_interpretations": notes,
        "global_read": (
            "M1 is diagnostic only: a head projection pass would support changing optimizer rules; "
            "a head projection fail supports feature/state limitations for the frozen representation."
        ),
    }


def make_plot(case_results: list[dict[str, Any]], out_path: Path) -> None:
    labels = [r["case_id"] for r in case_results]
    recorded = [r["recorded_fit_E"]["residual_ratio"] or float("nan") for r in case_results]
    readback = [r["readback_E"]["residual_ratio"] or float("nan") for r in case_results]
    projected = [r["head_projection_E"]["best_physical"]["residual_ratio"] or float("nan") for r in case_results]
    x = list(range(len(labels)))
    width = 0.25
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar([v - width for v in x], recorded, width, label="recorded final R")
    ax.bar(x, readback, width, label="diagnostic readback R")
    ax.bar([v + width for v in x], projected, width, label="float64 head projection R")
    ax.axhline(THRESHOLD, color="black", linestyle="--", linewidth=1.2, label="strict gate 1e-4")
    ax.set_yscale("log")
    ax.set_ylabel("E-fit residual ratio R")
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.legend(fontsize=8)
    ax.set_title("M1 fixed-state E target diagnosis")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def write_report(audit: dict[str, Any], out_path: Path) -> None:
    lines = [
        "# M1 Report - Fixed Failure Target Diagnosis",
        "",
        "Status: PASS (diagnostic delivered). Scientific status: NOT_APPLICABLE.",
        "",
        "This report is diagnostic-only. It does not reclassify old FAIL rows and does not create a production checkpoint.",
        "",
        "## Cases",
        "",
    ]
    for item in audit["cases"]:
        interp = next(x for x in audit["interpretation"]["case_interpretations"] if x["case_id"] == item["case_id"])
        lines.extend([
            f"### {item['case_id']}",
            "",
            f"- Source: `{Path(item['source_raw']).as_posix()}`",
            f"- Phase / accepted steps: `{item['phase']}` / `{item['accepted_steps']}`",
            f"- Recorded E final R: `{item['recorded_fit_E']['residual_ratio']}`",
            f"- Readback E R: `{item['readback_E']['residual_ratio']}`",
            f"- Float64 head-projection best E R: `{item['head_projection_E']['best_physical']['residual_ratio']}`",
            f"- Head projection primary read: `{interp['primary_read']}`",
            f"- E updates / elapsed in old row: `{item['recorded_fit_E']['n_updates']}` / `{item['recorded_fit_E']['elapsed_s']}` s",
            f"- H same-state readback R: `{item['readback_H_same_state']['residual_ratio']}`",
            "",
        ])
    lines.extend([
        "## Outputs",
        "",
        f"- Audit JSON: `{Path(audit['audit_path']).as_posix()}`",
        f"- Diagnostic figure: `{Path(audit['figure_path']).as_posix()}`",
        "",
        "## Limits",
        "",
        "- A head-projection pass or fail only describes these frozen intermediate features.",
        "- M1 does not prove the whole network class can or cannot express the curl target.",
        "- No old failure, resource limit, or recovery status is reclassified here.",
        "",
    ])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--action-id", default="")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "m1_audit.json"
    report_path = out_dir / "M1_REPORT.md"
    figure_path = out_dir / "m1_diagnostic.png"
    if audit_path.exists():
        raise FileExistsError(audit_path)

    case_results = [diagnose_case(case, args.device) for case in CASES]
    audit = {
        "schema": "direct-mechanism-m1-diagnosis-v1",
        "action_id": args.action_id,
        "device": args.device,
        "optimizer_updates_this_script": 0,
        "lbfgs_closures_this_script": 0,
        "diagnostic_only": True,
        "threshold": THRESHOLD,
        "cases": case_results,
        "interpretation": interpretation(case_results),
        "audit_path": audit_path.relative_to(ROOT),
        "report_path": report_path.relative_to(ROOT),
        "figure_path": figure_path.relative_to(ROOT),
        "script_sha256": sha256(Path(__file__)),
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
    }
    make_plot(case_results, figure_path)
    audit_path.write_text(json.dumps(jsonable(audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(jsonable(audit), report_path)
    print(json.dumps({
        "status": "PASS",
        "scientific_status": "NOT_APPLICABLE",
        "cases": [
            {
                "case_id": item["case_id"],
                "recorded_R": item["recorded_fit_E"]["residual_ratio"],
                "readback_R": item["readback_E"]["residual_ratio"],
                "head_projection_R": item["head_projection_E"]["best_physical"]["residual_ratio"],
            }
            for item in audit["cases"]
        ],
        "audit": str(audit_path.relative_to(ROOT)),
        "report": str(report_path.relative_to(ROOT)),
        "figure": str(figure_path.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
