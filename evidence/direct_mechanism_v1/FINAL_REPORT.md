# Final Report - Direct Mechanism v1

- Action: `A-20260914T181715-3bca00e1`; lab_run_id: `291`
- Conclusion: current evidence does **not** reproduce the PI-DON paper mechanism as a reliable field solver.
- Positive evidence: several DCO online arms can satisfy the registered residual gate for 128 steps.
- Negative/limiting evidence: 128-step field gates fail, S1 is incomplete, benefit fails, and long runs are not unlocked.

## Task Outcomes

| Task | Delivery | Scientific | Evidence |
|---|---|---|---|
| W0 | PASS | NOT_APPLICABLE | `evidence/workspace_reorganization_20260914/REPORT.md`, `evidence/workspace_reorganization_20260914/audit.json`, `evidence/workspace_reorganization_20260914/layout_validation.json` |
| M0 | PASS | NOT_APPLICABLE | `evidence/direct_mechanism_v1/m0/M0_REPORT.md`, `evidence/direct_mechanism_v1/m0/m0_audit.json`, `evidence/direct_mechanism_v1/manifest.json` |
| M1 | PASS | NOT_APPLICABLE | `evidence/direct_mechanism_v1/m1/M1_REPORT.md`, `evidence/direct_mechanism_v1/m1/m1_audit.json`, `evidence/direct_mechanism_v1/m1/m1_diagnostic.png` |
| M2 | PASS | RESIDUAL_128_PASS_FIELD_FAIL | `evidence/direct_mechanism_v1/M2_REPORT.md`, `evidence/direct_mechanism_v1/m2_audit.json`, `evidence/direct_mechanism_v1/runs/A_R/summary.json` |
| G128 | FAIL | FAIL | `evidence/direct_mechanism_v1/m2_audit.json` |
| S1 | INCOMPLETE | INCOMPLETE | `evidence/direct_mechanism_v1/s1_phase1/S1_REPORT.md`, `evidence/direct_mechanism_v1/s1_phase1/interrupted_audit.json`, `evidence/direct_mechanism_v1/s1_phase1/history.jsonl` |
| B | PASS | FAIL | `evidence/direct_mechanism_v1/benefit/B_REPORT.md`, `evidence/direct_mechanism_v1/benefit/B_audit.json`, `evidence/direct_mechanism_v1/benefit/B_R2/summary.json` |
| L1 | NOT_RUN | NOT_RUN |  |
| G1024 | NOT_RUN | NOT_RUN |  |
| L2 | NOT_RUN | NOT_RUN |  |
| U | NOT_RUN | NOT_RUN |  |
| V | PASS | FAIL | `evidence/direct_mechanism_v1/FINAL_REPORT.md`, `evidence/direct_mechanism_v1/FINAL_JUDGMENT.json` |

## Online Arms

| Arm | Status | Accepted | Adam | Closures | Elapsed s | H R | E R | Max effective nMAE | Probe valid/pass | Recovery |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| A-R | FAIL | 33 | 10228 | 1200 | 1142.8833609999856 | 9.967961762888484e-05 | 9.965224787875114e-05 | 6.496533195140788e-05 | 3/1 | False |
| A-P | PASS | 128 | 56680 | 0 | 4409.936257099966 | 8.691448396190442e-05 | 9.982332368004672e-05 | 0.051269250161268265 | 3/1 | False |
| B-R | PASS | 128 | 38127 | 0 | 2935.3384777000174 | 9.992266290590722e-05 | 9.968860361505215e-05 | 0.050785114883489905 | 3/1 | False |
| B-P | PASS | 128 | 44630 | 0 | 3502.87363690004 | 9.841101172563177e-05 | 9.943979027191016e-05 | 0.049254241513757416 | 3/1 | False |
| B-R2 | PASS | 128 | 37588 | 0 | 4759.5542747 | 9.778989283552609e-05 | 9.979193762074037e-05 | 0.04924114847047535 | 3/2 | False |

## Costs

- M2+B-R2 online Adam updates: `187253`; LBFGS closures: `1200`.
- S1 recorded before interruption: `23425` Adam updates.
- Relevant recorded lab wall time sum: `16784.0` seconds.

## Interpretation

- Strict residual evidence: A-P, B-R, B-P and B-R2 show that the current optimizer can force local residuals below the registered threshold for 128 steps.
- Field evidence: the residual-passing arms still have about five-percent component-scale field errors and source-outside waveform failures, so residual success did not translate into a reliable electromagnetic field.
- Phase-1 evidence: the full S1 attempt reached epoch 937 and best dev macro nMAE about 2.19%, but it lacks terminal state and blind migration testing; it is incomplete, not a pass or scientific fail.
- Benefit evidence: B-P did not save Adam updates relative to two random controls, and any cost comparison is not useful for the paper claim while field gates fail.
- Long-run evidence: no arm is qualified for 1024, 8192, or frozen reuse; those remain NOT_RUN by design.

## Research Judgment

当前证据支持：DCO在线每步拟合残差可以被优化到128步。但场误差、源外波形、第一阶段完整盲测和预训练收益均未过关或缺证据，所以不能说论文机制已复现，也不应在当前路线下启动1024/8192。

Practical next step, if continuing research: fix provenance/resume for S1 first, then investigate why residual-matched fields remain wrong. Do not spend compute on 1024/8192 under the current gates.

## Files

- Final audit JSON: `evidence/direct_mechanism_v1/FINAL_JUDGMENT.json`
- M2 audit: `evidence/direct_mechanism_v1/m2_audit.json`
- B audit: `evidence/direct_mechanism_v1/benefit/B_audit.json`
- S1 audit: `evidence/direct_mechanism_v1/s1_phase1/interrupted_audit.json`
