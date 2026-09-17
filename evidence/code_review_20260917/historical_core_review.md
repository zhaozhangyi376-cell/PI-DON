# 历史核心数值源码差异只读审查

日期：2026-09-17。范围仅为 `historical_deltas_v2/index.json` 中 `partition=core` 的 22 组、132 份历史成员。22 组完整 diff 共 4771 行，已逐行读完。本报告不是全项目无缺陷声明，也不是数值复算或论文复现认证。

## 范围、身份和方法

目标差距：判断哪些历史源码变化会改变演化、停止、评分或成本解释，防止用当前版本的优点或问题反推所有旧实验。行动合同：任务 `HC-STATIC-20260917`；待区分“数值规则变化”“仅测量/追溯变化”“仅布局/注释变化”；冻结范围为上述索引；被审模块导入、脚本执行、测试、推理、训练、GPU、优化器更新预算均为 0；成功判据为真实完整差异阅读、逐成员身份核对、历史原文件精确行号和未测边界。缺证据只列 INCOMPLETE，后续由主审整合、用户决定是否修复。

已读项目 AGENTS、PLAN、STATUS 和主审 REVIEW；为去重定点阅读已有专题及 v3/v4 历史审查。遵照本次更具体的只读约束，没有运行 `run.py`、harness、lab_log 或任何被审 Python 文件，没有登记行动、修改状态/旧证据/权重/账本/git，也没有再派 agent。文件操作只有读取/哈希，以及新增本报告和覆盖 JSON。

- 索引原始字节 SHA256：`f5104270c02f62511f2acf14271069bc097636ac70b7e5925174f59b29bf77a0`。
- 对 132 份成员逐个计算原始字节 SHA256，与各自 `members[].sha256` 比较；再以 UTF-8 文本统一 CRLF/CR 为 LF，计算内容 SHA256，与对应 `normalized_sha256` 比较。全部匹配，0 缺失、0 不符。
- 除人读完整 diff 外，另以只读 PowerShell 在内存逐 hunk 校验上下文，将当前 canonical 按 diff 转成历史文本，与代表原文逐行精确比较。22/22 重构相同，diff/source 行数均与索引一致。这是**文本身份核对，不是执行源码或数值测试**。
- diff 方向是 `--- 当前 canonical / +++ 历史原文件`；删除行代表“当前有、历史没有”。没有把这一方向反过来解释。
- 22 组都有 canonical，故“无 canonical 必须阅读全文”的分支为 0 组。两代 recorder 原文额外全文阅读，其余按差异涉及的实际调用读上下文；没有把整份历史文件未变部分虚报为本轮再次全文审查。
- 覆盖 JSON 保存每组 diff 哈希、canonical 哈希、成员身份核对、实际阅读区间及边界。相同规范化内容只合并内容审查，不合并执行身份或科学成绩。

HC 编号是历史差异定位索引，**不是可直接加到 F01-F30 的新增缺陷总数**。HC01-HC04 是本轮新增的具体历史定位；HC05 的 G109 部分是新增定位，G71 部分早有记录；其余明确标注已有纠正或版本影响。所有“可触发”均为静态控制流判断，本轮没有做运行反例。旧审查数值不在这里冒充重新复算。

## 新增历史定位

### HC01 [P1] 最早求解器只投影高侧面，低侧法向 H 可被网络误差驱动

位置：[G109 原文件:418](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:418)，同文件 427-429、442-446；输入切片见 172-180。当前对应 `src/pidon/pidon_solve.py:858` 增加低、高两面投影。

G109 把网络预测写入整个可预测立方体，仅把未覆盖的高侧 curl-E 面设为零。低侧 curl-E 面仍取网络输出，随后直接更新 H。对本项目零初场 PEC 腔体，精确切向 E 为零应保持法向 H 的相应边界不被激发；有限训练残差不保证该面的预测严格为零，因此旧代码可积累非物理边界 H。后来版本的双面投影会改变保存的 H 场和全域评分，不能称作纯整理。

