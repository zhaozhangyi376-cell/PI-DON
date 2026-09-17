# `_01`: 论文显式第一阶段参考线

这里是独立的第一阶段 DCO 训练实现。它不读取主项目的旧权重、旧优化器或失败现场。

`paper_contract.json` 把每个关键选择分成三类：

- `EXPLICIT`：论文明确写出；
- `DERIVED`：由论文公式直接推导；
- `ASSUMED`：作者代码缺失时必须冻结的实现假设。

因此这条线的准确表述是“论文显式配置参考复现”，不是“与作者未公开代码逐行一致”。

## 本机预检

```powershell
py -3.11 .\_01\train_phase1.py preflight --output .\_01\evidence\preflight_cpu --device cpu
```

## 完整训练

完整训练固定为 32^3、1000 样本、四层、Adam、学习率 1e-4、batch 32、1000 epoch
等价的 25000 次参数更新。训练过程使用 microbatch 仅用于显存分块，梯度累积后每次仍是
有效 batch 32。输出包含 `best.pt`、`last.pt`、`summary.json`、`audit.json` 和逐更新日志。
