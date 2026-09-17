# 图表与汇报链路只读审查

日期：2026-09-17。范围：`slides/` 全部 `.py/.js`、`scripts/figures/` 全部 `.py`、`tools/build_briefing_deck.js`，共 **24 个文件、4542 行，逐文件全文静态阅读**。本报告不是全项目审查完成声明，也不是图表重新验收。

目标差距：判断汇报中的精度、成本和复现结论是否被源码与原始证据支持，避免把展示问题误当训练失败，或把局部成功升级成论文复现成功。遵循用户要求，未运行图表生成器、PPT 构建器、训练或模型推理，未派发 agent。唯一新增文件为本报告，未修改生产文件、历史报告、状态或账本。

已读 `AGENTS.md`、`PLAN.md`、`STATUS.md`、本目录 `REVIEW.md`，执行只读 `py -3.11 -B run.py project_harness status` 和 `next`。status 退出 0；next 退出 1，原因是若干已迁移的历史证据路径缺失。这不证明实验未运行，也不阻止本轮源码审查。下文行号对应本次工作树；文末列出全部范围内源码的 SHA256。

## 结论与影响

发现 **3 项 P1、9 项 P2、2 项 P3**。最需要先决定是否纠正的是：旧汇报把 nMAE/相对 L2 与论文 MRE 算倍数；近期汇报把内层残差与论文场误差比较严格程度；旧汇报声称论文未做稳定性分析，与原文 Section IV-B 相反。

已确认一个具体模型身份拼接：近期表格把 `dco_lr1e3_300` 的 32³ 数值放在 `paper32` 列。另有已落盘的 run 编号错配，以及输入缺字段、缺文件、重新生成时可能误导读者的路径。

这些问题**不改写**原始预测、权重和已登记 FAIL。当前 P/R128 场门失败、不支持当前预训练成本收益的结论，不能因为旧图有错而撤销。固定算子摘要中的旧 DCO 宏 nMAE `0.0031189985063326195`、随机 `0.21332000693644848`，以及首个腔体 E 的 relL2 `7.11989107654712`，与近期汇报的相应舍入值一致；本轮没有重做其全量认证。

优先级沿用总审查：P1 为关键科学比较或研究判断；P2 为解释、身份、成本或追溯可靠性；P3 为局部显示与文字错误。以下“建议”均未实施，供用户选择修复范围。

## 发现

### PR01 [P1] 把论文 MRE 当成 nMAE/相对 L2，比出“优于论文”

位置与例子：

- `slides/make_comparison_table.py:39-46`：阶段一标为 nMAE，把本地 `2.875e-3` 除以论文 `4.1e-3`，显示“0.70x 优于论文”。
- `slides/make_p3_p4_figs.py:88-99`、`slides/make_p5_progress_fig.py:38-61`：本地 nMAE 曲线/数轴叠加论文 `5.3e-3`、`7.7e-4` 为精度目标。
- `slides/make_p5_evidence_figs.py:118-148`：把固定 `0.7~1.5` 倍标成“按论文定义算”“量对了”。该函数自己的注释承认数字来自旧 docstring 而非本次复算；`slides/build_progress_deck.js:219-230` 却把包含此图的证据区概称为现场重算。
- `slides/build_progress_deck.js:134-161`：表头称“论文 III-D 口径，指标 MAE/max”，据此写“维度不变性复现成功”。
- `slides/build_deck.js:148-186`：nMAE 行写“对上”，相对 L2 柱图混入论文 MRE `0.41×10^-2`；`slides/build_repro_section.js:230-234,259-262` 仍将 nMAE 与论文 Table I 比为“同一档”。
- `tools/build_briefing_deck.js:392-400` 已分栏写 MRE/nMAE，但 64³/非立方行仍写“旧模型较好/略差”；表内 S1R 对应项只有“数据已回传”，不能支撑这三个优劣判语。

依据：本地论文原文 `docs/paper/paper_text.txt:369-397` 为逐点式(5)，`:399-402` 的归一化说明仍称 MRE，`:429-430` 明确 Table I 使用式(5)，`:465-468` 明确 Fig.6 三值是 MRE。共同缩放不能将逐点分母变成全局最大值。

只读原始数据核对：`archive/legacy_results/arrays/test_results_dco_paper32.npz` 的 `exp2_nmae` 在 64³ 为 `0.002875168342143297`。该值确实存在，错误在于拿它与论文 MRE 做直接优劣判断，不是凭空编了本地数值。

影响：上述论文倍数、“对上”“复现成功”不成立；本地定义内的 nMAE 不因这个问题作废。历史日期和固定快照可以解释数字不更新，不能使错误指标等价关系成立。

建议：新版本分列数据集、模型身份、指标公式、归约和分量，撤销跨指标倍数。历史报告保持原样，以独立更正说明引用。

### PR02 [P1] 将项目残差 R 与论文场 MRE 比较为“更严格”

