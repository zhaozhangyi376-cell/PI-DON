# SR-64-LOWLR-CLEAN 回传审计

导入目录：`evidence/server_resource_v1/imports/server_clean_low_lr64_return_20260916T061148Z`。

## 结论

- 交付状态：`PASS`
- 科学状态：`PASS_64`
- 接受完整时间步：`64` / target `64`
- Adam更新：`178204`；closure：`0`
- wall time：`7543 s`
- 64步field gate：`True`
- Q/global relL2：`0.0293402`
- fixed amplitude error：`9.79421e-06`
- 结论边界：clean low-lr64 从0到64通过，且64步场门PASS。可以登记clean low-lr128；仍不能直接启动1024/8192。

## 最后一步

`{'accepted_steps': 64, 'H_R': 9.97744910784805e-06, 'H_updates': 1336, 'E_R': 9.906138511514005e-06, 'E_updates': 1603, 'Q': 0.0293402364347697, 'fixed_amplitude_error': 9.794213235532885e-06}`

| 分量 | nMAE | absMAE | weak | gate依据 | relL2 |
|---|---:|---:|---|---|---:|
| Ex | 0.001393 | 7.165e-06 | False | nMAE<=1% | 0.06374 |
| Ey | 0.00143 | 7.358e-06 | False | nMAE<=1% | 0.06737 |
| Ez | 0.001942 | 7.656e-06 | False | nMAE<=1% | 0.02197 |
| Hx | 0.001383 | 5.025e-06 | False | nMAE<=1% | 0.01821 |
| Hy | 0.001333 | 4.844e-06 | False | nMAE<=1% | 0.01736 |
| Hz | 8.112e+10 | 4.483e-06 | True | weak_abs | 5.117e+12 |

## 探针

- 源点Ez：`{'dut': 0.017165089026093483, 'ref': 0.01716508950750685}`
- 源外探针：`[{'cells': [12.0, 12.0, 13.0], 'xyz_m': [0.01935483870967742, 0.01935483870967742, 0.020967741935483872], 'dut_Ez': 0.0008925652073230595, 'ref_Ez': 0.0008793217130005361}, {'cells': [8.0, 10.0, 12.0], 'xyz_m': [0.012903225806451613, 0.016129032258064516, 0.01935483870967742], 'dut_Ez': -0.000784828356700018, 'ref_Ez': -0.0007896035676822066}, {'cells': [21.0, 19.0, 18.0], 'xyz_m': [0.03387096774193549, 0.03064516129032258, 0.02903225806451613], 'dut_Ez': -8.548483310733127e-05, 'ref_Ez': -8.021298162930316e-05}]`

## 证据

- summary: `evidence/server_resource_v1/imports/server_clean_low_lr64_return_20260916T061148Z/clean_low_lr64/summary.json`
- steps: `evidence/server_resource_v1/imports/server_clean_low_lr64_return_20260916T061148Z/clean_low_lr64/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_clean_low_lr64_return_20260916T061148Z/clean_low_lr64/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_clean_low_lr64_return_20260916T061148Z/clean_low_lr64/manifest.json`
- snapshot64: `evidence/server_resource_v1/imports/server_clean_low_lr64_return_20260916T061148Z/clean_low_lr64/snapshot_step_0064.pt`
