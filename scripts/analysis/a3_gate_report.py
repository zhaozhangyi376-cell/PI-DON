"""Machine gate and Chinese report for the single A3 h-layout candidate."""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
from pathlib import Path

from pidon_recording import sha256_file


ROOT = PROJECT_ROOT
OUT = ROOT / "evidence" / "gpt6_plan_v3" / "h_layout_candidate"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-run", type=int, required=True)
    args = parser.parse_args()
    development_path, readback_path = OUT / "A3_development.json", OUT / "A3_readback.json"
    dev = json.loads(development_path.read_text(encoding="utf-8"))
    readback = json.loads(readback_path.read_text(encoding="utf-8"))
    rows, complete = [], True
    for task in dev["tasks"]:
        if task.get("status") == "NOT_RUN":
            complete = False
            continue
        h, e = task["fit_H"], task.get("fit_E")
        oracle = task.get("oracle_E", {}).get("fit")
        legacy = task["legacy_H500_baseline"]
        e_elapsed = (e or oracle)["elapsed_s"]
        cost_pass = h["elapsed_s"] + e_elapsed <= 2 * (legacy["elapsed_s"] + e_elapsed)
        accepted_metrics = task.get("accepted_field_metrics") or {}
        row = {"step": task["step"], "H_R": h["residual_ratio"], "H_pass": h["passed"],
               "H_updates": h["n_updates"], "E_mode": "sequential" if e else "oracle_only",
               "E_R": (e or oracle)["residual_ratio"], "E_pass": (e or oracle)["passed"],
               "E_updates": (e or oracle)["n_updates"], "A_fixed":
               accepted_metrics.get("fixed_amplitude_error"),
               "old_H_R": legacy["residual_ratio"], "H_improvement_fraction":
               1 - h["residual_ratio"] / legacy["residual_ratio"], "cost_pass": cost_pass,
               "accepted_field_metrics": task.get("accepted_field_metrics"),
               "source_outside_probes": task.get("source_outside_probes"),
               "recovery_eligible": task["recovery_eligible"]}
        row["sequential_gate_pass"] = (row["H_pass"] and e is not None and e["passed"] and
                                       row["A_fixed"] is not None and row["A_fixed"] <= 1e-3 and cost_pass)
        complete = complete and row["sequential_gate_pass"]
        rows.append(row)
    result = {
        "schema": "pidon-a3-gate-v3", "lab_log_run": args.lab_run,
        "G1_development": "PASS" if complete else "FAIL",
        "G1_validation": "NOT_RUN" if not complete else "PENDING",
        "scientific_stop": not complete,
        "reason": "registered h_shift candidate missed the unchanged R<1e-4 development gate; no permitted candidate remains",
        "tasks": rows, "readback": {"all_pass": readback["all_pass"], "sha256": sha256_file(readback_path)},
        "evidence": {"development": sha256_file(development_path)},
        "downstream": {"64": "NOT_RUN", "128": "NOT_RUN", "1024": "NOT_RUN", "8192": "NOT_RUN",
                       "P5": "NOT_RUN"},
    }
    (OUT / "A3_GATE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# A3：唯一 H 位置候选报告", "", f"- lab_log：#{args.lab_run}",
             f"- 开发门：**{result['G1_development']}**", "- 固定验证与 64→128→1024→8192：**NOT_RUN**", "",
             "本次只改变 H 输入的 Yee 交错索引，保持原始权重、网络、学习率、种子、500 次更新和 360 秒上限。精确几何核不作为 DCO 成绩。", "",
             "| 固定状态 | H R | H 是否通过 | E 诊断 | E R | E 是否通过 | H 相对旧输入改善 | 完整步/六分量/探针 |", "|---:|---:|---|---|---:|---|---:|---|"]
    for row in rows:
        lines.append(f"| {row['step']} | {row['H_R']:.9g} | {row['H_pass']} | {row['E_mode']} | "
                     f"{row['E_R']:.9g} | {row['E_pass']} | {row['H_improvement_fraction']:.2%} | "
                     "N/A（停在 before_H，无接受的完整物理步） |")
    lines += ["", f"保存权重从磁盘纯推理复算：`{readback['all_pass']}`。两项 H 都实际完成 500 次 Adam、0 次 LBFGS；失败 raw、网络、优化器、目标与预测均已保留。", "",
              "43 步和 96 步均未达到 R<1e-4，因而不能生成顺序 E，也不能进入固定验证。按已登记规则，oracle E 仅诊断，不能替代 Algorithm 1 的顺序 E 或 G1。没有改变门槛、追加学习率或重跑 P4-A。"]
    (OUT / "A3_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT / "A3_GATE.json"), "G1_development": result["G1_development"],
                      "scientific_stop": result["scientific_stop"]}, ensure_ascii=False))
    if complete:
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
