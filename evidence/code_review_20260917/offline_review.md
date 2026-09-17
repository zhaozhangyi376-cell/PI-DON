# 离线训练与诊断入口只读审查

日期：2026-09-17。范围：用户指定的九个 `scripts/experiments` 文件、`_01/train_phase1.py` 及 `_01/tests` 下全部四个源文件，共 14 个源文件、2173 行，均逐行读完。本报告是这个范围的审查，不是全项目审查完成声明。

本轮只新增本文件。未修复代码、未运行训练/科学实验/推理/单元测试、未写 lab 账本、未修改 PLAN/STATUS/production、未提交、未另派 agent。唯一执行的项目入口是带 `-B` 的只读 `project_harness status` 和 `next`，避免写入 Python 缓存。status 退出 0；next 因已有证据路径缺失退出 1，没有据此改写历史科学状态。

已先读 AGENTS.md、现有 [REVIEW.md](C:/PI-DON/evidence/code_review_20260917/REVIEW.md)、PLAN、STATUS。以下用 O 编号，与已有 F01-F22 分开；重叠事项只作交叉引用。证据等级明确区分：**源码观察**表示控制流/公式直接成立，不表示本轮执行过反例；**历史证据**表示读取了已有数值或日志，未重新加载全部模型和数组复算；**已复现**仅用于本轮实际运行过的反例，本报告没有此类条目。历史复算不改标成本轮已复现。

## 主要判断

最需要优先处理的是仍属活动入口的 `train_dco.py`：输出文件名可以导致权重被 JSON 覆盖，新的输出父目录没有建立，warm-start 没有核对输出 head 的语义，训练数据的方向分布也没有进入 checkpoint。前两项威胁训练产物，后两项影响模型身份和评估解释。

历史 EXP3 确有提前发散后仍按完整步数报告成本的记录。旧 pilot 的指标聚合错误已有独立历史复算支持。两者都不改变既有失败状态，也不应外推为后来正式 128 步轨迹没有执行。`coverage_ab.py`、`diagnose_grid.py`、`spacing_probe.py` 的主要数值路径未发现新的确定性公式错误；其历史主入口存在迁移后的路径问题，实验结论仍受各自诊断范围约束。

`_01` 四个测试文件共八项测试，主要覆盖常规形状、单个解析方向和两更新预检。未发现这些测试断言本身的独立计算错误，但它们不足以证明完整数值合同、梯度累积等价、训练成本或科学门通过。

## 可确认的问题

### O01 [P1，源码观察] warm-start 会把 potential head 权重静默当作 direct head

位置：[train_dco.py:127](C:/PI-DON/scripts/experiments/train_dco.py:127)、[train_dco.py:130](C:/PI-DON/scripts/experiments/train_dco.py:130)、[train_dco.py:168](C:/PI-DON/scripts/experiments/train_dco.py:168)。依赖：[dco.py:119](C:/PI-DON/src/pidon/dco.py:119)、[dco.py:162](C:/PI-DON/src/pidon/dco.py:162)。

- 触发：`--init` 指向同 levels/base/coords/norm、但 `head='potential'` 的 checkpoint。
- 原因：新网络始终使用默认 direct head；兼容检查只检查四个字段。两种 head 的参数键和形状相同，差别是普通属性 `head_mode` 决定是否在 forward 最后施加 curl，所以 `load_state_dict` 不会报错。原先表示向量势的网络输出随即被解释为 curl，保存时又标成 `head='direct'`。
- 影响：这不是无缝继续原模型。旧 direct/analytic 主模型不因这一条件问题失效；本轮未发现历史日志证明主训练曾以 potential checkpoint 经此入口继续，历史触发情况为 INCOMPLETE。也不能把该问题套到能显式读取 head 的 `test_dco.load_net`。
- 建议：在第一次更新前拒绝不兼容 head，或显式登记为改变输出定义的新实验。测试用相同 state_dict、不同 head 元数据的极小模型，断言拒绝发生在 optimizer.step 前；不需要真实训练。

### O02 [P1，源码观察] 非 `.pt` 输出名可使历史 JSON 覆盖刚保存的权重

位置：[train_dco.py:202](C:/PI-DON/scripts/experiments/train_dco.py:202)、[train_dco.py:203](C:/PI-DON/scripts/experiments/train_dco.py:203)。

- 触发：父目录已存在，`--out evidence/new_case/model.bin`、`model` 或 `model.PT` 等路径中没有小写 `.pt`。CLI 未限制后缀，统一入口也未限制。
- 原因：`a.out.replace('.pt', '_hist.json')` 此时等于权重路径本身。代码先 `torch.save`，再以 `open(..., 'w')` 将同一文件截断并写入 JSON，最后仍打印 saved。若 `.pt` 出现在父目录名内，replace 还会错误改变目录。
- 影响：触发时会丢失本次最终权重，并覆盖该路径上先前的周期 checkpoint。正常小写 `.pt` 文件名不触发；未找到历史 `.bin`/大写后缀训练记录，不能声称现存主模型已被损坏。
- 建议：以 Path 的文件名/后缀操作构造独立历史路径，并验证两个绝对输出路径不同。测试覆盖无后缀、`.bin`、`.PT`、父目录含 `.pt`；用伪保存器或极小序列化夹具，无需训练。

