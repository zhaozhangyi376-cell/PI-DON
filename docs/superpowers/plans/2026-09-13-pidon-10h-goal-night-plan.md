# PI-DON：10 小时 goal 夜间执行计划

> **For agentic workers:** 使用 `$superpower-executing-plans` 按勾选项实施；用系统调试定位失败，用数值证据验收。用户在下一会话发送文末 goal 指令即授权本计划明确列出的训练规则调整。连续执行具备前置的分支，不需例行确认；不要自行扩展候选或通过重启获得新预算。

**Goal:** 在从首次执行开始累计不超过 10 小时的墙钟内，补成可信 G0，完成一次有明确依据的新优化规则实验，按原科学门槛尽可能取得 64/128/1024/8192 的有效结果；若分支失败，完成已登记的独立诊断并交付完整中文验收包。

**Architecture:** 保留 DCO L4/base32/direct、主权重、cellsize/RMS、h_shift=True、独立 H/E、Yee/PEC/源协议及原 R/场/频谱门槛。唯一新训练规则为每个需要拟合的目标先提交一次末层最小二乘解，再最多 499 次全网络 Adam，参数更新总数最多 500。先修真实停止、记录恢复、测量和认证器；长程由同一条新轨迹依门槛续进。

**Tech Stack:** Windows PowerShell，Python3.11，现有 torch/numpy/matplotlib/unittest，lab_log。不升级依赖、不引入新框架、不转移到服务器。

**当前状态：** 本文件为待执行计划。N0–N6 均 **NOT_RUN**。#173 是本计划前审计，不能算本夜已完成阶段。

**存储修订 v4.1（2026-09-13）：** 用户已清理磁盘，并授权空间不足时自主清理不常用软件的数据。#177/#178实测空闲约25.3GiB，原主权重和四份失败权重hash匹配。当前无需清理。采用两槽滚动＋主轨迹每256步完整检查点，将正常新增证据预算设为16GiB，保留5GiB系统余量＋1GiB紧急余量。原版本在 `evidence/gpt6_plan_v4_review/storage_revision/plan_before_storage_revision.md` 保留；下面存储条款覆盖旧预算。训练规则、科学门槛、10小时期限和新候选数量均不变。

**必读材料：**

- `C:/PI-DON/evidence/gpt6_plan_v4_review/REVIEW.md`、`audit.json` 与 `audit_night_v4.py`。
- `C:/PI-DON/evidence/gpt6_plan_v4_review/storage_revision/REVISION.md` 和 `storage_forecast_refined.json`（最新存储状态，覆盖旧5.91GiB估计）。
- `C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-g0-completion-and-h-layout-plan.md`。
- `C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-contract-repair-and-gated-continuation.md`。
- `C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-evidence-and-reproduction-plan.md` 的指标定义/G2–G5。
- 当前实际源码；AGENTS/STATUS/CLAUDE 的科学结论仅作线索。旧 nMAE=MRE 等结论不采用。

---

## 一、权限边界、预期和夜间完成定义

### 1.1 本次允许改变什么

| 项目 | 决策 |
|---|---|
| 工程实现 | 修复已知停止、恢复、记录、测量和认证缺陷，补独立的预算调度；不借此重训旧任务 |
| 新候选 | 仅 `head_lstsq_once_adam499`，精确说明其为优化规则变体；不是作者算法已确认 |
| 网络/尺度/位置 | 主网络结构不变，原主权重初始化，h_shift=True，RMS/cellsize，两种 H scale 都为 1 |
| 更新预算 | 每目标总参数提交<=500，其中末层联合提交<=1，Adam<=499；3个分量求解记3次线性求解和1次联合参数提交 |
| 既有失败 | #129/#132/#166 的失败及预算全部保留，禁止恢复旧失败网络继续更新；旧 P4-A 不重跑 |
| 门槛 | 非零目标 R<1e-4、A_fixed<=1e-3、G2/G3/G4均不放宽；候选达标仍属于声明优化变体的结果 |
| 额外工作 | 仅 N5 两个无更新诊断；无第一阶段长训、无第二优化器、无 lr/宽度/种子/损失扫参 |
| 保存策略 | 仅新夜间目录采用两槽滚动常规checkpoint；永久保留历史资产、新失败raw/safe、验收最终状态和证据清单 |
| 增强复核 | 主轨迹每256接受步保留完整参数/优化器/RNG，另保留主64/128和重复seed128，预算见2.3 |
| 软件数据清理 | 仅在实际空间不足时，按2.4自主清理已识别、可再生成的非活跃软件缓存/临时数据；不另行例行确认 |

本计划明确替代 v3 的“只准一个 H 位置候选”后续可执行范围：该候选已失败，本夜不重跑它，而登记一个不同训练规则。不是把旧失败改成成功，也不是因为测得失败而追改阈值。

### 1.2 预期分层

1. **最低应争取交付：** 完整的工程认证或逐项可复现的剩余缺口、旧证据纠正表、资源账本和中文报告。不能承诺一定修好所有问题。
2. **主要实验目标：** 新规则在 43/96 开发点给出有预算、有磁盘参数 R、有失败现场的明确结果，回答末层拟合能否解除当前瓶颈。
3. **较好结果：** 八个固定状态全部过 G1，并从零场严格完成 128 步；有六分量和有效源外波形。
4. **机制目标：** 主 seed 连续 1024 步和第二 seed 的 128 步满足 G2。允许与论文有偏差，但不能只以“运行到了某步”算成功。
5. **有条件冲刺：** 从同一主轨迹续到 8192 并通过 G3。当前无可靠耗时预测，**不承诺一夜达到8192**。

goal 的有限目标是“按本计划完成当夜可执行工作并交付可信结果”。只有所有适用任务已完成、合法停止/NOT_RUN 分支有完整理由、资产验收和最终报告齐全，才能把这个夜间 goal 标为 complete。必须另报 `G0/G1/G2/G3/论文复现状态`，不能把“夜间 goal 完成”写成“论文已复现”。若仍有可执行的必做任务，就不是 complete；goal 工具的 blocked 状态须遵循其连续阻塞轮次规则，不能第一次遇到 G1 FAIL 就直接设 blocked。

## 二、10 小时调度、资源与持久预算

### 2.1 持久时钟

- [ ] N0 第一个动作创建 `C:/PI-DON/evidence/gpt6_plan_v4_night/night_manifest.json`，用 UTC 写入 `started_at`、`deadline=started_at+10h`、`training_deadline=deadline-30min`。恢复读旧值，不新建开始时间。首次创建用排他写入；存在就校验身份再读取。
- [ ] 实现 `C:/PI-DON/night_budget.py`：墙钟截止与各分支预算都必须检查。单进程计时用 monotonic；恢复时 UTC 截止仍有效，已用累计训练时间/更新数从账本恢复。时钟倒退或记录冲突即停止新训练并报告。