影响边界：精确旋度控制本来就给这些面零值，不会证明真实 DCO 无此风险。[旧 curl_H:51](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/fdtd.py:51) 的精确差分不直接使用法向边界面；`h_shift=False` 时网络输入包含低面，才还可能反馈到后续学习更新，`h_shift=True` 的切片排除了该低面。不能笼统断言全部内部传播或当前 P/R128 失败由此造成。未读取对应旧轨迹全场数组，实际幅度和发生时刻未复算。G71 及之后的所审版本已含低高面投影。

### HC02 [P2] 最早 failure_raw 与活动参数共享存储，安全回滚会改掉待保存的失败权重

位置：[G109 原文件:378](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:378)，尤其 385-390；失败捕获/回滚为 458-460、471-473，实际写盘为 775-778；载入也未 clone（400-401）。

`state_payload()` 直接返回网络 `state_dict()`，未复制张量；CPU 场的 `detach().cpu()` 也可共享原存储。非有限分支先把此字典赋给 `last_failure_raw`，随后 `load_state_dict(safe)` 原位恢复网络参数。待 main 再写 failure_raw 时，字典中的参数已可能变成安全参数，不能据文件名认定保存了故障现场。保存在内存而延后落盘的普通 payload，以及在 CPU 上载入后继续原位更新的场，也有别名风险。

这与 F06 双指针崩溃窗口不同；即使没有文件中断也可丢失“失败参数”的身份。G71 起使用递归 `_cpu_clone`，加载场也 clone，消除了这里指出的 DUT 状态别名。该结论不宣称当前 reference payload 等所有缓冲都独立，也不证明任一现存旧 failure_raw 已损坏；本轮未载入权重或触发非有限训练。

### HC03 [P2] G97 的去源 nMAE 仍被已排除的硬源峰值归一化

位置：[G97 原文件:147](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_contract.py:147) 至 155；源 mask 为 173-177。

该版误差均值在 mask 内计算，却用整张参考场的 `max(abs(r))` 作 nMAE 分母。当源点是峰值且被排除时，分子评估的是源外区域，分母仍由强制赋值的源点决定，可能显著压低“去源 nMAE”。若源外参考全零但硬源非零，还会给出有限 nMAE，而非明确的零参考诊断。当前和 G137 已改用 `r[active]` 的最大值。

同函数的 weighted L2/Q、A_fixed 使用了 mask，不应一概说整个六分量指标都没去源。此项只影响测量，不改求解轨迹。G114 更早完全没有去源接口，见 HC09；G79 已与当前同公式。尚未逐时刻核对旧源外分母，不能直接用此项翻转某次旧场门。

### HC04 [P2] G71 的 float64 只传给场，未传给网络和坐标

位置：[G71 原文件:115](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:115)，120-125、155-157、164、170-185。

在默认 float32 的 PyTorch 环境中，`torch_dtype=torch.float64` 会建立 double 场和间距，但网络仅 `.to(device)`，坐标也使用默认 float32。真实 DCO 的非零 double 输入到卷积分支会遭遇参数/输入 dtype 不匹配；字符串 `"float64"` 也没有当前的解析函数。该接口不能据一个 dtype 属性就称为完整 double DCO 求解。

G109 根本只有显式 float32 转换；G112/G144 及之后才统一解析并传递 dtype。这里与主审提到的“评分参考又降到 float32”是不同位置的问题。精确控制若重写 `inner_train` 绕过网络，不触发本问题；不能据保存路径带 float64 就说那份控制没有运行。本轮未调用真实网络。

## 历史问题和版本影响

### HC05 [P2] 两代 LBFGS 中断行为不同；最早 n_updates 还混入成功提交数

位置：G109 [G109 原文件:318](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:318)、331-340、350-365；G71 [G71 原文件:374](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:374)、395-411。当前在每次成功 `LBFGS.step` 后刷新安全状态。

G109 捕获 closure 额度异常只 `pass`：strong-Wolfe 中途可能把参数留在试探点，外层 pred/loss 却仍来自此前完成的评估，没有回滚或再前向。保存参数与报告残差可不对应；异常原因还可能沿用 `max_updates`。它返回的 `n_updates=n_Adam+n_LBFGS_steps`，而 `n_lbfgs_steps` 又单列，不能把旧 n_updates 直接当 Adam，也不能再无条件加一次 LBFGS 成功提交。

