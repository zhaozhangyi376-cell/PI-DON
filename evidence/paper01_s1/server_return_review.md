# PAPER01-S1 服务器回传审计

- 原始回传SHA256：`23bdeb4d87d69ec7b10ea4aff69c9c7420a747fcfbdf1b892be3a2366fcc833a`
- 不可变导入目录：`evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z`
- 工程完整性：`PASS`
- 科学判定：`FAIL_REGISTERED_S1_GATES`
- 声明：这是论文显式配置参考线，不宣称作者源码逐位同一。

## 训练合同

- history行数/末更新：`25000` / `25000`
- 缺失文件：`[]`

| 完整性检查 | 结果 |
|---|---|
| summary_schema | True |
| manifest_schema | True |
| contract_schema | True |
| mode_train | True |
| complete_25000_updates | True |
| history_complete | True |
| constant_lr_1e4 | True |
| paper_scale_config | True |
| fresh_random_initialization | True |
| contract_matches_local | True |
| best_checkpoint_hash | True |
| last_checkpoint_hash | True |
| sample_specs_1000 | True |

## 第一阶段结果

- best normalized test MSE：`0.02659477601448695`（update `25000`）
- final normalized test MSE：`0.02659477601448695`
- 开发集宏nMAE：`0.09233404946513474`
- relL2 p90：`0.5790284514427184`
- Eq.(5) MRE均值：`2.0180368006477756`
- 训练墙钟：`8663.259723099996` 秒

| 登记门槛 | 结果 |
|---|---|
| macro_nmae_le_1pct | False |
| rel_l2_p90_le_5pct | False |
| every_sample_macro_nmae_le_1pct | False |

## 解释边界

该审计只回答独立第一阶段参考线是否按冻结合同执行，以及固定测试集指标是否过登记门。它不自动证明第二阶段预训练收益，也不解锁1024/8192。Eq.(5) MRE、nMAE和relL2继续分栏，不能互相替代。

## 原始证据

- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/manifest.json`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/paper_contract.json`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/sample_specs.json`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/history.jsonl`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/summary.json`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/audit.json`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/REPORT.md`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/best.pt`
- `evidence/paper01_s1/imports/server_paper01_return_20260917T015828Z/_01/evidence/paper01_s1_v1/last.pt`
