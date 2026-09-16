"""Audit M2 direct-mechanism 128-step arms and rewrite the M2 report."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

from project_paths import PROJECT_DIR, configure
configure()


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"
RUNS = OUT / "runs"
ARMS = ("A-R", "A-P", "B-R", "B-P")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def probe_metrics(summary: dict[str, Any]) -> list[dict[str, Any]]:
    series = summary.get("probe_timeseries") or []
    by_probe: list[dict[str, list[float]]] = [
        {"dut": [], "ref": []}, {"dut": [], "ref": []}, {"dut": [], "ref": []}
    ]
    cells = [None, None, None]
    for row in series:
        probes = row.get("source_outside_probes") or []
        for i, item in enumerate(probes[:3]):
            cells[i] = item.get("cells")
            by_probe[i]["dut"].append(float(item.get("dut_Ez", 0.0) or 0.0))
            by_probe[i]["ref"].append(float(item.get("ref_Ez", 0.0) or 0.0))
    result = []
    for i, values in enumerate(by_probe):
        dut = values["dut"]
        ref = values["ref"]
        if not dut or not ref:
            result.append({"index": i, "cells": cells[i], "status": "N_A", "reason": "missing"})
            continue
        num = math.sqrt(sum((a - b) ** 2 for a, b in zip(dut, ref)))
        den = math.sqrt(sum(b ** 2 for b in ref))
        peak = max(abs(b) for b in ref)
        rel = None if den == 0 else num / den
        valid = den > 0.0 and peak > 1e-12
        result.append({
            "index": i,
            "cells": cells[i],
            "ref_peak": peak,
            "relative_l2": rel,
            "valid": valid,
            "pass_5pct": bool(valid and rel is not None and rel <= 0.05),
        })
    return result


def summarize_arm(arm: str) -> dict[str, Any]:
    run_dir = RUNS / arm.replace("-", "_")
    path = run_dir / "summary.json"
    if not path.exists():
        return {"arm": arm, "status": "NOT_RUN", "run_dir": display(run_dir)}
    summary = read_json(path)
    last = summary.get("last_accepted_step") or {}
    stop_row = summary.get("stop_row") or {}
    row = last or stop_row
    fit_h = row.get("fit_H") or {}
    fit_e = row.get("fit_E") or {}
    metrics = (last.get("six_component_metrics") or {})
    components = metrics.get("components") or {}
    effective_nmae = {}
    weak_abs = {}
    for name, comp in components.items():
        if comp.get("weak_reference"):
            weak_abs[name] = {
                "absolute_mae": comp.get("absolute_mae"),
                "weak_absolute_pass": comp.get("weak_absolute_pass"),
                "reference_max": comp.get("reference_max"),
            }
        else:
            effective_nmae[name] = comp.get("nmae")
    finite_nmae = [safe_float(value) for value in effective_nmae.values()]
    finite_nmae = [value for value in finite_nmae if value is not None]
    max_effective_nmae = max(finite_nmae) if finite_nmae else None
    fixed_amp = (metrics or {}).get("fixed_amplitude_error")
    probes = probe_metrics(summary)
    valid_probes = [p for p in probes if p.get("valid")]
    probe_pass = len(valid_probes) >= 2 and all(p.get("pass_5pct") for p in valid_probes)
    residual_128_pass = summary.get("status") == "PASS" and int(summary.get("accepted_steps", 0)) >= 128
    field_gate_pass = bool(
        residual_128_pass and
        max_effective_nmae is not None and max_effective_nmae <= 0.01 and
        safe_float(fixed_amp) is not None and safe_float(fixed_amp) <= 1e-3 and
        probe_pass
    )
    return {
        "arm": arm,
        "status": summary.get("status"),
        "residual_128_pass": residual_128_pass,
        "field_gate_pass": field_gate_pass,
        "accepted_steps": summary.get("accepted_steps"),
        "target_steps": summary.get("target_steps"),
        "elapsed_s": summary.get("elapsed_s"),
        "budget": summary.get("budget"),
        "stop_reason": (summary.get("stop") or {}).get("reason"),
        "recovery_eligible": summary.get("recovery_eligible"),
        "final_H_R": fit_h.get("residual_ratio"),
        "final_E_R": fit_e.get("residual_ratio"),
        "global_weighted_relative_l2": metrics.get("global_weighted_relative_l2"),
        "fixed_amplitude_error": fixed_amp,
        "effective_component_nmae": effective_nmae,
        "max_effective_component_nmae": max_effective_nmae,
        "weak_component_absolute": weak_abs,
        "probe_waveform": probes,
        "valid_probe_count": len(valid_probes),
        "source_probe_Ez": last.get("source_probe_Ez"),
        "last_source_outside_probes": last.get("source_outside_probes"),
        "run_dir": display(run_dir),
    }


def write_report(audit: dict[str, Any]) -> None:
    lines = [
        "# M2 Report - Direct 128 Queue Audit",
        "",
        f"- Action: `{audit.get('action_id')}`; lab_run_id: `{audit.get('lab_run_id')}`",
        "- `Residual128 PASS` means all 128 accepted time steps met the per-half residual gate.",
        "- `Field gate PASS` additionally requires the registered field/probe checks; none passed here.",
        "",
        "| Arm | Status | Residual128 | Field gate | Accepted | Adam | Closures | H R | E R | Max nMAE | Probe L2 max |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in audit["arms"]:
        budget = arm.get("budget") or {}
        valid_probe_l2 = [p.get("relative_l2") for p in arm.get("probe_waveform", []) if p.get("valid") and p.get("relative_l2") is not None]
        max_probe = max(valid_probe_l2) if valid_probe_l2 else None
        lines.append(
            f"| {arm['arm']} | {arm['status']} | {arm['residual_128_pass']} | {arm['field_gate_pass']} | "
            f"{arm.get('accepted_steps') or 0} | {budget.get('adam', 0)} | {budget.get('closures', 0)} | "
            f"{arm.get('final_H_R')} | {arm.get('final_E_R')} | {arm.get('max_effective_component_nmae')} | {max_probe} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- A-R failed at 33 accepted steps; its failed E residual is far above the strict gate.",
        "- A-P, B-R and B-P all reached 128 residual-accepted steps.",
        "- All 128-step arms fail the field gate because effective component nMAE is about 4.8% to 5.1%, above the 1% gate; source-outside waveform errors are also not all within 5%.",
        "- Therefore M2 produces useful mechanism/optimizer evidence but does not unlock 1024/8192.",
        "",
        "## Files",
        "",
        f"- Audit JSON: `{display(OUT / 'm2_audit.json')}`",
        f"- Runs: `{display(RUNS)}`",
        "",
    ])
    (OUT / "M2_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", default="")
    args = parser.parse_args()
    arms = [summarize_arm(arm) for arm in ARMS]
    residual_pass = [a for a in arms if a.get("residual_128_pass")]
    field_pass = [a for a in arms if a.get("field_gate_pass")]
    audit = {
        "schema": "direct-mechanism-m2-audit-v1",
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "arms": arms,
        "residual_128_pass_arms": [a["arm"] for a in residual_pass],
        "field_gate_pass_arms": [a["arm"] for a in field_pass],
        "g128_qualified": bool(field_pass),
        "long_run_unlocked": bool(field_pass),
        "recommendation": "do_not_start_1024_or_8192" if not field_pass else "run_G128_selection_before_longrun",
    }
    (OUT / "m2_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(audit)
    print(json.dumps({
        "residual_128_pass_arms": audit["residual_128_pass_arms"],
        "field_gate_pass_arms": audit["field_gate_pass_arms"],
        "recommendation": audit["recommendation"],
        "audit": display(OUT / "m2_audit.json"),
        "report": display(OUT / "M2_REPORT.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
