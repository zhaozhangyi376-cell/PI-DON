# 核查、工作区整理与总计划交付

日期：2026-09-14。范围：核查上一轮、整理工作区、建立跨agent目标入口和下一轮计划；没有启动新的研究训练。工程测试中受控参数更新不计DCO研究成绩。

## 核查结论

- 一小时JSONL合计 **34939**，真实总数 **UNKNOWN**，已知下界 **35122**；尾部183不能从完整checkpoint恢复出来。
- 两小时两次新运行共 **4719** 更新，包含首试645；原报告4074只是retry成本。
- S-R的33个残差合格完整步和后续E失败有依据；D-LR4 retry只通过1步且下一E失败。原FAIL保持，两个独立首步不能拼接。
- S-P-retry原RESOURCE_LIMIT保持，恢复资格改为派生UNVERIFIED；新计划放弃生产恢复。旧审计True不是认证。
- 12分钟结束是执行INCOMPLETE，未逐项解释独立队列为何不再执行。高lr结果不能泛化解释R第34步；源外局部偏差说明不能仅看源点或全域小nMAE。
- 详见 [独立复核](INDEPENDENT_AUDIT.md) 和 [原始数值再审计](audit.json)。后者由tools/audit_reorganization_delivery.py读取JSONL、心跳和checkpoint，不复制旧报告的汇总值。

## 整理结果

原根文件中 **233** 项已分类（含两份账本），根目录现有 **10** 个入口/配置文件。

| 位置 | 移入文件数 |
|---|---:|
| `archive/legacy_commands` | 13 |
| `archive/legacy_results/arrays` | 28 |
| `archive/legacy_results/metrics` | 19 |
| `archive/legacy_results/training_curves` | 15 |
| `assets/datasets` | 5 |
| `assets/models` | 29 |
| `docs/guides` | 2 |
| `docs/history` | 3 |
| `docs/paper` | 3 |
| `records` | 2 |
| `scripts/analysis` | 27 |
| `scripts/experiments` | 41 |
| `scripts/exploratory` | 12 |
| `scripts/figures` | 6 |
| `src/pidon` | 11 |
| `tests` | 17 |

全部移动先登记旧/新路径及SHA256，再同盘移动并复核。二进制权重和数据原字节保留；114份Python源码只做布局导入/根路径适配，原源码字节在before/root保留，修改前后哈希分开登记。原evidence实验目录保持原位，没有清理原始权重或失败现场。

- [文件索引](../../docs/FILE_INDEX.md)：按目录列全体迁移文件。
- [资产索引](../../docs/ASSETS.md)：checkpoint自述轮次/网络/归一化，以及数据数组头形状、哈希；自述不等于训练来源认证。
- [迁移表](../../project/migration_map.json)：旧名字精确定位；旧证据不改写路径和数值。
- [原纲领/源码备份](before/root)：原AGENTS、STATUS、RESULTS和源码；before还保存了用户原有git差异。未提交，没有使用reset硬对齐工作树。

## Harness如何避免偏离总目标

AGENTS是持久入口，PLAN是唯一目标路线，STATUS是当前快照；project/plan.json登记任务和科学门，actions.jsonl记录行动。新会话不再读取多轮互相冲突的“当前有效状态”。

开始实验必须提供任务ID、问题、预期、成功判据、失败后去向和协议。run.py的实验主入口要求有效未结束行动和lab_log上下文，协议哈希改变或行动已结束会拒绝。源文件读取可解析旧路径，输出不会转向旧模型。

delivery任务PASS只表示交付完成；G128/G1024必须数值逐项通过才PASS。harness本身不认证论文，也不能阻止直接绕过入口调用Python。模型正确性仍由实验数值合同保证。

旧报告/历史固定输出驱动通过script_registry封存主入口，源码可阅读/导入。它们的根目录glob与所有默认路径未全部重构，不能承诺每条历史命令可直接重跑；这样避免把已迁移证据误写为NODATA，或覆盖旧失败。新实验按新计划建立明确输出。

## 验证与实际边界

- 移动完整性：233项文件存在、哈希和旧名解析均通过，原Python备份哈希一致。
- 核心dco、fdtd、pidon_contract、head_lstsq的函数/类AST完全一致；Solver仅_make_net读取路径与formal_run_identity的文件存在判断适配，内层拟合、场推进、指标数学未更改。源码字节变化真实记录，不伪造旧协议哈希恢复。
- #268执行71项、去重55个ID；全部通过。#270/#272验证入口保护，最终5个入口ID通过；合计60个不同测试ID，不将重复执行算额外覆盖。
- 工程登记检查通过，新的科学门/训练阶段仍NOT_RUN；局部测试不将旧完整G0升为PASS。
- 记录器尾部/新预算runner等M0后续研究工程尚未执行，不能因目录整理写成已修好。

## 下一轮

按 [PLAN](../../PLAN.md) 与 [直接机制执行计划](../../docs/plans/2026-09-14-direct-mechanism-plan.md)：最小计数/测量修复 → 真实失败输入一次鉴别 → 至多两个新优化规则、独立P/R直接连续128 → 合格同轨迹1024/8192。独立完成一次第一阶段完整训练和成本/研究判断。

不设1h/2h会话截止，仍登记有限更新/closure/存储配额。单臂失败转下一独立任务，不放宽科学门槛、不重领旧预算、不加第三种扫参。执行goal以有限队列和可审计判断完整交付为完成条件，科学成功另列。下一会话prompt在执行计划末节。

本次整理交付完成；论文第一/二阶段复现及新计划执行均未宣称完成。
