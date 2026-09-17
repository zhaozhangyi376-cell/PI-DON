# 历史与探索入口只读代码审查

日期：2026-09-17。范围：`scripts/exploratory/` 下全部 12 个 `.py`，以及用户指定的 6 个实验脚本，共 18 文件、4320 行。本文是全项目审查的一个分册，不代表全项目审查完成，也不是科学重新认证。

本轮只新增本文；未修改生产源码、计划、历史结果、权重或账本，未派 agent，未运行训练、旧主入口、自检或科学实验。建议测试全部为 **NOT_RUN**。问题依据为逐行静态检查、调用关系、明确的代数推导和已有 JSON/账本的只读摘录；没有把推导写成“已运行反例”。

目标差距：区分历史诊断能够支持的结论与当前逐时间步适配机制的证据，防止把探索算子的稳定性、参考控制或有偏指标解释为 DCO 的精度、成本或复用成绩。

## 结论与生产影响

- 三项优先处理的历史科学解释问题：`structured.py` 对非线性 CNN 使用线性基向量矩阵；`structured_cavity.py` 用共点训练标签校正实际交错 Yee curl；其频谱汇总又按误差大小排除模式。它们会改变相应历史诊断的解释，不能由此推翻当前正式 P/R128 的已记录失败。
- 18 个入口全部出现在 [script_registry.json](C:/PI-DON/project/script_registry.json:31) 的 `historical_entrypoints` 中；[run.py](C:/PI-DON/run.py:60) 在执行之前拒绝它们。封存的是主入口，导入函数仍被允许；直接执行脚本也没有同等保护，因此不等于代码已不可调用。
- 反向检索 `src`、`scripts/experiments`、`tools`、`tests`、`_01/src` 并核对正式调用点，未发现当前 `Solver`、`direct_m2_runner`、`server_short_tol_probe` 或 `phase1_full_run` 导入这 12 个探索模块或其算子。正式 P 入口仍指向旧 `dco_lr1e3_300.pt`（[server_short_tol_probe.py](C:/PI-DON/scripts/experiments/server_short_tol_probe.py:27)），随机对照显式使用 `random`。不存在依据这些探索缺陷就改判正式 P/R128 的证据。
- 仍有用途的历史依赖：旧 `test_dco.py:45` 导入 `train_pidon.yee_curl_t`；旧 `night_runner.py:21` 和两个 contract 测试导入 `pidon_exact_control`；`a2_zero_curl_control` 调用其 `run`。这是“旧评估/控制/测试依赖”，不是正式 DCO 用精确答案替代预测。
- 资产影响与代码依赖应分开：lab #73 确实产出过腔体监督微调模型，lab #74 曾把它作为旧 16 步实验初始化；这条旧实验应标为“额外 FDTD 数据监督后的诊断”。本轮未发现当前正式 P/R 使用此模型。C200 也曾训练和评估，但旧报告保留 U1/U2 FAIL，没有证据显示被提升为当前基线。

起手已读取 AGENTS、PLAN、STATUS、总审查 REVIEW，并执行要求的只读 `project_harness status` / `next`。前者退出 0，后者因许多历史 evidence 路径缺失退出 1；未据此修改任何状态。报告中的旧 JSON 值是读回摘录，不等于本轮从场数组/权重独立复算。

优先级沿用总报告：P1 为会改变科学结论的重要问题，P2 为特定模式、指标或可靠性问题，P3 为展示/维护问题。这里的 P1/P2 主要指历史诊断自身，不表示当前生产主路径正在触发。

## 逐文件覆盖

覆盖等级：**full** = 全文件逐行静态审查，包含公式、主控制流、输出和依赖；**partial** = 只读与本范围相关的函数、片段或搜索命中。主范围 **18/18 full，0 partial**，其中 5 个文件另读回直接相关历史 JSON/账本。full 仅表示阅读覆盖完整，不表示运行通过或科学正确；所有动态测试均 NOT_RUN。

