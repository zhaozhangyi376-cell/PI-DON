# N1 合同与恢复修复报告

- lab_log：#202
- C01–C15：**PASS**
- 正式 DCO 更新：0

| ID | 断言 | 回归测试 | 状态 |
|---|---|---|---|
| C01 | total physical R 严格小于门槛 | `test_component_loss_cannot_pass_when_physical_total_R_fails` | PASS |
| C02 | 仅完整零输入/零靶值走捷径 | `test_nonzero_irrotational_input_is_not_zero_shortcut` | PASS |
| C03 | H失败不改变E、源或H | `test_h_failure_does_not_advance_transaction` | PASS |
| C04 | E_pending不重复源或E更新 | `test_e_pending_resume_does_not_repeat_source_or_e_update` | PASS |
| C05 | Adam中断真实状态恢复一致 | `test_interrupted_adam_resume_matches_uninterrupted_trajectory` | PASS |
| C06 | LBFGS中断保存raw并回滚完整调用 | `test_lbfgs_budget_interrupt_restores_last_completed_call` | PASS |
| C07 | 耗尽预算/终态不可继续训练 | `test_exhausted_inner_budget_is_rejected_before_resume` | PASS |
| C08 | 非有限梯度/参数保留raw并回滚 | `test_nonfinite_parameter_after_step_is_raw_then_rolled_back` | PASS |
| C09 | schema、角色和冻结配置不合即拒绝 | `test_payload_schema_and_independent_run_identity_are_explicit` | PASS |
| C10 | 独立run UUID与稳定protocol hash分离 | `test_payload_schema_and_independent_run_identity_are_explicit` | PASS |
| C11 | JSONL后metadata崩溃扫描真实尾行 | `test_jsonl_commit_crash_recovers_unique_next_sequence_and_tail` | PASS |
| C12 | 截断、错序、重复和NaN JSONL拒绝 | `test_recorder_rejects_nonfinite_jsonl_constant_on_resume` | PASS |
| C13 | 两槽新指针失败时仍读回旧槽 | `test_rolling_checkpoint_pointer_keeps_prior_slot_if_new_pointer_fails` | PASS |
| C14 | failure_raw不改正式恢复指针且E用E尝试号 | `test_failure_raw_does_not_claim_a_recovery_checkpoint` | PASS |
| C15 | 持久deadline和任务累计额度不重置 | `test_training_stops_at_nine_and_a_half_hours` | PASS |
