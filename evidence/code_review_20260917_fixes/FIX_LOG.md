# 20260917 代码审查修复记录

日期：2026-09-17。范围：按 [REVIEW](../code_review_20260917/REVIEW.md) 和
[决策简表](../code_review_20260917/DECISION_BRIEF.md) 实施生产代码修复。

**这份记录说明改了什么代码、为什么改、影响边界到哪里。它不是科学认证，也不改判任何历史结论。**

## 本次没有做的事

- 没有重新训练任何模型，没有产生新的科学成绩，参数更新数为 0。
- 没有改写 `evidence/` 下任何历史证据、权重、`failure_raw`、旧 summary 或旧 FAIL。
- 没有连接服务器，没有中止或重启服务器上的任务。
- 没有补造缺失的 `direct_mechanism_v1/runs/` 四份 M2 摘要。
- 没有放宽任何已登记门槛；有两处反而把「均值门」和「逐样本门」分开报告。

## 一条重要的兼容性提醒

`source_hashes` 的冻结清单从 5 个文件扩大到 9 个（补上 `head_lstsq.py`、
`paper_protocol.py` 等实际被导入的依赖），因此 `protocol_hash` 会变化。

**后果：在修复前的代码下开始、尚未结束的正式运行，不能在修复后的代码下 `--resume`。**
这是正确行为而不是缺陷——求解器源码已经改变，继续原轨迹就是在偷偷更换动力学。
这类任务应当在它自己的冻结快照下跑完，或登记为独立新实验重开。

## 修复清单

### 一、物理与测量合同

| 编号 | 位置 | 改了什么 | 影响边界 |
|---|---|---|---|
| F01 | `src/pidon/fdtd.py`、`src/pidon/pidon_solve.py` | `eps_r` 现在真正进入 E 更新。新增 `sample_eps` 材料合同：`None`/标量/可调用函数三种形式，可调用形式在 Ex/Ey/Ez **三个交错支撑上各自采样**；裸数组因为没有声明的交错规则而被拒绝。第二阶段 `_update_E_and_source` 改为读取腔体的 `e_coefficients()`，不再写死 `EPS0`。 | 真空配置下三个系数精确等于 `dt/EPS0`，轨迹逐位不变（已验证）。介质能力是新增的，**没有任何历史结果依赖它**，也不因此产生任何介质实验结论。 |
| F12 | `src/pidon/fdtd.py:PECCavity.__init__`、`pidon_solve.main` | 超 Courant 限的构造由「打印警告」改为**拒绝**；超 CFL 研究必须显式传 `allow_super_cfl=True`。CFL 上限按材料最快波速 `C0/sqrt(min(eps_r))` 计算。 | 已登记的 `n=31 / dt=3.075ps` 配置 `dt/CFL=0.98996`，照常构造。`n=32 / 3.075ps`（比值 1.021895）现在报错。这不是当前真空 128 分量误差的已证实原因。 |
| F05 | `src/pidon/pidon_solve.py:stop_met` | 绝对损失模式的停止判据改用绝对物理 SSE；`rel` 模式不变。 | 服务器 short 配置显式使用 `rel`，**现有 64/128 结果不受影响**。 |
| F08 | `src/pidon/pidon_contract.py:component_metric` | Eq.(5) 零参考分支现在乘回尺度，真正是物理绝对误差；原来的归一化读数保留为 `mre_eq5_normalized`；新增 `mre_eq5_zero_branch_units`、`strict_zero_absolute_mae_physical` 和混合单位说明。 | `nMAE`、`relative_l2`、求解轨迹都不变。旧表里的 `mre_eq5_physical` 数值对应现在的 `mre_eq5_normalized`，跨表比较时按名字对齐。 |
| — | `src/pidon/pidon_contract.py:trilinear_sample` | 最高合法网格节点改用退化插值，真正域外仍然拒绝。 | lab325 的 `(2,1,1)` 现在正确返回 22。当前三个内部探针不触发该分支。 |
| — | `src/pidon/pidon_solve.py:_step_summary` | 参考场按 `solver.dtype` 转换，不再默认降到 float32。 | float64 DUT 不再与被降精度的参考比较。float32/n31 的当前配置数值不变。 |
| — | `src/pidon/pidon_solve.py` | 新增 `validate_source_outside_probes`，开训前校验固定探针几何；最终 `nMAE` 打印改用可选格式化器。 | 已登记探针的物理位置**没有被改动**；小网格现在提前报错而不是跑完一步再崩。 |

