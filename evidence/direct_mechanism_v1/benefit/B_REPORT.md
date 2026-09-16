# B Report - Pretraining Benefit Pair

- Action: `A-20260914T165418-00ed3794`; lab_run_id: `289`
- Strict interpretation: field gate already failed in G128, so this B result cannot unlock 1024/8192.
- Residual-window cost comparison is reported as engineering/diagnostic evidence only.

| Arm | Status | Accepted | Adam | Closures | Elapsed s | H R | E R | Recovery |
|---|---|---:|---:|---:|---:|---:|---:|---|
| B-P | PASS | 128 | 44630 | 0 | 3502.87363690004 | 9.841101172563177e-05 | 9.943979027191016e-05 | False |
| B-R | PASS | 128 | 38127 | 0 | 2935.3384777000174 | 9.992266290590722e-05 | 9.968860361505215e-05 | False |
| B-R2 | PASS | 128 | 37588 | 0 | 4759.5542747 | 9.778989283552609e-05 | 9.979193762074037e-05 | False |

## Benefit Judgment

- Comparable residual-128 window: `True`.
- P-vs-random Adam savings: `[-0.1705615443124295, -0.18734702564648292]`.
- P-vs-random time savings: `[-0.19334572946582784, 0.26403326136651106]`.
- Residual cost benefit PASS: `False`.
- Field-gate benefit PASS: `False`.
- Conclusion: even if residual-window cost differs, it is not evidence of a useful PI-DON long-run solver while field/probe gates fail.

## Files

- Audit JSON: `evidence/direct_mechanism_v1/benefit/B_audit.json`
- R2 run: `evidence/direct_mechanism_v1/benefit/B_R2`
