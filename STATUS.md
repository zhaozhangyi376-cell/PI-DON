# STATUS — 当前复现进度快照

更新：2026-09-17。旧配方长程训练继续暂停；用户批准并行推进算子/PEC审计、详细汇报和独立论文显式配置第一阶段参考。当前总计划 [PLAN](PLAN.md)，上一版快照在 `evidence/server_resource_v1/dco_value_review_20260916_r2/STATUS_before.md`。

## 当前结论

汇报前方向已收敛：[差异理由、PEC核对与工作包](docs/reports/2026-09-16-fidelity-boundary-and-briefing-plan.md)。固定权重算子审计已完成：旧`dco_lr1e3_300.pt`在重构Fig.5上的宏nMAE为0.312%，固定随机网络为21.332%，误差约相差68.4倍，证明旧DCO学到了非平凡旋度映射；但旧DCO在首个非零腔体E输入上的global relL2为7.12，显示从平面波训练分布到在线腔体状态的严重迁移失配。S1R权重未在本地，报告只列服务器原始指标，不伪造其场图。

PEC计算图审计已完成：生产`apply_pec`对Ex/Ey/Ez的切向边界掩膜与预期一致，预测插入也清零对应法向curl面；但玩具自动微分表明，loss前边界置零与更新后硬投影的边界梯度支撑不同，因此当前实现不能宣称与论文PEC路径等价。作者的具体张量错位与mask细节仍未公开。

汇报交付已完成：`汇报素材/PI-DON导师汇报_20260917_r3.pptx`共44页，配套逐页讲稿、Q&A和缩略总览；44页全部渲染且无几何溢出。用户已要求PPT终稿暂停，r3/r4只作为素材底稿，后续等用户写出自己的理解后再收敛成短汇报。独立`_01`论文显式第一阶段参考线已回传审计：1000样本、25000 Adam、恒定1e-4、等效batch32、fresh随机初始化和本地R1合同均核对通过；但科学门FAIL，开发集宏nMAE=9.2334%，relL2 p90=57.9028%，Eq.(5) MRE均值=2.0180，三项登记门均未过。随后PAPER01-DIAG以0参数更新分解了200个保留样本：最后5000更新test MSE仅下降2.42%，curl-z平均nMAE=13.25%显著高于curl-x 7.49%和curl-y 6.96%，`abs(cos theta)<0.25`组宏nMAE最高为13.45%。PAPER01-DATA-AUDIT进一步确认`k dot E0`横向条件满足到机器精度（相对最大≤1.23e-16），因此失败不能归因于平面波不横向；但Eq.(4)导致Ez放大比p90=3.09、最大=7.89，近奇异角组Ez放大均值=4.54且宏nMAE最高。原样延长训练优先级低；若重训，应先做角度/幅值/归一化的小型消融，不解锁第二阶段、1024或8192。

随机128已审核：服务器lab313，行动A-20260916T131636-74a4f0e0，交付PASS、科学FAIL。128步、159240 Adam、6837.28秒；Q=3.1335%，Ex/Ey nMAE=1.7801%/1.7705%。预训练128为261209 Adam、11074.07秒、Q=3.0811%，Ex/Ey=1.5486%/1.6308%。两组同在69步首次分量门失败；随机组更新少39.04%、时间少38.26%，但均未通过最终场门，不作合格求解的加速认证。

本地lab298（0更新）核对随机22项产出哈希，重算两组32/64/128快照指标一致，核心源码哈希相同，冻结配置仅init不同。此前两次本地审计尝试lab296/297因异类账本事件、CRLF/LF字节差异退出，均0更新，现场保留。指标源文件换成LF后与服务器哈希精确一致，并另存验证副本。

当前P实际使用旧300轮DCO，非S1R。S1R也不是逐细节论文复现：使用cellsize输入、RMS归一化、余弦调度。首个相同E目标上P初始R=50.6929、6647更新过门；随机R=1.0352、891更新过门，支持当前输入上的不利迁移迹象。随机组仍有完整DCO网络，只省去预训练。新训练暂停；1024/8192不启动。详见[数值审计](evidence/server_resource_v1/dco_value_review_20260916_r2/REPORT.md)和[方法回顾](docs/reports/2026-09-16-dco-value-retrospective.md)。

## 前序证据背景

服务器已完成一次1000轮、25000 Adam更新的S1R第一阶段训练。SR-COMPARE回传后，本地已核对S1R的history/summary/audit/stage、best/last、lab hash和checkpoint update计数：交付PASS、科学FAIL。旧S1中断保持INCOMPLETE，S1R禁止原样重复启动。

