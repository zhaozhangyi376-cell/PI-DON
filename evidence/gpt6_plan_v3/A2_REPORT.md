# A2 完整 G0 报告

- lab_log：#165
- G0：**PASS**

G0 认证合同、测量、参考时层和负对照。精确 Yee 结果只证明这条控制链路；不计入 DCO 成绩。

| 检查 | observed | 状态 |
|---|---|---|
| A1_contract_recovery_identity_fault_suite | `{"tests_run": 54, "failures": 0, "errors": 0}` | PASS |
| A2_float64_exact_128_with_restore | `{"steps": 128, "gate": true, "restored_at": 64, "uncovered": 0, "six_component_metrics": true, "control_only": true, "reference_dtype": "float64"}` | PASS |
| A2_float32_exact_128_with_restore | `{"steps": 128, "gate": true, "restored_at": 64, "uncovered": 0, "six_component_metrics": true, "control_only": true, "reference_dtype": "float64"}` | PASS |
| A2_hard_source_only_negative | `{"steps": 128, "gate": false, "restored_at": null, "uncovered": 0, "six_component_metrics": true, "control_only": true, "reference_dtype": "float64"}` | PASS |
| A2_wrong_H_half_negative | `{"steps": 128, "gate": false, "restored_at": null, "uncovered": 0, "six_component_metrics": true, "control_only": true, "reference_dtype": "float64"}` | PASS |
| A2_zero_curl_negative | `{"steps": 128, "gate": false, "restored_at": null, "uncovered": 0, "six_component_metrics": true, "control_only": true, "reference_dtype": "float64"}` | PASS |
| A2_reference_cache_8192 | `{"steps": 8192, "source_mode": "hard", "snapshot_exists": true, "snapshot_hash": "25632ead722034259fe02817726111f2cba90159e78999cf8da2ac0952c640c4", "probe_count": 3}` | PASS |
