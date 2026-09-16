# A1 工程合同修复报告

本报告由机器运行测试生成，不能作为 DCO 收敛或 G0 通过的替代证据。

- lab_log：#164
- 测试：54 项；失败 0 项；错误 0 项
- 结论：**PASS**（仅 A1 工程合同）

已覆盖累计时间预算、LBFGS 配置冻结、运行身份、Adam/LBFGS 完整调用边界的中断恢复、E_pending 事务、非有限 raw/safe、原子检查点、写入失败及 JSONL 未提交尾部分类。每个测试的 observed/expected 及源码哈希在 `contract_test_results.json`。

v2 的 `adam200_final.pt` 与 `adam200_lbfgs_final.pt` 保留不改；两者均标记为 `diagnostic_only_not_resumable_v3`，不会作为 v3 恢复入口或重新领取优化预算。