G71 加入回滚，但只在进入 LBFGS 前取一次 `lbfgs_safe`，后续成功提交不更新它；第二次调用中断会退回全部 LBFGS 之前。后一问题已在 [旧 STOP_REVIEW](C:/PI-DON/evidence/gpt6_plan_v3_review/STOP_REVIEW.md:23) 记录，本轮只确认版本范围，不重计、不声称重新实测。该报告也明确其旧 P4-A 未触发这一回滚，旧局部 FAIL 不因此撤销。G112/G144 已维护逐成功提交安全状态和持久 LBFGS；但这不消除 F24 的跨优化器中断问题。

### HC06 [P1，已有纠正] 分量平均目标曾直接决定接受；F05 的 abs 回归不能倒推给它

位置：[G109 原文件:261](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:261)、274；[G71 原文件:315](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:315)；[G112 原文件:409](C:/PI-DON/evidence/gpt6_plan_v3/h_layout_candidate/source_snapshot/pidon_solve.py:409)；[G144 原文件:407](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_solve.py:407)。G135 则见 [G135 原文件:439](C:/PI-DON/evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_solve.py:439)。

G109/G71/G112/G144 的非零目标直接对优化 objective 判门。`component_rel=True` 时它是三个分量相对 SSE 的均值，并不等于总物理 SSE/target_ss；某个能量占主导的分量可以超过物理 R 门而均值仍通过。这会改变停止次数和被接受的场。G135 起按物理总 R 判门，此差异已被 [v4 历史审查](C:/PI-DON/evidence/gpt6_plan_v4_review/REVIEW.md:21) 指出；不作为本轮新发现。

反过来，旧 `tol_mode=abs` 确实用其 SSE objective 判断，不能把当前 F05“abs 也用 R 停止”套到这四组。带 H 缩放时旧 SSE 是优化尺度下的量，也不能进一步称其必与论文物理 loss 一致。共同 scalar 缩放、rel、非 component_rel 的常规非零目标下，两种门在数学上等价；浮点运算路径仍可能略有差异。没有证明某个历史候选启用了出问题的选项。

### HC07 [P2，版本规则差异] 早期零旋度门与默认接受方式都不同

位置：[G109 原文件:229](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:229)、248-264、274-275、450-476、680；固定尺度新版见 [G71 原文件:294](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:294)、315-325。

G109 对非零输入、严格零目标使用输入能量/最小网格间距平方作分母，按用户 tol 过门；component_rel 分支又直接使用各目标能量的 1e-30 floor，没有进入专门零靶门。G71 起改用固定 curl0 尺度，并要求固定均方门和最大绝对误差门。因此旧“zero target PASS”不等价于后来固定零靶规则，换版本可改变实际训练与停止。

G109 的 CLI `--strict-stop` 默认 False，有限但未达 tol 的子步仍能更新场并计 accepted_steps；G71 起 CLI 默认严格。旧命令必须显式检查这一开关，不能把“完成 N 步”自动解释为严格 N 步。原 FAIL 不改判，也不据当前较严规则回写旧记录。另 G109/G71 的零输入快捷判断只看裁剪 core，后来改为检查完整 field；若只有裁剪外有值且目标恰零，两版路径不同，但本轮未证明合法零初场轨迹触发。

### HC08 [P1/P2，历史影响] 参考 H 半层和失败半事务的场评分不能混为完整接受层

位置：[G109 原文件:748](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:748) 与 [G32 原文件:110](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/fdtd.py:110)；失败摘要为 [G109 原文件:613](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:613)、[G71 原文件:740](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:740)、[G144 原文件:904](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_solve.py:904)。

G109 的 DUT 做 E→硬源→H，参考却做 H→E 后覆写硬源。对同一零初场和精确更新，E 的时刻可以对应，参考 H 比 DUT 少一个半步更新；直接比较六分量会把 H 的错时误差混入学习误差。单独的传统 `fdtd.step` 并无错误，问题在联合评分的时间层。G32/G40 缺便利接口只是能力差异，必须结合调用才能判影响。G71 起 main 已调用 E→source→H，不能再用此点解释其局部拟合 FAIL。旧时间层纠正已见 STOP_REVIEW/HA02，本轮不重复数值验证。

