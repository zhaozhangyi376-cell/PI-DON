# PI-DON：补齐 G0，并检验 H 交错位置修正

> **For agentic workers:** 使用 `$superpower-executing-plans` 按项实施。本文件承接 v1/v2，按用户授权连续完成具备前置的分支，不要求例行确认。已执行的停止点复核与尚未执行的修复、训练严格分开。

**Goal:** 补全真实 G0 验收，以一个由几何恒等式支持的 H 输入位置修正，判断当前网络能否通过原 G1，再决定短程/长程。

**Architecture:** 保留 DCO L4/base32/direct、主权重、cellsize/RMS、Yee 离散、独立 H/E 网络和原科学阈值。先修记录/恢复与验收器；随后仅将 H 的输入索引改为现有 `h_shift=True` 所定义的正确 E 型相对布局，E 路径不改。精确差分只用于 target/控制，不能加入网络输出。

**Tech Stack:** Windows PowerShell、Python3.11、torch/numpy/matplotlib/unittest、lab_log；不增加框架。

**本文件状态：** 计划已写入，实施任务 A1–A5 **NOT_RUN**。本轮仅完成 A0 审查与 CPU 证据复算（#137–#139）。

**上位协议：** `C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-evidence-and-reproduction-plan.md` 与 `C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-contract-repair-and-gated-continuation.md`。本文件只修订执行遗漏及新增一次有几何依据的输入 adapter 比较，未修改其余科学门槛。

---

## 1. 为什么修改，修改到哪里

v2 停止避免了浪费，但上次交付把“19项测试通过”扩大成“完整G0通过”。#137现在实际复现四个合同反例：累计时间已超预算仍进行更新；恢复增加LBFGS预算未被拒绝；异身份运行能写入已有目录；LBFGS被中断后丢掉先前完整接受的更新。P4-A checkpoint本身还漏记200 Adam/200 closure，不能当正式恢复入口。

这些缺口**不解释**#129/#132已经观测到的拟合失败。重载权重得到第43步Adam500 R=1.278613e-3、第96步R=9.224233e-4，P4-A R=5.061262e-4；仍保留FAIL。#132没有触发closure异常回滚，不允许借修复该异常为理由再跑一次相同P4-A。

存在一个具体且廉价的新方向：H与E位于不同的交错位置。`gen_data.py`的E输入位置是Ex=(i+1/2,j,k)，Ey=(i,j+1/2,k)，Ez=(i,j,k+1/2)。H输入取以下三块后，相对于共同原点(dx/2,dy/2,dz/2)，恰好具有相同布局：

```python
core_H = torch.stack([
    Hx[1:n+1, :n, :n],
    Hy[:n, 1:n+1, :n],
    Hz[:n, :n, 1:n+1],
])
```

相同原点下，curl-H的目标位置与预训练curl-E输出位置也一致。#139用精确前向核检验完整有效支持：旧输入相对L2=1.441945，shift后=0。这证明**转用预训练布局所需的位置对应**，不证明神经网络必然收敛；旧输入也可能经充分重训学会另一映射。因此把它列为有依据的单变量候选，不能宣称已找到失败的唯一根因。

| 项目 | 调整 |
|---|---|
| R、A_fixed、G2/G3/G4、弱场、频谱及种子 | 全部保持，不能放宽 |
| G0 | 撤回完整通过；按机器可读逐项证据补齐 |
| R2参考 | #138已证明原step+测量H半步与同序参考等价；仍补生产端到端和故障对照，不认定旧参考数值错误 |
| v2失败 | 保留为特定权重/位置/预算下的局部FAIL，禁止覆盖 |
| 新训练 | 仅新增位置修正候选，全部从原权重开始；不恢复旧失败权重重新领预算 |
| P4-A | 不新增同配置重试，不再扫优化器/lr；原200 closure记录不清零 |
| P5 | 四样本误差FAIL保留；实际标签来源/梯度完整诊断仍不充分，不宣称已经排除所有实现问题 |

## 2. 已做与没有做

- [x] A0：CPU微型反例、四份保存权重零更新复算、43步H/E共同振幅测试、参考时层对照、H布局恒等式、P5元数据/归一化往返。全部通过lab_log记录。
- [x] 保留#137错误使用参考默认加法源的子测；#138显式hard source后重新验证。该子测修正不影响#137其他结论。
- [ ] A1：真正修复合同、记录器与验收器。
- [ ] A2：完整G0。
- [ ] A3：位置修正候选开发与固定验证。
- [ ] A4：符合前置后64→128→1024→8192。
- [ ] A5：按条件处理P5及论文其他验收；未满足条件不得启动。

