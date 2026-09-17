# PAPER01-ABLATION-SMOKE 协议：第一阶段角度/幅值/归一化风险小型消融

## 问题

`PAPER01-S1` 完整 25000 Adam 更新未过第一阶段门；`PAPER01-DIAG` 和 `PAPER01-DATA-AUDIT` 显示失败不太像单纯未收敛，而更像与 Eq.(4) 的近奇异角、Ez幅值放大和未公开归一化/数据定义有关。该行动回答：在短预算下，控制这些因素是否能显著改善第一阶段趋势。

## 变体

固定共同项：32x32x32，1000样本，80/20划分，四级DCO，Adam，lr=1e-4，等效batch32，microbatch8，fresh随机初始化，旧权重不加载。

- `baseline`：R1合同当前实现，`abs(cos(theta))>=0.15`，Ez由Eq.(4)计算。
- `theta_min_0p5`：只提高角度拒绝下限到`abs(cos(theta))>=0.5`，测试远离Eq.(4)奇异角是否改善。
- `ez_cap3`：保持`abs(cos(theta))>=0.15`，但拒绝`max|Ez|/max|Ex,Ey|>3`的样本，测试幅值放大是否是主要风险。
- `projected_amp`：直接投影随机三分量幅值到垂直于k的平面，保持横向但不保留论文Ex/Ey抽样；仅作诊断对照，不能声称忠实论文。

## 预算

- 每变体最多 2000 Adam 更新；四变体总计 8000 Adam。
- 每250更新评估一次测试集；每50更新打印进度。
- 该行动只看短训趋势，不认证第一阶段最终精度。

## 输出

服务器输出目录：`_01/evidence/paper01_ablation_v1/`。

必须保存：

- 根目录 `summary.json`、`REPORT.md`
- 每个变体的 `manifest.json`、`paper_contract.json`、`sample_specs.json`、`variant_contract_stats.json`、`history.jsonl`、`summary.json`、`REPORT.md`、`best.pt`、`last.pt`

## 成功判据

- 四个变体均完成预注册更新数并保存证据。
- 报告列出每变体 best test MSE、macro nMAE、relL2 p90、Eq.(5) MRE和Ez放大统计。
- 若某个变体明显优于baseline，只授权后续独立登记完整第一阶段重训；不改变旧失败，不解锁第二阶段、1024或8192。
