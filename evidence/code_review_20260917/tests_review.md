# tests/ 只读审查

日期：2026-09-17。范围：`C:/PI-DON/tests/` 全部 `test_*.py`，不含 `_01/tests/`。本报告只提出问题和建议，由用户决定修复。

## 审查范围与结论边界

- 完整逐行静态阅读 33/33 文件，共 2,342 行、140 个本地定义的 `test_*` 方法；0 个仅部分阅读的测试文件。逐文件行数、字节 SHA256 和实际断言范围见末表。
- “完整”只表示本次文件阅读完整，不表示分支覆盖完整、测试已经运行或科学合同已认证。运行结果为 **NOT_RUN**；未执行测试、训练、科学计算或报告生成器，未导入项目测试模块。
- 已读 AGENTS、PLAN、STATUS 和已有 REVIEW 的 F01-F27，采用 dispatching-parallel 技能的独占范围，不再派生 agent。仅新增本文件，不修改生产代码、测试、历史证据、账本、计划或 git。
- 按项目入口执行了带 `-B` 的只读 `project_harness status/next`：status 退出 0；next 退出 1，指出旧 M2 和部分服务器回传证据路径缺失。未修路径或变更调度。另只读查看本机 Python 3.11 的 unittest loader 源码以核实 T08，没有调用测试收集或运行。
- 以下 T 编号描述测试自身的问题或覆盖缺口。关联 F 项不重复计为新的生产 bug。除明确标注的静态控制流结论外，反例是建议的测试输入，**本次没有执行反例**。没有重新认证任何旧科学结果。

## 问题与建议

### T01 [P1，错误的通过夹具] 回传审核测试把损坏权重和摘要自述固定成完整交付

位置：`tests/test_ingest_paper01_return.py:22`、`:26`、`:27`、`:54`、`:65`、`:66`；`tests/test_ingest_paper01_ablation_return.py:14`、`:48`、`:49`、`:53`。

第一份测试用 `b"best"`/`b"last"` 代替可加载 checkpoint，1000 个空对象代替样本定义，history 仅含 update；声明的宏 nMAE 为 0.005，两个 individual 值 0.006/0.009 的均值却是 0.0075，仍要求 engineering_pass 和科学门 PASS。第二份只创建 summary，没有逐臂 history、checkpoint、输入/输出身份文件，仍要求审核 PASS 和完整训练建议。定点读取 `tools/ingest_paper01_return.py:86-145` 确认首个审核只核文件存在、声明和哈希，未加载模型；这是已有 F04/F20 的测试层根因，而非独立重报生产缺陷。

触发：未来给审核器补 checkpoint 可加载性、逐行连续性、样本完整性或聚合一致性检查时，现有“正例”会先失败，容易诱导维护者保留过宽行为。当前测试只证明摘要解析/规则拼装能工作，不能支撑“独立审计完整”。

旧结果影响：不能因此断言旧真实 checkpoint 损坏或 25000 更新没有发生；旧科学 FAIL 保留。旧工程 PASS 需要原始 history、checkpoint、合同和账本的独立交叉证据，不能援引这两份测试补认证。

建议：把摘要解析单元测试与完整审核测试分开。完整正例使用最小合法 checkpoint 和一致样本/指标；新增同哈希但不可加载的文件、重复/缺失 update、逐行 lr 不符、空/缺臂、指标 NaN、individual 与宏值矛盾、优化器 step 与声明不同的负例，缺项返回 INCOMPLETE。

### T02 [P1，科学验收缺口] 根测试没有对正式全场门和收益门实施反面验证

位置：`tests/test_pidon_contract_v3.py:135-145`；`tests/test_failure_mechanism_audit.py:21-32`；`tests/test_first_e_budget_probe.py:14-21`；`tests/test_stop_review_claims.py:30-31`。

前者断言的是 exact-control 的 field_gate_pass；另外几处分别检查分量摘要、首半步残差分类和旧 G1 开发子集。它们没有调用正式 `server_short_tol_probe.field_gate`、`direct_m2_audit.audit_arm` 或收益汇总的最终门。全目录搜索也没有这些正式门的直接测试。`pidon_exact_control.py:69-77` 明确以目标旋度替代预测，所以这条路径可以检验接口和参考对齐，不能覆盖学习网络的科学验收。