本轮未改生产训练代码，未增加正式DCO优化器更新。未来实施结果写 `C:/PI-DON/evidence/gpt6_plan_v3/`；本轮复核在 `C:/PI-DON/evidence/gpt6_plan_v3_review/`，两者分开。

## 3. 预算与资产规则

1. A1/A2使用CPU微型测试；工作时间预期1–2小时，不当作GPU配额。全8192步**参考FDTD峰值预计算**最多10分钟CPU，只流式存峰值、探针、登记快照；不启动DCO8192。
2. A3是明确登记的**新H位置假设**，不是v2 resume；开发与六个验证状态合计最多30分钟GPU。每目标仍Adam lr3e-4、最多500次、最多360秒；无LBFGS、无lr备用、无随机重启、无坐标/网络扫参。
3. A3按固定候选和固定输入目标记录累计预算；异常重启只能使用剩余额度。一次目标完成后不得重领额度；非有限或max_updates停止对象禁止自动训练恢复。
4. v1/v2实际成本单列。A4沿用v2/原计划64步等诊断总60分钟、128步60分钟、1024新增4GPU小时、重复seed128步60分钟；8192剩余P90预测<=8GPU小时；P8总墙钟2小时。不能通过新目录或恢复重置。
5. 每次出数均包lab_log；实验前保存**完整执行源码副本**、dirty diff、配置与输入哈希。每个独立run使用新目录；同一run恢复须身份匹配。原权重不覆盖。

## A1：补完整工程合同

**修改文件：** `C:/PI-DON/pidon_solve.py`、`pidon_recording.py`、`pidon_contract.py`、`verify_claims.py`。
**新增：** `C:/PI-DON/test_pidon_contract_v3.py`、`evidence/gpt6_plan_v3/contract_test_results.json`。

### A1.1 先把本轮反例变成失败回归

- [ ] 将 `audit_v2_stop.py:contract_probes` 的四个实际反例拆为unittest。先记录当前FAIL，后修复；不要把“当前会出错”作为最终通过条件。
- [ ] 必须具备以下断言；按本轮实际接口取测试数据：

```python
self.assertEqual(fit_after_exhausted_time.n_updates, prior_adam_updates)
self.assertTrue(lbfgs_config_conflict_rejected)
self.assertTrue(foreign_run_directory_rejected)
self.assertTrue(torch.equal(restored_parameters, last_completed_lbfgs_parameters))
```

### A1.2 消耗和恢复为同一状态机

- [ ] 子步账本至少保存 `time_layer/phase/which/attempt_id/optimization_phase/adam_updates/lbfgs_steps/closures/elapsed_s/stop_reason/resumable/pending_fit_H`。保存参数、Adam和LBFGS各自状态、RNG、source_index。累计值在**每个完整更新边界**写入内存，不能仅inner_train返回后更新。
- [ ] 时间检查使用 `prior_elapsed + current_attempt_elapsed`。到达预算时零新增更新；停止状态仍允许一次纯前向最终核验，但不得因此进入优化器。保存与日志时间统计单列，不把I/O重算为GPU训练时间。

```python
remaining_updates = max(0, registered_max_updates - progress['adam_updates'])
elapsed_total = progress['elapsed_s'] + (time.perf_counter() - attempt_start)
time_exhausted = registered_seconds > 0 and elapsed_total >= registered_seconds
```

- [ ] LBFGS每次完整返回后更新最近accepted快照（网络**及LBFGS optimizer**）。closure中断前保留trial raw；只回滚本次未完成调用，不能回到整个LBFGS阶段之前。closure消耗即使回滚也计入累计预算。保存最终状态后从磁盘重新推理得到R。
- [ ] 显式检查gradient和parameter有限性；非有限raw含故障值及已消耗额度，safe含可诊断有限状态。nonfinite失败禁止自动重试；允许恢复的interrupt须从当前阶段继续。
- [ ] zero_input捷径检查完整物理输入与target均严格为零，不能只检查裁剪的core。非零零目标按固定物理尺度两项检查；非零target最终停止按保存参数的全量物理SSE/target_ss判定，优化目标或分量加权值不能冒充R。
- [ ] 所有数值/结构字段纳入canonical config，包括LBFGS、dtype、source模式/索引、真实checkpoint结构/归一化、协议hash、共享网络。缺字段旧状态判非正式、不得用默认值补成合法恢复。正式入口先读checkpoint的真实配置再建Solver。
- [ ] `--config`新增合法LBFGS字段。显式CLI数值与config冲突时拒绝，不悄悄被覆盖；恢复只允许总steps、路径和已验证的设备迁移。`--steps`是总接受步数，不能是新增步数。禁止改容差和优化预算。
- [ ] 增加中途保存钩子：第2个Adam更新后安全中断、保存恢复，比较不间断轨迹；再覆盖E_pending、完整完成物理步、LBFGS调用间中断。比较六场、两个网络、两个优化器、RNG、H已通过记录、时间层、源次数、全部计数；不得使用max_inner=0的失败重放充当这些测试。