### O03 [P2，源码观察] 新实验父目录不存在时，到第一次 checkpoint 才失败

位置：[train_dco.py:164](C:/PI-DON/scripts/experiments/train_dco.py:164)、[train_dco.py:199](C:/PI-DON/scripts/experiments/train_dco.py:199)。入口：[run.py:74](C:/PI-DON/run.py:74)。

- 触发：合法的新输出如 `evidence/new_case/model.pt`，而 `new_case` 尚不存在。
- 原因：统一入口只校验位置和文件是否已存在；训练器也不创建父目录或预检可写性。第一次 `torch.save` 才碰到不存在的父目录，默认可在 25 个 epoch 之后。
- 影响：已花计算成本但没有本次 checkpoint。旧输出在项目根目录、或预先建好目录的运行不受影响。现有 [test_run_entrypoint.py:30](C:/PI-DON/tests/test_run_entrypoint.py:30) mock 了整个实际运行，只证明参数没有被改写，不能覆盖本错误。
- 建议：第一次更新前准备和校验新输出目录。测试以临时新目录和伪训练回调检查顺序，不消耗科学训练预算。

### O04 [P2，源码观察] 训练方向分布丢失，自动评估会静默退回 shared

位置：[train_dco.py:41](C:/PI-DON/scripts/experiments/train_dco.py:41)、[train_dco.py:158](C:/PI-DON/scripts/experiments/train_dco.py:158)、[train_dco.py:165](C:/PI-DON/scripts/experiments/train_dco.py:165)；下游 [test_dco.py:386](C:/PI-DON/scripts/experiments/test_dco.py:386)。

- 触发：数据来自 `gen_data --dirs per-wave`，经本训练器生成 checkpoint，再由 `test_dco --dirs auto` 评估。
- 原因：生成器把 dirs 保存于 NPZ（[gen_data.py:199](C:/PI-DON/src/pidon/gen_data.py:199)）；load 只读 E/C/D/n，hist 和 checkpoint 都不保存 dirs。评估时缺字段自动取 shared，等于悄悄更换数据分布。
- 影响：per-wave 模型的“同分布测试”可能实为迁移测试。已读 paper_first_v1 摘要中两主模型的 dirs 为 null，说明摘要不能独立证明方向分布，但不能据此断言它们训练于 per-wave。共享方向旧主模型的数值不因本问题自动作废。
- 建议：保存并核对数据合同、dirs 和数据哈希；缺元数据应明确 UNKNOWN 或要求显式声明。测试只需带 `dirs='per-wave'` 的小型 NPZ/伪 checkpoint，验证训练配置到自动评估的元数据传递。

### O05 [P2，源码观察 + 历史证据] EXP3 发散尾部被剔除，完成步数和每步成本仍按请求长度报告

位置：[test_dco.py:322](C:/PI-DON/scripts/experiments/test_dco.py:322)、[test_dco.py:328](C:/PI-DON/scripts/experiments/test_dco.py:328)、[test_dco.py:335](C:/PI-DON/scripts/experiments/test_dco.py:335)。

- 触发：探针出现非有限值或超过 blow-up 门限，提前 break。
- 原因：`rec_dut[t:] = nan` 包括触发失败的这一点，后面又过滤所有非有限误差；只剩失败前前缀。`rec_ref` 同时停止，未计算尾部保持初始化零值，因此分母也不是完整窗口参考峰值。打印步数和毫秒/步却始终使用请求的 `steps`。仅检查单个 Ez 探针也不能证明其余五分量或源外全域仍有限。
- 历史证据：只读 [lab_runs.jsonl](C:/PI-DON/records/lab_runs.jsonl) 的 id=1/2/3/7。分别在替换步索引 147/158/86/158 报 blew up，却全部打印 `400 DCO-driven steps`。因此尝试更新数至多对应 148/159/87/159 次，不能当作 400 步完成。这里没有重新计算这些运行的总成本。
- 影响：旧 EXP3 全长成功率、波形误差与每步耗时不能使用这些打印值直接认证。原发散结论保留；有限前缀统计可以作为带明确截止点的诊断。当前正式在线训练未调用这段循环，不能用此项否定正式 128 步执行记录。
- 建议：分列请求、尝试、成功完成和失败步；保持时间索引与失效掩码，失败不得被过滤成“never exceeds”；全长参考与前缀误差分开。测试用可控制的假预测器在第 k 步返回 NaN/爆幅，核对步数、成本分母、失败状态及保存数组。

### O06 [P2，源码观察] Yee 目标模型的保存真值与保存分数不是同一目标

位置：[test_dco.py:90](C:/PI-DON/scripts/experiments/test_dco.py:90)、[test_dco.py:153](C:/PI-DON/scripts/experiments/test_dco.py:153)。下游：[make_figs.py:159](C:/PI-DON/scripts/figures/make_figs.py:159)、[make_figs.py:184](C:/PI-DON/scripts/figures/make_figs.py:184)。