### 二、验收、审核与报告

| 编号 | 位置 | 改了什么 | 影响边界 |
|---|---|---|---|
| F02 | `scripts/experiments/server_short_tol_probe.py` | 场门要求六分量齐全（缺项 `INCOMPLETE`）、拒绝非有限值、**把源外探针纳入判据**；新增 `window_field_gate` 做全窗口 + 源外整段波形相对 L2；科学 PASS 需要端点门和窗口门同时通过。 | 验收器原来确实能接受不完整记录；这不等于某次真实记录缺分量。旧 `PASS_64` 的范围以它当时实际核查的端点指标为准，**已明确的 Ex/Ey FAIL 不改判**。 |
| F02 补 | `scripts/analysis/direct_m2_audit.py` | 缺分量、非有限 nMAE、未检查的 Q 和弱场绝对门全部纳入；`field_gate_status` 分 PASS/FAIL/INCOMPLETE。 | 同上。旧 `m2_audit.json` 原文保留。 |
| F04 | `tools/ingest_paper01_theta_full_return.py`、`tools/ingest_paper01_ablation_return.py`、新增 `tools/ingest_contract.py` | 回传审核不再复述摘要自己的 `status`：核对必需文件、history 编号、成本、优化器 step 计数；读取状态 / 交付完整性 / 科学判据三层分开；缺件 `INCOMPLETE`。 | 反例（只有 `{"status":"PASS","variants":[{}]}`）现在是 `INCOMPLETE`。这不表示实际回传缺文件。 |
| F20 | `tools/ingest_paper01_return.py` | `history_complete` 改为严格校验编号为 `[1..25000]`、唯一、递增、每行损失有限；另从 `last.pt` 的优化器状态独立核对更新数。 | 25000 行全写 `update=25000` 不再算完整。原来的行数/末号检查保留为 `history_row_count_and_last`。 |
| F29 | `scripts/experiments/g0_verifier.py` | `control_integrity` 拒绝空源码哈希表、要求必需模块在表内、并把 summary 的行**逐行绑定到磁盘 steps.jsonl**；`control_numeric` 把「结构完整」和「数值正确」分开；负对照必须先通过完整性检查再被数值拒绝，缺项记 `INCOMPLETE` 而不是「负对照成功」。 | G0 的两个布尔值原来确实可以在结构不完整时通过。尚未发现真实历史 summary 与磁盘被这样替换。 |
| F27 | `scripts/experiments/direct_benefit_runner.py` | 收益判定改为 `residual_window_comparable` / `all_field_gates_pass` / `cost_saving_pass` 三层，叙述由同一规则派生；`field_gate_benefit_pass` 现在名副其实。 | 旧 B 场门全部失败，所以旧「未支持预训练收益」结论**不翻转**。 |
| F25 | `scripts/experiments/direct_m2_runner.py:classify_stop` | 异常优先于步数：到达目标步数但保存异常返回 `EXCEPTION`，其它非正常停止返回 `INCOMPLETE`。 | 未证明真实已完成轨迹触发过该情形。 |
| F22 | `scripts/analysis/direct_m2_audit.py`、`scripts/analysis/direct_final_judgment.py` | 缺 summary 但目录里有证据记 `INCOMPLETE`，目录不存在或为空才记 `NOT_RUN`；默认写入新的时间戳目录，只有显式 `--overwrite-historical` 才改写原路径；`stage_status.json` 在新目录模式下不改写；解释段由审核数据派生，删除硬编码旧叙述。 | 已有旧报告不因当前缺路径改变。 |
| F28 | `scripts/experiments/mechanism_hour_runner.py` | `finalize_arm` 先读已有终态，遇到 `PASS`/`FAIL` 直接拒绝改写；恢复资格改为验证指针 schema、槽位文件存在、哈希匹配并覆盖日志末尾；`update_status` 同时重算 manifest 顶层 `updates_this_experiment` 并标注下界。 | 真实一小时 manifest 的顶层 0 仍不能用于科学成本结论；`S-P-retry` 的恢复字段仍不构成认证。本修复不声称历史 S-R 曾被改判。 |
| F30 | `scripts/experiments/direct_m1_diagnosis.py` | 每个输入先建立带自己 `case_id` 的完整 note，缺量记 `INCOMPLETE`，不再通过列表末项隐式关联。 | 修复前第二个案例的数值会写到第一个案例的 ID 上，首个案例缺值则 `IndexError`。已保存的历史数值不变。 |
| PR02 | `tools/build_briefing_deck.js:324`、`slides/make_stage2_figs.py:30` | 删除「比论文 9.6e-3 严很多」的表述：项目 R 是内层停止量，`9.6e-3` 是场 MRE，等价关系未确认，不算严格倍数；图中的 `1e-4` 参考线改标为「本项目相对损失门」。 | 原始 R、Q、分量误差和耗时数值**都不变**，改的是比较说法。 |
| PR04 | `tools/build_briefing_deck.js:392` | 32³ 的 `2.791e-3` 来自 `test_results_dco_lr1e3_300.npz`，不属于 paper32；表格拆成两列，paper32 的 32³ 填其真实值 `4.738e-3`。 | 原始数值不变，改的是模型归属。 |
| PR14 | `tools/build_briefing_deck.js:425` | H 的「六个 Yee 支撑数组」改为三个。 | 只改讲解维度。 |
| E01 | `scripts/experiments/mechanism_decision_eval.py:diagnostics` | 叠加测试改为同输入可加性：把同一组波分成两半，两半之和精确等于原输入，并记录拆分残差；旧口径保留为 `legacy_partial_sum_defect_relative_l2` 并注明它不是非线性度量。 | 已保存的 `0.787333` 原值不动；它不能用来量化 DCO 偏离线性多少。 |
| E02 | `scripts/experiments/stage2_shared_interference.py` | 三次 H 残差固定用同一份精确 `curl-H` 目标；E 更新用的预测插入写进独立数组；旧口径另存为 `legacy_H_degradation_ratio`。 | 已保存的 `831.6` 原值不动；它不是同目标下的前后比较，不能量化遗忘程度。共享参数是否有干扰仍未判定。 |

