# S1 Rerun Authorization Proposal

状态：PROPOSAL，未授权，未登记新行动，未消耗新预算。

## 为什么需要新授权

当前 `direct_mechanism_v1` 队列已经完成 M0/M1/M2/B/V 交付，但原始 goal 仍不能标记完成。唯一阻塞项是 S1 完整第一阶段训练：

- 计划要求：1000 epoch、25000 Adam 更新、保存 last/best、再做一次盲测和迁移网格评估。
- 实际证据：`evidence/direct_mechanism_v1/s1_phase1/history.jsonl` 只到 epoch 937、23425 更新。
- 缺失：`last.pt`、`summary.json`、`audit.json`、`blind_data/` 和盲测/迁移指标。
- 已保存的 `best.pt` 是 epoch 930 的开发集最优点，不是最新 epoch 937 状态。
- 从 `best.pt` 自动恢复会重复一段训练更新，改变原登记的 25000 更新成本；这会违反“旧失败不恢复重领预算”和“增加预算只能首次更新前登记独立新实验”的红线。

因此，不能把旧 S1 自动续跑成完整 S1；如果继续，必须由用户授权一个新的 S1 协议和预算。

## 建议的新实验身份

- 任务目的：补齐第一阶段完整训练与盲测证据，独立回答 DCO 是否学到可迁移解析旋度。
- 新目录：`evidence/direct_mechanism_v2_s1/`
- 新 harness 任务：建议新增 `S1R`，不要覆盖 `S1` 的 INCOMPLETE 结论。
- 新协议文件：可从本提案扩展成正式计划，例如 `docs/plans/2026-09-15-s1-rerun.md`。
- 新行动：必须先 `project_harness start S1R ...`，再通过 `lab_log.py run` 包正式训练。

## 推荐固定配置

保持原 S1 科学配方不变，只修恢复和终止记录：

- 数据：1000 个 32^3 解析平面波叠加，seed `2026091701`，前 800 训练、后 200 开发。
- 盲测：seed `2026091702` 的 16 个样本；只在训练终止后评估一次。
- 网络：L4/base32，cellsize/RMS，解析标签，rel 损失。
- 优化：Adam，初始 lr `1e-4`，cosine 到 `2e-6`。
- 更新：1000 epoch，每 epoch 恰 25 次 optimizer.step，总上限 25000 Adam。
- batch：等效 batch 32；microbatch 4，若预检 OOM 才允许 microbatch 2。
- 验证：每 10 epoch 开发集验证，按开发宏 nMAE 最低选 best；同分取早。
- 盲测门槛：逐样本三分量宏 nMAE ≤ 1%，整体 curl 相对 L2 样本 90 分位 ≤ 5%；立方和迁移网格分别判。
- 指标：MRE Eq.(5)、nMAE、relative L2、近零点贡献、每分量绝对误差和参考峰值分列。

## 必须新增的工程保护

为避免再次出现 epoch 937 无法恢复的情况，新的 S1 runner 必须在正式训练前具备：

- 每 10 epoch 保存一个可生产恢复 checkpoint，至少包括 net、optimizer、scheduler、RNG、epoch、updates、best、history。
- `last.pt` 每个 epoch 或每 10 epoch 原子写；训练完成后另写 `terminal.pt` 或明确 `last.pt` 为终止态。
- `summary.json` 在正常完成、资源截断、异常退出时都必须写入；异常也要写 `status=EXCEPTION`。
- `interrupted_audit` 不应替代 `summary.json`；它只用于事后核查。
- `lab_log` 记录如果进程断开但文件未终止，必须保留为工程 INCOMPLETE，不能用 best 直接补盲测。

## 授权后预期状态变化

如果新 S1R 完整运行：

- S1R delivery PASS；科学 PASS/FAIL 由盲测门槛决定。
- 原 S1 保持 INCOMPLETE，不改判。
- 若 S1R 科学 PASS，才可讨论是否需要 P-new 128 配对；若科学 FAIL，也不改判已有 M2/G128/B。
- goal completion audit 可重新运行；如果仍无其他阻塞，才可考虑 goal complete。

## 不建议做的事

- 不要从 `evidence/direct_mechanism_v1/s1_phase1/best.pt` 继续原 S1。
- 不要直接对 epoch 930 best 做盲测并称作完整 S1。
- 不要把开发集 `0.021945` 宏 nMAE 当盲测成绩。
- 不要为了补齐 1575 更新而忽略缺失的 optimizer/RNG/last state。
- 不要把新 S1R 的结果写回旧 `direct_mechanism_v1/s1_phase1/`。
