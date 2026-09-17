"""Audit M2 direct-mechanism 128-step arms and rewrite the M2 report."""
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


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1"
RUNS = OUT / "runs"
ARMS = ("A-R", "A-P", "B-R", "B-P")
REQUIRED_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
COMPONENT_NMAE_GATE = 0.01
Q_GATE = 0.05
FIXED_AMPLITUDE_GATE = 1e-3
WEAK_ABSOLUTE_GATE = 1e-5


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


def missing_summary_state(run_dir: Path) -> dict[str, Any]:
    """Tell "never started" apart from "evidence is not here any more".

    F22: a missing summary.json was reported as NOT_RUN, so re-running this
    generator after the evidence moved would have rewritten a completed
    experiment into one that never happened.  Any other artefact in the run
    directory -- a log, a checkpoint, a pointer -- means the run did start and
    the summary is what is missing, which is INCOMPLETE.
    """
    markers = ["steps.jsonl", "run_metadata.json", "checkpoint_pointer.json",
               "checkpoint_A.pt", "checkpoint_B.pt", "checkpoint_latest.pt"]
    present = [name for name in markers if (run_dir / name).exists()]
    if not run_dir.exists():
        return {"status": "NOT_RUN", "evidence_present": [],
                "reason": "run directory does not exist at this path"}
    if present or any(run_dir.iterdir()):
        return {"status": "INCOMPLETE", "evidence_present": present,
                "reason": "run directory holds evidence but summary.json is absent"}
    return {"status": "NOT_RUN", "evidence_present": [],
            "reason": "run directory is empty"}