### 三、恢复、部署与记账

| 编号 | 位置 | 改了什么 | 影响边界 |
|---|---|---|---|
| F18 | `src/pidon/pidon_solve.py` | 模块同时绑定 `Path`，`--resume` 不再 `NameError`。 | 该通用 CLI 的恢复功能此前不可用；服务器新轨迹直接调用 Solver/专用运行器，**不能因此说那些从零训练没运行**。 |
| F19 | `src/pidon/pidon_solve.py`、`src/pidon/pidon_recording.py` | 新增 `assert_checkpoint_continues_log`：恢复必须从**日志末尾的唯一提交点**开始，校验提交序号、已接受步、时间层、phase、`source_index` 和预算；存在未 checkpoint 尾部时拒绝并指向只读诊断分支。新增 `RunRecorder.durable_rows()`。 | 修复前可以用旧快照重放已记账的物理时间步（日志物理步号 `[0,1,1,2]` 而 `sequence_id` 仍连续）。没有证据表明当前 P/R128 走过这条路径。 |
| F06 | `src/pidon/pidon_recording.py:rolling_checkpoint` | 活动槽由**已提交并通过哈希校验的指针文件**决定，metadata 只作后备；`load_rolling_checkpoint` 另外校验指针/载荷/日志三者的序号关系。 | 关闭了两次注入式中断复现的窗口。没有证据表明已完成的正常训练触发过它。 |
| F07 | `project_paths.py:resolve_legacy` | 项目外的绝对路径不再退化成文件名匹配；只有登记的旧根（`LEGACY_ROOTS`，可用 `PIDON_LEGACY_ROOTS` 覆盖）才映射。 | `C:`→`H:` 的已知迁移照常工作。同名外部模型（如 `Z:/independent_study/dco_lr1e3_300.pt`）不再被悄悄改写。**路径相同仍不等于模型相同，身份要用内容哈希。** |
| F17 | 新增 `tools/plan_state.py`，接入 10 个 `server_*_queue.py` | 安装队列变成幂等：已有任务保留 `status`/`scientific_result`/`evidence`/`execution_plan`，只刷新描述字段；没有任何结果记录的任务才可被重新登记为 READY。 | 修复前重复安装会把「交付 PASS、科学 FAIL、有证据」改写成「READY、NOT_RUN、evidence=[]」。**这只是计划状态失真，不等于发生过重训。** |
| F23 | `scripts/experiments/direct_mechanism_runner.py:budget_from_rows` | 按 (时间层, 半步) 取累计最大值再求和，恢复段不再重复计入；同时输出旧的逐行求和 `adam_row_sum` 与 `resume_double_counted_adam` 以便对账。 | 反例：中断 1 + 恢复 2，旧公式 3，实际 2。旧 `m0_audit.json` 记录的 5 保留原文，不原位改写。 |
| F26 | `scripts/experiments/direct_m2_runner.py:existing_m2_cost` | 无 summary 的臂改为从已提交的 `steps.jsonl` 复原成本下界；完全无法确定的臂进入 `unknown_arms`，此时**拒绝开训**而不是按「未消耗」重新领取预算。 | 不据此断言过去正常全摘要队列超预算。 |
| F24 | `src/pidon/pidon_solve.py:inner_train` | Adam 循环中的中断请求会阻止进入 LBFGS，保留可恢复的 `interrupt` 语义。 | 当前 LBFGS=0 的服务器正式轨迹不触发，**不能用它解释那些耗时**。 |
| F21 | `scripts/experiments/phase1_full_run.py` | ①`full_batch_equivalence` 真正比较阈值（损失相对 `1e-5`、梯度相对 `1e-4`），失败时调用者拒绝开训；②`recovery_eligible` 由硬编码 `True` 改为 `False` 并附逐项 `recovery_contract`（独立 Generator 状态、批游标均未持久化）；③`--allow-existing` 停用——它从来不是恢复，只会重开模型并把两条曲线混进同一个 history；④场门同时报告均值归约与逐样本归约。 | S1/S1R 已完成的 25000 生产更新**不因此减少**。旧 epoch937 的中断仍为 `INCOMPLETE`。 |
| F14 | `lab_log.py` | 完整产出清单另存 `records/output_manifests/run_*.json` 并记录其自身哈希，JSONL 行内仍只保留最大的 25 条但标注 `outputs_truncated_inline` 与总数；大文件改为流式哈希。 | 修复前 26 个产出只留 25 个，最小文件无提示遗漏。**不说明被遗漏文件的数值一定错误。** |
| F15 | `lab_log.py` | run id 改为带锁的预留（`records/lab_run_reservation.json`），并行 wrapper 不再拿到同一个 id；每次运行另有 `run_uuid`；Ctrl+C 现在会停止子进程并落账，标 `cost_accounting: LOWER_BOUND`。 | 同一主机 + lab_id 此前未必唯一。旧中断训练的成本缺失仍不能靠该工具恢复成精确总数。 |
| F16 | `lab_log.py:do_verify` | 退出码分状态：0 一致、3 缺失、4 哈希不符、5 两者都有。 | 人读输出不变；只依赖进程成功的自动流程不再误判。 |
| F13 | `project_paths.py` | `SOURCE_DIRS` 补 `_01/src`，根目录 unittest 可以导入 paper01 测试。 | 测试流程此前确实不完整；这不是训练失败原因。 |
| L01/L02/L03 | `tools/layout_guard.py`（新增）、`repair_layout_paths.py`、`finalize_layout.py`、`reorganize_workspace.py` | 迁移表在动任何文件之前整表校验（拒绝绝对路径、`..`、解析到项目外、目标或其父目录是链接）；`contained()` 返回未解析路径并拒绝链接，避免 rename 搬走链接指向的真实证据；finalize 先检查账本前置条件再改源码。 | 本轮 233 个 `new` 字段都没有绝对路径或父级遍历；没有证据表明历史发生过越界写入。 |
| L06/L07 | `tools/audit_reorganization_delivery.py`、`tools/write_reorganization_report.py` | audit.json 先写 `audit_status: INCOMPLETE`，全部断言通过后才改成 `COMPLETE`；新增 `backup_reverification()` 重新比对 114 份原备份与登记的 `sha256_before`，把「仅换行差异」和「未解释差异」分列；**登记值一律不覆盖**；报告在 `audit_status != COMPLETE`、或存在未解释差异时直接拒绝出报告和把 W0 写 PASS。 | 保留原登记值，另查差异。备份字节不符**不证明权重或场数据损坏**。 |

