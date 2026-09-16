# SR-36-48-LOWLR 回传审计

导入目录：`evidence/server_resource_v1/imports/server_step36_window_return_20260916T030320Z`。

## 结论

- 交付状态：`PASS`
- 诊断科学状态：`DIAGNOSTIC_PASS_WINDOW`
- 来源检查点：`evidence/server_resource_v1/strict64_probe/checkpoint_A.pt`
- 来源已接受步：`35`
- 重放后已接受步：`48`
- 新接受步数：`13`
- 目标接受步：`48`
- 学习率：`0.0001`；max_inner：`60000`
- Adam更新：`51977`；closure：`0`
- wall time：`2181 s`
- 结论边界：35→48低学习率局部窗口通过，说明第36步低学习率修复能连续维持一小段；但这是从SR-64第35步检查点出发的混合历史诊断，不改判SR-64，也不解锁128/1024/8192。

## 最后一步

`{'accepted_steps': 48, 'H_R': 9.97965731239344e-06, 'H_updates': 174, 'E_R': 9.81473445184969e-06, 'E_updates': 3710, 'Q': 0.0024659362923624495, 'fixed_amplitude_error': 6.809539915707566e-06}`

| 分量 | nMAE | absMAE | weak | relL2 |
|---|---:|---:|---|---:|
| Ex | 1.269e-05 | 4.173e-06 | False | 0.00201 |
| Ey | 1.297e-05 | 4.267e-06 | False | 0.002043 |
| Ez | 1.373e-05 | 4.216e-06 | False | 0.00248 |
| Hx | 4.27e-05 | 3.206e-06 | False | 0.006206 |
| Hy | 4.337e-05 | 3.256e-06 | False | 0.006383 |
| Hz | 5.619e+10 | 2.944e-06 | True | 4.22e+12 |

## 每步摘要

`[{'accepted_steps': 36, 'H_R': 9.981617495696145e-06, 'H_updates': 45, 'E_R': 9.701848720616284e-06, 'E_updates': 4606, 'Q': 0.0020660947454358043, 'fixed_amplitude_error': 4.566163895181654e-06}, {'accepted_steps': 37, 'H_R': 9.987629206389329e-06, 'H_updates': 98, 'E_R': 9.900977046516127e-06, 'E_updates': 3413, 'Q': 0.001990944285536629, 'fixed_amplitude_error': 4.971596767909715e-06}, {'accepted_steps': 38, 'H_R': 9.999282952198671e-06, 'H_updates': 141, 'E_R': 9.823170968581146e-06, 'E_updates': 1948, 'Q': 0.001923529531277261, 'fixed_amplitude_error': 5.32723752012574e-06}, {'accepted_steps': 39, 'H_R': 9.9818215762268e-06, 'H_updates': 249, 'E_R': 9.943166161807894e-06, 'E_updates': 2077, 'Q': 0.001863229598815639, 'fixed_amplitude_error': 5.617395450417062e-06}, {'accepted_steps': 40, 'H_R': 9.988193686622667e-06, 'H_updates': 482, 'E_R': 9.351183652209255e-06, 'E_updates': 2177, 'Q': 0.0018031031803384286, 'fixed_amplitude_error': 5.807912114950363e-06}, {'accepted_steps': 41, 'H_R': 9.9785578326382e-06, 'H_updates': 886, 'E_R': 9.726922269752306e-06, 'E_updates': 2165, 'Q': 0.0017596475157028752, 'fixed_amplitude_error': 5.942740680165925e-06}, {'accepted_steps': 42, 'H_R': 9.99144085423296e-06, 'H_updates': 1690, 'E_R': 9.900423443651689e-06, 'E_updates': 2454, 'Q': 0.0017286844556657342, 'fixed_amplitude_error': 6.006675296890131e-06}, {'accepted_steps': 43, 'H_R': 9.960170334635261e-06, 'H_updates': 4352, 'E_R': 9.696393383481732e-06, 'E_updates': 2546, 'Q': 0.0017205863754632328, 'fixed_amplitude_error': 6.03550263001094e-06}, {'accepted_steps': 44, 'H_R': 9.993249680106821e-06, 'H_updates': 5138, 'E_R': 9.858352005077714e-06, 'E_updates': 2740, 'Q': 0.0017407251268260527, 'fixed_amplitude_error': 6.048038289269512e-06}, {'accepted_steps': 45, 'H_R': 9.97783141931469e-06, 'H_updates': 875, 'E_R': 9.691000281888796e-06, 'E_updates': 2908, 'Q': 0.001818534263390988, 'fixed_amplitude_error': 6.1397927368644335e-06}, {'accepted_steps': 46, 'H_R': 9.995104543769919e-06, 'H_updates': 376, 'E_R': 9.962622564098119e-06, 'E_updates': 3286, 'Q': 0.0019597846033799146, 'fixed_amplitude_error': 6.307655884634447e-06}, {'accepted_steps': 47, 'H_R': 9.876696616354795e-06, 'H_updates': 220, 'E_R': 9.89956710848107e-06, 'E_updates': 3221, 'Q': 0.002162011238018062, 'fixed_amplitude_error': 6.50751874729558e-06}, {'accepted_steps': 48, 'H_R': 9.97965731239344e-06, 'H_updates': 174, 'E_R': 9.81473445184969e-06, 'E_updates': 3710, 'Q': 0.0024659362923624495, 'fixed_amplitude_error': 6.809539915707566e-06}]`

## 证据

- summary: `evidence/server_resource_v1/imports/server_step36_window_return_20260916T030320Z/step36_48_low_lr_window/summary.json`
- steps: `evidence/server_resource_v1/imports/server_step36_window_return_20260916T030320Z/step36_48_low_lr_window/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_step36_window_return_20260916T030320Z/step36_48_low_lr_window/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_step36_window_return_20260916T030320Z/step36_48_low_lr_window/manifest.json`
- checkpoint pointer: `evidence/server_resource_v1/imports/server_step36_window_return_20260916T030320Z/step36_48_low_lr_window/checkpoint_pointer.json`
