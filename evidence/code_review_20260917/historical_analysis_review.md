# 历史分析与报告验收只读审查

日期：2026-09-17。任务：第三子任务，独立报告/验收域。范围为用户指定的 `scripts/analysis/` 下 24 个文件，全文 3,389 行；逐文件覆盖与本次源码 SHA256 见末尾。本报告不是全项目审查完成声明。

## 范围和方法

目标差距：确认历史报告是否由真实证据支持，避免把摘要标签、工程运行成功、局部拟合或恢复声明解释为论文机制、完整场精度或成本收益已经通过。

行动合同：本次区分“真实数值失败”“报告或验收逻辑有缺口”“历史输入缺失或未重新认证”。冻结范围为上述 24 文件，训练、GPU、优化器更新和被审脚本执行/导入预算均为 0。成功判据是逐文件实际阅读、给出可定位的问题及历史影响边界；缺输入保留 INCOMPLETE，仍继续静态审查。唯一新增输出为本文件；修复、反例执行及旧报告更正均待父审汇总后由用户批准。

已读 `AGENTS.md`、`PLAN.md`、`STATUS.md`、本目录 `REVIEW.md` 和 dispatching-parallel skill。遵照用户对本子任务的明确约束，不再分派 agent，不运行测试。另定点读取历史协议、JSON/Markdown、账本相关行及路径辅助函数；没有读取或认领 `verify_claims.py`，`trunk_evidence.py` 对它的依赖只记为外部边界。

执行了入口要求的只读命令：

```powershell
Set-Location C:\PI-DON
py -3.11 run.py project_harness status
py -3.11 run.py project_harness next
```

status 退出 0；next 退出 1，指出 `evidence/direct_mechanism_v1/runs/{A_R,A_P,B_R,B_P}/summary.json` 缺失。本轮不据此把历史运行改成 NOT_RUN，不修计划、不写行动/成本账本。其它被审脚本均未执行或导入；权重只做文件存在性及选定 SHA256 核对，没有反序列化模型或推理。

本报告 HA 编号是定位索引，不是新增独立缺陷计数：HA01/02/03/04 分别扩充既有 F02/F29/F22/F28 家族；HA09 补充已有探索审查 X07/X08 的报告传播路径。HA05 与离线审查 H01 共用历史证据，但这里定位的是生成器仍输出相反解释的问题。不得把这些重复加进全项目问题总数。

## 对既有结果的影响

| 已核对事项 | 实际影响与边界 |
|---|---|
| R3 floor 解释 | **历史报告确实出现错误解释**。两种 floor 的已保存 loss 和梯度完全相等，384 个分量受影响数为 0，报告却说这些数值证明损失不同。应更正解释，不能据此归因 B 的退步。HA05。 |
| v1 P3 单步门 | **历史门槛口径确实错用**：比较的是瞬时相对 Q，不是登记的固定幅值 A_fixed。旧单步表不能认证 A_fixed；43E 的残差失败独立存在，所以原 G1 FAIL 不翻转。HA06。 |
| 夜间 COMPLETE | **已有保存结果过度认证执行完整性**。`night_evidence.json` 写 COMPLETE；后续 acceptance review 明确 PARTIAL_INCOMPLETE，并列出预登记、逐更新预算、逐项验收和 N5 覆盖缺口。G1 的数值失败仍成立。HA02。 |
| A1 “54 项” | 保存结果有 54 次测试执行、38 个不同 test ID，16 个 ID 各重复一次。不是 54 个独立合同场景；没有发现原 54 行含 FAIL。HA11。 |
| A3 | 43/96 的 H R 分别约 1.19441e-3、7.41518e-4，均失败；四个保存 checkpoint 的 SHA256 现存文件均匹配旧读回记录。空集通过/读回不参与门的漏洞**未被证实影响这次 FAIL**。HA01。 |
| 旧 32 步 | lab44 的 M3 已经是 FAIL；现存 JSON 中非零 H/E 都用满 200 次，且最终 loss 超过 1e-4。因此迭代次数代理判据有漏洞，但未把这次整体残差失败改为通过。HA07。 |
| 旧 S1 | 现存 history 最后一行为 epoch937/23425 updates，best.pt 的字节哈希匹配旧 audit。仍是 INCOMPLETE；未知尾部和未保存末状态没有被补齐，不能恢复旧失败预算。HA03/04。 |
| 当前 P/R128、S1R、PAPER01 | 本范围没有重算这些实验，不更改其失败或交付状态。旧报告漏洞不能当作“它们未训练”的证据，也不能解锁 1024/8192。 |

## 问题索引

### HA01 [P1，F02 家族补充] 部分或空任务集合、缺读回与缺预算仍可能通过开发门

位置：[a3_gate_report.py:31](C:/PI-DON/scripts/analysis/a3_gate_report.py:31)、[a3_gate_report.py:52](C:/PI-DON/scripts/analysis/a3_gate_report.py:52)、[a3_gate_report.py:62](C:/PI-DON/scripts/analysis/a3_gate_report.py:62)、[a3_readback.py:32](C:/PI-DON/scripts/analysis/a3_readback.py:32)、[a3_readback.py:49](C:/PI-DON/scripts/analysis/a3_readback.py:49)。