| 文件 | 行数 | 实际 coverage | 当前用途、发现与边界 |
|---|---:|---|---|
| [diag_coords.py](C:/PI-DON/scripts/exploratory/diag_coords.py) | 109 | full | 封存坐标诊断；X09。不能把坐标编码不随网格变化等同精度不变。 |
| [diag_exp3.py](C:/PI-DON/scripts/exploratory/diag_exp3.py) | 128 | full | 封存源/输入尺度诊断；X11。gauss/add 与 diff/hard 是不同诊断问题。 |
| [manifold_check.py](C:/PI-DON/scripts/exploratory/manifold_check.py) | 136 | full | 封存分布诊断；X10。方向性相关不证明误差唯一原因。 |
| [mini2d.py](C:/PI-DON/scripts/exploratory/mini2d.py) | 244 | full | 周期二维冻结网络；curl/div 索引静态自洽。见限制 L1、L5、L6。 |
| [structured.py](C:/PI-DON/scripts/exploratory/structured.py) | 380 | full | 二维对称滤波与自由 CNN 对照；X01、L2。 |
| [structured3d.py](C:/PI-DON/scripts/exploratory/structured3d.py) | 251 | full | 三维周期线性滤波；差分符号/谱导数半点相位静态自洽；L2、L3。 |
| [structured_scale.py](C:/PI-DON/scripts/exploratory/structured_scale.py) | 624 | full | Auto3D/PolyM/AdjPair；X04；有限预算误差不是表达能力下界，见 L3。 |
| [structured_deep.py](C:/PI-DON/scripts/exploratory/structured_deep.py) | 292 | full | 深层线性 T；X05；伴随逆序实现合理；L2、L5。 |
| [structured_material.py](C:/PI-DON/scripts/exploratory/structured_material.py) | 192 | full | 周期材料矩阵诊断；正对角相似变换自洽，非 Fig.8 复现；L1、L2。 |
| [structured_pec.py](C:/PI-DON/scripts/exploratory/structured_pec.py) | 162 | full | 去 PEC 切向 E 自由度后的矩阵控制；未发现核心伴随构造新 bug；L1、L4。 |
| [structured_cavity.py](C:/PI-DON/scripts/exploratory/structured_cavity.py) | 332 | full | 成对替换腔体诊断；X02、X03；共享源与投影并非生产 Algorithm-1 认证。 |
| [symplectic.py](C:/PI-DON/scripts/exploratory/symplectic.py) | 249 | full | 人工线性扰动对照；X12、L2。默认小扰动不因注释错误自动失效。 |
| [spectral_dco.py](C:/PI-DON/scripts/experiments/spectral_dco.py) | 368 | full（另读历史证据） | 固定网络的周期局部 Jacobian 诊断；X06、X07、X08；读回 R2 原 JSON。 |
| [train_pidon.py](C:/PI-DON/scripts/experiments/train_pidon.py) | 367 | full | 历史离线 div/短展开训练，不是当前逐步适配器；X14、L1、L6。 |
| [adapt_dco_cavity.py](C:/PI-DON/scripts/experiments/adapt_dco_cavity.py) | 71 | full（另读历史证据） | 明示的 FDTD 监督诊断；读回 lab #73/#74、loss JSON；X14、L5、L6。 |
| [pidon_exact_control.py](C:/PI-DON/scripts/experiments/pidon_exact_control.py) | 294 | full（另读历史证据） | 仍被测试/旧 runner 调用的控制函数；读回 A2 四臂，见控制边界 C1。 |
| [a2_zero_curl_control.py](C:/PI-DON/scripts/experiments/a2_zero_curl_control.py) | 37 | full（另读历史证据） | 零 curl 负对照封装；拒绝控制门才是预期结果；C1。 |
| [trunk_repair.py](C:/PI-DON/scripts/experiments/trunk_repair.py) | 84 | full（另读历史证据） | 历史 C200 单臂；X13；实际 train_arm 有冻结和 200 更新核查。 |

相关依赖仅为本范围解释所需的定点审查；不替代父侧对 core 和当前 runner 的全量审查。实际辅助阅读覆盖如下：

| 辅助文件 | 实际 coverage | 本轮读取内容 |
|---|---|---|
| `run.py`、`project_paths.py` | full | 完整入口和路径兼容代码。 |
| `src/pidon/fdtd.py` | partial | curl、PEC、两种更新顺序、源定义及 modes/spectrum。 |
| `src/pidon/dco.py` | partial | 归一化、指标、坐标完整函数，以及 head/forward 的定点检索。 |
| `src/pidon/rollout.py` | partial | 50-210 行：周期 curl、CFL、初值、leapfrog、推理包装。 |
| `src/pidon/gen_data.py` | partial | 平面波生成、E/curl 交错位置和 build 的相关片段。 |
| `scripts/experiments/coverage_ab.py` | partial | train_arm 完整函数及预算/调用检索。 |
| `scripts/experiments/paper_recheck.py` | partial | sha256/dump 及旧参考设置。 |
| `src/pidon/pidon_solve.py`、`src/pidon/pidon_recording.py` | partial | 依赖、身份/源码快照相关符号与调用检索；不重复父侧 core 审查。 |
| `direct_m2_runner.py`、`server_short_tol_probe.py`、`server_local_review.py`、`phase1_full_run.py` | partial | 导入和初始化资产的反向依赖检查，不对其实现重新认证。 |
| `tests/test_trunk_repair.py` | full | 完整冻结/预算测试源码；未执行。 |
| `tests/test_pidon_contract_v3.py` | partial | 前 145 行，含 exact-control checkpoint 测试。 |
| `tests/test_pidon_contract.py`、旧 night/test runner、server queue | partial | 相关导入/初始化搜索命中，不是全文件审查。 |

封存 JSON、迁移映射、已有结果与账本属于证据读取，不计为被审查 Python 文件的 full 覆盖。

## 已确认问题

### X01 [P1] 自由 CNN 的“放大矩阵”不是该非线性更新的矩阵或 Jacobian

位置：[structured.py:156](C:/PI-DON/scripts/exploratory/structured.py:156)、[structured.py:207](C:/PI-DON/scripts/exploratory/structured.py:207)、[structured.py:337](C:/PI-DON/scripts/exploratory/structured.py:337)。

触发：默认 main 把带 GELU 和 bias 的 `FreeCNN` 传给 `spectral_radius`。后者将 `F(e_j)` 逐列拼为 M，没有线性验证，没有扣 `F(0)`，也没有在指定状态求导。

结果影响：非线性 F 一般不满足 `F(sum a_j e_j)=sum a_j F(e_j)`；甚至仿射偏置都会被重复放进每列。`eigvals(M)` 因此不能称自由 CNN 的时间更新谱半径。历史图 `fig10_structured.png` 的 free 曲线及“没有任何 dt 能稳定”的推论没有这个计算所声称的依据。Yee 和 Structured 分支是线性齐次的，不受此特定问题影响；独立闭环实际发散的观察也不被抹除。

