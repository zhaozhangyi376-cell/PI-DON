# SR-36E-LOWLR 回传审计

导入目录：`evidence/server_resource_v1/imports/server_step36e_low_lr_return_20260916T021355Z`。

## 结论

- 尝试臂数：`1`
- 最佳交付状态：`PASS`
- 最佳诊断科学状态：`DIAGNOSTIC_PASS_STEP36`
- 来源检查点：`evidence/server_resource_v1/strict64_probe/checkpoint_A.pt`
- 来源已接受步：`35`
- 重放后已接受步：`36`
- 新接受步数：`1`
- 原学习率/诊断学习率：`0.0003` / `0.0001`
- Adam更新：`5350`；closure：`0`
- wall time：`225.4 s`
- 结论边界：lr=1e-4 单步诊断通过：第36步瓶颈主要表现为学习率/优化震荡敏感，不是单纯预算不足，也不是已证明的网络表示硬失败。该结论仍只是一阶诊断，不能改判SR-64，也不能解锁128/1024/8192。

## 各臂汇总

| 臂 | status | scientific | lr | accepted_after | new_steps | Adam | E_R | E_updates | crosses_1e-5 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| step36e_lr1e4_probe | PASS | DIAGNOSTIC_PASS_STEP36 | 0.0001 | 36 | 1 | 5350 | 9.4168727e-06 | 5305 | {'updates': 5305, 'loss': 9.41687267186353e-06} |

## 最佳臂半步拟合

- H：R=`9.9815196e-06`，updates=`45`，target_ss=`0.3900997`，stop=`tol_met`，passed=`True`
- E：R=`9.4168727e-06`，updates=`5305`，target_ss=`77.182281`，stop=`tol_met`，passed=`True`

## 证据

- step36e_lr1e4_probe summary: `evidence/server_resource_v1/imports/server_step36e_low_lr_return_20260916T021355Z/step36e_lr1e4_probe/summary.json`
- step36e_lr1e4_probe steps: `evidence/server_resource_v1/imports/server_step36e_low_lr_return_20260916T021355Z/step36e_lr1e4_probe/steps.jsonl`
- step36e_lr1e4_probe report: `evidence/server_resource_v1/imports/server_step36e_low_lr_return_20260916T021355Z/step36e_lr1e4_probe/REPORT.md`
- step36e_lr1e4_probe manifest: `evidence/server_resource_v1/imports/server_step36e_low_lr_return_20260916T021355Z/step36e_lr1e4_probe/manifest.json`
