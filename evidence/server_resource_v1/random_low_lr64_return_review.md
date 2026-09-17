# SR-64-LOWLR-RANDOM 回传审计

导入目录：`evidence/server_resource_v1/imports/server_random_low_lr64_return_20260916T130417Z`。

## 结论

- 交付状态：`PASS`
- 科学状态：`PASS_64`（诊断项，不改判clean128）
- 接受完整时间步：`64` / target `64`
- Adam更新：`84881`；closure：`0`
- wall time：`3636.8 s`
- 64步field gate：`True`
- 64步Q：`0.0293162`

解释：随机初始化在同样 `lr=1e-4`、`tol=1e-5`、64步场门下通过，并且成本低于预训练clean64。该结果不支持此配方下的预训练成本收益，但不自动否定第一阶段DCO本身；需要保留为收益对照证据。

## 里程碑

- 第32步：`{'accepted_steps': 32, 'Q': 0.0020200934398294343, 'component_failures': [], 'fixed_amplitude_error': 2.277736858133983e-06}`
- 第64步：`{'accepted_steps': 64, 'Q': 0.029316190579668024, 'component_failures': [], 'fixed_amplitude_error': 9.78618636660086e-06}`
- 第128步：`None`
- 首次Q>5%：`None`
- 首次分量门失败：`None`

## 最后接受步半步拟合

- H residual：`9.9490819e-06`，updates `831`
- E residual：`9.9837592e-06`，updates `1394`

## 六分量和探针

| 分量 | nMAE | absMAE | relL2 | weak |
|---|---:|---:|---:|---|
| Ex | 0.0015862 | 8.1611e-06 | 0.06428 | False |
| Ey | 0.0016048 | 8.2565e-06 | 0.064379 | False |
| Ez | 0.002079 | 8.1954e-06 | 0.020778 | False |
| Hx | 0.0015469 | 5.6223e-06 | 0.020074 | False |
| Hy | 0.0014648 | 5.324e-06 | 0.018841 | False |
| Hz | 9.2482e+10 | 5.1113e-06 | 5.7172e+12 | True |

- 源点Ez：dut=`0.0171651`，ref=`0.0171651`
- 源外探针：`(12.0, 12.0, 13.0): dut=0.00087863, ref=0.00087932; (8.0, 10.0, 12.0): dut=-0.00078705, ref=-0.0007896; (21.0, 19.0, 18.0): dut=-8.227e-05, ref=-8.0213e-05`

## 证据

- summary: `evidence/server_resource_v1/imports/server_random_low_lr64_return_20260916T130417Z/random_low_lr64/summary.json`
- steps: `evidence/server_resource_v1/imports/server_random_low_lr64_return_20260916T130417Z/random_low_lr64/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_random_low_lr64_return_20260916T130417Z/random_low_lr64/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_random_low_lr64_return_20260916T130417Z/random_low_lr64/manifest.json`
