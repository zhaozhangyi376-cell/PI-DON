# SR-MICRO4 回传审计

导入目录：`evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z`。

## 结论

- 交付状态：`PASS`
- 科学状态：`PASS_MICRO`（4步微型门；不是64/128门）
- 接受完整时间步：`4` / target `4`
- Adam更新：`10558`；closure：`0`
- wall time：`448.3 s`
- 第4步全局Q：`0.00291609`；固定源幅误差：`9.032e-12`
- micro field gate：`True`；64/128 field gate：`None` / `None`

解释：这证明更高半步预算能支撑4个完整严格步，并且第4步微型场门通过。它仍不是64/128轨迹认证，也不能启动1024/8192；下一步最多登记8到16步小实验。

## 第4步半步拟合

- H residual：`9.9994294e-06`，updates `312`，target_ss `4.4820454e-12`
- E residual：`9.9532724e-06`，updates `376`，target_ss `2.9313571e-07`

## 六分量和探针

| 分量 | nMAE | absolute MAE | weak | weak_abs_pass | relL2 |
|---|---:|---:|---|---|---:|
| Ex | 1.485e-05 | 3.413e-12 | True | True | 0.003038 |
| Ey | 1.375e-05 | 3.161e-12 | True | True | 0.003045 |
| Ez | 2.207e-05 | 3.47e-12 | True | True | 0.003525 |
| Hx | 8.71e-06 | 4.298e-12 | True | True | 0.002421 |
| Hy | 7.86e-06 | 3.878e-12 | True | True | 0.002242 |
| Hz | UNKNOWN | 3.45e-12 | True | True | UNKNOWN |

- 源点Ez：dut=`1.02563e-06`，ref=`1.02563e-06`
- 源外探针：`(12.0, 12.0, 13.0): dut=-1.815e-12, ref=0; (8.0, 10.0, 12.0): dut=-1.447e-12, ref=0; (21.0, 19.0, 18.0): dut=6.645e-12, ref=0`

## 每步成本

`[{'accepted_steps': 1, 'H': 0, 'E': 3830, 'wall_s': 160.11022480000975}, {'accepted_steps': 2, 'H': 3351, 'E': 1456, 'wall_s': 362.34119619999547}, {'accepted_steps': 3, 'H': 413, 'E': 820, 'wall_s': 415.6636596000171}, {'accepted_steps': 4, 'H': 312, 'E': 376, 'wall_s': 446.3821816999989}]`

## 记录注意

- action协议：`docs/plans/2026-09-15-server-micro4-protocol.md`
- manifest内部protocol：`docs/plans/2026-09-15-server-batch2-protocol.md`
复用短程探针入口导致manifest保留旧batch2协议名；本次科学身份以harness action、finish证据和本报告列出的micro4协议为准。后续包会修正脚本protocol参数。

## 证据

- summary: `evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z/micro4_strict_probe/summary.json`
- steps: `evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z/micro4_strict_probe/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z/micro4_strict_probe/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z/micro4_strict_probe/manifest.json`
- checkpoint A/B: `evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z/micro4_strict_probe/checkpoint_A.pt`, `evidence/server_resource_v1/imports/server_micro4_return_20260915T152352Z/micro4_strict_probe/checkpoint_B.pt`