- 触发：checkpoint 的 `target='yee'`。
- 原因：score 返回裁剪后的 Yee relL2/nMAE，exp1 却无条件把解析 C 保存为 `exp1_true`，把 Yee 分数保存为 `exp1_relL2`。后续 fig3 展示预测减解析真值的图，却在标题中使用 Yee 分数。
- 影响：图像和标题不属于同一个误差定义，不能据标题解释图中差值。id=1 的旧记录确为 yee 目标，相关入口条件历史上存在；本轮未重新打开该次 NPZ 或确认当次图文件，具体旧图身份为 INCOMPLETE。analytic 主模型没有这一错配。
- 建议：分别保存 analytic/yee 真值、共同支撑、各自分数和样本编号；绘图从选定真值重新核对标题。测试以解析与离散 curl 明显不同的玩具数组检查保存数据和标题一致性。

### O07 [P2，源码观察 + 历史证据] 仍打印“共同归一化使 MRE 变成 nMAE”等不成立结论

位置：[test_dco.py:194](C:/PI-DON/scripts/experiments/test_dco.py:194)、[test_dco.py:201](C:/PI-DON/scripts/experiments/test_dco.py:201)、[gap_analysis.py:165](C:/PI-DON/scripts/experiments/gap_analysis.py:165)。

- 触发：任何执行到这些打印段的运行，与本次实测数值无关。
- 原因：代码固定声称归一化后分母变成 local max，并推导可用 nMAE 对照论文成绩。对非零真值 t 和共同尺度 s，`abs(p/s-t/s)/abs(t/s) = abs(p-t)/abs(t)`，分母不会换成最大值。另一个固定断言“ANY model 都不能达到很小的 MRE”也有直接反例：p=t 时包括严格零分支在内误差全为零。
- 影响：错误在报告推理，不是当前 `D.mre_eq5` 的非零分支公式。id=1 的历史 stdout 确实有 nMAE 就是论文指标的表述；后来 [PAPER_FIRST_REVIEW.md:64](C:/PI-DON/docs/paper/PAPER_FIRST_REVIEW.md:64) 已撤回跨指标倍数，但源文件仍保留旧输出，重启会再次产生误导。不能以注释、固定打印值或“数值接近”推定作者实际实现。
- 建议：删除这些固定结论，分列指标定义、单位、支撑和实际测量；论文实现未确认处保留假设。测试用 p=t、不同公共尺度以及含零参考样本验证数学不变量；报告测试不得允许无条件声称论文复现。

### O08 [P2，源码观察 + 历史证据] 四样本 pilot 的宏 nMAE 实际跨样本共用最大值

位置：[phase1_pilot.py:33](C:/PI-DON/scripts/experiments/phase1_pilot.py:33)、[phase1_pilot.py:78](C:/PI-DON/scripts/experiments/phase1_pilot.py:78)、[phase1_pilot.py:99](C:/PI-DON/scripts/experiments/phase1_pilot.py:99)。

- 触发：indices 多于一个，样本峰值不同。
- 原因：每个分量把整个 batch 交给 `D.nmae`，该函数取所给张量的全局最大值。结果是 `mean_s(MAE_s)/max_s(peak_s)`，不是 `mean_s(MAE_s/peak_s)`。对于相同大小、非零峰值的样本，前者不大于后者，因此可能让门槛偏松。
- 历史证据：[R3_recompute.json:134](C:/PI-DON/evidence/gpt6_plan_v2/R3_recompute.json:134) 保存旧值 0.005852074478752911、逐样本逐分量值 0.020065677674559388；已读其复算源码 `scripts/analysis/r3_v2_recompute.py`，未在本轮重跑。两个值都高于 1e-3，旧 FAIL 不变。这里不是新发现历史记录，而是确认当前封存入口仍带此错误。
- 影响：不能把旧值当作逐样本宏指标，也不能据旧值判断距门槛只差多少。当前 `phase1_ab_pilot.per_component_macro` 已逐样本计算，不受这一特定问题影响；不能把这项批量套给所有第一阶段训练。
- 建议：先每样本每分量计算，再明确宏平均；零峰值另列绝对误差和分母。测试使用两个幅值差很大的样本，使旧聚合过门而正确聚合不过门，并覆盖样本复制/排序不改变结果。

### O09 [P2，源码观察] gap_analysis 忽略 checkpoint 的 target 和 dirs，却给出统一训练失败解释

位置：[gap_analysis.py:137](C:/PI-DON/scripts/experiments/gap_analysis.py:137)、[gap_analysis.py:142](C:/PI-DON/scripts/experiments/gap_analysis.py:142)、[gap_analysis.py:239](C:/PI-DON/scripts/experiments/gap_analysis.py:239)。

