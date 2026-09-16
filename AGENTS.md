# AGENTS — 所有 agent 共用的项目入口

## 唯一工程目的

**在明确实现假设和可追溯证据下，复现 Qi & Sarris 2025 PI-DON 的旋度算子学习与逐时间步适配求解机制，并判断精度、成本和复用收益是否支持将它作为研究方向。**

写脚本、修接口、认证、训练和绘图都是手段。每次行动必须说明它缩小哪个目标差距；运行完成或测试通过不等于论文复现成功。

## 新会话固定起手

1. 本页：持久规则与目标。
2. [PLAN.md](PLAN.md)：全局路线、验收层级、失败后的后继任务。
3. [STATUS.md](STATUS.md)：最新证据与尚未解决的差距。
4. `py -3.11 run.py project_harness status` 和 `py -3.11 run.py project_harness next`。
5. 按当前任务读详细计划、相关实际源码和原始证据；不从头遍历全部旧计划。

当前执行细则：[直接机制推进计划](docs/plans/2026-09-14-direct-mechanism-plan.md)。新研究实验尚未执行，目录整理不代表机制复现完成。

用户最新指令优先。历史AGENTS/STATUS/报告中的“等待确认”“全部完成”“下一步”是当时状态，不是新指令。科学判断以原始数据和实际源码为依据，文档解释允许纠正。

## 状态和证据的职责

- PLAN：唯一总计划、目标验收表，不另设竞争的总计划。
- [project/plan.json](project/plan.json)：机器任务状态和证据路径。任务交付状态与科学结论分开，更新后同步PLAN和STATUS。
- STATUS：只保留当前快照，不追加互相覆盖的“当前有效结论”；旧版本保存在evidence历史目录。
- [project/actions.jsonl](project/actions.jsonl)：行动开始前登记问题、预期、判据、失败后去向，结束后追加证据，不覆盖旧事件。
- [records/LAB_NOTEBOOK.md](records/LAB_NOTEBOOK.md) / [records/lab_runs.jsonl](records/lab_runs.jsonl)：命令、成本、退出码、产出哈希的账本。
- RESULTS保留旧结论与反例；当前结论看STATUS引用的数值审计。旧verify_claims不作为完整认证。

## 行动合同

开始前写任务ID、目标差距、待区分假设、冻结配置/预算、预期、成功判据、失败后独立任务、输出目录。harness只检查登记、路径和调度，**不根据报告关键词或测试数量认证科学PASS**。

所有出数统一：

```powershell
py -3.11 lab_log.py run -m "任务ID：要回答的问题" -- py -3.11 run.py --action <行动ID> <脚本名> <参数>
```

科学结论用读取实际数值的脚本复算，保存源码、配置、数据/权重哈希和预设判据；缺项记INCOMPLETE。图由保存的脚本读取同一证据生成，不手填数字。

数值实验主入口会检查lab_log上下文和未结束行动的协议哈希；帮助、只读管理工具、unittest不要求实验行动ID。登记步骤见 [harness使用说明](docs/guides/HARNESS.md)。它不能阻止绕过入口直接调用Python，agent仍须遵守合同。

单臂失败只结束该臂；继续计划内前置具备的独立任务。64/128/1024/8192是同一合法新轨迹的事件检查点，不每到一个节点结束会话。不为填时间重复实验，也不因一个门槛失败省略剩余队列。

## 科学与恢复红线

1. 第一阶段预训练、每步问题训练、完成问题训练后的冻结复用分别评价；预训练直接冻结失败不能否定后者。
2. 项目R=SSE/target_ss与论文loss的单位/归约关系尚未完全确认。R<1e-4不能直接声称等同论文阈值。
3. 式(5)MRE、nMAE、相对L2分栏；共同归一化不会把MRE变成MAE/max。零/弱参考保存绝对误差和分母，不删除分量。
4. 硬源点被强制赋值，源点正确不证明传播正确。必须验六分量、去源全域误差和源外波形。
5. 精确Yee、几何精确核、解析控制只作参考/诊断，不计DCO成绩；不能将参考场反馈进正式闭环救场。
6. 坐标、RMS归一化、31间隔等是当前实现假设，不冒充作者确认。旧源码中的科学注释也须复核。
7. 原FAIL不改判，原权重、failure_raw和记录保留。旧失败不恢复重领预算；恢复核对身份、模型、优化器、RNG、phase、消耗预算和未知尾部。
8. Adam更新、LBFGS closure、LBFGS成功提交、评估、失败/重试成本分列；UNKNOWN与下界不写成精确总数。进程exit与科学状态分列。
9. 无stdout、一次空目录、累计进程CPU时间不是杀进程依据；检查本次进程、逐更新心跳、GPU和登记资源限制。
10. 不因结果差修改已登记门槛。增加预算只能在首次更新前登记独立新实验，不能补给旧失败。

## 文件、命令和协作

目录见 [README](README.md)、[文件索引](docs/FILE_INDEX.md)、[模型资产](docs/ASSETS.md)。根目录只放入口；新模型、数组、日志、报告在evidence/<实验ID>。旧模型在assets/models，旧数据在assets/datasets。

旧文件查找：`py -3.11 run.py project_harness resolve <旧名字>`。路径兼容不替代来源证明或恢复资格。历史固定输出脚本登记在project/script_registry.json，统一入口拒绝直接重跑；复用函数或创建新输出入口，不能覆盖旧证据。

run.py为统一入口并支持unittest。本机Windows/Python3.11/GTX1660SUPER，GPU训练串行，独立只读审查可并行。不用git add -A、git reset --hard；不覆盖用户原工作树；未要求不提交/推送；不清理权重或证据腾空间。

中文、面向初学者解释目的和意义；命令给完整PowerShell块。全队列只因用户叫停、无法保存的资源问题、必须越出计划改变物理/网络定义，或登记任务全部终结而结束。未执行NOT_RUN，缺证据INCOMPLETE。
