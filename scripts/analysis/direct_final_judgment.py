"""Final evidence rollup for the direct mechanism goal."""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_paths import PROJECT_DIR, configure
configure()

from pidon_recording import atomic_json_save


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"
RUNS = OUT / "runs"
BENEFIT = OUT / "benefit"
S1 = OUT / "s1_phase1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(data, path)


def probe_waveform_metrics(summary: dict[str, Any]) -> list[dict[str, Any]]:
    series = summary.get("probe_timeseries") or []
    by_probe = [{"dut": [], "ref": [], "cells": None} for _ in range(3)]
    for row in series:
        for i, item in enumerate((row.get("source_outside_probes") or [])[:3]):
            by_probe[i]["cells"] = item.get("cells")
            by_probe[i]["dut"].append(float(item.get("dut_Ez", 0.0) or 0.0))
            by_probe[i]["ref"].append(float(item.get("ref_Ez", 0.0) or 0.0))
    out = []
    for i, probe in enumerate(by_probe):
        dut = probe["dut"]
        ref = probe["ref"]
        if not dut or not ref:
            out.append({"index": i, "cells": probe["cells"], "valid": False, "relative_l2": None})
            continue
        den = math.sqrt(sum(v * v for v in ref))
        num = math.sqrt(sum((a - b) ** 2 for a, b in zip(dut, ref)))
        peak = max(abs(v) for v in ref)
        rel = None if den == 0.0 else num / den
        valid = den > 0.0 and peak > 1e-12
        out.append({
            "index": i,
            "cells": probe["cells"],
            "valid": valid,
            "ref_peak": peak,
            "relative_l2": rel,
            "pass_5pct": bool(valid and rel is not None and rel <= 0.05),
        })
    return out


def arm_summary(name: str, path: Path) -> dict[str, Any]:
    if not path.exists():
        # F22: "the summary file is not here" is not the same claim as "this
        # experiment was never executed".  Look at the run directory before
        # writing a completed arm down as NOT_RUN.
        run_dir = path.parent
        if run_dir.exists() and any(run_dir.iterdir()):
            return {"arm": name, "status": "INCOMPLETE", "path": display(path),
                    "reason": "run directory holds evidence but summary.json is absent",
                    "evidence_present": sorted(item.name for item in run_dir.iterdir())[:20]}
        return {"arm": name, "status": "NOT_RUN", "path": display(path),
                "reason": "run directory is absent or empty"}
    summary = read_json(path)
    last = summary.get("last_accepted_step") or {}
    row = last or summary.get("stop_row") or {}
    metrics = last.get("six_component_metrics") or {}
    components = metrics.get("components") or {}
    effective_nmae = {}
    weak_abs = {}
    for comp, data in components.items():
        if data.get("weak_reference"):
            weak_abs[comp] = {
                "absolute_mae": data.get("absolute_mae"),
                "weak_absolute_pass": data.get("weak_absolute_pass"),
                "reference_max": data.get("reference_max"),
            }
        else:
            effective_nmae[comp] = data.get("nmae")
    finite_nmae = [safe_float(v) for v in effective_nmae.values()]
    finite_nmae = [v for v in finite_nmae if v is not None]
    probes = probe_waveform_metrics(summary)
    valid_probes = [p for p in probes if p.get("valid")]
    return {
        "arm": name,
        "status": summary.get("status"),
        "accepted_steps": summary.get("accepted_steps"),
        "target_steps": summary.get("target_steps"),
        "elapsed_s": summary.get("elapsed_s"),
        "budget": summary.get("budget"),
        "stop_reason": (summary.get("stop") or {}).get("reason"),
        "recovery_eligible": summary.get("recovery_eligible"),
        "final_H_R": (row.get("fit_H") or {}).get("residual_ratio"),
        "final_E_R": (row.get("fit_E") or {}).get("residual_ratio"),
        "global_weighted_relative_l2": metrics.get("global_weighted_relative_l2"),
        "fixed_amplitude_error": metrics.get("fixed_amplitude_error"),
        "effective_component_nmae": effective_nmae,
        "max_effective_component_nmae": max(finite_nmae) if finite_nmae else None,
        "weak_component_absolute": weak_abs,
        "source_probe_Ez": last.get("source_probe_Ez"),
        "probe_waveform": probes,
        "valid_probe_count": len(valid_probes),
        "path": display(path),
        "run_dir": summary.get("run_dir"),
    }


def task_status_table() -> list[dict[str, Any]]:
    plan = read_json(ROOT / "project" / "plan.json")
    rows = []
    for task in plan.get("tasks", []):
        rows.append({
            "id": task.get("id"),
            "status": task.get("status"),
            "scientific_result": task.get("scientific_result"),
            "evidence": task.get("evidence"),
        })
    return rows