触发：验收器接受空/缺分量、滤掉 NaN、忽略 Q/弱参考绝对误差，或在端点合格但中途/源外波形失败时仍 PASS；成本更贵或第二个随机对照失败时收益布尔值仍 True。已有 F02/F27 正是这类漏洞，当前根测试不阻止它们。

旧结果影响：原 Ex/Ey FAIL 不变；PASS_64 不能凭这些测试扩大为全时段、六分量、去源、波形齐全的认证。开发子集 PASS 与完整 G1 的区分本身是合理的，不应删除。

建议：为实际生产门建立一份完整合格的合成证据，逐项破坏六分量全集、有限性、去源 Q、固定全时长弱场尺度、源外整段波形、中途时刻和两随机对照/20%成本条件，逐个断言失败或 INCOMPLETE。另加纯硬源正确但传播错误的正式验收负例。

### T03 [P2，虚假安全断言] “不缓存目标”测试只检查输出有限

位置：`tests/test_head_lstsq.py:81-88`；同文件 `:41-52`。

H07 拟合一个输入后换输入，唯一断言是 `isfinite(output)`。若 predict 无条件返回第一次有限 target，测试仍满足；这没有验证名称所称的“不会缓存答案”。H03/H04 同样仅检查提交次数、求解次数、诊断长度和特征通道，未对 padding 后的每分量预测支撑及物理 SSE 做独立核对。

触发：head hook、归一化还原或预测缓存引入了输入无关输出/目标泄漏，但数组保持有限。定点阅读 `pidon_solve.py:286-330` 可见当前实现写回真实 head 后重新调用 predict；**本次没有认定当前存在缓存目标的生产 bug**。

旧结果影响：旧 head 诊断不能用 H07 通过证明没有参考答案泄漏；不能据此否定已经保存的 head 拟合数值，也不能推广到未使用该分支的正式服务器轨迹。

建议：冻结已拟合权重，使用两份受控且预期响应不同的输入，与独立直接网络前向/尺度还原结果比较；故意替换成缓存目标的 predict 时测试必须失败。补各分量不同形状、边界/padding 和保存重载后的数值等价断言。

### T04 [P2，恢复覆盖缺口] 参数一致不足以认证 RNG 和完整双网络状态恢复

位置：`tests/test_pidon_contract_v3.py:224-261`、`:263-290`；`tests/test_head_lstsq.py:90-108`；`tests/test_pidon_contract_v4.py:72-85`。

Adam 测试确实比较了 net_H 和 Adam 的参数组、step/动量张量，属于有效覆盖。但它把 field 预先生成后复制给两分支；当前 DCO 前向由确定性的卷积/GELU/池化构成，余下拟合不消耗随机数。因此第 242 行改种子再恢复，即使 restore_rng 被遗漏，后续参数相等也不能检测该错误。LBFGS 测试只比较更新/closure 数和 net_H，未比较 LBFGS 历史及成功提交数；这些用例也没有完整断言 net_E/opt_E、pending 状态、源索引和接受后轨迹。

`diagnostic_only` 测试只在 no_grad 下 predict 一次并比较 net_H，不能证明诊断加载后所有训练入口都被禁止，也没有检查 opt_E、进度或文件是否改变。当前 `load_state_payload` 的确调用 restore_rng（`pidon_solve.py:836`）；这里是回归保护不足，不是声称目前 RNG 必然丢失。

触发：将 restore_rng 变成空操作、遗漏某个 RNG 流/E 优化器或 LBFGS 历史，仍有可能通过现有断言。

旧结果影响：这些测试支持所测固定 H 拟合的参数/Adam 连续性，不能自动认证正式时域恢复、GPU RNG 或第一阶段独立 Generator 恢复（F21）。不否定从零开始的旧 P/R128。