### A1.3 记录器、身份、崩溃

- [ ] `RunRecorder`显式区分new/resume；元数据含唯一run_id、protocol/source/config/input哈希。new遇非空目录拒绝；resume遇身份不匹配拒绝。不得只因metadata已存在就跳过检查。
- [ ] 每行含唯一attempt_id/sequence_id，checkpoint记录最后提交id。保存两份不可变完整checkpoint后原子更新latest索引；失败raw按attempt命名，不覆盖之前raw。
- [ ] 模拟写临时文件失败、替换索引前后中断、JSONL尾记录已写但checkpoint未提交。至少一份完整状态可恢复；保留未提交尾部并分类，不删除证据或重复认领物理步。
- [ ] v2 P4A两checkpoint明确`diagnostic_only`：opt_H显示200，但fit_progress全0，无LBFGS状态。保留原文件，另写分类索引，拒绝当作v3续训资产。

### A1.4 验收器

- [ ] 不再读取报告关键词来判通过，不用一个P4A布尔值认证G1。机器结果必须关联run/源码/协议hash、测试名称、observed/expected。
- [ ] 必测：空任务、少96、少E、重复43、错seed、超预算、R为NaN/null、只有43H通过，均不能G1 PASS；显式零输入/零目标另按合同判断，不用null统一判错或判对。
- [ ] `test_stop_review_claims.py`仅认证非零开发任务的覆盖反例；不得直接复用为完整G0/G1验收器。

```powershell
py -3.11 lab_log.py run -m "v3 A1 停止恢复与故障记录合同" -- py -3.11 -m unittest test_pidon_contract test_pidon_contract_v3 test_stop_review_claims -v
```

**验收：**所有上述生产行为测试PASS、源代码/测试结果匹配。输出 `A1_REPORT.md`；工程通过不等于DCO科学通过。

## A2：补齐物理测量和端到端 G0

**修改文件：** `C:/PI-DON/pidon_exact_control.py`、`pidon_contract.py`、`pidon_solve.py`；扩展`test_pidon_contract_v3.py`。新增`reference_cache.py`及命令入口。

- [ ] 参考使用原`PECCavity.step(src_mode="hard")`独立前進。测量副本使用当前参考E补H半步；下一参考步继续用未改的原H。#138已有等价证据，不必重写FDTD离散。
- [ ] 生产精确替身必须经过 `Solver.step→映射→PEC/source→metrics→recorder→checkpoint→恢复`，全部128接受步、float64/float32。每步记录六分量和源外三个探针；参考始终double。
- [ ] double Q<=1e-10、float32 Q<=1e-4；严格零参考使用固定幅值。常量/线性/三方向离散符号覆盖H和E；支撑计数从真实mask计算，禁止直接写uncovered=0。
- [ ] 增加零旋度、只有硬源、故意错H半层三个负对照，均不得通过相同传播/场误差门槛。所有精确控制明确`control_only`，禁止正式配置走替身。
- [ ] 参考缓存使用同一31间隔/50mm/dt/硬源，流式预计算8192参考峰值，分别保存全六场加权峰值、E/H组峰值、Ez空间时间峰值和三探针；缓存绑定完整协议哈希，不在128/1024段改变分母。
- [ ] 实现原计划的弱场1e-6判定与绝对1e-5门槛、有效分量、有效探针；强源自由度在主统计掩码中排除。nMAE分母也必须来自声明的同一统计支持，保留含源辅助历史指标并标清。
- [ ] 逐分量保存式(5)MRE、nMAE、相对L2、SSE/参考能量/体积、严格零数与单位。A_fixed按v2唯一公式，Q和它各自独立字段。
- [ ] failed before_H/E_pending仅保存相位匹配诊断；没有完成整步则`accepted_field_metrics=null`，不把它与下一整步参考的误差拿来评分。
- [ ] 冻结机器清单 `required_g0_checks`，必须包含A1全部恢复/故障/身份测试，以及A2精度/支撑/时层/负例/峰值/弱场/mask；每项都有证据文件哈希与run_id。全量检查PASS才写`G0=PASS`，缺测就是INCOMPLETE。

