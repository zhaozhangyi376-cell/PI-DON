"""Create the immutable registry for the bounded mechanism/value experiment.

This intentionally records a *new* protocol.  It never changes historical
G0/G1 decisions, checkpoints, or their budgets.
"""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import torch

from pidon_recording import atomic_json_save, sha256_file, source_hashes


ROOT = PROJECT_ROOT
OUT = ROOT / "evidence" / "mechanism_decision_v1"
PLAN = ROOT / "docs" / "superpowers" / "plans" / "2026-09-14-pidon-mechanism-decision-plan.md"
MASTER = ROOT / "dco_lr1e3_300.pt"
SOURCE_FILES = (
    "dco.py", "fdtd.py", "gen_data.py", "pidon_contract.py", "pidon_recording.py",
    "pidon_solve.py", "mechanism_decision_init.py", "mechanism_path_check.py",
    "mechanism_decision_eval.py", "mechanism_decision_runner.py",
)


def digest(path: Path) -> str:
    value = sha256_file(path)
    if value is None:
        raise FileNotFoundError(path)
    return value


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                   encoding="utf-8", errors="replace").strip()


def write_exclusive_json(path: Path, data: dict) -> None:
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to replace existing experiment evidence: {OUT}")
    if not PLAN.is_file() or not MASTER.is_file():
        raise FileNotFoundError("plan or registered master checkpoint is absent")
    OUT.mkdir(parents=True)
    try:
        snapshot = OUT / "source_snapshot"
        snapshot.mkdir()
        source_digest = {}
        for name in SOURCE_FILES:
            src = ROOT / name
            if not src.is_file():
                raise FileNotFoundError(src)
            dst = snapshot / name
            shutil.copy2(src, dst)
            source_digest[name] = digest(dst)
        now = datetime.now(timezone.utc)
        config_common = {
            "n": 31, "side": 0.05, "dt": 3.075e-12, "tol": 1e-4,
            "tol_mode": "rel", "max_inner": 500, "lr": 3e-4,
            "levels": 4, "base": 32, "coords": "cellsize", "norm": "rms",
            "separate_nets": True, "reset_opt_each_step": False, "grad_clip": 0.0,
            "h_scale": 1.0, "component_rel": False, "h_output_scale": 1.0,
            "h_shift": True, "strict_stop": True, "inner_time_budget_s": 360.0,
            "fmax": 15e9, "lbfgs_closures": 0, "lbfgs_lr": 1.0,
            "lbfgs_history": 10, "lbfgs_time_budget_s": 0.0, "torch_dtype": "float32",
            "source_mode": "hard", "head_lstsq_once": False, "head_rcond": 1e-12,
            "seed": 20260914,
        }
        protocol = {
            "schema": "pidon-mechanism-decision-v1",
            "experiment_id": str(uuid.uuid4()),
            "created_at_utc": now.isoformat(),
            "training_deadline_utc": (now + timedelta(hours=9, minutes=30)).isoformat(),
            "deadline_utc": (now + timedelta(hours=10)).isoformat(),
            "plan": {"path": str(PLAN.relative_to(ROOT)), "sha256": digest(PLAN)},
            "master": {"path": MASTER.name, "sha256": digest(MASTER)},
            "source_hashes": source_hashes(ROOT),
            "source_snapshot_hashes": source_digest,
            "git": {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
                    "dirty": bool(git("status", "--porcelain"))},
            "resource_baseline": {
                "disk_free_bytes": shutil.disk_usage(ROOT).free,
                "python": sys.version, "torch": torch.__version__, "platform": platform.platform(),
                "cuda": bool(torch.cuda.is_available()),
                "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            },
            "common_config": config_common,
            "arms": {
                "P": {"init": MASTER.name, "seed": 20260914, "purpose": "pretrained"},
                "R": {"init": "random", "seed": 20260914, "purpose": "random_initialization"},
            },
            "gates": {
                "per_nonzero_fit": {"residual_ratio_lt": 1e-4, "adam_updates_le": 500,
                                     "elapsed_s_le": 360.0},
                "short_checkpoints": [64, 128],
                "S2": {"steps": 1024, "Q_le": 0.05, "component_nmae_le": 0.01,
                       "source_outside_waveform_error_le": 0.05, "A_fixed_le": 1e-3},
                "B": {"relative_online_time_and_updates_reduction_ge": 0.20,
                      "random_seeds_required": 2},
            },
            "prohibitions": [
                "No old failure checkpoint resumes for new budget.",
                "No head least-squares, LBFGS, learning-rate, scale, or architecture sweep.",
                "Exact Yee controls are interface controls, never DCO results.",
                "MRE Eq.5 and nMAE are reported in distinct columns.",
            ],
            "status": {"step1": "IN_PROGRESS", "S1": "NOT_RUN", "P": "NOT_RUN", "R": "NOT_RUN",
                       "S2": "NOT_RUN", "B": "NOT_RUN", "U": "NOT_RUN", "S3": "NOT_RUN"},
        }
        write_exclusive_json(OUT / "protocol.json", protocol)
        (OUT / "git_status_at_start.txt").write_text(git("status", "--short") + "\n", encoding="utf-8")
        (OUT / "working_tree_at_start.diff").write_text(git("diff") + "\n", encoding="utf-8")
        assumptions = """# 本次机制验证：已知事实与待澄清项

| 主题 | 论文明确文字 | 本次实现 | 仍未确认 |
|---|---|---|---|
| 式(7) | 每步以物理损失训练curl，损失低于1e-4停止 | 标准Yee三分量、物理总相对SSE R<1e-4 | 作者的sum/mean/归一化细节及印刷x分量符号是否为笔误 |
| trunk输入 | E/H坐标输入以提供cell size | 以毫米节点坐标编码cell spacing | 是否与作者的“coordinates”编码完全相同 |
| 第一阶段输出归一化 | 各分量local maximum | 输入RMS与长度尺度的可逆归一化 | 作者如何在未知测试场恢复local maximum |
| H/E网络 | 同时处理三分量 | 独立H/E网络与Adam状态 | 作者是否共享参数/优化器 |
| 训练后评估 | 论文报告evaluation stage和后续应用 | 本轮将最终H/E冻结作为一个明确、待检验的解释 | 作者实际使用最终、时间索引或其他权重的方式 |

本表不将当前实现选择写成论文已证实事实。未执行分支保持 NOT_RUN。
"""
        (OUT / "ASSUMPTIONS.md").write_text(assumptions, encoding="utf-8")
        print(json.dumps({"out": str(OUT), "experiment_id": protocol["experiment_id"],
                          "master_sha256": protocol["master"]["sha256"],
                          "disk_free_bytes": protocol["resource_baseline"]["disk_free_bytes"]}, ensure_ascii=False))
    except Exception:
        # Preserve a partly created failure scene, rather than silently deleting it.
        raise


if __name__ == "__main__":
    main()