- 触发：传入 `target='yee'` 或 `dirs='per-wave'` 的 checkpoint。
- 原因：加载 head，但只取 coords/norm/grid 作为测试合同；数据生成无条件 shared，所有主分数都对解析 C。随后固定打印“网络自己的训练 target 是解析 curl”及其导致发散的推论。
- 影响：可以把有意拟合的 Yee/解析差异算成拟合误差，或把分布迁移算成同分布精度。即使默认 analytic/shared 模型，静态散度诊断也不足以证明闭环不稳定的最可能因果机制。未找到本轮账本中此脚本的直接执行条目；旧运行是否使用非默认模型未证实。
- 建议：从 checkpoint 明确识别目标/分布，报告两种目标时采用相同支撑，自动解释限于实际证据。测试以 metadata 为 yee/per-wave 的伪模型验证生成器参数和报告标签，不需要训练。

### O10 [P2，源码观察，仅历史入口] gap_analysis 将输入路径直接拼成输出文件名

位置：[gap_analysis.py:272](C:/PI-DON/scripts/experiments/gap_analysis.py:272)。

- 触发：`--ckpt assets/models/dco_L3d.pt` 或 Windows 绝对路径。
- 原因：结果变为 `gap_assets/models/dco_L3d.json` 或含嵌入盘符的 `gap_C:/...json`；未创建中间目录，绝对路径形式在 Windows 也不是合法的预期文件路径。问题在推理全部完成之后才出现。
- 影响：当前目录迁移使带目录 checkpoint 成为正常使用方式；该入口若被另行适配重启会保存失败。历史根目录 basename 调用不受影响，且此入口现已被 registry 封存，统一入口不会触发该路径。
- 建议：使用独立 `--out` 和 `Path(ckpt).stem`，先检查输出路径。用相对/绝对路径字符串与临时目录作零推理测试。

### O11 [P2，源码观察，仅历史入口] 多个已迁移脚本仍使用旧根目录文件名进行实际 I/O

位置：[paper_recheck.py:89](C:/PI-DON/scripts/experiments/paper_recheck.py:89)、[paper_recheck.py:143](C:/PI-DON/scripts/experiments/paper_recheck.py:143)；[coverage_ab.py:170](C:/PI-DON/scripts/experiments/coverage_ab.py:170)；[diagnose_grid.py:104](C:/PI-DON/scripts/experiments/diagnose_grid.py:104)、[diagnose_grid.py:134](C:/PI-DON/scripts/experiments/diagnose_grid.py:134)、[diagnose_grid.py:150](C:/PI-DON/scripts/experiments/diagnose_grid.py:150)；[spacing_probe.py:99](C:/PI-DON/scripts/experiments/spacing_probe.py:99)、[spacing_probe.py:141](C:/PI-DON/scripts/experiments/spacing_probe.py:141)；[phase1_pilot.py:59](C:/PI-DON/scripts/experiments/phase1_pilot.py:59)；[phase1_ab_pilot.py:65](C:/PI-DON/scripts/experiments/phase1_ab_pilot.py:65)。

- 触发：绕过封存限制从当前 C:/PI-DON 直接运行这些旧 main，或未来只移除封存而未完成适配。
- 原因：`configure()` 只改变导入路径，不全局重定向 `shutil.copy2`、`sha256`、`torch.load`、`np.load`、`Path.exists`。旧顶层源码/权重/数据现分布在 scripts/src/assets，源码副本复制会失败；部分可选数据分支则静默跳过已有资产。
- 影响：这是迁移后的历史入口可执行性问题，不是对迁移前 id=13/18/23/27 等成功运行的反证。它与 F07 的“外部同名模型误映射”根因不同。`test_dco.py` 本身也已封存，且没有与统一入口要求对应的 `--out`，不应只取消 registry 项后重启。
- 建议：保留封存；需要复用时新建输出入口，显式定位每个源码和输入，验证身份后才运行。测试在新目录布局上只解析路径和检查计划读取文件，绝不执行训练或覆盖历史目录。

### O12 [P2，源码观察，历史默认未触发] paper_recheck 对同 basename checkpoint 会覆盖保存预测

位置：[paper_recheck.py:142](C:/PI-DON/scripts/experiments/paper_recheck.py:142)、[paper_recheck.py:148](C:/PI-DON/scripts/experiments/paper_recheck.py:148)、[paper_recheck.py:164](C:/PI-DON/scripts/experiments/paper_recheck.py:164)。

- 触发：`--ckpts` 含两个不同目录里的同名文件，如 `armA/best.pt`、`armB/best.pt`；假设其余迁移路径问题已在新入口中解决。
- 原因：模型身份只取 `Path(...).stem`。两个模型的 arrays 键完全相同，后加载的预测覆盖前者；summary 却保留两组相同 model 标签的行，前一组分数再也不能由保存的对应数组复算。
- 影响：默认两个旧模型 basename 不同，已读 paper_first_v1 摘要也分别为 dco_paper32/dco_lr1e3_300，不触发。不能因此否定其 24 行结果。
- 建议：使用显式唯一模型 ID 或路径加内容哈希标识；第一次推理前拒绝标签碰撞。用两个相同 stem 的伪模型和不同常量预测检查序列化键及行的对应关系。

### O13 [P3，源码观察] _01 CLI 接受零/负数控制参数，不能在更新前拒绝错误配置