G109/G71/G144 的 `_step_summary` 对 accepted=False 也出六场指标；若停在 E_pending，E 已更新而参考仍停在上个接受层，混合时间层没有完整场精度意义。若停 before_H，当前场可能仍是上一接受层，也不能当作本次成功推进。G112 和之后已将失败场指标置空。残差失败本身仍有效；不能把失败行的 Q/nMAE 与后来仅完整接受层评分作趋势比较。

### HC09 [P2，已有纠正] 旧同名 nMAE、weak_absolute_pass 和 MRE 并非同一测量合同

位置：[G114 原文件:126](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_contract.py:126)、151-171；[G137 原文件:153](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_contract.py:153)、165、183、220；G79 对应公式仅有布局差异。

G114 在全支撑上包含硬源点，没有 A_fixed、源外 mask、弱场/MRE 字段。硬源误差人为为零且增加参考能量，旧 global Q 不等于去源 Q。G97 已加 mask 和 A_fixed，但 nMAE 分母还存在 HC03。G137 把 `nmae/absolute_mae/weak_absolute_pass` 改成 dual-volume 加权均值；边界有半/四分之一权重，与普通 masked MAE 不同，跨版本可改变门判。

G79 恢复普通均值，并把体积均值另列。这是 [v4 历史审查](C:/PI-DON/evidence/gpt6_plan_v4_review/REVIEW.md:51) 已记录的纠正，不重复计数。G114/G97/G137 没有 `mre_eq5_physical` 合成字段，F08 不应套到不存在的字段；但它们的 absolute_mae 本来也是除以 E0/H0 后的量，不能称为未归一化物理绝对误差。G79 新增该字段后才承接 F08。评分变化不改旧权重，只有原数组足够时才能另行重算，不能从旧 nMAE 一个数反造新指标。

### HC10 [P2，部分已知] 恢复合同分三代，旧快照不能继承当前恢复资格

位置：[G109 原文件:252](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:252)、275、378-408、451-483、726-731；[G71 原文件:73](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:73)、85-87、336-337、469-516、833-843；[G112 原文件:283](C:/PI-DON/evidence/gpt6_plan_v3/h_layout_candidate/source_snapshot/pidon_solve.py:283)、658-680；[G144 原文件:273](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_solve.py:273)、656-678。

G109 无 frozen_config/fit_progress/pending_fit_H；重入拟合重新获得 max_inner/time/closure 额度，E_pending 恢复后的 H FitRecord 也丢失。改变 lr/dt/源参数没有完整兼容检查。它不具备当前生产续训合同。

G71 保存部分累计更新，开始扣减 Adam/closure 数，但每次调用的时间判断仍从零开始；raw 在 `_record_fit_attempt` 之前产生时进度会落后，LBFGS 状态不入 payload。冻结字段未含 LBFGS/dtype，缺失字段可绕过比较；config 可遗漏字段并静默覆盖显式 CLI。累计时间、LBFGS 配置及状态问题已见旧 STOP_REVIEW，不重计。

G112/G144 已有累计时间/closure/持久 LBFGS，却未拒绝终态：加载接受旧 stop_reason/resumable，进入拟合便清空原因并设 True。这是 v4 旧审查已记录的终态重入问题；不是 F19 的“旧 checkpoint 重放已落账物理步”，两者不可混称同一个窗口。G135 起的 required schema/terminal guard 才收紧此处。已完成的正常无恢复轨迹不因这些缺口自动失效；本轮不给任何旧失败恢复许可。

### HC11 [P2，历史追溯] 旧记录器的混写和提交窗口，与当前 F06 不同

位置：[G30 原文件:72](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_recording.py:72)、88-100；[G126 原文件:124](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_recording.py:124)、126-143、146-179；新 A/B 版本见 [G43 原文件:175](C:/PI-DON/evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_recording.py:175)。

