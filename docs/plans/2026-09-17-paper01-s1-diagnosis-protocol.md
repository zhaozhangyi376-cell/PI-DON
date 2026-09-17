# PAPER01-DIAG 协议：第一阶段失败原因只读分解

## 问题

`PAPER01-S1` 已按冻结合同完成 25000 Adam 更新，但登记第一阶段精度门失败。该行动只回答：失败更像训练未收敛，还是由样本族、分量、波数/网格尺度、角度/幅值、归一化或接口定义差异造成。

## 冻结输入

- 读取 `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/`。
- 使用该目录的 `best.pt`、`sample_specs.json`、`history.jsonl`、`paper_contract.json`。
- 测试集固定为训练脚本合同中的后 20% 样本，即索引 800 到 999。
- 不加载旧DCO权重，不训练，不改checkpoint，不改登记门槛。

## 输出

新证据目录：`evidence/paper01_s1/failure_diagnosis_v1/`。

必须包含：

- `summary.json`：总体诊断摘要、哈希、趋势和分组结论。
- `per_sample.csv`：每个测试样本的分量误差、波数/角度/幅值/尺度特征。
- `REPORT.md`：中文报告，明确哪些结论支持训练未收敛，哪些支持定义/数据/归一化差异。
- `history_curve.png`：25000更新验证误差曲线。
- `component_error_box.png`：三分量误差分布图。

## 判读边界

- 该行动是 0 参数更新诊断，不改变 `PAPER01-S1` 科学判定。
- 不能用本诊断结果启动第二阶段、1024或8192。
- 不能把 nMAE、relL2、Eq.(5) MRE 混为同一指标。
- 如果脚本失败，保留现场并标记 INCOMPLETE；不得重跑训练补证。