def lab_costs() -> dict[str, Any]:
    rows = read_jsonl(ROOT / "records" / "lab_runs.jsonl")
    relevant = []
    for row in rows:
        cmd = str(row.get("cmd", ""))
        note = str(row.get("note", ""))
        if any(token in cmd or token in note for token in (
            "direct_m2_runner", "direct_m2_audit", "s1_interrupted_audit",
            "direct_benefit_runner", "direct_final_judgment",
        )):
            relevant.append({
                "id": row.get("id"),
                "note": note,
                "cmd": cmd,
                "exit_code": row.get("exit_code"),
                "seconds": row.get("seconds"),
            })
    return {
        "relevant_lab_runs": relevant,
        "recorded_seconds_sum": sum(float(r.get("seconds") or 0.0) for r in relevant),
    }


def build_audit(action_id: str) -> dict[str, Any]:
    m2_audit = read_json(OUT / "m2_audit.json") if (OUT / "m2_audit.json").exists() else {}
    b_audit = read_json(BENEFIT / "B_audit.json") if (BENEFIT / "B_audit.json").exists() else {}
    s1_audit = read_json(S1 / "interrupted_audit.json") if (S1 / "interrupted_audit.json").exists() else {}
    arms = {
        "A-R": arm_summary("A-R", RUNS / "A_R" / "summary.json"),
        "A-P": arm_summary("A-P", RUNS / "A_P" / "summary.json"),
        "B-R": arm_summary("B-R", RUNS / "B_R" / "summary.json"),
        "B-P": arm_summary("B-P", RUNS / "B_P" / "summary.json"),
        "B-R2": arm_summary("B-R2", BENEFIT / "B_R2" / "summary.json"),
    }
    online_adam = sum(int((arm.get("budget") or {}).get("adam", 0) or 0) for arm in arms.values())
    online_closures = sum(int((arm.get("budget") or {}).get("closures", 0) or 0) for arm in arms.values())
    long_unlocked = bool(m2_audit.get("long_run_unlocked"))
    field_pass = bool(m2_audit.get("field_gate_pass_arms"))
    s1_complete = s1_audit.get("status") == "PASS"
    benefit_pass = bool(b_audit.get("field_gate_benefit_pass"))
    recommendation = (
        "do_not_continue_current_pi_don_path_to_1024_or_8192; "
        "treat residual training success as diagnostic only until field gates and S1 provenance are fixed"
    )
    return {
        "schema": "direct-final-judgment-v1",
        "action_id": action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "task_status": task_status_table(),
        "arms": arms,
        "s1": s1_audit,
        "m2": {
            "residual_128_pass_arms": m2_audit.get("residual_128_pass_arms"),
            "field_gate_pass_arms": m2_audit.get("field_gate_pass_arms"),
            "long_run_unlocked": long_unlocked,
            "recommendation": m2_audit.get("recommendation"),
        },
        "benefit": b_audit,
        "costs": {
            "online_adam_in_m2_and_b_r2": online_adam,
            "online_closures_in_m2_and_b_r2": online_closures,
            "s1_recorded_updates_before_interruption": (s1_audit.get("last_history") or {}).get("updates"),
            **lab_costs(),
        },
        "final_gates": {
            "phase1_complete_blind_pass": s1_complete,
            "residual_128_has_candidates": bool(m2_audit.get("residual_128_pass_arms")),
            "field_128_pass": field_pass,
            "longrun_unlocked": long_unlocked,
            "benefit_pass": benefit_pass,
            "reuse_test_possible": False,
        },
        "scientific_conclusion": {
            "paper_mechanism_reproduced": False,
            "research_direction_supported_as_current_implementation": False,
            "recommendation": recommendation,
            "plain_language": (
                "当前证据支持：DCO在线每步拟合残差可以被优化到128步。"
                "但场误差、源外波形、第一阶段完整盲测和预训练收益均未过关或缺证据，"
                "所以不能说论文机制已复现，也不应在当前路线下启动1024/8192。"
            ),
        },
    }