建议：显式比较 Python/NumPy/torch CPU RNG 和下一次抽样；有 CUDA 时单列 CUDA RNG 测试，独立 Generator 另存/另验。比较全部两网络、两优化器、LBFGS、phase、源索引和真正接受的下一步。诊断只读合同若由接口承诺，应测试尝试更新被拒绝，而不只做一次前向。

### T05 [P2，故障窗口缺口] 恢复测试没有覆盖 CLI、指针后崩溃和跨优化器停止

位置：`tests/test_pidon_contract_v4.py:98-110`、`:40-48`；`tests/test_pidon_contract_v3.py:119-127`、`:224-290`；`tests/test_run_entrypoint.py:20-38`。

rolling checkpoint 用无条件抛错的 atomic_json_save，只会在新 pointer 写入前失败；生产顺序为 slot -> pointer -> metadata（`pidon_recording.py:193-211`）。未测试 pointer 已提交但 metadata 未提交后的再保存/再中断，因此漏掉 F06。尾部测试只检查 recovery_tail_sequence_ids；没有旧快照与物理时间步/累计预算冲突的拒绝测试。run_entrypoint 检查入口路由和 action，未调用正式求解器 CLI resume，因此 F18/F19 不在其覆盖范围。

Adam 中断测试的 lbfgs_closures=0；LBFGS 中断测试则在 LBFGS 已成功提交后中断，缺少 Adam 回调停止且 LBFGS 尚有预算的边界（F24）。另 `test_recorder_rejects_truncated_or_duplicate_jsonl_on_resume` 实际只写入非法 JSON，没有重复 sequence 的样本；night_budget 的重复测试属于另一读取器，不能替代。

触发：指针写后崩溃、从旧快照追加现有日志、Adam 停止后意外进入 LBFGS，或 recorder 接受重复 JSONL。

旧结果影响：已有测试不能认证上述恢复资格；F06/F18/F19/F24 的历史影响边界沿用主审查，不增加“过去发生过损坏/超预算”的结论。

建议：按每个提交边界做故障注入，并增加完整 CLI 临时目录恢复测试；断言物理 step、sequence、phase、checkpoint、剩余预算同时一致。增加重复序号、缺口、倒序行和旧快照回放负例；对 Adam 停止后的 LBFGS 调用设置必须为零的 spy。

### T06 [P2，记账覆盖缺口] M0 成本只断言大于零，不能发现重复累计和未知尾部

位置：`tests/test_direct_mechanism_m0.py:25-31`；`tests/test_server_resource.py:21-29`、`:56-93`；`tests/test_mechanism_hour.py:29-35`；`tests/test_r4_p4a.py:17-23`。

M0 直接信任被测报告的 checks，且只要求 Adam/closures >=1，所以真实 4 次被汇总为 5 次仍满足（已知 F23）。server_resource 有值得保留的“失败候选计成本”和“保存失败仍保留15更新”断言，但使用独立行/吞吐探针，不覆盖同 attempt 中断行和恢复累计行的去重。hour 的单行分类及 P4-A 配置常量也不证明队列实际累计预算。

触发：累计 FitRecord 被二次相加、运行已经更新但没有 summary、末次保存失败被 target_steps 优先覆盖、closure/成功提交/评估混算。F25/F26 的路径没有根测试直接覆盖。

旧结果影响：M0 成本准确性不能由 >=1 推出；已有正常 P/R逐行独立复核并不因此失效。缺 summary 的历史消耗不能视为零。

建议：对真实 optimizer.step、closure 和提交点单独计数，对比报表增量/累计量；注入中断、恢复和末次写入错误。无 summary 但有心跳/日志的任务必须保留消耗下界和 UNKNOWN，不能恢复完整预算。

### T07 [P2，身份断言缺口] 相同标量统计被当作相同首个目标

位置：`tests/test_failure_mechanism_audit.py:14-19`。定点函数：`scripts/experiments/server_failure_mechanism_audit.py:258-264`，消费者 `:384-388`、`:404`。