```powershell
py -3.11 lab_log.py run -m "v3 A2 完整生产G0与负对照" -- py -3.11 -m unittest test_pidon_contract test_pidon_contract_v3 -v
```

**验收：** `A2_REPORT.md`、逐项G0 JSON、参考缓存、128步六分量/探针、控制恢复现场齐全。G0不全通过不执行A3。

## A3：只检验一个 H 位置候选

**修改：** `C:/PI-DON/r4_fixed_state.py`、`pidon_solve.py`；新增 `C:/PI-DON/h_layout_candidate.py`、`test_h_layout_candidate.py`。

### A3.1 冻结后才跑

- [ ] 配置：主权重`dco_lr1e3_300.pt`及R0同hash，L4/base32/direct、cellsize/RMS，独立H/E、h_scale=h_output_scale=1、h_shift=True、lr3e-4、R<1e-4、Adam<=500、360秒/目标，无LBFGS。主seed20260913。唯一语义变化是H索引块；不修改E/trunk坐标/target/物理输出还原。
- [ ] E抽块与H抽块集中在生产adapter函数；实际DCO推理、诊断和训练均调用它。用#139恒等式作为该adapter的回归，加非立方shape及边界附近输入。精确核仅测试使用。
- [ ] 新建`candidate_config.json`、预算账本、原输入和协议哈希。43/96开发；16/300/600原验证和192/450/900新增状态覆盖不参与调参。原v2记录只读。

### A3.2 两个开发状态，每个最多一对新拟合

- [ ] 从原权重重新初始化每个固定状态的H/E网络。先无更新记录H/E预测、分量R、物理SSE、目标能量、真实PEC mask/内部误差、归一化scale、div(curl)。43共同倍率1e-3/1/1e3测试使用实际adapter；#137无shift结果作为旧对照。
- [ ] 拟合H：max500/lr3e-4，逐10次和最终保存曲线。baseline复用#129同权重/同输入/同target的旧H500，不重新训练旧组。
- [ ] H通过：按其预测更新E并施加一次硬源；在**实际E**上造target、从原E网络开始拟合E，随后更新H。只该路径可形成顺序G1单步。
- [ ] H失败：不推进DUT，但允许在同状态**参考E**上做一次原计划遗漏的E拟合诊断，同样max500，明确oracle_only。它不能替代顺序E或G1；每状态最多一次E拟合，不同时追加oracle与sequential两轮。
- [ ] 保存最终网络/优化器、累计计数、真实相位、source_index、预测和target数组；从磁盘纯推理复算R。未完成物理步时A_fixed/Q不进入accepted成绩。
- [ ] 结果表逐任务：旧/新输入位置、原hash、time_layer、H/E、oracle/sequential、Adam数、final R/SSE/MSE、六分量、源外单时刻探针、phase、恢复资格、耗时。波形验收此时N/A。

**开发门槛：**43/96全部顺序H/E达到原R且A_fixed<=1e-3，预算合法，才做固定验证。不得凭H恒等式PASS、单独H拟合PASS或R下降倍数晋级。

**成本门槛的可比口径：**原文“完整候选不超同基线两倍”在旧基线无法完成物理步时没有完成步耗时。实施前明确比较相同固定拟合任务的训练耗时：H基线使用#129的27.794/27.918秒，E使用实际候选E任务的同一次训练（H位置选项不影响独立E网络，给定E输入/target后两配置是同一计算）。比较每状态 `new_H_seconds + E_seconds <= 2 * (old_H_seconds + E_seconds)`，并保留全部原始耗时。这个成本基线不是一条成功物理轨迹；不为失败基线编造完整步结果。2倍限值与绝对资源上限保持。

### A3.3 验证与失败归因

- [ ] 开发全部通过后冻结配置，对16/300/600/192/450/900各从主权重、独立固定状态开始，严格相同顺序与门槛；全体通过才G1 PASS。A3开发与验证共用30分钟。
- [ ] 任一失败仍保留其余已登记开发诊断，但不消耗留出验证调参。禁止额外学习率、P4-A重试和延长500。
- [ ] 报告必须回答：H的位置修正是否改善同任务残差；瓶颈是否转到E；误差主要在目标强/弱分量或边界/内部；最后100次是否仍下降。下降趋势仅作诊断，不自动延长预算。

预期分支：若H与E都过，进入固定验证；若H过E不过，记录E局部表示/优化瓶颈，不能再怪H位置；若H仍不过，说明位置对应正确仍不足以满足当前优化预算。以上均不证明网络全局不可学习。