G30 目录可复用，只在 metadata 不存在时写入，不校验新/旧身份，不分配序号；failure_raw 固定名字可覆盖，latest 先移到 previous 再创建新文件，异常时 latest 可暂缺。只能说 previous 可能仍在，不能说最后恢复点一定全丢失。torch 临时文件未 fsync。混写问题已有 STOP_REVIEW，不重复统计。

G126 有身份、序号、不可变 commit，但尾部只信 metadata；JSONL 已 fsync 而 metadata 未提交的中断可使后续重复序号。所有 checkpoint label（含 failure_raw/snapshot）都推进正式 checkpoint 标记并清尾部，即使 latest 没更新；E 失败文件名还错误取 H 的 attempt。重复序号和非正式文件推进提交标记已见 v4 旧审查。完整 commit 写好而 metadata 失败后，重试还可能撞同名不可变文件；本轮未注入故障。

G43 的内容已与当前记录器相同，只有布局/路径差异，故 F06 双指针问题确实属于它；G30/G126 根本没有 A/B 方法，不能被标成“同一 A/B bug”。这些问题影响追溯、恢复和持久性，不是正常空气腔体差分计算错误的证据。

### HC12 [P2，身份版本影响] 协议哈希曾充当 run_id；相同版本字符串横跨全部八代 solver

位置：[G112 原文件:128](C:/PI-DON/evidence/gpt6_plan_v3/h_layout_candidate/source_snapshot/pidon_solve.py:128) 至 135、1070-1079；[G144 原文件:128](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_solve.py:128) 至 135、1055-1064。

两组把 run_id 和 protocol_hash 都设成同一个确定性摘要，独立执行但配置/源码/初始资产相同会得到相同 run_id；恢复目录与 checkpoint 的比较因此不能区分这些独立执行。G135 起改用 UUID 加独立协议摘要。这主要改变证据身份；不能因 UUID 改造就说物理结果应改变，也不能据相同旧 run_id 把重复执行合成一次成本。

八组 solver 的 SCRIPT_VERSION 都仍为 `2026-09-13b`，从 G109 原文 65 行到 G23 原文 69 行、G62 原文 77 行，中间已跨越上述数值/恢复变化。这是 HA08“版本字符串不能认证可复现性”的具体历史扩展，不另算新缺陷。G23 及更早直接加载原 init 路径，G62 已有加载侧 resolve_legacy，但恢复比较仍是原字符串；只有当前再新增恢复比较侧 resolve_legacy。因此 F07 必须分调用点判断，不能按所有同版本文件一概回溯。

### HC13 [P3，解释边界] dco/fdtd 的强断言修正主要是文案，不是数值改进

位置：[G124 原文件:182](C:/PI-DON/evidence/grid_diagnosis_v1/source/dco.py:182) 至 187、249-268；[G40 原文件:69](C:/PI-DON/evidence/coverage_ab_v1/source/fdtd.py:69) 至 81。

G124 曾把 RMS 不随网格漂移、cellsize 编码使预测严格网格不变写成保证；对应归一化/坐标实现与当前相同。这些注释忽略采样窗口、卷积/池化和边界上下文，不能作为跨网格精度证据。G40 把 31 间隔解释说成已确认论文网格，当前改成与 dt 一致的重建假设。两项均不授权声称作者已确认。

本轮完整 diff 只见这些 docstring 与布局变化，没有公式修正，因此旧数组不会因注释改动而变化；新注释也不是重测证据。G107 的 25 份 dco、G152 的 paper_protocol、G47 的 head_lstsq 均只差布局引导，不另列数值缺陷。

## 当前发现的回溯边界

