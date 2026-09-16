# G0 尝试 01 停止记录

- lab_log：#194
- 状态：实现错误，未形成 G0 结论。
- 原因：`pidon_exact_control.run(torch.float32, ...)` 将 `torch.dtype` 直接交给 `numpy.dtype`，在第二个控制启动前抛出 `TypeError`。
- 保留现场：`control_runs/float64_exact/` 是已完成的第一项 float64 控制；没有删除、覆盖或把它混入下一次认证。
- 后续：修复 dtype 判别后，在隔离的 `g0_attempt_02/` 重新从头执行整套控制；尝试 01 不可作为任何 G0 PASS 证据。
