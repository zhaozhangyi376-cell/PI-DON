# PI-DON 复现工作区

目的：判断“学习旋度 → 每步适配求解 → 可靠场与可用收益”是否成立，支持研究方向决策。

先读 [总计划 PLAN](PLAN.md) 和 [当前进度 STATUS](STATUS.md)。Agent先读 [AGENTS](AGENTS.md)。

| 想找什么 | 位置 |
|---|---|
| 总目标、为什么做、怎样验收 | [PLAN.md](PLAN.md) |
| 当前进度、距目标差多少 | [STATUS.md](STATUS.md) |
| 下一轮完整执行细则 | [直接机制计划](docs/plans/2026-09-14-direct-mechanism-plan.md) |
| DCO、Yee、在线求解、指标与记录器 | [src/pidon](src/pidon) |
| 实验脚本 / 审计报告 / 论文外探索 | [scripts/experiments](scripts/experiments) / [scripts/analysis](scripts/analysis) / [scripts/exploratory](scripts/exploratory) |
| 单元与合同测试 / 工作流工具 | [tests](tests) / [tools](tools) |
| 原始模型 / 训练数据 | [assets/models](assets/models) / [assets/datasets](assets/datasets) |
| 各次实验原始证据与报告 | [evidence](evidence) |
| 总运行账本 | [records](records) |
| 历史曲线、指标、数组与旧批处理 | [archive](archive) |
| 论文推理、历史过程、环境指引、旧计划 | [docs](docs) |
| 图 / 汇报材料 | [figs](figs) / [slides](slides) |

[完整文件索引](docs/FILE_INDEX.md) · [模型资产索引](docs/ASSETS.md) · [两小时轮独立复核](evidence/workspace_reorganization_20260914/INDEPENDENT_AUDIT.md)

随时查看进度：

```powershell
py -3.11 run.py project_harness status
```

查看下一批可执行任务：

```powershell
py -3.11 run.py project_harness next
```

通过旧名字找文件：

```powershell
py -3.11 run.py project_harness resolve dco_lr1e3_300.pt
```

源码帮助：

```powershell
py -3.11 run.py pidon_solve --help
```

数值运行用根目录lab_log.py包裹run.py。部分旧脚本写死输出，已封存；先看project/script_registry.json。可导入其函数，不直接重跑旧命令。