触发：`dev.tasks=[]` 时 complete 保持 True；只有一项成功任务也没有检查必须包含 43/96。门只信 H/E 的 passed 标签和 A_fixed/cost_pass，不重算数值 R、不核验 500 次/360 秒绝对预算，也不把 `readback.all_pass` 加入 complete。A3_readback 在所有任务被跳过或 tasks 为空时 `all([])` 为 True。若将来顺序 E 成功，它仍固定读取 `oracle_E` 和 E_oracle 文件，不能覆盖成功候选的真正顺序 E。

同族覆盖：

| 文件/行号 | 缺口 |
|---|---|
| [p3_report.py:34](C:/PI-DON/scripts/analysis/p3_report.py:34)、47、68 | `tasks=[]` 且缺 `single_step_errors` 会打印 `g1_pass=true`；缺任一固定任务、未完成验证集、非有限单步误差也未统一拒绝。NaN 的 `value > 1e-3` 为假。 |
| [night_evidence.py:126](C:/PI-DON/scripts/analysis/night_evidence.py:126)、141 | G1 固定只检查 H43/H96/E96。即使三者标签与 R 都通过，也完全没有要求顺序 E43、完整接受步及其 A_fixed；没有校验总提交/Adam/closure/时间预算。 |
| [stop_review_evidence.py:43](C:/PI-DON/scripts/analysis/stop_review_evidence.py:43)、48 | 已正确拒绝缺任务/缺 H/E/错误相位/非有限 R，但仍只查更新数上限，未要求计数非负整数、elapsed_s 和登记时间预算。不能当完整预算认证。 |

历史影响：现存 A3_GATE 为 FAIL，A3_readback 四行 all_pass=True；四个文件哈希已单独核对相符。原 P3 有十项任务且 43E 明确失败。夜间 H43、顺序 E96 均失败，未出现上述假设的“三项好就通过”。因此本条是已定位的验收漏洞，不撤销真实失败；本轮没有运行合成反例。

建议：先由冻结协议构造必需任务、角色、阶段全集，缺项 INCOMPLETE；验证数值有限性、残差、预算和磁盘身份后再判门。读回须绑定实际 oracle/sequential 角色，并作为通过前置。固定状态协议中的源外探针是单时刻记录，不能额外误要求它具备闭环整段波形；完整轨迹的波形门仍归 F02 主问题。

排除误报：A3 的 `new_H + E <= 2*(old_H + E)` 是 [当时协议:160](C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-g0-completion-and-h-layout-plan.md:160) 明确登记的比较方式，不把共用 E 时间本身另报为成本公式 bug。

### HA02 [P1，F29 家族补充] 摘要、退出码和自报集合代替逐项证据绑定

位置：[n1_evidence.py:61](C:/PI-DON/scripts/analysis/n1_evidence.py:61)、[n1_evidence.py:64](C:/PI-DON/scripts/analysis/n1_evidence.py:64)、[night_evidence.py:119](C:/PI-DON/scripts/analysis/night_evidence.py:119)、[night_evidence.py:190](C:/PI-DON/scripts/analysis/night_evidence.py:190)。

N1 的全部 C01-C15 都由同一个 `exit_code==0` 且 cmd 含四个文件名的布尔值产生。`test_id` 是预填名称，observed 只有 lab ID/退出码；不检查具体测试结果、跳过、期望数值或测试版本。C09/C10 还映射到同一 test ID。报告时取得的当前五份生产源码哈希不是测试执行时的完整源码/测试快照。协议明确要求逐项数值/状态、测试 ID 去重：[夜间协议:202](C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-10h-goal-night-plan.md:202)。

`night_evidence` 用 N1 文件自己给出的 required_ids 做集合相等，空 required_ids 和空 checks 也会满足；重复 ID 不拒绝。G0 只查 28 行标签与顶层 PASS，不独立校验必需 ID 集合和原始数值。assets 为空会使 N0 vacuous PASS；N5 两种检查列表为空也会 `all([])` 通过。acceptance 仅记录文件是否存在，未参与 night_goal；COMPLETE 条件甚至不要求预登记与所有计划诊断完整。

历史影响有直接证据：

- [night_evidence.json:470](C:/PI-DON/evidence/gpt6_plan_v4_night/night_evidence.json:470) 保存 COMPLETE，同时 label_provenance=INCOMPLETE。
- [acceptance_review.json:944](C:/PI-DON/evidence/2026-09-14_acceptance_review/acceptance_review.json:944) 已修正为 PARTIAL_INCOMPLETE，A01-A07 逐项说明遗漏。本轮不把该旧纠正重新算作新发现。
- 原 lab202 的真实 cmd 为 unittest，stdout_tail 有具体 `... ok` 和 `Ran 72 tests ... OK`。不能因 N1 认证薄弱断言当时没有执行测试；问题是 C01-C15 的证据强度不足以覆盖登记断言。