### 四、第一阶段独立参考线（`_01`）

| 编号 | 位置 | 改了什么 | 影响边界 |
|---|---|---|---|
| F03 | `_01/train_phase1_ablation.py` | 变体索引不再折进种子：各臂默认**配对种子 + 共同初始权重**，并新增一份与所有训练集分离的**共同试卷**（默认 baseline 分布 200 样本），每臂都在上面评分。报告新增共同试卷列，并写明自测列来自各臂自己的变体分布。`--legacy-variant-seeds` 可复现修复前行为做对照。 | 现有四臂数值**保留**为各自分布内的诊断。`0.726 倍` 不能单独证明角度过滤提升原任务——要用共同试卷列重新核实。 |
| F09 | `_01/src/paper01/metrics.py`、`runner.py`、`train_phase1_ablation.py` | 新增 `component_normalized_vector_rel_l2`（＝原 `global_rel_l2`）与 `physical_vector_rel_l2`（用被归一化拿掉的分量尺度还原），并附 `metric_contract`。 | 各线原有定义内的数值可以保留，但**同名列不能直接算改善倍数**。 |
| F10 | `_01/src/paper01/runner.py` | 新增 `split_contract`，明确写出 `test_*` 是开发集（参与选模又被当最终成绩）；新增 `blind_fraction`（默认 0，保持已登记协议逐字节不变）用于将来封存真盲测。 | 影响泛化证据强度和命名，**不说明训练计算本身错误**。旧 S1R 另有独立盲测，此问题不套用到 S1R。 |
| F11 | `_01/src/paper01/metrics.py` | 还原尺度来自**目标自身**的分量最大值，因此 `physical_vector_rel_l2` 明确标注为诊断量，不是只由输入可得的还原规则。 | 这是未解决的模型使用假设，不是已证明作者方法有错。第二阶段接入前仍需登记可逆的输入/输出尺度合同。 |
| — | `_01/src/paper01/runner.py`、`_01/train_phase1_ablation.py` | checkpoint 改为写临时文件 + `fsync` + `os.replace` 的原子替换，并写入 `resume_contract` 说明批游标未持久化、该文件不构成恢复授权。 | 没有证据表明当前正常完成的 best/last 损坏。 |

