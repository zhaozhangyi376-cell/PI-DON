# 服务器第二批最小干预协议

Goal：在不放宽旧门槛、不恢复旧失败预算的前提下，区分第二阶段场失败是否主要来自每步残差门过松造成的时间积累误差。

Scope：本批只启动一个在线短程干预 `SR-SHORT/TOL1E5-P`。第一阶段S1R已经审计完整但科学FAIL；旧 `dco_lr1e3_300.pt` 在同题诊断上优于S1R，且旧M2已经使用该权重作为预训练初始化。因此本批不重复训练S1，不启动1024/8192。

## 冻结配置

脚本：`scripts/experiments/server_short_tol_probe.py`

输出：`evidence/server_resource_v1/short_tol_probe`

初始化：`assets/models/dco_lr1e3_300.pt`，保持原始权重不变。

物理和网络：n=31、side=0.05m、dt=3.075e-12s、L4/base32、direct/cellsize/RMS、float32、独立E/H网络、h_shift=True、h_scale=1、h_output_scale=1、grad_clip=0、component_rel=False、strict_stop=True、硬源、fmax=15GHz。

优化：Adam lr=3e-4、reset_opt_each_step=True、LBFGS closures=0、per_fit_cap=3000、累计Adam cap=150000。

关键干预：`tol=1e-5`，相对目标SSE规则不变。旧M2的 `tol=1e-4` 结果只作历史对照，不重跑旧臂。

步数：先到64个完整严格接受步。只有64步场门通过，才在同一行动、同一累计预算语义下继续到128。64步不通过或资源截断时停止，不启动1024/8192。

## 成功、失败和资源状态

交付PASS：脚本完成、保存steps.jsonl、summary.json、REPORT.md、checkpoint/failure现场，且至少有明确状态。

科学PASS_64：64步完整接受，且64步场门全部通过。

科学FAIL：残差拟合失败、64步前资源耗尽、64步场门失败，或只完成残差而全场/探针不满足。

RESOURCE_LIMIT：累计Adam达到150000、单步cap耗尽导致未通过，或可证明GPU/保存资源截断。保留failure_raw/rolling checkpoint/summary，不恢复重领预算。

## 场门

64步场门使用脚本保存的同一步参考场复算：

- global_weighted_relative_l2 <= 0.05
- fixed_amplitude_error <= 1e-3
- 六分量中非弱参考分量 nMAE <= 0.01
- 弱参考分量必须满足已登记 weak_absolute_pass
- 源点和源外探针保存为诊断证据；源点硬赋值不单独证明成功

这不是旧G128改判。旧A-P/B-R/B-P/B-R2的128场门FAIL保持不变。

## 解释

若TOL1E5-P在64步通过，说明旧`1e-4`残差门可能过松，下一步才可登记SR-G128复核。若64步仍失败，优先结论是场误差不是单靠更严单步残差门能解决，后续应回到接口/边界/训练分布诊断，而不是加长步数。