```python
from datetime import datetime, timedelta, timezone
started = datetime.now(timezone.utc)
manifest = {
    'started_at': started.isoformat(),
    'deadline': (started + timedelta(hours=10)).isoformat(),
    'training_deadline': (started + timedelta(hours=9, minutes=30)).isoformat(),
    'status': 'RUNNING',
}
# 仅在首次排他创建时生成。已存在文件绝不进入上述初始化路径。
```

- [ ] 全局账本使用 `experiment_id + task_id`，task_id 包含 split/seed/source_index/phase/输入靶值hash。run_id 是独立运行 UUID；protocol_hash 是配置内容 hash，二者不能混同。改输出目录不能获得新的 task 配额。
- [ ] 每个更新边界检查截止时间和剩余额度；每个子步、每次线性求解前再检查。单次 CPU SVD 也计该目标时间；最终纯前向/磁盘复核次数单列，不计参数更新。
- [ ] 全局预算不足时通过已测试的中断钩子保存当前阶段和预算。该任务只有确切保存的中断边界才有恢复资格；超出单目标预算、数值非有限或账本不明的失败不可自动恢复。

### 2.2 推荐时段及硬边界

时间以本夜 t0 为起点，不以写计划的时间起算。可提前进入下一阶段，不能靠重启延后总截止。

| 阶段 | 预算/最迟边界 | 产物 | 失败去向 |
|---|---|---|---|
| N0 资产/身份/资源登记 | 15分钟 | manifest、资产hash、源码、计划hash | 数据/身份不明则报告，不训练 |
| N1 合同与恢复修复 | 90分钟 | 真正回归与故障证据 | 不训练；允许继续 N2 中不依赖该缺陷的测量与 N5 |
| N2 完整测量与 G0 | 60分钟；N1/N2最迟t0+2h45m冻结结论 | 逐项G0清单、独立128控制、8192参考缓存 | G0不全则N3/N4 NOT_RUN，转N5/N6 |
| N3 新规则实现与开发/固定验证 | 45分钟；实际候选计算合计<=30分钟 | 规则单测、43/96、通过后六验证状态 | G1失败转N5；无第二候选 |
| N4 64→128→重复128→1024→8192 | 占用剩余可训练时间，最多到t0+9h30m；仍受原各段上限约束 | 连续轨迹/全部指标/实测P90预测 | 保留停止状态，转N5可完成项或N6 |
| N5 两项独立无更新诊断 | 从N4未使用时间中最多90分钟 | 特征/标签与梯度分析 | 数值问题如实记录；不追加训练 |
| N6 总验收 | 预留最后30分钟 | 中文总报告、表/图、重现入口、资源账本 | 发现证据缺失则降级对应结论 |

若 N1/N2 在规定修复窗口未完成，停止新增修复候选和正式训练；不能无限循环修补耗尽全夜。可以把剩余问题与稳定重现代码整理完整。未解决的结构问题不在夜间临时重构。N3 实现与接入后的再次认证共用45分钟，超过窗口也不允许挤掉报告预留继续冒险开跑。t0+2h45m冻结的是N1/N2基础版本结论，不禁止N3在自己的窗口内对接入新规则后的版本做下文明确要求的再次认证。

“充分利用”是不断执行有前置、有信息价值的已登记工作，不是保证 GPU 满载 10 小时。所有分支已结束时可以提前提交；不能等待空转、重复失败实验或凭空创建后台任务。无需创建定时自动化，goal 的连续执行由下一会话负责。

### 2.3 磁盘、内存、显存

- [ ] N0 用 `shutil.disk_usage`、系统内存和 `nvidia-smi` 在 lab_log 内重新实测。最新#178空闲25.324GiB；#173的5.91GiB仅是历史。不得把用户已经释放的空间仍判成当前不足。
- [ ] **区分半步和完整状态尺寸。** 旧149.5MB文件只有H的Adam已建立，E的Adam为空。#178读取实际tensor后，补计E的Adam约73.97MB，双优化器完整状态估计223.47MB；再加25%安全系数，每份预算279.34MB。新状态保存后核查H/E两侧所有可能参与Adam更新的参数是否都已有完整step/moments，不能把“H/E已达标”当作“Adam状态已建立”：末层直接达标可能是0次Adam。未建立的状态仍按参数shape/dtype补计两套moments和step，再给25%余量；不能用这种较小文件下调未来完整状态预算。真实文件超出预测则及时上调预计占用。
- [ ] 正常新增证据上限为 **16GiB**；实际允许值=`min(16GiB,当前可用空闲-6GiB+本夜已占用bytes)`，随实际空闲和本夜已占用更新，不因恢复清零。保留 **5GiB系统余量＋1GiB紧急raw/safe/日志空间**；正常写入完成后空闲须>=6GiB。保存前包括临时原子文件的峰值需求，不只看最终文件尺寸。
- [ ] 下列为包含已执行/未执行全部可能分支的保守证据预算，实际没跑的分支不得创建空模型文件凑数：

| 完整状态用途 | 最多份数 |
|---|---:|
| 主轨迹256、512、…、8192 | 32 |
| 主轨迹64、128额外保存 | 2 |
| 第二seed128最终 | 1 |
| 八个固定状态各一份最终H/E完整状态 | 8 |
| 两seed各自两槽滚动 | 4 |
| 科学/数值失败raw/safe预算 | 8 |

共55份，按每份279.34MB，再给六场/输入目标/控制/日志/图合计1.25GiB，估计新增 **15.56GiB**。这包含相互排斥分支，属于保守预估。失败证据超过预留份数也必须保留，随后停开重任务并重新预测；不能按份数删掉失败。

- [ ] 实现新运行两槽 `checkpoint_A.pt/checkpoint_B.pt`：写临时文件→flush/fsync→原子替换非当前槽→读取验证hash和必要状态→原子更新小型commit指针。上一槽仍可恢复；普通滚动提交只追加小型清单，除上表登记点外不复制完整权重。
- [ ] 上表永久状态由同一完整提交产生并记录hash，不再额外复制一个同内容“阶段final”文件。成功固定状态每点保留一份包含H/E的最终完整状态；失败保留raw/safe。轨迹300/600/900等场快照仍只存六场/参考/metadata，不重复优化器。不得保留每10次更新的大模型副本。
- [ ] 旧v1/v2/v3和v4审计目录只读。新目录普通滚动槽可被下一次正常提交原子替换；不得覆盖失败文件、登记永久状态和验收最终文件。项目原数据/权重不能作为清理候选。
- [ ] GPU 单作业，禁并行争用 GTX1660SUPER。显存/内存达85%且继续申请会越限时不启动下一重任务；不为凑显存改网络/网格/训练batch。CPU特征按角色流式释放，避免同时持有全部checkpoint。
- [ ] 每阶段记录 wall_s、训练/求解s、I/O_s、峰值显存/内存、磁盘新增bytes；本夜所有子阶段总和不得借恢复重置。