测试只让两个字典完全相同或 target_ss 改变。生产 helper 只比较 target_ss、target_count、loss_initial，并把结果命名为 first_E_target_identity_match。两个不同目标，例如 `[1,0]` 与 `[0,1]` 对同一个零预测，都有相同 SSE、点数和初始相对损失；这三个数字不能证明数组、交错支撑或网络身份相同。这里的碰撞是由字段定义即可确定的静态合同限制，未执行数值反例，也未全面审查该目录。

触发：不同目标恰好具有相同统计，或输入/坐标/权重改变但三个统计不变。测试没有这种反面夹具。

旧结果影响：SR-FAIL-AUDIT 的这一布尔值单独只能说明统计一致，不能单独排除目标错位；不据此宣布实际 A-P/R2 的目标不同。主审查应确认其身份结论是否另有数组哈希或从冻结状态重建的独立证据。

建议：要宣称目标身份，应比较带 shape/dtype/分量顺序的目标及输入哈希，同时绑定配置、权重、phase 和源索引；若仅做快速统计筛查，改为明确的统计一致字段。增加同统计异内容的负例。

### T08 [P3，已确认的测试组织问题] 导入 TestCase 导致标准 discovery 重复收集16项

位置：`tests/test_pidon_contract_v3.py:23`、`:28-29`；原类 `tests/test_pidon_contract.py:74`。

v3 为取得 `_tiny_args`，将 PidonContractTests 直接导入模块全局。本机 Python 3.11 `TestLoader.loadTestsFromModule` 遍历模块中所有 TestCase 子类，没有过滤 `obj.__module__`，因此在发现原模块后，又从 v3 发现同一个16方法类。这是根据测试文件和实际标准库源码确认的收集行为，未运行 discovery。

触发：标准根目录 unittest discover。当前静态定义140项；若同时出现已有 F13 的4方法模块导入失败，计数可解释为 `140 - 4 + 1个导入错误 + 16重复 = 153`，与主报告旧执行记录吻合。这个推导不是本次新的执行结果。

旧结果影响：旧153项不是153项独立断言覆盖。重复项还包含128步精确/负面对照，增加运行成本和全局 RNG 干扰机会；不改变原始科学实验数值。F13 不在此重复计数。

建议：把 tiny_args 放入不含 TestCase 的 fixtures/helper 模块，或导入模块后通过模块访问，避免把类暴露给 loader；主 agent 后续可检查收集出的 test.id 唯一性。

### T09 [P2，物理合同缺口] 单位尺度和模式变化缺少针对生产测量的断言

位置：`tests/test_pidon_contract_v3.py:147-153`；`tests/test_pidon_contract.py:76-83`、`:179-189`；`tests/test_paper_protocol.py:19-43`、`:64-87`；`tests/test_r4_fixed_state.py:20-30`。

已有 Eq.(5) 精确零分支、单位敏感性、三分量宏/全局归约、curl 符号和 PEC 测试是有效覆盖。但生产 component_metric 用例固定 scale=1，只检查计数和两个指标不相等，未验证 `mre_eq5_physical` 的具体数值和零分支单位（F08）。Solver 夹具均为 tol_mode=rel、h_scale/h_output_scale=1，缺 abs 停止规则及输入/输出尺度变换的合同比较（F05）。

插值测试只在一个内部网格节点取样，没有支撑端点/越界/半格插值；根测试没有 eps_r 非真空或超 CFL 的拒绝/物理响应测试（F01/F12）。fixed_pairs 的顺序测试只断言第一步初始 Hx 为零及源点赋值，未检查第二步源外 H/E 的非平凡变化，不能证明 E->源->H 的全部物理顺序。

触发：尺度、单位、loss 模式、介质或探针位置改变，内部节点和真空相对损失用例仍绿。

旧结果影响：不能把已有小网格/真空测试外推到材料或全参数范围。源点正确不证明传播；原真空128结果不因未测介质自动失效，旧 FAIL 不改判。

建议：手算生产 metric 在 scale!=1、H/E尺度及严格零/弱参考下的结果；加入 abs/rel 不同停止结果的对照。补不等网格间距、各支撑端点、越界、介质及 CFL 合同；用非平凡初始场比较两步更新的六分量和源外场。

