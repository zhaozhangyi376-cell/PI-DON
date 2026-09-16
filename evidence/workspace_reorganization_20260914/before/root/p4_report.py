"""Generate the P4-A stop-loss report from its raw fixed-state JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="evidence/gpt6_plan_v1/p4a_development_e43/fixed_state_report.json")
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/P4_REPORT.md")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    task = data["tasks"][0]
    baseline, fit = task["baseline"], task["fit"]
    text = f'''# P4-A：固定状态优化止损报告

## 触发条件

P3 的 G1 未通过：第 43 步 curl-E 在独立 FDTD 固定状态上，Adam 500 次后仍为 `R=6.3356466e-4`。按冻结计划只进入分支 A，不允许直接做闭环或再扫学习率。

## 已登记的唯一优化对照

`lab_log` #97 在同一初始 checkpoint、同一目标与同一 lr=`3e-4` 下执行：

| 配置 | Adam 实际更新 | LBFGS 外层步数 / closure | 最终 R | 是否达 `R<1e-4` | 墙钟 |
|---|---:|---:|---:|---|---:|
| 基线 Adam | {baseline['n_updates']} | 0 / 0 | `{baseline['loss_final']:.6e}` | {'是' if baseline['passed'] else '否'} | {baseline['elapsed_s']:.2f} s |
| Adam + LBFGS | {fit['n_updates'] - fit['n_lbfgs_steps']} + {fit['n_lbfgs_steps']} | {fit['n_lbfgs_steps']} / {fit['n_closures']} | `{fit['loss_final']:.6e}` | {'是' if fit['passed'] else '否'} | {fit['elapsed_s']:.2f} s |

LBFGS 降低了相对停止目标，但在登记的 200 closure 和 60 秒/目标限制内没有达到阈值。运行总时长 {data['elapsed_s']:.2f} 秒，未触发资源上限；失败由科学门槛而非资源耗尽决定。

## 判定与停止点

G1 仍失败，且无通过的开发候选，因此不得执行一次性验证状态验收、64 步闭环、P6 128/1024 或 P7 8192。P4-A 已使用计划允许的一次优化修复分支；继续换结构、增加 closure 或改阈值属于计划外变更，必须先制定并确认新方案。

原始 JSON：`p4a_development_e43/fixed_state_report.json`；P3 原始失败状态和 targets 均保留在 `fixed_states/`。
'''
    Path(args.out).write_text(text, encoding="utf-8")
    print(json.dumps({"out": args.out, "passed": fit["passed"], "final_residual": fit["loss_final"],
                      "adam_updates": fit["n_updates"] - fit["n_lbfgs_steps"], "closures": fit["n_closures"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