同族其它路径：

| 文件/行号 | 触发及历史边界 |
|---|---|
| [r1_r2_reports.py:28](C:/PI-DON/scripts/analysis/r1_r2_reports.py:28)、46 | R1 只按固定四个 lab ID 的退出码判定；R2 只信 summary 的 finite/max/classification，不核查 128 个步骤、磁盘记录/身份/恢复。实际旧 R2 报告保存 float64 Q=0、float32 Q=2.808282e-6、负例 Q=1，未证明原控制场错误。 |
| [trunk_evidence.py:65](C:/PI-DON/scripts/analysis/trunk_evidence.py:65)、69、73 | 权重/history/数组哈希检查较强，但评估 models 可为空，也未要求 tag 到 checkpoint 的必需映射。逐行只用 `pred_key/true_key` 取数组；没有证明 key 对应同一 model/seed/shape，也没有重推理绑定预测与权重。若清空 models 或改行键并同步自报元数据，模型身份检查会漏掉。真实 summary 的模型表完整，C200.pt 当前哈希匹配训练记录；没有证据表明历史模型/数组被替换。 |
| [audit_v2_stop.py:201](C:/PI-DON/scripts/analysis/audit_v2_stop.py:201)、214、217 | reference_ordering 把非有限 Q 直接跳过，最大值初始为 0；全程非有限也能留下 alignment_pass=True。已存修正版数值为 aligned=0、unaligned=0.96654，本轮未观察这种故障；它明确只作顺序诊断，不能升级 G0。 |
| [s1_interrupted_audit.py:106](C:/PI-DON/scripts/analysis/s1_interrupted_audit.py:106)、115 | 仅 summary.json 与 last.pt 存在就标交付 PASS，不读 summary/last 内容、history 连续性、25000 更新、盲测、身份；空文件也满足存在条件。真实旧 S1 两者缺失，正确维持 INCOMPLETE。 |
| [audit_night_storage_revision.py:31](C:/PI-DON/scripts/analysis/audit_night_storage_revision.py:31)、36 | 历史资产全集依赖上一份 audit 的 historical_fits；空列表使 preserved=True。它是存储规划，不能升级成全部历史权重认证；非空列表的缺文件检查确实会失败。 |

建议：每层只消费带必需 schema/集合、冻结身份、数值和文件哈希的事实源；标签不能替代原始行。测试证据记录执行时的测试/源码、每项 observed/expected 和跳过状态。评估行与模型/数组键建立显式关联。非有限或必需输入缺失保留 INCOMPLETE，不把结构缺失充作有效负对照。

### HA03 [P2，F22 家族补充] 固定历史文案被包装为实时审计，并可能覆写已完成状态

位置：[goal_completion_audit.py:54](C:/PI-DON/scripts/analysis/goal_completion_audit.py:54)、70、81、92、106、116、126、150；[s1_interrupted_audit.py:130](C:/PI-DON/scripts/analysis/s1_interrupted_audit.py:130)、146、179。

goal_completion_audit 读了 tasks/final，却不使用它们计算 requirements：M0/M1/M2、harness、收益和“不虚报成功”固定 PROVEN，S1 固定 NOT_PROVEN。因此缺 FINAL_JUDGMENT 时仍会声明已证明 final 中的布尔结论；将来合法第一阶段已完成也仍说没有完成。当前缺历史 summary 使 harness next 失败，与其“currently passes”文案不符，但不能据今天缺路径断言旧 lab292 当时也失败。

s1_interrupted_audit 对 completed 的 JSON 分支可给 PASS，但 Markdown 和 stage_status 永远写 INCOMPLETE，并固定“937/930、进程不活跃、无 last/summary”等理由；未测进程活跃性。若在训练中或完成后复用，既可给相互矛盾报告，又会实际改写旧 S1 阶段状态。该脚本及 goal_completion_audit 均不在当前 historical_entrypoints 封存清单内；不能套用其它历史入口被 run.py 拒绝的保护。

其它硬编码传播点：A3_gate 61、75-77 行始终叙述失败/500更新；p3_report 64 行无条件宣称低于预算；p4_report 30、34、41、45 行固定 run97 和失败原因；r1_r2_reports 53、57-59 行固定128步和“通过”；review_reproduction_acceptance 41-63 行把人工历史判断固定写进新结果，未由当前 computed/current_g0 派生。这些可作为特定历史快照模板保留，不能作为通用实时认证器。

真实路径兼容边界：`ROOT = PROJECT_ROOT` 的 `/` 运算会映射旧顶层文件，`pidon_recording.sha256_file` 也调用 resolve_legacy。没有把 `ROOT/'dco_lr1e3_300.pt'`、`ROOT/'lab_runs.jsonl'` 误判成缺文件。但下列裸路径不经过该适配：