建议：保留旧值为“基向量响应拼接诊断”，新入口对线性算子才使用此方法；非线性模型需要明确状态下的 JVP/Jacobian 和收敛误差。建议测试：仿射 `F(x)=Ax+b`、小型 GELU 网络，对照真正 Jacobian；另测线性 Yee/Structured 应相符。NOT_RUN。

### X02 [P1] 腔体修正核训练在共点场上，实际使用在交错 Yee 场上

位置：[structured_cavity.py:101](C:/PI-DON/scripts/exploratory/structured_cavity.py:101)、[structured_cavity.py:111](C:/PI-DON/scripts/exploratory/structured_cavity.py:111)、[structured_cavity.py:127](C:/PI-DON/scripts/exploratory/structured_cavity.py:127)、[structured_cavity.py:203](C:/PI-DON/scripts/exploratory/structured_cavity.py:203)。

触发：默认 `train_T`。`plane_wave_batch` 对所有 E 分量和解析 curl 使用同一个 `arg`，没有各自半格偏移；`yee_curl_periodic` 却用前向差分。实际腔体调用 `fdtd.curl_E`，各分量已经位于真实 H 支撑。

结果影响：训练逼近的不只是 Yee 导数幅值修正，还包括把半点导数搬回共点标签的相位修正。以只有 Ez 且沿 x 变化的波为例，前向差分天然在 x 半点，训练 C 却在 x 整点；把学到的同一个 T 用在真实 H 节点会多施加这段位置修正。不同方向的差分项也不能自动视作同一共点 curl。去掉边界壳层（129 行）解决不了体内半格错位。旧腔体色散改善/恶化不能单纯归因于“更准的交错旋度是否迁移”。伴随成对构造的稳定性代数并不因此失效。

建议测试：固定单一非轴对齐解析波，分别在 E 节点和 H 节点采样，逐分量核对差分与解析标签坐标；用恒等 T 验误差是正常幅值色散而非额外相位错位。复用 `structured3d.data` 的明确交错约定作为实现参考，但保留独立解析断言。NOT_RUN。

### X03 [P1] 超过 1% 的频率误差被当作“未激励”剔除

位置：[structured_cavity.py:238](C:/PI-DON/scripts/exploratory/structured_cavity.py:238)、[structured_cavity.py:245](C:/PI-DON/scripts/exploratory/structured_cavity.py:245)、[structured_cavity.py:254](C:/PI-DON/scripts/exploratory/structured_cavity.py:254)、[structured_cavity.py:323](C:/PI-DON/scripts/exploratory/structured_cavity.py:323)。

触发：某个已激励模式的近邻谱峰偏移超过 1%，或一个模式没有被峰提取器正确找到。

结果影响：程序根据要评价的误差决定该模式是否纳入平均，误差大的样本恰好消失。不同算子的 `mean(abs(error))` 可以来自不同模式集合，`s/y` 不再是同题比较。此处也没有验证模态耦合或峰的幅值；注释里的偶数模态解释不是代码执行的条件。默认 n=31 的源 x/y 索引 15 还不是几何正中心，不能仅凭“中心源”口头断言模式严格未激励。

建议：运行前冻结共同目标模式；对漏峰、错配、偏移分别记录，缺证据记 INCOMPLETE，不以误差阈值删除。建议测试：人为给五个峰中的一个加 2% 偏移，必须保留该错误；删除一个峰时不得报告完整五模均值；检查一对一匹配。NOT_RUN。

### X04 [P2] 大网格推进仍取 n=6 小网格的 CFL

位置：[structured_scale.py:251](C:/PI-DON/scripts/exploratory/structured_scale.py:251)、[structured_scale.py:275](C:/PI-DON/scripts/exploratory/structured_scale.py:275)、[structured_scale.py:587](C:/PI-DON/scripts/exploratory/structured_scale.py:587)。

触发：`--loop` 非零且实际 n 不等于 6，例如默认 n=16 配合 `--pair 1 --loop ...`。推进用实际 n 的 E，但 `cfl_exact(model,n=6)` 总在 6³ 上取最大特征值。

结果影响：两种网格采样不同波矢，小网格最大值不保证覆盖大网格。若漏掉真实高频最大值超过 0.99 安全系数能覆盖的差距，推进仍会超 CFL，导致把步长选择问题误归因于算子构造。反过来，小网格通过不能认证大网格稳定。`structured_deep` 已改成实际 n 的幂迭代（263 行），不能将本问题重复报在那一行。

建议测试：构造频率最大值落在 16³ 可分辨而 6³ 未采到的位置的线性核，对照两个网格的最大值与实际推进步长。正式使用时取实际网格的可靠上界；固定次数幂迭代本身仍非严格上界，见 L2。NOT_RUN。

### X05 [P2] DeepT 的额外隐通道从初始化起永久没有有效梯度

位置：[structured_deep.py:73](C:/PI-DON/scripts/exploratory/structured_deep.py:73)、[structured_deep.py:77](C:/PI-DON/scripts/exploratory/structured_deep.py:77)、[structured_deep.py:196](C:/PI-DON/scripts/exploratory/structured_deep.py:196)。

触发：depth>=2 且 ch>3，默认深度 2/3、ch=12 就触发。每层是无 bias、无激活的零核，仅通道对角的中心点设 1。