def write_report(audit: dict[str, Any], out_dir: Path) -> None:
    lines = [
        "# Final Report - Direct Mechanism v1",
        "",
        f"- Action: `{audit.get('action_id')}`; lab_run_id: `{audit.get('lab_run_id')}`",
        "- Conclusion: current evidence does **not** reproduce the PI-DON paper mechanism as a reliable field solver.",
        "- Positive evidence: several DCO online arms can satisfy the registered residual gate for 128 steps.",
        "- Negative/limiting evidence: 128-step field gates fail, S1 is incomplete, benefit fails, and long runs are not unlocked.",
        "",
        "## Task Outcomes",
        "",
        "| Task | Delivery | Scientific | Evidence |",
        "|---|---|---|---|",
    ]
    for row in audit["task_status"]:
        ev = ", ".join(f"`{e}`" for e in (row.get("evidence") or [])[:3])
        lines.append(f"| {row['id']} | {row['status']} | {row.get('scientific_result')} | {ev} |")
    lines.extend([
        "",
        "## Online Arms",
        "",
        "| Arm | Status | Accepted | Adam | Closures | Elapsed s | H R | E R | Max effective nMAE | Probe valid/pass | Recovery |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for name, arm in audit["arms"].items():
        budget = arm.get("budget") or {}
        probes = arm.get("probe_waveform") or []
        valid = [p for p in probes if p.get("valid")]
        probe_pass = [p for p in valid if p.get("pass_5pct")]
        lines.append(
            f"| {name} | {arm.get('status')} | {arm.get('accepted_steps')} | "
            f"{budget.get('adam')} | {budget.get('closures')} | {arm.get('elapsed_s')} | "
            f"{arm.get('final_H_R')} | {arm.get('final_E_R')} | "
            f"{arm.get('max_effective_component_nmae')} | {len(valid)}/{len(probe_pass)} | "
            f"{arm.get('recovery_eligible')} |"
        )
    costs = audit["costs"]
    lines.extend([
        "",
        "## Costs",
        "",
        f"- M2+B-R2 online Adam updates: `{costs.get('online_adam_in_m2_and_b_r2')}`; LBFGS closures: `{costs.get('online_closures_in_m2_and_b_r2')}`.",
        f"- S1 recorded before interruption: `{costs.get('s1_recorded_updates_before_interruption')}` Adam updates.",
        f"- Relevant recorded lab wall time sum: `{costs.get('recorded_seconds_sum')}` seconds.",
        "",
        "## Interpretation",
        "",
        "- Strict residual evidence: A-P, B-R, B-P and B-R2 show that the current optimizer can force local residuals below the registered threshold for 128 steps.",
        "- Field evidence: the residual-passing arms still have about five-percent component-scale field errors and source-outside waveform failures, so residual success did not translate into a reliable electromagnetic field.",
        "- Phase-1 evidence: the full S1 attempt reached epoch 937 and best dev macro nMAE about 2.19%, but it lacks terminal state and blind migration testing; it is incomplete, not a pass or scientific fail.",
        "- Benefit evidence: B-P did not save Adam updates relative to two random controls, and any cost comparison is not useful for the paper claim while field gates fail.",
        "- Long-run evidence: no arm is qualified for 1024, 8192, or frozen reuse; those remain NOT_RUN by design.",
        "",
        "## Research Judgment",
        "",
        audit["scientific_conclusion"]["plain_language"],
        "",
        "Practical next step, if continuing research: fix provenance/resume for S1 first, then investigate why residual-matched fields remain wrong. Do not spend compute on 1024/8192 under the current gates.",
        "",
        "## Files",
        "",
        f"- Final audit JSON: `{display(out_dir / 'FINAL_JUDGMENT.json')}`",
        f"- M2 audit: `{display(OUT / 'm2_audit.json')}`",
        f"- B audit: `{display(BENEFIT / 'B_audit.json')}`",
        f"- S1 audit: `{display(S1 / 'interrupted_audit.json')}`",
        "",
    ])
    (out_dir / "FINAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def update_stage_status(audit: dict[str, Any]) -> None:
    path = OUT / "stage_status.json"
    stage = read_json(path) if path.exists() else {"schema": "direct-mechanism-stage-status-v1"}
    stage["V"] = {
        "schema": "direct-final-judgment-v1",
        "status": "PASS",
        "scientific_result": "FAIL",
        "paper_mechanism_reproduced": False,
        "research_direction_supported_as_current_implementation": False,
        "report": display(OUT / "FINAL_REPORT.md"),
        "audit": display(OUT / "FINAL_JUDGMENT.json"),
    }
    write_json(path, stage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--out-dir", default="",
                        help="new output directory; without it a re-run refuses to "
                             "overwrite the historical FINAL_REPORT/FINAL_JUDGMENT")
    parser.add_argument("--overwrite-historical", action="store_true",
                        help="explicitly allow rewriting the original fixed evidence files")
    args = parser.parse_args()
    # F22: this entry point rewrote FINAL_JUDGMENT.json, FINAL_REPORT.md and
    # stage_status.json in place.  Run it once with the evidence missing and
    # the historical judgement is replaced by one derived from absent files.
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif args.overwrite_historical:
        out_dir = OUT
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = OUT / "rejudgment" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = build_audit(args.action_id)
    audit["output_dir"] = display(out_dir)
    incomplete = sorted(key for key, arm in audit.get("arms", {}).items()
                        if arm.get("status") in ("INCOMPLETE", "NOT_RUN"))
    audit["input_completeness"] = {
        "arms_without_summary": incomplete,
        "note": "INCOMPLETE 表示证据不在当前路径，不是科学 FAIL；缺件不改判旧结论。",
    }
    write_json(out_dir / "FINAL_JUDGMENT.json", audit)
    write_report(audit, out_dir)
    if out_dir == OUT:
        update_stage_status(audit)
    else:
        print(f"  stage_status.json 未改写；本次为只读输入/新输出重审：{display(out_dir)}")
    print(json.dumps({
        "paper_mechanism_reproduced": audit["scientific_conclusion"]["paper_mechanism_reproduced"],
        "research_direction_supported_as_current_implementation": audit["scientific_conclusion"]["research_direction_supported_as_current_implementation"],
        "longrun_unlocked": audit["final_gates"]["longrun_unlocked"],
        "report": display(out_dir / "FINAL_REPORT.md"),
        "audit": display(out_dir / "FINAL_JUDGMENT.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
