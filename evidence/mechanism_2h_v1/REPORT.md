# 2小时有界机制推进报告

## 状态总表

| 项目 | 分栏 | 状态 | 接受步 | 实际更新 | H/E残差 | 耗时(s) | 恢复资格 |
|---|---|---|---:|---:|---|---:|---|
| S-P-retry | strict-old | RESOURCE_LIMIT | 6 | 10447 | 9.9874e-5 / 9.9936e-5 | 758.9 | True |
| S-R | strict-old | FAIL | 33 | 10070 | 9.94307e-05 / 0.000125044 | 775.8 | False |
| X-R | explore-old | FAIL | 41 | 13764 | 9.6488e-4 / 9.9944e-4 accepted; next E 1.6029 | 1045.7 | False |
| D-LR old | diagnostic-old | INCOMPLETE | 1 | 657 | N/A / 9.9733e-5 | 48.2 | False |
| D-LR4-retry | diagnostic-strict-new | FAIL | 1 | 4074 | N/A / 347.608 | 344.1 | False |
| S-P continuation | strict-new | NOT_RUN | 0 | 0 | N/A | N/A | N/A |
| strict 64/128 | strict-new | NOT_RUN | 0 | 0 | N/A | N/A | N/A |

严格阈值仍为 `R < 1e-4`。探索阈值 `R < 1e-3` 的 X-R 只作诊断，不计严格成绩。

## 只读审计结论

- `manifest.json` 顶层 `updates_this_experiment=0`，但逐臂审计合计为 `34939`；本轮不使用顶层字段作科学结论。
- `S-P-retry` 是 `RESOURCE_LIMIT`，不是 PASS；`S-R` 是严格 FAIL 但保留 33 个接受步；`X-R` 是探索 FAIL；`D-LR` 是 INCOMPLETE。
- 上一轮 `steps.jsonl`、checkpoint 指针、stage_status 和 lab_log #248-#260 对得上；S-R 与 S-P-retry 的失败/恢复现场均保留。

## S-R失败点剖析

- 第 34 个候选停在 `E_pending`，失败原因为 `max_updates`；H 半步已过，H R=`9.9361e-05`。
- 真正卡住的是 E：3000 次更新后 E R=`0.000125044`，目标 `1e-4` 未达，target_ss=`254.716`，耗时 `218.585` 秒。
- 前一完整步六分量 nMAE：Ex `2.8713e-5`，Ey `2.8549e-5`，Ez `3.6378e-5`，Hx `6.3903e-5`，Hy `5.6943e-5`，Hz 为弱参考 `3.8940e12`，应单列。
- 因为最后完整步的源点/源外探针仍已落盘，且无阈值违规，当前更支持“E内层拟合在该状态触顶/变慢”，不是接口记录把 FAIL 算错，也不是整体场已经失控。

## D-LR极小补证

- 新臂 `D_LR4_retry` 只接受 1/4 步。第 1 步 E 用 650 更新到 `9.97449e-05`，随后第 2 候选停在 `E_pending`。
- 第 2 候选 H 已通过，E 在 `240.073` 秒内做 `2920` 次更新后，R=`347.608`，远高于 `1e-4`。
- 因此高学习率不是可直接连续通过 2 到 4 个完整严格步的补救；这个结果是诊断 FAIL，不是论文有效性证明。
- #261 和 #262 的 Python exit 1 是显示/诊断层空值处理问题；#262 的科学停止行、failure_raw 和 checkpoint 已在崩溃前落盘。

## 可用于论文方法判断

- 可用：严格臂 S-R 曾连续接受 33 步，说明 Algorithm 1 式逐步重训在短程不是完全不可行。
- 可用：S-R 第 34 候选和 D-LR4 第 2 候选都指向 E 半步内层拟合瓶颈；简单提高学习率没有给出连续严格步证据。
- 仅工程/诊断：manifest 顶层更新数字修正、显示层 None 修复、checkpoint 恢复资格审计、X-R 宽阈值推进。
- 不能用于论文成功判断：X-R 的 41 步、精确 Yee 控制、D-LR 首步或本轮 D-LR4 的单步接受。

## 进入64/128资格

没有资格。本轮没有任何严格新分支稳定达到 32 个接受步；D-LR4 连 2 个完整严格步都未通过。因此不要启动 64/128，更不要启动 1024/8192。
