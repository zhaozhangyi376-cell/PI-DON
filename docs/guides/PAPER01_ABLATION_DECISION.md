# PAPER01-ABLATION-SMOKE 回传后决策表

用途：服务器四臂短预算消融完成后，用同一套证据决定下一步。该表只用于第一阶段 DCO 诊断，不改变 `PAPER01-S1` 的科学 FAIL，不解锁第二阶段、1024 或 8192。

## 先导入

```powershell
Set-Location C:\PI-DON
py -3.11 run.py ingest_paper01_ablation_return .\server_paper01_ablation_return.zip
py -3.11 run.py project_harness check
```

审计报告：

```text
C:\PI-DON\evidence\paper01_s1\paper01_ablation_return_review.md
C:\PI-DON\evidence\paper01_s1\paper01_ablation_return_review.json
```

重点看三个字段：

- `baseline.macro_nmae_mean`
- `best_macro_nmae_variant.variant`
- `best_vs_baseline_macro_nmae_ratio`
- `recommendation.code`

## 决策表

| 回传现象 | 解释 | 下一步 |
|---|---|---|
| `status != PASS` 或四臂不全 | 服务器任务或证据不完整 | 保留现场；不重跑同一 action，不补旧预算；先看缺哪个文件/哪一臂中断 |
| `best=baseline` 或 `best/baseline >= 0.9` | 角度/Ez/幅值消融没有明显信号 | 原样完整重训优先级低；下一步应复核网络结构、输入坐标、目标归一化与论文未公开细节 |
| `best=theta_min_0p5` 且 `best/baseline <= 0.8` | 远离 Eq.(4) 近奇异角显著改善 | 可登记一个完整第一阶段重训，只改角度拒绝条件；仍需单独盲测，不进入第二阶段 |
| `best=ez_cap3` 且 `best/baseline <= 0.8` | Ez 幅值放大是主要风险 | 可登记一个完整第一阶段重训，只加入 Ez 放大上限；仍需说明这是工程过滤，不等同论文原文 |
| `best=projected_amp` | 诊断性正交投影最好 | 说明幅值/极化生成方式可能是关键，但它不是论文 Eq.(4) 字面复现；先用于解释失败，不直接作为论文复现配置 |
| 有改善但 `0.8 < best/baseline < 0.9` | 信号弱，短预算下不稳 | 先登记稍长但仍有界的消融复核，不直接完整重训 |

## 汇报口径

这轮要回答的问题不是“PI-DON 是否已经复现”，而是：

1. 完全按论文显式第一阶段配置训练为什么没有达到论文效果？
2. 失败是否更像训练没跑够，还是数据/公式/归一化未公开细节导致？
3. 后续完整重训是否有明确方向，而不是盲目重训？

可以用的结论只来自回传审计：

- 如果受控过滤显著优于 baseline：说明 `PAPER01-S1` 失败不是简单“GPU不够/训练不够”，更可能和 Eq.(4) 近奇异角或 Ez 幅值尺度有关。
- 如果所有变体都差不多：说明当前短证据不支持继续围绕角度/Ez 猜测，优先检查网络实现、坐标输入、归一化和论文缺失训练细节。
- 如果 `projected_amp` 最好：说明“横向平面波”本身没问题，但论文 Eq.(4) 的幅值构造路径可能在数值上更难学；该证据是诊断，不是复现成功。
