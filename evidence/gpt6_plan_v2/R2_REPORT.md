# R2：生产路径独立 Yee 控制报告

run #121 通过 `ProductionControlSolver.step`、支撑映射、PEC、硬源、六分量测量和独立 `PECCavity.step_e_source_h` 参考完成 128 步。

| 控制 | 最大全局相对 L2 | 门槛 | 结果 |
|---|---:|---:|---|
| float64 精确 Yee | 0.000000e+00 | <=1e-10 | 通过 |
| float32 精确 Yee | 2.808282e-06 | <=1e-4 | 通过 |
| 零旋度负例 | 1.000000e+00 | 必须 >5% | 被正确拒绝 |

控制分类固定为 `exact Yee control; not a DCO result`。它证明当前生产事务和评价接口能识别精确 Yee 与无传播负例；它不包含训练网络输出，不能计入 DCO 成绩。

R2 G0 判断：`PASS`。