结果影响：第一层第 4 个及以后输出通道恒为 0；末层对应输入通道权重也为 0。梯度对入口权重乘上零的下游路径，对出口权重乘上零的上游激活，两端都无法离开零；深层中间的额外单位通道也与输入/输出断开。Adam 不会自行开启这些通道。因此报告的参数量包含无法参与拟合的宽度，“更多通道/更多参数没有收益”的比较被隐藏的有效宽度限制混淆。selftest 主动加随机扰动（119、136 行）会打破此状态，不能代表训练初始化已经覆盖这个问题。

建议：在独立新实验中采用保留近似恒等但打通额外通道的初始化；旧结果保留原初始化标签。建议测试：随机输入/目标只做一次反向传播，检查额外通道的激活、输入/输出连接梯度；再验证修订初始化的伴随关系。NOT_RUN。

### X06 [P2] 首次超过 100% 的步号会被后来超过 1000 倍的步号覆盖

位置：[spectral_dco.py:168](C:/PI-DON/scripts/experiments/spectral_dco.py:168)、[spectral_dco.py:172](C:/PI-DON/scripts/experiments/spectral_dco.py:172)、[spectral_dco.py:176](C:/PI-DON/scripts/experiments/spectral_dco.py:176)。

触发：误差先大于 1、后来大于 1e3 或变成非有限值。

结果影响：`blow=s` 在第二个条件再次执行，最终 `blowup` 变成中止步而非首次 100% 步。若窗口内没有到达 1e3，同一个字段又表示首次 100%。此外 s 从 0 开始，但比较的预测 N 是更新次数。历史 `spectral_*.json` 的 meas/blowup 不能未经阈值核对直接和预测交叉验证。此 bug 改变报告步号，不改变实际场演化。

建议测试：令误差序列依次为 0.1、2、2000，分别保存 `first_error_gt_1_update=2` 与 `abort_update=3`，并校验 NaN 的终止原因；不得共用一个变量。NOT_RUN。

### X07 [P2] 发散预测把 curl 相对误差当作初始场误差

位置：[spectral_dco.py:165](C:/PI-DON/scripts/experiments/spectral_dco.py:165)、[spectral_dco.py:191](C:/PI-DON/scripts/experiments/spectral_dco.py:191)、[spectral_dco.py:318](C:/PI-DON/scripts/experiments/spectral_dco.py:318)、[spectral_dco.py:330](C:/PI-DON/scripts/experiments/spectral_dco.py:330)。

触发：打印或引用 `pred_blowup`。eps0 是 `||curl_dut(E)-curl_ref(E)||/||curl_ref(E)||`；经验曲线却是 `||E_dut-E_ref||/||E_initial||`。

结果影响：单步 curl 缺陷进入 H 时有 `c*dt`，再进入 E 时还经历 curl_H 和另一个 `c*dt`。两个“相对误差”不是同一量，不能直接套 `eps0*rho^N=1`。以后每一步还有新的算子缺陷，且固定状态 Jacobian 不是整条非线性轨迹的 Jacobian 乘积。旧预测值只能视为未经校准的启发式，不能称已由谱半径定量解释发散时间。

证据边界：原 [spectral_pidon_R2_all.json](C:/PI-DON/archive/legacy_results/metrics/spectral_pidon_R2_all.json:8) 的 CFL=.99、seed=0 行保存 eps0=0.0286165625、rho=1.1162992332、pred=32.3014、blowup=129。这里只摘录原数；X06 说明最后一个数还存在阈值混用，故没有把这对数当作精确误差倍数重新认证。

建议测试：同一线性替代 curl 在不同 dt 下，直接比较一次完整更新的 E/完整状态缺陷和 curl 缺陷；预测必须使用同一范数、时间索引与明确的受迫误差递推。NOT_RUN。

### X08 [P2] 谱诊断的稳定标签比数值校验更强，且非有限结果没有完整拒绝

位置：[spectral_dco.py:132](C:/PI-DON/scripts/experiments/spectral_dco.py:132)、[spectral_dco.py:213](C:/PI-DON/scripts/experiments/spectral_dco.py:213)、[spectral_dco.py:340](C:/PI-DON/scripts/experiments/spectral_dco.py:340)、[spectral_dco.py:353](C:/PI-DON/scripts/experiments/spectral_dco.py:353)。

触发与影响：

- 线性自检用 `abs(rho-1)>2e-4` 判 bad；若 rho=NaN，比较为 False，该 exact 子项显示 ok。负对照另有不同分支，不能断言所有 NaN 必然使整个 selftest 通过，但 exact 子项确实没有正确拒绝。
- 正式行的 exact 控制偏差超过 1e-3 才警告，汇总却用均值 `<=1+1e-6` 宣称 stable；估计误差没有被这个 1e-6 边界认证。平均值还可能掩盖某个探针状态的不稳定。
- 警告没有保存为 JSON 有效性字段，FD 步长、iters、burn 等关键参数也未完整写入 out；NaN 可由 `json.dump` 默认导出为非标准数值。后续只读 JSON 无法可靠排除失效行。

历史影响：远高于 1 的旧局部增长迹象不因此自动消失；接近 1 的 stable 标签、跨状态普遍保证及精确增长量不足以成立。没有影响当前适配器残差/场门的计算。

建议测试：注入 NaN exact 结果；让两行一高一低但均值合格；为 FD 步长和迭代次数设置收敛检查并保存不确定区间。无充分数值分辨率时标 INCOMPLETE。NOT_RUN。

### X09 [P2] 坐标诊断没有按 checkpoint 的归一化和 head 重建推理

位置：[diag_coords.py:52](C:/PI-DON/scripts/exploratory/diag_coords.py:52)、[diag_coords.py:66](C:/PI-DON/scripts/exploratory/diag_coords.py:66)、[dco.py:171](C:/PI-DON/src/pidon/dco.py:171)。

