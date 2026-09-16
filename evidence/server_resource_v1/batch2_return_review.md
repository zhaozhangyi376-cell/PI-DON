# SR-SHORT-R2 回传审计

导入目录：`evidence/server_resource_v1/imports/server_batch2_return_r2_full_20260915T141612Z`。

## 结论

- 交付状态：`FAIL`
- 科学状态：`FAIL`
- 接受完整时间步：`0`
- Adam更新：`3000`；closure：`0`
- 恢复资格：`False`
- 停止原因：`FIT_FAIL`

解释：`tol=1e-5` 在第一完整时间步前即失败，不能进入64/128，也不能解锁1024/8192。这否定的是“简单收紧单步残差门即可救场”这条工程路线，不改判旧G128失败。

## 首个/停止行

- row accepted: `False`；phase: `E_pending`；reason: `max_updates`
- H fit: `{'n_updates': 0, 'n_evals': 0, 'loss_initial': 0.0, 'loss_final': 0.0, 'residual_ratio': None, 'passed': True, 'stop_reason': 'zero_input', 'elapsed_s': 0.05539249999856111}`
- E fit: `{'n_updates': 3000, 'n_evals': 6001, 'loss_initial': 50.69289779663086, 'loss_final': 1.6351405065506697e-05, 'residual_ratio': 1.635140577517076e-05, 'passed': False, 'stop_reason': 'max_updates', 'elapsed_s': 124.38060829999449}`
- row cost: `{'adam': 3000, 'closures': 0, 'lbfgs_steps': 0}`

## 证据

- summary: `evidence/server_resource_v1/imports/server_batch2_return_r2_full_20260915T141612Z/short_tol_probe_r2/summary.json`
- steps: `evidence/server_resource_v1/imports/server_batch2_return_r2_full_20260915T141612Z/short_tol_probe_r2/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_batch2_return_r2_full_20260915T141612Z/short_tol_probe_r2/REPORT.md`

## 后续建议

停止继续容差收紧或长程运行。下一步应只读审计失败现场和旧M2第57-58步场门越线机制，优先检查边界/插入预测/弱参考/场门定义，而不是再开并行训练。
