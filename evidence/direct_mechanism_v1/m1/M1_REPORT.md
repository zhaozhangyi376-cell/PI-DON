# M1 Report - Fixed Failure Target Diagnosis

Status: PASS (diagnostic delivered). Scientific status: NOT_APPLICABLE.

This report is diagnostic-only. It does not reclassify old FAIL rows and does not create a production checkpoint.

## Cases

### P_first_nonzero_E

- Source: `evidence/mechanism_decision_v1/runs/P/failure_raw_000001_attempt_1.pt`
- Phase / accepted steps: `E_pending` / `0`
- Recorded E final R: `0.0005160257095534574`
- Readback E R: `0.0005160256693459008`
- Float64 head-projection best E R: `0.0003637489861693063`
- Head projection primary read: `frozen_features_head_projection_cannot_reach_strict_R`
- E updates / elapsed in old row: `500` / `35.95526769995922` s
- H same-state readback R: `None`

### S_R_step34_E

- Source: `evidence/mechanism_1h_v2/runs/S_R/failure_raw_000034_attempt_1.pt`
- Phase / accepted steps: `E_pending` / `33`
- Recorded E final R: `0.00012504438289440666`
- Readback E R: `0.00012504439684588243`
- Float64 head-projection best E R: `0.00012504151098427515`
- Head projection primary read: `frozen_features_head_projection_cannot_reach_strict_R`
- E updates / elapsed in old row: `3000` / `218.5852673999616` s
- H same-state readback R: `9.936099917875362e-05`

## Outputs

- Audit JSON: `evidence/direct_mechanism_v1/m1/m1_audit.json`
- Diagnostic figure: `evidence/direct_mechanism_v1/m1/m1_diagnostic.png`

## Limits

- A head-projection pass or fail only describes these frozen intermediate features.
- M1 does not prove the whole network class can or cannot express the curl target.
- No old failure, resource limit, or recovery status is reclassified here.

