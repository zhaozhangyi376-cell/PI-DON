# SR-128-PAPER-TOL-DIAG 回传审计

导入目录：`evidence/server_resource_v1/imports/server_paper_tol128_return_20260916T114443Z`。

## 结论

- 交付状态：`FAIL`
- 科学状态：`FAIL`（诊断项，不改判clean128）
- 接受完整时间步：`64` / target `128`
- Adam更新：`66173`；closure：`0`
- wall time：`2872 s`
- 64步field gate：`False`
- 64步Q：`0.0904105`

解释：`tol=1e-4` 在当前低学习率配置下可以完成64个残差接受步，但64步全场门失败，Q约为9.04%，高于5%。这支持当前实现不能直接按论文式残差阈值延长；`1e-5`严格门虽然慢，但对场误差有实际约束作用。

## 里程碑

- 第32步：`{'accepted_steps': 32, 'Q': 0.006102152545362393, 'component_failures': [], 'fixed_amplitude_error': 6.88042319849402e-06}`
- 第64步：`{'accepted_steps': 64, 'Q': 0.09041050330077748, 'component_failures': ['Hz: weak_abs_fail'], 'fixed_amplitude_error': 3.0180388969541545e-05}`
- 第128步：`None`
- 首次Q>5%：`{'accepted_steps': 58, 'Q': 0.057512467996446416, 'component_failures': ['Hz: weak_abs_fail'], 'fixed_amplitude_error': 2.9306066284674744e-05}`
- 首次分量门失败：`{'accepted_steps': 54, 'Q': 0.023439451314290257, 'component_failures': ['Hz: weak_abs_fail'], 'fixed_amplitude_error': 2.6326472837812437e-05}`

## 最后接受步半步拟合

- H residual：`9.9623924e-05`，updates `754`
- E residual：`9.931627e-05`，updates `542`

## 六分量和探针

| 分量 | nMAE | absMAE | relL2 | weak |
|---|---:|---:|---:|---|
| Ex | 0.0039571 | 2.0359e-05 | 0.20066 | False |
| Ey | 0.0039985 | 2.0572e-05 | 0.20164 | False |
| Ez | 0.0054157 | 2.1348e-05 | 0.064902 | False |
| Hx | 0.004298 | 1.5622e-05 | 0.058343 | False |
| Hy | 0.0042741 | 1.5535e-05 | 0.057764 | False |
| Hz | 2.5934e+11 | 1.4333e-05 | 1.6709e+13 | True |

- 源点Ez：dut=`0.0171651`，ref=`0.0171651`
- 源外探针：`(12.0, 12.0, 13.0): dut=0.00090603, ref=0.00087932; (8.0, 10.0, 12.0): dut=-0.00075684, ref=-0.0007896; (21.0, 19.0, 18.0): dut=-7.3511e-05, ref=-8.0213e-05`

## 证据

- summary: `evidence/server_resource_v1/imports/server_paper_tol128_return_20260916T114443Z/paper_tol128_diag/summary.json`
- steps: `evidence/server_resource_v1/imports/server_paper_tol128_return_20260916T114443Z/paper_tol128_diag/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_paper_tol128_return_20260916T114443Z/paper_tol128_diag/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_paper_tol128_return_20260916T114443Z/paper_tol128_diag/manifest.json`