| 主审项/变化 | 可以覆盖的历史范围 | 不能直接回溯的范围 |
|---|---|---|
| F01 材料、F12 CFL | 三组 fdtd 的相应执行公式都未改；G32 原文 83-89、122 已显示材料忽略 | 空气 eps_r=1 的正常结果不因材料接口缺陷撤销 |
| F05 abs 停止 | G135/G142/G23/G62 已使用物理 R | G109/G71/G112/G144 非零目标按 objective，见 HC06 |
| F06 A/B 双指针 | G43 原文 185、198-199 已有先指针后 metadata | G30/G126 没有 A/B；它们的窗口见 HC11 |
| F07 路径迁移 | G62 加载权重已 resolve_legacy（原文250）；当前恢复比较又扩大范围 | G23 及更早的 init 加载和恢复比较均未调用该 resolver |
| F08 Eq.(5) physical 零分支 | G79 与当前同测量代码 | G114/G97/G137 没这个字段；并不因此补出合格 MRE |
| F18 resume 裸 Path | G135:1140、G142:1221、G23:1230、G62:1238 均有同一未导入名字 | G109/G71/G112/G144 的 resume 没有该 metadata Path 分支；它们仍有各自恢复缺口 |
| F24 Adam 回调后仍入 LBFGS | G112/G144 及之后已有同样回调/切换结构 | G109/G71 未提供这些回调；时间预算后的 LBFGS 是另一个旧控制边界 |
| 空参考显示异常 | G109:770、G71:918、G112:1106、G144:1091、G135:1182、G142:1263 的每步输出都直接格式化 nMAE | G23/G62 的每步展示已加 None 保护；主审指出的最终打印仍是另一路径 |
| head 接入 | G142/G23/G62 的源代码已含 head 路径；当前相同 | G109/G71/G112/G144/G135 没有该路径；不能以当前 head 行为解释早期 Adam 成绩 |
| 服务器 random128 | G62 与当前唯一 diff 是恢复 init 比较（157-166） | 不据此改变从零训练的更新公式、成本或 Ex/Ey FAIL；本轮未重新认证其数值 |

上表行号均为各组**历史代表原文件**行号，完整路径见逐组表及 JSON。未把 None 打印问题、材料、CFL 或依赖哈希遗漏重复计入 HC 新发现。

## 逐 Group 真实覆盖

所有下列 diff 均从第 1 行读到最后一行，阅读模式为 `FULL_DELTA_REVIEW`，不是 AST/文件名推断。原文件列链接用于解释表中的历史行号。132 份成员清单、字节哈希及逐项匹配结果完整保存在覆盖 JSON；每组原文内容身份均与索引匹配。

