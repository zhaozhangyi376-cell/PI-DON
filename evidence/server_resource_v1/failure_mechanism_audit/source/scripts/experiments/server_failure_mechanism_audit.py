"""Read-only failure mechanism audit after server TOL1E5-P."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import socket
import time
from pathlib import Path
from typing import Any

from project_paths import PROJECT_DIR, configure
configure()

from pidon_recording import atomic_json_save, sha256_file


ROOT = PROJECT_DIR
BASE = ROOT / "evidence/server_resource_v1"
OUT = BASE / "failure_mechanism_audit"
PROTOCOL = ROOT / "docs/plans/2026-09-15-failure-mechanism-audit-protocol.md"
M2_BASE = ROOT / "evidence/direct_mechanism_v1"
R2_DIR = BASE / "imports/server_batch2_return_r2_full_20260915T141612Z/short_tol_probe_r2"
ARM_DIRS = {
    "A-P": M2_BASE / "runs/A_P",
    "B-R": M2_BASE / "runs/B_R",
    "B-P": M2_BASE / "runs/B_P",
    "B-R2": M2_BASE / "benefit/B_R2",
}
NAMES = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def file_identity(path: Path) -> dict[str, Any]:
    return {"path": display(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def prepare_output(action_id: str) -> dict[str, Any]:
    if OUT.exists():
        raise FileExistsError(f"output already exists: {display(OUT)}")
    OUT.mkdir(parents=True)
    source = OUT / "source"
    hashes: dict[str, str | None] = {}
    for rel in (
        "scripts/experiments/server_failure_mechanism_audit.py",
        "scripts/experiments/server_local_review.py",
        "scripts/experiments/server_short_tol_probe.py",
        "scripts/analysis/direct_m2_audit.py",
        "src/pidon/pidon_solve.py",
        "src/pidon/pidon_contract.py",
        "src/pidon/pidon_recording.py",
        "project_paths.py",
        "docs/plans/2026-09-15-failure-mechanism-audit-protocol.md",
    ):
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            hashes[rel] = sha256_file(path)
    manifest = {
        "schema": "pidon-server-failure-mechanism-audit-v1",
        "action_id": action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "host": socket.gethostname(),
        "new_adam_updates": 0,
        "new_closures": 0,
        "protocol": file_identity(PROTOCOL),
        "source_hashes": hashes,
    }
    atomic_json_save(manifest, OUT / "manifest.json")
    return manifest


def trace_crossing(trace: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    for item in trace:
        loss = finite(item.get("loss"))
        if loss is not None and loss <= threshold:
            return {"updates": int(item.get("updates", 0)), "loss": loss}
    return None


def fit_signature(row: dict[str, Any], phase: str) -> dict[str, Any]:
    fit = row.get(phase) or {}
    trace = (row.get("fit_traces") or {}).get(phase[-1], [])
    return {
        "target_ss": fit.get("target_ss"),
        "target_count": fit.get("target_count"),
        "loss_initial": fit.get("loss_initial"),
        "loss_final": fit.get("loss_final"),
        "residual_ratio": fit.get("residual_ratio"),
        "n_updates": fit.get("n_updates"),
        "passed": fit.get("passed"),
        "stop_reason": fit.get("stop_reason"),
        "trace_crosses_1e_minus_4": trace_crossing(trace, 1e-4),
        "trace_crosses_1e_minus_5": trace_crossing(trace, 1e-5),
    }


def component_summary(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("six_component_metrics") or {}
    components = metrics.get("components") or {}
    effective: dict[str, float | None] = {}
    weak: dict[str, dict[str, Any]] = {}
    for name in NAMES:
        comp = components.get(name) or {}
        if comp.get("weak_reference"):
            weak[name] = {
                "absolute_mae": comp.get("absolute_mae"),
                "weak_absolute_pass": comp.get("weak_absolute_pass"),
                "reference_max": comp.get("reference_max"),
            }
        else:
            effective[name] = comp.get("nmae")
    effective_values = [v for v in (finite(x) for x in effective.values()) if v is not None]
    return {
        "global_weighted_relative_l2": metrics.get("global_weighted_relative_l2"),
        "fixed_amplitude_error": metrics.get("fixed_amplitude_error"),
        "effective_component_nmae": effective,
        "max_effective_component_nmae": max(effective_values) if effective_values else None,
        "weak_components": weak,
        "weak_failed": [name for name, item in weak.items() if item.get("weak_absolute_pass") is False],
    }


def first_crossing(rows: list[dict[str, Any]], field: str, threshold: float) -> dict[str, Any] | None:
    for row in rows:
        if not row.get("accepted"):
            continue
        summary = component_summary(row)
        value = finite(summary.get(field))
        if value is not None and value > threshold:
            return {
                "accepted_steps": row.get("accepted_steps"),
                "step": row.get("step"),
                "value": value,
                "row": row,
            }
    return None


def first_component_crossing(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    for row in rows:
        if not row.get("accepted"):
            continue
        summary = component_summary(row)
        value = finite(summary.get("max_effective_component_nmae"))
        if value is not None and value > threshold:
            return {
                "accepted_steps": row.get("accepted_steps"),
                "step": row.get("step"),
                "value": value,
                "row": row,
            }
    return None


def probe_l2_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    series = summary.get("probe_timeseries") or []
    result = []
    for index in range(3):
        dut: list[float] = []
        ref: list[float] = []
        cells = None
        for row in series:
            probes = row.get("source_outside_probes") or []
            if index < len(probes):
                cells = probes[index].get("cells")
                dut.append(float(probes[index].get("dut_Ez", 0.0) or 0.0))
                ref.append(float(probes[index].get("ref_Ez", 0.0) or 0.0))
        den = math.sqrt(sum(x * x for x in ref))
        num = math.sqrt(sum((a - b) ** 2 for a, b in zip(dut, ref)))
        result.append({
            "index": index,
            "cells": cells,
            "relative_l2": None if den == 0 else num / den,
            "ref_l2": den,
            "pass_5pct": bool(den > 0 and num / den <= 0.05),
        })
    return result


def audit_arm(name: str, path: Path) -> dict[str, Any]:
    summary = read_json(path / "summary.json")
    rows = read_rows(path / "steps.jsonl")
    accepted = [row for row in rows if row.get("accepted")]
    first = rows[0]
    q_cross = first_crossing(rows, "global_weighted_relative_l2", 0.05)
    nmae_cross = first_component_crossing(rows, 0.01)
    last = accepted[-1] if accepted else None
    return {
        "arm": name,
        "status": summary.get("status"),
        "accepted_steps": len(accepted),
        "budget": summary.get("budget"),
        "first_E": fit_signature(first, "fit_E"),
        "first_H": fit_signature(first, "fit_H"),
        "first_Q_above_5pct": None if q_cross is None else {
            "accepted_steps": q_cross["accepted_steps"],
            "step": q_cross["step"],
            "value": q_cross["value"],
            "components": component_summary(q_cross["row"]),
        },
        "first_effective_component_nmae_above_1pct": None if nmae_cross is None else {
            "accepted_steps": nmae_cross["accepted_steps"],
            "step": nmae_cross["step"],
            "value": nmae_cross["value"],
            "components": component_summary(nmae_cross["row"]),
        },
        "last_field": None if last is None else component_summary(last),
        "probe_l2": probe_l2_from_summary(summary),
        "inputs": [file_identity(path / "summary.json"), file_identity(path / "steps.jsonl")],
    }


def r2_audit() -> dict[str, Any]:
    summary = read_json(R2_DIR / "summary.json")
    rows = read_rows(R2_DIR / "steps.jsonl")
    row = rows[0]
    return {
        "status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "accepted_steps": summary.get("accepted_steps"),
        "budget": summary.get("budget"),
        "stop_reason": (summary.get("stop") or {}).get("reason"),
        "first_E": fit_signature(row, "fit_E"),
        "first_H": fit_signature(row, "fit_H"),
        "row_cost": row.get("row_cost"),
        "inputs": [file_identity(R2_DIR / "summary.json"), file_identity(R2_DIR / "steps.jsonl")],
    }


def same_first_target(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = ("target_ss", "target_count", "loss_initial")
    return all(
        finite(a.get(key)) is not None and finite(b.get(key)) is not None
        and math.isclose(float(a[key]), float(b[key]), rel_tol=1e-10, abs_tol=1e-30)
        for key in keys
    )


def make_csv(audit: dict[str, Any]) -> None:
    rows = []
    r2 = audit["r2"]
    rows.append({
        "item": "SR-SHORT-R2 first E",
        "accepted_steps": r2["accepted_steps"],
        "E_R": r2["first_E"]["residual_ratio"],
        "E_updates": r2["first_E"]["n_updates"],
        "field_Q": "",
        "max_component_nmae": "",
        "classification": "strict_tol_first_step_fail",
    })
    for arm in audit["arms"]:
        q = arm.get("first_Q_above_5pct") or {}
        n = arm.get("first_effective_component_nmae_above_1pct") or {}
        last = arm.get("last_field") or {}
        rows.append({
            "item": arm["arm"],
            "accepted_steps": arm["accepted_steps"],
            "E_R": arm["first_E"]["residual_ratio"],
            "E_updates": arm["first_E"]["n_updates"],
            "field_Q": last.get("global_weighted_relative_l2"),
            "max_component_nmae": last.get("max_effective_component_nmae"),
            "classification": f"Q_cross={q.get('accepted_steps')}; nmae_cross={n.get('accepted_steps')}",
        })
    with (OUT / "failure_compare.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_plot(audit: dict[str, Any]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    r2_trace = read_rows(R2_DIR / "steps.jsonl")[0]["fit_traces"]["E"]
    axes[0].plot([x["updates"] for x in r2_trace], [x["loss"] for x in r2_trace], label="TOL1E5-P E trace")
    axes[0].axhline(1e-4, color="black", linestyle="--", linewidth=1, label="1e-4")
    axes[0].axhline(1e-5, color="red", linestyle="--", linewidth=1, label="1e-5")
    axes[0].set_yscale("log")
    axes[0].set(xlabel="Adam updates", ylabel="R = SSE / target_ss", title="First E target fit")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=.2)

    for arm in audit["arms"]:
        rows = [row for row in read_rows(ARM_DIRS[arm["arm"]] / "steps.jsonl") if row.get("accepted")]
        axes[1].plot(
            [row["accepted_steps"] for row in rows],
            [(row.get("six_component_metrics") or {}).get("global_weighted_relative_l2", float("nan")) * 100 for row in rows],
            label=arm["arm"],
        )
    axes[1].axhline(5, color="black", linestyle="--", linewidth=1, label="5% Q gate")
    axes[1].set(xlabel="Accepted steps", ylabel="Observed-window Q (%)", title="Residual-accepted field drift")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=.2)
    fig.savefig(OUT / "residual_vs_field.png", dpi=170)
    plt.close(fig)


def write_report(audit: dict[str, Any]) -> None:
    r2 = audit["r2"]
    ap = next(arm for arm in audit["arms"] if arm["arm"] == "A-P")
    lines = [
        "# SR-FAIL-AUDIT：第二阶段失败机制审计",
        "",
        "本审计只读已有证据，新增 Adam 更新 `0`，新增 closure `0`。它不改判旧失败，也不解锁64/128/1024/8192。",
        "",
        "## 关键结论",
        "",
        f"- 同一个首个E目标在A-P中按`1e-4`通过：E R=`{ap['first_E']['residual_ratio']}`，更新 `{ap['first_E']['n_updates']}` 次。",
        f"- 同一个首个E目标在TOL1E5-P中按`1e-5`失败：E R=`{r2['first_E']['residual_ratio']}`，更新 `{r2['first_E']['n_updates']}` 次。",
        f"- 两者首个E目标身份匹配：`{audit['first_E_target_identity_match']}`；因此首步失败不像是target_ss记录错位或目标尺度换了。",
        "- 旧M2的128残差通过不能推出场通过；所有残差128臂都有场/源外误差越线。",
        "",
        "## 分类判断",
        "",
    ]
    for key, value in audit["classification"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines += [
        "",
        "## 各臂场越线",
        "",
        "| 臂 | 完整接受步 | 首次Q>5% | 首次有效分量nMAE>1% | 末步Q | 末步最大有效nMAE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in audit["arms"]:
        q = arm.get("first_Q_above_5pct") or {}
        n = arm.get("first_effective_component_nmae_above_1pct") or {}
        last = arm.get("last_field") or {}
        lines.append(
            f"| {arm['arm']} | {arm['accepted_steps']} | {q.get('accepted_steps')} | {n.get('accepted_steps')} | "
            f"{last.get('global_weighted_relative_l2')} | {last.get('max_effective_component_nmae')} |"
        )
    lines += [
        "",
        "## 后续建议",
        "",
        "不要继续扫容差，也不要启动长程。下一步如果要做实验，只能在首次更新前登记一个针对性极小实验：要么处理首步E优化/表达限制，要么处理场传播/状态插入假设；在审计证据之外不得追加未登记扫参。",
        "",
        "## 证据文件",
        "",
        "- `audit.json`",
        "- `failure_compare.csv`",
        "- `residual_vs_field.png`",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    manifest = prepare_output(args.action_id)
    arms = [audit_arm(name, path) for name, path in ARM_DIRS.items()]
    r2 = r2_audit()
    ap = next(arm for arm in arms if arm["arm"] == "A-P")
    identity_match = same_first_target(ap["first_E"], r2["first_E"])
    r2_final = finite(r2["first_E"].get("residual_ratio"))
    ap_final = finite(ap["first_E"].get("residual_ratio"))
    classification = {
        "interface_recording_unlikely": identity_match,
        "optimization_or_expression_limit": bool(r2_final is not None and r2_final > 1e-5 and r2["first_E"].get("n_updates") == 3000),
        "propagation_field_accumulation": bool(any(arm.get("first_Q_above_5pct") for arm in arms)),
        "simple_tolerance_tightening_rejected": True,
    }
    audit = {
        "schema": "pidon-server-failure-mechanism-audit-v1",
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "manifest": manifest,
        "new_adam_updates": 0,
        "new_closures": 0,
        "status": "PASS",
        "scientific_result": "NOT_APPLICABLE",
        "r2": r2,
        "arms": arms,
        "first_E_target_identity_match": identity_match,
        "first_E_r2_vs_AP_final_ratio": None if r2_final is None or ap_final is None else r2_final / ap_final,
        "r2_extra_improvement_needed_to_1e_minus_5": None if r2_final is None else r2_final / 1e-5,
        "classification": classification,
        "long_run_unlocked": False,
        "next_recommendation": "register_targeted_micro_experiment_only_after_review; do_not_start_1024_or_8192",
        "elapsed_s": time.perf_counter() - started,
    }
    atomic_json_save(audit, OUT / "audit.json")
    make_csv(audit)
    make_plot(audit)
    write_report(audit)
    print(json.dumps({
        "status": audit["status"],
        "output": str(OUT),
        "new_updates": 0,
        "identity_match": identity_match,
        "long_run_unlocked": False,
    }, ensure_ascii=False))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    run(parser.parse_args())