第二阶段A-P/B-R/B-P/B-R2已有128残差接受证据；原G128场门FAIL、B收益FAIL保留。服务器第二批TOL1E5-P有效重试R2已回传：第一个E_pending用满3000 Adam后残差比为1.635e-5，未过1e-5，0个完整接受步。SR-FAIL-AUDIT已确认这个首个E目标与A-P首步目标身份匹配，首步失败不像是target_ss记录错位；同时旧128残差臂在57–58步Q越线、66步有效分量nMAE越线。SR-E1-BUDGET回传PASS：同一首个E目标在3769 Adam达到1e-5。SR-MICRO4回传PASS_MICRO：4个完整严格步通过；SR-MICRO16回传PASS_MICRO：16个完整严格步通过。SR-64回传FAIL：35个完整严格步通过，第36步E_pending在9000 Adam后残差仍为3.4467e-5。低学习率分支随后完成clean low-lr64并通过64步场门；clean low-lr128完成128步、64步场门仍通过，但128步场门FAIL：Q=3.0811%仍低于5%，Ex/Ey nMAE分别为1.5486%/1.6308%，首次分量门失败在第69步。论文式`1e-4`残差诊断SR-128-PAPER-TOL-DIAG在64步即场门FAIL，Q=9.041%，说明当前实现不能直接放宽回`1e-4`换取长程速度。随机初始化同规则SR-64-LOWLR-RANDOM也通过64步场门，Q=2.932%，且Adam=84,881低于预训练clean64的178,204；因此当前低学习率64步证据不支持预训练节省成本。因此1024/8192及合格问题训练后的冻结复用仍NOT_RUN。

## S1R 已报告结果

来源：用户上传 `pasted-text.txt`；服务器行动 `A-20260915T054513-93c57d73`，服务器lab run295。原始服务器目录 `H:/PI-DON/evidence/direct_mechanism_v2/s1r_phase1_server/`。

| 项目 | 结果 |
|---|---|
| 完整训练 | 1000 epoch，25000 Adam；约11192.58秒 |
| 开发集best | epoch970 / 24250更新；宏nMAE 0.0218643664，relL2 p90 0.0548391830，Eq5 MRE 1.7609199892 |
| 32³已见盲测 | 宏nMAE 0.0415034389；relL2 p90 0.0441235151；Eq5 MRE 1.0532566943 |
| 64³ | 宏nMAE 0.1144133828；relL2 p90 0.1314913762；Eq5 MRE 1.4773699253 |
| 64×96×16 | 宏nMAE 0.2313270163；relL2 p90 0.4440007878；Eq5 MRE 3.3278654702 |
| 32×64×16 | 宏nMAE 0.1777178291；relL2 p90 0.3709995404；Eq5 MRE 4.0044096227 |

以上指标来自同一份摘要，但不能与旧global nMAE直接互比。S1R重测集合已暴露，后续只作诊断；不能再次用于新训练选模后称盲测。

## 本次已核对的源码限制

- S1原计划文字为“逐样本三分量宏nMAE≤1%”，当前代码使用“样本宏nMAE的均值≤1%”。新报告同时列两种归约；不能用较宽判据升级旧失败。
- S1保存了全局RNG，没有保存用于randperm的独立torch.Generator状态。summary中的recovery_eligible=True不足以认证精确续跑；完成旧25000预算也不产生追加资格。
- 原M2审计field_gate_pass没有覆盖全部Q/弱分量检查；当前时刻弱参考标志也不等于登记的全时长固定参考规则。
- M2运行器保存64快照，但未在该节点执行完整场门停止逻辑。已有128轨迹不能未经审核称为“按全部检查点合同合格”。
- 上述问题不改变旧FAIL；新正式实验须先把测量/恢复合同补齐，避免靠旧布尔字段解锁长程。

## 本批进度