| Group | 历史代表原文件 | 成员 / diff 行 | 已读差异与影响 | 未测边界 |
|---|---|---:|---|---|
| G23 | [evidence/workspace_reorganization_20260914/before/root/pidon_solve.py](C:/PI-DON/evidence/workspace_reorganization_20260914/before/root/pidon_solve.py:149) | 1 / 64 | 仅布局引导、init 路径解析及恢复比较迁移；数值核与 head 规则无差异。F07 新的恢复路径别名比较不能回溯到本组；F18 裸 Path 原已存在。 | 未执行迁移路径或恢复；不声称外部同名权重曾被替换。 |
| G30 | [evidence/gpt6_plan_v2/r0_source_snapshot/pidon_recording.py](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_recording.py:72) | 2 / 267 | 完整比较旧 101 行记录器；缺独立身份、序号与尾部扫描；latest 先移走、failure_raw 固定覆盖。无 A/B 接口，F06 不能套用。 | 未注入断电/中断，未检查某次历史目录是否混写。 |
| G32 | [evidence/gpt6_plan_v2/r0_source_snapshot/fdtd.py](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/fdtd.py:110) | 1 / 53 | 仅缺 step_e_source_h 与布局引导；原 step 为 H→E→source。与 G109 调用一起构成 H 时间层未对齐；curl 差分本身未改。 | 未重算参考轨迹；独立使用原 step 不构成错误。 |
| G40 | [evidence/coverage_ab_v1/source/fdtd.py](C:/PI-DON/evidence/coverage_ab_v1/source/fdtd.py:69) | 5 / 79 | 缺 E→source→H 便利接口；另有 31 间隔已获论文确认式的过强注释，当前改为假设。数值 cfl 公式不变。 | 未核验本组各实验的外部调用顺序，不能仅凭接口缺失判其场结果错误。 |
| G43 | [evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_recording.py](C:/PI-DON/evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_recording.py:175) | 13 / 40 | 仅布局/sha256_file 路径解析变化；A/B、JSONL 尾部协调及 checkpoint 数值逻辑与当前一致。F06 已存在。 | 未做恢复或故障注入；五文件哈希清单仍非全执行依赖。 |
| G47 | [evidence/workspace_reorganization_20260914/before/root/head_lstsq.py](C:/PI-DON/evidence/workspace_reorganization_20260914/before/root/head_lstsq.py:1) | 1 / 17 | 仅新增布局引导的反向差异；head 最小二乘与 Adam 状态清理无差异。 | 未运行 SVD、写回或数值稳定性测试。 |
| G62 | [evidence/server_resource_v1/dco_value_review_20260916/returned/random_low_lr128/source/src/pidon/pidon_solve.py](C:/PI-DON/evidence/server_resource_v1/dco_value_review_20260916/returned/random_low_lr128/source/src/pidon/pidon_solve.py:157) | 2 / 25 | 唯一差异为 assert_resume_compatible 的 init 原字符串比较；加载时已有 resolve_legacy。从零的训练及测量公式不因该差异变化。 | 未复算 random128；只排除这一差异改变从零演化，F07 加载侧仍适用。 |
| G71 | [evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_solve.py:315) | 1 / 967 | 完整审查 967 行差异：旧停止目标、局部 LBFGS 回滚/预算、dtype、缺冻结字段及旧 recorder 调用；有低高 PEC 投影，不能套 G109 的边界缺口。 | 未推理、未复现旧 optimizer；该版本未实现 Adam/LBFGS 中断回调，不套 F24 的同一路径。 |
| G79 | [evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_contract.py](C:/PI-DON/evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_contract.py:132) | 13 / 19 | 仅布局引导；普通/体积 nMAE 已分列，mre_eq5_physical 已加入，F08 因而适用。 | 未重算数组；与 G137 的旧体积 nMAE 不能无条件混列。 |
| G97 | [evidence/gpt6_plan_v3_review/source_snapshot/pidon_contract.py](C:/PI-DON/evidence/gpt6_plan_v3_review/source_snapshot/pidon_contract.py:149) | 1 / 104 | 去源 mask 仅影响误差分子与部分分母，reference_max 仍含源；缺新增 MRE/weak/support 字段。 | 未检查每个历史时刻源点是否为最大值；不把缺字段补成当前口径。 |
| G107 | [evidence/coverage_ab_v1/source/dco.py](C:/PI-DON/evidence/coverage_ab_v1/source/dco.py:37) | 25 / 19 | 25 份成员仅差布局引导；网络、归一化、坐标计算无数值差异。 | 源码相同不证明训练数据、head 元数据或权重相同；未载入模型。 |
| G109 | [evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_solve.py:418) | 1 / 1151 | 完整审查 1151 行差异：低侧 H 法向面、原始快照别名、无累计恢复合同、零靶/默认非严格门、LBFGS 计数与中断、参考时层与未去源指标。 | 不知各旧调用实际启用开关；不能由保存源码推定所有训练走此 main；无科学重算。 |
| G112 | [evidence/gpt6_plan_v3/h_layout_candidate/source_snapshot/pidon_solve.py](C:/PI-DON/evidence/gpt6_plan_v3/h_layout_candidate/source_snapshot/pidon_solve.py:283) | 3 / 469 | 完整审查 469 行差异：抽取 H core 为同义实现；终态可重入、run_id=协议哈希、旧分量停止门、无 head 接入；失败场摘要已置空。 | 已保存耗费不等于可续训；未重放候选，不改局部 FAIL。 |
| G113 | [evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/fdtd.py](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/fdtd.py:138) | 21 / 19 | 仅布局引导；E→source→H 与传统 step 两接口均已存在，curl/材料/CFL 行为同当前。 | F01/F12 是已有家族，不重计；未证明各历史调用用了哪个接口。 |
| G114 | [evidence/gpt6_plan_v2/r0_source_snapshot/pidon_contract.py](C:/PI-DON/evidence/gpt6_plan_v2/r0_source_snapshot/pidon_contract.py:126) | 1 / 161 | 缺 curl 固定尺度、残差规则字段、去源 mask/A_fixed、弱场及 MRE；旧 nMAE 为全支撑普通均值。 | 未按当前规则重判旧数值，缺失量仍需原始数组。 |
| G124 | [evidence/grid_diagnosis_v1/source/dco.py](C:/PI-DON/evidence/grid_diagnosis_v1/source/dco.py:182) | 2 / 78 | 除布局外仅 docstring 不同；RMS/绝对坐标/cellsize 的强泛化说法被修正，执行公式没变。 | 没有因此新增网络精度改善，也不能据旧注释确认作者实现。 |
| G126 | [evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_recording.py](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_recording.py:124) | 8 / 194 | 完整比较及全文原文：无 A/B；尾部只信 metadata；任意 checkpoint label 都前移正式标记；E failure 名字取 H attempt；torch 文件无 fsync。 | 不套 F06 双指针问题；故障窗口未在本轮执行；已知旧问题不重复计数。 |
| G135 | [evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_solve.py](C:/PI-DON/evidence/gpt6_plan_v4_night/control_runs/float64_exact/source_snapshot/pidon_solve.py:425) | 6 / 275 | 完整审查 275 行差异：未接 head；物理 R/终态保护/UUID 已有；缺可空值展示保护；直接旧路径。 | 纯精确控制不等于 DCO head 训练；旧 main 的零参考打印与 F18 问题不证明控制 runner 未执行。 |
| G137 | [evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_contract.py](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_contract.py:153) | 8 / 85 | 旧 nMAE 和 weak_absolute_pass 使用 dual-volume MAE；无 Eq.(5) strict-zero 合成字段。 | F08 字段不存在，不能回溯套用；未重算普通均值与体积均值的差值。 |
| G142 | [evidence/gpt6_plan_v4_night/g0_after_head_integration/control_runs/float32_exact/source_snapshot/pidon_solve.py](C:/PI-DON/evidence/gpt6_plan_v4_night/g0_after_head_integration/control_runs/float32_exact/source_snapshot/pidon_solve.py:149) | 6 / 108 | 完整审查 108 行差异：head 已接入，数值训练相同；旧路径与 None 展示保护差异；F18 已存在。 | head 接入不等于各臂启用 head；未运行求解/保存，不能量化旧零参考异常次数。 |
| G144 | [evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_solve.py](C:/PI-DON/evidence/gpt6_plan_v3/A2_control_runs/float32_exact/source_snapshot/pidon_solve.py:407) | 5 / 558 | 完整审查 558 行差异：与 G112 同代预算/身份；H core 尚内联；失败半事务仍出场指标；无 head。 | 这些快照也用于 exact/negative 子类，未把继承后绕开的训练分支缺陷说成控制实测失败。 |
| G152 | [evidence/coverage_ab_v1/source/paper_protocol.py](C:/PI-DON/evidence/coverage_ab_v1/source/paper_protocol.py:1) | 6 / 19 | 仅布局引导；paper_protocol 的物理输入/精确零分支指标公式未变。 | 不能与 pidon_contract 的归一化 Eq.(5) 字段混同；未运行指标。 |

## 尚未执行的验证

本轮未执行任何被审模块、训练、测试、参考推进、模型推理、checkpoint 反序列化、数组数值复算、恢复故障注入或 GPU profile；均为 NOT_RUN。本报告不认证任一历史 PASS，不修改任一 FAIL，也不决定修复范围。

源文件身份与差异覆盖已经完成；“特定历史执行是否走过缺陷分支、误差具体多大、旧已保存故障现场是否受影响”仍需绑定该执行的命令/冻结配置、实际入口及原始产物。尤其 exact-control 可能覆盖训练方法，固定状态脚本可能绕过 Solver.main，不能从同目录源码快照推断必然执行过每条路径。缺原始数据时结论为 INCOMPLETE，不能从当前 canonical 倒算或补造旧证据。

向主审建议的整合重点是 HC01-HC04 和 HC05 的 G109 部分，以及 F05/F06/F07/F08/F18/F24 的版本适用矩阵；其它 HC 是已知问题的历史身份与范围补证，不应机械累加为新问题总数。

