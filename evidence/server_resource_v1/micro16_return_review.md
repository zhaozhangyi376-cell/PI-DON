# SR-MICRO16 回传审计

导入目录：`evidence/server_resource_v1/imports/server_micro16_return_20260915T154708Z`。

## 结论

- 交付状态：`PASS`
- 科学状态：`PASS_MICRO`（16步微型门；不是64/128门）
- 接受完整时间步：`16` / target `16`
- Adam更新：`13791`；closure：`0`
- wall time：`713.5 s`
- 第16步全局Q：`0.00300618`；固定源幅误差：`1.25085e-08`
- micro field gate：`True`；64/128 field gate：`None` / `None`

解释：这证明当前严格方案可从4步扩展到16步，并且第16步微型场门通过。它仍不是64/128轨迹认证，也不能启动1024/8192；下一步最多登记32或64步有界验证。

## 第16步半步拟合

- H residual：`9.6299442e-06`，updates `59`，target_ss `7.1128297e-06`
- E residual：`9.7872686e-06`，updates `66`，target_ss `0.22840366`

## 六分量和探针

| 分量 | nMAE | absMAE | weak | gate依据 | relL2 |
|---|---:|---:|---|---|---:|
| Ex | 9.985e-06 | 3.913e-09 | False | nMAE<=1% | 0.002563 |
| Ey | 8.02e-06 | 3.143e-09 | False | nMAE<=1% | 0.002747 |
| Ez | 1.337e-05 | 3.73e-09 | False | nMAE<=1% | 0.00363 |
| Hx | 7.421e-06 | 3.937e-09 | False | nMAE<=1% | 0.00281 |
| Hy | 7.139e-06 | 3.788e-09 | False | nMAE<=1% | 0.002555 |
| Hz | 6.542e+11 | 3.78e-09 | True | weak_abs | 6.881e+13 |

- 源点Ez：dut=`0.00137064`，ref=`0.00137064`
- 源外探针：`(12.0, 12.0, 13.0): dut=2.718e-07, ref=3.068e-07; (8.0, 10.0, 12.0): dut=4.592e-09, ref=8.352e-10; (21.0, 19.0, 18.0): dut=3.17e-09, ref=1.259e-08`

## 每步更新数

`[{'step': 1, 'H': 0, 'E': 3925}, {'step': 2, 'H': 3289, 'E': 1414}, {'step': 3, 'H': 455, 'E': 798}, {'step': 4, 'H': 315, 'E': 382}, {'step': 5, 'H': 404, 'E': 236}, {'step': 6, 'H': 376, 'E': 217}, {'step': 7, 'H': 259, 'E': 217}, {'step': 8, 'H': 169, 'E': 141}, {'step': 9, 'H': 117, 'E': 133}, {'step': 10, 'H': 73, 'E': 93}, {'step': 11, 'H': 68, 'E': 77}, {'step': 12, 'H': 65, 'E': 67}, {'step': 13, 'H': 64, 'E': 64}, {'step': 14, 'H': 63, 'E': 62}, {'step': 15, 'H': 59, 'E': 64}, {'step': 16, 'H': 59, 'E': 66}]`

## 证据

- summary: `evidence/server_resource_v1/imports/server_micro16_return_20260915T154708Z/micro16_strict_probe/summary.json`
- steps: `evidence/server_resource_v1/imports/server_micro16_return_20260915T154708Z/micro16_strict_probe/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_micro16_return_20260915T154708Z/micro16_strict_probe/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_micro16_return_20260915T154708Z/micro16_strict_probe/manifest.json`
- protocol in manifest: `docs/plans/2026-09-15-server-micro16-protocol.md`