### T10 [P2，身份/部署缺口] 文本匹配和旧截止时间不能认证恢复/重装身份

位置：`tests/test_paper01_ablation_bundle.py:51-64`，尤其 `:56`；`tests/test_paper01_server_bundle.py:27-33`；`tests/test_night_budget.py:33-37`；`tests/test_project_harness.py:124-135`。

包测试要求出现 `existing.update(task)`、lab_log.py 等字符串，没有实际检查重装时已有状态、证据、活动行动和协议是否保留。定点读取生成安装器 `tools/build_paper01_ablation_bundle.py:49-53` 可确认它保护 PASS/FAIL，但其他状态仍进入 update，不能将这里误报为覆盖所有终态。已有 server_resource.merge_tasks 的幂等测试只覆盖另一安装函数。

night_budget 的“保持截止时间”测试刻意换了 source_hashes，却只验两个时间字段；`night_budget.py:121-135` 只验证计划/主权重/期限，不认证当前源码身份。harness 的迁移测试使用字面字符串 `sha256="historical"`，只能验证路径解析/存在，不能证明哈希一致。harness 已明确不做科学认证，这个范围应保留。

触发：在 RUNNING/INCOMPLETE 任务上重装包、换源码继续旧预算窗口、同名不同内容资产。文本断言和时间断言不能检测身份误认，关联 F07/F17 的补测需求。

旧结果影响：不据此宣称已审核 PASS/FAIL 被该 ablation 安装器抹掉，也不宣称任何已回传模型发生替换。只能说现有测试不足以认证重装/续跑身份。

建议：在临时模拟项目中测试 READY/RUNNING/INCOMPLETE/PASS/FAIL 与未结束 action，比较重装前后内容；把源码变更处理为显式登记的修订/拒绝，而非仅靠截止时间相同。路径迁移与内容身份测试分开，覆盖存在的外部绝对路径和同名异哈希文件。

### T11 [P3，数据依赖] 历史证据测试混入默认单元集合，缺少独立坏输入夹具

位置：`tests/test_night_evidence.py:15-31`；`tests/test_mechanism_claims.py:18-26`。

两份直接读取固定历史目录。night_evidence 两个方法各自 compute，一次 compute 会重载三个实际 checkpoint 并执行前向重测（`scripts/analysis/night_evidence.py:49-68`、`:102-129`）；不是仅解析几个小 JSON。mechanism_claims 固定断言26条、500更新等旧轨迹状态，读取路径还依赖 cwd（`verify_claims.py:77-94`）。它们适合独立历史集成审计，但不能提供缺文件、错哈希、非有限数据等处理分支的独立覆盖。

触发：干净 checkout、证据迁移、不同 cwd、权重依赖缺失，或审核器坏分支改变但当前旧数据仍走同一正常路径。本次只查文件存在：上述 mechanism 五个直接输入及 night 的 manifest/三个 checkpoint 目前存在；没有加载权重、复算指标或声称这些测试当前失败。

旧结果影响：历史资产缺失时测试失败不能直接判为物理回归；历史资产齐全时测试绿也不能证明审核器面对坏证据可靠。已有失败/不完整状态保护仍有价值。

建议：保留带输入 manifest 的显式历史集成审计；默认单元测试用最小临时夹具覆盖缺失/篡改/坏值与旧 FAIL 不可改判。明确执行所需 cwd、数据及预计成本；同一只读重测结果可按测试类复用。

## 其余已检查的合同及限制