主位置：`tools/build_briefing_deck.js:324`，原句为“严格R<1e-5…比论文9.6e-3严很多，速度不可横比”。另一处为 `slides/make_stage2_figs.py:30-31`，在“相对平方损失”轴把 `1e-4` 标成“论文停止阈值”，尽管同文件 `:72` 承认当前损失替代了论文绝对平方和。

论文依据：`docs/paper/paper_text.txt:542-543` 写内层训练在 loss<1e-4 时结束；`:585-586` 的 `9.6e-3` 是时域场预测的 MRE。前者是优化停止量，后者是最终场结果，而且项目 R 与论文 loss 的单位/归约等价关系仍未确认。

影响：不能用 `1e-5 / 9.6e-3` 解释本项目为何慢，不能声称已证明“我们比论文严很多”。原 R、Q、分量误差和实际耗时数值不变。

建议：明确三列“项目 R”“论文 Eq.(7) loss”“场 MRE”，在等价关系未确认时不计算门槛严格倍数。

### PR03 [P1] “论文没有稳定性分析”与原文直接冲突

位置：`slides/build_deck.js:267,348`；`slides/build_repro_section.js:320,377`。正文/讲稿称作者没做稳定性分析、没给谱信息，并以此作为本地工作的研究切入点。

依据：`docs/paper/paper_text.txt:683-713` 就是 Section IV-B 稳定性分析与 DMD 方法，`:714-733` 给出完成训练后的评估、较大时间步及 Fig.9 单位圆内特征值。它不等于任意输入和任意时间步的普遍定理，但足以否定“完全没分析”。

影响：误表达作者已有工作与本地工作的新增价值，并容易把“预训练后直接冻结”反例套到“完成问题训练后的评估”。不否定旧冻结反例自身。

建议：对照作者的 DMD 证据范围讨论限制，区分预训练、问题训练和训练后评估。近期脚本 `tools/build_briefing_deck.js:192-198` 的 CFL 页应明确当前求解/训练阶段范围，避免被读成否定论文训练后评估；该页有当前配置说明，因此未单独判为已证实错误。

### PR04 [P2] 同一模型列混入另一 checkpoint 的精度

位置：`tools/build_briefing_deck.js:392-396`，表头为“旧 paper32 nMAE”，32³ 填 `2.791e-3`，另外三个尺寸填 paper32 的数值。

只读 NPZ 证据：

| 文件与字段 | 尺寸 | 保存值 |
|---|---|---:|
| `test_results_dco_lr1e3_300.npz`，`exp2_nmae[1]` | `exp2_sizes[1] = 32^3` | 0.0027908437186852098 |
| `test_results_dco_paper32.npz`，`exp2_nmae[0]` | `exp2_sizes[0] = 32^3` | 0.004738019604701549 |
| `test_results_dco_paper32.npz`，`exp2_nmae[2]` | `exp2_sizes[2] = 64^3` | 0.002875168342143297 |

这两份原始文件都在 `archive/legacy_results/arrays/`，本轮仅加载上述小型结果字段，未加载权重。`slides/make_comparison_table.py:7-11,40-47,56-58` 本来就区分了两个 checkpoint；近期表格丢失了这个区分。

影响：近期表不能作为某一个模型的跨网格泛化曲线/表，32³ 基准被错误归属。各 NPZ 内自己的结果不变。

建议：为每条结果保留 checkpoint 标识和评价集合，不把来自不同权重的最佳行拼成一个模型。

### PR05 [P2] 冻结推理的 158 步被画成第二阶段完成了 2%

位置：`slides/make_p5_progress_fig.py:64-79` 固定 `158/8192` 进度条并称“本身就是论文 Table II 的验收口径”，使用方为 `slides/build_progress_deck.js:216`。

依据：`slides/make_comparison_table.py:12-13,49-58` 已明确 158/230 是 EXP3 冻结推理，不是逐步适配；论文原文 `:515-534` 是每步训练循环，`:571-586` 是 8192 步问题训练和场误差比较，Table II 为谐振频率表。方法和合格判据不同，步数比不是完成度。

影响：历史图不能证明已完成 158 个合格 Algorithm 1 步，更不能把到发散的长度当场门通过长度。不影响目前独立的 P/R128 记录。

建议：分别展示冻结诊断长度和逐步适配接受/场门步数，不使用这两个数字构成同一个进度条。

### PR06 [P2] 从平均耗时推内层更新数，并把经验关系升级成预算定律

位置：`slides/build_progress_deck.js:181-188,197-203,225-230`。从 71 ms/步推出“一两次迭代就够”，写“ε必须≤1/N”，并称当前差 `2×10^5` 倍；两张冻结模型相关性/CFL 图被说成验证了冻结和在线两种方法的两半。

