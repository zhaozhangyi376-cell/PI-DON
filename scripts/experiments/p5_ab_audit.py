"""Append the declared P5 A/B decision to the stage report."""

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", default="evidence/gpt6_plan_v1/phase1_pilot_corrected/learnability.json")
    parser.add_argument("--ab", default="evidence/gpt6_plan_v1/phase1_ab_pilot/ab_pilot.json")
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/P5_REPORT.md")
    args = parser.parse_args()
    pilot = json.loads(Path(args.pilot).read_text(encoding="utf-8"))
    ab = json.loads(Path(args.ab).read_text(encoding="utf-8"))
    rows = {r["variant"]: r for r in ab["records"]}
    a, b = rows["A_relative"], rows["B_component_localmax"]
    text = f'''# P5：第一阶段诊断与配对小试止损报告

## 固定样本可学习性

四个固定 32³ 训练样本经过真实 {pilot['actual_updates']} 次 Adam 更新，优化器计数已核对。相对平方损失下降 `{pilot['loss_reduction']:.1f}×`，但宏 nMAE 为 `{pilot['history'][-1]['macro_nmae']:.6e}`，未达预登记 `≤1e-3`。解析标签与 Yee 位置回归另行通过。

## 已登记的唯一因素 A/B

按后续授权，只测试一个因素：按训练真值各分量局部最大值加权的物理量损失。A/B 使用相同随机初始状态、相同 128 个训练样本、相同 200 个 batch 序列以及相同 32 个未更新开发样本。

| 方案 | 实际更新 | 开发宏 nMAE：训练前 | 开发宏 nMAE：训练后 |
|---|---:|---:|---:|
| A：原相对损失 | {a['actual_updates']} | {a['dev_macro_nmae_before']:.6e} | {a['dev_macro_nmae_after']:.6e} |
| B：分量局部最大值加权 | {b['actual_updates']} | {b['dev_macro_nmae_before']:.6e} | {b['dev_macro_nmae_after']:.6e} |

B 的开发误差高于 A，未显示继续到 500 次或进入非立方验收的依据。该结果只否定本次声明的损失重建方向，不能证明论文作者未使用任何输出归一化方式。

## 停止点

P5 的可学习性门槛和唯一 A/B 小试均未给出可提升为候选的方案。因此不执行 1000 epoch 长训；P3/P4 也没有通过候选，P6/P7/P8 的前置 G1/G2 不成立。原始权重、两个 P5 目录及首次计数错误的失败目录均保留。
'''
    Path(args.out).write_text(text, encoding="utf-8")
    print(json.dumps({"out": args.out, "A": a["dev_macro_nmae_after"], "B": b["dev_macro_nmae_after"],
                      "same_initial_state": ab["same_initial_state"], "decision": "stop"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