位置：[_01/train_phase1.py:20](C:/PI-DON/_01/train_phase1.py:20)、[_01/train_phase1.py:30](C:/PI-DON/_01/train_phase1.py:30)；依赖：[runner.py:90](C:/PI-DON/_01/src/paper01/runner.py:90)、[runner.py:193](C:/PI-DON/_01/src/paper01/runner.py:193)、[runner.py:213](C:/PI-DON/_01/src/paper01/runner.py:213)。

- 触发：train 模式传入 `--microbatch 0`、负 microbatch、`--validation-every 0` 或 `--progress-every 0`。
- 原因：argparse 只检查 int，没有正数约束。microbatch=0 进入 range 才报错；负值使累积循环为空。interval=0 则在第 1 次更新因短路未报错，通常第 2 次真实更新之后才触发除零，留下部分输出和已消耗预算。
- 影响：默认 8/250/25 不触发，不解释 PAPER01-S1 科学失败。preflight 还会忽略用户提供的这三个值，固定使用 2/1/1，因此预检通过不能证明用户准备使用的 CLI 数值有效。
- 建议：入口及 RunConfig 都在输出写入/数据生成/optimizer.step 之前验证正数；preflight 明示实际采用的配置。测试仅解析非法参数并 mock 下游，断言无训练调用和无输出目录。

## 协议偏差、假设与建议

### H01 [源码观察 + 历史证据] 已知协议偏差：A/B floor 常数不同，但历史样本没有数值影响

位置：[phase1_ab_pilot.py:75](C:/PI-DON/scripts/experiments/phase1_ab_pilot.py:75)、[phase1_ab_pilot.py:103](C:/PI-DON/scripts/experiments/phase1_ab_pilot.py:103)。训练标签全局峰值被用作 curl_e0。已读原登记 [计划:283](C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-evidence-and-reproduction-plan.md:283) 及后续合同修订 [计划:75](C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-contract-repair-and-gated-continuation.md:75)：登记常数为 E0/L0=20，旧运行实际为 96249.9296875。

已有 [R3_recompute.json:136](C:/PI-DON/evidence/gpt6_plan_v2/R3_recompute.json:136) 记录两个 floor 为 0.0962499296875 与 0.00002，384 个样本分量没有一个低于旧 floor，首四样本的 B 末模型 loss/梯度范数也相同。因此该批训练每个分量的分母都是其自身峰值，floor 差异不能解释 B 的退步。保留这项协议不符，不能凭常数看起来大就宣布数值结果受损。本轮未再加载数组验证这一旧审计。

后续经用户决定修订时应显式固定常数，并用峰值高于两个 floor、夹在两者之间、低于两个 floor 的三组测试。旧 A/B 的共同初始化、共同抽样序列在代码中确有实现，不能套用 F03 的“每臂不同初始化/试卷”结论；这也不把它升级为新生成数据或独立终验。

### H02 [源码观察] 冻结 EXP3 的范围与边界实现不能代表逐步适配及训练后复用

位置：[test_dco.py:256](C:/PI-DON/scripts/experiments/test_dco.py:256)、[test_dco.py:298](C:/PI-DON/scripts/experiments/test_dco.py:298)、[test_dco.py:303](C:/PI-DON/scripts/experiments/test_dco.py:303)、[test_dco.py:310](C:/PI-DON/scripts/experiments/test_dco.py:310)。它先以参考 FDTD 暖启动，然后仅将 curl-E 的三个 core 块换成冻结 DCO；curl-H 仍用精确差分，未覆盖的高侧 H 面保留精确值，低侧对应面则在预测覆盖区内。没有逐时间步问题训练。

这是代码实际定义的混合诊断，不是两旋度完整学习替换。冻结预训练失败不能否定问题训练后的冻结复用。低/高侧边界不同处理应通过六面线性场和 PEC 控制检查；本轮没有证明该不对称单独导致哪次发散，不把它列成已定位的唯一根因。对硬源，当前 ref 的 `step(...,0)` 后再手动赋源在内部源位置与 DUT 对齐；不能一概把“加法源默认值”当作这些调用的 bug。

### H03 [源码观察] 两种换网格问题不能混成同一个维度不变性结论

`test_dco.exp2` 在 [test_dco.py:178](C:/PI-DON/scripts/experiments/test_dco.py:178) 按尺寸改变随机种子，每尺寸仅 4 个新场。它可以描述该分布在不同尺寸的表现，但不能把差异全部归因于尺寸，也不能解释为同一物理波形重采样。`paper_recheck` 对同 seed 复用 wave_spec；`diagnose_grid` 又固定公共 ROI、位置及 fixed32 尺度；这三者的问题不同。建议同题多网格夹具核对方向、振幅、波数、原点和空间范围，保留原四样本数值为其原有口径。

`gap_analysis` 的 shell 重加权只是条件外推；零 padding 并不能证明所有边界点“不可学习”，静态散度非零也不能单独证明动态发散因果。打印的容量/轮数处方和最可能根因超出当前实验能识别的内容。此处属于推断范围限制，不将 Yee 核的符号判为错误。