### 2.4 空间不足时自主清理软件缓存

用户已授权此条件分支，不需为下面明确范围再次询问。**当前空间充足，本轮未删除任何软件数据。** 清理是资源操作，不改变实验配额、科学门槛或deadline。

- [ ] 先区分两个限制：预测正常新产物超过16GiB硬上限时，停止对应重分支并报告，清缓存不能增加这个产物上限；此情况不触发清理。只有产物仍在16GiB内，而实际空闲不足以承受下一保存峰值及6GiB余量时，才触发软件缓存清理。先在完整更新边界利用预留空间保存可恢复状态，暂停新训练；不在活跃训练期间清显卡缓存，也不强行关闭用户应用。
- [ ] 新建 `C:/PI-DON/night_storage.py`，只在触发时检查已识别的软件缓存路径，不做整个C盘递归删除/全AppData清空。优先顺序：pip已下载包/HTTP缓存→非活跃应用确认可重建的shader/cache→Temp内确认归属且超过7天的普通临时文件。用软件自带cache查询/清理接口优先；pip目录可由 `py -3.11 -m pip cache dir` 定位，不按猜测路径删除。
- [ ] “不常用”不能仅凭最后访问时间认定。必须同时确认数据是可再生成缓存/临时产物、所属软件无当前任务依赖，且不是恢复/用户工程文件。软件身份或文件用途不明确就跳过这个目录，继续其他可安全清理项。
- [ ] 清理前写 `cleanup_manifest.jsonl`：候选绝对路径、所属软件、数据类别、可再生成依据、大小/mtime、未被使用的检查结果、预计回收量。先形成精确清单，再在同一PowerShell中逐项执行`Remove-Item -LiteralPath`或软件自带cache清理；用户授权已在此计划中，无需把清单再发回来等待确认。
- [ ] Windows路径约束：先`Resolve-Path -LiteralPath`并核对绝对路径位于已登记缓存根之内；拒绝盘符根、用户目录根、AppData整根、项目根以及任一父节点的junction/symlink/reparse point。避免跨shell拼接删除命令。遇锁定/拒绝访问直接跳过，不提权、不杀进程。单个候选删除前复核路径/文件状态，防止清单后发生变化。
- [ ] 不删除：论文/源码/git/evidence/数据集/权重/失败现场、桌面文档下载、浏览器profile/密码/历史、聊天附件/笔记、许可证/登录状态、应用数据库/恢复备份、离线模型/离线安装包、当前Python/CUDA环境、依赖目录和正在使用的应用数据。清理授权不等于卸载软件或删整个软件用户目录。
- [ ] 实際执行及清理前后空间测量一律包lab_log，记录每项成功/跳过/失败和实际回收bytes。释放到能容纳下一分支及6GiB余量即停止清理。最多两轮、合计15分钟，计入10小时总墙钟；清理不得延后训练/报告截止。
- [ ] 空间足够后从同一合法checkpoint和同一预算继续。若只有用途不明/用户数据可删，或安全清理后仍不足，保留现场并停止依赖分支，继续能完成的轻量诊断/报告；不要用危险删除换取继续训练。

## 三、文件职责

全部在 `C:/PI-DON/`。避免把调度、数值验收和报告糅在一个脚本。

| 文件 | 工作 |
|---|---|
| `pidon_solve.py` | 修停止/恢复入口；接入一处可选head拟合；正式轨迹使用同一Solver |
| `pidon_recording.py` | 修JSONL事务/真实磁盘恢复、两槽保存、失败证据和恢复资格 |
| `pidon_contract.py` | 明确指标定义、弱场参考上下文、同阶段诊断 |
| `pidon_exact_control.py` / `reference_cache.py` | 独立原step硬源参考、测量半步适配、double缓存与负对照 |
| `test_pidon_contract_v4.py` | N1/N2真实回归，逐ID原始数值证据；不导入旧TestCase类进入发现空间 |
| `g0_verifier.py` | 改为参数化输入/输出，逐项重算数值，拒绝缺失、重复、错hash和报告标签欺骗 |
| `night_budget.py` | 统一时钟、身份、task累计资源，原子持久化 |
| `night_storage.py` | 触发式存储预测、明确缓存清单、安全清理及实际回收记录；空间足够时不删除 |
| `head_lstsq.py` / `test_head_lstsq.py` | 末层最小二乘训练和专用恢复/计数/映射测试 |
| `night_fixed_state.py` | 八个固定状态，调用生产Solver，oracle分栏，保存任务级恢复身份 |
| `night_runner.py` | 实施前置图、单GPU调度、64/128/1024/8192、N5/N6路由 |
| `night_diagnostics.py` | N5无更新诊断；不能调用opt.step或写回正式模型 |
| `night_evidence.py` / `make_night_report.py` | 统一重算入口，verify_claims和图都调用它 |
| `verify_claims.py` / `STATUS.md` | 新Y0–Y3分阶段判据和实际结论；X0历史撤回保持 |

没有要求把现有仓库整体重构。只在明确上述职责所需的范围改代码。每项测试先记录当前不满足的行为，再修生产路径，之后记录满足要求的证据。

## N0：冻结现场与实际协议

- [ ] 保存当前源码（含全部被执行的本地import模块和入口）、git commit、dirty diff、计划hash、Python/torch/CUDA版本、GPU、设备/线程配置。使用源码快照可重现，不声称dirty树等于commit。
- [ ] 对原主权重和v1/v2/v3失败资产建立只读前hash清单；夜末核对。主权重必须是 `dco_lr1e3_300.pt`，SHA256=`3f259bc887a10fac77f6bdf77b43ba1ad6b45827a3f8b9bd685934acc47ca5d7`。不自动寻找“更好”的权重替换。
- [ ] 新建 `acceptance.json`：复制v2固定科学门槛、记录完整公式/单位、追加本计划规则和资源限制。源码实际加载的levels/base/head/coords/norm必须与配置一致；不允许`_make_net`静默覆盖 CLI 后仍声称配置一致。
- [ ] 更新总stage表：每项初始化NOT_RUN，记录前置和stop_reason。本夜的run_id从lab_log实际输出绑定，不手填猜测的下一序号。