- [check_files.py:50](C:/PI-DON/scripts/analysis/check_files.py:50)、54 的 `os.path.exists(f)/open(f)`，根目录运行会把已迁移源码误报 MISSING；发现 bad 也没有非零退出。
- [night_report.py:62](C:/PI-DON/scripts/analysis/night_report.py:62)、90、92、433、473 的 cwd glob/exists，在文件已迁移时输出 “never ran / did not run”，还建议重跑。
- [sweep_report.py:81](C:/PI-DON/scripts/analysis/sweep_report.py:81)、84 的 cwd glob 与“还没有，先跑”同类。
- [trunk_evidence.py:28](C:/PI-DON/scripts/analysis/trunk_evidence.py:28)、43 使用 manifest 中旧 `dco_lr1e3_300.pt`；被调用的 `paper_recheck.sha256` 是裸 open，torch.load 也未 resolve。这是 X13 家族的分析端消费者，不能把文件迁移当成权重丢失。

建议：固定历史生成器封存，任何重审用独立新输出和明确版本；所有 status/理由从检查结果派生，管理状态更新与只读报告分离。已运行但文件缺失标 INCOMPLETE，只有行动/调度证据支持从未运行才写 NOT_RUN。原 FAIL、旧时间戳和权重保持不改。

### HA04 [P2，F28 家族补充] 输出恢复资格和成本汇总，未核验完整恢复身份与未知尾部

位置：[a3_gate_report.py:51](C:/PI-DON/scripts/analysis/a3_gate_report.py:51)、[night_evidence.py:96](C:/PI-DON/scripts/analysis/night_evidence.py:96)、125、135-139、149、181。

触发：A3 直接转抄 task.recovery_eligible；night 转抄 progress.resumable/task.recovery_eligible。checkpoint 采用 diagnostic_only 读回，它明确不代表生产恢复许可；新算的 input/target hash 只是记录，未与冻结 expected 身份比对。未验证模型/optimizer/RNG/phase、有效提交点、累计预算和未保存尾部。resource 直接按 kind 对 ledger 求和，没有处理重复提交/恢复累计计数；空或部分账本会给精确数值 0/部分和，而没有 UNKNOWN 标志。

历史影响：旧 night_evidence 的 H96 行有 recovery_eligible=True，但它只表示单个 H 拟合的上游字段；同一报告明确没有合格完整轨迹。不能凭此字段允许正式续训。历史资源记录保存 registered Adam=1394、oracle=765，当前没有证据证明这些已保存行的和算错；这里只否定“已经认证全部实际成本/恢复状态”的更强推论。

正向边界：audit_mechanism_decision_review 109-115 行把随机臂 26 行/4108 saved updates 与 unsaved_tail_updates=UNKNOWN 分开；这是正确保留下界的做法。s1_interrupted_audit 固定 recovery=False 虽不是可复用验证器，但没有给旧 S1 重新领预算；现存 history937/best930 的差距确实支持保守拒绝。不要将本条改写成已经发生非法恢复。

建议：报告字段区分 `reported_resumable` 与 `verified_resume_eligible`；后者必须完整验证恢复合同。成本按 attempt/commit 身份去重，并分列本段增量、累计数、失败/诊断开销、UNKNOWN尾部。此条仅补全 F28 的消费者覆盖，不新增同类恢复问题计数。

### HA05 [P2] R3 对完全相同的 floor 数值结果写出相反解释

位置：[r3_v2_recompute.py:97](C:/PI-DON/scripts/analysis/r3_v2_recompute.py:97)、103-104、[r3_v2_recompute.py:135](C:/PI-DON/scripts/analysis/r3_v2_recompute.py:135)。

触发：模板无条件写“这证明两种公式不是相同损失”，不比较受影响分量数量或实算 loss/梯度。两个 floor 常数不同，不代表这个数据域的损失或梯度实际不同。

历史影响已确认：[R3_recompute.json:141](C:/PI-DON/evidence/gpt6_plan_v2/R3_recompute.json:141) 为 affected=0、below_new=0、384 components；旧/新 loss 都是 9.756619453430176，梯度范数都是 289.45452880859375。[R3_REPORT.md:13](C:/PI-DON/evidence/gpt6_plan_v2/R3_REPORT.md:13) 仍写上述证明语句。离线审查 H01 已正确解释“协议常数不同但该批分母未受影响”，本条定位导致错误历史解释的模板行。

建议：按数值分支表述“合同常数不符；此样本集未激活 floor，不能解释 B 的退步”。保留四样本 nMAE 复算 0.020065677674559388 与旧聚合 0.005852074478752911；这项 nMAE 纠正本身不因 floor 文案错误失效。未在本轮重新推理/反向计算。

### HA06 [P1] P3 把瞬时相对 Q 当成固定幅值误差门

位置：[p3_report.py:47](C:/PI-DON/scripts/analysis/p3_report.py:47)、48-52、62-69。登记要求见 [原计划:232](C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-evidence-and-reproduction-plan.md:232) 及 [v2 明确公式:103](C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-contract-repair-and-gated-continuation.md:103)。

触发：直接用 `global_weighted_relative_l2 > 1e-3` 生成单步失败，并进入 `g1_pass`。Q 的分母是当时参考场能量，A_fixed 的分母是固定幅值与体积；它们不是同一归一化。弱场时 Q 大不等于固定幅值门失败，强场时也不能用 Q 自动保证 A_fixed。