### H04 [源码观察] train_dco 的历史训练合同仍不等于论文完整训练

每样本全三分量 nMAE（[train_dco.py:73](C:/PI-DON/scripts/experiments/train_dco.py:73)）已经消除了跨样本峰值，但仍共用该样本三分量的全局峰值；不是逐分量宏 nMAE。global relL2、逐样本 nMAE、逐点 MRE 的归约不同。训练采用输入派生尺度、可选相对 loss 和 cosine 调度；这是代码合同，不能因为注释写“paper”就认定与作者实现一致。

`--init` 明确只重载权重，并重置优化器/调度；save 不含 optimizer/RNG/数据内容哈希，也没有 seed 参数。可以作为新 warm-start 实验，不能称精确恢复或把若干段 epoch 自动拼成论文预算。这与 F21 所述另一训练器的恢复夸大相关，本报告不重复给 F21 编号。

全 held-out batch 在 [train_dco.py:187](C:/PI-DON/scripts/experiments/train_dco.py:187) 一次前向，再由 evaluate 分批重复推理；全数据也预先放到设备。它是可见的显存/评估成本风险，是否在 1000×32³、L4、本机 6GB 上 OOM 本轮未测试，不作为确定性崩溃结论。

### H05 [源码观察] 历史输出保护、参数标签及序列化改进

- `phase1_pilot.py:103`、`phase1_ab_pilot.py:114` 使用 exist_ok=True，训练后直接覆盖固定文件；`test_dco.py:344,404-406` 写固定名。当前 registry 封存这些 main，不能绕过它重跑。与 F22 相同的证据保护原则只交叉引用，不重复认定又一次历史覆盖已经发生。
- `coverage_ab.py:229-232` 在 run 因已有目录而失败时，仍可能给那个已有、没有 summary 的目录写 failure.json。建议只有本进程成功新建的目录才可写失败现场；这是封存入口未来适配时的负面测试点，本轮未进行故障写入。
- `phase1_ab_pilot.py:115-116,125` 固定用 A_200/B_200 文件名及“128训练/32开发”文案，CLI 却允许更改预算和样本数。默认 id=110 不受影响；改参数后应从实际配置生成标签，checkpoint 保存 updates/config，避免只靠文件名辨认成本。
- `test_dco.py:399-400` 的源/探针坐标固定：例如 n=8 可被 CLI 接受但索引越界；warm=0 会在空 warm-up trace 的 max 处报错，steps=0 后续也有空归约。建议预检源/探针相对网格的位置及正数窗口，并用 n=8/16/32 的零求解夹具检查。没有把此问题扩写为 F02 的正式场门问题。
- pilot/checkpoint 元数据不足以让任意通用加载器自动识别 levels/base/target；两个 pilot 本身没有承诺通用 checkpoint 格式，因此记录为互操作和追溯建议，不断言训练数值错。

## _01 测试审查

已有 F09/F10/F11 分别涵盖 `_01` 的指标尺度、开发集选模和物理 curl 还原合同。本轮已读 runner/data/model/metrics 对照它们，不重复列项；F03 属于另一个 ablation 入口，不应套到本次所有旧 A/B。

| 文件和行号 | 确实覆盖的行为 | 没有覆盖的关键行为与建议 |
|---|---|---|
| [test_contract.py:10](C:/PI-DON/_01/tests/test_contract.py:10) | JSON schema/claim、字段数量下界、class 枚举、非空 source、若干 ASSUMED 名称 | 非空 source 不等于读过论文；未验证字段唯一性或实际 RunConfig/model/data 与合同数值一致。建议显式字段清单及运行配置比对；不以该测试通过认证论文来源。 |
| [test_data.py:15](C:/PI-DON/_01/tests/test_data.py:15) | 单 seed 横向条件、Ex/Ey 幅值范围、角度拒绝及波数范围 | 未覆盖接近拒绝边界、极小波数、多个种子与不同物理尺度。建议确定性边界规格和横向性相对残差。 |
| [test_data.py:26](C:/PI-DON/_01/tests/test_data.py:26) | x 传播、y 极化的单波；仅非零 curl-z 的一条差分关系 | 没有独立检查 curl-x/y、各交叉项、三方向非等距网格或所有分量符号。建议六个轴/极化组合加一般斜入射线性场。它使用共点样本，与旧 Yee 样本不同是已声明假设，不把测试差分非交错误判成 bug。 |
| [test_data.py:40](C:/PI-DON/_01/tests/test_data.py:40) | 坐标 shape、x 通道有变化、一个 x 步长单位 | y/z 通道、网格原点、轴顺序均未检查。建议非立方、非等距各通道的整轴断言。 |
| [test_model.py:15](C:/PI-DON/_01/tests/test_model.py:15) | L4 在 16³ 常规输入下的输出 shape | 没有检验非立方网格、不可整除尺寸、梯度是否到达两编码器，不能由 shape 正确推出 curl 正确。 |
| [test_model.py:22](C:/PI-DON/_01/tests/test_model.py:22) | 常数正分量的独立最大值与 scale shape | 两个样本使用相同数值，未排除跨样本合并归一化的错误；未覆盖负号、零分量、弱分量、还原往返和 nonfinite。建议两样本不同幅值及一个全零分量。 |
| [test_runner.py:14](C:/PI-DON/_01/tests/test_runner.py:14) | tiny 预检返回两更新、两个学习率值，manifest/contract 文件存在 | `parameter_updates` 直接回显 config.updates，断言不是独立 optimizer 计数；也未读 checkpoint、核对权重变化、finite、history 一致性、microbatch 梯度等价。建议以 optimizer step/已保存参数为独立观察量；有效 batch=4 测 microbatch=1/2/4 及非整除尾批。 |
| [test_runner.py:27](C:/PI-DON/_01/tests/test_runner.py:27) | 非空目录被拒绝 | 未断言旧文件内容未变，未覆盖文件占路径、空目录、保存中断；后者属于恢复/交付可靠性而非科学精度。 |

