# STATUS — 当前复现进度快照

更新：2026-09-15。总路线见 [PLAN](PLAN.md)，下一轮细则见 [直接机制计划](docs/plans/2026-09-14-direct-mechanism-plan.md)。

**当前结论：第一阶段尚未完成条件化验收；新S1完整训练尝试工程中断，不能作为盲测成绩。第二阶段已有四条B规则/相关残差128轨迹（A-P、B-R、B-P、B-R2中的后三条按B规则），但G128场门全部失败，严格1024/8192未解锁。B收益配对FAIL。V最终报告结论：当前实现不支持将这一路线直接推进为可靠长程PI-DON复现。**

本轮完成核查、工作区分类、目标约束工具、M0最小工程回归、M1只读失败目标诊断、M2四臂直接128队列、S1中断审计、B收益配对和V最终研究判断。M0中的受控优化器测试只验证记录/恢复接口；M1只做固定状态读回、末层投影和梯度差分。M2是DCO在线残差证据，但G128场门失败，不能宣称长程机制复现成功。S1没有完成1000epoch和盲测，不能宣称第一阶段验收通过或失败。B显示预训练在残差128窗口内也没有同时节省Adam和耗时。

## 最新进展：V最终研究判断

依据：[最终报告](evidence/direct_mechanism_v1/FINAL_REPORT.md) 和 [最终审计JSON](evidence/direct_mechanism_v1/FINAL_JUDGMENT.json)。harness行动：`A-20260914T181715-3bca00e1`；lab_log：#290、#291。

- V交付状态：PASS；科学状态：FAIL。
- 正向证据：A-P、B-R、B-P、B-R2能在当前残差定义下完成128步残差接受，说明在线优化能压残差。
- 负向证据：残差通过没有带来合格场；128场门失败，源外波形未全过；B收益失败；S1完整盲测缺证据。
- 结论：当前证据不能说明论文机制已复现，也不应在当前门槛下启动1024/8192或冻结复用U。

## 当前阻塞与安全下一步

依据：[goal完成性审计](evidence/direct_mechanism_v1/GOAL_COMPLETION_AUDIT.md) 和 [S1重跑授权提案](docs/plans/2026-09-15-s1-rerun-authorization-proposal.md)。

- 当前有限队列已交付，但原始goal仍未完成：唯一阻塞项是 S1 完整训练与盲测未证明。
- 不能自动从 `s1_phase1/best.pt` 续跑；它是开发集best，不是最新epoch 937状态，续跑会重复更新并改变原登记成本。
- 安全下一步需要用户授权一个新的 S1R 协议/预算；原 S1 保持 INCOMPLETE，不改判。

## 最新进展：B预训练收益配对

依据：[B报告](evidence/direct_mechanism_v1/benefit/B_REPORT.md)、[B审计JSON](evidence/direct_mechanism_v1/benefit/B_audit.json) 和 [B-R2 summary](evidence/direct_mechanism_v1/benefit/B_R2/summary.json)。harness行动：`A-20260914T165418-00ed3794`；lab_log：#289。

- B交付状态：PASS；科学状态：FAIL。
- 新增B-R2：seed `20260915`，B规则，128/128残差接受；Adam `37588`，closure `0`，耗时 `4759.55s`。
- 对比B-P：Adam `44630`，耗时 `3502.87s`；B-R：Adam `38127`，耗时 `2935.34s`；B-R2：Adam `37588`，耗时 `4759.55s`。
- B-P相对两个随机对照的Adam节省为负数（约`-17.1%`、`-18.7%`），没有达到“两个随机seed均省≥20%”。
- B-P耗时只相对B-R2更快、相对B-R更慢，仍不满足双seed耗时收益。
- 更重要的是G128场门已失败；因此即便残差窗口成本有差异，也不能作为论文长程有效性的证据。

## 最新进展：S1完整第一阶段训练尝试中断

依据：[S1报告](evidence/direct_mechanism_v1/s1_phase1/S1_REPORT.md)、[中断审计JSON](evidence/direct_mechanism_v1/s1_phase1/interrupted_audit.json) 和 [history.jsonl](evidence/direct_mechanism_v1/s1_phase1/history.jsonl)。harness行动：`A-20260914T102345-10b45e87`；中断审计lab_log：#288。