依据与例子：论文 `docs/paper/paper_text.txt:571-576` 仅给 8192 步训练共 583 s，算术平均约 71.17 ms/步；没有给每步 Adam 计数。硬件、训练及评估成本不同，平均时间不能反推出迭代数。按同页自己列的 `sqrt(3e-3)≈0.05477` 与 `1/8192` 相比约 448.7 倍；按 `g-1=0.0156` 比约 127.8 倍，均不是 `2×10^5`。更根本地，局部误差到多步场误差还需要传播算子和误差相关性条件，不能由两张相关图推出普遍必要条件。

影响：7340 与 71 ms 的旧数字可作为各自配置的历史耗时记录，但不足以解释差异或估算论文优化成本；不能据该段推导重训预算、不可行性或预训练收益。

建议：保留论文总训练时间及推导出的均值，内层更新数记未报告；把误差增长说成明确条件下的模型/经验观察。

### PR07 [P2] 结构化控制的稳定性讲稿使用了错误的数学推理

位置：`slides/build_deck.js:298-299,341,350`；`slides/build_repro_section.js:331-334,370`。讲稿称“两对称算子复合还是对称的”，再由实谱推出一步推进谱半径恒为 1，并把 ρ=1 解释为能量不增不减。

独立代数反例：取两个对称正定矩阵 `A=diag(1,2)`、`B=[[2,1],[1,2]]`，则 `AB=[[2,1],[2,4]]` 非对称。再取 `J=[[1,1],[0,1]]`，ρ(J)=1，但 `J^n=[[1,n],[0,1]]` 会增长，不能推出能量守恒。这些反例直接否定讲稿的通用推理，不是对项目某个具体满足额外条件的结构化算子的否定。

影响：可能高估控制算子的理论保证及对 DCO 的替代价值。`slides/make_slide_figs.py:276-300` 和 `slides/build_deck.js:306-314` 至少记录了特定 CFL 限制，应保留，不能用“一定稳定”覆盖它。

建议：新说明必须给出离散内积、边界/对易或伴随关系、时间推进矩阵及 CFL 条件；结构化/Yee 控制依旧不能记为 DCO 成绩。

### PR08 [P2] 缺失成本被默认成 0，精确零残差被变成缺失

位置：`scripts/figures/make_group_meeting_progress.py:76-77,123-125,131`。

静态可确定行为：摘要不含 `new_adam_updates` 时，`get(...,0)` 仍绘制 0 次更新，纵轴称“Total Adam parameter updates”；缺 `accepted_steps` 同样显示 0。残差读取用 `value or np.nan`，有效数值 0 被改成 NaN。仅有 `{"status":"PASS"}` 的摘要会被显示成 PASS、0 更新、0 个物理步，未要求任何完整性证据。

影响边界：这是生成器的缺证据处理缺口，**没有证据说明现有五份历史摘要实际缺这些字段**。上游 first-E 生产者确实写 `new_adam_updates`，不能把正常 first-E 的 3769 次说成被漏记。clean64 图只累加接受行 (`:72-79,104`)，不能用于含失败/重试的轨迹总成本；固定 clean64 是否受影响需原 JSONL，本地指定输入当前缺失，记 INCOMPLETE，不按零成本补数。

建议：缺字段报 INCOMPLETE；精确零保留并为对数图作明确标记；接受更新、失败/重试和其他优化器成本分列。不要把缺字段回退为 0。

### PR09 [P2] 宽松生成入口可能留下新旧混合图组，并在失败后正常结束

位置：`scripts/figures/make_figs.py:17-18,59-63,104-107,215-235,564-573`；`slides/make_slide_figs.py:305-309`；`slides/make_stage2_longrun_figs.py:15-18,32-35`。

例子：`make_figs.py` 根据当前目录 glob 选输入，缺文件就跳过，异常只打印后继续，最后输出 `done.`，不提供完整产出集合的失败退出；同名旧 PNG 不会因此失效。longrun 四个输入可逐个跳过，甚至全缺仍保存空比较图。`make_slide_figs.py` 也是逐函数吞异常。当前根目录的 `fdtd_cavity.npz`、`test_results.npz`、`spectral_dco_L4.json` 均不存在，而归档中有对应类别的资产；导入 `resolve_legacy` 不会自动重写这些裸字符串/glob。

影响：重新执行不能证明得到一套同批完整图，静态 PPT 可能继续引用上次遗留文件；控制/失败臂缺失时比较集合会缩水。本轮未执行，未覆盖任何旧图，也未证明某份旧 PPT 已触发此路径。`make_figs.py` 已列入 `project/script_registry.json:85` 的历史入口，统一入口封存降低了误跑风险，但直接运行源码仍有该行为。

建议：今后独立新输出入口使用显式输入清单和内容哈希，缺必需对照时停止或显著标明 INCOMPLETE，返回结构化逐图状态。原历史入口不原位重跑。

### PR10 [P2] 换网格图的回退路径把“第一个测试尺寸”当训练尺寸