没有在本轮执行上述测试：`test_runner` 会真实执行玩具 optimizer.step 并写临时输出，不符合本轮纯只读操作范围。原 REVIEW 中“8 项通过”是已有审查的运行证据，本轮不重复声称已经测试通过。梯度累积源码以实际选中样本数和元素数归一化，对默认 800/32 的整批未发现新的权重公式错误；缺少独立等价测试不等于已证明实现不等价。

## 逐文件覆盖

“完整”仅表示该文件全部源代码已读并沿相关调用核对，不意味着所有输入分支已运行。

| 指定文件 | 已读范围 | 结论与边界 |
|---|---:|---|
| [train_dco.py](C:/PI-DON/scripts/experiments/train_dco.py) | 1-213，完整 | O01-O04；H04。当前活动入口。没有做新训练或加载其所有旧 checkpoint。 |
| [test_dco.py](C:/PI-DON/scripts/experiments/test_dco.py) | 1-411，完整 | O05-O07；H02/H03/H05。重点核对三实验、目标裁剪、归一化及闭环成本；封存入口。 |
| [paper_recheck.py](C:/PI-DON/scripts/experiments/paper_recheck.py) | 1-182，完整 | O11/O12。共享 spec、物理预测、逐分量指标链未发现新确定性公式错误。reference 只证明其设定下的 Yee 频率参考，31 intervals 保持假设。 |
| [coverage_ab.py](C:/PI-DON/scripts/experiments/coverage_ab.py) | 1-233，完整 | O11、H05 失败处理。两臂同初始文件、同 specs/batches、fresh Adam、200 更新校验在代码中成立；spacing 干预同时改变输入场和目标是实验设计，不是额外偷偷改变第二因素。 |
| [diagnose_grid.py](C:/PI-DON/scripts/experiments/diagnose_grid.py) | 1-205，完整 | O11；H03。ROI 位置对齐、fixed32 尺度固定、坐标单位与解析 curl 公式逐项读过；环境/context 变化为明确诊断限制。 |
| [phase1_pilot.py](C:/PI-DON/scripts/experiments/phase1_pilot.py) | 1-132，完整 | O08、H05。当前累计更新循环为先 200 后额外 300，不再是旧 #102 那个假 500 计数问题。没有把旧已修复问题报为当前 bug。 |
| [phase1_ab_pilot.py](C:/PI-DON/scripts/experiments/phase1_ab_pilot.py) | 1-140，完整 | H01/H05。物理 loss 的目标尺度只进 loss，没有在推理还原中泄露真值；逐样本分量宏平均正确。 |
| [spacing_probe.py](C:/PI-DON/scripts/experiments/spacing_probe.py) | 1-183，完整 | O11。固定 q、trunk-only 的输入/尺度复用、Yee Fourier symbol 和 core 差分代数一致；wrap 位于评分 ROI 外，未发现 ROI 内混入 wrap 的代码路径。单波探针不是论文样本分布。 |
| [gap_analysis.py](C:/PI-DON/scripts/experiments/gap_analysis.py) | 1-278，完整 | O07/O09/O10；H03。三个 Yee curl 符号和前向散度索引未发现新错误，理论解释及外推范围需收紧。 |
| [_01/train_phase1.py](C:/PI-DON/_01/train_phase1.py) | 1-44，完整 | O13；默认 train/preflight 路由与配置传递未发现其他独立错误。 |
| [_01/tests/test_contract.py](C:/PI-DON/_01/tests/test_contract.py) | 1-30，完整 | 测试覆盖限制见上表；不认证论文来源。 |
| [_01/tests/test_data.py](C:/PI-DON/_01/tests/test_data.py) | 1-48，完整 | 测试覆盖限制见上表；无新增已确认测试计算 bug。 |
| [_01/tests/test_model.py](C:/PI-DON/_01/tests/test_model.py) | 1-34，完整 | 测试覆盖限制见上表；无新增已确认测试计算 bug。 |
| [_01/tests/test_runner.py](C:/PI-DON/_01/tests/test_runner.py) | 1-40，完整 | 自报计数不足以独立验证更新；本轮未运行。 |

## 历史影响与未读边界