```powershell
py -3.11 lab_log.py run -m "v3 A3 唯一H位置候选，G0前置与累计预算" -- py -3.11 h_layout_candidate.py --config evidence/gpt6_plan_v3/candidate_config.json --out evidence/gpt6_plan_v3/h_layout_candidate
```

该入口由A3实现，必须先验证G0 JSON、配置hash、预算。此时不能把尚未实现的命令当作已能运行。

## A4：只在完整 G0/G1 通过后继续

- [ ] 64步严格开发从零场/主权重/新candidate配置开始；不能从固定状态或旧失败轨迹续行。
- [ ] 64通过→128→同状态1024；第二seed=20260914从零场另跑128，主seed=20260913。源全局时间索引连续，不重放；恢复自动读checkpoint配置，无需重复手填数值参数。
- [ ] G2仍是所有接受子步R达标、活跃Q<=5%、有效分量nMAE<=1e-2、弱场<=1e-5、源外整段L2<=5%、至少2个有效探针含论文位置、300/600/900六场、末128段RMS-Q不超前段2倍。
- [ ] 满足G2/重复seed/耗时预测才8192；G3解析频率<=0.5%、FDTD频率<=0.2%、谱幅差<=1dB、活跃能量偏差<=10%，继续G2；G4/P8照上位计划。
- [ ] 若原允许的64步失败诊断（相同支持的R1e-4/1e-5、边界/divB）没有合格候选，停止且保存现场；不能无限循环。所有下游未跑状态明确NOT_RUN。

## A5：P5 的位置及最终停损

- [ ] P5宏nMAE=2.006568e-2的FAIL不撤回、不放宽1e-3。A/B floor未触发，不能用修常数作为重训理由；v2报告“同数值证明不同损失”的句子应更正为“在这批样本上权重相同”。
- [ ] 只有需要走P5支线时，先寻找这四条实际样本的原生成版本/RNG/波参数；不能只跑通用解析测试便认证旧标签。没有来源证据则INCOMPLETE。若从历史记录恢复参数，逐分量核对解析标签与Yee位置，不要求解析curl等于差分curl。
- [ ] 只有可复现的实际数据/梯度缺陷允许上位计划的一次修复后四样本重试；固定200→500、loss>=100倍下降与宏nMAE<=1e-3保持。配对新数据/非立方晋级/1000epoch仍需各自前置，不能用A3FAIL跳过。
- [ ] A3也无候选时交付具体阻塞报告；下一步若要换网络结构、输出形式、PDE离散、训练目标或预算，必须另立科学设计。不会为避免停止而继续训练。

## 4. 最终可验收交付

- [ ] `A1_REPORT.md`工程测试逐项证据；`A2_REPORT.md`完整G0。
- [ ] `A3_REPORT.md`全部实际拟合、失败、未执行验证、训练曲线/证据图；accepted状态不得混入oracle。
- [ ] 如果进入A4，每个里程碑中文报告和机器门槛；没有进入则NOT_RUN。
- [ ] STATUS/RESULTS从实际JSON复算；旧报告加更正链接，不覆盖历史数值。所有输入原hash不变；诊断检查点和正式可恢复检查点明确分类。

**继续规则：**接口修复、验证、通过前置后的本计划分支自动连续推进，不需例行确认。真正停止只发生在预注册科学失败且可用分支耗尽、资源上限、关键不可辨识资料或计划外结构变更。

**Next skill:** `$superpower-executing-plans`。

## 5. 给执行模型的完整指令

```text
请执行 C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-g0-completion-and-h-layout-plan.md。
先读该计划、实际源码和 evidence/gpt6_plan_v3_review 的复核，保留v1/v2原权重及所有失败。先完成A1真实合同/记录修复与A2完整G0，禁止用报告关键词或少量测试代替认证。G0完整通过后，只执行一次登记的h_shift=True位置候选及遗漏的E诊断；保持R、A_fixed、更新数、种子、学习率、网络和总预算。原P4-A不重跑，旧失败checkpoint不得恢复重领预算。
按前置连续完成开发、固定验证与64→128→1024→8192分支，每阶段中文报告，无需例行确认。未执行记NOT_RUN。所有出数运行包lab_log，真实计数、保存参数R、六分量、源外探针与恢复资格落盘。几何精确核与Yee控制不计DCO成绩；MRE/nMAE分栏。遇已登记科学/资源停止条件保存现场，禁止新增扫参来躲过停止。
```
