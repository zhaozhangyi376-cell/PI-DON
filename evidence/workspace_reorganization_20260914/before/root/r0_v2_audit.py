"""Freeze the v2 protocol inputs before altering the stage-2 implementation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "gpt6_plan_v2"
SNAPSHOT = OUT / "r0_source_snapshot"
SOURCE_FILES = (
    "pidon_solve.py", "pidon_contract.py", "pidon_recording.py", "pidon_exact_control.py",
    "stage2_fixed_state.py", "phase1_pilot.py", "phase1_ab_pilot.py", "p3_report.py",
    "p4_report.py", "p5_audit.py", "p5_ab_audit.py", "verify_claims.py", "fdtd.py",
    "dco.py", "test_pidon_contract.py", "lab_log.py",
)
INPUT_FILES = ("dco_lr1e3_300.pt", "dco_paper32.pt", "data_32.npz")


def digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False).stdout


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    sources: dict[str, str | None] = {}
    for name in SOURCE_FILES:
        origin, target = ROOT / name, SNAPSHOT / name
        if origin.is_file():
            shutil.copy2(origin, target)
        sources[name] = digest(origin)
    for name in ("AGENTS.md", "STATUS.md", "RESULTS.md", "LAB_NOTEBOOK.md", "lab_runs.jsonl"):
        origin = ROOT / name
        if origin.is_file():
            shutil.copy2(origin, SNAPSHOT / name)
        sources[name] = digest(origin)
    (SNAPSHOT / "git_status.txt").write_text(git("status", "--short"), encoding="utf-8")
    (SNAPSHOT / "git_diff.patch").write_text(git("diff", "--no-ext-diff"), encoding="utf-8")
    (SNAPSHOT / "git_diff_cached.patch").write_text(git("diff", "--cached", "--no-ext-diff"), encoding="utf-8")

    acceptance = {
        "protocol": "gpt6_plan_v2",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "rule": "Thresholds may not be relaxed after observing a result.",
        "scales": {"L0_m": 0.05, "E0_V_per_m": 1.0, "Z0_ohm": "sqrt(mu0/eps0)",
                   "H0_A_per_m": "E0/Z0", "curlE0": 20.0, "curlH0": "H0/L0"},
        "time_and_geometry": {"n_intervals": 31, "side_m": 0.05, "dt_s": 3.075e-12,
                              "source": "gauss", "fmax_hz": 15e9,
                              "probes_cells": [[12, 12, 13], [8, 10, 12], [21, 19, 18]],
                              "Ez_offset_cells": [0, 0, 0.5],
                              "snapshots": [1, 2, 16, 32, 43, 64, 96, 128, 192, 300, 600, 900,
                                            1024, 2048, 4096, 8192]},
        "g0": {"exact_control_steps": 128, "float64_error_max": 1e-10, "float32_error_max": 1e-4,
               "strict_stop": True, "nonzero_target_R_lt": 1e-4,
               "zero_target_fixed_mse_max": 1e-10, "zero_target_max_residual_over_curl0": 1e-4},
        "g1": {"main_checkpoint": "dco_lr1e3_300.pt", "development_steps": [43, 96],
               "legacy_validation_steps": [16, 300, 600], "new_holdout_steps": [192, 450, 900],
               "adam_lr": 3e-4, "max_adam_updates": 500, "per_task_seconds": 360,
               "fixed_amplitude_error_max": 1e-3,
               "lbfgs": {"adam_first": 200, "lr": 1.0, "history": 10, "closures_max": 200,
                         "seconds_max": 60, "only_lr_backup": 1e-4}},
        "g2": {"steps": [128, 1024], "Q_max": 0.05, "active_nmae_max": 1e-2,
               "probe_waveform_l2_max": 0.05, "weak_abs_max": 1e-5,
               "seed_primary": 20260913, "seed_repeat": 20260914,
               "gpu_minutes_128": 60, "gpu_hours_1024_increment": 4},
        "g3": {"steps": 8192, "analytic_frequency_rel_max": 0.005,
               "fdtd_frequency_rel_max": 0.002, "spectrum_amplitude_db_max": 1.0,
               "energy_rel_max": 0.10, "remaining_gpu_hours_p90_max": 8},
        "p5": {"fixed_indices": [0, 1, 2, 3], "pilot_seed": 20261012,
               "pilot_updates": [200, 500], "loss_reduction_min": 100, "macro_nmae_max": 1e-3,
               "ab_train": 128, "ab_updates": [200, 500], "batch": 4,
               "dev_fig6_seeds": [0, 1, 2], "promotion_seeds": [101, 102, 103],
               "final_seeds": [201, 202, 203], "noncubic_geomean_ratio_max": 0.8,
               "cubic_retention_ratio_max": 1.1, "formal_data_seed": 20261010,
               "formal_dev_seed": 20261011, "formal_epochs": 1000, "formal_lr": 1e-4,
               "formal_effective_batch": 32, "formal_gpu_hours_max": 8},
        "classification": {"exact_yee": "control only; never a DCO score",
                           "paper_MRE": "separate from nMAE; never divided or ranked together"},
    }
    (OUT / "acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "schema": "pidon-r0-v2-audit",
        "created_at_utc": acceptance["frozen_at_utc"], "git_head": git("rev-parse", "HEAD").strip(),
        "branch": git("branch", "--show-current").strip(), "sources_sha256": sources,
        "inputs_sha256": {name: digest(ROOT / name) for name in INPUT_FILES},
        "v1_preserved": (ROOT / "evidence" / "gpt6_plan_v1").is_dir(),
        "historical_status": {"v1_P1": "INCOMPLETE", "v1_P2": "INCOMPLETE",
                                "v1_G1": "NOT_CERTIFIED", "v1_G2_G3": "NOT_RUN"},
    }
    (OUT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = """# R0：v2 协议与证据账本\n\n## 已做\n\n- 已冻结 v2 的数值门槛、几何、时间层、探针、种子、预算和主权重身份，见 `acceptance.json`。\n- 已复制当前相关源码、状态文档、完整工作树 diff 与状态到 `r0_source_snapshot/`；原 `evidence/gpt6_plan_v1/` 未被修改。\n- 已分别记录历史 P1/P2 的 `INCOMPLETE`、G1 的 `NOT_CERTIFIED` 与 G2/G3 的 `NOT_RUN`，不把历史接口冒烟测试写成科学通过。\n\n## 未做\n\n- R1 的停止/恢复和测量合同尚未修复或复测。\n- R2 的生产路径独立 Yee 控制尚未执行。\n- R3 的保存权重指标复算尚未执行。\n\n## 无法从旧资产复算\n\n- v1 P3 没有足以重建固定幅值误差的完整预测与分母资产；待 R4 在修复接口后重测。\n- 历史 64/128 步 JSON 缺完整配置、优化器、RNG、源外探针及检查点链接，只作为历史观察。\n"""
    (OUT / "R0_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"out": str(OUT), "sources": len(sources), "inputs": audit["inputs_sha256"],
                      "v1_preserved": audit["v1_preserved"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