- 已读取 `records/lab_runs.jsonl` 中与范围入口有关的结构化记录，重点检查 id=1/2/3/7、13/18/23/27、102/103/110；没有重新执行其中的命令。#102 的 200/500 指标完全相同属于已有旧失败记录，当前源代码已调整累计循环，不将它包装成新问题。
- 已读取两个 learnability.json、ab_pilot.json、R3_recompute.json 及 R3 复算源码。R3 的 0.020066 等值是历史复算值，不是本轮新出数；旧原 FAIL 均保留。
- 读取了 paper_first_v1、grid_diagnosis_v1、spacing_probe_v1、coverage_ab_v1 summary 的模型元数据和行数，分别有 24、192、462、36 行；检查对应 arrays/evaluation 文件存在。**未解压和遍历这些数组，也未重新核对权重/数组哈希与数值**，不能声称独立通过了这些历史实验的全部判据。
- 完整阅读的依赖：`src/pidon/dco.py`、`gen_data.py`、`paper_protocol.py`；`_01/src/paper01/{runner,data,model,metrics}.py`、`_01/paper_contract.json`、`_01/README.md`；`run.py`、`project_paths.py`、script_registry；`tests/test_phase1_pilot.py`、`test_run_entrypoint.py`、`test_coverage_ab.py`；另读 P5/R3 相关报告生成源码以核对历史解释。
- 部分阅读的依赖：`src/pidon/fdtd.py` 的 68-260 行，核对腔体布局、PEC、两种步序、源和频谱，不对该文件未读部分作完整审查声明；`train_pidon.py` 的 36-123 行及相关 Yee helper；`make_figs.py` 的 150-209 行及关键词调用点；`tools/project_harness.py` 的状态/调度相关检索片段。其余主体未逐行读完。
- 文档只读当前入口和有关的 P5 合同段、R3 数值、指标撤回段；没有遍历所有历史计划。未重新阅读论文 PDF 或作者实现，未将任何源码注释、JSON 的 source 字符串或文档作者自述当作论文证据。
- `_01/tests` 除四个源文件外还存在四个 `__pycache__/*.pyc`；这些生成字节码未读取，不属于未覆盖的源代码。未载入全部模型元数据、未运行故障注入、未检查远端服务器当前状态。用户限定的 14 个源文件没有未读部分。
- 工作树开始时已有大量其他改动和证据迁移痕迹。本轮不回滚、不修复、不判定其作者；本报告也不改动机器任务状态。next 的证据缺失与当前科学结论之间的关系，应另由项目主审处理。

## 源码身份

以下为本轮读取时文件内容的 SHA-256，用于后续定位同一审查版本；不是实验模型/数据的认证。

| 文件 | SHA-256 |
|---|---|
| scripts/experiments/train_dco.py | `cee01ff621a393fcc305d2582e2e4d177b2b074ddbcdadc1dcbbaa720bb9c631` |
| scripts/experiments/test_dco.py | `457294adefbddc8a09deb0569cec2723a2307452ea50c32da7e26c0900443992` |
| scripts/experiments/paper_recheck.py | `fb7bffca251481346db6a2d42dea4ebe11197fb4807cb9d4a1e7dc9802dba8af` |
| scripts/experiments/coverage_ab.py | `19dbd577b7bec89c17b715eb53846ba7af2b0e75de1f663e1d0917776fca8e31` |
| scripts/experiments/diagnose_grid.py | `761e5b6df939c995230e26bba3e660142af749dc63906748f211586fbfe7e98c` |
| scripts/experiments/phase1_pilot.py | `0fcc2430ba98dee10b5093dedd5e696c01d3e8487a65fa798c33c727c0fa245a` |
| scripts/experiments/phase1_ab_pilot.py | `637dfbc73ee5c23b4bd13b11de475e49c94f8bd935e007d83384f8f933b92a9a` |
| scripts/experiments/spacing_probe.py | `409ec0b95b6eb428c7c1ccdffe74bab5da62b5a490b224e8363f42a1764cc9f3` |
| scripts/experiments/gap_analysis.py | `65a95b4c378e3e9aa364507747a99ff646144e6014cd3b6eda75c9475c9c6401` |
| _01/train_phase1.py | `46749f143c3f4663077b8c0c31c0041dce53b75b3b27980ea0d1abddc8f7ce0f` |
| _01/tests/test_contract.py | `7843ad747c68f451143027d7497ae70135f368c3c0e2507e33f421355ae00788` |
| _01/tests/test_data.py | `cc7c97eea88f6e2199f7a4e617c71b0ea0674e5d5ff206f9ea30a93d2a577bf5` |
| _01/tests/test_model.py | `a353913cc71266dcef28221152824403347a91211f8a6bdf9ea60e5a2f10898a` |
| _01/tests/test_runner.py | `b9ae13b517de2bdfe7123e88b02afd45b118ef4a8d8d5289f44a906936334b5a` |

后续是否修复、先修哪些入口及是否需要独立复算，由用户决定。本报告不授权重训，不恢复旧失败预算，不用修复建议改判已有结果。
