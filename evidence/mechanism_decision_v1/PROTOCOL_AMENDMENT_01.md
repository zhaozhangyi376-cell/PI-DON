# 协议附录 01：第一阶段评估器的元数据兼容修复

创建时间：2026-09-14，发生在 `lab_log #226` 失败之后、任何第一阶段结果或第二阶段参数更新之前。

| 项目 | 初始快照 | 修订后实际运行版本 |
|---|---|---|
| 文件 | `mechanism_decision_eval.py` | `mechanism_decision_eval.py` |
| SHA256 | `64344c7a2ba799d7741c0eaf442c82e990797d8013903bc49c015edb424c44ff` | `e9fabee2dfbe4b2aff8dc18da1eaa2027e02310a7ba1195b8875a1919b0c6197` |
| 原因 | `sample_spec`只接受新随机样本的`k_rad_per_m` | 同时接受既有论文重建样本的等价字段`k` |
| 影响 | #226在固定波形对照前退出，未写入`phase1_raw.json`，DCO参数更新为0 | 只改变评估元数据适配；不改波数、场、curl、网络、归一化、门槛或任何训练设置 |

失败证明：`lab_log #227` 的测试在`paper_protocol.wave_spec()`输入上以`KeyError: k_rad_per_m`失败。修复后同一测试在`lab_log #228`通过。

原`protocol.json`、初始化源码快照和#226失败记录均不覆盖或删除。本附录是本轮第一阶段结果应引用的评估器版本声明；核心DCO/求解器源码哈希未改变。