触发：传入 `norm=rms` 或 `head=potential` 的 checkpoint。诊断只读取 coords，调用 `D.normalise` 时省略 norm，实际默认 max；构建 DCO 时又省略 head，并且前向不提供潜在 head 所需的 d_rel。

结果影响：rms 模型被用错误输入幅值推理；potential 模型可能加载成功却被解释成 direct 输出，得到向量势而非其 curl。坐标/网格误差曲线因此混入不同模型合同。旧默认 max/direct checkpoint 不受这两个特定触发条件影响，不能说所有旧坐标实验失效。

建议测试：同一个 checkpoint 用标准完整推理合同和本诊断推理比较；覆盖 rms/max 与 direct/potential 四种组合，明确旧元数据缺失时的默认值。NOT_RUN。

### X10 [P2] “梯度方差占比”算成奇异值占比，且遗漏物理间距

位置：[manifold_check.py:63](C:/PI-DON/scripts/exploratory/manifold_check.py:63)、[manifold_check.py:85](C:/PI-DON/scripts/exploratory/manifold_check.py:85)、[manifold_check.py:121](C:/PI-DON/scripts/exploratory/manifold_check.py:121)。

触发：任何非各向同性、非严格秩 1 的梯度矩阵；训练数据具有不同 dx/dy/dz 时还有间距影响。代码返回 `sv[0]/sum(sv)`，不是能量占比 `sv[0]^2/sum(sv^2)`，也没有去均值定义统计方差；`np.gradient` 使用默认单位索引间隔，build 返回的 D 被丢弃。

结果影响：奇异值 [3,1,1] 时当前定义为 3/5，平方能量定义为 9/11，虽两端极限一样，中间刻度并不一样。不同采样间距还会改变索引梯度方向性。旧 `fig7_manifold.png`/`manifold_check.npz` 可以保留为原定义的指标，不能沿用“物理梯度方差百分比”标题，也不能由此确定分布外就是唯一失败原因。

建议测试：已知奇异值的梯度矩阵、常量场、同一解析物理场在不同各向异性间距采样；明确使用未中心化能量还是中心化方差，并保存分母。NOT_RUN。

### X11 [P2] TE101 的有效波数指标分子少计一个零分量

位置：[diag_exp3.py:67](C:/PI-DON/scripts/exploratory/diag_exp3.py:67)、[diag_exp3.py:71](C:/PI-DON/scripts/exploratory/diag_exp3.py:71)、[diag_exp3.py:72](C:/PI-DON/scripts/exploratory/diag_exp3.py:72)。

触发：默认 clean TE101 对照。Em 的 mean 对三个 E 分量平均（两个为零），Cm 的 mean 只对两个非零 curl 分量平均，省掉了零 curl-y。另有前向差分去掉端面导致的支撑差异。

结果影响：仅分量归约就给 curl/E 的 RMS 比引入 sqrt(3/2) 因子；有限网格支撑还会叠加偏差。与下面腔体分支三分量对三分量的 `k_eff_d` 及打印的 theory 值口径不一致。这不证明 gauss/add 源非法，也不改变 c.step 的数值演化。

建议测试：同一 TE101 在各自 curl 支撑采样三分量解析 curl，包括零分量；清楚区分解析范数和有限差分范数，再验证网格细化趋向打印的理论值。NOT_RUN。

### X12 [P3] 人工扰动结果表用随机浮点误差查找对应运行

位置：[symplectic.py:188](C:/PI-DON/scripts/exploratory/symplectic.py:188)、[symplectic.py:205](C:/PI-DON/scripts/exploratory/symplectic.py:205)、[symplectic.py:210](C:/PI-DON/scripts/exploratory/symplectic.py:210)。

触发：`op_error(f)` 每次重新抽随机场，而 rows 未存 eps，仅以名称和误差相差 <1e-9 匹配。preserve 算子的误差依赖随机场，通常匹配不到；查找为空时输出却是 stable。

结果影响：把“未找到测量”显示为“测得稳定”。默认 preserve 小扰动可能确实稳定，不据此改写旧运行；但表格关联本身不可靠，换参数后会隐藏实测发散。其前面的直接 rollout 行不受这一查找 bug 影响。

建议测试：以 `(case,eps,n,dt,seed)` 唯一键保存/检索，同名不同 eps 和缺失记录应显示 NOT_RUN/INCOMPLETE；禁止靠随机指标值识别运行。NOT_RUN。

### X13 [P2] trunk_repair 保留了迁移前直接文件路径

位置：[trunk_repair.py:31](C:/PI-DON/scripts/experiments/trunk_repair.py:31)、[trunk_repair.py:35](C:/PI-DON/scripts/experiments/trunk_repair.py:35)、[trunk_repair.py:41](C:/PI-DON/scripts/experiments/trunk_repair.py:41)。

触发：在当前布局尝试将旧脚本直接作为新实验运行。读取旧 manifest 的 initial/model 路径后直接传给 `sha256`；源码快照更是 `shutil.copy2(name,...)`，没有调用 resolver。已只读确认根目录 `trunk_repair.py`、`coverage_ab.py`、`dco.py`、`fdtd.py` 不存在。

