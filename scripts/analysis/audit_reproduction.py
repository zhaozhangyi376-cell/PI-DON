"""P0: inventory and audit existing PI-DON reproduction evidence.

This script is deliberately read-only with respect to previous experiment
artifacts.  It writes a new audit report and a frozen acceptance register so
that later phases cannot silently reinterpret historical trajectories.
"""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import hashlib
import json
import math
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from fdtd import gaussian_pulse


ROOT = PROJECT_ROOT

ARTIFACTS = {
    "phase1_checkpoint_lr1e3": "dco_lr1e3_300.pt",
    "phase1_checkpoint_paper32": "dco_paper32.pt",
    "phase1_data_32": "data_32.npz",
    "phase1_data_32_pw": "data_32_pw.npz",
    "trajectory_128": "evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json",
    "trajectory_64": "evidence/pidon_stage2_64_component_lr3e4_tol1e5.json",
    "longrun_report": "evidence/stage2_longrun/STAGE2_LONGRUN_REPORT.md",
    "current_solver": "pidon_solve.py",
    "current_fdtd": "fdtd.py",
    "current_dco": "dco.py",
    "claim_registry": "verify_claims.py",
    "lab_log": "lab_log.py",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_record(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    record: dict[str, Any] = {
        "label": label,
        "path": relative.replace("\\", "/"),
        "exists": path.is_file(),
        "historical_provenance": "unknown",
    }
    if path.is_file():
        record.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
    if label.startswith("phase1_"):
        record["historical_provenance"] = (
            "current-file inventory only; the original generating command and "
            "input-data hashes are not contained in this artifact"
        )
    elif label.startswith("trajectory_"):
        record["historical_provenance"] = (
            "trajectory JSON is present, but it omits a complete configuration, "
            "RNG state, optimizer state, and checkpoint linkage"
        )
    else:
        record["historical_provenance"] = "current-file inventory"
    return record


def source_version() -> str | None:
    text = (ROOT / "pidon_solve.py").read_text(encoding="utf-8")
    match = re.search(r'^SCRIPT_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return match.group(1) if match else None


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def descriptive_stepgain(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    for row in rows:
        value = safe_float(row.get("nmae"))
        step = safe_float(row.get("step"))
        if value is not None and step is not None and value > 0:
            pairs.append((step, value))
    if len(pairs) < 2:
        return {"available": False, "reason": "fewer than two positive nMAE rows"}
    max_value = max(value for _, value in pairs)
    selected = [(step, value) for step, value in pairs if value > 0.15 * max_value]
    if len(selected) < 2:
        selected = pairs
    slope, intercept = np.polyfit(
        [step for step, _ in selected], [math.log(value) for _, value in selected], 1
    )
    return {
        "available": True,
        "label": "descriptive log-linear fit; it is neither a spectral radius nor an exact one-step multiplier",
        "selection": "nMAE > 0.15 * trajectory maximum (fall back to all positive rows)",
        "n_points": len(selected),
        "log_slope_per_step": float(slope),
        "stepgain": float(math.exp(slope)),
        "intercept": float(intercept),
    }


def trajectory_audit(relative: str, current_version: str | None) -> dict[str, Any]:
    path = ROOT / relative
    if not path.is_file():
        return {"path": relative, "exists": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError(f"{relative}: rows is not a list")
    tolerance = safe_float(payload.get("tol"))
    continuity = [row.get("step") == index for index, row in enumerate(rows)]
    fields = ["step", "itH", "lossH", "cumH", "itE", "lossE", "cumE", "nmae"]
    missing_by_field = {
        field: sum(field not in row for row in rows) for field in fields
    }
    h_nonzero = [row for row in rows if int(row.get("itH", 0) or 0) > 0]
    e_nonzero = [row for row in rows if int(row.get("itE", 0) or 0) > 0]

    def pass_count(which: str, applicable: list[dict[str, Any]]) -> dict[str, Any]:
        key = "lossH" if which == "H" else "lossE"
        values = [safe_float(row.get(key)) for row in applicable]
        valid = [value for value in values if value is not None]
        passed = (
            sum(value < tolerance for value in valid) if tolerance is not None else None
        )
        return {
            "applicable_rows": len(applicable),
            "finite_final_loss_rows": len(valid),
            "passed_final_loss_lt_tol": passed,
            "failed_or_missing": None if passed is None else len(applicable) - passed,
        }

    final_row = rows[-1] if rows else {}
    source_version_value = payload.get("version")
    return {
        "path": relative,
        "exists": True,
        "sha256": sha256(path),
        "metadata": {
            key: payload.get(key)
            for key in ("version", "n", "side", "dt", "steps", "tol", "lr", "max_inner")
        },
        "row_count": len(rows),
        "step_continuity": {
            "all_zero_based_contiguous": all(continuity),
            "bad_row_indices": [i for i, ok in enumerate(continuity) if not ok][:20],
        },
        "required_historical_fields_missing_count": missing_by_field,
        "strict_final_loss_reconstruction": {
            "criterion": "recorded final loss < recorded tolerance; H rows with itH == 0 are excluded as historical zero/shortcut rows",
            "tolerance": tolerance,
            "H": pass_count("H", h_nonzero),
            "E": pass_count("E", e_nonzero),
        },
        "final_row": {
            key: final_row.get(key)
            for key in ("step", "lossH", "lossE", "nmae", "cumH", "cumE", "probe_dut", "probe_ref")
        },
        "descriptive_nmae_growth": descriptive_stepgain(rows),
        "version_reproducibility_risk": {
            "recorded_solver_version": source_version_value,
            "current_solver_version": current_version,
            "matches_current_source": source_version_value == current_version,
            "interpretation": (
                "a mismatch means the JSON cannot by itself establish that the current dirty source reproduces the recorded trajectory"
            ),
        },
        "known_omissions": [
            "complete CLI/configuration", "network and optimizer state", "RNG state",
            "per-step six-component field errors", "source-outside probes", "restart record",
        ],
    }


def source_timing() -> dict[str, Any]:
    dt = 3.075e-12
    total = 8192
    signal, tau, t0 = gaussian_pulse(total, dt, f_max=15e9, level=0.1)
    peak_index = int(np.argmax(np.abs(signal)))
    peak = float(np.abs(signal[peak_index]))
    post = np.flatnonzero(np.abs(signal[peak_index:]) <= peak * 1e-4)
    tail_index = int(peak_index + post[0]) if post.size else None
    side_m = 0.05
    f110 = math.sqrt(2.0) * 2.99792458e8 / (2.0 * side_m)
    return {
        "waveform": "fdtd.gaussian_pulse(fmax=15 GHz, level=0.1)",
        "dt_s": dt,
        "tau_s": float(tau),
        "t0_s": float(t0),
        "peak_index_zero_based": peak_index,
        "peak_time_s": peak_index * dt,
        "tail_below_peak_times_1e-4_index_zero_based": tail_index,
        "time_at_64_steps_s": 64 * dt,
        "time_at_128_steps_s": 128 * dt,
        "time_at_8192_steps_s": 8192 * dt,
        "mode_110_frequency_hz_for_side_0p05_m": f110,
        "mode_110_period_s": 1.0 / f110,
        "interpretation": (
            "The 64/128-step endpoints are pulse-transient windows, so a source-cell probe alone cannot establish propagation or cavity resonance."
        ),
    }


def acceptance_register() -> dict[str, Any]:
    return {
        "protocol": "gpt6_plan_v1",
        "frozen_on": "2026-09-13",
        "rule": "Thresholds are registered before later numerical results and may not be relaxed because a test fails.",
        "metrics": {
            "paper_comparison": "Paper MRE and local-max nMAE are reported in separate columns and are never divided or ranked against each other.",
            "neural_error": "Six-component weighted global L2 and per-component weighted relative L2 with E0=1 and H0=E0/Z0; physical Yee dual volumes.",
            "residual": "Yee/Maxwell residual, reported separately from field error.",
        },
        "gates": {
            "P1_contract": [
                "strict stop refuses to advance an E or H half-step after a finite target fit misses tolerance",
                "non-finite fit triggers rollback/recovery and records the event",
                "checkpoint/restart preserves exact time-layer state and produces matching continuation on the deterministic test",
            ],
            "P2_exact_control": [
                "float64 exact Yee control remains finite through 128 steps",
                "float32 exact Yee control remains finite through 128 steps",
                "control output is labelled exact Yee, never DCO",
            ],
            "P3_fixed_state": [
                "each registered source-free fixed-state task reaches its frozen residual tolerance within its update budget",
                "all six components and source-outside probes are recorded",
                "a target-matched fixed-state result is not promoted to a closed-loop DCO result",
            ],
            "P4_short_rollout": [
                "only candidates passing P3 may enter 32/64/128-step closed-loop comparison",
                "report actual updates, final residual, six-component errors, source-outside probes, and restart state",
                "no automatic 8192-step continuation from a failed short-run gate",
            ],
            "P6_longer_rollout": [
                "128 and 1024 steps are distinct gated milestones; 8192 is forbidden until the registered preceding gates pass",
            ],
        },
    }


def markdown_report(audit: dict[str, Any]) -> str:
    t128 = audit["trajectories"].get("128_step", {})
    t64 = audit["trajectories"].get("64_step", {})
    lines = [
        "# P0 证据审计报告",
        "",
        "本报告只盘点既有文件，不重跑训练、不覆盖权重，也不把历史轨迹当作当前源码的可复现实验。",
        "",
        "## 已登记历史轨迹",
        "",
        "| 轨迹 | 行数 | H 达标/适用 | E 达标/适用 | 终点 nMAE | 当前源码可直接复现 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, item in (("128 步", t128), ("64 步", t64)):
        strict = item.get("strict_final_loss_reconstruction", {})
        h = strict.get("H", {})
        e = strict.get("E", {})
        final = item.get("final_row", {})
        risk = item.get("version_reproducibility_risk", {})
        lines.append(
            "| {name} | {rows} | {hp}/{ha} | {ep}/{ea} | {nmae} | {match} |".format(
                name=name,
                rows=item.get("row_count", "—"),
                hp=h.get("passed_final_loss_lt_tol", "—"),
                ha=h.get("applicable_rows", "—"),
                ep=e.get("passed_final_loss_lt_tol", "—"),
                ea=e.get("applicable_rows", "—"),
                nmae=final.get("nmae", "—"),
                match="是" if risk.get("matches_current_source") else "否/无法证明",
            )
        )
    lines += [
        "",
        "## 审计判读",
        "",
        "- 历史 JSON 中的 `lossH/lossE` 是当时记录的最终拟合损失；上表仅按 `final loss < tol` 回算，不能替代新的严格停止实现。",
        "- `stepgain` 只是对 nMAE 轨迹的描述性对数线性拟合，不能解释为谱半径、稳定性证据或精确单步放大率。",
        "- 64 与 128 步仍处于当前高斯激励的瞬态窗口。硬源点探针不能单独证明波已传播到源外，更不能证明腔体谐振。",
        "- 论文 MRE 与当前局部最大值 nMAE 分栏保存；没有同口径转换证据时，不作倍数比较。",
        "",
        "## 后续门槛",
        "",
        "验收条件已冻结在 `evidence/gpt6_plan_v1/acceptance.json`。后续 P1/P2/P3 的失败也不得修改这些门槛。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/audit.json")
    parser.add_argument("--acceptance", default="evidence/gpt6_plan_v1/acceptance.json")
    parser.add_argument("--report", default="evidence/gpt6_plan_v1/P0_AUDIT_REPORT.md")
    args = parser.parse_args()
    out = ROOT / args.out
    acceptance = ROOT / args.acceptance
    report = ROOT / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    acceptance.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    register = acceptance_register()
    if acceptance.exists():
        existing = json.loads(acceptance.read_text(encoding="utf-8"))
        if existing != register:
            raise RuntimeError(
                "acceptance register already exists and differs from this frozen protocol; refusing to overwrite it"
            )
    else:
        acceptance.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    current_version = source_version()
    audit = {
        "schema": "pidon-p0-audit-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": platform.platform(), "python": platform.python_version()},
        "scope": "read-only inventory and interpretation audit of pre-P0 artifacts",
        "current_solver_version": current_version,
        "artifacts": [artifact_record(label, relative) for label, relative in ARTIFACTS.items()],
        "trajectories": {
            "128_step": trajectory_audit(ARTIFACTS["trajectory_128"], current_version),
            "64_step": trajectory_audit(ARTIFACTS["trajectory_64"], current_version),
        },
        "source_timing": source_timing(),
        "registered_interpretations": [
            "Historical trajectory pass counts are evidence quality indicators, not proof of strict Algorithm 1 execution.",
            "A finite exact-Yee control will validate geometry/time indexing only; it is not a DCO result.",
            "A source-point probe is retained as diagnostic context, while P1 adds probes outside the source cell.",
            "The 31-interval reading of a nominal 32-point grid is a current CFL-consistency hypothesis, not author-confirmed paper metadata.",
        ],
    }
    out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report.write_text(markdown_report(audit), encoding="utf-8")
    print(json.dumps({
        "audit": str(out.relative_to(ROOT)).replace("\\", "/"),
        "acceptance": str(acceptance.relative_to(ROOT)).replace("\\", "/"),
        "report": str(report.relative_to(ROOT)).replace("\\", "/"),
        "historical_128_rows": audit["trajectories"]["128_step"].get("row_count"),
        "historical_64_rows": audit["trajectories"]["64_step"].get("row_count"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
