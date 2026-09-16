# SR-E1-BUDGET 回传审计

导入目录：`evidence/server_resource_v1/imports/server_first_e_return_20260915T145629Z`。

## 结论

- 交付状态：`PASS`
- 科学状态：`DIAGNOSTIC_PASS`（诊断通过，不是连续轨迹通过）
- 接受完整时间步：`1`
- Adam更新：`3769`；closure：`0`
- wall time：`159.7 s`
- 首个E残差比：`9.9723174e-06`
- 1e-4过门：`1220` Adam；1e-5过门：`3769` Adam
- long_run_unlocked：`False`；恢复资格：`False`

解释：同一个首个 `E_pending` 目标在3000 Adam时未过 `1e-5`，但在9000上限内于3769 Adam过门。这说明第一处严格失败至少包含预算/优化收敛速度问题；它不说明后续H/E半步、场传播或64/128门已经合格。

## 首个E拟合

- 初始loss：`50.692898`
- 最终loss：`9.9723175e-06`
- target_ss：`1.9472424e-08`；target_count：`89373`
- stop_reason：`tol_met`；n_evals：`7539`

## 场与探针（仅第1步诊断）

- 六分量：`Ex: nMAE=UNKNOWN, absMAE=0, Ey: nMAE=UNKNOWN, absMAE=0, Ez: nMAE=UNKNOWN, absMAE=0, Hx: nMAE=1.257e-05, absMAE=8.084e-13, Hy: nMAE=1.148e-05, absMAE=7.384e-13, Hz: nMAE=UNKNOWN, absMAE=7.406e-13`
- global_weighted_relative_l2：`0.00313121`
- 源点Ez：dut=`1.12535e-07`，ref=`1.12535e-07`
- 源外探针：`(12.0, 12.0, 13.0): dut=0, ref=0; (8.0, 10.0, 12.0): dut=0, ref=0; (21.0, 19.0, 18.0): dut=0, ref=0`

## 证据

- summary: `evidence/server_resource_v1/imports/server_first_e_return_20260915T145629Z/first_e_budget_probe/summary.json`
- report: `evidence/server_resource_v1/imports/server_first_e_return_20260915T145629Z/first_e_budget_probe/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_first_e_return_20260915T145629Z/first_e_budget_probe/manifest.json`
- checkpoint: `evidence/server_resource_v1/imports/server_first_e_return_20260915T145629Z/first_e_budget_probe/checkpoint_A.pt`
- snapshot: `evidence/server_resource_v1/imports/server_first_e_return_20260915T145629Z/first_e_budget_probe/snapshot_step_0001.pt`

## 后续建议

下一步最多登记一个极小连续严格推进：同一旧lr1e3初始化、tol=1e-5、每半步9000 Adam上限，只跑2到4个完整步并复算全场/源外探针。若2到4步失败，停止该分支；若通过，再单独登记8到16步，仍不直接启动64/128/1024/8192。