位置：`scripts/figures/make_figs.py:233-235,259,264-277`。

例子：当四个 `FIG4_PICK` checkpoint 均缺失时，代码选择可用结果中的前四个，并一律把横轴第一个尺寸标“trained on this”，其余标“never seen”；倍数固定为 `rel[-1]/rel[0]`。已有 `test_results_dco_lr1e3_300.npz` 的尺寸顺序为 `[16^3,32^3,48^3]`，对应 relL2 `[0.0205290475860,0.0130372922868,0.0193913923576]`。该模型训练网格为 32³，代码却会标 16³ 为训练、32³ 为未见，并报约 0.945 倍；从真正 32³ 基准到 48³ 约为 1.487 倍。

模型训练网格的来源还可对照 `slides/make_comparison_table.py:7,34` 及已审阅的 `docs/reports/2026-09-16-dco-value-retrospective.md:28`；本轮未重新载入 checkpoint。NPZ 尺寸和误差来自直接只读加载。

影响：只影响进入回退或混合训练尺寸集合的图，原默认四个 16³ 模型是否受影响不能一概而论。潜在错误会把泛化退步画成改善。

建议：按各 checkpoint 的训练网格标记和取分母，没有身份字段则不作 trained/unseen 及退化倍数断言。

### PR11 [P2] 32 步图表清单已实际把 run #43 记为 #38

位置：`slides/make_stage2_figs.py:37,47,76,81`。图注和报告写 run #43，明确 run #38 是修正前历史轨迹，但清单固定 `{'run':38,...}`。

已有证据：`evidence/stage2_mechanism_32/figures_manifest.json:2` 实际就是 `"run":38`。其 `json_sha256` 为 `2a6a3f3f104cffd1f924b185a8708db85c9acef6e49b70f161f51e8cc01ed01d`，本轮只读重新哈希，匹配 `evidence/pidon_stage2_32_lr1e3_i200_postloss.json`，即该脚本读取的修正后数据。不是仅推测未来可能错。

影响：按清单追溯会误关联旧运行及其成本/版本；有输入哈希仍可定位正确 JSON，因此不能推断曲线用了错误数据，也不改写原残差失败。

建议：仅在新更正清单中写清主机、行动、lab run 和输入哈希关联，保留旧清单。

### PR12 [P2] 近期汇报从解释字符串抓数字，不能可靠保持指标与单位

位置：`tools/build_briefing_deck.js:500-501`，`reason.match(/[0-9.]+/)[0]*100` 被作为 Ex/Ey nMAE 百分比。

只读内存例子：`nmae=0.015486045` 得 1.5486045%；同一值改写为科学计数法 `nmae=1.5486045e-2` 得 154.86045%。`weak_absolute_pass=True` 不含数字，会在 `[0]` 处失败；若解释文本先写阈值，提取的也可能是阈值而非观测值。

影响边界：可读 random128 摘要当前为普通小数字符串，例如 Ex 的 `nmae=0.0178011991427113`，此格式能正确提取；这不证明当前 1.55%/1.63% 已提错。p128 指定原始摘要当前缺失，未声称本轮重新验证其实际格式。问题是生成器把自然语言说明当数值合同。

建议：使用对应 step 的结构化分量数值及明确零/弱参考分支；缺失数值就标 INCOMPLETE，不从 reason 推断单位和指标。

### PR13 [P3] 历史发散图裁掉真实 loss 峰值，图注范围也不准确

位置：`slides/make_p3_p4_figs.py:127-135`，loss 轴固定上限 1.3，图注写“全程停在0.5~1.0”。

原始 `archive/legacy_results/metrics/pidon_solve_random.json` 实际 `max(lossH)=1.9008760452270508`，`min(lossE)=0.40697601437568665`，`max(lossE)=1.0570071935653687`。因此至少一个 H 峰被裁掉。首尾 nMAE 为 `2.6042372013393623e-12` 与 `1.6901856820836443`，接近 12 个数量级的增长描述仍大致成立。

影响：错误范围削弱“真实全程”图注准确性，但不改变这条未收敛轨迹发散的反例。脚本已明确 n=15、固定4次迭代，并说明与 n=31 定量段不是同一实验；这些区别应保留。

### PR14 [P3] H 状态被描述为六个分量支撑数组

位置：`tools/build_briefing_deck.js:425`，“Hⁿ⁺¹ᐟ² 的六个 Yee 支撑数组”。H 自身只有 Hx/Hy/Hz 三个分量，E+H 才是六分量；同文件 `:171-174` 的 Yee 解释也区分了这两组。

影响：会让初学者误解 H-net 输入维度，不改变实际网络/求解器数组。建议将“六个”纠正为“三个磁场分量的交错支撑数组”。

## 历史快照与同源边界

以下不因硬编码或停留在旧日期就判错，也不建议在原目录“刷新历史”。

