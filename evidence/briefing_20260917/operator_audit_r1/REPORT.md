# 固定权重旋度算子汇报审计

- 交付状态：`PASS_WITH_DECLARED_S1R_VISUAL_LIMIT`；科学含义：`DIAGNOSTIC_ONLY`
- 参数更新：`0`；lab run：`300`
- 解析旋度和Yee目标只作参考，不计DCO成绩。

## 可视化对象

| 模型 | 平面波图 | 首个非零E输入图 | 权重状态 |
|---|---|---|---|
| old_lr1e3 | PASS_ZERO_UPDATE | PASS_ZERO_UPDATE | LOCAL_HASH_VERIFIED |
| random_seed_2026091704 | PASS_ZERO_UPDATE | PASS_ZERO_UPDATE_SEED_20260913 | EPHEMERAL_FIXED_SEED |
| S1R_best | SERVER_METRICS_ONLY | NOT_AVAILABLE_WEIGHT_NOT_LOCAL | SERVER_ONLY_HASH_958a9764 |

## 解释

- `old_lr1e3`和固定种子随机网络的图由本次零更新前向产生。
- S1R服务器分数来自已回传SR-COMPARE；本地缺少S1R权重时不伪造场图。
- Fig.5公开了网格、角度和k序列，但没有公开20组Ex/Ey振幅；本图将振幅明确标为固定种子假设。
- 首个非零E输入是当前腔体配方的硬源尖锐输入，只用于诊断平面波预训练到在线输入的迁移。