- S1交付状态：INCOMPLETE；科学状态：INCOMPLETE。
- 原训练进程不再存活，且没有终止态`summary.json`、`last.pt`或盲测/迁移评估。
- 已记录训练历史到epoch `937`、Adam更新 `23425/25000`；最后一行无dev验证。
- 保存的best checkpoint在epoch `930`、更新 `23250`，开发集宏nMAE=`0.0219454050`、relL2 p90=`0.0549186216`、Eq.(5) MRE均值=`1.80438891`。
- 恢复资格：FALSE。最新epoch 937模型/优化器/RNG状态未保存；从best恢复会重复更新并改变登记成本，因此不把它当生产续跑入口。
- 因未完成1000epoch和盲测，S1不能用于判断论文第一阶段有效性；只能说明当前固定配方在开发集上已降到约2.2%宏nMAE但未形成合格盲测证据。

## 最新进展：M0新队列记录/恢复最小检查

依据：[M0报告](evidence/direct_mechanism_v1/m0/M0_REPORT.md)、[M0审计JSON](evidence/direct_mechanism_v1/m0/m0_audit.json) 和 [manifest](evidence/direct_mechanism_v1/manifest.json)。harness行动：`A-20260914T063218-e7293aa4`；lab_log：#276、#277。

- M0工程状态：PASS；科学状态：NOT_APPLICABLE。
- pending中断恢复与不中断结果一致；terminal resource checkpoint 不允许作为生产恢复资格。
- 成本分列可用：M0最小检查合计Adam更新5次、LBFGS closure 1次、接受步0、失败候选4。
- `nmae=None` 场景可报告，避免后续把缺测误写成0或PASS。

## 最新进展：M1真实失败目标只读诊断

依据：[M1报告](evidence/direct_mechanism_v1/m1/M1_REPORT.md)、[M1审计JSON](evidence/direct_mechanism_v1/m1/m1_audit.json) 和 [诊断图](evidence/direct_mechanism_v1/m1/m1_diagnostic.png)。harness行动：`A-20260914T063913-cb020658`；lab_log：#278、#279为工程失败现场，#280为正式PASS。

- M1交付状态：PASS；科学状态：NOT_APPLICABLE；本脚本参数更新0次、LBFGS closure 0次。
- P首次非零E：旧记录R=`5.160257e-4`，读回R=`5.160257e-4`，float64末层投影最佳R=`3.637490e-4`，仍未过`1e-4`。
- S-R第34候选E：旧记录R=`1.250444e-4`，读回R=`1.250444e-4`，float64末层投影最佳R=`1.250415e-4`，几乎无改善。
- 解释：这支持“当前冻结特征/状态限制”而不是“记录尺度错误”或“只差末层线性解”；但它只描述这两个固定状态，不证明整个网络类不可表达。

## 最新进展：M2/G128直接128队列

依据：[M2报告](evidence/direct_mechanism_v1/M2_REPORT.md) 和 [M2审计JSON](evidence/direct_mechanism_v1/m2_audit.json)。harness行动：M2 `A-20260914T065013-9957817a`，G128 `A-20260914T101632-09ad59c0`；lab_log：#281、#282为工程启动失败现场，#283–#286为四臂运行，#287为审计。

- A-R：FAIL，接受33/128；Adam `10228`，closure `1200`，第34候选E残差约`5.43e-3`。
- A-P：残差128完成；Adam `56680`，closure `0`。
- B-R：残差128完成；Adam `38127`，closure `0`。
- B-P：残差128完成；Adam `44630`，closure `0`。
- G128：FAIL。三条残差128候选有效分量最大nMAE约`4.9%–5.1%`，高于`1%`门槛；源外波形也未全≤`5%`。无资格启动1024/8192。

## 最新复核：上一轮报告需要更正

依据：[独立复核](evidence/workspace_reorganization_20260914/INDEPENDENT_AUDIT.md)，原始checkpoint读回为lab_log #264。