| 链路 | 已核查的性质 | 边界 |
|---|---|---|
| paper_first / grid_diagnosis / spacing_probe | 调用 `verify_claims` 的对应数组读取器；相关读取器检查 manifest、数组与保存源码哈希并重新计算相应算子指标。MRE/nMAE/预测变化分开，Yee 标为参考。 | 固定 run #13/#18/#23 的报告模板，固定叙述不应自动当最新审计；本轮未调用读取器，也未对全部大数组复算。paper_first 的频率标注来自 summary 的 reference，不能把“算子指标从数组重算”扩称所有频谱峰也重新提取。 |
| coverage_ab / trunk_repair | 明确 A0/A/B/C 与新旧种子；图表区分 x-MRE、宏 nMAE、单波坐标干预；固定 FAIL 与局部 PASS 分列。 | 固定200次预算的历史报告，已读文件没有把坐标控制或局部改善提升为整体 DCO 成功。硬编码门结论只适用于该不可变实验。 |
| A3 / stop_review / night_review | 图明确 oracle E、精确核/几何控制、不计 DCO；night_review 将“错误检查器接受坏输入”正确转成验收 FAIL。 | 它们读取保存的审计，不是重新推理权重。`make_stop_review_report.py:24-25` 还拒绝覆盖已有图文。未因固定标题“FAIL”再列泛化 bug。 |
| night_report | 真实登记 N3 的 Adam/head/solve/closure 分列，oracle 765 次单列；已有 JSON 的 N3 为 FAIL/PASS/FAIL，Adam 为499/396/499，和固定文案一致。 | `:123-136` 的 bind 分支会修改 stage/manifest，`:141-153` 支持 `--root` 但文字大量绑定旧 run。只可作为该夜的历史交付器，不能未经改造当任意新运行的实时审计；本轮未运行。 |
| export_storage_revision_handoff | 范围明示仅计划交接、不是 G0；输出携带文档哈希且拒绝覆盖已有 GOAL_INSTRUCTION。 | `:23` 先写交接文本、`:27-29` 后断言，失败可能留下部分输出。这是交付顺序风险，未观察到历史错误，未升级成科学结果问题。 |
| make_slide_figs 的教学静态图 | E/F/G/H 数值为固定旧结果，文件头明确有转录；不能仅因未自动读 JSON 称其伪造。 | B 频谱曲线来自 `/tmp/cav.npz` (`:65`)，五个“实测峰”却来自常数 `mine` (`:71-83`)；C 声称现场生成但未检查子进程退出 (`:97-100`)。这两条混合链缺少输入身份约束；现有临时输入未核对，峰值正确性 INCOMPLETE。不能仅重跑图就称已经重新认证。 |
| build_briefing_deck | 带2026-09-17/r4日期，是汇报快照；大部分 S1R/P-R表为手工转录，不能因之后有新训练便称其错误。 | 一部分数值动态读摘要 (`:103-105,347-350,379`)，另一部分固定 (`:380-381,513-514`)；r128 变量未参与后续表格。0.312%/21.332% 当前与 op 摘要一致，但更换输入不会让所有页同步。未见统一的图/摘要/源码内容绑定清单。 |

特别说明：`slides/make_p3_p4_figs.py:11-27` 主动承认训练曲线和验收 checkpoint 不同、左侧轨迹和右侧定量记录不同，这属于应保留的来源说明。`make_p5_evidence_figs.py` 的 C2/C3 数值调用共享读取器，确有同源设计；但不能因此认证 PR01 的固定指标“纠偏”图，也不能推得 PR06 的在线普遍定律。

## 当前汇报引用核对

为区分“源码里存在”与“目前真的在汇报”，补充只读检查了现有 `汇报素材/PI-DON导师汇报_20260917_r4.pptx` 的 ZIP/XML 文字。没有打开编辑器、生成、重存、解包落盘或渲染 PPT。该文件 SHA256 为 `68ca62c55be623ac661b6fe6f0088805dad6635bb5b14c9deec10f32dd936e50`。下列页号来自实际 `ppt/slides/slideN.xml`，不是按源码注释猜测；“未引用”仅指当前 r4 源码未直接引用对应旧图/断言，不推广为所有历史汇报均未引用。

