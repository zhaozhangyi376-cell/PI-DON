# SR-48-64-LOWLR 回传审计

导入目录：`evidence/server_resource_v1/imports/server_step48_64_return_20260916T035641Z`。

## 结论

- 交付状态：`PASS`
- 诊断科学状态：`DIAGNOSTIC_PASS_WINDOW`
- 来源检查点：`evidence/server_resource_v1/step36_48_low_lr_window/checkpoint_A.pt`
- 来源已接受步：`48`
- 重放后已接受步：`64`
- 新接受步数：`16`
- 目标接受步：`64`
- 学习率：`0.0001`；max_inner：`60000`
- Adam更新：`61895`；closure：`0`
- wall time：`2802 s`
- 结论边界：48→64低学习率局部窗口通过，且step64 Q低于5%。这支持登记从0开始的低学习率64验证；但本结果仍是混合历史局部诊断，不改判原SR-64，也不解锁128/1024/8192。

## 最后一步

`{'accepted_steps': 64, 'H_R': 9.876616571634345e-06, 'H_updates': 1868, 'E_R': 9.966365073453417e-06, 'E_updates': 1588, 'Q': 0.03055066251511019, 'fixed_amplitude_error': 1.0198271708717376e-05}`

## 每步摘要

`[{'accepted_steps': 49, 'H_R': 9.986310330931644e-06, 'H_updates': 215, 'E_R': 9.819248792883502e-06, 'E_updates': 4131, 'Q': 0.002885807172255453, 'fixed_amplitude_error': 7.173045444577016e-06}, {'accepted_steps': 50, 'H_R': 9.974404027165636e-06, 'H_updates': 248, 'E_R': 9.997576351190387e-06, 'E_updates': 4292, 'Q': 0.0034674307105934964, 'fixed_amplitude_error': 7.613044031297131e-06}, {'accepted_steps': 51, 'H_R': 9.981871924194687e-06, 'H_updates': 259, 'E_R': 9.995340990871568e-06, 'E_updates': 3935, 'Q': 0.004240961886976381, 'fixed_amplitude_error': 8.074565682658364e-06}, {'accepted_steps': 52, 'H_R': 9.98406861246211e-06, 'H_updates': 267, 'E_R': 9.931593544311255e-06, 'E_updates': 3970, 'Q': 0.005226484284637935, 'fixed_amplitude_error': 8.477658919849404e-06}, {'accepted_steps': 53, 'H_R': 9.988160280547017e-06, 'H_updates': 291, 'E_R': 9.959569169195735e-06, 'E_updates': 3469, 'Q': 0.006539757786701937, 'fixed_amplitude_error': 8.890039179993913e-06}, {'accepted_steps': 54, 'H_R': 9.985763102405904e-06, 'H_updates': 344, 'E_R': 9.849185673698828e-06, 'E_updates': 2912, 'Q': 0.00819186681208982, 'fixed_amplitude_error': 9.200853562129983e-06}, {'accepted_steps': 55, 'H_R': 9.999262090452328e-06, 'H_updates': 433, 'E_R': 9.259499224734398e-06, 'E_updates': 2892, 'Q': 0.01028937214744912, 'fixed_amplitude_error': 9.449320654781784e-06}, {'accepted_steps': 56, 'H_R': 9.987946834548873e-06, 'H_updates': 542, 'E_R': 9.978919303339184e-06, 'E_updates': 2559, 'Q': 0.012906678221302849, 'fixed_amplitude_error': 9.650153633484175e-06}, {'accepted_steps': 57, 'H_R': 9.973503263342255e-06, 'H_updates': 697, 'E_R': 9.914570596859665e-06, 'E_updates': 2694, 'Q': 0.016081566051836017, 'fixed_amplitude_error': 9.83952482823378e-06}, {'accepted_steps': 58, 'H_R': 9.993158878788939e-06, 'H_updates': 992, 'E_R': 9.920953993196162e-06, 'E_updates': 2677, 'Q': 0.019549717177585215, 'fixed_amplitude_error': 9.9617583353988e-06}, {'accepted_steps': 59, 'H_R': 9.989653083037576e-06, 'H_updates': 1339, 'E_R': 9.993984480451375e-06, 'E_updates': 2673, 'Q': 0.022980534282918352, 'fixed_amplitude_error': 1.0053586951724027e-05}, {'accepted_steps': 60, 'H_R': 9.997565209422613e-06, 'H_updates': 1695, 'E_R': 9.999113148848049e-06, 'E_updates': 2677, 'Q': 0.02599603231989113, 'fixed_amplitude_error': 1.0148231818905447e-05}, {'accepted_steps': 61, 'H_R': 9.990353753120983e-06, 'H_updates': 1880, 'E_R': 9.922830300050349e-06, 'E_updates': 2476, 'Q': 0.028108953231209176, 'fixed_amplitude_error': 1.0172118729411409e-05}, {'accepted_steps': 62, 'H_R': 9.963891001967183e-06, 'H_updates': 2024, 'E_R': 9.999442244913538e-06, 'E_updates': 2114, 'Q': 0.029441165840974618, 'fixed_amplitude_error': 1.0183104592388086e-05}, {'accepted_steps': 63, 'H_R': 9.975794432901159e-06, 'H_updates': 1949, 'E_R': 9.985745090609408e-06, 'E_updates': 1793, 'Q': 0.030223856718311338, 'fixed_amplitude_error': 1.0203045058500498e-05}, {'accepted_steps': 64, 'H_R': 9.876616571634345e-06, 'H_updates': 1868, 'E_R': 9.966365073453417e-06, 'E_updates': 1588, 'Q': 0.03055066251511019, 'fixed_amplitude_error': 1.0198271708717376e-05}]`

## 证据

- summary: `evidence/server_resource_v1/imports/server_step48_64_return_20260916T035641Z/step48_64_low_lr_window/summary.json`
- steps: `evidence/server_resource_v1/imports/server_step48_64_return_20260916T035641Z/step48_64_low_lr_window/steps.jsonl`
- report: `evidence/server_resource_v1/imports/server_step48_64_return_20260916T035641Z/step48_64_low_lr_window/REPORT.md`
- manifest: `evidence/server_resource_v1/imports/server_step48_64_return_20260916T035641Z/step48_64_low_lr_window/manifest.json`
- checkpoint pointer: `evidence/server_resource_v1/imports/server_step48_64_return_20260916T035641Z/step48_64_low_lr_window/checkpoint_pointer.json`
