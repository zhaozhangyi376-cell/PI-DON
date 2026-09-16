# N2 完整 G0 数值认证

- 合同回归 lab_log：#195
- G0：**PASS**

精确 Yee 控制的 `control_only=true`；它们只认证测量与恢复链路，不能计为 DCO 成绩。

| ID | 状态 | 观测 |
|---|---|---|
| C01 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C02 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C03 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C04 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C05 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C06 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C07 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C08 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C09 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C10 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C11 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C12 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C13 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C14 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| C15 | PASS | `{"present": true, "lab_run": 190, "contract_status": "PASS"}` |
| M06 | PASS | `{"rows": 128, "step_sequence_ok": true, "accepted_rows": true, "six_components": true, "metric_fields": true, "finite": true, "max_Q": 0.0, "max_A_fixed": 0.0, "max_probe_abs": 0.0, "threshold": 1e-10, "numeric_ok": true, "restored_at": 64, "control_only": true, "reference_dtype": "float64", "identity_and_jsonl_integrity": true}` |
| M07 | PASS | `{"rows": 128, "step_sequence_ok": true, "accepted_rows": true, "six_components": true, "metric_fields": true, "finite": true, "max_Q": 2.808238397995293e-06, "max_A_fixed": 9.224699420841925e-10, "max_probe_abs": 8.429448684259353e-09, "threshold": 0.0001, "numeric_ok": true, "restored_at": 64, "control_only": true, "reference_dtype": "float64", "identity_and_jsonl_integrity": true}` |
| M08 | PASS | `{"rows": 128, "step_sequence_ok": true, "accepted_rows": true, "six_components": true, "metric_fields": true, "finite": true, "max_Q": 1.0, "max_A_fixed": 0.0035078173165410697, "max_probe_abs": 0.0017929709732387624, "threshold": 1e-10, "numeric_ok": false, "restored_at": null, "control_only": true, "reference_dtype": "float64", "identity_and_jsonl_integrity": true}` |
| M09 | PASS | `{"rows": 128, "step_sequence_ok": true, "accepted_rows": true, "six_components": true, "metric_fields": true, "finite": true, "max_Q": 1.0, "max_A_fixed": 0.0035078173165410697, "max_probe_abs": 0.0017929709732387624, "threshold": 1e-10, "numeric_ok": false, "restored_at": null, "control_only": true, "reference_dtype": "float64", "identity_and_jsonl_integrity": true}` |
| M10 | PASS | `{"rows": 128, "step_sequence_ok": true, "accepted_rows": true, "six_components": true, "metric_fields": true, "finite": false, "max_Q": null, "max_A_fixed": null, "max_probe_abs": null, "threshold": 1e-10, "numeric_ok": false, "restored_at": null, "control_only": true, "reference_dtype": "float64", "identity_and_jsonl_integrity": true}` |
| M01 | PASS | `{"lab_run": 195, "valid_lab_record": true}` |
| M02 | PASS | `{"lab_run": 195, "valid_lab_record": true}` |
| M03 | PASS | `{"lab_run": 195, "valid_lab_record": true}` |
| M04 | PASS | `{"lab_run": 195, "valid_lab_record": true}` |
| M05 | PASS | `{"lab_run": 195, "valid_lab_record": true}` |
| M11 | PASS | `{"restored": true, "rolling_pointer": true}` |
| M12 | PASS | `{"snapshot": "C:\\PI-DON\\evidence\\gpt6_plan_v4_night\\g0_attempt_02\\reference_cache_snapshots.npz", "hash_match": true, "steps": 8192}` |
| M13 | PASS | `{"missing_rows_rejected": true, "duplicate_step_rejected": true, "bad_numeric_rejected": true, "missing_probe_rejected": true, "hash_tamper_rejected": true, "empty_required_set_rejected": true, "control_disguised_as_dco_rejected": true}` |
