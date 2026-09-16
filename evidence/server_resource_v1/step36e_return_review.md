# SR-36E-BUDGET 回传审计

导入目录：`evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z`。

## 结论

- 交付状态：`FAIL`
- 诊断科学状态：`DIAGNOSTIC_FAIL_STEP36`
- 来源运行：`evidence/server_resource_v1/strict64_probe`
- 来源检查点：`evidence/server_resource_v1/strict64_probe/checkpoint_A.pt`
- 来源已接受步：`35`
- 重放后已接受步：`35`
- 新接受步数：`0`
- Adam更新：`30056`；closure：`0`
- wall time：`1245 s`
- 结论边界：第36步在30000 Adam半步预算下仍未通过；下一步应分析loss曲线、目标能量和表示能力，不应继续盲目扩大64步。

## 半步拟合

- H：R=`9.9883297e-06`，updates=`56`，target_ss=`0.3900997`，stop=`tol_met`，passed=`True`
- E：R=`3.3681379e-05`，updates=`30000`，target_ss=`77.094154`，stop=`max_updates`，passed=`False`
- E crosses 1e-4：`{'updates': 290, 'loss': 9.630664135329425e-05}`
- E crosses 1e-5：`None`

## 证据

- summary: `evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z/step36e_budget_probe/summary.json`
- steps: `evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z/step36e_budget_probe/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z/step36e_budget_probe/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z/step36e_budget_probe/manifest.json`
- checkpoint pointer: `evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z/step36e_budget_probe/checkpoint_pointer.json`
- failure raw: `evidence/server_resource_v1/imports/server_step36e_return_20260916T015804Z/step36e_budget_probe/failure_raw_000001_attempt_1.pt`
