# SR-128-LOWLR-CLEAN 回传审计

导入目录：`evidence/server_resource_v1/imports/server_clean_low_lr128_return_20260916T092721Z`。

## 结论

- 交付状态：`PASS`
- 科学状态：`FAIL`（128步门；不是1024/8192门）
- 接受完整时间步：`128` / target `128`
- Adam更新：`261209`；closure：`0`
- wall time：`1.107e+04 s`
- 64步field gate：`True`
- 128步field gate：`False`
- 结论边界：clean low-lr128 未通过或未完成；停止该分支，不启动1024/8192。

## 里程碑检查

- 第57步：`{'accepted_steps': 57, 'Q': 0.015361771911156674, 'component_failures': [], 'fixed_amplitude_error': 9.3991179489782e-06}`
- 第58步：`{'accepted_steps': 58, 'Q': 0.018541958901504126, 'component_failures': [], 'fixed_amplitude_error': 9.44824479882814e-06}`
- 第64步：`{'accepted_steps': 64, 'Q': 0.029045755311563313, 'component_failures': [], 'fixed_amplitude_error': 9.695910997207885e-06}`
- 第66步：`{'accepted_steps': 66, 'Q': 0.028922430601080688, 'component_failures': [], 'fixed_amplitude_error': 9.633202743165544e-06}`
- 第96步：`{'accepted_steps': 96, 'Q': 0.030086389069452258, 'component_failures': [], 'fixed_amplitude_error': 1.0026817478430634e-05}`
- 第128步：`{'accepted_steps': 128, 'Q': 0.030811310290015343, 'component_failures': ['Ex: nMAE=0.015486016672334027', 'Ey: nMAE=0.016307587903172226'], 'fixed_amplitude_error': 1.0419708821532546e-05}`
- 首次Q>5%：`None`
- 首次分量门失败：`{'accepted_steps': 69, 'Q': 0.02882556161545619, 'component_failures': ['Ex: nMAE=0.012205131252395625', 'Ey: nMAE=0.012830577276928892'], 'fixed_amplitude_error': 9.709008356435442e-06}`

## 最后/停止步半步拟合

- H residual：`9.9935791e-06`，updates `242`，target_ss `0.0050278199`
- E residual：`9.9778766e-06`，updates `558`，target_ss `413.77896`

## 六分量和探针

| 分量 | nMAE | absMAE | weak | gate依据 | relL2 |
|---|---:|---:|---|---|---:|
| Ex | 0.01549 | 7.574e-06 | False | nMAE<=1% | 0.08843 |
| Ey | 0.01631 | 7.975e-06 | False | nMAE<=1% | 0.09447 |
| Ez | 0.004709 | 8.297e-06 | False | nMAE<=1% | 0.03289 |
| Hx | 0.00391 | 6.008e-06 | False | nMAE<=1% | 0.016 |
| Hy | 0.003722 | 5.72e-06 | False | nMAE<=1% | 0.01527 |
| Hz | 9.068e+10 | 5.196e-06 | True | weak_abs | 5.773e+12 |

- 源点Ez：dut=`2.04171e-29`，ref=`2.04171e-29`
- 源外探针：`(12.0, 12.0, 13.0): dut=1.325e-05, ref=2.17e-05; (8.0, 10.0, 12.0): dut=0.0002096, ref=0.0002116; (21.0, 19.0, 18.0): dut=5.698e-05, ref=2.826e-05`

## 证据

- summary: `evidence/server_resource_v1/imports/server_clean_low_lr128_return_20260916T092721Z/clean_low_lr128/summary.json`
- steps: `evidence/server_resource_v1/imports/server_clean_low_lr128_return_20260916T092721Z/clean_low_lr128/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_clean_low_lr128_return_20260916T092721Z/clean_low_lr128/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_clean_low_lr128_return_20260916T092721Z/clean_low_lr128/manifest.json`
- protocol in manifest: `docs/plans/2026-09-16-clean-low-lr-128-protocol.md`