| ID | 状态 | 下一步 |
|---|---|---|
| SR-LOCAL | PASS（本地#293），0更新 | 摘要分解与五臂成本核对完成；初次float64参考读回仅作诊断 |
| SR-READBACK | PASS（本地#294），0更新 | 恢复原测量的float32参考转换后，8个里程碑读回指标全部一致 |
| SR-COMPARE | PASS（服务器#296），0更新 | S1R完整性审计PASS；旧lr1e3在同题四网格均优于S1R |
| SR-PERF | PASS（服务器#297），15临时Adam | microbatch=8最快；4/8/16首步等价均通过 |
| SR-DESIGN | PASS | 冻结第二批唯一在线干预TOL1E5-P；不重复S1R，不启动长程 |
| SR-SHORT | FAIL（服务器#300），3000 Adam | 旧lr1e3初始化、tol=1e-5；第一个E_pending未过门，0个完整接受步；不进入64/128 |
| SR-FAIL-AUDIT | PASS（本地#295），0更新 | 同一首个E目标1e-4可过、1e-5卡住；旧128残差臂场误差在57–66步越线 |
| SR-E1-BUDGET | PASS（服务器#301），3769 Adam | 同一首个E目标在9000上限内达到1e-5；诊断PASS，不是连续轨迹PASS |
| SR-MICRO4 | PASS（服务器#302），10558 Adam | 4个完整严格步和第4步微型场门通过；不是64/128通过 |
| SR-MICRO16 | PASS（服务器#303），13791 Adam | 16个完整严格步和第16步微型场门通过；不是64/128通过 |
| SR-64 | FAIL（服务器#304），33896 Adam | 35步通过；第36步E半步拟合失败，E残差3.4467e-5；未到57/58旧场门瓶颈 |
| SR-64-LOWLR-CLEAN | PASS，178204 Adam | 从0开始低学习率64步通过；64步Q=2.934%，六分量门通过 |
| SR-128-LOWLR-CLEAN | 交付PASS / 科学FAIL，261209 Adam | 从0开始低学习率128步完成；64步场门通过；128步Q=3.081%，但Ex/Ey nMAE=1.5486%/1.6308%，第69步首次分量门失败 |
| SR-128-PAPER-TOL-DIAG | FAIL，66173 Adam | 项目`R<1e-4`诊断到64步停止；64步Q=9.041%；未确认该R等于论文loss |
| SR-64-LOWLR-RANDOM | PASS，84881 Adam | 同clean64规则通过64步；成本低于预训练clean64；该配方未支持预训练成本收益 |
| SR-128-LOWLR-RANDOM | 交付PASS / 科学FAIL，159240 Adam | 128步Q=3.1335%；Ex/Ey=1.7801%/1.7705%；不进入1024 |
| SR-DCO-REVIEW | 审计PASS，本地lab298，0更新 | 完成证据回顾和论文实现对照；按用户要求暂停新训练 |
| BRIEF-OP | INCOMPLETE，本地lab299，0更新 | 首次聚合遇到零参考分量空值；现场保留，不改判 |
| BRIEF-OP-R1 | 诊断PASS，本地lab300，0更新 | 旧DCO Fig.5宏nMAE 0.312%，固定随机21.332%；首个腔体E暴露分布迁移失配 |
| BRIEF-PEC | 诊断PASS，本地lab301，0更新 | PEC掩膜正确；硬投影与loss前置零的梯度路径不同，尚非作者等价实现 |
| BRIEF-DECK | PASS | 44页PPT、逐页讲稿、Q&A和总览图完成，44/44渲染无溢出 |
| PAPER01-PREFLIGHT | PASS，本地lab302，2 Adam | 独立`_01`的恒定1e-4、等效batch、fresh目录和证据写入通过；不计科学成绩 |
| PAPER01-PREFLIGHT-R1 | PASS，本地lab303，2 Adam | 修正忠实度分类和Eq.(4)幅值构造后重新预检；合同哈希`370a93df...`，不计科学成绩 |
| PAPER01-S1 | 交付PASS / 科学FAIL | 服务器完整25000 Adam；合同、history、checkpoint哈希均通过；宏nMAE=9.2334%，relL2 p90=57.9028%，Eq.(5) MRE=2.0180，三项登记门均失败 |
| PAPER01-DIAG | 诊断PASS，本地lab304，0更新 | 后5000更新test MSE仅降2.42%；curl-z为主导误差；近奇异角`abs(cos theta)<0.25`组最差；原样重训优先级低 |
| PAPER01-DATA-AUDIT | 诊断PASS，本地lab305，0更新 | `k dot E0`相对最大≤1.23e-16；Ez放大p90=3.09、最大=7.89；近奇异角组Ez放大均值=4.54且宏nMAE最高 |
| PAPER01-ABLATION-SMOKE | READY，服务器包已生成 | `server_paper01_ablation_bundle.zip`及`.sha256`；SHA256 `19A6B42640055937CFB92409D6AA0D93EFEF3626D4139B80D5B8F32FB02BFD87`；四臂各2000 Adam，比较baseline、theta_min_0p5、ez_cap3、projected_amp短训趋势；执行说明见[服务器消融指南](docs/guides/PAPER01_ABLATION_SERVER.md) |
| SR-S1/SR-G128 | BLOCKED | SR-S1本批不消耗；SR-G128需新64/128场门证据后再审 |
| L1/G1024/L2/U | NOT_RUN | 无新合格128轨迹，不启动1024/8192 |