历史影响已确认：旧 fixed_state_report 在第16步 both_single_step 保存 Q=0.0045841640433964955，报告列为超过门槛；但保存资产没有对应 A_fixed/固定分母，不能由 Q 反造通过或失败。R3 已把该资产不足记 INCOMPLETE。43E 残差为 6.3356466e-4，仍独立决定旧 G1 FAIL；本条不把旧候选改判通过。

建议：Q、A_fixed 和物理 SSE/分母分栏；读取不到固定幅值证据就标该门 INCOMPLETE。只在独立新输出重算可恢复的资产，不覆盖原表或用新的判据重解释旧 FAIL。

### HA07 [P2] 32 步残差达标数由迭代次数猜测

位置：[stage2_evidence.py:33](C:/PI-DON/scripts/analysis/stage2_evidence.py:33)、34、47-48。

触发：把 `0 < it < 200` 当作达 tol，而不是看保存的 loss 与 tol。提前停但残差不合格会被计为成功；恰第200次才达标会被计失败；零更新但初始已达标也遗漏。H/E 总计只要求 >=62，而首个 H 为零、E 有32次，本来有63个需分别解释的非零子问题。文件还只检查行数32，不检查 step连续、完整物理配置或源外六分量证据。

历史边界：现存正式 postloss JSON、lab44 的 M3=FAIL 一致；其所有非零 H/E 都是200次且 loss>1e-4，未证实这条旧结论误判。M0/M2 的有限性与小 nMAE 也只是记录层诊断，不能认证严格 Algorithm 1 或传播。

建议：用实际残差规则逐半步分类，明确零靶/无更新/用满预算仍达标等边界；分别核对必需 H/E 集合和 step 顺序。现有源码使用 assert，若在 Python 优化模式下运行会丢失结构检查；任何后续正式验收入口应显式返回 FAIL/INCOMPLETE。

### HA08 [P2] 相同版本字符串被显示为“当前源码可直接复现”

位置：[audit_reproduction.py:183](C:/PI-DON/scripts/analysis/audit_reproduction.py:183)、186、[audit_reproduction.py:275](C:/PI-DON/scripts/analysis/audit_reproduction.py:275)、293。

触发：只比较 JSON.version 与当前 SCRIPT_VERSION；相同字符串就表格显示“是”，甚至两个版本都缺失时 None==None 也成立。版本字符串不能绑定源码字节、配置、模型、RNG、优化器和数据；脚本自己又在 known_omissions 中列出这些缺口，故此肯定显示过强。

历史边界：已存 v1 audit 的两条轨迹版本为 2026-09-10a、当前为2026-09-13a，matches_current_source=false。因此未见这两条旧轨迹实际被显示为“是”。版本相等导致误报属于静态可触发路径，不是历史现场反例。

建议：改成“版本标签相同/不同/缺失”，与“可复现性”分离；后者必须有冻结源码/配置/权重/数据哈希及可审核执行链。保留该脚本对 stepgain 仅为描述性拟合、MRE/nMAE 不混比的正确限制。

### HA09 [P2，X07/X08 报告家族补充] 有限扫描和偏相关被升级成机制或因果结论

位置：[night_report.py:122](C:/PI-DON/scripts/analysis/night_report.py:122)、129、242-267、[night_report.py:317](C:/PI-DON/scripts/analysis/night_report.py:317)、[night_report.py:376](C:/PI-DON/scripts/analysis/night_report.py:376)。

触发：少量 CFL 的 rho 都>1 就宣称“no time step rescues it”；某个 CFL 子集相关系数>0.8、经验倍数离散度<1.6 就称 rho 预测真实网络寿命；偏相关阈值触发“accuracy acts ONLY through rho”；有限采样的 steps*CFL 相近就排除所有时间步和积分器修复。共同状态可比性和 exact control 失败仅警告，后续结论不因此停止；`rho_exact` 缺失默认1.0，无法据此认证控制。删除 eps0>0.5/未观测发散的行也改变所评估集合，不能把剩余相关性解释成全体网络定律。

历史影响边界：消费者确实采用 X06 的 blowup 字段和 X07 的启发式预测，并输出上述预设因果措辞。已读的账本没有定位到直接运行这个 night_report.py 的留存输出，所以不声称某份历史终稿一定包含这段文字；存有 spectral 原始 JSON 不等于证实某个输出分支执行过。静态结论明显强于它实际计算的证据。

建议：限定为指定模型、seed、网格、CFL 范围内的关联观察；控制不完整标 INCOMPLETE；报告筛选前后集合与删失情况。偏相关不能单独认定因果中介机制，也不能用固定预训练算子失败否定问题训练后的冻结复用。与探索审查 X07/X08 合并，不重复统计。

### HA10 [P2] sweep 报告把不可读输入当无数据，未核对序列对齐，且列名误标

位置：[sweep_report.py:50](C:/PI-DON/scripts/analysis/sweep_report.py:50)、53-54、69-76、84、90、100、119。

