# PAPER01-DATA-AUDIT 协议：第一阶段数据/公式合同只读审计

## 问题

`PAPER01-DIAG` 显示 `PAPER01-S1` 失败主要集中在 curl-z、靠近 Eq.(4) 奇异角下限的样本和幅值/尺度因素。该行动只回答：当前独立第一阶段参考线的数据构造是否满足横向平面波条件，以及 Eq.(4) 的 Ez 放大、分量尺度和归一化后目标支撑是否解释失败方向。

## 输入

- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/sample_specs.json`
- 同目录 `summary.json` 或 `manifest.json`
- `evidence/paper01_s1/failure_diagnosis_v1/per_sample.csv`

## 冻结规则

- 0 参数更新，不加载或修改 checkpoint。
- 使用 `sample_specs.json` 重算保留 200 个测试样本的平面波、解析 curl 和归一化目标。
- 检查 `k dot E0` 横向性、Ez放大比、curl分量尺度、归一化后 active support，并与上一轮 per-sample 误差关联。
- 不改变 `PAPER01-S1`、`PAPER01-DIAG` 或任何旧第二阶段失败判定。

## 输出

新证据目录：`evidence/paper01_s1/data_contract_audit_v1/`。

必须保存：

- `summary.json`
- `per_sample_contract.csv`
- `REPORT.md`
- `z_error_vs_angle.png`
- `z_error_vs_support.png`
- `ez_amplification_hist.png`

## 成功判据

- 输出覆盖 200 个保留样本。
- 报告列出横向条件残差、Ez放大、z/xy尺度比、归一化后分量支撑和角度分组。
- 若证据指向某个高风险实现假设，只能作为后续独立小型消融的依据，不能直接修改旧门槛或重判旧失败。