结果影响：现有固定 ROOT 的 `exist_ok=False` 会先挡住重跑；若给它移植新输出目录而未修输入路径，可能更早在原模型路径处失败，最迟在源码复制阶段失败。这个迁移后可用性问题不否定 lab #33 迁移前完成的 C200。旧 training_summary 记录 updates=200，optimizer min/max=200；本轮只读了记录和实际 helper 的预算核查，没有重新载入权重复核。

建议：将来获准重用时显式解析输入并以哈希校验身份，使用全新输出；预检所有依赖后再创建运行目录。注意 81-83 行异常收尾在“既存但尚无 summary”的 ROOT 上会重写 failure.json，应验证目录属于本次运行。建议测试：迁移布局的只读预检，以及预放旧 failure 的非本次目录应保持原字节。NOT_RUN。

### X14 [P2] 非 `.pt` 输出名可能让 JSON 直接覆盖刚保存的模型

位置：[train_pidon.py:352](C:/PI-DON/scripts/experiments/train_pidon.py:352)、[train_pidon.py:356](C:/PI-DON/scripts/experiments/train_pidon.py:356)、[adapt_dco_cavity.py:68](C:/PI-DON/scripts/experiments/adapt_dco_cavity.py:68)。

触发：`--out model.bin` 等不含字符串 `.pt` 的路径。`torch.save` 先保存模型，随后 `.replace('.pt','_hist.json')` 返回原路径，`open(...,'w')` 立即截断模型并写 JSON；含 `.pt` 的目录名也会被意外替换。

结果影响：一次训练看似成功，但最终模型丢失。已读历史命令使用 `.pt`，没有证据说明这次历史运行触发；封存挡住当前统一入口。问题属于未来移植前必须处理的产出保护。

建议测试：用纯路径计算覆盖 `.pt`、`.pth`、`.bin` 和父目录含 `.pt` 的场景，断言模型/历史路径必定不同且位于同一新运行目录；使用 `Path.with_name/with_suffix` 明确生成 sidecar。NOT_RUN。

## 控制与非问题边界

### C1 精确控制与零 curl 负对照没有冒充 DCO

[pidon_exact_control.py:69](C:/PI-DON/scripts/experiments/pidon_exact_control.py:69) 的 exact 分支有意复制当前 solver 自己的 Yee target；没有把独立参考场反馈给一个正式学习轨迹。zero/hard-source-only 分支有意强制产生负对照，FitRecord 的接受用于让它走到可测的传播错误，不是宣称学习损失达标。输出在 189、247 行明确 `control_only` / “not a DCO result”。

更新顺序沿用 Solver.step，并以 `reference.step_e_source_h` 比较（201 行）。wrong_h_half 则有意对比旧 H 半层，属于测量负对照。不能把它们列为“curl 偷换成精确结果”的生产科学 bug。

已读 [A2_exact_control.json](C:/PI-DON/evidence/gpt6_plan_v3/A2_exact_control.json) 保存：float64/float32 均 128 步、64 步恢复、uncovered=0；float64 最大相对误差 0，float32 为 2.8082817835e-6；hard-source-only 与 wrong-H-half 场门均 False。独立 [A2_zero_curl_negative.json](C:/PI-DON/evidence/gpt6_plan_v3/A2_zero_curl_negative.json) 的门为 False，negative_control_rejected=True。这些是已有控制证据，未在本轮重新执行。

仍须限定控制证明范围：`resume_after` 恢复的是 solver/reference/recorder，源循环、已有 rows 与累计最大误差仍在同一 Python 进程里（225-240 行），故只证明一次 checkpoint 状态往返，不能替代进程崩溃、未知尾部、旧快照恢复等测试。总报告 F06/F18/F19 的恢复问题不由这个控制 PASS 消除。函数也应将 steps<=0、无效 resume_after 作输入校验；当前零步会在 last_control_support/rows[-1] 处失败，列为接口完善建议，不影响旧 128 步控制。

排除的迁移疑点：`_copy_source_snapshot` 虽写 `ROOT/name`，但 ROOT 是 `project_paths.ROOT`；其 `_ProjectRoot.__truediv__` 实际调用旧名映射。映射包含这些源码，因此不能像 X13 一样报成根目录文件不存在。

### C2 curl、源和边界的静态核对结果

- `mini2d`、`symplectic`、`structured` 的二维 curl_E=(D_y^+ Ez,-D_x^+ Ez)，curl_H=D_x^- Hy-D_y^- Hx；H 减 curl_E、E 加 curl_H，符号自洽。`mini2d.div_2d` 使用前向差分，能在共同支撑上与 curl 抵消。没有将历史已修复的 backward-div 错误再报成当前 bug。
- `structured3d` 的 E 前向差分、H 后向差分及分量顺序与标准周期 Yee 约定一致；spectral 导数有方向半格相位。矩阵构造对其线性模型成立，不能因 X01 把所有显式矩阵诊断一并否定。
- `structured_pec.spaces/full_E` 去掉切向 E 边界，完整 H 保留；AH 与 AE.T 的比较是在明确的自由度空间中进行。CompT 的同尺寸零填充卷积和翻转核伴随、DeepT 的逆序伴随，从代码形式看合理。本轮未数值运行，不声称新伴随检验 PASS。
- `structured_cavity` 使用 H→E→硬源→PEC；精确控制使用 E→硬源→H。两者作为各自成套的交错时间约定可成立，不能仅按顺序不同判符号错误，也不能直接混用 H 时间层做精度比较。
- 周期 roll、材料块、随机 T、零源/错误半层这些都是明确诊断设置；未把“与论文腔体不同”本身列作计算 bug。

## 需收紧的解释与建议

### L1 不同机制不能合并成绩

