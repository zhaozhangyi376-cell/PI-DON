"""Bounded v4 night-stage runner.  G0 contains no DCO optimization."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch

import g0_verifier
import pidon_exact_control as control
import reference_cache
from night_budget import NightPaths, append_ledger, assert_can_start
from pidon_recording import sha256_file

ROOT = PROJECT_ROOT


def atomic_json(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def stage_g0(root: Path, contract_run: int, *, night_root: Path | None = None) -> dict:
    night_root = night_root or root
    paths = NightPaths(night_root)
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert_can_start(manifest, training=False)
    out_runs = root / "control_runs"
    if out_runs.exists() or (root / "controls.json").exists() or (root / "reference_cache.json").exists():
        raise FileExistsError("G0 evidence already exists; refusing to mix a second control execution")
    out_runs.mkdir()
    controls = {
        "float64": control.run(torch.float64, steps=128, out_dir=out_runs / "float64_exact", resume_after=64),
        "float32": control.run(torch.float32, steps=128, out_dir=out_runs / "float32_exact", resume_after=64),
        "zero_curl_negative": control.run(torch.float64, steps=128, mode="zero", out_dir=out_runs / "zero_curl_negative"),
        "hard_source_only_negative": control.run(torch.float64, steps=128, mode="hard_source_only", out_dir=out_runs / "hard_source_only_negative"),
        "wrong_h_half_negative": control.run(torch.float64, steps=128, mode="exact", out_dir=out_runs / "wrong_h_half_negative", wrong_h_half=True),
    }
    atomic_json(root / "controls.json", controls)
    cache = reference_cache.build()
    snapshots, probes = cache.pop("snapshots"), cache.pop("probes")
    snapshot_path = root / "reference_cache_snapshots.npz"
    np.savez_compressed(snapshot_path, probes=probes, **snapshots)
    cache["snapshot_npz"] = str(snapshot_path.relative_to(ROOT)).replace("\\", "/")
    cache["snapshot_sha256"] = sha256_file(snapshot_path)
    atomic_json(root / "reference_cache.json", cache)
    return publish_g0(root, contract_run, night_root=night_root)


def publish_g0(root: Path, contract_run: int, *, night_root: Path) -> dict:
    """Verify and publish already-complete raw G0 evidence without rerunning it."""
    paths = NightPaths(night_root)
    result = g0_verifier.verify(root, contract_run=contract_run,
                                n1_path=night_root / "N1_contract_checks.json")
    atomic_json(root / "G0.json", result)
    atomic_json(root / "required_g0_checks.json", {"checks": result["required_g0_checks"]})
    report = ["# N2 完整 G0 数值认证", "", f"- 合同回归 lab_log：#{contract_run}", f"- G0：**{result['G0']}**", "",
              "精确 Yee 控制的 `control_only=true`；它们只认证测量与恢复链路，不能计为 DCO 成绩。", "",
              "| ID | 状态 | 观测 |", "|---|---|---|"]
    report.extend(f"| {row['id']} | {row['status']} | `{json.dumps(row['observed'], ensure_ascii=False)}` |"
                  for row in result["required_g0_checks"])
    (root / "N2_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    stage_path = night_root / "stage_status.json"; stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["N2"] = {"implementation": "PASS" if result["G0"] == "PASS" else "FAIL", "scientific_gate": result["G0"],
                   "lab_run_id": None, "evidence": "G0.json"}
    atomic_json(stage_path, stage)
    append_ledger(paths, {"kind": "N2_g0", "task_id": "N2", "adam_updates": 0, "head_commits": 0,
                          "linear_solve_calls": 0, "training_s": 0.0,
                          "artifact_used_bytes": sum(path.stat().st_size for path in root.rglob("*") if path.is_file())})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--stage", choices=["g0", "g0-finalize"], required=True)
    parser.add_argument("--root", default="evidence/gpt6_plan_v4_night"); parser.add_argument("--attempt", default="")
    parser.add_argument("--contract-run", type=int, required=True)
    args = parser.parse_args(); night_root = (ROOT / args.root).resolve()
    root = night_root / args.attempt if args.attempt else night_root
    if args.stage == "g0":
        if args.attempt: root.mkdir(parents=False, exist_ok=False)
        result = stage_g0(root, args.contract_run, night_root=night_root)
    else:
        if not root.is_dir(): raise FileNotFoundError(root)
        result = publish_g0(root, args.contract_run, night_root=night_root)
    print(json.dumps({"stage": args.stage, "G0": result["G0"], "checks": len(result["required_g0_checks"])}, ensure_ascii=False))
    if result["G0"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
