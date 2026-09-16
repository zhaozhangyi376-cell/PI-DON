# STATUS — 当前复现进度快照

更新：2026-09-15。当前总计划 [PLAN](PLAN.md)，首批执行细则 [服务器资源协议](docs/plans/2026-09-15-server-resource-protocol.md)。上一版快照在 `evidence/server_resource_v1/before/`。

## 当前结论

服务器已完成一次1000轮、25000 Adam更新的S1R第一阶段训练。SR-COMPARE回传后，本地已核对S1R的history/summary/audit/stage、best/last、lab hash和checkpoint update计数：交付PASS、科学FAIL。旧S1中断保持INCOMPLETE，S1R禁止原样重复启动。

第二阶段A-P/B-R/B-P/B-R2已有128残差接受证据；原G128场门FAIL、B收益FAIL保留。服务器第二批TOL1E5-P有效重试R2已回传：第一个E_pending用满3000 Adam后残差比为1.635e-5，未过1e-5，0个完整接受步。SR-FAIL-AUDIT已确认这个首个E目标与A-P首步目标身份匹配，首步失败不像是target_ss记录错位；同时旧128残差臂在57–58步Q越线、66步有效分量nMAE越线。SR-E1-BUDGET回传PASS：同一首个E目标在3769 Adam达到1e-5。SR-MICRO4回传PASS_MICRO：4个完整严格步通过；SR-MICRO16回传PASS_MICRO：16个完整严格步通过。SR-64回传FAIL：35个完整严格步通过，第35步Q=0.2104%、场仍健康，但第36步E_pending在9000 Adam后残差仍为3.4467e-5，未过1e-5。因此64/128认证仍失败，1024/8192及合格问题训练后的冻结复用仍NOT_RUN。

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
| SR-S1/SR-G128 | BLOCKED | SR-S1本批不消耗；SR-G128需新64/128场门证据后再审 |
| L1/G1024/L2/U | NOT_RUN | 无新合格128轨迹，不启动1024/8192 |

首批服务器执行包只安装本轮新任务，不覆盖服务器actions或records。本地和服务器lab run数字可能重复，以主机+行动ID+lab_run_id联合追溯。

本批已执行依据：[精度对齐复核JSON](evidence/server_resource_v1/local_review_v2/review.json)、[中文报告](evidence/server_resource_v1/local_review_v2/REPORT.md)、[场误差曲线](evidence/server_resource_v1/local_review_v2/field_timeline.png)、[SR-SHORT-R2回传审计](evidence/server_resource_v1/batch2_return_review.md)、[SR-FAIL-AUDIT报告](evidence/server_resource_v1/failure_mechanism_audit/REPORT.md)、[SR-E1-BUDGET回传审计](evidence/server_resource_v1/first_e_return_review.md)、[SR-MICRO4回传审计](evidence/server_resource_v1/micro4_return_review.md)、[SR-MICRO16回传审计](evidence/server_resource_v1/micro16_return_review.md)、[SR-64回传审计](evidence/server_resource_v1/strict64_return_review.md)。两次原始源码/输入哈希分别随现场保存。SR-READBACK行动为A-20260915T093341-03844084；SR-SHORT-R2行动为A-20260915T102902-9b618d25；SR-FAIL-AUDIT行动为A-20260915T142904-a8ebc3e9；SR-E1-BUDGET行动为A-20260915T144224-63c5e568；SR-MICRO4行动为A-20260915T150454-54384222；SR-MICRO16行动为A-20260915T153241-a20321cd；SR-64行动为A-20260915T155212-d9c7d617。

已知观察：五臂JSONL更新/closure/提交成本均与summary一致；四条128轨迹当前Q在第57–58步超过5%，有效分量nMAE在第66步超过1%；S1R的32³已见测试仅1/16样本宏nMAE≤1%，最差样本占宏误差和52.71%。服务器同题诊断显示旧`dco_lr1e3_300.pt`优于S1R_best。更严格单步残差门已被R2否定：不是“门槛再严一点就能自然变好”。SR-E1-BUDGET把首个E从3000 Adam失败推进到3769 Adam过1e-5；SR-MICRO4到4步且Q=0.2916%；SR-MICRO16到16步且Q=0.3006%；SR-64未到旧57–58步场门瓶颈，在第36步E半步拟合失败。下一步应做第36步E失败诊断，而不是启动128/1024/8192或修改门槛重跑64。

## 历史证据保留

- [M2原始审计](evidence/direct_mechanism_v1/m2_audit.json)：A-R接受33步后失败；A-P/B-R/B-P完成128残差但场门失败。
- [B收益审计](evidence/direct_mechanism_v1/benefit/B_audit.json)：B-P未相对两个随机对照同时节省Adam和时间，且场门失败。
- [旧S1中断审计](evidence/direct_mechanism_v1/s1_phase1/interrupted_audit.json)：937轮/23425更新，无终止last/盲测；best不能替代末状态恢复。
- [历史成本复核](evidence/workspace_reorganization_20260914/INDEPENDENT_AUDIT.md)：1h精确总数UNKNOWN、下界35122；2h新更新4719；S-P-retry恢复未认证。
- [原研究判断](evidence/direct_mechanism_v1/FINAL_REPORT.md)：当时证据不足以直接长程推进；新服务器资源改变可执行条件，不会自动改变科学结论。