| 项目 | 可确认事实 | 当前解释 |
|---|---|---|
| 1h更新成本 | JSONL合计34939；S-P-retry之后心跳另记录183 | 精确总数UNKNOWN；已知下界35122，不是精确35122 |
| S-P-retry | 已保存6完整步、10447更新；最新checkpoint不包含后续183更新 | 原RESOURCE_LIMIT保留；RECOVERY_UNVERIFIED，新计划放弃生产恢复 |
| S-R | 33个残差合格完整步；第34候选H=9.93610e-5，E用满3000更新为1.25044e-4 | 原FAIL保留；不是64/128传播验收 |
| 2h D-LR4首试 | #261已完成1步、645更新后显示异常 | 工程异常/INCOMPLETE，不能在成本表漏列 |
| 2h D-LR4 retry | #262仅1完整步；4074总更新；下一E经2920更新到347.608 | 原科学FAIL与进程异常分开报告；不可恢复 |
| 2h新训练总数 | 645+4074=4719 | 两次独立首步不能拼成连续两步 |
| 12分钟结束 | 完成一部分审计与特定高lr诊断 | 执行完整性INCOMPLETE；没有逐项证明队列耗尽 |

S-P训练的完整lab_log覆盖也有缺口：#253是finalize，不能替代训练过程记录。旧audit中的恢复True只是指针存在/硬编码，不能作为恢复认证。

## 距目标还差什么

- **第一阶段：** 旧16例12例宏nMAE≤1%，最差例受弱分量影响，但旧S1整体FAIL不改。新S1固定方案中断在epoch 937，best开发宏nMAE约2.19%，但无last/summary/盲测；不能称“完全没学会”，也不能称论文对标已过。
- **在线收敛：** A-P、B-R、B-P均完成128个残差接受步；A-R失败于33步。M1已排除明显记录读回错误，并显示末层投影不足以把两个固定E目标压过`1e-4`。
- **传播准确：** G128场门失败。残差过线不等于场正确；M2三条128候选的有效分量nMAE仍约`4.9%–5.1%`，源外波形也未全过门。
- **长程和价值：** 1024/8192 DCO未解锁；B收益配对FAIL；问题训练后复用因G1024未解锁而NOT_RUN。纯Yee/FDTD只作参考，不计DCO成绩。
- **论文忠实度：** 项目R、坐标/RMS和训练后权重使用仍有假设；MRE与nMAE必须分列。完整历史G0仍INCOMPLETE，不靠本轮局部测试改判。

## 下一批任务

| ID | 当前状态 | 这一步的意义 |
|---|---|---|
| M0 | PASS，工程证据已落盘；科学成绩NOT_APPLICABLE | 防止未知尾部、漏计重试和不可证实恢复再发生 |
| M1 | PASS，只读诊断证据已落盘；科学成绩NOT_APPLICABLE | 一次检查真实失败输入，区分特征/优化问题 |
| M2 | PASS；三条残差128候选，场门未过 | 至多A/B两种新优化规则，P/R直接目标128，64中间检查 |
| G128 | FAIL；无候选进入1024/8192 | 数值门通过才同轨迹1024→8192；与交付完成状态分开 |
| S1 | INCOMPLETE；epoch937中断，无盲测 | 一次完整1000epoch/25000更新预训练未完成，不能用于第一阶段验收 |
| L1/G1024/L2 | NOT_RUN，G128未解锁 | 长程只允许从场门合格轨迹继续 |
| B | PASS交付；科学FAIL | 残差128窗口内预训练未相对两个随机seed省Adam/耗时，且场门失败 |
| U | NOT_RUN，G1024未解锁 | 无合格问题训练模型可做冻结复用 |
| V | PASS交付；科学FAIL | 最终报告已给出当前实现不支持直接长程推进的判断 |
| S1R | 未登记；需用户授权 | 若继续，需要新协议补完整第一阶段训练与盲测，不能恢复旧S1重领预算 |

新计划无1h/2h会话截止，已登记有限更新/closure/存储上限。单臂失败转独立任务，不停止整轮、不追加第三扫参。

## 工作区现在怎样用

根目录保留共同入口。源码在src/pidon，脚本在scripts各分类，测试在tests，原模型/数据在assets，历史输出在archive，实验现场仍在evidence，账本在records。

- [整理验收报告](evidence/workspace_reorganization_20260914/REPORT.md)
- [目录与文件索引](docs/FILE_INDEX.md) / [模型资产](docs/ASSETS.md)
- [机器迁移校验](evidence/workspace_reorganization_20260914/layout_validation.json)
- [harness使用方法](docs/guides/HARNESS.md)

随时运行 `py -3.11 run.py project_harness status` 查看目标差距。原AGENTS/STATUS及源码在 `evidence/workspace_reorganization_20260914/before/root/` 原样备份；旧报告不再充当当前执行指令。
