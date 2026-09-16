"""Audit the P5 learnability pilot without re-training it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="evidence/gpt6_plan_v1/phase1_pilot_corrected")
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/P5_REPORT.md")
    args = parser.parse_args()
    root = Path(args.dir)
    data = json.loads((root / "learnability.json").read_text(encoding="utf-8"))
    checkpoint = torch.load(root / "learnability_checkpoint.pt", map_location="cpu", weights_only=False)
    steps = []
    for state in checkpoint["optimizer"]["state"].values():
        value = state.get("step")
        steps.append(int(value.item()) if hasattr(value, "item") else int(value))
    final = data["history"][-1]
    passed = data["passed"] and min(steps) == max(steps) == data["actual_updates"]
    text = f'''# P5：第一阶段可学习性止损报告

## 已登记检查

在 `data_32.npz` 的固定样本 `[0,1,2,3]` 上，以 seed `20261012`、RMS 输入归一化和 cellsize 坐标，从随机 L4/base32 网络训练。先运行 200 次，未达到门槛后才扩展至累计 500 次。

第一次目录 `phase1_pilot/` 保留为失败证据：它在 200 次后错误登记为 500 次，因此不可用于科学判读。修复计数后，使用独立目录 `phase1_pilot_corrected/` 重跑。

| 指标 | 修正后结果 | 门槛 |
|---|---:|---:|
| 实际 Adam 更新 | {data['actual_updates']}（优化器所有状态步数 {min(steps)}–{max(steps)}） | 500 上限 |
| 相对平方损失下降 | {data['loss_reduction']:.2f}× | ≥100× |
| 最终宏 nMAE | {final['macro_nmae']:.6e} | ≤1e-3 |

## 判定

**未通过。** 虽然损失下降远超 100 倍、优化器步数与记录一致，宏 nMAE 仍为 `{final['macro_nmae']:.6e}`。这不是“没有梯度”或更新计数错误；Yee 标签/位置的解析回归由 `test_paper_protocol.py` 单独覆盖。

按 P5 的预登记顺序，不启动 128 样本 A/B、1000 epoch 长训，也不改用测试集调参。下一步若继续，必须先提出能解释该固定样本误差的标签、归一化或表达诊断方案。
'''
    Path(args.out).write_text(text, encoding="utf-8")
    print(json.dumps({"out": args.out, "actual_updates": data["actual_updates"],
                      "optimizer_step_range": [min(steps), max(steps)], "passed": passed,
                      "macro_nmae": final["macro_nmae"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