首批服务器执行包只安装本轮新任务，不覆盖服务器actions或records。本地和服务器lab run数字可能重复，以主机+行动ID+lab_run_id联合追溯。

本批已执行依据：[精度对齐复核JSON](evidence/server_resource_v1/local_review_v2/review.json)、[中文报告](evidence/server_resource_v1/local_review_v2/REPORT.md)、[场误差曲线](evidence/server_resource_v1/local_review_v2/field_timeline.png)、[SR-SHORT-R2回传审计](evidence/server_resource_v1/batch2_return_review.md)、[SR-FAIL-AUDIT报告](evidence/server_resource_v1/failure_mechanism_audit/REPORT.md)、[SR-E1-BUDGET回传审计](evidence/server_resource_v1/first_e_return_review.md)、[SR-MICRO4回传审计](evidence/server_resource_v1/micro4_return_review.md)、[SR-MICRO16回传审计](evidence/server_resource_v1/micro16_return_review.md)、[SR-64回传审计](evidence/server_resource_v1/strict64_return_review.md)、[clean low-lr64回传审计](evidence/server_resource_v1/clean_low_lr64_return_review.md)、[clean low-lr128回传审计](evidence/server_resource_v1/clean_low_lr128_return_review.md)、[论文阈值诊断回传审计](evidence/server_resource_v1/paper_tol128_return_review.md)、[随机低学习率64对照审计](evidence/server_resource_v1/random_low_lr64_return_review.md)。两次原始源码/输入哈希分别随现场保存。SR-READBACK行动为A-20260915T093341-03844084；SR-SHORT-R2行动为A-20260915T102902-9b618d25；SR-FAIL-AUDIT行动为A-20260915T142904-a8ebc3e9；SR-E1-BUDGET行动为A-20260915T144224-63c5e568；SR-MICRO4行动为A-20260915T150454-54384222；SR-MICRO16行动为A-20260915T153241-a20321cd；SR-64行动为A-20260915T155212-d9c7d617。

已知观察：五臂JSONL更新/closure/提交成本均与summary一致；四条旧128残差轨迹当前Q在第57–58步超过5%，有效分量nMAE在第66步超过1%；S1R的32³已见测试仅1/16样本宏nMAE≤1%，最差样本占宏误差和52.71%。服务器同题诊断显示旧`dco_lr1e3_300.pt`优于S1R_best。更严格单步残差门已被R2否定：不是“门槛再严一点就能自然变好”。SR-E1-BUDGET把首个E从3000 Adam失败推进到3769 Adam过1e-5；SR-MICRO4到4步且Q=0.2916%；SR-MICRO16到16步且Q=0.3006%；SR-64未到旧57–58步场门瓶颈，在第36步E半步拟合失败。低学习率clean64首次给出合格64步场证据；clean128说明总Q可压在5%内，但Ex/Ey分量误差在第69步后超过1%，所以仍不启动1024/8192。论文式`1e-4`残差门在64步Q=9.041%而失败，说明不能靠放宽残差门换长程速度。随机初始化同规则64步对照PASS_64且成本更低，说明clean64成功不依赖预训练，当前配方下预训练收益为负。PAPER01数据合同审计显示Eq.(4)横向性自洽，但近奇异角带来强Ez放大并对应较高宏误差；下一步若继续第一阶段，应登记小型角度/幅值/归一化消融，而不是继续启动长程。

## 历史证据保留

- [M2原始审计](evidence/direct_mechanism_v1/m2_audit.json)：A-R接受33步后失败；A-P/B-R/B-P完成128残差但场门失败。
- [B收益审计](evidence/direct_mechanism_v1/benefit/B_audit.json)：B-P未相对两个随机对照同时节省Adam和时间，且场门失败。
- [旧S1中断审计](evidence/direct_mechanism_v1/s1_phase1/interrupted_audit.json)：937轮/23425更新，无终止last/盲测；best不能替代末状态恢复。
- [历史成本复核](evidence/workspace_reorganization_20260914/INDEPENDENT_AUDIT.md)：1h精确总数UNKNOWN、下界35122；2h新更新4719；S-P-retry恢复未认证。
- [原研究判断](evidence/direct_mechanism_v1/FINAL_REPORT.md)：当时证据不足以直接长程推进；新服务器资源改变可执行条件，不会自动改变科学结论。