## 验证

- 新增 `tests/test_code_review_20260917_fixes.py`：64 个负面/边界测试，逐条复现审查记录的反例并断言修复后的行为。
- 根目录 `py -3.11 run.py unittest discover -s tests`：220 项，2 个错误。
  这 2 个是 `test_night_evidence` 读取 `evidence/gpt6_plan_v4_night/n3_fixed/step_0043_H.pt`
  等 `.pt` 文件失败；这些文件被 `.gitignore` 排除，只在本地工作树存在。
  **修复前的同一批测试有同样的 2 个错误**（另加 1 个 paper01 导入错误，已由 F13 修复）。
- `_01/tests`：8 项通过。
- 真空系数逐位核对：`Solver._e_coefficients()` 三个分量精确等于 `dt / EPS0`。
- 参数更新数：0。没有运行任何训练。

测试通过只表示复现了预期行为，**不表示论文复现成功，也不认证任何科学 PASS**。

## 尚未处理、需要用户决定的事

1. **是否要研究非真空。** F01 的材料合同已经实现并有测试，但没有登记任何介质实验；
   要做介质块、非均匀介质或论文 Fig.8，需要单独登记新实验和新的验收判据。
2. **共同试卷的完整重训。** F03 的机制已就位，但四臂的完整重训属于新实验，未启动。
3. **`_01` 的封存盲测。** `blind_fraction` 默认 0，保持已登记协议不变；要用真盲测须登记新实验。
4. **第二阶段的尺度还原合同。** F11 只是把问题标明，没有给出只由输入可得的还原规则。
5. **性能优化。** 本轮没有做 GPU profile，没有移除任何审计或安全检查；
   静态热点仍按审查结论「不能宣称其中某个已解释小时级差距」处理。
6. **`direct_mechanism_v1/runs/` 的四份 M2 摘要**仍缺失，harness 路径检查仍不通过。
   本轮不自行恢复、不删除、不补造。