def summarize_arm(arm: str) -> dict[str, Any]:
    run_dir = RUNS / arm.replace("-", "_")
    path = run_dir / "summary.json"
    if not path.exists():
        state = missing_summary_state(run_dir)
        return {"arm": arm, "status": state["status"], "run_dir": display(run_dir),
                "field_gate_pass": False, "field_gate_status": "INCOMPLETE",
                "residual_128_pass": False,
                "missing_summary": state}
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
    # F02 (supplement): the old loop skipped absent components entirely and
    # then dropped every non-finite nMAE before taking the max, so a record
    # with three components, a NaN Ey and a weak Hz that missed its absolute
    # gate still produced field_gate_pass=True.  Missing or non-finite is now
    # INCOMPLETE, never "small enough".
    component_failures: list[str] = []
    missing_components = [name for name in REQUIRED_COMPONENTS if name not in components]
    for name in REQUIRED_COMPONENTS:
        comp = components.get(name)
        if not isinstance(comp, dict):
            continue
        if comp.get("weak_reference"):
            absolute = safe_float(comp.get("absolute_mae"))
            gate = safe_float(comp.get("weak_absolute_gate")) or WEAK_ABSOLUTE_GATE
            weak_abs[name] = {
                "absolute_mae": comp.get("absolute_mae"),
                "weak_absolute_pass": comp.get("weak_absolute_pass"),
                "weak_absolute_gate": gate,
                "reference_max": comp.get("reference_max"),
            }
            if absolute is None or absolute > gate or not bool(comp.get("weak_absolute_pass")):
                component_failures.append(f"{name}: weak absolute {comp.get('absolute_mae')} > {gate}")
        else:
            effective_nmae[name] = comp.get("nmae")
            value = safe_float(comp.get("nmae"))
            if value is None:
                component_failures.append(f"{name}: nmae is not a finite number ({comp.get('nmae')!r})")
            elif value > COMPONENT_NMAE_GATE:
                component_failures.append(f"{name}: nmae {value} > {COMPONENT_NMAE_GATE}")
    finite_nmae = [safe_float(value) for value in effective_nmae.values()]
    finite_nmae = [value for value in finite_nmae if value is not None]
    max_effective_nmae = max(finite_nmae) if finite_nmae else None
    fixed_amp = (metrics or {}).get("fixed_amplitude_error")
    q_value = safe_float(metrics.get("global_weighted_relative_l2"))
    probes = probe_metrics(summary)
    valid_probes = [p for p in probes if p.get("valid")]
    probe_pass = len(valid_probes) >= 2 and all(p.get("pass_5pct") for p in valid_probes)
    residual_128_pass = summary.get("status") == "PASS" and int(summary.get("accepted_steps", 0)) >= 128
    complete = bool(components) and not missing_components and len(valid_probes) >= 2
    field_gate_pass = bool(
        complete and residual_128_pass and not component_failures and
        q_value is not None and q_value <= Q_GATE and
        safe_float(fixed_amp) is not None and safe_float(fixed_amp) <= FIXED_AMPLITUDE_GATE and
        probe_pass
    )
    field_gate_status = ("PASS" if field_gate_pass
                         else "INCOMPLETE" if not complete else "FAIL")
    return {
        "arm": arm,
        "status": summary.get("status"),
        "residual_128_pass": residual_128_pass,
        "field_gate_pass": field_gate_pass,
        "field_gate_status": field_gate_status,
        "field_gate_complete": complete,
        "missing_components": missing_components,
        "component_failures": component_failures,
        "global_weighted_relative_l2_le_5pct": q_value is not None and q_value <= Q_GATE,
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


def interpretation_lines(audit: dict[str, Any]) -> list[str]:
    """Derive the narrative from the audited rows.

    F22: this section used to be a hard-coded retelling of one historical
    outcome, so re-running the generator on different (or absent) evidence
    printed conclusions the data no longer supported.
    """
    lines: list[str] = []
    for arm in audit["arms"]:
        name = arm["arm"]
        if arm.get("missing_summary"):
            state = arm["missing_summary"]
            lines.append(f"- {name}: `{arm['status']}` -- {state['reason']}; "
                         f"evidence present: {state['evidence_present'] or 'none'}.")
            continue
        accepted = arm.get("accepted_steps") or 0
        detail = f"- {name}: status `{arm.get('status')}`, accepted {accepted} steps, "
        detail += f"field gate `{arm.get('field_gate_status')}`"
        failures = arm.get("component_failures") or []
        if arm.get("missing_components"):
            detail += f"; components absent: {', '.join(arm['missing_components'])}"
        if failures:
            detail += "; " + "; ".join(failures[:4])
        lines.append(detail + ".")
    passed = audit["field_gate_pass_arms"]
    if passed:
        lines.append(f"- Field gate passed for: {', '.join(passed)}; a G128 selection review is required "
                     "before any long run.")
    else:
        lines.append("- No arm passed the registered field gate, so 1024/8192 stay NOT_RUN.")
    incomplete = [a["arm"] for a in audit["arms"] if a.get("field_gate_status") == "INCOMPLETE"]
    if incomplete:
        lines.append(f"- INCOMPLETE (evidence absent or partial, NOT a scientific FAIL): {', '.join(incomplete)}.")
    return lines


def write_report(audit: dict[str, Any], out_dir: Path) -> None:
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
            f"| {arm['arm']} | {arm['status']} | {arm['residual_128_pass']} | {arm.get('field_gate_status')} | "
            f"{arm.get('accepted_steps') or 0} | {budget.get('adam', 0)} | {budget.get('closures', 0)} | "
            f"{arm.get('final_H_R')} | {arm.get('final_E_R')} | {arm.get('max_effective_component_nmae')} | {max_probe} |"
        )
    lines.extend(["", "## Interpretation", ""])
    lines.extend(interpretation_lines(audit))
    lines.extend([
        "",
        "## Files",
        "",
        f"- Audit JSON: `{display(out_dir / 'm2_audit.json')}`",
        f"- Runs: `{display(RUNS)}`",
        "",
    ])
    (out_dir / "M2_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", default="")
    parser.add_argument("--out-dir", default="",
                        help="new output directory; defaults to a fresh timestamped "
                             "directory so a re-run never overwrites a historical audit")
    parser.add_argument("--overwrite-historical", action="store_true",
                        help="explicitly allow writing into the original fixed evidence directory")
    args = parser.parse_args()
    # F22: this generator wrote m2_audit.json and M2_REPORT.md straight back
    # into the historical evidence directory.  Re-running it after the runs
    # moved would have replaced an audited result with one derived from
    # missing files.  Read-only inputs, new outputs.
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif args.overwrite_historical:
        out_dir = OUT
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = OUT / "reaudit" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
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
    audit["output_dir"] = display(out_dir)
    audit["inputs_read_only"] = True
    (out_dir / "m2_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(audit, out_dir)
    print(json.dumps({
        "residual_128_pass_arms": audit["residual_128_pass_arms"],
        "field_gate_pass_arms": audit["field_gate_pass_arms"],
        "recommendation": audit["recommendation"],
        "audit": display(OUT / "m2_audit.json"),
        "report": display(OUT / "M2_REPORT.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