验收：资源可容纳最低证据包，全部初始化/协议hash匹配，否则不训练。交付 `N0_REPORT.md`。

## N1：真正修复停止、恢复和落盘

### N1.1 测试先行

- [ ] 将 #173 反例加入正式回归，期望是拒绝错误，不是“复现错误算PASS”。保留首次失败输出。

```python
self.assertNotEqual(len(saved_ids), 0)
self.assertEqual(len(saved_ids), len(set(saved_ids)))
with self.assertRaises(ValueError):
    solver.load_state_payload(terminal_payload)
self.assertFalse(fit.passed)  # component loss<1e-4，但全物理R>=1e-4
self.assertEqual(reference_e[0].dtype, torch.float64)
```

`terminal_payload` 在测试内用真实 Solver.state_payload 构造，并设置实际 stop_reason/resumable；拟合反例沿用 #173 的 100/1/1 靶值与101.5/1/1预测。正式诊断读取终止权重必须走显式 `diagnostic_only` 路径，只允许纯推理，不能把它作为恢复API旁路。

### N1.2 必須覆盖的合同清单

| ID | 真实断言/故障 | 通过证据 |
|---|---|---|
| C01 | total R与分量目标矛盾、R恰好1e-4、最后一次更新刚过门 | 用最终物理SSE/target_ss严格判断；等于门槛不通过 |
| C02 | 全物理输入/target均0；裁剪外非零；非零无旋场 | 仅完整严格零可捷径；零target按两项固定尺度，不删支撑 |
| C03 | H失败 | 无E更新、无加源、无H更新，phase before_H |
| C04 | E失败和E_pending恢复 | E和硬源只执行一次，下一源索引不变，H未提交 |
| C05 | Adam中断后从实际磁盘恢复 | 参数/Adam状态/RNG/计数与不中断轨迹一致 |
| C06 | LBFGS中断及完整调用后异常 | 保存trial raw，回滚到最近完整接受调用；closure不退款；真实磁盘恢复与连续路径一致 |
| C07 | 累计更新/时间/closure已耗尽 | 不再更新，不改预算，不重启优化阶段 |
| C08 | nonfinite输出、loss、梯度、参数 | 分别注入；raw保留故障值和已耗额度；safe可诊断但不得自动续训 |
| C09 | 保存payload缺version/config/role/source、配置/架构/hash不合 | 全部拒绝正式恢复；诊断加载明确隔离 |
| C10 | 相同协议独立run、同run恢复、换目录重复task | UUID不同；正确同run恢复；累计task额度不重领 |
| C11 | JSONL落盘后metadata失败 | 扫描真实行恢复唯一序号，尾部标未checkpoint，不假装已经接受 |
| C12 | JSONL最后一行截断/重复/错序/非有限JSON | 保留坏尾证据，拒绝不明确恢复，不直接截掉历史文件 |
| C13 | checkpoint临时写、替换后指针前、指针写失败 | 至少上一完整槽可用；协调完整槽与日志，不重复提交，不重领已消耗额度 |
| C14 | failure_raw或字段快照写入 | 不改变正式恢复commit标记；文件名唯一；E失败使用E attempt |
| C15 | deadline/磁盘预算触发、恢复后deadline不变 | 无新训练，保存确切phase/counters和stop_reason |

- [ ] 对每项生成 `id/test_id/expected/observed/status/run_id/source_hash/evidence_path/hash`。测试ID去重；单元测试assert覆盖行为，报告提供断言背后的数值/状态，不只SUCCESS字符串。
- [ ] 全物理 R 与优化目标分别存字段。梯度在step前检查，参数在step后检查；非有限失败的实际已执行次数保留，不返回0冒充没更新。
- [ ] 同阶段恢复不能无条件把stop_reason置空/resumable改True。只有允许的interrupt且预算剩余、phase/task/代码身份全匹配可续。`max_updates/time_budget/nonfinite/closure_budget`均终止。
- [ ] 每次Adam更新前后写轻量intent/commit账本。突然断电导致参数与已消费账本不对应时，标 `RECOVERY_UNCERTAIN` 并停止自动训练，不能回滚参数并重得同批更新预算。计划内中断须先保存完整状态，再退出。
- [ ] 两槽机制以及真实torch.load的schema/hash校验完成，文件fsync后才提交指针；训练状态和记录器状态一起核验。登记永久状态另外带相同commit身份和只读hash，不准损坏两槽恢复链。不能只在内存复制payload称磁盘恢复。

```powershell
py -3.11 lab_log.py run -m "N1 真实合同与故障恢复回归" -- py -3.11 -m unittest test_pidon_contract test_pidon_contract_v3 test_pidon_contract_v4 -v
```

验收：C01–C15全部通过并有逐项证据；包含旧回归但不以总数定义完成。交付 `N1_REPORT.md`。若限时仍有缺口，G0不得PASS。

## N2：完整测量、独立参考与不能被标签骗过的 G0

### N2.1 指标与参考上下文

- [ ] E0=1V/m，L0=.05m，H0=E0/Z0；curlE0=E0/L0，curlH0=H0/L0。拟合R按物理未加权SSE/target_ss；非零目标不删近零分量。
- [ ] 场主范数使用E/E0、H/H0和各分量实际Yee对偶体积，排除硬源Ez自由度；等价于原eps0/mu0加权比值。保存分子/分母/单位/支持数；A_fixed按v2已登记归一化公式，不改分母mask。
- [ ] 恢复普通masked MAE/max字段 `nmae`；若保留体积加权版本，命名 `volume_nmae`，不能把后者直接送入原nMAE门槛。
- [ ] 分栏 `mre_eq5_physical`、`mre_nonzero_diagnostic`、nMAE、relative_L2、physical_SSE、volume_weighted_SSE、严格零个数/近零贡献。Eq5严格零处为|pred|，其他为|pred-ref|/|ref|，单位记录明确。若输出归一化口径另测，必须另名，不宣称已还原论文MRE。
- [ ] 重新生成同协议8192步double参考缓存：原 `PECCavity.step(...,src_mode='hard')` 每步保留其原H作为后续状态，仅在测量副本补H半步，不重复E或源。与#138已验证的同序构造交叉核对128步。
- [ ] 峰值与测量使用同一hard-source mask/体积。保存全时长总范数峰值、E/H组峰值、Ez空间全时长峰值、3条源外波形和登记快照；源码/配置/数组hash齐全。峰值仅验收使用，不反馈到训练目标缩放/输出还原。
- [ ] 总弱场为reference范数<全时长峰值的1e-6；用误差绝对范数/峰值<=1e-5。分量有效性用其归一化L2与所属E/H组三分量全时长峰值比较1e-6，否则相应绝对误差/组峰值<=1e-5。严格零峰值说明N/A和固定尺度规则，不添加epsilon造好分数。
- [ ] 探针固定(12,12,13)、(8,10,12)、(21,19,18)乘网格间距，Ez offset=(0,0,.5)三线性插值。整段L2不事后平移缩放。probe peak<全域全时长Ez peak*1e-6则无效；晋级至少2个有效且含论文点。