| 问题 | 具体数字/定义来源 | 当前引用状态与影响 |
|---|---|---|
| PR01 | 本地 `test_results_dco_paper32.npz:exp2_nmae` 对论文式(5)/Fig.6 MRE；旧纠偏图的40~200与0.7~1.5来自 `make_p5_evidence_figs.py:120-126` 转录常数，不是实时测量。旧训练轴取 `../dco_L4_hist.json:nmae[-1]`。 | **r4第26页实际存在**“旧模型较好/略差”，且同页承认指标不同。旧0.70倍、40~200倍图未被r4直接引用；旧progress源码`:127-128,224`仍嵌入相应图。只否定比较结论，不删除NPZ结果。 |
| PR02 | `9.6e-3`来自论文`:585-586`场MRE，`1e-5`是项目R门；旧32步图读取 `evidence/pidon_stage2_32_lr1e3_i200_postloss.json:rows[].lossH/lossE`，把常数1e-4当同单位线。 | **r4第19页实际存在**“比论文9.6e-3严很多”。旧 `stage2_algorithm1_32.png` 未被r4直接引用。影响成本解释，不表示总耗时数值错误。 |
| PR03 | 论文Section IV-B与旧汇报“没有分析”断言冲突，非数字转录错误。 | r4源码未沿用该断言；保留在两份旧deck源码的正文/notes，不称为当前r4错误。 |
| PR04 | `test_results_dco_lr1e3_300.npz:exp2_nmae[1]`的0.0027908437被归到paper32；paper32同尺寸实际0.0047380196。 | **r4第26页实际存在**“旧 paper32 nMAE”列中的2.791e-3。这是已进入当前成稿的模型身份错误。 |
| PR05 | `make_p5_progress_fig.py:66`固定158和8192；前者按既有EXP3记录说明属于冻结paper32，后者为论文逐步问题训练。此处未重新认证158事件。 | r4未引用 `p5_progress.png`；旧progress源码`:216`直接引用。2%的算术没错，阶段/验收含义错。 |
| PR06 | 71.17ms是论文583s/8192；7340ms、g=1.0156、2×10^5来自旧progress源码常数，且其`:205-208`明确原始记录当时未随代码提供。 | r4源码未沿用该预算推论；旧progress源码直接展示。当前不能独立认证7340ms或g，2×10^5也不由同页列出的量算出。 |
| PR07 | 旧deck/repro讲稿的普遍数学断言，不是读取器测出的定理。 | r4源码未沿用该证明；影响旧结构化控制的理论解释，不回溯更改控制数值。 |
| PR08 | `make_group_meeting_progress.py:20-25`五个run各自的`summary.json:new_adam_updates/accepted_steps`；clean64的`steps.jsonl:fit_H/fit_E`。0回退来自源码，不是已确认的输入值。 | r4未引用 `figs/group_meeting_20260916` 图组。当前r4`:490`的3769为另一处手工转录，不能用本缺字段反例推翻它。现有图是否已受影响仍INCOMPLETE。 |
| PR09 | 各入口文件/glob选择与吞异常逻辑；不存在一个已查明“算错的数字”。 | r4不调用这几个生成器；旧progress/repro有静态PNG依赖，可能继续读旧图。未证明当前r4或某份历史成稿已发生新旧混图。 |
| PR10 | lr1e3 NPZ的`exp2_sizes/exp2_rel`与训练网格32³：回退路径0.945应按正确基准解释为1.487。 | r4未直接引用通用fig4，且本轮未重生成图；只确认可触发的标注/分母错误，不宣称现有r4带有该0.945值。 |
| PR11 | 既有 `evidence/stage2_mechanism_32/figures_manifest.json:run`为38；其输入哈希匹配postloss JSON，源码/图注身份43。 | 已落盘的旧清单错误；r4未直接读取该清单/32步图，未把问题提升为当前r4数据错配。 |
| PR12 | `tools/build_briefing_deck.js:103`指定P摘要的`field_gate_128.components.Ex/Ey.reason`。科学计数法反例是内存合成输入，不是已证实的本次P摘要内容。 | **r4第36页实际显示1.55%/1.63%**，对应动态解析路径；当前未发现数字错误。第37页的1.549%/1.631%为独立手工常数。风险在以后换格式/输入时，不据此撤销现有场门FAIL。 |
| PR13 | `archive/legacy_results/metrics/pidon_solve_random.json:lossH/lossE`与脚本固定ylim；H峰1.900876高于1.3。 | r4未引用 `p4_growth.png`；旧progress源码`:176`直接引用，`:179`还重复0.5~1.0范围。已确认源码会裁峰，但未重渲染认证旧PNG内容。 |
| PR14 | H只有Hx/Hy/Hz三分量；“六个”来自源码`:425`固定文字。 | **r4第29页实际存在**该六数组说法。只改讲解维度，不表示生产张量真的多了三分量。 |

父侧已审 `briefing_operator_audit` 和 `briefing_pec_audit`，本报告不重复这两个审计实现；对其产物只做当前汇报取数/图片引用的边界说明。上表中的历史NPZ默认目录为 `archive/legacy_results/arrays/`。

## 每文件实际覆盖

下表“全文”仅指源码静态覆盖，不表示执行、渲染或科学复算通过。依赖源码只作定点核对，不扩张本轮独占范围。