触发：JSON 损坏被静默返回 None；缺 nmae 也返回 None；所有候选被过滤时输出“还没有文件，先跑”，与真实输入状态不符。epoch 长度决定 tail 长度，但 train/test/nmae/relL2 不要求等长且对应同一 epoch，也不拒绝 NaN/Inf；不同时间窗口可被当作相同“末段”排名。表头“train损失”实际输出 `test_tail`。最后“1.15以内是训练噪声”只是预设经验线，没有重复seed或不确定度支持。

历史边界：当前裸 cwd glob 已受迁移影响（HA03）；本轮没有找到可归属的直接 sweep_report 账本输出，不把上述错误当作已证实翻转某次排名。已明确不跨 MSE/relative MSE 比大小是正确改进；但 nMAE 仍需同题、同评估集合和同归约才能用于严谨比较，不能仅凭指标名认证可比性。

建议：分别列 missing、parse_error、missing_metric、nonfinite、unaligned 与可排名项；先核对各记录的 epoch 和数据合同。把该列改为实际 test 指标名，把1.15称预设筛选线。零误差时显示比值边界，避免108/116行直接除零；不要以报告读取失败触发新训练。

### HA11 [P2] A1 合同证据未登记跳过项或必需唯一测试集合

位置：[a1_contract_report.py:29](C:/PI-DON/scripts/analysis/a1_contract_report.py:29)、34-44、67-80、93。

触发：CollectingResult 只记录 success/failure/error，没有 addSkip/expectedFailure 等记录；wasSuccessful 在全部测试跳过时也为 True。没有冻结必需 test ID/唯一数量，模块导入其它 TestCase 造成重复执行也未区分。报告宣称“每个测试的 observed/expected”，实际测试行只有 test/status 或失败 detail；数值观察没有逐项序列化。

历史影响：已存 contract_test_results.json 为54行 PASS，但只有38个唯一 ID；audit_night_v4 的历史 test_inventory 已记录这一点。54是执行次数，不应解释为54种独立合同覆盖。没有证据证明原54次包含跳过或失败；该脚本把 v2 P4A 资产标 diagnostic_only_not_resumable_v3 是正确边界。

建议：执行次数与唯一场景数分列；冻结必需 ID，对 skipped/缺项给 INCOMPLETE；输出逐项断言证据和执行版本。测试绿色仍仅说明工程合同，不能替代 DCO 科学门。

## 未报错的重点核对

- **P4 Adam 计数不能套用新 schema 误报。** 旧 P4 JSON 为 n_updates=297、n_lbfgs_steps=97、n_closures=200；当时 n_updates 合计两类提交，因此 p4_report 的相减得到 Adam200 符合该旧 schema。若输入当前 n_updates 已只计Adam的新记录会少算，但这个固定历史模板本轮未见这种实际输入。应加 schema约束，不能宣布历史实际只训103次或多算97次。
- **历史未知成本保持未知。** audit_mechanism_decision_review 已明确随机臂未保存尾部UNKNOWN；saved4108不是全部实际成本。其保存的正确双输入叠加诊断与旧“多波减两波”测试分列，并限制为一个样例，没有将其认证为一般线性定理。
- **audit_h_layout 是几何控制。** 随机场、各向异性间距和前向差分裁剪用于几何关系；明确 NOT DCO performance，不把该几何PASS计为网络成绩。47行 sha256_file会适配旧路径，不报根目录文件缺失。
- **audit_night_v4 / audit_v2_stop 是当时的反例快照。** 它们会做临时CPU玩具更新，虽 formal_dco_updates=0，也不等于工具内部零优化；本轮没有调用。保存的反例可说明历史版本漏洞，不能未经重新定位宣布当前全部旧漏洞仍存在。
- **review_reproduction_acceptance 的正确限制仍保留。** 它把夜间执行标 PARTIAL_INCOMPLETE，并没有因标量控制通过就声称论文复现成功。关于预登记时序的旧结论来自已保存历史审计，本轮没有拿迁移后的文件创建时间重新证明当时因果；若复用工具必须由冻结事件证据派生，而非固定文案。
- **不存在统一的“缺文件仍PASS”行为。** 多数脚本强制read_text/torch.load，缺文件会抛异常；报告只对上述明确的空集合、存在性、默认值或标签路径作出判定。

## 证据可用性与验证限制

现存并已读：A3 development/gate/readback、v1 P3/P4 JSON和报告、v2 R2/R3、v3 contract、v4 audit/night evidence、后续acceptance review、旧S1 audit/history末行、goal completion、mechanism decision review、trunk summary/manifest。没有把本地可用的历史权重笼统标“已缺失”。

SHA256 字节核对结果：A3 的 H43/E_oracle43/H96/E_oracle96 四个 .pt 均与 A3_readback.json 的预存哈希一致；C200.pt 与 trunk summary.training.sha256 一致；旧 S1 best.pt 的 SHA256 为 `00e4a9da0915fd44bc9f7b238dde56627a7e8a53f766367f9759ac2807e89579`，与 interrupted_audit 一致。此项只证明所比文件字节身份，不证明其训练状态或数值正确。