- `test_project_harness.py` 的暂存目录隔离、依赖环/未知依赖、前置阻挡、append-only、已结束行动不可改判、报告 PASS 不自动解锁依赖、损坏账本保持原样，均有直接断言。这不是科学认证器，不能要求占位报告本身证明物理正确。
- `test_run_entrypoint.py` 覆盖旧输出保护、历史入口执行前拦截、输入迁移、缺 logger/action、协议哈希变更及已结束 action 拒绝。没有逐历史入口注册表的完整矩阵，也未覆盖求解器主函数恢复。
- `test_coverage_ab.py` 覆盖单个配对样本与现有生成器一致、200批日程形状/索引/完整 epoch 置换、逐样本相对 loss 等权；使用同一生成器作比较不能独立认证解析 curl。`test_phase1_pilot.py` 验证分段值和种子重现，没有验证实际更新总数。`test_trunk_repair.py` 则确实调用真实训练 helper，用最小网络验证 branch 不变、trunk 改变、优化器只有一个可训参数及200更新，但归一化和加载均被 mock。
- `test_head_lstsq.py` 的满秩仿射系数恢复、零靶秩亏、head Adam 状态清理、终态拒绝及中断不重复提交有实质断言；不能因 T03 抹除这些覆盖。未覆盖非零秩亏误差、病态系数、E角色/共享网络的全矩阵。
- `test_briefing_pec_audit.py` 验证形状/掩膜数量、真实 apply_pec 的边界与内部，以及玩具梯度支撑；梯度 demo 不是论文完整训练图等价证明。
- `test_briefing_operator_audit.py:44-50` 的图测试只验文件存在且大于1000字节，并未验四类面板/正确切片/误差数组。哈希测试确实验证一个权重改变会改变哈希，未遍历 buffer/dtype 等身份维度。不能以测试名代替图内容审查。
- `test_paper01_ablation_data.py` 验theta约束、Ez cap、projected横向性和诊断标签；不验共同测试集、相同初始化/种子或训练干预的配对设计（F03）。已知F13仅作为运行边界引用，不另立问题。
- `test_paper01_data_contract_audit.py` / `test_paper01_s1_diagnosis.py` 覆盖构造横向性、分箱末端、常量相关性和收敛比值；横向性只有一个正例，history_trend的样例每行都有验证值，没有无验证行/零分母/NaN/缺窗口负例。
- `test_first_e_budget_probe.py:10-12` 与 `test_failure_mechanism_audit.py:10-12` 只测试严格低于阈值的命中。两被测 trace_crossing 使用 `<=`，而 Solver 的正式 reached 是严格 `<`；等号、乱序和坏值需要明确合同后补测。当前 crossing 是诊断字段，不能据此把某次正式接受状态改判。
- `test_paper01_ablation_status.py` 覆盖两臂运行/完成的显示字段，不验证完整交付；没有半写JSONL、损坏summary、缺臂或失败状态夹具，不能作回传验收替代。

## 逐文件覆盖清单

路径均相对 `C:/PI-DON/`；“完整”指静态阅读全部行。合同覆盖是所列子集，动态覆盖率及执行结果均 NOT_RUN。SHA256 为审查时文件原始字节哈希，不对换行做规范化。

