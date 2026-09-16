"""Create machine-readable A1 contract evidence from the production tests."""

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
import unittest
from pathlib import Path

import torch

from pidon_recording import sha256_file, source_hashes


ROOT = PROJECT_ROOT
OUT = ROOT / "evidence" / "gpt6_plan_v3"
MODULES = ("test_pidon_contract", "test_pidon_contract_v3", "test_stop_review_claims")


class CollectingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append({"test": test.id(), "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows.append({"test": test.id(), "status": "FAIL", "detail": self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.rows.append({"test": test.id(), "status": "ERROR", "detail": self._exc_info_to_string(err, test)})


def p4a_diagnostic_assets():
    directory = ROOT / "evidence" / "gpt6_plan_v2" / "R4_p4a_step0043"
    rows = []
    for path in sorted(directory.glob("*.pt")):
        state = torch.load(path, map_location="cpu", weights_only=False)
        rows.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(path),
            "classification": "diagnostic_only_not_resumable_v3",
            "fit_progress": state.get("fit_progress"),
            "has_lbfgs_H": state.get("lbfgs_H") is not None,
            "has_recorder_identity": "recorder_identity" in state,
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-run", type=int, required=True)
    args = parser.parse_args()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(MODULES)
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CollectingResult)
    result = runner.run(suite)
    rows = sorted(result.rows, key=lambda row: row["test"])
    document = {
        "schema": "pidon-a1-contract-v3",
        "lab_log_run": args.lab_run,
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "observed": {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)},
        "expected": {"failures": 0, "errors": 0},
        "tests": rows,
        "source_hashes": source_hashes(ROOT),
        "v2_p4a_assets": p4a_diagnostic_assets(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "contract_test_results.json"
    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = f"""# A1 工程合同修复报告

本报告由机器运行测试生成，不能作为 DCO 收敛或 G0 通过的替代证据。

- lab_log：#{args.lab_run}
- 测试：{result.testsRun} 项；失败 {len(result.failures)} 项；错误 {len(result.errors)} 项
- 结论：**{document['status']}**（仅 A1 工程合同）

已覆盖累计时间预算、LBFGS 配置冻结、运行身份、Adam/LBFGS 完整调用边界的中断恢复、E_pending 事务、非有限 raw/safe、原子检查点、写入失败及 JSONL 未提交尾部分类。每个测试的 observed/expected 及源码哈希在 `contract_test_results.json`。

v2 的 `adam200_final.pt` 与 `adam200_lbfgs_final.pt` 保留不改；两者均标记为 `diagnostic_only_not_resumable_v3`，不会作为 v3 恢复入口或重新领取优化预算。
"""
    (OUT / "A1_REPORT.md").write_text(report, encoding="utf-8")
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