明确 INCOMPLETE：harness 指出的四份旧 M2 summary 本地缺失；v1 P3 的固定幅值门缺预测/最终权重和固定分母；S1 epoch937末状态/未知尾部仍不足。A3/R3/night/trunk 权重或数组虽可在本地定位，本轮按授权未加载计算，数值重新认证为 NOT_RUN，不能声称完成端到端重算。

关键读到的历史证据 SHA256：

| 文件（相对 `C:/PI-DON/`） | SHA256 |
|---|---|
| `evidence/gpt6_plan_v2/R3_recompute.json` | `26e6bb69e92d5b288d1bbeb1231492972b6a20662088ea7efc7bd972d4dda89b` |
| `evidence/gpt6_plan_v2/R3_REPORT.md` | `05e39d829065dacccdcc4ef3fe4858727e9bc8d36071e0f5e5e848541bb513e8` |
| `evidence/gpt6_plan_v4_night/night_evidence.json` | `c8cffb4605c1a647ab5440c5bf8ad2084cafe97dd83c94618621d4616c194f96` |
| `evidence/2026-09-14_acceptance_review/acceptance_review.json` | `1feb846f19fc42edaa83ebd69b17e8e4cc6fa0cf3d75761a46f07030f4592b34` |
| `evidence/gpt6_plan_v3/contract_test_results.json` | `7af1de793c4f8fcdcd087a94e5a10f93445f64213d5b13bcc782334fb490bf75` |
| `evidence/gpt6_plan_v1/fixed_states/fixed_state_report.json` | `9aecf11806c133cb3b3d8f3c7e397c083f84b608565a233808937d2f03cad334` |
| `evidence/gpt6_plan_v1/p4a_development_e43/fixed_state_report.json` | `e0f2b3bba1278ac0b129e3673cebbffff94263d48ac012299cbe412920ceba0b` |
| `evidence/pidon_stage2_32_lr1e3_i200_postloss.json` | `2a6a3f3f104cffd1f924b185a8708db85c9acef6e49b70f161f51e8cc01ed01d` |
| `evidence/trunk_repair_v1/summary.json` | `c50456feca4ac3d1be782b3103ab5e2dfe68dbcbdf7574bd1e026e50e71fb402` |

## 逐文件真实覆盖

下列均为全文阅读，不是只做关键字搜索；范围外依赖只定点读取，未计入全文覆盖。行号和哈希绑定本次工作树字节，不能替代旧运行源快照。输出路径的防覆盖检查也已核对；“未新增独立问题”不等于重新认证科学PASS。

| 文件（均位于 `scripts/analysis/`） | 覆盖 | 实际核对内容与发现 |
|---|---:|---|
| a1_contract_report.py | 1-103 | unittest结果收集、输出、副作用、诊断资产；HA11。 |
| a3_gate_report.py | 1-87 | 任务全集、顺序E/oracle、R/成本/读回、固定叙述；HA01/03/04。 |
| a3_readback.py | 1-57 | 模型读回、角色选择、阈值与空集；HA01。 |
| audit_h_layout.py | 1-55 | Yee H形状、切片/差分控制、各向异性间距、hash解析、防覆盖；未新增独立问题。 |
| audit_mechanism_decision_review.py | 1-124 | 同题指标、叠加纠正、磁盘失败R、逐行预算、身份、UNKNOWN尾部；成本与诊断边界正确，未重跑。 |
| audit_night_storage_revision.py | 1-72 | 逐文件存在/hash、存储估算、主权重和防覆盖；HA02集合完整性边界，不是科学成绩。 |
| audit_night_v4.py | 1-157 | 反例注入、历史数组R/分量、optimizer计数、源快照、字节hash；旧反例与当前实现分开。 |
| audit_reproduction.py | 1-366 | 缺件清单、版本、轨迹连续、loss归约、描述性增长、冻结验收；HA08。 |
| audit_v2_stop.py | 1-280 | 预算/恢复反例、保存权重推理、幅度、时间交错、数据来源；HA02非有限Q跳过；保留P5来源INCOMPLETE。 |
| check_files.py | 1-70 | 顶层执行、清单/标记/版本和退出行为；HA03。 |
| goal_completion_audit.py | 1-187 | 所有requirement来源、未使用inputs、判定/覆写；HA03。 |
| n1_evidence.py | 1-91 | lab选择、逐项映射、source hash、阶段状态写入；HA02。 |
| night_evidence.py | 1-208 | 所有N0-N5门、磁盘R、身份/恢复、资源计数、完成判定；HA01/02/04。 |
| night_report.py | 1-527 | 全部timeline/stage2/verdict/control/blowup/rank/training/figures；HA03/09。 |
| p3_report.py | 1-74 | tasks、loss字段、单步分母、预算/输出；HA01/03/06。 |
| p4_report.py | 1-55 | 旧Adam/LBFGS schema和实际JSON、固定run/停止叙述；HA03，旧297-97=200不是新计数bug。 |
| r1_r2_reports.py | 1-70 | lab ID、控制门、硬编码表格和原报告；HA02/03。 |
| r3_v2_recompute.py | 1-148 | 逐样本逐分量MRE/nMAE、物理还原、floor梯度、模板和输出；HA05；缺P3原资产不反造。 |
| review_reproduction_acceptance.py | 1-71 | night/G0结果消费、时间证据、固定剩余要求、防覆盖；HA03，旧纠正边界保留。 |
| s1_interrupted_audit.py | 1-205 | history/best/文件hash、完成与恢复、报告和stage写回；HA02/03/04。 |
| stage2_evidence.py | 1-56 | 必需字段、次数/有限性、M0-M3声明、真实旧32步记录；HA07。 |
| stop_review_evidence.py | 1-55 | 缺项/失败优先、任务集合、phase、残差/A_fixed、预算；HA01。 |
| sweep_report.py | 1-124 | 所有解析/窗口/排名/缺失/展示分支；HA03/10。 |
| trunk_evidence.py | 1-147 | 全部源/权重/历史/数组hash断言、冻结张量、optimizer200、评估身份、比值和声明；HA02/03；verify_claims外部依赖未展开。 |

