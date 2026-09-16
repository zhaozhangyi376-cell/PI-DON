# 机制与收益验证：执行状态

| 步骤 | 状态 | 验证依据 |
|---|---|---|
| 1：协议、物理路径与记录检查 | PASS | lab_log #223–225；`protocol.json`；`path_check_raw.json` |
| 2：预训练权重的未见场/网格评估 | FAIL（S1） | lab_log #232；32³整体相对L2的90分位1.15%，但宏nMAE最大20.9%超过1%；迁移组另列，不混比 |
| 3：P/R顺序暖启动对照 | PARTIAL | P在第0层curl-E严格FAIL；R有26个严格接受步但被代理提前终止，详见`EXECUTION_DEVIATION_01.md`；B不可验收 |
| 4：首次失败鉴别 | COMPLETE（未定位到该范围内的接口错误） | lab_log #238；磁盘参数纯前向R=0.000516025687，与记录差2.23e-11；三分量、RMS尺度、支撑和未覆盖PEC面均已分栏核对 |
| 5：1024步与预训练收益 | NOT_RUN | 需要P通过128 |
| 6：冻结复用 | NOT_RUN | 需要步骤5产生合法在线轨迹 |
| 7：8192、材料/几何与大dt | NOT_RUN | 需要S2及收益证据 |

| 台账复核 | COMPLETE | lab_log #240（读取器单测）与#242（`verify_claims.py` Z0–Z3）；Z0、Z1为预登记FAIL，Z2为INCOMPLETE，Z3为NOT_RUN |

历史G0完整认证仍为INCOMPLETE；本表仅说明本实验路径的实际执行情况。P未通过，故本轮有界方案在步骤4结束；没有以恢复、重跑或追加扫参绕过门槛。