### N2.2 数值认证矩阵

| ID | 检查 | 完整要求 |
|---|---|---|
| M01 | 常量/线性curl-E及curl-H | double误差<=1e-10，位置/符号/每个支持点正确 |
| M02 | x/y/z离散平面波及div(curl) | E/H双路径，真实adapter，无解析截断误差混淆 |
| M03 | 输出支持 | learned/analytic_boundary/uncovered逐点互斥并集，uncovered=0；低/高PEC分别查 |
| M04 | 体积/硬源mask/插值 | 边界坐标决定1/2、1/4、1/8；源点显式排除；非整数物理位置可算出预期 |
| M05 | 指标手算反例 | 瞬时/全时长弱场不同判定，普通/加权nMAE不同，Eq5严格零分支不同于非零均值 |
| M06 | float64生产精确控制128 | 每步Q<=1e-10（严格零用固定尺度），double参考，全记录 |
| M07 | float32生产精确控制128 | 每步Q<=1e-4，对照仍double，完整第64步磁盘恢复 |
| M08 | 恒零curl替身 | 通过真实Solver.step两次训练调用，观测无传播，必须被全场/探针验收拒绝 |
| M09 | 独立仅硬源场替身 | 每时刻从零六场构造仅源自由度，不复用zero-curl子步分支；单独计数并必须拒绝 |
| M10 | H错半层负例 | 相同reference原H不补测量半步，必须被验收拒绝 |
| M11 | 精确控制落盘/恢复 | M06/M07第64步写完整状态，销毁Solver并从文件新建，验证恢复后的全128行、源索引、优化器/参数/场身份 |
| M12 | double全时长cache | 峰值可以从流式过程重算，hash/物理协议齐全；不只是检查文件存在 |
| M13 | 验收器自身负例 | 缺行、重复ID/sequence、错数值、错hash、空测试表、漏一个required ID、无probe、control伪装DCO，全应拒绝 |

- [ ] G0 required IDs明确为C01–C15和M01–M13。N3新增训练规则的H01–H08在其后认证；通过G0不代表新优化规则已经验证。
- [ ] `g0_verifier.py` 从JSONL、checkpoint读取信息，重算所有时刻最大值和判决。每项比对实际run_id/协议/源码/证据hash，必要ID集合精确覆盖，缺任何一项不得PASS。
- [ ] 科学负例的预期是“该数值控制被拒绝”，不是强求整个程序崩溃；保存拒绝发生时刻和原因。控制输出固定 `control_only=true`，不能进入DCO列。
- [ ] 验收器最终还执行#173两种破坏输入的拒绝测试，不修改原控制文件，使用隔离副本。

```powershell
py -3.11 lab_log.py run -m "N2 完整G0数值认证与独立参考" -- py -3.11 night_runner.py --stage g0 --root evidence/gpt6_plan_v4_night
```

本命令入口在本阶段实现后运行，不假称当前已存在。交付 `N2_REPORT.md`、`G0.json`、`required_g0_checks.json`、逐步六场/探针表。只有真实G0完整PASS才执行N3正式候选。

## N3：唯一新候选——末层最小二乘一次，再 Adam

### N3.1 数学与接口（禁止擅改成其他候选）

设网络最后一层输入为32通道特征 f_i，归一化输出为 `w_k @ f_i + b_k`。固定其余权重后，每个curl分量的真实有效支持构成矩阵 X_k=[f,1]，靶值为该分量物理Yee curl乘Lc/a；a、Lc必须由生产predict的**padding后输入**获得，不能用另算的未padding RMS。

通过最小化 `||X_k beta_k - y_k||²` 拟合三组33维系数。三分量独立最小二乘也最小化同一总SSE，因为目标能量分母不依赖参数。完成后写回普通head参数；推理依旧只调用网络，不读取Yee答案、缓存curl或求解器。