| 文件 | 实际覆盖 | 读取、输出与审查结果 |
|---|---|---|
| `slides/build_deck.js` | 全文1-354 | 五页静态正文/图表/notes；PR01、PR03、PR07，冻结与结构化控制范围。 |
| `slides/build_progress_deck.js` | 全文1-276 | 五页及所有图片引用、表格、推论；PR01、PR05、PR06。 |
| `slides/build_repro_section.js` | 全文1-381 | 七页复现段、所有notes；PR01、PR03、PR07；硬编码 Linux 图目录是历史依赖。 |
| `slides/extract_paper_figs.py` | 全文1-44 | PDF输入、页号、两个固定裁剪框、输出；不计算指标。注释称题注定位，实际固定第三页坐标，末尾明确需手工调版式；未对实际裁剪效果验收。 |
| `slides/make_comparison_table.py` | 全文1-112 | 配置、两模型注脚、指标倍数、步数限定；PR01，正确区分模型的注释用于PR04核对。 |
| `slides/make_coverage_ab_figs.py` | 全文1-148 | 三面板、训练曲线、全表和manifest；宏nMAE/x-MRE/干预效应分开；固定历史模板。 |
| `slides/make_grid_diagnosis_figs.py` | 全文1-139 | 矩阵、形状/间距控制、RMS对照、报告和manifest；变化量分母及ROI解释明确。 |
| `slides/make_p3_p4_figs.py` | 全文1-148 | 两训练图及发散双轴图、来源说明；PR01、PR13。 |
| `slides/make_p5_evidence_figs.py` | 全文1-157 | C2/C3共享读取、过滤、拟合、固定纠偏图；PR01/PR06，根目录glob迁移限制。 |
| `slides/make_p5_progress_fig.py` | 全文1-87 | nMAE目标轴和158/8192条；PR01、PR05。 |
| `slides/make_paper_first_figs.py` | 全文1-172 | 指标、x分量场图、FDTD波形/频谱、报告及哈希；正确区分MRE/nMAE/参考解；仅部分指标经共享读取器重算。 |
| `slides/make_slide_figs.py` | 全文1-309 | A-H全部教学图与异常循环；PR07相关控制显示、PR09；B/C混合动态与静态来源限制。 |
| `slides/make_spacing_probe_figs.py` | 全文1-147 | 单轴/横向干预/固定q三图及报告；L2、增益、nMAE不混称；明确Yee非误差下限。 |
| `slides/make_stage2_figs.py` | 全文1-87 | 32步图、report、manifest；PR02、PR11；短程有限不等于8192合格已明确。 |
| `slides/make_stage2_longrun_figs.py` | 全文1-38 | 四条历史输入、两指标轴、缺文件与输出路径；PR09；可读四份JSON分别确有128/64/64/64条，标签tol是目标，不证明最终过门。 |
| `slides/make_trunk_repair_figs.py` | 全文1-126 | C/A/B与独立新种子、训练和成本描述、报告/manifest；冻结参数未变与输出未变没有混同。 |
| `scripts/figures/export_storage_revision_handoff.py` | 全文1-39 | 交接提取、断言、已有文件保护和哈希；只作计划交付，局部写入顺序风险见上。 |
| `scripts/figures/make_a3_evidence_figure.py` | 全文1-53 | 保存的A3残差、H布局、oracle E、固定R门；没有把几何控制记为DCO。 |
| `scripts/figures/make_figs.py` | 全文1-573 | fig1/2/3/4/5/6/8/11全部数据选择、筛选、轴/单位、标签及入口；PR09、PR10。谱图排除了rho<=1/未发散等记录，只能描述筛后子集，不是所有模型不稳定的证据。 |
| `scripts/figures/make_group_meeting_progress.py` | 全文1-188 | clean64逐步成本/残差/Q、五实验摘要、manifest；PR08；manifest保存路径未保存内容哈希，不能独立认证不可变身份。 |
| `scripts/figures/make_night_report.py` | 全文1-160 | N3图、全部中文模板、资源/控制区分、bind/main；历史JSON数值定点一致，未运行bind或覆盖报告。 |
| `scripts/figures/make_night_review_figure.py` | 全文1-42 | 四旧fit、六反例检查、原门与标注；正确表达oracle/反例FAIL，未认证现在的求解器。 |
| `scripts/figures/make_stop_review_report.py` | 全文1-140 | 图文、固定失败叙述、Adam/LBFGS/closure、精确核、覆盖保护；原始失败与工程检查范围分开。 |
| `tools/build_briefing_deck.js` | 全文1-622 | 45个源码slide段、工具函数、全部表格/图片/动态字段；PR01-04、PR12、PR14；未生成r4或修改已有PPT。 |

## 核查限制与建议顺序

本轮只读核查包括论文本地文本、指定源码及相关读取器、保存 JSON、两个测试 NPZ 的小型指标字段、既有清单与单文件哈希，以及现有r4 PPT内的文字XML；只在内存演算了字符串解析反例。没有执行科学训练、模型推理、图表渲染或全量验证器。原文 Table I 的表格数值在文本提取中不完整，因此未声称独立核对了 `5.3e-3/7.7e-4` 的每一位；式(5)与 Fig.6 指标定义已有明确文字证据。