`mini2d.py:171-189`、`spectral_dco.py:84-92` 运行的是冻结算子周期盒；`train_pidon.py:285-314` 用 exact rollout 的未来场做离线监督；`adapt_dco_cavity.py:23-45` 用 FDTD 快照监督。它们不是当前每个时间步先拟合本步目标再接受更新的机制。探索本身有价值，但 `mini2d.py:27-28`、“这就是论文时域训练”（`train_pidon.py:42-46`）及 `structured_scale.py:209-212/580-582` 的外推过强。应保留旧实验原标签，不以冻结失败否定完成问题训练后的冻结复用。

`structured_material.py:62-69` 明确实现了自己的正 eps 块及 invE，故总报告 F01 的 `PECCavity.eps_r` 被忽略不适用于这个独立矩阵实验。它是周期 n=6 块和任意线性 T，不是论文材料腔体精度复现。`structured_pec` 同样只验证结构与稳定性，不是训练好的 DCO。

### L2 稳定性保证还需要正谱、正确步长和足够数值证据

`structured.py:29-35` 的“实谱即可用有限步长稳定”缺少非负性；自由 symmetric taps 可以变成负滤波器。反例可直接令 S=-I：curl_H curl_E S 有负特征值，减小非零 dt 不能把该增长分支变成单位圆振荡。`symplectic.py:19-24/215-219` 又把当前符号约定下的 curl-curl 写成负半定，并忽略 CFL。代码中 curl_H 是 curl_E 的伴随，所以组成的是正半定算子。

`symplectic.blur` 的平均核也不一定正定：周期 Fourier 符号为 `(1+2cos(kx))(1+2cos(ky))/9`，可为负；但默认组合 `(1-a)I+a*blur` 的 a<=0.072 仍有正下界。需修解释，不能据此把默认 preserve 轨迹改成 FAIL。

`structured_deep.lmax_power`（164-185 行）与 `structured_cavity.cavity_lmax`（144-182 行）固定次数幂迭代可能低估最大值，0.99 系数不是通用误差证明；对 one-sided 非对称算子，实 Rayleigh 商更不构成稳定界。它们应保存收敛残差/可靠界。成对正半定情形和特意不稳定的 one-sided 反例须分开解释。

### L3 表达能力与离散无散性不要用有限训练/连续条件代替

`structured_scale.py:398-404/609-618` 把训练所得误差称为函数族最优误差的“下界”，方向相反：任何已取得的可行模型误差是最优训练误差的上界；有限 Adam 尚有优化误差，不能据“小改善”证明无限数据也无用。X05 进一步说明 deep 的有效宽度有限。

`structured3d.data:148-159` 令 E0 垂直连续 k，并在 E 节点采样，得到连续横向波；它不保证垂直于离散波数 `2 sin(kd/2)/d`。一般非轴向波的离散 div(E) 未必零。当前数据是有意的解析平面波，生成方法本身不判 bug；但 `structured3d.py:134-137` 和 `structured_scale.py:190-198` 的离散无散子空间解释不能不经验证就套给这些样本。

### L4 物理单位和源点观测

`structured_pec.py:117-143` 使用含 1/d 的 curl，但更新中没有 1/eps、1/mu，打印 `lim ... s` 实为规范化传播速度为 1 的时间尺度；对应 SI 真空秒数还应除以 c。该程序是矩阵演示，这不改变无量纲稳定比较，却不能把该数字当物理 CFL。

`structured_cavity.run_cavity:224-226` 只监测一个 Ez 探针判中止；默认探针不是源点，但其它分量或位置可先异常。未来完整六场验收应检查所有场有限性和源外误差，而不是把“探针未爆”当全场合格。`diag_exp3` 的一个 k_eff*d 也只是幅值尺度描述；它没有排除坐标、场形状、偏振和边界的影响。旧注释“只有这一个输入轴”和“所有以前结果必须不再引用”不应当作审查结论。

### L5 预算、重复性和输出保护

| 入口 | 当前记录/资源限制 | 对旧结果的解释与建议 |
|---|---|---|
| mini2d、structured | data 使用局部种子，但模型初始化/训练 shuffle 未完整固定全局 RNG；固定 `.npz` / `figs` 输出（mini2d:209/239，structured:244/295） | 默认 head/模型对比不是配对随机重复；不根据单次差异判普遍优越。将来用新运行目录，保存模型/配置/种子。 |
| structured_deep | 导入就设 float64 及 `cpu_count()-1` 线程（51-58）；训练只有 stdout，模型不落盘 | 不适合直接导入 CPU 并行审计环境。100 核机器可能抢资源。将全局设置移入受控入口，显式限线程/预算。 |
| structured_scale / structured_deep / structured_cavity | 大量稠密谱分析或固定幂迭代；深层/腔体调整 dt 后固定物理时长可增大步数 | 实验规模与精度预算应独立登记。不能拿相同步数直接比较不同 dt 的物理时长或成本。 |
| adapt_dco_cavity | warmup 参数在 28 行被无条件改成 45；n 可变但 dt 固定 3.075 ps；52 行固定覆盖 `evidence/cavity_adapt_data.npz` | 默认 n=31 不因 CFL 问题失效；n>=32 需独立 CFL 预检。保存实际 warmup/dt/source/样本合同，不仅 epochs。固定数据文件应改为新运行目录下产出。 |
| spectral_dco | 362-363 行输出默认同 checkpoint basename 的固定 JSON，未做存在保护 | 不同目录同名 checkpoint、不同 sweep 都可撞名。封存之外不具备历史不可覆盖保证。 |
| train_pidon / adapt | 固定 epoch/batch 循环，无完整 optimizer/RNG/消费预算快照；中途覆盖 a.out | 权重可作已完成训练的模型资产，不应据周期保存就宣布可无损恢复。训练/评估/失败成本分列；非有限 loss/梯度应中止并保存独立失败现场。 |
| trunk_repair | ROOT `exist_ok=False`；helper 验证恰为 200 Adam、冻结参数未变，且保存 optimizer | 这部分保护真实存在。内嵌 unittest 有临时模型更新，应单列测试成本，不能把正式更新数改成超过 200，也不能当无成本。 |