采用 CPU float64 `torch.linalg.lstsq(..., driver='gelsd', rcond=1e-12)`，无ridge、不扫rcond、不根据结果换driver。该接口可返回秩/奇异值；固定rcond避免跨版本默认变化。实现前对本机torch跑极小兼容性回归，不升级依赖。参考：[PyTorch官方lstsq文档](https://docs.pytorch.org/docs/2.14/generated/torch.linalg.lstsq.html)。

```python
def solve_component_head(feature, target_normalized):
    # feature: [channels, nx, ny, nz]，已按该分量真实target支持裁剪。
    x = feature.detach().to(device='cpu', dtype=torch.float64).flatten(1).T
    y = target_normalized.detach().to(device='cpu', dtype=torch.float64).reshape(-1, 1)
    x = torch.cat((x, torch.ones((x.shape[0], 1), dtype=x.dtype)), dim=1)
    fit = torch.linalg.lstsq(x, y, rcond=1e-12, driver='gelsd')
    residual = x @ fit.solution - y
    return fit.solution[:, 0], {
        'rank': int(fit.rank), 'singular_values': fit.singular_values.tolist(),
        'normalized_sse': float(residual.square().sum()),
    }
```

- [ ] 用生产net.head的forward_pre_hook截获一次特征，运行原predict获取实际a/Lc/支持。hook在finally移除。禁止复制一套简化前向而漏padding/coords/scale。
- [ ] 分量target支持遵循现有实际curl-H各shape和curl-E边界划分，不按最小立方体截断；拟合前记录网络边界残差，更新场后另记PEC投影值。
- [ ] 求解一次后原子提交三行head.weight/bias；`head_commit_count=1`，`linear_solve_calls=3`，随后最多499 Adam，全网络lr3e-4。记录总提交=`head_commit_count+adam_updates`。
- [ ] 若当前参数已达停止条件，直接0更新返回；若完整零输入/target，沿已认证捷径。非零无旋场仍走真实目标拟合，不能手写head=0旁路。
- [ ] 每个目标只准一次head提交，包括恢复；进入下一物理子步才有下一次目标配额。不允许每10/50更新重复线性拟合，也不加入LBFGS。
- [ ] head改变后，删除该head.weight/head.bias各自的整个Adam参数state，包括step、exp_avg、exp_avg_sq（若有max_exp_avg_sq也删除）；其下一次Adam本地step从1开始。其余参数的step及moments完全延续。独立预算账本的累计Adam更新数绝不重置，不能从这些被重置的局部step推算总消耗。固定状态初始Adam为空；实际滚动轨迹也遵守这一明确规则。将清除动作及字段纳入可恢复状态。
- [ ] 求解/训练/SSE统计时间计入每目标360秒。写回float32参数后实际SSE若高于原SSE*(1+1e-6)+target_ss*1e-12（零target改用count*curl0²*1e-12），或参数非有限，保存原状态/试解/坏输出，标 `head_numeric_failure`；不换solver/rcond补救。
- [ ] 所有最终判断从磁盘reload后原predict得到；R应满足数值一致性`abs(R_disk-R_saved)<=1e-9+1e-5*abs(R_saved)`且二者均通过科学门槛，否则证据不合格。

### N3.2 新规则认证H01–H08

- [ ] H01：合成满秩X,y可解析回收系数，double预测相对L2<=1e-10。
- [ ] H02：秩亏及严格零目标，有限解、秩/奇异值齐全，显式重算残差，不读取可能为空的lstsq.residuals当0。
- [ ] H03：真实DCO tiny网络，截获feature与原head重建前向相对L2<=1e-6；验证padding后a和单位映射。
- [ ] H04：每分量不同shape、PEC高低面、源mask互不混淆；只训练支持内参数，不能丢有效点。
- [ ] H05：初始达标0更新；head达标为1提交0Adam；head未达标最多1+499，恢复不会重做head。
- [ ] H06：在head提交前/后注入中断：前者无正式提交，后者磁盘恢复从Adam阶段继续；无确切提交记录时终止自动恢复，不双算/漏算。
- [ ] H07：head参数float32写回后最终R与实际磁盘纯推理一致；一个固定输入训练后换另一输入，关闭Yee target调用仍可前向，证明无target输出缓存。
- [ ] H08：新规则中断与连续tiny训练的参数、head/Adam计数、RNG相同。逐字段确认head参数本地step和moments重新初始化，非head参数的step/moments不变，预算账本累计Adam不变；新增optim字段全部进入canonical config。

```powershell
py -3.11 lab_log.py run -m "N3 唯一末层拟合规则的数学、计数及恢复认证" -- py -3.11 -m unittest test_head_lstsq -v
```

任何H项失败，不开始正式候选；不将tiny模型成绩当正式DCO成绩。

- [ ] N3接入会修改生产Solver，因此正式候选前必须用N3最终源码快照重新执行C01–C15、M01–M13和H01–H08。这里直接选择完整重认证，避免由执行者自行裁定哪些测试受影响；控制/测试本身计算便宜。此重认证计入N3的45分钟实现窗口，不计正式候选1800秒计算额度，但计10小时总墙钟。保留N2的旧版本G0，另存G0_after_head_integration.json及全部新run_id/hash。全部通过后冻结源码，N3正式拟合和N4晋级均只认这一最终版本；不能拿接入前G0的PASS标签给接入后源码背书。

### N3.3 开发与固定验证

冻结：seed=20260913，n=31、side=.05m、dt=3.075e-12、Gaussian fmax15GHz、hard源位置(15,15,15)、原主权重hash、L4/base32/direct、h_shift=True、H/E独立、RMS/cellsize、lr3e-4、无LBFGS、每目标500总提交/360秒、候选全部计算<=1800秒。

- [ ] 开发43、96，验证16、300、600、192、450、900。固定状态来自已认证double参考，原six-field/target/source/mask存盘。split登记在查看候选成绩前。后六点只是固定覆盖，不能称统计独立数据。
- [ ] 每个固定状态分别从主权重全新初始化，不继承另一个固定状态训练结果。baseline只纯推理，且不调用可能更改进度的inner_train。保存初始R、head后R、最后R和全过程曲线。
- [ ] source_index=step-1；固定诊断 `origin=fixed_reference_state`、`accepted_steps=0`、`current_time_layer=source_index`，记录参考场的实际E/H时层。不能把43标签写成连续接受43步。oracle的phase明确`oracle_after_E_source`且禁止恢复到正式rollout。
- [ ] 先H→用预测curl-H更新E→只加一次源→在实际E上构造Yee靶值训练E→更新H。H失败时accepted_field_metrics=null；另存同before_H阶段六场/源外诊断。E失败时对比after_E_source阶段，不冒用完成H后的参考。
- [ ] 若一个开发状态H失败，仍允许完成另一个开发状态及该失败状态的一次oracle E诊断，预算归该候选全局；不因此启动验证。oracle E使用新的原主权重，只作诊断，角色/计数独立。
- [ ] 保存分量物理R/SSE/MSE/target能量、pred/target peak、RMS a/Lc/floor、内部/一层边框误差、投影前后边界、div(curl)、实际总更新/Adam/head/求解次数、同阶段六分量/3探针、phase和恢复资格。
- [ ] 在43步H/E做输入/target共同缩放1e-3/1/1e3纯前向，报告逆缩放差异/floor，无额外训练。
- [ ] 两开发状态H/E顺序都过R、单步A_fixed<=1e-3及支撑/零场规则，才进入六验证状态。验证一旦FAIL，余下验证仍可在1800秒内完成，以记录覆盖；无调参、无重试、无晋级。
- [ ] 全部八点PASS才G1 PASS。开发与验证最终文件从磁盘重新计算；空任务列表、NOT_RUN和oracle不能被all()当通过。
- [ ] 耗时与#166/#129分别列出，三种训练规则不同，不能宣称公平等FLOPs比较。额外效率门保持原“候选不超过基线两倍”用于开发H43/H96：各自完整拟合（含head CPU求解，不含单列I/O）的时间<=2*对应v2原始H500时间；原值由原R4_development.json读取，不能重跑基线。超时即EFFICIENCY_FAIL，不晋级。

```powershell
py -3.11 lab_log.py run -m "N3 唯一head_lstsq_once_adam499开发与按门槛固定验证" -- py -3.11 night_runner.py --stage fixed --root evidence/gpt6_plan_v4_night
```

交付 `N3_REPORT.md`，包括旧500-Adam FAIL、新规则判定、oracle分栏、全表、残差/时间曲线。G1失败仍有价值：不要据此修改门槛或宣称整个网络不可行。

## N4：按原门槛推进新连续轨迹

### N4.1 前置与顺序

- [ ] `night_runner.py`在启动/恢复每段时重新验证G0、H01–H08、G1证据hash与当前源码。训练源码中途改变会使既有认证失效；修复只能重做受影响的工程测试，不能重开已失败科学候选。
- [ ] 主seed20260913，从零场和原主权重开始，启用与固定验证完全相同的新规则。64→128在同一轨迹内继续；64开发全过程预算最多60分钟，128阶段最多60分钟，并扣掉本计划总墙钟。
- [ ] 128通过后先独立seed20260914从零场至少128步，最多60分钟；通过才恢复主seed向1024。这样重复性失败不在数小时长跑后才暴露。严格记录源全局索引，第二seed不是延长第一条轨迹。
- [ ] 主轨迹128→1024新增最多4小时，并受t0+9h30截止。每个子步最多1head+499Adam/360秒。段切换仅提高requested_steps，不能修改数值配置或每目标额度。
- [ ] 1024全部G2通过后再算8192剩余成本。不得从旧v1/v2/v3或固定状态checkpoint续成轨迹。

### N4.2 数值门槛

- [ ] 每个已接受子步在实际参数提交后测得最终R<1e-4或合法零场规则；保存参数摘要hash、输入/targethash、计数和R以追溯，不以更新前loss判定。常规完整状态两槽滚动，另按2.3每256步和关键节点永久保存。所有实际保留的最终/失败/阶段checkpoint必须做磁盘纯推理回读，并另列R_disk。为回读H/E各自最后拟合R，checkpoint需带各自当次fit_input和fit_target：不能拿完成H更新后的场去重算之前H拟合的R。只存六场的轨迹快照不声称能回读对应模型，不把内存复算冒称每步都做过磁盘回读。
- [ ] 活跃时刻全场Q<=5%；各有效分量普通nMAE<=1e-2；弱场/弱分量按N2全时长峰值绝对误差<=1e-5。任何硬门失败停止该正式轨迹，不继续带失败跑满。
- [ ] 至少两个有效源外探针含论文位置，整段波形相对L2<=5%，无事后平移/重标幅。300/600/900六场快照齐全，源波形作为输入单列。
- [ ] 在1024，接受步897–1024的RMS-Q不高于紧邻的769–896两倍（数组零基切片分别[896:1024]与[768:896]）；不能拿最初128步当分母窗口，不能丢弃不利点。两seed128均满足同一指标。上述全部通过才称G2机制层复现。
- [ ] 8192仍保持逐步G2，另对五模频率要求解析<=0.5%、匹配FDTD<=0.2%，可解析峰谱幅差<=1dB，活跃段交错层能量代理相对误差<=10%。FFT窗/去均值/峰选用原P7规则冻结，不看结果后改窗挑峰。谱分辨率不足则INCOMPLETE而非插值造通过。
- [ ] MRE/nMAE持续分栏；8192只在全部G3通过时称该优化变体的工程长程复现。原论文G4和训练后复用G5本夜未被本计划授权展开，记NOT_RUN；现有报告不能用G2代替G4/G5。

### N4.3 预测耗时与停止

- [ ] 每完成64/128/1024保存逐完整步墙钟、更新分布和峰值资源。8192预测用1024末256完整步的耗时P90，包含优化、CPU求解和日志I/O，不拿零场首步均值外推。

```python
remaining_seconds = (training_deadline_utc - now_utc).total_seconds()
estimate = 1.25 * (8192 - accepted_steps) * p90_last_256_step_seconds
may_extend = g2_pass and estimate <= min(8 * 3600, remaining_seconds)
```

这是调度估计，不保证完成；1024后每128步更新预测，若预计越限则在下一个可保存边界停止。磁盘估计也必须通过；不能因10小时长窗口忽略单目标/分段上限。

- [ ] 首次失败状态保存网络raw/safe、输入/target、分量/区域误差、实际预算与source/phase。只做纯前向定位，不新增原P4-B R1e-5训练分支，不再扫参。若触发的是磁盘资源问题，先按2.4执行已授权清理；只有释放后预算/恢复身份仍合格时才继续同一分支。
- [ ] 若时间不允许8192，保留1024验收，不启动大概率无法完成的长程去掩盖G2成果；报告 `8192 NOT_RUN: forecast_exceeds_remaining_window`。若已合法开始后估计恶化，中断状态记 `INCOMPLETE_RESOURCE`，不是NOT_RUN也不是FAIL科学门。

```powershell
py -3.11 lab_log.py run -m "N4 新规则连续轨迹与分段门槛" -- py -3.11 night_runner.py --stage rollout --root evidence/gpt6_plan_v4_night
```

每个完成段即时落盘中文报告，不能等全夜结尾才写第一份。

## N5：失败后仍可完成的两项独立诊断（无参数更新）

### N5.1 固定特征能表达多少旋度

适用：G0/G1/轨迹停止后，或不再能启动长程但还有时间。优先用本夜失败模型，其次只读v3四个失败权重；旧权重不写回。最多30分钟、4个固定角色状态，一次CPU least-squares/角色，结果是“冻结特征空间下的拟合下界估计”，不是整个DCO的理论极限。

- [ ] 对43/96的H及oracle E，读取原输入/target，纯前向保存末层特征。计算当前末层R与同一特征的最小二乘R；不把解安装进正式模型，不执行Adam。每分量单列target能量/秩/奇异值/列尺度。
- [ ] rcond固定1e-12，求解结果残差必须显式重算；有限精度、截断秩和float32回写误差都注明。没有真正达到全空间数学最优时不能称严格下界。
- [ ] 如果影子LS能降至R<1e-4，仅支持“当前特征已有足够表达力，旧head未充分拟合”这个局部解释；若不能，只证明当前固定特征不足，不证明改变特征的全网络训练无效。
- [ ] 输出第三分量近零目标的绝对误差及投影前后变化。只用既有输入，没有新候选、没有头部反复交替训练。

### N5.2 P5 实际标签来源与梯度链路

最多60分钟。先读v1/v2/v3 review的数据路径/hash和已有floor结果；不重复已经证明没触发的128×3 floor扫描，不重训四样本。

- [ ] 对旧四样本逐一列出可验证来源：NPZ键、shape、dtype、hash、原生成脚本/参数/seed能否匹配。缺少平面波参数时明确 `LABEL_PROVENANCE_INCOMPLETE`，不凭近似curl一致就认证旧解析标签。
- [ ] 新建独立微型解析平面波样例，固定seed20260913、n=7，保存波数/方向/相位/偏振/坐标；解析curl按公式生成。分别在三个轴验证连续解析式和离散符号，不能把两者逐位相等作为通过标准。
- [ ] 以CPU double tiny网络、固定方向seed20260913检验真实训练loss方向导数。epsilon固定1e-5和5e-6两点，比较自动微分与中心差分，容差 `abs(fd-ad)<=1e-7+1e-4*max(abs(fd),abs(ad))`；两点是预登记精度诊断，不能扫epsilon挑最漂亮值。
- [ ] 对旧真实四样本另检查梯度有限性、各层grad norm/为零参数比例、输出到loss的连通性；不执行optimizer.step。缺元数据与梯度错误分开结论。
- [ ] 即使发现明确标签/梯度缺陷，本夜只保留最小复现/具体修复建议，不据此临时增加P5训练或修改N3候选。

```powershell
py -3.11 lab_log.py run -m "N5 冻结特征表达与标签梯度无更新诊断" -- py -3.11 night_runner.py --stage diagnostics --root evidence/gpt6_plan_v4_night
```

交付 `N5_REPORT.md`。N5无需训练链路认证通过，但自身数值链路不可信的子项应记INCOMPLETE；不能转成正式成绩。

## N6：夜末验收与交接

- [ ] 在 `C:/PI-DON/night_evidence.py` 实现每阶段数值重算入口；verify_claims新增Y0完整G0、Y1新规则完整固定门、Y2主1024+重复128、Y3新8192。预先写期望，使用真实值判定，不搜索中文报告关键词。
- [ ] `make_night_report.py`与verify_claims调用同一入口，生成中文总表、残差/更新曲线、六分量曲线、三探针波形和已执行快照。未跑的图不造空曲线或借旧图伪装。
- [ ] 每个阶段/任务一行：status、stop_reason、lab_run_id、起止UTC、source/config/input/checkpoint hash、origin/phase/source_index、actual Adam/head/solver/closure counts、loss_objective、R_disk（若实际回读）、physical_SSE/MSE、六分量MRE/nMAE/L2、A_fixed/Q、source-outside probes、可恢复资格、总资源。另报存储预测/实占、已保留永久checkpoint、清理路径与实际释放量；未清理则明确0。
- [ ] 用 `PASS/FAIL/INCOMPLETE/NOT_RUN` 区分科学通过、已测未达门、已开始但因工程/资源不完整、根本未执行。stage的“实施完成”与科学门是否通过分别存字段。
- [ ] 回核原始资产hash，原失败全部存在；列出新失败和所有被跳过的项。最新STATUS置顶指向本夜报告，旧历史保留；X0不因新版本通过而改回旧v3PASS。
- [ ] 在训练截止时先停止更新并提交现场；最后30分钟跑纯验收/出图/记录。到10小时硬截止不再启动新长任务，输出已有完整结果和剩余缺口。

```powershell
py -3.11 lab_log.py run -m "N6 夜间证据重算、中文报告和图" -- py -3.11 make_night_report.py --root evidence/gpt6_plan_v4_night
```

```powershell
py -3.11 lab_log.py run -m "N6 更新结论核对表" -- py -3.11 verify_claims.py --pidon-v4-night --md
```

`--pidon-v4-night`在N6添加，并测试缺失阶段输出NOT_RUN/INCOMPLETE不能PASS。不要使用`--run`触发本夜范围外的历史实验。若提交git，只逐文件add已审核的代码/小型hist/报告；不提交大权重或无关用户文件，不要求清空dirty工作树。

最终交付：`FINAL_REPORT.md`、`stage_status.json`、`acceptance.json`、`night_manifest.json`、`resource_ledger.jsonl`、`required_g0_checks.json`、各阶段中文报告、原始数值/图脚本、实际checkpoint恢复说明。用户早上应能先看一页总表，再按run_id逐项验收。

## 七、给下一会话的 goal 执行指令

以下是发给 agent 的自然语言指令，不是 PowerShell。用户先在下一会话开启 goal 模式，再发送；当前会话只准备计划，不启动它。

```text
目标：请执行 C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-10h-goal-night-plan.md 的v4.1存储修订版，在从首次执行开始累计不超过10小时的墙钟内，完成其中全部具备前置条件的工作，交付可逐项验收的中文证据包。先读 evidence/gpt6_plan_v4_review/REVIEW.md、audit.json、storage_revision/REVISION.md、计划和实际源码，再按N0–N6推进。

我授权本计划明确登记的一种新训练规则：保持原DCO架构、主权重、h_shift=True及全部科学门槛，每个目标最多1次末层最小二乘联合提交+499次Adam，总参数更新不超过500。它是新优化规则实验，不是论文已确认算法；原500-Adam、P4-A和H位置候选失败都保留，禁止恢复旧失败权重重领预算。除此之外不增扫参、结构候选或P5长训。

先补可信G0和新规则专门认证，再做43/96开发与六个固定验证；全部过门才从零场按64→128→第二seed128→主1024→按实测剩余成本决定8192推进。不得只凭测试计数、报告关键词或PASS标签认证。G0/G1或轨迹停止后，连续完成计划内N5无更新诊断和N6验收，不需要例行确认；不能带失败继续正式轨迹。

第一次建立持久10小时deadline，恢复沿用同一deadline和全部累计配额；第9.5小时停止新增训练，预留最后30分钟验收。当前清盘后约25.3GiB空闲，以启动时复测为准；按v4.1存储修订实施两槽滚动＋主轨迹每256步和关键阶段完整保存，正常新增证据预算16GiB，留5GiB系统余量＋1GiB紧急空间。若仍不足，我授权按计划2.4自主清理已识别、可再生成、非活跃的软件缓存/临时数据，无需再次确认；先留精确清单，清理和实际回收量记入lab_log。不删除个人文件、软件数据库/账号/恢复数据、项目数据/权重/失败证据或当前依赖环境，不卸载软件。空间足够就不清理。

保留所有历史资产和新失败现场。所有出数运行包lab_log，逐阶段中文报告，记录真实Adam/head/求解/closure次数、最终物理R和实际磁盘回读、六分量、源外探针、source/phase和恢复资格。MRE/nMAE分栏，Yee/几何控制不得算DCO成绩。

在已有goal中执行；若当前没有goal，则以以上有限目标创建goal，不设置我未指定的token预算。没有前置的阶段记NOT_RUN，已开始但资源中断记INCOMPLETE。只有本夜适用任务、合法停止记录和最终证据包全部交付后，才可将夜间goal标为完成；这不等于论文复现成功，最终须单列G0/G1/G2/G3和论文复现状态。遇计划外结构问题、明确资源或科学停止条件时保存现场，完成仍获授权的独立分支后报告；不要为凑满10小时空转或擅自开新实验。
```

**Next skill:** `$superpower-executing-plans`。执行方式已由用户指定为下一会话goal连续运行，不再询问“是否开始”或另外开任务。
