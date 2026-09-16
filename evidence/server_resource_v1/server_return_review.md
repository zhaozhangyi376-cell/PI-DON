# 服务器首批证据回传审阅

导入目录：`evidence/server_resource_v1/imports/server_resource_return_20260915T100510Z`。

## 结论

- SR-COMPARE 交付状态：PASS；科学结论：NOT_APPLICABLE
- SR-PERF 交付状态：PASS；推荐 microbatch：8
- 这两项都是诊断/工程证据，不解锁1024/8192，也不把旧G128失败改判。

## S1R完整性

- audit status：PASS
- 1000_continuous_epochs: True
- 25_updates_each_epoch: True
- best.pt_updates: True
- best_dev_selection: True
- lab_exit_0_and_action: True
- lab_hash_best.pt: True
- lab_hash_last.pt: True
- lab_hash_summary.json: True
- last.pt_updates: True
- one_matching_lab_run: True
- stage_matches_summary: True
- summary_matches_audit: True
- summary_terminal_counts: True

## 三模型同题诊断

| 模型 | 网格 | 状态 | global nMAE | 宏nMAE | relL2 p90 | Eq5 MRE | 逐样本<=1% |
|---|---|---:|---:|---:|---:|---:|---:|
| old_paper32 | 32x32x32 | PASS | 0.00539559 | 0.0279652 | 0.0298348 | 0.428018 | 5 |
| old_paper32 | 64x64x64 | PASS | 0.0174475 | 0.0855062 | 0.110824 | 0.943569 | 3 |
| old_paper32 | 64x96x16 | PASS | 0.0572106 | 0.186225 | 0.377448 | 2.59664 | 0 |
| old_paper32 | 32x64x16 | PASS | 0.0394843 | 0.125688 | 0.276105 | 2.9271 | 0 |
| old_lr1e3 | 32x32x32 | PASS | 0.00353488 | 0.0201746 | 0.0176107 | 0.218256 | 8 |
| old_lr1e3 | 64x64x64 | PASS | 0.0147434 | 0.0736002 | 0.105912 | 0.803288 | 4 |
| old_lr1e3 | 64x96x16 | PASS | 0.041979 | 0.166037 | 0.266033 | 1.94848 | 0 |
| old_lr1e3 | 32x64x16 | PASS | 0.0240208 | 0.0939176 | 0.204939 | 3.17959 | 0 |
| S1R_best | 32x32x32 | PASS | 0.00748285 | 0.0415034 | 0.0441235 | 1.05325 | 1 |
| S1R_best | 64x64x64 | PASS | 0.0240143 | 0.114413 | 0.131491 | 1.47737 | 0 |
| S1R_best | 64x96x16 | PASS | 0.0690174 | 0.231327 | 0.444001 | 3.32787 | 0 |
| S1R_best | 32x64x16 | PASS | 0.0507339 | 0.177718 | 0.371 | 4.00441 | 0 |

## GV100吞吐诊断

| microbatch | 状态 | 已提交更新 | 中位计时更新(s) | peak allocated GiB | 一步等价 |
|---:|---:|---:|---:|---:|---:|
| 4 | PASS | 5 | 0.416733 | 0.511 | True |
| 8 | PASS | 5 | 0.315584 | 0.872 | True |
| 16 | PASS | 5 | 0.341889 | 1.598 | True |

## 后续动作

SR-DESIGN现在可以进入只读设计阶段：基于上述指标只冻结一个S1干预和一个在线干预。在新协议冻结前，不启动新的长训练；即便之后SR-SHORT通过128，也必须按首次更新前登记的累计预算进入长程。

原始服务器证据保存在导入目录；本报告只做本地索引和摘要，不修改服务器原始记录。