### L6 指标和实验标签

- `train_pidon.targets:238-249` 明确用“内核 Yee + 外壳解析”的混合靶，属于有意设计；不能报成误调用解析真值的 bug。但 `target=yee` 标签和最终全域分数应同时说明这层混合，尤其开启 div loss 时外壳不再保证离散 div=0。
- `train_pidon.evaluate:268-273` 在每个样本按输入幅值/网格尺度归一化后拼接求 relL2，不是物理量全样本拼接 relL2，更不是 Eq.(5) MRE。L_data 是平均相对平方误差，不能直接称 nMAE 或论文 loss。
- `adapt_dco_cavity` 训练集 loss 从 40.503 降至 0.1330316 的旧 JSON 可保留为训练损失；没有内部 held-out 划分，不能直接叫未见腔体泛化。E/H 两类目标压缩到共同 cube 的约定应随模型保存，不能只靠 `target=cavity-adapt` 推断。
- mini2d 的误差数组从一次更新后开始，却打印/绘图使用零基索引（203-206、231-237）；下一版应统一已完成更新数。NaN 不能通过 `err>threshold` 的 False 被解读为“从未超过”，也不应以所有 4000 步循环结束表示科学通过。

## 建议处理顺序

1. 先给 X01-X03 涉及的旧图表补充局限，保留原数和旧 FAIL；不要重跑旧脚本覆盖结果。
2. 获准后用独立小夹具验证 X04-X12，重点做坐标/半格、线性化、阈值与 NaN 的负面测试；本轮没有执行这些测试。
3. 只有确需重用某条探索线时，再修输出隔离、路径迁移、元数据与预算快照。它们不应挤占当前正式残差/场门和恢复合同的修复优先级。
4. 任何新科学实验需独立登记协议、预算和 evidence 目录；本文不批准新实验，不升级历史结论，也不改变 production。

## 审查源码指纹

以下为本轮只读取得的 SHA256，绑定本报告行号。它们是本次工作树字节，不能替代旧运行保存的源快照哈希；CRLF/LF 也会改变指纹。

```text
scripts/exploratory/diag_coords.py          5d0c036d601d102b78619b967f398c9a17187f0b045a77d7d7decd178b9dccaa
scripts/exploratory/diag_exp3.py            288a37ebf848ad451ea0bed71e3bb31e1c7a1ebe8624b21c9f5c0287e8cdbb06
scripts/exploratory/manifold_check.py       9e6d39942428046a66065fb12d6c33f5d57491af90ad88f248df27fe61759acb
scripts/exploratory/mini2d.py               0d3df8f5d9f961131732ae80bfc00889c67ebec0d77022e60c3c2578a7275d75
scripts/exploratory/structured_cavity.py    e43e100561de6794c9294ad324ec4b01421e968554fb479a00407b8673b0e074
scripts/exploratory/structured_deep.py      11f0ee7fa16c3d6a912f9a94d31f3a1e7fc95b7125870065589348d3698d692b
scripts/exploratory/structured_material.py  0f412765a3e427c8a187bc25bc5b0bd4069a95d12ba61ac50b1cbc7dca55a098
scripts/exploratory/structured_pec.py       7f008fe4aada4b06c7a9fdab1fa6f5a0c39c8e12d9c256891d4bd4f07a89291c
scripts/exploratory/structured_scale.py     f4994fec737f2b964d91c590aa8e6958859a0c060848e9340b7bb25e70bffa6f
scripts/exploratory/structured.py           c160293a70cfd782648b243a96152b38b7f3a1b2852a05c0d6b9f2f93fac1259
scripts/exploratory/structured3d.py         d3391db5b82c3fbbfe5453c7f721098f7e30e5f4a70a674db041b005024c0fd0
scripts/exploratory/symplectic.py           26d3b96c4a77641bb5381152d82ea1f35faf8bb8425dab6fd3cf07be0132c95c
scripts/experiments/spectral_dco.py         28986644e1782e7967986a470c683fd2eaf75cd0e780b5ab78f86db7c69b800b
scripts/experiments/train_pidon.py          0550ce03d5f0b2c103a3c836909cb98f9d46ff27a21be07f7f7d24da3284ff8c
scripts/experiments/adapt_dco_cavity.py      038fff85370142cdeff579a3b288835169f5210924888dad27e0ed5b88e210a5
scripts/experiments/pidon_exact_control.py  d3d4b655972be2a0e1317dee49977c2eb643b29b4c3572c06e523eebf0df41ed
scripts/experiments/a2_zero_curl_control.py 24588bb5f15cb9ecbc0062bc1f4c7d2b0ef411eb87a54caf54826056a5dfc634
scripts/experiments/trunk_repair.py         22dbc9b095d40c62e13757b97fd25ef78c7f7206d04d542f983edaeb08b15d1f
```