| 文件 | 阅读 | 行数 | 已检查断言 / 主要未覆盖 | SHA256 |
|---|---|---:|---|---|
| tests/test_briefing_operator_audit.py | 完整 | 54 | Fig5假设、毫米坐标、参数hash、出图存在；图内容见其余限制 | B5C1ED1B121084ADED7B706FB12EB8959296AD282B85521D525A7AA29D6DDE86 |
| tests/test_briefing_pec_audit.py | 完整 | 37 | PEC掩膜、生产边界/内部、玩具梯度；未证论文完整图等价 | 5F05442C7E1705AAF16A9F36257598681D3382A357DCC3D7CF53F210F3479F62 |
| tests/test_coverage_ab.py | 完整 | 43 | 单样本配对、批日程、loss等权；未独立验解析标签 | 28713B6C0A3AAEA7C32378E1AC667322EFEB73FE24E9EB4DE54447B15C4EB0CB |
| tests/test_direct_mechanism_m0.py | 完整 | 35 | 空指标JSON、M0布尔和非零成本；T06 | 5A7D2AB9602784C16D55C32AB984ADA1282B4329D1A286557075221FBCB9FE3C |
| tests/test_failure_mechanism_audit.py | 完整 | 37 | crossing、三标量匹配、弱分量摘要；T02/T07 | D96D3AB476471ECDECF1ACF8C233BA55CF25368D71FE29BC0D57C37FE857327B |
| tests/test_first_e_budget_probe.py | 完整 | 26 | 首阈值命中、失败距阈值倍数；未验实际预算/坏值 | 6159D20161798BCEC746A73A723B199FD84C1CE79095371A5A4AB6B51AE56959 |
| tests/test_head_lstsq.py | 完整 | 111 | 仿射头、秩亏零靶、提交、Adam状态、恢复；T03/T04 | DCC8030C0DD0F3388ACB52FD6AA0FE05B20523F206E62601E938663F93D8E5F7 |
| tests/test_ingest_paper01_ablation_return.py | 完整 | 82 | 摘要表/建议、内存计划更新；T01 | 0B70FBA5244104576CFF307425B327C8410DCBC69AC1FA586224AF4CFF6DF763 |
| tests/test_ingest_paper01_return.py | 完整 | 78 | 文件/摘要夹具通过、缺history；T01 | 7FB42A3AA1A04FE4DECC2F601662A5A4028613F7CF4D9961C1B750E64FA99272 |
| tests/test_mechanism_claims.py | 完整 | 30 | 固定旧失败/部分轨迹状态；T11 | 6593575D842E6F09473458F68D1001762F150BF6E92640965F1895DF4DC7FA99 |
| tests/test_mechanism_decision_eval.py | 完整 | 31 | 两种波数schema、采样shape；未验场/curl数值 | 1893F93EF0189D7F6294B20EAAA769AFFF34C480CB3CB2ABB26ABDDFB0CE0012 |
| tests/test_mechanism_first_failure.py | 完整 | 28 | 非零靶三分量/总R手算；未验零/弱靶/坏值 | 1F717F827EE279B3BC7682709F2FB064651E5368D4387176710A666D71D1EF6E |
| tests/test_mechanism_hour.py | 完整 | 46 | 截止时间、单行失败成本、心跳；T06 | 23A5BC87C1318D144085EC7D75F18D2F6B105AFF4700B41D6AF2E747A7C59626 |
| tests/test_night_budget.py | 完整 | 66 | 截止、计划变更、任务上限、重复序号；T10 | 769289BBFE14094AF09CCBAA78FC08ADAB0F5CC59C7153754233519A82E337E7 |
| tests/test_night_evidence.py | 完整 | 35 | 旧门状态、磁盘重测标签；T11 | 3E08BE8D00DC05C4C7D907B45AA34F9A460250BAE868BF6A0403AAE02897E728 |
| tests/test_paper_protocol.py | 完整 | 94 | Eq5/归约、横向波、curl、PEC、NaN；T09 | D88127893DFB0C59B751DBD6512C27CCE240281899E93125DBA95AFA507FA56C |
| tests/test_paper01_ablation_bundle.py | 完整 | 68 | zip重复hash、sidecar、清单/脚本文本；T10 | A8C00CC0B8F6FA866C3129009F0908C68207D7CE6C17EC88A58A1C23D8B5A3D2 |
| tests/test_paper01_ablation_data.py | 完整 | 38 | theta/Ez限制、projected横向性/标签；F13已知，缺配对设计 | A060ABB2D8DAD32A204945F6352BE72B1775F3F9C4F5419D189C0D4FA2CEBA6E |
| tests/test_paper01_ablation_status.py | 完整 | 56 | 两臂进度显示；未验缺/坏/失败证据 | 6F34BD52C52BE5EEE007C5EEC246564EF0459E3E8B5840D82FF9D2EE6D25E60A |
| tests/test_paper01_data_contract_audit.py | 完整 | 30 | 横向性正例、分箱、相关性；缺负例/坏值 | 72E7D448EAE004855E36F15DF3BFF6ABE59C08E9FB70E22A7CC24A72995BE4D4 |
| tests/test_paper01_s1_diagnosis.py | 完整 | 39 | 分箱/相关性/收敛比值；缺验证缺口/NaN | B74AA72549EE838E69E2E2E6501D685AC14E20AA06E8DD283AAF94C5ACA02340 |
| tests/test_paper01_server_bundle.py | 完整 | 37 | 包清单、无权重、脚本文本；T10 | DE3A5DD32C12D46FE5CA14F622BDD4AF80485BB515CEE4C0D509E8BA27C2819A |
| tests/test_phase1_pilot.py | 完整 | 33 | 分段预算值、无效值、随机日程重现；未验实际更新 | F371A2EBAB4A82A45F27E63EF1D9FE9691EDCEBF2F9662709AEE663C118FD6D4 |
| tests/test_pidon_contract.py | 完整 | 286 | 事务、终态、零靶、回滚、curl、控制；T05/T09 | 9052D78F188D798C8BB77ADCC1AAF42A3D9E0C05EAF54556FDB065CAA02A7117 |
| tests/test_pidon_contract_v3.py | 完整 | 294 | 配置/身份、成本、持久化、Adam/LBFGS恢复；T04/T05/T08 | 2A777C1C6B737A8688CD8C7CBC767C2EF93E8E4FD5C9081EC7DE98FC8FBE8B32 |
| tests/test_pidon_contract_v4.py | 完整 | 165 | JSONL崩溃/NaN、raw、终态、物理R、回滚；T04/T05 | EC142790BF6CDA439D4395426F08666DB63E37B02EAF7AE5FC27F06BC0B4FDDF |
| tests/test_project_harness.py | 完整 | 147 | 依赖/行动/证据路径/append-only/坏账本；T10 | 14EA5387C7F4C356BE69D13D6A70E5739A3A666461B480F1B8ECE3631A97D758 |
| tests/test_r4_fixed_state.py | 完整 | 39 | 字段全集、首源赋值、零预算配置；T09 | 35CAC7013D4C41F7FA72E830D80114E2C71A10741E41FA8E734DEEEA1517BD1D |
| tests/test_r4_p4a.py | 完整 | 27 | 五个冻结配置常量；T06 | F19E635948A8753D8D704632078532DC4F4E81FFD6A1C61C6023E22E17943C8C |
| tests/test_run_entrypoint.py | 完整 | 71 | 旧路径保护/路由/action协议与终态；T05 | B6851DCC1ADD1AA960EC0BF7F4C118C500C8C355DE504260A905D0B1BBD81025 |
| tests/test_server_resource.py | 完整 | 97 | 失败成本、均值vs逐样本、幂等、元数据/保存失败；T06 | 7AF195FC28A19CC2D22E09DDE302588FBB060B4B916894E84D8869811A8BD3F2 |
| tests/test_stop_review_claims.py | 完整 | 35 | 开发集完整性/双curl/失败不改判；T02 | 1DC5497723E7E8FCCD89E41ED277C51126238085F09680699895596D7666C9F7 |
| tests/test_trunk_repair.py | 完整 | 47 | 真实helper的冻结branch/更新trunk/200计数；依赖mock边界 | BDF97152C5ABA8EBC0C4D6486EC6BDAE190A2A4E113929623734C30B06BA7595 |

## 定点源码阅读与建议交接

只定点读取了被测相关函数/片段：`pidon_solve.py` 的 predict/head、inner_train停止与优化器切换、payload/load；`pidon_recording.py` 的 RNG 与 rolling_checkpoint；`dco.py` 的 Block/DCO前向；`pidon_exact_control.py` 的替代预测和run；`night_evidence.py` 的compute/重测；`verify_claims.py` 的mechanism reader；`server_failure_mechanism_audit.py` 的统计身份/调用点；`server_first_e_budget_probe.py` 的crossing；`night_budget.py` 的manifest身份；`ingest_paper01_return.py` 的audit；`build_paper01_ablation_bundle.py` 的生成安装器/任务字段。以上均为**部分覆盖**，不认领其所在目录或完整文件审查。

建议主 agent 按科学验收负例（T01/T02）、恢复及成本故障（T04-T06）、身份与无目标泄漏（T03/T07/T10）、测试组织/数据隔离（T08/T11）顺序准备可审阅修复方案。是否修改、运行哪些测试由主 agent 汇总交用户决定。本次所有建议测试仍为 NOT_RUN，未将测试绿色或报告交付等同于论文复现 PASS。