## 源码 SHA256

| 文件（均位于 `scripts/analysis/`） | SHA256 |
|---|---|
| a1_contract_report.py | `046ebe038accf0385f66e59c02b419a79b33375a7c714cd87cb25dc39c190841` |
| a3_gate_report.py | `7e1642571f6b20b3ef1ec6c56d04c16a9f0bc136f90182239d97ed294a31e767` |
| a3_readback.py | `ab3c1e88b3aeca8eba36b6470f105fda4fa1e7c8dd4b1621fb190fea13e0f045` |
| audit_h_layout.py | `eeacec38e0019e6a0c8c962b6a221128b6026e289b27525296c4e81ffd6d907c` |
| audit_mechanism_decision_review.py | `aa46cb0bd2a9e66f28242c594593d7520d573e2efde7b31292f2b00991cef647` |
| audit_night_storage_revision.py | `c720d369cca3dd8d85c1b165661ddc70356897995d6b7ea7022e62c25d9b3ece` |
| audit_night_v4.py | `6c3437e73b45483f0691ea30e9fc79916ddbc07c519bf6680ceaae71a043f18d` |
| audit_reproduction.py | `038fbc9d05a8c2209e170a82daa00ba821c7a9ed5223aca0b35fce78a560d842` |
| audit_v2_stop.py | `7a6ab128981d896bd7a7603713623f3cfd110fbf691d280ed78abf946b56331d` |
| check_files.py | `2f27c3b6473a39e0024b743ad4b8cffc4bedde83dcbeaa487bb7c8e3e66eba42` |
| goal_completion_audit.py | `0458b350cefc854b3ba9990b639100f27198350886a3a8acaf22887e7766904c` |
| n1_evidence.py | `be5ab61f29ab1abbb54dbd470b5ab479cafaf82f134eb0525c4cc514456e2132` |
| night_evidence.py | `df0afc6c9a401c0b4b26a68a8489b37681ea99ed2cd4ada4778603c3384c8d79` |
| night_report.py | `846a0484c54d35f88f0e9eee017ddea52aa07ba4c0fc254e4cd68342d450a67c` |
| p3_report.py | `758103c99eb41c6dff724da113171e493125cee4fd75bfcd65a004bd366dbc95` |
| p4_report.py | `447cef63626fd224f9e992b084d0f721e914c1b5f5fdf3dff7e2bcfc4b3bfbbe` |
| r1_r2_reports.py | `924fec0596b32f23d94197ca0962cb3f0a8878f1310d5bfbfce061ac40bd7e18` |
| r3_v2_recompute.py | `5d8bf2f5121c880245e45ba36443235e0ed6d4e0f7624b2cfdbb83215359fbf8` |
| review_reproduction_acceptance.py | `d186a5c2a7ff611fdb5cf3c790366b4772ca33562981f5128af8308ec87cd815` |
| s1_interrupted_audit.py | `f460c451688213260bb82cda15bf6fa955a9ecc67672ec142875fc5d9b6830c2` |
| stage2_evidence.py | `0bbf89140b24513ecf82dfeb96b7047fee89da1da4439d69f4fa204e02d28c4a` |
| stop_review_evidence.py | `4571ef010512012182ff41e334347395636a6cd78a5ea68838a61732d726903c` |
| sweep_report.py | `9ebdbe5768aa09b56ccde27f4fb8023a63ce9213e77518d5ddbcba8b0b982499` |
| trunk_evidence.py | `f30976b3e8f921015745d38e2f5efd4e3a1e27dc74e90f400158246183929ca9` |

## 交回父审的建议

优先更正可确认的历史解释范围：R3 floor、P3 Q/A_fixed、夜间 COMPLETE 与独立测试数。随后统一补验收器的缺项/非有限/身份/预算负面测试，再考虑任何恢复入口修订。所有反例执行和生产修复均 NOT_RUN；没有修改原报告、原权重、状态、账本或git，也没有创建新训练行动。