本地旧根路径失效、部分服务器摘要已迁移：重生成能力及部分输入完整性为 INCOMPLETE，不能改称 NOT_RUN。历史的 import/bootstrap 与输出覆盖问题，只说明这些脚本不能原样作为当前审计入口；不能据此断言当年的图没生成过。

建议用户先决定是否纠正 PR01-07 的科学解释与模型身份，再决定是否为未来新输出修 PR08-12 的生成/追溯链。PR13-14 可随新稿修订处理。**不建议为修图重训，也不建议在历史输出目录重跑这些生成器。**

## 源码身份

本轮范围内文件的 SHA256 如下；它们只定位本次审查的源码，不代表全部输入/历史图已经认证。

| 文件 | SHA256 |
|---|---|
| `slides/build_deck.js` | `6dad7ce7565b8983f224ad7c4b0b5b10687c9bd07a8baf5957266341e2612284` |
| `slides/build_progress_deck.js` | `566aff3778d64bc9f9efd7d365106329d746356497cec4f41e87f6bf4c1db6c0` |
| `slides/build_repro_section.js` | `d76b4fa691f34b2de332438568a648e3def61bb11bf3e9731e1f1851dd1c02f5` |
| `slides/extract_paper_figs.py` | `51aed8867cfefaea14be05c9fd6567f7856e11559c35ec5704ff7ba7a7716cc3` |
| `slides/make_comparison_table.py` | `9099e90c1e8018735274a1b096d98947f4b26def9d6b515d02e2dd25cdbbec33` |
| `slides/make_coverage_ab_figs.py` | `fa32ebc79b2dd4043551eb97ca8825ca2948dccb8db43d0cdf8b43a2e6a06bff` |
| `slides/make_grid_diagnosis_figs.py` | `7eb158f68bd52e5991a57dfe995499b39dd0b9d7f53d0f02f1304a15ed676275` |
| `slides/make_p3_p4_figs.py` | `47f55224218ff25a97a6e124c4a865838c7125b343611a7bad65602d5faeeb58` |
| `slides/make_p5_evidence_figs.py` | `bf168853b31b58474ca2737cfb329f574d8ecc07c973c3caafb602fcf1b8b6c7` |
| `slides/make_p5_progress_fig.py` | `d830b18d82c072827726d1d84a6a7c4f7bc1956df883bce136513fa0c540bef1` |
| `slides/make_paper_first_figs.py` | `3de4752fd66b4af2da313bc1847e653fbc638599f4e1e09fb09d67c65ec74b93` |
| `slides/make_slide_figs.py` | `adb982e48c091ebeee9a129e31b1120016fc27dc41cbc49c61e258f574713047` |
| `slides/make_spacing_probe_figs.py` | `9bb72d10b97d75cf5c212d419ab83c648f63c0dea94f0ed8aba185b0a9b82b14` |
| `slides/make_stage2_figs.py` | `af0f647d74fe5f94299137eb9a66f2c52483e23e51534ab4e042019fa306c5d0` |
| `slides/make_stage2_longrun_figs.py` | `6d10fad0d0b5b906a998414a6fa1b4c87a3c09be69ab6a1ad734828d6d55f8f2` |
| `slides/make_trunk_repair_figs.py` | `b71726b2e659492c7a4dd74eec0932d6b5ec53aa87a9f4c3af1fa355decd9212` |
| `scripts/figures/export_storage_revision_handoff.py` | `db3367a043baad29b1d00591b87cb2b0008c849ab347bb87c438ebc1390e5a78` |
| `scripts/figures/make_a3_evidence_figure.py` | `110f00e3a35fa7d951fb9b774189b0b0f8f8762ce3cae581b6d7c45517a0491d` |
| `scripts/figures/make_figs.py` | `07c15135911966031616a0d0fab48b8c7dd3fb89eb7cc11783b65f062ac7fa8a` |
| `scripts/figures/make_group_meeting_progress.py` | `6acc8470261d37ddcc7f4c3e677e5258cea3d5d791878825ab286fb518e29d6c` |
| `scripts/figures/make_night_report.py` | `1d09a9770f0651c970f1088fd4051a529a50c8c4fd4d55fafd14903614f8146d` |
| `scripts/figures/make_night_review_figure.py` | `122c7161edf18dd987c05b1364c90beaaeb421de85b36e305536f267feb1a4dd` |
| `scripts/figures/make_stop_review_report.py` | `9a31948dd86ab31f804d52fed55c6b458ae4c13453753b1119f362ef1aef7709` |
| `tools/build_briefing_deck.js` | `0512b650fd4c7900b1123a59e630bc6590c2a3f2d192f159bb2f916e33bf22f1` |
